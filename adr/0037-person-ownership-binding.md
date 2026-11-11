# ADR-0037 — Person-ownership binding (source manifest + integrity guard)

- **Status:** Accepted 2026-07-11.
- **Date:** 2026-07-11
- **Deciders:** operator (+ assistant; Tier-S: an independent red-team before a built guard or
  script lands)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Person mix-up — one person's dose, lab, condition or device landing in another's record — is the
highest-stakes error in this system (`CLAUDE.md`; ADR-0002). In July 2026 it was guarded by session
discipline and by guard L5, which greps each person's assistant-authored Markdown for another
person's folder handle, `med/sources/**` exempt (ADR-0028).

L5 cannot see a fact copied without the handle, nor a scan filed under the wrong person, which
carries a real name in the exempt evidence layer; the public description ("person-separation
enforced structurally") claimed more. Ownership rested on the folder a file sat in, which nothing
verified: there was no manifest, record ID, hash inventory or identity reconciliation.

A structural scan on 2026-07-11 (metadata only) found many sources, a large share of them
`.ocr.md` transcriptions. One hash under two people drove the
migration choice (point 6) and proved to be README boilerplate (point 7).

## Decision

Add an ownership-binding layer that makes mechanically detectable wrong-person filing loud, while
(a) raw evidence stays byte-for-byte unchanged, (b) it stores no clinical content and no real-name
registry, and (c) a deterministic guard never claims to have read identity off a scan. L5 stays, as
a handle-contamination lint.

The design was accepted in steps on 2026-07-11: Option B (point 6), ALT-C (point 7) and the
reconciliation of point 8. The operator narrowed the build to a lean MVP on 2026-07-15 (point 9).
What holds now: the L13 row of `checks/README.md`, the docstrings of `tools/person_ownership/`,
`_templates/INTAKE.md` and the filing procedure `_templates/person/med/sources/README.md`.

1. **One append-only manifest per person, not sidecars.** `patients/<handle>/med/MANIFEST` sits
   beside `med/sources/`: inside, it would collide with L6's naming rule in an immutable evidence
   layer. A correction appends a superseding record, never an in-place edit (as `INDEX.md`,
   ADR-0033). One ledger keeps history in order, lets a cross-person check read one file per person,
   and fits the single-writer-per-person discipline (ADR-0002; ADR-0036 D1). Its metadata
   concentration is acceptable because it holds no clinical content and stays inside the PII
   boundary: `patients/` is gitignored and never exported (ADR-0013, ADR-0017); sidecars would hold
   the same metadata in more files.

2. **Metadata only.** A record holds the source path and SHA-256, the person's record ID,
   acquisition metadata, identity-review provenance (status, reviewer, a dated note of its basis),
   1:1 derivative links and supersession fields (`tools/person_ownership/schema.py`). No document
   type: even "discharge summary" edges toward a clinical signal. The provenance note carries no
   name or clinical content, by convention. Derivative links cover 1:1 transcriptions only: analyses
   and handouts are many-source syntheses, so analyses rely on L5 and handouts are locked at the
   seal (ADR-0034, ADR-0039; L11 retired 2026-09-27). The design's four identity statuses were
   `operator-confirmed`, `document-identity-checked` (a page marker reconciled at intake, never
   stamped from folder position), `bundle-linked` and `legacy-folder-only` (folder position only:
   not verified ownership, the migration default); two are built (point 9).

3. **An opaque person record ID, never the handout tag.** 32 cryptographically random lowercase hex
   characters, so a malformed value is checkable, encoding no name, handle, birth date, diagnosis or
   order (a sequence leaks enrollment order and family size). It lives in `profile.md` → Identity,
   every record must match it, and it never prints. The ADR-0033 `<PPP>` tag prints on third-party
   documents, so reusing it would leak the integrity key. Rotation is break-glass only, for
   suspected exposure of the value: generate a new ID, append superseding records for those that
   carry the old one, and update `profile.md` last, once no active record carries it. Handout-tag
   rotation is independent.

4. **What the guard proves, and what it does not.** Guard L13, fail-closed and host-portable
   (ADR-0020, ADR-0021), proves that every current source under `med/sources/**` has an active
   record, its bytes match the recorded hash, the person ID matches the profile, each 1:1 derivative
   binds, and the ledger is well formed. **Boilerplate is not evidence:** `README.md` and
   `CAPTURE-GUIDE.md` at the root of `med/sources/` are identical across people by design and exempt
   by name, as in L6 (ALT-C, point 7). Required wording: *hash/person-ID consistency is mechanical;
   the underlying identity judgment remains operator/intake provenance.* With no vision in
   `check.sh` and no real-name registry (ADR-0028), the guard does not decide whose a document is; a
   single copy filed once under the wrong person is intake's responsibility, not an L13 event.
   Identity status is provenance, not a pass/fail axis: a page without an identity marker is not red
   (a documentation gap is not a care gap), and unverified items form a non-blocking review queue.

5. **Paths and renames.** Paths are person-root-relative and NFC; an absolute, `..`, root-escaping
   or symlinked path is red. A rename keeps hash, person and identity; a multi-document scan is one
   source; a split was to ride `bundle-linked` provenance (deferred, points 9 and 11).

6. **Migration: Option B, by a deterministic script** (operator, 2026-07-11). **Option A**,
   immediate fail-closed, would keep the board red until every source was inventoried: a large
   migration under a red tree, against "never end red", at real risk of being rushed. **Option B**,
   a staged legacy queue, lands green and reds only mechanical failures (a new source with no
   record, drift, a wrong ID, a broken derivative; its design also rejected a new cross-root
   evidence duplicate, whose detection the lean build deferred, point 9), while legacy sources wait
   in a non-blocking queue worked in one-person sessions; until worked, a legacy misfiling is as
   unseen as under L5. The operator's modification: inventory and hashing are a deterministic stdlib
   tool with no LLM inference in the binding path (per-source inference is token-heavy and less
   certain than a hash), proved first on a small pilot with a timing and confidence report before
   any full run. The tool stops rather than invent certainty. Legacy sources default to
   `legacy-folder-only`; stamping one checked because of its folder is forbidden. No source byte
   changes; integrity compares sorted `relpath + sha256` lists, not archive bytes, which false-fail
   on metadata.

7. **ALT-C: medical evidence is individual, and `_shared/med/` holds none** (operator, 2026-07-11).
   Two operator inputs corrected the premises: (i) a raw medical document is virtually never issued
   for more than one person, and joint matters are coordination prose (grade C), not evidence; (ii)
   the "cross-person duplicate" was byte-identical `med/sources/README.md` boilerplate. So the
   panel's ALT-C posture is the decision: `_shared/` refers to people only at pointer level (the
   keystone, unchanged), and `_shared/med/` holds prose and pointers, never scans. A cross-root
   evidence duplicate is a misfile: the copy under the true owner stays, by the operator's judgment
   with a stated basis, and the wrong one goes; the tool never settles ownership by inference
   (ADR-0005). The rule skips the boilerplate, which would otherwise red every intake README on day
   one; its detection is deferred (point 9). Kept from the panel: from a `_shared/med/` note only
   one person's facts enter their profile or handout (R-5); `_shared` filenames stay clinically
   neutral (N-8).

