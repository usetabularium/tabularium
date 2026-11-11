#!/usr/bin/env python3
"""containment.py — the two instance-aware containment checks (requirements 6 and 7
in evals/README.md, made executable and instance-aware by ADR-0050).

WHAT THIS IS
------------
`evals/README.md` has claimed since 2026-08-30 that every run performs a **pre-transit firewall
scan** of the instantiated fixture tree, the task prompts and the instruction bundle against the
private token registry, and that the build **asserts fixture handles collide with no real roster
handle**. Until 2026-09-06 neither existed in code: `fixture.py` only documented that the registry
is deliberately *not copied* into a fixture (which is a different, and separate, guarantee). This
module is the missing half — the checks themselves — and it is written to work in BOTH instances
ADR-0050 splits the system into:

  * wherever the registry RESOLVES the scan runs for real — a CARE instance, and equally a DEV
    instance, since after ADR-0050 A2 the registry lives outside every repository and a tree that
    holds no record still reaches it through `checks/FIREWALL-REGISTRY`;
  * where NO registry resolves and no record is present (CI, a test fixture, a fresh DEV clone
    before the pointer is written) there is nothing to scan *against*, so the check records
    `not-applicable (record-free instance)` and the registry component of the configuration
    identity is the literal `none`.

The branch is on registry resolution, not on the presence of records; the two coincided only while
the registry lived in the tree the records lived in.

The dangerous middle — a tree that holds records but cannot reach a registry — **aborts**. That
combination is a misconfiguration, not a licence to send an unscanned tree to the API.

WHAT THE SCAN LOOKS FOR — THE PRIVATE-MODE IDENTIFIER ONLY (narrowed 2026-09-28)
-------------------------------------------------------------------------------
Only one class names a harm on this path: the private-mode identifier, whose arrival at the API is
the harm itself (ADR-0029). The other four — identity, clinical, brand, consent — reach the API in
every ordinary care session, and the instruction bundle is tracked text every session already sends;
reading is not leaking. Scanning for them only ever stopped the operator's own run, on ordinary words
that happen to match a class atom. So `SCANNED_CLASSES` is the private-mode class
alone, plus the private mode v2 classes when the private file carries them (ADR-0029
point 13): a v2 person's withheld details reaching the API is the harm v2 exists for. The registry
is still resolved and validated whole — the private-mode pointer pairs with it,
the configuration identity binds its digest, and a malformed registry is a misconfiguration
everywhere — but its four classes are not matched here. The relay scan keeps the personal details
(identity, the private-mode lines) and the flip-time export gate every class: there the harm is a
person's details reaching a tracked file, or record content reaching the export. Real case dates are
not kept on the registry (ADR-0072): a leftover `PII_CASEREF` line in the registry, or a
`PII_PRIVATE_CASEREF` line in the private file, is ignored.

THE PRIVATE-MODE IDENTIFIER HAS ITS OWN FILE (ADR-0050 point 9)
-------------------------------------------------------------------------
Since the operator's decision of 2026-09-14 the private-mode identifier (ADR-0029) is cut out of its
registry class line into one small owner-only file outside every repository, named by the untracked
`checks/PRIVATE-MODE-ID` (or `TABULARIUM_PRIVATE_MODE_ID_PATH`). It is scanned as a sixth class,
`private-mode-id`. Wherever a registry resolves, that file must resolve too, be owner-only and carry
exactly one `PII_PRIVATE_MODE_ID='…'` line (and, for private mode v2, at most one `PII_PRIVATE_<CLASS>`
line per registry class) — otherwise the scan is **blinded** and the run aborts,
because a scan without it would let the one token that must never reach the API through. Its bytes
never enter the configuration identity: a digest of a one-line file is brute-forceable back to its
content, so `registry_digest` stays the digest of the registry file alone.

WHAT NEVER LEAVES THIS MODULE
-----------------------------
The token class values. They are read into the process (that is the only way to scan with them),
held in a private attribute, passed to `grep` as a pattern argument exactly as the retired
`check.sh` guards L9 and L18 did (and as the flip-time export gate still does), and never printed,
logged, repr'd or written anywhere. A hit is reported as a **locator only** — `path:line (class)` —
the discipline L18 adopted after a bounded read printed the identity tokens: identity-class *content* in guard output would itself
transit the model channel.

LOCALE DISCIPLINE (copied from L18, including its reasons; L18 is gone, the reasons are not)
----------------------------------------------------------
Several registry atoms carry multibyte diacritics. Under a C/POSIX locale BSD grep silently
NARROWS them — `-i` case folding and adjacency fail with rc=1, not rc=2, so no tripwire fires. So
every scan runs under a pinned UTF-8 locale; if the host has none, the scan is **blinded** and the
run aborts rather than proceeding with a quietly ASCII-only scan. A scan `grep` returning rc>=2 is
an ERROR, never "no hits" (the L5/ADR-0021 lesson).

NO CARVE-OUTS, DELIBERATELY
---------------------------
L18 exempted three shapes (`NOTICE.md`, the site `©` footer lines, the renderer's month arrays);
the flip-time export gate now exempts only the top-level `NOTICE.md` and `CITATION.cff` from its
identity-token scan, because a *shipped* surface legitimately carries operator self-disclosure. Synthetic eval material never does, and an abort here is cheap and loud, so this
scan applies no exemptions at all — over-mask, then recover.

Entry points:
    preflight(repo_root, fixture_handles, instruction_surfaces) -> Containment | raises ContainmentAbort
    Containment.scan_trial(label, fixture_dir, task_text)       -> None       | raises ContainmentAbort

Run `python3 -m evals.harness.containment` to print this instance's dispositions (no content).
"""

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Environment override for the registry path; external registry placement follows ADR-0050 Part A2.
REGISTRY_ENV = "TABULARIUM_REGISTRY_PATH"
#: Untracked pointer file naming the out-of-tree registry (the `checks/OFFSITE-DEST` pattern).
REGISTRY_CONFIG = os.path.join("checks", "FIREWALL-REGISTRY")
#: The pre-A2 home of the token arrays: still a registry for as long as it carries `PII_*=` lines.
REGISTRY_IN_TREE = os.path.join("checks", "publish-skeleton.sh")
#: Environment override for the private-mode identifier file (ADR-0050 point 9).
PRIVATE_ENV = "TABULARIUM_PRIVATE_MODE_ID_PATH"
#: Untracked pointer naming the private-mode identifier file, beside `checks/FIREWALL-REGISTRY`.
PRIVATE_CONFIG = os.path.join("checks", "PRIVATE-MODE-ID")
#: ledger-visible name -> the one assignment that file always carries.
PRIVATE_CLASS = ("private-mode-id", "PII_PRIVATE_MODE_ID")
#: private mode v2 (ADR-0029 point 13): the file may also carry one line per registry
#: class, holding the tokens of a v2 person's withheld details; keeping them off the API is the harm v2
#: exists for, so each present line is scanned like the identifier.
PRIVATE_V2_CLASSES = (
    ("private-identity", "PII_PRIVATE_IDENTITY"),
    ("private-clinical", "PII_PRIVATE_CLINICAL"),
    ("private-brand", "PII_PRIVATE_BRAND"),
    ("private-consent", "PII_PRIVATE_CONSENT"),
)

