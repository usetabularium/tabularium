# Source evidence — raw, immutable

This is the shared procedure for filing a person's source documents. It is read from
`_templates/person/med/sources/README.md` in any person's session and is not copied into a person's
folder.

The **evidence layer** (the person's `med/sources/`): original photos, scans, PDFs and their
OCR/transcription, filed there by intake from the person's `med/_inbox/`. Never rewritten, only added
to. Conclusions drawn from it live in the person's `med/analysis/` and `profile.md`.

> **Capturing scans:** see `_templates/person/med/sources/CAPTURE-GUIDE.md` — one document = one scan,
> colour, full resolution, sharp.

## Buckets

| Folder (in the person's `med/sources/`) | What goes here |
|--------|--------------------------|
| `discharge-summaries/` | hospital discharge summaries |
| `diagnoses/` | diagnoses, clinic letters, referrals |
| `labs/` | laboratory results (blood count, chemistry…) |
| `imaging/` | imaging (X-ray, ultrasound, CT, MRI) + reports |
| `prescriptions/` | prescriptions, paper or electronic |
| `receipts/` | receipts, invoices, proof of medicine purchases |
| `other/` | anything that doesn't fit above |
| `interviews/` | operator/patient answers (grade B; **verbatim**) — on-screen answers filed by `tools/interview_capture` (*Filing on-screen answers*, below); sheets filed before 2026-10-19 stay as they are |

## Naming

`YYYY-MM-DD__source__short-description.ext`
e.g. `2026-05-14__clinic__blood-count.pdf`, `2026-05-14__clinic__blood-count.ocr.md`

## Intake checklist (per new document)

**How a document arrives.** In a session, ask the operator to drag the file into the chat (or put it
in the intake tray, if they prefer): the client names its own path, the original. Sending it in this
person's session says whose it is (a session holding several people asks first; recorded as
confirmed only on the operator's explicit word); no session settles identity from a scan. Between
sessions, in a batch, or for a private-mode person it comes through this person's `med/_inbox/`,
where placement says it. **File only original bytes:** copy it unchanged from that path into this
person's `med/_inbox/` with `cp -n` — never re-typed, never re-rendered; `-n` refuses to replace a
pending file, which a plain `cp` does without a word, and scanner names repeat. If the name is
already taken, compare `shasum -a 256` of the two: the same bytes mean it is already there; different
bytes are a second document — copy it under the next free name (`<name>__2.<ext>`, `__3`, …). Say it
is filed only once the copy's hash equals the source's, then continue below.
- **A pasted image** (a screenshot) is the client's own copy, at the path it gives, sometimes reduced;
  file it the same way. A capture of a document's page is an original (A), like a photo; its
  transcription says it is the client's copy of a pasted image. A value it does not show legibly is
  asked for as the document's own file (the portal's PDF, say).
- **Pasted text** is the operator's copy, not the document: quote it as their report (B); to state it
  as fact, ask for the file.
- **No path to copy** (only a rendered page or extracted text is visible): say so in one sentence and
  ask for the file dragged in, or put in the intake tray.
- **A document whose owner is in doubt** (a page seems to be someone else's, or the operator doubts
  it) is a question for the operator, asked in chat, never a refile; a matching name or birth date
  never settles it either way. Until they answer, that document is not ready — not filed, transcribed
  or reconciled — while the rest go on. Remove a copy you made from a chat drag (theirs stays at its
  own path): tray placement must stay their word. Still open when the session ends: an open item — a
  document awaits their word on whose it is; who: the operator; by: the next session — naming no one.
  Their answer names one record (where a name fits two, its handle): this person's, filed
  `--confirmed`; another's, they move it to that person's tray.
- **In a private-mode session a chat attachment is refused** — `tools/private-mode/README.md`.

**0. Private mode?** Read this person's `profile.md` before opening the document, in a step of its
own. If its Identity section marks an identifier as ⟨never-API⟩
(experimental, ADR-0029): **no page image or extracted text may reach any model** until the
local redaction pipeline (`tools/private-mode/` — read its README) has masked the identifier,
its verify loop converged, and the **operator has eyeballed the redacted rasters**. All later
vision/OCR steps then use those rasters only; keep them under the person's
`med/sources/_redacted/<filed-name>/` as the audit trail. Pages that can't be confidently redacted
**wait** — never through unredacted.

1. File the original image/PDF in the right bucket under the naming convention (dated, final
   filename; never an identifier in the name).
2. **Transcribe a scan/photo into a sibling `*.ocr.md`** (any other original: *Less common cases*,
   below) — **vision-primary OCR** (read the image; a
   connector's free OCR can silently drop whole sections) plus an **independent numeric cross-check**
   (Tesseract digits). **A transcription's shape comes from this procedure and the example below,
   never from another person's files.** It opens with front matter (`redacted_in_transcription:` only
   when something was left out, below):
   ```
   ---
   filed_as: 2026-05-14__clinic__blood-count.pdf
   grade: C (derived transcription; cite the original)
   redacted_in_transcription: the contact person's name and phone number
   ---
   ```
   Transcribe faithfully — never "normalise" an odd value; tag per-field
   confidence and flag load-bearing uncertainty `⟨confirm⟩` in the transcription (a flagged value
   that enters the profile or medications carries the dated `⟨confirm by YYYY-MM: …⟩` tag, the only
   form the reminder queue lists). **Withheld from the text layer:** access
   codes, barcode numbers, prescription keys, household contact details, and the name, birth date, ID
   number and contacts of anyone but the person, their clinicians and the operator — write their role
   ("the contact person"), and what the page says of them is transcribed under that role, never as the
   person's; the person's own name stays, even if someone else shares it — name what was left out in
   a `redacted_in_transcription:` front-matter note; the original keeps them, and the digit cross-check
   skips them, never adding them back. This holds for new transcriptions; taking them out of a filed one
   is a correction (`append … retranscribe`, below) whose erratum line names the field, never its value.
   **Pages of one document saved separately** are each filed unchanged with their own transcription,
   never merged: the same date, source and description, ending `-p1`, `-p2`, …; each transcription
   lists the other pages' file names in its body. The image is **grade A**;
   the `.ocr.md` is **grade C** (derived) — cite the image, never the `.ocr.md`. **Safety-critical
   CATEGORICAL fields** — **laterality** (left vs. right), a test **result** (positive vs.
   negative), a device **type**, any drug **identity** whose value
   changes management — also need a **second independent reading surface** (a second high-resolution
   vision pass on the cropped field, and/or explicit operator confirmation): the numeric cross-check
   is blind to words. Until the second read agrees, the value carries
   `⟨confirm by YYYY-MM: categorical — second reading⟩` wherever it is stated.
   (ADR-0023 points 1–3; scanning: `_templates/person/med/sources/CAPTURE-GUIDE.md`.)
3. **Inventory it.** Finish the `.ocr.md` first (hashed with its source). Then
   `python3 -m tools.person_ownership --root . append <handle> add --relpath med/sources/<file>`; no
   `med/MANIFEST` yet: `init <handle>` instead (registers what is on disk). `--confirmed` only on the
   operator's word. Refused: follow its message (after a crash between writes:
   `refresh-checkpoint <handle>`). Other operations: `--help`. Never hand-edit the ledger or
   checkpoint. **A source that is ready is filed and inventoried, never parked in `_inbox/`;** several
   at once go in one call (*Less common cases*).
