## Resolved (same day, after the user pasted the Setup Script): it failed on first real test — made it network-free

User pasted the (git-clone-based) Setup Script into the `kakeibo` environment
settings and asked to test it. Spun up a real test session
(`session_014ecYpAAGVqBTGJfDAetRNH`, in the `kakeibo` environment, archived
after this investigation) via `create_session` to check. Result:
`last_init_error: {error_kind: "init_script", message: "Setup script
failed", recoverable: "false"}` — the session never became usable
(`ListAgents` couldn't reach it). No raw setup-script log was available
through any tool here to see the actual stderr.

Most likely cause (reasoned, not confirmed — no logs to verify against):
the Setup Script used `set -euo pipefail` and called `git clone` directly.
This early in container provisioning, the environment's git-auth proxy
injection (the mechanism confirmed working for every `git push`/`fetch` all
session, documented two sections up) may not be live yet, and any single
failing command under `-e` kills the whole script with no partial credit —
so even the harmless local file writes (hook scripts, `settings.json`)
never happened either.

**Fix**: rewrote the Setup Script to do *no network I/O at all*. It now only
writes a minimal `session-start.sh` (embedded inline, not fetched) plus
empty placeholder files for the other two hooks, and registers all three in
`settings.json` — all local filesystem operations, nothing that depends on
git auth being ready. The real `git clone`/`fetch` moved entirely into
`session-start.sh` itself, which only runs later once an actual session's
own git auth is live (proven reliable all session) and was already written
to tolerate a failed fetch without crashing (no `-e`). Verified locally
against a simulated fresh `HOME` — exits 0, produces the correct
`settings.json` and hook files, using no network access. Not yet re-verified
against a real new `kakeibo` session (need the user to re-paste the updated
script and re-test) — that's the next step, not confirmed done.

---

## Resolved (same day, right after merging to main): the whole fetch mechanism was silently broken — curl can't read a private repo

Immediately after fast-forwarding this work to `main` (at the user's "回して"
go-ahead), sanity-checked that the Setup Script would actually work by
curling the just-pushed `raw.githubusercontent.com/.../main/CLAUDE.md` URL —
**404**. Checked whether it was CDN propagation lag; it wasn't: a
deliberately nonexistent path on the same repo/branch also 404s, which is
GitHub's signature for "no unauthenticated access" (private repos and
missing files are indistinguishable on the raw CDN, by design). **This repo
is private, so every `curl` fetch in `hooks/session-start.sh` and the
Setup Script — the entire self-refresh mechanism this whole thread built —
had been non-functional since the very first version, hours ago.** The
`|| true` / best-effort error handling meant it would have failed silently:
`~/.claude/CLAUDE.md` and the hook scripts simply wouldn't have existed on a
real fresh container, no error surfaced to anyone.

Root cause understood via the one thing that *does* demonstrably work all
session: `git push`/`git fetch` against `github.com`. Checked
`~/.gitconfig` and found no embedded token or credential helper — auth is
injected transparently by the environment's outbound proxy for git's
smart-HTTP protocol specifically (`__agentproxy/status` showed
`"gitConfigInjection": true`). That injection doesn't apply to arbitrary
`curl` requests to a different host (`raw.githubusercontent.com`), which is
why git operations succeeded all along while raw-content curls silently
couldn't have.

**Fix**: replaced every `curl`-to-raw-CDN fetch with `git clone` (first run)
/ `git fetch` + `reset --hard` (subsequent runs) against a local mirror at
`~/.claude/governance-src/`, in both `hooks/session-start.sh` and the
Setup Script documented in `README.md`. Verified end-to-end against a
simulated fresh container (`HOME` pointed at an empty temp directory): the
script correctly cloned the private repo and populated
`~/.claude/CLAUDE.md` and all three hook scripts from nothing.

**Lesson for next time**: verify a fetch mechanism against the actual
deployed artifact (a real private repo, unauthenticated) before calling it
done — testing only against already-authenticated local git operations
(which is all that was done originally) hid this for the entire session.

---

## Resolved (same day, later still): session-switching policy derivation, and a correction

