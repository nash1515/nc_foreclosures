#!/bin/bash
# VPN Start Script - handles password input cleanly
# Usage: ./scripts/vpn_start.sh [server]
# Server options: virginia (default), california, florida, georgia, illinois, newyork

set -e

VPN_DIR="/home/ahn/frootvpn"
LOG_FILE="/tmp/openvpn.log"
AUTH_FILE="$VPN_DIR/auth.txt"
BASELINE_IP="136.61.20.173"

# Check if already connected
CURRENT_IP=$(timeout 5 curl -s --connect-timeout 3 --max-time 4 ifconfig.me 2>/dev/null || echo "")
if [ -n "$CURRENT_IP" ] && [ "$CURRENT_IP" != "$BASELINE_IP" ]; then
    echo "VPN already connected (IP: $CURRENT_IP)"
    exit 0
fi

# Map short names to config files
case "${1:-virginia}" in
    virginia)   CONFIG="United States - Virginia.ovpn" ;;
    california) CONFIG="United States - California.ovpn" ;;
    florida)    CONFIG="United States - Florida.ovpn" ;;
    georgia)    CONFIG="United States - Georgia.ovpn" ;;
    illinois)   CONFIG="United States - Illinois.ovpn" ;;
    newyork)    CONFIG="United States - New York.ovpn" ;;
    *)          echo "Unknown server: $1"; exit 1 ;;
esac

# Kill any existing OpenVPN
sudo -S killall openvpn 2>/dev/null <<< "ahn" || true
sleep 1

# Start OpenVPN in daemon mode
echo "Starting VPN: $CONFIG"
cd "$VPN_DIR"
sudo -S openvpn --config "$CONFIG" --auth-user-pass "$AUTH_FILE" --daemon --log "$LOG_FILE" <<< "ahn"

# Wait for connection (check log for "Initialization Sequence Completed")
echo "Waiting for connection..."
for i in {1..15}; do
    sleep 1
    if grep -q "Initialization Sequence Completed" "$LOG_FILE" 2>/dev/null; then
        NEW_IP=$(timeout 5 curl -s --connect-timeout 3 --max-time 4 ifconfig.me)
        echo "VPN connected! IP: $NEW_IP"
        exit 0
    fi
    echo -n "."
done

echo ""
echo "Connection timeout. Check $LOG_FILE"
tail -20 "$LOG_FILE"
exit 1
