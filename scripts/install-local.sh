#!/bin/bash
# One-time local install of this repo's governance hooks (session-start.sh,
# archive-turn.py, session-end.py) for a local Claude Code CLI / Desktop app
# installation — the same mechanism already running in the cloud "kakeibo"
# environment's Setup Script (see README.md), just invoked directly instead
# of pasted into an environment's Setup Script field, since a local machine
# has no such field and this session cannot reach a user's local filesystem
# to do it for them.
#
# This script needs a real bash — fine for macOS/Linux, and for WSL (run it
# from inside your WSL shell). On NATIVE Windows (PowerShell/cmd, no WSL, no
# Git Bash), use scripts/install-windows.ps1 instead — a bash script with a
# shebang won't run there. See README.md's "別マシン/別環境で使う場合" section.
#
# Usage (run once, on the machine you want covered):
#   curl -fsSL https://raw.githubusercontent.com/xilitol111/app-Governance/main/scripts/install-local.sh | bash
#
# What this does, and does NOT do:
# - Installs the 3 hook scripts to ~/.claude/hooks/ and registers them in
#   ~/.claude/settings.json (SessionStart/Stop/SessionEnd), merging into any
#   existing settings.json rather than overwriting it — identical to the
#   cloud Setup Script's own registration step.
# - Runs session-start.sh once immediately afterward, so CLAUDE.md and the
#   hook files themselves are populated right away rather than waiting for
#   the next session to start.
# - Does NOT touch any project you're currently working in, and does NOT
#   push anything on its own. From here on, archive-turn.py's Stop hook
#   (2026-08-31 revision) handles the rest automatically on every future
#   turn, in any project directory: it maintains its own separate clone of
#   this repo at ~/.claude/governance-usage-mirror purely for syncing
#   docs/token-usage-events.jsonl, and never touches whatever project repo
#   you're actually working in.
# - Requires this machine to already be able to `git push` to
#   xilitol111/app-Governance (SSH key or `gh auth login`, whichever you
#   normally use for this GitHub account) — without that, usage data still
#   accumulates locally (the collection itself never blocks on push) but
#   never leaves this machine.

set -uo pipefail

GOV_RAW="https://raw.githubusercontent.com/xilitol111/app-Governance/main"

echo "Installing app-Governance hooks to ~/.claude/hooks ..."
mkdir -p ~/.claude/hooks
GOV_TMP=$(mktemp -d)
GOV_SYNC_OK=1
fetch() {
  curl -fsSL "$GOV_RAW/$1" -o "$GOV_TMP/$(basename "$1")" || GOV_SYNC_OK=0
}
fetch "CLAUDE.md"
fetch "hooks/session-start.sh"
fetch "legacy/hooks/archive-turn.py"
fetch "legacy/hooks/session-end.py"

if [ "$GOV_SYNC_OK" != "1" ]; then
  echo "ERROR: failed to fetch one or more files from $GOV_RAW — check network access and try again." >&2
  rm -rf "$GOV_TMP"
  exit 1
fi

cp "$GOV_TMP/CLAUDE.md" ~/.claude/CLAUDE.md
for f in session-start.sh archive-turn.py session-end.py; do
  cp "$GOV_TMP/$f" ~/.claude/hooks/"$f"
  chmod +x ~/.claude/hooks/"$f"
done
rm -rf "$GOV_TMP"

python3 - << 'PY'
import json, os
path = os.path.expanduser("~/.claude/settings.json")
try:
    with open(path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

hooks = settings.setdefault("hooks", {})

def add(event, command):
    entries = hooks.setdefault(event, [])
    item = {"hooks": [{"type": "command", "command": command}]}
    if item not in entries:
        entries.append(item)

add("SessionStart", "~/.claude/hooks/session-start.sh")
add("Stop", "~/.claude/hooks/archive-turn.py")
add("SessionEnd", "~/.claude/hooks/session-end.py")

with open(path, "w") as f:
    json.dump(settings, f, indent=2)

print("Registered SessionStart/Stop/SessionEnd hooks in", path)
PY

echo
echo "Done. From your next Claude Code CLI turn onward (in any project,"
echo "anywhere on this machine), token usage is collected automatically."
echo
echo "One thing to verify yourself: this machine needs git push access to"
echo "xilitol111/app-Governance for usage data to actually leave this"
echo "machine (the hook silently skips the push, and only the push, if that"
echo "isn't set up — collection itself never blocks on it)."
