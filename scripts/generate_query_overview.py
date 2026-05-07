"""Generate a supervisor-friendly PDF overview of all query presets.

Reads nothing from the JS; queries are curated by hand here so the text
reads naturally for a non-technical reader. Keep in sync with
src/components/queries-list/queries.js if that file changes.
"""

from fpdf import FPDF
from pathlib import Path


# Columns: (title, pipeline, what_it_answers, output_topic)

LEGACY_CARS = [
    ("Query Car Brand Recognition",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> Sink",
     "For each frame, identifies the car's brand (ford, renault, etc.) or SKIP.",
     "cars_query_car_color_recognition_optimised_skipping"),
    ("Query Car Color Recognition",
     "Source -> Decode -> Resize -> LLM -> Sink",
     "For each frame, identifies the car's color (primary colors only).",
     "cars_query_car_color_recognition_optimised_skipping"),
    ("Query Grey Renault Plates",
     "Source -> Decode -> Resize -> LLM -> FilterEmpty -> Window -> Aggr -> Sink",
     "Finds the license plates of grey/silver Renaults seen in the stream.",
     "cars_grey_renault_plates_optimised_skipping"),
    ("Query License Plate Recognition",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> Sink",
     "License plate recognition for any visible plate in each frame (uppercase, no spaces).",
     "cars_query_license_plate_recognition_optimised_skipping"),
    ("Query Most Popular Brand",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> FilterEmpty -> Window -> Aggr -> Sink",
     "Most frequent car brand across a rolling window of frames.",
     "cars_query_most_popular_brand_optimised_skipping"),
    ("Query Most Popular Color + Brand",
     "Source -> Decode -> Resize -> LLM -> FilterEmpty -> Window -> Aggr -> Sink",
     "Most frequent (color, brand) combo over a window of frames.",
     "cars_query_most_popular_color_brand_optimised_skipping"),
    ("Query Most Popular Color",
     "Source -> Decode -> Resize -> LLM -> FilterEmpty -> Window -> Aggr -> Sink",
     "Most frequent car color over a window of frames.",
     "cars_query_most_popular_color_optimised_skipping"),
    ("Query Repeating License Plates",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> FilterEmpty -> Window -> FilterCount(>=3) -> Aggr(distinct) -> Sink",
     "Plates seen at least 3 times within a window - distinct output only.",
     "cars_query_repeating_license_plates_optimised_skipping"),
    ("Query Unique License Plates Optimised Skipping",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> FilterEmpty -> Window -> Aggr -> Sink",
     "Distinct license plates observed within each window.",
     "cars_query_unique_license_plates_optimised_skipping"),
]

