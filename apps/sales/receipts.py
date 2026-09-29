"""Receipt PDF generation via reportlab — cached under media/receipts/."""

import io
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("fomo.receipts")


def get_receipt_pdf(sale) -> bytes:
    """Return cached PDF if present; generate otherwise."""
    cache_dir = Path(settings.MEDIA_ROOT) / "receipts" / str(sale.business_id)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{sale.receipt_number}.pdf"
    if path.exists():
        return path.read_bytes()
    pdf = _render(sale)
    path.write_bytes(pdf)
    return pdf


def _render(sale) -> bytes:
    from reportlab.lib.pagesizes import A6
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A6)
    width, height = A6
    y = height - 12 * mm

    business = sale.business
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, y, business.name)
    y -= 6 * mm
    c.setFont("Helvetica", 8)
    if business.phone:
        c.drawCentredString(width / 2, y, f"Tel: {business.phone}")
        y -= 4 * mm
    if business.address:
        c.drawCentredString(width / 2, y, business.address[:60])
        y -= 4 * mm
    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica", 8)
    c.drawString(8 * mm, y, f"Receipt: {sale.receipt_number}")
    y -= 4 * mm
    c.drawString(8 * mm, y, f"Date: {sale.created_at:%Y-%m-%d %H:%M}")
    y -= 4 * mm
    c.drawString(8 * mm, y, f"Branch: {sale.branch.name}")
    y -= 4 * mm
    if sale.cashier:
        c.drawString(8 * mm, y, f"Cashier: {sale.cashier.full_name}")
        y -= 4 * mm
    if sale.customer:
        c.drawString(8 * mm, y, f"Customer: {sale.customer.name}")
        y -= 4 * mm
    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 5 * mm

    for item in sale.items.select_related("product"):
        name = item.product.name[:28]
        c.drawString(8 * mm, y, name)
        y -= 4 * mm
        line = f"{item.quantity} x {item.unit_price}"
        c.drawString(12 * mm, y, line)
        c.drawRightString(width - 8 * mm, y, str(item.total))
        y -= 4 * mm

    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(8 * mm, y, "Subtotal:")
    c.drawRightString(width - 8 * mm, y, f"{sale.subtotal}")
    y -= 4 * mm
    if sale.discount:
        c.drawString(8 * mm, y, "Discount:")
        c.drawRightString(width - 8 * mm, y, f"-{sale.discount}")
        y -= 4 * mm
    if sale.tax:
        c.drawString(8 * mm, y, "Tax:")
        c.drawRightString(width - 8 * mm, y, f"{sale.tax}")
        y -= 4 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(8 * mm, y, "TOTAL:")
    c.drawRightString(width - 8 * mm, y, f"{business.currency} {sale.total}")
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(8 * mm, y, f"Paid: {sale.amount_paid}   Balance: {sale.balance_due}")
    y -= 8 * mm
    c.drawCentredString(width / 2, y, "Thank you for your business!")
    y -= 4 * mm
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(width / 2, y, "Powered by Fomo — Your Business, Simplified.")

    c.showPage()
    c.save()
    return buffer.getvalue()
