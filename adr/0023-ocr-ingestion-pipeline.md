# ADR-0023 — Source-scan ingestion: vision-primary OCR, extract/reconcile split

- **Status:** Accepted 2026-06-21
- **Date:** 2026-06-21
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Bulk intake of phone-scanned medical PDFs, tens to hundreds per person, needed an OCR pipeline. A
pilot batch found these forces:

- the Drive connector caps files at 10 MB, below most full-resolution scans, and returns base64
  into the model context;
- the Cowork sandbox had no root and a short shell-time limit: slow renders, no language OCR pack;
- the connector's own OCR silently dropped clinically load-bearing content (it returned an
  administrative page and missed the result page);
- source images are permanent grade-A evidence, not to be degraded for a tool;
- person mix-up is the #1 risk (ADR-0002), and bulk stresses it;
- one report is sometimes saved as several single-page files.

## Decision

What holds now: the filing procedure, `_templates/person/med/sources/README.md` (step 2 is the
extraction), its `topics/` pages and `CAPTURE-GUIDE.md`, and `CLAUDE.md` → *Keeping the record
honest*. Each point carries the date of the amendment folded into it.

1. **Two stages, kept apart** (2026-06-21).
   - **Stage 1, extraction**, reads the original at full fidelity: Claude vision is the primary
     OCR, with an independent numeric cross-check (Tesseract; digits are script-agnostic). It
     writes only the evidence layer, a `*.ocr.md` per source with provenance, per-field confidence
     and `⟨confirm⟩` flags, never a canonical doc. It was model-tiered (a cheaper model for clean
     bulk, a strong one for handwriting, ambiguity and safety-critical numbers); `CLAUDE.md` →
     *Stance* now starts every helper on an Opus-class model.
   - **Pages of one document saved separately** are each filed unchanged with their own
     transcription, never merged, and each transcription lists the other pages' file names
     (operator, 2026-11-01): merging would file bytes that were never received and break guard
     L13's one-to-one binding of a transcription to its original.
   - **Stage 2, reconciliation**, a separate pass, one person per session, adjudicates the flags
     and updates the profile, medications and handouts.
   - **Roles, not substrates** (2026-10-11 sweep). Stage 1 ran on the host from a `cc-prompts/`
     spec, Stage 2 in Cowork. Cowork is retired (ADR-0030) and `cc-prompts/` frozen (ADR-0019): the
     spec is now step 2, where a flag that enters the record takes the dated tag
     `checks/confirms.sh` lists.
   - **Person separation**, first a scoped folder and branch per run, now follows `CLAUDE.md` →
     *Sessions and people*: one person per session, and a document's owner is the operator's word,
     never inferred from the page. The ownership ledger (ADR-0037, guard L13) checks bytes and
     metadata, not that judgment.

2. **Grades** (2026-06-21). The image is grade A; the derived `*.ocr.md` is grade C and is never
   cited as evidence: cite the image.

3. **A second reading for safety-critical categorical fields** (2026-06-25). The digit check is
   blind to words: a one-word OCR slip can read a safety-critical categorical field as its opposite
   and invert a treatment decision. Laterality, a test result, a device type and a drug identity
   that changes management need a second independent reading (vision on the cropped field, and/or
   the operator), and carry `⟨confirm by YYYY-MM: categorical — second reading⟩` until it agrees
   (the dated form since the 2026-10-11 sweep).

4. **Open the original before a transcription's value enters the record** (2026-09-03). Points 2
   and 3 governed extraction, not the moment a transcription's value is stated or acted on. The
   behavioural eval's first baseline caught that lapse: EV-05b, trial 2, cited a grade-A lab value
   from the `.ocr.md` without opening the scan (ADR-0049, *Findings the contract rests on*). The
   rule is in `CLAUDE.md` → *Keeping the record honest*; in private mode the original is the
   approved masked copy (ADR-0029). Stage 2 is otherwise unchanged.

5. **The proposed transcription guard is declined** (operator, 2026-10-11). The guard, never built
   (every source image has a sibling `.ocr.md`, never cited as evidence), was declined after a
   break test that day: ten synthetic care sessions on Opus 5.5, each given a scan reading 10 mg
   and a transcription reading 100 mg, all opened the scan first, recorded 10 mg as A and never
   cited the transcription. The filing procedure owns the pairing and `CLAUDE.md` the never-cite
   rule; the test stands as core eval case EV-13 (ADR-0049 element 14).

6. **An original that is not a page image** (operator, 2026-10-26). Step 2 covered scans and
   photos. A blind break test of the drag-first intake (2026-10-25, ADR-0029) found no rule for a
   video, which cannot be viewed, or a Word file, where converting it to text might count as the
   forbidden re-rendering. The 2026-10-26 break test matched the intended action in 25 of 25
   synthetic situations over two blind rounds. Decided (mechanics: `topics/other-originals.md`):
   - a reading copy made outside the record is reading, not re-rendering: never filed; only the
     received bytes are filed (A);
   - a Word file is read through macOS's own converter in web-page mode: exact text, tables kept,
     no model reading, so step 2's misread checks do not apply. Converters silently show a tracked
     edit as accepted, so the session first looks for tracked edits and comments and, if any, asks
     which version was issued;
   - any other office file, or a picture in a Word file that matters: the operator's PDF export,
     filed beside the original as an original;
   - private mode never converts an office file, since the converter would hand the identifier to
     the model unmasked; the export is masked like any page;
   - a recording gets no transcription: it enters as the operator's description (B), a value at one
     moment as a screenshot (A).

   Two Codex reviews found the look-inside missing tracked moves, formatting changes and edits
   outside the main text, then, after the fix, table-cell changes; it now counts every revision in
   every part.

## Alternatives considered

- **The connector with base64 in Cowork:** the 10 MB cap blocks most files; kept then for small
  files.
- **Compressing or downscaling to fit:** degrades grade-A evidence.
- **The connector's OCR text as the source:** it dropped load-bearing content; kept only as a weak
  corroborator.
- **All-in-Cowork extraction:** fine for a pilot, but it bloats context, stresses person separation
  at scale and hits the sandbox limits; kept then as the small-batch fallback. Cowork's retirement
  (ADR-0030) ended both fallbacks.
- **A single-surface host script with no review:** no independent re-read of a high-stakes
  extraction.
- **Merging a document's separately saved pages before extraction** (the rule from 2026-06-21;
  reversed by the operator, 2026-11-01): same reason as point 1.
- **For a Word file** (2026-10-26): plain-text conversion puts one table cell per line, so an empty
  cell shifts every later value; pandoc is not part of macOS. The operator first proposed a PDF of
  every Word file as a fixed snapshot, then a screenshot; on the test results they chose the file's
  own text, the export as fallback. A screenshot suits a one-page document but is no default: one
  per page, no text layer, sometimes reduced when pasted.

## Consequences

- Batches scale at full fidelity, with two independent reading surfaces plus the digit check and
  the operator; the costs are the handoff between stages and extraction resting on step 2's spec.
- Verified by `checks/check.sh` (L13 binds each transcription to its original) and EV-13.
- Capture guidance for the operator: `CAPTURE-GUIDE.md`.
