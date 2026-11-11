# Private mode — details kept from the AI service

Read when: a private-mode person's private-mode line carries the kept-details sign
`⟨withheld:details-kept⟩`, the operator is choosing what to keep, or a number's page sends you to
*A number with no date inside*. Every rule in `tools/private-mode/README.md` still holds; this
doc adds to it.

The designated number is always kept from the AI service (the masking pipeline). Besides it, the
operator chooses per person which routine details stay on the Mac; sessions see the handle, the age and
placeholders instead. The person's identity file is the one record of that choice: a kind of detail with
a value recorded there is kept, and no identity file means nothing besides the number. While anything is
kept, the identity tool keeps the sign `⟨withheld:details-kept⟩` on the profile's private-mode line, so
every session that reads the profile knows; never write or remove the sign yourself.

## In a session for a private-mode person

- **Run `identity.py status <handle>` once**: it names the kinds of detail kept, as counts, never a
  value. Kinds it does not name are written as usual, the number aside.
- Write a **placeholder** wherever a kept detail would go — profile, medications, analyses,
  transcriptions, handout sources: `⟨withheld:patient-name⟩`, `⟨withheld:date-of-birth⟩`, … (the list
  below). Relatives appear by role ("the sibling") when their names are kept.
- **Never ask the operator to type a kept detail into the chat**, and never copy one there; the form
  takes them, in the operator's own editor (*Choosing what to keep*). What the operator types of their
  own accord goes as typed (`/private` restates the posture).
- **Age**, when the date of birth is kept: run `identity.py age <handle>` and write the age with its
  reference date. When it is not kept, the profile shows the date as usual.
- Scans still show their details once, at intake, unless the operator covers them before scanning
  (`../README.md` → *Before you scan*); the transcription uses the placeholders.
- A red from the residue guard names the kind of detail and the kind of file, never the file: replace
  it with its placeholder; a value inside a file name or link needs the file renamed through the
  ownership ledger first, then `identity.py swap <handle>`.

## Choosing what to keep

