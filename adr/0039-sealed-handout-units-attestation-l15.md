# ADR-0039 — Sealed handout units: products≠evidence lane, build attestation + guard L15

- **Status:** Accepted 2026-07-17; superseded in part by ADR-0070 2026-11-07 (point 3, the control
  block)
- **Date:** 2026-07-17
- **Deciders:** operator (6-artifact classification + four scope decisions, 2026-07-16/17; directory
  shape steelmanned by an adversarial panel, then operator-refined); red-teamed before commit
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The fact-check gate (ADR-0034) proved the *Markdown* was checked; nothing proved the **bytes
actually handed over** were its rendering. A forgotten re-render left a stale PDF green; a changed
PDF left the tree green; PDF-only artifacts were invisible to every guard; the renderer wrote the
PDF *before* QA (crash-unsafe) and emitted no attestation; and the render toolchain was not
reproducible on the host. The deliverable is the highest-leverage artifact: a clinician acts on it
without re-applying our diligence.

## Decision

What holds now: the L15 row of `checks/README.md`, the L15 section and L4/L8 skips of
`checks/check.sh`, the `tools/handout_attest/` docstrings, `_templates/handout-assets/` (renderer,
README, pin), `_templates/HANDOUT-RULES.md` (*Filing, sealing and the register*) and
`CONTRIBUTING.md` (the render environment). Points 1–7 are the sections cited as
"ADR-0039 §1–§7"; amendment labels are tagged inline, and *Amendment labels* maps A1–A9.

Handed-over deliverable bytes (PDF/TXT) are **cryptographically bound** to their fact-checked
Markdown source, and handouts get a **products lane** distinct from evidence.

1. **Products ≠ evidence: the lane split** (operator, 2026-07-16). Everything under
   `patients/<h>/med/handouts/` is a **product**, a synthesis (or a blank form) generated from the
   record; everything under `med/sources/` is **evidence**. Nothing under `handouts/` may appear by
   content hash under any `sources/` tree, or the reverse; L15 checks this per patient. The
   operator: "Outputs should not be used as sources, they're products. We need a separate lane." A
   product that later needs to be evidence (a clinician annotates a printout and hands it back)
   re-enters through intake as a **new scan**, never as a reclassified product.

2. **Sealed, dated encounter units: immutable, with no archive step.** New handouts live in
   audience-outer, encounter-dir units:

   ```
   patients/<h>/med/handouts/
     INDEX.md                        (single root ledger; marks current vs superseded)
     patient/
       2026-01-01-example-visit/     (encounter dir: YYYY-MM-DD-<slug>, sealed on creation)
         <stem>.md                   (<stem> = 2026-01-01__handout-patient__<slug>[__TAB-…])
         <stem>.pdf                  (or .txt fallback, exactly one)
         <stem>.attest.json          (build attestation, point 4)
         <stem>.factcheck.md         (fact-check sidecar)
     clinician/
       2026-01-01-example-visit/…
   ```

   - **Immutable, sealed on creation** (operator, 2026-07-16). A unit is written once; new facts
     make a **new dated unit**, and `INDEX.md` flips the current pointer. There is **no archive
     step and no "spent" marker**: every unit is permanent non-evidence history; the old `archive/`
     subdirs remain only as legacy (point 6). Mechanical since A1: a seal happens only in place in
     a canonical unit dir (else exit 5), an attested stem refuses re-render in every mode, and
     `--out` may name only the canonical sibling.
   - **Bound to the owning repository** (A4, 2026-07-26). Checking only the trailing path shape let
     a look-alike `patients/<h>/…` tree elsewhere receive an attestation this repository's L15
     never inspects. The renderer derives the root from its own real path and `lstat`s every
     component. Deliberately no `--root` or environment bypass: tests copy renderer, stylesheet and
     fonts into the fixture repository.
   - **Audience-outer.** The panel-decisive property is the structural audience wall: a copy of
     `handouts/clinician/**` cannot include the patient's plain-language sheet. Wrong-audience
     handover is the second-worst error class after person mix-up; date-outer and hybrid layouts
     put it one wrong grab away, while audience-outer units fail loud-missing when torn or
     incomplete.
   - **Audiences are independent** (operator refinement, 2026-07-17). An encounter may yield a
     patient unit, a clinician unit or both. No pairing invariant exists, and L15 must never red a
     single-audience encounter; a matching `<date>-<slug>` is a browsing convenience.
   - **Bound to person, encounter and audience** (A1, 2026-07-17). The attestation's `person` and
     `encounter` must match the containing tree, and the leaf date the encounter-dir date, so a
     wrong-patient copy or a re-dated unit is red (the L13 product-lane analogue). The leaf's
     audience token must match its audience dir; the renderer refuses a contradicting `--audience`.
   - **Leaf grammar unchanged.** The canonical leaf
     `YYYY-MM-DD__handout-<audience>__<slug>[__TAB-…].ext` (L8, ADR-0026/0033) stays byte-identical
     inside encounter dirs: L8 and the ADR-0033 IDs stay untouched, a detached file stays
     self-describing (date, audience, slug and ID survive an AirDrop), and migration is a pure move.
   - **No language token in the leaf:** language lives in the front matter (`lang:`), the
     attestation and INDEX; a lang segment is added forward-only if a real multi-language encounter
     arrives.

