# _inbox — raw scan staging (transient, not the archive)

This is the shared procedure for a person's intake tray (`med/_inbox/`). It is read from
`_templates/person/med/_inbox/README.md` in any person's session and is not copied into a person's
folder.

Drop scan batches (iOS Notes PDFs, photos) and documents that arrive between sessions in the
person's `med/_inbox/`, then run intake. In an open session, dragging a document into the chat is
enough — except in private mode, where this tray is the only way in.
It is a **doormat**: files are processed *out* of it, not stored in it.

- **One person only.** A person's `med/_inbox/` lives under a single patient — never place another
  person's scans there. (Person-separation, ADR-0002.)
- **Transient.** Intake (the checklist in `_templates/person/med/sources/README.md`) renames each
  file, its bytes unchanged, and **moves** it into the person's `med/sources/<bucket>/` with a sibling
  `*.ocr.md`; then the inbox is emptied. The filed copy in `sources/` is the immutable **grade-A**
  evidence.
- **Not part of the record until filed.** Don't cite anything while it's still in `_inbox/`.
- **An interview sheet** (`*__interview__*__WIP.md`) left here by the retired sheet method is not a
  scan: ask the operator. Once they have filled it, it is filed unchanged as grade B in the person's
  `med/sources/interviews/`.
- **Not a parking lot for filed sources.** A source that is ready to file goes straight to
  the person's `med/sources/<bucket>/` and is inventoried with the ADR-0037 §11 `append` writer. The
  older "park it here until the ownership writer exists" instruction no longer applies.
- Gitignored (the `patients/` rule). Sessions send scans they read to the AI service, and the
  optional offsite backup copies them to your configured sync folder. Capture apps and device
  sync settings may also upload scans; check those settings before scanning health documents.

Flat is fine; optional batch subfolders (e.g. `YYYY-MM/`) just track scanning sessions.
