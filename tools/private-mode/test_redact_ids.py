#!/usr/bin/env python3
"""Test suite for redact_ids.py / approve_redaction.py — SYNTHETIC data only (no real person's
identifier, no real scans). stdlib unittest so both of these are real, discovered test runs:

    python3 tools/private-mode/test_redact_ids.py
    python3 -m unittest tools.private-mode.test_redact_ids

The second form is a dotted module path containing a hyphen ("private-mode"), which can never be
valid `import` *statement* syntax — but unittest's loader resolves names via
`importlib.import_module()`, whose path-based finder matches each dotted component against
filesystem entries by literal string, not by parsing it as a Python identifier. With
`tools/__init__.py` and `tools/private-mode/__init__.py` present (both packages now regular),
that resolution succeeds — verified empirically, not merely assumed; see those files' docstrings
and the SOP (README.md) for the same note.

Coverage:
  * SchemeTests / DetectionTests — the original pure-logic coverage (DOB->prefix, checksum,
    detect() rules, date exclusion, rules-toggle, strong_hits), semantics unchanged.
  * PixelBurnTest — the ImageMagick rectangle-burn geometry probe; auto-skipped with an explicit
    reason if ImageMagick is absent (the one permitted skip — it needs a real binary; every
    failure-path test below runs with subprocess entirely mocked, so it never skips).
  * RunCheckedTests — fault injection at the checked-external-command layer: nonzero exit,
    missing/empty/stale expected output, executable not found.
  * CliValidationTests — malformed DOB, empty/unknown rules, non-positive dpi/max-iters,
    overlapping/nested/aliased directories, pre-existing --log path, missing executables.
  * PromotionTests — atomic directory promotion: fresh promote, superseding a stale prior set
    (never merged, never deleted, unreachable from the live path afterward).
  * PipelineOrchestrationTests — process_pdf()/run_pipeline() end-to-end with every external tool
    call routed through a synthetic in-process shim (no real poppler/tesseract/ImageMagick
    needed): render/OCR/mask-burn/identify/OSD/pdfinfo failures, a command that exits 0 without
    creating its output, a stale pre-existing output at the destination path, a shorter rerun
    with a stale longer prior set present, page-numbering gap/mismatch, every fail-closed flag,
    and the resulting exit code / manifest / hash contract for each.
  * ApprovalTests — approve_redaction.py: clean approval, rejection on doc/page error, rejection
    on unresolved flags (and acceptance with --accept-flagged), rejection on a tampered artifact
    (hash mismatch = approval-state forgery defense), and promotion/supersede behavior.

Synthetic identity used throughout: DOB 1901-02-03 -> prefix 010203; a valid-checksum synthetic
ID 01020312340; the textbook checksum example 44051401359; label token 'IDNR'.
"""
import contextlib
import glob
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redact_ids as R
import approve_redaction as A
import verify_approved as V

PREFIX = '010203'   # from synthetic DOB 1901-02-03
LABEL = 'IDNR'
SYN_RUN = '20260101T000000Z-0000abcd'  # a syntactically-valid synthetic run id (RUN_ID_RE)


def stage_valid_doc(redacted_root, label='doc1', flags=None, npages=1, **man_over):
    """Stage a FULL, strictly schema-valid AWAITING_OPERATOR document under a valid opaque doc id
    (doc-<16 hex> from a synthetic label). Returns the doc directory. `man_over` overrides top-level
    manifest fields for negative tests. Reused by ApprovalTests / VerifyApprovedTests / crash tests."""
    input_sha = hashlib.sha256(label.encode()).hexdigest()
    doc_id = 'doc-' + input_sha[:16]
    d = os.path.join(redacted_root, doc_id)
    os.makedirs(d, exist_ok=True)
    flags = list(flags or [])
    pages = []
    for n in range(1, npages + 1):
        pf = os.path.join(d, 'page-%02d.png' % n)
        with open(pf, 'wb') as f:
            f.write(('REDACTED-PAGE-%d-BYTES' % n).encode())
        page = dict(page=n, w=600, h=800, n_words=25, label_seen=False, reasons=[],
                    n_masked=0, iters=0, converged=('MASK_VERIFY_FAILED' not in flags),
                    flags=list(flags), sha256=R._sha256_file(pf), osd_deg=0, osd_conf=5.0)
        if 'OSD_UNRELIABLE' in flags:
            page['osd_unreliable'] = True
        pages.append(page)
    man = dict(schema_version=R.SCHEMA_VERSION, kind='document-manifest', tool=R.TOOL_NAME,
               tool_version=R.TOOL_VERSION, run_id=SYN_RUN, doc=doc_id, input_sha256=input_sha,
               created_utc=R._utcnow(), n_pages=npages, expected_pages=None, pages=pages,
               error=None, notes=[], state='AWAITING_OPERATOR')
    man.update(man_over)
    R._atomic_write_json(os.path.join(d, 'manifest.json'), man)
    return d


# Folder names an operator could hand-rename or misfile into a --redacted/--approved root: one
# carrying the synthetic checksum-valid identifier past its 24th character, one that looks opaque
# for 20 characters and then carries more. Discovery picks both up and validation rejects both; no
# fragment of either may reach stdout.
NON_OPAQUE_FOLDERS = ('synthetic-private-label-44051401359', 'doc-' + '0' * 16 + '4405')
NON_OPAQUE_FRAGMENTS = ('synthetic', 'private-label', '44051401359', 'doc-' + '0' * 16)


def stage_non_opaque_folders(root, state_file):
    """Stage NON_OPAQUE_FOLDERS under `root`, each holding an empty-object `state_file`
    (manifest.json or approval.json) — the shape directory discovery accepts."""
    for name in NON_OPAQUE_FOLDERS:
        os.makedirs(os.path.join(root, name))
        R._atomic_write_json(os.path.join(root, name, state_file), {})


def W(text, left, top, width=90, height=30, conf=95, line=('1', '1', '1')):
    return dict(text=text, conf=conf, left=left, top=top, width=width, height=height, line_key=line)


def reasons(hits):
    return sorted({h['reason'] for h in hits})


def detect(words, rules=R.DEFAULT_RULES, label_token=LABEL):
    return R.detect(words, 2000, 2000, PREFIX, rules=rules, label_token=label_token)


# ---------------------------------------------------------------------------
# Pure logic — unchanged semantics, converted from the original ad-hoc asserts
# ---------------------------------------------------------------------------
class SchemeTests(unittest.TestCase):
    def test_dob_to_prefix(self):
        self.assertEqual(R._pl_id_prefix('1901-02-03'), '010203')
        self.assertEqual(R._pl_id_prefix('2004-03-05'), '042305')
        self.assertEqual(R._pl_id_prefix('1885-12-31'), '859231')

    def test_dob_century_outside_scheme_raises(self):
        with self.assertRaises(ValueError):
            R._pl_id_prefix('1750-01-01')

    def test_checksum(self):
        self.assertTrue(R._pl_id_checksum_ok('44051401359'))
        self.assertFalse(R._pl_id_checksum_ok('44051401358'))
        self.assertTrue(R._pl_id_checksum_ok('01020312340'))  # synthetic identity's valid ID
        self.assertFalse(R._pl_id_checksum_ok('12345678901'))
        self.assertFalse(R._pl_id_checksum_ok('2026070412'))


class DetectionTests(unittest.TestCase):
    def test_prefix_rule_across_split_tokens(self):
        h, lab, lnc = detect([W(PREFIX, 100, 100), W('00000', 200, 100)])
        self.assertTrue(any(x.startswith('id-prefix') for x in reasons(h)))

    def test_label_proximity_right(self):
        h, lab, lnc = detect([W(LABEL + ':', 100, 100, width=110), W('01020312340', 230, 100, width=260)])
        self.assertTrue(lab)
        self.assertIn('id-label-proximity', reasons(h))

    def test_label_proximity_below(self):
        h, lab, lnc = detect([W(LABEL, 100, 100), W('01020312340', 100, 145, width=260)])
        self.assertIn('id-label-proximity', reasons(h))

    def test_label_no_candidate_fails_closed(self):
        h, lab, lnc = detect([W(LABEL, 100, 100), W('brak', 300, 100)]
                             + [W(f'x{i}', 100, 900 + i * 40) for i in range(25)])
        self.assertTrue(lab)
        self.assertTrue(lnc)

    def test_true_negatives(self):
        h, lab, lnc = detect([W('Hemoglobina', 100, 100), W('13.5', 260, 100),
                              W('Glukoza', 100, 200), W('90', 260, 200),
                              W('Numer', 100, 800), W('probki', 200, 800),
                              W('20260704123', 320, 800, width=260)])
        self.assertFalse(h)
        self.assertFalse(lab)

    def test_checksum_rule_alone_and_strong_hits(self):
        h, lab, lnc = detect([W('44051401359', 500, 500, width=260)])
        self.assertIn('id-checksum', reasons(h))
        self.assertGreaterEqual(len(R.strong_hits(h)), 1)

    def test_fuzzy_prefix_ocr_confusables(self):
        h, lab, lnc = detect([W('O1O2O3OOOOO', 500, 500, width=260)])
        self.assertTrue(any(x.startswith('id-prefix') for x in reasons(h)))

    def test_strong_hits_excludes_weak_reasons(self):
        self.assertEqual(R.strong_hits([{'box': [0, 0, 1, 1], 'reason': 'id-label-proximity'}]), [])

    def test_date_words_never_the_identifier(self):
        self.assertTrue(R.is_date_word('03.02.1901'))
        self.assertTrue(R.is_date_word('1901-02-03'))
        self.assertTrue(R.is_date_word('03.02.1901r.'))
        self.assertFalse(R.is_date_word('01020312340'))
        self.assertFalse(R.is_date_word('010203-12340'))
        h, lab, lnc = detect([W('ur.', 100, 100), W('1901-02-03', 160, 100, width=200),
                              W('106', 380, 100), W('125', 460, 100), W('12345', 540, 100)])
        self.assertFalse(h, f'DOB + neighbor digits must not mask, got {reasons(h)}')

    def test_unseparated_identifier_still_fires(self):
        h, lab, lnc = detect([W('01020312340', 100, 100, width=260)])
        self.assertTrue(any(x.startswith('id-prefix') for x in reasons(h)))

    def test_rules_toggle_no_checksum(self):
        h, lab, lnc = detect([W('44051401359', 500, 500, width=260)], rules=('prefix', 'label'))
        self.assertFalse(h)

    # A83: an identifier split across two OCR lines — the prefix rule joins neighbouring lines
    def test_identifier_split_across_lines_on_one_row(self):
        h, lab, lnc = detect([W('010203', 100, 100, line=('1', '1', '1')),
                              W('12340', 400, 100, line=('2', '1', '1'))])
        self.assertIn('id-prefix', reasons(h))
        self.assertEqual(len({tuple(x['box']) for x in h}), 2, 'one mask per line part')

    def test_identifier_wrapped_to_the_next_line(self):
        h, lab, lnc = detect([W('Nr', 100, 100, line=('1', '1', '1')),
                              W('0102031', 1500, 100, line=('1', '1', '1')),
                              W('2340', 100, 140, line=('1', '1', '2')),
                              W('dalej', 300, 140, line=('1', '1', '2'))])
        self.assertIn('id-prefix', reasons(h))

    def test_cross_line_join_is_prefix_only(self):
        # a checksum-valid number split over two lines: no prefix, so no join (false-hit control)
        h, lab, lnc = detect([W('4405140', 100, 100, line=('1', '1', '1')),
                              W('1359', 400, 100, line=('2', '1', '1'))])
        self.assertFalse(h, reasons(h))

    def test_distant_lines_are_not_joined(self):
        h, lab, lnc = detect([W('010203', 100, 100, line=('1', '1', '1')),
                              W('12340', 900, 700, line=('2', '1', '1'))])
        self.assertFalse(h, reasons(h))

    # A89: the checksum rule's OCR-confusable pass, within one identifier-length word
    def test_fuzzy_checksum_on_a_misread_identifier(self):
        h, lab, lnc = detect([W('44O5l4O1359', 500, 500, width=260)])   # three confusables
        self.assertEqual(reasons(h), ['id-checksum-fuzzy'])
        self.assertGreaterEqual(len(R.strong_hits(h)), 1)

    def test_fuzzy_checksum_negatives(self):
        self.assertFalse(detect([W('44O5l4OI359', 500, 500, width=260)])[0])  # four confusables
        self.assertFalse(detect([W('SOlOSOlOSOl', 500, 500, width=260)])[0])  # no digit read at all
        self.assertFalse(detect([W('44O5l4O1359', 500, 500, width=260)],
                                rules=('prefix', 'label', 'lowconf'))[0])     # checksum rule off
        h, lab, lnc = detect([W('44051401359', 500, 500, width=260)])
        self.assertEqual(reasons(h), ['id-checksum'], 'a clean read stays the strict rule only')

    def test_fuzzy_checksum_stays_within_one_word(self):
        # letters of a neighbouring word must not complete a window (false-hit control)
        h, lab, lnc = detect([W('Kowalski', 100, 100), W('4051401359', 300, 100, width=240)])
        self.assertNotIn('id-checksum-fuzzy', reasons(h))

    # A80: identifier-shaped tokens below the OCR confidence floor are masked and marked
    def test_low_confidence_identifier_is_caught(self):
        h, lab, lnc = detect([W('01020312340', 500, 500, width=260, conf=20)])
        self.assertEqual(reasons(h), ['id-low-confidence'])
        self.assertGreaterEqual(len(R.strong_hits(h)), 1)

    def test_low_confidence_identifier_shaped_token_is_caught(self):
        # misread digits match neither prefix nor checksum, but the token is identifier-shaped
        h, lab, lnc = detect([W('7l2O45983l2', 500, 500, width=260, conf=15)])
        self.assertEqual(reasons(h), ['id-low-confidence'])

    def test_low_confidence_prefix_part_joins_a_confident_line(self):
        h, lab, lnc = detect([W('010203', 100, 100, conf=12), W('12340', 220, 100)])
        self.assertIn('id-low-confidence', reasons(h))

    def test_low_confidence_negatives(self):
        for token in ('IIlIlIllII', '1901-02-03', '12345678', '13.5', 'mg/dl'):
            h, lab, lnc = detect([W(token, 500, 500, width=260, conf=15)])
            self.assertFalse(h, f'{token!r} must not be held: {reasons(h)}')

    def test_low_confidence_rule_off_ignores_them(self):
        h, lab, lnc = detect([W('01020312340', 500, 500, width=260, conf=20)],
                             rules=('prefix', 'checksum', 'label'))
        self.assertFalse(h)


class PixelBurnTest(unittest.TestCase):
    """The one skip that needs a real external binary (ImageMagick). Every other test in this file
    runs with subprocess fully mocked; a handful of failure-path bites are still
    environment-conditional and self-skip with an explicit reason — the FIFO-refusal bites where
    `os.mkfifo` is unavailable, and the permission-bit bites when running as root."""

    def test_rectangle_burn_geometry(self):
        if not (shutil.which('magick') or (shutil.which('convert') and shutil.which('identify'))):
            self.skipTest('ImageMagick not found on PATH (magick, or convert+identify) — '
                          'geometry probe needs a real binary; every other test in this suite does not')
        R.IM = R._im()
        with tempfile.TemporaryDirectory() as tmp:
            img = os.path.join(tmp, 't_geo.png')
            out = os.path.join(tmp, 't_geo_out.png')
            subprocess.run(R.IM['convert'] + ['-size', '300x300', 'xc:white', img], check=True)
            R.burn(img, [[100, 100, 200, 150]], out)

            def px(p, x, y):
                return subprocess.run(R.IM['convert'] + [p, '-format', f'%[pixel:p{{{x},{y}}}]', 'info:'],
                                      capture_output=True, text=True).stdout.strip()

            def blk(s): return 'black' in s or 'gray(0)' in s or 'srgb(0,0,0)' in s
            def wht(s): return 'white' in s or 'gray(255)' in s

            inside, outside, above = px(out, 150, 125), px(out, 10, 10), px(out, 150, 50)
            self.assertTrue(blk(inside) and wht(outside) and wht(above), (inside, outside, above))


# ---------------------------------------------------------------------------
# run_checked() fault injection — the checked-external-command layer
# ---------------------------------------------------------------------------
class RunCheckedTests(unittest.TestCase):
    def test_nonzero_exit_raises_tool_error(self):
        with mock.patch('redact_ids.subprocess.run',
                        return_value=subprocess.CompletedProcess([], 1, '', '')):
            with self.assertRaises(R.ToolError) as ctx:
                R.run_checked(['fake-tool'], stage='fake')
            self.assertEqual(ctx.exception.stage, 'fake')
            self.assertIn('nonzero exit', ctx.exception.reason)

    def test_missing_output_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, 'never-written.png')
            with mock.patch('redact_ids.subprocess.run',
                            return_value=subprocess.CompletedProcess([], 0, '', '')):
                with self.assertRaises(R.ToolError) as ctx:
                    R.run_checked(['fake-tool'], stage='fake', outputs=[missing])
                self.assertIn('missing', ctx.exception.reason)

    def test_empty_output_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, 'empty.png')
            open(empty, 'wb').close()
            with mock.patch('redact_ids.subprocess.run',
                            return_value=subprocess.CompletedProcess([], 0, '', '')):
                with self.assertRaises(R.ToolError) as ctx:
                    R.run_checked(['fake-tool'], stage='fake', outputs=[empty])
                self.assertIn('empty', ctx.exception.reason)

    def test_stale_preexisting_output_raises(self):
        """A command that returns 0 but writes nothing must not be fooled by a file that
        happened to already exist at the expected path (the exact 'rc=0, no real output'
        fault class named in the handover) — freshness catches it even when existence+size
        checks alone would not."""
        with tempfile.TemporaryDirectory() as tmp:
            stale = os.path.join(tmp, 'stale.png')
            with open(stale, 'wb') as f:
                f.write(b'leftover-from-a-previous-run')
            old = R.time.time() - 3600
            os.utime(stale, (old, old))
            with mock.patch('redact_ids.subprocess.run',
                            return_value=subprocess.CompletedProcess([], 0, '', '')):
                with self.assertRaises(R.ToolError) as ctx:
                    R.run_checked(['fake-tool'], stage='fake', outputs=[stale])
                self.assertIn('stale', ctx.exception.reason)

    def test_executable_not_found_raises(self):
        with mock.patch('redact_ids.subprocess.run', side_effect=FileNotFoundError()):
            with self.assertRaises(R.ToolError) as ctx:
                R.run_checked(['does-not-exist'], stage='fake')
            self.assertIn('not found', ctx.exception.reason)

    def test_timeout_raises(self):
        with mock.patch('redact_ids.subprocess.run',
                        side_effect=subprocess.TimeoutExpired(cmd=['x'], timeout=1)):
            with self.assertRaises(R.ToolError) as ctx:
                R.run_checked(['fake-tool'], stage='fake')
            self.assertIn('timed out', ctx.exception.reason)

    def test_error_message_never_carries_stdout(self):
        """Sanitized-logging contract: ToolError's message must never include the raw
        stdout/stderr text (which could carry OCR'd digits) — only stage + reason category."""
        SENSITIVE = 'stdout-would-carry-ocr-text-or-digits-01020312340'
        with mock.patch('redact_ids.subprocess.run',
                        return_value=subprocess.CompletedProcess([], 1, SENSITIVE, SENSITIVE)):
            with self.assertRaises(R.ToolError) as ctx:
                R.run_checked(['fake-tool'], stage='fake')
            self.assertNotIn(SENSITIVE, str(ctx.exception))


# ---------------------------------------------------------------------------
# CLI validation
# ---------------------------------------------------------------------------
def _args(**over):
    d = dict(inbox='/tmp/x', render='/tmp/r', work='/tmp/w', redacted='/tmp/x2',
             log='/tmp/nonexistent-log.json', dob='1901-02-03', scheme='pl-id',
             label_token=None, rules=('prefix', 'checksum', 'label'), dpi=300,
             lang='pol', max_iters=5)
    d.update(over)
    return argparse_namespace(d)


def argparse_namespace(d):
    class NS: pass
    ns = NS()
    for k, v in d.items():
        setattr(ns, k, v)
    return ns


class CliValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inbox = os.path.join(self.tmp.name, 'inbox'); os.makedirs(self.inbox)
        self.render = os.path.join(self.tmp.name, 'render'); os.makedirs(self.render)
        self.work = os.path.join(self.tmp.name, 'work'); os.makedirs(self.work)
        self.redacted = os.path.join(self.tmp.name, 'redacted'); os.makedirs(self.redacted)
        self.log = os.path.join(self.tmp.name, 'run-log.json')
        _langs_installed(self)

    def _base(self, **over):
        d = dict(inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
                 log=self.log, dob='1901-02-03', scheme='pl-id', label_token=None,
                 rules=('prefix', 'checksum', 'label'), dpi=300, lang='pol', max_iters=5)
        d.update(over)
        return argparse_namespace(d)

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_valid_args_pass(self, _which):
        self.assertEqual(R.validate_args(self._base()), [])

    def test_malformed_dob_rejected(self):
        errs = R.validate_args(self._base(dob='not-a-date'))
        self.assertTrue(any('YYYY-MM-DD' in e for e in errs))

    def test_dob_bad_century_rejected_without_uncaught_exception(self):
        # this exact case used to raise an unsanitized ValueError out of _pl_id_prefix
        errs = R.validate_args(self._base(dob='1750-01-01'))
        self.assertTrue(any('century' in e or 'valid date' in e for e in errs))
        for e in errs:
            self.assertNotIn('1750-01-01', e)  # DOB value itself never echoed

    def test_empty_rules_rejected(self):
        errs = R.validate_args(self._base(rules=()))
        self.assertTrue(any('rules' in e for e in errs))

    def test_unknown_rule_token_rejected(self):
        errs = R.validate_args(self._base(rules=('prefix', 'bogus')))
        self.assertTrue(any('unknown' in e for e in errs))

    def test_nonpositive_dpi_rejected(self):
        errs = R.validate_args(self._base(dpi=0))
        self.assertTrue(any('dpi' in e for e in errs))

    def test_nonpositive_max_iters_rejected(self):
        errs = R.validate_args(self._base(max_iters=-1))
        self.assertTrue(any('max-iters' in e for e in errs))

    def test_overlapping_directories_rejected(self):
        errs = R.validate_args(self._base(render=self.work))
        self.assertTrue(any('same path' in e for e in errs))

    def test_nested_directories_rejected(self):
        nested = os.path.join(self.inbox, 'nested-render')
        errs = R.validate_args(self._base(render=nested))
        self.assertTrue(any('parent directory' in e for e in errs))

    def test_preexisting_log_path_rejected(self):
        with open(self.log, 'w') as f:
            f.write('{}')
        errs = R.validate_args(self._base())
        self.assertTrue(any('already exists' in e for e in errs))

    def test_missing_inbox_rejected(self):
        errs = R.validate_args(self._base(inbox=os.path.join(self.tmp.name, 'nope')))
        self.assertTrue(any('inbox' in e for e in errs))

    @mock.patch('shutil.which', return_value=None)
    def test_missing_executables_rejected(self, _which):
        errs = R.validate_args(self._base())
        self.assertTrue(any('pdftoppm' in e for e in errs))
        self.assertTrue(any('tesseract' in e for e in errs))


# ---------------------------------------------------------------------------
# Atomic directory promotion
# ---------------------------------------------------------------------------
class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_fresh_promote_no_prior(self):
        stage = os.path.join(self.tmp.name, 'stage'); os.makedirs(stage)
        with open(os.path.join(stage, 'page-01.png'), 'wb') as f:
            f.write(b'x')
        final = os.path.join(self.tmp.name, 'out', 'doc1')
        superseded = R._promote_dir(stage, final)
        self.assertIsNone(superseded)
        self.assertTrue(os.path.isfile(os.path.join(final, 'page-01.png')))

    def test_stale_prior_is_superseded_not_merged_not_deleted(self):
        """The core named bug: a shorter rerun must never leave a prior run's extra trailing
        pages reachable from the live path, and must never delete the old evidence outright."""
        final = os.path.join(self.tmp.name, 'out', 'doc1')
        os.makedirs(final)
        for n in (1, 2, 3, 4, 5):
            with open(os.path.join(final, f'page-{n:02d}.png'), 'wb') as f:
                f.write(f'old-page-{n}'.encode())

        stage = os.path.join(self.tmp.name, 'stage'); os.makedirs(stage)
        for n in (1, 2, 3):
            with open(os.path.join(stage, f'page-{n:02d}.png'), 'wb') as f:
                f.write(f'new-page-{n}'.encode())

        superseded = R._promote_dir(stage, final)

        self.assertIsNotNone(superseded)
        live = sorted(os.listdir(final))
        self.assertEqual(live, ['page-01.png', 'page-02.png', 'page-03.png'],
                         'stale page-04/05 must not be reachable from the live path')
        with open(os.path.join(final, 'page-01.png'), 'rb') as f:
            self.assertEqual(f.read(), b'new-page-1')
        # old content preserved, just unreachable from the live path (never deleted)
        self.assertTrue(os.path.isdir(superseded))
        self.assertEqual(sorted(os.listdir(superseded)),
                         [f'page-{n:02d}.png' for n in (1, 2, 3, 4, 5)])


