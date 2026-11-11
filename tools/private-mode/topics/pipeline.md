# Private mode — the masking pipeline

Read when: you are about to run `redact_ids.py`, `approve_redaction.py` or `verify_approved.py`,
present the operator eyeball gate, or file a masked page. The rules every private-mode session keeps
— what may reach a model, the gate, the local-only map, containment — are in
`tools/private-mode/README.md`; this doc does not restate them.

## Requirements

All local; no network. `bash tools/private-mode/check-setup.sh` names each missing tool with its
install command (the list: `tools/private-mode/topics/setup.md`); poppler's optional
`pdfinfo` cross-checks the page count. `redact_ids.py` refuses to start (exit 64) if `pdftoppm`,
`tesseract` or ImageMagick is missing from `PATH`.

## Run states

Every invocation is a state transition, not a fire-and-forget script:

```
NEW  --[redact_ids.py]-->  LOCALLY_PROCESSED  -->  AWAITING_OPERATOR  --[approve_redaction.py]-->  OPERATOR_APPROVED
```

- **`redact_ids.py`** (→ AWAITING_OPERATOR) gives each run a fresh `run_id` and run-scoped
  `--render`/`--work` subdirectories, so a stale or shorter rerun cannot resurface a prior run's
  pages. Each document's redacted set and hash-manifested `manifest.json` are staged privately, then
  **atomically promoted** into `--redacted/<doc>/`; a pre-existing `--redacted/<doc>/` is first
  renamed aside to `--redacted/.superseded/`, **never deleted**.
- **`approve_redaction.py`** (→ OPERATOR_APPROVED) is a separate, explicit command. Before copying
  anything it runs the **strict, versioned manifest validator** (`redact_ids.validate_document_manifest`;
  supported schema/kind/tool, `state == AWAITING_OPERATOR`, doc id matching the directory, a
  non-empty contiguous unique page set `1..N` with `n_pages == len(pages)`, allowed vocabulary only,
  no unknown fields, no symlinked/extra/missing page artifacts; an unknown schema version is rejected
  **closed**), then re-hashes every page raster against the manifest — an artifact changed since it
  was eyeballed is **rejected**. It refuses a document carrying any unresolved fail-closed flag
  unless given `--accept-flagged`, which **requires an explicit `--doc`**; `--accept-flags FLAG,FLAG`
  may pin the exact flag set, and an acknowledgement that does not exactly cover the manifest's
  current flags is rejected. The set is **copied**, not moved (the AWAITING_OPERATOR set stays as the
  audit trail of what was eyeballed), into `--approved/<doc>/` with a self-verifying, byte-bound
  `approval.json`, by a rollback-safe stage-then-promote that never loses the last known-good set.
- **`verify_approved.py`** is the mandatory pre-consumption integrity gate. It strictly validates the
  attestation, binds it to the **current** `--redacted` manifest generation (a later failed/HOLD
  rerun revokes an older approval), refuses a symlinked directory, approval or page, rejects any
  on-disk set that is not exactly attested (missing/extra/stray), and **re-hashes every page**.

Consuming approved pages:

- **Programmatic consumers use `verify_approved.load_verified_pages(approved_root, redacted_root,
  doc=None)`** — any future in-repo model/vision caller must. It verifies and *reads* in one step:
  each page opened once (no-follow/no-block), fstat'ed regular, read under explicit size bounds and
  hashed over the very buffer it returns, so no path is reopened after verification; it fails closed
  (`ConsumptionError`, category-only).
- **The CLI is diagnostic only**: its exit 0 detects tampering at check time, never across a later
  reopen. In the interactive workflow (eyeball → assistant reads the pages), serialize the local
  operation, use only the printed page set, and re-run the gate immediately before each pass — that
  window is owned by this discipline, not by code.

## Masking — `redact_ids.py`

```
python3 tools/private-mode/redact_ids.py \
  --inbox  patients/<handle>/med/_inbox \
  --render <workdir>/render --work <workdir>/work \
  --redacted patients/<handle>/_redacted \
  --log <workdir>/run-log-<fresh-name>.json \
  --scheme <KEY[,KEY]> \
  --dob YYYY-MM-DD \
  --label-token '<the ID label exactly as printed on the documents>'
```

