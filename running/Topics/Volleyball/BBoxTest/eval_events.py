"""
Event-level detection eval for the non-bbox volleyball classification queries.

An *event* = a contiguous run of frames where at least one player has
action == <target> and lost == 0, read directly from the VATIC tracking annotation.

An event is *detected* if the classification query (vbSpiking / vbSetting /
vbBlocking / vbDigging) returns the target label on ANY frame within the window.
Batch=1, single-image call -- no frame batcher.

Usage:
    python running/Topics/Volleyball/BBoxTest/eval_events.py --out eval_events.json

Cost: ~4 clips x ~20 frames in event windows x 4 queries ~= 200-320 LLM calls.
"""
import argparse
import base64
import json
import time
from pathlib import Path

import requests


HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_VLLM_SERVER = "http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"
DEFAULT_MODEL = "RedHatAI/Qwen2.5-VL-7B-Instruct-quantized.w8a8"


# Prompts copied verbatim from src/components/queries-list/queries.js:129-132
PROMPT_SPIKING = (
    "Is there a player spiking the ball in this volleyball image? "
    "If yes, return 'spiking'. If not or no players visible, return SKIP.\n\n"
    "Do not provide any text or any explanation."
)
PROMPT_SETTING = (
    "Is there a player setting the ball in this volleyball image? "
    "If yes, return 'setting'. If not or no players visible, return SKIP.\n\n"
    "Do not provide any text or any explanation."
)
PROMPT_BLOCKING = (
    "Is there a player blocking at the net in this volleyball image? "
    "If yes, return 'blocking'. If not or no players visible, return SKIP.\n\n"
    "Do not provide any text or any explanation."
)
PROMPT_DIGGING = (
    "Is there a player digging the ball in this volleyball image? "
    "If yes, return 'digging'. If not or no players visible, return SKIP.\n\n"
    "Do not provide any text or any explanation."
)

# (vatic_action_token, query_name, prompt, fire_token)
ACTIONS = [
    ("spiking",  "vbSpiking",  PROMPT_SPIKING,  "spiking"),
    ("setting",  "vbSetting",  PROMPT_SETTING,  "setting"),
    ("blocking", "vbBlocking", PROMPT_BLOCKING, "blocking"),
    ("digging",  "vbDigging",  PROMPT_DIGGING,  "digging"),
]


# Clips with VATIC annotations present in the dataset sample.
DEFAULT_CLIPS = [("7", "38025"), ("7", "51725"), ("10", "18360"), ("10", "20525")]


def load_tracks(path: Path):
    """Return list of (player_id, bbox, frame_id, lost, action) rows.
    Duplicates load_tracks from eval_single_track.py but keeps this script standalone."""
    rows = []
    with path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            pid = int(parts[0])
            fid = int(parts[5])
            lost = int(parts[6])
            action = parts[9]
            rows.append((pid, fid, lost, action))
    return rows


def build_events(rows, action_token):
    """Contiguous runs of frames where >=1 non-lost player has the given action.
    Returns list of (start_fid, end_fid) inclusive."""
    frames_with_action = sorted({fid for _, fid, lost, act in rows
                                 if lost == 0 and act == action_token})
    if not frames_with_action:
        return []
    events = []
    run_start = frames_with_action[0]
    run_end = frames_with_action[0]
    for fid in frames_with_action[1:]:
        if fid == run_end + 1:
            run_end = fid
        else:
            events.append((run_start, run_end))
            run_start = run_end = fid
    events.append((run_start, run_end))
    return events


def call_vllm(server, model, img_b64, prompt, timeout=120):
    r = requests.post(
        f"{server.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                ],
            }],
            "max_tokens": 50,
            "temperature": 0,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def frames_needed(events_by_action):
    """Union of all frames in any event window, across all action classes."""
    needed = set()
    for events in events_by_action.values():
        for start, end in events:
            for fid in range(start, end + 1):
                needed.add(fid)
    return sorted(needed)


