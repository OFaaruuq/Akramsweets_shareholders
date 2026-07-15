from datetime import datetime
from decimal import Decimal

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from apps import db
from apps.auth.decorators import finance_or_management_required, management_required
from apps.auth.forms import ShareholderPortalAccountForm
from apps.forms import ShareholderForm
from apps.models.shareholder import OwnershipRecord, Shareholder
from apps.services.audit_service import log_action
from apps.services.portal_service import create_shareholder_portal_user, deactivate_shareholder_portal_user
from apps.services.shareholder_service import (
    COUNTRY_CHOICES,
    country_flag_filename,
    country_label,
    get_ownership_percent,
    validate_ownership_totals,
)
from apps.shareholders import blueprint


def _prepare_shareholder_form(form, is_create=False, ownership_ctx=None):
    form.country_code.choices = list(COUNTRY_CHOICES)
    if not form.country_code.data:
        form.country_code.data = 'so'
    if is_create and request.method == 'GET':
        form.effective_from.data = datetime.utcnow().date()
        form.is_active.data = True
        # Suggest remaining ownership so totals stay near 100%.
        if ownership_ctx and ownership_ctx.get('remaining', 0) > 0.01:
            form.ownership_percent.data = round(Decimal(str(ownership_ctx['remaining'])), 4)


def _apply_country(shareholder, country_code):
    code = (country_code or 'so').lower()
    shareholder.country_code = code
    shareholder.country = country_label(code)


def _ownership_context(as_of_date=None, exclude_shareholder_id=None):
    as_of = as_of_date or datetime.utcnow().date()
    total, shareholders = validate_ownership_totals(as_of)
    rows = []
    for shareholder in shareholders:
        if exclude_shareholder_id and shareholder.id == exclude_shareholder_id:
            continue
        percent = get_ownership_percent(shareholder, as_of)
        rows.append({
            'id': shareholder.id,
            'name': shareholder.name,
            'country': shareholder.country,
            'country_code': shareholder.country_code,
            'flag': country_flag_filename(shareholder.country_code),
            'ownership_percent': float(percent),
            'is_owner': shareholder.is_owner,
        })
    allocated = float(sum(Decimal(str(row['ownership_percent'])) for row in rows))
    remaining = float(Decimal('100') - Decimal(str(allocated)))
    return {
        'as_of': as_of,
        'rows': rows,
        'allocated': allocated,
        'remaining': remaining,
        'valid': abs(Decimal(str(allocated)) - Decimal('100')) <= Decimal('0.01') if exclude_shareholder_id else abs(total - Decimal('100')) <= Decimal('0.01'),
        'total_with_all': float(total),
    }


def _email_taken(email, exclude_id=None):
    query = Shareholder.query.filter(Shareholder.email == email.lower())
    if exclude_id:
        query = query.filter(Shareholder.id != exclude_id)
    return query.first() is not None


@blueprint.route('/')
@finance_or_management_required
def list_shareholders():
    from apps.services.certificate_service import get_latest_approved_period, get_shareholder_certificate

    shareholders = Shareholder.query.order_by(Shareholder.name).all()
    latest_period = get_latest_approved_period()
    q = (request.args.get('q') or '').strip().lower()
    country_filter = request.args.get('country')
    rows = []
    for shareholder in shareholders:
        if country_filter and (shareholder.country_code or '').lower() != country_filter.lower():
            continue
        if q and q not in shareholder.name.lower() and q not in (shareholder.email or '').lower():
            continue
        ownership = get_ownership_percent(shareholder, datetime.utcnow().date())
        certificate = (
            get_shareholder_certificate(latest_period.id, shareholder.id) if latest_period else None
        )
        from apps.services.share_value_service import capital_for_ownership, shares_for_ownership

        share_units = shares_for_ownership(ownership)
        capital = capital_for_ownership(ownership)
        rows.append({
            'shareholder': shareholder,
            'ownership_percent': float(ownership),
            'share_units': float(share_units) if share_units is not None else None,
            'capital': float(capital) if capital is not None else None,
            'flag': country_flag_filename(shareholder.country_code),
            'country_name': shareholder.country or country_label(shareholder.country_code),
            'latest_period': latest_period,
            'latest_certificate': certificate,
        })
    return render_template(
        'shareholders/list.html',
        rows=rows,
        country_filter=country_filter,
        segment='shareholders',
    )


