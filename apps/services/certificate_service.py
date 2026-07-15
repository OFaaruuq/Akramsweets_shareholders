from datetime import datetime

from apps import db
from apps.models.certificate import ShareholderCertificate
from apps.models.period import MonthlyPeriod, ShareholderCalculation
from apps.models.shareholder import Shareholder
from apps.services.report_service import build_shareholder_report
from apps.services.shareholder_service import get_ownership_percent


def certificate_number_for(period, shareholder_id):
    from apps.services.certificate_settings_service import get_certificate_settings

    prefix = get_certificate_settings()['number_prefix'].strip() or 'AS-CERT'
    return f'{prefix}-{period.year}-{period.month:02d}-{shareholder_id:04d}-{period.id:05d}'


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


def issue_period_certificates(period, *, audit=False):
    """Generate a certificate record for every current shareholder in an approved period."""
    certificates = []
    newly_issued = 0
    for calculation in period.calculations:
        existing = ShareholderCertificate.query.filter_by(
            period_id=period.id,
            shareholder_id=calculation.shareholder_id,
        ).first()
        certificates.append(issue_shareholder_certificate(period, calculation))
        if not existing:
            newly_issued += 1
    db.session.commit()
    if audit and newly_issued:
        from apps.services.audit_service import log_action

        log_action(
            'issue',
            'certificate',
            period.id,
            f'{period.period_label}: issued {newly_issued} certificate(s)',
        )
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

    from apps.services.brand_service import ensure_default_logo, get_brand_settings
    from apps.services.certificate_settings_service import (
        ensure_default_certificate_settings,
        format_certificate_text,
        get_certificate_settings,
    )

    ensure_default_logo()
    ensure_default_certificate_settings()
    brand = get_brand_settings()
    cert = get_certificate_settings()
    approved_by = period.approved_by.full_name if period.approved_by else cert['approver_fallback']
    roster = _period_shareholder_roster(period) if cert['show_roster'] else []

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
        'cert_subtitle': cert['subtitle'],
        'cert_title': cert['title'],
        'cert_intro_text': cert['intro_text'],
        'cert_allocation_text': format_certificate_text(
            cert['allocation_text'],
            period_label=report.get('period_label', ''),
            company_name=brand['company_name'],
        ),
        'cert_profit_label': cert['profit_label'],
        'cert_loss_label': cert['loss_label'],
        'cert_currency_symbol': cert['currency_symbol'],
        'cert_owner_label': cert['owner_label'],
        'cert_roster_title': cert['roster_title'],
        'cert_label_company_pl': cert['label_company_pl'],
        'cert_label_base_share': cert['label_base_share'],
        'cert_label_ytd': cert['label_ytd'],
        'cert_label_odoo': cert['label_odoo'],
        'cert_footer_disclaimer': cert['footer_disclaimer'],
        'cert_footer_confidential': format_certificate_text(
            cert['footer_confidential'],
            company_name=brand['company_name'],
            period_label=report.get('period_label', ''),
        ),
        'cert_legal_text': cert['legal_text'],
        'cert_show_odoo_reference': cert['show_odoo_reference'],
        'cert_signature_name': cert['signature_name'],
        'cert_signature_title': cert['signature_title'],
        'cert_signature_image_path': cert['signature_filesystem_path'],
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