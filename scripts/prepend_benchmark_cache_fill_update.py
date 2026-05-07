#!/usr/bin/env python3
"""Prepend a cache-fill update page to the simple benchmark PDF."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "results" / "benchmark_simple_report.pdf"
BACKUP = ROOT / "results" / "benchmark_simple_report.before_cache_fill_update.pdf"


LINES = [
    ("Naive vs Optimized Query Benchmark Report", 18, True),
    ("Cache-Fill Update for Optimized Car Rows", 16, True),
    ("", 10, False),
    ("This update supersedes the earlier rows that showed four optimized car queries below 3953 frames.", 10, False),
    ("Only the missing leading frames were sent to the VLM; all existing result rows were reused as cache.", 10, False),
    ("All newly queried missing frames returned SKIP.", 10, False),
    ("", 10, False),
    ("Updated optimized car results:", 12, True),
    ("", 8, False),
    ("Query                                               Filled frames  Rows   Frame acc. before -> after  Overall", 8, True),
    ("Optimized Car Color Generic (R480)                  0              3953   85.9853% -> 86.0106%       87.5000%", 8, False),
    ("Optimized Car Color Blue (CFblue+R480)              0-5            3953   98.8363% -> 98.9881%       100.0000%", 8, False),
    ("Optimized Color+Plate Red (CFred native)            0-6            3953   99.4182% -> 99.5952%       25.0000%", 8, False),
    ("Optimized Car Color Red (CFred+R480)                0-8            3953   99.1652% -> 99.3929%       100.0000%", 8, False),
    ("", 10, False),
    ("Current status:", 12, True),
    ("- All optimized car color / red plate rows now contain 3953 frames.", 10, False),
    ("- The refreshed HTML report and metrics CSV contain the updated values.", 10, False),
    ("- Original files were backed up in results/cache_fill_backups/20260502T115246Z.", 10, False),
    ("- Detailed before/after values are in results/metrics/cache_fill_accuracy_report.csv.", 10, False),
]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_content() -> bytes:
    y = 742
    parts = ["q", "BT"]
    for text, size, bold in LINES:
        if not text:
            y -= size + 4
            continue
        font = "F2" if bold else "F1"
        parts.append(f"/{font} {size} Tf")
        parts.append(f"54 {y} Td")
        parts.append(f"({pdf_escape(text)}) Tj")
        parts.append(f"-54 {-1 * (size + 7)} Td")
        y -= size + 7
    parts.extend(["ET", "Q"])
    return "\n".join(parts).encode("utf-8")


def main() -> None:
    if not PDF.exists():
        raise FileNotFoundError(PDF)
    if not BACKUP.exists():
        BACKUP.write_bytes(PDF.read_bytes())

    reader = PdfReader(str(PDF))
    writer = PdfWriter()
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
        })
    })
    stream = DecodedStreamObject()
    stream.set_data(build_content())
    page[NameObject("/Contents")] = writer._add_object(stream)

    for old_page in reader.pages:
        writer.add_page(old_page)

    with PDF.open("wb") as f:
        writer.write(f)
    print(PDF)
    print(BACKUP)


if __name__ == "__main__":
    main()
