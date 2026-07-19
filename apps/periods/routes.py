from flask import flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from io import BytesIO

from apps import db
from apps.auth.decorators import finance_or_management_required, management_required
from apps.forms import AdjustmentForm, CorrectionReopenForm, PeriodForm, PeriodRejectForm, ShareholderUpdateForm
from apps.models.period import ManualAdjustment, MonthlyPeriod, ShareholderCalculation
from apps.models.shareholder import Shareholder
from apps.periods import blueprint
from apps.services.audit_service import log_action
from apps.services.approval_service import get_pending_approvals, reject_period
from apps.services.calculation_service import (
    approve_period,
    calculate_period,
    mark_payment_completed,
    preview_period_distribution,
    reopen_for_correction,
    submit_for_review,
)
from apps.services.period_service import (
    apply_period_form_defaults,
    get_period_create_context,
    get_period_readiness,
    period_as_of_date,
    resolve_period_totals,
)
from apps.services.report_schedule_service import auto_send_period_reports, can_send_reports_now, get_report_delivery_day, send_period_reports

PERIOD_FORM_TITLE = 'Monthly Mudarabah Profit Distribution'


def _form_extras():
    from apps.services.mudarabah_service import get_mudarabah_shareholder_percent
    from apps.services.share_value_service import get_share_settings

    settings = get_share_settings()
    return {
        'mudarabah_percent': float(get_mudarabah_shareholder_percent()),
        'share_value_label': settings.get('label'),
        'share_settings': settings,
    }


def _period_from_form(form, created_by_id=None):
    """Create a period from Net Profit only (optional P&L columns stay at zero)."""
    net_total, fields = resolve_period_totals(net_profit=form.total_profit_loss.data)
    period = MonthlyPeriod(
        year=form.year.data,
        month=form.month.data,
        total_profit_loss=net_total,
        income=fields['income'],
        gross_profit=fields['gross_profit'],
        total_gross_profit=fields['total_gross_profit'],
        total_income=fields['total_income'],
        total_revenues=fields['total_revenues'],
        cost_of_goods=fields['cost_of_goods'],
        total_expenses=fields['total_expenses'],
        other_income=fields['other_income'],
        entry_mode=fields['entry_mode'],
        odoo_reference=(form.odoo_reference.data or '').strip() or None,
        notes=(form.notes.data or '').strip() or None,
    )
    if created_by_id:
        period.created_by_id = created_by_id
    return period


def _update_period_from_form(period, form):
    """Update Net Profit / metadata only — do not wipe legacy P&L reference columns."""
    net_total, _fields = resolve_period_totals(net_profit=form.total_profit_loss.data)
    period.total_profit_loss = net_total
    period.entry_mode = 'pnl'
    period.odoo_reference = (form.odoo_reference.data or '').strip() or None
    period.notes = (form.notes.data or '').strip() or None


