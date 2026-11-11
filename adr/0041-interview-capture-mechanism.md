# ADR-0041 — Interview capture: on-screen answers filed word for word

- **Status:** Accepted 2026-07-23; revised decision accepted 2026-10-19
- **Date:** 2026-07-23
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Answers the operator or the patient gives to structured questions are grade-B evidence, and some
must survive word for word: a dose, a date, a symptom in their own words. The load-bearing property
is that the **human authors the verbatim bytes**. A model retyping answers is the paraphrase and
inference contamination that ADR-0005 exists to prevent, so the model must stay out of the path the
bytes take. An interview is about one person (ADR-0002).

The design of 2026-07-23 met this with a **local sheet the operator filled in an editor**. The move
to a cloud execution surface (about 2026-07) had broken only its delivery (download into a deep
folder, fill, upload again); a session with the desktop device bridge could write the sheet straight
into the tree. The legacy sheet was bilingual and prose-heavy, and capture had to work without the
bridge too.

**The incident.** A care session needing more answers than its structured-question
tool holds never reached for the mechanism: it authored the transcript itself, skipped the WIP
stage and filed a third distinct shape straight into `sources/interviews/`. The root causes were all
in the tool: `CLAUDE.md` never named the mechanism or its trigger; the sheet standard existed only
as one placed instance, while the template still described the legacy method; and the forward items
sat on no roadmap row, with no eval case. (A second incident, scans attached to a chat, is recorded in
ADR-0029.)

**The evidence** (a care session, abstract). Of the answers collected through the client's
on-screen question tool, few free-text ones reached the record whole and verbatim; one quotation
was silently spell-corrected inside its quote marks; the rest were accurate paraphrases or excerpts. The client stores the exact answers in the session
transcript, but transcripts live outside the record and the client prunes them. The tool's
free-text "Other" field also made the 2026-07-23 premise, preset choices only, untrue in practice.

## Decision

The decision of 2026-07-23 had five parts: **(a)** a local sheet the operator fills in place, the
primary capture; **(b)** numbered chat rounds stored verbatim, the fallback without a bridge;
**(c)** the client's structured-question tool is not a capture surface; **(d)** a single-language
sheet standard; **(e)** three concerns kept separate — question bank, capture surface and stored
evidence — with the evidence never JSON. On 2026-10-19 the operator reversed (c), withdrew (a), (b)
and (d) with everything built on them (*Alternatives considered*), and kept (e)'s rule for the
stored evidence. What holds now: `CLAUDE.md` → *Keeping the record honest*, last bullet; the filing
procedure `_templates/person/med/sources/README.md` → *Filing on-screen answers*; the docstrings of
`tools/interview_capture/`; and `evals/cases/EV-14-interview-quotes.md`.

1. **On-screen questions are the capture surface, and a tool copies the answers** (operator,
   2026-10-19, on one condition: answers reach the record word for word mechanically, never retyped
   by a model). This reverses (c), on the evidence in *Context*: the tool holds open answers, and
   answers retyped from it lost their wording. Withdrawn the same day: the sheet and chat-round
   lanes and all built on them — the interview skill
   (`tools/claude-skills/interview/`), the blank sheet, its validator, eval case EV-08 and the
   deferred JSON question bank (*Alternatives considered*).

2. **The stored evidence stays readable Markdown** ((e) of 2026-07-23, standing). A filing writes
   one grade-B source file, `YYYY-MM-DD__interview__<slug>.md`, in the person's
   `med/sources/interviews/`; JSON is never the stored evidence. Once inventoried, the ownership
   ledger (L13, ADR-0037) binds its bytes as for any source. Reconciling it into `profile.md` and
   `medications.md` stays a separate step under the operator's authority (ADR-0005), unchanged
   since 2026-07-23.

