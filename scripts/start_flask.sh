#!/bin/bash
# Start Flask server for NC Foreclosures

set -e

# Get to project root
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Set Python path
export PYTHONPATH=$(pwd)

# Load environment variables and start Flask
python -c "from dotenv import load_dotenv; load_dotenv(); from web_app.app import create_app; create_app().run(host='0.0.0.0', port=5001, debug=True)"
