# Operating guidelines (efficiency)

These apply across all projects/sessions, not just one repo. Goal: cut
token/cost waste without reducing work quality or thoroughness — never
skip verification or rigor to save tokens; save tokens by not
re-deriving or re-loading things unnecessarily.

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
- Within a single session, distinguish `/clear` from `/compact`: when the
  user pivots to a task clearly unrelated to what the conversation has been
  doing, proactively suggest `/clear` rather than letting unrelated history
  keep accumulating in the cached context — durable plan/spec files (not
  conversation memory) already carry any continuity that matters, so
  `/clear` loses nothing worth keeping. Reserve `/compact` for continuing
  the *same* line of work once the transcript has simply grown long. This is
  a different lever from the five-hour-limit `create_session` policy below:
  `/clear` addresses topic-locality within one session (free, instant,
  user-run), `create_session` addresses the account-wide usage-window limit
  — apply whichever is actually relevant, and both where both apply.
- No tool lets Claude run `/clear` or `/compact` on the user's behalf or
  pre-fill their input — either can only be suggested, and the user
  prefers this framed as an explicit choice rather than buried in prose.
  When a natural boundary for either is reached, use `AskUserQuestion` to
  ask directly (e.g. "clear now" vs. "keep going", or "compact now" vs.
  "keep going") instead of just mentioning the command in passing — a
  clickable decision point is easier to act on than free text. If the
  user picks the compacting/clearing option, follow up with the bare
  command alone on its own line as inline code (`` `/clear` `` or
  `` `/compact` ``), since Claude still can't run it for them — most
  clients render inline/fenced code with a one-tap copy affordance, so
  they can act on it without retyping.
- Commit meaningful progress at natural checkpoints, not only when a
  session feels "done." Sessions can end unexpectedly (container
  reclaimed, connection drop); uncommitted work does not survive to the
  next session, no matter what automation exists around it. When a
  decision, direction change, or open question gets resolved mid-session,
  write it to a durable file (NOTES/DEVLOG-style) right then rather than
  deferring to an end-of-session wrap-up that might not happen.
- The `Stop` hook tracks cumulative cache-read tokens against the
  account's five-hour usage limit and injects a system note every time
  that total crosses another watch interval (not just once per session —
  switching sessions is now cheap enough that repeated nudges are worth
  it). When that note appears: actually call `create_session` yourself
  (inherit the environment, same repo source) rather than just asking the
  user whether to — continuity is already covered by
  `docs/session-archive.md`, git history, and this file, so the new
  session starts oriented. Tell the user briefly what's still open here
  and hand them the new session's link; keep working here if they keep
  talking instead of moving. Don't wait for the user to suggest the
  switch themselves.

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
