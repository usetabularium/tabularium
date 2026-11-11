# Filing — an original that is not a page you can open

Read when: an original is too large to open, or is not a scan, a photo or a PDF — an office file, an
e-mail, a recording. The filing procedure is `_templates/person/med/sources/README.md`; this page is
read from here, never copied into a person's folder.

The original is filed unchanged, as the procedure says, and is grade A. A reading copy you make of it
outside the record (a page image, extracted text) is reading, not re-rendering: never filed, deleted
when done. An original you do not read takes its dated name from its export or from the operator.
A PDF export the operator makes is filed beside its original under its own name
(`<name>-export.pdf`, so its transcription binds to it), an original (A) noted as their export, and
transcribed and opened as any PDF. While one is awaited, what the operator reads out or pastes is
their report (B).

- **Too large to open** (the file reader refuses it, often above ~10 MB):
  `.venv-render/bin/python -m tools.original_view <handle> --relpath med/sources/<file> --out <scratch folder> [--page N]`
  writes a light JPEG of one page into a scratch folder outside the repository; open that, then
  delete it. It refuses a private-mode person's originals outright: for them the approved redacted
  rasters (the procedure's step 0) are what you read.
- **A Word file** (`.docx`): look inside first.
  `unzip -p <file> 'word/*.xml' | grep -c -E '<w:(ins|del|moveFrom|moveTo|cellIns|cellDel|cellMerge|[A-Za-z]+Change)[[:space:]/>]|w:author='`
  counts tracked revisions in every part, footnotes, headers and table cells included (every
  revision names its author), and `unzip -Z1 <file>` lists a `word/comments…` part when it has
  comments. Any found, or the look fails: ask the operator which version was issued, or for a PDF
  export that shows them, and no value from the file enters the record until they answer; an edit or comment still open is a question for its clinician (open
  items). Otherwise read it through macOS's own converter, `textutil -convert html -stdout <file>` —
  exact text, tables kept, so step 2's digit cross-check and second reading, which guard a misread,
  do not apply; transcribe from that output, and convert again to open the original for step 4. The
  transcription says that pictures, headers and comments are not in the text; one that matters is
  asked for as a PDF export, not pulled out of the file.
- **Any other office file** (a spreadsheet, an e-mail, an older word format): ask the operator for a
  PDF export from the app that opens it.
- **Private mode:** never convert an office file; its PDF export comes through the tray and is
  masked like any page. The original is filed, never opened.
- **A recording** (video, audio): no transcription — nothing here plays it, and it is never opened, so
  private mode adds no step. What it shows enters the record only as the operator's description (B),
  citing the file. A value shown at one moment (a monitor's reading) is asked for as a screenshot of
  that moment, filed as a capture (A).
