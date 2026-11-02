"""Serve the built React app from the same origin as the API.

Everything that is not under ``/api/``, ``/django-admin/`` or ``/static/`` is a
client-side route, so the request must return ``index.html`` and let React
Router take over. Serving the SPA from Django is what allows the session to live
in first-party cookies (no cross-origin CORS at all).
"""
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse

MISSING_BUILD_PAGE = """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <title>Liga eFootball — build ausente</title>
  </head>
  <body>
    <h1>Build do frontend não encontrado</h1>
    <p>Rode <code>npm install &amp;&amp; npm run build</code> em <code>frontend/</code>.</p>
    <p>Durante o desenvolvimento use o servidor do Vite: <code>npm run dev</code>.</p>
  </body>
</html>
"""


def _index_file() -> Path:
    return Path(settings.FRONTEND_BUILD_DIR) / "index.html"


def spa_index(request, path: str = ""):
    """Return the SPA shell for any non-API route."""
    index = _index_file()
    if index.is_file():
        response = HttpResponse(
            index.read_text(encoding="utf-8"),
            content_type="text/html; charset=utf-8",
        )
    else:
        response = HttpResponse(
            MISSING_BUILD_PAGE, content_type="text/html; charset=utf-8"
        )
    # The HTML shell must never be cached: it references hashed asset names.
    response["Cache-Control"] = "no-store"
    return response
