# Operating guidelines (efficiency)

These apply across all projects/sessions, not just one repo. Goal: cut
token/cost waste without reducing work quality or thoroughness — never
skip verification or rigor to save tokens; save tokens by not
re-deriving or re-loading things unnecessarily.

## Before starting a task

- Before diving into any non-trivial task, take one deliberate beat to
  consider which token-reduction levers from this document actually apply
  — reuse context already loaded this session, skip a subagent/tool call
  that isn't needed, scope a read/search/grep to what the task actually
  requires instead of the whole file or codebase, prefer a mechanical
  check over an LLM-judged one. This is an explicit step taken before
  acting, not passive background awareness — treat it as part of choosing
  an approach, the same as deciding which file to edit.
- The bar stays "no quality loss": every lever here only applies when it
  doesn't skip verification, rigor, or a check that would catch a real
  bug. When a cost-saving option and correctness conflict, correctness
  wins — this document exists to cut waste, not to justify cutting
  corners.

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
  the *same* line of work once the transcript has simply grown long.
  Treat this and the five-hour-limit `create_session` policy below as one
  escalation ladder, not two independent policies: both exist to reset the
  marginal cache-read cost of future turns, `/clear`/`/compact` being the
  free, instant, in-place rung and `create_session` the heavier one. Check
  the cheap rung first at every natural boundary; only escalate to
  `create_session` when the work is one continuous, unclearable task that
  still needs its full live context and has crossed the usage-window
  threshold — `/clear`/`/compact` can't help there since dropping or
  summarizing the context would lose what the task still needs.
