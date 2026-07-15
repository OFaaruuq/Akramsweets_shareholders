from io import BytesIO

from flask import abort, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from apps.auth.decorators import finance_or_management_required
from apps.models.period import MonthlyPeriod, ShareholderCalculation
from apps.reports import blueprint
from apps.services.certificate_service import (
    build_certificate_payload,
    get_monthly_certificate_register,
    get_shareholder_certificate,
    issue_period_certificates,
    issue_shareholder_certificate,
)
from apps.services.shareholder_service import country_flag_filename, country_label
from apps.services.pdf_service import (
    certificate_pdf_filename,
    generate_shareholder_certificate_pdf,
    generate_shareholder_report_pdf,
    report_pdf_filename,
)
from apps.services.report_service import build_shareholder_report


@blueprint.route('/')
@login_required
def history():
    if current_user.is_shareholder():
        return redirect(url_for('portal.reports'))

    query = MonthlyPeriod.query.filter_by(status=MonthlyPeriod.STATUS_APPROVED).order_by(
        MonthlyPeriod.year.desc(),
        MonthlyPeriod.month.desc(),
    )
    periods = query.all()
    return render_template('reports/history_admin.html', periods=periods, segment='reports')


@blueprint.route('/mudarabah')
@finance_or_management_required
def mudarabah_summary():
    """Monthly Mudarabah pools: Net Profit, shareholders' pool, managing partner share."""
    from apps.services.capital_withdrawal_service import outstanding_withdrawal_requests
    from apps.services.mudarabah_service import get_mudarabah_settings

    periods = (
        MonthlyPeriod.query.filter(MonthlyPeriod.calculated_at.isnot(None))
        .order_by(MonthlyPeriod.year.desc(), MonthlyPeriod.month.desc())
        .limit(36)
        .all()
    )
    rows = []
    for period in periods:
        distributed = sum((float(c.final_amount) for c in period.calculations), 0.0)
        rows.append({
            'period': period,
            'net_profit': float(period.total_profit_loss or 0),
            'shareholders_pool': float(period.shareholders_pool or 0),
            'managing_partner_share': float(period.managing_partner_share or 0),
            'mudarabah_percent': float(period.mudarabah_shareholder_percent or 50),
            'distributed': distributed,
            'status': period.status,
        })
    withdrawals = outstanding_withdrawal_requests()
    return render_template(
        'reports/mudarabah_summary.html',
        rows=rows,
        mudarabah=get_mudarabah_settings(),
        withdrawals=withdrawals,
        segment='mudarabah',
    )


@blueprint.route('/certificates')
@finance_or_management_required
def certificates_register():
    """Monthly register of current shareholders and their certificates."""
    from flask import flash

    period_id = request.args.get('period_id', type=int)
    period = MonthlyPeriod.query.get(period_id) if period_id else None
    if period and period.status != MonthlyPeriod.STATUS_APPROVED:
        flash('Only approved periods have certificates. Showing the latest approved month.', 'warning')
        period = None

    register = get_monthly_certificate_register(period)
    period = register['period']

    # Ensure certificates exist for the selected approved month.
    if period:
        missing = any(row['calculation'] and not row['certificate'] for row in register['rows'])
        if missing:
            issue_period_certificates(period, audit=True)
            register = get_monthly_certificate_register(period)
            flash('Missing certificates were generated for this month.', 'success')

    rows = []
    for row in register['rows']:
        shareholder = row['shareholder']
        rows.append({
            **row,
            'flag': country_flag_filename(shareholder.country_code),
            'country_name': shareholder.country or country_label(shareholder.country_code),
        })

    issued = sum(1 for row in rows if row.get('certificate'))
    emailed = sum(1 for row in rows if row.get('certificate') and row['certificate'].email_status == 'sent')
    pending = sum(
        1 for row in rows
        if row.get('certificate') and row['certificate'].email_status not in ('sent', 'skipped')
    )
    stats = {
        'total': len(rows),
        'issued': issued,
        'emailed': emailed,
        'pending': pending,
    }

    return render_template(
        'reports/certificates.html',
        period=register['period'],
        periods=register['periods'],
        rows=rows,
        as_of=register['as_of'],
        stats=stats,
        segment='certificates',
    )


@blueprint.route('/period/<int:period_id>/shareholder/<int:shareholder_id>')
@login_required
def shareholder_report(period_id, shareholder_id):
    period = MonthlyPeriod.query.filter_by(
        id=period_id,
        status=MonthlyPeriod.STATUS_APPROVED,
    ).first_or_404()
    calculation = ShareholderCalculation.query.filter_by(
        period_id=period.id,
        shareholder_id=shareholder_id,
    ).first_or_404()

    if current_user.is_shareholder():
        if current_user.shareholder_id != shareholder_id:
            abort(403)
        return redirect(url_for('portal.report_detail', period_id=period.id))

    report = build_shareholder_report(period, calculation)
    certificate = get_shareholder_certificate(period.id, shareholder_id)
    return render_template(
        'reports/shareholder_report.html',
        report=report,
        certificate=certificate,
        period_id=period.id,
        shareholder_id=shareholder_id,
        segment='reports',
    )


@blueprint.route('/period/<int:period_id>/shareholder/<int:shareholder_id>/certificate')
@login_required
def shareholder_certificate_pdf(period_id, shareholder_id):
    period = MonthlyPeriod.query.filter_by(
        id=period_id,
        status=MonthlyPeriod.STATUS_APPROVED,
    ).first_or_404()
    calculation = ShareholderCalculation.query.filter_by(
        period_id=period.id,
        shareholder_id=shareholder_id,
    ).first_or_404()

    if current_user.is_shareholder() and current_user.shareholder_id != shareholder_id:
        abort(403)

    certificate = get_shareholder_certificate(period.id, shareholder_id)
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


@blueprint.route('/period/<int:period_id>/shareholder/<int:shareholder_id>/pdf')
@login_required
def shareholder_report_pdf(period_id, shareholder_id):
    period = MonthlyPeriod.query.filter_by(
        id=period_id,
        status=MonthlyPeriod.STATUS_APPROVED,
    ).first_or_404()
    calculation = ShareholderCalculation.query.filter_by(
        period_id=period.id,
        shareholder_id=shareholder_id,
    ).first_or_404()

    if current_user.is_shareholder() and current_user.shareholder_id != shareholder_id:
        abort(403)

    report = build_shareholder_report(period, calculation)
    pdf_bytes = generate_shareholder_report_pdf(report)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=report_pdf_filename(report),
    )
