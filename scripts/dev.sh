#!/usr/bin/env bash
# Local development bootstrap
set -e
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements/development.txt

[ -f .env ] || cp .env.example .env

python manage.py migrate
python manage.py seed_plans
python manage.py seed_cron
echo "Done. Run: python manage.py runserver"
