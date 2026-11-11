# Intake — adding people and filing their first documents

Read this before onboarding people or filing their first documents, above all a mixed batch. The
per-document checklist is the shared `_templates/person/med/sources/README.md`. Holding several
people is a **combined session** (`CLAUDE.md` → *Sessions and people*): say so at the start; return to
one-person sessions after.

## 0. First person on a new Mac
The first run on a new Mac follows `SETUP.md` at the repository root, which comes here at section 1.

## 1. Scaffold every person before filing anything
1. For each person, create `patients/<handle>/` (lowercase; for people who share a first name,
   neither handle is that name alone — the separation check would flag the other's own name) with
   `profile.md` and `medications.md` from `_templates/profile.md` and `_templates/medications.md`, and
   `med/handouts/INDEX.md` from `_templates/person/med/handouts/INDEX.md`; fill `{{NAME}}` /
   `{{DATE}}`. Create `med/sources/` (the ledger's `init` needs it) and `med/_inbox/` (the intake tray)
   empty beside it; other folders are created at first use. The policy docs under `_templates/person/`
   (the filing checklist and its topic pages, the capture guide, the intake-tray note) are read from
   there and never copied into a person's folder. If the operator has asked for private mode for this
   person, offer an alias before creating their folder: a name used as the handle cannot later be kept
   from the AI. With an alias, `{{NAME}}` takes the handle and the name goes only into the form
   (step 3).
2. Add them to the roster in `patients/README.md` (local-only), never to `CLAUDE.md` (ADR-0007),
   each with any blood relative also on it: handle and role ("parent", "half-sibling, same parent"),
   as the operator states it, never inferred.
3. Private mode (ADR-0029) is an early experiment and is never offered: set it only when the
   operator asks for it for this person, in their own words. With no request, the profile's
   private-mode line reads `— none`: skip the rest of this step. On a request, read
   `tools/private-mode/README.md` before any page of theirs is opened and say once that it is
   experimental and what it does not protect (*What it does not protect*). Then record their decision
   in `profile.md` → Identity, with the country of the number printed on their papers as its number
   tag (*Which number*),
   and get this Mac its tools: ask in plain words what language the person's documents are in, get one
   yes (a language pack is a download of about 650 MB), then run
   `bash checks/setup-mac.sh private-mode <tesseract code>`, which installs only what is missing; its
   lines are handled as in `SETUP.md`, step 2. Then
   ask which other details to keep from the AI (names, date of birth, contact details and more; handle
   and name as in step 1), by `tools/private-mode/topics/kept-details.md` → *Choosing what to keep*;
   nothing ticked keeps only the number.
   If private mode was asked for anyone in this intake, finish steps 3 and 4 for each of those people
   before asking about anyone's documents. For a private-mode person, never offer a drag into the
   chat: link their `med/_inbox/` and say to put the pages there when ready.
4. If private mode is set (step 3), read the page of each listed key the person's exact tag names, or
   of every listed key when their line has no exact tag (`tools/private-mode/README.md` → *Which
   number*), and do the setup it names, if any.
5. Ask each person's family history once, on screen, one call per person, filed for them once their
   ledger exists (the checklist, *Filing on-screen answers*): "Has any of <person>'s blood relatives —
   mother and father, brothers and sisters, children and, on each side of the family, grandmothers and
   grandfathers, aunts and uncles —
   had a heart attack, chest pain from the heart (angina pectoris) or a stroke before 65; a sudden
   unexplained death before 40 or an inherited heart condition; very high cholesterol; diabetes; any
   cancer (which kind); a serious reaction to an anaesthetic; or a genetic test result that runs in the
   family? For each: who, by role, not by name,
   what, and at what age, roughly if need be. 'Don't know', 'adopted' or 'no contact' are fine." Each
   blood relative the roster lists for them: show the helper's draft in this call
   (`_templates/family-history-helper.md`).
   Declined: "not yet asked"; not known:
   "unknown", with why.
6. Setting up someone other than the operator: say once, plainly, "Where you can, tell them and
   include them. Their health data goes to the AI service too." No gate; nothing is recorded, because
   the person may be unable to answer.

**Before any filing**, initialise each new person's ownership ledger (ADR-0037/L13):
`python3 -m tools.person_ownership --root . init <handle>` mints their record ID and an empty
`med/MANIFEST`, touching no one else's folder. A person scaffolded later gets the same step.

## 2. Name each document's owner before filing it
- The owner is the **operator's statement**: placement in that person's `med/_inbox/`, or naming
  whose it is for a file dragged into this combined session's chat (filed per *How a document
  arrives* in the checklist, `_templates/person/med/sources/README.md`). Never infer it from a
  surname, birth date, address or anything else on the page — a match confirms nothing; ask, by
  handle where a name fits two. A page that seems to contradict the named owner is a question,
  never a refile: it waits as the checklist says (*How a document arrives*).
- A document about two people is filed under **one** owner, whom the operator names. The other is
  referenced only at pointer level, in `_shared/`; facts about them enter their record only from
  their own source or the operator.
- A private-mode person's documents come only through their `med/_inbox/`, filed under the
  `/private` posture; one sent in the chat follows the private-mode README → *Opening a
  private-mode session*. If anyone in the household is in private mode, the operator sorts the
  batch into each person's `med/_inbox/` before a session opens any page.

## 3. File one person at a time
- One person's documents per filing pass: run the per-document checklist on each (it registers
  sources with `append <handle> add`) and finish that person before the next. A pass edits only
  that person's folder — ideally in a fresh-context subagent that reads only that person's files.
- Pass `--confirmed` only for a document whose owner the operator confirmed explicitly in this
  session; inbox placement alone records it unverified.

## 4. Close
- List what was filed, by owner; `checks/check.sh` green.
- Only when the roster held no one before this intake, and no backup is set up: "Would you like a
  backup off this Mac, on an external drive or in a cloud folder of your choice? No is fine; the
  recovery copies on this Mac keep running." Asked this once, never again. On a yes, they pick the
  folder: write its absolute path to `checks/OFFSITE-DEST`, run
  `touch '<that folder>/.tabularium-offsite-ok'` in the app's Terminal panel, then
  `bash checks/backup-offsite.sh`, and say what it reported. A folder on this Mac's own disk is refused:
  say so plainly and ask for a drive or a cloud folder. Once it reports OK, ask once how often it should
  refresh: each time they work here, once a week, or only when they ask. Write `every session` or
  `every week` as the second line of `checks/OFFSITE-DEST` (nothing, for when they ask); the snapshot at
  the start of each editing session then refreshes it when due.
- End on an open question, such as "What would you like to cover this session?"
