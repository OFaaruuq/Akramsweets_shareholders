from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.services.brand_service import (
    DEFAULT_ACCENT,
    DEFAULT_COMPANY_NAME,
    DEFAULT_PRIMARY,
    DEFAULT_SECONDARY,
    get_brand_settings,
)


def _brand_palette(report=None):
    report = report or {}
    try:
        brand = get_brand_settings()
    except RuntimeError:
        brand = {
            'company_name': DEFAULT_COMPANY_NAME,
            'primary_color': DEFAULT_PRIMARY,
            'secondary_color': DEFAULT_SECONDARY,
            'accent_color': DEFAULT_ACCENT,
            'logo_filesystem_path': None,
        }

    primary = report.get('brand_primary_color') or brand['primary_color']
    secondary = report.get('brand_secondary_color') or brand['secondary_color']
    accent = report.get('brand_accent_color') or brand['accent_color']
    company = report.get('company_name') or brand['company_name']
    logo_path = report.get('brand_logo_path') or brand.get('logo_filesystem_path')

    return {
        'company_name': company,
        'primary': colors.HexColor(primary),
        'secondary': colors.HexColor(secondary),
        'accent': colors.HexColor(accent),
        'primary_hex': primary,
        'secondary_hex': secondary,
        'accent_hex': accent,
        'logo_path': logo_path,
    }


