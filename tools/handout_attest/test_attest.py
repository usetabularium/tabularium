"""Unit tests for tools.handout_attest (ADR-0039 / guard L15). Synthetic fixtures only —
never a real patient file, identifier, or hash. Run:
    python3 -m unittest tools.handout_attest.test_attest -v
    python3 -m unittest discover -s tools/handout_attest -t . -v
"""
import builtins
import contextlib
import hashlib
import io
import json
import os
import signal
import shutil
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

from . import __main__ as CLI
from . import verify as V
from ..person_ownership import fsverify as _owner

STEM = "2026-07-16__handout-patient__test-unit"
CSTEM = "2026-07-16__handout-clinician__test-unit"
ENC = "2026-07-16-test-unit"


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Tree:
    """Builds a synthetic repo tree with one patient."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="l15test-")
        self.pdir = os.path.join(self.root, "patients", "testperson")
        self.hout = os.path.join(self.pdir, "med", "handouts")
        os.makedirs(self.hout)
        self.write("med/handouts/INDEX.md", "# INDEX\n")

    def write(self, rel, content):
        p = os.path.join(self.pdir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(p, mode) as f:
            f.write(content)
        return p

    def sealed_unit(self, audience="patient", enc=ENC, stem=STEM, kind="pdf",
                    build_qa=None, index=True, attest_over=None, drop=()):
        """A consistent sealed unit; attest_over mutates attest fields; drop skips files."""
        base = "med/handouts/%s/%s/" % (audience, enc)
        md = ("id: TAB-ZZZ-9990\ndate: 2026-07-16\nlang: pl\n\n# Test\n\nsynthetic body\n").encode()
        fc = b"handout_sha256: " + sha(md).encode() + b"\nverdict: PASS\nmust_fix_open: 0\n\n# ledger\n"
        out = b"%PDF-synthetic-bytes" if kind == "pdf" else b"plain fallback text\n"
        ext = "." + kind
        attest = {
            "schema": V.ATTEST_SCHEMA, "tool": "render_handout.py/2.1.0",
            "md_file": stem + ".md", "md_sha256": sha(md),
            "factcheck_sha256": sha(fc),
            "output_kind": kind, "output_file": stem + ext, "output_sha256": sha(out),
            "audience": audience, "lang": "pl", "id": "TAB-ZZZ-9990",
            "person": "testperson", "encounter": enc,
            "build_qa": build_qa or ("PASS" if kind == "pdf" else "FALLBACK"),
            "timestamp": "2026-07-16T00:00:00Z",
        }
        if attest_over:
            attest.update(attest_over)
        if "md" not in drop:
            self.write(base + stem + ".md", md)
        if "factcheck" not in drop:
            self.write(base + stem + ".factcheck.md", fc)
        if "output" not in drop:
            self.write(base + stem + ext, out)
        if "attest" not in drop:
            self.write(base + stem + ".attest.json", json.dumps(attest))
        if index:
            with open(os.path.join(self.hout, "INDEX.md"), "a") as f:
                f.write("| %s | current |\n" % enc)
        return base

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class L15Tests(unittest.TestCase):
    def setUp(self):
        self.t = Tree()
        self.addCleanup(self.t.cleanup)

    def run_verify(self):
        return V.verify_tree(self.t.root)

    def cats(self):
        findings, _ = self.run_verify()
        return sorted(f.category for f in findings)

    def assertSealedDirSymlink(self):
        """The sealed encounter dir's own symlink finding, not the product walk's: both say `symlink`,
        so a category check alone passed with the sealed-dir check deleted."""
        findings, _ = self.run_verify()
        self.assertIn(("symlink", "symlinks undermine byte binding"),
                      [(f.category, f.detail) for f in findings])

    # ---- green paths ----
    def test_patient_free_tree_green(self):
        empty = tempfile.mkdtemp(prefix="l15empty-")
        self.addCleanup(lambda: shutil.rmtree(empty, ignore_errors=True))
        findings, agg = V.verify_tree(empty)
        self.assertEqual(findings, [])
        self.assertEqual(agg["patients"], 0)

    def test_scaffold_no_handout_dirs_green(self):
        shutil.rmtree(self.t.hout)
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])

    LEGACY_KEYS = ("patient/2026-06-08__handout-patient__old.md",
                   "patient/2026-06-08__handout-patient__old.pdf",
                   "patient/archive/2026-04-01__handout-patient__x.pdf")

    def _legacy_lane(self, freeze=True, version=2):
        """version=2 writes the byte-bound inventory (ADR-0039 A6); version=1 the superseded
        names-only shape, kept as a fixture so the migration path stays testable."""
        self.t.write("med/handouts/patient/2026-06-08__handout-patient__old.md", "old\n")
        self.t.write("med/handouts/patient/2026-06-08__handout-patient__old.pdf", b"%PDF-old")
        self.t.write("med/handouts/patient/archive/2026-04-01__handout-patient__x.pdf", b"%PDF-x")
        if freeze:
            self.t.write("med/handouts/" + V.LEGACY_FREEZE, self._freeze_body(version))

    def _freeze_body(self, version=2, keys=None):
        keys = self.LEGACY_KEYS if keys is None else keys
        if version == 1:
            return "# frozen queue\n" + "".join(k + "\n" for k in keys)
        lines = ["# frozen queue", V.LEGACY_FREEZE_MARKER]
        for k in keys:
            with open(os.path.join(self.t.hout, k), "rb") as f:
                lines.append("%s  %s" % (sha(f.read()), k))
        return "\n".join(lines) + "\n"

    def test_legacy_inventoried_flat_and_archive_queued_not_red(self):
        self._legacy_lane()
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])
        self.assertEqual(agg["legacy_unsealed"], 3)

    # ---- the inventory binds BYTES, not just names (ADR-0039 A6) ----
    def test_legacy_bytes_changed_after_freeze_red(self):
        """THE edited-legacy class: an already-inventoried legacy deliverable is edited. Names still
        match, so the pre-A6 verifier stayed green; the byte binding must red."""
        self._legacy_lane()
        self.t.write("med/handouts/patient/2026-06-08__handout-patient__old.pdf", b"%PDF-EDITED")
        cats = self.cats()
        self.assertIn("legacy-bytes-changed", cats)
        self.assertNotIn("legacy-lane-new-file", cats)   # the name is still inventoried

    def test_legacy_v1_inventory_reds_until_migrated(self):
        self._legacy_lane(version=1)
        self.assertIn("legacy-freeze-unversioned", self.cats())

    def test_legacy_v1_reds_even_though_names_all_match(self):
        """The v1 red is about the FORMAT, not about lane contents — otherwise an unmigrated
        inventory would keep passing and the mechanism would go unadopted."""
        self._legacy_lane(version=1)
        cats = self.cats()
        self.assertEqual(cats, ["legacy-freeze-unversioned"])

    def test_legacy_v2_bare_line_is_a_downgrade_and_reds(self):
        """A single bare line inside a v2 inventory would let one file escape hashing. The version
        comes from the marker, so a bare entry is malformed — never a per-line fallback to v1."""
        self._legacy_lane()
        body = self._freeze_body(2).replace(
            "  " + self.LEGACY_KEYS[1] + "\n", "  " + self.LEGACY_KEYS[1] + "\n").splitlines()
        body = [ln for ln in body if not ln.endswith(self.LEGACY_KEYS[1])]
        body.append(self.LEGACY_KEYS[1])          # re-add it in the v1 (bare) shape
        self.t.write("med/handouts/" + V.LEGACY_FREEZE, "\n".join(body) + "\n")
        cats = self.cats()
        self.assertIn("legacy-freeze-malformed", cats)

    def test_legacy_v2_conflicting_duplicate_entry_reds(self):
        self._legacy_lane()
        body = self._freeze_body(2)
        body += "%s  %s\n" % ("0" * 64, self.LEGACY_KEYS[0])
        self.t.write("med/handouts/" + V.LEGACY_FREEZE, body)
        self.assertIn("legacy-freeze-conflicting-entry", self.cats())

    def test_legacy_marker_after_entries_still_reds(self):
        """Marker placement must not create a window: entries above a late marker parse as v1 and
        the whole inventory is then malformed under v2, never silently half-bound."""
        self._legacy_lane()
        keys = "".join(k + "\n" for k in self.LEGACY_KEYS)
        self.t.write("med/handouts/" + V.LEGACY_FREEZE,
                     "# frozen queue\n" + keys + V.LEGACY_FREEZE_MARKER + "\n")
        self.assertIn("legacy-freeze-malformed", self.cats())

    def test_legacy_entry_absent_from_disk_stays_green(self):
        """The whitelist only shrinks: an inventoried file that was deleted or migrated away is
        not a finding (closure evidence for the edited-legacy class)."""
        self._legacy_lane()
        os.remove(os.path.join(self.t.hout, self.LEGACY_KEYS[2]))
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])
        self.assertEqual(agg["legacy_unsealed"], 2)

    def test_freeze_legacy_writes_byte_bound_inventory(self):
        self._legacy_lane(freeze=False)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_freeze_legacy(args), 0)
        with open(os.path.join(self.t.hout, V.LEGACY_FREEZE), encoding="utf-8") as f:
            body = f.read()
        self.assertIn(V.LEGACY_FREEZE_MARKER, body)
        frozen = V.read_freeze(self.t.hout)
        self.assertEqual(frozen.version, 2)
        self.assertEqual(frozen.errors, [])
        self.assertEqual(sorted(frozen.entries), sorted(self.LEGACY_KEYS))
        self.assertTrue(all(v and len(v) == 64 for v in frozen.entries.values()))
        self.assertEqual(self.cats(), [])
        # and a fresh freeze is immediately byte-binding: mutate one file, it reds
        self.t.write("med/handouts/" + self.LEGACY_KEYS[0], "edited\n")
        self.assertIn("legacy-bytes-changed", self.cats())

    def test_migrate_legacy_v1_to_v2_binds_current_bytes(self):
        self._legacy_lane(version=1)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 0)
        frozen = V.read_freeze(self.t.hout)
        self.assertEqual(frozen.version, 2)
        self.assertEqual(sorted(frozen.entries), sorted(self.LEGACY_KEYS))
        self.assertEqual(self.cats(), [])
        self.t.write("med/handouts/" + self.LEGACY_KEYS[1], b"%PDF-EDITED-AFTER-MIGRATION")
        self.assertIn("legacy-bytes-changed", self.cats())

    def test_migrate_legacy_refuses_an_already_bound_inventory(self):
        """Re-hashing a v2 inventory would re-bless mutated bytes — the laundering command the
        closed lane exists to prevent."""
        self._legacy_lane()
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        with open(os.path.join(self.t.hout, V.LEGACY_FREEZE), "rb") as f:
            before = f.read()
        self.t.write("med/handouts/" + self.LEGACY_KEYS[0], "mutated\n")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 2)
        with open(os.path.join(self.t.hout, V.LEGACY_FREEZE), "rb") as f:
            self.assertEqual(f.read(), before)     # untouched
        self.assertIn("legacy-bytes-changed", self.cats())   # and the mutation still reds

    def test_migrate_legacy_never_admits_a_new_path(self):
        self._legacy_lane(version=1)
        self.t.write("med/handouts/patient/2026-07-20__handout-patient__sneaked.pdf", b"%PDF-new")
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 0)
        frozen = V.read_freeze(self.t.hout)
        self.assertEqual(sorted(frozen.entries), sorted(self.LEGACY_KEYS))
        self.assertIn("legacy-lane-new-file", self.cats())   # the post-adoption write still reds

    def test_migrate_legacy_drops_entries_absent_from_disk(self):
        self._legacy_lane(version=1)
        os.remove(os.path.join(self.t.hout, self.LEGACY_KEYS[2]))
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 0)
        frozen = V.read_freeze(self.t.hout)
        self.assertEqual(sorted(frozen.entries), sorted(self.LEGACY_KEYS[:2]))
        self.assertEqual(self.cats(), [])

    def test_migrate_legacy_refuses_noncontained_and_symlinked_entries(self):
        outside = os.path.join(self.t.root, "outside-legacy.pdf")
        with open(outside, "wb") as f:
            f.write(b"%PDF-outside")
        self._legacy_lane(version=1)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        # (a) a traversal key must never be hashed (it would bless a file outside the lane)
        self.t.write("med/handouts/" + V.LEGACY_FREEZE,
                     "# frozen queue\n../../../outside-legacy.pdf\n")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 2)
        # (b) a symlinked lane entry must not be migrated into a binding either
        self.t.write("med/handouts/" + V.LEGACY_FREEZE, self._freeze_body(1))
        link = os.path.join(self.t.hout, self.LEGACY_KEYS[1])
        os.remove(link)
        os.symlink(outside, link)
        self.assertEqual(CLI._cmd_migrate_legacy(args), 2)

    def test_legacy_archive_entry_bytes_changed_red(self):
        """The archive sub-lane is byte-bound too — every other mutation bite edits a FLAT file, so
        without this one the binding could be disabled for archive/** with the suite green
        (red-team 2026-08-09)."""
        self._legacy_lane()
        self.t.write("med/handouts/" + self.LEGACY_KEYS[2], b"%PDF-ARCHIVE-EDITED")
        self.assertIn("legacy-bytes-changed", self.cats())

    def test_legacy_v2_garbled_line_reds_via_the_per_line_check(self):
        """A short/non-hex digest never reaches `entries`, so the trailing all-hashed sweep cannot
        see it — this is the per-line branch's unique coverage (red-team 2026-08-09)."""
        self._legacy_lane()
        self.t.write("med/handouts/" + V.LEGACY_FREEZE,
                     self._freeze_body(2) + "abc123  patient/whatever.pdf\n")
        self.assertIn("legacy-freeze-malformed", self.cats())

    def test_legacy_unreadable_inventory_reds_as_its_own_category(self):
        """An unreadable inventory must red on its own category, not merely as a side effect of
        every lane file then looking un-inventoried (red-team 2026-08-09)."""
        self._legacy_lane()
        fpath = os.path.join(self.t.hout, V.LEGACY_FREEZE)
        real_open = builtins.open

        def boom(path, *a, **kw):
            if os.fspath(path) == fpath:
                raise OSError("unreadable")
            return real_open(path, *a, **kw)

        with mock.patch("builtins.open", side_effect=boom):
            frozen = V.read_freeze(self.t.hout)
        self.assertEqual(frozen.errors, ["legacy-freeze-unreadable"])
        self.assertEqual(frozen.entries, {})

    def test_freeze_legacy_refuses_a_line_break_in_a_lane_path(self):
        """Injection (red-team 2026-08-09, MEDIUM): a lane entry whose NAME carries a line break
        would write a second, syntactically valid inventory entry — pre-blessing bytes for a file
        that was never in the lane. The command must refuse outright and write nothing."""
        self._legacy_lane(freeze=False)
        target_bytes = b"%PDF-never-in-the-lane"
        injected = "d\n%s  patient/2026-06-08__handout-patient__pwned.pdf" % sha(target_bytes)
        os.makedirs(os.path.join(self.t.hout, "patient", "archive", injected))
        with open(os.path.join(self.t.hout, "patient", "archive", injected, "x.pdf"), "wb") as f:
            f.write(b"%PDF-x")
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_freeze_legacy(args), 2)
        self.assertFalse(os.path.exists(os.path.join(self.t.hout, V.LEGACY_FREEZE)))
        # and the reader refuses such a key even if one is hand-written into an inventory
        self.assertTrue(V.unsafe_freeze_key("a\nb"))
        self.assertTrue(V.unsafe_freeze_key("a\rb"))
        self.assertTrue(V.unsafe_freeze_key("a\x85b"))     # splitlines() splits on this too
        self.assertTrue(V.unsafe_freeze_key("a b"))
        self.assertFalse(V.unsafe_freeze_key("patient/archive/ok name (1).pdf"))

    def test_freeze_legacy_removes_its_partial_inventory_on_write_failure(self):
        """A mid-write failure used to leave a partial/complete inventory on disk while reporting
        that nothing was written — and create-once then blocked every repair (red-team 2026-08-09)."""
        self._legacy_lane(freeze=False)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        with mock.patch("os.fsync", side_effect=OSError("ENOSPC")):
            self.assertEqual(CLI._cmd_freeze_legacy(args), 2)
        self.assertFalse(os.path.exists(os.path.join(self.t.hout, V.LEGACY_FREEZE)))
        # the lane is therefore still repairable: a clean re-run succeeds
        self.assertEqual(CLI._cmd_freeze_legacy(args), 0)
        self.assertEqual(self.cats(), [])

    def test_migrate_legacy_torn_write_leaves_the_v1_inventory_intact(self):
        """Negative control for the temp-file + os.replace shape: writing in place would leave a
        truncated inventory here (red-team 2026-08-09 — the atomicity claim had no bite)."""
        self._legacy_lane(version=1)
        fpath = os.path.join(self.t.hout, V.LEGACY_FREEZE)
        with open(fpath, "rb") as f:
            before = f.read()
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        with mock.patch("os.fsync", side_effect=OSError("EIO")):
            self.assertEqual(CLI._cmd_migrate_legacy(args), 2)
        with open(fpath, "rb") as f:
            self.assertEqual(f.read(), before)          # untouched v1, never a torn file
        self.assertEqual(V.read_freeze(self.t.hout).version, 1)
        self.assertFalse(os.path.exists(os.path.join(self.t.hout, ".legacy-frozen.migrating")))
        self.assertEqual(CLI._cmd_migrate_legacy(args), 0)   # and migration is still possible

    def test_migrate_legacy_post_commit_failure_reports_the_truth(self):
        """If only the durability barrier fails AFTER os.replace landed, the message must not claim
        the old inventory survived — that steers the operator onto the one re-bless path."""
        self._legacy_lane(version=1)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        real_fsync = os.fsync

        def fail_on_dir(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("EINVAL")
            return real_fsync(fd)

        buf = io.StringIO()
        with mock.patch("os.fsync", side_effect=fail_on_dir), contextlib.redirect_stdout(buf):
            rc = CLI._cmd_migrate_legacy(args)
        self.assertEqual(rc, 2)
        out = buf.getvalue()
        self.assertIn("WAS applied", out)
        self.assertNotIn("existing inventory retained", out)
        self.assertEqual(V.read_freeze(self.t.hout).version, 2)   # the state the message describes
        self.assertEqual(self.cats(), [])

    def test_migrate_legacy_refuses_missing_or_malformed_inventory(self):
        self._legacy_lane(freeze=False)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 2)       # nothing to migrate
        self.t.write("med/handouts/" + V.LEGACY_FREEZE,
                     V.LEGACY_FREEZE_MARKER + "\nnot-a-hashed-line\n")
        self.assertEqual(CLI._cmd_migrate_legacy(args), 2)       # structurally untrustworthy

    def test_legacy_lane_without_freeze_red(self):
        # fail closed: a legacy lane with no frozen inventory cannot be told from new writes
        self._legacy_lane(freeze=False)
        self.assertIn("legacy-freeze-missing", self.cats())

    def test_symlinked_legacy_freeze_red_without_following(self):
        outside = os.path.join(self.t.root, "outside-freeze")
        with open(outside, "w", encoding="utf-8") as f:
            f.write("# external mutable inventory\n")
        os.symlink(outside, os.path.join(self.t.hout, V.LEGACY_FREEZE))
        self.assertIn("symlink", self.cats())

    def test_nonregular_legacy_freeze_red_without_opening(self):
        os.mkfifo(os.path.join(self.t.hout, V.LEGACY_FREEZE))
        self.assertIn("non-regular-artifact", self.cats())

    def test_freeze_legacy_is_create_once(self):
        self._legacy_lane(freeze=False)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        self.assertEqual(CLI._cmd_freeze_legacy(args), 0)
        freeze = os.path.join(self.t.hout, V.LEGACY_FREEZE)
        with open(freeze, "rb") as f:
            first = f.read()
        self.t.write("med/handouts/patient/2026-07-17__handout-patient__new.pdf", b"%PDF-new")
        self.assertEqual(CLI._cmd_freeze_legacy(args), 2)
        with open(freeze, "rb") as f:
            self.assertEqual(f.read(), first)
        self.assertIn("legacy-lane-new-file", self.cats())

    def test_freeze_legacy_rejects_handle_traversal_and_symlinked_patient(self):
        outside = os.path.join(self.t.root, "outside-person")
        outside_hroot = os.path.join(outside, "med", "handouts")
        os.makedirs(outside_hroot)
        absolute = types.SimpleNamespace(root=self.t.root, handle=outside)
        traversal = types.SimpleNamespace(root=self.t.root, handle="../outside-person")
        self.assertEqual(CLI._cmd_freeze_legacy(absolute), 2)
        self.assertEqual(CLI._cmd_freeze_legacy(traversal), 2)
        link = os.path.join(self.t.root, "patients", "linkedperson")
        os.symlink(outside, link)
        linked = types.SimpleNamespace(root=self.t.root, handle="linkedperson")
        self.assertEqual(CLI._cmd_freeze_legacy(linked), 2)
        self.assertFalse(os.path.lexists(os.path.join(outside_hroot, V.LEGACY_FREEZE)))

    def test_freeze_legacy_listing_error_is_category_only_and_writes_nothing(self):
        self._legacy_lane(freeze=False)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        adir = os.path.join(self.t.hout, "patient")
        real_listdir = os.listdir

        def failed_listdir(path):
            if os.path.abspath(path) == os.path.abspath(adir):
                raise PermissionError("synthetic-sensitive-locator")
            return real_listdir(path)

        out = io.StringIO()
        with mock.patch.object(CLI.os, "listdir", side_effect=failed_listdir), \
             contextlib.redirect_stdout(out):
            self.assertEqual(CLI._cmd_freeze_legacy(args), 2)
        self.assertNotIn("synthetic-sensitive-locator", out.getvalue())
        self.assertNotIn("testperson", out.getvalue())
        self.assertNotIn("Traceback", out.getvalue())
        self.assertFalse(os.path.lexists(os.path.join(self.t.hout, V.LEGACY_FREEZE)))

    def test_freeze_legacy_archive_walk_error_is_category_only_and_writes_nothing(self):
        self._legacy_lane(freeze=False)
        args = types.SimpleNamespace(root=self.t.root, handle="testperson")
        archive = os.path.join(self.t.hout, "patient", "archive")
        real_walk = os.walk

        def failed_walk(top, *args, **kwargs):
            if os.path.abspath(top) == os.path.abspath(archive):
                kwargs["onerror"](PermissionError("synthetic-sensitive-locator"))
                return []
            return real_walk(top, *args, **kwargs)

        out = io.StringIO()
        with mock.patch.object(CLI.os, "walk", side_effect=failed_walk), \
             contextlib.redirect_stdout(out):
            self.assertEqual(CLI._cmd_freeze_legacy(args), 2)
        self.assertNotIn("synthetic-sensitive-locator", out.getvalue())
        self.assertNotIn("testperson", out.getvalue())
        self.assertNotIn("Traceback", out.getvalue())
        self.assertFalse(os.path.lexists(os.path.join(self.t.hout, V.LEGACY_FREEZE)))

    def test_new_flat_file_not_in_freeze_red(self):
        # the laundering channel (red-team 2026-07-17): a NEW un-fact-checked deliverable filed
        # flat must be red, not queued
        self._legacy_lane()
        self.t.write("med/handouts/clinician/2026-07-17__handout-clinician__nowa.pdf", b"%PDF-new")
        self.assertIn("legacy-lane-new-file", self.cats())

    def test_new_archive_file_not_in_freeze_red(self):
        self._legacy_lane()
        self.t.write("med/handouts/patient/archive/2026-07-17__handout-patient__nowa.pdf", b"%PDF-n2")
        self.assertIn("legacy-lane-new-file", self.cats())

    def test_freeze_listing_absent_file_is_fine(self):
        # a migrated-away entry (listed but gone) is a shrinking queue, never red
        self._legacy_lane()
        os.remove(os.path.join(self.t.pdir, "med/handouts/patient/2026-06-08__handout-patient__old.pdf"))
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])
        self.assertEqual(agg["legacy_unsealed"], 2)

    def test_sealed_happy_path_green(self):
        self.t.sealed_unit()
        findings, agg = self.run_verify()
        self.assertEqual([f.render() for f in findings], [])
        self.assertEqual(agg["sealed_units"], 1)

    def test_txt_fallback_happy_path_green(self):
        self.t.sealed_unit(kind="txt")
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])
        self.assertEqual(agg["sealed_units"], 1)

    def test_clinician_only_encounter_green(self):
        # audiences are INDEPENDENT (ADR-0039): a single-audience encounter is normal, never red
        self.t.sealed_unit(audience="clinician", stem=CSTEM)
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])
        self.assertEqual(agg["sealed_units"], 1)

    def test_ds_store_in_sealed_encounter_green(self):
        # Finder drops one in any folder it opens (A79): not a finding, not part of the unit
        base = self.t.sealed_unit()
        self.t.write(base + ".DS_Store", b"\x00\x00\x00\x01Bud1")
        findings, agg = self.run_verify()
        self.assertEqual([f.render() for f in findings], [])
        self.assertEqual(agg["sealed_units"], 1)

    def test_other_dotfile_in_sealed_encounter_still_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + ".hidden.pdf", b"%PDF-hidden")
        self.t.write(base + ".gitkeep", b"")
        self.assertEqual(self.cats().count("hidden-artifact"), 2)

    def test_ds_store_that_is_not_a_regular_file_still_red(self):
        base = self.t.sealed_unit()
        outside = os.path.join(self.t.root, "outside.bin")
        with open(outside, "wb") as f:
            f.write(b"x")
        os.symlink(outside, os.path.join(self.t.pdir, base + ".DS_Store"))
        self.assertSealedDirSymlink()

    def test_encounter_dir_holding_only_ds_store_still_phantom(self):
        self.t.write("med/handouts/patient/%s/.DS_Store" % ENC, b"Bud1")
        self.assertIn("phantom-encounter-dir", self.cats())

    # ---- binding breaks ----
    def test_stale_md_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".md", "id: x\n\n# edited after sealing\n")
        self.assertIn("stale-source", self.cats())

    def test_tampered_pdf_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf", b"%PDF-tampered")
        self.assertIn("tampered-output", self.cats())

    def test_tampered_txt_red(self):
        base = self.t.sealed_unit(kind="txt")
        self.t.write(base + STEM + ".txt", b"tampered fallback\n")
        self.assertIn("tampered-output", self.cats())

    def test_stale_factcheck_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".factcheck.md", "handout_sha256: 0\nverdict: PASS\nmust_fix_open: 0\n")
        self.assertIn("stale-factcheck", self.cats())

    def test_missing_factcheck_red(self):
        self.t.sealed_unit(drop=("factcheck",))
        self.assertIn("missing-factcheck", self.cats())

    def test_missing_output_red(self):
        self.t.sealed_unit(drop=("output",))
        self.assertIn("missing-output", self.cats())

    # ---- structural breaks ----
    def test_draft_md_without_factcheck_green(self):
        # A7: a draft awaiting its seal is not a finding — the seal gate is the lock.
        self.t.sealed_unit(drop=("attest", "output", "factcheck"), index=False)
        self.assertEqual(self.cats(), [])

    def test_draft_md_with_failing_factcheck_green(self):
        base = self.t.sealed_unit(drop=("attest", "output"), index=False)
        self.t.write(base + STEM + ".factcheck.md", "handout_sha256: %s\nverdict: FAIL\n"
                     "must_fix_open: 2\n\n# ledger\n" % ("0" * 64))
        self.assertEqual(self.cats(), [])

    def test_output_beside_draft_red(self):
        self.t.sealed_unit(drop=("attest",))
        cats = self.cats()
        self.assertIn("orphan-output", cats)
        self.assertNotIn("unsealed-md", cats)

    def test_unattested_md_beside_sealed_unit_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + "2026-07-16__handout-patient__second.md", "draft\n")
        self.assertIn("unsealed-md", self.cats())

    def _cli_verify_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = CLI._cmd_verify(types.SimpleNamespace(root=self.t.root))
        return rc, out.getvalue()

    def test_cli_red_names_the_path(self):
        self.t.write("profile.md", "# profile\n")
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf", b"%PDF-tampered")
        rc, out = self._cli_verify_output()
        self.assertEqual(rc, 1)
        self.assertIn("[tampered-output] patients/testperson/" + base + STEM + ".pdf", out)

    def test_cli_red_withholds_path_for_private_mode_person(self):
        self.t.write("profile.md", "# profile\n- Private mode: synthetic ⟨never-API⟩\n")
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf", b"%PDF-tampered")
        rc, out = self._cli_verify_output()
        self.assertEqual(rc, 1)
        self.assertIn("[tampered-output] " + _owner.WITHHELD_PRIVATE, out)
        self.assertNotIn("testperson", out)
        self.assertNotIn("test-unit", out)

    def test_cli_withholds_unknown_owner_only_while_private_mode_in_use(self):
        # testperson has no profile.md: owner unknown. Printed while nobody is private-mode…
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf", b"%PDF-tampered")
        rc, out = self._cli_verify_output()
        self.assertIn("patients/testperson/", out)
        # …withheld once another person declares private mode.
        other = os.path.join(self.t.root, "patients", "otherperson")
        os.makedirs(other)
        with open(os.path.join(other, "profile.md"), "w", encoding="utf-8") as f:
            f.write("# profile\n- Private mode: synthetic ⟨never-API⟩\n")
        rc, out = self._cli_verify_output()
        self.assertEqual(rc, 1)
        self.assertIn(_owner.WITHHELD_UNKNOWN, out)
        self.assertNotIn("testperson", out)

    def test_orphan_output_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + "2026-07-16__handout-patient__extra.pdf", b"%PDF-orphan")
        self.assertIn("orphan-output", self.cats())

    def test_orphan_attestation_red(self):
        self.t.sealed_unit(drop=("md",))
        self.assertIn("orphan-attestation", self.cats())

    def test_orphan_factcheck_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + "2026-07-16__handout-patient__lone.factcheck.md", "x\n")
        self.assertIn("orphan-factcheck", self.cats())

    def test_conflicting_pdf_and_txt_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".txt", b"stray fallback\n")
        self.assertIn("conflicting-deliverables", self.cats())

    def test_phantom_empty_encounter_dir_red(self):
        os.makedirs(os.path.join(self.t.hout, "patient", ENC))
        self.assertIn("phantom-encounter-dir", self.cats())

    def test_malformed_encounter_name_red(self):
        os.makedirs(os.path.join(self.t.hout, "patient", "notadate-slug"))
        self.assertIn("malformed-encounter-dir", self.cats())

    def test_impossible_calendar_date_red(self):
        # 2026-99-99 passes a shape regex; only a real calendar parse rejects it (HO-09 lesson)
        os.makedirs(os.path.join(self.t.hout, "patient", "2026-99-99-bad"))
        self.assertIn("malformed-encounter-dir", self.cats())

    def test_unknown_artifact_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf.tmp", b"leftover")
        self.assertIn("unknown-artifact", self.cats())

    def test_unknown_audience_dir_red(self):
        os.makedirs(os.path.join(self.t.hout, "insurer"))
        self.assertIn("unknown-audience-dir", self.cats())

    def test_root_stray_red(self):
        self.t.write("med/handouts/stray.pdf", b"%PDF-stray")
        self.assertIn("root-stray", self.cats())

    def test_hidden_root_directory_red(self):
        os.makedirs(os.path.join(self.t.hout, ".hidden-products"))
        self.assertIn("hidden-artifact", self.cats())

    def test_hidden_flat_product_red(self):
        self.t.write("med/handouts/patient/.hidden.pdf", b"%PDF-hidden")
        self.assertIn("hidden-artifact", self.cats())

    def test_legacy_archive_walk_error_red(self):
        self._legacy_lane()
        archive = os.path.join(self.t.hout, "patient", "archive")
        real_walk = os.walk

        def failed_walk(top, *args, **kwargs):
            if os.path.abspath(top) == os.path.abspath(archive):
                kwargs["onerror"](PermissionError("synthetic-sensitive-locator"))
                return []
            return real_walk(top, *args, **kwargs)

        with mock.patch.object(V.os, "walk", side_effect=failed_walk):
            self.assertIn("uninspectable-artifact", self.cats())

    def test_product_walk_error_red(self):
        self.t.sealed_unit()
        real_walk = os.walk

        def failed_walk(top, *args, **kwargs):
            if os.path.abspath(top) == os.path.abspath(self.t.hout):
                kwargs["onerror"](PermissionError("synthetic-sensitive-locator"))
                return []
            return real_walk(top, *args, **kwargs)

        with mock.patch.object(V.os, "walk", side_effect=failed_walk):
            self.assertIn("uninspectable-artifact", self.cats())

    def test_standalone_verify_rejects_symlinked_patients_root(self):
        patients = os.path.join(self.t.root, "patients")
        outside = os.path.join(self.t.root, "outside-patients")
        shutil.move(patients, outside)
        os.symlink(outside, patients)
        self.assertIn("symlink", self.cats())

    def test_standalone_verify_rejects_hidden_patient_root(self):
        os.makedirs(os.path.join(self.t.root, "patients", ".hidden-synthetic"))
        self.assertIn("hidden-patient-root", self.cats())

    def test_standalone_verify_rejects_symlinked_patient_root(self):
        outside = os.path.join(self.t.root, "outside-person")
        os.makedirs(outside)
        os.symlink(outside, os.path.join(self.t.root, "patients", "linked-synthetic"))
        self.assertIn("symlink", self.cats())

    def test_uninspectable_med_root_red_instead_of_absent_green(self):
        med = os.path.join(self.t.pdir, "med")
        real_listdir = os.listdir

        def failed_listdir(path):
            if os.path.abspath(path) == os.path.abspath(med):
                raise PermissionError("synthetic-sensitive-locator")
            return real_listdir(path)

        with mock.patch.object(V.os, "listdir", side_effect=failed_listdir):
            self.assertIn("uninspectable-root", self.cats())

    def test_symlinked_handouts_root_red_without_traversal(self):
        outside = os.path.join(self.t.root, "outside-handouts")
        shutil.move(self.t.hout, outside)
        os.symlink(outside, self.t.hout)
        self.assertIn("symlink", self.cats())

    def test_fifo_artifact_red_without_hanging(self):
        base = self.t.sealed_unit()
        fifo = os.path.join(self.t.pdir, base + "stray.pdf")
        os.mkfifo(fifo)
        old_handler = signal.signal(
            signal.SIGALRM,
            lambda _signum, _frame: (_ for _ in ()).throw(AssertionError("verifier hung on FIFO")),
        )
        signal.alarm(2)
        try:
            self.assertIn("non-regular-artifact", self.cats())
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def test_hidden_symlink_artifact_red(self):
        base = self.t.sealed_unit()
        outside = os.path.join(self.t.root, "outside.pdf")
        with open(outside, "wb") as f:
            f.write(b"%PDF-outside")
        os.symlink(outside, os.path.join(self.t.pdir, base + ".hidden.pdf"))
        self.assertSealedDirSymlink()

    def test_two_attested_stems_in_one_encounter_red(self):
        self.t.sealed_unit()
        second = "2026-07-16__handout-patient__second"
        self.t.sealed_unit(stem=second)
        self.assertIn("multiple-sealed-units", self.cats())

    # ---- attestation content breaks ----
    def test_malformed_json_red(self):
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".attest.json", "{not json")
        self.assertIn("malformed-attestation", self.cats())

    def test_unknown_schema_red(self):
        self.t.sealed_unit(attest_over={"schema": "tabularium-handout-attest/v99"})
        self.assertIn("unknown-attestation-schema", self.cats())

    def test_duplicate_json_key_red(self):
        base = self.t.sealed_unit()
        apath = os.path.join(self.t.pdir, base + STEM + ".attest.json")
        with open(apath, encoding="utf-8") as f:
            raw = f.read()
        with open(apath, "w", encoding="utf-8") as f:
            f.write('{"output_sha256":"conflicting",' + raw.lstrip()[1:])
        self.assertIn("malformed-attestation", self.cats())

    def test_unknown_attestation_field_red(self):
        self.t.sealed_unit(attest_over={"unexpected": "value"})
        self.assertIn("malformed-attestation", self.cats())

    def test_missing_field_red(self):
        self.t.sealed_unit(attest_over={"output_sha256": ""})
        self.assertIn("malformed-attestation", self.cats())

    def test_qa_kind_inconsistent_red(self):
        self.t.sealed_unit(kind="txt", build_qa="PASS")
        self.assertIn("malformed-attestation", self.cats())

    def test_audience_mismatch_red(self):
        self.t.sealed_unit(attest_over={"audience": "clinician"})
        self.assertIn("audience-mismatch", self.cats())

    # ---- person / encounter / leaf binding (red-team 2026-07-17: portable-unit class) ----
    def test_person_mismatch_red(self):
        # a sealed unit copied into another patient's tree — the #1 error class, product lane
        self.t.sealed_unit(attest_over={"person": "innaosoba"})
        self.assertIn("person-mismatch", self.cats())

    def test_encounter_mismatch_red(self):
        # unit renamed/moved into a different-dated encounter dir (stale presented as current)
        self.t.sealed_unit(attest_over={"encounter": "2026-01-01-stara"})
        self.assertIn("encounter-mismatch", self.cats())

    def test_missing_person_field_red(self):
        self.t.sealed_unit(attest_over={"person": ""})
        self.assertIn("malformed-attestation", self.cats())

    def test_empty_id_is_fine(self):
        self.t.sealed_unit(attest_over={"id": ""})
        findings, agg = self.run_verify()
        self.assertEqual(findings, [])
        self.assertEqual(agg["sealed_units"], 1)

    def test_leaf_date_mismatch_red(self):
        # leaf dated 2026-07-16 sealed inside a 2026-07-15-* encounter dir — one unit, one date
        self.t.sealed_unit(enc="2026-07-15-test-unit",
                           attest_over={"encounter": "2026-07-15-test-unit"})
        self.assertIn("leaf-date-mismatch", self.cats())

    def test_leaf_audience_mismatch_red(self):
        # __handout-patient__ leaf sealed under clinician/ with a directory-matching attestation —
        # the detached file would misreport its own audience (red-team repro)
        self.t.sealed_unit(audience="clinician", stem=STEM,
                           attest_over={"audience": "clinician"})
        self.assertIn("leaf-audience-mismatch", self.cats())

    def test_noncanonical_complete_unit_red_and_not_counted_sealed(self):
        self.t.sealed_unit(stem="2026-07-16-noncanonical")
        findings, agg = self.run_verify()
        self.assertIn("noncanonical-leaf", [f.category for f in findings])
        self.assertEqual(agg["sealed_units"], 0)

    # ---- INDEX ----
    def test_index_missing_sealed_unit_red(self):
        self.t.sealed_unit(index=False)
        self.assertIn("index-missing", self.cats())

    def test_index_substring_is_not_presence(self):
        # INDEX names only the LONGER '…-test-unit-extended'; the sealed '…-test-unit' must red
        self.t.sealed_unit(index=False)
        with open(os.path.join(self.t.hout, "INDEX.md"), "a") as f:
            f.write("| %s-extended | current |\n" % ENC)
        self.assertIn("index-missing", self.cats())

    def test_index_superstring_suffix_is_not_presence(self):
        # LEFT edge (red-team 2026-07-17): an INDEX row naming '…-przygotowanie-<ENC>' must not
        # satisfy presence for the unlisted <ENC> — slugs admit digits and hyphens
        self.t.sealed_unit(index=False)
        with open(os.path.join(self.t.hout, "INDEX.md"), "a") as f:
            f.write("| 2026-07-01-przygotowanie-%s | current |\n" % ENC)
        self.assertIn("index-missing", self.cats())

    def test_index_absent_with_sealed_unit_red(self):
        self.t.sealed_unit()
        os.remove(os.path.join(self.t.hout, "INDEX.md"))
        self.assertIn("index-missing", self.cats())

    # ---- lane separation + path safety ----
    def test_product_in_evidence_red(self):
        payload = b"identical bytes in both lanes"
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf", payload)  # breaks attest too, but the lane check must fire
        self.t.write("med/sources/2026-07-01__source__dup.pdf", payload)
        self.assertIn("product-in-evidence", self.cats())

    def test_evidence_boilerplate_not_a_product_hit(self):
        payload = b"# boilerplate readme\n"
        self.t.write("med/handouts/README.md", payload)
        self.t.write("med/sources/README.md", payload)
        self.assertNotIn("product-in-evidence", self.cats())

    def test_symlinked_evidence_root_red_without_following(self):
        self.t.sealed_unit()
        os.symlink(self.t.hout, os.path.join(self.t.pdir, "med", "sources"))
        self.assertIn("symlink", self.cats())

    def test_symlinked_evidence_file_red_without_hashing_target(self):
        base = self.t.sealed_unit()
        product = os.path.join(self.t.pdir, base + STEM + ".pdf")
        sources = os.path.join(self.t.pdir, "med", "sources")
        os.makedirs(sources)
        os.symlink(product, os.path.join(sources, "2026-07-01__source__linked.pdf"))
        self.assertIn("symlink", self.cats())

    def test_wrong_type_evidence_root_red(self):
        self.t.sealed_unit()
        self.t.write("med/sources", b"not a directory\n")
        self.assertIn("lane-root-wrong-type", self.cats())

    def test_symlink_red(self):
        base = self.t.sealed_unit()
        real = os.path.join(self.t.pdir, base + STEM + ".pdf")
        link = os.path.join(self.t.pdir, base + "2026-07-16__handout-patient__alias.pdf")
        os.symlink(real, link)
        self.assertSealedDirSymlink()

    # ---- the draft home: HANDOUT-SOP step 1 keeps drafts in med/analysis/drafts/ ----
    def _strays(self, root):
        """The stray shapes a draft or a scratch folder takes: an empty encounter-shaped folder, an
        empty folder under an audience, an empty folder beside the audiences. `root` is where they
        sit — the draft home, or the handouts lane (the twin that must red)."""
        for rel in ("patient/2026-07-17-next", "patient/scratch", "scratch"):
            os.makedirs(os.path.join(self.t.pdir, root, rel))

    def _draft_files(self):
        self.t.write("med/analysis/drafts/2026-07-17__handout-patient__next.md",
                     "id: TAB-ZZZ-9991\ndate: 2026-07-17\nlang: pl\n\n# draft\n")
        self.t.write("med/analysis/drafts/2026-07-17__handout-patient__next.draft.pdf", b"%PDF-draft")
        self.t.write("med/analysis/previews/2026-07-17__handout-patient__next.draft-1.html",
                     "<html></html>")

    def test_draft_home_beside_a_sealed_unit_is_green(self):
        # (a) drafts, previews, a draft PDF and empty folders in med/analysis/ never red L15 ...
        self.t.sealed_unit()
        self._draft_files()
        self._strays("med/analysis/drafts")
        findings, agg = self.run_verify()
        self.assertEqual([f.category for f in findings], [])
        self.assertEqual(agg["sealed_units"], 1)

    def test_same_strays_in_the_lane_red_and_tampering_still_red(self):
        # ... the twin: the SAME empty folders under med/handouts/ red, so the green above is the
        # location's doing; (b) and a tampered sealed unit beside them still reds as before.
        base = self.t.sealed_unit()
        self._strays("med/handouts")
        self.t.write(base + STEM + ".pdf", b"%PDF-tampered")
        cats = self.cats()
        for cat in ("phantom-encounter-dir", "malformed-encounter-dir", "unknown-audience-dir",
                    "tampered-output"):
            self.assertIn(cat, cats)

    def test_cli_points_a_stray_folder_to_the_draft_home(self):
        shapes = {
            "phantom-encounter-dir": lambda t: os.makedirs(
                os.path.join(t.hout, "patient", "2026-07-17-next")),
            "malformed-encounter-dir": lambda t: os.makedirs(
                os.path.join(t.hout, "patient", "scratch")),
            "unknown-audience-dir": lambda t: os.makedirs(os.path.join(t.hout, "scratch")),
            "unexpected-subdir": lambda t: os.makedirs(
                os.path.join(t.pdir, t.sealed_unit(), "previews")),
        }
        for category, make in shapes.items():
            with self.subTest(category=category):
                self.t = Tree()               # a fresh tree per shape
                self.addCleanup(self.t.cleanup)
                make(self.t)
                rc, out = self._cli_verify_output()
                self.assertEqual(rc, 1)
                self.assertIn("[%s]" % category, out)
                self.assertIn("med/analysis/drafts/", out)
                self.assertIn("never move it", out)

    def test_cli_gives_no_pointer_for_findings_on_sealed_bytes(self):
        # a deliverable is repaired in place; telling a session to move it out would be the
        # park-it-to-go-green workaround the pointer exists to prevent
        base = self.t.sealed_unit()
        self.t.write(base + STEM + ".pdf", b"%PDF-tampered")
        self.t.write(base + "2026-07-16__handout-patient__extra.pdf", b"%PDF-orphan")
        rc, out = self._cli_verify_output()
        self.assertEqual(rc, 1)
        self.assertIn("[tampered-output]", out)
        self.assertIn("[orphan-output]", out)
        self.assertNotIn("hint", out)
        self.assertNotIn("med/analysis", out)

    def test_cli_pointer_names_no_person_in_private_mode(self):
        self.t.write("profile.md", "# profile\n- Private mode: synthetic ⟨never-API⟩\n")
        os.makedirs(os.path.join(self.t.hout, "patient", "2026-07-17-next"))
        rc, out = self._cli_verify_output()
        self.assertEqual(rc, 1)
        self.assertIn("[phantom-encounter-dir] " + _owner.WITHHELD_PRIVATE, out)
        self.assertIn("med/analysis/drafts/", out)
        self.assertNotIn("testperson", out)
        self.assertNotIn("2026-07-17", out)

    def test_public_finding_render_is_category_only(self):
        rendered = V.Finding("synthetic-category", "private-handle",
                             "private/path", "private detail").render()
        self.assertEqual(rendered, "[synthetic-category]")


class SealLocationTests(unittest.TestCase):
    """The renderer's in-place seal gate (red-team 2026-07-17): a seal must resolve a valid
    patients/<handle>/med/handouts/<audience>/<YYYY-MM-DD-slug>/ location or refuse (exit 5).
    render_handout.py is stdlib-only at import (weasyprint loads inside render()), so the pure
    path logic is testable here without the render env."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                         "_templates", "handout-assets", "render_handout.py"))
        spec = importlib.util.spec_from_file_location("render_handout_under_test", p)
        cls.rh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rh)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="l15loc-")
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        repo_patch = mock.patch.object(self.rh, "REPO_ROOT", self.root)
        repo_patch.start()
        self.addCleanup(repo_patch.stop)

    def p(self, rel):
        return os.path.join(self.root, rel)

    def materialize(self, rel, content=b"# synthetic handout\n"):
        path = self.p(rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def refuse(self, rel, audience="patient"):
        path = self.materialize(rel)
        with self.assertRaises(SystemExit) as cm:
            self.rh.seal_location(path, audience)
        self.assertEqual(cm.exception.code, 5)

    def test_valid_location_returns_binding(self):
        path = self.materialize(
            "patients/testperson/med/handouts/patient/2026-07-16-wizyta/"
            "2026-07-16__handout-patient__x.md")
        got = self.rh.seal_location(
            path, "patient")
        self.assertEqual(got, ("testperson", "2026-07-16-wizyta"))

    def test_filename_stable_id_must_match_front_matter(self):
        path = self.materialize(
            "scratch/2026-07-16__handout-patient__summary__TAB-AAA-0015.md")
        self.rh.assert_filename_id_matches_metadata(path, "TAB-AAA-0015")
        with self.assertRaises(SystemExit) as cm:
            self.rh.assert_filename_id_matches_metadata(path, "TAB-AAA-014F")
        self.assertEqual(cm.exception.code, 5)

    def test_legacy_filename_does_not_impose_an_id(self):
        path = self.materialize("scratch/2026-07-16__handout-patient__legacy.md")
        self.rh.assert_filename_id_matches_metadata(path, "TAB-AAA-0015")

    def test_outside_patients_tree_refused(self):
        self.refuse("scratch/2026-07-16__handout-patient__x.md")

    def test_complete_external_lookalike_tree_refused(self):
        self.refuse("lookalike/patients/testperson/med/handouts/patient/2026-07-16-w/"
                    "2026-07-16__handout-patient__x.md")

    def test_symlink_at_each_seal_component_refused(self):
        rel = ("patients/testperson/med/handouts/patient/2026-07-16-w/"
               "2026-07-16__handout-patient__x.md")
        for component_index in range(7):  # patients root through the leaf
            with self.subTest(component_index=component_index):
                case_root = tempfile.mkdtemp(prefix="l15symlink-")
                self.addCleanup(lambda p=case_root: shutil.rmtree(p, ignore_errors=True))
                path = os.path.join(case_root, rel)
                os.makedirs(os.path.dirname(path))
                with open(path, "wb") as f:
                    f.write(b"# synthetic\n")
                parts = rel.split(os.sep)
                victim = os.path.join(case_root, *parts[:component_index + 1])
                moved = victim + ".real"
                shutil.move(victim, moved)
                os.symlink(moved, victim)
                with mock.patch.object(self.rh, "REPO_ROOT", case_root), \
                     self.assertRaises(SystemExit) as cm:
                    self.rh.seal_location(path, "patient")
                self.assertEqual(cm.exception.code, 5)

    def test_nonregular_leaf_refused_without_opening(self):
        rel = ("patients/testperson/med/handouts/patient/2026-07-16-w/"
               "2026-07-16__handout-patient__x.md")
        path = self.materialize(rel)
        os.remove(path)
        os.mkfifo(path)
        with self.assertRaises(SystemExit) as cm:
            self.rh.seal_location(path, "patient")
        self.assertEqual(cm.exception.code, 5)

    def test_flat_audience_level_refused(self):
        # sealing a FLAT file would mint a cosmetic attestation the verifier never opens
        self.refuse("patients/t/med/handouts/patient/2026-07-16__handout-patient__x.md")

    def test_wrong_audience_dir_refused(self):
        self.refuse("patients/t/med/handouts/clinician/2026-07-16-w/"
                    "2026-07-16__handout-patient__x.md", audience="patient")

    def test_invalid_encounter_dir_refused(self):
        self.refuse("patients/t/med/handouts/patient/notadate-slug/"
                    "2026-07-16__handout-patient__x.md")

    def test_impossible_calendar_date_refused(self):
        self.refuse("patients/t/med/handouts/patient/2026-99-99-w/"
                    "2026-99-99__handout-patient__x.md")

    def test_leaf_date_vs_dir_date_refused(self):
        self.refuse("patients/t/med/handouts/patient/2026-07-15-w/"
                    "2026-07-16__handout-patient__x.md")

    def test_noncanonical_leaf_refused_even_with_explicit_audience(self):
        self.refuse("patients/t/med/handouts/patient/2026-07-16-w/"
                    "2026-07-16-noncanonical.md")

    # The seal gate is the one fact-check lock since guard L11 retired (ADR-0034 point 3): each
    # shape L11 used to red must make the gate refuse (exit 4).
    def _gate(self, sidecar_text=None, data=b"# synthetic\n"):
        md = self.materialize("gate.md", data)
        if sidecar_text is not None:
            with open(self.p("gate.factcheck.md"), "w", encoding="utf-8") as f:
                f.write(sidecar_text)
        with self.assertRaises(SystemExit) as cm:
            self.rh.factcheck_gate(md, hashlib.sha256(data).hexdigest())
        self.assertEqual(cm.exception.code, 4)

    def test_factcheck_gate_refuses_what_l11_used_to_red(self):
        good = hashlib.sha256(b"# synthetic\n").hexdigest()
        for label, text in (
                ("missing sidecar", None),
                ("stale hash", "handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n" % ("0" * 64)),
                ("FAIL verdict", "handout_sha256: %s\nverdict: FAIL\nmust_fix_open: 0\n\n" % good),
                ("open must-fix", "handout_sha256: %s\nverdict: PASS\nmust_fix_open: 2\n\n" % good),
                ("missing field", "handout_sha256: %s\nverdict: PASS\n\n# ledger\n" % good)):
            with self.subTest(label):
                side = self.p("gate.factcheck.md")
                if os.path.lexists(side):
                    os.unlink(side)
                self._gate(text)

    def test_factcheck_gate_accepts_fresh_pass(self):
        data = b"# synthetic\n"
        md = self.materialize("gate.md", data)
        digest = hashlib.sha256(data).hexdigest()
        with open(self.p("gate.factcheck.md"), "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n# ledger\n" % digest)
        self.assertEqual(len(self.rh.factcheck_gate(md, digest)), 64)

    def test_factcheck_duplicate_control_field_refused(self):
        md = self.p("draft.md")
        os.makedirs(os.path.dirname(md), exist_ok=True)
        data = b"# synthetic\n"
        with open(md, "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        with open(self.p("draft.factcheck.md"), "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n"
                    "verdict: FAIL\n" % digest)
        with self.assertRaises(SystemExit) as cm:
            self.rh.factcheck_gate(md, digest)
        self.assertEqual(cm.exception.code, 4)

    def test_factcheck_colon_suffix_values_refused(self):
        md = self.p("draft.md")
        os.makedirs(os.path.dirname(md), exist_ok=True)
        data = b"# synthetic\n"
        with open(md, "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        with open(self.p("draft.factcheck.md"), "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s:stale\nverdict: PASS:FAIL\nmust_fix_open: 0:9\n\n"
                    "# ledger\n" % digest)
        with self.assertRaises(SystemExit) as cm:
            self.rh.factcheck_gate(md, digest)
        self.assertEqual(cm.exception.code, 4)

    def test_factcheck_controls_displaced_from_first_lines_refused(self):
        md = self.p("draft.md")
        os.makedirs(os.path.dirname(md), exist_ok=True)
        data = b"# synthetic\n"
        with open(md, "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        with open(self.p("draft.factcheck.md"), "w", encoding="utf-8") as f:
            f.write("# prose first\nhandout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n"
                    "# ledger\n" % digest)
        with self.assertRaises(SystemExit) as cm:
            self.rh.factcheck_gate(md, digest)
        self.assertEqual(cm.exception.code, 4)

    def test_factcheck_unreadable_sidecar_has_no_path_traceback(self):
        md = self.p("private-clinical-name.md")
        os.makedirs(os.path.dirname(md), exist_ok=True)
        data = b"# synthetic\n"
        with open(md, "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        side = self.p("private-clinical-name.factcheck.md")
        with open(side, "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n" % digest)
        real_open = builtins.open

        def guarded_open(path, *args, **kwargs):
            if os.fspath(path) == side:
                raise PermissionError("private-clinical-name.factcheck.md")
            return real_open(path, *args, **kwargs)

        err = io.StringIO()
        with mock.patch("builtins.open", side_effect=guarded_open), \
             contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.rh.factcheck_gate(md, digest)
        self.assertEqual(cm.exception.code, 4)
        self.assertNotIn("private-clinical-name", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_factcheck_symlink_refused_without_reading_target(self):
        md = self.materialize("draft.md", b"# synthetic\n")
        digest = hashlib.sha256(b"# synthetic\n").hexdigest()
        outside = self.materialize(
            "outside-sidecar",
            ("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n" % digest).encode())
        os.symlink(outside, self.p("draft.factcheck.md"))
        with self.assertRaises(SystemExit) as cm:
            self.rh.factcheck_gate(md, digest)
        self.assertEqual(cm.exception.code, 4)

    # ADR-0070: a five-line sidecar binds the record the verifier checked; the gate re-hashes the
    # person's profile.md and medications.md and refuses a change since the verify.
    def _record(self, profile=b"# profile\n", meds=b"# medications\n"):
        person = self.p("patients/t")
        os.makedirs(person, exist_ok=True)
        for name, data in (("profile.md", profile), ("medications.md", meds)):
            with open(os.path.join(person, name), "wb") as f:
                f.write(data)
        return person, hashlib.sha256(profile).hexdigest(), hashlib.sha256(meds).hexdigest()

    def _five_line(self, digest, prof, meds, tail="\n# ledger\n"):
        return ("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\nprofile_sha256: %s\n"
                "medications_sha256: %s\n%s" % (digest, prof, meds, tail))

    def _gate_with_record(self, sidecar_text, person, data=b"# synthetic\n"):
        md = self.materialize("gate.md", data)
        with open(self.p("gate.factcheck.md"), "w", encoding="utf-8") as f:
            f.write(sidecar_text)
        return self.rh.factcheck_gate(md, hashlib.sha256(data).hexdigest(), person)

    def _refused_with_record(self, sidecar_text, person):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self._gate_with_record(sidecar_text, person)
        self.assertEqual(cm.exception.code, 4)
        return err.getvalue()

    def test_factcheck_gate_accepts_five_line_sidecar_with_unchanged_record(self):
        person, prof, meds = self._record()
        digest = hashlib.sha256(b"# synthetic\n").hexdigest()
        self.assertEqual(len(self._gate_with_record(self._five_line(digest, prof, meds), person)), 64)

    def test_factcheck_gate_refuses_a_record_changed_since_verification(self):
        digest = hashlib.sha256(b"# synthetic\n").hexdigest()
        for changed in ("medications.md", "profile.md"):
            with self.subTest(changed):
                person, prof, meds = self._record()
                with open(os.path.join(person, changed), "ab") as f:
                    f.write(b"- 2026-11-07 dose changed\n")
                err = self._refused_with_record(self._five_line(digest, prof, meds), person)
                self.assertIn("profile.md or medications.md changed since verification", err)
                self.assertIn("run a later verify round, then seal", err)

    def test_factcheck_gate_three_line_sidecar_still_seals_with_a_record_present(self):
        person, _prof, _meds = self._record()
        digest = hashlib.sha256(b"# synthetic\n").hexdigest()
        text = "handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n# ledger\n" % digest
        self.assertEqual(len(self._gate_with_record(text, person)), 64)

    def test_factcheck_gate_refuses_malformed_record_lines(self):
        person, prof, meds = self._record()
        digest = hashlib.sha256(b"# synthetic\n").hexdigest()
        head = "handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n" % digest
        for label, text in (
                ("one of two", head + "profile_sha256: %s\n\n# ledger\n" % prof),
                ("bad hex", self._five_line(digest, prof, "X" * 64)),
                ("after the blank line", head + "\nprofile_sha256: %s\nmedications_sha256: %s\n"
                                                % (prof, meds)),
                ("repeated", self._five_line(digest, prof, meds,
                                             tail="\nmedications_sha256: %s\n" % meds)),
                ("order swapped", head + "medications_sha256: %s\nprofile_sha256: %s\n\n"
                                         % (meds, prof))):
            with self.subTest(label):
                self._refused_with_record(text, person)

    def test_factcheck_gate_five_line_refuses_an_unreadable_record_without_a_path(self):
        digest = hashlib.sha256(b"# synthetic\n").hexdigest()
        for label in ("missing", "symlinked", "no person dir"):
            with self.subTest(label):
                person, prof, meds = self._record()
                target = os.path.join(person, "medications.md")
                if label == "missing":
                    os.unlink(target)
                elif label == "symlinked":
                    outside = self.materialize("outside-meds.md", b"# medications\n")
                    os.unlink(target)
                    os.symlink(outside, target)
                err = self._refused_with_record(self._five_line(digest, prof, meds),
                                                None if label == "no person dir" else person)
                self.assertNotIn(self.root, err)
                self.assertNotIn("Traceback", err)

    def test_preflight_rejects_symlinked_output_and_reserved_temp(self):
        md = self.materialize("draft.md")
        outside = self.materialize("outside-output", b"untouched\n")
        out = self.p("draft.pdf")
        os.symlink(outside, out)
        with self.assertRaises(SystemExit) as cm:
            self.rh.preflight_artifact_paths(md, out, draft=False)
        self.assertEqual(cm.exception.code, 5)
        os.unlink(out)
        with open(out + ".tmp", "wb") as f:
            f.write(b"stale\n")
        with self.assertRaises(SystemExit) as cm:
            self.rh.preflight_artifact_paths(md, out, draft=False)
        self.assertEqual(cm.exception.code, 5)

    def test_draft_out_cannot_name_or_replace_an_arbitrary_deliverable(self):
        md = self.materialize("scratch/source.md")
        live = self.materialize("scratch/live.pdf", b"live bytes\n")
        err = io.StringIO()
        with mock.patch.object(sys, "argv", [
                "render_handout.py", md, "--draft", "--out", live]), \
             mock.patch.object(self.rh, "render") as render_mock, \
             contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.rh.main()
        self.assertEqual(cm.exception.code, 5)
        with open(live, "rb") as f:
            self.assertEqual(f.read(), b"live bytes\n")
        render_mock.assert_not_called()

        named_draft = self.materialize("scratch/source.draft.pdf", b"prior draft\n")
        with mock.patch.object(sys, "argv", [
                "render_handout.py", md, "--draft", "--out", named_draft]), \
             mock.patch.object(self.rh, "render") as render_mock, \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            self.rh.main()
        self.assertEqual(cm.exception.code, 5)
        with open(named_draft, "rb") as f:
            self.assertEqual(f.read(), b"prior draft\n")
        render_mock.assert_not_called()

    def test_location_refusal_withholds_path_canaries(self):
        rel = ("patients/privatehandlecanary/med/handouts/clinician/"
               "2026-07-16-encountercanary/"
               "2026-07-16__handout-patient__leafcanary.md")
        path = self.materialize(rel)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.rh.seal_location(path, "patient")
        self.assertEqual(cm.exception.code, 5)
        for canary in ("privatehandlecanary", "encountercanary", "leafcanary", self.root):
            self.assertNotIn(canary, err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_entrypoint_converts_unexpected_exception_to_generic_refusal(self):
        err = io.StringIO()
        with mock.patch.object(self.rh, "main",
                               side_effect=PermissionError("private-path-canary")), \
             contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.rh.entrypoint()
        self.assertEqual(cm.exception.code, 5)
        self.assertNotIn("private-path-canary", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_preview_path_is_new_html_outside_handout_lane(self):
        md = self.materialize("scratch/source.md")
        existing = self.materialize("scratch/existing.html", b"keep this copy")
        for path in (existing, self.p("scratch/source.md"), self.p("missing/new.html"),
                     self.p("patients/t/med/handouts/patient/2026-07-16-w/preview.html")):
            with self.subTest(path=path), self.assertRaises(SystemExit):
                self.rh.preflight_preview_path(md, path)
        self.rh.preflight_preview_path(md, self.p("scratch/new.html"))

    def test_patient_preview_stays_with_its_source_person(self):
        md = self.materialize("patients/t/med/handouts/patient/2026-07-16-w/"
                              "2026-07-16__handout-patient__x.md")
        os.makedirs(self.p("patients/t/med/analysis"))
        os.makedirs(self.p("patients/other/med/analysis"))
        self.rh.preflight_preview_path(md, self.p("patients/t/med/analysis/preview.html"))
        for path in (self.p("preview.html"), self.p("patients/other/med/analysis/preview.html"),
                     os.path.join(os.path.dirname(md), "preview.html")):
            with self.subTest(path=path), self.assertRaises(SystemExit):
                self.rh.preflight_preview_path(md, path)
        os.symlink(self.p("patients/other/med/analysis"), self.p("patients/t/linked"))
        with self.assertRaises(SystemExit):
            self.rh.preflight_preview_path(md, self.p("patients/t/linked/preview.html"))
        external = self.materialize("external-care/patients/t/med/analysis/source.md")
        for path in (self.p("preview.html"), self.p("patients/other/med/analysis/preview.html")):
            with self.subTest(path=path), self.assertRaises(SystemExit):
                self.rh.preflight_preview_path(external, path)

    def test_preview_markup_cannot_activate_scripts_or_fetch_assets(self):
        for markup in ('<script>alert(1)</script>', '<img src="https://example.invalid/a.png">',
                       '<p onclick="alert(1)">text</p>', '<style>@import "remote.css";</style>',
                       '<td style="text-align: left;display:none">text</td>',
                       '<a href="javascript:alert(1)">link</a>', '<a href="../source.pdf">link</a>'):
            with self.subTest(markup=markup), self.assertRaises(SystemExit):
                self.rh.PreviewMarkup().feed(markup)
        self.rh.PreviewMarkup().feed('<p class="identity">Text <strong>[A]</strong>.</p>'
                                    '<table><tr><td style="text-align: right;">One</td></tr></table>'
                                    '<a href="https://example.invalid/reference">Reference</a>')

    def test_preview_rejects_declarations_hidden_from_stdlib_tag_callbacks(self):
        for markup in ('<![CDATA[><style>@media screen{#instruction{display:none}}</style>]]>',
                       '<![CDATA[><style>@media screen{p{display:none}}</style>',
                       '<!--><style>#instruction{display:none}</style>-->',
                       '<!---><style>#instruction{display:none}</style>-->',
                       '<!DOCTYPE html>', '<?processing instruction?>'):
            with self.subTest(markup=markup), self.assertRaises(SystemExit):
                self.rh.PreviewMarkup().feed(markup)
        self.rh.PreviewMarkup().feed('<!-- Ordinary template comment. -->\n<p>Visible text.</p>')

    def test_preview_rejects_browser_only_editing_and_visibility_attributes(self):
        for attr in ('contenteditable', 'contenteditable="true"', 'contenteditable="plaintext-only"',
                     'popover', 'inert', 'hidden'):
            with self.subTest(attr=attr), self.assertRaises(SystemExit):
                self.rh.PreviewMarkup().feed('<div %s>Important synthetic instruction.</div>' % attr)

    def test_preview_embeds_design_system_fonts_and_the_exact_pdf(self):
        import base64
        import re
        css = self.rh.embedded_preview_css()
        # The preview wears the Tabularium design system (preview.css), not the PDF's house style.
        self.assertIn("--paper:#FBF8F2", css)
        self.assertIn("--green:#3D5A48", css)
        self.assertIn("'Lora'", css)
        self.assertIn("'Alegreya Sans'", css)
        self.assertNotIn("Spectral", css)
        self.assertNotIn("font-style:italic", css)
        self.assertNotIn("italic.woff2", css)
        # Every font is inlined, so the saved copy makes no request; nothing is left pointing at disk.
        self.assertEqual(css.count("data:font/woff2;base64,"), css.count("@font-face"))
        self.assertGreater(css.count("@font-face"), 0)
        self.assertNotIn("url('fonts/", css)
        rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)                  # prose in comments may say "url()"
        self.assertIsNone(re.search(r"url\(\s*(?!['\"]?data:)", rules))  # every url() is a data: URI
        pdf = b"%PDF-synthetic-exact-bytes\x00\xff"
        doc = self.rh.preview_document('<h1>Document</h1><table><tr><td>One</td></tr></table>',
                                       "A & B", "patient", "en", css, pdf, 'safe.pdf', True)
        self.assertIn("<title>A &amp; B</title>", doc)
        self.assertIn('<p class="preview-status preview-draft">%s</p>' % self.rh.draft_mark("en"), doc)
        saved = self.rh.preview_document("<h1>Document</h1>", "A", "patient", "en", css, pdf, "s.pdf", False)
        self.assertIn('<p class="preview-status">Saved copy</p>', saved)
        self.assertNotIn(self.rh.draft_mark("en"), saved)
        # printing the preview keeps a draft's status line (its draft mark) and drops everything else
        printed = re.search(r"@media print\{(.*?)\n\}", rules, re.S).group(1)
        hidden = [sel.strip() for block in re.findall(r"([^{}]+)\{display:none\}", printed)
                  for sel in block.split(",")]
        self.assertIn(".preview-status:not(.preview-draft)", hidden)
        self.assertNotIn(".preview-status", hidden)
        self.assertNotIn(".preview-draft", hidden)
        self.assertIn("Download PDF", doc)
        self.assertNotIn("Download draft PDF", doc)   # the label stays plain; the status line marks drafts
        self.assertIn('download="safe.pdf"', doc)
        self.assertIn("data:application/pdf;base64," + base64.b64encode(pdf).decode(), doc)
        self.assertLess(doc.index("</table>"), doc.index('class="preview-actions"'))
        self.assertIn("default-src 'none'", doc)
        self.assertNotIn("<script", doc)
        self.assertNotIn("contenteditable", doc)

    def test_handout_stylesheets_use_upright_type(self):
        with open(self.rh.CSS_PATH, encoding="utf-8") as f:
            pdf_css = f.read()
        preview_css = self.rh.embedded_preview_css()
        for stylesheet in (pdf_css, preview_css):
            self.assertNotIn("font-style:italic", stylesheet)
            self.assertNotIn("italic.woff2", stylesheet)

    def test_rendered_notes_do_not_compete_with_bold_instructions(self):
        """Old drafts can wrap whole notes/journal names in emphasis; keep their regular weight."""
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; pure stylesheet tests still run")
        probe = r'''
import json, sys
from weasyprint import CSS, HTML
body = ('<p>ordinary</p><p><strong>instruction</strong></p>'
        '<p><em>legacy</em></p><p class="provenance"><em>provenance</em></p>'
        '<p class="metodyka"><em>methodology</em></p><p class="provenance">plainnote</p>'
        '<ol><li><em>journal</em></li></ol><p class="identity"><em>identity</em></p>'
        '<p><strong><em>nested</em></strong></p>')
results = {}
for sheet in ('handout', 'preview'):
    for audience in ('patient', 'clinician'):
        doc = HTML(string=f'<body class="audience-{audience}">{body}</body>').render(
            stylesheets=[CSS(filename=f'{sys.argv[1]}/{sheet}.css')])
        results[f'{sheet}/{audience}'] = {
            box.text: [box.style['font_weight'], box.style['font_style']]
            for page in doc.pages for box in page._page_box.descendants()
            if getattr(box, 'text', None)}
print(json.dumps(results))
'''
        result = subprocess.run([runtime, "-c", probe, self.rh.HERE], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for variant, runs in json.loads(result.stdout).items():
            with self.subTest(variant=variant):
                self.assertEqual(runs["ordinary"], [400, "normal"])
                for name in ("legacy", "provenance", "methodology", "plainnote", "journal"):
                    self.assertEqual(runs[name], runs["ordinary"], name)
                self.assertGreater(runs["instruction"][0], runs["ordinary"][0])
                self.assertEqual(runs["identity"], runs["instruction"])
                self.assertEqual(runs["nested"], runs["instruction"])

    def test_preview_publication_is_private_and_never_overwrites(self):
        path = self.p("preview.html")
        self.rh.write_preview(path, "first copy")
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.rh.write_preview(path, "second copy")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "first copy")
        self.assertFalse(any(n.startswith(".handout-preview-") for n in os.listdir(self.root)))

    def test_real_draft_preview_download_and_failed_render(self):
        import base64
        import re
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; pure preview tests still run")
        md = self.materialize("source.md", (
            "id: TAB-TST-001J\ndate: 2026-07-16\nlang: en\n\n# Document for review\n\n"
            "Synthetic text only.\n\n| Topic | Detail |\n|:---|---:|\n| One | First item |\n\n"
            "## Next steps\n\n- Review the information.\n- Save the document.\n").encode())
        preview = self.p("preview.html")
        command = [runtime, os.path.join(self.rh.HERE, "render_handout.py"), md,
                   "--draft", "--audience", "patient", "--preview-html", preview]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with open(preview, encoding="utf-8") as f:
            document = f.read()
        download = re.search(r'data:application/pdf;base64,([^" ]+)', document)
        self.assertIsNotNone(download)
        with open(self.p("source.draft.pdf"), "rb") as f:
            self.assertEqual(base64.b64decode(download.group(1)), f.read())
        self.assertIn("<table>", document)
        self.assertIn('style="text-align: left;"', document)
        self.assertIn('style="text-align: right;"', document)
        self.assertIn("<ul>", document)
        # The saved page wears the design-system stylesheet with every font inlined (ADR-0058):
        # a render that handed the preview the PDF's stylesheet, or none, fails here.
        self.assertIn("--green:#3D5A48", document)
        self.assertGreater(document.count("@font-face"), 0)
        self.assertEqual(document.count("@font-face"), document.count("data:font/woff2;base64,"))
        rules = re.sub(r"/\*.*?\*/", "", document, flags=re.S)
        self.assertIsNone(re.search(r"url\(\s*(?!['\"]?data:)", rules))

        bad = self.materialize("bad.md", b"# Missing mandatory metadata\n\nSynthetic text.\n")
        failed_preview = self.p("failed.html")
        command[2] = bad
        command[-1] = failed_preview
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(failed_preview))
        self.assertFalse(os.path.exists(self.p("bad.draft.pdf")))

        # A date the footer cannot print truthfully halts as B0 before anything is written.
        for n, value in enumerate(("2026-02-30", "16.07.2026")):
            dated = self.materialize(f"dated{n}.md", (
                f"id: TAB-TST-001J\ndate: {value}\nlang: en\n\n# Document for review\n\n"
                "Synthetic text only.\n").encode())
            command[2] = dated
            command[-1] = self.p(f"dated{n}.html")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("B0: front-matter date", result.stderr)
            for leaf in (f"dated{n}.html", f"dated{n}.draft.pdf", f"dated{n}.draft.pdf.tmp",
                         f"dated{n}.draft.txt"):
                self.assertFalse(os.path.exists(self.p(leaf)), leaf)

    def test_real_draft_rejects_filename_id_mismatch_before_output(self):
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; pure ID tests still run")
        renderer = os.path.join(self.rh.HERE, "render_handout.py")
        cases = (
            ("matched__TAB-AAA-0015.md", "TAB-AAA-0015", 0),
            ("mismatch__TAB-AAA-0015.md", "TAB-AAA-014F", 5),
            ("legacy.md", "TAB-AAA-0015", 0),
        )
        for leaf, handout_id, expected_rc in cases:
            with self.subTest(leaf=leaf):
                md = self.materialize("ids/2026-07-16__handout-patient__" + leaf, (
                    f"id: {handout_id}\ndate: 2026-07-16\nlang: en\n\n"
                    "# Summary\n\nSynthetic content for renderer verification.\n").encode())
                out = os.path.splitext(md)[0] + ".draft.pdf"
                result = subprocess.run([runtime, renderer, md, "--draft", "--out", out],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected_rc, result.stdout + result.stderr)
                self.assertEqual(os.path.exists(out), expected_rc == 0)

    def _with_id_module(self):
        os.makedirs(self.p("tools/handout_attest"), exist_ok=True)
        shutil.copy(os.path.join(os.path.dirname(__file__), "handout_id.py"),
                    self.p("tools/handout_attest/handout_id.py"))

    def test_front_matter_id_must_carry_its_check_character(self):
        # ADR-0033 point 8: a TAB-shaped front-matter id halts as B0 (exit 3) when it is
        # malformed or its check character is wrong; a valid or non-TAB value passes (B0 presence
        # still owns a missing one)
        self._with_id_module()
        for ok in ("TAB-AAA-0015", "TAB-AAA-014F.r2", "", "legacy-7"):
            self.rh.assert_front_matter_id_valid(ok)
        for bad, expected in (("TAB-AAA-001Z", "'5'"), ("TAB-AAA-014M.r2", "'F'"), ("TAB-AAI-0016", None),
                              ("TAB-AAA-16", None)):
            err = io.StringIO()
            with self.subTest(bad), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                self.rh.assert_front_matter_id_valid(bad)
            self.assertEqual(cm.exception.code, 3)
            self.assertIn("B0: front-matter id", err.getvalue())
            self.assertNotIn(bad, err.getvalue())
            if expected:
                self.assertIn(expected, err.getvalue())

    def test_front_matter_id_check_fails_closed_without_its_module(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            self.rh.assert_front_matter_id_valid("TAB-AAA-0015")
        self.assertEqual(cm.exception.code, 5)

    def test_real_render_halts_on_a_wrong_front_matter_check_character(self):
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; the unit-level ID tests still run")
        renderer = os.path.join(self.rh.HERE, "render_handout.py")
        for handout_id, expected_rc in (("TAB-AAA-0015", 0), ("TAB-AAA-001Z", 3), ("TAB-AAI-0016", 3)):
            with self.subTest(handout_id):
                md = self.materialize("fm/%s/2026-07-16__handout-patient__x.md" % handout_id, (
                    "id: %s\ndate: 2026-07-16\nlang: en\n\n# Summary\n\nSynthetic content.\n"
                    % handout_id).encode())
                out = md[:-3] + ".draft.pdf"
                result = subprocess.run([runtime, renderer, md, "--draft"], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected_rc, result.stdout + result.stderr)
                self.assertEqual(os.path.exists(out), expected_rc == 0)
        # a seal reports the ID before the fact-check gate (rc 3, not the gate's 4); nothing written
        assets = self.p("_templates/handout-assets")
        shutil.copytree(self.rh.HERE, assets)
        self._with_id_module()
        md = self.materialize("patients/t/med/handouts/patient/2026-07-16-w/"
                              "2026-07-16__handout-patient__x.md",
                              b"id: TAB-AAA-001Z\ndate: 2026-07-16\nlang: en\n\n# Summary\n\nSynthetic.\n")
        result = subprocess.run([runtime, os.path.join(assets, "render_handout.py"), md],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(sorted(os.listdir(os.path.dirname(md))), ["2026-07-16__handout-patient__x.md"])

    def test_real_preview_flag_does_not_change_the_pdf(self):
        """The preview is a reading convenience; it must not change the artifact it previews.

        The PDF always renders from handout.css; the preview embeds preview.css on its own. The same
        Markdown must yield byte-identical PDFs with and without the flag. The renderer is
        deterministic, so bytes are the right comparison. The fixture carries the elements a stray
        preview rule would restyle — headings, both list kinds, a blockquote, a link, several
        paragraphs, Polish letters — so a leak into the PDF path changes the bytes.
        """
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; pure preview tests still run")
        data = ("id: TAB-TST-001J\ndate: 2026-07-16\nlang: en\n\n# Document for review\n\n"
                "Synthetic text with **bold**, *italic* and a table.\n\n"
                "A second paragraph with Polish letters: zażółć gęślą jaźń.\n\n"
                "## Next steps\n\n- Review the information.\n- Save the document.\n\n"
                "1. First step.\n2. Second step.\n\n> A quoted note.\n\n"
                "See [the source](https://example.org/).\n\n"
                "| Topic | Detail |\n|:---|---:|\n| One | First item |\n").encode()
        plain = self.materialize("plain/source.md", data)
        with_preview = self.materialize("with/source.md", data)
        renderer = os.path.join(self.rh.HERE, "render_handout.py")
        for md, extra in ((plain, []), (with_preview, ["--preview-html", self.p("with/preview.html")])):
            result = subprocess.run([runtime, renderer, md, "--draft", "--audience", "patient", *extra],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with open(self.p("plain/source.draft.pdf"), "rb") as f:
            without_flag = f.read()
        with open(self.p("with/source.draft.pdf"), "rb") as f:
            with_flag = f.read()
        self.assertEqual(hashlib.sha256(without_flag).hexdigest(), hashlib.sha256(with_flag).hexdigest(),
                         "--preview-html changed the PDF it previews")

    def test_real_sealed_preview_requires_factcheck_and_matches_attestation(self):
        import base64
        import re
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; pure preview tests still run")
        assets = self.p("_templates/handout-assets")
        shutil.copytree(self.rh.HERE, assets)
        os.makedirs(self.p("tools/handout_attest"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "handout_id.py"),
                    self.p("tools/handout_attest/handout_id.py"))
        data = ("id: TAB-TST-001J\ndate: 2026-07-16\nlang: en\n\n"
                "# Document for review\n\nSynthetic text only.\n").encode()
        md = self.materialize("patients/t/med/handouts/patient/2026-07-16-w/"
                              "2026-07-16__handout-patient__x.md", data)
        preview = self.p("patients/t/med/analysis/preview.html")
        os.makedirs(os.path.dirname(preview))
        command = [runtime, os.path.join(assets, "render_handout.py"), md,
                   "--preview-html", preview]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(preview))
        with open(md[:-3] + ".factcheck.md", "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n"
                    "# Synthetic fixture only\n" % hashlib.sha256(data).hexdigest())
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with open(md[:-3] + ".pdf", "rb") as f:
            pdf = f.read()
        with open(md[:-3] + ".attest.json", encoding="utf-8") as f:
            attest = json.load(f)
        with open(preview, encoding="utf-8") as f:
            document = f.read()
        download = re.search(r'data:application/pdf;base64,([^" ]+)', document)
        self.assertEqual(base64.b64decode(download.group(1)), pdf)
        self.assertEqual(attest["md_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(attest["output_sha256"], hashlib.sha256(pdf).hexdigest())
        self.assertIn("Download PDF", document)
        self.assertNotIn("Download draft PDF", document)

    def test_real_draft_marks_every_page_and_a_seal_never(self):
        """A draft skipped the fact-check gate, so every page it prints says so; the seal of the same
        Markdown says nothing of the kind. The mark sits in a page-margin box, so both paginate alike:
        the same page count and, mark aside, the same text on every page."""
        import subprocess
        runtime = os.path.join(os.path.dirname(self.rh.HERE), "..", ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("pinned render environment absent; the pure draft-mark tests still run")
        assets = self.p("_templates/handout-assets")
        shutil.copytree(self.rh.HERE, assets)
        os.makedirs(self.p("tools/handout_attest"))
        shutil.copy(os.path.join(os.path.dirname(__file__), "handout_id.py"),
                    self.p("tools/handout_attest/handout_id.py"))
        renderer = os.path.join(assets, "render_handout.py")
        mark = self.rh.FOOTER["en"]["draft"]
        para = "Synthetic paragraph for pagination only. " * 10
        data = ("id: TAB-TST-001J\ndate: 2026-07-16\nlang: en\n\n# Document for review\n\n"
                + "\n\n".join("## Section %d\n\n%s" % (i, para) for i in range(14)) + "\n").encode()
        seal_md = self.materialize("patients/t/med/handouts/patient/2026-07-16-w/"
                                   "2026-07-16__handout-patient__x.md", data)
        with open(seal_md[:-3] + ".factcheck.md", "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n"
                    "# Synthetic fixture only\n" % hashlib.sha256(data).hexdigest())
        draft_md = self.materialize("drafts/2026-07-16__handout-patient__x.md", data)
        for command in ([runtime, renderer, seal_md], [runtime, renderer, draft_md, "--draft"]):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        probe = ("import json, sys; from pypdf import PdfReader; r = PdfReader(sys.argv[1]); "
                 "print(json.dumps([r.metadata.title] + [p.extract_text() or '' for p in r.pages]))")

        def pages(pdf):
            out = subprocess.run([runtime, "-c", probe, pdf], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            title, *texts = json.loads(out.stdout)
            titles[pdf] = title
            return texts
        titles = {}

        def squeezed(text):
            return " ".join(text.split())

        drafted, sealed = pages(draft_md[:-3] + ".draft.pdf"), pages(seal_md[:-3] + ".pdf")
        self.assertEqual(titles[draft_md[:-3] + ".draft.pdf"], mark + " · Document for review")
        self.assertEqual(titles[seal_md[:-3] + ".pdf"], "Document for review")
        self.assertGreaterEqual(len(drafted), 2, "the fixture must span pages")
        self.assertEqual(len(drafted), len(sealed), "the draft mark changed the pagination")
        for n, (d, s) in enumerate(zip(drafted, sealed), 1):
            with self.subTest(page=n):
                self.assertEqual(squeezed(d).count(mark), 1)
                self.assertNotIn(mark, s)
                self.assertEqual(squeezed(d.replace(mark, "")), squeezed(s))
        # a render fault (B4: a glyph no bundled font covers) writes the text fallback; a draft's opens
        # with the same mark
        faulty = self.materialize("drafts/2026-07-16__handout-patient__y.md",
                                  data.replace(b"for review", "for review ☃".encode()))
        result = subprocess.run([runtime, renderer, faulty, "--draft"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("B4:", result.stderr)
        with open(faulty[:-3] + ".draft.txt", encoding="utf-8") as f:
            self.assertEqual(f.readline(), mark + "\n")
        # ... and a seal's never does: the same fault in a sealed unit writes an unmarked, attested .txt
        faulty_data = data.replace(b"for review", "for review \u2603".encode())
        sealed_faulty = self.materialize("patients/t/med/handouts/patient/2026-07-16-v/"
                                         "2026-07-16__handout-patient__y.md", faulty_data)
        with open(sealed_faulty[:-3] + ".factcheck.md", "w", encoding="utf-8") as f:
            f.write("handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n"
                    "# Synthetic fixture only\n" % hashlib.sha256(faulty_data).hexdigest())
        result = subprocess.run([runtime, renderer, sealed_faulty], capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("B4:", result.stderr)
        self.assertTrue(os.path.isfile(sealed_faulty[:-3] + ".attest.json"))
        with open(sealed_faulty[:-3] + ".txt", encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("# Document for review"), text[:80])
        self.assertNotIn(mark, text)
        # a page-style override in the source that blanks the draft line fails build-QA (B10): no PDF,
        # only the marked text fallback
        blanked = self.materialize("drafts/2026-07-16__handout-patient__z.md", data.replace(
            b"# Document for review\n", b"# Document for review\n\n<style>@page{@top-center{content:none}}</style>\n"))
        result = subprocess.run([runtime, renderer, blanked, "--draft"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("B10:", result.stderr)
        self.assertFalse(os.path.exists(blanked[:-3] + ".draft.pdf"))
        with open(blanked[:-3] + ".draft.txt", encoding="utf-8") as f:
            self.assertEqual(f.readline(), mark + "\n")


class FooterTests(unittest.TestCase):
    """The footer every handout page prints (ADR-0032 points 5 and 8): the prep-date as
    DD.MM.YYYY, the site root after the attribution, and neutral grey text only."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                         "_templates", "handout-assets", "render_handout.py"))
        spec = importlib.util.spec_from_file_location("render_handout_footer_under_test", p)
        cls.rh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rh)

    def test_prep_date_is_numeric_in_every_language(self):
        self.assertEqual(self.rh.fmt_date("2026-01-05"), "05.01.2026")
        for lang, prep in (("pl", "Przygotowano 05.01.2026 · "), ("en", "Prepared 05.01.2026 · ")):
            self.assertIn(prep, self.rh.footer_css("TAB-ZZZ-9990", self.rh.fmt_date("2026-01-05"), lang))

    def test_impossible_date_fails_closed(self):
        for bad in ("2026-13-01", "2026-00-10", "2026-02-30", "2026-09-00", "0000-01-01"):
            with self.assertRaises(ValueError, msg=bad):
                self.rh.fmt_date(bad)

    def test_date_not_written_as_iso_fails_closed(self):
        for bad in ("16.07.2026", "2026-2-03", "2026-09-130", "{{YYYY-MM-DD}}", "YYYY-MM-DD", "draft"):
            with self.assertRaises(ValueError, msg=bad):
                self.rh.fmt_date(bad)

    def test_empty_date_is_left_to_b0(self):
        self.assertEqual(self.rh.fmt_date(""), "")
        self.assertEqual(self.rh.fmt_date(None), "")

    def test_handouts_carry_the_site_address(self):
        # Footer: the site root, every language. Clinician closing note: the clinicians page.
        for lang, strings in self.rh.FOOTER.items():
            self.assertIn("Tabularium", strings["attr"], lang)
            self.assertTrue(strings["attr"].endswith(" · usetabularium.com"), lang)
        import glob
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        paths = sorted(glob.glob(os.path.join(root, "_templates", "handout-clinician*.md")))
        self.assertGreaterEqual(len(paths), 2)
        for path in paths + [os.path.join(root, "_templates", "HANDOUT-RULES.md")]:
            with open(path, encoding="utf-8") as fh:
                self.assertIn("(https://usetabularium.com/clinicians/)", fh.read(), path)

    def test_footer_text_is_neutral_grey(self):
        import re
        for draft in (False, True):
            css = self.rh.footer_css("TAB-ZZZ-9990", "05.01.2026", "pl", draft)
            colours = re.findall(r"color:\s*#([0-9A-Fa-f]{6})\b", css)
            self.assertEqual(len(colours), 3 if draft else 2, css)
            for c in colours:
                self.assertTrue(c[0:2] == c[2:4] == c[4:6], c)

    def test_draft_mark_prints_only_on_a_draft(self):
        # a draft skipped the fact-check gate: each page says so in the top margin; a seal never does
        import re
        for lang, strings in self.rh.FOOTER.items():
            with self.subTest(lang):
                drafted = self.rh.footer_css("TAB-ZZZ-9990", "05.01.2026", lang, draft=True)
                sealed = self.rh.footer_css("TAB-ZZZ-9990", "05.01.2026", lang)
                self.assertIn('@top-center{ content:"%s";' % strings["draft"], drafted)
                self.assertNotIn(strings["draft"], sealed)
                self.assertNotIn("@top", sealed)
                # a mark nobody can see is no mark: the footer's grey, at least the footer's size
                box = re.search(r"@top-center\{([^}]*)\}", drafted).group(1)
                self.assertRegex(box, r"color:#555555;")
                self.assertGreaterEqual(float(re.search(r"(\d+(?:\.\d+)?)pt", box).group(1)), 7)
        self.assertEqual(self.rh.draft_mark("xx"), self.rh.FOOTER["en"]["draft"])  # footer's fallback

    def test_draft_mark_never_trips_build_qa(self):
        # build-QA reads every page of a draft too: a mark it halted or warned on would block every draft
        for lang, strings in self.rh.FOOTER.items():
            self.assertIsNone(self.rh.LEAK.search(strings["draft"]), lang)
            self.assertEqual(self.rh.style_words(strings["draft"]), [], lang)
            # interpolated into CSS content:"…" — nothing that could end the string or the block
            self.assertNotRegex(strings["draft"], r'["\\{}\n]', lang)

    def test_draft_text_fallback_opens_with_the_mark(self):
        tmp = tempfile.mkdtemp(prefix="l15fallback-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        source = "id: TAB-ZZZ-9990\ndate: 2026-01-05\nlang: en\n\n# Title\n\nBody.\n"
        drafted, sealed = os.path.join(tmp, "x.draft.txt"), os.path.join(tmp, "x.txt")
        self.rh.plaintext_fallback(source, drafted, self.rh.draft_mark("en"))
        self.rh.plaintext_fallback(source, sealed)
        with open(drafted, encoding="utf-8") as f:
            self.assertEqual(f.read(), "DRAFT — not fact-checked\n\n# Title\n\nBody.\n")
        with open(sealed, encoding="utf-8") as f:
            self.assertEqual(f.read(), "# Title\n\nBody.\n")


class BuildQaWordTests(unittest.TestCase):
    """Build-QA B7 (split 2026-10-04): a style word only WARNS, an unfinished-draft or private-data
    marker HALTS. The word lists are pure, so they are bitten here without the render environment."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                         "_templates", "handout-assets", "render_handout.py"))
        spec = importlib.util.spec_from_file_location("render_handout_words_under_test", p)
        cls.rh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rh)

    def test_style_words_warn_and_never_halt(self):
        for text in ("grade A", "Grade-b", "graded as mild", "a Vetted source", "reference library",
                     "reference-library", "this handout", "Handouts", "see cal-proc-b", "{: .marker}"):
            self.assertTrue(self.rh.style_words(text), text)
            self.assertIsNone(self.rh.LEAK.search(text), text)

    def test_each_style_class_is_named_once(self):
        found = self.rh.style_words("grade A, grade B, a handout, another handout")
        self.assertEqual(len(found), 2)
        self.assertEqual(len(set(found)), 2)

    def test_leak_markers_halt_and_are_not_style_words(self):
        for text in ("{{imie}}", "TODO later", "fixme", "MUST-FIX open", "⟨confirm⟩ dose",
                     "x.factcheck.md", "⟨withheld:phone⟩", "withheld:phone"):
            self.assertIsNotNone(self.rh.LEAK.search(text), text)
            self.assertEqual(self.rh.style_words(text), [], text)

    def _qa(self, txt, mark):
        with mock.patch.object(self.rh, "pdf_text", return_value=txt), \
                mock.patch.object(self.rh, "page_is_white", return_value=True), \
                mock.patch.object(self.rh, "covered_codepoints", return_value=None):
            return [f for f in self.rh.build_qa("# T\n", "<h1>T</h1>", "unused.pdf", mark=mark)
                    if f.startswith("B10")]

    def test_b10_requires_the_draft_line_on_every_page(self):
        mark = self.rh.draft_mark("en")
        spaced = mark.replace(" ", "   ")                       # pdftotext -layout may widen spaces
        two = "%s\nBody one.\np. 1 / 2\f%s\nBody two.\np. 2 / 2\f" % (spaced, mark)
        self.assertEqual(self._qa(two, mark), [])
        self.assertEqual(self._qa(two.rstrip("\f"), mark), [])  # the pypdf form: no trailing form feed
        self.assertEqual(len(self._qa("%s\nBody one.\np. 1 / 2\fBody two.\np. 2 / 2\f" % mark, mark)), 1)
        self.assertEqual(len(self._qa("", mark)), 1)               # an empty extraction never passes
        self.assertEqual(self._qa("Body.\np. 1 / 1\f", None), [])  # a seal is never asked for it

    def test_ordinary_prose_is_neither(self):
        for text in ("Tresc syntetyczna.", "baseline renal function", "EEG delta wave", "upgrade A1",
                     "medical-legal review", "the withheld dose"):
            self.assertEqual(self.rh.style_words(text), [], text)
            self.assertIsNone(self.rh.LEAK.search(text), text)


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _check_sh_function(name):
    """A function's text from checks/check.sh, so a test runs guard L8's own shell code."""
    import re
    with open(os.path.join(REPO, "checks", "check.sh"), encoding="utf-8") as fh:
        m = re.search(r"^%s\(\)\{.*?^\}$" % re.escape(name), fh.read(), re.S | re.M)
    if not m:
        raise AssertionError("%s not found in checks/check.sh" % name)
    return m.group(0)


class HandoutIdTests(unittest.TestCase):
    """The Python check character (handout_id.py) against ADR-0033's worked values and guard L8's
    shell reference, `tab_checkchar` (ADR-0033 points 2 and 8)."""

    def setUp(self):
        from . import handout_id
        self.H = handout_id

    def test_worked_values(self):
        for payload, char in (("AAA001", "5"), ("AAA014", "F"), ("BBB007", "G"), ("ZZZ999", "A")):
            self.assertEqual(self.H.check_char(payload), char)
        self.assertEqual(self.H.make_id("AAA", 14), "TAB-AAA-014F")
        self.assertIsNone(self.H.id_problem("TAB-AAA-014F.r2"))
        self.assertEqual(self.H.id_problem("TAB-AAA-001Z"), ("wrong check character", "5"))
        for bad in ("TAB-AAI-0016", "TAB-AAA-16", "tab-aaa-0015", "TAB-AAA-0015\n", "TAB-AAA-0015x"):
            self.assertIsNotNone(self.H.id_problem(bad), bad)
        for bad in (("AAI", 1), ("AAA", 0), ("AAA", 1000)):
            with self.assertRaises(ValueError):
                self.H.make_id(*bad)

    def test_every_single_symbol_substitution_changes_the_character(self):
        for pos in range(6):
            for sym in self.H.ALPHABET:
                payload = "AAA014"
                if pos >= 3 and not sym.isdigit() or payload[pos] == sym:
                    continue
                changed = payload[:pos] + sym + payload[pos + 1:]
                self.assertNotEqual(self.H.check_char(changed), "F", changed)

    def test_python_and_guard_l8_agree(self):
        import random
        import subprocess
        rng = random.Random(20261002)
        syms = self.H.ALPHABET
        payloads = ["AAA001", "AAA014", "BBB007", "ZZZ999", "000000", "ZZZ000"] + [
            "".join(rng.choice(syms) for _ in range(3)) + "%03d" % rng.randrange(1000) for _ in range(600)]
        script = _check_sh_function("tab_checkchar") + '\nfor p in "$@"; do tab_checkchar "$p"; echo; done\n'
        out = subprocess.run(["bash", "-c", script, "bash"] + payloads, capture_output=True, text=True,
                             check=True).stdout.split()
        self.assertEqual(out, [self.H.check_char(p) for p in payloads])


ID = "TAB-AAA-0015"


class FrontMatterParityTests(unittest.TestCase):
    """The two readers of a handout's front-matter `id:` — python-markdown's `meta` (the renderer) and
    fsverify.front_matter (next-id, L13's filed_as) — agree on every shape, and the renderer's rule
    (`front_matter_id_verdict`) judges every value."""
    SHAPES = (                                                      # (text, the id both read)
        ("id: %s\ndate: 2026-07-16\n\n# T\n" % ID, ID),
        ("---\nid: %s\n---\n# T\n" % ID, ID),
        ("----\nid: %s\n\n" % ID, ID),
        ("   id:%s\n\n" % ID, ID),
        ("ID: %s  \r\ndate: x\r\n\r\n# T\r\n" % ID, ID),
        ("id: %s\rdate: x\r\r# T\r" % ID, ID),                        # lone CR line ends
        ("date: x\rid: %s\r\r# T\r" % ID, ID),
        ("\x02id: %s\x03\n\n" % ID, ID),                              # STX / ETX dropped
        ("date: x\n    continued\nid: %s\n\n" % ID, ID),
        ("date: x\n\tcontinued\nid: %s\n\n" % ID, ID),
        ("id:\t%s\n" % ID, ID),
        ("id: %s\nid: TAB-AAA-014F\n" % ID, ID),
        ("id: %s" % ID, ID),
        ("id: %s \n" % ID, ID),                                   # trailing NBSP
        ("id: %s\u0085\n" % ID, ID),                                   # trailing NEL
        ("id: %s　\x1f\n" % ID, ID),                               # other Unicode / ASCII separators
        ("id: %s\n" % ID, ID),                                    # NBSP after the colon
        ("id: ​%s\n" % ID, "​" + ID),                         # ZWSP is not whitespace: kept
        ('id: "%s"\n' % ID, '"%s"' % ID),
        ("id: tab-aaa-0015\n", "tab-aaa-0015"),
        ("# Title\nid: %s\n" % ID, ""),
        ("    id: %s\n" % ID, ""),
        ("\tid: %s\n" % ID, ""),
        ("date: x\n\nid: %s\n" % ID, ""),
        ("date: x\n    \nid: %s\n" % ID, ""),
        ("date: x\n     \nid: %s\n" % ID, ""),                    # a line of Unicode space is blank
        ("lang: pl\n...\nid: %s\n" % ID, ""),
        ("lang: pl\n---\nid: %s\n" % ID, ""),
        ("<!-- note -->\nid: %s\n" % ID, ""),
        ("﻿id: %s\n" % ID, ""),                                   # the renderer keeps a BOM: no id
    )
    VALUES = ("", "legacy-7", "AAA-0015", ID, "TAB-AAA-014F.r2", "TAB-AAA-001Z", '"TAB-AAA-001Z"',
              "'%s'" % ID, "`%s`" % ID, "<%s>" % ID, "tab-aaa-0015", "Tab-AAA-0015", "​" + ID,
              "﻿" + ID, "ТАВ-AAA-0015", "TAB‐AAA‐0015",
              "ＴＡＢ-AAA-0015", "TAB-AAI-0016", "Karta żółta")

    def test_both_readers_agree(self):
        import subprocess
        d = tempfile.mkdtemp(prefix="fmparity-")
        self.addCleanup(shutil.rmtree, d, True)
        paths = []
        for n, (text, _) in enumerate(self.SHAPES):
            p = os.path.join(d, "%02d.md" % n)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            paths.append(p)
        ported = [(_owner.read_front_matter(p).get("id") or [""])[0] for p in paths]
        self.assertEqual(ported, [want for _, want in self.SHAPES])
        runtime = os.path.join(REPO, ".venv-render", "bin", "python")
        if not os.path.isfile(runtime):
            self.skipTest("render environment absent: python-markdown's own reading not compared")
        probe = ("import json, sys, markdown\nout = []\nfor p in sys.argv[1:]:\n"
                 "    md = markdown.Markdown(extensions=['meta'])\n"
                 "    md.convert(open(p, encoding='utf-8', newline='').read())\n"
                 "    v = getattr(md, 'Meta', {}).get('id') or ['']\n"
                 "    out.append(v[0].strip())\nprint(json.dumps(out))\n")
        real = json.loads(subprocess.run([runtime, "-c", probe] + paths, capture_output=True, text=True,
                                         check=True).stdout)
        self.assertEqual(real, ported)

    def test_renderer_rule_judges_every_value(self):
        from . import handout_id
        python = [handout_id.front_matter_id_verdict(v) for v in self.VALUES]
        self.assertEqual(python[:6], ["", "", "", "ok", "ok", "5"])
        self.assertEqual(set(python[6:]), {"malformed"})


class NextIdTests(unittest.TestCase):
    """`python3 -m tools.handout_attest next-id <handle>` (ADR-0033 point 8): read-only,
    the next number after the highest in use, the tag INDEX.md uses."""

    def setUp(self):
        self.t = Tree()
        self.addCleanup(shutil.rmtree, self.t.root, True)
        self.t.write("med/handouts/INDEX.md", "| ID |\n|---|\n| TAB-AAA-0015 |\n| TAB-AAA-002G |\n")

    def ids(self, **kw):
        return CLI.next_ids(self.t.root, "testperson", **kw)

    def stop(self, want, **kw):
        with self.assertRaises(CLI._NextIdStop) as cm:
            self.ids(**kw)
        self.assertIn(want, str(cm.exception))

    def test_next_after_the_highest_in_use(self):
        self.assertEqual(self.ids(), (["TAB-AAA-003V"], []))
        self.t.write("med/handouts/patient/2026-07-16-w/2026-07-16__handout-patient__x__TAB-AAA-0046.md",
                     "# x\n")
        self.t.write("med/analysis/drafts/d.md", "id: TAB-AAA-006W\ndate: 2026-07-16\n\n# d\n")
        self.t.write("med/analysis/notes.md", "# notes\n\nmentions TAB-AAA-0099 in prose only\n")
        ids, notes = self.ids(count=3)
        self.assertEqual(ids, ["TAB-AAA-0077", "TAB-AAA-008J", "TAB-AAA-009X"])
        self.assertEqual(notes, [])
        from . import handout_id
        for i in ids:
            self.assertIsNone(handout_id.id_problem(i))

    def test_writes_nothing(self):
        before = sorted(os.walk(self.t.root))
        self.ids(count=2)
        self.assertEqual(sorted(os.walk(self.t.root)), before)

    def test_tag_rules(self):
        self.t.write("med/handouts/INDEX.md", "| ID |\n|---|\n| — |\n")
        self.stop("pass --tag")
        self.assertEqual(self.ids(tag="AAA")[0], ["TAB-AAA-0015"])
        self.stop("three Crockford symbols", tag="AAI")
        self.t.write("med/handouts/INDEX.md", "| TAB-AAA-0015 |\n")
        self.stop("differs from the tag", tag="BBB")
        self.t.write("med/handouts/INDEX.md", "| TAB-AAA-0015 |\n| TAB-BBB-007G |\n")
        self.stop("more than one person tag")

    def test_notes_name_one_decision(self):
        self.t.write("med/handouts/INDEX.md", "| TAB-AAA-0015 |\n| TAB-AAA-002Z |\n")
        self.t.write("med/analysis/drafts/d.md", "id: TAB-BBB-007G\n\n# foreign\n")
        ids, notes = self.ids()
        self.assertEqual(ids, ["TAB-AAA-003V"])
        self.assertEqual(len(notes), 2)
        self.assertIn("TAB-AAA-002Z", notes[0])
        self.assertIn("supersede", notes[0])
        self.assertIn("whose document", notes[1])

    def test_unclean_values_are_noted_and_still_counted(self):
        # a quoted or hidden-character ID still holds a number: it is counted and named in a note
        self.t.write("med/analysis/drafts/q.md", 'id: "TAB-AAA-0077"\n\n# q\n')
        ids, notes = self.ids()
        self.assertEqual(ids, ["TAB-AAA-008J"])
        self.assertEqual(len(notes), 1)
        self.assertIn("not a clean stable ID", notes[0])
        self.t.write("med/analysis/drafts/z.md", "id: ​TAB-AAA-009X\n\n# z\n")
        self.assertEqual(self.ids()[0], ["TAB-AAA-0103"])

    def test_what_is_skipped_is_said(self):
        self.t.write("med/handouts/INDEX.md", "| TAB-AAA-0015 |\n| TAB-AAA-16 |\n"
                     "> `__TAB-<PPP>-<NNN><C>` template prose is not an ID\n")
        self.t.write("med/analysis/drafts/2026-07-16__draft__TAB-AAA-0046.md", "# no front matter\n")
        ids, notes = self.ids()
        self.assertEqual(ids, ["TAB-AAA-005H"])        # the file-name-only ID is counted
        self.assertEqual(len(notes), 2, notes)
        self.assertIn("TAB-AAA-16", notes[0])
        self.assertIn("only in its file name", notes[1])
        other = tempfile.mkdtemp(prefix="nid-analysis-")
        self.addCleanup(shutil.rmtree, other, True)
        shutil.rmtree(os.path.join(self.t.pdir, "med", "analysis"))
        os.symlink(other, os.path.join(self.t.pdir, "med", "analysis"))
        self.assertTrue(any("is a link and was not read" in n for n in self.ids()[1]))

    def test_refusals(self):
        self.stop("--count", count=0)
        with self.assertRaises(CLI._NextIdStop):
            CLI.next_ids(self.t.root, "../x")
        os.remove(os.path.join(self.t.hout, "INDEX.md"))
        self.stop("no INDEX.md")
        other = tempfile.mkdtemp(prefix="nid-")
        self.addCleanup(shutil.rmtree, other, True)
        with open(os.path.join(other, "INDEX.md"), "w") as fh:
            fh.write("| TAB-AAA-0015 |\n")
        os.symlink(os.path.join(other, "INDEX.md"), os.path.join(self.t.hout, "INDEX.md"))
        self.stop("no INDEX.md")
        os.remove(os.path.join(self.t.hout, "INDEX.md"))
        shutil.rmtree(self.t.hout)
        os.symlink(other, self.t.hout)
        self.stop("no handout lane")
        os.remove(self.t.hout)
        os.makedirs(self.t.hout)
        with open(os.path.join(self.t.hout, "INDEX.md"), "w") as fh:
            fh.write("| TAB-AAA-9982 |\n")
        self.stop("pass 999", count=2)

    def test_cli_prints_ids_only(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = CLI.main(["--root", self.t.root, "next-id", "testperson", "--count", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "TAB-AAA-003V\nTAB-AAA-0046\n")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = CLI.main(["--root", self.t.root, "next-id", "nobody"])
        self.assertEqual(code, 2)
        self.assertNotIn(self.t.root, err.getvalue())


if __name__ == "__main__":
    unittest.main()
