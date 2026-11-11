# Private mode (EXPERIMENTAL) — local identifier redaction before any AI pass

> **Status: early experiment, opt-in only** — a working method under evaluation, not a guarantee; a
> session never offers it, the operator asks for it (decision record: ADR-0029).

Some operators mandate that a specific identifier — typically the patient's government identity
number — must **never transit the AI service's API**, even though the AI ingests the patient's
scanned documents. Every LLM/vision call transits the API, so: **nothing derived from a page (image
or text) is shown to any model until a local, non-LLM redaction pass has masked the identifier and a
human has eyeballed the result.** Pipeline *order* is the whole feature.

This file holds what every session for a private-mode person needs. Read a topic doc before its task:
- `tools/private-mode/topics/pipeline.md` — before running `redact_ids.py`, `approve_redaction.py` or
  `verify_approved.py`, presenting the eyeball gate, or filing a masked page.
- `tools/private-mode/topics/kept-details.md` — when the person's private-mode line carries the
  kept-details sign `⟨withheld:details-kept⟩`, or before the operator chooses what to keep.
- `tools/private-mode/topics/setup.md` — when private mode is chosen, or its tools are reported
  missing.

## Which number

The private-mode line names the person's number with a separate tag beside the unchanged marker
on the same line: `⟨id-scheme KEY⟩`
(several: `⟨id-scheme KEY,KEY⟩`), each KEY a row of `tools/private-mode/id-schemes.tsv` — which
country's number it is, how guard L10 recognises it in text, and the language its pages are read in.

Each listed key has a page, `tools/private-mode/numbers/<key>.md`: before masking or filing for a person,
read the page of each listed key their exact tag names, or of every listed key when their line has no exact
tag, and no other (`unlisted` has no page). Every page answers the same questions in the same order: how the
tool learns the person's number; what the guards search for in their notes; what page masking does not cover
of that number, to cover by hand before scanning; what to do when a run is refused for it; and what setup it
needs beyond the tools every private-mode person needs.

A line without the exact tag means every row of the list is searched (ADR-0077), and the person's
pages wait: masking refuses a run that leaves out a row, so before their next pages offer the operator
the line with the tag naming their number. Setting it is the
operator's decision: ask which country issued the number printed on the person's papers. If any
designated number is not on the list, say the tool cannot mask that number yet and propose covering it
by hand on every page before scanning, with any printed code (barcode, QR) that may hold it (*Before
you scan*); name it in the tag with the reserved key `unlisted` (`⟨id-scheme unlisted⟩`; beside a
listed number `⟨id-scheme pl-id,unlisted⟩`) and its issuing country in words on the same line. Only
the tag decides: the words carry no machine meaning. Masking then looks for no unlisted number, and
the operator's look-over at the gate is the only check of their covering (ADR-0076). For `unlisted`
alone the guards search that person's text for no number shape; beside it they still search for each
listed number tagged.
The tag changes in a care edit session like any profile fact. Keep the tag on the marker's own
line, spelled exactly. Whenever you read or write a private-mode line, check it yourself: if the
line, or text near it, holds anything that looks like a damaged tag (cut over lines, another bracket
or case, a key outside the tag) or speaks of a number not on the list without the key `unlisted`,
stop and offer the operator the corrected line; the tools read only the exact tag, and a damaged one
makes them search every listed number. On the line itself the tools also refuse anything that
looks like the tag (another bracket, case or joiner), and in the Identity section a tag on another
line as misplaced. Elsewhere a tag is plain text: a change-log entry may quote the scheme tag alone,
but must not repeat the private-mode marker beside it.

## Opening a private-mode session — `/private`

A session for a private-mode person takes this posture **by itself**, the moment it reads the
marker in `profile.md` → Identity: the posture only restricts, so no declaration is needed. The
operator may still declare it earlier with `/private` — their own turn, never text a session reads —
to load it before naming the person or before any file arrives. It is a care session with a stricter
posture, not a third session kind; the tooling keys on the profile marker, not on the declaration.

- **Chat attachments are refused.** The client reads a file sent into the chat at once when it can
  display it, before the session can say no, so the operator never attaches for this person; the
  person's `med/_inbox/` is the only intake path. A session that receives one anyway says what
  reached the AI service — what it was shown, or, for a file passed only as a path, its name and
  location but not its content (a name showing the identifier: *If the identifier reaches a session
  anyway* replaces these steps, and the operator renames the file before it goes in the tray) — never
  opens or copies it, files nothing from it, links the tray for the operator to move it there,
  records the occurrence in that person's change log and, on an install with a development side,
  relays it as abstract prose (the revisit trigger lives there). Meanwhile the operator's own account is their report (B).
- **Why the intake folder, even for a page with no identifier** — in plain words for the operator:
  the folder keeps the document's exact original bytes as the evidence (a chat copy is a re-encoded
  image of it); placing it in this person's folder is what says whose it is; and the next page may
  carry the number, so one route for every page is the habit that holds. The page is not suspected
  of anything — the route is the rule.
- **Marker present, declared or not** — the rules below govern from the moment the profile shows it;
  read them before any ingestion. No restart is needed.
