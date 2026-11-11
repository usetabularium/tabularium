# ADR-0064 — The handout verifier opens cited product information

- **Status:** Accepted 2026-11-07 (operator)
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

ADR-0006 point 3 has a clinician handout cite official product information by link and revision
date, with its fact check confirming the revision against the current text; that check is why a
library tier and a `label:` form were declined. ADR-0034 point 1 holds the independent verifier to
one person's files and the Vetted library, so only the author's self-audit was told to open the
link, and the standing prompt named no rule for it.

A synthetic verify on 2026-11-07, with five links to one national register and one trial on the
prompt as it stood, showed the verifier opening the links off its list, and failing a handout
because the text printed no revision date. Six of ten official texts sampled that day showed no
date in their extracted text.

## Decision

1. **The verifier opens the product information a handout cites, at that link, and judges the
   medicine's facts against its text** (operator, 2026-11-07). This adds one class to the material
   in ADR-0034 points 1 and 6; they otherwise stand. The author's self-audit stays.

2. **A wrong citation holds the seal; a site does not** (operator, 2026-11-07). A revision date the
   text rules out, a link with nothing behind it, or another product's or country's text not named
   as a stand-in is a MUST-FIX. A text printing no date, or a page that stays blocked, down or
   unreadable, is an advisory note. Ledger statuses, the sidecar and the verdict rule are unchanged.

## Alternatives considered

- **Leave the comparison to the self-audit** (declined, operator, 2026-11-07): the prompt leaves the
  verifier's handling of these links unspecified, and the author alone would compare.
- **Every unopened page a MUST-FIX** (declined, operator, 2026-11-07): an outage or a block would
  hold a seal the author can do nothing about.
- **A library tier or a `label:` form:** still declined (ADR-0006).

## Consequences

- A handout's product facts get an independent look before the seal when the cited text can be
  opened.
- The verify reaches the web for the cited link only, carrying nothing about the person
  (`CLAUDE.md`, *Safeguards*).
- In three synthetic trials the prompt as it stood and this wording's drafts cost about the same.
  EV-12's handout cites no product information and its session has no web tool, so EV-12 does not
  exercise this.

### Admission test (guard-admission)

(1) A wrong dose limit or warning reaching a clinician in a sealed handout, checked only by its
author. (2) Nothing stops the operator; a stale date costs one round. (3) It acts at the hand-over
gate. (4) About the same measured cost as the prompt as it stood, and it removes a false fail.
(5) No new control: a sharper method inside the existing verifier.
