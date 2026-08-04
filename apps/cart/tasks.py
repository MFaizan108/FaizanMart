from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def cleanup_stale_guest_carts_task(retention_days=14):
    """Periodic cleanup: removes guest (anonymous, unauthenticated) carts abandoned long
    enough that the guest_token is very unlikely to ever come back and reuse them."""
    from .models import Cart

    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted, _ = Cart.objects.filter(user__isnull=True, updated_at__lt=cutoff).delete()
    return {"guest_carts_deleted": deleted}
