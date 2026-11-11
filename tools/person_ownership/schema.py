#!/usr/bin/env python3
"""Ownership manifest schema (ADR-0037 v1) — pure validation, no filesystem side effects beyond
reading a manifest's bytes. Metadata only; never touches clinical content.

Manifest encoding: versioned JSON Lines at the extension-less path `patients/<handle>/med/MANIFEST`,
one complete JSON object per line, UTF-8, NFC, append-only. Corrections append a new record that
`supersedes` a prior one — never in-place mutation. The active view = records not superseded by a
later record.

All validation is category-only: error strings name the failure class and a non-secret locator
(the source relpath), NEVER the `person_record_id` (a local-only integrity key that must never
print) and never a source hash."""
import re
import unicodedata

SCHEMA_VERSION = 1

# identity-review statuses (LEAN MVP — collapsed to two; ADR-0037's document-identity-checked and
# bundle-linked are deferred to a v2, added when a real case first needs them). `operator-confirmed`
# = the operator attested this source belongs to this person; `legacy-folder-only` = ownership
# inferred ONLY from folder position (NOT verified — the migration default + the review-queue marker).
STATUSES = ('operator-confirmed', 'legacy-folder-only')
CAPTURE_METHODS = frozenset({'scan', 'photo', 'export', 'transcript'})
REVIEWERS = frozenset({'operator', 'intake-pipeline'})  # no bundle-parent form in the lean schema
# supersede reasons — NOTE: no `dedup-to-shared` (withdrawn under ALT-C); no `bundle-attach` (v2).
# `retranscribe` (ADR-0037 §13) re-binds a corrected `.ocr.md` to its unchanged original;
# `transcribe` (§14) binds a first one written after its original was inventoried.
SUPERSEDE_REASONS = frozenset({'rename', 'rehash', 'status-change', 'wrong-owner', 'split',
                               'retranscribe', 'transcribe'})

_PERSON_ID_RE = re.compile(r'^[0-9a-f]{32}$')          # opaque, 32 lowercase hex; never PII/order-derived
_RECORD_ID_RE = re.compile(r'^[0-9a-f]{8,64}$')        # opaque per-manifest row key
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

RECORD_FIELDS = frozenset({
    'schema_version', 'record_id', 'person_record_id', 'source_relpath', 'sha256',
    'acquired_date', 'capture_method', 'identity_status', 'identity_reviewer', 'identity_source',
    'review_date', 'derivatives', 'supersedes', 'supersede_reason', 'supersede_date'})
DERIVATIVE_FIELDS = frozenset({'derivative_relpath', 'derivative_sha256'})
# A `retranscribe` row's derivative also records how many erratum lines the transcription it binds
# carries (ADR-0037 §13), so the next correction must add to that count. Required there, and
# carried by no other row.
ERRATA_COUNT_FIELD = 'derivative_errata_count'

CHECKPOINT_FIELDS = frozenset({'schema_version', 'manifest_sha256', 'record_count', 'tail_record_id'})


def _is_real_date(s):
    if not (isinstance(s, str) and _DATE_RE.match(s)):
        return False
    y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    import datetime
    try:
        datetime.date(y, m, d)
        return True
    except ValueError:
        return False


def _safe_relpath(p):
    """A patient-root-relative, forward-slash, NFC path that does not escape the root. Returns an
    error-category string, or None if safe. (Symlink/on-disk checks happen in the filesystem verify;
    this is the pure string check.) No `_shared/med/` carve-out exists under ALT-C."""
    if not isinstance(p, str) or not p:
        return 'empty or non-string relpath'
    if '\\' in p or '\x00' in p:
        return 'relpath contains a backslash or NUL'
    if p != unicodedata.normalize('NFC', p):
        return 'relpath is not NFC-normalized'
    if p.startswith('/') or (len(p) > 1 and p[1] == ':'):
        return 'relpath is absolute'
    parts = p.split('/')
    if any(seg in ('', '.', '..') for seg in parts):
        return 'relpath has an empty, "." or ".." component'
    return None


def validate_derivative(d, retranscribe=False):
    """One derivative entry; `retranscribe` says whether its row is a `retranscribe` successor, the
    only row whose derivative carries (and must carry) a positive integer erratum count."""
    errs = []
    if not isinstance(d, dict):
        return ['derivative is not an object']
    fields = (DERIVATIVE_FIELDS | {ERRATA_COUNT_FIELD}) if retranscribe else DERIVATIVE_FIELDS
    if ERRATA_COUNT_FIELD in d and not retranscribe:
        errs.append('derivative carries an erratum count on a row that is not a retranscribe')
    elif set(d) - fields:
        errs.append('derivative has unknown field(s)')
    if fields - set(d):
        errs.append('derivative missing required field(s)')
    count = d.get(ERRATA_COUNT_FIELD)
    if retranscribe and ERRATA_COUNT_FIELD in d and not (type(count) is int and count >= 1):
        errs.append('derivative has a malformed erratum count')
    rp = d.get('derivative_relpath')
    rerr = _safe_relpath(rp)
    if rerr:
        errs.append('derivative ' + rerr)
    if not (isinstance(d.get('derivative_sha256'), str) and _SHA256_RE.match(d.get('derivative_sha256', ''))):
        errs.append('derivative has a malformed sha256')
    return errs


