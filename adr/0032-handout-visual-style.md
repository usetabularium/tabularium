# ADR-0032 — Handout visual style: shared stylesheet + render helper ("Warm Editorial", paper-first)

- **Status:** Accepted 2026-07-05
- **Date:** 2026-07-05
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Handout styling was reinvented at every render, so the look drifted between documents and between
regenerations of one document. The rules named the toolchain (python-markdown → weasyprint) but
gave it no executable home, so each render re-derived the mechanics behind ADR-0026's failures
(broken tables, collapsed references). The operator also asked for a deliberate type and colour
identity.

## Decision

What holds now: `_templates/handout-assets/README.md`, the header, tokens and change log of
`handout.css`, the footer and build-QA of `render_handout.py`, `preview.css` for the screen preview
(ADR-0058), `_templates/HANDOUT-RULES.md` (*Header, identity and footer*; *Rendering and visual
style*) and the identity-scan comments in `checks/publish-skeleton.sh`.

1. **One shared style and one render path for both audiences** (2026-07-05), in
   `_templates/handout-assets/`: `handout.css` is the single source of truth for the PDF's look,
   `render_handout.py` runs the route HANDOUT-RULES and ADR-0026 mandate, and the fonts are bundled.
   The writing rules stay in `HANDOUT-RULES.md`. Density follows the filename's audience: larger
   type for the patient's older readers, denser for the clinician's tables and references.
2. **"Warm Editorial" type** (operator, 2026-07-05, picked from rendered specimens): Spectral
   headings, Source Sans 3 body. Both cover Polish and broad European Latin and read well for older
   patients and a time-pressed clinician. The first warm terracotta-and-sand colours gave way to
   points 4 and 5.
3. **Paper-first** (operator ask, 2026-07-05: warm on a display, white on paper). One PDF cannot be
   both, so the printed page stays white; warmth rides on accents and a screen-only layer.
4. **Ink-lean revision** (operator, 2026-07-05: a little too warm; the print must be white to save
   ink). Headings went dark sienna, terracotta stayed on thin rules and list markers, and every
   filled area became screen-only. Superseded by point 5.
5. **Ink-neutral revision for cheap home printing** (operator ask, 2026-09-13). All text is neutral
   grey (R=G=B), so a printer can use black ink alone; the design system's green is the only accent,
   on thin lines and marks. The screen-only block was removed, since the PDF renders print media
   and the screen view is now `preview.css`.
6. **Fonts are bundled** (2026-07-05), OFL, from Fontsource, so a render is identical on any host
   and offline. Two same-day red-team findings, fixed before commit: **M1**, weasyprint embeds
   `@font-face` fonts only when given a `FontConfiguration` (without one, every PDF had silently
   used system fonts); **M2**, weasyprint ignores `unicode-range`, so Polish letters rendered as
   tofu until each weight became one merged file.
7. **The body face ships as Handout Sans** (2026-10-11, operator-requested after a licence review).
   The M2 merge makes each body file a Modified Version under the OFL, and Adobe reserves the name
   "Source" (condition 3). Only names changed, so the printed page did not. The licence file is
   Adobe's own `LICENSE.md` from its source-sans repository (retrieved 2026-10-11), replacing the
   Fontsource copy. Point 2's design choice stands.
8. **The footer prints a numeric date and no web address** (operator asks, 2026-09-13): the
   prep-date is `DD.MM.YYYY` in every language, an impossible or non-ISO date halts the render as a
   B0 authoring fault, and no web address for Tabularium appears until the public site serves (flip
   checklist P3).
9. **A line-scoped export-scan carve-out for the helper** (operator-approved, 2026-07-06). The fonts
   did not trip the publish firewall; a lowercase month name in the helper's date formatter did,
   matched case-insensitively by the identity scan against a proper-name token. Only the helper's
   month-array lines were exempted, and the scans gained `grep -I` for the binary fonts. The script
   was then local; it is tracked since 2026-09-06 (ADR-0050).
10. **The carve-out is retired** (2026-09-29). After point 8 the helper carries no month names and
    is scanned like every other file; the top-level `NOTICE.md` is the only content carve-out left,
    and a negative control was added against its return. The dry export this left owed ran on
    2026-10-10 and stopped on a scan hit in ADR-0050, fixed in `59119c7`; whether its file list
    matched the earlier one was not recorded.
11. **That control is not restored** (operator, 2026-10-11, after a break test in which the ported
    control caught its mutant). The 2026-10-04 suite shrink dropped it with the other export tests,
    and their 2026-10-10 restore did not port it; no decision had named it. The identity scan is
    unchanged since it last passed. When it returns is an open decision.

## Alternatives considered

- **Warm colour** (2026-07-05): a warm tint baked into the PDF (rejected: it prints a cream cast
  unless the viewer strips backgrounds, against print-white by default); a warm HTML view beside a
  white PDF (deferred: two files per handout and a pipeline change; ADR-0058's preview later took
  this shape).
- **Type** (operator, 2026-07-05): *Clinical Calm* (Source Serif 4 + Inter, cooler) and *Soft
  Humanist* (Fraunces + Lora, warmest but more characterful).
- **Font delivery** (2026-07-05): installed on the system (not reproducible; neither face is a
  default on macOS or the sandbox) or fetched from Google Fonts at render (a network dependency the
  sandbox blocks). Bundling is the only reproducible offline option, and the OFL allows it.
- **Designing it in Claude Design** (rejected 2026-07-05): it targets web UI, while this is print
  CSS tied to weasyprint under hard constraints (Polish diacritics, elderly legibility,
  print-white). It was designed against the real pipeline, with a live preview.
- **Case-sensitive identity matching instead of the carve-out** (rejected 2026-07-06): it would
  blind the scan to a name in lowercase (OCR text, a URL slug), a false negative in the
  highest-stakes leak class.

## Consequences

- New handouts take the style through the helper. Earlier handouts stayed as rendered; re-rendering
  was offered as a per-person, single-session follow-up, and nothing touches patient folders
  automatically.
- The assets ship with the skeleton (`_templates` is on the export allow-list) and tripped no guard.
