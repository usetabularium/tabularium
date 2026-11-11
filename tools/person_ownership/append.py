#!/usr/bin/env python3
"""Append-safe MANIFEST writer (ADR-0037 §11 / handover 12). The one supported path to add a
later source or correct an existing record AFTER a person's initial migration, without ever
re-blessing an in-place rewrite of the append-only ledger. `init_ledger` (§12) writes one person's
FIRST ledger through the same lock / projected-verify / forward-write path.

Guarantees (ADR-0037 §10 requirements):
  1. Append-only prefix proof — the on-disk MANIFEST must byte-for-byte match its checkpoint before
     any append (a finalized, un-drifted starting state); the new manifest is the old bytes with new
     line(s) *concatenated* (an exact byte prefix, never a rewrite).
  2. Crash-safe forward write under an exclusive lock — the new state is written only AFTER the
     projected verify passes (see the correctness model), so there is a single forward write and no
     destructive rollback: MANIFEST is replaced first (atomic, so a torn/partial final line is never
     visible), then MANIFEST.checkpoint. A crash between those two replaces leaves the tree loudly RED
     (never a silent green) and is recoverable with `prefix_finalize` — the prefix-validating re-bless
     of an append that was already verified green. Every write is fsync + os.replace, mirroring
     migrate.write_manifest. The lock path itself is symlink-refused (never followed).
  3. Removal / split semantics — a `wrong-owner` retraction removes a misfiled source from the active
     view (the operator must have already moved the file off this person's med/sources); `split` is
     refused (v2-deferred: it needs bundle-linked provenance and a forked ledger the graph rejects).

Correctness model: the PROJECTED result (old bytes + new line(s)) is verified with the existing L13
verifier BEFORE anything is written — `fsverify.verify_tree(root, manifest_override={handle: ...})`
runs every L13 check against the projected manifest without publishing it. Only if that projected
state is green for this patient (and no global finding) is the new MANIFEST + checkpoint written (the
single crash-safe forward write). A rejected mutation writes NOTHING — there is no destructive
rollback, hence no rollback-crash window; and if the verifier itself raises, it propagates before any
write (fail closed). This rides the exhaustively-tested verifier instead of re-deriving its checks.
The only op-specific verifier change is `wrong-owner` retraction handling (fsverify).

Metadata only: hashes source bytes and reads path structure; never parses clinical content. The one
text it reads is a corrected transcription's erratum block (`retranscribe`, ADR-0037 §13), checked
for shape and date only; an original is never opened by that op. stdout (via __main__) stays
category/queue-only — never a hash or person id, and never a path or handle except what a refusal
names about files still waiting to be logged, which follows the locator rule (withheld for a
private-mode person). No source byte is ever changed; "removal" means the operator moved the file,
the tool only records it.
"""
import datetime
import fcntl
import hashlib
import json
import os
import re
import secrets
import shlex
import stat
import unicodedata

from . import schema
from . import fsverify
from .fsverify import (read_person_id, is_private_mode, _sha256_file, _OCR_SUFFIX, person_scheme_keys,
                       residue_re, _CONTROL_RE)
from .migrate import (_acquired_date_from_name, build_records, _write_person_id, MigrationStop,
                      _is_pristine_initial_manifest, _recorded_inventory, _evidence_inventory)


class AppendStop(Exception):
    """A fail-closed stop condition for the append writer (category only — never a handle, path,
    hash, or person id). Any refusal raises this; the caller commits nothing."""


def _today(today=None):
    return today or datetime.date.today().isoformat()


