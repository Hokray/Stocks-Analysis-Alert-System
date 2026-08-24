"""
Email notification layer for the stock screener.

Handles three jobs:
  1. Tracking the full alert history per ticker, so a stock that keeps
     qualifying day after day is visibly flagged as a persistent wave rather
     than looking identical to a one-off spike.
  2. Suppressing repeat emails inside a cooldown window.
  3. Formatting and sending the alert email.

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
# History
#
# Structure per ticker:
#   {
#     "qualifying_dates": ["2026-08-24", "2026-08-25", ...],
#     "last_emailed": "2026-08-24T07:30:00",
#     "first_seen": "2026-08-20"
#   }
#
# qualifying_dates is recorded EVERY run, even when no email goes out. That is
# what lets the screener say "qualified 8 of the last 10 days" instead of just
# re-alerting blindly or staying silent.
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


def prune_old_dates(dates, window_days=90):
    """Drop qualifying dates older than the tracking window."""
    cutoff = datetime.now().date() - timedelta(days=window_days)
    kept = []
    for d in dates:
        try:
            if datetime.fromisoformat(d).date() >= cutoff:
                kept.append(d)
        except ValueError:
            continue
    return sorted(set(kept))


def current_streak(dates):
    """
    How many days within the streak window this ticker qualified.

    Returns (count_in_window, calendar_days_spanned).
    """
    window = config.STREAK_WINDOW_DAYS
    cutoff = datetime.now().date() - timedelta(days=window)

    in_window = []
    for d in dates:
        try:
            parsed = datetime.fromisoformat(d).date()
            if parsed >= cutoff:
                in_window.append(parsed)
        except ValueError:
            continue

    if not in_window:
        return 0, 0

    in_window.sort()
    span = (datetime.now().date() - in_window[0]).days + 1
    return len(in_window), span


def describe_streak(count, span):
    """Human-readable persistence label shown in the email."""
    if count <= 1:
        return "First alert", "new"
    if count >= config.PERSISTENT_STREAK_MIN:
        return f"Qualified {count} of the last {span} days", "strong"
    return f"Qualified {count} times in {span} days", "building"


# ---------------------------------------------------------------------------
# Recording and filtering
# ---------------------------------------------------------------------------

def record_and_filter(matches, history):
    """
    Record today's qualifiers, then decide which ones get emailed.

    Every match is recorded. Only matches outside the email cooldown are
    returned for sending, but each carries its streak info so the email can
    show how persistent it has been.
    """
    now = datetime.now()
    today = now.date().isoformat()
    cooldown = timedelta(days=config.ALERT_COOLDOWN_DAYS)
    to_send = []

    for match in matches:
        ticker = match["ticker"]
        entry = history.get(ticker, {})

        # --- always record that it qualified today ---
        dates = prune_old_dates(entry.get("qualifying_dates", []) + [today])
        entry["qualifying_dates"] = dates
        entry.setdefault("first_seen", today)

        count, span = current_streak(dates)
        match["streak_count"] = count
        match["streak_span"] = span
        match["streak_label"], match["streak_level"] = describe_streak(count, span)

        # --- decide whether to email ---
        last_emailed = entry.get("last_emailed")
        should_email = True

        if last_emailed:
            try:
                if now - datetime.fromisoformat(last_emailed) < cooldown:
                    should_email = False
            except ValueError:
                pass

        # A ticker crossing into "persistent" territory is worth re-sending
        # even inside the cooldown -- that crossing is the whole signal.
        if (not should_email
                and count >= config.PERSISTENT_STREAK_MIN
                and not entry.get("persistence_notified")):
            should_email = True
            entry["persistence_notified"] = True

        if should_email:
            entry["last_emailed"] = now.isoformat()
            to_send.append(match)
        else:
            print(f"  {ticker}: qualified again (streak {count}), "
                  f"inside cooldown - recorded but not emailed")

        history[ticker] = entry

    return to_send, history


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
            f"  {m['streak_label']}",
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
        "-" * 55,
        "Persistence matters: a name qualifying day after day suggests capital",
        "keeps arriving, rather than a single-day spike.",
        "",
        "This is a research screener, not investment advice.",
    ]
    return "\n".join(lines)


STREAK_COLOURS = {
    "new": ("#e8f0fe", "#1a56c4"),
    "building": ("#fef7e0", "#a06400"),
    "strong": ("#e6f4ea", "#137333"),
}


def build_html(matches):
    rows = ""
    for m in matches:
        bg, fg = STREAK_COLOURS.get(m.get("streak_level", "new"),
                                    STREAK_COLOURS["new"])
        rows += f"""
        <tr>
          <td style="padding:12px 10px;border-bottom:1px solid #eee;">
            <strong style="font-size:15px;">{m['ticker']}</strong><br>
            <span style="color:#666;font-size:12px;">{m['company']}</span><br>
            <span style="color:#999;font-size:11px;">{m['category']} &middot; {m['exchange']}</span><br>
            <span style="display:inline-block;margin-top:6px;padding:2px 8px;
                         background:{bg};color:{fg};border-radius:10px;
                         font-size:11px;font-weight:600;">
              {m['streak_label']}
            </span>
          </td>
          <td style="padding:12px 10px;border-bottom:1px solid #eee;text-align:right;">
            ${m['price']}<br>
            <span style="color:#137333;font-weight:600;">{m['price_change_pct']:+.1f}%</span>
          </td>
          <td style="padding:12px 10px;border-bottom:1px solid #eee;text-align:right;">
            <strong>{m['volume_ratio']}x</strong><br>
            <span style="color:#666;font-size:12px;">${m['recent_dollar_vol_musd']:,.0f}M/day</span>
          </td>
          <td style="padding:12px 10px;border-bottom:1px solid #eee;text-align:right;font-size:13px;">
            ${m['market_cap_busd']}B<br>
            <span style="color:#666;font-size:12px;">CFO ${m['ttm_cfo_musd']:,.0f}M</span>
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;
                       max-width:760px;margin:0 auto;color:#222;">
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
      <p style="color:#555;font-size:12px;margin-top:18px;background:#fafafa;
                padding:10px;border-radius:6px;">
        <strong>Reading the tag:</strong> a name that keeps qualifying day after day
        means capital is still arriving, not a single spike. Green =
        {config.PERSISTENT_STREAK_MIN}+ qualifying days in the window.
      </p>
      <p style="color:#999;font-size:11px;margin-top:20px;border-top:1px solid #eee;padding-top:12px;">
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
    persistent = [m["ticker"] for m in matches
                  if m.get("streak_level") == "strong"]

    if persistent:
        msg["Subject"] = f"Screener: {tickers} (persistent: {', '.join(persistent)})"
    else:
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
    Entry point. Records every qualifying ticker (so streaks build even on days
    no email goes out), then emails whatever is due.
    """
    history = load_history()

    if not matches:
        print("No matches today.")
        save_history(history)
        return

    to_send, history = record_and_filter(matches, history)

    # Always save -- the streak record must persist even with no email.
    save_history(history)

    if not to_send:
        print("All matches recorded, none due for email.")
        return

    send_email(to_send)