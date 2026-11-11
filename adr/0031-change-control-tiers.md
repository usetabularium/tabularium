# ADR-0031 — Change-control tiers: structural edits get an independent red-team pass; PR/CI rejected for the working repo; CI accepted for the published skeleton

- **Status:** Accepted 2026-07-05; PR/CI rejection reversed for DEV 2026-09-06 (CI) and 2026-09-07
  (pull requests); `Red-team:` trailer retired 2026-10-24
- **Date:** 2026-07-05
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The repository's incidents (truncation, literature-value confusion, wrong-paper citation, a
false-green guard) were caught or prevented by executable guards, never by review ceremony. So the
leverage is guard coverage plus independent review of the guards themselves, not imported
pull-request process: a defective guard edit is the one change class that can silently remove the
net while looking green.

## Decision

What holds now: `CONTRIBUTING.md` (*Threat model*, *Its workflow*, *How a change lands*) and
`CLAUDE.md` → *Safeguards*. The lanes in point 4 are defined only here.

1. **Two change-control tiers** (2026-07-05).
   - **Tier-S (structural):** an edit under `checks/**`, `_templates/**`, `tools/**`, `CLAUDE.md`,
     `.gitignore`, or guard-running or reporting automation under `.github/**` (a reporter that lies
     about guard state removes the net as surely as a broken guard). As decided, it took an
     independent subagent red-team review before commit ("find how this change breaks a guard,
     opens a fail-open path, or contradicts an ADR"), recorded in a `Red-team:` commit trailer
     (retired, point 7).
   - **Tier-C (care content):** patient docs, analyses, handouts, the reference library. The
     existing gates are the control, with no added branch or pull-request ceremony, because daily
     care work is where friction would hurt. Its edit order, first tied to the power-loss durability limit, is the standing
     care workflow (recorded 2026-10-11).

2. **No daemon: no reliance on local scheduled execution** (operator, 2026-07-05). The daily launchd
   check shipped with this ADR (`tools/scheduled-check/`) was removed, never installed, and
   Tier-S's automation clause shrank to `.github/**`. Integrity rests on gates that fire at the
   guarded action (the ADR-0022 hooks, the pre-push block) and the every-session board. A timer
   depends on the machine being awake, the agent loaded and a notification seen: a weaker class than
   a git hook. The gap it targeted, a red tree left uncommitted between sessions, is accepted: the
   next board or commit catches it. The skeleton CI, on GitHub, is unaffected.

3. **Pull requests and cloud CI rejected for the working repository; CI accepted for the published
   skeleton** (2026-07-05). Grounds: (a) the ADR-0017 no-remote posture: pull requests need a
   remote, and cloud runners would receive the PII tree, a hard privacy violation, not mere
   friction; (b) a single operator's self-review is ceremony without independent scrutiny; (c) the
   ADR-0022 pre-commit gate is the local equivalent of CI (guards block a red commit, selftest
   bite-tests staged guard edits, and bypass is two-factor and audited). CI is accepted for the
   PII-free published skeleton only: a GitHub Actions workflow running `check.sh` and `selftest.sh`
   on every push, shipped with the export and inert in the working repository, which had no remote.
   - Ground (c) stood when the bite suite left the pre-commit hook (2026-09-08): the gate still
     blocks a red commit.
   - **Reversed for DEV** (CI 2026-09-06, pull requests 2026-09-07). The rejection rested on one
     premise, that runners would receive the PII tree; ADR-0050 removed it, since DEV never holds a
     record, a handle, a real date or a token list. It stands for a record-bearing tree (CARE has no
     CI). Since 2026-09-07 every DEV change lands through a pull request and CI. CI sits underneath
     the review lanes, never instead of them: it cannot discharge a reading of the diff. It fires on
     a push, not a timer (point 2).

4. **Tier-S review laned by diff class** (operator-ratified, 2026-07-26). One full red-team lane for
   every Tier-S edit was replaced because the yield split by what the diff touches: every review of
   executable surface found at least one must-fix, while prose-only reviews recorded passes or
   advisory notes. A mixed diff takes the highest lane it touches.
   - **S-exec:** any non-`.md` file, or a gating `.md` whose text drives enforcement or model
     behaviour: `CLAUDE.md`, `tools/claude-skills/architect/SKILL.md`,
     `_templates/handout-factcheck-verifier.md`, `_templates/HANDOUT-RULES.md` (its fact-check gate
     section), `_templates/HANDOUT-SOP.md`, and since 2026-10-11
     `_templates/handout-verifier-prompt.md`, the verifier's standing prompt moved out of its brief
     (ADR-0034). Extend the list the moment a new `.md` starts gating behaviour: under-inclusion is
     the known failure mode. Full adversarial review, scaled by blast radius: a bounded diff (about
     300 changed executable lines or fewer; no new guard, writer or protocol) gets one focused
     fresh-context adversary told to construct and run the attacks; a new guard, ledger writer,
     protocol or firewall change gets a panel and rounds. A review with dead agents or no executed
     attacks does not count; rerun it.
   - **S-doc:** a `.md`-only diff under Tier-S paths, ADR bodies, READMEs and register prose, and
     since 2026-09-27 the files in point 6. One fresh-context, single-round reviewer (Sonnet-class
     acceptable), asked: "does this contradict a guard/ADR or misstate enforced behavior?"
   - **S-mech:** register or status flips, change-log lines, next-free-number bumps, few-line typo
     fixes with no semantic change. No review; the ADR-0022 gate is the control. Self-declared;
     the operator may spot-audit it. Any doubt → S-doc.

   Until 2026-10-24 every lane carried the trailer, S-mech as `Red-team: exempt (S-mech: <what>)`.

5. **Every red-team brief states the threat model** (operator, 2026-09-10). Two adversarial rounds
   on ADR-0050's worktree change found six real structural findings, worth every token, and many
   constructed filesystem shapes whose chasing added code and bites the redesign then deleted. The
   operator: this is a single-operator Claude plugin, and the class to review for is the honest
   slip (a config bit flipped by accident, a marker hand-written in the wrong tree, two copies of
   one rule drifting), not an adversary with a shell in the repository. An S-exec brief names that
   threat model in as many words and puts adversarial filesystem constructions out of scope unless
   the change exists to withstand them; the attacks are still constructed and run. Corollary:
   **DEV is not taxed at CARE's rate.** A check that protects records earns its friction; in DEV,
   where a wrong answer costs a rerun, the same friction does not.

6. **The build contract and the audience handout templates take S-doc** (operator, 2026-09-27): a
   diff confined to `CONTRIBUTING.md`, `contributing/*.md`, `_templates/handout-patient.md`,
   `_templates/handout-clinician.md` or their language siblings (`.en`; `.pl` since ADR-0008,
   2026-10-27). Why: full attack reviews of them yielded little; none reaches a patient before the
   per-handout fact-check (ADR-0034; locked at the seal since guard L11 retired the same day); and
   build-contract slips still meet the board, the bite suite and CI. The three files that define or
   sequence that fact-check stay S-exec, because this reason rests on them. Residual: a
   build-contract rule no guard enforces rests on that one reviewer.
   - **The templates' `factcheck: required` lint is dropped** (operator, 2026-10-11, after a break
     test: 13 seal attempts without a fresh PASS were all refused). Nothing reads the line; the
     seal gate, which is bitten, refuses any seal without a fresh PASS either way, so this point's
     premise holds. A pull request that makes any tool read handout front matter to decide
     fact-check scope restores the lint from `0e2cb69^:checks/selftest.sh` (§35e) in the same pull
     request.

