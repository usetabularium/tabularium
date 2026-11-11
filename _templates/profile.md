# Profile — {{NAME}}

> Last reviewed: {{DATE}}

## Identity & basics
- Name / role: {{NAME}}
- Date of birth / age:
- Patient language: {{e.g. English}} — language for this person's patient handouts
- Clinician language: {{e.g. English}} — language for this person's clinician handouts (may differ, e.g. a clinician abroad)
- Handout calibration: health literacy {{high/medium/low}} · cognitive impairment {{no/yes}} → patient-handout register {{LEAN if literate+intact / EXPLANATORY if impaired}} (drives how much we explain; see _templates/HANDOUT-RULES.md)
- Known reservations / preferences: {{the person's known fears, objections, priorities — the patient
  handout pre-empts these ("What's the aim?" section); collected at interview; see HANDOUT-RULES}}
- Private mode (experimental, ADR-0029): {{— none · OR: <identifier class> then the marker: never-API
  inside the brackets ⟨ ⟩ (U+27E8, U+27E9), no spaces — spelled apart here so an unfilled line is not
  private mode — operator decision YYYY-MM-DD; then which country's number, beside the marker on
  the same line, in a bracket pair of its own and never inside the marker's: id-scheme KEY, KEY a row
  of tools/private-mode/id-schemes.tsv, or unlisted for a number not on it, covered by hand (several
  joined with commas; no tag = every row searched; spelled exactly and kept on the marker's line, or
  it is refused); ingestion
  then follows tools/private-mode/ (local
  redaction + operator gate BEFORE any model pass); the identifier itself is never recorded anywhere in this tree · when the
  person's names are kept from the AI too, the same line says in words whether the handle was in use
  before; which details are kept lives only in the identity file (tools/private-mode/topics/kept-details.md),
  and the lines above then hold placeholders for them, the age its reference date}}
- **Person record ID (local; never prints; minted by the ownership tool's `init`):** `{{32 lowercase hex}}`
  Never reused as the printed handout tag; rotation is break-glass only.
- Handout tag: {{— none yet · OR: three symbols, set at the first handout (_templates/HANDOUT-SOP.md → IDs); never changed}}
- Allergies / intolerances: {{never blank — a blank line reads as "none". One of: each allergy
  with its reaction, source and date · none known (source + date) · not yet established (source +
  date), saying whether it was asked and is unknown or not yet asked ⟨confirm by YYYY-MM: allergy
  history⟩. An original and a report that disagree: keep both, the original first}}
- Baseline (height, weight, blood type if known):

## Care team
| Role | Name | Facility | Contact | Notes |
|------|------|----------|---------|-------|
| GP / family doctor | | | | |
| | | | | |

## Active conditions

| Condition | Since | Status | Managing clinician | Evidence (file in med/sources/) |
|-----------|-------|--------|--------------------|--------------------------------|
| | | | | |

## Family history
> Conditions that may run in families, in blood relatives by role to this person (side, full/half):
> condition or variant (germline or tumour, classification, report date), ages at diagnosis and
> death, when known; mother and father related by blood: a row. Never blank: rows, and for the rest
> none known (what was asked; source, date), unknown (why) or not yet asked; an older profile gains this
> section at its next update. No name, handle or other identifier. Home exposure: this person's own
> fact, not here. Source: this person's sources, or a report (B) asked by role
> (`_templates/INTAKE.md` §1) — never the relative's folder or combined-session section; a blood
> relative the roster lists for them (check it): `_templates/family-history-helper.md`. A relative's
> finding is this person's only on their own result (reported included), never by inference, the
> operator's included; the history, and a clinician's plan on it, are this person's facts. Advice
> for someone else: an open item to pass on. A reported (B) fact here that a test, screening or
> medicine item or question gives as its reason:
> `⟨confirm by YYYY-MM: a copy of the relative's report⟩`.

| Relative (role, side) | Condition or variant | Age at diagnosis | Age at death, cause | Source, date, grade |
|-----------------------|----------------------|------------------|---------------------|---------------------|
| | | | | |

## Current status

## Next steps
> Each item also gives its current state.

### Planned (booked / in queue)
- [ ]

### Recommended (not yet acted on — a clinician or document, general health advice, or applied guidance)
- [ ]

## Open items
> by when: `YYYY-MM-DD`, `YYYY-MM` or `—`; state: booked · expected · to book · to ask, or overdue.
<!-- OPEN-ITEMS:BEGIN -->
| what | who | by when | state |
|------|-----|---------|-------|
<!-- OPEN-ITEMS:END -->

## Change log
- {{DATE}} — profile created.
