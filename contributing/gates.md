# Gates, hooks and merging

Read when: you add, change or retire a control — a guard, a hook, CI, a notice; a gate refuses; or you
merge a queue of pull requests or a stacked one.

## Safeguards — the machinery around the board

`CLAUDE.md` → *Safeguards* carries the care-edit workflow, including its pre-edit snapshot. Build edits follow
`CONTRIBUTING.md` → *Opening a build session*: git is their recovery floor; no care snapshot. After editing guard
code, `tools/` verifier code, or `_templates/`, run `checks/selftest.sh` (bite-tests). This section owns
the build gates and hooks; `checks/README.md` → *Commit gate* has the mechanics.

- **Guards fail closed** — never green having examined nothing (a precondition + coverage asserts
  catch the wrong-directory / empty-tree false green). They must run on **both** substrates (Linux CI *and*
  the macOS host); `selftest.sh` lints every guard script for host-portability, and `check.sh` stamps
  its green line with the platform, so a green is attributable (ADR-0020/0021).
- **L19/L20 hold the two-instance shape** (ADR-0050): the mode is derived from the records, the marker
  only asserts it, and a CARE tree with a changed tracked file is red. `checks/install-instance.sh`
  installs the hooks and the session read-guard per instance.
- **Commits are gated structurally** (ADR-0022): `pre-commit` runs `check.sh` and **blocks a red
  working tree** — about a second, every commit, no exceptions. Auto-committed merges go through the paired
  `pre-merge-commit` (same gate); `cherry-pick` has no such hook and stays ungated — run
  `check.sh` after it. **Merges only** (operator, 2026-10-28): never rebase or force-push a DEV branch; bring
  it up to date by merging `main` into it.
- **The bite suite runs before a pull request is opened, not in a hook** (ADR-0022 point 6): run
  it on the clean, committed tree, then `gh pr create`; CI repeats it for every PR. The
  [push hook](../checks/git-hooks/pre-push) lets only a record-free DEV family push, and refuses a
  pushed ref whose own tree tracks a record path.
  Installed hooks are copies that drift from `checks/git-hooks/` until reinstalled.
- **No hook judges what `CLAUDE.md` says**; the development tree's context-health hook only counts the
  lines of the docs that enter a session's context (`tools/claude-hooks/README.md`). A behavioural run
  after a load-bearing change to `CLAUDE.md` is **strongly recommended, not required**: read the cost with `run_eval --estimate`; the core run is the default
  and the one that counts, the full suite runs on request (ADR-0049).
- **The sanctioned bypass** is `TABULARIUM_SKIP_GUARD=1`, which the paired `commit-msg` hook forces you
  to **name in the commit message**, so it is always recorded. `git commit --no-verify` (and `-n`) skips
  the commit-path hooks — `pre-commit` gate and `commit-msg` audit alike — and `git merge --no-verify` /
  `git push --no-verify` do the same for `pre-merge-commit` and `pre-push`; none leaves a mark — never
  use it, never advise it. Client-side hooks are a discipline aid, not an enforcement boundary.
- Hooks live in `checks/git-hooks/`; install all four like `pre-push` (see `checks/README.md`).

**A notice that repeats without a decision path trains dismissal.** The scrutiny here is deliberate —
the LOUD lines and the holds make a one-collaborator project auditable, and are not to be
trimmed for feeling heavy. The failure mode is *repetition*: an operator who meets the same warning
every run learns to skip the class, and the one that mattered goes with it. So a notice must either name
a decision the operator can take **once** and have recorded — an ACCEPTED RISK row with a revisit
trigger — or fire once and go quiet. **A
notice with no way to answer it is a defect in the notice**: give it an answerable form, never lower
the bar it guards (operator, 2026-09-09).

## Quality controls

Judge a control's cost against the top-level `README.md` → *Purpose* and prefer the smallest control
that preserves the needed protection. Admission: the `guard-admission` skill
(`CONTRIBUTING.md` → *Operating stance when building*).

An agent that works around an access denial — in a red-team round or any other — is no longer
trusted: discard its output, whatever it found (operator, 2026-10-11; incident in ADR-0037).

## Merging a queue of pull requests

Simulate every *ordered pair* onto `origin/main` (`git merge-tree --write-tree`) rather than trusting
each PR's own report; expect two sessions to have claimed the same next ADR number; pin every merge to
the full head SHA (`gh pr merge N --merge --match-head-commit <40-hex>`); retarget a stacked PR to
`main` once its parent lands, or it merges into a dead branch.
