from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("verify-email/<str:uidb64>/<str:token>/", views.verify_email_view, name="verify-email"),
    path("login/", views.login_view, name="login"),
    path("login/2fa-verify/", views.two_factor_verify_view, name="2fa-verify"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.password_reset_request_view, name="password-reset-request"),
    path(
        "password-reset/confirm/<str:uidb64>/<str:token>/",
        views.password_reset_confirm_view,
        name="password-reset-confirm",
    ),
    path("google/", views.google_login_view, name="google-login"),
    path("profile/", views.profile_view, name="profile"),
    path("2fa/setup/", views.two_factor_setup_view, name="2fa-setup"),
    path("2fa/disable/", views.two_factor_disable_view, name="2fa-disable"),
    path("sessions/<int:pk>/revoke/", views.revoke_session_view, name="session-revoke"),
]
