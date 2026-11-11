# ADR-0050 — Two instances: a development tree that never holds PII, a care instance that is never developed

- **Status:** Accepted 2026-09-06; point 11 superseded by ADR-0049 2026-09-07; point 4 superseded in part
  by ADR-0066 (a single-commit, history-free export) 2026-11-07; point 9 superseded in part by ADR-0068
  2026-11-07; point 4's flip hold deprecated 2026-11-08; point 17 superseded in part by ADR-0071 2026-11-08;
  point 8 superseded in part by ADR-0072 (the relay scan's classes) 2026-11-08
- **Date:** 2026-09-05 (revised 2026-09-06)
- **Deciders:** operator (+ assistant; steelmanned by a second fresh-context model session on
  2026-09-06, whose findings and dispositions are recorded below)
- **Amends:** ADR-0012 (the scripted export stops being the routine path and survives only as the
  public-flip gate); **ADR-0013, reversed in part** (the clinical-fingerprint scan runs only where
  records could cross, at the CARE→DEV relay and the public flip, no longer on every shipped-surface
  edit); **ADR-0017, reversed for DEV** (DEV has a remote; the records are never committed
  anywhere); ADR-0027, ADR-0036 and ADR-0046 (guards L9, L12 and L18 retire; ADR-0036's D1 and D2
  survive); ADR-0049 (containment requirements 6 and 7, point 6); ADR-0031 (its cloud-CI rejection
  premise dissolves for DEV); ADR-0009 (point 17 widens its out-of-folder warning to a read-only
  answer, 2026-10-27); ADR-0038 (Part B: `mk()` copies no firewall artifact). ADR-0045 is
  unchanged; its single-egress rule is re-affirmed (point 13).
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The founding structure (ADR-0007, 0012, 0013, 0017) put the product (tracked, publishable) and the
records (gitignored, local) in one working tree, with a firewall between them: token classes, a
checkpointed registry (L12), a session-time surface sweep (L18), an allow-listed export with its own
scan, consent gating (L9), the FIRE bites, Tier-S ceremonies for every shipped-surface edit, and a
self-reference trap every author had to remember. Measured on 2026-09-06: roughly 1,200–1,400 lines
of script, guard and bite code, permanently load-bearing, whose only job was to compensate for PII
and product sharing a tree.

The trigger is not the justification. On 2026-09-05 a bounded read of the export list in a
development session overran and printed the whole token registry, including the identifier class
private mode exists to keep off the API, into a model session. No care work was involved;
the tree simply held what must never be printed. That incident has a twenty-line fix (Part A). The
justification is the recurring tax: at least five recorded incident classes, none a careless
operator's fault — an unanchored export glob that dropped a directory; a consent-class token that
collides with ordinary test prose, kept as a permanent over-mask; L18's self-skip false green in
worktrees; a subagent brief that put live specifics onto a shipped surface (caught by L18,
2026-08-16); and the registry print. All five exist only because product and records share a tree.

The alternative was proven: the behavioral eval (ADR-0049) found a real defect on synthetic fixtures
without a single real record, and `selftest.sh` has been synthetic since ADR-0038. The operator's
question, in spirit: *wouldn't two instances be easier — one for development that never contains
PII, one for care that is never developed?*

## Decision

Accepted on 2026-09-06 by the operator after the steelman review returned *adopt-with-changes*:
"implement parts A and B". Both landed the same day (point 13). What holds now:
`contributing/instances.md`, `checks/README.md` (the instance marker, *Install an instance*, the
`pre-push` hook, the L19 and L20 rows), `checks/topics/relay-and-export.md`, `checks/RECORD-SET`
and the header of `checks/install-instance.sh`.

### Part A — the registry leaves the model's reach

1. **A1: a session read-guard.** A Claude Code `PreToolUse` hook denies any Bash command, file tool
   or content search that would read, copy or print the registry, and lets metadata-only work run.
   It is a discipline aid, not an enforcement boundary: it closes the honest-slip class the incident
   belongs to, not an adversary.
   Decided on acceptance to land first, as repository tooling wired per instance by the installer;
   it landed that day (`ecd9711`), proven live by a Bash probe and a file-tool decoy, both denied.
   It shrank to the private-mode identifier on 2026-09-16 (point 9). Rules:
   `tools/claude-hooks/README.md`.

2. **A2: the registry moves outside every repository.** The token arrays leave the export script for
   one owner-only file outside every repository, named by the untracked pointer
   `checks/FIREWALL-REGISTRY` (the `checks/OFFSITE-DEST` pattern of ADR-0045). Decided on
   acceptance: A2 is folded into Part B; the arrays are moved by a **content-blind transformer** — a
   script reads the file, no model session does — and the export script is slimmed only once it
   holds no token. The five `PII_*` class lines moved that day, proven lossless by digests that
   never printed a value. **The second move (WP8, 2026-09-06)** took out the component words of the
   guarded brand phrases, which the export gate still carried as literals one push from the DEV
   remote once Part B made the script tracked; they became one `BRAND_ADJ_PAIRS` registry line,
   named so that every class counter still counts five. Decided, fail-closed: a missing or empty
   `BRAND_ADJ_PAIRS` aborts the export, because an old registry or a copy banked before the move
   must not export quietly; the cost is that an adopter must define it. WP8 also made `docs/` a
   positive list, because a recreated private publishing note would otherwise become tracked by
   default; the later blanket exclusion of `docs/` is in `.gitignore`. Mechanics:
   `checks/topics/relay-and-export.md` → *The token registry*.

Part A fixes the trigger and only the trigger: the five incident classes, the inert CI, the merged
assistant memory and the care-utility dilemma remain. That is why Part B exists.

### Part B — two instances, one product

3. **DEV, the development tree.** The existing private skeleton repository becomes the primary
   repository: tooling, templates, guards, ADRs, the eval. **It never contains a record, a handle, a
   real date or a token list, hashed or plain.** Development happens only here, against synthetic
   fixtures and the eval. It pushes to its private remote, only from a record-free `dev` instance.

4. **Publishing stays an export, not a visibility toggle.** The public flip remains held; when it
   comes, it is a fresh, allow-listed, history-free export from DEV gated by the export scan;
   ADR-0013's clinical-fingerprint control also remains at the CARE→DEV relay (point 8). DEV's
   history (about 156 commits at the split), its messages and its ADR context paragraphs had never
   been scanned, and a visibility flip would publish them irretrievably; they are never published.

5. **CARE, the consumer instance.** A pull-only checkout of DEV at a release tag, plus the record
   directories that are never committed anywhere (`checks/RECORD-SET`'s `record` entries, the
   PII-laden historical registers among them as cold storage). **It never edits a tracked file** and
   runs care sessions only. It moves by fast-forward to a release tag in a *release-acceptance
   session* — board green, guard noise reviewed against the live corpus — and rolls back by checking
   out the previous tag, always clean. Adoption is now one command (`contributing/releases.md`;
   ADR-0054, ADR-0055); its template-block re-sync went with L16 on 2026-10-04. Every backup layer
   runs in CARE only.

6. **L19 and L20, over one record list.** `checks/RECORD-SET` names the record paths, and L19, L20
   and `.gitignore` consume it, with a drift check.
   - **L19 (CARE):** the working tree is clean apart from the record set, untracked-but-not-ignored
     files included, and `HEAD` is a release fetched from DEV, never a local tag. **Break-glass:**
     an untracked `checks/CARE-EXCEPTION` (reason, date, expiry within seven days) turns that red
     into a LOUD yellow; the fix must land in DEV within the window, and every use is named in that
     fix's commit and pull request. Without it, a renderer fault mid-encounter-prep would leave CARE
     red for days and train blindness.
   - **L20 (every tree):** the mode is *derived* from whether record directories exist, and the
     untracked marker `.tabularium-instance` (`dev` | `care`) only *asserts* it; a mismatch or a
     missing marker reds. A marker that *selected* the mode failed open in the dangerous direction:
     DEV mis-marked `care` would have silenced the one guard keeping records out. In CARE no roster
     handle may match `evalperson-*`, replacing ADR-0049's containment requirement 7. For
     requirement 6, the eval scans wherever a registry resolves; without one, a record-free tree
     records not-applicable and a record-bearing tree aborts (ADR-0049 element 5).

7. **The instance belongs to the checkout family, derived in one place** (2026-09-10). L20's inputs
   are untracked, so a scratch worktree (ADR-0040) had neither and derived no mode: `/architect`
   could not open (ADR-0053's key is the derived mode) and `pre-push` blocked on "no marker", in the
   only kind of tree that exists to edit the product. The operator hit both that day. Decided:
   - **One repository is one instance.** Marker and observable are read from the family's verified
     main checkout, found from `--git-common-dir`; the worktree must still be record-free itself.
   - **Derived once.** `checks/check.sh --instance-mode` gives the answer, and L20, the `pre-push`
     hook and the installer consume it (later the snapshot script too). The first version wrote the
     derivation three times: one defect cost three fixes and two copies disagreed about one tree.
     Copy-verbatim with a byte-identity bite was the wrong tool for a rule with three consumers.
   - **The asymmetry (operator, 2026-09-10).** Some checks exist to protect records, and DEV should
     not be taxed at the same rate; the threat model is a single competent operator making honest
     slips, not an adversary constructing filesystem shapes. Where the family is **verified**, a
     CARE family's worktree is refused and a records-holding family reds, because a wrong answer
     there costs a record. Where it **cannot** be verified (bare, `--separate-git-dir`, main tree
     gone, unreadable marker), nothing is inherited, it is said LOUD and the tree's own marker
     governs — no red, because a wrong answer in DEV costs a rerun. With no marker, no mode is
     derived.
   - **Reviews.** Two adversarial rounds found the `git worktree list` reading failing open three
     ways and its replacement trusting `core.bare`, one config bit already flipped here by accident;
     fixed by removing mechanism: no git config is consulted. A third round, briefed under the
     threat model above (ADR-0031 point 5), found guard and hook disagreeing about one
     tree, so one derivation was not enough: the fix added bites that run the board and a real push
     on one fixture and require the same verdict (§15w8).
   - **Those agreement bites were dropped** in the 2026-10-04 suite shrink, with no decision naming
     them. On 2026-10-11, after their port passed 26/26 on that day's main, the operator declined
     immediate restoration; the disposition is kept in the local register.

8. **Incidents flow one way, and the scan sits where the tokens are.** A failure seen in CARE
   becomes a keystone rule, an ADR row or an eval case written in DEV, abstractly — prose composed
   in the CARE session, never a file copy. **The relay scan runs in CARE**, on the outgoing prose,
   before anything is pasted: CARE holds the registry legitimately, so it scans every class, exactly
   the ones a narrative write-up leaks by habit. DEV holds no token list of any kind. The scan
   catches tokens, not a re-identifying clinical picture told in fresh words; there the keystone's
   abstraction rule and the CARE author's judgment remain the control.
   - **A recovery exception (2026-09-09), since deleted.** The migration moved `_inbox/` wholesale,
     landing four handovers about DEV machinery in CARE. The rule gained a narrow, conjunctive
     exception (tooling AND a clean scan just before the copy), written down because reading an
     absolute rule as having an unwritten exception is how such rules die. ADR-0030 deleted it on
     2026-10-25: that set now sits under `_archive/`, a `record` path.
   - **The scan gates what DEV stores, not what a build session reads** (2026-09-24). It had stopped
     a build session reading the operator's own care note, though care sessions send the same
     classes to the model. Withdrawn: the read restriction only; flagged identifier lines are
     replaced by line number first. The first application of the admission test (ADR-0059).
   - **A build session may read CARE when the operator asks it to look into care sessions**
     (2026-10-02). The operator: "The effect is the same as pasting them, and we will save some
     effort in the future. The data is ours anyway." Withdrawn: the limit to a note the operator
     points at, and "never `patients/` or `_shared/`" (written with ADR-0053). Kept: the
     identifier's file and pointers, snapshots and tarballs stay unread, and nothing read returns
     except abstract prose the scan passes. The ban failed the admission test's question 2, stopping
     an agent at the operator's request from reading the operator's own data. How:
     `contributing/instances.md`.

9. **Only the private-mode identifier stays secret** (operator decision 2026-09-14; built
   2026-09-16). With the firewall gone, care sessions send personal names to the model in ordinary
   work, so hiding the whole registry protected almost nothing — except the private-mode identifier
   (ADR-0029), which sat inside the identity class and is what the overrun printed. Decided: (1) the
   identifier moves into its own owner-only file outside every repository, named by a second
   untracked pointer, `checks/PRIVATE-MODE-ID`; (2) the rest of the registry stops being secret from
   sessions, though it still lives outside every repository and is never committed, published or
   pasted into a tracked file; (3) the read-guard protects that file and its pointer. PR #9, a
   both-directions shell grammar, was closed as superseded.
   - A digest of the new file is never computed or recorded: a one-line file's hash can be
     brute-forced back to its content. Its readers: `checks/topics/relay-and-export.md`.
   - **Migration safety.** Until the installer has verified the split, the hook protects the
     registry exactly like the new file. The installer writes the protected paths into the hook's
     command line, the installer-owned identity PR #9's architect steelman recommended over run-time
     derivation. The registry is shared, so care must adopt the release carrying the new scanner
     before the split or in the same sitting, and run no relay scan between the two, or its older
     scan silently drops the identifier. The one-time by-hand recipe (kept here from 2026-10-11) is
     in the source revision.
   - **The guard, rebuilt small (operator, 2026-09-16).** Mid-build, two drafts denied legitimate,
     safe work. The operator: *fix the guard — guards must not sabotage legitimate and safe work —
     and keep them to a high-confidence minimum, grown only when a need shows up.* The rules are
     only what is near-certainly a read of a protected file or its pointer; metadata-only work runs,
     and digest tools are not metadata. An independent review fixed one blocker: a copy check that
     matched the identifier's pattern only as a regex.

10. **The session firewall retires; the record guards stay.** Retired after the records moved, not
    before: L9, L12 and L18, the FIRE bites, the registry checkpoint and its refresh script.
    `docs/PUBLISHING.md` and the hold's full ledger carry rationale a future flip needs, so they
    were kept in CARE, not deleted. The export script survives, slimmed, as the flip-time gate.
    Every guard and keystone rule about records was kept (neither L10 nor L13 reads the registry);
    since then L17 (ADR-0051), L3 and L16 have retired and L4 only warns (`checks/README.md`).

11. **One keystone, and adoption without an eval gate.** ADR-0049's baselines bound the keystone's
    bytes, so as decided *a tag is adoptable only with a recorded green under it*. **Superseded on
    2026-09-07** by ADR-0049 element 13: a full run was 58 Opus sessions, and an adopter who cannot
    afford it would be left with an unadoptable release rather than an informed one. A lineage
    record of the keystone bytes, with the run strongly recommended and LOUD, never red, replaced
    it, and was itself removed on 2026-10-04. A run after a load-bearing change stays recommended;
    nothing gates adoption on it.
    **The keystone split, deferred and consumed.** Care-mode bytes stable in the keystone and
    dev-mode text in a DEV-only file was deferred, to be revisited at more than one re-baseline a
    month. That fired (baselines under `a709fb9`, 2026-09-03, and `636bd85`, 2026-09-06), and
    `658ebc8` (2026-09-07) made `CLAUDE.md` the care contract and moved the building machinery to
    `CONTRIBUTING.md`; recorded here on 2026-09-08. Which contract a session reads is ADR-0053's
    decision, which also names the boundary between instance and session kind that L19 and L20 only
    half cover.

12. **Memory, registers and per-instance tooling.** Two Claude Code projects mean two auto-memories:
    DEV's never holds a handle, and care sessions stop carrying development entries. The PII-laden
    historical registers (`_inbox/`, `_archive/`, `cc-prompts/`) stayed with CARE; DEV started
    sanitized successors, whose lifecycle is ADR-0030's. The per-instance untracked inventory is
    made executable by an idempotent installer, `checks/install-instance.sh`: CARE gets `pre-push`
    alone, as a belt, since it never commits and three more hooks would double the installed-hook drift
    surface.

13. **The migration** (decided and executed 2026-09-06).
    - **Sequencing**, decided on acceptance: A1 first; A2 folded into Part B; a bounded marker mode,
      `migration:<YYYY-MM-DD>`, LOUD yellow instead of red until its date while Part B landed (point
      14); the current directory becomes DEV, CARE is a fresh clone, and the records move by rename
      on the same volume, so two live record trees never coexist; irreversible steps — the first
      push to the DEV remote, the records move — only on an explicit, step-specific operator go.
    - **History premise, corrected the same day:** the `.git` was the post-ADR-0017 clean
      replacement, 156 commits from `6dd2159` (2026-06-09) with no `patients/` path ever committed.
      Path-level cleanliness was verified, content-level was not, so DEV was seeded after a one-time
      gate: the export scan over the whole tree and every commit message. The draft's offline git
      archive in the offsite-mirror folder was struck: ADR-0045 sanctions exactly two roots as its
      single egress, and a git archive is neither.
    - **Records-move rules:** byte-preserving, then an ownership verify and a file count; an old
      tree's copy is quarantined read-only and destroyed after a verified restore (ADR-0017's
      precedent) or kept on offline encrypted media, never in a synced folder.
    - **Rounds 1–5** (evening): L19 and L20, executable eval containment, the relay scan, the
      installer and an instance-aware `pre-push` landed with an adversarial review's fixes, tagged
      `v0.50.0-migration-ready`. The eval gate surfaced two behavioural findings, closed in the
      keystone: a care session runs the guards and never reads them to orient, and a confirm tag
      rides the line where its fact is stated.
    - **Round 6** (late evening), on the operator's step-specific goes: CARE was cloned at
      `v0.50.0-migration-ready`; the record files moved by rename, counts equal and the ownership
      verify green; `main` was pushed to the private skeleton repository over its single export
      commit (kept locally as `refs/archive/skeleton-export-before-adr0050`). The operator read the
      fourteen commit messages the gate flagged, in their own terminal: nothing sensitive. The
      session firewall then retired; the retirement commit was amended before any push, so no
      pushed history carries the WP8 pair words. A relay scan over every tracked file found the hold
      file's ledger quoting class-maintenance specifics; it was abstracted, the full ledger kept in
      CARE. Tag `v0.51.0-firewall-retired` needed no re-run: the keystone bytes were unchanged.

14. **Migration mode, retired** (operator decision, 2026-10-24). Round 6 finished the split the day
    the mode was added. Reasons: no bite exercised its accept branch, so it was an untested way past
    L19 and L20's mismatch red; and the care contract still named it as a second place a build
    session could open, in a tree that may hold records (ADR-0053 point 3). L20
    now reds it as an unknown marker, and the installer and the snapshot script refuse it. The date
    helper stays for L19's break-glass window: a first cut removed it, and a break round caught
    every valid ticket turning red. Bitten on one fixture across board, push and installer.

15. **L20's record-shape scan reads the index too** (2026-10-25). Break rounds on the retirement
    found five layouts the scan missed; two reached a commit and the remote — a record-shaped path
    staged and then deleted from disk, and one staged under a nested `.claude/` or `node_modules/`.
    One change closes both, for the existing shapes only: in a development tree the index's paths
    join the scan, a hit only the index has counted with its name withheld. Guard admission: harm —
    record content pushed to the private remote; never the operator against themselves — it reads
    only paths; at the point of harm — the commit; net positive — one `git ls-files` per board run;
    smallest form — no new guard, hook or notice. Bitten per layout and per review fix (Opus,
    Codex).

16. **A snapshot from a shell that cannot see the operator's home** (operator decision,
    2026-10-25). The claude.ai chat runs commands in a Linux VM with only the care folder mounted;
    every snapshot was refused there, and its failed cleanup left partial copies. Now a named file
    whose folder does not exist is left out with a note and the records are copied; a file missing
    from a folder that exists is a loss and still refuses. The out-of-tree files change rarely in
    care work, and every snapshot on the Mac banks them. Guard admission: the harm, a lost registry,
    is kept at the loss case; the friction, every chat snapshot refused, is removed.

