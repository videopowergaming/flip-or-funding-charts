# Flip-Or Funding Charts

Tracks and graphs **time vs. dollars backed** for the Kickstarter campaign
**"FLIP-OR and the CHAMPIONS of NEFARITY - WAVE 2!!"** by Hatter Toys.

🔗 Campaign: https://www.kickstarter.com/projects/1332620926/flip-or-and-the-champions-of-nefarity-wave-2
🎯 Goal: $200,000 · ⏰ Deadline: Nov 17 2026, 8:00 PM EST

## What it does

- Logs timestamped funding snapshots (pledged $, backers) to `data/flipor_wave2_funding_log.json`.
- Renders a dependency-free, **self-refreshing** HTML/SVG line chart to
  `charts/flipor_wave2_funding.html` (time on the x-axis, dollars pledged on the y-axis,
  with the $200k goal line and the full runway to the deadline).
- The chart page auto-reloads every 60s, so while snapshots are being appended it updates on its own.

## Usage

```bash
# Append a new snapshot (timestamp = now) and rebuild the chart:
python3 build.py --record --pledged 125716 --backers 386

# Just rebuild the chart from the existing log:
python3 build.py
```

Open `charts/flipor_wave2_funding.html` in any browser to view.

## How the data is collected (important)

Kickstarter **blocks scripted/direct requests** (HTTP 403) and only shows the *current* total
publicly — the full historical funding curve lives on the creator's private dashboard. So:

- Snapshots are read from the **logged-in Kickstarter session in Chrome** (not fetched by a script).
- The chart's starting origin is a **launch anchor** at $0 (campaign launched ~Oct 13 2026, 8 PM).
- **Hourly monitoring** works by reading the live total through Chrome on an interval **while a
  session is active**. It cannot run 24/7 unattended, because that requires the logged-in browser
  (a background/cloud job wouldn't have the Kickstarter login).

## Structure

- `build.py` — records snapshots and builds the chart
- `config.json` — campaign details + paths
- `data/` — the funding log (`flipor_wave2_funding_log.json`)
- `charts/` — generated chart (`flipor_wave2_funding.html`)
- `docs/` — notes

## Notes

- Standalone project — unrelated to the daily-stock-analysis work.
- Report funding figures as factual data only.
