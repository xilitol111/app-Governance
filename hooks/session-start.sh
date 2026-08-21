#!/bin/bash
# SessionStart hook. Installed once (via the kakeibo environment's Setup Script),
# but re-fetches this file, its siblings, and CLAUDE.md from GitHub on every run —
# so logic/content updates apply on the next session without touching the
# environment settings again. See ../README.md for the install step.
set -uo pipefail

RAW_BASE="https://raw.githubusercontent.com/xilitol111/app-Governance/main"
mkdir -p ~/.claude/hooks

for f in session-start.sh archive-turn.py session-end.py; do
  curl -fsSL "$RAW_BASE/hooks/$f" -o ~/.claude/hooks/"$f".new 2>/dev/null \
    && mv ~/.claude/hooks/"$f".new ~/.claude/hooks/"$f" \
    && chmod +x ~/.claude/hooks/"$f"
done

curl -fsSL "$RAW_BASE/CLAUDE.md" -o ~/.claude/CLAUDE.md.new 2>/dev/null \
  && mv ~/.claude/CLAUDE.md.new ~/.claude/CLAUDE.md

# Cheap, zero-LLM-cost continuity: surface recent git history so a new session
# has a hint of what happened last, at near-zero token cost.
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
