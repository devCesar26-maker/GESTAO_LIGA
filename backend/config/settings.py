"""Django settings for the eFootball league API.

Everything is configurable through environment variables (see .env.example):
SECRET_KEY, DEBUG, DATABASE_URL, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS.

Security model (see README): the API is served from the same origin as the
React build and the JWT session lives in HttpOnly cookies, so JavaScript can
never read the tokens. Every unsafe request must carry the CSRF token.
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # <repo>/backend
ROOT_DIR = BASE_DIR.parent
FRONTEND_BUILD_DIR = ROOT_DIR / "frontend" / "dist"

# Loading ".env" from the repo root keeps a single source of truth for backend
# and frontend variables.
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default) or ""


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def is_running_tests() -> bool:
    """True under pytest, which forces DEBUG=False and uses a throwaway DB."""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


INSECURE_DEV_KEY = "dev-only-insecure-secret-key-change-me"
INSECURE_KEYS = {
    INSECURE_DEV_KEY,
    "change-me-in-production",
    "changeme",
    "django-insecure",
    "secret",
}


def resolve_secret_key() -> str:
    """Never fall back to a known key outside development.

    Production deployments must provide SECRET_KEY; refusing to boot avoids
    quietly signing sessions with a public value. Known placeholders and very
    short keys are rejected when DEBUG=False.
    """
    key = env("SECRET_KEY")
    if key and key not in INSECURE_KEYS:
        if not DEBUG and len(key) < 32:
            raise ImproperlyConfigured(
                "SECRET_KEY must be at least 32 characters when DEBUG=False. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(50))"'
            )
        return key
    if DEBUG:
        return INSECURE_DEV_KEY
    if is_running_tests():
        return "test-only-key-never-used-outside-pytest"
    raise ImproperlyConfigured(
        "SECRET_KEY is required when DEBUG=False. "
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(50))"'
    )


DEBUG = env_bool("DEBUG", True)
SECRET_KEY = resolve_secret_key()
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
if DEBUG and "*" not in ALLOWED_HOSTS:
    # Convenient for local network access from a phone while developing.
    ALLOWED_HOSTS.append("*")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "core",
    "accounts",
    "league",
]

MIDDLEWARE = [
    # Adds the security headers to every response, including error responses.
    "core.middleware.SecurityHeadersMiddleware",
    # Turns unexpected API exceptions into the standard friendly JSON body
    # instead of an HTML stack trace.
    "core.middleware.ApiErrorMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Forces Django's CSRF check on every unsafe /api/ request (DRF views are
    # csrf_exempt by default and authentication is cookie based). It runs before
    # the standard middleware, which then sees the request as already checked.
    "core.middleware.ApiCsrfMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # The built SPA lives here so Django can serve index.html at "/".
        "DIRS": [BASE_DIR / "templates", FRONTEND_BUILD_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    # Neon (and most managed PostgreSQL providers) requires TLS and may close
    # idle connections when the compute scales to zero. CONN_MAX_AGE is kept at
    # or below 300s and CONN_HEALTH_CHECKS avoids reusing a dead connection.
    # Server-side cursors are not supported by PgBouncer transaction pooling.
    database_config = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(env("DATABASE_CONN_MAX_AGE", "300")),
        conn_health_checks=True,
        disable_server_side_cursors=True,
    )
    database_host = str(database_config.get("HOST") or "")
    is_local_database = (
        database_host in {"", "localhost", "127.0.0.1", "::1", "db"}
        or database_host.startswith("/")
    )
    # If the URL does not say otherwise, require TLS for a remote database.
    if (
        env_bool("DATABASE_SSL_REQUIRE", not is_local_database)
        and "sslmode" not in DATABASE_URL
    ):
        database_config.setdefault("OPTIONS", {})["sslmode"] = "require"
    database_config.setdefault("OPTIONS", {})["connect_timeout"] = int(
        env("DATABASE_CONNECT_TIMEOUT", "10")
    )
    DATABASES = {"default": database_config}
else:
    # Fallback used only for quick local runs and for CI without a database
    # service. PostgreSQL is the supported production database.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.CookieJWTAuthentication",
    ],
    # Reads are public; write endpoints declare their own permissions.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "anon": "600/hour",
        "user": "6000/hour",
        "login": "10/min",
        "register": "30/hour",
        "refresh": "60/hour",
        "password_reset": "5/hour",
        "password_reset_confirm": "20/hour",
    },
    # Set NUM_PROXIES=1 on Render/Railway so throttling uses the real client IP
    # from X-Forwarded-For instead of the platform proxy address. Keep 0 when
    # the app is exposed directly (otherwise clients could spoof the header).
    "NUM_PROXIES": int(env("NUM_PROXIES", "0")),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_RENDERER_CLASSES": (
        [rest for rest in ["rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"]]
        if DEBUG
        else ["rest_framework.renderers.JSONRenderer"]
    ),
}

# ---------------------------------------------------------------------------
# Session cookies (JWT in HttpOnly cookies) and CSRF
# ---------------------------------------------------------------------------
AUTH_ACCESS_COOKIE = "access_token"
AUTH_REFRESH_COOKIE = "refresh_token"
AUTH_ACCESS_COOKIE_PATH = "/api/"
# Wide enough for /api/auth/refresh/ and /api/auth/logout/ (logout needs the
# token to blacklist it), never sent to the rest of the API or to assets.
AUTH_REFRESH_COOKIE_PATH = "/api/auth/"
AUTH_COOKIE_SAMESITE = "Lax"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": SECRET_KEY,
}

# Needed by Django's own CSRF machinery for the Django admin over HTTPS.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
CSRF_FAILURE_VIEW = "core.csrf.csrf_failure"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # axios must read it to send X-CSRFToken
CSRF_COOKIE_SECURE = not DEBUG

# ---------------------------------------------------------------------------
# Email and password reset
# ---------------------------------------------------------------------------
# Production uses SMTP. Development and the test suite use the console backend
# so no real message leaves the machine by accident. Any SMTP provider works
# (Resend, Brevo, Mailgun, Gmail, etc.) because only environment variables are
# involved; no SDK is required.
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", not EMAIL_USE_SSL)
_default_email_backend = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG or is_running_tests()
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_BACKEND = env("EMAIL_BACKEND", _default_email_backend)
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "465" if EMAIL_USE_SSL else "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))
# Brevo transactional email API. When the key is set it takes precedence over
# SMTP, so production only needs BREVO_API_KEY + DEFAULT_FROM_EMAIL.
BREVO_API_KEY = env("BREVO_API_KEY").strip()
BREVO_API_URL = env("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email").strip()
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL", "Biblioteca <dev.cesar26@gmail.com>"
).strip()
# Public origin of the React app, used in the reset link. In development the
# Vite server is on :5173; in production set it to the public HTTPS URL.
FRONTEND_URL = env(
    "FRONTEND_URL",
    "http://localhost:5173" if DEBUG or is_running_tests() else "",
).rstrip("/")
# Django's default is three days; one hour is plenty for a league invite.
PASSWORD_RESET_TIMEOUT = int(env("PASSWORD_RESET_TIMEOUT", "3600"))

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
    },
}
# WhiteNoise serves the Vite build (hashed /assets/*) straight from the app.
WHITENOISE_ROOT = FRONTEND_BUILD_DIR
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# League domain settings
# ---------------------------------------------------------------------------
MAX_GOALS_PER_MATCH = int(env("MAX_GOALS_PER_MATCH", "30"))
CONTEST_WINDOW_HOURS = int(env("CONTEST_WINDOW_HOURS", "48"))
WALKOVER_GOALS = int(env("WALKOVER_GOALS", "3"))
LEAGUE_NAME_MIN_LENGTH = 3
LEAGUE_NAME_MAX_LENGTH = 60

# ---------------------------------------------------------------------------
# Security / deployment
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG) and not is_running_tests()
# Platform health checks arrive over plain HTTP from the internal network.
# Exempting this public liveness endpoint avoids a redirect loop while keeping
# every other route HTTPS-only.
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000")) if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