User asked how to derive an actual session-switching *policy* from the
calibrated ceiling (~43.2M tokens ≈ 100% of five_hour, from the prior
section), and separately whether an optimal CLAUDE.md size range could be
derived by weighing the diminishing token-savings from shrinking it against
the point where it gets too small to function.

**Growth model, fit to this session's own real data** (99 messages in the
current five_hour window, `cache_read_input_tokens` per unique `message.id`):

```
cumulative(N) = B·N + (c/2)·N²
B ≈ 273,747 tokens   (fitted intercept — roughly the fixed per-turn floor:
                       system prompt + CLAUDE.md + early accumulated reads)
c ≈ 3,788 tokens/turn (fitted slope — conversation growth per turn)
```

Solving `cumulative(N) = W` for the calibrated ceiling (W = 43,200,000) gives
**N ≈ 95 turns** as the safe turn count for a conversation shaped like this
one (research + writing, moderate tool use). The existing notification
threshold (15M) corresponds to **N ≈ 42 turns**, i.e. roughly 50 turns of
margin before the true ceiling under this model.

**Code-centric estimate (rough, not confidently fit)**: split this same
session's per-turn deltas by whether the turn followed heavy tool output
(>2000 chars of `tool_result` content). Tool-heavy turns (n=14) had ~3x the
*median* delta of light/conversational turns (n=88) — 3,740 vs 1,213. Means
were not usable (light-turn mean was negative, an artifact of parallel
tool-call batching / thinking-token variance, not real content shrinkage).
Applying that ~3x as an illustrative multiplier: `c_code ≈ 11,364/turn` →
**N ≈ 66 turns**. This is a single-session, single-account extrapolation —
treat as a placeholder until a real code-heavy session (e.g. in GAME) runs
with this same logging and produces its own fit.

**Correction to a claim made earlier the same day**: previously stated that
shrinking CLAUDE.md (reducing B) has *diminishing* returns as it gets
smaller. Recomputed `dN/dB` properly and found the opposite: marginal safe-
turns gained per token cut **increases** as B shrinks (0.113 turns/1000 tok
at B=400K, rising to 0.262 turns/1000 tok at B=5K — approaching the
asymptote 1/c as B→0), and is smallest when B is already large. Consequence:
**the token/five-hour-limit model alone provides no natural floor on
CLAUDE.md size** — it says smaller is always at least as good, with no point
where the model itself says "stop cutting here." Any floor has to come from
content necessity (what CLAUDE.md must keep to avoid Claude making avoidable
mistakes), which isn't something this token model can quantify. The
practical way to find that floor is empirical, not computed: run the
existing "if Claude repeats a mistake twice, add it to CLAUDE.md" process in
reverse after trimming — watch for regressions (repeated mistakes, redundant
questions, convention violations) as the signal that a cut went too far.

---

## Resolved in the follow-up governance session (2026-08-21, later same day)

Decisions made, superseding the "planned structure" and TODOs below:

- **Physical migration dropped.** GAME (and kakeibo/kakeibo-liff) stay in
  their own repos, unchanged. This repo holds only the guidelines text —
  no `projects/<name>/` subtree, no `git subtree` import. See
  `README.md` for why (researched alternatives — plugin marketplace,
  `.claude/rules/` symlinks — and both had real gaps for this use case:
  plugins can't reliably deliver always-loaded free-text guidance the
  way CLAUDE.md does, and rules-symlinks don't survive this ephemeral
  cloud environment where each session gets a fresh container).
- **Important correction to this file's own claim below**: the
  "`~/.claude/CLAUDE.md` already written in the current remote
  environment" statement turned out to be wrong by the time the next
  session opened — the file didn't exist. Same environment
  (`env_01CH8G8RmBJwUGCWuLdsJFGj`, "kakeibo"), but each session gets an
  ephemeral container, so a manually-edited home directory doesn't
  survive to the next session. This is *why* the environment-level
  approach needed a real fix rather than just "it's already done."
- **Chosen mechanism**: this repo's `CLAUDE.md` is the source of truth.
  The `kakeibo` environment's **Setup Script** (configured once via the
  claude.ai environment settings UI — not something Claude Code can set
  from inside a session) copies it to `~/.claude/CLAUDE.md` on
  container provisioning. Because the environment caches state after
  the setup script runs, this survives to every future session in that
  environment, for any project, without per-project setup — satisfying
  "CLAUDE.md-level" and "auto-applies to new projects" both. Trade-off:
  the setup script runs once and caches, so updates to this repo's
  `CLAUDE.md` require re-saving the environment's setup script to force
  a re-fetch. See `README.md` for the exact script and update steps.
