import logging

logger = logging.getLogger(__name__)


def send_sms_notification(phone, message):
    """SMS/WhatsApp delivery stub (BRD §12 future channel). Logs until provider is configured."""
    if not phone:
        return {'sent': False, 'mode': 'skipped', 'reason': 'no phone number'}

    logger.info('SMS/WhatsApp (not configured) to %s: %s', phone, message[:120])
    return {'sent': False, 'mode': 'log', 'recipient': phone}


def notify_shareholder(report_data, email_result, sms_enabled):
    results = {'email': email_result}
    if sms_enabled and report_data.get('shareholder_phone'):
        sms_body = (
            f'Akram Sweets report {report_data["period_label"]}: '
            f'final amount {float(report_data["final_amount"]):,.2f}. '
            f'Full details sent by email.'
        )
        results['sms'] = send_sms_notification(report_data.get('shareholder_phone'), sms_body)
    return results
