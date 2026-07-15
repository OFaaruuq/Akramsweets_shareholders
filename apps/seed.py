from datetime import date
from decimal import Decimal
import os

from apps import db
from apps.models.arrangement import SpecialArrangement
from apps.models.settings import SystemSetting
from apps.models.shareholder import OwnershipRecord, Shareholder
from apps.models.user import User


PORTAL_USERS = (
    ('Shareholder A', 'shareholder.a@akramsweets.com', 'Shareholder A', 'shareholder123'),
    ('Shareholder B', 'shareholder.b@akramsweets.com', 'Shareholder B', 'shareholder123'),
)


def _demo_seed_enabled():
    """
    Demo users/shareholders are only auto-created when explicitly allowed.

    - SEED_DEMO_DATA=true forces seeding
    - SEED_DEMO_DATA=false disables seeding even in DEBUG
    - Otherwise DEBUG mode seeds an empty database for local development
    """
    flag = os.getenv('SEED_DEMO_DATA')
    if flag is not None and str(flag).strip() != '':
        return str(flag).strip().lower() in ('1', 'true', 'yes', 'on')
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            return bool(current_app.debug)
    except RuntimeError:
        pass
    return str(os.getenv('DEBUG', 'False')).strip().lower() in ('1', 'true', 'yes', 'on')


def seed_if_empty():
    if User.query.count():
        if _demo_seed_enabled():
            seed_portal_users_if_missing()
        return

    if not _demo_seed_enabled():
        return

    owner = Shareholder(
        name='Pocly (Owner)',
        email='pocly@akramsweets.com',
        country='Somalia',
        country_code='so',
        is_owner=True,
        is_active=True,
    )
    shareholder_a = Shareholder(
        name='Shareholder A',
        email='shareholder.a@akramsweets.com',
        country='United Arab Emirates',
        country_code='ae',
        is_active=True,
    )
    shareholder_b = Shareholder(
        name='Shareholder B',
        email='shareholder.b@akramsweets.com',
        country='Kenya',
        country_code='ke',
        is_active=True,
    )
    db.session.add_all([owner, shareholder_a, shareholder_b])
    db.session.flush()

    effective = date(2026, 1, 1)
    db.session.add_all([
        OwnershipRecord(shareholder_id=owner.id, ownership_percent=Decimal('30'), effective_from=effective),
        OwnershipRecord(shareholder_id=shareholder_a.id, ownership_percent=Decimal('40'), effective_from=effective),
        OwnershipRecord(shareholder_id=shareholder_b.id, ownership_percent=Decimal('30'), effective_from=effective),
    ])

    db.session.add(
        SpecialArrangement(
            name='Owner bonus from other shareholders',
            recipient_shareholder_id=owner.id,
            bonus_percent=Decimal('20'),
            applies_to_all_others=True,
            apply_on_profit=True,
            apply_on_loss=True,
            effective_from=effective,
            notes='Example arrangement from business requirements document.',
        )
    )

    admin = User(
        email='admin@akramsweets.com',
        full_name='System Administrator',
        role=User.ROLE_OWNER,
    )
    admin.set_password('admin123')

    finance = User(
        email='finance@akramsweets.com',
        full_name='Finance Staff',
        role=User.ROLE_FINANCE,
    )
    finance.set_password('finance123')

    system_admin = User(
        email='sysadmin@akramsweets.com',
        full_name='System Administrator',
        role=User.ROLE_ADMIN,
    )
    system_admin.set_password('admin123')

    db.session.add_all([admin, finance, system_admin])
    db.session.flush()
    _create_portal_users([shareholder_a, shareholder_b])
    SystemSetting.set('auto_email_on_approval', 'true')
    from apps.services.brand_service import ensure_default_brand_settings
    from apps.services.share_value_service import ensure_default_share_settings

    ensure_default_brand_settings()
    ensure_default_share_settings()
    db.session.commit()


def seed_portal_users_if_missing():
    if not _demo_seed_enabled():
        return

    from apps.services.brand_service import ensure_default_brand_settings

    ensure_default_brand_settings()
    shareholders = {
        sh.name: sh
        for sh in Shareholder.query.filter(Shareholder.name.in_([row[0] for row in PORTAL_USERS])).all()
    }
    created = False
    for shareholder_name, email, full_name, password in PORTAL_USERS:
        shareholder = shareholders.get(shareholder_name)
        if not shareholder:
            continue
        existing = User.query.filter_by(email=email).first()
        if existing:
            continue
        user = User(
            email=email,
            full_name=full_name,
            role=User.ROLE_SHAREHOLDER,
            shareholder_id=shareholder.id,
        )
        user.set_password(password)
        db.session.add(user)
        created = True
    if created:
        db.session.commit()


def _create_portal_users(shareholders):
    by_name = {sh.name: sh for sh in shareholders}
    for shareholder_name, email, full_name, password in PORTAL_USERS:
        shareholder = by_name.get(shareholder_name)
        if not shareholder:
            continue
        user = User(
            email=email,
            full_name=full_name,
            role=User.ROLE_SHAREHOLDER,
            shareholder_id=shareholder.id,
        )
        user.set_password(password)
        db.session.add(user)
