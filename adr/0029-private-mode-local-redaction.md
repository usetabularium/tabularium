# ADR-0029 — Private mode (experimental): an operator-designated identifier never transits the API; local redaction + human gate before any model pass

- **Status:** Accepted (experimental) 2026-07-04; v2 record half accepted 2026-09-30, frozen
  2026-10-04, unfrozen for real persons 2026-10-28; v2 masking half proposed 2026-09-30, gated and
  frozen 2026-10-04; superseded in part by ADR-0062 2026-11-05 (point 7's fixed residue shape), and
  by ADR-0068 2026-11-07 (point 13.2's filling at the terminal), by ADR-0072 2026-11-08 (case
  dates on the registry), and by ADR-0075 2026-11-09 (points 13.1–13.3: the v2 tag, `dob=exempt`
  and the cutover date; one private mode).
- **Date:** 2026-07-04
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

When private mode was first needed, the operator mandated that a patient's government identity
number must never reach the AI service, while still wanting full AI-assisted Stage-1 ingestion of
the patient's scanned documents. Every LLM or vision call transits the API, so prompt discipline
("don't repeat the number") cannot meet the mandate: the number must be **absent from the bytes the
model receives**. It was run as an explicit experiment with an operator-set priority: analysis
quality outranks the privacy experiment, and if masking would hurt the record, the conflict is
surfaced rather than the record degraded silently.

## Decision

Private mode is a per-person, per-identifier-class setting, marked `⟨never-API⟩` in the person's
`profile.md` → Identity. What holds now: `tools/private-mode/README.md` and its `topics/`,
`tools/claude-hooks/README.md`, `checks/README.md`, `checks/topics/relay-and-export.md`,
`_templates/INTAKE.md` and the filing procedure (`_templates/person/med/sources/README.md`).

### v1: the identifier off the API (2026-07-04)

1. **Pipeline order is the feature.** No page image or extracted text is shown to any model until
   (a) a **local, non-LLM** pass (poppler render, tesseract orientation and TSV, detection,
   ImageMagick masking) has masked the identifier, (b) an **iterative verify loop** (re-OCR the
   masked raster, remask survivors wider, repeat) has converged, and (c) the **operator has
   eyeballed** the redacted rasters. The model works only from them; the original stays local, the
   untouched grade-A evidence. The loop exists because OCR is non-deterministic on noisy scans: the
   read behind pass N's mask can leave a fragment pass N+1 reads again (reason recorded 2026-10-11).

2. **Detection is prior-driven and generous.** Three rules: the identifier **prefix derived from the
   date of birth** (the scheme encodes it, so detection is near-deterministic when the profile has a
   DOB); the scheme **checksum** over any candidate digit window (about 10% false positives on
   arbitrary windows); the printed **label's proximity**. Over-masking is the chosen failure
   direction: with the gate and the untouched original an over-mask is recoverable, an under-mask is
   not once bytes leave the machine. Label proximity masks but does not drive convergence, so a
   label with an unreadable value fails closed (`LABEL_NO_CANDIDATE`) instead of spinning the loop
   (reason recorded 2026-10-11). The rules live in `redact_ids.py`; removing one is a new decision.
   Which scheme's rules apply to a person: ADR-0062.

3. **Date-formatted tokens are excluded from detection.** A printed DOB holds the prefix digits but
   is never the identifier, and it stays model-visible on purpose: person-separation reconciliation
   depends on it. Without the exclusion the first run masked DOB rows and, through line-digit
   concatenation, ate adjacent content.

4. **Fail closed.** A page with a seen label but no maskable value, near-empty OCR, or a verify loop
   that did not converge **waits for the operator**: it is never sent unredacted, and an unreadable
   page is never "just looked at" with vision. An identifier local OCR cannot read (handwriting,
   stamps, blur) is the human gate's to catch, explicitly.

5. **Auditability.** The redacted rasters, the exact bytes the model saw, are kept under
   `med/sources/_redacted/<filed-name>/` (date-named for L6). Tool output and logs carry
   coordinates, reasons and flags, never recognised text or digits. Every `.ocr.md` records the
   redaction provenance, and an end-of-run assert greps every transcript for prefix- or
   checksum-valid tokens.

6. **Home.** Engine, procedure and synthetic self-test in `tools/private-mode/`; the setting in
   `profile.md` → Identity; the intake checklist branches to it. On 2026-10-11 (operator) the
   procedure split by role, since every private-mode session read all 460 lines: the README for
   every session, the masking runbook and v2 in `topics/`, each read before its task.

### The self-reference trap, applied

The publish firewall's identity class includes the identifier scheme's local name as a token, in any
case. So every tracked or publishable artifact of this feature names the class generically
("national identity number", scheme key `pl-id`) and takes the printed label **only as a
command-line argument at invocation**. Test identities are synthetic. The concrete label may appear
only in deny-listed local files.

### Hardening, and the routes closed since

7. **Guard L10: the identifier is never recorded in the tree** (2026-07-05). L10, every session and
   at the commit gate, reds a **contiguous 11-digit run** in the derived text of a person whose
   profile carries the marker; originals legitimately hold the identifier and never leave the
   machine, so they are out of scope. Choices: **a plain run, not checksum-validated**, since an
   OCR-mangled identifier fails a checksum yet must red (over-red beats under-red); **a dated
   waiver**, `⟨not-an-id: verified YYYY-MM-DD⟩`, a deliberate, audited act; **no echo**, no scheme
   name or real digit in the shipped guard and no matched run printed, and since 2026-07-17 no file
   or line in its findings or the L13 companion scan's, because guard output is model-visible and a
   filename can carry the identifier; **fail closed** on a marker in a person tree with no
   `profile.md` anchor. DOB-prefix matching, for a shorter residue, was deferred: it needs a
   per-person DOB parse, and the plain run covers the dominant residue shape. Revisit at the first
   real L10 false negative, or a second private-mode person. The run's shape per person: ADR-0062.

8. **The run-state contract and byte-bound approval** (Tier-S, 2026-07-10 to 2026-08-09). A gap
   review found that stale or unverified bytes could pass as a run's output (unchecked return codes,
   reused directories, exit 0 under every fail-closed flag): a hole in points 1 and 4 at the process
   boundary. Decided:
   - **Explicit states** (2026-07-10):
     `NEW → LOCALLY_PROCESSED → AWAITING_OPERATOR → OPERATOR_APPROVED`. `redact_ids.py` stops at
     `AWAITING_OPERATOR`; a separate `approve_redaction.py` records the operator's approval as an
     attestation, never inferred from a green exit, and only an approved artifact may reach a model.
     Checked external calls, run-scoped directories, atomic promotion that never deletes a prior
     set; any flag or error fails the whole invocation. The tests became a `unittest` suite run in
     CI.
   - **Bound to bytes** (2026-07-14): a strict, versioned schema; real-calendar DOB validation; an
     unparseable orientation held, never read as 0; approval bound by a hash per page;
     `verify_approved.py` as the **mandatory** gate re-hashing every page just before use, since a
     directory name or an `approval.json` is never authorization; an **opaque, content-derived
     document id** on every model-visible surface, because a filename can carry the identifier and
     shell output transits the API (a rerun of the same bytes lands under the same id and supersedes
     the prior set).
   - **Later:** approval bound to the current redacted generation, the CLI a pre-consumption check
     only (2026-07-17); special files refused (2026-07-19); one consumption path,
     `load_verified_pages()`, hashing the very buffer it returns, from a one-time input snapshot
     (2026-08-09).
   - **No MAC** (2026-08-09): the gates detect accidental and concurrent tampering; a same-user
     writer who rewrites everything together is outside the threat model, since no external trust
     anchor exists and a MAC keyed beside the writable state would be theater.

   Mechanics: `tools/private-mode/topics/pipeline.md`.