#: ledger-visible name -> the assignment the registry uses. Order is the reporting order.
CLASS_LINES = (
    ("identity", "PII_IDENTITY"),
    ("clinical", "PII_CLINICAL"),
    ("brand", "PII_BRAND"),
    ("consent", "PII_CONSENT"),
)
#: The retired case-reference class (ADR-0072): its private-file line keeps a valid shape and is ignored.
RETIRED_PRIVATE = "PII_PRIVATE_CASEREF"
#: Every class the registry and the private file must carry and compile, the private-mode one last.
ALL_CLASSES = CLASS_LINES + (PRIVATE_CLASS,)
#: The classes the pre-transit scan always matches: the private-mode identifier (narrowed 2026-09-28;
#: module docstring) — the class whose arrival at the API is itself the harm. A private mode v2 class
#: present in the private file is matched too (`Registry._scanned`), for the same reason.
SCANNED_CLASSES = (PRIVATE_CLASS,)

#: The record directories whose presence makes a tree a CARE instance. ADR-0050 derives the mode
#: from this observable rather than from a marker, because a marker fails open in the dangerous
#: direction. `checks/RECORD-SET` owns the full list; the roster directory alone is the observable
#: the eval needs.
RECORDS_DIR = "patients"
ROSTER_FILE = os.path.join("patients", "README.md")

