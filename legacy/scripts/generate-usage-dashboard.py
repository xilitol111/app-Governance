#!/usr/bin/env python3
"""Generate a static, self-contained HTML dashboard from
docs/token-usage-events.jsonl (per-API-call granularity, see
legacy/hooks/archive-turn.py's append_usage_events).

Usage:
    python3 legacy/scripts/generate-usage-dashboard.py [output_path] [events_path]

Defaults to writing docs/dashboard.html relative to this script's repo root,
reading docs/token-usage-events.jsonl from that same repo root. Pass
events_path explicitly to read from elsewhere instead — e.g. a local
machine's ~/.claude/governance-usage-mirror/docs/token-usage-events.jsonl,
when that's a separate clone from wherever this script itself lives.
No network access, no dependencies beyond the stdlib. The Python side only
pre-aggregates raw events down to one row per (day, session, model) — small
enough to embed as inline JSON — and ships that to the page; all further
rollup (day/week/month bucketing, group-by session/model, column sort) runs
client-side in vanilla JS so the same static file supports interactive
filtering with no server and no re-generation per view. Re-run any time to
refresh with newer data; the output file is not meant to be committed (it's
a point-in-time report, not source) — publish it as an Artifact when someone
wants to look. Collection itself (docs/token-usage-events.jsonl, committed
every turn) is the durable record; this dashboard is a read-only convenience
view on top of it, not where the data lives.
"""

import datetime
import json
import os
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(REPO_ROOT, "docs", "token-usage-events.jsonl")

METRICS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


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


def build_rows(events):
    """One row per (day, session_id, model, project), each metric summed.
    This is the finest grain the dashboard needs client-side — day-level,
    since week/month are just coarser client-side re-bucketings of the same
    rows. `project` defaults to "unknown" for rows recorded before that
    field existed (2026-08-31) or from a source that never set it.
    """
    buckets = defaultdict(lambda: defaultdict(int))
    for e in events:
        key = (
            day_of(e.get("ts")),
            e.get("session_id") or "unknown",
            e.get("model") or "unknown",
            e.get("project") or "unknown",
        )
        b = buckets[key]
        for m in METRICS:
            b[m] += e.get(m) or 0
        b["calls"] += 1

    rows = []
    for (day, session_id, model, project), b in sorted(buckets.items()):
        row = {"day": day, "session_id": session_id, "model": model, "project": project, "calls": b["calls"]}
        row.update({m: b[m] for m in METRICS})
        rows.append(row)
    return rows


