from decimal import Decimal

from apps import db
from apps.models.audit import AuditLog


def log_action(action, entity_type, entity_id=None, details=None, user=None):
    from flask_login import current_user

    actor = user or (current_user if getattr(current_user, 'is_authenticated', False) else None)
    entry = AuditLog(
        user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.session.add(entry)
    db.session.commit()
    return entry
