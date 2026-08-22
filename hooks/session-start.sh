#!/bin/bash
# SessionStart hook. Installed once (via the kakeibo environment's Setup Script),
# but re-fetches this file, its siblings, and CLAUDE.md from GitHub on every run —
# so logic/content updates apply on the next session without touching the
# environment settings again. See ../README.md for the install step.
#
# Uses `git clone`/`git pull` rather than `curl` to raw.githubusercontent.com:
# app-Governance is a private repository, so unauthenticated curl to the raw
# CDN always 404s (confirmed 2026-08-21 — even for nonexistent paths, the
# signature of a private repo). git operations against github.com work
# IF AND ONLY IF the current session's environment has app-Governance in its
# authorized repo scope — the outbound proxy injects git-smart-HTTP
# credentials per repo, not globally. Confirmed 2026-08-22: a session running
# in an environment scoped only to a different repo (e.g. xilitol111/game)
# gets a bare `fatal: could not read Username` here, every single session,
# with no other symptom — which is exactly why this block's success/failure
# is echoed below instead of silenced. If you see "Governance sync: FAILED"
# on session start, this environment needs app-Governance added to its
# authorized repo scope (or the repo needs another distribution path that
# doesn't depend on git auth, e.g. making it public).
set -uo pipefail

GOV_REPO="https://github.com/xilitol111/app-Governance"
GOV_CLONE="$HOME/.claude/governance-src"

if [ -d "$GOV_CLONE/.git" ]; then
  GOV_SYNC_ERR=$( { git -C "$GOV_CLONE" fetch --quiet origin main \
    && git -C "$GOV_CLONE" reset --quiet --hard origin/main; } 2>&1 )
else
  rm -rf "$GOV_CLONE"
  GOV_SYNC_ERR=$(git clone --quiet --depth 1 --branch main "$GOV_REPO" "$GOV_CLONE" 2>&1)
fi

if [ -d "$GOV_CLONE" ] && [ -f "$GOV_CLONE/CLAUDE.md" ]; then
  mkdir -p ~/.claude/hooks
  cp "$GOV_CLONE/CLAUDE.md" ~/.claude/CLAUDE.md
  for f in session-start.sh archive-turn.py session-end.py; do
    if [ -f "$GOV_CLONE/hooks/$f" ]; then
      cp "$GOV_CLONE/hooks/$f" ~/.claude/hooks/"$f"
      chmod +x ~/.claude/hooks/"$f"
    fi
  done
  echo "## Governance sync: OK ($(git -C "$GOV_CLONE" log -1 --format='%h %s' 2>/dev/null))"
else
  echo "## Governance sync: FAILED"
  echo "~/.claude/CLAUDE.md and hooks were NOT updated this session — whatever"
  echo "was already there (possibly stale, possibly empty placeholder files) is"
  echo "still in effect. This environment likely lacks git access to"
  echo "app-Governance; see the comment above this block for the fix."
  if [ -n "${GOV_SYNC_ERR:-}" ]; then
    echo "git error: $GOV_SYNC_ERR"
  fi
fi
echo

# Cheap, zero-LLM-cost continuity: surface recent git history of the CURRENT
# project (not the governance repo) so a new session has a hint of what
# happened last, at near-zero token cost.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "## Recent commits"
  git log --oneline -10 2>/dev/null
  echo
  echo "## Latest commit (full message)"
  git log -1 2>/dev/null
  echo
  echo "## Uncommitted changes"
  git status --short 2>/dev/null
fi

# Same zero-LLM-cost idea, for the handoff notes archive-turn.py writes:
# surface a bounded TAIL of docs/session-archive.md (not the whole file —
# it's appended to forever across every past session in this project, so
# reading all of it would grow unbounded). This is what lets a session
# spun up via create_session (e.g. the one the five-hour-limit notification
# in archive-turn.py has Claude create proactively) actually pick up "what
# was still open" without an LLM having to go Read the file itself — it's
# already sitting in context the moment the session starts, for the cost
# of a `tail`, not a tool call.
ARCHIVE_FILE="docs/session-archive.md"
if [ -f "$ARCHIVE_FILE" ]; then
  echo
  echo "## Recent session archive (tail of docs/session-archive.md)"
  tail -c 4000 "$ARCHIVE_FILE" 2>/dev/null
fi
