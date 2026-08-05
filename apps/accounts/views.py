import base64
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from . import services
from .forms import (
    LoginForm,
    PasswordResetRequestForm,
    RegisterForm,
    SetNewPasswordForm,
    TwoFactorCodeForm,
    TwoFactorDisableForm,
)
from .models import UserSession

User = get_user_model()

SESSION_2FA_PENDING_USER_ID = "2fa_pending_user_id"
SESSION_2FA_NEXT_URL = "2fa_next_url"


def _safe_next_url(request, candidate):
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return None


def _verify_email_path(uidb64, token):
    return reverse("accounts:verify-email", args=[uidb64, token])


def _reset_password_path(uidb64, token):
    return reverse("accounts:password-reset-confirm", args=[uidb64, token])


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = services.register_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                phone_number=form.cleaned_data["phone_number"],
            )
            services.send_verification_email(user, request, _verify_email_path)
            messages.success(request, "Account created. Check your email to verify your address.")
            return redirect("accounts:login")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def verify_email_view(request, uidb64, token):
    user = services.verify_email_token(uidb64, token)
    if user is None:
        messages.error(request, "That verification link is invalid or has expired.")
    else:
        messages.success(request, "Your email has been verified. You can now log in.")
    return redirect("accounts:login")


def login_view(request):
    next_url = _safe_next_url(request, request.POST.get("next") or request.GET.get("next"))

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=email, password=password)

            if user is None:
                services.record_login(
                    request, user=None, email_attempted=email, method="password", success=False
                )
                messages.error(request, "Invalid email or password.")
            elif services.has_two_factor_enabled(user):
                request.session[SESSION_2FA_PENDING_USER_ID] = user.pk
                request.session[SESSION_2FA_NEXT_URL] = next_url
                return redirect("accounts:2fa-verify")
            else:
                django_login(request, user)
                services.record_login(
                    request,
                    user=user,
                    email_attempted=email,
                    method="password",
                    success=True,
                    session_key=request.session.session_key,
                )
                return redirect(next_url or settings.LOGIN_REDIRECT_URL)
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form, "next": next_url or ""})


def two_factor_verify_view(request):
    user_id = request.session.get(SESSION_2FA_PENDING_USER_ID)
    if not user_id:
        return redirect("accounts:login")
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        del request.session[SESSION_2FA_PENDING_USER_ID]
        return redirect("accounts:login")

    if request.method == "POST":
        form = TwoFactorCodeForm(request.POST)
        if form.is_valid():
            if services.verify_totp(user, form.cleaned_data["code"]):
                del request.session[SESSION_2FA_PENDING_USER_ID]
                next_url = request.session.pop(SESSION_2FA_NEXT_URL, None)
                django_login(request, user)
                services.record_login(
                    request,
                    user=user,
                    email_attempted=user.email,
                    method="password",
                    success=True,
                    session_key=request.session.session_key,
                )
                return redirect(next_url or settings.LOGIN_REDIRECT_URL)
            services.record_login(
                request, user=None, email_attempted=user.email, method="password", success=False
            )
            messages.error(request, "Invalid authentication code.")
    else:
        form = TwoFactorCodeForm()
    return render(request, "accounts/two_factor_verify.html", {"form": form})


@login_required
def logout_view(request):
    UserSession.objects.filter(
        user=request.user, session_key=request.session.session_key, is_active=True
    ).update(is_active=False)
    django_logout(request)
    return redirect("accounts:login")


def password_reset_request_view(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
            if user is not None:
                services.send_password_reset_email(user, request, _reset_password_path)
            messages.success(request, "If that email exists, a reset link has been sent.")
            return redirect("accounts:login")
    else:
        form = PasswordResetRequestForm()
    return render(request, "accounts/password_reset_request.html", {"form": form})


def password_reset_confirm_view(request, uidb64, token):
    user = services.get_user_from_uidb64(uidb64)
    token_valid = user is not None and default_token_generator.check_token(user, token)

    if not token_valid:
        messages.error(request, "That password reset link is invalid or has expired.")
        return redirect("accounts:password-reset-request")

    if request.method == "POST":
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            services.reset_password(uidb64, token, form.cleaned_data["new_password1"])
            messages.success(request, "Password reset. You can now log in.")
            return redirect("accounts:login")
    else:
        form = SetNewPasswordForm()
    return render(request, "accounts/password_reset_confirm.html", {"form": form})


@login_required
def profile_view(request):
    sessions = request.user.sessions.filter(is_active=True)[:10]
    return render(
        request,
        "accounts/profile.html",
        {
            "user_obj": request.user,
            "two_factor_enabled": services.has_two_factor_enabled(request.user),
            "sessions": sessions,
        },
    )


@login_required
def two_factor_setup_view(request):
    if services.has_two_factor_enabled(request.user):
        messages.info(request, "Two-factor authentication is already enabled.")
        return redirect("accounts:profile")

    if request.method == "POST":
        form = TwoFactorCodeForm(request.POST)
        if form.is_valid() and services.confirm_totp(request.user, form.cleaned_data["code"]):
            messages.success(request, "Two-factor authentication enabled.")
            return redirect("accounts:profile")
        messages.error(request, "Invalid code, please try again.")

    two_factor, provisioning_uri = services.generate_totp_secret(request.user)
    qr_buffer = BytesIO()
    qrcode.make(provisioning_uri).save(qr_buffer, format="PNG")
    qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()

    return render(
        request,
        "accounts/two_factor_setup.html",
        {
            "form": TwoFactorCodeForm(),
            "secret": two_factor.secret,
            "provisioning_uri": provisioning_uri,
            "qr_base64": qr_base64,
        },
    )


@login_required
def two_factor_disable_view(request):
    if request.method == "POST":
        form = TwoFactorDisableForm(request.POST)
        if form.is_valid() and request.user.check_password(form.cleaned_data["password"]):
            services.disable_totp(request.user)
            messages.success(request, "Two-factor authentication disabled.")
            return redirect("accounts:profile")
        messages.error(request, "Incorrect password.")
    else:
        form = TwoFactorDisableForm()
    return render(request, "accounts/two_factor_disable.html", {"form": form})


@login_required
def revoke_session_view(request, pk):
    UserSession.objects.filter(pk=pk, user=request.user).update(is_active=False)
    return redirect("accounts:profile")


def google_login_view(request):
    if request.method == "POST":
        id_token = request.POST.get("id_token", "")
        try:
            user = services.authenticate_google_id_token(id_token)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("accounts:login")

        django_login(request, user)
        services.record_login(
            request,
            user=user,
            email_attempted=user.email,
            method="google",
            success=True,
            session_key=request.session.session_key,
        )
        return redirect(settings.LOGIN_REDIRECT_URL)

    return render(
        request,
        "accounts/google_login.html",
        {"google_client_id": settings.GOOGLE_OAUTH_CLIENT_ID},
    )
