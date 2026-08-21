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

Threshold calibration (2026-08-21): summing cache_read_input_tokens across the
transcript's assistant entries (deduped by message.id, since each message is
logged as multiple JSONL lines) initially came out ~2.1x higher than
get_session's reported total for the same session. Traced the cause: the
get_session usage field lags — it matched this session's own *live* running
total from ~3 hours earlier, not the current moment, so it's a stale
comparison baseline, not a bug in this count. Redid the correlation using the
live local total instead: from the current five_hour window's start (a
resetsAt timestamp, reconstructed from two rate_limit_info snapshots seen
during this session) to the moment the user reported the account's usage page
at 62%, this session's own cache-read total was 26,776,894 — no other session
was active in that window. That implies ~43,200,000 tokens for this session's
own contribution at 100%. Known limitations, still unresolved: (a) single
data point — recalibrate as more (reported %, sample) pairs come in; (b) this
hook has no visibility into window resets (hooks don't receive
rate_limit_info), so cumulative-since-session-start systematically overcounts
for any session that spans a reset — biases the trigger earlier than the true
window-scoped total would, an acceptable direction to be wrong in; (c)
doesn't account for usage from other concurrent sessions or other Claude
surfaces (claude.ai, Desktop) sharing the same account-wide limit. See
NOTES-2026-08-21-handoff.md for the full investigation.

Notification behavior (revised 2026-08-21, later): originally fired once per
session at THRESHOLD_TOKENS and only *suggested* wrapping up, because moving
to a new session cost the user manual setup + lost continuity. Since
continuity is now handled automatically (CLAUDE.md sync, git-log injection,
docs/session-archive.md) and Claude can create the replacement session itself
(create_session), the user asked to raise the frequency — the switching cost
that justified infrequent, soft nudges is mostly gone. So: THRESHOLD_TOKENS
is now an *interval*, not a one-time trip wire — this fires again every time
cumulative cache-read grows by another THRESHOLD_TOKENS, not just once — and
the reason text instructs Claude to actually call create_session and hand
the user a link, not merely ask if they'd like to.
"""
import json
import os
import sys

NOTIFY_ENABLED = True
THRESHOLD_TOKENS = 5_000_000


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

    if not NOTIFY_ENABLED:
        return None

    marker_path = f"/tmp/.five-hour-notified-{session_id}"
    last_notified = 0
    if os.path.exists(marker_path):
        try:
            with open(marker_path) as f:
                last_notified = int((f.read() or "0").strip())
        except (ValueError, OSError):
            last_notified = 0

    if total - last_notified < THRESHOLD_TOKENS:
        return None  # not yet another full interval past the last nudge

    try:
        with open(marker_path, "w") as f:
            f.write(str(total))
    except OSError:
        pass

    return (
        f"[System note, not from the user: this session's cumulative cache-read "
        f"tokens just crossed another five-hour-limit watch interval "
        f"({total:,} tokens; nudging every {THRESHOLD_TOKENS:,}). Per governance "
        f"policy in CLAUDE.md: proactively create a fresh session now with the "
        f"create_session tool — inherit this environment (omit environment_id), "
        f"same repo source as this session — then briefly tell the user what's "
        f"still open here and hand them the new session's link so they can move "
        f"over whenever convenient. Continuity is already covered by "
        f"docs/session-archive.md, this repo's git history, and CLAUDE.md, so "
        f"the new session won't start blind — don't just ask whether to create "
        f"one, actually create it, since that's now a low-cost action. Then "
        f"continue this session normally if the user keeps talking here instead "
        f"of moving.]"
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
