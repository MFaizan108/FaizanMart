from .models import Notification


def notify(user, title, message="", notification_type=Notification.NotificationType.GENERAL, link=""):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
    )


def mark_read(notification):
    from django.utils import timezone

    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at"])
    return notification


def mark_all_read(user):
    from django.utils import timezone

    Notification.objects.filter(user=user, is_read=False).update(is_read=True, read_at=timezone.now())