8. **Reconciling ALT-C: R-3′, R-4′, N-4** (2026-07-11, under the operator's "proceed, no loose ends"
   delegation; reversible). **R-3′:** L5 is not extended into `_shared/med/`, the one place meant to
   name several people, where a handle ban makes permanent false reds. Instead (a) `_shared/med/`
   holds only `.md` prose, anything else red; (b) the identifier-residue scan covers `_shared/med/`
   text when anyone referred to is in private mode, and every manifest's free-text fields, because
   metadata-only is the whole basis for accepting the concentration. **R-4′:** a checkpoint guards
   append-only, otherwise convention over a gitignored file. It stays untracked beside the manifest:
   a tracked digest would put a patient count and its changes into shipping git history, and git was
   never the evidence layer for `patients/`. **N-4 dropped:** an orphan-`_shared`-file rule presumed
   manifests bind `_shared` prose, which under ALT-C they never do.

9. **Lean MVP** (operator, 2026-07-15; HO-10). Asked whether the design was over-built for a small,
   local, single-operator system, the operator chose the core that closes the actual gap
   (wrong-person filing, hash drift, an un-inventoried source) and deferred the parts that guard
   rare-to-nonexistent cases. **Built:** a JSON-Lines `MANIFEST` per person with an untracked
   `MANIFEST.checkpoint`; the ID in the profile; L13 delegating fail-closed to the stdlib package
   `tools/person_ownership`, with the R-3′(a) rule; the Option B migration. **Deferred to a v2:**
   the additional identity statuses, `bundle-linked` provenance chains and cross-root
   evidence-duplicate detection (boilerplate exempt). As designed (2026-07-11), a `bundle-linked`
   record's parent is an active record in the same manifest with the same person record ID and a
   stronger status (`operator-confirmed` or `document-identity-checked`), never another
   `bundle-linked` or a `legacy-folder-only` record. The built statuses are `operator-confirmed`
   and `legacy-folder-only`. Their revisit triggers live in the local register.

   **Two deliberate deviations.** The Python verifier NFC-normalizes on-disk and recorded names,
   with no on-disk rename: the design's "NFC-at-rest, byte-exact compare" was for a shell verifier,
   and on APFS the rename is a no-op. The manifest is JSON Lines, since derivative nesting is past
   awk's reach, so L13 fails closed when `python3` is absent and ownership content exists. A shell
   residue scan over the MANIFEST was reverted: a 64-hex digest routinely holds an 11-digit run.

