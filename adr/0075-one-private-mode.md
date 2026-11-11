# ADR-0075 — One private mode: the identity file says what else is kept

- **Status:** Accepted 2026-11-09 (operator); supersedes in part ADR-0029 points 13.1–13.3 (the v2 tag, `dob=exempt`, the cutover date), ADR-0068 point 3 (the separate cutover step) and ADR-0069 point 2 (the verifier's exception follows kept details, not the tag)
- **Date:** 2026-11-09
- **Deciders:** operator (+ assistant)

## Context

Private mode had two levels: the marker alone (the designated number kept from the AI service), and a
second level set by a tag beside it, with a person-wide cutover date, an optional date-of-birth
exemption and an identity file. Two modes meant two setups, a tag and a file that could disagree, and a
later migration from one to the other. The operator asked for one mode in which they are asked which
details to keep (2026-11-09).

## Decision

1. **The marker alone switches private mode on**, byte-identical; the number is always kept. Every check
   that keys on the marker is unchanged.
2. **What else is kept is what the person's identity file holds**, and nothing else decides it: a kind of
   detail with a value there is kept; no file, nothing besides the number. The second-level tag, its
   `dob=exempt` option and the cutover date are retired; a date of birth left visible is simply not in
   the file.
3. **Setup asks once, as a tick-list in chat**, which details to keep; the form then holds only those
   parts, and nothing ticked means no form (operator, 2026-11-09).
4. **Taking in the form also swaps the details out of the profile and medication list**, in one step
   and all or nothing (operator, 2026-11-09): a swap that would break a file reference records nothing.
   `swap` remains for a terminal entry or an interrupted run. A name the handle spells cannot be kept.
5. **Each value counts from the day it was recorded** (operator, 2026-11-09): the residue guard looks
   for it in the working record always, elsewhere only in text dated or written on or after that day
   (a file's name date or its last write, the later; operator, the same day).
6. **The tool keeps a sign on the private-mode line**, `⟨withheld:details-kept⟩`, while anything is
   kept (operator, 2026-11-09, after a cold review): every session reads the profile, so it learns of
   kept details that never stand there. It is derived, not a setting: guard L10 reds the sign without
   the identity file (or any placeholder in the profile or medication list without it), and a file
   keeping something without the sign, so a lost file never switches the scan off. It replaces the
   red for a tag without its file.
7. **No conversion**: no person on the operator's care install had the second level (counted without
   reading content, 2026-11-09). A file in the old format is refused with its way out: fill in the form
   again.

## Alternatives considered

- Keep two levels: two setups and a migration later.
- A tag listing the kept kinds on the profile: a second truth that drifts from the file.
- One person-wide setup date: a detail added later reds notes written before it, forcing history edits.
- The form alone, every part shown, blank meaning visible: always a form, even when nothing is kept.
- A one-time conversion command: nobody to convert.
- Every session runs the status command first instead of a sign: one more step each time, none for a
  session without a shell, and a lost file still unnoticed.

## Consequences

- Fewer states: no tag to parse strictly, no exemption flag, no red window between setup steps.
- The identity file's format gains a date per value; the old format is refused.
- An old note copied or restored with a new write date can red for a detail it held before the detail
  was recorded; the next step is the placeholder or the dated waiver.
- The read guard keeps its dormant check for the retired tag (it is frozen); with no such tag in use it
  refuses nothing new.
- Held by guard L10 (the kept-details scan), the read guard's by-name rule, `tools/private-mode/test_identity.py`
  and the L10 bites in `checks/selftest.sh`.
