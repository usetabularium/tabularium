# ADR-0027 — Consent-gated sensitive attributes (care surface free; export surface gated)

- **Status:** Accepted 2026-07-04; guard L9 retired 2026-09-06; point 3 superseded in part by
  ADR-0072 (no consent scan at the relay) 2026-11-08
- **Date:** 2026-07-04
- **Deciders:** operator (scope, marker and exemption confirmed 2026-07-04)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

> Deliberately **abstract** (the self-reference trap): this file ships in the export, so it names no
> attribute and carries no token.

## Context

An operator may disclose a sensitive personal attribute of a patient **for clinical use** and ask
that disclosing it on any **public or handover surface requires the patient's consent**. It is
recorded where care needs it: the person's own record, and the clinician handout the person gives
their own treating team, a disclosure the operator controls. This ADR makes that boundary
structural.

## Decision

What holds now: `checks/topics/relay-and-export.md`, the export-gate bites in `checks/selftest.sh`
and `_templates/HANDOUT-SOP.md` (*Standing reminders*).

1. **One token registry** (2026-07-04). The detection tokens (case-insensitive ERE, in each record
   language) lived in one consent class line in the deny-listed export script, the single home
   everything else read. ADR-0050 Part A2 later moved the registry outside every work tree, and the
   export script became tracked, token-free product.
2. **The export gate fails closed** (B1, 2026-07-04): it **aborts** on a class hit unless the line
   carries a consent marker (point 4). This guards against ALLOW-list drift; `patients/` is
   deny-listed anyway.
3. **Guard L9 at check time** (B2, 2026-07-04; retired 2026-09-06). L9 scanned every ALLOW-listed
   file for the class and went red on an unmarked hit, so drift showed at edit and commit time. It
   read tokens and ALLOW list from the export script, failed closed if either would not parse
   (ADR-0021) and skipped where the script was absent (the published skeleton). From 2026-07-05 it
   scanned the export as pruned, ending recurring false reds on files that never ship, and a grep
   error went red, not clean.
   - **Retirement condition** (2026-09-06): L9 existed because care and shipped surfaces shared one
     tree, so it retires, its class folding into the flip-time export gate, when ADR-0050 Part B
     completes with the records physically moved out: not on Part A, its register row or a
     migration marker. Until then L9 runs as specified, reading its class wherever the registry
     lives. That happened the same day; the class is now scanned at the export and over CARE→DEV
     relay prose (`checks/relay-scan.sh`).
4. **A consent marker lifts the gate** (format confirmed by the operator, 2026-07-04):
   `⟨consent: <attribute>-disclosure — patient, YYYY-MM⟩` on the line of the mention. It is
   greppable and records who consented and when.
5. **Scope: the publish surface only** (operator, 2026-07-04). Host-side handover files
   (`HANDOVER.md`, `cc-prompts/`) are not gated: local-only, they named the attribute *class*
   generically, never anyone's value, and gating them would have gone red at once.
6. **The care surface is exempt** (operator, 2026-07-04). `patients/**`, `handouts/clinician/**`
   included, records such an attribute freely where care needs it, and a clinician handout given
   to the patient's own doctors is operator-controlled disclosure, not publication. Removing it
   would degrade care; care utility wins (ADR-0013, 2026-06-08).
7. **An attribute disclosed for care but not consented for wider sharing** joins by appending its
   tokens to the same line; no guard code changes. A care record carrying it is marked
   `⟨consent-restricted…⟩`, so a human reviewer keeps it off the shared clinician handout: no scan
   covers the care surface, so the note holds that line.

## Alternatives considered

- **Firewall only, no L9** (rejected 2026-07-04): it runs only at publish, then held, so drift
  would sit unnoticed until a publish attempt. L9's own premise, the shared tree, ended 2026-09-06
  (point 3).
- **Tokens duplicated into `check.sh`** (rejected 2026-07-04): it ships (the self-reference trap),
  and two copies drift.
- **Gating handover files too** (rejected by the operator, 2026-07-04): point 5.
- **A per-file consent marker** (rejected for now, 2026-07-04): a same-line marker keeps the consent
  visibly attached to the exact mention.

## Consequences

- The boundary is executable (at session and publish time until 2026-09-06, at the export and the
  relay scan since) and auditable through the marker.
- A new consent-gated attribute appends its tokens to the same line; the mechanism is
  attribute-agnostic.
- Verified by the export-gate bites (`checks/selftest.sh --export`): an unmarked token aborts, a
  marker on its line lifts the gate; each bite writes its own synthetic registry.
