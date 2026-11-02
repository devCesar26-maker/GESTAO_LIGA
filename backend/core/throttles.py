"""Scoped throttles for the sensitive public endpoints."""
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"


class RefreshRateThrottle(AnonRateThrottle):
    scope = "refresh"


class WriteRateThrottle(ScopedRateThrottle):
    scope = "user"
