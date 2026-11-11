# ADR-0036 — Concurrent-threads working-tree safety

- **Status:** Accepted 2026-07-08; D3 (guard L12) retired 2026-09-06
- **Date:** 2026-07-07
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Several assistant threads worked at once on one shared working tree. One session ran four, two of
them editing the export firewall, and showed three gaps at the highest-stakes point:

1. **No conflict detection on the firewall.** `checks/publish-skeleton.sh` held the raw token
   registry and was untracked by design, since git must never store the tokens (ADR-0017).
   Overlapping edits were silent last-writer-wins, with nothing to diff or recover; the two edits
   held only by falling in disjoint functions.
2. **A green `selftest.sh` did not prove no token was dropped.** It protects only the tokens it
   tests, so dropping an untested one leaves the firewall fail-open with every guard green.
3. **Ambiguous commit ownership.** A coordinator committed another thread's staged changes first,
   turning that thread's commit into a no-op (`rc=1`, "nothing to commit"): benign with identical
   bytes, but a stale copy would have passed as success.

The ADR-0022 pre-commit gate held and is kept: its guards run the real scripts (that session, a
bash fault passed `bash -n` and failed only at run time). The `snapshot.sh` pre-edit copy was the
only recovery for a clobbered untracked file.

## Decision

Concurrent editing of an untracked high-stakes file is a hazard class of its own. Proposed on
2026-07-07 as analysis in three tiers, cheapest first; on 2026-07-08 the operator delegated the
choice to an Opus panel, and D3 was built while D1 and D2 became standing conventions. Points 1–3
are D1–D3; working form: `CONTRIBUTING.md` → *When sessions run in parallel* and *Retiring a
session — the certifying pass*.

1. **D1 — one committer per file-set** (convention). After any commit the owner checks that
   `HEAD:<file>` holds the intended content, and reads `rc=1 "nothing to commit"` as ambiguous:
   inspect `git log`, never take it as failure or as success.
   - **Own-worktree editing replaces the shared-tree form** (operator, 2026-10-24). Every session
     edits in its own worktree, so no thread stages and hands off; the stash recipe that carried D1
     went too, since every worktree shares the stash list. "Never commit another session's work"
     and the `HEAD:<file>` check stand.
2. **D2 — thread retire checklist** (convention). A thread records its base commit and intended
   file-set at start. At retire it runs a fresh board (and the bite suite if it touched `checks/`),
   lists concurrent commits with `git log <base>..`, audits what is dirty and whose, and checks
   that its own content survived.
3. **D3 — a registry integrity checkpoint, built as guard L12** (2026-07-08). The panel was
   unanimous that D3 is load-bearing: a silent token drop voids the firewall with every guard green,
   the risk was live under concurrent threads, and one checkpoint covers all five token classes
   with no carve-out. L12 kept salted SHA-256 digests in a tracked sidecar, refreshed only
   deliberately, failing closed. Digests were **per class, never per token**: a mismatch names the
   changed class, which defeats a blind refresh, and a per-token digest of the co-located date
   material would be guessable. L12 detected; the pre-edit snapshot recovered. A sibling
   session-time identity guard was deferred the same day (ADR-0013).
   - **Extended to the required ALLOW export contract** (2026-07-17): deleting a path from the
     untracked `ALLOW` array also removed it from the existence check, so an export could omit a
     keystone file and report clean. The sidecar gained a digest of the ALLOW block.
   - **Bound to the live copy array** (2026-07-19) by an adjacent `readonly ALLOW`, so a later reset
     of the array cannot change what is copied while the digest stays clean.
   - **Retired 2026-09-06, when ADR-0050 Part B completed and the records moved** (not on Part A,
     its register row or a migration marker; L12 ran unchanged until then). Its premise, an
     untracked file without git history, ended: the registry moved outside every repository and
     the export script became tracked. A salted digest of the real classes is PII-derived material
     DEV must not hold, so L12, its sidecar and its refresh tool were deleted.
4. **ALLOW entries are registered at merge time, never ahead of the artifact** (2026-07-17). The
   first ALLOW checkpoint found one registered before its branch merged (`tools/handout_attest`,
   ADR-0039), removed until that merge on 2026-07-18: the contract describes the tree as it is. On
   2026-09-06 the rule moved with the ALLOW contract to the export script as the flip-time gate.
5. **A care session that cannot see other sessions assumes none** (2026-10-25). Asked to make sure
   no other session writes records, a session that could not check (the chat client sees no other
   session) had asked the operator, who cannot know either. It now checks where it can, otherwise
   assumes none and re-reads each file right before editing; a file changed since it was read means
   another writer, so it stops and says so. Working form: `CLAUDE.md` → *Safeguards*.

## Alternatives considered

- **Track the export script so git detects conflicts** (rejected 2026-07-07): it would store the raw
  token set, the leak ADR-0017 exists to prevent. D3 bought detection without prevention,
  leak-safely. The premise ended on 2026-09-06 (point 3).
- **Serialize firewall edits through one owner or a lock file** (parked 2026-07-07): stronger for
  prevention but heavier process; a possible escalation of D1.
- **Lean on `selftest.sh` alone** (rejected 2026-07-07): necessary for behavioural regressions, not
  sufficient for silent drops (event 2).
- **PR or cloud-CI serialization** (rejected for the working repository, ADR-0017 and ADR-0031:
  cloud runners would receive the PII tree). Reversed for DEV on 2026-09-06 and 2026-09-07
  (ADR-0031 point 3); every DEV change now lands through a pull request and CI (`CONTRIBUTING.md` →
  *How a change lands*).

## Consequences

- D1 avoids stale-commit races and D2 makes a thread's close auditable; they and point 5 are
  conventions, not machine-enforced. L12 made a silent clobber loud while it ran, at the cost of a
  tracked sidecar and the discipline to refresh it.
- Since 2026-09-06 a silent change to a class value in the out-of-tree registry is not detected
  (`checks/topics/relay-and-export.md` → *What is no longer detected*).