9. **The token registry, and the identifier's own file** (2026-09-05 to 2026-09-16). On 2026-09-05 a
   development session's bounded read of the export allow-list overran and printed the whole token
   registry, the identifier included, into a model session; no care record or export was involved.
   Lessons: the registry is a credential no session reads; the transcript should be deleted (it was
   kept: operator, 2026-09-09); the root cause is the registry living in the development
   tree, which ADR-0050 removed. Then:
   - **2026-09-06:** a `PreToolUse` read guard (ADR-0050 Part A1): a discipline aid against the
     honest slip, not an enforcement boundary.
   - **2026-09-07:** the firewall-synchronisation duty (Consequences) targets the registry outside
     every work tree, edited **by the operator, by hand, outside any model session**; a session may
     say what to add, never opens the file. An unsynced class now surfaces only at the flip-time
     export or the relay scan, so the sync is a standing habit. The DOB-derived prefix is identity
     even though the full number is never recorded.
   - **2026-09-16** (the operator's decision of 2026-09-14; ADR-0050 point 9): tokens that are the
     identifier or reveal it live in **its own owner-only file** beside the registry, edited the
     same way: the only content still secret from sessions, and the one the read guard protects once
     the split is verified. Names and the model-visible DOB forms stay in the registry.

10. **A private-mode session; chat attachments refused there and nowhere else** (operator,
    2026-09-17; handover 40). A care session received scans attached to the chat and asked for them
    in the intake tray instead. The handover recommended a household-wide **inbox-first** rule,
    arguing that only one uniform habit keeps the private-mode check ahead of the exposure. The
    operator inverted it: the ban applies **only in a private-mode session**, declared with
    `/private` (ADR-0053's mechanism: a skill invoked in the operator's own turn), installed into
    every instance as a care-side declaration. Steelmanned before accepting:
    - **Why the inversion holds.** The uniform ban taxed every ordinary session to protect one
      experimental mode for one person, and under either rule a session cannot refuse an attachment
      already sent. What the ban bought was a habit; `/private` moves it to where the risk is and
      gives it a ritual: the session's first output restates the posture. Ownership by placement and
      grade A survive: a session files an attachment only from an on-disk path, byte for byte, into
      the folder of the person the session is about (a combined session asks first). The
      ordinary-session route moved on 2026-10-25 (point 14).
    - **A declaration cannot un-send an attachment;** it is intent, not a boundary, and the tooling
      keys on the marker. The four states (declared or not, marker or not) each have a set response.
    - **Where the rules live** (operator's review of PR #15, 2026-09-19; the keystone stays thin):
      the protocol in `tools/private-mode/README.md` → *Opening a private-mode session*, the
      ordinary-session rule in the filing procedure.
    - **The posture is taken from the marker** (2026-10-25): a session that reads it takes the
      posture undeclared, since the posture only restricts (`/architect` grants). `/private` stays,
      optional, for loading it before the person is named or a file arrives. Why: the operator found
      declaring every session of an already-private person a needless step, easy to forget.

11. **The locator rule: guard output names the file, except in private mode** (operator-approved
    guard sweep, 2026-09-27). A red that withheld its locator named no file, and the only reason to
    withhold is this ADR's: a filename can carry the identifier. Every guard prints the
    tree-relative path, withheld only (a) inside a person folder whose profile carries the marker,
    or (b) where the owner cannot be established while anyone is private-mode or has an unreadable
    profile. Board-wide, because a mis-named scan printed by L6 was the live route by which an
    identifier-named file would have reached the API. Source-derived diagnostic details are withheld
    for the same owners, since L10 cannot undo an earlier echo; residue findings stay category-only.
    Admission for the diagnostic values: (1) an identifier in L1/L4/L5/L7/L16 output reaches the
    API, unseen by L10; (2) only output changes; (3) `loc_detail()` withholds it as emitted; (4)
    only private and unknown owners lose excerpts; (5) one helper reusing `loc()`. L5 goes further
    while any person is private-mode: since 2026-10-25 (`ef0e373`) it reports hits in person folders
    and `reference-library/` as counts, withholding matching lines and their file names, because
    either can carry the identifier (`checks/README.md` → *Locator rule* and the L5 row).

12. **Profile first, and the read guard over a private-mode person's originals** (2026-09-29). A
    contained experiment (sealed eval sessions; a synthetic marked person, a new scan in her intake
    tray, a filing task, no `/private`) found sessions opening the unredacted scan: Sonnet 5 in 4 of
    6 under both the old and the slimmed keystone, Opus 5.5 in 1 of 4. The mechanism is batching:
    the scan was read in the same step as the profile, so the marker arrived after the page was
    sent. With the profile read first, in a step of its own (`CLAUDE.md` → *Context*; the filing
    procedure's step 0), Sonnet 5 opened it in 1 of 6. **Prose narrows the path but does not close
    it.** So a candidate control was proposed and, on the operator's decision, built the same day:
    the read guard refuses recognised reads of a marked person's originals (everything in
    `med/_inbox/` and `med/sources/` but Markdown and redacted rasters) by any tool, connectors and
    uploads included, while listing, filing, hashing, the pipeline and the ownership ledger run.
    Admission: (1) the harm is this ADR's own, observed; (2) for an agent, reading is sending; (3)
    at the read; (4) it blocks only reads the setting already forbids; (5) it extends the existing
    guard.
    - **Interpreter code is judged by its literals** (2026-10-02). Three edit scripts naming no
      original were refused on 2026-10-01: the guard took every word of a string literal as a path
      (the prose word *patients* resolved to the folder). Decided: such code is judged by each
      literal whole and each word holding a `/`; a literal without one is a name, not a glob; shell
      code keeps the word-by-word reading. Every denied row still denies, and a denial names the
      rule class that matched, never the path. Admission: the same harm; friction met three times in
      one day removed; no new control.

### Private mode v2 (2026-09-30)

13. **Routine personal details off the API: a pseudonymous working record and broad masking at
    intake** (proposed 2026-09-30, handover 46; revised that day after review on PR #79). **Care
    comes first** (operator, 2026-09-30): v2 reduces routine disclosure; where quality or patient
    safety is at stake it makes a transparent exemption instead of withholding (age is the
    operator's example), and it stays light to operate: choices set once, one approval step,
    existing tools extended. **Why two halves:** masked scans alone do not make downstream work
    private, since every session reads `profile.md` and later documents repeat it. So v2 is a
    **pseudonymous working record**, independent of the local-masking benchmark, plus **broad
    masking** at intake, which depends on it. Proposed gates: round 3 of the benchmark
    (`evals/local-masking/`) passes, the real-document check (13.6) passes marks the operator sets
    beforehand, and the operator accepts.

    **13.1 — Opt-in, per person, set once.** The Identity line records the level, the choices and
    the cutover date. **The `⟨never-API⟩` marker stays byte-identical**, because L10, L13, the
    locator rule and the ownership tools match it exactly; v2 is a separate tag, and a bite test
    proves a v2 profile trips everything v1's does. v1 stays, the only option below v2's memory
    minimum; **v2 never relaxes a v1 commitment.** Withheld by default: names of the person,
    relatives and contacts; the date of birth; ID, document, case, visit and order numbers;
    addresses, phones, e-mails; barcodes. Clinicians, facilities, dates of care and clinical content
    stay visible. **Age is the transparent exemption; the date of birth is presented as age**
    (operator, 2026-09-30), computed locally with its reference date at the precision care needs.
    The trade-off, stated once: an age with its date narrows identity, and a month-level age hints
    at the identifier's date-derived prefix, which a full DOB would give away. v1 keeps its
    model-visible DOB (point 3); the operator may exempt the exact date for a person.

    **13.2 — The pseudonymous working record.** Withheld values live in one local-only file per
    person, the v2 identity file, typed by the operator at the terminal without echo, inside a care
    edit session after its snapshot, which banks the file; only local tools read it. Sessions see
    the **handle**, which every path and sealed handout carries (L15): an existing person keeps
    theirs, its exposure recorded once; an alias is offered only at a new person's intake; no random
    handle, no rename. Relatives appear by role. The operator moves a v2 person's withheld-value
    tokens, by hand, into the identifier's protected file. **Handouts keep one seal on the delivered
    bytes:** placeholders in the source, a draft showing the handle for the assistant's check, a
    final render that substitutes the values, passes build-QA and is sealed (L15), and the
    operator's own look at it, since substitution can move line breaks. **A render fault halts:** a
    plaintext fallback would carry the names outside every check. No second seal, no identity
    ledger. **Pseudonymous, not anonymous:** a facility, dates and a rare diagnosis can still
    re-identify, and pseudonymised data stays personal data (GDPR Art. 4(5)); the claim stays
    exposure reduction. Out of scope: `nmed/`; the chat, where the operator's own words go as typed;
    the assistant's memory in CARE.

    **13.3 — Migration keeps history.** Cutover updates the working record (profile and
    medications); originals, bound transcriptions and sealed handouts keep their bytes. What was
    sent before is past: earlier items and snapshot copies stay readable as legacy, an older item
    can get a locally redacted derivative, and pruning old snapshots is the operator's call. No
    blanket re-key of history.

    **13.4 — The masking pipeline is the tested configuration,** the union benchmarked in PR #81
    (`redact_ids.py` unmodified, the rules, zbar, `qwen3.5:9b` with the tested prompt and settings),
    recorded as a configuration id beside the weight digest. **The model may only add masks and
    holds.** The **owner check runs locally** and raises an owner question, never a refile; **filing
    stays in the cloud**, on masked pages. **The page review stays the one approval step;** the
    schema bumps narrowly, and the approval records the policy level, so a v1 approval never
    satisfies a v2 person. The DOB is masked unless exempted.

    **13.5 — Packaging:** a local core that prints no personal detail but the exempted age, wrapped
    by the `/private` protocol; **Ollama checked for, never installed.** Every round ran on 24 GB;
    16 GB is to be measured before it is offered, and smaller machines keep v1 unless a smaller
    model passes the benchmark. At about 50 s a page
    on a current laptop (estimate), intake is a background batch.

    **13.6 — The real-document check (gate 2):** locally in CARE, on one person's documents, during
    the page review, which records per page leaks, clinically important over-masks, missed owner
    contradictions, false holds and time; a local scorer prints metrics only, under v1's egress
    rules. The evidence so far is synthetic pages, one model and one 24 GB Mac; real stickers,
    handwriting and stamps come with this gate.

    **Controls, with guard admission (1 harm · 2 operator · 3 point · 4 net · 5 smallest):**
    - **C1 — the read guard refuses a v2 person's identity file and personalised handout output:**
      the identity file by name, anywhere, snapshot copies included; and, in the shape of PR #69's
      person-scoped rule, a final render or preview under that person's `med/handouts/`, drafts
      excepted. (1) A session that reads either sends the withheld values, and sessions open what
      the rules forbid (point 12); (2) for an agent, reading is sending; (3) at the read; (4) no
      session task needs either: the assistant checks the draft, the operator the final; (5) one
      name and one rule in the existing hook.
    - **C2 — guard L10 extends to a v2 person's withheld values:** always in the profile and
      medications, in other Markdown dated on or after the cutover, legacy never; whole fixed
      strings, category-only. (1) One mask miss transcribed becomes a standing exposure, re-sent by
      every later session; (2) it fires only for a person set to v2, and reading stays free; (3) at
      the write; (4) whole values only, so a shared first name or a common street does not fire, the
      next step is L10's dated waiver, and immutable history is never forced to change; (5) L10
      extended.
    - **C3 — the tool refuses weights other than the tested digest.** (1) Ollama tags are mutable,
      and a routine pull can swap in a model that masks worse; (2) it changes what the tool runs,
      never what the operator reads; (3) before the masking run; (4) it fires only after a pull and
      names the next step, re-run the benchmark or restore the weights; (5) one comparison in the
      core.

    **Accepted in part** (operator, 2026-09-30): the record half goes ahead of the masking gates,
    since it does not depend on the benchmark. **Accepted for building:** 13.1–13.3 with C1 and C2.
    **Still gated:** 13.4–13.6 and C3, until round 4 of the benchmark passes on two fresh test seeds
    (operator, the same day) and the real-document check passes. Synthetic persons first, then per
    person by the operator's choice. **Interim claim:** until broad masking lands, each new scan
    still exposes its names once, at intake; this half removes the repeated exposure, the working
    record every session reads and what is written from then on. `nmed/` remains outside v2's
    accepted scope.

    **Built, frozen, unfrozen.** The record half was built on synthetic persons in four slices
    (2026-09-30 to 2026-10-01): identity file, age, snapshot copy and C1; residue scan and cutover
    (C2); sealed handouts; tokens out of the registry. No register entry is owed: the register
    retired on 2026-10-04 (ADR-0059). That day the operator froze it until the six-week board-log
    review, and the test reduction moved its bites to git history; the masking half is frozen too
    (ROADMAP F1). One v2 test pair was to return before a first real person (ROADMAP F10). On
    2026-10-28 the operator unfroze the record half for real persons, for release v0.63.0, with that
    pair restored; the same day the operator judged the reproduced e-mail hyperlink harmless and
    closed it without a change. Mechanics: `tools/private-mode/topics/kept-details.md`.

### Intake routes (2026-10-25 and 2026-10-26)

14. **In an ordinary session a document is dragged into the chat; a folder ask carries a link**
    (operator, 2026-10-25). *This point concerns ordinary intake, not private mode;* it is recorded
    here because it revisits point 10's route. A care session had asked the operator to put a
    document in the tray, naming the folder without a link; the operator called placing files by
    hand in an open session obsolete. Decided:
    - **Route.** In an open session, ask for the file dragged into the chat (or the tray, if the
      operator prefers); the tray stays for documents between sessions, for batches and for a
      private-mode person (point 10). Sending it in that person's session says whose it is; a
      session of several people asks first; `--confirmed` still needs the operator's explicit word.
    - **What the client hands over** (Claude Code desktop 2.1.299, tested with non-health files): a
      dragged file arrives as **its own on-disk path**, so `cp -n` and the hash check file the exact
      bytes at A; a type the client cannot read passes as the path only. A pasted image is the
      client's **own copy**, sometimes reduced (one seen at 2,000 px, as WebP): an original (A, like
      a phone photo) when it shows a document's page, its illegible values asked for as the
      document's own file. Another AI's answer stays an inference (C); pasted text is the operator's
      report (B).
    - **The link rule** is general: any folder the session asks the operator to use gets a clickable
      link (`CLAUDE.md` → *Reporting back*). The ask sits in `CLAUDE.md` → *Keeping it current*,
      because a session asks for a document before reading the filing procedure, which keeps the
      method.
    - **Coverage.** No guard: the failure is in a reply, which no board check sees; EV-15 measures
      it in the full suite, since a wrong ask is visible to the operator.
    - **Steelman.** The uniform inbox-first rule (point 10) keeps one habit for everyone, but the
      ask does not need it: a session reads the profile before any document, and the posture
      switches on at the marker.
    - **If the client changes:** should a dragged file stop arriving as its own path, the tray is
      the route again for a PDF; should a misreading be traced to a reduced pasted image, a
      screenshot drops to a reading aid.

15. **A private-mode drag that sent only a path** (operator, 2026-10-26). Point 10's script said
    "the exposure has already happened", false when the client passes a file it cannot display (a
    video, a Word file) as its path only: the name and location reached the service, the content did
    not. Decided: the session says what reached the service (a name showing the identifier takes the
    containment steps instead, and the operator renames the file before the tray), never opens or
    copies the file, files nothing from it, links the tray, and still records and relays the
    occurrence. **Rejected:** the session copying a path-only file into the tray: byte-safe, but it
    makes the chat a route for some file types, the operator cannot know which in advance, and the
    one-route habit is what the setting rests on. The operator confirmed that no drag is ever
    invited for a private-mode person and point 14's tray link stays.

### Reviews and break tests behind the decisions

- **Point 8:** a gap review, a two-round red-team, a hand-back review and a red-team (2026-07-10 to
  2026-08-09); the last found a refactor that reopens a path and a deleted streaming bound invisible
  to the suite, and negative controls now catch each.
- **Point 12:** two review rounds (Codex, then an independent reviewer) closed the bypasses they
  found. **Point 13:** at review, PR #81 passed every masking mark and failed the owner check, 12
  of 15.
- **Point 14:** 26 adversarial synthetic situations, verdicts written from the operator's rulings,
  sorted blind from the rule text by a fresh agent per round: 24 of 26 in round 1, with four wording
  gaps fixed; every verdict in round 2. Three older gaps it found were settled separately: video and
  office files in transcription (ADR-0023), a page naming another person (ADR-0037 point 15), a
  private-mode drag that sent only a path (point 15). **Point 15:** two blind rounds, 25 of 25.

### Other rulings and records

- The 2026-10-11 drift sweep is folded in above.
- Each limit a reader needs is stated with its decision above or in the tool's README; the
  operator's revisit triggers are kept on the development side.

## Alternatives considered

- **Prompt discipline** ("don't repeat the number") — rejected: the number must be absent from the
  bytes (Context).
- **A household-wide inbox-first rule** (handover 40) — rejected for the inversion (point 10), and
  not needed for the ordinary-session ask (point 14).
- The other rejected or deferred options are given with their reasons in points 3, 4, 7, 8, 12,
  13.2, 13.3 and 15.

## Consequences

- **Proven feasible (n=1):** the first run redacted 9 of 9 documents, converged and gate-passed;
  every numeric and categorical cross-check passed on the redacted rasters; the identifier never
  left the machine. Two gate interventions (checksum false positives unmasked; an over-masked page
  rebuilt tighter) were by design. The mode remains experimental.
- **Bounded scope, stated honestly:** one identifier class per run; other personal details transit
  the API as in normal operation, except what v2's record half withholds; the ingestion path only;
  an identifier rendering local OCR cannot read relies on the human gate; the read guard covers
  Claude Code only. The published README labels the mode experimental and claims only exposure
  *reduction*.
- **A hold-point:** private-mode ingestion is two-touch (run, operator eyeball, model pass), the
  backstop for the one channel automation cannot see.
- **Firewall-synchronisation duty, continuous:** a private-mode person's identifier-derived tokens
  (DOB formats, the prefix) join the token classes, as every handle does at scaffold
  time; the prefix and a v2 person's withheld values go to the identifier's own file (points 9,
  13.2).
- **Verified by** `tools/private-mode/test_redact_ids.py` and `test_identity.py`,
  `tools/claude-hooks/test_registry_guard.py`, the L10 bites in `checks/selftest.sh`, and CI.
