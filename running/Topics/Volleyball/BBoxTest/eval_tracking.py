"""
Evaluate whether a VLM can localize all players in a volleyball frame well
enough to drive a tracker.

Supports two modes:
  --batch-size 1 : one frame per LLM call (single-image path)
  --batch-size N : group N sequential frames per clip into one multi-image call,
                   mirroring production's frame_batcher -> llm pipeline
                   (queries.js:84-88 + 713-972, MapFrameBatcher in
                    Methodtemplates.js:455-500, send_to_vllm_multi in
                    llm_call.py:222-252). Predictions from the single batched
                    response are scored against the GT of the LAST frame in
                    the batch.

Usage:
    # single-frame (backward-compat smoke)
    python eval_tracking.py --batch-size 1 --limit 10 --out-results tracking_single.json

    # production-shaped (batch=4)
    python eval_tracking.py --batch-size 4 --limit 16 --out-results tracking_batch4.json

    # production-shaped AND production token budget (shows truncation effect)
    python eval_tracking.py --batch-size 4 --max-tokens 50 --limit 16 --out-results tracking_prod50.json
"""
import argparse
import base64
import json
import re
import struct
import time
from pathlib import Path
from statistics import mean, median

import requests


HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
BBOX_RE = re.compile(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")

DEFAULT_VLLM_SERVER = "http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"
DEFAULT_OLLAMA_SERVER = "http://localhost:11434"

PROMPT_TEMPLATE = (
    "Each image is {w} pixels wide and {h} pixels tall. "
    "List bounding boxes for every volleyball player visible. "
    "Return one bounding box per line as 'x1,y1,x2,y2' with pixel integers "
    "in image coordinates (0 <= x <= {w}, 0 <= y <= {h}). "
    "If no players are visible, return SKIP.\n\n"
    "Do not provide any text or any explanation."
)


def jpeg_dims(path: Path):
    """Parse width/height from a JPEG's SOF marker. No PIL dep."""
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError(f"Not a JPEG: {path}")
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            # Skip any fill bytes (0xFF padding)
            marker = f.read(1)
            while marker == b"\xff":
                marker = f.read(1)
            if not marker:
                raise ValueError(f"Unexpected EOF in {path}")
            m = marker[0]
            # SOF0..SOF15 excluding DHT(C4), JPG(C8), DAC(CC)
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                f.read(3)  # segment length (2) + precision (1)
                h, w = struct.unpack(">HH", f.read(4))
                return w, h
            # Skip non-SOF segment
            seg_len = struct.unpack(">H", f.read(2))[0]
            f.read(seg_len - 2)


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


def parse_all_bboxes(text: str):
    """Extract every 4-int sequence from the response as a candidate bbox."""
    boxes = []
    for m in BBOX_RE.finditer(text):
        x1, y1, x2, y2 = (int(x) for x in m.groups())
        # Normalize so x1<=x2, y1<=y2; discard degenerate boxes
        xa, xb = sorted((x1, x2))
        ya, yb = sorted((y1, y2))
        if xb - xa < 2 or yb - ya < 2:
            continue
        boxes.append([xa, ya, xb, yb])
    # De-duplicate exact repeats
    seen, out = set(), []
    for b in boxes:
        t = tuple(b)
        if t in seen:
            continue
        seen.add(t)
        out.append(b)
    return out


def greedy_match(preds, gts, iou_thr):
    """Greedy IoU matching. Returns list of (pred_idx, gt_idx, iou) for matches
    with iou >= iou_thr. Each pred and each gt can match at most once."""
    pairs = []
    for i, p in enumerate(preds):
        for j, g in enumerate(gts):
            pairs.append((iou(p, g), i, j))
    pairs.sort(reverse=True)
    used_p, used_g = set(), set()
    matches = []
    for v, i, j in pairs:
        if v < iou_thr:
            break
        if i in used_p or j in used_g:
            continue
        matches.append((i, j, v))
        used_p.add(i)
        used_g.add(j)
    return matches


def call_vllm(server, model, img_b64, prompt, timeout, max_tokens):
    r = requests.post(
        f"{server.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                ],
            }],
            "max_tokens": max_tokens,
            "temperature": 0,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def call_ollama(host, model, img_b64, prompt, timeout, max_tokens):
    r = requests.post(
        f"{host.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def call_vllm_multi(server, model, img_b64_list, prompt, timeout, max_tokens):
    """Mirror send_to_vllm_multi in llm_call.py:222-252: single user message,
    text followed by one image_url content item per frame."""
    content = [{"type": "text", "text": prompt}]
    for b in img_b64_list:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
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


def call_ollama_multi(host, model, img_b64_list, prompt, timeout, max_tokens):
    r = requests.post(
        f"{host.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": list(img_b64_list)}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def chunk_by_clip(entries, batch_size):
    """Yield lists of up to batch_size consecutive entries, never crossing a
    (game, clip) boundary. Assumes entries are already ordered by clip+frame."""
    batch, key = [], None
    for e in entries:
        k = (e["game"], e["clip"])
        if k != key or len(batch) == batch_size:
            if batch:
                yield batch
            batch = []
            key = k
        batch.append(e)
    if batch:
        yield batch


def resolve_image(raw: str, image_root: Path) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else image_root / raw


def score(preds, gts, iou_thr):
    matches = greedy_match(preds, gts, iou_thr)
    prec = len(matches) / len(preds) if preds else 0.0
    recall = len(matches) / len(gts) if gts else 0.0
    f1 = (2 * prec * recall / (prec + recall)) if (prec + recall) else 0.0
    # Threshold-free overlap metrics (average, not filtered by 0.5)
    pred_overlaps = [max((iou(p, g) for g in gts), default=0.0) for p in preds]
    gt_coverages  = [max((iou(p, g) for p in preds), default=0.0) for g in gts]
    mean_pred_overlap = mean(pred_overlaps) if pred_overlaps else 0.0
    mean_gt_coverage  = mean(gt_coverages)  if gt_coverages  else 0.0
    # Back-compat: mean best-IoU among preds that have ANY overlap
    best_ious = [mx for mx in pred_overlaps if mx > 0]
    mean_best = mean(best_ious) if best_ious else 0.0
    return matches, prec, recall, f1, mean_best, mean_pred_overlap, mean_gt_coverage


def run(args):
    manifest = json.loads(Path(args.manifest).read_text())
    entries = manifest["entries"]
    if args.limit:
        entries = entries[:args.limit]
    image_root = Path(args.image_root).resolve() if args.image_root else REPO_ROOT
    server = args.server or (DEFAULT_VLLM_SERVER if args.backend == "vllm" else DEFAULT_OLLAMA_SERVER)

    batched = args.batch_size > 1
    if batched:
        batches = [b for b in chunk_by_clip(entries, args.batch_size)]
        n_calls = len(batches)
        print(f"Batched mode: batch_size={args.batch_size}, "
              f"{len(entries)} frames -> {n_calls} LLM calls")
    else:
        batches = [[e] for e in entries]
        n_calls = len(batches)
        print(f"Single-frame mode: {n_calls} LLM calls")
    print(f"Target: {args.backend}:{args.model} @ {server}  (max_tokens={args.max_tokens})")

    results = []
    for k, batch in enumerate(batches, 1):
        # Load all images in the batch
        img_b64_list, missing = [], False
        for e in batch:
            p = resolve_image(e["image"], image_root)
            if not p.is_file():
                print(f"[{k}/{n_calls}] MISS: {p}")
                missing = True
                break
            img_b64_list.append(base64.b64encode(p.read_bytes()).decode())
        if missing:
            continue

        # Build a dims-aware prompt using the target (last) frame's size.
        # In this dataset clips are uniform (1280x720), so one dim fits the whole batch.
        target_path = resolve_image(batch[-1]["image"], image_root)
        try:
            w, h = jpeg_dims(target_path)
        except Exception:
            w, h = 1280, 720  # safe fallback for volleyball dataset
        prompt = args.prompt_template.format(w=w, h=h)
        t0 = time.time()
        try:
            if batched:
                if args.backend == "vllm":
                    text = call_vllm_multi(server, args.model, img_b64_list, prompt, args.timeout, args.max_tokens)
                else:
                    text = call_ollama_multi(server, args.model, img_b64_list, prompt, args.timeout, args.max_tokens)
            else:
                if args.backend == "vllm":
                    text = call_vllm(server, args.model, img_b64_list[0], prompt, args.timeout, args.max_tokens)
                else:
                    text = call_ollama(server, args.model, img_b64_list[0], prompt, args.timeout, args.max_tokens)
        except Exception as ex:
            text = f"__REQUEST_ERROR__: {ex}"
        dt = time.time() - t0

        preds = parse_all_bboxes(text)
        # Score against the LAST frame's GT (most recent = tracker's "current state")
        target = batch[-1]
        gts = target["gt_bboxes"]
        matches, prec, recall, f1, mean_best, pred_overlap, gt_coverage = score(preds, gts, args.iou_thr)

        frame_ids = [e["frame_id"] for e in batch]
        results.append({
            "id": target["id"],
            "batch_frames": frame_ids,
            "batch_size": len(batch),
            "game": target["game"],
            "clip": target["clip"],
            "target_frame_id": target["frame_id"],
            "image_dims": [w, h],
            "n_gt": len(gts),
            "n_pred": len(preds),
            "matches": len(matches),
            "precision": prec,
            "recall": recall,
            "f1": f1,
            "mean_best_iou": mean_best,
            "mean_pred_overlap": pred_overlap,
            "mean_gt_coverage": gt_coverage,
            "response": text,
            "pred_bboxes": preds,
            "gt_bboxes": gts,
            "latency_s": round(dt, 3),
        })
        if k % 5 == 0 or k == n_calls:
            fr_tag = f"[{frame_ids[0]}..{frame_ids[-1]}]" if batched else f"f{frame_ids[0]}"
            print(f"[{k}/{n_calls}] g{target['game']}_c{target['clip']} {fr_tag:18s} "
                  f"gt={len(gts):2d} pred={len(preds):2d} match={len(matches):2d} "
                  f"P={prec:.2f} R={recall:.2f} F1={f1:.2f} ({dt:.1f}s)")

    if args.out_results:
        Path(args.out_results).write_text(json.dumps(results, indent=2))
        print(f"\nPer-batch results -> {args.out_results}")

    if not results:
        return

    total_gt = sum(r["n_gt"] for r in results)
    total_pred = sum(r["n_pred"] for r in results)
    total_match = sum(r["matches"] for r in results)
    micro_p = total_match / total_pred if total_pred else 0.0
    micro_r = total_match / total_gt if total_gt else 0.0
    micro_f1 = (2*micro_p*micro_r / (micro_p+micro_r)) if (micro_p+micro_r) else 0.0
    macro_p = mean(r["precision"] for r in results)
    macro_r = mean(r["recall"] for r in results)
    macro_f1 = mean(r["f1"] for r in results)
    count_err = [r["n_pred"] - r["n_gt"] for r in results]
    count_abs = [abs(x) for x in count_err]

    unit = "batches" if args.batch_size > 1 else "frames"
    print(f"\n=== Summary (n={len(results)} {unit}, IoU>={args.iou_thr}) ===")
    print(f"Total GT boxes (target-frame only): {total_gt}")
    print(f"Total predicted                    : {total_pred}")
    print(f"Total matched                      : {total_match}")
    print(f"\nMicro-avg (pooled): P={micro_p:.3f}  R={micro_r:.3f}  F1={micro_f1:.3f}")
    print(f"Macro-avg (per-{unit[:-2]}{unit[-1]} mean): P={macro_p:.3f}  R={macro_r:.3f}  F1={macro_f1:.3f}")
    print(f"\nCount accuracy: mean(|pred - gt|)={mean(count_abs):.2f}  "
          f"median={median(count_abs)}  mean(pred - gt)={mean(count_err):+.2f}")
    all_mean_iou = [r["mean_best_iou"] for r in results if r["mean_best_iou"] > 0]
    if all_mean_iou:
        print(f"Mean best-IoU on {unit} with any match: {mean(all_mean_iou):.3f}")

    # Threshold-free overlap metrics -- answer "how well do the boxes overlap?"
    # independent of the 0.5 cutoff.
    pred_overlaps = [r["mean_pred_overlap"] for r in results]
    gt_coverages  = [r["mean_gt_coverage"]  for r in results]
    print(f"\n=== Overlap (no IoU threshold) ===")
    print(f"Mean pred_overlap (per pred, max-IoU vs any GT): {mean(pred_overlaps):.3f}")
    print(f"Mean gt_coverage  (per GT,   max-IoU vs any pred): {mean(gt_coverages):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(HERE / "tracking_manifest.json"))
    ap.add_argument("--backend", choices=["vllm", "ollama"], default="vllm")
    ap.add_argument("--model", default="RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8")
    ap.add_argument("--server", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--iou-thr", type=float, default=0.5)
    ap.add_argument("--batch-size", type=int, default=4,
                    help="Number of frames per LLM call. 1 = single-image path; "
                         ">1 = multi-image path (production uses 4).")
    ap.add_argument("--max-tokens", type=int, default=500,
                    help="Headroom for ~4 frames x ~10 players. Production uses 50 "
                         "which truncates; pass --max-tokens 50 to measure that effect.")
    ap.add_argument("--prompt-template", default=PROMPT_TEMPLATE,
                    help="Python format string; {w}, {h} are filled with image dims "
                         "read from the target frame's JPEG header.")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--out-results", default=None)
    ap.add_argument("--image-root", default=None)
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
