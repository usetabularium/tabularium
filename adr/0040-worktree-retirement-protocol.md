# ADR-0040 — Worktree retirement protocol: one sanctioned teardown path (`checks/retire-worktree.sh`)

- **Status:** Accepted 2026-07-19; recursive removal reversed 2026-07-26
- **Date:** 2026-07-19
- **Deciders:** not recorded in the source (A1 followed an independent red-team)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

On 2026-07-19 (incident №2 of the concurrent-threads family, ADR-0036) two sessions were given the
same teardown target. One force-removed the worktree, with 10 uncommitted modified files, seconds
after the other had read them and while it was verifying their bytes. The end state was right
because a merge (`b0d8a45`) had already adjudicated that content: luck, not mechanism. Findings:

- Any check before destroying is a **snapshot**: nothing held the worktree between one session's
  check and the other's removal.
- **A supersession notice cannot land in time**: stopping a session needs a prompt, and a running
  sibling acts in seconds. Prevention must be structural or operator-side.
- Both sessions hand-rolled the same four-step checklist **divergently**; it existed only as prose,
  in three homes, and prose does not execute.
- `git worktree remove` deregisters the worktree, so the loser's re-check hit "unknown name" and
  trapped again.

## Decision

What holds now: the header and comments of `checks/retire-worktree.sh`, its line in
`checks/README.md`, the retirement bites in the `checks/selftest.sh` header and `CONTRIBUTING.md`
→ *When sessions run in parallel*. Points 2 and 3 keep the labels A1 and A2 that code and docs cite.

1. **One sanctioned teardown path** (2026-07-19): `checks/retire-worktree.sh <name-or-path>
   [--bank]` replaces every hand-rolled teardown.
   - One retirement at a time, under a lock taken before the registry is read; a stale lock is
     reported, never broken automatically.
   - **Merged gate:** HEAD must be an ancestor of `main`. A squash or rebase merge fails it by
     design, with no override flag: verify at artifact level, bank and finish by hand.
   - **Bank, never justify:** `--bank` keeps non-ignored loose work as a WIP commit and stops.
     Ignored files and submodule content refuse, since `git add -A` would omit them. "The merge took
     it" is never a reason to destroy bytes.
   - **Idempotent:** an already-retired target is a verified green no-op, so the race loser gets a
     proof, not a trap; an unknown name refuses (no vacuous green, ADR-0021).
   - Branch refs are never deleted; the main worktree and the caller's own are refused.
   - *Superseded by A1:* a dirty path passed as a **proven duplicate** when its disk bytes equalled
     `main` and its index equalled HEAD or `main`; the tree was removed with
     `git worktree remove --force`.

2. **A1 (2026-07-26): retained quarantine replaces recursive removal.** A byte proof covers one
   observation, not the destructive interval: ordinary writers do not take this lock, so unique
   bytes can arrive before the removal. Dropping `--force` was not enough: a red-team injected an
   **ignored** file just before an ordinary `git worktree remove`, and Git deleted it with exit 0.
   No further scan can make that interval safe. So any dirty state refuses, even bytes equal to
   `main`, and automation never runs `git worktree remove` on a live directory: a clean merged
   worktree is moved atomically into an owner-only quarantine, git-locked, rechecked and retained.
   Writes at the active path before the move go with it, later writes at that path stay there, and
   an open descriptor that still writes into the quarantine loses nothing because the quarantine is
   never deleted. A registered-but-missing entry is locked and retained too. Retirement means "out
   of the active namespace and retained under lock", not "bytes erased".

3. **A2 (2026-09-20): the quarantine lives in the common git dir**
   (`retired-worktrees/<name>`), not under the main checkout's gitignored `_archive/worktrees/`.
   Since ADR-0050, `_archive/` is a record category, so a retirement in a development checkout
   created a record path and guard L20 went red there and in every linked worktree. The
   new place is outside every work tree, never scanned by L20, never published, and the same in both
   instances. A pre-A2 quarantine is answered as a verified no-op.

## Alternatives considered

- **Repository-wide `git worktree prune` for a missing entry** (rejected 2026-07-19): it could
  erase another missing, unmerged entry.
- **Removal without `--force` after a clean scan** (rejected in A1): Git still deletes an ignored
  file created after the scan.
- **Moving the quarantine only in a development checkout** (rejected in A2): deriving the instance
  adds a state to hold for no gain, and a care checkout has no worktrees to retire.

## Consequences

- The teardown race is dissolved, not policed: the lock serialises, a rerun is a proof, and nothing
  live is recursively deleted.
- Operator-side prevention, not executable here: stop a session before spawning its successor, and
  the successor checks the session registry first.
- Tombstones match by name: a same-named worktree removed later outside the script matches the older
  line, whose timestamp and HEAD show it is stale.
- Since A2 the retained bytes are outside the whole-tree tarball, which leaves out `.git`: accepted,
  since admission requires a clean tree whose HEAD is already in `main`. `git clean -xdf` in the
  checkout cannot reach the quarantine.
