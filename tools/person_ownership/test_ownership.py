#!/usr/bin/env python3
"""Synthetic tests for the person-ownership package (ADR-0037 / HO-10). SYNTHETIC data only — no
real handle, path, hash, person id, or clinical content. Both entrypoints discover this suite:

    python3 tools/person_ownership/test_ownership.py
    python3 -m unittest tools.person_ownership.test_ownership
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.person_ownership import schema, fsverify, migrate, append

PID = '0123456789abcdef0123456789abcdef'   # synthetic 32-hex person record id
PID2 = 'fedcba9876543210fedcba9876543210'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rec(person_id=PID, relpath='med/sources/2026-01-01__source__a.pdf', data=b'A', rid='aaaaaaaa',
        status='legacy-folder-only', reviewer='intake-pipeline', derivs=None,
        supersedes='', reason='', sdate=''):
    return dict(schema_version=1, record_id=rid, person_record_id=person_id, source_relpath=relpath,
                sha256=sha(data), acquired_date='2026-01-01', capture_method='scan',
                identity_status=status, identity_reviewer=reviewer,
                identity_source='legacy migration 2026-01-01 — folder position only',
                review_date='2026-01-01', derivatives=derivs or [],
                supersedes=supersedes, supersede_reason=reason, supersede_date=sdate)


class Tree:
    """Synthetic repo tree builder."""
    def __init__(self, tc):
        self.root = tempfile.mkdtemp()
        tc.addCleanup(self._cleanup)
        os.makedirs(os.path.join(self.root, 'patients'))

    def _cleanup(self):
        import shutil
        for dp, dns, fns in os.walk(self.root):
            for n in fns + dns:
                try:
                    os.chmod(os.path.join(dp, n), 0o700)
                except OSError:
                    pass
        shutil.rmtree(self.root, ignore_errors=True)

    def patient(self, handle, person_id=PID):
        pdir = os.path.join(self.root, 'patients', handle)
        os.makedirs(os.path.join(pdir, 'med', 'sources'), exist_ok=True)
        prof = os.path.join(pdir, 'profile.md')
        with open(prof, 'w', encoding='utf-8') as f:
            f.write('# profile\n## Identity\n')
            if person_id:
                f.write('- **Person record ID (local-only):** `%s`\n' % person_id)
        return self

    def src(self, handle, relname, data=b'A'):
        p = os.path.join(self.root, 'patients', handle, 'med', 'sources', relname)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
        return self

    def manifest(self, handle, records, checkpoint='auto'):
        med = os.path.join(self.root, 'patients', handle, 'med')
        os.makedirs(med, exist_ok=True)
        body = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records)
        data = body.encode('utf-8')
        with open(os.path.join(med, 'MANIFEST'), 'wb') as f:
            f.write(data)
        if checkpoint is None:
            return self
        if checkpoint == 'auto':
            cp = schema.compute_checkpoint(data, records)
        else:
            cp = checkpoint
        with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w', encoding='utf-8') as f:
            json.dump(cp, f, sort_keys=True)
        return self

    def raw_manifest(self, handle, text, checkpoint='auto'):
        med = os.path.join(self.root, 'patients', handle, 'med')
        os.makedirs(med, exist_ok=True)
        with open(os.path.join(med, 'MANIFEST'), 'w', encoding='utf-8') as f:
            f.write(text)
        if checkpoint == 'auto':
            data = text.encode('utf-8')
            try:
                records = schema.parse_manifest_bytes(data)
                cp = schema.compute_checkpoint(data, records)
            except schema.ManifestError:
                cp = {'schema_version': 1, 'manifest_sha256': sha(data),
                      'record_count': 0, 'tail_record_id': ''}
            with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w') as f:
                json.dump(cp, f, sort_keys=True)
        return self

    def shared(self, relname, data=b'x'):
        p = os.path.join(self.root, '_shared', 'med', relname)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = 'wb' if isinstance(data, bytes) else 'w'
        with open(p, mode) as f:
            f.write(data)
        return self

    def verify(self):
        return fsverify.verify_tree(self.root)

    def is_green(self):
        findings, _ = self.verify()
        return not findings, findings


# ---------------------------------------------------------------------------
# Phase 0 — schema / record validation (pure)
# ---------------------------------------------------------------------------
class SchemaTests(unittest.TestCase):
    def test_valid_record(self):
        self.assertEqual(schema.validate_record(rec()), [])

    def test_unknown_schema_version(self):
        r = rec(); r['schema_version'] = 2
        self.assertTrue(any('schema_version' in e for e in schema.validate_record(r)))

    def test_unknown_and_missing_fields(self):
        r = rec(); r['surprise'] = 1
        self.assertTrue(any('unknown field' in e for e in schema.validate_record(r)))
        del r['surprise']; del r['sha256']
        self.assertTrue(any('missing required' in e for e in schema.validate_record(r)))

    def test_malformed_person_id(self):
        for bad in ('short', 'A' * 32, '0' * 31, '0' * 33, 123):
            r = rec(person_id=bad)
            self.assertTrue(any('person_record_id' in e for e in schema.validate_record(r)), bad)

    def test_unsafe_relpaths_rejected(self):
        for bad in ('/abs/x', '../escape', 'a/../b', 'a//b', './x', 'a\\b'):
            r = rec(relpath=bad)
            self.assertTrue(schema.validate_record(r), bad)

    def test_non_nfc_relpath_rejected(self):
        import unicodedata
        nfd = unicodedata.normalize('NFD', 'med/sources/zażółć.pdf')
        self.assertNotEqual(nfd, unicodedata.normalize('NFC', nfd))
        r = rec(relpath=nfd)
        self.assertTrue(any('NFC' in e for e in schema.validate_record(r)))

    def test_unknown_status_reviewer_capture(self):
        self.assertTrue(schema.validate_record(dict(rec(), identity_status='made-up')))
        self.assertTrue(schema.validate_record(dict(rec(), identity_reviewer='hacker')))
        self.assertTrue(schema.validate_record(dict(rec(), capture_method='fax')))

    def test_unhashable_vocabulary_values_reject_without_exception(self):
        for field, bad in (('capture_method', {}), ('identity_status', []),
                           ('identity_reviewer', {})):
            r = rec(); r[field] = bad
            self.assertTrue(schema.validate_record(r), field)
        r = rec(supersedes='bbbbbbbb', reason='rename', sdate='2026-01-01')
        r['supersede_reason'] = []
        self.assertTrue(schema.validate_record(r))

    def test_unhashable_record_id_stays_a_schema_finding(self):
        r = rec(); r['record_id'] = {}; r['derivatives'] = 1
        active, errs = schema.supersession_errors([r])
        self.assertEqual(active, [r])
        self.assertEqual(errs, [])
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'A')
        t.manifest('alpha', [r])
        ok, findings = t.is_green()
        self.assertFalse(ok)
        self.assertTrue(any('manifest schema/graph' in x.category for x in findings))

    def test_invalid_dates(self):
        self.assertTrue(schema.validate_record(dict(rec(), acquired_date='2026-13-40')))
        self.assertTrue(schema.validate_record(dict(rec(), review_date='not-a-date')))

    def test_lean_statuses_and_reviewers(self):
        # only the two lean statuses are accepted; deferred v2 statuses reject
        self.assertEqual(schema.validate_record(rec(status='operator-confirmed', reviewer='operator')), [])
        self.assertTrue(schema.validate_record(rec(status='document-identity-checked')))  # v2, not in lean
        self.assertTrue(schema.validate_record(rec(status='bundle-linked')))              # v2, not in lean
        # bundle-parent reviewer form is not part of the lean schema
        self.assertTrue(schema.validate_record(rec(reviewer='bundle-parent:aaaaaaaa')))

    def test_identity_status_requires_coherent_reviewer_and_provenance(self):
        r = rec(status='operator-confirmed', reviewer='intake-pipeline')
        r['identity_source'] = ''
        errs = schema.validate_record(r)
        self.assertTrue(any('operator reviewer' in e for e in errs))
        self.assertTrue(any('provenance basis' in e for e in errs))
        r.update(identity_reviewer='operator', identity_source='operator page-one reconciliation')
        self.assertEqual(schema.validate_record(r), [])

        r = rec(status='legacy-folder-only', reviewer='operator')
        self.assertTrue(any('intake-pipeline reviewer' in e for e in schema.validate_record(r)))

    def test_supersede_fields_coherence(self):
        self.assertTrue(schema.validate_record(rec(supersedes='', reason='rename', sdate='2026-01-01')))
        self.assertTrue(schema.validate_record(rec(supersedes='bbbbbbbb', reason='bogus', sdate='2026-01-01')))
        self.assertTrue(schema.validate_record(rec(supersedes='bbbbbbbb', reason='rename', sdate='nope')))
        self.assertEqual(schema.validate_record(rec(supersedes='bbbbbbbb', reason='rename', sdate='2026-01-01')), [])

    def test_erratum_count_belongs_to_a_retranscribe_row_only(self):
        # ADR-0037 §13: a retranscribe row's derivative must carry a positive int count; no other may
        d = {'derivative_relpath': 'med/sources/2026-01-01__source__a.ocr.md', 'derivative_sha256': '0' * 64}
        rt = dict(rec(supersedes='bbbbbbbb', reason='retranscribe', sdate='2026-01-01'))
        self.assertEqual(schema.validate_record(dict(rt, derivatives=[dict(d, derivative_errata_count=2)])), [])
        self.assertTrue(any('missing required' in e for e in schema.validate_record(dict(rt, derivatives=[d]))))
        for bad in (0, -1, '2', True, 1.0, None, [1]):
            errs = schema.validate_record(dict(rt, derivatives=[dict(d, derivative_errata_count=bad)]))
            self.assertTrue(any('malformed erratum count' in e for e in errs), bad)
        for other in (rec(derivs=[dict(d, derivative_errata_count=1)]),
                      rec(derivs=[dict(d, derivative_errata_count=1)], supersedes='bbbbbbbb',
                          reason='status-change', sdate='2026-01-01')):
            self.assertTrue(any('not a retranscribe' in e for e in schema.validate_record(other)))


class ManifestParseTests(unittest.TestCase):
    def test_empty_is_empty(self):
        self.assertEqual(schema.parse_manifest_bytes(b''), [])

    def test_partial_final_line_rejected(self):
        with self.assertRaisesRegex(schema.ManifestError, 'does not end with a newline'):
            schema.parse_manifest_bytes(b'{"a":1}')  # no trailing newline

    def test_blank_line_rejected(self):
        with self.assertRaisesRegex(schema.ManifestError, 'has a blank line'):
            schema.parse_manifest_bytes(b'{"a":1}\n\n{"b":2}\n')

    def test_non_object_line_rejected(self):
        with self.assertRaisesRegex(schema.ManifestError, 'not a JSON object'):
            schema.parse_manifest_bytes(b'[1,2]\n')

    def test_non_utf8_rejected(self):
        with self.assertRaisesRegex(schema.ManifestError, 'not valid UTF-8'):
            schema.parse_manifest_bytes(b'\xff\xfe\n')

    def test_non_json_line_rejected(self):
        with self.assertRaisesRegex(schema.ManifestError, 'not valid JSON'):
            schema.parse_manifest_bytes(b'not json\n')

    def test_duplicate_json_key_rejected(self):
        with self.assertRaisesRegex(schema.ManifestError, 'not valid JSON'):
            schema.parse_manifest_bytes(b'{"record_id":"aaaaaaaa","record_id":"bbbbbbbb"}\n')

    def test_duplicate_checkpoint_key_rejected_by_verifier(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'A')
        t.manifest('alpha', [rec(data=b'A')])
        cp = os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint')
        with open(cp, 'w') as fh:
            fh.write('{"schema_version":1,"schema_version":1,"manifest_sha256":"%s",'
                     '"record_count":1,"tail_record_id":"aaaaaaaa"}\n' % ('0' * 64))
        ok, findings = t.is_green()
        self.assertFalse(ok)
        self.assertTrue(any('checkpoint unreadable' in f.category for f in findings))


class SupersessionTests(unittest.TestCase):
    def test_duplicate_record_id(self):
        recs = [rec(rid='aaaaaaaa'), rec(rid='aaaaaaaa', relpath='med/sources/2026-01-01__source__b.pdf')]
        _, errs = schema.supersession_errors(recs)
        self.assertTrue(any('duplicate record_id' in e for e in errs))

    def test_forward_reference(self):
        recs = [rec(rid='aaaaaaaa', supersedes='bbbbbbbb', reason='rename', sdate='2026-01-01'),
                rec(rid='bbbbbbbb', relpath='med/sources/2026-01-01__source__b.pdf')]
        _, errs = schema.supersession_errors(recs)
        self.assertTrue(any('forward' in e for e in errs))

    def test_missing_parent(self):
        recs = [rec(rid='aaaaaaaa', supersedes='zzzzzzzz', reason='rename', sdate='2026-01-01')]
        _, errs = schema.supersession_errors(recs)
        self.assertTrue(any('non-existent' in e for e in errs))

    def test_cycle(self):
        recs = [rec(rid='aaaaaaaa', supersedes='bbbbbbbb', reason='rename', sdate='2026-01-01'),
                rec(rid='bbbbbbbb', supersedes='aaaaaaaa', reason='rename', sdate='2026-01-01',
                    relpath='med/sources/2026-01-01__source__b.pdf')]
        _, errs = schema.supersession_errors(recs)
        self.assertTrue(any('cycle' in e for e in errs))

    def test_split_active_successors(self):
        recs = [rec(rid='aaaaaaaa'),
                rec(rid='bbbbbbbb', supersedes='aaaaaaaa', reason='rename', sdate='2026-01-01',
                    relpath='med/sources/2026-01-01__source__b.pdf'),
                rec(rid='cccccccc', supersedes='aaaaaaaa', reason='rehash', sdate='2026-01-01',
                    relpath='med/sources/2026-01-01__source__c.pdf')]
        _, errs = schema.supersession_errors(recs)
        self.assertTrue(any('more than one record' in e for e in errs))

    def test_valid_supersession_active_view(self):
        recs = [rec(rid='aaaaaaaa'),
                rec(rid='bbbbbbbb', supersedes='aaaaaaaa', reason='rename', sdate='2026-01-01')]
        active, errs = schema.supersession_errors(recs)
        self.assertEqual(errs, [])
        self.assertEqual([r['record_id'] for r in active], ['bbbbbbbb'])

    def test_transitive_supersession_fork_red(self):
        """Red-team fix: a MULTI-LEVEL fork (A<-B, then B<-C and B<-C') must RED even though C/C' are not
        direct successors of the same parent — the fork point B has >1 superseder."""
        recs = [rec(rid='aaaaaaaa'),
                rec(rid='bbbbbbbb', supersedes='aaaaaaaa', reason='rename', sdate='2026-01-01',
                    relpath='med/sources/2026-01-01__source__b.pdf'),
                rec(rid='cccccccc', supersedes='bbbbbbbb', reason='rehash', sdate='2026-01-02',
                    relpath='med/sources/2026-01-01__source__c.pdf'),
                rec(rid='dddddddd', supersedes='bbbbbbbb', reason='rehash', sdate='2026-01-02',
                    relpath='med/sources/2026-01-01__source__d.pdf')]
        _, errs = schema.supersession_errors(recs)
        self.assertTrue(any('more than one record' in e for e in errs))


# ---------------------------------------------------------------------------
# Phase 4 — L13 filesystem verification (green + red bites)
# ---------------------------------------------------------------------------
class VerifyTests(unittest.TestCase):
    def _one_source_patient(self, tree, handle='alpha', data=b'EVIDENCE-A'):
        tree.patient(handle).src(handle, '2026-01-01__source__a.pdf', data)
        r = rec(relpath='med/sources/2026-01-01__source__a.pdf', data=data)
        tree.manifest(handle, [r])
        return r

    def test_zero_patient_green(self):
        t = Tree(self)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_scaffolded_empty_person_green(self):
        t = Tree(self); t.patient('alpha')  # no sources, no manifest
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_scaffolded_empty_person_with_duplicate_ids_red(self):
        t = Tree(self); t.patient('alpha')
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- **Person record ID (local-only):** `%s`\n' % PID2)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('more than one person record id' in x.category for x in f))

    def test_scaffolded_private_person_still_scans_identifier_paths(self):
        t = Tree(self); t.patient('alpha')
        pdir = os.path.join(t.root, 'patients', 'alpha')
        with open(os.path.join(pdir, 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        os.makedirs(os.path.join(pdir, 'med', 'analysis'))
        with open(os.path.join(pdir, 'med', 'analysis', 'synthetic-01020312340.md'), 'w') as fh:
            fh.write('synthetic\n')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('residue in a path' in x.category for x in f))

    def _private_with_path(self, *relparts, beside=('manifest.json',)):
        """A private-mode person with one file at relparts; `beside` are files written next to it."""
        t = Tree(self); t.patient('alpha')
        pdir = os.path.join(t.root, 'patients', 'alpha')
        with open(os.path.join(pdir, 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        target = os.path.join(pdir, *relparts)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        for p in (target,) + tuple(os.path.join(os.path.dirname(target), b) for b in beside):
            with open(p, 'wb') as fh:
                fh.write(b'synthetic')
        return t.is_green()

    def test_the_masking_tools_own_folder_names_are_no_identifier(self):
        """About one document id in sixty holds an 11-digit run: a false red no edit could clear."""
        for parts, beside in ((('_redacted', 'doc-1234567890123456', 'page-01.png'), ('manifest.json',)),
                              (('approved', 'doc-1234567890123456', 'page-01.png'), ('manifest.json', 'approval.json')),
                              (('_redacted', '.superseded', 'doc-1234567890123456__20261107T184213Z-4242-abc123',
                                'page-01.png'), ('manifest.json',))):
            with self.subTest(parts[-2]):
                ok, f = self._private_with_path(*parts, beside=beside)
                self.assertFalse(any('residue in a path' in x.category for x in f), [x.category for x in f])

    def test_every_other_number_shaped_name_still_reds(self):
        for parts, beside in (
                (('med', 'analysis', 'doc-01020312340.md'), ()),                   # too short to be the tool's id
                (('_redacted', 'doc-1234567890123456-01020312340', 'page-01.png'), ('manifest.json',)),
                (('_redacted', 'doc-1234567890123456__01020312340', 'page-01.png'), ('manifest.json',)),
                (('_redacted', 'doc-1234567890123456', '01020312340.png'), ('manifest.json',)),
                (('_redacted', 'xdoc-1234567890123456', 'page-01.png'), ('manifest.json',)),
                # the tool's shape on a folder the tool did not make (cold review 2026-11-07)
                (('med', 'sources', 'doc-01020312340abcde', 'scan.pdf'), ()),
                (('_redacted', 'doc-1234567890123456', 'page-01.png'), ()),
                (('med', 'analysis', 'doc-1234567890123456'), ()),                 # a file, not a folder
                (('_redacted', 'doc-1234567890123456\n', 'page-01.png'), ('manifest.json',))):
            with self.subTest('/'.join(parts)):
                ok, f = self._private_with_path(*parts, beside=beside)
                self.assertFalse(ok)
                self.assertTrue(any('residue in a path' in x.category for x in f))

    def test_valid_one_patient_green(self):
        t = Tree(self); self._one_source_patient(t)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_sources_without_manifest_red(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'X')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('without a manifest' in x.category for x in f))

    def test_sources_without_person_id_red(self):
        t = Tree(self)
        t.patient('alpha', person_id=None).src('alpha', '2026-01-01__source__a.pdf', b'X')
        t.manifest('alpha', [rec(data=b'X')])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('person record id' in x.category for x in f))

    def test_missing_source_on_disk_red(self):
        t = Tree(self); t.patient('alpha')
        t.manifest('alpha', [rec(data=b'X')])  # record but no file
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('not on disk' in x.category for x in f))

    def test_changed_bytes_red(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'ORIGINAL')
        t.manifest('alpha', [rec(relpath='med/sources/2026-01-01__source__a.pdf', data=b'DIFFERENT')])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('do not match recorded sha256' in x.category for x in f))

    def test_wrong_person_id_red(self):
        t = Tree(self); t.patient('alpha', person_id=PID).src('alpha', '2026-01-01__source__a.pdf', b'X')
        t.manifest('alpha', [rec(person_id=PID2, data=b'X')])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('does not match profile' in x.category for x in f))

    def test_uninventoried_source_red(self):
        t = Tree(self); self._one_source_patient(t)
        t.src('alpha', '2026-01-02__source__b.pdf', b'B')  # extra file, no record
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('no active manifest record' in x.category for x in f))

    # --- unreadable directories must RED, never vanish (2026-08-23 audit: os.walk onerror=None) ---
    def _need_mode_bits(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('root ignores directory mode bits; chmod 000 cannot deny')

    def _locked_subdir(self, t, handle='alpha'):
        sub = os.path.join(t.root, 'patients', handle, 'med', 'sources', 'locked')
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(sub, '2026-01-02__source__hidden.pdf'), 'wb') as f:
            f.write(b'HIDDEN')
        os.chmod(sub, 0)
        return sub

    def test_unreadable_sources_subdir_zero_record_manifest_red(self):
        self._need_mode_bits()
        t = Tree(self); t.patient('alpha').manifest('alpha', [])
        self._locked_subdir(t)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('unreadable directory' in x.category for x in f))

    def test_unreadable_sources_subdir_populated_manifest_red(self):
        """Inventoried files stay protected by 'not on disk'; the hole was an UN-inventoried file
        inside an unlistable subdirectory passing GREEN even with a populated manifest."""
        self._need_mode_bits()
        t = Tree(self); self._one_source_patient(t)
        self._locked_subdir(t)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('unreadable directory' in x.category for x in f))

    def test_unreadable_sources_root_red(self):
        self._need_mode_bits()
        t = Tree(self); t.patient('alpha').manifest('alpha', [])
        sd = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        with open(os.path.join(sd, '2026-01-02__source__hidden.pdf'), 'wb') as f:
            f.write(b'HIDDEN')
        os.chmod(sd, 0)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('unreadable directory' in x.category for x in f))

    def test_unreadable_dir_does_not_leak_locator(self):
        self._need_mode_bits()
        t = Tree(self); t.patient('alpha').manifest('alpha', [])
        self._locked_subdir(t)
        _ok, f = t.is_green()
        hits = [x for x in f if 'unreadable directory' in x.category]
        self.assertTrue(hits)
        self.assertTrue(all(not x.relpath for x in hits))

    def test_private_mode_residue_scan_unreadable_red(self):
        self._need_mode_bits()
        t = Tree(self); t.patient('alpha').manifest('alpha', [])
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a', encoding='utf-8') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        self._locked_subdir(t)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('residue scan could not list' in x.category for x in f))

    def test_hidden_evidence_is_not_silently_ignored(self):
        t = Tree(self); t.patient('alpha').src('alpha', '.hidden-evidence.pdf', b'X')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('without a manifest' in x.category for x in f))

    def test_known_os_cruft_is_still_ignored(self):
        t = Tree(self); t.patient('alpha').src('alpha', '.DS_Store', b'cruft')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_nested_readme_is_evidence_not_global_boilerplate(self):
        t = Tree(self); t.patient('alpha').src('alpha', 'nested/README.md', b'EVIDENCE')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('without a manifest' in x.category for x in f))

    def test_symlinked_root_readme_is_not_exempt(self):
        t = Tree(self); t.patient('alpha')
        target = os.path.join(t.root, 'outside');
        with open(target, 'wb') as fh: fh.write(b'X')
        os.symlink(target, os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', 'README.md'))
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('symlink' in x.category or 'without a manifest' in x.category for x in f))

    def test_symlinked_profile_red(self):
        t = Tree(self); self._one_source_patient(t)
        external = os.path.join(t.root, 'outside-profile.md')
        with open(external, 'w') as fh:
            fh.write('# profile\n## Identity\n- Person record ID: `%s`\n' % PID)
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        os.remove(profile); os.symlink(external, profile)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('profile.md is a symlink' in x.category for x in f))

    def test_duplicate_person_id_across_patients_red(self):
        t = Tree(self); self._one_source_patient(t, 'alpha', b'A')
        self._one_source_patient(t, 'beta', b'B')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('reused across patient roots' in x.category for x in f))

    def test_multiple_person_ids_in_one_profile_red(self):
        t = Tree(self); self._one_source_patient(t)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- **Person record ID (local-only):** `%s`\n' % PID2)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('more than one person record id' in x.category for x in f))

    def test_person_id_outside_identity_section_is_not_canonical(self):
        t = Tree(self); self._one_source_patient(t)
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        with open(profile, 'w') as fh:
            fh.write('# profile\n## Identity\n- no canonical id\n## Change log\n'
                     '- **Person record ID (local-only):** `%s`\n' % PID)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('outside the Identity section' in x.category for x in f))

    def test_shipped_profile_template_field_round_trips_after_substitution(self):
        template = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                '_templates', 'profile.md')
        with open(template, encoding='utf-8') as fh:
            body = fh.read().replace('{{32 lowercase hex}}', PID)
        with tempfile.TemporaryDirectory() as td:
            profile = os.path.join(td, 'profile.md')
            with open(profile, 'w', encoding='utf-8') as fh:
                fh.write(body)
            self.assertEqual(fsverify.read_person_ids(profile), [PID])

    def test_empty_patient_with_symlinked_manifest_red(self):
        t = Tree(self); t.patient('alpha')
        target = os.path.join(t.root, 'outside-manifest')
        with open(target, 'w') as fh: fh.write('')
        os.symlink(target, os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'))
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('manifest is a symlink' in x.category for x in f))

    def test_empty_patient_with_orphan_checkpoint_red(self):
        t = Tree(self); t.patient('alpha')
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint'), 'w') as fh:
            fh.write('{}\n')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('checkpoint exists without a manifest' in x.category for x in f))

    def test_empty_manifest_without_checkpoint_red(self):
        t = Tree(self); t.patient('alpha').manifest('alpha', [], checkpoint=None)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('without a valid MANIFEST.checkpoint' in x.category for x in f))

    def test_empty_manifest_with_matching_checkpoint_green(self):
        t = Tree(self); t.patient('alpha').manifest('alpha', [])
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_empty_manifest_with_malformed_checkpoint_red(self):
        t = Tree(self); t.patient('alpha').manifest('alpha', [], checkpoint={})
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('checkpoint:' in x.category for x in f))

    def test_empty_manifest_with_duplicate_checkpoint_key_red(self):
        t = Tree(self); t.patient('alpha').manifest('alpha', [])
        cp = os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint')
        with open(cp, 'w') as fh:
            fh.write('{"schema_version":1,"schema_version":1,"manifest_sha256":"%s",'
                     '"record_count":0,"tail_record_id":""}\n' % sha(b''))
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('checkpoint unreadable' in x.category for x in f))

    def test_sources_path_as_regular_file_red(self):
        t = Tree(self); t.patient('alpha')
        sources = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        os.rmdir(sources)
        with open(sources, 'w') as fh: fh.write('not a directory')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('sources exists but is not a directory' in x.category for x in f))

    def test_profile_path_as_directory_red(self):
        t = Tree(self); t.patient('alpha')
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        os.remove(profile); os.mkdir(profile)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('profile.md exists but is not a regular file' in x.category for x in f))

    def test_patients_root_as_regular_file_red(self):
        t = Tree(self); os.rmdir(os.path.join(t.root, 'patients'))
        with open(os.path.join(t.root, 'patients'), 'w') as fh: fh.write('wrong type')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('patients/ root exists but is not a directory' in x.category for x in f))

    def test_private_locator_never_renders_identifier_bearing_path(self):
        t = Tree(self); self._one_source_patient(t)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        t.src('alpha', '2026-01-02__source__01020312340.pdf', b'B')
        ok, f = t.is_green(); self.assertFalse(ok)
        rendered = '\n'.join(x.render() for x in f)
        self.assertNotIn('01020312340', rendered)
        self.assertTrue(any('residue in a path' in x.category for x in f))

    def _cli_verify(self, t):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.main(['--root', t.root, 'verify'])
        return code, buf.getvalue()

    def test_cli_red_names_the_path(self):
        t = Tree(self); self._one_source_patient(t)
        t.src('alpha', '2026-01-01__source__a.pdf', b'DRIFTED')
        code, out = self._cli_verify(t)
        self.assertEqual(code, 1)
        self.assertIn('drift) — patients/alpha/med/sources/2026-01-01__source__a.pdf', out)
        self.assertNotIn(PID, out)

    def test_cli_red_withholds_path_for_private_mode_person(self):
        t = Tree(self); self._one_source_patient(t)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        t.src('alpha', '2026-01-01__source__a.pdf', b'DRIFTED')
        code, out = self._cli_verify(t)
        self.assertEqual(code, 1)
        self.assertIn(fsverify.WITHHELD_PRIVATE, out)
        self.assertNotIn('alpha', out)
        self.assertNotIn('source__a', out)

    def test_cli_shared_path_withheld_only_while_private_mode_in_use(self):
        t = Tree(self); t.patient('alpha')
        t.shared('scan.pdf', b'evidence-shaped')
        code, out = self._cli_verify(t)
        self.assertEqual(code, 1)
        self.assertIn('_shared/med/scan.pdf', out)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        code, out = self._cli_verify(t)
        self.assertEqual(code, 1)
        self.assertIn(fsverify.WITHHELD_UNKNOWN, out)
        self.assertNotIn('scan.pdf', out)

    def test_private_manifest_free_text_residue_red_without_echo(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'A')
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        r = rec(data=b'A'); r['identity_source'] = 'synthetic 01020312340'
        t.manifest('alpha', [r])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertNotIn('01020312340', '\n'.join(x.render() for x in f))
        self.assertTrue(any('manifest metadata' in x.category for x in f))

    def test_nfc_key_collision_red(self):
        """Red-team fix: two distinct on-disk source names that NFC-normalize to the SAME path (possible
        on a byte-based FS like ext4) must RED, not silently drop one from both checks. macOS/APFS
        collapses the pair, so we exercise the defect site by feeding the two colliding entries directly."""
        import unicodedata
        from unittest import mock
        t = Tree(self); t.patient('alpha')
        realA = os.path.join(t.root, 'A'); realB = os.path.join(t.root, 'B')
        with open(realA, 'wb') as fh: fh.write(b'LEGIT')
        with open(realB, 'wb') as fh: fh.write(b'WRONG-PERSON')
        nfc = 'labs/2026-01-01__lab__' + unicodedata.normalize('NFC', 'café') + '.pdf'
        nfd = 'labs/2026-01-01__lab__' + unicodedata.normalize('NFD', 'café') + '.pdf'
        self.assertNotEqual(nfc, nfd)
        t.manifest('alpha', [rec(relpath='med/sources/' + nfc, data=b'LEGIT')])

        def fake_scan(sd):  # (abspath, rel_from_sources, issue) — colliding NFC keys
            return ([(realA, nfc, False), (realB, nfd, False)], [])
        with mock.patch('tools.person_ownership.fsverify._scan_sources', side_effect=fake_scan):
            ok, f = t.is_green()
        self.assertFalse(ok)
        self.assertTrue(any('NFC collision' in x.category for x in f))

    def test_symlinked_sources_dir_red(self):
        """Red-team fix: a symlinked med/sources must RED (un-inventoried evidence behind it), not be
        treated as an empty source set (a silent false-GREEN)."""
        t = Tree(self); t.patient('alpha')
        real = os.path.join(t.root, 'real-sources'); os.makedirs(real)
        with open(os.path.join(real, '2026-01-01__lab__x.pdf'), 'wb') as fh: fh.write(b'X')
        sd = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        os.rmdir(sd); os.symlink(real, sd)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('med/sources is a symlink' in x.category for x in f))

    def test_symlinked_patient_dir_red(self):
        t = Tree(self)
        real = os.path.join(t.root, 'real-alpha', 'med', 'sources'); os.makedirs(real)
        with open(os.path.join(real, '2026-01-01__lab__x.pdf'), 'wb') as fh: fh.write(b'X')
        os.symlink(os.path.join(t.root, 'real-alpha'), os.path.join(t.root, 'patients', 'alpha'))
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('patient directory is a symlink' in x.category for x in f))

    def test_symlink_source_red(self):
        t = Tree(self); t.patient('alpha')
        target = os.path.join(t.root, 'outside.bin')
        with open(target, 'wb') as fh:
            fh.write(b'X')
        link = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', '2026-01-01__source__a.pdf')
        os.symlink(target, link)
        t.manifest('alpha', [rec(data=b'X')])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('symlink' in x.category for x in f))

    def test_fifo_source_reds_without_being_opened(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        t = Tree(self); t.patient('alpha')
        relname = '2026-01-01__source__a.pdf'
        path = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', relname)
        os.mkfifo(path)
        t.manifest('alpha', [rec(relpath='med/sources/' + relname, data=b'NEVER-READ')])
        original = fsverify._sha256_file
        fsverify._sha256_file = lambda _p: (_ for _ in ()).throw(
            AssertionError('a non-regular source must be rejected before hashing'))
        try:
            ok, findings = t.is_green()
        finally:
            fsverify._sha256_file = original
        self.assertFalse(ok)
        self.assertTrue(any('not a readable regular file' in x.category for x in findings))

    def test_partial_manifest_red(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'X')
        t.raw_manifest('alpha', '{"schema_version":1}')  # no trailing newline
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('unparseable' in x.category for x in f))

    def test_checkpoint_mismatch_red(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'X')
        r = rec(data=b'X')
        bad_cp = {'schema_version': 1, 'manifest_sha256': '0' * 64, 'record_count': 1, 'tail_record_id': r['record_id']}
        t.manifest('alpha', [r], checkpoint=bad_cp)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('checkpoint' in x.category for x in f))

    def test_missing_checkpoint_red(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'X')
        t.manifest('alpha', [rec(data=b'X')], checkpoint=None)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('checkpoint' in x.category for x in f))

    def test_truncated_ledger_red(self):
        # checkpoint claims 2 records, manifest has 1 -> truncation
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'X')
        r = rec(data=b'X')
        cp = {'schema_version': 1, 'manifest_sha256': sha((json.dumps(r, sort_keys=True) + '\n').encode()),
              'record_count': 2, 'tail_record_id': r['record_id']}
        t.manifest('alpha', [r], checkpoint=cp)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('record_count' in x.category for x in f))

    def test_in_place_mutation_red(self):
        # rewrite a record's status in place (append-only violated) -> checkpoint hash mismatch
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'X')
        good = rec(data=b'X')
        t.manifest('alpha', [good])  # checkpoint auto over good
        mutated = dict(good, identity_status='operator-confirmed', identity_reviewer='operator')
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        with open(os.path.join(med, 'MANIFEST'), 'w') as fh:
            fh.write(json.dumps(mutated, sort_keys=True) + '\n')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('checkpoint' in x.category for x in f))


class DerivativeTests(unittest.TestCase):
    def test_valid_ocr_derivative_green(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'SRC')
        t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR')
        r = rec(data=b'SRC', derivs=[{'derivative_relpath': 'med/sources/2026-01-01__source__a.ocr.md',
                                      'derivative_sha256': sha(b'OCR')}])
        t.manifest('alpha', [r])
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_unbound_ocr_red(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'SRC')
        t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR')
        t.manifest('alpha', [rec(data=b'SRC')])  # no derivative binding
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('no manifest binding' in x.category for x in f))

    def test_wrong_hash_derivative_red(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'SRC')
        t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR')
        r = rec(data=b'SRC', derivs=[{'derivative_relpath': 'med/sources/2026-01-01__source__a.ocr.md',
                                      'derivative_sha256': sha(b'WRONG')}])
        t.manifest('alpha', [r])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('derivative bytes' in x.category for x in f))

    def test_missing_derivative_file_red(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'SRC')
        r = rec(data=b'SRC', derivs=[{'derivative_relpath': 'med/sources/2026-01-01__source__a.ocr.md',
                                      'derivative_sha256': sha(b'OCR')}])
        t.manifest('alpha', [r])
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('not on disk' in x.category for x in f))


class SharedShapeTests(unittest.TestCase):
    def test_shared_unreadable_subdir_red(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('root ignores directory mode bits; chmod 000 cannot deny')
        t = Tree(self); t.shared('note.md', 'fine\n')
        sub = os.path.join(t.root, '_shared', 'med', 'locked')
        os.makedirs(sub)
        with open(os.path.join(sub, 'evidence.pdf'), 'wb') as f:
            f.write(b'X')
        os.chmod(sub, 0)
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('unreadable directory' in x.category for x in f))

    def test_boilerplate_not_evidence_no_record_needed(self):
        # a per-patient README.md is boilerplate, excluded from the evidence set: it needs no
        # manifest record and does not RED (the exclusion the cross-root check would have relied on).
        t = Tree(self)
        t.patient('alpha').src('alpha', 'README.md', b'INTAKE-CHECKLIST')
        t.src('alpha', '2026-01-01__source__a.pdf', b'A')
        t.manifest('alpha', [rec(data=b'A')])
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_shared_md_prose_green(self):
        t = Tree(self); self._green_patient(t)
        t.shared('2026-01-01__coordination__note.md', 'joint care note (pointer-level)\n')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_shared_non_md_red(self):
        t = Tree(self); self._green_patient(t)
        t.shared('scan.pdf', b'%PDF-EVIDENCE-SHAPED')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('_shared/med' in x.category for x in f))

    def test_shared_fifo_named_markdown_is_not_prose(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        t = Tree(self); self._green_patient(t)
        shared = os.path.join(t.root, '_shared', 'med')
        os.makedirs(shared)
        os.mkfifo(os.path.join(shared, 'coordination.md'))
        ok, findings = t.is_green()
        self.assertFalse(ok)
        self.assertTrue(any('_shared/med non-regular file' in x.category for x in findings))

    def test_symlinked_shared_med_root_red(self):
        t = Tree(self); self._green_patient(t)
        outside = os.path.join(t.root, 'outside-shared'); os.makedirs(outside)
        with open(os.path.join(outside, 'note.md'), 'w') as fh: fh.write('pointer prose\n')
        os.makedirs(os.path.join(t.root, '_shared'))
        os.symlink(outside, os.path.join(t.root, '_shared', 'med'))
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('_shared/med is a symlink' in x.category for x in f))

    def test_shared_med_as_regular_file_red(self):
        t = Tree(self); self._green_patient(t)
        os.makedirs(os.path.join(t.root, '_shared'))
        with open(os.path.join(t.root, '_shared', 'med'), 'w') as fh: fh.write('wrong type')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('_shared/med exists but is not a directory' in x.category for x in f))

    def test_shared_root_as_regular_file_red(self):
        t = Tree(self); self._green_patient(t)
        with open(os.path.join(t.root, '_shared'), 'w') as fh: fh.write('wrong type')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('_shared exists but is not a directory' in x.category for x in f))

    def test_private_shared_prose_residue_red_without_echo(self):
        t = Tree(self); self._green_patient(t)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        t.shared('coordination.md', 'synthetic 01020312340\n')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertNotIn('01020312340', '\n'.join(x.render() for x in f))
        self.assertTrue(any('prose' in x.category for x in f))

    def test_private_shared_prose_dated_non_id_waiver_green(self):
        t = Tree(self); self._green_patient(t)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        t.shared('coordination.md',
                 'synthetic 01020312340 ⟨not-an-id: verified 2026-07-17⟩\n')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def _green_patient(self, tree):
        tree.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'A')
        tree.manifest('alpha', [rec(data=b'A')])


# ---------------------------------------------------------------------------
# Phase 3 — migration (deterministic, byte-preserving, legacy-folder-only)
# ---------------------------------------------------------------------------
class MigrationTests(unittest.TestCase):
    def _corpus(self, tc):
        t = Tree(tc)
        t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
        t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR-A')
        t.patient('beta', person_id=PID2)
        t.src('beta', '2026-02-02__source__b.pdf', b'BBBB')
        return t

    def test_migrate_defaults_legacy_and_greens(self):
        t = self._corpus(self)
        pre = {h: migrate._evidence_inventory(os.path.join(t.root, 'patients', h, 'med', 'sources'))
               for h in ('alpha', 'beta')}
        agg = migrate.migrate(t.root, today='2026-07-14')
        self.assertEqual(agg['migrated'], 2)
        self.assertEqual(agg['total_legacy_folder_only'], 2)  # one primary source each
        # every evidence byte unchanged (content-only integrity)
        post = {h: migrate._evidence_inventory(os.path.join(t.root, 'patients', h, 'med', 'sources'))
                for h in ('alpha', 'beta')}
        self.assertEqual(pre, post)
        # and the migrated tree is L13-green
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        # all records are legacy-folder-only
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST')) as fh:
            recs = [json.loads(l) for l in fh]
        self.assertTrue(all(r['identity_status'] == 'legacy-folder-only' for r in recs))
        self.assertEqual(recs[0]['derivatives'][0]['derivative_relpath'],
                         'med/sources/2026-01-01__source__a.ocr.md')

    def test_migrate_mints_person_id_when_absent(self):
        t = Tree(self); t.patient('alpha', person_id=None)
        t.src('alpha', '2026-01-01__source__a.pdf', b'A')
        migrate.migrate(t.root, today='2026-07-14')
        pid = fsverify.read_person_id(os.path.join(t.root, 'patients', 'alpha', 'profile.md'))
        self.assertIsNotNone(pid)
        self.assertRegex(pid, r'^[0-9a-f]{32}$')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_migrate_refuses_to_overwrite(self):
        t = self._corpus(self)
        migrate.migrate(t.root, today='2026-07-14')
        with self.assertRaisesRegex(migrate.MigrationStop, 'already exists'):
            migrate.write_manifest(t.root, 'alpha', [rec()])

    def test_migrate_skips_migrated_person_and_creates_the_missing_ledger(self):
        # alpha: one source, migrated; beta: interview-only, not yet migrated.
        # Second migrate should skip alpha untouched and create beta's MANIFEST.
        t = Tree(self)
        t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
        migrate.migrate(t.root, today='2026-07-14')
        alpha_manifest_before = _read_bytes(t, handle='alpha')
        # Add beta with only an interview source
        t.patient('beta', person_id=PID2).src('beta', 'interviews/2026-01-02__interview__demo.md', b'interview')
        # Run migrate again — on a LATER day: migrate stamps its run date into every record it writes,
        # so a rewrite of alpha's ledger could not hide behind byte-identical output.
        agg = migrate.migrate(t.root, today='2026-07-15')
        self.assertEqual(agg['migrated'], 1)  # only beta is new
        # alpha's MANIFEST is unchanged
        alpha_manifest_after = _read_bytes(t, handle='alpha')
        self.assertEqual(alpha_manifest_before, alpha_manifest_after)
        # beta's MANIFEST now exists
        self.assertTrue(os.path.exists(os.path.join(t.root, 'patients', 'beta', 'med', 'MANIFEST')))
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_interview_as_first_source_then_a_later_interview(self):
        # gamma: interview-only, no manifest. append.add_source should refuse.
        # After migrate, it should work. A second interview should register fine.
        t = Tree(self)
        t.patient('gamma', person_id=PID2).src('gamma', 'interviews/2026-01-02__interview__first.md', b'first')
        # Refuse append before migrate (no manifest)
        with self.assertRaisesRegex(append.AppendStop, 'no MANIFEST to append to'):
            append.add_source(t.root, 'gamma', 'med/sources/interviews/2026-01-02__interview__first.md', today='2026-07-18')
        # Migrate creates the manifest
        migrate.migrate(t.root, today='2026-07-14')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        # Add a second interview
        t.src('gamma', 'interviews/2026-01-03__interview__second.md', b'second')
        append.add_source(t.root, 'gamma', 'med/sources/interviews/2026-01-03__interview__second.md', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_migrate_orphan_ocr_stops(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'A')
        t.src('alpha', '2026-01-09__source__orphan.ocr.md', b'ORPHAN')  # no matching primary stem
        with self.assertRaisesRegex(migrate.MigrationStop, 'ambiguous or orphan'):
            migrate.migrate(t.root, today='2026-07-14')

    def test_migrate_rejects_symlink_even_when_named_as_cruft(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'A')
        outside = os.path.join(t.root, 'outside-cruft')
        with open(outside, 'wb') as fh: fh.write(b'X')
        os.symlink(outside, os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', '._hidden'))
        with self.assertRaisesRegex(migrate.MigrationStop, 'symlinked source file'):
            migrate.migrate(t.root, today='2026-07-14')

    def test_migrate_stops_on_unreadable_subdir(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('root ignores directory mode bits; chmod 000 cannot deny')
        t = Tree(self); t.patient('alpha')
        sources = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        sub = os.path.join(sources, 'locked'); os.makedirs(sub)
        with open(os.path.join(sub, '2026-01-01__source__a.pdf'), 'wb') as f:
            f.write(b'A')
        os.chmod(sub, 0)
        with self.assertRaises(migrate.MigrationStop) as cm:
            migrate._patient_source_files(sources)
        self.assertIn('unreadable', str(cm.exception))
        with self.assertRaisesRegex(migrate.MigrationStop, 'unreadable directory'):
            migrate._count_non_nfc(sources)

    def test_migrate_rejects_fifo_source_before_hashing(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        t = Tree(self); t.patient('alpha')
        sources = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        os.mkfifo(os.path.join(sources, '2026-01-01__source__a.pdf'))
        with self.assertRaises(migrate.MigrationStop) as cm:
            migrate._patient_source_files(sources)
        self.assertIn('non-regular', str(cm.exception))

    def test_migrate_rejects_fifo_profile_before_reading(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        t = Tree(self); t.patient('alpha')
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        os.remove(profile); os.mkfifo(profile)
        sources = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        with self.assertRaises(migrate.MigrationStop) as cm:
            migrate._patient_source_files(sources)
        self.assertIn('profile.md', str(cm.exception))

    def test_migrate_preserves_orphan_checkpoint_and_writes_no_manifest(self):
        # An orphan checkpoint (no MANIFEST) is prior ownership state: the patient is SURFACED
        # (skipped, per-patient — one broken node must not abort the fleet), the checkpoint bytes
        # preserved, and no MANIFEST/person-id write happens.
        t = Tree(self); t.patient('alpha', person_id=None).src(
            'alpha', '2026-01-01__source__a.pdf', b'A')
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        with open(profile, 'rb') as fh:
            profile_before = fh.read()
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        checkpoint = os.path.join(med, 'MANIFEST.checkpoint')
        sentinel = b'operator-owned orphan checkpoint\n'
        with open(checkpoint, 'wb') as fh:
            fh.write(sentinel)
        agg = migrate.migrate(t.root, today='2026-07-14')
        self.assertEqual(agg['migrated'], 0)  # surfaced-skipped, not migrated
        with open(checkpoint, 'rb') as fh:
            self.assertEqual(fh.read(), sentinel)
        with open(profile, 'rb') as fh:
            self.assertEqual(fh.read(), profile_before)
        self.assertFalse(os.path.lexists(os.path.join(med, 'MANIFEST')))

    def test_rerun_recovers_checkpointless_clean_migration(self):
        # Recovery is by RE-DERIVE (pristine + inventory-gated, §11.1), so a recovered patient
        # counts as migrated; the rebuilt ledger is green.
        t = Tree(self); t.patient('alpha').src(
            'alpha', '2026-01-01__source__a.pdf', b'A')
        migrate.migrate(t.root, today='2026-07-14')
        checkpoint = os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint')
        os.remove(checkpoint)  # simulate death after MANIFEST replace, before checkpoint replace
        ok, _ = t.is_green(); self.assertFalse(ok)
        agg = migrate.migrate(t.root, today='2026-07-14')
        self.assertEqual(agg['migrated'], 1)
        self.assertTrue(os.path.isfile(checkpoint))
        ok, findings = t.is_green(); self.assertTrue(ok, [x.render() for x in findings])

    def test_checkpointless_nonmigration_ledger_is_not_blessed(self):
        t = Tree(self); t.patient('alpha').src(
            'alpha', '2026-01-01__source__a.pdf', b'A')
        migrate.migrate(t.root, today='2026-07-14')
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        checkpoint = os.path.join(med, 'MANIFEST.checkpoint')
        os.remove(checkpoint)
        with open(os.path.join(med, 'MANIFEST'), encoding='utf-8') as fh:
            record = json.loads(fh.readline())
        record.update(identity_status='operator-confirmed', identity_reviewer='operator',
                      identity_source='operator review')
        with open(os.path.join(med, 'MANIFEST'), 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        # Non-pristine (carries an attestation): SURFACED per patient — never re-derived (which would
        # destroy the claim), never blessed; the tree stays RED until the operator resolves it.
        agg = migrate.migrate(t.root, today='2026-07-14')
        self.assertEqual(agg['migrated'], 0)
        self.assertFalse(os.path.lexists(checkpoint))
        ok, _ = t.is_green(); self.assertFalse(ok)

    def test_checkpointless_migration_shaped_but_nondeterministic_ledger_is_not_blessed(self):
        t = Tree(self); t.patient('alpha').src(
            'alpha', '2026-01-01__source__a.pdf', b'A')
        migrate.migrate(t.root, today='2026-07-14')
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        checkpoint = os.path.join(med, 'MANIFEST.checkpoint')
        os.remove(checkpoint)
        manifest = os.path.join(med, 'MANIFEST')
        with open(manifest, encoding='utf-8') as fh:
            record = json.loads(fh.readline())
        record['capture_method'] = 'photo'
        with open(manifest, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        # Pristine + inventory-matching, so re-derive fires and the L13-unchecked metadata hand-edit
        # is DISCARDED (not blessed): the rebuilt record carries migration's deterministic value.
        agg = migrate.migrate(t.root, today='2026-07-14')
        self.assertEqual(agg['migrated'], 1)
        self.assertTrue(os.path.isfile(checkpoint))
        with open(manifest, encoding='utf-8') as fh:
            rebuilt = json.loads(fh.readline())
        self.assertEqual(rebuilt['capture_method'], 'scan')
        ok, findings = t.is_green(); self.assertTrue(ok, [x.render() for x in findings])

    def test_migrate_stdout_has_no_identifier(self):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        t = self._corpus(self)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.main(['--root', t.root, 'migrate'])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertNotIn('alpha', out)   # no handle
        self.assertNotIn('source__a', out)  # no path
        self.assertNotIn(PID, out)       # no person id

    def test_report_cannot_overwrite_or_escape_outputs_ownership(self):
        t = self._corpus(self)
        target = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources',
                              '2026-01-01__source__a.pdf')
        with self.assertRaisesRegex(migrate.MigrationStop, 'new direct child of outputs/ownership'):
            migrate.pilot(t.root, report_path=target)
        with open(target, 'rb') as fh:
            self.assertEqual(fh.read(), b'AAAA')

    def test_report_writes_new_private_file_under_outputs_ownership(self):
        t = self._corpus(self)
        rel = os.path.join('outputs', 'ownership', 'pilot.json')
        migrate.pilot(t.root, report_path=rel)
        path = os.path.join(t.root, rel)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_nfd_source_records_nfc_relpath_and_greens(self):
        """A non-NFC (NFD) source filename is recorded with an NFC source_relpath, the bytes are
        untouched (no on-disk rename), and L13 is green because the verifier NFC-normalizes the
        on-disk name to match. (macOS filesystems return the NFD name that was written.)"""
        import unicodedata
        t = Tree(self); t.patient('alpha')
        nfd_name = unicodedata.normalize('NFD', '2026-01-01__source__zażółć.pdf')
        t.src('alpha', nfd_name, b'DIACRITIC')
        migrate.migrate(t.root, today='2026-07-14')
        # the manifest records the NFC relpath (schema requires NFC)
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST')) as fh:
            recs = [json.loads(l) for l in fh]
        nfc_rel = 'med/sources/' + unicodedata.normalize('NFC', nfd_name)
        self.assertEqual(recs[0]['source_relpath'], nfc_rel)
        self.assertEqual(schema.validate_record(recs[0]), [])  # NFC relpath passes schema
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])


def _migrated(tc, handle='alpha', primary='2026-01-01__source__a.pdf', data=b'AAAA', person_id=PID):
    """A one-source migrated, L13-green patient tree ready for append tests."""
    t = Tree(tc); t.patient(handle, person_id=person_id).src(handle, primary, data)
    migrate.migrate(t.root, today='2026-07-14')
    ok, f = t.is_green(); tc.assertTrue(ok, [x.render() for x in f])
    return t


def _records(t, handle='alpha'):
    with open(os.path.join(t.root, 'patients', handle, 'med', 'MANIFEST')) as fh:
        return [json.loads(l) for l in fh]


def _opened_by(fn):
    """Basenames of the files `fn` opens. It spies on builtins.open, so a read through a helper in
    another module (fsverify's hashing) counts too; a spy on `append.open` alone missed that."""
    from unittest import mock
    real_open, opened = open, []

    def spy(path, *a, **k):
        opened.append(os.path.basename(str(path)))
        return real_open(path, *a, **k)
    with mock.patch('builtins.open', spy):
        fn()
    return opened


def _read_bytes(t, handle='alpha', name='MANIFEST'):
    with open(os.path.join(t.root, 'patients', handle, 'med', name), 'rb') as fh:
        return fh.read()


def _active_status(t, relpath, handle='alpha'):
    active, _ = schema.supersession_errors(_records(t, handle))
    for r in active:
        if r['source_relpath'] == relpath:
            return r
    return None


class FinalizeTests(unittest.TestCase):
    """The prefix-validating finalizer (ADR-0037 §11) — crash recovery that cannot re-bless a rewrite."""
    def test_finalize_cannot_rebless_an_inplace_rewrite(self):
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        recs = _records(t)
        recs[0]['review_date'] = '2026-07-15'  # rewrite the checkpointed prefix record in place
        with open(os.path.join(med, 'MANIFEST'), 'w') as fh:
            fh.write(json.dumps(recs[0], sort_keys=True, ensure_ascii=False) + '\n')
        ok, _ = t.is_green(); self.assertFalse(ok)  # RED (checkpoint hash mismatch)
        with self.assertRaisesRegex(append.AppendStop, 'checkpointed prefix does not match'):
            append.prefix_finalize(t.root, 'alpha')
        ok, _ = t.is_green(); self.assertFalse(ok)  # still RED — never re-blessed

    def test_finalize_recovers_a_crash_between_the_two_writes(self):
        # simulate: append advanced MANIFEST (2 records) but crashed before the checkpoint advanced.
        t = _migrated(self)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        mbytes = _read_bytes(t)
        recs = schema.parse_manifest_bytes(mbytes)
        line0 = mbytes.split(b'\n')[0] + b'\n'
        stale = {'schema_version': 1, 'manifest_sha256': sha(line0), 'record_count': 1,
                 'tail_record_id': recs[0]['record_id']}
        with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w') as fh:
            json.dump(stale, fh, sort_keys=True)
        ok, _ = t.is_green(); self.assertFalse(ok)  # RED: checkpoint behind manifest
        append.prefix_finalize(t.root, 'alpha')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])  # recovered

    def test_finalize_refuses_a_row_reviving_a_retraction(self):
        # a hand-appended row superseding a wrong-owner retraction would bring the retracted document
        # back into this person's record; no writer op supersedes a retraction (§14)
        t = _migrated(self)
        rel = 'med/sources/2026-01-01__source__a.pdf'
        p = os.path.join(t.root, 'patients', 'alpha', rel)
        os.remove(p)
        append.wrong_owner(t.root, 'alpha', rel, today='2026-07-18')
        with open(p, 'wb') as fh:
            fh.write(b'AAAA')
        ret = _records(t)[-1]
        row = dict(ret, record_id='eeeeeeeeeeeeeeee', supersedes=ret['record_id'],
                   supersede_reason='status-change', supersede_date='2026-07-19')
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn('wrong-owner retraction', str(cm.exception))
        ok, _ = t.is_green(); self.assertFalse(ok)

    def test_finalize_refuses_a_shorter_manifest_than_checkpoint(self):
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        mbytes = _read_bytes(t)
        recs = schema.parse_manifest_bytes(mbytes)
        cp = {'schema_version': 1, 'manifest_sha256': sha(mbytes), 'record_count': 2,
              'tail_record_id': recs[0]['record_id']}
        with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w') as fh:
            json.dump(cp, fh, sort_keys=True)
        with self.assertRaisesRegex(append.AppendStop, 'shorter than its checkpoint'):
            append.prefix_finalize(t.root, 'alpha')