#: Fixture handles are deliberately implausible; nothing real may look like one.
FIXTURE_HANDLE_RE = re.compile(r"^evalperson-", re.I)

NOT_APPLICABLE_SCAN = "not-applicable (record-free instance)"
NOT_APPLICABLE_ROSTER = "not-applicable"
CLEAN = "clean"


class ContainmentAbort(RuntimeError):
    """A pre-transit check that must stop the run. Carries locators, never content."""

    def __init__(self, reason, locators=None):
        super().__init__(reason)
        self.reason = reason
        self.locators = list(locators or [])


def _grep_binary():
    """A real grep. `/usr/bin/grep` by preference: an interactive shell's `grep` may be ugrep,
    whose ERE dialect is not the one the registry classes were written against."""
    if os.access("/usr/bin/grep", os.X_OK):
        return "/usr/bin/grep"
    found = shutil.which("grep")
    if not found:
        raise ContainmentAbort("no grep on PATH — the pre-transit scan cannot run (fail closed)")
    return found


def pick_locale():
    """The UTF-8 locale every scan runs under, or None. L18's probe, same allow-list, same order."""
    try:
        out = subprocess.run(["locale", "-a"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=30)
    except Exception:                            # noqa: BLE001 — no `locale` binary is "none found"
        return None
    for name in out.stdout.decode("utf-8", "replace").splitlines():
        name = name.strip()
        if re.match(r"^(en_US|en_GB|C)\.(UTF-8|utf8)$", name):
            return name
    return None


def _registry_classes(path):
    """The four class values, read into this process. Returns {} when the file is not a registry.

    The return value is token content: it goes straight into a Registry's private attribute and
    is never printed. Any read failure is reported without the bytes that caused it.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ContainmentAbort("registry at %s is not valid UTF-8 — cannot source the token "
                               "classes (fail closed)" % path)
    except OSError as exc:
        raise ContainmentAbort("registry at %s is unreadable (%s) — fail closed"
                               % (path, exc.strerror or type(exc).__name__))
    found = {}
    for name, var in CLASS_LINES:
        m = re.search(r"^%s='(.*)'$" % re.escape(var), text, re.M)
        if m and m.group(1):
            found[name] = m.group(1)
    return found


def _private_classes(path):
    """{ledger name: pattern} from the private-mode identifier file, read into this process — never
    printed.

    The file must be a regular file (not a symlink), owner-only, and carry exactly one non-empty
    `PII_PRIVATE_MODE_ID='…'` line and, for private mode v2, at most one non-empty line of each
    `PRIVATE_V2_CLASSES` assignment — nothing else. Anything else blinds the scan (fail closed).
    """
    try:
        st = os.lstat(str(path))
    except OSError as exc:
        raise ContainmentAbort("the private-mode identifier file at %s is unreadable (%s) — "
                               "pre-transit scan blinded (fail closed)"
                               % (path, exc.strerror or type(exc).__name__))
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ContainmentAbort("the private-mode identifier file at %s is a symlink or not a regular "
                               "file — never followed; pre-transit scan blinded (fail closed)" % path)
    if st.st_mode & 0o077:
        raise ContainmentAbort("the private-mode identifier file at %s is not owner-only (mode %o) — "
                               "chmod 600 it; pre-transit scan blinded (fail closed)"
                               % (path, stat.S_IMODE(st.st_mode)))
    try:
        raw = Path(path).read_bytes()
        text = raw.decode("utf-8")
    except (UnicodeDecodeError, OSError):
        raise ContainmentAbort("the private-mode identifier file at %s cannot be read as UTF-8 text — "
                               "pre-transit scan blinded (fail closed)" % path)
    if b"\r" in raw:
        # the relay scan, the installer and the registry's fold-in block all refuse a CR line ending;
        # read the file the way they do rather than more leniently (review of PR #14)
        raise ContainmentAbort("the private-mode identifier file at %s has carriage-return line endings "
                               "— pre-transit scan blinded (fail closed)" % path)
    # every line not blank or a `#` comment must be one of the assignments, exactly — a near miss
    # (`export …`, spaces around `=`, another case or name) would otherwise go unscanned; the relay
    # scan, the installer and the registry's fold block read the file the same way. One quoted pair
    # per value, no `'` inside it (Codex review of PR #92): read greedily, `'a'|'b'` or `'a'x'b'` is
    # one value that matches neither token. Checked first, so every malformed line gets one answer.
    lines = [l for l in text.split("\n") if not re.match(r"^[ \t\v\f]*(#.*)?$", l)]
    known = r"^[ \t\v\f]*PII_PRIVATE_(MODE_ID|IDENTITY|CASEREF|CLINICAL|BRAND|CONSENT)='[^']*'$"
    shape = ("the private-mode identifier file at %s must carry exactly one non-empty %s='…' line and, "
             "for kept details, PII_PRIVATE_<CLASS> lines only, with no ' inside a value (write an "
             "apostrophe as .) (found %d class line(s)) — pre-transit scan blinded (fail closed)"
             % (path, PRIVATE_CLASS[1], len(lines)))
    if not all(re.match(known, l) and l.count("PII_PRIVATE_") == 1 for l in lines):
        raise ContainmentAbort(shape)
    lines = [l for l in lines if not re.match(r"^[ \t\v\f]*%s=" % RETIRED_PRIVATE, l)]
    found = {}
    for name, assign in (PRIVATE_CLASS,) + PRIVATE_V2_CLASSES:
        mine = [l for l in lines if re.match(r"^[ \t\v\f]*%s=" % assign, l)]
        m = re.match(r"^[ \t\v\f]*%s='([^']*)'$" % assign, mine[0]) if len(mine) == 1 else None
        if mine and (not m or not m.group(1)):
            raise ContainmentAbort("the private-mode identifier file at %s must carry %s one "
                                   "non-empty %s='…' line (found %d) — pre-transit scan blinded "
                                   "(fail closed)" % (path, "exactly" if assign == PRIVATE_CLASS[1]
                                                      else "at most", assign, len(mine)))
        if m:
            found[name] = m.group(1)
    if PRIVATE_CLASS[0] not in found or len(found) != len(lines):
        raise ContainmentAbort(shape)
    return found


def resolve_private(repo_root=REPO_ROOT, env=None):
    """`TABULARIUM_PRIVATE_MODE_ID_PATH` -> `checks/PRIVATE-MODE-ID` -> None, as (path or None, how).

    A route that is present but names nothing usable aborts rather than falling through: the one
    file whose absence must never read as "nothing to scan for"."""
    env = os.environ if env is None else env
    explicit = (env.get(PRIVATE_ENV) or "").strip()
    if explicit:
        path = Path(os.path.expanduser(explicit))
        if not path.is_absolute() or not path.is_file():
            raise ContainmentAbort("%s names %s, which is not an absolute path to a file — fail closed"
                                   % (PRIVATE_ENV, path))
        return path, PRIVATE_ENV
    pointer = Path(repo_root) / PRIVATE_CONFIG
    if pointer.is_symlink() or pointer.exists():
        if pointer.is_symlink() or not pointer.is_file():
            raise ContainmentAbort("%s is a symlink or not a regular file — fail closed" % PRIVATE_CONFIG)
        named = ""
        for line in pointer.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                named = line
                break
        path = Path(os.path.expanduser(named)) if named else None
        if path is None or not path.is_absolute():
            raise ContainmentAbort("%s names no absolute path — fail closed" % PRIVATE_CONFIG)
        if not path.exists() and not path.is_symlink():
            raise ContainmentAbort("%s names %s, which does not exist — fail closed"
                                   % (PRIVATE_CONFIG, path))
        return path, PRIVATE_CONFIG
    return None, "none"


def looks_like_registry(path):
    """True when `path` carries the `PII_*=` class lines — the test ADR-0050's A1 hook uses too."""
    try:
        return bool(_registry_classes(path))
    except ContainmentAbort:
        return False


def resolve_registry(repo_root=REPO_ROOT, env=None):
    """`TABULARIUM_REGISTRY_PATH` -> `checks/FIREWALL-REGISTRY` -> the in-tree script -> None.

    Returns (path or None, how) where `how` names the resolution route for the run log.

    An explicit pointer that names a file which does not exist, or which is not a registry, is a
    misconfiguration and **aborts** — falling through to the next candidate would silently
    downgrade a CARE instance to an unscanned one. Only the in-tree fallback may decline quietly:
    after ADR-0050's A2 cut the script legitimately holds no tokens at all.
    """
    env = os.environ if env is None else env
    repo_root = Path(repo_root)

    explicit = (env.get(REGISTRY_ENV) or "").strip()
    if explicit:
        path = Path(os.path.expanduser(explicit))
        if not path.is_file():
            raise ContainmentAbort("%s names %s, which is not a file — fail closed"
                                   % (REGISTRY_ENV, path))
        if not looks_like_registry(path):
            raise ContainmentAbort("%s names %s, which carries no PII_ class lines — fail closed"
                                   % (REGISTRY_ENV, path))
        return path, "%s" % REGISTRY_ENV

    pointer = repo_root / REGISTRY_CONFIG
    if pointer.is_file():
        named = ""
        for line in pointer.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                named = line
                break
        if not named:
            raise ContainmentAbort("%s exists but names no path — fail closed" % REGISTRY_CONFIG)
        path = Path(os.path.expanduser(named))
        if not path.is_file():
            raise ContainmentAbort("%s names %s, which is not a file — fail closed"
                                   % (REGISTRY_CONFIG, path))
        if not looks_like_registry(path):
            raise ContainmentAbort("%s names %s, which carries no PII_ class lines — fail closed"
                                   % (REGISTRY_CONFIG, path))
        return path, REGISTRY_CONFIG

    in_tree = repo_root / REGISTRY_IN_TREE
    if in_tree.is_file() and looks_like_registry(in_tree):
        return in_tree, REGISTRY_IN_TREE
    return None, "none"


class Registry(object):
    """The four registry classes plus the private-mode identifier, loaded and compile-checked;
    usable only as a scanner, and it matches `SCANNED_CLASSES` only, plus any private mode v2 class
    the private file carries.

    Never printed: `__repr__` deliberately shows the path and the digest, never a class value.
    """

    def __init__(self, path, how, private_path):
        self.path = Path(path)
        self.how = how
        # The registry file alone: the private file's bytes never enter a digest (brute-forceable).
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self._classes = _registry_classes(self.path)
        missing = [name for name, _ in CLASS_LINES if name not in self._classes]
        if missing:
            raise ContainmentAbort(
                "registry at %s is missing class line(s): %s — pre-transit scan blinded "
                "(fail closed)" % (self.path, ", ".join(missing)))
        if private_path is None:
            raise ContainmentAbort(
                "no private-mode identifier file (%s unset, %s absent) — since 2026-09-16 the "
                "identifier lives there, not in the registry; pre-transit scan blinded (fail closed)"
                % (PRIVATE_ENV, PRIVATE_CONFIG))
        private = _private_classes(private_path)
        self._classes.update(private)
        #: what this registry matches: the identifier, and any v2 class the file carries
        self._scanned = [(n, a) for n, a in (PRIVATE_CLASS,) + PRIVATE_V2_CLASSES if n in private]
        self.locale = pick_locale()
        if not self.locale:
            raise ContainmentAbort(
                "no UTF-8 locale on this host — diacritic registry atoms would silently narrow "
                "under the C locale; pre-transit scan blinded (fail closed)")
        self._grep = _grep_binary()
        for name, _ in ALL_CLASSES + tuple(self._scanned[1:]):   # regex sanity, before any path is read
            rc = self._run(["-qiE", "--", self._classes[name]], stdin=b"x").returncode
            if rc >= 2:
                raise ContainmentAbort("the %s class regex does not compile (grep rc=%d) — "
                                       "pre-transit scan blinded (fail closed)" % (name, rc))
            # A class matching an EMPTY line matches every line — what a hand edit leaves behind
            # when it cuts an alternative and keeps its `|`. Unusable, so blinded, not "all hits".
            if self._run(["-qiE", "--", self._classes[name]], stdin=b"\n").returncode == 0:
                raise ContainmentAbort("the %s class regex matches an empty line, so it would match "
                                       "every line — pre-transit scan blinded (fail closed)" % name)

    def __repr__(self):                          # noqa: D105 — content must never reach a traceback
        return "<Registry path=%s digest=%s classes=%d (values withheld)>" % (
            self.path, self.digest[:12], len(self._classes))

    __str__ = __repr__

    def _run(self, args, stdin=None):
        """One scan. The pattern travels in argv, exactly as L9/L18 hand it to grep — a pattern
        FILE would put token bytes on disk outside the registry, which is the artifact class
        the registry split guards against. stdin is closed unless a surface is being piped in, so a scan can never
        block on an inherited terminal."""
        env = dict(os.environ)
        env["LC_ALL"] = self.locale
        kwargs = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
        return subprocess.run([self._grep] + args, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=600, **kwargs)

    def scan_tree(self, root, label=None):
        """Locators for every scanned-class hit anywhere under `root`. Content is never retained."""
        root = Path(root)
        prefix = (label + ":") if label else ""
        hits = []
        for name, _ in self._scanned:
            out = self._run(["-rIniE", "--", self._classes[name], str(root)])
            if out.returncode >= 2:
                raise ContainmentAbort("pre-transit scan errored (grep rc=%d) on %s for the %s "
                                       "class — blinded (fail closed)"
                                       % (out.returncode, root, name))
            if out.returncode != 0:
                continue
            for line in out.stdout.decode("utf-8", "replace").splitlines():
                path, lineno = _split_locator(line)
                try:
                    path = str(Path(path).relative_to(root))
                except ValueError:
                    pass
                hits.append("%s%s:%s (%s class)" % (prefix, path, lineno, name))
        return hits

    def scan_text(self, label, text):
        """Locators for scanned-class hits in one in-memory surface (a prompt, an instruction file)."""
        data = text.encode("utf-8") if isinstance(text, str) else text
        hits = []
        for name, _ in self._scanned:
            out = self._run(["-nIiE", "--", self._classes[name]], stdin=data)
            if out.returncode >= 2:
                raise ContainmentAbort("pre-transit scan errored (grep rc=%d) on %s for the %s "
                                       "class — blinded (fail closed)"
                                       % (out.returncode, label, name))
            if out.returncode != 0:
                continue
            for line in out.stdout.decode("utf-8", "replace").splitlines():
                lineno = line.split(":", 1)[0]
                if not lineno.isdigit():
                    lineno = "?"
                hits.append("%s:%s (%s class)" % (label, lineno, name))
        return hits


def _split_locator(line):
    """(path, line-number) out of one `grep -rn` line, dropping the matched text unread.

    A filename may legally contain ':' (the L18 lesson), so the second field is only trusted when
    it is a number; otherwise the line number is reported as unknown. Either way the third field —
    the matched content — is never returned, so it can never be printed.
    """
    parts = line.split(":", 2)
    if len(parts) >= 2 and parts[1].isdigit():
        return parts[0], parts[1]
    return parts[0], "?"


def roster_handles(repo_root=REPO_ROOT):
    """Directory names under `patients/` — the handles, and nothing else.

    Only names are read. Nothing inside a person's folder is opened, listed or hashed here: the
    keystone's context-discipline rule applies to the harness exactly as to a session.
    """
    base = Path(repo_root) / RECORDS_DIR
    try:
        return sorted(name for name in os.listdir(str(base))
                      if os.path.isdir(os.path.join(str(base), name)))
    except OSError:
        return []


def roster_collision_check(repo_root=REPO_ROOT, fixture_handles=()):
    """Requirement 7 (evals/README.md). Returns the disposition string; raises on a collision.

    Gated on the roster file, per ADR-0050: a record-free instance has no roster to collide with.
    A colliding name is safe to print — by construction it is a fixture handle.
    """
    if not (Path(repo_root) / ROSTER_FILE).is_file():
        return NOT_APPLICABLE_ROSTER
    fixture_handles = set(fixture_handles or ())
    collisions = [h for h in roster_handles(repo_root)
                  if h in fixture_handles or FIXTURE_HANDLE_RE.match(h)]
    if collisions:
        raise ContainmentAbort(
            "roster handle(s) collide with the eval's synthetic handles: %s — a real record and a "
            "fixture would share a folder name (fail closed)" % ", ".join(sorted(collisions)))
    return CLEAN


class Containment(object):
    """One instance's resolved containment posture, reused by every trial of a run."""

    def __init__(self, registry, how, pre_transit_scan, roster_collision_check_, records_present):
        self.registry = registry
        self.how = how
        self.pre_transit_scan = pre_transit_scan
        self.roster_collision_check = roster_collision_check_
        self.records_present = records_present

    @property
    def registry_digest(self):
        """The registry-digest component of the configuration identity — leak-safe by
        construction (a SHA-256 of the file, never its content), the literal `none` when no
        registry exists. Computed in-process from whichever file resolved, so it survives
        ADR-0050's A2 move of the token arrays out of the repository."""
        return self.registry.digest if self.registry else "none"

    def scan_trial(self, label, fixture_dir, task_text):
        """Requirement 6, per trial: the instantiated tree and the task prompt, before the session.
        A no-op on a record-free instance, where there is nothing to scan against."""
        if not self.registry:
            return
        hits = self.registry.scan_tree(fixture_dir, label=label)
        hits += self.registry.scan_text("%s: task prompt" % label, task_text)
        if hits:
            raise ContainmentAbort(
                "pre-transit firewall scan found registry token(s) in material bound for the API "
                "— nothing has been sent; locators only, content withheld", hits)

    def as_row_fields(self):
        return {"pre_transit_scan": self.pre_transit_scan,
                "roster_collision_check": self.roster_collision_check,
                "registry_digest": self.registry_digest}


def preflight(repo_root=REPO_ROOT, fixture_handles=(), instruction_surfaces=(), env=None):
    """Resolve the instance, check the roster, scan the instruction bundle. Once per run.

    `instruction_surfaces` is a sequence of (label, bytes-or-str) — the assembled bundle the
    sessions will be given (keystone bytes under test, the eval-mode addendum, and the intake
    checklist for the profile that supplies it). They do not change between trials, so they are
    scanned here rather than 42 times.
    """
    repo_root = Path(repo_root)
    registry_path, how = resolve_registry(repo_root, env=env)
    private_path, _ = resolve_private(repo_root, env=env)
    records_present = (repo_root / RECORDS_DIR).is_dir()
    roster = roster_collision_check(repo_root, fixture_handles)

    if registry_path is None:
        if records_present:
            raise ContainmentAbort(
                "this tree holds records (%s/ exists) but no firewall registry resolves "
                "(%s unset, %s absent, %s carries no PII_ class lines) — the pre-transit scan "
                "cannot run and a records tree is never sent unscanned (fail closed)"
                % (RECORDS_DIR, REGISTRY_ENV, REGISTRY_CONFIG, REGISTRY_IN_TREE))
        if private_path is not None:
            raise ContainmentAbort(
                "a private-mode identifier file is configured (%s) but no firewall registry "
                "resolves — a half-configured instance is a misconfiguration, never "
                "`not-applicable` (fail closed)" % PRIVATE_CONFIG)
        return Containment(None, how, NOT_APPLICABLE_SCAN, roster, records_present)

    registry = Registry(registry_path, how, private_path)
    hits = []
    for label, blob in instruction_surfaces or ():
        text = blob.decode("utf-8", "replace") if isinstance(blob, bytes) else blob
        hits += registry.scan_text("instruction bundle: %s" % label, text)
    if hits:
        raise ContainmentAbort(
            "pre-transit firewall scan found registry token(s) in the instruction bundle — "
            "nothing has been sent; locators only, content withheld", hits)
    return Containment(registry, how, CLEAN, roster, records_present)


def _main(argv):
    """Print this instance's dispositions. Never prints a token, only paths and digests."""
    try:
        c = preflight(REPO_ROOT, fixture_handles=("evalperson-a", "evalperson-b"))
    except ContainmentAbort as abort:
        print("containment ABORT: %s" % abort.reason)
        for loc in abort.locators:
            print("  %s" % loc)
        return 3
    print("registry route      : %s" % c.how)
    print("registry path       : %s" % (c.registry.path if c.registry else "-"))
    print("registry digest     : %s" % c.registry_digest)
    print("private-mode id     : %s" % ("loaded (path, digest and value withheld)" if c.registry else "-"))
    print("records present     : %s" % ("yes" if c.records_present else "no"))
    print("pre_transit_scan    : %s" % c.pre_transit_scan)
    print("roster_collision    : %s" % c.roster_collision_check)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
