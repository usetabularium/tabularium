#!/usr/bin/env python3
"""
Private mode (ADR-0029) — pre-consumption integrity gate. STDLIB ONLY.

`approve_redaction.py` records OPERATOR_APPROVED. But an approved directory can still be tampered
with AFTER approval — a page swapped, edited, deleted, an extra file dropped, a page replaced by a
symlink. A directory name, or the mere existence of approval.json, is therefore NEVER authorization
once the bytes can change. This command is the mandatory deterministic integrity check immediately
before a model/vision pass: it binds the approval to the current redacted generation, refuses a
symlinked directory/approval/page, rejects any on-disk page set that is not exactly the attested one
(missing / extra / stray), and RE-HASHES every page, comparing to the hash approve_redaction sealed
into approval.json.

Two consumption shapes, with different guarantees:
  * `load_verified_pages(...)` — THE supported programmatic consumption API. It verifies and READS
    in one integrated step: every page is opened once (no-follow, no-block), fstat'ed as a regular
    file, read fully under explicit workload bounds, and hashed — and the hash is computed over
    exactly the byte buffer that is returned. Consumed bytes therefore cannot differ from verified
    bytes: they are the same immutable object, with no path reopen anywhere after verification. An
    injected swap at any point either changes what is read (hash mismatch -> rejected) or changes
    only the file AFTER the read (immaterial — the consumer holds the verified buffer). Any future
    in-repo model/vision caller MUST consume through this API.
  * The CLI below — a diagnostic pre-consumption integrity check. It exits before any separate
    consumer reopens the files, so it detects tampering at verification time but cannot make a
    later path reopen atomic. Its exit 0 is necessary, never sufficient, for such a consumer.

Approval authenticity, stated honestly: approval.json (and this gate) detect accidental and
concurrent tampering. They are integrity metadata, NOT an authenticated signature — a same-user
writer who coherently rewrites source, manifest, pages, and approval together is out of scope by
the supported threat model (no external trust anchor exists here, and a MAC whose key sat beside
the writable state would be authentication theater, not authentication).

Workload bounds (fail closed, before/while buffering): approval/manifest JSON size, page count,
per-page bytes, and per-document total bytes — see the MAX_* constants in redact_ids.py. The
total-bytes bound is PER DOCUMENT; load_verified_pages(doc=None) buffers every approved document
at once, so select --doc-style subsets when consuming a large approved root.

Exit-status contract:
  0  every requested document matched its approval and current redacted generation at verification time
  30 approval attestation missing / unreadable / failed strict schema validation
  31 a page's bytes do not match the sealed hash (tamper/swap after approval)
  32 a page file is missing, a symlink, non-regular, or an unexpected/extra file is present
  33 nothing to verify — no approval.json found under --approved (for --doc, if given)
  64 invalid invocation

All output is category only: opaque doc ids and page numbers, never a filename/path/OCR text/digits.
"""
import argparse, hashlib, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redact_ids as R

EXIT_VERIFIED = 0
EXIT_SCHEMA = 30
EXIT_HASH = 31
EXIT_ARTIFACT = 32
EXIT_NOTHING = 33
EXIT_INVALID_INVOCATION = 64


def _iter_approvals(approved_root, doc=None):
    if doc:
        p = os.path.join(approved_root, doc, 'approval.json')
        return [p] if (os.path.isfile(p) and not os.path.islink(p)) else []
    out = []
    try:
        entries = sorted(os.listdir(approved_root))
    except OSError:
        return out
    for name in entries:
        if name.startswith('.'):
            continue  # .staging / .superseded are not approved documents
        p = os.path.join(approved_root, name, 'approval.json')
        if os.path.isfile(p) and not os.path.islink(p):
            out.append(p)
    return out


