#!/bin/bash
# Run the Flask API server

cd "$(dirname "$0")/.."
export PYTHONPATH=$(pwd)
source venv/bin/activate

# Load .env if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

python web_app/app.py
