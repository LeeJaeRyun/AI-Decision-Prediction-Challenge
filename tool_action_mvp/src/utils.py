from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} 파일을 찾을 수 없습니다: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} 경로가 파일이 아닙니다: {path}")


def read_json(path: str | Path) -> Any:
    json_path = Path(path)
    ensure_file(json_path, "JSON")
    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str | Path, data: Any) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    jsonl_path = Path(path)
    ensure_file(jsonl_path, "JSONL")
    rows: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{jsonl_path}:{line_number} JSON 파싱 실패: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"{jsonl_path}:{line_number} JSON 객체가 아닙니다.")
            rows.append(item)
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    jsonl_path = Path(path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_tool_names(path: str | Path) -> set[str]:
    tools = read_json(path)
    if not isinstance(tools, list):
        raise ValueError("tools.json은 Tool 객체 리스트여야 합니다.")
    names: set[str] = set()
    for index, tool in enumerate(tools, start=1):
        if not isinstance(tool, dict) or not isinstance(tool.get("tool_name"), str):
            raise ValueError(f"tools.json의 {index}번째 항목에 tool_name이 없습니다.")
        names.add(tool["tool_name"])
    return names
