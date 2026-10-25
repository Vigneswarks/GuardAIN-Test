from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "PROJECT_FINAL_OUTPUT.md"
OUTPUT = ROOT / "output" / "pdf" / "GuardAIN_Project_Final_Output.pdf"


def clean(value: str) -> str:
    replacements = {
        "-": "-", "-": "-", "-": "-", "-": "-",
        "“": '"', "”": '"', "’": "'", "…": "...",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return value


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(doc.leftMargin, 1.35 * cm, A4[0] - doc.rightMargin, 1.35 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(doc.leftMargin, 0.87 * cm, "GuardAIN | Academic prototype | Confidential demonstration material")
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.87 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build_table(lines: list[str], styles: dict[str, ParagraphStyle]):
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return []

    column_count = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (column_count - len(row)))
    table_rows = []
    for row_number, row in enumerate(rows):
        style = styles["table_header"] if row_number == 0 else styles["table_cell"]
        table_rows.append([Paragraph(clean(cell), style) for cell in row])

    available_width = A4[0] - 3.1 * cm
    widths = [available_width / column_count] * column_count
    table = Table(table_rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [table, Spacer(1, 10)]


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    stylesheet = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("Title", parent=stylesheet["Title"], fontName="Helvetica-Bold", fontSize=24,
                                leading=29, textColor=colors.HexColor("#0F172A"), spaceAfter=14, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("Subtitle", parent=stylesheet["BodyText"], fontSize=10, leading=14,
                                   textColor=colors.HexColor("#475569"), spaceAfter=22, alignment=TA_CENTER),
        "h1": ParagraphStyle("H1", parent=stylesheet["Heading1"], fontName="Helvetica-Bold", fontSize=16,
                              leading=20, textColor=colors.HexColor("#0F172A"), spaceBefore=16, spaceAfter=8),
        "h2": ParagraphStyle("H2", parent=stylesheet["Heading2"], fontName="Helvetica-Bold", fontSize=12,
                              leading=16, textColor=colors.HexColor("#0F766E"), spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("Body", parent=stylesheet["BodyText"], fontSize=9.3, leading=14,
                                textColor=colors.HexColor("#1E293B"), spaceAfter=6),
        "bullet": ParagraphStyle("Bullet", parent=stylesheet["BodyText"], fontSize=9.3, leading=13.5,
                                  leftIndent=14, firstLineIndent=-9, textColor=colors.HexColor("#1E293B"), spaceAfter=3),
        "code": ParagraphStyle("Code", parent=stylesheet["Code"], fontName="Courier", fontSize=8.2,
                                leading=11, backColor=colors.HexColor("#F1F5F9"), borderColor=colors.HexColor("#CBD5E1"),
                                borderWidth=0.4, borderPadding=6, spaceBefore=5, spaceAfter=8),
        "table_header": ParagraphStyle("TableHeader", parent=stylesheet["BodyText"], fontName="Helvetica-Bold",
                                        fontSize=7, leading=8.5, textColor=colors.white),
        "table_cell": ParagraphStyle("TableCell", parent=stylesheet["BodyText"], fontSize=6.8, leading=8.2,
                                      textColor=colors.HexColor("#1E293B")),
    }

    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    index = 0
    cover_done = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.extend(build_table(table_lines, styles))
            continue
        if line.startswith("```text"):
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            story.append(Paragraph(clean("<br/>".join(code_lines)), styles["code"]))
        elif line.startswith("# "):
            story.append(Spacer(1, 3 * cm))
            story.append(Paragraph(clean(line[2:]), styles["title"]))
            story.append(Paragraph("Final-year project presentation and implementation guide", styles["subtitle"]))
            story.append(Paragraph("Prepared for academic demonstration | GuardAIN centralized fraud-triage platform", styles["subtitle"]))
            story.append(PageBreak())
            cover_done = True
        elif line.startswith("## "):
            story.append(Paragraph(clean(line[3:]), styles["h1"]))
        elif line.startswith("### "):
            story.append(Paragraph(clean(line[4:]), styles["h2"]))
        elif line.startswith("- "):
            story.append(Paragraph("- " + clean(line[2:]), styles["bullet"]))
        elif re.match(r"^\d+\. ", line):
            story.append(Paragraph(clean(line), styles["body"]))
        elif line.strip():
            story.append(Paragraph(clean(line), styles["body"]))
        index += 1

    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=1.55 * cm, rightMargin=1.55 * cm,
        topMargin=1.55 * cm, bottomMargin=1.85 * cm,
        title="GuardAIN - Project Final Output", author="GuardAIN Project Team",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
