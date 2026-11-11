# ADR-0001 — Three-layer model

- **Status:** Accepted by 2026-06-07; superseded in part by ADR-0039 2026-07-17
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Without layers, the profile rots into a log. Conclusions should flow up, never sideways.

## Decision

What holds now: `CLAUDE.md` → *Layout* and *Handouts*, `_templates/person/README.md` and the table
of doc kinds in `contributing/documentation.md`.

Three layers: sources (immutable) → profile and medications (current truth) → outputs (handouts and
analyses). Sources feed the profile, and the profile feeds the outputs, which are never evidence. An
analysis is a derived output and can be regenerated. A delivered handout is sealed (ADR-0039): kept
exactly as it is and superseded by a new dated handout, never regenerated.

## Alternatives considered

- **Every output regenerable** (the rule as first recorded; replaced by ADR-0039's sealed handouts,
  2026-07-17): a clinician acts on the bytes handed over, so they stay as delivered.
