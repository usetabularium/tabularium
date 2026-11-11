# Reference library — curated clinical sources

Shared across all persons. A **cache** of the sources that cleared the bar and were verified,
not a prerequisite for citing: a source that clears the bar may be cited once you have opened and
verified it, and is added here as you cite it, not admitted beforehand. A metaanalysis on a
general-medicine topic applies to more than one person, so it lives once, here — not duplicated per
person.

## The bar (a source must clear *all* of these to be cited and added)
- Peer-reviewed and **PubMed-indexed** (or a recognised guideline body: NICE, USPSTF, ESC,
  Cochrane, WHO, or national specialist societies suitable for the patient's locale, e.g. U.S.,
  U.K., German or Polish ones).
- **Recency**: prefer the last ~5 years, unless it is a landmark / still-current standard.
- **Evidence tier**: prefer systematic reviews, meta-analyses, and guidelines over single
  trials; single trials only when they are practice-defining.
- **Not predatory** — no journals on Beall's-list-type registries; legitimate publisher.
- Traceable: a working DOI or PMID.

### Official product information
A medicine's summary of product characteristics or patient leaflet, as approved, clears the bar for
that medicine's own facts only: dosing and its limits, how long it may be taken, contraindications,
interactions, warnings. Never for a wider clinical claim.
- **The product in use.** Ask for the name and strength on the box; limits differ between products of
  one substance. Open that product's text from the country where it was dispensed — its regulator's
  register first. For example: in Poland the Medicinal Products Register
  (rejestrymedyczne.ezdrowie.gov.pl, both documents as PDF); in the UK the MHRA's products site
  (products.mhra.gov.uk, summaries of product characteristics and leaflets); in the US DailyMed
  (dailymed.nlm.nih.gov, FDA labelling — it also lists unapproved products, so check the approval
  status; Drugs@FDA for an approved prescription label); for a medicine authorised across the EU, its
  EMA page (ema.europa.eu). Another product's or country's text, or a retailer's page, is a
  stand-in: say so, and never give its limits as this product's.
- **When a fetch fails** or returns a PDF it cannot read, download the PDF and extract its text
  locally before falling back to a stand-in.
- **Reporting.** Answer from the sections that bear on the question, in the reader's language: the
  patient leaflet for the operator, the summary of product characteristics for a clinician's
  detail. Explain a clinical term with no plain equivalent, or leave it out.
- **Citing.** By link and revision date (a text that prints none: say so, with the date you opened
  it); it has no PMID or DOI and is not added to `index.md`, since it is revised often.

A source that doesn't clear the bar doesn't go in a clinician handout, catalogued or not. When in
doubt, leave it out.

## How to use
- `index.md`, `whitelist.txt` and `blacklist.txt` are this instance's own: never published, absent
  until their first entry.
- `index.md` is the running annotated bibliography; start it from `_templates/reference-index.md`,
  whose headings the board reads. Add an entry as you cite a source that is not in it yet, once it
  has cleared the two tiers below.
- Tag each entry by topic so handouts can pull by condition.
- Look here first: a Vetted entry is already verified. Cite into `patients/*/med/handouts/clinician/`
  documents.

## Two-tier verification (a citation must clear BOTH before it is "Vetted")
1. **Tier 1 — find + confirm.** Locate the canonical source (guideline/systematic review/landmark) and
   **confirm its PMID/DOI on PubMed** (the metadata must resolve to the paper you describe). A librarian
   subagent may do the legwork, but the identifier must be machine-confirmed, not remembered.
2. **Tier 2 — curate + lint.** A second pass checks the claim matches what the source says (no
   mischaracterisation — e.g. a citation credited to the wrong author or claiming more than the paper says), assigns the tier, and moves it to
   **Vetted**. The board warns on a cited id that is not Vetted here: before the document is used,
   verify it and add it as Vetted, or drop the claim. Never write a Candidate's id into a person's
   profile, medications or handouts, not even to say it was left out (a handout's fact-check sidecar
   may name one it flags); a choice worth keeping goes in their `med/analysis/`.
- **Superseded sources.** When a newer edition replaces a Vetted entry, keep the old entry in Vetted,
  marked *(superseded by …)* — sealed handouts may still cite it — vet the successor as a new entry,
  and cite only the successor in new work.
- Whitelist/blacklist: `whitelist.txt` (prioritized, open) and `blacklist.txt` (never-cite).