def _line(rec):
    """Canonical on-disk serialization of one record — identical to migrate.write_manifest and the
    test fixtures, so `compute_checkpoint` and the byte-prefix invariant stay consistent."""
    return (json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')


def _med(root, handle):
    return os.path.join(root, 'patients', handle, 'med')


def _abs(root, handle, relpath):
    return os.path.join(root, 'patients', handle, relpath)


def _check_handle(root, handle):
    """An operator-supplied patient handle must be a single safe directory segment directly under
    patients/ — never a traversal that escapes the jail (`../decoy`, `a/../b`), a nested path, a
    separator/NUL, or a hidden/cruft name. The L13 verifier only ever sees real `patients/*` dirents
    (`_list_patients`); the writer takes the handle from the operator, so containment MUST be checked
    here or every path (`_med`, `_abs`, lock, profile) and the post-write green-gate are escapable.
    Mirrors `_list_patients`' dot-skip + `schema._safe_relpath`'s segment rules. The handle must also
    match exactly one real `patients/` entry (NFC-compared, so case counts): on a case-insensitive
    filesystem `ALPHA` would open `alpha/` while the verifier walks — and the projected check keys
    on — the on-disk name, passing a gate that never saw this person. Returns the ON-DISK spelling
    or raises AppendStop (category only)."""
    if not isinstance(handle, str) or not handle:
        raise AppendStop('empty handle')
    if handle != unicodedata.normalize('NFC', handle):
        raise AppendStop('handle is not NFC-normalized')
    if ('\x00' in handle or '/' in handle or '\\' in handle or os.sep in handle
            or (os.altsep and os.altsep in handle)):
        raise AppendStop('handle contains a path separator or NUL')
    if handle in ('.', '..') or handle.startswith('.'):
        raise AppendStop('handle is ".", "..", or a hidden name')
    if handle != os.path.basename(handle):
        raise AppendStop('handle is not a single path segment')
    patients = os.path.join(root, 'patients')
    if os.path.islink(patients):
        raise AppendStop('patients root is symlinked')
    try:
        names = os.listdir(patients)
    except OSError:
        raise AppendStop('patients root cannot be listed')
    matches = [n for n in names if unicodedata.normalize('NFC', n) == handle]
    if len(matches) != 1:
        raise AppendStop('handle does not name exactly one patients/ entry (spelling and case count)')
    return matches[0]


def _new_record_id(existing_ids):
    rid = secrets.token_hex(8)
    while rid in existing_ids:
        rid = secrets.token_hex(8)
    return rid


def _check_relpath(relpath):
    """Operator-provided relpaths must be safe, NFC, and live under med/sources (never a derivative
    stem the caller mistook for a primary). Returns the NFC form or raises AppendStop."""
    if not isinstance(relpath, str) or not relpath:
        raise AppendStop('empty relpath')
    nfc = unicodedata.normalize('NFC', relpath)
    err = schema._safe_relpath(nfc)
    if err:
        raise AppendStop('unsafe relpath (' + err + ')')
    if not nfc.startswith('med/sources/'):
        raise AppendStop('relpath is not under med/sources/')
    if nfc.endswith(_OCR_SUFFIX):
        raise AppendStop('relpath is an .ocr.md derivative, not a primary source')
    return nfc


def _capture_method(relpath):
    return 'transcript' if relpath.lower().endswith(('.md', '.txt')) else 'scan'


def _derivative_for(root, handle, relpath):
    """The 1:1 `.ocr.md` sidecar of a primary (stem + '.ocr.md'), if present on disk. Mirrors the
    migration binding rule. Refuses a symlinked sidecar (never record through a symlink)."""
    ocr_rel = os.path.splitext(relpath)[0] + _OCR_SUFFIX
    ocr_abs = _abs(root, handle, ocr_rel)
    if os.path.islink(ocr_abs):
        raise AppendStop('derivative sidecar is a symlink')
    if os.path.isfile(ocr_abs):
        return [{'derivative_relpath': ocr_rel, 'derivative_sha256': _sha256_file(ocr_abs)}]
    return []


def _assert_no_symlink_path(root, handle, relpath):
    """Reject a symlink at ANY component of patients/<handle>/<relpath>, not just the final file. An
    intermediate symlinked directory under med/sources (e.g. `sources/labs` -> outside the repo) would
    otherwise be followed and the writer would hash a file OUTSIDE the jail. Walk each component with
    lstat-based islink so a link is caught before it is followed. (`_check_relpath` already forbids
    `..`/absolute; this covers an on-disk symlink component.)"""
    cur = os.path.join(root, 'patients', handle)
    for seg in relpath.split('/'):
        cur = os.path.join(cur, seg)
        if os.path.islink(cur):
            raise AppendStop('a path component is a symlink')


def _fresh_record_from_disk(root, handle, person_id, relpath, status, reviewer, identity_source,
                            today, supersedes='', reason=''):
    """Build a record by hashing the on-disk file at `relpath` (+ its 1:1 sidecar). Used by add /
    rename / rehash — anything whose bytes come from disk. Refuses a symlinked path component (so bytes
    are never hashed from outside the jail) or an absent primary."""
    src_abs = _abs(root, handle, relpath)
    _assert_no_symlink_path(root, handle, relpath)
    if not os.path.isfile(src_abs):
        raise AppendStop('source file is not present on disk at the given relpath')
    return {
        'schema_version': schema.SCHEMA_VERSION, 'record_id': None, 'person_record_id': person_id,
        'source_relpath': relpath, 'sha256': _sha256_file(src_abs),
        'acquired_date': _acquired_date_from_name(os.path.basename(relpath)) or today,
        'capture_method': _capture_method(relpath), 'identity_status': status,
        'identity_reviewer': reviewer, 'identity_source': identity_source, 'review_date': today,
        'derivatives': _derivative_for(root, handle, relpath),
        'supersedes': supersedes, 'supersede_reason': reason,
        'supersede_date': today if supersedes else ''}


def _active_by_relpath(records):
    """Active records keyed by source_relpath, EXCLUDING wrong-owner retractions — matching the L13
    verifier's active-on-disk view (`fsverify._is_retraction`). A retraction removes its source from
    the active view (the file is gone), so the relpath is free for a clean re-add and no follow-up op
    (confirm/rehash/rename/wrong-owner) can inherit a retracted record's operator-confirmed identity."""
    active, _ = schema.supersession_errors(records)
    out = {}
    for r in active:
        if fsverify._is_retraction(r):
            continue
        rp = r.get('source_relpath')
        if isinstance(rp, str):
            out.setdefault(rp, []).append(r)
    return out


def _one_active(records, relpath):
    by = _active_by_relpath(records)
    recs = by.get(relpath)
    if not recs:
        raise AppendStop('no active record for the given relpath')
    if len(recs) != 1:
        raise AppendStop('more than one active record for the given relpath (ledger already forked)')
    return recs[0]


# --------------------------------------------------------------------------------------------------
# Operation builders — each returns the list of NEW record(s) to append. They do the op-specific
# filesystem preconditions; the transaction (write + re-verify + rollback) is in _locked_apply.
# --------------------------------------------------------------------------------------------------
def _build_add(root, handle, person_id, records, relpaths, confirmed, identity_source, today):
    """One new record per relpath, all in one append (§14): a document that arrives with others is
    added with them, so the projected check sees every new file accounted for at once. A relpath
    named twice, or already inventoried, refuses the whole call."""
    if isinstance(relpaths, str):
        relpaths = [relpaths]
    if not relpaths:
        raise AppendStop('no relpath given')
    out = []
    for relpath in relpaths:
        relpath = _check_relpath(relpath)
        if relpath in _active_by_relpath(records + out):
            raise AppendStop('an active record already exists for this relpath, or it is named twice '
                             '(a later transcription is bound with transcribe; changed bytes with rehash)')
        status = 'operator-confirmed' if confirmed else 'legacy-folder-only'
        reviewer = 'operator' if confirmed else 'intake-pipeline'
        src = identity_source or ('operator append ' + today + (' — operator-confirmed' if confirmed
                                  else ' — folder position only, unverified'))
        rec = _fresh_record_from_disk(root, handle, person_id, relpath, status, reviewer, src, today)
        rec['record_id'] = _new_record_id({r.get('record_id') for r in records + out})
        out.append(rec)
    return out


def _carried_derivatives(rec):
    """`rec`'s derivatives as a `status-change` successor carries them: the same bindings, minus
    the erratum count, which stays on the `retranscribe` row that recorded it (schema) for
    `_bound_errata_count` to find."""
    return [{k: v for k, v in d.items() if k != schema.ERRATA_COUNT_FIELD} if isinstance(d, dict)
            else d for d in (rec.get('derivatives') or [])]


def _derivative_hashes(rec):
    """The transcription hashes a row binds, order-free. A rename or status-change carries them
    unchanged: a transcription changed, added or dropped on the way would be bound with no erratum
    line (ADR-0037 §13) — a correction is a `retranscribe`."""
    return sorted(str(d.get('derivative_sha256')) for d in (rec.get('derivatives') or [])
                  if isinstance(d, dict))


def _build_confirm(root, handle, person_id, records, relpath, identity_source, today):
    relpath = _check_relpath(relpath)
    old = _one_active(records, relpath)
    if old.get('identity_status') == 'operator-confirmed':
        raise AppendStop('record is already operator-confirmed')
    src = identity_source or ('operator confirmation ' + today + ' — reviewed and attested')
    rec = dict(old, record_id=_new_record_id({r.get('record_id') for r in records}),
               derivatives=_carried_derivatives(old),
               identity_status='operator-confirmed', identity_reviewer='operator',
               identity_source=src, review_date=today,
               supersedes=old['record_id'], supersede_reason='status-change', supersede_date=today)
    return [rec]


def _build_rename(root, handle, person_id, records, old_relpath, new_relpath, identity_source, today):
    old_relpath = _check_relpath(old_relpath)
    new_relpath = _check_relpath(new_relpath)
    if old_relpath == new_relpath:
        raise AppendStop('rename source and target are the same relpath')
    old = _one_active(records, old_relpath)
    if os.path.lexists(_abs(root, handle, old_relpath)):
        raise AppendStop('rename requires the old path to be gone on disk (move the file first)')
    if new_relpath in _active_by_relpath(records):
        raise AppendStop('an active record already exists for the target relpath')
    src = identity_source or ('operator rename ' + today + ' — path corrected; identity unchanged')
    rec = _fresh_record_from_disk(root, handle, person_id, new_relpath,
                                  old.get('identity_status'), old.get('identity_reviewer'), src, today,
                                  supersedes=old['record_id'], reason='rename')
    # A rename is a PURE path move — the successor inherits the old record's identity_status/reviewer,
    # so the moved bytes must be identical. Refuse if they differ: carrying an operator-confirmed
    # attestation onto substituted content would be a false "identity unchanged". Changed bytes are a
    # rehash (a fresh review), not a rename.
    if rec['sha256'] != old.get('sha256'):
        raise AppendStop('rename target bytes differ from the source record — a rename is a pure path '
                         'move; use rehash to record changed bytes')
    if _derivative_hashes(rec) != _derivative_hashes(old):
        raise AppendStop('rename refused: the transcription at the new path is not the one bound to '
                         'the original — move it with the original unchanged; a corrected '
                         'transcription is bound with `retranscribe` first, then renamed')
    rec['record_id'] = _new_record_id({r.get('record_id') for r in records})
    return [rec]


def _build_rehash(root, handle, person_id, records, relpath, identity_source, today):
    relpath = _check_relpath(relpath)
    old = _one_active(records, relpath)
    # A rehash records CHANGED bytes for the same path. Changed bytes invalidate any prior identity
    # attestation — the operator has not attested the NEW content — so an `operator-confirmed` record
    # DROPS to `legacy-folder-only` (the operator must re-`confirm` the re-scanned bytes). This blocks
    # the transfer of an operator-confirmed attestation onto substituted content (the changed-bytes
    # twin of the rename byte-equality guard). A legacy record keeps its status.
    was_confirmed = old.get('identity_status') == 'operator-confirmed'
    status = 'legacy-folder-only' if was_confirmed else old.get('identity_status')
    reviewer = 'intake-pipeline' if was_confirmed else old.get('identity_reviewer')
    default_src = ('operator rehash ' + today + ' — bytes re-scanned; '
                   + ('prior operator-confirmed attestation dropped, re-confirm required'
                      if was_confirmed else 'identity unchanged'))
    src = identity_source or default_src
    rec = _fresh_record_from_disk(root, handle, person_id, relpath, status, reviewer, src, today,
                                  supersedes=old['record_id'], reason='rehash')
    if rec['sha256'] == old.get('sha256'):
        raise AppendStop('rehash refused: the original\'s bytes are unchanged (nothing to record) — a '
                         'corrected transcription is recorded with `retranscribe`')
    rec['record_id'] = _new_record_id({r.get('record_id') for r in records})
    return [rec]


# A corrected transcription carries its own erratum (ADR-0037 §13): under one `## Errata` heading,
# at least one new line per correction — the date the original was checked, the page of the
# original looked at, and what changed. Checked for shape, count and date only; never printed.
ERRATUM_FORMAT = '- YYYY-MM-DD, page N: <as transcribed> -> <as the original reads>'
_ERRATA_HEADING_RE = re.compile(r'^##[ \t]+Errata[ \t]*$')
_HEADING_RE = re.compile(r'^#{1,6}[ \t]')
_ERRATUM_RE = re.compile(r'^- (\d{4}-\d{2}-\d{2}), pages? [^:]*[^\s:]: \S.*?[ \t]*(?:->|→)[ \t]*\S')


def _erratum_check(data, floor, ceiling, bound):
    """(n, None) when the transcription bytes carry a well-formed erratum of n lines, n greater than
    `bound` — the count the previous correction bound, so no line it bound, a spare one included,
    can carry a new edit, same day included — and one dated in [floor, ceiling]: not before the
    record's last ledger date, not after the op's date. Else (None, a category-only reason)."""
    try:
        lines = data.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        return None, 'the transcription is not UTF-8 text'
    starts = [i for i, line in enumerate(lines) if _ERRATA_HEADING_RE.match(line)]
    if len(starts) > 1:
        return None, 'the transcription has more than one `## Errata` heading'
    entries = []
    if starts:
        for line in lines[starts[0] + 1:]:
            if _HEADING_RE.match(line):
                break
            if not line.strip():
                continue
            m = _ERRATUM_RE.match(line)
            if not m or not schema._is_real_date(m.group(1)):
                return None, 'an erratum line is not in the form `' + ERRATUM_FORMAT + '`'
            entries.append(m.group(1))
    if len(entries) <= bound or not any(floor <= d <= ceiling for d in entries):
        return None, ('the transcription carries no new erratum line for this correction — add one '
                      'under its `## Errata` heading, `' + ERRATUM_FORMAT + '`, dated the day you '
                      'checked the original; earlier lines stay')
    return len(entries), None


def _read_transcription(root, handle, relpath):
    """The bytes of a bound `.ocr.md`, read once (the same bytes are hashed and checked). Refuses a
    symlinked path component or a non-regular file before opening it (a FIFO would block)."""
    _assert_no_symlink_path(root, handle, relpath)
    path = _abs(root, handle, relpath)
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise AppendStop('the bound transcription is not a regular file')
        with open(path, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        raise AppendStop('the bound transcription is not on disk')


def _last_ledger_date(rec):
    return rec.get('supersede_date') or rec.get('review_date') or ''


def _bound_errata_count(records, rec):
    """The erratum line count the latest `retranscribe` row leading to `rec` recorded, walking back
    through status-change and rename, which carry the transcription unchanged; 0 when an add, a
    migration row or a rehash (the transcription written whole) comes first. The caller has already
    validated the graph acyclic and every row's schema (so a count is a positive int)."""
    by_id = {r.get('record_id'): r for r in records}
    while rec is not None and rec.get('supersede_reason') in ('status-change', 'rename'):
        rec = by_id.get(rec.get('supersedes'))
    if rec is None or rec.get('supersede_reason') != 'retranscribe':
        return 0
    return max((d.get(schema.ERRATA_COUNT_FIELD, 0) for d in (rec.get('derivatives') or [])
                if isinstance(d, dict)), default=0)


def _each_original(records, relpaths, build_one):
    """One successor row per named original, all in one append (§14), so layers written together bind
    together: `build_one(relpath, old)` builds the row for one original's active record. An original
    named twice refuses the whole call; record ids stay unique across the batch."""
    if isinstance(relpaths, str):
        relpaths = [relpaths]
    if not relpaths:
        raise AppendStop('no relpath given')
    out, seen = [], set()
    for relpath in relpaths:
        relpath = _check_relpath(relpath)
        if relpath in seen:
            raise AppendStop('the same original is named twice in one call')
        seen.add(relpath)
        rec = build_one(relpath, _one_active(records, relpath))
        rec['record_id'] = _new_record_id({r.get('record_id') for r in records + out})
        out.append(rec)
    return out


def _build_retranscribe(root, handle, person_id, records, relpaths, today):
    """Re-bind a corrected `.ocr.md` to its unchanged original — one row per original named. Only the
    transcription is read; the original's recorded hash is carried over, and the projected L13 check
    refuses if its bytes moved (that is a `rehash`). Identity fields are kept: the original, which
    identity is about, is the same."""
    def one(relpath, old):
        derivs = [d for d in (old.get('derivatives') or []) if isinstance(d, dict)]
        if len(derivs) != 1:
            raise AppendStop('no single transcription is bound to this source — nothing to correct (a '
                             'first transcription is bound with `transcribe`)')
        ocr_rel = derivs[0].get('derivative_relpath')
        data = _read_transcription(root, handle, ocr_rel)
        digest = hashlib.sha256(data).hexdigest()
        if digest == derivs[0].get('derivative_sha256'):
            raise AppendStop('retranscribe refused: the transcription is unchanged (nothing to record)')
        count, problem = _erratum_check(data, _last_ledger_date(old), today,
                                        _bound_errata_count(records, old))
        if problem:
            raise AppendStop('retranscribe refused: ' + problem)
        return dict(old, derivatives=[{'derivative_relpath': ocr_rel, 'derivative_sha256': digest,
                                       schema.ERRATA_COUNT_FIELD: count}],
                    supersedes=old['record_id'], supersede_reason='retranscribe', supersede_date=today)
    return _each_original(records, relpaths, one)


def _ocr_beside(relpath):
    return os.path.splitext(relpath)[0] + _OCR_SUFFIX


def _build_transcribe(root, handle, person_id, records, relpaths, today):
    """Bind a FIRST transcription, written after its original was inventoried (§14; KI A65 b) — one row
    per original named: the `.ocr.md` with the original's name stem beside it. Only the transcription
    is read; the original's recorded hash is carried over and the projected L13 check refuses if its
    bytes moved, and checks the pair (stem, `filed_as:`). Identity fields are kept: the original is
    the same document."""
    def one(relpath, old):
        if old.get('derivatives'):
            raise AppendStop('a transcription is already bound to this source — a corrected one is '
                             'bound with `retranscribe`')
        ocr_rel = _ocr_beside(relpath)
        if not os.path.lexists(_abs(root, handle, ocr_rel)):
            raise AppendStop('no transcription beside the original — write it with the same name '
                             'stem, ending .ocr.md, then run this again')
        data = _read_transcription(root, handle, ocr_rel)
        return dict(old, derivatives=[{'derivative_relpath': ocr_rel,
                                       'derivative_sha256': hashlib.sha256(data).hexdigest()}],
                    supersedes=old['record_id'], supersede_reason='transcribe', supersede_date=today)
    return _each_original(records, relpaths, one)


def _build_wrong_owner(root, handle, person_id, records, relpath, identity_source, today):
    relpath = _check_relpath(relpath)
    old = _one_active(records, relpath)
    if os.path.lexists(_abs(root, handle, relpath)):
        raise AppendStop('wrong-owner requires the misfiled source already moved off this med/sources')
    # A retraction carries the misfiled record's bytes-metadata but declares NO derivatives and,
    # via supersede_reason='wrong-owner', tells the verifier the file must now be ABSENT here.
    src = identity_source or ('wrong-owner retraction ' + today
                              + ' — source belongs to another person; moved off this med/sources')
    rec = dict(old, record_id=_new_record_id({r.get('record_id') for r in records}),
               identity_status='operator-confirmed', identity_reviewer='operator',
               identity_source=src, review_date=today, derivatives=[],
               supersedes=old['record_id'], supersede_reason='wrong-owner', supersede_date=today)
    return [rec]


def _build_split(*a, **k):
    raise AppendStop('split is v2-deferred: it needs bundle-linked provenance and more than one '
                     'successor per record, which the ledger graph rejects as a fork')


# --------------------------------------------------------------------------------------------------
# Lock + consistent-load + crash-safe transaction
# --------------------------------------------------------------------------------------------------
_CHECKPOINTLESS_FIRST = ('a MANIFEST with no checkpoint that is exactly an interrupted first write '
                         '(re-deriving it from the folder reproduces it): remove that MANIFEST and '
                         're-run `init <handle>`')
_CHECKPOINTLESS_RESTORE = ('a MANIFEST with no checkpoint that carries history or disagrees with the '
                           'folder: restore the checkpoint from the snapshot/backup — never delete this '
                           'ledger')


def _checkpointless(med):
    """The one recovery a MANIFEST with no checkpoint allows, decided from its bytes. Deleting it is
    offered ONLY for exactly what an interrupted first write leaves — empty, or pristine legacy rows
    as `build_records` writes them — AND only while its recorded (relpath, sha256) inventory still
    equals the folder's, so no attestation, correction or L13-checked missing/drifted source can be
    erased by a re-run (§11.1's laundering class). Anything else, or anything unreadable: restore."""
    manifest = os.path.join(med, 'MANIFEST')
    try:
        with open(manifest, 'rb') as f:
            records = schema.parse_manifest_bytes(f.read())
        first = ((not records or (_is_pristine_initial_manifest(manifest) and all(
                     r['identity_source'].startswith('legacy migration ') for r in records)))
                 and _recorded_inventory(manifest) == _evidence_inventory(os.path.join(med, 'sources')))
    except (OSError, schema.ManifestError, MigrationStop):
        first = False
    return _CHECKPOINTLESS_FIRST if first else _CHECKPOINTLESS_RESTORE


def _load_consistent(med):
    """Read MANIFEST + checkpoint and require the finalized invariant: parseable JSONL, schema+graph
    valid, and the checkpoint byte-matches the manifest (no pending crash / no drift). Returns
    (manifest_bytes, records). Raises AppendStop otherwise (fail closed)."""
    manifest_path = os.path.join(med, 'MANIFEST')
    checkpoint_path = os.path.join(med, 'MANIFEST.checkpoint')
    if os.path.islink(manifest_path) or os.path.islink(checkpoint_path):
        raise AppendStop('MANIFEST or checkpoint is a symlink')
    if not os.path.isfile(manifest_path):
        raise AppendStop('no MANIFEST to append to — create the first ledger with `init <handle>`')
    if not os.path.isfile(checkpoint_path):
        raise AppendStop(_checkpointless(med))
    with open(manifest_path, 'rb') as f:
        manifest_bytes = f.read()
    try:
        records = schema.parse_manifest_bytes(manifest_bytes)
    except schema.ManifestError as e:
        raise AppendStop('MANIFEST unparseable (' + str(e) + ')')
    errs = []
    for r in records:
        errs.extend(schema.validate_record(r))
    _, sup_errs = schema.supersession_errors(records)
    if errs or sup_errs:
        raise AppendStop('current ledger is not schema/graph valid; refusing to append')
    try:
        with open(checkpoint_path, 'rb') as f:
            cp = schema.parse_checkpoint_bytes(f.read())
    except (OSError, ValueError, UnicodeDecodeError):
        raise AppendStop('checkpoint unreadable/unparseable')
    if schema.validate_checkpoint_shape(cp):
        raise AppendStop('checkpoint malformed')
    want = schema.compute_checkpoint(manifest_bytes, records)
    if (cp['manifest_sha256'] != want['manifest_sha256']
            or cp['record_count'] != want['record_count']
            or cp['tail_record_id'] != want['tail_record_id']):
        raise AppendStop('MANIFEST does not match its checkpoint (drift/pending crash) — finalize first')
    return manifest_bytes, records


def _atomic_write(path, data):
    tmp = path + '.tmp-%s' % secrets.token_hex(4)
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _fsync_dir(path):
    """Durably persist a directory's entries so a rename INTO it is ordered. Used to ORDER the two-file
    commit: `os.replace` makes each rename atomic for its target but does NOT order the two directory-
    entry updates across a crash on a filesystem that doesn't order metadata implicitly (macOS/APFS — a
    first-class substrate). An unordered crash could persist the checkpoint rename before the manifest
    rename → OLD manifest + NEW checkpoint = the unrecoverable checkpoint-ahead wedge (ADR-0037 §11.1).

    On macOS `os.fsync` (fsync(2)) does NOT flush the drive's volatile cache to stable media — only
    F_FULLFSYNC does — so under POWER LOSS (not just a process crash) plain fsync would not guarantee the
    manifest rename reached the platter before the checkpoint rename. Prefer F_FULLFSYNC where present
    (macOS), fall back to fsync (Linux, where fsync reaches stable media and the journal orders metadata).
    (Distinct from losing an append, which is benign: this barrier orders the two renames, so the
    crash/power-loss window stays forward-recoverable.)"""
    fd = os.open(path, os.O_RDONLY)
    try:
        if hasattr(fcntl, 'F_FULLFSYNC'):
            try:
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)  # true barrier to stable media on macOS
                return
            except OSError:
                pass  # unsupported on this fd/fs → fall back to fsync
        os.fsync(fd)
    except OSError:
        pass  # directory fsync unsupported on some filesystems; best-effort ordering barrier
    finally:
        os.close(fd)


def _write_manifest_and_checkpoint(med, manifest_bytes, records):
    """Crash-safe, manifest-first: replace MANIFEST (atomic), fsync the dir to ORDER it ahead of the
    checkpoint, then replace MANIFEST.checkpoint. A crash between the two can only leave NEW-manifest /
    OLD-checkpoint (forward-recoverable via prefix_finalize) — never OLD-manifest / NEW-checkpoint (the
    unrecoverable checkpoint-ahead wedge), even on a filesystem that doesn't order metadata implicitly."""
    cp = schema.compute_checkpoint(manifest_bytes, records)
    _atomic_write(os.path.join(med, 'MANIFEST'), manifest_bytes)
    _fsync_dir(med)  # ordering barrier: manifest rename durable BEFORE the checkpoint rename
    _atomic_write(os.path.join(med, 'MANIFEST.checkpoint'),
                  (json.dumps(cp, sort_keys=True) + '\n').encode('utf-8'))
    _fsync_dir(med)


def _open_lock(med):
    """Open (creating) the per-ledger exclusive lock, REFUSING a symlinked lock path — the one path
    component the writer otherwise left unguarded. A plain O_CREAT open follows a symlinked lock,
    creating an arbitrary target file and flock'ing a foreign inode (defeating mutual exclusion). An
    islink pre-check plus O_NOFOLLOW (which fails ELOOP on a final-component symlink) closes the TOCTOU.
    Returns the lock fd or raises AppendStop (category only)."""
    lock_path = os.path.join(med, 'MANIFEST.lock')
    if os.path.islink(lock_path):
        raise AppendStop('MANIFEST.lock is a symlink')
    try:
        return os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        raise AppendStop('MANIFEST.lock could not be opened safely (symlink or race)')


def _relevant_findings(findings, handle):
    """Split verify_tree findings into (global, this-patient). Matched NFC-INSENSITIVELY: the verifier
    stamps each Finding with the raw on-disk dirent, which on a normalization-preserving filesystem is
    NFD while the operator `handle` is forced NFC — a byte-exact `f.handle == handle` would silently
    drop this patient's findings and let the gate pass onto a RED tree (macOS/APFS)."""
    handle_nfc = unicodedata.normalize('NFC', handle)
    globals_ = [f for f in findings if f.handle is None]
    mine = [f for f in findings if f.handle is not None
            and unicodedata.normalize('NFC', f.handle) == handle_nfc]
    return globals_, mine


def _projected_findings(root, handle, manifest_bytes, records):
    """Run L13 against the PROJECTED manifest for `handle` WITHOUT writing it (the pre-publish gate).
    Returns (global findings, this-patient findings). The projected append is committed only when it
    verifies green, so the ledger is never written into a red state and no destructive rollback exists."""
    findings, _ = fsverify.verify_tree(root, manifest_override={handle: (manifest_bytes, records)})
    return _relevant_findings(findings, handle)


def _pending_note(root, handle, manifest_bytes, records, rerun):
    """The lines a refusal adds when files in this person's med/sources are not logged yet and the call
    did not name them: the files, the warning that one may be another session's, and the one `add` call
    that logs them all together (a pending file's own `.ocr.md` is bound by that same `add`). Reads the
    folder as it is now, before the refused op. Names follow the locator rule — a private-mode person's
    print as placeholders. The call is printed only when nothing else is red: with another kind pending
    too (a late transcription, a changed source) no single call is clean, and the sources README says
    what to do. `rerun` is (relpaths, confirmed, identity_source) of a refused `add`, else None: its
    own files go into the call, its attestation never — `confirm` follows for the files it named.
    '' when no file beyond the caller's own is pending."""
    own, confirmed, source = rerun if rerun else ([], False, None)
    own = [own] if isinstance(own, str) else [r for r in own if isinstance(r, str)]
    named = {unicodedata.normalize('NFC', r) for r in own}
    findings = [f for part in _projected_findings(root, handle, manifest_bytes, records) for f in part]
    pending = sorted({f.relpath for f in findings
                      if f.category == fsverify.UNLOGGED_SOURCE and isinstance(f.relpath, str)})
    extra = [r for r in pending if r not in named]
    if not extra:
        return ''
    sidecars = {os.path.splitext(r)[0] + _OCR_SUFFIX for r in pending}
    clean = all(f.category == fsverify.UNLOGGED_SOURCE
                or (f.category == fsverify.UNBOUND_TRANSCRIPTION and f.relpath in sidecars)
                for f in findings)
    where = fsverify.locator(root, handle, None, fsverify.private_mode_in_use(root))
    show = (where not in (fsverify.WITHHELD_PRIVATE, fsverify.WITHHELD_UNKNOWN)
            and not any(_CONTROL_RE.search(r) for r in own + extra))
    head = 'Not logged yet in this person\'s med/sources'
    if show:
        lines = [head + ' (%d):' % len(extra)] + ['  ' + r for r in extra]
        who = shlex.quote(unicodedata.normalize('NFC', handle))
        rels = ' '.join('--relpath ' + shlex.quote(r) for r in own + extra)
    else:
        lines = [head + ': %d (names withheld).' % len(extra)]
        who, rels = '<handle>', '--relpath <file> ... (every file, yours too)'
    lines.append('If any of them belongs to another session that is still filing it, wait for that '
                 'session to finish instead.')
    if clean:
        # never an attestation on files the caller did not name: the combined call records every file
        # unverified, and `confirm` (one file per call) attests only the caller's own
        lines += ['Otherwise log all of them together in one call (all are written or none)'
                  + ('' if own else ', then run this call again') + ':',
                  '  python3 -m tools.person_ownership --root . append %s add %s' % (who, rels)]
        if confirmed or source:
            lines.append('The other files\' owners have not been confirmed in this session, so that call '
                         'records every file unverified; '
                         + ('then confirm only the files you named, one call each:' if confirmed
                            else 'your --identity-source is not carried onto it.'))
        if confirmed:
            if show:
                tail = ' --identity-source ' + shlex.quote(source) if source else ''
                lines += ['  python3 -m tools.person_ownership --root . append %s confirm --relpath %s%s'
                          % (who, shlex.quote(r), tail) for r in own]
            else:
                lines.append('  python3 -m tools.person_ownership --root . append <handle> confirm '
                             '--relpath <each file you named, one call each>')
    else:
        lines.append('Something else is pending too (a late transcription, a changed or moved source), '
                     'so no single call settles everything yet: see the sources README, late '
                     'transcriptions.')
    return '\n' + '\n'.join(lines)


def _locked_apply(root, handle, build, rerun=None):
    """Take the per-person MANIFEST lock, load the finalized state, build the new record(s), append
    them, and re-verify. Commit only if the result is L13-green for this patient (and no global
    finding); otherwise refuse, writing nothing. `rerun` is only what a refusal's note needs (see
    `_pending_note`)."""
    handle = _check_handle(root, handle)
    med = _med(root, handle)
    pdir = os.path.join(root, 'patients', handle)
    if os.path.islink(pdir) or not os.path.isdir(pdir):
        raise AppendStop('no such patient directory (or it is a symlink)')
    if not os.path.isdir(med) or os.path.islink(med):
        raise AppendStop('no med/ directory for this person (or it is a symlink)')
    profile = os.path.join(pdir, 'profile.md')
    if os.path.islink(profile):  # never read person-id / private-mode marker through a symlinked profile
        raise AppendStop('profile.md is a symlink')
    if os.path.lexists(profile) and not os.path.isfile(profile):
        # A non-regular profile.md (FIFO/device — a botched restore) would BLOCK the read below while
        # the exclusive MANIFEST lock is held, hanging this writer and stalling any concurrent
        # appender/finalizer. Refuse fast, before the lock (mirrors the L13 verifier's guard).
        raise AppendStop('profile.md is not a regular file')
    lock_fd = _open_lock(med)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        manifest_bytes, records = _load_consistent(med)
        person_id = read_person_id(profile)
        if person_id is None:
            raise AppendStop('no single canonical person record id in profile.md')

        new_records = build(root, handle, person_id, records)
        for r in new_records:
            r_errs = schema.validate_record(r)
            if r_errs:
                raise AppendStop('constructed record failed schema validation')
            if r.get('person_record_id') != person_id:
                raise AppendStop('constructed record person id does not match profile')
        if is_private_mode(profile):
            _assert_no_residue(profile, new_records)
        _, sup_errs = schema.supersession_errors(records + new_records)
        if sup_errs:
            raise AppendStop('append would break the supersession graph (fork/forward-ref)')

        new_bytes = manifest_bytes + b''.join(_line(r) for r in new_records)
        all_records = records + new_records
        # Verify the PROJECTED state BEFORE writing anything — commit only if it is L13-green for this
        # patient (and no global finding). A rejected append writes NOTHING, so the prior blessed
        # MANIFEST+checkpoint stay intact: no destructive rollback, hence no rollback-crash window. If
        # verify_tree itself raises it propagates here, before any write (fail closed).
        globals_, mine = _projected_findings(root, handle, new_bytes, all_records)
        if globals_ or mine:
            cats = sorted({f.category for f in (globals_ + mine)})
            raise AppendStop('append would leave L13 red (' + '; '.join(cats)
                             + '); nothing written — resolve the tree first'
                             + _pending_note(root, handle, manifest_bytes, records, rerun))
        _write_manifest_and_checkpoint(med, new_bytes, all_records)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _assert_no_residue(profile, new_records):
    """Private-mode: no identifier-shaped residue may enter scanned free-text fields (source_relpath,
    identity_source, derivative paths). Fail closed BEFORE writing rather than tripping L10/L13 after.
    The shape is the person's (ADR-0062); a number tag that cannot be read refuses too."""
    try:
        shape = residue_re(person_scheme_keys(profile))
    except ValueError as e:
        raise AppendStop('private-mode: ' + str(e) + ' (refused)')
    for r in new_records:
        vals = [r.get('source_relpath'), r.get('identity_source')]
        for d in (r.get('derivatives') or []):
            if isinstance(d, dict):
                vals.append(d.get('derivative_relpath'))
        if any(isinstance(v, str) and shape.search(v) for v in vals):
            raise AppendStop('private-mode: identifier-shaped residue in a new record field (refused)')


# --------------------------------------------------------------------------------------------------
# Public operations — each bakes `today` into the build closure, then runs the locked transaction.
# --------------------------------------------------------------------------------------------------
def add_source(root, handle, relpath, confirmed=False, identity_source=None, today=None):
    """Add one source, or a list of them in one locked append (§14)."""
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_add(ro, h, pid, recs, relpath, confirmed, identity_source, t),
                  rerun=(relpath, confirmed, identity_source))


