# ADR-0009 — Medical peer persona

- **Status:** Accepted by 2026-06-07; superseded in part by ADR-0050 2026-10-27
- **Date:** not recorded in its register row (the register was backfilled 2026-06-07)
- **Deciders:** not recorded for point 1; the operator for the later points
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The original decision is a register row, copied here on 2026-09-29 when the register became an
index. Its reason: "Performance is best when framed as a peer in an unfamiliar high-stakes domain;
the framing was missing." From 2026-10-24 the record also took the care contract's decisions on
recommendations, medicine look-ups and what comes before research.

## Decision

What holds now: `CONTRIBUTING.md` → *Operating stance when building*; `CLAUDE.md` (*An emergency
comes first*, *Stance*, *Sessions and people*, *Next steps*); `reference-library/README.md` →
*Official product information*; and the profile, medications, handout-rules and verifier-prompt
templates in `_templates/`.

1. **A peer framing** (date not recorded): a medical peer persona in `CLAUDE.md` ("Operating
   stance"). By 2026-10-11 that section was gone and the framing lived in *Stance* (drift recorded
   that day).
2. **A clinician's epistemics, not the role** (2026-10-12): a careful clinician's method, not a
   clinical role or qualification. The build contract asks for the rigor of a careful medical-data
   specialist and clinical software architect, without "with medical background"; the handout
   fact-checker's prompt, and from 2026-10-14 the care contract (in a change carrying a core
   behavioural run), say "Bring a careful clinician's epistemics".
3. **Two more origins for a recommendation** (operator, 2026-10-24, after a blind break test). The
   recommended tier of *Next steps* also holds general health advice that nothing on record changes
   (six topics: harmful substances, alcohol, sleep, diet, activity, weight; never a medicine,
   supplement or screening) and applied guidance: a guideline or official product information
   meeting a current A or B fact with little room for judgement (a listed interaction, an allergy, a
   dose or duration above the label maximum), whose step is to contact the prescriber or a
   pharmacist, timed by severity, never to stop or change a medicine. Any other conclusion of the
   session's own stays a question for a named clinician. Product information may ground an item in
   the record; citing it in a handout waited on roadmap decision D1. The review that day added a
   mismatch-not-diagnosis framing, a timing ladder with an out-of-hours route, the more urgent
   timing where sources disagree, raising a serious item whose current use is unconfirmed, an
   applicability checklist and a dependence question; a deliberate prescription was context, not an
   exemption, and overdue monitoring was raised again (full text: `_templates/profile.md` before
   `fc25f83`). Why: advice no clinician would dispute was being pushed out of the plan, with
   nowhere to go when no clinician was placed to be asked, and a severe, documented conflict should
   not wait months for a visit.
4. **Open the product information; research after a declined emergency call** (operator,
   2026-10-25, after a blind break test). For a medicine's limits, duration, interactions and
   warnings, a care session asks which product is in use unless stated, opens its approved
   information first, names the document behind each fact and reports only what bears on the
   question; the look-up carries nothing about the person, what it could not open is given marked
   inference, and a leaflet's figure is never the person's value. An emergency line never waits
   for research. When the operator says it is not an emergency, the symptoms described still pick
   the line; after an urgent line, or at once when neither fits, the session researches (the
   product information, and on-screen questions for what the answer hinges on) even before the
   question is tied to anyone; after an emergency line, research waits until the operator returns.
   Why: a care session answered a two-drug interaction question twice from memory and asked
   nothing; told to check, it opened other countries' texts for other products, with a different
   duration limit, and reported irrelevant sections in untranslated clinical terms.
5. **Overdose, each medicine, the hand-off** (operator, 2026-10-25, a third break round). The
   emergency trigger also covers a possible overdose or poisoning with no symptoms yet (under
   "symptoms" alone, a silent paracetamol overdose fell to research first). Each medicine involved
   has its own product information opened, and a leaflet warning that matches what is known of the
   person always bears on the question. A session outside Claude Code's main care folder may still
   give a warning that cannot wait before its hand-off, kept brief (superseded in part: ADR-0050
   widened it to a full read-only answer, operator, 2026-10-27). A self-medication course has its
   own section in the medications template.
