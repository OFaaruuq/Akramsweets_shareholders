import logging
import mimetypes
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from flask import current_app, render_template

from apps.models.settings import SystemSetting
from apps.services.brand_service import ensure_default_logo, get_brand_settings
from apps.services.certificate_service import (
    build_certificate_payload,
    issue_shareholder_certificate,
    mark_certificate_emailed,
)
from apps.services.notification_service import notify_shareholder
from apps.services.pdf_service import (
    certificate_pdf_filename,
    generate_shareholder_certificate_pdf,
    generate_shareholder_report_pdf,
    report_pdf_filename,
)

logger = logging.getLogger(__name__)

LOGO_CID = 'brand-logo'


def _mail_settings():
    mail_server = (SystemSetting.get('mail_server') or current_app.config.get('MAIL_SERVER') or '').strip()
    mail_port = int(SystemSetting.get('mail_port') or current_app.config.get('MAIL_PORT', 587) or 587)
    mail_user = (SystemSetting.get('mail_username') or current_app.config.get('MAIL_USERNAME') or '').strip() or None
    mail_password = SystemSetting.get('mail_password') or current_app.config.get('MAIL_PASSWORD') or None
    mail_from = (SystemSetting.get('mail_from') or current_app.config.get('MAIL_FROM') or mail_user or '').strip()
    return mail_server, mail_port, mail_user, mail_password, mail_from


def mail_is_configured():
    mail_server, _, _, _, mail_from = _mail_settings()
    return bool(mail_server and mail_from)


def auto_email_enabled():
    value = SystemSetting.get('auto_email_on_approval', 'true')
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def _brand_for_email():
    ensure_default_logo()
    return get_brand_settings()


def _attach_brand_logo(related_part, brand):
    """Embed the company logo as a CID image so HTML emails show branding offline."""
    logo_path = brand.get('logo_filesystem_path')
    if not logo_path:
        return False

    path = Path(logo_path)
    if not path.is_file():
        return False

    data = path.read_bytes()
    mime_type, _ = mimetypes.guess_type(str(path))
    subtype = 'png'
    if mime_type and mime_type.startswith('image/'):
        subtype = mime_type.split('/', 1)[1]

    image = MIMEImage(data, _subtype=subtype)
    image.add_header('Content-ID', f'<{LOGO_CID}>')
    image.add_header('Content-Disposition', 'inline', filename=path.name)
    related_part.attach(image)
    return True


def _build_from_header(mail_from, company_name):
    if not mail_from:
        return company_name
    if '<' in mail_from and '>' in mail_from:
        return mail_from
    return formataddr((company_name, mail_from))


def _send_smtp(message, mail_server, mail_port, mail_user, mail_password):
    context = ssl.create_default_context()
    if mail_port == 465:
        with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
            if mail_user and mail_password:
                server.login(mail_user, mail_password)
            server.send_message(message)
        return

    with smtplib.SMTP(mail_server, mail_port, timeout=60) as server:
        server.ehlo()
        try:
            server.starttls(context=context)
            server.ehlo()
        except smtplib.SMTPException:
            # Some local/dev SMTP servers do not support STARTTLS.
            pass
        if mail_user and mail_password:
            server.login(mail_user, mail_password)
        server.send_message(message)


