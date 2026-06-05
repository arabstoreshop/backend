#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS_ON_START" = "true" ]; then
  echo "Running Alembic migrations..."
  alembic upgrade head
  echo "Migrations complete."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
