"""Compute precision / recall / F1 for ALL 70 benchmark query plans and render a PDF.

This does NOT invent numbers. It reuses the exact loaders, ground truth and
pred/gt construction from build_simple_benchmark_pdf.py, and derives precision,
recall and F1 from the same data the accuracy evaluators use.

Metric family per query (one metric per query, labelled in the table):
  - detection (frame): single-target "is X present" car queries -> per-frame TP/FP/FN.
  - retrieval (set):    multi-value car queries (brand/colour/plate sets) -> set TP/FP/FN.
  - event (window):     volleyball event-presence queries -> per-window TP/FP/FN.
  - single-answer:      "most popular" / "top action" / motion -> exact match (P/R n/a).
  - count:              count queries -> closeness (P/R n/a).

Outputs:
  results/metrics/precision_recall_summary.csv
  results/precision_recall_report.pdf
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_simple_benchmark_pdf as B  # noqa: E402
from fpdf import FPDF  # noqa: E402
from functools import lru_cache  # noqa: E402

# The GT loaders re-read large files on every call; cache them since the data is
# static for one run (each is otherwise invoked dozens of times across 70 queries).
B.load_car_gt = lru_cache(maxsize=1)(B.load_car_gt)
B.load_volleyball_gt_frames = lru_cache(maxsize=1)(B.load_volleyball_gt_frames)

OUT_PDF = B.RESULTS / "precision_recall_report.pdf"
OUT_CSV = B.METRICS / "precision_recall_summary.csv"

NAVY = (30, 50, 90)
GREY = (90, 90, 90)
RED = (160, 40, 40)


# --------------------------------------------------------------------------- #
# Metric helpers
# --------------------------------------------------------------------------- #
def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    """Precision, recall, F1 from confusion counts. None when undefined."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = 0.0 if (precision is not None and recall is not None) else None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def set_prf(pred: set, gt: set) -> tuple[float | None, float | None, float | None, int]:
    tp = len(pred & gt)
    fp = len(pred - gt)
    fn = len(gt - pred)
    p, r, f = prf(tp, fp, fn)
    return p, r, f, tp


# --------------------------------------------------------------------------- #
# Car queries
# --------------------------------------------------------------------------- #
SINGLE_TARGET = {  # title-substring -> (annotation field, target value, is_plate)
    "Brand Ford": ("brand", "ford", False),
    "Brand Renault": ("brand", "renault", False),
    "Brand Toyota": ("brand", "toyota", False),
    "Color Grey": ("color", "gray", False),
    "Color White": ("color", "white", False),
    "Color Blue": ("color", "blue", False),
}


def car_rows(title: str):
    rows = B.read_jsonl(B.RESULTS / f"{B.slugify(title)}.jsonl")
    if not rows:
        return None
    return sorted(rows, key=lambda r: r.get("sent", 0))[: B.CAR_TARGET_FRAMES]


def car_pred_gt_sets(rows):
    """Replicates the set construction used by car_overall_eval()."""
    gt_plates, gt_brands, gt_colors = B.load_car_gt()
    if not gt_plates:
        gt_brands = [B.norm_label(r.get("annotation_brand")) for r in rows]
        gt_colors = [B.norm_label(r.get("annotation_color")) for r in rows]
        gt_plates = [B.norm_plate(r.get("annotation_plate")) for r in rows]
    pred_labels, pred_plates = [], []
    for r in rows:
        items = B.result_items(r.get("result"))
        pred_labels.extend(B.norm_label(x) for x in items)
        pred_plates.extend(B.norm_plate(x) for x in items)
    return {
        "pred_label": Counter(x for x in pred_labels if x),
        "pred_plate": Counter(x for x in pred_plates if x),
        "gt_brand": Counter(x for x in gt_brands if x),
        "gt_color": Counter(x for x in gt_colors if x),
        "gt_plate": Counter(x for x in gt_plates if x),
        "gt_plates_list": gt_plates,
        "gt_colors_list": gt_colors,
    }


