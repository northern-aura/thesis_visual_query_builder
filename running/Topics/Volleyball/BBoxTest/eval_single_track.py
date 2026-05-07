"""
Single-player tracking test for Qwen2.5-VL.

Question: given an anchor (frame 0 + bbox), can the model follow the same
player across subsequent frames?

For each player we pick a starting frame (anchor) and N-1 query frames. Every
query call sends TWO images -- the anchor and the query frame -- plus the
anchor's bbox in text. We ask for the same player's bbox in the query frame
and score per-frame IoU against the VATIC tracking annotation.

This differs from eval_tracking.py, which asks the model to enumerate EVERY
player (multi-target detection). Here the model gets one target and has to
re-localize it. Fixed-anchor (non-drifting) scoring keeps errors independent.

Example:
    python running/Topics/Volleyball/BBoxTest/eval_single_track.py \
        --max-players 4 --seq-len 10 --out tracking_single_target.json
"""
import argparse
import base64
import json
import re
import time
from io import BytesIO
from pathlib import Path

import requests


HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
BBOX_RE = re.compile(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")

DEFAULT_VLLM_SERVER = "http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"
DEFAULT_MODEL = "RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8"

ANCHOR_LABEL = (
    "IMAGE 1 (reference frame, {w}x{h} pixels): one specific volleyball player "
    "has bounding box {x1},{y1},{x2},{y2} (pixel integers, top-left origin). "
    "Study this player's appearance and position."
)

QUERY_LABEL = (
    "IMAGE 2 (query frame, {w}x{h} pixels): a later frame from the same video, "
    "same camera angle. The same player IS present."
)

TASK_TEXT = (
    "Task: return the bounding box of that SAME player in IMAGE 2, as "
    "'x1,y1,x2,y2' with pixel integers (0 <= x <= {w}, 0 <= y <= {h}). "
    "Output the four numbers only. No explanation, no labels, no other text."
)

ANCHOR_LABEL_VISUAL = (
    "IMAGE 1 (reference): a single volleyball player, cropped from an "
    "earlier frame of this video. Study this player's appearance."
)

QUERY_LABEL_VISUAL = (
    "IMAGE 2 (query frame, {w}x{h} pixels): a later frame from the same "
    "video, same camera angle. The same player IS present."
)

TASK_TEXT_VISUAL = (
    "Task: return the bounding box of the player from IMAGE 1 as seen in "
    "IMAGE 2, as 'x1,y1,x2,y2' with pixel integers (0 <= x <= {w}, "
    "0 <= y <= {h}). Output the four numbers only. No explanation."
)

JERSEY_PROMPT = (
    "This is a frame from a volleyball match ({w} pixels wide, {h} pixels tall). "
    "Return the bounding box of the player wearing jersey number {n} "
    "as 'x1,y1,x2,y2' with pixel integers (0 <= x <= {w}, 0 <= y <= {h}). "
    "If that player is not visible, return SKIP. "
    "Output the four numbers only. No explanation."
)


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    aw, ah = max(0, ax2 - ax1), max(0, ay2 - ay1)
    bw, bh = max(0, bx2 - bx1), max(0, by2 - by1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def parse_bbox(text):
    s = text.strip()
    m = BBOX_RE.search(s)
    if m:
        return [int(x) for x in m.groups()], "bbox"
    if "SKIP" in s.upper():
        return None, "skip"
    return None, "parse_error"


def jpeg_dims(path: Path):
    """Parse width/height from JPEG SOF marker. No PIL dep."""
    with path.open("rb") as f:
        data = f.read()
    i = 2  # skip SOI
    while i < len(data):
        if data[i] != 0xFF:
            return None, None
        marker = data[i + 1]
        i += 2
        # SOF0..SOF15 excluding DHT (C4), JPG (C8), DAC (CC)
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = (data[i + 3] << 8) | data[i + 4]
            w = (data[i + 5] << 8) | data[i + 6]
            return w, h
        # segments with no length
        if marker in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9):
            continue
        seg_len = (data[i] << 8) | data[i + 1]
        i += seg_len
    return None, None


def crop_to_b64(img_path: Path, bbox, pad: int = 0) -> str:
    """Crop img_path to bbox (with optional padding) and return a base64 JPEG."""
    from PIL import Image  # lazy: only needed in --visual-anchor mode
    img = Image.open(img_path).convert("RGB")
    W, H = img.size
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(W, x2 + pad)
    y2 = min(H, y2 + pad)
    crop = img.crop((x1, y1, x2, y2))
    buf = BytesIO()
    crop.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def load_tracks(path: Path):
    """Return {player_id: [(frame_id, bbox, lost, action), ...]} sorted by frame_id."""
    tracks = {}
    with path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            pid = int(parts[0])
            bbox = [int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])]
            fid = int(parts[5])
            lost = int(parts[6])
            action = parts[9]
            tracks.setdefault(pid, []).append((fid, bbox, lost, action))
    for pid in tracks:
        tracks[pid].sort()
    return tracks


