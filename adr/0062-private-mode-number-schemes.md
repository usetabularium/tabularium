# ADR-0062 — Private mode names each person's number from a shared list of schemes

- **Status:** Accepted 2026-11-05; supersedes in part ADR-0029 point 7 (fixed residue shape); superseded in part by ADR-0073 (points 2 and 4) 2026-11-08 and by ADR-0074 (point 5) 2026-11-09
- **Date:** 2026-11-01
- **Deciders:** operator (+ assistant)

## Context

Private mode (ADR-0029) masks one designated identifier, and everything around it assumed one
country's number: the masking tool defaulted to it, and guard L10, the ownership verifier's residue
scans, the ownership writer's refusal and the v2 identity tool's refusal each hard-coded its
11-digit shape. A person with another country's number would get the wrong detector silently, and
L10 would not see their number in a transcription at all. The first public users will include
caregivers outside that country (operator, 2026-11-01: "include US, other EU").

## Decision

1. **One list, `tools/private-mode/id-schemes.tsv`**: per scheme a key, the OCR language data, the
   residue shape, and plain words. The shape is a POSIX extended regular expression Python reads the
   same way, so the shell guard and the Python tools share one text.
2. **A per-person tag** on the profile's private-mode line, beside the unchanged marker:
   `⟨id-scheme KEY⟩`, several as `⟨id-scheme KEY,KEY⟩` (operator, 2026-11-01: a person may have
   more than one number). No tag means the list's first row, so every profile written before the tag
   keeps its shape. On a line containing the exact private-mode marker, a tag with the recognised opening
   `⟨id-scheme` that is repeated, malformed or names an unknown key reds L10 and refuses in
   the Python tools. Tags on other lines and mistyped openings are ignored; if no recognised
   tag remains on a marker line, the profile uses the first row. This preserves the existing
   shape for people using the shipped scheme. An unsupported number must therefore also be
   recorded in words as specified in point 4. Before a second row ships, scheme selection
   must distinguish an intentional legacy default from an unreadable intended selection,
   without treating historical tag quotations as configuration.
3. **Every residue check reads the person's shapes**: L10 (shell), the ownership verifier and writer,
   the v2 identity tool. A joint note, whose owner is unknown, is checked against every private-mode
   person's shapes.
4. **The masking tool has no default scheme**: `--scheme` is required and its language comes from
   the list. This replaces a proposed red for an absent tag, which failed the guard-admission test
   (question 4): the choice is now made at each run from the profile, without a new red. A
   profile with no tag still means the first row, so a person whose number is not on the list
   says so in words on the private-mode line, and their pages wait. That statement overrides
   the no-tag default.
5. **This change ships the mechanism only**, with today's scheme as the one row (operator,
   2026-11-01: groundwork before the release, new numbers after). Decided for the follow-up, same
   date: first the US SSN with ITIN, the Czech/Slovak birth number and the French social security
   number; for a number with no date of birth inside, the person's full number may be stored, opt-in
   per person, as one more alternative in the existing owner-only identifier file; a US page's last
   four SSN digits are masked when printed in SSN shape or beside its label; label words for a new
   scheme ship with it, while the operator's own scheme's label stays local (a firewall token); each
   new scheme is tested by unit cases and a small rendered page round before it is offered.

## Alternatives considered

- An instance-wide setting: fewer places, but a household can mix countries, and L10 already works
  per person.
- Red when a marked profile has no tag (one-time migration of existing profiles): fails the
  guard-admission test's net-benefit question; the tool's required `--scheme` does the job.
- A separate shape per checker: the drift that this list removes.

## Consequences

- Adding a country is a row in the list plus its detection in `redact_ids.py`, with tests; the guards
  follow without change. A shape with no checksum and no date of birth inside (9 digits) needs
  bounding in the list so L10 does not red on longer numbers.
- One more file every private-mode check depends on; unreadable or malformed, it reds the board for
  private-mode persons only.
- ADR-0029 points 2 and 7 point here. Verified by the L10 bites in `checks/selftest.sh` and the list
  and refusal tests in `tools/private-mode/test_identity.py` and `test_redact_ids.py`.
