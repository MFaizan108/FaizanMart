import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .models import LoginHistory, TwoFactorAuth, UserSession
from .tokens import email_verification_token

User = get_user_model()

TWO_FACTOR_PENDING_SALT = "accounts.two-factor-pending"
TWO_FACTOR_PENDING_MAX_AGE = 300  # seconds


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def register_user(*, email, password, first_name="", last_name="", phone_number="", role=User.Role.CUSTOMER):
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role=role,
    )
    return user


def _build_absolute_url(request, path):
    return request.build_absolute_uri(path)


def send_verification_email(user, request, verify_path_builder):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    url = _build_absolute_url(request, verify_path_builder(uidb64, token))
    send_mail(
        subject="Verify your FaizanMart email",
        message=(
            f"Hi {user.get_short_name()},\n\n"
            f"Please verify your email by visiting the link below:\n{url}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def verify_email_token(uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None

    if not email_verification_token.check_token(user, token):
        return None

    user.is_email_verified = True
    user.save(update_fields=["is_email_verified"])
    return user


def send_password_reset_email(user, request, reset_path_builder):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = _build_absolute_url(request, reset_path_builder(uidb64, token))
    send_mail(
        subject="Reset your FaizanMart password",
        message=(
            f"Hi {user.get_short_name()},\n\n"
            f"Reset your password using the link below:\n{url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def get_user_from_uidb64(uidb64):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None


def reset_password(uidb64, token, new_password):
    user = get_user_from_uidb64(uidb64)
    if user is None or not default_token_generator.check_token(user, token):
        return None
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return user


def authenticate_google_id_token(token_str):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise ValueError("Google OAuth is not configured (GOOGLE_OAUTH_CLIENT_ID is blank).")

    payload = google_id_token.verify_oauth2_token(
        token_str, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
    )
    email = payload["email"]

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": payload.get("given_name", ""),
            "last_name": payload.get("family_name", ""),
            "role": User.Role.CUSTOMER,
            "is_email_verified": True,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def record_login(request, *, user=None, email_attempted, method, success, session_key=""):
    LoginHistory.objects.create(
        user=user,
        email_attempted=email_attempted,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        method=method,
        was_successful=success,
    )
    if success and user is not None:
        return UserSession.objects.create(
            user=user,
            session_key=session_key or "",
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        )
    return None


def issue_two_factor_pending_token(user):
    return signing.dumps({"user_id": user.pk}, salt=TWO_FACTOR_PENDING_SALT)


def resolve_two_factor_pending_token(token):
    try:
        data = signing.loads(token, salt=TWO_FACTOR_PENDING_SALT, max_age=TWO_FACTOR_PENDING_MAX_AGE)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=data.get("user_id")).first()


def generate_totp_secret(user):
    secret = pyotp.random_base32()
    two_factor, _ = TwoFactorAuth.objects.update_or_create(
        user=user,
        defaults={"secret": secret, "is_enabled": False, "confirmed_at": None},
    )
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name=settings.EMAIL_HOST_NAME
    )
    return two_factor, provisioning_uri


def confirm_totp(user, code):
    try:
        two_factor = user.two_factor
    except TwoFactorAuth.DoesNotExist:
        return False
    if not pyotp.TOTP(two_factor.secret).verify(code):
        return False
    two_factor.is_enabled = True
    two_factor.confirmed_at = timezone.now()
    two_factor.save(update_fields=["is_enabled", "confirmed_at"])
    return True


def verify_totp(user, code):
    try:
        two_factor = user.two_factor
    except TwoFactorAuth.DoesNotExist:
        return False
    if not two_factor.is_enabled:
        return False
    return pyotp.TOTP(two_factor.secret).verify(code)


def disable_totp(user):
    TwoFactorAuth.objects.filter(user=user).delete()


def has_two_factor_enabled(user):
    return TwoFactorAuth.objects.filter(user=user, is_enabled=True).exists()
