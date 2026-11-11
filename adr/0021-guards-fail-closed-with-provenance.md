# ADR-0021 — Guards fail closed and carry provenance

- **Status:** Accepted 2026-06-13
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The real danger in the 2026-06-13 incident (ADR-0020) was not the red exit but a guard that could
pass having checked zero patients, and "green in the sandbox" read as "green everywhere".

## Decision

What holds now: `checks/README.md` (its opening rule, *Host portability*, *Writing a guard or a
bite*), `contributing/gates.md` and the L0, coverage and green-line code in `checks/check.sh`.

1. **A guard never reports green having examined nothing.** An L0 precondition refuses to run
   outside the repository root (`CLAUDE.md` or `checks/` absent), and coverage asserts fail a guard
   that found nothing to check, such as patient folders with no canonical docs: a silent false
   green becomes a loud stop.
2. **A green carries provenance:** the green line names the platform (`uname`, bash version), so it
   says where it holds.
3. **Pre-commit enforcement waited for trusted guards** (`cc-prompts/006`, held until this fix was
   verified on the host): enforcing untrusted guards would cement false confidence. It landed as
   ADR-0022.
4. **A grep error is never a clean scan** (2026-07-04). An adversarially verified gap review closed
   two fail-open paths and two latent false reds, with bites: L4 mangled candidate ids, letting an
   unvetted citation pass (one canonical extractor now serves both sides); L5 read grep's exit code
   2, from a handle with a regex metacharacter, as "no hits" (handles are validated, and 2 or more
   reds); L6's filename glob and L7's id extraction were too loose.
