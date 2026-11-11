# ADR-0042 — Private recovery publication and guard-complete patient-root discovery

- **Status:** Accepted 2026-07-26; independent validation of pre-edit snapshots dropped 2026-10-27
- **Date:** 2026-07-26
- **Deciders:** not named (red-teamed independently before commit); the operator for the rulings
  of 2026-08-22 and 2026-10-27
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Patient data is kept out of git history (ADR-0017), so snapshots and whole-tree tarballs were the
only local recovery layers. A recovery artifact can harm in two opposite ways: incomplete while
looking current, or a full private copy readable by others. The scripts wrote straight to final
names, so an interruption could leave a partial copy under one, and older artifacts and live
private trees were group- or world-readable.

The same audit found discovery blind spots: globs over `patients/*/` omit a dot-prefixed root and
follow a symlinked one outside the repository; in private mode `find -type f` skips a symlinked
Markdown subtree; and a recursive grep could read an unreadable subtree as "marker absent" or hang
on a FIFO.

## Decision

What holds now: `checks/snapshot.sh`, `checks/backup-tree.sh`, `checks/README.md` (*Recovery*,
*Version control & backups*), the L0 and L10 sections of `checks/check.sh` and `CLAUDE.md` →
*Safeguards*; the bites are listed in the `checks/selftest.sh` header (recovery floor).

1. **Recovery artifacts are owner-only by construction** (2026-07-26), never relying on source
   modes or the caller's umask. The live and recovery trees were restricted to their owner once: a
   permission repair, not a claim of cryptographic isolation.
2. **Only a complete, verified recovery point is published, atomically and never over another**
   (2026-07-26): private staging, validation, then the final name; a snapshot's root completion
   marker tells an exact publication from a nested or partial one. Nothing is pruned automatically.
3. **Patient-root discovery is guard-complete** (2026-07-26). L0 reds a symlinked or hidden patient
   root before any downstream discovery; L10 reds any symlink in an in-scope private-mode tree and
   treats a traversal or grep error as red, never as "no marker". L0's reds at first withheld their
   locators; since 2026-09-27 they follow ADR-0029's locator rule (drift recorded 2026-10-11).
4. **Guard first, writers quiesced, each recovery point validated** (2026-07-26). A capture is not
   atomic across other writers; without `fsync` the atomic names hold for a clean or caught
   failure, not sudden power loss; and run standalone the scripts rely on a prior green L0 for
   patient-root topology. The operator accepted that limit on 2026-08-22, so on 2026-08-30
   this practice became permanent, not interim.
   - **Pre-edit snapshots: the session's confirmation is cut** (operator, 2026-10-27). For them
     only, the independent validation is dropped: `CLAUDE.md` → *Safeguards* no longer has the
     session confirm the copy, which rests on `checks/snapshot.sh`'s completion marker and its
     refusals of a failed, empty or misplaced copy. Guard first and quiesced writers stay; backup
     tarballs are unchanged. The limit was re-reviewed (operator).

## Alternatives considered

None were recorded in the source ADR.

## Consequences

- The local layers share the machine's failure domain by design: they protect against bad writes,
  accidental deletion and interrupted publication, not device loss or a same-user adversary.
- Device loss was open at acceptance; backup layer 3 closed it on 2026-08-09, after a
  restore drill and the operator's confirmation of an offline recovery key (ADR-0045 point 9),
  recorded here on 2026-08-30.
