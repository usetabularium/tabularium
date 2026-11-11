# ADR-0046 — Publish-firewall token classes guarded at session/commit time (guard L18)

- **Status:** Accepted 2026-08-09; superseded by ADR-0050 2026-09-06
- **Date:** 2026-08-09
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The publish firewall (`checks/publish-skeleton.sh`, which then held the token classes) ran only at
export time, so a PII token put back onto an ALLOW-listed file sat undetected until the next dry
build. Three leak classes were caught only that way: two on 2026-07-04/05, two more while
landing private-ring push #4, and a care-setting fingerprint. A commit-time scan had waited for an
operator decision since 2026-07-05.

## Decision

What holds now: L18 is retired (the retired-numbers line of `checks/check.sh`, the *Retired* line
of `checks/README.md`, ADR-0050 Part B, point 10). The token classes are scanned at the flip by
`checks/publish-skeleton.sh` and over CARE→DEV relay prose by `checks/relay-scan.sh`
(`checks/topics/relay-and-export.md`).

1. **Mechanism over one attribute class** (operator, 2026-08-09). The operator took L18 in the
   decision that left per-form consent morphology unbuilt as an accepted gap:
   mechanism-level coverage beats sharpening one attribute class.

2. **A guard in `checks/check.sh`, not a hook step** (2026-08-09). The ADR-0022 pre-commit hook
   already runs `check.sh`, so L18 fired at every commit, as asked, and at every session,
   with no new wiring and the guard discipline: fail closed, loud self-skip, bite-tested.

3. **What it scanned** (2026-08-09). L18 read the ALLOW list and class lines live from the firewall
   script (the L9 pattern: shipped `check.sh` holds no token) and ran the export scan's lanes over
   the ALLOW surface, content and names, with its three identity exemptions replicated.
   Consent-class content stayed L9's; the export scan stayed the deep gate. Content hits printed
   locators only (the L10 lesson).

4. **Accepted deltas from the export scan** (2026-08-09): working-tree bytes, not staged;
   coarser, whole-line carve-outs; and no wrapped-brand, binary, deny-list, commit-parity,
   render-volume or per-entry ALLOW checks, which stayed with the export.

5. **Same-day adversarial fixes** (2026-08-09). Missing scan sources failed closed; identity
   exemptions required an anchored path and a pure line number; symlinked ALLOW paths were refused;
   and scans required a probed UTF-8 locale. Current boundary scans: `checks/publish-skeleton.sh`
   and `checks/topics/relay-and-export.md`.

6. **Retired 2026-09-06 with ADR-0050 Part B, after the records moved and not before.** L18 caught
   the one failure a shared tree allows, a live specific copied from the care surface onto a shipped
   one (on 2026-08-16 and on the citation-membership lane's first merge attempt). A record-free development
   instance has no such path and no registry to read. L18 retired with L9, L12 and the FIRE bites;
   its number is not reused. A token reaching a shipped file another way is now caught at the flip,
   not at the commit: a gap reopened on purpose.

## Alternatives considered

- **A pre-commit step over staged blobs** (rejected 2026-08-09). Closer to the ask and free of
  the partial-staging delta, but it duplicates scan logic outside the guard discipline, runs only at
  commit, and leaves the working-tree gap open, since other tests read the working tree. One mechanism beats two
  half-gates.
- **A `--scan-tree` mode in `publish-skeleton.sh`** (rejected 2026-08-09). The script was linear,
  hash-checkpointed (L12) and deliberately boring; a second entry point was more risk than
  replicating three small, bite-tested exemptions.

## Consequences

- While L18 ran, a reintroduced token turned the board red that session and blocked its commit;
  the dry build stopped being the first detector.
- Costs: one grep pass over the ALLOW surface per run, and a sync duty: an exemption changed in the
  export scan had to be mirrored in L18. Both ended with the retirement (point 6).