- The two rungs are gated by different preconditions, though — don't
  generalize one's check to the other. `/clear`/`/compact` only reset this
  session's local context window; they touch no files or git state at all,
  so their precondition stays the existing soft one (has anything from
  this session that matters already been written to a durable file, per
  the commit-discipline bullet below). `create_session`'s precondition is
  mechanical and stricter: the current project repo's `docs/session-
  archive.md` must be confirmed pushed to origin *and reachable from the
  repo's actual default branch* — not just pushed to some branch, since a
  brand-new session only ever sees `origin/<default>` with no other channel
  back to this session's container. Being pushed to an unmerged feature
  branch satisfies neither "committed" nor "safe" (`archive-turn.py`'s
  `commit_and_push` reports this distinctly as `"pushed_off_default"`,
  2026-08-22 — found live in this repo's own governance session, sitting on
  a feature branch the whole time). A `/clear`-safe moment is not
  automatically a `create_session`-safe moment.
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
- **Standard post-`/clear`/`/compact` handoff — don't re-derive it, follow
  this every time:** `session-start.sh` already injects, at zero LLM cost,
  the current project's recent git log, latest commit message, git status,
  and a bounded tail of `docs/session-archive.md` (plus, since 2026-08-22,
  a stale-`CLAUDE.md` notice when relevant). Treat that injected block as
  the complete handoff and resume directly from whatever its last entries
  describe as still open — don't ask the user to re-explain, and don't
  re-read `docs/session-archive.md` in full or dig into `docs/plans/`/
  `docs/DEVLOG.md` unless the injected tail doesn't cover what's actually
  needed. If anything was being actively tracked before the clear (a PR
  subscription, a scheduled check-in), re-establish it explicitly rather
  than assuming it survived — `subscribe_pr_activity` and scheduling calls
  are idempotent, so just re-arm them. Only fall back to asking the user a
  clarifying question if the injected tail ends without a clear next step.
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
  it). The note includes a push-status check (2026-08-22) — read it first:
  only if it confirms the repo is fully pushed, actually call
  `create_session` yourself (inherit the environment, same repo source)
  rather than just asking the user whether to — continuity is already
  covered by `docs/session-archive.md`, git history, and this file, so the
  new session starts oriented. If the note instead warns the repo isn't
  confirmed pushed, don't create the session — the hook retries the push
  every turn automatically; if it's still stuck after a couple of turns,
  say so to the user plainly instead of proceeding on stale assumptions or
  silently waiting. Once it's safe to proceed: tell the user briefly
  what's still open here and hand them the new session's link; keep
  working here if they keep talking instead of moving. Don't wait for the
  user to suggest the switch themselves.

## Loop engineering (autonomous fix/verify cycles)

Applies whenever a session runs an autonomous "make a change, check it,
retry" cycle (bug-fix loops, `/goal`, a checker/fixer subagent) inside an
app repo — not this repo itself, which holds no app code. On the Pro plan,
usage-window budget is the binding constraint for continuous multi-day
development, so prefer the loop shape that gets the same verification
rigor at the lowest token cost, not the most sophisticated one.

- Never start an open-ended loop. Before the first iteration, fix an
  explicit stopping condition: a mechanical quality bar (tests green, lint
  clean, typecheck clean) *and* a hard iteration/time cap. "The AI still
  seems to be making progress" is not a stopping condition.
- Prefer mechanical verification over LLM-judged verification: wire
  tests/lint/typecheck into the app repo's own `.claude/settings.json`
  (`PostToolUse`/`Stop` hooks that shell out, mirroring this repo's own
  `hooks/archive-turn.py` — no LLM call, so it costs nothing against the
  usage window). Reach for an LLM-based checker/fixer subagent only for
  judgment calls a linter/test genuinely can't make (spec conformance,
  code smell), and only on higher-risk changes — each subagent call is a
  full extra turn in its own context, not a free check.
- On two consecutive failures on the same error inside one loop, hand off
  to a fresh subagent turn instead of continuing to retry in the same
  increasingly-polluted conversation — but don't stand up a dedicated
  subagent per project unless that project's loop actually needs one.
- `/goal` is fine for a narrowly-scoped, well-defined task, always with
  both a max-iteration and max-time cap set explicitly. It's the most
  expensive mechanism here (every retry is a full extra turn), so treat an
  unscoped `/goal` as a real risk to the day's remaining usage window, not
  a convenience.
- Skip `/schedule` and unattended multi-agent "Agent Teams" loops on the
  Pro plan entirely — periodic/background iteration with nobody watching
  has no natural ceiling on usage-window consumption.
- If the same multi-step task recurs across sessions, register it as a
  Skill (`.claude/skills/`) rather than re-explaining it each time: a
  skill adds only a name + one-line description to every turn's baseline
  (much cheaper than the same instructions living in `CLAUDE.md`) and
  loads its full body only when actually invoked.
- Hold the phase sequence itself — requirements, design, implementation,
  verification, release — as a shared mental model with the user, not
  just a habit of producing artifacts. Before non-trivial work, name
  which phase the task is in, and don't slide into the next phase's
  actions (e.g. writing implementation code while the design is still
  unreviewed) just because the conversation has momentum. The phase docs
  below are how that shared understanding gets written down; writing the
  file is not a substitute for actually respecting the phase boundary.
- For anything beyond a small fix, write phase docs as external memory
  before the loop starts — a short requirements note, a design note, an
  implementation plan, as files, not just conversation. This is the
  within-task version of the durable-file-handoff pattern from Session
  scoping above, and it's what lets a `/clear`, a `/compact`, or a
  hand-off to a fresh subagent resume the task correctly mid-way.
- Gate implementation on a design review, not only on tests passing after
  the fact: a design doc reviewed for two minutes before code exists is
  cheaper than several loop iterations spent fixing a correct
  implementation of a wrong design.
- Keep the roadmap-approval gate human-owned no matter how automated the
  rest of the loop is — see "Roadmap-gated autonomous execution" below
  for exactly when to check in and when to stop and raise a real
  question instead.

## Roadmap-gated autonomous execution

For any non-trivial task, produce the roadmap first — concrete steps from
requirements through design, implementation, and test to done — and get
it approved before starting execution. Once approved, that roadmap is
the standing authorization to keep going: don't re-ask "what should I do
next" mid-task, and don't ask open-ended direction questions the roadmap
already answers.

- Write the roadmap as a durable file (e.g. `docs/plans/<task>.md`) so it
  survives a `/clear`, a `/compact`, or a session switch — per Session
  scoping above, that's the handoff mechanism, not conversation memory.
- After approval, ask for permission to proceed — never for direction —
  at exactly two points: (a) on resuming work (after `/clear`/`/compact`,
  a new `create_session`, or any other session boundary), and (b) right
  after finishing the step/task currently in front of you. At both
  points: reload the roadmap file, state which step is next in one line,
  and ask only "proceed with this step?" — not "what should I do now?".
  Between those two points, execute without asking.
- Update the roadmap file in place as steps complete or the plan changes,
  so each check-in reads the file's current state rather than
  reconstructing progress from conversation memory.

**Exceptions — stop and raise the actual issue, not just a proceed-check, when:**
  - The step needs a destructive or hard-to-reverse action the approved
    roadmap didn't already call out (force-push, `git reset --hard`,
    `rm -rf`, dropping/altering shared data, discarding uncommitted
    work).
  - A design decision or fork in the road comes up that the roadmap
    didn't anticipate (an assumption turns out wrong, two valid
    approaches diverge, a dependency needs to change).
  - The work needs to expand beyond what was approved (a new requirement
    surfaces, a fix needs files/areas outside the roadmap's scope).
  - A step fails repeatedly with no fix obviously inside the approved
    plan (see the two-consecutive-failures rule above).
  - The action reaches outside the local repo into shared/external state
    — pushing, opening or merging a PR, deploying, notifying someone —
    when the roadmap didn't already spell that out as an approved step.

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