10. **Hand-back review** (2026-07-17). Migration skips a person who has a `MANIFEST`, so no path
    added a later source, and `refresh-checkpoint` re-hashed current bytes, able to re-bless any
    rewrite. The blind refresh was disabled fail-closed, and later intake stayed red until a writer
    met three requirements: (1) prove that the old checkpointed bytes are the exact prefix of a
    strictly longer valid ledger; (2) lock and finalize both files crash-safely; (3) define removal
    and split semantics. The review also closed bounded false-green and leak edges (the L13 row):
    even a zero-record MANIFEST needs an exact checkpoint, so truncation cannot erase history; the
    field-aware private-mode scan implements R-3′(b), never reading hash or ID fields. Since
    ADR-0029's locator rule (2026-09-27), L13's reds name the path; IDs, hashes and counts never
    print.

11. **The append-safe writer** (2026-07-18). `append.py` meets point
    10's requirements. (1) It starts only from a finalized state, the `MANIFEST` matching its
    checkpoint, and appends lines to the old bytes. (2) Under an exclusive lock it replaces the
    manifest, then the checkpoint; a crash between leaves the board red, and a prefix-validating
    finalizer, replacing the blind refresh, re-blesses only an exact checkpointed prefix of a valid
    ledger: it recovers a crash and cannot bless a rewrite. (3) A `wrong-owner` retraction expects
    the misfiled file gone (the operator moved it; the tool never deletes evidence), so a file left
    behind is un-inventoried and red. `split` is refused: it needs `bundle-linked` provenance and a
    fork the ledger graph rejects. At landing each op was applied, re-verified and rolled back
    unless green; 11.1 replaced that. Ops and output rules: the `append.py` header.

    **11.1 — Tier-S red-team and hardening** (2026-07-18 to 19). The writer landed without the
    red-team ADR-0031 requires; seven bounded rounds followed, each fixed forward. The rules they
    left, with reasons:
    - **Verify before publish:** the writer runs the L13 verifier on the projected manifest and
      writes once, forward, only if green; a rejected append writes nothing. A rollback could crash
      between its two writes and leave the checkpoint ahead of the manifest, beyond the forward-only
      finalizer. This supersedes point 11's requirement-2 and correctness-model text: recovery
      covers the sole forward write of an already-verified append.
    - **The handle is jailed,** and symlinked patient, `med`, `profile.md` and lock nodes are
      refused: a traversal or link escaped `patients/<handle>`, and a linked lock locked a foreign
      inode.
    - **A rename only onto the same bytes;** a `rehash` drops an operator confirmation, which
      otherwise rode onto substituted content.
    - **A MANIFEST with no checkpoint is re-derived only when pristine and inventory-equal,** else
      left red: a rebuild re-blessed hand edits, and an unguarded re-derive laundered drifted
      sources and destroyed attestations.
    - **Manifest, directory barrier, checkpoint,** because macOS does not order two directory
      updates across a crash.
    - **The finalizer also judges the suffix,** since a hand-appended row could attest substituted
      bytes; a non-regular `profile.md` is refused before the lock, since a FIFO hung the writer.

    **Convergence and bar** (operator, 2026-07-19). Confirmed defects ran 7, 3, 3, 1 per round, each
    round finding new but less severe ones, several of them twins of earlier fixes, and the writer
    was wired into no live or automated path. The operator chose bounded rounds, blessing at no high
    or critical finding, with surviving fail-closed mediums and lows recorded as a hardening known
    issue, rather than chasing literal zero. A round whose agents failed (quota, network)
    is vacuous, never read as clean. The seventh round met the bar (0 critical, 0 high, 0 medium).
    One round-7 agent, after access denials, tried an alternate firmlink path; nothing in the
    blessing rests on its output (the incident behind the rule in `contributing/gates.md`).

    **11.2 — The parallel special-files branch** (2026-07-19 merge). Taken from a Codex branch cut
    before point 11: sources, derivatives, migration profiles and `_shared/med` files must be
    regular files, because an inventoried FIFO could block L13 or migration forever; migration's
    refusals are surfaced per person. Superseded: its checkpoint-rebuild recovery, because re-derive
    was already blessed and strictly stronger on laundering (rebuild blesses hand-edited bytes as
    they are). The merge red-team fixed three defects: re-derive removes a stale MANIFEST only after
    every fallible step; a pristine-shaped row must pass full schema validation; L13's cross-person
    ID read opens only a regular `profile.md`, because a FIFO there hung the guard.