@blueprint.route('/create', methods=['GET', 'POST'])
@management_required
def create_shareholder():
    form = ShareholderForm()
    ownership_ctx = _ownership_context()
    _prepare_shareholder_form(form, is_create=True, ownership_ctx=ownership_ctx)
    if form.effective_from.data:
        ownership_ctx = _ownership_context(form.effective_from.data)

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if _email_taken(email):
            form.email.errors.append('A shareholder with this email already exists.')
            flash('Please fix the highlighted fields.', 'danger')
        elif form.create_portal.data and not form.portal_password.data:
            form.portal_password.errors.append('Portal password is required when creating portal login.')
            flash('Please fix the highlighted fields.', 'danger')
        else:
            shareholder = Shareholder(
                name=form.name.data.strip(),
                email=email,
                phone=(form.phone.data or '').strip() or None,
                is_owner=form.is_owner.data,
                is_active=True if form.is_active.data else False,
                notes=form.notes.data,
                investment_amount=form.investment_amount.data or 0,
                share_count=form.share_count.data or 0,
                investment_date=form.investment_date.data,
            )
            _apply_country(shareholder, form.country_code.data)
            db.session.add(shareholder)
            db.session.flush()

            ownership = OwnershipRecord(
                shareholder_id=shareholder.id,
                ownership_percent=form.ownership_percent.data,
                effective_from=form.effective_from.data,
                created_by_id=current_user.id,
            )
            db.session.add(ownership)
            db.session.commit()

            if form.create_portal.data:
                portal_email = (form.portal_email.data or email).strip().lower()
                try:
                    create_shareholder_portal_user(
                        shareholder,
                        portal_email,
                        form.name.data.strip(),
                        form.portal_password.data,
                        current_user.id,
                    )
                except ValueError as exc:
                    flash(f'Shareholder saved, but portal account failed: {exc}', 'warning')

            total, _ = validate_ownership_totals(form.effective_from.data)
            if abs(total - Decimal('100')) > Decimal('0.01'):
                flash(
                    f'Shareholder created. Active ownership now totals {total:.2f}% '
                    f'(remaining to allocate: {100 - float(total):.2f}%).',
                    'warning',
                )
            else:
                flash('Shareholder created successfully. Ownership totals 100%.', 'success')
            log_action('create', 'shareholder', shareholder.id, shareholder.name)
            return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))
    elif request.method == 'POST':
        flash('Please fix the highlighted fields.', 'danger')
        ownership_ctx = _ownership_context(form.effective_from.data)

    return render_template(
        'shareholders/form.html',
        form=form,
        title='Add Shareholder',
        ownership_ctx=ownership_ctx,
        is_create=True,
        segment='shareholders',
    )


@blueprint.route('/<int:shareholder_id>/edit', methods=['GET', 'POST'])
@management_required
def edit_shareholder(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    form = ShareholderForm(obj=shareholder)
    _prepare_shareholder_form(form)
    latest_ownership = shareholder.ownership_records.first()
    if latest_ownership and request.method == 'GET':
        form.ownership_percent.data = latest_ownership.ownership_percent
        form.effective_from.data = latest_ownership.effective_from
        form.country_code.data = shareholder.country_code or 'so'

    ownership_ctx = _ownership_context(
        form.effective_from.data or datetime.utcnow().date(),
        exclude_shareholder_id=shareholder.id,
    )

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if _email_taken(email, exclude_id=shareholder.id):
            form.email.errors.append('A shareholder with this email already exists.')
            flash('Please fix the highlighted fields.', 'danger')
        else:
            shareholder.name = form.name.data.strip()
            shareholder.email = email
            shareholder.phone = (form.phone.data or '').strip() or None
            shareholder.is_owner = form.is_owner.data
            shareholder.is_active = form.is_active.data
            shareholder.notes = form.notes.data
            shareholder.investment_amount = form.investment_amount.data or 0
            shareholder.share_count = form.share_count.data or 0
            shareholder.investment_date = form.investment_date.data
            _apply_country(shareholder, form.country_code.data)

            if (
                not latest_ownership
                or latest_ownership.ownership_percent != form.ownership_percent.data
                or latest_ownership.effective_from != form.effective_from.data
            ):
                if latest_ownership and latest_ownership.effective_from == form.effective_from.data:
                    latest_ownership.ownership_percent = form.ownership_percent.data
                else:
                    if latest_ownership and latest_ownership.effective_to is None:
                        latest_ownership.effective_to = form.effective_from.data
                    db.session.add(
                        OwnershipRecord(
                            shareholder_id=shareholder.id,
                            ownership_percent=form.ownership_percent.data,
                            effective_from=form.effective_from.data,
                            created_by_id=current_user.id,
                        )
                    )

            db.session.commit()
            total, _ = validate_ownership_totals(form.effective_from.data)
            if abs(total - Decimal('100')) > Decimal('0.01'):
                flash(f'Shareholder updated. Active ownership totals {total:.2f}% (expected 100%).', 'warning')
            else:
                flash('Shareholder updated successfully.', 'success')
            log_action('update', 'shareholder', shareholder.id, shareholder.name)
            return redirect(url_for('shareholders.list_shareholders'))
    elif request.method == 'POST':
        flash('Please fix the highlighted fields.', 'danger')

    portal_form = ShareholderPortalAccountForm()
    if request.method == 'GET':
        portal_form.email.data = shareholder.user_account.email if shareholder.user_account else shareholder.email
        portal_form.full_name.data = shareholder.user_account.full_name if shareholder.user_account else shareholder.name

    return render_template(
        'shareholders/form.html',
        form=form,
        title='Edit Shareholder',
        shareholder=shareholder,
        portal_form=portal_form,
        ownership_ctx=ownership_ctx,
        is_create=False,
        segment='shareholders',
    )


@blueprint.route('/<int:shareholder_id>/portal-account', methods=['POST'])
@management_required
def save_portal_account(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    portal_form = ShareholderPortalAccountForm()
    if portal_form.validate_on_submit():
        try:
            create_shareholder_portal_user(
                shareholder,
                portal_form.email.data,
                portal_form.full_name.data,
                portal_form.password.data,
                current_user.id,
            )
            flash('Shareholder portal access saved.', 'success')
        except ValueError as exc:
            flash(str(exc), 'danger')
    else:
        flash('Could not save portal access. Check the form fields.', 'danger')

    return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))


