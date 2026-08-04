"""Generic field-diffing audit trail. register_audit(Model) wires pre_save/post_save/
post_delete signals that record a focused before/after diff (only the fields that actually
changed) into AuditLog, attributed to whoever the current request's user/IP is.

Only register models where an admin/staff-visible change history is actually valuable —
this isn't meant to log every model (e.g. Notification, LoginHistory, InventoryLog already
have their own purpose-built tracking).
"""

import datetime
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save

from .middleware import get_client_ip, get_current_user
from .models import AuditLog

EXCLUDED_FIELDS = {"created_at", "updated_at", "password", "last_login", "date_joined"}


def _serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def _state(instance):
    return {
        field.attname: _serialize(getattr(instance, field.attname))
        for field in instance._meta.fields
        if field.attname not in EXCLUDED_FIELDS and field.name not in EXCLUDED_FIELDS
    }


def register_audit(model):
    def _pre_save(sender, instance, **kwargs):
        instance._audit_old_state = None
        if instance.pk:
            old = sender.objects.filter(pk=instance.pk).first()
            if old is not None:
                instance._audit_old_state = _state(old)

    def _post_save(sender, instance, created, **kwargs):
        if created:
            AuditLog.objects.create(
                user=get_current_user(),
                action=AuditLog.Action.CREATE,
                model_name=sender.__name__,
                object_id=str(instance.pk),
                object_repr=str(instance)[:255],
                ip_address=get_client_ip(),
                old_value=None,
                new_value=_state(instance),
            )
            return

        old_state = getattr(instance, "_audit_old_state", None)
        if old_state is None:
            return
        new_state = _state(instance)
        old_diff = {k: old_state[k] for k in new_state if new_state[k] != old_state.get(k)}
        new_diff = {k: v for k, v in new_state.items() if v != old_state.get(k)}
        if not new_diff:
            return
        AuditLog.objects.create(
            user=get_current_user(),
            action=AuditLog.Action.UPDATE,
            model_name=sender.__name__,
            object_id=str(instance.pk),
            object_repr=str(instance)[:255],
            ip_address=get_client_ip(),
            old_value=old_diff,
            new_value=new_diff,
        )

    def _post_delete(sender, instance, **kwargs):
        AuditLog.objects.create(
            user=get_current_user(),
            action=AuditLog.Action.DELETE,
            model_name=sender.__name__,
            object_id=str(instance.pk),
            object_repr=str(instance)[:255],
            ip_address=get_client_ip(),
            old_value=_state(instance),
            new_value=None,
        )

    pre_save.connect(_pre_save, sender=model, weak=False)
    post_save.connect(_post_save, sender=model, weak=False)
    post_delete.connect(_post_delete, sender=model, weak=False)