# ---------------------------------------------------------------------------
# End-to-end pipeline orchestration, entirely mocked subprocess — no real
# poppler/tesseract/ImageMagick required, so this never skips in CI.
# ---------------------------------------------------------------------------
def _write_tsv(path, words):
    header = ['level', 'page_num', 'block_num', 'par_num', 'line_num', 'word_num',
              'left', 'top', 'width', 'height', 'conf', 'text']
    lines = ['\t'.join(header)]
    for i, w in enumerate(words):
        bn, pn, ln = w.get('line_key', ('1', '1', '1'))
        lines.append('\t'.join(str(x) for x in [
            5, 1, bn, pn, ln, i + 1, w['left'], w['top'], w['width'], w['height'],
            w.get('conf', 95), w['text']]))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


ALL_LANGS = ('eng', 'osd', 'pol', 'ces', 'slk', 'fra')   # every language the tool's schemes name


def _langs_installed(test, langs=ALL_LANGS):
    """Answer the tool's language check without running tesseract."""
    p = mock.patch('redact_ids._installed_langs', return_value=set(langs))
    p.start(); test.addCleanup(p.stop)


class ToolRouter:
    """Routes redact_ids.subprocess.run calls to a per-tool fake, keyed by the invoked
    executable's basename. Each fake receives the full cmd list, performs whatever file
    side-effects it wants, and returns a subprocess.CompletedProcess."""

    def __init__(self, langs=ALL_LANGS):
        self.handlers = {}
        self.calls = []
        self.langs = langs          # what `tesseract --list-langs` answers; that call is not in self.calls

    def set(self, tool, handler):
        self.handlers[tool] = handler

    def __call__(self, cmd, **kwargs):
        if os.path.basename(cmd[0]) == 'tesseract' and list(cmd[1:]) == ['--list-langs']:
            return subprocess.CompletedProcess(
                cmd, 0, 'List of available languages in "/synthetic/" (%d):\n%s\n' % (len(self.langs), '\n'.join(self.langs)), '')
        self.calls.append(list(cmd))
        tool = os.path.basename(cmd[0])
        h = self.handlers.get(tool)
        if h is None:
            raise AssertionError(f'PipelineOrchestrationTests: no fake handler for tool {tool!r} ({cmd})')
        return h(cmd)


def _default_pdftoppm(n_pages=1, rc=0, numbers=None):
    def handler(cmd):
        prefix = cmd[-1]
        if rc == 0:
            nums = numbers if numbers is not None else range(1, n_pages + 1)
            for n in nums:
                with open(f'{prefix}-{n:02d}.png', 'wb') as f:
                    f.write(b'PNGDATA')
        return subprocess.CompletedProcess(cmd, rc, '', '')
    return handler


def _default_tesseract(words=None):
    """Handles BOTH tesseract call shapes: OSD ('stdout' as 3rd arg) and TSV OCR."""
    words = words or []

    def handler(cmd):
        if cmd[2] == 'stdout':  # OSD
            return subprocess.CompletedProcess(
                cmd, 0, 'Orientation in degrees: 0\nRotate: 0\nOrientation confidence: 5.00\n', '')
        base = cmd[2]
        _write_tsv(base + '.tsv', words)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    return handler


def _default_identify(w=600, h=800, rc=0):
    def handler(cmd):
        return subprocess.CompletedProcess(cmd, rc, f'{w} {h}', '')
    return handler


def _clean_page_words():
    """Enough non-identifier words to clear NEAR_EMPTY_WORDS so a scenario reads as genuinely
    clean (no flags at all), not just 'no identifier hit'. Purely alphabetic (no digits at all)
    and each on its OWN line_key, so nothing accidentally concatenates into a digit run across
    words on what detect() would otherwise treat as a shared line."""
    return [W('lorem', 100, 40 * i, line=(str(i), '1', '1')) for i in range(NEAR_EMPTY_WORDS_TEST_FLOOR)]


NEAR_EMPTY_WORDS_TEST_FLOOR = 25  # > R.NEAR_EMPTY_WORDS


def _pgm(level, n=64):
    """A grey-cell file: one level everywhere, or (share, dark, light) for a part-dark page."""
    if isinstance(level, tuple):
        share, dark, light = level
        k = int(share * n * n)
        return b'P5\n%d %d\n255\n' % (n, n) + bytes([dark]) * k + bytes([light]) * (n * n - k)
    return b'P5\n%d %d\n255\n' % (n, n) + bytes([level]) * (n * n)


def _default_convert(rc=0, grey=None):
    """A fake ImageMagick. The darkened read's grey cells (a .pgm output) come out at grey(input file
    name), white paper by default. The name, not the path: a temp folder's random name can hold '_v'."""
    def handler(cmd):
        if rc == 0:
            out = cmd[-1]
            with open(out, 'wb') as f:
                f.write(_pgm(grey(os.path.basename(cmd[1])) if grey else 255) if out.endswith('.pgm') else b'PNGDATA')
        return subprocess.CompletedProcess(cmd, rc, '', '')
    return handler


class PipelineOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inbox = os.path.join(self.tmp.name, 'inbox'); os.makedirs(self.inbox)
        self.render = os.path.join(self.tmp.name, 'render'); os.makedirs(self.render)
        self.work = os.path.join(self.tmp.name, 'work'); os.makedirs(self.work)
        self.redacted = os.path.join(self.tmp.name, 'redacted'); os.makedirs(self.redacted)
        self.pdf = os.path.join(self.inbox, 'doc1.pdf')
        with open(self.pdf, 'wb') as f:
            f.write(b'%PDF-FAKE')
        R.IM = dict(convert=['convert'], identify=['identify'])
        self._old_im = None

    def _args(self, **over):
        d = dict(inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
                 dob='1901-02-03', scheme='pl-id', label_token=None,
                 rules=R.DEFAULT_RULES, dpi=300, lang='pol', max_iters=3,
                 prefix=PREFIX)
        d.update(over)
        return argparse_namespace(d)

    def _run(self, router, **arg_over):
        """By default, simulate a host where pdfinfo is NOT on PATH — the independently-
        determined page-count check is 'where available' (point 5); tests that specifically
        exercise it patch shutil.which back in. This keeps the other scenarios deterministic
        regardless of whether the *actual* dev/CI host happens to have poppler's pdfinfo."""
        a = self._args(**arg_over)
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', return_value=None):
            return R.run_pipeline(a)

    def _doc_dirs(self):
        return sorted(d for d in os.listdir(self.redacted)
                      if not d.startswith('.') and os.path.isdir(os.path.join(self.redacted, d)))

    def _only_doc(self):
        """The single opaque-id doc dir under --redacted (doc ids are content-derived, not the
        source stem — HO-09 item 3 — so tests discover the dir rather than hardcoding 'doc1')."""
        dirs = self._doc_dirs()
        self.assertEqual(len(dirs), 1, 'expected exactly one document dir, got %r' % dirs)
        self.assertRegex(dirs[0], r'^doc-[0-9a-f]{16}$')
        return os.path.join(self.redacted, dirs[0])

    def _docid_for(self, pdf_path):
        return 'doc-' + R._sha256_file(pdf_path)[:16]

    def _manifest(self):
        with open(os.path.join(self._only_doc(), 'manifest.json')) as f:
            return json.load(f)

    def test_clean_run_no_identifier(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'CLEAN')
        self.assertEqual(code, R.EXIT_OK_AWAITING_OPERATOR)
        self.assertTrue(os.path.isfile(os.path.join(self._only_doc(), 'page-01.png')))
        man = self._manifest()
        self.assertEqual(man['state'], 'AWAITING_OPERATOR')
        self.assertEqual(man['doc'], self._docid_for(self.pdf))
        self.assertEqual(man['pages'][0]['flags'], [])
        self.assertTrue(man['pages'][0]['sha256'])
        # the strict validator accepts a genuinely clean manifest (round-trip on real output)
        self.assertEqual(R.validate_document_manifest(man, self._only_doc()), [])

    def test_real_output_approves_and_verifies_end_to_end(self):
        """The whole chain composes on REAL tool output (not a synthetic manifest): a clean
        redact run -> approve_one -> verify_one, all green at the pre-consumption check."""
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        self._run(router)
        doc_dir = self._only_doc()
        approved = os.path.join(self.tmp.name, 'approved')
        r = A.approve_one(os.path.join(doc_dir, 'manifest.json'), approved, accept_flagged=False)
        self.assertTrue(r['ok'], r)
        v = V.verify_one(os.path.join(approved, os.path.basename(doc_dir), 'approval.json'), self.redacted)
        self.assertTrue(v['ok'])
        self.assertEqual(v['pages'], [1])

    def test_private_run_redacted_and_approved_modes(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        _, run_id, _, _ = self._run(router)
        doc_dir = self._only_doc()
        approved_root = os.path.join(self.tmp.name, 'approved')
        result = A.approve_one(os.path.join(doc_dir, 'manifest.json'), approved_root,
                               accept_flagged=False)
        self.assertTrue(result['ok'], result)
        approved_dir = os.path.join(approved_root, os.path.basename(doc_dir))

        for directory in (os.path.join(self.render, run_id), os.path.join(self.work, run_id),
                          self.redacted, doc_dir, approved_root, approved_dir):
            self.assertEqual(os.stat(directory).st_mode & 0o777, 0o700, directory)
        for private_file in (os.path.join(doc_dir, 'page-01.png'),
                             os.path.join(doc_dir, 'manifest.json'),
                             os.path.join(approved_dir, 'page-01.png'),
                             os.path.join(approved_dir, 'approval.json')):
            self.assertEqual(os.stat(private_file).st_mode & 0o777, 0o600, private_file)

    def test_real_hold_output_needs_accept_flagged_then_verifies(self):
        """A real HOLD manifest (OSD_UNRELIABLE) is schema-valid but blocks approval until an
        explicit acknowledgement, after which it verifies — proving real HOLD output composes."""
        def osd_unreliable(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 1, '', '')  # nonzero OSD -> HOLD
            _write_tsv(cmd[2] + '.tsv', _clean_page_words())
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', osd_unreliable)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual(run_result, 'HOLD')
        doc_dir = self._only_doc()
        approved = os.path.join(self.tmp.name, 'approved')
        blocked = A.approve_one(os.path.join(doc_dir, 'manifest.json'), approved, accept_flagged=False)
        self.assertFalse(blocked['ok'])
        self.assertEqual(blocked['code'], A.EXIT_REJECTED_FLAGS)
        ok = A.approve_one(os.path.join(doc_dir, 'manifest.json'), approved, accept_flagged=True,
                           accept_flags={'OSD_UNRELIABLE'})
        self.assertTrue(ok['ok'], ok)
        v = V.verify_one(os.path.join(approved, os.path.basename(doc_dir), 'approval.json'), self.redacted)
        self.assertTrue(v['ok'])

    def test_byte_identical_inputs_deduped_not_run_error(self):
        """Red-team hardening: two byte-identical inputs are the same document by content — process
        once and record the duplicate as a benign SKIPPED_DUPLICATE, NOT a whole-run ERROR (which a
        naive content-id collision would have produced). The good document stays approvable."""
        with open(os.path.join(self.inbox, 'copy.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')  # byte-identical to self.pdf ('doc1.pdf')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'CLEAN')
        self.assertEqual(code, R.EXIT_OK_AWAITING_OPERATOR)
        states = sorted(r.get('state') for r in results)
        self.assertIn('SKIPPED_DUPLICATE', states)
        self.assertIn('AWAITING_OPERATOR', states)
        self.assertEqual(len(self._doc_dirs()), 1)  # only one promoted doc dir for the identical bytes

    def test_prefix_collision_different_docs_fails_closed(self):
        """Second-pass fix: two DIFFERENT documents that merely share the 64-bit doc-id prefix must
        NOT be silently dropped as a duplicate (dedup keys on the FULL sha) — they fall through and
        fail CLOSED via the run-scoped makedirs collision -> PROCESS_ERROR -> run ERROR."""
        with open(os.path.join(self.inbox, 'other.pdf'), 'wb') as f:
            f.write(b'%PDF-DIFFERENT-CONTENT')
        real_snap = R._snapshot_input

        def fake_snap(src, snap_dir):
            snap_path, real_hash = real_snap(src, snap_dir)
            base = os.path.basename(src)
            if base == 'doc1.pdf':
                return snap_path, '0123456789abcdef' + 'a' * 48
            if base == 'other.pdf':
                return snap_path, '0123456789abcdef' + 'b' * 48  # same 16-hex prefix, different full hash
            return snap_path, real_hash

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        a = self._args()
        with mock.patch('redact_ids._snapshot_input', side_effect=fake_snap), \
             mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', return_value=None):
            results, run_id, code, run_result = R.run_pipeline(a)
        self.assertEqual(run_result, 'ERROR')            # fail closed, not a silent duplicate
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertNotIn('SKIPPED_DUPLICATE', [r.get('state') for r in results])

    def test_empty_inbox_is_an_error_not_success(self):
        empty_inbox = os.path.join(self.tmp.name, 'empty-inbox'); os.makedirs(empty_inbox)
        a = self._args(inbox=empty_inbox)
        results, run_id, code, run_result = R.run_pipeline(a)
        self.assertIsNone(run_id)
        self.assertEqual(code, R.EXIT_EMPTY_INPUT)
        self.assertEqual(run_result, 'EMPTY_INPUT')

    def test_render_failure_nonzero_exit(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(rc=1))
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'ERROR')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertEqual(results[0]['error'], 'RENDER_FAILED')
        self.assertFalse(glob.glob(os.path.join(self._only_doc(), 'page-*.png')))
        # an errored document's manifest must say FAILED, never claim operator-readiness
        self.assertEqual(self._manifest()['state'], 'FAILED')

    def test_document_level_exception_is_contained_and_documented(self):
        """An unexpected failure OUTSIDE the per-page handling (e.g. an unreadable input PDF
        failing its input snapshot) must surface as a documented PROCESS_ERROR result for that
        document with exit 11 — never an unhandled traceback with an undocumented exit code —
        and must publish nothing at the live --redacted/<doc>/ path."""
        router = ToolRouter()  # no handlers needed; the failure happens before any tool call
        a = self._args()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', return_value=None), \
             mock.patch('redact_ids._snapshot_input', side_effect=OSError('unreadable')):
            results, run_id, code, run_result = R.run_pipeline(a)
        self.assertEqual(run_result, 'ERROR')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertEqual(results[0]['error'], 'PROCESS_ERROR')
        self.assertEqual(results[0]['state'], 'FAILED')
        self.assertEqual(results[0]['error_type'], 'OSError')
        self.assertRegex(results[0]['doc'], r'^doc-[0-9a-f]{16}$')  # opaque id, never the source stem
        self.assertEqual(self._doc_dirs(), [])  # input hash failed before any dir was created

    def test_run_dir_collision_raises_sanitized_runtime_error(self):
        """A run-scoped directory collision must raise RuntimeError carrying NO path (the message
        is caught in main() and mapped to the documented exit 65; a leaked filename would defeat
        the sanitized-logging contract even in-process)."""
        a = self._args()
        secret = '/some/secret/leftover/path'
        with mock.patch('redact_ids.glob.glob', return_value=[self.pdf]), \
             mock.patch('redact_ids.os.makedirs',
                        side_effect=FileExistsError(17, 'File exists', secret)):
            with self.assertRaises(RuntimeError) as ctx:
                R.run_pipeline(a)
        self.assertNotIn(secret, str(ctx.exception))
        self.assertNotIn('/', str(ctx.exception))  # no path fragment at all

    def test_main_maps_run_state_error_to_exit_65_no_traceback_no_path(self):
        """A RuntimeError/OSError escaping run_pipeline must become the documented exit 65 with a
        sanitized abort line — never an uncaught traceback (Python exit 1) and never a leaked path."""
        secret = '/private/leftover/render/deadbeef'
        for exc in (RuntimeError(f'run-scoped directory collision: {secret}'),
                    OSError(28, 'No space left on device', secret)):
            with mock.patch('redact_ids._im',
                            return_value={'convert': ['convert'], 'identify': ['identify']}), \
                 mock.patch('redact_ids.validate_args', return_value=[]), \
                 mock.patch('redact_ids.run_pipeline', side_effect=exc):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = R.main(['--inbox', '/x', '--render', '/r', '--work', '/w',
                                   '--redacted', '/red', '--log', '/l.json', '--dob', '1901-02-03', '--scheme', 'pl-id'])
            out = buf.getvalue()
            self.assertEqual(code, R.EXIT_STATE_ERROR)
            self.assertNotIn('Traceback', out)
            self.assertNotIn(secret, out)

    def test_render_zero_pages_rc0(self):
        """pdftoppm exits 0 but writes no page files — must not be read as an empty-but-clean run."""
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(rc=0, numbers=[]))
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(results[0]['error'], 'RENDER_FAILED')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)

    def test_page_numbering_gap_mismatch(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(numbers=[1, 3]))  # gap at 2
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(results[0]['error'], 'PAGE_COUNT_MISMATCH')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)

    def test_pdfinfo_page_count_mismatch(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('pdfinfo', lambda cmd: subprocess.CompletedProcess(cmd, 0, 'Pages: 2\n', ''))

        def fake_which(name):
            return f'/usr/bin/{name}' if name == 'pdfinfo' else None

        a = self._args()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', side_effect=fake_which):
            results, run_id, code, run_result = R.run_pipeline(a)
        self.assertEqual(results[0]['error'], 'PAGE_COUNT_MISMATCH')
        self.assertIn('pdfinfo', ' '.join(results[0]['notes']))

    def test_near_empty_ocr_holds(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=[]))  # near-empty
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'HOLD')
        self.assertEqual(code, R.EXIT_HOLD)
        self.assertIn('NEAR_EMPTY_OCR', results[0]['pages'][0]['flags'])
        # the page still gets a raster — it needs the operator's eyeball, not withholding
        self.assertTrue(os.path.isfile(os.path.join(self._only_doc(), 'page-01.png')))

    def test_label_no_candidate_holds(self):
        many_words = [W('Hemoglobina', 100, 100)] + [W(f'w{i}', 100, 200 + i * 40) for i in range(20)]
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=[W(LABEL, 100, 900)] + many_words))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router, label_token=LABEL)
        self.assertEqual(run_result, 'HOLD')
        self.assertIn('LABEL_NO_CANDIDATE', results[0]['pages'][0]['flags'])

    def test_checksum_only_expected_false_positive_holds(self):
        many_words = [W(f'w{i}', 100, 40 * i) for i in range(20)]
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(
            words=many_words + [W('44051401359', 500, 900, width=260)]))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'HOLD')
        self.assertIn('CHECKSUM_ONLY_EXPECT_FALSE_POSITIVE', results[0]['pages'][0]['flags'])

    def test_mask_verify_never_converges_holds(self):
        many_words = [W(f'w{i}', 100, 40 * i) for i in range(20)]
        strong = W('01020312340', 500, 900, width=260)  # keeps re-appearing every re-OCR pass
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=many_words + [strong]))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router, max_iters=2)
        self.assertEqual(run_result, 'HOLD')
        pg = results[0]['pages'][0]
        self.assertIn('MASK_VERIFY_FAILED', pg['flags'])
        self.assertFalse(pg['converged'])
        # imperfect but present — over-mask beats under-mask; still needs the eyeball
        self.assertTrue(os.path.isfile(os.path.join(self._only_doc(), 'page-01.png')))

    def test_mask_burn_failure_is_process_error_and_publishes_nothing_for_that_page(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=[W('Hemoglobina', 100, 100)]))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert(rc=1))  # burn fails
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'ERROR')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertIn('PROCESS_ERROR', results[0]['pages'][0]['flags'])
        self.assertFalse(os.path.isfile(os.path.join(self._only_doc(), 'page-01.png')))

    # A81: a page that fails AFTER its first burn already has that burn's raster (and possibly a
    # re-mask's temp) in the staged set. PROCESS_ERROR promises no raster for the page, so neither
    # may reach the live --redacted/<doc>/. Each case below published one before the fix.
    def _assert_failed_page_published_nothing(self, results, code):
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertIn('PROCESS_ERROR', results[0]['pages'][0]['flags'])
        self.assertEqual(sorted(os.listdir(self._only_doc())), ['manifest.json'],
                         'a failed page must leave no raster or temp in the live redacted set')

    def _strong_hit_words(self):
        return _clean_page_words() + [W('01020312340', 100, 2000, line=('99', '1', '1'))]

    def test_verify_reocr_failure_after_first_burn_publishes_no_raster(self):
        tsv_calls = []

        def tesseract(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            tsv_calls.append(cmd)
            if len(tsv_calls) > 1:                       # the verify re-OCR of the burned raster fails
                return subprocess.CompletedProcess(cmd, 1, '', '')
            _write_tsv(cmd[2] + '.tsv', self._strong_hit_words())
            return subprocess.CompletedProcess(cmd, 0, '', '')

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self._assert_failed_page_published_nothing(results, code)

    def test_remask_failure_after_first_burn_publishes_no_raster_or_temp(self):
        identify_calls = []
        ok_identify = _default_identify()

        def identify(cmd):
            identify_calls.append(cmd)
            if len(identify_calls) > 2:                  # page dims, first burn ok; the re-mask's check fails
                return subprocess.CompletedProcess(cmd, 1, '', '')
            return ok_identify(cmd)

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=self._strong_hit_words()))  # the hit survives re-OCR
        router.set('identify', identify)
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self._assert_failed_page_published_nothing(results, code)

    def test_unexpected_error_after_first_burn_publishes_no_raster(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        with mock.patch('redact_ids._sha256_file', side_effect=OSError('synthetic')):
            results, run_id, code, run_result = self._run(router)
        self._assert_failed_page_published_nothing(results, code)
        self.assertEqual(results[0]['pages'][0].get('error_type'), 'OSError')

    def test_failed_raster_removal_promotes_nothing_for_the_document(self):
        real_unlink = os.unlink

        def unlink(p, *a, **k):
            if os.path.basename(p) == 'page-01.png':
                raise PermissionError('synthetic')
            return real_unlink(p, *a, **k)

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        with mock.patch('redact_ids._sha256_file', side_effect=OSError('synthetic')), \
             mock.patch('redact_ids.os.unlink', side_effect=unlink):
            results, run_id, code, run_result = self._run(router)
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertEqual(results[0]['error'], 'PROCESS_ERROR')
        self.assertEqual(self._doc_dirs(), [], 'nothing may be promoted when the raster cannot be removed')

    def test_low_confidence_identifier_holds_the_page_for_explicit_review(self):
        """A80: an identifier OCR read below its confidence floor used to vanish: no mask, no flag, a
        CLEAN exit. Now it is masked and the page HOLDs until the operator acknowledges it."""
        tsv_calls = []

        def tesseract(cmd):                             # the masked re-read no longer sees the token
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            tsv_calls.append(cmd)
            extra = [W('01020312340', 100, 2000, conf=18, line=('99', '1', '1'))] if len(tsv_calls) == 1 else []
            _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
            return subprocess.CompletedProcess(cmd, 0, '', '')

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        pg = results[0]['pages'][0]
        self.assertEqual(pg['flags'], ['LOW_CONFIDENCE_CANDIDATE'])
        self.assertIn('id-low-confidence', pg['reasons'])
        self.assertGreaterEqual(pg['n_masked'], 1)
        man = self._manifest()
        self.assertEqual(R.validate_document_manifest(man, self._only_doc()), [])
        approved = os.path.join(self.tmp.name, 'approved')
        mpath = os.path.join(self._only_doc(), 'manifest.json')
        blocked = A.approve_one(mpath, approved, accept_flagged=False)
        self.assertEqual(blocked['code'], A.EXIT_REJECTED_FLAGS)
        ok = A.approve_one(mpath, approved, accept_flagged=True, accept_flags={'LOW_CONFIDENCE_CANDIDATE'})
        self.assertTrue(ok['ok'], ok)

    def test_low_confidence_hit_first_seen_on_the_re_read_still_holds(self):
        tsv_calls = []

        def tesseract(cmd):                             # only the verify re-read sees the faint token
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            tsv_calls.append(cmd)
            extra = [W('01020312340', 100, 2000, conf=18, line=('99', '1', '1'))] if len(tsv_calls) == 2 else []
            _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
            return subprocess.CompletedProcess(cmd, 0, '', '')

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual(results[0]['pages'][0]['flags'], ['LOW_CONFIDENCE_CANDIDATE'])

    def _faint_router(self, dark_sees, convert=None):
        """Faint ink: the plain reads never see the number; dark_sees(file name) says which darkened reads
        do. The name, not the path: a temp folder's random name can hold '_v' or '_dark'."""
        def tesseract(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            extra = [W('01020312340', 100, 2000, line=('99', '1', '1'))] if dark_sees(os.path.basename(cmd[1])) else []
            _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', convert or _default_convert())
        return router

    def test_faint_ink_only_a_darkened_read_shows_is_masked_and_held(self):
        """OCR reads no word at all in faint ink, so the confidence floor never saw it: no mask, no flag,
        a CLEAN exit, on real tools and invented pages (2026-11-07). The darkened read finds it."""
        router = self._faint_router(lambda png: png.endswith('p1_dark.png'))
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        pg = results[0]['pages'][0]
        self.assertEqual(pg['flags'], ['LOW_CONFIDENCE_CANDIDATE'])
        self.assertIn('id-low-confidence', pg['reasons'])
        self.assertGreaterEqual(pg['n_masked'], 1)
        self.assertTrue(pg['converged'])
        self.assertTrue(any('-draw' in c for c in router.calls), 'the box was never burned')
        self.assertEqual(R.validate_document_manifest(self._manifest(), self._only_doc()), [])
        approved = os.path.join(self.tmp.name, 'approved')
        mpath = os.path.join(self._only_doc(), 'manifest.json')
        self.assertEqual(A.approve_one(mpath, approved, accept_flagged=False)['code'], A.EXIT_REJECTED_FLAGS)
        self.assertTrue(A.approve_one(mpath, approved, accept_flagged=True,
                                      accept_flags={'LOW_CONFIDENCE_CANDIDATE'})['ok'])

    def _label_router(self, plain, dark):
        """What the plain and the darkened first reads add to a clean page; masked re-reads add nothing."""
        def tesseract(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            base = os.path.basename(cmd[2])
            extra = [] if '_v' in base else (dark if '_dark' in base else plain)
            _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        return router

    def test_a_label_only_the_darkened_read_sees_holds_the_page(self):
        label = [W(LABEL, 100, 2000, line=('99', '1', '1'))]
        results, _, code, run_result = self._run(self._label_router([], label), label_token=LABEL)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        self.assertEqual(results[0]['pages'][0]['flags'], ['LABEL_NO_CANDIDATE'])

    def test_a_number_beside_a_label_only_the_darkened_read_sees_is_masked_and_held(self):
        pair = [W(LABEL, 100, 2000, line=('99', '1', '1')), W('1234', 220, 2000, line=('99', '1', '1'))]
        results, _, _, run_result = self._run(self._label_router([], pair), label_token=LABEL)
        self.assertEqual(run_result, 'HOLD')
        pg = results[0]['pages'][0]
        self.assertEqual(pg['flags'], ['LOW_CONFIDENCE_CANDIDATE'])
        self.assertGreaterEqual(pg['n_masked'], 1)

    def test_a_label_the_plain_read_saw_is_not_held_for_the_darkened_read_losing_its_number(self):
        pair = [W(LABEL, 100, 2000, line=('99', '1', '1')), W('1234', 220, 2000, line=('99', '1', '1'))]
        results, _, code, run_result = self._run(self._label_router(pair, pair[:1]), label_token=LABEL)
        self.assertEqual((run_result, code), ('CLEAN', R.EXIT_OK_AWAITING_OPERATOR))
        self.assertEqual(results[0]['pages'][0]['flags'], [])

    def test_the_darkened_copy_is_owner_only_while_read_and_gone_after(self):
        modes = []
        router = self._faint_router(lambda png: False)
        plain = router.handlers['tesseract']

        def tesseract(cmd):
            if cmd[1].endswith('_dark.png'):
                modes.append((os.path.dirname(cmd[1]).startswith(self.work), stat.S_IMODE(os.stat(cmd[1]).st_mode)))
            return plain(cmd)
        router.set('tesseract', tesseract)
        self._run(router)
        self.assertEqual(modes, [(True, 0o600)] * 2)     # the page, and its masked re-read
        left = [n for dp, _, ns in os.walk(self.work) for n in ns if n.endswith(('.png', '.pgm', '.part'))
                and ('_dark' in n or '_cells' in n)]
        self.assertEqual(left, [])
        self.assertEqual([n for n in os.listdir(self._only_doc()) if 'dark' in n], [])

    def test_the_black_point_follows_the_pages_own_paper(self):
        """A fixed 80% black point turned 78% grey paper solid black: nothing read, CLEAN (cold review
        2026-11-07). The paper is white in the copy, and 80% of its level is the black point."""
        router = self._faint_router(lambda png: '_dark' in png and '_v' not in png,
                                    convert=_default_convert(grey=lambda png: 255 if '_dark' in png else 199))
        results, _, _, run_result = self._run(router)
        levels = [c[c.index('-level') + 1] for c in router.calls if '-level' in c]
        self.assertEqual(levels[0], '62.4%,78.0%')
        self.assertEqual(run_result, 'HOLD')
        self.assertEqual(results[0]['pages'][0]['flags'], ['LOW_CONFIDENCE_CANDIDATE'])

    def test_a_darkened_copy_that_comes_out_dark_holds_the_page_unread(self):
        router = self._faint_router(lambda png: False,
                                    convert=_default_convert(grey=lambda png: 3 if '_dark' in png else 230))
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        self.assertEqual(results[0]['pages'][0]['flags'], ['DARKENED_READ_UNREADABLE'])
        self.assertFalse(any(c[0] == 'tesseract' and c[1].endswith('_dark.png') for c in router.calls),
                         'an unreadable copy is not read as nothing faint')
        mpath = os.path.join(self._only_doc(), 'manifest.json')
        approved = os.path.join(self.tmp.name, 'approved')
        self.assertEqual(A.approve_one(mpath, approved, accept_flagged=False)['code'], A.EXIT_REJECTED_FLAGS)
        self.assertTrue(A.approve_one(mpath, approved, accept_flagged=True,
                                      accept_flags={'DARKENED_READ_UNREADABLE'})['ok'])

    def test_a_dark_half_page_does_not_set_the_paper(self):
        """The middle grey cell fell into a dark block over half the page: the faint number came out light
        grey and the page exited CLEAN on real tools (2026-11-07). The paper is the cell 90% of the way up."""
        router = self._faint_router(lambda png: False,
                                    convert=_default_convert(grey=lambda png: 255 if '_dark' in png else (0.55, 120, 199)))
        self._run(router)
        levels = [c[c.index('-level') + 1] for c in router.calls if '-level' in c]
        self.assertEqual(levels[0], '62.4%,78.0%')

    def test_a_darkened_copy_dark_over_a_quarter_holds_and_under_it_does_not(self):
        for share, flags in ((0.36, ['DARKENED_READ_UNREADABLE']), (0.2, [])):
            with self.subTest(share):
                self.setUp()
                router = self._faint_router(lambda png: False, convert=_default_convert(
                    grey=lambda png: (share, 0, 255) if '_dark' in png else 255))
                results, _, _, _ = self._run(router)
                self.assertEqual(results[0]['pages'][0]['flags'], flags)

    def test_a_small_faint_number_no_plain_box_covers_is_kept(self):
        """A box no taller than twice the tolerance shrank to nothing and counted as covered with no plain
        box at all: dropped, CLEAN (Codex, 2026-11-07)."""
        small = [W('01020312340', 100, 2000, width=60, height=12, line=('99', '1', '1'))]
        results, _, code, run_result = self._run(self._label_router([], small))
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        self.assertIn('id-low-confidence', results[0]['pages'][0]['reasons'])
        self.assertFalse(R.covered([100, 200, 90, 12], [], 6))
        self.assertFalse(R.covered([100, 200, 4, 4], [], 6))
        self.assertTrue(R.covered([100, 200, 90, 12], [[98, 198, 95, 16]], 6))
        self.assertFalse(R.covered([100, 200, 90, 12], [[98, 198, 40, 16]], 6))

    def test_a_masked_re_read_whose_darkened_copy_comes_out_dark_holds_too(self):
        router = self._faint_router(lambda png: False,
                                    convert=_default_convert(grey=lambda png: 3 if '_v1_dark' in png else 250))
        results, _, _, run_result = self._run(router)
        self.assertEqual(run_result, 'HOLD')
        self.assertEqual(results[0]['pages'][0]['flags'], ['DARKENED_READ_UNREADABLE'])

    def test_paper_too_dark_to_darken_holds_the_page_unread(self):
        # the second case: a brighter tenth of the page must not lift a dark page over the floor (Codex)
        for grey in (40, (0.8, 63, 65)):
            with self.subTest(grey):
                self.setUp()
                router = self._faint_router(lambda png: False, convert=_default_convert(grey=lambda png: grey))
                results, _, _, run_result = self._run(router)
                self.assertEqual(run_result, 'HOLD')
                self.assertIn('DARKENED_READ_UNREADABLE', results[0]['pages'][0]['flags'])
                self.assertFalse(any('-level' in c for c in router.calls))

    def test_a_darkened_hit_reaching_past_a_weaker_box_is_kept_whole(self):
        """The plain read sees the label and the first six digits, printed dark (a label-proximity box);
        the darkened read sees all eleven over that box. Dropped for touching it, the serial and check
        digits stayed visible: CLEAN (cold review 2026-11-07)."""
        part = [W(LABEL, 100, 2000, line=('99', '1', '1')), W('010203', 220, 2000, width=90, line=('99', '1', '1'))]
        whole = [W(LABEL, 100, 2000, line=('99', '1', '1')), W('01020312340', 220, 2000, width=170, line=('99', '1', '1'))]
        router = self._label_router(part, whole)
        results, _, code, run_result = self._run(router, label_token=LABEL)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        pg = results[0]['pages'][0]
        self.assertIn('LOW_CONFIDENCE_CANDIDATE', pg['flags'])
        self.assertIn('id-low-confidence', pg['reasons'])
        burned = [c for c in router.calls if '-draw' in c][0]
        rects = [tuple(map(int, re.findall(r'-?\d+', r))) for r in burned[burned.index('-draw') + 1].split('rectangle')[1:]]
        self.assertTrue(any(x0 <= 220 and x1 >= 220 + 170 for x0, _, x1, _ in rects), 'the whole number is boxed')

    def test_a_darkened_hit_the_plain_boxes_cover_adds_nothing(self):
        same = [W('01020312340', 100, 2000, width=170, line=('99', '1', '1'))]
        drift = [W('01020312340', 103, 1998, width=172, height=33, line=('99', '1', '1'))]
        results, _, _, run_result = self._run(self._label_router(same, drift))
        self.assertEqual(run_result, 'CLEAN')
        self.assertNotIn('id-low-confidence', results[0]['pages'][0]['reasons'])

    def test_a_label_only_the_darkened_read_sees_holds_even_beside_one_the_plain_read_saw(self):
        """One dark label with its number, and a second faint one whose number stays unreadable: the
        hold fired only when the plain read saw no label anywhere (cold review 2026-11-07)."""
        dark_pair = [W(LABEL, 100, 600, line=('98', '1', '1')), W('1234', 220, 600, line=('98', '1', '1'))]
        faint_label = [W(LABEL, 100, 2000, line=('99', '1', '1'))]
        results, _, code, run_result = self._run(self._label_router(dark_pair, dark_pair + faint_label),
                                                 label_token=LABEL)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        self.assertEqual(results[0]['pages'][0]['flags'], ['LABEL_NO_CANDIDATE'])

    def test_a_page_with_nothing_faint_stays_clean(self):
        router = self._faint_router(lambda png: False)
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('CLEAN', R.EXIT_OK_AWAITING_OPERATOR))
        self.assertEqual(results[0]['pages'][0]['flags'], [])
        self.assertEqual(sum('-level' in c for c in router.calls), 2)

    def test_a_number_both_reads_see_is_no_faint_hold(self):
        def tesseract(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            extra = [] if '_v' in os.path.basename(cmd[2]) else [W('01020312340', 100, 2000, line=('99', '1', '1'))]
            _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('CLEAN', R.EXIT_OK_AWAITING_OPERATOR))
        self.assertEqual(results[0]['pages'][0]['flags'], [])
        self.assertNotIn('id-low-confidence', results[0]['pages'][0]['reasons'])

    def test_a_faint_number_a_box_does_not_hide_fails_the_verify_loop(self):
        results, _, _, run_result = self._run(self._faint_router(lambda png: '_dark' in png))
        self.assertEqual(run_result, 'HOLD')
        self.assertEqual(sorted(results[0]['pages'][0]['flags']), ['LOW_CONFIDENCE_CANDIDATE', 'MASK_VERIFY_FAILED'])

    def test_the_darkened_read_goes_with_the_lowconf_rule(self):
        router = self._faint_router(lambda png: '_dark' in png)
        results, _, _, run_result = self._run(router, rules=('checksum', 'label', 'prefix'))
        self.assertEqual(run_result, 'CLEAN')
        self.assertFalse(any('-level' in c for c in router.calls))

    def test_a_darkened_read_that_fails_fails_the_page(self):
        ok = _default_convert()

        def convert(cmd):
            if '-level' in cmd:
                return subprocess.CompletedProcess(cmd, 1, '', '')
            return ok(cmd)
        results, _, code, run_result = self._run(self._faint_router(lambda png: False, convert=convert))
        self.assertEqual(run_result, 'ERROR')
        pg = results[0]['pages'][0]
        self.assertEqual(pg['flags'], ['PROCESS_ERROR'])
        self.assertEqual(pg['error_stage'], 'darken')

    def test_low_confidence_noise_stays_clean(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(
            words=_clean_page_words() + [W('IIlIlIllII', 100, 2000, conf=9, line=('99', '1', '1')),
                                         W('12.5', 300, 2000, conf=11, line=('99', '1', '1'))]))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('CLEAN', R.EXIT_OK_AWAITING_OPERATOR))

    def test_unsure_turn_holds_the_page_unrotated(self):
        """A82: OSD suggesting a turn below its confidence floor was neither applied nor flagged."""
        def unsure_turn(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 90\nOrientation confidence: 0.80\n', '')
            _write_tsv(cmd[2] + '.tsv', _clean_page_words())
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', unsure_turn)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('HOLD', R.EXIT_HOLD))
        pg = results[0]['pages'][0]
        self.assertIn('OSD_UNRELIABLE', pg['flags'])
        self.assertNotIn('rotated', pg)
        self.assertEqual(R.validate_document_manifest(self._manifest(), self._only_doc()), [])

    def test_unsure_upright_page_stays_clean(self):
        def unsure_upright(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 0.80\n', '')
            _write_tsv(cmd[2] + '.tsv', _clean_page_words())
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', unsure_upright)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, _, code, run_result = self._run(router)
        self.assertEqual((run_result, code), ('CLEAN', R.EXIT_OK_AWAITING_OPERATOR))

    def test_identify_failure_is_process_error(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=[W('Hemoglobina', 100, 100)]))
        router.set('identify', _default_identify(rc=1))
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'ERROR')
        self.assertIn('PROCESS_ERROR', results[0]['pages'][0]['flags'])

    def test_ocr_failure_is_process_error_not_silent_convergence(self):
        """An OCR failure during the initial pass must not be silently treated as 'clean' —
        before this fix, ocr_tsv() could return None and parse_tsv(None) -> [] -> zero hits."""
        def failing_tesseract(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            return subprocess.CompletedProcess(cmd, 1, '', '')  # OCR always fails

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', failing_tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'ERROR')
        self.assertIn('PROCESS_ERROR', results[0]['pages'][0]['flags'])

    def test_osd_nonzero_is_unreliable_and_holds(self):
        """HO-09 item 4: a nonzero OSD return is orientation-UNRELIABLE and fails CLOSED to an
        OSD_UNRELIABLE HOLD — never a silent CLEAN with orientation 0. (Was the reproduced defect:
        osd() returned unreliable=False and the run read CLEAN.)"""
        def osd_fails_ocr_ok(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 99, '', 'Too few characters.')
            _write_tsv(cmd[2] + '.tsv', _clean_page_words())
            return subprocess.CompletedProcess(cmd, 0, '', '')

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', osd_fails_ocr_ok)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'HOLD')
        self.assertEqual(code, R.EXIT_HOLD)
        self.assertTrue(results[0]['pages'][0].get('osd_unreliable'))
        self.assertIn('OSD_UNRELIABLE', results[0]['pages'][0]['flags'])

    def test_rerun_shorter_document_drops_stale_extra_pages(self):
        """The named bug: a gate-fix rerun of the same source bytes rendered shorter (3 pages -> 1)
        must not leave the old page-02/03 rasters reachable at the live doc path. Identity is the
        input CONTENT hash (HO-09 item 3), so the same bytes land under the same opaque id twice
        and the shorter set supersedes the longer one — never merges with it."""
        doc = self._docid_for(self.pdf)
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=3))
        router.set('tesseract', _default_tesseract(words=[W('Hemoglobina', 100, 100)]))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        self._run(router)
        self.assertEqual(sorted(os.listdir(os.path.join(self.redacted, doc))),
                         ['manifest.json', 'page-01.png', 'page-02.png', 'page-03.png'])

        router2 = ToolRouter()
        router2.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router2.set('tesseract', _default_tesseract(words=[W('Hemoglobina', 100, 100)]))
        router2.set('identify', _default_identify())
        router2.set('convert', _default_convert())
        self._run(router2)
        live = sorted(os.listdir(os.path.join(self.redacted, doc)))
        self.assertEqual(live, ['manifest.json', 'page-01.png'],
                         'stale page-02/03 must not survive a shorter rerun')

    def test_burn_failure_with_a_preexisting_stale_redacted_file(self):
        """A stale page-01.png already sits at the live doc path (from an earlier successful run);
        this run's burn step fails. The stale file must not be silently treated as this run's
        (unverified) output, and the run must still report ERROR."""
        stale_dir = os.path.join(self.redacted, self._docid_for(self.pdf)); os.makedirs(stale_dir)
        with open(os.path.join(stale_dir, 'page-01.png'), 'wb') as f:
            f.write(b'STALE-FROM-PRIOR-RUN')

        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=[W('Hemoglobina', 100, 100)]))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert(rc=1))  # burn fails this run
        results, run_id, code, run_result = self._run(router)
        self.assertEqual(run_result, 'ERROR')
        # the stale file is superseded (moved aside), not left live and not silently reused
        live = os.listdir(os.path.join(self.redacted, self._docid_for(self.pdf)))
        self.assertNotIn('page-01.png', live)
        superseded_root = os.path.join(self.redacted, '.superseded')
        self.assertTrue(os.path.isdir(superseded_root))


