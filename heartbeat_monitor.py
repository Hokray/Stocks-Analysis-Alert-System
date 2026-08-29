"""
Monitoring and alerting for the screener.

The problem this solves: silence is ambiguous. An empty inbox can mean the
screener ran and found nothing, that GitHub skipped the scheduled run, or that
the script crashed. All three look identical from the outside.

Three pieces:

  1. RUN LOG      every run appends an entry to run_log.json, whether it
                  matched anything or not
  2. FAILURE MAIL any unhandled exception emails the traceback immediately
  3. HEARTBEAT    a weekly summary confirming how many runs actually happened

The run log is the important part. Without it there is no record of which days
the screener actually executed, which means the persistence counts in
alerts_history.json have unknown gaps.
"""

import json
import os
import smtplib
import traceback
from datetime import datetime, timedelta
from email.message import EmailMessage

import config


RUN_LOG_FILE = "run_log.json"
MAX_LOG_ENTRIES = 400          # roughly 18 months of weekdays


# ---------------------------------------------------------------------------
# Run log
# ---------------------------------------------------------------------------

def load_run_log():
    if not os.path.exists(RUN_LOG_FILE):
        return []
    try:
        with open(RUN_LOG_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_run_log(entries):
    """Truncate to the cap and write. Returns what was actually saved."""
    entries = entries[-MAX_LOG_ENTRIES:]
    with open(RUN_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    return entries


def record_run(status, tickers_screened=0, matches=None,
               error=None, near_misses=None):
    """
    Append one entry describing this run.

    Called on both success and failure, so a crashed run still leaves evidence
    that it happened.
    """
    entries = load_run_log()

    entries.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "date": datetime.now().date().isoformat(),
        "status": status,                       # "ok" | "error"
        "tickers_screened": tickers_screened,
        "match_count": len(matches or []),
        "matches": [m["ticker"] for m in (matches or [])],
        "near_misses": near_misses or [],
        "error": str(error)[:500] if error else None,
    })

    saved = save_run_log(entries)
    return saved


def find_near_misses(results_df, top_n=3):
    """
    Tickers that passed the cash-flow gate and came closest to tripping both
    technical conditions without doing so.

    Useful in the weekly summary: it shows the screener is looking at live data
    and reaching sensible conclusions, rather than silently returning nothing.
    """
    if results_df is None or results_df.empty:
        return []

    try:
        candidates = results_df[
            (~results_df["MATCH"]) & (results_df["pass_cfo"])
        ].copy()

        if candidates.empty:
            return []

        # Distance from qualifying, as a fraction of each threshold
        vol_gap = ((config.VOLUME_SURGE_THRESHOLD - candidates["volume_ratio"])
                   / config.VOLUME_SURGE_THRESHOLD).clip(lower=0)
        price_gap = ((config.PRICE_CHANGE_THRESHOLD * 100
                      - candidates["price_change_pct"])
                     / (config.PRICE_CHANGE_THRESHOLD * 100)).clip(lower=0)

        candidates["distance"] = vol_gap + price_gap
        closest = candidates.nsmallest(top_n, "distance")

        return [
            {
                "ticker": r["ticker"],
                "volume_ratio": round(r["volume_ratio"], 2),
                "price_change_pct": round(r["price_change_pct"], 1),
            }
            for _, r in closest.iterrows()
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Email plumbing
# ---------------------------------------------------------------------------

def _send(subject, plaintext, html=None, recipients_env="EMAIL_TO"):
    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    recipients = os.environ.get(recipients_env, "")

    if not all([sender, password, recipients]):
        print("Monitor: email credentials missing, cannot send")
        return False

    recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)
    msg.set_content(plaintext)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"Monitor: sent '{subject}'")
        return True
    except Exception as e:
        print(f"Monitor: send failed - {e}")
        return False


# ---------------------------------------------------------------------------
# Failure alert
# ---------------------------------------------------------------------------

def send_failure_alert(error, tb_text=None):
    """
    Email immediately on an unhandled exception.

    Goes only to the operator (FAILURE_EMAIL_TO if set, otherwise EMAIL_TO) --
    a stack trace is not useful to everyone on the alert list.
    """
    tb_text = tb_text or traceback.format_exc()
    when = datetime.now().strftime("%Y-%m-%d %H:%M")

    body = f"""The screener failed and did not complete.

Time:  {when}
Error: {error}

Traceback
---------
{tb_text}

No alert email was sent for this run. The next scheduled run will retry.
Check the Actions tab for the full log.
"""

    env_key = "FAILURE_EMAIL_TO" if os.environ.get("FAILURE_EMAIL_TO") else "EMAIL_TO"
    return _send(f"[SCREENER FAILED] {type(error).__name__}", body,
                 recipients_env=env_key)


# ---------------------------------------------------------------------------
# Weekly heartbeat
# ---------------------------------------------------------------------------

def _expected_weekdays(start_date, end_date):
    """Count Mon-Fri days in an inclusive range (ignores market holidays)."""
    days, d = 0, start_date
    while d <= end_date:
        if d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return days


