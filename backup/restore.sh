#!/bin/bash
# AIP-X Database Restore Script
# Usage: ./restore.sh <backup_file.sql.gz> <DATABASE_URL>
#
# Example:
#   ./restore.sh aipx_backup_20260314_020000.sql.gz \
#     "postgresql://postgres:PASSWORD@interchange.proxy.rlwy.net:52241/railway"

set -e

BACKUP_FILE="$1"
DB_URL="$2"

if [ -z "$BACKUP_FILE" ] || [ -z "$DB_URL" ]; then
    echo "Usage: $0 <backup_file.sql.gz> <DATABASE_URL>"
    echo ""
    echo "Steps to restore:"
    echo "  1. Download backup from Railway volume or local copy"
    echo "  2. Run this script with the backup file and DATABASE_URL"
    echo ""
    echo "Example:"
    echo "  $0 aipx_backup_20260314_020000.sql.gz 'postgresql://user:pass@host:port/db'"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "=== AIP-X Database Restore ==="
echo "Backup: $BACKUP_FILE"
echo "Target: $DB_URL"
echo ""
echo "WARNING: This will DROP and recreate all tables!"
read -p "Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Restoring..."
gunzip -c "$BACKUP_FILE" | psql "$DB_URL"

echo ""
echo "Restore complete. Verify with:"
echo "  psql $DB_URL -c 'SELECT COUNT(*) FROM audit_ledger;'"
echo "  psql $DB_URL -c 'SELECT COUNT(*) FROM queries;'"
