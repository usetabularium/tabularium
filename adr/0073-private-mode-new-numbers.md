# ADR-0073 — Private mode reads its number tag strictly, before a second number ships

- **Status:** Accepted 2026-11-08 (operator); supersedes in part ADR-0062 points 2 and 4 (tag reading, words-only "not on the list"); point 2 superseded in part by ADR-0076 2026-11-10 (the pages wait); points 1 (no tag means the first row) and 2 superseded in part by ADR-0077 2026-11-10 (exact tokens only)
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

ADR-0062 reads a marked profile without a tag as the list's first row. Once a second row ships, a
mistyped or wrapped tag would read as that first row, so masking, guard L10 and the residue checks
would look for the wrong number. ADR-0062 point 2 asks for this to be settled first.

## Decision

1. **The tag is read strictly, the same way in guard L10 and the Python readers, on the file's
   bytes.** On the private-mode marker's line, anything shaped like the tag, and any key of the list
   outside the one exact tag, is refused, never read as absent. In the Identity section, the exact
   tag opening on another line is refused. Elsewhere a tag is plain text, so change-log quotes stay
   free. No tag still means the first row, with no migration (operator, 2026-11-07).
2. **"Number not on the list" on the marker line names no scheme:** with no tag, no residue shape
   and no first-row default for that person. Beside a tag, the tagged schemes are searched as usual.
   Either way the person's pages wait: the masking tool is not run while the phrase is there
   (operator, 2026-11-08).

## Alternatives considered

- Red every marked profile with no tag: every existing profile reds once, for no harm.
- Read a tag anywhere in the profile: change-log quotes become configuration.
- "Not on the list" read by sessions only: L10 keeps searching that person's text with the first
  row's shape, a false alarm with nothing to fix.
- Refuse a tag beside "number not on the list" (proposed 2026-11-07; changed by the operator
  2026-11-08): it switched off the board's search for a listed number.

## Consequences

- A mistyped tag costs one red with a plain next step instead of a silent wrong shape. Prose naming
  an "ID scheme" belongs off the marker line.
- Verified by the L10 bites in `checks/selftest.sh` and the `IdSchemes` tests in
  `tools/private-mode/test_identity.py`.
