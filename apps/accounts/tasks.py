from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


@shared_task
def send_email_task(subject, message, recipient_list):
    """Runs the actual SMTP send off the request thread — registration/password-reset
    endpoints call this via .delay() instead of blocking on send_mail() directly."""
    send_mail(subject=subject, message=message, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=recipient_list)


@shared_task
def cleanup_expired_sessions_task(retention_days=30):
    """Periodic cleanup: deactivates sessions idle past the retention window and trims old
    login history rows, so these tables don't grow unbounded."""
    from .models import LoginHistory, UserSession

    cutoff = timezone.now() - timedelta(days=retention_days)
    deactivated = UserSession.objects.filter(is_active=True, last_seen_at__lt=cutoff).update(is_active=False)
    deleted, _ = LoginHistory.objects.filter(created_at__lt=cutoff).delete()
    return {"sessions_deactivated": deactivated, "login_history_deleted": deleted}
