from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path

from core.spa import spa_index


def health(request):
    """Lightweight health check used by Render/Railway."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # The Django admin lives on a non-obvious path; /admin is the React panel.
    path("django-admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("league.urls")),
    # Everything else is a client-side route of the React build.
    re_path(r"^(?!api/|django-admin/|static/)(?P<path>.*)$", spa_index, name="spa"),
]
