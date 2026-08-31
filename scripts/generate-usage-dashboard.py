#!/usr/bin/env python3
"""Generate a static, self-contained HTML dashboard from
docs/token-usage-events.jsonl (per-API-call granularity, see
hooks/archive-turn.py's append_usage_events).

Usage:
    python3 scripts/generate-usage-dashboard.py [output_path]

Defaults to writing docs/dashboard.html relative to this script's repo root.
No network access, no dependencies beyond the stdlib — reads the jsonl,
aggregates in Python, and embeds the aggregates as inline JSON in the HTML
so the page has no runtime data dependency. Re-run any time to refresh; the
output file is not meant to be committed (it's a point-in-time report, not
source), publish it as an Artifact instead when a human wants to look at it.
"""

import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(REPO_ROOT, "docs", "token-usage-events.jsonl")


def load_events(path):
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def day_of(ts):
    return (ts or "")[:10] or "unknown"


def aggregate(events):
    by_day = defaultdict(lambda: defaultdict(int))
    by_session = defaultdict(lambda: defaultdict(int))
    by_model = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(int)

    fields = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )

    for e in events:
        d = day_of(e.get("ts"))
        sid = e.get("session_id") or "unknown"
        model = e.get("model") or "unknown"
        for field in fields:
            v = e.get(field) or 0
            by_day[d][field] += v
            by_session[sid][field] += v
            by_model[model][field] += v
            totals[field] += v
        by_session[sid]["calls"] += 1
        by_model[model]["calls"] += 1
        by_session[sid]["_last_day"] = d

    return {
        "by_day": dict(sorted(by_day.items())),
        "by_session": dict(by_session),
        "by_model": dict(by_model),
        "totals": dict(totals),
        "call_count": len(events),
    }


PAGE_TEMPLATE = """<!doctype html>
<title>Token Usage Dashboard</title>
<style>
:root {{
  --bg: #f7f7f5;
  --surface: #ffffff;
  --border: #e4e2dd;
  --text: #1a1a1a;
  --text-muted: #6b6f76;
  --accent: #b3791f;
  --accent-soft: #f1dcae;
  --good: #2f8f5b;
  --warn: #c17d1f;
  --grid-line: #eceae5;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #0f1115;
    --surface: #171a20;
    --border: #262b33;
    --text: #e8e6e1;
    --text-muted: #9098a3;
    --accent: #e0a63e;
    --accent-soft: #3a2f14;
    --good: #4caf6f;
    --warn: #e0a63e;
    --grid-line: #232730;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0f1115;
  --surface: #171a20;
  --border: #262b33;
  --text: #e8e6e1;
  --text-muted: #9098a3;
  --accent: #e0a63e;
  --accent-soft: #3a2f14;
  --good: #4caf6f;
  --warn: #e0a63e;
  --grid-line: #232730;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "IBM Plex Sans", system-ui, sans-serif;
  padding: 2.5rem 1.5rem 4rem;
}}
.mono {{ font-family: "IBM Plex Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; }}
.wrap {{ max-width: 960px; margin: 0 auto; }}
h1 {{
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0 0 0.25rem;
  text-wrap: balance;
}}
.subtitle {{ color: var(--text-muted); font-size: 0.875rem; margin: 0 0 2rem; }}
.summary {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 2rem;
}}
.stat {{
  background: var(--surface);
  padding: 1rem 1.1rem;
}}
.stat .label {{
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}}
.stat .value {{ font-size: 1.35rem; font-weight: 600; }}
.stat .value.accent {{ color: var(--accent); }}
section {{ margin-bottom: 2.25rem; }}
h2 {{
  font-size: 0.95rem;
  font-weight: 600;
  margin: 0 0 0.9rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}}
h2 .hint {{ font-size: 0.75rem; font-weight: 400; color: var(--text-muted); }}
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem;
  overflow-x: auto;
}}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; min-width: 480px; }}
th, td {{ text-align: right; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--grid-line); }}
th:first-child, td:first-child {{ text-align: left; }}
th {{
  color: var(--text-muted);
  font-weight: 500;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
tr:last-child td {{ border-bottom: none; }}
.bar-cell {{ display: flex; align-items: center; gap: 0.5rem; justify-content: flex-end; }}
.bar-track {{ width: 90px; height: 6px; border-radius: 3px; background: var(--grid-line); overflow: hidden; }}
.bar-fill {{ height: 100%; background: var(--accent); border-radius: 3px; }}
.empty {{
  color: var(--text-muted);
  font-size: 0.875rem;
  padding: 2rem;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 10px;
}}
svg text {{ fill: var(--text-muted); font-size: 10px; font-family: "IBM Plex Mono", monospace; }}
.legend {{ display: flex; gap: 1rem; font-size: 0.75rem; color: var(--text-muted); margin-top: 0.6rem; flex-wrap: wrap; }}
.legend span {{ display: inline-flex; align-items: center; gap: 0.35rem; }}
.swatch {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
footer {{ margin-top: 2.5rem; font-size: 0.75rem; color: var(--text-muted); }}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<div class="wrap">
  <h1>Token Usage Dashboard</h1>
  <p class="subtitle">{generated_at} &middot; source: docs/token-usage-events.jsonl &middot; {call_count} API calls recorded</p>

  {body}

  <footer>Regenerate with <code>python3 scripts/generate-usage-dashboard.py</code> whenever new turns have landed in the jsonl.</footer>
</div>
"""

EMPTY_BODY = """
<div class="empty">No usage events recorded yet. This file fills in as
<code>hooks/archive-turn.py</code>'s Stop hook fires on future turns &mdash;
come back after a turn or two.</div>
"""


