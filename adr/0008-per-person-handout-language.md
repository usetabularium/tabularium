# ADR-0008 — Per-person handout language

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded for point 1; the operator for point 2
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

A person's clinician may use another language; language is a per-person fact.

## Decision

What holds now: `_templates/profile.md` (*Identity & basics*), `_templates/HANDOUT-RULES.md`
(*Audience, language and voice*), `_templates/handout-patient.md`, `_templates/handout-clinician.md`
and their `.pl.md` siblings, `_templates/handout-assets/render_handout.py` (the footer strings) and
`CLAUDE.md` (*Conventions*).

1. **Handout language is set per person** (date not recorded). The `Patient language` and
   `Clinician language` fields in `profile.md` set it; it is never hard-coded. Why: a person's
   clinician may use another language; language is a per-person fact.

2. **English is the base template; Polish is one localisation** (operator, 2026-10-27).
   `handout-<audience>.md` is the English template and `handout-<audience>.pl.md` the Polish one;
   any other language translates the English template. The renderer's footer is English when `lang`
   is absent or unsupported, and Polish with `lang: pl`. Polish terms and examples left the
   person-facing templates (profile, filing procedure, handout rules). Why: the public version needs
   no Polish defaults.

## Alternatives considered

- **Polish hard-coded in the templates** (the rule before this record; replaced by point 1, date not
  recorded): language is a per-person fact.
- **Polish as the base template, English as its `.en.md` sibling** (the rule from an unrecorded
  date; replaced by the operator, 2026-10-27): the public version needs no Polish defaults.

## Consequences

- ADR-0031's S-doc list (point 6) covers the `.pl` siblings where it says `.en`.