def confirm(root, handle, relpath, identity_source=None, today=None):
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_confirm(ro, h, pid, recs, relpath, identity_source, t))


def rename(root, handle, old_relpath, new_relpath, identity_source=None, today=None):
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_rename(ro, h, pid, recs, old_relpath, new_relpath, identity_source, t))


def rehash(root, handle, relpath, identity_source=None, today=None):
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_rehash(ro, h, pid, recs, relpath, identity_source, t))


def wrong_owner(root, handle, relpath, identity_source=None, today=None):
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_wrong_owner(ro, h, pid, recs, relpath, identity_source, t))


def retranscribe(root, handle, relpath, today=None):
    """Re-bind one corrected transcription, or a list of them in one locked append (§13/§14)."""
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_retranscribe(ro, h, pid, recs, relpath, t))


def transcribe(root, handle, relpath, today=None):
    """Bind one first transcription, or a list of them in one locked append (§14)."""
    t = _today(today)
    _locked_apply(root, handle, lambda ro, h, pid, recs:
                  _build_transcribe(ro, h, pid, recs, relpath, t))


def split(*a, **k):
    _build_split()


# --------------------------------------------------------------------------------------------------
# Person-scoped first ledger (ADR-0037 §12) — `migrate`'s initial write, for ONE person
# --------------------------------------------------------------------------------------------------
def _ledger_refusal(med):
    """None when this person has no ledger state at all; else why `init` must refuse. Any directory
    entry counts (lexists: a dangling or wrong-type node is prior state too). Category only."""
    manifest = os.path.join(med, 'MANIFEST')
    has_m = os.path.lexists(manifest)
    has_c = os.path.lexists(os.path.join(med, 'MANIFEST.checkpoint'))
    if has_m and has_c:
        return ('this person already has a ledger (an empty one counts) — register sources with '
                '`append <handle> add`; nothing written')
    if has_m and (os.path.islink(manifest) or not os.path.isfile(manifest)):
        return 'MANIFEST is a symlink or not a regular file — resolve it by hand; nothing written'
    if has_m:
        return _checkpointless(med) + '; nothing written'
    if has_c:
        return 'a checkpoint without a MANIFEST is prior ownership state; nothing written'
    return None


