"""
AIP-X Health Monitor
Checks API health every 5 minutes and sends email alert on failure.
Runs as a standalone service on Railway.
"""

import os
import time
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

API_URL = os.getenv("MONITOR_API_URL", "https://aip-x-api-production.up.railway.app")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutes
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "decision.acc@gmail.com")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

# Track state to avoid spamming alerts
last_alert_time = 0
ALERT_COOLDOWN = 1800  # 30 min between repeat alerts
consecutive_failures = 0


def check_health():
    """Check API health endpoint. Returns (ok, details)."""
    try:
        req = Request(f"{API_URL}/health", headers={"User-Agent": "AIP-X-Monitor/1.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            status = data.get("status", "unknown")
            if status == "healthy":
                return True, data
            return False, data
    except URLError as e:
        return False, {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return False, {"error": str(e)}


def send_alert(subject, body):
    """Send email alert via SMTP."""
    global last_alert_time
    now = time.time()

    if now - last_alert_time < ALERT_COOLDOWN:
        print(f"  Alert suppressed (cooldown). Last alert {int(now - last_alert_time)}s ago.")
        return

    if not SMTP_USER or not SMTP_PASS:
        print(f"  SMTP not configured. Would send: {subject}")
        print(f"  To: {ALERT_EMAIL}")
        print(f"  Body: {body}")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        last_alert_time = now
        print(f"  Alert sent to {ALERT_EMAIL}")
    except Exception as e:
        print(f"  Failed to send alert: {e}")


def run():
    global consecutive_failures
    print(f"AIP-X Monitor started")
    print(f"  Target: {API_URL}")
    print(f"  Interval: {CHECK_INTERVAL}s")
    print(f"  Alert email: {ALERT_EMAIL}")
    print(f"  SMTP configured: {'yes' if SMTP_USER else 'no (alerts logged to stdout)'}")
    print()

    while True:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ok, details = check_health()

        if ok:
            consecutive_failures = 0
            counts = details.get("counts", {})
            print(f"[{now}] OK — db={details.get('database')} bc={details.get('blockchain')} "
                  f"queries={counts.get('queries', '?')} ledger={counts.get('ledger_entries', '?')} "
                  f"blocks={counts.get('blocks', '?')}")
        else:
            consecutive_failures += 1
            print(f"[{now}] FAIL #{consecutive_failures} — {json.dumps(details)}")

            if consecutive_failures >= 2:
                send_alert(
                    f"[AIP-X ALERT] API unhealthy — {consecutive_failures} consecutive failures",
                    f"AIP-X Health Monitor Alert\n"
                    f"Time: {now}\n"
                    f"Endpoint: {API_URL}/health\n"
                    f"Consecutive failures: {consecutive_failures}\n"
                    f"Details: {json.dumps(details, indent=2)}\n\n"
                    f"Dashboard: https://aip-x-dashboard-production.up.railway.app\n"
                    f"Railway: https://railway.com\n"
                )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
