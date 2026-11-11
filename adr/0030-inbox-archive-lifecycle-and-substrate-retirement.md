# ADR-0030 — Transient-helper lifecycle; Cowork⇄CC substrate retired; `docs/` repurposed

- **Status:** Accepted 2026-07-05; DEV helper lifecycle retired 2026-10-04; DEV `_inbox/` lane
  retired 2026-10-24; CARE's top-level `_inbox/` removed 2026-10-25; point 3's roadmap
  clause deprecated 2026-11-08
- **Date:** 2026-07-05
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

1. **`HANDOVER.md`** (284 lines) existed only for the **two-substrate split**: the in-app sandbox
   could not run git, so its record work went to a host git environment through this file and
   numbered `cc-prompts/`. Work now happens in one environment with git. The file had become a
   session log duplicating git and the `cc-prompts/README.md` register, with one live loop left
   (the ADR-0018 L3 build-or-re-defer decision).
2. **Transient helpers had no home**: notes, coordination docs and one-off scripts sat at the root,
   where they drift and pass for canonical structure.
3. **`docs/` had changed role**, from "retired exploration — do not load" to the product roadmap
   and private strategy notes, but `CLAUDE.md`, `.gitignore` and the publish firewall still said
   otherwise and kept stale entries for four files that had moved there.

## Decision

What holds now: `contributing/documentation.md` (the doc table and *Conventions*),
`CONTRIBUTING.md` → *Open work*, `contributing/instances.md` (the layout), `checks/RECORD-SET`,
`.gitignore` and the DENY list in `checks/publish-skeleton.sh`.

1. **A lifecycle for transient helpers** (2026-07-05). They stage in a gitignored top-level
   `_inbox/` and retire into `_archive/<kind>/` (`handover/`, `cc-prompts/` or a new kind), after
   any still-live decision has moved to its canonical home: the archive is cold storage, not a
   tracker. Both folders hold PII-laden history, so both are gitignored and publish-DENY-listed. The
   top-level `_inbox/` is not the per-person intake tray `patients/<handle>/med/_inbox/`
   (ADR-0023). Retired in stages by points 5–7; the repo-root `_archive/` stays a CARE record
   path.

2. **The Cowork⇄Claude-Code two-substrate split is retired** (2026-07-05). `HANDOVER.md` went to
   `_archive/handover/`, its L3 loop to `docs/ROADMAP.md`. The `cc-prompts/` register (ADR-0019)
   stayed live; a done or superseded prompt file retires to `_archive/cc-prompts/` with its number
   and register row kept (archival is not deletion), and an open task keeps its file. The hand-off
   routine (ADR-0024) became legacy: it no longer routes daily work, but its prompt shape and green
   gate before commit still bound a numbered task until numbering was retired on 2026-10-04
   (ADR-0019). Recorded 2026-10-11: the register has been frozen at 036 as CARE history since
   2026-09-07 (ADR-0019).

3. **`docs/` classified honestly** (2026-07-05): roadmap and private strategy, local-only
   (gitignored, publish-DENY-listed). `docs/ROADMAP.md` is the product backlog; `docs/strategy/`
   stays private. The
   stale entries for the four moved files and `HANDOVER.md` went, covered by the blanket rules.
   Recorded 2026-10-11: from ADR-0050 (2026-09-06) DEV tracked four product files there.

4. **Handover retirement is monitored, not guarded** (2026-07-23). After a closed handover sat
   un-retired for days, retirement being a manual move with no ledger, an ACTIVE/RETIRED register, a
   `**Closes:** KI-NNN` field and `checks/handovers.sh` were added. Deliberately not a `check.sh`
   guard (as for `confirms.sh`): retirement is housekeeping, not record integrity, and a guard would
   block an unrelated care-record commit until someone moved a file. Since ADR-0050 no record is
   committed, so the reason reads (2026-09-08): a monitor must never red an ordinary session's
   board.

