#!/usr/bin/env python3
"""Deny/allow matrix for registry-read-guard.py (ADR-0050 A1 and point 9).

Runs the hook the way Claude Code does — JSON on stdin, exit 2 = deny, exit 0 = no opinion —
against a SYNTHETIC layout built in a temp dir: a home directory holding a synthetic token registry
and a synthetic private-mode identifier file, a project with both pointers and a snapshot bank, a
symlink and a hard link to the private file. Nothing real is read.

Both directions are pinned, and the allow direction matters as much: the guard is kept to a
high-confidence minimum (operator, 2026-09-16), so ordinary work — including writing prose, fixtures
and edit scripts that merely MENTION these names — must pass. Configurations:

  verified       the installer verified the split:   --private P --registry R --split-verified
  unverified     both files named, split not verified: the registry stays protected too
  registry-only  the split has not happened:          --registry R
  pointers       no arguments, main checkout: the hook reads the two pointers itself
  bare           no arguments and no pointers (a worktree an older installer never saw)

Exit 0 with `mismatches=0` is the pass condition. `Matrix` also runs it against a stub that allows
everything and requires a mismatch (the negative control).

  python3 -m unittest tools.claude-hooks.test_registry_guard
  python3 tools/claude-hooks/test_registry_guard.py
  HOOK=/path/to/copy.py python3 tools/claude-hooks/test_registry_guard.py
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.environ.get("HOOK") or os.path.join(HERE, "registry-read-guard.py")
TS = "20260901T000000Z"
WORKERS = min(16, os.cpu_count() or 4)


def run(layout, mode, tool, ti, cwd=None, raw=None, timeout=None, stderr=False):
    env = dict(os.environ)
    env["HOME"] = layout["home"]
    project = layout["bare"] if mode == "bare" else layout["proj"]
    env["CLAUDE_PROJECT_DIR"] = project
    args = {
        "verified": ["--private", layout["P"], "--registry", layout["R"], "--split-verified"],
        "unverified": ["--private", layout["P"], "--registry", layout["R"]],
        "registry-only": ["--registry", layout["R"]],
        "pointers": [],
        "bare": [],
    }[mode]
    payload = raw if raw is not None else json.dumps(
        {"tool_name": tool, "tool_input": ti, "cwd": cwd or project}).encode()
    try:
        p = subprocess.run([sys.executable, HOOK] + args, input=payload, capture_output=True, env=env,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if p.returncode == 2:
        return "D:" + p.stderr.decode("utf-8", "replace") if stderr else "D"
    if p.returncode == 0 and not p.stdout.strip():
        return "A"
    return "ERR(rc=%d):%s" % (p.returncode, p.stderr.decode("utf-8", "replace").strip()[-300:])


def make_layout(tmp):
    home = os.path.join(tmp, "home")
    ext = os.path.join(home, ".tabularium")
    os.makedirs(ext)
    reg = os.path.join(ext, "firewall-registry.sh")
    prv = os.path.join(ext, "private-mode-id.sh")
    with open(reg, "w") as fh:
        fh.write("PII_IDENTITY='zqx1aa'\n")
    with open(prv, "w") as fh:
        fh.write("PII_PRIVATE_MODE_ID='zqx9zz'\n")
    with open(os.path.join(ext, "notes.txt"), "w") as fh:
        fh.write("unrelated\n")
    os.chmod(reg, 0o600)
    os.chmod(prv, 0o600)
    proj = os.path.join(tmp, "proj")
    for d in ("checks", ".snapshots/%s/external" % TS, ".snapshots/%s/patients/x" % TS):
        os.makedirs(os.path.join(proj, d))
    for f in ("checks/check.sh", "checks/RECORD-SET", "CLAUDE.md",
              ".snapshots/%s/patients/x/profile.md" % TS,
              ".snapshots/%s/external/firewall-registry.sh" % TS,
              ".snapshots/%s/external/private-mode-id.sh" % TS):
        with open(os.path.join(proj, f), "w") as fh:
            fh.write("# synthetic\n")
    with open(os.path.join(proj, "checks", "PRIVATE-MODE-ID"), "w") as fh:
        fh.write("# path of the private-mode identifier file\n%s\n" % prv)
    with open(os.path.join(proj, "checks", "FIREWALL-REGISTRY"), "w") as fh:
        fh.write("%s\n" % reg)
    # two synthetic people: pm-a marked private-mode, plain-b not (ADR-0029 point 12)
    pm_files = {
        "patients/pm-a/profile.md": "- Private mode: national identity number \u27e8never-API\u27e9\n",
        "patients/pm-a/med/_inbox/2026-09-28__lab__panel.jpg": "\xff\xd8 synthetic jpeg\n",
        "patients/pm-a/med/_inbox/2026-09-28__lab__letter.txt": "synthetic original text\n",
        "patients/pm-a/med/_inbox/lab results.txt": "synthetic original, as it arrived\n",
        "patients/pm-a/med/_inbox/lab [1].txt": "synthetic original with a bracketed name\n",
        "patients/pm-a/med/_inbox/patients/nested/profile.md": "- Private mode: none\n",
        "patients/pm-a/med/_inbox/patients/nested/med/_inbox/copy.txt": "synthetic nested original\n",
        "patients/pm-a/med/sources/_redacted/2026-09-01__lab__panel/2026-09-01__lab__panel__page-01.png": "synthetic raster\n",
        "patients/pm-a/med/analysis/2026-09-02__analysis__review.md": "working note\n",
        "patients/pm-a/_redacted/.never-api-source-map.json": "{}\n",
        "patients/pm-c/profile.md": "- Private mode: \u27e8never-API\u27e9\n",
        "patients/pm-c/med/_inbox/2026-09-28__lab__panel.jpg": "synthetic\n",
        "patients/pm-a/med/sources/labs/2026-09-01__lab__panel.pdf": "%PDF synthetic\n",
        "patients/pm-a/med/sources/labs/2026-09-01__lab__panel.ocr.md": "derived transcription\n",
        "patients/pm-a/med/sources/README.md": "checklist\n",
        "patients/pm-a/_redacted/doc-0123456789abcdef/page-1.png": "synthetic raster\n",
        "patients/plain-b/profile.md": "- Private mode: none\n",
        "patients/plain-b/med/_inbox/2026-09-28__lab__panel.jpg": "\xff\xd8 synthetic jpeg\n",
        "tools/private-mode/redact_ids.py": "# stub\n",
        # private mode v2 (ADR-0029 control C1): the identity file, refused by name
        "patients/pm-a/.never-api-identity.json": "{}\n",
        "patients/plain-c/profile.md": "- Private mode: none\n",
        "patients/plain-c/.never-api-identity.json": "{}\n",
        # a lost marker (codex review 2026-10-01): the identity file keeps the person private
        "patients/pm-lost/profile.md": "- Private mode: none (the line was rewritten)\n",
        "patients/pm-lost/.never-api-identity.json": "{}\n",
        "patients/pm-lost/med/_inbox/2026-09-28__lab__panel.jpg": "synthetic\n",
        "patients/pm-lost/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf": "%PDF final\n",
        "patients/pm-noprof/.never-api-identity.json": "{}\n",
        "patients/pm-noprof/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf": "%PDF final\n",
        "patients/pm-a/.tmp-0a1b2c3d.never-api-identity.json": "{}\n",
        ".snapshots/%s/patients/pm-a/.never-api-identity.json" % TS: "{}\n",
        "tools/private-mode/identity.py": "# stub\n",
        # an editor's copies and backups of the filled form or the identity file (cold review 2026-11-07)
        "patients/pm-a/fill-in-form.never-api-identity.json~": "name: synthetic\n",
        "patients/pm-a/.fill-in-form.never-api-identity.json.swp": "name: synthetic\n",
        "patients/pm-a/#fill-in-form.never-api-identity.json#": "name: synthetic\n",
        "patients/pm-a/fill-in-form.never-api-identity copy.json": "name: synthetic\n",
        "patients/pm-a/fill-in-form.never-api-identity.json.txt": "name: synthetic\n",
        "patients/pm-a/fill-in-form.never-api-identity.json.save": "name: synthetic\n",
        "patients/plain-c/.never-api-identity.json.bak": "{}\n",
        # the picture of the spot a number was read from (ADR-0074): the same by-name rule
        "patients/pm-a/number-picture.never-api-identity.png": "png\n",
        "patients/pm-a/med/_inbox/scan.pdf": "%PDF original\n",
        "Desktop-like/Fill-In-Form.Never-API-Identity (2).json": "name: synthetic\n",
        # private mode v2 (C1, second part): a v2 person's final handout output is refused; a v1
        # person's (pm-a) is not
        "patients/pm-v2/profile.md": "- Private mode: synthetic ⟨never-API⟩ · ⟨private-v2 cutover=2026-10-01⟩\n",
        "patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.md": "placeholder source\n",
        "patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf": "%PDF final\n",
        "patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.txt": "final text\n",
        "patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.attest.json": "{}\n",
        "patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.factcheck.md": "PASS\n",
        "patients/pm-v2/med/handouts/drafts/2026-10-05__handout-patient__x.draft.pdf": "%PDF draft\n",
        "patients/pm-v2/med/handouts/INDEX.md": "register\n",
        "patients/pm-v2/med/handouts/.legacy-frozen": "inventory\n",
        "patients/pm-v1/profile.md": "- Private mode: synthetic ⟨never-API⟩\n",
        "patients/pm-v1/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__y.pdf": "%PDF v1 final\n",
    }
    for rel, body in pm_files.items():
        f = os.path.join(proj, rel)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(body)
    os.symlink(os.path.join(proj, "patients/pm-a/med/_inbox"), os.path.join(tmp, "inbox-link"))
    os.chmod(os.path.join(proj, "patients/pm-c/profile.md"), 0)     # unreadable: counts as marked
    # a marked person under a project folder whose name has a space: its file URL is percent-encoded
    sproj = os.path.join(tmp, "space project")
    for rel, body in (("patients/pm-s/profile.md", "- Private mode: \u27e8never-API\u27e9\n"),
                      ("patients/pm-s/med/_inbox/2026-09-28__lab__panel.jpg", "synthetic\n")):
        f = os.path.join(sproj, rel)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(body)
    surl = pathlib.Path(os.path.join(sproj, "patients/pm-s/med/_inbox/2026-09-28__lab__panel.jpg")).as_uri()
    bare = os.path.join(tmp, "bare")
    os.makedirs(os.path.join(bare, "checks"))
    link = os.path.join(tmp, "link-to-p")
    os.symlink(prv, link)
    linkdir = os.path.join(tmp, "linkdir")
    os.symlink(ext, linkdir)
    hard = os.path.join(tmp, "hard-p")
    try:
        os.link(prv, hard)
    except OSError:
        hard = None
    return {"home": home, "ext": ext, "R": reg, "P": prv, "proj": proj, "bare": bare, "link": link,
            "linkdir": linkdir, "hard": hard, "tmp": tmp, "sproj": sproj, "surl": surl}


def fill(v, L):
    if isinstance(v, str):
        for k in ("home", "ext", "R", "P", "proj", "link", "linkdir", "tmp", "sproj", "surl"):
            v = v.replace("{%s}" % k, L[k])
        return v
    if isinstance(v, dict):
        return {k: fill(x, L) for k, x in v.items()}
    if isinstance(v, list):
        return [fill(x, L) for x in v]
    return v


# (verified, unverified, command). D = denied, A = allowed.
BASH = [
    # --- the private file, every spelling of a read --------------------------------------------
    ("D", "D", "cat {P}"),
    ("D", "D", "cat ~/.tabularium/private-mode-id.sh"),
    ("D", "D", "cat $HOME/.tabularium/private-mode-id.sh"),
    ("D", "D", 'cat "$HOME"/.tabularium/private-mode-id.sh'),
    ("D", "D", "head -c 1 {home}/.TABULARIUM/Private-Mode-ID.SH"),
    ("D", "D", "cat ~/.tabularium/*"),
    ("D", "D", "cat ~/.tab*/priv*"),
    ("D", "D", "cat ~/.tabularium/private-mode-id.s?"),
    ("D", "D", "cat ~/.tabularium/{notes.txt,private-mode-id.sh}"),
    ("D", "D", "grep -rn PII ~/.tabularium"),
    ("D", "D", "grep -rn PII ~/.tab*"),                                      # a glob naming its directory
    ("D", "D", "rg PII {ext}"),
    ("D", "D", "cd ~/.tabularium && cat *"),
    ("D", "D", "cat {link}"),
    ("D", "D", "grep -rn PII {linkdir}"),
    ("D", "D", "grep -rn PII {home}/.TABULARIUM"),
    ("D", "D", "cat {linkdir}/*"),
    ("D", "D", "cp -r ~/.tabularium /tmp/x"),
    ("D", "D", "ls ~/.tabularium | xargs cat"),
    ("D", "D", "nice -n 5 cat ~/.tabularium/*"),
    ("D", "D", "diff <(cat {P}) /dev/null"),
    ("D", "D", "bash -c 'cat ~/.tabularium/private-mode-id.sh'"),
    ("D", "D", 'eval "cat ~/.tabularium/private-mode-id.sh"'),
    ("D", "D", "python3 -c \"print(open('{P}').read())\""),
    ("D", "D", "shasum -a 256 {P}"),
    ("D", "D", "cat /somewhere/else/private-mode-id.sh"),
    ("D", "D", "cat .snapshots/%s/external/private-mode-id.sh" % TS),
    ("D", "D", "cat <<EOF\nno delimiter follows\ncat {P}"),               # unterminated: never hides a line
    ("D", "D", "echo ${x//<</y}\ncat {P}"),                                # `<<` inside ${…} is no here-document
    ("D", "D", "# <<EOF\ncat {P}\nEOF"),                                    # nor inside a comment
    ("D", "D", "echo ${x//<<EOF/y}\ncat {P}\nEOF"),                          # nor inside ${…}, even with a delimiter
    ("D", "D", "cat 'unterminated ~/.tabularium/private-mode-id.sh"),
    # ...metadata over the same file is the sanctioned way to ask about it
    ("A", "A", "ls -la ~/.tabularium"),
    ("A", "A", "wc -c ~/.tabularium/private-mode-id.sh"),
    ("A", "A", "stat -f %Lp {P}"),
    ("A", "A", "test -s {P} && echo present"),
    ("A", "A", "printf '%s\\n' ~/.tabularium/*"),
    ("A", "A", "chmod 600 ~/.tabularium/private-mode-id.sh"),
    ("A", "A", "ls -la ~/.tabularium && git status --short"),
    ("A", "A", "cat {ext}/notes.txt"),
    ("A", "A", "cat {ext}/*.txt"),
    ("A", "A", "head -3 checks/*.sh"),                                        # a glob that matches nothing protected
    # --- its pointer ---------------------------------------------------------------------------
    ("D", "D", "cat checks/PRIVATE-MODE-ID"),
    ("D", "D", 'cat "$(cat checks/PRIVATE-MODE-ID)"'),
    ("D", "D", "xargs cat < checks/PRIVATE-MODE-ID"),
    ("D", "D", 'P=$(cat checks/PRIVATE-MODE-ID); head -c 1 "$P"'),
    ("D", "D", "echo `cat checks/PRIVATE-MODE-ID`"),
    ("D", "D", "echo `date #`; cat checks/PRIVATE-MODE-ID"),               # a comment ends at the backtick
    ("A", "A", "echo `date # cat checks/PRIVATE-MODE-ID`"),
    ("D", "D", "echo `cat <<EOF`\ncat {P}\nEOF"),                                # the span closes: no body
    ("D", "D", "echo $'it\\'s # x'; cat {P}"),                                   # `\'` does not end `$'…'`
    # refused though harmless: a backtick in a search pattern is judged as code (use the Grep tool)
    ("D", "D", "grep -rn '`cat checks/PRIVATE-MODE-ID`' tools"),
    ("D", "D", "grep -rn \"`cat checks/PRIVATE-MODE-ID`\" tools"),
    ("D", "D", "grep -rn \"$(cat checks/PRIVATE-MODE-ID)\" tools"),
    ("D", "D", "grep -n '`x`' checks/PRIVATE-MODE-ID"),
    ("D", "D", "cat /main/checkout/checks/PRIVATE-MODE-ID"),
    ("A", "A", "test -f checks/PRIVATE-MODE-ID && echo yes"),
    ("A", "A", "ls -la checks/PRIVATE-MODE-ID"),
    # --- names that are not paths: a pattern, a message ----------------------------------------
    ("A", "A", "grep -rn PRIVATE-MODE-ID checks"),
    ("A", "A", "git grep -n PII_PRIVATE_MODE_ID"),
    ("A", "A", 'git commit -m "document the PRIVATE-MODE-ID pointer and ~/.tabularium/private-mode-id.sh"'),
    ("A", "A", 'echo "the private-mode identifier stays out of every session"'),
    # --- the token registry: readable once the split is verified ---------------------------------
    ("A", "D", "cat {R}"),
    ("A", "D", "grep -n PII_BRAND {R}"),
    ("A", "D", 'cat "$(cat checks/FIREWALL-REGISTRY)"'),
    ("A", "D", "cat checks/FIREWALL-REGISTRY"),
    ("A", "D", "cat .snapshots/%s/external/firewall-registry.sh" % TS),
    ("A", "A", "grep -rn FIREWALL-REGISTRY checks | head -5"),
    # --- DATA: here-document bodies and redirection targets are written, not read ----------------
    ("A", "A", "cat > /tmp/note.md <<'EOF'\nthe file lives at ~/.tabularium/private-mode-id.sh\ncat checks/PRIVATE-MODE-ID\nEOF"),
    ("A", "A", "git commit -F - <<'EOF'\nMoved to {P}; see checks/FIREWALL-REGISTRY\nEOF"),
    ("A", "A", "python3 - <<'PY'\nsrc = open('t.py').read()\nsrc = src.replace('cat ~/.tabularium/private-mode-id.sh', 'bash {R}')\nPY"),
    ("A", "A", "printf '%s\\n' {tmp}/syn/registry.sh > {tmp}/syn/FIREWALL-REGISTRY && bash checks/relay-scan.sh draft.md"),
    ("A", "A", "printf '%s\\n' {tmp}/syn/pm.sh > {tmp}/syn/PRIVATE-MODE-ID"),
    ("A", "A", "cat draft.md > {tmp}/syn/PRIVATE-MODE-ID"),
    # --- ordinary work stays ordinary ------------------------------------------------------------
    ("A", "A", "git status --short"),
    ("A", "A", "bash checks/check.sh 2>&1 | tail -3"),
    ("A", "A", "bash checks/relay-scan.sh draft.md"),
    ("A", "A", 'PUBLISH_DEST="$(mktemp -d)/t" bash checks/publish-skeleton.sh'),
    ("A", "A", "python3 -m evals.harness.containment"),
    ("A", "A", "grep -rn 'x' ."),
    ("A", "A", "cat checks/check.sh"),
    ("A", "A", "cut -d / -f 1 checks/RECORD-SET"),
    ("A", "A", "awk -F / '{print $1}' checks/RECORD-SET"),
    ("A", "A", "cat CLAUDE.md; ls ."),
    ("A", "A", "cat 'unterminated"),
    ("A", "A", "cat _inbox/2026-09-14__handover__38-private-mode-id-split.md"),
    ("A", "A", "cp .snapshots/%s/patients/x/profile.md /tmp/p.md" % TS),
    ("A", "A", "git log --oneline -5 && git diff --stat"),
    # --- independent review of PR #14 (2026-09-16): shapes inside the stated rules that passed ------
    ("D", "D", "bash -lc 'cat {P}'"),                                          # combined flags
    ("D", "D", "sh -ec 'cat ~/.tabularium/private-mode-id.sh'"),
    ("D", "D", "timeout 5 bash -c 'cat {P}'"),                                 # an interpreter behind a wrapper
    ("D", "D", "env bash -c 'cat {P}'"),
    ("D", "D", "perl -le 'open F,\"<\",\"{P}\"; print <F>'"),
    ("A", "D", "bash -lc 'cat {R}'"),
    ("D", "D", "cat <<EOF\n$(cat {P})\nEOF"),                                  # an UNQUOTED body expands $(…)
    ("A", "A", "cat <<'EOF'\n$(cat {P})\nEOF"),                                # a quoted body does not
    ("D", "D", "echo $(<~/.tabularium/private-mode-id.sh)"),                   # operators glued by the tokeniser
    ("D", "D", "printf '%s\\n' $(<{P})"),
    ("D", "D", "ls -la $(<checks/PRIVATE-MODE-ID)"),
    ("D", "D", "(ls ~/.tabularium); cat ~/.tabularium/private-mode-id.sh"),
    ("D", "D", "(cd ~/.tabularium && ls)&& cat ~/.tabularium/private-mode-id.sh"),
    ("A", "D", "echo $(<{R})"),
    ("D", "D", "cd -P ~/.tabularium && cat private-mode-id.sh"),
    ("D", "D", "cat $SOMEWHERE/private-mode-id.sh"),                            # an unexpanded variable keeps its name
    ("D", "D", 'P=~/.tabularium/private-mode-id.sh; cat "$P"'),                # one assignment hop
    ("D", "D", "file -f {P}"),                                                 # `file -f` prints the file's lines
    ("D", "D", "(( x = 1 << 2 ))\ncat {P}\n2"),                                # `((…))` is no here-document
    ("D", "D", "find ~/.tabularium -type f -exec cat {} +"),
    ("D", "D", "git diff --no-index checks/PRIVATE-MODE-ID /dev/null"),
    ("D", "D", "git hash-object {P}"),
    ("D", "D", "ls ~/.tabularium | while read f; do cat \"$f\"; done"),
    ("D", "D", "grep -f checks/PRIVATE-MODE-ID notes.txt"),                    # -f names a file that is read
    # ...and ordinary build work the review found denied
    ("A", "A", "grep -rn 'checks/PRIVATE-MODE-ID' ."),                         # a pattern is not a path
    ("A", "A", "grep -rn '~/.tabularium/private-mode-id.sh' checks"),
    ("A", "A", "grep -e checks/PRIVATE-MODE-ID -r ."),
    ("A", "A", "rg -n -E utf8 'checks/PRIVATE-MODE-ID' tools"),
    ("A", "A", "git log -S 'checks/PRIVATE-MODE-ID'"),
    ("A", "A", "git check-ignore -v checks/PRIVATE-MODE-ID"),
    ("A", "A", "git status --short --ignored checks/PRIVATE-MODE-ID"),
    ("A", "A", "ls -la ~/.tabularium | head -5"),
    ("A", "A", "ls -la ~/.tabularium | grep private"),
    ("A", "A", "wc -c ~/.tabularium/* | tail -1"),
    ("A", "A", "find ~/.tabularium -maxdepth 1 -type f -perm -044"),
    ("A", "A", "bash -lc 'bash checks/check.sh'"),
    ("A", "A", "(cd checks && ls); git status"),
    ("A", "A", "cat PRIVATE-MODE-ID"),                                         # a bare word is a path only where it resolves
    # --- Codex review of PR #14 (2026-09-16): the shell runs a $(…) in ANY redirection operand -------
    ("D", "D", 'cat <<<"$(cat {P})"'),                                          # a here-string's $(…) prints the file
    ("D", "D", 'cat <<<"`cat {P}`"'),
    ("D", "D", 'cat <<<"$(<{P})"'),
    ("D", "D", 'wc -c <<<"$(cat ~/.tabularium/private-mode-id.sh)"'),          # a metadata head does not launder it
    ("A", "D", 'cat <<<"$(cat {R})"'),
    ("A", "D", 'cat <<<"$(cat checks/FIREWALL-REGISTRY)"'),
    ("D", "D", 'cat < "$(cat checks/PRIVATE-MODE-ID)"'),                        # an input operand computed by a read
    ("D", "D", 'echo x > "$(cat checks/PRIVATE-MODE-ID)"'),                      # so is a WRITE target: the $(…) reads
    ("D", "D", 'echo x >> "`cat checks/PRIVATE-MODE-ID`"'),
    ("D", "D", 'ls 2> "$(<checks/PRIVATE-MODE-ID)"'),
    ("D", "D", 'cat <<<"$(head -c 9 $(pwd)/.tabularium/private-mode-id.sh)"'),  # the outer span, past a nested one
    ("D", "D", 'cat <<<"$(cat {P}"'),                                            # a span that never closes runs on
    ("A", "A", 'cat <<<"checks/PRIVATE-MODE-ID"'),                               # a here-string's TEXT is data
    ("A", "A", 'cat <<<"the file is ~/.tabularium/private-mode-id.sh"'),
    ("A", "A", 'grep -c x <<<"$(date) see checks/PRIVATE-MODE-ID"'),             # a $(…) that reads nothing, beside prose
    ("A", "A", 'printf x > "$(mktemp -d)/PRIVATE-MODE-ID"'),                     # a write target computed harmlessly
    ("A", "A", 'echo hi 2>"$(mktemp)"'),
    # ...and a shell comment is not an operand (removed quote-aware; a real read after it still is)
    ("A", "A", "cat checks/README.md # documents checks/PRIVATE-MODE-ID"),
    ("A", "A", "cat checks/check.sh #checks/PRIVATE-MODE-ID"),
    ("A", "A", "ls;# see ~/.tabularium/private-mode-id.sh and checks/FIREWALL-REGISTRY"),
    ("A", "A", "(ls)# cat checks/PRIVATE-MODE-ID"),
    ("D", "D", "ls # note\ncat checks/PRIVATE-MODE-ID"),                         # a comment ends at its line
    ("D", "D", "echo x # it's noted\ncat checks/PRIVATE-MODE-ID"),               # a quote inside a comment opens nothing
    ("D", "D", "printf '%s#%s\\n' a b; cat {P}"),                                # a # inside quotes is part of the word
    ("D", "D", 'echo "#"; cat {P}'),
    ("D", "D", "echo 'a\n# b'; cat checks/PRIVATE-MODE-ID"),                     # a quote spans lines; no comment inside
    ("D", "D", "echo ${#x}$# x#y; cat checks/PRIVATE-MODE-ID"),                  # ${#x}, $# and a#b are not comments
    ("A", "A", "cat > notes.md <<'EOF'\nit's a note\nEOF\ncat x # checks/PRIVATE-MODE-ID"),  # a body's quote spans nothing
    # --- 2026-09-28 finding: a here-document a shell runs is a script, judged like the line --------------
    ("D", "D", "bash -s <<'EOF'\nDEV={proj}\nR=\"$(cat \"$DEV/checks/PRIVATE-MODE-ID\")\"\necho \"${#R}\"\nEOF"),
    ("A", "D", "bash -s <<'EOF'\nDEV={proj}\nR=\"$(cat \"$DEV/checks/FIREWALL-REGISTRY\")\"\necho \"${#R}\"\nEOF"),
    ("D", "D", "bash -c 'DEV={proj}; R=\"$(cat \"$DEV/checks/PRIVATE-MODE-ID\")\"; echo ${#R}'"),  # variable + suffix
    ("A", "D", "bash -c 'DEV={proj}; R=\"$(cat \"$DEV/checks/FIREWALL-REGISTRY\")\"; echo ${#R}'"),
    ("D", "D", "DEV={proj}; cat \"$DEV/checks/PRIVATE-MODE-ID\""),
    ("D", "D", "bash -s <<'EOF'\ncat {P}\nEOF"),
    ("D", "D", "cat <<'EOF' | sh\ncat ~/.tabularium/private-mode-id.sh\nEOF"),         # piped into a shell
    ("D", "D", "timeout 9 zsh <<-'EOF'\n\tcat checks/PRIVATE-MODE-ID\n\tEOF"),
    ("D", "D", "cd checks && bash <<'EOF'\ncat PRIVATE-MODE-ID\nEOF"),                  # the line's `cd` carries in
    ("A", "A", "bash -s <<'EOF'\ngit status --short\nls -la checks/PRIVATE-MODE-ID\nEOF"),  # judged, not banned
    ("A", "A", "bash -s <<'EOF'\ngrep -rn 'checks/PRIVATE-MODE-ID' .\nEOF"),
    ("A", "A", "bash -s <<'EOF'\ncat > n.md <<'IN'\nsee checks/PRIVATE-MODE-ID\nIN\nEOF"),  # a nested body stays data
    ("A", "A", "cat > n.md <<'EOF' && bash checks/check.sh\nsee ~/.tabularium/private-mode-id.sh\nEOF"),  # not its pipeline
    ("A", "A", "cat > n.md <<'sh'\ncat {P}\nsh"),                                      # a delimiter is no shell
    ("D", "D", "bash -s \\\n  -- a b <<'EOF'\ncat checks/PRIVATE-MODE-ID\nEOF"),         # `\`-newline continues
    ("D", "D", "cat <<'EOF' \\\n  | bash\ncat {P}\nEOF"),
    ("D", "D", "ls # see \\\ncat checks/PRIVATE-MODE-ID"),                              # …but not in a comment
    ("D", "D", "bash -s <<'EOF'\ncat checks/PRIVATE-MODE-ID\nEOF\necho 'oops"),          # an unparsable line after
    ("D", "D", "bash <<<'cat checks/PRIVATE-MODE-ID'"),                                # a here-string a shell runs
    ("A", "D", "sh <<< \"cat {R} | wc -c\""),
    ("D", "D", "$SHELL -s <<'EOF'\ncat {P}\nEOF"),
    ("D", "D", "bash -euo pipefail <<'EOF'\ncat {P}\nEOF"),                             # an option's value is no script
    ("D", "D", "if true; then bash -s <<'EOF'\ncat {P}\nEOF\nfi"),                      # after a reserved word
    ("D", "D", "{ bash -s <<'EOF'\ncat checks/PRIVATE-MODE-ID\nEOF\n} 2>&1"),
    ("D", "D", "gtimeout 60 bash -s <<'EOF'\ncat {P}\nEOF"),
    ("D", "D", "sudo -s <<'EOF'\ncat {P}\nEOF"),
    ("D", "D", "bash /dev/fd/0 <<'EOF'\ncat {P}\nEOF"),
    ("D", "D", "cd checks; (cd s0 && true); (cd s1 && true); (cd s2 && true); (cd s3 && true); "
               "(cd s4 && true); (cd s5 && true); cat PRIVATE-MODE-ID"),                 # a capped `cd` keeps it
    ("D", "D", "source /dev/stdin <<'EOF'\ncat {P}\nEOF"),
    ("A", "A", "bash <<<'git status --short'"),
    ("A", "A", "bash checks/relay-scan.sh /dev/stdin <<'EOF'\nthe file lives at ~/.tabularium/private-mode-id.sh\nEOF"),
    ("A", "A", "cat <<'EOF' | bash checks/relay-scan.sh /dev/stdin\nsee checks/PRIVATE-MODE-ID\nEOF"),  # stdin is data
    ("A", "A", "bash -c 'cat > n.md' <<'EOF'\nsee ~/.tabularium/private-mode-id.sh\nEOF"),
    ("A", "A", "bash -s 3<<'DATA' <<'EOF'\nsee ~/.tabularium/private-mode-id.sh\nDATA\nls\nEOF"),  # fd 3 is no script
    ("A", "A", "grep -c sh <<'EOF'\nsee ~/.tabularium/private-mode-id.sh\nEOF"),       # a shell word as argument
    ("A", "A", "cat > n.md <<'EOF'  # notes for the sh wrapper\nsee ~/.tabularium/private-mode-id.sh\nEOF"),
    # --- 2026-09-28 finding: a here-document inside `$(…)`, even within double quotes ------------------
    # ...the commit-message idiom: a bare `cat` makes the body a string, and a string is data
    ("A", "A", "git add -A && git commit -m \"$(cat <<'EOF'\nread-guard: fix (see checks/PRIVATE-MODE-ID) — "
               "it's \"quoted\" `tick` $(not run)\nEOF\n)\" && git push -u origin HEAD"),
    ("A", "A", "gh pr create --title \"$(cat <<'T'\ntitle\nT\n)\" --body \"$(cat <<'B'\n- names "
               "~/.tabularium/private-mode-id.sh\n)\"\nB\n)\""),                         # two bodies; `)"` in one
    ("A", "A", "git commit -m \"$(cat <<'EOF'\nsee checks/PRIVATE-MODE-ID\nEOF\n)\" && cat > n.md <<'EOF2'\n"
               "cat checks/PRIVATE-MODE-ID\nEOF2"),                                      # the quote closes after
    ("A", "A", "git commit -m \"$(cat - <<-'EOF'\n\tsee checks/PRIVATE-MODE-ID\n\tEOF\n)\""),
    ("A", "A", "git commit -m \"$(cat <<EOF\nsee checks/PRIVATE-MODE-ID on $(date +%F)\nEOF\n)\""),
    ("A", "A", "M=\"$(cat <<'EOF'\nsee checks/PRIVATE-MODE-ID\nEOF\n)\"; git commit -m \"$M\""),
    ("A", "A", "bash -s <<'OUT'\ngit commit -m \"$(cat <<'IN'\nsee checks/PRIVATE-MODE-ID\nIN\n)\"\nOUT"),
    ("A", "A", "printf $'it\\'s\\n' && cat > n.md <<'EOF'\ncat checks/PRIVATE-MODE-ID\nEOF"),  # $'…' escapes a quote
    ("A", "A", "git commit -m \"$(cat <<'EOF'\nsee checks/FIREWALL-REGISTRY and {R}\nEOF\n)\""),
    ("A", "A", "git commit -m \"$( (true); cat <<'EOF'\nsee checks/PRIVATE-MODE-ID\nEOF\n)\""),  # a subshell inside
    # ...a real read elsewhere in the line, or in the substitution, still counts
    ("D", "D", "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\" && cat {P}"),
    ("D", "D", "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\" \"$(cat checks/PRIVATE-MODE-ID)\""),
    ("D", "D", "echo \"$(cat <<'EOF'\nmsg\nEOF\ncat {P})\""),                               # after the body
    ("D", "D", "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\"\ncat checks/PRIVATE-MODE-ID"),
    ("D", "D", "x=\"$(cat <<EOF\n$(cat {P})\nEOF\n)\""),                                     # an unquoted body runs $(…)
    # ...so does the string, where it is a protected path or where it is run or read as names
    ("D", "D", "cat \"$(cat <<'EOF'\n{P}\nEOF\n)\""),
    ("D", "D", "cat \"$(cat <<-'EOF'\n\t{P}\n\tEOF\n)\""),                              # `<<-` strips the tab
    ("D", "D", "cat $(cat <<'EOF'\n~/.tabularium/private-mode-id.sh\nEOF\n)"),
    ("D", "D", "bash -c \"$(cat <<'EOF'\ncat {P}\nEOF\n)\""),
    ("D", "D", "bash -c $(cat <<'EOF'\ncat {P}\nEOF\n)"),
    ("D", "D", "caffeinate -i bash -c \"$(cat <<'EOF'\ncat {P}\nEOF\n)\""),            # behind an unlisted wrapper
    ("D", "D", "echo \"$(cat <<'EOF'\ncat checks/PRIVATE-MODE-ID\nEOF\n)\" | $SHELL"),
    ("D", "D", "xargs cat <<<\"$(cat <<'EOF'\n{ext}/notes.txt\n{P}\nEOF\n)\""),
    ("D", "D", "source <(cat <<'EOF'\ncat {P}\nEOF\n)"),
    ("D", "D", "bash -s $(echo a; echo b) <<'EOF'\ncat {P}\nEOF"),                   # `;` in `$(…)`: not the end
    ("A", "D", "cat \"$(cat <<'EOF'\n{R}\nEOF\n)\""),
    # ...any reader but a bare `cat`: a shell runs it, and inside double quotes the body stays in its word
    ("D", "D", "x=\"$(bash -s <<'EOF'\ncat {P}\nEOF\n)\""),
    ("D", "D", "git commit -m \"$(cat <<'EOF' | bash\ncat {P}\nEOF\n)\""),
    ("D", "D", "x=\"$(python3 - <<'PY'\nprint(open('{P}').read())\nPY\n)\""),
    ("D", "D", "x=\"$(xargs cat <<'EOF'\n{P}\nEOF\n)\""),
    # ...and no line is taken for a body that is not one
    ("D", "D", "echo \"[$(cat <<'EOF')]\"\ncat {P}\nEOF"),                              # closed on its own line:
    ("D", "D", "echo $(cat <<'EOF')\ncat {P}\nEOF"),                                    # the next line is a command
    ("D", "D", "echo \"x\ncat <<EOF\n\"\ncat {P}\nEOF"),                                 # `<<` inside a string
    ("D", "D", "echo \"$(( cat <<EOF\n))\"\ncat {P}\nEOF"),                               # arithmetic in quotes
]

FILES = [
    ("D", "D", "Read", {"file_path": "{P}"}),
    ("D", "D", "Read", {"file_path": "~/.tabularium/private-mode-id.sh"}),
    ("D", "D", "Read", {"file_path": "{link}"}),
    ("D", "D", "Read", {"file_path": "{home}/.TABULARIUM/PRIVATE-MODE-ID.SH"}),
    ("D", "D", "Read", {"file_path": "checks/PRIVATE-MODE-ID"}),
    ("D", "D", "Read", {"file_path": ".snapshots/%s/external/private-mode-id.sh" % TS}),
    ("D", "D", "Edit", {"file_path": "{P}", "old_string": "a", "new_string": "b"}),
    ("D", "D", "Write", {"file_path": "checks/PRIVATE-MODE-ID", "content": "x"}),
    ("A", "D", "Read", {"file_path": "{R}"}),
    ("A", "D", "Read", {"file_path": "checks/FIREWALL-REGISTRY"}),
    ("A", "A", "Read", {"file_path": "checks/check.sh"}),
    ("A", "A", "Read", {"file_path": "_inbox/2026-09-14__handover__38-private-mode-id-split.md"}),
    ("A", "A", "Read", {"file_path": ".snapshots/%s/patients/x/profile.md" % TS}),
    ("D", "D", "Grep", {"pattern": "PII", "path": "{ext}", "output_mode": "content"}),
    ("A", "A", "Grep", {"pattern": "PII", "path": "{ext}"}),
    ("A", "A", "Grep", {"pattern": "PII", "path": "{ext}", "output_mode": "content", "glob": "*.txt"}),
    ("A", "D", "Grep", {"pattern": "PII", "path": "{R}", "output_mode": "content"}),
    ("A", "A", "Grep", {"pattern": "PII", "output_mode": "content"}),
    ("A", "A", "Grep", {"pattern": "PII", "path": "checks", "output_mode": "content"}),
    ("D", "D", "Grep", {"pattern": "PII", "path": "{ext}", "output_mode": "content", "glob": "**/*.sh"}),
    ("D", "D", "Grep", {"pattern": "PII", "path": "{ext}", "output_mode": "content", "glob": "!*.txt"}),
    # other tools that run a shell command are judged like Bash
    ("D", "D", "Monitor", {"command": "cat {P}", "description": "x", "timeout_ms": 1000}),
    ("D", "D", "mcp__terminal__run_in_terminal", {"command": "cat ~/.tabularium/private-mode-id.sh"}),
    ("A", "A", "Monitor", {"command": "tail -f /tmp/build.log", "description": "x", "timeout_ms": 1000}),
]

# Configurations without installer arguments, or before the split: (mode, expectation, tool, input)
OTHER = [
    ("pointers", "D", "Bash", {"command": "cat {P}"}),
    ("pointers", "D", "Bash", {"command": "cat {R}"}),
    ("pointers", "D", "Bash", {"command": "grep -rn PII ~/.tabularium"}),
    ("pointers", "D", "Read", {"file_path": "{R}"}),
    ("pointers", "A", "Bash", {"command": "grep -rn x checks"}),
    ("pointers", "D", "Bash", {"command": "bash -s <<'EOF'\nDEV={proj}\ncat \"$DEV/checks/FIREWALL-REGISTRY\"\nEOF"}),
    ("registry-only", "D", "Bash", {"command": "bash -s <<'EOF'\ncat {R}\nEOF"}),
    ("bare", "D", "Bash", {"command": "bash -s <<'EOF'\ncat checks/PRIVATE-MODE-ID\nEOF"}),
    ("bare", "A", "Bash", {"command": "git commit -m \"$(cat <<'EOF'\nsee checks/PRIVATE-MODE-ID\nEOF\n)\""}),
    ("bare", "D", "Bash", {"command": "cat \"$(cat <<'EOF'\nchecks/PRIVATE-MODE-ID\nEOF\n)\""}),
    ("pointers", "A", "Bash", {"command": "gh pr create --body \"$(cat <<'EOF'\nsee checks/FIREWALL-REGISTRY\nEOF\n)\""}),
    ("registry-only", "D", "Bash", {"command": "cat {R}"}),
    ("registry-only", "D", "Bash", {"command": "grep -rn PII ~/.tabularium"}),
    ("registry-only", "D", "Bash", {"command": "cat ~/.tabularium/private-mode-id.sh"}),
    ("registry-only", "D", "Bash", {"command": "cat checks/FIREWALL-REGISTRY"}),
    ("bare", "D", "Bash", {"command": "cat checks/PRIVATE-MODE-ID"}),
    ("bare", "D", "Bash", {"command": "cat ~/.tabularium/private-mode-id.sh"}),
    ("bare", "D", "Bash", {"command": "cat {R}"}),
    ("bare", "A", "Bash", {"command": "bash checks/check.sh"}),
]

# A private-mode person's originals (ADR-0029 point 12), judged the same in every
# configuration. (expected, tool, input); paths relative to the project unless {proj}/{tmp} given.
PMA = "patients/pm-a/med"
PM = [
    # --- never to a model: the file tools, a content search, a connector ---------------------------
    ("D", "Read", {"file_path": "{proj}/%s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "Read", {"file_path": "%s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Read", {"file_path": "{proj}/%s/sources/labs/2026-09-01__lab__panel.pdf" % PMA, "pages": "1"}),
    # the same file only where the filesystem ignores case (macOS by default); elsewhere it is not
    # the file, reading it fails, and allowing it is right — "D~" resolves per filesystem below
    ("D~", "Read", {"file_path": "{proj}/PATIENTS/pm-a/MED/_inbox/2026-09-28__lab__panel.jpg"}),
    ("D", "Read", {"file_path": "{tmp}/inbox-link/2026-09-28__lab__panel.jpg"}),
    ("D", "Grep", {"pattern": "[0-9]{11}", "path": "%s/sources" % PMA, "output_mode": "content"}),
    ("D", "Grep", {"pattern": "x", "path": "%s/_inbox/2026-09-28__lab__letter.txt" % PMA, "output_mode": "content"}),
    ("D", "mcp__PDF_Tools__read_pdf_content", {"path": "{proj}/%s/sources/labs/2026-09-01__lab__panel.pdf" % PMA}),
    ("D", "mcp__pdf-viewer__display_pdf", {"url": "file://{proj}/%s/sources/labs/2026-09-01__lab__panel.pdf" % PMA}),
    ("D", "Bash", {"command": "tesseract %s/_inbox/2026-09-28__lab__panel.jpg stdout" % PMA}),
    ("D", "Bash", {"command": "pdftotext %s/sources/labs/2026-09-01__lab__panel.pdf -" % PMA}),
    ("D", "Bash", {"command": "cat %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "base64 < %s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "Bash", {"command": "cat %s/_inbox/*" % PMA}),
    ("D", "Bash", {"command": "cd %s/_inbox && strings 2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "Bash", {"command": "F=%s/_inbox/2026-09-28__lab__panel.jpg; xxd \"$F\"" % PMA}),
    ("D", "Bash", {"command": "grep -ra 12 %s/sources" % PMA}),
    ("D", "Bash", {"command": "find %s/_inbox -type f | xargs cat" % PMA}),
    ("D", "Bash", {"command": "python3 -c \"print(open('%s/_inbox/2026-09-28__lab__letter.txt').read())\"" % PMA}),
    # copying prints nothing, so a name produced by `$(ls …)` for `cp` is allowed like a plain `cp`
    ("A", "Bash", {"command": "cp \"$(ls %s/_inbox/*.jpg | head -1)\" /tmp/x.jpg" % PMA}),
    # review round 1 (2026-09-30): a negation-only or mixed glob; a quoted name with a space; file URLs
    ("D", "Grep", {"pattern": "x", "path": "%s/_inbox" % PMA, "glob": "!*.md", "output_mode": "content"}),
    ("D", "Grep", {"pattern": "x", "path": "%s/_inbox" % PMA, "glob": "{*.md,*.txt}", "output_mode": "content"}),
    ("D", "Bash", {"command": "cat \"%s/_inbox/lab results.txt\"" % PMA}),
    ("D", "Bash", {"command": "cd %s/_inbox && cat 'lab results.txt'" % PMA}),
    ("D", "Bash", {"command": "python3 -c \"print(open('%s/_inbox/lab results.txt').read())\"" % PMA}),
    ("D", "mcp__pdf-viewer__display_pdf", {"url": "{surl}"}),
    ("D", "mcp__pdf-viewer__display_pdf", {"url": "file://localhost{proj}/%s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "mcp__pdf-viewer__display_pdf", {"url": "file:{proj}/%s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    # review round 2 (2026-09-30): searches from above a lane, `**`, interpreter here-documents, paths
    # built from a variable, bracketed names, uploads, the file-name map, parse failures, fail-closed
    ("D", "Grep", {"pattern": "eGFR", "path": "patients/pm-a", "output_mode": "content"}),
    ("D", "Grep", {"pattern": "eGFR", "path": "patients", "output_mode": "content"}),
    ("D", "Bash", {"command": "grep -rn eGFR patients/pm-a"}),
    ("D", "Bash", {"command": "grep -rn eGFR patients/pm-a/med"}),
    ("D", "Bash", {"command": "find patients/pm-a -name '*.jpg' | while read f; do tesseract \"$f\" stdout; done"}),
    ("D", "Bash", {"command": "cat $(find patients/pm-a -name '*.txt')"}),
    ("D", "mcp__PDF_Tools__search_pdf_text", {"directory": "{proj}/patients/pm-a"}),
    ("D", "Bash", {"command": "tesseract patients/pm-a/**/*.jpg stdout"}),
    ("D", "Bash", {"command": "for f in patients/pm-a/**/*.txt; do cat \"$f\"; done"}),
    ("D", "Bash", {"command": "python3 - <<'EOF'\nprint(open('%s/_inbox/lab results.txt').read())\nEOF" % PMA}),
    ("D", "Bash", {"command": "P=patients/pm-a; cat $P/med/_inbox/2026-09-28__lab__letter.txt"}),
    ("D", "Bash", {"command": "H=pm-a; cat \"patients/$H/med/_inbox/2026-09-28__lab__letter.txt\""}),
    ("D", "Bash", {"command": "cat \"%s/_inbox/lab [1].txt\"" % PMA}),
    ("D", "Artifact", {"action": "publish", "asset": True, "url": "https://claude.ai/artifact/x", "file_path": "%s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "SendUserFile", {"files": ["{proj}/%s/sources/labs/2026-09-01__lab__panel.pdf" % PMA], "status": "normal"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/_redacted/.never-api-source-map.json"}),
    ("D", "Bash", {"command": "cat patients/pm-a/_redacted/.never-api-source-map.json"}),
    ("D", "Bash", {"command": "cat %s/_inbox/2026-09-28__lab__letter.txt; echo $'it\\'s'" % PMA}),
    ("D", "mcp__pdf-viewer__display_pdf", {"url": "file://[{proj}/%s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "Bash", {"command": "python3 -m json.tool %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Read", {"file_path": "{proj}/%s/_inbox/patients/nested/med/_inbox/copy.txt" % PMA}),
    ("D!", "Read", {"file_path": "{proj}/patients/pm-c/med/_inbox/2026-09-28__lab__panel.jpg"}),
    # review round 3 (2026-09-30): digests only in hashing mode; conversions only into a lane
    ("D", "Bash", {"command": "md5 -p < %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "md5 -qp < %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "shasum -c %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "sha256sum --check %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "magick %s/_inbox/2026-09-28__lab__panel.jpg /tmp/local-input.pdf" % PMA}),
    ("D", "Bash", {"command": "magick %s/_inbox/2026-09-28__lab__panel.jpg txt:-" % PMA}),
    ("D", "Bash", {"command": "magick %s/_inbox/2026-09-28__lab__panel.jpg -print '%%c' %s/_inbox/p.pdf" % (PMA, PMA)}),
    ("D", "Bash", {"command": "magick identify -verbose %s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("D", "Bash", {"command": "img2pdf %s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    # --- allowed: names, filing, hashing, the operator's own screen, the pipeline, derived text -----
    ("A", "Read", {"file_path": "{proj}/%s/sources/labs/2026-09-01__lab__panel.ocr.md" % PMA}),
    ("A", "Read", {"file_path": "{proj}/%s/sources/README.md" % PMA}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-a/profile.md"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-a/_redacted/doc-0123456789abcdef/page-1.png"}),
    ("A", "Read", {"file_path": "{proj}/patients/plain-b/med/_inbox/2026-09-28__lab__panel.jpg"}),
    ("A", "Grep", {"pattern": "x", "path": "%s/sources" % PMA}),
    ("A", "Grep", {"pattern": "grade", "path": "%s/sources" % PMA, "glob": "*.md", "output_mode": "content"}),
    ("A", "Bash", {"command": "ls -l %s/_inbox" % PMA}),
    ("A", "Bash", {"command": "ls %s/_inbox | head" % PMA}),
    ("A", "Bash", {"command": "find %s -type f" % PMA}),
    ("A", "Bash", {"command": "mkdir -p %s/sources/labs && mv %s/_inbox/2026-09-28__lab__panel.jpg %s/sources/labs/" % (PMA, PMA, PMA)}),
    ("A", "Bash", {"command": "cp -n /tmp/attachment.jpg %s/_inbox/2026-09-29__lab__new.jpg" % PMA}),
    ("A", "Bash", {"command": "shasum -a 256 %s/_inbox/2026-09-28__lab__panel.jpg /tmp/attachment.jpg" % PMA}),
    ("A", "Bash", {"command": "open %s/sources/labs/2026-09-01__lab__panel.pdf" % PMA}),
    ("A", "Bash", {"command": "python3 tools/private-mode/redact_ids.py --inbox %s/_inbox --render /tmp/w/render --work /tmp/w/work --redacted patients/pm-a/_redacted --log /tmp/w/log-1.json" % PMA}),
    ("A", "Bash", {"command": "python3 -m tools.person_ownership --root . append pm-a add --relpath med/sources/labs/2026-09-01__lab__panel.pdf"}),
    ("A", "Bash", {"command": "cat %s/sources/labs/2026-09-01__lab__panel.ocr.md" % PMA}),
    ("A", "Bash", {"command": "tesseract patients/plain-b/med/_inbox/2026-09-28__lab__panel.jpg stdout"}),
    ("A", "Bash", {"command": "ls -l \"%s/_inbox/lab results.txt\"" % PMA}),
    ("A", "Bash", {"command": "echo \"filed %s/_inbox/lab results.txt today\"" % PMA}),
    ("A", "Grep", {"pattern": "grade", "path": "%s/sources" % PMA, "glob": "{*.md,!README.md}", "output_mode": "content"}),
    ("A", "Grep", {"pattern": "eGFR", "path": "patients/pm-a", "glob": "*.md", "output_mode": "content"}),
    ("A", "Grep", {"pattern": "grade", "path": "%s/sources" % PMA, "type": "md", "output_mode": "content"}),
    ("A", "Bash", {"command": "grep -rn eGFR %s/analysis" % PMA}),
    ("A", "Bash", {"command": "ls patients/pm-a && ls -R patients/pm-a/med"}),
    ("A", "Read", {"file_path": "{proj}/%s/sources/_redacted/2026-09-01__lab__panel/2026-09-01__lab__panel__page-01.png" % PMA}),
    ("A", "Read", {"file_path": "{proj}/patients/README.md"}),
    ("A", "Bash", {"command": "for f in %s/_inbox/*.jpg; do mv \"$f\" %s/sources/labs/; done" % (PMA, PMA)}),
    ("A", "Bash", {"command": "find %s/_inbox -name '*.jpg' -exec mv {} %s/sources/labs/ \\;" % (PMA, PMA)}),
    ("A", "Bash", {"command": "mv %s/_inbox/2026-09-28__lab__panel.jpg \"%s/sources/labs/$(date +%%F)__panel.jpg\"" % (PMA, PMA)}),
    ("A", "Bash", {"command": "python3 tools/private-mode/redact_ids.py --inbox %s/_inbox --render \"$(mktemp -d)/r\" --work /tmp/w/work --redacted patients/pm-a/_redacted --log /tmp/w/log-2.json" % PMA}),
    ("A", "Bash", {"command": "nohup python3 tools/private-mode/redact_ids.py --inbox %s/_inbox --render /tmp/w/r --work /tmp/w/w --redacted patients/pm-a/_redacted --log /tmp/w/l3.json" % PMA}),
    ("A", "Bash", {"command": "caffeinate -i python3 tools/private-mode/redact_ids.py --inbox %s/_inbox --render /tmp/w/r --work /tmp/w/w --redacted patients/pm-a/_redacted --log /tmp/w/l4.json" % PMA}),
    ("A", "mcp__ccd_host__open_in_editor", {"path": "{proj}/%s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("A", "Artifact", {"action": "publish", "file_path": "/tmp/report.html"}),
    ("A", "Bash", {"command": "md5 %s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("A", "Bash", {"command": "md5 -q %s/_inbox/2026-09-28__lab__panel.jpg" % PMA}),
    ("A", "Bash", {"command": "find %s/_inbox -type f -exec shasum -a 256 {} +" % PMA}),
    ("A", "Bash", {"command": "find %s/_inbox -type f | xargs shasum -a 256" % PMA}),
    ("A", "Bash", {"command": "magick %s/_inbox/2026-09-28__lab__panel.jpg %s/_inbox/2026-09-28__lab__panel.pdf" % (PMA, PMA)}),
    ("A", "Bash", {"command": "magick convert %s/_inbox/2026-09-28__lab__panel.jpg pdf:%s/_inbox/p1.pdf" % (PMA, PMA)}),
    ("A", "Bash", {"command": "img2pdf %s/_inbox/2026-09-28__lab__panel.jpg -o %s/_inbox/p2.pdf" % (PMA, PMA)}),
    ("A", "Bash", {"command": "sips -s format pdf %s/_inbox/2026-09-28__lab__panel.jpg --out %s/_inbox/p3.pdf" % (PMA, PMA)}),
    ("A", "mcp__PDF_Tools__read_pdf_content", {"path": "{proj}/patients/plain-b/med/_inbox/2026-09-28__lab__panel.jpg"}),
    # private mode v2 (ADR-0029 control C1): a person's identity file is never read,
    # by name, anywhere — an unmarked person's too, a snapshot copy, an interrupted write's leftover
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/.never-api-identity.json"}),
    ("D", "Read", {"file_path": "{proj}/patients/plain-c/.never-api-identity.json"}),
    ("D", "Read", {"file_path": "{proj}/.snapshots/%s/patients/pm-a/.never-api-identity.json" % TS}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/.tmp-0a1b2c3d.never-api-identity.json"}),
    ("D", "Bash", {"command": "cat patients/pm-a/.never-api-identity.json"}),
    ("D", "Bash", {"command": "cat .snapshots/%s/patients/pm-a/.never-api-identity.json" % TS}),
    ("D", "Bash", {"command": "python3 -m json.tool patients/plain-c/.never-api-identity.json"}),
    ("D", "Bash", {"command": "jq . patients/pm-a/.never-api-identity.json"}),
    ("D", "Grep", {"pattern": "x", "path": "patients/plain-c/.never-api-identity.json", "output_mode": "content"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-lost/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-lost/med/_inbox/2026-09-28__lab__panel.jpg"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-noprof/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"}),
    ("D", "Bash", {"command": "cat patients/pm-lost/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"}),
    ("D", "SendUserFile", {"files": ["{proj}/patients/pm-a/.never-api-identity.json"], "status": "normal"}),
    ("A", "Bash", {"command": "ls -la patients/pm-a"}),
    ("A", "Bash", {"command": "stat patients/pm-a/.never-api-identity.json"}),
    ("A", "Bash", {"command": "cp -p patients/pm-a/.never-api-identity.json .snapshots/%s/patients/pm-a/" % TS}),
    ("A", "Bash", {"command": "python3 tools/private-mode/identity.py --root . status pm-a"}),
    ("A", "Bash", {"command": "python3 tools/private-mode/identity.py --root . age pm-a"}),
    # the fill-in form holds what the identity file will hold: the same by-name rule, with no new shape
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/fill-in-form.never-api-identity.json"}),
    ("D", "Read", {"file_path": "{proj}/patients/plain-c/fill-in-form.never-api-identity.json"}),
    ("D", "Bash", {"command": "cat patients/pm-a/fill-in-form.never-api-identity.json"}),
    ("D", "Grep", {"pattern": "x", "path": "patients/pm-a/fill-in-form.never-api-identity.json", "output_mode": "content"}),
    ("D", "SendUserFile", {"files": ["{proj}/patients/pm-a/fill-in-form.never-api-identity.json"], "status": "normal"}),
    ("A", "Bash", {"command": "python3 tools/private-mode/identity.py --root . form pm-a"}),
    ("A", "Bash", {"command": "python3 tools/private-mode/identity.py --root . take-form pm-a"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/number-picture.never-api-identity.png"}),
    ("D", "SendUserFile", {"files": ["{proj}/patients/pm-a/number-picture.never-api-identity.png"], "status": "normal"}),
    ("A", "Bash", {"command": "python3 tools/private-mode/identity.py --root . form pm-a --read-number patients/pm-a/med/_inbox/scan.pdf"}),
    ("A", "Bash", {"command": "python3 tools/private-mode/redact_ids.py --inbox patients/pm-a/med/_inbox --render /tmp/w/r --work /tmp/w/w --redacted patients/pm-a/_redacted --log /tmp/w/l.json --scheme us-ssn --number-from-identity patients/pm-a"}),
    ("A", "Bash", {"command": "python3 tools/private-mode/redact_ids.py --inbox patients/pm-a/med/_inbox --render /tmp/w/r --work /tmp/w/w --redacted patients/pm-a/_redacted --log /tmp/w/l.json --scheme pl-id --dob-from-identity patients/pm-a"}),
    # an editor's copy or backup of either holds the same values: any existing file whose name holds
    # the marker, anywhere, in any case (cold review 2026-11-07; an exception to the freeze for this rule)
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/fill-in-form.never-api-identity.json~"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/.fill-in-form.never-api-identity.json.swp"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/#fill-in-form.never-api-identity.json#"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/fill-in-form.never-api-identity copy.json"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/fill-in-form.never-api-identity.json.txt"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-a/fill-in-form.never-api-identity.json.save"}),
    ("D", "Read", {"file_path": "{proj}/patients/plain-c/.never-api-identity.json.bak"}),
    ("D", "Read", {"file_path": "{proj}/Desktop-like/Fill-In-Form.Never-API-Identity (2).json"}),
    ("D", "Bash", {"command": "cat 'patients/pm-a/fill-in-form.never-api-identity copy.json'"}),
    ("D", "Bash", {"command": "cat 'patients/pm-a/#fill-in-form.never-api-identity.json#'"}),
    ("D", "Bash", {"command": "head -5 patients/plain-c/.never-api-identity.json.bak"}),
    ("D", "Bash", {"command": "cat patients/pm-a/*.save"}),
    ("D", "Bash", {"command": "python3 -c \"print(open('patients/pm-a/fill-in-form.never-api-identity.json~').read())\""}),
    ("D", "Grep", {"pattern": "x", "path": "patients/pm-a/fill-in-form.never-api-identity.json.txt", "output_mode": "content"}),
    ("D", "SendUserFile", {"files": ["{proj}/Desktop-like/Fill-In-Form.Never-API-Identity (2).json"], "status": "normal"}),
    # …while a word that only mentions the marker names no file, and the tools that never print stay open
    ("A", "Read", {"file_path": "{proj}/patients/pm-a/never-api-identity-notes.txt"}),
    ("A", "Bash", {"command": "echo never-api-identity"}),
    ("A", "Bash", {"command": "git commit -m 'refuse copies of never-api-identity files'"}),
    ("A", "Bash", {"command": "python3 -c \"print('never-api-identity')\""}),
    ("A", "Bash", {"command": "grep -rn never-api-identity tools"}),
    ("A", "Bash", {"command": "open 'patients/pm-a/fill-in-form.never-api-identity copy.json'"}),
    ("A", "Read", {"file_path": "{proj}/tools/private-mode/identity.py"}),
    ("A", "Read", {"file_path": "{proj}/patients/plain-b/profile.md"}),
    ("D", "Bash", {"command": "cd patients/pm-a && cat .never-api-identity.json"}),
    ("D", "Bash", {"command": "echo $(<patients/pm-a/.never-api-identity.json)"}),
    ("D", "Bash", {"command": "x=$(<patients/pm-a/.never-api-identity.json); echo \"$x\""}),
    ("D", "Bash", {"command": "echo $(<%s/_inbox/2026-09-28__lab__letter.txt)" % PMA}),
    # by name, existing or not: a copy and a read of the copy can share one line (review 2026-10-01)
    ("D", "Bash", {"command": "mkdir -p restore && cp patients/pm-a/.never-api-identity.json restore/.never-api-identity.json && cat restore/.never-api-identity.json"}),
    ("D", "Bash", {"command": "cp -R patients/pm-a restore-x && cat restore-x/.never-api-identity.json"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-z/.never-api-identity.json"}),
    # private mode v2 (C1, second part): a v2 person's final handout output is never read; its
    # Markdown, attestation and drafts are; a v1 person's handouts are untouched
    ("D", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"}),
    ("D", "Bash", {"command": "pdftotext patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf -"}),
    ("D", "Bash", {"command": "cat patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.txt"}),
    ("D", "Grep", {"pattern": "x", "path": "patients/pm-v2/med/handouts", "output_mode": "content"}),
    ("D", "SendUserFile", {"files": ["{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"], "status": "normal"}),
    ("D", "mcp__PDF_Tools__read_pdf_content", {"path": "{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.md"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.attest.json"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.factcheck.md"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/drafts/2026-10-05__handout-patient__x.draft.pdf"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/INDEX.md"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/.legacy-frozen"}),
    ("D", "Read", {"file_path": "{proj}/patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf.tmp"}),
    ("A", "Grep", {"pattern": "x", "path": "patients/pm-v2/med/handouts", "glob": "*.md", "output_mode": "content"}),
    ("A", "Bash", {"command": "ls -la patients/pm-v2/med/handouts/patient/2026-10-05-visit"}),
    ("A", "Bash", {"command": "open patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.pdf"}),
    ("A", "Bash", {"command": ".venv-render/bin/python _templates/handout-assets/render_handout.py patients/pm-v2/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__x.md"}),
    ("A", "Read", {"file_path": "{proj}/patients/pm-v1/med/handouts/patient/2026-10-05-visit/2026-10-05__handout-patient__y.pdf"}),
    # a grep-family pattern is data, never a file: mentioning the name there runs
    ("A", "Bash", {"command": "grep -rn '.never-api-identity.json' tools"}),
    ("A", "Bash", {"command": "rg -l .never-api-identity.json"}),
    ("A", "Bash", {"command": "rg -n -e '.never-api-identity.json' tools"}),
    ("A", "Bash", {"command": "cd patients/plain-c && grep -n .never-api-identity.json profile.md"}),
    ("A", "Bash", {"command": "git commit -m 'document patients/pm-z/.never-api-identity.json'"}),
    ("D", "Bash", {"command": "grep -n x patients/pm-a/.never-api-identity.json"}),
    ("D", "Bash", {"command": "grep -f patients/pm-a/.never-api-identity.json notes.md"}),
    # backtick substitution is judged exactly as `$(…)` (found 2026-10-01 red-teaming v2 slice 1)
    ("D", "Bash", {"command": "echo `cat %s/_inbox/2026-09-28__lab__letter.txt`" % PMA}),
    ("D", "Bash", {"command": "x=`cat %s/_inbox/2026-09-28__lab__letter.txt`" % PMA}),
    ("D", "Bash", {"command": "echo `<%s/_inbox/2026-09-28__lab__letter.txt`" % PMA}),
    ("D", "Bash", {"command": "cat < `echo %s/_inbox/2026-09-28__lab__letter.txt`" % PMA}),
    ("D", "Bash", {"command": "cat > notes.txt <<EOF\n`cat %s/_inbox/2026-09-28__lab__letter.txt`\nEOF" % PMA}),
    ("D", "Bash", {"command": "echo `echo \\`cat %s/_inbox/2026-09-28__lab__letter.txt\\``" % PMA}),
    ("D", "Bash", {"command": "echo `date #`; cat %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "echo \"`cat %s/_inbox/2026-09-28__lab__letter.txt`\"" % PMA}),
    ("A", "Bash", {"command": "echo `date`"}),
    ("A", "Bash", {"command": "x=`ls %s/_inbox`" % PMA}),
    ("A", "Bash", {"command": "mv %s/_inbox/2026-09-28__lab__panel.jpg \"%s/sources/labs/`date +%%F`__panel.jpg\"" % (PMA, PMA)}),
    ("A", "Bash", {"command": "git commit -m \"fix \\`cat\\` handling\" && git commit --amend -m 'fix `cat` handling'"}),
    ("A", "Bash", {"command": "git commit -m \"$(cat <<'EOF'\nfiled `%s/_inbox/2026-09-28__lab__letter.txt` today\nEOF\n)\"" % PMA}),
    ("A", "Bash", {"command": "cat > notes.txt <<EOF\nrun `date` before filing\nEOF"}),
    ("A", "Bash", {"command": "echo `date # not %s/_inbox/2026-09-28__lab__letter.txt`" % PMA}),
    # red-team 2026-10-01: a here-document inside a span that closes on its line has no body; a
    # substitution nested in a substitution's own words; an ANSI-C string's `\'`
    ("D", "Bash", {"command": "echo `cat <<EOF`\ncat %s/_inbox/2026-09-28__lab__letter.txt\nEOF" % PMA}),
    ("D", "Bash", {"command": "x=`true <<-EOF`\n\tcat %s/_inbox/2026-09-28__lab__letter.txt\n\tEOF" % PMA}),
    ("D", "Bash", {"command": "echo \"`echo \\\"\\`cat %s/_inbox/2026-09-28__lab__letter.txt\\`\\\"`\"" % PMA}),
    ("D", "Bash", {"command": "echo \"$(echo \\\"$(cat %s/_inbox/2026-09-28__lab__letter.txt)\\\")\"" % PMA}),
    ("D", "Bash", {"command": "echo $'it\\'s # x'; cat %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    ("D", "Bash", {"command": "echo $'it\\'s' `cat %s/_inbox/2026-09-28__lab__letter.txt` \\'" % PMA}),
    ("A", "Bash", {"command": "echo $'it\\'s fine'"}),
    ("A", "Bash", {"command": "x=\"`cat <<'EOF'\nfiled today\nEOF\n`\"; echo \"$x\""}),
    # refused though harmless, as with `$(…)`: an unquoted substitution with more of its command after
    # it (quote it — the next case)
    ("D", "Bash", {"command": "mv %s/_inbox/2026-09-28__lab__panel.jpg %s/sources/labs/`date +%%F`__panel.jpg" % (PMA, PMA)}),
    # refused though harmless: a backtick in a search pattern is judged as code (use the Grep tool)
    ("D", "Bash", {"command": "grep -rn '`cat %s/_inbox/2026-09-28__lab__letter.txt`' tools" % PMA}),
    ("D", "Bash", {"command": "grep -rn \"`cat %s/_inbox/2026-09-28__lab__letter.txt`\" tools" % PMA}),
    ("D", "Bash", {"command": "grep -n '`x`' %s/_inbox/2026-09-28__lab__letter.txt" % PMA}),
    # a non-shell interpreter's script is judged by its literals and paths, not by the words of the
    # prose inside them — `patients` (the patients/ folder, from the project root) and Markdown bold
    # `patient**` (a glob matching it) must not refuse an unmarked person's own files or a shared one:
    ("A", "Bash", {"command": "python3 - <<'EOF'\np=\"patients/plain-b/med/analysis/2001-01-01__analysis__review.md\"\n"
                              "t=open(p,encoding=\"utf-8\").read()\nsubs=[\n(\"\"\"   (point 2). Old line. [C, high]\"\"\",\n"
                              "\"\"\"   (point 2). New line: placeholder ⟨lit⟩; **the plan holds** (2001-01-01, A).\n"
                              "   What patients report: placeholder; many patients do well. [C, high]\"\"\"),\n"
                              "(\"\"\"1. **Old** item\"\"\",\"\"\"1. **New** item, see the 2001-01-01__lab__panel original\"\"\"),\n]\n"
                              "for a,b in subs:\n    assert t.count(a)==1, a[:70]; t=t.replace(a,b)\n"
                              "open(p,\"w\",encoding=\"utf-8\").write(t); print(\"ok\")\nEOF"}),
    ("A", "Bash", {"command": "python3 - <<'EOF'\np='reference-library/index.md'; s=open(p,encoding='utf-8').read()\n"
                              "o=\"placeholder patients; plain-b note).\"\nn=\"placeholder patients — not applicable here).\"\n"
                              "assert s.count(o)==1; s=s.replace(o,n); open(p,'w',encoding='utf-8').write(s)\nEOF\n"
                              "grep -c -i plain reference-library/index.md; bash checks/check.sh 2>&1 | grep -E 'FAIL|all guards'"}),
    ("A", "Bash", {"command": "cd {proj}/patients/plain-b && python3 - <<'EOF'\np='medications.md'; s=open(p,encoding='utf-8').read()\n"
                              "o=\"| Drug V | generic | class — **placeholder / as told by the patient** |\"\n"
                              "n=\"| Drug V | generic | class — **placeholder / as told by the patient**. ⟨confirm by 2027-01: re-read the \\\"x\\\" original⟩ |\"\n"
                              "assert s.count(o)==1; s=s.replace(o,n); open(p,'w',encoding='utf-8').write(s)\nEOF\n"
                              "cd ../.. && bash checks/check.sh 2>&1 | grep -E 'FAIL|all guards'"}),
    ("A", "Bash", {"command": "python3 - <<'EOF'\nprint('*' * 40)\nt = open('notes.md').read().replace('**', '')\nEOF"}),
    ("A", "Bash", {"command": "python3 -c \"print('most patients agree')\""}),
    # ...while the same shapes naming a private-mode person's original, or the folders above one, deny
    ("D", "Bash", {"command": "python3 - <<'EOF'\np=\"%s/_inbox/2026-09-28__lab__letter.txt\"\n"
                              "t=open(p,encoding=\"utf-8\").read()\nsubs=[(\"\"\"old\"\"\",\"\"\"many patients do well\"\"\")]\n"
                              "for a,b in subs:\n    assert t.count(a)==1, a[:70]; t=t.replace(a,b)\nprint(t)\nEOF" % PMA}),
    ("D", "Bash", {"command": "python3 - <<'EOF'\np='reference-library/index.md'; s=open(p,encoding='utf-8').read()\n"
                              "o=open('%s/sources/labs/2026-09-01__lab__panel.pdf','rb').read()[:99]\nprint(o)\nEOF" % PMA}),
    ("D", "Bash", {"command": "cd {proj}/%s/_inbox && python3 - <<'EOF'\np='2026-09-28__lab__letter.txt'; s=open(p,encoding='utf-8').read()\n"
                              "o=\"**placeholder / as told by the patient**\"\nprint(s.count(o))\nEOF\ncd ../.. && bash checks/check.sh" % PMA}),
    ("D", "Bash", {"command": "python3 - <<'EOF'\nimport os\nprint(os.listdir('patients'))\nEOF"}),
    ("D", "Bash", {"command": "python3 - <<'EOF'\nimport os\nfor r, d, f in os.walk('patients/pm-a'): print(f)\nEOF"}),
    ("D", "Bash", {"command": "python3 - <<'EOF'\nimport os\nos.system('cat %s/_inbox/2026-09-28__lab__letter.txt')\nEOF" % PMA}),
    ("D", "Bash", {"command": "python3 - <<'EOF'\nimport glob\nfor f in glob.glob('%s/_inbox/*'): print(open(f).read())\nEOF" % PMA}),
    ("D", "Bash", {"command": "cd %s/_inbox && python3 - <<'EOF'\nimport glob\nfor f in glob.glob('*.txt'): print(open(f).read())\nEOF" % PMA}),
    ("D", "Bash", {"command": "python3 -c \"import os; print(os.listdir('patients'))\""}),
    ("D", "Bash", {"command": "cd patients/pm-a && python3 - <<'EOF'\nimport os\nos.system('cat .never-api-identity.json | head -1')\nEOF"}),
    ("D", "Bash", {"command": "bash -c 'grep -rn eGFR patients'"}),                    # shell code keeps its words
]

# The denial names the rule class that matched — never the word, path or person — so a session can
# tell a real hit from a false one: (command, text the reason must hold). The person's handle and the
# file's date are never in it.
PM_MESSAGES = [
    ("python3 - <<'EOF'\nprint(open('%s/_inbox/2026-09-28__lab__letter.txt').read())\nEOF" % PMA,
     "matched rule: a path in it resolves to an original of a private-mode person"),
    ("python3 - <<'EOF'\nimport os\nprint(os.listdir('patients'))\nEOF",
     "matched rule: a path in it resolves to a folder above a private-mode person's originals"),
    ("grep -rn eGFR %s/sources" % PMA,
     "matched rule: a path in it resolves to a folder of a private-mode person's originals"),
    ("python3 - <<'EOF'\nimport glob\nprint(glob.glob('patients/pm-a/med/*/2026-*'))\nEOF",
     "matched rule: a glob pattern in it matches, on disk, an original of a private-mode person"),
    ("F=%s/_inbox/2026-09-28__lab__panel.jpg; xxd \"$F\"" % PMA,
     "matched rule: a variable assigned on the line holds the path of one"),
    ("cat patients/pm-a/.never-api-identity.json",
     "matched rule: a path in it resolves to a file refused by its name"),
]

# The fail-closed net: input the hook cannot analyse is denied exactly when it names a protected file.
CRASH = [
    ("D", b'{"tool_name": "Bash", "tool_input": ["cat checks/PRIVATE-MODE-ID"], "cwd": "/"}'),
    ("A", b'{"tool_name": "Bash", "tool_input": ["ls"], "cwd": "/"}'),
    ("D", b'{"tool_name": "Bash", "tool_input": {"command": {"x": "private-mode-id.sh"}}, "cwd": "/"}'),
    ("D", b'{"tool_name": "Read", "tool_input": {"file_path": ["FIREWALL-REGISTRY"]}, "cwd": "/"}'),
    ("D", b'{"tool_name": "Bash", "tool_input": {"command": "cat x"}, "cwd": 7, "p": "PRIVATE-MODE-ID"}'),
    ("D", b'not json at all: cat checks/PRIVATE-MODE-ID'),
    ("A", b'not json at all: ls'),
    ("D", b'\xff\xfe{"tool_name": "Bash", "tool_input": {"command": "cat firewall-registry.sh"}}'),
    ("A", b''),
]


class _Stop(Exception):
    pass


def main(stop_at_mismatch=False):
    bad = total = 0

    def verdict(label, exp, got, what):
        nonlocal bad, total
        total += 1
        if got != exp:
            bad += 1
            print("MISMATCH [%s] exp=%s got=%s: %s" % (label, exp, got, what))
            if stop_at_mismatch:
                raise _Stop()

    try:
        _matrix(verdict)
    except _Stop:
        return 1
    print("cases=%d mismatches=%d" % (total, bad))
    return 1 if bad else 0


def _matrix(verdict):
    # Every case is still a fresh process of the real hook; they run on a thread pool (the hook only reads the
    # synthetic layout) and are judged in the order listed, so a mismatch report reads the same as a serial run.
    with tempfile.TemporaryDirectory() as tmp:
        L = make_layout(os.path.realpath(tmp))
        pool = ThreadPoolExecutor(max_workers=WORKERS)
        pending = []

        def check(label, exp, what, *a, post=None, **k):
            pending.append((label, exp, what, pool.submit(run, L, *a, **k), post))
        try:
            _cases(check, L)
            for label, exp, what, fut, post in pending:
                got = fut.result()
                verdict(label, exp, post(got) if post else got, what)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)


def _cases(check, L):
    for exp_v, exp_u, cmd in BASH:
        c = fill(cmd, L)
        check("verified", exp_v, repr(cmd), "verified", "Bash", {"command": c})
        check("unverified", exp_u, repr(cmd), "unverified", "Bash", {"command": c})
    if L["hard"]:
        for mode in ("verified", "unverified"):
            check(mode, "D", "hard link", mode, "Bash", {"command": "cat " + L["hard"]})
            check(mode, "D", "Read a hard link", mode, "Read", {"file_path": L["hard"]})
    for exp_v, exp_u, tool, ti in FILES:
        t = fill(ti, L)
        check("verified", exp_v, "%s %s" % (tool, ti), "verified", tool, t)
        check("unverified", exp_u, "%s %s" % (tool, ti), "unverified", tool, t)
    checks = os.path.join(L["proj"], "checks")
    # a relative spelling from a subdirectory reaches the same pointer; `cd` moves later words
    check("verified", "D", "cwd=checks", "verified", "Bash", {"command": "cat ./PRIVATE-MODE-ID"}, cwd=checks)
    check("verified", "D", "bare word, cwd=checks", "verified", "Bash", {"command": "cat PRIVATE-MODE-ID"}, cwd=checks)
    check("verified", "D", "cd base", "verified", "Bash", {"command": "cd .. && cat ../home/.tabularium/*"}, cwd=checks)
    # each `cd` once doubled the bases tried: 24 of them in a script body must still answer in time
    hops = "bash -s <<'EOF'\n" + "".join("cd d%d && make\n" % n for n in range(24)) + "git status\nEOF"
    check("verified", "A", "24 cd hops", "verified", "Bash", {"command": hops}, timeout=10)
    for mode, exp, tool, ti in OTHER:
        check(mode, exp, "%s %s" % (tool, ti), mode, tool, fill(ti, L))
    case_blind = os.path.exists(os.path.join(L["proj"], "PATIENTS", "pm-a", "profile.md"))
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    for exp, tool, ti in PM:            # the rule ignores the configuration: each case runs once
        if exp == "D~":
            exp = "D" if case_blind else "A"
        if exp == "D!":                 # root reads an unreadable profile, so it is not unreadable
            if is_root:
                continue
            exp = "D"
        check("pm", exp, "%s %s" % (tool, ti), "verified", tool, fill(ti, L))
    for cmd, want in PM_MESSAGES:
        def message(err, want=want):
            return "D+class" if (err.startswith("D:") and want in err and "pm-a" not in err
                                 and "2026-09-28" not in err) else err[:300]
        check("pm-message", "D+class", repr(cmd), "verified", "Bash", {"command": fill(cmd, L)}, stderr=True,
              post=message)
    for exp, raw in CRASH:
        check("crash-net", exp, repr(raw[:60]), "verified", None, None, raw=raw)


class Matrix(unittest.TestCase):
    def test_every_verdict_matches(self):
        self.assertEqual(main(), 0)

    def test_a_permissive_stub_is_caught(self):
        # negative control: a hook that allows everything must mismatch, or the matrix proves nothing
        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "allow-all.py")
            with open(stub, "w") as fh:
                fh.write("import sys\nsys.stdin.read()\n")
            out = StringIO()
            with mock.patch.object(sys.modules[__name__], "HOOK", stub), redirect_stdout(out):
                self.assertEqual(main(stop_at_mismatch=True), 1)
            self.assertIn("MISMATCH", out.getvalue())


if __name__ == "__main__":
    sys.exit(main())
