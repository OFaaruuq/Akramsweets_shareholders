from datetime import datetime
from io import BytesIO

from flask import flash, redirect, render_template, send_file, url_for

from apps.app_settings import blueprint
from apps.auth.decorators import management_required
from apps.forms import ArrangementForm, DashboardSettingsForm, SystemSettingsForm
from apps.models.arrangement import SpecialArrangement
from apps.models.audit import AuditLog
from apps.models.settings import SystemSetting
from apps.models.shareholder import Shareholder
from apps import db
from apps.services.audit_service import log_action
from apps.services.dashboard_service import get_dashboard_manual_kpis, save_dashboard_manual_kpis


@blueprint.route('/')
@management_required
def settings_home():
    return redirect(url_for('app_settings.arrangements'))


def _shareholder_choices():
    return [
        (sh.id, sh.name)
        for sh in Shareholder.query.filter_by(is_active=True).order_by(Shareholder.name)
    ]


def _sync_arrangement_sources(arrangement, form):
    if form.applies_to_all_others.data:
        arrangement.source_shareholders = []
        return
    selected_ids = set(form.source_shareholder_ids.data or [])
    selected_ids.discard(form.recipient_shareholder_id.data)
    arrangement.source_shareholders = Shareholder.query.filter(
        Shareholder.id.in_(selected_ids),
        Shareholder.is_active.is_(True),
    ).all() if selected_ids else []


@blueprint.route('/arrangements', methods=['GET', 'POST'])
@management_required
def arrangements():
    form = ArrangementForm()
    choices = _shareholder_choices()
    form.recipient_shareholder_id.choices = choices
    form.source_shareholder_ids.choices = choices

    if form.validate_on_submit():
        arrangement = SpecialArrangement(
            name=form.name.data.strip(),
            recipient_shareholder_id=form.recipient_shareholder_id.data,
            bonus_percent=form.bonus_percent.data,
            applies_to_all_others=form.applies_to_all_others.data,
            apply_on_profit=form.apply_on_profit.data,
            apply_on_loss=form.apply_on_loss.data,
            effective_from=form.effective_from.data,
            effective_to=form.effective_to.data,
            notes=form.notes.data,
        )
        db.session.add(arrangement)
        db.session.flush()
        _sync_arrangement_sources(arrangement, form)
        db.session.commit()
        log_action('create', 'special_arrangement', arrangement.id, arrangement.name)
        flash('Special arrangement saved.', 'success')
        return redirect(url_for('app_settings.arrangements'))

    rows = SpecialArrangement.query.order_by(SpecialArrangement.effective_from.desc()).all()
    return render_template(
        'settings/arrangements.html',
        form=form,
        rows=rows,
        segment='settings',
    )


@blueprint.route('/arrangements/<int:arrangement_id>/edit', methods=['GET', 'POST'])
@management_required
def edit_arrangement(arrangement_id):
    arrangement = SpecialArrangement.query.get_or_404(arrangement_id)
    form = ArrangementForm(obj=arrangement)
    choices = _shareholder_choices()
    form.recipient_shareholder_id.choices = choices
    form.source_shareholder_ids.choices = choices
    if not form.is_submitted():
        form.source_shareholder_ids.data = [s.id for s in arrangement.source_shareholders]

    if form.validate_on_submit():
        arrangement.name = form.name.data.strip()
        arrangement.recipient_shareholder_id = form.recipient_shareholder_id.data
        arrangement.bonus_percent = form.bonus_percent.data
        arrangement.applies_to_all_others = form.applies_to_all_others.data
        arrangement.apply_on_profit = form.apply_on_profit.data
        arrangement.apply_on_loss = form.apply_on_loss.data
        arrangement.effective_from = form.effective_from.data
        arrangement.effective_to = form.effective_to.data
        arrangement.notes = form.notes.data
        _sync_arrangement_sources(arrangement, form)
        db.session.commit()
        log_action('update', 'special_arrangement', arrangement.id, arrangement.name)
        flash('Special arrangement updated.', 'success')
        return redirect(url_for('app_settings.arrangements'))

    return render_template(
        'settings/arrangement_form.html',
        form=form,
        title='Edit Special Arrangement',
        arrangement=arrangement,
        segment='settings',
    )


@blueprint.route('/arrangements/<int:arrangement_id>/deactivate', methods=['POST'])
@management_required
def deactivate_arrangement(arrangement_id):
    arrangement = SpecialArrangement.query.get_or_404(arrangement_id)
    arrangement.is_active = False
    db.session.commit()
    log_action('deactivate', 'special_arrangement', arrangement.id, arrangement.name)
    flash('Special arrangement deactivated.', 'success')
    return redirect(url_for('app_settings.arrangements'))


