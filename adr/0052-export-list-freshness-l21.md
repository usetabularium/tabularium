# ADR-0052 — The export file list is checked every session, not at the flip (guard L21)

- **Status:** Accepted 2026-09-08; guard L21 retired 2026-09-27
- **Date:** 2026-09-08
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).
- **Amends:** ADR-0012/0013 (the export firewall) by moving one of its preflight assertions earlier.

## Context

`checks/publish-skeleton.sh`'s `ALLOW` array is the publish contract: the export copies exactly
those paths and nothing else. The script already refuses to build when the contract is incomplete —
a required file that is missing, empty or not a regular file aborts the export.

That refusal only ever fired **at export time**, and the export is run rarely and mostly on the day
of a flip. Nothing else read the array. `check.sh` did not, and the export's own bite-tests
build a *synthetic* repository from a fixture rather than reading the live list — which
is correct for what they test (the firewall's behaviour) and is exactly why they cannot notice this.

The gap became concrete during ADR-0051. Deleting the orientation site removed `site/`,
`tools/site/build_site.py` and `OVERVIEW.md`; for the length of one editing session three `ALLOW`
entries went on naming them. The guard board was green throughout — the site guard L17 merely
LOUD-skipped — and the bite suite stayed at zero failures. The next reader would have been the flip
itself, which is the worst possible moment: a stale contract there means either an aborted export in
the middle of a release, or, if the entry were re-created by something unrelated, shipping a file
nobody decided to ship.

## Decision

1. **Guard L21 runs the same completeness assertion every session** (operator, 2026-09-08: "You can
   build the check."). It parses `ALLOW` and `DENY` out of the export script (parses — never
   sources; sourcing would run the export) and reds when:

   - an `ALLOW` entry names a path that does not exist — the ADR-0051 shape;
   - an entry names an empty file, or a directory holding no non-empty regular file — the same
     standard the export preflight applies, so an empty scaffold cannot satisfy the contract;
   - an entry is a symlink — the export refuses symlinked sources outright, so such a contract could
     never be honoured;
   - a path is on **both** lists — the export copies it and then prunes it, so the contradiction
     resolves silently in favour of `DENY`;
   - either array cannot be parsed, or `ALLOW` parses to zero entries — fail closed, because an
     empty contract cannot describe a shippable skeleton; it can only mean the extraction stopped
     extracting.

   A tree with no export gate (a fixture, a partial checkout) **skips LOUDLY** and does not red.

2. **Retired 2026-09-27; number not reused** (operator-approved guard sweep). While publishing is
   held, a stale list harms nothing: the export's own preflight refuses a missing, empty, symlinked
   or empty-directory entry and aborts on a denied path in the export, at the one moment the list is
   used. Checking it every session cost a board line and a red on every rename for no care benefit.
   The guard's bites go with it; the export firewall's own bites keep the missing, empty and
   denied-path aborts bitten.

## What this deliberately does not do

- **It does not check the `DENY` list against `.gitignore`.** The two are legitimately different:
  `docs` is denied from the export while only `/docs/*` is gitignored, with four files re-included
  by name. A naive mirror assert would red on that every session. The record-set half of that
  mirror is already guarded by L20, and the export keeps its own structural deny belt.
- **It does not check that the list is *right*** — only that it is *satisfiable*. A file that
  should ship and was never added is invisible to this guard, as it is to every other; that
  judgment stays with the dry export and the reader.
- **It does not read the token registry** and needs no secret, so it runs identically on the host,
  in CI and on an exported skeleton.

## Consequences

- The mistake is now caught in the session that makes it, by the board the session already runs.
- Cheap: a parse plus a stat per entry, and one more loud self-skip line in a tree with no export
  gate.
- Since the retirement (point 2), the export's own preflight is the only check of the list.
