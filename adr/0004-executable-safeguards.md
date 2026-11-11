# ADR-0004 — Executable safeguards

- **Status:** Accepted by 2026-06-07; superseded in part by ADR-0042 2026-07-26
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

A prose rule with no failing test is a comment: the 38-line truncation slipped through *because* no
check existed.

## Decision

What holds now: `checks/README.md`, `contributing/gates.md` and `CLAUDE.md` → *Safeguards*.

Safeguards are executable: `checks/`, its guards and bite-tests, plus an append-only `.snapshots/`
recovery floor. A care editing session runs green board → no other session writing records →
snapshot → edit → green board. That order is the standing care workflow, not an interim one.

## Alternatives considered

- **Snapshot, then check** (the rule as first recorded; replaced by ADR-0042's guard-first order,
  2026-07-26): a capture is not atomic across other writers, and it relies on a green board to find
  the patient folders.
- **The session validating each pre-edit snapshot** (the rule from 2026-07-26; dropped by the
  operator, 2026-10-27, ADR-0042): the snapshot script's completion marker and refusals carry it.
