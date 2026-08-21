#!/usr/bin/env python3
"""Stop hook: archive each turn + track cache-read against the five-hour limit.

Fires once per turn, but does no model calls — it only parses the already-generated
transcript file, so it adds no tokens to the running conversation.

Two independent jobs, both local-only (committed later by session-end.py, not here,
to keep git history from getting noisy):

1. Append the latest assistant turn's text to docs/session-archive.md (unchanged
   from the original version of this hook).
2. Append a timestamped (cumulative cache_read_input_tokens) sample to
   docs/five-hour-samples.jsonl, and — once per session, via a decision:"block"
   reason Claude actually sees — nudge toward wrapping up once cumulative cache
   read crosses a provisional threshold.

Threshold notification is currently DISABLED (see NOTIFY_ENABLED below). While
building this, summing cache_read_input_tokens across the transcript's assistant
entries (deduped by message.id, since each message is logged as multiple JSONL
lines) still came out ~2.1x higher than the account API's own reported total for
the same session (38.6M locally vs. 18.4M from get_session), for a reason not
yet identified (possibly mid-session auto-compaction resetting the cached
prefix, possibly further duplication not yet found). Shipping a threshold
trigger on a number with an unexplained ~2x discrepancy would manufacture false
confidence, so this hook logs samples only for now — see
docs/five-hour-samples.jsonl and NOTES-2026-08-21-handoff.md for the full
investigation. Re-enable NOTIFY_ENABLED once the discrepancy is understood
and THRESHOLD_TOKENS is set against a number known to be measuring the same
thing the account's own usage page shows.
"""
import json
import os
import sys
import time

NOTIFY_ENABLED = False
THRESHOLD_TOKENS = 8_000_000


def read_transcript(transcript_path):
    with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def archive_latest_turn(lines, cwd):
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


def cumulative_cache_read(lines):
    # Each logical API response is logged as multiple JSONL lines (streaming
    # deltas); dedupe by message.id and keep the last occurrence, or every
    # duplicate's cache_read_input_tokens gets summed as if it were a separate
    # API call. Known caveat (2026-08-21): even after this fix, the total came
    # out ~2.1x higher than the account API's own reported session total, for a
    # reason not yet identified — see the module docstring. Treat this number
    # as directional/relative, not an absolute count to calibrate a threshold
    # against, until that gap is explained.
    by_id = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "assistant":
            msg = obj.get("message") or {}
            mid = msg.get("id")
            usage = msg.get("usage") or {}
            cr = usage.get("cache_read_input_tokens")
            if mid and isinstance(cr, int):
                by_id[mid] = (obj.get("timestamp"), cr)

    total = sum(cr for _, cr in by_id.values())
    last_ts = None
    if by_id:
        last_ts = max(by_id.values(), key=lambda pair: pair[0] or "")[0]
    return total, last_ts


def log_sample_and_maybe_notify(lines, cwd, session_id):
    total, ts = cumulative_cache_read(lines)
    if total == 0:
        return None

    sample_path = os.path.join(cwd, "docs", "five-hour-samples.jsonl")
    os.makedirs(os.path.dirname(sample_path), exist_ok=True)
    with open(sample_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "cache_read_cumulative": total}) + "\n")

    if not NOTIFY_ENABLED or total < THRESHOLD_TOKENS:
        return None

    marker_path = f"/tmp/.five-hour-notified-{session_id}"
    if os.path.exists(marker_path):
        return None  # already nudged once this session

    try:
        with open(marker_path, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass

    return (
        f"[System note, not from the user: this session's cumulative cache-read "
        f"tokens have crossed the provisional five-hour-limit watch threshold "
        f"({total:,} tokens, threshold {THRESHOLD_TOKENS:,}). This is a soft, "
        f"one-time heads-up per governance policy in CLAUDE.md — mention briefly "
        f"to the user that this session has grown large and, if there's a natural "
        f"stopping point, offer to wrap up with a handoff note and let them start "
        f"fresh. Do not force it or block on it — just surface the option, then "
        f"continue normally.]"
    )


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    transcript_path = data.get("transcript_path")
    cwd = data.get("cwd") or os.getcwd()
    session_id = data.get("session_id", "unknown")
    if not transcript_path or not os.path.exists(transcript_path):
        return

    lines = read_transcript(transcript_path)

    archive_latest_turn(lines, cwd)
    reason = log_sample_and_maybe_notify(lines, cwd, session_id)

    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "decision": "block",
                "reason": reason,
            }
        }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # archival must never break the session
