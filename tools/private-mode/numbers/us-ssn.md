# The US number — `us-ssn`

Read when: the private-mode line of the person you work for names `us-ssn`, or has no exact tag,
before masking or filing for them (`../README.md` → *Which number*). Every rule there still holds;
this page adds what belongs to this number.

## How the tool learns the person's number

The number holds no date, so it is read once from one of the person's pages and kept in their
identity file: `../topics/kept-details.md` → *A number with no date inside*. Then pass
`--scheme us-ssn --number-from-identity patients/<handle>`. Masking searches that number whole,
through OCR's misreads and up to two wrong digits, and, under the default rules, its last four when
printed masked or beside a recognised label.

## What the guards search for in the person's notes

The recorded number in the person's Markdown outside `nmed/`, with up to two separators between its
digits; and, in the notes the guards scan, any nine digits written in groups of three, two and four
with separators between them. Neither searches for the last four alone or another bare run of nine
digits (a phone or record number has that shape).

## What page masking does not cover

Of this number: its last four printed neither masked nor beside a label, and a printed code (barcode,
QR) that may hold it. Cover those by hand before scanning (`../README.md` → *Before you scan*).
Medicare and other insurance member numbers, names and addresses are not masked either; covering
them is the operator's choice.

## When a run is refused for this number

- "none is recorded for us-ssn": check the run passed `--number-from-identity patients/<handle>`; if
  it did, read the number first (*How the tool learns the person's number*); the pages wait.
- The reading refuses when the line names more than one number that holds no date: the operator
  decides which is read, the tag names that one alone while it is read, then the full tag returns.

## Setup beyond the common tools

None for the number: its row's language is English, which every private-mode install has; the
person's documents may need another (`../topics/setup.md`).
