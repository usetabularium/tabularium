# ADR-0077 — Private mode decides by the exact tag alone: an unlisted number is a key, no tag searches every row

- **Status:** Accepted 2026-11-10 (operator); supersedes in part ADR-0073 point 1 (no tag means the first row) and point 2, and ADR-0076 point 2 (the phrase "number not on the list" names no scheme)
- **Date:** 2026-11-10
- **Deciders:** operator (+ assistant)

## Context

Guard L10 and the masking tool choose which number shapes to search from a person's profile. Two inputs
could lower that protection: the words "number not on the list", matched as prose, switched the search
off; and a profile without a readable tag fell back to the narrowest choice, the first row. A damaged
tag beside the phrase therefore left a listed number unsearched. Catching damaged tags with patterns
cannot be finished: the spellings people, editors and OCR produce have no end, and each pattern adds
false refusals of ordinary prose.

## Decision

1. **Only exact tokens decide.** The tools read the exact `⟨id-scheme KEY[,KEY]⟩` on the marker line,
   and nothing else in the text carries machine meaning (operator, 2026-11-10).
2. **A number not on the list is the reserved key `unlisted`**, in the same tag: `⟨id-scheme unlisted⟩`,
   or `⟨id-scheme pl-id,unlisted⟩` beside a listed number. It has no residue shape, and the masking
   tool's `--covered-by-hand` needs it. Its issuing country stays in words beside it (operator,
   2026-11-10).
3. **No exact tag read means every row of the list is searched**, so a damaged tag can widen the
   search but never narrow it (operator, 2026-11-10).
4. **Language is the session's job.** A session that reads or writes a private-mode line stops and
   offers the operator a corrected line when anything near it looks like a damaged tag. ADR-0073's
   one-line refusals on the marker line stay as they are and are not extended.

## Alternatives considered

- The phrase "number not on the list" names no scheme (ADR-0073 point 2, ADR-0076 point 2, 2026-11-08):
  prose in the direction that lowers protection; a damaged tag beside it switched the search off.
- No tag means the first row (ADR-0073 point 1, 2026-11-07): fails narrow once a second row ships.
- Refusing damaged tags by pattern, across lines, list items or sections (proposed 2026-11-10): seven
  review passes each found new spellings missed and prose refused; it never converges.

## Consequences

- A profile whose number is not on the list carries `unlisted` in its tag; one that still has only the
  phrase is searched with every listed shape (false alarms, not a blind spot) until the key is added in
  a care edit session.
- Once a second row ships, an untagged profile is searched with every row's shape; tagging it narrows
  the search.
- Held by guard L10 and the `IdSchemes` tests in `tools/private-mode/test_identity.py`; the session's
  check is a rule in `tools/private-mode/README.md` → *Which number*.
