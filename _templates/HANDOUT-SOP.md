# Handout generation SOP — the sequence (order of operations)

`HANDOUT-RULES.md` says **how** a handout is written (voice, register, notation, rendering, citations).
This file says **in what order** to do the work, so the process isn't re-derived each run and so the
expensive steps don't get repeated.

## Why the order matters
The fact-check (step 6) binds to the Markdown's **SHA-256**, so **any** later edit — a citation, a glyph,
a missing blank line — forces another verify round. So **finalize everything mechanical
before the fact-check** and verify last; no check is skipped (why and measured cost: ADR-0034). For a
same-encounter pair, draft both audiences in one session (same person — allowed).

## The sequence

In short: draft in the person's `med/analysis/drafts/` → author pre-flight → draft render with `--out`
and `--preview-html` → operator review → move into the encounter directory → bundle + fact-check (a
repair that changes content gets a fresh preview) → seal → eyeball → INDEX → board.

1. **Start the draft outside the handout lane**, in this person's `med/analysis/drafts/` (create it the
   first time). Its encounter dir — one per handout, `med/handouts/<audience>/<YYYY-MM-DD>-<slug>/` — is
   created only when the reviewed draft moves in (step 5). `med/analysis/drafts/` is the draft's home
   across sessions and **L15** never reads it; a draft PDF, preview or empty folder left under
   `med/handouts/` reds L15 — move it back here (L15's message says so), never outside this person's folder.
   Once reviewed and moved in (step 5), the Markdown and its fact-check sidecar may wait unsealed in
   its encounter dir.
   Canonical leaf `YYYY-MM-DD__handout-<audience>__<slug>[__TAB-…].md` (L8). Put front-matter at the very
   TOP: `id:` / `date:` / `lang:` (drives the footer; missing → build-QA **B0**).
   A trailing `__TAB-…` is optional for grandfathered files; when present, it must exactly match `id:`
   before either a draft or seal is rendered. Read the person's
   `Patient language` / `Clinician language` / `Handout calibration` from `profile.md` — never hardcode.
   Copy the template in the reader's language (`HANDOUT-RULES.md` → *Language per person*: English
   `handout-<audience>.md`, the base; Polish `handout-<audience>.pl.md`).

2. **Write the `.md`** to `HANDOUT-RULES.md` (audience voice, register-per-person, notation, structure,
   the one-line evidence key + standard closing note for clinician handouts).

3. **Freeze the mechanicals before the fact-check — it binds the bytes:** a clean draft render
   (step 5) with its warnings resolved too (style words such as `Vetted`, `grade A–D` and `cal-…`
   only warn), no arrows or maths signs (`→ ≠ ≥ ≤`: outside the fonts, and B4 does not say which
   glyph), and every citation opened and checked under `reference-library/README.md` — build-QA does
   not check citations, and L4 only warns.

4. **Author pre-flight (cheap insurance — do it in the drafting session).** Before the operator's
   preview (step 5), so the text they review is the text that gets verified, re-walk every claim
   against `profile.md` + `medications.md` (already in your context) for the must-fix classes that
   recur:

   - each value belongs to THIS person, and each grade tag (clinician) or plain-words provenance
     (patient) matches the profile's;
   - every `⟨confirm⟩` obligation is carried (in a patient handout, in plain words only);
   - **no unsearched absence claim** — before "none on file", "not documented", "never measured" or
     "unknown" about a measurable fact stands, in the handout or the record, search this person's
     `med/sources/` text layers (a content search with a `*.md` glob, never the scans); a recorded
     result is not an absence — open its original (for a private-mode person, the approved redacted
     copy) and file the fact in the record;
   - clinician text: every cited source clears the bar and has its Vetted library entry (added as cited) —
     official product information instead its link, with the revision date checked against the current
     text —, and no uncited drug-label claim (a contraindication, an interaction, a dose limit);
   - patient text: the urgency levels in "if anything worries you" (emergency number, same day, soon)
     come from the person's latest recorded escalation frame (in the profile or an interview record)
     when one exists — list it in the manifest — and each symptom sits at exactly one level.

   This does **not** replace the independent verify (step 6 runs regardless); it exists because each
   MUST-FIX the verifier finds costs another round — first-pass PASS is the single biggest
   token saving. While auditing, write down the **source manifest**: the exact `med/sources/` text layers +
   `reference-library/` entries the handout relies on, including the concrete source files that relevant
   provenance pointers in profile/medications resolve to — step 6 needs the list.

