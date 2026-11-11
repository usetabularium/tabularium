# ADR-0047 — Guard L3: literature-value qualifier (low-noise)

- **Status:** Accepted 2026-08-16; guard L3 retired 2026-10-04
- **Date:** 2026-08-16
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).
- **Supersedes:** ADR-0018 in full (its revisit trigger, spent when L3 was built).

## Context

`CLAUDE.md` (then *Drift control & provenance*) carried the rule **"a number is either *this person's measured value* or a *typical/study figure*. Label it."**
A study's median logged as the patient's value, or a paper's example age read as a confirmed age,
is one failure: the last incident class in the catalogue with no executable check.

ADR-0018's tripwire for the deferred guard fired twice:

- **2026-06-25.** It fired, and the guard was **consciously re-deferred**: on a **small record
  set** a numeric patient-vs-literature heuristic cannot be tuned. Every clinical number is
  a candidate, and **alert fatigue that erodes the green signal is worse than no guard at all.** The
  sharper trigger: a larger record set, or a handout placing a literature range and a measured value
  of the same quantity in one document.
- **2026-07-04.** The record-set trigger fired; the call was blocked on the operator.
- **2026-08-09 (operator).** **Build it, in the low-noise version**, with that reasoning as a hard
  constraint: *the guard must red only where the ambiguity is real and care-material*, and if the
  noise floor cannot be met on the live corpus, come back with what a tuned version would cost
  rather than ship a noisy guard.

## Decision

What holds now: the rule is prose in `CLAUDE.md` → *Stance*; the guard's atom sets, normalization,
strip list and clause rule survive in `evals/harness/grader.py` (EV-04b's F4).

1. **A context-triggered attribution demand, not a numeric heuristic** (2026-08-16). L3
   (`checks/check.sh`) never asked whether a number was plausible for a person, only whether a line
   plainly about the literature said whose figure it held.
   - **Trigger:** a citation id, or a study-design or population-statistic term (meta-analysis,
     median survival, prevalence, hazard ratio …), in English or Polish.
   - **Demand:** a clause with a marker and a care-material number (dates, citation ids and
     document references stripped) declares its own attribution.
   - **Satisfy:** `⟨lit⟩` (a typical or study figure), `⟨pt⟩` (this person's measured value), or
     the plain words the live corpus already used.
   - **Waive:** `⟨not-a-figure: verified YYYY-MM-DD⟩`, dated like L10's `⟨not-an-id⟩` so an
     exemption is an audited act; undated, it is not honoured, and it covers its own clause only.

   Measured on the live corpus that day: every literature-context line came
   with a care-material number already attributed in plain words, **0 flagged**, no patient
   doc edited. Adding a marker atom widens the trigger and can reopen noise, so the
   measurement was to be re-run on the live corpus before landing one.

2. **The first build was held, not merged** (2026-08-16): a same-day independent red-team confirmed
   five findings, all fixed before landing (points 3–5, and a BSD `sort -u` dedupe that could drop
   a distinct row).

3. **A clause ends only at a `;` at bracket depth 0** (red-team finding 1, then the fix's first live
   run, 2026-08-16). A whole-line qualifier let an incidental "her own", or another clause's waiver,
   launder an unattributed figure; splitting on every `;` then broke a correctly attributed sentence
   inside its own parentheses. Never an em-dash or a period: the corpus attributes after an em-dash,
   and Polish abbreviations make period-splitting unsafe.
   - **Arbiter decision, recorded so it is not silently "fixed" later:** a qualifier in a FOLLOWING
     clause is deliberately NOT honoured — `prevalence 41%; a literature figure, not theirs` **reds
     by design** — because honouring the next clause reopens the laundering bypass clause scope
     closed (`median survival 18 months in this setting; not his usual room` would pass). The cost
     is friction in the safe direction: the author writes the attribution in the same clause or
     after an em-dash.

4. **No reference-range leg** (red-team finding 4, 2026-08-16). `ULN`, "reference range" and their
   kin reddened ordinary own-lab idiom and were removed, in the operator's direction: low noise
   outranks reach. Provenance tags were deliberately not accepted instead (*Alternatives*), so
   range-vs-value confusion was caught only beside statistics or citation vocabulary.

5. **Match a normalized copy, with anchored atoms** (red-team findings 2–3 and tuning, 2026-08-16).
   Emphasis or an invisible code point inside an atom (`meta-**analysis**`) made the scan find
   nothing; a per-line normalized copy kept every locator. Atoms open to substring matches carried
   a left word anchor, and acronyms were also case-sensitive and right-anchored: case-insensitive
   `ROM` matched "from", and unanchored `not his` accepted "not histology" as an attribution.

6. **Scope: each person's `profile.md` and `medications.md` and their two templates, whole file,
   change log included** (2026-08-16). A figure baked into a template reaches every person added
   later, and the templates kept the guard from being vacuous on a patient-free tree. Handouts had
   the fact-check (ADR-0034); analysis notes are grade-C working reasoning. Output was locators only
   (guard output is model-visible), and the guard failed closed (ADR-0021).

7. **Retired 2026-10-04; the number is not reused.** It flagged 0 of 1,045 lines in recorded use.
   The rule stays as prose in `CLAUDE.md` (label a study figure in words); the `⟨lit⟩`/`⟨pt⟩` tags
   and the guard's bites went with it.

## Alternatives considered

All rejected on 2026-08-16.

- **Flag every clinical number lacking a provenance tag** (ADR-0018's sketch): the noise both
  re-defers were about; the board goes permanently amber and the green signal dies.
- **Accept any provenance tag as the resolver** (`(imaging YYYY-MM-DD)`, a grade letter): the
  historical error was a literature figure written *with* a confident-looking patient provenance.
- **Exclude the change log, as L7 does for dates:** including it cost zero additional false
  positives on the live corpus. A historical date records what was known then; an unattributed
  figure was always unattributed, so adding the attribution corrects rather than rewrites.
- **A fresh tag required everywhere:** the corpus already attributed figures in plain words, so no
  patient doc needed an edit; the tags were for new writing, not a migration.
- **Guideline-body acronyms as markers:** the only false positive in tuning; a body name identifies
  a source, not a statistic.
- **"Typical", "guideline", "study", "normal", "target":** each means both things (a person's own
  typical reading, a qualitative recommendation, a band prescribed for this person). No marker may
  be a word that also describes the person.

## Consequences

- While it ran, an unattributed population statistic in a canonical record stopped the board, every
  session and, through the ADR-0022 hook, at every commit.
- Limits, stated so a green never read as coverage: it forced an attribution but could not verify
  it, and an unmarked literature figure (a bare study median in ordinary prose) was invisible, the
  price of the low-noise constraint and its largest hole; line scope and an enumerated atom set
  left narrower gaps.
- Since 2026-10-04 no guard checks that a study figure is labelled; the reader does.