3. **`tools/interview_capture` files the answers** (2026-10-19), replacing the sheet lane. `file
   <handle>` copies every answered call of this session's transcript not yet filed into one source
   file, each item in its own fenced block, bound by two hashes, and inventories it as the
   procedure's step 3 does.
   `verify` re-renders a filed copy from the transcript and compares every byte while the
   transcript exists, and checks the file against its own hash after. The rules that shape it, most
   from the reviews below:
   - **Nothing half-filed.** The file appears whole or not at all. It is removed again only when the
     ledger refuses it, the one failure known to write nothing, and kept after any other
     registration error; a filing an interruption left un-inventoried is completed on the next run,
     once its file passes its own checks.
   - **A call is filed once, for one person.** A call already filed for anyone, from any session, is
     never filed again (a resumed session repeats old calls under the same ids). In a record of more
     than one person the default refuses: the session names this person's calls (`--call`) or says
     every question was about them (`--all`), and a session whose calls are partly filed for another
     person refuses even then.
   - **Only live, readable answers are evidence.** A call on a branch the conversation was rewound
     or edited past is reported, not filed. A call that cannot be filed (two questions with the same
     text, an answer for a question the call does not hold) is named, to be asked again. An
     interview file that cannot be read back stops filing until the operator has looked.
   - **Identifiers:** the session id is stored as 32 hex digits: a hyphenated UUID's last group is
     all digits about once in 300 sessions, an 11-digit run the private-mode guard reds on, while a
     32-hex token with a letter it reads as a digest. A session never asks on screen for an
     identifier the profile protects.

   Mechanics: the module's and functions' docstrings; the procedure's steps 1, 2 and 4.

4. **One person per call** (2026-10-19). A call that asks about two people cannot be filed for
   either; the keystone says so, and the procedure says to ask the operator about such a call. Not
   enforced: the tool cannot tell whom a question is about, so this rule and `--all` rest on the
   session's word. **Before a person is named** (2026-10-25): questions may be asked while the
   question is tied to no one yet, so a session can gather what a general question hinges on. The
   answers stay in the session; once the operator says whose they are, they are filed for that
   person in the same session with `--confirmed`, and if no one is named before the session ends,
   nothing is filed.

5. **Capture timing: in the same care session, before it ends** (2026-10-19), inside the session's
   safeguards, so pruning cannot lose the answers. An emergency in an answer still comes first (the
   emergency stress test has mid-interview rows), so the rule no longer says "right after they are
   given". **Decided by the operator, 2026-10-19:** no hook reminds a session that ends with unfiled
   on-screen answers, to be revisited if a session is seen ending with answers unfiled; and the
   client's transcript retention (`cleanupPeriodDays`) stays at its default, since transcripts hold
   health data outside the records folder and same-session filing is the protection.

