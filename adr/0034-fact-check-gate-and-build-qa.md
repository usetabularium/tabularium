# ADR-0034 — Handout fact-check gate, non-LLM build-QA and plaintext fallback

- **Status:** Accepted 2026-07-05; superseded in part by ADR-0064 2026-11-07 (points 1 and 6),
  ADR-0069 2026-11-07 (point 9's private-mode exception) and ADR-0070 2026-11-07 (point 2's control
  block)
- **Date:** 2026-07-05
- **Deciders:** operator (+ assistant; design red-teamed by an independent Opus subagent)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

A handout may be handed to a clinician without the operator re-applying their own diligence, so one
unverified or drifted claim can undo all upstream record integrity: the hand-over is the
highest-leverage place for a hard, mechanical check. PDF fragility had also repeatedly cost render
iterations and risked shipping a broken document. Every handout needs two independent guarantees,
*content correct* and *rendering faithful*, plus a fallback.

An LLM verdict cannot live inside `check.sh`: the board must be deterministic, offline, fail-closed
and host-portable (ADR-0020, ADR-0021). A model's judgement has to reach the deterministic side as
an artifact a check can verify.

## Decision

**Current verify procedure:** `_templates/handout-factcheck-verifier.md` owns invocation and repair,
and points the verifier to `_templates/handout-verifier-prompt.md`; `_templates/HANDOUT-SOP.md`
places verification in the handout workflow. Rendering and sealing mechanics stay in
`_templates/handout-assets/` (the tools and README) and `checks/README.md` (L4, L8, L15); ADR-0039
owns sealed units.

1. **A fact-check gate on every handout (content)** (2026-07-05). Before a handout is handed over,
   an independent, fresh-context peer Opus verifier scoped to one person reads it on the Markdown,
   adversarially, against only that person's `profile.md`, `medications.md`, cited `med/sources/`
   and the Vetted reference library. It writes a per-claim ledger (`supported`, `unsupported`,
   `contradicted`, `wrong-grade`, `mislabeled-value`, `uncited`, `unvetted`, `identity-mismatch`,
   `inconsistent`, `dropped-⟨confirm⟩`), each finding MUST-FIX or advisory, to a hash-stamped
   `<stem>.factcheck.md` sidecar. Any open MUST-FIX blocks hand-over; an `identity-mismatch` is a
   hard stop. Wired 2026-07-06, enforced on every handout from 2026-07-11 (point 3).

2. **The model writes a hashed verdict; a deterministic check reads it** (2026-07-05). The sidecar
   opens with three control lines (2026-07-06): `handout_sha256` over the handout's exact bytes,
   `verdict: PASS|FAIL` and `must_fix_open: <int>`. The check accepts only a fresh sidecar (the
   Markdown's current SHA-256, PASS, zero MUST-FIX), so the gate is structural, not vigilance, as
   ADR-0022 made "never commit through red". The fact-check runs on the Markdown and precedes, never
   replaces, the render and the eyeball. A sidecar lives inside the `patients` boundary (gitignored,
   publish-DENY) and inherits the firewall with no entry of its own. It is a QA record, not a
   handout anyone receives, so L4 skips `*.factcheck.md` (a sidecar legitimately names a Candidate
   id when it flags an `unvetted` citation) and, from 2026-07-11, so does L8, whose single-extension
   tail cannot match the two-dot name a sidecar gets when it inherits its handout's `__TAB-…`
   segment (ADR-0033).

3. **Guard L11 retired; the renderer's seal gate is the one lock** (operator-approved guard sweep,
   2026-09-27; number not reused). L11 was point 2's check on the board: a fresh hash-matching
   PASS/0 sidecar beside every handout `.md`, staged opt-in behind a `factcheck: required` marker
   from 2026-07-06 and blanket from 2026-07-11 (handover 02, operator go-ahead), once every live
   handout carried one; the templates kept the marker as reader-visible metadata. **Why it went:**
   L11 red every handout `.md` from the moment it existed until a passing sidecar did, so a draft
   could not span two sessions without ending one red, which the care workflow forbids. The harm is
   a deliverable reaching a reader unverified, and that happens at the seal: the renderer's seal
   mode refuses without a fresh PASS/0 sidecar for the Markdown's current bytes (the grammar L11
   parsed; `test_attest` bites each shape L11 used to red), L15 binds the sealed Markdown, sidecar
   and output bytes, and L15's inventory freezes the legacy lane's bytes. What L11 added beyond
   those was the red on unsealed drafts, the thing removed. L15's `unsealed-md` changed with it
   (ADR-0039 A7). The verifier, the sidecar contract and the mandatory fact-check are unchanged.

