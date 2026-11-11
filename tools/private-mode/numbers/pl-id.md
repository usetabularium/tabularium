# The Polish number — `pl-id`

Read when: the private-mode line of the person you work for names `pl-id`, or has no exact tag,
before masking or filing for them (`../README.md` → *Which number*). Every rule there still holds;
this page adds what belongs to this number.

## How the tool learns the person's number

It works the number's six-digit prefix out from the date of birth at each run: the number encodes
DOB in its first six digits, century in the month field. Pass `--scheme pl-id` with `--dob`
(required), or `--dob-from-identity patients/<handle>` when the date of birth is kept
(`../topics/pipeline.md` → *Masking*). Its last digit is a check digit: checksum matching has a real
~10% false-positive rate on arbitrary 11-digit windows and is the main over-masking source.

## What the guards search for in the person's notes

Any run of eleven digits, inside a longer run too. Digits split by spaces or dashes are not joined.

## What page masking does not cover

Masking reads text only: a printed code (barcode, QR) that may hold the number is not masked; cover
it by hand before scanning (`../README.md` → *Before you scan*).

## When a run is refused for this number

For the date of birth (missing, not a real date, or outside the years the number covers, 1800 to
2299): ask the operator for the date on the person's papers, never guess it. A kept date of birth is
never asked for in the chat: the operator corrects it, `identity.py set <handle> dob` at their own
terminal.

## Setup beyond the common tools

- Tesseract's Polish language data (`pol`): `bash tools/private-mode/check-setup.sh` reports it and
  names the install command.
- On an install used only for care, nothing else: masking works the number's prefix out from the date
  of birth at each run, so you type no part of it anywhere.
- At intake (`_templates/INTAKE.md` step 4): test whether `checks/PRIVATE-MODE-ID` exists, never
  opening it. It does not on a care-only install: nothing to add, since masking works the number's
  prefix out from the date of birth at each run. Where it does, the operator adds the DOB-derived
  identifier prefix, by hand, to the owner-only file it names, which no session opens or views (no
  screenshot while Finder shows it). In order: the session runs `bash checks/reveal-private-id.sh`,
  which shows that file in Finder; they open it in a text editor, add the prefix as one more
  alternative inside the quotes of `PII_PRIVATE_MODE_ID='…'`, joined with `|`, save and reply; then
  the session runs `bash checks/install-instance.sh care`, which must print `private-mode identifier:
  split verified`, or it names what to fix. The rest of the token registry is brought up to date
  before a relay or an export, not here. Never write a real handle, date of birth, prefix or case date
  into a tracked file.