def build_weekly_summary(days_back=7):
    """Assemble the heartbeat from the run log and the alert history."""
    entries = load_run_log()
    today = datetime.now().date()
    start = today - timedelta(days=days_back - 1)

    recent = []
    for e in entries:
        try:
            d = datetime.fromisoformat(e["date"]).date()
            if start <= d <= today:
                recent.append(e)
        except (ValueError, KeyError):
            continue

    expected = _expected_weekdays(start, today)

    # Count weekday runs only, so this figure and missing_dates agree.
    # A manual weekend run would otherwise inflate the count while the
    # weekday it did not cover still shows as missing.
    def _is_weekday(entry):
        try:
            return datetime.fromisoformat(entry["date"]).date().weekday() < 5
        except (ValueError, KeyError):
            return False

    weekday_runs = [e for e in recent if _is_weekday(e)]
    ok_runs = [e for e in weekday_runs if e.get("status") == "ok"]
    failed = [e for e in weekday_runs if e.get("status") == "error"]
    ran_dates = {e["date"] for e in weekday_runs}

    missing = []
    d = start
    while d <= today:
        if d.weekday() < 5 and d.isoformat() not in ran_dates:
            missing.append(d.isoformat())
        d += timedelta(days=1)

    # Matches over the window
    match_counts = {}
    for e in ok_runs:
        for t in e.get("matches", []):
            match_counts[t] = match_counts.get(t, 0) + 1

    # Current persistence, read from the live alert history
    persistent = []
    try:
        with open(config.ALERTS_HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

        cutoff = today - timedelta(days=config.STREAK_WINDOW_DAYS)
        for ticker, entry in history.items():
            dates = entry.get("qualifying_dates", [])
            in_window = [
                d for d in dates
                if datetime.fromisoformat(d).date() >= cutoff
            ]
            if len(in_window) >= config.PERSISTENT_STREAK_MIN:
                persistent.append((ticker, len(in_window)))
        persistent.sort(key=lambda x: -x[1])
    except (OSError, json.JSONDecodeError, ValueError):
        pass

    latest_near = recent[-1].get("near_misses", []) if recent else []

    return {
        "start": start.isoformat(),
        "end": today.isoformat(),
        "expected_runs": expected,
        "actual_runs": len(weekday_runs),
        "ok_runs": len(ok_runs),
        "failed_runs": len(failed),
        "missing_dates": missing,
        "match_counts": match_counts,
        "persistent": persistent,
        "near_misses": latest_near,
        "last_run": recent[-1]["timestamp"] if recent else None,
    }


def format_weekly_plaintext(s):
    lines = [
        f"Screener weekly summary  {s['start']} to {s['end']}",
        "=" * 52,
        "",
        f"Runs completed:  {s['actual_runs']} of {s['expected_runs']} expected weekdays",
    ]

    if s["failed_runs"]:
        lines.append(f"Runs FAILED:     {s['failed_runs']}")
    if s["missing_dates"]:
        lines.append(f"Missing days:    {', '.join(s['missing_dates'])}")
        lines.append("                 (GitHub scheduled runs are best-effort"
                     " and are sometimes skipped)")

    lines += ["", f"Last run: {s['last_run'] or 'none recorded'}", ""]

    if s["match_counts"]:
        lines.append("Matches this week:")
        for t, c in sorted(s["match_counts"].items(), key=lambda x: -x[1]):
            lines.append(f"  {t:<6} qualified on {c} day(s)")
    else:
        lines.append("Matches this week: none")
    lines.append("")

    if s["persistent"]:
        lines.append(f"Currently persistent "
                     f"(>= {config.PERSISTENT_STREAK_MIN} days "
                     f"in last {config.STREAK_WINDOW_DAYS}):")
        for t, n in s["persistent"]:
            lines.append(f"  {t:<6} {n} qualifying days")
    else:
        lines.append("Currently persistent: none")
    lines.append("")

    if s["near_misses"]:
        lines.append("Closest to qualifying on the most recent run:")
        for nm in s["near_misses"]:
            lines.append(f"  {nm['ticker']:<6} volume {nm['volume_ratio']}x, "
                         f"price {nm['price_change_pct']:+.1f}%")
        lines.append("")

    lines += [
        "-" * 52,
        "This email confirms the screener is running. If it stops arriving,",
        "the automation has broken -- check the GitHub Actions tab.",
    ]
    return "\n".join(lines)


def send_weekly_summary():
    s = build_weekly_summary()

    health = "OK"
    if s["failed_runs"]:
        health = "ERRORS"
    elif s["actual_runs"] < s["expected_runs"]:
        health = "GAPS"

    subject = (f"[Screener {health}] {s['actual_runs']}/{s['expected_runs']} runs, "
               f"{len(s['match_counts'])} name(s) matched")

    return _send(subject, format_weekly_plaintext(s))


if __name__ == "__main__":
    # Invoked by the weekly workflow
    send_weekly_summary()