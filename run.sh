#!/usr/bin/env bash
set -e
python3 -m pip install -e .
python3 -m playwright install chromium
python3 -m app.cli init
python3 -m app.cli seed-qna
python3 -m app.cli web
