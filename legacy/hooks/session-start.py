#!/usr/bin/env python3
"""SessionStart hook — cross-platform (stdlib-only) twin of session-start.sh.

session-start.sh (bash + curl) is the original and remains what the cloud
"kakeibo" environment's Setup Script installs — untouched by this file, and
still the right choice for any Linux/macOS/WSL install. This script exists
solely for native Windows (2026-08-31), where a bash script with a
`#!/bin/bash` shebang doesn't run without Git Bash, and Claude Code's hook
runner invokes commands directly rather than through a POSIX shell. Same
job, same behavior, just implemented with only the Python standard library
(urllib instead of curl, hashlib instead of sha256sum, pathlib instead of
tilde expansion) so `python session-start.py` works unmodified on Windows,
Linux, or macOS alike. See scripts/install-windows.ps1 for the installer
that wires this in, and README.md's "別マシン/別環境で使う場合" section for
the native-Windows vs. WSL distinction this split exists to handle.

Keep this in sync with session-start.sh by hand when either changes — there
is deliberately no code sharing between them, since they're each tuned to
their own platform's primitives (curl+bash text plumbing vs. urllib+json).
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

GOV_RAW = "https://raw.githubusercontent.com/xilitol111/app-Governance/main"
FILES = ["CLAUDE.md", "legacy/hooks/session-start.py", "legacy/hooks/archive-turn.py", "legacy/hooks/session-end.py"]


def read_hook_input():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    return data.get("session_id", "unknown"), data.get("source", "unknown")


def fetch(url, dest):
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            content = resp.read()
    except (urllib.error.URLError, OSError) as e:
        return False, str(e)
    with open(dest, "wb") as f:
        f.write(content)
    return True, None


def main():
    out = []
    session_id, source = read_hook_input()

    tmp_dir = tempfile.mkdtemp()
    ok = True
    last_err = None
    for rel in FILES:
        success, err = fetch(f"{GOV_RAW}/{rel}", os.path.join(tmp_dir, os.path.basename(rel)))
        if not success:
            ok = False
            last_err = err

    claude_dir = os.path.expanduser("~/.claude")
    hooks_dir = os.path.join(claude_dir, "hooks")

    if ok:
        os.makedirs(hooks_dir, exist_ok=True)
        with open(os.path.join(tmp_dir, "CLAUDE.md"), "rb") as f:
            claude_md_bytes = f.read()
        with open(os.path.join(claude_dir, "CLAUDE.md"), "wb") as f:
            f.write(claude_md_bytes)
        for name in ("session-start.py", "archive-turn.py", "session-end.py"):
            with open(os.path.join(tmp_dir, name), "rb") as src:
                content = src.read()
            with open(os.path.join(hooks_dir, name), "wb") as dst:
                dst.write(content)
        out.append("## Governance sync: OK (urllib, public repo)")

        if session_id and session_id != "unknown":
            new_hash = hashlib.sha256(claude_md_bytes).hexdigest()
            marker = os.path.join(tempfile.gettempdir(), f".claude-md-hash-{session_id}")
            if source in ("startup", "clear", "compact"):
                try:
                    with open(marker, "w") as f:
                        f.write(new_hash)
                except OSError:
                    pass
            else:
                if os.path.exists(marker):
                    try:
                        with open(marker) as f:
                            old_hash = f.read().strip()
                    except OSError:
                        old_hash = None
                    if old_hash and old_hash != new_hash:
                        out.append("")
                        out.append("## CLAUDE.md has changed on main since this session's live context was loaded")
                        out.append("This conversation is still running on an older version of app-Governance's")
                        out.append("CLAUDE.md than what's on main right now. /clear or /compact will pick up the")
                        out.append("update (see CLAUDE.md's Session scoping section).")
                else:
                    try:
                        with open(marker, "w") as f:
                            f.write(new_hash)
                    except OSError:
                        pass
    else:
        out.append("## Governance sync: FAILED")
        out.append("~/.claude/CLAUDE.md and hooks were NOT updated this session — whatever")
        out.append("was already there (possibly stale, possibly empty placeholder files) is")
        out.append("still in effect. This should only happen if this environment has no")
        out.append("outbound HTTPS at all, or GitHub itself is unreachable.")
        if last_err:
            out.append(f"fetch error: {last_err}")

    try:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    out.append("")

    def run(*args):
        return subprocess.run(args, capture_output=True, text=True)

    if run("git", "rev-parse", "--is-inside-work-tree").returncode == 0:
        out.append("## Recent commits")
        log = run("git", "log", "--oneline", "-10")
        out.append(log.stdout.rstrip("\n"))
        out.append("")
        out.append("## Latest commit (full message)")
        log1 = run("git", "log", "-1")
        out.append(log1.stdout.rstrip("\n"))
        out.append("")
        out.append("## Uncommitted changes")
        status = run("git", "status", "--short")
        out.append(status.stdout.rstrip("\n"))

    archive_path = os.path.join("docs", "session-archive.md")
    if os.path.exists(archive_path):
        with open(archive_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 4000))
            tail = f.read().decode("utf-8", errors="ignore")
        out.append("")
        out.append("## Recent session archive (tail of docs/session-archive.md)")
        out.append(tail)

    print("\n".join(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
