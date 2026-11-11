# ADR-0068 — Private mode on a care-only install: no token files, no typed number, a form for v2

- **Status:** Accepted 2026-11-07; supersedes in part ADR-0050 point 9 (a care-only install holds neither file) and ADR-0029 point 13.2 (how the identity file is filled); superseded in part by ADR-0074 2026-11-09 (point 2: no slot for the number) and by ADR-0075 2026-11-09 (point 3: the separate cutover step)
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

The first public users hold one care install and no development tree. Private mode's setup assumed
both: intake sent them to a file named by a pointer they do not have, and asked for an installer line
that cannot print without a token registry. Setting a person to v2 moved tokens in two checkouts, and
masking took the date of birth on the command line, so for a v2 person a model would have written a
withheld value.

A walk of a synthetic stranger's install (scratch clone, its own home folder) showed what needs those
files. The board, snapshots, masking and v2's residue guard ran without them. Only the relay scan, the
export gate and the eval's pre-transit scan read them.

## Decision

1. **A care-only install has no token registry and no identifier file.** Nothing it runs needs them;
   the relay scan and export stay refused rather than scanning nothing. Intake and the v2 steps test
   for the pointer and skip their step without it (operator, 2026-11-07).
2. **On a care-only install, nobody types any part of the designated number.** Masking derives what it
   looks for from the date of birth at each run, so no shape or slot for it exists in any file. An install
   with a token registry still adds the prefix to its identifier file, for its relay scan. A scheme whose
   number holds no date brings its own slot with its row (ADR-0062 point 5) (operator, 2026-11-07).
3. **A v2 person's details arrive through a form.** A local tool writes it, slots only, owner-only, and
   opens it in TextEdit; the operator replaces the slots; a local tool validates it, writes the identity
   file, deletes the form and prints only counts. It takes no value on its command line. The form holds
   no quotes, so an editor's curly ones and an apostrophe change nothing, and it is named so the read
   guard's by-name rule covers it (operator, 2026-11-07). The date of birth goes on two of its lines
   and counts only when they agree, as the terminal prompt asks twice, since masking keys on it; a form
   nobody wants is deleted unread (`discard-form`), and each refusal names the way out (cold review,
   2026-11-07). The terminal prompt stays for an operator who prefers it.
4. **Masking reads a v2 person's date of birth itself** (`--dob-from-identity`), so no session writes it.
5. **A second read on a darkened copy of each page, under the `lowconf` rule.** OCR reads no word at all
   in faint ink, so the confidence floor never saw it; what only this read finds is masked and held as
   `LOW_CONFIDENCE_CANDIDATE`, and a printed label only this read sees, with no number near it, holds the
   page as the plain read's would, wherever the plain read saw other labels (operator, 2026-11-07). The
   page's own paper sets the black point: the grey cell 90% of the way up the page's 64 × 64 goes
   white, and 80% of it black. A page whose middle cell is darker than a quarter, or a copy more than a
   quarter dark, holds as `DARKENED_READ_UNREADABLE`, never read as nothing faint. A hit
   of this read that reaches beyond the plain read's boxes is kept whole, not dropped for touching one.
   The copy is deleted once read (cold review, 2026-11-07). This is the detector half of launch
   condition #2.

6. **The masking tool's own folder names are not an identifier.** The ownership check's path scan skips
   `doc-` and 16 hex only as the name of a folder the tool made, live or superseded, which holds its
   manifest or approval: about one such hash in sixty holds an 11-digit run, a red no edit could clear
   (operator, 2026-11-07). Any other number-shaped name still reds, that shape elsewhere included.

7. **The read guard refuses any existing file whose name holds `never-api-identity`.** An editor's
   backup or a copy of the filled form or of the identity file holds the same values, and the rule that
   matched only the exact ending let a session read six such names (cold review, 2026-11-07). The exact
   ending stays refused whether the file exists or not; a word that only mentions the marker names no
   file. An exception to the read guard's freeze, for this rule alone (operator, 2026-11-07).

