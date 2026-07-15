from decimal import Decimal, InvalidOperation

from apps.models.arrangement import SpecialArrangement
from apps.models.shareholder import OwnershipRecord, Shareholder
from apps.services.decimal_utils import OWNERSHIP_TOLERANCE


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


def validate_capital_against_ownership(ownership_percent, share_count=None, investment_amount=None):
    """
    When company total shares are configured, registered shares/investment must match
    values derived from ownership %. Empty/zero register fields are allowed (display falls back).
    """
    from apps.services.share_value_service import capital_for_ownership, get_share_settings, shares_for_ownership

    settings = get_share_settings()
    if not settings.get('has_total_shares'):
        return []

    errors = []
    expected_shares = shares_for_ownership(ownership_percent)
    expected_capital = capital_for_ownership(ownership_percent)
    registered_shares = _as_decimal(share_count)
    registered_investment = _as_decimal(investment_amount)

    if registered_shares > 0 and expected_shares is not None:
        if abs(registered_shares - expected_shares) > Decimal('0.0001'):
            errors.append(
                f'Registered shares ({registered_shares}) must match ownership-derived '
                f'{expected_shares} (ownership % × company total shares). '
                f'Use “Auto-fill shares from ownership %” or clear the shares field.'
            )
    if registered_investment > 0 and expected_capital is not None:
        if abs(registered_investment - expected_capital) > Decimal('0.01'):
            errors.append(
                f'Registered investment ({registered_investment}) must match ownership-derived '
                f'{expected_capital} (shares × share value). '
                f'Use auto-fill or clear the investment field.'
            )
    return errors


def effective_shares_and_capital(shareholder, ownership_percent):
    """
    Canonical display values: prefer ownership-derived when company totals are set;
    otherwise use registered fields.
    """
    from apps.services.share_value_service import capital_for_ownership, get_share_settings, shares_for_ownership

    settings = get_share_settings()
    registered_shares = float(shareholder.share_count or 0) if shareholder else 0.0
    registered_investment = float(shareholder.investment_amount or 0) if shareholder else 0.0
    derived_shares = shares_for_ownership(ownership_percent)
    derived_capital = capital_for_ownership(ownership_percent)

    if settings.get('has_total_shares') and derived_shares is not None:
        return {
            'shares': float(derived_shares),
            'investment': float(derived_capital) if derived_capital is not None else registered_investment,
            'source': 'derived',
            'registered_shares': registered_shares,
            'registered_investment': registered_investment,
            'mismatch': (
                (registered_shares > 0 and abs(registered_shares - float(derived_shares)) > 0.0001)
                or (
                    registered_investment > 0
                    and derived_capital is not None
                    and abs(registered_investment - float(derived_capital)) > 0.01
                )
            ),
        }

    return {
        'shares': registered_shares or (float(derived_shares) if derived_shares is not None else 0.0),
        'investment': registered_investment or (
            float(derived_capital) if derived_capital is not None else 0.0
        ),
        'source': 'registered' if registered_shares or registered_investment else 'derived',
        'registered_shares': registered_shares,
        'registered_investment': registered_investment,
        'mismatch': False,
    }


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
