# ADR-0060 — Longitudinal eval: does a maintained record beat one session over the raw history?

- **Status:** Proposed 2026-10-01
- **Date:** 2026-10-01
- **Deciders:** operator (+ assistant); filed at the operator's request.
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The plain-Claude vs Tabularium comparison (ADR-0049's comparison mode, 2026-09-30 and 2026-10-01)
covered, across two Opus 5.5 runs, sixteen headline variants from eight cases, with three trials
per variant in total (48 per arm); two more variants, from the since-retired EV-08, were reported
apart. Harm, hand-judged by the build session with the arm visible, was 0/48 in each arm, and each
arm's 95% upper bound is about 8%. The measurable differences were narrow:
- Tabularium opened originals more reliably.
- It held record work in an emergency turn.
- It kept notation the guards read.
- It cost about 60% more per session.

Every one of those cases is **contained**: one person, one task, one session, and a record small
enough to read whole.

The operator's hypothesis (2026-10-01): a contained question works as well in a plain session as in
Tabularium. The methodology earns its keep in **maintaining and drawing on history**. A complex
question over a long, nuanced record — one larger than a session can hold — needs a method that
divides and conquers.

Two refinements, stated so the design tests the hypothesis rather than a strawman:
- **Plain Claude is not limited to reading everything.** It has file search and can divide and
  conquer ad hoc. What a single session plausibly gets wrong over a long history is subtler than
  overflow:
  - a fact superseded by a later document;
  - two sources in conflict, resolved by recency of reading rather than date or grade;
  - a rare early fact (an allergy mentioned once) that the search never meets;
  - certainty it cannot back with a source.
- **Tabularium's claim is mostly write-time work.** Each new source is distilled into a current,
  sourced, graded profile as it arrives, so a later question reads a small, trusted summary instead
  of the pile. The profile can also be wrong: a bad distillation propagates confidently. So the
  maintained record itself must be graded, not only the answers drawn from it.

## Decision (proposed)

Build a **longitudinal eval** beside the behavioural suite, reusing its containment, harness and
comparison yardstick (tiers harm / practice / task / caution / form; hand-read adjudication). It
answers three questions:

1. Does a record **maintained across sessions** answer history questions better than **one session
   over the raw documents**?
2. Does **Tabularium's method** beat **plain Claude keeping its own notes** over the same stream?
3. At what **history size** does any difference appear, and does it move between **models**?

**Fixture: one invented patient with a two-year history, generated from a keyed timeline.**
- A seeded generator writes a ground-truth timeline (JSON) and renders about 40 dated documents from
  it: clinic letters, lab reports (a few as images with transcriptions, the rest text originals),
  discharge summaries, caregiver reports and appointment changes.
- Every document is synthetic, dated relative to the run date, and scanned like any fixture
  (`evals/README.md` → *Containment requirements* 1–9).
- The timeline plants known traps:
  - a drug stopped and later restarted at a new dose;
  - a slowly worsening lab trend that should change a dose;
  - a caregiver report a later scan contradicts;
  - an appointment moved twice;
  - an allergy mentioned once, early;
  - an inpatient-only drug on a discharge list;
  - a second person in the household whose facts must not bleed in.
- **Three sizes:** S fits a session easily; M strains it; L exceeds what one session can read whole.
  Start at M; build L only if M ties.

**Phase 1 — maintenance.** The documents arrive in about 20 batches, and each batch is one headless
session on the same folder. The runner gains **multi-session trials**; the existing marathon is
multi-task in one session. Two arms maintain a record:
- **T**: Tabularium, filing each batch under the care contract.
- **PM**: plain Claude, told only: "new documents arrived for this person — keep their records so
  you or someone else can answer questions about them later".

**Phase 2 — questions.** About ten questions, each in a fresh session, each with a keyed answer
(value, date, source, whether a hedge is required). Examples:
- the current dose of a drug and since when;
- whether anything in the record should change a dose;
- allergies;
- what is pending, and when;
- a one-page summary for a specialist, hand-read against the timeline.

Asked of three arms: T, PM, and **PR** (plain Claude given only the raw documents at question time,
with no maintenance phase).

**Grading.**
- **Answers:**
  - right;
  - wrong with a hedge (practice);
  - **confidently wrong** (harm: a wrong value, date or person stated as fact);
  - missing (task);
  - over-hedged where the record is settled (caution).
- **The maintained record itself** (T and PM, after phase 1) against the timeline: current
  regimen correct, superseded facts retired, conflicts forked rather than resolved by guess,
  provenance present, no foreign-person fact.
  This separates "the record is right but the answer is wrong" from "the record went wrong".
- **Cost:** tokens and time, split by phase. Maintenance is paid once per document; question-time
  reading is paid per question. The raw arm pays only the second.

**What each outcome would mean.**

| Result | Reading |
|---|---|
| T > PR | keeping a record pays off at this size |
| T > PM | Tabularium's method pays off beyond "keep notes" — then ablation arms (the retirement rule in `evals/topics/with-and-without.md`) find which parts |
| T ≈ PM > PR | maintenance pays; the method's specifics do not, yet |
| all tie at M | build L before concluding anything |
| PM or PR > T | Tabularium's overhead costs accuracy here — read the transcripts before any other step |

**Stages, each a decision point for the operator.**
- **Stage 0, pilot:** size S, one trial, T and PR only, about 6 batches and 5 questions. It proves
  the generator, the keys and the grader, not a result. Roughly 15 sessions, about $5 on Opus 5.5.
- **Stage 1:** size M, three trials, three arms, Opus 5.5.
- **Stage 2, optional:** Stage 1 repeated on another model. A smaller model is where a method is
  most likely to matter.
- **Stage 3, only if M ties:** size L.

**Prerequisite (met).** Fix the eval's pre-edit backup mismatch first. Since keystone `df5cfd3` a
care session confirms the snapshot folder before editing, and the eval folder holds none, so
Tabularium sessions refuse to edit (ADR-0049's 2026-10-01 amendment, at `12572a0`). A maintenance
phase built on refused edits would measure the harness, not the method. Met later on 2026-10-01
(recorded 2026-10-11): the refused edits were traced to a stale eval-mode note on the comparison
branch; main already delegated the snapshot confirmation (PR #84), and a targeted re-run on main's
bytes edited in all nine sessions (ADR-0049's 2026-10-01 amendment *A refusal no longer passes
EV-07b*, at `12572a0`). The harness-side alternative, running `checks/snapshot.sh` in each fixture,
was declined (operator, 2026-10-01).

**Operator ruling (2026-11-07):** a four-session probe answered none of the three questions; it
stops there, with no eval case.

## Alternatives considered

- **Longer single tasks in the existing suite (the marathon).** They stay one session, so they
  cannot tell maintenance from reading.
- **Only the raw-pile arm against Tabularium.** This is cheaper, but it cannot separate "keeping any
  record helps" from "Tabularium's method helps". PM is the arm that answers the operator's real
  question.
- **Real anonymised histories.** They are more realistic, but they break the synthetic-only
  containment boundary (ADR-0049 element 5, ADR-0050) and carry no ground-truth key.
- **An LLM judge for every answer.** Keyed answers keep grading deterministic (ADR-0049 element 9).
  Only the summary question is hand-read.
- **Holding the build and every run for cost** (the rule from 2026-10-01; reversed by the operator,
  2026-11-07). Each Stage already waits for the operator's word, and *Consequences* prices a run, so a
  standing hold added nothing.

## Consequences

- **Build cost:**
  - the generator and its traps;
  - the answer keys;
  - a multi-session trial driver;
  - grading for the record and the answers, with controls both ways.
  That is several builder sessions: mid-sized, mostly Sonnet builders under one Opus design review,
  in the pattern of the comparison mode.
- **Run cost, rough; the first pilot's `--estimate` pins it:**
  - one Stage 1 run is about 120 maintenance sessions plus about 90 question sessions per model;
  - raw-pile sessions cost the most, since they read the history at question time;
  - at the measured per-session costs (Opus 5.5 about $0.21 in the behavioural eval's harness),
    roughly **$60–130 per model**.
- **Maintenance burden:** a generator and keys to keep in step with the templates and the care
  contract. A template change can move what a correct maintained record looks like.
- **Limits that will remain:**
  - Synthetic histories are cleaner than real ones.
  - Headless is not live.
  - The PM instruction's wording moves plain Claude's result. It is fixed in the fixture and
    recorded in every row, like the comparison's arm labels.
  - Three trials per arm detect only large differences (`evals/topics/how-sure-a-green-is.md`).
- **Nothing here gates anything.** Like the comparison, it measures and never counts as a passing
  run.
