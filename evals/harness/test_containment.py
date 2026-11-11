#!/usr/bin/env python3
"""test_containment.py — self-test for the two instance-aware containment checks.

    python3 -m evals.harness.test_containment
    python3 -m unittest evals.harness.test_containment

WHY IT IS SEPARATE FROM `controls.py`. `controls.py` is the *grader's* driving test — it plants
bad answers and proves the marking scheme catches them. This file tests the harness's containment
machinery instead: registry resolution, the pre-transit scan, the roster-collision assert, that
a free check removes its run root, that a paid run's root goes to the archive only matched, and the
canary probe's verdict. Keeping them apart keeps the controls count meaningful (a
control is an oracle assertion, not a harness unit test).

DISCIPLINE, borrowed wholesale from `checks/selftest.sh`: **every case has a negative control.**
A check that fires on a planted token proves nothing unless the same check stays silent on the
clean tree next to it — a scan that fires on everything is as useless as one that fires on
nothing. So the cases come in pairs, and both halves are counted.

EVERYTHING HERE IS SYNTHETIC. The registries this file writes carry invented tokens
(`Zzyzxwold`, `KZ-99-777`), never a real class value; the real registry is never read, copied or
consulted by any case below. That is the point: this file must be runnable in a DEV instance that
has no registry at all.
"""

import contextlib
import datetime
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.harness import containment, paths  # noqa: E402  (needs the path bootstrap above)

# Invented tokens. Chosen to be unmistakably synthetic and to contain no substring of any real
# clinical or personal vocabulary. Nothing in this file is a class value, so it stays safe to read
# in any instance — including a DEV tree that holds no registry, where these cases still run.
FAKE_IDENTITY = "Zzyzxwold"
#: A leftover line of the retired case-reference class (ADR-0072): every reader must ignore it.
FAKE_CASEREF = "KZ-99-777"
FAKE_REGISTRY = (
    "#!/bin/bash\n"
    "PII_IDENTITY='%s'\n"
    "PII_CASEREF='%s'\n"
    "PII_CLINICAL='qwyxdrome'\n"
    "PII_BRAND='Vvexicorp'\n"
    "PII_CONSENT='nnarcolytic'\n"
    "PII_REST=\"$PII_CLINICAL|$PII_BRAND\"\n"
    "ALLOW=(\n  CLAUDE.md\n)\n"
    "readonly ALLOW\n"
    "DENY=(\n  patients\n)\n"
    "for p in \"${ALLOW[@]}\"; do :; done\n"
) % (FAKE_IDENTITY, FAKE_CASEREF)

#: The synthetic private-mode identifier (ADR-0050 point 9): its own class, its own file.
FAKE_PRIVATE = "Qwxprivtok"


def fake_private(path, value=FAKE_PRIVATE, mode=0o600, body=None):
    """A synthetic private-mode identifier file: one class line, owner-only unless told otherwise."""
    path = Path(path)
    paths.ensure_dir(path.parent)
    path.write_text(body if body is not None else "# synthetic\nPII_PRIVATE_MODE_ID='%s'\n" % value,
                    encoding="utf-8")
    os.chmod(str(path), mode)
    return path


#: The run date every fixture-date case uses. Deliberately far future and deliberately fixed: the
#: cases stay deterministic whatever day they run, and a date derived from a future run date cannot
#: be a real case date however the arithmetic lands.
FIXED_RUN_DATE = datetime.date(2031, 3, 14)

#: `archive.restore` refuses a Python whose tarfile has no data filter (before 3.12): its checks skip.
CAN_RESTORE = hasattr(tarfile, "data_filter")

PASS = []
FAIL = []


def check(label, ok, why=""):
    (PASS if ok else FAIL).append(label)
    print("%-5s %s%s" % ("OK" if ok else "MISS", label, ("  — " + why) if why and not ok else ""))
    return ok


def aborts(label, fn, wanted_substring=None, want_locator=None):
    """Assert `fn()` raises ContainmentAbort; optionally that the reason/locators say the right thing."""
    try:
        fn()
    except containment.ContainmentAbort as abort:
        if wanted_substring and wanted_substring not in abort.reason:
            return check(label, False, "aborted for the wrong reason: %s" % abort.reason)
        if want_locator is not None:
            joined = " ".join(abort.locators)
            if want_locator not in joined:
                return check(label, False, "locators lack %r (got %r)" % (want_locator, joined))
        return check(label, True)
    except Exception as exc:                      # noqa: BLE001
        return check(label, False, "raised %s: %s" % (type(exc).__name__, exc))
    return check(label, False, "did not abort")


def _or_none(fn):
    """Call `fn`, returning None if it aborts — so an unexpected abort is a MISS, not a crash."""
    try:
        return fn()
    except containment.ContainmentAbort:
        return None


_CRASHED = object()


def _or_crashed(fn):
    """Call `fn`, returning the `_CRASHED` sentinel on ANY exception.

    Same reason as `_or_none`, one level wider: a check whose subject raises must report a named
    MISS, never take the suite down with it. Proven necessary — deleting `regrade_run`'s
    fixture-free guard used to kill this file mid-run, so the guard had loud behaviour but no
    bite: no MISS line, no summary, nothing a reader could name.
    """
    try:
        return fn()
    except Exception as exc:                      # noqa: BLE001 — a crash IS the failure here
        print("      (raised %s: %s)" % (type(exc).__name__, exc))
        return _CRASHED


def survives(label, fn, want=None):
    """Assert `fn()` returns (does not abort); optionally that it returns `want`."""
    try:
        got = fn()
    except containment.ContainmentAbort as abort:
        return check(label, False, "aborted: %s" % abort.reason)
    except Exception as exc:                      # noqa: BLE001
        return check(label, False, "raised %s: %s" % (type(exc).__name__, exc))
    if want is not None and got != want:
        return check(label, False, "returned %r, wanted %r" % (got, want))
    return check(label, True)


# --------------------------------------------------------------------------- fixture trees

def mk_instance(root, records=False, registry="in-tree", pointer_target=None):
    """A synthetic repository root.

    records=True   -> `patients/` with a roster and one handle (a CARE-shaped tree)
    registry       -> "in-tree" | "none" | "empty-script" | "pointer"
    """
    root = Path(root)
    paths.ensure_dir(root / "checks")
    (root / "CLAUDE.md").write_text("synthetic keystone for the containment self-test\n",
                                    encoding="utf-8")
    if registry == "in-tree":
        (root / "checks" / "publish-skeleton.sh").write_text(FAKE_REGISTRY, encoding="utf-8")
    elif registry == "empty-script":
        # ADR-0050 A2 leaves the export script in place with the token arrays cut out of it.
        (root / "checks" / "publish-skeleton.sh").write_text(
            "#!/bin/bash\nALLOW=(\n  CLAUDE.md\n)\nreadonly ALLOW\n", encoding="utf-8")
    elif registry == "pointer":
        (root / "checks" / "FIREWALL-REGISTRY").write_text(
            "# where the token arrays live\n%s\n" % pointer_target, encoding="utf-8")
    if records:
        paths.ensure_dir(root / "patients" / "someone")
        (root / "patients" / "README.md").write_text("# roster\n", encoding="utf-8")
    return root


def mk_fixture_tree(root, planted=None):
    """A synthetic instantiated fixture tree, optionally with a token planted in it."""
    root = Path(root)
    paths.ensure_dir(root / "patients" / "evalperson-a")
    (root / "CLAUDE.md").write_text("keystone bytes\n", encoding="utf-8")
    body = "# profile\n\nDrug X, taken daily (caregiver report, grade B)\n"
    if planted:
        body += "contact: %s\n" % planted
    (root / "patients" / "evalperson-a" / "profile.md").write_text(body, encoding="utf-8")
    return root


# --------------------------------------------------------------------------- the cases

def case_registry_resolution(tmp):
    """Resolution order, both directions: the env var wins, the pointer beats the in-tree script,
    and a slimmed in-tree script (post-A2) resolves to nothing rather than to a false registry."""
    tree = mk_instance(tmp / "res-in-tree", registry="in-tree")
    survives("R1  in-tree script carrying PII_ lines resolves",
             lambda: containment.resolve_registry(tree, env={})[1],
             want=containment.REGISTRY_IN_TREE)

    # NEGATIVE CONTROL for R1: the same script with the token arrays cut out must NOT resolve.
    slim = mk_instance(tmp / "res-slim", registry="empty-script")
    survives("R2  slimmed in-tree script (post-A2) resolves to none",
             lambda: containment.resolve_registry(slim, env={})[1], want="none")

    elsewhere = tmp / "elsewhere-registry.sh"
    elsewhere.write_text(FAKE_REGISTRY, encoding="utf-8")
    ptr = mk_instance(tmp / "res-pointer", registry="pointer", pointer_target=str(elsewhere))
    survives("R3  checks/FIREWALL-REGISTRY pointer resolves out of tree",
             lambda: containment.resolve_registry(ptr, env={})[0], want=elsewhere)

    # The env var outranks the config file: same tree, a different registry named in the env.
    other = tmp / "env-registry.sh"
    other.write_text(FAKE_REGISTRY, encoding="utf-8")
    survives("R4  TABULARIUM_REGISTRY_PATH wins over the config file",
             lambda: containment.resolve_registry(
                 ptr, env={containment.REGISTRY_ENV: str(other)})[0], want=other)
    # ... and over the in-tree script.
    survives("R5  TABULARIUM_REGISTRY_PATH wins over the in-tree script",
             lambda: containment.resolve_registry(
                 tree, env={containment.REGISTRY_ENV: str(other)})[1],
             want=containment.REGISTRY_ENV)
    # `~` is expanded when resolving registry paths; see checks/topics/relay-and-export.md → *The token registry*.
    # HOME points at the scratch dir for this one case, so it runs wherever the scratch dir lives.
    real_home = os.environ.get("HOME")
    os.environ["HOME"] = str(other.parent)
    try:
        survives("R6  a ~-relative env path is expanded",
                 lambda: containment.resolve_registry(
                     tree, env={containment.REGISTRY_ENV: "~/" + other.name})[0], want=other)
    finally:
        if real_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = real_home

    # An explicit pointer that names nothing fails CLOSED — it never falls through to a weaker
    # candidate, because that would silently downgrade a CARE instance to an unscanned one.
    aborts("R7  env var naming a missing file aborts",
           lambda: containment.resolve_registry(tree, env={containment.REGISTRY_ENV:
                                                           str(tmp / "no-such-file.sh")}),
           wanted_substring="not a file")
    bad = mk_instance(tmp / "res-badptr", registry="pointer",
                      pointer_target=str(tmp / "no-such-file.sh"))
    aborts("R8  pointer file naming a missing file aborts",
           lambda: containment.resolve_registry(bad, env={}), wanted_substring="not a file")

    # WP8 (2026-09-06): the registry gained a SIXTH assignment, `BRAND_ADJ_PAIRS`, carrying the export
    # gate's wrapped-brand adjacency pairs. Its name deliberately does not match `PII_[A-Z]+=`, and
    # every reader that enumerates the class SET must keep counting exactly four — a reader that
    # counted five would fail closed and blind the pre-transit scan for no reason.
    extra = tmp / "pairs-registry.sh"
    extra.write_text(FAKE_REGISTRY + "BRAND_ADJ_PAIRS='alpha beta|gamma delta'\n", encoding="utf-8")
    survives("R9  a registry carrying BRAND_ADJ_PAIRS still enumerates exactly four classes",
             lambda: len(containment._registry_classes(extra)), want=4)
    survives("R9a it still reads as a registry",
             lambda: containment.looks_like_registry(extra), want=True)
    ptr2 = mk_instance(tmp / "res-pairs", registry="pointer", pointer_target=str(extra))
    survives("R9b and still resolves through the pointer",
             lambda: containment.resolve_registry(ptr2, env={})[0], want=extra)
    # NEGATIVE CONTROL for R9: the pairs line ALONE is not a registry. If it ever counted as one, a
    # file that merely carried adjacency pairs would resolve as a token source and be scanned against.
    only = tmp / "pairs-only.sh"
    only.write_text("#!/bin/bash\nBRAND_ADJ_PAIRS='alpha beta'\n", encoding="utf-8")
    survives("R10 a file carrying ONLY BRAND_ADJ_PAIRS is not a registry",
             lambda: containment.looks_like_registry(only), want=False)