@blueprint.route('/')
@finance_or_management_required
def list_periods():
    from calendar import month_name

    from apps.services.approval_service import get_pending_approvals

    status = (request.args.get('status') or '').strip() or None
    year_raw = (request.args.get('year') or '').strip()
    q = (request.args.get('q') or '').strip()

    year_filter = None
    if year_raw.isdigit():
        year_filter = int(year_raw)

    all_periods = MonthlyPeriod.query.order_by(
        MonthlyPeriod.year.desc(),
        MonthlyPeriod.month.desc(),
    ).all()

    status_counts = {
        'all': len(all_periods),
        'draft': sum(1 for p in all_periods if p.status == MonthlyPeriod.STATUS_DRAFT),
        'review': sum(1 for p in all_periods if p.status == MonthlyPeriod.STATUS_REVIEW),
        'approved': sum(1 for p in all_periods if p.status == MonthlyPeriod.STATUS_APPROVED),
    }
    available_years = sorted({p.year for p in all_periods}, reverse=True)

    periods = list(all_periods)
    if status in MonthlyPeriod.STATUSES:
        periods = [p for p in periods if p.status == status]
    if year_filter:
        periods = [p for p in periods if p.year == year_filter]
    if q:
        q_lower = q.lower().strip()
        q_compact = q_lower.replace(' ', '-')
        filtered = []
        for period in periods:
            label = period.period_label.lower()
            name = f'{month_name[period.month]} {period.year}'.lower()
            hay = ' '.join(
                [
                    label,
                    name,
                    (period.odoo_reference or '').lower(),
                    (period.notes or '').lower(),
                    period.status,
                ]
            )
            if q_lower in hay or q_compact in label:
                filtered.append(period)
        periods = filtered

    rows = []
    for period in periods:
        has_calcs = period.calculations.count() > 0
        if period.status == MonthlyPeriod.STATUS_DRAFT:
            next_action = {
                'label': 'Submit for review' if has_calcs else 'Continue draft',
                'url': url_for('periods.detail_period', period_id=period.id),
                'style': 'btn-warning' if has_calcs else 'btn-soft-warning',
            }
        elif period.status == MonthlyPeriod.STATUS_REVIEW:
            if current_user.can_approve_periods():
                next_action = {
                    'label': 'Review & approve',
                    'url': url_for('periods.detail_period', period_id=period.id),
                    'style': 'btn-primary',
                }
            else:
                next_action = {
                    'label': 'Awaiting approval',
                    'url': url_for('periods.detail_period', period_id=period.id),
                    'style': 'btn-soft-info',
                }
        elif period.status == MonthlyPeriod.STATUS_APPROVED:
            if not period.reports_sent_at and current_user.can_approve_periods():
                next_action = {
                    'label': 'Send reports',
                    'url': url_for('periods.detail_period', period_id=period.id),
                    'style': 'btn-soft-primary',
                }
            else:
                next_action = {
                    'label': 'View',
                    'url': url_for('periods.detail_period', period_id=period.id),
                    'style': 'btn-soft-secondary',
                }
        else:
            next_action = {
                'label': 'Open',
                'url': url_for('periods.detail_period', period_id=period.id),
                'style': 'btn-soft-primary',
            }

        rows.append({
            'period': period,
            'month_name': month_name[period.month],
            'partner_share': period.managing_partner_share or 0,
            'pool': period.shareholders_pool or 0,
            'has_calcs': has_calcs,
            'reports_sent': bool(period.reports_sent_at),
            'next_action': next_action,
        })

    inbox = get_pending_approvals()
    return render_template(
        'periods/list.html',
        rows=rows,
        status_filter=status,
        year_filter=year_filter,
        q=q,
        status_counts=status_counts,
        available_years=available_years,
        approvals_pending=inbox.get('period_count', 0),
        segment='periods',
    )


@blueprint.route('/approvals')
@finance_or_management_required
def approvals_inbox():
    """Unified pending approvals: periods in review + open capital withdrawals."""
    queue = get_pending_approvals()
    view = (request.args.get('view') or '').strip().lower() or None
    if view not in (None, 'decision', 'tracking', 'periods', 'withdrawals'):
        view = None

    decision_items = list(queue['needs_decision'])
    tracking_items = list(queue['tracking'])

    if view == 'decision':
        tracking_items = []
    elif view == 'tracking':
        decision_items = []
    elif view == 'periods':
        decision_items = [i for i in decision_items if i['kind'] == 'period']
        tracking_items = []
    elif view == 'withdrawals':
        decision_items = [i for i in decision_items if i['kind'] == 'withdrawal']
        # keep tracking withdrawals visible under withdrawals filter
        tracking_items = list(queue['tracking'])

    show_decision = view in (None, 'decision', 'periods', 'withdrawals')
    show_tracking = view in (None, 'tracking', 'withdrawals')
    if view == 'periods':
        show_tracking = False
    if view == 'decision':
        show_tracking = False

    return render_template(
        'periods/approvals.html',
        queue=queue,
        decision_items=decision_items,
        tracking_items=tracking_items,
        show_decision=show_decision,
        show_tracking=show_tracking,
        view_filter=view,
        segment='approvals',
    )


