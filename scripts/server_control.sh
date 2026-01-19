#!/bin/bash
# Server control script for NC Foreclosures (API + Frontend)
# Usage: ./scripts/server_control.sh [install|start|stop|restart|status|logs|uninstall]

API_SERVICE="nc-foreclosures-api"
FRONTEND_SERVICE="nc-foreclosures-frontend"
SERVICE_DIR="/home/ahn/projects/nc_foreclosures/scheduler"

case "$1" in
    install)
        echo "Installing server services..."
        sudo cp "$SERVICE_DIR/$API_SERVICE.service" /etc/systemd/system/
        sudo cp "$SERVICE_DIR/$FRONTEND_SERVICE.service" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable "$API_SERVICE"
        sudo systemctl enable "$FRONTEND_SERVICE"
        echo "Services installed and enabled. Start with: $0 start"
        ;;

    start)
        echo "Starting server services..."
        sudo systemctl start "$API_SERVICE"
        sudo systemctl start "$FRONTEND_SERVICE"
        echo ""
        echo "=== API Service ==="
        sudo systemctl status "$API_SERVICE" --no-pager
        echo ""
        echo "=== Frontend Service ==="
        sudo systemctl status "$FRONTEND_SERVICE" --no-pager
        ;;

    stop)
        echo "Stopping server services..."
        sudo systemctl stop "$API_SERVICE"
        sudo systemctl stop "$FRONTEND_SERVICE"
        echo "Servers stopped."
        ;;

    restart)
        echo "Restarting server services..."
        sudo systemctl restart "$API_SERVICE"
        sudo systemctl restart "$FRONTEND_SERVICE"
        echo ""
        echo "=== API Service ==="
        sudo systemctl status "$API_SERVICE" --no-pager
        echo ""
        echo "=== Frontend Service ==="
        sudo systemctl status "$FRONTEND_SERVICE" --no-pager
        ;;

    status)
        echo "=== API Service ==="
        sudo systemctl status "$API_SERVICE" --no-pager
        echo ""
        echo "=== Frontend Service ==="
        sudo systemctl status "$FRONTEND_SERVICE" --no-pager
        ;;

    logs)
        if [ "$2" = "api" ]; then
            echo "Following API logs (Ctrl+C to exit)..."
            sudo journalctl -u "$API_SERVICE" -f
        elif [ "$2" = "frontend" ]; then
            echo "Following frontend logs (Ctrl+C to exit)..."
            sudo journalctl -u "$FRONTEND_SERVICE" -f
        else
            echo "Recent logs from both services:"
            echo ""
            echo "=== API Logs (last 20 lines) ==="
            sudo journalctl -u "$API_SERVICE" -n 20 --no-pager
            echo ""
            echo "=== Frontend Logs (last 20 lines) ==="
            sudo journalctl -u "$FRONTEND_SERVICE" -n 20 --no-pager
            echo ""
            echo "To follow logs: $0 logs [api|frontend]"
        fi
        ;;

    uninstall)
        echo "Uninstalling server services..."
        sudo systemctl stop "$API_SERVICE" 2>/dev/null
        sudo systemctl stop "$FRONTEND_SERVICE" 2>/dev/null
        sudo systemctl disable "$API_SERVICE" 2>/dev/null
        sudo systemctl disable "$FRONTEND_SERVICE" 2>/dev/null
        sudo rm -f /etc/systemd/system/"$API_SERVICE".service
        sudo rm -f /etc/systemd/system/"$FRONTEND_SERVICE".service
        sudo systemctl daemon-reload
        echo "Services uninstalled."
        ;;

    *)
        echo "Usage: $0 {install|start|stop|restart|status|logs|uninstall}"
        echo ""
        echo "Commands:"
        echo "  install   - Install and enable the systemd services"
        echo "  start     - Start both API and frontend servers"
        echo "  stop      - Stop both servers"
        echo "  restart   - Restart both servers"
        echo "  status    - Show status of both services"
        echo "  logs      - Show recent logs from both services"
        echo "              Use 'logs api' or 'logs frontend' to follow specific service"
        echo "  uninstall - Remove the systemd services"
        exit 1
        ;;
esac
