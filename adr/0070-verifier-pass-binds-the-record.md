# ADR-0070 — A fact-check pass expires when the record changes

- **Status:** Accepted 2026-11-07 (operator); supersedes ADR-0034 in part (point 2) and ADR-0039 in
  part (point 3, the control block)
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

The seal gate accepts a passing sidecar while the handout's bytes are unchanged (ADR-0034 point 2,
ADR-0039 point 3). A draft may wait unsealed across sessions (`HANDOUT-SOP.md` step 7) and every
session refreshes the profile, so a dose or an allergy changed after the verify could reach a sealed
handout checked against the older record. The gate had no record input. An outside architecture
review of 2026-11-07 raised the path; no incident is recorded.

## Decision

1. **The sidecar binds the record it was checked against** (operator, 2026-11-07). Its control block
   gains two lines after `must_fix_open`, `profile_sha256` and `medications_sha256`: the digests of
   the record bytes the verifier checked, copied from the bundle's file headers in bundle mode or
   taken before reading in files mode. The seal gate re-hashes both files and refuses unless they
   match when it runs; the author then runs a later round, which re-checks what the change could make
   wrong and carries the rest (ADR-0034 point 13).
2. **Both files, whole** (operator, 2026-11-07). Any byte change in either expires the pass; sources,
   the library and other files do not. Excluding the profile's change log could spare rounds after
   log-only edits, but adds section-boundary parsing; whole-file binding accepts those extra rounds.
3. **A sidecar without the two lines seals as before** (operator, 2026-11-07), so a draft verified
   before this change keeps working, and sealed units are untouched: guard L15 hashes a sidecar and
   never parses it. A control block is exactly three or exactly five ordered lines, then a blank
   line; anything else refuses.

## Alternatives considered

- **A control block binding the handout alone** (the rule from 2026-07-06, ADR-0034 point 2 and
  ADR-0039 point 3; reversed by the operator, 2026-11-07): a pass outlived the record it was checked
  against.
- **Bind `medications.md` only:** allergies, diagnoses and measured values live in the profile.
- **Bind only the record lines the ledger cites:** the verifier would choose its own binding, and an
  omission would go unseen.
- **Refuse a three-line sidecar** (declined by the operator, 2026-11-07): every draft waiting at
  adoption would need another round.
- **A board warning on a stale pass:** the harm is at the seal, which refuses there.

## Consequences

- A seal straight after the pass costs nothing more. After a record edit, even one unrelated to the
  handout, it costs one later round, change-only; the SOP's seal step says to seal before editing
  the record.
- A three-line sidecar binds the handout alone, whether written before this change or by a verifier
  that left the lines out; nothing tells the two apart.
- In bundle mode the bound record bytes are the ones the verifier read, so a record change after
  assembly now refuses at the seal; other bundled files keep the stamped, not re-checked, window.
- EV-12's session has no shell; its note hands it the two record digests as well as the handout's.
  Verified by the seal-gate tests in `tools/handout_attest/test_attest.py`.

### Admission test (guard-admission)

(1) A dose or allergy changed after a PASS reaching a clinician in a sealed handout that states the
older value: drafts may wait across sessions, and each session refreshes the record; a credible
path an outside review found, no observed incident. (2) It refuses a seal, never a read; the way
forward is one round. (3) It acts at the seal, the point of hand-over. (4) The usual path, a seal
straight after the pass, never meets it; on the waiting path it costs one change-only round (a
fresh verifier starts at about 75 K tokens, ADR-0034 point 11), against a silent stale dose. (5) It
extends the one existing seal gate, adds no guard, and prints one message naming one next step; a
legacy sidecar prints nothing.