- **Image originals** (a JPEG or PNG from a phone or a scanner): `redact_ids.py` reads only `*.pdf`,
  so convert each one into the **same inbox** first — `magick patients/<handle>/med/_inbox/<photo>.jpg
  patients/<handle>/med/_inbox/<photo>.pdf` (or `sips -s format pdf <photo>.jpg --out <photo>.pdf`).
  The PDF stays in the protected lane; the image stays as the untouched original. The read guard
  refuses a conversion that prints or writes anywhere else.
- `--scheme` or `--covered-by-hand` is required. First check the private-mode tag: if it names the key
  `unlisted`, pass `--covered-by-hand`: the operator covered that number by hand on every page before
  scanning (README → *Which number*); the tool refuses it unless the person's tag names `unlisted`,
  and in place of a number the tag names. Ask on screen first whether every page in the tray was
  covered, any put there before covering began included. For `unlisted` alone it stands in place of
  `--scheme`, with `--lang` set to the documents' language. Otherwise, and beside a listed key,
  take the KEY from the `TAG` line that `python3 tools/private-mode/id_schemes.py patients/<handle>/profile.md`
  prints (the tag's keys, or every row of the number list when there is no tag; README → *Which
  number*), never by eye, leaving out `unlisted`. If it prints anything else, or the board reports the tag as unreadable,
  fix the line before running the tool; never pick a scheme by guess. Pass every KEY the tag names, joined with commas: one
  run masks them all. The tool reads the same tag and refuses, before any page, a run that leaves one out
  (`unlisted` counts as named by `--covered-by-hand`), or whose profile or tag it cannot read; an extra key
  only masks more. In a care folder with people it also refuses an `--inbox` that is not one of their trays
  (a folder inside a tray is fine): put the pages in the person's tray. The keys also pick `--lang`, the OCR language data, unless that is given; the tool
  refuses at start when one is not installed, and `check-setup.sh` reports which.
- `--dob` gives the date masking uses to find a number built from the date of birth, making
  detection nearly deterministic; the number's page says whether it is required. **For a person who keeps the date of birth from the AI, never write the date: pass
  `--dob-from-identity patients/<handle>` in its place**; the tool reads it from the identity file and
  prints it nowhere.
- `--number-from-identity patients/<handle>` (required for a scheme whose number holds no date): the
  tool reads the person's own number from their identity file (`topics/kept-details.md` → *A number with no
  date inside*) and searches it whole, through OCR's misreads, in place of that scheme's shape rules;
  without one it refuses and the pages wait.
- `--label-token` enables the third detection rule (numeric tokens near the printed label). It is
  CLI-only by design: tracked files must stay free of the label string (an instance may list it as a publish-firewall token).
  It masks every number near the label, a date printed there included: a date-shaped word can be a
  piece of an identifier OCR broke up, so the tool never frees one on its own.
- `--rules prefix,checksum,label,lowconf` (default). Over-masking is the chosen failure direction — the gate
  and the untouched original make it recoverable; an under-mask is not, once bytes leave the machine.
  For **gate-fix reruns**, once the operator has confirmed which hits were false positives, use
  `--rules prefix,label,lowconf`: for a number with a checksum, checksum matching also masks unrelated
  numbers (the number's page says how often).
  `lowconf` masks and holds identifier-shaped words OCR read below its confidence floor, and what only a
  second read, on a darkened copy of the page, can see (faint ink OCR otherwise reads no word of), so
  each page is read twice. The page's own paper sets how dark the copy goes, the copy is deleted once
  read, and a page that is mostly dark, or a copy more than a quarter dark, holds; leave `lowconf` out
  only after the operator has checked on the original that such a box holds no identifier.
  **A rerun that drops `checksum` frees every number only that rule caught.** If a number built from the
  date of birth is on the page and only the checksum rule masked it (no `id-prefix` reason on that page), the
  date of birth used is wrong: correct it first (a kept date of birth: the operator, `identity.py set <handle> dob`
  at their own terminal), never rerun without the checksum rule.
- `--dpi 300` default; aim for ~2× the source scan's density (phone captures are often ~72 ppi →
  150 dpi is enough; beyond 2× adds blur, not detail).
