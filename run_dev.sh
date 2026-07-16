#!/usr/bin/env bash
# MikRapor — geliştirme ortamında çalıştır (Linux / macOS).
# Windows için: .\run_dev.ps1
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -d ".venv" ]; then
    echo "Sanal ortam oluşturuluyor..."
    "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
python main.py
