# Token consumption follow-ups (from 2026-08-22 usage investigation)

Source session: `claude/token-consumption-optimization-azrovw` (PR #8). Full
analysis (segment breakdown, repo-size cross-check, root-cause split) lives in
that session's `docs/session-archive.md` entries and the published Artifact
("トークン消費スナップショット") — this file is the actionable TODO extract, not
a re-derivation. Read those only if the reasoning behind an item below is
actually needed.

## Status legend
- [ ] not started
- Items needing write access to `xilitol111/GAME` or `xilitol111/kakeibo`
  are marked **(needs app-repo write access)** — this repo (app-governance)
  only has read access to both as of 2026-08-22.

## Items, priority order

1. [ ] **Move GAME's test/verification suite to CI** **(needs app-repo write access)**
   GAME has no CI configured; build/lint/tsc + 60-120 randomized playouts +
   Playwright smoke tests currently run inline inside Claude Code sessions
   every batch, and that output stays in the conversation transcript for the
   rest of the session (re-read, at cost, every subsequent turn). Tool-heavy
   turns were measured at ~3x the token cost of plain conversational turns
   (see archive-turn.py's own docstring investigation). Moving verification
   to GitHub Actions means Claude pushes and checks a pass/fail result
   instead of keeping the full test output in-context. Highest estimated
   impact, moderate setup effort (CI workflow authoring + verifying it
   actually replaces, not just duplicates, the inline runs).

2. [ ] **Code a PR-merge-boundary `/clear` nudge, mirroring the five-hour
   notification mechanism** (this repo, `hooks/archive-turn.py`)
   Root cause of the single largest segment found (2.42億 tokens, 38% of
   GAME's 8/22 total): a session ran through a PR merge into the next batch
   with no `/clear`. Same mechanism as the existing `THRESHOLD_TOKENS`
   interval nudge — detect a `merge_pull_request` (or equivalent) tool call
   in the transcript, and on the next Stop hook after it, surface a
   `decision:"block"` reason once suggesting `/clear`/`/compact` via
   AskUserQuestion, instead of leaving this purely to CLAUDE.md prose that
   evidently isn't always followed in practice. High impact, low effort,
   stays inside this repo.

3. [ ] **Actually split kakeibo's CLAUDE.md** **(needs app-repo write access)**
   kakeibo's `CLAUDE.md` is 1,889 lines / 203,913 bytes; only the first ~131
   lines are current-state reference, the remaining ~93% is a dated
   changelog (2026-08-06 through 2026-08-16 entries) that should live in a
   separate `docs/DEVLOG.md` per this repo's own hygiene rule. This is the
   exact anti-pattern GAME was earlier (incorrectly) recorded as having
   already fixed — GAME's CLAUDE.md is actually fine (250 lines, current-
   state only); kakeibo is the one that's actually bloated and unaddressed.
   Rough estimate: cuts kakeibo's per-turn fixed system-prompt cost by an
   order of magnitude. Mechanical, low-risk, high impact.

4. [ ] **Pre-emptively split GAME's own CLAUDE.md before it bloats**
   Not urgent yet (still lean), but the "Known simplifications" section is
   already accumulating dated batch-completion narrative (batch 4, 5a,
   5b-i...). Carve out a `docs/DEVLOG.md` (or a `docs/roadmap-log.md`) for
   batch-completion write-ups now, before it grows into kakeibo's problem.

5. [ ] **Confirm the governance hooks are actually live in kakeibo sessions**
   kakeibo's repo currently has no `docs/five-hour-samples.jsonl` and no
   `docs/session-archive.md` at all, unlike GAME. Unconfirmed whether this
   is because no kakeibo session has run since the hook mechanism went live
   account-wide, or because something about that environment/session setup
   isn't invoking the hooks against this repo's working directory. Needs
   checking the next time actual work happens in kakeibo — if hooks aren't
   firing there, kakeibo usage stays invisible to all of the above analysis
   indefinitely.

6. [ ] **Re-check the segment-4-shaped anomaly once session_id data accumulates**
   GAME's 8/22 segment 4 (12:52-13:23) showed a ~10x-higher growth rate than
   every other segment (+1.05億 tokens in the first 10 minutes) — suspected
   to be a resumed session's pre-existing transcript history getting counted
   in one lump at the hook's first sample of it, rather than genuinely new
   generation. The `session_id` field added in PR #8 is what makes this
   checkable; revisit once a few days of samples with that field exist.

## Not on this list (already done / already tracked elsewhere)

- `session_id` field + standardized usage-analysis report format — shipped,
  PR #8 (merge status: check `list_pull_requests` if picking this up cold).
- five-hour notification threshold, `/clear` vs `/compact` guidance, the
  5-hour-anchor Routine — pre-existing, documented in this repo's
  `CLAUDE.md`/`README.md` already, not new from this investigation.
