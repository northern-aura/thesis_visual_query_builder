#!/usr/bin/env python3
"""Render thesis-quality PNG plots from metrics/<slug>.json.

Usage:
    python scripts/render_thesis_plots.py <slug>         # one query
    python scripts/render_thesis_plots.py --all          # all queries under metrics/
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = REPO_ROOT / "results" / "metrics"
PLOTS_DIR = REPO_ROOT / "results" / "plots"


def load_metrics(slug: str) -> dict:
    path = METRICS_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"No metrics file at {path}")
    with path.open() as f:
        return json.load(f)


def render_query(slug: str) -> Path:
    data = load_metrics(slug)
    out_dir = PLOTS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    title = data.get("query_title", slug)
    chart = data.get("chart_summary") or {}
    raw = chart.get("raw", {})
    timelines = chart.get("timelines", {})
    box = chart.get("box_stats", {})
    acc_means = chart.get("accuracy_means_pct", {})

    _llm_box(box.get("llm"), raw.get("llm_times_ms", []), out_dir, title)
    _operator_boxes(box.get("operators", {}), raw.get("operator_latencies_ms", {}), out_dir, title)
    _timeline(timelines.get("llm", []), "LLM Latency per Frame", "ms", out_dir / "llm_timeline.png", title)
    _timeline(timelines.get("e2e", []), "End-to-End Latency per Frame", "ms", out_dir / "e2e_timeline.png", title, color="#8b5cf6")
    _accuracy_bar(acc_means, out_dir, title)

    print(f"[render] {slug} -> {out_dir}")
    return out_dir


def _llm_box(stats: dict | None, values: list, out_dir: Path, title: str):
    if not values:
        return
    fig, ax = plt.subplots(figsize=(4, 4.5))
    ax.boxplot([values], tick_labels=["LLM"], showfliers=True, widths=0.5, patch_artist=True,
               boxprops=dict(facecolor="#3b82f6", alpha=0.3),
               medianprops=dict(color="#22c55e", linewidth=2))
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"LLM Response Time — {title}")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    if stats:
        ax.text(1.05, stats["median"], f"median={stats['median']:.0f}ms\nn={stats['n']}",
                va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "llm_box.png", dpi=150)
    plt.close(fig)


def _operator_boxes(box_stats: dict, raw_ops: dict, out_dir: Path, title: str):
    if not raw_ops:
        return
    items = sorted(raw_ops.items(), key=lambda kv: (box_stats.get(kv[0]) or {}).get("median", 0), reverse=True)
    labels = [k for k, _ in items]
    vals = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 4.5))
    ax.boxplot(vals, tick_labels=labels, showfliers=True, widths=0.5, patch_artist=True,
               boxprops=dict(facecolor="#8b5cf6", alpha=0.25),
               medianprops=dict(color="#22c55e", linewidth=2))
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"Per-Operator Latency — {title}")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(out_dir / "operator_boxes.png", dpi=150)
    plt.close(fig)


def _timeline(points: list, ylabel: str, unit: str, path: Path, title: str, color: str = "#3b82f6"):
    if not points:
        return
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.scatter(xs, ys, color=color, alpha=0.7, s=30)
    if len(points) > 2:
        win = 5
        avg = [sum(ys[max(0, i - win // 2):i + win // 2 + 1]) /
               len(ys[max(0, i - win // 2):i + win // 2 + 1]) for i in range(len(ys))]
        ax.plot(xs, avg, color="#f59e0b", linewidth=2, alpha=0.8, label=f"rolling avg (w={win})")
        ax.legend(loc="upper right", fontsize=9)
    ax.set_xlabel("Frame")
    ax.set_ylabel(f"{ylabel} ({unit})")
    ax.set_title(f"{ylabel} — {title}")
    ax.grid(linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _accuracy_bar(acc_means: dict, out_dir: Path, title: str):
    if not acc_means:
        return
    labels, vals = [], []
    for k, v in acc_means.items():
        if v is None:
            continue
        clean = k.replace("_match", "").replace("_accuracy", "")
        labels.append(clean)
        vals.append(v)
    if not labels:
        return
    fig, ax = plt.subplots(figsize=(max(4, len(labels) * 1.5), 3.8))
    bars = ax.bar(labels, vals, color="#10b981", alpha=0.8)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title(f"Accuracy by Field — {title}")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_dir / "accuracy_bar.png", dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("slug", nargs="?", help="query slug (filename in metrics/ without .json)")
    g.add_argument("--all", action="store_true", help="render plots for every metrics/*.json")
    args = ap.parse_args()

    if args.all:
        slugs = [p.stem for p in METRICS_DIR.glob("*.json")]
        if not slugs:
            print("No metrics files found in metrics/", file=sys.stderr)
            sys.exit(1)
        for slug in slugs:
            render_query(slug)
    else:
        render_query(args.slug)


if __name__ == "__main__":
    main()
