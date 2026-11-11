# ADR-0014 — Per-condition whitelist that grows with casework

- **Status:** Accepted by 2026-06-09
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

A whitelist of only the roster's conditions is a fingerprint of the roster. A broad list covering
many conditions is a public good and hides which ones the roster holds, so care value need not be
stripped to publish it (cf. ADR-0013's 2026-06-08 ruling that care outranks publishing).

## Decision

What holds now: `reference-library/README.md`, `checks/RECORD-SET` (both lists are records) and the
top-level `README.md` (the library ships empty).

`whitelist.txt` grows per condition with casework, toward broad coverage, in separate `[category]`
blocks (greppable, cheap to load). The roster's conditions are built out and verified on PubMed;
the rest are explicit stubs, promoted as new people arrive. The aim: build it out broadly with
specialist-red-teamed helpers, then publish it; until it hides the roster, it stays local.
