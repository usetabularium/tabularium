# ADR-0024 — CC handover routine for sandbox-limited tasks

- **Status:** Deprecated 2026-10-11 (accepted 2026-06-21)
- **Date:** 2026-06-21
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Cowork, the desktop sandbox, hosted reasoning and orchestration, but hard limits kept blocking its
tasks. One session hit five: no `git`, no root for installs, no file delete on mounts, a shell
ceiling of about 45 s, and a connector capping downloads at 10 MB and returning bytes as base64
into context. Each hand-off to Claude Code (CC) was improvised again; ADR-0019 numbered the
host-side prompts but set no routine for when, in what shape and with what guardrails. The routine
was borrowed from a sibling project's exemplar and trimmed, as this repository was local-only, with
no remote, pull requests or CI (ADR-0017).

## Decision

**A standing CC handover routine** (2026-06-21), its skeleton in `cc-prompts/README.md`.

1. **Triggers.** Hand off when the sandbox structurally blocks the task: `git`, an install or root,
   deleting or moving files on a mount, the shell ceiling, bulk or large-binary transport, or bulk
   vision-OCR ingestion (ADR-0023 Stage 1). Reasoning, single files Cowork can write directly,
   profile and handout work and chat-only output stay in Cowork.
2. **Shape.** One numbered, append-only `cc-prompts/NNN-<slug>.md` per hand-off (ADR-0019): scope,
   trigger, inputs, procedure, person-scope guardrail, verification, status. The pasted prompt is
   the payload; CC works on the host, so the bytes go local first, never through the connector.
3. **Tiers, borrowed.** *Push back:* CC verifies and strengthens the reasoning, documents a
   fixable inconsistency and proceeds. *Flag and pause:* a false load-bearing premise, a missing
   prerequisite or an outward-facing or hard-to-reverse action stops CC for the operator; no
   guessed default. *Verify before commit:* the prompt lists the checks; `checks/check.sh` is green
   first (ADR-0022).
4. **Person scope, the first rule.** One person per hand-off: the prompt names them, and CC refuses
   paths outside `patients/<handle>/`. The exemplar had none; person mix-up is this system's
   highest-severity error (ADR-0002).
5. **Status discipline.** Each prompt carries a Status line (`READY`, `DONE (sha, date)` or
   `SUPERSEDED by NNN`) and a register row, so the folder is a truthful backlog without `git log`.

### Disposition (deprecated 2026-10-11)

- **Legacy from 2026-07-05** (ADR-0030): every trigger was a sandbox limit, and the substrate split
  was retired, leaving one environment with `git` and the shell. The routine stopped routing daily
  work; the shape still bound, and ADR-0030 left a formal deprecation to the operator.
- **2026-09-07:** "local-only: no remote, PR or CI" stopped holding for DEV, which since the
  2026-09-06 split has a private remote and CI (ADR-0050 Part B). The shape never depended on it.
- **2026-10-11, drift:** handover numbering and its register were retired on 2026-10-04
  (ADR-0019), `cc-prompts/` is frozen CARE history, no build document outside the ADRs names the
  tiers, and DEV lands every change through a branch, a pull request and CI (ADR-0031).
- **Deprecated** (operator, 2026-10-11) after a break test that day found only stale pointers to
  the flip runbook, since re-pointed. Nothing here binds by its own authority, and what survives has
  its own home: one person per hand-off (ADR-0002, the care contract) and a green board before
  commit (ADR-0022). Deprecated, not superseded: no later decision replaces it.

## Alternatives considered

- **Keep improvising** (rejected 2026-06-21): the limits recur, so the cost recurs, and an ad hoc
  hand-off is where a person-scope or verification step gets skipped.
- **The exemplar's full two-lane machinery: pull requests, CI, branches, late binding** (rejected
  2026-06-21): over-built for a local-only, single-operator repository; only the format and tiers
  were kept. On 2026-09-07 the rejection stood by choice, since a review lane added little beyond
  the guards and the ADR-0022 commit gate; overtaken for DEV by CI on 2026-09-06 and pull requests
  on 2026-09-07 (ADR-0031).
- **One large inline `HANDOVER.md` section** (rejected 2026-06-21): it breaks ADR-0019's numbered,
  greppable, gap-evident trail.

## Consequences

- While live, a sandbox wall was a known trigger with a ready format, and hand-offs were uniform,
  auditable and person-safe. The trigger list was to grow as limits surfaced.
