# Monitoring & Restart — Flip-Or Wave 2

This file persists the live-monitoring setup so it's **tracked in GitHub** and survives
logouts / days off. The *data* and *config* always persist here; the *hourly execution*
is session-bound (see the honest limits below) and is re-armed in one step each session.

## Current setup

- **Cadence:** hourly, at **:07** past the hour (cron `7 * * * *`)
- **Started:** 2026-10-14 · **7-day cron expiry:** ~2026-10-21 · **Restart reminder:** 2026-10-20
- **Campaign deadline:** Nov 17 2026, 8:00 PM EST
- Each hour: read pledged $ + backers from the campaign via the logged-in Chrome →
  `python3 build.py --record --pledged N --backers N` → commit + push.

## What persists in GitHub (survives logout / days off)

- ✅ All funding data (`data/flipor_wave2_funding_log.json`) — never lost.
- ✅ The chart, the build script, and this monitoring spec + state (`data/monitor_state.json`).
- ✅ So you can always see the history and pick up exactly where it left off.

## What does NOT persist (session-only, must be re-armed)

- ⚠️ The hourly cron job and the restart-reminder — they live only in an **active Claude session**.
- They cannot run from GitHub or the cloud, because reading Kickstarter requires *your logged-in
  Chrome* (Kickstarter blocks scripted/API access — HTTP 403).

## For the hourly loop to actually fire

Chrome running + Claude extension connected (🧩) + Mac awake + the Claude session open.
Minimizing the tab, switching windows, or opening new tabs/windows is **fine** — the monitor
uses its own background tab and doesn't touch your other tabs.

## Resume in one step (new session, or after the 7-day expiry / days away)

When Patrick logs back in after any break, Claude should:
1. Run `python3 monitor_status.py` — **report the last day/time data was pulled**, show the
   **update calendar** (which days have data, which were "away"), and the gap since last pull.
2. **Take a fresh snapshot now** (pull current pledged/backers via Chrome) →
   `python3 build.py --record --pledged N --backers N` → graph it → commit + push.
3. Re-arm the hourly cron (`7 * * * *`, with connection-check + notify) and the restart reminder.

So the flow is always: *"here's when we last updated + the calendar → now here's today's new point, graphed."*

### Where the calendar + last-pull live
- **`data/monitor_state.json`** stores `last_pulled`, `last_pledged_usd`, `last_backers` (stamped on every snapshot, committed to GitHub) — so the last update is known even across logouts.
- The **chart page** (`charts/flipor_wave2_funding.html`) shows an **Update calendar** table: per-day end-of-day pledged, daily gain, backers, snapshots, and flags days with **no data (away)**.
- `monitor_status.py` prints the same calendar in the terminal.

Gaps (hours/days the loop wasn't running) show as gaps/"away" rows — no data is corrupted.