12. **A person's first ledger: `init <handle>`** (2026-09-29). Whole-tree `migrate` at onboarding
    minted IDs and empty ledgers for everyone without one, a cross-person write from a one-person
    session (nothing clinical crossed; found in Codex's review). `init` writes only under
    `patients/<handle>/`, the handle naming exactly one real entry, and refuses over any existing
    MANIFEST or checkpoint. A MANIFEST without a checkpoint gets one of two texts, chosen from its
    bytes: remove and re-run only when it is empty, or pristine and inventory-equal (11.1); else
    restore the checkpoint, never delete the ledger. One conditional text would lead a session to
    delete an attested ledger and re-run to green. The exact-entry rule is shared with `append`,
    because `append ALPHA add` had passed its check onto a red tree on a case-insensitive
    filesystem. Used in `_templates/INTAKE.md` §1.

13. **Correcting a filed transcription: `retranscribe`** (2026-10-02). A filed `.ocr.md` is hashed
    with its original, so an edit reds, and `rehash` is for a re-scanned original. One care session
    found misreads in long-filed transcriptions: the record was corrected, the transcriptions stayed
    wrong, and every later reader, the fact-check included, met the wrong value first. The operator
    wants the record to heal. **A new op, not a wider `rehash`:** one op, one meaning. Its row
    changes only the derivative's hash and erratum count. The op refuses unless the file's dated
    erratum lines, under `## Errata`, outnumber the count last bound and one is dated between the
    record's last ledger date and today, so no correction rides on bound lines or on a line older
    than the inventory. It is an honest-mistake control, not a proof: the erratum is not compared
    with the edit.
    **Admission:** a misread re-fails every reader, and a sanctioned rewrite without a trace would
    hide what changed; the op opens a path, acts at the ledger write, costs one line per rare
    correction and adds no board guard. Procedure: the filing procedure → *Correcting a filed
    transcription*.

14. **Arrivals together, late transcriptions, pairing, large originals** (2026-10-02): frictions
    from one care session whose workarounds moved evidence or bypassed a check.
    - **`add` takes several `--relpath`,** all or nothing: two sources filed together were each
      refused alone, and the way through was moving evidence back to the inbox.
    - **`transcribe`** (KI A65 (b)) binds a first transcription written after its original was
      inventoried, a new op for point 13's reason; it and `retranscribe` batch too. No row may
      supersede a wrong-owner retraction, which would bring back a document moved to its owner.
    - **The private-mode residue scan** dates a transcription bound by `transcribe` or re-made by
      `rehash` by that row, never before its original's filing, so new text after a cutover is
      scanned.
    - **Pairing** (KI A66): a transcription written under another document's name had hashed as a
      consistent pair. L13 requires each `.ocr.md` to sit beside one same-stem original, be bound to
      it and, when its front matter carries `filed_as:`, name it exactly.
    - **`tools/original_view`:** one page of a large original as a light JPEG outside the
      repository, refusing a private-mode person before touching the original.

    **Admission:** batch ops open paths. Pairing: a misattributed transcription re-misleads every
    reader; the check acts at the write and on the board, reds only a real mismatch (a missing
    `filed_as` is not checked) and lives in L13. The viewer's refusal: a raster of a private-mode
    original would reach the AI API. Procedures: `topics/batches.md` and `topics/other-originals.md`
    beside the filing procedure.

15. **A page that seems to be someone else's; people who share a name** (operator, 2026-10-26, in
    wording only). A blind break test of the drag-first intake (ADR-0029, 2026-10-25) found the
    rules silent on doubted pages and on others' details in a transcription; the operator then set
    identical twins (same name, birth date and illness) as the hardest case. Two cold reviews (Opus,
    Codex) agreed that twins leave ownership by the operator's word intact but remove every cue on
    the page, so a doubted-page rule cannot fire for them, and "seems to contradict" invites the
    reverse reading. Decided:
    - **A match confirms nothing:** a name or birth date never confirms or clears whose a page is,
      nor earns the deferred `document-identity-checked`.
    - **A shared name is asked, by handle,** at session start, in a session of several people,
      before filing and for on-screen answers; whose a document is gets asked in chat, since an
      on-screen question naming both could be filed for neither. A shared first name is never a bare
      handle (ADR-0028, same date).
    - **A doubted document waits,** unfiled, untranscribed and unreconciled until the operator names
      one record; the rest go on. A copy made from a chat drag is removed, so tray placement stays
      their word; unresolved at the end, it is an open item naming no one.
    - **Others on a page are written by role,** name, birth date, ID number and contacts withheld.
      The keystone's "never mentions another person" sets clinicians and the operator aside (read
      literally, it forbade the care-team table) and leaves originals and captured answers verbatim;
      a profile or analysis never compares the person with anyone.
    - **Rejected:** a distinguishing number per twin in the profile (a partial identifier every
      session reads, identity read off a page, and masked in private mode anyway); a twin marker
      making the operator confirm every document's owner (more friction than the case warrants).

    Owning text: `CLAUDE.md` → *Sessions and people*; `_templates/INTAKE.md` §2; the filing
    procedure, *How a document arrives* and step 2.

