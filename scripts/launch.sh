#!/bin/bash
# Launch the Multi-Agent Dashboard
# Usage: bash launch.sh [port]

PORT="${1:-9121}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🖥️  Starting Multi-Agent Dashboard on port $PORT ..."
echo "   Open: http://localhost:$PORT"
echo "   Press Ctrl+C to stop"
echo ""

python3 "$SCRIPT_DIR/dashboard_server.py" --port "$PORT" &
SERVER_PID=$!

# Wait for server to start
sleep 1

# Open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:$PORT"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:$PORT"
elif command -v wslview &>/dev/null; then
    wslview "http://localhost:$PORT"
fi

# Wait for server process
wait $SERVER_PID
