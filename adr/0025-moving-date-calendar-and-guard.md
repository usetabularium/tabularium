# ADR-0025 — Single-source-of-truth calendar for moving dates + guard L7

- **Status:** Accepted 2026-06-23; calendar block replaced by the open-items table 2026-10-04
- **Date:** 2026-06-23
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `ba2851d`; the amendment history is in
  git).

> Abstract by design (a published file): no handles, case dates or condition names. The incident
> itself is in the patient's local, deny-listed reconciliation log.

## Context

Moving dates (appointments, planned procedures, expected results) were restated in several places
of a `profile.md`. In a large-context reconciliation pass a booked appointment's date was copied
onto a *different* condition's row, implying a procedure was scheduled when it was only
recommended. The operator caught it; no executable control covered date duplication.

Each restated copy is a drift surface. Misattribution between condition rows is adjacent to the
person mix-up class (ADR-0002), here within one person. Historical dates are settled and must stay
out of scope. Another patient's record was un-migrated: a new guard must not turn it red, and
under ADR-0002 this work must not read its files. Operator facts are authoritative (ADR-0005): the
guard enforces structure, never clinical truth.

## Decision

What holds now: the L7 section of `checks/check.sh` and its row in `checks/README.md`, the
`## Open items` block of `_templates/profile.md` and `CLAUDE.md` (*Keeping it current*).

1. **One home for moving dates, inside `profile.md`** (2026-06-23): a block between HTML-comment
   markers (invisible in a render, independent of the heading's language). It was a
   `## Kalendarz / Calendar` block of rows keyed by stable `cal-<id>`s; since 2026-10-04 it is the
   `## Open items` table between the `OPEN-ITEMS` markers.

2. **The rest of the record refers to the item, never restates its date** (2026-06-23): by its
   `cal-<id>`, with a dateless row giving an owed but unbooked item an id; since 2026-10-04, in
   words, as the table has no ids.

3. **Guard L7: opt-in per doc, fail-closed, host-portable** (2026-06-23; ADR-0020, ADR-0021). A
   canonical doc that declares the block subjects itself to L7; one without it is untouched. No
   bare `YYYY-MM-DD` later than today may appear in the live body. Today was the UTC date; since
   2026-10-31 it is the later of the UTC and the local date, because east of UTC an operator who
   wrote their own today before UTC midnight turned the board red for hours, with nothing to do but
   wait. A date past both still fails. The change log is excluded: history
   records dates as they were known, and policing it would force editing history. A block L7
   cannot read fails loudly, never skips. On 2026-10-04 the second rule, that every `cal-<id>`
   referenced is defined, went with the ids, and an intact empty table became green.

4. **The profile template ships the block** (operator, 2026-07-04). The opt-in protected the
   un-migrated patient but never set the default for future ones, so every scaffolded profile
   started outside L7, the incident class unguarded on every new person. Docs scaffolded earlier
   keep the opt-in. The calendar was seeded with dateless rows because an empty block then failed
   closed; the table ships empty (point 3). Accepted cost: every new patient inherits the
   graduation step from day one.

## Alternatives considered

All rejected on 2026-06-23.

- **A separate `calendar.md` per patient:** its own L1 coverage, snapshot discovery, L5 pass and
  canonical-doc wiring, where the profile inherits them; and the date belongs with the person.
- **A non-blocking monitor like `confirms.sh`:** the incident is a record-integrity error in a
  canonical doc, which should block a commit (ADR-0022), not merely be chased.
- **Forbidding every duplicate date, historical ones too:** a false-positive storm, and historical
  dates cannot drift.
- **A mandatory calendar for every patient at once:** reading and editing another patient's files
  (an ADR-0002 breach), and an un-migrated patient turned red.
- **Refactoring every condition row to one date-referencing template** (for that pass): many
  clinical rows touched for cosmetic uniformity multiplies edit risk in a life-and-death file, and
  the guard already prevents the incident once a profile adopts L7 and its future dates move.

## Consequences

- A moving date lives in one place, so misattributing it is structurally hard; an owed but unbooked
  item is findable, and the block doubles as a visit-preparation list.
- **Graduation** (2026-06-23): as a date passed, the operator moved it into the record as history
  and retired the row, the natural moment to confirm what happened. Since 2026-10-04 an overdue
  item stays in the table until done, cancelled or abandoned (`CLAUDE.md`).
- L7 checks where a date lives, not what a reference means: a reference to the wrong event passes.
- A `medications.md` whose dates have one home may stay standalone, outside L7.
- A future date that is not an appointment, such as a birthday, trips L7, so it is written without
  a bare ISO day; a quiet, sound guard beats a noisy one.