5. **The DEV helper lifecycle is retired** (operator, 2026-10-04). The repo-root `_archive/` being a
   CARE record path since ADR-0050, DEV first retired helpers into `_inbox/_archive/<kind>/`; the
   same day, that gave way to deletion: a finished DEV handover is deleted, not archived or
   registered, and point 4 and `checks/handovers.sh` no longer apply.

6. **The development tree's `_inbox/` is retired as a working lane** (operator, 2026-10-24). It
   dated from when one assistant filed instructions for another; no check read it, worktree
   sessions could not write it, spent notes piled up, and tracked files pointed into its untracked
   archive. A handover is now the brief one session passes another, plus the pull request body;
   findings go there, in an ADR amendment (a new ADR since ADR-0061) or in a known-issue row;
   private planning goes in named `docs/` files, then tracked on the private remote and denied by
   the export (untracked since 2026-10-28: `.gitignore`). No TODO file replaces it: open work stays
   in the known-issue register and the roadmap. The archive, its register and the spent notes were
   deleted from the main checkout. This supersedes ADR-0019's 2026-10-04 plain-note model for
   development: "handover N" in tracked files names a note that no longer exists, whose outcome is
   in the citing row, the ADRs and git history.

7. **CARE's top-level `_inbox/` is gone too** (operator, 2026-10-25, after a tested panel with two
   break rounds). The care checkout had moved its set into `_archive/` on 2026-10-24 (clean status,
   green board). The `tooling _inbox/` line leaves `checks/RECORD-SET`, `_inbox` leaves the export's
   DENY list, and `CLAUDE.md` no longer names it: care work's stay-out list names the top-level
   `_archive/`, where that history lives. The root-anchored `/_inbox/` rule **stays** in
   `.gitignore`, so a leftover folder stays ignored. No care instance had one and nothing tracked
   wrote one. The 2026-09-09 recovery exception for DEV tooling misfiled into CARE's `_inbox/` is
   deleted: it needed a `tooling` path, and that set is now under `_archive/`, a `record` path. The
   per-person intake tray is unchanged.

## Alternatives considered

- **Keep `HANDOVER.md` as a slim live headline** (rejected 2026-07-05): the register, git and the
  ADRs already do its job, and a near-empty "live" file is the drift the three-layer discipline
  fights.
- **Delete `HANDOVER.md` outright** (rejected 2026-07-05): it holds real history (intake lessons,
  the local identifier-redaction narrative of ADR-0029); deletion waits until that value is gone.
- **A new name instead of the operator's `_inbox`/`_archive`** (rejected 2026-07-05): the clash with
  the per-person `_inbox` is namespaced by path and documented, so a fourth name adds vocabulary for
  no safety gain.
- **Make `docs/ROADMAP.md` publishable now** (declined by the operator, 2026-07-05): the publish
  hold stays.
- **For CARE's `_inbox/`: drop every rule, keep the DENY entry too, or keep the old rules**
  (rejected 2026-10-25). The export copies an allow-list, so the DENY entry changed nothing. The
  `tooling` line hid record-shaped paths under `_inbox/` from L20's shape scan, which now reds them.
  Without the ignore rule a stray in DEV (a note, a scan, a transcription) was staged by
  `git add -A` and pushed, and in CARE guard L19 printed its file name, which can carry a
  private-mode identifier.

## Consequences

- The root stays canonical-only, and "is this file still live?" has a structural answer.
- The ignore rules and the export's DENY list must keep `_archive/` out; a new kind inherits that
  from the blanket rule. No new guard was needed: this is classification and hygiene.
- A stray top-level `_inbox/` holding nothing record-shaped is silent in both instances and
  readable by a care session; a forced `git add -f`, or `git mv` into it, commits and pushes in
  DEV, which the old rules refused.
- Left to the operator on 2026-07-05: a fuller de-substrate pass on `CLAUDE.md`'s publishing prose
  and a formal ADR-0024 deprecation, if wanted. ADR-0024 was deprecated on 2026-10-11.
