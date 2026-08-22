#!/bin/bash
# SessionStart hook. Installed once (via the kakeibo environment's Setup Script),
# but re-fetches this file, its siblings, and CLAUDE.md from GitHub on every run —
# so logic/content updates apply on the next session without touching the
# environment settings again. See ../README.md for the install step.
#
# Uses plain `curl` against raw.githubusercontent.com, not `git clone`.
# app-Governance was private through 2026-08-21, so unauthenticated curl to
# the raw CDN always 404'd and git (authenticated transparently by the
# environment's outbound proxy, but ONLY for repos in the current session's
# authorized scope) was the only option — which silently failed in any
# environment/session not scoped to this repo (confirmed 2026-08-22 against
# a `xilitol111/game` session: bare `fatal: could not read Username`, every
# time, with nothing surfaced anywhere). Made public 2026-08-22 specifically
# to remove that per-environment scope dependency: curl to the raw CDN now
# works from any environment with plain outbound HTTPS, no auth of any kind
# needed. If this ever needs to go private again, this block has to revert
# to the git-clone approach (see git history around 2026-08-22 for it) and
# every environment that should receive governance updates will again need
# app-Governance explicitly added to its authorized repo scope.
set -uo pipefail

GOV_RAW="https://raw.githubusercontent.com/xilitol111/app-Governance/main"
GOV_TMP=$(mktemp -d)
GOV_SYNC_OK=1

fetch() {
  curl -fsSL "$GOV_RAW/$1" -o "$GOV_TMP/$(basename "$1")" 2>>"$GOV_TMP/.err" || GOV_SYNC_OK=0
}

fetch "CLAUDE.md"
fetch "hooks/session-start.sh"
fetch "hooks/archive-turn.py"
fetch "hooks/session-end.py"

# All-or-nothing: only replace the live files once every fetch above
# succeeded, so a mid-fetch network hiccup can't leave CLAUDE.md and the
# hooks on mismatched versions of each other.
if [ "$GOV_SYNC_OK" = "1" ]; then
  mkdir -p ~/.claude/hooks
  cp "$GOV_TMP/CLAUDE.md" ~/.claude/CLAUDE.md
  for f in session-start.sh archive-turn.py session-end.py; do
    cp "$GOV_TMP/$f" ~/.claude/hooks/"$f"
    chmod +x ~/.claude/hooks/"$f"
  done
  echo "## Governance sync: OK (curl, public repo)"
else
  echo "## Governance sync: FAILED"
  echo "~/.claude/CLAUDE.md and hooks were NOT updated this session — whatever"
  echo "was already there (possibly stale, possibly empty placeholder files) is"
  echo "still in effect. This should only happen if this environment has no"
  echo "outbound HTTPS at all, or GitHub itself is unreachable."
  if [ -f "$GOV_TMP/.err" ]; then
    echo "curl error: $(cat "$GOV_TMP/.err")"
  fi
fi
rm -rf "$GOV_TMP"
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
