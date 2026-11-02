import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import AppError
from core.mailer import send_transactional_email
from core.messages import MESSAGES
from core.permissions import IsAuthenticatedWithMessage, IsLeagueOpenForRegistration
from core.throttles import (
    LoginRateThrottle,
    PasswordResetConfirmRateThrottle,
    PasswordResetRateThrottle,
    RefreshRateThrottle,
    RegisterRateThrottle,
)

from .cookies import clear_auth_cookies, set_auth_cookies
from .models import User
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


def tokens_for_user(user) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def _frontend_base_url(request) -> str:
    """Public SPA origin used in the reset link.

    ``FRONTEND_URL`` is the explicit setting. The fallbacks keep local and
    single-service deployments working without an extra variable; the host
    header is only used as a last resort and is constrained by ALLOWED_HOSTS.
    """
    if settings.FRONTEND_URL:
        return settings.FRONTEND_URL
    if settings.CSRF_TRUSTED_ORIGINS:
        return settings.CSRF_TRUSTED_ORIGINS[0].rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _send_password_reset_email(user, reset_url: str):
    expires_minutes = max(1, settings.PASSWORD_RESET_TIMEOUT // 60)
    context = {
        "user": user,
        "reset_url": reset_url,
        "expires_minutes": expires_minutes,
    }
    subject = render_to_string(
        "accounts/emails/password_reset_subject.txt", context
    ).strip()
    text_body = render_to_string("accounts/emails/password_reset.txt", context)
    html_body = render_to_string("accounts/emails/password_reset.html", context)

    send_transactional_email(
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        to_email=user.email,
        to_name=user.name,
    )


def _blacklist_user_refresh_tokens(user):
    """Invalidate every refresh token already issued to the user."""
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Hands the browser a readable CSRF cookie before the first write."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    """Open registration, only while the active league has no fixtures."""

    permission_classes = [AllowAny, IsLeagueOpenForRegistration]
    throttle_classes = [RegisterRateThrottle]
    authentication_classes = []

    def post(self, request):
        from league.models import Participant

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        league = getattr(request, "active_league", None)
        if league is not None:
            try:
                with transaction.atomic():
                    Participant.objects.get_or_create(league=league, user=user)
            except IntegrityError:
                # Extremely unlikely race; the account exists, which is enough.
                pass

        access, refresh = tokens_for_user(user)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "code": "REGISTERED",
                "message": MESSAGES["REGISTERED"],
            },
            status=status.HTTP_201_CREATED,
        )
        return set_auth_cookies(
            response, access_token=access, refresh_token=refresh
        )


class LoginView(APIView):
    """Authenticate by email; the tokens go straight into HttpOnly cookies."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    authentication_classes = []

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = request.data.get("password", "")
        if not email or not password:
            # Same message for unknown email and wrong password: no user
            # enumeration through the API.
            raise AppError("INVALID_CREDENTIALS", 401)

        user = authenticate(request, username=email, password=password)
        if user is None or not user.is_active:
            raise AppError("INVALID_CREDENTIALS", 401)

        access, refresh = tokens_for_user(user)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "code": "LOGGED_IN",
                "message": MESSAGES["LOGGED_IN"],
            }
        )
        return set_auth_cookies(
            response, access_token=access, refresh_token=refresh
        )


class RefreshView(APIView):
    """Rotates the refresh token from its cookie and blacklists the old one."""

    permission_classes = [AllowAny]
    throttle_classes = [RefreshRateThrottle]
    authentication_classes = []

    def post(self, request):
        raw_token = request.COOKIES.get("refresh_token")
        if not raw_token:
            raise AppError("SESSION_EXPIRED", 401)

        try:
            # TokenRefreshSerializer applies rotation/blacklisting from settings.
            serializer = TokenRefreshSerializer(data={"refresh": raw_token})
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            if "expired" in str(exc).lower():
                raise AppError("SESSION_EXPIRED", 401)
            raise AppError("INVALID_TOKEN", 401)

        data = serializer.validated_data
        response = Response({"code": "SESSION_REFRESHED", "message": "Sessão renovada."})
        return set_auth_cookies(
            response,
            access_token=data["access"],
            refresh_token=data.get("refresh"),
        )


class LogoutView(APIView):
    """Clears the cookies and blacklists the refresh token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_token = request.COOKIES.get("refresh_token")
        if raw_token:
            try:
                RefreshToken(raw_token).blacklist()
            except TokenError:
                # Logging out locally is still fine with an invalid token.
                logger.info("Logout with an unusable refresh token")
        response = Response(
            {"code": "LOGGED_OUT", "message": MESSAGES["LOGGED_OUT"]}
        )
        return clear_auth_cookies(response)


class PasswordResetRequestView(APIView):
    """Start the password reset flow without revealing whether the email exists."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = (
                f"{_frontend_base_url(request)}/redefinir-senha"
                f"?uid={uid}&token={token}"
            )
            try:
                _send_password_reset_email(user, reset_url)
            except Exception:
                # Never turn a delivery failure into account enumeration. The
                # error is logged for the operator and the response stays generic.
                logger.exception("Failed to send password reset email for user %s", user.pk)

        return Response(
            {
                "code": "PASSWORD_RESET_SENT",
                "message": MESSAGES["PASSWORD_RESET_SENT"],
            }
        )


class PasswordResetConfirmView(APIView):
    """Apply a new password using a short-lived, single-use Django token."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetConfirmRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user_id = urlsafe_base64_decode(data["uid"]).decode()
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, UnicodeError, User.DoesNotExist):
            raise AppError("PASSWORD_RESET_INVALID", 400)

        if not default_token_generator.check_token(user, data["token"]):
            raise AppError("PASSWORD_RESET_INVALID", 400)

        with transaction.atomic():
            user.set_password(data["password"])
            user.save(update_fields=["password"])
            _blacklist_user_refresh_tokens(user)

        response = Response(
            {
                "code": "PASSWORD_RESET_SUCCESS",
                "message": MESSAGES["PASSWORD_RESET_SUCCESS"],
            }
        )
        # The caller's old session is gone; other sessions lose their refresh
        # token above. Access tokens expire naturally in 15 minutes.
        return clear_auth_cookies(response)


class MeView(APIView):
    permission_classes = [IsAuthenticatedWithMessage]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "code": "PROFILE_UPDATED",
                "message": MESSAGES["PROFILE_UPDATED"],
            }
        )
