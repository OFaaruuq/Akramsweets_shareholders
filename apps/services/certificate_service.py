from datetime import datetime

from apps import db
from apps.models.certificate import ShareholderCertificate
from apps.models.period import MonthlyPeriod, ShareholderCalculation
from apps.models.shareholder import Shareholder
from apps.services.report_service import build_shareholder_report
from apps.services.shareholder_service import get_ownership_percent


def certificate_number_for(period, shareholder_id):
    return f'AS-CERT-{period.year}-{period.month:02d}-{shareholder_id:04d}-{period.id:05d}'


def issue_shareholder_certificate(period, calculation):
    existing = ShareholderCertificate.query.filter_by(
        period_id=period.id,
        shareholder_id=calculation.shareholder_id,
    ).first()
    if existing:
        return existing

    certificate = ShareholderCertificate(
        period_id=period.id,
        shareholder_id=calculation.shareholder_id,
        certificate_number=certificate_number_for(period, calculation.shareholder_id),
        generated_at=datetime.utcnow(),
        email_status='pending',
    )
    db.session.add(certificate)
    db.session.flush()
    return certificate


def issue_period_certificates(period):
    """Generate a certificate record for every current shareholder in an approved period."""
    certificates = []
    for calculation in period.calculations:
        certificates.append(issue_shareholder_certificate(period, calculation))
    db.session.commit()
    return certificates


def ensure_approved_period_certificates():
    """Backfill certificates for any approved period that is missing them."""
    periods = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED).all()
    issued = []
    for period in periods:
        existing_count = ShareholderCertificate.query.filter_by(period_id=period.id).count()
        expected_count = period.calculations.count()
        if expected_count and existing_count < expected_count:
            issue_period_certificates(period)
            issued.append(period)
    return issued


def _period_shareholder_roster(period):
    rows = (
        ShareholderCalculation.query.filter_by(period_id=period.id)
        .join(Shareholder)
        .order_by(Shareholder.name)
        .all()
    )
    return [
        {
            'id': calc.shareholder_id,
            'name': calc.shareholder.name,
            'email': calc.shareholder.email,
            'phone': calc.shareholder.phone,
            'ownership_percent': float(calc.ownership_percent),
            'is_owner': bool(calc.shareholder.is_owner),
            'final_amount': float(calc.final_amount),
        }
        for calc in rows
    ]


def build_certificate_payload(period, calculation, certificate):
    report = build_shareholder_report(period, calculation)
    shareholder = calculation.shareholder
    approved_by = period.approved_by.full_name if period.approved_by else 'Akram Sweets Management'
    roster = _period_shareholder_roster(period)

    from apps.services.brand_service import ensure_default_logo, get_brand_settings

    ensure_default_logo()
    brand = get_brand_settings()

    return {
        **report,
        'shareholder_id': shareholder.id,
        'shareholder_phone': shareholder.phone,
        'shareholder_is_owner': bool(shareholder.is_owner),
        'shareholder_is_active': bool(shareholder.is_active),
        'certificate_number': certificate.certificate_number,
        'certificate_issued_at': certificate.generated_at,
        'approved_at': period.approved_at,
        'approved_by': approved_by,
        'period_year': period.year,
        'period_month': period.month,
        'is_profit': float(period.total_profit_loss) >= 0,
        'company_name': brand['company_name'],
        'brand_primary_color': brand['primary_color'],
        'brand_secondary_color': brand['secondary_color'],
        'brand_accent_color': brand['accent_color'],
        'brand_logo_path': brand['logo_filesystem_path'],
        'current_shareholders': roster,
    }


def mark_certificate_emailed(certificate, status='sent'):
    certificate.emailed_at = datetime.utcnow()
    certificate.email_status = status
    db.session.commit()


def get_shareholder_certificate(period_id, shareholder_id):
    return ShareholderCertificate.query.filter_by(
        period_id=period_id,
        shareholder_id=shareholder_id,
    ).first()


def get_latest_approved_period():
    return (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .first()
    )


def get_monthly_certificate_register(period=None):
    """
    Current shareholders with their monthly certificate for the selected period.
    Defaults to the latest approved month.
    """
    period = period or get_latest_approved_period()
    as_of = period.as_of_date if period else datetime.utcnow().date()
    shareholders = Shareholder.query.filter_by(is_active=True).order_by(Shareholder.name).all()
    certificates_by_shareholder = {}
    calculations_by_shareholder = {}

    if period:
        for cert in ShareholderCertificate.query.filter_by(period_id=period.id).all():
            certificates_by_shareholder[cert.shareholder_id] = cert
        for calc in ShareholderCalculation.query.filter_by(period_id=period.id).all():
            calculations_by_shareholder[calc.shareholder_id] = calc

    rows = []
    for shareholder in shareholders:
        calculation = calculations_by_shareholder.get(shareholder.id)
        ownership = (
            float(calculation.ownership_percent)
            if calculation is not None
            else float(get_ownership_percent(shareholder, as_of))
        )
        rows.append({
            'shareholder': shareholder,
            'ownership_percent': ownership,
            'calculation': calculation,
            'certificate': certificates_by_shareholder.get(shareholder.id),
            'final_amount': float(calculation.final_amount) if calculation is not None else None,
        })

    approved_periods = (
        MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED)
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .all()
    )
    return {
        'period': period,
        'periods': approved_periods,
        'rows': rows,
        'as_of': as_of,
    }