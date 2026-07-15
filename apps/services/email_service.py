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
EMAIL_HEADER_CID = 'email-header'


def _mail_settings():
    mail_server = (SystemSetting.get('mail_server') or current_app.config.get('MAIL_SERVER') or '').strip()
    mail_port = int(SystemSetting.get('mail_port') or current_app.config.get('MAIL_PORT', 587) or 587)
    mail_user = (SystemSetting.get('mail_username') or current_app.config.get('MAIL_USERNAME') or '').strip() or None
    raw_password = SystemSetting.get('mail_password') or current_app.config.get('MAIL_PASSWORD') or None
    # Gmail app passwords are often pasted with spaces — strip them for SMTP auth
    mail_password = ''.join(str(raw_password).split()) if raw_password else None
    mail_from = (
        SystemSetting.get('mail_from')
        or current_app.config.get('MAIL_FROM')
        or current_app.config.get('MAIL_DEFAULT_SENDER')
        or mail_user
        or ''
    ).strip()
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    if isinstance(use_tls, str):
        use_tls = use_tls.lower() in ('1', 'true', 'yes', 'on')
    return mail_server, mail_port, mail_user, mail_password, mail_from, bool(use_tls)


def mail_is_configured():
    mail_server, _, mail_user, mail_password, mail_from, _ = _mail_settings()
    return bool(mail_server and mail_from and mail_user and mail_password)


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


def _email_header_flags():
    from apps.services.media_service import get_slot_image

    item = get_slot_image('email_header')
    return bool(item and item.get('filesystem_path')), EMAIL_HEADER_CID


def _attach_email_header(related_part):
    """Embed optional admin-managed email header banner."""
    from apps.services.media_service import get_slot_image

    item = get_slot_image('email_header')
    if not item or not item.get('filesystem_path'):
        return False
    path = Path(item['filesystem_path'])
    if not path.is_file():
        return False
    data = path.read_bytes()
    mime_type, _ = mimetypes.guess_type(str(path))
    subtype = 'png'
    if mime_type and mime_type.startswith('image/'):
        subtype = mime_type.split('/', 1)[1]
    image = MIMEImage(data, _subtype=subtype)
    image.add_header('Content-ID', f'<{EMAIL_HEADER_CID}>')
    image.add_header('Content-Disposition', 'inline', filename=path.name)
    related_part.attach(image)
    return True


def _build_from_header(mail_from, company_name):
    if not mail_from:
        return company_name
    if '<' in mail_from and '>' in mail_from:
        return mail_from
    return formataddr((company_name, mail_from))


def _send_smtp(message, mail_server, mail_port, mail_user, mail_password, use_tls=True):
    context = ssl.create_default_context()
    if mail_port == 465:
        with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
            if mail_user and mail_password:
                server.login(mail_user, mail_password)
            server.send_message(message)
        return

    with smtplib.SMTP(mail_server, mail_port, timeout=60) as server:
        server.ehlo()
        if use_tls:
            try:
                server.starttls(context=context)
                server.ehlo()
            except smtplib.SMTPException:
                # Some local/dev SMTP servers do not support STARTTLS.
                pass
        if mail_user and mail_password:
            server.login(mail_user, mail_password)
        server.send_message(message)