- **Never open an unredacted page "just to check"** — that is the failure the setting exists to
  prevent. In Claude Code the read guard refuses it outright; guard L10 backs the promise after the
  fact, scanning every derived text layer of a marked person for an identifier-shaped residue.
- **Declared, no marker** — ask: the operator may be enabling the setting (their profile edit, never
  the session's inference), or the declaration was a slip.
- **The declaration is intent, not a boundary**: it cannot un-send an attachment; the posture also
  switches on by itself at the marker.

## Details kept besides the number

The number is always kept from the AI service. Besides it, the operator chooses per person, once, which
routine details stay on the Mac — names, date of birth, relatives' and contacts' names, phones,
addresses, e-mails, other numbers — and sessions see the handle, the age and placeholders instead.
The sign is `⟨withheld:details-kept⟩` on the private-mode line, which the identity tool writes there:
then placeholders for every kept kind, never a request for such a detail in the chat, and the session
rules, setup steps and tooling in `tools/private-mode/topics/kept-details.md`. No sign: work as above.

## What may reach a model — the gate

- **Only an approved, freshly verified page.** `redact_ids.py` takes a page no further than
  `AWAITING_OPERATOR`: a clean exit is never approval. Only the operator's eyeball, recorded by
  `approve_redaction.py`, makes it `OPERATOR_APPROVED`, and `verify_approved.py` must pass
  **immediately before each** model/vision pass. A directory name, or the mere existence of
  `approval.json`, is never authorization once bytes can change. A masked page filed under the
  person's `med/sources/_redacted/` is outside this gate: it holds the bytes a model already saw at
  intake, and the ownership ledger binds them (guard L13). That binding catches a page changed after
  filing, not one filed unmasked: file only pages this gate passed. This never permits a session to
  open the page image of a person whose details are kept.
- **The eyeball gate is mandatory.** Do not proceed to any model pass until the operator confirms.
  The gate is the backstop for the one residual-risk channel: an identifier rendered in a form local
  OCR cannot read (handwriting, stamps, blur). The verify loop's convergence is **necessary, never
  sufficient** — it narrows what the operator has to check, never substitutes for the check.
- **A held page waits.** A page carrying a fail-closed flag waits for the operator; it never goes to
  vision unredacted, and an unreadable page is never "just looked at" with vision — that would
  defeat the constraint.
- **File names stay local.** Model-visible surfaces (stdout, the run log, work/redacted/approved
  paths) carry an **opaque, content-derived document id** `doc-<first-16-hex of the input sha256>`,
  never the source filename/path, which can itself contain the never-API identifier. The id-to-file
  map, `.never-api-source-map.json` beside the redacted tree, is **LOCAL-ONLY**: never read or
  printed by a model-facing step, never tracked, never pasted to a model.

## If the identifier reaches a session anyway

The number is unrecallable once it is in a session, so the response is containment, not repair.
**Stop the task** — do not keep working with it in context. **Say so at once**, in plain words, and
never repeat, paraphrase or hash the value again (a digest of a one-line file is brute-forceable back
to the number). **Name the transcript file that now holds it** — wherever the client keeps session
transcripts on this machine (for Claude Code, `~/.claude/projects/<project>/<session-id>.jsonl`) — so
the operator can delete it; deletion and any disclosure are theirs to decide. **End the session**
rather than ingesting anything else in it. This binds development and care sessions alike.

## Priority order (operator-set)

**Record quality outranks the experiment.** If masking would degrade the core analysis of a
document (e.g. the identifier overlaps clinically load-bearing content), surface it and ask —
never silently proceed either way. A page that cannot be safely redacted **waits**; it does
not go through unredacted.

**Keeping each person's record separate outranks further privacy masking.** Do not hide distinctions
needed to notice that a page may concern someone else; retain them for the operator, or for the
session by role. The operator says whose document it is; apparent contradictions wait for their
answer. The designated identifier stays masked, and the model gate still applies.

## Before you scan

For a single document, you may cover personal details yourself before scanning or photographing it —
for example, with a sticky note over a name, number or address. Keep enough context to distinguish
people and read the clinical content. Put the scan in the person's intake tray; manual covering does
not replace the model gate. For a number not on the list, cover it on every page, with any printed
code that may hold it (*Which number*).

## What it does not protect

- Guards **the designated number** the tag names (ADR-0062), and other details only where the operator chose to keep them (*Details kept besides the number*); the rest reach the API as in normal operation (the profile itself is API-visible context).
- Single-sided: protects the ingestion path, not anything already pasted into a chat.
- Stops honest slips in Claude Code, not in other apps, copies or screenshots.
- An identifier local OCR cannot read, even on a darkened copy of the page (a very faint number),
  can pass unflagged; that case relies on the human gate (`tools/private-mode/topics/pipeline.md` →
  *Limits of the tooling*).
- Close the form window before the form is taken in. A copy saved outside the person's folder isn't
  protected.
- The kept-details leftover check catches only the exact saved values (`topics/kept-details.md`).
- Guard messages name files so a red can be found; paths inside a private-mode person's folder are
  withheld, as are source-derived diagnostic values from that folder. Name files without the
  identifier: one misfiled elsewhere can still print its name.