6. **Emergency guidance may be fetched in the background** (operator, 2026-10-25, raised in
   review). After the call line, and only then, a background helper may fetch official emergency
   guidance (the product's overdose section, the poison information service) as a few plain lines
   readable under stress; record work still waits until the emergency is handled. Why: vetted
   instructions, quickly, can save a life, and in Claude Code a helper does not delay the call line.
7. **A patient handout states plain advice plainly** (operator, 2026-10-27). A recommended item of
   ordinary self-care is a plain step, and a source's own instruction, such as a leaflet's warning,
   is stated as the source gives it, naming the source; what it means for the person's own
   treatment stays a question for their doctor or pharmacist, with its urgency and uncertainty. The
   clinician handout is unchanged. Why: "something to ask, never an instruction" turned advice meant
   for anyone into "ask your doctor whether…" and could blunt a leaflet's own warning (found in
   review; no care transcript showed it either way). Constraint: the operator's 2026-10-14
   decision keeps patient handouts as they are until Anthropic answers a usage-policy question;
   quoted leaflet warnings fit even its "explain and ask" fallback, and the plain self-care steps
   are what that fallback would move back to the clinician handout.
8. **The recommended tier becomes a short cue** (operator, 2026-10-27, after a blind break test).
   Point 3's guidance (about 700 words) and its `CLAUDE.md` bullet became one cue in both places:
   the three origins (applied guidance now a warning from an opened source that fits a recorded
   fact), the session's own conclusions as questions for a named clinician, and each item and
   question timed to its harm, one that could hurt before the next visit opening the reply and
   raised today, before any next dose. Point 3's six topics and review additions went, with the
   "more pressing" clause, the not-yet-started rule, "never infer stopping, withholding or
   continuing a medicine" and the overdose line (the emergency section keeps it). Why: a review of
   care sessions and the eval history found plain Claude on Opus 5.5 matching Tabularium on harm
   (0/48 in both arms), the contract's measured value lying elsewhere (emergency first, opening the
   original and the product information, prescribed vs taken); in care, "own conclusion is never a
   recommendation" turned an urgent scan within days into a soft question for weeks later, and the
   label-warning branch over-called twice, once on the operator's everyday word; no eval had
   exercised the tier.
9. **A label warning is timed by its own words** (operator, later on 2026-10-27, after a blind
   break test). A label warning about the person or their family (a condition, a finding, age,
   pregnancy, breastfeeding or family history; not an interaction, which keeps the harm test) is
   raised the same day, before the next dose, only if it says not to use the medicine ("avoid" too)
   or meets a recorded allergy, otherwise within a week. Whether to skip a dose is the clinician's
   or pharmacist's call. Advice to stop a substance where dependence is possible comes with
   professional support. Why: with only "(a label warning: by the label's own words)" in the cue,
   blind sorts got every emergency, contraindication and allergy right and told no one to take or
   skip a dose, but let the harm test override a label's caution and let cautions drift to a month
   when no visit was booked; the folded wording first let a medicine-with-medicine warning not
   worded "do not use" fall to a week, closed by "(not an interaction)". The last two tightenings
   ("avoid"; the interaction exclusion) were not re-tested.

## Alternatives considered

- **A clinical role or qualification** ("with medical background"): dropped 2026-10-12.
- **"Wrong dose" in the emergency trigger** (left out at the operator's review, 2026-10-25): a
  harmless double dose is judged urgent or not, not sent to the emergency number.
- **A patient-handout question about "anything about the person's own treatment"** (rejected in
  review, 2026-10-27): it would have turned the handout's existing prescriptions into questions.
- **Pull request 214**, applied guidance meeting a fact about the person or their family (closed as
  superseded, 2026-10-27): its cases were sorted against the cue instead, giving point 9.
- **A clause that a relative's result is not the person's own** (not added, 2026-10-27): the
  *Family history* section of `_templates/profile.md` already says so, and the sorters held to it.

## Consequences

- The build and care contracts share one stance, a careful clinician's method; the operator and
  their doctors decide.
- Limits:
  - A session may advise holding a new, not-yet-taken medicine with a listed contraindication until
    its prescriber answers, and "before any next dose" can be read as holding a dose.
  - "Within a week" counts from today, so a short course or a planned first dose sooner than that
    rests on the harm test.