7. **The pull request review is the review of record; the `Red-team:` trailer is retired**
   (operator, 2026-10-24: "It's an artifact of a gone era. Yes, PR review is the record"). Since
   2026-09-07 every change lands through a pull request, where the posted review stays beside the
   diff. The trailer never became that record: 91 of 114 non-merge commits since 2026-10-01 touching
   `checks/`, `tools/`, `_templates/` or `CLAUDE.md` lacked it, and nothing enforced it. The tiers
   and lanes stay as guidance on how hard to review, with point 5 for every brief. For a key
   structural change (the S-exec lane) the session recommends a fresh-context review before
   `gh pr create` and asks the operator, who may skip it; S-doc and S-mech get no pre-PR step.
   `git log --grep='Red-team:'` stays the ledger up to 2026-10-24. Admission (guard-admission
   skill): (1) harm: an executable change that breaks a guard or opens a fail-open path while the
   board stays green; every S-exec review in the 2026-07-26 sample found a must-fix. (2) A
   question, never a block. (3) At the landing step, before the pull request. (4) One question per
   S-exec pull request, replacing a mandatory trailer on every Tier-S commit: less friction.
   (5) One line in `CONTRIBUTING.md` and one in the pull request template; no hook, no check.

## Alternatives considered

- **Pull requests and cloud CI for a record-bearing tree** (rejected 2026-07-05, point 3).
- **A launchd daily check** (rejected by the operator, 2026-07-05, point 2).
- **A `commit-msg` hook requiring the trailer on staged Tier-S paths:** deferred 2026-07-05 until
  the boundary was exercised (prose first, enforcement second, as ADR-0021 → ADR-0022); dropped
  with the trailer, 2026-10-24.
- **One full red-team lane for every Tier-S edit** (replaced 2026-07-26, point 4), and for the build
  contract and templates (replaced 2026-09-27, point 6).
- **Chasing adversarial filesystem constructions** (out of scope since 2026-09-10, point 5).

## Consequences

- Scrutiny concentrates on the change class that can remove the net while looking green; care work
  carries no added ceremony.
- Review depth is guidance, not enforcement: the lane is self-declared and the S-exec review can be
  skipped (point 7).