4. If it changes the clinical picture, update `profile.md` and/or `medications.md`, citing this
   file under "Evidence" / "Source", by `CLAUDE.md` → *Keeping the record honest*.
5. Note the update in the relevant change log, naming this source file.
6. Intake done: offer a handout (`CLAUDE.md` → *Handouts*).

## Correcting a filed transcription

A misread found in a filed `*.ocr.md` is corrected **in that file** too, not only in the profile —
the next reader, the fact-check included, meets the transcription first.
1. **Check the value on the original** (private mode: on the operator-approved redacted raster,
   never the raw scan — step 0), then correct the transcription's text.
2. **Add one erratum line for the correction** under a `## Errata` heading at the end of the file
   (create the heading the first time; earlier lines stay as they are):
   `- YYYY-MM-DD, page N: <as transcribed> -> <as the original reads>` — the day you checked the
   original and the page of it you looked at. A v2 private-mode person: placeholders, never a
   withheld detail.
3. **Re-bind it:** `python3 -m tools.person_ownership --root . append <handle> retranscribe --relpath med/sources/<original>`
   (the original's path, not the `.ocr.md`'s). It keeps the identity status and refuses, writing
   nothing, without a new erratum line or if the original's bytes changed (that is `rehash`). An
   edit without this step keeps L13 red.

