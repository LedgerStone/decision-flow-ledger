"""
AIP-X — Email Notification Service
Sends alerts via Gmail SMTP when queries require approval.
"""

import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("aipx")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "decision.acc@gmail.com"
SMTP_PASS = os.getenv("SMTP_PASS", "")
NOTIFY_TO = "decision.acc@gmail.com"


def _send_email(subject: str, html_body: str) -> None:
    """Send an email via Gmail SMTP. Runs in caller's thread."""
    if not SMTP_PASS:
        logger.warning("SMTP_PASS not set — skipping email notification")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, NOTIFY_TO, msg.as_string())
        logger.info("Email sent: %s", subject)
    except Exception as e:
        logger.error("Failed to send email: %s", e)


def _send_async(subject: str, html_body: str) -> None:
    """Fire-and-forget email in a background thread so the API doesn't block."""
    t = threading.Thread(target=_send_email, args=(subject, html_body), daemon=True)
    t.start()


def notify_query_submitted(
    query_id: int,
    operator: str,
    query_text: str,
    reason: str,
    query_hash: str,
) -> None:
    """Send notification when a new query is submitted and awaits approval."""
    subject = f"[AIP-X] New query #{query_id} requires approval"

    html = f"""\
<html>
<body style="font-family: monospace; background: #0a0a0a; color: #e0e0e0; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; border: 1px solid #333; border-radius: 8px; padding: 24px;">
    <h2 style="color: #00ff88; margin-top: 0;">New Query Awaiting Approval</h2>
    <table style="width: 100%; border-collapse: collapse;">
      <tr>
        <td style="padding: 8px 12px; color: #888; border-bottom: 1px solid #222;">Query ID</td>
        <td style="padding: 8px 12px; color: #fff; border-bottom: 1px solid #222;"><strong>#{query_id}</strong></td>
      </tr>
      <tr>
        <td style="padding: 8px 12px; color: #888; border-bottom: 1px solid #222;">Operator</td>
        <td style="padding: 8px 12px; color: #fff; border-bottom: 1px solid #222;">{operator}</td>
      </tr>
      <tr>
        <td style="padding: 8px 12px; color: #888; border-bottom: 1px solid #222;">SQL Query</td>
        <td style="padding: 8px 12px; color: #fff; border-bottom: 1px solid #222;">
          <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px; word-break: break-all;">{query_text}</code>
        </td>
      </tr>
      <tr>
        <td style="padding: 8px 12px; color: #888; border-bottom: 1px solid #222;">Reason</td>
        <td style="padding: 8px 12px; color: #fff; border-bottom: 1px solid #222;">{reason}</td>
      </tr>
      <tr>
        <td style="padding: 8px 12px; color: #888;">Hash</td>
        <td style="padding: 8px 12px; color: #666; font-size: 11px; word-break: break-all;">{query_hash}</td>
      </tr>
    </table>
    <p style="margin-top: 16px; color: #888; font-size: 12px;">
      This query requires 2 supervisor/judge approvals before execution.<br>
      Review it on the <a href="https://aip-x-dashboard-production.up.railway.app" style="color: #00ff88;">AIP-X Dashboard</a>.
    </p>
    <hr style="border-color: #333;">
    <p style="color: #555; font-size: 11px; margin-bottom: 0;">AIP-X &mdash; Accountable Intelligence Platform</p>
  </div>
</body>
</html>"""

    _send_async(subject, html)
