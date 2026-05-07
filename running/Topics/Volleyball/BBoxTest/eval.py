"""
Evaluate a VLM on the volleyball bbox test set built by build_testset.py.

Self-contained HTTP calls (no llm_call.py dep) so you can point it at any
local Ollama / vLLM server.

Defaults mirror the production pipeline exactly (see Methodtemplates.js:179-180,
llm_call.py:98-129): vLLM at the DM-lab DGX server, model
RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8, max_tokens=50, temperature=0.

Note: the UI subtype label "qwen2.5-vl-3b" is a misnomer -- the served model is
the 7B quantized variant. Test results reflect that 7B model, not a 3B.

Examples:
    # Mirror the production pipeline exactly (default)
    python eval.py

    # Override server (tunneling, local vLLM, etc.)
    python eval.py --server http://localhost:8000

    # Quick smoke test (5 pos + 5 neg per class)
    python eval.py --limit-per-class 5 --out-results smoke.json

    # Fall back to Ollama to compare against other VLMs
    python eval.py --backend ollama --model qwen2.5vl:3b --server http://localhost:11434

Metrics per action class:
    detection rate  - frac of positives where model returned a valid bbox
    false-pos rate  - frac of negatives where model returned a bbox (hallucination)
    mean IoU        - mean IoU of returned bbox vs best-matching GT, on detected positives
    IoU@0.5 recall  - frac of ALL positives where the returned bbox has IoU >= 0.5
    parse errors    - frac of responses that were neither a valid bbox nor SKIP
"""
import argparse
import base64
import json
import re
import sys
import time
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import requests


HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
BBOX_RE = re.compile(r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def resolve_image(raw: str, image_root: Path) -> Path:
    """Manifest entries may be absolute (legacy) or repo-root-relative (current)."""
    p = Path(raw)
    if p.is_absolute():
        return p
    return image_root / raw


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


def parse_response(text: str):
    """Return ('skip', None) | ('bbox', [x1,y1,x2,y2]) | ('parse_error', raw)."""
    s = text.strip()
    m = BBOX_RE.search(s)
    if m:
        return "bbox", [int(x) for x in m.groups()]
    if "SKIP" in s.upper():
        return "skip", None
    return "parse_error", s


def call_ollama(host: str, model: str, img_b64: str, prompt: str, timeout: int):
    r = requests.post(
        f"{host.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def call_vllm(server: str, model: str, img_b64: str, prompt: str, timeout: int):
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
            "max_tokens": 50,
            "temperature": 0,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


DEFAULT_VLLM_SERVER = "http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"
DEFAULT_OLLAMA_SERVER = "http://localhost:11434"


def call_model(args, img_b64: str, prompt: str):
    if args.backend == "ollama":
        return call_ollama(args.server or DEFAULT_OLLAMA_SERVER, args.model, img_b64, prompt, args.timeout)
    return call_vllm(args.server or DEFAULT_VLLM_SERVER, args.model, img_b64, prompt, args.timeout)


def call_vllm_list(server: str, model: str, img_paths, prompt: str, timeout: int):
    """Send a list of image_urls (one per frame) -- mirrors send_to_vllm_multi."""
    content = [{"type": "text", "text": prompt}]
    for p in img_paths:
        b = base64.b64encode(Path(p).read_bytes()).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b}"},
        })
    r = requests.post(
        f"{server.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 50,
            "temperature": 0,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def load_context_frames(entry, n: int, image_root: Path):
    """Return up to n consecutive image paths ending at the manifest frame.
    Preceding frames come from the same clip dir; missing frames are skipped."""
    target_path = resolve_image(entry["image"], image_root)
    if not target_path.is_file():
        return []
    clip_dir = target_path.parent
    try:
        fid = int(target_path.stem)
    except ValueError:
        return [target_path]
    paths = []
    for k in range(n - 1, -1, -1):
        p = clip_dir / f"{fid - k}.jpg"
        if p.is_file():
            paths.append(p)
    return paths


def stitch_mosaic(paths):
    """2xK grid of frames with FRAME-N labels burned in.
    Returns (jpeg_bytes, frame_w, frame_h) -- per-panel size, not canvas size."""
    from PIL import Image, ImageDraw, ImageFont
    imgs = [Image.open(p).convert("RGB") for p in paths]
    w, h = imgs[0].size
    n = len(imgs)
    cols = 2 if n > 1 else 1
    rows = (n + cols - 1) // cols
    canvas = Image.new("RGB", (w * cols, h * rows), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        x, y = c * w, r * h
        canvas.paste(img, (x, y))
        label = f"FRAME {i + 1}"
        draw.text((x + 22, y + 22), label, fill=(0, 0, 0), font=font)
        draw.text((x + 20, y + 20), label, fill=(255, 230, 0), font=font)
    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=88)
    return buf.getvalue(), w, h


def mosaic_prompt_prefix(n_frames: int, frame_w: int, frame_h: int) -> str:
    """Prepended to the manifest prompt in mosaic mode so the model returns
    coordinates in target-frame space, not composite-image space."""
    layout = ("FRAME 1: top-left, FRAME 2: top-right, "
              "FRAME 3: bottom-left, FRAME 4: bottom-right") if n_frames == 4 else \
             "frames are laid out left-to-right, top-to-bottom in reading order"
    return (
        f"IMAGE LAYOUT: this image is a 2x2 mosaic of {n_frames} consecutive video "
        f"frames, each {frame_w}x{frame_h} pixels ({layout}). "
        f"The task below applies to FRAME {n_frames} (the latest frame). "
        f"Return any bounding-box coordinates in FRAME {n_frames}'s own coordinate "
        f"space (0 <= x <= {frame_w}, 0 <= y <= {frame_h}) -- NOT in the composite "
        f"image. Frames 1..{n_frames - 1} are temporal context only.\n\n"
        f"TASK: "
    )


def select_entries(entries, action_filter, limit_per_class):
    if action_filter:
        entries = [e for e in entries if e["action"] == action_filter]
    if not limit_per_class:
        return entries
    counts = defaultdict(lambda: {"pos": 0, "neg": 0})
    out = []
    for e in entries:
        side = "pos" if e["is_positive"] else "neg"
        if counts[e["action"]][side] >= limit_per_class:
            continue
        counts[e["action"]][side] += 1
        out.append(e)
    return out


def run(args):
    manifest = json.loads(Path(args.manifest).read_text())
    entries = select_entries(manifest["entries"], args.action, args.limit_per_class)
    effective_server = args.server or (DEFAULT_VLLM_SERVER if args.backend == "vllm" else DEFAULT_OLLAMA_SERVER)
    if args.batch_size > 1 and args.backend != "vllm":
        raise SystemExit("--batch-size > 1 only supported for --backend vllm")
    print(f"Evaluating {len(entries)} entries against {args.backend}:{args.model} @ {effective_server}")
    print(f"Input: batch_size={args.batch_size}, mode={args.input_mode}")

    results = []
    image_root = Path(args.image_root).resolve() if args.image_root else REPO_ROOT
    for i, e in enumerate(entries, 1):
        target_path = resolve_image(e["image"], image_root)
        if not target_path.is_file():
            print(f"[{i}/{len(entries)}] MISS image: {target_path}")
            continue

        n_frames_actual = 1
        t0 = time.time()
        try:
            if args.batch_size > 1:
                paths = load_context_frames(e, args.batch_size, image_root)
                if len(paths) < args.batch_size:
                    print(f"[{i}/{len(entries)}] SKIP (only {len(paths)}/{args.batch_size} ctx frames): {e['id']}")
                    continue
                n_frames_actual = len(paths)
                if args.input_mode == "mosaic":
                    mosaic_bytes, fw, fh = stitch_mosaic(paths)
                    img_b64 = base64.b64encode(mosaic_bytes).decode()
                    prompt = mosaic_prompt_prefix(len(paths), fw, fh) + e["prompt"]
                    text = call_vllm(args.server or DEFAULT_VLLM_SERVER, args.model,
                                     img_b64, prompt, args.timeout)
                else:
                    text = call_vllm_list(args.server or DEFAULT_VLLM_SERVER, args.model,
                                          paths, e["prompt"], args.timeout)
            else:
                img_b64 = base64.b64encode(target_path.read_bytes()).decode()
                text = call_model(args, img_b64, e["prompt"])
        except Exception as ex:
            text = f"__REQUEST_ERROR__: {ex}"
        dt = time.time() - t0
        kind, parsed = parse_response(text)
        best_iou = 0.0
        if kind == "bbox" and e["is_positive"] and e["gt_bboxes"]:
            best_iou = max(iou(parsed, gt) for gt in e["gt_bboxes"])
        results.append({
            "id": e["id"],
            "action": e["action"],
            "is_positive": e["is_positive"],
            "gt_bboxes": e["gt_bboxes"],
            "response": text,
            "parsed_kind": kind,
            "pred_bbox": parsed,
            "best_iou": best_iou,
            "latency_s": round(dt, 3),
            "batch_size": args.batch_size,
            "input_mode": args.input_mode,
            "n_frames_actual": n_frames_actual,
        })
        if i % 5 == 0 or i == len(entries):
            tag = f"iou={best_iou:.2f}" if (kind == "bbox" and e["is_positive"]) else kind
            print(f"[{i}/{len(entries)}] {e['id']:22s} {tag:14s} {dt:.1f}s")

    if args.out_results:
        Path(args.out_results).write_text(json.dumps(results, indent=2))
        print(f"\nPer-item results -> {args.out_results}")

    print("\n=== Summary ===")
    by = defaultdict(list)
    for r in results:
        by[r["action"]].append(r)
    if not by:
        return
    rows = []
    for action in sorted(by):
        group = by[action]
        pos = [r for r in group if r["is_positive"]]
        neg = [r for r in group if not r["is_positive"]]
        pos_bbox = [r for r in pos if r["parsed_kind"] == "bbox"]
        neg_bbox = [r for r in neg if r["parsed_kind"] == "bbox"]
        parse_err = [r for r in group if r["parsed_kind"] == "parse_error"]
        det_rate = len(pos_bbox) / len(pos) if pos else 0.0
        fp_rate = len(neg_bbox) / len(neg) if neg else 0.0
        mean_iou = (sum(r["best_iou"] for r in pos_bbox) / len(pos_bbox)) if pos_bbox else 0.0
        iou_at_50 = (sum(1 for r in pos_bbox if r["best_iou"] >= 0.5) / len(pos)) if pos else 0.0
        rows.append((action, len(pos), len(neg), det_rate, fp_rate, mean_iou, iou_at_50, len(parse_err)))

    header = f"{'action':6s} {'P':>4s} {'N':>4s} {'det':>7s} {'FP':>7s} {'mIoU':>6s} {'IoU@.5':>7s} {'err':>4s}"
    print(header)
    print("-" * len(header))
    for a, p, n, d, fp, m, i50, pe in rows:
        print(f"{a:6s} {p:>4d} {n:>4d} {d:>6.1%} {fp:>6.1%} {m:>6.2f} {i50:>6.1%} {pe:>4d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(HERE / "manifest.json"))
    ap.add_argument("--backend", choices=["vllm", "ollama"], default="vllm")
    ap.add_argument("--model", default="RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8")
    ap.add_argument("--server", default=None,
                    help=f"vllm default: {DEFAULT_VLLM_SERVER}; ollama default: {DEFAULT_OLLAMA_SERVER}")
    ap.add_argument("--action", choices=list(["spike", "set", "block", "dig"]), default=None)
    ap.add_argument("--limit-per-class", type=int, default=None,
                    help="Cap positives and negatives per class (useful for smoke tests)")
    ap.add_argument("--out-results", default=None)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--image-root", default=None,
                    help=f"Root for resolving relative image paths (default: {REPO_ROOT})")
    ap.add_argument("--batch-size", type=int, default=1,
                    help="N-1 preceding frames from same clip are prepended to the manifest frame")
    ap.add_argument("--input-mode", choices=["list", "mosaic"], default="list",
                    help="'list' = N image_urls (production shape); 'mosaic' = one stitched image with FRAME labels")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
