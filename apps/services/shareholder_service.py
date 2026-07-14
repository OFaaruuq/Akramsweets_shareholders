from decimal import Decimal

from apps.models.arrangement import SpecialArrangement
from apps.models.shareholder import OwnershipRecord, Shareholder


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