def init_ledger(root, handle, today=None):
    """Create ONE person's first ledger — whole-tree `migrate`'s initial write, scoped to
    patients/<handle>/ and nothing else. Mints the Person record ID only if the profile has none,
    derives the records for the sources already on disk with migrate's own `build_records` (so they
    are exactly what `migrate` would write for this person), and then takes the append writer's
    path: the per-person lock, the projected L13 verify, the manifest-first forward write.

    Refuses, writing nothing and creating no file, when any MANIFEST or checkpoint entry exists: an
    existing ledger, even an empty one, is extended only through `append`. A refusal after the lock
    is taken leaves the lock file; one at the projected verify also leaves a freshly minted ID in
    the profile — the same two leftovers as `append` and `migrate`, both green."""
    t = _today(today)
    handle = _check_handle(root, handle)
    med = _med(root, handle)
    pdir = os.path.join(root, 'patients', handle)
    if os.path.islink(pdir) or not os.path.isdir(pdir):
        raise AppendStop('no such patient directory (or it is a symlink)')
    if not os.path.isdir(med) or os.path.islink(med):
        raise AppendStop('no med/ directory for this person (or it is a symlink)')
    profile = os.path.join(pdir, 'profile.md')
    if os.path.islink(profile) or not os.path.isfile(profile):
        raise AppendStop('profile.md is missing, a symlink, or not a regular file')
    refusal = _ledger_refusal(med)
    if refusal:
        raise AppendStop(refusal)
    lock_fd = _open_lock(med)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        refusal = _ledger_refusal(med)   # re-checked under the lock: a concurrent writer may have won
        if refusal:
            raise AppendStop(refusal)
        person_id = read_person_id(profile)
        mint = person_id is None
        if mint:
            person_id = secrets.token_hex(16)
        try:
            records = build_records(root, handle, person_id, today=t)
            if is_private_mode(profile):
                _assert_no_residue(profile, records)
            if mint:
                _write_person_id(root, handle, person_id)   # refuses an ambiguous/misplaced field
        except MigrationStop as e:
            raise AppendStop(str(e))
        manifest_bytes = b''.join(_line(r) for r in records)
        globals_, mine = _projected_findings(root, handle, manifest_bytes, records)
        if globals_ or mine:
            cats = sorted({f.category for f in (globals_ + mine)})
            raise AppendStop('init would leave L13 red (' + '; '.join(cats)
                             + '); no ledger written — resolve the tree first')
        _write_manifest_and_checkpoint(med, manifest_bytes, records)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# --------------------------------------------------------------------------------------------------
