from .settings import *  # noqa

# SQLite (in-memory) for tests so that PostgreSQL container不要
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
