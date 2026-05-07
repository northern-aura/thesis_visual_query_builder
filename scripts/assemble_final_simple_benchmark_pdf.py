#!/usr/bin/env python3
"""Assemble the final simple benchmark PDF with cache-filled results merged in.

The browser print path is unreliable in this Windows sandbox, so this script
keeps the unaffected pages from the existing report and replaces only the pages
that contained stale pre-cache-fill optimized car rows.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "results" / "benchmark_simple_report.before_cache_fill_update.pdf"
OUT = ROOT / "results" / "benchmark_simple_report.pdf"
BACKUP = ROOT / "results" / "benchmark_simple_report.with_cache_fill_update_page.pdf"


STALE_PAGES_1_BASED = {3, 4, 5, 6, 9, 15, 16}


def esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def add_text_page(writer: PdfWriter, title: str, lines: list[str]) -> None:
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }),
            NameObject("/F2"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
            }),
            NameObject("/F3"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Courier"),
            }),
            NameObject("/F4"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Courier-Bold"),
            }),
        })
    })
    parts = ["q", "BT", "/F2 16 Tf", f"42 752 Td ({esc(title)}) Tj"]
    y_step = 13
    y = 728
    for raw in lines:
        if raw == "":
            y -= 8
            continue
        if raw.startswith("## "):
            parts.append("/F2 11 Tf")
            text = raw[3:]
        elif raw.startswith("H|"):
            parts.append("/F4 7.2 Tf")
            text = raw[2:]
        elif raw.startswith("M|"):
            parts.append("/F3 7.0 Tf")
            text = raw[2:]
        else:
            parts.append("/F1 9.2 Tf")
            text = raw
        parts.append(f"42 {y} Td ({esc(text)}) Tj")
        parts.append(f"-42 {-y} Td")
        y -= y_step
    parts.extend(["ET", "Q"])
    stream = DecodedStreamObject()
    stream.set_data("\n".join(parts).encode("utf-8"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def replacement_intro_pages(writer: PdfWriter) -> None:
    add_text_page(writer, "Metrics and Thesis-Level Findings", [
        "Frame-by-frame accuracy scores each frame or window against ground truth; overall query accuracy scores the final",
        "answer after aggregation. Cars use a fixed denominator of 3953 frames; volleyball uses 20-frame windows.",
        "",
        "## Coverage and comparability",
        "All final optimized car frame-level rows meet the 3953-frame target. Volleyball naive and optimized rows meet the",
        "200-window threshold. Aggregate car queries intentionally emit window/final rows and are evaluated by final-answer",
        "accuracy rather than by 3953 emitted rows.",
        "",
        "## Latency effect",
        "Across paired rows, optimized car queries reduce average LLM latency most clearly for resize-only classification and",
        "CV-prefiltered color tasks. Localization and text-reading tasks preserve more detail and therefore save less.",
        "",
        "## Final optimized car row coverage",
        "The final result cache contains 3953 rows for each optimized color/red-plate row. These rows are included as the",
        "final benchmark data for the optimized car comparisons.",
        "",
        "H|Query                                               Filled frames  Rows   Frame acc.      Overall acc.",
        "M|Optimized Car Color Generic (R480)                  0              3953   86.01%          87.50%",
        "M|Optimized Car Color Blue (CFblue+R480)              0-5            3953   98.99%          100.00%",
        "M|Optimized Color+Plate Red (CFred native)            0-6            3953   99.60%          25.00%",
        "M|Optimized Car Color Red (CFred+R480)                0-8            3953   99.39%          100.00%",
        "",
        "## Coverage audit",
        "H|Group                         Checked queries  Required count  Status",
        "M|Cars naive frame-level        12               3953            incomplete: Car Brand Generic has 3952 rows",
        "M|Cars optimized frame-level    12               3953            complete",
        "M|Volleyball naive windows      20               200             complete",
        "M|Volleyball optimized windows  20               200             complete",
    ])

    add_text_page(writer, "Naive vs Optimized Pairwise Findings: Cars", [
        "H|Naive query                    Optimized query                         Messages       Avg LLM ms       Frame delta  Overall delta",
        "M|Car Brand Generic              Opt Car Brand Generic R854              3952 -> 3953   1219.55 -> 344.13 +1.44 pp    +24.94 pp",
        "M|Car Brand Ford                 Opt Car Brand Ford R854                 3953 -> 3953   520.40 -> 319.74  -0.05 pp    +0.00 pp",
        "M|Car Brand Renault              Opt Car Brand Renault R854              4711 -> 3953   709.83 -> 323.92  +3.19 pp    +0.00 pp",
        "M|Car Brand Toyota               Opt Car Brand Toyota R854               3953 -> 3953   481.40 -> 326.47  -0.25 pp    +0.00 pp",
        "M|Car Color Generic              Opt Car Color Generic R480              3953 -> 3953   476.21 -> 216.67  -2.73 pp    +0.00 pp",
        "M|Car Color Red                  Opt Car Color Red CFred R480            3953 -> 3953   485.04 -> 223.77  +0.30 pp    +0.00 pp",
        "M|Car Color Grey                 Opt Car Color Grey CFgrey R480          3953 -> 3953   485.68 -> 209.22  -2.05 pp    +0.00 pp",
        "M|Car Color White                Opt Car Color White CFwhite R480        3953 -> 3953   478.02 -> 204.03  -2.02 pp    +0.00 pp",
        "M|Car Color Blue                 Opt Car Color Blue CFblue R480          3953 -> 3953   500.84 -> 222.65  +1.17 pp    +0.00 pp",
        "M|License Plate Generic          Opt License Plate Recognition Native    3953 -> 3953   529.42 -> 483.56  +0.00 pp    +0.00 pp",
        "M|Specific Plate QRF8G17         Opt Specific Plate QRF8G17 Native       3953 -> 3953   474.87 -> 475.17  +0.00 pp    +0.00 pp",
        "M|Color + License Plate Red      Opt Color+Plate Red CFred native        3954 -> 3953   476.75 -> 571.17  +0.18 pp    +15.00 pp",
        "",
        "Resize and CV-filter optimizations preserve final answers for the color existence tasks while lowering average LLM",
        "latency. Red-plate extraction is a text-detail task, so native-resolution inference is slower but improves the final",
        "set-level answer relative to the naive red-plate query.",
    ])

    add_text_page(writer, "Naive vs Optimized Pairwise Findings: Cars, Aggregates", [
        "Aggregate car queries are judged by final-answer accuracy. Their message counts are window/final outputs, not one row",
        "per input frame.",
        "",
        "H|Naive query                    Optimized query                         Messages       Avg LLM ms       Overall delta",
        "M|Most Popular Brand             Opt Most Popular Brand R854             37 -> 19       775.35 -> 318.53  +0.00 pp",
        "M|Most Popular Color             Opt Most Popular Color R480             120 -> 19      805.07 -> 217.71  -100.00 pp",
        "M|Most Popular Brand and Color   Opt Most Popular Brand+Color R854       24 -> 21       563.38 -> 341.48  +0.00 pp",
        "M|Most Popular Color Ford        Opt Most Popular Color Ford R854        33 -> 16       716.43 -> 386.58  +0.00 pp",
        "M|Most Popular Brand Red Cars    Opt Most Popular Brand Red CFred R854   21 -> 13       477.48 -> 10.70   +100.00 pp",
        "M|Unique License Plates          Opt Unique Plates Native                29 -> 25       633.36 -> 506.38  +10.08 pp",
        "M|Repeating License Plates       Opt Repeating Plates Native             33 -> 22       491.70 -> 482.66  -30.56 pp",
        "",
        "Set-retrieval plate tasks remain the hardest car tasks because the final Jaccard score penalizes both missed plates",
        "and extra plate strings. Most-popular tasks are intentionally strict exact-top-label comparisons.",
    ])


def replacement_plot_page(writer: PdfWriter) -> None:
    add_text_page(writer, "Plots", [
        "The generated HTML report contains the current table values. This final PDF reports the updated optimized car sample",
        "counts numerically in the tables below.",
        "",
        "Final optimized car sample counts used in the report:",
        "H|Query                                               Rows   LLM calls  Avg LLM ms",
        "M|Optimized Car Color Generic (R480)                  3953   3953       216.67",
        "M|Optimized Car Color Red (CFred+R480)                3953   83         223.77",
        "M|Optimized Car Color Blue (CFblue+R480)              3953   718        222.65",
        "M|Optimized Color+Plate Red (CFred native)            3953   81         571.17",
        "",
        "Per-query diagnostic plots in the appendix remain useful for latency shape and operator timing; final numerical values",
        "for the optimized car rows are reported in the tables and metrics CSV.",
    ])


def replacement_optimized_car_pages(writer: PdfWriter) -> None:
    add_text_page(writer, "Cars: Optimized Results", [
        "H|Query                                      Messages  Avg LLM  Frame acc.  Overall  Notes",
        "M|Opt Car Brand Generic R854                 3953      344.13   81.89%      56.52%   labeled acc 83.35%; LLM calls 3953",
        "M|Opt Car Brand Ford R854                    3953      319.74   8.30%       100.00%  labeled acc 98.28%; LLM calls 3953",
        "M|Opt Car Brand Renault R854                 3953      323.92   16.22%      100.00%  labeled acc 96.93%; LLM calls 3953",
        "M|Opt Car Brand Toyota R854                  3953      326.47   18.85%      100.00%  labeled acc 97.17%; LLM calls 3953",
        "M|Opt Car Color Generic R480                 3953      216.67   86.01%      87.50%   labeled acc 75.88%; LLM calls 3953",
        "M|Opt Car Color Red CFred R480               3953      223.77   99.39%      100.00%  labeled acc 78.95%; LLM calls 83",
        "M|Opt Car Color Grey CFgrey R480             3953      209.22   87.45%      100.00%  labeled acc 91.60%; LLM calls 3952",
        "M|Opt Car Color White CFwhite R480           3953      204.03   90.69%      100.00%  labeled acc 75.35%; LLM calls 3891",
        "M|Opt Car Color Blue CFblue R480             3953      222.65   98.99%      100.00%  labeled acc 94.74%; LLM calls 718",
        "M|Opt License Plate Recognition Native       3953      483.56   85.73%      24.26%   labeled acc 60.06%; LLM calls 3953",
        "M|Opt Specific Plate QRF8G17 Native          3953      475.17   5.34%       100.00%  labeled acc 99.39%; LLM calls 3953",
        "M|Opt Color+Plate Red CFred native           3953      571.17   99.60%      25.00%   labeled acc 92.86%; LLM calls 81",
        "",
        "All optimized frame-level car rows in this table use the final 3953-row caches.",
    ])

    add_text_page(writer, "Cars: Optimized Aggregate Results", [
        "H|Query                                      Messages  Avg LLM  Frame acc.  Overall  Notes",
        "M|Opt Most Popular Brand R854                19        318.53   -           100.00%  top brand exact match",
        "M|Opt Most Popular Color R480                19        217.71   -           0.00%    top color exact match",
        "M|Opt Most Popular Brand+Color R854          21        341.48   -           100.00%  top pair exact match",
        "M|Opt Most Popular Color Ford R854           16        386.58   -           0.00%    top color among Ford cars",
        "M|Opt Most Popular Brand Red CFred R854      13        10.70    -           100.00%  top brand among red cars",
        "M|Opt Unique Plates Native                   25        506.38   -           24.26%   unique-plate Jaccard",
        "M|Opt Repeating Plates Native                22        482.66   -           5.80%    repeating-plate Jaccard",
        "",
        "Aggregate rows intentionally emit window/final answers. Their message counts should not be compared to the 3953-frame",
        "denominator used by frame-level car tasks.",
    ])


def main() -> None:
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if OUT.exists():
        BACKUP.write_bytes(OUT.read_bytes())

    reader = PdfReader(str(BASE))
    writer = PdfWriter()
    for idx, page in enumerate(reader.pages, start=1):
        if idx == 3:
            replacement_intro_pages(writer)
        if idx == 9:
            replacement_plot_page(writer)
        if idx == 15:
            replacement_optimized_car_pages(writer)
        if idx in STALE_PAGES_1_BASED:
            continue
        writer.add_page(page)

    with OUT.open("wb") as f:
        writer.write(f)
    print(OUT)
    print(BACKUP)


if __name__ == "__main__":
    main()
