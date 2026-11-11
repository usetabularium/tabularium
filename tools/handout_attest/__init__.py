"""Sealed-handout attestation verification (ADR-0039) — the logic behind guard L15.

Verifies, per patient, that every sealed handout unit's deliverable bytes (PDF/TXT) are bound to
their fact-checked Markdown source via the renderer's `<stem>.attest.json` (schema
`tabularium-handout-attest/v1`), that the sealed lane's structure is sound (audience-outer
encounter dirs, no strays/phantoms/conflicts), and that products never cross into the evidence
lane (`med/sources/`). Flat files and `archive/` subdirs are the CLOSED legacy queue: only paths
recorded in the byte-bound `.legacy-frozen` inventory (ADR-0039 A6) are counted rather
than red. A lane file absent from the inventory (`legacy-lane-new-file`), an inventoried file whose
bytes changed (`legacy-bytes-changed`), a lane with files but no inventory (`legacy-freeze-missing`)
and a names-only v1 inventory (`legacy-freeze-unversioned`) are all RED — new handouts must be
sealed encounter units, never flat/archive files.

Stdlib only; fail-closed; category-only output (handle, relpath, hashes and detail are held
internally but never printed — guard output can cross an API/log boundary).
L15 proves METADATA/HASH consistency only — content-level audience judgment stays with the
fact-check gate + render QA (ADR-0034/0039).

Also home of the stable handout ID's Python check character (`handout_id.py`, ADR-0033) and the
read-only `next-id` command.
"""