def car_metric(title: str) -> dict:
    rows = car_rows(title)
    base = {"query": title, "family": "-", "precision": None, "recall": None,
            "f1": None, "support": "", "note": ""}
    if rows is None:
        base["note"] = "no result rows"
        return base

    # --- single-target detection (per-frame TP/FP/FN) ----------------------- #
    field = target = None
    is_plate = False
    for marker, (fld, tgt, plate) in SINGLE_TARGET.items():
        if marker in title:
            field, target, is_plate = fld, tgt, plate
            break
    if field is None and ("Color Red" in title and "Plate" not in title and "License Plate" not in title):
        field, target, is_plate = "color", "red", False
    if field is None and "Specific Plate" in title:
        field, target, is_plate = "plate", B.SPECIFIC_PLATE_TARGET, True

    if field is not None:
        tp = fp = fn = 0
        for r in rows:
            result = B.clean_text(r.get("result"))
            ann = B.norm_label(r.get(f"annotation_{field}")) if field != "plate" else B.norm_plate(r.get("annotation_plate"))
            pred_val = B.norm_plate(result) if is_plate else B.norm_label(result)
            gold = ann == target
            pred = pred_val == target
            tp += int(gold and pred)
            fp += int(pred and not gold)
            fn += int(gold and not pred)
        p, r_, f = prf(tp, fp, fn)
        base.update(family="detection (frame)", precision=p, recall=r_, f1=f,
                    support=f"{tp+fn} positive frames",
                    note=f"TP={tp} FP={fp} FN={fn}")
        return base

    # --- single-answer aggregates (exact match) ----------------------------- #
    if "Most Popular" in title:
        acc, note = B.car_overall_eval(title)
        base.update(family="single-answer", support="1 answer", note=f"exact match: {note}",
                    precision=None, recall=None, f1=None)
        base["accuracy"] = acc
        return base

    # --- set retrieval ------------------------------------------------------ #
    s = car_pred_gt_sets(rows)
    if "Repeating" in title and "Plates" in title:
        # need raw counts incl. duplicates for the >=3 rule
        plate_counts = Counter()
        for r in rows:
            plate_counts.update(B.norm_plate(x) for x in B.result_items(r.get("result")) if B.norm_plate(x))
        gt_plate_counts = s["gt_plate"]
        pred = {p for p, c in plate_counts.items() if c >= 3}
        gt = {p for p, c in gt_plate_counts.items() if c >= 3}
        fam = "retrieval (set)"
    elif "Unique" in title and "Plates" in title:
        pred, gt, fam = set(s["pred_plate"]), set(s["gt_plate"]), "retrieval (set)"
    elif "Color+Plate Red" in title or "License Plate (Red)" in title or "Red Plate Lookup" in title:
        pred = set(s["pred_plate"])
        gt = {p for p, c in zip(s["gt_plates_list"], s["gt_colors_list"]) if p and c == "red"}
        fam = "retrieval (set)"
    elif B.is_plate_recognition_title(title):
        pred, gt, fam = set(s["pred_plate"]), set(s["gt_plate"]), "retrieval (set)"
    elif "Brand" in title and "Color" not in title:
        pred, gt, fam = set(s["pred_label"]), set(s["gt_brand"]), "retrieval (set)"
    elif "Color" in title:
        pred, gt, fam = set(s["pred_label"]), set(s["gt_color"]), "retrieval (set)"
    else:
        base["note"] = "no metric rule"
        return base

    p, r_, f, tp = set_prf(pred, gt)
    base.update(family=fam, precision=p, recall=r_, f1=f,
                support=f"pred {len(pred)} / gt {len(gt)}",
                note=f"TP={tp} FP={len(pred-gt)} FN={len(gt-pred)}")
    return base


# --------------------------------------------------------------------------- #
# Volleyball queries (per-window TP/FP/FN)
# --------------------------------------------------------------------------- #
def vb_windows(title: str):
    rows = B.read_jsonl(B.RESULTS / f"{B.slugify(title)}.jsonl")
    gt = B.load_volleyball_gt_frames()
    if not rows or not gt:
        return None
    windows, start = [], 0
    for r in rows:
        size = int(r.get("frames") or 20)
        windows.append((r, gt[start:start + size]))
        start += size
        if start >= 200:
            break
    return windows or None


