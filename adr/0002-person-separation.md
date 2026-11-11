# ADR-0002 — Person separation is the #1 rule

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

A person mix-up is the highest-stakes error, so it is guarded structurally, not by vigilance.

## Decision

What holds now: `CLAUDE.md` → *Sessions and people*, and the L5 and L13 rows of `checks/README.md`
→ *Guards*.

One person per session by default. Each person's files are self-contained. Only `_shared/` and
`patients/README.md` (the roster) refer to more than one person. The exceptions, a combined session
and another person named only by role, are stated in `CLAUDE.md`.