def verify_one(approval_path, redacted_root, collect_bytes=False):
    """Return dict(doc, ok, code, reason, pages). `pages` is the exact verified page set on success;
    a consumer must use ONLY those pages and never re-derive the set from the directory listing.
    With collect_bytes=True (the load_verified_pages() path) the success dict also carries
    'page_bytes': [{'page', 'sha256', 'data'}, ...] where 'data' is the exact buffer each sealed
    hash was verified against — the CLI check and the integrated consumer share this one code
    path, so the two cannot drift."""
    approved_dir = os.path.dirname(approval_path)
    doc = os.path.basename(approved_dir)
    if os.path.islink(approved_dir):
        return dict(doc=doc, ok=False, code=EXIT_ARTIFACT, reason='approved directory is a symlink', pages=[])
    if os.path.islink(approval_path) or not os.path.isfile(approval_path):
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='approval.json is a symlink or non-regular file', pages=[])
    try:
        app = R._json_load_bytes_strict(R._read_state_json_bytes(approval_path))
    except (OSError, UnicodeError, ValueError, RecursionError):
        # ValueError covers strict JSON/duplicate-key rejection, a non-regular file raced past the
        # pre-check, and the workload bound; RecursionError covers pathological nesting (a
        # documented schema rejection, never an uncaught exit-1 traceback).
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='approval.json unreadable/unparseable/over-bound', pages=[])

    errs = R.validate_approval_attestation(app, approved_dir)
    if errs:
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='approval failed strict schema validation (' + errs[0] + ')', pages=[])

    # Resolve the attestation back to the CURRENT redacted generation. Without this binding, a
    # later FAILED/HOLD rerun could replace --redacted/<doc> while an older approval stayed green.
    # Read the manifest once, validate exactly those bytes, and compare both generation and page set.
    current_doc_dir = os.path.join(redacted_root, doc)
    current_manifest = os.path.join(current_doc_dir, 'manifest.json')
    if (os.path.islink(current_doc_dir) or os.path.islink(current_manifest) or
            not os.path.isdir(current_doc_dir) or not os.path.isfile(current_manifest)):
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='current redacted generation is symlinked or non-regular', pages=[])
    try:
        current_manifest_bytes = R._read_state_json_bytes(current_manifest)
        current = R._json_load_bytes_strict(current_manifest_bytes)
    except (OSError, UnicodeError, ValueError, RecursionError):
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='current redacted manifest is unreadable/unparseable/over-bound', pages=[])
    current_errs = R.validate_document_manifest(current, current_doc_dir, require_awaiting=True)
    if current_errs:
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='current redacted generation is not approvable (' + current_errs[0] + ')', pages=[])
    current_pages = [{'page': p['page'], 'sha256': p['sha256']} for p in current['pages']]
    current_flags = sorted({f for p in current['pages'] for f in p.get('flags', [])
                            if f in R.HOLD_FLAGS})
    if (current['run_id'] != app['source_run_id'] or
            hashlib.sha256(current_manifest_bytes).hexdigest() != app['source_manifest_sha256'] or
            current_pages != app['pages']):
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='approval does not bind the current redacted generation', pages=[])
    if (app['flags_present_at_approval'] != current_flags or
            app['accepted_flagged'] != bool(current_flags)):
        return dict(doc=doc, ok=False, code=EXIT_SCHEMA,
                    reason='approval flag acknowledgement does not bind the current manifest', pages=[])

    page_numbers = [p['page'] for p in app['pages']]
    # exact on-disk artifact set: {approval.json} + attested pages, nothing more/less, no symlinks
    art_errs = R._validate_dir_artifacts(approved_dir, page_numbers, {'approval.json'})
    if art_errs:
        return dict(doc=doc, ok=False, code=EXIT_ARTIFACT,
                    reason='approved artifacts do not match the attestation (' + art_errs[0] + ')', pages=[])

    # RE-HASH every page at the pre-consumption gate — descriptor-based: each page is
    # opened once (no-follow/no-block), fstat'ed regular, read fully under the page/total bounds,
    # and hashed over the read buffer itself. With collect_bytes the SAME buffer is what the
    # consumer receives, so consumed bytes are the verified bytes by construction. An unreadable
    # page or a vanish-after-check (TOCTOU) is a documented, path-free REJECTION — never an
    # uncaught OSError escaping to an exit-1 traceback that would leak the page path.
    page_bytes = []
    total = 0
    for p in app['pages']:
        pf = os.path.join(approved_dir, 'page-%02d.png' % p['page'])
        try:
            data = R._read_page_bytes(pf)
        except OSError:
            return dict(doc=doc, ok=False, code=EXIT_ARTIFACT,
                        reason='page %d unreadable or vanished before re-hash' % p['page'], pages=[])
        except ValueError:
            return dict(doc=doc, ok=False, code=EXIT_ARTIFACT,
                        reason='page %d is non-regular or exceeds the workload bound' % p['page'], pages=[])
        total += len(data)
        if total > R.MAX_TOTAL_PAGE_BYTES:
            return dict(doc=doc, ok=False, code=EXIT_ARTIFACT,
                        reason='document exceeds the total-bytes workload bound', pages=[])
        if hashlib.sha256(data).hexdigest() != p['sha256']:
            return dict(doc=doc, ok=False, code=EXIT_HASH,
                        reason='page %d bytes changed since approval (tamper/swap)' % p['page'], pages=[])
        if collect_bytes:
            page_bytes.append(dict(page=p['page'], sha256=p['sha256'], data=data))
        data = None
    result = dict(doc=doc, ok=True, code=EXIT_VERIFIED, reason='verified', pages=page_numbers)
    if collect_bytes:
        result['page_bytes'] = page_bytes
    return result


class ConsumptionError(Exception):
    """Fail-closed rejection at the integrated consumption gate. The message is category-only —
    never a filename/path/OCR text/digits — safe on a model-visible channel."""


