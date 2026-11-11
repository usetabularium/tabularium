# checks/ — the executable guards

Prose rules don't execute; these do. Each guard has a **bite-test** proving it catches the failure
it exists for. **Guards fail closed** — none reports green having examined nothing (ADR-0021).

## Routine (run it every canonical-edit session)

The required sequence lives in [the care contract](../CLAUDE.md#safeguards).
For tool changes, use [the build workflow](../CONTRIBUTING.md#opening-a-build-session-adr-0053).
This is a command index; what each backup holds and how to restore are under
[Version control & backups](#version-control--backups) and [Recovery](#recovery).

```
checks/check.sh         # the session board; green where the care and build contracts require
checks/snapshot.sh      # care pre-edit recovery point; DEV refuses
checks/selftest.sh      # after changing checks/, tools/ verifier code or _templates/: guard, queue, hook and render bites, host-portability lint, every tools/*/ and evals/*/ test_*.py; red if a listed suite is missing or a suite is in neither checks/PYTHON-SUITES (shipped) nor checks/PYTHON-SUITES-DEV — list a new suite in the same change
checks/selftest.sh --export   # before any export and after changing publish-skeleton.sh (CI runs this form): the same plus the export gate's full matrix
checks/confirms.sh      # queue monitor, any time: ⟨confirm by YYYY-MM⟩ tags and dated open items; 1 = overdue or malformed, 2 = incomplete scan
checks/backup-tree.sh   # periodic: whole-tree recovery tarball (backup layer 2)
checks/backup-offsite.sh [--verify-only]   # periodic, or by the snapshot when due: append-only mirror of patients/ + _shared/ into the configured folder, the only off-machine copy (layer 3)
checks/retire-worktree.sh <name> [--bank]  # the one sanctioned way to retire a worktree: lock, merged/clean gates, locked quarantine or bank-and-stop; nothing deletes a live worktree recursively
python3 tools/private-mode/real_tools_check.py   # DEV, by hand, before a release and after a Homebrew upgrade of poppler, tesseract or ImageMagick: runs the real masking pipeline on invented pages; `REAL_TOOLS_OK` or a word that holds the tag; not in the bite suite or CI (contributing/releases.md)
checks/relay-scan.sh <file>…               # CARE, before care prose reaches DEV or a build session: scans for personal details; 0 clean / 1 hit / 2 blinded (topics/relay-and-export.md)
PUBLISH_DEST="$(mktemp -d)/t" checks/publish-skeleton.sh   # after editing a shipped file, and before a release: build the allow-listed copy from the working tree and scan it; expect "firewall: clean", "deny-list: clean" and commit parity; no commit, no tag; the only firewall scan
PUBLISH_DEST="$(mktemp -d)/t" checks/publish-skeleton.sh vX.Y.Z   # before a public release: dry release build over the tag's tree and note, then one commit and the tag; REMOTE=<url> builds on the public copy's main, read only; pushing is a separate, held step (topics/relay-and-export.md)
checks/setup-mac.sh [pre-approve | private-mode <lang> | handouts]   # CARE, a new Mac: no argument changes nothing and reports what is there and missing; `pre-approve` lets the checks, snapshots and filing tools run without asking; the other two install private mode's tools or the handout renderer; a step needing a password or Apple's dialog prints an `in Terminal:` line and exits 2 (procedure: SETUP.md)
checks/install-instance.sh dev|care [<release-tag>]   # once per instance, idempotent: marker, git hooks, read-guard settings, tool checks; `care <tag>` pins the release last (topics/instances.md)
checks/adopt-release.sh [vX.Y.Z]            # CARE: fetch tags, check out the newest release (or the one named) without replacing an ignored file, install, board; refuses DEV and a tracked-file change; on failure prints the recovery and rollback; rerun with the same tag to finish (contributing/releases.md)
checks/reveal-private-id.sh                 # CARE intake (_templates/INTAKE.md step 4): shows the private-mode identifier file in Finder for the operator to edit; never reads it or prints its path
checks/release-notice.sh [--daily]          # CARE (the session-start hook runs --daily): is a newer minor or major release out? asks origin for tags only; exit 1 = one waits; never fetches or adopts (tools/claude-hooks/README.md)
```
`check.sh` exits nonzero if any guard fires. **Do not end a session red.** `confirms.sh` is a
**separate queue monitor, not the session gate**: a nonzero means an overdue or malformed item to
chase, or (exit 2) a scan it could not complete. It never blocks ending a session, and it stays out of
`check.sh` so housekeeping never reds the board. This file states the implemented guard contract;
known limits live in the issue list (`docs/KNOWN-ISSUES.md` in the maintainer's tree).

## Instances

**The instance marker** (DEV or CARE, derived from `checks/RECORD-SET`), the care release pin and
break-glass ticket, and **Install an instance** (`install-instance.sh`):
[topics/instances.md](topics/instances.md).

A care tree may still hold a `checks/BOARD-LOG` from the retired board log: guard ids and clocks only,
safe to delete. It stays git-ignored and `tooling` in `RECORD-SET` until a release whose note deletes it.

**Relay, token registry and export.** The CARE→DEV relay scan, keeping the token registry current,
where the registry and the private-mode identifier's file live and how to set them up, the token move
for a person's kept details, the registry block the operator pastes, and the flip-time export ceremony:
[topics/relay-and-export.md](topics/relay-and-export.md) — the operator's procedures.

## Commit gate (the guards run themselves — ADR-0022)
- **`pre-commit`** runs `check.sh` on every commit and **blocks a red working tree** — 0.6 s,
  unconditional. The commit check reads working-tree bytes.
- **No hook runs the bite suite** (ADR-0022 point 6). It runs before a pull request is
  opened and in CI on every PR: `CONTRIBUTING.md` → *Opening a build session* owns the step.
- **`pre-merge-commit`** delegates to `pre-commit` for **auto-committed merges** (clean `git merge` /
  `--no-ff -m` / `-s ours`), which git routes past `pre-commit`. `git cherry-pick` and `git rebase`
  have no pre-commit-class hook at all: they stay **ungated** — run `check.sh` after them.
- **Emergency override is two-factor and audited** — set `TABULARIUM_SKIP_GUARD=1` *and* name it in the
  commit message (pre-commit runs before the message exists, so the paired `commit-msg` hook holds the
  audit half and rejects a bypass whose message doesn't name the token).
- Hooks are git-tracked in `git-hooks/`, bite-tested (the **HOOK** cases in `selftest.sh`) and
  PORT-linted. `checks/install-instance.sh dev`, run in the main checkout, installs all four; by hand,
  copy each from `checks/git-hooks/` into `.git/hooks/` and make it executable.

**`pre-push` is instance-aware.** A push is allowed only from a tree that is **both** marked `dev`
**and** demonstrably record-free, re-derived from `checks/RECORD-SET` as L20 does; each pushed ref's
own tree is checked too, and anything it cannot read blocks. The hook's header has the full rule. It
reads only the tip tree, not the history the push carries: a record path committed and then removed
on a branch still leaves with it, so rewrite that history before pushing, and treat a remote that
already received one as needing the same rewrite. `git push --no-verify` skips the hook and leaves no
mark — a discipline aid, not an enforcement boundary.

## Guards
**Locator rule** (ADR-0029 point 11), every guard: a red names the tree-relative path it is about, withheld only inside a private-mode person's folder (its `profile.md` carries `⟨never-API⟩`) or, while withholding is on (any person is private-mode, an existing profile's status cannot be established, or the roster cannot be safely inspected), where the owner cannot be established (an absent or unreadable profile, a symlinked patient root, `_shared/`). L1/L4/L5/L7 also withhold values read from that private or unknown owner's files; L10 cannot undo an earlier echo or filter a later guard. While any person is private-mode, L5 reports hits as counts, withholding matching lines and their file names in both person folders and `reference-library/`; a grep error also withholds a private searched handle. L10 and L13's residue findings stay category-only. One rule, two copies: `loc()` in `check.sh`, `locator()` in `tools/person_ownership/fsverify.py`.

Each guard's full rule — scope, exemptions, fail-closed arms, accepted gaps — lives in its
`# ---- Ln:` section of [`check.sh`](check.sh), with the decision record that header names. A
`WARN [Ln]` line never changes the exit code.

| ID | Catches | How |
|----|---------|-----|
| **L0** | a vacuous, redirected or false green | refuses to run outside the repository or on a malformed `patients/` (a symlinked or hidden patient root reds), and a guard that examined nothing fails |
| **L1** | structural truncation or a partial write | each canonical doc keeps its required headers and a minimum length and does not end on a table row; a truncation that keeps this shape passes (the top-level `README.md` → *Limits*) |
| **L5** | person mix-up | no other person's handle, as a whole word, in a person's assistant-written Markdown (their `med/sources/` exempt, ADR-0028), nor, case-sensitive, in `reference-library/`; while anyone is in private mode only counts print; a line a UTF-8 locale cannot decode is searched as bytes, where a handle inside a longer word also reds (save the file as UTF-8), so locate a hit with `LC_ALL=C grep -a` |
| **L4** | a pending, wrong-paper, uncatalogued or invented citation — **warns, never reds** (ADR-0048) | every PMID/DOI/PMC id in a clinical doc must resolve to a `## Vetted` entry of `reference-library/index.md`, never a Candidate; freshness is not checked |
| **L6** | source-file naming drift — **warns** | files in `med/sources/` follow `YYYY-MM-DD__source__desc.ext` (`YYYY-MM__` when the day is unknown); a sources tree it cannot list still reds |
| **L7** | a moving date stated outside the open-items table | in a doc with the `OPEN-ITEMS:BEGIN`/`END` block, no future date in the live body outside that table; a broken block reds |
| **L8** | handout-file naming drift | files in `med/handouts/` follow `YYYY-MM-DD__handout-<audience>__<slug>`; an optional `__TAB-…` ID segment must validate, check character included (ADR-0033; the front-matter `id:` is the renderer's to check); `python3 -m tools.handout_attest next-id <handle> [--count N]` prints valid IDs |
| **L10** | a private-mode identifier recorded in the tree | for a person whose profile carries `⟨never-API⟩`, no run in the shape of the person's number in any text a model may read — the shape of each scheme the profile's `⟨id-scheme KEY⟩` tag names in `tools/private-mode/id-schemes.tsv`, every row of the list without an exact tag, none for a tag of the key `unlisted` alone; a tag that cannot be read, is mistyped on the marker line (a key of the list outside the exact tag included) or sits on another line of the Identity section reds (ADR-0062, ADR-0073, ADR-0077) (a dated `⟨not-an-id: verified YYYY-MM-DD⟩` line is waived), and, for a person with an identity file of kept details, none of its values in text dated on or after each value was recorded, nor a placeholder in the profile or medications with that file missing (ADR-0029, ADR-0075); output is category-only, so locate a hit with a local `LC_ALL=C grep -a`; a separate WARN (never red) when a person in private mode or holding masked output (`_redacted`) is in a tree whose `.claude/settings.local.json` does not name the session read-guard hook, answered by `bash checks/install-instance.sh care` |
| **L13** | person-ownership drift: an un-inventoried source, changed bytes, a wrong-person binding | every file under `med/sources/` needs an active record in that person's `med/MANIFEST` matching its SHA-256 and the profile's `person_record_id`, each transcription bound 1:1 to its original; only `python3 -m tools.person_ownership` (`migrate`, `init`, `append`, `refresh-checkpoint`) writes the ledger, and `tools.interview_capture file` calls the same writer (ADR-0037) |
| **L15** | handed-over bytes that are not the fact-checked Markdown's rendering | every sealed encounter unit carries an attestation whose hashes, person and date match its files, and no product shares bytes with the evidence; a draft lives in `med/analysis/drafts/` or as an unsealed unit; the legacy lane is frozen by `python3 -m tools.handout_attest freeze-legacy`/`migrate-legacy` (ADR-0039) |
| **L19** | a CARE checkout editing the product | runs only where L20 derived `care`: the working tree may change only record-set paths, and `HEAD` must be the release `checks/CARE-RELEASE` pins, reachable from origin; `checks/CARE-EXCEPTION` is the time-boxed, loud break-glass |
| **L20** | a DEV tree holding a record, a CARE tree holding none, a wrong or missing instance marker, `RECORD-SET`↔`.gitignore` drift | the mode is derived from which `checks/RECORD-SET` record paths exist and the marker only asserts it — an unknown marker, an old `migration:` included, reds; in DEV a record shape on disk or in the index reds (a shape it does not know escapes); every set entry must be git-ignored; a worktree inherits its main checkout's mode, and a CARE worktree is refused |

Retired numbers are never reused (L3, L9, L11, L12, L16, L17, L18, L21); each one's decision record
says why it went. No guard checks that a study figure is labelled as one: the reader does.

Beyond the guards, `selftest.sh` bite-tests the non-`check.sh` machinery the same way — one test plus
one negative control per kept tool; its header lists what each covers. A case that cannot run prints
`SKIP  [<id>] (LOUD)` and the summary lists the ids; `--expect-skips "<ids>"` fails the run on any other,
and CI names its set in the workflow.

## Writing a guard or a bite — the traps that fail green

Each of these produced a *passing* run, not an error — which is why a new guard is not trusted until
its bite has been made to fail.

- **The agent's shell is not the guards' shell.** A guard runs under `bash` and calls bare `grep`
  through `PATH` — BSD grep on the host — while an assistant's shell here is `zsh`, often with `grep`
  aliased to another engine: validate a pattern with `/usr/bin/grep`. Two `zsh`-only traps return
  empty results that read as a clean scan: an unbraced parameter followed by `:` takes a history
  modifier (`git show "$c:adr/README.md"` expands `$c:a` — write `"${c}:adr/README.md"`), and an
  unquoted `for x in $LIST` does not word-split. Put multi-line logic in a `bash` file.
- **BSD grep in the C locale silently drops the non-ASCII branch of a word-anchored group**
  (`\<(ascii|diacritic)\>`: one match in the C locale, three under UTF-8). Keep ASCII forms inside the
  anchored group and give each diacritic form its own anchored literal.
- **Never `|| true` a scan, and never trust a pipeline's exit status.** A pattern error (rc ≥ 2) means
  *unscanned*, not *clean*: capture it (`rc=0; HITS="$(grep …)" || rc=$?`) and abort loudly at 2.
  Without `pipefail` a pipeline reports only its last command; with it the **rightmost** non-zero
  wins, so a filter's benign rc=1 masks the scan's rc=2 and the caller reads "no hits". `while … done
  < <(cmd)` discards the producer's status entirely. Read `${PIPESTATUS[0]}` as the very next statement
  after a pipeline, or capture the scan in a command substitution and check its rc. `grep -q` also
  SIGPIPEs its producer, which reads as a failed probe where it should succeed.
- **A `case` whose patterns end in `)` cannot sit inside `$(…)`**: it passes `bash -n` and dies at
  runtime — put it in a function. A `case` glob also crosses `:` and `/`, so an exemption tested
  against whole `grep -rn` output is forgeable from file content — split the hit into path, line number
  and content, and test each field.
- **Strip git's environment in anything that runs `git init` or `git -C` from hook-invoked code.** A
  hook exports `GIT_DIR`/`GIT_INDEX_FILE`, which override `git -C`, so a fixture can retarget the real
  repository. `unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX
  GIT_OBJECT_DIRECTORY` at entry, and wrap fixture calls in `env -u …`. `selftest.sh` strips them once
  at its entry, bitten with a decoy repository set as `GIT_DIR`.
- **A bite that backgrounds, kills or sleep-races a process must skip under `TABULARIUM_NO_HOOK_TEST`**
  and have a bounded reap: a caller that captures the suite in a command substitution returns only
  when every process inheriting its stdout has exited, so a lingering child hangs it forever while the
  bite passes standalone.
- **Fixtures are deliberately minimal** (ADR-0038): `mk()` ships no `_templates/`. Scope a
  template-reading guard on a marker the real tree and the skeleton both carry (`_templates/profile.md`),
  or most existing bites fail closed for a reason their messages will not name.
- **No bite is trusted until a negative control proves it MISSes.** Mutate what it guards — one mutation
  per asserted property — confirm the MISS, restore, and `cmp` byte-identical. Run the unmutated fixture
  through the same harness first: a fixture that fails on its own makes every "catch" vacuous. Anchor a
  static bite on the invocation, never on a bare token — a grep bite will match its own explanatory
  comment.
- **When two consumers read one derivation, bite both against one fixture** and require the same verdict
  in the states that differ from the happy path; per-consumer bites and byte-identity tests both miss the
  disagreement (the worked example: one fixture bites L20 and `pre-push` together on an unknown marker
  and its `dev` twin).

## Host portability (the guards must run where the operator is)
These scripts run in **two** places: the Linux skeleton CI (`.github/workflows/skeleton-check.yml`) *and*
the operator's **macOS host** (bash 3.2, BSD userland). A guard that only runs on Linux is no safety net
on the host — worse, a half-portable rewrite can leave L5 silently scanning **zero** patients. So: no
bash-4-only builtins or syntax, no GNU-only flags. `selftest.sh` **lints** for a named list of them
(`PORT_PATS` in the suite: a list of known traps, not a parser) across every `checks/*.sh`,
`checks/git-hooks/*` and `tools/private-mode/*.sh`, auto-discovered; it runs on Linux, so CI catches a
host-only regression. A file grep cannot read is a failure, never portable, and each pattern is bitten
by a planted sample with a portable twin. L5 carries a discovery tripwire, and `check.sh` **stamps its
green line with the platform** (`uname` + bash version), so a green is attributable, not assumed
universal (ADR-0020 / ADR-0021).

Portable is worthless if it won't start. Every script the **Routine** block above documents as a direct
invocation (a line beginning at column 0 with `checks/<name>.sh`) must carry the executable bit **in the
git index**, not merely on this machine — a clone materialises the index mode, so a local `chmod` that
never reached it ships mode 644 and the documented command dies with "permission denied".
`selftest.sh`'s **EPX** lint checks both, auto-discovering its targets from this file, so a newly
documented entrypoint is covered without editing a list. Fail-closed: an unreadable README, a grep
error, a failed `git ls-files`, or zero discovered entrypoints is a failure, not a quiet pass; outside a
git checkout the index half is skipped, loudly.

## The ⟨confirm⟩ queue (`confirms.sh`)
Care-material facts resting on a low grade (C/D) or a weak source carry a dated tag on the line where
they are stated: `⟨confirm by YYYY-MM: what to obtain⟩` (the exact form CLAUDE.md specifies).
`confirms.sh` greps each person's `profile.md`, `medications.md` and every `med/analysis/**/*.md`
(working notes and handout drafts), prints each tag as `file:line` with a status — `future` (deadline
ahead), `due` (this month), `overdue` (month past) — and exits 1 if anything is overdue. It also lists
each row of the open-items table in `patients/*/profile.md` (the rows between the `OPEN-ITEMS` markers)
whose "by when" cell holds `YYYY-MM-DD` or `YYYY-MM`, with the same statuses on the month and the same
exit rule; a row with no date is skipped. Month granularity; deadlines are proposals the operator can
re-date.
- **Not scanned:** `med/handouts/` — a sealed handout is immutable, so an overdue tag there would have no
  fix, and build-QA halts on any `⟨confirm` in a handout anyway; `med/sources/`, whose transcriptions flag
  uncertainty with the undated `⟨confirm⟩` (the dated tag goes where the value enters the profile);
  `nmed/` and `_shared/`.
- **Its own locator rule, narrower than the guards' on purpose:** the fixed-shape `profile.md` and
  `medications.md` paths print for everyone — a fixed name cannot carry the identifier, and the queue
  must say whose item is due — while an analysis note's free-text name is withheld for a private-mode
  person or one whose profile cannot be read (the guards withhold the whole path inside a private-mode
  person's folder: *Guards* → *Locator rule*).
- **`MALFORMED`** (exit 1): a deadline the queue cannot read — `confirm`, `by` and a four-digit year not in
  the exact form (a non-breaking space or a tab, a short month such as `2026-1`, a month outside 01–12),
  or a by-when date whose month is not 01–12. Rewrite it in the exact form; it may hide an overdue item.
  Prose with "confirm" alone, or "confirm by" before anything but a year ("confirm by phone", the
  templates' `YYYY-MM` placeholder), is never a tag; a year-only phrase such as "confirm by 2026"
  reads as malformed — write it as a tag.
- **Fails closed** (exit 2): a ROOT that is not the repository, a file it cannot read, or a folder `find`
  cannot list prints what it did read and exits 2 — a partial queue, never "no tags". A repository with
  no `patients/` is an empty queue (exit 0); the summary line counts the files scanned.

## Recovery
- A bad write to a **canonical doc** is recoverable when a verified snapshot exists: `diff` the live file
  against the newest `.snapshots/<ts>/` copy, `cp` it back. Snapshots are append-only and pruned only by
  hand. A snapshot the current script made is valid only when `.snapshot-complete` exists at its timestamp directory's root; a
  nested or partial publication returns nonzero and lacks that marker.
- Anything **outside** the canonical docs — a lost `med/sources/` scan above all — comes from the newest
  **validated** `outputs/_snapshots/<ts>__worktree.tgz` tarball (backup layer 2); `.snapshots/` does
  not hold it.
- Both scripts publish owner-only artifacts (`0700` directories, `0600` files) from private staging
  only after copy/archive validation, refuse same-second clobbers, and refuse symlinked recovery
  destinations.
- Before trusting a recovery point, independently compare it with its promised input set. The
  [care contract](../CLAUDE.md#safeguards) owns preflight, writer quiescence and the edit sequence.
- The snapshot flushes its copies to disk before publishing them, best effort and never refusing a
  snapshot (the script's header has how, per platform). A write error the disk reports only at that
  point is not detected, and sudden power loss can still lose data.

## Version control & backups
**Records are never committed, and the instance that pushes holds none (ADR-0017, ADR-0050).** The
records live in a **CARE** checkout that never edits a tracked file (L19) and never pushes: its
`pre-push` refuses on the `care` marker alone, and its `origin` exists only to *fetch* DEV's release
tags. **DEV** is record-free by construction (L20 derives that from the tree, not the marker) and is
the one instance that pushes, to a **private** remote. Either way PII cannot leave the machine by git:
it is in no history to push. Publishing a de-identified skeleton is a *separate, deliberate, gated*
step (`publish-skeleton.sh`, held behind `checks/PUBLISH-HOLD`): an allow-listed **export** of a
release tag, carrying none of DEV's history.

**Git does NOT back up patient data — do not rely on it as one.** Every `record` path of
`checks/RECORD-SET` is git-ignored, so git versions the skeleton only. The records have three recovery
layers; [topics/backups.md](topics/backups.md) has what each holds, how to set it up and its limits:
1. `.snapshots/` — CARE-only append-only copies of the canonical docs via `snapshot.sh`, inside this
   folder; not `med/sources/`.
2. tarball — `outputs/_snapshots/<ts>__worktree.tgz`, a whole-tree copy via `backup-tree.sh`,
   including the raw evidence. Run it as a habit.
3. **off-machine mirror** — `checks/backup-offsite.sh` (ADR-0045), a one-way append-only copy of
   `patients/` + `_shared/` into a folder you choose, on an external drive or synced by a cloud
   client: the only layer that survives losing the laptop. Set it up once (the folder's path, then a
   `.tabularium-offsite-ok` marker inside it) as the topic doc says. A provider that does not encrypt
   end to end can read the copy.

Local git is DEV's own history of the **skeleton** only — **not** a patient-data backup.

## Deferred controls

Citation-freshness automation (cited papers are not rechecked on a schedule: the top-level `README.md` → *Limits*)
and the L14 INDEX/ID proposal are unbuilt. Neither is an implementation commitment. L4 membership (a
warning), manual citation review, L8 filename validation, manual INDEX discipline and L15 encounter
binding continue unchanged.
