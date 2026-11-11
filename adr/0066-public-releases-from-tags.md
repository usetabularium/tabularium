# ADR-0066 — A public release is built from its tag and appended to the public copy

- **Status:** Accepted 2026-11-07 (operator); supersedes in part ADR-0012 point 1 and ADR-0050 point 4
  (one fresh copy per export), ADR-0017 point 2 (each push replaces the display copy) and ADR-0054 point 6
  (how later public releases arrive, not settled) 2026-11-07
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

A care instance pins the release it adopted, and the board's release check wants that pin to name a
tag at HEAD, reachable from `origin` (ADR-0050, ADR-0054). The export built one commit with no tag from
the working tree. A walk of a mock export on 2026-11-01 (desktop app, non-technical caregiver, macOS)
showed the result: after the care declaration the release check stays red on such a clone, so a
stranger's first care session breaks the contract's rule never to end a session red, and the release
notice has no tags to compare with. Force-replacing the copy at each release would also leave every
earlier adopter's commit outside `origin`, which reds the same check.

## Decision

1. **A public release is a release tag, exported from its committed tree** (operator, 2026-10-31).
   `checks/publish-skeleton.sh vX.Y.Z` reads the tag's tree, never the working tree, and the running
   script must be the tag's own, because its allow-list decides what ships. The tag stays the number's
   only home, so there is no `VERSION` file (ADR-0054 point 6).
2. **Each release appends one commit to the public `main`, and nothing is force-pushed** (operator,
   2026-10-31). The first is a root commit into an empty repository, and a public `main` that is not
   the newest public release is refused, so no other commit becomes public history under a release. A
   push sends both refs or neither and is rejected if the public `main` moved. A tag already there, one
   older than the newest, a name with a leading zero or a release that changes no exported file is
   refused. No DEV history enters. Every public commit is a release, so a plain clone stands at the
   newest tag.
3. **The tag travels with its note, under the fixed export identity** (operator, 2026-11-07). The shipped `/update` skill reads
   the note's `Adoption:` and `Rollback:` lines. A source tag's signature is not carried: it holds the
   signer's key, which leads back to its owner. A note is not in the tree, so the export scans it with
   every class and no carve-out, printing no content on a hit. A tag never moves, so a hit means a new
   release.
4. **An untagged source makes no export** (operator, 2026-11-01: no interim untagged mode). `--push`
   without a tag is refused before any git call. A run naming no tag scans the working tree and makes
   no commit and no tag, so nothing it leaves can be published. The scan stays (operator, 2026-11-07)
   because a tag never moves and must not be cut to find out whether a scan passes.
5. **A stranger installs by Claude cloning the public repository at the newest tag** (operator,
   2026-10-31): full clone, worktree option off, no zip. There are no GitHub Release pages (operator,
   2026-10-31, again 2026-11-06).
6. **This record sets no number.** The export takes any name of the release shape; which number the first
   public release carries is ADR-0054's subject and its successors'.

## Alternatives considered

- **Force-replace a one-commit display copy** (the rule from 2026-07-04; reversed by the operator,
  2026-10-31): moves history under anyone who pinned a release, and the release check reds.
- **Stamp a `VERSION` file at export** (ADR-0054 point 6's first plan; reversed by the operator,
  2026-10-31): a second home for what the tag holds, and the check reads tags, not files.
- **An interim untagged mode on the board** (declined by the operator, 2026-11-01): the red would have
  stood for a real absence, and the tag fixes it.
- **Refuse every untagged run, the scan included:** the only firewall scan would need a tag first, and
  each hit would burn a release number.
- **A fixed message on the public tag:** nothing to scan, but `/update` would read no extra steps from it.
- **Require a clean tree or HEAD at the tag:** lifting the hold dirties the tree, and only the script's own
  bytes bear on what ships.

## Consequences

- A clone of the public copy at its tag, a first person from the intake procedure and the care installer
  give a green board, and an appended release reaches the notice and adopts green. `selftest.sh --export`
  walks that route on the tree's tracked files, the one fixture that copies them (ADR-0038's objection was
  records and gigabytes per case), with bites for each refusal and a no-force race.
- **What reached a public release stays in the public history.** The fix is a new release; taking it out
  means replacing the repository, which is the operator's decision and breaks every adopter's pin.
- The first public release must be a tag cut after this lands, since the running script must be the tag's own.
- A note now has two readers. Its `Rollback:` line may name a release the public copy never carried;
  adoption reads the pin, not the note, so the printed way back still works.
- A clone of the public copy has a remote whose every commit is a release, so the release notice and
  adoption need no change of their own.
