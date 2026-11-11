# ADR-0017 — Go local-only

- **Status:** Accepted by 2026-06-09; superseded in part by ADR-0050 2026-09-06 and by ADR-0066
  (point 2) 2026-11-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The GitHub repository was contaminated and the local `.git` wedged. A documentary rule against
early publishing must be remembered; a structural one need not be.

## Decision

What holds now: `checks/README.md` → *Version control & backups*, `checks/git-hooks/pre-push`,
`checks/PUBLISH-HOLD`, `.gitignore` and `checks/topics/relay-and-export.md`.

1. **Local-only.** The contaminated remote repository is deleted, and the wedged `.git` is replaced
   by a fresh repository with no remote and a `pre-push` hook that blocks every push
   (`cc-prompts/002`). No remote and no repository make early publishing structurally impossible.
2. **Publishing is a deliberate later step, the fresh-export model:** `publish-skeleton.sh`
   builds a fresh, history-free export; each push replaces the display copy rather than
   publishing development history. Its `--push` aborts while `checks/PUBLISH-HOLD` exists. A
   removable hold file turns "an explicit operator request" into an enforceable act.
   `cc-prompts/001` stayed held.
3. **Reversed for the development tree** (ADR-0050, 2026-09-06), which has a remote: it is the
   private skeleton repository. The no-remote rule survives where it mattered, for the records,
   which are never committed anywhere; `pre-push` allows a push only from a record-free `dev`
   instance.
