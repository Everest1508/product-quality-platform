import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps/ to Python path so we can import apps.core, apps.accounts, etc.
sys.path.insert(0, str(BASE_DIR / "apps"))

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-!n(6jx1*y%1%3p+lz^jcw3)%m2$v-st6rrry@ipec8pc)i)@p7",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "django_htmx",
    "corsheaders",
    "channels",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "apps.core",
    "apps.accounts",
    "apps.products",
    "apps.ingestion",
    "apps.errors",
    "apps.tickets",
    "apps.automation",
    "apps.feedback",
    "apps.dashboards",
    "apps.dsr",
    "apps.attendance",
    "apps.leave",
    "apps.payroll",
    "apps.serop",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.core.middleware.CurrentCompanyMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.product_context",
                "apps.core.context_processors.workspace_context",
                "apps.core.context_processors.version_context",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# Asia/Kolkata, not UTC. `WorkShift.start_time` is 10:00 and every lateness
# band, every `date:"g:i A"` in a template and every cycle boundary is read in
# this zone, so a UTC default silently shifted the whole company four and a half
# hours: a 10:00 IST arrival punched at 10:00 was stored as 04:30 local and read
# as five and a half hours early, and nobody was ever late. Storage is still
# UTC (`USE_TZ`); only display and all day-boundary arithmetic change.
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Shown in the sidebar footer and served by /api/v1/version/. There are no git
# tags in this repo, so `git describe` yields only a commit hash, which is not
# something to show a user. Bump this when cutting a release, and start a new
# "## [Unreleased]" block in CHANGELOG.md above the one you just closed.
APP_VERSION = os.environ.get("DJANGO_APP_VERSION", "1.0.1")
CHANGELOG_PATH = BASE_DIR / "CHANGELOG.md"

# Auth
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "dashboards:index"  # a URL *name*: the path is in core/urls.py
LOGOUT_REDIRECT_URL = "/login/"

# The active workspace is stored in the session under this key.
ACTIVE_COMPANY_SESSION_KEY = "active_company_id"

# django-allauth
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "allauth.account.adapter.DefaultAccountAdapter"
ACCOUNT_SIGNUP_REDIRECT_URL = "/login/"

# Login / logout routes handled by our own views, not allauth's defaults
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_LOGIN_BY_PASSWORD_ENABLED = True

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
    },
    "UNAUTHENTICATED_USER": None,
}

# CSRF
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "https://crm.beforth.in,http://localhost:8011,http://127.0.0.1:8011",
).split(",")

# CORS — scoped to the Serop desktop app's bearer-token-authenticated API only.
# These paths carry no cookies, so allowing any origin on them is safe; the
# rest of the CRM (session-cookie web UI) is untouched by corsheaders.
CORS_URLS_REGEX = r"^/(oauth|api/serop)/.*$"
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = False

# Serop desktop app integration
ASGI_APPLICATION = "core.asgi.application"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}

# Fernet key used to encrypt shared-server passwords (apps.serop.models.SeropSharedServer).
# Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SHARED_SERVER_ENCRYPTION_KEY = os.environ.get(
    "SHARED_SERVER_ENCRYPTION_KEY",
    "Wj9_TxFEXHDzzcaYIxY3dfCjyK2_9pZDesWRfpFIcWA=",
)
