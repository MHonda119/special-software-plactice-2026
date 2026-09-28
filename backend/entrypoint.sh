#!/usr/bin/env sh
set -e

# DB待機（Postgres）: psycopg2で接続確認
if [ -n "${POSTGRES_HOST:-}" ]; then
  echo "Waiting for database ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
  python - <<'PY'
import os, time, sys
import psycopg2

host = os.getenv('POSTGRES_HOST', 'db')
port = int(os.getenv('POSTGRES_PORT', '5432'))
dbname = os.getenv('POSTGRES_DB')
user = os.getenv('POSTGRES_USER')
password = os.getenv('POSTGRES_PASSWORD')

for i in range(60):
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.close()
        print('Database is ready')
        sys.exit(0)
    except Exception as e:
        print(f'Waiting for database... ({i+1}/60) {e!r}')
        time.sleep(1)

print('Database not ready, exiting', file=sys.stderr)
sys.exit(1)
PY
fi


# 起動時処理の制御（k8sではJobに寄せるため、Pod起動時は無効化する運用を推奨）
: "${DJANGO_RUN_MIGRATIONS:=true}"
: "${DJANGO_COLLECTSTATIC:=true}"
: "${DJANGO_CREATE_SUPERUSER:=true}"

if [ "${DJANGO_RUN_MIGRATIONS}" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "${DJANGO_COLLECTSTATIC}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

# 初回の管理ユーザー自動作成（環境変数で制御）
if [ "${DJANGO_CREATE_SUPERUSER}" = "true" ]; then
  python manage.py shell <<'PYCODE'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin")

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Created superuser: {username}")
else:
    print("Superuser already exists. Skipping.")
PYCODE
fi

exec "$@"