- **Still open / not decided**: whether kakeibo/kakeibo-liff should also
  live under this governance umbrella (same answer as GAME — no code
  migration needed, they'd just benefit automatically once opened in
  the `kakeibo` environment); whether to also cover a local-machine
  Claude Code setup (the Setup Script mechanism is cloud-environment
  specific, so a local install needs its own sync step, not yet
  designed); the `my-monorepo-apps` duplicate-purpose question below
  is still unresolved.

## Resolved in a later same-day follow-up: physical integration reconsidered, then dropped again

User asked to research general industry practice (polyrepo vs monorepo, and
whether something bigger than "a repository" exists for cross-repo
governance) before finalizing. Findings:

- GitHub **Organization** is the real supra-repo management unit
  (billing, teams, org-wide security policy, reusable workflows). Its
  `<org>/.github` special repo provides org-wide *default* issue/PR
  templates, `CODE_OF_CONDUCT`, `SECURITY.md`, etc. — but **not**
  `CLAUDE.md`: Claude Code's CLAUDE.md load locations are only managed
  policy / user / project / local, and the `.github` defaults mechanism
  isn't one of them.
- GitHub **Projects (v2)** at the org level can aggregate issues/PRs
  across multiple repos into one board — a real answer to "issues feel
  scattered across repos," but again orthogonal to CLAUDE.md
  distribution.
- Meta-repo/manifest-repo pattern (Android's `repo` tool, ROS's
  `vcstool`/`west`) — a lightweight repo holding pointers to other repos
  without merging code — is close to what this repo already is.
- **User's conclusion, which settled the question**: "even with an
  Organization, if we still need the hook, why bother with the
  Organization?" — correct. Organization doesn't reduce reliance on the
  CLAUDE.md-sync hook at all, so it was dropped as unnecessary
  complexity. This also reconfirmed the earlier point that the *only*
  way to avoid needing any hook at all is physical integration.
- Despite that, **user explicitly chose to keep existing apps
  (GAME/kakeibo/kakeibo-liff) as separate repos and rely on the hook**
  ("フックで済ませるのがマシな気がしてきた") rather than physically
  migrating them. Physical integration is considered closed — do not
  re-litigate without a new reason from the user.

## Resolved: session continuity across sessions, at near-zero token cost

Follow-up requirement: switching sessions should not lose progress/decisions,
without materially increasing token consumption. Design settled on:

- Claude Code's built-in **auto memory** (`~/.claude/projects/<project>/memory/`)
  was ruled out — it lives under `~/.claude`, which this session empirically
  confirmed does **not** survive across sessions in the `kakeibo` environment
  (same root cause as the CLAUDE.md correction above).
- A `Stop`-hook-writes-a-log-file design was considered, but rejected in that
  form: a file written locally and never committed doesn't survive to a new
  session (fresh clone) either. Auto-committing on every turn was also
  rejected (git history noise, credential/push concerns).
- **Final design** — three hooks, installed once via the same Setup Script,
  each self-refreshing from this repo's `main` every session so future logic
  changes don't require touching the environment settings again:
  - `hooks/session-start.sh` (`SessionStart`, once per session): re-fetches
    itself + its siblings + `CLAUDE.md` from `main`, then prints
    `git log --oneline -10` + the latest commit's full message +
    `git status --short` to stdout (auto-injected into context at session
    start). Zero LLM cost; small bounded token cost once per session.
  - `hooks/archive-turn.py` (`Stop`, every turn): parses the transcript file
    (no model call) and appends the latest assistant text to
    `docs/session-archive.md` in the current project, locally only. Zero
    token cost — nothing here is injected into context.
  - `hooks/session-end.py` (`SessionEnd`, once per session, fires
    automatically — no explicit close needed): commits + pushes
    `docs/session-archive.md` if it changed, bundling the whole session
    into one commit rather than one per turn. Zero token cost (pure git
    ops).