def pick_sequences(tracks, clip_dir: Path, seq_len: int, max_players: int):
    """For each player: longest contiguous run of non-lost frames whose JPGs exist,
    capped at seq_len. Return [(pid, [(fid, bbox, action), ...]), ...]."""
    out = []
    for pid, rows in tracks.items():
        run, best = [], []
        for fid, bbox, lost, action in rows:
            if lost == 0 and (clip_dir / f"{fid}.jpg").is_file():
                run.append((fid, bbox, action))
                if len(run) > len(best):
                    best = list(run)
            else:
                run = []
        if len(best) >= seq_len:
            out.append((pid, best[:seq_len]))
    out.sort(key=lambda x: x[0])
    if max_players:
        out = out[:max_players]
    return out


def call_vllm_labeled(server, model, parts, timeout, max_tokens):
    """parts: list of ('text', str) or ('image', b64) tuples, sent in order."""
    content = []
    for kind, value in parts:
        if kind == "text":
            content.append({"type": "text", "text": value})
        else:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{value}"},
            })
    r = requests.post(
        f"{server.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": 0,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def frames_with_jpgs(tracks, clip_dir: Path, seq_len: int):
    """Pick frames that have JPGs on disk, in order. All players' rows live at
    the same frame grid, so we pull frame IDs from any player's entries."""
    if not tracks:
        return []
    any_pid = next(iter(tracks))
    fids = []
    for fid, _, _, _ in tracks[any_pid]:
        if (clip_dir / f"{fid}.jpg").is_file():
            fids.append(fid)
        if len(fids) >= seq_len:
            break
    return fids


def best_matching_player(pred, frame_rows):
    """Find which GT player the predicted bbox overlaps most with.
    frame_rows: list of (pid, bbox, lost, action). Returns (pid, bbox, iou) or None."""
    best = (None, None, 0.0)
    for pid, bbox, lost, _ in frame_rows:
        if lost:
            continue
        ov = iou(pred, bbox)
        if ov > best[2]:
            best = (pid, bbox, ov)
    return best if best[0] is not None else None


def run_jersey(args):
    track_path = Path(args.track_file).resolve()
    clip_dir = Path(args.clip_dir).resolve()
    tracks = load_tracks(track_path)
    fids = frames_with_jpgs(tracks, clip_dir, args.seq_len)

    # Rebuild "rows by frame" so we can find best-matching player per frame.
    rows_by_frame = {}
    for pid, entries in tracks.items():
        for fid, bbox, lost, action in entries:
            rows_by_frame.setdefault(fid, []).append((pid, bbox, lost, action))

    print(f"Clip: {clip_dir}")
    print(f"Mode: jersey={args.jersey}")
    print(f"Querying {len(fids)} frames, one call per frame\n")

    track_records = []
    t_total = time.time()
    for fid in fids:
        img_path = clip_dir / f"{fid}.jpg"
        w, h = jpeg_dims(img_path)
        img_b64 = base64.b64encode(img_path.read_bytes()).decode()
        prompt = JERSEY_PROMPT.format(w=w, h=h, n=args.jersey)
        parts = [("text", prompt), ("image", img_b64)]
        t0 = time.time()
        try:
            text = call_vllm_labeled(args.server, args.model, parts,
                                     args.timeout, args.max_tokens)
        except Exception as ex:
            text = f"__REQUEST_ERROR__: {ex}"
        dt = time.time() - t0
        pred, kind = parse_bbox(text)

        match = best_matching_player(pred, rows_by_frame.get(fid, [])) if pred else None
        matched_pid = match[0] if match else None
        matched_iou = match[2] if match else None

        track_records.append({
            "frame_id": fid,
            "pred_bbox": pred,
            "parsed_kind": kind,
            "matched_pid": matched_pid,
            "matched_iou": matched_iou,
            "response": text,
            "latency_s": round(dt, 3),
        })
        tag = f"pid={matched_pid} iou={matched_iou:.2f}" if match else kind
        print(f"  f={fid}  {tag:24s}  pred={pred}  ({dt:.1f}s)")
        if args.debug:
            print(f"    raw: {text!r}")

    # Consistency: did the model lock onto one player?
    pid_counts = {}
    for r in track_records:
        if r["matched_pid"] is not None:
            pid_counts[r["matched_pid"]] = pid_counts.get(r["matched_pid"], 0) + 1
    n_bbox = sum(1 for r in track_records if r["parsed_kind"] == "bbox")
    n_skip = sum(1 for r in track_records if r["parsed_kind"] == "skip")
    n_err = sum(1 for r in track_records if r["parsed_kind"] == "parse_error")

    print("\n" + "=" * 60)
    print(f"Jersey #{args.jersey}: {n_bbox} bbox / {n_skip} skip / {n_err} err "
          f"across {len(track_records)} frames  wall={time.time() - t_total:.1f}s")
    if pid_counts:
        ranked = sorted(pid_counts.items(), key=lambda x: -x[1])
        top_pid, top_n = ranked[0]
        print(f"Most-matched player_id = {top_pid} ({top_n}/{n_bbox} frames = "
              f"{top_n / n_bbox:.0%} consistency)")
        print(f"All matches: {dict(ranked)}")
        matched_ious = [r["matched_iou"] for r in track_records
                        if r["matched_pid"] == top_pid]
        print(f"Mean IoU on top-pid frames: {sum(matched_ious) / len(matched_ious):.2f}")
    else:
        print("No valid bbox predictions — model returned SKIP or parse errors.")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "jersey": args.jersey,
            "clip": str(clip_dir),
            "records": track_records,
            "pid_counts": pid_counts,
        }, indent=2))
        print(f"Wrote {args.out}")


