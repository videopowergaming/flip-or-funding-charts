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


STATE_PATH = ROOT / "data" / "monitor_state.json"


def update_state(entry: dict) -> None:
    """Stamp the last-pulled date/time into the persisted state file (committed to GitHub)."""
    try:
        state = json.loads(STATE_PATH.read_text())
    except Exception:
        state = {"monitoring": {}}
    m = state.setdefault("monitoring", {})
    m["last_pulled"] = entry["timestamp"]
    m["last_pledged_usd"] = entry["pledged_usd"]
    m["last_backers"] = entry["backers"]
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


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
    update_state(entry)
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

    # x domain: start of the first day -> deadline (so daily ticks align cleanly)
    first_t = points[0][0] if points else deadline - dt.timedelta(days=34)
    t0 = dt.datetime.combine(first_t.date(), dt.time(0, 0), tzinfo=first_t.tzinfo)
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
        svg.append(f'<text x="{ML-10}" y="{y+4:.1f}" text-anchor="end" class="ylab">{_fmt_usd(v)}</text>')

    # goal line
    gy = y_px(goal)
    svg.append(f'<line x1="{ML}" y1="{gy:.1f}" x2="{W-MR}" y2="{gy:.1f}" stroke="var(--goal)" stroke-width="2" stroke-dasharray="6 5"/>')
    svg.append(f'<text x="{W-MR}" y="{gy-8:.1f}" text-anchor="end" class="goal-label">Goal {_fmt_usd(goal)}</text>')

    # x gridlines + DAILY date labels (Oct 13, 14, 15, ... Nov 17)
    n_days = (t1.date() - t0.date()).days
    # thin labels only if a day would get less than ~22px (keeps text from overlapping)
    px_per_day = plot_w / max(n_days, 1)
    label_every = max(1, int(round(22 / px_per_day))) if px_per_day < 22 else 1
    d = t0.date()
    one = dt.timedelta(days=1)
    idx = 0
    while d <= t1.date():
        tx = dt.datetime.combine(d, dt.time(0, 0), tzinfo=t0.tzinfo)
        x = x_px(tx)
        svg.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+plot_h}" stroke="var(--grid)" stroke-width="1"/>')
        if idx % label_every == 0 or d == t1.date():
            # day number on the main row
            svg.append(f'<text x="{x:.1f}" y="{MT+plot_h+20:.1f}" text-anchor="middle" class="xlab">{d.day}</text>')
            # month name on a second row, only at the first tick and each month start
            if idx == 0 or d.day == 1:
                svg.append(f'<text x="{x:.1f}" y="{MT+plot_h+38:.1f}" text-anchor="middle" class="xmonth">{d.strftime("%b")}</text>')
        d += one
        idx += 1

    # colored axis spines (y = purple, x = teal)
    svg.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{MT+plot_h}" stroke="var(--yaxis)" stroke-width="3"/>')
    svg.append(f'<line x1="{ML}" y1="{MT+plot_h}" x2="{W-MR}" y2="{MT+plot_h}" stroke="var(--xaxis)" stroke-width="3"/>')

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

    # axis titles (colored to match their axes)
    svg.append(f'<text x="{ML+plot_w/2:.1f}" y="{H-18}" text-anchor="middle" class="xtitle">Date</text>')
    svg.append(f'<text x="22" y="{MT+plot_h/2:.1f}" text-anchor="middle" class="ytitle" transform="rotate(-90 22 {MT+plot_h/2:.1f})">Dollars pledged (USD)</text>')

    svg.append("</svg>")
    return "\n".join(svg), latest, goal, deadline


def _hour_label(t: dt.datetime) -> str:
    hr = t.strftime("%I").lstrip("0") or "12"
    return f"{hr} {t.strftime('%p')}"


