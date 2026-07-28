#!/bin/sh
set -e

DB_FILE="/app/db.sqlite3"

# If db file exists but is empty or invalid, remove it so Django creates a fresh one
if [ -f "$DB_FILE" ]; then
  if ! sqlite3 "$DB_FILE" "PRAGMA integrity_check;" > /dev/null 2>&1; then
    echo "Invalid database file found, removing..."
    rm -f "$DB_FILE"
  fi
fi

# Ensure the file exists (Docker bind-mount needs it)
touch "$DB_FILE"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8011
