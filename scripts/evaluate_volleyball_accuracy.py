#!/usr/bin/env python3
"""Compute frame-level and clip-level accuracy for every volleyball query result.

Reads volleyball_*.jsonl files under results/logs/ and scores each one against TWO
ground-truth sources from the new full dataset (game 0):

  1. Per-frame multi-label GT — set of all actions any non-lost player performs in a frame
     Source: volleyball_tracking_annotation/_/0/<clip>/<clip>.txt

  2. Per-clip group-activity GT — single team-level event label per clip
     Source: volleyball-detections/0/annotations.txt
     Format per line: <center_frame>.jpg <activity> <player_box1...>
     Activities: r-spike / l-spike / r-set / l-set / r-pass / l-pass / r_winpoint /
                 l_winpoint / r-bspike / l-bspike / r_block / l_block / etc.

The streaming pipeline's built-in action_match_accuracy compares to a majority-voted
per-frame GT (mostly "standing"), so it scores ~0 even when the LLM is correct. This
script ignores that and recomputes against the multi-label GT.

Mapping windows -> clips: the sender (running/Topics/Volleyball/Data/send_volleyball.py)
streams clips in `(path.as_posix(), clip_id)` lexicographic order. We replicate that
exact order so window i (0-indexed) maps to absolute frames [i*20+1 .. i*20+20] which
in turn map to specific clips/frames.

Usage:
    python scripts/evaluate_volleyball_accuracy.py
    python scripts/evaluate_volleyball_accuracy.py --logs-dir results/logs --out report.tsv
    python scripts/evaluate_volleyball_accuracy.py --max-frames 4000  # match the default capped sender run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOGS = REPO_ROOT / "results" / "logs"
DEFAULT_DATASET = REPO_ROOT / "volleyball_dataset"
WINDOW_SIZE = 20  # matches `windowNode("7", "8", "5", "20f")` in queries.js
DEFAULT_MAX_FRAMES = 4000


# -----------------------------------------------------------------------------
# Ground truth loaders
# -----------------------------------------------------------------------------

def load_per_frame_gt(tracking_path: Path) -> dict[int, set[str]]:
    """frame_id -> set of actions any non-lost player performs in that frame."""
    out: dict[int, set[str]] = defaultdict(set)
    if not tracking_path.is_file():
        return out
    for line in tracking_path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 10 or int(parts[6]):  # lost = 1
            continue
        out[int(parts[5])].add(parts[9])
    return out


def load_clip_activities(annotations_path: Path) -> dict[int, str]:
    """clip_id -> group-activity label. clip_id is taken from the file's first column
    (the center-frame .jpg name without extension)."""
    out: dict[int, str] = {}
    if not annotations_path.is_file():
        return out
    for line in annotations_path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            clip_id = int(parts[0].rsplit(".", 1)[0])
        except ValueError:
            continue
        out[clip_id] = parts[1]
    return out


def discover_clips(dataset_root: Path) -> list[tuple[int, Path]]:
    """Replicate send_volleyball.py's clip discovery + ordering. Returns list of
    (clip_id, clip_dir) in the exact order the sender streams them."""
    candidates = [
        dataset_root / "volleyball-detections" / "volleyball-detections",
        dataset_root / "volleyball-detections",
        dataset_root / "videos_sample" / "videos_sample",
        dataset_root / "videos_sample",
    ]
    base = next((c for c in candidates if c.is_dir()), None)
    if base is None:
        raise SystemExit(f"No frames dir found under {dataset_root}")

    clips: list[tuple[int, Path]] = []
    for game_entry in sorted(base.iterdir()):
        if not game_entry.is_dir() or not game_entry.name.isdigit():
            continue
        for entry in game_entry.rglob("*"):
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            if any(f.suffix == ".jpg" and f.is_file() for f in entry.iterdir()):
                clips.append((int(entry.name), entry))
    clips.sort(key=lambda pair: (pair[1].as_posix(), pair[0]))
    return clips


def sorted_jpgs(clip_dir: Path) -> list[int]:
    """Numeric frame ids of jpgs directly inside clip_dir, in send order."""
    return sorted(int(f.stem) for f in clip_dir.iterdir()
                  if f.is_file() and f.suffix == ".jpg" and f.stem.lstrip("-").isdigit())


# -----------------------------------------------------------------------------
# Build absolute-frame -> (clip_id, frame_id, per-frame GT, per-clip GT) index
# -----------------------------------------------------------------------------

def build_frame_index(dataset_root: Path, max_clips: int | None = None, max_frames: int | None = DEFAULT_MAX_FRAMES):
    clips = discover_clips(dataset_root)
    if max_clips is not None:
        clips = clips[:max_clips]
    activities = load_clip_activities(dataset_root / "volleyball-detections" / "0" / "annotations.txt")

    abs_idx_to_info: dict[int, dict] = {}
    used_clips: list[tuple[int, Path]] = []
    abs_idx = 1
    for clip_id, clip_dir in clips:
        if max_frames is not None and abs_idx > max_frames:
            break
        used_this_clip = False
        # Tracking file path — match resolve_tracking_game_dir semantics
        # (game id 0 hardcoded since that's all the new dataset has)
        tracking = (dataset_root / "volleyball_tracking_annotation" /
                    "volleyball_tracking_annotation" / "_" / "0" / str(clip_id) /
                    f"{clip_id}.txt")
        per_frame_gt = load_per_frame_gt(tracking)
        clip_activity = activities.get(clip_id, "")
        for frame_id in sorted_jpgs(clip_dir):
            if max_frames is not None and abs_idx > max_frames:
                break
            abs_idx_to_info[abs_idx] = {
                "clip_id": clip_id,
                "frame_id": frame_id,
                "frame_gt": {a.upper() for a in per_frame_gt.get(frame_id, set())},
                "clip_activity": clip_activity,
            }
            used_this_clip = True
            abs_idx += 1
        if used_this_clip:
            used_clips.append((clip_id, clip_dir))
    return abs_idx_to_info, used_clips, activities


# -----------------------------------------------------------------------------
# Result JSONL loaders + scoring
# -----------------------------------------------------------------------------

ACTION_ALIAS = {
    "SPIKE": "SPIKING", "SPIKING": "SPIKING", "SPIKER": "SPIKING",
    "SET": "SETTING", "SETTING": "SETTING", "SETTER": "SETTING",
    "BLOCK": "BLOCKING", "BLOCKING": "BLOCKING", "BLOCKER": "BLOCKING",
    "DIG": "DIGGING", "DIGGING": "DIGGING", "DIGGER": "DIGGING",
    "MOVE": "MOVING", "MOVING": "MOVING", "MOTION": "MOVING",
    "STAND": "STANDING", "STANDING": "STANDING", "STILL": "STANDING",
    "JUMP": "JUMPING", "JUMPING": "JUMPING",
    "WAIT": "WAITING", "WAITING": "WAITING",
    "FALL": "FALLING", "FALLING": "FALLING",
    "SKIP": "SKIP", "": "SKIP",
}


def normalize_label(label) -> str:
    s = str(label).strip().upper()
    if s in ACTION_ALIAS:
        return ACTION_ALIAS[s]
    for k, v in ACTION_ALIAS.items():
        if k and k in s:
            return v
    return "OTHER"


# clip-level activity tokens that imply each action is happening
# (we map a player-level action to the set of clip activities it could co-occur with)
CLIP_ACTIVITY_FOR_ACTION = {
    "SPIKING": {"r-spike", "l-spike", "r-bspike", "l-bspike", "r_spike", "l_spike"},
    "SETTING": {"r-set", "l-set", "r-bset", "l-bset", "r_set", "l_set"},
    "BLOCKING": {"r-block", "l-block", "r_block", "l_block"},
    "DIGGING": {"r-pass", "l-pass"},  # passing/digging often overlaps
    "MOVING": set(),  # any clip — motion is not an event-level activity
    "STANDING": set(),
    "JUMPING": set(),  # jumping isn't a clip-level activity in this dataset
    "WAITING": set(),
    "FALLING": set(),
}


# Query metadata — same shape as the inline analysis we did earlier
QUERIES = {
    "volleyball_repeated_spikers":   ("class_event", "SPIKING"),
    "volleyball_repeated_setters":   ("class_event", "SETTING"),
    "volleyball_repeated_blockers":  ("class_event", "BLOCKING"),
    "volleyball_repeated_diggers":   ("class_event", "DIGGING"),
    "volleyball_motion_category":    ("categorical", None),
    "volleyball_players_moving":     ("class_event", "MOVING"),
    "volleyball_players_standing":   ("class_event", "STANDING"),
    "volleyball_players_jumping":    ("class_event", "JUMPING"),
    "volleyball_top_actions":        ("topk", None),
    "volleyball_spike_count":        ("class_event", "SPIKING"),
    "volleyball_set_count":          ("class_event", "SETTING"),
    "volleyball_block_count":        ("class_event", "BLOCKING"),
    "volleyball_set_spike":          ("ordered_pair", ("SETTING", "SPIKING")),
    "volleyball_set_block":          ("ordered_pair", ("SETTING", "BLOCKING")),
    "volleyball_dig_set":            ("ordered_pair", ("DIGGING", "SETTING")),
    "volleyball_jump_spike":         ("ordered_pair", ("JUMPING", "SPIKING")),
    "volleyball_bbox_spike":         ("class_event", "SPIKING"),
    "volleyball_bbox_set":           ("class_event", "SETTING"),
    "volleyball_bbox_block":         ("class_event", "BLOCKING"),
    "volleyball_bbox_dig":           ("class_event", "DIGGING"),
}


def score_query(slug, qtype, target, msgs, abs_idx_to_info):
    """Returns (frame_acc%, precision%, recall%, clip_acc%, notes)."""
    correct_emits = total_emits = 0
    target_emits = 0
    target_tp = 0
    target_truth_frames = 0

    # Clip-level scoring: did the LLM detect target on a window whose clip's
    # group-activity is consistent with that target action?
    clip_window_total = 0
    clip_window_correct = 0

    for wi, m in enumerate(msgs):
        # Frames in this window: absolute indices wi*20+1 .. wi*20+20
        win_frames = []
        for f in range(wi * WINDOW_SIZE + 1, (wi + 1) * WINDOW_SIZE + 1):
            info = abs_idx_to_info.get(f)
            if info:
                win_frames.append(info)
        if not win_frames:
            continue
        union_gt = set().union(*(fi["frame_gt"] for fi in win_frames))
        win_clip_activity = win_frames[0]["clip_activity"] if win_frames else ""

        # Per-emission walk
        win_emits = m.get("result", [])
        target_emits_w = 0
        target_truth_w = 0
        if isinstance(target, str):
            target_truth_w = sum(1 for fi in win_frames if target in fi["frame_gt"])
            target_truth_frames += target_truth_w

        any_target_emit = False
        for entry in win_emits:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            label = normalize_label(entry[0])
            cnt = entry[1] if isinstance(entry[1], (int, float)) else 1
            total_emits += cnt
            if label == "SKIP":
                # SKIP correct on frames where the target action is absent
                if isinstance(target, str):
                    skip_correct = sum(1 for fi in win_frames if target not in fi["frame_gt"])
                else:
                    skip_correct = sum(1 for fi in win_frames if not fi["frame_gt"])
                correct_emits += min(cnt, skip_correct)
            else:
                if label in union_gt:
                    correct_emits += cnt
                if isinstance(target, str) and label == target:
                    target_emits_w += cnt
                    any_target_emit = True

        target_emits += target_emits_w
        target_tp += min(target_emits_w, target_truth_w)

        # Clip-level scoring: only meaningful for class_event queries with a known
        # mapping from action → clip activity. Score per window:
        #   - "expected fire": clip activity is in CLIP_ACTIVITY_FOR_ACTION[target]
        #   - "actual fire": LLM emitted target at least once in the window
        if isinstance(target, str) and target in CLIP_ACTIVITY_FOR_ACTION:
            target_activities = CLIP_ACTIVITY_FOR_ACTION[target]
            if target_activities:  # only score when the action has a clip-level proxy
                clip_window_total += 1
                expected_fire = win_clip_activity in target_activities
                if expected_fire == any_target_emit:
                    clip_window_correct += 1

    frame_acc = 100 * correct_emits / total_emits if total_emits else 0
    if isinstance(target, str):
        precision = 100 * target_tp / target_emits if target_emits else 0
        recall = 100 * target_tp / target_truth_frames if target_truth_frames else 0
        notes = f"TP={target_tp}/{target_emits} emit, gt={target_truth_frames}fr"
    elif qtype == "ordered_pair":
        first, second = target
        emitted = sum(int(m.get("sequence", {}).get("ordered_pairs", 0)) for m in msgs
                      if isinstance(m.get("sequence"), dict))
        # Did GT have any frame containing both first and second?
        gt_in_same_frame = False
        for wi in range(len(msgs)):
            for f in range(wi * WINDOW_SIZE + 1, (wi + 1) * WINDOW_SIZE + 1):
                info = abs_idx_to_info.get(f)
                if info and first in info["frame_gt"] and second in info["frame_gt"]:
                    gt_in_same_frame = True
                    break
        precision = recall = float("nan")
        notes = f"pairs_emitted={emitted}, gt_in_same_frame={gt_in_same_frame}"
    else:
        precision = recall = float("nan")
        notes = qtype

    clip_acc = 100 * clip_window_correct / clip_window_total if clip_window_total else float("nan")

    return frame_acc, precision, recall, clip_acc, notes


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def fmt(v, suffix=""):
    if isinstance(v, float):
        if v != v:  # nan
            return "  N/A"
        return f"{v:>5.2f}{suffix}"
    return f"{v!s:>5}{suffix}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs-dir", default=str(DEFAULT_LOGS))
    ap.add_argument("--dataset-root", default=str(DEFAULT_DATASET))
    ap.add_argument("--max-clips", type=int, default=None,
                    help="Use only the first N clips of the send order (matches a sender run with VOLLEYBALL_MAX_CLIPS=N)")
    ap.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES,
                    help=f"Use only the first N frames of the send order (default: {DEFAULT_MAX_FRAMES}; use 0 for no cap)")
    ap.add_argument("--out", default=None, help="Write TSV summary here (default: stdout only)")
    args = ap.parse_args()

    logs_dir = Path(args.logs_dir).resolve()
    dataset_root = Path(args.dataset_root).resolve()

    max_frames = None if args.max_frames <= 0 else args.max_frames
    abs_idx_to_info, clips, activities = build_frame_index(dataset_root, args.max_clips, max_frames)
    print(f"Indexed {len(abs_idx_to_info)} frames across {len(clips)} clips "
          f"({sum(1 for v in abs_idx_to_info.values() if v['frame_gt'])} with per-frame GT, "
          f"{sum(1 for v in abs_idx_to_info.values() if v['clip_activity'])} with clip GT)")
    if activities:
        cnt = Counter(a for a in activities.values())
        print(f"Clip activities distribution: {dict(cnt)}")
    print()

    rows = []
    header = f"{'#':<2} {'QUERY':<32} {'wins':>4} {'frame_acc%':>10} {'prec%':>6} {'rec%':>6} {'clip_acc%':>9}  notes"
    print(header)
    print("-" * len(header))

    for i, (slug, (qtype, target)) in enumerate(QUERIES.items(), 1):
        path = logs_dir / f"{slug}.jsonl"
        if not path.exists() or path.stat().st_size == 0:
            print(f"{i:<2} {slug:<32} {0:>4} {fmt(0.0)}  {fmt(0.0)}  {fmt(0.0)}  {fmt(0.0)}   no data")
            rows.append((i, slug, 0, 0, 0, 0, 0, "no data"))
            continue
        msgs = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msgs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        if not msgs:
            print(f"{i:<2} {slug:<32} {0:>4} {fmt(0.0)}  {fmt(0.0)}  {fmt(0.0)}  {fmt(0.0)}   empty")
            continue

        # Cap windows to whatever the frame index supports
        n_total = len(msgs)
        max_wins_supported = max(1, len(abs_idx_to_info) // WINDOW_SIZE)
        msgs_used = msgs[:max_wins_supported]

        frame_acc, prec, rec, clip_acc, notes = score_query(slug, qtype, target, msgs_used, abs_idx_to_info)
        cap_str = f" [file:{n_total}w used {len(msgs_used)}]" if n_total != len(msgs_used) else ""
        print(f"{i:<2} {slug:<32} {len(msgs_used):>4} {fmt(frame_acc)}  {fmt(prec)}  {fmt(rec)}  {fmt(clip_acc)}   {notes}{cap_str}")
        rows.append((i, slug, len(msgs_used), frame_acc, prec, rec, clip_acc, notes))

    print()
    print("Definitions:")
    print("  frame_acc% — % of LLM emissions that match per-frame multi-label GT (any-player union)")
    print("               SKIP is correct on frames where target action is absent")
    print("  prec%      — TP / target-emissions (when LLM said target, it was actually in GT)")
    print("  rec%       — TP / target-truth-frames (fraction of target frames the LLM hit)")
    print("  clip_acc%  — fraction of windows where (LLM detected target) == (clip activity implies target)")
    print("               only computed for class_event queries with a clip-activity mapping")

    if args.out:
        out_path = Path(args.out).resolve()
        with open(out_path, "w") as f:
            f.write("#\tquery\twins\tframe_acc%\tprecision%\trecall%\tclip_acc%\tnotes\n")
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
        print(f"\nWrote TSV: {out_path}")


if __name__ == "__main__":
    main()
