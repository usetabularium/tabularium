# Instances, layout and export

Read when: you touch a record path, `checks/RECORD-SET`, the instance files or the installer;
install hooks or work across worktrees; read CARE files or relay something learned in CARE; make
Tabularium store anything outside its working folder; or work on the export.

## Two instances, one product (ADR-0050)

**DEV** is the development tree: it never holds a record, a
handle, a real date or a token list, and it is the only place code, templates, guards and ADRs change.
**CARE** is a pull-only checkout of a DEV release tag plus the record directories named in
`checks/RECORD-SET`; it never edits a tracked file. The untracked marker `.tabularium-instance`
(`dev` | `care`) only *asserts* the mode — guard **L20** derives it from whether
records exist and reds a mismatch; **L19** reds any tracked-file change in CARE and pins the adopted
release (`checks/CARE-RELEASE`; break-glass `checks/CARE-EXCEPTION`, bounded to seven days, every use
recorded). Anything learned in CARE, a lesson for the tool included, enters DEV's tracked files only
as **abstract prose** — no name, place, folder handle, date or clinical detail, and nothing copied word
for word from a care-folder file — never as a file copy, and **scanned first** by
`checks/relay-scan.sh` for personal details (ADR-0072; reading is fine: *Reading CARE from a build
session*, below). The token registry itself lives outside every
repository (`checks/FIREWALL-REGISTRY` names it) and is never committed, published or pasted into a
tracked file. Its one secret — the private-mode identifier — sits in its own owner-only file
(`checks/PRIVATE-MODE-ID` names it), and **that file is never read into a model session**: the
read-guard hook denies the attempt, and protects the whole registry until the installer has verified
the split (ADR-0050 point 9; setup in `checks/topics/relay-and-export.md`). A care-only install has
neither file and needs neither (ADR-0068). **None of this is care-session
work:** a care session orients on `CLAUDE.md` and guard output, and never reads `docs/`, the code in
`checks/`, the top-level `_archive/` or the instance files; `CLAUDE.md` → *Context* names the
procedures a care session does read.

## Reading CARE from a build session

When the operator asks a build session to look into care sessions, it may read CARE: the care
project's Claude Code transcripts (`~/.claude/projects/<care checkout>/`), care-side notes and any
file in the care checkout, records included. The effect is the operator pasting them, and the data
is theirs; guard what comes back, not the read (ADR-0050 point 8).

- **Read-only.** A build session never writes, moves or deletes anything in the care checkout.
- **Never read:** the private-mode identifier's file, `checks/PRIVATE-MODE-ID`,
  `checks/FIREWALL-REGISTRY`, a snapshot folder or a backup tarball — the last two bank copies of
  everything below.
- **A transcript** (`*.jsonl`) is, near enough, what that care session already sent to the AI API, so
  it needs no scan; the residue is tool output the client stored in full but cut short for the model.
  Anything else in that folder counts as a note.
- **Records** (`patients/`, `_shared/`) may hold what no session has sent, so they are read as a care
  session reads them (`CLAUDE.md` → *Context*): a person's `profile.md` first, in a step of its
  own; for a private-mode person, the approved masked copies and their transcriptions only — never an
  unredacted original, the pipeline's source map or a `*.never-api-identity.json`. The read-guard
  hook recognises these by absolute path from a DEV session too, where it is installed.
- **Any other note** is scanned first with `checks/relay-scan.sh`, run from the care checkout or DEV's
  main checkout (a linked worktree has no registry pointer, so its scan comes back blinded); lines it
  flags `PII_PRIVATE_*` are read only from a copy with them replaced by number
  (`checks/topics/relay-and-export.md` → *The CARE→DEV relay*).
- **What comes back** — a tracked file, a commit message, a pull request — is abstract prose with no
  handle, real date or token and no line copied from CARE, and the same scan passes it clean first.
- **The client's own permission layer** may still ask or block such a read. That is the operator's
  setting, not a repo rule: tell them, never work around it.

## Scratch worktrees

**In a scratch worktree** (ADR-0040) the instance is the **main checkout's**: marker and records are
untracked, so L20 reads both from the main checkout and prints `inherited` (ADR-0050 point 7). So:
- Never write `.tabularium-instance` in a worktree — a second assertion can only drift, and L20 reds
  one that contradicts the family.
- Install marker and hooks **in the main checkout**: one hooks directory serves every worktree, and an
  install from a worktree would overwrite the family's hooks with that branch's. In a worktree,
  `checks/install-instance.sh` skips both and installs only the per-tree read-guard settings and
  skills. A worktree session needs no copy of its own on a current client: Claude Code reads a
  worktree's settings and skills from the main checkout, so that copy serves only an older one.
- A worktree of a CARE checkout is refused by the guard, not merely by the skill's absence. The
  client may open care sessions in a worktree by default, so the refusal leads with the record-work remedy:
  a new session, started by the operator, in the main care folder with the worktree option off.
- A family the guard cannot verify (bare repository, separate git directory, main tree gone,
  unreadable marker) inherits nothing, says so loudly, and this tree's own marker governs as in a plain
  clone — deliberately not a red; hard refusals are kept for the verified case, where records are at
  stake.