4. **Build-QA and the plaintext fallback (rendering)** (2026-07-05). `render_handout.py` checks the
   rendered PDF without a model for mechanical breakage (tables, lists, glyphs, page numbers) and
   leaked internal vocabulary. When a clean PDF cannot be verified, it writes a plain-but-correct
   `.txt` with the same content and exits non-zero: accuracy over aesthetics, since a correct plain
   handout beats a broken pretty one and formatting must never risk patient harm. A content failure
   (an identity mismatch, an open MUST-FIX) halts and never falls back. **B8** (2026-07-20): a list
   run into the paragraph above it, caught only by a human eyeball after the immutable seal, cost a
   full new unit; B8 is marker-agnostic (a red-team caught a hyphen-only first draft), and as an
   authoring fault whose one-blank-line fix yields the intended PDF it halts like B0 and B7 instead
   of falling back. The checks and their outcomes: `build_qa` and `handout-assets/README.md`.

5. **Mechanical work before the fact-check** (2026-07-20). The sidecar binds the Markdown's bytes,
   so any later edit forces another verify round. `HANDOUT-SOP.md` puts the mechanical checks (a
   draft render, the board) before the expensive fact-check, so a late mechanical fix no longer
   forces a re-verify; the author pre-flight (point 10) does the same for recurring must-fix
   classes.

6. **A one-shot bundle and an author source manifest** (2026-07-26, landings a–d). A verify cost
   about 130 K tokens, mostly from the invocation's shape, not its judgement: a multi-turn verifier
   re-sends its growing context every turn and spends a discovery phase finding the sources, and a
   discovery miss surfaces as a spurious `unsupported` MUST-FIX that wastes a whole round. Only the
   shape changed. The author's manifest is a floor, never a blinder: the verifier may open any other
   file of the same person or the library, still refuses every other person's folder, and resolves
   or ledgers every explicit provenance pointer. The deterministic assembler enforces the one-person
   scope before any model sees a byte, admits only the evidence lane (analysis and products refuse),
   and prints a whole-bundle digest, passed outside the bundle, that binds every inline byte; the
   handout is read from disk, the bytes the sidecar binds. All bundled text is untrusted quoted
   evidence, never instructions (b). Source completeness is bounded (c): the working set plus a
   targeted lookup for each provenance pointer a claim needs, not a second exhaustive scan of raw
   sources, which intake reconciliation owns; the contract became one literal, value-free standing
   prompt plus a versioned input block. Ergonomics, the point of the whole lineage (d): `--out` is
   optional and the script prints a ready-to-paste input block, removing about nineteen hand
   transcriptions per run, a 64-hex digest among them. File mode stays the fallback; no fsync, by
   decision (b): the bundle is transient and an interrupted assembly is re-run. **The
   accident model:** the wall stops accidents, not a same-user adversary, and record drift inside
   the assemble-then-verify window is stamped, not re-checked. The boundaries keep a
   token-saving adapter from becoming a security protocol whose cost exceeds its benefit. Every
   property and boundary: the script's header.

7. **A handout is a full synthesis** (2026-07-26, b and c). Delta-by-default was removed: delta
   scoping needs a baseline binding and a material-omissions check that are not built, so full
   synthesis stays the default, and an `INDEX.md` row records lineage but cannot authorize delta
   scope (`HANDOUT-RULES.md` → *Filing, sealing and the register*).

8. **The hardening ceiling** (operator-directed, 2026-07-26 d), set in the then-local,
   single-operator, no-remote system: anyone with code execution as this user can already read the
   patient tree, so same-user adversary hardening buys nothing the OS does not already concede. The
   bundle component is closed to further hardening passes. Future work on it is admissible only when
   it (a) fixes a defect reachable by accident, (b) is required by a real incident, or (c) reduces
   operator friction. A finding whose only reachable path needs a same-user adversary is recorded as
   an accepted residual — not graded a blocker, not fixed — unless its fix is also simpler or more
   correct, in which case it is taken on those merits. **Why:** the prior rounds spent most of their
   budget on adversary-shaped findings while two accident-shaped defects (the masked `cat` and the
   glob substitution, *Reviews*) survived them all, and the tool's benefit was unmeasured. The next
   action was measurement, not hardening: per-phase token counts on the next real handout run, and a
   revisit only with that data in hand (the measurements of 2026-10-02: point 11).