@blueprint.route('/dashboard', methods=['GET', 'POST'])
@management_required
def dashboard_settings():
    manual = get_dashboard_manual_kpis()
    form = DashboardSettingsForm(
        total_revenues=manual['total_revenues'],
        total_expenses=manual['total_expenses'],
        cost_of_goods=manual['cost_of_goods'],
        other_income=manual['other_income'],
        operating_notes=manual['operating_notes'],
    )

    if form.validate_on_submit():
        save_dashboard_manual_kpis(form)
        log_action('update', 'dashboard_settings', None, 'Updated dashboard KPI figures')
        flash('Dashboard figures saved. The main dashboard will reflect these values.', 'success')
        return redirect(url_for('app_settings.dashboard_settings'))

    return render_template('settings/dashboard.html', form=form, segment='dashboard-settings')


@blueprint.route('/system', methods=['GET', 'POST'])
@management_required
def system_settings():
    from apps.services.brand_service import ensure_default_brand_settings, get_brand_settings, save_brand_settings
    from apps.services.certificate_settings_service import (
        ensure_default_certificate_settings,
        get_certificate_settings,
        save_certificate_settings,
    )

    ensure_default_brand_settings()
    ensure_default_certificate_settings()
    brand = get_brand_settings()
    cert = get_certificate_settings()
    form = SystemSettingsForm(
        auto_email_on_approval=str(SystemSetting.get('auto_email_on_approval', 'true')).lower() in ('1', 'true', 'yes', 'on'),
        report_delivery_day=SystemSetting.get('report_delivery_day'),
        mail_from=SystemSetting.get('mail_from'),
        mail_server=SystemSetting.get('mail_server'),
        mail_port=SystemSetting.get('mail_port') or 587,
        mail_username=SystemSetting.get('mail_username'),
        mail_password=SystemSetting.get('mail_password'),
        brand_company_name=brand['company_name'],
        brand_primary_color=brand['primary_color'],
        brand_secondary_color=brand['secondary_color'],
        brand_accent_color=brand['accent_color'],
        cert_subtitle=cert['subtitle'],
        cert_title=cert['title'],
        cert_intro_text=cert['intro_text'],
        cert_allocation_text=cert['allocation_text'],
        cert_profit_label=cert['profit_label'],
        cert_loss_label=cert['loss_label'],
        cert_currency_symbol=cert['currency_symbol'],
        cert_number_prefix=cert['number_prefix'],
        cert_approver_fallback=cert['approver_fallback'],
        cert_owner_label=cert['owner_label'],
        cert_roster_title=cert['roster_title'],
        cert_label_company_pl=cert['label_company_pl'],
        cert_label_base_share=cert['label_base_share'],
        cert_label_ytd=cert['label_ytd'],
        cert_label_odoo=cert['label_odoo'],
        cert_footer_disclaimer=cert['footer_disclaimer'],
        cert_footer_confidential=cert['footer_confidential'],
        cert_legal_text=cert['legal_text'],
        cert_show_roster=cert['show_roster'],
        cert_show_odoo_reference=cert['show_odoo_reference'],
        cert_signature_name=cert['signature_name'],
        cert_signature_title=cert['signature_title'],
    )

    if form.validate_on_submit():
        SystemSetting.set('auto_email_on_approval', 'true' if form.auto_email_on_approval.data else 'false')
        for key in (
            'report_delivery_day',
            'mail_from',
            'mail_server',
            'mail_port',
            'mail_username',
            'mail_password',
        ):
            value = getattr(form, key).data
            SystemSetting.set(key, '' if value is None else str(value))
        try:
            save_brand_settings(
                form.brand_company_name.data,
                form.brand_primary_color.data,
                form.brand_secondary_color.data,
                form.brand_accent_color.data,
                logo_file=form.brand_logo.data,
                remove_logo=form.remove_brand_logo.data,
            )
            save_certificate_settings(
                {
                    'subtitle': form.cert_subtitle.data,
                    'title': form.cert_title.data,
                    'intro_text': form.cert_intro_text.data,
                    'allocation_text': form.cert_allocation_text.data,
                    'profit_label': form.cert_profit_label.data,
                    'loss_label': form.cert_loss_label.data,
                    'currency_symbol': form.cert_currency_symbol.data,
                    'number_prefix': form.cert_number_prefix.data,
                    'approver_fallback': form.cert_approver_fallback.data,
                    'owner_label': form.cert_owner_label.data,
                    'roster_title': form.cert_roster_title.data,
                    'label_company_pl': form.cert_label_company_pl.data,
                    'label_base_share': form.cert_label_base_share.data,
                    'label_ytd': form.cert_label_ytd.data,
                    'label_odoo': form.cert_label_odoo.data,
                    'footer_disclaimer': form.cert_footer_disclaimer.data,
                    'footer_confidential': form.cert_footer_confidential.data,
                    'legal_text': form.cert_legal_text.data,
                    'show_roster': form.cert_show_roster.data,
                    'show_odoo_reference': form.cert_show_odoo_reference.data,
                    'signature_name': form.cert_signature_name.data,
                    'signature_title': form.cert_signature_title.data,
                },
                signature_file=form.cert_signature_image.data,
                remove_signature=form.remove_cert_signature.data,
            )
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template(
                'settings/system.html',
                form=form,
                brand=get_brand_settings(),
                cert=get_certificate_settings(),
                segment='settings',
            )

        log_action('update', 'system_settings', None, 'Updated system, brand, and certificate settings')
        flash('Settings saved. New certificates will use the updated brand and certificate content.', 'success')
        return redirect(url_for('app_settings.system_settings'))

    return render_template(
        'settings/system.html',
        form=form,
        brand=brand,
        cert=cert,
        segment='settings',
    )