- User explicitly approved the auto-commit/push behavior, scoped strictly to
  `docs/session-archive.md` for archival purposes only — not a general
  "Claude may auto-push anything" grant.
- `docs/session-archive.md` is a passive archive: it is **not** auto-injected
  into new sessions' context (that would make the cost grow unbounded over
  time). It exists to be read on demand, only when a future session actually
  needs to dig past what the `git log` summary already shows.
- Known residual gap (discussed openly, accepted as a trade-off): work that
  is neither committed nor archived before a session ends unexpectedly is
  still lost. Zero-cost automation cannot fully close this; the mitigation
  is the CLAUDE.md guidance to commit/write decisions at checkpoints rather
  than only at a session's end.
- Implemented and locally verified this session: `hooks/archive-turn.py` run
  against this session's own real transcript correctly appended the latest
  assistant turn to `docs/session-archive.md` with a dedup marker; the
  resulting file was correctly detected as a new file by
  `git status --porcelain`.

## Resolved (same day, later): five-hour-limit investigation — log collection shipped, threshold notification deliberately NOT enabled yet

User's actual pain point ("今引っかかることが多い") turned out to be the
`five_hour` rolling window specifically (confirmed by asking directly — other
sessions in `list_sessions` showed `seven_day` and there's a separate monthly
spend cap, so there are at least 3 independent limit tiers on this account).

Investigation, in order:

1. **Premise check (user pushed back correctly)**: asked whether the five-hour
   meter is fundamentally token-based (with per-operation weighting). Verified
   against Anthropic's own support article: **it is explicitly NOT a token
   budget** — "usage is metered as a share of a five-hour session... Anthropic
   reserves the right to adjust that share." Token count, message length,
   attachments, tool use, model, and effort all influence it, but there's no
   published conversion formula. This means any token-based threshold is
   necessarily a proxy, not a direct measurement.
2. **External research, round 1**: generic blog advice (use cheaper models,
   keep CLAUDE.md small, disable unused tools). User correctly called this out
   as "things anyone could guess without research" and pointed out that
   model/effort/tool-connector choices are made by the *human* at session
   setup, not by Claude reading CLAUDE.md — so writing that guidance into
   CLAUDE.md targets the wrong actor and accomplishes nothing.
3. **External research, round 2, more targeted**: found real quantitative
   community investigations — a leaked Claude Code source map led to
   `github.com/ArkNill/claude-code-hidden-problem-analysis` (45,884 requests /
   320 sessions monitored via `anthropic-ratelimit-unified-*` headers: ~1% of
   quota ≈ 1.5–2.1M cache-read tokens vs. only 9–16K output tokens, i.e. output
   is far "heavier" per-token but cache read dominates in raw volume) and
   `anthropics/claude-code` issue #24147 (one real account, 30 days: cache
   reads were 99.93% of total metered tokens, 1,310:1 ratio vs. I/O; single-day
   comparison showed cache reads growing 2.8x while I/O only grew 1.7x — a real
   measurement of the super-linear growth this session's CLAUDE.md guidance
   was already written to guard against). **Critical finding from #24147**:
   cache-read tokens reportedly count at *full* weight against the five-hour/
   weekly quota, unlike the ~0.1x discount they get on the dollar-billed
   `cost_usd` — this is the most likely explanation for the 9–13x gap found
   earlier between computed and reported `cost_usd` (quota consumption and
   dollar billing are apparently not the same meter).
4. **Own account calibration attempt**: user reported the app showing
   `five_hour: 62%, resets in ~1h20m`. Cross-referenced against this session's
   own `rate_limit_info.resetsAt` values already seen twice this session
   (09:50 UTC, then 15:40 UTC after an intervening idle-gap reset around
   09:50–10:40) — confirmed the current window started ~10:40 UTC, consistent
   with the reported reset countdown. But this session's own start (05:43 UTC)
   predates that window, so `get_session`'s cumulative
   `cache_read_tokens: 18,389,231` for the session mixes pre-window and
   in-window usage and can't be cleanly attributed to the current window's 62%
   without per-turn timestamps — which is exactly what the new logging (below)
   now captures going forward.