def send_shareholder_report(report_data, certificate_data):
    brand = _brand_for_email()
    company_name = (
        (certificate_data or {}).get('company_name')
        or report_data.get('company_name')
        or brand['company_name']
    )
    recipient = (report_data.get('shareholder_email') or '').strip()
    if not recipient or '@' not in recipient:
        logger.warning(
            'Skipping shareholder email — missing/invalid address for %s',
            report_data.get('shareholder_name'),
        )
        return {
            'sent': False,
            'mode': 'skipped',
            'reason': 'missing_or_invalid_email',
            'recipient': recipient or None,
        }

    subject = f"{company_name} — Shareholder Update & Certificate — {report_data['period_label']}"
    logo_cid = LOGO_CID
    body_text = render_template(
        'emails/shareholder_report.txt',
        report=report_data,
        certificate=certificate_data,
        company_name=company_name,
    )
    body_html = render_template(
        'emails/shareholder_report.html',
        report=report_data,
        certificate=certificate_data,
        company_name=company_name,
        logo_cid=logo_cid,
        has_logo=bool(brand.get('logo_filesystem_path')),
        brand=brand,
    )

    mail_server, mail_port, mail_user, mail_password, mail_from = _mail_settings()

    report_pdf = generate_shareholder_report_pdf(report_data)
    report_name = report_pdf_filename(report_data)
    certificate_pdf = generate_shareholder_certificate_pdf(certificate_data)
    certificate_name = certificate_pdf_filename(certificate_data)

    if not mail_server or not mail_from:
        logger.info(
            'Email not configured. Would notify %s with report (%s) and certificate (%s).\n%s',
            recipient,
            report_name,
            certificate_name,
            body_text,
        )
        return {
            'sent': False,
            'mode': 'log',
            'recipient': recipient,
            'report_pdf': report_name,
            'certificate_pdf': certificate_name,
            'reason': 'smtp_not_configured',
        }

    message = MIMEMultipart('mixed')
    message['From'] = _build_from_header(mail_from, company_name)
    message['To'] = recipient
    message['Subject'] = subject

    related = MIMEMultipart('related')
    alternative = MIMEMultipart('alternative')
    alternative.attach(MIMEText(body_text, 'plain', 'utf-8'))
    alternative.attach(MIMEText(body_html, 'html', 'utf-8'))
    related.attach(alternative)
    _attach_brand_logo(related, brand)
    message.attach(related)

    report_attachment = MIMEApplication(report_pdf, _subtype='pdf')
    report_attachment.add_header('Content-Disposition', 'attachment', filename=report_name)
    message.attach(report_attachment)

    certificate_attachment = MIMEApplication(certificate_pdf, _subtype='pdf')
    certificate_attachment.add_header('Content-Disposition', 'attachment', filename=certificate_name)
    message.attach(certificate_attachment)

    _send_smtp(message, mail_server, mail_port, mail_user, mail_password)
    logger.info(
        'Shareholder notification emailed to %s (period %s, certificate %s)',
        recipient,
        report_data.get('period_label'),
        (certificate_data or {}).get('certificate_number'),
    )

    return {
        'sent': True,
        'mode': 'smtp',
        'recipient': recipient,
        'report_pdf': report_name,
        'certificate_pdf': certificate_name,
    }


def distribute_period_reports(period):
    from datetime import datetime

    from apps import db
    from apps.services.report_service import build_shareholder_report

    # Guarantee brand logo exists before generating certificate/report PDFs.
    ensure_default_logo()

    results = []
    sms_enabled = str(SystemSetting.get('sms_notifications_enabled', 'false')).lower() in ('1', 'true', 'yes', 'on')
    any_smtp_sent = False

    for calculation in period.calculations:
        shareholder_name = calculation.shareholder.name
        try:
            certificate = issue_shareholder_certificate(period, calculation)
            report = build_shareholder_report(period, calculation)
            certificate_data = build_certificate_payload(period, calculation, certificate)
            email_result = send_shareholder_report(report, certificate_data)

            if email_result.get('sent'):
                status = 'sent'
                any_smtp_sent = True
            elif email_result.get('mode') == 'skipped':
                status = 'skipped'
            elif email_result.get('mode') == 'log':
                status = 'logged'
            else:
                status = 'failed'

            mark_certificate_emailed(certificate, status=status)
            notification_result = notify_shareholder(certificate_data, email_result, sms_enabled)
            results.append({
                'shareholder': shareholder_name,
                'email': email_result,
                'certificate_number': certificate.certificate_number,
                'notifications': notification_result,
                'ok': bool(email_result.get('sent') or email_result.get('mode') == 'log'),
            })
        except Exception as exc:
            logger.exception(
                'Failed to email shareholder update for %s (period %s)',
                shareholder_name,
                period.id,
            )
            results.append({
                'shareholder': shareholder_name,
                'email': {'sent': False, 'mode': 'error', 'error': str(exc)},
                'certificate_number': None,
                'notifications': {},
                'ok': False,
            })

    # Only mark the period as emailed when at least one real SMTP delivery succeeded.
    # Log-only / skipped runs stay pending so the scheduler can retry after SMTP is configured.
    if any_smtp_sent:
        period.reports_sent_at = datetime.utcnow()
        db.session.commit()
    return results