- `--log` must be a **fresh path that does not already exist** (reuse → exit 64); name it per run.
- `--inbox`, `--render`, `--work` and `--redacted` must be **distinct and non-nested** (exit 64
  otherwise): `--redacted` sits outside the intake dir (e.g. `patients/<handle>/_redacted`), never
  inside `_inbox/`.
- `--render`/`--work` are **roots**; each run writes its own `<run_id>/` there. Delete them
  periodically — disposable local intermediates holding raw pages/text, never model-visible or
  evidence.

`redact_ids.py` prints the opaque doc id; it is the directory name under `--redacted`.

## The operator eyeball gate

Present a per-page listing (masks, reasons, flags) and open `_redacted/` for a human pass. Typical
outcomes:

- *page clean* → approve (`approve_redaction.py`, no flags to accept);
- *"no identifier on this page"* → checksum hits were coincidences; rerun that page with
  `--rules prefix,label,lowconf` to unmask (operator word is authoritative — record it);
- *"over-masked"* → rebuild that page keeping only prefix, label and low-confidence hits; eyeball
  again;
- *"a date beside the label was masked"* (`id-label-proximity`) and the record needs it → the
  operator checks on the untouched original that the box holds only the date, and that neither its
  digits nor any number beside it are part of the identifier. Then rerun that document alone with
  `--rules prefix,checksum,lowconf` — the label rule off, the checksum kept. The label rule is then
  off for every page of that document, so eyeball every page again: every occurrence of the
  identifier must still be masked. `prefix,label,lowconf` cannot free the date: it keeps the rule
  that masked it;
- *`OSD_UNRELIABLE`* → the operator confirms the page's orientation explicitly; never assume
  orientation 0 (it also fires when orientation detection suggests a turn it is unsure of, left
  unapplied: a sideways page reads badly, so check its masks with care);
- *`LOW_CONFIDENCE_CANDIDATE`* → OCR read an identifier-shaped word too faintly to trust, or only on
  a second, darkened read of the page, and it was masked: check that box on the untouched original; if it holds no identifier and hides something the
  record needs, rerun without `lowconf`;
- *`DARKENED_READ_UNREADABLE`* → the second, darkened read came out dark (dark paper, a dark photo), so
  faint ink on that page went unchecked: the operator looks over the untouched original for a faint
  number left visible on the masked page. None → approve with `--accept-flagged`; one → a lighter scan
  or photo of the page, then rerun;
- *covered by hand* (`--covered-by-hand`) → the tool looked for no unlisted number: the operator
  checks on every page that their covering hides it and any printed code (barcode, QR) that may hold
  it; a page where either shows is covered and scanned
  again, then rerun;
- *a fail-closed flag, and the page is genuinely fine as masked* → approve with
  `--accept-flagged`, which records that acknowledgement in `approval.json`.

Approval is the explicit, recorded hand-off point.

