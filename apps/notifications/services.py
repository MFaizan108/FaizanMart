from .models import Notification


def notify(user, title, message="", notification_type=Notification.NotificationType.GENERAL, link=""):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
    )


def notify_admins(title, message="", link=""):
    """In-app notification + a real email to every super admin — used for things that need
    a human to act (new seller application, product submitted for review). Queries for
    admins at call time rather than a fixed address, so it stays correct if who's an admin
    ever changes."""
    from apps.accounts.models import User
    from apps.accounts.tasks import send_email_task

    admins = list(User.objects.filter(is_superuser=True, is_active=True))
    for admin in admins:
        notify(admin, title=title, message=message, notification_type=Notification.NotificationType.ADMIN_ALERT, link=link)

    admin_emails = [admin.email for admin in admins]
    if admin_emails:
        body = f"{message}\n\nReview it here: {link}" if link else message
        send_email_task.delay(subject=title, message=body, recipient_list=admin_emails)


def mark_read(notification):
    from django.utils import timezone

    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at"])
    return notification


def mark_all_read(user):
    from django.utils import timezone

    Notification.objects.filter(user=user, is_read=False).update(is_read=True, read_at=timezone.now())
