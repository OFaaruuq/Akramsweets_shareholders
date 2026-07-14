from datetime import datetime

from apps.models.settings import SystemSetting
from apps.services.email_service import auto_email_enabled, distribute_period_reports


def get_report_delivery_day():
    value = SystemSetting.get('report_delivery_day')
    if not value:
        return None
    try:
        day = int(value)
    except (TypeError, ValueError):
        return None
    return day if 1 <= day <= 28 else None


def can_send_reports_now(as_of=None):
    delivery_day = get_report_delivery_day()
    if delivery_day is None:
        return True
    current_day = (as_of or datetime.utcnow()).day
    return current_day >= delivery_day


def send_period_reports(period, force=False, auto_on_approval=False):
    if period.status != period.STATUS_APPROVED:
        raise ValueError('Only approved periods can have reports sent.')

    if period.reports_sent_at and not force:
        raise ValueError('Reports were already sent. Use resend to send again.')

    if not force and not auto_on_approval and not can_send_reports_now():
        delivery_day = get_report_delivery_day()
        raise ValueError(
            f'Reports are scheduled for day {delivery_day} of each month. '
            'Use Send Reports Now to override the schedule.'
        )

    return distribute_period_reports(period)


def auto_send_period_reports(period):
    """Send shareholder emails and certificates immediately after approval."""
    if not auto_email_enabled():
        return []
    return send_period_reports(period, force=True, auto_on_approval=True)


def send_due_approved_reports():
    from apps.models.period import MonthlyPeriod
    from apps.services.certificate_service import ensure_approved_period_certificates

    # Always keep monthly certificates issued for current shareholders on approved periods.
    ensure_approved_period_certificates()

    if not can_send_reports_now():
        return []

    pending = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED).filter(
        MonthlyPeriod.reports_sent_at.is_(None)
    ).all()

    sent = []
    for period in pending:
        distribute_period_reports(period)
        sent.append(period)
    return sent
