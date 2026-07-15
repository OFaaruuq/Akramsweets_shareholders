"""Top bar helpers: shareholder countries and comprehensive notifications."""

from __future__ import annotations

from datetime import datetime, timedelta

from flask import url_for
from flask_login import current_user
from sqlalchemy import or_

from apps.models.audit import AuditLog
from apps.models.certificate import ShareholderCertificate
from apps.models.period import MonthlyPeriod
from apps.models.shareholder import Shareholder
from apps.services.shareholder_service import COUNTRY_FLAG_MAP, country_label

# Auth noise stays in the audit trail but is excluded from the bell dropdown.
TOPBAR_EXCLUDED_ACTIONS = frozenset({'login', 'logout', 'otp_sent', 'otp_resend'})


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


def get_shareholder_countries(selected_code=None):
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
    selected = None
    wanted = (selected_code or '').lower()
    if wanted:
        selected = next((row for row in countries if row['code'] == wanted), None)
    if not selected:
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
        if entity_type in ('monthly_period', 'certificate') and entity_id:
            return url_for('periods.detail_period', period_id=entity_id)
        if entity_type == 'manual_adjustment' and entity_id:
            from apps.models.period import ManualAdjustment

            adjustment = ManualAdjustment.query.get(entity_id)
            if adjustment:
                return url_for('periods.detail_period', period_id=adjustment.period_id)
            return url_for('periods.list_periods')
        if entity_type == 'shareholder' and entity_id:
            return url_for('shareholders.edit_shareholder', shareholder_id=entity_id)
        if entity_type == 'special_arrangement':
            if entity_id:
                return url_for('app_settings.edit_arrangement', arrangement_id=entity_id)
            return url_for('app_settings.arrangements')
        if entity_type == 'media_image':
            return url_for('app_settings.manage_images')
        if entity_type == 'system_settings':
            return url_for('app_settings.system_settings')
        if entity_type == 'dashboard_settings':
            return url_for('app_settings.dashboard_settings')
        if entity_type == 'staff_user':
            if entity_id:
                return url_for('users.edit_user', user_id=entity_id)
            return url_for('users.list_users')
        if entity_type == 'shareholder_portal_user' and entity_id:
            from apps.models.user import User

            portal_user = User.query.get(entity_id)
            if portal_user and portal_user.shareholder_id:
                return url_for('shareholders.edit_shareholder', shareholder_id=portal_user.shareholder_id)
            return url_for('shareholders.list_shareholders')
        if entity_type == 'user' and action == 'password_change':
            return url_for('auth.account')
        if entity_type == 'user' and action in ('avatar_update', 'avatar_remove'):
            return url_for('auth.account')
        if action == 'send_reports' and entity_id:
            return url_for('periods.detail_period', period_id=entity_id)
    except Exception:
        return None
    return None


def _format_notification(entry, unread_cutoff):
    actor = entry.user.full_name if entry.user else 'System'
    details = (entry.details or '').strip()
    title_map = {
        ('create', 'monthly_period'): f'Period created — {details}',
        ('update', 'monthly_period'): f'Period updated — {details}',
        ('recalculate', 'monthly_period'): f'Period recalculated — {details}',
        ('submit_review', 'monthly_period'): f'Submitted for review — {details}',
        ('approve', 'monthly_period'): f'Period approved — {details}',
        ('send_reports', 'monthly_period'): f'Reports & certificates emailed — {details}',
        ('correction_reopen', 'monthly_period'): f'Period reopened — {details}',
        ('adjustment', 'manual_adjustment'): f'Manual adjustment — {details}',
        ('issue', 'certificate'): f'Certificates issued — {details}',
        ('create', 'shareholder'): f'New shareholder — {details}',
        ('update', 'shareholder'): f'Shareholder updated — {details}',
        ('deactivate', 'shareholder'): f'Shareholder deactivated — {details}',
        ('create', 'special_arrangement'): f'Arrangement created — {details}',
        ('update', 'special_arrangement'): f'Arrangement updated — {details}',
        ('deactivate', 'special_arrangement'): f'Arrangement deactivated — {details}',
        ('activate', 'special_arrangement'): f'Arrangement activated — {details}',
        ('update', 'system_settings'): details or 'Brand / system settings updated',
        ('update', 'dashboard_settings'): details or 'Dashboard KPI figures updated',
        ('create', 'staff_user'): f'Staff user created — {details}',
        ('update', 'staff_user'): f'Staff user updated — {details}',
        ('create', 'shareholder_portal_user'): f'Portal access granted — {details}',
        ('update', 'shareholder_portal_user'): f'Portal access updated — {details}',
        ('deactivate', 'shareholder_portal_user'): f'Portal access deactivated — {details}',
        ('update', 'media_image'): details or 'Application images updated',
        ('create', 'media_image'): details or 'Application image uploaded',
        ('delete', 'media_image'): details or 'Application image deleted',
        ('password_change', 'user'): 'Password changed',
        ('avatar_update', 'user'): 'Profile photo updated',
        ('avatar_remove', 'user'): 'Profile photo removed',
        ('notify', 'management'): details or 'Management notification',
    }
    title = title_map.get((entry.action, entry.entity_type))
    if not title:
        pretty_action = entry.action.replace('_', ' ').title()
        title = details or f'{pretty_action} ({entry.entity_type})'

    created = entry.created_at
    unread = bool(created and created >= unread_cutoff)

    return {
        'id': entry.id,
        'title': title,
        'actor': actor,
        'time_label': created.strftime('%Y-%m-%d %H:%M') if created else '',
        'relative': _relative_time(created),
        'url': _notification_url(entry.action, entry.entity_type, entry.entity_id),
        'unread': unread,
    }


