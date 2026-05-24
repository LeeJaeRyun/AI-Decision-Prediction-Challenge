from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from utils import load_tool_names, read_jsonl, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tool-Action 예측 결과를 평가합니다.")
    parser.add_argument("--tools", required=True, help="tools.json 경로")
    parser.add_argument("--predictions", required=True, help="predictions JSONL 경로")
    parser.add_argument("--output", required=True, help="evaluation JSON 출력 경로")
    parser.add_argument("--detail", required=True, help="상세 CSV 출력 경로")
    return parser.parse_args()


def argument_pairs(arguments: Any, normalize: bool = False) -> set[tuple[str, str]]:
    if not isinstance(arguments, dict):
        return set()
    pairs: set[tuple[str, str]] = set()
    for key, value in arguments.items():
        if normalize:
            for candidate in normalized_value_candidates(value):
                pairs.add((str(key), candidate))
        else:
            serialized_value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            pairs.add((str(key), serialized_value))
    return pairs


def normalized_value_candidates(value: Any) -> set[str]:
    if not isinstance(value, str):
        return {json.dumps(value, ensure_ascii=False, sort_keys=True)}

    text = re.sub(r"\s+", " ", value.strip())
    time_candidates = korean_time_candidates(text)
    if time_candidates:
        return time_candidates
    return {json.dumps(text, ensure_ascii=False, sort_keys=True)}


def korean_time_candidates(text: str) -> set[str]:
    hhmm_match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if hhmm_match:
        hour = int(hhmm_match.group(1))
        minute = int(hhmm_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {f"{hour:02d}:{minute:02d}"}

    match = re.fullmatch(r"(오전|오후|저녁|밤|아침|새벽)?\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", text)
    if not match:
        return set()

    period = match.group(1)
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return set()

    if period in {"오후", "저녁", "밤"} and hour < 12:
        return {f"{hour + 12:02d}:{minute:02d}"}
    if period in {"오전", "아침", "새벽"}:
        if hour == 12:
            hour = 0
        return {f"{hour:02d}:{minute:02d}"}
    if hour <= 11:
        return {f"{hour:02d}:{minute:02d}", f"{hour + 12:02d}:{minute:02d}"}
    return {f"{hour:02d}:{minute:02d}"}


def argument_f1(gold_arguments: Any, pred_arguments: Any, normalize: bool = False) -> float:
    gold_pairs = argument_pairs(gold_arguments, normalize=normalize)
    pred_pairs = argument_pairs(pred_arguments, normalize=normalize)
    if not gold_pairs and not pred_pairs:
        return 1.0
    if not pred_pairs:
        return 0.0
    true_positive = len(gold_pairs & pred_pairs)
    precision = true_positive / len(pred_pairs) if pred_pairs else 0.0
    recall = true_positive / len(gold_pairs) if gold_pairs else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def is_exact_match(gold_action: dict[str, Any], pred_action: Any) -> bool:
    return isinstance(pred_action, dict) and pred_action == gold_action


def is_normalized_exact_match(gold_action: dict[str, Any], pred_action: Any) -> bool:
    if not isinstance(pred_action, dict):
        return False
    if pred_action.get("tool_name") != gold_action.get("tool_name"):
        return False
    return argument_pairs(gold_action.get("arguments", {}), normalize=True) == argument_pairs(
        pred_action.get("arguments", {}),
        normalize=True,
    )


def evaluate_rows(rows: list[dict[str, Any]], tool_names: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    details: list[dict[str, Any]] = []
    total = len(rows)
    tool_correct_count = 0
    exact_match_count = 0
    normalized_exact_match_count = 0
    json_success_count = 0
    hallucinated_count = 0
    f1_sum = 0.0
    normalized_f1_sum = 0.0
    latency_values: list[float] = []

    for row in rows:
        gold_action = row.get("gold_action") if isinstance(row.get("gold_action"), dict) else {}
        pred_action = row.get("pred_action") if isinstance(row.get("pred_action"), dict) else None
        gold_tool = gold_action.get("tool_name")
        pred_tool = pred_action.get("tool_name") if pred_action else None
        tool_correct = pred_tool == gold_tool
        sample_f1 = argument_f1(gold_action.get("arguments", {}), pred_action.get("arguments", {}) if pred_action else None)
        normalized_sample_f1 = argument_f1(
            gold_action.get("arguments", {}),
            pred_action.get("arguments", {}) if pred_action else None,
            normalize=True,
        )
        exact_match = is_exact_match(gold_action, pred_action)
        normalized_exact_match = is_normalized_exact_match(gold_action, pred_action)
        json_success = row.get("json_success") is True
        hallucinated_tool = pred_tool is not None and pred_tool not in tool_names

        tool_correct_count += int(tool_correct)
        exact_match_count += int(exact_match)
        normalized_exact_match_count += int(normalized_exact_match)
        json_success_count += int(json_success)
        hallucinated_count += int(hallucinated_tool)
        f1_sum += sample_f1
        normalized_f1_sum += normalized_sample_f1
        if isinstance(row.get("latency_ms"), (int, float)):
            latency_values.append(float(row["latency_ms"]))

        details.append(
            {
                "id": row.get("id"),
                "instruction": row.get("instruction", ""),
                "gold_tool": gold_tool,
                "pred_tool": pred_tool,
                "tool_correct": tool_correct,
                "argument_f1": sample_f1,
                "normalized_argument_f1": normalized_sample_f1,
                "exact_match": exact_match,
                "normalized_exact_match": normalized_exact_match,
                "json_success": json_success,
                "hallucinated_tool": hallucinated_tool,
                "gold_action": json.dumps(gold_action, ensure_ascii=False, sort_keys=True),
                "pred_action": json.dumps(pred_action, ensure_ascii=False, sort_keys=True),
                "error": row.get("error"),
            }
        )

    metrics = {
        "total": total,
        "tool_accuracy": tool_correct_count / total if total else 0.0,
        "argument_f1": f1_sum / total if total else 0.0,
        "normalized_argument_f1": normalized_f1_sum / total if total else 0.0,
        "exact_match": exact_match_count / total if total else 0.0,
        "normalized_exact_match": normalized_exact_match_count / total if total else 0.0,
        "json_success_rate": json_success_count / total if total else 0.0,
        "hallucinated_tool_rate": hallucinated_count / total if total else 0.0,
        "avg_latency_ms": sum(latency_values) / len(latency_values) if latency_values else 0.0,
    }
    return metrics, details


def write_detail_csv(path: str | Path, details: list[dict[str, Any]]) -> None:
    detail_path = Path(path)
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "instruction",
        "gold_tool",
        "pred_tool",
        "tool_correct",
        "argument_f1",
        "normalized_argument_f1",
        "exact_match",
        "normalized_exact_match",
        "json_success",
        "hallucinated_tool",
        "gold_action",
        "pred_action",
        "error",
    ]
    with detail_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(details)


def main() -> None:
    args = parse_args()
    print(f"도구 목록 로드: {args.tools}")
    tool_names = load_tool_names(args.tools)
    print(f"예측 결과 로드: {args.predictions}")
    rows = read_jsonl(args.predictions)
    metrics, details = evaluate_rows(rows, tool_names)
    write_json(args.output, metrics)
    write_detail_csv(args.detail, details)
    print(f"평가 JSON 저장: {args.output}")
    print(f"상세 CSV 저장: {args.detail}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
