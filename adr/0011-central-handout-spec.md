# ADR-0011 — Central handout spec

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The first generated PDFs failed concretely: broken tables, cluttered data, invisible rigor, and
patient text that was over-sentimental and over-explaining. Codifying the fixes keeps the next
handouts from repeating them.

## Decision

What holds now: `_templates/HANDOUT-RULES.md` and the `Handout calibration` line of
`_templates/profile.md`. Voice, filenames and render conventions are ADR-0026's.

1. **One central handout spec**, `_templates/HANDOUT-RULES.md`, plus a per-person `Handout
   calibration` field.
2. **The patient register is calibrated** to literacy and cognition (lean or explanatory), with
   warmth once and medical scope only.
3. **Clinician handouts** use structured tables, a one-line evidence key and the standard closing
   note, showing rigor once (ADR-0026).
4. **Render and eyeball** each handout.

## Alternatives considered

- **A visible methodology appendix** (the rule as first recorded; replaced 2026-10-04, ADR-0026):
  the evidence key and closing note show rigor once without a credibility pitch.