def send_login_otp_email(user, code, expires_minutes=10):
    """Email a login verification OTP to the user."""
    recipient = (user.email or '').strip()
    if not recipient or '@' not in recipient:
        return {'sent': False, 'mode': 'skipped', 'reason': 'missing_or_invalid_email'}

    brand = _brand_for_email()
    company_name = brand.get('company_name') or 'Akram Sweets'
    subject = f'{company_name} — Login verification code'
    has_email_header, email_header_cid = _email_header_flags()
    body_text = render_template(
        'emails/login_otp.txt',
        user=user,
        code=code,
        expires_minutes=expires_minutes,
        company_name=company_name,
    )
    body_html = render_template(
        'emails/login_otp.html',
        user=user,
        code=code,
        expires_minutes=expires_minutes,
        company_name=company_name,
        brand=brand,
        logo_cid=LOGO_CID,
        has_logo=bool(brand.get('logo_filesystem_path')),
        has_email_header=has_email_header,
        email_header_cid=email_header_cid,
    )

    mail_server, mail_port, mail_user, mail_password, mail_from, use_tls = _mail_settings()
    if not mail_server or not mail_from or not mail_user or not mail_password:
        logger.error('SMTP is not configured — cannot send login OTP to %s', recipient)
        return {
            'sent': False,
            'mode': 'error',
            'reason': 'smtp_not_configured',
            'recipient': recipient,
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
    if has_email_header:
        _attach_email_header(related)
    message.attach(related)

    try:
        _send_smtp(message, mail_server, mail_port, mail_user, mail_password, use_tls=use_tls)
    except Exception as exc:
        logger.exception('Failed to send login OTP to %s', recipient)
        return {
            'sent': False,
            'mode': 'error',
            'reason': 'smtp_error',
            'error': str(exc),
            'recipient': recipient,
        }

    logger.info('Login OTP emailed to %s', recipient)
    return {'sent': True, 'mode': 'smtp', 'recipient': recipient}


def send_system_notice(
    recipient,
    subject,
    *,
    title,
    paragraphs,
    cta_label=None,
    cta_endpoint=None,
    cta_kwargs=None,
):
    """Send a branded transactional notice (staff invite, review alert, etc.)."""
    recipient = (recipient or '').strip()
    if not recipient or '@' not in recipient:
        return {'sent': False, 'mode': 'skipped', 'reason': 'missing_or_invalid_email'}

    brand = _brand_for_email()
    company_name = brand.get('company_name') or 'Company'
    has_email_header, email_header_cid = _email_header_flags()
    cta_url = None
    if cta_endpoint:
        try:
            from flask import url_for

            cta_url = url_for(cta_endpoint, _external=True, **(cta_kwargs or {}))
        except Exception:
            cta_url = None

    body_text = render_template(
        'emails/system_notice.txt',
        company_name=company_name,
        title=title,
        paragraphs=paragraphs,
        cta_label=cta_label,
        cta_url=cta_url,
    )
    body_html = render_template(
        'emails/system_notice.html',
        company_name=company_name,
        title=title,
        paragraphs=paragraphs,
        cta_label=cta_label,
        cta_url=cta_url,
        brand=brand,
        logo_cid=LOGO_CID,
        has_logo=bool(brand.get('logo_filesystem_path')),
        has_email_header=has_email_header,
        email_header_cid=email_header_cid,
    )

    mail_server, mail_port, mail_user, mail_password, mail_from, use_tls = _mail_settings()
    if not mail_server or not mail_from:
        logger.info('Email not configured. Would notify %s:\n%s', recipient, body_text)
        return {
            'sent': False,
            'mode': 'log',
            'recipient': recipient,
            'reason': 'smtp_not_configured',
        }

    message = MIMEMultipart('mixed')
    message['From'] = _build_from_header(mail_from, company_name)
    message['To'] = recipient
    message['Subject'] = f'{company_name} — {subject}' if company_name not in subject else subject

    related = MIMEMultipart('related')
    alternative = MIMEMultipart('alternative')
    alternative.attach(MIMEText(body_text, 'plain', 'utf-8'))
    alternative.attach(MIMEText(body_html, 'html', 'utf-8'))
    related.attach(alternative)
    _attach_brand_logo(related, brand)
    if has_email_header:
        _attach_email_header(related)
    message.attach(related)

    try:
        _send_smtp(message, mail_server, mail_port, mail_user, mail_password, use_tls=use_tls)
    except Exception as exc:
        logger.exception('Failed to send system notice to %s', recipient)
        return {
            'sent': False,
            'mode': 'error',
            'reason': 'smtp_error',
            'error': str(exc),
            'recipient': recipient,
        }

    logger.info('System notice emailed to %s (%s)', recipient, title)
    return {'sent': True, 'mode': 'smtp', 'recipient': recipient}


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
    has_email_header, email_header_cid = _email_header_flags()
    currency_symbol = (
        report_data.get('currency_symbol')
        or (certificate_data or {}).get('cert_currency_symbol')
        or '$'
    )
    body_text = render_template(
        'emails/shareholder_report.txt',
        report=report_data,
        certificate=certificate_data,
        company_name=company_name,
        currency_symbol=currency_symbol,
    )
    body_html = render_template(
        'emails/shareholder_report.html',
        report=report_data,
        certificate=certificate_data,
        company_name=company_name,
        currency_symbol=currency_symbol,
        logo_cid=logo_cid,
        has_logo=bool(brand.get('logo_filesystem_path')),
        has_email_header=has_email_header,
        email_header_cid=email_header_cid,
        brand=brand,
    )

    mail_server, mail_port, mail_user, mail_password, mail_from, use_tls = _mail_settings()

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
    if has_email_header:
        _attach_email_header(related)
    message.attach(related)

    report_attachment = MIMEApplication(report_pdf, _subtype='pdf')
    report_attachment.add_header('Content-Disposition', 'attachment', filename=report_name)
    message.attach(report_attachment)

    certificate_attachment = MIMEApplication(certificate_pdf, _subtype='pdf')
    certificate_attachment.add_header('Content-Disposition', 'attachment', filename=certificate_name)
    message.attach(certificate_attachment)

    _send_smtp(message, mail_server, mail_port, mail_user, mail_password, use_tls=use_tls)
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
            # Pass report payload (has period_label / final_amount / phone) for SMS + logging
            notification_result = notify_shareholder(report, email_result, sms_enabled)
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