17. **Outside the main care folder, a care session answers and asks, read-only** (2026-10-25 to
    2026-10-29; owning text `CLAUDE.md` → *Sessions and people*).
    - **2026-10-25:** the board's refusal of a care worktree reaches only a session that runs the
      board, so a question-only session worked a whole conversation where nothing could be filed.
      Such a session was to say so first, after any emergency line, and do no care work; the
      main-folder session files its on-screen answers by session id. Admission: observed twice; one
      sentence. **Later that day** the rule covered the chat app too, after a chat care session
      could not take the snapshot and handed over only after a long exchange: any session outside
      Claude Code's main care folder hands over a ready prompt in its first reply.
    - **2026-10-27, the evidence:** in the care transcripts reviewed, 16 of 41 sessions opened in a
      worktree and about 13 were stranded (the client's new-session worktree switch was on, and the
      care preset set none). One medicine fact took about an hour and nine restarts to record; one
      stranded session refused to ask history questions; another answered a medicine question
      anyway, read the record from the main folder and sharpened its urgent advice. **Decided:**
      such a session works read-only from the main folder — it answers and asks, and copies no
      record out — and its reply to the first care request, after any emergency line or urgent
      warning, gives a one-sentence notice and a ready prompt carrying its session id. Every write
      is still held where it was: the board refuses a care worktree, and the client refuses a
      worktree session's edits to the main folder. "Copies no record out" answers the chat's one
      privacy failure, a record copied into its workspace. Opening originals stays allowed (the
      operator's choice after the break test: a smudged value must be checkable against its scan).
      The private-mode read guard does run in a care worktree, which reads its settings from the
      main checkout (probed 2026-10-27 on a synthetic clone). This widens ADR-0009's 2026-10-25
      "warning that cannot wait, kept brief" to a full answer, and **reverses the chat part of the
      operator's 2026-10-25 decision, for reading only** (operator, 2026-10-27, told that it reopens
      that decision). Break test: 24 adversarial cases, two blind judges per round; round two
      matched the intent on every case the rule decides. Admission: removes a refusal; adds no
      control.
    - **The stranded session cannot start the main-folder session itself.** Three starts on
      2026-10-27 opened in a worktree again; a probe on 2026-10-29 (desktop app 2.42304.0, the
      development tree) saw both starts open in the starting session's own worktree. So the ready
      prompt stays and the rule is unchanged.