9. **The verifier opens the originals behind safety-critical values** (risk survey,
   operator-approved, 2026-09-29). The verifier read text layers only, so a value misread at
   transcription could travel unchanged through the profile, the medications list and the handout,
   and the fact-check found the three in agreement and ruled it `supported`: the last look at the
   scan was at intake, and the first behavioural baseline caught a session citing a transcription
   without opening its original (EV-05b-t2). The verifier now opens the original behind every
   medication, allergy, measured value and safety-critical categorical fact the intake checklist
   names; for those rows a text layer alone is not a loaded source. Before any original it must have
   read the profile in an earlier step and checked it for the private-mode marker: the raw-scan
   experiment in ADR-0029 point 12, of the same date, measured that ordering narrowing raw-scan opens
   (Sonnet 5: 4 of 6 without it, 1 of 6 with it) without closing them, and the read-guard extension
   described there covers this path too. The ledger vocabulary and sidecar grammar are unchanged, so the
   gate cannot see whether an original was opened; the ledger's source column shows it to a
   reviewer. **Private mode is excepted:** no page image is opened for a private-mode person, and
   those rows are ledgered from the text layer with an advisory note. The operator-approved redacted
   raster, which `CLAUDE.md` lets stand for the original, is not used: approved sets live outside
   the person's tree, and the protocol requires its integrity gate immediately before any model
   pass, a step the verify does not own. The exception fails safe; for those persons a misreading
   that survived intake stays uncaught here. Cost: image reads per verify, growing with the scanned
   sources behind the handout's values (figures: point 11).

10. **A FAIL routes its repair, and the record heals before another round** (operator-directed,
    2026-10-02). In real care sessions handouts took many full verify runs (about 5 M tokens), and
    one clinician handout failed four rounds running and was left unsealed. The verifier was right
    each time; what followed was weak. The instructions said "fix the handout, re-run" and nothing
    about the record the error came from, so a value corrected only in the handout would return in
    the next one, and nothing used the evidence grades, which already decide many conflicts. The
    same sessions logged one authoring error three times: an absence claim ("not on file") written
    while the person's sources held the value, once feeding a dosing argument. The operator: instead
    of failing the handout, "it should have corrected it and the underlying files based on higher
    grade evidence now available", and the system should "proactively heal the record rather than
    run a fifth round of certification". Decided:

    1. **Fix class.** Every MUST-FIX finding carries one: `record` (the error started in the record
       and the handout repeats it), `handout` (only the handout is wrong) or `operator` (only the
       operator can settle it; an identity mismatch is `operator` and still a hard stop). The
       verifier stays read-only; statuses, severity, the verdict rule and the sidecar grammar are
       unchanged.
    2. **Repair loop.** The author repairs `record` and `handout` findings without asking, the
       record first, asks each `operator` item in one plain question, tells the operator which
       record facts changed, and verifies again once no question is open. An identity mismatch stops
       all repair until the operator has reconciled it. This replaces the **N = 2 then escalate**
       threshold: after the second FAIL, and each one after it, the operator is asked whether
       another round runs, with what is still open and the round's rough cost. A FAIL is never
       terminal by itself.
    3. **Grades settle conflicts**, by the care contract's provenance clause (added to `CLAUDE.md`
       separately, handover 51, to reach CARE in the same release): a handout stating a value an
       original outranks, or presenting a care-material fact the original settles as an open fork,
       is `contradicted` and repaired before the seal, since a sealed handout is immutable.
    4. **Absence claims.** The author searches the person's text layers (`*.md`, which the
       private-mode read guard admits) before an absence claim about a measurable fact stands; the
       verifier may run the same search for that one fact, a narrow exception to point 6's bounded
       completeness.
    5. **Author pre-flight.** The SOP's self-audit becomes a short checklist of the recurring
       must-fix classes (`HANDOUT-SOP.md`, step 4).

    Every round was to stay a full fresh read (*Alternatives considered*); point 13 changed that for
    later rounds. **Limits:** the fix class is the verifier's judgement, so a `record` fix still
    reads its source first; an absence search reads text layers, so a fact a transcription dropped
    or garbled can still hide. Since closed: a misread text layer has a sanctioned correction path
    (*Correcting a filed transcription*, ADR-0037 §13), and recording an operator-directed omission
    (handover 50, finding 7) is settled by point 13.

