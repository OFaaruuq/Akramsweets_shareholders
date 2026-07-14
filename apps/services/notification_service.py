import logging

logger = logging.getLogger(__name__)


def send_sms_notification(phone, message):
    """SMS/WhatsApp delivery stub (BRD §12 future channel). Logs until provider is configured."""
    if not phone:
        return {'sent': False, 'mode': 'skipped', 'reason': 'no phone number'}

    logger.info('SMS/WhatsApp (not configured) to %s: %s', phone, message[:120])
    return {'sent': False, 'mode': 'log', 'recipient': phone}


def notify_shareholder(report_data, email_result, sms_enabled):
    """Record / fan-out notifications after a shareholder email attempt."""
    results = {'email': email_result}

    company = report_data.get('company_name') or 'Akram Sweets'
    period_label = report_data.get('period_label') or 'period'
    if sms_enabled and report_data.get('shareholder_phone'):
        try:
            amount = float(report_data.get('final_amount') or 0)
        except (TypeError, ValueError):
            amount = 0.0
        sms_body = (
            f'{company} report {period_label}: '
            f'final amount {amount:,.2f}. '
            f'Certificate & full details sent by email.'
        )
        results['sms'] = send_sms_notification(report_data.get('shareholder_phone'), sms_body)

    if email_result.get('sent'):
        logger.info(
            'Shareholder %s notified by email (%s)',
            report_data.get('shareholder_name'),
            email_result.get('recipient'),
        )
    elif email_result.get('mode') == 'log':
        logger.info(
            'Shareholder %s notification logged only — configure SMTP in Settings → System',
            report_data.get('shareholder_name'),
        )

    return results