def validate_record(rec):
    """Schema-level validation of one manifest record (no filesystem). Returns a list of
    category-only error strings; empty == structurally valid for schema v1. The source relpath may
    appear in an error (a non-secret local locator); the person_record_id and hashes never do."""
    if not isinstance(rec, dict):
        return ['record is not a JSON object']
    errs = []
    if rec.get('schema_version') != SCHEMA_VERSION:
        errs.append('unknown or unsupported schema_version')
    extra = set(rec) - RECORD_FIELDS
    if extra:
        errs.append('record has unknown field(s)')
    if RECORD_FIELDS - set(rec):
        errs.append('record missing required field(s)')

    if not (isinstance(rec.get('record_id'), str) and _RECORD_ID_RE.match(rec.get('record_id', ''))):
        errs.append('malformed record_id')
    if not (isinstance(rec.get('person_record_id'), str) and _PERSON_ID_RE.match(rec.get('person_record_id', ''))):
        errs.append('malformed person_record_id (must be 32 lowercase hex)')

    rerr = _safe_relpath(rec.get('source_relpath'))
    if rerr:
        errs.append('source_relpath: ' + rerr)
    if not (isinstance(rec.get('sha256'), str) and _SHA256_RE.match(rec.get('sha256', ''))):
        errs.append('malformed sha256')

    if not _is_real_date(rec.get('acquired_date')):
        errs.append('malformed or unreal acquired_date')
    capture_method = rec.get('capture_method')
    if not isinstance(capture_method, str) or capture_method not in CAPTURE_METHODS:
        errs.append('unknown capture_method')

    status = rec.get('identity_status')
    if not isinstance(status, str) or status not in STATUSES:
        errs.append('unknown identity_status')
    reviewer = rec.get('identity_reviewer')
    if not isinstance(reviewer, str) or reviewer not in REVIEWERS:
        errs.append('unknown identity_reviewer')
    identity_source = rec.get('identity_source')
    if not isinstance(identity_source, str):
        errs.append('malformed identity_source')
    elif not identity_source.strip():
        errs.append('identity_source must name the local provenance basis')
    if status == 'operator-confirmed' and reviewer != 'operator':
        errs.append('operator-confirmed requires the operator reviewer')
    if status == 'legacy-folder-only' and reviewer != 'intake-pipeline':
        errs.append('legacy-folder-only requires the intake-pipeline reviewer')
    if not _is_real_date(rec.get('review_date')):
        errs.append('malformed or unreal review_date')

    derivs = rec.get('derivatives')
    if not isinstance(derivs, list):
        errs.append('derivatives is not a list')
    else:
        retranscribe = rec.get('supersede_reason') == 'retranscribe'
        for d in derivs:
            errs.extend(validate_derivative(d, retranscribe))

    sup = rec.get('supersedes')
    reason = rec.get('supersede_reason')
    sdate = rec.get('supersede_date')
    if not isinstance(sup, str):
        errs.append('malformed supersedes')
    elif sup == '':
        if reason not in ('', None) or sdate not in ('', None):
            errs.append('supersede_reason/date set on a non-superseding record')
        if reason != '' or sdate != '':
            errs.append('supersede_reason and supersede_date must be "" when not superseding')
    else:
        if not _RECORD_ID_RE.match(sup):
            errs.append('malformed supersedes reference')
        if not isinstance(reason, str) or reason not in SUPERSEDE_REASONS:
            errs.append('unknown supersede_reason')
        if not _is_real_date(sdate):
            errs.append('malformed or unreal supersede_date')
        if sup == rec.get('record_id'):
            errs.append('record supersedes itself')
    return errs


class ManifestError(Exception):
    """A manifest that cannot even be parsed into records (malformed JSONL / partial final line /
    non-UTF-8). Carries a category only."""


