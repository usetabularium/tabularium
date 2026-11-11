# ADR-0054 — Versioning and releases: the number measures what adopting costs, the tag is the release

- **Status:** Accepted 2026-09-13; point 7 superseded by ADR-0022 2026-09-27; point 6 superseded in part
  by ADR-0066 2026-11-07; point 5 superseded in part by
  ADR-0065 2026-11-08
- **Date:** 2026-09-13
- **Deciders:** operator (+ assistant); the pull request that landed this file was the review
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The operator asked on 2026-09-13: "start versioning tabularium … come up with an appropriate
methodology … and derive the current version". Releases had existed since the two-instance split
(ADR-0050): the care instance pins a release tag by name, and CI runs on every `v*` tag. Three
annotated release tags existed (`v0.50.0-migration-ready`, `v0.51.0-firewall-retired`,
`v0.52.0-evals-ship-lean-route`). Five things were missing or wrong:

1. **The number meant nothing stated:** not why the series began at 0.50, what bumps which
   component, or when 1.0 comes.
2. **The name shape was a SemVer pre-release.** `0.52.0-evals-ship-lean-route` ranks below `0.52.0`,
   so a SemVer-aware consumer (a marketplace update check, a "latest stable" filter) read every
   release as a pre-release.
3. **Release notes had no home**, though ADR-0050 required them to list changed template blocks.
4. **A release tag could not be pushed.** Since 2026-09-08 `pre-push` refused a ref whose object id
   was not HEAD's commit id, and git hands the hook an annotated tag's own object id, so only the
   forbidden `--no-verify` could get one past it. No release had been pushed since the gate landed;
   the failure was reproduced in a scratch repository on 2026-09-13.
5. **The public copy would carry no version:** the flip-time export is fresh and history-free
   (ADR-0012/0017/0050), so tags do not travel with it.

## Decision

What holds now: `contributing/releases.md` (when, which number, the note template, cutting and
adopting), the release-notes row of `contributing/documentation.md`, and the release-name shape
defined once in `checks/check.sh` (`--release-name`), applied by L19 and the installer.

1. **A release is an annotated tag named exactly `vMAJOR.MINOR.PATCH`** (2026-09-13), on a `main`
   commit whose CI run is green, pushed so CI attests the tag itself. The human-readable name goes
   in the tag's subject line; a tag that is not a release never begins with `v`. **A pushed tag
   never moves and is never deleted:** the care instance pins releases by name. Since 2026-09-29
   L19 reds, and the installer refuses, a care pin that is not a release name (the legacy `-slug`
   form allowed): resolving `refs/tags/<pin>^{}` had also accepted `<tag>~1`, an untagged commit.

2. **The bump measures what it costs an instance to adopt the release** (2026-09-13), routine
   adoption being ADR-0050's release-acceptance session. The class is read from the diff since the
   previous release, not from commit-type prefixes, and the highest class present wins.
   - **MAJOR:** routine adoption would leave an instance broken or less protected (a record format
     or path changes, adoption needs an extra step, or a protection is withdrawn).
   - **MINOR:** something an instance runs changes what it does or checks; routine adoption
     suffices.
   - **PATCH:** nothing an instance runs changes behaviour.
   - **Before 1.0.0 there is no MAJOR:** what would be one is a MINOR whose note leads with the
     extra steps and withdrawn protections, which the number cannot show.

   On 2026-10-04 routine adoption stopped re-syncing template blocks, because the patient copies
   were removed (ADR-0044), so a template counts as MINOR like a tool; and the keystone change
   classes went with the instruction-change ceremony: a change to what `CLAUDE.md` asks of a care
   session is MINOR, a wording-only change PATCH.

3. **The annotated tag's message is the release note** (2026-09-13), written once in one template
   and relay-scanned first: a tag message is not a tracked file, and a release note is where guard
   noise seen in care gets described. **No GitHub Releases** in the development repository: a
   surface outside the object graph that the flip's content sweep would otherwise have to cover. The
   note first left out the behavioural-eval state, because adoption and L19 read the tag's keystone
   lineage aloud. That file went on 2026-10-04, and the rule was dropped (operator, 2026-10-11,
   after a break test: "nothing reads release notes or tag messages").

4. **Cadence** (2026-09-13). A release is cut when the care instance should adopt something or a
   maintenance campaign closes, never per pull request; a development-only change rides the next
   one. No release branches.

5. **Numbering continues from 0.52.0, and 1.0.0 is the first public release** (2026-09-13), the
   commit the flip-time export is taken from. 1.0.0 promises a stable public contract, and before
   the flip there is none: the licence is unattached and `NOTICE.md` carries preview terms
   (ADR-0035). The existing tags keep their names: the care pin, ADR-0050 and the remote name them.

6. **The tag is the number's only home in this repository** (2026-09-13): no tracked `VERSION` file,
   no version string in any document. Whatever must carry the number later (the public export, a
   plugin manifest) is stamped from the tag when the release is cut, never by hand. The export's
   stamp is a flip-time item; how later public releases reach the public repository is not settled.

7. **The push gate compared the commit a ref resolves to** (2026-09-13; superseded by ADR-0022,
   2026-09-27). `pre-push` compared each pushed ref's peeled commit with HEAD: an annotated tag on
   HEAD passed; a ref resolving elsewhere or to no commit was refused. Since the installed copy is
   what runs, a release was cut only after reinstalling the hooks from the release commit.
   On 2026-09-27 `pre-push` stopped comparing pushed refs with HEAD (ADR-0022): a tag pushes like
   any ref, and the bite suite runs on the release commit before it is tagged.

## Alternatives considered

- **Calendar versions (`2026.09.1`).** A date says when, not what adopting costs, the one thing an
  adopter needs from the number; the tag object already holds the date.
- **Keep the slugged names.** They rank as pre-releases (Context 2).
- **Renumber from 0.1.0, or jump to 0.9.0.** A lower number breaks ordering against the existing
  tags, one of them the care pin; order is the sequence's only job.
- **1.0.0 now.** No stable public contract exists before the flip.
- **Size the bump by commit-type prefix.** The prefixes are unenforced, and several `fix` commits
  since 0.52.0 changed what a guard or the installer does: a prefix records intent, not cost.
- **A tracked `VERSION` file.** A second home for a fact the tag holds.
- **Exempt tags from the push gate.** Only the checked-out commit is vouched for; an exempt tag
  could name an untested one.
- **A release script that assembles the note.** Deferred: one releaser, a short template.

## Consequences

- The care instance knows what adopting costs before it pulls; SemVer-aware consumers read releases
  as releases; release notes have one home and one shape.
- Every release owes a note, and the releaser classifies the diff by hand. Until 1.0.0 a MINOR may
  carry a withdrawn protection, so the adopter reads the note, not just the number.
- Nothing mechanical checks the note's shape or that a pushed tag never moves; that rests on the one
  releaser.
- **Applied, 2026-09-13.** The version in use was 0.52.0, the care instance's adopted release. The
  delta since was MINOR (guard L21 added, L20 changed, two `load-bearing` keystone changes, and L17
  retired with the site it checked, so no protection withdrawn): the next release was v0.53.0.
