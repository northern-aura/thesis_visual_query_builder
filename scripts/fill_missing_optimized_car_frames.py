#!/usr/bin/env python3
"""Fill the near-complete optimized car result caches.

This script is intentionally narrow. It only patches the four optimized car
queries whose result JSONL files are short by 1, 6, 7, and 9 rows. Existing
rows are treated as cached results; only the missing leading frames are sent to
the VLM.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2 as cv
import requests


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
METRICS = RESULTS / "metrics"
SUMMARY = METRICS / "summary.csv"
VIDEO = ROOT / "running" / "Topics" / "Cars" / "Data" / "cars-me" / "04" / "out_04.mp4"
GT_CSV = ROOT / "running" / "Topics" / "Cars" / "Data" / "cars-me" / "04" / "out_04.csv"
TARGET_FRAMES = 3953
MODEL = "RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8"
DEFAULT_SERVER = "http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"


PROMPT_COLOR_GENERIC = """Is there a car visible in this image? If yes, return the color of the car (do not take into consideration the bumper). The answer should be in lowercase and use only primary colors (e.g. black, white, gray, red, blue, etc.), also consider silver to be gray. In case that there are two cars in the frame, return the color of the one which has a visible license plate. If there is no car in the image return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!"""

PROMPT_COLOR_RED = """Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return "red". If the car is not red or there is no car, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!"""

PROMPT_COLOR_BLUE = """Is there a car visible in this image? If yes, is the car blue (do not take into consideration the bumper)? If the car is blue, return "blue". If the car is not blue or there is no car, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!"""

PROMPT_RED_PLATE = """Is there a car visible in this image? If yes, is the car red (do not take into consideration the bumper)? If the car is red, return its license plate in uppercase without any whitespaces. If the car is not red or there is no car or no license plate is visible, return the string SKIP.