def _object_without_duplicate_keys(pairs):
    """json object_pairs_hook that REJECTS duplicate keys (default json.loads is last-wins, which
    would let a duplicate-key MANIFEST or checkpoint the verifier REDs be silently accepted by any
    other reader). Raises ValueError."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate JSON object key')
        obj[key] = value
    return obj


def parse_checkpoint_bytes(data):
    """Parse MANIFEST.checkpoint bytes into a dict with the SAME duplicate-key rejection the L13
    verifier applies, so every reader of the checkpoint (verifier, append writer, finalizer) agrees
    on what is well-formed. Raises ValueError / UnicodeDecodeError like json.loads; callers catch and
    fail closed."""
    import json
    return json.loads(data.decode('utf-8'), object_pairs_hook=_object_without_duplicate_keys)


def parse_manifest_bytes(data):
    """Parse manifest file BYTES into a list of record dicts. Raises ManifestError (category only)
    on: non-UTF-8, a blank/whitespace-only line, a partial (unterminated) final line, or any line
    that is not exactly one JSON object. Append-only JSONL: the file MUST end with a newline, and
    every line MUST be a complete object — a torn final append (no trailing newline) is a truncation
    signal, not a valid record."""
    import json
    if data == b'':
        return []
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise ManifestError('manifest is not valid UTF-8')
    if not text.endswith('\n'):
        raise ManifestError('manifest does not end with a newline (torn/partial final record)')
    records = []
    for line in text.split('\n')[:-1]:  # drop the trailing '' after the final newline
        if line.strip() == '':
            raise ManifestError('manifest has a blank line')
        try:
            obj = json.loads(line, object_pairs_hook=_object_without_duplicate_keys)
        except (ValueError, RecursionError):
            raise ManifestError('manifest has a line that is not valid JSON')
        if not isinstance(obj, dict):
            raise ManifestError('manifest has a line that is not a JSON object')
        records.append(obj)
    return records


def supersession_errors(records):
    """Structural integrity of the supersession graph over ALL records (N-3), independent of the
    filesystem: unique record_ids; every `supersedes` resolves to an existing EARLIER record; no
    forward reference; no cycle; no two active records superseding the same parent (split active
    successors). Returns (active_records, errors)."""
    errs = []
    ids = [r.get('record_id') for r in records]
    seen = {}
    for i, rid in enumerate(ids):
        if isinstance(rid, str):
            if rid in seen:
                errs.append('duplicate record_id')
            seen[rid] = i
    superseded_by = {}   # parent_id -> list of child indices that supersede it
    for i, r in enumerate(records):
        sup = r.get('supersedes')
        if isinstance(sup, str) and sup != '':
            if sup not in seen:
                errs.append('supersedes references a non-existent record')
            elif seen[sup] > i:
                errs.append('supersedes references a later record (forward reference)')
            superseded_by.setdefault(sup, []).append(i)
    # an inactive record = one that some record supersedes
    inactive = set(superseded_by.keys())
    # forked ledger: ANY record superseded by more than one record makes the active view ambiguous.
    # Checking the fork POINT (>1 superseder) — not "multiple ACTIVE direct successors" — also catches a
    # MULTI-LEVEL fork (A<-B, then B<-C and B<-C'): the prior direct-children-only check missed a
    # transitive fork whose two active heads were not both direct successors of one parent.
    for parent, children in superseded_by.items():
        if len(children) > 1:
            errs.append('a record is superseded by more than one record (forked/ambiguous ledger)')
    # cycle detection over the supersedes edges (child -> parent)
    def _has_cycle():
        color = {}
        def visit(idx):
            color[idx] = 1
            r = records[idx]
            sup = r.get('supersedes')
            if isinstance(sup, str) and sup in seen:
                nxt = seen[sup]
                c = color.get(nxt, 0)
                if c == 1:
                    return True
                if c == 0 and visit(nxt):
                    return True
            color[idx] = 2
            return False
        for i in range(len(records)):
            if color.get(i, 0) == 0:
                if visit(i):
                    return True
        return False
    if _has_cycle():
        errs.append('supersession graph has a cycle')
    # A malformed record id is already a schema error, but must not raise TypeError here when an
    # attacker supplies an unhashable JSON value (array/object). Keep it in the active view so the
    # caller remains fail-closed and can report the ordinary schema finding.
    active = [r for r in records
              if not isinstance(r.get('record_id'), str) or r.get('record_id') not in inactive]
    return active, errs


def compute_checkpoint(manifest_bytes, records):
    """The untracked checkpoint content (ADR-0037 R-4'): schema, whole-manifest sha256, record
    count, and the tail record_id. Any in-place mutation/truncation/append-without-refresh makes
    manifest_sha256 or record_count disagree at verify time -> RED."""
    import hashlib
    tail = records[-1].get('record_id') if records else ''
    return {'schema_version': SCHEMA_VERSION,
            'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'record_count': len(records),
            'tail_record_id': tail if isinstance(tail, str) else ''}


def validate_checkpoint_shape(cp):
    errs = []
    if not isinstance(cp, dict):
        return ['checkpoint is not a JSON object']
    if cp.get('schema_version') != SCHEMA_VERSION:
        errs.append('unknown checkpoint schema_version')
    if set(cp) - CHECKPOINT_FIELDS:
        errs.append('checkpoint has unknown field(s)')
    if CHECKPOINT_FIELDS - set(cp):
        errs.append('checkpoint missing required field(s)')
    if not (isinstance(cp.get('manifest_sha256'), str) and _SHA256_RE.match(cp.get('manifest_sha256', ''))):
        errs.append('malformed checkpoint manifest_sha256')
    rc = cp.get('record_count')
    if not (isinstance(rc, int) and not isinstance(rc, bool) and rc >= 0):
        errs.append('malformed checkpoint record_count')
    if not isinstance(cp.get('tail_record_id'), str):
        errs.append('malformed checkpoint tail_record_id')
    return errs
