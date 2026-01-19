#!/bin/bash
# NC Foreclosures Database Backup Script
# Runs daily before the morning scrape to protect manual analysis data

set -e

BACKUP_DIR="/home/ahn/projects/nc_foreclosures/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/nc_foreclosures_$TIMESTAMP.sql.gz"
RETENTION_DAYS=7

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Create compressed backup
echo "Creating backup: $BACKUP_FILE"
PGPASSWORD=nc_password pg_dump -U nc_user -h localhost nc_foreclosures | gzip > "$BACKUP_FILE"

# Verify backup was created
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "Backup complete: $BACKUP_FILE ($SIZE)"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Remove backups older than retention period
echo "Removing backups older than $RETENTION_DAYS days..."
DELETED=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "Deleted $DELETED old backup(s)"

# List current backups
echo ""
echo "Current backups:"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "No backups found"