def vb_metric(title: str) -> dict:
    base = {"query": title, "family": "-", "precision": None, "recall": None,
            "f1": None, "support": "", "note": ""}

    # single-answer / count families -> reuse existing evaluator, P/R n/a
    if "Top Actions" in title or "Motion Category" in title:
        acc, note = B.vb_overall_eval(title)
        base.update(family="single-answer", support="1 answer", note=f"exact match: {note}")
        base["accuracy"] = acc
        return base
    if " Count" in title:
        acc, note = B.vb_overall_eval(title)
        base.update(family="count", support="1 count", note=f"closeness: {note}")
        base["accuracy"] = acc
        return base

    windows = vb_windows(title)
    if windows is None:
        base["note"] = "no windows / no GT"
        return base

    pair = B.pair_target(title)
    target = B.action_target(title)
    tp = fp = fn = 0
    for r, frames in windows:
        pred_counts = B.result_counts(r.get("result"))
        if pair:
            first, second, label = pair
            pred = pred_counts.get(label, 0) > 0
            truth = B.ordered_pair_exists([set(f["actions"]) for f in frames], first, second)
        elif target:
            pred = pred_counts.get(target, 0) > 0
            if "Repeated" in title:
                truth = sum(1 for f in frames if target in f["counts"]) >= 3
            else:
                truth = any(target in f["counts"] for f in frames)
        else:
            continue
        tp += int(truth and pred)
        fp += int(pred and not truth)
        fn += int(truth and not pred)

    p, r_, f = prf(tp, fp, fn)
    base.update(family="event (window)", precision=p, recall=r_, f1=f,
                support=f"{len(windows)} windows / {tp+fn} pos",
                note=f"TP={tp} FP={fp} FN={fn}")
    return base


# --------------------------------------------------------------------------- #
# Drive all 70 queries
# --------------------------------------------------------------------------- #
def overall_accuracy(title: str, dataset: str) -> str:
    try:
        if dataset == "cars":
            return B.car_overall_eval(title)[0]
        return B.vb_overall_eval(title)[0]
    except Exception:
        return "-"


# Stacked-optimization case study: color filter + resize + skip on one pipeline.
# Scored alongside the standard cars_optimized group (its slug already resolves to
# results/optimized_red_plate_lookup_cfred_r1120_s3.jsonl, no override needed).
EXTRA_COMBINED = ["Optimized Red Plate Lookup (CFred+R1120+S3)"]


def collect() -> list[dict]:
    out = []
    groups = [
        ("cars_naive", "cars", B.CAR_NAIVE),
        ("cars_optimized", "cars", list(B.CAR_OPT) + EXTRA_COMBINED),
        ("volleyball_naive", "vb", B.VB_NAIVE),
        ("volleyball_optimized", "vb", B.VB_OPT),
    ]
    for group, dataset, titles in groups:
        for title in titles:
            row = car_metric(title) if dataset == "cars" else vb_metric(title)
            row["group"] = group
            row["dataset"] = dataset
            row["old_overall_accuracy"] = overall_accuracy(title, dataset)
            out.append(row)
    return out


def fmt_pct(v) -> str:
    return "-" if v is None else f"{100 * v:.1f}%"


def cell(record: dict, metric: str, long: bool = False) -> str:
    """Reason-aware cell token. Defined values -> percentage. Blanks become either
    'n/a' (metric does not apply to single-answer/count queries) or 'undef'
    (mathematically undefined: no positives or no predictions in the scored span)."""
    v = record.get(metric)
    if v is not None:
        return f"{100 * v:.1f}%"
    family = record.get("family", "")
    if family in ("single-answer", "count"):
        return f"n/a ({family})" if long else "n/a"
    if not long:
        return "undef"
    if metric == "precision":
        return "undef (no predictions)"
    if metric == "recall":
        return "undef (no positives)"
    return "undef (recall undefined)"


