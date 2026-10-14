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

## Resume in one step (new session, or after the 7-day expiry)

1. Run `python3 monitor_status.py` to see last snapshot, any gap, and whether a restart is due.
2. Tell Claude: **"resume Flip-Or monitoring."** Claude re-arms the hourly cron (`7 * * * *`)
   with the connection-check + notify behavior, and the 7-day restart reminder.

Gaps (hours the loop wasn't running) simply show as gaps in the chart — no data is corrupted.