The operator's decision, in one care edit session, with the private-mode marker already on the
profile (the marker is what makes the read guard protect the person's folder whole):
1. Board green, then the snapshot.
2. Ask in one tick-list question which details to keep from the AI besides the number: the person's
   names, date of birth, relatives' and contacts' names, other ID or document numbers, addresses,
   phones, e-mails, case, visit and order numbers. Nothing ticked: nothing else is kept, and setup ends
   here. A kind is kept only once a value of it is recorded: a ticked kind left blank in the form keeps
   nothing yet, so add the value through a later form when it is known. When the person's names are kept, the private-mode line records, in words, whether the handle
   was in use before (an existing person's was, its exposure recorded once; an alias given at intake
   was not).
3. The session runs `identity.py form <handle> --keep <kinds>`, the ticked kinds by the names under
   *Commands*: it writes a form holding slots for those only and opens it in TextEdit. The operator
   replaces the slots, saves, closes and says so; nothing is typed into the chat. The session then runs
   `identity.py take-form <handle>`, which records the details, deletes the form, swaps them for
   placeholders in the profile and medication list and puts the sign on the private-mode line — or
   changes nothing and names the line to correct. A name the handle itself spells cannot be kept (every
   path names it); the tool refuses it. Never link, open or
   copy the form, or any file named like it, yourself; a stray copy is the operator's to delete. Ask
   them to close its window first: an editor left open can write the form back when closed, and
   `status` then says a form is waiting, which `take-form` clears. A form the operator does not want
   (never filled, or given up on): `discard-form <handle>` deletes it unread, at their word. An
   operator who prefers the terminal runs `identity.py set <handle>` there instead (each value typed
   twice); the session then runs `identity.py swap <handle>`.
4. If it refuses on a file reference, nothing is recorded and the form stays: rename that file through
   the ownership ledger, update the reference, then run `take-form` (or `swap`, after `set`) again.
5. Only where `checks/PRIVATE-MODE-ID` exists (test it, never open it; a care-only install has none and
   skips this step). Outside any session, the operator follows `checks/topics/relay-and-export.md` →
   *Kept details: moving a person's tokens*: paste the current registry block first, then move the
   tokens and check `split verified` in both checkouts. For a new person, the tokens go straight into
   the protected private-mode file during that procedure: add their name tokens and, when the date of
   birth is kept, the date as `YYYY-MM-DD`, `DD.MM.YYYY` and `DD-MM-YYYY` to `PII_PRIVATE_IDENTITY`,
   creating that line if it is missing.
6. Board green, `status` names no form waiting; the session writes the age if the date of birth is
   kept, and says what changed in the profile's change log.

**Later**, the same steps with only the new kinds or values: a later form adds to what is recorded.
Each value counts from the day it was recorded, so notes written before it stay as they are.

## A number with no date inside (ADR-0074)

Masking cannot work such a number out from the date of birth, so it searches the person's own number,
which the tool reads from one of their pages. These steps are for a listed number whose page sends you
here; a number not on the list is covered by hand and masked with `--covered-by-hand`, with none of
the steps below (README → *Which number*). They need the private-mode marker and the exact tag
naming that number, but no kept-details sign: a person with nothing else kept has an identity file
holding only the number.
1. The operator names a PDF in the person's intake tray that prints the number clearly beside its
   label. The session runs `identity.py form <handle> --read-number patients/<handle>/med/_inbox/<file>.pdf`
   (`--page N` for another page than the first; no `--keep`). The tool reads the number beside the
   label, writes it into the form and saves a picture of that spot beside it, both refused to sessions
   by name, and opens both. No single number beside a label: it refuses; ask for another page.
2. The operator compares the number in the form with the picture, corrects a digit if one differs,
   saves and closes both windows. That comparison is the safeguard: the check below allows for OCR's
   misreads, so it also lets a slip of one or two digits through.
3. The session runs `take-form`: it records the number only if masking finds it on that page again,
   then deletes the form and the picture; otherwise it names the step, and the form stays for
   correction (or `discard-form`, which deletes the picture too). A new reading of the same number
   replaces the earlier one. The number is kept always, so it carries no date.
4. Masking then runs with `--number-from-identity patients/<handle>`; without a recorded number it
   refuses and the pages wait.

While it reads a page the tool keeps the page and its text in a private temporary folder, deleted when
it finishes; only a forced quit or a power cut leaves one behind.

## What exists

- **The identity file** `.never-api-identity.json` in the person's folder holds the kept values by
  kind, each with the date it was recorded: the person's names, the date of birth, relatives' and
  contacts' names, other ID and document numbers, addresses, phones, e-mails, case, visit and order
  numbers. The operator fills it through the form or at their own terminal, never through a session.
  The form has no quotes, so an editor's curly ones and an apostrophe in a name change nothing. The
  date of birth goes on two lines of the form and counts only when they agree: masking uses it to
  find a number built from the date of birth. At the terminal each value is typed twice without echo. The file is
  owner-only and replaced atomically. The designated identifier is never typed here: a value
  holding a run in its shape (the number list's residue shape for the schemes the profile's tag names)
  is refused, so a phone or a case number is typed with its spaces. The one exception is a number with
  no date inside, which the tool reads from a page (*A number with no date inside*). A file in the format from before
  values carried their dates is refused: the operator deletes it and fills in the form again.
- **Who reads it:** local tools only, masking included (`--dob-from-identity` when the date of birth is
  kept, so no session writes it). The read guard refuses it and the form to every session by name —
  anywhere, existing or not, snapshot copies and an interrupted write's leftover included — and any
  existing file whose name holds `never-api-identity`, so an editor's backup or a copy of either is
  refused too (control C1). `checks/snapshot.sh` banks it beside the profile under the same name.
- **Placeholders** stand where a kept value would: `⟨withheld:patient-name⟩`,
  `⟨withheld:date-of-birth⟩`, `⟨withheld:other-name⟩` (a relative or contact, named by role around
  it), `⟨withheld:id-number⟩`, `⟨withheld:address⟩`, `⟨withheld:phone⟩`, `⟨withheld:email⟩`,
  `⟨withheld:case-number⟩`. The swap writes `⟨withheld:national-number⟩` where a recorded number with no
  date inside stood; like any designated number it never belongs in a handout, whose renderer refuses it.
- **The swap** (`take-form`, or `swap` after a terminal entry) replaces the kept values in the working
  record — `profile.md` and `medications.md` — with their placeholders and writes the sign, inside a care
  edit session after its snapshot; it prints counts only. Everything else stays as it is: originals,
  transcriptions, analyses and sealed handouts written before a value was recorded are history.
- **The residue guard** (`scan`, run by guard L10; control C2) reds a kept value in the working record
  always, and in any other Markdown of the person's dated on or after the day that value was recorded:
  a transcription or Markdown source by the ownership ledger's filing date (so an old letter
  transcribed later is covered, and a future-dated one filed earlier is not), a sealed handout by its
  seal, anything else by the later of the latest date in its path (file or encounter folder) and when it
  was last written, an undated file by when it was last written. `nmed/`, the roster and `_shared/` are out of its scope. It matches whole
  recorded values, accents and Markdown emphasis aside: names in either order, the date of birth in its
  numeric printed forms, phone and other numbers with any separators, the address and e-mail as
  recorded. Other forms are not recognised: record each variant you know of as a further value
  (`../README.md` → *What it does not protect*). Output is category-only; a verified namesake line takes
  L10's dated `⟨not-an-id: verified YYYY-MM-DD⟩` waiver. A value inside a file name or any Markdown
  link target gets its own next step — rename the file through the ownership ledger, then update the
  reference — and the swap refuses, changing nothing, until then. It also reds an identity file whose
  profile lost the marker, an identity file that keeps something while the sign is missing (run `swap`),
  the sign with nothing kept, and the sign or any placeholder in the profile or medication list whose
  identity file is missing (restore it from the latest snapshot), so a lost file never switches the
  scan off. Records
  the one-time ledger migration wrote carry no filing date (they fall back to the name's date); a
  sealed unit's fact-check sidecar shares its seal's date.
- **Handouts**: the source carries the placeholders; the renderer's draft shows the handle, its seal
  fills in the recorded values locally and seals them (guard L15 binds the delivered bytes), with no
  plaintext fallback and no HTML preview; the read guard refuses the final to sessions for any person
  with an identity file, and the operator looks at it before handing it over
  (`_templates/HANDOUT-RULES.md` → *Kept details*).

## Commands

```
python3 tools/private-mode/identity.py --root . status <handle>         # what is kept, as counts
python3 tools/private-mode/identity.py --root . form <handle> --keep patient_names,dob,other_names,id_numbers,addresses,phones,emails,case_numbers
python3 tools/private-mode/identity.py --root . form <handle> --read-number <pdf> [--page N]   # ADR-0074
python3 tools/private-mode/identity.py --root . take-form <handle>       # the filled form -> the identity file, then the swap
python3 tools/private-mode/identity.py --root . discard-form <handle>    # deletes a waiting form unread
python3 tools/private-mode/identity.py --root . set <handle> [<kind>]    # the operator's terminal
python3 tools/private-mode/identity.py --root . swap <handle>            # in a care edit session
python3 tools/private-mode/identity.py --root . age <handle>
python3 tools/private-mode/identity.py --root . scan                     # guard L10 runs this
```

`--keep` takes the ticked kinds only, joined with commas. `form --no-open` writes it without opening
it. `age` prints today's age with the date and nothing else — years and months; months and whole weeks
under two; days in the first month, where care needs them (and where they fix the date of birth). It
takes no other reference date. None prints a value; exit 1 is `scan` finding residue, 2 a refusal with
its reason, 64 a bad invocation. Self-test: `python3 tools/private-mode/test_identity.py` (synthetic
persons).