@blueprint.route('/<int:shareholder_id>/portal-account/deactivate', methods=['POST'])
@management_required
def deactivate_portal_account(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    deactivate_shareholder_portal_user(shareholder, current_user.id)
    flash('Shareholder portal access deactivated.', 'success')
    return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))


@blueprint.route('/<int:shareholder_id>/deactivate', methods=['POST'])
@management_required
def deactivate_shareholder(shareholder_id):
    shareholder = Shareholder.query.get_or_404(shareholder_id)
    if shareholder.is_owner:
        flash('The company owner shareholder cannot be deactivated.', 'danger')
        return redirect(url_for('shareholders.edit_shareholder', shareholder_id=shareholder.id))

    shareholder.is_active = False
    latest_ownership = shareholder.ownership_records.first()
    if latest_ownership and latest_ownership.effective_to is None:
        latest_ownership.effective_to = datetime.utcnow().date()
    if shareholder.user_account:
        shareholder.user_account.is_active = False
    db.session.commit()
    log_action('deactivate', 'shareholder', shareholder.id, shareholder.name)
    flash('Shareholder deactivated.', 'success')
    return redirect(url_for('shareholders.list_shareholders'))


@blueprint.route('/withdrawals')
@finance_or_management_required
def list_withdrawals():
    from apps.services.capital_withdrawal_service import list_withdrawal_requests

    status = (request.args.get('status') or '').strip() or None
    requests = list_withdrawal_requests(status=status)
    return render_template(
        'shareholders/withdrawals.html',
        requests=requests,
        status_filter=status,
        segment='withdrawals',
    )


@blueprint.route('/withdrawals/<int:request_id>', methods=['GET', 'POST'])
@finance_or_management_required
def review_withdrawal(request_id):
    from apps.forms import CapitalWithdrawalReviewForm
    from apps.models.shareholder import CapitalWithdrawalRequest
    from apps.services.capital_withdrawal_service import (
        approve_withdrawal,
        cancel_withdrawal,
        complete_withdrawal,
        reject_withdrawal,
    )

    withdrawal = CapitalWithdrawalRequest.query.get_or_404(request_id)
    form = CapitalWithdrawalReviewForm()
    can_act = current_user.is_management()

    if request.method == 'GET':
        form.review_notes.data = withdrawal.review_notes
        form.capital_return_date.data = withdrawal.capital_return_date or datetime.utcnow().date()

    if request.method == 'POST' and not can_act:
        flash('Only owners/admins can approve or update capital withdrawal requests.', 'danger')
        return redirect(url_for('shareholders.review_withdrawal', request_id=withdrawal.id))

    if can_act and form.validate_on_submit():
        try:
            if form.submit_approve.data:
                approve_withdrawal(withdrawal.id, current_user, form.review_notes.data)
                flash('Capital withdrawal approved. Company has up to 6 months to return capital.', 'success')
            elif form.submit_reject.data:
                reject_withdrawal(withdrawal.id, current_user, form.review_notes.data)
                flash('Capital withdrawal rejected.', 'warning')
            elif form.submit_complete.data:
                complete_withdrawal(
                    withdrawal.id,
                    current_user,
                    capital_return_date=form.capital_return_date.data,
                    review_notes=form.review_notes.data,
                )
                flash('Capital return recorded as completed.', 'success')
            elif form.submit_cancel.data:
                cancel_withdrawal(withdrawal.id, current_user, form.review_notes.data)
                flash('Capital withdrawal cancelled.', 'info')
            return redirect(url_for('periods.approvals_inbox'))
        except ValueError as exc:
            flash(str(exc), 'danger')

    return render_template(
        'shareholders/withdrawal_detail.html',
        withdrawal=withdrawal,
        form=form,
        can_act=can_act,
        segment='approvals',
    )
