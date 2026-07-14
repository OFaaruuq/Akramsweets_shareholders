import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app, render_template

from apps.models.settings import SystemSetting
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


def _mail_settings():
    mail_server = SystemSetting.get('mail_server') or current_app.config.get('MAIL_SERVER')
    mail_port = int(SystemSetting.get('mail_port') or current_app.config.get('MAIL_PORT', 587))
    mail_user = SystemSetting.get('mail_username') or current_app.config.get('MAIL_USERNAME')
    mail_password = SystemSetting.get('mail_password') or current_app.config.get('MAIL_PASSWORD')
    mail_from = SystemSetting.get('mail_from') or current_app.config.get('MAIL_FROM', mail_user)
    return mail_server, mail_port, mail_user, mail_password, mail_from


def auto_email_enabled():
    value = SystemSetting.get('auto_email_on_approval', 'true')
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def send_shareholder_report(report_data, certificate_data):
    recipient = report_data['shareholder_email']
    subject = (
        f"Akram Sweets — Shareholder Update & Certificate — {report_data['period_label']}"
    )
    body_text = render_template('emails/shareholder_report.txt', report=report_data, certificate=certificate_data)
    body_html = render_template('emails/shareholder_report.html', report=report_data, certificate=certificate_data)

    mail_server, mail_port, mail_user, mail_password, mail_from = _mail_settings()

    report_pdf = generate_shareholder_report_pdf(report_data)
    report_name = report_pdf_filename(report_data)
    certificate_pdf = generate_shareholder_certificate_pdf(certificate_data)
    certificate_name = certificate_pdf_filename(certificate_data)

    if not mail_server:
        logger.info(
            'Email not configured. Would send to %s with report (%s) and certificate (%s).\n%s',
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
        }

    message = MIMEMultipart('mixed')
    message['From'] = mail_from
    message['To'] = recipient
    message['Subject'] = subject

    alternative = MIMEMultipart('alternative')
    alternative.attach(MIMEText(body_text, 'plain', 'utf-8'))
    alternative.attach(MIMEText(body_html, 'html', 'utf-8'))
    message.attach(alternative)

    report_attachment = MIMEApplication(report_pdf, _subtype='pdf')
    report_attachment.add_header('Content-Disposition', 'attachment', filename=report_name)
    message.attach(report_attachment)

    certificate_attachment = MIMEApplication(certificate_pdf, _subtype='pdf')
    certificate_attachment.add_header('Content-Disposition', 'attachment', filename=certificate_name)
    message.attach(certificate_attachment)

    with smtplib.SMTP(mail_server, mail_port) as server:
        server.starttls()
        if mail_user and mail_password:
            server.login(mail_user, mail_password)
        server.send_message(message)

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

    results = []
    sms_enabled = str(SystemSetting.get('sms_notifications_enabled', 'false')).lower() in ('1', 'true', 'yes', 'on')
    any_delivered = False

    for calculation in period.calculations:
        shareholder_name = calculation.shareholder.name
        try:
            certificate = issue_shareholder_certificate(period, calculation)
            report = build_shareholder_report(period, calculation)
            certificate_data = build_certificate_payload(period, calculation, certificate)
            email_result = send_shareholder_report(report, certificate_data)
            status = 'sent' if email_result.get('sent') else 'logged'
            mark_certificate_emailed(certificate, status=status)
            notification_result = notify_shareholder(certificate_data, email_result, sms_enabled)
            any_delivered = True
            results.append({
                'shareholder': shareholder_name,
                'email': email_result,
                'certificate_number': certificate.certificate_number,
                'notifications': notification_result,
                'ok': True,
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

    if any_delivered:
        period.reports_sent_at = datetime.utcnow()
        db.session.commit()
    return results