5. **Mechanical gate, operator review, move into the lane — all BEFORE the fact-check; fix everything
   they find:**
   - **Draft render with a preview** (create `med/analysis/previews/` the first time; `<n>` counts the
     rounds, because a preview is never overwritten):
     `.venv-render/bin/python _templates/handout-assets/render_handout.py <draft>.md --draft --out <scratch>/<stem>.draft.pdf --preview-html <person>/med/analysis/previews/<stem>.draft-<n>.html`
     → runs the full build-QA (B0–B10) with no seal gate, and saves a local HTML reading copy that embeds
     the same PDF (`handout-assets/README.md` → *Optional local HTML preview*).
     Pass `--out` explicitly: without it the draft PDF lands beside the input. The leaf must stay
     `<stem>.draft.pdf` (`<stem>` = the input basename without `.md`; any other name is refused), and
     `<scratch>/` must sit outside `patients/**` (convention — no guard covers the patient tree beyond
     `med/handouts/`). **Eyeball it** (tables intact, lists are lists, sections break, no clutter, no tofu).
     The "not fact-checked" line in the top margin of every draft page is expected — leave it.
   - `bash checks/check.sh` → **L5** (no other person's handle in this person's files — including any
     sidecar you've drafted).
   - **Operator review.** Give the operator the preview and wait for their go-ahead: a handout reaches
     the fact-check and the seal only after they have seen it, unless they waive the review. A correction
     goes into the draft and a fresh render.
   - **Move it into its encounter dir** `med/handouts/<audience>/<YYYY-MM-DD>-<slug>/` — the fact-check
     reads the handout only from there. Create the dir and move the approved `.md` in one step, the
     `__TAB-…` ID suffix in its filename matching `id:`. An empty encounter dir reds **L15**: if the move
     stops halfway, move the draft back and remove the dir. Then `bash checks/check.sh` again → **L8**
     (filename), **L4** (cites), **L5** — L8 and L4 do not read `med/analysis/`.
   - Keep the `.draft.pdf` **out** of the encounter dir (L15 reds a draft artifact inside one); delete it
     when done. Do **not** proceed to the fact-check (step 6) with any known mechanical break — that is
     exactly what forces a re-verify.

6. **Independent fact-check (INVARIANT — never skip, never reuse across handouts).** A fresh-context,
   single-person-scoped peer verifier (`_templates/handout-factcheck-verifier.md`, ADR-0034) reads the
   `.md` adversarially and writes the hash-stamped `…__handout-<audience>__<slug>.factcheck.md` sidecar
   (`verdict: PASS`, `must_fix_open: 0`). Any open MUST-FIX or identity-mismatch blocks the seal.
   It must open the scanned original behind every medication, allergy, measured value and
   safety-critical categorical fact (for a private-mode person, the filed masked page in its place;
   for a person with kept details, no page image); originals never enter the bundle — it finds them on disk.
   Invoke it as `handout-factcheck-verifier.md` says (bundle mode for 3+ sources).
   **On FAIL**, repair by each finding's fix class and verify again —
   `handout-factcheck-verifier.md` → *After the verifier runs*. A repair that changes content gets a
   fresh preview for the operator before the seal (they may waive it, as with the first review).

7. **Seal** (no `--draft`): `.venv-render/bin/python …/render_handout.py <file>.md`. Until this step the
   `.md` (and its sidecar) is a draft: it may stay in its encounter dir across sessions with the board
   green, and nothing there is deliverable. The gate requires PASS with zero open MUST-FIX findings
   and matching handout bytes. If the sidecar records the profile's and medications list's digests,
   those must also match when the gate runs: seal before editing the record, or run a later verify
   round after the edit. Then it writes `<stem>.attest.json` (L15). Sealed units are **immutable** — a
   re-render of an attested stem refuses; new facts → a **new dated unit**.

8. **Eyeball the sealed PDF** (INVARIANT — build-QA is mechanical, not a substitute). A handout that looks
   wrong is wrong, and a sealed PDF never shows the draft's "not fact-checked" top-margin line — one that
   does is a draft, not the seal. For a person with kept details the sealed PDF carries them and no session may
   read it: the session eyeballs the draft, and **the operator** looks at the sealed PDF before handing
   it over (`HANDOUT-RULES.md` → *Kept details*).

9. **Register in `INDEX.md`.** Append the row naming the encounter dir (+ the `ID` / `Supersedes` columns).
   A sealed unit absent from `INDEX.md` is **red** (L15).

10. **Board.** `bash checks/check.sh` must end green; never end the session red. Records are never
    committed, and a care checkout makes no commits.

## Standing reminders (pointers, not restated logic)
- **Consent (ADR-0027).** A fact the record marks ⟨consent-restricted…⟩ stays off the clinician handout.
- **IDs (ADR-0033 / L8).** `TAB-<PPP>-<NNN><C>`: `<PPP>` the person's handout tag, `<NNN>` = next in
  `INDEX.md`, `<C>` the check character. Never work it out by hand: `python3 -m tools.handout_attest
  next-id <handle> [--count N]` prints the next free ID(s) and writes nothing; once `INDEX.md` holds an
  ID it takes the tag from there. Before that, add `--tag` with the tag on the `Handout tag:` line of
  `profile.md` → Identity; no tag there either: draw one, never pick it yourself —
  `python3 -c "import secrets; from tools.handout_attest.handout_id import ALPHABET as A; print(''.join(secrets.choice(A) for _ in range(3)))"`
  — and record it on that line (added if missing) before numbering. A wrong character halts the draft
  render and the seal; in a filename, L8 reds it too.
- **No render environment yet?** The first handout on this Mac: one yes, saying it is a download of a
  few minutes, then `bash checks/setup-mac.sh handouts` (its `in Terminal:` and `restart:` lines stop
  for the operator, as `SETUP.md`, step 2, says). **Env broken?** Rebuild the pinned render venv with
  `_templates/handout-assets/rebuild-render-env.sh` (ADR-0039 §7 / A2).
