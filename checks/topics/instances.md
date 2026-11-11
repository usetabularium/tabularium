# The instance marker and installing an instance

Read when: you install or repair an instance, write a care release pin or a break-glass ticket, or
work out why L19 or L20 is red. The command index and the guards are in
[checks/README.md](../README.md); [contributing/instances.md](../../contributing/instances.md)
explains the two instances.

## The instance marker

Every tree is **DEV** (the product: tooling, templates, guards, ADRs, the eval; never a record) or
**CARE** (a pull-only checkout of DEV at a release tag, plus the record directories, never committed
anywhere).
- `checks/RECORD-SET` is the one tracked list of paths that are not product, and **which of them
  exist on disk decides the mode**. The untracked one-line marker `.tabularium-instance` (`dev` |
  `care`) only asserts it; L20 reds a disagreement. A marker that chose the mode would fail open: a
  DEV tree mis-marked `care` would silence the check that keeps records out.
- A tree with neither marker nor record (the published skeleton, every synthetic fixture) is the one
  shape L20 checks nothing on, and it says so. An unknown marker, an old `migration:` one included,
  is red, and the installer refuses it.
- **A linked worktree has neither input of its own** (both are untracked): the instance belongs to
  the checkout family. L20 reads both from the main checkout and says when a mode was inherited. Do
  not write a marker in a worktree: it can only drift, and L20 reds one that contradicts the family.
  A worktree of a `care` family is refused outright: CARE never edits a tracked file, and such a
  worktree would escape L19.
- In CARE, `checks/CARE-RELEASE` (untracked, one line) names the release tag this instance adopted;
  L19 requires `HEAD` to be exactly that tag. `checks/install-instance.sh care <tag>` writes it. Red:
  missing, multi-line, symlinked, not a release name (`vMAJOR.MINOR.PATCH`, optionally `-slug`, as
  `check.sh --release-name` defines it), naming an absent tag, or naming a tag that is not `HEAD`.
- In CARE, `checks/CARE-EXCEPTION` is the break-glass: `reason:` / `date:` / `expires:` (at most 7
  days, and never more than 7 days from today) turns an L19 red into a loud yellow, so a renderer
  fault mid-encounter-prep cannot leave the board red for days and train blindness. The fix is still
  owed in DEV inside the window. A malformed or expired ticket is red, and a valid one is always
  announced (`L19 EXCEPTION OPEN (LOUD)`), so a ticket left behind stays visible.

## Install an instance

`checks/install-instance.sh dev | care [<release-tag>]`, once per instance. It is idempotent: each
action prints one line (`written`, `unchanged` or `warn: …`), so a diff of two runs is the change
set. Its header lists every action per mode; what to know before running it:
- It asks `check.sh --instance-mode` which instance it is in, and refuses when that answer is
  unavailable or the requested mode is unknown.
- `dev` installs the four commit-path hooks; `care` installs only `pre-push`, as a belt.
- `care <release-tag>` checks, before writing anything, that the tag is a release name that resolves
  here and is checked out at `HEAD`, and writes `checks/CARE-RELEASE` last, only when every other
  action succeeded. Plain `care` warns when no pin exists. A release tag with any other mode is
  refused.
- `care` removes, printing each, tooling of the installer's own that care must not run; an edited
  copy is kept with a warning, and the operator's own skills, hooks and settings are never touched.
- It advises on `.venv-render/` but never creates it, reports private mode's local tools in one
  line, and verifies the private-mode identifier split content-blind (`split verified` or why not;
  see [relay-and-export.md](relay-and-export.md)).
- It merges, never replaces, the read-guard hook and its deny rules into
  `.claude/settings.local.json`, refuses a settings file that is not valid JSON, and never prints the
  registry's path.
- An export gate it cannot read is reported as "cannot tell — inspect by hand", never as clean.

**In a linked worktree** it installs only per-tree tooling (the read-guard settings and the skills)
and says so for the two it skips: the marker is the family's, and one hooks directory serves every
worktree, so a hook install from there would overwrite every sibling's hooks with that worktree's
branch of `checks/git-hooks/*`. Run it in the **main checkout** for those two. A requested mode that
disagrees with the family is refused, as is a contradicting leftover local marker. A family that
asserts nothing, or cannot be read, is a warning with no marker written: asserting an unverified
instance is the operator's act, not the installer's. The install-instance cases in `selftest.sh`
bite all of this.
