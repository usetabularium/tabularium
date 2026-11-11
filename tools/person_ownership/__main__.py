#!/usr/bin/env python3
"""CLI for the person-ownership package (ADR-0037): `python3 -m tools.person_ownership <cmd>`.

Subcommands:
  verify              L13's fail-closed check. Exit 0 = GREEN (aggregate summary only); 1 = RED
                      (category + path, the path withheld for a private-mode person — ADR-0029
                      point 11; no person id / hash); 2 = internal error (fail closed).
                      `--mirror` checks an append-only backup mirror: every current record's file
                      present with its recorded bytes; files no current record binds are counted only.
  pilot               dry structural pilot on the smallest patient (writes nothing into patient trees).
  migrate             deterministic Option-B migration (legacy-folder-only); writes local-only output.
                      WHOLE-TREE: every person without a ledger — the explicit maintenance operation.
  init                ONE person's first ledger (ADR-0037 §12): mints the ID if absent, registers the
                      sources already on disk as migrate would; refuses if any ledger exists.
  append              add a later source or correct an existing record after migration (ADR-0037 §11):
                      add (one or several --relpath, one append) / confirm / rename /
                      rehash / wrong-owner (split is refused); retranscribe re-binds a corrected
                      `.ocr.md` to its unchanged original and refuses unless the file carries a dated
                      erratum line for it (§13); transcribe binds a first `.ocr.md` written after its
                      original was inventoried (§14). add, retranscribe and transcribe each take
                      several --relpath values, written as one append or not at all.
  refresh-checkpoint  prefix-validating finalizer (ADR-0037 §11): re-bless MANIFEST.checkpoint to the
                      current MANIFEST iff the checkpointed bytes are its exact prefix — recovers a
                      crash between the two writes; CANNOT re-bless an in-place rewrite.

Output discipline: GREEN reports only review-queue presence. A finding prints its category and the
path it is about under the locator rule (`fsverify.locator`); person IDs, hashes and corpus counts
never print.
"""
import argparse
import os
import sys

from . import fsverify
from . import migrate as _migrate


def _cmd_verify(a):
    try:
        findings, agg = fsverify.verify_tree(a.root, mirror=a.mirror)
    except Exception:
        # fail closed: any unexpected error in the guard is RED, not a green pass. Category only.
        print('L13 RED: ownership verifier hit an internal error (fail closed)')
        return 2
    if findings:
        try:
            in_use = fsverify.private_mode_in_use(a.root)
            wheres = [fsverify.locator(a.root, f.handle, f.relpath, in_use) for f in findings]
        except Exception:
            wheres = [''] * len(findings)   # cannot apply the locator rule: category only
        print('L13 RED: %d ownership finding(s):' % len(findings))
        for f, where in zip(findings, wheres):
            print('  ' + f.render() + ((' — ' + where) if where else ''))
        return 1
    legacy = agg['legacy_folder_only']
    queue = 'present' if legacy else 'empty'
    print('L13 GREEN: ownership consistent; legacy-folder-only review queue is %s. '
          'L13 proves metadata/hash consistency only — identity judgment is operator/intake provenance.'
          % queue)
    if a.mirror:
        print('  mirror: every current record\'s file is present with its recorded bytes; %d file(s) no '
              'current record binds (old names the no-delete copy keeps, or other extras) — information, '
              'not a failure' % agg['mirror_extra_files'])
    return 0


def _cmd_pilot(a):
    try:
        agg = _migrate.pilot(a.root, report_path=a.report)
    except _migrate.MigrationStop as e:
        print('pilot STOPPED: ' + str(e))
        return 3
    except OSError:
        print('pilot STOPPED: filesystem operation failed (locator withheld)')
        return 3
    print('pilot: completed; evidence inventory and corpus counts withheld from stdout; exceptions=%s'
          % ('present' if agg.get('exceptions') else 'none'))
    for e in agg.get('exceptions', []):
        print('  exception: ' + e)
    return 0


def _cmd_migrate(a):
    try:
        agg = _migrate.migrate(a.root, report_path=a.report, mint=not a.no_mint)
    except _migrate.MigrationStop as e:
        print('migrate STOPPED (no certainty invented): ' + str(e))
        return 3
    except OSError:
        print('migrate STOPPED: filesystem operation failed (locator withheld)')
        return 3
    print('migrate: completed; patient/evidence counts withheld from stdout; changes=%s; '
          'legacy review queue=%s'
          % ('yes' if agg['migrated'] else 'no',
             'present' if agg['total_legacy_folder_only'] else 'empty'))
    return 0


def _cmd_init(a):
    from . import append as _append
    try:
        _append.init_ledger(a.root, a.handle)
    except _append.AppendStop as e:
        print('init STOPPED (no certainty invented): ' + str(e))
        return 3
    except OSError:
        print('init STOPPED: filesystem operation failed (locator withheld)')
        return 3
    print('init: done (one patient); first ledger written — later sources go through '
          '`append <handle> add`')
    return 0


_APPEND_OPS = ('add', 'confirm', 'rename', 'rehash', 'wrong-owner', 'retranscribe', 'transcribe',
               'split')


