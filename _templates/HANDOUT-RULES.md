# Handout rules — patient and clinician handouts

Read before writing any handout. The templates embed these rules; this file is their source of truth.
Order of work: `HANDOUT-SOP.md`. Fact-checker: `handout-factcheck-verifier.md`. Render commands,
build-QA and refusals: `handout-assets/README.md`. Examples are synthetic.

## Audience, language and voice
- **Two audiences, independent** (an encounter may get only one): the patient handout
  (`handouts/patient/`) in plain everyday language; the clinician handout (`handouts/clinician/`),
  built for analytical depth and to deserve trust.
- **Language per person:** `Patient language` / `Clinician language` in `profile.md`, never hardcoded.
  Copy the template in the reader's language: English `handout-<audience>.md` (the base), Polish
  `handout-<audience>.pl.md`. The English wording has not yet carried a real handout: the first time
  it does, tell the operator. Any other language: translate the English template, keep its sections,
  and tell the operator nobody has reviewed the wording. Never fall back to another language,
  even with a warning. Write `lang: en` or `lang: pl` exactly: any other value, `en-GB` included, prints an
  English footer — for a third language, tell the operator so. One encounter's handout in two languages: the
  second gets its own slug (`<slug>-<lang>`, e.g. `<slug>-pl`).
- **Scope: medical and care-actionable only** — no social commentary, no guessing how the person
  feels, no non-medical reassurance. If a feeling or preference matters, ask the operator.
- **Voice: neutral, warm, plain, informational** — neither the treating physician nor the caregiver
  (who may appear as a contact, never as narrator). It impersonates no clinician and signs as none (no
  "your doctor" sign-off, in any language): it is a summary of the person's records and
  conversation to take to appointments, with no authority of its own.
- **Register**, from the profile's `Handout calibration`: high health literacy and intact cognition →
  **lean** (keep why a step helps; don't define terms the person plainly knows, judged from the
  recorded calibration, never an assumed history); cognitive impairment → **explanatory** (simpler
  sentences, a little gentle repetition, definitions where they help).
- **Warm once, and don't over-signal honesty:** at most one warm opening, no repeated endearments, no
  "honestly", "frankly", "to be fair", "I don't want to overstate this" or their equivalent in the
  reader's language — say it plainly.
- **One form of address, held throughout.** In a language with formal and informal (or gendered)
  address, default to the formal form its template shows; the informal only if the person prefers it;
  never the two mixed in one handout. English default is `Dear {{first name}},`; title and
  surname only if preferred.
- **Patient handout:** plain words, the minimum necessary; meet the person's known reservations (from
  `profile.md`) gently and head-on. Close with one short note (`{: .provenance}`) that opens with the
  template's fixed sentence (prepared from the person's records and conversations with the help of an
  AI assistant), then, neutrally: meant to help prepare for appointments; not medical advice or a
  diagnosis; decisions are made by the patient with the doctors treating them.
  A recommended item of ordinary self-care (never a medicine, supplement, test or screening) is a
  plain step, giving no personal reason the record
  does not; a source's own instruction, such as a leaflet's warning, is stated as the source gives it,
  naming the source, and what it means for the person's own treatment stays a question for their
  doctor or pharmacist, keeping its urgency and uncertainty.
  Keep the template's source list (`References`, or its template's heading in the reader's language)
  only when the operator says the reader wants the evidence — the sources the text cites as `[1]`,
  `[2]`, each opened and clearing the bar; otherwise delete it.

## Clinician handout
- **Structured and scannable:** short labelled sections, key data in tables — never a wall of text.
- **Observations and questions, not advice:** the background section gives the course so far, what
  the records show and what the caregiver has noticed, each fact once with its mark (a fact the
  tables give is referred to, not restated); one questions section follows, and each question says
  why it is asked, a citation only as context. The section always ends with the standing question of
  what should prompt seeking care before the next visit, and where; its "why" rests on the record,
  never on a list of warning signs of the handout's own. No diagnosis or treatment recommendation of
  the handout's own. A recommended item of general health advice or applied guidance appears as a
  question whose why names the guidance and the recorded fact it applies to, keeping its urgency and
  uncertainty. An item resting on official product information cites it by link and revision date,
  for that medicine's own facts only (`reference-library/README.md` → *Official product
  information*); any other citation clears the bar.
- **Evidence key up front, origin and limits at the close — each once:** the one-line key (opening
  blockquote: [A]/[B]/[C] and ⟨…⟩), and the standard closing note (last section). No credibility pitch:
  the marks and the cited sources show the rigor.
