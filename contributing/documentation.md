# Documentation, decisions and handovers

Read when: you add, move, rename or retire a doc; grow or split a doc a session loads whole; change
a fact other docs state, or remove a passage; add or change a rule in `CLAUDE.md`; write an ADR, a
proposal, a runbook or a brief for another session; state what an evaluation shows; make a
structural decision; or change an issue's status.

## Documentation map (where each kind of doc lives — for discoverability)
The [layout tree](instances.md#repository-layout--the-machinery) is the *folder* view; this is the *doc-kind* view — read it to know where a given
kind of writing belongs. One fact, one home; don't restate the same fact across docs.

### Current-state ownership

`docs/` is the maintainer's own: `docs/KNOWN-ISSUES.md`, `docs/ROADMAP.md`, `docs/FLIP-RUNBOOK.md` and the
rest are absent from an export. An adopter keeps the same kinds of list wherever suits them, for example
their repository's issue tracker, and reads each mention of them in this contract as that.

- **Issue status, acceptance criteria and closure evidence:** `docs/KNOWN-ISSUES.md` owns active
  issues, `docs/KNOWN-ISSUES-CLOSED.md` resolutions and `docs/ACCEPTED-RISKS.md` accepted risks. Move rows on state
  transitions; one authoritative row per ID. Routine backlog work reads only the active file.
  Consult a specific archived entry for subsystem changes or regressions; review accepted-risk
  triggers at release and relevant user/client/threat/access changes. Other docs cite the appropriate
  owner by ID, never copying a register row; they do not maintain another status list. These
  registers are DEV-local, so what they say about limitations stays off the remote; from a worktree,
  read them at `"$(git rev-parse --git-common-dir)/../docs/"`.
- **Required workflows:** `CLAUDE.md` for care and shared safety, `CONTRIBUTING.md` and its
  topic docs for building.
  `checks/README.md` owns tool usage and recovery instructions, and
  `checks/topics/relay-and-export.md` the operator's relay, registry and export procedures. Keep the
  detail a reader needs to act,
  and link to the owner for the rest.
- **Decisions and dated evidence:** ADRs hold decisions; change logs and pull requests hold dated
  evidence. These records describe what was decided or observed then; consult the current owner
  before treating a historical statement as today's instruction.

When changing a fact, update its owner and search for the affected claim and IDs in current guidance.
Replace duplicate status or implementation summaries with links; retain any action-critical warning.
Before removing a passage, verify that its unique rationale, constraints and evidence have a durable
home. An accepted ADR is not rewritten: a changed decision gets a new ADR that supersedes it
(`adr/README.md`, ADR-0061). Dated logs remain historical. Required
reconciliation of a template-derived per-person record (`profile.md`, `medications.md`, the handout
register) still follows the KI closure checklist and `CLAUDE.md` — these links do not replace
self-contained patient records or load development docs into care context. The policy docs under
`_templates/person/` are shared, not copied into a person's folder, so changing one needs no per-person
reconciliation.

| Kind of doc | Home | Notes / governed by |
|---|---|---|
| **Keystone / operating contract** | `CLAUDE.md` | always-read; the care rules and the patient-facing layout. Ships (abstract). |
| **Codex entry surface** | `AGENTS.md` | required by Codex/`AGENTS.md`-aware agents; points first to `CLAUDE.md`, which routes build work to `CONTRIBUTING.md` — never a content copy. Ships (abstract). |
| **Build contract** | `CONTRIBUTING.md` + topic docs in `contributing/` | read in a build session: the entry file holds what every build session needs and routes each task to one topic doc (*How this contract is split*). Ships. |
| **Canonical patient truth** | `patients/<h>/profile.md`, `medications.md` | what's true *now*; each keeps a change log. Local. |
| **Evidence (raw)** | `patients/<h>/med/sources/` | immutable, append-only; grade A. Local. |
| **Generated outputs** | `patients/<h>/med/{handouts,analysis}/` | analyses and unsealed drafts regenerable; sealed encounter units retained and superseded, never edited or deleted. Local. |
| **Architecture decisions and proposals** | `adr/NNNN-*.md`, one file per decision, indexed in `adr/README.md` | why/when; one decision per file, superseded rather than amended (ADR-0061); Proposed distinguishes discussion from accepted policy. The index holds one line per decision (number, title, status); the reasoning lives only in the file. Ships. |
| **Release notes** | the annotated `vX.Y.Z` tag's message | ADR-0054; written once, in the [releases.md](releases.md) template. Never a file; no GitHub Releases in DEV. |
| **Confirmed system limitations** | `docs/KNOWN-ISSUES.md` (active); `docs/KNOWN-ISSUES-CLOSED.md` (resolved); `docs/ACCEPTED-RISKS.md` (accepted) | read per *Current-state ownership*; the active register owns lifecycle rules. DEV-local. |
| **Record set / instance tooling** | `checks/RECORD-SET` (tracked) + the untracked `.tabularium-instance`, `checks/FIREWALL-REGISTRY`, `checks/CARE-RELEASE`, `checks/CARE-EXCEPTION` | ADR-0050; one list, read by L19/L20, mirrored by `.gitignore`; `checks/install-instance.sh` writes the per-instance files. |
| **Product roadmap** | `docs/ROADMAP.md` | the tool's forward direction (privacy/durability, guards, templates). DEV-local. |
| **Release + strategy** | `docs/strategy/` (RELEASE-ROADMAP, DISTRIBUTION-NOTES, LICENSING-NOTES) | packaging / licensing / distribution. Local. |
| **Runbooks, drafts and other private planning** | a named file in `docs/` (e.g. `docs/FLIP-RUNBOOK.md`) | DEV-local. Deleted when its work lands; move any live decision to an ADR, `docs/KNOWN-ISSUES.md` or `docs/ROADMAP.md` first. The flip runbook stays until the flip; every executed push is logged in `checks/PUBLISH-HOLD`. No instance uses a top-level `_inbox/`; a root rule still ignores a stray one (ADR-0030 point 7). `cc-prompts/` and the repo-root `_archive/` are retired record paths of the maintainer's care instance only; a new install never creates them. |
| **Public-facing front matter** | `README.md`, `NOTICE.md`, `CITATION.cff`, `LICENSE`, `TRADEMARKS.md` | what a recipient of the skeleton reads. The `README.md` technical description owns what the project is technically; the `CITATION.cff` abstract follows it. `NOTICE.md` owns the intended-purpose wording; the README's intended-purpose statement stays in sync. Ships. |
| **Human orientation** | the public website, **https://usetabularium.com/how-it-works/** | ADR-0051: no tracked generated HTML here; humans orient on the website, agents on `CLAUDE.md`. |
| **Reference library** | `reference-library/` (README ships; index/lists local) | a cache of vetted citations, added as they are cited; two-tier verification. The index starts from `_templates/reference-index.md`. |
| **Build-session declaration** | `tools/claude-skills/architect/SKILL.md` → installed to `.claude/skills/architect/SKILL.md` | ADR-0053; the `/architect` skill, installed by `checks/install-instance.sh` in development trees only (a care checkout gets nothing; that absence is the refusal). A pointer, never a contract: the rules live in `CLAUDE.md` and `CONTRIBUTING.md` → *Opening a build session*. **Ships** — adopters edit it for their own setup. |
| **Private-session declaration** | `tools/claude-skills/private/SKILL.md` → installed to `.claude/skills/private/SKILL.md` | ADR-0029 point 10; the `/private` skill — an optional early declaration of the private-mode posture, which a session also takes by itself from the profile marker (same point, 2026-10-25). Installed into **every** instance by `checks/install-instance.sh` (a care-side declaration; a worktree gets it too). A pointer, never a contract: the protocol's home is `tools/private-mode/README.md` → *Opening a private-mode session*. **Ships**, named as a file. |
| **On-screen interview capture** | `tools/interview_capture/` | ADR-0041 points 3 and 6; copies on-screen answers word for word from the session transcript into `med/sources/interviews/`, verifies a filed copy and checks quotations that cite one. `CLAUDE.md` names it; the method lives in the filing procedure (`_templates/person/med/sources/README.md` → *Filing on-screen answers*). Replaced the interview skill and its sheet. **Ships.** |
| **Guard-admission skill** | `tools/claude-skills/guard-admission/SKILL.md` → installed to `.claude/skills/guard-admission/SKILL.md` | ADR-0059 point 4; admission test for a new or tightened control. Installed in development trees only. **Ships**, named as a file (operator, 2026-10-11), as does the folder's `README.md` (one line per skill and how to install). |
| **Update skill** | `tools/claude-skills/update/SKILL.md` → installed to `.claude/skills/update/SKILL.md` | ADR-0055 companion, accepted 2026-10-25; `/update` runs `checks/adopt-release.sh` at the operator's word and reports the outcome in plain words; the release notice at session start points to it. Installed in care trees only. It holds the `/update` steps; `contributing/releases.md` owns the release and adoption rules. **Ships**, named as a file. |
| **Templates** | `_templates/` | profile / medications / handout scaffolds. `_templates/person/` holds the shared policy docs (the filing checklist and its topic pages, the capture guide, the intake-tray note), read from there in every person's session and never copied into a person's folder, and the handout register copied at scaffold. Ships. |
| **Live-session counts** | `tools/session_counts/` | ADR-0049 point 22; reads the care checkout's local transcripts with no model call and writes ids, dates, rule names and counts only: the edit sequence, and read-guard refusals with what ran next. The operator runs it; its output is relay-scanned before a build session reads it. Command and limits in its `README.md`. Tracked in DEV, **not exported**. |
| **Behavioral eval** | `evals/` — `cases/` (scenario specs), `profiles/` (eval-mode addendum + manifests), `harness/` (runner, grader, controls, regrade, containment), `topics/` (topic docs), `results/` (append-only run ledger) | ADR-0049; tests the *agent's* behavior under this stack on synthetic fixtures (`checks/` tests artifacts). `results/` (ledgers, sidecars, `scores.csv`) is tracked in DEV, not exported; `local-masking/` (frozen benchmark, ROADMAP F1) is tracked in DEV, not exported; the rest ships (cases per file; `cases/HOLDOUT` keeps a new case private until promoted). A run after a load-bearing change is recommended, not required (ADR-0049). |

"Ships" = in the publish ALLOW-list; "Tracked in DEV, not exported" = product held out of the export
until a deliberate promotion; "Local" = a `checks/RECORD-SET` path (gitignored + publish-DENY; lives
in CARE); "DEV-local" = untracked in the DEV main checkout's `docs/`, never exported.
`RECORD-SET` and the export script's ALLOW/DENY arrays are the two lists; `.gitignore` mirrors both —
guard L20 checks the RECORD-SET half, git history the export script's half.

## Conventions — the building lane

- **An ADR is for a decision that meets `adr/README.md` → *Essentials only*** (its own
  `adr/NNNN-*.md` file and a line in the index) — so we track why/when and don't relitigate. Any other
  change is explained in its pull request and commit; routine content edits stay in change logs.
- **Proposals stay durable and visibly proposed.** Substantial design reasoning and acceptance
  criteria live in tracked ADRs; discuss in their PRs, and conclude by accepting or rejecting the
  ADR. Merging a Proposed document does not accept its policy. A `docs/` runbook may point to it for execution but must not
  be a specification's only home. ADR-0056 proposes the next retrieval step.
- **Open work lives in `docs/KNOWN-ISSUES.md` and `docs/ROADMAP.md`** — one issue list. Findings go
  in the pull request body or a known-issue row; private planning (a runbook, a
  draft) goes in a DEV-local `docs/` file. A handover is the brief one session passes another — the
  files to read, the scope, the preflight, the deliverable, and any constraint that would do real
  damage if missed — plus the pull request body for what was done. Nothing goes to an inbox. Delete a
  runbook when its work lands; the flip runbook stays until the flip.
- **A doc a session loads whole carries rules, not history.** `CLAUDE.md`, `AGENTS.md`,
  `CONTRIBUTING.md`, the docs they point to, topic docs and skills cost context in every session
  that reads them: state the current rule and at most a clause of why. A decision's longer rationale
  and dated operator rulings go to its ADR; a changed decision gets a new ADR. Other provenance and
  incident history go to the commit and pull request, which also keep the old wording.
- **A doc split by role** keeps an entry file (what every reader needs, plus one line per topic doc
  saying when to read it) and puts its topic docs in a folder of their own beside it, as
  `CONTRIBUTING.md` and `contributing/`, or `tools/private-mode/README.md` and `topics/`. Each topic
  doc opens with a `Read when:` line and does not restate the entry.
- **An evidence claim says what was measured, and where.** "Fewer detected lapses", "in these
  runs", "on synthetic records", the model named, the run's date or tag. Never "safer",
  "certifies", "proven", a patient outcome, or a trend across model sizes from two models. The
  method's aims may be stated as aims.
- **A change to `CLAUDE.md`'s emergency section** also recommends the emergency stress test's
  current-rule arm, with its cost (`evals/topics/emergency-stress.md`).
