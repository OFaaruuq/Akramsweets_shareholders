"""Top bar helpers: shareholder countries and live notifications."""

from __future__ import annotations

from datetime import datetime

from flask import url_for
from flask_login import current_user

from apps.models.audit import AuditLog
from apps.models.certificate import ShareholderCertificate
from apps.models.period import MonthlyPeriod
from apps.models.shareholder import Shareholder
from apps.services.shareholder_service import COUNTRY_FLAG_MAP, country_label


def _relative_time(moment):
    if not moment:
        return ''
    now = datetime.utcnow()
    delta = now - moment
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return 'just now'
    if seconds < 3600:
        mins = seconds // 60
        return f'{mins} min ago'
    if seconds < 86400:
        hours = seconds // 3600
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    days = seconds // 86400
    if days < 7:
        return f'{days} day{"s" if days != 1 else ""} ago'
    return moment.strftime('%Y-%m-%d')


def get_shareholder_countries():
    """Unique countries of active shareholders for the top-bar country picker."""
    rows = (
        Shareholder.query.filter_by(is_active=True)
        .filter(Shareholder.country_code.isnot(None))
        .filter(Shareholder.country_code != '')
        .order_by(Shareholder.country.asc(), Shareholder.name.asc())
        .all()
    )
    by_code = {}
    for shareholder in rows:
        code = (shareholder.country_code or '').lower()
        if not code:
            continue
        entry = by_code.setdefault(
            code,
            {
                'code': code,
                'name': shareholder.country or country_label(code),
                'flag': COUNTRY_FLAG_MAP.get(code, f'{code}.svg'),
                'count': 0,
                'shareholders': [],
            },
        )
        entry['count'] += 1
        entry['shareholders'].append({
            'id': shareholder.id,
            'name': shareholder.name,
            'ownership_hint': None,
        })

    countries = sorted(by_code.values(), key=lambda row: row['name'])
    selected = countries[0] if countries else {
        'code': 'so',
        'name': 'Somalia',
        'flag': 'so.svg',
        'count': 0,
        'shareholders': [],
    }
    return {
        'countries': countries,
        'selected': selected,
    }


def _notification_url(action, entity_type, entity_id):
    try:
        if entity_type == 'monthly_period' and entity_id:
            return url_for('periods.detail_period', period_id=entity_id)
        if entity_type == 'shareholder' and entity_id:
            return url_for('shareholders.edit_shareholder', shareholder_id=entity_id)
        if entity_type == 'system_settings':
            return url_for('app_settings.system_settings')
        if action == 'send_reports' and entity_id:
            return url_for('periods.detail_period', period_id=entity_id)
    except Exception:
        return None
    return None


def _format_notification(entry):
    actor = entry.user.full_name if entry.user else 'System'
    details = entry.details or ''
    title_map = {
        ('approve', 'monthly_period'): f'Period approved — {details}',
        ('send_reports', 'monthly_period'): f'Reports & certificates emailed — {details}',
        ('create', 'shareholder'): f'New shareholder — {details}',
        ('update', 'shareholder'): f'Shareholder updated — {details}',
        ('deactivate', 'shareholder'): f'Shareholder deactivated — {details}',
        ('create', 'special_arrangement'): f'Arrangement saved — {details}',
        ('update', 'system_settings'): 'Brand / system settings updated',
        ('correction_reopen', 'monthly_period'): f'Period reopened — {details}',
    }
    title = title_map.get((entry.action, entry.entity_type))
    if not title:
        title = details or f'{entry.action.replace("_", " ").title()} ({entry.entity_type})'

    return {
        'id': entry.id,
        'title': title,
        'actor': actor,
        'time_label': entry.created_at.strftime('%Y-%m-%d %H:%M') if entry.created_at else '',
        'relative': _relative_time(entry.created_at),
        'url': _notification_url(entry.action, entry.entity_type, entry.entity_id),
        'unread': True,
    }


def get_topbar_notifications(limit=8):
    """Build real notifications from recent audit activity."""
    if not getattr(current_user, 'is_authenticated', False):
        return {'items': [], 'count': 0}

    if current_user.is_shareholder():
        # Shareholder portal: certificate / report events for their account.
        certs = (
            ShareholderCertificate.query.filter_by(shareholder_id=current_user.shareholder_id)
            .order_by(ShareholderCertificate.generated_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for cert in certs:
            period = cert.period
            items.append({
                'id': f'cert-{cert.id}',
                'title': f'Certificate ready — {period.period_label if period else "period"}',
                'actor': 'Akram Sweets',
                'time_label': cert.generated_at.strftime('%Y-%m-%d %H:%M') if cert.generated_at else '',
                'relative': _relative_time(cert.generated_at),
                'url': url_for('portal.report_detail', period_id=cert.period_id) if cert.period_id else url_for('portal.reports'),
                'unread': cert.email_status == 'pending',
            })
        unread = sum(1 for item in items if item['unread'])
        return {'items': items, 'count': unread or len(items)}

    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    items = [_format_notification(entry) for entry in logs]

    # Include pending approved periods waiting for report email.
    pending = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
        .filter(MonthlyPeriod.reports_sent_at.is_(None))
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .limit(3)
        .all()
    )
    for period in pending:
        items.insert(0, {
            'id': f'pending-{period.id}',
            'title': f'Reports pending for {period.period_label}',
            'actor': 'System',
            'time_label': period.approved_at.strftime('%Y-%m-%d %H:%M') if period.approved_at else '',
            'relative': _relative_time(period.approved_at),
            'url': url_for('periods.detail_period', period_id=period.id),
            'unread': True,
        })

    items = items[:limit]
    unread = sum(1 for item in items if item.get('unread'))
    return {'items': items, 'count': unread}