def run(args):
    clips = [(g, c) for g, c in DEFAULT_CLIPS]
    vatic_root = Path(args.vatic_root).resolve()
    videos_root = Path(args.videos_root).resolve()

    all_events = []          # [(clip_key, action_token, start, end, n_frames, detected)]
    per_frame_records = []   # [{clip, fid, action, response, fired, latency_s}]

    t_total = time.time()
    total_calls = 0

    for game, clip in clips:
        clip_key = f"{game}/{clip}"
        track_path = vatic_root / game / clip / f"{clip}.txt"
        clip_dir = videos_root / game / clip
        if not track_path.is_file() or not clip_dir.is_dir():
            print(f"SKIP clip {clip_key}: missing files")
            continue

        rows = load_tracks(track_path)

        # Build events per action class for this clip
        events_by_action = {tok: build_events(rows, tok) for tok, _, _, _ in ACTIONS}

        frames = frames_needed(events_by_action)
        frames = [fid for fid in frames if (clip_dir / f"{fid}.jpg").is_file()]
        if not frames:
            print(f"SKIP clip {clip_key}: no event frames on disk")
            continue

        n_events_total = sum(len(v) for v in events_by_action.values())
        print(f"\n=== Clip {clip_key}: {len(frames)} frames across "
              f"{n_events_total} event windows ===")
        for tok, _, _, _ in ACTIONS:
            evs = events_by_action[tok]
            if evs:
                print(f"  {tok}: {evs}")

        # fired[(fid, action_token)] = bool
        fired = {}

        for fid in frames:
            img_path = clip_dir / f"{fid}.jpg"
            img_b64 = base64.b64encode(img_path.read_bytes()).decode()

            for vatic_tok, query_name, prompt, fire_tok in ACTIONS:
                # Only call if this frame is inside an event window for this action
                in_any_event = any(s <= fid <= e for s, e in events_by_action[vatic_tok])
                if not in_any_event:
                    continue

                t0 = time.time()
                try:
                    text = call_vllm(args.server, args.model, img_b64, prompt,
                                     timeout=args.timeout)
                except Exception as ex:
                    text = f"__REQUEST_ERROR__: {ex}"
                dt = time.time() - t0
                total_calls += 1
                fire = fire_tok.lower() in text.lower()
                fired[(fid, vatic_tok)] = fire
                per_frame_records.append({
                    "clip": clip_key,
                    "frame_id": fid,
                    "query": query_name,
                    "vatic_action": vatic_tok,
                    "response": text,
                    "fired": fire,
                    "latency_s": round(dt, 3),
                })
                tag = "FIRE" if fire else "skip"
                print(f"  f={fid} {query_name:10s} -> {tag}  ({dt:.1f}s)  {text!r}")

        # Aggregate per event
        for vatic_tok, query_name, _, _ in ACTIONS:
            for start, end in events_by_action[vatic_tok]:
                n_frames = end - start + 1
                detected = any(fired.get((fid, vatic_tok), False)
                               for fid in range(start, end + 1))
                all_events.append({
                    "clip": clip_key,
                    "action": vatic_tok,
                    "query": query_name,
                    "start": start,
                    "end": end,
                    "n_frames": n_frames,
                    "detected": detected,
                })
                mark = "HIT" if detected else "MISS"
                print(f"  event {vatic_tok} [{start}..{end}] n={n_frames}: {mark}")

    # Summary
    print("\n" + "=" * 60)
    print(f"Total LLM calls: {total_calls}  wall: {time.time() - t_total:.1f}s")
    print(f"\n{'action':10s} {'n_events':>9s} {'n_detect':>9s} {'recall':>8s} "
          f"{'mean_len':>9s}")
    print("-" * 52)
    for tok, _, _, _ in ACTIONS:
        evs = [e for e in all_events if e["action"] == tok]
        if not evs:
            print(f"{tok:10s} {'0':>9s}   (no events)")
            continue
        n_total = len(evs)
        n_det = sum(1 for e in evs if e["detected"])
        mean_len = sum(e["n_frames"] for e in evs) / n_total
        print(f"{tok:10s} {n_total:>9d} {n_det:>9d} "
              f"{n_det / n_total:>7.1%} {mean_len:>9.1f}")

    if args.out:
        Path(args.out).write_text(json.dumps({
            "events": all_events,
            "per_frame": per_frame_records,
        }, indent=2))
        print(f"\nWrote {args.out}")


def main():
    default_vatic = REPO_ROOT / "volleyball_dataset" \
        / "volleyball_tracking_annotation" / "volleyball_tracking_annotation" / "_"
    default_videos = REPO_ROOT / "volleyball_dataset" / "videos_sample" / "videos_sample"

    ap = argparse.ArgumentParser()
    ap.add_argument("--vatic-root", default=str(default_vatic))
    ap.add_argument("--videos-root", default=str(default_videos))
    ap.add_argument("--server", default=DEFAULT_VLLM_SERVER)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
