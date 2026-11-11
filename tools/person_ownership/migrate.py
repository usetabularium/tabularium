#!/usr/bin/env python3
"""Deterministic migration / inventory (ADR-0037, Option B). No LLM inference, no clinical-content
reads, NO source-byte changes. Legacy evidence defaults to `legacy-folder-only`. NFD->NFC path
renames precede the byte-exact record so day-one RED can never be an encoding artifact.

stdout is aggregate/category only — never a patient handle, path, hash, person id, or count that
would fingerprint a family. The detailed pre/post `relpath + sha256` inventory is written only to a
LOCAL file inside the PII boundary (never tracked, never stdout)."""
import datetime
import fcntl
import hashlib
import json
import os
import secrets
import stat
import unicodedata

from . import schema
from .fsverify import (read_person_id, _read_person_id_state, _sha256_file, _BOILERPLATE,
                       _OCR_SUFFIX, _is_cruft_name)


class MigrationStop(Exception):
    """A stop condition (ADR-0037 / HO-10): an ambiguous derivative, an existing manifest to
    overwrite, a byte-integrity failure, or anything that would invent certainty. Category only."""


def _walk_stop(err):
    """os.walk onerror hook: an unlistable directory under med/sources must STOP the migration, not
    silently shrink the inventory (os.walk's default swallows the error; 2026-08-23 audit)."""
    raise MigrationStop('unreadable directory under med/sources (fail closed)')


def _today():
    return datetime.date.today().isoformat()


def _acquired_date_from_name(name):
    """L6 source names lead with YYYY-MM-DD. Use that as the (provisional) acquisition date; None if
    the name is not L6-dated."""
    if len(name) >= 10 and name[4] == '-' and name[7] == '-' and name[:4].isdigit() \
            and name[5:7].isdigit() and name[8:10].isdigit():
        try:
            datetime.date(int(name[:4]), int(name[5:7]), int(name[8:10]))
            return name[:10]
        except ValueError:
            return None
    return None


def _patient_source_files(sources_dir):
    """(primary, ocr) lists of (abspath, name, rel_from_patient_root). Excludes boilerplate/hidden.
    Rejects symlinks and non-regular files by raising MigrationStop (migration never records through
    a symlink or opens a FIFO/device/socket while hashing)."""
    pdir = os.path.dirname(os.path.dirname(sources_dir))
    med = os.path.dirname(sources_dir)
    profile = os.path.join(pdir, 'profile.md')
    if any(os.path.islink(p) for p in (pdir, med, sources_dir, profile)):
        raise MigrationStop('symlinked patient/profile/med/sources path')
    if not (os.path.isdir(pdir) and os.path.isdir(med) and os.path.isdir(sources_dir)):
        raise MigrationStop('patient/med/sources path is not a directory')
    if not os.path.isfile(profile):
        raise MigrationStop('profile.md is missing or is not a regular file')
    primary, ocr = [], []
    for dirpath, dirnames, filenames in os.walk(sources_dir, onerror=_walk_stop):
        for dn in dirnames:
            if os.path.islink(os.path.join(dirpath, dn)):
                raise MigrationStop('symlinked directory under med/sources')
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                mode = os.lstat(full).st_mode
            except OSError:
                raise MigrationStop('source file type could not be inspected')
            if stat.S_ISLNK(mode):
                raise MigrationStop('symlinked source file')
            if not stat.S_ISREG(mode):
                raise MigrationStop('non-regular source file')
            if _is_cruft_name(fn):
                continue
            rel = 'med/sources/' + os.path.relpath(full, sources_dir).replace(os.sep, '/')
            if rel == 'med/sources/' + fn and fn in _BOILERPLATE:
                continue
            (ocr if fn.endswith(_OCR_SUFFIX) else primary).append((full, fn, rel))
    return primary, ocr


def _count_non_nfc(sources_dir):
    n = 0
    for dirpath, dirnames, filenames in os.walk(sources_dir, onerror=_walk_stop):
        for fn in filenames:
            if unicodedata.normalize('NFC', fn) != fn:
                n += 1
    return n


def _evidence_inventory(sources_dir):
    """Sorted list of (NFC relpath, sha256) over primary + ocr evidence. Content-only integrity
    basis (ADR-0037 migration integrity = sorted relpath+sha256)."""
    primary, ocr = _patient_source_files(sources_dir)
    inv = []
    for full, name, rel in primary + ocr:
        inv.append((unicodedata.normalize('NFC', rel), _sha256_file(full)))
    return sorted(inv)