16. **Family history: relatives by role** (operator, 2026-10-26, in wording only). Point 15 left
    family history no home, and the keystone barred a relative's condition, though a relative's
    inherited variant or early-onset disease can decide a test, a screening age or a medicine warning.
    Decided:
    - **A Family history section in the profile:** blood relatives' conditions that may run in
      families, by role, side and full or half, with ages and a variant's details when known; never
      a name, handle or other identifier; never blank. The keystone admits others by role in
      transcriptions, family history, exposures, care based on these and advice to pass on.
    - **Source:** this person's sources or a report (B), never the relative's folder or
      combined-session section; the operator, not the session, carries a fact across (the
      combined-session rule is unchanged).
    - **A relative's finding stays theirs:** it is this person's only on their own result, never by
      inference, the operator's included; the history, and a clinician's plan on it, are this
      person's facts. No new planning tier; advice for someone else is an open item to pass on.
    - **Confirmation:** a reported row that a test, screening or medicine item or question gives as
      its reason gains a dated ⟨confirm by⟩ tag for a copy of the relative's report. Tagging every
      reported row was rejected: most is reported, and the queue would fill with records nobody can
      obtain.
    - **Handout checker:** a relative's finding presented as this person's stays a wrong-person hard
      stop; history stated as the relative's, by role, is not one.
    - **Intake asks once** (operator, 2026-10-27, after a research pass on official guidance): one
      on-screen, by-role question per person, ages asked rather than filtered and the widest cut-off
      (heart disease before 65) kept so one answer serves differing thresholds. Opened: the 2021
      European prevention guideline; NICE CG71, CG109, CG164 and NG238; the US task force on BRCA
      risk (2019); the British hereditary colorectal guideline (2020); the national health checks of
      England and Poland. None sets a re-ask interval, so none was added. Ancestry questions were
      left out (sensitive; relevant only after a cancer is reported).
    - **Rejected:** recording only the consequence (loses the age thresholds screening hinges on); a
      shared hereditary file in `_shared/` (joint files hold no diagnosis; most relatives are not on
      the roster); leaving it to transcriptions (the profile stops being the current truth for
      risk-driven care).

    Owning text: `_templates/profile.md` → *Family history*; `_templates/INTAKE.md` §1 step 5;
    `_templates/HANDOUT-RULES.md`; `_templates/handout-verifier-prompt.md`.

