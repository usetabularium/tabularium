#!/usr/bin/env python3
"""release-notice.py — the Claude Code adapter of the care-side release notice (ADR-0055 point 5,
accepted 2026-10-25; ROADMAP F7).

A SessionStart hook, matcher `startup`, wired by `checks/install-instance.sh care` only. It runs the
host-neutral check, `checks/release-notice.sh --daily`, and speaks only when a release raising MINOR or
MAJOR waits: one fixed line naming the newer release, the release in use and `/update`. Everything
else — no newer release, a patch only, an opted-out machine, a check already made today, a failure of
any kind — prints nothing and exits 0. What it prints is fixed words around two release names checked
against the release shape here again; never the remote address, git's messages or a tag's message.

Exit status is always 0: a SessionStart hook cannot block anything, and a notice never reds.
"""
import json
import os
import re
import subprocess
import sys

STRICT = re.compile(r"^v[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}$")
NAME = re.compile(r"^v[0-9]{1,9}\.[0-9]{1,9}\.[0-9]{1,9}(-[A-Za-z0-9][A-Za-z0-9.-]{0,63})?$")
TIMEOUT = 12  # seconds; the check caps its one network call at a few, the rest is local


def notice(newest, pinned, gap):
    """The operator's line and the session's context, both fixed text."""
    major = ", a major release," if gap == "major" else ""
    line = ("Tabularium %s%s is out; this folder runs %s. To update, type /update "
            "before you start care work." % (newest, major, pinned))
    # The desktop app shows systemMessage on screen (host test 2026-10-26); without this sentence the
    # session repeated the line in its first reply.
    context = ("Tabularium release notice, already shown to the operator on screen at session start: "
               + line + " Do not repeat it unless they ask about it. Adopting a release is the "
               "operator's choice, made by typing /update; never start it yourself.")
    return line, context


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if isinstance(payload, dict) and payload.get("source") not in (None, "startup"):
        return 0
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(root, "checks", "release-notice.sh")
    if not os.path.isfile(script) or os.path.islink(script):
        return 0
    try:
        run = subprocess.run(["bash", script, "--daily"], cwd=root, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=TIMEOUT)
    except Exception:
        return 0
    result = {}
    for raw in run.stdout.decode("utf-8", "replace").splitlines():
        key, sep, value = raw.partition("=")
        if sep:
            result[key] = value
    newest, pinned, gap = result.get("newest", ""), result.get("pinned", ""), result.get("gap", "")
    if (run.returncode != 1 or result.get("status") != "ok" or gap not in ("minor", "major")
            or not STRICT.match(newest) or not NAME.match(pinned)):
        return 0
    line, context = notice(newest, pinned, gap)
    print(json.dumps({
        "systemMessage": line,
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