def build_records(root, handle, person_id, today=None):
    """Build the legacy-folder-only manifest records for a patient (pure of writes; caller persists).
    Binds each `.ocr.md` 1:1 to the primary source sharing its stem; a derivative with no unambiguous
    single primary -> MigrationStop (never invent a parent)."""
    today = today or _today()
    sources_dir = os.path.join(root, 'patients', handle, 'med', 'sources')
    primary, ocr = _patient_source_files(sources_dir)
    # record NFC relpaths (the on-disk name may be NFD on macOS; `full` stays the real path for
    # hashing). The verifier NFC-normalizes on-disk names to match — no on-disk rename needed.
    primary = [(full, name, unicodedata.normalize('NFC', rel)) for full, name, rel in primary]
    ocr = [(full, name, unicodedata.normalize('NFC', rel)) for full, name, rel in ocr]

    # index primary by stem (name without final extension) within its directory-relative key
    prim_by_stem = {}
    for full, name, rel in primary:
        stem = os.path.splitext(rel)[0]  # rel without final ext; unique per file
        prim_by_stem.setdefault(stem, []).append((full, name, rel))
    # bind ocr derivatives
    derivs_for = {}  # primary rel -> [ {derivative_relpath, derivative_sha256} ]
    for full, name, rel in ocr:
        stem = rel[:-len(_OCR_SUFFIX)]  # strip '.ocr.md'
        matches = prim_by_stem.get(stem)
        if not matches or len(matches) != 1:
            raise MigrationStop('ambiguous or orphan .ocr.md derivative')
        prel = matches[0][2]
        derivs_for.setdefault(prel, []).append(
            {'derivative_relpath': rel, 'derivative_sha256': _sha256_file(full)})

    records = []
    used_ids = set()
    for full, name, rel in sorted(primary, key=lambda t: t[2]):
        rid = secrets.token_hex(8)
        while rid in used_ids:
            rid = secrets.token_hex(8)
        used_ids.add(rid)
        acquired = _acquired_date_from_name(name) or today
        # nominal capture_method for legacy metadata: a text source (a transcription filed as the
        # source-of-record when the original was lost) is 'transcript'; everything else 'scan'.
        capture = 'transcript' if name.lower().endswith(('.md', '.txt')) else 'scan'
        records.append({
            'schema_version': schema.SCHEMA_VERSION, 'record_id': rid, 'person_record_id': person_id,
            'source_relpath': rel, 'sha256': _sha256_file(full), 'acquired_date': acquired,
            'capture_method': capture, 'identity_status': 'legacy-folder-only',
            'identity_reviewer': 'intake-pipeline',
            'identity_source': 'legacy migration ' + today + ' — folder position only, unverified',
            'review_date': today, 'derivatives': derivs_for.get(rel, []),
            'supersedes': '', 'supersede_reason': '', 'supersede_date': ''})
    return records


def _fsync_dir(path):
    """Durably persist a directory's entries — an ordering barrier between the two-file commit's renames
    (mirrors append._fsync_dir). Prefer F_FULLFSYNC (a true barrier to stable media on macOS, where plain
    fsync does not flush the drive cache), fall back to fsync; best-effort where unsupported."""
    fd = os.open(path, os.O_RDONLY)
    try:
        if hasattr(fcntl, 'F_FULLFSYNC'):
            try:
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
                return
            except OSError:
                pass
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _is_pristine_initial_manifest(manifest_path):
    """True iff the manifest is exactly what an INITIAL migration produces: parseable, non-empty, and
    every record is `legacy-folder-only` with no supersession (`supersedes == ''`). Anything else — an
    operator-confirmed record, or any rename/rehash/confirm/wrong-owner supersession row — is
    post-migration work that a re-derive would silently destroy, so it must be surfaced, not re-derived."""
    try:
        with open(manifest_path, 'rb') as f:
            records = schema.parse_manifest_bytes(f.read())
    except (OSError, schema.ManifestError):
        return False
    if not records:
        return False
    # Full per-row schema validation, not just the two pristine fields: a pristine-SHAPED row with a
    # malformed field (e.g. `"derivatives": null`) would otherwise reach _recorded_inventory and die
    # with a raw TypeError instead of the fail-closed surfaced skip (merge red-team 2026-07-19).
    if any(schema.validate_record(r) for r in records):
        return False
    return all(r.get('identity_status') == 'legacy-folder-only' and r.get('supersedes', '') == ''
               for r in records)


