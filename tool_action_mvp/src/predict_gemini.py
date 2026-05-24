from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from utils import read_json, read_jsonl, write_jsonl


DEFAULT_MODEL = "gemini-2.5-flash"
API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini API로 Tool-Action JSON을 예측합니다.")
    parser.add_argument("--tools", required=True, help="tools.json 경로")
    parser.add_argument("--data", required=True, help="test_data.jsonl 경로")
    parser.add_argument("--output", required=True, help="predictions JSONL 출력 경로")
    parser.add_argument("--limit", type=int, default=None, help="앞에서부터 처리할 샘플 수")
    parser.add_argument("--delay-seconds", type=float, default=0.0, help="요청 사이에 대기할 초")
    return parser.parse_args()


def load_dotenv_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    with env_path.open("r", encoding="utf-8") as file:
        for line in file:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def build_prompt(tools: list[dict[str, Any]], instruction: str) -> str:
    tool_text = json.dumps(tools, ensure_ascii=False, indent=2)
    return (
        "너는 Tool-Action JSON 예측기다.\n"
        "사용자의 한국어 지시문을 보고 다음에 호출해야 할 Tool-Action을 예측해라.\n"
        "실제 이메일, 캘린더, 슬랙, 파일, 웹 검색을 실행하지 마라.\n"
        "반드시 사용 가능한 tool_name 중 하나를 선택해라.\n"
        "응답은 JSON 객체 하나만 반환해라.\n\n"
        "응답 형식:\n"
        '{"tool_name":"string","arguments":{"key":"value"}}\n\n'
        f"사용 가능한 Tool 목록:\n{tool_text}\n\n"
        f"사용자 지시문:\n{instruction}"
    )


def load_tools(path: str) -> list[dict[str, Any]]:
    tools = read_json(path)
    if not isinstance(tools, list):
        raise ValueError("tools.json은 Tool 객체 리스트여야 합니다.")
    return tools


def strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    return match.group(1).strip() if match else cleaned


def validate_tool_action(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(strip_code_fence(value))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 파싱 실패: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Gemini 응답이 JSON 객체가 아닙니다.")
    if not isinstance(value.get("tool_name"), str):
        raise ValueError("Gemini 응답에 문자열 tool_name이 없습니다.")
    arguments = value.get("arguments")
    if arguments is None:
        value["arguments"] = {}
    elif not isinstance(arguments, dict):
        raise ValueError("Gemini 응답의 arguments가 객체가 아닙니다.")
    return {"tool_name": value["tool_name"], "arguments": value["arguments"]}


def extract_text(response_data: dict[str, Any]) -> str:
    candidates = response_data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini 응답에 candidates가 없습니다: {response_data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    text = "".join(texts).strip()
    if not text:
        raise ValueError(f"Gemini 응답 text가 비어 있습니다: {response_data}")
    return text


def call_gemini(api_key: str, model: str, tools: list[dict[str, Any]], instruction: str) -> dict[str, Any]:
    encoded_model = urllib.parse.quote(model, safe="")
    query = urllib.parse.urlencode({"key": api_key})
    url = f"{API_BASE_URL}/{encoded_model}:generateContent?{query}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_prompt(tools, instruction)}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    context = None
    if os.getenv("GEMINI_ALLOW_INSECURE_SSL") == "1":
        context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {error_body}") from exc
    return validate_tool_action(extract_text(response_data))


def predict_one(
    api_key: str,
    model: str,
    tools: list[dict[str, Any]],
    instruction: str,
) -> tuple[dict[str, Any] | None, bool, str | None, int]:
    started = time.perf_counter()
    try:
        action = call_gemini(api_key, model, tools, instruction)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return action, True, None, latency_ms
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return None, False, str(exc), latency_ms


def main() -> None:
    load_dotenv_file()
    args = parse_args()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 없습니다. .env 파일 또는 환경변수에 Gemini API 키를 설정하세요.")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    tools = load_tools(args.tools)
    data = read_jsonl(args.data)
    if args.limit is not None:
        data = data[: args.limit]

    predictions: list[dict[str, Any]] = []
    print(f"Gemini 모델: {model}")
    print(f"처리할 샘플 수: {len(data)}")

    for index, item in enumerate(data, start=1):
        if index > 1 and args.delay_seconds > 0:
            print(f"{args.delay_seconds}초 대기 후 다음 요청을 보냅니다.")
            time.sleep(args.delay_seconds)
        instruction = str(item.get("instruction", ""))
        pred_action, json_success, error, latency_ms = predict_one(api_key, model, tools, instruction)
        predictions.append(
            {
                "id": item.get("id"),
                "instruction": instruction,
                "gold_action": item.get("gold_action"),
                "pred_action": pred_action,
                "json_success": json_success,
                "error": error,
                "latency_ms": latency_ms,
            }
        )
        status = "성공" if json_success else f"실패: {error}"
        print(f"[{index}/{len(data)}] id={item.get('id')} {status}")

    write_jsonl(args.output, predictions)
    print(f"예측 결과 저장: {args.output}")


if __name__ == "__main__":
    main()
