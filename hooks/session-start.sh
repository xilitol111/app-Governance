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
# because the environment's outbound proxy authenticates git's smart-HTTP
# protocol transparently (the same mechanism that makes `git push` work in
# every session) — curl to a different host/path pattern doesn't get that
# injection.
set -uo pipefail

GOV_REPO="https://github.com/xilitol111/app-Governance"
GOV_CLONE="$HOME/.claude/governance-src"

if [ -d "$GOV_CLONE/.git" ]; then
  git -C "$GOV_CLONE" fetch --quiet origin main 2>/dev/null \
    && git -C "$GOV_CLONE" reset --quiet --hard origin/main 2>/dev/null
else
  rm -rf "$GOV_CLONE"
  git clone --quiet --depth 1 --branch main "$GOV_REPO" "$GOV_CLONE" 2>/dev/null
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
fi

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