def fmt(n):
    return f"{n:,}"


def render_summary(totals, call_count, session_count, model_count):
    total_tokens = sum(totals.get(k, 0) for k in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
    ))
    stats = [
        ("Total tokens", fmt(total_tokens), True),
        ("Cache read", fmt(totals.get("cache_read_input_tokens", 0)), False),
        ("Cache creation", fmt(totals.get("cache_creation_input_tokens", 0)), False),
        ("Output", fmt(totals.get("output_tokens", 0)), False),
        ("Input", fmt(totals.get("input_tokens", 0)), False),
        ("API calls", fmt(call_count), False),
        ("Sessions", fmt(session_count), False),
        ("Models", fmt(model_count), False),
    ]
    cells = "".join(
        f'<div class="stat"><div class="label">{label}</div>'
        f'<div class="value mono{" accent" if accent else ""}">{value}</div></div>'
        for label, value, accent in stats
    )
    return f'<div class="summary">{cells}</div>'


def render_daily_chart(by_day):
    if not by_day:
        return ""
    days = list(by_day.keys())
    fields = [
        ("cache_read_input_tokens", "var(--accent-soft)", "cache read"),
        ("cache_creation_input_tokens", "var(--warn)", "cache creation"),
        ("input_tokens", "var(--good)", "input"),
        ("output_tokens", "var(--accent)", "output"),
    ]
    totals_per_day = [sum(by_day[d].get(f, 0) for f, _, _ in fields) for d in days]
    max_total = max(totals_per_day) or 1

    width, height = 900, 220
    pad_left, pad_bottom = 10, 24
    plot_w = width - pad_left - 10
    plot_h = height - pad_bottom - 10
    n = len(days)
    bar_gap = 6
    bar_w = max(6, (plot_w / n) - bar_gap)

    bars = []
    labels = []
    for i, d in enumerate(days):
        x = pad_left + i * (plot_w / n) + (plot_w / n - bar_w) / 2
        y_cursor = height - pad_bottom
        for field, color, _ in fields:
            v = by_day[d].get(field, 0)
            h = (v / max_total) * plot_h
            if h <= 0:
                continue
            y = y_cursor - h
            bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" />')
            y_cursor = y
        if n <= 14 or i % max(1, n // 14) == 0:
            label = d[5:] if len(d) == 10 else d
            labels.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - 6}" text-anchor="middle">{label}</text>')

    grid = "".join(
        f'<line x1="{pad_left}" y1="{height - pad_bottom - frac * plot_h:.1f}" '
        f'x2="{width - 10}" y2="{height - pad_bottom - frac * plot_h:.1f}" '
        f'stroke="var(--grid-line)" stroke-width="1" />'
        for frac in (0.25, 0.5, 0.75, 1.0)
    )

    legend = "".join(
        f'<span><span class="swatch" style="background:{color}"></span>{name}</span>'
        for _, color, name in fields
    )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Daily token usage by category">'
        f"{grid}{''.join(bars)}{''.join(labels)}</svg>"
    )
    return f'<section><h2>Daily trend <span class="hint">stacked by token category</span></h2><div class="card">{svg}<div class="legend">{legend}</div></div></section>'


def render_breakdown_table(title, hint, by_key, key_label):
    if not by_key:
        return ""
    rows = sorted(
        by_key.items(),
        key=lambda kv: sum(kv[1].get(f, 0) for f in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
        )),
        reverse=True,
    )
    max_total = max(
        sum(v.get(f, 0) for f in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
        ))
        for _, v in rows
    ) or 1

    trs = []
    for key, v in rows:
        total = sum(v.get(f, 0) for f in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
        ))
        pct = (total / max_total) * 100
        trs.append(
            f"<tr><td>{key}</td>"
            f'<td class="mono">{fmt(v.get("calls", 0))}</td>'
            f'<td class="mono">{fmt(v.get("input_tokens", 0))}</td>'
            f'<td class="mono">{fmt(v.get("output_tokens", 0))}</td>'
            f'<td class="mono">{fmt(v.get("cache_creation_input_tokens", 0))}</td>'
            f'<td class="mono">{fmt(v.get("cache_read_input_tokens", 0))}</td>'
            f'<td><div class="bar-cell"><span class="mono">{fmt(total)}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div></div></td></tr>'
        )

    return (
        f'<section><h2>{title} <span class="hint">{hint}</span></h2>'
        f'<div class="card"><table><thead><tr>'
        f"<th>{key_label}</th><th>calls</th><th>input</th><th>output</th>"
        f"<th>cache create</th><th>cache read</th><th>total</th>"
        f"</tr></thead><tbody>{''.join(trs)}</tbody></table></div></section>"
    )


def build_html(agg):
    if agg["call_count"] == 0:
        body = EMPTY_BODY
    else:
        by_session = {k: v for k, v in agg["by_session"].items()}
        by_model = agg["by_model"]
        body = (
            render_summary(agg["totals"], agg["call_count"], len(by_session), len(by_model))
            + render_daily_chart(agg["by_day"])
            + render_breakdown_table("By session", "most recent first isn't guaranteed; sorted by total tokens", by_session, "session")
            + render_breakdown_table("By model", "", by_model, "model")
        )

    import datetime
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return PAGE_TEMPLATE.format(generated_at=generated_at, call_count=fmt(agg["call_count"]), body=body)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_ROOT, "docs", "dashboard.html")
    events = load_events(EVENTS_PATH)
    agg = aggregate(events)
    html = build_html(agg)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path} ({agg['call_count']} events)")


if __name__ == "__main__":
    main()