def case_pre_transit_scan(tmp):
    """Requirement 6: the private-mode identifier aborts with a locator and no token text; the
    other five classes no longer stop a run (narrowed 2026-09-28); the clean twin passes."""
    registry = tmp / "scan-registry.sh"
    registry.write_text(FAKE_REGISTRY, encoding="utf-8")
    reg = containment.Registry(registry, "test", fake_private(tmp / "scan-private.sh"))

    clean = mk_fixture_tree(tmp / "tree-clean")
    survives("S1  clean fixture tree scans clean", lambda: reg.scan_tree(clean), want=[])

    # NEGATIVE CONTROL for S1: the same tree with the private-mode identifier planted is caught.
    dirty = mk_fixture_tree(tmp / "tree-dirty", planted=FAKE_PRIVATE)
    hits = reg.scan_tree(dirty)
    check("S2  a planted private-mode identifier in the tree is caught", len(hits) == 1,
          "got %d hits" % len(hits))
    if hits:
        check("S3  the hit is a locator (path:line (class))",
              hits[0].startswith("patients/evalperson-a/profile.md:")
              and hits[0].endswith("(private-mode-id class)"), hits[0])
        check("S4  the locator carries no token text", FAKE_PRIVATE not in hits[0], hits[0])
    else:
        check("S3  the hit is a locator (path:line (class))", False)
        check("S4  the locator carries no token text", False)

    # The narrowing, pinned: tokens of the other five classes are ordinary care-session traffic and
    # no longer stop a run. S2 is their negative control — the scanner is live, it just looks for
    # one class.
    for label, token in (("S5  an identity-class token no longer stops a run", FAKE_IDENTITY),
                         ("S5a nor a case-reference token", "ref " + FAKE_CASEREF),
                         ("S5b nor a brand token", "Vvexicorp")):
        tree = mk_fixture_tree(tmp / ("tree-%s" % label[:3].strip()), planted=token)
        survives(label, lambda: reg.scan_tree(tree), want=[])

    # The prompt surface, both directions.
    survives("S6  clean task prompt scans clean",
             lambda: reg.scan_text("EV-01a-t1: task prompt",
                                   "Please update the profile for evalperson-a."), want=[])
    ptext = reg.scan_text("EV-01a-t1: task prompt", "line one\nask %s about it\n" % FAKE_PRIVATE)
    check("S7  the identifier in the task prompt is caught with its line number",
          ptext == ["EV-01a-t1: task prompt:2 (private-mode-id class)"], str(ptext))

    # And end to end, through the object a run actually uses.
    c = containment.Containment(reg, "test", containment.CLEAN, containment.CLEAN, True)
    survives("S8  scan_trial passes a clean tree + prompt",
             lambda: c.scan_trial("EV-01a-t1", clean, "do the thing"))
    aborts("S9  scan_trial aborts on the planted identifier, locators only",
           lambda: c.scan_trial("EV-01a-t1", dirty, "do the thing"),
           wanted_substring="content withheld", want_locator="(private-mode-id class)")


def case_blinded_scanner(tmp):
    """A scanner that cannot see must abort, never report clean: the three blinding modes."""
    good = tmp / "blind-good.sh"
    good.write_text(FAKE_REGISTRY, encoding="utf-8")
    priv = fake_private(tmp / "blind-private.sh")

    # A registry short one class line would scan four-fifths of the material and call it clean.
    partial = tmp / "blind-partial.sh"
    partial.write_text(FAKE_REGISTRY.replace("PII_CONSENT='nnarcolytic'\n", ""), encoding="utf-8")
    aborts("B1  a registry missing a class line aborts (blinded)",
           lambda: containment.Registry(partial, "test", priv), wanted_substring="missing class line")
    # NEGATIVE CONTROL for B1: the complete registry constructs.
    survives("B2  the complete registry constructs",
             lambda: bool(containment.Registry(good, "test", priv)), want=True)

    # No UTF-8 locale: BSD grep silently narrows diacritic atoms under C, with rc=1, not rc=2 —
    # a green that examined less than it claims. L18's reason, and its answer: refuse to scan.
    real_pick = containment.pick_locale
    containment.pick_locale = lambda: None
    try:
        aborts("B3  no UTF-8 locale aborts rather than scanning narrowed",
               lambda: containment.Registry(good, "test", priv), wanted_substring="blinded")
    finally:
        containment.pick_locale = real_pick

    # A scan grep at rc>=2 is an ERROR, never "no hits" (the L5/ADR-0021 lesson). Forced here,
    # because a class value that failed to compile would already have been caught at construction.
    class _Rc(object):
        returncode = 2
        stdout = b""

    reg = containment.Registry(good, "test", priv)
    tree = mk_fixture_tree(tmp / "blind-tree")
    real_run = reg._run
    reg._run = lambda *a, **k: _Rc()
    try:
        aborts("B4  a scan grep at rc>=2 aborts, never reports clean",
               lambda: reg.scan_tree(tree), wanted_substring="blinded")
    finally:
        reg._run = real_run
    # NEGATIVE CONTROL for B4: rc=1 is the ordinary "no hits" and must stay silent.
    _Rc.returncode = 1
    reg._run = lambda *a, **k: _Rc()
    try:
        survives("B5  rc=1 is no-hits, not an error", lambda: reg.scan_tree(tree), want=[])
    finally:
        reg._run = real_run


def case_instance_dispositions(tmp):
    """Requirement 6's instance arms: record-free -> not-applicable; records without a registry -> abort."""
    dev = mk_instance(tmp / "inst-dev", records=False, registry="none")
    # `_or_none` so a check that aborts where it must not is reported as a MISS, not a traceback:
    # a self-test that crashes tells the operator less than one that names the failing case.
    c = _or_none(lambda: containment.preflight(dev, fixture_handles=("evalperson-a",), env={}))
    check("I1  record-free instance records not-applicable",
          c is not None and c.pre_transit_scan == containment.NOT_APPLICABLE_SCAN,
          "aborted" if c is None else c.pre_transit_scan)
    check("I2  record-free instance uses the literal `none` as the registry digest",
          c is not None and c.registry_digest == "none",
          "aborted" if c is None else c.registry_digest)
    check("I3  its row fields carry both dispositions",
          c is not None and set(c.as_row_fields()) == {"pre_transit_scan",
                                                       "roster_collision_check",
                                                       "registry_digest"},
          "aborted" if c is None else str(sorted(c.as_row_fields())))

    # NEGATIVE CONTROL for I1: the same tree WITH records and no registry must abort, not
    # quietly record not-applicable. This is the dangerous middle the fail-closed rule exists for.
    care_no_reg = mk_instance(tmp / "inst-records-noreg", records=True, registry="none")
    aborts("I4  records present + no registry aborts (fail closed)",
           lambda: containment.preflight(care_no_reg, fixture_handles=("evalperson-a",), env={}),
           wanted_substring="holds records")

    # A slimmed in-tree script is the same case: present, but not a registry.
    care_slim = mk_instance(tmp / "inst-records-slim", records=True, registry="empty-script")
    aborts("I5  records present + slimmed script aborts (fail closed)",
           lambda: containment.preflight(care_slim, fixture_handles=("evalperson-a",), env={}),
           wanted_substring="holds records")

    # And the healthy CARE arm: records + a resolvable registry -> a real scan, recorded clean.
    care = mk_instance(tmp / "inst-care", records=True, registry="in-tree")
    penv = {containment.PRIVATE_ENV: str(fake_private(tmp / "inst-private.sh"))}
    ok = _or_none(lambda: containment.preflight(
        care, fixture_handles=("evalperson-a",), env=penv,
        instruction_surfaces=[("CLAUDE.md", b"keystone bytes\n")]))
    check("I6  records + registry records a real clean scan",
          ok is not None and ok.pre_transit_scan == containment.CLEAN
          and ok.registry_digest != "none",
          "aborted" if ok is None else ok.pre_transit_scan)

    # NEGATIVE CONTROL for I6: the private-mode identifier in the instruction bundle aborts.
    aborts("I7  the identifier in the instruction bundle aborts the preflight",
           lambda: containment.preflight(
               care, fixture_handles=("evalperson-a",), env=penv,
               instruction_surfaces=[("CLAUDE.md", ("keystone %s\n" % FAKE_PRIVATE).encode())]),
           wanted_substring="instruction bundle", want_locator="instruction bundle: CLAUDE.md:1")
    # The incident the narrowing answers (2026-09-28): an ordinary word in CLAUDE.md matched a
    # brand atom and stopped the operator's run. Any other class in the bundle is not a stop.
    ok7 = _or_none(lambda: containment.preflight(
        care, fixture_handles=("evalperson-a",), env=penv,
        instruction_surfaces=[("CLAUDE.md", ("keystone %s Vvexicorp\n" % FAKE_IDENTITY).encode())]))
    check("I7a another class's token in the instruction bundle no longer aborts",
          ok7 is not None and ok7.pre_transit_scan == containment.CLEAN,
          "aborted" if ok7 is None else ok7.pre_transit_scan)

    # The honest scope of the record-free arm, pinned so it cannot drift into a false claim: with
    # no registry there is nothing to scan AGAINST, so scan_trial is a no-op even on a tree that a
    # CARE instance would abort on (S9 is that same tree, aborting). `not-applicable` on the row is
    # therefore the literal truth, and the docs must never call it a clean scan.
    dirty = mk_fixture_tree(tmp / "inst-dev-dirty", planted=FAKE_PRIVATE)
    dev_c = containment.Containment(None, "none", containment.NOT_APPLICABLE_SCAN,
                                    containment.NOT_APPLICABLE_ROSTER, False)
    survives("I8  a record-free instance's scan_trial is an honest no-op, not a claimed scan",
             lambda: dev_c.scan_trial("EV-01a-t1", dirty, "task"))

    # NEGATIVE CONTROL for I6, second direction: requirement 7 aborts the WHOLE preflight, not
    # just its own helper — a collision found and then returned would be no check at all.
    collide = mk_instance(tmp / "inst-collide", records=True, registry="in-tree")
    paths.ensure_dir(collide / "patients" / "evalperson-a")
    aborts("I9  a roster collision aborts the preflight itself",
           lambda: containment.preflight(collide, fixture_handles=("evalperson-a",), env={}),
           wanted_substring="collide")


