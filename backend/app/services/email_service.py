"""Email delivery service with HTML templates.

Sends emails synchronously (designed to be called from Celery tasks)
or can be used directly in async context via run_in_executor.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── HTML Templates ──

_BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f172a; color:#e2e8f0;">
<div style="max-width:600px; margin:0 auto; padding:32px 24px;">
  <div style="text-align:center; margin-bottom:32px;">
    <h1 style="color:#60a5fa; font-size:28px; margin:0;">ABLE</h1>
    <p style="color:#64748b; font-size:12px; margin:4px 0 0;">AI Trading Platform</p>
  </div>
  <div style="background:#1e293b; border-radius:12px; padding:24px; border:1px solid #334155;">
    {content}
  </div>
  {action_button}
  <div style="text-align:center; margin-top:32px; padding-top:24px; border-top:1px solid #1e293b;">
    <p style="color:#475569; font-size:11px; margin:0;">
      This is an automated notification from ABLE Trading Platform.<br>
      You can manage notification preferences in your dashboard settings.
    </p>
  </div>
</div>
</body>
</html>
"""

_ACTION_BUTTON = """
<div style="text-align:center; margin-top:20px;">
  <a href="{url}" style="display:inline-block; background:#3b82f6; color:white; padding:12px 28px; border-radius:8px; text-decoration:none; font-weight:600; font-size:14px;">
    {label}
  </a>
</div>
"""


def _render_template(content_html: str, action_url: str | None = None, action_label: str = "View Details") -> str:
    """Render email content into the base template."""
    btn = ""
    if action_url:
        btn = _ACTION_BUTTON.format(url=action_url, label=action_label)
    return _BASE_TEMPLATE.format(content=content_html, action_button=btn)


# ── Template builders ──

def template_order_filled(stock_code: str, side: str, quantity: int, price: float) -> tuple[str, str]:
    """Returns (subject, html_body) for order filled notification."""
    color = "#22c55e" if side.lower() == "buy" else "#ef4444"
    content = f"""
    <div style="text-align:center; margin-bottom:16px;">
      <span style="background:{color}20; color:{color}; padding:4px 12px; border-radius:6px; font-size:13px; font-weight:600;">
        {side.upper()} ORDER FILLED
      </span>
    </div>
    <h2 style="text-align:center; margin:12px 0 4px; font-size:22px; color:#f1f5f9;">{stock_code}</h2>
    <table style="width:100%; margin-top:16px; border-collapse:collapse;">
      <tr><td style="padding:8px 0; color:#94a3b8; font-size:13px;">Side</td><td style="padding:8px 0; text-align:right; color:#f1f5f9; font-weight:600;">{side.upper()}</td></tr>
      <tr><td style="padding:8px 0; color:#94a3b8; font-size:13px;">Quantity</td><td style="padding:8px 0; text-align:right; color:#f1f5f9; font-weight:600;">{quantity:,} shares</td></tr>
      <tr><td style="padding:8px 0; color:#94a3b8; font-size:13px;">Fill Price</td><td style="padding:8px 0; text-align:right; color:#f1f5f9; font-weight:600;">{price:,.0f} KRW</td></tr>
      <tr><td style="padding:8px 0; color:#94a3b8; font-size:13px;">Total Value</td><td style="padding:8px 0; text-align:right; color:#f1f5f9; font-weight:600;">{quantity * price:,.0f} KRW</td></tr>
    </table>
    """
    subject = f"[ABLE] Order Filled: {side.upper()} {stock_code}"
    return subject, _render_template(content, action_url=None)


def template_agent_error(session_id: str, error: str) -> tuple[str, str]:
    """Returns (subject, html_body) for agent error notification."""
    content = f"""
    <div style="text-align:center; margin-bottom:16px;">
      <span style="background:#ef444420; color:#ef4444; padding:4px 12px; border-radius:6px; font-size:13px; font-weight:600;">
        AGENT ERROR
      </span>
    </div>
    <p style="color:#f1f5f9; font-size:14px; line-height:1.6; margin:12px 0;">
      Your AI agent session encountered an error and has been stopped.
    </p>
    <div style="background:#0f172a; border-radius:8px; padding:12px 16px; margin:16px 0;">
      <p style="color:#94a3b8; font-size:12px; margin:0 0 4px;">Error Details</p>
      <p style="color:#fbbf24; font-size:13px; font-family:monospace; margin:0; word-break:break-all;">{error}</p>
    </div>
    <p style="color:#64748b; font-size:12px; margin:12px 0 0;">Session: {session_id[:8]}...</p>
    """
    subject = "[ABLE] AI Agent Error - Action Required"
    return subject, _render_template(content, action_url=None)


def template_pending_approval(session_id: str, trade_count: int, total_value: float) -> tuple[str, str]:
    """Returns (subject, html_body) for pending approval notification."""
    content = f"""
    <div style="text-align:center; margin-bottom:16px;">
      <span style="background:#f59e0b20; color:#f59e0b; padding:4px 12px; border-radius:6px; font-size:13px; font-weight:600;">
        APPROVAL REQUIRED
      </span>
    </div>
    <p style="color:#f1f5f9; font-size:14px; line-height:1.6; text-align:center; margin:12px 0;">
      Your AI agent has <strong>{trade_count} trade(s)</strong> pending your approval.
    </p>
    <div style="text-align:center; background:#0f172a; border-radius:8px; padding:16px; margin:16px 0;">
      <p style="color:#94a3b8; font-size:12px; margin:0 0 4px;">Total Trade Value</p>
      <p style="color:#60a5fa; font-size:24px; font-weight:700; margin:0;">{total_value:,.0f} KRW</p>
    </div>
    """
    subject = f"[ABLE] {trade_count} Trade(s) Pending Approval"
    return subject, _render_template(content, action_url=None, action_label="Review Trades")


def template_pnl_alert(stock_code: str, pnl: float, pnl_pct: float) -> tuple[str, str]:
    """Returns (subject, html_body) for P&L alert."""
    color = "#22c55e" if pnl >= 0 else "#ef4444"
    direction = "Gain" if pnl >= 0 else "Loss"
    content = f"""
    <div style="text-align:center; margin-bottom:16px;">
      <span style="background:{color}20; color:{color}; padding:4px 12px; border-radius:6px; font-size:13px; font-weight:600;">
        P&L ALERT
      </span>
    </div>
    <h2 style="text-align:center; margin:12px 0 4px; font-size:22px; color:#f1f5f9;">{stock_code}</h2>
    <div style="text-align:center; margin:16px 0;">
      <p style="color:{color}; font-size:28px; font-weight:700; margin:0;">{pnl_pct:+.1f}%</p>
      <p style="color:#94a3b8; font-size:13px; margin:4px 0 0;">Unrealized {direction}: {abs(pnl):,.0f} KRW</p>
    </div>
    """
    subject = f"[ABLE] P&L Alert: {stock_code} {pnl_pct:+.1f}%"
    return subject, _render_template(content)


# ── Sending ──

def send_email(to_address: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True on success.

    This is synchronous — call from Celery tasks or via run_in_executor.
    """
    settings = get_settings()

    if not settings.smtp_host:
        logger.debug("SMTP not configured, skipping email to %s", to_address)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Email sent to %s: %s", to_address, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_address, e)
        return False
