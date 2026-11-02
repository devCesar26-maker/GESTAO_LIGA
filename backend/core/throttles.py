"""Scoped throttles for the sensitive public endpoints."""
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"


class RefreshRateThrottle(AnonRateThrottle):
    scope = "refresh"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"


class PasswordResetConfirmRateThrottle(AnonRateThrottle):
    scope = "password_reset_confirm"


class WriteRateThrottle(ScopedRateThrottle):
    scope = "user"