class AppendWriterTests(unittest.TestCase):
    def test_add_later_source_greens_and_preserves_byte_prefix(self):
        t = _migrated(self)
        before = _read_bytes(t)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        after = _read_bytes(t)
        self.assertTrue(after.startswith(before))  # exact append-only byte prefix
        self.assertEqual(len(_records(t)), 2)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_add_binds_its_1to1_ocr_derivative(self):
        t = _migrated(self)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        t.src('alpha', '2026-02-02__source__b.ocr.md', b'OCR-B')
        append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        r = _active_status(t, 'med/sources/2026-02-02__source__b.pdf')
        self.assertEqual(r['derivatives'][0]['derivative_relpath'],
                         'med/sources/2026-02-02__source__b.ocr.md')

    def test_add_confirmed_uses_operator_reviewer(self):
        t = _migrated(self)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf',
                          confirmed=True, today='2026-07-18')
        r = _active_status(t, 'med/sources/2026-02-02__source__b.pdf')
        self.assertEqual(r['identity_status'], 'operator-confirmed')
        self.assertEqual(r['identity_reviewer'], 'operator')

    def test_add_refuses_when_active_record_already_exists(self):
        t = _migrated(self)
        with self.assertRaisesRegex(append.AppendStop, 'active record already exists'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')

    def test_add_refuses_uninventoried_file_not_on_disk(self):
        t = _migrated(self)
        with self.assertRaisesRegex(append.AppendStop, 'not present on disk'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-09-09__source__ghost.pdf', today='2026-07-18')

    def test_add_refuses_a_derivative_stem_as_primary(self):
        t = _migrated(self)
        t.src('alpha', '2026-02-02__source__b.ocr.md', b'OCR')
        with self.assertRaisesRegex(append.AppendStop, 'not a primary source'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.ocr.md', today='2026-07-18')

    def test_add_refuses_onto_a_drifted_tree_and_rolls_back(self):
        # a pre-existing, unrelated drift must block the append (fail closed) and leave bytes untouched.
        t = _migrated(self)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        # drift the ALREADY-inventoried source a.pdf
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'sources',
                               '2026-01-01__source__a.pdf'), 'wb') as fh:
            fh.write(b'TAMPERED')
        before = _read_bytes(t)
        with self.assertRaisesRegex(append.AppendStop, 'would leave L13 red'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        after = _read_bytes(t)
        self.assertEqual(before, after)  # rolled back: no partial append committed

    def test_confirm_promotes_status_and_greens(self):
        t = _migrated(self)
        append.confirm(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        r = _active_status(t, 'med/sources/2026-01-01__source__a.pdf')
        self.assertEqual(r['identity_status'], 'operator-confirmed')
        self.assertEqual(r['supersede_reason'], 'status-change')

    def test_confirm_refuses_when_already_confirmed(self):
        t = _migrated(self)
        append.confirm(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')
        with self.assertRaisesRegex(append.AppendStop, 'already operator-confirmed'):
            append.confirm(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')

    def test_rehash_records_new_bytes_and_greens(self):
        t = _migrated(self)
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'sources',
                               '2026-01-01__source__a.pdf'), 'wb') as fh:
            fh.write(b'AAAA-v2')
        append.rehash(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        r = _active_status(t, 'med/sources/2026-01-01__source__a.pdf')
        self.assertEqual(r['sha256'], sha(b'AAAA-v2'))
        self.assertEqual(r['supersede_reason'], 'rehash')

    def test_rehash_refuses_when_bytes_unchanged(self):
        t = _migrated(self)
        with self.assertRaisesRegex(append.AppendStop, 'bytes are unchanged'):
            append.rehash(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')

    def test_rename_requires_old_gone_and_greens(self):
        t = _migrated(self)
        srcs = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        os.rename(os.path.join(srcs, '2026-01-01__source__a.pdf'),
                  os.path.join(srcs, '2026-01-01__source__a-fixed.pdf'))
        append.rename(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf',
                      'med/sources/2026-01-01__source__a-fixed.pdf', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertIsNone(_active_status(t, 'med/sources/2026-01-01__source__a.pdf'))
        self.assertIsNotNone(_active_status(t, 'med/sources/2026-01-01__source__a-fixed.pdf'))

    def test_rename_refuses_when_old_still_on_disk(self):
        t = _migrated(self)
        t.src('alpha', '2026-01-01__source__a-fixed.pdf', b'AAAA')  # copy present, old NOT removed
        with self.assertRaisesRegex(append.AppendStop, 'old path to be gone'):
            append.rename(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf',
                          'med/sources/2026-01-01__source__a-fixed.pdf', today='2026-07-18')

    def test_wrong_owner_retracts_when_file_absent_and_greens(self):
        t = _migrated(self)
        os.remove(os.path.join(t.root, 'patients', 'alpha', 'med', 'sources',
                               '2026-01-01__source__a.pdf'))
        ok, _ = t.is_green(); self.assertFalse(ok)  # RED until retracted
        append.wrong_owner(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        # the misfiled evidence record is superseded by a wrong-owner retraction; it no longer counts
        # as evidence and its file must be gone (proven by the green tree above).
        r = _active_status(t, 'med/sources/2026-01-01__source__a.pdf')
        self.assertEqual(r['supersede_reason'], 'wrong-owner')
        _, agg = t.verify()
        self.assertEqual(agg['evidence_records'], 0)

    def test_wrong_owner_refuses_while_file_present(self):
        t = _migrated(self)
        with self.assertRaisesRegex(append.AppendStop, 'already moved off'):
            append.wrong_owner(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')

    def test_retracted_source_replaced_on_disk_is_red(self):
        # after a wrong-owner retraction, a file reappearing at the retracted path is un-inventoried.
        t = _migrated(self)
        p = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', '2026-01-01__source__a.pdf')
        os.remove(p)
        append.wrong_owner(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')
        with open(p, 'wb') as fh:
            fh.write(b'REAPPEARED')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertTrue(any('no active manifest record' in x.category for x in f))

    def test_split_is_refused(self):
        with self.assertRaisesRegex(append.AppendStop, 'v2-deferred'):
            append.split()

    def test_append_refuses_when_manifest_drifted_from_checkpoint(self):
        # a manifest byte-mismatch with its checkpoint (unfinalized/crashed) blocks a fresh append.
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w') as fh:
            json.dump({'schema_version': 1, 'manifest_sha256': '0' * 64, 'record_count': 1,
                       'tail_record_id': _records(t)[0]['record_id']}, fh, sort_keys=True)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        with self.assertRaisesRegex(append.AppendStop, 'does not match its checkpoint'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')

    def test_append_refuses_without_manifest(self):
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'A')
        with self.assertRaisesRegex(append.AppendStop, 'no MANIFEST to append to'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf', today='2026-07-18')

    def test_private_mode_residue_in_identity_source_refused(self):
        t = _migrated(self)
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a', encoding='utf-8') as fh:
            fh.write('\n- Private mode: synthetic ⟨never-API⟩\n')
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        with self.assertRaisesRegex(append.AppendStop, 'in a new record field'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf',
                              identity_source='ref 12345678901 basis', today='2026-07-18')

    def test_cli_append_stdout_has_no_identifier(self):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        t = _migrated(self)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.main(['--root', t.root, 'append', 'alpha', 'add',
                           '--relpath', 'med/sources/2026-02-02__source__b.pdf'])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertNotIn('alpha', out)
        self.assertNotIn('source__b', out)
        self.assertNotIn(PID, out)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])


class AppendHardeningTests(unittest.TestCase):
    """Bites for the 2026-07-18 Tier-S red-team findings on the append writer (D1-D6): traversal
    handle, symlinked lock, verify-before-publish crash-safety, terminal retraction, verify-raise
    fail-closed, duplicate-key checkpoint. SYNTHETIC only."""

    def test_traversal_or_nested_handle_is_refused(self):
        # D1 (HIGH): the operator handle must be a single in-jail segment — never a traversal that
        # escapes patients/<handle>. _check_handle runs before any path is built.
        t = _migrated(self)
        for bad in ('../decoy', 'alpha/../decoy', '..', '.', 'a/b', 'a\\b', '.hidden', ''):
            with self.assertRaises(append.AppendStop) as cm:
                append.add_source(t.root, bad, 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
            self.assertIn('handle', str(cm.exception))
            with self.assertRaises(append.AppendStop) as cm2:
                append.prefix_finalize(t.root, bad)
            self.assertIn('handle', str(cm2.exception))

    def test_symlinked_manifest_lock_is_refused(self):
        # D2: a symlinked MANIFEST.lock must be rejected, not followed — O_CREAT would create the
        # target file and flock a foreign inode, defeating single-writer mutual exclusion.
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        target = os.path.join(t.root, 'PLANTED')
        os.symlink(target, os.path.join(med, 'MANIFEST.lock'))
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        self.assertIn('lock', str(cm.exception))
        self.assertFalse(os.path.exists(target))  # O_CREAT did not follow the symlink
        with self.assertRaisesRegex(append.AppendStop, 'MANIFEST.lock is a symlink'):
            append.prefix_finalize(t.root, 'alpha')

    def test_rejected_append_does_zero_writes_and_does_not_wedge(self):
        # D3: verify-before-publish — a rejected append performs ZERO manifest writes (no forward write,
        # no destructive rollback, hence no rollback-crash window). The OLD apply-then-rollback did two
        # manifest-first writes; a crash between the rollback's pair wedged the ledger (checkpoint ahead
        # of manifest, which the forward-only finalizer cannot retreat).
        t = _migrated(self)
        p = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', '2026-01-01__source__a.pdf')
        with open(p, 'wb') as fh:  # drift an already-inventoried source -> projected verify is RED
            fh.write(b'TAMPERED')
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        m_before = _read_bytes(t)
        c_before = _read_bytes(t, name='MANIFEST.checkpoint')
        writes = []
        orig = append._write_manifest_and_checkpoint
        append._write_manifest_and_checkpoint = lambda *a, **k: writes.append(1)
        try:
            with self.assertRaisesRegex(append.AppendStop, 'would leave L13 red'):
                append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        finally:
            append._write_manifest_and_checkpoint = orig
        self.assertEqual(writes, [])  # zero writes on rejection (old code did forward + rollback = 2)
        self.assertEqual(_read_bytes(t), m_before)
        self.assertEqual(_read_bytes(t, name='MANIFEST.checkpoint'), c_before)
        with open(p, 'wb') as fh:  # un-drift: the ledger was never corrupted, so a valid append works
            fh.write(b'AAAA')
        append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_append_fails_closed_if_verify_raises(self):
        # D5: if the pre-publish verify raises (an unguarded FS fault mid-walk), it happens BEFORE any
        # write — the append must not persist (previously verify ran AFTER the write and an exception
        # skipped the rollback, leaving an unverified append on disk while the CLI reported STOPPED).
        t = _migrated(self)
        before = _read_bytes(t)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        orig = fsverify.verify_tree
        fsverify.verify_tree = lambda *a, **k: (_ for _ in ()).throw(OSError('synthetic mid-verify fault'))
        try:
            with self.assertRaisesRegex(OSError, 'synthetic mid-verify fault'):
                append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        finally:
            fsverify.verify_tree = orig
        self.assertEqual(_read_bytes(t), before)  # nothing written
        self.assertEqual(len(_records(t)), 1)

    def test_writer_rejects_a_duplicate_key_checkpoint(self):
        # D6: the writer parses the checkpoint with the SAME dup-key rejection the L13 verifier uses,
        # so a checkpoint the guard REDs cannot be silently accepted and laundered green.
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        good = schema.compute_checkpoint(_read_bytes(t), _records(t))
        dup = ('{"schema_version":1,"manifest_sha256":"%s","manifest_sha256":"%s",'
               '"record_count":%d,"tail_record_id":"%s"}'
               % ('0' * 64, good['manifest_sha256'], good['record_count'], good['tail_record_id']))
        with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w', encoding='utf-8') as fh:
            fh.write(dup)
        ok, _ = t.is_green(); self.assertFalse(ok)  # L13 REDs a dup-key checkpoint
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        with self.assertRaisesRegex(append.AppendStop, 'checkpoint unreadable'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        with self.assertRaisesRegex(append.AppendStop, 'checkpoint unreadable'):
            append.prefix_finalize(t.root, 'alpha')

    def test_wrong_owner_retraction_is_terminal_for_the_relpath(self):
        # D4: a wrong-owner retraction leaves the relpath with NO active on-disk record — follow-up ops
        # (confirm/rehash/rename) find nothing to act on, and a NEW correctly-owned file at the same
        # path re-adds cleanly (previously blocked as 'already active').
        t = _migrated(self)
        rel = 'med/sources/2026-01-01__source__a.pdf'
        p = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', '2026-01-01__source__a.pdf')
        os.remove(p)
        append.wrong_owner(t.root, 'alpha', rel, today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        with self.assertRaisesRegex(append.AppendStop, 'no active record'):  # cannot inherit the retraction's identity
            append.confirm(t.root, 'alpha', rel, today='2026-07-18')
        with open(p, 'wb') as fh:
            fh.write(b'DIFFERENT-DOC')
        append.add_source(t.root, 'alpha', rel, today='2026-07-18')  # clean re-add, no 'already active'
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        fresh = [r for r in _records(t) if r['source_relpath'] == rel
                 and r['supersedes'] == '' and r['sha256'] == sha(b'DIFFERENT-DOC')]
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]['identity_status'], 'legacy-folder-only')


class AppendHardeningRound2Tests(unittest.TestCase):
    """Bites for the 2026-07-18 second red-team pass (N1-N3): migration crash recovery, finalize
    symlinked-dir containment, and rename bytes-preservation. SYNTHETIC only."""

    def test_prefix_finalize_refuses_a_symlinked_patient_or_med_dir(self):
        # N2 (HIGH): _check_handle rejects a traversal STRING, but the finalize/recovery path must also
        # reject a symlinked patient/med DIRECTORY (a valid handle whose dir is a symlink out of jail).
        t = _migrated(self)
        os.symlink(os.path.join(t.root, 'patients', 'alpha'),
                   os.path.join(t.root, 'patients', 'linkpatient'))
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'linkpatient')
        self.assertIn('symlink', str(cm.exception))
        os.makedirs(os.path.join(t.root, 'patients', 'gamma'))
        with open(os.path.join(t.root, 'patients', 'gamma', 'profile.md'), 'w', encoding='utf-8') as fh:
            fh.write('# p\n## Identity\n')
        os.symlink(os.path.join(t.root, 'patients', 'alpha', 'med'),
                   os.path.join(t.root, 'patients', 'gamma', 'med'))
        with self.assertRaises(append.AppendStop) as cm2:
            append.prefix_finalize(t.root, 'gamma')
        self.assertIn('symlink', str(cm2.exception))

    def test_rename_refuses_when_moved_bytes_differ(self):
        # N3: a rename is a pure path move; the successor inherits the old identity, so the moved bytes
        # must be identical. Different bytes at the new path -> refuse (that is a rehash, not a rename).
        t = _migrated(self)  # a.pdf = b'AAAA'
        srcs = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        os.remove(os.path.join(srcs, '2026-01-01__source__a.pdf'))
        with open(os.path.join(srcs, '2026-01-01__source__a-fixed.pdf'), 'wb') as fh:
            fh.write(b'SUBSTITUTED')
        with self.assertRaises(append.AppendStop) as cm:
            append.rename(t.root, 'alpha', 'med/sources/2026-01-01__source__a.pdf',
                          'med/sources/2026-01-01__source__a-fixed.pdf', today='2026-07-18')
        self.assertIn('bytes differ', str(cm.exception))

    def test_migration_crash_missing_checkpoint_is_recovered_by_rerun(self):
        # N1: a migration crash (MANIFEST written, checkpoint not) leaves the tree RED; re-running
        # migrate recovers by RE-DERIVE (§11.1): the pristine manifest is REWRITTEN from the folder
        # (fresh record_ids — record_id stability across crash recovery is NOT promised; the
        # load-bearing person_record_id comes from profile.md and IS preserved) -> green.
        t = _migrated(self)
        old_rid = _records(t)[0]['record_id']
        os.remove(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint'))
        ok, _ = t.is_green(); self.assertFalse(ok)  # RED: manifest without checkpoint
        migrate.migrate(t.root, today='2026-07-14')  # re-run recovers (no MigrationStop)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        rebuilt = _records(t)[0]
        self.assertNotEqual(rebuilt['record_id'], old_rid)   # re-derive mints fresh record_ids
        self.assertEqual(rebuilt['person_record_id'], PID)   # person binding preserved

    def test_checkpointless_manifest_with_confirmed_record_is_surfaced_not_destroyed(self):
        # N1 + R4-1 + R5-med: re-derive fires ONLY for a pristine initial-migration manifest. One
        # carrying an operator-confirmed record is post-migration work whose checkpoint was lost —
        # surfaced (left RED), NOT silently re-derived (which would destroy the attestation).
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        rel = 'med/sources/2026-01-01__source__a.pdf'
        recs = _records(t)
        recs[0]['identity_status'] = 'operator-confirmed'
        recs[0]['identity_reviewer'] = 'operator'
        with open(os.path.join(med, 'MANIFEST'), 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(recs[0], sort_keys=True, ensure_ascii=False) + '\n')
        os.remove(os.path.join(med, 'MANIFEST.checkpoint'))
        migrate.migrate(t.root, today='2026-07-19')
        ok, _ = t.is_green(); self.assertFalse(ok)  # surfaced: checkpoint absent, tree stays RED
        self.assertFalse(os.path.exists(os.path.join(med, 'MANIFEST.checkpoint')))
        self.assertEqual(_active_status(t, rel)['identity_status'], 'operator-confirmed')  # preserved


class AppendHardeningRound3Tests(unittest.TestCase):
    """Bites for the 2026-07-18/19 third red-team pass (R3-1..R3-4): NFD patient-dir override key,
    intermediate-symlink hashing, rehash identity transfer, finalize suffix verify. SYNTHETIC only."""

    def test_nfd_patient_dir_gate_still_catches_red(self):
        # R3-1 (HIGH): on a normalization-preserving FS the patient dir is stored NFD while the operator
        # handle is forced NFC. The verify-before-publish gate must still see this patient's findings
        # (override applied + findings matched NFC-insensitively) and refuse an append onto a RED tree.
        import unicodedata
        nfd = unicodedata.normalize('NFD', 'zażółć')
        nfc = unicodedata.normalize('NFC', 'zażółć')
        if nfd == nfc:
            self.skipTest('platform has no NFD/NFC distinction for this name')
        t = Tree(self)
        t.patient(nfd, person_id=PID).src(nfd, '2026-01-01__source__a.pdf', b'AAAA')
        migrate.migrate(t.root, today='2026-07-14')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        srcs = os.path.join(t.root, 'patients', nfd, 'med', 'sources')
        with open(os.path.join(srcs, '2026-01-01__source__a.pdf'), 'wb') as fh:
            fh.write(b'TAMPERED')  # drift the inventoried source -> tree is genuinely L13-RED
        with open(os.path.join(srcs, '2026-02-02__source__b.pdf'), 'wb') as fh:
            fh.write(b'BBBB')
        before = _read_bytes(t, handle=nfd)
        # operator must pass NFC; gate must still catch it
        with self.assertRaisesRegex(append.AppendStop, 'would leave L13 red'):
            append.add_source(t.root, nfc, 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        self.assertEqual(_read_bytes(t, handle=nfd), before)  # nothing written onto the RED tree

    def test_intermediate_symlinked_dir_under_sources_is_refused(self):
        # R3-2: a symlinked INTERMEDIATE directory under med/sources must be rejected before hashing —
        # else the writer hashes a file OUTSIDE the jail.
        t = _migrated(self)
        srcs = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        outside = os.path.join(t.root, 'OUTSIDE')
        os.makedirs(outside)
        with open(os.path.join(outside, 'x.pdf'), 'wb') as fh:
            fh.write(b'OUTSIDE-BYTES')
        os.symlink(outside, os.path.join(srcs, 'labs'))  # med/sources/labs -> OUTSIDE
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', 'med/sources/labs/x.pdf', today='2026-07-18')
        self.assertIn('component is a symlink', str(cm.exception))

    def test_rehash_of_confirmed_record_drops_to_legacy(self):
        # R3-3: a rehash records CHANGED bytes; an operator-confirmed attestation must NOT ride onto the
        # new content (the changed-bytes twin of the rename guard) — it drops to legacy-folder-only.
        t = _migrated(self)
        rel = 'med/sources/2026-01-01__source__a.pdf'
        append.confirm(t.root, 'alpha', rel, today='2026-07-18')
        self.assertEqual(_active_status(t, rel)['identity_status'], 'operator-confirmed')
        p = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources', '2026-01-01__source__a.pdf')
        with open(p, 'wb') as fh:
            fh.write(b'SUBSTITUTED-DOC')
        append.rehash(t.root, 'alpha', rel, today='2026-07-18')
        r = _active_status(t, rel)
        self.assertEqual(r['sha256'], sha(b'SUBSTITUTED-DOC'))
        self.assertEqual(r['identity_status'], 'legacy-folder-only')  # attestation dropped, not carried
        self.assertEqual(r['identity_reviewer'], 'intake-pipeline')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_finalize_refuses_a_hand_appended_unverified_suffix(self):
        # R3-4: finalize re-blesses only an ALREADY-verified append. A hand-appended suffix whose source
        # is not on disk (binding-RED) must be refused, not blessed.
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        mbytes = _read_bytes(t)
        recs = schema.parse_manifest_bytes(mbytes)
        ghost = dict(recs[0], record_id='bbbbbbbb',
                     source_relpath='med/sources/2026-09-09__source__ghost.pdf',
                     supersedes='', supersede_reason='', supersede_date='')
        new = mbytes + (json.dumps(ghost, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')
        with open(os.path.join(med, 'MANIFEST'), 'wb') as fh:
            fh.write(new)  # stale 1-record checkpoint left in place -> looks like a crashed append
        with self.assertRaisesRegex(append.AppendStop, 'not L13-green'):
            append.prefix_finalize(t.root, 'alpha')
        ok, _ = t.is_green(); self.assertFalse(ok)  # never blessed


class AppendHardeningRound4Tests(unittest.TestCase):
    """Bites for the 2026-07-19 fourth red-team pass (R4-1 migrate re-derive not launder; R4-3 symlinked
    profile.md). SYNTHETIC only."""

    def test_migration_rederive_discards_an_inplace_metadata_edit(self):
        # R4-1: a checkpointless manifest is re-derived from the folder — a hand-edit to an L13-unchecked
        # field (acquired_date) is DISCARDED (re-derived from the filename), never laundered GREEN as-is.
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        rel = 'med/sources/2026-01-01__source__a.pdf'
        recs = _records(t)
        recs[0]['acquired_date'] = '2025-12-31'  # tamper a field L13 does not check; bytes unchanged
        with open(os.path.join(med, 'MANIFEST'), 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(recs[0], sort_keys=True, ensure_ascii=False) + '\n')
        os.remove(os.path.join(med, 'MANIFEST.checkpoint'))
        migrate.migrate(t.root, today='2026-07-19')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertEqual(_active_status(t, rel)['acquired_date'], '2026-01-01')  # re-derived, not the edit

    def test_symlinked_profile_is_refused_before_the_read(self):
        # R4-3: _locked_apply must refuse a symlinked profile.md BEFORE reading person-id / private-mode
        # through it — an early gate, not the late projected verify (which would also catch it).
        t = _migrated(self)
        prof = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        real = os.path.join(t.root, 'REALPROFILE.md')
        os.rename(prof, real)
        os.symlink(real, prof)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')
        msg = str(cm.exception)
        self.assertIn('profile.md is a symlink', msg)
        self.assertNotIn('would leave L13 red', msg)  # refused at the early gate, before any read


class AppendHardeningRound5Tests(unittest.TestCase):
    """Bites for the 2026-07-19 fifth red-team pass (R5-HIGH dir-fsync ordering barrier; R5-med
    surface-don't-destroy a checkpoint-lost attested ledger). SYNTHETIC only."""

    def test_legit_confirmed_then_checkpoint_lost_is_surfaced(self):
        # R5-med: a LEGITIMATELY confirmed record whose (untracked) checkpoint is later lost
        # (backup/restore asymmetry) must be SURFACED on re-migrate, not silently re-derived away.
        t = _migrated(self)
        rel = 'med/sources/2026-01-01__source__a.pdf'
        append.confirm(t.root, 'alpha', rel, today='2026-07-18')
        self.assertEqual(_active_status(t, rel)['identity_status'], 'operator-confirmed')
        os.remove(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint'))
        migrate.migrate(t.root, today='2026-07-19')
        ok, _ = t.is_green(); self.assertFalse(ok)  # surfaced RED, not re-derived
        self.assertEqual(_active_status(t, rel)['identity_status'], 'operator-confirmed')  # preserved

    def test_write_manifest_orders_dir_fsync_between_the_two_renames(self):
        # R5-HIGH: the two-file commit fsyncs the directory BETWEEN the manifest and checkpoint renames,
        # so a crash cannot persist the checkpoint ahead of the manifest (the unrecoverable wedge) on a
        # filesystem that does not order metadata implicitly (macOS/APFS).
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        mbytes = _read_bytes(t)
        recs = schema.parse_manifest_bytes(mbytes)
        seq = []
        orig_aw, orig_fs = append._atomic_write, append._fsync_dir
        append._atomic_write = lambda p, d: seq.append('write:' + os.path.basename(p))
        append._fsync_dir = lambda p: seq.append('fsyncdir')
        try:
            append._write_manifest_and_checkpoint(med, mbytes, recs)
        finally:
            append._atomic_write, append._fsync_dir = orig_aw, orig_fs
        self.assertEqual(seq, ['write:MANIFEST', 'fsyncdir', 'write:MANIFEST.checkpoint', 'fsyncdir'])


class AppendHardeningRound6Tests(unittest.TestCase):
    """Bites for the 2026-07-19 sixth red-team pass (R6-1 re-derive must not launder a missing/drifted
    source; R6-3 finalize must re-check op semantics on the un-checkpointed suffix; R6-4 non-regular
    profile.md is refused fast). SYNTHETIC only."""

    def _src_path(self, t, name, handle='alpha'):
        return os.path.join(t.root, 'patients', handle, 'med', 'sources', name)

    def _cp_path(self, t, handle='alpha'):
        return os.path.join(t.root, 'patients', handle, 'med', 'MANIFEST.checkpoint')

    def test_rederive_refuses_a_recorded_source_missing_on_disk(self):
        # R6-1: checkpointless pristine manifest whose recorded source vanished on disk. Re-derive would
        # silently DROP the record (RED→GREEN, zero trace); instead SURFACE it, record preserved.
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        migrate.migrate(t.root, today='2026-07-14')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        os.remove(self._src_path(t, '2026-02-02__source__b.pdf'))
        os.remove(self._cp_path(t))
        migrate.migrate(t.root, today='2026-07-19')
        ok, _ = t.is_green(); self.assertFalse(ok)          # surfaced, not re-derived
        self.assertEqual(len(_records(t)), 2)               # b's record preserved (not silently dropped)

    def test_rederive_refuses_byte_drift(self):
        # R6-1: checkpointless pristine manifest whose source bytes drifted. Re-derive would re-bless the
        # NEW hash (drift RED→GREEN); instead SURFACE it, recorded hash preserved.
        t = _migrated(self)
        with open(self._src_path(t, '2026-01-01__source__a.pdf'), 'wb') as fh:
            fh.write(b'DRIFTED-DIFFERENT-BYTES')
        os.remove(self._cp_path(t))
        migrate.migrate(t.root, today='2026-07-19')
        ok, _ = t.is_green(); self.assertFalse(ok)          # surfaced, not re-derived
        self.assertEqual(_records(t)[0]['sha256'], sha(b'AAAA'))  # recorded hash NOT re-blessed to drift

    def test_finalize_refuses_forged_confirm_onto_substituted_bytes(self):
        # R6-3: a hand-appended status-change (confirm) suffix that attests SUBSTITUTED bytes passes the
        # prefix hash, schema graph, and structural L13 (record sha == disk sha) — but the writer would
        # never produce it. The suffix-semantic gate must refuse it (no laundering via finalize).
        t = _migrated(self)
        med = os.path.join(t.root, 'patients', 'alpha', 'med')
        with open(self._src_path(t, '2026-01-01__source__a.pdf'), 'wb') as fh:
            fh.write(b'SUBSTITUTED')
        base = _records(t)[0]
        forged = dict(base, record_id='ffffffffffffffff', identity_status='operator-confirmed',
                      identity_reviewer='operator', identity_source='forged', sha256=sha(b'SUBSTITUTED'),
                      review_date='2026-07-19', supersedes=base['record_id'],
                      supersede_reason='status-change', supersede_date='2026-07-19')
        with open(os.path.join(med, 'MANIFEST'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(forged, sort_keys=True, ensure_ascii=False) + '\n')
        # checkpoint still count=1 -> the suffix is un-checkpointed (the finalize/crash-recovery shape)
        with self.assertRaisesRegex(append.AppendStop, 'violates writer op semantics'):
            append.prefix_finalize(t.root, 'alpha')
        self.assertEqual(_active_status(t, 'med/sources/2026-01-01__source__a.pdf')['identity_status'],
                         'operator-confirmed')  # forged row still on disk, but never blessed
        ok, _ = t.is_green(); self.assertFalse(ok)          # tree stays RED

    def test_append_refuses_a_non_regular_profile(self):
        # R6-4: a non-regular profile.md (FIFO/device — a botched restore) must be refused BEFORE the
        # exclusive lock + blocking read, not hang the writer. A directory is a safe deterministic proxy
        # for the `not isfile` guard (a FIFO would hang an unfixed writer; a dir raises cleanly).
        t = _migrated(self)
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        os.remove(profile); os.mkdir(profile)
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        with self.assertRaisesRegex(append.AppendStop, 'profile.md is not a regular file'):
            append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today='2026-07-18')


class MergeReconcileBites(unittest.TestCase):
    """Bites for the 2026-07-19 Codex-sweep merge red-team (ADR-0037 §11.2): the three confirmed
    mediums (re-derive unlink ordering; pristine-gate schema validation; verify_tree FIFO-profile
    re-read) and the untested grafted guards. SYNTHETIC only."""

    def _med(self, t, handle='alpha'):
        return os.path.join(t.root, 'patients', handle, 'med')

    def test_rederive_aborts_before_unlink_on_profile_id_anomaly(self):
        # M1: checkpoint lost + profile id line later DUPLICATED. The re-derive gate passes (manifest
        # pristine, inventory matches) but the person-id step raises — the old ledger must STILL be
        # on disk (all fallible steps precede the unlink).
        t = _migrated(self)
        manifest = os.path.join(self._med(t), 'MANIFEST')
        os.remove(os.path.join(self._med(t), 'MANIFEST.checkpoint'))
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        with open(profile, 'a', encoding='utf-8') as fh:
            fh.write('- **Person record ID (local-only):** `%s`\n' % PID2)  # duplicate id line
        with self.assertRaisesRegex(migrate.MigrationStop, 'ambiguous or misplaced'):
            migrate.migrate(t.root, today='2026-07-19')
        self.assertTrue(os.path.isfile(manifest))  # ledger NOT destroyed by the failed re-derive

    def test_pristine_gate_surfaces_malformed_derivatives_without_traceback(self):
        # M2: a pristine-SHAPED row with `"derivatives": null` must be a surfaced skip (not pristine),
        # never a raw TypeError out of _recorded_inventory.
        t = _migrated(self)
        med = self._med(t)
        recs = _records(t)
        recs[0]['derivatives'] = None
        with open(os.path.join(med, 'MANIFEST'), 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(recs[0], sort_keys=True, ensure_ascii=False) + '\n')
        os.remove(os.path.join(med, 'MANIFEST.checkpoint'))
        agg = migrate.migrate(t.root, today='2026-07-19')  # must not raise TypeError
        self.assertEqual(agg['migrated'], 0)               # surfaced, not re-derived
        self.assertTrue(os.path.isfile(os.path.join(med, 'MANIFEST')))  # preserved for diagnosis

    def test_verify_tree_completes_red_on_fifo_profile(self):
        # M3: a FIFO profile.md must not hang the whole-tree verifier (the cross-patient person-id
        # re-read is regular-file-gated; _verify_patient REDs the node without opening it).
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO creation is unavailable on this platform')
        t = _migrated(self)
        profile = os.path.join(t.root, 'patients', 'alpha', 'profile.md')
        os.remove(profile); os.mkfifo(profile)
        findings, _ = fsverify.verify_tree(t.root)  # must return, not block
        self.assertTrue(any('not a regular file' in f.category for f in findings))

    def test_migrate_surfaces_wrong_type_manifest_and_checkpoint(self):
        # Grafted guards: a symlinked MANIFEST, and a non-regular checkpoint beside a regular
        # MANIFEST, are surfaced per patient (migrated=0) with the node left untouched.
        t = _migrated(self)
        med = self._med(t)
        manifest = os.path.join(med, 'MANIFEST')
        real = manifest + '.real'
        os.rename(manifest, real); os.symlink(real, manifest)
        agg = migrate.migrate(t.root, today='2026-07-19')
        self.assertEqual(agg['migrated'], 0)
        self.assertTrue(os.path.islink(manifest))  # untouched
        os.remove(manifest); os.rename(real, manifest)
        cp = os.path.join(med, 'MANIFEST.checkpoint')
        os.remove(cp); os.mkdir(cp)                # non-regular checkpoint
        agg = migrate.migrate(t.root, today='2026-07-19')
        self.assertEqual(agg['migrated'], 0)
        self.assertTrue(os.path.isdir(cp))         # untouched

    def test_write_manifest_refuses_orphan_checkpoint_and_dangling_symlink(self):
        # Broadened overwrite guard, exercised DIRECTLY: (a) orphan checkpoint only; (b) dangling
        # symlinked MANIFEST (exists=False, lexists=True — the case the old `exists` guard clobbered).
        t = Tree(self); t.patient('alpha').src('alpha', '2026-01-01__source__a.pdf', b'A')
        med = self._med(t)
        os.makedirs(med, exist_ok=True)
        with open(os.path.join(med, 'MANIFEST.checkpoint'), 'w') as fh:
            fh.write('orphan')
        with self.assertRaisesRegex(migrate.MigrationStop, 'already exists'):
            migrate.write_manifest(t.root, 'alpha', [rec()])
        os.remove(os.path.join(med, 'MANIFEST.checkpoint'))
        os.symlink(os.path.join(med, 'no-such-target'), os.path.join(med, 'MANIFEST'))
        with self.assertRaisesRegex(migrate.MigrationStop, 'already exists'):
            migrate.write_manifest(t.root, 'alpha', [rec()])
        self.assertTrue(os.path.islink(os.path.join(med, 'MANIFEST')))  # not clobbered


def _snapshot(t, handle):
    """Every directory and file under patients/<handle>/ (hidden ones included) -> its bytes (a symlink
    -> its target): equality proves the folder byte-identical AND that it gained no new entry."""
    base = os.path.join(t.root, 'patients', handle)
    out = {}
    for dp, dns, fns in os.walk(base):
        for n in dns:
            out[os.path.relpath(os.path.join(dp, n), base) + '/'] = None
        for n in fns:
            full = os.path.join(dp, n)
            if os.path.islink(full):
                out[os.path.relpath(full, base)] = ('symlink', os.readlink(full))
                continue
            with open(full, 'rb') as fh:
                out[os.path.relpath(full, base)] = fh.read()
    return out


class InitLedgerTests(unittest.TestCase):
    """`init <handle>` (ADR-0037 §12): one person's first ledger and nobody else's. Codex's matrix —
    the target's ledger absent / existing-empty / existing-populated — each with a SECOND unfinished
    person present (no ID, no ledger) whose folder must stay byte-identical and gain no entry."""
    DAY = '2026-09-29'

    def _tree(self, alpha_id=None, beta_source=True):
        t = Tree(self)
        t.patient('alpha', person_id=alpha_id)
        t.patient('beta', person_id=None)
        if beta_source:
            t.src('beta', '2026-02-02__source__b.pdf', b'BBBB')
        return t

    def _alpha_findings(self, t):
        findings, _ = t.verify()
        return [f.render() for f in findings if f.handle in ('alpha', None)]

    def _path(self, t, *parts):
        return os.path.join(t.root, 'patients', 'alpha', *parts)

    # --- absent -----------------------------------------------------------------------------------
    def test_absent_scaffold_mints_id_and_empty_ledger_for_the_target_only(self):
        t = self._tree(beta_source=False)   # handover 42's repro: two scaffolds, no sources
        beta = _snapshot(t, 'beta')
        append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertRegex(fsverify.read_person_id(self._path(t, 'profile.md')) or '', r'^[0-9a-f]{32}$')
        self.assertEqual(_read_bytes(t), b'')
        self.assertTrue(os.path.isfile(self._path(t, 'med', 'MANIFEST.checkpoint')))
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertEqual(_snapshot(t, 'beta'), beta)
        # negative control: the whole-tree command DOES write into beta, so the check above has teeth
        migrate.migrate(t.root, today=self.DAY)
        self.assertNotEqual(_snapshot(t, 'beta'), beta)

    def test_absent_with_sources_registers_them_exactly_as_migrate(self):
        def plant(t):
            t.src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
            t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR-A')
            t.src('alpha', 'interviews/2026-01-02__interview__first.md', b'first')
        t = self._tree(alpha_id=PID); plant(t)
        beta = _snapshot(t, 'beta')
        profile = _snapshot(t, 'alpha')['profile.md']
        append.init_ledger(t.root, 'alpha', today=self.DAY)
        twin = Tree(self); twin.patient('alpha'); plant(twin)
        migrate.migrate(twin.root, today=self.DAY)
        strip = lambda rs: [{k: v for k, v in r.items() if k != 'record_id'} for r in rs]
        self.assertEqual(strip(_records(t)), strip(_records(twin)))
        self.assertEqual(_snapshot(t, 'alpha')['profile.md'], profile)  # existing ID kept byte for byte
        self.assertEqual(self._alpha_findings(t), [])
        self.assertEqual(_snapshot(t, 'beta'), beta)  # beta's own RED (no ledger) is not init's business

    def test_interview_as_first_source_then_a_later_one(self):
        # The interview filing path: the ledger does not exist yet -> init; then it does -> append add.
        t = self._tree()
        beta = _snapshot(t, 'beta')
        first = 'med/sources/interviews/2026-01-02__interview__first.md'
        t.src('alpha', 'interviews/2026-01-02__interview__first.md', b'first')
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', first, today=self.DAY)
        self.assertIn('`init <handle>`', str(cm.exception))   # never the whole-tree `migrate`
        self.assertNotIn('migrate', str(cm.exception))
        append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual([r['source_relpath'] for r in _records(t)], [first])
        t.src('alpha', 'interviews/2026-01-03__interview__second.md', b'second')
        append.add_source(t.root, 'alpha', 'med/sources/interviews/2026-01-03__interview__second.md',
                          today=self.DAY)
        self.assertEqual(self._alpha_findings(t), [])
        self.assertEqual(_snapshot(t, 'beta'), beta)

    # --- existing (empty / populated): refused, byte-identical, no new entry anywhere ---------------
    def _assert_refused_untouched(self, t, expect):
        alpha, beta = _snapshot(t, 'alpha'), _snapshot(t, 'beta')
        with self.assertRaises(append.AppendStop) as cm:
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertIn(expect, str(cm.exception))
        self.assertNotIn('migrate', str(cm.exception))   # no recovery sends anyone to the whole tree
        self.assertEqual(_snapshot(t, 'alpha'), alpha)   # no lock file either: refused before the lock
        self.assertEqual(_snapshot(t, 'beta'), beta)

    def test_existing_empty_ledger_is_refused_then_append_registers_the_first_source(self):
        t = self._tree(alpha_id=PID)
        t.manifest('alpha', [])                        # an empty ledger left by onboarding
        t.src('alpha', 'interviews/2026-01-02__interview__first.md', b'first')
        self._assert_refused_untouched(t, 'append <handle> add')
        beta = _snapshot(t, 'beta')
        append.add_source(t.root, 'alpha', 'med/sources/interviews/2026-01-02__interview__first.md',
                          today=self.DAY)
        self.assertEqual(self._alpha_findings(t), [])
        self.assertEqual(_snapshot(t, 'beta'), beta)

    def test_existing_populated_ledger_is_refused(self):
        t = _migrated(self)
        t.patient('beta', person_id=None).src('beta', '2026-02-02__source__b.pdf', b'BBBB')
        t.src('alpha', '2026-02-02__source__late.pdf', b'LATE')   # an unregistered later source
        self._assert_refused_untouched(t, 'append <handle> add')

    def test_checkpointless_manifest_and_orphan_checkpoint_are_refused(self):
        t = self._tree(alpha_id=PID)
        t.manifest('alpha', [], checkpoint=None)       # an interrupted first write
        self._assert_refused_untouched(t, 'remove that MANIFEST and re-run `init <handle>`')
        os.remove(self._path(t, 'med', 'MANIFEST'))
        with open(self._path(t, 'med', 'MANIFEST.checkpoint'), 'w') as fh:
            fh.write('orphan')
        self._assert_refused_untouched(t, 'prior ownership state')

    # --- a MANIFEST with no checkpoint: the tool decides which recovery is safe --------------------
    A = 'med/sources/2026-01-01__source__a.pdf'
    REMOVE = 'remove that MANIFEST and re-run `init <handle>`'
    RESTORE = 'never delete this ledger'

    def _checkpointless_refusals(self, t):
        # The same checkpointless ledger as `init` and as `append` see it; neither writes anything.
        before = _snapshot(t, 'alpha')
        msgs = []
        for op in (lambda: append.init_ledger(t.root, 'alpha', today=self.DAY),
                   lambda: append.add_source(t.root, 'alpha', self.A, today=self.DAY)):
            with self.assertRaises(append.AppendStop) as cm:
                op()
            msgs.append(str(cm.exception))
        self.assertEqual(_snapshot(t, 'alpha'), before)
        return msgs

    def _initialised(self):
        t = self._tree(alpha_id=PID)
        t.src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
        t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR-A')
        append.init_ledger(t.root, 'alpha', today=self.DAY)
        return t

    def _lose_checkpoint(self, t):
        os.remove(self._path(t, 'med', 'MANIFEST.checkpoint'))

    def test_interrupted_first_write_with_legacy_rows_is_offered_the_rerun(self):
        t = self._initialised()
        self._lose_checkpoint(t)                       # the crash between init's two writes
        for msg in self._checkpointless_refusals(t):
            self.assertIn(self.REMOVE, msg)
        os.remove(self._path(t, 'med', 'MANIFEST'))    # ...and following that advice is sound
        append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual(self._alpha_findings(t), [])

    def test_ledger_carrying_a_confirmation_is_only_told_to_restore(self):
        # Round-2 review scenario: deleting this ledger would erase the operator's attestation and its
        # correction row, and a re-run would report done with L13 green. Also with operator-typed
        # provenance that happens to read like migration's: the row's status and supersession decide.
        for provenance in (None, 'legacy migration — operator re-checked the folder'):
            t = self._initialised()
            append.confirm(t.root, 'alpha', self.A, identity_source=provenance, today=self.DAY)
            self._lose_checkpoint(t)
            for msg in self._checkpointless_refusals(t):
                self.assertIn(self.RESTORE, msg)
                self.assertNotIn('remove', msg)

    def test_ledger_carrying_a_later_append_is_only_told_to_restore(self):
        t = self._initialised()
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        append.add_source(t.root, 'alpha', 'med/sources/2026-02-02__source__b.pdf', today=self.DAY)
        self._lose_checkpoint(t)                       # legacy rows, no supersession — but not init's
        for msg in self._checkpointless_refusals(t):
            self.assertIn(self.RESTORE, msg)
            self.assertNotIn('remove', msg)

    def test_hand_marked_or_malformed_row_is_only_told_to_restore(self):
        # Bytes still match the folder and the provenance reads like migration's, but the row claims
        # an operator attestation (or is not a valid record at all): the row's shape decides, and a
        # malformed row must give the restore text, never a traceback.
        for edit in ({'identity_status': 'operator-confirmed', 'identity_reviewer': 'operator'},
                     {'identity_source': None}):
            t = self._initialised()
            self._lose_checkpoint(t)
            rows = _records(t)
            rows[0].update(edit)
            with open(self._path(t, 'med', 'MANIFEST'), 'w', encoding='utf-8') as fh:
                fh.write(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))
            for msg in self._checkpointless_refusals(t):
                self.assertIn(self.RESTORE, msg)
                self.assertNotIn('remove', msg)

    def test_drifted_or_unreadable_checkpointless_ledger_is_only_told_to_restore(self):
        t = self._initialised()
        self._lose_checkpoint(t)
        t.src('alpha', '2026-01-01__source__a.pdf', b'DRIFTED')   # a re-run would adopt these bytes
        for msg in self._checkpointless_refusals(t):
            self.assertIn(self.RESTORE, msg)
            self.assertNotIn('remove', msg)
        t2 = self._tree(alpha_id=PID)
        t2.raw_manifest('alpha', '{"torn": ', checkpoint=None)    # unparseable: keep it, never delete
        with self.assertRaises(append.AppendStop) as cm:
            append.init_ledger(t2.root, 'alpha', today=self.DAY)
        self.assertIn(self.RESTORE, str(cm.exception))

    # --- refusals that must write no ledger -------------------------------------------------------
    def test_projected_red_is_refused_with_no_ledger_written(self):
        # alpha's scaffold was copied with beta's ID: a global L13 finding the projected verify sees.
        t = Tree(self)
        t.patient('alpha', person_id=PID2)
        t.patient('beta', person_id=PID2).src('beta', '2026-02-02__source__b.pdf', b'BBBB')
        beta = _snapshot(t, 'beta')
        profile = _snapshot(t, 'alpha')['profile.md']
        with self.assertRaises(append.AppendStop) as cm:
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertIn('L13 red', str(cm.exception))
        self.assertFalse(os.path.lexists(self._path(t, 'med', 'MANIFEST')))
        self.assertFalse(os.path.lexists(self._path(t, 'med', 'MANIFEST.checkpoint')))
        self.assertEqual(_snapshot(t, 'alpha')['profile.md'], profile)
        self.assertEqual(_snapshot(t, 'beta'), beta)

    def test_builder_and_residue_stops_come_before_the_mint(self):
        t = self._tree()
        profile = _snapshot(t, 'alpha')['profile.md']
        t.src('alpha', '2026-01-09__source__orphan.ocr.md', b'ORPHAN')   # no primary to bind to
        with self.assertRaisesRegex(append.AppendStop, 'ambiguous or orphan'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual(_snapshot(t, 'alpha')['profile.md'], profile)   # no ID minted
        os.remove(self._path(t, 'med', 'sources', '2026-01-09__source__orphan.ocr.md'))
        with open(self._path(t, 'profile.md'), 'a', encoding='utf-8') as fh:
            fh.write('- Private mode: synthetic ⟨never-API⟩\n')
        profile = _snapshot(t, 'alpha')['profile.md']
        t.src('alpha', '2026-01-01__source__synthetic-01020312340.pdf', b'A')
        with self.assertRaisesRegex(append.AppendStop, 'in a new record field'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual(_snapshot(t, 'alpha')['profile.md'], profile)   # no ID minted
        self.assertFalse(os.path.lexists(self._path(t, 'med', 'MANIFEST')))

    def test_handle_must_be_one_safe_segment(self):
        t = self._tree()
        beta = _snapshot(t, 'beta')
        for bad, why in (('../patients/beta', 'path separator'), ('alpha/../beta', 'path separator'),
                         ('alpha/med', 'path separator'), ('.alpha', 'hidden name'), ('', 'empty handle'),
                         ('alpha\u0301', 'not NFC')):
            with self.assertRaisesRegex(append.AppendStop, why):
                append.init_ledger(t.root, bad, today=self.DAY)
        with self.assertRaisesRegex(append.AppendStop, 'does not name exactly one'):
            append.init_ledger(t.root, 'nobody', today=self.DAY)
        self.assertEqual(_snapshot(t, 'beta'), beta)

    # --- path guards: a link or a wrong spelling must never reach another person's folder ----------
    def test_symlinked_patient_dir_to_another_person_is_refused_without_writing_there(self):
        t = self._tree()
        beta = _snapshot(t, 'beta')
        import shutil
        shutil.rmtree(self._path(t))
        os.symlink(os.path.join(t.root, 'patients', 'beta'), self._path(t))
        with self.assertRaisesRegex(append.AppendStop, 'no such patient directory'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual(_snapshot(t, 'beta'), beta)   # no lock file, ID or ledger in beta

    def test_symlinked_med_dir_to_another_persons_med_is_refused_without_writing_there(self):
        t = self._tree()
        beta = _snapshot(t, 'beta')
        import shutil
        shutil.rmtree(self._path(t, 'med'))
        os.symlink(os.path.join(t.root, 'patients', 'beta', 'med'), self._path(t, 'med'))
        with self.assertRaisesRegex(append.AppendStop, 'no med/ directory'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual(_snapshot(t, 'beta'), beta)

    def test_symlinked_or_missing_profile_is_refused_before_the_lock(self):
        t = self._tree()
        beta = _snapshot(t, 'beta')
        os.remove(self._path(t, 'profile.md'))
        os.symlink(os.path.join(t.root, 'patients', 'beta', 'profile.md'), self._path(t, 'profile.md'))
        with self.assertRaisesRegex(append.AppendStop, 'profile.md is missing'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertFalse(os.path.lexists(self._path(t, 'med', 'MANIFEST.lock')))
        os.remove(self._path(t, 'profile.md'))          # and a missing profile, the same way
        with self.assertRaisesRegex(append.AppendStop, 'profile.md is missing'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertFalse(os.path.lexists(self._path(t, 'med', 'MANIFEST.lock')))
        self.assertEqual(_snapshot(t, 'beta'), beta)

    def test_dangling_symlink_manifest_is_refused_before_the_lock(self):
        t = self._tree(alpha_id=PID)
        os.symlink(os.path.join(t.root, 'no-such-target'), self._path(t, 'med', 'MANIFEST'))
        self._assert_refused_untouched(t, 'symlink')
        self.assertTrue(os.path.islink(self._path(t, 'med', 'MANIFEST')))   # not clobbered

    def test_ledger_written_between_the_check_and_the_lock_is_not_overwritten(self):
        # A concurrent writer wins the race after the pre-lock check: the re-check under the lock
        # must refuse rather than replace that ledger.
        from unittest import mock
        t = self._tree(alpha_id=PID)
        t.src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
        real_open_lock = append._open_lock
        won = {}
        def racing_open_lock(med):
            t.manifest('alpha', [rec(relpath='med/sources/2026-01-01__source__a.pdf', data=b'AAAA')])
            won['m'] = _read_bytes(t)
            won['c'] = _read_bytes(t, name='MANIFEST.checkpoint')
            return real_open_lock(med)
        with mock.patch.object(append, '_open_lock', side_effect=racing_open_lock):
            with self.assertRaises(append.AppendStop) as cm:
                append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertIn('already has a ledger', str(cm.exception))
        self.assertEqual(_read_bytes(t), won['m'])
        self.assertEqual(_read_bytes(t, name='MANIFEST.checkpoint'), won['c'])

    def test_handle_must_name_an_on_disk_entry_exactly(self):
        # Case counts even where the filesystem ignores it: `ALPHA` must not open `alpha/` while the
        # verifier (and the projected check's key) walk the on-disk spelling. Holds for append too.
        t = _migrated(self)
        with self.assertRaisesRegex(append.AppendStop, 'does not name exactly one'):
            append._check_handle(t.root, 'ALPHA')      # everywhere, whatever the filesystem
        self.assertEqual(append._check_handle(t.root, 'alpha'), 'alpha')
        t.src('alpha', '2026-02-02__source__b.pdf', b'BBBB')
        before = _snapshot(t, 'alpha')
        for op in (lambda: append.init_ledger(t.root, 'ALPHA', today=self.DAY),
                   lambda: append.add_source(t.root, 'ALPHA', 'med/sources/2026-02-02__source__b.pdf',
                                             today=self.DAY)):
            with self.assertRaisesRegex(append.AppendStop, 'does not name exactly one'):
                op()
        self.assertEqual(_snapshot(t, 'alpha'), before)   # nothing written, no lock file
        import unicodedata
        nfd = unicodedata.normalize('NFD', 'zażółć')
        t.patient(nfd)
        self.assertEqual(append._check_handle(t.root, unicodedata.normalize('NFC', nfd)),
                         [n for n in os.listdir(os.path.join(t.root, 'patients'))
                          if unicodedata.normalize('NFC', n) == unicodedata.normalize('NFC', nfd)][0])

    def test_symlinked_patients_root_is_refused_before_touching_the_other_tree(self):
        t = self._tree()
        other = Tree(self); other.patient('alpha', person_id=None)
        other_before = _snapshot(other, 'alpha')
        import shutil
        shutil.rmtree(os.path.join(t.root, 'patients'))
        os.symlink(os.path.join(other.root, 'patients'), os.path.join(t.root, 'patients'))
        with self.assertRaisesRegex(append.AppendStop, 'patients root is symlinked'):
            append.init_ledger(t.root, 'alpha', today=self.DAY)
        self.assertEqual(_snapshot(other, 'alpha'), other_before)   # no lock file, no minted ID

    def test_cli_prints_no_identifier_and_a_second_run_points_to_append(self):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        t = self._tree(alpha_id=PID)
        t.src('alpha', '2026-01-01__source__a.pdf', b'AAAA')
        for want_code, want_text in ((0, 'init: done'), (3, 'append <handle> add')):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = M.main(['--root', t.root, 'init', 'alpha'])
            out = buf.getvalue()
            self.assertEqual(code, want_code, out)
            self.assertIn(want_text, out)
            for secret in ('alpha', 'source__a', PID):
                self.assertNotIn(secret, out)
        self.assertEqual(self._alpha_findings(t), [])


class RetranscribeTests(unittest.TestCase):
    """`append <handle> retranscribe` (ADR-0037 §13): a corrected `.ocr.md` re-binds to its unchanged
    original only when the file carries a dated erratum line for the correction. SYNTHETIC only."""
    REL = 'med/sources/2026-01-01__source__a.pdf'
    OCR = 'med/sources/2026-01-01__source__a.ocr.md'
    LAYER = b'# a\n\nValue X: 3.4 unit\n'
    FIXED = b'# a\n\nValue X: 4.3 unit\n'
    ERRATUM = b'\n## Errata\n- 2026-07-20, page 2: Value X 3.4 unit -> 4.3 unit\n'

    def _tree(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'ORIGINAL-SCAN')
        t.src('alpha', '2026-01-01__source__a.ocr.md', self.LAYER)
        migrate.migrate(t.root, today='2026-07-14')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        return t

    def _write_layer(self, t, data):
        with open(os.path.join(t.root, 'patients', 'alpha', self.OCR), 'wb') as fh:
            fh.write(data)

    def _ledger(self, t):
        return _read_bytes(t), _read_bytes(t, name='MANIFEST.checkpoint')

    def _refused(self, t, today='2026-07-20', want=None):
        before = self._ledger(t)
        with self.assertRaises(append.AppendStop) as cm:
            append.retranscribe(t.root, 'alpha', self.REL, today=today)
        if want:
            self.assertIn(want, str(cm.exception))
        self.assertEqual(self._ledger(t), before)   # zero writes
        return cm.exception

    def test_corrected_layer_with_erratum_greens_and_keeps_original_and_identity(self):
        t = self._tree()
        append.confirm(t.root, 'alpha', self.REL, today='2026-07-15')
        before = _read_bytes(t)
        old = _active_status(t, self.REL)
        self._write_layer(t, self.FIXED + self.ERRATUM)
        ok, _ = t.is_green(); self.assertFalse(ok)          # the edit alone reds L13
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertTrue(_read_bytes(t).startswith(before))  # append-only byte prefix
        new = _active_status(t, self.REL)
        self.assertEqual(new['supersede_reason'], 'retranscribe')
        self.assertEqual(new['supersedes'], old['record_id'])
        self.assertEqual(new['derivatives'],
                         [{'derivative_relpath': self.OCR,
                           'derivative_sha256': sha(self.FIXED + self.ERRATUM),
                           'derivative_errata_count': 1}])
        for k in ('sha256', 'identity_status', 'identity_reviewer', 'identity_source', 'review_date',
                  'acquired_date', 'capture_method', 'person_record_id'):
            self.assertEqual(new[k], old[k], k)               # original and identity untouched

    def test_uncorrected_edit_without_the_op_stays_red(self):
        t = self._tree()
        self._write_layer(t, self.FIXED)
        findings, _ = t.verify()
        self.assertIn('RED derivative bytes do not match recorded sha256', [f.render() for f in findings])

    def test_refused_without_an_erratum(self):
        t = self._tree()
        self._write_layer(t, self.FIXED)
        self._refused(t, want='no new erratum line for this correction')
        ok, _ = t.is_green(); self.assertFalse(ok)          # still red: nothing was re-blessed

    def test_refused_when_the_only_entry_predates_the_record(self):
        t = self._tree()   # migrated 2026-07-14
        self._write_layer(t, self.FIXED + b'\n## Errata\n- 2026-07-13, page 2: 3.4 -> 4.3\n')
        self._refused(t, want='no new erratum line for this correction')

    def test_refused_when_the_only_entry_is_dated_after_the_op(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        self._refused(t, today='2026-07-19', want='no new erratum line for this correction')

    def test_a_second_correction_needs_its_own_entry(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        self._write_layer(t, self.FIXED + b'Value Y: 7\n' + self.ERRATUM)
        self._refused(t, today='2026-07-22', want='no new erratum line for this correction')
        self._write_layer(t, self.FIXED + b'Value Y: 7\n' + self.ERRATUM
                          + b'- 2026-07-22, pages 3-4: [illegible] -> Value Y: 7\n')
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-22')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_a_same_day_second_correction_needs_its_own_entry(self):
        # later verify rounds the same day find more misreads: the count, not the date, catches reuse
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        append.confirm(t.root, 'alpha', self.REL, today='2026-07-20')   # the count walks through it
        self._write_layer(t, self.FIXED + b'Value Y: 7\n' + self.ERRATUM)
        self._refused(t, today='2026-07-20', want='no new erratum line for this correction')
        self._write_layer(t, self.FIXED + b'Value Y: 7\n' + self.ERRATUM
                          + b'- 2026-07-20, page 3: [illegible] -> Value Y: 7\n')
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    TWO = (b'\n## Errata\n- 2026-07-20, page 2: Value X 3.4 unit -> 4.3 unit\n'
           b'- 2026-07-20, page 3: Value Z: 1 -> Value Z: 7\n')

    def _bound(self, t):
        return _active_status(t, self.REL)['derivatives'][0].get('derivative_errata_count')

    def test_spare_lines_of_a_multi_line_correction_carry_no_later_edit(self):
        # Codex on #94: a first correction with two lines bound once must not let a second edit
        # through on the same two lines, same day; one more line lets it through
        t = self._tree()
        self._write_layer(t, self.FIXED + b'Value Z: 7\n' + self.TWO)
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')   # several lines: passes
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertEqual(self._bound(t), 2)
        self._write_layer(t, self.FIXED + b'Value Z: 7\nValue Y: 9\n' + self.TWO)
        self._refused(t, today='2026-07-20', want='no new erratum line for this correction')
        ok, _ = t.is_green(); self.assertFalse(ok)
        self._write_layer(t, self.FIXED + b'Value Z: 7\nValue Y: 9\n' + self.TWO
                          + b'- 2026-07-20, page 4: [illegible] -> Value Y: 9\n')
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')   # one more: passes
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertEqual(self._bound(t), 3)

    def test_the_bound_count_walks_back_through_a_rename(self):
        # all on one day, so the date floor cannot stand in for the count
        t = self._tree()
        self._write_layer(t, self.FIXED + b'Value Z: 7\n' + self.TWO)
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        rel2, ocr2 = 'med/sources/2026-01-01__source__b.pdf', 'med/sources/2026-01-01__source__b.ocr.md'
        base = os.path.join(t.root, 'patients', 'alpha')
        os.rename(os.path.join(base, self.REL), os.path.join(base, rel2))
        os.rename(os.path.join(base, self.OCR), os.path.join(base, ocr2))
        append.rename(t.root, 'alpha', self.REL, rel2, today='2026-07-20')
        with open(os.path.join(base, ocr2), 'wb') as fh:
            fh.write(self.FIXED + b'Value Z: 7\nValue Y: 9\n' + self.TWO)
        with self.assertRaises(append.AppendStop) as cm:
            append.retranscribe(t.root, 'alpha', rel2, today='2026-07-20')
        self.assertIn('no new erratum line', str(cm.exception))
        with open(os.path.join(base, ocr2), 'ab') as fh:
            fh.write(b'- 2026-07-20, page 4: [illegible] -> Value Y: 9\n')
        append.retranscribe(t.root, 'alpha', rel2, today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    REL2 = 'med/sources/2026-01-01__source__b.pdf'
    OCR2 = 'med/sources/2026-01-01__source__b.ocr.md'

    def _move(self, t, layer):
        """Move the original to REL2 and leave `layer` at OCR2 (None: no transcription there)."""
        base = os.path.join(t.root, 'patients', 'alpha')
        os.rename(os.path.join(base, self.REL), os.path.join(base, self.REL2))
        if os.path.exists(os.path.join(base, self.OCR)):
            os.remove(os.path.join(base, self.OCR))
        if layer is not None:
            with open(os.path.join(base, self.OCR2), 'wb') as fh:
                fh.write(layer)

    def _bare_tree(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'ORIGINAL-SCAN')
        migrate.migrate(t.root, today='2026-07-14')
        return t

    def test_rename_refuses_a_transcription_changed_on_the_way(self):
        # the sibling path: an edited transcription moved with its original would otherwise be bound
        # by `rename` with no erratum line; so would one dropped, or added where none was bound
        for make, layer in ((self._tree, self.FIXED), (self._tree, self.FIXED + self.ERRATUM),
                            (self._tree, None), (self._bare_tree, self.FIXED)):
            t = make()
            self._move(t, layer)
            before = self._ledger(t)
            with self.assertRaises(append.AppendStop) as cm:
                append.rename(t.root, 'alpha', self.REL, self.REL2, today='2026-07-20')
            self.assertIn('retranscribe', str(cm.exception))
            self.assertEqual(self._ledger(t), before)          # zero writes
            ok, _ = t.is_green(); self.assertFalse(ok)

    def test_rename_carries_an_unchanged_transcription(self):
        t = self._tree()
        self._move(t, self.LAYER)
        append.rename(t.root, 'alpha', self.REL, self.REL2, today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertEqual(_active_status(t, self.REL2)['derivatives'],
                         [{'derivative_relpath': self.OCR2, 'derivative_sha256': sha(self.LAYER)}])

    def test_finalize_refuses_a_hand_appended_rename_or_confirm_over_a_changed_layer(self):
        # structurally consistent rows (they record the edited layer's hash), so only the semantic
        # gate stands between them and an edited transcription bound with no erratum line
        for reason, layer, refused in (('rename', self.FIXED, True), ('status-change', self.FIXED, True),
                                       ('rename', self.LAYER, False)):        # negative control
            t = self._tree()
            old = _records(t)[-1]
            if reason == 'rename':
                self._move(t, layer)
                row = dict(old, source_relpath=self.REL2, derivatives=[
                    {'derivative_relpath': self.OCR2, 'derivative_sha256': sha(layer)}])
            else:
                self._write_layer(t, layer)
                row = dict(old, identity_status='operator-confirmed', identity_reviewer='operator',
                           derivatives=[{'derivative_relpath': self.OCR, 'derivative_sha256': sha(layer)}])
            row.update(record_id='eeeeeeeeeeeeeeee', supersedes=old['record_id'],
                       supersede_reason=reason, supersede_date='2026-07-20')
            with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'), 'a',
                      encoding='utf-8') as fh:
                fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
            if refused:
                with self.assertRaises(append.AppendStop) as cm:
                    append.prefix_finalize(t.root, 'alpha')
                self.assertIn('carry the transcription unchanged', str(cm.exception), reason)
                ok, _ = t.is_green(); self.assertFalse(ok)
            else:
                append.prefix_finalize(t.root, 'alpha')
                ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_a_rescan_starts_the_count_again(self):
        # a rehash writes the transcription whole from the new scan; its first correction needs one line
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        with open(os.path.join(t.root, 'patients', 'alpha', self.REL), 'wb') as fh:
            fh.write(b'RE-SCANNED')
        self._write_layer(t, self.LAYER)
        append.rehash(t.root, 'alpha', self.REL, today='2026-07-21')
        self._write_layer(t, self.FIXED + b'\n## Errata\n- 2026-07-22, page 2: 3.4 -> 4.3\n')
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-22')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_malformed_erratum_is_refused(self):
        for block in (b'## Errata\n- 2026-07-20: 3.4 -> 4.3\n',              # no page
                      b'## Errata\n- 2026-07-20, page 2: now reads 4.3\n',   # no was -> now
                      b'## Errata\n- 2026-07-20, page 2: 3.4 -> 4.3\n'
                      b'- 2026-02-30, page 1: a -> b\n',                     # not a real date
                      b'## Errata\n- 2026-07-20, page 2: 3.4 -> 4.3\nsee above\n',
                      self.ERRATUM + b'\n## Errata\n- 2026-07-20, page 1: a -> b\n'):
            t = self._tree()
            self._write_layer(t, self.FIXED + b'\n' + block)
            self._refused(t)

    def test_unicode_arrow_and_trailing_section_are_accepted(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + '\n## Errata\n- 2026-07-20, page 1: done → could not be '
                          'done\n\n## Notes\nfree text\n'.encode('utf-8'))
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_refused_when_the_original_changed_too(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        with open(os.path.join(t.root, 'patients', 'alpha', self.REL), 'wb') as fh:
            fh.write(b'RE-SCANNED')
        self._refused(t, want='source bytes do not match recorded sha256')

    def test_rehash_of_an_unchanged_original_points_to_retranscribe(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        with self.assertRaises(append.AppendStop) as cm:
            append.rehash(t.root, 'alpha', self.REL, today='2026-07-20')
        self.assertIn('retranscribe', str(cm.exception))

    def test_refused_when_the_layer_is_unchanged(self):
        t = self._tree()
        self._refused(t, want='transcription is unchanged')

    def test_refused_when_no_transcription_is_bound(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'ORIGINAL-SCAN')
        migrate.migrate(t.root, today='2026-07-14')
        self._write_layer(t, self.FIXED + self.ERRATUM)      # a first layer, written after inventory
        self._refused(t, want='no single transcription is bound')

    def test_relpath_names_the_original_not_the_layer(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        with self.assertRaisesRegex(append.AppendStop, 'not a primary source'):
            append.retranscribe(t.root, 'alpha', self.OCR, today='2026-07-20')

    def test_symlinked_or_non_regular_layer_is_refused(self):
        t = self._tree()
        p = os.path.join(t.root, 'patients', 'alpha', self.OCR)
        os.remove(p); os.mkdir(p)
        self._refused(t, want='not a regular file')
        os.rmdir(p)
        outside = os.path.join(t.root, 'outside.ocr.md')
        with open(outside, 'wb') as fh:
            fh.write(self.FIXED + self.ERRATUM)
        os.symlink(outside, p)
        self._refused(t, want='symlink')

    def test_the_builder_never_opens_the_original(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        records = _records(t)
        opened = _opened_by(lambda: append._build_retranscribe(t.root, 'alpha', PID, records, self.REL, '2026-07-20'))
        self.assertEqual(opened, ['2026-01-01__source__a.ocr.md'])

    def _crash_after(self, t):
        """Run a retranscribe, then put the pre-op checkpoint back (a crash between the two writes)."""
        cp = _read_bytes(t, name='MANIFEST.checkpoint')
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint'), 'wb') as fh:
            fh.write(cp)
        ok, _ = t.is_green(); self.assertFalse(ok)

    def test_finalize_recovers_a_crashed_retranscribe(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        self._crash_after(t)
        append.prefix_finalize(t.root, 'alpha')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def _hand_append(self, t, **changes):
        old = _records(t)[-1]
        row = dict(old, record_id='eeeeeeeeeeeeeeee', supersedes=old['record_id'],
                   supersede_reason='retranscribe', supersede_date='2026-07-20', **changes)
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'), 'a',
                  encoding='utf-8') as fh:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')

    def test_finalize_refuses_a_hand_appended_row_without_erratum(self):
        t = self._tree()
        self._write_layer(t, self.FIXED)
        self._hand_append(t, derivatives=[{'derivative_relpath': self.OCR,
                                           'derivative_sha256': sha(self.FIXED),
                                           'derivative_errata_count': 1}])
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn('erratum', str(cm.exception))
        ok, _ = t.is_green(); self.assertFalse(ok)

    def test_finalize_refuses_a_hand_appended_row_that_promotes_identity(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + self.ERRATUM)
        self._hand_append(t, identity_status='operator-confirmed', identity_reviewer='operator',
                          derivatives=[{'derivative_relpath': self.OCR,
                                        'derivative_sha256': sha(self.FIXED + self.ERRATUM),
                                        'derivative_errata_count': 1}])
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn('identity status', str(cm.exception))

    def test_finalize_refuses_a_hand_appended_row_over_a_substituted_original(self):
        # structurally consistent (the row records the substituted bytes), so only the semantic gate
        # stands between it and an attested identity carried onto a different document
        t = self._tree()
        append.confirm(t.root, 'alpha', self.REL, today='2026-07-15')
        self._write_layer(t, self.FIXED + self.ERRATUM)
        with open(os.path.join(t.root, 'patients', 'alpha', self.REL), 'wb') as fh:
            fh.write(b'SUBSTITUTED')
        self._hand_append(t, sha256=sha(b'SUBSTITUTED'),
                          derivatives=[{'derivative_relpath': self.OCR,
                                        'derivative_sha256': sha(self.FIXED + self.ERRATUM),
                                        'derivative_errata_count': 1}])
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn("original's path and bytes", str(cm.exception))

    def test_finalize_refuses_a_hand_appended_row_with_a_forged_count(self):
        # an under-count would leave a spare line for the next edit; an over-count is not the file's
        for forged in (1, 3):
            t = self._tree()
            self._write_layer(t, self.FIXED + b'Value Z: 7\n' + self.TWO)
            self._hand_append(t, derivatives=[{'derivative_relpath': self.OCR,
                                               'derivative_sha256': sha(self.FIXED + b'Value Z: 7\n' + self.TWO),
                                               'derivative_errata_count': forged}])
            with self.assertRaises(append.AppendStop) as cm:
                append.prefix_finalize(t.root, 'alpha')
            self.assertIn('erratum count', str(cm.exception), forged)
            ok, _ = t.is_green(); self.assertFalse(ok)

    def test_finalize_refuses_a_hand_appended_row_reusing_spare_lines(self):
        t = self._tree()
        self._write_layer(t, self.FIXED + b'Value Z: 7\n' + self.TWO)
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-20')
        data = self.FIXED + b'Value Z: 7\nValue Y: 9\n' + self.TWO
        self._write_layer(t, data)
        self._hand_append(t, derivatives=[{'derivative_relpath': self.OCR, 'derivative_sha256': sha(data),
                                           'derivative_errata_count': 2}])
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn('no new erratum line', str(cm.exception))

    def test_finalize_refuses_a_hand_appended_row_that_drops_the_layer(self):
        t = self._tree()
        os.remove(os.path.join(t.root, 'patients', 'alpha', self.OCR))
        self._hand_append(t, derivatives=[])
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn('exactly one transcription', str(cm.exception))

    def test_cli_prints_no_identifier_or_content(self):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        t = self._tree()
        self._write_layer(t, self.FIXED)
        for want_code, data in ((3, self.FIXED), (0, self.FIXED + self.ERRATUM)):
            self._write_layer(t, data)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = M.main(['--root', t.root, 'append', 'alpha', 'retranscribe',
                               '--relpath', self.REL])
            out = buf.getvalue()
            self.assertEqual(code, want_code, out)
            for secret in ('alpha', 'source__a', PID, 'Value X', '4.3'):
                self.assertNotIn(secret, out)
        # the CLI stamps today's date; the erratum entry is dated within [2026-07-14, today]
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])


def _ledger_state(t, handle='alpha'):
    return _read_bytes(t, handle), _read_bytes(t, handle, name='MANIFEST.checkpoint')


class BatchAddTests(unittest.TestCase):
    """`append <handle> add` with several --relpath values (ADR-0037 §14; handover 50 finding 2):
    documents that arrive together are added in one locked, projected, all-or-nothing append."""
    A, B, C = ('med/sources/2026-02-02__lab__b.pdf', 'med/sources/2026-02-03__lab__c.pdf',
               'med/sources/2026-02-04__lab__d.pdf')

    def _two_new(self):
        t = _migrated(self)
        t.src('alpha', '2026-02-02__lab__b.pdf', b'BBBB').src('alpha', '2026-02-02__lab__b.ocr.md', b'OCR-B')
        t.src('alpha', '2026-02-03__lab__c.pdf', b'CCCC').src('alpha', '2026-02-03__lab__c.ocr.md', b'OCR-C')
        return t

    def _refused(self, t, relpaths, want=None):
        before = _ledger_state(t)
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', relpaths, today='2026-07-18')
        if want:
            self.assertIn(want, str(cm.exception))
        self.assertEqual(_ledger_state(t), before)            # zero writes

    def test_one_at_a_time_is_refused_while_the_other_waits(self):
        # the incident: each single add is projected red by the other new source (negative control)
        t = self._two_new()
        self._refused(t, self.A, want='source on disk with no active manifest record')
        self._refused(t, self.B, want='source on disk with no active manifest record')

    def test_the_refusal_names_the_pending_files_and_the_one_call_that_logs_all(self):
        # the note: a file the caller did not name, the other-session warning, and calls that work as
        # printed — the combined add never carries the caller's attestation (the other file's owner is
        # unconfirmed), `confirm` follows for the caller's file alone; a private-mode person's names
        # print as placeholders
        import io, contextlib, shlex
        from tools.person_ownership import __main__ as M
        t = self._two_new()
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', self.A, confirmed=True, identity_source='sheet 1',
                              today='2026-07-18')
        lines = str(cm.exception).splitlines()
        self.assertIn('  ' + self.B, lines)
        self.assertNotIn('  ' + self.A, lines)                 # the caller's own file is not "pending"
        self.assertTrue(any('another session' in l for l in lines))
        calls = [shlex.split(l)[3:] for l in lines if l.startswith('  python3 -m')]
        self.assertEqual(len(calls), 2)                          # the combined add, then one confirm
        self.assertEqual(calls[0], ['--root', '.', 'append', 'alpha', 'add', '--relpath', self.A,
                                    '--relpath', self.B])        # no --confirmed, no --identity-source
        self.assertEqual(calls[1], ['--root', '.', 'append', 'alpha', 'confirm', '--relpath', self.A,
                                    '--identity-source', 'sheet 1'])
        for argv in calls:
            self.assertNotIn('--confirmed', argv)
            argv[1] = t.root
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(M.main(argv), 0)                # the printed calls are the fix
        self.assertEqual(_active_status(t, self.A)['identity_status'], 'operator-confirmed')
        self.assertEqual(_active_status(t, self.B)['identity_status'], 'legacy-folder-only')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        # private mode: the other file's name and the handle stay out of the output
        t = self._two_new()
        with open(os.path.join(t.root, 'patients', 'alpha', 'profile.md'), 'a', encoding='utf-8') as fh:
            fh.write('- Private mode: synthetic \u27e8never-API\u27e9\n')
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', self.A, confirmed=True, today='2026-07-18')
        self.assertIn('names withheld', str(cm.exception))
        self.assertIn('confirm --relpath <each file you named', str(cm.exception))
        for secret in ('lab__b', 'lab__c', 'alpha'):
            self.assertNotIn(secret, str(cm.exception))
        # a different kind pending too (a late transcription): no single call, so none is printed
        t = self._two_new()
        t.src('alpha', '2026-01-01__source__a.ocr.md', b'OCR-A')
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', self.A, today='2026-07-18')
        self.assertIn('no single call', str(cm.exception))
        self.assertNotIn('python3 -m', str(cm.exception))

    def test_two_new_sources_in_one_call_green_in_a_single_append(self):
        t = self._two_new()
        before = _read_bytes(t)
        from unittest import mock
        writes = []
        real = append._write_manifest_and_checkpoint
        with mock.patch.object(append, '_write_manifest_and_checkpoint',
                                        side_effect=lambda *a: (writes.append(1), real(*a))):
            append.add_source(t.root, 'alpha', [self.A, self.B], today='2026-07-18')
        self.assertEqual(len(writes), 1)                       # one locked write for the batch
        self.assertTrue(_read_bytes(t).startswith(before))     # append-only byte prefix
        self.assertEqual(len(_records(t)), 3)
        self.assertEqual(len({r['record_id'] for r in _records(t)}), 3)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        for rel in (self.A, self.B):
            self.assertEqual(len(_active_status(t, rel)['derivatives']), 1)

    def test_a_document_left_out_refuses_the_whole_batch(self):
        t = self._two_new()
        t.src('alpha', '2026-02-04__lab__d.pdf', b'DDDD')
        self._refused(t, [self.A, self.B], want='source on disk with no active manifest record')
        append.add_source(t.root, 'alpha', [self.A, self.B, self.C], today='2026-07-18')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_a_transcription_with_no_original_in_the_batch_refuses_it(self):
        # B's transcription written under a third document's name: nothing in the batch binds it
        t = _migrated(self)
        t.src('alpha', '2026-02-02__lab__b.pdf', b'BBBB').src('alpha', '2026-02-02__lab__b.ocr.md', b'OCR-B')
        t.src('alpha', '2026-02-03__lab__c.pdf', b'CCCC').src('alpha', '2026-02-04__lab__d.ocr.md', b'OCR-C')
        self._refused(t, [self.A, self.B], want='.ocr.md derivative on disk with no manifest binding')

    def test_a_missing_or_repeated_relpath_refuses_the_whole_batch(self):
        t = self._two_new()
        self._refused(t, [self.A, self.B, 'med/sources/2026-09-09__lab__ghost.pdf'],
                      want='not present on disk')
        self._refused(t, [self.A, self.A, self.B], want='named twice')
        self._refused(t, [self.A, 'med/sources/2026-01-01__source__a.pdf', self.B],
                      want='already exists')

    def test_cli_takes_repeated_relpath(self):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        t = self._two_new()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.main(['--root', t.root, 'append', 'alpha', 'add', '--relpath', self.A,
                           '--relpath', self.B])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertNotIn('lab__b', buf.getvalue())
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])


class TranscribeTests(unittest.TestCase):
    """`append <handle> transcribe` (ADR-0037 §14; KI A65 b): a first transcription written after its
    original was inventoried binds to it — original bytes and identity kept."""
    REL = 'med/sources/2026-01-01__source__a.pdf'
    OCR = 'med/sources/2026-01-01__source__a.ocr.md'
    LAYER = b'filed_as: 2026-01-01__source__a.pdf\n\n# a\n\nValue X: 3.4 unit\n'

    def _tree(self, confirmed=False):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'ORIGINAL-SCAN')
        migrate.migrate(t.root, today='2026-07-14')
        if confirmed:
            append.confirm(t.root, 'alpha', self.REL, today='2026-07-15')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        return t

    def _layer(self, t, data=None, rel=None):
        with open(os.path.join(t.root, 'patients', 'alpha', rel or self.OCR), 'wb') as fh:
            fh.write(self.LAYER if data is None else data)

    def _refused(self, t, want=None, rel=None):
        before = _ledger_state(t)
        with self.assertRaises(append.AppendStop) as cm:
            append.transcribe(t.root, 'alpha', rel or self.REL, today='2026-07-20')
        if want:
            self.assertIn(want, str(cm.exception))
        self.assertEqual(_ledger_state(t), before)            # zero writes

    def test_a_late_transcription_binds_and_greens(self):
        t = self._tree(confirmed=True)
        before, old = _read_bytes(t), _active_status(t, self.REL)
        self._layer(t)
        ok, f = t.is_green(); self.assertFalse(ok)              # unbound layer reds L13 (the incident)
        self.assertIn('RED .ocr.md derivative on disk with no manifest binding', [x.render() for x in f])
        append.transcribe(t.root, 'alpha', self.REL, today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertTrue(_read_bytes(t).startswith(before))
        new = _active_status(t, self.REL)
        self.assertEqual(new['supersede_reason'], 'transcribe')
        self.assertEqual(new['supersedes'], old['record_id'])
        self.assertEqual(new['derivatives'], [{'derivative_relpath': self.OCR,
                                               'derivative_sha256': sha(self.LAYER)}])
        for k in ('sha256', 'identity_status', 'identity_reviewer', 'identity_source', 'review_date',
                  'acquired_date', 'capture_method', 'person_record_id', 'source_relpath'):
            self.assertEqual(new[k], old[k], k)               # original and identity untouched
        self.assertEqual(schema.validate_record(new), [])

    def test_a_missing_layer_refuses(self):
        self._refused(self._tree(), want='no transcription beside the original')

    def test_a_wrong_stem_layer_refuses_and_stays_red(self):
        t = self._tree()
        self._layer(t, rel='med/sources/2026-01-01__source__b.ocr.md')
        self._refused(t, want='no transcription beside the original')
        ok, f = t.is_green(); self.assertFalse(ok)
        self.assertIn('RED transcription has no single original with its name stem beside it',
                      [x.render() for x in f])

    def test_a_layer_naming_another_original_refuses(self):
        t = self._tree()
        self._layer(t, b'filed_as: 2026-01-01__source__other.pdf\n\n# a\n')
        self._refused(t, want='filed_as names another original')

    def test_already_bound_points_to_retranscribe(self):
        t = self._tree()
        self._layer(t)
        append.transcribe(t.root, 'alpha', self.REL, today='2026-07-20')
        self._layer(t, self.LAYER + b'more\n')
        self._refused(t, want='retranscribe')

    def test_a_changed_original_refuses(self):
        t = self._tree()
        self._layer(t)
        with open(os.path.join(t.root, 'patients', 'alpha', self.REL), 'wb') as fh:
            fh.write(b'RE-SCANNED')
        self._refused(t, want='source bytes do not match recorded sha256')

    def test_the_builder_never_opens_the_original(self):
        t = self._tree()
        self._layer(t)
        records = _records(t)
        opened = _opened_by(lambda: append._build_transcribe(t.root, 'alpha', PID, records, self.REL, '2026-07-20'))
        self.assertEqual(opened, ['2026-01-01__source__a.ocr.md'])

    def test_its_first_correction_needs_an_erratum_line(self):
        t = self._tree()
        self._layer(t)
        append.transcribe(t.root, 'alpha', self.REL, today='2026-07-20')
        self._layer(t, self.LAYER.replace(b'3.4', b'4.3'))
        with self.assertRaises(append.AppendStop) as cm:
            append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-21')
        self.assertIn('no new erratum line', str(cm.exception))
        self._layer(t, self.LAYER.replace(b'3.4', b'4.3')
                    + b'\n## Errata\n- 2026-07-21, page 1: 3.4 -> 4.3\n')
        append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-21')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_finalize_recovers_a_crashed_transcribe(self):
        t = self._tree()
        self._layer(t)
        cp = _read_bytes(t, name='MANIFEST.checkpoint')
        append.transcribe(t.root, 'alpha', self.REL, today='2026-07-20')
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST.checkpoint'), 'wb') as fh:
            fh.write(cp)
        ok, _ = t.is_green(); self.assertFalse(ok)
        append.prefix_finalize(t.root, 'alpha')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_finalize_refuses_hand_appended_transcribe_rows(self):
        # each row is structurally consistent (it records the bytes on disk), so only the semantic
        # gate stands between it and a binding the op would refuse; the last is the negative control
        def bind(rel):
            return [{'derivative_relpath': rel, 'derivative_sha256': sha(self.LAYER)}]
        cases = (
            ('identity promoted', dict(identity_status='operator-confirmed', identity_reviewer='operator',
                                       derivatives=bind(self.OCR)), 'identity status'),
            ('another stem bound', dict(derivatives=bind('med/sources/2026-01-01__source__b.ocr.md')),
             'beside the original'),
            ('two layers', dict(derivatives=bind(self.OCR) + bind('med/sources/x.ocr.md')),
             'beside the original'),
            ('control', dict(derivatives=bind(self.OCR)), None),
        )
        for label, changes, want in cases:
            with self.subTest(label):
                t = self._tree()
                self._layer(t)
                if 'b.ocr.md' in str(changes):
                    self._layer(t, rel='med/sources/2026-01-01__source__b.ocr.md')
                old = _records(t)[-1]
                row = dict(old, record_id='eeeeeeeeeeeeeeee', supersedes=old['record_id'],
                           supersede_reason='transcribe', supersede_date='2026-07-20')
                row.update(changes)
                with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'), 'a',
                          encoding='utf-8') as fh:
                    fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
                if want:
                    with self.assertRaises(append.AppendStop) as cm:
                        append.prefix_finalize(t.root, 'alpha')
                    self.assertIn(want, str(cm.exception))
                else:
                    append.prefix_finalize(t.root, 'alpha')
                    ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_finalize_refuses_a_transcribe_row_after_a_bound_layer(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'ORIGINAL-SCAN')
        t.src('alpha', '2026-01-01__source__a.ocr.md', self.LAYER)
        migrate.migrate(t.root, today='2026-07-14')
        old = _records(t)[-1]
        row = dict(old, record_id='eeeeeeeeeeeeeeee', supersedes=old['record_id'],
                   supersede_reason='transcribe', supersede_date='2026-07-20')
        with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
        with self.assertRaises(append.AppendStop) as cm:
            append.prefix_finalize(t.root, 'alpha')
        self.assertIn('already binds a transcription', str(cm.exception))

    REL_B = 'med/sources/2026-01-02__source__b.pdf'
    OCR_B = 'med/sources/2026-01-02__source__b.ocr.md'

    def _two(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-01-01__source__a.pdf', b'SCAN-A').src('alpha', '2026-01-02__source__b.pdf', b'SCAN-B')
        migrate.migrate(t.root, today='2026-07-14')
        self._layer(t)
        self._layer(t, b'filed_as: 2026-01-02__source__b.pdf\n\n# b\n', rel=self.OCR_B)
        return t

    def test_two_late_layers_bind_in_one_call(self):
        # the deadlock: each layer alone is projected red by the other's unbound layer
        t = self._two()
        self._refused(t, want='append would leave L13 red')
        self._refused(t, want='append would leave L13 red', rel=self.REL_B)
        from unittest import mock
        writes, real = [], append._write_manifest_and_checkpoint
        with mock.patch.object(append, '_write_manifest_and_checkpoint',
                               side_effect=lambda *a: (writes.append(1), real(*a))):
            append.transcribe(t.root, 'alpha', [self.REL, self.REL_B], today='2026-07-20')
        self.assertEqual(len(writes), 1)
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        self.assertEqual(len({r['record_id'] for r in _records(t)}), len(_records(t)))

    def test_an_original_named_twice_refuses(self):
        t = self._two()
        before = _ledger_state(t)
        with self.assertRaises(append.AppendStop) as cm:
            append.transcribe(t.root, 'alpha', [self.REL, self.REL, self.REL_B], today='2026-07-20')
        self.assertIn('named twice', str(cm.exception))
        self.assertEqual(_ledger_state(t), before)

    def test_two_corrections_rebind_in_one_call(self):
        t = self._two()
        append.transcribe(t.root, 'alpha', [self.REL, self.REL_B], today='2026-07-20')
        erratum = b'\n## Errata\n- 2026-07-21, page 1: 3.4 -> 4.3\n'
        self._layer(t, self.LAYER.replace(b'3.4', b'4.3') + erratum)
        self._layer(t, b'filed_as: 2026-01-02__source__b.pdf\n\n# b, corrected\n' + erratum, rel=self.OCR_B)
        before = _ledger_state(t)
        with self.assertRaisesRegex(append.AppendStop, 'would leave L13 red'):
            append.retranscribe(t.root, 'alpha', self.REL, today='2026-07-21')   # the other pending: red
        self.assertEqual(_ledger_state(t), before)
        append.retranscribe(t.root, 'alpha', [self.REL, self.REL_B], today='2026-07-21')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_finalize_refuses_a_backdated_future_or_altered_transcribe_row(self):
        for label, changes, want in (
                ('backdated', dict(supersede_date='2026-07-01'), 'dated before'),
                ('future', dict(supersede_date='2999-01-01'), 'after today'),
                ('field changed', dict(acquired_date='2020-01-01'), 'carry every other field'),
                ('control', {}, None)):
            with self.subTest(label):
                t = self._tree()
                self._layer(t)
                old = _records(t)[-1]
                row = dict(old, record_id='eeeeeeeeeeeeeeee', supersedes=old['record_id'],
                           supersede_reason='transcribe', supersede_date='2026-07-20',
                           derivatives=[{'derivative_relpath': self.OCR, 'derivative_sha256': sha(self.LAYER)}])
                row.update(changes)
                with open(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST'), 'a',
                          encoding='utf-8') as fh:
                    fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
                if want:
                    with self.assertRaises(append.AppendStop) as cm:
                        append.prefix_finalize(t.root, 'alpha', today='2026-10-02')
                    self.assertIn(want, str(cm.exception))
                else:
                    append.prefix_finalize(t.root, 'alpha', today='2026-10-02')
                    ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_cli_prints_no_identifier(self):
        import io, contextlib
        from tools.person_ownership import __main__ as M
        t = self._tree()
        self._layer(t)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.main(['--root', t.root, 'append', 'alpha', 'transcribe', '--relpath', self.REL])
        self.assertEqual(code, 0, buf.getvalue())
        for secret in ('alpha', 'source__a', PID, 'Value X'):
            self.assertNotIn(secret, buf.getvalue())
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])


class TranscriptionPairTests(unittest.TestCase):
    """A transcription sits beside its own original (L13; KI A66): same name stem, bound to that
    original, and its front matter's `filed_as:`, when present, names it."""
    A, B = '2026-05-14__lab__a.pdf', '2026-05-14__lab__b.pdf'

    def _pair(self, layer_a=b'# a\n', layer_b=b'# b\n', migrate_now=True):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', self.A, b'SCAN-A').src('alpha', self.B, b'SCAN-B')
        t.src('alpha', self.A[:-4] + '.ocr.md', layer_a).src('alpha', self.B[:-4] + '.ocr.md', layer_b)
        if migrate_now:
            migrate.migrate(t.root, today='2026-07-14')
        return t

    def _cats(self, t):
        return [x.render() for x in t.verify()[0]]

    def test_matched_pairs_pass(self):
        for fm in (b'filed_as: %s\n\n# x\n', b'---\nfiled_as: "%s"\nsource: scan\n---\n# x\n',
                   b'FILED_AS: med/sources/%s\n\n# x\n', b'filed_as: `%s`\n\n# x\n'):
            with self.subTest(fm):
                t = self._pair(fm % self.A.encode(), fm % self.B.encode())
                ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_a_swapped_pair_reds(self):
        t = self._pair(b'filed_as: %s\n\n# x\n' % self.B.encode(), b'filed_as: %s\n\n# x\n' % self.A.encode())
        self.assertEqual(self._cats(t).count('RED transcription filed_as names another original (swapped pair?)'), 2)

    def test_every_spelling_of_a_swapped_name_reds(self):
        # the first non-empty value is compared; a byte-order mark does not hide the block
        B = self.B.encode()
        for fm in (b'filed_as:\n    %s\n\n# x\n', b'\xef\xbb\xbffiled_as: %s\n\n# x\n'):
            with self.subTest(fm):
                t = self._pair(fm % B)
                self.assertIn('RED transcription filed_as names another original (swapped pair?)', self._cats(t))

    def test_a_repeated_or_list_filed_as_reds(self):
        A, B = self.A.encode(), self.B.encode()
        for fm in (b'filed_as: %s\nfiled_as: %s\n\n# x\n' % (A, B),
                   b'filed_as: %s\nfiled_as:\n\n# x\n' % A,
                   b'filed_as:\n  - %s\n  - %s\n\n# x\n' % (A, B),
                   b'filed_as:\n    - %s\n\n# x\n' % A,
                   b'filed_as: [%s, %s]\n\n# x\n' % (A, B),
                   b'filed_as: %s\n    %s\n\n# x\n' % (A, B)):
            with self.subTest(fm):
                t = self._pair(fm)
                self.assertIn('RED transcription filed_as is repeated or a list — it names one original',
                              self._cats(t))
        t = self._pair(b'filed_as:\n\n# an empty value is no claim\n')      # negative control
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_the_bound_original_wins_when_two_share_a_stem(self):
        # x.jpg inventoried first, then x.pdf's transcription bound: green before this check, green now
        t = Tree(self); t.patient('alpha')
        t.src('alpha', '2026-05-14__lab__x.jpg', b'PHOTO').src('alpha', '2026-05-14__lab__x.pdf', b'SCAN')
        migrate.migrate(t.root, today='2026-07-14')
        t.src('alpha', '2026-05-14__lab__x.ocr.md', b'filed_as: 2026-05-14__lab__x.pdf\n\n# x\n')
        append.transcribe(t.root, 'alpha', 'med/sources/2026-05-14__lab__x.pdf', today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])
        t.src('alpha', '2026-05-14__lab__x.ocr.md', b'filed_as: 2026-05-14__lab__x.jpg\n\n# x\n')
        self.assertIn('RED transcription filed_as names another original (swapped pair?)', self._cats(t))

    def test_negative_control_no_front_matter_or_filed_as_in_the_body(self):
        # without the field nothing is compared — and a body line is not front matter
        t = self._pair(b'# a\n\nfiled_as: %s\n' % self.B.encode(), b'source: scan\n\n# b\n')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_the_writer_refuses_to_inventory_a_swapped_pair(self):
        t = _migrated(self)
        t.src('alpha', self.A, b'SCAN-A').src('alpha', self.A[:-4] + '.ocr.md', b'filed_as: %s\n' % self.B.encode())
        before = _ledger_state(t)
        with self.assertRaises(append.AppendStop) as cm:
            append.add_source(t.root, 'alpha', 'med/sources/' + self.A, today='2026-07-18')
        self.assertIn('filed_as names another original', str(cm.exception))
        self.assertEqual(_ledger_state(t), before)

    def test_init_refuses_a_swapped_pair(self):
        t = self._pair(b'filed_as: %s\n' % self.B.encode(), b'# b\n', migrate_now=False)
        with self.assertRaises(append.AppendStop) as cm:
            append.init_ledger(t.root, 'alpha', today='2026-07-14')
        self.assertIn('filed_as names another original', str(cm.exception))
        self.assertFalse(os.path.lexists(os.path.join(t.root, 'patients', 'alpha', 'med', 'MANIFEST')))

    def test_a_rename_keeps_the_former_name_valid(self):
        t = self._pair(b'filed_as: %s\n\n# x\n' % self.A.encode())
        src = os.path.join(t.root, 'patients', 'alpha', 'med', 'sources')
        for old, new in ((self.A, '2026-05-14__lab__a2.pdf'),
                         (self.A[:-4] + '.ocr.md', '2026-05-14__lab__a2.ocr.md')):
            os.rename(os.path.join(src, old), os.path.join(src, new))
        append.rename(t.root, 'alpha', 'med/sources/' + self.A, 'med/sources/2026-05-14__lab__a2.pdf',
                      today='2026-07-20')
        ok, f = t.is_green(); self.assertTrue(ok, [x.render() for x in f])

    def test_an_orphan_transcription_reds(self):
        t = _migrated(self)
        t.src('alpha', '2026-03-03__lab__nothing.ocr.md', b'# x\n')
        self.assertIn('RED transcription has no single original with its name stem beside it', self._cats(t))

    def test_a_hand_made_binding_to_another_stem_reds(self):
        t = Tree(self); t.patient('alpha')
        t.src('alpha', self.A, b'SCAN-A').src('alpha', self.B[:-4] + '.ocr.md', b'# b\n')
        t.src('alpha', self.B, b'SCAN-B')
        t.manifest('alpha', [
            rec(relpath='med/sources/' + self.A, data=b'SCAN-A', rid='aaaaaaaa', derivs=[
                {'derivative_relpath': 'med/sources/' + self.B[:-4] + '.ocr.md',
                 'derivative_sha256': sha(b'# b\n')}]),
            rec(relpath='med/sources/' + self.B, data=b'SCAN-B', rid='bbbbbbbb')])
        self.assertIn('RED transcription is bound to an original with another name stem', self._cats(t))

    def test_front_matter_parser(self):
        fm = fsverify.front_matter
        self.assertEqual(fm('id: X\nfiled_as: a.pdf\n\nbody: no\n'), {'id': ['X'], 'filed_as': ['a.pdf']})
        self.assertEqual(fm('---\nid: X\n---\nlater: no\n'), {'id': ['X']})
        self.assertEqual(fm('# Title\nid: X\n'), {})
        self.assertEqual(fm('    id: X\n'), {})
        self.assertEqual(fm('Id:X\r\n   key: one\n     two\n'), {'id': ['X'], 'key': ['one', 'two']})
        self.assertEqual(fm('\tid: X\n'), {})
        self.assertEqual(fm('id: X\n    \nlater: no\n'), {'id': ['X']})   # a blank line of spaces ends it



class MirrorTests(unittest.TestCase):
    """`verify --mirror` (the offsite backup's check): every active record's file must be present with
    its recorded bytes; a file no active record binds (an old name the append-only copy keeps, or a
    stray) is counted, never failed."""
    A, B, C = ('med/sources/2026-01-01__source__%s.pdf' % x for x in 'abc')
    LAYER = b'filed_as: 2026-01-01__source__a.pdf\n\n# t\n'

    def _mirror(self):
        # a -> b -> c with a transcription that still names a; the mirror kept every old copy
        ocr = lambda path: [{'derivative_relpath': path[:-4] + '.ocr.md', 'derivative_sha256': sha(self.LAYER)}]
        t = Tree(self); t.patient('alpha')
        for path in (self.A, self.B, self.C):
            t.src('alpha', path[12:], b'A').src('alpha', path[12:-4] + '.ocr.md', self.LAYER)
        t.manifest('alpha', [rec(rid='aaaaaaaa', derivs=ocr(self.A)),
                             rec(relpath=self.B, rid='bbbbbbbb', supersedes='aaaaaaaa', reason='rename',
                                 sdate='2026-01-02', derivs=ocr(self.B)),
                             rec(relpath=self.C, rid='cccccccc', supersedes='bbbbbbbb', reason='rename',
                                 sdate='2026-01-03', derivs=ocr(self.C))])
        return t

    def _mirror_verify(self, t):
        findings, agg = fsverify.verify_tree(t.root, mirror=True)
        return [x.render() for x in findings], agg.get('mirror_extra_files')

    def test_old_copies_are_counted_not_failed(self):
        t = self._mirror()
        self.assertEqual(self._mirror_verify(t), ([], 4))
        self.assertIn('RED ' + fsverify.UNLOGGED_SOURCE, [x.render() for x in t.verify()[0]])
        self.assertNotIn('mirror_extra_files', t.verify()[1])

    def test_a_stray_file_is_counted_not_failed(self):
        t = self._mirror()
        t.src('alpha', '2026-03-03__source__stray.pdf', b'S')
        self.assertEqual(self._mirror_verify(t), ([], 5))

    def test_a_current_file_missing_or_drifted_reds(self):
        for path, data, red in (
                (self.C, None, 'RED active record for a source not on disk'),
                (self.C, b'Z', 'RED source bytes do not match recorded sha256 (drift)'),
                (self.C[:-4] + '.ocr.md', None, 'RED declared derivative not on disk'),
                (self.C[:-4] + '.ocr.md', b'Z', 'RED derivative bytes do not match recorded sha256')):
            with self.subTest(path=path, data=data):
                t = self._mirror()
                if data is None:
                    os.remove(os.path.join(t.root, 'patients', 'alpha', path))
                else:
                    t.src('alpha', path[12:], data)
                self.assertIn(red, self._mirror_verify(t)[0])


if __name__ == '__main__':
    unittest.main()