5. **Implementation attempt surfaced a real data-quality bug**: extended
   `hooks/archive-turn.py` to sum `cache_read_input_tokens` across the
   transcript for a same-session proxy metric. First pass (summing every
   `type:"assistant"` JSONL line) came out **77.3M**, vs. `get_session`'s
   18.39M for the same moment — a ~4.2x overcount. Root cause found: each
   logical API response is logged as *multiple* JSONL lines (this session had
   275 assistant-type lines but only 128 unique `message.id` values), so the
   same `cache_read_input_tokens` was being summed multiple times. Deduping by
   `message.id` brought it down to **38.6M** — still ~2.1x higher than
   `get_session`'s number, for a reason **not yet identified** (candidate:
   mid-session auto-compaction resetting the cached prefix, since the last few
   samples showed cache_read dropping to ~570-580K per call late in this very
   long session, far below earlier readings — but not confirmed).

**Initial decision**: ship the log-collection half only, `NOTIFY_ENABLED =
False`, pending an explanation for the ~2.1x gap.

## Resolved (same day, immediately after): the 2.1x gap explained — get_session lags; threshold re-enabled

User followed up with another live reading of the app: `five_hour`, resets in
1h28m — checked against the already-known `resetsAt` (15:40 UTC) and found it
consistent with the same window (10:40–15:40 UTC), not a new one.

Investigated the 2.1x gap directly instead of leaving it as an open question:

- Inspected several full `usage` objects (including the `iterations` array)
  across the transcript — no double-counting found; `cache_read_input_tokens`
  grows monotonically and sanely turn to turn (0 → 229K → 359K → 512K →
  597K), consistent with a normal cumulative-context growth curve, not a bug.
- Tried splitting the sum at the window boundary (10:40 UTC) in case
  `get_session` only counted the current window — didn't reconcile (still
  ~2.1x off).
- Found the actual explanation: computed a running cumulative sum ordered by
  timestamp and found the exact point where it crosses `get_session`'s
  reported value (18,389,231) — **10:58:49 UTC**, roughly three hours before
  the ~14:11 UTC moment `get_session` was actually called. **`get_session`'s
  `usage.cache_read_tokens` field lags significantly behind the live
  conversation** — it's a periodically-updated aggregate, not a real-time
  counter. So the "2.1x discrepancy" was never a bug in the local count; it
  was comparing a live number against a stale one.
- Redid the 62%-correlation using the corrected, live local total instead of
  the stale `get_session` figure: window-scoped (10:40 UTC → ~14:14 UTC, when
  62% was reported) cumulative cache-read for this session alone =
  **26,776,894**. No other session was active in that window. This implies
  **~43,200,000 tokens ≈ 100%** of this session's own contribution to the
  five-hour limit.

**Updated decision**: `NOTIFY_ENABLED = True`, `THRESHOLD_TOKENS =
15,000,000` (roughly a third of the implied 100% figure — an early,
one-time, non-blocking nudge, not a hard stop). Verified locally: crossing
the threshold correctly emits one `decision:"block"` reason Claude sees, and
a second Stop within the same session correctly suppresses re-notifying
(marker file at `/tmp/.five-hour-notified-<session_id>`).

**Still open, honestly**: this is one calibration data point. The hook also
has no way to know when a window resets (hooks don't receive
`rate_limit_info`), so for a session that spans a reset — like this one did
— cumulative-since-session-start overcounts relative to the true
current-window figure, biasing the trigger earlier (an acceptable direction
to err in, but still imprecise). It also can't see usage from concurrent
sessions or other Claude surfaces (claude.ai, Desktop) sharing the same
account-wide limit. Recalibrate `THRESHOLD_TOKENS` as more (reported
five_hour %, `docs/five-hour-samples.jsonl` reading) pairs accumulate across
future sessions.

---

# Handoff notes — parent-repo governance (from the GAME session, 2026-08-21)

This repo's purpose and initial structure were discussed in a separate
session working on `xilitol111/GAME`, as a side conversation about
Claude usage efficiency. That session is not continuing this work — it
handed off here. This file is the handoff memo: what was decided, what
was tried, and what's still open.

## Why this repo exists

