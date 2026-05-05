#!/bin/sh
set -eu

wait_for_mysql() {
  if [ -n "${MYSQL_HOST:-}" ]; then
    echo "Aguardando MySQL em ${MYSQL_HOST}:${MYSQL_PORT:-3306}..."
    while ! nc -z "$MYSQL_HOST" "${MYSQL_PORT:-3306}"; do
      sleep 1
    done
  fi
}

run_init_tasks() {
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
}

wait_for_mysql

if [ "${1:-}" = "init" ]; then
  run_init_tasks
  exit 0
fi

if [ "${APP_RUN_MIGRATIONS:-0}" = "1" ] || [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${APP_COLLECTSTATIC:-0}" = "1" ] || [ "${RUN_COLLECTSTATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
