#!/usr/bin/env python3
"""Flip-Or Funding Charts — time vs. dollars-backed chart builder.

Tracks the Kickstarter campaign "FLIP-OR and the CHAMPIONS of NEFARITY - WAVE 2!!"
by logging timestamped funding snapshots and rendering a dependency-free,
self-refreshing HTML/SVG line chart of pledged dollars over time.

Usage:
    # Append a new snapshot (timestamp = now) and rebuild the chart:
    python3 build.py --record --pledged 125716 --backers 386

    # Just rebuild the chart from the existing log:
    python3 build.py

The chart auto-refreshes in the browser (default every 60s), so if snapshots are
being appended while it's open, it updates on its own. Kickstarter blocks scripted
requests, so snapshots are read from the logged-in browser session, not fetched here.
"""

import argparse
import datetime as dt
import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())
CAMP = CONFIG["campaign"]
LOG_PATH = ROOT / CAMP["funding_log"]
CHART_PATH = ROOT / CONFIG["charts_dir"] / "flipor_wave2_funding.html"
REFRESH_SECONDS = 60


def load_log() -> list:
    if LOG_PATH.exists():
        return json.loads(LOG_PATH.read_text())
    return []


def save_log(log: list) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2))


def record(pledged: float, backers: int) -> list:
    log = load_log()
    now = dt.datetime.now(dt.timezone.utc).astimezone()
    entry = {
        "timestamp": now.isoformat(timespec="seconds"),
        "pledged_usd": float(pledged),
        "backers": int(backers),
    }
    # De-dupe: if the last entry has identical pledged+backers, just refresh its time.
    if log and log[-1]["pledged_usd"] == entry["pledged_usd"] and log[-1]["backers"] == entry["backers"]:
        log[-1]["timestamp"] = entry["timestamp"]
    else:
        log.append(entry)
    save_log(log)
    return log


def _fmt_usd(v: float) -> str:
    return "${:,.0f}".format(v)


def render_chart(log: list) -> str:
    goal = float(CAMP["goal_usd"])
    deadline = dt.datetime.fromisoformat(CAMP["deadline"])
    points = [
        (dt.datetime.fromisoformat(e["timestamp"]), e["pledged_usd"], e["backers"])
        for e in log
    ]
    points.sort(key=lambda p: p[0])

    # --- chart geometry ---
    W, H = 960, 540
    ML, MR, MT, MB = 90, 40, 70, 70
    plot_w, plot_h = W - ML - MR, H - MT - MB

    # x domain: first snapshot -> deadline (so the goal/time runway is visible)
    t0 = points[0][0] if points else deadline - dt.timedelta(days=34)
    t1 = deadline
    if t1 <= t0:
        t1 = t0 + dt.timedelta(days=1)
    span = (t1 - t0).total_seconds()

    # y domain: 0 -> a bit above max(goal, pledged)
    max_pledged = max([p[1] for p in points], default=0)
    y_max = max(goal, max_pledged) * 1.1
    y_max = max(y_max, 1)

    def x_px(t):
        return ML + plot_w * ((t - t0).total_seconds() / span)

    def y_px(v):
        return MT + plot_h * (1 - v / y_max)

    latest = points[-1] if points else None

    svg = []
    svg.append(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" class="chart">')
    svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="var(--bg)"/>')

    # y gridlines + labels ($)
    steps = 5
    for i in range(steps + 1):
        v = y_max * i / steps
        y = y_px(v)
        svg.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W-MR}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        svg.append(f'<text x="{ML-10}" y="{y+4:.1f}" text-anchor="end" class="axis">{_fmt_usd(v)}</text>')

    # goal line
    gy = y_px(goal)
    svg.append(f'<line x1="{ML}" y1="{gy:.1f}" x2="{W-MR}" y2="{gy:.1f}" stroke="var(--goal)" stroke-width="2" stroke-dasharray="6 5"/>')
    svg.append(f'<text x="{W-MR}" y="{gy-8:.1f}" text-anchor="end" class="goal-label">Goal {_fmt_usd(goal)}</text>')

    # x gridlines + date labels (up to 6 ticks across the window)
    xticks = 6
    for i in range(xticks + 1):
        t = t0 + dt.timedelta(seconds=span * i / xticks)
        x = x_px(t)
        svg.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+plot_h}" stroke="var(--grid)" stroke-width="1"/>')
        svg.append(f'<text x="{x:.1f}" y="{MT+plot_h+22:.1f}" text-anchor="middle" class="axis">{t.strftime("%b %d")}</text>')

    # funding line + area
    if len(points) >= 2:
        pts = " ".join(f"{x_px(t):.1f},{y_px(v):.1f}" for t, v, _ in points)
        area = f"{x_px(points[0][0]):.1f},{y_px(0):.1f} " + pts + f" {x_px(points[-1][0]):.1f},{y_px(0):.1f}"
        svg.append(f'<polygon points="{area}" fill="var(--fill)" opacity="0.18"/>')
        svg.append(f'<polyline points="{pts}" fill="none" stroke="var(--line)" stroke-width="3" stroke-linejoin="round"/>')
    for t, v, _ in points:
        svg.append(f'<circle cx="{x_px(t):.1f}" cy="{y_px(v):.1f}" r="4" fill="var(--line)"/>')

    # latest marker callout
    if latest:
        lx, lv = x_px(latest[0]), y_px(latest[1])
        svg.append(f'<circle cx="{lx:.1f}" cy="{lv:.1f}" r="6" fill="var(--line)" stroke="var(--bg)" stroke-width="2"/>')
        svg.append(f'<text x="{lx-10:.1f}" y="{lv-12:.1f}" text-anchor="end" class="callout">{_fmt_usd(latest[1])}</text>')

    # axis titles
    svg.append(f'<text x="{ML+plot_w/2:.1f}" y="{H-18}" text-anchor="middle" class="axis-title">Date</text>')
    svg.append(f'<text x="22" y="{MT+plot_h/2:.1f}" text-anchor="middle" class="axis-title" transform="rotate(-90 22 {MT+plot_h/2:.1f})">Dollars pledged (USD)</text>')

    svg.append("</svg>")
    return "\n".join(svg), latest, goal, deadline


