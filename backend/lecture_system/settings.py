import os
from pathlib import Path


def _getenv_bool(name: str, default: bool) -> bool:
    """Read a boolean env var.

    Accepted truthy values: 1, true, yes, on (case-insensitive)
    Accepted falsy values: 0, false, no, off (case-insensitive)
    """

    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _getenv_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = [v.strip() for v in raw.split(",")]
    return [v for v in values if v]


BASE_DIR = Path(__file__).resolve().parent.parent

ROOT_URLCONF = "lecture_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # ここに独自テンプレートパスを追加可
        "APP_DIRS": True,  # templates/ を探索
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

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe")

# NOTE:
# - Compose/k8s両対応のため、重要な値は環境変数で上書き可能にする（既定は現状互換）。
# - 本番/Stageでは必ず DJANGO_DEBUG=false とし、SECRET_KEY を Secret で管理してください。
DEBUG = _getenv_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _getenv_csv("DJANGO_ALLOWED_HOSTS", ["*"])

# CSRF/CORS 設定（開発用）
# ブラウザは frontend の http://localhost:3000 から /api へリクエストし、
# frontend(Nginx) が backend:8000 にプロキシします。このとき Django は
# Origin: http://localhost:3000 を受け取るため、信頼オリジンに追加が必要です。
CSRF_TRUSTED_ORIGINS = _getenv_csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    [
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
    ],
)

# 開発の利便性のため（本番では適切に設定）
CSRF_COOKIE_HTTPONLY = _getenv_bool("DJANGO_CSRF_COOKIE_HTTPONLY", False)
CSRF_COOKIE_SECURE = _getenv_bool("DJANGO_CSRF_COOKIE_SECURE", False)
SESSION_COOKIE_SECURE = _getenv_bool("DJANGO_SESSION_COOKIE_SECURE", False)

# Ingress等でHTTPS終端する場合の推奨設定（デフォルトは無効=現状互換）
# - Nginx Ingress などは X-Forwarded-Proto を付与するため、必要に応じて有効化する
USE_X_FORWARDED_HOST = _getenv_bool("DJANGO_USE_X_FORWARDED_HOST", False)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if _getenv_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False)
    else None
)
SECURE_SSL_REDIRECT = _getenv_bool("DJANGO_SECURE_SSL_REDIRECT", False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise: Gunicorn配下で静的ファイルを提供（管理画面のCSS/JS含む）
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOW_ALL_ORIGINS = _getenv_bool("DJANGO_CORS_ALLOW_ALL_ORIGINS", True)  # 開発用

# CORS_ALLOW_ALL_ORIGINS=false の場合は、許可するOriginを明示指定する
# 例: DJANGO_CORS_ALLOWED_ORIGINS=https://example.com,https://app.example.com
CORS_ALLOWED_ORIGINS = _getenv_csv("DJANGO_CORS_ALLOWED_ORIGINS", [])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": int(os.getenv("POSTGRES_PORT", "5432")),
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
# 圧縮+ハッシュ付与でキャッシュ最適化
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
