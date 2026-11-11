# ADR-0016 — Top-level README, `docs/` unpublished, public flip held

- **Status:** Accepted by 2026-06-09; point 3 deprecated 2026-11-08
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

GitHub showed the retired-exploration archive note as the front page: meaningless for a skeleton,
and it leaked origin detail. "Private until an explicit request" was only remembered.

## Decision

What holds now: the top-level `README.md`, `DENY` in `checks/publish-skeleton.sh`, `.gitignore`,
`CLAUDE.md` → *Safeguards*, `checks/PUBLISH-HOLD` and `contributing/instances.md` →
*Publishing*.

1. **A real top-level `README.md`:** a reusable skeleton needs a front page that explains it.
2. **`docs/` leaves the publishable set** (deny-listed); the firewall gains brand and origin tokens,
   and the skeleton's remaining wording about its domain of origin was made generic.
3. **The public flip is held, by a hard hold in `CLAUDE.md`:** the rule is enforced in the
   always-read contract, not remembered.