# Prefix-validating finalizer / crash recovery (replaces the disabled blind refresh)
# --------------------------------------------------------------------------------------------------
_CHANGED_BY_A_LAYER_OP = frozenset({'record_id', 'derivatives', 'supersedes', 'supersede_reason',
                                    'supersede_date'})


def _layer_row_errors(r, old, op, today):
    """What a `transcribe` or `retranscribe` row may change: its id, its transcription and its
    supersession fields — every other field is the superseded row's — dated between that row's last
    ledger date and today (§14: a backdated row would date new text before a kept detail was recorded)."""
    if any(r.get(k) != old.get(k) for k in schema.RECORD_FIELDS - _CHANGED_BY_A_LAYER_OP):
        return ['%s suffix must carry every other field of the row it supersedes' % op]
    when = r.get('supersede_date')
    if not (isinstance(when, str) and _last_ledger_date(old) <= when <= today):
        return ['%s suffix is dated before the row it supersedes or after today' % op]
    return []


def _retranscribe_suffix_errors(root, handle, records, r, old, today):
    """A `retranscribe` row keeps the original's path, bytes and identity status, binds exactly one
    transcription, that file carries the new erratum line `_build_retranscribe` requires, and the
    row's recorded erratum count is the file's (the projected L13 check proves the binding itself).
    One writer call may leave several rows; each is checked against the file as it is now, failing
    closed."""
    new_d = [d for d in (r.get('derivatives') or []) if isinstance(d, dict)]
    if r.get('source_relpath') != old.get('source_relpath') or r.get('sha256') != old.get('sha256'):
        return ['retranscribe suffix must keep the original\'s path and bytes']
    if (r.get('identity_status'), r.get('identity_reviewer')) != (old.get('identity_status'),
                                                                   old.get('identity_reviewer')):
        return ['retranscribe suffix must not change the identity status']
    if len(new_d) != 1:
        return ['retranscribe suffix must bind exactly one transcription']
    try:
        data = _read_transcription(root, handle, new_d[0].get('derivative_relpath'))
    except (AppendStop, OSError):
        return ['retranscribe suffix: the bound transcription cannot be read']
    count, problem = _erratum_check(data, _last_ledger_date(old), r.get('supersede_date') or '',
                                    _bound_errata_count(records, old))
    if problem:
        return ['retranscribe suffix: the transcription carries no new erratum line for it']
    if new_d[0].get(schema.ERRATA_COUNT_FIELD) != count:
        return ['retranscribe suffix: its erratum count is not the transcription\'s']
    return _layer_row_errors(r, old, 'retranscribe', today)


