# Cutting a release (ADR-0054)

Read when: you cut a release, decide which version number a change will need, or create, move or
delete a tag.

A release is an **annotated tag named exactly `vMAJOR.MINOR.PATCH`** on a `main` commit whose CI run
is green; its message is the release note. A pushed tag never moves and is never deleted — the care
instance pins releases by name — and a tag that is not a release never begins with `v`. No GitHub
Releases in this repository.

**When.** When the care instance should adopt something, or a maintenance campaign closes — never per
pull request. A change that runs only here (commit-path hooks, bite suite, CI) rides the next release.

**Which number.** Read the diff since the previous release, not the commit prefixes; the highest class
present wins. *Routine adoption* is the care instance's release-acceptance session (ADR-0050).
- **MAJOR** — routine adoption would leave an instance broken or less protected: a record format or
  path changes, adoption needs a step the routine does not take, or a protection is withdrawn (a care
  rule removed or reversed, a guard retired while what it protected remains). **Before 1.0.0 this is a
  MINOR whose note leads with it.** 1.0.0 is the first release at which all three hold: the record
  layout and the care contract have been steady for a while; two releases in a row withdraw no
  protection; someone other than the operator has run it (ADR-0065).
- **MINOR** — something an instance runs changes what it does or checks: the board, a guard, the
  installer, a tool, a template, an eval case, a care rule (a change to what `CLAUDE.md` asks of
  a care session).
- **PATCH** — nothing an instance runs changes: documentation, a wording-only `CLAUDE.md` change,
  development-only machinery. `pre-push` is also the care instance's push block, so a change to it is
  classed by what it does there.

**The note**, written once, in this shape:

```
vX.Y.Z — <name>

Bump: <MAJOR | MINOR | PATCH> — <the rule that decided it>
Adoption: routine | routine, then: <each extra step, in order>
Withdrawn protections: none | <one line each>
Guards changed: none | <guard by plain name — added | changed | retired, one line each>
Rollback: <previous release tag>[, then by hand: <each skill, git hook or settings hook this release adds>]

<what changed, in prose, for the person adopting it>
```

The note is read by the person adopting the release, so it follows the build register's plain-name
rule (`CONTRIBUTING.md` → *Its register*): no bare guard number, issue, decision or handover id.
Point guard readers to `checks/README.md` → *Guards*, and spell out any extra adoption step.

Write the note to a file outside the tree and relay-scan it — a
tag message is not a tracked file, so no other sweep sees it. **A release that is exported takes its note
to the public copy word for word**, so a public adopter reads it too.

Which release goes public, and when, is the operator's call, and a release is exported only after it is cut:
`checks/topics/relay-and-export.md` → *The flip-time export* (ADR-0066). The release in use by care is
unaffected either way.

**Cutting it — in the main checkout**, which has the render environment. No hook tests what a tag
names, so run the bite suite on exactly the release commit, on a clean tree, before tagging it. Land
any eval rows gathered since the last change that recorded a run first: `git status --short
evals/results` shows none, and `python3 -m evals.harness.scores --check` passes
(`evals/README.md` → *Ledger*). Run private mode's real-tools check on the same commit, on the Mac with
poppler, tesseract and ImageMagick installed: the bite suite and CI fake all three, so only this run sees
a change in how they behave, a Homebrew upgrade included (run it after one too). It must end
`REAL_TOOLS_OK`; any other word (`CHECK_FAILED`, `CONTROL_NOT_CAUGHT`, `TOOLS_ABSENT`,
`TOOLS_WRONG_VERSION`, `SETUP_ERROR`) holds the tag. It prints tokens and counts only, so its output
may be pasted anywhere.

```bash
git fetch origin
git switch --detach origin/main
bash checks/selftest.sh
python3 tools/private-mode/real_tools_check.py
bash checks/relay-scan.sh <note file outside the tree>
git tag -a vX.Y.Z -F <note file outside the tree>
git push origin vX.Y.Z
git switch -
```

**Adopting it — in the care checkout.** One command, from the care checkout's top folder:

```bash
bash checks/adopt-release.sh          # the newest vX.Y.Z; to name one: bash checks/adopt-release.sh vX.Y.Z
```

It fetches the tags, checks the release out, runs `checks/install-instance.sh care <tag>` and then the
board, stopping at the first failure. A care session's first start of the day says in one line when a
newer MINOR or MAJOR release is out (`checks/release-notice.sh`); `/update` runs this command. It refuses in development and over any tracked-file change, and
prints no remote address. The checkout never replaces or deletes an ignored file — every record is one —
so a release that would is refused with nothing changed. **An interrupted adoption is finished by
running the same command with the same tag again**; if the checkout itself stopped partway, that run
removes only the untracked files that are the release's own, whole or partly written (never a
`checks/RECORD-SET` path), and prints the line that finishes it. Every recovery it prints is one line chained with `&&` —
clear the shell's git variables, the checkout, the release's own installer and board, commands every
release has — so a checkout that fails stops the line before the installer re-pins; when a killed git
left its index lock and no git is running in the checkout, the line starts by removing it, said why,
and the script never removes it itself. On a red installer or board it rolls nothing back, by decision
(ADR-0055), and prints the line back to the previous pin; when the pin already names the release, as
after a repeated run, it reads the previous release from git's record of where HEAD has been (the
reflog), or says plainly it has none. The installer refuses a tag that is not checked out, writes the
pin only once every other step succeeded, and in care removes the skills, git hooks and settings hooks
of its own that care must not run — a skill or git hook only when its bytes are a release tag's own,
never by name lists, and never the operator's (an edited copy is kept with a warning). These clean-ups run in the installer of the release
being installed, so a rollback to a release older than this one still leaves a newer release's
additions to remove by hand (its release note's `Rollback:` line names them). The note's `Adoption:`
extra steps stay by hand.

**A release that changes the record format** ships a one-time migration tool and lists its commands
under `Adoption:` in the note; the tool is deleted once the care instance has migrated, so a care
instance that has not yet migrated runs it from the release that carried it.
