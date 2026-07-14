"""Contact directory helpers — shareholders + internal staff."""

from __future__ import annotations

from datetime import datetime

from apps.models.shareholder import Shareholder
from apps.models.user import User
from apps.services.shareholder_service import (
    country_flag_filename,
    country_label,
    get_ownership_percent,
)


def build_shareholder_contacts(q=None, country=None, status='active'):
    """Return shareholder contact cards for the directory."""
    query = Shareholder.query.order_by(Shareholder.name.asc())
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    shareholders = query.all()
    needle = (q or '').strip().lower()
    country_code = (country or '').strip().lower() or None
    as_of = datetime.utcnow().date()
    rows = []

    for shareholder in shareholders:
        if country_code and (shareholder.country_code or '').lower() != country_code:
            continue

        haystack = ' '.join(filter(None, [
            shareholder.name,
            shareholder.email,
            shareholder.phone,
            shareholder.country,
            shareholder.country_code,
        ])).lower()
        if needle and needle not in haystack:
            continue

        ownership = float(get_ownership_percent(shareholder, as_of))
        portal = shareholder.user_account
        rows.append({
            'id': shareholder.id,
            'name': shareholder.name,
            'email': shareholder.email,
            'phone': shareholder.phone,
            'country': shareholder.country or country_label(shareholder.country_code),
            'country_code': shareholder.country_code,
            'flag': country_flag_filename(shareholder.country_code),
            'is_owner': bool(shareholder.is_owner),
            'is_active': bool(shareholder.is_active),
            'ownership_percent': ownership,
            'has_portal': bool(portal),
            'portal_email': portal.email if portal else None,
            'notes': shareholder.notes,
            'kind': 'shareholder',
            'badge': 'Owner' if shareholder.is_owner else 'Shareholder',
            'badge_class': 'bg-primary' if shareholder.is_owner else 'bg-info',
            'initials': _initials(shareholder.name),
        })
    return rows


def build_staff_contacts(q=None):
    """Return internal staff users (non-shareholder roles)."""
    users = (
        User.query.filter(User.role != User.ROLE_SHAREHOLDER)
        .order_by(User.full_name.asc())
        .all()
    )
    needle = (q or '').strip().lower()
    rows = []
    for user in users:
        haystack = ' '.join(filter(None, [user.full_name, user.email, user.role])).lower()
        if needle and needle not in haystack:
            continue
        role_label = user.role.replace('_', ' ').title()
        rows.append({
            'id': user.id,
            'name': user.full_name,
            'email': user.email,
            'phone': None,
            'role': user.role,
            'role_label': role_label,
            'is_active': bool(user.is_active),
            'kind': 'staff',
            'badge': role_label,
            'badge_class': {
                User.ROLE_OWNER: 'bg-primary',
                User.ROLE_ADMIN: 'bg-danger',
                User.ROLE_FINANCE: 'bg-warning text-dark',
            }.get(user.role, 'bg-secondary'),
            'initials': _initials(user.full_name),
        })
    return rows


def contact_directory_stats(shareholder_rows, staff_rows):
    countries = {
        row['country_code']
        for row in shareholder_rows
        if row.get('country_code')
    }
    return {
        'shareholders': len(shareholder_rows),
        'owners': sum(1 for row in shareholder_rows if row.get('is_owner')),
        'portal_accounts': sum(1 for row in shareholder_rows if row.get('has_portal')),
        'countries': len(countries),
        'staff': len(staff_rows),
        'active_staff': sum(1 for row in staff_rows if row.get('is_active')),
    }


def _initials(name: str) -> str:
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return 'AS'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
