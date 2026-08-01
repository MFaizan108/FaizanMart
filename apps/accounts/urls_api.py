from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from . import api_views

app_name = "accounts_api"

urlpatterns = [
    path("register/", api_views.RegisterView.as_view(), name="register"),
    path(
        "verify-email/<str:uidb64>/<str:token>/",
        api_views.VerifyEmailView.as_view(),
        name="verify-email",
    ),
    path("login/", api_views.LoginView.as_view(), name="login"),
    path("login/2fa-verify/", api_views.TwoFactorLoginVerifyView.as_view(), name="login-2fa-verify"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", api_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", api_views.PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm/",
        api_views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("google/", api_views.GoogleLoginView.as_view(), name="google-login"),
    path("me/", api_views.MeView.as_view(), name="me"),
    path("2fa/enable/", api_views.TwoFactorEnableView.as_view(), name="2fa-enable"),
    path("2fa/confirm/", api_views.TwoFactorConfirmView.as_view(), name="2fa-confirm"),
    path("2fa/disable/", api_views.TwoFactorDisableView.as_view(), name="2fa-disable"),
    path("sessions/", api_views.SessionListView.as_view(), name="sessions"),
    path("sessions/<int:pk>/", api_views.SessionRevokeView.as_view(), name="session-revoke"),
]
