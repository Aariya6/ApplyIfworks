#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
python -m app.cli init
python -m app.cli seed-qna
python -m app.cli seed-companies
[ -f .env ] || cp .env.example .env
python -m app.cli setup
