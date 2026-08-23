"""
Email notification layer for the stock screener.

Handles two jobs:
  1. Remembering which tickers have already been alerted (so you don't get the
     same stock emailed to you every day while it sits in the 10-day window).
  2. Formatting and sending the alert email.

Credentials come from environment variables, never from code:
    EMAIL_ADDRESS       the Gmail account sending the mail
    EMAIL_APP_PASSWORD  a Google App Password (NOT your real password)
    EMAIL_TO            comma-separated list of recipients
"""

import json
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

import config


# ---------------------------------------------------------------------------
# Deduplication
#
# Without this, a stock that trips the trigger on Monday is still inside the
# 10-day lookback window on Tuesday and Wednesday, so you'd get the identical
# alert three days running and start ignoring the emails.
# ---------------------------------------------------------------------------

def load_history():
    path = config.ALERTS_HISTORY_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_history(history):
    with open(config.ALERTS_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, sort_keys=True)


def filter_new_alerts(matches, history):
    """
    Drop any ticker alerted within the cooldown window.

    Returns (fresh_matches, updated_history).
    """
    today = datetime.now()
    cooldown = timedelta(days=config.ALERT_COOLDOWN_DAYS)
    fresh = []

    for match in matches:
        ticker = match["ticker"]
        last_alerted = history.get(ticker, {}).get("last_alerted")

        if last_alerted:
            try:
                if today - datetime.fromisoformat(last_alerted) < cooldown:
                    print(f"  {ticker}: already alerted on {last_alerted[:10]}, skipping")
                    continue
            except ValueError:
                pass  # malformed date, treat as never alerted

        fresh.append(match)
        history[ticker] = {
            "last_alerted": today.isoformat(),
            "price": match["price"],
            "volume_ratio": match["volume_ratio"],
            "price_change_pct": match["price_change_pct"],
        }

    return fresh, history


# ---------------------------------------------------------------------------
# Email formatting
# ---------------------------------------------------------------------------

def build_plaintext(matches):
    lines = [
        f"Stock screener alert - {datetime.now().strftime('%A %d %B %Y')}",
        "",
        f"{len(matches)} name(s) tripped all screening conditions.",
        "",
    ]

    for m in matches:
        lines += [
            f"{m['ticker']} - {m['company']}",
            f"  Category:      {m['category']} ({m['exchange']})",
            f"  Price:         ${m['price']}  ({m['price_change_pct']:+.1f}% over "
            f"{config.RECENT_WINDOW_DAYS} days)",
            f"  Dollar volume: {m['volume_ratio']}x its 3-month normal "
            f"(${m['recent_dollar_vol_musd']:,.0f}M/day)",
            f"  Market cap:    ${m['market_cap_busd']}B",
            f"  TTM cash ops:  ${m['ttm_cfo_musd']:,.0f}M",
            "",
        ]

    lines += [
        "-" * 50,
        "This is a research screener, not investment advice. It flags where",
        "capital is concentrating so you know what to look into.",
    ]
    return "\n".join(lines)


def build_html(matches):
    rows = ""
    for m in matches:
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            <strong style="font-size:15px;">{m['ticker']}</strong><br>
            <span style="color:#666;font-size:12px;">{m['company']}</span><br>
            <span style="color:#999;font-size:11px;">{m['category']} &middot; {m['exchange']}</span>
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:right;">
            ${m['price']}<br>
            <span style="color:#137333;font-weight:600;">{m['price_change_pct']:+.1f}%</span>
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:right;">
            <strong>{m['volume_ratio']}x</strong><br>
            <span style="color:#666;font-size:12px;">${m['recent_dollar_vol_musd']:,.0f}M/day</span>
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee;text-align:right;font-size:13px;">
            ${m['market_cap_busd']}B<br>
            <span style="color:#666;font-size:12px;">CFO ${m['ttm_cfo_musd']:,.0f}M</span>
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;
                       max-width:720px;margin:0 auto;color:#222;">
      <h2 style="margin-bottom:4px;">Screener alert</h2>
      <p style="color:#666;margin-top:0;font-size:13px;">
        {datetime.now().strftime('%A %d %B %Y')} &middot;
        {len(matches)} name(s) tripped all conditions
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="background:#f7f7f7;text-align:left;font-size:12px;color:#666;">
          <th style="padding:8px;">Company</th>
          <th style="padding:8px;text-align:right;">Price / {config.RECENT_WINDOW_DAYS}d</th>
          <th style="padding:8px;text-align:right;">$ Volume vs normal</th>
          <th style="padding:8px;text-align:right;">Size</th>
        </tr>
        {rows}
      </table>
      <p style="color:#999;font-size:11px;margin-top:24px;border-top:1px solid #eee;padding-top:12px;">
        Conditions: dollar volume &ge; {config.VOLUME_SURGE_THRESHOLD}x its 3-month average,
        price &ge; +{config.PRICE_CHANGE_THRESHOLD*100:.0f}% over {config.RECENT_WINDOW_DAYS} days,
        positive TTM cash from operations.<br>
        Research screener, not investment advice.
      </p>
    </body></html>"""


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send_email(matches):
    """Send the alert. Returns True on success."""
    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    recipients = os.environ.get("EMAIL_TO", "")

    if not all([sender, password, recipients]):
        print("Email credentials missing - set EMAIL_ADDRESS, "
              "EMAIL_APP_PASSWORD and EMAIL_TO")
        return False

    recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]

    msg = EmailMessage()
    tickers = ", ".join(m["ticker"] for m in matches)
    msg["Subject"] = f"Screener: {tickers}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)

    msg.set_content(build_plaintext(matches))
    msg.add_alternative(build_html(matches), subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Email sent to {len(recipient_list)} recipient(s): {tickers}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


def notify(matches):
    """
    Entry point. Takes the list of matching stocks, filters out ones already
    alerted recently, and emails whatever is left.
    """
    if not matches:
        print("No matches - no email sent.")
        return

    history = load_history()
    fresh, history = filter_new_alerts(matches, history)

    if not fresh:
        print("All matches were already alerted recently - no email sent.")
        return

    if send_email(fresh):
        save_history(history)