6. **Quotations are checked against the file: `quotes <handle>`** (2026-10-19; the reading widened
   2026-10-21). A quotation in `profile.md` or `medications.md` that cites an interview file by its
   dated name must be word for word in one of that file's answers or notes (spacing, Unicode form
   and ellipses aside). **Decided by the operator, 2026-10-19:** a workflow step that reports, run
   after the write and before the session ends, not a board guard. Since 2026-10-21 wrapped prose
   is read as one line, and a quotation belongs to a citation by its layout. A quotation right after
   the words "open item" is a label, and one followed by a citation that ends in a mark other than
   B and names no interview file is that source's (on-screen answers are grade B); neither is read.
   A quotation no citation claims is listed by line ("NOT READ"), never passed in silence.
   `quotations(root, handle)` yields each verdict, so the eval grader reuses the tool's reading
   instead of restating it. The reading rules live once, in the tool (`_norm`, `_at_bounds`,
   `_paragraphs`, `_owner`, `quotations`).

   **Decided by the operator, 2026-10-21:** a failure names a second way out, "copy it from the
   file, or, if it quotes no answer, take the quote marks off". In EV-14's first live run (targeted,
   ×3 per variant, Opus 5.5) two of six sessions put quote marks around the record's own words on a
   citing line; a quotation turned into a paraphrase hides nothing, so no exemption was added. Also
   decided that day: the filing procedure's step 3 was to say what the check accepts — an answer, a
   chosen option or a note, never a question; the citation in the same paragraph or list item, a
   line break between being fine; `…` and `...` both ellipses; an editor's `[sic]` after the closing
   mark. A line saying an open-item label is not a quotation was offered and left out: the tool
   skips labels itself. On 2026-10-27 (`3396fee`) step 3 was shortened: the ellipsis, `[sic]` and
   spacing details were left to the checker, while word-for-word copying, the dated citation,
   running `quotes` and re-copying on failure remained.

   **Reading limits:**
   - a quotation with no dated name of the file in its paragraph (a citing paragraph that only
     paraphrases is allowed by design, and counted);
   - an option label that also answers another question passes the substring rule, and an excerpt
     can drop a whole word before its first fragment, a negation included;
   - straight double quotes used as inch marks pair across one paragraph's lines, failing a correct
     quotation or hiding an altered one;
   - a chat answer quoted with its own `(operator <date>, B)` tag in a paragraph that cites an
     interview file is read against that file and fails: a grade-B tag cannot tell a chat answer
     from an on-screen one, and treating it as another source hid misquoted on-screen answers
     (accepted by the operator, 2026-10-21, to be revisited when a live session first hits it); a
     quotation of a document written with no citation of its own is read the same way;
   - a misquote right after "open item" passes, where the 2026-10-19 check failed it, and a label in
     other words (another language included) is read as a quotation; reading a label of the
     open-items table as a label wherever it stands is deferred until a live session needs it;
   - each line of a blockquote is read alone, a wrapped line that starts like a list item ("- as they
     put it", "2. of") starts a new block, and an unindented line right after a list item continues
     it (Markdown's lazy continuation).

7. **The interview file prints its own citation** (operator, 2026-10-21, on an adversarial panel's
   ruling; built 2026-10-22 as format 2). In EV-14's first live run three of six sessions quoted the
   answers word for word but cited them by date ("on-screen answers <date>, B"), not by the file's
   dated name, so `quotes` never saw them; those sessions never opened the filing procedure, and the
   three that did complied. The operator required the next release shipping the capture tool to
   include this header change, followed by EV-14 at three trials per variant. The header's closing
   sentence now prints the exact citation, `(operator, <dated name>, B)`, and `file`'s next-step
   line prints the same. `render` takes the dated name as a required argument, so an old caller
   fails loudly, never with a wrong citation. `verify` re-renders a file in the format its own
   `format:` line names, so a format-1 file still verifies byte for byte and its name, which it
   never cited, is still not read. Format 2 runs forward only: the former tool fails a format-2
   file, so the tool is not rolled back once one is filed. A format-2 file renamed after filing
   fails `verify` only while the transcript exists, with the generic "differs" message; after that
   the ledger, and `quotes`, which no longer finds the cited file, report it. **Decided by the
   operator, 2026-10-22:** no care-contract line. The contract's interview line was to gain "citing
   it by its file name" only if a session still cited by date. In EV-14's second run every session
   cited its quotation of the answers by the file's dated name, but two quoted a three-word fragment
   again with a date alone, in an inference line and an open-items row. Those date-only fragment
   quotations are accepted; revisit if a misquoted fragment or a main quotation cited by date is
   seen.

8. **Chat answers are quoted from the operator's own messages** (2026-10-25). A care session drafted
   a summary of facts for the operator to send back as their own message so it could quote it; the
   draft misattributed who advised what and asked again for what the operator had already said. A
   quotation of a chat answer now comes from the operator's earlier messages as they stand; a
   session never writes a statement for the operator to send back as theirs, and asks only for what
   they have not said (`CLAUDE.md`, the same bullet).

9. **What the retired lane left** (2026-10-19). Sheets already filed stay as they are: immutable
   evidence that `quotes` skips and whose fences the tool does not parse, so a sheet-era file never
   blocks filing. The intake tray's note keeps a line for a sheet left from the retired method. In a
   care checkout the next `install-instance.sh care <tag>` removes the installed interview skill by
   the leftovers path (bytes equal to a release's copy); a development tree keeps its installed
   copy until removed by hand. A transcript filed in CARE in a shape of its own before then is a
   tool finding, not a record defect, and nothing rewrites it (2026-09-17).

### Admission tests (guard-admission)

- **`quotes`, 2026-10-19:** (1) record damage on the profile write, observed in a care session (a quotation
  corrected inside its quote marks); (2) it only reads the person's own files and reports; (3) it
  runs after the write, before the session ends — a workflow step, not the board, on the sheet
  validator's 2026-09-29 precedent; (4) net positive only as a step that reports, since a board
  guard parsing profile prose would turn its residuals into blocked session ends; (5) one home, a
  subcommand of the capture tool.
- **The wider reading, 2026-10-21** (tightening an existing control): (1) the same damage, plus the
  wrapped form escaping the check in calibration, and false failures on the record's own label form
  and on another document's quotation, which push a session to reword correct text; (2) and (3)
  unchanged; (4) net positive: wrapped quotations, half of the compliant answers, are checked at no
  new friction for correct text, and two kinds of false failure go; (5) no new control — the same
  subcommand, its one message reworded, and the reading rules once, in the tool.
- **Format 2, 2026-10-22** (the wording of an existing control, not its strength): (1) a quotation
  cited by date is never read, so one altered inside its quote marks passes (three of six sessions
  in EV-14's first live run); (2) it blocks nothing: one sentence in a file and one printed line;
  (3) it acts where the quotation is written, since the session reads the header as it copies the
  answer; (4) no new refusal, notice or step; (5) no new control: `quotes` and `verify` accept and
  refuse what they did, save the renamed file in point 7.

### Reviews and break tests behind the decisions

- **The capture tool** (2026-10-19). Red-team round 1 (S-exec, one fresh-context adversary, 102
  attacks; honest-slip threat model): fidelity held for every byte attack (normalisation forms,
  invisible characters, odd line ends, fence-like lines, empty and non-string answers; a lone
  surrogate is refused before writing). Its must-fix: another person's calls reached a file by the
  default after a per-person `--call`. Round 2 (122 attacks against the fixes) found one more: a
  default run made first in a combined session still filed another person's call, now the
  several-people refusal of point 3. Codex's pull-request review (three findings, all reproduced and
  valid) gave the rule that keeps the file after a registration error other than the ledger's
  refusal, the completion of an interrupted filing when its original `--call` is retried, and a
  capture header cut before its closing line read as damaged. An independent cold-eyed Opus review
  gave the branch check: of 404 real question calls in build transcripts, 28 sat on a branch the
  conversation was rewound or edited past. Kept against its over-build notes: the time window,
  `--confirmed` and `verify`'s re-render, the one check that sees a retyped answer before the
  ledger binds the bytes. Each fix has a test. The operator asked for the Codex review to be
  assessed and fixed, then for the independent review, before the core behavioural run.
- **Mutation proof** (the tool's suite, selftest and CI): any answer altered, retyped or re-spaced
  in a filed copy fails `verify` with and without the transcript; a quotation spell-corrected,
  renormalised, re-capitalised, translated, reordered, cut mid-number or re-punctuated fails
  `quotes`; each of 47 mutations of the tool turns the suite red.
- **The wider reading** (2026-10-21). EV-14's calibration on 2026-10-19 (pull request #173: six
  compliant hand-written answers by an independent Opus agent) found that three of the six wrapped a
  quotation across a line break, where `quotes` never read it, and one bait tree hid a
  spell-corrected quotation exactly there; the record's `open item “<label>”` naming failed on a
  citing line. Two red-team rounds followed (one fresh-context Opus adversary each; 72 and 75
  hand-made attacks, about 9,000 and 26,600 generated texts; no must-fix). Round 2's should-fix: the
  other-source rule, which then took any date or evidence mark, hid misquoted on-screen answers
  tagged in the record's own form, `(operator YYYY-MM-DD, B)`; it now takes marks A, C and D only.
  Measured on round 2's generator (21 paragraph shapes, 2,452 citing paragraphs, each on one line
  and hard-wrapped at 28 to 100 columns), final code against the former: misquotes caught 1,838 of
  1,838 both ways (former: 1,838 on one line, 225 wrapped, 19 silent); correct quotations failed
  605 on one line and 407 wrapped (former: 1,772 and 250), every failing paragraph holding the
  chat-tag or uncited-document limit of point 6; a first count of 18 shapes was caught by the
  panel's defender. Each of 30 mutations of the new reading turns the suite red; EV-14's 825
  controls stay green.
- **The adversarial panel** (operator's request, 2026-10-21; four Opus panelists and an Opus judge,
  no paid runs) on the change's low-confidence choices and on where the dated-name rule lives. Kept,
  each after attempts to break it: grade-B tags read against the file; the next citation across a
  line break; unread quotations listed with exit 0; the open-item skip; Markdown's lazy
  continuation. Rejected: a "near miss" similarity test that would have read a grade-B-tagged
  quotation only when it resembled an answer. The judge's hand-made misquotes (translations, a
  rewording, a reordering) passed it silently, 5 of 7, where the former check failed all 7, and its
  threshold rested only on generated text.
- **Format 2** (2026-10-22). Red-team (S-exec, one fresh-context Opus adversary; no must-fix): 582
  files written by the former tool across eight timezones, `__N` names, CRLF and unusual answers,
  all byte-identical under the new `verify`; 696 format-2 files, each citing its own name; 29 ways a
  session might copy the citation, each read or listed as before. Its should-fix: the format-1 test
  now pins the text to the SHA-256 of the bytes the former tool wrote, so a change to text both
  formats share goes red instead of failing every format-1 file in a record. Five new tests; each of
  16 mutations turns the suite red; EV-14's 828 controls behave as before. The twelve format-1 files
  from EV-14's first run verify byte for byte; the care checkout held none.

## Alternatives considered

- **The sheet lane, 2026-07-23 to 2026-10-19** (withdrawn by the operator, 2026-10-19; point 1).
  (a): a blank sheet was written over the device bridge into the person's `med/_inbox/` as
  `YYYY-MM-DD__interview__<slug>__WIP.md`, filled in place by the operator and graduated (renamed
  and moved) into `sources/interviews/`, which widened the intake tray from scans to operator input.
  (b): numbered chat rounds, stored byte for byte, kept the model in the loop only when no bridge
  was connected. (d): a single-language sheet with bulleted instructions, `‼️` safety-critical
  markers and a verbatim slot per question. (e)'s question bank, one JSON source rendering every
  surface, was to keep the paths from diverging. Built on it:
  - **The interview skill** (decision recorded 2026-09-17 after the incident in *Context*; built
    2026-09-19, its shape settled in the operator's review of pull request #15): the forward
    "portable skill" item, built rather than deferred, to capture the answers verbatim as evidence
    against model-attributed distortion (summarising, rephrasing), in the operator's words. It was
    self-contained, agent- and version-agnostic in wording, model-invocable and installed in every
    instance, and it absorbed `_templates/interview-template.md`. The keystone carried a pointer,
    not the method; (c) stood; if the operator declined the sheet, chat rounds were the sanctioned
    path. Its must-nots: never author the transcript, fill a slot, skip the WIP stage, file straight
    into `sources/interviews/` or rewrite a graduated transcript. From 2026-10-04 (drift recorded
    2026-10-11) a short answer that must survive word for word was quoted in the record with who
    said it and when, and the skill was for a real interview only.
  - **The sheet standard** (`_templates/interview-sheet.md`, 2026-09-17) revised (d) in three places
    on the operator's review: frontmatter labels in the sheet's language (seven fields in a fixed
    order), not English; the date with `HH:mm`, since several interviews can happen in a day; a
    blank slot reads as no answer, never filled by the session. No `<!-- t:… -->` anchors (ADR-0044
    considered): a sheet graduates into immutable evidence, so they would be stripped.
  - **The sheet validator** (`tools/interview_check`, built 2026-09-29): a capture-time
    workflow step, not a `check.sh` assertion, because L13 binds the bytes once inventoried and a
    tree-wide guard would block unrelated care commits. It reported a blank `‼️` answer rather
    than failing closed on it. **EV-08** (wired 2026-09-29) ran in the full suite only.
  - **The JSON question bank** stayed deferred (ROADMAP F3, 2026-09-20) until a second sheet-shape
    drift.

  Why withdrawn: the evidence in *Context* (point 1). Answers asked on screen and retyped
  lost their wording, while the client already holds the exact answers for a tool to copy.
- **The structured-question tool as the capture surface.** Rejected on 2026-07-23 as multiple-choice
  only (2 to 4 preset options, at most 4 questions a call), which would force answers into options;
  kept then for scoping and route questions. Adopted on 2026-10-19 (point 1).
- **Delivering a cloud file to download, fill and upload again** (rejected 2026-07-23): the
  regression the operator flagged — deep-folder friction, and it invites transcription slips.
- **Chat capture as the primary path** (rejected 2026-07-23): it puts the model in the verbatim
  path, the ADR-0005 contamination class.
- **JSON as the operator's edit surface, or as the stored evidence** (rejected 2026-07-23).
  Hand-editing verbatim clinical text as JSON is punctuation-fragile: one stray quote or newline
  breaks the parse. A JSON evidence file would duplicate the Markdown transcript: two sources of
  truth in the immutable lane, against one fact, one home and the ledger's hash model.
- **A dedicated `interviews-wip/` folder** (rejected 2026-07-23): the person-scoped `med/_inbox/`
  already existed, and a fourth staging vocabulary adds surface for no safety gain (the same call
  ADR-0030 made on the `_inbox` name).

## Consequences

- The human-authored bytes reach the record with no sheet to deliver or fill: the operator answers
  on screen, and a tool, not a model, writes the source. Answers the client keeps only in a pruned
  transcript are safe once filed in the same session.
- Verified by the tool's synthetic suite (`tools/interview_capture/test_interview_capture.py`, in
  the selftest and CI; the mutation proofs above) and, for quotations, by behavioural case EV-14.
- `quotes` reports and blocks nothing. Its limits and the rules that rest on the session's word
  are recorded in points 4 and 6.
- Format 2 commits the tool forward (point 7), and sheet-era files stay in records (point 9).