def render_pull_log(log: list) -> str:
    """Table listing every data pull: date & time + pledge level (newest first)."""
    if not log:
        return ""
    pts = [
        (dt.datetime.fromisoformat(e["timestamp"]), e["pledged_usd"], e["backers"])
        for e in log
    ]
    pts.sort(key=lambda p: p[0])  # chronological, to compute change
    rows = []
    for i in range(len(pts) - 1, -1, -1):  # newest first
        t, pledged, backers = pts[i]
        prev = pts[i - 1][1] if i > 0 else None
        change = "" if prev is None else f"+{_fmt_usd(pledged - prev)}"
        clock = t.strftime("%I:%M %p").lstrip("0")
        when = t.strftime("%a %b %d, %Y") + " · " + clock
        when += f' <span class="tz">{t.strftime("%Z")}</span>'
        rows.append(
            f'<tr><td>{when}</td>'
            f'<td class="r">{_fmt_usd(pledged)}</td>'
            f'<td class="r gain">{change}</td>'
            f'<td class="r">{backers:,}</td></tr>'
        )
    return f"""
    <h2 class="caltitle">Data pull log ({len(pts)} pulls)</h2>
    <table class="cal">
      <thead><tr><th>Date &amp; time</th><th class="r">Pledged</th>
        <th class="r">Change</th><th class="r">Backers</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def render_calendar(log: list) -> str:
    """Day-by-day update calendar derived from the log: shows end-of-day totals,
    daily gain, snapshots per day, and flags days with no data (time away)."""
    if not log:
        return ""
    by_day = {}
    for e in log:
        t = dt.datetime.fromisoformat(e["timestamp"])
        by_day.setdefault(t.date(), []).append((t, e["pledged_usd"], e["backers"]))

    first_day = min(by_day)
    last_day = max(by_day)
    rows = []
    prev_pledged = None
    d = first_day
    one = dt.timedelta(days=1)
    while d <= last_day:
        if d in by_day:
            snaps = sorted(by_day[d], key=lambda s: s[0])
            last_t, pledged, backers = snaps[-1]
            gain = "" if prev_pledged is None else f"+{_fmt_usd(pledged - prev_pledged)}"
            rows.append(
                f'<tr><td>{d.strftime("%a %b %d")}</td>'
                f'<td class="r">{_fmt_usd(pledged)}</td>'
                f'<td class="r gain">{gain}</td>'
                f'<td class="r">{backers:,}</td>'
                f'<td class="r">{len(snaps)}</td>'
                f'<td class="t">last {last_t.strftime("%I:%M %p")}</td></tr>'
            )
            prev_pledged = pledged
        else:
            rows.append(
                f'<tr class="gapday"><td>{d.strftime("%a %b %d")}</td>'
                f'<td class="r">—</td><td class="r">—</td><td class="r">—</td>'
                f'<td class="r">0</td><td class="t">no data (away)</td></tr>'
            )
        d += one

    return f"""
    <h2 class="caltitle">Update calendar</h2>
    <table class="cal">
      <thead><tr><th>Day</th><th class="r">Pledged (EOD)</th><th class="r">Gain</th>
        <th class="r">Backers</th><th class="r">Snaps</th><th>Last pull</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


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
        as_of = latest[0].strftime("%A, %b %d %Y · %I:%M %p %Z")
        stat_cards = f"""
        <p class="asof">As of <strong>{as_of}</strong></p>
        <div class="stats">
          <div class="stat s-pledged"><div class="num">{_fmt_usd(latest[1])}</div><div class="lbl">pledged</div></div>
          <div class="stat s-pct"><div class="num">{pct:.1f}%</div><div class="lbl">of {_fmt_usd(goal)} goal</div></div>
          <div class="stat s-backers"><div class="num">{latest[2]:,}</div><div class="lbl">backers</div></div>
          <div class="stat s-days"><div class="num">{days_left}</div><div class="lbl">days to go</div></div>
        </div>"""

    pull_log_html = render_pull_log(log) if log else ""
    calendar_html = render_calendar(log)
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
    --xaxis:#0891b2; --yaxis:#7c3aed; --xlabel:#0e7490; --ylabel:#6d28d9;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#0f141a; --fg:#e5e7eb; --muted:#9ca3af; --grid:#283039;
      --line:#60a5fa; --fill:#60a5fa; --goal:#f87171; --card:#1a222c;
      --xaxis:#22d3ee; --yaxis:#a78bfa; --xlabel:#67e8f9; --ylabel:#c4b5fd;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#0f141a; --fg:#e5e7eb; --muted:#9ca3af; --grid:#283039;
    --line:#60a5fa; --fill:#60a5fa; --goal:#f87171; --card:#1a222c;
    --xaxis:#22d3ee; --yaxis:#a78bfa; --xlabel:#67e8f9; --ylabel:#c4b5fd;
  }}
  html,body {{ background:var(--bg); color:var(--fg); margin:0;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:24px 16px 40px; }}
  h1 {{ font-size:1.35rem; margin:0 0 2px; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin:0 0 18px; }}
  .sub a {{ color:var(--line); }}
  .asof {{ font-size:.92rem; margin:0 0 12px; color:var(--fg); }}
  .asof strong {{ color:var(--line); }}
  .stats {{ display:flex; flex-wrap:wrap; gap:12px; margin:0 0 18px; }}
  .stat {{ background:var(--card); border-radius:12px; padding:14px 18px; flex:1 1 140px;
    border-left:5px solid var(--muted); }}
  .stat .num {{ font-size:1.5rem; font-weight:700; }}
  .stat .lbl {{ color:var(--muted); font-size:.8rem; margin-top:2px; }}
  .s-pledged {{ border-left-color:var(--line); }}   .s-pledged .num {{ color:var(--line); }}
  .s-pct {{ border-left-color:var(--yaxis); }}       .s-pct .num {{ color:var(--yaxis); }}
  .s-backers {{ border-left-color:var(--xaxis); }}   .s-backers .num {{ color:var(--xaxis); }}
  .s-days {{ border-left-color:var(--goal); }}       .s-days .num {{ color:var(--goal); }}
  .chart {{ width:100%; height:auto; background:var(--bg); border-radius:12px; }}
  text.xlab {{ fill:var(--xlabel); font-size:11px; font-weight:600; }}
  text.xmonth {{ fill:var(--xaxis); font-size:12px; font-weight:700; }}
  text.ylab {{ fill:var(--ylabel); font-size:12px; font-weight:600; }}
  text.xtitle {{ fill:var(--xaxis); font-size:13px; font-weight:700; }}
  text.ytitle {{ fill:var(--yaxis); font-size:13px; font-weight:700; }}
  text.goal-label {{ fill:var(--goal); font-size:12px; font-weight:600; }}
  text.callout {{ fill:var(--line); font-size:13px; font-weight:700; }}
  .caltitle {{ font-size:1.05rem; margin:28px 0 10px; }}
  .hourcap {{ font-size:.9rem; margin:6px 0 0; color:var(--fg); }}
  .hourcap strong {{ color:var(--line); }}
  .hourcap .miss {{ color:var(--goal); font-weight:600; }}
  table.cal {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
  table.cal th, table.cal td {{ padding:8px 10px; border-bottom:1px solid var(--grid); text-align:left; }}
  table.cal th {{ color:var(--muted); font-weight:600; border-bottom:2px solid var(--xaxis); }}
  table.cal td.r, table.cal th.r {{ text-align:right; }}
  table.cal td.t {{ color:var(--muted); font-size:.8rem; }}
  table.cal .tz {{ color:var(--muted); font-size:.72rem; }}
  table.cal td.gain {{ color:#16a34a; font-weight:600; }}
  table.cal tr.gapday td {{ color:var(--muted); font-style:italic; background:var(--card); }}
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
    {pull_log_html}
    {calendar_html}
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
