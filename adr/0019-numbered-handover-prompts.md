# ADR-0019 — Numbered, append-only handover prompts

- **Status:** Accepted 2026-06-13; retired 2026-10-04; superseded in part by ADR-0030
  2026-10-24
- **Date:** not recorded in its register row (the register was backfilled 2026-06-07)
- **Deciders:** not recorded for points 1 and 3; the operator for points 2, 4 and 5
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Host-side prompts were the audit trail of what changed the repository from outside Cowork. The rule
was recorded because it was nearly broken: the 2026-06-13 commit task was first captured only
inline in `HANDOVER.md`.

## Decision

What holds now: `contributing/documentation.md`, `CONTRIBUTING.md` → *Open work*,
`contributing/instances.md`, `checks/RECORD-SET` and `checks/PUBLISH-HOLD`. The care freeze and
push ledger in point 2 still stand; point 5 states the current development rule.

1. **Claude Code handover prompts are numbered and append-only** (date not recorded), like ADRs,
   so the trail is greppable and gap-evident: `cc-prompts/NNN-<slug>.md`, next free three-digit
   number, never reused; a superseded prompt says so in its body and is never renumbered or
   deleted; no task is left only inline. The register and rule lived in `cc-prompts/README.md`.
2. **Care keeps the history, development the convention** (operator, 2026-09-07, Option A, after
   the 2026-09-06 split). `cc-prompts/` had become a care-only record path, out of reach of the
   development instance where the export runs. So: `cc-prompts/` is frozen at 036 as care history,
   nothing added or renumbered; development continues as numbered `_inbox/` handovers under one
   register and the same rules; the flip-time export runbook, once `cc-prompts/001`, is handover 28;
   `checks/PUBLISH-HOLD` is both the ledger of executed pushes and the sentinel that gates them. The
   rationale stands; only the folder differs per instance.
3. **Handovers are cited by number** (2026-10-04), since an archived handover's path went stale.
4. **Numbering retired** (operator, 2026-10-04). A handover is a plain note with a kickoff block,
   deleted when its work lands; no register, no numbers.
5. **No development inbox** (operator, 2026-10-24). For development, point 4 is superseded by
   ADR-0030 point 6: a handover is the brief one session passes another, plus the pull request body.

## Alternatives considered

- **Leaving a task only inline, or renumbering or deleting a superseded prompt:** ruled out by
  the original numbered, append-only convention, to keep the trail greppable and gap-evident.
- **Option A** was chosen by the operator on 2026-09-07; alternatives are not recorded.

## Consequences

- Prompts 001–036 stay care history, never exported. A "handover N" in a tracked file names a note
  that no longer exists; its outcome is in the citing text, the ADRs and git (ADR-0030 point 6).
