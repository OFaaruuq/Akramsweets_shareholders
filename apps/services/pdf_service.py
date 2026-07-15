import logging
from io import BytesIO
from pathlib import Path

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
    ensure_default_logo,
    get_brand_settings,
)

logger = logging.getLogger(__name__)


def _brand_palette(report=None):
    report = report or {}
    try:
        ensure_default_logo()
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

    if logo_path and not Path(str(logo_path)).is_file():
        logger.warning('Brand logo file missing at %s — regenerating default', logo_path)
        try:
            logo_path = ensure_default_logo()
        except Exception:
            logo_path = None

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


def _brand_slug(company_name):
    safe = ''.join(ch for ch in (company_name or DEFAULT_COMPANY_NAME) if ch.isalnum() or ch in (' ', '-', '_'))
    return safe.strip().replace(' ', '_') or 'Company'


def _draw_brand_logo(pdf, logo_path, center_x, top_y, max_width=4.2 * cm, max_height=2.6 * cm):
    """Draw the company logo centered; returns drawn height (0 if unavailable)."""
    if not logo_path:
        return 0
    path = Path(str(logo_path))
    if not path.is_file():
        logger.warning('Cannot draw brand logo — file not found: %s', logo_path)
        return 0
    try:
        image = ImageReader(str(path))
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
        logger.exception('Failed to draw brand logo from %s', logo_path)
        return 0


def _draw_line(c, y, text, bold=False):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', 10)
    c.setFillColor(colors.black)
    c.drawString(2 * cm, y, text)
    return y - 0.55 * cm


