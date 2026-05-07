"""
Kafka producer for the `volleyball_video` topic.

Streams JPG frames from one game of the Volleyball Activity Recognition dataset
into the Kafka topic consumed by every `volleyballSource(...)` pipeline in
src/components/queries-list/queries.js.

Message schema (matches what Methodtemplates.js > MapDecodeStream reads):
    frame       - base64-encoded JPG bytes      (required)
    sent        - producer timestamp, epoch sec (required)
    timestamp   - epoch ms                      (informational)
    game_id     - volleyball dataset game id    (informational)
    clip_id     - target-frame id of the clip   (informational)
    frame_id    - this frame's id (target +/-20)(informational)
    gt_action   - majority-vote action label    (optional, backward compatibility)
    gt_actions  - all per-player action labels in this frame
    gt_action_counts - count of every action label in this frame
    gt_has_spiking - true if any visible player is annotated as spiking
    gt_bboxes_spiking - visible spiking player boxes as [x1, y1, x2, y2]
    gt_players  - compact per-player annotation rows with action/bbox/lost

Generated PyFlink decode code should preserve these fields as annotations.
They are also kept here so you can tail the topic and sanity-check what was
sent.

Usage:
    python send_volleyball.py                 # defaults: first 4000 frames, 20 FPS
    python send_volleyball.py --game 10
    python send_volleyball.py --game 7 --clip 38025 --fps 10
"""

import argparse
import base64
import os
import time
from collections import Counter
from pathlib import Path

try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

try:
    from kafka import KafkaProducer
    from kafka.admin import KafkaAdminClient
except ModuleNotFoundError:
    KafkaProducer = None
    KafkaAdminClient = None


# This script lives at <repo>/running/Topics/Volleyball/Data/send_volleyball.py
# The dataset is at <repo>/volleyball_dataset. Resolve from __file__ so that the
# default works regardless of the cwd the UI backend spawns us with.
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATASET_ROOT = REPO_ROOT / "volleyball_dataset"
DEFAULT_MAX_FRAMES = 4000


def parse_args():
    p = argparse.ArgumentParser(description="Stream volleyball games to Kafka.")
    p.add_argument(
        "--game",
        default="all",
        help="Game id, or 'all' to stream every game with frames on disk (default: all)",
    )
    p.add_argument("--clip", type=int, default=None, help="Single clip id (default: all clips with frames)")
    p.add_argument("--max-clips", type=int, default=None,
                   help="Cap clips streamed per game to this many (default: no cap). "
                        "Use this when the full dataset (153+ clips) is too long for one run.")
    p.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES,
                   help=f"Cap total frames streamed across all games/clips (default: {DEFAULT_MAX_FRAMES}; "
                        "use 0 for no cap).")
    p.add_argument("--fps", type=float, default=20.0, help="Send rate (default: 20)")
    p.add_argument("--bootstrap", default="localhost:9092")
    p.add_argument("--topic", default="volleyball_video")
    p.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help=f"Path to volleyball_dataset (default: {DEFAULT_DATASET_ROOT})",
    )
    # Topic clearing defaults OFF. The UI clears the input topic BEFORE submitting
    # the pipeline (the safe moment, before Flink's KafkaSource binds to a topic UUID).
    # If the sender deletes+recreates the topic AFTER Flink has subscribed, Flink ends
    # up bound to a stale topic UUID and silently sees 0 records. Pass --clear only when
    # running the sender standalone with no pipeline already consuming.
    p.add_argument("--clear", action="store_true",
                   help="Delete + recreate topic before sending. Unsafe if a Flink job is "
                        "already subscribed (will silently lose all messages).")
    return p.parse_args()


