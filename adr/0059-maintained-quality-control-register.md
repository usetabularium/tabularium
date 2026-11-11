# ADR-0059 — Maintain a quality-control register with the product

- **Status:** Accepted 2026-09-19; register retired 2026-10-04
- **Date:** 2026-09-19
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The operator asked whether the caregiver-facing purpose was clear, for a control surface that
tracks gates as they come and go, and which design choices worked against that purpose. The prose
quality-gates overview had drifted: retired L17 shown as active, L21 and the eval and lineage
controls missing, CI's trigger misstated.

## Decision

What holds now: `README.md` → *Purpose*; `contributing/documentation.md` → *Current-state
ownership*; `CONTRIBUTING.md` → *Operating stance when building* and *Quality controls*;
`tools/claude-skills/guard-admission/SKILL.md`, installed by step 7c of
`checks/install-instance.sh`.

1. **The purpose opens `README.md`** (2026-09-19): continuity of understanding, informed
   participation and less work for the caregiver, within the intended-purpose and clinical limits.
   These are desired outcomes, not results the checks prove.
2. **Each kind of current fact has a named owner** (2026-09-20), which makes one fact, one home
   actionable. Other docs point to the owner and keep only action-critical instructions and
   historical evidence. No generator or gate.
3. **Build-session replies are contextual** (operator's choice, 2026-09-20): they report what is new
   and offer outside help when it is needed, not on every system question; evaluation-cost guidance
   and required notices keep their obligations. Why: it lifts an unconditional conversational
   burden.
4. **New controls pass an admission test** (operator ruling, 2026-09-24): never guard the operator's
   data from the operator; add complexity only where the safety-usability trade-off is clearly
   positive. Five questions, in development trees. A skill, not a hook: proposals happen in
   conversation, before any edit. A new or tightened control passes it first (reaffirmed by the
   operator, 2026-10-04).

### Retired: the control register (2026-10-04)

From 2026-09-19 a DEV-local control register (a JSON inventory and guide, not exported) gave each
control a permanent ID, status, scope, trigger, effect, protected failure, burden, limits and
sources; retired IDs stayed with reasons and successors, and planned controls counted as no
protection. Each control change updated it, and git, not dated copies, kept its history. It never
activated, disabled or certified a check; rules and code set behaviour. No generator, rendering,
dependency, scheduler or runtime gate; review checked it; ADR-0056's broader proposal was not
adopted. **Retired** (operator, 2026-10-04: development paperwork that touches no care is deleted;
git keeps it), with its IDs. The ownership rule has named no control inventory since (recorded
2026-10-11).

## Alternatives considered

All rejected on 2026-09-19.

- **Refresh the old overview:** lifecycle stays implicit, another prose copy of status drifts, and
  the operator asked for a maintained surface.
- **JSON plus a full Markdown table:** doubles editable state, or adds a build step if generated;
  queries plus a guide suffice.
- **The register as gate configuration:** changes enforcement and adds a failure path; the request
  was documentation.
- **Removing expensive safeguards at the same time:** evidence supported particular boundary
  changes and removals, several already made; remaining candidates needed their own scoped changes
  and validation. This change withdrew no protection.

## Consequences

- The hand-kept-register issue stayed open: a hand-kept register still needed review against the code, and the scoped
  ownership cleanup did not close it.
- The purpose statement changed no care rule and needed no new behavioural baseline.
- Contextual replies leave the care contract and patient-status upkeep unchanged; no measured gain
  in care or model compliance is claimed.
- The admission test fires only when a session recognises a proposal.
