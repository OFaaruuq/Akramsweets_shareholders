from flask import flash, redirect, render_template, send_file, url_for
from flask_login import current_user

from apps import db
from apps.auth.decorators import shareholder_portal_required
from apps.auth.forms import ChangePasswordForm
from apps.models.period import MonthlyPeriod, ShareholderCalculation
from apps.portal import blueprint
from apps.services.audit_service import log_action
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
    metrics = get_shareholder_portal_metrics(current_user.shareholder_id)
    return render_template(
        'portal/ownership.html',
        segment='portal-ownership',
        shareholder=metrics['shareholder'],
        ownership_percent=metrics['ownership_percent'],
        ownership_history=metrics['ownership_history'],
    )


@blueprint.route('/profile', methods=['GET', 'POST'])
@shareholder_portal_required
def profile():
    form = ChangePasswordForm()
    shareholder = current_user.shareholder

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            log_action('password_change', 'user', current_user.id)
            flash('Password updated successfully.', 'success')
            return redirect(url_for('portal.profile'))

    return render_template(
        'portal/profile.html',
        form=form,
        shareholder=shareholder,
        segment='portal-profile',
    )