11. **Two cheap cost fixes before any reuse machinery** (operator: "cheap fixes, then measure",
    2026-10-02). Measured on two real care sessions (19 verifier runs): a run starts at about 75 K
    tokens of context and grows to 160–440 K, mostly from originals opened during it (about 30% of
    all steps); 7 of 13 runs in one session fell back to the multi-turn mode, at about twice the
    steps, because the bundle exceeded its 250,000-byte ceiling; most PDF originals were opened
    whole. (1) `TABULARIUM_BUNDLE_MAX` defaults to 600,000 bytes: the ceiling was a budget, not a
    safety bound, and the fallback costs more than the larger bundle. (2) The verifier opens only
    the page of a PDF that holds the value, with fallbacks for a text layer without page markers;
    the duty to inspect the original is unchanged. Reusing confirmations across runs (a hash-bound
    record of which canonical lines matched which original) was designed and deferred.

12. **The verifier reads its standing prompt itself** (operator-approved context cut, 2026-10-11).
    The prompt moved into `handout-verifier-prompt.md`; the session that wrote the handout sends a
    fixed three-line brief naming the file, plus the input block, and never loads or copies the
    prompt. Why: the author paid about 3.4 K tokens to read the prompt and as many again to retype
    it into every verify call, and a verbatim retype can drift. Cost: the prompt-cache prefix a
    same-encounter pair of verifies shared is lost, pricing only and under 1% of one verify.

