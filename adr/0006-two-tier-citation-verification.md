# ADR-0006 — Two-tier citation verification

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded for points 1 and 2; the operator for point 3
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Citation mis-attributions showed that unverified citations leak. Roadmap decision D1 asked how a
clinician handout could cite official product information and how often to re-check it.

## Decision

What holds now: `reference-library/README.md` (*The bar*, *Official product information*,
*Two-tier verification*), the L4 row of `checks/README.md`, `_templates/HANDOUT-RULES.md`,
`_templates/HANDOUT-SOP.md` (the fact-check self-audit) and `CLAUDE.md` (*Stance*).

1. **A source is Vetted only after a PubMed-confirmed identifier (tier 1) and curation and lint
   (tier 2).** Guard L4 warns on a cited id that is not Vetted and never reds (ADR-0048 point 10),
   so nothing deterministic stops a warned id at the seal.

2. **Official product information clears the bar for its own medicine** (2026-10-25). An approved
   summary of product characteristics or patient leaflet may be cited for that medicine's dosing
   and its limits, duration of use, contraindications, interactions and warnings, never for a wider
   clinical claim. It is the text of the product in use, from the country where it was dispensed
   (national register first), since limits differ between products of one substance; another
   product's or country's text is a named stand-in. It is cited by link and revision date, with no
   PMID, DOI or `index.md` entry, since it is revised often.

3. **Roadmap decision D1 closes on that basis, handouts included** (operator, 2026-10-25, after the
   Astra-model review found the handout rule still waiting on D1). A clinician handout cites product
   information by link and revision date, for that medicine's own facts; its fact check confirms the
   revision against the current text, the re-verification cadence D1 asked for.

## Alternatives considered

- **Guard L4 blocks unverified candidates from handouts** (as backfilled; replaced 2026-10-04 by
  ADR-0048 point 10; drift recorded 2026-10-11).
- **A library tier for product information, or a `label:` form for guard L4** (D1's options a and
  b; declined by the operator, 2026-10-25): the fact check's revision check already re-verifies it.

## Consequences

- Product information carries no id, so L4 cannot see it; the handout's fact check is its check:
  the author's self-audit compares the revision with the current text, and the verifier does so
  independently (ADR-0064).
