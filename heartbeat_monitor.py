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

import math
import json
import os
import smtplib
import traceback
from datetime import date, datetime, timedelta
from email.message import EmailMessage

import config


RUN_LOG_FILE = "run_log.json"
MAX_LOG_ENTRIES = 400          # roughly 18 months of weekdays

# How far the newest archived session may trail the calendar before the
# heartbeat treats it as a problem rather than ordinary provider lag. The
# heartbeat fires Friday 22:00 UTC and can itself be hours late, so a lag of
# one or two days is normal; beyond that the screener has stopped keeping up.
MAX_BAR_LAG_DAYS = 3


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
    entries = _clean(entries[-MAX_LOG_ENTRIES:])
    with open(RUN_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, allow_nan=False)
    return entries


def record_run(status, tickers_screened=0, matches=None,
               error=None, near_misses=None, bar_date=None):
    """
    Append one entry describing this run.

    Called on both success and failure, so a crashed run still leaves evidence
    that it happened.
    """
    entries = load_run_log()

    run_date = bar_date or datetime.now().date().isoformat()

    # A run whose newest bar is not newer than the previous run's screened
    # nothing new -- the data provider had not published the session yet.
    # Recording it as "ok" makes a silent no-op look like a healthy run.
    if status == "ok" and entries:
        prev = entries[-1].get("date")
        if prev and run_date <= prev:
            status = "stale"

    entries.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "date": run_date,
        "status": status,                       # "ok" | "stale" | "error"
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

         # A ticker with no price change has no measurable distance from the
        # threshold -- that is missing data, not a near miss.
        candidates = candidates[candidates["price_change_pct"].notna()]
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

def _clean(obj):
    """Replace NaN with None so the log is valid JSON.

    NaN is not part of the JSON spec. Python writes and reads it happily,
    but nothing else does, and this file is meant to outlive the script
    that wrote it.
    """
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


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


def _newest_bar_date(entries):
    """The most recent trading session the run log actually covers."""
    dates = []
    for e in entries:
        try:
            dates.append(date.fromisoformat(e["date"]))
        except (ValueError, KeyError, TypeError):
            continue
    return max(dates) if dates else None


def build_weekly_summary(days_back=7):
    """Assemble the heartbeat from the run log and the alert history.

    The window is anchored on the newest session in the log, not on the clock.
    Entries are keyed by bar_date -- the session the screener read -- so when
    the provider runs a day behind, the run that did happen is filed under an
    earlier date. Anchoring on datetime.now() then reported that weekday as a
    skipped run and blamed GitHub for a gap that never occurred.

    Anchoring alone would hide a real outage, because a log that stopped
    updating a week ago would slide the whole window back into healthy
    territory. days_since_last_bar is the guard: it measures the anchor
    against the clock, so a stalled screener shows up as lag rather than as
    missing days.
    """
    entries = load_run_log()
    clock_today = datetime.now().date()
    anchor = _newest_bar_date(entries) or clock_today
    start = anchor - timedelta(days=days_back - 1)

    recent = []
    for e in entries:
        try:
            d = datetime.fromisoformat(e["date"]).date()
            if start <= d <= anchor:
                recent.append(e)
        except (ValueError, KeyError):
            continue

    expected = _expected_weekdays(start, anchor)

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
    stale = [e for e in weekday_runs if e.get("status") == "stale"]
    ran_dates = {e["date"] for e in weekday_runs}

    missing = []
    d = start
    while d <= anchor:
        if d.weekday() < 5 and d.isoformat() not in ran_dates:
            missing.append(d.isoformat())
        d += timedelta(days=1)

    # Count DAYS a ticker qualified, not log entries. A day with two runs --
    # a delayed scheduled one plus a retry, say -- must count once.
    match_days = {}
    for e in ok_runs:
        for t in e.get("matches", []):
            match_days.setdefault(t, set()).add(e["date"])
    match_counts = {t: len(days) for t, days in match_days.items()}

    # Current persistence, read from the live alert history
    persistent = []
    try:
        with open(config.ALERTS_HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

        # qualifying_dates are bar dates too, so the cutoff is measured from
        # the anchor rather than the clock.
        cutoff = anchor - timedelta(days=config.STREAK_WINDOW_DAYS)
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
        "end": anchor.isoformat(),
        "as_of": anchor.isoformat(),
        "days_since_last_bar": (clock_today - anchor).days,
        "expected_runs": expected,
        "actual_runs": len(ran_dates),
        "ok_runs": len(ok_runs),
        "failed_runs": len(failed),
        "stale_runs": len(stale),
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

    if s.get("stale_runs"):
        lines.append(f"Runs STALE:      {s['stale_runs']} "
                f"(ran, but the data provider had no new bar)")
    if s["missing_dates"]:
        lines.append(f"Missing days:    {', '.join(s['missing_dates'])}")
        lines.append("                 (GitHub scheduled runs are best-effort"
                     " and are sometimes skipped)")

    # The window above is measured in trading sessions. This line is the only
    # one measured against the calendar, and it is what distinguishes "caught
    # up to Thursday because Friday has not published yet" from "stopped".
    lag = s.get("days_since_last_bar")
    if lag is not None:
        lines.append(f"Newest session:  {s.get('as_of', s['end'])}"
                     f" ({lag} day(s) behind today)")
        if lag > MAX_BAR_LAG_DAYS:
            lines.append("                 WARNING: no new session archived in"
                         f" over {MAX_BAR_LAG_DAYS} days -- the screener has"
                         " likely stopped running")

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
            pct = nm.get("price_change_pct")
            pct_text = f"{pct:+.1f}%" if pct is not None else "n/a"
            lines.append(f"  {nm['ticker']:<6} volume {nm['volume_ratio']}x, "
                         f"price {pct_text}")
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
    elif s.get("days_since_last_bar", 0) > MAX_BAR_LAG_DAYS:
        # Checked before GAPS: a log that stopped updating has a window full
        # of healthy-looking runs, so lag is the only symptom left.
        health = "STALLED"
    elif s["actual_runs"] < s["expected_runs"]:
        health = "GAPS"

    subject = (f"[Screener {health}] {s['actual_runs']}/{s['expected_runs']} runs, "
               f"{len(s['match_counts'])} name(s) matched")

    return _send(subject, format_weekly_plaintext(s))


if __name__ == "__main__":
    # Invoked by the weekly workflow
    send_weekly_summary()