#!/usr/bin/env python3
"""
Build a single self-contained HTML benchmark report for the cars dataset.

For each canonical naive / optimized cars query, picks the run with the highest
message_count from results/metrics/summary.csv and emits:
  - a metrics table
  - embedded plots from results/plots/<slug>/ (base64-inlined)

Output: results/benchmark_report.html
"""

import base64
import csv
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
METRICS = RESULTS / "metrics"
PLOTS = RESULTS / "plots"
SUMMARY_CSV = METRICS / "summary.csv"
OUT_HTML = RESULTS / "benchmark_report.html"

NAIVE_QUERIES = [
    "Car Brand (Generic)",
    "Car Brand Ford",
    "Car Brand Renault",
    "Car Brand Toyota",
    "Car Color (Generic)",
    "Car Color Red",
    "Car Color Grey",
    "Car Color White",
    "Car Color Blue",
    "License Plate Recognition (Generic)",
    "Specific Plate: QRF8G17",
    "Color + License Plate (Red)",
    "Most Popular Brand",
    "Most Popular Color",
    "Most Popular Brand and Color",
    "Most Popular Color (Ford)",
    "Most Popular Brand (Red Cars)",
    "Unique License Plates (Window)",
    "Repeating License Plates",
]

OPTIMIZED_QUERIES = [
    "Car Brand (Resize)",
    "Car Brand (Skip 10)",
    "Car Color (Resize)",
    "Car Color (Skip 10)",
    "License Plate Recognition (Resize)",
    "License Plate Recognition (Skip 10)",
    "License Plate Recognition (Grayscale)",
    "Specific Plate (Resize)",
    "Specific Plate (Skip 10)",
    "Specific Plate (Grayscale)",
    "Color + Plate (Resize)",
    "Color + Plate (Skip 10)",
    "Most Popular Brand (Resize)",
    "Most Popular Brand (Skip 10)",
    "Most Popular Color (Resize)",
    "Most Popular Color (Skip 10)",
    "Most Popular Brand+Color (Resize)",
    "Most Popular Brand+Color (Skip 10)",
    "Unique Plates (Resize)",
    "Unique Plates (Skip 10)",
    "Unique Plates (Grayscale)",
    "Repeating Plates (Resize)",
    "Repeating Plates (Skip 10)",
    "Repeating Plates (Grayscale)",
]

PLOT_ORDER = [
    ("accuracy_bar.png", "Accuracy"),
    ("llm_box.png", "LLM latency distribution"),
    ("operator_boxes.png", "Per-operator latency"),
    ("llm_timeline.png", "LLM latency over time"),
    ("e2e_timeline.png", "End-to-end latency over time"),
]

SLUG_OVERRIDES = {
    "License Plate Recognition (Generic)": "license_plates_generic",
    "License Plate Recognition (Resize)": "license_plates_resize",
    "License Plate Recognition (Skip 10)": "license_plates_skip_10",
    "License Plate Recognition (Grayscale)": "license_plates_grayscale",
}

TITLE_ALIASES = {
    "License Plate Recognition (Generic)": "License Plates (Generic)",
    "License Plate Recognition (Resize)": "License Plates (Resize)",
    "License Plate Recognition (Skip 10)": "License Plates (Skip 10)",
    "License Plate Recognition (Grayscale)": "License Plates (Grayscale)",
}


def slugify(title: str) -> str:
    if title in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[title]
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def best_row(best: dict, title: str):
    return best.get(title) or best.get(TITLE_ALIASES.get(title, ""))


COLS_21 = [
    "query_title", "timestamp", "duration_s", "message_count", "llm_model",
    "has_window", "has_grayscale",
    "resize_width_lbound", "resize_width_rbound",
    "resize_height_lbound", "resize_height_rbound",
    "brand_accuracy", "color_accuracy", "plate_accuracy",
    "avg_llm_time_ms", "avg_e2e_ms",
    "avg_decode_ms", "avg_resize_ms", "avg_llm_op_ms", "avg_grayscale_ms",
    "pipeline_nodes",
]
COLS_19 = [
    "query_title", "timestamp", "duration_s", "message_count", "llm_model",
    "has_window", "has_grayscale",
    "resize_width", "resize_height",
    "brand_accuracy", "color_accuracy", "plate_accuracy",
    "avg_llm_time_ms", "avg_e2e_ms",
    "avg_decode_ms", "avg_resize_ms", "avg_llm_op_ms", "avg_grayscale_ms",
    "pipeline_nodes",
]


