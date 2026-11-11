# ADR-0038 — selftest fixtures are synthetic, not whole-tree copies

- **Status:** Accepted 2026-07-11; superseded in part by ADR-0050 (2026-09-06)
- **Date:** 2026-07-11
- **Deciders:** not named in the source; Tier S (`checks/**`), red-teamed independently before
  commit (ADR-0031 point 1)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

`checks/selftest.sh` bite-tests every guard by building a fixture tree, injecting one defect and
asserting that the matching guard fires (and that a clean tree passes). Since ADR-0022 the
pre-commit hook ran the full suite whenever guard machinery was staged, so every guard-touching
commit paid its wall time, which had grown to about 25 minutes on the macOS host.

The cause, measured: the `mk()` fixture helper copied the entire working tree into a temp
directory once per case, about 55 times. The tree was several GB, dominated by `outputs/` backup
tarballs and the scans under `patients/`, while everything the guards test is a few MB of Markdown;
the copy, not the check, was the cost. The fixtures also put real patient health data (profiles and
scans) into temp directories: local and deleted, but avoidable.

## Decision

What holds now: the header and `mk()` of `checks/selftest.sh` and `checks/README.md` (*Writing a
guard or a bite*: fixtures are deliberately minimal).

1. **`mk()` builds a minimal synthetic tree from scratch** (2026-07-11): only what the L0
   precondition needs to run, an empty `CLAUDE.md` and a `checks/` directory. Every case builds its
   own synthetic `patients/`.
2. **`mk()` copies no firewall artifact** (2026-09-06; ADR-0050 Part B and WP8 supersede the
   decision's second bullet of 2026-07-11). At first `mk()` also copied the export script and the
   registry checkpoint, the two files guards L9 and L12 had to read to run rather than self-skip.
   Both readers retired with the session firewall and the checkpoint was deleted, so a `check.sh`
   fixture carries neither. The export gate's own fixtures use the token-free script and write a
   synthetic registry of their own (with `BRAND_ADJ_PAIRS` since WP8); the real registry is never
   read, copied or pointed at.
3. **Two cases that need the real tree read it in place** (2026-07-11). The live-tree case runs
   `check.sh` on the repository directly, with no copy and never a delete: stronger than checking a
   copy, at no copy cost. The template-scaffold case copies the shipped templates from the
   repository, since `mk()` no longer carries `_templates/`.

## Alternatives considered

- **An APFS clone (`cp -c`)** (rejected 2026-07-11): nearly free on Darwin, but it keeps real PII
  in fixtures, does not help Linux CI and still clones gigabytes of irrelevant `outputs/`. Synthetic
  is faster and also solves privacy.
- **Pruning the copy set** (rejected 2026-07-11): smaller, but still a per-case copy that couples
  fixtures to the real tree's shape. Built from scratch is simpler and cannot drift.
- **Parallelism** (rejected 2026-07-11): unnecessary once the copies are gone, and a risk of
  nondeterministic pass/fail output.

## Consequences

- The full suite went from about 25 minutes to about 17 seconds on the macOS host with the same
  results; every case was kept, and a guard neutered in a scratch `check.sh` still reds the suite
  on that guard. No guard logic changed; the skeleton and the live tree stayed green.
- Guard edits were bite-tested in seconds, removing the incentive to reach for
  `TABULARIUM_SKIP_GUARD`. The suite later left the commit hook for the push boundary (2026-09-08),
  and since 2026-09-27 no hook runs it: it runs before a pull request and in CI (ADR-0022;
  `checks/README.md` → *Commit gate*).
- **Privacy:** fixtures hold no patient records. Until 2026-09-06 the copied export script still
  carried real identifying tokens in its registry lines, so exposure was strictly less, not zero;
  the independent red-team flagged the first wording as overclaiming, and it was corrected. Since
  2026-09-06 a fixture carries no real patient data and no real token.