### The steelman review behind the decision

One fresh-context reviewer, on 2026-09-06, returned *adopt-with-changes*. Five blockers, all
accepted: (1) the DEV identity scan needed a real-name list in DEV — the scan moved to CARE, every
class (point 8); (2) visibility-toggle publishing exposed unscanned history — a fresh export stays,
plus a migration-gate scan (points 4, 13); (3) ADR-0049's containment requirements were voided
silently — re-dispositioned (point 6); (4) no amends header — added; (5) a PII archive in the
offsite folder — struck (point 13). Thirteen should-fixes were folded in; the review's missed
alternatives became Part A and the rejected two-worktrees option. Later reviews and break tests:
points 7, 9 and 13 to 17.

### Other rulings and records

- Kept from the migration (2026-09-06): every builder's draft is treated as untrusted and reviewed
  before its gate.
- The 2026-10-11 drift sweep is folded in above.
- The residuals the operator accepted along the way, and their revisit triggers, are kept with the
  accepted risks, outside the tracked tree.

## Alternatives considered

- **Status quo, the firewall discipline** — rejected: a permanently load-bearing subsystem with five
  incident classes and an author-side trap; every future shipped-surface change pays again.
- **Part A alone** — adopted as Part A, rejected as the whole answer: the minimal fix for the
  trigger, done first, leaving every other cost in place.
