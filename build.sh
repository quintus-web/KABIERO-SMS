#!/usr/bin/env bash
set -o errexit

echo "=== Installing dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput --verbosity 0 --skip-checks

echo "=== Running database migrations ==="
python manage.py migrate --noinput --skip-checks

echo "=== Applying Kabiero Academy starter configuration ==="
python manage.py bootstrap_kabiero --skip-checks

echo "=== Build complete ==="
