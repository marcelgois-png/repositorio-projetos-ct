import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


DEFAULT_SECRET_KEY = "dev-insecure-secret-key"
LOCAL_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}
LOCAL_CSRF_ORIGINS = {"http://localhost", "http://127.0.0.1"}
DEFAULT_MYSQL_VALUES = {
    "MYSQL_DATABASE": "repo_arquitetonico",
    "MYSQL_USER": "repo_user",
    "MYSQL_PASSWORD": "repo_password",
    "MYSQL_ROOT_PASSWORD": "root_password",
}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_SECRET_KEY)
DEBUG = env_bool("DJANGO_DEBUG", True)
USE_SQLITE = env_bool("DJANGO_USE_SQLITE", False)
PRODUCTION = not DEBUG
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "repository.apps.RepositoryConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "repository.context_processors.navigation_permissions",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("MYSQL_DATABASE", "repo_arquitetonico"),
            "USER": os.getenv("MYSQL_USER", "repo_user"),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", "repo_password"),
            "HOST": os.getenv("MYSQL_HOST", "mysql"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles" if USE_SQLITE else Path(os.getenv("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media" if USE_SQLITE else Path(os.getenv("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media" if USE_SQLITE else Path(os.getenv("DJANGO_PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))
MAX_UPLOAD_MB = int(os.getenv("DJANGO_MAX_UPLOAD_MB", "200"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if PRODUCTION:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
    }

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "repository:project_list"
LOGOUT_REDIRECT_URL = "repository:project_list"
PASSWORD_RESET_TIMEOUT = int(os.getenv("DJANGO_PASSWORD_RESET_TIMEOUT_SECONDS", "1800"))

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "Repositório CT/UFPB <nao-responda@ct.ufpb.br>")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", True)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_COOKIE_AGE", "3600"))
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", True)
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")
X_FRAME_OPTIONS = "DENY"

if PRODUCTION:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
else:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)


def validate_production_settings():
    if SECRET_KEY == DEFAULT_SECRET_KEY:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY com um valor seguro para producao.")

    if not ALLOWED_HOSTS or set(ALLOWED_HOSTS).issubset(LOCAL_ALLOWED_HOSTS):
        raise ImproperlyConfigured("Defina DJANGO_ALLOWED_HOSTS com os dominios reais da aplicacao.")

    if not CSRF_TRUSTED_ORIGINS or set(CSRF_TRUSTED_ORIGINS).issubset(LOCAL_CSRF_ORIGINS):
        raise ImproperlyConfigured("Defina DJANGO_CSRF_TRUSTED_ORIGINS com as URLs HTTPS reais da aplicacao.")

    if USE_SQLITE:
        raise ImproperlyConfigured("DJANGO_USE_SQLITE deve permanecer desligado em producao.")

    for env_name, default_value in DEFAULT_MYSQL_VALUES.items():
        current_value = os.getenv(env_name, "").strip()
        if not current_value or current_value == default_value:
            raise ImproperlyConfigured(f"Defina {env_name} com um valor seguro para producao.")


if PRODUCTION:
    validate_production_settings()