def _recorded_inventory(manifest_path):
    """The manifest's own recorded evidence inventory — sorted (relpath, sha256) over every record's
    primary + derivatives — or None if unreadable. Comparison basis against `_evidence_inventory`:
    re-derive is safe ONLY when the two agree byte-for-byte (then the rebuild is deterministic and can
    only discard an L13-unchecked metadata hand-edit). Any disagreement — a recorded source missing on
    disk, drifted bytes, an extra file — is an L13-CHECKED signal the recorded ledger is carrying;
    re-deriving would silently re-bless it (drop the missing record / adopt the drifted hash), erasing
    the exact RED the checkpoint-lost restore scenario most needs. Surface those instead."""
    try:
        with open(manifest_path, 'rb') as f:
            records = schema.parse_manifest_bytes(f.read())
    except (OSError, schema.ManifestError):
        return None
    inv = []
    for r in records:
        inv.append((unicodedata.normalize('NFC', r.get('source_relpath', '')), r.get('sha256', '')))
        for d in r.get('derivatives', []):
            inv.append((unicodedata.normalize('NFC', d.get('derivative_relpath', '')),
                        d.get('derivative_sha256', '')))
    return sorted(inv)


def write_manifest(root, handle, records):
    """Atomically write the MANIFEST (JSONL, NFC, newline-terminated) + its untracked checkpoint.
    Refuses to overwrite an existing MANIFEST (MigrationStop) — migration is one-shot per patient."""
    med = os.path.join(root, 'patients', handle, 'med')
    manifest_path = os.path.join(med, 'MANIFEST')
    checkpoint_path = os.path.join(med, 'MANIFEST.checkpoint')
    # `exists` is false for a dangling symlink, and `os.replace` below would also clobber an orphan
    # checkpoint. Both are prior ownership state, never migration scratch: refuse either directory
    # entry before writing a byte.
    if os.path.lexists(manifest_path) or os.path.lexists(checkpoint_path):
        raise MigrationStop('MANIFEST or checkpoint already exists (refusing to overwrite)')
    os.makedirs(med, exist_ok=True)
    body = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records)
    data = body.encode('utf-8')
    tmp = manifest_path + '.tmp-%s' % secrets.token_hex(4)
    with open(tmp, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, manifest_path)
    _fsync_dir(med)  # ORDER the manifest rename ahead of the checkpoint rename (see append._fsync_dir):
                     # a crash can then only leave NEW-manifest/OLD-checkpoint (RED, re-derivable), never
                     # OLD-manifest/NEW-checkpoint (the unrecoverable checkpoint-ahead wedge) on APFS.
    cp = schema.compute_checkpoint(data, records)
    tmpc = checkpoint_path + '.tmp-%s' % secrets.token_hex(4)
    with open(tmpc, 'w', encoding='utf-8') as f:
        json.dump(cp, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmpc, checkpoint_path)
    _fsync_dir(med)


def _list_patients(root):
    pdir = os.path.join(root, 'patients')
    if os.path.islink(pdir):
        raise MigrationStop('patients root is symlinked')
    if not os.path.isdir(pdir):
        return []
    return sorted(n for n in os.listdir(pdir)
                  if not n.startswith('.') and os.path.isdir(os.path.join(pdir, n))
                  and not os.path.islink(os.path.join(pdir, n)))


def _patient_evidence_count(root, handle):
    sd = os.path.join(root, 'patients', handle, 'med', 'sources')
    if not os.path.isdir(sd):
        return 0
    p, o = _patient_source_files(sd)
    return len(p) + len(o)


def pilot(root, report_path=None):
    """Dry pilot on the structurally-smallest patient. Stdout exposes only category/queue state; the
    inventory and exact counts stay in a LOCAL report. Writes nothing into a patient tree."""
    patients = _list_patients(root)
    if not patients:
        return {'patients': 0}
    smallest = min(patients, key=lambda h: _patient_evidence_count(root, h))
    sd = os.path.join(root, 'patients', smallest, 'med', 'sources')
    exceptions = []
    nfc_pending = 0
    inv = []
    try:
        if os.path.isdir(sd):
            for dirpath, dirnames, filenames in os.walk(sd, onerror=_walk_stop):
                for fn in filenames:
                    if unicodedata.normalize('NFC', fn) != fn:
                        nfc_pending += 1
            inv = _evidence_inventory(sd)  # note: reads post-any-existing-NFC; pilot does not rename
    except MigrationStop as e:
        exceptions.append(str(e))
    agg = {'patients': len(patients), 'pilot_evidence_files': len(inv),
           'non_nfc_names': nfc_pending, 'exceptions': exceptions}
    if report_path:
        _write_report(root, report_path,
                      {'kind': 'ownership-pilot-inventory', 'note': 'LOCAL ONLY — never track/print',
                       'inventory': inv, 'aggregate': agg})
    return agg


