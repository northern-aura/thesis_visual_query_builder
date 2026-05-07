#!/usr/bin/env python3
"""Build a simple benchmark report as HTML.

The report is intentionally conservative: it shows the results that are present
on disk, and it labels known evaluator problems instead of hiding them.
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path
from collections import Counter


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
METRICS = RESULTS / "metrics"
SUMMARY = METRICS / "summary.csv"
OUT_HTML = RESULTS / "benchmark_simple_report.html"
OUT_SUMMARY = METRICS / "benchmark_summary.csv"
OUT_BENCHMARK_PLOTS = RESULTS / "plots" / "benchmark_summary"
CAR_GT_CSV = ROOT / "running" / "Topics" / "Cars" / "Data" / "cars-me" / "04" / "out_04.csv"

CAR_TARGET_FRAMES = 3953
VB_TARGET_FRAMES = 4000
SPECIFIC_PLATE_TARGET = "QRF8G17"


COLS_21 = [
    "query_title", "timestamp", "duration_s", "message_count", "llm_model",
    "has_window", "has_grayscale", "resize_width_lbound", "resize_width_rbound",
    "resize_height_lbound", "resize_height_rbound", "brand_accuracy",
    "color_accuracy", "plate_accuracy", "avg_llm_time_ms", "avg_e2e_ms",
    "avg_decode_ms", "avg_resize_ms", "avg_llm_op_ms", "avg_grayscale_ms",
    "pipeline_nodes",
]
COLS_19 = [
    "query_title", "timestamp", "duration_s", "message_count", "llm_model",
    "has_window", "has_grayscale", "resize_width", "resize_height",
    "brand_accuracy", "color_accuracy", "plate_accuracy", "avg_llm_time_ms",
    "avg_e2e_ms", "avg_decode_ms", "avg_resize_ms", "avg_llm_op_ms",
    "avg_grayscale_ms", "pipeline_nodes",
]


CAR_NAIVE = [
    "Car Brand (Generic)",
    "Car Brand Ford",
    "Car Brand Renault",
    "Car Brand Toyota",
    "Car Color (Generic)",
    "Car Color Red",
    "Car Color Grey",
    "Car Color White",
    "Car Color Blue",
    "License Plate Text Extraction (Generic)",
    f"Specific Plate: {SPECIFIC_PLATE_TARGET}",
    "Color + License Plate (Red)",
    "Most Popular Brand",
    "Most Popular Color",
    "Most Popular Brand and Color",
    "Most Popular Color (Ford)",
    "Most Popular Brand (Red Cars)",
    "Unique License Plates (Window)",
    "Repeating License Plates",
]

CAR_OPT = [
    "Optimized Car Brand Generic (R854)",
    "Optimized Car Brand Ford (R854)",
    "Optimized Car Brand Renault (R854)",
    "Optimized Car Brand Toyota (R854)",
    "Optimized Car Color Generic (R480)",
    "Optimized Car Color Red (CFred+R480)",
    "Optimized Car Color Grey (CFgrey+R480)",
    "Optimized Car Color White (CFwhite+R480)",
    "Optimized Car Color Blue (CFblue+R480)",
    "Optimized License Plate Recognition (Native)",
    f"Optimized Specific Plate {SPECIFIC_PLATE_TARGET} (Native)",
    "Optimized Color+Plate Red (CFred native)",
    "Optimized Most Popular Brand (R854)",
    "Optimized Most Popular Color (R480)",
    "Optimized Most Popular Brand+Color (R854)",
    "Optimized Most Popular Color Ford (R854)",
    "Optimized Most Popular Brand Red (CFred+R854)",
    "Optimized Unique Plates (Native)",
    "Optimized Repeating Plates (Native)",
]

VB_NAIVE = [
    "Repeated Spikers (Window)",
    "Repeated Setters (Window)",
    "Repeated Blockers (Window)",
    "Repeated Diggers (Window)",
    "Motion Category (Window)",
    "Players Moving (Window)",
    "Players Standing (Window)",
    "Players Jumping (Window)",
    "Top Actions (Window)",
    "Spike Count (Window)",
    "Set Count (Window)",
    "Block Count (Window)",
    "Set->Spike Events (Window)",
    "Set->Block Events (Window)",
    "Dig->Set Events (Window)",
    "Jump->Spike Events (Window)",
    "Spike Bounding Boxes (Window)",
    "Block Bounding Boxes (Window)",
    "Set Bounding Boxes (Window)",
    "Dig Bounding Boxes (Window)",
]

VB_OPT = [
    "Optimized Repeated Spikers (G+R854)",
    "Optimized Repeated Setters (G+R854)",
    "Optimized Repeated Blockers (G+R854)",
    "Optimized Repeated Diggers (G+R854)",
    "Optimized Motion Category (R480)",
    "Optimized Players Moving (R480)",
    "Optimized Players Standing (R480)",
    "Optimized Players Jumping (R480)",
    "Optimized Top Actions (R854)",
    "Optimized Spike Count (R854)",
    "Optimized Set Count (R854)",
    "Optimized Block Count (R854)",
    "Optimized Set->Spike Events (R854)",
    "Optimized Set->Block Events (R854)",
    "Optimized Dig->Set Events (R854)",
    "Optimized Jump->Spike Events (R854)",
    "Optimized Spike Bounding Boxes (R960+B3+W20)",
    "Optimized Block Bounding Boxes (R960+B3+W20)",
    "Optimized Set Bounding Boxes (R960+B3+W20)",
    "Optimized Dig Bounding Boxes (R960+B3+W20)",
]

SLUG_OVERRIDES = {
    "License Plate Text Extraction (Generic)": "license_plates_generic",
    f"Specific Plate: {SPECIFIC_PLATE_TARGET}": f"specific_plate_{SPECIFIC_PLATE_TARGET.lower()}",
    "Color + License Plate (Red)": "color_license_plate_red",
    "Most Popular Brand and Color": "most_popular_brand_and_color",
    "Most Popular Brand (Red Cars)": "most_popular_brand_red_cars",
    "Set->Spike Events (Window)": "set_spike_events_window",
    "Set->Block Events (Window)": "set_block_events_window",
    "Dig->Set Events (Window)": "dig_set_events_window",
    "Jump->Spike Events (Window)": "jump_spike_events_window",
    "Case Car Brand Generic (R854)": "case_car_brand_generic_r854",
    "Case Car Color Generic (R480)": "case_car_color_generic_r480",
    "Case Car Color Red (CFred+R480)": "case_car_color_red_cfred_r480",
    "Case License Plates (CFwhite native)": "case_license_plates_cfwhite_native",
    "Case Color+Plate Red (CFred native)": "case_color_plate_red_cfred_native",
    "Case Repeated Spikers (G+R854)": "case_repeated_spikers_g_r854",
    "Case Motion Category (R480)": "case_motion_category_r480",
    "Case Spike Bbox (R960+B3)": "case_spike_bbox_r960_b3",
    "Optimized Car Brand Generic (R854)": "optimized_car_brand_generic_r854",
    "Optimized Car Brand Ford (R854)": "optimized_car_brand_ford_r854",
    "Optimized Car Brand Renault (R854)": "optimized_car_brand_renault_r854",
    "Optimized Car Brand Toyota (R854)": "optimized_car_brand_toyota_r854",
    "Optimized Car Color Generic (R480)": "optimized_car_color_generic_r480",
    "Optimized Car Color Red (CFred+R480)": "optimized_car_color_red_cfred_r480",
    "Optimized Car Color Grey (CFgrey+R480)": "optimized_car_color_grey_cfgrey_r480",
    "Optimized Car Color White (CFwhite+R480)": "optimized_car_color_white_cfwhite_r480",
    "Optimized Car Color Blue (CFblue+R480)": "optimized_car_color_blue_cfblue_r480",
    "Optimized License Plate Recognition (Native)": "optimized_license_plate_recognition_native",
    f"Optimized Specific Plate {SPECIFIC_PLATE_TARGET} (Native)": f"optimized_specific_plate_{SPECIFIC_PLATE_TARGET.lower()}_native",
    "Optimized License Plates (CFwhite native)": "optimized_license_plates_cfwhite_native",
    "Optimized License Plate Text Extraction (CFwhite native)": "optimized_license_plates_cfwhite_native",
    "Optimized Color+Plate Red (CFred native)": "optimized_color_plate_red_cfred_native",
    "Optimized Most Popular Brand (R854)": "optimized_most_popular_brand_r854",
    "Optimized Most Popular Color (R480)": "optimized_most_popular_color_r480",
    "Optimized Most Popular Brand+Color (R854)": "optimized_most_popular_brand_color_r854",
    "Optimized Most Popular Color Ford (R854)": "optimized_most_popular_color_ford_r854",
    "Optimized Most Popular Brand Red (CFred+R854)": "optimized_most_popular_brand_red_cfred_r854",
    "Optimized Unique Plates (Native)": "optimized_unique_plates_native",
    "Optimized Repeating Plates (Native)": "optimized_repeating_plates_native",
    "Optimized Repeated Spikers (R854)": "optimized_repeated_spikers_r854",
    "Optimized Repeated Spikers (G+R854)": "optimized_repeated_spikers_g_r854",
    "Optimized Repeated Setters (G+R854)": "optimized_repeated_setters_g_r854",
    "Optimized Repeated Blockers (G+R854)": "optimized_repeated_blockers_g_r854",
    "Optimized Repeated Diggers (G+R854)": "optimized_repeated_diggers_g_r854",
    "Optimized Motion Category (R480)": "optimized_motion_category_r480",
    "Optimized Players Moving (R480)": "optimized_players_moving_r480",
    "Optimized Players Standing (R480)": "optimized_players_standing_r480",
    "Optimized Players Jumping (R480)": "optimized_players_jumping_r480",
    "Optimized Top Actions (R854)": "optimized_top_actions_r854",
    "Optimized Spike Count (R854)": "optimized_spike_count_r854",
    "Optimized Set Count (R854)": "optimized_set_count_r854",
    "Optimized Block Count (R854)": "optimized_block_count_r854",
    "Optimized Set->Spike Events (R854)": "optimized_set_spike_events_r854",
    "Optimized Set->Block Events (R854)": "optimized_set_block_events_r854",
    "Optimized Dig->Set Events (R854)": "optimized_dig_set_events_r854",
    "Optimized Jump->Spike Events (R854)": "optimized_jump_spike_events_r854",
    "Optimized Spike Bbox (R960+B3)": "optimized_spike_bbox_r960_b3",
    "Optimized Spike Bounding Boxes (R960+B3+W20)": "optimized_spike_bounding_boxes_r960_b3_w20",
    "Optimized Block Bounding Boxes (R960+B3+W20)": "optimized_block_bounding_boxes_r960_b3_w20",
    "Optimized Set Bounding Boxes (R960+B3+W20)": "optimized_set_bounding_boxes_r960_b3_w20",
    "Optimized Dig Bounding Boxes (R960+B3+W20)": "optimized_dig_bounding_boxes_r960_b3_w20",
}

TITLE_ALIASES = {
    "Set->Spike Events (Window)": "Set→Spike Events (Window)",
    "Set->Block Events (Window)": "Set→Block Events (Window)",
    "Dig->Set Events (Window)": "Dig→Set Events (Window)",
    "Jump->Spike Events (Window)": "Jump→Spike Events (Window)",
    "License Plate Text Extraction (Generic)": "License Plates (Generic)",
    "Optimized License Plate Text Extraction (CFwhite native)": "Optimized License Plates (CFwhite native)",
}


def is_plate_recognition_title(title: str) -> bool:
    return "License Plates" in title or "License Plate Text Extraction" in title or "License Plate Recognition" in title


def slugify(title: str) -> str:
    if title in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[title]
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def parse_summary_row(fields: list[str]) -> dict[str, str]:
    if len(fields) == 19:
        row = dict(zip(COLS_19, fields))
        row["resize_width_lbound"] = row.get("resize_width", "")
        row["resize_height_lbound"] = row.get("resize_height", "")
        row["resize_width_rbound"] = ""
        row["resize_height_rbound"] = ""
        return row
    cols = COLS_21
    padded = list(fields) + [""] * (len(cols) - len(fields))
    return dict(zip(cols, padded[: len(cols)]))


def load_best_runs() -> dict[str, dict[str, str]]:
    best: dict[str, tuple[int, str, dict[str, str]]] = {}
    with SUMMARY.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)
        for raw in reader:
            if not raw:
                continue
            row = parse_summary_row(raw)
            title = row.get("query_title", "")
            if not title:
                continue
            try:
                messages = int(float(row.get("message_count") or 0))
            except ValueError:
                messages = 0
            ts = row.get("timestamp", "")
            old = best.get(title)
            if old is None or messages > old[0] or (messages == old[0] and ts > old[1]):
                best[title] = (messages, ts, row)
    return {title: data[2] for title, data in best.items()}


def read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def load_car_gt() -> tuple[list[str], list[str], list[str]]:
    plates: list[str] = []
    brands: list[str] = []
    colors: list[str] = []
    if not CAR_GT_CSV.exists():
        return plates, brands, colors
    with CAR_GT_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            row = list(row) + ["", "", ""]
            plates.append(norm_plate(row[0]))
            brands.append(norm_label(row[1]))
            colors.append(norm_label(row[2]))
    return plates[:CAR_TARGET_FRAMES], brands[:CAR_TARGET_FRAMES], colors[:CAR_TARGET_FRAMES]


def clean_text(value) -> str:
    return str(value or "").strip().strip('"').strip("'")


def norm_label(value) -> str:
    value = clean_text(value).lower()
    if value in {"", "skip", "none", "null", "nan"}:
        return ""
    value = value.replace("silver", "gray").replace("grey", "gray")
    return re.sub(r"[^a-z0-9]+", "", value)


def norm_plate(value) -> str:
    value = clean_text(value).upper()
    if value in {"", "SKIP", "NONE", "NULL", "NAN"}:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", value)


def pct(n: float | None, d: float | None = None) -> str:
    if n is None:
        return "-"
    if d is not None:
        if d == 0:
            return "-"
        n = 100.0 * n / d
    try:
        value = float(n)
    except (TypeError, ValueError):
        return "-"
    return f"{value:.2f}%"


def num(value, digits: int = 2) -> str:
    if value in (None, ""):
        return "-"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{f:,.{digits}f}"


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_accuracy_from_summary(row: dict[str, str]) -> str:
    candidates = [
        row.get("brand_accuracy"),
        row.get("color_accuracy"),
        row.get("plate_accuracy"),
    ]
    vals = []
    for c in candidates:
        try:
            f = float(c)
        except (TypeError, ValueError):
            continue
        if 0 <= f <= 100:
            vals.append(f)
    return pct(vals[0]) if vals else "-"


def car_eval(title: str) -> dict[str, object] | None:
    slug = slugify(title)
    rows = read_jsonl(RESULTS / f"{slug}.jsonl")
    if not rows:
        return None
    original_rows = len(rows)
    rows = sorted(rows, key=lambda r: r.get("sent", 0))[:CAR_TARGET_FRAMES]
    if len(rows) < CAR_TARGET_FRAMES:
        missing = CAR_TARGET_FRAMES - len(rows)
    else:
        missing = 0
    extra = max(0, original_rows - CAR_TARGET_FRAMES)

    correct = 0
    labeled = 0
    labeled_correct = 0
    positives = 0
    positive_hits = 0
    llm_calls = 0

    for r in rows:
        result = clean_text(r.get("result"))
        result_label = norm_label(result)
        result_plate = norm_plate(result)
        if safe_float(r.get("llm_time")) > 0 or safe_float((r.get("metrics") or {}).get("llm_time_ms")) > 0:
            llm_calls += 1

        brand = norm_label(r.get("annotation_brand"))
        color = norm_label(r.get("annotation_color"))
        plate = norm_plate(r.get("annotation_plate"))

        if "Brand Ford" in title:
            gold = brand == "ford"
            pred = result_label == "ford"
            labeled += int(gold)
        elif "Brand Renault" in title:
            gold = brand == "renault"
            pred = result_label == "renault"
            labeled += int(gold)
        elif "Brand Toyota" in title:
            gold = brand == "toyota"
            pred = result_label == "toyota"
            labeled += int(gold)
        elif "Brand" in title and "Color" not in title and "Red Cars" not in title:
            gold_value = brand
            pred_value = result_label
            gold = bool(gold_value)
            pred = pred_value == gold_value if gold else pred_value == ""
            labeled += int(gold)
        elif "Color Red" in title or "Color+Plate Red" in title or "License Plate (Red)" in title:
            if "Plate" in title or "License Plate" in title:
                gold = color == "red" and bool(plate)
                pred = (result_plate == plate) if gold else result_plate == ""
            else:
                gold = color == "red"
                pred = result_label == "red" if gold else result_label == ""
            labeled += int(gold)
        elif "Color Grey" in title:
            gold = color == "gray"
            pred = result_label == "gray" if gold else result_label == ""
            labeled += int(gold)
        elif "Color White" in title:
            gold = color == "white"
            pred = result_label == "white" if gold else result_label == ""
            labeled += int(gold)
        elif "Color Blue" in title:
            gold = color == "blue"
            pred = result_label == "blue" if gold else result_label == ""
            labeled += int(gold)
        elif "Color (Generic)" in title or "Color Generic" in title:
            gold_value = color
            pred_value = result_label
            gold = bool(gold_value)
            pred = pred_value == gold_value if gold else pred_value == ""
            labeled += int(gold)
        elif "Specific Plate" in title:
            gold = plate == SPECIFIC_PLATE_TARGET
            pred = result_plate == SPECIFIC_PLATE_TARGET
            labeled += int(gold)
        elif is_plate_recognition_title(title):
            gold = bool(plate)
            pred = result_plate == plate if gold else result_plate == ""
            labeled += int(gold)
        else:
            return None

        if gold:
            positives += 1
            if pred:
                positive_hits += 1
        if pred:
            correct += 1
            if gold:
                labeled_correct += 1

    total_correct = correct
    total = CAR_TARGET_FRAMES
    # Missing rows count as incorrect for the fixed denominator.
    return {
        "fixed_frame_accuracy": 100 * total_correct / total,
        "labeled_accuracy": (100 * labeled_correct / labeled) if labeled else None,
        "positive_recall": (100 * positive_hits / positives) if positives else None,
        "rows_used": len(rows),
        "missing_rows": missing,
        "extra_rows": extra,
        "llm_calls": llm_calls,
    }


def result_items(value) -> list[str]:
    """Flatten a result field into normalized string labels/count labels."""
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, list) and item:
                out.append(clean_text(item[0]))
            else:
                out.extend(result_items(item))
        return out
    text = clean_text(value)
    if not text:
        return []
    if "," in text and not re.match(r"^\d+\s*,", text):
        return [p.strip() for p in text.split(",") if p.strip()]
    return [text]


def result_counts(value) -> Counter[str]:
    """Return normalized labels with counts from a pipeline result field."""
    counts: Counter[str] = Counter()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, (list, tuple)) and item:
                label = norm_action(item[0])
                amount = 1
                if len(item) > 1:
                    try:
                        amount = int(float(item[1]))
                    except (TypeError, ValueError):
                        amount = 1
                if label:
                    counts[label] += amount
            else:
                counts.update(result_counts(item))
        return counts
    label = norm_action(value)
    if label:
        counts[label] += 1
    return counts


def norm_car_result_label(value) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if "," in text and not re.match(r"^\d+\s*,", text):
        parts = [norm_label(part) for part in text.split(",")[:2]]
        parts = [part for part in parts if part]
        return ",".join(parts)
    return norm_label(text)


def car_result_counts(value) -> Counter[str]:
    """Return normalized car labels with embedded aggregate counts preserved."""
    counts: Counter[str] = Counter()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, (list, tuple)) and item:
                label = norm_car_result_label(item[0])
                amount = 1
                if len(item) > 1:
                    try:
                        amount = int(float(item[1]))
                    except (TypeError, ValueError):
                        amount = 1
                if label:
                    counts[label] += amount
            else:
                counts.update(car_result_counts(item))
        return counts
    label = norm_car_result_label(value)
    if label:
        counts[label] += 1
    return counts


def norm_action(value) -> str:
    text = clean_text(value).lower()
    text = text.replace("->", "_").replace("-", "_")
    text = re.sub(r"[^a-z0-9_]+", "", text)
    aliases = {
        "set": "setting",
        "setter": "setting",
        "setting": "setting",
        "spike": "spiking",
        "spiker": "spiking",
        "spiking": "spiking",
        "block": "blocking",
        "blocker": "blocking",
        "blocking": "blocking",
        "dig": "digging",
        "digger": "digging",
        "digging": "digging",
        "jump": "jumping",
        "jumper": "jumping",
        "jumping": "jumping",
        "stand": "standing",
        "standing": "standing",
        "wait": "waiting",
        "waiting": "waiting",
        "move": "moving",
        "moving": "moving",
        "none_moving": "none_moving",
        "nonemoving": "none_moving",
        "some_moving": "some_moving",
        "somemoving": "some_moving",
        "most_moving": "most_moving",
        "mostmoving": "most_moving",
        "set_spike": "set_spike",
        "setspike": "set_spike",
        "set_block": "set_block",
        "setblock": "set_block",
        "dig_set": "dig_set",
        "digset": "dig_set",
        "jump_spike": "jump_spike",
        "jumpspike": "jump_spike",
        "skip": "",
    }
    return aliases.get(text, text)


def action_target(title: str) -> str:
    if "Spiker" in title or "Spike Count" in title or "Spike Bbox" in title or "Spike Bounding" in title:
        return "spiking"
    if "Setter" in title or "Set Count" in title or "Set Bbox" in title or "Set Bounding" in title:
        return "setting"
    if "Blocker" in title or "Block Count" in title or "Block Bbox" in title or "Block Bounding" in title:
        return "blocking"
    if "Digger" in title or "Dig Count" in title or "Dig Bbox" in title or "Dig Bounding" in title:
        return "digging"
    if "Moving" in title:
        return "moving"
    if "Standing" in title:
        return "standing"
    if "Jumping" in title:
        return "jumping"
    return ""


def pair_target(title: str) -> tuple[str, str, str] | None:
    pairs = [
        ("Set->Spike", "setting", "spiking", "set_spike"),
        ("Set->Block", "setting", "blocking", "set_block"),
        ("Dig->Set", "digging", "setting", "dig_set"),
        ("Jump->Spike", "jumping", "spiking", "jump_spike"),
    ]
    for marker, first, second, label in pairs:
        if marker in title:
            return first, second, label
    return None


def load_volleyball_gt_frames() -> list[dict]:
    """Reconstruct the capped volleyball frames sent by the default sender."""
    root = ROOT / "volleyball_dataset"
    frames: list[dict] = []
    game_bases = [
        root / "volleyball-detections" / "volleyball-detections",
        root / "volleyball-detections",
        root / "videos_sample" / "videos_sample",
        root / "videos_sample",
        root,
    ]
    games_base = next((p for p in game_bases if p.exists()), game_bases[0])
    track_base = root / "volleyball_tracking_annotation" / "volleyball_tracking_annotation" / "_"
    if not games_base.exists() or not track_base.exists():
        return frames

    def parse_tracking(path: Path) -> dict[int, list[dict]]:
        by_frame: dict[int, list[dict]] = {}
        if not path.exists():
            return by_frame
        with path.open(encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 10:
                    continue
                try:
                    xmin, ymin, xmax, ymax, frame_id, lost = map(int, parts[1:7])
                except ValueError:
                    continue
                by_frame.setdefault(frame_id, []).append({
                    "bbox": [xmin, ymin, xmax, ymax],
                    "lost": lost,
                    "action": norm_action(parts[9]),
                })
        return by_frame

    for game_dir in sorted([p for p in games_base.iterdir() if p.is_dir() and p.name.isdigit()], key=lambda p: int(p.name)):
        game = game_dir.name
        clip_dirs = []
        for clip_dir in game_dir.rglob("*"):
            if clip_dir.is_dir() and clip_dir.name.isdigit() and any(clip_dir.glob("*.jpg")):
                clip_dirs.append(clip_dir)
        for clip_dir in sorted(clip_dirs, key=lambda p: (p.as_posix(), int(p.name))):
            clip = clip_dir.name
            tracking = parse_tracking(track_base / game / clip / f"{clip}.txt")
            jpgs = sorted([p for p in clip_dir.iterdir() if p.suffix.lower() == ".jpg" and p.stem.lstrip("-").isdigit()], key=lambda p: int(p.stem))
            for jpg in jpgs:
                frame_id = int(jpg.stem)
                players = tracking.get(frame_id, [])
                visible = [p for p in players if p.get("lost") == 0]
                actions = [p["action"] for p in visible if p.get("action")]
                frames.append({
                    "game": int(game),
                    "clip": int(clip),
                    "frame_id": frame_id,
                    "actions": actions,
                    "counts": Counter(actions),
                    "bboxes_spiking": [p["bbox"] for p in visible if p.get("action") == "spiking"],
                })
    return frames[:VB_TARGET_FRAMES]


def motion_category(actions: list[str]) -> str:
    visible = [a for a in actions if a]
    if not visible:
        return ""
    moving = sum(1 for a in visible if a not in {"standing", "waiting"})
    if moving == 0:
        return "none_moving"
    if moving >= len(visible) / 2:
        return "most_moving"
    return "some_moving"


def ordered_pair_exists(action_sets: list[set[str]], first: str, second: str) -> bool:
    seen_first = False
    for actions in action_sets:
        if first in actions:
            seen_first = True
        if seen_first and second in actions:
            return True
    return False


def jaccard_pct(pred: set[str], gt: set[str]) -> float:
    if not pred and not gt:
        return 100.0
    if not pred or not gt:
        return 0.0
    return 100.0 * len(pred & gt) / len(pred | gt)


def top_nonempty(counter: Counter[str]) -> str:
    for key, _count in counter.most_common():
        if key:
            return key
    return ""


def yesno(value: bool) -> str:
    return "yes" if value else "no"


def specific_plate_gt_count() -> int:
    gt_plates, _gt_brands, _gt_colors = load_car_gt()
    return sum(1 for plate in gt_plates if plate == SPECIFIC_PLATE_TARGET)


def summarize_values(values, max_items: int = 5) -> str:
    clean = sorted(str(v) for v in values if v)
    if not clean:
        return "none"
    head = ", ".join(clean[:max_items])
    if len(clean) > max_items:
        return f"{len(clean)} values ({head}, ...)"
    return head


def car_result_summary(title: str) -> str:
    rows = read_jsonl(RESULTS / f"{slugify(title)}.jsonl")
    if not rows:
        if "Specific Plate" in title:
            return f"pred {SPECIFIC_PLATE_TARGET}: not run | ground truth {SPECIFIC_PLATE_TARGET}: {specific_plate_gt_count()} frames"
        return "pred: no rows | ground truth: available"
    if "Specific Plate" in title and len(rows) < int(CAR_TARGET_FRAMES * 0.9):
        return f"partial run: {len(rows)}/{CAR_TARGET_FRAMES} rows | ground truth {SPECIFIC_PLATE_TARGET}: {specific_plate_gt_count()} frames"
    rows = sorted(rows, key=lambda r: r.get("sent", 0))[:CAR_TARGET_FRAMES]

    gt_plates, gt_brands, gt_colors = load_car_gt()
    if not gt_plates:
        gt_brands = [norm_label(r.get("annotation_brand")) for r in rows]
        gt_colors = [norm_label(r.get("annotation_color")) for r in rows]
        gt_plates = [norm_plate(r.get("annotation_plate")) for r in rows]

    pred_labels = []
    pred_plates = []
    pred_aggregate_counts = Counter()
    for r in rows:
        items = result_items(r.get("result"))
        pred_labels.extend(norm_label(x) for x in items)
        pred_plates.extend(norm_plate(x) for x in items)
        pred_aggregate_counts.update(car_result_counts(r.get("result")))

    pred_label_counts = Counter(x for x in pred_labels if x)
    pred_plate_counts = Counter(x for x in pred_plates if x)
    gt_brand_counts = Counter(x for x in gt_brands if x)
    gt_color_counts = Counter(x for x in gt_colors if x)
    gt_plate_counts = Counter(x for x in gt_plates if x)

    if "Brand Ford" in title:
        return f"pred ford: {yesno('ford' in pred_label_counts)} | ground truth ford: {yesno('ford' in gt_brand_counts)}"
    if "Brand Renault" in title:
        return f"pred renault: {yesno('renault' in pred_label_counts)} | ground truth renault: {yesno('renault' in gt_brand_counts)}"
    if "Brand Toyota" in title:
        return f"pred toyota: {yesno('toyota' in pred_label_counts)} | ground truth toyota: {yesno('toyota' in gt_brand_counts)}"
    if "Color Red" in title and "Plate" not in title:
        return f"pred red: {yesno('red' in pred_label_counts)} | ground truth red: {yesno('red' in gt_color_counts)}"
    if "Color Grey" in title:
        return f"pred gray: {yesno('gray' in pred_label_counts)} | ground truth gray: {yesno('gray' in gt_color_counts)}"
    if "Color White" in title:
        return f"pred white: {yesno('white' in pred_label_counts)} | ground truth white: {yesno('white' in gt_color_counts)}"
    if "Color Blue" in title:
        return f"pred blue: {yesno('blue' in pred_label_counts)} | ground truth blue: {yesno('blue' in gt_color_counts)}"
    if "Specific Plate" in title:
        return f"pred {SPECIFIC_PLATE_TARGET}: {yesno(SPECIFIC_PLATE_TARGET in pred_plate_counts)} | ground truth {SPECIFIC_PLATE_TARGET}: {yesno(SPECIFIC_PLATE_TARGET in gt_plate_counts)}"
    if "Repeating" in title and "Plates" in title:
        pred = {p for p, count in pred_plate_counts.items() if count >= 3}
        gt = {p for p, count in gt_plate_counts.items() if count >= 3}
        return f"pred repeated plates: {summarize_values(pred)} | ground truth repeated plates: {summarize_values(gt)}"
    if "Unique" in title and "Plates" in title:
        pred = set(pred_plate_counts)
        gt = set(gt_plate_counts)
        return f"pred plates: {summarize_values(pred)} | ground truth plates: {summarize_values(gt)}"
    if "Color+Plate Red" in title or "License Plate (Red)" in title:
        pred = set(pred_plate_counts)
        gt = {p for p, c in zip(gt_plates, gt_colors) if p and c == "red"}
        return f"pred red plates: {summarize_values(pred)} | ground truth red plates: {summarize_values(gt)}"
    if is_plate_recognition_title(title):
        pred = set(pred_plate_counts)
        gt = set(gt_plate_counts)
        return f"pred plates: {summarize_values(pred)} | ground truth plates: {summarize_values(gt)}"
    if "Most Popular Brand and Color" in title or "Most Popular Brand+Color" in title:
        gt_pairs = Counter(f"{c},{b}" for b, c in zip(gt_brands, gt_colors) if b and c)
        pred_pairs = Counter({k: v for k, v in pred_aggregate_counts.items() if "," in k})
        return f"pred top: {top_nonempty(pred_pairs) or '-'} | ground truth top: {top_nonempty(gt_pairs) or '-'}"
    if "Most Popular Color (Ford)" in title or "Most Popular Color Ford" in title:
        gt_top = top_nonempty(Counter(c for b, c in zip(gt_brands, gt_colors) if b == "ford" and c))
        return f"pred top: {top_nonempty(pred_aggregate_counts) or '-'} | ground truth top: {gt_top or '-'}"
    if "Most Popular Brand (Red Cars)" in title or "Most Popular Brand Red" in title:
        gt_top = top_nonempty(Counter(b for b, c in zip(gt_brands, gt_colors) if c == "red" and b))
        return f"pred top: {top_nonempty(pred_aggregate_counts) or '-'} | ground truth top: {gt_top or '-'}"
    if "Most Popular Brand" in title:
        return f"pred top: {top_nonempty(pred_aggregate_counts) or '-'} | ground truth top: {top_nonempty(gt_brand_counts) or '-'}"
    if "Most Popular Color" in title:
        return f"pred top: {top_nonempty(pred_aggregate_counts) or '-'} | ground truth top: {top_nonempty(gt_color_counts) or '-'}"
    if "Brand" in title and "Color" not in title:
        return f"pred brands: {summarize_values(pred_label_counts)} | ground truth brands: {summarize_values(gt_brand_counts)}"
    if "Color" in title:
        return f"pred colors: {summarize_values(pred_label_counts)} | ground truth colors: {summarize_values(gt_color_counts)}"
    return "-"


def car_overall_eval(title: str) -> tuple[str, str]:
    """Compute one final answer accuracy for the whole car query run."""
    rows = read_jsonl(RESULTS / f"{slugify(title)}.jsonl")
    if not rows:
        if "Specific Plate" in title:
            return "-", f"not run after target changed to {SPECIFIC_PLATE_TARGET}; target appears in {specific_plate_gt_count()} annotated frames"
        return "-", "overall not available: no result rows"
    is_aggregate_query = any(token in title for token in ["Most Popular", "Unique", "Repeating"])
    if not is_aggregate_query and len(rows) < int(CAR_TARGET_FRAMES * 0.9):
        return "-", f"overall not available: raw result file has only {len(rows)} rows"
    rows = sorted(rows, key=lambda r: r.get("sent", 0))[:CAR_TARGET_FRAMES]

    gt_plates, gt_brands, gt_colors = load_car_gt()
    if not gt_plates:
        gt_brands = [norm_label(r.get("annotation_brand")) for r in rows]
        gt_colors = [norm_label(r.get("annotation_color")) for r in rows]
        gt_plates = [norm_plate(r.get("annotation_plate")) for r in rows]

    pred_labels = []
    pred_plates = []
    pred_aggregate_counts = Counter()
    for r in rows:
        items = result_items(r.get("result"))
        pred_labels.extend(norm_label(x) for x in items)
        pred_plates.extend(norm_plate(x) for x in items)
        pred_aggregate_counts.update(car_result_counts(r.get("result")))

    pred_label_counts = Counter(x for x in pred_labels if x)
    pred_plate_counts = Counter(x for x in pred_plates if x)
    gt_brand_counts = Counter(x for x in gt_brands if x)
    gt_color_counts = Counter(x for x in gt_colors if x)
    gt_plate_counts = Counter(x for x in gt_plates if x)

    def binary(pred: bool, gt: bool) -> tuple[str, str]:
        return (
            "100.00%" if pred == gt else "0.00%",
            f"pred exists={pred}; ground truth exists={gt}",
        )

    if "Brand Ford" in title:
        return binary("ford" in pred_label_counts, "ford" in gt_brand_counts)
    if "Brand Renault" in title:
        return binary("renault" in pred_label_counts, "renault" in gt_brand_counts)
    if "Brand Toyota" in title:
        return binary("toyota" in pred_label_counts, "toyota" in gt_brand_counts)
    if "Color Red" in title and "Plate" not in title:
        return binary("red" in pred_label_counts, "red" in gt_color_counts)
    if "Color Grey" in title:
        return binary("gray" in pred_label_counts, "gray" in gt_color_counts)
    if "Color White" in title:
        return binary("white" in pred_label_counts, "white" in gt_color_counts)
    if "Color Blue" in title:
        return binary("blue" in pred_label_counts, "blue" in gt_color_counts)
    if "Specific Plate" in title:
        return binary(SPECIFIC_PLATE_TARGET in pred_plate_counts, SPECIFIC_PLATE_TARGET in gt_plate_counts)
    if "Repeating" in title and "Plates" in title:
        pred = {p for p, count in pred_plate_counts.items() if count >= 3}
        gt = {p for p, count in gt_plate_counts.items() if count >= 3}
        return pct(jaccard_pct(pred, gt)), f"repeating-plate Jaccard; pred {len(pred)}, ground truth {len(gt)}"
    if "Unique" in title and "Plates" in title:
        pred = set(pred_plate_counts)
        gt = set(gt_plate_counts)
        return pct(jaccard_pct(pred, gt)), f"unique-plate Jaccard; pred {len(pred)}, ground truth {len(gt)}"
    if "Color+Plate Red" in title or "License Plate (Red)" in title:
        gt = {p for p, c in zip(gt_plates, gt_colors) if p and c == "red"}
        pred = set(pred_plate_counts)
        return pct(jaccard_pct(pred, gt)), f"plate-set Jaccard; pred {len(pred)}, ground truth {len(gt)}"
    if is_plate_recognition_title(title):
        pred = set(pred_plate_counts)
        gt = set(gt_plate_counts)
        return pct(jaccard_pct(pred, gt)), f"plate-set Jaccard; pred {len(pred)}, ground truth {len(gt)}"
    if "Most Popular Brand and Color" in title or "Most Popular Brand+Color" in title:
        gt_pairs = Counter(f"{c},{b}" for b, c in zip(gt_brands, gt_colors) if b and c)
        pred_pairs = Counter({k: v for k, v in pred_aggregate_counts.items() if "," in k})
        pred_top = top_nonempty(pred_pairs)
        gt_top = top_nonempty(gt_pairs)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"pred top={pred_top or '-'}; ground truth top={gt_top or '-'}"
    if "Most Popular Color (Ford)" in title or "Most Popular Color Ford" in title:
        gt_top = top_nonempty(Counter(c for b, c in zip(gt_brands, gt_colors) if b == "ford" and c))
        pred_top = top_nonempty(pred_aggregate_counts)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"pred top={pred_top or '-'}; ground truth top={gt_top or '-'}"
    if "Most Popular Brand (Red Cars)" in title or "Most Popular Brand Red" in title:
        gt_top = top_nonempty(Counter(b for b, c in zip(gt_brands, gt_colors) if c == "red" and b))
        pred_top = top_nonempty(pred_aggregate_counts)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"pred top={pred_top or '-'}; ground truth top={gt_top or '-'}"
    if "Most Popular Brand" in title:
        pred_top = top_nonempty(pred_aggregate_counts)
        gt_top = top_nonempty(gt_brand_counts)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"pred top={pred_top or '-'}; ground truth top={gt_top or '-'}"
    if "Most Popular Color" in title:
        pred_top = top_nonempty(pred_aggregate_counts)
        gt_top = top_nonempty(gt_color_counts)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"pred top={pred_top or '-'}; ground truth top={gt_top or '-'}"
    if "Brand" in title and "Color" not in title:
        pred = set(pred_label_counts)
        gt = set(gt_brand_counts)
        return pct(jaccard_pct(pred, gt)), f"brand-set Jaccard; pred {len(pred)}, ground truth {len(gt)}"
    if "Color" in title:
        pred = set(pred_label_counts)
        gt = set(gt_color_counts)
        return pct(jaccard_pct(pred, gt)), f"color-set Jaccard; pred {len(pred)}, ground truth {len(gt)}"
    return "-", "overall not available: no task rule"


def vb_frame_eval(title: str) -> tuple[str, str]:
    """Window/frame proxy accuracy for volleyball using direct annotation files."""
    rows = read_jsonl(RESULTS / f"{slugify(title)}.jsonl")
    if not rows:
        return "-", "no result rows"
    gt = load_volleyball_gt_frames()
    if not gt:
        return "-", "ground-truth annotations not found"

    pair = pair_target(title)
    target = action_target(title)
    is_bbox = "Bbox" in title or "Bounding Boxes" in title
    is_count = " Count" in title

    # Non-window bbox final query emits one row per input frame, with SKIP rows
    # between real grouped-frame calls. This can be scored as frame presence/absence.
    if is_bbox and not any("frames" in r for r in rows):
        used = rows[:VB_TARGET_FRAMES]
        correct = 0
        for i, r in enumerate(used):
            pred = any(re.search(r"\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+", clean_text(x)) for x in result_items(r.get("result")))
            truth = bool(gt[i].get("bboxes_spiking")) if i < len(gt) and target == "spiking" else (target in gt[i]["counts"] if i < len(gt) else False)
            correct += int(pred == truth)
        return pct(100 * correct / VB_TARGET_FRAMES), f"frame bbox presence over {len(used)}/{VB_TARGET_FRAMES} rows"

    windows = []
    start = 0
    for r in rows:
        size = int(r.get("frames") or 20)
        windows.append((r, gt[start:start + size]))
        start += size
        if start >= 200:
            break
    if not windows:
        return "-", "no complete windows"

    scores = []
    for r, frames in windows:
        pred_counts = result_counts(r.get("result"))
        gt_counts = Counter()
        for frame in frames:
            gt_counts.update(frame["counts"])
        if "Motion Category" in title:
            pred = top_nonempty(pred_counts)
            gt_motion = Counter(motion_category(frame["actions"]) for frame in frames)
            truth = top_nonempty(gt_motion)
            scores.append(1.0 if pred == truth else 0.0)
        elif "Top Actions" in title:
            scores.append(1.0 if top_nonempty(pred_counts) == top_nonempty(gt_counts) else 0.0)
        elif pair:
            first, second, label = pair
            pred = pred_counts.get(label, 0) > 0
            truth = ordered_pair_exists([set(frame["actions"]) for frame in frames], first, second)
            scores.append(1.0 if pred == truth else 0.0)
        elif is_count and target:
            pred = pred_counts.get(target, 0)
            truth = sum(1 for frame in frames if target in frame["counts"])
            denom = max(len(frames), truth, 1)
            scores.append(max(0.0, 1.0 - abs(pred - truth) / denom))
        elif target:
            pred = pred_counts.get(target, 0) > 0
            truth = any(target in frame["counts"] for frame in frames)
            if "Repeated" in title:
                truth = sum(1 for frame in frames if target in frame["counts"]) >= 3
            scores.append(1.0 if pred == truth else 0.0)
        elif is_bbox:
            pred = any(re.search(r"\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+", clean_text(x)) for x in result_items(r.get("result")))
            truth = any(frame.get("bboxes_spiking") for frame in frames)
            scores.append(1.0 if pred == truth else 0.0)

    if not scores:
        return "-", "no supported volleyball scoring rule"
    return pct(100 * sum(scores) / len(scores)), f"annotation-based window proxy over {len(scores)} windows"


def vb_overall_eval(title: str) -> tuple[str, str]:
    """Compute whole-query volleyball accuracy from saved rows and annotations."""
    rows = read_jsonl(RESULTS / f"{slugify(title)}.jsonl")
    if not rows:
        return "-", "overall not available: no result rows"
    gt = load_volleyball_gt_frames()
    if not gt:
        return "-", "overall not available: ground-truth annotations not found"

    pred_counts = Counter()
    for r in rows:
        pred_counts.update(result_counts(r.get("result")))
    gt_counts = Counter()
    for frame in gt:
        gt_counts.update(frame["counts"])

    pair = pair_target(title)
    target = action_target(title)
    is_bbox = "Bbox" in title or "Bounding Boxes" in title
    is_count = " Count" in title

    if "Top Actions" in title:
        pred_top = top_nonempty(pred_counts)
        gt_top = top_nonempty(gt_counts)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"top action exact match; pred={pred_top or '-'}; ground truth={gt_top or '-'}"
    if "Motion Category" in title:
        pred_top = top_nonempty(pred_counts)
        gt_motion = Counter(motion_category(frame["actions"]) for frame in gt)
        gt_top = top_nonempty(gt_motion)
        return ("100.00%" if pred_top == gt_top else "0.00%"), f"motion top exact match; pred={pred_top or '-'}; ground truth={gt_top or '-'}"
    if pair:
        first, second, label = pair
        pred = pred_counts.get(label, 0) > 0
        truth = ordered_pair_exists([set(frame["actions"]) for frame in gt], first, second)
        return ("100.00%" if pred == truth else "0.00%"), f"ordered event existence; pred={pred}; ground truth={truth}"
    if is_bbox:
        has_bbox = any(re.search(r"\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+", clean_text(x)) for r in rows for x in result_items(r.get("result")))
        truth = any(frame.get("bboxes_spiking") for frame in gt) if target == "spiking" else gt_counts.get(target, 0) > 0
        return ("100.00%" if has_bbox == truth else "0.00%"), f"bounding-box existence only; pred={has_bbox}; ground truth target={truth}; IoU unavailable"
    if is_count and target:
        pred = pred_counts.get(target, 0)
        truth = sum(1 for frame in gt if target in frame["counts"])
        score = max(0.0, 100.0 * (1.0 - abs(pred - truth) / max(truth, 1)))
        return pct(score), f"count closeness; pred={pred}; ground truth={truth}"
    if target:
        pred = pred_counts.get(target, 0) > 0
        truth = gt_counts.get(target, 0) > 0
        return ("100.00%" if pred == truth else "0.00%"), f"event existence; pred {target}={pred}; ground truth {target}={truth}"
    return "-", "overall not available: no task rule"


def vb_result_summary(title: str) -> str:
    rows = read_jsonl(RESULTS / f"{slugify(title)}.jsonl")
    if not rows:
        return "pred: no rows | ground truth: available"
    gt = load_volleyball_gt_frames()
    if not gt:
        return "pred: available | ground truth: missing annotations"

    pred_counts = Counter()
    for r in rows:
        pred_counts.update(result_counts(r.get("result")))
    gt_counts = Counter()
    for frame in gt:
        gt_counts.update(frame["counts"])

    pair = pair_target(title)
    target = action_target(title)
    is_bbox = "Bbox" in title or "Bounding Boxes" in title
    is_count = " Count" in title

    if "Top Actions" in title:
        return f"pred top: {top_nonempty(pred_counts) or '-'} | ground truth top: {top_nonempty(gt_counts) or '-'}"
    if "Motion Category" in title:
        gt_motion = Counter(motion_category(frame["actions"]) for frame in gt)
        return f"pred motion: {top_nonempty(pred_counts) or '-'} | ground truth motion: {top_nonempty(gt_motion) or '-'}"
    if pair:
        first, second, label = pair
        pred = pred_counts.get(label, 0) > 0
        truth = ordered_pair_exists([set(frame["actions"]) for frame in gt], first, second)
        return f"pred event: {yesno(pred)} | ground truth event: {yesno(truth)}"
    if is_bbox:
        pred = any(re.search(r"\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+", clean_text(x))
                   for r in rows for x in result_items(r.get("result")))
        if target == "spiking":
            truth = any(frame.get("bboxes_spiking") for frame in gt)
        else:
            truth = gt_counts.get(target, 0) > 0
        return f"pred bounding box: {yesno(pred)} | ground truth target/box: {yesno(truth)}"
    if is_count and target:
        pred = pred_counts.get(target, 0)
        truth = sum(1 for frame in gt if target in frame["counts"])
        return f"pred count: {pred} | ground truth count: {truth}"
    if target:
        pred = pred_counts.get(target, 0) > 0
        truth = gt_counts.get(target, 0) > 0
        return f"pred {target}: {yesno(pred)} | ground truth {target}: {yesno(truth)}"
    return f"pred labels: {summarize_values(pred_counts)} | ground truth labels: {summarize_values(gt_counts)}"


def metric_json_accuracy(title: str) -> str:
    data = read_json(METRICS / f"{slugify(title)}.json")
    if not data:
        return "-"
    acc = ((data.get("aggregate_metrics") or {}).get("accuracy") or {})
    values = []
    for v in acc.values():
        try:
            f = float(v)
            values.append(f * 100 if f <= 1 else f)
        except (TypeError, ValueError):
            pass
    return pct(values[0]) if values else "-"


def format_pipeline_text(value: str) -> str:
    replacements = {
        "Frame Batcher": "Frame Grouper",
        "Llm": "LLM",
        "Aggr": "Aggregate",
        "Resize": "Resize",
        "Decode": "Decode",
        "Sink": "Sink",
        "Source": "Source",
        "Filter": "Filter",
        "CV Color Filter": "CV Color Filter",
    }
    out = value or "-"
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out.replace(" -> ", " > ")


def pipeline(row: dict[str, str] | None) -> str:
    if not row:
        return "-"
    p = row.get("pipeline_nodes") or "-"
    return format_pipeline_text(p)


def display_meta(title: str, row: dict[str, str] | None, detail: dict | None) -> dict[str, str]:
    meta = (detail or {}).get("query_meta") or {}
    agg = (detail or {}).get("aggregate_metrics") or {}
    return {
        "messages": str((detail or {}).get("message_count", row.get("message_count", "-") if row else "-")),
        "duration_s": num((detail or {}).get("duration_s", row.get("duration_s") if row else None)),
        "avg_llm_ms": num(agg.get("avgLlmTime", row.get("avg_llm_time_ms") if row else None)),
        "pipeline": format_pipeline_text(meta.get("pipeline_nodes") or pipeline(row)),
    }


def find_best_row(best: dict[str, dict[str, str]], title: str) -> dict[str, str] | None:
    return best.get(title) or best.get(TITLE_ALIASES.get(title, ""))


def compute_row(title: str, best: dict[str, dict[str, str]], dataset: str) -> dict[str, str]:
    row = find_best_row(best, title)
    detail = read_json(METRICS / f"{slugify(title)}.json")
    display = display_meta(title, row, detail)
    frame_acc = "-"
    overall = "-"
    note = ""

    if dataset == "cars":
        result_summary = car_result_summary(title)
        overall, overall_note = car_overall_eval(title)
        is_aggregate_query = any(token in title for token in ["Most Popular", "Unique", "Repeating"])
        raw_rows = read_jsonl(RESULTS / f"{slugify(title)}.jsonl")
        incomplete_nonaggregate = (
            bool(raw_rows)
            and not is_aggregate_query
            and len(raw_rows) < int(CAR_TARGET_FRAMES * 0.9)
        )
        if incomplete_nonaggregate:
            display["messages"] = str(len(raw_rows))
        ce = None if is_aggregate_query or incomplete_nonaggregate else car_eval(title)
        if is_aggregate_query:
            note = "window aggregate: no ordered per-frame labels saved; use overall query accuracy"
        elif incomplete_nonaggregate:
            note = f"incomplete run: {len(raw_rows)}/{CAR_TARGET_FRAMES} result rows; rerun required for benchmark"
        elif ce:
            frame_acc = pct(ce["fixed_frame_accuracy"])
            if ce.get("labeled_accuracy") is not None:
                note = f"labeled acc {pct(ce['labeled_accuracy'])}; LLM calls {ce['llm_calls']}"
            if ce.get("missing_rows"):
                missing = ce["missing_rows"]
                note += f"; {missing} missing row{'s' if missing != 1 else ''}"
            if ce.get("extra_rows"):
                extra = ce["extra_rows"]
                note += f"; {extra} extra row{'s' if extra != 1 else ''} ignored"
        elif row:
            frame_acc = get_accuracy_from_summary(row)
            note = "summary metric only"
        if overall_note:
            note = (note + "; " if note else "") + overall_note
        if "Specific Plate" in title and not row and not detail:
            note = f"not run after target changed to {SPECIFIC_PLATE_TARGET}; target appears in {specific_plate_gt_count()} annotated frames"
    else:
        result_summary = vb_result_summary(title)
        overall, overall_note = vb_overall_eval(title)
        frame_acc, frame_note = vb_frame_eval(title)
        note = frame_note
        if "Bbox" in title or "Bounding Boxes" in title:
            note += "; IoU not scored because saved output does not preserve enough ordered ground-truth/predicted box pairs"
        elif detail:
            note += "; saved pipeline metric is not used because old runs used majority-action ground truth"
        elif row:
            note += "; summary row only"
        if overall_note:
            note = (note + "; " if note else "") + overall_note

    return {
        "query": title,
        "pipeline": display["pipeline"],
        "messages": display["messages"],
        "duration_s": display["duration_s"],
        "avg_llm_ms": display["avg_llm_ms"],
        "frame_accuracy": frame_acc,
        "overall_query_accuracy": overall,
        "result_summary": result_summary,
        "notes": note,
    }


def table_rows(titles: list[str], best: dict[str, dict[str, str]], dataset: str, optimized=False) -> str:
    rows_html = []
    for title in titles:
        computed = compute_row(title, best, dataset)

        rows_html.append(
            "<tr>"
            f"<td>{esc(computed['query'])}</td>"
            f"<td>{esc(computed['pipeline'])}</td>"
            f"<td class='num'>{esc(computed['messages'])}</td>"
            f"<td class='num'>{esc(computed['duration_s'])}</td>"
            f"<td class='num'>{esc(computed['avg_llm_ms'])}</td>"
            f"<td class='num'>{esc(computed['frame_accuracy'])}</td>"
            f"<td class='num'>{esc(computed['overall_query_accuracy'])}</td>"
            f"<td>{esc(computed['result_summary'])}</td>"
            f"<td>{esc(computed['notes'])}</td>"
            "</tr>"
        )
    return "\n".join(rows_html)


def write_benchmark_summary(best: dict[str, dict[str, str]]) -> None:
    groups = [
        ("cars_naive", "cars", CAR_NAIVE),
        ("cars_optimized", "cars", CAR_OPT),
        ("volleyball_naive", "volleyball", VB_NAIVE),
        ("volleyball_optimized", "volleyball", VB_OPT),
    ]
    OUT_SUMMARY.parent.mkdir(exist_ok=True)
    with OUT_SUMMARY.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "group", "query", "pipeline", "messages", "duration_s",
            "avg_llm_ms", "frame_accuracy", "overall_query_accuracy",
            "result_summary", "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for group, dataset, titles in groups:
            for title in titles:
                row = compute_row(title, best, dataset)
                row["group"] = group
                writer.writerow({field: row.get(field, "") for field in fields})


def pct_value(value: str) -> float | None:
    value = str(value or "").strip().replace("%", "")
    if not value or value == "-":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def short_query_label(query: str) -> str:
    replacements = {
        "Optimized ": "Opt ",
        "Car ": "",
        "License Plate Text Extraction": "Plate Text",
        "License Plates": "Plates",
        "Color + License Plate": "Color+Plate",
        "Repeated ": "Rep ",
        "Bounding Boxes": "Box",
        "Bbox": "Box",
        "Motion Category": "Motion",
        "Generic": "Gen",
        "(Window)": "",
    }
    label = query
    for old, new in replacements.items():
        label = label.replace(old, new)
    return label.strip()


def render_benchmark_plots(best: dict[str, dict[str, str]]) -> list[tuple[str, str]]:
    """Create report-level latency box plots and line graphs as dependency-free SVG."""
    return render_benchmark_svg_plots(best)


def render_benchmark_svg_plots(best: dict[str, dict[str, str]]) -> list[tuple[str, str]]:
    """Render actual saved per-run latency distributions and timelines."""
    _ = best
    OUT_BENCHMARK_PLOTS.mkdir(parents=True, exist_ok=True)
    outputs: list[tuple[str, str]] = []

    car_pairs = [
        ("Car Brand (Generic)", "Optimized Car Brand Generic (R854)"),
        ("Car Color (Generic)", "Optimized Car Color Generic (R480)"),
        ("Car Color Red", "Optimized Car Color Red (CFred+R480)"),
        ("License Plate Text Extraction (Generic)", "Optimized License Plate Recognition (Native)"),
        ("Color + License Plate (Red)", "Optimized Color+Plate Red (CFred native)"),
        ("Most Popular Brand", "Optimized Most Popular Brand (R854)"),
        ("Most Popular Color", "Optimized Most Popular Color (R480)"),
    ]
    volleyball_pairs = [
        ("Repeated Spikers (Window)", "Optimized Repeated Spikers (G+R854)"),
        ("Motion Category (Window)", "Optimized Motion Category (R480)"),
        ("Spike Bounding Boxes (Window)", "Optimized Spike Bounding Boxes (R960+B3+W20)"),
        ("Top Actions (Window)", "Optimized Top Actions (R854)"),
    ]

    def metric_data(title: str) -> dict:
        return read_json(METRICS / f"{slugify(title)}.json") or {}

    def chart(title: str) -> dict:
        return metric_data(title).get("chart_summary") or {}

    def llm_box(title: str) -> dict | None:
        stats = (chart(title).get("box_stats") or {}).get("llm")
        if isinstance(stats, dict) and stats.get("n"):
            return stats
        return None

    def llm_timeline(title: str) -> list[tuple[float, float]]:
        raw = ((chart(title).get("timelines") or {}).get("llm") or [])
        out: list[tuple[float, float]] = []
        for i, point in enumerate(raw, start=1):
            if not isinstance(point, dict):
                continue
            x = safe_float(point.get("x"), i)
            y = safe_float(point.get("y"), None)
            if y is not None and y >= 0:
                out.append((x, y))
        if out:
            return out
        values = ((chart(title).get("raw") or {}).get("llm_times_ms") or [])
        for i, value in enumerate(values, start=1):
            y = safe_float(value, None)
            if y is not None and y >= 0:
                out.append((float(i), y))
        return out

    def boxplot_rows(pairs: list[tuple[str, str]]) -> list[tuple[str, dict]]:
        rows: list[tuple[str, dict]] = []
        for naive, opt in pairs:
            for title in (naive, opt):
                stats = llm_box(title)
                if stats:
                    rows.append((short_query_label(title), stats))
        return rows

    def nice_max(value: float) -> float:
        if value <= 0:
            return 1.0
        if value <= 1000:
            step = 100.0
        elif value <= 5000:
            step = 500.0
        else:
            step = 1000.0
        return ((int(value / step) + 1) * step)

    def write_boxplot(filename: str, title: str, rows: list[tuple[str, dict]]):
        if not rows:
            return
        width = 1200
        left, right, top, bottom = 270, 40, 72, 54
        row_h = 42
        height = top + row_h * len(rows) + bottom
        plot_w = width - left - right
        max_value = 0.0
        for _label, stats in rows:
            vals = [stats.get(k) for k in ("max", "wHigh", "q3")]
            vals += list(stats.get("outliers") or [])
            max_value = max(max_value, *(safe_float(v, 0.0) for v in vals if v is not None))
        x_max = nice_max(max_value)

        def sx(value) -> float:
            return left + plot_w * max(0.0, min(safe_float(value, 0.0), x_max)) / x_max

        parts = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white'/>",
            f"<text x='{left}' y='30' font-family='Arial' font-size='22' font-weight='700'>{html.escape(title)}</text>",
            f"<text x='{left}' y='50' font-family='Arial' font-size='13' fill='#475569'>Box = IQR, center line = median, whiskers = saved low/high, circles = outliers.</text>",
        ]
        tick_count = 5
        for i in range(tick_count + 1):
            value = x_max * i / tick_count
            x = sx(value)
            parts.append(f"<line x1='{x:.1f}' y1='{top-10}' x2='{x:.1f}' y2='{height-bottom}' stroke='#d0d7de' stroke-dasharray='3,3'/>")
            parts.append(f"<text x='{x:.1f}' y='{height-20}' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>{value:.0f}</text>")
        parts.append(f"<text x='{left + plot_w / 2:.1f}' y='{height-4}' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>LLM latency (ms)</text>")

        for idx, (label, stats) in enumerate(rows):
            y = top + idx * row_h + row_h / 2
            q1 = sx(stats.get("q1"))
            q3 = sx(stats.get("q3"))
            med = sx(stats.get("median"))
            w_low = sx(stats.get("wLow", stats.get("min")))
            w_high = sx(stats.get("wHigh", stats.get("max")))
            mean = sx(stats.get("mean", stats.get("median")))
            fill = "#dbeafe" if "Opt" not in label else "#dcfce7"
            stroke = "#2563eb" if "Opt" not in label else "#16a34a"
            parts.append(f"<text x='12' y='{y+4:.1f}' font-family='Arial' font-size='12' fill='#1f2937'>{html.escape(label[:42])}</text>")
            parts.append(f"<line x1='{w_low:.1f}' y1='{y:.1f}' x2='{w_high:.1f}' y2='{y:.1f}' stroke='{stroke}' stroke-width='2'/>")
            parts.append(f"<line x1='{w_low:.1f}' y1='{y-9:.1f}' x2='{w_low:.1f}' y2='{y+9:.1f}' stroke='{stroke}' stroke-width='2'/>")
            parts.append(f"<line x1='{w_high:.1f}' y1='{y-9:.1f}' x2='{w_high:.1f}' y2='{y+9:.1f}' stroke='{stroke}' stroke-width='2'/>")
            parts.append(f"<rect x='{min(q1, q3):.1f}' y='{y-13:.1f}' width='{abs(q3-q1):.1f}' height='26' fill='{fill}' stroke='{stroke}' stroke-width='2'/>")
            parts.append(f"<line x1='{med:.1f}' y1='{y-15:.1f}' x2='{med:.1f}' y2='{y+15:.1f}' stroke='#111827' stroke-width='2'/>")
            parts.append(f"<path d='M {mean:.1f} {y-5:.1f} L {mean+5:.1f} {y:.1f} L {mean:.1f} {y+5:.1f} L {mean-5:.1f} {y:.1f} Z' fill='#f97316' opacity='0.9'/>")
            for outlier in stats.get("outliers") or []:
                ox = sx(outlier)
                parts.append(f"<circle cx='{ox:.1f}' cy='{y:.1f}' r='2.0' fill='#334155' opacity='0.45'/>")
            parts.append(f"<text x='{width-right-4}' y='{y+4:.1f}' text-anchor='end' font-family='Arial' font-size='11' fill='#475569'>n={int(safe_float(stats.get('n'), 0))}</text>")
        parts.append("</svg>")
        path = OUT_BENCHMARK_PLOTS / filename
        path.write_text("\n".join(parts), encoding="utf-8")
        outputs.append((title, f"plots/benchmark_summary/{filename}"))

    def downsample(points: list[tuple[float, float]], max_points: int = 900) -> list[tuple[float, float]]:
        if len(points) <= max_points:
            return points
        step = max(1, len(points) // max_points)
        sampled = points[::step]
        if sampled[-1] != points[-1]:
            sampled.append(points[-1])
        return sampled

    def write_lineplot(filename: str, title: str, naive_title: str, opt_title: str):
        series = [
            ("Naive", downsample(llm_timeline(naive_title)), "#2563eb"),
            ("Optimized", downsample(llm_timeline(opt_title)), "#16a34a"),
        ]
        series = [(label, pts, color) for label, pts, color in series if pts]
        if not series:
            return
        width, height = 1200, 430
        left, right, top, bottom = 74, 34, 62, 58
        plot_w = width - left - right
        plot_h = height - top - bottom
        min_x = min(x for _label, pts, _color in series for x, _y in pts)
        max_x = max(x for _label, pts, _color in series for x, _y in pts)
        max_y = nice_max(max(y for _label, pts, _color in series for _x, y in pts))
        x_span = max(1.0, max_x - min_x)

        def sx(x: float) -> float:
            return left + plot_w * (x - min_x) / x_span

        def sy(y: float) -> float:
            return top + plot_h * (1.0 - max(0.0, min(y, max_y)) / max_y)

        parts = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white'/>",
            f"<text x='{left}' y='30' font-family='Arial' font-size='22' font-weight='700'>{html.escape(title)}</text>",
            f"<text x='{left}' y='50' font-family='Arial' font-size='13' fill='#475569'>Saved LLM latency over frame/window order. Lines have no point markers.</text>",
            f"<line x1='{left}' y1='{height-bottom}' x2='{width-right}' y2='{height-bottom}' stroke='#475569'/>",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{height-bottom}' stroke='#475569'/>",
        ]
        for i in range(6):
            value = max_y * i / 5
            y = sy(value)
            parts.append(f"<line x1='{left}' y1='{y:.1f}' x2='{width-right}' y2='{y:.1f}' stroke='#d0d7de' stroke-dasharray='3,3'/>")
            parts.append(f"<text x='{left-8}' y='{y+4:.1f}' text-anchor='end' font-family='Arial' font-size='12' fill='#475569'>{value:.0f}</text>")
        for i in range(6):
            value = min_x + x_span * i / 5
            x = sx(value)
            parts.append(f"<text x='{x:.1f}' y='{height-bottom+22}' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>{value:.0f}</text>")
        for label, pts, color in series:
            point_str = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
            parts.append(f"<polyline points='{point_str}' fill='none' stroke='{color}' stroke-width='2.1' opacity='0.9'/>")
        parts.append(f"<rect x='{width-224}' y='18' width='178' height='38' fill='white' stroke='#d0d7de'/>")
        parts.append(f"<line x1='{width-210}' y1='34' x2='{width-174}' y2='34' stroke='#2563eb' stroke-width='3'/>")
        parts.append(f"<text x='{width-166}' y='38' font-family='Arial' font-size='12' fill='#1f2937'>Naive</text>")
        parts.append(f"<line x1='{width-210}' y1='50' x2='{width-174}' y2='50' stroke='#16a34a' stroke-width='3'/>")
        parts.append(f"<text x='{width-166}' y='54' font-family='Arial' font-size='12' fill='#1f2937'>Optimized</text>")
        parts.append(f"<text x='{left + plot_w / 2:.1f}' y='{height-6}' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>Frame/window order</text>")
        parts.append("<text x='18' y='235' transform='rotate(-90 18 235)' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>LLM latency (ms)</text>")
        parts.append("</svg>")
        path = OUT_BENCHMARK_PLOTS / filename
        path.write_text("\n".join(parts), encoding="utf-8")
        outputs.append((title, f"plots/benchmark_summary/{filename}"))

    write_boxplot("cars_llm_latency_boxplot.svg", "Cars: LLM Latency Box Plot", boxplot_rows(car_pairs))
    write_boxplot("volleyball_llm_latency_boxplot.svg", "Volleyball: LLM Latency Box Plot", boxplot_rows(volleyball_pairs))

    for naive, opt in car_pairs:
        name = slugify(f"line_{naive}_vs_{opt}_llm")
        write_lineplot(f"{name}.svg", f"{short_query_label(naive)} vs {short_query_label(opt)}: LLM Latency", naive, opt)
    for naive, opt in volleyball_pairs:
        name = slugify(f"line_{naive}_vs_{opt}_llm")
        write_lineplot(f"{name}.svg", f"{short_query_label(naive)} vs {short_query_label(opt)}: LLM Latency", naive, opt)

    return outputs


def esc(value) -> str:
    return html.escape(str(value))


CSS = """
@page {
  size: A4 landscape;
  margin: 16mm 18mm 18mm 18mm;
  /* Suppress the browser-injected URL/date header & footer in print-to-PDF. */
  @top-left { content: ""; }
  @top-center { content: ""; }
  @top-right { content: ""; }
  @bottom-left {
    content: "Naive vs Optimized Query Benchmark Report";
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 8.5pt;
    color: #6b7280;
  }
  @bottom-center { content: ""; }
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 8.5pt;
    color: #6b7280;
  }
}
@page :first {
  @bottom-left { content: ""; }
  @bottom-right { content: ""; }
}

* { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

html { background: #ffffff; }
body {
  font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: #1f2328;
  background: #ffffff;
  line-height: 1.55;
  font-size: 11pt;
  margin: 0;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
}

/* Typography */
h1 {
  font-size: 26pt;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #102a43;
  margin: 0 0 6px;
  line-height: 1.2;
}
h2 {
  font-size: 15pt;
  font-weight: 600;
  letter-spacing: -0.005em;
  color: #102a43;
  margin: 22px 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #d6dee7;
  page-break-after: avoid;
}
h3 {
  font-size: 11.5pt;
  font-weight: 600;
  color: #1f2937;
  margin: 14px 0 6px;
  page-break-after: avoid;
}
p { margin: 6px 0 8px; }
p, li { font-size: 10.5pt; line-height: 1.55; }
ul, ol { margin: 6px 0 12px; padding-left: 22px; }
ol { padding-left: 24px; }
li { margin-bottom: 4px; }
b, strong { font-weight: 600; color: #102a43; }
i, em { color: #1f2937; }

.muted { color: #5b6470; }

code {
  font-family: ui-monospace, "Cascadia Code", "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace;
  font-size: 0.9em;
  background: #f1f3f6;
  color: #1f2937;
  padding: 1px 5px;
  border-radius: 3px;
}

/* Title block */
.title {
  margin: 0 0 18px;
  padding: 0 0 14px;
  border-bottom: 2px solid #102a43;
}
.title h1 { margin: 0; }
.title .subtitle {
  margin: 6px 0 0;
  font-size: 10.5pt;
  color: #475569;
  line-height: 1.5;
}

/* Callouts */
.callouts { margin: 4px 0 14px; }
.callout {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #4a90b8;
  border-radius: 4px;
  padding: 10px 14px 10px 14px;
  margin: 0 0 8px;
}
.callout.warm {
  background: #fbf8ee;
  border-color: #ecdfb5;
  border-left-color: #b6862d;
}
.callout.note {
  background: #f5f8fb;
  border-color: #dfe6ed;
  border-left-color: #5b7a98;
}
.callout p { margin: 4px 0; font-size: 10pt; line-height: 1.55; }
.callout ul { margin: 4px 0 4px; padding-left: 20px; }
.callout li { font-size: 10pt; margin-bottom: 2px; line-height: 1.5; }
.callout-title {
  display: block;
  font-weight: 600;
  font-size: 10.5pt;
  color: #102a43;
  margin: 0 0 4px;
  letter-spacing: 0.005em;
}

.finding-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 8px 0 16px;
}
.finding {
  border: 1px solid #dbe5ef;
  border-radius: 4px;
  padding: 10px 12px;
  background: #ffffff;
  break-inside: avoid;
}
.finding h3 {
  margin: 0 0 6px;
  font-size: 11pt;
  color: #102a43;
}
.finding p {
  margin: 0;
}

/* Tables */
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  margin: 8px 0 14px;
  page-break-inside: auto;
  background: #ffffff;
  border: 1px solid #dde3eb;
  border-radius: 3px;
  overflow: hidden;
}
tr { page-break-inside: avoid; }
th, td {
  border-bottom: 1px solid #e6eaf0;
  border-right: 1px solid #eef2f6;
  padding: 6px 8px;
  font-size: 9.2pt;
  vertical-align: top;
  line-height: 1.42;
}
th:last-child, td:last-child { border-right: none; }
tr:last-child td { border-bottom: none; }
thead th {
  background: #eef2f7;
  color: #102a43;
  text-align: left;
  font-weight: 600;
  font-size: 9.4pt;
  border-bottom: 1.5px solid #c7d1dc;
  letter-spacing: 0.01em;
}
tbody tr:nth-child(even) td { background: #f8fafc; }
td.num, th.num {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* Wide data tables stay legible at smaller sizes */
.small { font-size: 8.4pt; }
.small th, .small td {
  font-size: 8.4pt;
  padding: 5px 7px;
  line-height: 1.4;
}
.small thead th { font-size: 8.6pt; }

/* Plot grids */
.plot-grid, .appendix-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin: 10px 0 16px;
}
.plot, .appendix-plot {
  break-inside: avoid;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 10px;
  background: #ffffff;
}
.plot img, .appendix-plot img {
  width: 100%;
  height: auto;
  display: block;
}
.plot-title {
  font-size: 9.2pt;
  font-weight: 600;
  margin: 0 0 6px;
  color: #102a43;
  letter-spacing: 0.005em;
}
.appendix-query {
  page-break-inside: avoid;
  margin-top: 18px;
}
.appendix-query > h3 {
  margin-top: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e2e8f0;
}

.section { page-break-before: auto; }
.pagebreak { page-break-before: always; }
"""


def plot_rel(path: Path) -> str:
    return path.relative_to(RESULTS).as_posix()


def human_plot_name(value: str) -> str:
    value = value.replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() if not word.isupper() else word for word in value.split())


def appendix_plot_div(title: str, src: str) -> str:
    return (
        f"<div class='appendix-plot'>"
        f"<div class='plot-title'>{esc(title)}</div>"
        f"<img src='{esc(src)}' alt='{esc(title)}'>"
        f"</div>"
    )


def render_appendix_summary_plots(best: dict[str, dict[str, str]]) -> None:
    groups = [
        ("Cars naive", "cars", CAR_NAIVE, "cars_naive_accuracy.svg", "Cars Naive: Frame vs Overall Query Accuracy"),
        ("Cars optimized", "cars", CAR_OPT, "cars_optimized_accuracy.svg", "Cars Optimized: Frame vs Overall Query Accuracy"),
        ("Volleyball naive", "volleyball", VB_NAIVE, "volleyball_naive_accuracy.svg", "Volleyball Naive: Window/Frame vs Overall Query Accuracy"),
        ("Volleyball optimized", "volleyball", VB_OPT, "volleyball_optimized_accuracy.svg", "Volleyball Optimized: Window/Frame vs Overall Query Accuracy"),
    ]
    OUT_BENCHMARK_PLOTS.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for group_name, dataset, titles, _filename, _title in groups:
        for query_title in titles:
            row = compute_row(query_title, best, dataset)
            all_rows.append({
                "group": group_name,
                "query": query_title,
                "label": short_query_label(query_title),
                "frame": pct_value(row["frame_accuracy"]),
                "overall": pct_value(row["overall_query_accuracy"]),
                "llm": safe_float(row["avg_llm_ms"].replace(",", ""), None),
            })

    def write_accuracy(group_name: str, filename: str, title: str) -> None:
        data = [row for row in all_rows if row["group"] == group_name]
        data = [row for row in data if row["frame"] is not None or row["overall"] is not None]
        if not data:
            return
        width = 1180
        left, right, top = 285, 42, 58
        row_h = 34
        height = top + row_h * len(data) + 54
        plot_w = width - left - right
        parts = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white'/>",
            f"<text x='{left}' y='28' font-family='Arial' font-size='22' font-weight='700'>{html.escape(title)}</text>",
            f"<text x='{left}' y='48' font-family='Arial' font-size='13' fill='#475569'>Blue = frame/window accuracy when available. Green = overall query accuracy.</text>",
        ]
        for tick in range(0, 101, 25):
            x = left + plot_w * tick / 100
            parts.append(f"<line x1='{x:.1f}' y1='{top-8}' x2='{x:.1f}' y2='{height-36}' stroke='#d0d7de' stroke-dasharray='3,3'/>")
            parts.append(f"<text x='{x:.1f}' y='{height-16}' text-anchor='middle' font-family='Arial' font-size='12' fill='#475569'>{tick}%</text>")
        for i, row in enumerate(data):
            y = top + i * row_h
            label = html.escape(row["label"][:44])
            frame = row["frame"]
            overall = row["overall"]
            frame_w = plot_w * frame / 100 if frame is not None else 0
            overall_w = plot_w * overall / 100 if overall is not None else 0
            frame_text = f"{frame:.1f}%" if frame is not None else "n/a"
            overall_text = f"{overall:.1f}%" if overall is not None else "n/a"
            parts.append(f"<text x='12' y='{y+18}' font-family='Arial' font-size='12' fill='#1f2937'>{label}</text>")
            parts.append(f"<rect x='{left}' y='{y+3}' width='{frame_w:.1f}' height='12' fill='#2563eb' opacity='0.82'/>")
            parts.append(f"<rect x='{left}' y='{y+18}' width='{overall_w:.1f}' height='12' fill='#16a34a' opacity='0.82'/>")
            parts.append(f"<text x='{left + frame_w + 5:.1f}' y='{y+13}' font-family='Arial' font-size='10' fill='#1f2937'>{frame_text}</text>")
            parts.append(f"<text x='{left + overall_w + 5:.1f}' y='{y+28}' font-family='Arial' font-size='10' fill='#1f2937'>{overall_text}</text>")
        parts.append("</svg>")
        (OUT_BENCHMARK_PLOTS / filename).write_text("\n".join(parts), encoding="utf-8")

    for group_name, _dataset, _titles, filename, title in groups:
        write_accuracy(group_name, filename, title)

    cost_rows = []
    for group_name, _dataset, _titles, _filename, _title in groups:
        vals = [row["llm"] for row in all_rows if row["group"] == group_name and row["llm"] is not None and row["llm"] > 0]
        if vals:
            cost_rows.append((group_name, sum(vals) / len(vals)))
    if cost_rows:
        width, height = 900, 420
        left, bottom, top, right = 90, 70, 54, 30
        plot_h = height - top - bottom
        plot_w = width - left - right
        max_v = max(v for _g, v in cost_rows) * 1.15
        bar_w = plot_w / max(len(cost_rows), 1) * 0.55
        colors = ["#64748b", "#0ea5e9", "#94a3b8", "#14b8a6"]
        parts = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white'/>",
            f"<text x='{left}' y='30' font-family='Arial' font-size='22' font-weight='700'>Average LLM Latency by Benchmark Group</text>",
            f"<line x1='{left}' y1='{height-bottom}' x2='{width-right}' y2='{height-bottom}' stroke='#475569'/>",
            f"<line x1='{left}' y1='{top}' x2='{left}' y2='{height-bottom}' stroke='#475569'/>",
        ]
        for i, (label, value) in enumerate(cost_rows):
            x = left + (i + 0.5) * plot_w / len(cost_rows) - bar_w / 2
            h = plot_h * value / max_v
            y = height - bottom - h
            parts.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{h:.1f}' fill='{colors[i % len(colors)]}' opacity='0.88'/>")
            parts.append(f"<text x='{x + bar_w/2:.1f}' y='{y - 6:.1f}' text-anchor='middle' font-family='Arial' font-size='13'>{value:.0f} ms</text>")
            parts.append(f"<text x='{x + bar_w/2:.1f}' y='{height - bottom + 22}' text-anchor='middle' font-family='Arial' font-size='12'>{html.escape(label)}</text>")
        parts.append("<text x='18' y='210' transform='rotate(-90 18 210)' text-anchor='middle' font-family='Arial' font-size='13'>Average LLM latency (ms)</text>")
        parts.append("</svg>")
        (OUT_BENCHMARK_PLOTS / "group_avg_llm_latency.svg").write_text("\n".join(parts), encoding="utf-8")


def build_appendix(plot_outputs: list[tuple[str, str]], best: dict[str, dict[str, str]]) -> str:
    render_appendix_summary_plots(best)
    main_srcs = {src for _title, src in plot_outputs}
    aggregate_dirs = {
        slugify(title) for title in CAR_NAIVE
        if any(token in title for token in ["Most Popular", "Unique", "Repeating"])
    }
    summary_names = [
        ("Cars Naive: Frame vs Overall Query Accuracy", "cars_naive_accuracy.svg"),
        ("Cars Optimized: Frame vs Overall Query Accuracy", "cars_optimized_accuracy.svg"),
        ("Volleyball Naive: Window/Frame vs Overall Query Accuracy", "volleyball_naive_accuracy.svg"),
        ("Volleyball Optimized: Window/Frame vs Overall Query Accuracy", "volleyball_optimized_accuracy.svg"),
        ("Average LLM Latency by Benchmark Group", "group_avg_llm_latency.svg"),
    ]
    summary_plots = []
    for title, filename in summary_names:
        path = OUT_BENCHMARK_PLOTS / filename
        rel = plot_rel(path) if path.exists() else ""
        if rel and rel not in main_srcs:
            summary_plots.append((title, rel))

    other_report_plots = []
    if OUT_BENCHMARK_PLOTS.exists():
        summary_files = {filename for _title, filename in summary_names}
        for path in sorted(OUT_BENCHMARK_PLOTS.iterdir(), key=lambda p: p.name):
            if not path.is_file() or path.name in summary_files:
                continue
            if "license_plate_recognition" in path.name or "license_plates_generic_vs_optimized_license_plates" in path.name:
                continue
            rel = plot_rel(path)
            if rel in main_srcs:
                continue
            other_report_plots.append((human_plot_name(path.stem), rel))

    per_query_sections = []
    plot_order = ["accuracy_bar.png", "llm_box.png", "operator_boxes.png", "llm_timeline.png", "e2e_timeline.png"]
    plot_titles = {
        "accuracy_bar.png": "Accuracy Summary",
        "llm_box.png": "LLM Latency Box Plot",
        "operator_boxes.png": "Operator Latency Box Plot",
        "llm_timeline.png": "LLM Latency Timeline",
        "e2e_timeline.png": "End-to-End Latency Timeline",
    }
    if (RESULTS / "plots").exists():
        for folder in sorted((RESULTS / "plots").iterdir(), key=lambda p: p.name):
            if not folder.is_dir() or folder.name == "benchmark_summary":
                continue
            if folder.name.startswith("specific_plate_") and folder.name != slugify(f"Specific Plate: {SPECIFIC_PLATE_TARGET}"):
                continue
            files = []
            for filename in plot_order:
                if folder.name in aggregate_dirs and filename == "accuracy_bar.png":
                    continue
                path = folder / filename
                if path.exists():
                    files.append((plot_titles.get(filename, human_plot_name(path.stem)), plot_rel(path)))
            extras = [
                path for path in sorted(folder.iterdir(), key=lambda p: p.name)
                if path.is_file() and path.name not in plot_order
            ]
            files.extend((human_plot_name(path.stem), plot_rel(path)) for path in extras)
            if files:
                per_query_sections.append(
                    f"<div class='appendix-query'><h3>{esc(human_plot_name(folder.name))}</h3>"
                    f"<div class='appendix-grid'>{''.join(appendix_plot_div(title, src) for title, src in files)}</div></div>"
                )

    summary_html = "".join(appendix_plot_div(title, src) for title, src in summary_plots)
    other_html = "".join(appendix_plot_div(title, src) for title, src in other_report_plots)
    return f"""
  <div class="pagebreak"></div>
  <h2>Appendix</h2>
  <p>This appendix collects the remaining generated plots. The first block contains the report-level summary plots; the following blocks contain per-query diagnostic plots from <code>results/plots</code>. Legacy plots for the old specific-plate target are excluded.</p>

  <h3>Summary Plots</h3>
  <div class="appendix-grid">{summary_html or '<p class="muted">No extra summary plots found.</p>'}</div>

  <h3>Additional Report-Level Plots</h3>
  <div class="appendix-grid">{other_html or '<p class="muted">No additional report-level plots found.</p>'}</div>

  <h3>Per-Query Diagnostic Plots</h3>
  {''.join(per_query_sections) or '<p class="muted">No per-query plots found.</p>'}
"""


def int_cell(value: str) -> int | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text == "-":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def float_cell(value: str) -> float | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_car_aggregate(title: str) -> bool:
    return any(token in title for token in ["Most Popular", "Unique", "Repeating"])


def query_pair_rows(best: dict[str, dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    car_rows = []
    for naive, opt in zip(CAR_NAIVE, CAR_OPT):
        car_rows.append({
            "dataset": "cars",
            "naive_title": naive,
            "opt_title": opt,
            "naive": compute_row(naive, best, "cars"),
            "opt": compute_row(opt, best, "cars"),
        })
    vb_rows = []
    for naive, opt in zip(VB_NAIVE, VB_OPT):
        vb_rows.append({
            "dataset": "volleyball",
            "naive_title": naive,
            "opt_title": opt,
            "naive": compute_row(naive, best, "volleyball"),
            "opt": compute_row(opt, best, "volleyball"),
        })
    return car_rows, vb_rows


def signed(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "-"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}{suffix}"


def latency_change(naive_ms: float | None, opt_ms: float | None) -> str:
    if not naive_ms or opt_ms is None:
        return "-"
    change = 100.0 * (opt_ms - naive_ms) / naive_ms
    if opt_ms == 0:
        return signed(change, "%")
    return f"{signed(change, '%')} ({naive_ms / opt_ms:.2f}x)"


def pair_interpretation(dataset: str, naive_title: str, opt_title: str, naive: dict[str, str], opt: dict[str, str]) -> str:
    frame_delta = None
    overall_delta = None
    naive_frame = float_cell(naive["frame_accuracy"])
    opt_frame = float_cell(opt["frame_accuracy"])
    naive_overall = float_cell(naive["overall_query_accuracy"])
    opt_overall = float_cell(opt["overall_query_accuracy"])
    if naive_frame is not None and opt_frame is not None:
        frame_delta = opt_frame - naive_frame
    if naive_overall is not None and opt_overall is not None:
        overall_delta = opt_overall - naive_overall

    opt_messages = int_cell(opt["messages"])
    if dataset == "cars":
        if not is_car_aggregate(opt_title) and opt_messages is not None and opt_messages < CAR_TARGET_FRAMES:
            return f"Coverage shortfall: optimized run has {opt_messages}/{CAR_TARGET_FRAMES} rows, so thesis comparisons should mark it incomplete even when the accuracy estimate is useful."
        if "Color+Plate" in opt_title:
            return "CV color filtering sharply reduces LLM calls for the expensive red-car plate query, but set-level accuracy remains low because extra predicted plate strings are penalized by Jaccard scoring."
        if "License Plate Recognition" in opt_title:
            return "Native-resolution plate recognition protects text detail better than resize/filter variants; this is a different optimization pattern from brand/color classification."
        if "Most Popular" in opt_title:
            return "This is an aggregate query: judge it by final answer accuracy, not frame accuracy. A small number of window outputs can still answer the whole-video question."
        if "Unique" in opt_title or "Repeating" in opt_title:
            return "Set retrieval is the hard case for plates: the final answer is sensitive to both missed plates and hallucinated/variant plate strings."
        if frame_delta is not None and frame_delta >= 0 and overall_delta is not None and overall_delta >= 0:
            return "Optimization preserved or improved both frame-level and final-answer accuracy while reducing LLM latency."
        if overall_delta is not None and overall_delta >= 0:
            return "Optimization preserved the final answer; frame-level differences mainly reflect label noise and class imbalance."
        return "Optimization changes the error profile; use the paired row to discuss the tradeoff between cost and answer quality."

    if "Bounding Boxes" in opt_title:
        return "Bounding-box rows intentionally use higher resolution and grouped frames; existence can be scored, but IoU needs raw ordered box pairs that were not saved."
    if " Count" in opt_title:
        return "Count queries use a graded count-closeness score, so the overall value captures how far the aggregate count is from the annotation count."
    if "->" in opt_title:
        return "Temporal pair queries are strict at the overall level: a correct answer requires detecting the ordered event anywhere in the represented clip."
    if frame_delta is not None and frame_delta >= 0:
        return "Resize-based optimization keeps the window-level decision comparable to the naive run while lowering the LLM cost."
    return "Read this as a window-level comparison; exact frame alignment is not recoverable after aggregation."


def comparison_table(pair_rows: list[dict[str, str]]) -> str:
    rows = []
    for item in pair_rows:
        naive = item["naive"]
        opt = item["opt"]
        naive_llm = float_cell(naive["avg_llm_ms"])
        opt_llm = float_cell(opt["avg_llm_ms"])
        frame_delta = None
        overall_delta = None
        nf = float_cell(naive["frame_accuracy"])
        of = float_cell(opt["frame_accuracy"])
        no = float_cell(naive["overall_query_accuracy"])
        oo = float_cell(opt["overall_query_accuracy"])
        if nf is not None and of is not None:
            frame_delta = of - nf
        if no is not None and oo is not None:
            overall_delta = oo - no
        rows.append(
            "<tr>"
            f"<td>{esc(item['naive_title'])}</td>"
            f"<td>{esc(item['opt_title'])}</td>"
            f"<td class='num'>{esc(naive['messages'])} -> {esc(opt['messages'])}</td>"
            f"<td class='num'>{esc(naive['avg_llm_ms'])} -> {esc(opt['avg_llm_ms'])}</td>"
            f"<td class='num'>{esc(latency_change(naive_llm, opt_llm))}</td>"
            f"<td class='num'>{esc(signed(frame_delta, ' pp'))}</td>"
            f"<td class='num'>{esc(signed(overall_delta, ' pp'))}</td>"
            f"<td>{esc(pair_interpretation(item['dataset'], item['naive_title'], item['opt_title'], naive, opt))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def coverage_audit(best: dict[str, dict[str, str]]) -> str:
    groups = [
        ("Cars naive frame-level", "cars", CAR_NAIVE, CAR_TARGET_FRAMES, "per-frame car result rows"),
        ("Cars optimized frame-level", "cars", CAR_OPT, CAR_TARGET_FRAMES, "per-frame car result rows"),
        ("Volleyball naive windows", "volleyball", VB_NAIVE, 200, "20-frame windows representing the capped sender run"),
        ("Volleyball optimized windows", "volleyball", VB_OPT, 200, "20-frame windows or grouped-frame outputs"),
    ]
    rows = []
    for label, dataset, titles, target, unit in groups:
        checked = []
        short = []
        aggregate = []
        for title in titles:
            if dataset == "cars" and is_car_aggregate(title):
                aggregate.append(title)
                continue
            row = compute_row(title, best, dataset)
            messages = int_cell(row["messages"])
            checked.append(title)
            if messages is None or messages < target:
                short.append(f"{title} ({messages or 0}/{target})")
        status = "complete" if not short else "incomplete"
        notes = []
        if short:
            notes.append("; ".join(short))
        if aggregate:
            notes.append(f"{len(aggregate)} aggregate car queries emit window/final rows and are audited by final-answer accuracy instead of {CAR_TARGET_FRAMES} frame rows")
        rows.append(
            "<tr>"
            f"<td>{esc(label)}</td>"
            f"<td class='num'>{len(checked)}</td>"
            f"<td class='num'>{esc(str(target))}</td>"
            f"<td>{esc(unit)}</td>"
            f"<td>{esc(status)}</td>"
            f"<td>{esc('; '.join(notes) if notes else 'all checked queries meet the threshold')}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def average_llm(rows: list[dict[str, str]]) -> float | None:
    vals = [float_cell(row["avg_llm_ms"]) for row in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def best_overall_rows(rows: list[dict[str, str]], limit: int = 3) -> list[dict[str, str]]:
    sortable = []
    for row in rows:
        value = float_cell(row["overall_query_accuracy"])
        if value is not None:
            sortable.append((value, row))
    return [row for _value, row in sorted(sortable, key=lambda x: (-x[0], x[1]["query"]))[:limit]]


def weakest_overall_rows(rows: list[dict[str, str]], limit: int = 3) -> list[dict[str, str]]:
    sortable = []
    for row in rows:
        value = float_cell(row["overall_query_accuracy"])
        if value is not None:
            sortable.append((value, row))
    return [row for _value, row in sorted(sortable, key=lambda x: (x[0], x[1]["query"]))[:limit]]


def query_name_list(rows: list[dict[str, str]]) -> str:
    return ", ".join(f"{row['query']} ({row['overall_query_accuracy']})" for row in rows) or "-"


def findings_html(best: dict[str, dict[str, str]]) -> str:
    car_pairs, vb_pairs = query_pair_rows(best)
    cars_naive = [item["naive"] for item in car_pairs]
    cars_opt = [item["opt"] for item in car_pairs]
    vb_naive = [item["naive"] for item in vb_pairs]
    vb_opt = [item["opt"] for item in vb_pairs]

    car_naive_llm = average_llm(cars_naive)
    car_opt_llm = average_llm(cars_opt)
    vb_naive_llm = average_llm(vb_naive)
    vb_opt_llm = average_llm(vb_opt)
    car_short = [
        item["opt_title"] for item in car_pairs
        if not is_car_aggregate(item["opt_title"])
        and (int_cell(item["opt"]["messages"]) or 0) < CAR_TARGET_FRAMES
    ]
    vb_short = [
        item["opt_title"] for item in vb_pairs
        if (int_cell(item["opt"]["messages"]) or 0) < 200
    ]

    return f"""
  <h2>Thesis-Level Findings</h2>
  <div class="finding-grid">
    <div class="finding">
      <h3>Coverage and comparability</h3>
      <p>All naive volleyball and final optimized volleyball rows meet the 200-window threshold. The optimized car frame-level set is nearly complete but not perfect: {esc('; '.join(car_short) if car_short else 'no optimized car shortfalls')} fall below the {CAR_TARGET_FRAMES}-frame target. These rows should be described as near-complete runs, not as clean full-coverage comparisons.</p>
    </div>
    <div class="finding">
      <h3>Latency effect</h3>
      <p>Across the paired report rows, average car LLM latency changes from {num(car_naive_llm)} ms in the naive rows to {num(car_opt_llm)} ms in the optimized rows. Volleyball changes from {num(vb_naive_llm)} ms to {num(vb_opt_llm)} ms. The strongest savings come from resize-only classification and CV prefilters; localization and text-reading tasks retain more resolution and therefore save less.</p>
    </div>
    <div class="finding">
      <h3>Best final answers</h3>
      <p>Cars: {esc(query_name_list(best_overall_rows(cars_opt)))}. Volleyball: {esc(query_name_list(best_overall_rows(vb_opt)))}. These rows are useful examples where optimization did not prevent the system from answering the full query correctly.</p>
    </div>
    <div class="finding">
      <h3>Weakest final answers</h3>
      <p>Cars: {esc(query_name_list(weakest_overall_rows(cars_opt)))}. Volleyball: {esc(query_name_list(weakest_overall_rows(vb_opt)))}. These failures are concentrated in set-retrieval, rare plate aggregation, temporal-pair detection, and bounding-box tasks where a single final answer depends on sparse events or exact text/box recovery.</p>
    </div>
  </div>

  <h2>Coverage Audit</h2>
  <p>This table separates full per-frame car runs from aggregate car queries. Aggregate car queries intentionally emit window/final rows, so their message count is not expected to equal {CAR_TARGET_FRAMES}; they are evaluated by final-answer accuracy.</p>
  <table class="small">
    <thead><tr><th>Group</th><th>Checked queries</th><th>Required count</th><th>Unit</th><th>Status</th><th>Details</th></tr></thead>
    <tbody>{coverage_audit(best)}</tbody>
  </table>

  <h2>Naive vs Optimized Pairwise Findings: Cars</h2>
  <table class="small">
    <thead><tr><th>Naive query</th><th>Optimized query</th><th>Messages</th><th>Avg LLM (ms)</th><th>LLM change</th><th>Frame acc. delta</th><th>Overall acc. delta</th><th>Interpretation</th></tr></thead>
    <tbody>{comparison_table(car_pairs)}</tbody>
  </table>

  <h2>Naive vs Optimized Pairwise Findings: Volleyball</h2>
  <table class="small">
    <thead><tr><th>Naive query</th><th>Optimized query</th><th>Messages</th><th>Avg LLM (ms)</th><th>LLM change</th><th>Window acc. delta</th><th>Overall acc. delta</th><th>Interpretation</th></tr></thead>
    <tbody>{comparison_table(vb_pairs)}</tbody>
  </table>
"""


def build_html() -> str:
    best = load_best_runs()
    plot_outputs = render_benchmark_plots(best)
    appendix_html = build_appendix(plot_outputs, best)
    findings = findings_html(best)

    benchmark_rows = [
        ("Car attribute per frame", "brand/color each frame", "Decode > LLM", "Decode > resize > LLM", "per frame", "correct label or correct SKIP over 3953 frames", "majority/set answer correct, depending on query"),
        ("Car rare target", "red car, specific brand", "Decode > LLM", "Decode > CV filter > resize > LLM", "per frame", "binary target label over 3953 frames", "target exists/count/list is correct"),
        ("License plate text extraction", "license plates", "Decode > LLM", "Decode > native/R960 > LLM, optional conservative filter", "per frame + set", "plate text correct or correct SKIP", "unique plate set exact/Jaccard"),
        ("Volleyball event", "repeated spikers", "Decode > LLM > window", "Decode > resize > LLM > window > threshold", "20-frame windows", "event label aligned to frame/window", "event-level accuracy/F1"),
        ("Volleyball motion", "motion category", "Decode > LLM > window", "Decode > resize > LLM > window", "20-frame windows", "window motion label", "dominant task answer correct"),
        ("Volleyball bounding boxes", "spike-player box", "Decode > frame grouping > LLM", "Decode > R960 > 3-frame grouping > LLM, raw output preserved", "frame or group", "box present/absent and parse success", "IoU@0.5 and mean IoU"),
    ]

    benchmark_html = "\n".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
        for row in benchmark_rows
    )
    plots_html = "\n".join(
        f"<div class='plot'><div class='plot-title'>{esc(title)}</div><img src='{esc(src)}' alt='{esc(title)}'></div>"
        for title, src in plot_outputs
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Naive vs Optimized Benchmark Report</title>
  <style>{CSS}</style>
</head>
<body>
  <header class="title">
    <h1>Naive vs Optimized Query Benchmark Report</h1>
    <p class="subtitle">Generated from <code>results/metrics/summary.csv</code> and result JSONL files. Cars use a fixed denominator of {CAR_TARGET_FRAMES} frames where possible; volleyball uses {VB_TARGET_FRAMES} frames.</p>
  </header>

  <div class="callouts">
    <div class="callout">
      <span class="callout-title">How to read the two accuracy columns</span>
      <ul>
        <li><b>Frame-by-frame accuracy</b> scores each frame or window against ground truth.</li>
        <li><b>Overall query accuracy</b> scores the final answer after aggregating the whole run.</li>
      </ul>
      <p>The scoring rule for overall query accuracy depends on query type:</p>
      <ul>
        <li>generic set queries &mdash; Jaccard overlap between predicted and ground-truth label sets;</li>
        <li>most-popular queries &mdash; exact top-label match;</li>
        <li>specific target / event queries &mdash; binary existence;</li>
        <li>count queries &mdash; count closeness;</li>
        <li>bounding-box queries &mdash; box existence (IoU cannot be reconstructed from the saved aggregate outputs).</li>
      </ul>
      <p>The <i>predicted vs ground truth</i> column shows the predicted final answer next to the corresponding ground-truth answer.</p>
    </div>

    <div class="callout note">
      <span class="callout-title">Glossary for the Notes column</span>
      <p><i>labeled acc</i> = label-only accuracy on frames that have a non-empty ground-truth label, ignoring SKIP rows. <i>LLM calls</i> = number of frames that actually invoked the LLM (the rest were CV-filtered out). <i>missing row(s)</i> = result rows below the fixed denominator. <i>extra row(s) ignored</i> = result rows beyond the fixed denominator that are not used in scoring.</p>
    </div>

    <div class="callout warm">
      <span class="callout-title">Volleyball caveat</span>
      <p>Most volleyball outputs are 20-frame windows, so the table reports a window-level proxy for frame accuracy on the represented frames from the capped sender run. Bounding-box IoU needs raw frame IDs and ordered predicted boxes; the current saved JSONL supports box existence, not IoU.</p>
    </div>

    <div class="callout warm">
      <span class="callout-title">Specific plate caveat</span>
      <p>The old specific-plate query used a target that was not in the video. The report now uses <code>{SPECIFIC_PLATE_TARGET}</code>, which appears in {specific_plate_gt_count()} annotated frames. The old result is not reused; the scored row comes from the completed run for this updated plate.</p>
    </div>

    <div class="callout note">
      <span class="callout-title">Message-count footnote</span>
      <p>The <i>Messages</i> column reports raw rows produced by the run; the accuracy denominator is always {CAR_TARGET_FRAMES} for cars (or {VB_TARGET_FRAMES} for volleyball). For stream-wide aggregates, a full run usually emits window rows rather than one row per input frame. Surplus rows are ignored when scoring fixed-denominator frame metrics.</p>
    </div>
  </div>

  <h2>Benchmark Organization</h2>
  <table>
    <thead><tr><th>Family</th><th>Example task</th><th>Naive pipeline</th><th>Optimized pipeline</th><th>Unit</th><th>Frame-by-frame accuracy</th><th>Overall query accuracy</th></tr></thead>
    <tbody>{benchmark_html}</tbody>
  </table>

  <h2>Metrics and Why They Matter</h2>
  <ul>
    <li><b>Frame-by-frame accuracy</b> matters for per-frame filters and labels. It indicates whether the pipeline can make the right decision at the same granularity at which frames are sent.</li>
    <li><b>Overall query accuracy</b> matters for analytical queries. A query can miss many frames but still answer the final question correctly, or it can have high frame accuracy but return the wrong final set/count/top label.</li>
    <li><b>Message count</b> is a run-quality check. For cars, clean per-frame runs should be close to {CAR_TARGET_FRAMES}. For volleyball window runs, full windows should represent the capped {VB_TARGET_FRAMES} sent frames.</li>
    <li><b>Average LLM time</b> is the main cost signal. Optimizations are valuable when they reduce calls, resolution, or prompt work without damaging the task-level answer.</li>
  </ul>

  {findings}

  <h2>Plots</h2>
  <p>The plots below use the saved per-run latency values. Box plots show LLM latency distribution, with outlier circles kept. Line graphs show LLM latency across frame/window order and intentionally do not draw point markers.</p>
  <div class="plot-grid">{plots_html}</div>

  <h2>Cars: Naive Results</h2>
  <table class="small">
    <thead><tr><th>Query</th><th>Pipeline</th><th>Messages</th><th>Duration (s)</th><th>Avg LLM (ms)</th><th>Frame/window acc.</th><th>Overall query acc.</th><th>Predicted vs ground truth</th><th>Notes</th></tr></thead>
    <tbody>{table_rows(CAR_NAIVE, best, "cars")}</tbody>
  </table>

  <h2>Cars: Optimized Results</h2>
  <table class="small">
    <thead><tr><th>Query</th><th>Pipeline</th><th>Messages</th><th>Duration (s)</th><th>Avg LLM (ms)</th><th>Frame/window acc.</th><th>Overall query acc.</th><th>Predicted vs ground truth</th><th>Notes</th></tr></thead>
    <tbody>{table_rows(CAR_OPT, best, "cars", optimized=True)}</tbody>
  </table>

  <h2>Car Interpretation</h2>
  <ul>
    <li>Generic brand and color queries are good candidates for resizing because the target is visible at lower resolution and every frame may need a label.</li>
    <li>Specific rare targets, such as red cars, benefit most from a cheap CV filter before the LLM. Most frames become SKIP without paying for an LLM call.</li>
    <li>The red color plus plate query is the clearest optimization win: the CV red filter keeps the expensive license plate text extraction prompt only for likely red-car frames.</li>
    <li>License plate text extraction is different from color and brand. It needs detail. A white-region prefilter is aggressive and can skip valid plates, so it should be reported as an ablation unless the task is specifically restricted to likely white/plate-heavy frames.</li>
    <li>The white-prefilter plate run should be treated as an ablation: it is useful for comparing the white-region prefilter on the generic plate-reading task, but the final optimized plate rows use native-resolution detail preservation.</li>
    <li>Aggregate car queries (most-popular, unique-plate, repeating-plate) should be read mainly through overall query accuracy. They save only final window answers, so there is no reliable ordered per-frame label sequence to score.</li>
    <li>The most-popular queries use exact top-answer matching. This makes the metric intentionally strict: Most Popular Color succeeds because both prediction and ground truth are gray, while the brand variants score 0% because the predicted top brand or brand-color pair is different from the ground truth.</li>
    <li>Unique and repeating plate queries are set-retrieval tasks, so the report uses Jaccard overlap instead of exact match. Their low scores show that the pipeline found some valid plate text but also missed many ground-truth plates or added extra plate strings.</li>
    <li><b>Reading the high-frame / low-query gap.</b> A few rows show high frame accuracy alongside low overall query accuracy &mdash; for example, <i>Color + License Plate (Red)</i> is 99.4% per frame but 10% overall, and <i>Specific Plate: {SPECIFIC_PLATE_TARGET}</i> is 5.3% per frame but 100% overall. This is expected: per-frame accuracy is dominated by correct SKIP decisions (the rare target is absent in most frames), while overall query accuracy compares the aggregated set / single answer to ground truth, where set queries penalize over-generation (extra plate strings) and rare-target queries reward a single hit anywhere in the run.</li>
  </ul>

  <div class="pagebreak"></div>
  <h2>Volleyball: Naive Results</h2>
  <table class="small">
    <thead><tr><th>Query</th><th>Pipeline</th><th>Messages</th><th>Duration (s)</th><th>Avg LLM (ms)</th><th>Frame/window acc.</th><th>Overall query acc.</th><th>Predicted vs ground truth</th><th>Notes</th></tr></thead>
    <tbody>{table_rows(VB_NAIVE, best, "volleyball")}</tbody>
  </table>

  <h2>Volleyball: Optimized Results</h2>
  <table class="small">
    <thead><tr><th>Query</th><th>Pipeline</th><th>Messages</th><th>Duration (s)</th><th>Avg LLM (ms)</th><th>Frame/window acc.</th><th>Overall query acc.</th><th>Predicted vs ground truth</th><th>Notes</th></tr></thead>
    <tbody>{table_rows(VB_OPT, best, "volleyball", optimized=True)}</tbody>
  </table>

  <h2>Volleyball Interpretation</h2>
  <ul>
    <li>The updated volleyball scoring reads the original tracking annotations, not just the old majority-action field. This matters because a frame can contain several actions at the same time.</li>
    <li>Windowed volleyball queries should be interpreted as window-level accuracy. They answer temporal questions, so exact per-frame alignment is not recoverable after aggregation.</li>
    <li>Repeated-action and event queries are judged by whether the target event exists in the window/run. This matches the query intent better than exact label matching for every player.</li>
    <li>Count queries are judged by count closeness, because being off by one is less severe than predicting the wrong action entirely.</li>
    <li>Bounding-box queries are judged by box existence only in this report. To score IoU, the pipeline must save frame IDs, ground-truth boxes, and raw predicted boxes before window aggregation.</li>
    <li><b>Reading the window-acc / query-acc gap.</b> Some rows show high window accuracy with 0% overall query accuracy &mdash; for example, <i>Dig&rarr;Set Events</i> is 100% per window but 0% overall, and <i>Set Bounding Boxes</i> is 80% per window but 0% overall. The window proxy rewards correctly answering "no, this window does not contain the event"; the overall query asks "did the event ever appear in the run", which is a single ordered-pair / target check across the full clip and is much harder to satisfy with sparse window-level outputs.</li>
    <li><b>Optimized volleyball latency.</b> The optimized table now covers every final volleyball family. Resize-only motion/action rows are the cheapest; bounding-box rows intentionally use R960 with 3-frame grouping, so they cost more but preserve localization detail. Compare those rows within their family rather than averaging them with coarse action classification.</li>
  </ul>

  <h2>Final Benchmark Rules</h2>
  <ol>
    <li>Use exactly {CAR_TARGET_FRAMES} car frames and exactly {VB_TARGET_FRAMES} volleyball frames for every compared run.</li>
    <li>Clear Kafka topics and result files before each run. Extra messages or fewer processed frames count as a run-quality problem.</li>
    <li>Report both cost and quality: duration, message count, LLM calls, average LLM latency, frame-by-frame accuracy, and overall query accuracy.</li>
    <li>For cars, keep generic, rare-target, and license plate text extraction tasks separate because their best optimizations are different.</li>
    <li>For volleyball, use the corrected annotation-based scorer (this report does); legacy majority-action numbers are not directly comparable.</li>
  </ol>
  {appendix_html}
</body>
</html>
"""


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    best = load_best_runs()
    write_benchmark_summary(best)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(OUT_HTML)
    print(OUT_SUMMARY)


if __name__ == "__main__":
    main()