Admission of point 5 (`guard-admission`): (1) the identifier reaches the AI service from a faint page
that exits clean, seen on invented pages through the real tools; (2) it stops no reading of the
operator's data; (3) it acts before any model pass; (4) one more read per page, against a silent miss;
(5) one new hold flag, so an unread darkened copy is never reported as nothing faint.

Admission of point 7: (1) a copy of the filled form holds withheld names, the date of birth and phone
numbers, and a session's read sends them to the AI service; the cold review read six editor names
through Read and `cat`; (2) the data is declared never-API, the one exception the question allows, and
the operator still opens any of it in their own editor; (3) it acts at the read, which for an agent is
the send; (4) it trips only on an existing file holding the marker, so a commit message, a search or a
line of code naming it runs; (5) the same rule in its one home, with no new message.

## Alternatives considered

- A slot file of pattern lines for every install, filled in an editor: the first shape of the ruling
  of 2026-11-07. It would be read by nothing but a relay scan a stranger has no use for, and it needed
  rules about quotes, apostrophes and date forms.
- Only the identifier file, with a relay scan that runs without a registry: more code, and masking gets
  no better.
- Generating a v2 person's pattern lines from the identity file: nothing to generate once point 1 holds.
- Keeping the terminal prompt as the only route: declined by the operator, 2026-11-07.
- Refusing a literal `--dob` for a v2 person: fails the admission test's question 3, since the model has
  already written the date when the tool refuses. Point 4 removes the need instead.
- Holding v2 back from strangers, or deferring private mode from the public workflow: both smaller, both
  remove what the release offers (operator, 2026-11-07).
- A fixed 80% black point for the darkened read, the first shape of point 5: paper darker than it came
  out solid black and the page exited clean (cold review, 2026-11-07).
- The middle grey cell as the paper: a dark block over half an invented page pulled it down, the faint
  number came out light grey, and the page exited clean on real tools (2026-11-07).

## Consequences

- A stranger's relay scan stays blinded, and their care sessions cannot relay. An install that relays or
  exports sets up both files by the existing procedure, `checks/topics/relay-and-export.md`, unchanged.
- ADR-0062 point 5's opt-in for a full number needs an owner-only file that a care-only install lacks;
  the session adding those numbers builds it by point 3's method.
- Each page is read twice, and each masked re-read twice: 6.0 s to 10.7 s for a full invented page on the
  operator's Mac. Measured on invented pages only (50, each with and without the label): faint ink
  at six grey levels on white paper went from exiting clean to masked and held; dark ink, blur, low
  resolution, noise and skew kept their outcome; on grey paper from 70% to 95% and two tints, every
  number was masked, and every one the plain read missed was held; a dark block over half a page and a
  grey band on white paper hold as unreadable. No page exited clean with its number unmasked. No real
  scan has been tried, so the human gate remains the backstop.
- A page with a large dark area (a dark photo, uneven light on a phone capture) holds for the person to
  look, even when nothing faint is on it.
- Two ways to fill the identity file. TextEdit may keep its own version history of the form on the Mac,
  and, seen in TextEdit on 2026-11-07, a window left open and edited after the form is deleted writes it
  back when closed, readable by other accounts on that Mac. The read guard still refuses it, and any
  copy of it, by name; `status` shows it waiting and `take-form` clears it.
- A copy of the form saved outside the person's folder is refused to a direct read, but a content
  search over the whole folder it sits in can still reach it: the guard judges a folder by where it
  sits, not by what it holds, as it already did for the identity file's own name. Accepted by the
  operator, 2026-11-08, rather than walking every searched folder. Editors save their backups beside
  the form; inside the project, an ignore line keeps any such name out of commits and out of searches
  that honour ignore rules.
- Verified by `tools/private-mode/test_identity.py` (`Form`, `StrangerWalk`), `test_redact_ids.py`
  (the faint-read cases, `DobFromIdentity`), the form rows in `tools/claude-hooks/test_registry_guard.py`,
  the path cases in `tools/person_ownership/test_ownership.py` and the care-only bites in
  `checks/selftest.sh`.
