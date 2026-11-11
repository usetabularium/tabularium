#!/usr/bin/env python3
"""
Private mode (ADR-0029) — operator approval / promotion step (handover 04; hardened HO-09).

redact_ids.py takes a run from NEW through AWAITING_OPERATOR: it stages a masked, hash-manifested
redacted set for each document under --redacted/<doc>/ for the operator to eyeball. A clean run of
that script is NOT approval — it must never itself imply the identifier is safely masked. THIS
script performs the final, explicit, recorded step: AWAITING_OPERATOR -> OPERATOR_APPROVED. Only
an OPERATOR_APPROVED artifact (under --approved/<doc>/) may proceed to the mandatory pre-consumption
integrity check. That checker also binds the approval to the current redacted generation; directory
name / approval.json existence alone is never authorization once bytes can change. Programmatic
consumption goes through verify_approved.load_verified_pages(), which verifies and reads in one
integrated step; the standalone CLI check remains diagnostic and is not atomic with a
later consumer reopen.

What it checks before promoting a document (never trust a "successful" prior run alone):
  * the document's manifest.json carries no unresolved document-level error (RENDER_FAILED /
    PAGE_COUNT_MISMATCH / SYMLINK_REJECTED) — never approvable, --accept-flagged or not;
  * no page carries PROCESS_ERROR (no verifiable artifact exists for it) — same, never approvable;
  * the manifest passes the STRICT, VERSIONED schema validator (redact_ids.validate_document_manifest,
    require_awaiting=True): supported schema_version/kind/tool, state == AWAITING_OPERATOR, opaque
    doc id matching the directory, contiguous unique 1..N page set with n_pages == len(pages),
    required hashes/flags/convergence fields, allowed error/flag vocabulary, no unknown fields, and
    no symlinked/extra/missing page artifacts on disk. Unknown schema versions reject CLOSED;
  * every remaining page's raster on disk hashes to EXACTLY what the manifest recorded at
    LOCALLY_PROCESSED time — an artifact that changed since it was eyeballed (edited, corrupted,
    swapped) is REJECTED, never silently approved. This is the "approval-state forgery" defense;
  * a page carrying any other fail-closed flag blocks approval UNLESS the operator passes
    --accept-flagged (which requires an explicit --doc — never a global acknowledgement over every
    discovered document). --accept-flags may additionally pin the EXACT flag set being acknowledged;
    an acknowledgement that does not exactly cover the manifest's current flag set is rejected.

Promotion is atomic, rollback-safe, and non-destructive: pages are copied (not moved — the
AWAITING_OPERATOR set stays in place as the audit trail of what was actually eyeballed) into a fresh
staging directory inside --approved, a self-verifying attestation (approval.json — exact approved
page set + per-page sha256 + source-manifest hash + bindings) is written, then the staged set is
renamed into --approved/<doc>/. A pre-existing --approved/<doc>/ is renamed aside first (never
deleted); if the staging rename then fails, the prior live set is restored (redact_ids._promote_dir).
"""
import argparse, hashlib, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redact_ids as R

# ---- documented exit-status contract ----
EXIT_APPROVED = 0
EXIT_REJECTED_HASH = 20            # artifact hash mismatch vs. manifest -> approval-state forgery defense fired
EXIT_REJECTED_FLAGS = 21           # unresolved hold flag(s) present and not (exactly) acknowledged
EXIT_REJECTED_ERROR = 22           # document/page carries a hard processing error -> never approvable
EXIT_NOTHING_TO_APPROVE = 23       # no manifest.json found under --redacted (nothing to do)
EXIT_REJECTED_SCHEMA = 24          # manifest failed strict versioned schema validation
EXIT_INVALID_INVOCATION = 64


def _iter_manifests(redacted_root, doc=None):
    if doc:
        p = os.path.join(redacted_root, doc, 'manifest.json')
        return [p] if (os.path.isfile(p) and not os.path.islink(p)) else []
    out = []
    try:
        entries = sorted(os.listdir(redacted_root))
    except OSError:
        return out
    for name in entries:
        if name.startswith('.'):
            continue  # .staging / .superseded / .never-api-source-map.json are not documents
        p = os.path.join(redacted_root, name, 'manifest.json')
        if os.path.isfile(p) and not os.path.islink(p):
            out.append(p)
    return out