NAIVE_CARS = [
    # Per-frame
    ("Car Brand (Generic)",
     "Source -> Decode -> LLM -> Sink",
     "Brand of the car in each frame, or SKIP if none.",
     "cars_brand_generic"),
    ("Car Brand Ford",
     "Source -> Decode -> LLM -> Sink",
     "Returns 'ford' only if the frame shows a Ford.",
     "cars_brand_ford"),
    ("Car Brand Renault",
     "Source -> Decode -> LLM -> Sink",
     "Returns 'renault' only if the frame shows a Renault.",
     "cars_brand_renault"),
    ("Car Brand Toyota",
     "Source -> Decode -> LLM -> Sink",
     "Returns 'toyota' only if the frame shows a Toyota.",
     "cars_brand_toyota"),
    ("Car Color (Generic)",
     "Source -> Decode -> LLM -> Sink",
     "Color of the car in each frame.",
     "cars_color_generic"),
    ("Car Color Red",
     "Source -> Decode -> LLM -> Sink",
     "Flags frames containing a red car.",
     "cars_color_red"),
    ("Car Color Grey",
     "Source -> Decode -> LLM -> Sink",
     "Flags frames containing a grey/silver car.",
     "cars_color_grey"),
    ("Car Color White",
     "Source -> Decode -> LLM -> Sink",
     "Flags frames containing a white car.",
     "cars_color_white"),
    ("Car Color Blue",
     "Source -> Decode -> LLM -> Sink",
     "Flags frames containing a blue car.",
     "cars_color_blue"),
    ("License Plate Recognition (Generic)",
     "Source -> Decode -> LLM -> Sink",
     "License plate recognition for any visible plate in each frame.",
     "cars_plate_generic"),
    ("Specific Plate: QRF8G17",
     "Source -> Decode -> LLM -> Sink",
     "Returns 'QRF8G17' only if that specific plate appears.",
     "cars_specific_plate_qrf8g17"),
    ("Color + License Plate (Red)",
     "Source -> Decode -> LLM -> Sink",
     "Plate of red cars only; SKIP otherwise.",
     "cars_color_plate_red"),
    # Windowed
    ("Most Popular Brand",
     "Source -> Decode -> LLM -> Window -> Aggr -> Sink",
     "Most frequent brand in each window of frames.",
     "cars_most_popular_brand"),
    ("Most Popular Color",
     "Source -> Decode -> LLM -> Window -> Aggr -> Sink",
     "Most frequent color in each window.",
     "cars_most_popular_color"),
    ("Most Popular Brand and Color",
     "Source -> Decode -> LLM -> Window -> Aggr -> Sink",
     "Most frequent (color, brand) combination in each window.",
     "cars_most_popular_brand_and_color"),
    ("Most Popular Color (Ford)",
     "Source -> Decode -> LLM -> Window -> Aggr -> Sink",
     "Most frequent color among Fords seen in the window.",
     "cars_most_popular_color_ford"),
    ("Most Popular Brand (Red Cars)",
     "Source -> Decode -> LLM -> Window -> Aggr -> Sink",
     "Most frequent brand among red cars in the window.",
     "cars_most_popular_brand_red"),
    ("Unique License Plates (Window)",
     "Source -> Decode -> LLM -> Window -> Aggr -> Sink",
     "Distinct plates observed per window.",
     "cars_unique_plates_window"),
    ("Repeating License Plates",
     "Source -> Decode -> LLM -> Window -> FilterCount(>=3) -> Aggr(distinct) -> Sink",
     "Plates that recur at least 3 times in a window.",
     "cars_repeating_plates"),
]