# ---------------------------------------------------------------------------
# Operator approval / promotion
# ---------------------------------------------------------------------------
class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.redacted = os.path.join(self.tmp.name, 'redacted')
        self.approved = os.path.join(self.tmp.name, 'approved')

    def _stage_clean_doc(self, label='doc1', flags=None, npages=1):
        return stage_valid_doc(self.redacted, label=label, flags=flags, npages=npages)

    def test_clean_approval(self):
        d = self._stage_clean_doc()
        doc = os.path.basename(d)
        results = [A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)]
        self.assertTrue(results[0]['ok'])
        self.assertTrue(os.path.isfile(os.path.join(self.approved, doc, 'page-01.png')))
        self.assertTrue(os.path.isfile(os.path.join(self.approved, doc, 'approval.json')))
        # the attestation is a strictly-valid, self-verifying approval
        with open(os.path.join(self.approved, doc, 'approval.json')) as f:
            app = json.load(f)
        self.assertEqual(R.validate_approval_attestation(app, os.path.join(self.approved, doc)), [])
        self.assertEqual([p['page'] for p in app['pages']], [1])
        self.assertTrue(R._HEX64_RE.match(app['source_manifest_sha256']))

    def test_doc_level_error_never_approvable(self):
        d = os.path.join(self.redacted, 'doc1'); os.makedirs(d)
        man = dict(run_id='r1', doc='doc1', error='RENDER_FAILED', pages=[])
        R._atomic_write_json(os.path.join(d, 'manifest.json'), man)
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=True)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_ERROR)
        self.assertFalse(os.path.isdir(os.path.join(self.approved, 'doc1')))

    def test_process_error_page_never_approvable_even_with_accept_flagged(self):
        d = self._stage_clean_doc(flags=['PROCESS_ERROR'])
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=True)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_ERROR)

    def test_unhashable_manifest_flag_is_schema_rejection_not_typeerror(self):
        d = self._stage_clean_doc()
        mp = os.path.join(d, 'manifest.json')
        with open(mp) as fh:
            man = json.load(fh)
        man['pages'][0]['flags'] = [{}]
        R._atomic_write_json(mp, man)
        r = A.approve_one(mp, self.approved, accept_flagged=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_SCHEMA)

    def test_hold_flag_rejected_without_accept_flagged(self):
        d = self._stage_clean_doc(flags=['NEAR_EMPTY_OCR'])
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_FLAGS)

    def test_hold_flag_approved_with_accept_flagged(self):
        d = self._stage_clean_doc(flags=['NEAR_EMPTY_OCR'])
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=True)
        self.assertTrue(r['ok'])

    def test_tampered_artifact_rejected_hash_mismatch(self):
        """Approval-state forgery defense: an artifact changed after the manifest was written
        (edited, corrupted, swapped) must be rejected, never silently approved."""
        d = self._stage_clean_doc()
        with open(os.path.join(d, 'page-01.png'), 'wb') as f:
            f.write(b'TAMPERED-BYTES-DIFFERENT-FROM-WHAT-WAS-EYEBALLED')
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_HASH)
        self.assertFalse(os.path.isdir(os.path.join(self.approved, os.path.basename(d))))

    def test_missing_page_file_rejected(self):
        d = self._stage_clean_doc()
        os.remove(os.path.join(d, 'page-01.png'))
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
        self.assertFalse(r['ok'])

    def test_direct_approval_refuses_fifo_manifest_without_opening(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        d = self._stage_clean_doc()
        manifest = os.path.join(d, 'manifest.json')
        os.remove(manifest); os.mkfifo(manifest)
        real_open = open
        def guarded_open(path, *args, **kwargs):
            if os.fspath(path) == manifest:
                raise AssertionError('a non-regular manifest must be rejected before open')
            return real_open(path, *args, **kwargs)
        with mock.patch('builtins.open', side_effect=guarded_open):
            result = A.approve_one(manifest, self.approved, accept_flagged=False)
        self.assertFalse(result['ok'])
        self.assertEqual(result['code'], A.EXIT_REJECTED_SCHEMA)

    def test_reapproval_supersedes_previous_approved_set(self):
        d = self._stage_clean_doc()
        A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
        with open(os.path.join(d, 'page-01.png'), 'wb') as f:
            f.write(b'NEW-CONTENT-AFTER-GATE-FIX-RERUN')
        new_sha = R._sha256_file(os.path.join(d, 'page-01.png'))
        man_path = os.path.join(d, 'manifest.json')
        with open(man_path) as f:
            man = json.load(f)
        man['pages'][0]['sha256'] = new_sha
        R._atomic_write_json(man_path, man)
        r = A.approve_one(man_path, self.approved, accept_flagged=False)
        self.assertTrue(r['ok'])
        with open(os.path.join(self.approved, os.path.basename(d), 'page-01.png'), 'rb') as f:
            self.assertEqual(f.read(), b'NEW-CONTENT-AFTER-GATE-FIX-RERUN')

    def test_main_nothing_to_approve(self):
        os.makedirs(self.redacted)
        with contextlib.redirect_stdout(io.StringIO()):  # keep main()'s ABORT line out of green test output
            code = A.main(['--redacted', self.redacted, '--approved', self.approved])
        self.assertEqual(code, A.EXIT_NOTHING_TO_APPROVE)

    def test_main_end_to_end_clean(self):
        self._stage_clean_doc()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = A.main(['--redacted', self.redacted, '--approved', self.approved])
        self.assertEqual(code, A.EXIT_APPROVED)
        self.assertIn('OPERATOR_APPROVED', buf.getvalue())

    def test_main_rejects_approved_equal_to_redacted(self):
        """--approved must not alias --redacted (would promote the approved set on top of the very
        AWAITING_OPERATOR set it reads). Invalid invocation -> exit 64."""
        self._stage_clean_doc()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = A.main(['--redacted', self.redacted, '--approved', self.redacted])
        self.assertEqual(code, A.EXIT_INVALID_INVOCATION)
        self.assertIn('distinct', buf.getvalue())

    def test_main_rejects_approved_nested_in_redacted(self):
        self._stage_clean_doc()
        nested = os.path.join(self.redacted, 'approved-sub')
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = A.main(['--redacted', self.redacted, '--approved', nested])
        self.assertEqual(code, A.EXIT_INVALID_INVOCATION)
        self.assertIn('nested', buf.getvalue())

    def test_main_rejects_redacted_nested_in_approved(self):
        os.makedirs(self.approved)
        inner = os.path.join(self.approved, 'redacted-inner'); os.makedirs(inner)
        # stage a doc under the inner (redacted) dir so isdir passes and it's a real source
        d = os.path.join(inner, 'doc1'); os.makedirs(d)
        with open(os.path.join(d, 'page-01.png'), 'wb') as f:
            f.write(b'X')
        sha = R._sha256_file(os.path.join(d, 'page-01.png'))
        R._atomic_write_json(os.path.join(d, 'manifest.json'),
                             dict(run_id='r1', doc='doc1', error=None,
                                  pages=[dict(page=1, flags=[], sha256=sha)]))
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = A.main(['--redacted', inner, '--approved', self.approved])
        self.assertEqual(code, A.EXIT_INVALID_INVOCATION)
        self.assertIn('nested', buf.getvalue())

    # ---- narrowed operator acknowledgement (HO-09 item 5) ----
    def test_main_accept_flagged_requires_doc(self):
        """A global --accept-flagged over every discovered document is invalid: it must be scoped
        to one explicit --doc (an operator's per-document eyeball decision, not a blanket sweep)."""
        self._stage_clean_doc(flags=['NEAR_EMPTY_OCR'])
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = A.main(['--redacted', self.redacted, '--approved', self.approved, '--accept-flagged'])
        self.assertEqual(code, A.EXIT_INVALID_INVOCATION)
        self.assertIn('--doc', buf.getvalue())

    def test_accept_flags_exact_cover_approves(self):
        d = self._stage_clean_doc(flags=['NEAR_EMPTY_OCR'])
        with contextlib.redirect_stdout(io.StringIO()):
            code = A.main(['--redacted', self.redacted, '--approved', self.approved,
                           '--doc', os.path.basename(d), '--accept-flagged',
                           '--accept-flags', 'NEAR_EMPTY_OCR'])
        self.assertEqual(code, A.EXIT_APPROVED)

    def test_accept_flags_incomplete_ack_rejected(self):
        """An acknowledgement that does not EXACTLY cover the manifest's current flag set is a
        stale/incomplete ack and must be rejected (HO-09 item 5)."""
        d = self._stage_clean_doc(flags=['NEAR_EMPTY_OCR', 'LABEL_NO_CANDIDATE'])
        with contextlib.redirect_stdout(io.StringIO()):
            code = A.main(['--redacted', self.redacted, '--approved', self.approved,
                           '--doc', os.path.basename(d), '--accept-flagged',
                           '--accept-flags', 'NEAR_EMPTY_OCR'])
        self.assertEqual(code, A.EXIT_REJECTED_FLAGS)

    def test_approve_rejects_forged_failed_manifest(self):
        """The reproduced HO-07 defect: a manifest with wrong kind / state:FAILED / mismatched doc /
        n_pages:99 / empty pages must NOT create an OPERATOR_APPROVED directory (now strict schema)."""
        doc_id = 'doc-' + '0' * 16
        d = os.path.join(self.redacted, doc_id); os.makedirs(d)
        forged = dict(schema_version=R.SCHEMA_VERSION, kind='not-a-manifest', tool=R.TOOL_NAME,
                      tool_version=R.TOOL_VERSION, run_id=SYN_RUN, doc='doc-' + 'f' * 16,
                      input_sha256='0' * 64, created_utc='x', n_pages=99, expected_pages=None,
                      pages=[], error=None, notes=[], state='FAILED')
        R._atomic_write_json(os.path.join(d, 'manifest.json'), forged)
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=True)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_SCHEMA)
        self.assertFalse(os.path.isdir(os.path.join(self.approved, doc_id)))

    def test_forged_bad_type_manifest_rejected_not_crash(self):
        """Red-team fix: a forged manifest whose `flags` is non-iterable or whose `pages` is a
        non-list must reach the strict validator and be a documented REJECTED_SCHEMA — never an
        uncaught TypeError -> exit-1 traceback in the pre-check that runs before the validator."""
        for i, mutate in enumerate((lambda m: m['pages'][0].update(flags=None),
                                    lambda m: m['pages'][0].update(flags=5),
                                    lambda m: m.update(pages=5, n_pages=5))):
            d = self._stage_clean_doc(label='forge%d' % i)
            mp = os.path.join(d, 'manifest.json')
            with open(mp) as f:
                man = json.load(f)
            mutate(man)
            R._atomic_write_json(mp, man)
            r = A.approve_one(mp, self.approved, accept_flagged=True)
            self.assertFalse(r['ok'])
            self.assertEqual(r['code'], A.EXIT_REJECTED_SCHEMA)

    def test_pathological_json_manifest_rejected_not_crash(self):
        """Second-pass fix: a deeply-nested manifest.json (json.load -> RecursionError, or a valid
        non-dict) is a documented REJECTED_SCHEMA, never an uncaught exit-1 traceback."""
        doc_id = 'doc-' + '0' * 16
        d = os.path.join(self.redacted, doc_id); os.makedirs(d)
        with open(os.path.join(d, 'page-01.png'), 'wb') as f:
            f.write(b'PG')
        with open(os.path.join(d, 'manifest.json'), 'w') as f:
            f.write('[' * 200000 + ']' * 200000)  # pathological nesting
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=True)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_SCHEMA)

    def test_unreadable_redacted_page_rejected_not_crash(self):
        """Red-team fix: an unreadable source page (pre-copy hash) is a documented, path-free
        rejection — never an uncaught OSError -> exit-1 traceback leaking the --redacted path."""
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('running as root: chmod 000 does not restrict root reads')
        d = self._stage_clean_doc()
        pf = os.path.join(d, 'page-01.png')
        os.chmod(pf, 0)
        try:
            r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
            self.assertFalse(r['ok'])
            self.assertEqual(r['code'], A.EXIT_REJECTED_SCHEMA)
            self.assertNotIn('/', r['reason'])  # category only, no path
            self.assertFalse(os.path.isdir(os.path.join(self.approved, os.path.basename(d))))
        finally:
            os.chmod(pf, 0o644)

    def test_main_withholds_non_opaque_folder_names(self):
        """A hand-renamed or misfiled folder under --redacted is still rejected with the same exit,
        but its name — which can carry the never-API identifier — never reaches stdout, whole or in
        part; opaque doc ids in the same run still print, approved and rejected alike."""
        good = os.path.basename(self._stage_clean_doc(label='doc1'))
        tampered = self._stage_clean_doc(label='doc2')
        with open(os.path.join(tampered, 'page-01.png'), 'wb') as f:
            f.write(b'CHANGED-SINCE-EYEBALL')
        stage_non_opaque_folders(self.redacted, 'manifest.json')
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = A.main(['--redacted', self.redacted, '--approved', self.approved])
        out = buf.getvalue()
        self.assertEqual(code, A.EXIT_REJECTED_SCHEMA)  # worst of 20 (tamper) and 24 (schema)
        self.assertRegex(out, r'%s\s+APPROVED' % good)
        self.assertRegex(out, r'%s\s+REJECTED' % os.path.basename(tampered))
        for n in (1, 2):
            self.assertRegex(out, r'non-standard folder name #%d \(withheld\)\s+REJECTED' % n)
        self.assertEqual([f for f in NON_OPAQUE_FRAGMENTS if f in out], [])


