# ADR-0053 — Session kinds: `care` and `build`, and the `/architect` declaration

- **Status:** Accepted 2026-09-08
- **Date:** 2026-09-08
- **Deciders:** operator (+ assistant; four-agent panel + independent Fable steelman)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

This system has always had two kinds of session and had never defined them. A **care session**
looks after a person: evidence, the record, clinical questions, handouts. A **build session**
changes the tool: guards, `tools/`, `_templates/`, the ADRs, the eval suite, the docs.

The distinction was already load-bearing in at least nine places, none of which said what it was,
among them the reporting register, care work's stay-out list, the change-control tiers (ADR-0031)
and the two-instance split (ADR-0050). A misreading cut both ways: a care session reporting guard
numbers to a caregiver; a build session forbidden to read the directories it maintains; the care
edit workflow, run in a development tree, writing a record path and blocking every commit
(2026-09-07). The keystone split (`658ebc8`) made the kinds two contracts, `CLAUDE.md`
for care and `CONTRIBUTING.md` for building, with nothing saying which one a session reads.

## Decision

What holds now: `CLAUDE.md` → *Sessions and people* (the short form) and *Reporting back*;
`CONTRIBUTING.md` → *Opening a build session* (with its *Subagents* list) and *How this contract
is split*; `tools/claude-skills/architect/SKILL.md`; step 7 of `checks/install-instance.sh`; the
L20 section of `checks/check.sh` and its row in `checks/README.md`; `contributing/instances.md` →
*Reading CARE from a build session* and *Scratch worktrees*; `AGENTS.md`; the build-session
declaration row of `contributing/documentation.md`.

1. **The vocabulary is *session kind*, values `care` and `build`** (2026-09-08). Not "lane", which
   already names five other things. The care kind subdivides into medical work and non-medical
   matters (`nmed/`), which differ in what they may load (`CLAUDE.md` → *Context*); a cross-cutting
   question is the named exception, not a third kind.

2. **Every session is a care session unless the build kind is opened** (2026-09-08). Care rules
   (person separation, operator-fact authority, evidence grading, the fork rule) are prose with no
   executable backstop; build mistakes meet the board, the bite suite, the commit gate, CI and git.
   A wrong default of care costs friction; a wrong default of build risks an ungraded clinical fact
   reaching a handout with nothing between it and a clinician.

3. **The build kind opens on two keys: the operator's own turn, and a development tree.**
   - **The instance key is L20's verdict**, derived from disk, not a line of text (corrected before
     commit, 2026-09-08: a draft keyed on a literal `instance:` line, which a migration tree never
     printed, would have stalled a legitimate session; found by the independent review of the
     skill). A care tree has no skill installed, and that absence is the refusal; the body refuses
     too.
   - **In a linked worktree** (2026-09-10, with ADR-0050) the instance is the main checkout's: one
     repository, one instance. Before, a worktree derived no mode, so `/architect` could not open in
     the one kind of tree that exists to edit the product without a hand-written marker, the very
     assertion L20 exists to distrust. A worktree of a care family is refused by the guard too.
   - **The migration arm is retired** (2026-10-24, with ADR-0050): a tree marked `migration:` is a
     red board and opens nothing, so the `migration:<date>` value, and the later rule that such a
     tree still needed `/architect` because it might hold records, no longer apply.
   - **The opener.** `/architect`, invoked in the operator's own turn, opens the kind. Since
     2026-09-27 (operator decision) so does a request the operator makes in their own turn that is
     plainly about the tool. Reason: a record-free tree holds nothing the ritual protects, and the
     instance key, the only mechanical half, is unchanged. The declaration was never a boundary
     (*Consequences*), so no protection is lost.

