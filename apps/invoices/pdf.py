"""Invoice PDF generation via reportlab — cached under media/invoices/."""

import io
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("fomo.invoices")


def get_invoice_pdf(invoice) -> bytes:
    """Return cached PDF if present; generate otherwise."""
    cache_dir = Path(settings.MEDIA_ROOT) / "invoices" / str(invoice.business_id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{invoice.invoice_number}.pdf"
    if path.exists() and invoice.updated_at.timestamp() <= path.stat().st_mtime:
        return path.read_bytes()
    pdf = _render(invoice)
    path.write_bytes(pdf)
    return pdf


def _render(invoice) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm
    y = height - 20 * mm

    business = invoice.business

    # ── header: business left, invoice meta right ────────────────────────
    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, y, business.name)
    c.setFont("Helvetica", 9)
    meta_y = y
    c.drawRightString(right, meta_y, "INVOICE")
    meta_y -= 5 * mm
    c.drawRightString(right, meta_y, invoice.invoice_number)

    y -= 6 * mm
    c.setFont("Helvetica", 9)
    for line in (business.address, business.phone, business.email):
        if line:
            c.drawString(left, y, str(line)[:70])
            y -= 4.5 * mm

    meta_y -= 5 * mm
    c.drawRightString(right, meta_y, f"Issued: {invoice.issue_date}")
    meta_y -= 4.5 * mm
    c.drawRightString(right, meta_y, f"Due: {invoice.due_date}")
    meta_y -= 4.5 * mm
    c.drawRightString(
        right, meta_y, f"Status: {invoice.get_status_display()}"
    )
    meta_y -= 4.5 * mm
    c.drawRightString(right, meta_y, f"Branch: {invoice.branch.name}")

    y -= 4 * mm
    c.line(left, y, right, y)
    y -= 7 * mm

    # ── bill to ──────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left, y, "BILL TO")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    customer = invoice.customer
    c.drawString(left, y, customer.name if customer else "Walk-in Customer")
    y -= 4.5 * mm
    if customer and customer.phone:
        c.drawString(left, y, customer.phone)
        y -= 4.5 * mm
    y -= 5 * mm

    # ── items table ──────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left, y, "ITEM")
    c.drawRightString(right - 60 * mm, y, "QTY")
    c.drawRightString(right - 30 * mm, y, "PRICE")
    c.drawRightString(right, y, "TOTAL")
    y -= 2 * mm
    c.line(left, y, right, y)
    y -= 5 * mm

    c.setFont("Helvetica", 9)
    for item in invoice.items.select_related("product"):
        name = (
            item.product.name
            if item.product
            else item.description
        )[:50]
        c.drawString(left, y, name)
        c.drawRightString(right - 60 * mm, y, str(item.quantity))
        c.drawRightString(right - 30 * mm, y, str(item.unit_price))
        c.drawRightString(right, y, str(item.total))
        y -= 5 * mm

    y -= 2 * mm
    c.line(left, y, right, y)
    y -= 6 * mm

    # ── totals ───────────────────────────────────────────────────────────
    def total_row(label, value, bold=False, x_offset=0):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
        c.drawRightString(right - 30 * mm + x_offset, y, label)
        c.drawRightString(right, y, str(value))
        y -= 5 * mm

    total_row("Subtotal", invoice.subtotal)
    if invoice.discount:
        total_row("Discount", f"-{invoice.discount}")
    if invoice.tax:
        total_row("Tax", invoice.tax)
    c.setFont("Helvetica-Bold", 11)
    total_row("TOTAL", f"{business.currency} {invoice.total}", bold=True)
    y -= 1 * mm
    total_row("Paid", invoice.amount_paid)
    if invoice.balance_due:
        total_row("Balance due", f"{business.currency} {invoice.balance_due}", bold=True)

    # ── notes + footer ───────────────────────────────────────────────────
    if invoice.notes:
        y -= 4 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(left, y, f"Notes: {invoice.notes[:110]}")

    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 18 * mm, "Thank you for your business!")
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(
        width / 2, 13 * mm, "Powered by Fomo — Your Business, Simplified."
    )

    c.showPage()
    c.save()
    return buffer.getvalue()
