"""Reusable DRF permissions.

Authentication answers *who* the user is; these permissions answer *what* the
user may do. Object-level checks are always enforced here and repeated in the
service layer, never only in the frontend.
"""
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotAuthenticated

from .exceptions import AppError


def require_authenticated(user):
    if user is None or not user.is_authenticated:
        raise NotAuthenticated()


class IsAdmin(BasePermission):
    """Only staff (league administrators) may proceed."""

    def has_permission(self, request, view):
        require_authenticated(request.user)
        if not request.user.is_staff:
            raise AppError("ADMIN_ONLY", 403)
        return True


class IsAuthenticatedWithMessage(BasePermission):
    def has_permission(self, request, view):
        require_authenticated(request.user)
        return True


class IsMatchParticipant(BasePermission):
    """Owner-of-the-match rule: only the two players involved (or an admin)."""

    def has_permission(self, request, view):
        require_authenticated(request.user)
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if not obj.involves(request.user):
            raise AppError("NOT_MATCH_PARTICIPANT", 403)
        return True


class IsLeagueOpenForRegistration(BasePermission):
    """Registration is only open before fixtures are generated."""

    def has_permission(self, request, view):
        from league.models import League

        league = League.get_active()
        if league is None:
            raise AppError("NO_ACTIVE_LEAGUE", 400)
        if not league.registration_open:
            raise AppError("REGISTRATION_CLOSED", 403)
        request.active_league = league
        return True


__all__ = [
    "IsAdmin",
    "IsAuthenticatedWithMessage",
    "IsMatchParticipant",
    "IsLeagueOpenForRegistration",
]
