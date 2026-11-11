# ADR-0072 — The relay scan matches personal details; nothing crosses word for word

- **Status:** Accepted 2026-11-08; supersedes in part ADR-0050 point 8, ADR-0013 point 6, ADR-0027
  point 3 and ADR-0049 point 5 (the relay scan's classes), and ADR-0013 point 5 and ADR-0029 point 9
  (case dates on the registry)
- **Date:** 2026-11-08
- **Deciders:** operator (+ assistant)

## Context

The relay scan matched every registry class. The clinical, brand and consent classes hold words that
on their own fit anybody (a relationship word, a care setting, a condition or a sensitive attribute),
so the scan stopped ordinary prose bound for the development tree. What the relay must keep out is a
person's details and care-folder text itself.

## Decision

1. The relay scan matches personal details: the identity class (names, handles, dates of birth), the
   private-mode identifier and each kept-details line, `PII_PRIVATE_<CLASS>`
   (operator, 2026-11-08).
2. The clinical, brand and consent classes are not matched at the relay. The flip-time export gate
   still scans every class over what is published.
3. Nothing from a care folder crosses word for word: care knowledge enters the development tree only
   as abstract prose, never a file copy or a copied line (operator, 2026-11-08). A written rule; no
   check compares outgoing text with care files.
4. Real case dates are not kept on the token registry (operator, 2026-11-08). A leftover
   case-reference line, in the registry or as a kept-details line, is ignored by every reader, so
   it can be deleted at any time; any other unknown class still blinds the relay scan.

## Alternatives considered

- **Every class at the relay** (the rule from 2026-09-06; reversed by the operator, 2026-11-08): it
  flagged words that identify nobody, and the export gate already guards the public copy.
- **Drop the brand class only:** condition and drug names would still stop ordinary prose.
- **A case-reference class of real case dates** at the relay and the export (the rule until
  2026-11-08; reversed by the operator, 2026-11-08): a case date looks like any other date, so it
  flagged ordinary text and fixture dates.
- **A check for copied lines:** the scan would have to read records to compare; the written rule and
  the author's judgment suffice.

## Consequences

- A condition fingerprint or a care-setting word written into a development-tree file is caught only
  at the export, and only if that file is published.
- A real case date written into a development-tree file or the public copy is caught by no scan; the
  abstract-prose rule (point 3) is the control.
- A fifth registry class blinds the relay scan until it is ruled in or out.
- Held by `checks/relay-scan.sh`, `checks/publish-skeleton.sh`, `checks/install-instance.sh`,
  `evals/harness/containment.py` and their bites in `checks/selftest.sh` and
  `evals/harness/test_containment.py`.