def summarize_track(track_records, seq_len):
    ious = [r["iou"] for r in track_records if r["iou"] is not None]
    skips = sum(1 for r in track_records if r["parsed_kind"] == "skip")
    errs = sum(1 for r in track_records if r["parsed_kind"] == "parse_error")
    mean_iou = sum(ious) / len(ious) if ious else 0.0
    var = sum((x - mean_iou) ** 2 for x in ious) / len(ious) if ious else 0.0
    std = var ** 0.5
    n_queries = seq_len - 1
    at_50 = sum(1 for x in ious if x >= 0.5) / n_queries if n_queries else 0.0
    return mean_iou, std, at_50, skips, errs


def run(args):
    track_path = Path(args.track_file).resolve()
    clip_dir = Path(args.clip_dir).resolve()
    tracks = load_tracks(track_path)
    sequences = pick_sequences(tracks, clip_dir, args.seq_len, args.max_players)

    mode = f"visual_anchor (pad={args.crop_pad})" if args.visual_anchor else "text_anchor"
    print(f"Clip: {clip_dir}")
    print(f"Mode: {mode}")
    print(f"Testing {len(sequences)} players x {args.seq_len} frames each")
    print(f"Anchor = first non-lost frame, queries = next {args.seq_len - 1} frames\n")

    results = []
    t_total = time.time()
    for pid, frames in sequences:
        anchor_fid, anchor_bbox, anchor_action = frames[0]
        anchor_path = clip_dir / f"{anchor_fid}.jpg"
        w, h = jpeg_dims(anchor_path)
        if args.visual_anchor:
            anchor_b64 = crop_to_b64(anchor_path, anchor_bbox, pad=args.crop_pad)
            anchor_label = ANCHOR_LABEL_VISUAL
            query_label_tpl = QUERY_LABEL_VISUAL
            task_text = TASK_TEXT_VISUAL.format(w=w, h=h)
        else:
            anchor_b64 = base64.b64encode(anchor_path.read_bytes()).decode()
            anchor_label = ANCHOR_LABEL.format(
                w=w, h=h,
                x1=anchor_bbox[0], y1=anchor_bbox[1],
                x2=anchor_bbox[2], y2=anchor_bbox[3],
            )
            query_label_tpl = QUERY_LABEL
            task_text = TASK_TEXT.format(w=w, h=h)

        print(f"--- player {pid} (anchor_fid={anchor_fid}, action={anchor_action}, "
              f"anchor_bbox={anchor_bbox}) ---")
        track_records = []
        for fid, gt_bbox, action in frames[1:]:
            img_path = clip_dir / f"{fid}.jpg"
            query_b64 = base64.b64encode(img_path.read_bytes()).decode()
            query_label = query_label_tpl.format(w=w, h=h)
            parts = [
                ("text", anchor_label),
                ("image", anchor_b64),
                ("text", query_label),
                ("image", query_b64),
                ("text", task_text),
            ]
            t0 = time.time()
            try:
                text = call_vllm_labeled(args.server, args.model, parts,
                                         args.timeout, args.max_tokens)
            except Exception as ex:
                text = f"__REQUEST_ERROR__: {ex}"
            dt = time.time() - t0
            pred, kind = parse_bbox(text)
            score = iou(pred, gt_bbox) if pred else None
            track_records.append({
                "frame_id": fid,
                "action": action,
                "gt_bbox": gt_bbox,
                "pred_bbox": pred,
                "iou": score,
                "parsed_kind": kind,
                "response": text,
                "latency_s": round(dt, 3),
            })
            tag = f"iou={score:.2f}" if score is not None else kind
            print(f"  f={fid}  {tag:14s}  pred={pred} gt={gt_bbox}  ({dt:.1f}s)")
            if args.debug:
                print(f"    raw: {text!r}")

        mean_iou, std, at_50, skips, errs = summarize_track(track_records, args.seq_len)
        print(f"  -> mean_iou={mean_iou:.2f}  std={std:.2f}  IoU>=0.5={at_50:.1%}  "
              f"skips={skips}  parse_err={errs}\n")

        results.append({
            "player_id": pid,
            "anchor_frame": anchor_fid,
            "anchor_bbox": anchor_bbox,
            "anchor_action": anchor_action,
            "image_dims": [w, h],
            "mode": "visual_anchor" if args.visual_anchor else "text_anchor",
            "crop_pad": args.crop_pad if args.visual_anchor else None,
            "track": track_records,
            "summary": {
                "mean_iou": mean_iou, "std": std,
                "iou_at_50": at_50, "skips": skips, "parse_err": errs,
            },
        })

    # overall
    print("=" * 60)
    all_ious = [r["iou"] for res in results for r in res["track"] if r["iou"] is not None]
    if all_ious:
        overall_mean = sum(all_ious) / len(all_ious)
        print(f"OVERALL  mean_iou={overall_mean:.2f}  "
              f"IoU>=0.5={sum(1 for x in all_ious if x >= 0.5) / len(all_ious):.1%}  "
              f"n={len(all_ious)}  wall={time.time() - t_total:.1f}s")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2))
        print(f"Wrote {args.out}")