3. **Canonical order: author → fact-check → render and attest.** The fact-check (ADR-0034) runs on
   the Markdown and precedes render. The renderer **refuses to seal** without a fresh
   `verdict: PASS` / `must_fix_open: 0` sidecar for the Markdown's current SHA-256: the order is
   structural, not vigilance. Sidecar and attestation both bind the Markdown bytes, neither the
   other's creation, so there is no circular dependency. Markdown and sidecar are read once (A1), so
   gate, attested hashes and rendered bytes describe one buffer.
   - **The control block is parsed exactly** (A3, 2026-07-26): three ordered lines and a blank
     fourth, each key once. Splitting on every colon had made `PASS:FAIL` and `0:9` pass.
   - **`--draft`** renders an eyeball copy with no gate and no attestation. Since A1 it writes
     `<stem>.draft.pdf` (`.draft.txt` fallback) and skips every destructive branch, which had run in
     draft mode and could overwrite or delete a live sealed deliverable. Since A5 (2026-07-26) the
     leaf is exactly that name and never replaces an existing PDF or TXT. A draft artifact inside an
     encounter dir is red.

4. **Build attestation (`<stem>.attest.json`, schema `tabularium-handout-attest/v1`).** The
   renderer writes it only after PDF build-QA PASS or the attested plaintext fallback, atomically,
   last in the promote sequence: flat JSON, basenames only, binding the Markdown, sidecar and output
   SHA-256s and the unit's person and encounter (key set: `ATTEST_FIELDS` in `verify.py`), so a
   post-render sidecar swap is loud. A **fallback TXT** (ADR-0034's render-fault path) is
   attested as `output_kind: "txt"`, `build_qa: "FALLBACK"`; PDF and TXT at one stem is a conflict,
   red. A1 made person, encounter, language, tool and timestamp required (`id` may be empty); no
   sealed unit existed yet, so nothing migrated. Since A3 the key set is **exact**, duplicate JSON
   keys are rejected (Python's default decoder keeps the last) and an encounter holds one attested
   stem. The schema stays v1: the key set did not change, only its shape became exact.

5. **Crash-safe render: temp → QA → atomic promote.** The renderer writes a sibling temp in the
   same directory (so `rename(2)` stays atomic), runs build-QA on it and promotes with `os.replace`
   only after PASS: a prior good deliverable is never overwritten before the new one is known valid.
   A QA failure removes only the temp (the fallback path deliberately supersedes the live PDF with
   the attested TXT); a content fault (B0/B7) halts with the previous state intact. A crash between
   promote and attestation leaves an output newer than its attestation, red: no crash window yields
   a silent green. Reserved staging names must be absent (A4), so a planted symlink cannot redirect
   a write.

6. **Guard L15, the legacy queue and same-commit guard repairs.** L15 delegates to the stdlib-only
   `tools/handout_attest` package (JSON is past awk's reach, the L13 pattern), fails closed, and
   without Python mirrors L13's fallback. It covers every `patients/*/med/handouts/` tree and reds
   the attestation, hash, structure and lane faults its section of `checks/check.sh` lists,
   products∩evidence (point 1) and a sealed unit absent from `INDEX.md` (forward presence only).
   - **Filesystem shape fails closed** (A3–A5, 2026-07-26). Every artifact is classified by `lstat`
     before any exemption (a dotfile exemption applied first had hidden symlinks and blocking
     FIFOs); traversal errors (`os.walk` drops them silently) and uninspectable roots are red, never
     an empty set; the no-Python fallback, which had passed exactly when the verifier was
     unavailable, inventories every node type. Green is state-only and renderer read errors
     path-free (A3); red, category-only from A3, names the file since 2026-09-27, withheld for a
     private-mode person (A7; the locator rule, ADR-0029).
   - **The legacy queue is closed** (A1). Flat files and the old `archive/` subdirs are
     `legacy-unsealed`, counted and surfaced on green (the L13 `legacy-folder-only` pattern), only
     if inventoried in the patient's `handouts/.legacy-frozen`. An uninventoried lane file is red
     (`legacy-lane-new-file`), as is lane content with no inventory (`legacy-freeze-missing`): the
     open queue had admitted new, never fact-checked deliverables, green, a laundering channel.
     `freeze-legacy <handle>` writes it once at adoption, for one safe handle below real ancestors,
     so it cannot escape the root (A3). Migration into sealed units is deferred, per patient, at the
     operator's pace, byte-preserving.
   - **The legacy inventory binds bytes (A6, 2026-08-09).** The queue is unsealed by
     design, but bare paths let an inventoried pre-ADR-0039 deliverable, possibly already with a
     clinician, be edited unsurfaced. The v2 inventory holds `<sha256>  <relpath>` under the marker
     `# format: tabularium-legacy-freeze/v2`, its version read from the marker only: a per-line
     fallback would let one bare line downgrade its own entry and escape hashing. Changed bytes are
     red, as is a names-only v1 inventory until migrated: a silently tolerated old format goes
     unadopted. `migrate-legacy`, the one-way v1→v2 conversion, is the only command that
     may replace an inventory; it refuses a v2 one, since re-hashing would re-bless mutated bytes,
     admits no new path and drops absent ones. **Honest scope:** the baseline is the bytes at freeze
     or migration, not at authoring, so a deliverable altered before 2026-08-09 is blessed as-is;
     that is inherent to a late binding, and why the lane should shrink, not be maintained. The
     live inventories were migrated on 2026-08-09. Lessons from its red-team (ten findings, all
     fixed): a key holding a line break could inject a pre-blessed entry, so any character
     `str.splitlines` splits on is refused; a false "inventory retained" after `os.replace` steered
     the operator toward re-blessing, so it reports the true state: do not restore.
   - **An unsealed draft is not a finding (A7, 2026-09-27).** `unsealed-md` fires only in an
     encounter dir that already holds an attestation. A dir with the Markdown (and its sidecar) but
     no attestation and no output is a draft awaiting its seal, and is green: with guard L11 retired
     (ADR-0034 point 3) the renderer's seal gate is the fact-check lock, and this was the second
     guard keeping a draft red across sessions. Nothing deliverable can sit unsealed: an output with
     no attestation stays `orphan-output`, and an extra Markdown beside a sealed unit `unsealed-md`.
   - **Same-commit guard repairs** (panel-verified traps). **L4 re-depth:** its handout glob
     `patients/*/med/handouts/*/*.md` gains depth 3 for encounter dirs (depth 2 kept for legacy),
     or L4 silently fails open on sealed handouts. **L8 carve-out** for `*.attest.json`: its
     two-dot extension false-trips the TAB-segment regex tail exactly as `.factcheck.md` did (the
     ADR-0034 point 2 precedent).
   - **Test gating** (A1): the bite suite executes the `tools/` unit suites behind L15, since "run
     separately" was fail-open; `INDEX.md` presence is boundary-anchored on both edges.

7. **Pinned render environment.** A repo-local, gitignored `.venv-render/` is rebuilt from the
   tracked, shipped `_templates/handout-assets/requirements-render.txt`, a full transitive freeze
   (weasyprint 69.0, Markdown 3.10.2; captured 2026-07-17, Python 3.14.6, Darwin); host libraries
   outside pip are listed there. A synthetic render sanity test proves the pipeline without
   patient data.
   - **Rebuildable on any host** (A2, 2026-07-20). Another host, or a Python bump, inherits a dead
     symlink, and rebuilding by hand under time pressure was the observed cost.
     `rebuild-render-env.sh` rebuilds from the unchanged pin on macOS or Linux and fails closed with
     the native-library hint. The pin holds (pip reproduces its versions on Linux; only wheels
     differ); a materially different interpreter may lack a wheel and need a deliberate re-pin,
     surfacing as a loud pip failure, never a silent divergence.

8. **The sealed format stays PDF or plaintext** (A8; operator, 2026-10-04). HTML as the sealed
   format is withdrawn, not deferred: the operator chose not to build it (the HTML preview outside
   the lane is unaffected). Sharing handouts through an encrypted cloud-drive link, by hand or by a
   tool step, is dropped with it: no new egress path for patient data. Closes roadmap D4.

9. **No python3: one red, tested** (operator decision, 2026-11-01; simplification scan item 10).
   Without python3, L15 no longer walks the handout lanes in shell for non-scaffold node types: it
   reds once whenever `patients/` holds any person entry, naming the fix, install Python 3.9 or
   newer; a person-free tree stays green. The shell walk had no bite; `checks/selftest.sh` now runs
   this path. Lost: a no-Python host with scaffolded people and no handouts reds instead of green.

### The 6-artifact inventory (operator classifications, 2026-07-16)

- **1, a blank tracking form** (PDF-only, live dir): retire to `patient/archive/` in its patient's
  migration pass. A form is a product, not a handout; no form class is built.
- **2–5, four archived PDF-only deliverables:** preserved-not-verified legacy, queued under
  `archive/`; no reconstructed source, no retroactive attestation.
- **6, a pre-visit card** (Markdown, fact-checked, no PDF): flat legacy, queued; no render, no
  archive step: under point 2 it is simply a historical unit.

### v2 deferrals (built only when triggered, the ADR-0037 §9 pattern)

Reverse INDEX reconciliation (every row points at an existing unit) and current-vs-superseded graph
validation; an audience-scoped export or copy-out helper; a content-level audience assertion (the
front matter's `audience:` against the path), while path, filename and attestation already agree by
enforcement at render time (A1); and a lang leaf segment, forward-only, on the first real
multi-language encounter.

### Amendment labels

Folded into the points above: **A1** (2026-07-17, the pre-commit red-team fix pack, Tier-S under
ADR-0031, every confirmed finding fixed in the same landing): points 2–4, 6 and *Consequences*;
**A2** (2026-07-20): 7; **A3** (2026-07-26): 3, 4, 6; **A4** (2026-07-26): 2, 5, 6; **A5**
(2026-07-26): 3, 6; **A6** (2026-08-09) and **A7** (2026-09-27): 6; **A8** (2026-10-04): 8. **A9**
(2026-10-11) recorded drift the owners now state: no hook runs the bite suite (`CONTRIBUTING.md`),
and CI skips the render sanity test (`checks/selftest.sh`, *Handout renderer*).

## Alternatives considered

- **Date-outer or hybrid layouts** (panel): an encounter dir with no person handle gives
  identically named "portable packets" across relatives (cross-person collision, the #1 error
  class), and both audiences sit one grab apart: silent-wrong, where B is loud-missing.
- **The panel's own rich-leaf rename (B-prime):** it breaks L8's grammar and ADR-0033 TAB-ID
  continuity for no added safety.
- **A cross-audience pairing invariant:** audiences are independent (operator), so pairing is not
  a property of the domain and not a check, not even deferred.
- **Extending L11 instead of a new guard:** L11 was one crisp contract (sidecar freshness); byte
  binding, lane separation and unit structure are another, and cohesion favours L15.
- **Retroactive attestation of archived PDFs:** it would assert verification that never happened.
- **Shell-parsing the attestation JSON in `check.sh`:** the L13 lesson (point 6).

## Consequences

- The bytes a reader receives are bound to the fact-checked
  Markdown, and a stale, changed or orphaned deliverable is red.
- L15 proves byte binding and lane separation only; the content verdict stays with the seal gate's
  fact-check (ADR-0034).
- **Limits**, all in the accident model:
  - The attestation is unsigned: L15 verifies bytes and fields, not renderer authorship, so a
    same-user writer editing attestation and bytes together passes, as for every guard.
    A hostile same-user swap after the renderer's preflight would need `openat`/`renameat`.
  - The products∩evidence check skips evidence boilerplate by name, so a product byte-copied to
    `sources/README.md` evades it; it runs per patient, so cross-patient product duplication rides
    with ADR-0037's deferred cross-root duplicate detection.
  - A1's acceptance of inventoried archive symlinks was superseded by A3's fail-closed symlink
    classification.
- Verified by `tools/handout_attest/test_attest.py` and the L15 and renderer bites in
  `checks/selftest.sh`.
