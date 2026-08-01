#!/bin/sh
set -e

DB_HOST=$(python -c "import environ,os; e=environ.Env(); environ.Env.read_env('.env'); print(e.db('DATABASE_URL')['HOST'])")
DB_PORT=$(python -c "import environ,os; e=environ.Env(); environ.Env.read_env('.env'); print(e.db('DATABASE_URL')['PORT'])")

echo "Waiting for Postgres at ${DB_HOST}:${DB_PORT}..."
until nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 0.5
done
echo "Postgres is up."

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
