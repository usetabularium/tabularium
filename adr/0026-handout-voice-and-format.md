# ADR-0026 — Patient-handout voice, canonical handout format and the references-rendering fix

- **Status:** Accepted 2026-06-23
- **Date:** 2026-06-23
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

ADR-0011 set the handout spec but left three things unsettled, and the handouts had drifted:

1. **Voice.** Earlier patient handouts spoke as the caregiver (informal address, personal sign-off),
   a later baseline as the treating physician (formal address, clinician sign-off).
2. **Filenames.** Two earlier files had dropped the `__handout-<audience>__` infix.
3. **A rendering bug** in the clinician template and two clinician handouts: in "Piśmiennictwo" (the
   references) a `> ` blockquote sat straight before `1.`, with no blank line. On the
   python-markdown → weasyprint route the references collapse into the blockquote's paragraph or the
   `<ol>` splits and renumbers.

## Decision

What holds now: `_templates/HANDOUT-RULES.md`, the handout templates and the L8 row of
`checks/README.md`.

1. **The patient handout's voice is neutral, warm, plain and informational; it impersonates no one
   and signs as no one** (operator, 2026-07-04). Addressed formally, it closes by routing diagnostic
   and treatment decisions to the treating clinicians. The 2026-06-23 decision had it speak as the
   treating physician, signed "lekarz prowadzący", because that voice carries more authority for
   adherence and reads consistently for a clinician. The operator reversed it: the physician voice
   **wrongly implies the handout carries independent clinical authority**. Nor does the caregiver
   voice return: the caregiver may be a contact, never the narrator. Register and language stay per
   person (ADR-0008, ADR-0011), clinician handouts stay clinician-to-clinician, and voice is not
   machine-checked.
2. **Canonical filename `YYYY-MM-DD__handout-<audience>__<slug>.md`** (patient or clinician), the
   PDF sharing the stem (2026-06-23). It first bound new handouts only, the two strays
   grandfathered; on 2026-06-27 guard L8 made it commit-blocking (`35aabc0`) and the strays were
   conformed (recorded 2026-07-04). ADR-0033 adds an optional ID segment; ADR-0039 keeps the leaf in
   sealed units.
3. **The templates hold one section skeleton per audience** (2026-06-23), and **a handout is a full
   synthesis** (2026-07-31). The *delta* option (only what is new, non-essential sections dropped
   but the escalation section kept whenever the patient is asked to act) is suspended: ADR-0034
   removed delta-by-default on 2026-07-26 for want of a baseline binding and a material-omissions
   check.
4. **The references render as a real numbered list** (2026-06-23): blank lines after the heading
   and before `1.`, the introductory note a paragraph and never a `>` blockquote, one line per item,
   none blank between. The route is python-markdown with `sane_lists` and `tables`, then weasyprint,
   since ADR-0032 the house renderer.
5. **Clinician rigor is shown once** (operator's reduction panel, 2026-10-04): a one-line evidence
   key opens the handout and `NOTICE.md`'s intended-purpose sentences close it. The 2026-06-23 rule
   showed it twice (a legend up front, the quality bar in a closing *Metodyka* appendix); that and
   the "quality-controlled system" pitch were dropped as not serving the reader.

## Alternatives considered

- **Amend ADR-0011** (rejected 2026-06-23): reversing shipped voice practice and adding format and
  render conventions merited their own record; ADR-0011 stays the register, scope and
  rendering-spec decision.
- **Caregiver voice** (rejected 2026-06-23 and 2026-07-04) and **physician voice** (reversed
  2026-07-04): point 1.
- **Renaming the strays at once** (deferred 2026-06-23: it touched the Markdown, the PDF and
  `INDEX.md`, a host-side move then; done 2026-06-27).
- **Only a blank line before `1.`** (2026-06-23): it stops the collapse, but the paragraph form
  (italic then) with `sane_lists` also resists renumbering.

## Consequences

- One voice, one skeleton, one filename rule, and a correct reference `<ol>`. The templates embed
  the rules; `HANDOUT-RULES.md` is their source of truth.
- The check is the render-and-eyeball step (references numbered 1..N, tables printed). Since
  2026-06-27 L8 reds a mis-named file, superseding "no new executable guard"; build-QA B2
  (ADR-0034) catches a collapsed reference list.
- Handouts predating a rule (caregiver- or physician-voiced, one clinician handout with the latent
  references bug) were grandfathered, each to conform on its next render (since ADR-0039, a new
  dated unit).
