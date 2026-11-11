# Handout house style (`handout-assets/`)

The single visual style for **both** handout audiences, so the look never drifts between documents or
regenerations. Decided in **ADR-0032**; the writing rules that use it live in `../HANDOUT-RULES.md`
(*Rendering and visual style*). This folder is the *appearance* home; HANDOUT-RULES stays the *voice/content* home.

## What's here
- `handout.css` — the stylesheet (colour tokens, typography, tables, callouts, references, page numbers).
- `render_handout.py` — the render helper (the canonical toolchain; see below).
- `preview.css` — the screen-only stylesheet of the optional HTML preview (design-system tokens); never
  used for the PDF.
- `fonts/` — the two print typefaces and the three preview-only families, all under the SIL OFL 1.1
  (texts in `fonts/OFL-*.txt`). The body face **Handout Sans** is Adobe's Source Sans 3, renamed; how
  a re-merge must name it is in the bundled-fonts note in `handout.css`.

## How to render
Two modes — an unsealed draft for build-QA, and the seal itself:
```
# draft — build-QA + eyeball copy, no gate. Without --out it lands beside the input — inside the
# encounter dir once the draft has moved in (L15 reds a draft artifact there); the leaf must stay
# <stem>.draft.pdf.
.venv-render/bin/python _templates/handout-assets/render_handout.py  <handout>.md  --draft  --out <scratch>/<stem>.draft.pdf

# SEAL — run in place inside the encounter dir; writes <stem>.pdf + <stem>.attest.json
.venv-render/bin/python _templates/handout-assets/render_handout.py  <handout>.md
```
A default (no `--draft`) render **is a seal** (ADR-0039): it refuses (exit 4) without a fresh PASS
`.factcheck.md` sidecar matching the markdown's current bytes, and refuses (exit 5) outside the canonical
`patients/<handle>/med/handouts/<audience>/<YYYY-MM-DD>-<slug>/` location, on any re-render of an
already-attested stem, and on any `--out` other than the canonical sibling `<stem>.pdf` — for a copy
elsewhere use `--draft`. The sequence around these two commands is `../HANDOUT-SOP.md`.

A draft skipped the fact-check, so every page of a draft PDF prints **DRAFT — not fact-checked** in the
top margin (in the footer's language), and a
draft's `.txt` fallback opens with the same line; a seal never shows it. The margin keeps the draft's
pages laid out exactly like the seal's.

**Kept details** (ADR-0075): the helper fills the placeholders of a person with kept details from
their identity file — the
handle and neutral labels in a draft, the recorded values in a seal. It refuses (exit 5) a placeholder
that is unknown, has not exactly one recorded value, belongs to a person with no identity file, or sits in the
front matter or inside markup (a link target, an image, an attribute). A render fault halts with no
`.txt` fallback; a seal takes no `--preview-html`. Where placeholders may go: `../HANDOUT-RULES.md` →
*Kept details*; the mode itself: `tools/private-mode/topics/kept-details.md`.

**Nothing is fetched or embedded** (every render): the PDF engine may load only `data:` URLs and the
files beside this helper (the stylesheet and its fonts). A source that refers to anything else — a
remote image, a local file — refuses (exit 5), so a render never reaches the network and a delivered
PDF never carries another file.

Audience is inferred from the canonical `__handout-<audience>__` filename when not passed; it sets body
density (patient larger, clinician denser). The sealed PDF shares the input stem (guard L8);
a draft is `<stem>.draft.pdf`, where `<stem>` is the input basename without `.md`. Use the
repo-local pinned `.venv-render/` (rebuild with `rebuild-render-env.sh`), not a bare `python3`. This
helper *is* the toolchain HANDOUT-RULES mandates: never hand-roll a Markdown-to-PDF call, which
breaks tables and the references list.

## Optional local HTML preview

Add `--preview-html <new-file>.html` to a draft or final render to get one offline HTML file, styled
for the screen (`preview.css`), that embeds the exact PDF that passed build-QA, with a **Download PDF**
button at the bottom. The PDF itself is unchanged: screen and paper deliberately look different while
carrying the same text.

```
# Review before the fact-check. <person> means patients/<handle>; create the preview directory first.
.venv-render/bin/python _templates/handout-assets/render_handout.py <handout>.md --draft --out <scratch>/<stem>.draft.pdf --preview-html <person>/med/analysis/previews/<stem>.draft.html

# After the ordinary fact-check, optionally save a matching preview alongside the final seal.
.venv-render/bin/python _templates/handout-assets/render_handout.py <handout>.md --preview-html <person>/med/analysis/previews/<stem>.html
```

Open the saved HTML locally. Drafts carry the PDF's draft line above the title, and it stays when the
preview is printed; the button
always says **Download PDF** (both translated with the document's footer language). Make corrections in the Markdown and render a new copy; a saved
preview always contains the PDF from that same render and does not update itself after later edits.
The screen view helps with reading and proofreading; inspect the generated PDF for its pagination.

Where it may go: a new file in an existing folder, **outside `med/handouts/`** (HTML is not part of a
sealed unit), and for a patient source inside that same person's folder (`med/analysis/previews/`
suits). It holds the person's information: it stays in CARE, never in tracked product. A synthetic
input may save its preview beside the fixture. A preview is never replaced and is saved owner-only;
a patient source from another checkout is refused (run that checkout's renderer).

Preview mode takes prose, tables, lists and explicit web or e-mail links; embedded media, scripts,
inline styles and relative links refuse before rendering. A failed render or a `.txt` fallback makes
no HTML. If the preview fails to save after the PDF was made, the PDF is kept: never re-seal a sealed
unit.

## Markup the stylesheet styles
Tables, the clinician evidence-legend (`>` blockquote) and the references numbered list (`<ol>`) are
styled automatically. Three attr_list markers are opt-in (already in the templates):
- `{: .identity}` — the one-line `Patient:` / `For:` identity line under the title (ADR-0033).
- `{: .provenance}` — on the patient closing note (small muted footnote; the `---` above it is the rule).
- `{: .metodyka}` — the clinician closing note (muted and smaller; the `---` above it is the rule).

(`.docmeta` remains in the stylesheet as a legacy selector for older files; no template uses it.)

## Front-matter, footer & build-QA
Set three fields in the file's front-matter (top of the file, `key: value` lines, then a blank line):
`id` (the handout ID, ADR-0033), `date` (prep date, `YYYY-MM-DD`), `lang` (`en` default; `pl` also supported). The
helper prints a footer on every page — `Prepared DD.MM.YYYY · …Tabularium · usetabularium.com` (left) and `<id> · p. X / Y`
(right); the page numbers are computed by weasyprint, so they are reliable across multi-page handouts.

After rendering, the helper runs a fast non-LLM **build-QA**; each failure prints its code and what
to fix. A *render* fault (a broken table, a bad glyph, a missing page number …) writes a
plain-but-correct `.txt` instead of a suspect PDF and exits non-zero. An *authoring* fault (front
matter, a leaked unfinished-text or private-data marker such as `{{`, `TODO`, `⟨confirm` or
`⟨withheld`, a list with no blank line above it, a kept detail that did not reach the PDF intact)
**halts with no fallback**: fix the source. Style words (`grade B`, `Vetted`, `handout` …) only warn.
The header, identity and notation standards live in `../HANDOUT-RULES.md`.

## Style and fonts
The look, colour tokens and fonts are set and explained in the headers of `handout.css` (the PDF's
single source of truth) and `preview.css` (the screen preview). After any style edit, render a sample
and eyeball the PDF.
