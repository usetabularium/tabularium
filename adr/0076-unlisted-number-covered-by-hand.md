# ADR-0076 — A number private mode cannot mask yet is covered by hand, not waited for

- **Status:** Accepted 2026-11-10 (operator); supersedes in part ADR-0073 point 2 (the pages wait); point 2 superseded in part by ADR-0077 2026-11-10 (the key `unlisted` replaces the phrase)
- **Date:** 2026-11-09
- **Deciders:** operator (+ assistant)

## Context

Private mode masks only the numbers on its list, and the list ships one row. For anyone else's
number, ADR-0073 point 2 has the person's pages wait until a row ships, so most people set up in
private mode could not have a page filed. The operator asked that no one wait (2026-11-09).

## Decision

1. **No one waits.** When a designated number is not on the list, the session says the tool cannot
   mask that number yet and proposes covering it by hand on every page before scanning, with any
   printed code that may hold it, keeping what tells people apart (operator, 2026-11-09).
2. **The gate stays.** Masking runs with `--covered-by-hand`: it looks for no unlisted number (beside
   a tag, it still masks the tagged ones), and every page still goes through the operator's look-over,
   approval and verification before any model sees it. The marker, the read guard and the phrase
   "number not on the list" stay as they are.

## Alternatives considered

- Pages wait until a row ships (ADR-0073 point 2, 2026-11-08): no route for most countries.
- Private mode off, details covered by hand: loses the read guard and the look-over for that person.
- A row per country on request: each needs a page round first; no faster for the person waiting.

## Consequences

- For an unlisted number, the operator's covering is the only mask and their look-over the only
  check; guard L10, the relay scan and the export scan search for no pattern of it, as before. The
  masking tool refuses `--covered-by-hand` for a person whose private-mode line does not say "number not
  on the list", and in place of a number the line tags.
- The covering habit is the operator's; a page scanned uncovered is caught only at the look-over.
