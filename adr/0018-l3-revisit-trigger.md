# ADR-0018 — An explicit revisit trigger for guard L3

- **Status:** Superseded by ADR-0047 2026-08-16 (accepted 2026-06-13)
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Guard L3 was to keep a literature value apart from a patient value, and it was deferred "until
tuned". It covered the one failure class with no executable check yet: a study median logged as a
patient value.

## Decision

**L3 gets an explicit revisit trigger, not an open-ended deferral.** Build it when the first of
these comes: a further patient is added, the canonical-doc count (`profile.md` + `medications.md`)
grows past a set size, or the next batch source-intake. Why: a deferral "until tuned" silently goes stale as
the corpus grows, so it needs a tripwire, not vigilance. The trigger was recorded in
`checks/README.md` → *Not yet built* (now *Deferred controls*); `confirms.sh`, the other "next
increment", shipped that round.

### Disposition (superseded 2026-08-16)

- **2026-06-25, re-deferred.** The batch source-intake trigger fired, and L3 was re-deferred, not
  built. On a small record set a numeric patient-vs-literature heuristic cannot be tuned low-noise:
  every clinical number is a candidate, so an untuned guard would redden the real corpus or breed
  alert fatigue that erodes the green signal, which is worse than no guard. Manual review, the
  `⟨confirm⟩` queue and L4 held the adjacent risk. Sharper triggers, whichever came first: a
  further patient is added, or a clinician handout must place a literature or guideline range and
  a patient-measured value of the same quantity in one document. The operator may override and ask
  for L3 now.
- **2026-07-04, fired** (recorded 2026-07-26). The record-set trigger fired; the
  build-or-re-defer choice was blocked on the operator.
- **2026-08-16, built** (ADR-0047). The operator decided on 2026-08-09 to build L3, in the
  low-noise version. The tripwire did its job and is spent: no later document may describe L3 as
  deferred, triggered-but-unbuilt or blocked. The small-record-set reasoning became ADR-0047's hard
  design constraint, which is why L3 became a context-triggered attribution demand rather than the
  numeric heuristic first sketched for it.
- **2026-10-04, retired** (ADR-0047); the number is not reused.

## Alternatives considered

- **Leave L3 deferred "until tuned", with no trigger:** it rests on vigilance and goes stale
  unnoticed.

## Consequences

- A fired trigger forces a recorded choice, build or re-defer, never an implicit one; each firing
  above was recorded.
