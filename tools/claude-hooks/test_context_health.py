#!/usr/bin/env python3
"""Fire/quiet matrix for context-health.py.

Runs the hook the way Claude Code does — PostToolUse JSON on stdin; a `"decision": "block"` object on
stdout = it spoke — against a SYNTHETIC project in a temp dir. Its CLAUDE.md points to docs by
backticked paths (plain, `./`-prefixed, with an anchor), its AGENTS.md by a Markdown link with a
title, its CONTRIBUTING.md to a topic doc that in turn points to a two-hop doc; there are two skills,
a doc nobody points to, a symlink to a watched doc and a nested project with its own CLAUDE.md.
Nothing outside the temp dir is read or written.

Exit 0 with `mismatches=0` is the pass condition. `Matrix` also runs it against a stub that never
speaks and requires mismatches (the negative control).

  python3 -m unittest tools.claude-hooks.test_context_health
  python3 tools/claude-hooks/test_context_health.py
  HOOK=/path/to/copy.py python3 tools/claude-hooks/test_context_health.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.environ.get("HOOK") or os.path.join(HERE, "context-health.py")


def body(n):
    return "".join("line %d\n" % i for i in range(n))


def wide(n_bytes):
    """Few long lines: exactly n_bytes, in 200-byte lines."""
    return ("x" * 199 + "\n") * (n_bytes // 200)


def run(root, tool, tool_input, tool_response=None, args=(), raw=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    event = {"session_id": "s1", "cwd": root, "hook_event_name": "PostToolUse",
             "tool_name": tool, "tool_input": tool_input, "tool_response": tool_response or {}}
    payload = raw if raw is not None else json.dumps(event)
    p = subprocess.run([sys.executable, HOOK] + list(args), input=payload, capture_output=True,
                       text=True, env=env, timeout=20)
    if p.returncode != 0:
        return "rc=%d" % p.returncode
    if not p.stdout.strip():
        return "quiet"
    try:
        out = json.loads(p.stdout)
    except ValueError:
        return "garbled"
    ok = out.get("decision") == "block" and "AskUserQuestion" in out.get("reason", "")
    return "fire" if ok else "garbled"


def main():
    total = bad = 0
    with tempfile.TemporaryDirectory() as root:
        root = os.path.realpath(root)
        for d in ("docs", "contributing", "skills/a", "skills/b", "sub"):
            os.makedirs(os.path.join(root, d))

        def put(rel, text):
            path = os.path.join(root, rel)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return path

        put("CLAUDE.md", "Read `docs/linked.md`, `./docs/dot.md` and `docs/anchor.md#part`.\n")
        put("AGENTS.md", 'See [the guide](docs/guide.md#start "The guide").\n')
        put("CONTRIBUTING.md", "| gates | [gates.md](contributing/gates.md) |\n")
        put("contributing/gates.md", "Then read `docs/twohop.md`.\n")
        put("sub/CLAUDE.md", "Read `inner.md`.\n")
        os.symlink(os.path.join(root, "docs", "linked.md"), os.path.join(root, "docs", "alias.md"))

        def edit(rel, before, after, tool_response=True, args=(), old="a", new="a\nb\n", **extra):
            """Leave `rel` at `after` lines and report an Edit that found it at `before` lines."""
            relative = rel.startswith("rel:")
            rel = rel[4:] if relative else rel
            path = os.path.join(root, rel)
            put(rel, body(after) if isinstance(after, int) else after)  # through a symlink: its target
            ti = dict({"file_path": rel if relative else path, "old_string": old, "new_string": new},
                      **extra)
            original = body(before) if isinstance(before, int) else before
            resp = {"filePath": path, "originalFile": original} if tool_response else {}
            return run(root, "Edit", ti, resp, args)

        put("docs/linked.md", body(10))
        cases = [
            ("crossing: 399 -> 401", "fire", lambda: edit("docs/linked.md", 399, 401)),
            ("boundary: 399 -> 400 stays at the limit", "quiet", lambda: edit("docs/linked.md", 399, 400)),
            ("boundary: 400 -> 401", "fire", lambda: edit("docs/linked.md", 400, 401)),
            ("already over, same step: 401 -> 450", "quiet", lambda: edit("docs/linked.md", 401, 450)),
            ("next step: 450 -> 451", "fire", lambda: edit("docs/linked.md", 450, 451)),
            ("shrinks while over: 460 -> 455", "quiet", lambda: edit("docs/linked.md", 460, 455)),
            ("under the limit: 10 -> 20", "quiet", lambda: edit("docs/linked.md", 10, 20)),
            ("./-prefixed pointer", "fire", lambda: edit("docs/dot.md", 399, 401)),
            ("backticked pointer with an anchor", "fire", lambda: edit("docs/anchor.md", 399, 401)),
            ("Markdown link with anchor and title", "fire", lambda: edit("docs/guide.md", 399, 401)),
            ("two hops away", "quiet", lambda: edit("docs/twohop.md", 399, 401)),  # before the next: it overwrites the topic doc's pointer
            ("CONTRIBUTING topic doc", "fire", lambda: edit("contributing/gates.md", 399, 401)),
            ("doc nobody points to", "quiet", lambda: edit("docs/loose.md", 399, 401)),
            ("first skill", "fire", lambda: edit("skills/a/SKILL.md", 399, 401)),
            ("second skill, same session", "fire", lambda: edit("skills/b/SKILL.md", 399, 401)),
            ("edited through a symlink", "fire", lambda: edit("docs/alias.md", 399, 401)),
            ("relative file_path", "fire", lambda: edit("rel:docs/linked.md", 399, 401)),
            ("nested project's own pointer", "fire", lambda: edit("sub/inner.md", 399, 401)),
            ("bytes cross 16 KB in few lines: 15000 -> 17000", "fire",
             lambda: edit("docs/linked.md", wide(15000), wide(17000))),
            ("bytes, same step: 16600 -> 18000", "quiet",
             lambda: edit("docs/linked.md", wide(16600), wide(18000))),
            ("bytes, next step: 18400 -> 18600", "fire",
             lambda: edit("docs/linked.md", wide(18400), wide(18600))),
            ("bytes under the limit: 10000 -> 12000", "quiet",
             lambda: edit("docs/linked.md", wide(10000), wide(12000))),
            ("--limit 5 on a small watched doc", "fire",
             lambda: edit("docs/linked.md", 4, 6, args=("--limit", "5"))),
            ("--limit 5, already past it", "quiet",
             lambda: edit("docs/linked.md", 6, 7, args=("--limit", "5"))),
            ("no originalFile: strings add a line", "fire",
             lambda: edit("docs/linked.md", 0, 401, tool_response=False, old="x", new="x\n")),
            ("no originalFile: strings add bytes past 16 KB", "fire",
             lambda: edit("docs/linked.md", 0, wide(16400), tool_response=False, old="x", new="x" * 300)),
            ("no originalFile: strings add nothing", "quiet",
             lambda: edit("docs/linked.md", 0, 401, tool_response=False, old="x", new="y")),
            ("prior size unknown (replace_all), left at the limit", "quiet",
             lambda: edit("docs/linked.md", 0, 400, tool_response=False, replace_all=True)),
            ("prior size unknown (replace_all), left over the limit", "fire",
             lambda: edit("docs/linked.md", 0, 401, tool_response=False, replace_all=True)),
            ("Read is never judged", "quiet",
             lambda: run(root, "Read", {"file_path": os.path.join(root, "docs/linked.md")})),
            ("malformed input", "quiet", lambda: run(root, "Edit", {}, raw="{not json")),
            # last: it overwrites CLAUDE.md, and with it the pointers the cases above rely on
            ("CLAUDE.md itself crossing", "fire", lambda: edit("CLAUDE.md", 399, 401)),
        ]
        for label, exp, call in cases:
            total += 1
            got = call()
            if got != exp:
                bad += 1
                print("MISMATCH [%s] exp=%s got=%s" % (label, exp, got))

        # Write: a new file, a rewrite that shrinks, a rewrite that grows past the limit.
        put("CLAUDE.md", "Read `docs/linked.md`.\n" + body(450))
        claude = os.path.join(root, "CLAUDE.md")
        for label, exp, resp in (
                ("Write creates CLAUDE.md over the limit", "fire",
                 {"type": "create", "originalFile": None}),
                ("Write rewrites CLAUDE.md smaller, still over", "quiet",
                 {"type": "update", "originalFile": body(500)}),
                ("Write rewrites CLAUDE.md past the limit", "fire",
                 {"type": "update", "originalFile": body(10)})):
            total += 1
            got = run(root, "Write", {"file_path": claude, "content": ""}, resp)
            if got != exp:
                bad += 1
                print("MISMATCH [%s] exp=%s got=%s" % (label, exp, got))
    print("cases=%d mismatches=%d" % (total, bad))
    return 1 if bad else 0


class Matrix(unittest.TestCase):
    def test_every_case_fires_or_stays_quiet_as_expected(self):
        self.assertEqual(main(), 0)

    def test_a_silent_stub_is_caught(self):
        # negative control: a hook that never speaks must mismatch, or the matrix proves nothing
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "silent.py")
            with open(stub, "w") as fh:
                fh.write("import sys\nsys.stdin.read()\n")
            out = StringIO()
            with mock.patch.object(sys.modules[__name__], "HOOK", stub), redirect_stdout(out):
                self.assertEqual(main(), 1)
            self.assertIn("MISMATCH", out.getvalue())


if __name__ == "__main__":
    sys.exit(main())