def generate_shareholder_report_pdf(report):
    brand = _brand_palette(report)
    currency = report.get('currency_symbol') or report.get('cert_currency_symbol') or '$'
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

    def money(amount):
        value = float(amount or 0)
        sign = '-' if value < 0 else ''
        return f'{sign}{currency}{abs(value):,.2f}'

    generated = report['generated_at'].strftime('%Y-%m-%d %H:%M') if report.get('generated_at') else 'Draft'
    y = _draw_line(pdf, y, f"Generated: {generated}")
    y = _draw_line(pdf, y, f"Shareholder: {report['shareholder_name']} ({report['shareholder_email']})")
    y = _draw_line(pdf, y, f"Company total for month: {money(report['company_total'])}")
    if report.get('odoo_reference'):
        y = _draw_line(pdf, y, f"Odoo reference: {report['odoo_reference']}")
    y -= 0.3 * cm

    y = _draw_line(pdf, y, f"Ownership: {float(report['ownership_percent']):,.2f}%", bold=True)
    y = _draw_line(pdf, y, f"Base share: {money(report['base_share'])}")

    if report.get('arrangements_applied'):
        y = _draw_line(pdf, y, 'Special arrangements:', bold=True)
        for item in report['arrangements_applied']:
            y = _draw_line(
                pdf,
                y,
                f"  - {item['name']} ({float(item['percent']):,.2f}%): "
                f"{money(item['amount'])} — {item['description']}",
            )
    else:
        y = _draw_line(pdf, y, f"Arrangement deduction: {money(report['arrangement_deduction'])}")
        y = _draw_line(pdf, y, f"Arrangement received: {money(report['arrangement_received'])}")

    if report.get('adjustment_lines'):
        y = _draw_line(pdf, y, 'Manual adjustments:', bold=True)
        for item in report['adjustment_lines']:
            y = _draw_line(pdf, y, f"  - {money(item['amount'])} — {item['reason']}")
    else:
        y = _draw_line(pdf, y, f"Manual adjustment: {money(report['manual_adjustment'])}")

    y -= 0.4 * cm
    pdf.setFillColor(brand['primary'])
    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(2 * cm, y, f"Final amount: {money(report['final_amount'])}")
    y -= 0.7 * cm
    pdf.setFillColor(colors.black)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(2 * cm, y, f"Year-to-date total: {money(report['ytd_total'])}")

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
    brand = _brand_palette(report)
    safe_name = ''.join(ch for ch in report['shareholder_name'] if ch.isalnum() or ch in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_') or 'shareholder'
    return f"{_brand_slug(brand['company_name'])}_Report_{report['period_label']}_{safe_name}.pdf"


def certificate_pdf_filename(report):
    brand = _brand_palette(report)
    safe_name = ''.join(ch for ch in report['shareholder_name'] if ch.isalnum() or ch in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_') or 'shareholder'
    cert_no = report.get('certificate_number', 'certificate').replace('/', '-')
    return f"{_brand_slug(brand['company_name'])}_Certificate_{cert_no}_{safe_name}.pdf"


def generate_shareholder_certificate_pdf(report):
    brand = _brand_palette(report)
    currency = report.get('cert_currency_symbol') or '$'
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

    y = height - 2.5 * cm
    # Company brand mark — logo is required identity on every certificate
    logo_h = _draw_brand_logo(pdf, brand['logo_path'], width / 2, y, max_width=4.8 * cm, max_height=3.0 * cm)
    if logo_h:
        y -= logo_h + 0.4 * cm
    else:
        y -= 0.15 * cm

    pdf.setFillColor(brand['primary'])
    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawCentredString(width / 2, y, brand['company_name'])
    y -= 0.55 * cm
    pdf.setFillColor(brand['secondary'])
    pdf.setFont('Helvetica', 9)
    pdf.drawCentredString(width / 2, y, report.get('cert_subtitle') or 'Official Company Brand Certificate')
    y -= 0.55 * cm
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawCentredString(width / 2, y, report.get('cert_title') or 'Monthly Shareholder Certificate')
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
    pdf.drawCentredString(width / 2, y, report.get('cert_intro_text') or 'This certifies the current shareholder')
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
        role_bits.append(report.get('cert_owner_label') or 'Company Owner')
    pdf.setFont('Helvetica-Bold', 11)
    pdf.setFillColor(brand['primary'])
    pdf.drawCentredString(width / 2, y, ' · '.join(role_bits))
    y -= 0.85 * cm

    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.black)
    allocation = report.get('cert_allocation_text') or (
        f"and has been allocated the following amount for {report['period_label']}:"
    )
    pdf.drawCentredString(width / 2, y, allocation)
    y -= 0.85 * cm

    amount = float(report['final_amount'])
    pdf.setFont('Helvetica-Bold', 24)
    pdf.setFillColor(colors.HexColor('#46B277') if amount >= 0 else colors.HexColor('#E7366B'))
    pdf.drawCentredString(width / 2, y, f"{currency}{abs(amount):,.2f}")
    y -= 0.55 * cm
    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.black)
    if amount >= 0:
        amount_label = report.get('cert_profit_label') or 'Profit share'
    else:
        amount_label = report.get('cert_loss_label') or 'Loss allocation'
    pdf.drawCentredString(width / 2, y, amount_label)
    y -= 0.95 * cm

    details = [
        (report.get('cert_label_company_pl') or 'Company net P/L for month', f"{currency}{float(report['company_total']):,.2f}"),
        (report.get('cert_label_base_share') or 'Base ownership share', f"{currency}{float(report['base_share']):,.2f}"),
        (report.get('cert_label_ytd') or 'Year-to-date total', f"{currency}{float(report['ytd_total']):,.2f}"),
    ]
    if report.get('odoo_reference') and report.get('cert_show_odoo_reference', True):
        details.append((report.get('cert_label_odoo') or 'Odoo reference', report['odoo_reference']))

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
        pdf.drawString(left_x, y, report.get('cert_roster_title') or 'Current shareholders this month')
        y -= 0.42 * cm
        pdf.setFillColor(colors.black)
        owner_tag_label = report.get('cert_owner_label') or 'Owner'
        for peer in current_shareholders:
            if y < 3.8 * cm:
                pdf.setFont('Helvetica-Oblique', 8)
                pdf.setFillColor(colors.grey)
                pdf.drawString(left_x, y, '…')
                break
            marker = '★ ' if peer.get('id') == report.get('shareholder_id') else '  '
            owner_tag = f' ({owner_tag_label})' if peer.get('is_owner') else ''
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

    legal_text = (report.get('cert_legal_text') or '').strip()
    if legal_text and y > 4.2 * cm:
        pdf.setFont('Helvetica', 8)
        pdf.setFillColor(colors.HexColor('#5A5A5A'))
        # Wrap legal text roughly to ~90 chars per line
        words = legal_text.split()
        line = ''
        for word in words:
            candidate = f'{line} {word}'.strip()
            if len(candidate) > 95:
                pdf.drawCentredString(width / 2, y, line)
                y -= 0.32 * cm
                line = word
                if y < 3.6 * cm:
                    break
            else:
                line = candidate
        if line and y >= 3.6 * cm:
            pdf.drawCentredString(width / 2, y, line)
            y -= 0.45 * cm

    sig_name = (report.get('cert_signature_name') or '').strip()
    sig_title = (report.get('cert_signature_title') or '').strip()
    sig_path = report.get('cert_signature_image_path')
    if (sig_name or sig_title or sig_path) and y > 3.2 * cm:
        sig_x = width - inner_margin - 1 * cm
        if sig_path:
            try:
                from reportlab.lib.utils import ImageReader

                img = ImageReader(sig_path)
                iw, ih = img.getSize()
                max_w, max_h = 4.2 * cm, 1.6 * cm
                scale = min(max_w / float(iw), max_h / float(ih), 1.0)
                draw_w, draw_h = iw * scale, ih * scale
                pdf.drawImage(
                    img,
                    sig_x - draw_w,
                    y - draw_h + 0.2 * cm,
                    width=draw_w,
                    height=draw_h,
                    mask='auto',
                    preserveAspectRatio=True,
                )
                y -= draw_h + 0.15 * cm
            except Exception:
                pass
        pdf.setStrokeColor(brand['secondary'])
        pdf.setLineWidth(1)
        pdf.line(sig_x - 4.5 * cm, y, sig_x, y)
        y -= 0.35 * cm
        pdf.setFillColor(brand['primary'])
        pdf.setFont('Helvetica-Bold', 9)
        if sig_name:
            pdf.drawRightString(sig_x, y, sig_name)
            y -= 0.3 * cm
        if sig_title:
            pdf.setFont('Helvetica', 8)
            pdf.setFillColor(colors.HexColor('#5A5A5A'))
            pdf.drawRightString(sig_x, y, sig_title)
            y -= 0.4 * cm

    pdf.setStrokeColor(brand['secondary'])
    pdf.line(left_x, y, width - inner_margin - 1 * cm, y)
    y -= 0.65 * cm
    pdf.setFont('Helvetica-Oblique', 8)
    pdf.setFillColor(colors.grey)
    pdf.drawCentredString(
        width / 2,
        y,
        report.get('cert_footer_disclaimer')
        or 'Generated automatically each month for the current shareholder upon period approval.',
    )
    confidential = report.get('cert_footer_confidential') or (
        f"{brand['company_name']} Shareholders Profit Calculation System — confidential"
    )
    pdf.setFillColor(brand['primary'])
    pdf.drawCentredString(width / 2, 1.2 * cm, confidential)

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