@blueprint.route('/create', methods=['GET', 'POST'])
@finance_or_management_required
def create_period():
    form = PeriodForm()
    extras = _form_extras()
    if request.method == 'GET':
        create_context = apply_period_form_defaults(form)
    else:
        create_context = get_period_create_context(form.year.data, form.month.data)

    if form.validate_on_submit():
        existing = MonthlyPeriod.query.filter_by(year=form.year.data, month=form.month.data).first()
        if existing:
            flash('A period for that month already exists.', 'danger')
            return redirect(url_for('periods.detail_period', period_id=existing.id))

        readiness = get_period_readiness(form.year.data, form.month.data)
        if not readiness['ownership_valid']:
            flash(
                readiness['blocking_errors'][0]
                if readiness.get('blocking_errors')
                else 'Ownership must total exactly 100% before calculation.',
                'danger',
            )
            return render_template(
                'periods/form.html',
                form=form,
                title=PERIOD_FORM_TITLE,
                segment='periods',
                create_context=create_context,
                **extras,
            )

        period = _period_from_form(form, created_by_id=current_user.id)
        db.session.add(period)
        db.session.commit()
        try:
            calculate_period(period)
        except ValueError as exc:
            db.session.delete(period)
            db.session.commit()
            flash(str(exc), 'danger')
            return render_template(
                'periods/form.html',
                form=form,
                title=PERIOD_FORM_TITLE,
                segment='periods',
                create_context=create_context,
                **extras,
            )

        log_action('create', 'monthly_period', period.id, period.period_label)
        flash('Monthly Mudarabah distribution calculated and saved as Draft.', 'success')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    return render_template(
        'periods/form.html',
        form=form,
        title=PERIOD_FORM_TITLE,
        segment='periods',
        create_context=create_context,
        **extras,
    )


@blueprint.route('/preview', methods=['POST'])
@finance_or_management_required
def preview_period():
    payload = request.get_json(silent=True) or request.form
    try:
        year = int(payload.get('year'))
        month = int(payload.get('month'))
        net_total, _ = resolve_period_totals(
            net_profit=payload.get('total_profit_loss'),
            income=payload.get('income'),
            gross_profit=payload.get('gross_profit'),
            total_gross_profit=payload.get('total_gross_profit'),
            total_income=payload.get('total_income'),
            total_operating_expenses=payload.get('total_expenses'),
        )
        readiness = get_period_readiness(year, month)
        if not readiness['ownership_valid']:
            return jsonify({
                'ok': False,
                'error': (
                    readiness['blocking_errors'][0]
                    if readiness.get('blocking_errors')
                    else 'Ownership must total exactly 100.0000% before preview.'
                ),
                'ownership_valid': False,
                'ownership_total': readiness['ownership_total'],
                'warnings': readiness['warnings'],
            }), 400
        preview = preview_period_distribution(net_total, period_as_of_date(year, month))
        return jsonify({
            'ok': True,
            'preview': preview,
            'warnings': readiness['warnings'],
            'ownership_total': readiness['ownership_total'],
            'ownership_valid': readiness['ownership_valid'],
            'withdrawal_warnings': readiness.get('withdrawal_warnings') or [],
        })
    except (TypeError, ValueError) as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400