**Every rerun names its rules.** The run log keeps the `--rules` set; the session also writes it,
and which rule was left out and why, into the filed transcription's masked-region note and the
change-log line ("rerun without the label rule: the operator confirmed the box held only the
examination date").

## Approval and verification

Once the operator has eyeballed every masked raster under `--redacted/<doc>/`, run the explicit
**approval** step — nothing is eligible for a model/vision pass before this:

```
python3 tools/private-mode/approve_redaction.py \
  --redacted patients/<handle>/_redacted \
  --approved <workdir>/approved \
  [--doc <opaque-doc-id>]      # doc-<16 hex>; default: every document with a manifest under --redacted
  [--accept-flagged]           # approve a document that still carries a fail-closed flag; REQUIRES --doc
  [--accept-flags FLAG,FLAG]   # optional: the exact flag set being acknowledged (must cover it exactly)
```

Then — **mandatory, immediately before any model/vision pass** — run the integrity gate against both
the approval and the current redacted generation:

```
python3 tools/private-mode/verify_approved.py \
  --approved <workdir>/approved \
  --redacted patients/<handle>/_redacted \
  [--doc <opaque-doc-id>]      # default: verify every approved document
```

## Exit status

`redact_ids.py`:

| Exit | Meaning | State reached |
|---|---|---|
| 0 | Clean local processing — no flag or error fired; never a proof that no identifier survived | `AWAITING_OPERATOR` (not approval) |
| 10 | HOLD — a page carries a fail-closed flag (`LABEL_NO_CANDIDATE` / `NEAR_EMPTY_OCR` / `MASK_VERIFY_FAILED` / `CHECKSUM_ONLY_EXPECT_FALSE_POSITIVE` / `OSD_UNRELIABLE` / `LOW_CONFIDENCE_CANDIDATE` / `DARKENED_READ_UNREADABLE` / `BARE_NUMBER_ONLY`) | `AWAITING_OPERATOR`, never clean |
| 11 | ERROR — a hard failure (render / page-count mismatch / a tool step / an internal `PROCESS_ERROR`) | affected page(s) **absent** from `--redacted/<doc>/` pending a rerun |
| 12 | Empty input — `--inbox` held zero `*.pdf` files | an error, not a successful zero-document run |
| 64 | Invalid invocation — bad CLI args or a missing required executable | nothing processed |
| 65 | Run-state error — e.g. a run-scoped directory collision (should not happen) | investigate the host |

`approve_redaction.py`:

| Exit | Meaning |
|---|---|
| 0 | All requested documents approved -> `OPERATOR_APPROVED` |
| 20 | Rejected — artifact hash mismatch vs. the manifest (approval-state-forgery defense fired) |
| 21 | Rejected — unresolved fail-closed flag(s) not (exactly) acknowledged |
| 22 | Rejected — a hard processing error on a document/page (never approvable), **or** the approval failed on the host (staging, promotion/copy, unexpected filesystem error); nothing written for that document either way |
| 23 | Nothing to approve — no `manifest.json` under `--redacted` |
| 24 | Rejected — manifest failed strict, versioned schema validation (unknown version rejected closed) |
| 64 | Invalid invocation (incl. `--accept-flagged` without `--doc`, a non-opaque `--doc`, symlinked root) |

`verify_approved.py`:

| Exit | Meaning |
|---|---|
| 0 | Every requested document matched its approval and current redacted generation at verification time |
| 30 | Approval attestation missing / unreadable / failed strict schema validation |
| 31 | A page's bytes do not match the sealed hash (tamper/swap after approval) |
| 32 | A page is missing / a symlink / non-regular, or an unexpected extra file is present |
| 33 | Nothing to verify — no `approval.json` under `--approved` |
| 64 | Invalid invocation (incl. a non-opaque `--doc`, symlinked/nested `--approved` or `--redacted`) |

Any flag or document-level error makes the **whole invocation** exit nonzero; no `redact_ids.py`
exit implies `OPERATOR_APPROVED`.

## Recovery

- **HOLD (exit 10):** eyeball the flagged page(s) in `--redacted/<doc>/`. A false positive (e.g.
  `CHECKSUM_ONLY_EXPECT_FALSE_POSITIVE`, or a `LABEL_NO_CANDIDATE`/`MASK_VERIFY_FAILED` page the
  operator confirms is fine as masked) → approve with `--doc … --accept-flagged`. Otherwise rerun,
  optionally narrowing `--rules` (e.g. `prefix,label,lowconf` drops noisy checksum hits, never the
  person's own number: see `--rules` above); the rerun
  supersedes the held set safely.
- **ERROR (exit 11):** the run log (`--log`) gives the failing document's `error`/`error_stage`/
  `error_reason` (or the page's `error_stage`/`error_reason`/`error_type`) — stage and category
  only, never OCR text, digits or argv. Fix the cause (missing tool, corrupt PDF page, disk full)
  and rerun; a failed page was never published, so a rerun cannot double-publish or mix runs.
- **Rejected approval (exit 20/21/22/24):**
  - *20* — an artifact changed after it was eyeballed: rerun `redact_ids.py` fresh and eyeball the
    new set before approving; do not investigate the old bytes.
  - *21* — review the flagged pages, then rerun more narrowly or approve with
    `--doc … --accept-flagged` (optionally pinning `--accept-flags`).
  - *22* — the printed line says which: `…processing error…` → fix the cause and rerun
    `redact_ids.py` first; `could not create the approval staging area`, `promotion failed (…)` or a
    top-level `ABORT: an unexpected filesystem error…` → no redaction rerun, only a retry once the
    filesystem problem is fixed.
  - *24* — malformed, unknown-version or forged manifest: never hand-edit it; rerun `redact_ids.py`.
- **Failed verification (exit 30/31/32):** send **no** page of that document to a model/vision
  pass; re-approve from a fresh `redact_ids.py` run.
- **Superseded sets** in `--redacted/.superseded/` (and `--approved/.superseded/`) keep every prior
  attempt as `<doc>__<supersession-timestamp>-<pid>-<hex>` — **not** the `run_id`; the
  `manifest.json` inside names the run. Prune them by hand when the history is no longer needed;
  they are local intermediates, not evidence.

## Filing — provenance conventions

- Every `.ocr.md` records the original inbox filename; that it was transcribed **from the redacted
  raster**; the identifier line as
  `⟨redacted locally before model pass — not recorded, operator decision YYYY-MM-DD⟩`;
  and every masked region as `⟨masked⟩` with what it covered (label vs over-mask).
- Keep the redacted rasters — **the exact bytes the model saw** — as the audit trail under
  `med/sources/_redacted/<filed-name>/<filed-name>__page-NN.png` (date-named for the L6
  source-naming guard), and **inventory each in the ownership ledger**, since everything under
  `med/sources/**`, nested subdirectories included, is in L13's scope (ADR-0037):
  `python3 -m tools.person_ownership --root . append <handle> add --relpath med/sources/_redacted/<filed-name>/<filed-name>__page-NN.png`
  — or L13 reds it as un-inventoried on the board. Delete the `--render`/`--work`
  intermediates (they contain raw pages/text).
- `manifest.json` and `approval.json` are **tool metadata, not evidence** (page hashes, flags,
  run/approval ids, timestamps — never OCR text or digits); by default leave them in the local
  `--redacted`/`--approved` trees. A manifest filed under `med/sources/_redacted/<filed-name>/` for
  audit gets the dated name (e.g. `YYYY-MM-DD__redaction-manifest__<filed-name>.json`, for L6)
  **and its own ledger entry**
  (`… append <handle> add --relpath med/sources/_redacted/<filed-name>/<dated-name>.json`): L13
  requires an active record for every primary file in that tree (exempt: exact OS cruft and the two
  root-level boilerplate docs; an `.ocr.md` derivative binds through its primary).
- End-of-run assert: no `.ocr.md` contains a token in a selected scheme's residue shape (the number list's
  third field); for a number with a date-of-birth prefix or a checksum, one matching the prefix or
  passing the checksum (grep + checksum pass).

## Limits of the tooling

- Local OCR can miss an identifier it cannot read even on the darkened copy: none was missed on 50
  invented pages, grey and tinted paper included, but no real scan has been tested; the human gate
  remains required.
- Read verified pages through `load_verified_pages()`, the only call that returns exactly the
  verified bytes; the verifier CLI cannot make a later reopen atomic, and the interactive-read window
  is owned by the discipline above.
- Approval files are integrity metadata, not an authenticated signature: with both gates they
  detect **accidental and concurrent** tampering, not a same-user writer who coherently rewrites
  source, manifest, pages and approval together — outside the supported threat model.

## Self-test

Synthetic identities only; either invocation runs the full suite and exits zero (the dotted form
works despite the hyphen in this directory's name, see `tools/private-mode/__init__.py`):

```
python3 tools/private-mode/test_redact_ids.py
python3 -m unittest tools.private-mode.test_redact_ids
```

Every external tool call is mocked, so no real poppler/tesseract/ImageMagick is needed except for
the ImageMagick pixel-burn geometry probe, which self-skips with an explicit reason when ImageMagick
is absent (a permitted skip). The only other environment skips: a platform without `os.mkfifo`
silently loses four FIFO-refusal bites, and a run as root three permission-bit bites.