def main():
    default_track = REPO_ROOT / "volleyball_dataset" / "volleyball_tracking_annotation" \
        / "volleyball_tracking_annotation" / "_" / "7" / "51725" / "51725.txt"
    default_clip = REPO_ROOT / "volleyball_dataset" / "videos_sample" \
        / "videos_sample" / "7" / "51725"

    ap = argparse.ArgumentParser()
    ap.add_argument("--track-file", default=str(default_track))
    ap.add_argument("--clip-dir", default=str(default_clip))
    ap.add_argument("--seq-len", type=int, default=10,
                    help="frames per player: 1 anchor + (seq_len-1) queries")
    ap.add_argument("--max-players", type=int, default=4)
    ap.add_argument("--server", default=DEFAULT_VLLM_SERVER)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--max-tokens", type=int, default=80)
    ap.add_argument("--visual-anchor", action="store_true",
                    help="send a cropped image of the anchor player instead of bbox coords in text")
    ap.add_argument("--crop-pad", type=int, default=0,
                    help="pixels of context around the anchor bbox crop (visual-anchor mode only)")
    ap.add_argument("--jersey", type=int, default=None,
                    help="jersey number to track; enables single-image jersey-anchor mode")
    ap.add_argument("--debug", action="store_true",
                    help="print raw model responses for each query")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.jersey is not None:
        run_jersey(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
