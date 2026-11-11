# ADR-0069 — The handout verifier opens a private-mode person's filed masked pages

- **Status:** Accepted 2026-11-07 (operator); supersedes ADR-0034 in part (point 9); superseded in part by ADR-0075 2026-11-09 (point 2: the exception follows kept details, not the v2 tag)
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

ADR-0034 point 9 has the verifier open the original behind every medication, allergy, measured
value and safety-critical categorical fact, because a value misread at transcription can travel
unchanged into the profile, the medications list and the handout. For a private-mode person it
opened no page image, so that misreading passed the fact check. The masked pages a model saw are
filed under the person's `med/sources/_redacted/`, where the ownership ledger binds their bytes
(guard L13) and the read guard admits them, and the author's repair step already opens them. An
outside architecture review of 2026-11-07 raised the gap.

## Decision

1. **For a private-mode person the verifier opens the filed masked page in the original's place**
   (operator, 2026-11-07), never an original. A value under a mask is not on the page, so the row is
   `unsupported` unless another loaded source supports it; so is a row whose masked page is missing
   or unreadable, as for a missing original.
2. **Private mode v2 is excepted until local masking covers names** (operator, 2026-11-07). Its
   masked pages still show the person's names (`tools/private-mode/topics/kept-details.md`), so the verifier
   opens no page image for a v2 person, nor where the profile has anything shaped like the v2 tag,
   and ledgers those rows from the text layer with an advisory note.
3. **A filed masked page is outside the pipeline's gate** (operator, 2026-11-07). `verify_approved.py`
   must pass immediately before each model pass over the pipeline's approved sets
   (`tools/private-mode/README.md`). A page filed under `med/sources/_redacted/` has no attestation
   for it to check: it holds the bytes a model already saw at intake, and the ownership ledger binds
   them. That binding catches a page changed after filing at the next board run, not one filed
   unmasked, so only pages the gate passed are filed. This exemption never covers a v2 person: no
   session opens a v2 person's filed masked page.

## Alternatives considered

- **No page image for any private-mode person** (the rule from 2026-09-29, ADR-0034 point 9;
  reversed by the operator, 2026-11-07): a misreading that survived intake reached the seal while the
  masked page that would catch it was on file.
- **An ownership check immediately before each opened page:** it would catch a change after filing
  before exposure, where the board leaves that interval unchecked; neither sees a page filed
  unmasked. Not taken: no such change has been seen, and it adds a step to every verify.
- **Lift the v2 exception now:** the person's names would reach the AI service on every verify.
- **A missing masked page as an advisory note:** the unchecked reading this closes would stay open.

## Consequences

- For a v1 private-mode person, a misreading behind a value is caught before the seal; for v2 it
  stays uncaught here, as before.
- No new exposure for v1: the verifier sends bytes a model already saw at intake. No guard changes.
- A v1 handout leaning on a scanned value with no masked page on file fails until the page is filed
  or the value is restated at the grade its other support allows.
- Cost: image reads per verify, as ADR-0034 point 11 counts for everyone else.
- EV-12a and EV-12b test a person outside private mode and do not change; the deferred private-mode
  variant EV-12c is restated and stays unbuilt.

### Admission test (guard-admission)

(1) A misread dose reaching a clinician in a sealed handout for a private-mode person, by the path
ADR-0034 point 9 names. (2) Nothing refuses the operator; a missing masked page costs a filing or a
restated grade. (3) It acts at the verify before the seal. (4) Image reads only for rows behind
scanned sources. (5) No new control: the existing method extended to pages already on file.
