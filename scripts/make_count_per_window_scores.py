#!/usr/bin/env python3
"""Per-window scores for every count query.

The benchmark's window proxy (build_simple_benchmark_pdf.vb_frame_eval) hard-stops
at start>=200, so it only scores the FIRST 10 windows. This script aligns ALL
result rows to the full 4000-frame ground truth (200 windows of 20) so every
window is scored, and reports the bounded signed score per window:

    signed_score = 100 * (pred - gt) / (pred + gt)   # + over-counts, - under-counts

Output: results/metrics/count_per_window_scores.csv  (long format, one row/window)
"""
from __future__ import annotations

import csv
import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "metrics" / "count_per_window_scores.csv"

# import helpers from the benchmark builder without running its __main__
spec = importlib.util.spec_from_file_location(
    "bench", ROOT / "scripts" / "build_simple_benchmark_pdf.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

COUNT_QUERIES = [
    "Spike Count (Window)",
    "Set Count (Window)",
    "Block Count (Window)",
    "Optimized Spike Count (R854)",
    "Optimized Set Count (R854)",
    "Optimized Block Count (R854)",
]


def signed_score(pred: int, gt: int) -> float:
    return 100.0 * (pred - gt) / (pred + gt) if (pred + gt) else 0.0


def windows_for(title: str):
    rows = bench.read_jsonl(bench.RESULTS / f"{bench.slugify(title)}.jsonl")
    gt = bench.load_volleyball_gt_frames()
    target = bench.action_target(title)
    out = []
    start = 0
    for i, r in enumerate(rows):
        size = int(r.get("frames") or 20)
        frames = gt[start:start + size]
        start += size
        if not frames:
            break
        pred = bench.result_counts(r.get("result")).get(target, 0)
        truth = sum(1 for f in frames if target in f["counts"])
        out.append((i, pred, truth))
    return target, out


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    summary = []
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query", "target", "window", "pred", "gt",
                    "signed_score_pct", "direction"])
        for title in COUNT_QUERIES:
            target, wins = windows_for(title)
            over = under = exact = 0
            for idx, pred, gt in wins:
                s = signed_score(pred, gt)
                d = "over" if pred > gt else ("under" if pred < gt else "exact")
                over += d == "over"
                under += d == "under"
                exact += d == "exact"
                w.writerow([title, target, idx, pred, gt, f"{s:+.1f}", d])
            n = len(wins)
            mean_s = sum(signed_score(p, g) for _, p, g in wins) / n if n else 0.0
            summary.append((title, n, over, under, exact, mean_s))

    print(f"wrote {OUT.relative_to(ROOT)}\n")
    print(f"{'query':30}{'win':>4}{'over':>6}{'under':>6}{'exact':>6}{'mean signed':>13}")
    print("-" * 65)
    for title, n, over, under, exact, mean_s in summary:
        print(f"{title:30}{n:>4}{over:>6}{under:>6}{exact:>6}{mean_s:>+12.1f}%")


if __name__ == "__main__":
    main()
