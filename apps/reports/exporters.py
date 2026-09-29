"""Report exporters — CSV / XLSX / PDF.

Only formats entitled by the plan reach these functions; EntitlementService
gates everything before this runs. Row limits are enforced by the caller.
"""

import csv
import io
from decimal import Decimal


def _stringify(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def to_csv(columns, rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([c["label"] for c in columns])
    for row in rows:
        writer.writerow([_stringify(row.get(c["key"])) for c in columns])
    return buffer.getvalue().encode("utf-8-sig")  # BOM → Excel opens cleanly


def to_xlsx(columns, rows) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append([c["label"] for c in columns])
    for row in rows:
        ws.append([_stringify(row.get(c["key"])) for c in columns])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def to_pdf(columns, rows, *, title="", business_name="") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=24, rightMargin=24,
                            topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{business_name}</b> — {title}", styles["Title"])]

    header = [c["label"] for c in columns]
    data = [header] + [
        [_stringify(row.get(c["key"])) for c in columns] for row in rows
    ]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


EXPORTERS = {
    "csv": ("text/csv", to_csv),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             to_xlsx),
    "pdf": ("application/pdf", to_pdf),
}
