#!/usr/bin/env python3
"""Re-score saved optimized volleyball query outputs with task-specific metrics.

The streaming pipeline's built-in action accuracy compares aggregate/windowed
outputs directly to per-frame action labels, which makes the optimized
volleyball queries score as 0 even when their output is useful. This script
evaluates the saved JSONL files in their actual output space:

* repeated spikers: binary spiking counts/events per 20-frame window
* motion category: window motion category derived from GT action labels
* spike bbox: detection/count parsing from aggregate bbox outputs

Existing result files do not preserve frame ids or ordered per-frame predictions
after window aggregation, so bbox IoU and exact per-frame alignment cannot be
computed from the saved JSONL alone. The script reports those limitations
explicitly.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"
METRICS_DIR = RESULTS_DIR / "metrics"
TARGET_FRAMES = 4000


FILES = {
    "repeated_spikers": RESULTS_DIR / "case_repeated_spikers_g_r854.jsonl",
    "motion_category": RESULTS_DIR / "case_motion_category_r480.jsonl",
    "spike_bbox": RESULTS_DIR / "case_spike_bbox_r960_b3.jsonl",
}
INPUT_DUMP = METRICS_DIR / f"volleyball_video_input_{TARGET_FRAMES}.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_input_frames(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Dump Kafka input first, e.g. "
            "docker exec docker-kafka-1 kafka-console-consumer.sh "
            "--bootstrap-server localhost:9092 --topic volleyball_video "
            f"--from-beginning --max-messages {TARGET_FRAMES} > {INPUT_DUMP.as_posix()}"
        )
    frames = load_jsonl(path)
    return frames[:TARGET_FRAMES]


def norm_action(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "spike": "spiking",
        "spiker": "spiking",
        "attack": "spiking",
        "attacking": "spiking",
        "set": "setting",
        "block": "blocking",
        "dig": "digging",
        "stand": "standing",
    }
    return aliases.get(text, text)


def result_counts(row: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in row.get("result", []):
        if not isinstance(item, list) or len(item) < 2:
            continue
        label = str(item[0] or "").strip().upper()
        try:
            count = int(item[1])
        except (TypeError, ValueError):
            count = 1
        counts[label] += count
    return counts


def is_pred_spiking(label: str) -> bool:
    text = label.strip().lower()
    return "spik" in text and text != "skip"


def is_bbox_like(label: str) -> bool:
    if label.strip().upper() == "SKIP":
        return False
    nums = re.findall(r"-?\d+", label)
    return len(nums) >= 4


def motion_bucket(action: str) -> str:
    action = norm_action(action)
    if action in {"", "standing", "waiting", "none", "skip"}:
        return "still"
    return "moving"


def motion_category_from_actions(actions: list[str]) -> str:
    if not actions:
        return "SKIP"
    moving = sum(1 for action in actions if motion_bucket(action) == "moving")
    ratio = moving / len(actions)
    if moving == 0:
        return "NONE_MOVING"
    if ratio == 1:
        return "ALL_MOVING"
    if ratio > 0.5:
        return "MOST_MOVING"
    return "SOME_MOVING"


def dominant_pred_category(counts: Counter[str]) -> str:
    non_empty = Counter({k: v for k, v in counts.items() if k and k != "SKIP"})
    if not non_empty:
        return "SKIP"
    return non_empty.most_common(1)[0][0]


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def pct(num: float, den: float) -> float:
    return round(100.0 * safe_div(num, den), 2)


def input_windows(frames: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    windows: list[list[dict[str, Any]]] = []
    cursor = 0
    for row in rows:
        n = int(row.get("frames", 0))
        windows.append(frames[cursor : cursor + n])
        cursor += n
    return windows


def evaluate_repeated_spikers(rows: list[dict[str, Any]], frames: list[dict[str, Any]]) -> dict[str, Any]:
    represented = sum(int(r.get("frames", 0)) for r in rows)
    pred_pos = 0
    gt_pos = 0
    known_frames = 0
    count_tp = 0
    event_tp = event_fp = event_fn = event_tn = 0

    for row, gt_window in zip(rows, input_windows(frames, rows)):
        actions = [norm_action(frame.get("gt_action", "")) for frame in gt_window]
        known = [a for a in actions if a]
        known_frames += len(known)
        gt = sum(1 for a in actions if a == "spiking")
        pred = sum(c for label, c in result_counts(row).items() if is_pred_spiking(label))

        pred_pos += pred
        gt_pos += gt
        count_tp += min(pred, gt)

        pred_event = pred > 0
        gt_event = gt > 0
        if pred_event and gt_event:
            event_tp += 1
        elif pred_event and not gt_event:
            event_fp += 1
        elif not pred_event and gt_event:
            event_fn += 1
        else:
            event_tn += 1

    fixed_correct_lower_bound = TARGET_FRAMES - pred_pos if gt_pos == 0 else count_tp
    count_precision = safe_div(count_tp, pred_pos)
    count_recall = safe_div(count_tp, gt_pos)
    count_f1 = safe_div(2 * count_precision * count_recall, count_precision + count_recall)
    event_precision = safe_div(event_tp, event_tp + event_fp)
    event_recall = safe_div(event_tp, event_tp + event_fn)
    event_f1 = safe_div(2 * event_precision * event_recall, event_precision + event_recall)

    return {
        "query": "Case Repeated Spikers (G+R854)",
        "target_frames": TARGET_FRAMES,
        "represented_frames": represented,
        "missing_frames": TARGET_FRAMES - represented,
        "coverage_pct": pct(represented, TARGET_FRAMES),
        "windows": len(rows),
        "known_gt_frames": known_frames,
        "gt_spiking_frames_in_windows": gt_pos,
        "pred_spiking_votes": pred_pos,
        "count_true_positive_overlap": count_tp,
        "fixed_target_lower_bound_correct": fixed_correct_lower_bound,
        "fixed_target_lower_bound_accuracy_pct": pct(fixed_correct_lower_bound, TARGET_FRAMES),
        "frame_count_precision_pct": round(count_precision * 100, 2),
        "frame_count_recall_pct": round(count_recall * 100, 2),
        "frame_count_f1_pct": round(count_f1 * 100, 2),
        "event_tp": event_tp,
        "event_fp": event_fp,
        "event_fn": event_fn,
        "event_tn": event_tn,
        "event_accuracy_pct": pct(event_tp + event_tn, len(rows)),
        "event_precision_pct": round(event_precision * 100, 2),
        "event_recall_pct": round(event_recall * 100, 2),
        "event_f1_pct": round(event_f1 * 100, 2),
        "notes": "Uses Kafka input GT. Count-based frame metric; exact frame alignment is unavailable after window aggregation.",
    }


def evaluate_motion(rows: list[dict[str, Any]], frames: list[dict[str, Any]]) -> dict[str, Any]:
    represented = sum(int(r.get("frames", 0)) for r in rows)
    correct_windows = 0
    labeled_correct_frames = 0
    known_frames = 0
    pred_counts: Counter[str] = Counter()
    gt_counts: Counter[str] = Counter()
    confusion: Counter[str] = Counter()
    scored_windows = 0

    for row, gt_window in zip(rows, input_windows(frames, rows)):
        frames = int(row.get("frames", 0))
        actions = [norm_action(frame.get("gt_action", "")) for frame in gt_window]
        labeled_actions = [a for a in actions if a]
        if not labeled_actions:
            gt = "UNKNOWN"
        else:
            gt = motion_category_from_actions(labeled_actions)
            scored_windows += 1
            known_frames += len(labeled_actions)
        pred = dominant_pred_category(result_counts(row))
        gt_counts[gt] += 1
        pred_counts[pred] += 1
        confusion[f"{gt}->{pred}"] += 1
        if pred == gt:
            correct_windows += 1
            labeled_correct_frames += len(labeled_actions)

    known_gt_counts = Counter({k: v for k, v in gt_counts.items() if k != "UNKNOWN"})
    majority_gt = known_gt_counts.most_common(1)[0][0] if known_gt_counts else "UNKNOWN"
    majority_pred = pred_counts.most_common(1)[0][0] if pred_counts else "SKIP"

    return {
        "query": "Case Motion Category (R480)",
        "target_frames": TARGET_FRAMES,
        "represented_frames": represented,
        "missing_frames": TARGET_FRAMES - represented,
        "coverage_pct": pct(represented, TARGET_FRAMES),
        "windows": len(rows),
        "scored_windows_with_gt": scored_windows,
        "known_gt_frames": known_frames,
        "window_correct": correct_windows,
        "window_accuracy_pct_on_gt_windows": pct(correct_windows, scored_windows),
        "labeled_frame_correct": labeled_correct_frames,
        "labeled_frame_accuracy_pct": pct(labeled_correct_frames, known_frames),
        "fixed_target_lower_bound_accuracy_pct": pct(labeled_correct_frames, TARGET_FRAMES),
        "majority_gt": majority_gt,
        "majority_pred": majority_pred,
        "overall_task_correct": majority_gt == majority_pred,
        "gt_window_counts": dict(gt_counts),
        "pred_window_counts": dict(pred_counts),
        "confusion": dict(confusion),
        "notes": "GT motion category is derived from Kafka input gt_action labels; UNKNOWN windows are excluded from GT-window accuracy.",
    }


def evaluate_spike_bbox(rows: list[dict[str, Any]], frames: list[dict[str, Any]]) -> dict[str, Any]:
    represented = sum(int(r.get("frames", 0)) for r in rows)
    gt_spike = 0
    known_frames = 0
    pred_bbox = 0
    parse_errors = 0
    window_tp = window_fp = window_fn = window_tn = 0

    for row, gt_window in zip(rows, input_windows(frames, rows)):
        actions = [norm_action(frame.get("gt_action", "")) for frame in gt_window]
        known_frames += sum(1 for a in actions if a)
        gt = sum(1 for a in actions if a == "spiking")
        counts = result_counts(row)
        pred = sum(c for label, c in counts.items() if is_bbox_like(label))
        err = sum(c for label, c in counts.items() if label != "SKIP" and not is_pred_spiking(label) and not is_bbox_like(label))

        gt_spike += gt
        pred_bbox += pred
        parse_errors += err

        pred_event = pred > 0
        gt_event = gt > 0
        if pred_event and gt_event:
            window_tp += 1
        elif pred_event and not gt_event:
            window_fp += 1
        elif not pred_event and gt_event:
            window_fn += 1
        else:
            window_tn += 1

    event_precision = safe_div(window_tp, window_tp + window_fp)
    event_recall = safe_div(window_tp, window_tp + window_fn)
    event_f1 = safe_div(2 * event_precision * event_recall, event_precision + event_recall)
    count_precision = safe_div(min(pred_bbox, gt_spike), pred_bbox)
    count_recall = safe_div(min(pred_bbox, gt_spike), gt_spike)

    return {
        "query": "Case Spike Bbox (R960+B3)",
        "target_frames": TARGET_FRAMES,
        "represented_frames": represented,
        "missing_frames": TARGET_FRAMES - represented,
        "coverage_pct": pct(represented, TARGET_FRAMES),
        "windows": len(rows),
        "known_gt_frames": known_frames,
        "gt_spiking_frames_in_windows": gt_spike,
        "parsed_bbox_votes": pred_bbox,
        "parse_error_votes": parse_errors,
        "fixed_target_lower_bound_accuracy_pct": pct(TARGET_FRAMES - pred_bbox, TARGET_FRAMES) if gt_spike == 0 else None,
        "count_precision_upper_bound_pct": round(count_precision * 100, 2),
        "count_recall_upper_bound_pct": round(count_recall * 100, 2),
        "event_tp": window_tp,
        "event_fp": window_fp,
        "event_fn": window_fn,
        "event_tn": window_tn,
        "event_accuracy_pct": pct(window_tp + window_tn, len(rows)),
        "event_precision_pct": round(event_precision * 100, 2),
        "event_recall_pct": round(event_recall * 100, 2),
        "event_f1_pct": round(event_f1 * 100, 2),
        "iou_at_50_pct": None,
        "mean_iou": None,
        "notes": "Uses Kafka input GT actions. IoU still cannot be computed from saved aggregate JSONL because ordered per-frame bbox predictions were not preserved.",
    }


def main() -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    input_frames = load_input_frames(INPUT_DUMP)
    repeated = evaluate_repeated_spikers(load_jsonl(FILES["repeated_spikers"]), input_frames)
    motion = evaluate_motion(load_jsonl(FILES["motion_category"]), input_frames)
    bbox = evaluate_spike_bbox(load_jsonl(FILES["spike_bbox"]), input_frames)
    results = [repeated, motion, bbox]

    json_path = METRICS_DIR / "optimized_volleyball_reeval.json"
    csv_path = METRICS_DIR / "optimized_volleyball_reeval.csv"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    fieldnames = sorted({key for row in results for key in row})
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"Wrote {csv_path.relative_to(REPO_ROOT)}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
