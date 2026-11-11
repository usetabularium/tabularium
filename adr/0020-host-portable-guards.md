# ADR-0020 — Host-portable guard scripts

- **Status:** Accepted 2026-06-13
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

A pristine checkout ran red on the operator's macOS host: L5's patient discovery used a bash-4
builtin and a GNU-only `find` flag, and a naive half-fix would have left L5, the highest-severity
guard, silently checking zero patients. Guards that run only on Linux leave the host without an
executable net, and a Linux-only selftest cannot show it.

## Decision

What holds now: `checks/README.md` → *Host portability*, `contributing/gates.md` and the
`HOST-PORTABILITY` comments in `checks/check.sh`.

1. **Guard scripts run on macOS `bash 3.2` and BSD userland, not only on Linux,** enforced by a
   portability lint in `selftest.sh`. The lint runs on Linux, where the bites would never show a
   host-only regression.
2. **All shared executable code** (2026-06-13) is bash-3.2/BSD-portable and verified on both Linux
   and macOS. Each green names its platform (ADR-0021); both runs supply the two-substrate
   attestation. The lint auto-discovers every `checks/*.sh` and `checks/git-hooks/*`.
3. **Empty arrays** (2026-06-24). Under `set -u`, bash 3.2 treats an empty `"${arr[@]}"` as unbound,
   and `check.sh` crashed on a patient-free tree, unseen where real patients filled the array. A new
   guard expands an array that can be empty as `${arr[@]+"${arr[@]}"}`, and one meant to pass on the
   skeleton is bite-tested on a patient-free tree.