def approve_one(manifest_path, approved_root, accept_flagged, accept_flags=None):
    doc_dir = os.path.dirname(manifest_path)
    doc = os.path.basename(doc_dir)
    if os.path.islink(manifest_path) or not os.path.isfile(manifest_path):
        # Refuse FIFOs/devices/sockets before open: this helper is also called directly by tests and
        # other local tooling, not only through `_iter_manifests`' regular-file discovery filter.
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_SCHEMA,
                    reason='manifest is a symlink or non-regular file')
    try:
        manifest_bytes = R._read_state_json_bytes(manifest_path)
        man = R._json_load_bytes_strict(manifest_bytes)
    except (OSError, UnicodeError, ValueError, RecursionError):
        # ValueError covers strict JSON/duplicate-key rejection, a non-regular file raced past the
        # pre-check, and the workload bound; RecursionError covers pathological nesting (a
        # documented schema rejection, never an uncaught exit-1 traceback).
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_SCHEMA,
                    reason='manifest unreadable/unparseable/over-bound')

    # 1) hard errors first — never approvable, --accept-flagged or not (distinct, clear rejection).
    # Type-guard every attacker-controlled dereference: a forged non-list `pages` or non-iterable
    # `flags` must fall through to the strict validator (a documented REJECTED_SCHEMA), never crash
    # this pre-check with an uncaught TypeError before the validator that exists to reject it.
    if isinstance(man, dict) and man.get('error'):
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_ERROR,
                    reason='document has an unresolved processing error; never approvable')
    _pages = man.get('pages') if isinstance(man, dict) else None
    if any(isinstance(p, dict) and isinstance(p.get('flags'), list) and 'PROCESS_ERROR' in p['flags']
           for p in (_pages if isinstance(_pages, list) else [])):
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_ERROR,
                    reason='a page hit a processing error (no verifiable artifact); never approvable')

    # 2) STRICT, versioned schema validation (rejects the permissive/forged shapes) before any copy
    serrs = R.validate_document_manifest(man, doc_dir, require_awaiting=True)
    if serrs:
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_SCHEMA,
                    reason='manifest failed strict schema validation (' + serrs[0] + ')')

    pages = man['pages']  # schema guarantees a non-empty, contiguous, well-formed page list
    hold_flags = sorted({f for p in pages for f in p.get('flags', [])})

    # 3) fail-closed flags — narrowed operator acknowledgement (HO-09 item 5)
    if hold_flags:
        if not accept_flagged:
            return dict(doc=doc, ok=False, code=EXIT_REJECTED_FLAGS,
                        reason=str(len(hold_flags)) + ' fail-closed flag kind(s) present; '
                               'review, then approve with --doc + --accept-flagged to accept as-is')
        if accept_flags is not None and set(accept_flags) != set(hold_flags):
            return dict(doc=doc, ok=False, code=EXIT_REJECTED_FLAGS,
                        reason='--accept-flags does not exactly cover the manifest flag set '
                               '(stale/incomplete acknowledgement)')

    # 4) approval-state-forgery defense: every page raster hashes to what the manifest recorded. An
    # unreadable page or a vanish-after-check (TOCTOU) is a documented, path-free rejection — never
    # an uncaught OSError escaping to an exit-1 traceback that would leak the page path.
    for p in pages:
        pf = os.path.join(doc_dir, 'page-%02d.png' % p['page'])
        if os.path.islink(pf) or not os.path.isfile(pf):
            return dict(doc=doc, ok=False, code=EXIT_REJECTED_SCHEMA,
                        reason='page %02d is missing or a symlink' % p['page'])
        try:
            cur = R._sha256_file(pf)
        except OSError:
            return dict(doc=doc, ok=False, code=EXIT_REJECTED_SCHEMA,
                        reason='page %02d unreadable or vanished before hashing' % p['page'])
        if cur != p['sha256']:
            return dict(doc=doc, ok=False, code=EXIT_REJECTED_HASH,
                        reason='artifact hash mismatch on page %d (changed since it was eyeballed)' % p['page'])

    try:
        os.makedirs(approved_root, exist_ok=True)
        os.chmod(approved_root, 0o700)
        stage = tempfile.mkdtemp(prefix='.stage-%s-' % doc, dir=approved_root)
    except OSError:
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_ERROR,
                    reason='could not create the approval staging area')
    try:
        approved_pages = []
        for p in pages:
            src = os.path.join(doc_dir, 'page-%02d.png' % p['page'])
            dst = os.path.join(stage, 'page-%02d.png' % p['page'])
            with open(src, 'rb') as sf, open(dst, 'wb') as df:
                shutil.copyfileobj(sf, df)
            os.chmod(dst, 0o600)
            # verify the COPY too — a torn/short write must not become promotable merely because
            # the source verified a moment earlier (the copy is what a consumer will re-hash).
            if R._sha256_file(dst) != p['sha256']:
                raise RuntimeError('staged copy hash mismatch')
            approved_pages.append(dict(page=p['page'], sha256=p['sha256']))
        attestation = dict(
            schema_version=R.SCHEMA_VERSION, kind='approval-attestation',
            tool='approve_redaction.py', tool_version=R.TOOL_VERSION, doc=doc,
            source_run_id=man['run_id'],
            source_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            approved_utc=R._utcnow(), pages=approved_pages,
            flags_present_at_approval=hold_flags, accepted_flagged=bool(hold_flags))
        R._atomic_write_json(os.path.join(stage, 'approval.json'), attestation)
        final_dir = os.path.join(approved_root, doc)
        superseded = R._promote_dir(stage, final_dir)
    except Exception as e:
        shutil.rmtree(stage, ignore_errors=True)  # tool-owned staging dir; not caller-supplied
        return dict(doc=doc, ok=False, code=EXIT_REJECTED_ERROR,
                    reason='promotion failed (%s)' % type(e).__name__)
    return dict(doc=doc, ok=True, code=EXIT_APPROVED, reason='approved',
                promoted_to=final_dir, superseded_previous=superseded)