## Filing on-screen answers

Answers the operator gives to on-screen questions (the client's question tool) are grade-B evidence.
A tool copies them into the record; the session never types one. **Ask about one person per call** —
a call that mixes two people cannot be filed for either: ask the operator what to do with it. While
the question is not tied to anyone yet, ask anyway: the answers stay in the session, and once the
operator says whose they are, they are filed for that person in the same session (`--confirmed`); if
no one is named before it ends, nothing is filed.
1. **In the same session, before it ends** — the client keeps the answers only in its session
   transcript, which it prunes. An emergency in an answer still comes first (`CLAUDE.md`), and filing
   is a record write, so the session's safeguards come before it. Then
   `python3 -m tools.interview_capture file <handle>` (`--confirmed` when the operator has said whose
   answers these are): it
   copies every answered call not yet filed for anyone into
   `med/sources/interviews/YYYY-MM-DD__interview__on-screen.md` (`--slug` names it otherwise; a taken
   name gets `__2`), inventories it as step 3 does, and lists what it filed. It also completes a
   filing an interruption left half done. Answers given in another session (one opened in a
   worktree, say): pass `--session <its id>` to both `list` and `file`, so the call numbers are
   that session's. A refusal writes nothing and says why; a call whose
   answers cannot be told apart is named, to be asked again, and one the conversation was rewound or
   edited past is not filed — its answers were taken back. An interview file that cannot be read
   back stops it: ask the operator.
2. **Only this person's calls.** In a record that holds one person, the default files every call of
   the session. In a record of several people, `python3 -m tools.interview_capture list` shows the
   calls by number and header: file this person's with `--call N` (repeatable), or with `--all` only
   when every question in this session was about them — never a call about another person
   (whose document is this?). A call filed for one person is never filed for another.
3. **Reconcile** as step 4 does. Quote by copying from the filed answers word for word (an answer, a
   chosen option or a note, never a question), citing the dated file right after it in the same
   paragraph: `"…" (operator, 2026-05-20__interview__on-screen, B)`; a paraphrase stays outside quote
   marks and cites it too. Then `python3 -m tools.interview_capture quotes <handle>` (checks
   `profile.md` and `medications.md`); on a failure, copy the quotation from the file again.
4. `python3 -m tools.interview_capture verify <file>` re-checks a filed copy against the transcript
   while the client still keeps it, and against the file's own hash after.

**Private mode:** never ask on screen for an identifier the profile marks ⟨never-API⟩. If an answer
holds one anyway, do not file that call: ask the operator.

A short answer given in chat rather than on screen is quoted as before, with who said it and when.

## Less common cases

- **Several documents at once, or a late transcription** (written after its original was
  inventoried): `_templates/person/med/sources/topics/batches.md`.
- **An original that is not a page you can open** (too large, an office file, an e-mail, a
  recording): `_templates/person/med/sources/topics/other-originals.md`.