def _transcribe_suffix_errors(r, old, today):
    """A `transcribe` row keeps the original's path, bytes and identity status, follows a row that
    bound no transcription, and binds exactly the `.ocr.md` with the original's name stem (the
    projected L13 check proves its hash and the pair)."""
    new_d = [d for d in (r.get('derivatives') or []) if isinstance(d, dict)]
    if r.get('source_relpath') != old.get('source_relpath') or r.get('sha256') != old.get('sha256'):
        return ['transcribe suffix must keep the original\'s path and bytes']
    if (r.get('identity_status'), r.get('identity_reviewer')) != (old.get('identity_status'),
                                                                   old.get('identity_reviewer')):
        return ['transcribe suffix must not change the identity status']
    if old.get('derivatives'):
        return ['transcribe suffix follows a row that already binds a transcription']
    rel = old.get('source_relpath')
    if len(new_d) != 1 or not isinstance(rel, str) or new_d[0].get('derivative_relpath') != _ocr_beside(rel):
        return ['transcribe suffix must bind exactly the transcription beside the original']
    return _layer_row_errors(r, old, 'transcribe', today)


def _suffix_semantic_errors(records, n, root, handle, today):
    """The op builders' SEMANTIC invariants, re-checked over the un-checkpointed suffix (records[n:]).
    Structural L13 proves bytes/binding but not op semantics, so without this a HAND-APPENDED suffix
    the writer would refuse — e.g. `operator-confirmed` riding onto substituted bytes via a forged
    'status-change'/'rename' row — would be re-blessed by finalize. Category-only errors.

    Per superseding suffix record, mirroring _build_confirm/_build_rename/_build_rehash/
    _build_wrong_owner/_build_retranscribe: status-change = same path + same bytes; rename = new path
    + SAME bytes (both carry the transcription hashes unchanged); rehash = same path + changed bytes
    + confirmed DROPS (never carries); wrong-owner =
    same bytes + no derivatives; retranscribe = same path, bytes and status + one transcription
    carrying its new erratum line, its count recorded truly (read from the tree); transcribe = same
    path, bytes and status + the one transcription beside the original, after none (both layer ops
    carry every other field and are dated between the row they supersede and today). No row may
    supersede a wrong-owner retraction. Any other reason is not a writer op. Fresh adds (supersedes=='') are the CLI's own capability (add [--confirmed])
    — nothing to re-check beyond L13."""
    by_id = {r.get('record_id'): r for r in records}
    errs = []
    for r in records[n:]:
        sup = r.get('supersedes', '')
        if not sup:
            continue
        old = by_id.get(sup)
        if old is None:
            errs.append('suffix supersedes an unknown record')  # schema graph also refuses this
            continue
        if fsverify._is_retraction(old):
            # no writer op supersedes a retraction (the active view drops it): a row that does would
            # bring a source moved to its true owner back into this person's record (§14)
            errs.append('suffix supersedes a wrong-owner retraction')
            continue
        reason = r.get('supersede_reason', '')
        same_path = r.get('source_relpath') == old.get('source_relpath')
        same_bytes = r.get('sha256') == old.get('sha256')
        confirmed = r.get('identity_status') == 'operator-confirmed'
        old_confirmed = old.get('identity_status') == 'operator-confirmed'
        same_layer = _derivative_hashes(r) == _derivative_hashes(old)
        if reason == 'status-change':
            if not (same_path and same_bytes):
                errs.append('status-change suffix must keep path and bytes (confirm attests the '
                            'SUPERSEDED bytes, not substituted content)')
            elif not same_layer:
                errs.append('status-change suffix must carry the transcription unchanged '
                            '(a corrected one is a retranscribe)')
        elif reason == 'rename':
            if same_path or not same_bytes:
                errs.append('rename suffix must move the path and keep the bytes identical')
            elif not same_layer:
                errs.append('rename suffix must carry the transcription unchanged '
                            '(a corrected one is a retranscribe)')
        elif reason == 'rehash':
            if not same_path or same_bytes:
                errs.append('rehash suffix must keep the path and change the bytes')
            elif old_confirmed and confirmed:
                errs.append('rehash suffix carries operator-confirmed onto changed bytes '
                            '(the writer drops it; re-confirm required)')
        elif reason == 'wrong-owner':
            if not same_bytes or r.get('derivatives'):
                errs.append('wrong-owner suffix must retract the superseded bytes with no derivatives')
        elif reason == 'retranscribe':
            errs.extend(_retranscribe_suffix_errors(root, handle, records, r, old, today))
        elif reason == 'transcribe':
            errs.extend(_transcribe_suffix_errors(r, old, today))
        else:
            errs.append('suffix supersession reason is not a writer operation')
    return errs


