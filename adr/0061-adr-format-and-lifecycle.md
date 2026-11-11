# ADR-0061 — ADR format and lifecycle: short decision records, superseded rather than amended

- **Status:** Accepted 2026-11-01 (operator)
- **Date:** 2026-11-01
- **Deciders:** operator (+ assistant)

## Context

The numbered ADRs held 127,648 words at `4a419ec` (2026-10-11), 100,793 after that day's trim
(`b3a1026`) and 129,526 at `8874f85` (2026-10-31). Almost all the growth is in-file amendments:
amendments make up 81% of ADR-0049 (its *Run history* aside) and 91% of ADR-0029.
The convention in `adr/README.md` is to correct a decision by dated amendment and never rewrite it,
so every change appends. The current decision can only be found by replaying amendments, and the
Status lines lag behind reversals.

Most of those amendments record operating detail, not decisions: which cases are in a suite, grader
fixes, run results, review rounds and build steps. What holds now is already in an owning doc
(`evals/README.md`, `checks/README.md`, the tool READMEs, the topic docs), so the same fact has two
homes and drifts. `contributing/documentation.md` already says an ADR is for a choice that is hard
to reverse.

The published guidance mostly runs the other way. Nygard (2011) recommends a short record of one
decision, one or two pages long, and when the decision changes, a new record with the old one kept
and marked superseded. AWS treats an accepted ADR as immutable apart from lifecycle updates. One
widely used guide (joelparkerhenderson, *architecture-decision-record*) reports that dated in-place
edits worked better for its authors' teams, which is the shape this repository took. Git keeps
every version of every file, and the pull request keeps the reasoning for each change. The public
release is a fresh one-commit export, so its readers get the ADR text without the history.

## Decision

1. **One decision per ADR, kept short.** It has Context, Decision, Alternatives considered and
   Consequences, including costs, constraints and the dated operator rulings it rests on.
2. **Accepted substance is fixed.** A changed decision gets a new ADR that names what it
   supersedes. In-place edits are limited to lifecycle updates, non-substantive corrections (links,
   typos, pointers) and the migration in point 6.
3. **Operating detail is not ADR material.** What holds now lives in the doc that owns it. How it
   got there lives in git and the pull request. A reversible change needs no ADR.
4. **The Status line carries the lifecycle only:** Proposed, Accepted, Rejected, Deprecated, or
   Superseded (in part) by ADR-NNNN, each with its date. It holds no run results, counts or
   narrative.
5. **The index in `adr/README.md` shows each supersession**, so a chain can be followed from
   either end.
6. **Migration applies once to each ADR present when this proposal is accepted**, one ADR per pull
   request, largest first; ADRs with no substantive amendment may share one pull request:
   - operating detail is first moved to, or confirmed in, its owning doc;
   - only decisions already recorded before acceptance are consolidated, keeping their dates,
     alternatives, constraints and the reasons for any reversal;
   - the commit names the source revision, and the ADR carries a permanent
     `Migrated under ADR-0061: YYYY-MM-DD` line, so it cannot use the exception twice;
   - dated amendment citations, heading links, code comments and runtime messages that point into
     it are re-pointed.

   A new decision after acceptance always takes point 2. Existing ADR numbers stay addressable,
   including records that fall below today's threshold for an ADR. A rejected, deprecated or
   superseded record keeps its alternatives, constraints and the dated reason for its disposition.
   A partial supersession names the replaced scope in the old ADR and the replacement in the new
   one; the rest of the old ADR stays accepted.

## Operator rulings

- **a. Supersede, or edit in place?** Decided (operator, 2026-11-01): supersede (point 2). An
  accepted record stays readable as decided, and the regrowth stops at the file.
- **b. A one-line change list in each ADR (date, what, commit)?** Decided (operator, 2026-11-01):
  no. `git log -p adr/NNNN-*.md` holds it, and the public copy keeps the superseded ADRs themselves.
- **c. Where is the latest eval run recorded?** Decided (operator, 2026-11-01): a *Latest passing
  run* line in `evals/README.md`, with the build-session model check in `CONTRIBUTING.md` reading
  it there. ADR-0049's Status line loses it.
- **d. Migrate in place (point 6), or supersede each bloated ADR with a fresh consolidated one?**
  Decided (operator, 2026-11-01): in place. Superseding would keep the full old text in the tree next
  to the new text.

## Alternatives considered

- **Keep in-file amendments, under a rule that they stay brief** (draft of 2026-10-31). This slows
  the regrowth but does not stop it, and the current state still has to be replayed.
- **Living ADRs rewritten to the current state, with history in git.** That gives one place to read.
  But an ADR then becomes a second copy of the owning doc, and without git a reader loses the
  decision as it was made, along with what was rejected and why.
- **A change list in each ADR.** History in prose would grow more slowly, but it would still need
  upkeep (rejected by the operator, 2026-11-01).

## Consequences

- ADRs shrink to decision records the operator can read in one sitting, and each owning doc becomes
  the single home for what holds now.
- ADR files multiply over time, and supersession chains appear. A partial supersession needs a
  clear pointer in both files and in the index.
- About 130 lines outside `adr/` cite a dated amendment, and the migration re-points them.
- On acceptance, the same change reconciles `adr/README.md`, `adr/_template.md` and every ADR
  ownership and amendment rule in `contributing/documentation.md`. It gives the dated evidence and
  findings that leave ADRs an explicit durable home. It also moves the eval snapshot to
  `evals/README.md` and updates the model check in `CONTRIBUTING.md`.
- No guard or check is added; reading and review keep the format.

Sources: M. Nygard, "Documenting Architecture Decisions" (2011),
https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions; AWS Prescriptive
Guidance, "ADR process",
https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html;
J. P. Henderson, https://github.com/joelparkerhenderson/architecture-decision-record (all read
2026-11-01).