The derivation lives in one place, `check.sh --instance-mode`, which the push hook and the installer
call rather than reimplementing.

## Repository layout — the machinery

`CLAUDE.md` carries the patient-facing half of the tree (`patients/`, `_shared/`); `reference-library/`
and `_templates/` are in the top-level `README.md` tree. The rest is the build contract's:

```
checks/            executable guards and tooling: session board (check.sh), bite-tests (selftest.sh),
                   pre-edit snapshot, backups, queue monitors, commit hooks, CARE→DEV relay scan,
                   per-instance installer, Mac setup, flip-time export gate + hold sentinel. RECORD-SET = the one
                   list of paths that are not product. Index: checks/README.md — run the board every session
adr/               architecture decision records (why/when); see adr/README.md
contributing/      the build contract's topic docs, each routed from CONTRIBUTING.md
tools/             host-side utilities (seven folders ship — the two claude-* folders file by file;
                   session_counts/ and the top-level __init__.py do not):
                   session_counts/ = counts-only report on live sessions from local transcripts,
                   run by the operator (ADR-0049 point 22);
                   private-mode/ = experimental local ID redaction (ADR-0029 — read its README before any
                   private-mode ingestion); person_ownership/ = L13 ledger (ADR-0037); handout_attest/ =
                   L15 sealed-unit binding (ADR-0039) + next-id (ADR-0033); original_view/ = a light
                   raster of a large original, refused for private mode (ADR-0037 §14);
                   interview_capture/ = files on-screen interview answers word for word from the
                   session transcript (ADR-0041); claude-hooks/ =
                   the PreToolUse read-guard for the private-mode identifier's file + its deny/allow
                   matrix (ADR-0050 A1), the development-tree PostToolUse context-health notice and
                   the care-tree SessionStart release notice (ADR-0055 companion); claude-skills/ =
                   the /architect, /private, /update and guard-admission skills with a README,
                   installed by checks/install-instance.sh (/architect and guard-admission into
                   development trees only, /update into care only; all four ship)
cc-prompts/        retired host-task prompts 001–036 + register — the maintainer's care instance only,
                   a record path; never created by a new install
outputs/           backup tarballs (PII) — a record path, CARE only, never published
.github/           Linux CI; skeleton-check.yml owns triggers and jobs (workflow: CONTRIBUTING.md → How a change lands);
                   ISSUE_TEMPLATE/report.md asks issue writers to leave out personal and health details
evals/             behavioral eval (ADR-0049): cases/ (per-file ALLOW; a new case stays private until
                   promoted — cases/HOLDOUT), profiles/, harness/ ship; results/ = run ledgers and
                   scores, tracked in DEV, not exported; local-masking/ (frozen benchmark, ROADMAP F1) = tracked in DEV, not
                   exported. A run is recommended, not required (ADR-0049)
docs/              limitation registers, roadmap, runbooks and drafts — DEV-local:
                   untracked, main checkout only; strategy/ = private notes, a record path (CARE).
                   Load only for matching system work, never for care
_archive/          retired cold storage for old helpers — the maintainer's care instance only, a record
                   path (ADR-0030); never created by a new install. No instance uses a top-level
                   _inbox/ (a root rule still ignores a stray one)
```
Three more top-level directories are **never tracked and never published**: `.snapshots/` (recovery
layer 1, written by `checks/snapshot.sh`; a record path — CARE only), `.venv-render/` (the pinned
handout-render environment, built per instance; no rendering or sealing without it), and
`.claude/worktrees/` (scratch worktrees; retire only via `checks/retire-worktree.sh`, ADR-0040).

## Storage outside the working folder

Where Tabularium keeps something lasting outside its working folder — the offsite backup, eval archives
— the place is the operator's choice: a folder they configure, optional, with no provider as the only
route (a cloud sync folder, an external drive or a network share all serve; a provider appears at most
as an example). A default, if there is one, stays on this disk (eval archives: the scratch folder);
temporary working files are not covered. A configured folder that does not exist is never created (an
unmounted drive must not swallow data), and no path naming an account enters a tracked file (eval
archives also keep one out of everything they print; the offsite backup prints its destination to the
operator's own terminal). Who can read a records backup depends on where it lands: a provider that does
not encrypt end to end can read it (ADR-0067).

## Publishing — the export process

> **Each export needs an explicit, current operator request**: never inferred from context, a roadmap
> line or a prior plan. If in doubt, don't export.

Publishing is a firewalled, allow-listed **export**: a copy of a release tag's tree taken from DEV with
none of DEV's history, appended to the public copy (ADR-0066), scanned against the registry, run by
`checks/publish-skeleton.sh` and held by `checks/PUBLISH-HOLD`.
Before an export the operator brings the registry up to date — the handles, dates of birth and
distinctive names filed since its last change (`checks/topics/relay-and-export.md` → *Keep the registry current*);
a token never added is invisible to the scan.
It is never a visibility flip of a repository's history — pushing DEV to its private remote is not
publishing, and the records have no remote of any kind. The procedures — relay scan, registry upkeep,
the private-mode identifier's file, the export ceremony: `checks/topics/relay-and-export.md`.