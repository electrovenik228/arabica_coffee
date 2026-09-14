from datetime import timedelta
from pathlib import Path
import os
from decouple import config
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-l_!4sv+5z%qhzn+1p0%vx98j&efjw^^9yx#ln$@s(4swj=zv_#",
)

INSTALLED_APPS = [
    "daphne",
    "jazzmin",
    "modeltranslation",
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "apps.users.apps.UsersConfig",
    "apps.menu.apps.MenuConfig",
    "apps.cart.apps.CartConfig",
    "apps.order.apps.OrderConfig",
    "apps.news.apps.NewsConfig",
    "apps.promotions.apps.PromotionsConfig",
    "apps.bonus.apps.BonusConfig",
    "apps.printing.apps.PrintingConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "arabica.middleware.LanguageQueryParamMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "arabica.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "arabica.wsgi.application"
ASGI_APPLICATION = "arabica.asgi.application"

AUTH_USER_MODEL = "users.User"

LANGUAGE_CODE = "ru-ky"

LANGUAGES = (
    ("ru", _("Russian")),
    ("ky", _("Kyrgyz")),
)

MODELTRANSLATION_DEFAULT_LANGUAGE = "ru"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "EXCEPTION_HANDLER": "arabica.exception_handlers.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_BLACKLIST_ENABLED": True,
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    "BLACKLIST_TOKEN_MODEL": "rest_framework_simplejwt.token_blacklist.BlacklistedToken",
}

CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://77.95.206.95:8001",
    "http://77.95.206.95",
    "https://arabicacoffee.duckdns.org"
]

PRINTER_WS_TOKEN = config("PRINTER_WS_TOKEN", default="")

TWILIO_ACCOUNT_SID = config(
    "TWILIO_ACCOUNT_SID", default=os.environ.get("TWILIO_ACCOUNT_SID")
)
TWILIO_AUTH_TOKEN = config(
    "TWILIO_AUTH_TOKEN", default=os.environ.get("TWILIO_AUTH_TOKEN")
)
TWILIO_VERIFY_SERVICE_SID = config(
    "TWILIO_VERIFY_SERVICE_SID", default=os.environ.get("TWILIO_VERIFY_SERVICE_SID")
)

# Временная замена Twilio: код подтверждения доставляется через Telegram-бота.
# Чтобы вернуться на Twilio, поменяйте импорт в apps/users/api/views/login.py
# обратно на apps.users.utils.twilio.
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = config("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_WEBHOOK_SECRET = config("TELEGRAM_WEBHOOK_SECRET", default="")
TELEGRAM_BOT_DEEPLINK = (
    f"https://t.me/{TELEGRAM_BOT_USERNAME}" if TELEGRAM_BOT_USERNAME else ""
)

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/3")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379/4"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = config("CELERY_TIMEZONE", default="Asia/Bishkek")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = config("CELERY_TASK_TIME_LIMIT", default=30 * 60, cast=int)
CELERY_TASK_SOFT_TIME_LIMIT = config(
    "CELERY_TASK_SOFT_TIME_LIMIT", default=25 * 60, cast=int
)