def _staff_workflow_alerts(limit, unread_cutoff):
    """Synthetic alerts for periods waiting on review or report delivery."""
    items = []
    pending_reports = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
        .filter(MonthlyPeriod.reports_sent_at.is_(None))
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .limit(3)
        .all()
    )
    for period in pending_reports:
        items.append({
            'id': f'pending-reports-{period.id}',
            'title': f'Reports pending for {period.period_label}',
            'actor': 'System',
            'time_label': period.approved_at.strftime('%Y-%m-%d %H:%M') if period.approved_at else '',
            'relative': _relative_time(period.approved_at),
            'url': url_for('periods.detail_period', period_id=period.id),
            'unread': True,
        })

    in_review = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_REVIEW)
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .limit(3)
        .all()
    )
    for period in in_review:
        items.append({
            'id': f'review-{period.id}',
            'title': f'Awaiting approval — {period.period_label}',
            'actor': 'System',
            'time_label': '',
            'relative': '',
            'url': url_for('periods.detail_period', period_id=period.id),
            'unread': True,
        })

    return items[:limit]


def _shareholder_portal_audit_items(limit, unread_cutoff, company):
    """Portal-relevant audit events for the signed-in shareholder."""
    user_id = current_user.id
    shareholder_id = current_user.shareholder_id
    query = AuditLog.query.filter(
        or_(
            (AuditLog.entity_type == 'user') & (AuditLog.entity_id == user_id) & (AuditLog.action == 'password_change'),
            (AuditLog.entity_type == 'shareholder_portal_user') & (AuditLog.entity_id == user_id),
            (AuditLog.entity_type == 'shareholder') & (AuditLog.entity_id == shareholder_id) & (
                AuditLog.action.in_(['update', 'deactivate'])
            ),
        )
    ).order_by(AuditLog.created_at.desc()).limit(limit)

    items = []
    for entry in query.all():
        item = _format_notification(entry, unread_cutoff)
        if not item.get('actor') or item['actor'] == 'System':
            item['actor'] = company
        if entry.action == 'password_change':
            item['url'] = url_for('auth.account')
        elif entry.entity_type == 'shareholder':
            item['url'] = url_for('portal.ownership')
        else:
            item['url'] = url_for('auth.account')
        items.append(item)
    return items


def get_topbar_notifications(limit=8):
    """Build notifications from audit activity, certificates, and workflow queues."""
    if not getattr(current_user, 'is_authenticated', False):
        return {'items': [], 'count': 0}

    unread_cutoff = datetime.utcnow() - timedelta(hours=24)

    if current_user.is_shareholder():
        from apps.services.brand_service import get_brand_settings

        company = get_brand_settings().get('company_name') or 'Company'
        certs = (
            ShareholderCertificate.query.filter_by(shareholder_id=current_user.shareholder_id)
            .order_by(ShareholderCertificate.generated_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for cert in certs:
            period = cert.period
            label = period.period_label if period else 'period'
            if cert.email_status == 'sent':
                title = f'Report emailed — {label}'
            elif cert.email_status == 'logged':
                title = f'Certificate ready (email logged) — {label}'
            elif cert.email_status == 'pending':
                title = f'Certificate pending email — {label}'
            else:
                title = f'Certificate ready — {label}'
            items.append({
                'id': f'cert-{cert.id}',
                'title': title,
                'actor': company,
                'time_label': cert.generated_at.strftime('%Y-%m-%d %H:%M') if cert.generated_at else '',
                'relative': _relative_time(cert.generated_at),
                'url': (
                    url_for('portal.report_detail', period_id=cert.period_id)
                    if cert.period_id
                    else url_for('portal.reports')
                ),
                'unread': cert.email_status in ('pending', 'logged') or (
                    bool(cert.generated_at and cert.generated_at >= unread_cutoff)
                ),
            })

        # Merge portal account events (password / access) without drowning cert alerts.
        for item in _shareholder_portal_audit_items(4, unread_cutoff, company):
            items.append(item)

        items.sort(key=lambda row: row.get('time_label') or '', reverse=True)
        items = items[:limit]
        unread = sum(1 for item in items if item.get('unread'))
        return {'items': items, 'count': unread}

    fetch_limit = max(limit * 3, 24)
    logs = (
        AuditLog.query.filter(~AuditLog.action.in_(list(TOPBAR_EXCLUDED_ACTIONS)))
        .order_by(AuditLog.created_at.desc())
        .limit(fetch_limit)
        .all()
    )
    items = [_format_notification(entry, unread_cutoff) for entry in logs]
    workflow = _staff_workflow_alerts(limit, unread_cutoff)
    for alert in reversed(workflow):
        items.insert(0, alert)

    items = items[:limit]
    unread = sum(1 for item in items if item.get('unread'))
    return {'items': items, 'count': unread}