def case_private_mode_file(tmp):
    """The private-mode identifier's own file (ADR-0050 point 9): scanned as a sixth
    class, required wherever a registry resolves, and every unusable shape of it blinds the scan."""
    registry = tmp / "pm-registry.sh"
    registry.write_text(FAKE_REGISTRY, encoding="utf-8")
    good = fake_private(tmp / "pm" / "private-mode-id.sh")

    # Resolution, both routes, and the absent case.
    tree = mk_instance(tmp / "pm-res", registry="none")
    survives("V1  no pointer and no env resolves to none",
             lambda: containment.resolve_private(tree, env={})[1], want="none")
    (tree / "checks" / "PRIVATE-MODE-ID").write_text("# path\n%s\n" % good, encoding="utf-8")
    survives("V2  checks/PRIVATE-MODE-ID resolves", lambda: containment.resolve_private(tree, env={})[0],
             want=good)
    other = fake_private(tmp / "pm-env" / "private-mode-id.sh")
    survives("V3  TABULARIUM_PRIVATE_MODE_ID_PATH wins over the pointer",
             lambda: containment.resolve_private(tree, env={containment.PRIVATE_ENV: str(other)})[0],
             want=other)
    (tree / "checks" / "PRIVATE-MODE-ID").write_text("%s\n" % (tmp / "nowhere.sh"), encoding="utf-8")
    aborts("V4  a pointer naming nothing aborts", lambda: containment.resolve_private(tree, env={}),
           wanted_substring="does not exist")
    (tree / "checks" / "PRIVATE-MODE-ID").write_text("relative/private-mode-id.sh\n", encoding="utf-8")
    aborts("V5  a pointer naming a relative path aborts", lambda: containment.resolve_private(tree, env={}),
           wanted_substring="no absolute path")

    # The file itself: the good one constructs, every unusable shape blinds.
    survives("V6  a registry plus a good private file constructs",
             lambda: bool(containment.Registry(registry, "test", good)), want=True)
    aborts("V7  no private file at all blinds the scan",
           lambda: containment.Registry(registry, "test", None), wanted_substring="no private-mode identifier file")
    link = tmp / "pm" / "link.sh"
    os.symlink(str(good), str(link))
    aborts("V8  a symlinked private file is never followed",
           lambda: containment.Registry(registry, "test", link), wanted_substring="symlink")
    loose = fake_private(tmp / "pm" / "loose.sh", mode=0o640)
    aborts("V9  a group-readable private file blinds the scan",
           lambda: containment.Registry(registry, "test", loose), wanted_substring="not owner-only")
    two = fake_private(tmp / "pm" / "two.sh", body="PII_PRIVATE_MODE_ID='%s'\nPII_EXTRA='x'\n" % FAKE_PRIVATE)
    aborts("V10 a second class line in the private file blinds the scan",
           lambda: containment.Registry(registry, "test", two), wanted_substring="exactly one")
    # private mode v2 (ADR-0029 point 13): one PII_PRIVATE_<CLASS> line per registry class
    # is accepted and matched like the identifier; a duplicate or an empty one blinds.
    v2 = fake_private(tmp / "pm" / "v2.sh", body="PII_PRIVATE_MODE_ID='%s'\nPII_PRIVATE_IDENTITY='Qwxvtwotok'\n"
                      % FAKE_PRIVATE)
    v2reg = containment.Registry(registry, "test", v2)
    v2hits = v2reg.scan_text("EV-01a-t1: task prompt", "line one\nmeet Qwxvtwotok today\n")
    check("V10a a v2 class line is scanned like the identifier (located, value withheld)",
          v2hits == ["EV-01a-t1: task prompt:2 (private-identity class)"]
          and not any("Qwxvtwotok" in h for h in v2hits), repr(v2hits))
    check("V10b ... and its clean twin reads clean",
          v2reg.scan_text("EV-01a-t1: task prompt", "line one\nmeet nobody\n") == [])
    dup = fake_private(tmp / "pm" / "dup.sh", body="PII_PRIVATE_MODE_ID='%s'\nPII_PRIVATE_IDENTITY='a1'\n"
                       "PII_PRIVATE_IDENTITY='b2'\n" % FAKE_PRIVATE)
    aborts("V10c two lines of one v2 class blind the scan",
           lambda: containment.Registry(registry, "test", dup), wanted_substring="at most one")
    v2empty = fake_private(tmp / "pm" / "v2empty.sh", body="PII_PRIVATE_MODE_ID='%s'\nPII_PRIVATE_CLINICAL=''\n"
                           % FAKE_PRIVATE)
    aborts("V10d an empty v2 class blinds the scan",
           lambda: containment.Registry(registry, "test", v2empty), wanted_substring="at most one")
    # The retired case-reference class (ADR-0072): a leftover v2 line neither blinds nor is matched,
    # and a registry without its line still constructs. V10 is the negative control: an unknown line blinds.
    v2old = fake_private(tmp / "pm" / "v2old.sh", body="PII_PRIVATE_MODE_ID='%s'\nPII_PRIVATE_CASEREF='Qwxoldcase'\n"
                         % FAKE_PRIVATE)
    survives("V10f a leftover PII_PRIVATE_CASEREF line is ignored, never matched",
             lambda: containment.Registry(registry, "test", v2old).scan_text(
                 "EV-01a-t1: task prompt", "meet Qwxoldcase today\n"), want=[])
    nocase = tmp / "pm" / "nocase-registry.sh"
    nocase.write_text(FAKE_REGISTRY.replace("PII_CASEREF='%s'\n" % FAKE_CASEREF, ""), encoding="utf-8")
    survives("V10g a registry without the case-reference line still constructs",
             lambda: bool(containment.Registry(nocase, "test", good)), want=True)
    for i, near in enumerate(("export PII_PRIVATE_BRAND='a1'", "PII_PRIVATE_BRAND = 'a1'",
                              "pii_private_brand='a1'", "PII_PRIVATE_BRAND2='a1'",
                              "PII_PRIVATE_BRAND='a1'; PII_PRIVATE_CASEREF='b2'", " PII_PRIVATE_BRAND='a1'",
                              # Codex review of PR #92: one quoted pair, no ' inside — read greedily,
                              # either line is one value that matches neither token
                              "PII_PRIVATE_BRAND='a1'|'b2'", "PII_PRIVATE_BRAND='a1'x'b2'")):
        nm = fake_private(tmp / "pm" / ("near%d.sh" % i), body="PII_PRIVATE_MODE_ID='%s'\n%s\n" % (FAKE_PRIVATE, near))
        aborts("V10e%d a near-miss private-file line is never ignored (%s)" % (i, near.strip()[:28]),
               lambda nm=nm: containment.Registry(registry, "test", nm), wanted_substring="lines only")
    empty = fake_private(tmp / "pm" / "empty.sh", value="")
    aborts("V11 an empty private class blinds the scan",
           lambda: containment.Registry(registry, "test", empty), wanted_substring="exactly one")
    crlf = fake_private(tmp / "pm" / "crlf.sh", body="PII_PRIVATE_MODE_ID='%s'\r\n" % FAKE_PRIVATE)
    aborts("V11a a private file with CR line endings is refused, as the other readers refuse it",
           lambda: containment.Registry(registry, "test", crlf), wanted_substring="carriage-return")
    everything = fake_private(tmp / "pm" / "everything.sh", value="(%s)?" % FAKE_PRIVATE)
    aborts("V12 a private class that matches an empty line blinds the scan",
           lambda: containment.Registry(registry, "test", everything), wanted_substring="empty line")
    # The shape a botched cut really leaves: BSD grep refuses a trailing `|` (does not compile), GNU
    # grep accepts it and matches every line (empty line). Either way the scan must be blinded.
    stray = fake_private(tmp / "pm" / "stray.sh", value=FAKE_PRIVATE + "|")
    aborts("V13 a private class left with a stray | by the cut blinds the scan",
           lambda: containment.Registry(registry, "test", stray), wanted_substring="blinded")
    stray_reg = tmp / "pm-stray-registry.sh"
    stray_reg.write_text(FAKE_REGISTRY.replace("PII_BRAND='Vvexicorp'", "PII_BRAND='Vvexicorp|'"),
                         encoding="utf-8")
    aborts("V13a ...and so does a REGISTRY class left with a stray | by the cut",
           lambda: containment.Registry(stray_reg, "test", good), wanted_substring="blinded")

    # The scan, both directions, locators only.
    reg = containment.Registry(registry, "test", good)
    clean = mk_fixture_tree(tmp / "pm-tree-clean")
    survives("V14 a clean tree scans clean", lambda: reg.scan_tree(clean), want=[])
    dirty = mk_fixture_tree(tmp / "pm-tree-dirty", planted=FAKE_PRIVATE)
    hits = reg.scan_tree(dirty)
    check("V15 a planted private-mode identifier is caught as its own class",
          len(hits) == 1 and hits[0].endswith("(private-mode-id class)"), str(hits))
    check("V16 ...with a locator only, no token text", all(FAKE_PRIVATE not in h for h in hits), str(hits))
    ptext = reg.scan_text("EV-01a-t1: task prompt", "ask about %s\n" % FAKE_PRIVATE)
    check("V18 a private-mode identifier in the task prompt is caught",
          ptext == ["EV-01a-t1: task prompt:1 (private-mode-id class)"], str(ptext))
    check("V19 repr withholds the private value", FAKE_PRIVATE not in repr(reg), repr(reg))

    # The digest binds the registry file only: a one-line file's hash is brute-forceable.
    before = reg.digest
    fake_private(good, value="Qwxothertok")
    check("V20 the registry digest does not move when only the private file changes",
          containment.Registry(registry, "test", good).digest == before)

    # Preflight arms.
    split = mk_instance(tmp / "pm-pre-split", records=True, registry="pointer", pointer_target=str(registry))
    aborts("V21 a registry without the private file aborts the preflight (blinded)",
           lambda: containment.preflight(split, fixture_handles=("evalperson-a",), env={}),
           wanted_substring="no private-mode identifier file")
    (split / "checks" / "PRIVATE-MODE-ID").write_text("%s\n" % good, encoding="utf-8")
    c = _or_none(lambda: containment.preflight(split, fixture_handles=("evalperson-a",), env={}))
    check("V22 NEGATIVE CONTROL for V21: registry + private file is a real clean scan",
          c is not None and c.pre_transit_scan == containment.CLEAN, "aborted" if c is None else c.pre_transit_scan)
    half = mk_instance(tmp / "pm-half", records=False, registry="none")
    (half / "checks" / "PRIVATE-MODE-ID").write_text("%s\n" % good, encoding="utf-8")
    aborts("V23 a private file with no registry is a misconfiguration, not not-applicable",
           lambda: containment.preflight(half, fixture_handles=("evalperson-a",), env={}),
           wanted_substring="half-configured")


def case_roster_collision(tmp):
    """Requirement 7: a roster handle that looks like a fixture handle is caught; a real one is not."""
    clean = mk_instance(tmp / "roster-clean", records=True, registry="in-tree")
    survives("P1  an ordinary roster passes",
             lambda: containment.roster_collision_check(clean, ("evalperson-a", "evalperson-b")),
             want=containment.CLEAN)

    # NEGATIVE CONTROL for P1: the exact fixture handle on the roster must be caught.
    exact = mk_instance(tmp / "roster-exact", records=True, registry="in-tree")
    paths.ensure_dir(exact / "patients" / "evalperson-a")
    aborts("P2  a roster handle equal to a fixture handle aborts",
           lambda: containment.roster_collision_check(exact, ("evalperson-a", "evalperson-b")),
           wanted_substring="collide")

    # ... and so must any `evalperson-*`, even one no fixture uses (ADR-0050's CARE-side rule).
    near = mk_instance(tmp / "roster-near", records=True, registry="in-tree")
    paths.ensure_dir(near / "patients" / "evalperson-q")
    aborts("P3  any evalperson-* roster handle aborts",
           lambda: containment.roster_collision_check(near, ("evalperson-a", "evalperson-b")),
           wanted_substring="collide")

    # No roster -> not-applicable, and nothing under patients/ is opened either way.
    dev = mk_instance(tmp / "roster-none", records=False, registry="in-tree")
    survives("P4  no roster file records not-applicable",
             lambda: containment.roster_collision_check(dev, ("evalperson-a",)),
             want=containment.NOT_APPLICABLE_ROSTER)

    # Only directory names count: a stray FILE named like a fixture handle is not a handle.
    filey = mk_instance(tmp / "roster-file", records=True, registry="in-tree")
    (filey / "patients" / "evalperson-a.md").write_text("not a handle\n", encoding="utf-8")
    survives("P5  a file (not a directory) named like a handle is not a collision",
             lambda: containment.roster_collision_check(filey, ("evalperson-a",)),
             want=containment.CLEAN)


def case_no_content_ever_leaks(tmp):
    """The scanner must be structurally unable to print a token: repr, str, and abort text."""
    registry = tmp / "leak-registry.sh"
    registry.write_text(FAKE_REGISTRY, encoding="utf-8")
    reg = containment.Registry(registry, "test", fake_private(tmp / "leak-private.sh"))
    check("L1  repr(Registry) withholds the class values",
          FAKE_IDENTITY not in repr(reg) and FAKE_CASEREF not in repr(reg)
          and FAKE_PRIVATE not in repr(reg), repr(reg))
    check("L2  str(Registry) withholds the class values",
          FAKE_IDENTITY not in str(reg), str(reg))
    dirty = mk_fixture_tree(tmp / "leak-tree", planted=FAKE_PRIVATE)
    try:
        containment.Containment(reg, "test", containment.CLEAN, containment.CLEAN,
                                True).scan_trial("EV-01a-t1", dirty, "task")
        check("L3  an abort's text carries no token", False, "did not abort")
    except containment.ContainmentAbort as abort:
        blob = abort.reason + " " + " ".join(abort.locators)
        check("L3  an abort's text carries no token", FAKE_PRIVATE not in blob, blob)


def case_run_log_rows(tmp):
    """The run log: every trial row carries both dispositions; an abort writes one `aborted` row."""
    import datetime
    import types

    from evals.harness import regrade, run_eval

    registry = tmp / "rows-registry.sh"
    registry.write_text(FAKE_REGISTRY, encoding="utf-8")
    reg = containment.Registry(registry, "test", fake_private(tmp / "rows-private.sh"))
    ledger = tmp / "rows" / "ledger.jsonl"
    run_root = tmp / "rows" / "run"
    paths.ensure_dir(run_root)

    def ctx_with(c):
        return types.SimpleNamespace(
            today=datetime.date(2026, 9, 6), run_root=run_root, stack_rev="worktree",
            stack_hashes={"canonical-update": "deadbeef"},
            # The instruction-stack blobs a real ctx carries since 2026-09-07:
            # synthetic here, and asserted absent from the row's text by G4 like everything else.
            keystone_blob="0" * 40, addendum_blob="1" * 40, containment=c)

    manifest = {"id": "EV-01a", "profile": "canonical-update"}
    care = ctx_with(containment.Containment(reg, "test", containment.CLEAN,
                                            containment.CLEAN, True))
    row = run_eval.trial_row(care, manifest, "EV-01a-t1")
    check("G1  a CARE trial row records the scan disposition",
          row.get("pre_transit_scan") == containment.CLEAN, str(row.get("pre_transit_scan")))
    check("G2  a CARE trial row records the roster disposition",
          row.get("roster_collision_check") == containment.CLEAN,
          str(row.get("roster_collision_check")))
    check("G3  a CARE trial row binds the registry digest",
          row.get("registry_digest") == reg.digest, str(row.get("registry_digest")))
    check("G4  no token text anywhere in the row",
          FAKE_IDENTITY not in json.dumps(row), "row leaked a class value")

    dev = ctx_with(containment.Containment(None, "none", containment.NOT_APPLICABLE_SCAN,
                                           containment.NOT_APPLICABLE_ROSTER, False))
    drow = run_eval.trial_row(dev, manifest, "EV-01a-t1")
    check("G5  a DEV trial row records not-applicable and the literal `none`",
          drow.get("pre_transit_scan") == containment.NOT_APPLICABLE_SCAN
          and drow.get("roster_collision_check") == containment.NOT_APPLICABLE_ROSTER
          and drow.get("registry_digest") == "none", str(drow))

    # The abort path, end to end, with the repository ledger redirected into the scratch tree —
    # a self-test never writes to evals/results/.
    real_log = run_eval.RESULTS_LOG
    run_eval.RESULTS_LOG = ledger
    try:
        rc = run_eval.abort_run(care, containment.ContainmentAbort(
            "pre-transit firewall scan found registry token(s) — content withheld",
            ["EV-01a-t1:patients/evalperson-a/profile.md:4 (identity class)"]))
    finally:
        run_eval.RESULTS_LOG = real_log
    check("G6  an abort returns a distinct non-zero status", rc == 3, str(rc))
    lines = ledger.read_text(encoding="utf-8").splitlines()
    check("G7  the abort writes exactly one ledger row", len(lines) == 1, "%d rows" % len(lines))
    arow = json.loads(lines[0]) if lines else {}
    check("G8  the row is kind=run, verdict=aborted",
          arow.get("kind") == "run" and arow.get("verdict") == "aborted", str(arow.get("verdict")))
    check("G9  the row carries the locators and no token text",
          arow.get("locators") and FAKE_IDENTITY not in json.dumps(arow), str(arow.get("locators")))
    check("G10 the row is dated, so regrade can still read the run",
          arow.get("run_date") == "2026-09-06", str(arow.get("run_date")))
    check("G14 the row names the registry route, so a rehearsal is not mistaken for a real find",
          arow.get("registry_route") == "test", str(arow.get("registry_route")))

    # regrade tolerates rows with and without the dispositions, and an abort-only log.
    (run_root / "log.jsonl").write_text(
        json.dumps({"kind": "run", "verdict": "aborted", "run_date": "2026-09-06"}) + "\n"
        + json.dumps({"trial_id": "EV-01a-t1", "run_date": "2026-09-06", "verdict": "pass"}) + "\n",
        encoding="utf-8")
    got = _or_crashed(lambda: list(regrade.regrade_run(run_root)))
    check("G11 regrade reads a log whose first row is an abort", got == [], str(got))
    (run_root / "log.jsonl").write_text("not json at all\n", encoding="utf-8")
    got = _or_crashed(lambda: list(regrade.regrade_run(run_root)))
    check("G12 regrade survives an unparseable log row", got == [], str(got))
    # ... and refuses to call an empty regrade a green (the guards' fail-closed rule).
    import contextlib
    import io
    buf = io.StringIO()

    def _regrade_main():
        with contextlib.redirect_stdout(buf):
            return regrade.main([str(run_root)])

    rc = _or_crashed(_regrade_main)
    check("G13 regrade over an aborted run is loud, not green",
          rc == 2 and "NOTHING TO REGRADE" in buf.getvalue(), "rc=%s" % rc)


