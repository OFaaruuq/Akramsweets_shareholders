from flask import flash, redirect, render_template, send_file, url_for
from flask_login import current_user

from apps.auth.decorators import shareholder_portal_required
from apps.models.period import MonthlyPeriod, ShareholderCalculation
from apps.portal import blueprint
from apps.services.certificate_service import build_certificate_payload, get_shareholder_certificate, issue_shareholder_certificate
from apps.services.dashboard_service import get_shareholder_portal_metrics
from apps.services.pdf_service import (
    certificate_pdf_filename,
    generate_shareholder_certificate_pdf,
    generate_shareholder_report_pdf,
    report_pdf_filename,
)
from apps.services.report_service import build_shareholder_report


@blueprint.route('/')
@shareholder_portal_required
def dashboard():
    metrics = get_shareholder_portal_metrics(current_user.shareholder_id)
    return render_template('portal/dashboard.html', segment='portal', **metrics)


@blueprint.route('/reports')
@shareholder_portal_required
def reports():
    metrics = get_shareholder_portal_metrics(current_user.shareholder_id)
    return render_template('portal/reports.html', segment='portal-reports', **metrics)


@blueprint.route('/reports/<int:period_id>')
@shareholder_portal_required
def report_detail(period_id):
    period = MonthlyPeriod.query.filter_by(
        id=period_id,
        status=MonthlyPeriod.STATUS_APPROVED,
    ).first_or_404()
    calculation = ShareholderCalculation.query.filter_by(
        period_id=period.id,
        shareholder_id=current_user.shareholder_id,
    ).first_or_404()
    report = build_shareholder_report(period, calculation)
    certificate = get_shareholder_certificate(period.id, current_user.shareholder_id)
    return render_template(
        'portal/report_detail.html',
        report=report,
        period=period,
        calculation=calculation,
        certificate=certificate,
        segment='portal-reports',
    )


@blueprint.route('/reports/<int:period_id>/certificate')
@shareholder_portal_required
def report_certificate_pdf(period_id):
    from io import BytesIO

    period = MonthlyPeriod.query.filter_by(
        id=period_id,
        status=MonthlyPeriod.STATUS_APPROVED,
    ).first_or_404()
    calculation = ShareholderCalculation.query.filter_by(
        period_id=period.id,
        shareholder_id=current_user.shareholder_id,
    ).first_or_404()
    certificate = get_shareholder_certificate(period.id, calculation.shareholder_id)
    if not certificate:
        certificate = issue_shareholder_certificate(period, calculation)
        from apps import db
        db.session.commit()
    certificate_data = build_certificate_payload(period, calculation, certificate)
    pdf_bytes = generate_shareholder_certificate_pdf(certificate_data)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=certificate_pdf_filename(certificate_data),
    )


@blueprint.route('/reports/<int:period_id>/pdf')
@shareholder_portal_required
def report_pdf(period_id):
    from io import BytesIO

    period = MonthlyPeriod.query.filter_by(
        id=period_id,
        status=MonthlyPeriod.STATUS_APPROVED,
    ).first_or_404()
    calculation = ShareholderCalculation.query.filter_by(
        period_id=period.id,
        shareholder_id=current_user.shareholder_id,
    ).first_or_404()
    report = build_shareholder_report(period, calculation)
    pdf_bytes = generate_shareholder_report_pdf(report)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_pdf_filename(report),
    )


@blueprint.route('/ownership')
@shareholder_portal_required
def ownership():
    from apps.services.share_value_service import (
        capital_for_ownership,
        get_share_settings,
        shares_for_ownership,
    )

    metrics = get_shareholder_portal_metrics(current_user.shareholder_id)
    percent = metrics['ownership_percent']
    share_settings = get_share_settings()
    return render_template(
        'portal/ownership.html',
        segment='portal-ownership',
        shareholder=metrics['shareholder'],
        ownership_percent=percent,
        ownership_history=metrics['ownership_history'],
        share_settings=share_settings,
        share_units=shares_for_ownership(percent),
        capital=capital_for_ownership(percent),
    )


@blueprint.route('/profile', methods=['GET', 'POST'])
@shareholder_portal_required
def profile():
    """Shareholder account settings live on the shared profile page."""
    return redirect(url_for('auth.account'))