17. **Family history from a relative on the roster** (operator, 2026-10-27, in wording only). Under
    point 16 an operator could retell from memory what a relative's record already holds, original
    included. Decided:
    - **The roster lists blood relatives also on it,** by handle and role, as the operator states
      them, never inferred. It already names people at pointer level, unscanned by the separation
      guard.
    - **A context-isolated helper drafts; the operator carries.** The requester's session never
      opens the relative's folder. A fresh Opus-class helper per relative, given their handle and
      nothing about the requester, reads only their profile and the intake question, writes nothing,
      and returns one table of the intake categories, only what the profile states as their own at A
      or B: no medicine, dose, value, name, handle, date, clinician, facility, place or other
      condition. The draft is shown on screen in a call about the requester, by role; only the
      operator's yes enters the record, filed and cited B.
    - **Private mode** changes nothing: the profile never holds the protected identifier and the
      helper opens no page, so a stop would protect nothing.
    - **"A serious reaction to an anaesthetic" joins the intake question** (operator, 2026-10-27):
      rare, serious and a standard pre-operative question.
    - **The profile's note is cut to cues** (operator, 2026-10-27; 239 to 182 words), each dropped
      rule held elsewhere.
    - **Admission** of the confirmation step: the harm is a helper over-share written into the
      requester's record; the step replaces a retelling with a confirmation at the write, is rare,
      and is the B provenance the row needs anyway. A private-mode stop failed the first question
      and was dropped; the helper's narrow return is a brief, not a control.
    - **Rejected:** the requester's session reading the relative's profile (every medicine, value
      and name in context for one line); a separate relationship file (the roster already is the
      meeting place); a code filter over the helper's answer (the requester's record holds the same
      kinds of words, so it cannot tell a leak from a fact; the operator's yes is the backstop);
      carrying the relative's own family-history rows (second-degree role arithmetic is a decision
      tree; the intake question asks directly).

    Owning text: `_templates/family-history-helper.md`; `_templates/INTAKE.md` §1 steps 2 and 5;
    `_templates/profile.md` → *Family history*.

