# Monitoring

How the screener reports on its own health, and why that is necessary.

---

## The problem: silence is ambiguous

The screener only emails when a stock qualifies. Most days nothing does, so an
empty inbox is the normal state.

That creates a blind spot. Three completely different situations produce an
identical empty inbox:

| What happened | Inbox | Reality |
|---|---|---|
| Ran, nothing qualified | empty | Working correctly |
| GitHub skipped the scheduled run | empty | Data gap |
| Script crashed | empty | Broken |

Without monitoring, the only way to tell them apart is manually opening the
GitHub Actions tab. That is exactly how one skipped run went unnoticed until it
was spotted by chance.

**This is not hypothetical.** During the first week of live operation:

- A scheduled run was skipped entirely, with no notification
- Another arrived **10 hours 37 minutes late**, executing at 19:14 UTC against a
  cron set for 08:37 UTC

GitHub scheduled workflows are explicitly best-effort. They are the lowest
priority on shared infrastructure, and under load they are delayed or dropped
without warning.

**Why this matters beyond convenience:** the project is currently collecting
out-of-sample data to validate the persistence finding. If runs are silently
skipped, `alerts_history.json` develops gaps, persistence counts under-report,
and the validation is quietly corrupted with no way to detect it afterwards.
The run log is the audit trail that makes the experiment trustworthy.

---

## What was built

Three components in `monitor.py`:

### 1. Run log

Every run appends an entry to `run_log.json`, **whether it matched anything or
not**, and whether it succeeded or failed:

```json
{
  "timestamp": "2026-08-27T21:15:04",
  "date": "2026-08-27",
  "status": "ok",
  "tickers_screened": 60,
  "match_count": 1,
  "matches": ["NBIS"],
  "near_misses": [
    {"ticker": "LITE", "volume_ratio": 1.47, "price_change_pct": 6.8}
  ],
  "error": null
}
```

This is the foundation — everything else reads from it. Like
`alerts_history.json`, it must be **committed back to the repo** by the
workflow, because the runner is destroyed after each run.

Capped at 400 entries (roughly 18 months of weekdays) so it cannot grow without
limit.

### 2. Failure alerts

The screener is wrapped so any unhandled exception sends an immediate email with
the traceback:

```
Subject: [SCREENER FAILED] HTTPError

Time:  2026-08-27 21:15
Error: HTTPError 429: Too Many Requests
...
```

Sent to `FAILURE_EMAIL_TO` if set, otherwise `EMAIL_TO`. A stack trace is
operator information, not something everyone on the alert list needs.

Most likely causes in practice: yfinance rate limiting, a Yahoo endpoint change,
or a delisted ticker.

### 3. Weekly heartbeat

Every Friday, one email regardless of activity:

```
Screener weekly summary  2026-08-22 to 2026-08-28
====================================================

Runs completed:  3 of 5 expected weekdays
Runs FAILED:     1
Missing days:    2026-08-25, 2026-08-28
                 (GitHub scheduled runs are best-effort and are
                  sometimes skipped)

Last run: 2026-08-27T21:15:00

Matches this week:
  NBIS   qualified on 2 day(s)

Currently persistent (>= 8 days in last 14):
  NBIS   11 qualifying days

Closest to qualifying on the most recent run:
  LITE   volume 1.47x, price +6.8%
```

The subject line carries the health state so it is visible without opening the
mail:

- `[Screener OK]` — every expected weekday ran
- `[Screener GAPS]` — runs missing
- `[Screener ERRORS]` — at least one run failed

**Near-misses are included deliberately.** They demonstrate the screener is
processing live data and reaching sensible conclusions, rather than silently
returning nothing because something upstream broke. A week of "no matches" plus
plausible near-misses is reassuring; "no matches" with no near-misses at all is
suspicious.

---

## Design notes

**Weekday counting.** `actual_runs` counts weekday runs only, so it reconciles
with `missing_dates`. An early version counted all entries, which meant a manual
weekend run inflated the total while the weekday it did not cover still appeared
as missing — the summary contradicted itself.

**Market holidays are not modelled.** Thanksgiving and similar days will appear
as "missing." Adding a holiday calendar was not judged worth the dependency;
a handful of false gaps per year is acceptable for a health check.

**The heartbeat schedule can be late without consequence.** Unlike the screener,
it reads the run log rather than live market data, so a delayed heartbeat is
merely a late email.

**Failure alerts are not rate-limited.** If the screener breaks for a week you
receive five emails. That is deliberate — a persistent failure should be
annoying.

---

## Files

| File | Purpose | Committed? |
|---|---|---|
| `monitor.py` | Run log, failure alerts, weekly summary | Yes |
| `run_log.json` | Execution history | **Yes — must be** |
| `.github/workflows/weekly_heartbeat.yml` | Friday schedule | Yes |

---

## Setup

**1. Add `monitor.py`** to the repo root.

**2. Wrap the screener.** In `screener.py`, replace the `__main__` block:

```python
if __name__ == "__main__":
    import monitor
    try:
        main()
    except Exception as e:
        monitor.record_run("error", error=e)
        monitor.send_failure_alert(e)
        raise          # re-raise so the workflow shows as failed
```

**3. Record successful runs.** At the end of `main()`, after the results are
written:

```python
    monitor.record_run(
        "ok",
        tickers_screened=len(results),
        matches=matches.to_dict("records"),
        near_misses=monitor.find_near_misses(df),
    )
```

**4. Add the workflow** at `.github/workflows/weekly_heartbeat.yml`.

**5. Commit the run log** from the daily workflow. Extend the existing persist
step:

```yaml
      - name: Persist alerts history and run log
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add alerts_history.json run_log.json
          if git diff --staged --quiet; then
            echo "Nothing to record."
          else
            git commit -m "Update alerts history and run log [skip ci]"
            git push
          fi
```

Note this step must now run **even when the screener fails**, so the failure is
logged. Add `if: always()` to it.

**6. Create `run_log.json`** containing `[]` and commit it, or the first
`git add` fails on a missing file.

**7. Optionally add a `FAILURE_EMAIL_TO` secret** to send tracebacks only to
yourself.

---

## Testing

Trigger the heartbeat manually from the Actions tab — `workflow_dispatch` is
enabled. It will summarise whatever is in the run log.

To test failure alerting, temporarily point `TICKER_FILE` at a path that does
not exist. The screener will raise, email the traceback, and the run will show
as failed in Actions. Revert afterwards.

---

## What this does not cover

**Data quality.** A run can succeed while returning nonsense — stale prices, or
`None` cash flow because a cache key changed. Detecting that requires assertions
on the values themselves, not just on whether the script exited cleanly.

**Timing drift.** The log records when a run happened but does not alert if it
executed at the wrong time. The 10.5-hour delay described above would appear in
the log as a normal run. The evening schedule makes the consequence harmless,
but the drift itself is invisible.

**Delivery failure.** If Gmail rejects the message, the screener records `ok` and
you receive nothing. The heartbeat partially covers this: if that email stops
arriving too, mail delivery is the likely cause.