def prefix_finalize(root, handle, today=None):
    """Re-bless MANIFEST.checkpoint to the current MANIFEST **iff** the checkpointed bytes are the
    exact byte prefix of the (strictly-or-equally longer) valid on-disk ledger. This is the ADR-0037
    §10 requirement-1 proof made executable: it advances the checkpoint after a crash between the two
    replaces, but CANNOT re-bless an in-place rewrite (a mutated prefix fails the byte-prefix hash).

    Fails closed (AppendStop) on: symlinks, unparseable/invalid ledger, a shorter manifest than the
    checkpoint, or a broken prefix. No source byte is touched."""
    handle = _check_handle(root, handle)
    med = _med(root, handle)
    pdir = os.path.join(root, 'patients', handle)
    # Same containment guards as _locked_apply: a valid handle STRING is not enough — a symlinked
    # patient/med DIRECTORY would let finalize read and re-bless a ledger OUTSIDE the jail. _check_handle
    # catches a traversal string; these catch a symlinked directory on the recovery path.
    if os.path.islink(pdir) or not os.path.isdir(pdir):
        raise AppendStop('no such patient directory (or it is a symlink)')
    if os.path.islink(med) or not os.path.isdir(med):
        raise AppendStop('no med/ directory for this person (or it is a symlink)')
    manifest_path = os.path.join(med, 'MANIFEST')
    checkpoint_path = os.path.join(med, 'MANIFEST.checkpoint')
    if os.path.islink(manifest_path) or os.path.islink(checkpoint_path):
        raise AppendStop('MANIFEST or checkpoint is a symlink')
    if not os.path.isfile(manifest_path):
        raise AppendStop('no MANIFEST to finalize')
    if not os.path.isfile(checkpoint_path):
        raise AppendStop('no MANIFEST.checkpoint to validate the prefix against')
    lock_fd = _open_lock(med)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        with open(manifest_path, 'rb') as f:
            manifest_bytes = f.read()
        try:
            records = schema.parse_manifest_bytes(manifest_bytes)
        except schema.ManifestError as e:
            raise AppendStop('MANIFEST unparseable (' + str(e) + ')')
        errs = []
        for r in records:
            errs.extend(schema.validate_record(r))
        _, sup_errs = schema.supersession_errors(records)
        if errs or sup_errs:
            raise AppendStop('MANIFEST is not schema/graph valid; refusing to finalize')
        try:
            with open(checkpoint_path, 'rb') as f:
                cp = schema.parse_checkpoint_bytes(f.read())
        except (OSError, ValueError, UnicodeDecodeError):
            raise AppendStop('checkpoint unreadable/unparseable')
        if schema.validate_checkpoint_shape(cp):
            raise AppendStop('checkpoint malformed')
        n = cp['record_count']
        if len(records) < n:
            raise AppendStop('MANIFEST is shorter than its checkpoint (truncation, not an append)')
        # True stored prefix bytes: the first n record lines exactly as on disk (no re-serialization).
        # parse_manifest_bytes guarantees newline-terminated, one complete object per line.
        import hashlib
        lines = manifest_bytes.split(b'\n')  # trailing '' after the final newline
        prefix_bytes = b'\n'.join(lines[:n]) + (b'\n' if n else b'')
        if hashlib.sha256(prefix_bytes).hexdigest() != cp['manifest_sha256']:
            raise AppendStop('checkpointed prefix does not match the MANIFEST (in-place rewrite refused)')
        tail_expected = records[n - 1].get('record_id') if n else ''
        if cp['tail_record_id'] != (tail_expected if isinstance(tail_expected, str) else ''):
            raise AppendStop('checkpoint tail does not match the prefix tail (refused)')
        sem_errs = _suffix_semantic_errors(records, n, root, handle, _today(today))
        if sem_errs:
            raise AppendStop('finalize refused: suffix violates writer op semantics ('
                             + '; '.join(sorted(set(sem_errs))) + ')')
        # Enforce the "re-bless of an ALREADY-verified append" guarantee (ADR-0037 §11.1): the recovered
        # ledger must be L13-green as a PROJECTED state (reusing the overlay — the stale on-disk
        # checkpoint is skipped). A crashed append was verify-before-published, so this passes; a
        # hand-appended suffix that never passed verify_tree (binding/drift/residue) is refused here
        # instead of blessed. The prefix hash above already refuses an in-place rewrite of the prefix.
        findings, _ = fsverify.verify_tree(root, manifest_override={handle: (manifest_bytes, records)})
        globals_, mine = _relevant_findings(findings, handle)
        if globals_ or mine:
            cats = sorted({f.category for f in (globals_ + mine)})
            raise AppendStop('finalize refused: ledger is not L13-green (' + '; '.join(cats)
                             + ') — resolve the tree first')
        _write_manifest_and_checkpoint(med, manifest_bytes, records)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