def _parse_row(fields: list) -> dict:
    """Map a raw CSV row to a dict, choosing the schema based on field count.

    summary.csv started with the range-bound resize schema (21 cols) and later
    switched to single width/height (19 cols); the header was never updated, so
    DictReader would silently shift values two columns to the right on the newer
    rows. We detect and remap here.
    """
    n = len(fields)
    if n == 21:
        cols = COLS_21
    elif n == 19:
        cols = COLS_19
    else:
        # Pad/truncate best-effort against the longer schema
        cols = COLS_21
        fields = list(fields) + [""] * (len(cols) - n)
        fields = fields[: len(cols)]
    d = dict(zip(cols, fields))
    # Normalize resize fields so downstream code has one shape
    if n == 19:
        d["resize_width_lbound"] = d.get("resize_width", "")
        d["resize_height_lbound"] = d.get("resize_height", "")
        d["resize_width_rbound"] = ""
        d["resize_height_rbound"] = ""
    return d


def load_best_runs():
    """Return {query_title: best_row_dict} where best = max(message_count), tie-break latest timestamp."""
    best = {}
    with open(SUMMARY_CSV, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # discard — we parse by row-length
        for raw in reader:
            if not raw:
                continue
            row = _parse_row(raw)
            title = row.get("query_title", "")
            if not title:
                continue
            try:
                msgs = int(row.get("message_count") or 0)
            except ValueError:
                msgs = 0
            ts = row.get("timestamp", "")
            prev = best.get(title)
            if prev is None or msgs > prev[0] or (msgs == prev[0] and ts > prev[1]):
                best[title] = (msgs, ts, row)
    return {k: v[2] for k, v in best.items()}


def embed_image(path: Path) -> str:
    b = path.read_bytes()
    b64 = base64.b64encode(b).decode("ascii")
    return f"data:image/png;base64,{b64}"


def read_metrics_json(slug: str):
    p = METRICS / f"{slug}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def fmt_num(v, digits=2, default="–"):
    if v is None or v == "" or v == "nan":
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # nan
        return default
    if digits == 0:
        return f"{int(round(f))}"
    return f"{f:,.{digits}f}"


def fmt_pct(v, default="–"):
    if v is None or v == "":
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:
        return default
    # Guard against CSV schema-drift leakage: accuracy must be in [0, 100].
    # Values outside this range are almost certainly latency_ms misaligned
    # into the accuracy column — show '–' rather than a misleading 263,689%.
    if f < 0 or f > 100:
        return default
    return f"{f:.2f}%"


def resize_label(row):
    w = row.get("resize_width_lbound") or row.get("resize_width_rbound")
    h = row.get("resize_height_lbound") or row.get("resize_height_rbound")
    # newer runs store the single chosen width in resize_width_lbound
    if w and h:
        return f"{w}×{h}"
    if row.get("pipeline_nodes") and "Resize" in row["pipeline_nodes"]:
        return "(resize params unavailable)"
    return "–"


def render_query_block(title: str, row: dict) -> str:
    slug = slugify(title)
    detail = read_metrics_json(slug)

    msg_count = row.get("message_count", "0")
    duration = fmt_num(row.get("duration_s"), 2)
    llm_model = row.get("llm_model", "–")
    pipeline = row.get("pipeline_nodes", "–")
    ts = row.get("timestamp", "–")
    has_window = row.get("has_window", "false") == "true"
    has_grayscale = row.get("has_grayscale", "false") == "true"
    resize = resize_label(row)

    brand = fmt_pct(row.get("brand_accuracy"))
    color = fmt_pct(row.get("color_accuracy"))
    plate = fmt_pct(row.get("plate_accuracy"))
    avg_llm = fmt_num(row.get("avg_llm_time_ms"))
    avg_e2e = fmt_num(row.get("avg_e2e_ms"))

    # Throughput = messages / duration
    throughput = "–"
    try:
        d = float(row.get("duration_s") or 0)
        m = float(row.get("message_count") or 0)
        if d > 0:
            throughput = f"{m/d:.2f} msg/s"
    except ValueError:
        pass

    # Plots
    plot_dir = PLOTS / slug
    plot_html_parts = []
    if plot_dir.is_dir():
        for fname, caption in PLOT_ORDER:
            p = plot_dir / fname
            if p.exists():
                src = embed_image(p)
                plot_html_parts.append(
                    f'<figure><img src="{src}" alt="{caption}"/>'
                    f"<figcaption>{caption}</figcaption></figure>"
                )
    plots_html = (
        f'<div class="plots">{"".join(plot_html_parts)}</div>'
        if plot_html_parts
        else '<p class="no-plots">No plots available.</p>'
    )

    # Additional aggregate details if available from metrics JSON
    extra = ""
    if detail and detail.get("aggregate_metrics"):
        agg = detail["aggregate_metrics"]
        ops = agg.get("avgOperatorLatencies") or {}
        gaps = agg.get("avgBetweenNodes") or {}
        if ops:
            rows = "".join(
                f"<tr><td>{k}</td><td class='num'>{fmt_num(v)}</td></tr>"
                for k, v in ops.items()
            )
            extra += (
                "<details><summary>Per-operator latency (ms)</summary>"
                f"<table class='sub'><thead><tr><th>Operator</th><th>Avg (ms)</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></details>"
            )
        if gaps:
            rows = "".join(
                f"<tr><td>{k}</td><td class='num'>{fmt_num(v)}</td></tr>"
                for k, v in gaps.items()
            )
            extra += (
                "<details><summary>Gaps between nodes (ms)</summary>"
                f"<table class='sub'><thead><tr><th>Edge</th><th>Avg (ms)</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></details>"
            )

    return f"""
<section class="query" id="{slug}">
  <h3>{title}</h3>
  <table class="meta">
    <tr><th>Pipeline</th><td colspan="3"><code>{pipeline}</code></td></tr>
    <tr>
      <th>Messages</th><td class="num">{msg_count}</td>
      <th>Duration (s)</th><td class="num">{duration}</td>
    </tr>
    <tr>
      <th>Throughput</th><td class="num">{throughput}</td>
      <th>Avg LLM (ms)</th><td class="num">{avg_llm}</td>
    </tr>
    <tr>
      <th>Avg E2E (ms)</th><td class="num">{avg_e2e}</td>
      <th>LLM Model</th><td>{llm_model}</td>
    </tr>
    <tr>
      <th>Resize</th><td>{resize}</td>
      <th>Grayscale</th><td>{'yes' if has_grayscale else 'no'}</td>
    </tr>
    <tr>
      <th>Windowed</th><td>{'yes' if has_window else 'no'}</td>
      <th>Run at</th><td>{ts}</td>
    </tr>
    <tr>
      <th>Brand acc.</th><td class="num">{brand}</td>
      <th>Color acc.</th><td class="num">{color}</td>
    </tr>
    <tr>
      <th>Plate acc.</th><td class="num" colspan="3">{plate}</td>
    </tr>
  </table>
  {extra}
  {plots_html}
</section>
"""


def render_summary_table(section_title: str, queries: list, best: dict) -> str:
    rows_html = []
    for q in queries:
        row = best_row(best, q)
        if not row:
            rows_html.append(
                f"<tr class='missing'><td>{q}</td>"
                "<td colspan='7'><em>no run recorded</em></td></tr>"
            )
            continue
        rows_html.append(
            "<tr>"
            f"<td><a href='#{slugify(q)}'>{q}</a></td>"
            f"<td class='num'>{row.get('message_count','')}</td>"
            f"<td class='num'>{fmt_num(row.get('duration_s'))}</td>"
            f"<td class='num'>{fmt_num(row.get('avg_llm_time_ms'))}</td>"
            f"<td class='num'>{fmt_num(row.get('avg_e2e_ms'))}</td>"
            f"<td class='num'>{fmt_pct(row.get('brand_accuracy'))}</td>"
            f"<td class='num'>{fmt_pct(row.get('color_accuracy'))}</td>"
            f"<td class='num'>{fmt_pct(row.get('plate_accuracy'))}</td>"
            "</tr>"
        )
    return f"""
<h2>{section_title}</h2>
<table class="summary">
  <thead>
    <tr>
      <th>Query</th><th>Messages</th><th>Duration (s)</th>
      <th>Avg LLM (ms)</th><th>Avg E2E (ms)</th>
      <th>Brand acc.</th><th>Color acc.</th><th>Plate acc.</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>
"""


CSS = """
:root {
  --bg: #fafbfc;
  --fg: #1f2328;
  --muted: #57606a;
  --border: #d0d7de;
  --accent: #0969da;
  --row: #ffffff;
  --alt: #f6f8fa;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.45;
}
header.top {
  padding: 32px 48px;
  border-bottom: 1px solid var(--border);
  background: #fff;
}
header.top h1 { margin: 0 0 4px 0; font-size: 28px; }
header.top .sub { color: var(--muted); font-size: 14px; }
main { padding: 24px 48px 64px; max-width: 1400px; margin: 0 auto; }
h2 { margin-top: 40px; border-bottom: 2px solid var(--border); padding-bottom: 6px; }
h3 { margin-top: 0; font-size: 20px; }
code { background: var(--alt); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
table { border-collapse: collapse; width: 100%; background: var(--row); margin: 12px 0; }
table th, table td {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
  font-size: 13px;
  vertical-align: top;
}
table th { background: var(--alt); font-weight: 600; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
table.summary td:first-child { min-width: 240px; }
table.summary tr:nth-child(even) td { background: var(--alt); }
table.summary a { color: var(--accent); text-decoration: none; }
table.summary a:hover { text-decoration: underline; }
table.meta { max-width: 760px; }
table.meta th { width: 130px; }
table.sub { max-width: 480px; margin: 8px 0; }
section.query {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px 24px;
  margin: 24px 0;
}
.plots {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.plots figure { margin: 0; background: var(--alt); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.plots img { width: 100%; height: auto; display: block; }
.plots figcaption {
  padding: 6px 10px;
  font-size: 12px;
  color: var(--muted);
  border-top: 1px solid var(--border);
  background: #fff;
}
.no-plots { color: var(--muted); font-style: italic; }
tr.missing td { color: var(--muted); font-style: italic; }
details { margin: 8px 0; }
details summary { cursor: pointer; font-weight: 600; color: var(--accent); padding: 4px 0; }
.legend { background: #fffbea; border: 1px solid #ffdf5d; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 12px 0 24px; }
"""


def main():
    best = load_best_runs()

    sections = []
    # Naive block
    sections.append(render_summary_table("Naive — Summary", NAIVE_QUERIES, best))
    # Optimized block summary
    sections.append(render_summary_table("Optimized — Summary", OPTIMIZED_QUERIES, best))

    # Details
    sections.append("<h2>Naive — Details</h2>")
    for q in NAIVE_QUERIES:
        row = best_row(best, q)
        if row:
            sections.append(render_query_block(q, row))
        else:
            sections.append(
                f"<section class='query'><h3>{q}</h3>"
                "<p class='no-plots'>No run recorded in summary.csv.</p></section>"
            )

    sections.append("<h2>Optimized — Details</h2>")
    for q in OPTIMIZED_QUERIES:
        row = best.get(q)
        if row:
            sections.append(render_query_block(q, row))
        else:
            sections.append(
                f"<section class='query'><h3>{q}</h3>"
                "<p class='no-plots'>No run recorded in summary.csv.</p></section>"
            )

    total_naive_msgs = sum(
        int(best[q].get("message_count") or 0) for q in NAIVE_QUERIES if q in best
    )
    total_opt_msgs = sum(
        int(best[q].get("message_count") or 0) for q in OPTIMIZED_QUERIES if q in best
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Cars Benchmark Report</title>
<style>{CSS}</style>
</head>
<body>
<header class="top">
  <h1>Cars Dataset Benchmark Report</h1>
  <div class="sub">Naive and optimized query runs. Each entry is the run with the highest
  <em>message_count</em> for that query in <code>results/metrics/summary.csv</code>.</div>
</header>
<main>
  <div class="legend">
    <strong>Totals (best runs):</strong>
    Naive = {total_naive_msgs:,} messages across {sum(1 for q in NAIVE_QUERIES if q in best)}/{len(NAIVE_QUERIES)} queries ·
    Optimized = {total_opt_msgs:,} messages across {sum(1 for q in OPTIMIZED_QUERIES if q in best)}/{len(OPTIMIZED_QUERIES)} queries.
    Accuracy is only meaningful for queries whose LLM output matches the annotation type
    (brand / color / plate). Latency numbers are averaged per frame.
  </div>
  {''.join(sections)}
</main>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    size_mb = OUT_HTML.stat().st_size / (1024 * 1024)
    print(f"Wrote {OUT_HTML} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