# --------------------------------------------------------------------------- #
# CSV + PDF
# --------------------------------------------------------------------------- #
def write_csv(records: list[dict]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "query", "metric_family", "precision", "recall", "f1",
                    "support", "old_overall_accuracy", "detail"])
        for r in records:
            w.writerow([r["group"], r["query"], r["family"],
                        cell(r, "precision", long=True), cell(r, "recall", long=True),
                        cell(r, "f1", long=True), r["support"],
                        r.get("old_overall_accuracy", "-"), r["note"]])


GROUP_TITLES = {
    "cars_naive": "Cars - naive pipeline",
    "cars_optimized": "Cars - optimized pipeline",
    "volleyball_naive": "Volleyball - naive pipeline",
    "volleyball_optimized": "Volleyball - optimized pipeline",
}


def short(title: str) -> str:
    return title.replace("Optimized ", "").replace(" (Window)", "")


class PDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def write_pdf(records: list[dict]) -> None:
    pdf = PDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 8, "Precision, Recall & F1 - All 70 Query Plans")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 5, "Computed from the same ground truth and prediction data as the accuracy "
                         "evaluators in build_simple_benchmark_pdf.py. Precision = of what the "
                         "system returned, how much was correct. Recall = of what truly existed, "
                         "how much was found. F1 = their harmonic mean. The last column repeats the "
                         "old single 'overall accuracy' so the gap is visible.")
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 4.6, "Metric family: detection (frame) = per-frame is-target-present; "
                           "retrieval (set) = distinct values returned vs present; event (window) = "
                           "per-window event presence; single-answer / count = one answer, exact "
                           "match or closeness.")
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 4.6, "Blank cells: 'n/a' = metric does not apply (single-answer / count "
                           "query); 'undef' = mathematically undefined (no positive cases in the "
                           "scored span, so recall/F1 have no denominator).")
    pdf.ln(2)

    headers = ["Query", "Family", "Prec", "Recall", "F1", "Old acc"]
    widths = [70, 38, 20, 20, 20, 20]
    by_group: dict[str, list[dict]] = {}
    for r in records:
        by_group.setdefault(r["group"], []).append(r)

    for group, title in GROUP_TITLES.items():
        rows = by_group.get(group, [])
        if not rows:
            continue
        if pdf.get_y() > pdf.h - 50:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 11.5)
        pdf.set_text_color(*NAVY)
        pdf.ln(1)
        pdf.multi_cell(0, 6, title)

        # header row
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        for h, w in zip(headers, widths):
            pdf.cell(w, 6.5, h, align="C", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8.5)
        fill = False
        for r in rows:
            if pdf.get_y() > pdf.h - 18:
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.set_fill_color(*NAVY)
                pdf.set_text_color(255, 255, 255)
                for h, w in zip(headers, widths):
                    pdf.cell(w, 6.5, h, align="C", fill=True)
                pdf.ln()
                pdf.set_font("Helvetica", "", 8.5)
            pa = cell(r, "precision")
            rc = cell(r, "recall")
            f1 = cell(r, "f1")
            old = r.get("old_overall_accuracy", "-")
            pdf.set_fill_color(238, 241, 247) if fill else pdf.set_fill_color(255, 255, 255)
            cells = [short(r["query"]), r["family"], pa, rc, f1, old]
            aligns = ["L", "L", "C", "C", "C", "C"]
            # low precision OR recall -> red text to flag the failure mode
            flag = (r["precision"] is not None and r["precision"] < 0.5) or \
                   (r["recall"] is not None and r["recall"] < 0.5)
            pdf.set_text_color(*(RED if flag else (20, 20, 20)))
            for val, w, a in zip(cells, widths, aligns):
                txt = val if len(val) < 46 else val[:43] + "..."
                pdf.cell(w, 5.8, txt, align=a, fill=True)
            pdf.ln()
            fill = not fill
        pdf.set_text_color(20, 20, 20)
        pdf.ln(1)

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT_PDF))


def main() -> None:
    records = collect()
    write_csv(records)
    write_pdf(records)
    # console summary
    fam = Counter(r["family"] for r in records)
    print(f"Queries scored: {len(records)}")
    for k, v in fam.items():
        print(f"  {k}: {v}")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_PDF}")


if __name__ == "__main__":
    main()