OPTIMIZED_CARS = [
    # Brand
    ("Car Brand (Resize)",
     "Source -> Decode -> Resize -> LLM -> Sink",
     "Per-frame brand; resizing cuts upstream cost.",
     "cars_brand_resize"),
    ("Car Brand (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Sink",
     "Per-frame brand; only every 10th frame reaches the LLM.",
     "cars_brand_skip10"),
    # Color
    ("Car Color (Resize)",
     "Source -> Decode -> Resize -> LLM -> Sink",
     "Per-frame color; resized first to save bandwidth.",
     "cars_color_resize"),
    ("Car Color (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Sink",
     "Per-frame color; sampled 1 in 10 frames.",
     "cars_color_skip10"),
    # Plates
    ("License Plate Recognition (Resize)",
     "Source -> Decode -> Resize -> LLM -> Sink",
     "License plate recognition with resized input.",
     "cars_plate_resize"),
    ("License Plate Recognition (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Sink",
     "License plate recognition on 1-in-10 frames.",
     "cars_plate_skip10"),
    ("License Plate Recognition (Grayscale)",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> Sink",
     "License plate recognition after grayscale+resize preprocessing.",
     "cars_plate_grayscale"),
    # Specific plate
    ("Specific Plate (Resize)",
     "Source -> Decode -> Resize -> LLM -> Sink",
     "Matches QRF8G17 after resize.",
     "cars_specific_plate_resize"),
    ("Specific Plate (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Sink",
     "Matches QRF8G17 on 1-in-10 frames.",
     "cars_specific_plate_skip10"),
    ("Specific Plate (Grayscale)",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> Sink",
     "Matches QRF8G17 after grayscale+resize.",
     "cars_specific_plate_grayscale"),
    # Color + plate
    ("Color + Plate (Resize)",
     "Source -> Decode -> Resize -> LLM -> Sink",
     "Plate of red cars; resized first.",
     "cars_color_plate_resize"),
    ("Color + Plate (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Sink",
     "Plate of red cars; 1-in-10 frames.",
     "cars_color_plate_skip10"),
    # Windowed
    ("Most Popular Brand (Resize)",
     "Source -> Decode -> Resize -> LLM -> Window -> Aggr -> Sink",
     "Top brand per window with resize preprocessing.",
     "cars_most_popular_brand_resize"),
    ("Most Popular Brand (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Window -> Aggr -> Sink",
     "Top brand per window with frame skipping.",
     "cars_most_popular_brand_skip10"),
    ("Most Popular Color (Resize)",
     "Source -> Decode -> Resize -> LLM -> Window -> Aggr -> Sink",
     "Top color per window with resize preprocessing.",
     "cars_most_popular_color_resize"),
    ("Most Popular Color (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Window -> Aggr -> Sink",
     "Top color per window with frame skipping.",
     "cars_most_popular_color_skip10"),
    ("Most Popular Brand+Color (Resize)",
     "Source -> Decode -> Resize -> LLM -> Window -> Aggr -> Sink",
     "Top (color, brand) per window with resize.",
     "cars_most_popular_brand_color_resize"),
    ("Most Popular Brand+Color (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Window -> Aggr -> Sink",
     "Top (color, brand) per window with frame skipping.",
     "cars_most_popular_brand_color_skip10"),
    ("Unique Plates (Resize)",
     "Source -> Decode -> Resize -> LLM -> Window -> Aggr -> Sink",
     "Distinct plates per window after resize.",
     "cars_unique_plates_resize"),
    ("Unique Plates (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Window -> Aggr -> Sink",
     "Distinct plates per window with frame skipping.",
     "cars_unique_plates_skip10"),
    ("Unique Plates (Grayscale)",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> Window -> Aggr -> Sink",
     "Distinct plates per window after grayscale+resize.",
     "cars_unique_plates_grayscale"),
    ("Repeating Plates (Resize)",
     "Source -> Decode -> Resize -> LLM -> Window -> FilterCount(>=3) -> Aggr(distinct) -> Sink",
     "Plates repeating 3+ times per window, after resize.",
     "cars_repeating_plates_resize"),
    ("Repeating Plates (Skip 10)",
     "Source -> Decode -> SkipFrames(10) -> LLM -> Window -> FilterCount(>=3) -> Aggr(distinct) -> Sink",
     "Plates repeating 3+ times per window, with frame skipping.",
     "cars_repeating_plates_skip10"),
    ("Repeating Plates (Grayscale)",
     "Source -> Decode -> Grayscale -> Resize -> LLM -> Window -> FilterCount(>=3) -> Aggr(distinct) -> Sink",
     "Plates repeating 3+ times per window, after grayscale+resize.",
     "cars_repeating_plates_grayscale"),
]

# Every volleyball naive query now includes a Frame Batcher (batch_size=4) between
# Decode and LLM, so 4 consecutive frames go to the LLM together in one API call.
VB_PIPE_FILTER = "Source -> Decode -> FrameBatcher(4) -> LLM -> Window(10) -> FilterCount(>=3) -> Aggr(distinct) -> Sink"
VB_PIPE_WINDOW = "Source -> Decode -> FrameBatcher(4) -> LLM -> Window(10) -> Aggr -> Sink"

