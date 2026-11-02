import logging

from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import AppError
from core.messages import MESSAGES
from core.permissions import IsAuthenticatedWithMessage, IsLeagueOpenForRegistration
from core.throttles import LoginRateThrottle, RefreshRateThrottle, RegisterRateThrottle

from .cookies import clear_auth_cookies, set_auth_cookies
from .serializers import ProfileSerializer, RegisterSerializer, UserSerializer

logger = logging.getLogger(__name__)


def tokens_for_user(user) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


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
