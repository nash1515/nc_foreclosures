#!/bin/bash
# VPN Status Check - quick verification
# Returns exit code 0 if VPN is connected, 1 if not

BASELINE_IP="136.61.20.173"

CURRENT_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null)

if [ -z "$CURRENT_IP" ]; then
    echo "ERROR: Could not get current IP"
    exit 1
fi

if [ "$CURRENT_IP" = "$BASELINE_IP" ]; then
    echo "VPN NOT connected (IP: $CURRENT_IP = baseline)"
    exit 1
else
    echo "VPN connected (IP: $CURRENT_IP)"
    exit 0
fi
