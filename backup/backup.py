"""
AIP-X Database Backup Service
Runs daily pg_dump at configured time, keeps N most recent backups.
Stores backups on Railway volume at /data/backups.
"""

import os
import subprocess
import time
import gzip
import shutil
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlparse

# Config
DATABASE_URL = os.getenv("DATABASE_URL", "")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/data/backups"))
BACKUP_HOUR = int(os.getenv("BACKUP_HOUR", "2"))       # 02:00 UTC
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "7"))        # Keep 7 days
API_URL = os.getenv("MONITOR_API_URL", "https://aip-x-api-production.up.railway.app")
API_KEY = os.getenv("API_KEY", "")


def log(msg):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}", flush=True)


def parse_db_url(url):
    """Parse DATABASE_URL into components for pg_dump."""
    p = urlparse(url)
    return {
        "host": p.hostname,
        "port": str(p.port or 5432),
        "user": p.username,
        "password": p.password,
        "dbname": p.path.lstrip("/"),
    }


def run_backup():
    """Execute pg_dump and compress output."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_file = BACKUP_DIR / f"aipx_backup_{ts}.sql"
    gz_file = BACKUP_DIR / f"aipx_backup_{ts}.sql.gz"

    db = parse_db_url(DATABASE_URL)
    env = os.environ.copy()
    env["PGPASSWORD"] = db["password"]

    log(f"Starting backup to {gz_file.name}...")

    try:
        result = subprocess.run(
            [
                "pg_dump",
                "-h", db["host"],
                "-p", db["port"],
                "-U", db["user"],
                "-d", db["dbname"],
                "--no-owner",
                "--no-privileges",
                "-F", "p",       # plain SQL format
                "-f", str(dump_file),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            log(f"pg_dump FAILED: {result.stderr}")
            return False, result.stderr

        # Compress
        with open(dump_file, "rb") as f_in:
            with gzip.open(gz_file, "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)

        dump_file.unlink()  # remove uncompressed

        size_kb = gz_file.stat().st_size / 1024
        log(f"Backup complete: {gz_file.name} ({size_kb:.1f} KB)")
        return True, gz_file.name

    except subprocess.TimeoutExpired:
        log("pg_dump TIMEOUT (120s)")
        return False, "timeout"
    except Exception as e:
        log(f"Backup error: {e}")
        return False, str(e)


def cleanup_old_backups():
    """Keep only MAX_BACKUPS most recent backups."""
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("aipx_backup_*.sql.gz"), reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink()
        log(f"Deleted old backup: {old.name}")


def list_backups():
    """List all available backups."""
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("aipx_backup_*.sql.gz"), reverse=True)
    return [
        {
            "file": b.name,
            "size_kb": round(b.stat().st_size / 1024, 1),
            "created": datetime.fromtimestamp(b.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for b in backups
    ]


def verify_backup(gz_file):
    """Quick verification: decompress and check for key SQL markers."""
    path = BACKUP_DIR / gz_file
    if not path.exists():
        return False, "file not found"
    try:
        with gzip.open(path, "rt") as f:
            content = f.read(4096)
            has_tables = "CREATE TABLE" in content or "audit_ledger" in content
            return has_tables, "valid SQL dump" if has_tables else "no expected tables found"
    except Exception as e:
        return False, str(e)


def run_immediate_backup():
    """Run a single backup immediately (for startup/testing)."""
    log("Running immediate backup on startup...")
    ok, detail = run_backup()
    if ok:
        cleanup_old_backups()
        valid, msg = verify_backup(detail)
        log(f"Verification: {msg}")
    backups = list_backups()
    log(f"Available backups: {len(backups)}")
    for b in backups:
        log(f"  {b['file']} — {b['size_kb']} KB — {b['created']}")
    return ok


def run_scheduler():
    """Main loop: run backup at BACKUP_HOUR UTC daily."""
    log("AIP-X Backup Service started")
    log(f"  Database: {DATABASE_URL[:30]}...") if DATABASE_URL else log("  WARNING: DATABASE_URL not set!")
    log(f"  Backup dir: {BACKUP_DIR}")
    log(f"  Schedule: daily at {BACKUP_HOUR:02d}:00 UTC")
    log(f"  Retention: {MAX_BACKUPS} backups")
    log("")

    # Run immediate backup on first start
    run_immediate_backup()

    last_backup_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    while True:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        if now.hour == BACKUP_HOUR and today != last_backup_date:
            ok, detail = run_backup()
            if ok:
                cleanup_old_backups()
                valid, msg = verify_backup(detail)
                log(f"Verification: {msg}")
            last_backup_date = today

        time.sleep(60)  # check every minute


if __name__ == "__main__":
    run_scheduler()
