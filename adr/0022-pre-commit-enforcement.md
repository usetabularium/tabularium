# ADR-0022 — Executable pre-commit enforcement of the guards

- **Status:** Accepted 2026-06-13
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

ADR-0021 made the guards fail closed and named executable pre-commit enforcement as its gated
follow-on; this record is that follow-on.

## Decision

What holds now: `checks/README.md` → *Commit gate* (pre-push included),
`contributing/gates.md`, `CONTRIBUTING.md` → *Opening a build session* and the comments in
`checks/git-hooks/`; the HOOK bites are in `checks/selftest.sh`.

1. **A red working tree blocks the commit:** a tracked `pre-commit` hook runs `check.sh` on every
   commit.
2. **The override is two-factor and audited:** `TABULARIUM_SKIP_GUARD=1` bypasses `pre-commit`, and
   a paired `commit-msg` hook requires the message to name it, since git runs `pre-commit` before
   the message exists.
3. **The bite suite first ran at commit**, when staged paths touched `checks/`, `tools/` or
   `_templates/` (the selector was hardened against renames on 2026-07-26). Superseded by point 4.
4. **It moved to the push boundary** (2026-09-08): `selftest.sh` guards the guards, took minutes,
   and matters when work leaves the machine; `check.sh` stayed on every commit. The saving came from
   batching commits. `pre-push` refused any ref other than the checked-out commit, or a differing
   tracked tree, since the suite vouches only for the working tree (a reviewer's finding). The
   staged-path trigger and the maintenance window's suite half were deleted, not moved: the trigger
   existed only to hold the per-commit cost down, and an adversarial panel found three files the
   suite asserts against that could not fire it. Named cost: a broken guard could land locally,
   found at push. Superseded by point 6.
5. **A pushed ref was compared as the commit it resolves to** (2026-09-13, ADR-0054): git hands the
   hook an annotated tag's own object id, so every release tag had been refused. A ref resolving to
   no commit still blocked. Lapsed with point 6.
6. **No hook runs the bite suite** (2026-09-27): the per-push cost outweighed a gate the pull
   request already offers. It runs before a pull request is opened and in CI. The HEAD-only and
   clean-tree refusals went with it: they existed because the suite tested working-tree bytes. The
   renderer-skip block also went: a broken handout asset endangers no record and surfaces at render
   time, so it failed guard admission's first question. `pre-push` keeps the instance and record
   checks, now on each pushed ref's own tree. ADR-0054 point 7 lapses.
7. **Index materialisation was rejected** (2026-09-10; *Alternatives considered*). Its successor,
   the refusal rule handover 18 allowed (block a commit when a safety-trigger path differs between
   index and working tree), was dropped on 2026-09-20. The gate checks working-tree
   bytes, so it must not be called a committed-byte seal.

## Alternatives considered

- **Run the suite on the staged bytes, materialised in a scratch repository** (rejected 2026-09-10;
  do not revive it). Iterated three times, never under a hook, and dropped before a line was
  written: an adversarial review reproduced two writes into the real repository. An unchecked
  `mktemp` aimed `git -C ""` at it; a hook's absolute `GIT_INDEX_FILE` (under `git commit -a` and
  in any linked worktree) survived an `env -u` strip on `git init` alone. The cause is the shape:
  many git writes next to a live repository, the class of the 2026-08-23 `git reset --hard`
  incident.

## Consequences

- An ordinary commit cannot pass a red working tree; the sanctioned override leaves a mark in
  history.
- The installed hooks are copies that can drift from the tracked ones.
- A commit or a push can carry a broken guard until the pre-PR run or CI.
