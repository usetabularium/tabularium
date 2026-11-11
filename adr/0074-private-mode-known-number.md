# ADR-0074 — Private mode learns a number with no date inside from a page

- **Status:** Accepted 2026-11-09 (operator); supersedes in part ADR-0068 point 2 (no slot for the number in any file) and ADR-0062 point 5 (the opt-in full number in the identifier file)
- **Date:** 2026-11-09
- **Deciders:** operator (+ assistant)

## Context

Masking finds the Polish number by its date of birth prefix. A number with no date inside, such as the
US Social Security number, has no such prior: rules by shape missed numbers and held clean pages in
every page round, and no open-source detector finds such a number in noisy OCR without knowing it.
The known value is the strong prior.

## Decision

1. **For a scheme whose number holds no date, the person's own number is kept in their identity file**
   (ADR-0075), undated since it is kept always, under the read guard's by-name rule like the rest of
   it, and read only by local tools that never print it. The private-mode marker is all it needs: a
   person with nothing else kept has a file holding only the number (operator, 2026-11-09).
2. **The tool reads it, the operator checks it.** The tool reads the number printed beside its label on
   one page the operator names, writes that reading into the form, and saves a picture of that spot
   beside it. The operator compares the two in their own editor and may correct digits; there is no
   blank line for typing a whole number (operator, 2026-11-09).
3. **Recorded only when found again.** The number is recorded only if masking finds it on the page it
   was read from; otherwise nothing changes. A new reading replaces the earlier one (operator, 2026-11-09).
4. **Masking searches that number, not a shape.** Whole, through OCR misreads and up to two wrong digits,
   on a line and across the line that continues it, plus its form masked to the last four; a strong
   label with no number near it still holds the page. Without a recorded number the pages wait
   (operator, 2026-11-09).
5. **The residue guard searches it** in the person's text, in any spacing and with no date filter, for
   private-mode persons only (operator, 2026-11-09).

## Alternatives considered

- Rules by shape alone: missed numbers and held clean pages in three page rounds (2026-11-08).
- An open-source detector: none found that works without the value (2026-11-08).
- The operator's own screenshot of the number: works for any layout, one more step every time.
- Typing the whole number, the opt-in once planned: a typo goes unchecked against any page.
- A setting of its own for a number-only person: one private mode already serves, its identity file
  holding only the number (ADR-0075).
- Recording a number that is not found again, with a warning: keeps a wrong number.
- Masking names and addresses by known value too: OCR letters collide, and masked names blind the
  catch for another person's page (operator, 2026-11-09).

## Consequences

- The full number is on disk, as the other kept details are; the read guard covers Claude Code only.
- A wrong number confirmed by mistake would make masking search the wrong value. The self-check
  allows for OCR's misreads, so it lets a slip of one or two digits through; the comparison with the
  picture and the operator's look at every page are the safeguards (operator, 2026-11-09).
- The US row returns to the number list only after a page round passes its marks.
- Verified by `tools/private-mode/test_identity.py` (`ReadNumber`), `test_redact_ids.py`
  (`KnownNumberTests`, the CLI refusal) and the picture rows in `tools/claude-hooks/test_registry_guard.py`.
