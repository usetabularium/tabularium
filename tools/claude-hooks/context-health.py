#!/usr/bin/env python3
"""context-health — a Claude Code PostToolUse hook on Write and Edit.

WHAT IT WATCHES. The docs that enter a session's context: the contract entries `CLAUDE.md`,
`AGENTS.md` and `CONTRIBUTING.md`, plus every Markdown file one of them points to — a backticked
repository path (`_templates/INTAKE.md`) or a Markdown link target, one hop, worked out afresh on
every call — and every skill (`SKILL.md`). A file with one of those names counts anywhere. The
pointers are read from the nearest ancestor of the edited file that holds a `CLAUDE.md`.

WHEN IT SPEAKS. When an edit carries a watched doc past LIMIT lines or BYTE_LIMIT bytes, and again
each time it grows a further STEP lines or BYTE_STEP bytes, the hook asks the session to agree a workaround with the operator through
AskUserQuestion — split by role, move to the owner, cut history — or to keep the size for now. It
keeps no state: the sizes before and after the edit decide (Claude Code sends the prior
content as `originalFile`, null for a new file; without it, an Edit's own strings are counted, and
when even that cannot tell, an edit that leaves the doc over the limit counts as a crossing).

WHAT IT NEVER DOES. It cannot undo the edit (PostToolUse runs after it) and never opens a file outside
the watched set. The installer wires it in development trees only, where these docs change. Any error
is silent: a notice must never break the work it comments on.
"""
import json
import os
import re
import sys

LIMIT = 400
STEP = 50
BYTE_LIMIT = 16384  # about 4k tokens: a line count cannot see a doc of few, long lines
BYTE_STEP = 2048
BASE_NAMES = ("CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md")
WATCHED_NAMES = BASE_NAMES + ("SKILL.md",)
BACKTICK = re.compile(r"`([^`\s#]+\.md)(?:#[^`\s]*)?`")
MD_LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)\s]*)?(?:\s+\"[^\"]*\")?\)")


def lines_of(text):
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def find_root(target, fallback):
    d = os.path.dirname(target)
    while True:
        if os.path.isfile(os.path.join(d, "CLAUDE.md")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return fallback
        d = parent


def watched(root, target):
    """Is `target` watched: a file by one of the watched names, or a Markdown file a base points to?"""
    if os.path.basename(target) in WATCHED_NAMES:
        return True
    for name in BASE_NAMES:
        base = os.path.join(root, name)
        if not os.path.isfile(base):
            continue
        text = read(base)
        for ref in BACKTICK.findall(text) + MD_LINK.findall(text):
            if same(os.path.join(root, ref), target):
                return True
    return False


def size_before(tool, tool_input, tool_response, after):
    """The doc's (lines, bytes) before the edit, or None when it cannot be told."""
    if isinstance(tool_response, dict):
        original = tool_response.get("originalFile")
        if isinstance(original, str):
            return lines_of(original), len(original.encode("utf-8", "replace"))
    if tool == "Edit" and not tool_input.get("replace_all"):
        new, old = tool_input.get("new_string", ""), tool_input.get("old_string", "")
        return (after[0] - (new.count("\n") - old.count("\n")),
                after[1] - (len(new.encode("utf-8", "replace")) - len(old.encode("utf-8", "replace"))))
    return None


def band(n, limit, step):
    """-1 at or under the limit; 0 for the first `step` past it, 1 for the next, and so on."""
    return -1 if n <= limit else (n - limit - 1) // step


def main():
    limit = LIMIT
    if len(sys.argv) == 3 and sys.argv[1] == "--limit":
        limit = int(sys.argv[2])
    event = json.load(sys.stdin)
    tool = event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    target = tool_input.get("file_path")
    if tool not in ("Write", "Edit") or not isinstance(target, str):
        return
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    target = os.path.abspath(os.path.join(project, target))
    if not target.endswith(".md") or not os.path.isfile(target):
        return
    root = find_root(target, project)
    if not watched(root, target):
        return
    after = (lines_of(read(target)), os.path.getsize(target))
    before = size_before(tool, tool_input, event.get("tool_response"), after)
    limits = ((limit, STEP), (BYTE_LIMIT, BYTE_STEP))
    if before is None:
        crossed = any(a > lim for a, (lim, _) in zip(after, limits))
    else:
        crossed = any(band(a, lim, st) > band(b, lim, st) for a, b, (lim, st) in zip(after, before, limits))
    if not crossed:
        return
    shown = os.path.relpath(target, root)
    if shown.startswith(".."):
        shown = target
    reason = (
        "Context-health notice (the operator's rule for the docs that enter a session's context: "
        "CLAUDE.md, AGENTS.md, CONTRIBUTING.md, the docs they point to, and skills). %s is now %d "
        "lines and %d KB, past the limit of %d lines or %d KB. Under the rule nothing more is added to it until the operator "
        "agrees a workaround through AskUserQuestion: split by role (a section only some sessions need "
        "moves to its own doc, read when its task comes up, with a one-line pointer), move to the owner "
        "(a rule another doc owns, such as a topic doc, skill, README or ADR, moves there with a "
        "pointer), or cut history (dates, provenance and rationale go to ADRs and commit messages). "
        "The operator may also keep the size for now. No rule is dropped to get under the limit. A "
        "subagent, which cannot ask the operator, stops adding to the doc and reports this notice to "
        "its caller. The edit itself stands; the notice comes back only if the doc grows another %d "
        "lines or %d KB." % (shown, after[0], after[1] // 1024, limit, BYTE_LIMIT // 1024, STEP,
                             BYTE_STEP // 1024))
    json.dump({"decision": "block", "reason": reason}, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a notice never breaks the work it comments on
        pass
    sys.exit(0)