def load_gt_annotations(tracking_path: Path) -> dict[int, dict]:
    """Per-frame player actions and bboxes from the tracking annotation file.

    The tracking file has one row per player per frame:
        player_id xmin ymin xmax ymax frame_id lost group generated action

    A frame can contain several actions at once. Keep the full list and counts,
    and also include the old majority label as `gt_action` for compatibility.
    """
    if not tracking_path.is_file():
        return {}
    rows_by_frame: dict[int, list[dict]] = {}
    with tracking_path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            try:
                player_id, xmin, ymin, xmax, ymax, frame_id, lost = [int(v) for v in parts[:7]]
            except ValueError:
                continue
            action = parts[9]
            rows_by_frame.setdefault(frame_id, []).append({
                "player_id": player_id,
                "bbox": [xmin, ymin, xmax, ymax],
                "lost": lost,
                "action": action,
            })

    annotations = {}
    for frame_id, players in rows_by_frame.items():
        actions = [p["action"] for p in players]
        counts = Counter(actions)
        visible_players = [p for p in players if p.get("lost") == 0]
        visible_actions = [p["action"] for p in visible_players]
        visible_counts = Counter(visible_actions)
        spiking_players = [p for p in visible_players if p.get("action") == "spiking"]
        annotations[frame_id] = {
            "gt_action": counts.most_common(1)[0][0] if counts else "",
            "gt_actions": actions,
            "gt_action_counts": dict(counts),
            "gt_visible_actions": visible_actions,
            "gt_visible_action_counts": dict(visible_counts),
            "gt_has_spiking": bool(spiking_players),
            "gt_bboxes_spiking": [p["bbox"] for p in spiking_players],
            "gt_players": players,
        }
    return annotations


def clip_dirs(game_dir: Path, clip_filter: int | None):
    """Yield (clip_id, clip_dir) for every directory under game_dir that contains JPG frames.
    Walks recursively because some sample clips contain nested clip dirs (e.g. 10/20525/20500/).
    The clip_id is the directory's own integer name."""
    if not game_dir.is_dir():
        raise SystemExit(f"Game dir not found: {game_dir}")
    found = []
    for entry in game_dir.rglob("*"):
        if not entry.is_dir() or not entry.name.isdigit():
            continue
        clip_id = int(entry.name)
        if clip_filter is not None and clip_id != clip_filter:
            continue
        if any(f.suffix == ".jpg" and f.is_file() for f in entry.iterdir()):
            found.append((clip_id, entry))
    if not found:
        raise SystemExit(f"No clips with JPG frames under {game_dir} (filter={clip_filter}).")
    found.sort(key=lambda pair: (pair[1].as_posix(), pair[0]))
    return found


def list_games_with_frames(dataset_root: Path) -> list[int]:
    """Return the int-named game dirs that contain at least one JPG, across any of the
    layouts we've ever shipped: the new full dataset (volleyball-detections/<game>/...),
    the old sampler (videos_sample/videos_sample/<game>/...), or a flat root."""
    candidates = [
        dataset_root / "volleyball-detections" / "volleyball-detections",
        dataset_root / "volleyball-detections",
        dataset_root / "videos_sample" / "videos_sample",
        dataset_root / "videos_sample",
        dataset_root,
    ]
    games: set[int] = set()
    for base in candidates:
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if entry.is_dir() and entry.name.isdigit() and any(entry.rglob("*.jpg")):
                games.add(int(entry.name))
    return sorted(games)


def sorted_frames(clip_dir: Path):
    """JPGs in numeric order, skipping any non-JPG or nested dirs."""
    frames = []
    for f in clip_dir.iterdir():
        if f.is_file() and f.suffix == ".jpg" and f.stem.lstrip("-").isdigit():
            frames.append(f)
    frames.sort(key=lambda p: int(p.stem))
    return frames