@blueprint.route('/system/preview-certificate')
@management_required
def preview_certificate():
    """Download a sample branded certificate using current logo, colors, and certificate text."""
    from apps.services.brand_service import ensure_default_brand_settings, get_brand_settings
    from apps.services.certificate_settings_service import (
        ensure_default_certificate_settings,
        format_certificate_text,
        get_certificate_settings,
    )
    from apps.services.pdf_service import certificate_pdf_filename, generate_shareholder_certificate_pdf

    ensure_default_brand_settings()
    ensure_default_certificate_settings()
    brand = get_brand_settings()
    cert = get_certificate_settings()
    now = datetime.utcnow()
    period_label = now.strftime('%B %Y')
    sample = {
        'period_label': period_label,
        'generated_at': now,
        'company_total': 100000,
        'shareholder_name': 'Sample Shareholder',
        'shareholder_email': 'shareholder@example.com',
        'shareholder_phone': '+252 61 0000000',
        'shareholder_id': 0,
        'shareholder_is_owner': False,
        'ownership_percent': 40,
        'base_share': 40000,
        'final_amount': 40000,
        'ytd_total': 120000,
        'certificate_number': f"{cert['number_prefix']}-PREVIEW-{now.strftime('%Y%m')}",
        'certificate_issued_at': now,
        'approved_at': now,
        'approved_by': cert['approver_fallback'],
        'company_name': brand['company_name'],
        'brand_primary_color': brand['primary_color'],
        'brand_secondary_color': brand['secondary_color'],
        'brand_accent_color': brand['accent_color'],
        'brand_logo_path': brand['logo_filesystem_path'],
        'current_shareholders': (
            [
                {'id': 1, 'name': 'Pocly (Owner)', 'ownership_percent': 30, 'is_owner': True},
                {'id': 0, 'name': 'Sample Shareholder', 'ownership_percent': 40, 'is_owner': False},
                {'id': 2, 'name': 'Shareholder B', 'ownership_percent': 30, 'is_owner': False},
            ]
            if cert['show_roster']
            else []
        ),
        'odoo_reference': 'PREVIEW' if cert['show_odoo_reference'] else None,
        'cert_subtitle': cert['subtitle'],
        'cert_title': cert['title'],
        'cert_intro_text': cert['intro_text'],
        'cert_allocation_text': format_certificate_text(
            cert['allocation_text'],
            period_label=period_label,
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
            period_label=period_label,
        ),
        'cert_legal_text': cert['legal_text'],
        'cert_show_odoo_reference': cert['show_odoo_reference'],
        'cert_signature_name': cert['signature_name'],
        'cert_signature_title': cert['signature_title'],
        'cert_signature_image_path': cert['signature_filesystem_path'],
    }
    pdf_bytes = generate_shareholder_certificate_pdf(sample)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=certificate_pdf_filename(sample).replace(
            sample['certificate_number'].replace('/', '-'),
            'Preview',
        ),
    )


@blueprint.route('/audit-log')
@management_required
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('settings/audit_log.html', logs=logs, segment='audit-log')