- **Citations:** every non-observational claim cites a source that clears the bar in
  `reference-library/README.md` and that you opened and verified. The library is a cache: add a source
  as you cite it (the citation check warns on one not yet catalogued). When in doubt, leave it out.

## Notation and reader-facing language
Natural prose in the reader's language; never the system's machinery.
- **Provenance carries over:** a grade-C or ⟨confirm⟩ fact reads as provisional; an analysis-derived
  figure is never presented as documented.
- **Evidence marks are for clinician handouts only:** bold `**[A]**` / `**[B]**` / `**[C]**` — never
  "(grade B)", "grade-C" or prose; the opening key defines them once.
- **References are plain `[1]`, `[2]`** into the reference list; never lettered (`A.` collides with
  the grades). A `1.` list item is not a citation.
- **The confirm tag, also clinician-only, in the reader's language:** ⟨do potwierdzenia⟩ (or the
  document language's equivalent), in English ⟨to be confirmed⟩ — never anything beginning
  "⟨confirm" (build-QA halts).
- **A patient handout carries neither marks nor the bracketed confirm tag.** It says where a fact
  comes from and how sure it is in plain words only, in the reader's language ("your doctor's letter
  says…", "you told us…", "not yet confirmed").
- **No system vocabulary:** not "Vetted", "reference-library", "handout", "baseline" or "delta" as
  labels for a handout's scope, `{{placeholders}}`, `{: .markers}`, `cal-…` ids. "Baseline" and
  "delta" in their clinical sense stay (a baseline lab value, an EEG delta wave). In English, where
  build-QA warns on a word the reader would not know, write "class A" or "level A" for "grade A",
  "summary" or "document" for "handout", "checked" or "verified" for "vetted", "source list" for
  "reference library".
- **Inline translation only across a real language gap** (a term the caregiver must say to a clinician
  in another language); a same-language document gets no glosses like "(active diagnoses)".

## Header, identity and footer
- **Title (H1):** the shortest phrase that says what the document is (specialty + kind), e.g.
  "<Specialty> summary". No date, no patient name.
- **Identity line** (`{: .identity}`), one line, as the templates lay it out, in the reader's language:
  `Patient:` (clinician) / `For:` (patient), the name, `(age)`, ` · `, the occasion and its date
  (`Consultation` / `Visit summary`), and on the clinician handout ` · Caregiver: name · phone`. The occasion date may differ
  from the prep-date.
- **Footer:** the renderer prints the prep-date, attribution, ID and page numbers; the prep-date never
  goes in the header. The attribution ends with the site root, `usetabularium.com`.
- **ID** `TAB-<PPP>-<NNN><C>`: the person's tag from `profile.md`, the next number in their `INDEX.md`,
  a check character — never worked out by hand (`HANDOUT-SOP.md` → *IDs*) — and `.rN` only for a
  re-issue (new facts → new number; a re-render keeps the ID). Front matter at the very top: `id`,
  `date`, `lang`.

## Rendering and visual style
- **Render only with the house helper** (`_templates/handout-assets/render_handout.py`, pinned
  `.venv-render/`): never a hand-rolled markdown→PDF call or a `.docx`. A default render **is the
  seal**; `--draft` writes an unsealed `<stem>.draft.pdf`.
- **One house stylesheet; never restyle a handout.** Markers: `{: .identity}` on the identity line,
  `{: .provenance}` on the patient closing note, `{: .metodyka}` on the clinician one. Never spell a
  marker inside an HTML comment (build-QA reads comments).
- **Typography stays upright:** `*single asterisks*` keep the surrounding style; `**bold**` for short
  emphasis; never a whole paragraph or note in either; no italic faces.
- **A blank line above every list**, any marker, or it runs into the paragraph above. The reference
  list must render as a real numbered list: no `>` blockquote straight before `1.`, one line per item,
  no blank lines between items.
- **Build-QA** (glyphs, lists, leaked markers — freeze them before the fact-check, `HANDOUT-SOP.md`
  step 3): never hand over a PDF that failed it; an authoring fault halts — fix the source. When a
  clean PDF cannot be verified the helper writes a plain `.txt` instead: a correct plain handout beats
  a broken pretty one.
- **Verification step: eyeball the rendered PDF** — tables intact, lists are lists, sections break, no
  clutter. A handout that looks wrong is wrong.