VOLLEYBALL_NAIVE = [
    # Task 2 - Action-state repetition (filter count)
    ("Repeated Spikers (Window)", VB_PIPE_FILTER,
     "Players who appear spiking in 3+ batches within a window.",
     "volleyball_repeated_spikers"),
    ("Repeated Setters (Window)", VB_PIPE_FILTER,
     "Players who appear setting in 3+ batches within a window.",
     "volleyball_repeated_setters"),
    ("Repeated Blockers (Window)", VB_PIPE_FILTER,
     "Players who appear blocking in 3+ batches within a window.",
     "volleyball_repeated_blockers"),
    ("Repeated Diggers (Window)", VB_PIPE_FILTER,
     "Players who appear digging in 3+ batches within a window.",
     "volleyball_repeated_diggers"),
    # Task 3 - Motion ratio
    ("Motion Category (Window)", VB_PIPE_WINDOW,
     "Per window: fraction of players moving (ALL/MOST/SOME/NONE).",
     "volleyball_motion_category"),
    ("Players Moving (Window)", VB_PIPE_WINDOW,
     "Flags batches where at least one player is moving.",
     "volleyball_players_moving"),
    ("Players Standing (Window)", VB_PIPE_WINDOW,
     "Flags batches where at least one player is standing still.",
     "volleyball_players_standing"),
    ("Players Jumping (Window)", VB_PIPE_WINDOW,
     "Flags batches where at least one player is jumping.",
     "volleyball_players_jumping"),
    # Task 4 - Action counts / top-K
    ("Top Actions (Window)", VB_PIPE_WINDOW,
     "Most frequent player action per window (e.g. spiking/setting).",
     "volleyball_top_actions"),
    ("Spike Count (Window)", VB_PIPE_WINDOW,
     "Number of batches showing a spike per window.",
     "volleyball_spike_count"),
    ("Set Count (Window)", VB_PIPE_WINDOW,
     "Number of batches showing a set per window.",
     "volleyball_set_count"),
    ("Block Count (Window)", VB_PIPE_WINDOW,
     "Number of batches showing a block per window.",
     "volleyball_block_count"),
    # Task 5 - Sequence detection
    ("Set -> Spike Events (Window)", VB_PIPE_WINDOW,
     "Detects set-then-spike sequences (set, spike, other labels).",
     "volleyball_set_spike"),
    ("Set -> Block Events (Window)", VB_PIPE_WINDOW,
     "Detects set-then-block sequences.",
     "volleyball_set_block"),
    ("Dig -> Set Events (Window)", VB_PIPE_WINDOW,
     "Detects dig-then-set sequences.",
     "volleyball_dig_set"),
    ("Jump -> Spike Events (Window)", VB_PIPE_WINDOW,
     "Detects jump-then-spike sequences.",
     "volleyball_jump_spike"),
    # Task 6 - Bounding boxes
    ("Spike Bounding Boxes (Window)", VB_PIPE_WINDOW,
     "Bounding box (x1,y1,x2,y2) of the spiking player if any.",
     "volleyball_bbox_spike"),
    ("Block Bounding Boxes (Window)", VB_PIPE_WINDOW,
     "Bounding box of the blocking player if any.",
     "volleyball_bbox_block"),
    ("Set Bounding Boxes (Window)", VB_PIPE_WINDOW,
     "Bounding box of the setting player if any.",
     "volleyball_bbox_set"),
    ("Dig Bounding Boxes (Window)", VB_PIPE_WINDOW,
     "Bounding box of the digging player if any.",
     "volleyball_bbox_dig"),
]


SECTIONS = [
    ("Cars - Naive", NAIVE_CARS,
     "Baselines: each frame hits the LLM with no preprocessing."),
    ("Cars - Optimized", OPTIMIZED_CARS,
     "Resize and frame-skipping optimisations applied to the naive baselines."),
    ("Volleyball - Naive (with Frame Batcher)", VOLLEYBALL_NAIVE,
     "Temporal volleyball queries. Every pipeline collects 4 consecutive frames "
     "via a Frame Batcher node and sends them together in a single multi-image "
     "LLM call, giving the model temporal context for action recognition."),
]


# --- PDF rendering -----------------------------------------------------------

class OverviewPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=15)
        self.current_section = ""

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, f"Query Overview - {self.current_section}", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def title_page(pdf: OverviewPDF) -> None:
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 15, "ReactFlow Query Builder", align="C")
    pdf.ln(18)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Query Overview", align="C")
    pdf.ln(30)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    intro = (
        "This document lists every preset query shipped with the visual query "
        "builder, organised by dataset. For each query you get a one-line "
        "pipeline, a plain-English description of what it answers, and the "
        "Kafka output topic where results are published."
    )
    pdf.multi_cell(220, 7, intro, align="C")
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Contents", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    for title, rows, _desc in SECTIONS:
        pdf.cell(0, 7, f"- {title}  ({len(rows)} queries)", align="C")
        pdf.ln(7)


HEADER_FILL = (60, 90, 140)
HEADER_TEXT = (255, 255, 255)
ZEBRA_FILL = (240, 244, 250)
BODY_TEXT = (40, 40, 40)

# Landscape A4 = 297x210 mm; with 10mm margins each side -> usable 277mm
COL_WIDTHS = {
    "title": 55,
    "pipeline": 110,
    "answers": 75,
    "topic": 37,
}
ROW_MIN_H = 6


