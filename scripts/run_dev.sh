#!/bin/bash
# Run both frontend and API in development mode

cd "$(dirname "$0")/.."

echo "Starting Flask API on port 5000..."
./scripts/run_api.sh &
API_PID=$!

echo "Starting React frontend on port 5173..."
./scripts/run_frontend.sh &
FRONTEND_PID=$!

echo ""
echo "Development servers running:"
echo "  - API: http://localhost:5000"
echo "  - Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C and cleanup
trap "kill $API_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