## Kept details
For a private-mode person whose identity file keeps details from the AI (`identity.py status`), the
handout source never holds those details: write `⟨withheld:patient-name⟩`, `⟨withheld:date-of-birth⟩`, and for a contact `⟨withheld:phone⟩` /
`⟨withheld:other-name⟩` (only when exactly one value of that kind is recorded; otherwise name the
contact by role), in plain body or link text only — never the front matter, a link target, an image,
an autolink or code. Write the age as such, from the identity command's `age`, when the date of birth is kept. A draft shows the handle
and neutral labels; eyeball that. The seal fills in the recorded values, the Markdown keeps its
placeholders, and no session may read the sealed PDF: **the operator looks at it before handing it
over.**

## Fact-check gate — every handout, before hand-over
- **Every handout is fact-checked before it is sealed** by a fresh-context peer subagent that did
  not write it, on an Opus-class or stronger model, scoped to this one person, briefed as
  `handout-factcheck-verifier.md` says; it reads its standing prompt, `handout-verifier-prompt.md`,
  itself, and that prompt owns its scope and method.
- **An open MUST-FIX blocks hand-over; an identity-mismatch** (wrong-person attribution, a relative's finding presented as this person's included; family history stated as the relative's, by role, as this record gives it, is not one) **is a hard stop.**
- **A care-material fact an original settles is never handed over as an open fork:** where sources
  disagree on it, the higher grade states it, in the record and the handout; a conflicting report the
  operator has not settled stays beside the original's value, attributed as reported.
- **A FAIL is repaired** by each finding's fix class; after the second FAIL the operator decides
  whether another round runs (verifier → *After the verifier runs*).
- Its verdict is a hash-stamped `<stem>.factcheck.md` sidecar (local-only); the seal refuses without a
  fresh PASS for the Markdown's current bytes, so any later edit means another verify round.

## Filing, sealing and the register
- **Filing:** `YYYY-MM-DD__handout-<audience>__<slug>.md`; the PDF (or fallback TXT), `.factcheck.md`
  and `.attest.json` share its stem. One encounter dir per handout,
  `med/handouts/<audience>/<YYYY-MM-DD>-<slug>/`, created once, when the reviewed draft moves in. An
  unreviewed draft lives in the person's `med/analysis/drafts/`, never in the handout lane. The
  reviewed Markdown and its fact-check sidecar may wait unsealed in the encounter dir across sessions;
  `.draft.pdf` files and previews stay outside it. Name it right at generation: the board checks names
  (L8) and sealing (L15).
- **A sealed unit is permanent** — never edited, deleted, regenerated or moved (its attestation binds
  it to its person and encounter). New facts → a **new dated unit**; no archive step, no "spent"
  marker; `INDEX.md` marks the current one.
- **A handout is a full synthesis.** Delta scope waits for baseline binding and a material-omission
  check; an INDEX row records lineage and never authorizes a delta.
- **Legacy:** pre-ADR-0039 flat files and `archive/` dirs are inventoried in `handouts/.legacy-frozen`
  and closed to new writes; they migrate per person at the operator's pace.
- **The register** (`med/handouts/INDEX.md`, one per person): a row appended for every handout, naming
  its encounter dir (a sealed unit missing from it is red). **ID** leads and sorts; a handout older than
  IDs carries `—` (files are never renamed). **Supersedes** names the ID replaced, `.rN` chain
  included; the old unit stays put — flip its row's **Status**. Old `delta` rows are history, never
  rewritten. A note in a person's register never overrides this file (voice included): where they
  disagree, flag it to the operator and correct the note once they agree.
- **Handouts are products, never evidence.** Nothing under `handouts/` is cited or filed as a source;
  an annotated printout that comes back enters intake as a new scan. Legacy PDFs without a Markdown
  source are preserved, not verified, and assert nothing.

## Clinician closing note — standard text
After the last section: a `---` rule, then the note, no heading, tagged `{: .metodyka}`. Its first
sentence says an AI assistant helped prepare the document; then come `NOTICE.md`'s intended-purpose
sentences, and last a link to the website's clinicians page. Keep the note verbatim, in the clinician's
language, and add nothing about how carefully the document was made. The Polish template carries the same note in Polish; any other language
translates the English below.

> This document was prepared with the help of an AI assistant, using **Tabularium**, a personal
> record-keeping and care-coordination methodology for patients and informal caregivers. It is not a
> medical device and is not intended for diagnosis or treatment decisions; clinical decisions belong to
> qualified clinicians. Outputs may contain errors and must be verified against source documents.
> About this document: [usetabularium.com/clinicians](https://usetabularium.com/clinicians/)
