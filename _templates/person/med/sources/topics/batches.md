# Filing — several documents at once, late transcriptions

Read when: you file several documents for one person in one pass, bind a transcription written after
its original was inventoried, or a ledger refusal names a late transcription. The filing procedure is
`_templates/person/med/sources/README.md`; this page is read from here, never copied into a person's
folder.

- **Several documents arriving together** are inventoried in one call, one `--relpath` each:
  `python3 -m tools.person_ownership --root . append <handle> add --relpath med/sources/<a> --relpath med/sources/<b>`.
  All are written or none: anything still not inventoried afterwards refuses the whole call. Never
  move one back to `med/_inbox/` to get the other through. A refusal that finds other files in the
  folder not inventoried yet lists them and prints this call with all of them, recorded unverified,
  and — if you passed `--confirmed` — one `confirm` per file you named, never for the others; one may
  be another session's, still being filed — then wait for that session instead of logging it.
- **A first transcription written after its original was inventoried** binds with
  `python3 -m tools.person_ownership --root . append <handle> transcribe --relpath med/sources/<original>`
  (the original's path; repeat `--relpath` for several, as `retranscribe` takes them too). The
  transcription sits beside its original with the same name stem; its `filed_as:`, when it has one,
  names exactly that original's file name — L13 reds one that names another, repeats, or lists. The
  op keeps the original's record and identity, and writes nothing when the transcription is missing,
  misnamed or already bound (a correction is `retranscribe`: the filing procedure → *Correcting a
  filed transcription*).
- **Bind a late transcription or a correction right after writing it, before filing new arrivals:**
  every op is checked against the whole folder, so one kind left pending refuses another kind. Several
  of one kind go in one call (arrivals above; `transcribe` and `retranscribe` repeat `--relpath` too).
  Only if two *different* kinds are pending already, move the file nothing binds yet (the new arrival,
  or the late transcription) to the person's `med/_inbox/`, run the other op, then put it back and
  run its own.