def _shift_ctx(tmp, name, registry_text, today):
    """A minimal run ctx for the fixture-date cases: a real Registry over a synthetic file, a run
    root under the scratch tree, and the handful of attributes `prepare_trial`/`run_trial` read."""
    import datetime
    import types

    from evals.harness import run_eval

    reg_path = tmp / ("%s-registry.sh" % name)
    reg_path.write_text(registry_text, encoding="utf-8")
    reg = containment.Registry(reg_path, "test", fake_private(tmp / ("%s-private.sh" % name)))
    run_root = tmp / name / "run"
    for sub in ("fixtures", "pre", "transcripts"):
        paths.ensure_dir(run_root / sub)
    return types.SimpleNamespace(
        today=today if isinstance(today, datetime.date) else datetime.date.fromisoformat(today),
        run_root=run_root, keystone=b"keystone bytes\n", addendum=b"addendum bytes\n",
        stack_rev="worktree", stack_hashes={"canonical-update": "deadbeef"},
        keystone_blob="0" * 40, addendum_blob="1" * 40, config_dir=None, model=None,
        containment=containment.Containment(reg, "test", containment.CLEAN,
                                            containment.CLEAN, True))


#: The offsets the stub builder plants. Real grammar, real expander, three files' worth of dates in
#: one file — enough for the ledger-row cases, far cheaper than a real tree. `case_fixture_dates`
#: exercises the REAL builder, so the stub can never drift into testing itself.
_STUB_BODY = ("# profile\n"
              "Drug X (long-course) — taking daily (caregiver report {{TODAY-2m}}, grade B).\n"
              "Last reviewed: {{TODAY-1w}}.\n"
              "Analysis note filed {{TODAY-3d}}.\n")


def _stub_builder(planted=None):
    """A `build_fixture_tree` stand-in: one profile file of dated lines, optionally with a token."""
    from evals.harness import fixture

    def build(dest, manifest, keystone, addendum, today, trial_id):
        body = _STUB_BODY + (("contact: %s\n" % planted) if planted else "")
        target = Path(dest) / "patients" / "evalperson-a" / "profile.md"
        paths.ensure_dir(target.parent)
        target.write_text(fixture.instantiate_placeholders(body, today), encoding="utf-8")
        return {"task": "Please review the profile.", "ownership_steps": []}
    return build


def _iso_dates_in(tree):
    """Every bare YYYY-MM-DD in a built tree, as dates. Text files only — an image source is bytes."""
    import datetime

    found = set()
    for path in sorted(Path(tree).rglob("*")):
        if not path.is_file() or path.suffix in (".jpg", ".jpeg", ".png"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for hit in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
            try:
                found.add(datetime.date(int(hit[0]), int(hit[1]), int(hit[2])))
            except ValueError:
                continue
    return found


def case_fixture_dates(tmp):
    """Fixtures build at the run date: a date meeting the case-reference class no longer stops a run
    (the fixture back-shift retired with the narrowed scan, 2026-09-28), and no planted date lands
    within three days of the run date."""
    import datetime

    from evals.harness import fixture, run_eval

    # A FIXED, far-future run date, not the real clock: deterministic whatever day this runs, and a
    # date computed from it can never coincide with a real case date.
    day = FIXED_RUN_DATE
    tid = "EV-01a-t1"
    manifest = run_eval.manifest_for("EV-01a", today=day)

    # The date the run date's `{{TODAY-2m}}` lands on — the collision the retired retry stepped around.
    collide = fixture.instantiate_placeholders("{{TODAY-2m}}", day)
    one_date = FAKE_REGISTRY.replace("PII_CASEREF='%s'" % FAKE_CASEREF,
                                     "PII_CASEREF='%s|%s'" % (FAKE_CASEREF, collide))
    ctx = _shift_ctx(tmp, "d-real", one_date, day)
    real_dir = ctx.run_root / "fixtures" / "real"
    build = _or_crashed(lambda: run_eval.build_fixture_tree(real_dir, manifest, ctx.keystone,
                                                            ctx.addendum, day, tid))
    task = run_eval.resolve_task(build, manifest, day) if build is not _CRASHED else "task"
    check("D1  the REAL ev01 builder plants the date the case-reference class carries",
          build is not _CRASHED and collide in {d.isoformat() for d in _iso_dates_in(real_dir)},
          "the collision under test is not in the tree, so D2 would prove nothing")
    survives("D2  ... and the run is no longer stopped by it",
             lambda: ctx.containment.scan_trial(tid, real_dir, task))
    # NEGATIVE CONTROL for D2: the same tree carrying the private-mode identifier still aborts.
    (real_dir / "patients" / "evalperson-a" / "planted.md").write_text(
        "contact: %s\n" % FAKE_PRIVATE, encoding="utf-8")
    aborts("D3  ... while the private-mode identifier in the same tree still aborts",
           lambda: ctx.containment.scan_trial(tid, real_dir, task),
           wanted_substring="content withheld", want_locator="(private-mode-id class)")
    (real_dir / "patients" / "evalperson-a" / "planted.md").unlink()

    # D4/D5: the two dates a manifest has to keep apart, on ONE manifest that carries both. Still
    # live: `regrade` re-judges runs from before 2026-09-28 whose fixture base the retry shifted.
    # EV-05b's oracles name a planted lab date (`{{TODAY-2w}}`) AND the bare `{{TODAY}}` the agent
    # is expected to stamp. The first must move with the fixture base; the second must not.
    one = datetime.timedelta(days=1)
    m_b0 = run_eval.manifest_for("EV-05b", today=day)
    m_b1 = run_eval.manifest_for("EV-05b", today=day, fixture_date=day - one)
    j0 = json.dumps(m_b0, ensure_ascii=False)
    j1 = json.dumps(m_b1, ensure_ascii=False)
    lab0 = fixture.instantiate_placeholders("{{TODAY-2w}}", day)
    lab1 = fixture.instantiate_placeholders("{{TODAY-2w}}", day - one)
    check("D4  a shifted manifest re-instantiates its offsets against the shifted base",
          j0 != j1 and lab0 in j0 and lab1 in j1,
          "planted-date oracles did not move with the base")
    # NEGATIVE CONTROL for D4: the bare {{TODAY}} alternation stays on the REAL run date — it is
    # about what the agent writes when it stamps today, not about what was planted.
    check("D5  the bare-today alternation still names the real run date",
          day.isoformat() in j1 and (day + one).isoformat() in j1,
          "the alternation moved with the fixture base")

    # D6: the invariant, executed on the real tree. No planted date may fall in the three days the
    # margin protects — [run date - 2 .. run date] — or the moving-date guard could red on the
    # closing check.
    window = {day - datetime.timedelta(days=k) for k in range(3)}
    inside = sorted(str(d) for d in _iso_dates_in(real_dir) & window)
    check("D6  no planted date lands within three days of the run date",
          build is not _CRASHED and not inside, "planted %s" % ", ".join(inside))
    # NEGATIVE CONTROL for D6: a tree that does carry today's date must be caught, or D6 would be
    # an assertion over an empty set.
    (real_dir / "patients" / "evalperson-a" / "leak.md").write_text(
        "stamped %s\n" % day.isoformat(), encoding="utf-8")
    check("D7  ... and the same check catches a tree that does",
          bool(_iso_dates_in(real_dir) & window), "the window check found nothing")


def case_fixture_date_rows(tmp):
    """The ledger says which day the fixture was built from: the run date, with shift 0, even when
    a planted date meets the case-reference class (the retired fixture retry would have shifted)."""
    from evals.harness import fixture, run_eval

    day = FIXED_RUN_DATE
    tid = "EV-01a-t1"
    manifest = run_eval.manifest_for("EV-01a", today=day)
    collide = fixture.instantiate_placeholders("{{TODAY-2m}}", day)
    one_date = FAKE_REGISTRY.replace("PII_CASEREF='%s'" % FAKE_CASEREF,
                                     "PII_CASEREF='%s|%s'" % (FAKE_CASEREF, collide))

    # A trial that never gets as far as a build still carries an honest default.
    plain = _shift_ctx(tmp, "row-plain", FAKE_REGISTRY, day)
    base_row = run_eval.trial_row(plain, manifest, tid)
    check("D19 an unbuilt trial row defaults to the run date and shift 0",
          base_row.get("fixture_date") == day.isoformat()
          and base_row.get("fixture_date_shift") == 0,
          "%s / %s" % (base_row.get("fixture_date"), base_row.get("fixture_date_shift")))

    # The built path, with the two expensive steps stood down: the guard board (a real check.sh
    # run per trial) and the session itself. Everything between them is the code under test.
    ctx = _shift_ctx(tmp, "row-shift", one_date, day)
    real = (run_eval.build_fixture_tree, run_eval.guard_check, run_eval.session.run_session)
    run_eval.build_fixture_tree = _stub_builder()
    run_eval.guard_check = lambda d: (0, "OK: all guards green\n")
    run_eval.session.run_session = lambda *a, **k: {
        "config_problems": ["stubbed: a self-test never runs a session"]}
    try:
        row = _or_crashed(lambda: run_eval.run_trial(ctx, manifest, tid))
    finally:
        (run_eval.build_fixture_tree, run_eval.guard_check, run_eval.session.run_session) = real
    check("D20 the trial row records the run date and shift 0, collision or not",
          row is not _CRASHED and row.get("fixture_date") == day.isoformat()
          and row.get("fixture_date_shift") == 0,
          str(row if row is _CRASHED else (row.get("fixture_date"), row.get("fixture_date_shift"))))
    check("D21 ... and the trial got past the scan to the (stubbed) session",
          row is not _CRASHED and "stubbed" in str(row.get("note")),
          str(row if row is _CRASHED else row.get("note")))
    check("D22 and the row still carries no token text",
          row is not _CRASHED and collide not in json.dumps(row)
          and FAKE_CASEREF not in json.dumps(row), "row leaked a class value")

    # D23: the pre-transit scan inside run_trial itself. A tree carrying the private-mode identifier
    # aborts before the session is called; D21 is the clean twin that reaches it. Without this pair,
    # deleting the scan from prepare_trial left every case here green (test-suite review 2026-11-01).
    sessions = []
    run_eval.build_fixture_tree = _stub_builder(planted=FAKE_PRIVATE)
    run_eval.guard_check = lambda d: (0, "OK: all guards green\n")
    run_eval.session.run_session = lambda *a, **k: sessions.append(a) or {}
    try:
        aborts("D23 a trial whose tree carries the private-mode identifier aborts in run_trial",
               lambda: run_eval.run_trial(_shift_ctx(tmp, "row-planted", FAKE_REGISTRY, day),
                                          manifest, tid),
               wanted_substring="content withheld", want_locator="(private-mode-id class)")
    finally:
        (run_eval.build_fixture_tree, run_eval.guard_check, run_eval.session.run_session) = real
    check("D24 ... and the session is never called", not sessions, "session called %d time(s)" % len(sessions))


def case_regrade_reads_the_fixture_date(tmp):
    """A regrade of a shifted run must re-instantiate the oracles against the day the tree was
    built from, not the run date — otherwise every planted-date assertion misses by the shift."""
    from evals.harness import grader, regrade, run_eval

    day = FIXED_RUN_DATE
    shifted = day - datetime.timedelta(days=1)

    def mk_run(name, rows):
        root = tmp / name
        for sub in ("fixtures/EV-01a/EV-01a-t1", "pre/EV-01a/EV-01a-t1", "transcripts"):
            paths.ensure_dir(root / sub)
        (root / "transcripts" / "EV-01a-t1.jsonl").write_text("", encoding="utf-8")
        (root / "log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows),
                                        encoding="utf-8")
        return root

    row = {"trial_id": "EV-01a-t1", "variant": "EV-01a", "run_date": day.isoformat(),
           "verdict": "pass", "fixture_date": shifted.isoformat(), "fixture_date_shift": 1}
    root = mk_run("rg-shift", [row])
    check("D25 the run log yields the day each trial's fixture was built from",
          regrade.fixture_dates(root, day) == {"EV-01a-t1": shifted},
          str(regrade.fixture_dates(root, day)))
    # NEGATIVE CONTROL for D25: a pre-2026-09-07 row carries no such field and must stay on the
    # run date rather than invent one.
    old = dict(row)
    old.pop("fixture_date")
    old.pop("fixture_date_shift")
    old_root = mk_run("rg-old", [old])
    check("D26 ... and an older row without the field falls back to the run date",
          regrade.fixture_dates(old_root, day) == {}, str(regrade.fixture_dates(old_root, day)))
    # The last row for a trial id wins — the same identity rule the ledger is read under.
    later = dict(row, fixture_date=(day - datetime.timedelta(days=3)).isoformat(), kind="regrade")
    both = mk_run("rg-last", [row, later])
    check("D27 the LAST row for a trial id decides",
          regrade.fixture_dates(both, day) == {"EV-01a-t1": day - datetime.timedelta(days=3)},
          str(regrade.fixture_dates(both, day)))

    # End to end: regrade_run must ask manifest_for for the shifted base while keeping the REAL run
    # date for the run-month boundary.
    seen = []
    real_mf, real_grade = run_eval.manifest_for, grader.grade
    run_eval.manifest_for = lambda v, today=None, fixture_date=None: (
        seen.append((v, today, fixture_date)) or {"id": v, "assertions": []})
    grader.grade = lambda *a, **k: "graded"
    try:
        out = _or_crashed(lambda: list(regrade.regrade_run(root)))
    finally:
        run_eval.manifest_for, grader.grade = real_mf, real_grade
    check("D28 regrade resolves the manifest at the shifted fixture base",
          out is not _CRASHED and seen == [("EV-01a", day, shifted)], str(seen))
    # NEGATIVE CONTROL for D28: the unshifted run asks for the run date, so D28 is not just
    # "whatever was in the log".
    seen2 = []
    run_eval.manifest_for = lambda v, today=None, fixture_date=None: (
        seen2.append((v, today, fixture_date)) or {"id": v, "assertions": []})
    grader.grade = lambda *a, **k: "graded"
    try:
        _or_crashed(lambda: list(regrade.regrade_run(old_root)))
    finally:
        run_eval.manifest_for, grader.grade = real_mf, real_grade
    check("D29 ... and at the run date when the run never shifted",
          seen2 == [("EV-01a", day, day)], str(seen2))


def case_canary_probe_verdict(tmp):
    """The canary probe is proven only by a permission-layer refusal in each direction."""
    from evals.harness import session

    def fake_session(calls, create_write_canary=False, absolute=False):
        """A stand-in for `run_session`: the tool calls a session made, each refused or not by the
        permission layer. Nothing reaches the CLI."""
        def run(fixture_root, transcript_path, **_kwargs):
            outside = Path(fixture_root).parent
            if create_write_canary:
                (outside / "canary-write.txt").write_text("BREACH\n", encoding="utf-8")
            events, denials = [{"type": "system", "subtype": "init", "cwd": str(fixture_root)}], []
            for n, (name, target, denied) in enumerate(calls):
                use_id = "toolu_%02d" % n
                if target == "ABS":
                    target = str(outside / "canary-write.txt")
                elif absolute:                   # as the CLI reports them
                    target = os.path.abspath(os.path.join(str(fixture_root), target))
                tool_input = {"file_path": target}
                events.append({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": use_id, "name": name, "input": tool_input}]}})
                events.append({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": use_id, "is_error": True,
                     "content": "refused"}]}})
                if denied:
                    denials.append({"tool_name": name, "tool_use_id": use_id,
                                    "tool_input": tool_input})
            Path(transcript_path).write_text("".join(json.dumps(e) + "\n" for e in events),
                                             encoding="utf-8")
            return {"init": events[0], "config_problems": [], "events": events,
                    "permission_denials": denials, "transcript_path": str(transcript_path),
                    "final_message": "", "resolved_model": "fake"}
        return run

    def probe(label, calls, want, scratch=None, **kw):
        real = session.run_session
        session.run_session = fake_session(calls, **kw)
        try:
            got = _or_crashed(lambda: session.containment_selftest(scratch or tmp / label.split()[0],
                                                                   tmp / "cfg"))
        finally:
            session.run_session = real
        if got is _CRASHED:
            return check(label, False, "the probe raised")
        return check(label, got["proven"] is want,
                     "proven %r, reasons %r" % (got["proven"], got["reasons"]))

    r, w = "../canary-read.txt", "../canary-write.txt"
    # The Codex reproduction (2026-10-28): both Reads refused, no Write at all — once "proven".
    probe("C1  two refused Reads and no Write are not proven",
          [("Read", r, True), ("Read", w, True)], False)
    probe("C2  ... a refused Read and a refused Write are proven",
          [("Read", r, True), ("Write", w, True)], True)
    # The 2026-09-02 probe transcript: the Write was stopped by the CLI's read-first check, not the
    # permission layer, so the refusal is no evidence about the boundary.
    probe("C3  a Write refused by something other than the permission layer is not proven",
          [("Read", r, True), ("Write", w, False)], False)
    probe("C4  a Read not refused by the permission layer is not proven",
          [("Read", r, False), ("Edit", w, True)], False)
    probe("C5  a refused Write of a look-alike path is not proven",
          [("Read", r, True), ("Write", "../canary-write.txt.bak", True)], False)
    probe("C6  ... and an absolute or roundabout path to the canary is the canary",
          [("Read", "../fx/../canary-read.txt", True), ("Edit", "ABS", True)], True)
    probe("C7  a file created at the write canary is a breach, whatever was refused",
          [("Read", r, True), ("Write", w, True)], False, create_write_canary=True)
    # The manual route passes TAB_EVAL_SCRATCH as given (Codex review of this PR, 2026-10-28).
    cwd = os.getcwd()
    os.chdir(str(tmp))
    try:
        probe("C8  a relative scratch folder still matches the CLI's absolute paths",
              [("Read", r, True), ("Write", w, True)], True, scratch=Path("C8"), absolute=True)
    finally:
        os.chdir(cwd)
    # The probe clears its folder first; a symlink there must stop it, not have its target removed.
    elsewhere = tmp / "C9-elsewhere"
    paths.ensure_dir(elsewhere)
    (elsewhere / "keep.txt").write_text("not the probe's\n", encoding="utf-8")
    paths.ensure_dir(tmp / "C9")
    os.symlink(str(elsewhere), str(tmp / "C9" / "containment"))
    real = session.run_session
    session.run_session = fake_session([("Read", r, True), ("Write", w, True)])
    try:
        got = _or_crashed(lambda: session.containment_selftest(tmp / "C9", tmp / "cfg"))
    finally:
        session.run_session = real
    check("C9  a symlinked probe folder stops the probe ...", got is _CRASHED or not got["proven"])
    check("C9b ... and what it points at survives", (elsewhere / "keep.txt").is_file())