def build(log: list) -> None:
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().astimezone()

    if not log:
        chart_svg = '<p class="empty">No funding snapshots logged yet. Run <code>build.py --record --pledged N --backers N</code>.</p>'
        latest = None
        goal = float(CAMP["goal_usd"])
        deadline = dt.datetime.fromisoformat(CAMP["deadline"])
    else:
        chart_svg, latest, goal, deadline = render_chart(log)

    days_left = (deadline - now).days
    pct = (latest[1] / goal * 100) if latest else 0
    stat_cards = ""
    if latest:
        stat_cards = f"""
        <div class="stats">
          <div class="stat"><div class="num">{_fmt_usd(latest[1])}</div><div class="lbl">pledged</div></div>
          <div class="stat"><div class="num">{pct:.1f}%</div><div class="lbl">of {_fmt_usd(goal)} goal</div></div>
          <div class="stat"><div class="num">{latest[2]:,}</div><div class="lbl">backers</div></div>
          <div class="stat"><div class="num">{days_left}</div><div class="lbl">days to go</div></div>
        </div>"""

    title = html.escape(CAMP["name"])
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>Flip-Or Wave 2 — Funding Over Time</title>
<style>
  :root {{
    --bg:#ffffff; --fg:#111827; --muted:#6b7280; --grid:#e5e7eb;
    --line:#2563eb; --fill:#2563eb; --goal:#dc2626; --card:#f3f4f6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0f141a; --fg:#e5e7eb; --muted:#9ca3af; --grid:#283039;
      --line:#60a5fa; --fill:#60a5fa; --goal:#f87171; --card:#1a222c;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0f141a; --fg:#e5e7eb; --muted:#9ca3af; --grid:#283039;
    --line:#60a5fa; --fill:#60a5fa; --goal:#f87171; --card:#1a222c;
  }}
  html,body {{ background:var(--bg); color:var(--fg); margin:0;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:24px 16px 40px; }}
  h1 {{ font-size:1.35rem; margin:0 0 2px; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin:0 0 18px; }}
  .sub a {{ color:var(--line); }}
  .stats {{ display:flex; flex-wrap:wrap; gap:12px; margin:0 0 18px; }}
  .stat {{ background:var(--card); border-radius:12px; padding:14px 18px; flex:1 1 140px; }}
  .stat .num {{ font-size:1.5rem; font-weight:700; }}
  .stat .lbl {{ color:var(--muted); font-size:.8rem; margin-top:2px; }}
  .chart {{ width:100%; height:auto; background:var(--bg); border-radius:12px; }}
  text.axis {{ fill:var(--muted); font-size:12px; }}
  text.axis-title {{ fill:var(--fg); font-size:13px; font-weight:600; }}
  text.goal-label {{ fill:var(--goal); font-size:12px; font-weight:600; }}
  text.callout {{ fill:var(--line); font-size:13px; font-weight:700; }}
  .empty {{ color:var(--muted); padding:40px; text-align:center; }}
  .foot {{ color:var(--muted); font-size:.78rem; margin-top:16px; }}
  .live {{ display:inline-block; width:8px; height:8px; border-radius:50%;
    background:#16a34a; margin-right:6px; vertical-align:middle;
    animation:pulse 1.6s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.3}} }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>{title}</h1>
    <p class="sub">by {html.escape(CAMP['creator'])} ·
      <a href="{html.escape(CAMP['url'])}" target="_blank" rel="noopener">View on Kickstarter</a></p>
    {stat_cards}
    {chart_svg}
    <p class="foot"><span class="live"></span>Auto-refreshes every {REFRESH_SECONDS}s ·
      {len(log)} snapshot(s) logged · last built {now.strftime('%Y-%m-%d %H:%M %Z')} ·
      deadline {deadline.strftime('%b %d %Y %I:%M %p %Z')}</p>
  </div>
</body>
</html>"""
    CHART_PATH.write_text(page)
    print(f"Chart written: {CHART_PATH}  ({len(log)} snapshot(s))")


def main() -> None:
    ap = argparse.ArgumentParser(description="Flip-Or Wave 2 funding chart builder")
    ap.add_argument("--record", action="store_true", help="append a snapshot (timestamp = now)")
    ap.add_argument("--pledged", type=float, help="current pledged USD (with --record)")
    ap.add_argument("--backers", type=int, help="current backer count (with --record)")
    args = ap.parse_args()

    if args.record:
        if args.pledged is None or args.backers is None:
            ap.error("--record requires --pledged and --backers")
        log = record(args.pledged, args.backers)
        print(f"Recorded: {_fmt_usd(args.pledged)}, {args.backers} backers")
    else:
        log = load_log()
    build(log)


if __name__ == "__main__":
    main()