18. **Without python3, one red, tested** (operator decision, 2026-11-01; simplification scan
    item 10). L13 no longer walks the tree in shell to decide whether there is ownership content:
    it reds once whenever `patients/` holds any person entry or `_shared/med` holds anything (a
    symlinked or wrong-type `_shared` root included), naming the fix, install Python 3.9 or newer.
    A person-free tree stays green. The shell walk had no bite (the test switch
    `TABULARIUM_TEST_NO_PYTHON` was set nowhere); `checks/selftest.sh` now runs this path. Lost: a
    no-Python host whose people are scaffolded but hold no documents reds instead of green; every
    record tool and the installer need Python already.

### Reviews and break tests behind the decisions

- **The design** (2026-07-11): a Tier-S red-team found three blockers and seven majors, folded in
  before acceptance. An Opus panel of four, unanimously conditional, affirmed the core; its N-3
  (ledger-graph integrity), N-7 and N-8 were kept for the build.
- **Point 15:** 25 adversarial synthetic situations, sorted blind from the rule text by a fresh Opus
  agent per round; two rounds matched the intended action in 25 of 25.
- **Point 16:** cold Opus and Codex reads, then blind rounds of 23 of 24, 26 of 28 and 16 of 16; the
  intake step's blind check matched or bettered the intended action in eight of eight.
- **Point 17** (synthetic fixtures; about $2.60 of Opus 5.5 sessions): a leak test of six planted
  relative profiles, 15 of 15 answers clean; four contained care sessions that kept the relative's
  folder out of their reads, wrote only after the yes and ended green; wording rounds of 22 of 22
  and 26 of 26.
- The last fixes of points 16 and 17 were not re-sorted.

### Other rulings and records

- One person's `<PPP>` tag, minted for the handout-ID build gate, was ratified by the operator on
  2026-07-11; PPP assignment stays an operator decision (ADR-0033 unchanged).
- Left for its own slice (2026-10-02): a pre-inventory transcription lint.
- The residuals the operator accepted along the way, and their revisit triggers, are kept with the
  accepted risks, outside the tracked tree.

## Alternatives considered

- **Extending L5 instead of a new guard** — rejected: a handle grep over authored text and a hash
  inventory over evidence are different error classes, treating `med/sources/**` oppositely.
- **A guard that reads identity off the scan** (vision, real-name match) — rejected: no LLM in
  `check.sh` (ADR-0020, ADR-0021) and no real-name registry (ADR-0028).
- **Whitelisting a duplicate hash** — rejected (handover constraint): a whitelist rots and
  normalizes a byte-identical copy under two roots.
- **One shared copy of joint evidence** — designed, red-teamed and withdrawn on 2026-07-11. A
  two-person document was to live once in `_shared/med/sources/`, referenced by both manifests, with
  the known duplicate carried by a migration-written `dedup-to-shared` queue record that
  discriminated on record provenance, never on the hash. Withdrawn because evidence is individual
  and the duplicate was boilerplate: there was nothing to de-duplicate (point 7). The panel's
  two-sided `_shared` attestation (R-1), its keystone amendment (R-2) and N-1, N-2, N-5 and N-6 went
  with it. Do not build it.
- The other rejected or superseded options are given with their reasons in points 1, 3, 6, 8 to 11,
  13 and 15 to 17.

## Consequences

- Mechanically detectable wrong-person filing is loud, ownership provenance is explicit instead of
  implied by folder position, and the public claims were corrected to match. Neither L5 nor L13
  substitutes for the operator's identity judgment.
- Every intake keeps the ledger in step: a source is filed once inventoried, never parked in
  `_inbox/`; legacy sources are a backlog for one-person sessions.
- `check.sh` needs `python3` wherever ownership content exists. The manifest is a second metadata
  concentration inside the PII boundary. The ledger guards against accident, not against hand edits
  to both ledger and checkpoint.
- Verified by `tools/person_ownership/test_ownership.py`, L13 wiring bites in `checks/selftest.sh`
  and CI; points 12 to 14 were mutation-tested.