def _cmd_append(a):
    from . import append as _append
    try:
        if a.op == 'add':
            _append.add_source(a.root, a.handle, a.relpath, confirmed=a.confirmed,
                               identity_source=a.identity_source)
        elif a.op == 'confirm':
            _append.confirm(a.root, a.handle, a.relpath, identity_source=a.identity_source)
        elif a.op == 'rename':
            _append.rename(a.root, a.handle, a.old_relpath, a.new_relpath,
                           identity_source=a.identity_source)
        elif a.op == 'rehash':
            _append.rehash(a.root, a.handle, a.relpath, identity_source=a.identity_source)
        elif a.op == 'wrong-owner':
            _append.wrong_owner(a.root, a.handle, a.relpath, identity_source=a.identity_source)
        elif a.op == 'retranscribe':
            _append.retranscribe(a.root, a.handle, a.relpath)
        elif a.op == 'transcribe':
            _append.transcribe(a.root, a.handle, a.relpath)
        elif a.op == 'split':
            _append.split()
    except _append.AppendStop as e:
        print('append STOPPED (no certainty invented): ' + str(e))
        return 3
    except OSError:
        print('append STOPPED: filesystem operation failed (locator withheld)')
        return 3
    print('append: done (one patient); category/queue detail withheld from stdout')
    return 0


def _cmd_refresh(a):
    from . import append as _append
    try:
        _append.prefix_finalize(a.root, a.handle)
    except _append.AppendStop as e:
        print('finalize STOPPED: ' + str(e))
        return 3
    except OSError:
        print('finalize STOPPED: filesystem operation failed (locator withheld)')
        return 3
    print('finalize: checkpoint re-blessed to the current MANIFEST (prefix-validated)')
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog='python3 -m tools.person_ownership',
                                 description='Person-ownership binding (ADR-0037)')
    ap.add_argument('--root', default=os.getcwd(), help='repository root (default: cwd)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('verify', help='L13 fail-closed ownership check')
    v.add_argument('--mirror', action='store_true',
                   help='an append-only backup mirror: count, never fail, files no current record binds')
    p = sub.add_parser('pilot', help='dry structural pilot on the smallest patient')
    p.add_argument('--report', default=None, help='LOCAL-ONLY inventory report path (never track)')
    m = sub.add_parser('migrate', help='deterministic Option-B migration')
    m.add_argument('--report', default=None, help='LOCAL-ONLY migration report path (never track)')
    m.add_argument('--no-mint', action='store_true', help='fail rather than mint a missing person id')
    i = sub.add_parser('init', help="one person's first ledger (touches only that person's folder)")
    i.add_argument('handle', help='patient handle')

    ap_append = sub.add_parser('append', help='append/correct a MANIFEST record (ADR-0037 §11)')
    ap_append.add_argument('handle', help='patient handle')
    asub = ap_append.add_subparsers(dest='op', required=True)
    p_add = asub.add_parser('add', help='add new later source(s) (+ each 1:1 .ocr.md if present) '
                            'in one append')
    p_add.add_argument('--relpath', required=True, action='append',
                       help='patient-root-relative med/sources path; repeat it for documents that '
                            'arrived together (all are written, or none)')
    p_add.add_argument('--confirmed', action='store_true',
                       help='operator-confirmed (default: legacy-folder-only, unverified)')
    p_add.add_argument('--identity-source', default=None, help='local provenance basis (optional)')
    p_conf = asub.add_parser('confirm', help='promote a legacy-folder-only record to operator-confirmed')
    p_conf.add_argument('--relpath', required=True)
    p_conf.add_argument('--identity-source', default=None)
    p_ren = asub.add_parser('rename', help='record a source rename (the old path must already be gone)')
    p_ren.add_argument('--from', dest='old_relpath', required=True)
    p_ren.add_argument('--to', dest='new_relpath', required=True)
    p_ren.add_argument('--identity-source', default=None)
    p_reh = asub.add_parser('rehash', help='record re-scanned bytes for an existing source')
    p_reh.add_argument('--relpath', required=True)
    p_reh.add_argument('--identity-source', default=None)
    p_wo = asub.add_parser('wrong-owner',
                           help='retract a misfiled source (move the file off med/sources first)')
    p_wo.add_argument('--relpath', required=True)
    p_wo.add_argument('--identity-source', default=None)
    p_rt = asub.add_parser('retranscribe', help='re-bind a corrected .ocr.md to its unchanged '
                           'original (refused without a dated erratum line in the file)')
    p_rt.add_argument('--relpath', required=True, action='append',
                      help="the ORIGINAL's med/sources path (not the .ocr.md); repeat it for "
                           "corrections made together (one append)")
    p_tr = asub.add_parser('transcribe', help='bind a first .ocr.md written after its original was '
                           'inventoried (same name stem, beside it)')
    p_tr.add_argument('--relpath', required=True, action='append',
                      help="the ORIGINAL's med/sources path (not the .ocr.md); repeat it for "
                           "transcriptions written together (one append)")
    asub.add_parser('split', help='refused — v2-deferred (needs bundle-linked provenance)')

    r = sub.add_parser('refresh-checkpoint',
                       help='prefix-validating finalizer / crash recovery (ADR-0037 §11)')
    r.add_argument('handle', help='patient handle')
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    return {'verify': _cmd_verify, 'pilot': _cmd_pilot, 'migrate': _cmd_migrate, 'init': _cmd_init,
            'append': _cmd_append, 'refresh-checkpoint': _cmd_refresh}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
