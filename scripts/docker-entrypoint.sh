#!/bin/bash
set -e

mkdir -p data models logs

if [ ! -f "data/accesslens.db" ]; then
    echo "Initializing SQLite database..."
    python scripts/setup_db.py
fi

if [ -f "scripts/run_migrations.py" ]; then
    echo "Running database migrations..."
    python scripts/run_migrations.py
fi

echo "Starting AccessLens API..."
exec "$@"