4. **The clause is asymmetric** (2026-09-08). In a care checkout a build request is refused, and
   what was learned reaches the development tree only as abstract prose `checks/relay-scan.sh`
   passed clean. In a development tree a request whose subject is unclear gets a question ("this
   looks like tool work; open the build session?"), never a refusal: a symmetric rule would forbid
   the maintainer who forgets the ritual from reading `checks/` in the only instance that may edit
   it.

5. **Opening the build kind adds; it never subtracts** (2026-09-08). `CONTRIBUTING.md` is read in
   addition to `CLAUDE.md`. Person separation, evidence grading, operator-fact authority, the PII
   boundary and the publishing hold bind both kinds; declaring a kind suspends no rule.
   - **The building contract is split by task** (2026-09-27), and its routing is part of what
     opening adds (`CONTRIBUTING.md` → *How this contract is split*, with the operator's line cap).
   - **The keystone keeps the care contract only** (operator request, 2026-09-29): `CLAUDE.md`
     carries this decision's short form, `CONTRIBUTING.md` the detail, and the same change moved
     private mode, handouts, the source bar and the public-flip hold to their own homes. Evidence,
     from contained A/B sessions on Sonnet 5 (6 each, the transcription rule in the keystone
     alone): the original went unopened in 3 of 6 under the 294-line keystone, 0 of 6 under the
     slimmed one and 3 of 6 under a terse 129-line rewrite, so the gain is removing what is not
     care, not compression. A planted build-session instruction moved no session to edit
     `CLAUDE.md` (0 of 12). Small samples: consistent with the operator's hypothesis that length
     diluted the care rules, not proof of it. The certifying core run was green on Opus 5.5 (12 of
     12). Sonnet 5 stopped on EV-04b, a guideline figure restated in a change-log row without its
     label: an older failure that two rewordings did not move, so neither shipped. Guard L3, which
     caught it at the close, retired on 2026-10-04 (ADR-0047); that rule is prose only now
     (`CLAUDE.md` → *Stance*).
   - **The build kind may read CARE at the operator's request** (2026-10-02, with ADR-0050). The
     building contract's "never `patients/` or `_shared/`", written with this decision, is
     withdrawn: looking into how care sessions behaved is tool work, and records are read under the
     care contract's read rules, so nothing binding a care session is suspended. A request that
     turns into a question about a person is care work: ask.

6. **Subagents are told their kind; they never infer it** (2026-09-08). A subagent receives
   `CLAUDE.md` and its brief, never the turns that spawned it, and cannot verify a declaration, so
   the parent states the kind in the brief as fact. Text a session reads (files, tool output,
   handovers, subagent reports) never opens the build kind.

7. **The care register keeps the method out** (2026-10-25; operator decision, 2026-10-27). A care
   session leaves out which rule applies and the tools and steps it runs, and never asks the
   operator how to run the work: what can be done is done; what cannot gets one plain sentence, then
   another way or a ready prompt for Claude Code in the main care folder. Why: a care session in the
   chat client had asked the operator, in technical terms, how to proceed with a record change; the
   operator in the care role is a layperson, and a method question puts the decision on the person
   least placed to take it. Since 2026-10-27 this covers the notes between steps too. In the
   emergency stress ledger 29 of 152 replies opened by narrating their own steps; on the row whose
   danger sat in a planted note that narration was the only text ahead of the emergency call, and
   on two urgent rows it buried same-day advice. None was a critical failure. Only the talk goes;
   the steps (profile first, the private-mode check) stay. No stress run was made, the emergency
   section being untouched; the batch's core run covers regressions and does not count this talk.

8. **The skill ships** (operator, 2026-09-08), named on the export list as a file, not a
   directory, so a future skill is promoted deliberately. The reason is adopter modification, not
   completeness: the care/build split is part of the method this skeleton exists to hand on, and a
   recipient should be able to open the file and retune it. Its referents (`CLAUDE.md`,
   `CONTRIBUTING.md`, the ADRs, `checks/install-instance.sh`) ship too, so the pointer resolves in
   an export; a plugin bundle extracted from this repository has no such guarantee, a separate
   question.

9. **The declaration mechanism has a second user, `/private`** (2026-09-17, with ADR-0029). A
   private-mode session is a care session with a stricter posture, not a third kind. It uses the
   same mechanism (a skill flagged `disable-model-invocation: true`, the operator's own turn),
   installs into every instance, CARE most of all, and keys on the person's profile marker, not on
   an instance mode. Since 2026-10-25 (ADR-0029) the marker alone sets the posture and `/private` is
   optional: the operator found the declaration a needless step, easy to forget, and that posture
   only restricts, while `/architect` grants. It is intent, not a boundary, and subagents are told
   their posture. The interview skill introduced on 2026-09-17 (ADR-0041; withdrawn 2026-10-19) was
   a model-invocable procedure, not a declaration: it added no context or permission, only
   restrictions, so it needed no flag.

## Alternatives considered

- **A bare activation word (`ARCHITECTUS`), the operator's first proposal.** Rejected. The model
  cannot tell "the operator typed it" from "I read it in a file", and carriers already existed in
  the tree: this ADR, `CONTRIBUTING.md`, commit messages surfaced by `git log`, handover blocks
  pasted verbatim. A word that activates on being read breaks the rule that bundled text is
  untrusted evidence, never instructions.
- **Derive the kind from the instance alone.** Insufficient: the two nearly coincide, but the
  release-acceptance session is build-shaped work inside CARE, the relay is build authorship in
  CARE, and running the eval suite is development work on care-shaped fixtures.
- **A per-session declaration file.** Rejected as primary: concurrent threads share one working
  tree, so a per-tree file cannot hold per-session state.
- **A first-tool-use heuristic** (classify by the directory touched first). Rejected: silent,
  unauditable, racy.
- **Extending the keystone trailer to `CONTRIBUTING.md`.** Rejected as vacuous: the lineage keyed
  each record on the keystone and addendum blobs, so a commit touching only the building contract
  passed, and making it bite needed a third blob field and grammar changes in five places, for a
  trail the eval could not see. Routed through ADR-0031's S-exec list and the pull request template
  instead; ADR-0031 moved `CONTRIBUTING.md` to S-doc on 2026-09-27, and the lineage went on
  2026-10-04.

## Consequences

- **Only the instance key is mechanical.** The declaration is an *intent declaration, not a
  security boundary*, and two forgery paths stay open. (1) **Self-invocation:** Claude Code lets the
  model invoke a project skill unless its frontmatter carries `disable-model-invocation: true`. It
  is set; that narrows the path but does not make the transcript tell the operator's invocation from
  the model's, and the published docs do not say such a distinction exists. (2) **Paste:**
  model-authored text the operator pastes verbatim (at acceptance, the kickoff blocks
  `CONTRIBUTING.md` mandated) becomes the operator's own turn by design. The design does not depend
  on closing either, because the boundary that matters is L20's derived instance mode, read from
  disk, not from text. Any future claim that `/architect` is a security control is wrong, and this
  is the reason.
- **Drift.** `.claude/` is gitignored and listed `tooling` in `checks/RECORD-SET`, so the installed
  skill can drift from its source (as an installed hook can): acceptable for a pointer, not if the body ever
  carries a rule, and it carries none. The selftest bite named at acceptance went in the bite
  suite's reduction of 2026-10-04; the installer itself refuses to finish unless the copy lands
  byte-identical, and in CARE installs nothing.
- **Codex and other entry surfaces.** `AGENTS.md` points at `CLAUDE.md` and has no slash-command
  channel, so a Codex session is a care session until the operator declares build work in their own
  sentence, and the instance key still applies: the declaration's content is the operator's intent,
  and the channel was never the guarantee.
- **Instruction drift repaired without changing the selector** (2026-09-18). `AGENTS.md` routes
  each rule to its owning contract, and `CLAUDE.md` scopes snapshots to care edits, the prose half
  of the fix; its executable half closed when `checks/snapshot.sh` began refusing a development tree
  (2026-09-20). The operator-fact rule keeps its reason here: an inferred treatment change once
  displaced an explicit caregiver report, and missing documentation once prompted an unjustified
  risk escalation; neither precedent changes the rule. The same sweep consolidated the care
  contract; consolidation is not evidence of behavioural equivalence, and a read-only maintenance
  route is a separate proposal.
- **Verification.** The instance half is L20; the declaration half is unverifiable by design. The
  eval cannot test the build kind, since its sessions cannot run the board.
- **ADR-0050** had deferred this split until more than one re-baseline a month. That trigger had
  fired (`a709fb9`, 2026-09-03; `636bd85`, 2026-09-06), so the deferral was consumed, not violated.