def migrate(root, today=None, report_path=None, mint=True):
    """Deterministically migrate every patient with sources that has no manifest yet: record
    NFC-normalized relpaths for each source as a `legacy-folder-only` record, bind 1:1 `.ocr.md`
    derivatives, write the manifest + untracked checkpoint. NO source byte changes and NO on-disk
    rename (the verifier NFC-normalizes to match). Content-only integrity: the sorted (relpath,
    sha256) inventory is byte-identical before and after. STOPS (raising) rather than inventing
    certainty. Writes only inside the PII boundary; stdout stays aggregate."""
    today = today or _today()
    patients = _list_patients(root)
    per_patient = {}
    full_inventory = {}
    for handle in patients:
        sd = os.path.join(root, 'patients', handle, 'med', 'sources')
        manifest_path = os.path.join(root, 'patients', handle, 'med', 'MANIFEST')
        checkpoint_path = os.path.join(root, 'patients', handle, 'med', 'MANIFEST.checkpoint')
        if not os.path.isdir(sd):
            continue
        if os.path.lexists(manifest_path):
            # Wrong-type nodes are surfaced per patient (never opened, never blocking): a symlinked or
            # non-regular MANIFEST/checkpoint is prior ownership state we refuse to touch, and one
            # patient's broken node must not abort the other patients' migration.
            if os.path.islink(manifest_path) or not os.path.isfile(manifest_path):
                per_patient[handle] = {'skipped': 'manifest is a symlink or non-regular file'}
                continue
            if os.path.lexists(checkpoint_path):
                if os.path.islink(checkpoint_path) or not os.path.isfile(checkpoint_path):
                    per_patient[handle] = {'skipped': 'checkpoint is a symlink or non-regular file'}
                    continue
                per_patient[handle] = {'skipped': 'manifest exists'}
                continue
            # Checkpointless MANIFEST: either a crash during INITIAL migration, or a manifest whose
            # (untracked) checkpoint was lost asymmetrically. RE-DERIVE from the folder ONLY when the
            # manifest is PRISTINE initial-migration shape (all legacy-folder-only, no supersession) —
            # then re-deriving discards a hand-edit L13 does not check (e.g. acquired_date) rather than
            # blessing it, and re-adds a dropped-but-present source. If the manifest carries
            # operator-confirmed records or supersession history (rename/rehash/confirm/wrong-owner),
            # that is post-migration WORK whose checkpoint was lost — silently re-deriving would DESTROY
            # those attestations, so SURFACE it instead (leave RED; the operator restores the checkpoint
            # from backup or resolves manually).
            if not _is_pristine_initial_manifest(manifest_path):
                per_patient[handle] = {'skipped': 'checkpointless manifest carries post-migration '
                                       'history/attestations (checkpoint lost) — not auto-re-derived; '
                                       'restore the checkpoint from backup or resolve manually'}
                continue
            # Pristine is necessary but NOT sufficient: the recorded (relpath, sha256) rows are the
            # authoritative ledger, and re-deriving from the folder would silently adopt whatever is
            # on disk NOW — laundering an L13-CHECKED missing-source or byte-drift RED to GREEN with
            # zero trace. Re-derive ONLY when the recorded inventory equals the folder inventory
            # byte-for-byte (then the rebuild is deterministic: it can only discard an L13-unchecked
            # metadata hand-edit, never an integrity signal).
            try:
                folder_inv = _evidence_inventory(sd)
            except MigrationStop:
                folder_inv = None
            if folder_inv is None or _recorded_inventory(manifest_path) != folder_inv:
                per_patient[handle] = {'skipped': 'checkpointless manifest disagrees with the on-disk '
                                       'evidence (missing/drifted/extra) — not auto-re-derived; restore '
                                       'the checkpoint from backup and investigate the disagreement'}
                continue
            rederive_stale_manifest = manifest_path   # fall through -> re-derive from the folder
        elif os.path.lexists(checkpoint_path):
            per_patient[handle] = {'skipped': 'checkpoint exists without a MANIFEST — refusing to '
                                   'overwrite prior ownership state'}
            continue
        else:
            rederive_stale_manifest = None
        pre = _evidence_inventory(sd)
        non_nfc = _count_non_nfc(sd)
        person_id = read_person_id(os.path.join(root, 'patients', handle, 'profile.md'))
        if person_id is None:
            if not mint:
                raise MigrationStop('no person record id and minting disabled')
            person_id = secrets.token_hex(16)
            _write_person_id(root, handle, person_id)
        records = build_records(root, handle, person_id, today=today)
        # The stale checkpointless manifest is unlinked ONLY now — after every fallible step (profile
        # person-id resolve/mint, record build) has succeeded — so a raise above leaves the old ledger
        # intact on disk (merge red-team 2026-07-19: deleting before the fallible person-id step could
        # destroy the ledger with no rewrite). The remaining window is write_manifest's own
        # tmp+fsync+atomic-replace discipline.
        if rederive_stale_manifest is not None:
            os.remove(rederive_stale_manifest)
        write_manifest(root, handle, records)
        post = _evidence_inventory(sd)
        # content-only integrity: not a single evidence byte moved (only the MANIFEST was written)
        if post != pre:
            raise MigrationStop('evidence inventory changed during migration (must never happen)')
        per_patient[handle] = {'sources': len(records),
                               'derivatives': sum(len(r['derivatives']) for r in records),
                               'non_nfc_names': non_nfc, 'legacy_folder_only': len(records)}
        full_inventory[handle] = post
    agg = {'patients': len(patients),
           'migrated': sum(1 for v in per_patient.values() if 'sources' in v),
           'total_legacy_folder_only': sum(v.get('legacy_folder_only', 0) for v in per_patient.values())}
    if report_path:
        _write_report(root, report_path,
                      {'kind': 'ownership-migration-report', 'note': 'LOCAL ONLY — never track/print',
                       'per_patient': per_patient, 'inventory': full_inventory, 'aggregate': agg})
    return agg