def case_throwaway_run_roots(tmp):
    """Run roots: the free checks (controls, stress controls, dry runs) remove theirs, unless --keep."""
    from evals.harness import compare, compare_controls, controls, run_eval, stress, stress_controls

    scratch = tmp / "throwaway-scratch"
    left = lambda: sorted(p.name for p in scratch.iterdir()) if scratch.exists() else []
    seen = []

    def crash_in(root):
        seen.append(root.is_dir())
        raise RuntimeError("planted crash inside the run")

    real_env = os.environ.get("TAB_EVAL_SCRATCH")
    os.environ["TAB_EVAL_SCRATCH"] = str(scratch)
    real_rc, real_rf = controls.run_controls, stress_controls.run_families
    real_runs = compare.run, stress.run, run_eval.run_suite
    real_so = stress.so.load, stress.so.pick
    real_make_root, real_preflight = run_eval.make_run_root, containment.preflight
    real_build = run_eval.build_fixture_tree
    real_variants, real_cases = compare_controls.co.FULL_VARIANTS, compare_controls.cases
    controls.run_controls = lambda _controls, _today, root: crash_in(root)
    stress_controls.run_families = lambda _data, _today, root, _verbose: crash_in(root)
    # The comparison controls build their first tree at <root>/base/<variant>, inside the root.
    run_eval.build_fixture_tree = lambda dest, *_a: crash_in(dest.parent.parent)

    def comparison_controls(argv):
        with contextlib.redirect_stdout(io.StringIO()):     # its forty-odd offline checks
            return compare_controls.main(argv)

    controls_mains = (("controls", controls.main), ("stress controls", stress_controls.main),
                      ("comparison controls", comparison_controls))
    try:
        for name, main in controls_mains:
            del seen[:]
            out = _or_crashed(lambda: main([]))
            check("D30 %s: a run that crashes leaves no run root behind" % name,
                  out is _CRASHED and left() == [], "left %s" % left())
            # NEGATIVE CONTROL for D30: the root existed while the run ran, so "nothing left" is
            # the cleanup's doing, not a run that never made one.
            check("D31 ... and the root was there while it ran", seen == [True], str(seen))
            _or_crashed(lambda: main(["--keep"]))
            kept = left()
            check("D32 %s --keep leaves the run root for debugging" % name, len(kept) == 1, str(kept))
            for folder in kept:
                shutil.rmtree(scratch / folder, ignore_errors=True)
        with run_eval.throwaway_run_root("test") as root:
            inside = root.is_dir()
        check("D33 a run that returns removes its root too", inside and not root.exists(), str(root))

        # D30 crashes each runner; a runner that returns must clean up as well, not only a crash.
        returns = lambda root: seen.append(root.is_dir()) or 0  # noqa: E731
        controls.run_controls = lambda _controls, _today, root: returns(root)
        stress_controls.run_families = lambda _data, _today, root, _verbose: returns(root)
        # One variant's tree, planted empty, and no cases: the comparison controls report a red and
        # return, which is all this needs.
        run_eval.build_fixture_tree = lambda dest, *_a: returns(dest.parent.parent)
        compare_controls.co.FULL_VARIANTS = real_variants[:1]
        compare_controls.cases = lambda: []
        for name, main in controls_mains:
            del seen[:]
            out = _or_crashed(lambda: main([]))
            check("D67 %s: a run that returns leaves no run root behind" % name,
                  out is not _CRASHED and seen == [True] and left() == [],
                  "returned %s, ran %s, left %s" % ("a crash" if out is _CRASHED else out, seen, left()))
        run_eval.build_fixture_tree = real_build
        compare_controls.co.FULL_VARIANTS, compare_controls.cases = real_variants, real_cases

        # The dry runs take the same throwaway root; the root is the last argument they get.
        handed = []
        dry = lambda *a: handed.append(len(a)) or crash_in(a[-1])  # noqa: E731
        compare.run, stress.run, run_eval.run_suite = dry, dry, dry
        stress.so.load, stress.so.pick = (lambda *a: {}), (lambda *a: [])
        for name, main in (("eval", run_eval.main), ("comparison", compare.main),
                           ("stress test", stress.main)):
            del seen[:]
            out = _or_crashed(lambda: main(["--dry-run"]))
            check("D34 the %s dry run: a crash leaves no run root behind" % name,
                  out is _CRASHED and left() == [], "left %s" % left())
            # NEGATIVE CONTROL for D34, as D31 is for D30.
            check("D35 ... and the root was there while it ran", seen == [True], str(seen))
            _or_crashed(lambda: main(["--dry-run", "--keep"]))
            kept = left()
            check("D36 the %s dry run --keep leaves the run root" % name, len(kept) == 1, str(kept))
            for folder in kept:
                shutil.rmtree(scratch / folder, ignore_errors=True)
        dry_returns = lambda *a: returns(a[-1])  # noqa: E731
        compare.run, stress.run, run_eval.run_suite = dry_returns, dry_returns, dry_returns
        for name, main in (("eval", run_eval.main), ("comparison", compare.main),
                           ("stress test", stress.main)):
            del seen[:]
            out = _or_crashed(lambda: main(["--dry-run"]))
            check("D68 the %s dry run: a run that returns leaves no run root behind" % name,
                  out is not _CRASHED and seen == [True] and left() == [],
                  "returned %s, ran %s, left %s" % ("a crash" if out is _CRASHED else out, seen, left()))
        # A run that spends keeps its evidence: it is handed a durable root, never a throwaway one.
        # Nothing runs here, so that root holds no file and the archive step removes it unarchived.
        del handed[:]
        kinds = []
        real_make = run_eval.make_run_root
        run_eval.make_run_root = lambda durable=False: kinds.append(durable) or real_make(durable)
        record = lambda *a: handed.append(len(a))  # noqa: E731
        compare.run, stress.run, run_eval.run_suite = record, record, record
        try:
            for main in (run_eval.main, compare.main, stress.main):
                main([])
        finally:
            run_eval.make_run_root = real_make
        check("D37 a run that spends gets a durable root, not a throwaway one",
              handed == [4, 4, 5] and kinds == [True] * 3 and left() == [],
              "%s, durable %s, left %s" % (handed, kinds, left()))

        # D34-D37 replace the runner itself, so a runner that ignored the root it was handed and
        # made its own would pass them. These run the real context builders up to a planted crash
        # once the root is in hand, counting every root made (Codex review, 2026-10-26).
        compare.run, stress.run, run_eval.run_suite = real_runs
        made = []

        def counting(durable=False):
            made.append(durable)
            return real_make_root(durable=durable)

        def stop(*_a, **_k):
            raise RuntimeError("planted crash once the run root is in hand")

        run_eval.make_run_root, containment.preflight = counting, stop
        for name, main in (("eval", run_eval.main), ("comparison", compare.main),
                           ("stress test", stress.main)):
            del made[:]
            _or_crashed(lambda: main(["--dry-run"]))
            check("D59 the %s dry run makes one root, the throwaway, and leaves none" % name,
                  made == [False] and left() == [], "made %s, left %s" % (made, left()))
            del made[:]
            _or_crashed(lambda: main([]))
            check("D60 the %s run that spends makes one root, a durable one" % name,
                  made == [True], str(made))
            for folder in left():
                shutil.rmtree(scratch / folder, ignore_errors=True)
    finally:
        controls.run_controls, stress_controls.run_families = real_rc, real_rf
        run_eval.build_fixture_tree = real_build
        compare_controls.co.FULL_VARIANTS, compare_controls.cases = real_variants, real_cases
        compare.run, stress.run, run_eval.run_suite = real_runs
        stress.so.load, stress.so.pick = real_so
        run_eval.make_run_root, containment.preflight = real_make_root, real_preflight
        if real_env is None:
            os.environ.pop("TAB_EVAL_SCRATCH", None)
        else:
            os.environ["TAB_EVAL_SCRATCH"] = real_env