@blueprint.route('/<int:period_id>')
@finance_or_management_required
def detail_period(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    calculations = (
        ShareholderCalculation.query.filter_by(period_id=period.id)
        .join(Shareholder)
        .order_by(Shareholder.name)
        .all()
    )
    distributed_total = sum((calc.final_amount for calc in calculations), 0)
    adjustments = period.adjustments.order_by(ManualAdjustment.created_at.desc()).all()
    adjustment_form = AdjustmentForm()
    adjustment_form.shareholder_id.choices = [
        (sh.id, sh.name) for sh in Shareholder.query.filter_by(is_active=True).order_by(Shareholder.name)
    ]
    correction_form = CorrectionReopenForm()
    reject_form = PeriodRejectForm()
    update_form = ShareholderUpdateForm()

    from apps.models.certificate import ShareholderCertificate
    from apps.services.share_value_service import capital_for_ownership, shares_for_ownership

    certificates = {
        cert.shareholder_id: cert
        for cert in ShareholderCertificate.query.filter_by(period_id=period.id).all()
    }

    calc_rows = []
    for calc in calculations:
        sh = calc.shareholder
        ownership = calc.ownership_percent
        registered_shares = float(sh.share_count or 0) if sh else 0.0
        registered_investment = float(sh.investment_amount or 0) if sh else 0.0
        derived_shares = shares_for_ownership(ownership)
        derived_capital = capital_for_ownership(ownership)
        arrangement_adj = float(calc.arrangement_deduction or 0) + float(calc.arrangement_received or 0)
        calc_rows.append({
            'calc': calc,
            'investment': registered_investment or (
                float(derived_capital) if derived_capital is not None else 0.0
            ),
            'shares': registered_shares or (
                float(derived_shares) if derived_shares is not None else 0.0
            ),
            'original_profit': float(calc.base_share or 0),
            'adjustment': arrangement_adj + float(calc.manual_adjustment or 0),
            'final_profit': float(calc.final_amount or 0),
        })

    readiness = get_period_readiness(period.year, period.month)
    remaining = float(period.shareholders_pool or 0) - float(distributed_total or 0)

    return render_template(
        'periods/detail.html',
        period=period,
        calculations=calculations,
        calc_rows=calc_rows,
        certificates=certificates,
        distributed_total=distributed_total,
        remaining_balance=remaining,
        adjustments=adjustments,
        adjustment_form=adjustment_form,
        correction_form=correction_form,
        reject_form=reject_form,
        update_form=update_form,
        withdrawal_warnings=readiness.get('withdrawal_warnings') or [],
        ownership_valid=readiness['ownership_valid'],
        ownership_total=readiness['ownership_total'],
        report_delivery_day=get_report_delivery_day(),
        can_send_reports_now=can_send_reports_now(),
        segment='periods',
    )


@blueprint.route('/<int:period_id>/mark-payment', methods=['POST'])
@management_required
def mark_period_payment(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    try:
        mark_payment_completed(period, current_user)
        flash(
            'Period marked as Payment Completed. Shareholders were notified by email + WhatsApp when enabled.',
            'success',
        )
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/export.xlsx')
@finance_or_management_required
def export_period_xlsx(period_id):
    """Download monthly profit distribution as Excel (sheet-style workbook)."""
    period = MonthlyPeriod.query.get_or_404(period_id)
    try:
        from apps.services.distribution_export_service import build_period_distribution_xlsx

        payload, filename = build_period_distribution_xlsx(period)
    except ValueError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    log_action('export', 'monthly_period', period.id, f'{period.period_label} Excel export')
    return send_file(
        BytesIO(payload),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@blueprint.route('/<int:period_id>/export.csv')
@finance_or_management_required
def export_period_csv(period_id):
    """Download monthly profit distribution as CSV."""
    period = MonthlyPeriod.query.get_or_404(period_id)
    try:
        from apps.services.distribution_export_service import build_period_distribution_csv

        payload, filename = build_period_distribution_csv(period)
    except ValueError as exc:
        flash(str(exc), 'warning')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    log_action('export', 'monthly_period', period.id, f'{period.period_label} CSV export')
    return send_file(
        BytesIO(payload.encode('utf-8-sig')),
        mimetype='text/csv; charset=utf-8',
        as_attachment=True,
        download_name=filename,
    )


@blueprint.route('/<int:period_id>/edit', methods=['GET', 'POST'])
@finance_or_management_required
def edit_period(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    if not period.is_editable:
        if period.awaits_approval:
            flash(
                'This period is awaiting approval and is locked. Management must return it to draft before figures can change.',
                'warning',
            )
        else:
            flash('Approved periods are locked and cannot be edited.', 'danger')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    form = PeriodForm(obj=period)
    extras = _form_extras()
    create_context = get_period_create_context(period.year, period.month)

    if form.validate_on_submit():
        if not create_context['ownership_valid']:
            flash(
                create_context['blocking_errors'][0]
                if create_context.get('blocking_errors')
                else 'Ownership must total exactly 100% before calculation.',
                'danger',
            )
            return render_template(
                'periods/form.html',
                form=form,
                title=f'Edit — {PERIOD_FORM_TITLE}',
                period=period,
                segment='periods',
                create_context=create_context,
                **extras,
            )

        previous_net = period.total_profit_loss
        _update_period_from_form(period, form)
        db.session.commit()
        try:
            calculate_period(period)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template(
                'periods/form.html',
                form=form,
                title=f'Edit — {PERIOD_FORM_TITLE}',
                period=period,
                segment='periods',
                create_context=create_context,
                **extras,
            )

        log_action('update', 'monthly_period', period.id, period.period_label)
        flash('Period updated and recalculated.', 'success')

        # Notify shareholders when Net Profit changed (or any update after review / prior send).
        net_changed = previous_net != period.total_profit_loss
        should_notify = net_changed or period.status == MonthlyPeriod.STATUS_REVIEW or bool(period.reports_sent_at)
        if should_notify and period.calculations.count():
            try:
                from apps.services.notification_service import notify_shareholders_period_update

                notify_shareholders_period_update(
                    period,
                    message='Figures were updated after recalculation.' if net_changed else None,
                )
            except Exception:
                pass
        return redirect(url_for('periods.detail_period', period_id=period.id))

    return render_template(
        'periods/form.html',
        form=form,
        title=f'Edit — {PERIOD_FORM_TITLE}',
        period=period,
        segment='periods',
        create_context=create_context,
        **extras,
    )


@blueprint.route('/<int:period_id>/recalculate', methods=['POST'])
@finance_or_management_required
def recalculate_period(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    if not period.is_editable:
        flash('Only draft periods can be recalculated. Return to draft first if changes are needed.', 'warning')
        return redirect(url_for('periods.detail_period', period_id=period.id))
    try:
        calculate_period(period)
        log_action('recalculate', 'monthly_period', period.id, period.period_label)
        flash('Period recalculated.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/submit-review', methods=['POST'])
@finance_or_management_required
def submit_review(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    try:
        submit_for_review(period, user=current_user)
        try:
            from apps.services.notification_service import notify_management_period_submitted

            notify_management_period_submitted(period, submitted_by=current_user)
        except Exception:
            # Audit + flash already recorded; email failure must not block workflow.
            pass
        flash('Period submitted for management review. Figures are locked until approved or returned.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/adjustments', methods=['POST'])
@finance_or_management_required
def add_adjustment(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    form = AdjustmentForm()
    form.shareholder_id.choices = [
        (sh.id, sh.name) for sh in Shareholder.query.filter_by(is_active=True).order_by(Shareholder.name)
    ]
    if period.is_locked:
        flash('Approved periods are locked.', 'danger')
        return redirect(url_for('periods.detail_period', period_id=period.id))
    if period.awaits_approval:
        flash('Periods in review are locked. Return to draft before adding adjustments.', 'warning')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    if form.validate_on_submit():
        adjustment = ManualAdjustment(
            period_id=period.id,
            shareholder_id=form.shareholder_id.data,
            amount=form.amount.data,
            reason=form.reason.data.strip(),
            created_by_id=current_user.id,
        )
        db.session.add(adjustment)
        db.session.commit()
        try:
            calculate_period(period)
            shareholder = Shareholder.query.get(form.shareholder_id.data)
            from apps.services.display_settings_service import money_label

            log_action(
                'adjustment',
                'manual_adjustment',
                adjustment.id,
                f'{period.period_label}: {money_label(form.amount.data)} for '
                f'{shareholder.name if shareholder else "shareholder"} — {form.reason.data.strip()}',
            )
            flash('Manual adjustment added and period recalculated.', 'success')
        except ValueError as exc:
            db.session.delete(adjustment)
            db.session.commit()
            flash(
                f'Adjustment was not kept because calculation failed: {exc}',
                'danger',
            )
    else:
        flash('Could not save adjustment. Check the form fields.', 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/approve', methods=['POST'])
@management_required
def approve_period_view(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    try:
        approve_period(period, current_user)
        log_action('approve', 'monthly_period', period.id, period.period_label)
        try:
            from apps.services.notification_service import notify_management_period_approved

            notify_management_period_approved(period, approved_by=current_user)
        except Exception:
            pass
        try:
            results = auto_send_period_reports(period)
            if results:
                from apps.services.notification_service import count_dual_results, flash_dual_summary

                failed = [r for r in results if not r.get('ok', True)]
                dual_rows = []
                for r in results:
                    dual_rows.append({
                        'email': r.get('email') or {},
                        'whatsapp': (r.get('notifications') or {}).get('whatsapp') or {},
                    })
                counts = count_dual_results(dual_rows)
                log_action('send_reports', 'monthly_period', period.id, period.period_label)
                if failed:
                    names = ', '.join(r['shareholder'] for r in failed)
                    flash(
                        'Period approved and branded certificates generated. '
                        f'Some shareholder notifications failed ({names}). Use Send Reports Now to retry.',
                        'warning',
                    )
                else:
                    msg, cat = flash_dual_summary(counts, noun='shareholder report')
                    flash(
                        f'Period approved. Branded certificates generated. {msg}',
                        cat,
                    )
            else:
                flash(
                    'Period approved and branded certificates generated automatically. '
                    'Report delivery is disabled in system settings — enable email/WhatsApp under '
                    'Settings → System, or use Send Reports Now.',
                    'success',
                )
        except ValueError as exc:
            flash(
                f'Period approved and certificates generated, but automatic delivery failed: {exc}. '
                'Use Send Reports Now from the period page.',
                'warning',
            )
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/send-reports', methods=['POST'])
@management_required
def send_reports_view(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    force = request.form.get('force') == '1'
    try:
        results = send_period_reports(period, force=force)
        log_action('send_reports', 'monthly_period', period.id, period.period_label)
        from apps.services.notification_service import count_dual_results, flash_dual_summary

        dual_rows = []
        for r in results or []:
            dual_rows.append({
                'email': r.get('email') or {},
                'whatsapp': (r.get('notifications') or {}).get('whatsapp') or {},
            })
        counts = count_dual_results(dual_rows)
        failed = [r for r in (results or []) if not r.get('ok', True)]
        if failed:
            names = ', '.join(r['shareholder'] for r in failed)
            flash(
                f'Some notifications failed ({names}). '
                'Check SMTP, Twilio WhatsApp, and shareholder emails/phones.',
                'warning',
            )
        else:
            msg, cat = flash_dual_summary(counts, noun='shareholder report')
            flash(msg, cat)
    except ValueError as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/send-update', methods=['POST'])
@finance_or_management_required
def send_shareholder_update(period_id):
    """Email + WhatsApp all shareholders on this period with a profit / distribution update."""
    period = MonthlyPeriod.query.get_or_404(period_id)
    form = ShareholderUpdateForm()
    if not form.validate_on_submit():
        flash('Could not send update. Check the message and try again.', 'danger')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    if not period.calculations.count():
        flash('Calculate the period before sending shareholder updates.', 'warning')
        return redirect(url_for('periods.detail_period', period_id=period.id))

    try:
        from apps.services.notification_service import (
            flash_dual_summary,
            notify_shareholders_period_update,
        )

        result = notify_shareholders_period_update(
            period,
            message=form.message.data,
            reason='manual_update',
            actor=current_user,
            respect_setting=False,  # manual send always allowed
        )
        if not result.get('ok'):
            flash('No shareholder updates were sent.', 'warning')
        else:
            msg, cat = flash_dual_summary(
                result.get('counts') or {},
                noun='shareholder update',
            )
            flash(msg, cat)
    except Exception as exc:
        flash(f'Could not send shareholder update: {exc}', 'danger')

    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/reject', methods=['POST'])
@management_required
def reject_period_view(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    form = PeriodRejectForm()
    if form.validate_on_submit():
        try:
            reject_period(period, current_user, form.reason.data)
            try:
                from apps.services.notification_service import notify_finance_period_rejected

                notify_finance_period_rejected(period, rejected_by=current_user)
            except Exception:
                pass
            flash(
                'Period returned to draft. Finance has been notified by email/WhatsApp to make changes and re-submit.',
                'warning',
            )
        except ValueError as exc:
            flash(str(exc), 'danger')
    else:
        flash('A rejection reason is required.', 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))


@blueprint.route('/<int:period_id>/reopen-correction', methods=['POST'])
@management_required
def reopen_correction(period_id):
    period = MonthlyPeriod.query.get_or_404(period_id)
    form = CorrectionReopenForm()
    if form.validate_on_submit():
        try:
            _, reason = reopen_for_correction(period, form.reason.data, user=current_user)
            log_action('correction_reopen', 'monthly_period', period.id, reason)
            try:
                from apps.services.notification_service import notify_finance_period_rejected

                notify_finance_period_rejected(period, rejected_by=current_user)
            except Exception:
                pass
            flash(
                'Period reopened as draft. Finance was notified by email/WhatsApp. '
                'Edit figures, recalculate, then submit for review again before approval.',
                'warning',
            )
        except ValueError as exc:
            flash(str(exc), 'danger')
    else:
        flash('A detailed reason is required to reopen an approved period.', 'danger')
    return redirect(url_for('periods.detail_period', period_id=period.id))
