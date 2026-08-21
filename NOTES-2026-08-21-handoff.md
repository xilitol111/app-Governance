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
