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

1. [~] **Move GAME's test/verification suite to CI** — PR open:
   https://github.com/xilitol111/GAME/pull/7 (draft, watched)
   Write access confirmed 2026-08-23 (GAME/kakeibo/kakeibo-liff all added
   with `access: push`). Phase 1 investigation (2026-08-23) found the
   original scoping was wrong: GAME has **no committed automated test
   suite** at all — `npm test` doesn't exist, and no vitest/playwright
   dependency is in `package.json`. The "60-120 randomized playouts +
   Playwright smoke tests" mentioned below were run ad hoc inside Claude
   Code sessions, never committed as test code, so there was nothing for
   CI to pick up and run. Scope narrowed to what actually exists: PR #7
   adds `.github/workflows/ci.yml` running `npm ci` + `npm run build` +
   `npm run lint` on PRs/pushes (both verified green locally before push).
   Committing an actual test suite (the random-playout script, a
   Playwright smoke test) so CI has something beyond build+lint to run is
   a separate, not-yet-started follow-up — see item 1b below.
   Also found not to generalize: **kakeibo has no root `package.json`**
   (GAS + Supabase Edge Functions + SQL migrations, no npm project) and
   **kakeibo-liff has no build system at all** (static HTML files, no
   package.json). Neither fits an npm-based reusable CI workflow; each
   needs its own separate design if/when picked up. User decided
   2026-08-23 to proceed with GAME only for now.

1b. [ ] **Commit an actual test suite for GAME** (blocks CI from covering
    more than build+lint)
    Turn the ad hoc "60-120 randomized playouts" and Playwright smoke
    checks that have been run inline in sessions into real committed test
    files (e.g. a `scripts/random-playout.ts` + a `tests/` dir with a
    Playwright config), then add a corresponding step to PR #7's
    `ci.yml`. Not started; no test framework dependency exists in
    `package.json` yet.

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
