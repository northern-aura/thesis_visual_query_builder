"""
Build a bounding-box test set for the 4 volleyball bbox queries in
src/components/queries-list/queries.js (vbBboxSpike/Set/Block/Dig).

Per target action (spike/set/block/dig):
  - Positives: frames where >=1 tracking row has action=<target> AND lost=0.
               GT bboxes = those players' [xmin, ymin, xmax, ymax].
  - Negatives: same count as positives. Drawn same-clip first (hard negatives --
               frames in a clip where the action occurs but this specific frame
               doesn't have it), then from other clips.

Only clips with both committed JPGs (volleyball_dataset/videos_sample/...) and
tracking annotations (volleyball_dataset/volleyball_tracking_annotation/...)
are considered.

Output: manifest.json with absolute image paths and verbatim prompts from queries.js.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


ACTION_MAP = {
    "spike": "spiking",
    "set":   "setting",
    "block": "blocking",
    "dig":   "digging",
}

# Copied verbatim from src/components/queries-list/queries.js:146-149
PROMPTS = {
    "spike": ("Is a volleyball spike happening in this image? If yes, return the bounding box "
              "of the spiking player as 'x1,y1,x2,y2' (pixel integers). If no spike, return SKIP.\n\n"
              "Do not provide any text or any explanation."),
    "block": ("Is a volleyball block happening at the net in this image? If yes, return the "
              "bounding box of the blocking player as 'x1,y1,x2,y2' (pixel integers). If no block, "
              "return SKIP.\n\nDo not provide any text or any explanation."),
    "set":   ("Is a volleyball set happening in this image? If yes, return the bounding box of "
              "the setting player as 'x1,y1,x2,y2' (pixel integers). If no set, return SKIP.\n\n"
              "Do not provide any text or any explanation."),
    "dig":   ("Is a volleyball dig happening in this image? If yes, return the bounding box of "
              "the digging player as 'x1,y1,x2,y2' (pixel integers). If no dig, return SKIP.\n\n"
              "Do not provide any text or any explanation."),
}


def load_tracking(path: Path):
    """Return {frame_id: [{bbox, lost, action, player_id}, ...]}."""
    out = defaultdict(list)
    if not path.is_file():
        return out
    with path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            pid, xmin, ymin, xmax, ymax, fid, lost, _grp, _gen, action = parts[:10]
            out[int(fid)].append({
                "player_id": int(pid),
                "bbox": [int(xmin), int(ymin), int(xmax), int(ymax)],
                "lost": int(lost),
                "action": action,
            })
    return out


def enumerate_clips(dataset_root: Path):
    """Yield (game, clip, frames_dir, tracking_path) for clips with both JPGs and tracking."""
    videos = dataset_root / "videos_sample" / "videos_sample"
    track_root = dataset_root / "volleyball_tracking_annotation" / "volleyball_tracking_annotation" / "_"
    if not videos.is_dir():
        raise SystemExit(f"Not found: {videos}")
    for game_dir in sorted(videos.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
        if not game_dir.is_dir() or not game_dir.name.isdigit():
            continue
        for clip_dir in sorted(game_dir.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
            if not clip_dir.is_dir() or not clip_dir.name.isdigit():
                continue
            track = track_root / game_dir.name / clip_dir.name / f"{clip_dir.name}.txt"
            if not track.is_file():
                continue
            yield int(game_dir.name), int(clip_dir.name), clip_dir, track


REPO_ROOT = Path(__file__).resolve().parents[4]


def rel_to_repo(p: Path) -> str:
    """Return a forward-slash path relative to the repo root (portable across OSes)."""
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def build(dataset_root: Path, out_path: Path, seed: int):
    random.seed(seed)
    clips = list(enumerate_clips(dataset_root))
    if not clips:
        raise SystemExit("No clips with both JPGs and tracking annotations.")
    clip_rows = {(g, c): load_tracking(t) for g, c, _, t in clips}
    print(f"Scanned {len(clips)} clip(s): " + ", ".join(f"{g}/{c}" for g, c, _, _ in clips))

    entries = []
    for short, full in ACTION_MAP.items():
        positives = []              # (game, clip, frame_id, frames_dir, gt_bboxes)
        clip_has_positives = set()  # (g,c) that contain at least one positive frame

        for g, c, frames_dir, _ in clips:
            rows_by_frame = clip_rows[(g, c)]
            for fid, rows in rows_by_frame.items():
                gt = [r["bbox"] for r in rows if r["action"] == full and r["lost"] == 0]
                if not gt:
                    continue
                jpg = frames_dir / f"{fid}.jpg"
                if not jpg.is_file():
                    continue
                positives.append((g, c, fid, frames_dir, gt))
                clip_has_positives.add((g, c))

        need_neg = len(positives)
        neg_same, neg_other = [], []
        for g, c, frames_dir, _ in clips:
            rows_by_frame = clip_rows[(g, c)]
            is_same = (g, c) in clip_has_positives
            for fid, rows in rows_by_frame.items():
                if any(r["action"] == full and r["lost"] == 0 for r in rows):
                    continue
                jpg = frames_dir / f"{fid}.jpg"
                if not jpg.is_file():
                    continue
                item = (g, c, fid, frames_dir)
                (neg_same if is_same else neg_other).append(item)
            # Also consider frames in the clip that aren't in the tracking file at all
            tracked_fids = set(rows_by_frame.keys())
            for jpg in frames_dir.iterdir():
                if not (jpg.is_file() and jpg.suffix == ".jpg" and jpg.stem.lstrip("-").isdigit()):
                    continue
                fid = int(jpg.stem)
                if fid in tracked_fids:
                    continue
                item = (g, c, fid, frames_dir)
                (neg_same if is_same else neg_other).append(item)

        random.shuffle(neg_same)
        random.shuffle(neg_other)
        negatives = (neg_same + neg_other)[:need_neg]

        for idx, (g, c, fid, frames_dir, gt) in enumerate(positives):
            entries.append({
                "id": f"{short}_pos_{idx:04d}",
                "image": rel_to_repo(frames_dir / f"{fid}.jpg"),
                "action": short,
                "prompt_key": f"vbBbox{short.capitalize()}",
                "prompt": PROMPTS[short],
                "is_positive": True,
                "gt_bboxes": gt,
                "game": g, "clip": c, "frame_id": fid,
            })
        for idx, (g, c, fid, frames_dir) in enumerate(negatives):
            entries.append({
                "id": f"{short}_neg_{idx:04d}",
                "image": rel_to_repo(frames_dir / f"{fid}.jpg"),
                "action": short,
                "prompt_key": f"vbBbox{short.capitalize()}",
                "prompt": PROMPTS[short],
                "is_positive": False,
                "gt_bboxes": [],
                "game": g, "clip": c, "frame_id": fid,
            })

    out_path.write_text(json.dumps({
        "dataset_root": str(dataset_root),
        "source_clips": [f"{g}/{c}" for g, c, _, _ in clips],
        "seed": seed,
        "entries": entries,
    }, indent=2))

    by = defaultdict(lambda: {"pos": 0, "neg": 0})
    for e in entries:
        by[e["action"]]["pos" if e["is_positive"] else "neg"] += 1
    print(f"\nWrote {len(entries)} entries -> {out_path}")
    for k in ACTION_MAP:
        v = by[k]
        print(f"  {k:5s}: {v['pos']:3d} positives  {v['neg']:3d} negatives")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="volleyball_dataset")
    ap.add_argument("--out", default="running/Topics/Volleyball/BBoxTest/manifest.json")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    build(Path(args.dataset_root).resolve(), Path(args.out).resolve(), args.seed)


if __name__ == "__main__":
    main()
