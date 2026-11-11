# ADR-0005 — Evidence grades A–D, ⟨confirm⟩ and operator facts

- **Status:** Accepted by 2026-06-07
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded for point 1; the operator for points 2–5
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

An operator-stated medication status was once wrongly overridden by inference: inference must not
overrule the operator or a higher-grade source. Until 2026-10-02 a report against a scanned
document was forked, never settled. In the care session that raised it, most apparent A-against-B
conflicts were two facts (a prescriber's card against what is taken; an old document against a
later reported change), and absence claims were written three times while the sources held the
values.

## Decision

What holds now: `CLAUDE.md` (*Keeping the record honest*, *Conventions*), the legend of
`_templates/medications.md`, `_templates/HANDOUT-RULES.md` (*Fact-check gate*),
`_templates/handout-verifier-prompt.md` (*Conflicting sources*) and `evals/README.md`.

1. **Evidence grades A–D and `⟨confirm⟩`; the operator's facts are authoritative.** Never
   self-correct an operator fact by inference; fork, don't override (narrowed by point 2).

2. **A higher grade corrects a lower one on the same fact** (operator, 2026-10-02): "Since you have
   indeed found conclusive evidence there are grade A records disconfirming grade B evidence, you
   should always correct the record with grade A evidence."
   - Only where both speak to the same fact at the same time and the original is its authoritative
     record (a measured value, a printed prescription line, a coded diagnosis, a test result). A
     handwritten note on a stamped document is grade A for what is written, not for who decided it.
   - It corrects, never silently erases: both values and sources are logged, and the operator is
     told in one plain sentence, asked when it is found or told at the end if away. Point 1 still
     forbids correcting an operator fact on the session's own inference.
   - **Original first, report beside** (operator, 2026-10-27). The outranked value first went to
     the change log as superseded; a review (Codex, care transcripts, eval history) found that this
     can retire a safety fact: a discharge letter's "no known allergies" would hide a reported
     severe reaction. The original's value is stated as the fact; a conflicting report stays beside
     it, marked, until the operator settles it. An inference is corrected.
   - In a handout, the outranked value stated as fact is `contradicted`, and a settled
     care-material fact shown as an open fork is a must-fix, repaired in record and handout before
     sealing (advisory where it cannot mislead care); point 3's cases are exempt.

3. **Two facts are not a conflict** (2026-10-02): prescribed against taken (keep both), and an
   older document against a later reported change (date both). **Dose rows** (operator, 2026-10-31,
   after a blind judge review): one row per dose, `prescribed` or `taken`, with its own From, To and
   source; a change ends its row and adds one of the same kind; the Adherence column goes. The cue
   sits in the list's legend, so a record on the older layout keeps it until the operator converts
   it; `CLAUDE.md` is unchanged.

4. **Search the sources before an absence claim** (2026-10-02, operator-approved): before "none on
   file", "never measured" or "unknown" about a measurable fact, search the person's `med/sources/`
   text layers and open any hit's original; in private mode only the approved masked copy, so the
   rule never invites opening an unmasked scan. A real gap stays a question.

5. **Ask, don't guess** (operator, 2026-10-31, from the blind review of the judge's flags).
   - An unexplained medical term, notation or medicine name the session cannot identify for
     certain stays as written and is asked about, never glossed or read as a misspelling. Eight
     replies or records called the synthetic code LAB-KFN a "kidney" test (ruled practice); the
     operator widened the cue from test names.
   - Details that could change urgency (after a fall: how, whether the head was struck) are asked
     on screen now, not left to confirm: all three EV-06a trials deferred them, which the operator
     called a non-obvious path to harm by negligence.

## Alternatives considered

- **Fork every report-against-original conflict** (until 2026-10-02): nothing settled the fact.
- **Apply point 2 to every A-against-B pair** (2026-10-02): most were two facts.
- **Move the outranked report to the change log** (2026-10-02 to 2026-10-27, reversed): it can
  retire a safety fact. **Holding both open as equals** ("not yet clear which") stays wrong.
- **A board check for dose rows** (not built, guard admission) and **a new eval case for point 5**
  (operator: none; the code is already in most trees), both 2026-10-31.

## Consequences

- An original settles its fact while a conflicting report stays visible; inference never overrides
  an operator fact. A gap is written only after a search.
- The drift sweep (2026-10-11) and the interview skill's retirement as a carrier (2026-10-19,
  ADR-0041) changed nothing decided.
