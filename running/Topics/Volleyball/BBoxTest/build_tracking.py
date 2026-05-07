"""
Build a manifest for testing whether the VLM can localize *all* players in a
frame -- i.e. whether its coordinates are good enough to be used as the
detection step of a tracker. No action-conditioning, no positives/negatives:
every tracked frame is one entry, GT = every non-lost player in that frame.

Output: tracking_manifest.json
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


PROMPT = (
    "List bounding boxes for every volleyball player visible in this image. "
    "Return one bounding box per line as 'x1,y1,x2,y2' with pixel integers -- "
    "nothing else on the line. If no players are visible, return SKIP.\n\n"
    "Do not provide any text or any explanation."
)


REPO_ROOT = Path(__file__).resolve().parents[4]


def rel_to_repo(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def load_tracking(path: Path):
    rows = defaultdict(list)
    if not path.is_file():
        return rows
    with path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            pid, xmin, ymin, xmax, ymax, fid, lost, _grp, _gen, action = parts[:10]
            rows[int(fid)].append({
                "player_id": int(pid),
                "bbox": [int(xmin), int(ymin), int(xmax), int(ymax)],
                "lost": int(lost),
                "action": action,
            })
    return rows


def enumerate_clips(dataset_root: Path):
    videos = dataset_root / "videos_sample" / "videos_sample"
    track_root = dataset_root / "volleyball_tracking_annotation" / "volleyball_tracking_annotation" / "_"
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


def build(dataset_root: Path, out_path: Path):
    clips = list(enumerate_clips(dataset_root))
    entries = []
    per_clip_counts = defaultdict(int)

    for g, c, frames_dir, track_path in clips:
        rows_by_frame = load_tracking(track_path)
        for fid, rows in sorted(rows_by_frame.items()):
            gt = [r["bbox"] for r in rows if r["lost"] == 0]
            if not gt:
                continue
            jpg = frames_dir / f"{fid}.jpg"
            if not jpg.is_file():
                continue
            entries.append({
                "id": f"g{g}_c{c}_f{fid}",
                "image": rel_to_repo(jpg),
                "prompt": PROMPT,
                "gt_bboxes": gt,
                "n_players": len(gt),
                "game": g, "clip": c, "frame_id": fid,
            })
            per_clip_counts[(g, c)] += 1

    out_path.write_text(json.dumps({
        "prompt": PROMPT,
        "source_clips": [f"{g}/{c}" for g, c, _, _ in clips],
        "entries": entries,
    }, indent=2))

    print(f"Wrote {len(entries)} frames -> {out_path}")
    total_gt = sum(e["n_players"] for e in entries)
    print(f"Total GT player boxes: {total_gt}")
    for (g, c), n in sorted(per_clip_counts.items()):
        print(f"  {g}/{c}: {n} frames")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="volleyball_dataset")
    ap.add_argument("--out", default="running/Topics/Volleyball/BBoxTest/tracking_manifest.json")
    args = ap.parse_args()
    build(Path(args.dataset_root).resolve(), Path(args.out).resolve())


if __name__ == "__main__":
    main()
