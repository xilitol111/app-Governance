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

1. [x] **Move GAME's test/verification suite to CI** — merged 2026-08-23:
   https://github.com/xilitol111/GAME/pull/7
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

2. [x] **Code a PR-merge-boundary `/clear` nudge, mirroring the five-hour
   notification mechanism** (this repo, `hooks/archive-turn.py`) — done
   2026-08-23. Added `find_last_successful_merge` + `maybe_notify_pr_merge`:
   detects a successful `mcp__github__merge_pull_request` tool call in the
   transcript and fires a one-time-per-merge `decision:"block"` reason (deduped
   via a `/tmp/.pr-merge-notified-{session_id}` marker, same pattern as the
   five-hour interval nudge) suggesting `/clear`/`/compact` via
   AskUserQuestion. Combined with the interval nudge's reason text (joined
   with `\n\n`) if both fire on the same turn, since a Stop hook only gets one
   `reason` field. Unit-verified locally with a synthetic transcript
   (dedup + error-case suppression both confirmed) — not yet observed live
   against a real merge in this session.

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

5. [x] **Confirm the governance hooks are actually live in kakeibo sessions**
   — confirmed 2026-08-31: `xilitol111/kakeibo`'s `docs/` now has both
   `five-hour-samples.jsonl` and `session-archive.md` (checked via
   `get_file_contents`), so the hooks are firing there. Root cause of the
   earlier gap was simply "no kakeibo session had run yet since the
   mechanism went live", not a broken hook. Also confirmed only one
   Claude Code environment exists on this account (`kakeibo`,
   `env_01CH8G8RmBJwUGCWuLdsJFGj`) and it already carries the
   self-healing Setup Script (see README's "仕組み" section) that
   re-registers SessionStart/Stop/SessionEnd hooks into
   `~/.claude/settings.json` every session regardless of which repo's
   directory that session is working in — so enforcement across "any
   session" is structurally already satisfied as long as future sessions
   keep using this one environment. The one live dependency: a session
   only picks up new hook logic (e.g. item 6 below's
   `token-usage-events.jsonl` collection, added 2026-08-31) once
   `session-start.sh`'s per-session `curl` re-fetch pulls it from this
   repo's `main` — i.e. only after the PR carrying that change is merged.

6. [x] **Per-API-call token usage collection + dashboard** — added
   2026-08-31, PR #12. `hooks/archive-turn.py` now also appends
   `docs/token-usage-events.jsonl`, one row per actual API call
   (assistant `message.id`) with its own `input_tokens`/`output_tokens`/
   `cache_creation_input_tokens`/`cache_read_input_tokens`/`model` —
   finer than `five-hour-samples.jsonl`'s per-turn cumulative
   `cache_read` snapshot, which is unchanged and kept as-is (it still
   drives the five-hour interval nudge). Committed + pushed every turn
   via the existing `TRACKED_FILES` mechanism, so it inherits the same
   loss-resistance guarantee as `session-archive.md`. Dedup is against
   the jsonl file's own contents, so re-scanning the full transcript on
   every Stop firing never double-counts a call. `scripts/generate-
   usage-dashboard.py` reads it and renders a self-contained, Japanese-
   language, interactive HTML report (day/week/month period toggle,
   session/model/overall group-by, sortable breakdown table, stacked
   trend chart) with no server and no external JS dependency — publish
   the output as an Artifact whenever a human wants to look. This is
   explicitly a read-only convenience layer on top of the jsonl, not
   where durability lives.

8. [x] **Account-wide collection (local Claude Code CLI + any project, not
   just cloud/governance-aware repos)** — added 2026-08-31. Extended item
   6's collection so it isn't cwd-scoped anymore: `resolve_usage_mirror_dir`
   routes `token-usage-events.jsonl` through a fixed clone of this repo at
   `~/.claude/governance-usage-mirror` (or `cwd` directly when already
   inside this repo), so usage is recorded no matter which project a
   session is actually working in — cloud or local. Each row now also
   carries a `project` label. `scripts/install-local.sh` is the one-time
   manual step for a local machine (this session can't reach one itself);
   `README.md`'s new "トークン利用状況の収集" and "別マシン/別環境で使う場合"
   sections cover both. Explicitly ruled out of scope: claude.ai's plain
   chat/Desktop app (non-Code) — no hooks or public per-user usage API
   exist for it, confirmed with the user 2026-08-31.

   Turning this into a genuinely multi-writer file (every cloud session
   plus potentially several local machines, all racing to push the same
   `token-usage-events.jsonl`) needed a merge strategy beyond git's own:
   `git rebase` was tried first and proven live to deadlock — two writers
   independently appending one line each to a *short* file produce
   identical-context diffs, a textbook conflict even though there's no
   real disagreement, and retrying doesn't help since nothing about the
   conflict changes between retries. Replaced with a content-level union
   merge keyed by `message_id` (`sync_mirror_before_write`) — conflict-free
   by construction for an append-only, id-deduped file. Verified against a
   synthetic two-writer race (local git repos standing in for GitHub): the
   rebase approach left the second writer permanently stuck; the union
   merge converged on the first retry and both writers ended up with the
   full set of rows.

9. [ ] **Native-Windows install path — needs real-machine verification**
   Added 2026-08-31: `hooks/session-start.py` (pure-Python twin of
   `hooks/session-start.sh`, since a bash shebang script won't run on
   native Windows without Git Bash) and `scripts/install-windows.ps1`
   (PowerShell installer, bakes absolute paths + interpreter into each
   hook's `command` string rather than relying on `~`/env-var expansion
   inside Claude Code's hook runner). `archive-turn.py`/`session-end.py`
   needed no changes — already pure Python. **Unverified against a real
   Windows machine** — this session runs in a cloud Linux environment with
   no way to test PowerShell or an actual native-Windows Claude Code hook
   invocation; the implementation follows the general understanding that
   native Windows doesn't honor Unix shebangs and needs an explicit
   interpreter in the hook command, but that hasn't been confirmed against
   primary Claude Code documentation. Needs a real Windows user to run
   `scripts/install-windows.ps1` and report back whether hooks actually
   fire and CLAUDE.md loads correctly.

10. [ ] **Re-check the segment-4-shaped anomaly once session_id data accumulates**
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
