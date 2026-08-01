import base64
from io import BytesIO

import qrcode
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import exceptions, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from . import services
from .models import UserSession
from .serializers import (
    GoogleAuthSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    TwoFactorConfirmSerializer,
    TwoFactorDisableSerializer,
    TwoFactorLoginVerifySerializer,
    UserSerializer,
    UserSessionSerializer,
)

User = get_user_model()


def _verify_email_path(uidb64, token):
    # Emails are human-clickable, so they always link to the browsable
    # session/template pages, even when registration happened via the API.
    return reverse("accounts:verify-email", args=[uidb64, token])


def _reset_password_path(uidb64, token):
    return reverse("accounts:password-reset-confirm", args=[uidb64, token])


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        services.send_verification_email(user, request, _verify_email_path)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, uidb64, token):
        user = services.verify_email_token(uidb64, token)
        if user is None:
            return Response({"detail": "Invalid or expired verification link."}, status=400)
        return Response({"detail": "Email verified successfully."})


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except exceptions.AuthenticationFailed:
            services.record_login(
                request,
                user=None,
                email_attempted=request.data.get("email", ""),
                method="password",
                success=False,
            )
            raise

        data = serializer.validated_data
        if not data.get("two_factor_required"):
            services.record_login(
                request,
                user=serializer.user,
                email_attempted=serializer.user.email,
                method="password",
                success=True,
            )
        return Response(data, status=200)


class TwoFactorLoginVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = TwoFactorLoginVerifySerializer

    def post(self, request):
        serializer = TwoFactorLoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = services.resolve_two_factor_pending_token(serializer.validated_data["pending_token"])
        if user is None:
            return Response({"detail": "Invalid or expired pending token."}, status=400)

        if not services.verify_totp(user, serializer.validated_data["code"]):
            services.record_login(
                request, user=None, email_attempted=user.email, method="password", success=False
            )
            return Response({"detail": "Invalid 2FA code."}, status=400)

        services.record_login(
            request, user=user, email_attempted=user.email, method="password", success=True
        )
        refresh = RefreshToken.for_user(user)
        return Response({"refresh": str(refresh), "access": str(refresh.access_token)})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except Exception:
            return Response({"detail": "Invalid refresh token."}, status=400)

        UserSession.objects.filter(user=request.user, is_active=True).update(is_active=False)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        if user is not None:
            services.send_password_reset_email(user, request, _reset_password_path)
        return Response({"detail": "If that email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.reset_password(**serializer.validated_data)
        if user is None:
            return Response({"detail": "Invalid or expired reset link."}, status=400)
        return Response({"detail": "Password reset successfully."})


class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GoogleAuthSerializer

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = services.authenticate_google_id_token(serializer.validated_data["id_token"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        services.record_login(
            request, user=user, email_attempted=user.email, method="google", success=True
        )
        refresh = RefreshToken.for_user(user)
        return Response({"refresh": str(refresh), "access": str(refresh.access_token)})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class TwoFactorEnableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        two_factor, provisioning_uri = services.generate_totp_secret(request.user)

        qr_image = qrcode.make(provisioning_uri)
        buffer = BytesIO()
        qr_image.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        return Response(
            {
                "secret": two_factor.secret,
                "provisioning_uri": provisioning_uri,
                "qr_code_base64": qr_base64,
            }
        )


class TwoFactorConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TwoFactorConfirmSerializer

    def post(self, request):
        serializer = TwoFactorConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not services.confirm_totp(request.user, serializer.validated_data["code"]):
            return Response({"detail": "Invalid code."}, status=400)
        return Response({"detail": "Two-factor authentication enabled."})


class TwoFactorDisableView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TwoFactorDisableSerializer

    def post(self, request):
        serializer = TwoFactorDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            return Response({"detail": "Incorrect password."}, status=400)
        services.disable_totp(request.user)
        return Response({"detail": "Two-factor authentication disabled."})


class SessionListView(generics.ListAPIView):
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)


class SessionRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        updated = UserSession.objects.filter(pk=pk, user=request.user).update(is_active=False)
        if not updated:
            return Response({"detail": "Session not found."}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)