def _draw_brand_logo(pdf, logo_path, center_x, top_y, max_width=3.5 * cm, max_height=2.2 * cm):
    if not logo_path:
        return 0
    try:
        image = ImageReader(logo_path)
        img_w, img_h = image.getSize()
        if not img_w or not img_h:
            return 0
        scale = min(max_width / img_w, max_height / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        pdf.drawImage(
            image,
            center_x - draw_w / 2,
            top_y - draw_h,
            width=draw_w,
            height=draw_h,
            mask='auto',
            preserveAspectRatio=True,
            anchor='c',
        )
        return draw_h
    except Exception:
        return 0


def _draw_line(c, y, text, bold=False):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', 10)
    c.setFillColor(colors.black)
    c.drawString(2 * cm, y, text)
    return y - 0.55 * cm


def generate_shareholder_report_pdf(report):
    brand = _brand_palette(report)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    logo_h = _draw_brand_logo(pdf, brand['logo_path'], width / 2, y + 0.3 * cm)
    if logo_h:
        y -= logo_h + 0.35 * cm

    pdf.setFillColor(brand['primary'])
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(2 * cm, y, brand['company_name'])
    y -= 0.7 * cm
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(2 * cm, y, 'Shareholder Profit Report')
    y -= 0.5 * cm
    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.grey)
    pdf.drawString(2 * cm, y, f"Period: {report['period_label']}")
    y -= 1 * cm

    pdf.setStrokeColor(brand['secondary'])
    pdf.setLineWidth(2)
    pdf.line(2 * cm, y, width - 2 * cm, y)
    y -= 0.8 * cm

    generated = report['generated_at'].strftime('%Y-%m-%d %H:%M') if report.get('generated_at') else 'Draft'
    y = _draw_line(pdf, y, f"Generated: {generated}")
    y = _draw_line(pdf, y, f"Shareholder: {report['shareholder_name']} ({report['shareholder_email']})")
    y = _draw_line(pdf, y, f"Company total for month: {float(report['company_total']):,.2f}")
    if report.get('odoo_reference'):
        y = _draw_line(pdf, y, f"Odoo reference: {report['odoo_reference']}")
    y -= 0.3 * cm

    y = _draw_line(pdf, y, f"Ownership: {float(report['ownership_percent']):,.2f}%", bold=True)
    y = _draw_line(pdf, y, f"Base share: {float(report['base_share']):,.2f}")

    if report.get('arrangements_applied'):
        y = _draw_line(pdf, y, 'Special arrangements:', bold=True)
        for item in report['arrangements_applied']:
            y = _draw_line(
                pdf,
                y,
                f"  - {item['name']} ({float(item['percent']):,.2f}%): "
                f"{float(item['amount']):,.2f} — {item['description']}",
            )
    else:
        y = _draw_line(pdf, y, f"Arrangement deduction: {float(report['arrangement_deduction']):,.2f}")
        y = _draw_line(pdf, y, f"Arrangement received: {float(report['arrangement_received']):,.2f}")

    if report.get('adjustment_lines'):
        y = _draw_line(pdf, y, 'Manual adjustments:', bold=True)
        for item in report['adjustment_lines']:
            y = _draw_line(pdf, y, f"  - {float(item['amount']):,.2f} — {item['reason']}")
    else:
        y = _draw_line(pdf, y, f"Manual adjustment: {float(report['manual_adjustment']):,.2f}")

    y -= 0.4 * cm
    pdf.setFillColor(brand['primary'])
    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(2 * cm, y, f"Final amount: {float(report['final_amount']):,.2f}")
    y -= 0.7 * cm
    pdf.setFillColor(colors.black)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(2 * cm, y, f"Year-to-date total: {float(report['ytd_total']):,.2f}")

    pdf.setFillColor(colors.grey)
    pdf.setFont('Helvetica', 8)
    pdf.drawString(
        2 * cm,
        1.5 * cm,
        f"{brand['company_name']} Shareholders Profit Calculation System — confidential shareholder report",
    )
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def report_pdf_filename(report):
    safe_name = ''.join(ch for ch in report['shareholder_name'] if ch.isalnum() or ch in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_') or 'shareholder'
    return f"Akram_Sweets_Report_{report['period_label']}_{safe_name}.pdf"


def certificate_pdf_filename(report):
    safe_name = ''.join(ch for ch in report['shareholder_name'] if ch.isalnum() or ch in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_') or 'shareholder'
    cert_no = report.get('certificate_number', 'certificate').replace('/', '-')
    return f"Akram_Sweets_Certificate_{cert_no}_{safe_name}.pdf"


def generate_shareholder_certificate_pdf(report):
    brand = _brand_palette(report)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 1.5 * cm
    inner_margin = 2.2 * cm

    # Soft brand accent wash behind certificate content
    pdf.setFillColor(brand['accent'])
    pdf.rect(margin + 0.15 * cm, margin + 0.15 * cm, width - 2 * margin - 0.3 * cm, height - 2 * margin - 0.3 * cm, fill=1, stroke=0)

    pdf.setStrokeColor(brand['primary'])
    pdf.setLineWidth(3.2)
    pdf.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    pdf.setStrokeColor(brand['secondary'])
    pdf.setLineWidth(1.4)
    pdf.rect(inner_margin, inner_margin, width - 2 * inner_margin, height - 2 * inner_margin)

    # Corner accents in brand gold
    corner = 0.7 * cm
    for x, y, dx, dy in (
        (margin + 0.35 * cm, height - margin - 0.35 * cm, 1, -1),
        (width - margin - 0.35 * cm, height - margin - 0.35 * cm, -1, -1),
        (margin + 0.35 * cm, margin + 0.35 * cm, 1, 1),
        (width - margin - 0.35 * cm, margin + 0.35 * cm, -1, 1),
    ):
        pdf.setStrokeColor(brand['secondary'])
        pdf.setLineWidth(1.5)
        pdf.line(x, y, x + dx * corner, y)
        pdf.line(x, y, x, y + dy * corner)

    y = height - 2.6 * cm
    logo_h = _draw_brand_logo(pdf, brand['logo_path'], width / 2, y)
    if logo_h:
        y -= logo_h + 0.45 * cm
    else:
        y -= 0.2 * cm

    pdf.setFillColor(brand['primary'])
    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawCentredString(width / 2, y, brand['company_name'])
    y -= 0.75 * cm
    pdf.setFillColor(brand['secondary'])
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawCentredString(width / 2, y, 'Monthly Shareholder Certificate')
    y -= 0.5 * cm
    pdf.setFont('Helvetica', 10)
    pdf.setFillColor(colors.HexColor('#5A5A5A'))
    pdf.drawCentredString(width / 2, y, f"Certificate No: {report.get('certificate_number', 'N/A')}")
    y -= 0.4 * cm
    pdf.drawCentredString(width / 2, y, f"Period: {report.get('period_label', '')}")
    y -= 0.85 * cm

    pdf.setStrokeColor(brand['secondary'])
    pdf.setLineWidth(1.5)
    pdf.line(inner_margin + 0.5 * cm, y, width - inner_margin - 0.5 * cm, y)
    y -= 0.85 * cm

    pdf.setFillColor(colors.black)
    pdf.setFont('Helvetica', 11)
    pdf.drawCentredString(width / 2, y, 'This certifies the current shareholder')
    y -= 0.8 * cm
    pdf.setFont('Helvetica-Bold', 20)
    pdf.setFillColor(brand['primary'])
    pdf.drawCentredString(width / 2, y, report['shareholder_name'])
    y -= 0.55 * cm

    pdf.setFont('Helvetica', 10)
    pdf.setFillColor(colors.black)
    contact_bits = [report.get('shareholder_email') or '']
    if report.get('shareholder_phone'):
        contact_bits.append(str(report['shareholder_phone']))
    pdf.drawCentredString(width / 2, y, ' · '.join(bit for bit in contact_bits if bit))
    y -= 0.55 * cm

    role_bits = [f"{float(report['ownership_percent']):,.2f}% ownership"]
    if report.get('shareholder_is_owner'):
        role_bits.append('Company Owner')
    pdf.setFont('Helvetica-Bold', 11)
    pdf.setFillColor(brand['primary'])
    pdf.drawCentredString(width / 2, y, ' · '.join(role_bits))
    y -= 0.85 * cm

    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.black)
    pdf.drawCentredString(
        width / 2,
        y,
        f"and has been allocated the following amount for {report['period_label']}:",
    )
    y -= 0.85 * cm

    amount = float(report['final_amount'])
    pdf.setFont('Helvetica-Bold', 24)
    pdf.setFillColor(colors.HexColor('#46B277') if amount >= 0 else colors.HexColor('#E7366B'))
    pdf.drawCentredString(width / 2, y, f"${abs(amount):,.2f}")
    y -= 0.55 * cm
    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.black)
    pdf.drawCentredString(width / 2, y, 'Profit share' if amount >= 0 else 'Loss allocation')
    y -= 0.95 * cm

    details = [
        ('Company net P/L for month', f"${float(report['company_total']):,.2f}"),
        ('Base ownership share', f"${float(report['base_share']):,.2f}"),
        ('Year-to-date total', f"${float(report['ytd_total']):,.2f}"),
    ]
    if report.get('odoo_reference'):
        details.append(('Odoo reference', report['odoo_reference']))

    left_x = inner_margin + 1 * cm
    for label, value in details:
        pdf.setFont('Helvetica', 10)
        pdf.setFillColor(colors.black)
        pdf.drawString(left_x, y, label)
        pdf.setFont('Helvetica-Bold', 10)
        pdf.setFillColor(brand['primary'])
        pdf.drawRightString(width - inner_margin - 1 * cm, y, value)
        y -= 0.48 * cm

    current_shareholders = report.get('current_shareholders') or []
    if current_shareholders and y > 5.5 * cm:
        y -= 0.3 * cm
        pdf.setStrokeColor(brand['secondary'])
        pdf.setLineWidth(1)
        pdf.line(left_x, y, width - inner_margin - 1 * cm, y)
        y -= 0.5 * cm
        pdf.setFillColor(brand['primary'])
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(left_x, y, 'Current shareholders this month')
        y -= 0.42 * cm
        pdf.setFillColor(colors.black)
        for peer in current_shareholders:
            if y < 3.8 * cm:
                pdf.setFont('Helvetica-Oblique', 8)
                pdf.setFillColor(colors.grey)
                pdf.drawString(left_x, y, '…')
                break
            marker = '★ ' if peer.get('id') == report.get('shareholder_id') else '  '
            owner_tag = ' (Owner)' if peer.get('is_owner') else ''
            pdf.setFont('Helvetica', 9)
            pdf.setFillColor(brand['primary'] if peer.get('id') == report.get('shareholder_id') else colors.black)
            pdf.drawString(left_x, y, f"{marker}{peer['name']}{owner_tag}")
            pdf.setFont('Helvetica-Bold', 9)
            pdf.drawRightString(
                width - inner_margin - 1 * cm,
                y,
                f"{float(peer['ownership_percent']):,.2f}%",
            )
            y -= 0.38 * cm

    y -= 0.3 * cm
    issued = report.get('certificate_issued_at') or report.get('approved_at')
    approved = report.get('approved_at')
    pdf.setFont('Helvetica', 9)
    pdf.setFillColor(colors.black)
    if issued:
        pdf.drawString(left_x, y, f"Issued: {issued.strftime('%Y-%m-%d %H:%M')}")
        y -= 0.38 * cm
    if approved:
        pdf.drawString(
            left_x,
            y,
            f"Approved: {approved.strftime('%Y-%m-%d %H:%M')} by {report.get('approved_by', 'Management')}",
        )
        y -= 0.55 * cm

    pdf.setStrokeColor(brand['secondary'])
    pdf.line(left_x, y, width - inner_margin - 1 * cm, y)
    y -= 0.65 * cm
    pdf.setFont('Helvetica-Oblique', 8)
    pdf.setFillColor(colors.grey)
    pdf.drawCentredString(
        width / 2,
        y,
        'Generated automatically each month for the current shareholder upon period approval.',
    )
    pdf.setFillColor(brand['primary'])
    pdf.drawCentredString(
        width / 2,
        1.2 * cm,
        f"{brand['company_name']} Shareholders Profit Calculation System — confidential",
    )

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