13. **A later round re-checks what changed; a recorded omission is not a finding** (operator,
    2026-10-27, after the break test in *Reviews*). Care transcripts: one handout's loop ran a dozen
    full rounds, about four hours and 4–5 M tokens, until the operator capped the rounds and asked
    for change-only checks; the same checkers also caught real record errors; and a drug-label
    warning the operator had chosen to leave out failed round after round (roadmap D3). Under the
    simplification review of that day — on Opus 5.5 plain Claude matched Tabularium on harm, so a
    rule that blocks sound inference is cut or becomes a cue — the operator reversed point 10's
    rejection of diff-only re-verification, the ruling of 2026-10-04 and the roadmap's "rejected as
    unsafe" (D8). That ruling (operator, 2026-10-04) had followed a care session's operator-approved
    re-verify of only the changed lines: recorded, not formalised, since the seal gate accepts any
    passing sidecar for the bytes and cannot tell such a run from a full one; every re-verify was to
    stay a full read.

    1. **Later rounds.** The first round stays a full check, and each ledger row quotes its heading
       and whole sentence verbatim. A later round reads this handout's own earlier sidecar as a
       ledger, never as evidence. It re-checks unmatched or removed sentences, every earlier
       MUST-FIX, and anything a change to the handout, the record or its sources could make wrong;
       other rows are carried forward, marked `carried`, only while their support still stands (the
       prompt's *Later rounds*). Without a complete readable earlier sidecar, it checks everything.
    2. **Omissions.** An item the record says the operator chose to leave out of this handout, or of
       every handout for its audience, is not a finding — any item, a drug's official warning
       included; a sentence the omission leaves misleading still is. The author records the choice,
       dated, in `profile.md`; an omission not recorded as theirs is still `fix: operator`. D3
       closes.

    Unchanged: statuses, severity, the verdict rule, the sidecar front matter, the seal gate and the
    round question after the second FAIL. **Limits:** an error in unchanged text that the first
    round missed now reaches the seal — the one recorded late catch, a false absence claim, is a
    class the author searches for before the first round (point 10), but an unchanged one is carried
    after it; a sentence naming a changed drug only by its class rests on the verifier seeing the
    link; the seal gate cannot tell a carried row from a checked one, only the ledger can; a handout
    can go out without a label warning by the operator's recorded choice, while the pack leaflet
    still carries it. No eval case covers a later round (EV-12 is a first round).

### Admission tests (guard-admission)

- **Retiring L11, 2026-09-27:** (1) the harm is at the seal, not the draft; (2) L11 blocked the
  operator's own multi-session drafting; (3) the seal gate acts at the point of harm; (4) removal
  costs no protection the gate and L15 do not already give; (5) one lock, one home.
- **Opening originals, 2026-09-29:** (1) a wrong dose or value reaching a clinician in a sealed
  handout, by a path the eval has already seen start; (2) the verifier reading the operator's own
  scans blocks nothing of theirs; (3) it acts at the hand-over gate; (4) handouts are rare and the
  harm alters care; (5) no new control — a sharper method inside the existing verifier.
- **Routing the repair, 2026-10-02:** (1) wrong facts written into the record cost verify rounds and
  could return in later handouts, and a handout was left unsealed after four rounds with no decision
  path; (2) nothing refuses the operator — they decide on further rounds; (3) it acts at the verify
  before the seal and at the record write; (4) no new step per run beyond one targeted search per
  absence claim, against fewer rounds — expected, not measured; (5) no new control: a routing field
  and a repair loop inside the existing verifier, the pre-flight replacing the self-audit.

### Reviews and break tests behind the decisions

- **The bundle, 2026-07-26:** three adversarial rounds and a separate four-lens audit exposed both
  boundary defects and ordinary shell failures; the resulting constraints and the hardening ceiling
  are recorded above, and the repairs live in the assembler's header and tests. **Lesson:** three
  rounds hunting exotic same-user attacks missed a plain shell-quoting bug that a routine filename
  triggered (fixed with `set -euf`; noglob is load-bearing).
- **Codex review of #96, 2026-10-02:** the first draft made a care-material fork advisory and
  corrected the record after the seal (point 10), and had no fallback for a text layer without page
  markers (point 11).
- **The break test for point 13, 2026-10-27:** four Opus agents, 23 synthetic repair cases, three
  wording rounds. One agent wrote the cases with expected verdicts; a fresh agent per round applied
  the text literally. Round one's gaps (a cut quote, exchanged headings, a removed sentence, a
  record change without a log line, an older handout's sidecar) were closed by round three with
  whole-sentence quotes under headings, "changed or removed", "the record or its sources" and "this
  handout's own".

### Other rulings and records

- The 2026-10-11 drift sweep is folded in (the pre-flight is the SOP's step 4; what the selftest
  keeps: its header). The SOP's rationale paragraph was cut that day; this ADR keeps the why.
- Each limit a reader needs is stated with its decision above or in the owning doc; the operator's
  revisit triggers are kept on the development side.

## Alternatives considered

- **An LLM inside a guard** (rejected 2026-07-05): it breaks the deterministic guard model.
- **Verifying the PDF instead of the Markdown** (rejected 2026-07-05): OCR of the tool's own output
  adds noise, and the Markdown is the source of truth.
- **Gating on advisories** (rejected 2026-07-05): alert fatigue erodes the green signal (cf.
  ADR-0018 on L3).
- **Plain `ln` for the bundle publish** (proposed by the (d) audit; rejected, recorded because the
  reasoning matters): `ln` and `mv` treat an existing directory at the destination as "put it
  inside", so the finished PII bundle could be stranded while success is reported; only raw
  `link(2)` is exact-path and fails closed. Simpler is the tie-breaker, never the trump card.
- **Diff-only re-verification** (rejected 2026-10-02): later full rounds caught real errors earlier
  ones missed (a false "no blood tests after <month>" while a later blood test was on file); not
  re-opening already-confirmed originals was left to a separate cost design (handover 50, finding
  13). Not a supported mode on 2026-10-04; adopted for later rounds, bounded, on 2026-10-27 (point
  13).
- **A verifier that edits the record** (rejected 2026-10-02): the checker would become the author.
- Set aside with their reasons in the points: delta handouts by default (7), the approved redacted
  raster as a private-mode person's original (9), reusing confirmations across runs (deferred, 11).

## Consequences

- No handout is sealed without a fresh PASS/0 sidecar for its exact Markdown bytes, and L15 binds
  what was sealed; drafts may wait unsealed across sessions with the board green.
- A rendering fault cannot ship silently: build-QA halts or falls back to a plain-text handout.
- The verify stays the expensive step (figures in points 6 and 10–13); points 5, 6, 11, 12 and 13
  keep its rounds few and cheap.
- Verified by `tools/handout_attest/test_attest.py`, the renderer and bundle bites in
  `checks/selftest.sh`, and EV-12 for point 9.
