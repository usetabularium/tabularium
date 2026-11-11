# ADR-0012 — Scripted, firewalled GitHub publish

- **Status:** Accepted by 2026-06-07; superseded in part by ADR-0050 2026-09-06 and by ADR-0066
  (point 1: one fresh copy per push) 2026-11-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The sandbox could not run git and the local `.git` held PII, so publishing had to be mechanically
unable to leak patient data.

## Decision

What holds now: `checks/publish-skeleton.sh`, `checks/topics/relay-and-export.md` → *The flip-time
export — the mechanics*, `checks/PUBLISH-HOLD` and `contributing/instances.md` → *Publishing — the
export process*.

1. **A scripted, firewalled export** (`checks/publish-skeleton.sh`): a fresh, history-free,
   allow-listed copy behind the PII firewall and a deny-list assertion, so repository history
   cannot leak.
2. **The export serves only the public flip** (ADR-0050, 2026-09-06), taken from record-free DEV and
   gated by the export scan reading the registry from outside every repository (ADR-0050 Part A2).
3. **Deleting the local `.git` is gated** and confirmed by the operator.
4. **`selftest.sh` runs on synthetic fixtures**, decoupled from real names, so it ships (ADR-0038).

## Alternatives considered

- **The scripted export as the routine sharing path** (the rule as first recorded; replaced by
  ADR-0050, 2026-09-06): DEV never holds a record and pushes to its own private remote, so only the
  public flip needs an export.
