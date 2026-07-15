from decimal import Decimal, InvalidOperation

from apps.models.arrangement import SpecialArrangement
from apps.models.shareholder import OwnershipRecord, Shareholder


OWNERSHIP_TOLERANCE = Decimal('0.01')


COUNTRY_CHOICES = [
    ('so', 'Somalia'),
    ('ke', 'Kenya'),
    ('ae', 'United Arab Emirates'),
    ('us', 'United States'),
    ('gb', 'United Kingdom'),
    ('ca', 'Canada'),
    ('au', 'Australia'),
    ('in', 'India'),
    ('de', 'Germany'),
    ('br', 'Brazil'),
    ('tr', 'Turkey'),
    ('sa', 'Saudi Arabia'),
]

COUNTRY_FLAG_MAP = {
    'so': 'so.svg',
    'ke': 'ke.svg',
    'ae': 'ae.svg',
    'us': 'us.svg',
    'gb': 'gb.svg',
    'ca': 'ca.svg',
    'au': 'au.svg',
    'in': 'in.svg',
    'de': 'de.svg',
    'br': 'br.svg',
    'tr': 'tr.svg',
    'sa': 'sa.svg',
    'ru': 'ru.svg',
    'si': 'si.svg',
}

COUNTRY_LABELS = {code: name for code, name in COUNTRY_CHOICES}


def country_label(code):
    return COUNTRY_LABELS.get((code or '').lower(), (code or '').upper() or 'Unknown')


def country_flag_filename(code):
    return COUNTRY_FLAG_MAP.get((code or '').lower(), 'so.svg')


def get_active_shareholders(as_of_date):
    return Shareholder.query.filter_by(is_active=True).order_by(Shareholder.name).all()


def get_ownership_percent(shareholder, as_of_date):
    record = (
        OwnershipRecord.query.filter(
            OwnershipRecord.shareholder_id == shareholder.id,
            OwnershipRecord.effective_from <= as_of_date,
            db_or_effective_to(OwnershipRecord, as_of_date),
        )
        .order_by(OwnershipRecord.effective_from.desc())
        .first()
    )
    return Decimal(record.ownership_percent) if record else Decimal('0')


def db_or_effective_to(model, as_of_date):
    from sqlalchemy import or_

    return or_(model.effective_to.is_(None), model.effective_to >= as_of_date)


def get_active_arrangements(as_of_date, is_profit):
    query = SpecialArrangement.query.filter(
        SpecialArrangement.is_active.is_(True),
        SpecialArrangement.effective_from <= as_of_date,
        db_or_effective_to(SpecialArrangement, as_of_date),
    )
    if is_profit:
        query = query.filter(SpecialArrangement.apply_on_profit.is_(True))
    else:
        query = query.filter(SpecialArrangement.apply_on_loss.is_(True))
    return query.all()


def validate_ownership_totals(as_of_date):
    shareholders = get_active_shareholders(as_of_date)
    total = sum(get_ownership_percent(sh, as_of_date) for sh in shareholders)
    return total, shareholders


def normalize_email(email):
    return (email or '').strip().lower()


def shareholder_email_taken(email, exclude_id=None):
    email = normalize_email(email)
    if not email:
        return False
    query = Shareholder.query.filter(Shareholder.email == email)
    if exclude_id:
        query = query.filter(Shareholder.id != exclude_id)
    return query.first() is not None


def _as_decimal(value, default='0'):
    try:
        if value is None or value == '':
            return Decimal(default)
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def proposed_ownership_total(ownership_percent, as_of_date, exclude_shareholder_id=None):
    """Total ownership % if `ownership_percent` is applied for the excluded shareholder."""
    total, shareholders = validate_ownership_totals(as_of_date)
    others = total
    if exclude_shareholder_id:
        current = next((sh for sh in shareholders if sh.id == exclude_shareholder_id), None)
        if current:
            others = total - get_ownership_percent(current, as_of_date)
    return others + _as_decimal(ownership_percent)


def ownership_would_exceed_100(ownership_percent, as_of_date, exclude_shareholder_id=None):
    proposed = proposed_ownership_total(ownership_percent, as_of_date, exclude_shareholder_id)
    return proposed > (Decimal('100') + OWNERSHIP_TOLERANCE), proposed


def ownership_fits_or_error(ownership_percent, as_of_date, exclude_shareholder_id=None):
    """Return an error message if ownership would push active total over 100%, else None."""
    exceeds, proposed = ownership_would_exceed_100(
        ownership_percent, as_of_date, exclude_shareholder_id=exclude_shareholder_id
    )
    if exceeds:
        return (
            f'This ownership would make the active total {proposed:.2f}% '
            f'(maximum allowed is 100%). Reduce the percentage or adjust other shareholders first.'
        )
    return None


def get_ownership_history(shareholder, limit=20):
    return (
        OwnershipRecord.query.filter_by(shareholder_id=shareholder.id)
        .order_by(OwnershipRecord.effective_from.desc(), OwnershipRecord.id.desc())
        .limit(limit)
        .all()
    )


def registration_stats(as_of_date=None):
    from datetime import datetime

    as_of = as_of_date or datetime.utcnow().date()
    shareholders = Shareholder.query.order_by(Shareholder.name).all()
    active = [s for s in shareholders if s.is_active]
    inactive = [s for s in shareholders if not s.is_active]
    with_portal = [s for s in shareholders if s.user_account and s.user_account.is_active]
    total_ownership, _ = validate_ownership_totals(as_of)
    countries = {(s.country_code or '').lower() for s in active if s.country_code}
    return {
        'total': len(shareholders),
        'active': len(active),
        'inactive': len(inactive),
        'portal': len(with_portal),
        'countries': len(countries),
        'ownership_total': float(total_ownership),
        'ownership_ok': abs(total_ownership - Decimal('100')) <= OWNERSHIP_TOLERANCE,
        'remaining': float(Decimal('100') - total_ownership),
    }