# ---------------------------------------------------------------------------
# HO-09 item 1 — real-calendar DOB validation (before scheme arithmetic)
# ---------------------------------------------------------------------------
class CalendarDobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('inbox', 'render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        self.log = os.path.join(self.tmp.name, 'run-log.json')
        _langs_installed(self)

    def _base(self, **over):
        d = dict(inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
                 log=self.log, dob='1901-02-03', scheme='pl-id', label_token=None,
                 rules=('prefix', 'checksum', 'label'), dpi=300, lang='pol', max_iters=5)
        d.update(over); return argparse_namespace(d)

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_impossible_month_day_rejected(self, _w):
        errs = R.validate_args(self._base(dob='1901-99-99'))
        self.assertTrue(any('real calendar date' in e for e in errs))
        for e in errs:
            self.assertNotIn('1901-99-99', e)  # the DOB value is never echoed

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_invalid_leap_day_rejected(self, _w):
        errs = R.validate_args(self._base(dob='2005-02-29'))  # 2005 is not a leap year
        self.assertTrue(any('real calendar date' in e for e in errs))

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_valid_leap_day_accepted(self, _w):
        self.assertEqual(R.validate_args(self._base(dob='2004-02-29')), [])  # a real leap day

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_real_date_outside_scheme_century_rejected(self, _w):
        errs = R.validate_args(self._base(dob='1750-01-01'))  # real date, century uncovered
        self.assertTrue(any('century' in e for e in errs))
        for e in errs:
            self.assertNotIn('1750-01-01', e)


# ---------------------------------------------------------------------------
# HO-09 item 2 — strict, versioned document-manifest schema validation
# ---------------------------------------------------------------------------
class ManifestSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def _valid(self, label='m', flags=None, npages=1, **man_over):
        d = stage_valid_doc(self.tmp.name, label=label, flags=flags, npages=npages, **man_over)
        with open(os.path.join(d, 'manifest.json')) as f:
            return d, json.load(f)

    def _errs(self, man, d):
        return R.validate_document_manifest(man, d)

    def test_valid_manifest_passes(self):
        d, man = self._valid()
        self.assertEqual(self._errs(man, d), [])

    def test_unknown_schema_version_rejected_closed(self):
        d, man = self._valid(); man['schema_version'] = 2
        self.assertTrue(any('schema_version' in e for e in self._errs(man, d)))

    def test_wrong_kind_rejected(self):
        d, man = self._valid(); man['kind'] = 'run-log'
        self.assertTrue(any('kind' in e for e in self._errs(man, d)))

    def test_wrong_tool_rejected(self):
        d, man = self._valid(); man['tool'] = 'evil.py'
        self.assertTrue(any('tool identity' in e for e in self._errs(man, d)))

    def test_state_failed_not_approvable(self):
        d, man = self._valid(); man['state'] = 'FAILED'
        self.assertTrue(self._errs(man, d))

    def test_doc_directory_binding_mismatch(self):
        d, man = self._valid(); man['doc'] = 'doc-' + 'a' * 16  # dir basename differs
        self.assertTrue(any('does not match its directory' in e for e in self._errs(man, d)))

    def test_non_opaque_doc_id_rejected(self):
        d, man = self._valid(); man['doc'] = 'raw-source-stem'  # a source stem, not an opaque id
        # rename dir so the binding matches but the SHAPE is still non-opaque
        nd = os.path.join(self.tmp.name, man['doc']); os.rename(d, nd)
        self.assertTrue(any('non-opaque' in e for e in self._errs(man, nd)))

    def test_empty_pages_not_approvable(self):
        d, man = self._valid(); man['pages'] = []; man['n_pages'] = 0
        # remove the on-disk page so artifacts also match the empty set
        os.remove(os.path.join(d, 'page-01.png'))
        self.assertTrue(any('no pages to approve' in e for e in self._errs(man, d)))

    def test_n_pages_mismatch_rejected(self):
        d, man = self._valid(); man['n_pages'] = 99
        self.assertTrue(any('n_pages' in e for e in self._errs(man, d)))

    def test_expected_pages_mismatch_rejected(self):
        d, man = self._valid(); man['expected_pages'] = 2
        self.assertTrue(any('expected_pages' in e for e in self._errs(man, d)))

    def test_document_id_must_derive_from_input_hash(self):
        d, man = self._valid(); man['input_sha256'] = 'f' * 64
        self.assertTrue(any('bound to the input hash' in e for e in self._errs(man, d)))

    def test_page_number_gap_rejected(self):
        d, man = self._valid(npages=2)
        os.rename(os.path.join(d, 'page-02.png'), os.path.join(d, 'page-03.png'))
        man['pages'][1]['page'] = 3  # numbering 1,3 -> gap
        self.assertTrue(any('contiguous' in e for e in self._errs(man, d)))

    def test_duplicate_page_number_rejected(self):
        d, man = self._valid(npages=2)
        man['pages'][1]['page'] = 1  # 1,1
        os.remove(os.path.join(d, 'page-02.png'))
        self.assertTrue(any('duplicate' in e for e in self._errs(man, d)))

    def test_out_of_order_pages_rejected(self):
        d, man = self._valid(npages=2)
        man['pages'] = list(reversed(man['pages']))  # 2,1
        self.assertTrue(any('out of order' in e for e in self._errs(man, d)))

    def test_unknown_flag_rejected(self):
        d, man = self._valid(); man['pages'][0]['flags'] = ['BOGUS_FLAG']
        self.assertTrue(any('flag' in e for e in self._errs(man, d)))

    def test_unhashable_manifest_vocab_values_reject_without_typeerror(self):
        d, man = self._valid(label='bad-error'); man['error'] = {}
        self.assertTrue(any('error code' in e for e in self._errs(man, d)))
        d, man = self._valid(label='bad-flag'); man['pages'][0]['flags'] = [{}]
        self.assertTrue(any('flag' in e for e in self._errs(man, d)))
        d, man = self._valid(label='bad-reason'); man['pages'][0]['reasons'] = [[]]
        self.assertTrue(any('reason' in e for e in self._errs(man, d)))

    def test_extra_top_level_field_rejected(self):
        d, man = self._valid(); man['surprise'] = 1
        self.assertTrue(any('unknown top-level field' in e for e in self._errs(man, d)))

    def test_extra_page_field_rejected(self):
        d, man = self._valid(); man['pages'][0]['surprise'] = 1
        self.assertTrue(any('unknown field' in e for e in self._errs(man, d)))

    def test_unknown_reason_rejected(self):
        d, man = self._valid(); man['pages'][0]['reasons'] = ['id-evil']
        self.assertTrue(any('reason' in e for e in self._errs(man, d)))

    def test_convergence_flag_inconsistency_rejected(self):
        d, man = self._valid(); man['pages'][0]['flags'] = ['MASK_VERIFY_FAILED']
        man['pages'][0]['converged'] = True  # contradiction
        self.assertTrue(any('convergence' in e for e in self._errs(man, d)))

    def test_missing_required_field_rejected(self):
        d, man = self._valid(); del man['input_sha256']
        self.assertTrue(any('missing required field' in e for e in self._errs(man, d)))

    def test_malformed_run_id_rejected(self):
        d, man = self._valid(); man['run_id'] = 'r1'
        self.assertTrue(any('run_id' in e for e in self._errs(man, d)))

    def test_malformed_page_hash_rejected(self):
        d, man = self._valid(); man['pages'][0]['sha256'] = 'not-a-hash'
        self.assertTrue(any('page hash' in e for e in self._errs(man, d)))

    def test_bad_osd_deg_rejected(self):
        d, man = self._valid(); man['pages'][0]['osd_deg'] = 45
        self.assertTrue(any('osd_deg' in e for e in self._errs(man, d)))

    def test_malformed_osd_conf_rejected(self):
        for value in ('high', True, -0.1, float('inf'), float('nan')):
            d, man = self._valid(label='osd-%r' % value)
            man['pages'][0]['osd_conf'] = value
            self.assertTrue(any('osd_conf' in e for e in self._errs(man, d)), repr(value))

    def test_osd_unreliable_must_be_boolean_and_match_flag(self):
        d, man = self._valid(); man['pages'][0]['osd_unreliable'] = 'yes'
        self.assertTrue(any('osd_unreliable' in e for e in self._errs(man, d)))
        d, man = self._valid(label='osd-missing', flags=['OSD_UNRELIABLE'])
        del man['pages'][0]['osd_unreliable']
        self.assertTrue(any('osd_unreliable' in e for e in self._errs(man, d)))
        d, man = self._valid(label='osd-spurious')
        man['pages'][0]['osd_unreliable'] = True
        self.assertTrue(any('osd_unreliable' in e for e in self._errs(man, d)))

    def test_unknown_error_code_rejected(self):
        d, man = self._valid(state='FAILED', error='WEIRD_ERROR', pages=[], n_pages=0)
        os.remove(os.path.join(d, 'page-01.png'))
        self.assertTrue(any('error code' in e for e in R.validate_document_manifest(man, d, require_awaiting=False)))

    def test_symlink_page_artifact_rejected(self):
        d, man = self._valid()
        pf = os.path.join(d, 'page-01.png'); os.remove(pf)
        os.symlink(os.path.join(self.tmp.name, 'elsewhere'), pf)  # dangling symlink named like a page
        self.assertTrue(any('symlink' in e for e in self._errs(man, d)))

    def test_extra_file_in_doc_dir_rejected(self):
        d, man = self._valid()
        with open(os.path.join(d, 'stray.txt'), 'w') as f:
            f.write('x')
        self.assertTrue(any('unexpected file' in e for e in self._errs(man, d)))

    def test_symlinked_doc_dir_rejected(self):
        d, man = self._valid()
        link = d + '-link'; os.symlink(d, link)
        self.assertTrue(any('symlink' in e for e in R.validate_document_manifest(man, link)))


# ---------------------------------------------------------------------------
# HO-09 item 4 — honest OSD failure (osd() unit-level truthfulness)
# ---------------------------------------------------------------------------
class OsdHonestyTests(unittest.TestCase):
    def _osd(self, rc, out, err=''):
        with mock.patch('redact_ids.subprocess.run',
                        return_value=subprocess.CompletedProcess([], rc, out, err)):
            return R.osd('page.png')

    def test_nonzero_return_is_unreliable(self):
        self.assertEqual(self._osd(1, 'Rotate: 0\nOrientation confidence: 5.0\n')[2], True)

    def test_zero_return_empty_output_is_unreliable(self):
        self.assertEqual(self._osd(0, '', '')[2], True)

    def test_malformed_rotation_is_unreliable(self):
        self.assertEqual(self._osd(0, 'Rotate: sideways\nOrientation confidence: 5.0\n')[2], True)

    def test_missing_confidence_is_unreliable(self):
        self.assertEqual(self._osd(0, 'Rotate: 90\n')[2], True)

    def test_invalid_rotation_value_is_unreliable(self):
        self.assertEqual(self._osd(0, 'Rotate: 45\nOrientation confidence: 5.0\n')[2], True)

    def test_clean_osd_is_reliable(self):
        self.assertEqual(self._osd(0, 'Rotate: 90\nOrientation confidence: 7.5\n'), (90, 7.5, False))

    def test_unsure_turn_is_unreliable(self):
        self.assertEqual(self._osd(0, 'Rotate: 90\nOrientation confidence: 0.8\n'), (90, 0.8, True))

    def test_unsure_upright_is_reliable(self):
        self.assertEqual(self._osd(0, 'Rotate: 0\nOrientation confidence: 0.8\n'), (0, 0.8, False))

    def test_return_code_outside_allow_raises_then_unreliable(self):
        self.assertEqual(self._osd(99, '')[2], True)


# ---------------------------------------------------------------------------
# HO-09 item 6 — verify_approved.py pre-consumption integrity gate
# ---------------------------------------------------------------------------
class VerifyApprovedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.redacted = os.path.join(self.tmp.name, 'redacted')
        self.approved = os.path.join(self.tmp.name, 'approved')

    def _approve(self, npages=1):
        d = stage_valid_doc(self.redacted, npages=npages)
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
        self.assertTrue(r['ok'], r)
        return os.path.join(self.approved, os.path.basename(d))

    def test_clean_verify_returns_exact_page_set(self):
        ad = self._approve(npages=2)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertTrue(r['ok'])
        self.assertEqual(r['pages'], [1, 2])

    def test_tamper_after_approval_rejected(self):
        ad = self._approve()
        with open(os.path.join(ad, 'page-01.png'), 'wb') as f:
            f.write(b'TAMPERED-AFTER-APPROVAL')
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_HASH)

    def test_later_failed_redaction_generation_revokes_prior_approval(self):
        ad = self._approve()
        doc = os.path.basename(ad)
        mp = os.path.join(self.redacted, doc, 'manifest.json')
        with open(mp) as f:
            man = json.load(f)
        man.update(state='FAILED', error='RENDER_FAILED', run_id='20260102T000000Z-0000abcd')
        R._atomic_write_json(mp, man)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)
        self.assertIn('current redacted generation', r['reason'])

    def test_later_hold_generation_revokes_prior_approval(self):
        ad = self._approve()
        doc = os.path.basename(ad)
        mp = os.path.join(self.redacted, doc, 'manifest.json')
        with open(mp) as f:
            man = json.load(f)
        man['run_id'] = '20260102T000000Z-0000abcd'
        man['pages'][0]['flags'] = ['OSD_UNRELIABLE']
        man['pages'][0]['osd_unreliable'] = True
        R._atomic_write_json(mp, man)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_same_run_manifest_rewrite_revokes_prior_approval(self):
        ad = self._approve()
        doc = os.path.basename(ad)
        mp = os.path.join(self.redacted, doc, 'manifest.json')
        with open(mp) as f:
            man = json.load(f)
        man['notes'] = ['synthetic rewrite with the same run id']
        R._atomic_write_json(mp, man)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_current_page_hash_set_change_revokes_prior_approval(self):
        ad = self._approve()
        doc = os.path.basename(ad)
        current_page = os.path.join(self.redacted, doc, 'page-01.png')
        with open(current_page, 'wb') as fh:
            fh.write(b'NEW-CURRENT-GENERATION-PAGE')
        mp = os.path.join(self.redacted, doc, 'manifest.json')
        with open(mp) as f:
            man = json.load(f)
        man['pages'][0]['sha256'] = R._sha256_file(current_page)
        R._atomic_write_json(mp, man)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_current_fifo_manifest_rejects_without_blocking_open(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        ad = self._approve()
        manifest = os.path.join(self.redacted, os.path.basename(ad), 'manifest.json')
        os.remove(manifest); os.mkfifo(manifest)
        real_open = open
        def guarded_open(path, *args, **kwargs):
            if os.fspath(path) == manifest:
                raise AssertionError('a non-regular current manifest must be rejected before open')
            return real_open(path, *args, **kwargs)
        with mock.patch('builtins.open', side_effect=guarded_open):
            result = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(result['ok'])
        self.assertEqual(result['code'], V.EXIT_SCHEMA)

    def test_tampered_flag_acknowledgement_rejected(self):
        d = stage_valid_doc(self.redacted, flags=['NEAR_EMPTY_OCR'])
        approved = A.approve_one(os.path.join(d, 'manifest.json'), self.approved,
                                 accept_flagged=True, accept_flags={'NEAR_EMPTY_OCR'})
        self.assertTrue(approved['ok'], approved)
        ad = os.path.join(self.approved, os.path.basename(d))
        ap = os.path.join(ad, 'approval.json')
        with open(ap) as fh:
            app = json.load(fh)
        app['flags_present_at_approval'] = []
        app['accepted_flagged'] = False
        R._atomic_write_json(ap, app)
        r = V.verify_one(ap, self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_swap_after_approval_rejected(self):
        ad = self._approve(npages=2)
        p1, p2 = os.path.join(ad, 'page-01.png'), os.path.join(ad, 'page-02.png')
        with open(p1, 'rb') as f: b1 = f.read()
        with open(p2, 'rb') as f: b2 = f.read()
        with open(p1, 'wb') as f: f.write(b2)
        with open(p2, 'wb') as f: f.write(b1)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertEqual(r['code'], V.EXIT_HASH)

    def test_deleted_page_after_approval_rejected(self):
        ad = self._approve(npages=2)
        os.remove(os.path.join(ad, 'page-02.png'))
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertEqual(r['code'], V.EXIT_ARTIFACT)

    def test_extra_file_after_approval_rejected(self):
        ad = self._approve()
        with open(os.path.join(ad, 'page-99.png'), 'wb') as f:
            f.write(b'INJECTED')
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertEqual(r['code'], V.EXIT_ARTIFACT)

    def test_symlink_page_after_approval_rejected(self):
        ad = self._approve()
        pf = os.path.join(ad, 'page-01.png'); os.remove(pf)
        os.symlink(os.path.join(self.tmp.name, 'evil'), pf)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertEqual(r['code'], V.EXIT_ARTIFACT)

    def test_symlinked_approved_dir_rejected(self):
        ad = self._approve()
        link = ad + '-link'; os.symlink(ad, link)
        r = V.verify_one(os.path.join(link, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])

    def test_symlinked_approval_json_rejected(self):
        ad = self._approve()
        real = os.path.join(ad, 'approval.json')
        moved = os.path.join(self.tmp.name, 'moved-approval.json')
        os.rename(real, moved); os.symlink(moved, real)
        r = V.verify_one(real, self.redacted)
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_malformed_approval_schema_rejected(self):
        ad = self._approve()
        with open(os.path.join(ad, 'approval.json')) as f:
            app = json.load(f)
        app['kind'] = 'not-an-approval'
        R._atomic_write_json(os.path.join(ad, 'approval.json'), app)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_unhashable_approval_flag_rejected_without_typeerror(self):
        ad = self._approve()
        ap = os.path.join(ad, 'approval.json')
        with open(ap) as f:
            app = json.load(f)
        app['flags_present_at_approval'] = [{}]
        R._atomic_write_json(ap, app)
        r = V.verify_one(ap, self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_duplicate_key_approval_rejected(self):
        ad = self._approve()
        ap = os.path.join(ad, 'approval.json')
        with open(ap, 'rb') as f:
            body = f.read()
        with open(ap, 'wb') as f:
            f.write(body[:-2] + b', "kind": "approval-attestation"}\n')
        self.assertEqual(V.verify_one(ap, self.redacted)['code'], V.EXIT_SCHEMA)

    def test_unreadable_page_rejected_no_traceback_no_path(self):
        """Red-team fix: an unreadable (or TOCTOU-vanished) approved page must be a documented,
        path-free rejection at the pre-consumption gate — never an uncaught OSError -> exit-1
        traceback that leaks the page path (the exact model-visible surface HO-09 protects)."""
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('running as root: chmod 000 does not restrict root reads')
        ad = self._approve()
        pf = os.path.join(ad, 'page-01.png')
        os.chmod(pf, 0)
        try:
            r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
            self.assertFalse(r['ok'])
            self.assertEqual(r['code'], V.EXIT_ARTIFACT)
            self.assertNotIn('/', r['reason'])  # category only, no path
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = V.main(['--approved', self.approved, '--redacted', self.redacted])
            self.assertEqual(code, V.EXIT_ARTIFACT)
            self.assertNotIn('Traceback', buf.getvalue())
            self.assertNotIn(pf, buf.getvalue())
        finally:
            os.chmod(pf, 0o644)  # restore so tempdir cleanup succeeds

    def test_pathological_json_approval_rejected_not_crash(self):
        """Second-pass fix: a deeply-nested approval.json (json.load -> RecursionError, or a valid
        non-dict) is a documented EXIT_SCHEMA rejection at the integrity gate, never an exit-1 crash."""
        ad = self._approve()
        with open(os.path.join(ad, 'approval.json'), 'w') as f:
            f.write('[' * 200000 + ']' * 200000)
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], V.EXIT_SCHEMA)

    def test_main_end_to_end_green(self):
        self._approve()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = V.main(['--approved', self.approved, '--redacted', self.redacted])
        self.assertEqual(code, V.EXIT_VERIFIED)
        self.assertIn('VERIFIED', buf.getvalue())

    def test_main_nothing_to_verify(self):
        os.makedirs(self.approved)
        os.makedirs(self.redacted)
        with contextlib.redirect_stdout(io.StringIO()):
            code = V.main(['--approved', self.approved, '--redacted', self.redacted])
        self.assertEqual(code, V.EXIT_NOTHING)

    def test_main_rejects_non_opaque_doc(self):
        self._approve()
        with contextlib.redirect_stdout(io.StringIO()):
            code = V.main(['--approved', self.approved, '--redacted', self.redacted,
                           '--doc', 'patient-smith'])
        self.assertEqual(code, V.EXIT_INVALID_INVOCATION)

    def test_main_withholds_non_opaque_folder_names(self):
        """A hand-renamed or misfiled folder under --approved is still rejected with the same exit,
        but its name — which can carry the never-API identifier — never reaches stdout, whole or in
        part; opaque doc ids in the same run still print, verified and rejected alike."""
        good = os.path.basename(self._approve())
        d2 = stage_valid_doc(self.redacted, label='doc2')
        self.assertTrue(A.approve_one(os.path.join(d2, 'manifest.json'), self.approved,
                                      accept_flagged=False)['ok'])
        tampered = os.path.basename(d2)
        with open(os.path.join(self.approved, tampered, 'page-01.png'), 'wb') as f:
            f.write(b'TAMPERED-AFTER-APPROVAL')
        stage_non_opaque_folders(self.approved, 'approval.json')
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = V.main(['--approved', self.approved, '--redacted', self.redacted])
        out = buf.getvalue()
        self.assertEqual(code, V.EXIT_HASH)  # worst of 30 (schema) and 31 (tamper)
        self.assertRegex(out, r'VERIFIED\s+%s\s+pages=\[1\]' % good)
        self.assertRegex(out, r'REJECTED\s+%s' % tampered)
        for n in (1, 2):
            self.assertRegex(out, r'REJECTED\s+non-standard folder name #%d \(withheld\)' % n)
        self.assertEqual([f for f in NON_OPAQUE_FRAGMENTS if f in out], [])

    def test_main_non_opaque_folder_alone_keeps_exit_30(self):
        """The reproduced shape: only a non-opaque folder with an empty-object approval.json and an
        empty --redacted root — still exit 30, its name withheld."""
        os.makedirs(self.redacted)
        stage_non_opaque_folders(self.approved, 'approval.json')
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = V.main(['--approved', self.approved, '--redacted', self.redacted])
        self.assertEqual(code, V.EXIT_SCHEMA)
        self.assertEqual([f for f in NON_OPAQUE_FRAGMENTS if f in buf.getvalue()], [])


# ---------------------------------------------------------------------------
# HO-09 item 3 — opaque doc ids: zero source-name residue on model-visible surfaces
# ---------------------------------------------------------------------------
class DobFromIdentity(unittest.TestCase):
    """Masking for a person who keeps their date of birth from the AI: the tool reads it itself, so no session
    writes it. The rest of the walk: StrangerWalk in test_identity.py."""
    DOB = '1901-02-03'                                  # gives PREFIX

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('inbox', 'render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        self.log = os.path.join(self.tmp.name, 'run-log.json')
        with open(os.path.join(self.inbox, 'doc1.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')
        self.person = os.path.join(self.tmp.name, 'patients', 'szt-kept')
        os.makedirs(self.person)
        with open(os.path.join(self.person, 'profile.md'), 'w', encoding='utf-8') as f:
            f.write('- Private mode: synthetic ⟨never-API⟩\n')

    def _record_dob(self):
        import identity
        data = identity.empty()
        data['classes']['dob'] = [{'value': self.DOB, 'since': '2026-10-01'}]
        identity.write(self.person, data)

    def _main(self, *dob_args):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        self.reads = 0

        def tesseract(cmd):
            if cmd[2] == 'stdout':
                return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
            self.reads += 1
            extra = [W('01020312340', 100, 2000, line=('99', '1', '1'))] if self.reads == 1 else []
            _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        router.set('tesseract', tesseract)
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        self.router = router
        buf = io.StringIO()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', side_effect=lambda n: '/usr/bin/' + n if n in ('pdftoppm', 'tesseract') else None), \
             mock.patch('redact_ids._im', return_value={'convert': ['convert'], 'identify': ['identify']}), \
             contextlib.redirect_stdout(buf):
            code = R.main(['--inbox', self.inbox, '--render', self.render, '--work', self.work,
                           '--redacted', self.redacted, '--log', self.log, '--scheme', 'pl-id'] + list(dob_args))
        return code, buf.getvalue()

    def test_the_tool_uses_the_recorded_date_and_prints_it_nowhere(self):
        self._record_dob()
        argv = ['--dob-from-identity', self.person]
        code, stdout = self._main(*argv)
        self.assertEqual(code, R.EXIT_OK_AWAITING_OPERATOR)
        docs = [x for x in os.listdir(self.redacted) if x.startswith('doc-')]
        with open(os.path.join(self.redacted, docs[0], 'manifest.json')) as f:
            manifest = f.read()
        self.assertIn('id-prefix', manifest)            # only the recorded date could have given this prefix
        with open(self.log) as f:
            log_text = f.read()
        tool_lines = '\n'.join(' '.join(c) for c in self.router.calls)
        for text in (stdout, log_text, manifest, tool_lines, ' '.join(argv)):
            self.assertNotIn(self.DOB, text)
            self.assertNotIn(PREFIX, text)

    def test_no_identity_file_stops_before_any_tool_runs(self):
        code, stdout = self._main('--dob-from-identity', self.person)
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn('no date of birth is recorded', stdout)
        self.assertEqual(self.router.calls, [])

    def test_exactly_one_source_for_the_date(self):
        self._record_dob()
        for argv in ([], ['--dob', self.DOB, '--dob-from-identity', self.person]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self._main(*argv)


class SanitizedObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('inbox', 'render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        self.log = os.path.join(self.tmp.name, 'run-log.json')

    def _clean_router(self):
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        return router

    def test_identifier_shaped_filename_leaves_no_residue(self):
        """A source filename that IS the never-API identifier must not appear in stdout, the run
        log, or the on-disk manifest — only in the explicit LOCAL never-API map (HO-09 item 3)."""
        ID = '44051401359'  # synthetic checksum-valid identifier, used here only as a FILENAME
        with open(os.path.join(self.inbox, ID + '.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')
        router = self._clean_router()

        def fake_which(name):
            return '/usr/bin/' + name if name in ('pdftoppm', 'tesseract') else None

        buf = io.StringIO()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', side_effect=fake_which), \
             mock.patch('redact_ids._im', return_value={'convert': ['convert'], 'identify': ['identify']}), \
             contextlib.redirect_stdout(buf):
            code = R.main(['--inbox', self.inbox, '--render', self.render, '--work', self.work,
                           '--redacted', self.redacted, '--log', self.log, '--dob', '1901-02-03', '--scheme', 'pl-id'])
        self.assertEqual(code, R.EXIT_OK_AWAITING_OPERATOR)

        stdout = buf.getvalue()
        with open(self.log) as f:
            log_text = f.read()
        doc_dirs = [x for x in os.listdir(self.redacted) if not x.startswith('.')]
        self.assertEqual(len(doc_dirs), 1)
        with open(os.path.join(self.redacted, doc_dirs[0], 'manifest.json')) as f:
            manifest_text = f.read()

        self.assertNotIn(ID, stdout, 'identifier-shaped filename leaked to stdout')
        self.assertNotIn(ID, log_text, 'identifier-shaped filename leaked to the run log')
        self.assertNotIn(ID, manifest_text, 'identifier-shaped filename leaked to the manifest')
        # run log carries NO absolute paths either (path components can carry the identifier)
        for p in (self.inbox, self.redacted, self.render, self.work):
            self.assertNotIn(p, log_text)
        # the ONE explicit place the raw name is allowed: the LOCAL, never-API map
        map_path = os.path.join(self.redacted, R.NEVER_API_MAP_NAME)
        self.assertTrue(os.path.isfile(map_path))
        with open(map_path) as f:
            self.assertIn(ID, f.read())
        self.assertEqual(doc_dirs[0], 'doc-' + R._sha256_file(
            os.path.join(self.inbox, ID + '.pdf'))[:16])

    def test_residue_selfcheck_raises_on_leak(self):
        with self.assertRaises(RuntimeError):
            R._assert_no_name_residue([{'doc': 'doc-x', 'note': 'leaked 44051401359.pdf here'}],
                                      {'doc-x': '44051401359.pdf'})

    def test_residue_selfcheck_raises_on_extension_less_identifier_stem(self):
        """Second-pass fix: a scan named after the identifier, leaked WITHOUT its .pdf extension
        (a bare '44051401359'), is still caught by the identifier-shaped-stem arm — while ordinary
        names like document.pdf do not false-trip (covered by the no-false-positive test)."""
        with self.assertRaises(RuntimeError):
            R._assert_no_name_residue([{'doc': 'doc-z', 'notes': ['44051401359']}],
                                      {'doc-z': '44051401359.pdf'})

    def test_residue_selfcheck_raises_on_non_ascii_leak(self):
        """Red-team fix: a non-ASCII source filename is escaped (\\uXXXX) when serialized, so the
        backstop must escape the needle the same way — a raw-string search would miss the exact
        (Polish-name) population the tool most needs to catch."""
        bn = 'zażółć.pdf'  # canonical synthetic Polish diacritic test string (ż/ó/ł/ć); not a name
        blob_rec = json.loads(json.dumps({'doc': 'doc-y', 'note': 'could not read ' + bn}))
        with self.assertRaises(RuntimeError):
            R._assert_no_name_residue([blob_rec], {'doc-y': bn})

    def test_residue_selfcheck_no_false_positive_on_structural_names(self):
        """Red-team fix: ordinary scan/download names whose STEM is a substring of the manifest's
        structural scaffolding (document -> 'document-manifest', notes/pages/state/error keys) must
        NOT false-trip — the needle is the full basename (ends in .pdf), absent from the scaffolding."""
        rec = dict(schema_version=R.SCHEMA_VERSION, kind='document-manifest', tool=R.TOOL_NAME,
                   run_id=SYN_RUN, doc='doc-' + '0' * 16, input_sha256='0' * 64, n_pages=0,
                   expected_pages=None, pages=[], error=None, notes=[], state='AWAITING_OPERATOR')
        for name in ('document.pdf', 'notes.pdf', 'pages.pdf', 'state.pdf', 'error.pdf',
                     'manifest.pdf', 'redact.pdf'):
            R._assert_no_name_residue([rec], {rec['doc']: name})  # must not raise

    def test_doc_labels_echo_only_the_exact_opaque_form(self):
        opaque = 'doc-0123456789abcdef'
        self.assertEqual(
            R.doc_labels([opaque, 'synthetic-private-label', opaque + '\n', 'DOC-0123456789ABCDEF']),
            [opaque] + ['non-standard folder name #%d (withheld)' % n for n in (1, 2, 3)])

    def test_residue_selfcheck_passes_when_clean(self):
        R._assert_no_name_residue([{'doc': 'doc-abc', 'input_sha256': '0' * 64}],
                                  {'doc-abc': '44051401359.pdf'})  # must not raise

    def test_common_and_non_ascii_filenames_run_clean_end_to_end(self):
        """Regression for the residue false-positive: a clean run on a common name ('document.pdf')
        and on a non-ASCII name must both reach exit 0 (AWAITING_OPERATOR), write the run log, and
        keep the raw name only in the local never-API map — never abort with a phantom exit 65."""
        def fake_which(name):
            return '/usr/bin/' + name if name in ('pdftoppm', 'tesseract') else None
        for fname in ('document.pdf', 'zażółć.pdf'):  # 2nd = canonical synthetic Polish diacritic string
            inbox = os.path.join(self.tmp.name, 'in-' + fname); os.makedirs(inbox)
            redacted = os.path.join(self.tmp.name, 'red-' + fname); os.makedirs(redacted)
            render = os.path.join(self.tmp.name, 'ren-' + fname); os.makedirs(render)
            work = os.path.join(self.tmp.name, 'wk-' + fname); os.makedirs(work)
            log = os.path.join(self.tmp.name, 'log-' + fname + '.json')
            with open(os.path.join(inbox, fname), 'wb') as f:
                f.write(b'%PDF-FAKE-' + fname.encode())
            router = self._clean_router()
            with mock.patch('redact_ids.subprocess.run', side_effect=router), \
                 mock.patch('redact_ids.shutil.which', side_effect=fake_which), \
                 mock.patch('redact_ids._im', return_value={'convert': ['convert'], 'identify': ['identify']}), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = R.main(['--inbox', inbox, '--render', render, '--work', work,
                               '--redacted', redacted, '--log', log, '--dob', '1901-02-03', '--scheme', 'pl-id'])
            self.assertEqual(code, R.EXIT_OK_AWAITING_OPERATOR, fname)
            self.assertTrue(os.path.isfile(log), 'run log must be written for ' + fname)
            # the raw name lives ONLY in the local never-API map (stored escaped like every surface;
            # json.load decodes it back) — decode and check the value, not the raw file text
            with open(os.path.join(redacted, R.NEVER_API_MAP_NAME)) as f:
                self.assertIn(fname, json.load(f)['map'].values())


# ---------------------------------------------------------------------------
# HO-09 item 7 — crash-safe writes, rollback-safe promotion, symlink refusal
# ---------------------------------------------------------------------------
class CrashSafePromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def _pair(self):
        final = os.path.join(self.tmp.name, 'out', 'doc'); os.makedirs(final)
        with open(os.path.join(final, 'page-01.png'), 'wb') as f:
            f.write(b'PRIOR-KNOWN-GOOD')
        stage = os.path.join(self.tmp.name, 'stage'); os.makedirs(stage)
        with open(os.path.join(stage, 'page-01.png'), 'wb') as f:
            f.write(b'NEW-STAGED')
        return stage, final

    def test_second_rename_failure_restores_prior_live_set(self):
        """If the prior live set was moved aside and the staging rename then fails, the prior live
        set is RESTORED — never left stranded with an empty live path (HO-09 item 7)."""
        stage, final = self._pair()
        real_rename = os.rename

        def flaky(src, dst):
            if os.path.abspath(src) == os.path.abspath(stage):
                raise OSError('injected staging-rename failure')
            return real_rename(src, dst)

        with mock.patch('redact_ids.os.rename', side_effect=flaky):
            with self.assertRaises(OSError):
                R._promote_dir(stage, final)
        self.assertTrue(os.path.isfile(os.path.join(final, 'page-01.png')))
        with open(os.path.join(final, 'page-01.png'), 'rb') as f:
            self.assertEqual(f.read(), b'PRIOR-KNOWN-GOOD')  # last known-good never lost

    def test_first_rename_failure_leaves_prior_untouched(self):
        stage, final = self._pair()
        real_rename = os.rename

        def flaky(src, dst):
            if os.path.abspath(src) == os.path.abspath(final):
                raise OSError('injected move-aside failure')
            return real_rename(src, dst)

        with mock.patch('redact_ids.os.rename', side_effect=flaky):
            with self.assertRaises(OSError):
                R._promote_dir(stage, final)
        with open(os.path.join(final, 'page-01.png'), 'rb') as f:
            self.assertEqual(f.read(), b'PRIOR-KNOWN-GOOD')

    def test_promote_refuses_symlinked_destination(self):
        stage, final = self._pair()
        os.rename(final, final + '-real')
        os.symlink(final + '-real', final)
        with self.assertRaises(RuntimeError):
            R._promote_dir(stage, final)

    def test_promote_refuses_same_path_alias(self):
        stage = os.path.join(self.tmp.name, 's'); os.makedirs(stage)
        with self.assertRaises(RuntimeError):
            R._promote_dir(stage, stage)

    def test_run_log_write_failure_maps_to_exit_65(self):
        """A run-log write failure (disk full / fsync/replace) after documents were promoted must
        map to the documented exit 65 with a sanitized line — never a traceback or exit 1."""
        inbox = os.path.join(self.tmp.name, 'inbox'); os.makedirs(inbox)
        render = os.path.join(self.tmp.name, 'render'); os.makedirs(render)
        work = os.path.join(self.tmp.name, 'work'); os.makedirs(work)
        redacted = os.path.join(self.tmp.name, 'redacted'); os.makedirs(redacted)
        log = os.path.join(self.tmp.name, 'log.json')
        with open(os.path.join(inbox, 'd.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')
        router = ToolRouter()
        router.set('pdftoppm', _default_pdftoppm(n_pages=1))
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        real_awj = R._atomic_write_json

        def flaky_awj(path, obj):
            if os.path.abspath(path) == os.path.abspath(log):
                raise OSError('injected run-log write failure')
            return real_awj(path, obj)

        def fake_which(name):
            return '/usr/bin/' + name if name in ('pdftoppm', 'tesseract') else None

        buf = io.StringIO()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', side_effect=fake_which), \
             mock.patch('redact_ids._im', return_value={'convert': ['convert'], 'identify': ['identify']}), \
             mock.patch('redact_ids._atomic_write_json', side_effect=flaky_awj), \
             contextlib.redirect_stdout(buf):
            code = R.main(['--inbox', inbox, '--render', render, '--work', work,
                           '--redacted', redacted, '--log', log, '--dob', '1901-02-03', '--scheme', 'pl-id'])
        self.assertEqual(code, R.EXIT_STATE_ERROR)
        self.assertNotIn('Traceback', buf.getvalue())
        # the document WAS promoted; only the log failed (documented recoverable state)
        self.assertTrue([x for x in os.listdir(redacted) if not x.startswith('.')])

    def test_approve_copy_failure_rejects_and_publishes_nothing(self):
        redacted = os.path.join(self.tmp.name, 'redacted')
        approved = os.path.join(self.tmp.name, 'approved')
        d = stage_valid_doc(redacted)
        with mock.patch('approve_redaction.shutil.copyfileobj', side_effect=OSError('injected copy failure')):
            r = A.approve_one(os.path.join(d, 'manifest.json'), approved, accept_flagged=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['code'], A.EXIT_REJECTED_ERROR)
        self.assertFalse(os.path.isdir(os.path.join(approved, os.path.basename(d))))


# ---------------------------------------------------------------------------
# HO-09 items 1/14 — symlinked input / roots refused at the redact boundary
# ---------------------------------------------------------------------------
class SymlinkInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('inbox', 'render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        self.log = os.path.join(self.tmp.name, 'log.json')

    def _args(self, **over):
        d = dict(inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
                 dob='1901-02-03', scheme='pl-id', label_token=None,
                 rules=('prefix', 'checksum', 'label'), dpi=300, lang='pol', max_iters=3, prefix=PREFIX)
        d.update(over); return argparse_namespace(d)

    def test_symlinked_input_pdf_rejected(self):
        target = os.path.join(self.tmp.name, 'outside-target.pdf')
        with open(target, 'wb') as f:
            f.write(b'%PDF-FAKE')
        os.symlink(target, os.path.join(self.inbox, 'link.pdf'))
        results, run_id, code, run_result = R.run_pipeline(self._args())
        self.assertEqual(run_result, 'ERROR')
        self.assertEqual(results[0]['error'], 'SYMLINK_REJECTED')
        self.assertRegex(results[0]['doc'], r'^doc-[0-9a-f]{16}$')

    def test_nonregular_input_pdf_rejected_without_opening(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        os.mkfifo(os.path.join(self.inbox, 'blocking.pdf'))
        with mock.patch('redact_ids._sha256_file',
                        side_effect=AssertionError('non-regular input must be rejected before hashing')):
            results, run_id, code, run_result = R.run_pipeline(self._args())
        self.assertEqual(run_result, 'ERROR')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertEqual(results[0]['error'], 'PROCESS_ERROR')

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_symlinked_root_rejected(self, _w):
        realdir = os.path.join(self.tmp.name, 'real-inbox'); os.makedirs(realdir)
        link = os.path.join(self.tmp.name, 'inbox-link'); os.symlink(realdir, link)

        class NS: pass
        a = NS()
        for k, v in dict(inbox=link, render=self.render, work=self.work, redacted=self.redacted,
                         log=self.log, dob='1901-02-03', scheme='pl-id', label_token=None,
                         rules=('prefix', 'checksum', 'label'), dpi=300, lang='pol', max_iters=5).items():
            setattr(a, k, v)
        errs = R.validate_args(a)
        self.assertTrue(any('symlink' in e for e in errs))


class _Alarm:
    """Bounded-time guard for tests whose FAILURE mode is a hang (e.g. a FIFO open that lost
    O_NONBLOCK): converts the hang into a red test instead of wedging the ADR-0022 pre-commit
    hook, which runs this suite with its output captured (see the selftest hook-hang class)."""

    def __init__(self, seconds=10):
        self.seconds = seconds

    def __enter__(self):
        import signal
        self._signal = signal

        def _fire(signum, frame):
            raise AssertionError('operation blocked — a no-block/no-follow guard has regressed')
        self._old = signal.signal(signal.SIGALRM, _fire)
        signal.alarm(self.seconds)
        return self

    def __exit__(self, *exc):
        self._signal.alarm(0)
        self._signal.signal(self._signal.SIGALRM, self._old)
        return False


class BoundedReaderTests(unittest.TestCase):
    """The STREAMING half of the workload bounds — the half that exists for a file growing between
    fstat and read. Direct negative controls: deleting either streaming check reds these even
    though every other bounds test happens to be satisfied by the fstat pre-check."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def test_read_fd_bounded_rejects_past_bound_while_reading(self):
        p = os.path.join(self.tmp.name, 'blob')
        with open(p, 'wb') as f:
            f.write(b'x' * 100)
        fd = os.open(p, os.O_RDONLY)
        try:
            with self.assertRaises(ValueError):
                R._read_fd_bounded(fd, 10)     # no fstat pre-check involved: the stream must refuse
        finally:
            os.close(fd)
        fd = os.open(p, os.O_RDONLY)
        try:
            self.assertEqual(R._read_fd_bounded(fd, 100), b'x' * 100)  # exactly-at-bound passes
        finally:
            os.close(fd)

    def test_snapshot_streaming_bound_catches_growth_past_fstat(self):
        """Defeat the fstat pre-check (the file 'grew' after fstat under-reported it) and prove the
        hash-while-copy loop still refuses — and that the mid-copy failure path leaves no partial
        snapshot behind (the cleanup branch the pre-check rejection never exercises)."""
        src = os.path.join(self.tmp.name, 'grow.pdf')
        with open(src, 'wb') as f:
            f.write(b'x' * 64)
        snap_dir = os.path.join(self.tmp.name, 'snaps'); os.makedirs(snap_dir)
        real_fstat = os.fstat

        def underreporting_fstat(fd):
            st = real_fstat(fd)
            return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid,
                                   st.st_gid, 4, st.st_atime, st.st_mtime, st.st_ctime))

        with mock.patch.object(R, 'MAX_INPUT_PDF_BYTES', 16), \
             mock.patch('redact_ids.os.fstat', side_effect=underreporting_fstat):
            with self.assertRaises(ValueError):
                R._snapshot_input(src, snap_dir)
        self.assertEqual(os.listdir(snap_dir), [])   # partial snapshot unlinked on the failure path


class InputSnapshotTests(unittest.TestCase):
    """The redactor consumes an immutable run-owned snapshot of each input, never
    the mutable inbox path after the initial hash-while-copy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.inbox = os.path.join(self.tmp.name, 'inbox'); os.makedirs(self.inbox)
        self.render = os.path.join(self.tmp.name, 'render'); os.makedirs(self.render)
        self.work = os.path.join(self.tmp.name, 'work'); os.makedirs(self.work)
        self.redacted = os.path.join(self.tmp.name, 'redacted'); os.makedirs(self.redacted)
        self.pdf = os.path.join(self.inbox, 'doc1.pdf')
        self.orig_bytes = b'%PDF-FAKE-SNAPSHOT-FIXTURE'
        with open(self.pdf, 'wb') as f:
            f.write(self.orig_bytes)
        R.IM = dict(convert=['convert'], identify=['identify'])

    def _args(self):
        a = argparse_namespace(dict(
            inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
            dob='1901-02-03', scheme='pl-id', label_token=None,
            rules=('prefix', 'checksum', 'label'), dpi=300, lang='pol', max_iters=3,
            prefix=PREFIX))
        return a

    def _run(self, router):
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', return_value=None):
            return R.run_pipeline(self._args())

    def _manifest(self):
        dirs = [d for d in os.listdir(self.redacted)
                if not d.startswith('.') and os.path.isdir(os.path.join(self.redacted, d))]
        self.assertEqual(len(dirs), 1)
        with open(os.path.join(self.redacted, dirs[0], 'manifest.json')) as f:
            return json.load(f)

    def test_render_consumes_the_snapshot_not_the_inbox_path(self):
        rendered = {}

        def capturing_pdftoppm(cmd):
            with open(cmd[-2], 'rb') as f:      # capture in-flight: the snapshot is unlinked
                rendered['bytes'] = f.read()    # at end-of-document (raw-PII lifecycle)
            with open(cmd[-1] + '-01.png', 'wb') as f:
                f.write(b'PNGDATA')
            return subprocess.CompletedProcess(cmd, 0, '', '')

        router = ToolRouter()
        router.set('pdftoppm', capturing_pdftoppm)
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        _, _, code, run_result = self._run(router)
        self.assertEqual(run_result, 'CLEAN')
        render_calls = [c for c in router.calls if os.path.basename(c[0]) == 'pdftoppm']
        self.assertEqual(len(render_calls), 1)
        rendered_input = render_calls[0][-2]
        self.assertNotEqual(os.path.abspath(rendered_input), os.path.abspath(self.pdf))
        self.assertIn(os.sep + 'input-snapshots' + os.sep, rendered_input)
        # opaque snapshot name — carries no byte of the source filename (HO-09 item 3)
        self.assertRegex(os.path.basename(rendered_input), r'^in-[0-9a-f]{16}\.pdf$')
        self.assertEqual(rendered['bytes'], self.orig_bytes)
        self.assertEqual(self._manifest()['input_sha256'],
                         hashlib.sha256(self.orig_bytes).hexdigest())
        # end-of-document cleanup: no raw-identifier snapshot copy survives the run
        self.assertEqual(glob.glob(os.path.join(self.work, '*', 'input-snapshots', '*')), [])

    def test_inbox_mutation_after_snapshot_binds_the_snapshot(self):
        """Change the inbox source while the pipeline runs: manifest hash, doc id and rendered
        bytes must bind the snapshot taken at intake, never a later reopen of the inbox path."""
        rendered_from = {}

        def mutating_pdftoppm(cmd):
            with open(cmd[-2], 'rb') as f:
                rendered_from['bytes'] = f.read()
            with open(self.pdf, 'wb') as f:
                f.write(b'%PDF-MUTATED-AFTER-SNAPSHOT')
            with open(cmd[-1] + '-01.png', 'wb') as f:
                f.write(b'PNGDATA')
            return subprocess.CompletedProcess(cmd, 0, '', '')

        router = ToolRouter()
        router.set('pdftoppm', mutating_pdftoppm)
        router.set('tesseract', _default_tesseract(words=_clean_page_words()))
        router.set('identify', _default_identify())
        router.set('convert', _default_convert())
        _, _, _, run_result = self._run(router)
        self.assertEqual(run_result, 'CLEAN')
        self.assertEqual(rendered_from['bytes'], self.orig_bytes)
        man = self._manifest()
        orig_sha = hashlib.sha256(self.orig_bytes).hexdigest()
        self.assertEqual(man['input_sha256'], orig_sha)
        self.assertEqual(man['doc'], 'doc-' + orig_sha[:16])

    def test_snapshot_rejects_symlink_fifo_and_overbound_directly(self):
        snap_dir = os.path.join(self.tmp.name, 'snaps'); os.makedirs(snap_dir)
        link = os.path.join(self.inbox, 'link.pdf')
        os.symlink(self.pdf, link)
        with self.assertRaises(OSError):
            R._snapshot_input(link, snap_dir)          # O_NOFOLLOW: ELOOP, never followed
        if hasattr(os, 'mkfifo'):
            fifo = os.path.join(self.inbox, 'fifo.pdf')
            os.mkfifo(fifo)
            with _Alarm():   # a lost O_NONBLOCK would HANG here; the alarm reds it instead
                with self.assertRaises(ValueError):
                    R._snapshot_input(fifo, snap_dir)  # O_NONBLOCK open + fstat reject, no hang
        with mock.patch.object(R, 'MAX_INPUT_PDF_BYTES', 4):
            with self.assertRaises(ValueError):
                R._snapshot_input(self.pdf, snap_dir)
        self.assertEqual(os.listdir(snap_dir), [])     # no partial snapshot left behind

    def test_overbound_input_fails_closed_as_process_error(self):
        router = ToolRouter()  # no handlers needed; rejection precedes any tool call
        with mock.patch.object(R, 'MAX_INPUT_PDF_BYTES', 4):
            results, _, code, run_result = self._run(router)
        self.assertEqual(run_result, 'ERROR')
        self.assertEqual(code, R.EXIT_PROCESS_ERROR)
        self.assertEqual(results[0]['error'], 'PROCESS_ERROR')
        self.assertEqual(results[0]['error_type'], 'ValueError')


class IntegratedConsumptionTests(unittest.TestCase):
    """load_verified_pages() verifies and reads in one step — consumed bytes
    are the verified bytes by construction — under explicit workload bounds, failing closed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.redacted = os.path.join(self.tmp.name, 'redacted')
        self.approved = os.path.join(self.tmp.name, 'approved')

    def _approve(self, label='doc1', npages=1):
        d = stage_valid_doc(self.redacted, label=label, npages=npages)
        r = A.approve_one(os.path.join(d, 'manifest.json'), self.approved, accept_flagged=False)
        self.assertTrue(r['ok'], r)
        return os.path.join(self.approved, os.path.basename(d))

    def test_returns_exact_verified_bytes(self):
        ad = self._approve(npages=2)
        docs = V.load_verified_pages(self.approved, self.redacted)
        self.assertEqual(len(docs), 1)
        self.assertEqual([p['page'] for p in docs[0]['pages']], [1, 2])
        for p in docs[0]['pages']:
            self.assertIsInstance(p['data'], bytes)
            self.assertEqual(hashlib.sha256(p['data']).hexdigest(), p['sha256'])
            with open(os.path.join(ad, 'page-%02d.png' % p['page']), 'rb') as f:
                self.assertEqual(p['data'], f.read())

    def test_cli_verify_one_shape_unchanged_without_collect(self):
        ad = self._approve()
        r = V.verify_one(os.path.join(ad, 'approval.json'), self.redacted)
        self.assertTrue(r['ok'])
        self.assertNotIn('page_bytes', r)   # the diagnostic CLI path never buffers page bytes

    def test_injected_swap_between_validation_and_read_rejects(self):
        """The core case: a writer swaps a page AFTER the artifact-set validation but
        BEFORE the would-be consumer read. The consumed bytes must be the verified bytes or the
        operation must reject — here the read hashes the swapped bytes and rejects."""
        ad = self._approve()
        target = os.path.join(ad, 'page-01.png')
        real_validate = R._validate_dir_artifacts

        def swap_after_validation(directory, page_numbers, extra_allowed):
            errs = real_validate(directory, page_numbers, extra_allowed)
            with open(target, 'wb') as f:
                f.write(b'SWAPPED-BETWEEN-VALIDATION-AND-READ')
            return errs

        with mock.patch.object(R, '_validate_dir_artifacts', side_effect=swap_after_validation):
            with self.assertRaises(V.ConsumptionError) as cm:
                V.load_verified_pages(self.approved, self.redacted)
        self.assertIn('tamper/swap', str(cm.exception))

    def test_mutation_after_read_cannot_change_consumed_bytes(self):
        ad = self._approve()
        docs = V.load_verified_pages(self.approved, self.redacted)
        page = docs[0]['pages'][0]
        with open(os.path.join(ad, 'page-01.png'), 'wb') as f:
            f.write(b'MUTATED-AFTER-CONSUMPTION')
        self.assertEqual(hashlib.sha256(page['data']).hexdigest(), page['sha256'])

    def test_no_reopen_after_verification_negative_control(self):
        """THE snapshot-consumption property, bitten directly (red-team finding 1): every page path is
        read exactly once, and the returned buffer is the bytes of that one read. The wrapper
        poisons each page file immediately after its first read, so ANY reopen-after-verify
        implementation fails — a reopen through the bounded reader re-reads poisoned bytes (hash
        mismatch -> rejects, first assert fires), and a reopen through any other channel returns
        poisoned buffers (second/third asserts fire). The shipped implementation passes because
        the verified buffer IS the returned buffer."""
        ad = self._approve(npages=2)
        first_read = {}
        real_read = R._read_page_bytes

        def read_then_poison(path):
            data = real_read(path)
            if path not in first_read:
                first_read[path] = data
                with open(path, 'wb') as f:
                    f.write(b'POISONED-IMMEDIATELY-AFTER-FIRST-READ')
            return data

        with mock.patch.object(R, '_read_page_bytes', side_effect=read_then_poison):
            docs = V.load_verified_pages(self.approved, self.redacted)
        self.assertEqual(len(first_read), 2)          # each page path read exactly once
        for p in docs[0]['pages']:
            path = os.path.join(ad, 'page-%02d.png' % p['page'])
            self.assertEqual(p['data'], first_read[path])                      # the one read's bytes
            self.assertEqual(hashlib.sha256(p['data']).hexdigest(), p['sha256'])  # still the sealed hash

    def test_any_rejected_document_fails_the_whole_call(self):
        self._approve(label='doc1')
        ad2 = self._approve(label='doc2')
        with open(os.path.join(ad2, 'page-01.png'), 'wb') as f:
            f.write(b'TAMPERED')
        with self.assertRaises(V.ConsumptionError):
            V.load_verified_pages(self.approved, self.redacted)

    def test_fifo_page_rejects_without_blocking(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        ad = self._approve()
        pf = os.path.join(ad, 'page-01.png')
        os.remove(pf); os.mkfifo(pf)
        with _Alarm():   # a lost O_NONBLOCK would HANG here; the alarm reds it instead
            with self.assertRaises(V.ConsumptionError):
                V.load_verified_pages(self.approved, self.redacted)

    def test_unreadable_page_rejects_category_only(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('permission bits do not bind as root')
        ad = self._approve()
        pf = os.path.join(ad, 'page-01.png')
        os.chmod(pf, 0o000)
        self.addCleanup(os.chmod, pf, 0o600)
        with self.assertRaises(V.ConsumptionError) as cm:
            V.load_verified_pages(self.approved, self.redacted)
        self.assertNotIn(self.tmp.name, str(cm.exception))   # category-only, no path leak

    def test_page_bytes_bound_rejects(self):
        self._approve()
        with mock.patch.object(R, 'MAX_PAGE_BYTES', 4):
            with self.assertRaises(V.ConsumptionError) as cm:
                V.load_verified_pages(self.approved, self.redacted)
        self.assertIn('workload bound', str(cm.exception))

    def test_total_bytes_bound_rejects(self):
        self._approve(npages=2)   # each synthetic page ~21 bytes; total > 30
        with mock.patch.object(R, 'MAX_TOTAL_PAGE_BYTES', 30):
            with self.assertRaises(V.ConsumptionError) as cm:
                V.load_verified_pages(self.approved, self.redacted)
        self.assertIn('workload bound', str(cm.exception))

    def test_state_json_bound_rejects(self):
        self._approve()
        with mock.patch.object(R, 'MAX_STATE_JSON_BYTES', 16):
            with self.assertRaises(V.ConsumptionError):
                V.load_verified_pages(self.approved, self.redacted)

    def test_manifest_page_count_bound_rejects(self):
        self._approve(npages=2)
        with mock.patch.object(R, 'MAX_PAGES_PER_DOC', 1):
            with self.assertRaises(V.ConsumptionError):
                V.load_verified_pages(self.approved, self.redacted)
        # and the canonical validator reports it as a schema error directly
        d = os.path.join(self.redacted, os.listdir(self.approved)[0])
        with open(os.path.join(d, 'manifest.json')) as f:
            man = json.load(f)
        with mock.patch.object(R, 'MAX_PAGES_PER_DOC', 1):
            errs = R.validate_document_manifest(man, d)
        self.assertTrue(any('workload bound' in e for e in errs))

    def test_invalid_roots_and_selectors_reject(self):
        self._approve()
        link = os.path.join(self.tmp.name, 'approved-link')
        os.symlink(self.approved, link)
        with self.assertRaises(V.ConsumptionError):
            V.load_verified_pages(link, self.redacted)                    # symlinked root
        with self.assertRaises(V.ConsumptionError):
            V.load_verified_pages(self.approved, self.approved)           # aliased roots
        with self.assertRaises(V.ConsumptionError):
            V.load_verified_pages(self.approved, self.redacted, doc='../evil')  # raw-path selector
        empty = os.path.join(self.tmp.name, 'empty'); os.makedirs(empty)
        with self.assertRaises(V.ConsumptionError):
            V.load_verified_pages(empty, self.redacted)                   # nothing to consume



class SchemeChoiceTests(unittest.TestCase):
    """ADR-0062: the scheme is named, never assumed, and each row of the number list guard L10 reads is
    one the tool knows; the row also gives its OCR language."""
    ARGV = ['--inbox', '/x', '--render', '/r', '--work', '/w', '--redacted', '/red', '--log', '/l.json',
            '--dob', '1901-02-03']

    def test_scheme_is_required(self):
        # --scheme or, for a number not on the list, --covered-by-hand (ADR-0076): neither refuses
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            R.main(self.ARGV)
        self.assertIn('one of the arguments --scheme --covered-by-hand is required', err.getvalue())
        self.assertIsNone(R.build_arg_parser().parse_args(self.ARGV + ['--scheme', 'pl-id']).lang)

    def test_every_row_of_the_number_list_is_a_scheme(self):
        # an entry in SCHEMES may wait without its row (the CLI refuses its key); a row never waits
        # without its entry
        table = R.id_schemes.load()
        for key in table:
            self.assertIn(key, R.SCHEMES)
            self.assertTrue(table[key]['lang'])


# ---------------------------------------------------------------------------
# The token schemes (us-ssn, cz-sk-rc, fr-nir). Every number below is generated or a never-issued
# value: 987-65-432N is the range SSA keeps for advertising; the others are built here from invented
# dates and endings, with their check computed by this file (not by the code under test).
# ---------------------------------------------------------------------------
SSN = '987-65-4321'
SSN_BARE = '987654321'


def row(*texts, top=500, left=100, conf=95, line=('1', '1', '1'), gap=15):
    """One OCR line of words, close together as one printed line would be."""
    out = []
    for t in texts:
        out.append(W(t, left, top, width=20 * len(t), conf=conf, line=line))
        left += 20 * len(t) + gap
    return out


def tdetect(words, scheme, dob=None, rules=R.DEFAULT_RULES, label_boxes=None, signals=None, label_token=None):
    prefix = R._pl_id_prefix(dob) if dob and 'pl-id' in scheme.split(',') else (PREFIX if 'pl-id' in scheme else None)
    return R.detect(words, 2000, 2000, prefix, rules=rules, label_token=label_token, scheme=scheme,
                    label_boxes=label_boxes, dob=dob, signals=signals)


def cz(head, divisible=True, tail='123'):
    """A ten-digit Czech/Slovak number on `head` (YYMMDD), divisible by 11 or not."""
    for n in range(int(tail), int(tail) + 20):
        for d in '0123456789':
            s = head + '%03d' % n + d
            if (int(s) % 11 == 0) == divisible:
                return s
    raise AssertionError('no ending found')


CZ_SLASH = cz('900102')[:6] + '/' + cz('900102')[6:]   # an invented date, written with its slash


def nir(body):
    """A 15-character French number: the 13 + their key, Corsica's 2A/2B counted as 19/18."""
    n = int(body[:5] + {'2A': '19', '2B': '18'}.get(body[5:7], body[5:7]) + body[7:])
    return body + '%02d' % (97 - n % 97)


FR_BODY = '1900199999123'          # man, born 1990-01, abroad (99), invented country and order
FR_CORSICA = '285072A004123'       # woman, born 1985-07, Corse-du-Sud
FILLER = [W(f'w{i}', 100, 900 + 40 * i, line=(str(i + 10), '1', '1')) for i in range(5)]   # lines far below


def _token_router(plain, dark=(), langs=ALL_LANGS):
    """The tools for one page: `plain` on the first plain read only (a mask hides it), `dark` on the
    darkened read."""
    def tesseract(cmd):
        if cmd[2] == 'stdout':
            return subprocess.CompletedProcess(cmd, 0, 'Rotate: 0\nOrientation confidence: 5.0\n', '')
        base = os.path.basename(cmd[2])
        extra = [] if '_v' in base else (list(dark) if '_dark' in base else list(plain))
        _write_tsv(cmd[2] + '.tsv', _clean_page_words() + extra)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    router = ToolRouter(langs=langs)
    router.set('pdftoppm', _default_pdftoppm(n_pages=1))
    router.set('tesseract', tesseract)
    router.set('identify', _default_identify())
    router.set('convert', _default_convert())
    return router


class TokenSchemeUSTests(unittest.TestCase):
    def test_separated_print_forms(self):
        for words in ([W(SSN, 100, 500, width=220)], row('987', '65', '4321'), row('987-', '65-4321'),
                      row('987', '-', '65', '-', '4321'), row('SSN:' + SSN)):
            h, _, _ = tdetect(words, 'us-ssn')
            self.assertIn('id-shape', reasons(h), [w['text'] for w in words])

    def test_bare_nine_digits_mask_as_bare(self):
        h, _, _ = tdetect([W(SSN_BARE, 100, 500, width=220)], 'us-ssn')
        self.assertEqual(reasons(h), ['id-shape-bare'])
        self.assertGreaterEqual(len(R.strong_hits(h)), 1)
        # OCR's split of one bare run masks the same way (review 2026-11-08)
        self.assertEqual(reasons(tdetect(row('98765', '4321') + FILLER, 'us-ssn')[0]), ['id-shape-bare'])

    def test_a_table_rule_another_hyphen_a_dot_or_an_underscore_still_masks(self):
        # cold review 2026-11-08: each of these left the number visible on a page with no label
        for t in ('|987-65-4321', '987-65-4321|', '987654321|', '987\u201065\u20104321', '987\u201165\u20114321',
                  '987\u201265\u20124321', '987\u221265\u22124321', '987.65.4321', '987_65_4321',
                  '|23-45-6789', '123-45-678|', '|98765432'):       # and a | that is OCR's 1 still counts as one
            self.assertTrue(tdetect(row(t) + FILLER, 'us-ssn')[0], t)
        for t in ('XXX-XX-4321|', '|XXX-XX-4321', 'XXX\u2011XX\u20114321', 'XXX-XX-432|'):
            self.assertIn('id-last-four', reasons(tdetect(row(t) + FILLER, 'us-ssn')[0]), t)
        for t in ('12.25.2024', '987.654.321', '98.765.4321'):          # a date, other groupings
            self.assertFalse(tdetect(row(t) + FILLER, 'us-ssn')[0], t)

    def test_never_issued_bare_values_do_not_mask(self):
        for t in ('000654321', '666654321', '987004321', '987650000'):
            self.assertFalse(tdetect([W(t, 100, 500, width=220)], 'us-ssn')[0], t)

    def test_confusables(self):
        h, _, _ = tdetect([W('98T-65-432l', 100, 500, width=220)], 'us-ssn')
        self.assertEqual(reasons(h), ['id-shape-fuzzy'])
        self.assertFalse(tdetect([W('9BT-6S-4ZOl', 100, 500, width=220)], 'us-ssn')[0])   # five confusables

    def test_decoys(self):
        digest = hashlib.sha256(b'synthetic').hexdigest()
        for words in (row('(212)', '555-0123'), row('212-555-0123'), row('2125550123'), row('12345-6789'),
                      row('12-25-2024'), row('12/25/2024'), row('Glucose', '13.5', 'mmol/l'), row(digest),
                      row('MRN', '12345678'), row('1234567890123456'), row('12', '34', '56', '78', '90'),
                      row('987654321012'), row('98765-4321'), row('987', '654', '321')):
            h, _, _ = tdetect(words, 'us-ssn')
            self.assertFalse(h, [w['text'] for w in words])

    def test_a_long_run_holds_no_window(self):
        # the sliding window would find nine digits inside; whole printed numbers do not
        self.assertFalse(tdetect(row('19876543210'), 'us-ssn')[0])
        self.assertFalse(tdetect(row('1-987-65-4321'), 'us-ssn')[0])
        self.assertFalse(tdetect(row('987-65-4321-7'), 'us-ssn')[0])

    def test_columns_apart_are_not_one_number(self):
        self.assertTrue(tdetect(row('987', '65-4321'), 'us-ssn')[0])
        self.assertFalse(tdetect(row('987', '65-4321', gap=400), 'us-ssn')[0])

    def test_last_four(self):
        for words in (row('XXX-XX-4321'), row('***-**-4321'), row('###-##-4321'), row('•••-••-4321'),
                      row('xxx-xx-4321'), row('XXX', 'XX', '4321'), row('XXX-XX-', '4321'), row('XXX-XX-432l'),
                      row('XXX', '-', 'XX', '-', '4321'),       # split as one OCR line, and over a continuing line
                      row('XXX-XX-') + row('4321', left=300, line=('1', '1', '2')),
                      row('XXX-XxX-4321', conf=32), row('XX-XX-4321')):   # a mask group misread in width
            h, _, _ = tdetect(words + FILLER, 'us-ssn')
            self.assertIn('id-last-four', reasons(h), [w['text'] for w in words])
        for words in (row('XXX-XX-ABCD'), row('XXX-XX-43lI')):
            self.assertNotIn('id-last-four', reasons(tdetect(words, 'us-ssn')[0]), [w['text'] for w in words])
        self.assertFalse(tdetect(row('XXX-XX-4321'), 'cz-sk-rc')[0], 'a US form only for a US run')

    def test_four_digits_after_an_ssn_label_mask_as_any_number_beside_it(self):
        h, lab, lnc = tdetect(row('SSN', '4321'), 'us-ssn')
        self.assertEqual(reasons(h), ['id-label-proximity'])
        self.assertTrue(lab)
        self.assertFalse(lnc)

    def test_a_label_or_sign_glued_on_without_a_colon(self):
        for t, scheme in (('SSN' + SSN, 'us-ssn'), ('SS#' + SSN, 'us-ssn'), ('#' + SSN, 'us-ssn'),
                          ('No.' + SSN, 'us-ssn'), ('RČ' + CZ_SLASH, 'cz-sk-rc'), ('n°' + CZ_SLASH, 'cz-sk-rc'),
                          ('NIR' + nir(FR_BODY), 'fr-nir')):
            self.assertIn('id-shape', reasons(tdetect(row(t), scheme)[0]), t)

    def test_a_separator_binds_only_towards_a_number(self):
        for words, scheme in ((row('Name', '—', SSN), 'us-ssn'), (row('Pacient', '-', CZ_SLASH), 'cz-sk-rc'),
                              (row(SSN + '/'), 'us-ssn'), (row('"' + SSN + '"'), 'us-ssn'), (row('*' + SSN), 'us-ssn'),
                              (row('Tel', '-', SSN), 'us-ssn'), (row(SSN, '-', 'Name'), 'us-ssn')):
            self.assertIn('id-shape', reasons(tdetect(words, scheme)[0]), [w['text'] for w in words])
        self.assertFalse(tdetect(row('1', '-', SSN), 'us-ssn')[0], 'a number on both sides: one longer number')

    def test_a_fragment_read_only_as_confusables(self):
        self.assertEqual(reasons(tdetect(row('987', 'SS', '4321'), 'us-ssn')[0]), ['id-shape-fuzzy'])

    def test_a_fragment_shaped_like_a_date(self):
        self.assertEqual(reasons(tdetect(row('9', '87-65-4321'), 'us-ssn')[0]), ['id-shape'])

    def test_strong_label_alone_holds_weak_does_not(self):
        h, lab, lnc = tdetect(row('SSN', 'on', 'file') + FILLER, 'us-ssn')
        self.assertTrue(lab and lnc)
        h, lab, lnc = tdetect(row('Social', 'Security', 'Administration') + FILLER, 'us-ssn')
        self.assertTrue(lab)
        self.assertFalse(lnc)

    def test_the_abbreviated_french_label_is_strong(self):
        for first in ('N°', 'Nº', 'No'):
            h, lab, lnc = tdetect(row(first, 'de', 'sécurité', 'sociale', ':', 'voir', 'carte') + FILLER, 'fr-nir')
            self.assertTrue(lab and lnc, first)
        h, lab, _ = tdetect(row('régime', 'de', 'sécurité', 'sociale') + FILLER, 'fr-nir')
        self.assertFalse(lab, 'the words alone are not the label')

    def test_short_labels_are_whole_words_in_capitals(self):
        for words in (row('Tin', 'box', '12345'), row('patients', '12345'), row('TINCTURE', '12345'),
                      row('ssn', '12345')):
            h, lab, _ = tdetect(words, 'us-ssn')
            self.assertFalse(lab, [w['text'] for w in words])
            self.assertNotIn('id-label-proximity', reasons(h))
        h, lab, _ = tdetect(row('TIN:', '12345'), 'us-ssn')
        self.assertTrue(lab)
        self.assertIn('id-label-proximity', reasons(h))

    def test_a_spaced_number_satisfies_a_strong_label(self):
        h, lab, lnc = tdetect(row('SSN', '987', '65', '4321'), 'us-ssn')
        self.assertIn('id-shape', reasons(h))
        self.assertIn('id-label-proximity', reasons(h))
        self.assertFalse(lnc)

    def test_a_capitalised_word_is_not_a_number_beside_a_label(self):
        h, _, lnc = tdetect(row('Social', 'Security', 'STATISTICS'), 'us-ssn')
        self.assertFalse(h)


class TokenSchemeCzSkTests(unittest.TestCase):
    DOB = '1990-01-02'

    def test_slash_forms_mask_without_divisibility(self):
        n = cz('900102', divisible=False)
        for words in (row(n[:6] + '/' + n[6:]), row(n[:6], '/', n[6:]), row(n[:6] + '/', n[6:]),
                      row(n[:6], '/' + n[6:]), row('RČ:' + n[:6] + '/' + n[6:]), row('900102/123')):
            h, _, _ = tdetect(words, 'cz-sk-rc')
            self.assertIn('id-shape', reasons(h), [w['text'] for w in words])

    def test_bare_ten_needs_divisibility_and_a_month(self):
        self.assertEqual(reasons(tdetect(row(cz('900102')), 'cz-sk-rc')[0]), ['id-shape'])
        self.assertEqual(reasons(tdetect(row(cz('900102')[:6], cz('900102')[6:]), 'cz-sk-rc')[0]), ['id-shape'])
        self.assertFalse(tdetect(row(cz('900102', divisible=False)), 'cz-sk-rc')[0], 'near-miss checksum')
        self.assertFalse(tdetect(row(cz('901302')), 'cz-sk-rc')[0], 'month 13 is not a month')
        for head in ('905102', '902102', '907102', '900142', '900152'):      # women, RČ+, EČP, insured
            self.assertEqual(reasons(tdetect(row(cz(head)), 'cz-sk-rc')[0]), ['id-shape'], head)

    def test_bare_nine_masks_as_bare(self):
        self.assertEqual(reasons(tdetect(row('450102123'), 'cz-sk-rc')[0]), ['id-shape-bare'])
        self.assertEqual(reasons(tdetect(row('450145123'), 'cz-sk-rc')[0]), ['id-shape-bare'])  # day +40
        for t in ('450102000', '451302123', '450135123', '450100123'):    # ending 000, month 13, day 35, day 0
            self.assertFalse(tdetect(row(t), 'cz-sk-rc')[0], t)

    def test_remainder_ten_and_a_slashed_ending_000(self):
        self.assertEqual(int('700101005') % 11, 10)                    # issued with the check digit 0
        self.assertEqual(reasons(tdetect(row('7001010050'), 'cz-sk-rc')[0]), ['id-shape'])
        self.assertFalse(tdetect(row('7001010051'), 'cz-sk-rc')[0])
        self.assertEqual(reasons(tdetect(row('535101/000'), 'cz-sk-rc')[0]), ['id-shape'])

    def test_the_dob_prefix_set(self):
        heads = R._cz_sk_prefixes(self.DOB)
        self.assertEqual(len(heads), 12)
        self.assertIn('907152', heads)
        for head in heads:
            for n in (cz(head, divisible=False), head + '123'):
                h, _, _ = tdetect(row(n), 'cz-sk-rc', dob=self.DOB)
                self.assertEqual(reasons(h), ['id-prefix'], n)
        # without the DOB, the same not-divisible ten digits do not mask: shape alone
        self.assertFalse(tdetect(row(cz('900102', divisible=False)), 'cz-sk-rc')[0])
        # with another person's DOB, the prefix does not help
        self.assertFalse(tdetect(row(cz('900102', divisible=False)), 'cz-sk-rc', dob='1991-05-06')[0])

    def test_confusables(self):
        self.assertEqual(reasons(tdetect(row('9OO1O2/1234'), 'cz-sk-rc')[0]), ['id-shape-fuzzy'])
        self.assertEqual(reasons(tdetect(row('9OO1O2/1234'), 'cz-sk-rc', dob=self.DOB)[0]), ['id-prefix-fuzzy'])

    def test_decoys(self):
        digest = hashlib.sha256(b'synthetic').hexdigest()
        for words in (row('603', '123', '456'), row('+420', '603', '123', '456'), row('110', '00'),
                      row('1.', '2.', '1990'), row('02.01.1990'), row('č.j.', '1234/2024'), row('123456/2024'),
                      row('Glukóza', '5.4', 'mmol/l'), row(digest), row('12345678901234'),
                      row('900102/12345'), row('4501021234567')):
            self.assertFalse(tdetect(words, 'cz-sk-rc')[0], [w['text'] for w in words])

    def test_labels(self):
        for words in (row('Rodné', 'číslo:'), row('rodne', 'cislo'), row('RODNÉ', 'ČÍSLO')):
            h, lab, lnc = tdetect(words + FILLER, 'cz-sk-rc')
            self.assertTrue(lab and lnc, [w['text'] for w in words])
        h, lab, lnc = tdetect(row('RČ') + FILLER, 'cz-sk-rc')
        self.assertTrue(lab)
        self.assertFalse(lnc, 'a weak label only masks')
        self.assertFalse(tdetect(row('Rč', '12345') + FILLER, 'cz-sk-rc')[1])
        h, lab, lnc = tdetect(row('Rodné', 'číslo:', '4501', '02', '123'), 'cz-sk-rc')
        self.assertFalse(lnc)
        self.assertIn('id-label-proximity', reasons(h))


class TokenSchemeFrTests(unittest.TestCase):
    DOB = '1990-01-15'

    def test_keyed_print_forms(self):
        n = nir(FR_BODY)
        for words in (row(n), row('1', '90', '01', '99', '999', '123', n[13:]), row(n[:13] + '/' + n[13:]),
                      row(n[:13], '/', n[13:]), row('1', '90', '01', '99', '999', '123', '-', n[13:]),
                      row(*n)):                                          # one digit per box
            h, _, _ = tdetect(words, 'fr-nir')
            self.assertEqual(reasons(h), ['id-shape'], [w['text'] for w in words])

    def test_near_miss_key_does_not_mask(self):
        n = nir(FR_BODY)
        bad = n[:13] + '%02d' % ((int(n[13:]) % 97) + 1)
        self.assertFalse(tdetect(row(bad), 'fr-nir')[0])

    def test_corsica_and_its_ocr_misreads(self):
        n = nir(FR_CORSICA)
        self.assertEqual(reasons(tdetect(row(n), 'fr-nir')[0]), ['id-shape'])
        self.assertEqual(reasons(tdetect(row(n.replace('2A', '24')), 'fr-nir')[0]), ['id-shape'])  # A read as 4
        b = nir(FR_CORSICA.replace('2A', '2B'))
        self.assertEqual(reasons(tdetect(row(b), 'fr-nir')[0]), ['id-shape'])
        self.assertEqual(reasons(tdetect(row(b.replace('2B', '28')), 'fr-nir')[0]), ['id-shape'])
        dordogne = nir(FR_CORSICA.replace('2A', '24'))                    # a real 24, read as 2A
        self.assertEqual(reasons(tdetect(row(dordogne.replace('24', '2A', 1)), 'fr-nir')[0]), ['id-shape'])
        body = '190019A999123'                     # a letter where the place is not Corsica's 2_
        n = int(body.replace('A', '0')) - 1000000
        self.assertNotEqual(97 - n % 97, 97 - int(body.replace('A', '4')) % 97)
        self.assertFalse(tdetect(row(body + '%02d' % (97 - n % 97)), 'fr-nir')[0], 'a letter only for Corsica')

    def test_first_digit(self):
        for first in '5690':
            self.assertFalse(tdetect(row(nir(first + FR_BODY[1:])), 'fr-nir')[0], first)
        for first in '123478':
            self.assertTrue(tdetect(row(nir(first + FR_BODY[1:])), 'fr-nir')[0], first)

    def test_keyless_thirteen_needs_a_second_sign(self):
        self.assertFalse(tdetect(row(FR_BODY), 'fr-nir')[0])
        self.assertFalse(tdetect(row(FR_BODY), 'fr-nir', dob='1991-02-03')[0])
        self.assertEqual(reasons(tdetect(row(FR_BODY), 'fr-nir', dob=self.DOB)[0]), ['id-prefix'])
        for label in (('NIR',), ('Mat', 'INS'), ('matricule', 'INS'), ('numéro', 'INSEE')):
            h, _, _ = tdetect(row(*label, '1', '90', '01', '99', '999', '123'), 'fr-nir')
            self.assertIn('id-shape', reasons(h), label)
        h, _, _ = tdetect([W('NIR', 100, 460, line=('0', '1', '1'))] + row(FR_BODY, top=500), 'fr-nir')  # above
        self.assertIn('id-shape', reasons(h))
        n = nir(FR_BODY)                                                   # the DOB strengthens a bad key too
        bad = n[:13] + '%02d' % ((int(n[13:]) % 97) + 1)
        self.assertEqual(reasons(tdetect(row(bad), 'fr-nir', dob=self.DOB)[0]), ['id-prefix'])

    def test_a_faint_label_beside_a_clear_keyless_thirteen(self):
        h, _, _ = tdetect([W('NIR', 100, 500, width=60, conf=20)] + row(FR_BODY, left=180), 'fr-nir')
        self.assertIn('id-shape', reasons(h))

    def test_confusables(self):
        n = nir(FR_BODY)
        self.assertEqual(reasons(tdetect(row(n.replace('0', 'O')), 'fr-nir')[0]), ['id-shape-fuzzy'])

    def test_decoys(self):
        digest = hashlib.sha256(b'synthetic').hexdigest()
        for words in (row('1234567890123'), row('01', '23', '45', '67', '89'), row('75001', 'Paris'),
                      row('insuline', '12', 'UI'), row('INSULINE', '12', 'UI'), row(digest),
                      row('15/01/1990'), row('Glycémie', '1.05', 'g/l'), row(FR_BODY + '/12' + '3')):
            h, lab, _ = tdetect(words, 'fr-nir')
            self.assertFalse(h, [w['text'] for w in words])
            self.assertFalse(lab, [w['text'] for w in words])

    def test_labels(self):
        for words in (row('NIR'), row('Numéro', 'de', 'sécurité', 'sociale'), row('numero', 'de', 'securite', 'sociale')):
            self.assertTrue(tdetect(words + FILLER, 'fr-nir')[2], [w['text'] for w in words])
        for words in (row('INS'), row('ouvrant', 'droit'), row('NIA')):
            h, lab, lnc = tdetect(words + FILLER, 'fr-nir')
            self.assertTrue(lab)
            self.assertFalse(lnc, [w['text'] for w in words])
        self.assertFalse(tdetect(row('NIR', '1', '90', '01', '99', '999', '123', '45'), 'fr-nir')[2])
        self.assertFalse(tdetect(row('INS', 'né', 'le', '15/01/1990'), 'fr-nir')[0], 'the DOB stays visible')

    def test_scannable_code_signal(self):
        for words in (row('INS', 'à', 'scanner'), row('ins', 'a', 'SCANNER'), row('INS', 'à'), row('INSàscanner')):
            signals = set()
            tdetect(words, 'fr-nir', signals=signals)
            self.assertEqual(signals, {'scan-code'} if 'scanner' in ' '.join(w['text'] for w in words).lower()
                             else set(), [w['text'] for w in words])
        signals = set()
        tdetect(row('INS', 'à', 'scanner', conf=10), 'fr-nir', signals=signals)
        self.assertEqual(signals, {'scan-code'}, 'read below the confidence floor still holds')
        signals = set()
        tdetect(row('INS', 'à', 'scanner'), 'us-ssn,cz-sk-rc', signals=signals)
        self.assertEqual(signals, set(), 'a French sign only for a French run')

    def test_the_scan_caption_wrapped_over_two_lines(self):
        signals = set()
        tdetect(row('INS', 'à') + row('scanner', top=540, line=('1', '1', '2')) + FILLER, 'fr-nir', signals=signals)
        self.assertEqual(signals, {'scan-code'})


class TokenSchemeSharedTests(unittest.TestCase):
    def test_several_schemes_in_one_run(self):
        words = (row('90010212346', top=100, line=('1', '1', '1')) + row(SSN, top=200, line=('2', '1', '1'))
                 + row(nir(FR_BODY), top=300, line=('3', '1', '1'))
                 + row(cz('900102'), top=400, line=('4', '1', '1')))
        self.assertLessEqual({'id-prefix', 'id-shape'},
                             set(reasons(tdetect(words, 'pl-id,us-ssn,cz-sk-rc,fr-nir', dob='1990-01-02')[0])))
        self.assertEqual(len([h for h in tdetect(words, 'us-ssn,fr-nir')[0] if h['reason'] == 'id-shape']), 2)
        self.assertNotIn('id-shape', reasons(tdetect(words, 'pl-id')[0]), 'pl-id alone stays as it was')

    def test_low_confidence(self):
        h, _, _ = tdetect([W(SSN, 100, 500, width=220, conf=20)], 'us-ssn')
        self.assertEqual(reasons(h), ['id-low-confidence'])
        h, _, _ = tdetect(row('1', '90', '01') + row('99', '999', '123', nir(FR_BODY)[13:], left=260, conf=12),
                          'fr-nir')
        self.assertIn('id-low-confidence', reasons(h))
        self.assertEqual(reasons(tdetect([W('9876S432l', 100, 500, width=220, conf=15)], 'cz-sk-rc')[0]),
                         ['id-low-confidence'])                               # nine, identifier-shaped
        self.assertFalse(tdetect([W(SSN, 100, 500, width=220, conf=20)], 'us-ssn',
                                 rules=('prefix', 'checksum', 'label'))[0])
        for t in ('13.5', 'mg/dl', '123456', 'IIlIlIllII'):
            self.assertFalse(tdetect([W(t, 100, 500, conf=15)], 'us-ssn')[0], t)

    def test_rules_toggle(self):
        n = nir(FR_BODY)
        self.assertFalse(tdetect(row(n), 'fr-nir', rules=('prefix', 'label', 'lowconf'))[0])
        self.assertFalse(tdetect(row(cz('900102')), 'cz-sk-rc', rules=('prefix', 'label', 'lowconf'))[0])
        self.assertFalse(tdetect(row(SSN), 'us-ssn', rules=('checksum', 'label', 'lowconf'))[0])
        self.assertFalse(tdetect(row('SSN', '4321'), 'us-ssn', rules=('prefix', 'checksum'))[1])

    def test_label_boxes_carry_strong_labels_only(self):
        boxes = []
        tdetect(row('SSN', top=100, line=('1', '1', '1')) + row('Social', 'Security', top=300, line=('2', '1', '1')),
                'us-ssn', label_boxes=boxes)
        self.assertEqual([found for _, found in boxes], [False])

    def test_a_number_split_over_two_ocr_lines(self):
        key = nir(FR_BODY)[13:]
        for words, scheme in (
                (row('Patient', '987-65-') + row('4321', left=410, line=('1', '1', '2')), 'us-ssn'),        # same row
                (row('Patient', '987-65-') + row('4321', top=540, left=255, line=('1', '1', '2')), 'us-ssn'),  # below
                (row(CZ_SLASH[:7]) + row(CZ_SLASH[7:], left=255, line=('1', '1', '2')), 'cz-sk-rc'),
                (row('1', '90', '01') + row('99', '999', '123', key, left=245, line=('1', '1', '2')), 'fr-nir')):
            h, _, _ = tdetect(words, scheme)
            self.assertIn('id-shape', reasons(h), [w['text'] for w in words])
            self.assertEqual(len(h), 2, 'one box per line')
        self.assertFalse(tdetect(row('Patient', '987-65-') + row('4321', top=900, line=('1', '1', '2')), 'us-ssn')[0])



def kdetect(words, known=SSN_BARE, scheme='us-ssn', rules=R.DEFAULT_RULES, label_boxes=None):
    return R.detect(words, 2000, 2000, None, rules=rules, scheme=scheme, label_boxes=label_boxes,
                    known={'us-ssn': known} if known else None)


class KnownNumberTests(unittest.TestCase):
    """A person's own number, recorded in their identity file (ADR-0074): searched whole, through OCR's
    misreads, in place of the scheme's shape rules."""

    def test_the_number_in_its_print_forms(self):
        for words in (row(SSN), row(SSN_BARE), row('987', '65', '4321'), row('SSN:' + SSN),
                      row('Patient', '987-65-') + row('4321', left=410, line=('1', '1', '2')),       # split over lines
                      row('Ref', '00' + SSN_BARE + '11')):                                       # inside a longer run
            h, _, _ = kdetect(words + FILLER)
            self.assertIn('id-known', reasons(h), [w['text'] for w in words])
            self.assertTrue(R.strong_hits(h), 'it drives the verify loop')

    def test_through_confusables_and_up_to_two_wrong_digits(self):
        self.assertIn('id-known-fuzzy', reasons(kdetect(row('98T-6S-432l') + FILLER)[0]))
        for t in ('987-65-4329', '987-66-4329', '997-65-4321'):
            self.assertIn('id-known', reasons(kdetect(row(t) + FILLER)[0]), t)
        for t in ('917-66-4329', '123-45-6789'):
            self.assertNotIn('id-known', reasons(kdetect(row(t) + FILLER)[0]), t)

    def test_it_replaces_the_shape_guess(self):
        for t in ('123-45-6789', '123456789'):
            self.assertIn(reasons(tdetect(row(t) + FILLER, 'us-ssn')[0])[0], ('id-shape', 'id-shape-bare'))
            self.assertEqual(kdetect(row(t) + FILLER)[0], [], 'another nine digits stay visible')

    def test_the_last_four_form_and_the_label_still_count(self):
        self.assertIn('id-last-four', reasons(kdetect(row('XXX-XX-4321') + FILLER)[0]))
        h, lab, lnc = kdetect(row('SSN', 'on', 'file') + FILLER)
        self.assertTrue(lab and lnc, 'a strong label with no number near it still holds the page')
        self.assertIn('id-label-proximity', reasons(kdetect(row('SSN', '4321') + FILLER)[0]))

    def test_a_faint_word(self):
        h, _, _ = kdetect([W(SSN, 100, 500, width=220, conf=20)] + FILLER)
        self.assertIn('id-low-confidence', reasons(h))

    def test_no_rules_override_drops_it_and_the_scheme_gates_it(self):
        for rules in (('checksum', 'label', 'lowconf'), ('label',)):
            self.assertIn('id-known', reasons(kdetect(row(SSN) + FILLER, rules=rules)[0]), rules)
        h, _, _ = R.detect(row(SSN) + FILLER, 2000, 2000, PREFIX, scheme='pl-id', known={'us-ssn': SSN_BARE})
        self.assertNotIn('id-known', reasons(h), 'a number for a scheme not in the run is not searched')

    def test_pl_id_unchanged_beside_it(self):
        words = row('44051401359') + row(SSN, top=600, line=('2', '1', '1')) + FILLER
        h, _, _ = R.detect(words, 2000, 2000, PREFIX, scheme='pl-id,us-ssn', known={'us-ssn': SSN_BARE})
        self.assertLessEqual({'id-known'}, set(reasons(h)))
        self.assertEqual(reasons(R.detect(row('44051401359') + FILLER, 2000, 2000, PREFIX, scheme='pl-id')[0]),
                         reasons(R.detect(row('44051401359') + FILLER, 2000, 2000, PREFIX, scheme='pl-id',
                                          known={'us-ssn': SSN_BARE})[0]))

    def test_the_number_beside_its_label_is_read_for_the_identity_tool(self):
        self.assertEqual(list(R.labelled_numbers(row('SSN:', SSN) + FILLER, 'us-ssn')), [SSN_BARE])
        self.assertEqual(list(R.labelled_numbers(row('SSN', '98T-65-4321') + FILLER, 'us-ssn')), [SSN_BARE])
        self.assertEqual(list(R.labelled_numbers(row('SSN:' + SSN) + FILLER, 'us-ssn')), [SSN_BARE])
        self.assertEqual(R.labelled_numbers(row('Patient', SSN) + FILLER, 'us-ssn'), {})
        self.assertEqual(R.labelled_numbers(row('SSN', SSN) + row('SSN', '987-65-4320', top=540,
                                                                    line=('2', '1', '1')), 'us-ssn').keys(),
                         {SSN_BARE, '987654320'})
        self.assertEqual(R.labelled_numbers(row('SSN', 'XXX-XX-4321'), 'us-ssn'), {})

    def test_the_valid_and_shown_forms(self):
        v = R.SCHEMES['us-ssn']['valid']
        self.assertTrue(v(SSN_BARE) and v('912345678'))
        for bad in ('000654321', '666654321', '987004321', '987650000', '98765432', 'abcdefghi'):
            self.assertFalse(v(bad), bad)
        self.assertEqual(R.SCHEMES['us-ssn']['shown'](SSN_BARE), SSN)


def _number_list(path, keys=('pl-id', 'us-ssn', 'cz-sk-rc', 'fr-nir')):
    """A temporary number list holding the waiting rows too, so the CLI accepts their keys."""
    rows = {'pl-id': 'pol\t[0-9]{11}', 'us-ssn': 'eng\t[0-9]{3}-[0-9]{2}-[0-9]{4}',
            'cz-sk-rc': 'ces+slk\t[0-9]{6}/[0-9]{3,4}', 'fr-nir': 'fra+eng\t[0-9]{13}'}
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join('%s\t%s\tsynthetic row\n' % (k, rows[k]) for k in keys))
    real = R.id_schemes.load
    return mock.patch.object(R.id_schemes, 'load', lambda p=None: real(path))


class CoveredByHandTests(unittest.TestCase):
    """ADR-0076, ADR-0077: a number not on the list (the tag's key `unlisted`) is covered by hand before
    scanning; the run masks no unlisted number, needs the documents' language when no scheme is named,
    and still ends at the operator's gate."""
    NOT_LISTED = '## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme unlisted⟩ — a synthetic country\n'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        self.inbox = os.path.join(self.tmp.name, 'person', 'med', '_inbox'); os.makedirs(self.inbox)
        patcher = mock.patch.object(R, 'PATIENTS', self.tmp.name); patcher.start(); self.addCleanup(patcher.stop)
        self.profile = os.path.join(self.tmp.name, 'person', 'profile.md')
        self._profile(self.NOT_LISTED)
        self.log = os.path.join(self.tmp.name, 'run-log.json')
        with open(os.path.join(self.inbox, 'doc1.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')
        self.table = os.path.join(self.tmp.name, 'id-schemes.tsv')

    def _profile(self, text):
        with open(self.profile, 'w', encoding='utf-8') as f:
            f.write(text)

    def _main(self, *argv, extra=(), langs=ALL_LANGS):
        self.router = router = _token_router(extra, langs=langs)
        buf, err = io.StringIO(), io.StringIO()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', side_effect=lambda n: '/usr/bin/' + n if n in ('pdftoppm', 'tesseract') else None), \
             mock.patch('redact_ids._im', return_value={'convert': ['convert'], 'identify': ['identify']}), \
             contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            try:
                code = R.main(['--inbox', self.inbox, '--render', self.render, '--work', self.work,
                               '--redacted', self.redacted, '--log', self.log] + list(argv))
            except SystemExit as e:
                code = ('usage', e.code)
        return code, buf.getvalue() + err.getvalue()

    def test_alone_it_needs_the_documents_language_before_any_page(self):
        with _number_list(self.table):
            code, out = self._main('--covered-by-hand')
        self.assertEqual(code, ('usage', 2))
        self.assertIn('needs --lang', out)
        self.assertEqual(self.router.calls, [], 'no page is read')

    def test_alone_its_language_is_checked(self):
        with _number_list(self.table):
            code, out = self._main('--covered-by-hand', '--lang', 'ces', langs=('eng', 'osd'))
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn("tesseract's language data (ces) is not installed", out)
        self.assertEqual(self.router.calls, [], 'no page is read')

    def test_alone_it_masks_no_number_and_ends_at_the_gate(self):
        with _number_list(self.table):
            code, out = self._main('--covered-by-hand', '--lang', 'eng', extra=row('SSN:', SSN))
        self.assertNotIn(code, (R.EXIT_INVALID_INVOCATION, R.EXIT_STATE_ERROR))
        self.assertIn('masked= 0', out)
        self.assertIn('note: covered by hand', out)
        self.assertIn('AWAITING_OPERATOR', out)
        with open(self.log, encoding='utf-8') as fh:
            log = json.load(fh)
        self.assertTrue(log['args']['covered_by_hand'])
        self.assertEqual(log['args']['scheme'], '')
        self.assertEqual(log['state'], 'AWAITING_OPERATOR')
        self.assertNotIn(SSN, json.dumps(log) + out)

    def test_a_tagged_number_must_stay_among_the_schemes(self):
        self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme us-ssn,unlisted⟩\n')
        with _number_list(self.table):
            code, out = self._main('--covered-by-hand', '--lang', 'eng', extra=row('SSN:', SSN))
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn('beside --scheme for every other number the tag names', out)
        self.assertEqual(self.router.calls, [], 'no page is read')

    def test_only_the_exact_unlisted_key_allows_it(self):
        # ADR-0077: words never allow it; a damaged tag beside them reads as no tag, which never allows it
        for text in ('## Identity\n- Private mode ⟨never-API⟩ — number not on the list\n',
                     '## Identity\n- Private mode ⟨never-API⟩ — number not on the list; ⟨id-\nscheme pl-id⟩\n',
                     '## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme pl-id⟩ and a number not on the list\n'):
            self._profile(text)
            with _number_list(self.table):
                code, out = self._main('--covered-by-hand', '--lang', 'eng', extra=row('SSN:', SSN))
            self.assertEqual(code, R.EXIT_INVALID_INVOCATION, text)
            self.assertEqual(self.router.calls, [], 'no page is read')

    def test_a_batch_folder_inside_the_tray_finds_the_profile(self):
        batch = os.path.join(self.inbox, '2026-11'); os.makedirs(batch)
        os.replace(os.path.join(self.inbox, 'doc1.pdf'), os.path.join(batch, 'doc1.pdf'))
        self.inbox = batch
        with _number_list(self.table):
            code, out = self._main('--covered-by-hand', '--lang', 'eng', extra=row('SSN:', SSN))
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)
        self.assertIn('note: covered by hand', out)

    def test_beside_a_scheme_the_tagged_number_is_still_masked(self):
        self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme us-ssn,unlisted⟩\n')
        with _number_list(self.table), mock.patch('identity.recorded_numbers', return_value={'us-ssn': SSN_BARE}):
            code, out = self._main('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name,
                                   '--covered-by-hand', extra=row('SSN:', SSN))
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertNotIn('masked= 0', out)
        self.assertIn('note: covered by hand', out)

    def test_refused_unless_the_tag_names_unlisted(self):
        for text in ('## Identity\n- Private mode ⟨never-API⟩\n',                       # no tag: every row, masked
                     '## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme pl-id⟩\n',
                     '## Identity\n- Private mode ⟨never-API⟩\n## Notes\n- ⟨id-scheme unlisted⟩\n',  # not on its line
                     None):                                                                # no profile
            if text is None:
                os.unlink(self.profile)
            else:
                self._profile(text)
            with _number_list(self.table):
                code, out = self._main('--covered-by-hand', '--lang', 'eng', extra=row('SSN:', SSN))
            self.assertEqual(code, R.EXIT_INVALID_INVOCATION, text)
            self.assertIn('only for a person whose private-mode tag names', out)
            self.assertNotIn(self.profile, out)
            self.assertNotIn(self.tmp.name, out)
            self.assertEqual(self.router.calls, [], 'no page is read')

    def test_an_empty_scheme_detects_nothing_but_the_label_rule(self):
        words = row('SSN:', SSN) + row('Nr', '12345678', top=700)
        self.assertEqual(R.detect(words, 2000, 3000, None, scheme='')[0], [])
        hits = R.detect(words, 2000, 3000, None, scheme='', label_token='Nr')[0]
        self.assertEqual({h['reason'] for h in hits}, {'id-label-proximity'})


class SchemesCoverTagTests(unittest.TestCase):
    """A run on a private-mode person's intake tray leaves out no key the profile's tag names (cold review
    2026-11-10): a key left out leaves that number unmasked. Exact tokens only (ADR-0077)."""
    NOT_LISTED = '## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme us-ssn⟩\n'
    setUp, _profile, _main = CoveredByHandTests.setUp, CoveredByHandTests._profile, CoveredByHandTests._main
    REFUSED = 'the run leaves out a number this person\'s profile tag names'

    def _ssn(self, *argv, keys=('pl-id', 'us-ssn', 'cz-sk-rc', 'fr-nir')):
        self.log = tempfile.mktemp(suffix='.json', dir=self.tmp.name)    # a fresh run log for each run
        with _number_list(self.table, keys), mock.patch('identity.recorded_numbers', return_value={'us-ssn': SSN_BARE}):
            return self._main(*argv, extra=row('SSN:', SSN))

    def _refused(self, code, out):
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION, out)
        self.assertIn(self.REFUSED, out)
        self.assertNotIn(self.tmp.name, out)
        self.assertNotIn(SSN_BARE, out)
        self.assertEqual(self.router.calls, [], 'no page is read')

    def test_a_scheme_the_tag_does_not_name_is_refused(self):
        code, out = self._ssn('--scheme', 'pl-id', '--dob', '1901-02-03')
        self._refused(code, out)
        self.assertIn(self.REFUSED + ' (or the profile or its tag cannot be read): us-ssn;', out)   # the key left out
        self.assertIn('tools/private-mode/numbers/<key>.md', out)

    def test_a_tagged_key_left_out_is_refused_before_the_number_is_asked_for(self):
        self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme pl-id,us-ssn⟩\n')
        self._refused(*self._ssn('--scheme', 'pl-id', '--dob', '1901-02-03'))

    def test_no_tag_needs_every_row_of_the_list(self):
        self._profile('## Identity\n- Private mode ⟨never-API⟩\n')
        two = ('pl-id', 'us-ssn')
        code, out = self._ssn('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name, keys=two)
        self._refused(code, out)
        self.assertIn('cannot be read): pl-id;', out)
        code, out = self._ssn('--scheme', 'pl-id,us-ssn', '--dob', '1901-02-03',
                              '--number-from-identity', self.tmp.name, keys=two)
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)

    def test_unlisted_is_named_by_covered_by_hand(self):
        self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme us-ssn,unlisted⟩\n')
        self._refused(*self._ssn('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name))
        code, out = self._ssn('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name, '--covered-by-hand')
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)
        self.assertIn('note: covered by hand', out)

    def test_a_refused_or_missing_tag_or_profile_is_refused(self):
        for text in ('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme nope⟩\n',     # unknown key
                     '## Identity\n- Private mode ⟨never-API⟩ ⟨ID-scheme us-ssn⟩\n',   # not the exact tag
                     None):                                                            # no profile
            if text is None:
                os.unlink(self.profile)
            else:
                self._profile(text)
            code, out = self._ssn('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name)
            self._refused(code, out)
            self.assertIn('cannot be read); pass in', out, 'no key is printed when the tag cannot be read')

    def test_every_tagged_key_runs_and_an_extra_one_only_masks_more(self):
        for argv in (('--scheme', 'us-ssn'), ('--scheme', 'pl-id,us-ssn', '--dob', '1901-02-03')):
            code, out = self._ssn(*argv, '--number-from-identity', self.tmp.name)
            self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)
            self.assertNotIn('masked= 0', out)

    def test_every_path_to_the_tray_is_the_tray(self):
        # Codex review 2026-11-10, passes 1-3: links, link chains, '..' past a link and another case each
        # hid the tray from a walk over the path's names; the tray is now known by the directory itself
        batch = os.path.join(self.inbox, '2026-11'); os.makedirs(batch)
        os.replace(os.path.join(self.inbox, 'doc1.pdf'), os.path.join(batch, 'doc1.pdf'))
        person = os.path.dirname(os.path.dirname(self.inbox))
        store = os.path.join(self.tmp.name, 'store'); os.replace(os.path.join(person, 'med'), store)
        os.symlink(store, os.path.join(person, 'med'))                                   # med/ is a link
        os.symlink(self.inbox, os.path.join(self.tmp.name, 'tray-link'))                  # a link to the tray
        os.makedirs(os.path.join(person, 'nmed')); os.symlink(os.path.join(person, 'nmed'),
                                                              os.path.join(self.tmp.name, 'shortcut'))
        os.symlink(batch, os.path.join(self.tmp.name, 'batch-link'))                      # a link into the tray
        os.makedirs(os.path.join(batch, 'part')); shutil.copy(os.path.join(batch, 'doc1.pdf'), os.path.join(batch, 'part'))
        paths = [batch, os.path.join(self.tmp.name, 'tray-link', '2026-11'), os.path.join(self.tmp.name, 'batch-link', 'part'),
                 os.path.join(self.tmp.name, 'shortcut', '..', 'med', '_inbox', '2026-11')]
        upper = os.path.join(person, 'MED', '_INBOX', '2026-11')
        if os.path.isdir(upper):                                                          # macOS folds case
            paths.append(upper)
        for path in paths:
            self.inbox = path
            self._refused(*self._ssn('--scheme', 'pl-id', '--dob', '1901-02-03'))
        self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme unlisted⟩\n')
        for path in paths:
            self.inbox = path
            code, out = self._ssn('--covered-by-hand', '--lang', 'eng')
            self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, (path, out))
            self.assertIn('note: covered by hand', out)

    def test_an_unlistable_care_folder_refuses_and_a_missing_one_compares_nothing(self):
        # Codex review 2026-11-10, pass 4: any listing error read as "no people"
        with mock.patch('redact_ids.os.listdir', side_effect=PermissionError):
            self._refused(*self._ssn('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name))
        with mock.patch.object(R, 'PATIENTS', os.path.join(self.tmp.name, 'absent')):
            code, out = self._ssn('--scheme', 'pl-id', '--dob', '1901-02-03')
        self.assertNotIn(self.REFUSED, out)

    def test_a_path_not_known_as_a_tray_refuses(self):
        # operator 2026-11-10 (after Codex passes 1-5 each found one more path shape): in a folder with people,
        # a path the tool does not know as a tray refuses instead of skipping the comparison
        scans = os.path.join(self.tmp.name, 'scans', '2026-11'); os.makedirs(scans)
        os.replace(os.path.join(self.inbox, 'doc1.pdf'), os.path.join(scans, 'doc1.pdf'))
        os.symlink(os.path.dirname(scans), os.path.join(self.inbox, 'scanner-link'))
        for path in (scans, os.path.join(self.inbox, 'scanner-link', '2026-11')):   # elsewhere; a link out of the tray
            self.inbox = path
            for argv in (('--scheme', 'pl-id', '--dob', '1901-02-03'), ('--covered-by-hand', '--lang', 'eng')):
                code, out = self._ssn(*argv)
                self.assertEqual(code, R.EXIT_INVALID_INVOCATION, out)
                self.assertIn("--inbox is not a person's intake tray in this care folder", out)
                self.assertNotIn(self.tmp.name, out)
                self.assertEqual(self.router.calls, [], 'no page is read')

    def test_a_tray_two_people_share_refuses(self):
        # Codex review 2026-11-10, pass 6: another person's tray linked to this one chose their profile
        other = os.path.join(self.tmp.name, 'other', 'med'); os.makedirs(other)
        with open(os.path.join(self.tmp.name, 'other', 'profile.md'), 'w', encoding='utf-8') as f:
            f.write('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme pl-id⟩\n')
        os.symlink(self.inbox, os.path.join(other, '_inbox'))
        self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme pl-id,unlisted⟩\n')
        self._refused(*self._ssn('--scheme', 'pl-id', '--dob', '1901-02-03'))

    def test_an_unreadable_tray_refuses(self):
        batch = os.path.join(self.inbox, '2026-11'); os.makedirs(batch)
        os.replace(os.path.join(self.inbox, 'doc1.pdf'), os.path.join(batch, 'doc1.pdf'))
        self.inbox = batch
        real_stat = os.stat
        def stat(path, *a, **k):
            if str(path).startswith(R.PATIENTS) and str(path).endswith(os.path.join('med', '_inbox')):
                raise PermissionError
            return real_stat(path, *a, **k)
        with mock.patch('redact_ids.os.stat', side_effect=stat):
            self._refused(*self._ssn('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name))

    def test_the_care_folder_is_found_through_a_linked_tool_folder(self):
        # Codex review 2026-11-10, pass 4: a linked tools/private-mode chose the folders above the link
        here = os.path.dirname(os.path.realpath(R.__file__))
        link = os.path.join(self.tmp.name, 'tool-link'); os.symlink(here, link)
        out = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0, sys.argv[1]); '
                              'import redact_ids; print(redact_ids.PATIENTS)', link],
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, os.path.join(os.path.dirname(os.path.dirname(here)), 'patients'))

    def test_a_profile_without_the_marker_compares_nothing(self):
        self._profile('## Identity\n- ⟨id-scheme us-ssn⟩\n')
        code, out = self._ssn('--scheme', 'pl-id', '--dob', '1901-02-03')
        self.assertNotIn(self.REFUSED, out)
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)


class ShippedListTests(unittest.TestCase):
    """The number list as shipped: the Polish and the US number are listed; the other entries wait for their
    rows. A profile with no exact tag needs every listed row in the run (ADR-0077), so an untagged Polish
    person's run is refused until their tag names their number."""
    setUp, _profile, _main = CoveredByHandTests.setUp, CoveredByHandTests._profile, CoveredByHandTests._main
    REFUSED = SchemesCoverTagTests.REFUSED
    NOT_LISTED = '## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme pl-id⟩\n'

    def _run(self, *argv):
        self.log = tempfile.mktemp(suffix='.json', dir=self.tmp.name)    # a fresh run log for each run
        with mock.patch('identity.recorded_numbers', return_value={'us-ssn': SSN_BARE}):
            return self._main(*argv, extra=row('SSN:', SSN))

    def test_the_shipped_rows_and_their_languages(self):
        table = R.id_schemes.load()
        self.assertEqual(list(table), ['pl-id', 'us-ssn'])
        self.assertEqual(R._shipped_schemes(), 'pl-id, us-ssn')
        self.assertEqual(R.run_langs(['us-ssn'], None, table), ['eng'])
        self.assertEqual(R.run_langs(['pl-id', 'us-ssn'], None, table), ['pol', 'eng'])

    def test_the_waiting_entries_are_still_refused(self):
        for key in ('cz-sk-rc', 'fr-nir'):
            code, out = self._run('--scheme', key, '--dob', '1990-01-02')
            self.assertEqual(code, R.EXIT_INVALID_INVOCATION, key)
            self.assertIn('not in the private-mode number list', out)
            self.assertEqual(self.router.calls, [], 'no page is read')

    def test_a_tagged_person_runs_on_their_own_number(self):
        for tag, argv in (('pl-id', ('--scheme', 'pl-id', '--dob', '1901-02-03')),
                          ('us-ssn', ('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name))):
            self._profile('## Identity\n- Private mode ⟨never-API⟩ ⟨id-scheme %s⟩\n' % tag)
            code, out = self._run(*argv)
            self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)
            self.assertNotIn(SSN_BARE, out)

    def test_an_untagged_person_needs_every_listed_number(self):
        self._profile('## Identity\n- Private mode ⟨never-API⟩\n')
        code, out = self._run('--scheme', 'pl-id', '--dob', '1901-02-03')
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION, out)
        self.assertIn(self.REFUSED, out)
        self.assertEqual(self.router.calls, [], 'no page is read')
        code, out = self._run('--scheme', 'pl-id,us-ssn', '--dob', '1901-02-03',
                              '--number-from-identity', self.tmp.name)
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION, out)


class TokenSchemeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('inbox', 'render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        self.log = os.path.join(self.tmp.name, 'run-log.json')
        with open(os.path.join(self.inbox, 'doc1.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')
        self.table = os.path.join(self.tmp.name, 'id-schemes.tsv')
        self.langs = ALL_LANGS

    def _ns(self, **over):
        d = dict(inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
                 log=self.log, dob=None, scheme='us-ssn', label_token=None,
                 rules=R.DEFAULT_RULES, dpi=300, lang='eng', max_iters=3)
        d.update(over)
        return argparse_namespace(d)

    def _main(self, *argv, extra=()):
        self.router = router = _token_router(extra, langs=self.langs)
        buf = io.StringIO()
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', side_effect=lambda n: '/usr/bin/' + n if n in ('pdftoppm', 'tesseract') else None), \
             mock.patch('redact_ids._im', return_value={'convert': ['convert'], 'identify': ['identify']}), \
             contextlib.redirect_stdout(buf):
            code = R.main(['--inbox', self.inbox, '--render', self.render, '--work', self.work,
                           '--redacted', self.redacted, '--log', self.log] + list(argv))
        return code, buf.getvalue()

    def test_scheme_list_parses_in_order_once_each(self):
        ap = R.build_arg_parser()
        base = ['--inbox', '/x', '--render', '/r', '--work', '/w', '--redacted', '/red', '--log', '/l.json']
        self.assertEqual(ap.parse_args(base + ['--scheme', 'fr-nir,us-ssn,fr-nir']).scheme, 'fr-nir,us-ssn')
        for bad in ('bogus', 'pl-id,bogus', '', 'pl-id,'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                ap.parse_args(base + ['--scheme', bad])

    def test_a_missing_language_refuses_before_any_page_and_names_only_the_language(self):
        self.langs = ('eng', 'osd', 'pol')
        with _number_list(self.table):
            code, out = self._main('--scheme', 'cz-sk-rc')
            self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
            self.assertIn("tesseract's language data (ces) is not installed", out)
            self.assertIn("tesseract's language data (slk) is not installed", out)
            self.assertNotIn('(eng)', out)
            self.assertNotIn(self.tmp.name, out)
            self.assertEqual(self.router.calls, [])                  # no page was read
            code, out = self._main('--scheme', 'pl-id,fr-nir', '--dob', '1990-01-02')
            self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
            self.assertIn('(fra)', out)
            self.assertNotIn('(pol)', out)
            with mock.patch('identity.recorded_numbers', return_value={'us-ssn': SSN_BARE}):
                code, out = self._main('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name)  # eng is there
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertNotIn('language data', out)

    def test_an_explicit_lang_is_the_one_checked(self):
        self.langs = ('eng', 'osd', 'ces', 'slk')
        with _number_list(self.table):
            code, out = self._main('--scheme', 'cz-sk-rc', '--lang', 'ces+fra')
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn('(fra)', out)
        self.assertNotIn('(slk)', out)
        with _number_list(self.table):
            code, out = self._main('--scheme', 'us-ssn', '--lang', 'eng+x/y')
        self.assertIn('one named by --lang', out)
        self.assertNotIn('x/y', out)

    def test_the_language_list_is_read_from_either_stream_and_a_failure_refuses(self):
        r = subprocess.CompletedProcess
        with mock.patch('redact_ids.subprocess.run', return_value=r([], 0, '', 'List of available languages in "/a b/" (2):\neng\nces\n')):
            self.assertEqual(R._installed_langs(), {'eng', 'ces'})
        with mock.patch('redact_ids.subprocess.run', return_value=r([], 0, 'List of available languages (1):\nfra\n', '')):
            self.assertEqual(R._installed_langs(), {'fra'})
        with mock.patch('redact_ids.subprocess.run', return_value=r([], 1, '', 'error')):
            self.assertIsNone(R._installed_langs())
        with mock.patch('redact_ids._installed_langs', return_value=None), \
             mock.patch('shutil.which', return_value='/usr/bin/fake'), _number_list(self.table):
            errs = R.validate_args(self._ns())
        self.assertIn('tesseract could not list its language data', errs)

    def test_a_scheme_whose_number_holds_no_date_needs_the_persons_own(self):
        with _number_list(self.table):
            code, out = self._main('--scheme', 'us-ssn')
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn('none is recorded for us-ssn', out)
        self.assertIn('tools/private-mode/numbers/<key>.md', out)
        self.assertEqual(self.router.calls, [], 'no page is read')
        with _number_list(self.table), mock.patch('identity.recorded_numbers', return_value={'us-ssn': SSN_BARE}):
            code, out = self._main('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name,
                                   extra=row('SSN:', SSN))
        self.assertNotEqual(code, R.EXIT_INVALID_INVOCATION)
        with open(self.log, encoding='utf-8') as fh:
            log = fh.read()
        self.assertTrue(json.loads(log)['args']['known_number_given'])
        self.assertIn('id-known', log)
        for v in (SSN, SSN_BARE, '4321'):
            self.assertNotIn(v, log + out)

    def test_an_unreadable_identity_file_refuses_without_a_value(self):
        import identity
        with _number_list(self.table), mock.patch('identity.recorded_numbers',
                                                  side_effect=identity.Refused('no national number is recorded')):
            code, out = self._main('--scheme', 'us-ssn', '--number-from-identity', self.tmp.name)
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn('no national number is recorded', out)

    def test_a_key_without_its_row_still_fails(self):
        with _number_list(self.table, keys=('pl-id',)):
            code, out = self._main('--scheme', 'us-ssn')
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)
        self.assertIn('not in the private-mode number list', out)
        self.assertEqual(self.router.calls, [])
        with _number_list(self.table, keys=('pl-id', 'us-ssn')):
            code, out = self._main('--scheme', 'us-ssn,fr-nir')
        self.assertEqual(code, R.EXIT_INVALID_INVOCATION)

    @mock.patch('shutil.which', return_value='/usr/bin/fake')
    def test_dob_only_when_a_scheme_needs_it(self, _w):
        _langs_installed(self)
        with _number_list(self.table):
            self.assertEqual(R.validate_args(self._ns()), [])
            self.assertEqual(R.validate_args(self._ns(scheme='cz-sk-rc,fr-nir')), [])
            self.assertEqual(R.validate_args(self._ns(scheme='cz-sk-rc', dob='1990-01-02')), [])
            self.assertTrue(any('YYYY-MM-DD' in e for e in R.validate_args(self._ns(scheme='pl-id,us-ssn'))))
            errs = R.validate_args(self._ns(scheme='fr-nir', dob='1990-02-30'))
            self.assertTrue(any('real calendar date' in e for e in errs))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self._main('--scheme', 'us-ssn,pl-id')


class TokenSchemePipelineTests(unittest.TestCase):
    """The page flow for the token schemes: both reads, the new holds, the manifest and approval."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for n in ('inbox', 'render', 'work', 'redacted'):
            setattr(self, n, os.path.join(self.tmp.name, n)); os.makedirs(getattr(self, n))
        with open(os.path.join(self.inbox, 'doc1.pdf'), 'wb') as f:
            f.write(b'%PDF-FAKE')
        R.IM = dict(convert=['convert'], identify=['identify'])

    def _run(self, plain, dark=(), scheme='us-ssn', dob=None):
        router = _token_router(plain, dark)
        a = argparse_namespace(dict(inbox=self.inbox, render=self.render, work=self.work, redacted=self.redacted,
                                    dob=dob, scheme=scheme, label_token=None, rules=R.DEFAULT_RULES, dpi=300,
                                    lang='eng', max_iters=3, prefix=None))
        with mock.patch('redact_ids.subprocess.run', side_effect=router), \
             mock.patch('redact_ids.shutil.which', return_value=None):
            results, _, code, run_result = R.run_pipeline(a)
        return results[0]['pages'][0], code, run_result

    def _manifest_path(self):
        d = [x for x in os.listdir(self.redacted) if x.startswith('doc-')][0]
        return os.path.join(self.redacted, d, 'manifest.json')

    def _at(self, words):
        return [dict(w, top=2000, line_key=('99', '1', '1')) for w in words]

    def test_separated_ssn_is_masked_and_clean(self):
        pg, code, result = self._run(self._at(row(SSN)))
        self.assertEqual((result, pg['flags']), ('CLEAN', []))
        self.assertEqual(pg['reasons'], ['id-shape'])
        self.assertGreaterEqual(pg['n_masked'], 1)

    def test_bare_nine_alone_holds_and_beside_a_label_does_not(self):
        pg, code, result = self._run(self._at(row(SSN_BARE)))
        self.assertEqual((result, code, pg['flags']), ('HOLD', R.EXIT_HOLD, ['BARE_NUMBER_ONLY']))
        with open(self._manifest_path()) as f:
            man = json.load(f)
        self.assertEqual(R.validate_document_manifest(man, os.path.dirname(self._manifest_path())), [])
        approved = os.path.join(self.tmp.name, 'approved')
        self.assertEqual(A.approve_one(self._manifest_path(), approved, accept_flagged=False)['code'],
                         A.EXIT_REJECTED_FLAGS)
        self.assertTrue(A.approve_one(self._manifest_path(), approved, accept_flagged=True,
                                      accept_flags={'BARE_NUMBER_ONLY'})['ok'])
        shutil.rmtree(self.redacted); os.makedirs(self.redacted)
        pg, _, result = self._run(self._at(row('SSN', SSN_BARE)))
        self.assertEqual((result, pg['flags']), ('CLEAN', []))

    def test_czech_bare_nine_holds_but_not_with_the_dob(self):
        pg, _, result = self._run(self._at(row('450102123')), scheme='cz-sk-rc')
        self.assertEqual(pg['flags'], ['BARE_NUMBER_ONLY'])
        shutil.rmtree(self.redacted); os.makedirs(self.redacted)
        pg, _, result = self._run(self._at(row('450102123')), scheme='cz-sk-rc', dob='1945-01-02')
        self.assertEqual((result, pg['flags'], pg['reasons']), ('CLEAN', [], ['id-prefix']))

    def test_french_runs_with_and_without_a_dob(self):
        pg, _, result = self._run(self._at(row(nir(FR_BODY))), scheme='fr-nir')
        self.assertEqual((result, pg['reasons']), ('CLEAN', ['id-shape']))
        shutil.rmtree(self.redacted); os.makedirs(self.redacted)
        pg, _, result = self._run(self._at(row(FR_BODY)), scheme='fr-nir', dob='1990-01-15')
        self.assertEqual((result, pg['reasons']), ('CLEAN', ['id-prefix']))

    def test_scannable_code_holds(self):
        pg, code, result = self._run(self._at(row('INS', 'à', 'scanner')), scheme='fr-nir')
        self.assertEqual((result, code), ('HOLD', R.EXIT_HOLD))
        self.assertIn('SCANNABLE_CODE', pg['flags'])
        with open(self._manifest_path()) as f:
            man = json.load(f)
        self.assertEqual(R.validate_document_manifest(man, os.path.dirname(self._manifest_path())), [])

    def test_a_number_only_the_darkened_read_sees(self):
        pg, code, result = self._run([], dark=self._at(row(SSN)))
        self.assertEqual((result, pg['flags']), ('HOLD', ['LOW_CONFIDENCE_CANDIDATE']))
        self.assertIn('id-low-confidence', pg['reasons'])
        self.assertGreaterEqual(pg['n_masked'], 1)

    def test_a_strong_label_only_the_darkened_read_sees(self):
        pg, _, result = self._run([], dark=self._at(row('NIR')), scheme='fr-nir')
        self.assertEqual(pg['flags'], ['LABEL_NO_CANDIDATE'])
        shutil.rmtree(self.redacted); os.makedirs(self.redacted)
        pg, _, result = self._run([], dark=self._at(row('INS')), scheme='fr-nir')
        self.assertEqual((result, pg['flags']), ('CLEAN', []), 'a weak label never holds')
        shutil.rmtree(self.redacted); os.makedirs(self.redacted)
        pg, _, result = self._run(self._at(row('NIR', nir(FR_BODY))), dark=self._at(row('NIR')), scheme='fr-nir')
        self.assertEqual((result, pg['flags']), ('CLEAN', []), 'the plain read saw it with its number')


if __name__ == '__main__':
    unittest.main()