def _write_report(root, report_path, payload):
    """Write cross-patient inventory only below outputs/ownership, never through symlinks and never
    over an existing file. This prevents `--report` from clobbering evidence or creating a tracked
    corpus fingerprint."""
    base = os.path.abspath(os.path.join(root, 'outputs', 'ownership'))
    candidate = report_path if os.path.isabs(report_path) else os.path.join(root, report_path)
    candidate = os.path.abspath(candidate)
    try:
        inside = os.path.commonpath([base, candidate]) == base
    except ValueError:
        inside = False
    if not inside or candidate == base or os.path.dirname(candidate) != base:
        raise MigrationStop('report path must be a new direct child of outputs/ownership')
    root_abs = os.path.abspath(root)
    cur = root_abs
    for part in os.path.relpath(os.path.dirname(candidate), root_abs).split(os.sep):
        cur = os.path.join(cur, part)
        if os.path.lexists(cur) and os.path.islink(cur):
            raise MigrationStop('report path contains a symlink')
    if os.path.lexists(candidate):
        raise MigrationStop('report path already exists (refusing to overwrite)')
    os.makedirs(base, mode=0o700, exist_ok=True)
    os.chmod(base, 0o700)
    tmp = candidate + '.tmp-%s' % secrets.token_hex(4)
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        # Atomic publication without clobber: unlike os.replace(), this fails if another writer
        # claimed the report name after the initial existence check.
        os.link(tmp, candidate)
        os.remove(tmp)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _write_person_id(root, handle, person_id):
    """Insert the canonical Person record ID into profile.md -> Identity if absent (migration output;
    local-only, never staged). Idempotent: refuses to add a second one. Inserts right after the first
    `## Identity` header so it lands in the Identity section (not under Change log); creates that
    section before the first H2 when an older profile lacks it."""
    profile = os.path.join(root, 'patients', handle, 'profile.md')
    ids, misplaced = _read_person_id_state(profile)
    if len(ids) == 1 and not misplaced:
        return
    if ids or misplaced:
        raise MigrationStop('profile person record id field is ambiguous or misplaced')
    line = ('- **Person record ID (local-only integrity key — never prints, never ships; ADR-0037):** '
            '`%s`\n' % person_id)
    with open(profile, encoding='utf-8') as f:
        lines = f.readlines()
    idx = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('## Identity'):
            idx = i + 1
            break
    if idx is None:
        # Older profiles did not have an Identity section. Create it before the first H2 instead of
        # appending the field under Change log, which is structurally misleading.
        idx = next((i for i, ln in enumerate(lines) if ln.startswith('## ')), len(lines))
        lines[idx:idx] = ['## Identity\n', line, '\n']
    else:
        lines.insert(idx, line)
    tmp = profile + '.tmp-%s' % secrets.token_hex(4)
    with open(tmp, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    os.replace(tmp, profile)