- **A visibility flip as the publishing model** (the 2026-09-05 draft) — rejected (point 4): the
  export is a fresh single-commit copy so that an authoring accident never reaches the public.
- **Two branches in one repository** — rejected: PII enters git history the moment a care commit
  lands, and ADR-0017's point is that record-bearing history is never pushable.
- **One repository, two worktrees (CARE a worktree at a tag)** — rejected: a shared object store
  makes every commit reachable from both; a worktree cannot be pull-only; L19's tag anchor would be
  a local, spoofable ref; and the recorded shared-`.git` incidents (the `core.bare` flip, the
  ADR-0040 retirement races) are the class two worktrees invite.
- **A submodule or subtree** — rejected: a second git object model for no gain.
- **An encrypted vault inside one tree** — rejected: nothing against tracked-file authoring leaks,
  the class the firewall scans for, and a new key-loss failure mode.
- **A small identity scan in DEV** — rejected: an untracked real-name file in a development tree is
  the incident's own artifact (blocker 1). **A salted-hash belt** — rejected: still PII-derived
  material in DEV, and name inflection defeats whole-token hashing.
- The other rejected or superseded options are given with their reasons in points 6, 7, 9 and 11.

## Consequences

- **Simplification:** roughly 1,200–1,400 lines of firewall machinery retired; shipped-surface edits
  lose their token ceremonies; the care-utility-versus-genericize dilemma disappears, so CARE files
  can be as specific as care needs.
- **Gains:** `.github/workflows/skeleton-check.yml` stopped being inert, so the Linux leg of the
  two-substrate attestation (ADR-0020, ADR-0021) runs on DEV's changes instead of only at export; a
  second developer, or a shared memory file, became possible.
- **New discipline:** development only in DEV, care only in CARE, incidents relayed as scanned
  abstract prose. A bug that shows only on a real record is reproduced with a synthetic fixture in
  DEV, or handled under the CARE break-glass.
- **Lost signal, compensated:** guards are written where no corpus exists; bites prove the fail
  directions, and only the live corpus proves the pass directions. The release-acceptance session —
  board green, noise reviewed, rollback available — is the compensating control.
- **Two projects to keep oriented,** mostly a cost to the assistant; the memory split pays for it.
- **Risks and mitigations:** divergence (L19, loud; pull-only by rule); forgetting to pull (a CARE
  session-start line compares the adopted tag with DEV's latest); relay leaks (the CARE-side scan
  and the keystone's abstraction rule); a persisting red in CARE (the bounded break-glass); a
  mis-marked instance (the mode derived, not selected).