Mid-session in GAME, discussion turned to Claude Code usage cost (that
session alone: ~$272, dominated by ~80.7M cache-read tokens from running
one very long session across multiple days/initiatives). Two concrete
fixes came out of that:

1. **Per-project `CLAUDE.md` hygiene**: split GAME's `CLAUDE.md` (had
   grown to 1198 lines, ~80% detailed narrative history) into a lean
   current-state reference (`CLAUDE.md`, kept) + a separate
   `docs/DEVLOG.md` (moved, read only on demand). Already done in GAME
   — see `xilitol111/GAME`'s `CLAUDE.md` and `docs/DEVLOG.md` for the
   pattern to reuse elsewhere.
2. **Cross-project governance**: rather than re-solving this per-repo,
   put shared operating guidelines somewhere that applies automatically
   across projects. Two mechanisms discussed:
   - `~/.claude/CLAUDE.md` (user/environment-level memory) — already
     written in the current remote environment (env name "kakeibo",
     `env_01CH8G8RmBJwUGCWuLdsJFGj`, the only environment on this
     account as of 2026-08-21). Applies automatically to any repo
     worked on *in that environment*, but isn't git-tracked, isn't
     shareable/reviewable, and won't follow to a new environment or
     another machine.
   - **This repo** — a git-tracked, versioned, portable alternative:
     one parent repo with governance at the root + each project as a
     subdirectory. Claude Code loads `CLAUDE.md` hierarchically within
     one repo (root + subdirectory CLAUDE.md both apply when working in
     a subdirectory) — this is a real, already-supported mechanism, not
     a proposal that needs new tooling.

Decision: **do both, they complement each other** — environment-level
for a personal baseline, this repo for anything meant to be durable/
versioned/shared.

## The `~/.claude/CLAUDE.md` content already in place

Written to the current environment's `/root/.claude/CLAUDE.md`. Copy
below verbatim as a starting point for this repo's root `CLAUDE.md` —
it's already generic/project-agnostic, not GAME-specific:

```markdown
# Operating guidelines (efficiency)

These apply across all projects/sessions in this environment, not just
one repo. Goal: cut token/cost waste without reducing work quality or
thoroughness — never skip verification or rigor to save tokens; save
tokens by not re-deriving or re-loading things unnecessarily.

## Project CLAUDE.md hygiene

- Keep a project's `CLAUDE.md` as **current-state reference only**:
  architecture, stack, decided conventions ("don't relitigate without
  reason" sections), known gaps/simplifications. This file is reloaded
  as project instructions on every single turn of every future session,
  so its cost compounds — keep it lean.
- Move detailed dated narrative (iteration trails, "user asked X, I
  found Y, fixed Z" decision logs) to a separate file — e.g.
  `docs/DEVLOG.md` — linked from `CLAUDE.md` with a one-line pointer,
  not inlined. Read the devlog only when the *reasoning* behind a past
  decision is actually needed, not routinely.
- Rule of thumb: if a project's `CLAUDE.md` has grown past a few hundred
  lines and historical/narrative content outweighs current-state
  reference content, split it proactively — don't wait to be asked.

## Session scoping

- Prefer a fresh session per distinct initiative or phase of work over
  one session spanning many unrelated efforts across multiple days.
  Long-lived sessions accumulate large cached context that gets
  re-read every turn regardless of relevance to the current task.
- Use durable files as the handoff mechanism between sessions — commit
  plans to `docs/plans/`, keep `CLAUDE.md` current, write clear commit
  messages — not conversation memory. A new session should be able to
  pick up exactly where the last one left off by reading the repo, not
  by re-deriving context that already exists in a file.
- A natural place to suggest splitting: once a plan is finalized and
  captured in a durable file, or a feature/phase ships — flag it to the
  user as a good session boundary rather than continuing by default.

## My own operating discipline

- Don't spawn Explore/Plan subagents to rediscover context already held
  from earlier in the current session — only spawn them for genuinely
  unfamiliar territory, or when a fresh/independent perspective is the
  actual point (e.g. a second-opinion review).
- Prefer text extraction over image-based reads when both give
  equivalent information (e.g. `pdftotext` over rendering PDF pages as
  images; reading a file's text over screenshotting it) — image/vision
  content is markedly more expensive per unit of information.
- Batch UI/visual verification (screenshots, Playwright checks) at
  meaningful milestones rather than after every micro-change; prefer
  cheap text-only verification (unit/scenario tests, log assertions)
  for intermediate steps and reserve visual checks for what actually
  needs eyes.
- Reuse file contents already read into context this session instead of
  re-reading files that haven't changed.
```

