#!/usr/bin/env python3
"""SessionEnd hook: commit + push docs/session-archive.md if it changed.

Fires automatically once per session (no explicit close needed). Bundles the
whole session's archived turns into a single commit, rather than committing on
every Stop, to keep git history readable. Best-effort: never raises, never
blocks session end (network/permission failures are swallowed).
"""
import json
import os
import subprocess
import sys


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    cwd = data.get("cwd")
    if not cwd or not os.path.isdir(cwd):
        return

    if run("git", "rev-parse", "--is-inside-work-tree", cwd=cwd).returncode != 0:
        return

    log_rel = os.path.join("docs", "session-archive.md")
    if not os.path.exists(os.path.join(cwd, log_rel)):
        return

    status = run("git", "status", "--porcelain", "--", log_rel, cwd=cwd)
    if not status.stdout.strip():
        return  # nothing new to archive this session

    run("git", "add", log_rel, cwd=cwd)
    commit = run(
        "git", "commit", "-m", "chore: archive session transcript [auto]", cwd=cwd
    )
    if commit.returncode != 0:
        return
    run("git", "push", "origin", "HEAD", cwd=cwd)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass


