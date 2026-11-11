# Relay, token registry and export — the operator's procedures

Read when: you relay care prose into the development tree, keep the token registry current, set up or
add to the private-mode identifier's file, move the tokens of a person's kept details, or prepare an
export. The registry and the private-mode identifier's file are edited by the operator by hand,
outside any session; a session never opens either. A care-only install has neither and needs neither
(ADR-0068): nothing but its relay scan and export reads them, and both stay refused. The command index and the guards are in
[checks/README.md](../README.md).

**The CARE→DEV relay (`checks/relay-scan.sh <file>…`).** Under ADR-0050 incidents flow one way: a
failure seen in CARE becomes a keystone rule, an ADR row or an eval case **written in DEV**, as
abstract prose — never a file copy, and nothing copied word for word from a care folder.
`relay-scan.sh` is what proves that prose carries no personal detail before it is pasted (ADR-0072). It gates what DEV **stores**, not what a build session **reads**. Flagged private-mode
lines are replaced by number before a build session reads the note:
`awk 'NR==50||NR==63{print "[withheld]";next}{print}' note.md > "$SCRATCH/note.md"`. The scan runs **in CARE**, because CARE is the instance that legitimately holds the
registry. It matches the personal details: the identity class (names, handles, dates of birth), the
private-mode identifier from its own file (without that file the scan is blinded) and each kept-details
line. Real case dates are not kept on the registry: a leftover `PII_CASEREF` line there, or a
`PII_PRIVATE_CASEREF` line in the private file, is ignored by every reader, so delete it whenever
convenient. The clinical, brand and consent classes hold
words that on their own fit anybody, so the relay leaves them to the export gate, which scans every
class over what is published. DEV holds no token list of any kind
(a DEV-side identity scan would have re-created the very artifact the split removes); DEV's main
checkout, whose untracked pointers name the same out-of-tree files, scans the same way, and a linked
worktree, which has none, comes back blinded. Output is
**locators only** — `<CLASS> <file>:<line>`, content withheld — and it exits `0` clean, `1` on a hit,
`2` **blinded**: no registry, a symlinked or group/world-readable one, a missing, renamed or
duplicated class line, an empty or uncompilable regex in a matched class, no UTF-8 locale, a directory or symlink named as
input, an unreadable input, or zero inputs. It resolves the registry through the same
`registry_path()` every other reader uses; it refuses a **substituted** registry rather than scanning
against one — symlinked, group- or world-readable, or with a class line missing, renamed, duplicated
(a later duplicate shadows the live value under bash last-assignment-wins) or a sixth class added, or a
matched class emptied (an unmatched class's value is the export gate's to check); and
it **pins a UTF-8 locale** before any input is read, because under a C locale BSD grep silently
narrows the diacritic atoms — `-i` folding and adjacency then fail with rc=1, so no tripwire fires and
the scan reads clean. A sixth class added to the registry blinds it until the class is ruled in or out
of the relay. **Honest scope:** it catches *tokens*, not a re-identifying clinical picture told in
fresh words or a line copied from a care file — the abstract-prose relay rule and the CARE author's
judgment remain the control there. Bites: the relay-scan cases in `selftest.sh`.

**Keep the registry current before a relay or an export** (ADR-0013 point 5). A token never
added is invisible to every scan, so the upkeep sits at the transfer moment, not at intake. A relay
scan names the registry's last-change date (its mtime — never its content or path) only when some
person's ownership ledger (`patients/*/med/MANIFEST`: stat'ed, never opened or named) is newer than
the registry file — documents were filed, or a person added, since; with nothing filed it prints
nothing extra, so the notice never repeats without something to do. On that notice the operator adds,
by hand and outside any session: each new handle and — unless the person keeps it from the AI — the date
of birth in every printed format (`YYYY-MM-DD`, `DD.MM.YYYY`, `DD-MM-YYYY`) to the identity class;
newly distinctive condition or drug names to the clinical class. Then
re-scan. If there is nothing to add, touching the registry file records that the check was made and
quiets the notice until the next filing. A private-mode person's identifier prefix goes into the
private-mode identifier's own file at intake instead (`_templates/INTAKE.md` step 4); the tokens of a
person's kept details go there once they are recorded (`tools/private-mode/topics/kept-details.md` →
*Choosing what to keep*).

**The token registry — where it lives, how to move it, how to get it back (ADR-0050 Part A2).** The
publish firewall's four `PII_*` class lines must never be printed into a model session (a
bounded read once overran and printed them all). Part A1 put a session hook in front of the file; **A2
takes the file out of the tree the sessions run in**:
- The class lines live in one file **outside every git work tree** — `~/.tabularium/firewall-registry.sh`
  by default, mode **0600**. The untracked one-line config `checks/FIREWALL-REGISTRY` holds its path: a
  leading `~` is expanded, and the path must be **absolute** — readers resolve the config from
  different working directories and `check.sh` cds to the linted ROOT, so a relative path would resolve
  *inside the tree under test* (the `checks/OFFSITE-DEST` pattern of ADR-0045).
- `publish-skeleton.sh` sources it inline (it must run standalone); `snapshot.sh`, `relay-scan.sh` and
  `install-instance.sh` resolve it through `registry_path()` in `checks/config-paths.sh`, which each
  loads from its own directory and refuses to run without. `check.sh` resolves no registry — no guard
  reads one since L9/L12/L18 retired.
- The `PII_REST` composition line and the ALLOW/DENY lists stay in the export script, which is tracked
  product and ships in its own export.

*The move (done; its one-shot tool is retired).* A script took the class lines out of the tree once,
content-blind and proved by digest; it and its bites are in git history (the pre-shrink suite).

*The wrapped-brand adjacency pairs.* The export gate's wrapped-brand lane reads the **component words** of
the guarded brand phrases from the registry as `BRAND_ADJ_PAIRS` (moved there once by a one-shot
script, since retired; its bites are in git history, the lane's own run in `selftest.sh --export`).
- Encoding: `BRAND_ADJ_PAIRS='<left> <right>|<left> <right>|…'` — pairs split on `|`, the two sides on
  one space, each side an unanchored ERE fragment the lane anchors as `^(side)$` and matches against one
  lowercased word. A word is ASCII letters plus the accented Latin letters (U+00C0–U+017F); digits and
  other characters split words. Write an accented letter literally and in lower case, never inside a
  bracket expression or as `.`: the awk on macOS and Linux reads a regular expression byte by byte.
- The name deliberately does **not** match `PII_[A-Z]+=`: every reader that counts the class *set*
  (`relay-scan.sh`, `evals/harness/containment.py`) must
  keep counting exactly four with this line present.
- **Fail closed:** a missing or empty `BRAND_ADJ_PAIRS` is a hard `ABORT: registry: BRAND_ADJ_PAIRS
  missing`, never a silently disabled lane — an old registry or a pre-move banked copy must not export
  quietly.

*If it goes missing:* a config that names nothing readable, a **symlinked** registry or a
**group/world-readable** one each **abort** the export gate and blind the relay scan (exit 2) — never a
quiet fallback to scanning nothing. Recovery: `.snapshots/<ts>/external/firewall-registry.sh`
(`snapshot.sh` banks the out-of-tree registry beside the canonical docs, same 0600 discipline); the
layer-2 tarball excludes `.snapshots/` and never held the out-of-tree file. No recurring output of the `checks/`
scripts prints the registry's path (a location in the operator's home); messages name
`checks/FIREWALL-REGISTRY` instead. The one exception: the eval harness's containment diagnostic and
misconfiguration aborts (`evals/harness/containment.py`).
**What is no longer detected (ADR-0050 Part B):** a silent *change to a class value* in that file.
To check a suspect class line, diff it against an earlier banked copy,
`.snapshots/<ts>/external/firewall-registry.sh`.

**The private-mode identifier's own file (ADR-0050 point 9).** Only one thing in the
registry is secret from model sessions: the private-mode identifier (ADR-0029). The rest still lives
outside every repository and is never committed, published or pasted into a tracked file, but is no
longer secret. The identifier lives outside its class line, in **its own owner-only file beside the
registry**, named by a second untracked pointer, **`checks/PRIVATE-MODE-ID`** (one line, the absolute
path; same rules as `checks/FIREWALL-REGISTRY`). The file holds exactly one class line,
`PII_PRIVATE_MODE_ID='<pattern>'` — and, for kept details, one `PII_PRIVATE_<CLASS>` line per registry
class holding a person's kept-detail tokens (below). Who reads it:
- `relay-scan.sh` and `evals/harness/containment.py` parse both files, scan it as a class of its own
  (and each kept-details line too), and
  report **blinded** without it;
- the export gate *sources* the registry, so the registry folds the identifier back into its class
  with the block below, and the export script is unchanged;
- `snapshot.sh` banks it as `external/private-mode-id.sh`;
- `install-instance.sh` verifies the split without printing anything from either file, and only then
  shrinks the read-guard to the new file and its pointer (`tools/claude-hooks/README.md`).

A digest of the new file is never computed or recorded anywhere: a one-line file's hash can be
brute-forced back to its content.

*Setting up the file, or adding to it* — by the operator, in Terminal and a text editor, never inside a
model session. Set it up with the steps below. For an existing unsplit registry, first adopt the
release carrying the split scanner in CARE, as ADR-0050 point 9 requires; the original migration
transcript remains at `12572a0`.
1. The file sits in the registry's directory (`private-mode-id.sh`), mode `0600`, and holds a `#`
   comment line and `PII_PRIVATE_MODE_ID='<pattern>'`, plus a kept-details line per class (below).
   Alternatives are joined with `|` inside the one pair of quotes; a value holds no `'` (write an
   apostrophe as `.`); leave no `||`, no leading or trailing `|` and no empty `()`. Leave no copy of
   the registry or this file in that directory or below it — an editor's backup counts: the installer
   refuses while any other file there still carries one of its values.
2. The registry ends with the block below, its `tab_pmid_file=` line naming this file's absolute path.
3. `checks/PRIVATE-MODE-ID` holds that path in the main checkout and in the care checkout:
   `printf '%s\n' "$HOME/.tabularium/private-mode-id.sh" > checks/PRIVATE-MODE-ID` (use the real path).
4. Verify: `bash checks/install-instance.sh dev` in the main checkout and `checks/install-instance.sh
   care` in care must each print `private-mode identifier: split verified`. If one prints `split
   NOT verified — …`, fix what it names and run it again; until it verifies, the read-guard keeps
   protecting the whole registry. Then `bash checks/relay-scan.sh` on any plain text file must print
   `clean (1 files, 2 classes)` (one more per kept-details line), and `python3 -m evals.harness.containment` must
   print `pre_transit_scan    : clean`.
5. On first setup, start new sessions afterwards — the hook reads its paths when a session starts —
   and, on an older client that reads a worktree's own settings, run the installer in each worktree
   made before it, or retire that worktree.

**Kept details: moving a person's tokens (ADR-0029 point 13, ADR-0075).** Once a person's kept
details are recorded (`tools/private-mode/topics/kept-details.md` → *Choosing what to keep*), the tokens
the registry holds for those details must stop being readable by sessions. Same
hands, same places, never inside a model session:
1. Paste the **current** block below over the old one at the end of the registry (it folds the new lines
   back for the export gate; the old block refuses them and the export aborts, which is safe).
2. For each registry class holding such tokens, **cut** them out of its line and add one line to the
   private file: `PII_PRIVATE_<CLASS>='<pattern>'` (`IDENTITY`, `CLINICAL`, `BRAND` or `CONSENT`), alternatives joined with `|` inside the one pair of quotes (`'a|b'`, never `'a'|'b'`);
   at most one line per class, no other kind of line (every other line blank or a `#` comment, each
   line exactly `NAME='value'` — no `export`, no spaces around `=`, no `'` inside the value: write
   an apostrophe as `.`). Leave no `||`, no stray `|` and no empty `()` behind, and **never empty a
   class**: if the cut takes its last token, leave one invented placeholder token there. Anchor a
   short alternative (`\b`): one that is part of a longer word beside the registry, the block's own
   comment included, is refused as *copied, not cut*. The brand adjacency pairs (`BRAND_ADJ_PAIRS`)
   have no private line — keep a person's kept details out of them.
3. Verify as in step 4 of *Setting up the file* above, in both checkouts: `split verified` again, or the
   reason it is not (a value copied rather than cut, a line the registry does not fold back); the relay
   scan counts one more class per line.
Adopt the release carrying this in care before the move, as for the split itself (ADR-0050
point 9): an older care scanner refuses the new lines (it blinds, the safe state).

**Two residues stay behind; removing them is the operator's call:** the 2026-09-05 session transcript
and, in the care checkout, every `.snapshots/<ts>/external/firewall-registry.sh` banked
*before* the split — those copies still carry the identifier and are unprotected once the split verifies.
The same holds after a kept-details move: registry copies banked before it (the setup's own pre-edit snapshot
included) still carry that person's tokens, readable by sessions.

<!-- private-mode-id-block:begin -->
```bash
# ---- the private-mode identifier lives in its own owner-only file (ADR-0050 amendment 2026-09-16) ----
# The relay scan and the eval's pre-transit scan read that file themselves. This block is for the
# export gate, which SOURCES this registry: it folds the identifier back into its class, and each
# kept-details line (PII_PRIVATE_<CLASS>, ADR-0029 point 13) back into <CLASS>; a
# PII_PRIVATE_CASEREF line (a retired class) is accepted and not folded. If the
# file is missing, not owner-only, or carries any other non-blank, non-comment line, a second line
# of one name or a ' inside a value, it unsets the identity class so the export aborts. The file is
# parsed, never sourced. Keep this block at the end.
tab_pmid_file='/ABSOLUTE/PATH/OF/private-mode-id.sh'
tab_pmid_val=''
case "$(ls -ld "$tab_pmid_file" 2>/dev/null)" in -r??------*)
  [ "$(LC_ALL=C grep -cvE '^[[:space:]]*(#.*)?$' "$tab_pmid_file" 2>/dev/null)" = \
    "$(LC_ALL=C grep -cE "^[[:space:]]*PII_PRIVATE_(MODE_ID|IDENTITY|CASEREF|CLINICAL|BRAND|CONSENT)='[^']*'\$" "$tab_pmid_file" 2>/dev/null)" ] &&
  [ "$(LC_ALL=C grep -c '^[[:space:]]*PII_PRIVATE_MODE_ID=' "$tab_pmid_file" 2>/dev/null)" = 1 ] &&
  [ "$(LC_ALL=C grep -cE '^[[:space:]]*PII_PRIVATE_[A-Z_]+=.*PII_PRIVATE_' "$tab_pmid_file" 2>/dev/null)" = 0 ] &&
  tab_pmid_val="$(sed -n "s/^[[:space:]]*PII_PRIVATE_MODE_ID='\([^']*\)'\$/\1/p" "$tab_pmid_file" 2>/dev/null)" ;;
esac
if [ -n "$tab_pmid_val" ]; then
  PII_IDENTITY+="|$tab_pmid_val"
  for tab_pmid_c in IDENTITY CLINICAL BRAND CONSENT; do
    case "$(LC_ALL=C grep -c "^[[:space:]]*PII_PRIVATE_${tab_pmid_c}=" "$tab_pmid_file" 2>/dev/null)" in
      0) ;;
      1) tab_pmid_val="$(sed -n "s/^[[:space:]]*PII_PRIVATE_${tab_pmid_c}='\([^']*\)'\$/\1/p" "$tab_pmid_file" 2>/dev/null)"
         if [ -n "$tab_pmid_val" ]; then eval "PII_${tab_pmid_c}+=\"|\$tab_pmid_val\""; else unset PII_IDENTITY; fi ;;
      *) unset PII_IDENTITY ;;
    esac
  done
else unset PII_IDENTITY; fi
unset tab_pmid_file tab_pmid_val tab_pmid_c
```
<!-- private-mode-id-block:end -->

**The flip-time export — the mechanics (ADR-0012/0013/0017, slimmed by ADR-0050).** The rules that
govern the one surviving gate:

- *Allow-list, never deny-list.* The export copies only what `ALLOW` names — path by path — into a
  fresh temp tree, so a file nobody deliberately added is simply absent. `DENY` is a belt over the
  result, and a structural sweep refuses any record-shaped directory nested under an allow-listed one.
- *Identity **and** clinical fingerprint (ADR-0013).* De-identification is not name-stripping: a
  family's distinctive condition/procedure/date fingerprint re-identifies it to anyone who knows them.
  So the identity class is scanned in its own lane (it has carve-outs), the clinical and brand
  classes in another, the consent-gated attribute class in a third — and all of them again over
  every file *name*. Any hit aborts before a commit exists; a scan error (rc ≥ 2) aborts too — no
  output from a broken grep is not "clean".
- *A release is exported from its tag and appended (ADR-0066).* `publish-skeleton.sh vX.Y.Z` reads the
  tag's committed tree and note, never the working tree, and refuses a name that is not exactly
  `vMAJOR.MINOR.PATCH`, a missing or lightweight tag, a tag that origin does not carry as it is here or
  whose commit is not on origin's `main`, or a running script that is not the tag's own (its ALLOW list
  decides what ships: run it from the tag, `git switch --detach vX.Y.Z`). The tree must arrive byte for
  byte, so an attribute that changes archived files aborts, and a release builds only into an empty folder. The result, in a temp
  directory, is one commit and the annotated tag. With `REMOTE=` it sits on top of the public main, read
  only; a remote that cannot be read aborts, and so does a public main that is not its newest release (an
  old display copy, a hosting site's starter README), a main holding commits this export did not make, a
  copy with refs but no main, or a main that moves while it is read. After a first push the copy's default
  branch must be `main`; if it is not, the script says so and exits 3. The staged bytes must be the
  scanned ones, so a clean filter at staging aborts. The first release is a root commit into an empty
  repository and each later one appends one, so every public commit is a release and a plain clone stands
  at the newest tag. A name with a leading zero is refused. `--push`
  never forces and sends both refs or neither; a tag already there, an older one or a release that
  changes no exported file is refused. DEV's own history is never published. What reached a public release
  stays in the public history: the fix is a new release, and removing it means replacing the repository,
  an operator decision.
- *With no tag named it only scans.* The working tree's allow-listed files get every scan and the parity
  check, with no commit and no tag, and `--push` is refused. A tag never moves, so the scan has to be
  able to run before the tag exists.
- *The note is public text.* The tag's note reaches the public copy word for word, without a signature
  (it carries the signer's key): the shipped `/update` skill reads its `Adoption:` and `Rollback:` lines. It gets every class with no carve-out, and a hit
  prints no content. A tag never moves, so a hit means a new release with a clean note.
- *A stranger's first care session is part of the gate.* `selftest.sh --export` walks this tree's tracked
  files from a tag through the export, a clone, the intake procedure and the care installer to a green board,
  and on through an appended release, the notice and an adoption.
- *The self-reference discipline.* Never write a real handle, date, identifier or condition fingerprint
  into a tracked file — comments, ADRs and bites included; describe the case abstractly. That is why
  every export-gate bite writes its own synthetic registry. (The export script itself holds no token since A2
  and ships in its own ALLOW list.)
- *The hold.* `checks/PUBLISH-HOLD` gates `--push` and nothing else — a dry build runs under a live
  hold on purpose, so the gate can be exercised any day. Lifting it is an operator act, and the PUBLIC
  flip happens only on the operator's explicit, current request, never inferred from a roadmap line or
  a prior plan. The step-by-step runbook is operator-side and stays in DEV — `docs/FLIP-RUNBOOK.md`,
  local to the main checkout and never exported: the ceremony is run from this repository, not by a
  recipient of the skeleton.
- *The ceremony's standing rules* (the runbook's steps stay in that file):
  - **Four preconditions, in order:** the right instance (`dev`, board green, L20 record-free — a red
    board is a stop, not a caveat); `bash checks/selftest.sh --export` at `0 failed` — the suite plus the
    export gate's full matrix, which proves the scan still bites; a clean **dry** release build from the tag, with `REMOTE=` naming the destination (`firewall: clean`, `deny-list: clean`, and a
    recorded `commit parity` file count — know why if it moved); and a **whole-tree** relay scan over
    every tracked file, not just the ALLOW surface, with every hit accounted for individually (a hit you
    cannot explain is a stop).
  - **A private-ring push is not a step toward the PUBLIC flip.** They are separate decisions, and
    each ledger entry says so explicitly. A repository that took a push keeps every release pushed to it,
    so it is never made public by a visibility change: the public copy starts as an empty repository.
  - **Never advise a way around the gate** — `--no-verify`, deleting the sentinel, widening `ALLOW`
    to quiet a scan, or re-running until it passes. An aborted scan is information: fix the content,
    never the gate.
  - **The registry is never opened.** The gate reads it; you do not. Locators are all you get, and
    they are enough.
  - **A failed publish leaves nothing behind** — the build is a temp directory and never touches the
    local repository; restore the hold, delete the temp tree, report.
  - **Re-examine the identity disclosure the export actually makes, at a public flip:** the notice
    file's copyright line and the citation file's author, which trade the operator's own identity against the household's
    de-identification; re-decide that trade out loud when it becomes public. The **export commit's
    author and committer** are one fixed identity in the exporter, the maintainer's name and GitHub
    no-reply address, never local git configuration or the environment. It is added *after* the firewall scan, so no scan sees it — the
    fixed value is the guarantee, and `selftest.sh --export` bites it.
