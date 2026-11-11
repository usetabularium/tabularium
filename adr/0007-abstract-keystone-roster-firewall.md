# ADR-0007 — Abstract `CLAUDE.md`, local roster and PII firewall

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

`CLAUDE.md` naming conditions violated its own preamble, and PII must never reach GitHub. At the
time, the sandbox could not run git.

## Decision

What holds now: `CLAUDE.md`, `_templates/INTAKE.md`, `.gitignore`, `checks/RECORD-SET` and
`contributing/instances.md`.

1. **An abstract keystone:** `CLAUDE.md` carries no names or conditions.
2. **A local roster** in `patients/README.md`, kept out of git by `.gitignore`, which mirrors
   `checks/RECORD-SET` (guard L20, ADR-0050).
3. **No PII to any git remote.**
4. **One environment runs git**, so work needs no hand-off between environments.

## Alternatives considered

- **Git run only by Claude Code on the host, because the sandbox could not run it** (the rule as
  first recorded; ended when ADR-0030 retired the split, 2026-07-05): work now happens in one
  environment, which has git.
- **`HANDOVER.md` as the hand-off file** (retired 2026-07-05, ADR-0030): one environment with git
  removed its purpose.
