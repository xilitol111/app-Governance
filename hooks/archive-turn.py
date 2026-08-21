#!/usr/bin/env python3
"""Stop hook: append the latest assistant turn's text to a local session archive.

Fires once per turn, but does no model calls — it only parses the already-generated
transcript file, so it adds no tokens to the running conversation. It only writes
locally; docs/session-archive.md is committed by session-end.py (once per session),
not by this script, to keep git history from getting noisy.
"""
import json
import os
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    transcript_path = data.get("transcript_path")
    cwd = data.get("cwd") or os.getcwd()
    if not transcript_path or not os.path.exists(transcript_path):
        return

    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    last_text = None
    last_ts = None
    last_uuid = None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "assistant":
            content = (obj.get("message") or {}).get("content") or []
            texts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            if texts:
                last_text = "\n".join(t for t in texts if t)
                last_ts = obj.get("timestamp")
                last_uuid = obj.get("uuid")
                break

    if not last_text:
        return  # this turn had no prose (tool-only turn) — nothing to archive

    log_path = os.path.join(cwd, "docs", "session-archive.md")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    marker = f"<!-- uuid:{last_uuid} -->"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            if marker in f.read():
                return  # already archived this turn

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n---\n{marker}\n**{last_ts}**\n\n{last_text}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # archival must never break the session