#: The child for `case_stop_signals`: the real entry point's `main`, its runner replaced by one that
#: sends this process a real signal from inside the run root. argv: repo, entry, argv as JSON,
#: signal name, "1" for the shipped cleanup or "0" for it taken out (the negative control), and
#: when it lands: "run" (mid-run), "twice" (mid-run and again in the run's own `finally`), "cleanup"
#: (the run returns; the only signal lands as the cleanup starts), "making" (while the root's
#: folders are being made), or "boundary" / "boundary-crash" (the run returns or crashes, and the
#: only signal lands as the cleanup begins, before its hold takes effect).
_STOP_CHILD = r"""
import contextlib, json, os, shutil, signal, sys, time
sys.path.insert(0, sys.argv[1])
from evals.harness import compare, compare_controls, controls, paths, run_eval, stress, stress_controls
entry, argv, signame, shipped = sys.argv[2], json.loads(sys.argv[3]), sys.argv[4], sys.argv[5] == "1"
for sig in (signal.SIGTERM, signal.SIGHUP):     # as from a terminal, whatever the parent inherited
    signal.signal(sig, signal.SIG_DFL)
signal.signal(signal.SIGINT, signal.default_int_handler)
if not shipped:                         # the same (hold, release), doing nothing
    run_eval.unwind_on_stop_signals = lambda: contextlib.nullcontext((lambda *_: None, lambda: None))
when = sys.argv[6]


def signalled_first(real):             # `real`, its first call preceded by the signal; a signal
    sent = []                           # that does not wait lands in the sleep

    def call(*a, **k):
        if not sent:
            sent.append(os.kill(os.getpid(), getattr(signal, signame)))
            time.sleep(0.5)
        return real(*a, **k)
    return call


if when == "cleanup":
    shutil.rmtree = signalled_first(shutil.rmtree)
if when == "making":
    paths.ensure_dir = signalled_first(paths.ensure_dir)
if when.startswith("boundary"):
    real_unwind = run_eval.unwind_on_stop_signals

    @contextlib.contextmanager
    def late_stop_unwind():
        with real_unwind() as (hold, release):
            holds = []

            def hold_after_a_stop(*a):
                holds.append(a)
                if len(holds) == 2:             # the cleanup's: the signal lands just before it
                    os.kill(os.getpid(), getattr(signal, signame))
                    time.sleep(0.5)
                return hold(*a)
            yield hold_after_a_stop, release
    run_eval.unwind_on_stop_signals = late_stop_unwind

def stop(*_a, **_k):
    if when in ("cleanup", "making", "boundary"):
        return 0
    if when == "boundary-crash":
        raise RuntimeError("planted crash inside the run")
    try:
        os.kill(os.getpid(), getattr(signal, signame))
        time.sleep(60)                  # the signal lands here
        raise SystemExit("the signal never arrived")
    finally:
        if when == "twice":             # a repeat that is not ignored lands in this sleep
            os.kill(os.getpid(), getattr(signal, signame))
            time.sleep(0.5)
            print("the run's own cleanup finished")

controls.run_controls = stress_controls.run_families = stop
compare.run = stress.run = run_eval.run_suite = stop
run_eval.build_fixture_tree = stop      # the comparison controls' first step inside the root
stress.so.load, stress.so.pick = (lambda *a: {}), (lambda *a: [])
sys.exit({"controls": controls.main, "stress controls": stress_controls.main,
          "comparison controls": compare_controls.main, "eval dry run": run_eval.main,
          "comparison dry run": compare.main, "stress test dry run": stress.main}[entry](argv))
"""


def case_stop_signals(tmp):
    """Run roots: a kill (SIGTERM, SIGHUP) or Ctrl-C, even mid-removal, still removes the root."""
    from evals.harness import run_eval

    scratch = tmp / "stop-scratch"
    left = lambda: sorted(p.name for p in scratch.iterdir()) if scratch.exists() else []  # noqa: E731
    env = dict(os.environ, TAB_EVAL_SCRATCH=str(scratch))

    def killed(entry, argv, signame="SIGTERM", shipped=True, when="run"):
        """Run `entry` in a child that signals itself inside the run; (exit status, roots printed)."""
        out = subprocess.run([sys.executable, "-u", "-c", _STOP_CHILD, str(REPO_ROOT), entry,
                              json.dumps(argv), signame, "1" if shipped else "0", when],
                             env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        text = out.stdout.decode("utf-8", "replace")
        return out.returncode, re.findall(r"run root: (\S+)", text), text

    def clear():
        for folder in left():
            shutil.rmtree(scratch / folder, ignore_errors=True)

    term = 128 + signal.SIGTERM
    entries = (("controls", []), ("stress controls", []), ("comparison controls", []),
               ("eval dry run", ["--dry-run"]), ("comparison dry run", ["--dry-run"]),
               ("stress test dry run", ["--dry-run"]))
    for entry, argv in entries:
        code, roots, text = killed(entry, argv)
        check("D69 %s: SIGTERM mid-run leaves no run root behind" % entry,
              code == term and len(roots) == 1 and left() == [] and "run root removed" in text,
              "exit %s, printed %s, left %s: %s" % (code, roots, left(), text[-300:]))
        clear()
        code, roots, text = killed(entry, argv + ["--keep"])
        check("D70 %s --keep: SIGTERM keeps the run root and prints where" % entry,
              code == term and len(left()) == 1 and len(roots) == 1
              and ("kept (--keep): %s" % roots[0]) in text,
              "exit %s, printed %s, left %s" % (code, roots, left()))
        clear()
    code, roots, text = killed("controls", [], signame="SIGHUP")
    check("D71 controls: a hangup (closed terminal) leaves no run root behind",
          code == 128 + signal.SIGHUP and len(roots) == 1 and left() == [],
          "exit %s, printed %s, left %s" % (code, roots, left()))
    clear()
    code, roots, text = killed("controls", [], when="twice")
    check("D75 controls: a second SIGTERM while the run unwinds cuts neither its own cleanup "
          "nor the root's short", code == term and left() == []
          and "the run's own cleanup finished" in text, "exit %s, left %s: %s" % (code, left(), text[-300:]))
    clear()
    code, roots, text = killed("controls", [], when="cleanup")
    check("D76 controls: a run that returned and is SIGTERMed as its cleanup starts finishes the "
          "cleanup, then stops", code == term and len(roots) == 1 and left() == [],
          "exit %s, printed %s, left %s" % (code, roots, left()))
    clear()
    code, roots, text = killed("controls", [], when="making")
    check("D77 controls: a SIGTERM while the run root is being made stops the run before it "
          "starts and leaves no root", code == term and len(roots) == 1 and left() == []
          and "run root removed" in text,
          "exit %s, printed %s, left %s: %s" % (code, roots, left(), text[-300:]))
    clear()
    code, roots, text = killed("controls", [], when="boundary")
    check("D80 controls: a SIGTERM that beats the cleanup's hold still lets the cleanup run, then "
          "stops the run", code == term and len(roots) == 1 and left() == [],
          "exit %s, printed %s, left %s: %s" % (code, roots, left(), text[-300:]))
    clear()
    code, roots, text = killed("controls", [], when="boundary-crash")
    check("D80 ... and after a crash too, the crash's own exit kept",
          code == 1 and "planted crash inside the run" in text and len(roots) == 1 and left() == [],
          "exit %s, printed %s, left %s: %s" % (code, roots, left(), text[-300:]))
    clear()
    # Ctrl-C always unwound; a second one, or one landing while the root is made or removed, cut
    # that short. An unhandled KeyboardInterrupt ends the process by SIGINT, as Python always does.
    for when, what in (("twice", "a second Ctrl-C while the run unwinds"),
                       ("cleanup", "Ctrl-C as a returned run's cleanup starts"),
                       ("making", "Ctrl-C while the run root is being made")):
        code, roots, text = killed("controls", [], signame="SIGINT", when=when)
        check("D78 controls: %s leaves no run root behind" % what,
              code == -signal.SIGINT and left() == []
              and (when != "twice" or "the run's own cleanup finished" in text),
              "exit %s, left %s: %s" % (code, left(), text[-300:]))
        clear()
    # NEGATIVE CONTROL for D69/D71: the same kill with the signal handling taken out ends the
    # process at the default, skipping every `finally`, and the root stays. So D69 passes on the
    # cleanup's doing, and a real signal reached the child.
    code, roots, text = killed("controls", [], shipped=False)
    check("D72 ... and without the signal handling the same kill leaves the root",
          code == -signal.SIGTERM and len(roots) == 1 and len(left()) == 1,
          "exit %s, printed %s, left %s" % (code, roots, left()))
    clear()

    # A signal someone already ignores (`nohup`) or handles is theirs: it is not taken over.
    before = {sig: signal.getsignal(sig) for sig in run_eval.UNWIND_SIGNALS}
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    watched = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    try:
        with run_eval.unwind_on_stop_signals():
            inside = tuple(signal.getsignal(sig) for sig in watched)
        after = tuple(signal.getsignal(sig) for sig in watched)
    finally:
        for sig, handler in before.items():
            signal.signal(sig, handler)
    check("D73 an ignored hangup (nohup) stays ignored; SIGTERM and Ctrl-C are taken over, then "
          "handed back", inside[0] is signal.SIG_IGN and callable(inside[1])
          and inside[2] not in (signal.default_int_handler, signal.SIG_IGN, signal.SIG_DFL)
          and after == (signal.SIG_IGN, signal.SIG_DFL, signal.default_int_handler),
          "inside %s, after %s" % (inside, after))

    # A root that fails while its folders are being made (a full disk, say) is not left half made.
    real_ensure, calls = paths.ensure_dir, []

    def full_disk(path):
        calls.append(path)
        if len(calls) == 2:
            raise OSError(28, "planted: no space left on device")
        return real_ensure(path)

    os.environ["TAB_EVAL_SCRATCH"], saved_env = str(scratch), os.environ.get("TAB_EVAL_SCRATCH")
    paths.ensure_dir = full_disk
    try:
        out = _or_crashed(lambda: run_eval.throwaway_run_root("test").__enter__())
    finally:
        paths.ensure_dir = real_ensure
        if saved_env is None:
            os.environ.pop("TAB_EVAL_SCRATCH", None)
        else:
            os.environ["TAB_EVAL_SCRATCH"] = saved_env
    check("D79 a run root that fails half made is removed, not left", out is _CRASHED
          and len(calls) == 2 and left() == [], "calls %d, left %s" % (len(calls), left()))
    clear()

    # A root that cannot be fully removed says so instead of printing "removed".
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("SKIP  D74 (running as root: a read-only folder does not stop the removal)")
        return
    err, out = io.StringIO(), io.StringIO()
    os.environ["TAB_EVAL_SCRATCH"], real_env = str(scratch), os.environ.get("TAB_EVAL_SCRATCH")
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            with run_eval.throwaway_run_root("test") as root:
                locked = root / "locked"
                locked.mkdir()
                (locked / "file").write_text("x")
                locked.chmod(0o500)
        check("D74 a root that could not be removed says so, and never claims it was",
              root.exists() and "could not be fully removed: %s" % root in err.getvalue()
              and "removed: %s" % root not in out.getvalue(), err.getvalue() + out.getvalue())
    finally:
        if real_env is None:
            os.environ.pop("TAB_EVAL_SCRATCH", None)
        else:
            os.environ["TAB_EVAL_SCRATCH"] = real_env
        for folder in scratch.glob("*/locked"):
            folder.chmod(0o700)
        clear()

#: Planted in the CLI's account and auth files of a test run root; must never reach an archive.
AUTH_MARKER = b"Qzauthmarker"
#: Planted in the one config file that IS archived, so the byte scan for AUTH_MARKER is not vacuous.
KEPT_MARKER = b"Qzkeptmarker"


def _plant_run(root):
    """A paid run's folder as it ends: trees, transcript, log, and the CLI's config folder."""
    files = {
        "config/.eval-auth-mode": b"clean\n" + KEPT_MARKER + b"\n",
        "config/.claude.json": b'{"account": "' + AUTH_MARKER + b'"}',
        "config/policy-limits.json": AUTH_MARKER,
        "config/backups/.claude.json.backup": AUTH_MARKER,
        "config/.credentials.json": AUTH_MARKER,
        "config/projects/x/session.jsonl": AUTH_MARKER,
        "fixtures/EV-01a-t1/patients/evalperson-a/profile.md": b"# evalperson-a\n" * 50,
        "pre/EV-01a-t1/profile.md": b"# before\n",
        "transcripts/EV-01a-t1.jsonl": bytes(range(256)) * 16,
        "log.jsonl": b'{"trial_id": "EV-01a-t1"}\n',
    }
    for rel, body in files.items():
        paths.ensure_dir((root / rel).parent)
        (root / rel).write_bytes(body)
    return {rel: body for rel, body in files.items() if not rel.startswith("config/") or rel == "config/.eval-auth-mode"}


def _archive_bytes(path):
    """Every member name and every file's bytes of an archive, decompressed, as one blob."""
    out = []
    with tarfile.open(str(path), "r:*") as tf:
        for m in tf:
            out.append(m.name.encode())
            if m.isfile():
                out.append(tf.extractfile(m).read())
    return b"\n".join(out)


def case_run_archive(tmp):
    """Archive: a paid run's folder goes to the Drive matched, then leaves; anything short keeps it."""
    import contextlib
    import io
    from evals.harness import archive, compare, run_eval, stress

    scratch, drive = tmp / "archive-scratch", tmp / "fake-drive"
    paths.ensure_dir(drive)
    no_cloud = tmp / "no-cloud-storage"
    left = lambda: sorted(p.name for p in scratch.iterdir()) if scratch.exists() else []  # noqa: E731
    in_drive = lambda: sorted(p.name for p in drive.iterdir())  # noqa: E731
    no_evict = lambda path: (False, "test: no File Provider")  # noqa: E731
    saved_env = {k: os.environ.get(k) for k in ("TAB_EVAL_SCRATCH", archive.DEST_ENV)}
    real = (archive.CLOUD_STORAGE, archive.evict_and_confirm, archive.write_archive, archive.archive_run,
            run_eval.run_suite, compare.run, stress.run, stress.so.load, stress.so.pick,
            archive.CONFIG_FILE, archive.RECENT)
    os.environ["TAB_EVAL_SCRATCH"] = str(scratch)
    os.environ[archive.DEST_ENV] = str(drive)
    archive.CLOUD_STORAGE = no_cloud
    archive.CONFIG_FILE = tmp / "archive-config" / "archive-dir"   # absent until a case writes it
    archive.RECENT = 0
    archive.evict_and_confirm = no_evict
    planted = {}

    def paid(name, outcome):
        """A paid runner's `run`, stubbed: plants the run's files in the root it is handed, then ends."""
        def run(*a):
            planted[name] = (a[-1], _plant_run(a[-1]))
            if outcome == "crash":
                raise RuntimeError("planted crash at the end of the run")
            return outcome
        return run

    def wipe():
        for d in (scratch, drive):
            if d.exists():
                for p in d.iterdir():
                    shutil.rmtree(p) if p.is_dir() else p.unlink()

    try:
        stress.so.load, stress.so.pick = (lambda *a: {}), (lambda *a: [])
        run_eval.run_suite, compare.run, stress.run = paid("eval", 1), paid("comparison", 0), paid("stress", "crash")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rcs = [_or_crashed(lambda: main([])) for main in (run_eval.main, compare.main, stress.main)]
        roots = {name: root for name, (root, _f) in planted.items()}
        archives = {name: archive.archive_in(drive, root.name) for name, root in roots.items()}
        check("D38 each paid runner, red, green or crashed, ends with its folder archived and gone",
              rcs[:2] == [1, 0] and rcs[2] is _CRASHED and all(archives.values())
              and not any(r.exists() for r in roots.values()) and left() == [],
              "rc %s, archives %s, left %s" % (rcs, in_drive(), left()))
        blob = _archive_bytes(archives["eval"]) if archives.get("eval") else b""
        check("D39 the CLI's account and auth files never enter the archive", blob and AUTH_MARKER not in blob,
              "the planted auth marker is in the archive")
        # NEGATIVE CONTROL for D39: the same byte scan finds the one config file that is archived.
        check("D40 ... while .eval-auth-mode is archived and the scan reads its bytes", KEPT_MARKER in blob)

        # A restore brings the run back byte for byte (and is the negative control for D38: the
        # archive holds the run, so "gone" is not "lost").
        name = roots["eval"].name
        # The scratch setting moved since the run: the restore still goes back where the run ran,
        # because the comparison and stress ledgers find its evidence by that path.
        os.environ["TAB_EVAL_SCRATCH"] = str(tmp / "scratch-moved")
        if CAN_RESTORE:
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    rc = _or_crashed(lambda: archive.restore(name, evict=no_evict))
                except SystemExit as exc:         # a refusal is a MISS here, never the suite's end
                    rc = "refused: %s" % exc
            back = {rel: (roots["eval"] / rel).read_bytes() for rel in planted["eval"][1]
                    if (roots["eval"] / rel).is_file()}
            check("D41 restore puts the run back where it ran, file for file, the scratch setting moved",
                  rc == 0 and back == planted["eval"][1] and not (roots["eval"] / "config" / ".claude.json").exists()
                  and not (tmp / "scratch-moved").exists(),
                  "rc %s, restored %d of %d files" % (rc, len(back), len(planted["eval"][1])))
            os.environ["TAB_EVAL_SCRATCH"] = str(scratch)
            before = sorted(p.name for p in roots["eval"].rglob("*"))
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    archive.restore(name, evict=no_evict)
                refused = False
            except SystemExit:
                refused = True
            except Exception as exc:              # noqa: BLE001 — failing late is not refusing
                refused = False
                print("      (raised %s: %s)" % (type(exc).__name__, exc))
            check("D42 restore refuses to write over a folder that is already there",
                  refused and sorted(p.name for p in roots["eval"].rglob("*")) == before)
        else:
            print("SKIP  D41, D42, restore's output in D58 (LOUD): restore needs Python 3.12; this is %d.%d"
                  % sys.version_info[:2])
            os.environ["TAB_EVAL_SCRATCH"] = str(scratch)
        wipe()

        # A mismatch keeps the folder: a file changed after it was packed (the archive lacks the
        # newer bytes), or the archive cannot be read back (cut short).
        def moved(root, target, fmt):
            real[2](root, target, fmt)
            with open(str(root / "log.jsonl"), "ab") as fh:
                fh.write(b'{"late": true}\n')

        def cut(root, target, fmt):
            real[2](root, target, fmt)
            with open(str(target), "r+b") as fh:
                fh.truncate(os.path.getsize(str(target)) // 2)

        for label, writer in (("a file changed after it was packed", moved), ("an archive cut short", cut)):
            root = run_eval.make_run_root(durable=True)
            _plant_run(root)
            archive.write_archive = writer
            with contextlib.redirect_stderr(io.StringIO()):
                got = archive.archive_run(root)
            archive.write_archive = real[2]
            check("D43 %s: the local folder stays and no archive is left" % label,
                  got.status == "kept" and (root / "log.jsonl").is_file() and in_drive() == [],
                  "%s, drive %s" % (got.status, in_drive()))
            wipe()

        # The setting is a folder path or `off`, nothing else: a provider's name is not a destination.
        cloud = tmp / "fake-cloud-storage"
        archive.CLOUD_STORAGE = cloud
        sync = cloud / "ExampleDrive-someone@example.org-folder"
        paths.ensure_dir(sync)
        cwd = os.getcwd()
        os.chdir(str(tmp))
        try:
            for value in ("example-drive", "icloud"):
                paths.ensure_dir(tmp / value)       # a same-named folder here must not be taken either
                os.environ[archive.DEST_ENV] = value
                root = run_eval.make_run_root(durable=True)
                _plant_run(root)
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    got = archive.archive_run(root)
                check("D44 the setting %r is not special: the run says so, keeps its folder, writes nothing" % value,
                      got.status == "kept" and root.is_dir() and "NOT archived" in err.getvalue()
                      and list(sync.iterdir()) == [] and list((tmp / value).iterdir()) == [],
                      "%s, %s" % (got.status, got.why))
                wipe()
        finally:
            os.chdir(cwd)
        os.environ[archive.DEST_ENV] = str(tmp / "unmounted" / "eval-runs")
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        with contextlib.redirect_stderr(io.StringIO()):
            got = archive.archive_run(root)
        check("D44 a named destination folder that is not there: kept, and the folder never created",
              got.status == "kept" and root.is_dir() and not (tmp / "unmounted").exists())
        wipe()
        # With nothing set, the archive lands on this disk, even beside a sync folder, and nothing is
        # evicted: no folder is ever found for the operator.
        os.environ.pop(archive.DEST_ENV)
        evicted = []
        archive.evict_and_confirm = lambda path: evicted.append(path) or (True, None)
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            got = archive.archive_run(root)
        local = scratch / archive.LOCAL_SUBDIR
        check("D45 nothing set: the archive lands on this disk, never in a sync folder, nothing evicted",
              got.status == "archived" and archive.archive_in(local, root.name) is not None
              and list(sync.iterdir()) == [] and evicted == [] and not got.evicted,
              "%s, %s, evicted %s" % (got.status, got.why, evicted))
        check("D45 ... and the run names the default and where to change it, in one line",
              "the default" in out.getvalue() and "archive-dir" in out.getvalue())
        shutil.rmtree(str(local), ignore_errors=True)
        # The local archive folder cannot be made (a file in its place): the run's folder stays and
        # the failure never escapes into the paid run's own result.
        local.write_text("not a folder\n")
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        with contextlib.redirect_stderr(io.StringIO()):
            got = _or_crashed(lambda: archive.archive_run(root))
        check("D45 an archive folder that cannot be made: kept, and nothing raised",
              got is not _CRASHED and got.status == "kept" and root.is_dir(), str(got))
        local.unlink()
        wipe()
        # NEGATIVE CONTROL for D44 and D45: any existing folder named in the config file works — here an
        # external drive's — and the eviction is asked for (it finds nothing to evict there).
        ssd = tmp / "Volumes" / "external-ssd" / "tabularium-eval-runs"
        paths.ensure_dir(ssd)
        paths.ensure_dir(archive.CONFIG_FILE.parent)
        archive.CONFIG_FILE.write_text("# where eval archives go\n%s\n" % ssd)
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        with contextlib.redirect_stdout(io.StringIO()):
            got = archive.archive_run(root)
        check("D45 ... and any existing folder named in the config file takes the archive, eviction asked",
              got.status == "archived" and archive.archive_in(ssd, root.name) is not None
              and not root.exists() and len(evicted) == 1, "%s, %s, evicted %s" % (got.status, got.why, evicted))
        # A cloud sync folder's own name carries its account: the output never prints it.
        target = sync / "tabularium" / "eval-runs"
        paths.ensure_dir(target)
        archive.CONFIG_FILE.write_text("%s\n" % target)
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            got = archive.archive_run(root, evict=lambda p: (False, "planted: not uploaded, at %s" % p))
        check("D56 a sync folder's account-bearing name never reaches the output, errors included",
              got.status == "archived" and archive.archive_in(target, root.name) is not None
              and "someone@example.org" not in out.getvalue(), out.getvalue()[-300:])
        # NEGATIVE CONTROL for D56: the output does name where the archive went, the account withheld.
        check("D57 ... while it still names the folder, with <sync folder> in the account's place",
              "<sync folder>/tabularium/eval-runs/%s" % root.name in out.getvalue())
        # Every line and refusal is withheld, whatever the name holds (a space, a quote, Polish letters),
        # with the scratch folder itself inside a sync folder: archive, restore, the backfill's listing, a
        # refusal, and a failure at the command line (an archive it may not read: the error quotes its path).
        for odd in ("Provider Jane@example.org", "O'Brien@example.org", 'Q"uote@example.org',
                    "Za\u017c\u00f3\u0142\u0107@example.org"):
            home = cloud / odd
            paths.ensure_dir(home / "eval-runs")
            os.environ["TAB_EVAL_SCRATCH"] = str(home / "scratch")
            archive.CONFIG_FILE.write_text("%s\n" % (home / "eval-runs"))
            blob = io.StringIO()
            with contextlib.redirect_stdout(blob), contextlib.redirect_stderr(blob):
                root = run_eval.make_run_root(durable=True)
                _plant_run(root)
                got = archive.archive_run(root, evict=lambda p: (False, "planted: at %s" % p))
                if CAN_RESTORE:
                    archive.restore(root.name, evict=no_evict)
                archive.archive_existing(dry_run=True)
                for argv in (["restore", root.name], ["restore", "tab-eval-corrupt1"]):
                    if argv[1] == "tab-eval-corrupt1":
                        locked = home / "eval-runs" / "tab-eval-corrupt1.tar.zst"
                        locked.write_bytes(b"not an archive")
                        os.chmod(str(locked), 0)
                    try:
                        archive.main(argv)
                    except SystemExit as exc:
                        print(exc)
                    except Exception as exc:          # noqa: BLE001 — a raw escape is what D58 looks for
                        print("%s: %s" % (type(exc).__name__, exc))
            text = blob.getvalue()
            check("D58 sync folder %r: no line or refusal names its account" % odd,
                  got.status == "archived" and "@example.org" not in text, text[-400:])
        # NEGATIVE CONTROL for D58: the output still names the place, account withheld.
        check("D58 ... and the output still names the place, as <sync folder>",
              "<sync folder>/eval-runs/" in text and (not CAN_RESTORE or "<sync folder>/scratch/" in text),
              text[-400:])
        os.environ["TAB_EVAL_SCRATCH"] = str(scratch)
        archive.CONFIG_FILE.unlink()
        archive.evict_and_confirm = no_evict
        shutil.rmtree(str(cloud), ignore_errors=True)
        os.environ[archive.DEST_ENV] = str(drive)
        wipe()

        # A dry run never archives; a run that spends always does.
        calls = []
        archive.archive_run = lambda root, **kw: calls.append(root)
        run_eval.run_suite = compare.run = stress.run = lambda *a: 0
        for main in (run_eval.main, compare.main, stress.main):
            with contextlib.redirect_stdout(io.StringIO()):
                main(["--dry-run"])
        check("D46 no dry run (eval, comparison, stress test) calls the archive", calls == [], str(calls))
        with contextlib.redirect_stdout(io.StringIO()):
            for main in (run_eval.main, compare.main, stress.main):
                main([])
        # NEGATIVE CONTROL for D46: the spy sees each paid runner's call.
        check("D47 ... and each paid runner calls it once", len(calls) == 3, str(calls))
        archive.archive_run = real[3]
        wipe()

        # Codex review, 2026-10-26. A destination inside the run's own folder (its `config/`, which the
        # archive leaves out) would match, then go with the folder it archives.
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        inside = root / "config" / "archives"
        paths.ensure_dir(inside)
        os.environ[archive.DEST_ENV] = str(inside)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            got = archive.archive_run(root, evict=no_evict)
        check("D61 a destination inside the run's own folder is refused: the folder stays, nothing written",
              got.status == "kept" and root.is_dir() and inside.is_dir() and not list(inside.iterdir()),
              "%s, %s" % (got.status, got.why))
        os.environ[archive.DEST_ENV] = str(drive)
        wipe()
        # Two archivers of one run: neither writes into the other's temporary file.
        root = run_eval.make_run_root(durable=True)
        _plant_run(root)
        other = drive / (".%s.tar.%s.part" % (root.name, archive.archive_format()))
        other.write_bytes(b"another archiver's file, mid-write")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            got = archive.archive_run(root, evict=no_evict)
        check("D62 a second archiver's temporary file for the same run is left as it was",
              got.status == "archived" and other.is_file()
              and other.read_bytes() == b"another archiver's file, mid-write", "%s, %s" % (got.status, got.why))
        wipe()
        # Stopped by hand: nothing packed or removed. A crash still goes to the archive.
        spied = []
        archive.archive_run = lambda root, **kw: spied.append(root)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                with run_eval.paid_run_root("test") as stopped:
                    (stopped / "log.jsonl").write_text("{}\n")
                    raise KeyboardInterrupt
        except KeyboardInterrupt:
            pass
        check("D63 a paid run stopped by hand is not archived: its folder stays",
              spied == [] and stopped.is_dir(), str(spied))
        try:
            with run_eval.paid_run_root("test") as crashed:
                raise RuntimeError("planted crash")
        except RuntimeError:
            pass
        # NEGATIVE CONTROL for D63: the spy does see a run that crashed.
        check("D64 ... while a run that crashed still goes to the archive", spied == [crashed], str(spied))
        archive.archive_run = real[3]
        wipe()
        check("D65 the backfill waits out the longest quiet step of a live run (a 30-minute guard check)",
              real[10] > 30 * 60, str(real[10]))
        # Ctrl-C during a session: its own process group is stopped, not left running and spending.
        from evals.harness import session
        killed = []

        class Stuck:
            pid, returncode = 0, None

            def communicate(self, timeout=None):
                raise KeyboardInterrupt

        real_popen, real_kill = session.subprocess.Popen, session._kill_group
        session.subprocess.Popen, session._kill_group = (lambda *a, **k: Stuck()), killed.append
        try:
            session.run_session(tmp / "sess", "task", tmp / "sess-config", tmp / "sess" / "t.jsonl",
                                addendum=False)
        except KeyboardInterrupt:
            pass
        finally:
            session.subprocess.Popen, session._kill_group = real_popen, real_kill
        check("D66 a session stopped by Ctrl-C has its process group stopped too", len(killed) == 1,
              str(killed))

        # Online-only is claimed only when the file is seen dataless on disk.
        asked = lambda path: ("requested", None)  # noqa: E731
        got = real[1]("x", request=asked, dataless=lambda p: False, wait=0, poll=0)
        check("D48 an eviction the File Provider accepted but did not perform is not claimed",
              got[0] is False, str(got))
        # NEGATIVE CONTROL for D48.
        got = real[1]("x", request=asked, dataless=lambda p: True, wait=0, poll=0)
        check("D49 ... and a file seen dataless is", got == (True, None), str(got))
        started = __import__("time").monotonic()
        got = real[1]("x", request=lambda p: ("unsupported", "test"), dataless=lambda p: False, wait=60)
        check("D50 a folder no File Provider keeps is answered at once, without the wait",
              got == (None, "test") and __import__("time").monotonic() - started < 5, str(got))
        def broken(path):
            raise OSError("planted: Foundation would not load")
        got = real[1]("x", request=broken, dataless=lambda p: False, wait=60)
        check("D50 a request that fails is 'not confirmed', never 'nothing to evict', and does not wait",
              got[0] is False and __import__("time").monotonic() - started < 5, str(got))

        # The backfill: every run root a session ran in, one at a time, each matched; a kept
        # rehearsal (a run root no session ran in) and anything else left alone.
        roots = [run_eval.make_run_root(durable=True) for _ in range(2)]
        for root in roots:
            _plant_run(root)
        rehearsal = run_eval.make_run_root(durable=True)
        (rehearsal / "fixtures" / "tree.md").write_text("a dry run's tree\n")
        paths.ensure_dir(scratch / "session-selftest" / "config")
        (scratch / "baseline.log").write_text("not a run\n")
        with contextlib.redirect_stdout(io.StringIO()):
            archive.archive_existing(dry_run=True)
        check("D51 the backfill's --dry-run changes nothing",
              all(r.is_dir() for r in roots) and in_drive() == [], str(in_drive()))
        with contextlib.redirect_stdout(io.StringIO()):
            rc = archive.archive_existing(evict=no_evict)
        check("D52 the backfill archives each run root a session ran in and leaves everything else",
              rc == 0 and left() == sorted(["baseline.log", "session-selftest", rehearsal.name])
              and sorted(p.split(".")[0] for p in in_drive()) == sorted(r.name for r in roots),
              "rc %s, left %s, drive %s" % (rc, left(), in_drive()))
        # A run root whose archive is already there: removed only if the archive matches it.
        for root, extra, want in ((roots[0], None, "archived"), (roots[1], b"regraded\n", "kept")):
            _plant_run(root)
            if extra:
                (root / "log.jsonl").write_bytes(extra)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                got = archive.archive_run(root, evict=no_evict)
            check("D53 an archive already there %s: %s" % ("that differs" if extra else "that matches", want),
                  got.status == want and root.exists() == (want == "kept") and len(in_drive()) == 2,
                  "%s, drive %s" % (got.status, in_drive()))
        wipe()
        # A run root written in the last 15 minutes may belong to a run still going in another session.
        archive.RECENT = 15 * 60
        fresh, old = run_eval.make_run_root(durable=True), run_eval.make_run_root(durable=True)
        for root in (fresh, old):
            _plant_run(root)
        hour_ago = __import__("time").time() - 3600
        for dirpath, _dirs, files in os.walk(str(old)):
            for f in files:
                os.utime(os.path.join(dirpath, f), (hour_ago, hour_ago))
        with contextlib.redirect_stdout(io.StringIO()):
            archive.archive_existing(evict=no_evict)
        check("D54 the backfill leaves a run root written in the last 15 minutes",
              fresh.is_dir() and archive.archive_in(drive, fresh.name) is None, str(in_drive()))
        # NEGATIVE CONTROL for D54: the one written an hour ago is archived in the same pass.
        check("D55 ... and archives the one written an hour ago",
              not old.exists() and archive.archive_in(drive, old.name) is not None, str(in_drive()))
        archive.RECENT = 0
    finally:
        (archive.CLOUD_STORAGE, archive.evict_and_confirm, archive.write_archive, archive.archive_run,
         run_eval.run_suite, compare.run, stress.run, stress.so.load, stress.so.pick,
         archive.CONFIG_FILE, archive.RECENT) = real
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def case_runs_to_the_end(tmp):
    """Every run goes to the end, and a safety failure still fails it (2026-10-29)."""
    import types

    from evals.harness import run_eval

    ctx = types.SimpleNamespace(run_root=tmp / "plan")
    plan = [({"id": "EV-A"}, 2), ({"id": "EV-B"}, 2)]
    planned = ["EV-A-t1", "EV-A-t2", "EV-B-t1", "EV-B-t2"]

    def runner(fails):
        def run(_ctx, m, trial_id):
            sev = fails.get(trial_id)
            return {"trial_id": trial_id, "variant": m["id"], "verdict": "fail" if sev else "pass",
                    "worst_severity": sev, "failed": ["F1"] if sev else []}
        return run

    # The care failure comes first in the plan; the summary must still name the safety one first.
    for label, fails in (("a safety failure", {"EV-A-t1": "care", "EV-B-t1": "safety"}),
                         ("no failure", {})):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rows, skipped = run_eval.run_plan(ctx, plan, True, trial_runner=runner(fails),
                                              logger=lambda *_a: None)
            outcome = run_eval.summarize(rows, skipped, set(), ctx.run_root)
        text = out.getvalue()
        check("R1  %s: every planned trial ran, nothing skipped" % label,
              [r["trial_id"] for r in rows] == planned and not skipped,
              "ran %s, skipped %s" % ([r["trial_id"] for r in rows], skipped))
        if fails:
            check("R2  a safety failure fails the run: do not adopt",
                  outcome == "read-these-failures" and "DO NOT ADOPT" in text, "outcome %s" % outcome)
            listed = text[text.find("READ THESE FAILURES"):]
            check("R3  the safety failure is listed before the care failure",
                  0 <= listed.find("EV-B-t1") < listed.find("EV-A-t1"), listed)
        else:
            check("R2  the paired all-pass run is green, no do-not-adopt line",
                  outcome == "green" and "DO NOT ADOPT" not in text, "outcome %s" % outcome)


def main(argv=None):
    from evals.harness import archive
    tmp = Path(tempfile.mkdtemp(prefix="tab-eval-containment-"))
    # No case may reach a real Drive folder: a case that wants an archive names its own fake one.
    real_dest = os.environ.get(archive.DEST_ENV)
    os.environ[archive.DEST_ENV] = "off"
    archive.CLOUD_STORAGE = tmp / "no-cloud-storage"
    archive.CONFIG_FILE = tmp / "no-archive-config"
    try:
        for case in (case_registry_resolution, case_pre_transit_scan, case_blinded_scanner,
                     case_instance_dispositions, case_private_mode_file, case_roster_collision,
                     case_no_content_ever_leaks, case_run_log_rows, case_fixture_dates,
                     case_fixture_date_rows, case_regrade_reads_the_fixture_date,
                     case_throwaway_run_roots, case_stop_signals, case_run_archive,
                     case_canary_probe_verdict, case_runs_to_the_end):
            print("\n-- %s" % case.__doc__.splitlines()[0])
            case(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if real_dest is None:
            os.environ.pop(archive.DEST_ENV, None)
        else:
            os.environ[archive.DEST_ENV] = real_dest
    print("\n%d checks, %d passed, %d failed." % (len(PASS) + len(FAIL), len(PASS), len(FAIL)))
    if FAIL:
        print("FAILED: %s" % ", ".join(FAIL))
        return 1
    print("containment self-test green (every case paired with its negative control).")
    return 0


class SelfTest(unittest.TestCase):
    """The whole run as one unittest case, so the bite suite and `python3 -m unittest` run it too."""
    def test_every_case_and_its_negative_control(self):
        self.assertEqual(main(), 0, "FAILED: %s" % ", ".join(FAIL))


if __name__ == "__main__":
    sys.exit(main())
