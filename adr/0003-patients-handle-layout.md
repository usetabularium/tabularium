# ADR-0003 — `patients/<handle>/` layout

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Each person's folder sat at the top level. The layout has to scale to N people without renaming,
and without forcing people to be named by role.

## Decision

What holds now: `CLAUDE.md` → *Layout*, `_templates/person/README.md`, `_templates/INTAKE.md` and
the handle check of guard L5 in `checks/check.sh`.

Each person's files live in `patients/<handle>/`, moved from the top-level per-person folders.
Handles are free-form, not role names; the board accepts only ASCII letters, digits, `_` and `-`,
so its separation check can match them.
