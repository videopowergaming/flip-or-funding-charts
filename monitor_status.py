#!/usr/bin/env python3
"""Flip-Or Wave 2 — monitoring status check (runs locally, no network).

Reads the funding log + monitor state and reports:
  - latest logged snapshot and how long ago it was
  - whether the hourly loop looks stalled (a gap since the last snapshot)
  - whether the 7-day session-cron restart is due
  - days left until the campaign deadline

Use at the start of a session to see where things stand:
    python3 monitor_status.py
"""

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
CAMP = CONFIG["campaign"]
LOG = ROOT / CAMP["funding_log"]
STATE = ROOT / "data" / "monitor_state.json"


def main() -> None:
    now = dt.datetime.now().astimezone()
    print("=== Flip-Or Wave 2 — monitoring status ===")

    # --- latest snapshot ---
    log = json.loads(LOG.read_text()) if LOG.exists() else []
    if log:
        last = log[-1]
        last_t = dt.datetime.fromisoformat(last["timestamp"])
        gap = now - last_t
        hrs = gap.total_seconds() / 3600
        print(f"Snapshots logged : {len(log)}")
        print(f"Latest           : ${last['pledged_usd']:,.0f} / {last['backers']:,} backers")
        print(f"  recorded        : {last_t.strftime('%a %b %d %Y %I:%M %p %Z')}  ({hrs:.1f}h ago)")
        if hrs > 2:
            print(f"  ⚠️  gap > 2h — hourly loop may be stopped (session closed / Mac asleep / extension off).")

        # per-day calendar
        by_day = {}
        for e in log:
            t = dt.datetime.fromisoformat(e["timestamp"])
            by_day.setdefault(t.date(), []).append((t, e["pledged_usd"], e["backers"]))
        print("\nUpdate calendar:")
        d, last_day, one = min(by_day), max(by_day), dt.timedelta(days=1)
        prev = None
        while d <= last_day:
            if d in by_day:
                snaps = sorted(by_day[d])
                _, pl, bk = snaps[-1]
                gain = "" if prev is None else f"(+${pl-prev:,.0f})"
                print(f"  {d.strftime('%a %b %d')} : ${pl:,.0f} {gain:<12} {bk:,} backers  [{len(snaps)} snap]")
                prev = pl
            else:
                print(f"  {d.strftime('%a %b %d')} : — no data (away) —")
            d += one
    else:
        print("No snapshots logged yet.")

    # --- restart + deadline ---
    if STATE.exists():
        st = json.loads(STATE.read_text())["monitoring"]
        restart = dt.datetime.fromisoformat(st["restart_reminder_date"]).date()
        expires = dt.datetime.fromisoformat(st["expires_7day"]).date()
        today = now.date()
        print(f"Loop cadence     : {st['cadence']} (cron '{st['cron_hourly']}')")
        if today >= expires:
            print(f"  🔁 RESTART DUE  — the 7-day session cron expired {expires}. Restart the hourly loop.")
        elif today >= restart:
            print(f"  🔁 restart soon — 7-day cron expires {expires}. Consider restarting now.")
        else:
            print(f"  next restart due ~{expires} (reminder {restart}).")

    deadline = dt.datetime.fromisoformat(CAMP["deadline"])
    dleft = (deadline - now).days
    print(f"Campaign deadline: {deadline.strftime('%b %d %Y %I:%M %p %Z')}  ({dleft} days left)")
    print(f"Campaign         : {CAMP['url']}")


if __name__ == "__main__":
    main()
