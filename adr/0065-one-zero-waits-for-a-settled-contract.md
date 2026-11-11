# ADR-0065 — 1.0.0 waits for a settled contract, not the public flip

- **Status:** Accepted 2026-11-08; supersedes in part ADR-0054 point 5
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

ADR-0054 point 5 made 1.0.0 the first public release, the commit the flip-time export is taken
from: 1.0.0 promises a stable public contract, and before the flip there was none, since the licence
was unattached and `NOTICE.md` carried preview terms. The licence was attached on 2026-11-07 and the
preview terms are gone (ADR-0035), so that reason no longer holds, as ADR-0035 notes.

The rest of the premise, a stable contract at the flip, does not hold either. Each of the last three
releases (v0.62.0, v0.63.0, v0.64.0) withdrew at least one protection, and v0.64.0 also changed the
medications list's layout and added two asks to the care contract. After 1.0.0, ADR-0054 point 2
would make each such withdrawal a MAJOR. ADR-0066 builds public releases from their tags and leaves
the number to ADR-0054 and its successors.

## Decision

On acceptance this record supersedes only ADR-0054 point 5's rule that 1.0.0 is the first public
release; the rest of ADR-0054 stays accepted.

1. **Keep 0.x at the public flip** (operator, 2026-11-02). The flip does not itself bring 1.0.0;
   numbering goes on under ADR-0054 point 2, so what would be a MAJOR stays a MINOR whose note leads
   with it, until the conditions below hold.
2. **1.0.0 is the first release at which all three hold** (operator, 2026-11-02):
   - the record layout and the care contract have been steady for a while;
   - two releases in a row withdraw no protection;
   - someone other than the operator has run it.

   The operator judges the first and third at a release; the second is read from the notes'
   *Withdrawn protections* lines.

## Alternatives considered

- **1.0.0 at the flip (ADR-0054 point 5):** the flip would set the stable-contract milestone before
  the three conditions hold, and each later withdrawn protection, record format or path change, or
  extra adoption step would then be a MAJOR under ADR-0054 point 2.

## Consequences

- The public copy starts below 1.0.0, so its number tells readers the contract may still change,
  which is true. A withdrawn protection stays visible only in the note, which the adopter must read
  (ADR-0054, *Consequences*).
- Nothing checks the three conditions; the releaser reads them at each release, as the bump class is
  read today.
- On acceptance, `contributing/releases.md` replaces "1.0.0 is the first public release" with point 2,
  ADR-0054's Status line names the partial supersession, and the index in `adr/README.md` shows it.
