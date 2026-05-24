from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from utils import read_json, read_jsonl, write_jsonl


DEFAULT_MODEL = "gpt-4o-mini"


class ToolAction(BaseModel):
    tool_name: str = Field(description="호출할 도구 이름")
    arguments: dict[str, Any] = Field(default_factory=dict, description="도구 호출 인자")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenAI API로 Tool-Action JSON을 예측합니다.")
    parser.add_argument("--tools", required=True, help="tools.json 경로")
    parser.add_argument("--data", required=True, help="test_data.jsonl 경로")
    parser.add_argument("--output", required=True, help="predictions JSONL 출력 경로")
    parser.add_argument("--limit", type=int, default=None, help="앞에서부터 처리할 샘플 수")
    return parser.parse_args()


def build_prompt(tools: list[dict[str, Any]], instruction: str) -> list[dict[str, str]]:
    tool_text = json.dumps(tools, ensure_ascii=False, indent=2)
    return [
        {
            "role": "system",
            "content": (
                "너는 사용자의 한국어 지시문을 보고 다음에 호출해야 할 Tool-Action JSON만 예측한다. "
                "실제 이메일, 캘린더, 슬랙, 파일, 웹 검색을 실행하지 않는다. "
                "반드시 사용 가능한 tool_name 중 하나를 선택하고 JSON 객체만 반환한다."
            ),
        },
        {
            "role": "user",
            "content": (
                "사용 가능한 Tool 목록:\n"
                f"{tool_text}\n\n"
                "사용자 지시문:\n"
                f"{instruction}\n\n"
                "응답 형식:\n"
                '{"tool_name":"string","arguments":{"key":"value"}}'
            ),
        },
    ]


def parse_tool_action(raw_text: str) -> ToolAction:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 파싱 실패: {exc}") from exc
    try:
        return ToolAction.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"ToolAction 스키마 검증 실패: {exc}") from exc


def predict_one(client: OpenAI, model: str, tools: list[dict[str, Any]], instruction: str) -> tuple[dict[str, Any] | None, bool, str | None, int]:
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=build_prompt(tools, instruction),
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("모델 응답이 비어 있습니다.")
        action = parse_tool_action(content)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return action.model_dump(), True, None, latency_ms
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return None, False, str(exc), latency_ms


def load_tools(path: str) -> list[dict[str, Any]]:
    tools = read_json(path)
    if not isinstance(tools, list):
        raise ValueError("tools.json은 Tool 객체 리스트여야 합니다.")
    return tools


def main() -> None:
    load_dotenv()
    args = parse_args()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 없습니다. .env 파일 또는 환경변수에 API 키를 설정하세요.")

    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    tools = load_tools(args.tools)
    data = read_jsonl(args.data)
    if args.limit is not None:
        data = data[: args.limit]

    client = OpenAI(api_key=api_key)
    predictions: list[dict[str, Any]] = []
    print(f"OpenAI 모델: {model}")
    print(f"처리할 샘플 수: {len(data)}")

    for index, item in enumerate(data, start=1):
        instruction = str(item.get("instruction", ""))
        pred_action, json_success, error, latency_ms = predict_one(client, model, tools, instruction)
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