def draw_table(pdf: OverviewPDF, section_title: str, description: str, rows) -> None:
    pdf.current_section = section_title
    pdf.add_page()

    # Section title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, section_title)
    pdf.ln(12)

    # Description
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 5, description)
    pdf.ln(4)

    _render_header(pdf)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*BODY_TEXT)

    for idx, (title, pipeline, answers, topic) in enumerate(rows):
        _render_row(pdf, idx, title, pipeline, answers, topic)


def _render_header(pdf: OverviewPDF) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*HEADER_FILL)
    pdf.set_text_color(*HEADER_TEXT)
    pdf.cell(COL_WIDTHS["title"], 8, "Query Title", border=0, fill=True)
    pdf.cell(COL_WIDTHS["pipeline"], 8, "Pipeline", border=0, fill=True)
    pdf.cell(COL_WIDTHS["answers"], 8, "What it answers", border=0, fill=True)
    pdf.cell(COL_WIDTHS["topic"], 8, "Output topic", border=0, fill=True)
    pdf.ln(8)


def _measure_row_height(pdf: OverviewPDF, title, pipeline, answers, topic) -> float:
    # Use multi_cell dry-run trick: split into lines
    def lines(text: str, w: float) -> int:
        pdf.set_font("Helvetica", "", 9)
        split = pdf.multi_cell(w, 5, text, dry_run=True, output="LINES")
        return max(1, len(split))

    h_title = lines(title, COL_WIDTHS["title"])
    h_pipe = lines(pipeline, COL_WIDTHS["pipeline"])
    h_ans = lines(answers, COL_WIDTHS["answers"])
    h_topic = lines(topic, COL_WIDTHS["topic"])
    return max(ROW_MIN_H, 5 * max(h_title, h_pipe, h_ans, h_topic) + 2)


def _render_row(pdf: OverviewPDF, idx: int, title, pipeline, answers, topic) -> None:
    h = _measure_row_height(pdf, title, pipeline, answers, topic)

    # Page break if needed
    if pdf.get_y() + h > pdf.h - pdf.b_margin:
        pdf.add_page()
        _render_header(pdf)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*BODY_TEXT)

    x0 = pdf.get_x()
    y0 = pdf.get_y()
    fill = (idx % 2 == 1)
    if fill:
        pdf.set_fill_color(*ZEBRA_FILL)

    # Title
    pdf.set_xy(x0, y0)
    pdf.multi_cell(COL_WIDTHS["title"], 5, title, border=0, fill=fill,
                   new_x="RIGHT", new_y="TOP", max_line_height=5)
    # Pipeline
    pdf.set_xy(x0 + COL_WIDTHS["title"], y0)
    pdf.multi_cell(COL_WIDTHS["pipeline"], 5, pipeline, border=0, fill=fill,
                   new_x="RIGHT", new_y="TOP", max_line_height=5)
    # Answers
    pdf.set_xy(x0 + COL_WIDTHS["title"] + COL_WIDTHS["pipeline"], y0)
    pdf.multi_cell(COL_WIDTHS["answers"], 5, answers, border=0, fill=fill,
                   new_x="RIGHT", new_y="TOP", max_line_height=5)
    # Topic
    pdf.set_xy(x0 + COL_WIDTHS["title"] + COL_WIDTHS["pipeline"] + COL_WIDTHS["answers"], y0)
    pdf.multi_cell(COL_WIDTHS["topic"], 5, topic, border=0, fill=fill,
                   new_x="RIGHT", new_y="TOP", max_line_height=5)

    # Move cursor to next row
    pdf.set_xy(x0, y0 + h)


def main() -> None:
    out_path = Path(__file__).resolve().parent.parent / "query_overview.pdf"

    pdf = OverviewPDF()
    title_page(pdf)
    for section_title, rows, description in SECTIONS:
        draw_table(pdf, section_title, description, rows)

    pdf.output(str(out_path))
    print(f"Wrote {out_path}")
    total = sum(len(rows) for _, rows, _ in SECTIONS)
    print(f"Sections: {len(SECTIONS)}  |  Queries: {total}")


if __name__ == "__main__":
    main()