PAGE_TEMPLATE = """<!doctype html>
<title>トークン利用ダッシュボード</title>
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
    --bg: #0f1115; --surface: #171a20; --border: #262b33; --text: #e8e6e1;
    --text-muted: #9098a3; --accent: #e0a63e; --accent-soft: #3a2f14;
    --good: #4caf6f; --warn: #e0a63e; --grid-line: #232730;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0f1115; --surface: #171a20; --border: #262b33; --text: #e8e6e1;
  --text-muted: #9098a3; --accent: #e0a63e; --accent-soft: #3a2f14;
  --good: #4caf6f; --warn: #e0a63e; --grid-line: #232730;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Noto Sans JP", "IBM Plex Sans", system-ui, sans-serif;
  padding: 2.5rem 1.5rem 4rem;
}}
.mono {{ font-family: "IBM Plex Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; }}
.wrap {{ max-width: 980px; margin: 0 auto; }}
h1 {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -0.01em; margin: 0 0 0.25rem; text-wrap: balance; }}
.subtitle {{ color: var(--text-muted); font-size: 0.8rem; margin: 0 0 1.75rem; }}
.summary {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 2rem;
}}
.stat {{ background: var(--surface); padding: 0.9rem 1.05rem; }}
.stat .label {{ font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.3rem; }}
.stat .value {{ font-size: 1.3rem; font-weight: 700; }}
.stat .value.accent {{ color: var(--accent); }}
section {{ margin-bottom: 2.25rem; }}
h2 {{ font-size: 0.95rem; font-weight: 700; margin: 0 0 0.9rem; display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }}
h2 .hint {{ font-size: 0.75rem; font-weight: 400; color: var(--text-muted); }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; overflow-x: auto; }}
.controls {{ display: flex; gap: 1.25rem; flex-wrap: wrap; margin-bottom: 1rem; align-items: center; }}
.control-group {{ display: flex; align-items: center; gap: 0.5rem; }}
.control-group .cg-label {{ font-size: 0.75rem; color: var(--text-muted); }}
.seg {{ display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
.seg button {{
  font-family: inherit; font-size: 0.8rem; padding: 0.35rem 0.75rem; border: none;
  background: var(--surface); color: var(--text); cursor: pointer; border-right: 1px solid var(--border);
}}
.seg button:last-child {{ border-right: none; }}
.seg button.active {{ background: var(--accent); color: #1a1305; font-weight: 600; }}
.seg button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: -2px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; min-width: 520px; }}
th, td {{ text-align: right; padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--grid-line); }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ color: var(--text-muted); font-weight: 500; font-size: 0.7rem; cursor: pointer; user-select: none; white-space: nowrap; }}
th:hover {{ color: var(--text); }}
th .arrow {{ font-size: 0.65rem; margin-left: 0.15rem; opacity: 0.6; }}
tr:last-child td {{ border-bottom: none; }}
.bar-cell {{ display: flex; align-items: center; gap: 0.5rem; justify-content: flex-end; }}
.bar-track {{ width: 80px; height: 6px; border-radius: 3px; background: var(--grid-line); overflow: hidden; flex: none; }}
.bar-fill {{ height: 100%; background: var(--accent); border-radius: 3px; }}
.empty {{ color: var(--text-muted); font-size: 0.875rem; padding: 2rem; text-align: center; border: 1px dashed var(--border); border-radius: 10px; }}
svg text {{ fill: var(--text-muted); font-size: 10px; font-family: "IBM Plex Mono", monospace; }}
.legend {{ display: flex; gap: 1rem; font-size: 0.75rem; color: var(--text-muted); margin-top: 0.6rem; flex-wrap: wrap; }}
.legend span {{ display: inline-flex; align-items: center; gap: 0.35rem; }}
.swatch {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}
footer {{ margin-top: 2.5rem; font-size: 0.75rem; color: var(--text-muted); }}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<div class="wrap">
  <h1>トークン利用ダッシュボード</h1>
  <p class="subtitle">生成日時 {generated_at} ・ データ元: docs/token-usage-events.jsonl ・ 記録済みAPI呼び出し数 {call_count}件</p>
  <div id="app"></div>
  <footer>最新の状態にするには <code>python3 legacy/scripts/generate-usage-dashboard.py</code> を再実行してください。実データの保管場所は docs/token-usage-events.jsonl 本体で、このダッシュボードはその上に載る閲覧用のおまけです。</footer>
</div>
<script>
const ROWS = {rows_json};
const METRICS = ["cache_read_input_tokens", "cache_creation_input_tokens", "input_tokens", "output_tokens"];
const METRIC_LABELS = {{
  cache_read_input_tokens: "キャッシュ読込",
  cache_creation_input_tokens: "キャッシュ作成",
  input_tokens: "入力",
  output_tokens: "出力",
}};
const METRIC_COLORS = {{
  cache_read_input_tokens: "var(--accent-soft)",
  cache_creation_input_tokens: "var(--warn)",
  input_tokens: "var(--good)",
  output_tokens: "var(--accent)",
}};

function totalOf(row) {{ return METRICS.reduce((s, m) => s + (row[m] || 0), 0); }}
function fmt(n) {{ return n.toLocaleString("ja-JP"); }}

function isoWeekStart(dayStr) {{
  const d = new Date(dayStr + "T00:00:00Z");
  const day = (d.getUTCDay() + 6) % 7; // Monday = 0
  d.setUTCDate(d.getUTCDate() - day);
  return d.toISOString().slice(0, 10);
}}
function periodKey(day, period) {{
  if (period === "day") return day;
  if (period === "week") return isoWeekStart(day) + "週";
  if (period === "month") return day.slice(0, 7);
  return day;
}}

function aggregateByPeriod(rows, period) {{
  const buckets = new Map();
  for (const r of rows) {{
    const key = periodKey(r.day, period);
    if (!buckets.has(key)) {{
      const b = {{ key }};
      for (const m of METRICS) b[m] = 0;
      buckets.set(key, b);
    }}
    const b = buckets.get(key);
    for (const m of METRICS) b[m] += r[m] || 0;
  }}
  return [...buckets.values()].sort((a, b) => a.key < b.key ? -1 : 1);
}}

function aggregateByGroup(rows, groupField) {{
  const buckets = new Map();
  for (const r of rows) {{
    const key = groupField ? r[groupField] : "全体";
    if (!buckets.has(key)) {{
      const b = {{ key, calls: 0 }};
      for (const m of METRICS) b[m] = 0;
      buckets.set(key, b);
    }}
    const b = buckets.get(key);
    b.calls += r.calls || 0;
    for (const m of METRICS) b[m] += r[m] || 0;
  }}
  return [...buckets.values()];
}}

function renderChart(buckets) {{
  if (!buckets.length) return "";
  const width = 900, height = 220, padLeft = 10, padBottom = 24;
  const plotW = width - padLeft - 10, plotH = height - padBottom - 10;
  const n = buckets.length;
  const barGap = 6;
  const barW = Math.max(4, (plotW / n) - barGap);
  const maxTotal = Math.max(...buckets.map(b => METRICS.reduce((s, m) => s + b[m], 0)), 1);

  let bars = "", labels = "";
  const labelStride = Math.max(1, Math.ceil(n / 14));
  buckets.forEach((b, i) => {{
    const x = padLeft + i * (plotW / n) + (plotW / n - barW) / 2;
    let yCursor = height - padBottom;
    for (const m of METRICS) {{
      const v = b[m] || 0;
      const h = (v / maxTotal) * plotH;
      if (h <= 0) continue;
      const y = yCursor - h;
      bars += `<rect x="${{x.toFixed(1)}}" y="${{y.toFixed(1)}}" width="${{barW.toFixed(1)}}" height="${{h.toFixed(1)}}" fill="${{METRIC_COLORS[m]}}" />`;
      yCursor = y;
    }}
    if (i % labelStride === 0) {{
      const label = b.key.length > 8 ? b.key.slice(5) : b.key;
      labels += `<text x="${{(x + barW / 2).toFixed(1)}}" y="${{height - 6}}" text-anchor="middle">${{label}}</text>`;
    }}
  }});

  const grid = [0.25, 0.5, 0.75, 1.0].map(frac =>
    `<line x1="${{padLeft}}" y1="${{(height - padBottom - frac * plotH).toFixed(1)}}" x2="${{width - 10}}" y2="${{(height - padBottom - frac * plotH).toFixed(1)}}" stroke="var(--grid-line)" stroke-width="1" />`
  ).join("");

  const legend = METRICS.map(m =>
    `<span><span class="swatch" style="background:${{METRIC_COLORS[m]}}"></span>${{METRIC_LABELS[m]}}</span>`
  ).join("");

  return `<div class="card"><svg viewBox="0 0 ${{width}} ${{height}}" width="100%" height="${{height}}" role="img" aria-label="期間別トークン使用量">${{grid}}${{bars}}${{labels}}</svg><div class="legend">${{legend}}</div></div>`;
}}

function renderTable(groupRows, keyLabel, sortField, sortDir) {{
  if (!groupRows.length) return '<div class="empty">データがありません。</div>';
  const withTotal = groupRows.map(r => ({{ ...r, total: totalOf(r) }}));
  withTotal.sort((a, b) => {{
    const av = a[sortField], bv = b[sortField];
    const cmp = typeof av === "string" ? av.localeCompare(bv) : av - bv;
    return sortDir === "asc" ? cmp : -cmp;
  }});
  const maxTotal = Math.max(...withTotal.map(r => r.total), 1);
  const cols = [
    ["key", keyLabel], ["calls", "呼出数"], ["input_tokens", "入力"], ["output_tokens", "出力"],
    ["cache_creation_input_tokens", "キャッシュ作成"], ["cache_read_input_tokens", "キャッシュ読込"], ["total", "合計"],
  ];
  const thead = cols.map(([field, label]) => {{
    const arrow = sortField === field ? `<span class="arrow">${{sortDir === "asc" ? "▲" : "▼"}}</span>` : "";
    return `<th data-field="${{field}}">${{label}}${{arrow}}</th>`;
  }}).join("");
  const rows = withTotal.map(r => {{
    const pct = (r.total / maxTotal) * 100;
    return `<tr><td>${{r.key}}</td><td class="mono">${{fmt(r.calls)}}</td>` +
      `<td class="mono">${{fmt(r.input_tokens)}}</td><td class="mono">${{fmt(r.output_tokens)}}</td>` +
      `<td class="mono">${{fmt(r.cache_creation_input_tokens)}}</td><td class="mono">${{fmt(r.cache_read_input_tokens)}}</td>` +
      `<td><div class="bar-cell"><span class="mono">${{fmt(r.total)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{pct.toFixed(1)}}%"></div></div></div></td></tr>`;
  }}).join("");
  return `<table><thead><tr>${{thead}}</tr></thead><tbody>${{rows}}</tbody></table>`;
}}

const state = {{ period: "day", group: "project", sortField: "total", sortDir: "desc" }};

function seg(idAttr, options, current) {{
  const btns = options.map(([val, label]) =>
    `<button data-${{idAttr}}="${{val}}" class="${{val === current ? "active" : ""}}">${{label}}</button>`
  ).join("");
  return `<div class="seg">${{btns}}</div>`;
}}

function render() {{
  const app = document.getElementById("app");
  if (!ROWS.length) {{
    app.innerHTML = '<div class="empty">まだ記録されたデータがありません。legacy/hooks/archive-turn.py のStopフックが今後のターンで発火するたびに蓄積されます。数ターン後に再生成してください。</div>';
    return;
  }}

  const totalAll = ROWS.reduce((s, r) => s + totalOf(r), 0);
  const totalsByMetric = {{}};
  for (const m of METRICS) totalsByMetric[m] = ROWS.reduce((s, r) => s + (r[m] || 0), 0);
  const sessionCount = new Set(ROWS.map(r => r.session_id)).size;
  const modelCount = new Set(ROWS.map(r => r.model)).size;
  const callCount = ROWS.reduce((s, r) => s + r.calls, 0);

  const summary = `<div class="summary">` + [
    ["合計トークン", fmt(totalAll), true],
    ["キャッシュ読込", fmt(totalsByMetric.cache_read_input_tokens), false],
    ["キャッシュ作成", fmt(totalsByMetric.cache_creation_input_tokens), false],
    ["出力", fmt(totalsByMetric.output_tokens), false],
    ["入力", fmt(totalsByMetric.input_tokens), false],
    ["API呼出数", fmt(callCount), false],
    ["セッション数", fmt(sessionCount), false],
    ["モデル数", fmt(modelCount), false],
  ].map(([label, value, accent]) =>
    `<div class="stat"><div class="label">${{label}}</div><div class="value mono${{accent ? " accent" : ""}}">${{value}}</div></div>`
  ).join("") + `</div>`;

  const periodBuckets = aggregateByPeriod(ROWS, state.period);
  const chartSection = `<section><h2>推移 <span class="hint">トークン種別ごとの積み上げ</span></h2>` +
    `<div class="controls"><div class="control-group"><span class="cg-label">期間</span>${{seg("period", [["day","日次"],["week","週次"],["month","月間"]], state.period)}}</div></div>` +
    renderChart(periodBuckets) + `</section>`;

  const GROUP_LABELS = {{ session_id: "セッション", model: "モデル", project: "プロジェクト" }};
  const groupLabel = GROUP_LABELS[state.group] || "";
  const groupRows = aggregateByGroup(ROWS, state.group === "none" ? null : state.group);
  const tableSection = `<section><h2>内訳 <span class="hint">列見出しクリックで並び替え</span></h2>` +
    `<div class="controls"><div class="control-group"><span class="cg-label">グループ</span>${{seg("group", [["project","プロジェクト別"],["session_id","セッション別"],["model","モデル別"],["none","全体"]], state.group)}}</div></div>` +
    `<div class="card">${{renderTable(groupRows, groupLabel || "区分", state.sortField, state.sortDir)}}</div></section>`;

  app.innerHTML = summary + chartSection + tableSection;

  app.querySelectorAll("[data-period]").forEach(b => b.addEventListener("click", () => {{ state.period = b.dataset.period; render(); }}));
  app.querySelectorAll("[data-group]").forEach(b => b.addEventListener("click", () => {{ state.group = b.dataset.group; render(); }}));
  app.querySelectorAll("th[data-field]").forEach(th => th.addEventListener("click", () => {{
    const field = th.dataset.field;
    if (state.sortField === field) {{ state.sortDir = state.sortDir === "asc" ? "desc" : "asc"; }}
    else {{ state.sortField = field; state.sortDir = "desc"; }}
    render();
  }}));
}}

render();
</script>
"""


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_ROOT, "docs", "dashboard.html")
    events_path = sys.argv[2] if len(sys.argv) > 2 else EVENTS_PATH
    events = load_events(events_path)
    rows = build_rows(events)
    call_count = sum(r["calls"] for r in rows)

    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = PAGE_TEMPLATE.format(
        generated_at=generated_at,
        call_count=f"{call_count:,}",
        rows_json=json.dumps(rows, ensure_ascii=False),
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path} ({call_count} events, {len(rows)} rows)")


if __name__ == "__main__":
    main()
