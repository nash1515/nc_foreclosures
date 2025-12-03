#!/bin/bash
# Scheduler control script for NC Foreclosures
# Usage: ./scripts/scheduler_control.sh [install|start|stop|status|logs|uninstall]

SERVICE_NAME="nc-foreclosures-scheduler"
SERVICE_FILE="/home/ahn/projects/nc_foreclosures/scheduler/nc-foreclosures-scheduler.service"
LOG_FILE="/var/log/nc-foreclosures-scheduler.log"

case "$1" in
    install)
        echo "Installing scheduler service..."
        sudo cp "$SERVICE_FILE" /etc/systemd/system/
        sudo touch "$LOG_FILE"
        sudo chown ahn:ahn "$LOG_FILE"
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        echo "Service installed and enabled. Start with: $0 start"
        ;;

    start)
        echo "Starting scheduler service..."
        sudo systemctl start "$SERVICE_NAME"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;

    stop)
        echo "Stopping scheduler service..."
        sudo systemctl stop "$SERVICE_NAME"
        echo "Scheduler stopped."
        ;;

    restart)
        echo "Restarting scheduler service..."
        sudo systemctl restart "$SERVICE_NAME"
        sudo systemctl status "$SERVICE_NAME" --no-pager
        ;;

    status)
        sudo systemctl status "$SERVICE_NAME" --no-pager
        echo ""
        echo "Recent logs:"
        tail -20 "$LOG_FILE" 2>/dev/null || echo "No logs yet"
        ;;

    logs)
        tail -f "$LOG_FILE"
        ;;

    uninstall)
        echo "Uninstalling scheduler service..."
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null
        sudo systemctl disable "$SERVICE_NAME" 2>/dev/null
        sudo rm -f /etc/systemd/system/"$SERVICE_NAME".service
        sudo systemctl daemon-reload
        echo "Service uninstalled."
        ;;

    *)
        echo "Usage: $0 {install|start|stop|restart|status|logs|uninstall}"
        echo ""
        echo "Commands:"
        echo "  install   - Install and enable the systemd service"
        echo "  start     - Start the scheduler"
        echo "  stop      - Stop the scheduler"
        echo "  restart   - Restart the scheduler"
        echo "  status    - Show scheduler status and recent logs"
        echo "  logs      - Follow scheduler logs in real-time"
        echo "  uninstall - Remove the systemd service"
        exit 1
        ;;
esac
