# ADR-0028 — L5 person-separation guard: evidence-layer (med/sources/) exemption

- **Status:** Accepted 2026-07-04
- **Date:** 2026-07-04
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

L5 searches each person's `.md` files for other people's folder handles, as whole words. A new
handle that was a common first name turned the tree red: unrelated clinicians with that name appear
in other people's grade-A transcriptions (`med/sources/**.ocr.md`), an evidence layer never
rewritten, so no edit could clear it. Every later common-first-name handle would collide again.

## Decision

What holds now: the L5 row of `checks/README.md`, the L5 section of `checks/check.sh` and
`_templates/INTAKE.md` §1; the bites are in `checks/selftest.sh`.

1. **L5 skips hits under `patients/*/med/sources/`** (2026-07-04), filtering only after a successful
   grep, so a grep error still fails loud; every layer the assistant writes stays scanned. L5
   targets assistant-authored cross-contamination; a third party's name in a verbatim transcription
   is reality.
2. **A misfiled scan is not L5's case:** it carries the other person's real name, not their handle.
   Intake's page-1 identity check (ADR-0023) first owned it; since 2026-09-19 the operator's
   placement of the document and the ownership ledger do (ADR-0037, guard L13), and no session
   reads identity off a scan.
3. **A shared first name is never a bare handle** (2026-10-26, cold review; wording, no guard
   change). Outside `med/sources/`, such a handle (`mark` beside `mark-b`, identical twins) reds the
   other person's own profile, with no way to clear it. ADR-0037 point 15 covers people who share a
   name and birth date.

## Alternatives considered

- **Rename the handle** (add digits): moves the cost onto naming forever, re-collides with every
  common-name handle, needs folder moves on the host, and gives up the operator's free choice of
  handle (ADR-0003) for a guard detail.
- **A per-file whitelist:** every later scan naming a same-named third party reds again and needs an
  edit; whitelists rot.
- **Matching real names:** needs a registry of full names the guard can read, a concentration of
  personal data the system avoids.

## Consequences

- Common-first-name handles are safe, and the evidence layer stays immutable.
- Limit: L5 does not scan assistant-written text placed in `med/sources/`.
