from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services as accounts_services
from apps.notifications import services as notification_services

from .models import Store

User = get_user_model()


def _verify_email_path(uidb64, token):
    return reverse("accounts:verify-email", args=[uidb64, token])


def register_vendor(
    *, email, password, first_name="", last_name="", phone_number="", store_name, description="", request
):
    user = accounts_services.register_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role=User.Role.VENDOR,
    )
    store = Store.objects.create(owner=user, name=store_name, description=description)
    accounts_services.send_verification_email(user, request, _verify_email_path)
    return user, store


def apply_as_seller(user, *, store_name, description=""):
    """Turns an already-registered (customer) account into a seller by attaching a Store
    to it directly — no second account, no separate email. Mirrors what register_vendor()
    does for a brand-new signup (Store starts PENDING, role flips to VENDOR immediately;
    IsVendor-gated endpoints check role, so this keeps that in sync with store ownership)."""
    if hasattr(user, "store"):
        raise ValueError("You already have a store.")
    store = Store.objects.create(owner=user, name=store_name, description=description)
    user.role = User.Role.VENDOR
    user.save(update_fields=["role"])
    return store


def approve_store(store, admin_user):
    store.status = Store.Status.APPROVED
    store.approved_at = timezone.now()
    store.approved_by = admin_user
    store.rejection_reason = ""
    store.save(update_fields=["status", "approved_at", "approved_by", "rejection_reason"])
    notification_services.notify(
        store.owner,
        title="Your store has been approved",
        message=f"'{store.name}' is now live on FaizanMart.",
        notification_type="vendor_approval",
    )
    return store


def reject_store(store, admin_user, reason):
    store.status = Store.Status.REJECTED
    store.rejection_reason = reason
    store.approved_at = None
    store.approved_by = admin_user
    store.save(update_fields=["status", "rejection_reason", "approved_at", "approved_by"])
    notification_services.notify(
        store.owner,
        title="Your store application was rejected",
        message=reason,
        notification_type="vendor_approval",
    )
    return store


def resubmit_store(store):
    if store.status != Store.Status.REJECTED:
        raise ValueError("Only rejected stores can be resubmitted.")
    store.status = Store.Status.PENDING
    store.rejection_reason = ""
    store.save(update_fields=["status", "rejection_reason"])
    return store