def load_verified_pages(approved_root, redacted_root, doc=None):
    """THE supported programmatic consumption API. Verifies and reads in one
    integrated step and returns the exact bytes it hashed:

        [{'doc': 'doc-<16 hex>', 'pages': [{'page': 1, 'sha256': '...', 'data': b'...'}, ...]}, ...]

    'data' is an immutable `bytes` buffer; its sealed hash was verified over that very buffer, so
    an injected swap between verification and use cannot change what the caller consumes — there
    is no path reopen after verification. Fails CLOSED: any rejection (of ANY selected document)
    raises ConsumptionError with a category-only message and returns nothing partial. A future
    in-repo model/vision caller must use this, never a reopen after the CLI.

    Boundary, stated honestly: this closes the verify-then-reopen TOCTOU for the process that
    calls it. It is not a defense against a same-user writer who coherently rewrites manifest,
    pages, and approval together before verification begins (see the module docstring)."""
    for name, root in (('approved', approved_root), ('redacted', redacted_root)):
        if os.path.islink(root) or not os.path.isdir(root):
            raise ConsumptionError('%s root does not exist, is not a directory, or is a symlink' % name)
    if R.distinct_nonnested_errors(dict(approved=approved_root, redacted=redacted_root)):
        raise ConsumptionError('approved and redacted roots must be distinct and non-nested')
    if doc is not None and not R.DOC_ID_RE.match(doc):
        raise ConsumptionError('doc selector must be an opaque document id')
    approvals = _iter_approvals(approved_root, doc)
    if not approvals:
        raise ConsumptionError('no approval found — nothing to consume')
    out = []
    for path in approvals:
        try:
            r = verify_one(path, redacted_root, collect_bytes=True)
        except OSError:
            raise ConsumptionError('unexpected filesystem error during verification')
        if not r['ok']:
            raise ConsumptionError('a document was rejected at the consumption gate (%s)' % r['reason'])
        out.append(dict(doc=r['doc'], pages=r['page_bytes']))
    return out


def build_arg_parser():
    ap = argparse.ArgumentParser(description='Private mode: pre-consumption integrity verifier (ADR-0029)')
    ap.add_argument('--approved', required=True, help='OPERATOR_APPROVED root written by approve_redaction.py')
    ap.add_argument('--redacted', required=True,
                    help='current AWAITING_OPERATOR root; the approval must bind its live generation')
    ap.add_argument('--doc', default=None, help='verify a single opaque document id (default: all)')
    return ap


def main(argv=None):
    a = build_arg_parser().parse_args(argv)
    if not os.path.isdir(a.approved) or os.path.islink(a.approved):
        print('ABORT (invalid invocation): --approved does not exist, is not a directory, or is a symlink')
        return EXIT_INVALID_INVOCATION
    if not os.path.isdir(a.redacted) or os.path.islink(a.redacted):
        print('ABORT (invalid invocation): --redacted does not exist, is not a directory, or is a symlink')
        return EXIT_INVALID_INVOCATION
    if R.distinct_nonnested_errors(dict(approved=a.approved, redacted=a.redacted)):
        print('ABORT (invalid invocation): --approved and --redacted must be distinct and non-nested')
        return EXIT_INVALID_INVOCATION
    if a.doc is not None and not R.DOC_ID_RE.match(a.doc):
        print('ABORT (invalid invocation): --doc must be an opaque document id (doc-<16 hex>), not a raw name/path')
        return EXIT_INVALID_INVOCATION

    approvals = _iter_approvals(a.approved, a.doc)
    if not approvals:
        print('ABORT: no approval.json found under --approved' + (' for --doc ' + a.doc if a.doc else '') +
              ' — nothing to verify')
        return EXIT_NOTHING

    # Top-level firewall (parity with redact_ids.main): no unexpected error may escape this mandatory
    # gate as an exit-1 traceback leaking a path — verify_one already contains its OSError sites; this
    # is the backstop. Fails CLOSED (no VERIFIED), category-only, so no unverified page is consumed.
    try:
        results = [verify_one(p, a.redacted) for p in approvals]
    except OSError:
        print('ABORT: an unexpected filesystem error occurred during verification — nothing verified')
        return EXIT_ARTIFACT
    for r, label in zip(results, R.doc_labels([r['doc'] for r in results])):
        if r['ok']:
            print('  VERIFIED  %-24s  pages=%s' % (label, r['pages']))
        else:
            print('  REJECTED  %-24s  %s' % (label, r['reason']))

    if all(r['ok'] for r in results):
        print('STATE: VERIFIED (%d document(s)) at check time. Use only the exact page set(s) above. '
              'This CLI is a diagnostic check — a separate consumer reopen is NOT atomic with it; '
              'programmatic consumption must go through load_verified_pages().' % len(results))
        return EXIT_VERIFIED
    print('STATE: one or more documents FAILED verification (see REJECTED lines). '
          'Do NOT send any page of a rejected document to a model/vision pass.')
    return max(r['code'] for r in results if not r['ok'])


if __name__ == '__main__':
    sys.exit(main())