def resolve_game_frames_dir(dataset_root: Path, game: int) -> Path:
    """Find the dir holding clip subdirs for `game`, across any historical dataset layout.
    Tries the new full dataset (volleyball-detections/<game>/) first, then the older
    sampler paths."""
    candidates = [
        dataset_root / "volleyball-detections" / "volleyball-detections" / str(game),
        dataset_root / "volleyball-detections" / str(game),
        dataset_root / "videos_sample" / "videos_sample" / str(game),
        dataset_root / "videos_sample" / str(game),
        dataset_root / str(game),
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return candidates[0]


def resolve_tracking_game_dir(dataset_root: Path, game: int) -> Path:
    """Accept dataset root as volleyball_dataset or volleyball_tracking_annotation subtree."""
    candidates = [
        dataset_root / "volleyball_tracking_annotation" / "volleyball_tracking_annotation" / "_" / str(game),
        dataset_root / "volleyball_tracking_annotation" / "_" / str(game),
        dataset_root / "_" / str(game),
    ]
    for p in candidates:
        if p.is_dir():
            return p
    return candidates[0]


def main():
    args = parse_args()
    root = Path(args.dataset_root).resolve()

    # Env-var overrides for callers that can't pass CLI args (the UI's /api/sender/run only
    # passes script + cwd). Set VOLLEYBALL_MAX_CLIPS=N in the dev-server environment to cap
    # streaming length without modifying the harness.
    if args.max_clips is None:
        env_cap = os.getenv("VOLLEYBALL_MAX_CLIPS")
        if env_cap and env_cap.isdigit():
            args.max_clips = int(env_cap)
    env_frame_cap = os.getenv("VOLLEYBALL_MAX_FRAMES")
    if env_frame_cap and env_frame_cap.isdigit():
        args.max_frames = int(env_frame_cap)
    if args.max_frames is not None and args.max_frames <= 0:
        args.max_frames = None

    if KafkaProducer is None:
        raise SystemExit("Missing dependency: install kafka-python to run the volleyball sender.")

    if str(args.game).lower() == "all":
        games = list_games_with_frames(root)
        if not games:
            raise SystemExit(f"No games with JPG frames under {root}")
    else:
        try:
            games = [int(args.game)]
        except ValueError:
            raise SystemExit(f"--game must be an integer or 'all', got: {args.game!r}")

    print(f"Dataset root : {root}")
    print(f"Games        : {games}")
    print(f"Topic        : {args.topic} @ {args.bootstrap}")
    print(f"FPS          : {args.fps}")
    print(f"Max frames   : {args.max_frames if args.max_frames is not None else 'unlimited'}")

    if args.clear:
        try:
            admin = KafkaAdminClient(bootstrap_servers=args.bootstrap)
            admin.delete_topics([args.topic])
            admin.close()
            print(f"Cleared old data from {args.topic}")
            time.sleep(3)
        except Exception as e:
            print(f"Note: could not clear topic (may not exist yet): {e}")

    producer = KafkaProducer(bootstrap_servers=[args.bootstrap])
    delay = 1.0 / args.fps
    sent_count = 0

    for game in games:
        if args.max_frames is not None and sent_count >= args.max_frames:
            break
        frames_root = resolve_game_frames_dir(root, game)
        tracking_root = resolve_tracking_game_dir(root, game)
        print(f"\n=== Game {game} ===")
        print(f"Frames root  : {frames_root}")

        clips = clip_dirs(frames_root, args.clip)
        if args.max_clips is not None and len(clips) > args.max_clips:
            print(f"Capping clips: {len(clips)} found, streaming first {args.max_clips}")
            clips = clips[:args.max_clips]
        print(f"Clips found  : {len(clips)} (first 10 ids: {[cid for cid,_ in clips[:10]]})")

        for clip_id, clip_dir in clips:
            if args.max_frames is not None and sent_count >= args.max_frames:
                break
            gt = load_gt_annotations(tracking_root / str(clip_id) / f"{clip_id}.txt")
            frames = sorted_frames(clip_dir)
            if args.max_frames is not None:
                remaining = args.max_frames - sent_count
                if remaining <= 0:
                    break
                frames = frames[:remaining]
            print(f"\nClip {clip_id}: {len(frames)} frames, gt_actions={'yes' if gt else 'no'}")

            for frame_path in frames:
                frame_id = int(frame_path.stem)
                with frame_path.open("rb") as f:
                    image_encoded = base64.b64encode(f.read()).decode()

                payload = {
                    "frame": image_encoded,
                    "sent": time.time(),
                    "timestamp": time.time_ns() // 1_000_000,
                    "game_id": game,
                    "clip_id": clip_id,
                    "frame_id": frame_id,
                }
                if frame_id in gt:
                    payload.update(gt[frame_id])

                producer.send(
                    topic=args.topic,
                    key=str(sent_count).encode(),
                    value=ujson.dumps(payload).encode(),
                )
                print(f"  sent game={game} clip={clip_id} frame={frame_id}"
                      + (f" gt={payload['gt_action']} actions={payload.get('gt_action_counts', {})}"
                         if "gt_action" in payload else ""))
                sent_count += 1
                time.sleep(delay)

    producer.flush()
    producer.close()
    if args.max_frames is not None and sent_count >= args.max_frames:
        print(f"\nReached max frame cap ({args.max_frames}); stopping sender.")
    print(f"\nDone. {sent_count} frames sent to {args.topic}.")


if __name__ == "__main__":
    main()
