from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from utils import read_json


METRIC_COLUMNS = [
    "total",
    "tool_accuracy",
    "argument_f1",
    "normalized_argument_f1",
    "exact_match",
    "normalized_exact_match",
    "json_success_rate",
    "hallucinated_tool_rate",
    "avg_latency_ms",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="여러 evaluation JSON을 하나의 결과표 CSV로 합칩니다.")
    parser.add_argument("--inputs", nargs="+", required=True, help="evaluation JSON 경로들")
    parser.add_argument("--names", nargs="+", required=True, help="각 입력 파일의 방법 이름")
    parser.add_argument("--output", required=True, help="결과표 CSV 출력 경로")
    return parser.parse_args()


def build_rows(inputs: list[str], names: list[str]) -> list[dict[str, Any]]:
    if len(inputs) != len(names):
        raise ValueError("--inputs 개수와 --names 개수가 같아야 합니다.")

    rows: list[dict[str, Any]] = []
    for path, name in zip(inputs, names, strict=True):
        metrics = read_json(path)
        row = {"method": name}
        for column in METRIC_COLUMNS:
            row[column] = metrics.get(column, 0)
        rows.append(row)
    return rows


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["method", *METRIC_COLUMNS]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows = build_rows(args.inputs, args.names)
    write_csv(args.output, rows)
    print(f"결과표 저장: {args.output}")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