Do not provide any text or any explanation, just the final answer in the correct format!"""


@dataclass(frozen=True)
class QueryPatch:
    title: str
    slug: str
    missing_count: int
    prompt: str
    task: str
    resize: tuple[int, int] | None
    pipeline_nodes: str


PATCHES = [
    QueryPatch(
        "Optimized Car Color Generic (R480)",
        "optimized_car_color_generic_r480",
        1,
        PROMPT_COLOR_GENERIC,
        "color_generic",
        (480, 270),
        "Source -> Decode -> Resize -> Llm -> Sink",
    ),
    QueryPatch(
        "Optimized Car Color Blue (CFblue+R480)",
        "optimized_car_color_blue_cfblue_r480",
        6,
        PROMPT_COLOR_BLUE,
        "color_blue",
        (480, 270),
        "Source -> Decode -> CV Color Filter -> Resize -> Llm -> Sink",
    ),
    QueryPatch(
        "Optimized Color+Plate Red (CFred native)",
        "optimized_color_plate_red_cfred_native",
        7,
        PROMPT_RED_PLATE,
        "red_plate",
        None,
        "Source -> Decode -> CV Color Filter -> Llm -> Sink",
    ),
    QueryPatch(
        "Optimized Car Color Red (CFred+R480)",
        "optimized_car_color_red_cfred_r480",
        9,
        PROMPT_COLOR_RED,
        "color_red",
        (480, 270),
        "Source -> Decode -> CV Color Filter -> Resize -> Llm -> Sink",
    ),
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def load_gt() -> list[tuple[str, str, str]]:
    out = []
    with GT_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            row = (row + ["", "", ""])[:3]
            out.append((row[0].strip(), row[1].strip(), row[2].strip()))
    return out[:TARGET_FRAMES]


def norm_label(value: Any) -> str:
    text = str(value or "").strip().strip('"').strip("'").lower()
    if text in {"", "skip", "none", "null", "nan"}:
        return ""
    text = text.replace("silver", "gray").replace("grey", "gray")
    return "".join(ch for ch in text if ch.isalnum())


def norm_plate(value: Any) -> str:
    text = str(value or "").strip().strip('"').strip("'").upper()
    if text in {"", "SKIP", "NONE", "NULL", "NAN"}:
        return ""
    return "".join(ch for ch in text if ch.isalnum())


def encode_frame(frame, resize: tuple[int, int] | None) -> str:
    if resize is not None:
        frame = cv.resize(frame, resize)
    ok, buffer = cv.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("OpenCV failed to encode frame as JPEG")
    return base64.b64encode(buffer).decode("utf-8")


def load_frames(max_frame_id: int) -> dict[int, Any]:
    cap = cv.VideoCapture(str(VIDEO))
    frames = {}
    frame_id = 0
    while cap.isOpened() and frame_id <= max_frame_id:
        ret, frame = cap.read()
        if not ret:
            break
        frames[frame_id] = frame
        frame_id += 1
    cap.release()
    missing = [idx for idx in range(max_frame_id + 1) if idx not in frames]
    if missing:
        raise RuntimeError(f"Could not read video frames: {missing}")
    return frames


def call_vllm(server: str, image_b64: str, prompt: str, timeout_s: int) -> tuple[str, float]:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
        "max_tokens": 50,
        "temperature": 0,
    }
    start = time.time()
    response = requests.post(
        f"{server.rstrip('/')}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=timeout_s,
    )
    elapsed = time.time() - start
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    return text.upper().strip(), elapsed


def accuracy_for_row(task: str, row: dict[str, Any]) -> dict[str, bool]:
    result_label = norm_label(row.get("result"))
    result_plate = norm_plate(row.get("result"))
    color = norm_label(row.get("annotation_color"))
    plate = norm_plate(row.get("annotation_plate"))
    if task == "color_generic":
        return {"color_match": result_label == color if color else result_label == ""}
    if task == "color_red":
        return {"color_match": result_label == "red" if color == "red" else result_label == ""}
    if task == "color_blue":
        return {"color_match": result_label == "blue" if color == "blue" else result_label == ""}
    if task == "red_plate":
        return {"plate_match": result_plate == plate if color == "red" and plate else result_plate == ""}
    raise ValueError(task)


def build_patch_row(
    patch: QueryPatch,
    frame_id: int,
    annotation: tuple[str, str, str],
    result: str,
    llm_elapsed: float,
    base_sent: float,
) -> dict[str, Any]:
    plate, brand, color = annotation
    sent = base_sent - (patch.missing_count - frame_id) * 0.05
    row = {
        "result": result,
        "annotation_plate": plate,
        "annotation_brand": brand,
        "annotation_color": color,
        "annotation_action": "",
        "annotation_actions": [],
        "sent": sent,
        "in": sent + llm_elapsed,
        "llm_time": llm_elapsed,
        "llm": MODEL,
        "cache_fill": True,
        "cache_fill_frame_id": frame_id,
    }
    accuracy = accuracy_for_row(patch.task, row)
    ops = {"Decode": 0.0, "LLM": round(llm_elapsed * 1000, 2)}
    if patch.resize is not None:
        ops["Resize"] = 0.0
    if "CV Color Filter" in patch.pipeline_nodes:
        ops["CVColorFilter"] = 0.0
    row["metrics"] = {
        "e2e_latency_ms": round(llm_elapsed * 1000, 2),
        "operator_latencies_ms": ops,
        "between_nodes_ms": [],
        "accuracy": accuracy,
        "llm_time_ms": round(llm_elapsed * 1000, 2),
    }
    return row


def fixed_frame_accuracy(task: str, rows: list[dict[str, Any]]) -> tuple[float, float | None, int]:
    correct = 0
    labeled = 0
    labeled_correct = 0
    llm_calls = 0
    for row in rows[:TARGET_FRAMES]:
        result_label = norm_label(row.get("result"))
        result_plate = norm_plate(row.get("result"))
        color = norm_label(row.get("annotation_color"))
        plate = norm_plate(row.get("annotation_plate"))
        if float(row.get("llm_time") or 0) > 0 or float((row.get("metrics") or {}).get("llm_time_ms") or 0) > 0:
            llm_calls += 1
        if task == "color_generic":
            gold = bool(color)
            pred = result_label == color if gold else result_label == ""
        elif task == "color_red":
            gold = color == "red"
            pred = result_label == "red" if gold else result_label == ""
        elif task == "color_blue":
            gold = color == "blue"
            pred = result_label == "blue" if gold else result_label == ""
        elif task == "red_plate":
            gold = color == "red" and bool(plate)
            pred = result_plate == plate if gold else result_plate == ""
        else:
            raise ValueError(task)
        if gold:
            labeled += 1
            labeled_correct += int(pred)
        correct += int(pred)
    frame_acc = 100.0 * correct / TARGET_FRAMES
    labeled_acc = 100.0 * labeled_correct / labeled if labeled else None
    return frame_acc, labeled_acc, llm_calls


def jaccard_pct(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 100.0
    union = a | b
    if not union:
        return 0.0
    return 100.0 * len(a & b) / len(union)


def overall_accuracy(task: str, rows: list[dict[str, Any]], gt: list[tuple[str, str, str]]) -> float:
    if task == "color_generic":
        pred = {norm_label(r.get("result")) for r in rows[:TARGET_FRAMES]}
        pred.discard("")
        truth = {norm_label(c) for _p, _b, c in gt}
        truth.discard("")
        return jaccard_pct(pred, truth)
    if task == "color_red":
        pred = any(norm_label(r.get("result")) == "red" for r in rows[:TARGET_FRAMES])
        truth = any(norm_label(c) == "red" for _p, _b, c in gt)
        return 100.0 if pred == truth else 0.0
    if task == "color_blue":
        pred = any(norm_label(r.get("result")) == "blue" for r in rows[:TARGET_FRAMES])
        truth = any(norm_label(c) == "blue" for _p, _b, c in gt)
        return 100.0 if pred == truth else 0.0
    if task == "red_plate":
        pred = {norm_plate(r.get("result")) for r in rows[:TARGET_FRAMES]}
        pred.discard("")
        truth = {norm_plate(p) for p, _b, c in gt if norm_label(c) == "red" and norm_plate(p)}
        return jaccard_pct(pred, truth)
    raise ValueError(task)


def avg_llm_ms(rows: list[dict[str, Any]]) -> float:
    vals = []
    for row in rows:
        ms = (row.get("metrics") or {}).get("llm_time_ms")
        if ms is None:
            ms = float(row.get("llm_time") or 0) * 1000
        try:
            value = float(ms)
            if value > 0:
                vals.append(value)
        except (TypeError, ValueError):
            pass
    return sum(vals) / len(vals) if vals else 0.0


def update_metric_json(patch: QueryPatch, rows: list[dict[str, Any]], frame_acc: float) -> None:
    path = METRICS / f"{patch.slug}.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    data["message_count"] = len(rows)
    data.setdefault("chart_summary", {})["total_processed"] = len(rows)
    agg = data.setdefault("aggregate_metrics", {})
    agg["avgLlmTime"] = avg_llm_ms(rows)
    acc = agg.setdefault("accuracy", {})
    if patch.task == "red_plate":
        acc["plate_match"] = frame_acc / 100.0
    else:
        acc["color_match"] = frame_acc / 100.0
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_summary_csv(patch: QueryPatch, rows: list[dict[str, Any]], frame_acc: float) -> None:
    if not SUMMARY.exists():
        return
    with SUMMARY.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        records = [row for row in reader]
    best_idx = None
    best_count = -1
    for idx, record in enumerate(records):
        if not record or record[0] != patch.title:
            continue
        try:
            count = int(float(record[3] or 0))
        except ValueError:
            count = 0
        if count > best_count:
            best_idx = idx
            best_count = count
    if best_idx is None:
        return
    record = records[best_idx]
    if len(record) == 19:
        record = [
            record[0],
            record[1],
            record[2],
            record[3],
            record[4],
            record[5],
            record[6],
            record[7],
            "",
            record[8],
            "",
            record[9],
            record[10],
            record[11],
            record[12],
            record[13],
            record[14],
            record[15],
            record[16],
            record[17],
            record[18],
        ]
        records[best_idx] = record
    record[3] = str(len(rows))
    color_idx = 12
    plate_idx = 13
    avg_llm_idx = 14
    pipeline_idx = 20
    if patch.task == "red_plate":
        record[plate_idx] = f"{frame_acc:.12g}"
    else:
        record[color_idx] = f"{frame_acc:.12g}"
    record[avg_llm_idx] = f"{avg_llm_ms(rows):.12g}"
    record[pipeline_idx] = patch.pipeline_nodes
    with SUMMARY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(records)


def make_backup(paths: list[Path]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = RESULTS / "cache_fill_backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    for path in paths:
        if path.exists():
            shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    gt = load_gt()
    frames = load_frames(max(p.missing_count for p in PATCHES) - 1)
    before_after = []
    generated: dict[str, list[dict[str, Any]]] = {}

    for patch in PATCHES:
        path = RESULTS / f"{patch.slug}.jsonl"
        rows = read_jsonl(path)
        if len(rows) >= TARGET_FRAMES:
            print(f"{patch.slug}: already has {len(rows)} rows; skipping")
            continue
        missing = TARGET_FRAMES - len(rows)
        if missing != patch.missing_count:
            raise RuntimeError(f"{patch.slug}: expected {patch.missing_count} missing rows, found {missing}")
        old_frame, old_labeled, _old_llm_calls = fixed_frame_accuracy(patch.task, rows)
        old_overall = overall_accuracy(patch.task, rows, gt)
        first_sent = float(rows[0].get("sent") or time.time())
        patch_rows = []
        for frame_id in range(missing):
            image_b64 = encode_frame(frames[frame_id], patch.resize)
            print(f"{patch.slug}: querying frame {frame_id}")
            result, elapsed = call_vllm(args.server, image_b64, patch.prompt, args.timeout)
            patch_rows.append(build_patch_row(patch, frame_id, gt[frame_id], result, elapsed, first_sent))
        new_rows = patch_rows + rows
        new_frame, new_labeled, new_llm_calls = fixed_frame_accuracy(patch.task, new_rows)
        new_overall = overall_accuracy(patch.task, new_rows, gt)
        generated[patch.slug] = new_rows
        before_after.append({
            "query": patch.title,
            "slug": patch.slug,
            "old_rows": len(rows),
            "new_rows": len(new_rows),
            "filled_frame_ids": " ".join(str(i) for i in range(missing)),
            "new_results": " ".join(r["result"] for r in patch_rows),
            "old_frame_accuracy": f"{old_frame:.4f}",
            "new_frame_accuracy": f"{new_frame:.4f}",
            "old_labeled_accuracy": "" if old_labeled is None else f"{old_labeled:.4f}",
            "new_labeled_accuracy": "" if new_labeled is None else f"{new_labeled:.4f}",
            "old_overall_accuracy": f"{old_overall:.4f}",
            "new_overall_accuracy": f"{new_overall:.4f}",
            "new_llm_calls": new_llm_calls,
        })

    if args.dry_run:
        print(json.dumps(before_after, indent=2))
        return

    paths_to_backup = [SUMMARY]
    for patch in PATCHES:
        paths_to_backup.append(RESULTS / f"{patch.slug}.jsonl")
        paths_to_backup.append(METRICS / f"{patch.slug}.json")
    backup_dir = make_backup(paths_to_backup)
    print(f"Backed up existing files to {backup_dir}")

    for patch in PATCHES:
        new_rows = generated.get(patch.slug)
        if not new_rows:
            continue
        frame_acc, _labeled_acc, _llm_calls = fixed_frame_accuracy(patch.task, new_rows)
        write_jsonl(RESULTS / f"{patch.slug}.jsonl", new_rows)
        update_metric_json(patch, new_rows, frame_acc)
        update_summary_csv(patch, new_rows, frame_acc)

    report_path = METRICS / "cache_fill_accuracy_report.csv"
    fields = [
        "query",
        "slug",
        "old_rows",
        "new_rows",
        "filled_frame_ids",
        "new_results",
        "old_frame_accuracy",
        "new_frame_accuracy",
        "old_labeled_accuracy",
        "new_labeled_accuracy",
        "old_overall_accuracy",
        "new_overall_accuracy",
        "new_llm_calls",
    ]
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(before_after)
    print(report_path)
    print(json.dumps(before_after, indent=2))


if __name__ == "__main__":
    main()
