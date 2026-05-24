from __future__ import annotations

import argparse
import random
import re
import time
from typing import Any

from utils import read_json, read_jsonl, write_jsonl


KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["날씨", "비", "기온"], "weather.search"),
    (["메일", "이메일", "교수님", "인사팀", "고객사"], "email.send"),
    (["슬랙", "채널", "팀에 알려", "올려줘", "메시지"], "slack.send_message"),
    (["알림", "리마인더", "까먹지"], "reminder.create"),
    (["문서", "파일"], "file.create_document"),
    (["할 일", "todo", "작업"], "todo.create_task"),
    (["장소", "지도", "근처", "주변", "가까운"], "map.search_place"),
    (["번역"], "translate.text"),
    (["계산", "곱하기", "나누기", "%"], "calculator.calculate"),
    (["검색", "찾아"], "web.search"),
    (["수정", "변경", "바꿔", "늦춰"], "calendar.update_event"),
    (["일정", "회의", "캘린더", "등록"], "calendar.create_event"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenAI API 없이 baseline 예측을 생성합니다.")
    parser.add_argument("--tools", required=True, help="tools.json 경로")
    parser.add_argument("--data", required=True, help="test_data.jsonl 경로")
    parser.add_argument("--method", required=True, choices=["random", "keyword"], help="baseline 방법")
    parser.add_argument("--output", required=True, help="predictions JSONL 출력 경로")
    return parser.parse_args()


def load_tools(path: str) -> list[dict[str, Any]]:
    tools = read_json(path)
    if not isinstance(tools, list):
        raise ValueError("tools.json은 리스트 형식이어야 합니다.")
    return tools


def random_predict(tools: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    tool = rng.choice(tools)
    return {"tool_name": tool["tool_name"], "arguments": {}}


def keyword_predict(instruction: str, fallback_tool: str) -> dict[str, Any]:
    selected_tool = fallback_tool
    for keywords, tool_name in KEYWORD_RULES:
        if any(keyword in instruction for keyword in keywords):
            selected_tool = tool_name
            break
    return {"tool_name": selected_tool, "arguments": extract_simple_arguments(selected_tool, instruction)}


def extract_simple_arguments(tool_name: str, instruction: str) -> dict[str, str]:
    if tool_name == "weather.search":
        location = first_match(instruction, ["서울", "부산", "제주도", "강남"])
        date = first_match(instruction, ["오늘", "내일", "이번 주말"])
        return compact({"location": location, "date": date})
    if tool_name == "translate.text":
        target_language = first_match(instruction, ["영어", "일본어", "한국어", "중국어"])
        text = instruction.split(":", 1)[1].strip() if ":" in instruction else ""
        return compact({"text": text, "target_language": target_language})
    if tool_name == "calculator.calculate":
        expression = extract_expression(instruction)
        return compact({"expression": expression})
    if tool_name == "map.search_place":
        location = first_match(instruction, ["강남역 근처", "회사 주변", "홍대입구역 근처", "서울역"])
        query = re.sub(r"(찾아줘|검색해줘|지도에서|근처|주변|가장 가까운)", "", instruction).strip()
        return compact({"query": query, "location": location})
    if tool_name == "todo.create_task":
        due_date = first_match(instruction, ["오늘", "내일", "이번 주"])
        return compact({"task": strip_command_words(instruction), "due_date": due_date})
    if tool_name == "calendar.create_event":
        date = first_match(instruction, ["오늘", "내일", "금요일", "다음 주 월요일"])
        time_text = extract_time(instruction)
        return compact({"title": strip_command_words(instruction), "date": date, "time": time_text})
    if tool_name == "calendar.update_event":
        time_text = extract_time(instruction)
        return compact({"event": strip_command_words(instruction), "time": time_text})
    return {}


def first_match(text: str, candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in text:
            return candidate
    return ""


def compact(arguments: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in arguments.items() if value}


def strip_command_words(text: str) -> str:
    cleaned = re.sub(r"(해줘|추가해줘|등록해줘|만들어줘|잡아줘|넣어줘|일정|할 일|todo|캘린더)", "", text)
    return cleaned.strip(" .")


def extract_time(text: str) -> str:
    match = re.search(r"(오전|오후)?\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", text)
    if not match:
        return ""
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    if match.group(1) == "오후" and hour < 12:
        hour += 12
    if match.group(1) == "오전" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def extract_expression(text: str) -> str:
    expression = text.replace("곱하기", "*").replace("나누기", "/").replace("더하기", "+").replace("빼기", "-")
    expression = expression.replace("계산해줘", "")
    tokens = re.findall(r"\d+(?:\.\d+)?|[+\-*/%]", expression)
    return " ".join(tokens)


def build_predictions(method: str, tools: list[dict[str, Any]], data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(42)
    fallback_tool = tools[0]["tool_name"]
    predictions: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        start = time.perf_counter()
        if method == "random":
            pred_action = random_predict(tools, rng)
        else:
            pred_action = keyword_predict(str(item.get("instruction", "")), fallback_tool)
        latency_ms = int((time.perf_counter() - start) * 1000)
        predictions.append(
            {
                "id": item.get("id"),
                "instruction": item.get("instruction"),
                "gold_action": item.get("gold_action"),
                "pred_action": pred_action,
                "json_success": True,
                "error": None,
                "latency_ms": latency_ms,
            }
        )
        print(f"[{index}/{len(data)}] {method} 예측 완료: id={item.get('id')}")
    return predictions


def main() -> None:
    args = parse_args()
    tools = load_tools(args.tools)
    data = read_jsonl(args.data)
    predictions = build_predictions(args.method, tools, data)
    write_jsonl(args.output, predictions)
    print(f"예측 결과 저장: {args.output}")


if __name__ == "__main__":
    main()