## Planned structure (agreed, not yet built)

```
app-governance/               <- this repo
  CLAUDE.md                   <- root governance, applies to every project below
  docs/governance/             <- longer-form policy docs, referenced from root CLAUDE.md
  projects/
    game/                      <- xilitol111/GAME folded in here (see below)
      CLAUDE.md
      docs/DEVLOG.md
      src/...
    kakeibo/                   <- exists separately today (xilitol111/kakeibo,
                                   xilitol111/kakeibo-liff) — not yet discussed
                                   whether/how it folds in, flagging since it's
                                   the environment's namesake project
    ...future projects
```

User explicitly confirmed **GAME should be folded in too**, not left
external ("GAMEも含めて全部まとめる") — accepting that this means a real
migration, not just governance-for-new-projects-only.

## GAME migration plan (not yet executed)

- Source: `xilitol111/GAME`, branch `claude/cloudflare-api-token-0fyald`
  (the active work branch as of 2026-08-21 — **not** `main`; confirm
  whether it's been merged to main by the time this is picked up, and
  import whichever ref actually has the current state).
- Recommended method: `git subtree add --prefix=projects/game
  <game-repo-url> <branch> --squash` — brings GAME's current state in
  as a single commit rather than its full multi-hundred-commit history.
  Rationale: `xilitol111/GAME` stays intact as its own repo with full
  history preserved there, so nothing is lost by squashing on import;
  a squashed import keeps this parent repo's own history focused on
  governance/cross-project changes rather than being dominated by one
  project's entire commit log. (Not executed — full-history subtree
  merge is the alternative if that reasoning doesn't hold up on review.)
- After migration: **do not delete `xilitol111/GAME`** — leave it
  intact (only decide later, separately, whether to archive it on
  GitHub once `projects/game/` is confirmed working and future GAME
  work actually happens here instead).

## Known constraint hit this session

Creating `xilitol111/apps` via Claude's GitHub integration failed:
`403 Resource not accessible by integration` — the GitHub App's
permissions for this account don't include repository creation, only
access to individually-authorized repos. User created this repo
manually instead (and renamed it `app-governance` in the process). If
more child repos need creating later, either keep doing it manually, or
grant the GitHub App broader "Administration" permission via
claude.ai's GitHub connector settings if repo-creation-by-Claude is
wanted going forward.

## Also noticed, not yet discussed with the user

`xilitol111/my-monorepo-apps` already exists (pushed 2026-03-09,
private) — an existing repo whose name suggests it may already be
attempting something similar to what this repo is now for. Worth
checking what's in it before building this out further, in case it's
meant to be reused/merged rather than duplicated.

## TODO for the governance session

- [ ] Decide: reuse `my-monorepo-apps` instead of this new repo, or
      confirm they're meant to serve different purposes.
- [ ] Write the actual root `CLAUDE.md` (start from the guidelines
      block above; add repo purpose statement + the `projects/<name>/`
      convention + anything else the governance session decides).
- [ ] Decide final directory-naming convention (`projects/<name>` vs.
      `apps/<name>` etc.) before migrating anything, so it's not redone.
- [ ] Execute the GAME migration (subtree import, squash vs full-history
      decision, verify `projects/game/CLAUDE.md` still loads correctly
      alongside root `CLAUDE.md` in a real session).
- [ ] Decide whether `kakeibo`/`kakeibo-liff` fold in too, given the
      environment itself is named "kakeibo."
- [ ] Decide the relationship between this repo's root `CLAUDE.md` and
      the environment-level `~/.claude/CLAUDE.md` going forward — keep
      both in sync manually, make one the canonical source and have the
      other just point to it, or let them diverge intentionally (e.g.
      environment-level = personal defaults, repo-level = team/process
      policy)?
- [ ] Decide GitHub App permission question (manual repo creation each
      time vs. granting broader access).