def build_arg_parser():
    ap = argparse.ArgumentParser(description='Private mode: operator approval / promotion (ADR-0029)')
    ap.add_argument('--redacted', required=True, help='AWAITING_OPERATOR root written by redact_ids.py')
    ap.add_argument('--approved', required=True, help='OPERATOR_APPROVED destination (model-eligible)')
    ap.add_argument('--doc', default=None,
                    help='approve a single opaque document id (required with --accept-flagged)')
    ap.add_argument('--accept-flagged', action='store_true',
                    help='explicit operator acknowledgement: approve a document even though some '
                         'page(s) carry a fail-closed flag (reviewed and accepted as-is). '
                         'Requires --doc — never a global acknowledgement over every document.')
    ap.add_argument('--accept-flags', default=None,
                    help='comma-set of the EXACT fail-closed flags being acknowledged; if given it '
                         'must exactly cover the manifest flag set, else approval is rejected')
    return ap


def main(argv=None):
    a = build_arg_parser().parse_args(argv)
    if not os.path.isdir(a.redacted):
        print('ABORT (invalid invocation): --redacted does not exist or is not a directory')
        return EXIT_INVALID_INVOCATION
    if os.path.islink(a.redacted) or os.path.islink(a.approved):
        print('ABORT (invalid invocation): --redacted/--approved must not be symlinks (path-ownership boundary)')
        return EXIT_INVALID_INVOCATION
    if a.doc is not None and not R.DOC_ID_RE.match(a.doc):
        print('ABORT (invalid invocation): --doc must be an opaque document id (doc-<16 hex>), not a raw name/path')
        return EXIT_INVALID_INVOCATION
    if (a.accept_flagged or a.accept_flags) and not a.doc:
        print('ABORT (invalid invocation): --accept-flagged/--accept-flags require an explicit --doc '
              '(a global acknowledgement over every discovered document is not allowed)')
        return EXIT_INVALID_INVOCATION
    accept_flags = None
    if a.accept_flags is not None:
        accept_flags = {t.strip() for t in a.accept_flags.split(',') if t.strip()}
        unknown = accept_flags - R.HOLD_FLAGS
        if unknown:
            print('ABORT (invalid invocation): --accept-flags names unknown flag(s); allowed: '
                  + ','.join(sorted(R.HOLD_FLAGS)))
            return EXIT_INVALID_INVOCATION
    # --redacted (source, AWAITING_OPERATOR) and --approved (destination, OPERATOR_APPROVED) must
    # be distinct and non-nested — same rule redact_ids applies to its dirs. Promoting into a tree
    # that aliases or nests the source would let the approved set land under the very set it reads.
    dir_errs = R.distinct_nonnested_errors(dict(redacted=a.redacted, approved=a.approved))
    if dir_errs:
        for e in dir_errs:
            print('ABORT (invalid invocation): ' + e)
        return EXIT_INVALID_INVOCATION

    manifests = _iter_manifests(a.redacted, a.doc)
    if not manifests:
        print('ABORT: no manifest.json found under --redacted' + (' for --doc ' + a.doc if a.doc else '') +
              ' — nothing to approve')
        return EXIT_NOTHING_TO_APPROVE

    # Top-level firewall (parity with redact_ids.main): no unexpected error may escape as an exit-1
    # traceback that could leak a path — approve_one already contains its OSError sites, this is the
    # backstop. Category-only line; nothing was promoted (each approve_one is self-contained).
    try:
        results = [approve_one(m, a.approved, a.accept_flagged, accept_flags) for m in manifests]
    except OSError:
        print('ABORT: an unexpected filesystem error occurred during approval — nothing was approved')
        return EXIT_REJECTED_ERROR
    for r, label in zip(results, R.doc_labels([r['doc'] for r in results])):
        print('  %-24s  %-10s  %s' % (label, 'APPROVED' if r['ok'] else 'REJECTED', r['reason']))

    if all(r['ok'] for r in results):
        print('STATE: OPERATOR_APPROVED (%d document(s)). Next: verify_approved.py with both current '
              '--redacted and --approved roots (diagnostic); programmatic consumption goes through '
              'verify_approved.load_verified_pages().' % len(results))
        return EXIT_APPROVED
    worst = max((r['code'] for r in results if not r['ok']), default=EXIT_REJECTED_ERROR)
    print('STATE: one or more documents were NOT approved (see REJECTED lines above). '
          'No bytes were published into --approved for a rejected document.')
    return worst


if __name__ == '__main__':
    sys.exit(main())
