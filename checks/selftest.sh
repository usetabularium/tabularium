#!/usr/bin/env bash
# Bite-tests: a guard is only real once it's proven to catch a KNOWN defect.
# One test plus one negative control per guard and per kept tool (operator decision 2026-10-04): the
# test injects the incident into a MINIMAL SYNTHETIC fixture (ADR-0038 — never a copy of the working
# tree, one --export walk of the tracked files aside; no real patient names, so this script is PII-free and portable to the public skeleton) and
# asserts the guard fires; the control is the same fixture without the defect, or the real-world
# false red, and must stay green. Extras cover a second incident class the pair cannot see; a few
# static lints guard the suite's own wiring. The retired guards' and one-shot tools' bites and the
# wider private-mode v2 bites live in git history (the pre-shrink suite). The export gate's wider matrix
# runs only with --export (about a hundred synthetic exports): required before any export; CI runs it.
#
# What the suite bites beyond the board guards (checks/README.md → Guards owns those):
# - worktree retirement (`retire-worktree.sh`, ADR-0040): unique dirty bytes refuse and the worktree
#   survives; a clean merged tree moves atomically into owner-only `retired-worktrees/` inside the common
#   git dir (no record path in any work tree), git-locked, rechecked and retained, not deleted, its
#   branch kept.
# - publish firewall (`publish-skeleton.sh`, on a synthetic registry the fixture writes): a planted
#   identity-class token ABORTs and the clean twin passes; a scan whose grep errors (rc≥2) aborts rather than
#   printing clean; the entrypoint is executable and the script carries only the `PII_REST` composition line.
#   The wider matrix runs only with `selftest.sh --export` (about a hundred synthetic exports, about a minute): the other
#   classes, consent marker, locale pin (an accented token under an inherited C locale), private-mode split,
#   deny-list belts, contract preflight, NOTICE and CITATION carve-outs, registry fail-closed arms, filename lane, binary and
#   symlink guards, inherited git env, the export commit's fixed identity, the hold, the release path (the
#   tag's refusals, tree and note, the append, no force, and the whole route from a tag to a stranger's green
#   first care session), the wrapped-brand lane (an accented pair included) and the eval-case classification. Run it before any export and after changing
#   the export script; CI runs it on every run. The hold is bitten in all three directions: a dry build under
#   it still runs; a held `--push` with `REMOTE` aborts before any git call; `--push` without `REMOTE` refuses.
#   The `--push` bites run the fixture's copy of the publisher with the hold present, `REMOTE` a missing path
#   inside the fixture and network transport off for every git call; each has a negative control (its check
#   made a no-op).
# - recovery floor (`snapshot.sh`, `backup-tree.sh`): an empty or unrelated root refuses before any recovery
#   data is touched, against a real owner-only atomic capture of the canonical docs and the firewall script;
#   a scan under a nested `outputs/` directory is captured while the top-level `outputs/` stays out, against a
#   plain tree backed up complete. Stub `sync` and `perl` prove the snapshot flushes its copies before it
#   publishes and the publication before its result line. What else power loss can do, and standalone
#   topology, remain known limits.
# - off-machine mirror (`backup-offsite.sh`): an unmarked destination refuses, a marked one mirrors and
#   verifies, also through a symlink that resolves outside the repository, while one that resolves inside it
#   or onto a folder holding it refuses with nothing written; `--verify-only` with no mirror reports it and
#   creates nothing; completeness is per file: a missing file is indeterminate even when an old extra file
#   makes the count match, a file of another size refuses, and a name stored decomposed (NFD) still matches;
#   after two recorded renames the old copies are kept, counted and verify, as does an extra file, while a
#   current source missing or changed at the same size refuses; the rsync invocation never carries `--delete`.
# - CARE→DEV relay scan (`relay-scan.sh`): a planted token of the identity class reds with a locator only
#   and its text absent from the output, abstract prose scans clean and states its coverage; a kept-details
#   line of any class reds, clinical, brand and consent tokens scan clean, a leftover case-reference line (registry
#   or kept-details) is ignored and its absence changes nothing, and a fifth or renamed registry class blinds; no registry exits 2; a ledger newer than the registry makes the scan name the registry's last-change date from its mtime —
#   no path, handle or token — and with no filing since it prints no reminder.
# - instance installer (`install-instance.sh`): existing settings keys and deny rules survive the merge; a
#   fresh `dev` install writes the marker, four executable hooks and the read-guard settings, and a second run
#   is `unchanged` with no duplicate hook; the context-health hook is wired in `dev` and removed by a `care`
#   run, which keeps the operator's own hooks; a Tabularium hook sharing an entry with the operator's own
#   moves to an entry of its own, the operator's matcher untouched; a correct private-mode identifier split
#   verifies, and a copy of the identifier left beside the registry un-verifies it and restores the registry's
#   protection; private mode's setup costs the install one line and never its exit code; an unknown mode
#   is refused with nothing written. In care: an install that fails late (a missing
#   skill source) leaves the previous pin, while a complete one writes it last; a tag that is not checked out is refused with nothing written, the one at HEAD
#   accepted; a skill, Tabularium git hook and settings hooks of its own that the release does not ship are
#   removed, each printed — a hook sharing an entry leaves it alone, the operator's hook and matcher in place —
#   while what the release ships and the operator's own skill, hook and entry come through intact; below a
#   newer release, its skill and a hook outside the four known names, each byte for byte a release tag's own,
#   are removed, while an edited released skill and a headed hook of other bytes stay with a warning and the
#   operator's own skill and an unmarked hook stay without one. The release notice's start hook (matcher
#   `startup`) and `/update` are installed once in care, never in dev, and a release without the hook's
#   script removes it.
# - Mac setup (`setup-mac.sh`): on a stubbed Mac without Apple's tools, the tools are named with their Terminal line,
#   exit 1, and neither placeholder (git, python3) is run; with them, base is complete and the AI-service line
#   prints once; a folder in Documents draws its note; another system is refused. `pre-approve` keeps existing
#   settings, adds only the checks, snapshots and filing tools, says so once, and refuses a settings file it
#   cannot read with the file untouched. Private mode with no Homebrew stops for the person (exit 2) with
#   nothing installed; with Homebrew it installs what is missing, the language pack only when needed, and
#   ends on the read-only check's word; a Homebrew found only in its standard home is added to the shell's
#   path once; a bad language code exits 64. Handouts installs the pinned Python and the renderer's libraries,
#   hands that Python to the rebuild script, and a failed rebuild exits 1.
# - private mode's setup check (`tools/private-mode/check-setup.sh`): on a stubbed Mac, a too-old Python, missing
#   English language data and no ImageMagick are each named with their install command, Homebrew first, exit 1;
#   another row's missing language is reported, not needed; on a stubbed Linux machine it says macOS only
#   and gives no install command: with every tool needed now it is complete, exit 0, and one missing exits 1;
#   a python3 that does not run and missing orientation data are caught, and --summary exits 1.
# - release adoption (`adopt-release.sh`): no argument adopts the newest `vX.Y.Z` (numeric order, slugged and
#   non-release tags ignored); a release that tracks an ignored record's path is refused by real git with the
#   record untouched; a re-run after a red board finds the previous release in HEAD's reflog, and says so when
#   there is none; a checkout stopped with HEAD unmoved — when git stops, and on a re-run after a kill — loses
#   only the release's own untracked copy and prints one `&&` line that, followed, ends on the release, while a
#   file of other bytes, the operator's own, a record-set path and an ignored record survive, a set over fifty
#   announced first; a partly written copy (a strict prefix, 0 bytes included) is removed too, while a longer
#   file and a shorter one of other bytes stay; a stale index
#   lock makes that line start with its removal (none without a lock, and none while a git works there).
# - release notice (`release-notice.sh`, ADR-0055 companion): a pin a MINOR or MAJOR behind origin's newest
#   strict `vX.Y.Z` speaks (exit 1, five fixed lines; numeric order, every other tag shape ignored), a patch
#   behind and up to date stay silent; a legacy slugged pin compares by its numbers, no pin is no answer; a
#   failing remote's address never reaches the output; one that never answers is cut off within seconds,
#   with what git started killed; `--daily` asks origin once a day, a failed attempt included, its stamp in
#   git's own directory, four simultaneous starts asking once, and the opt-out file stops it; outside care it is inert. Its adapter prints one line only for a MINOR or MAJOR
#   gap with release-shaped names — nothing for a resumed session, a patch, an exit 0 or a missing check.
# - line endings (`.gitattributes`): a clone under `core.autocrlf=true` checks out LF and `check.sh` runs; without
#   the file the same clone writes CRLF and the run fails.
# - git hooks: `pre-commit` blocks a red tree and commits a green one; `commit-msg` blocks an override not
#   named in the message and allows it named; `pre-merge-commit` blocks a red auto-committed merge and passes a
#   green one; `pre-push` blocks a tree marked `dev` that holds records and allows a record-free one; on one
#   fixture, an unknown marker reds guard L20 and blocks the push, the `dev` twin passing both.
# - handout renderer (needs `.venv-render`, loudly skipped without it; CI has none): the seal gate refuses an
#   unverified seal and writes nothing; a real sealed render satisfies L15; each print font file covers
#   printable ASCII, Latin-1 and Latin Extended-A, and a body font without ą is caught.
# - print font names: every font stack in `handout.css` and the renderer's footer starts with a family an
#   `@font-face` declares, and a stale footer or body name is caught.
# - fact-check bundle (`make_verify_bundle.sh`): a wrong-person entry is refused with the person-scope fault
#   named; the happy path's digest matches its file and omits the handout body; a relied-on name carrying a
#   newline is refused as a control character, not by a later refusal.
# - every `tools/*/` and `evals/*/` `test_*.py` suite runs inside the suite, one process each, and a module that
#   runs no test, or skips them all, fails (bitten on a synthetic tree); CI runs this suite and keeps no list of
#   its own. The suites found must match `checks/PYTHON-SUITES` plus `-DEV`: one missing or one listed in neither
#   is red (bitten in a scratch tree with lists of its own, an export-shaped one staying green). The two hook matrices carry their own negative controls (a stub that allows everything, one that
#   never speaks).
# - `confirms.sh`: an overdue tag or open-items row exits nonzero; future-only tags and rows stay green. A
#   deadline it cannot read (month 13, a short month, a non-breaking space) is MALFORMED, exit 1, while prose,
#   the undated tag and the templates' placeholders stay green; an unreadable file, a folder `find` cannot
#   list or a ROOT outside the repo is exit 2, and a NUL byte hides nothing; analysis notes are scanned,
#   sealed handouts are not, and a private-mode person's note name is withheld.
# - static lints: host portability (a named list of bash-4 and GNU-only constructs — each pattern caught in a
#   planted sample, a portable twin clean, an unscannable target a failure), executable documented entrypoints
#   (a failed `git ls-files` is a failure, not "untracked"), no silent self-skip in `check.sh`, the
#   tooling-shaped record list written identically in `check.sh` and the `pre-push` hook, and the three
#   consumers of `checks/config-paths.sh` refusing without it.
# - `check.sh` over the live tree stays clean, and a zero-patient repo and a person scaffolded as
#   intake does (profile, medications and handout register from `_templates/`) are green — the
#   empty-array and template↔guard drift classes.
# - the suite's own wiring: the git environment a hook passes down is stripped at entry (an inherited GIT_DIR
#   aimed at a decoy repository never reaches a fixture's `git -C`, and does without the strip); every
#   self-skip goes through `skip`, and an id outside the expected set is reported.
#
# Self-skips: every case that cannot run here prints one line, `SKIP  [<id>] (LOUD): <reason>`, and the closing
# summary lists the ids (a self-skip of the live board joins as `board-<guard>`). With `--expect-skips "<id> …"`
# any id outside that set fails the run; CI names its set in `.github/workflows/skeleton-check.yml`, the one
# home of that list. A local run may legitimately skip other things, so without the flag it only lists them.
#
# Usage: checks/selftest.sh [--export] [--expect-skips "<id> …"]
set -uo pipefail
# A git hook exports GIT_DIR / GIT_INDEX_FILE (an absolute GIT_DIR in a linked worktree), and they override
# `git -C`: a fixture's `git init` or `git -C "$d" config` then writes into the CALLER's repository — the class
# that once flipped `core.bare` in the real one. Stripped once, here, before any case; the
# per-call `env -u` wrappers below stay as belts for code copied out of this file. Bitten in the git-env case.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY
EXPORT_MATRIX=0; EXPECT_SET=0; EXPECT_SKIPS=""
st_usage(){ echo 'usage: checks/selftest.sh [--export] [--expect-skips "<id> …"]' >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --export) EXPORT_MATRIX=1 ;;
    --expect-skips) [ $# -ge 2 ] || st_usage; EXPECT_SET=1; EXPECT_SKIPS="$2"; shift ;;
    # an unknown argument (a typo of --export) must not quietly run without the matrix
    *) st_usage ;;
  esac
  shift
done
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHECK="$ROOT/checks/check.sh"
CONFIRMS="$ROOT/checks/confirms.sh"
pass=0; fail=0
echo "selftest env: $(uname -s) / bash ${BASH_VERSINFO[0]}.${BASH_VERSINFO[1]}"
# skip id reason — EVERY self-skip in this suite goes through here: one greppable line, and the id
# joins SKIPPED for the closing summary and the --expect-skips comparison. Ids are lower-case words and dashes.
SKIPPED=""
skip(){ echo "SKIP  [$1] (LOUD): $2"; SKIPPED="$SKIPPED $1"; }
# skip_unexpected skipped expected -> the skipped ids absent from the expected set, each with a leading space
skip_unexpected(){ local s e hit out=""
  for s in $1; do hit=0; for e in $2; do [ "$s" = "$e" ] && hit=1; done; [ "$hit" -eq 1 ] || out="$out $s"; done
  printf '%s' "$out"; }

# mk — a MINIMAL SYNTHETIC fixture (ADR-0038): what the L0 precondition needs to RUN (CLAUDE.md plus a
# checks/ directory). Every case builds its own synthetic patients/.
mk(){ local d; d="$(mktemp -d)"
  : > "$d/CLAUDE.md"; mkdir -p "$d/checks"
  echo "$d"; }

# write a VALID profile (passes the FULL L1 lint — all headers, ≥25 lines, no trailing table row)
# for a synthetic patient. Used by most cases AND the HOOK cases (where a green tree must commit).
valid_profile(){ # path
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<'EOF'
# Profile — Example
_synthetic fixture; no real person._

## Active conditions
| Condition (PL) | Status | Evidence |
|---|---|---|
| example one (przyklad jeden) | stable | analysis |
| example two (przyklad dwa) | watch | analysis |

## Current status
Synthetic record used only by the bite-tests. Nothing here is real.
Two example conditions, both stable enough for this fixture.
This profile exists solely to give check.sh a fully-valid tree to pass,
so the HOOK bite-tests can prove a green commit is allowed through.

## Next steps
- Planned: nothing (fixture).
- Recommended: nothing (fixture).

## Notes
- No medications, sources, or handouts: this fixture only needs to clear L1.
- Padded past the L1 minimum-length floor on purpose.
- One more padding line, so the floor holds with a margin.

## Change log
- created (synthetic fixture for checks/selftest.sh)
- padded to clear the L1 min-length floor
EOF
}

sha_file(){ if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }
sha_in(){ if command -v shasum >/dev/null 2>&1; then shasum -a 256 | cut -d' ' -f1; else sha256sum | cut -d' ' -f1; fi; }

# a FRESH PASS/0 fact-check sidecar for a handout — the file the renderer's seal gate demands and L15 binds
mk_pass_sidecar(){ # handout-path
  printf 'handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\n\n# Fact-check ledger\n- ok\n' "$(sha_file "$1")" > "${1%.md}.factcheck.md"
}

# L15: flat handout files need a .legacy-frozen inventory (the real freeze-legacy CLI) or L15 reds them
mk_legacy_freeze(){ # fixture-dir handle
  ( cd "$ROOT" && python3 -m tools.handout_attest --root "$1" freeze-legacy "$2" >/dev/null )
}

# L13: evidence under med/sources needs an ownership MANIFEST or L13 reds it. mk_ownership runs the
# deterministic migration over a fixture; mk_append adds a later source through the append writer.
# The verifier package loads from $ROOT (this repo), not the fixture.
mk_ownership(){ # fixture-dir
  PYTHONPATH="$ROOT" python3 -m tools.person_ownership --root "$1" migrate >/dev/null 2>&1
}
mk_append(){ # fixture-dir handle relpath
  PYTHONPATH="$ROOT" python3 -m tools.person_ownership --root "$1" append "$2" add --relpath "$3" >/dev/null 2>&1
}

assert_fail(){ # dir tag label
  local d="$1" tag="$2" label="$3" out rc
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q "\[$tag\]" <<<"$out"; then
    echo "BITE  OK  ($label): $tag fired"; pass=$((pass+1))
  else
    echo "BITE  MISS ($label): expected $tag, rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; chmod -R u+rwX "$d" 2>/dev/null; rm -rf "$d"; }   # permissions back first: some bites chmod 000

# assert_warn dir tag want avoid label — a warning-only guard (L4, L6): the board stays GREEN (rc 0), prints
# `WARN [tag]` with `want` and never `avoid` (fixed strings; empty = no check), and no `FAIL [tag]`.
assert_warn(){
  local d="$1" tag="$2" want="$3" avoid="$4" label="$5" out rc
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q "^WARN \[$tag\]" <<<"$out" && ! grep -q "^FAIL \[$tag\]" <<<"$out" \
     && { [ -z "$want" ] || grep -qF -- "$want" <<<"$out"; } \
     && { [ -z "$avoid" ] || ! grep -qF -- "$avoid" <<<"$out"; }; then
    echo "BITE  OK  ($label): WARN $tag, board green"; pass=$((pass+1))
  else
    echo "BITE  MISS ($label): expected rc=0 and WARN $tag with '$want' and without '$avoid', rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; rm -rf "$d"; }

# assert_quiet dir tag label — the control twin of a warning-only guard: rc 0 and neither `WARN [tag]` nor `FAIL [tag]`.
assert_quiet(){
  local d="$1" tag="$2" label="$3" out rc
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && ! grep -qE "(WARN|FAIL) \[$tag\]" <<<"$out"; then
    echo "BITE  OK  ($label): $tag quiet"; pass=$((pass+1))
  else
    echo "BITE  MISS ($label): expected rc=0 and no WARN/FAIL $tag, rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; rm -rf "$d"; }

LOC_PRIV='<locator withheld: private-mode person>'
pm_mark(){ printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩.\n' >> "$1"; }

assert_pass(){ # dir label
  local d="$1" label="$2" out rc
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then echo "CLEAN OK  ($label)"; pass=$((pass+1))
  else echo "CLEAN FAIL ($label): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi; rm -rf "$d"; }

# confirms.sh queue monitor: assert its exit code (0 = nothing overdue or malformed, 1 = something is,
# 2 = setup error or an incomplete scan) and, optionally, a fixed string the output must carry (want)
# and one it must not (avoid). The fixtures hold only the injected tag, so the result depends on nothing
# else and not on the wall clock. Permissions are restored before the reap (some bites chmod 000).
assert_confirms(){ # dir expected_rc label [want] [avoid]
  local d="$1" exp="$2" label="$3" want="${4:-}" avoid="${5:-}" out rc
  out="$(bash "$CONFIRMS" "$d" 2>&1)"; rc=$?
  if [ "$rc" -eq "$exp" ] && { [ -z "$want" ] || grep -qF -- "$want" <<<"$out"; } \
     && { [ -z "$avoid" ] || ! grep -qF -- "$avoid" <<<"$out"; }; then
    echo "CONF  OK  ($label): rc=$rc"; pass=$((pass+1))
  else echo "CONF  FAIL ($label): expected rc=$exp${want:+ with '$want'}${avoid:+ without '$avoid'}, got rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
  chmod -R u+rwX "$d" 2>/dev/null; rm -rf "$d"; }

# 0. the real repo is clean — asserted against the LIVE tree (no copy): the one case that sees the real
# canonical docs, reference library and instance shape. Inline, never via assert_pass (which reaps its dir).
if out="$(bash "$CHECK" "$ROOT" 2>&1)"; then echo "CLEAN OK  (unmodified repo)"; pass=$((pass+1))
else echo "CLEAN FAIL (unmodified repo)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
# a guard that skipped itself on the live tree (it prints `SKIP (LOUD)`, linted below) is a self-skip of this run
while IFS= read -r st_line; do
  case "$st_line" in
    *'SKIP (LOUD)'*) st_g="${st_line%% *}"; case "$st_g" in L[0-9]*) ;; *) st_g=unnamed ;; esac
      skip "board-$st_g" "the live board: ${st_line#*SKIP (LOUD): }" ;;
  esac
done <<EOF
$out
EOF

# --- the guards: one test, one control each ---------------------------------------------------------

# L0 — a guard must refuse to run outside the repo, not pass vacuously over an empty tree
d="$(mktemp -d)"
assert_fail "$d" L0 "precondition refuses a non-repo dir"
assert_pass "$(mk)" "skeleton-safe: zero-patient repo passes green (no empty-CANON crash on bash 3.2)"

# L1 — the 38-line truncation: a profile that stops at its conditions table
d="$(mk)"; mkdir -p "$d/patients/sztest1"
printf '# Profile — t\n## Active conditions\n| a | b |\n|---|---|\n| x | y |\n' > "$d/patients/sztest1/profile.md"
assert_fail "$d" L1 "truncated profile (the real incident)"
# control: a person scaffolded FROM the shipped templates (profile, medications, handout register — the
# intake scaffold) passes (template↔guard drift)
d="$(mk)"; mkdir -p "$d/patients/szttemplate/med/handouts" "$d/patients/szttemplate/med/sources" "$d/patients/szttemplate/med/_inbox"
cp "$ROOT/_templates/profile.md"     "$d/patients/szttemplate/profile.md"
cp "$ROOT/_templates/medications.md" "$d/patients/szttemplate/medications.md"
cp "$ROOT/_templates/person/med/handouts/INDEX.md" "$d/patients/szttemplate/med/handouts/INDEX.md"
assert_pass "$d" "template-scaffolded person passes green (template↔guard drift)"

# L4 (warns) — an unvetted Candidate id cited in a clinician handout. The draft sits in its encounter dir
# (depth 3), which is green on its own, so the WARN is the finding.
L4_DRAFT="patients/sztgamma/med/handouts/clinician/2026-07-06-x/2026-07-06__handout-clinician__x.md"
mk_l4v(){ # $1=full index.md content  $2=handout citation line -> dir
  local d; d="$(mk)"; valid_profile "$d/patients/sztgamma/profile.md"
  mkdir -p "$d/reference-library" "$(dirname "$d/$L4_DRAFT")"
  printf '%s\n' "$1" > "$d/reference-library/index.md"
  printf 'id: TAB-AAA-0015\ndate: 2026-07-06\nlang: pl\nfactcheck: required\n\n# Karta\n\n%s\n' "$2" > "$d/$L4_DRAFT"
  echo "$d"; }
SYNVET='## Vetted — synthetic topic
- Synthetic Author, et al. A synthetic paper. *Synth J.* 2026. PMID 55555555 · DOI 10.5555/synthetic.vetted.
  *Systematic review.*

## Candidates — PENDING VERIFICATION
- Synthetic pending candidate. PMID 66666666. *Verify.*'
assert_warn "$(mk_l4v "$SYNVET" 'Evidence: PMID 66666666 supports the synthetic claim (the pending Candidate).')" \
  L4 "" "" "unvetted Candidate citation in a clinician handout"
assert_quiet "$(mk_l4v "$SYNVET" 'Evidence: PMID 55555555 supports the synthetic claim (correctly Vetted).')" \
  L4 "L4 clean synthetic corpus: a genuinely Vetted citation passes"
# extra: the Vetted DOI closed by an autolink's ">", a backtick or a quote resolves; an
# uncatalogued DOI in the same position still warns, named without the closing character.
A11D="10.5555/synthetic.vetted"
assert_quiet "$(mk_l4v "$SYNVET" "$(printf 'Evidence: <https://doi.org/%s>, `%s`, "%s" and '\''%s'\''.' "$A11D" "$A11D" "$A11D" "$A11D")")" \
  L4 "L4: a Vetted DOI closed by an autolink >, a backtick or a quote resolves"
assert_warn "$(mk_l4v "$SYNVET" 'Evidence: <https://doi.org/10.5555/synthetic.invented>.')" \
  L4 "citation '10.5555/synthetic.invented' in" "" "L4: an uncatalogued DOI in an autolink still warns, named without the >"
# extra: decimal prose such as 10.5/day is a quantity, not a DOI. Since 2026-11-01 L4 checks
# well-formed ids only; a label with no clean id is the fact-check's to catch. A citation-shaped label
# with no clean id beside an uncatalogued one: the uncatalogued id still warns.
assert_quiet "$(mk_l4v "$SYNVET" 'Dose 10.5/day, then 10.25/day; evidence PMID 55555555.')" \
  L4 "L4: decimal prose (10.5/day) is not read as a broken DOI"
assert_warn "$(mk_l4v "$SYNVET" 'Evidence: PMID: (missing); DOI 10.5555/synthetic.invented.')" \
  L4 "citation '10.5555/synthetic.invented' in" "" "L4: beside a label with no clean id, an uncatalogued DOI still warns"

# L5 — one person's handle written into another person's record
d="$(mk)"; valid_profile "$d/patients/sztalpha/profile.md"; valid_profile "$d/patients/sztbeta/profile.md"
printf '\nNote: see sztbeta.\n' >> "$d/patients/sztalpha/profile.md"
assert_fail "$d" L5 "cross-person reference"
# control (the real false red, ADR-0028): another handle as a third-party name inside an immutable scan
# transcript stays green
d="$(mk)"; valid_profile "$d/patients/sztalpha/profile.md"; valid_profile "$d/patients/sztbeta/profile.md"
mkdir -p "$d/patients/sztalpha/med/sources/labs"
printf 'primary scan bytes (fixture)\n' > "$d/patients/sztalpha/med/sources/labs/2026-01-01__lab__example.pdf"
printf 'Lekarz: sztbeta Example (third-party name inside an immutable scan transcript)\n' \
  > "$d/patients/sztalpha/med/sources/labs/2026-01-01__lab__example.ocr.md"
mk_ownership "$d"
assert_pass "$d" "L5 evidence-layer exemption: other handle as third-party name in med/sources/ stays green (ADR-0028)"
# extra: the shared reference library is read in every person's session, so a handle there reds;
# _shared/, the roster and a longer word stay green
d="$(mk)"; valid_profile "$d/patients/sztalpha/profile.md"; valid_profile "$d/patients/sztbeta/profile.md"
mkdir -p "$d/reference-library"
printf '## Candidates — PENDING VERIFICATION\n- Synthetic candidate (relevant to sztbeta).\n' > "$d/reference-library/index.md"
assert_fail "$d" L5 "L5 reds a person's handle in the shared reference library"
d="$(mk)"; valid_profile "$d/patients/sztalpha/profile.md"; valid_profile "$d/patients/sztbeta/profile.md"
mkdir -p "$d/reference-library" "$d/_shared/med"
printf '## Candidates — PENDING VERIFICATION\n- Synthetic candidate (see sztbetaxyz, not a handle).\n' > "$d/reference-library/index.md"
printf '# Roster\n- sztalpha\n- sztbeta\n' > "$d/patients/README.md"
printf '# Joint note\nA household fact for sztalpha and sztbeta, at pointer level.\n' > "$d/_shared/med/joint.md"
assert_pass "$d" "L5 leaves _shared/, the roster and a longer word in the library green"

# L6 (warns) — a mis-named scan only WARNS: a naming slip must not block care. The extra is the locator
# rule: a scan saved under the identifier itself must not print it for a private-mode person.
l6_fx(){ # -> a person with one mis-named scan, inventoried so L13 is quiet
  local d; d="$(mk)"; valid_profile "$d/patients/sztloc/profile.md"
  mkdir -p "$d/patients/sztloc/med/sources"; printf 'x\n' > "$d/patients/sztloc/med/sources/scanner-default-name.pdf"
  echo "$d"; }
d="$(l6_fx)"; mk_ownership "$d"
assert_warn "$d" L6 "patients/sztloc/med/sources/scanner-default-name.pdf" "" "undated source filename warns, never reds"
d="$(mk)"; valid_profile "$d/patients/sztcruft/profile.md"
mkdir -p "$d/patients/sztcruft/med/sources/other"
printf 'x\n' > "$d/patients/sztcruft/med/sources/other/2026-01-01__lab__x.pdf"; : > "$d/patients/sztcruft/med/sources/other/.DS_Store"
mk_ownership "$d"
assert_quiet "$d" L6 "L6 stays quiet on a conforming source name and ignores .DS_Store cruft"
d="$(l6_fx)"; pm_mark "$d/patients/sztloc/profile.md"; mk_ownership "$d"
assert_warn "$d" L6 "$LOC_PRIV" "scanner-default-name" "L6 warning withholds a private-mode person's mis-named source"

# L7 — the moving-date incident (ADR-0025): a doc that adopts the open-items table but restates a FUTURE
# date in the live body. Far-future date, so the case is clock-stable. mk_l7ok = the correct shape.
mk_l7ok(){ # -> dir with a CORRECT open-items table under patients/sztl7/profile.md
  local d; d="$(mk)"; mkdir -p "$d/patients/sztl7"
  cat > "$d/patients/sztl7/profile.md" <<'EOF'
# Profile — t
_synthetic; a correct open-items table._

## Active conditions
| Condition (PL) | Status | Evidence |
|---|---|---|
| example a | stable | analysis |
| example b | booked — see the open items | analysis |

## Current status
A correct shape: a future date lives only in the open-items table; the body
refers to the item in words. Padding to clear the L1 minimum-length floor.
One more padding line to stay above the L1 minimum-length floor.
A last padding line, so the floor holds with a margin.

## Next steps
- Planned: procedure b — booked; see its row in the open-items table.
- Recommended: nothing (fixture).

## Open items
<!-- OPEN-ITEMS:BEGIN -->
| what | who | by when | state |
|------|-----|---------|-------|
| procedure b (example) | example clinic | 2099-07-14 | booked |
<!-- OPEN-ITEMS:END -->

## Change log
- created (synthetic L7 fixture)
- padded to clear the L1 min-length floor
EOF
  echo "$d"; }
d="$(mk_l7ok)"; sed -e 's/example a | stable/example a | re-test; the 2099-07-14 slot covers this/' \
  "$d/patients/sztl7/profile.md" > "$d/patients/sztl7/profile.tmp" && mv "$d/patients/sztl7/profile.tmp" "$d/patients/sztl7/profile.md"
assert_fail "$d" L7 "open-items table adopted but a future date restated in the body (the incident)"
d="$(mk_l7ok)"; printf -- '- historical event 2001-03-18 stated as fact (past — L7 must ignore it)\n' >> "$d/patients/sztl7/profile.md"
assert_pass "$d" "L7 passes a correct open-items table (the future date only in it; a past date in the body ignored)"
# L7's today is the later of the UTC and local dates: east of UTC, the operator's own today in the body is
# not future. A stub `date` fixes both answers (UTC one day behind local) and hands every other call to
# the real one, so the case is clock-stable; a date past local today still fires.
L7STUB="$(mktemp -d)"; L7REAL="$(command -v date)"
printf '#!/bin/sh\ncase "$*" in\n  "-u +%%F") echo 2098-05-01 ;;\n  "+%%F") echo 2098-05-02 ;;\n  *) exec "%s" "$@" ;;\nesac\n' "$L7REAL" > "$L7STUB/date"
chmod +x "$L7STUB/date"
l7_body(){ # fixture-dir line -> the line inserted into the live body, just above the change log
  awk -v l="$2" '/^## Change log/{print l; print ""} {print}' "$1/patients/sztl7/profile.md" > "$1/patients/sztl7/profile.tmp" \
    && mv "$1/patients/sztl7/profile.tmp" "$1/patients/sztl7/profile.md"; }
d="$(mk_l7ok)"; l7_body "$d" '- reviewed 2098-05-02 (the local today, a day ahead of UTC)'
PATH="$L7STUB:$PATH" assert_pass "$d" "L7 passes the local today in the body when local is a day ahead of UTC"
d="$(mk_l7ok)"; l7_body "$d" '- planned 2098-05-03 (past the local today)'
PATH="$L7STUB:$PATH" assert_fail "$d" L7 "L7 still fires on a date past the local today"
rm -rf "$L7STUB"

# L8 — a handout file that breaks the canonical name (the pre-ADR-0026 drift class)
d="$(mk)"; valid_profile "$d/patients/sztgamma/profile.md"
mkdir -p "$d/patients/sztgamma/med/handouts/patient"
echo x > "$d/patients/sztgamma/med/handouts/patient/2026-06-22__notes.md"
assert_fail "$d" L8 "non-canonical handout filename"
# control: INDEX.md/README.md are ignored and a conforming handout passes as .md and .pdf
d="$(mk)"; valid_profile "$d/patients/sztgamma/profile.md"
mkdir -p "$d/patients/sztgamma/med/handouts/clinician/archive"
echo x > "$d/patients/sztgamma/med/handouts/INDEX.md"
echo x > "$d/patients/sztgamma/med/handouts/clinician/archive/README.md"
echo x > "$d/patients/sztgamma/med/handouts/clinician/2026-06-08__handout-clinician__example.md"
echo x > "$d/patients/sztgamma/med/handouts/clinician/2026-06-08__handout-clinician__example.pdf"
mk_pass_sidecar "$d/patients/sztgamma/med/handouts/clinician/2026-06-08__handout-clinician__example.md"
mk_legacy_freeze "$d" sztgamma
assert_pass "$d" "L8 ignores INDEX/README and passes a conforming handout (.md + .pdf)"

# L10 — private-mode identifier residue (ADR-0029): a contiguous 11-digit run in a marked person's text
# layer. SYNTHETIC token only (the textbook check number); the guard reports file:line, never the run.
pm_profile(){ # path -> a VALID profile carrying the ⟨never-API⟩ private-mode marker
  valid_profile "$1"
  printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩, not recorded.\n' >> "$1"; }
L10TOK="44051401359"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/analysis"
printf 'Working note: %s stray token (synthetic fixture).\n' "$L10TOK" > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
assert_fail "$d" L10 "private-mode residue: 11-digit run in an analysis file"
# control (the real false red, about 1 in 9 digests): digits inside a 64-hex integrity digest are not residue
L10HEX="abcdef${L10TOK}abcdef0123456789abcdef0123456789abcdef012345678"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/analysis"
printf 'handout_sha256: %s\nverdict: PASS\n' "$L10HEX" > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
assert_pass "$d" "L10: digits inside a 64-hex digest are not identifier residue"
# L10's read-guard notice: a person in private mode, or holding masked output, in a tree whose settings do not
# name the read-guard hook is a WARN (never red), by category only; the hook wired, or nobody in private mode, is quiet
RGHOOK='{"hooks":{"PreToolUse":[{"matcher":"Read","hooks":[{"type":"command","command":"python3 \"$CLAUDE_PROJECT_DIR/tools/claude-hooks/registry-read-guard.py\""}]}]}}'
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
assert_warn "$d" L10 'session read-guard is not wired' 'sztpm' "L10: a private-mode person and no read-guard settings warns, naming no one"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"; mkdir -p "$d/.claude"; printf '{"hooks":{}}\n' > "$d/.claude/settings.local.json"
assert_warn "$d" L10 'session read-guard is not wired' '' "L10: settings that name no read-guard hook warn"
d="$(mk)"; valid_profile "$d/patients/sztpm/profile.md"; mkdir -p "$d/patients/sztpm/_redacted/doc-abcdefabcdefabcd"
assert_warn "$d" L10 'session read-guard is not wired' '' "L10: a person holding masked output, with no marker, and no read-guard settings warns"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"; mkdir -p "$d/.claude"; printf '%s\n' "$RGHOOK" > "$d/.claude/settings.local.json"
assert_quiet "$d" L10 "L10: the read-guard hook wired in settings is quiet (control)"
d="$(mk)"; valid_profile "$d/patients/sztpm/profile.md"
assert_quiet "$d" L10 "L10: nobody in private mode, no read-guard settings, is quiet (control)"
# L10 extras: every text file a model may read is scanned, not only Markdown …
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/analysis"
printf 'exported table, synthetic: %s\n' "$L10TOK" > "$d/patients/sztpm/med/analysis/2026-01-01__export.txt"
assert_fail "$d" L10 "private-mode residue: 11-digit run in a non-Markdown text file"
# … control: an original in the intake tray (the read guard keeps it from a model), a binary and the
# redaction tool's opaque document id are not residue
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/_inbox" "$d/patients/sztpm/med/analysis" "$d/patients/sztpm/_redacted/doc-abcdefabcdefabcd"
printf 'original letter, synthetic: %s\n' "$L10TOK" > "$d/patients/sztpm/med/_inbox/letter.txt"
printf 'BIN\000%s\000\n' "$L10TOK" > "$d/patients/sztpm/med/analysis/2026-01-01__chart.png"
printf '{"doc": "doc-0%s0123"}\n' "$L10TOK" > "$d/patients/sztpm/_redacted/doc-abcdefabcdefabcd/manifest.json"
assert_pass "$d" "L10: intake-tray originals, binaries and opaque document ids are not residue"
# … and the joint non-medical lane's Markdown while any person is private-mode
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/_shared/nmed"
printf 'joint note, synthetic: %s\n' "$L10TOK" > "$d/_shared/nmed/2026-01-01__note.md"
assert_fail "$d" L10 "private-mode residue: 11-digit run in _shared/nmed prose"
# … control: with no private-mode person, or with the dated waiver, the same note is green
d="$(mk)"; valid_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/_shared/nmed"
printf 'joint note, synthetic: %s\n' "$L10TOK" > "$d/_shared/nmed/2026-01-01__note.md"
printf 'waived, synthetic: %s ⟨not-an-id: verified 2026-01-01⟩\n' "$L10TOK" > "$d/_shared/nmed/2026-01-02__note.md"
assert_pass "$d" "L10: _shared/nmed prose is out of scope without a private-mode person"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/_shared/nmed"
printf 'waived, synthetic: %s ⟨not-an-id: verified 2026-01-01⟩\n' "$L10TOK" > "$d/_shared/nmed/2026-01-02__note.md"
printf 'joint letter original, synthetic: %s\n' "$L10TOK" > "$d/_shared/nmed/2026-01-03__letter.txt"
assert_pass "$d" "L10: a waived _shared/nmed line and a non-Markdown original there stay green"
# … names fold the way the read guard folds them, and only the ownership ledger's own files are left out
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/_inbox"
printf 'note, synthetic: %s\n' "$L10TOK" > "$d/patients/sztpm/med/_inbox/note.MD"
assert_fail "$d" L10 "private-mode residue: an upper-case .MD file in the intake tray (a model may read it)"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/_inbox/_REDACTED/doc"
printf '{"note": "synthetic %s"}\n' "$L10TOK" > "$d/patients/sztpm/med/_inbox/_REDACTED/doc/meta.json"
assert_fail "$d" L10 "private-mode residue: a file under an upper-case _REDACTED folder"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med"
printf 'synthetic: %s\n' "$L10TOK" > "$d/patients/sztpm/med/MANIFEST.md"
assert_fail "$d" L10 "private-mode residue: a MANIFEST.md beside the ownership ledger is not the ledger"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med"
printf 'synthetic: %s\n' "$L10TOK" > "$d/patients/sztpm/med/MANIFEST.lock"
assert_pass "$d" "L10: the ownership ledger's own files are left to L13"
# … and a listing it cannot complete is blinded, never clean (the suite runs unprivileged: as root, chmod 000 hides nothing)
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/analysis/locked"; chmod 000 "$d/patients/sztpm/med/analysis/locked"
assert_fail "$d" L10 "L10: a private-mode tree it cannot list fails closed"
d="$(mk)"; pm_profile "$d/patients/sztpm/profile.md"
mkdir -p "$d/_shared/nmed/locked"; chmod 000 "$d/_shared/nmed/locked"
assert_fail "$d" L10 "L10: a _shared/nmed it cannot list fails closed"
# extra: the profile template names the marker in words, so a person scaffolded from it and
# left unedited is out of private-mode scope; the same scaffold with its private-mode line filled in is in.
c4_fx(){ # $1 = a private-mode line written over the template's placeholder, or '' to leave it -> dir
  local d p; d="$(mk)"; p="$d/patients/sztc4/profile.md"; mkdir -p "$d/patients/sztc4/med/analysis"
  cp "$ROOT/_templates/profile.md" "$p"
  if [ -n "$1" ]; then
    awk -v line="$1" '/^- Private mode \(experimental/ { print line; next } { print }' "$p" > "$p.tmp" && mv "$p.tmp" "$p"
  fi
  printf 'Working note: %s stray token (synthetic fixture).\n' "$L10TOK" > "$d/patients/sztc4/med/analysis/2026-01-01__note.md"
  echo "$d"; }
assert_pass "$(c4_fx '')" "L10: a person scaffolded from the unedited profile template is out of private-mode scope"
assert_fail "$(c4_fx '- Private mode (experimental, ADR-0029): synthetic identifier class ⟨never-API⟩ — operator decision 2026-01-01')" \
  L10 "L10: the same scaffold with the marker on its private-mode line is in scope"
# L10 reads each person's shape from the number list their tag names (ADR-0062), through the Python reader
# tools/private-mode/id_schemes.py (ADR-0073; ADR-0077: only the exact tag decides, no tag searches every row). Its rules, the list's own
# validation and its union are bitten in tools/private-mode/test_identity.py; here, a selection and each
# kind of refusal reaching the board with its own message, and the union the board searches below.
tag_fx(){ # $1 = the private-mode line's tail after the marker, $2 = extra profile line or '', $3 = note -> dir
  local d p; d="$(mk)"; p="$d/patients/sztpm/profile.md"; valid_profile "$p"
  printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩%s\n' "$1" >> "$p"
  [ -z "$2" ] || printf '%s\n' "$2" >> "$p"
  mkdir -p "$d/patients/sztpm/med/analysis"
  printf 'Working note: %s (synthetic fixture).\n' "$3" > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
  echo "$d"; }
l10_says(){ # dir · the start of the L10 message the board must print · label
  local out; out="$(bash "$CHECK" "$1" 2>&1)"; rm -rf "$1"
  if grep -qF "FAIL [L10] $2" <<<"$out"; then echo "BITE  OK  ($3)"; pass=$((pass+1))
  else echo "BITE  MISS ($3)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi; }
L10KEY="$(awk -F'\t' '!/^#/ && NF { print $1; exit }' "$ROOT/tools/private-mode/id-schemes.tsv")"
L10_RES='identifier-shaped residue'
l10_says "$(tag_fx " ⟨id-scheme ${L10KEY}⟩" '' "$L10TOK")" "$L10_RES" "L10: a named scheme reds its residue shape"
assert_pass "$(tag_fx " ⟨id-scheme ${L10KEY}⟩" '' 'nothing shaped like a number')" "L10: a named scheme with clean notes stays green"
l10_says "$(tag_fx ' ⟨id-scheme zz-none⟩' '' 'clean')" "the private-mode number tag in one profile names a scheme the number list does not know" "L10: a tag naming an unknown scheme reds"
l10_says "$(tag_fx " ⟨id-scheme ${L10KEY}⟩ ⟨id-scheme ${L10KEY}⟩" '' 'clean')" "the private-mode number tag appears more than once" "L10: a repeated tag reds"
l10_says "$(tag_fx " ⟨id scheme ${L10KEY}⟩" '' 'clean')" "the private-mode number tag is malformed" "L10: a mistyped tag on the marker line reds"
l10_says "$(tag_fx " ⟨id – scheme ${L10KEY}⟩" '' 'clean')" "the private-mode number tag is malformed" "L10: a tag joined by a spaced dash reds"
l10_says "$(tag_fx " ⟨id-sceme ${L10KEY}⟩" '' 'clean')" "the private-mode number tag is malformed" "L10: a key of the list outside the exact tag reds"
id_fx(){ # $1 = line after the marker line in an Identity section, $2 = note -> dir
  local d p; d="$(mk)"; p="$d/patients/sztpm/profile.md"; valid_profile "$p"
  printf -- '\n## Identity & basics\n- Private mode (synthetic): the designated identifier is ⟨never-API⟩\n%s\n' "$1" >> "$p"
  mkdir -p "$d/patients/sztpm/med/analysis"
  printf 'Working note: %s (synthetic fixture).\n' "$2" > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
  echo "$d"; }
l10_says "$(id_fx "  ⟨id-scheme ${L10KEY}⟩" 'clean')" "the private-mode number tag is in one profile's Identity section" "L10: a tag wrapped off the marker line in the Identity section reds"
assert_pass "$(tag_fx ' ⟨id-scheme unlisted⟩ — synthetic country' '' "$L10TOK")" "L10: a number not on the list (the key unlisted) is searched with no shape"
l10_says "$(tag_fx " ⟨id-scheme ${L10KEY},unlisted⟩" '' "$L10TOK")" "$L10_RES" "L10: beside the key unlisted, a listed scheme is still searched"
l10_says "$(tag_fx ' — number not on the list (synthetic country)' '' "$L10TOK")" "$L10_RES" "L10: the words \"number not on the list\" never narrow the search (ADR-0077)"
l10_says "$(tag_fx ' — number not on the list; ⟨id-' "scheme ${L10KEY}⟩" "$L10TOK")" "$L10_RES" "L10: a tag cut over two lines beside those words still searches every row"
# The shipped second row (the US number, separated forms only; 987-65-432N is never a person's number):
# its tag reds it, a Polish tag narrows the search away from it, and no tag searches it too (ADR-0077)
L10US='987-65-4321'
l10_says "$(tag_fx ' ⟨id-scheme us-ssn⟩' '' "$L10US")" "$L10_RES" "L10: the US row reds its separated form"
l10_says "$(tag_fx ' ⟨id-scheme us-ssn⟩' '' "987 – 65 – 4321")" "$L10_RES" "L10: the US row reds a spaced dash form"
assert_pass "$(tag_fx ' ⟨id-scheme us-ssn⟩' '' '987654321, 555-123-4567 and 2026-11-11')" "L10: the US row leaves a bare run, a phone and a date alone"
assert_pass "$(tag_fx " ⟨id-scheme ${L10KEY}⟩" '' "$L10US")" "L10: a Polish tag does not search the US row"
l10_says "$(tag_fx '' '' "$L10US")" "$L10_RES" "L10: no tag searches the US row too"
# A byte that is not UTF-8 must not make a parser print the line, nor lose the tag or the hit. These run
# under a UTF-8 locale, where the parser fails; both output streams are searched for the number.
L10_UTF8="$(locale -a 2>/dev/null | grep -iE '^(en_US|C)\.utf-?8$' | head -n 1)"
L10_BAD="$(printf 'caf\351')"
# The search itself reads bytes: under a UTF-8 locale, grep can miss a number after such a byte, which is
# exactly what a leak looks like. The control below proves a leak counts as shown under this suite's locale.
bad_byte_shown(){ LC_ALL=C grep -aqF "$L10TOK" <<<"$1"; }
if bad_byte_shown "$(printf "awk: towc: multibyte conversion failure on: '\351 after=%s'" "$L10TOK")"; then
  echo "BITE  OK  (byte not UTF-8: a number printed after such a byte counts as shown)"; pass=$((pass+1))
else echo "BITE  MISS (byte not UTF-8: a number printed after such a byte did not count as shown)"; fail=$((fail+1)); fi
bad_byte_case(){ # guard dir yes|no label — run under UTF-8: must the guard fire? the number must never show
  local out got=no shown=no; out="$(LC_ALL="${L10_UTF8:-C}" bash "$CHECK" "$2" 2>&1)"; rm -rf "$2"
  LC_ALL=C grep -aq "FAIL \\[$1\\]" <<<"$out" && got=yes
  bad_byte_shown "$out" && shown=yes
  if [ "$got" = "$3" ] && [ "$shown" = no ]; then echo "BITE  OK  ($1, byte not UTF-8: $4)"; pass=$((pass+1))
  else echo "BITE  MISS ($1, byte not UTF-8: $4 — expected $1 fired=$3, got fired=$got, number shown=$shown)"; fail=$((fail+1)); fi
}
[ -n "$L10_UTF8" ] || echo "NOTE (L10, byte not UTF-8: no UTF-8 locale on this machine, so these ran under C)"
bad_byte_case L10 "$(tag_fx " ⟨id-scheme ${L10KEY}⟩ $L10_BAD number=$L10TOK" '' 'clean')" yes "a number after it on the tag's line reds and is not printed"
# A number beside such a byte reds in every kind of file the scan reads, wherever it stands on the line;
# the number must never show.
residue_fx(){ # kind of file, its text -> dir with a private-mode person
  local d m; d="$(tag_fx '' '' 'clean')"; m="$d/patients/sztpm"
  case "$1" in
    profile) printf '%s\n' "$2" >> "$m/profile.md" ;;
    medications) printf '%s\n' "$2" > "$m/medications.md" ;;
    note) printf '%s\n' "$2" > "$m/med/analysis/2026-01-01__note.md" ;;
    shared) mkdir -p "$d/_shared/nmed"; printf '%s\n' "$2" > "$d/_shared/nmed/2026-01-01__note.md" ;;
  esac
  echo "$d"; }
for k in profile medications note shared; do
  bad_byte_case L10 "$(residue_fx "$k" "$L10_BAD after=$L10TOK")" yes "a number after it reds, in a $k file"
done
bad_byte_case L10 "$(residue_fx note "$L10TOK before $L10_BAD")" yes "a number before it reds"
bad_byte_case L10 "$(residue_fx note "$L10TOK $L10_BAD after=$L10TOK")" yes "a number on both sides of it reds"
bad_byte_case L10 "$(residue_fx note "$(printf '%s\nnext line %s' "$L10_BAD" "$L10TOK")")" yes "a number on the line after it reds"
bad_byte_case L10 "$(residue_fx note "$L10_BAD after=$L10TOK ⟨not-an-id: verified 2026-01-01⟩")" no "a waived number after it stays green"
d="$(tag_fx '' '' 'clean')"; printf 'a\000b %s after=%s\n' "$L10_BAD" "$L10TOK" > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
bad_byte_case L10 "$d" no "a file with a NUL byte stays out of the scan"
d="$(mk)"; valid_profile "$d/patients/sztpub/profile.md"; mkdir -p "$d/patients/sztpub/med/analysis"
printf '%s after=%s\n' "$L10_BAD" "$L10TOK" > "$d/patients/sztpub/med/analysis/2026-01-01__note.md"
bad_byte_case L10 "$d" no "a person without the marker stays out of the scan"
# The marker reads the same after such a byte and after a NUL, wherever it is searched: scope, the
# locator, a tree with no profile, and a kept-detail placeholder.
hidden_mark(){ printf -- '- %s %s\n' "$L10_BAD" "$1" >> "$2"; } # text, file
scoped_fx(){ local d; d="$(mk)"; valid_profile "$d/patients/sztpm/profile.md"
  mkdir -p "$d/patients/sztpm/med/analysis"; printf 'note %s\n' "$L10TOK" > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
  echo "$d"; }
d="$(scoped_fx)"; hidden_mark '⟨never-API⟩' "$d/patients/sztpm/profile.md"
bad_byte_case L10 "$d" yes "the marker after it still brings the person in scope"
d="$(scoped_fx)"; printf -- '- \000 ⟨never-API⟩\n' >> "$d/patients/sztpm/profile.md"
bad_byte_case L10 "$d" yes "the marker after a NUL byte still brings the person in scope"
d="$(mk)"; valid_profile "$d/patients/sztpm/profile.md"; hidden_mark '⟨never-API⟩' "$d/patients/sztpm/profile.md"
mkdir -p "$d/patients/sztpm/med/handouts"; : > "$d/patients/sztpm/med/handouts/$L10TOK.md"
bad_byte_case L8 "$d" yes "the marker after it still withholds a file's name"
d="$(mk)"; mkdir -p "$d/patients/sztpm/med/analysis"; hidden_mark '⟨never-API⟩' "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
bad_byte_case L10 "$d" yes "the marker after it still reds a tree with no profile"
d="$(mk)"; valid_profile "$d/patients/sztpm/profile.md"; hidden_mark '⟨withheld:patient-name⟩ ⟨never-API⟩' "$d/patients/sztpm/profile.md"
bad_byte_case L10 "$d" yes "a placeholder after it still wakes the kept-details scan"
# The open-items lint reads the whole of a profile with a block, so the byte goes on every kind of line of a
# private-mode profile: never printed, no false red, and a future date after it is still seen.
l7_bad_fx(){ # the line to add it after, the line to add (default: byte + number) -> dir
  local d p; d="$(mk_l7ok)"; p="$d/patients/sztl7/profile.md"
  LC_ALL=C awk -v a="$1" -v t="${2:-$L10_BAD after=$L10TOK}" '{ print } $0 == a { print t }' "$p" > "$p.tmp" && mv "$p.tmp" "$p"
  printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩\n' >> "$p"
  echo "$d"; }
bad_byte_case L7 "$(l7_bad_fx '# Profile — t')" no "under the title"
bad_byte_case L7 "$(l7_bad_fx '## Current status')" no "in the body before the block"
bad_byte_case L7 "$(l7_bad_fx '|------|-----|---------|-------|')" no "as a line in the block"
bad_byte_case L7 "$(l7_bad_fx '<!-- OPEN-ITEMS:END -->')" no "right after the block"
bad_byte_case L7 "$(l7_bad_fx '## Change log')" no "in the change log"
d="$(l7_bad_fx 'no such line')"; p="$d/patients/sztl7/profile.md"; LC_ALL=C sed "s/^| what |/| what $L10_BAD after=$L10TOK |/" "$p" > "$p.tmp" && mv "$p.tmp" "$p"
bad_byte_case L7 "$d" no "in the block's header"
bad_byte_case L7 "$(l7_bad_fx '## Next steps' "$L10_BAD after=$L10TOK re-test 2099-07-14")" yes "a future date after it in the body still reds"
# L5 reads a line the locale cannot decode as bytes, and keeps the locale's word boundaries on every other line.
l5_bad_fx(){ # file under the fixture, line to write -> dir, two people
  local d; d="$(mk)"; valid_profile "$d/patients/sztalpha/profile.md"; valid_profile "$d/patients/sztbeta/profile.md"
  mkdir -p "$(dirname "$d/$1")"; printf '%s\n' "$2" >> "$d/$1"; echo "$d"; }
L5_NOTE=patients/sztalpha/med/analysis/note.md
bad_byte_case L5 "$(l5_bad_fx "$L5_NOTE" "$L10_BAD then sztbeta here")" yes "a handle after it in a person's note reds"
bad_byte_case L5 "$(l5_bad_fx "$L5_NOTE" "$L10_BAD then SZTBETA here")" yes "a capitalised handle after it in a note reds"
bad_byte_case L5 "$(l5_bad_fx reference-library/index.md "$L10_BAD then sztbeta here")" yes "a handle after it in the library reds"
bad_byte_case L5 "$(l5_bad_fx reference-library/index.md "$L10_BAD then SZTBETA here")" no "a capitalised handle after it in the library stays green"
d="$(l5_bad_fx patients/sztalpha/med/sources/labs/2026-01-01__lab__example.ocr.md "Lekarz $L10_BAD sztbeta")"
printf 'primary scan bytes (fixture)\n' > "$d/patients/sztalpha/med/sources/labs/2026-01-01__lab__example.pdf"; mk_ownership "$d"
bad_byte_case L5 "$d" no "a handle after it in med/sources stays green"
d="$(l5_bad_fx "$L5_NOTE" 'plain line')"; printf 'a\000b\n%s then sztbeta here\n' "$L10_BAD" >> "$d/$L5_NOTE"
bad_byte_case L5 "$d" yes "a handle after it in a file with a NUL byte reds"
L5_SRC=patients/sztalpha/med/sources/labs/2026-01-01__lab__example
d="$(l5_bad_fx "$L5_SRC.ocr.md" 'plain line')"; printf 'a\000b\nLekarz sztbeta\nLekarz %s sztbeta\n' "$L10_BAD" >> "$d/$L5_SRC.ocr.md"
printf 'primary scan bytes (fixture)\n' > "$d/$L5_SRC.pdf"; mk_ownership "$d"
bad_byte_case L5 "$d" no "the same file in med/sources stays green"
if [ -n "$L10_UTF8" ]; then
  bad_byte_case L5 "$(l5_bad_fx "$L5_NOTE" "$(printf 'sztbeta\303\263w and \305\274sztbeta')")" no "a handle inside a longer word in valid text stays green"
fi
d="$(l5_bad_fx patients/sztalpha/profile.md "sztbeta $L10_BAD id=$L10TOK")"; pm_mark "$d/patients/sztalpha/profile.md"
out="$(LC_ALL="${L10_UTF8:-C}" bash "$CHECK" "$d" 2>&1)"; rm -rf "$d"
if LC_ALL=C grep -aq 'FAIL \[L5\].* in 1 line(s)' <<<"$out" && ! bad_byte_shown "$out"; then
  echo "BITE  OK  (L5, byte not UTF-8: a private-mode hit before it counts once)"; pass=$((pass+1))
else echo "BITE  MISS (L5, byte not UTF-8: a private-mode hit before it counts once)"; LC_ALL=C grep -a 'L5' <<<"$out" | LC_ALL=C sed 's/^/      /'; fail=$((fail+1)); fi
sr="$(mktemp -d)"; L5_GREP="$(command -v grep)"
printf '#!/bin/bash\ncase "$LC_ALL:$1" in C:-rn*) exit 2;; esac\nexec "%s" "$@"\n' "$L5_GREP" > "$sr/grep"; chmod +x "$sr/grep"
d="$(l5_bad_fx patients/sztalpha/med/analysis/note.md 'nothing to find')"; out="$(PATH="$sr:$PATH" LC_ALL="${L10_UTF8:-en_US.UTF-8}" bash "$CHECK" "$d" 2>&1)"; rm -rf "$d" "$sr"
if LC_ALL=C grep -aq 'FAIL \[L5\] grep failed' <<<"$out"; then
  echo "BITE  OK  (L5, byte not UTF-8: a failed byte search reds)"; pass=$((pass+1))
else echo "BITE  MISS (L5, byte not UTF-8: a failed byte search reds)"; LC_ALL=C grep -a 'L5' <<<"$out" | LC_ALL=C sed 's/^/      /'; fail=$((fail+1)); fi
# … and a number list it cannot read blinds L10 for a private-mode person: a copy of this check.sh beside
# a list with a three-field row (check.sh reads the list from its own repo, so the copy carries one)
sr="$(mktemp -d)"; mkdir -p "$sr/checks" "$sr/tools/private-mode"
cp "$ROOT/checks/check.sh" "$sr/checks/"; cp -R "$ROOT/tools/person_ownership" "$sr/tools/"
cp "$ROOT/tools/private-mode/id_schemes.py" "$sr/tools/private-mode/"
printf 'pl-id\tpol\tonly three fields\n' > "$sr/tools/private-mode/id-schemes.tsv"
d="$(tag_fx '' '' 'clean')"; out="$(bash "$sr/checks/check.sh" "$d" 2>&1)"; rc=$?; rm -rf "$d" "$sr"
if [ "$rc" -ne 0 ] && grep -qF "FAIL [L10] the private-mode number list is missing, malformed or unreadable" <<<"$out"; then
  echo "BITE  OK  (L10: a malformed number list blinds L10 for a private-mode person)"; pass=$((pass+1))
else echo "BITE  MISS (L10: a malformed number list did not red L10), rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
# … the union the board searches: a copy of this check.sh beside a three-row list — several schemes for one person, an
# anchored shape, and a joint note against every private-mode person's shapes
sr="$(mktemp -d)"; mkdir -p "$sr/checks" "$sr/tools/private-mode"
cp "$ROOT/checks/check.sh" "$sr/checks/"; cp -R "$ROOT/tools/person_ownership" "$sr/tools/"
cp "$ROOT/tools/private-mode/id_schemes.py" "$sr/tools/private-mode/"
{ awk -F'\t' '!/^#/ && NF { print; exit }' "$ROOT/tools/private-mode/id-schemes.tsv"
  printf 'zz-two\tpol\tX[0-9]{5}Y\tsynthetic\nzz-top\tpol\t^Q[0-9]{4}\tsynthetic\n'; } > "$sr/tools/private-mode/id-schemes.tsv"
union_case(){ # dir yes|no label — does L10 fire under the three-row list?
  local out got=no; out="$(bash "$sr/checks/check.sh" "$1" 2>&1)"; grep -q 'FAIL \[L10\]' <<<"$out" && got=yes
  if [ "$got" = "$2" ]; then echo "BITE  OK  (L10 union: $3)"; pass=$((pass+1))
  else echo "BITE  MISS (L10 union: $3 — expected L10 fired=$2)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
  rm -rf "$1"; }
union_case "$(tag_fx " ⟨id-scheme $L10KEY,zz-two⟩" '' 'X12345Y')" yes "a tag naming two schemes reds the second's shape"
union_case "$(tag_fx " ⟨id-scheme $L10KEY,zz-two⟩" '' "$L10TOK")" yes "a tag naming two schemes reds the first's shape"
union_case "$(tag_fx " ⟨id-scheme $L10KEY,zz-two⟩" '' 'nothing shaped like one')" no "clean notes stay free of L10"
d="$(tag_fx ' ⟨id-scheme zz-top⟩' '' 'clean')"; printf 'Q1234 starts this line.\n' > "$d/patients/sztpm/med/analysis/2026-01-02__note.md"
union_case "$d" yes "an anchored shape at the start of a line"
# a NUL byte in the profile: the board reads the tag after it as Python reads the file's bytes
d="$(tag_fx '' '' 'clean')"; printf -- '- \000 ⟨never-API⟩ ⟨id-scheme zz-two⟩\n' >> "$d/patients/sztpm/profile.md"
union_case "$d" no "a tag after a NUL byte is read (a clean note stays green)"
d="$(tag_fx '' '' 'clean')"; printf -- '- \000 ⟨never-API⟩ ⟨id-scheme zz-two⟩\n' >> "$d/patients/sztpm/profile.md"
printf 'synthetic X12345Y\n' > "$d/patients/sztpm/med/analysis/2026-01-01__note.md"
union_case "$d" yes "a tag after a NUL byte selects its scheme's shape"
union_fx(){ # $1 = joint note's text -> two private-mode people on different schemes, and the joint note
  local d; d="$(tag_fx " ⟨id-scheme ${L10KEY}⟩" '' 'clean')"; valid_profile "$d/patients/sztpn/profile.md"
  printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩ ⟨id-scheme zz-two⟩\n' >> "$d/patients/sztpn/profile.md"
  mkdir -p "$d/patients/sztpn/med/analysis" "$d/_shared/nmed"
  printf 'Working note: clean (synthetic fixture).\n' > "$d/patients/sztpn/med/analysis/2026-01-01__note.md"
  printf 'joint note, synthetic: %s\n' "$1" > "$d/_shared/nmed/2026-01-01__note.md"
  echo "$d"; }
union_case "$(union_fx 'X12345Y')" yes "a joint note reds one person's shape"
union_case "$(union_fx "$L10TOK")" yes "a joint note reds the other person's shape"
union_case "$(union_fx 'nothing shaped like one')" no "a clean joint note stays free of L10"
rm -rf "$sr"
# L10, kept details (control C2, ADR-0075): a kept value left in a private-mode person's working record
# reds, by category and never by value; the twin with the placeholder in its place stays green, and reds
# again once its identity file is lost. The matcher's forms and dating are bitten in
# tools/private-mode/test_identity.py.
v2_fx(){ # $1 = the name line's value -> dir with a synthetic person keeping their name and date of birth
  local d p; d="$(mk)"; p="$d/patients/sztv2/profile.md"; valid_profile "$p"
  printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩ · ⟨withheld:details-kept⟩\n' >> "$p"
  printf -- '- Name / role: %s (synthetic)\n' "$1" >> "$p"
  ( umask 077; printf '%s\n' '{"schema": "tabularium.never-api-identity", "version": 2, "classes": {"patient_names": [{"value": {"given": "Synthia", "family": "Testperson"}, "since": "2026-10-01"}], "dob": [{"value": "1901-02-23", "since": "2026-10-01"}], "other_names": [], "id_numbers": [], "addresses": [], "phones": [], "emails": [], "case_numbers": []}}' > "$d/patients/sztv2/.never-api-identity.json" )
  echo "$d"; }
d="$(v2_fx 'Synthia Testperson')"; out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?; rm -rf "$d"
if [ "$rc" -ne 0 ] && grep -qF "kept detail (the person's name) in the profile" <<<"$out" && ! grep -qF Testperson <<<"$out"; then
  echo "BITE  OK  (kept details: a kept name in the profile reds L10, value withheld)"; pass=$((pass+1))
else echo "BITE  MISS (kept details: a kept name in the profile did not red L10 by category), rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
assert_pass "$(v2_fx '⟨withheld:patient-name⟩')" "kept details: the same person with the placeholder stays green"
d="$(v2_fx '⟨withheld:patient-name⟩')"; rm -f "$d/patients/sztv2/.never-api-identity.json"
assert_fail "$d" L10 "kept details: a placeholder whose identity file is lost reds, never switches the scan off"
# A care-only install (ADR-0068): no token registry, no identifier file, no pointer to either. The
# masking tool's folder, named by a document id that holds an 11-digit run (about one in sixty), stays
# green where the tool made it and reds where only the name's shape matches; a fresh person keeping their
# name and date of birth reaches
# green through the form alone, with no typed value in anything a session runs or reads. The deep
# cases: test_ownership.py and test_identity.py.
for made in 1 0; do
  d="$(mk)"; p="$d/patients/sztcare/profile.md"; valid_profile "$p"; pm_mark "$p"
  x="$d/patients/sztcare/_redacted/doc-1234567890123456"; mkdir -p "$x"; printf x > "$x/page-01.png"
  if [ "$made" = 1 ]; then printf '{}' > "$x/manifest.json"
    assert_pass "$d" "care-only: a folder the masking tool made, named by its document id, stays green"
  else assert_fail "$d" L13 "care-only: the tool's name shape on a folder it did not make still reds"; fi
done
d="$(mk)"; p="$d/patients/sztcare/profile.md"; valid_profile "$p"
printf -- '- Private mode (synthetic): the designated identifier is ⟨never-API⟩\n- Name / role: Synthia Testperson\n' >> "$p"
IDT="$ROOT/tools/private-mode/identity.py"; f="$d/patients/sztcare/fill-in-form.never-api-identity.json"
seen="$(python3 "$IDT" --root "$d" form sztcare --keep patient_names,dob --no-open 2>&1)"; rc1=$?
sed -e 's|^name: .*|name: Synthia / Testperson|' -e 's|^date of birth: .*|date of birth: 23.02.1901|' \
    -e 's|^date of birth again: .*|date of birth again: 23.02.1901|' "$f" > "$d/filled.tmp" && cat "$d/filled.tmp" > "$f"; rm -f "$d/filled.tmp"
seen="$seen
$(python3 "$IDT" --root "$d" take-form sztcare 2>&1)"; rc2=$?
seen="$seen
$(bash "$CHECK" "$d" 2>&1)"; rc3=$?
if [ "$rc1$rc2$rc3" = 000 ] && [ ! -e "$f" ] && [ -f "$d/patients/sztcare/.never-api-identity.json" ] \
   && grep -qF 'Name / role: ⟨withheld:patient-name⟩' "$p" && grep -qF '⟨never-API⟩ · ⟨withheld:details-kept⟩' "$p" \
   && ! grep -qE 'Testperson|Synthia|1901' <<<"$seen"; then
  echo "BITE  OK  (care-only: a fresh person keeping details reaches green through the form in one step, no value printed)"; pass=$((pass+1))
else echo "BITE  MISS (care-only: the kept-details form walk, rc=$rc1/$rc2/$rc3)"; echo "$seen" | sed 's/^/      /'; fail=$((fail+1)); fi
rm -rf "$d"

# L13 — person-ownership binding (ADR-0037): these cases prove the check.sh WIRING; the deep logic is
# tools/person_ownership/test_ownership.py (run in the SUITE case below).
d="$(mk)"; valid_profile "$d/patients/sztown/profile.md"
mkdir -p "$d/patients/sztown/med/sources"; echo scan > "$d/patients/sztown/med/sources/2026-01-01__lab__x.pdf"
mk_ownership "$d"; echo TAMPERED > "$d/patients/sztown/med/sources/2026-01-01__lab__x.pdf"
assert_fail "$d" L13 "source byte drift after inventory fires L13"
d="$(mk)"; valid_profile "$d/patients/sztown/profile.md"
mkdir -p "$d/patients/sztown/med/sources"; echo scan > "$d/patients/sztown/med/sources/2026-01-01__lab__x.pdf"
mk_ownership "$d"
assert_pass "$d" "L13 green after ownership migration (valid manifest + checkpoint)"
# tools/person_ownership wiring: a crash between the MANIFEST and checkpoint writes fires L13; the same
# steps without the crash (the append writer adds a later source) stay green
d="$(mk)"; valid_profile "$d/patients/sztown/profile.md"
mkdir -p "$d/patients/sztown/med/sources"; echo scan > "$d/patients/sztown/med/sources/2026-01-01__lab__x.pdf"
mk_ownership "$d"; cp "$d/patients/sztown/med/MANIFEST.checkpoint" "$d/ckpt.bak"
echo scan2 > "$d/patients/sztown/med/sources/2026-02-02__lab__y.pdf"
mk_append "$d" sztown med/sources/2026-02-02__lab__y.pdf
cp "$d/ckpt.bak" "$d/patients/sztown/med/MANIFEST.checkpoint"; rm -f "$d/ckpt.bak"
assert_fail "$d" L13 "a crash between the MANIFEST and checkpoint writes fires L13"
d="$(mk)"; valid_profile "$d/patients/sztown/profile.md"
mkdir -p "$d/patients/sztown/med/sources"; echo scan > "$d/patients/sztown/med/sources/2026-01-01__lab__x.pdf"
mk_ownership "$d"
echo scan2 > "$d/patients/sztown/med/sources/2026-02-02__lab__y.pdf"
mk_append "$d" sztown med/sources/2026-02-02__lab__y.pdf
assert_pass "$d" "L13 green after the append writer adds a later source"

# L15 — sealed-handout byte binding (ADR-0039): the wiring; deep logic is tools/handout_attest/test_attest.py.
# mk_sealed builds one CONSISTENT sealed unit (md + PASS factcheck + output + attest, real hashes) plus its
# INDEX row; the attest schema constant comes from THE package. $3 = kind (pdf|txt).
mk_sealed(){ # fixture-dir audience kind
  local fx="$1" aud="$2" kind="${3:-pdf}"
  valid_profile "$fx/patients/sztseal/profile.md"
  ( cd "$ROOT" && python3 - "$fx" "$aud" "$kind" <<'PYEOF'
import hashlib, json, os, sys
from tools.handout_attest.verify import ATTEST_SCHEMA
fx, aud, kind = sys.argv[1], sys.argv[2], sys.argv[3]
hid = "TAB-ZZZ-999A"
enc, stem = "2026-07-16-bite", "2026-07-16__handout-%s__bite" % aud
d = os.path.join(fx, "patients", "sztseal", "med", "handouts", aud, enc)
os.makedirs(d, exist_ok=True)
sha = lambda b: hashlib.sha256(b).hexdigest()
md = b"id: " + hid.encode() + b"\ndate: 2026-07-16\nlang: pl\n\n# Karta testowa\n\ntresc syntetyczna\n"
fc = b"handout_sha256: " + sha(md).encode() + b"\nverdict: PASS\nmust_fix_open: 0\n\n# ledger\n- ok\n"
out = b"%PDF-synthetic" if kind == "pdf" else b"plain fallback\n"
open(os.path.join(d, stem + ".md"), "wb").write(md)
open(os.path.join(d, stem + ".factcheck.md"), "wb").write(fc)
open(os.path.join(d, stem + "." + kind), "wb").write(out)
attest = {"schema": ATTEST_SCHEMA, "tool": "selftest-fixture",
          "md_file": stem + ".md", "md_sha256": sha(md), "factcheck_sha256": sha(fc),
          "output_kind": kind, "output_file": stem + "." + kind, "output_sha256": sha(out),
          "audience": aud, "lang": "pl", "id": hid,
          "person": "sztseal", "encounter": enc,
          "build_qa": "PASS" if kind == "pdf" else "FALLBACK",
          "timestamp": "2026-07-16T00:00:00Z"}
open(os.path.join(d, stem + ".attest.json"), "w").write(json.dumps(attest))
idx = os.path.join(fx, "patients", "sztseal", "med", "handouts", "INDEX.md")
with open(idx, "a") as f:
    f.write("| %s | current |\n" % enc)
PYEOF
  )
}
SB="patients/sztseal/med/handouts/patient/2026-07-16-bite/2026-07-16__handout-patient__bite"
# the md re-fact-checked after an edit but the PDF never re-rendered (the gap L15 exists to close)
d="$(mk)"; mk_sealed "$d" patient
printf '\nedycja po zapieczetowaniu\n' >> "$d/$SB.md"; mk_pass_sidecar "$d/$SB.md"
assert_fail "$d" L15 "fresh factcheck but stale render fires L15"
# The control also carries the SOP's draft home (HANDOUT-SOP step 1): a draft, its preview and empty
# folders under med/analysis/ sit beside sealed units with the board green — L15 reads med/handouts/ only.
mk_draft_home(){ # fixture-dir (person sztseal)
  local a="$1/patients/sztseal/med/analysis"
  mkdir -p "$a/drafts/patient/2026-10-05-next" "$a/drafts/scratch" "$a/previews"
  printf 'id: TAB-ZZZ-999B\ndate: 2026-10-05\nlang: pl\n\n# Szkic\n' > "$a/drafts/2026-10-05__handout-patient__next.md"
  printf 'draft pdf' > "$a/drafts/2026-10-05__handout-patient__next.draft.pdf"
  printf '<html></html>\n' > "$a/previews/2026-10-05__handout-patient__next.draft-1.html"
}
d="$(mk)"; mk_sealed "$d" patient; mk_sealed "$d" clinician; mk_draft_home "$d"
assert_pass "$d" "L15 green: sealed units, audiences independent, drafts and empty folders in the draft home"
# its twin: the same kind of empty folder under med/handouts/ reds, and the red names the draft home
d="$(mk)"; mk_sealed "$d" patient; mkdir -p "$d/patients/sztseal/med/handouts/patient/2026-10-05-next"
out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
if [ "$rc" -ne 0 ] && grep -q "\[phantom-encounter-dir\]" <<<"$out" && grep -qF "med/analysis/drafts/" <<<"$out"; then
  echo "BITE  OK  (an empty folder in the handouts lane fires L15 and names the draft home)"; pass=$((pass+1))
else
  echo "BITE  MISS (an empty folder in the handouts lane: expected L15 [phantom-encounter-dir] and the draft-home pointer, rc=$rc)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
fi; rm -rf "$d"
# tools/handout_attest wiring: an inventoried legacy deliverable's BYTES change after the freeze
# (names still match — the class the old names-only inventory waved through); unchanged it stays queued, green
mk_legacy(){ # fixture-dir — flat md+sidecar and an archived pdf under synthetic patient sztown
  valid_profile "$1/patients/sztown/profile.md"
  mkdir -p "$1/patients/sztown/med/handouts/patient/archive"
  printf 'legacy pdf' > "$1/patients/sztown/med/handouts/patient/archive/2026-04-01__handout-patient__old.pdf"
  printf 'id: x\ndate: 2026-06-08\n\n# Karta\ntresc\n' > "$1/patients/sztown/med/handouts/patient/2026-06-08__handout-patient__flat.md"
  mk_pass_sidecar "$1/patients/sztown/med/handouts/patient/2026-06-08__handout-patient__flat.md"
}
d="$(mk)"; mk_legacy "$d"; mk_legacy_freeze "$d" sztown
printf 'EDITED after the freeze' > "$d/patients/sztown/med/handouts/patient/archive/2026-04-01__handout-patient__old.pdf"
assert_fail "$d" L15 "inventoried legacy deliverable's bytes changed after the freeze"
d="$(mk)"; mk_legacy "$d"; mk_legacy_freeze "$d" sztown
assert_pass "$d" "L15 queues INVENTORIED legacy flat+archive handouts green (deferred migration)"

# L13 / L15 without python3 (TABULARIUM_TEST_NO_PYTHON=1 hides it): a scaffolded person, documents or not,
# reds both, once each; an original in _shared/med alone reds L13 only; a person-free tree stays green.
np_run(){ out="$(TABULARIUM_TEST_NO_PYTHON=1 bash "$CHECK" "$1" 2>&1)"; rc=$?; chmod -R u+rwX "$1" 2>/dev/null; rm -rf "$1"; }
np_n(){ grep -c "^FAIL \[$1\] python3 not on PATH" <<<"$out"; }
d="$(mk)"; valid_profile "$d/patients/sztnopy/profile.md"; np_run "$d"
if [ "$rc" -ne 0 ] && [ "$(np_n L13)" = 1 ] && [ "$(np_n L15)" = 1 ]; then
  echo "BITE  OK  (no python3: a scaffolded person reds L13 and L15, once each)"; pass=$((pass+1))
else echo "BITE  MISS (no python3, scaffolded person: rc=$rc L13=$(np_n L13) L15=$(np_n L15))"; echo "$out" | sed 's/^/      /' | tail -8; fail=$((fail+1)); fi
d="$(mk)"; mkdir -p "$d/_shared/med"; echo scan > "$d/_shared/med/2026-01-01__lab__x.pdf"; np_run "$d"
if [ "$rc" -ne 0 ] && [ "$(np_n L13)" = 1 ] && [ "$(np_n L15)" = 0 ]; then
  echo "BITE  OK  (no python3: an original in _shared/med with no person folder reds L13, not L15)"; pass=$((pass+1))
else echo "BITE  MISS (no python3, _shared/med only: rc=$rc L13=$(np_n L13) L15=$(np_n L15))"; echo "$out" | sed 's/^/      /' | tail -8; fail=$((fail+1)); fi
d="$(mk)"; mkdir -p "$d/patients" "$d/_shared/med"; : > "$d/patients/README.md"; np_run "$d"
if [ "$rc" -eq 0 ]; then echo "CLEAN OK  (no python3: a person-free tree, roster and empty _shared/med, stays green)"; pass=$((pass+1))
else echo "CLEAN FAIL (no python3, person-free tree: rc=$rc)"; echo "$out" | sed 's/^/      /' | tail -8; fail=$((fail+1)); fi

# confirms.sh — an OVERDUE dated tag or open-items row exits nonzero; future-only ones (and a dateless
# row) stay green
conf_rows(){ # $@ = "by when" cells -> an open-items block with one example row per cell
  local c; printf '<!-- OPEN-ITEMS:BEGIN -->\n| what | who | by when | state |\n|------|-----|---------|-------|\n'
  for c in "$@"; do printf '| example item | example clinic | %s | booked |\n' "$c"; done
  printf '<!-- OPEN-ITEMS:END -->\n'; }
d="$(mk)"; mkdir -p "$d/patients/sztconf"
printf '# Profile — t\n⟨confirm by 2000-01: obtain the missing record⟩\n' > "$d/patients/sztconf/profile.md"
assert_confirms "$d" 1 "overdue confirm tag fires"
d="$(mk)"; mkdir -p "$d/patients/sztconf"
{ printf '# Profile — t\n⟨confirm by 2999-12: obtain the missing record⟩\n'; conf_rows 2999-12-31 2999-12 —; } > "$d/patients/sztconf/profile.md"
assert_confirms "$d" 0 "future-only confirm tag and open-items rows are green"
d="$(mk)"; mkdir -p "$d/patients/sztconf"
{ printf '# Profile — t\n'; conf_rows 2999-12-31 2000-01-05; } > "$d/patients/sztconf/profile.md"
assert_confirms "$d" 1 "overdue open-items row fires"
# a scan it could not make is never "no tags", a deadline it cannot read is
# flagged, and a person's analysis notes are in the queue while sealed handouts stay out
conf_fx(){ local d; d="$(mk)"; mkdir -p "$d/patients/sztconf"; echo "$d"; }
CONF_P='patients/sztconf/profile.md'; CONF_TAG='⟨confirm by 2000-01: obtain the missing record⟩'
# A45 — exit 2 and named (the suite runs unprivileged: as root, chmod 000 hides nothing)
d="$(conf_fx)"; printf '# Medications — t\n%s\n' "$CONF_TAG" > "$d/patients/sztconf/medications.md"; chmod 000 "$d/patients/sztconf/medications.md"
assert_confirms "$d" 2 "A45 an unreadable medications.md is an incomplete scan, never 'no tags'" "UNREADABLE patients/sztconf/medications.md"
d="$(conf_fx)"; printf '# Profile — t\n%s\n' "$CONF_TAG" > "$d/$CONF_P"; chmod 000 "$d/patients/sztconf"
assert_confirms "$d" 2 "A45 a person folder find cannot list is an incomplete scan" "find could not list"
assert_confirms "$(mktemp -d)" 2 "A45 a ROOT that is not the repo refuses, never an empty queue" "not at repo root"
assert_confirms "$(mk)" 0 "A45 twin: a repo root with no patients/ is an empty queue" "0 file(s) scanned"
d="$(conf_fx)"; printf '# Profile — t\n\000\n%s\n' "$CONF_TAG" > "$d/$CONF_P"
assert_confirms "$d" 1 "A45 a stray NUL byte does not hide the file's tags" "OVERDUE  2000-01  $CONF_P:3"
# A49 — MALFORMED, exit 1, file:line named; prose, the undated tag and the templates' YYYY-MM placeholders
# are not tags
for c in "month 13|⟨confirm by 2999-13: x⟩" "short month|⟨confirm by 2999-1: x⟩" \
         "non-breaking space|⟨confirm"$'\xc2\xa0'"by 2999-12: x⟩"; do
  d="$(conf_fx)"; printf '# Profile — t\n%s\n' "${c#*|}" > "$d/$CONF_P"
  assert_confirms "$d" 1 "A49 a tag with a ${c%%|*} is MALFORMED" "MALFORMED $CONF_P:2"
done
d="$(conf_fx)"; { printf '# Profile — t\n'; conf_rows 2999-13-01; } > "$d/$CONF_P"
assert_confirms "$d" 1 "A49 an open-items row dated month 13 is MALFORMED" "MALFORMED $CONF_P:5"
d="$(conf_fx)"
printf '# Profile — t\nAsk the clinic to confirm by phone; they confirm by 10 June.\n%s\n%s\n' \
  '⟨confirm current use of example drug⟩ ⟨confirm by YYYY-MM: placeholder⟩' \
  '⟨confirm by 2999-12: x⟩ ⟨confirm by 2999-12-31: y⟩' > "$d/$CONF_P"
assert_confirms "$d" 0 "A49 twin: prose, the undated tag and a placeholder are not tags; well-formed ones are" "2 future, 0 malformed"
d="$(conf_fx)"; cp "$ROOT/_templates/profile.md" "$d/$CONF_P"; cp "$ROOT/_templates/medications.md" "$d/patients/sztconf/medications.md"
assert_confirms "$d" 0 "A49 twin: a person scaffolded from the templates queues nothing" "0 malformed — 2 file(s) scanned"
# A50 — analysis notes at any depth (drafts included) are scanned; a sealed handout is not (immutable: an
# overdue tag there has no fix); a private-mode person's note name is withheld
d="$(conf_fx)"; printf '# Profile — t\n' > "$d/$CONF_P"; mkdir -p "$d/patients/sztconf/med/analysis/notes"
printf '# Note\n%s\n' "$CONF_TAG" > "$d/patients/sztconf/med/analysis/notes/2026-01-01__example-note.md"
assert_confirms "$d" 1 "A50 an overdue tag in an analysis note is listed" "OVERDUE  2000-01  patients/sztconf/med/analysis/notes/2026-01-01__example-note.md:2"
d="$(conf_fx)"; printf '# Profile — t\n' > "$d/$CONF_P"; mkdir -p "$d/patients/sztconf/med/handouts/clinician/2026-01-01-example"
printf '# Handout\n%s\n' "$CONF_TAG" > "$d/patients/sztconf/med/handouts/clinician/2026-01-01-example/2026-01-01__handout-clinician__example.md"
assert_confirms "$d" 0 "A50 twin: a sealed handout is not scanned" "1 file(s) scanned"
d="$(conf_fx)"; printf '# Profile — t\n' > "$d/$CONF_P"; pm_mark "$d/$CONF_P"; mkdir -p "$d/patients/sztconf/med/analysis"
printf '# Note\n%s\n' "$CONF_TAG" > "$d/patients/sztconf/med/analysis/2026-01-01__zqexample.md"
assert_confirms "$d" 1 "A50 a private-mode person's note is listed with its name withheld" \
  "OVERDUE  2000-01  patients/sztconf/med/analysis/<name withheld" "zqexample"

# L19 / L20 — the instance model (ADR-0050): DEV never holds a record; CARE is a pull-only checkout of a
# release tag plus the records. L20 derives the mode from which RECORD-SET paths exist (the marker only
# asserts it); L19 holds CARE's "never edits a tracked file". Fixtures are synthetic; the git ones build a
# BARE origin, push tagged releases, clone and detach at the fetched tag. Every git call strips the
# inherited git environment: under the pre-commit hook GIT_DIR/GIT_INDEX_FILE override `git -C` and once
# wrote into the REAL repository (core.bare flipped). Every fixture clone in this suite passes --no-local: it
# goes through git's transport, as a clone from a real remote does, instead of copying object files, and a
# repository just committed or pushed to may be packing itself in a detached maintenance process that a
# file copy can race into a clone missing objects.
inst_git(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY git "$@"; }
# a record-free product tree: CLAUDE.md + checks/ + the real RECORD-SET and .gitignore (not mk(): the
# ignore-mirror check needs them)
inst_mk(){ local d; d="$(mktemp -d)"; : > "$d/CLAUDE.md"; mkdir -p "$d/checks"
  cp "$ROOT/checks/RECORD-SET" "$d/checks/RECORD-SET"; cp "$ROOT/.gitignore" "$d/.gitignore"; echo "$d"; }
inst_mkgit(){ local d; d="$(inst_mk)"
  inst_git -C "$d" init -q >/dev/null 2>&1
  inst_git -C "$d" config user.email t@t.test; inst_git -C "$d" config user.name tester
  inst_git -C "$d" config commit.gpgsign false
  inst_git -C "$d" config core.hooksPath "$d/.git/hooks"   # never inherit a global hooksPath
  echo "$d"; }
# a CARE instance built the way a real one is: bare origin ← two tagged releases ← clone ← detach at the
# fetched tag, plus the untracked checks/CARE-RELEASE pin. Returns the CLONE; its parent temp dir holds
# origin+seed and is what inst_rm reaps.
inst_mkcare(){ local d o s w; d="$(mktemp -d)"; o="$d/origin.git"; s="$d/seed"; w="$d/care"
  inst_git init -q --bare "$o" >/dev/null 2>&1; inst_git -C "$o" symbolic-ref HEAD refs/heads/main
  mkdir -p "$s/checks"; : > "$s/CLAUDE.md"
  cp "$ROOT/checks/RECORD-SET" "$s/checks/RECORD-SET"; cp "$ROOT/.gitignore" "$s/.gitignore"
  inst_git -C "$s" init -q >/dev/null 2>&1; inst_git -C "$s" symbolic-ref HEAD refs/heads/main
  inst_git -C "$s" config user.email t@t.test; inst_git -C "$s" config user.name tester
  inst_git -C "$s" config commit.gpgsign false; inst_git -C "$s" config core.hooksPath "$s/.git/hooks"
  inst_git -C "$s" add -A >/dev/null 2>&1; inst_git -C "$s" commit -q -m "release v0" >/dev/null 2>&1
  inst_git -C "$s" tag v1.0.0 >/dev/null 2>&1
  printf 'synthetic second release\n' > "$s/RELEASE-NOTES.md"
  inst_git -C "$s" add -A >/dev/null 2>&1; inst_git -C "$s" commit -q -m "release v1" >/dev/null 2>&1
  inst_git -C "$s" tag v1.1.0 >/dev/null 2>&1
  inst_git -C "$s" push -q "$o" main --tags >/dev/null 2>&1
  inst_git clone -q --no-local "$o" "$w" >/dev/null 2>&1
  inst_git -C "$w" config user.email t@t.test; inst_git -C "$w" config user.name tester
  inst_git -C "$w" config commit.gpgsign false; inst_git -C "$w" config core.hooksPath "$w/.git/hooks"
  inst_git -C "$w" checkout -q --detach v1.1.0 >/dev/null 2>&1
  valid_profile "$w/patients/szinst/profile.md"
  echo care > "$w/.tabularium-instance"
  echo v1.1.0 > "$w/checks/CARE-RELEASE"
  echo "$w"; }
# teardown climbs one level, and `dirname` of an empty string is `.` (the REAL repository under this
# script's cwd): refuse anything that is not the absolute `<mktemp -d>/care` shape built above
inst_rm(){
  case "${1:-}" in
    /*/care) rm -rf "$(dirname "$1")" ;;
    *) echo "BITE  MISS (instance fixtures: refusing to remove '${1:-<empty>}' — not a fixture path)"; fail=$((fail+1)) ;;
  esac; }
# green AND says so: a mode that passes must announce what it derived (a silent green is a guard that
# examined nothing)
inst_pass_says(){ # dir pattern label
  local d="$1" pat="$2" label="$3" out rc
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q "$pat" <<<"$out"; then
    echo "BITE  OK  ($label): green and announced"; pass=$((pass+1))
  else
    echo "BITE  MISS ($label): expected rc=0 + /$pat/, got rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; }

if command -v git >/dev/null 2>&1; then
  # L20: a DEV tree holding a record category reds (the mis-marked direction the derived mode exists for);
  # the clean twin is the same tree record-free
  d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"; valid_profile "$d/patients/szinst/profile.md"
  assert_fail "$d" L20 "L20: dev tree holding patients/"
  d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"
  inst_pass_says "$d" 'L20 instance: dev — record-free.*ignore-mirror verified' "L20: dev, record-free (clean twin)"; rm -rf "$d"
  # L20's record-shape scan reads the INDEX as well as the disk, because the index is what a commit
  # carries. The two blind spots the 2026-10-25 break rounds reproduced each red: a record-shaped path
  # staged and then deleted from disk, and one staged under a NESTED .claude/ that the disk scan prunes.
  # A third stages a handle holding a `"`, which git C-quotes unless the index is read with -z (review
  # 2026-10-25). The clean twin keeps the nested path on disk but unstaged, beside a staged template
  # scaffold, one of its names holding a `"` (a quoted path must not slip out of the exemption).
  # Mutation: a copy of check.sh whose index read returns nothing must green all three bites, and
  # still red a record on disk (its positive control: the mutant greens for the right reason).
  l20_idx_fx(){ # case -> a dev fixture
    local d; d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"
    case "$1" in
      staged-gone) valid_profile "$d/x/patients/szinst/profile.md"; inst_git -C "$d" add -A >/dev/null 2>&1; rm -rf "$d/x" ;;
      quoted)      valid_profile "$d/x/patients/sz\"inst/profile.md"; inst_git -C "$d" add -A >/dev/null 2>&1; rm -rf "$d/x" ;;
      disk)        valid_profile "$d/x/patients/szinst/profile.md" ;;
      nested)      valid_profile "$d/x/.claude/patients/szinst/profile.md"; inst_git -C "$d" add -A >/dev/null 2>&1 ;;
      twin)        mkdir -p "$d/_templates/person/med/sources"; : > "$d/_templates/person/med/sources/README.md"; : > "$d/_templates/person/med/sources/a\"b.md"
                   inst_git -C "$d" add -A >/dev/null 2>&1; valid_profile "$d/x/.claude/patients/szinst/profile.md" ;;
    esac; echo "$d"; }
  l20_idx_red(){ # dir [check.sh] -> 0 when the record-shape red fired (a here-string: the board exits red, and pipefail)
    local out; out="$(bash "${2:-$CHECK}" "$1" 2>&1)"
    grep -q 'FAIL \[L20\] marked dev but [0-9]* path(s) match a record shape' <<<"$out"; }
  l20_mut="$(mktemp -d)"; mkdir -p "$l20_mut/checks"; ln -s "$ROOT/tools" "$l20_mut/tools"
  sed 's/l20_git ls-files -z/true/' "$CHECK" > "$l20_mut/checks/check.sh"
  cmp -s "$CHECK" "$l20_mut/checks/check.sh" && { echo "BITE  MISS (L20 index scan: the mutation did not apply — the index read moved)"; fail=$((fail+1)); }
  d="$(l20_idx_fx disk)"
  if l20_idx_red "$d" "$l20_mut/checks/check.sh"; then echo "BITE  OK  (L20 index scan mutant, positive control: still reds a record on disk)"; pass=$((pass+1))
  else echo "BITE  MISS (L20 index scan mutant, positive control: no red for a record on disk, so the mutant is broken and the mutation bites prove nothing)"; bash "$l20_mut/checks/check.sh" "$d" 2>&1 | sed 's/^/      /'; fail=$((fail+1)); fi; rm -rf "$d"
  for _c in staged-gone nested quoted; do
    d="$(l20_idx_fx "$_c")"
    if l20_idx_red "$d"; then echo "BITE  OK  (L20: dev, record shape in the index only — $_c)"; pass=$((pass+1))
    else echo "BITE  MISS (L20: dev, record shape in the index only — $_c: no record-shape red)"; bash "$CHECK" "$d" 2>&1 | sed 's/^/      /'; fail=$((fail+1)); fi
    if l20_idx_red "$d" "$l20_mut/checks/check.sh"; then echo "BITE  MISS (L20 index scan mutation — $_c: still red with the index read removed, so the bite does not test it)"; fail=$((fail+1))
    else echo "BITE  OK  (L20 index scan mutation — $_c: the bite misses without the index read)"; pass=$((pass+1)); fi
    rm -rf "$d"
  done; rm -rf "$l20_mut"
  d="$(l20_idx_fx twin)"
  inst_pass_says "$d" 'L20 instance: dev — record-free (record-shape scan clean, disk and index' "L20: dev, nested .claude record shape unstaged, template scaffold staged (clean twin)"; rm -rf "$d"
  # Four more from the review of 2026-10-25, each with its twin and its own mutant (a sed on a copy of
  # check.sh, cmp-checked so a moved line cannot pass for a caught mutation):
  #  (a) the hook's own index: a record staged only in an alternate index (GIT_INDEX_FILE) and gone
  #      from disk blocks that commit through a real pre-commit hook; twin — the same alternate index,
  #      but the commit uses the default one, which goes through;
  #  (b) a hit only the index has is counted, never named: a private-mode profile staged, then deleted,
  #      reds without its handle; twin — a hit on disk (the nested case) is still named;
  #  (c) a name holding a line break, staged then deleted, still reds as one hit;
  #  (d) a checkout git calls bare (core.bare true) reds once with the fix; twin — the record-free clean
  #      twin above.
  l20_mk_mut(){ # sed-expression -> a mutant check.sh path (empty, and a MISS, if the sed changed nothing)
    local m; m="$(mktemp -d)"; mkdir -p "$m/checks"; ln -s "$ROOT/tools" "$m/tools"
    sed "$1" "$CHECK" > "$m/checks/check.sh"
    if cmp -s "$CHECK" "$m/checks/check.sh"; then echo "BITE  MISS (L20 mutant '$1' did not apply — the line moved)" >&2; rm -rf "$m"; return 1; fi
    echo "$m"; }
  l20_altgit(){ local i="$1"; shift; env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY GIT_INDEX_FILE="$i" git "$@"; }
  l20_alt_fx(){ # check.sh -> a dev fixture whose pre-commit hook runs that board; record staged only in .git/alt
    local d; d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"
    printf '#!/bin/sh\nexec bash "%s" "$(git rev-parse --show-toplevel)"\n' "$1" > "$d/.git/hooks/pre-commit"; chmod +x "$d/.git/hooks/pre-commit"
    inst_git -C "$d" add CLAUDE.md >/dev/null 2>&1
    valid_profile "$d/x/patients/szinst/profile.md"; l20_altgit "$d/.git/alt" -C "$d" add -A >/dev/null 2>&1; rm -rf "$d/x"
    echo "$d"; }
  l20_alt_commit(){ # dir [alt|default] -> rc of the commit
    if [ "$2" = alt ]; then l20_altgit "$1/.git/alt" -C "$1" commit -q -m t >/dev/null 2>&1; else inst_git -C "$1" commit -q -m t >/dev/null 2>&1; fi; }
  if l20_m="$(l20_mk_mut 's/if \[ -n "\${GIT_INDEX_FILE:-}" \]; then/if false; then/')"; then
    d="$(l20_alt_fx "$CHECK")"
    if ! l20_alt_commit "$d" alt && ! inst_git -C "$d" rev-parse -q --verify HEAD >/dev/null 2>&1; then echo "BITE  OK  (L20: record staged only in the commit's own index blocks it at the hook)"; pass=$((pass+1))
    else echo "BITE  MISS (L20: a commit from an alternate index carrying a record went through)"; fail=$((fail+1)); fi; rm -rf "$d"
    d="$(l20_alt_fx "$CHECK")"
    if l20_alt_commit "$d" default; then echo "CLEAN OK  (L20: the same alternate index, committing from the default one goes through)"; pass=$((pass+1))
    else echo "CLEAN FAIL (L20: a commit from a clean default index was blocked by a record in another index)"; fail=$((fail+1)); fi; rm -rf "$d"
    d="$(l20_alt_fx "$l20_m/checks/check.sh")"
    if l20_alt_commit "$d" alt; then echo "BITE  OK  (L20 mutant without the hook's index: that commit goes through, so the bite tests it)"; pass=$((pass+1))
    else echo "BITE  MISS (L20 mutant without the hook's index still blocks — the bite does not test it)"; fail=$((fail+1)); fi; rm -rf "$d" "$l20_m"
  else fail=$((fail+1)); fi
  l20_priv_fx(){ local d; d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"
    valid_profile "$d/x/patients/szprivx/profile.md"; pm_mark "$d/x/patients/szprivx/profile.md"
    inst_git -C "$d" add -A >/dev/null 2>&1; rm -rf "$d/x"; echo "$d"; }
  if l20_m="$(l20_mk_mut 's/if \[ ! -e "\$_h" \] && \[ ! -L "\$_h" \]; then l20_hidden=\$((l20_hidden+1)); continue; fi/:/')"; then
    d="$(l20_priv_fx)"; out="$(bash "$CHECK" "$d" 2>&1)"
    if grep -q 'match a record shape.*1 staged but gone from disk (names withheld' <<<"$out" && ! grep -q szprivx <<<"$out"; then echo "BITE  OK  (L20: a private profile staged then deleted reds, counted, its handle withheld)"; pass=$((pass+1))
    else echo "BITE  MISS (L20: staged-then-deleted private profile — expected a counted red with no handle)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
    out="$(bash "$l20_m/checks/check.sh" "$d" 2>&1)"
    if grep -q szprivx <<<"$out"; then echo "BITE  OK  (L20 mutant without the withholding names the handle, so the bite tests it)"; pass=$((pass+1))
    else echo "BITE  MISS (L20 mutant without the withholding still hides the handle — the bite does not test it)"; fail=$((fail+1)); fi; rm -rf "$d" "$l20_m"
    d="$(l20_idx_fx nested)"; out="$(bash "$CHECK" "$d" 2>&1)"
    if grep -q 'match a record shape.*x/\.claude/patients/szinst/profile\.md' <<<"$out" && ! grep -q 'names withheld' <<<"$out"; then echo "CLEAN OK  (L20: a hit on disk is still named)"; pass=$((pass+1))
    else echo "CLEAN FAIL (L20: a hit on disk was not named)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi; rm -rf "$d"
  else fail=$((fail+1)); fi
  d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"; valid_profile "$d/x/patients/sz
inst/profile.md"
  inst_git -C "$d" add -A >/dev/null 2>&1; rm -rf "$d/x"
  if l20_idx_red "$d"; then echo "BITE  OK  (L20: a staged name holding a line break reds)"; pass=$((pass+1))
  else echo "BITE  MISS (L20: a staged name holding a line break passed)"; bash "$CHECK" "$d" 2>&1 | sed 's/^/      /'; fail=$((fail+1)); fi; rm -rf "$d"
  if l20_m="$(l20_mk_mut 's/--is-inside-work-tree 2>\/dev\/null)" = false \]/--is-inside-work-tree 2>\/dev\/null)" = never ]/')"; then
    d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"; inst_git -C "$d" config core.bare true
    out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ] && grep -q 'FAIL \[L20\] git reports this checkout as bare.*git config core.bare false' <<<"$out"; then echo "BITE  OK  (L20: a checkout git calls bare reds once, with the fix)"; pass=$((pass+1))
    else echo "BITE  MISS (L20: core.bare true — expected the bare red, rc=$rc)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1)); fi
    if grep -q 'git reports this checkout as bare' <<<"$(bash "$l20_m/checks/check.sh" "$d" 2>&1)"; then echo "BITE  MISS (L20 bare mutant still names the bare checkout)"; fail=$((fail+1))
    else echo "BITE  OK  (L20 bare mutant: the red is gone, so the bite tests it)"; pass=$((pass+1)); fi; rm -rf "$d" "$l20_m"
  else fail=$((fail+1)); fi
  # L19: a modified tracked file in CARE reds; the clean twin is a clone at its adopted release, records only
  w="$(inst_mkcare)"; echo x >> "$w/CLAUDE.md"; assert_fail "$w" L19 "L19: CARE modified a tracked file"; inst_rm "$w"
  # L19's two remedies (break round 2026-10-25): an edited tracked file is told to revert; a path not in the
  # adopted release — untracked, staged new, intent-to-add, the new side of a rename — may be a misfiled
  # record and is told never to delete it; when one path shows both ways (`git rm --cached`) only that remedy
  # prints; the old line parser's " -> " split is gone (a name that held one could pass green). The clean
  # twin is the CARE clone above, green.
  l19_has(){ grep -qF "$1" <<<"$2"; }
  l19_nd="never delete it: ask the operator whose it is"
  w="$(inst_mkcare)"
  echo x >> "$w/CLAUDE.md"
  mkdir -p "$w/stray" "$w/tools"; printf 'synthetic\n' > "$w/stray/scan.pdf"
  printf 'synthetic\n' > "$w/tools/staged-new.md"; inst_git -C "$w" add tools/staged-new.md
  printf 'synthetic\n' > "$w/tools/ita.md"; inst_git -C "$w" add -N tools/ita.md
  inst_git -C "$w" mv RELEASE-NOTES.md notes-renamed.md
  printf 'synthetic\n' > "$w/tools/.DS_Store -> .DS_Store"
  printf 'synthetic\n' > "$w/stray/line"$'\n'"break.txt"
  printf 'synthetic\n' > "$w/stray/\"quoted\" name.pdf"; printf 'synthetic\n' > "$w/-leading.pdf"
  mkdir -p "$w/newdir/sub"; printf 'synthetic\n' > "$w/newdir/sub/file.pdf"
  printf 'synthetic\n' > "$w/stray/ctl"$'\001'"byte.pdf"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  l19_ok=1
  l19_has "not in the adopted release: stray/line?break.txt — $l19_nd" "$out" || { l19_ok=0; echo "      missing never-delete line: a name with a line break"; }
  for _q in stray/scan.pdf tools/staged-new.md tools/ita.md notes-renamed.md "tools/.DS_Store -> .DS_Store" \
            'stray/"quoted" name.pdf' -leading.pdf newdir/sub/file.pdf 'stray/ctl?byte.pdf'; do
    l19_has "FAIL [L19] new path outside the record set, not in the adopted release: $_q — $l19_nd" "$out" || { l19_ok=0; echo "      missing never-delete line: $_q"; }
    l19_has "change outside the record set: $_q —" "$out" && { l19_ok=0; echo "      revert remedy on a new path: $_q"; }
  done
  for _q in CLAUDE.md RELEASE-NOTES.md; do
    l19_has "FAIL [L19] working-tree change outside the record set: $_q — CARE never edits a tracked file (ADR-0050); revert it here" "$out" || { l19_ok=0; echo "      missing revert line: $_q"; }
    l19_has "not in the adopted release: $_q —" "$out" && { l19_ok=0; echo "      never-delete remedy on a tracked edit: $_q"; }
  done
  if [ "$rc" -ne 0 ] && [ "$l19_ok" -eq 1 ]; then
    echo "BITE  OK  (L19: tracked edits are told to revert; untracked, staged-new, intent-to-add, renamed-to, nested, quoted, dash-led, control-byte and \" -> \"-named paths are told never to delete)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L19 remedy split, rc=$rc)"; echo "$out" | grep 'L19' | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  w="$(inst_mkcare)"; inst_git -C "$w" rm -q --cached RELEASE-NOTES.md
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && l19_has "not in the adopted release: RELEASE-NOTES.md — $l19_nd" "$out" \
     && ! l19_has "change outside the record set: RELEASE-NOTES.md" "$out"; then
    echo "BITE  OK  (L19: a path both removed from the index and on disk gets only the never-delete remedy)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L19 git rm --cached, rc=$rc)"; echo "$out" | grep 'L19' | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  # While a person is in private mode, a new path's NAME is withheld and counted — a stray file name can carry
  # the identifier, and a product path has no owner for the locator rule to withhold by. Clean twin: the same
  # stray with no private-mode person is named, in the remedy-split bite above.
  # An intent-to-add file then moved away (status ` D`, not in HEAD) stays withheld too, and a tracked edit's
  # product name still prints.
  w="$(inst_mkcare)"; valid_profile "$w/patients/szpriv/profile.md"; printf -- '- Private mode: on ⟨never-API⟩\n' >> "$w/patients/szpriv/profile.md"
  mkdir -p "$w/stray"; printf 'synthetic\n' > "$w/stray/Qqzyx 99887766554 discharge.pdf"
  printf 'synthetic\n' > "$w/stray/Qqzyx 11223344556 letter.pdf"; inst_git -C "$w" add -N "stray/Qqzyx 11223344556 letter.pdf"
  mkdir -p "$w/patients/szpriv/med/_inbox"; mv "$w/stray/Qqzyx 11223344556 letter.pdf" "$w/patients/szpriv/med/_inbox/"
  echo x >> "$w/CLAUDE.md"
  # another guard must not disclose it either: a library file whose name carries the identifier and whose
  # text names a person reaches L5's library scan (review 2026-10-25)
  mkdir -p "$w/reference-library"; printf 'note about szinst here\n' > "$w/reference-library/Qqzyx-77665544332.md"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && l19_has "FAIL [L19] 2 new path(s) outside the record set, not in the adopted release — names withheld while private mode is in use" "$out" \
     && l19_has "referenced inside the shared reference-library/ in 1 line(s) — file names and lines withheld while private mode is in use" "$out" \
     && ! l19_has "77665544332" "$out" \
     && l19_has "FAIL [L19] 1 new path(s) still listed by git but gone from disk — names withheld" "$out" \
     && l19_has "FAIL [L19] working-tree change outside the record set: CLAUDE.md" "$out" \
     && ! l19_has "99887766554" "$out" && ! l19_has "11223344556" "$out" && ! l19_has "Qqzyx" "$out"; then
    echo "BITE  OK  (L19/L5: with a private-mode person present, new paths' names are withheld and counted, a moved intent-to-add one too, and L5's library hits too; a tracked edit is still named)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L19 private-mode withholding, rc=$rc)"; echo "$out" | grep -E 'L19|L5|99887766554|11223344556|77665544332|Qqzyx' | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  # clean twin for L5: with no private-mode person the library hit is printed whole, file name included
  w="$(inst_mkcare)"; mkdir -p "$w/reference-library"; printf 'note about szinst here\n' > "$w/reference-library/Qqzyx-77665544332.md"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && l19_has "reference-library/Qqzyx-77665544332.md:1:note about szinst here" "$out"; then
    echo "BITE  OK  (L5: with no private-mode person a library hit prints whole — the twin the withholding is measured against)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L5 library twin, rc=$rc)"; echo "$out" | grep L5 | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  # a private-mode person whose folder name holds a line break is still seen (the people are enumerated with
  # a quoted glob, as L10 does, not by splitting find output on line breaks)
  w="$(inst_mkcare)"; valid_profile "$w/patients/szp"$'\n'"riv/profile.md"; printf -- '- Private mode: on ⟨never-API⟩\n' >> "$w/patients/szp"$'\n'"riv/profile.md"
  mkdir -p "$w/stray"; printf 'synthetic\n' > "$w/stray/Qqzyx 55443322110 scan.pdf"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && ! l19_has "55443322110" "$out" && l19_has "names withheld while private mode is in use" "$out"; then
    echo "BITE  OK  (locator rule: a private-mode person whose folder name holds a line break still turns withholding on)"; pass=$((pass+1))
  else
    echo "BITE  MISS (private-mode folder with a line break, rc=$rc)"; echo "$out" | grep -E 'L19|55443322110' | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  # A staged new file then moved away as the remedy says (`AD`) is told how to unstage it, and once unstaged
  # the board is green again — a care session has a way back.
  w="$(inst_mkcare)"; mkdir -p "$w/stray"; printf 'synthetic\n' > "$w/stray/scan2.pdf"; inst_git -C "$w" add stray/scan2.pdf
  mkdir -p "$w/_archive"; mv "$w/stray/scan2.pdf" "$w/_archive/"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  inst_git -C "$w" rm -q --cached stray/scan2.pdf
  out2="$(bash "$CHECK" "$w" 2>&1)"; rc2=$?
  if [ "$rc" -ne 0 ] && l19_has "FAIL [L19] new path still listed by git but gone from disk: stray/scan2.pdf — unstage it with git rm --cached" "$out" \
     && [ "$rc2" -eq 0 ] && [ -f "$w/_archive/scan2.pdf" ]; then
    echo "BITE  OK  (L19: a staged file moved away is told how to unstage it, and the board is green once it is)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L19 staged-then-moved, rc=$rc then rc=$rc2)"; { echo "$out"; echo "$out2"; } | grep L19 | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  # git status failing is a red, never a clean working tree (the status code rides through a pipe and a parse)
  w="$(inst_mkcare)"; printf 'not an index\n' > "$w/.git/index"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && l19_has "FAIL [L19] git status failed (rc=" "$out" && ! l19_has "working tree carries only record-set paths" "$out"; then
    echo "BITE  OK  (L19: a failing git status reds, never reads as a clean working tree)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L19 git status failure, rc=$rc)"; echo "$out" | grep -E 'L19|L20' | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  w="$(inst_mkcare)"; inst_pass_says "$w" 'L19 CARE anchor: HEAD = pinned release v1\.1\.0, reachable from origin' "L19/L20: CARE clone at its adopted release, records only"; inst_rm "$w"
  # L19 break-glass (`checks/CARE-EXCEPTION`): a valid ticket turns a tracked edit into a LOUD yellow and says
  # the hatch is open; the same ticket expired reds. Its window arithmetic shares L20's date helper, which a
  # first cut of the migration-mode retirement removed with the migration arm (break round 2026-10-25).
  ce_day(){ date -u -v"$1"d +%F 2>/dev/null || date -u -d "$1 days" +%F 2>/dev/null; }
  ce_t="$(ce_day +0)"; ce_p3="$(ce_day +3)"; ce_m5="$(ce_day -5)"; ce_m1="$(ce_day -1)"
  w="$(inst_mkcare)"; echo x >> "$w/CLAUDE.md"
  printf 'reason: synthetic renderer fault\ndate: %s\nexpires: %s\n' "$ce_t" "$ce_p3" > "$w/checks/CARE-EXCEPTION"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  printf 'reason: synthetic renderer fault\ndate: %s\nexpires: %s\n' "$ce_m5" "$ce_m1" > "$w/checks/CARE-EXCEPTION"
  out2="$(bash "$CHECK" "$w" 2>&1)"; rc2=$?
  if [ -n "$ce_p3" ] && [ "$rc" -eq 0 ] && grep -qF 'L19 EXCEPTION OPEN (LOUD)' <<<"$out" && ! grep -q 'command not found' <<<"$out" \
     && [ "$rc2" -ne 0 ] && grep -qF "FAIL [L19] checks/CARE-EXCEPTION EXPIRED on $ce_m1" <<<"$out2"; then
    echo "BITE  OK  (L19: a valid break-glass ticket opens the hatch on a tracked edit; the same ticket expired reds)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L19 break-glass — valid rc=$rc, expired rc=$rc2)"; { echo "$out"; echo "$out2"; } | sed 's/^/      /' | tail -8; fail=$((fail+1))
  fi; inst_rm "$w"
  # L20: a linked worktree of a CARE checkout reds, and its refusal leads with the care remedy — the
  # client can open care sessions there by default, and "do the work in DEV" alone strands one
  w="$(inst_mkcare)"; inst_git -C "$w" worktree add -q --detach "$w/.claude/worktrees/wt" >/dev/null 2>&1
  out="$(bash "$CHECK" "$w/.claude/worktrees/wt" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'FAIL \[L20\] linked worktree of a CARE instance' <<<"$out" \
     && grep -q 'Record work: stop, and ask the operator to start a new session in the main care folder' <<<"$out"; then
    echo "BITE  OK  (L20: CARE worktree refused, care remedy named)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L20: CARE worktree — expected L20 red naming the care remedy, rc=$rc)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; inst_rm "$w"
  # L20: an unknown marker reds, naming dev | care (an old `migration:` one included, ADR-0050 point 14)
  # — on a records-bearing CARE clone, so a marker read as `care` whenever records exist fails here;
  # the record-free case is the pre-push agreement bite.
  w="$(inst_mkcare)"; echo 'staging' > "$w/.tabularium-instance"
  out="$(bash "$CHECK" "$w" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -qF "FAIL [L20] unknown instance marker 'staging' — expected dev | care" <<<"$out"; then
    echo "BITE  OK  (L20: an unknown marker reds on a records-bearing CARE clone)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L20: unknown marker on a CARE clone — rc=$rc)"; echo "$out" | sed 's/^/      /' | tail -6; fail=$((fail+1))
  fi; inst_rm "$w"
  # L20, DEV: the top-level `_inbox/` left the record set but stays ignored by its root rule
  # (ADR-0030 point 7). Ordinary staging ignores a stray file there and the board stays green;
  # a record-shaped path still reds L20's shape scan. NEGATIVE CONTROL: restoring the old
  # `tooling _inbox/` line in the fixture makes the same record-shaped path go green — the blind
  # spot that line made.
  d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"; mkdir -p "$d/_inbox"; printf 'synthetic scan\n' > "$d/_inbox/scan.pdf"
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  st="$(inst_git -C "$d" status --porcelain -uall 2>/dev/null)"
  if [ "$rc" -eq 0 ] && grep -q 'L20 instance: dev — record-free' <<<"$out" && inst_git -C "$d" check-ignore -q _inbox/scan.pdf \
     && ! grep -qF '_inbox' <<<"$st"; then
    echo "BITE  OK  (L20: a stray _inbox/scan.pdf in DEV is ignored — never staged — and the board stays green)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L20: DEV stray under _inbox/ — rc=$rc, status='$st')"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; rm -rf "$d"
  d="$(inst_mkgit)"; echo dev > "$d/.tabularium-instance"; valid_profile "$d/_inbox/patients/szinbox/profile.md"
  out="$(bash "$CHECK" "$d" 2>&1)"; rc=$?
  printf 'tooling _inbox/\n' >> "$d/checks/RECORD-SET"
  mout="$(bash "$CHECK" "$d" 2>&1)"; mrc=$?
  if [ "$rc" -ne 0 ] && grep -q 'FAIL \[L20\].*_inbox/patients/szinbox/profile.md' <<<"$out" && [ "$mrc" -eq 0 ]; then
    echo "BITE  OK  (L20: a record-shaped path under an ignored DEV _inbox/ still reds; with the old tooling line back it hides — the control)"; pass=$((pass+1))
  else
    echo "BITE  MISS (L20: record-shaped DEV stray under _inbox/ — rc=$rc, with tooling line rc=$mrc)"; { echo "$out"; echo "$mout"; } | sed 's/^/      /' | tail -8; fail=$((fail+1))
  fi; rm -rf "$d"
else
  skip instance-model "git absent — the L19/L20 instance-model bites were NOT run"
fi

# snapshot.sh (the care recovery floor) — a snapshot that reports success having captured nothing is no floor.
# Test: an empty or unrelated directory is not a root; refuse before creating `.snapshots/` (the marker-only
# "success" defect). Control: a real capture of the canonical docs, owner-only, atomically published.
SNAP="$ROOT/checks/snapshot.sh"
snap_root_floor_ok=yes; snap_root_floor_diag=""
for snap_root_shape in empty unrelated; do
  d="$(mktemp -d)"
  [ "$snap_root_shape" = empty ] || printf 'synthetic unrelated file\n' > "$d/notes.txt"
  out="$(bash "$SNAP" "$d" 2>&1)"; rc=$?
  if [ "$rc" -ne 2 ] || ! grep -q 'snapshot refused.*root has no canonical files to capture' <<<"$out" \
     || [ -e "$d/.snapshots" ]; then
    snap_root_floor_ok=no; snap_root_floor_diag="$snap_root_floor_diag $snap_root_shape(rc=$rc)"
  fi
  rm -rf "$d"
done
if [ "$snap_root_floor_ok" = yes ]; then
  echo "SNAP  OK  (empty/wrong roots refuse before recovery data is touched)"; pass=$((pass+1))
else
  echo "SNAP  MISS (empty/wrong root floor:$snap_root_floor_diag)"; fail=$((fail+1))
fi
d="$(mktemp -d)"; valid_profile "$d/patients/sztsnap/profile.md"
# the UNTRACKED publish firewall script must be banked too (its only pre-edit recovery path)
mkdir -p "$d/checks"; printf '# synthetic firewall fixture (selftest SNAP)\n' > "$d/checks/publish-skeleton.sh"
out="$( (umask 000; bash "$SNAP" "$d") 2>&1)"; rc=$?
snap_bad="$(find "$d/.snapshots" \( -type d ! -perm 700 -o -type f ! -perm 600 \) -print 2>/dev/null)"
if [ "$rc" -eq 0 ] && find "$d/.snapshots" -path '*patients/sztsnap/profile.md' 2>/dev/null | grep -q . \
   && find "$d/.snapshots" -path '*checks/publish-skeleton.sh' 2>/dev/null | grep -q . \
   && find "$d/.snapshots" -mindepth 2 -maxdepth 2 -name '.snapshot-complete' -type f -print 2>/dev/null | grep -q . \
   && [ -z "$snap_bad" ] \
   && [ -z "$(find "$d/.snapshots" \( -name '*.part.*' -o -name '*.lock' \) -print 2>/dev/null)" ]; then
  echo "SNAP  OK  (atomic capture of canonical docs + firewall with private permissions)"; pass=$((pass+1))
else
  echo "SNAP  MISS (snapshot floor, incl. firewall banking): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
fi; rm -rf "$d"
# The copies are flushed to disk before publication, and the publication before the result line. Stub `sync`
# and `perl` (on a Mac with perl, passing through to the real one, which runs the per-file full flush) go first
# on PATH and log what they were given and what `.snapshots/` held: the first `sync` must already see the copied
# profile and the completion marker in private staging and no published snapshot, the second the published one
# and no staging; on such a Mac each staged file and the snapshot folder are flushed before the first, the
# folder again before the second; elsewhere perl is not used.
d="$(mktemp -d)"; sy="$(mktemp -d)"; valid_profile "$d/patients/sztsync/profile.md"
printf '#!/bin/sh\necho stub-sync\n{ echo call; find .snapshots -print | sed "s/^/seen /"; } >> "%s/log"\n' "$sy" > "$sy/sync"; chmod +x "$sy/sync"
sy_perl=""; [ "$(uname -s)" = Darwin ] && { sy_perl="$(command -v perl 2>/dev/null)" || sy_perl=""; }
if [ -n "$sy_perl" ]; then
  printf '#!/bin/sh\n{ echo perl; for a in "$@"; do printf "arg %%s\\n" "$a"; done; } >> "%s/log"\nexec "%s" "$@"\n' "$sy" "$sy_perl" > "$sy/perl"
elif [ "$(uname -s)" != Darwin ]; then
  printf '#!/bin/sh\necho perl >> "%s/log"\n' "$sy" > "$sy/perl"
fi
[ ! -f "$sy/perl" ] || chmod +x "$sy/perl"
out="$(PATH="$sy:$PATH" bash "$SNAP" "$d" 2>&1)"; rc=$?
sy_calls="$(grep -c '^call$' "$sy/log" 2>/dev/null)"
sy_sec(){ awk -v want="$1" '/^call$/{n++; next} n==want' "$sy/log" 2>/dev/null; }
sy0="$(sy_sec 0)"; sy1="$(sy_sec 1)"; sy2="$(sy_sec 2)"
sy_part='\.snapshots/\.[0-9]\{8\}T[0-9]\{6\}Z\.part\.[0-9]*'; sy_pub='\.snapshots/[0-9]\{8\}T[0-9]\{6\}Z'
sy_bad=""
[ "$rc" -eq 0 ] && [ "${sy_calls:-0}" -eq 2 ] || sy_bad="$sy_bad rc=$rc,calls=${sy_calls:-0}"
grep -q "^seen $sy_part/\.snapshot-complete\$" <<<"$sy1" && grep -q "^seen $sy_part/patients/sztsync/profile\.md\$" <<<"$sy1" \
  && ! grep -q "^seen $sy_pub" <<<"$sy1" || sy_bad="$sy_bad first-flush-before-copies-staged"
grep -q "^seen $sy_pub/\.snapshot-complete\$" <<<"$sy2" && ! grep -q '\.part\.' <<<"$sy2" || sy_bad="$sy_bad second-flush-before-publication"
[ "$(grep -c '^stub-sync$' <<<"$out")" -eq 2 ] && tail -n 1 <<<"$out" | grep -q '^snapshot -> ' || sy_bad="$sy_bad result-line-before-flush"
if [ -n "$sy_perl" ]; then
  { grep -q "^arg $sy_part/\.snapshot-complete\$" <<<"$sy0" && grep -q "^arg $sy_part/patients/sztsync/profile\.md\$" <<<"$sy0" \
    && grep -qx 'arg .snapshots' <<<"$sy0" && grep -qx 'arg .snapshots' <<<"$sy1"; } || sy_bad="$sy_bad mac-full-flush-missing"
else
  ! grep -qx perl "$sy/log" || sy_bad="$sy_bad perl-used-where-not-expected"
fi
# The flush is best effort and never refuses a snapshot (a folder some mounts cannot flush, a drive that refuses
# the full flush): with `sync` and `perl` both failing, every platform still leaves a complete, published snapshot,
# both `sync` calls made.
d2="$(mktemp -d)"; sy2="$(mktemp -d)"; valid_profile "$d2/patients/sztsync/profile.md"
printf '#!/bin/sh\nexit 1\n' > "$sy2/perl"; printf '#!/bin/sh\necho call >> "%s/log"\nexit 1\n' "$sy2" > "$sy2/sync"
chmod +x "$sy2/perl" "$sy2/sync"
out2="$(PATH="$sy2:$PATH" bash "$SNAP" "$d2" 2>&1)"; rc2=$?
[ "$rc2" -eq 0 ] && [ "$(grep -c '^call$' "$sy2/log" 2>/dev/null)" = 2 ] && tail -n 1 <<<"$out2" | grep -q '^snapshot -> ' \
  && find "$d2/.snapshots" -mindepth 2 -maxdepth 2 -name .snapshot-complete -print 2>/dev/null | grep -q . \
  && [ -z "$(find "$d2/.snapshots" \( -name '*.part.*' -o -name '*.lock' \) -print 2>/dev/null)" ] || sy_bad="$sy_bad failed-flush-refused-snapshot(rc=$rc2)"
rm -rf "$d2" "$sy2"
if [ -z "$sy_bad" ]; then
  echo "SNAP  OK  (copies and completion marker flushed before publication, the publication before the result line$([ -n "$sy_perl" ] && echo '; each file through the full flush on this Mac'); a failing flush still leaves a complete snapshot)"; pass=$((pass+1))
else
  echo "SNAP  MISS (snapshot flush:$sy_bad)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
fi; rm -rf "$d" "$sy"
# The files kept outside the tree: a folder this shell cannot see (a chat's VM with only the care folder
# mounted) copies the records with a note; a file gone from a folder that exists still refuses; a present
# file is banked under external/.
snap_ext_ok=yes; snap_ext_diag=""
for snap_ext_case in hidden lost present; do
  d="$(mktemp -d)"; e="$(mktemp -d)"; valid_profile "$d/patients/sztsnapx/profile.md"; mkdir -p "$d/checks"
  case "$snap_ext_case" in
    hidden)  printf '%s\n' "$e/not-mounted/registry.sh" > "$d/checks/FIREWALL-REGISTRY"
             printf '%s\n' "$e/not-mounted/id.sh" > "$d/checks/PRIVATE-MODE-ID" ;;
    lost)    printf '%s\n' "$e/registry.sh" > "$d/checks/FIREWALL-REGISTRY" ;;
    present) printf '# synthetic registry (selftest SNAP)\n' > "$e/registry.sh"
             printf '%s\n' "$e/registry.sh" > "$d/checks/FIREWALL-REGISTRY" ;;
  esac
  out="$(bash "$SNAP" "$d" 2>&1)"; rc=$?
  case "$snap_ext_case" in
    hidden)  [ "$rc" -eq 0 ] && [ "$(grep -c "folder is not visible from this shell" <<<"$out")" -eq 2 ] \
               && tail -n 1 <<<"$out" | grep -q '^snapshot -> ' \
               && find "$d/.snapshots" -path '*patients/sztsnapx/profile.md' | grep -q . \
               && [ -z "$(find "$d/.snapshots" -name external -print)" ] || snap_ext_ok=no ;;
    lost)    [ "$rc" -eq 2 ] && grep -q 'refusing an incomplete recovery point' <<<"$out" \
               && [ -z "$(find "$d/.snapshots" -mindepth 1 -maxdepth 1 ! -name '.*' -print 2>/dev/null)" ] || snap_ext_ok=no ;;
    present) [ "$rc" -eq 0 ] && ! grep -q '^note:' <<<"$out" \
               && find "$d/.snapshots" -path '*external/firewall-registry.sh' | grep -q . || snap_ext_ok=no ;;
  esac
  [ "$snap_ext_ok" = yes ] || { snap_ext_diag="$snap_ext_diag $snap_ext_case(rc=$rc)"; snap_ext_ok=yes; snap_ext_bad=1; }
  rm -rf "$d" "$e"
done
if [ -z "${snap_ext_bad:-}" ]; then
  echo "SNAP  OK  (outside files: an unseen folder copies the records with a note; a lost file refuses; a present one is banked)"; pass=$((pass+1))
else
  echo "SNAP  MISS (outside files:$snap_ext_diag)"; fail=$((fail+1))
fi

# snapshot.sh refuses an unknown marker before touching anything (an old `migration:` one included, ADR-0050
# point 14); the same root marked `care` captures.
snap_mk(){ local d; d="$(mktemp -d)"; valid_profile "$d/patients/sztsnapm/profile.md"; printf '%s\n' "$1" > "$d/.tabularium-instance"; echo "$d"; }
d="$(snap_mk staging)"; out="$(bash "$SNAP" "$d" 2>&1)"; rc=$?
[ "$rc" -eq 2 ] && grep -qF 'the instance marker has an unsupported value' <<<"$out" && [ ! -e "$d/.snapshots" ]; snap_m=$?
rm -rf "$d"
d="$(snap_mk care)"; out="$(bash "$SNAP" "$d" 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && find "$d/.snapshots" -mindepth 2 -maxdepth 2 -name '.snapshot-complete' -type f 2>/dev/null | grep -q .; snap_c=$?
rm -rf "$d"
# and on a git main checkout, where the instance lookup runs first and must not let the marker through
d="$(snap_mk staging)"; env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$d" init -q >/dev/null 2>&1
: > "$d/CLAUDE.md"; mkdir -p "$d/checks"
out="$(bash "$SNAP" "$d" 2>&1)"; rc=$?
[ "$rc" -eq 2 ] && grep -qF 'the instance marker has an unsupported value' <<<"$out" && [ ! -e "$d/.snapshots" ]; snap_g=$?
rm -rf "$d"
if [ "$snap_m" -eq 0 ] && [ "$snap_c" -eq 0 ] && [ "$snap_g" -eq 0 ]; then
  echo "SNAP  OK  (an unknown marker is refused before anything is written, plain or git; its care twin captures)"; pass=$((pass+1))
else
  echo "SNAP  MISS (unknown marker — refused=$snap_m git-root=$snap_g care-twin=$snap_c; 0 = as expected)"; fail=$((fail+1))
fi

# backup-tree.sh — backup LAYER 2 is the SOLE backup of med/sources/, so a silently broken generator is a
# silent loss of the only raw-scan backup. Test: a scan under a NESTED dir literally named 'outputs/' must
# be captured (`tar . --exclude=./outputs` drops it at any depth — the generator must SELECT root members)
# while the TOP-LEVEL outputs/ stays out (no self-swallow of a prior tarball), archive mode 0600. Control:
# a plain tree backs up complete. Here-strings, not `tar | grep -q` (pipefail + SIGPIPE false negative).
BTREE="$ROOT/checks/backup-tree.sh"
d="$(mktemp -d)"; : > "$d/CLAUDE.md"
mkdir -p "$d/patients/sztbak/med/sources/outputs" "$d/outputs/_snapshots"
echo scan   > "$d/patients/sztbak/med/sources/2026-01-01__lab__x.pdf"
echo nested > "$d/patients/sztbak/med/sources/outputs/2026-01-01__lab__nested.pdf"   # nested 'outputs' dir — MUST be kept
echo prior  > "$d/outputs/_snapshots/PRIOR__worktree.tgz"                            # top-level outputs/ — MUST be excluded
out="$( (umask 000; bash "$BTREE" "$d") 2>&1)"; rc=$?
tb="$(ls -1 "$d"/outputs/_snapshots/*__worktree.tgz 2>/dev/null | grep -v PRIOR | head -1)"
members=""; [ -n "$tb" ] && members="$(tar tzf "$tb" 2>/dev/null)"
if [ "$rc" -eq 0 ] && [ -n "$tb" ] \
   && [ -z "$(find "$d/outputs/_snapshots" -type d ! -perm 700 -print 2>/dev/null)" ] \
   && [ -n "$(find "$tb" -type f -perm 600 -print 2>/dev/null)" ] \
   && [ -z "$(find "$d/outputs/_snapshots" -name '*.part.*' -print 2>/dev/null)" ] \
   && grep -q 'patients/sztbak/med/sources/2026-01-01__lab__x.pdf' <<<"$members" \
   && grep -q 'patients/sztbak/med/sources/outputs/2026-01-01__lab__nested.pdf' <<<"$members" \
   && ! grep -q 'PRIOR__worktree.tgz' <<<"$members"; then
  echo "BKUP  OK  (captures all source paths, excludes root outputs, archive mode 0600)"; pass=$((pass+1))
else
  echo "BKUP  MISS (backup-tree.sh): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
fi; rm -rf "$d"
d="$(mktemp -d)"; : > "$d/CLAUDE.md"; mkdir -p "$d/patients/sztplain/med/sources"
echo scan > "$d/patients/sztplain/med/sources/2026-01-01__lab__x.pdf"
out="$( (umask 000; bash "$BTREE" "$d") 2>&1)"; rc=$?
tb="$(ls -1 "$d"/outputs/_snapshots/*__worktree.tgz 2>/dev/null | head -1)"
members=""; [ -n "$tb" ] && members="$(tar tzf "$tb" 2>/dev/null)"
if [ "$rc" -eq 0 ] && [ -n "$tb" ] && [ -n "$(find "$tb" -type f -perm 600 -print 2>/dev/null)" ] \
   && grep -q 'patients/sztplain/med/sources/2026-01-01__lab__x.pdf' <<<"$members"; then
  echo "BKUP  OK  (control: a plain tree with no nested outputs/ backs up complete, archive mode 0600)"; pass=$((pass+1))
else
  echo "BKUP  MISS (backup-tree.sh plain tree): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
fi; rm -rf "$d"

# backup-offsite.sh (backup layer 3) — its failure mode is unique: writing to a path that LOOKS like the synced
# folder but is not (client logged out, not mounted) yields a complete, verified, entirely local copy and
# reports success. Test: an unmarked destination refuses. Control: a marked destination mirrors and verifies.
# Extras: a mirror missing bytes is indeterminate, not a backup; completeness is judged file by file, never by
# count; --verify-only writes nothing; a destination that resolves into the repository refuses; and the mirror
# is append-only (no --delete).
OFFSITE="$ROOT/checks/backup-offsite.sh"
if [ ! -x "$OFFSITE" ]; then
  echo "BITE  MISS (offsite: checks/backup-offsite.sh missing or not executable)"; fail=$((fail+1))
else
  off_ok(){   echo "BITE  OK  (offsite: $1)"; pass=$((pass+1)); }
  off_miss(){ echo "BITE  MISS (offsite: $1, rc=$rc)"; printf '%s\n' "$out" | sed 's/^/      /'; fail=$((fail+1)); }
  # every destination sits in a stand-in home's cloud-app area, as a synced folder does on a Mac: a plain folder on the
  # records' own disk is refused (ADR-0067), which the bite after the first mirror proves
  OFF_HOME="$(mktemp -d)"; mkdir -p "$OFF_HOME/Library/CloudStorage"
  off_dest(){ mktemp -d "$OFF_HOME/Library/CloudStorage/sync.XXXXXX"; }
  # a synthetic data root with NO med/sources (a sources dir without a MANIFEST is L13's red, not this script's);
  # one name carries a Polish letter, written composed (NFC) as the local tree holds it
  OFF_NFC="$(printf 'za\305\274.md')"; OFF_NFD="$(printf 'zaz\314\207.md')"   # one name, two Unicode forms
  off_root(){ : > "$1/CLAUDE.md"; mkdir -p "$1/patients/example/nmed" "$1/_shared/nmed"
    printf '# Profile — Example\n_synthetic fixture; no real person._\n' > "$1/patients/example/profile.md"
    printf 'synthetic\n' > "$1/patients/example/nmed/note.md"
    printf 'synthetic\n' > "$1/patients/example/nmed/$OFF_NFC"
    printf 'synthetic\n' > "$1/_shared/nmed/note.md"; }
  od="$(mktemp -d)"; off_root "$od"
  odest="$(off_dest)"; om="$odest/tabularium"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" "$od" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'not a confirmed offsite target' <<<"$out"; then
    off_ok "unmarked destination refuses — unmounted-provider case"
  else off_miss "unmarked destination was accepted"; fi
  : > "$odest/.tabularium-offsite-ok"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" "$od" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ -f "$om/patients/example/profile.md" ] && grep -q 'offsite mirror OK' <<<"$out"; then
    off_ok "marked destination mirrors and verifies"
  else off_miss "clean mirror did not succeed"; fi
  if [ -f "$om/.tabularium-last-backup" ]; then off_ok "a verified copy records when it was taken"
  else rc=-; off_miss "a verified copy left no record of its time"; fi
  # off this Mac's disk (ADR-0067): the marker says "this folder, on purpose", not "off this disk". A marked folder on
  # the records' own disk outside the cloud-app area is refused before anything is written; one in iCloud Drive's is not
  ops="$(mktemp -d)"; : > "$ops/.tabularium-offsite-ok"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ops" "$OFFSITE" "$od" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -q "on this Mac's own disk" <<<"$out" && [ ! -e "$ops/tabularium" ]; then
    off_ok "a marked folder beside the records, outside the cloud-app area, is refused, nothing written"
  else off_miss "a folder on the records' own disk was used"; fi
  rm -rf "$ops"
  oic="$OFF_HOME/Library/Mobile Documents/com~apple~CloudDocs/backup"; mkdir -p "$oic"; : > "$oic/.tabularium-offsite-ok"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$oic" "$OFFSITE" "$od" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q 'offsite mirror OK' <<<"$out"; then off_ok "a folder in iCloud Drive's area mirrors and verifies"
  else off_miss "a folder in iCloud Drive's area was refused"; fi
  # --verify-only reads and never writes: a marked destination with no mirror yet (a first run, or a provider
  # folder not hydrated locally) is reported as such, and the destination is left exactly as it was
  odv="$(off_dest)"; : > "$odv/.tabularium-offsite-ok"; before="$(find "$odv" -print)"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odv" "$OFFSITE" --verify-only "$od" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'no mirror to verify' <<<"$out" && [ "$(find "$odv" -print)" = "$before" ]; then
    off_ok "--verify-only with no mirror reports it and writes nothing"
  else off_miss "--verify-only changed the destination or did not report the missing mirror"; fi
  rm -rf "$odv"
  # a provider may hand a name back decomposed (NFD): the same file to a person, other bytes to a string
  # compare. A per-file check that false-fails it fails a good backup (the backup-tree.sh lesson).
  rm -f "$om/patients/example/nmed/$OFF_NFC"; printf 'synthetic\n' > "$om/patients/example/nmed/$OFF_NFD"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" --verify-only "$od" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q 'offsite VERIFY OK' <<<"$out"; then
    off_ok "a name the provider stored decomposed (NFD) still counts as present"
  else off_miss "a Unicode-normalized name failed a complete mirror"; fi
  # … but two LOCAL names that differ only in Unicode form are one name to that comparison, so a mirror holding
  # either would count for both: the check refuses them (a Linux file system holds both; macOS cannot)
  oc="$(mktemp -d)"; off_root "$oc"; printf 'synthetic\n' > "$oc/patients/example/nmed/$OFF_NFD"
  if [ "$(ls -1 "$oc/patients/example/nmed" | wc -l | tr -d '[:space:]')" -eq 3 ]; then
    ocd="$(off_dest)"; : > "$ocd/.tabularium-offsite-ok"
    out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ocd" "$OFFSITE" "$oc" 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ] && grep -q 'differ from another only in Unicode form' <<<"$out"; then
      off_ok "two local names that differ only in Unicode form refuse"
    else off_miss "two local names that differ only in Unicode form were both counted present"; fi
    rm -rf "$ocd"
  else
    skip offsite-nfc-collision "this file system cannot hold two names that differ only in Unicode form — the collision bite runs on Linux"
  fi
  rm -rf "$oc"
  # genuinely absent mirror bytes: the local observation cannot tell a lost file from an unhydrated one,
  # so the safe answer is "indeterminate", never a green
  rm -f "$om/_shared/nmed/note.md"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" --verify-only "$od" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'verification is INDETERMINATE' <<<"$out" \
     && grep -q 'not hydrated locally' <<<"$out" && grep -q 'remote data may be missing' <<<"$out"; then
    off_ok "genuinely missing mirror bytes also refuse as indeterminate"
  else off_miss "genuinely missing mirror bytes were not indeterminate"; fi
  # per file, not by count: an old name the append-only mirror kept (a local rename) brings the count back up,
  # and the mirror is still one file short
  printf 'synthetic\n' > "$om/patients/example/nmed/old-name.md"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" --verify-only "$od" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'lacks 1 of 4 local files' <<<"$out" && grep -q 'verification is INDETERMINATE' <<<"$out"; then
    off_ok "the right number of files with one missing still refuses"
  else off_miss "a stale extra file hid a missing one"; fi
  # control: a copy run restores the missing file and keeps the extra (append-only); that mirror verifies
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" "$od" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q 'offsite mirror OK' <<<"$out" && [ -f "$om/_shared/nmed/note.md" ] \
     && [ -f "$om/patients/example/nmed/old-name.md" ]; then
    off_ok "a complete mirror that also keeps an old file verifies"
  else off_miss "a complete mirror holding an extra file did not verify"; fi
  # a file edited locally since the last run: same names, same count, another size — out of date, never green
  printf 'edited\n' >> "$od/patients/example/nmed/note.md"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$odest" "$OFFSITE" --verify-only "$od" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q '1 of 4 local files have a different size in the mirror' <<<"$out"; then
    off_ok "a mirror file whose size differs from the local one refuses"
  else off_miss "a mirror holding an out-of-date file passed"; fi
  rm -rf "$od" "$odest"
  # containment is judged on where a path RESOLVES: a marked destination reached through a symlinked component
  # that lands inside the repository, or on a folder holding it, refuses before anything is written; one whose
  # symlink lands outside still mirrors and verifies
  ob="$(mktemp -d)"; mkdir -p "$ob/box/repo/inner"; off_root "$ob/box/repo"
  : > "$ob/box/repo/inner/.tabularium-offsite-ok"; : > "$ob/box/.tabularium-offsite-ok"
  oo="$(off_dest)"; mkdir -p "$oo/inner"; : > "$oo/inner/.tabularium-offsite-ok"
  ol="$(mktemp -d)"; ln -s "$ob/box/repo" "$ol/in"; ln -s "$ob" "$ol/up"; ln -s "$oo" "$ol/out"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ol/in/inner" "$OFFSITE" "$ob/box/repo" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'offsite destination is inside the repository' <<<"$out" \
     && [ ! -e "$ob/box/repo/inner/tabularium" ]; then
    off_ok "a destination resolving inside the repository through a symlink refuses, nothing written"
  else off_miss "a destination resolving inside the repository was used"; fi
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ol/up/box" "$OFFSITE" "$ob/box/repo" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'repository is inside the offsite destination' <<<"$out" \
     && [ ! -e "$ob/box/tabularium" ]; then
    off_ok "a destination resolving onto a folder that holds the repository refuses, nothing written"
  else off_miss "a destination resolving onto a folder that holds the repository was used"; fi
  out1="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ol/out/inner" "$OFFSITE" "$ob/box/repo" 2>&1)"; rc=$?
  out2="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ol/out/inner" "$OFFSITE" --verify-only "$ob/box/repo" 2>&1)"; rc2=$?
  out="$out1
$out2"
  if [ "$rc" -eq 0 ] && [ "$rc2" -eq 0 ] && grep -q 'offsite mirror OK' <<<"$out1" \
     && grep -q 'offsite VERIFY OK' <<<"$out2" && [ -f "$oo/inner/tabularium/patients/example/profile.md" ]; then
    off_ok "a destination reached through a symlink that resolves outside the repository mirrors and verifies"
  else off_miss "a destination resolving outside the repository did not mirror and verify (verify rc=$rc2)"; fi
  rm -rf "$ol" "$ob" "$oo"
  # recorded renames: the append-only mirror keeps the old names of a source and of its transcription (which
  # still names the first original); its ownership check counts them and any other extra file, never failing on
  # one, so each backup after a rename stays green; a current file missing, or changed at the same size, refuses
  orn="$(mktemp -d)"; : > "$orn/CLAUDE.md"; valid_profile "$orn/patients/sztren/profile.md"
  ors="$orn/patients/sztren/med/sources"; mkdir -p "$ors"; echo scan > "$ors/2026-01-01__lab__a.pdf"
  printf 'filed_as: 2026-01-01__lab__a.pdf\n\n# t\n' > "$ors/2026-01-01__lab__a.ocr.md"; mk_ownership "$orn"
  ornd="$(off_dest)"; : > "$ornd/.tabularium-offsite-ok"; orm="$ornd/tabularium/patients/sztren/med/sources"
  # each run dates the tree anew: rsync skips a same-size file whose time is unchanged, and a rename rewrites
  # the checkpoint at its old size, within the same second in a fixture
  orn_backup(){ find "$orn/patients" -type f -exec touch -t "$1" {} +; HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ornd" "$OFFSITE" "$orn" 2>&1; }
  orn_rename(){ mv "$ors/$1.pdf" "$ors/$2.pdf" && mv "$ors/$1.ocr.md" "$ors/$2.ocr.md" \
    && PYTHONPATH="$ROOT" python3 -m tools.person_ownership --root "$orn" append sztren rename \
         --from "med/sources/$1.pdf" --to "med/sources/$2.pdf" >/dev/null 2>&1; }
  out1="$(orn_backup 202601010000)"; rc1=$?
  orn_rename 2026-01-01__lab__a 2026-01-01__lab__b; rc2=$?
  out2="$(orn_backup 202601020000)"; rc3=$?
  orn_rename 2026-01-01__lab__b 2026-01-01__lab__c; rc4=$?
  out3="$(orn_backup 202601030000)"; rc=$?
  out="$out1
$out2
$out3"
  if [ "$rc1$rc2$rc3$rc4$rc" = 00000 ] && grep -q 'offsite mirror OK' <<<"$out2" && grep -q 'offsite mirror OK' <<<"$out3" \
     && [ -f "$orm/2026-01-01__lab__a.pdf" ] && [ -f "$orm/2026-01-01__lab__a.ocr.md" ] \
     && [ -f "$orm/2026-01-01__lab__b.pdf" ] && [ -f "$orm/2026-01-01__lab__b.ocr.md" ] \
     && [ -f "$orm/2026-01-01__lab__c.ocr.md" ] && grep -q ' 4 file(s) no current record binds' <<<"$out3"; then
    off_ok "backups after two recorded renames keep the old copies, count them and verify"
  else off_miss "a backup after a recorded rename did not verify (rc: backup $rc1, rename $rc2, backup $rc3, rename $rc4)"; fi
  echo scan > "$orm/2026-03-03__lab__stray.pdf"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ornd" "$OFFSITE" --verify-only "$orn" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q ' 5 file(s) no current record binds' <<<"$out"; then
    off_ok "an extra file in the mirror is counted, not failed"
  else off_miss "an extra file in the mirror failed it, or was not counted"; fi
  rm -f "$orm/2026-01-01__lab__c.pdf"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ornd" "$OFFSITE" --verify-only "$orn" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'lacks 1 of' <<<"$out"; then
    off_ok "a current source missing from the mirror refuses"
  else off_miss "a mirror missing a current source passed"; fi
  echo SCAN > "$orm/2026-01-01__lab__c.pdf"
  out="$(HOME="$OFF_HOME" TABULARIUM_OFFSITE_DEST="$ornd" "$OFFSITE" --verify-only "$orn" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q 'source bytes do not match recorded sha256 (drift)' <<<"$out"; then
    off_ok "a same-size change to a current source in the mirror refuses"
  else off_miss "a drifted current source in the mirror passed"; fi
  rm -rf "$orn" "$ornd"
  # APPEND-ONLY, statically: an rsync --delete would forward a local accident to the one copy meant to
  # outlive it, and no runtime bite can observe the absence of a future deletion. Anchored on the command.
  if grep -q '^[[:space:]]*rsync -rlt -- ' "$OFFSITE" && ! grep -qE '^[[:space:]]*rsync .*--delete' "$OFFSITE"; then
    echo "BITE  OK  (offsite: mirror is append-only — no --delete in the rsync invocation)"; pass=$((pass+1))
  else
    echo "BITE  MISS (offsite: rsync invocation changed — append-only property not provable)"; fail=$((fail+1))
  fi
  # the snapshot refreshes the off-Mac copy at the pace the operator chose (ADR-0067): none chosen, never; `every session`,
  # each snapshot; `every week`, once the last verified copy is a week old. A copy that cannot run costs the snapshot one
  # note, never its result. One root per case: two snapshots of one root in the same second collide by design.
  osnap(){ # $1 = pace line (or empty) · $2 = mark the destination (yes/no) · $3 = age of a prior copy's stamp (none/new/old)
    osr="$(mktemp -d)"; off_root "$osr"; mkdir -p "$osr/checks"; osd="$(off_dest)"
    [ "$2" = yes ] && : > "$osd/.tabularium-offsite-ok"
    if [ -n "$1" ]; then printf '%s\n%s\n' "$osd" "$1" > "$osr/checks/OFFSITE-DEST"; else printf '%s\n' "$osd" > "$osr/checks/OFFSITE-DEST"; fi
    case "$3" in new) mkdir -p "$osd/tabularium"; : > "$osd/tabularium/.tabularium-last-backup" ;;
      old) mkdir -p "$osd/tabularium"; : > "$osd/tabularium/.tabularium-last-backup"; touch -t 202601010000 "$osd/tabularium/.tabularium-last-backup" ;; esac
    out="$(HOME="$OFF_HOME" bash "$SNAP" "$osr" 2>&1)"; rc=$?; }
  osnap_done(){ rm -rf "$osr" "$osd"; }
  osnap '' yes none
  if [ "$rc" -eq 0 ] && ! grep -q 'off-Mac backup' <<<"$out" && [ ! -e "$osd/tabularium" ]; then off_ok "with no pace chosen, a snapshot leaves the off-Mac copy alone"
  else off_miss "a snapshot ran the off-Mac copy with no pace chosen"; fi
  osnap_done; osnap 'every session' yes none
  if [ "$rc" -eq 0 ] && grep -qxF 'off-Mac backup refreshed (every session)' <<<"$out" && [ -f "$osd/tabularium/patients/example/profile.md" ] \
     && [ "$(printf '%s\n' "$out" | tail -n 1 | cut -c1-11)" = 'snapshot ->' ]; then off_ok "every session: a snapshot refreshes the off-Mac copy, its own result line still last"
  else off_miss "every session: the snapshot did not refresh the off-Mac copy"; fi
  osnap_done; osnap 'every week' yes new
  if [ "$rc" -eq 0 ] && ! grep -q 'off-Mac backup' <<<"$out" && [ ! -e "$osd/tabularium/patients" ]; then off_ok "every week: a copy under a week old is left alone"
  else off_miss "every week: a fresh copy was refreshed again"; fi
  osnap_done; osnap 'every week' yes old
  if [ "$rc" -eq 0 ] && grep -qxF 'off-Mac backup refreshed (every week)' <<<"$out" && [ -f "$osd/tabularium/patients/example/profile.md" ]; then
    off_ok "every week: a copy a week old or more is refreshed"
  else off_miss "every week: an old copy was not refreshed"; fi
  osnap_done; osnap 'every session' no none
  if [ "$rc" -eq 0 ] && grep -qF 'note: the off-Mac backup did not refresh (every session): destination is not a confirmed offsite target' <<<"$out" \
     && [ "$(printf '%s\n' "$out" | tail -n 1 | cut -c1-11)" = 'snapshot ->' ] && [ -d "$osr/.snapshots" ]; then
    off_ok "a destination that is not there costs the snapshot one note, not its result"
  else off_miss "an absent destination broke the snapshot or went unreported"; fi
  osnap_done
  rm -rf "$OFF_HOME"
fi

# relay-scan.sh — the CARE→DEV relay gate: incidents cross as abstract prose, and this proves the prose carries
# no personal detail — identity and the private-mode lines (ADR-0072). Everything runs against a SYNTHETIC registry the fixture writes for
# itself (mode 0600, opaque `zqx…` tokens — never an ordinary word, which could collide with a live class)
# through the fixture's OWN checks/FIREWALL-REGISTRY; the real registry is never read, copied or pointed at.
RSCAN="$ROOT/checks/relay-scan.sh"
if [ ! -x "$RSCAN" ]; then
  echo "BITE  MISS (relay: checks/relay-scan.sh is missing or not executable)"; fail=$((fail+1))
else
  rs_ok(){   echo "BITE  OK  ($1)"; pass=$((pass+1)); }
  rs_miss(){ echo "BITE  MISS ($1)"; fail=$((fail+1)); }
  # a fixture: its own 0600 registry, its own config naming it, the private-mode identifier's own file (a
  # sixth class) and its own copy of the scanner (the config resolves from $0's directory)
  rs_mk(){ local d; d="$(mktemp -d)"; mkdir -p "$d/checks"
    {
      echo '# SYNTHETIC relay-scan registry (selftest) — no real token anywhere.'
      echo "PII_IDENTITY='zqx1aa'"
      echo "PII_CASEREF='zqx2bb'"   # a leftover line of the retired case-reference class: ignored
      echo "PII_CLINICAL='zqx3cc'"
      echo "PII_BRAND='zqx4dd'"
      echo "PII_CONSENT='zqx5ee'"
    } > "$d/checks/registry.sh"
    chmod 600 "$d/checks/registry.sh"
    printf '%s\n' "$d/checks/registry.sh" > "$d/checks/FIREWALL-REGISTRY"
    printf "PII_PRIVATE_MODE_ID='zqx9zz'\n" > "$d/checks/private-mode-id.sh"
    chmod 600 "$d/checks/private-mode-id.sh"
    printf '%s\n' "$d/checks/private-mode-id.sh" > "$d/checks/PRIVATE-MODE-ID"
    cp "$RSCAN" "$d/checks/relay-scan.sh"; chmod +x "$d/checks/relay-scan.sh"; cp "$ROOT/checks/config-paths.sh" "$d/checks/"
    printf '%s\n' "$d"; }
  rs_reg(){ printf '%s\n' "$1/checks/registry.sh"; }

  # test: a planted token reds with the right class and a file:line locator, token text NOWHERE in the output
  # (a scan that echoed the match would be the leak it exists to stop)
  d="$(rs_mk)"
  printf 'first line is clean\nsecond line carries zqx1aa inline\nthird line is clean\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] && grep -q "^PII_IDENTITY .*/relay\.md:2\$" <<<"$out" && ! grep -qF 'zqx1aa' <<<"$out"; then
    rs_ok "relay: a planted PII_IDENTITY token reds with a locator only (token text withheld)"
  else
    rs_miss "relay: PII_IDENTITY (rc=$rc, locator=$(grep -c '^PII_IDENTITY ' <<<"$out"), token-leak=$(grep -cF 'zqx1aa' <<<"$out"))"
  fi; rm -rf "$d"
  # control: abstract prose scans clean and says what it covered
  d="$(rs_mk)"; printf 'A guard self-skipped where the untracked script is absent.\nWrite it up abstractly.\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -qF 'relay-scan: clean (1 files, 2 classes)' <<<"$out"; then
    rs_ok "relay: abstract prose scans clean and says what it covered"
  else
    rs_miss "relay: clean prose did not pass (rc=$rc)"
  fi; rm -rf "$d"
  # scope (ADR-0072): real case dates are not kept on the registry, so a leftover case-reference line — in
  # the registry or as a kept-details line — is ignored and deleting it changes nothing; tokens of the clinical, brand
  # and consent classes — words that on their own fit anybody — scan clean; a kept-details line of any
  # other class still reds; and a fifth or renamed registry class blinds the scan until it is ruled in or out
  d="$(rs_mk)"; printf "PII_PRIVATE_CASEREF='zqx7qq'\n" >> "$d/checks/private-mode-id.sh"; printf 'clean\nthe case date zqx2bb\nzqx7qq\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -qF 'relay-scan: clean (1 files, 2 classes)' <<<"$out"; then
    rs_ok "relay: a leftover case-reference line (registry and kept-details) neither blinds nor matches"
  else
    rs_miss "relay: a leftover case-reference line blinded or matched (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; sed -i.bak '/^PII_CASEREF=/d' "$(rs_reg "$d")"; rm -f "$(rs_reg "$d").bak"; printf 'clean\nzqx1aa\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] && grep -q "^PII_IDENTITY .*/relay\.md:2\$" <<<"$out" && ! grep -q 'BLINDED' <<<"$out"; then
    rs_ok "relay: with the case-reference line deleted the scan still runs and reds on identity"
  else
    rs_miss "relay: a registry without the case-reference line did not scan (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; printf 'zqx3cc\nzqx4dd\nzqx5ee\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -qF 'relay-scan: clean (1 files, 2 classes)' <<<"$out"; then
    rs_ok "relay: clinical, brand and consent tokens are not matched at the relay"
  else
    rs_miss "relay: a clinical, brand or consent token was matched (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; printf "PII_PRIVATE_BRAND='zqx8yy'\n" >> "$d/checks/private-mode-id.sh"; printf 'a v2 detail zqx8yy\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] && grep -q "^PII_PRIVATE_BRAND .*/relay\.md:1\$" <<<"$out" && grep -qF '3 classes' <<<"$out" && ! grep -qF 'zqx8yy' <<<"$out"; then
    rs_ok "relay: a kept-details line reds whatever its class"
  else
    rs_miss "relay: PII_PRIVATE_BRAND (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; printf "PII_EXTRA='zqx6ff'\n" >> "$(rs_reg "$d")"; printf 'abstract prose\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -qF 'this scan expects 4' <<<"$out"; then
    rs_ok "relay: a fifth registry class blinds the scan (exit 2)"
  else
    rs_miss "relay: a fifth class did not blind (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; sed -i.bak 's/^PII_CASEREF=/PII_EXTRA=/' "$(rs_reg "$d")"; rm -f "$(rs_reg "$d").bak"; printf 'abstract prose\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -qF 'this scan expects 4' <<<"$out"; then
    rs_ok "relay: the case-reference line renamed to an unknown class blinds the scan (exit 2)"
  else
    rs_miss "relay: an unknown class in the case-reference line's place did not blind (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; sed -i.bak 's/^PII_CASEREF=/PII_CASEREF_V2=/' "$(rs_reg "$d")"; rm -f "$(rs_reg "$d").bak"; printf 'abstract prose\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -qF 'this scan expects 4' <<<"$out"; then
    rs_ok "relay: an unknown class whose name carries a digit blinds the scan (exit 2)"
  else
    rs_miss "relay: an unknown class named with a digit did not blind (rc=$rc)"
  fi; rm -rf "$d"
  d="$(rs_mk)"; sed -i.bak 's/^PII_CONSENT=/PII_EXTRA=/' "$(rs_reg "$d")"; rm -f "$(rs_reg "$d").bak"; printf 'abstract prose\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -qF 'PII_CONSENT: expected exactly 1 assignment line' <<<"$out"; then
    rs_ok "relay: a renamed class (four lines, one unknown) blinds the scan (exit 2)"
  else
    rs_miss "relay: a renamed class did not blind (rc=$rc)"
  fi; rm -rf "$d"
  # extra: a scan that cannot load its registry exits 2, never reads clean
  d="$(rs_mk)"; rm -f "$d/checks/FIREWALL-REGISTRY" "$(rs_reg "$d")"; printf 'abstract prose\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -qF 'there is nothing to scan against' <<<"$out"; then
    rs_ok "relay: no registry at all (exit 2)"
  else
    rs_miss "relay: no registry (rc=$rc, expected 2)"
  fi; rm -rf "$d"
  # extra: registry upkeep (ADR-0013 point 5). A ledger NEWER than the registry file makes the
  # scan name the registry's last-change date — from its mtime, set to a past day so a printed run date would
  # MISS — and say it cannot see tokens added since; the scan still ends clean (a notice, never a refusal),
  # with no path, handle or class value.
  d="$(rs_mk)"; mkdir -p "$d/patients/hdl7q/med"; : > "$d/patients/hdl7q/med/MANIFEST"
  touch -t 199912311200 "$(rs_reg "$d")"; touch -t 200001011200 "$d/patients/hdl7q/med/MANIFEST"
  printf 'abstract prose\n' > "$d/relay.md"
  out="$(bash "$d/checks/relay-scan.sh" "$d/relay.md" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -qF 'relay-scan: documents were filed after the token registry last changed (1999-12-31) — this scan cannot see tokens added since' <<<"$out" \
     && grep -qF 'relay-scan: clean (1 files, 2 classes)' <<<"$out" \
     && ! grep -qF "$d" <<<"$out" && ! grep -qF 'hdl7q' <<<"$out" && ! grep -qF 'zqx' <<<"$out"; then
    rs_ok "relay: a ledger newer than the registry names the registry's last-change date (mtime only, no path, handle or token)"
  else
    rs_miss "relay: filed-since reminder missing or wrong (rc=$rc)"
  fi; rm -rf "$d"
  # its control: silent when there is nothing to do — no patients/ at all; the registry newer than every
  # ledger; a symlinked ledger, however new its target, never counts
  rs_silent(){ # dir -> 0 when the scan ends clean AND prints no filed-since reminder
    local o r; o="$(bash "$1/checks/relay-scan.sh" "$1/relay.md" 2>&1)"; r=$?
    [ "$r" -eq 0 ] && grep -qF 'relay-scan: clean (1 files, 2 classes)' <<<"$o" && ! grep -qF 'documents were filed' <<<"$o"; }
  rs_q=""
  d="$(rs_mk)"; printf 'abstract prose\n' > "$d/relay.md"
  rs_silent "$d" || rs_q="$rs_q no-patients"; rm -rf "$d"
  d="$(rs_mk)"; printf 'abstract prose\n' > "$d/relay.md"; mkdir -p "$d/patients/hdl7q/med" "$d/patients/hdl8r/med"
  : > "$d/patients/hdl7q/med/MANIFEST"; : > "$d/patients/hdl8r/med/MANIFEST"
  touch -t 199912311200 "$d/patients/hdl7q/med/MANIFEST" "$d/patients/hdl8r/med/MANIFEST"; touch -t 200001011200 "$(rs_reg "$d")"
  rs_silent "$d" || rs_q="$rs_q registry-newer"; rm -rf "$d"
  d="$(rs_mk)"; printf 'abstract prose\n' > "$d/relay.md"; mkdir -p "$d/patients/hdl7q/med"
  : > "$d/newer.txt"; ln -s "$d/newer.txt" "$d/patients/hdl7q/med/MANIFEST"
  touch -t 199912311200 "$(rs_reg "$d")"; touch -t 200001011200 "$d/newer.txt"
  rs_silent "$d" || rs_q="$rs_q symlinked-ledger"; rm -rf "$d"
  if [ -z "$rs_q" ]; then
    rs_ok "relay: with no filing since (no patients/, registry newer than every ledger, a symlinked ledger) the scan prints no reminder and ends clean"
  else
    rs_miss "relay: the filed-since reminder fired with nothing to do ($rs_q)"
  fi
fi

# install-instance.sh — ADR-0050's per-instance untracked inventory, executable. Its load-bearing properties
# are IDEMPOTENCE and MERGE-NOT-REPLACE (an operator's own settings survive). Fixtures are synthetic minimal
# repos built with the inherited git environment STRIPPED; nothing touches this repository's own hooks or
# .claude/settings.local.json.
INSTINST="$ROOT/checks/install-instance.sh"
if [ ! -x "$INSTINST" ]; then
  echo "BITE  MISS (install-instance: checks/install-instance.sh is missing or not executable)"; fail=$((fail+1))
elif ! command -v git >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  skip install-instance "git or python3 absent — the install-instance bites were NOT run"
else
  ii_ok(){   echo "BITE  OK  ($1)"; pass=$((pass+1)); }
  ii_miss(){ echo "BITE  MISS ($1)"; fail=$((fail+1)); }
  # the installer refuses a tree whose skill sources or check.sh are missing, so the fixture carries them
  # (copied, never synthesised); check.sh answers `--instance-mode` for the checkout family
  ii_mk(){ local d s; d="$(mktemp -d)"; mkdir -p "$d/checks/git-hooks"
    : > "$d/CLAUDE.md"
    cp "$ROOT"/checks/git-hooks/* "$d/checks/git-hooks/"; chmod +x "$d/checks/git-hooks/"*
    cp "$INSTINST" "$d/checks/install-instance.sh"; chmod +x "$d/checks/install-instance.sh"; cp "$ROOT/checks/config-paths.sh" "$d/checks/"
    for s in architect private guard-admission update; do
      mkdir -p "$d/tools/claude-skills/$s"
      cp "$ROOT/tools/claude-skills/$s/SKILL.md" "$d/tools/claude-skills/$s/SKILL.md"
    done
    cp "$ROOT/checks/check.sh" "$d/checks/check.sh"; chmod +x "$d/checks/check.sh"
    mkdir -p "$d/tools/private-mode"; cp "$ROOT/tools/private-mode/check-setup.sh" "$ROOT/tools/private-mode/id-schemes.tsv" "$d/tools/private-mode/"
    # present, so a care run removes a context-health hook because care never runs it, not because the
    # script is missing
    mkdir -p "$d/tools/claude-hooks"; cp "$ROOT/tools/claude-hooks/context-health.py" "$ROOT/tools/claude-hooks/release-notice.py" "$d/tools/claude-hooks/"
    inst_git -C "$d" init -q >/dev/null 2>&1
    inst_git -C "$d" config core.hooksPath "$d/.git/hooks"
    printf '%s\n' "$d"; }
  # how many PreToolUse entries carry the read-guard command? (1 = wired; 2 = a duplicate was added)
  ii_hookn(){ python3 - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("-1"); raise SystemExit(0)
n = 0
for e in d.get("hooks", {}).get("PreToolUse", []) or []:
    for h in (e.get("hooks") or []):
        if isinstance(h, dict) and "registry-read-guard.py" in (h.get("command") or ""):
            n += 1
print(n)
PY
  }
  # how many PostToolUse entries carry the context-health command? (1 = wired)
  ii_chn(){ python3 - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("-1"); raise SystemExit(0)
print(sum(1 for e in d.get("hooks", {}).get("PostToolUse", []) or [] for h in (e.get("hooks") or [])
          if isinstance(h, dict) and "context-health.py" in (h.get("command") or "")))
PY
  }
  # a dotted probe: prints the value at a path, or NONE
  ii_val(){ python3 - "$1" "$2" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("NONE"); raise SystemExit(0)
cur = d
for part in sys.argv[2].split("."):
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        print("NONE"); raise SystemExit(0)
print(json.dumps(cur, sort_keys=True))
PY
  }

  # MERGE, never replace: an operator's own settings keys survive untouched and the deny belt is appended
  # to the existing list rather than overwriting it
  d="$(ii_mk)"; mkdir -p "$d/.claude"
  printf '{\n  "model": "opus",\n  "permissions": { "allow": ["Bash(ls:*)"], "deny": ["Read(./secret)"] }\n}\n' > "$d/.claude/settings.local.json"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  ii_model="$(ii_val "$d/.claude/settings.local.json" model)"
  ii_allow="$(ii_val "$d/.claude/settings.local.json" permissions.allow)"
  ii_deny="$(ii_val "$d/.claude/settings.local.json" permissions.deny)"
  if [ "$rc" -eq 0 ] && [ "$ii_model" = '"opus"' ] && [ "$ii_allow" = '["Bash(ls:*)"]' ] \
     && grep -qF 'Read(./secret)' <<<"$ii_deny" && grep -qF 'Read(./checks/PRIVATE-MODE-ID)' <<<"$ii_deny" \
     && [ "$(ii_hookn "$d/.claude/settings.local.json")" = "1" ]; then
    ii_ok "install-instance: pre-existing settings keys and deny rules survive the merge"
  else
    ii_miss "install-instance merge (rc=$rc, model=$ii_model, allow=$ii_allow)"
  fi
  rm -rf "$d"
  # control: a fresh DEV instance — marker written, all four commit-path hooks installed and executable,
  # settings created with exactly one read-guard hook — and a second run reports unchanged everywhere
  d="$(ii_mk)"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  ii_exec=0; for h in pre-commit commit-msg pre-merge-commit pre-push; do [ -x "$d/.git/hooks/$h" ] && ii_exec=$((ii_exec+1)); done
  if [ "$rc" -eq 0 ] && grep -qF 'marker: written' <<<"$out" && [ "$(cat "$d/.tabularium-instance")" = "dev" ] \
     && [ "$ii_exec" -eq 4 ] && [ "$(ii_hookn "$d/.claude/settings.local.json")" = "1" ] \
     && [ "$(ii_chn "$d/.claude/settings.local.json")" = "1" ]; then
    ii_ok "install-instance dev: marker written, 4/4 hooks installed executable, settings created with the read-guard and context-health hooks"
  else
    ii_miss "install-instance dev (rc=$rc, hooks=$ii_exec/4, read-guard entries=$(ii_hookn "$d/.claude/settings.local.json"), context-health entries=$(ii_chn "$d/.claude/settings.local.json"))"
  fi
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -qF 'marker: unchanged' <<<"$out" && grep -qF 'hooks: unchanged' <<<"$out" \
     && grep -qF 'settings: unchanged' <<<"$out" && [ "$(ii_hookn "$d/.claude/settings.local.json")" = "1" ] \
     && [ "$(ii_chn "$d/.claude/settings.local.json")" = "1" ]; then
    ii_ok "install-instance: a second run reports unchanged everywhere and adds no duplicate hook"
  else
    ii_miss "install-instance idempotence (rc=$rc, read-guard entries=$(ii_hookn "$d/.claude/settings.local.json"), context-health entries=$(ii_chn "$d/.claude/settings.local.json"))"
  fi
  rm -rf "$d"
  # private mode's local tools: a setup check that finds something missing (exit 1) costs the install exactly
  # one line, its own last line, and never the exit code; the planted check answers only to --summary (the full
  # report would call Ollama and point at install commands the installer never prints)
  d="$(ii_mk)"
  printf '#!/bin/sh\n[ "$1" = --summary ] || { echo "private mode setup: run without --summary"; exit 1; }\necho "a report line"\necho "private mode setup: incomplete — missing poppler. Planted."\nexit 1\n' \
    > "$d/tools/private-mode/check-setup.sh"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ "$(grep -c '^private mode setup: ' <<<"$out")" = "1" ] \
     && grep -qx 'private mode setup: incomplete — missing poppler. Planted.' <<<"$out" && ! grep -qF 'a report line' <<<"$out"; then
    ii_ok "install-instance: private mode's setup is reported in one line, and a missing tool never fails the install"
  else
    ii_miss "install-instance, private mode setup line (rc=$rc, lines=$(grep -c '^private mode setup: ' <<<"$out"))"
  fi
  rm -rf "$d"
  # an unknown mode is refused before anything is written — no marker, no hook (the retired
  # `migration:<date>` included, ADR-0050 point 14). The clean twin is the fresh `dev` install
  # above, on the same fixture shape.
  d="$(ii_mk)"
  out="$(bash "$d/checks/install-instance.sh" staging 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -qF "mode must be dev | care (got 'staging')" <<<"$out" \
     && [ ! -e "$d/.tabularium-instance" ] && [ ! -e "$d/.git/hooks/pre-commit" ] && [ ! -e "$d/.git/hooks/pre-push" ]; then
    ii_ok "install-instance: an unknown mode is refused, nothing written"
  else
    ii_miss "install-instance, unknown mode (rc=$rc)"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # the context-health notice is a development-tree hook: a CARE run wires the read-guard, removes an entry
  # an earlier development install left, and keeps the operator's own PostToolUse hook
  d="$(ii_mk)"; mkdir -p "$d/.claude"
  printf '{"hooks":{"PostToolUse":[{"matcher":"Write|Edit","hooks":[{"type":"command","command":"python3 \\"$CLAUDE_PROJECT_DIR/tools/claude-hooks/context-health.py\\""}]},{"matcher":"Bash","hooks":[{"type":"command","command":"true # operator-own"}]}]}}\n' > "$d/.claude/settings.local.json"
  out="$(bash "$d/checks/install-instance.sh" care 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ "$(ii_hookn "$d/.claude/settings.local.json")" = "1" ] \
     && [ "$(ii_chn "$d/.claude/settings.local.json")" = "0" ] && grep -qF 'removed (care)' <<<"$out" \
     && grep -qF 'operator-own' "$d/.claude/settings.local.json"; then
    ii_ok "install-instance care: read-guard wired, a leftover context-health hook removed, the operator's own hook kept"
  else
    ii_miss "install-instance care (rc=$rc, read-guard entries=$(ii_hookn "$d/.claude/settings.local.json"), context-health entries=$(ii_chn "$d/.claude/settings.local.json"))"
  fi
  rm -rf "$d"
  # the release notice (ADR-0055 companion): a CARE install wires its SessionStart hook, one entry under
  # matcher `startup`, and the /update skill, and a second run is unchanged; a DEV install gets neither.
  # A release that does not ship the adapter (a rollback) loses the hook, printed.
  ii_rn(){ python3 - "$1/.claude/settings.local.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("none"); raise SystemExit(0)
hits = [e.get("matcher") for e in d.get("hooks", {}).get("SessionStart", []) or []
        for h in (e.get("hooks") or []) if "release-notice.py" in (h.get("command") or "")]
print(" ".join(hits) if hits else "none")
PY
  }
  d="$(ii_mk)"
  out="$(bash "$d/checks/install-instance.sh" care 2>&1)"; rc=$?
  out2="$(bash "$d/checks/install-instance.sh" care 2>&1)"; rc2=$?
  dv="$(ii_mk)"; outd="$(bash "$dv/checks/install-instance.sh" dev 2>&1)"; rcd=$?
  if [ "$rc" -eq 0 ] && [ "$(ii_rn "$d")" = "startup" ] && cmp -s "$ROOT/tools/claude-skills/update/SKILL.md" "$d/.claude/skills/update/SKILL.md" \
     && [ "$rc2" -eq 0 ] && grep -qF 'settings: unchanged (read-guard hook, release-notice hook' <<<"$out2" && [ "$(ii_rn "$d")" = "startup" ] \
     && [ "$rcd" -eq 0 ] && [ "$(ii_rn "$dv")" = "none" ] && [ ! -e "$dv/.claude/skills/update" ]; then
    ii_ok "install-instance care: the release-notice hook (matcher startup) and /update are installed once; dev gets neither"
  else
    ii_miss "install-instance, release notice (care rc=$rc/$rc2, hook=$(ii_rn "$d"); dev rc=$rcd, hook=$(ii_rn "$dv"))"; echo "$out2" | sed 's/^/      /'
  fi
  rm -rf "$dv"
  rm -f "$d/tools/claude-hooks/release-notice.py"
  out="$(bash "$d/checks/install-instance.sh" care 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ "$(ii_rn "$d")" = "none" ] && grep -qF 'runs tools/claude-hooks/release-notice.py, which this release does not ship' <<<"$out"; then
    ii_ok "install-instance care: a release without the notice's adapter removes its hook, printed"
  else
    ii_miss "install-instance care, release notice rollback (rc=$rc, hook=$(ii_rn "$d"))"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # a Tabularium hook found in an entry it shares with the operator's own hook moves to an entry of its
  # own: the operator's hook keeps its matcher (a rewritten shared matcher silently re-scoped it), and a
  # second run is unchanged
  ii_shared(){ python3 - "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]
def home(event, needle):
    hits = [e for e in d.get(event, []) if any(needle in (h.get("command") or "") for h in e.get("hooks", []))]
    return hits[0] if len(hits) == 1 else None
op_pre, rg = home("PreToolUse", "operator-pre"), home("PreToolUse", "registry-read-guard.py")
op_post, ch = home("PostToolUse", "operator-post"), home("PostToolUse", "context-health.py")
ok = (op_pre and op_pre["matcher"] == "Bash" and len(op_pre["hooks"]) == 1
      and rg and len(rg["hooks"]) == 1 and "Read" in rg["matcher"].split("|")
      and op_post and op_post["matcher"] == "Bash|Write|Edit" and len(op_post["hooks"]) == 1
      and ch and len(ch["hooks"]) == 1 and ch["matcher"] == "Write|Edit")
print("ok" if ok else "bad")
PY
  }
  d="$(ii_mk)"; mkdir -p "$d/.claude"
  printf '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"true # operator-pre"},{"type":"command","command":"python3 \\"$CLAUDE_PROJECT_DIR/tools/claude-hooks/registry-read-guard.py\\""}]}],"PostToolUse":[{"matcher":"Bash|Write|Edit","hooks":[{"type":"command","command":"true # operator-post"},{"type":"command","command":"python3 \\"$CLAUDE_PROJECT_DIR/tools/claude-hooks/context-health.py\\""}]}]}}\n' > "$d/.claude/settings.local.json"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  ii_s1="$(ii_shared "$d/.claude/settings.local.json")"
  out2="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc2=$?
  if [ "$rc" -eq 0 ] && [ "$ii_s1" = "ok" ] && [ "$rc2" -eq 0 ] && grep -qF 'settings: unchanged' <<<"$out2" \
     && [ "$(ii_shared "$d/.claude/settings.local.json")" = "ok" ]; then
    ii_ok "install-instance: hooks sharing an entry with the operator's own move out; the operator's matchers survive, a second run is unchanged"
  else
    ii_miss "install-instance shared entry (rc=$rc/$rc2, layout=$ii_s1)"
  fi
  rm -rf "$d"
  # the read-guard's matcher covers every tool the hook handles, in a care and in a development install: every
  # tool name the hook compares its `tool` with (the file tools and Grep, found in its source), its SHELL_TOOLS and
  # PM_UPLOAD_TOOLS, and the connector wildcard (the hook's source is read, never run). A tool the matcher drops is
  # a tool the hook never sees. ii_rgmiss prints the handled tools the installed matcher lacks, "NONE", or "ERROR"
  # when it cannot tell (the file tools and Grep must be among the names found, or the reading itself is broken).
  ii_rgmiss(){ python3 - "$1" "$ROOT/tools/claude-hooks/registry-read-guard.py" <<'PY'
import ast, json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    tree = ast.parse(open(sys.argv[2], encoding="utf-8").read())
    sets = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
           and n.targets[0].id in ("SHELL_TOOLS", "PM_UPLOAD_TOOLS"):
            sets[n.targets[0].id] = set(ast.literal_eval(n.value))
    if len(sets) != 2 or not all(sets.values()):
        raise ValueError("hook tool sets not read")
    named = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "tool":
            for c in n.comparators:
                for v in (c.elts if isinstance(c, (ast.Tuple, ast.Set, ast.List)) else [c]):
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        named.add(v.value)
    if not {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep"} <= named:
        raise ValueError("hook file tools not read")
    want = named | {"mcp__.*"} | sets["SHELL_TOOLS"] | sets["PM_UPLOAD_TOOLS"]
    have = set()
    for e in d["hooks"]["PreToolUse"]:
        if any("registry-read-guard.py" in (h.get("command") or "") for h in e.get("hooks", [])):
            have |= set((e.get("matcher") or "").split("|"))
    print(" ".join(sorted(want - have)) or "NONE")
except Exception:
    print("ERROR")
PY
  }
  # drop one tool from the installed matcher (the control: the bite must see it go)
  ii_rgdrop(){ python3 - "$1" "$2" <<'PY'
import json, sys
p, tool = sys.argv[1], sys.argv[2]
d = json.load(open(p, encoding="utf-8"))
for e in d["hooks"]["PreToolUse"]:
    if any("registry-read-guard.py" in (h.get("command") or "") for h in e.get("hooks", [])):
        e["matcher"] = "|".join(t for t in e["matcher"].split("|") if t != tool)
json.dump(d, open(p, "w", encoding="utf-8"))
PY
  }
  for ii_m in dev care; do
    d="$(ii_mk)"
    out="$(bash "$d/checks/install-instance.sh" $ii_m 2>&1)"; rc=$?
    ii_rgs="$d/.claude/settings.local.json"
    ii_r0="$(ii_rgmiss "$ii_rgs")"
    ii_rb=""; for ii_t in Bash Grep SendUserFile 'mcp__.*'; do ii_rgdrop "$ii_rgs" "$ii_t"; ii_rb="$ii_rb [$(ii_rgmiss "$ii_rgs")]"; done
    if [ "$rc" -eq 0 ] && [ "$ii_r0" = "NONE" ] && [ "$ii_rb" = " [Bash] [Bash Grep] [Bash Grep SendUserFile] [Bash Grep SendUserFile mcp__.*]" ]; then
      ii_ok "install-instance $ii_m: the read-guard matcher covers every tool the hook handles; each tool dropped from it is reported (control)"
    else
      ii_miss "install-instance $ii_m, read-guard matcher (rc=$rc, missing='$ii_r0', after drops:$ii_rb)"
    fi
    rm -rf "$d"
  done
  # extra: the private-mode identifier split check. The installer verifies the split
  # content-blind and only then drops the registry's deny rules, so a false "split verified" would let a
  # session read the registry. Synthetic registry carrying the documented fold-in block (extracted from
  # checks/topics/relay-and-export.md, the text the operator copies) and a private file, both OUTSIDE the fixture repository.
  ii_pmblock="$(awk '/<!-- private-mode-id-block:begin -->/{f=1; next} /<!-- private-mode-id-block:end -->/{f=0} f' "$ROOT/checks/topics/relay-and-export.md" | sed '/^```/d')"
  ii_split(){ # $1 = fixture repo · $2 = external dir -> a correctly split synthetic registry + private file + pointers
    printf "PII_IDENTITY='zqx1aa'\nPII_CASEREF='zqx2bb'\nPII_CLINICAL='zqx3cc'\nPII_BRAND='zqx4dd'\nPII_CONSENT='zqx5ee'\n" > "$2/firewall-registry.sh"
    printf '%s\n' "$ii_pmblock" | sed "s#/ABSOLUTE/PATH/OF/private-mode-id.sh#$2/private-mode-id.sh#" >> "$2/firewall-registry.sh"
    printf "PII_PRIVATE_MODE_ID='zqx9zz'\n" > "$2/private-mode-id.sh"
    chmod 600 "$2/firewall-registry.sh" "$2/private-mode-id.sh"
    printf '%s\n' "$2/firewall-registry.sh" > "$1/checks/FIREWALL-REGISTRY"
    printf '%s\n' "$2/private-mode-id.sh" > "$1/checks/PRIVATE-MODE-ID"; }
  ii_has(){ grep -qF -- "$2" <<<"$(ii_val "$1/.claude/settings.local.json" permissions.deny)"; }
  ii_cmd(){ python3 - "$1/.claude/settings.local.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("\n".join(h.get("command", "") for e in d["hooks"]["PreToolUse"] for h in e.get("hooks", [])
                if "registry-read-guard.py" in h.get("command", "")))
PY
  }
  # control: a correct split verifies — paths on the hook's command line, the private file's rules added,
  # the registry's rules REMOVED, no path and no token printed
  d="$(ii_mk)"; x="$(mktemp -d)"; ii_split "$d" "$x"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  ii_c="$(ii_cmd "$d")"
  if [ "$rc" -eq 0 ] && grep -qF 'private-mode identifier: split verified' <<<"$out" \
     && grep -qF -- '--split-verified' <<<"$ii_c" && grep -qF -- "--private $x/private-mode-id.sh" <<<"$ii_c" \
     && ii_has "$d" "Read(/$x/private-mode-id.sh)" && ii_has "$d" "Read(./checks/PRIVATE-MODE-ID)" \
     && ! ii_has "$d" "Read(/$x/firewall-registry.sh)" && ! ii_has "$d" "Read(./checks/FIREWALL-REGISTRY)" \
     && ! grep -qF "$x" <<<"$out" && ! grep -qF 'zqx9zz' <<<"$out"; then
    ii_ok "install-instance: a correct split verifies — paths on the hook line, registry rules dropped, nothing printed"
  else
    ii_miss "install-instance, verified split (rc=$rc, verified=$(grep -c 'split verified' <<<"$out"), path-leak=$(grep -cF "$x" <<<"$out"))"
  fi
  # test, on that same verified state: a copy of the identifier left beside the registry (an editor
  # backup) un-verifies the split and restores the registry's protection
  cp "$x/private-mode-id.sh" "$x/firewall-registry.sh~"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  if grep -qF 'split NOT verified' <<<"$out" && grep -qF 'copied, not cut' <<<"$out" \
     && ! grep -qF -- '--split-verified' <<<"$(ii_cmd "$d")" && ii_has "$d" "Read(/$x/firewall-registry.sh)"; then
    ii_ok "install-instance: a copy of the identifier left beside the registry (an editor backup) un-verifies the split and restores the registry's protection"
  else
    ii_miss "install-instance, editor backup (rc=$rc)"
  fi
  rm -rf "$d" "$x"
  # a leftover kept-details line of the retired case-reference class (ADR-0072) is ignored: the split still verifies.
  # Negative control: the same file with an unknown class line does not.
  d="$(ii_mk)"; x="$(mktemp -d)"; ii_split "$d" "$x"; printf "PII_PRIVATE_CASEREF='zqx7qq'\n" >> "$x/private-mode-id.sh"
  out="$(bash "$d/checks/install-instance.sh" dev 2>&1)"; rc=$?
  printf "PII_PRIVATE_EXTRA='zqx6ww'\n" >> "$x/private-mode-id.sh"
  out2="$(bash "$d/checks/install-instance.sh" dev 2>&1)"
  if [ "$rc" -eq 0 ] && grep -qF 'private-mode identifier: split verified' <<<"$out" && grep -qF 'split NOT verified' <<<"$out2"; then
    ii_ok "install-instance: a leftover kept-details case-reference line still verifies; an unknown class line does not"
  else
    ii_miss "install-instance, leftover kept-details case-reference line (rc=$rc, verified=$(grep -c 'split verified' <<<"$out"), unknown-refused=$(grep -c 'split NOT verified' <<<"$out2"))"
  fi
  rm -rf "$d" "$x"

  # CARE (ADR-0055 point 4). ii_mkcare <tag at HEAD>: ii_mk's tree, plus a synthetic
  # tools/claude-hooks/session-notice.py, committed as release v1.0.0; v1.1.0 drops that script and the
  # guard-admission skill's source; v1.2.0 adds a `notice` skill and a `post-merge` git hook. HEAD
  # detached at the tag given; the pin reads v1.0.0, adopted before.
  ii_g(){ inst_git -c user.name=fixture -c user.email=fixture@example.invalid -c commit.gpgsign=false \
    -c tag.gpgsign=false -c advice.detachedHead=false "$@"; }
  ii_mkcare(){ local d; d="$(ii_mk)"; mkdir -p "$d/tools/claude-hooks"
    printf 'print("synthetic")\n' > "$d/tools/claude-hooks/session-notice.py"
    ii_g -C "$d" add -A >/dev/null 2>&1; ii_g -C "$d" commit -q -m "release 1" >/dev/null 2>&1
    ii_g -C "$d" tag -a -m n v1.0.0 >/dev/null 2>&1
    ii_g -C "$d" rm -r -q tools/claude-skills/guard-admission tools/claude-hooks/session-notice.py >/dev/null 2>&1
    ii_g -C "$d" commit -q -m "release 2" >/dev/null 2>&1; ii_g -C "$d" tag -a -m n v1.1.0 >/dev/null 2>&1
    mkdir -p "$d/tools/claude-skills/notice"; printf 'a skill a newer release added\n' > "$d/tools/claude-skills/notice/SKILL.md"
    printf '#!/bin/sh\n# Tabularium post-merge guard — synthetic, a hook a newer release added\nexit 0\n' > "$d/checks/git-hooks/post-merge"
    ii_g -C "$d" add -A >/dev/null 2>&1; ii_g -C "$d" commit -q -m "release 3" >/dev/null 2>&1
    ii_g -C "$d" tag -a -m n v1.2.0 >/dev/null 2>&1
    ii_g -C "$d" checkout -q --detach "$1" >/dev/null 2>&1
    printf 'v1.0.0\n' > "$d/checks/CARE-RELEASE"
    printf '%s\n' "$d"; }
  ii_pin(){ cat "$1/checks/CARE-RELEASE" 2>/dev/null; }
  # leftovers of an earlier release, and the operator's own beside them: a managed skill, the Tabularium
  # pre-commit hook and a settings hook entry running a tools/claude-hooks/ script; the operator's skill,
  # git hook and settings hook entry
  ii_leftovers(){ mkdir -p "$1/.claude/skills/guard-admission" "$1/.claude/skills/my-notes" "$1/.git/hooks"
    cp "$ROOT/tools/claude-skills/guard-admission/SKILL.md" "$1/.claude/skills/guard-admission/SKILL.md"
    printf "the operator's own skill\n" > "$1/.claude/skills/my-notes/SKILL.md"
    cp "$ROOT/checks/git-hooks/pre-commit" "$1/.git/hooks/pre-commit"; chmod +x "$1/.git/hooks/pre-commit"
    printf "#!/bin/sh\n# the operator's own hook\n" > "$1/.git/hooks/post-checkout"
    cat > "$1/.claude/settings.local.json" <<'IIJSON'
{
  "hooks": {
    "SessionStart": [ { "hooks": [ { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/claude-hooks/session-notice.py\"" } ] } ],
    "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "echo operator-own" },
      { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/claude-hooks/session-notice.py\" --pre" } ] } ]
  }
}
IIJSON
  }
  # the entry holding the operator's hook: its matcher and how many hooks it holds ("Bash 1" = intact)
  ii_opentry(){ python3 - "$1/.claude/settings.local.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
hits = [e for es in d.get("hooks", {}).values() for e in es
        if any(h.get("command") == "echo operator-own" for h in e.get("hooks", []))]
print("%s %d" % (hits[0].get("matcher"), len(hits[0]["hooks"])) if len(hits) == 1 else "none")
PY
  }
  ii_cmds(){ python3 - "$1/.claude/settings.local.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("\n".join(h.get("command", "") for es in d.get("hooks", {}).values() for e in es for h in e.get("hooks", [])))
PY
  }
  # test (failure 1): an install that fails late — a care skill's source missing — must not write the pin;
  # the old order wrote it before the skills and left L19 green over a stale skill
  d="$(ii_mkcare v1.1.0)"; rm -f "$d/tools/claude-skills/private/SKILL.md"
  out="$(bash "$d/checks/install-instance.sh" care v1.1.0 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] && [ "$(ii_pin "$d")" = "v1.0.0" ] && grep -qF 'release: NOT written' <<<"$out"; then
    ii_ok "install-instance care: an install that fails late (a missing skill source) leaves the previous pin"
  else
    ii_miss "install-instance care, late failure (rc=$rc, pin=$(ii_pin "$d"))"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # control: every source present — the pin is written, and as the last action
  d="$(ii_mkcare v1.1.0)"
  out="$(bash "$d/checks/install-instance.sh" care v1.1.0 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ "$(ii_pin "$d")" = "v1.1.0" ] \
     && [ "$(grep -v '^install-instance: done' <<<"$out" | tail -1)" = "release: written (checks/CARE-RELEASE = v1.1.0)" ]; then
    ii_ok "install-instance care: a complete install writes the pin, last"
  else
    ii_miss "install-instance care, pin last (rc=$rc, pin=$(ii_pin "$d"))"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # test (failure 3, installer leg): a tag that is not checked out is refused before anything is written —
  # the unchained recovery re-pinned a release whose checkout had aborted
  d="$(ii_mkcare v1.0.0)"
  out="$(bash "$d/checks/install-instance.sh" care v1.1.0 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] && grep -qF "HEAD is not the release 'v1.1.0'" <<<"$out" && [ "$(ii_pin "$d")" = "v1.0.0" ] \
     && [ ! -e "$d/.tabularium-instance" ] && [ ! -e "$d/.git/hooks/pre-push" ] && [ ! -e "$d/.claude/settings.local.json" ]; then
    ii_ok "install-instance care: a release that is not checked out is refused with nothing written"
  else
    ii_miss "install-instance care, HEAD not the tag (rc=$rc, pin=$(ii_pin "$d"))"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # control: the release at HEAD (a re-install of the one in use) is accepted and the pin is unchanged
  d="$(ii_mkcare v1.0.0)"
  out="$(bash "$d/checks/install-instance.sh" care v1.0.0 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ "$(ii_pin "$d")" = "v1.0.0" ] && grep -qF 'release: unchanged' <<<"$out"; then
    ii_ok "install-instance care: the release at HEAD is accepted"
  else
    ii_miss "install-instance care, release at HEAD (rc=$rc, pin=$(ii_pin "$d"))"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # test (failure 4): v1.1.0 ships neither the guard-admission skill nor session-notice.py — the
  # installer removes that skill, the Tabularium pre-commit hook care never installs and both settings
  # hooks whose script is gone (python3 on it exits 2, a blocking PreToolUse answer), printing each — the
  # one sharing an entry with the operator's hook leaves it alone; the operator's own skill, hook, entry
  # and matcher stay
  d="$(ii_mkcare v1.1.0)"; ii_leftovers "$d"
  out="$(bash "$d/checks/install-instance.sh" care v1.1.0 2>&1)"; rc=$?
  ii_c="$(ii_cmds "$d")"
  if [ "$rc" -eq 0 ] && [ ! -e "$d/.claude/skills/guard-admission" ] && [ ! -e "$d/.git/hooks/pre-commit" ] \
     && ! grep -qF 'session-notice.py' <<<"$ii_c" \
     && [ "$(grep -c '^removed: ' <<<"$out")" = "4" ] && grep -qF 'removed: the guard-admission skill' <<<"$out" \
     && grep -qF 'removed: the pre-commit git hook' <<<"$out" && grep -qF 'runs tools/claude-hooks/session-notice.py' <<<"$out" \
     && [ -f "$d/.claude/skills/my-notes/SKILL.md" ] && [ -f "$d/.git/hooks/post-checkout" ] \
     && [ "$(ii_opentry "$d")" = "Bash 1" ] && [ "$(ii_pin "$d")" = "v1.1.0" ]; then
    ii_ok "install-instance care: tooling of its own the release does not ship is removed, each removal printed, a shared entry keeping the operator's hook and matcher"
  else
    ii_miss "install-instance care, leftovers (rc=$rc, removed lines=$(grep -c '^removed: ' <<<"$out"))"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # control: v1.0.0 ships that skill and that script, and the pre-commit hook is the operator's own (no
  # Tabularium header) — nothing is removed and every one of them comes through byte-identical
  d="$(ii_mkcare v1.0.0)"; ii_leftovers "$d"
  printf "#!/bin/sh\n# the operator's own pre-commit\n" > "$d/.git/hooks/pre-commit"
  for x in .claude/skills/guard-admission/SKILL.md .claude/skills/my-notes/SKILL.md .git/hooks/pre-commit .git/hooks/post-checkout; do
    cp "$d/$x" "$d/.fx-$(basename "$(dirname "$x")")-$(basename "$x").orig"
  done
  out="$(bash "$d/checks/install-instance.sh" care v1.0.0 2>&1)"; rc=$?
  ii_c="$(ii_cmds "$d")"; ii_same=1
  for x in .claude/skills/guard-admission/SKILL.md .claude/skills/my-notes/SKILL.md .git/hooks/pre-commit .git/hooks/post-checkout; do
    cmp -s "$d/$x" "$d/.fx-$(basename "$(dirname "$x")")-$(basename "$x").orig" || ii_same=0
  done
  if [ "$rc" -eq 0 ] && [ "$ii_same" -eq 1 ] && ! grep -q '^removed: ' <<<"$out" \
     && [ "$(grep -c 'tools/claude-hooks/session-notice.py' <<<"$ii_c")" = "2" ] && [ "$(ii_opentry "$d")" = "Bash 2" ]; then
    ii_ok "install-instance care: what the release ships and what is the operator's own is never removed"
  else
    ii_miss "install-instance care, nothing to remove (rc=$rc, byte-identical=$ii_same)"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # tests (a rollback below a NEWER release): v1.1.0 is installed over what v1.2.0 left — its `notice`
  # skill and its `post-merge` hook, each byte for byte v1.2.0's own. No name list knows either; the
  # release tags' bytes do, and both go, each printed
  d="$(ii_mkcare v1.1.0)"; mkdir -p "$d/.claude/skills/notice"
  ii_g -C "$d" show v1.2.0:tools/claude-skills/notice/SKILL.md > "$d/.claude/skills/notice/SKILL.md"
  ii_g -C "$d" show v1.2.0:checks/git-hooks/post-merge > "$d/.git/hooks/post-merge"
  out="$(bash "$d/checks/install-instance.sh" care v1.1.0 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && [ ! -e "$d/.claude/skills/notice" ] && grep -qF "removed: the notice skill — v1.2.0's own copy" <<<"$out"; then
    ii_ok "install-instance care: a skill whose bytes are a release tag's own, not shipped here, is removed"
  else
    ii_miss "install-instance care, newer release's skill (rc=$rc)"; echo "$out" | sed 's/^/      /'
  fi
  if [ "$rc" -eq 0 ] && [ ! -e "$d/.git/hooks/post-merge" ] && grep -qF "removed: the post-merge git hook — v1.2.0's own" <<<"$out"; then
    ii_ok "install-instance care: a git hook outside the four known names whose bytes are a release's own hook is removed"
  else
    ii_miss "install-instance care, newer release's hook (rc=$rc)"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
  # controls: the same names with other bytes — the `notice` skill and the headed `post-merge` hook
  # edited by hand — beside the operator's own skill and an unmarked hook. All kept byte-identical,
  # nothing removed; the edited released skill and the headed hook each get a warning, the operator's
  # own skill and unmarked hook none
  d="$(ii_mkcare v1.1.0)"; mkdir -p "$d/.claude/skills/notice" "$d/.claude/skills/my-notes"
  printf 'the operator rewrote this notice\n' > "$d/.claude/skills/notice/SKILL.md"
  printf "the operator's own skill\n" > "$d/.claude/skills/my-notes/SKILL.md"
  { ii_g -C "$d" show v1.2.0:checks/git-hooks/post-merge; printf '# a line the operator added\n'; } > "$d/.git/hooks/post-merge"
  printf "#!/bin/sh\n# the operator's own post-checkout\n" > "$d/.git/hooks/post-checkout"
  for x in .claude/skills/notice/SKILL.md .claude/skills/my-notes/SKILL.md .git/hooks/post-merge .git/hooks/post-checkout; do
    cp "$d/$x" "$d/.fx-$(basename "$(dirname "$x")")-$(basename "$x").orig"
  done
  out="$(bash "$d/checks/install-instance.sh" care v1.1.0 2>&1)"; rc=$?
  ii_same=1
  for x in .claude/skills/notice/SKILL.md .claude/skills/my-notes/SKILL.md .git/hooks/post-merge .git/hooks/post-checkout; do
    cmp -s "$d/$x" "$d/.fx-$(basename "$(dirname "$x")")-$(basename "$x").orig" || ii_same=0
  done
  ii_w="$(grep '^warn: ' <<<"$out")"
  if [ "$rc" -eq 0 ] && [ "$ii_same" -eq 1 ] && ! grep -q '^removed: ' <<<"$out" \
     && grep -qF "kept .claude/skills/notice as the operator's: v1.2.0 shipped a skill of that name" <<<"$ii_w" \
     && ! grep -qF 'my-notes' <<<"$ii_w"; then
    ii_ok "install-instance care: an edited released skill is kept with a warning, the operator's own skill without one"
  else
    ii_miss "install-instance care, skills of other bytes (rc=$rc, byte-identical=$ii_same)"; echo "$out" | sed 's/^/      /'
  fi
  if [ "$rc" -eq 0 ] && [ "$ii_same" -eq 1 ] && ! grep -q '^removed: ' <<<"$out" \
     && grep -qF "kept the post-merge git hook as the operator's" <<<"$ii_w" && ! grep -qF 'post-checkout' <<<"$ii_w"; then
    ii_ok "install-instance care: a headed hook of other bytes is kept with a warning, an unmarked one without"
  else
    ii_miss "install-instance care, hooks of other bytes (rc=$rc, byte-identical=$ii_same)"; echo "$out" | sed 's/^/      /'
  fi
  rm -rf "$d"
fi

# checks/setup-mac.sh — what a caregiver's Mac needs, and getting it there. Each case runs a copy in a synthetic root
# with PATH reduced to a stub directory, so it sees exactly the machine the case describes; stubs are shell scripts,
# the few real tools it uses linked in. Test: a Mac without Apple's tools, whose placeholder git and python3 leave a
# trace if run. Control: the same stubs with the tools present.
SM_SRC="$ROOT/checks/setup-mac.sh"
if [ ! -f "$SM_SRC" ]; then
  echo "BITE  MISS (Mac setup: checks/setup-mac.sh is missing)"; fail=$((fail+1))
else
  sm_ok(){ echo "BITE  OK  (Mac setup: $1)"; pass=$((pass+1)); }
  sm_miss(){ echo "BITE  MISS (Mac setup: $1)"; [ -z "${2:-}" ] || printf '%s\n' "$2" | sed 's/^/      /'; fail=$((fail+1)); }
  sm_stub(){ printf '#!/bin/sh\n%s\n' "$2" > "$1"; chmod +x "$1"; }   # $1 = path · $2 = its body
  sm_box(){ # $1 = uname answer · $2 = xcode-select's exit code -> a directory holding root/ (a copy of the script), bin/ and home/
    local b u
    b="$(mktemp -d "${TMPDIR:-/tmp}/tabularium-sm.XXXXXX")"
    mkdir -p "$b/root/checks" "$b/root/tools/private-mode" "$b/root/_templates/handout-assets" "$b/bin" "$b/home"
    cp "$SM_SRC" "$b/root/checks/setup-mac.sh"
    for u in grep dirname mkdir chmod touch cat; do ln -s "$(command -v "$u")" "$b/bin/$u"; done
    ln -s "$(command -v python3)" "$b/bin/python3-real"
    sm_stub "$b/bin/uname" "echo $1"
    sm_stub "$b/bin/xcode-select" "exit $2"
    sm_stub "$b/bin/git" "echo run >> '$b/placeholder-run'; echo 'git version 2.50.1'"
    sm_stub "$b/bin/python3" "echo run >> '$b/placeholder-run'; echo 3.9.6"
    printf '%s\n' "$b"; }
  sm_run(){ # $1 = box · the rest = the script's arguments -> out, rc
    local b="$1"; shift
    out="$(cd "$b/root" && HOME="$b/home" PATH="$b/bin" SHELL="${SM_SHELL:-/bin/zsh}" SETUP_APPLE_BIN="$b/bin" SETUP_BREW_DIRS="$b/brewhome" "$BASH" checks/setup-mac.sh "$@" 2>&1)"; rc=$?; }

  # --- inspect ---
  b="$(sm_box Darwin 2)"; sm_run "$b"
  if [ "$rc" -eq 1 ] && grep -qF "MISSING Apple's command line tools — why: git and Python come with them" <<<"$out" \
     && grep -qxF "in Terminal: xcode-select --install" <<<"$out" \
     && grep -qxF "setup: base incomplete — missing Apple's command line tools" <<<"$out" && [ ! -e "$b/placeholder-run" ]; then
    sm_ok "a Mac without Apple's tools is told what and why, with its Terminal line, and neither placeholder is run"
  else sm_miss "no Apple tools (rc=$rc, placeholder run: $([ -e "$b/placeholder-run" ] && echo yes || echo no))" "$out"; fi
  rm -rf "$b"

  # a git and a Python of Homebrew's are real ones, with or without Apple's tools
  b="$(sm_box Darwin 2)"; out="$(cd "$b/root" && HOME="$b/home" PATH="$b/bin" SETUP_APPLE_BIN=/nonexistent "$BASH" checks/setup-mac.sh 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -qxF "setup: base complete (git and Python)" <<<"$out"; then sm_ok "a git and Python outside Apple's folder need no Apple tools"
  else sm_miss "non-Apple git and Python (rc=$rc)" "$out"; fi
  rm -rf "$b"

  b="$(sm_box Darwin 0)"; sm_run "$b"
  if [ "$rc" -eq 0 ] && grep -qxF "ok      git" <<<"$out" && grep -qxF "ok      Python 3.9.6" <<<"$out" \
     && grep -qxF "setup: base complete (git and Python)" <<<"$out" \
     && [ "$(grep -c 'send what they read to the AI service; check your plan' <<<"$out")" = "1" ] \
     && ! grep -q 'iCloud' <<<"$out"; then
    sm_ok "with Apple's tools, base is complete, the AI-service line prints once and no folder note appears"
  else sm_miss "complete Mac (rc=$rc)" "$out"; fi
  sm_stub "$b/bin/python3" "echo 3.8.10"; sm_run "$b"
  if [ "$rc" -eq 1 ] && grep -qF "MISSING Python 3.9 or newer (this one is 3.8.10, at $b/bin/python3)" <<<"$out" \
     && ! grep -q '^in Terminal:' <<<"$out"; then sm_ok "a too-old Python ahead of Apple's is named, with no installer line that cannot fix it"
  else sm_miss "old Python (rc=$rc)" "$out"; fi
  rm -rf "$b"

  # Apple's tools in and git still not running: Apple's installer fixes neither, so it is not offered; an Xcode licence
  # not yet accepted (git exits 69) is the one case with a step for the person
  b="$(sm_box Darwin 0)"; sm_stub "$b/bin/git" "exit 1"; sm_run "$b"
  if [ "$rc" -eq 1 ] && grep -qF "Apple's command line tools are in, but the git at $b/bin/git does not run" <<<"$out" \
     && ! grep -q '^in Terminal:' <<<"$out"; then sm_ok "a git that fails with Apple's tools in is named, with no installer line"
  else sm_miss "failing git with Apple's tools (rc=$rc)" "$out"; fi
  sm_stub "$b/bin/git" "exit 69"; sm_run "$b"
  if [ "$rc" -eq 1 ] && grep -qxF "in Terminal: sudo xcodebuild -license" <<<"$out" && ! grep -qF 'xcode-select --install' <<<"$out"; then
    sm_ok "an Xcode licence not accepted gives the licence step in the Terminal panel"
  else sm_miss "licence not accepted (rc=$rc)" "$out"; fi
  rm -rf "$b"

  b="$(sm_box Darwin 0)"; mkdir -p "$b/home/Documents"; mv "$b/root" "$b/home/Documents/Tabularium"
  out="$(cd "$b/home/Documents/Tabularium" && HOME="$b/home" PATH="$b/bin" "$BASH" checks/setup-mac.sh 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ] && grep -q "note: this folder sits where iCloud's Desktop & Documents sync" <<<"$out"; then sm_ok "a folder in Documents draws its note and still completes"
  else sm_miss "folder note (rc=$rc)" "$out"; fi
  rm -rf "$b"

  b="$(sm_box Linux 0)"; sm_run "$b"
  if [ "$rc" -eq 1 ] && grep -qF "macOS is the only system" <<<"$out" && [ ! -e "$b/placeholder-run" ]; then sm_ok "another system is refused"
  else sm_miss "not a Mac (rc=$rc)" "$out"; fi
  rm -rf "$b"

  # --- pre-approve ---
  b="$(sm_box Darwin 0)"; mv "$b/bin/python3-real" "$b/bin/python3"; mkdir -p "$b/root/.claude"
  printf '{"permissions":{"allow":["Read(./x)"],"deny":["Read(./secret)"]},"hooks":{"Stop":[]}}\n' > "$b/root/.claude/settings.local.json"
  sm_run "$b" pre-approve; first_rc=$rc; first="$out"
  sm_rules="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("\n".join(d["permissions"]["allow"])); print("deny="+d["permissions"]["deny"][0]); print("hooks="+",".join(d["hooks"]))' "$b/root/.claude/settings.local.json" 2>&1)"
  sm_run "$b" pre-approve
  # every added rule is one of the three families; nothing that installs, moves records off the Mac or runs git
  sm_extra="$(grep -E '^Bash' <<<"$sm_rules" | grep -vE '^Bash\((bash )?checks/(check|snapshot|confirms)\.sh( \*)?\)$|^Bash\(python3 -m tools\.person_ownership --root \. (init|append|verify) \*\)$|^Bash\(python3 -m tools\.interview_capture \*\)$|^Bash\(\.venv-render/bin/python -m tools\.original_view \*\)$')"
  if [ "$first_rc" -eq 0 ] && grep -qxF 'Read(./x)' <<<"$sm_rules" && grep -qxF 'deny=Read(./secret)' <<<"$sm_rules" && grep -qxF 'hooks=Stop' <<<"$sm_rules" \
     && grep -qxF 'Bash(bash checks/check.sh)' <<<"$sm_rules" && grep -qxF 'Bash(python3 -m tools.person_ownership --root . append *)' <<<"$sm_rules" \
     && grep -qxF 'Bash(.venv-render/bin/python -m tools.original_view *)' <<<"$sm_rules" && ! grep -qF 'migrate' <<<"$sm_rules" \
     && [ -z "$sm_extra" ] && [ "$rc" -eq 0 ] && grep -qF 'already pre-approved' <<<"$out"; then
    sm_ok "pre-approve keeps existing settings, adds only the checks, snapshots and filing tools, and says so once"
  else sm_miss "pre-approve (first rc=$first_rc, second rc=$rc; outside the list: ${sm_extra:-none})" "$first"; fi
  printf 'not json\n' > "$b/root/.claude/settings.local.json"; sm_run "$b" pre-approve
  if [ "$rc" -eq 1 ] && [ "$(cat "$b/root/.claude/settings.local.json")" = "not json" ]; then sm_ok "pre-approve refuses a settings file it cannot read, untouched"
  else sm_miss "pre-approve over unreadable settings (rc=$rc)" "$out"; fi
  rm -rf "$b"

  # --- private mode: a stub Homebrew whose `install` puts the named tools on PATH and records its arguments ---
  sm_pm(){ # $1 = box: a read-only check that passes once tesseract-lang is in, and the stub Homebrew
    local b="$1"
    sm_stub "$b/root/tools/private-mode/check-setup.sh" "[ -e '$b/pack-in' ] && { echo 'private mode setup: complete'; exit 0; }; echo 'private mode setup: incomplete — missing language data'; exit 1"
    sm_stub "$b/bin/bash" "exec '$BASH' \"\$@\""
    sm_brew "$b" "$b/bin/brew"; }
  sm_brew(){ # $1 = box · $2 = where the stub goes
    local b="$1"
    sm_stub "$2" "[ \"\$1\" = install ] || exit 0; shift; echo \"\$*\" >> '$b/brew-args'; for f in \"\$@\"; do case \"\$f\" in
      poppler) printf '#!/bin/sh\nexit 0\n' > '$b/bin/pdftoppm'; chmod +x '$b/bin/pdftoppm' ;;
      imagemagick) printf '#!/bin/sh\nexit 0\n' > '$b/bin/magick'; chmod +x '$b/bin/magick' ;;
      tesseract) printf '#!/bin/sh\nprintf \"List:\\\\neng\\\\nosd\\\\n\"; [ -e %s/pack-in ] && printf \"pol\\\\ndeu\\\\n\"; exit 0\n' '$b' > '$b/bin/tesseract'; chmod +x '$b/bin/tesseract' ;;
      tesseract-lang) touch '$b/pack-in' ;;
    esac; done; exit 0"; }

  b="$(sm_box Darwin 0)"; sm_run "$b" private-mode pol
  if [ "$rc" -eq 2 ] && grep -qF 'in Terminal: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' <<<"$out" \
     && grep -qF 'MISSING Homebrew' <<<"$out" && [ ! -e "$b/brew-args" ]; then sm_ok "private mode with no Homebrew stops for the person, nothing installed"
  else sm_miss "private mode without Homebrew (rc=$rc)" "$out"; fi
  rm -rf "$b"

  b="$(sm_box Darwin 0)"; sm_pm "$b"; sm_run "$b" private-mode deu
  if [ "$rc" -eq 0 ] && [ "$(sed -n 1p "$b/brew-args" 2>/dev/null)" = "poppler tesseract imagemagick" ] && [ "$(sed -n 2p "$b/brew-args" 2>/dev/null)" = "tesseract-lang" ] \
     && grep -qxF 'ok      text recognition (deu)' <<<"$out" && grep -qxF 'ok      text recognition (eng)' <<<"$out" \
     && grep -qxF 'private mode setup: complete' <<<"$out" && grep -qxF "setup: private mode's tools complete" <<<"$out"; then
    sm_ok "private mode installs what is missing plus the language pack, and ends on the read-only check's word"
  else sm_miss "private mode install (rc=$rc; brew: $(tr '\n' '|' < "$b/brew-args" 2>/dev/null))" "$out"; fi
  : > "$b/brew-args"; sm_run "$b" private-mode deu
  if [ "$rc" -eq 0 ] && [ ! -s "$b/brew-args" ]; then sm_ok "a second private mode run installs nothing"
  else sm_miss "private mode second run (rc=$rc)" "$out"; fi
  rm -rf "$b"

  # English chosen, and the number list's language still needed: the pack comes anyway, because the check says so
  b="$(sm_box Darwin 0)"; sm_pm "$b"; sm_run "$b" private-mode eng
  if [ "$rc" -eq 0 ] && grep -qx 'tesseract-lang' "$b/brew-args"; then sm_ok "choosing English does not drop what the read-only check requires"
  else sm_miss "English chosen (rc=$rc)" "$out"; fi
  # the pack already in and the check content: English needs no download
  : > "$b/brew-args"; sm_run "$b" private-mode eng
  if [ "$rc" -eq 0 ] && [ ! -s "$b/brew-args" ]; then sm_ok "with the check content, English needs no language pack"
  else sm_miss "English, nothing needed (rc=$rc)" "$out"; fi
  rm -rf "$b"

  # a check that stays unhappy after the install fails the step
  b="$(sm_box Darwin 0)"; sm_pm "$b"; sm_stub "$b/root/tools/private-mode/check-setup.sh" "echo 'private mode setup: incomplete — missing poppler'; exit 1"; sm_run "$b" private-mode eng
  if [ "$rc" -eq 1 ] && grep -qF "setup: private mode's tools incomplete" <<<"$out"; then sm_ok "the read-only check's no fails the step"
  else sm_miss "unhappy check (rc=$rc)" "$out"; fi
  rm -rf "$b"

  # Homebrew only in its standard home: found, added to the shell's path once
  b="$(sm_box Darwin 0)"; sm_pm "$b"; rm -f "$b/bin/brew"; mkdir -p "$b/brewhome"; sm_brew "$b" "$b/brewhome/brew"; sm_run "$b" private-mode deu; rc1=$rc
  sm_run "$b" private-mode deu
  # the Claude app reads that path only when it starts, so a step that had to add Homebrew ends on the restart line
  if [ "$rc1" -eq 2 ] && [ "$rc" -eq 2 ] && [ "$(grep -c 'brew shellenv' "$b/home/.zprofile" 2>/dev/null)" = "1" ] \
     && grep -qxF "[ -x $b/brewhome/brew ] && eval \"\$($b/brewhome/brew shellenv)\"" "$b/home/.zprofile" \
     && grep -q '^restart: quit the Claude app completely and open it again' <<<"$out" \
     && [ "$(printf '%s\n' "$out" | tail -n 1)" = "setup: private mode's tools complete, once the Claude app has been reopened" ]; then
    sm_ok "a Homebrew off the app's path is added once, by a line harmless once it is gone, and the step asks for a restart"
  else sm_miss "Homebrew path (rc=$rc1, $rc; lines: $(grep -c 'brew shellenv' "$b/home/.zprofile" 2>/dev/null))" "$out"; fi
  # a profile whose only Homebrew line is commented out, or names another Homebrew home, gets a live line for this one,
  # or every later run would ask for a restart again
  b2="$(sm_box Darwin 0)"; sm_pm "$b2"; rm -f "$b2/bin/brew"; mkdir -p "$b2/brewhome"; sm_brew "$b2" "$b2/brewhome/brew"
  printf '# eval "$(%s/brew shellenv)"\neval "$(/elsewhere/bin/brew shellenv)"\n' "$b2/brewhome" > "$b2/home/.zprofile"
  sm_run "$b2" private-mode deu
  if [ "$rc" -eq 2 ] && [ "$(grep -v '^#' "$b2/home/.zprofile" | grep -cF "$b2/brewhome/brew shellenv")" = "1" ]; then
    sm_ok "a commented-out or foreign Homebrew line in the profile still gets a live line for this Homebrew"
  else sm_miss "stale profile line (rc=$rc)" "$(cat "$b2/home/.zprofile")"; fi
  rm -rf "$b2"
  # a bash account: the line joins the first of bash's login files that exists, so an existing .profile is never hidden
  # behind a new .bash_profile; with none, .bash_profile is made. A zsh account's .zprofile is left alone.
  sm_bashbox(){ b2="$(sm_box Darwin 0)"; sm_pm "$b2"; rm -f "$b2/bin/brew"; mkdir -p "$b2/brewhome"; sm_brew "$b2" "$b2/brewhome/brew"; }
  sm_bashbox; SM_SHELL=/bin/bash; sm_run "$b2" private-mode deu; SM_SHELL=""
  if [ "$rc" -eq 2 ] && [ ! -e "$b2/home/.zprofile" ] && grep -qF "$b2/brewhome/brew shellenv" "$b2/home/.bash_profile" 2>/dev/null; then sm_b1=ok; else sm_b1="no login file (rc=$rc)"; fi
  rm -rf "$b2"
  sm_bashbox; printf 'export EDITOR=vi\n' > "$b2/home/.profile"; SM_SHELL=/bin/bash; sm_run "$b2" private-mode deu; SM_SHELL=""
  if [ "$sm_b1" = ok ] && [ "$rc" -eq 2 ] && [ ! -e "$b2/home/.bash_profile" ] && [ ! -e "$b2/home/.zprofile" ] \
     && grep -qxF 'export EDITOR=vi' "$b2/home/.profile" && grep -qF "$b2/brewhome/brew shellenv" "$b2/home/.profile"; then
    sm_ok "a bash account gets the line in the login file bash reads, an existing .profile kept and never hidden"
  else sm_miss "bash account ($sm_b1; with .profile rc=$rc)" "$out"; fi
  rm -rf "$b2"
  sm_run "$b" private-mode 'P0L'; sm_c1=$rc; sm_run "$b" private-mode osd; sm_c2=$rc; sm_run "$b" private-mode; sm_c3=$rc
  # capitals under a UTF-8 locale, where bash 3.2's a-z range takes them too; nothing may reach Homebrew first
  : > "$b/brew-args"; out="$(cd "$b/root" && LC_ALL=en_US.UTF-8 HOME="$b/home" PATH="$b/bin" SETUP_APPLE_BIN="$b/bin" SETUP_BREW_DIRS="$b/brewhome" "$BASH" checks/setup-mac.sh private-mode POL 2>&1)"; sm_c4=$?
  if [ "$sm_c1" -eq 64 ] && [ "$sm_c2" -eq 64 ] && [ "$sm_c3" -eq 64 ] && [ "$sm_c4" -eq 64 ] && [ ! -s "$b/brew-args" ]; then
    sm_ok "a bad language code exits 64, capitals under a UTF-8 locale included, before any install"
  else sm_miss "bad language code (rc=$sm_c1, $sm_c2, $sm_c3, $sm_c4)" "$out"; fi
  rm -rf "$b"

  # --- handouts: the pinned Python's path reaches the rebuild script ---
  b="$(sm_box Darwin 0)"; sm_stub "$b/bin/bash" "exec '$BASH' \"\$@\""
  sm_stub "$b/bin/brew" "case \"\$1\" in list) exit 1 ;; --prefix) echo /stub/opt/\$2 ;; install) shift; echo \"\$*\" >> '$b/brew-args' ;; esac; exit 0"
  sm_stub "$b/root/_templates/handout-assets/rebuild-render-env.sh" "echo \"\$PYTHON\" > '$b/python-given'; exit \$(cat '$b/rebuild-rc' 2>/dev/null || echo 0)"
  sm_run "$b" handouts
  if [ "$rc" -eq 0 ] && [ "$(cat "$b/brew-args" 2>/dev/null)" = "python@3.14 pango cairo glib poppler" ] \
     && [ "$(cat "$b/python-given" 2>/dev/null)" = "/stub/opt/python@3.14/bin/python3.14" ] && grep -qxF "setup: handout tools complete" <<<"$out"; then
    sm_ok "handouts installs the pinned Python and libraries and gives the rebuild that Python"
  else sm_miss "handouts (rc=$rc; python: $(cat "$b/python-given" 2>/dev/null))" "$out"; fi
  mkdir -p "$b/brewhome"; mv "$b/bin/brew" "$b/brewhome/brew"; sm_run "$b" handouts
  if [ "$rc" -eq 2 ] && grep -q '^restart: ' <<<"$out" && [ "$(printf '%s\n' "$out" | tail -n 1)" = "setup: handout tools complete, once the Claude app has been reopened" ]; then
    sm_ok "handouts through a Homebrew off the app's path ends on the restart line"
  else sm_miss "handouts off the app's path (rc=$rc)" "$out"; fi
  mv "$b/brewhome/brew" "$b/bin/brew"
  echo 3 > "$b/rebuild-rc"; sm_run "$b" handouts
  if [ "$rc" -eq 1 ] && grep -qF "the handout renderer did not build" <<<"$out"; then sm_ok "a failed rebuild exits 1"
  else sm_miss "failed rebuild (rc=$rc)" "$out"; fi
  rm -rf "$b"
  # the rebuild itself, failing offline at its pip step: no staged venv is left behind for the board to find
  b="$(mktemp -d "${TMPDIR:-/tmp}/tabularium-sm.XXXXXX")"
  sm_stub "$b/py" "case \"\$1\" in --version) echo 'Python 3.14.0' ;; -m) mkdir -p \"\$3/bin\"; printf '#!/bin/sh\\nexit 1\\n' > \"\$3/bin/pip\"; chmod +x \"\$3/bin/pip\" ;; esac; exit 0"
  rr_rc=0; out="$(VENV_DIR="$b/.venv-render" PYTHON="$b/py" "$BASH" "$ROOT/_templates/handout-assets/rebuild-render-env.sh" 2>&1)" || rr_rc=$?
  if [ "$rr_rc" -ne 0 ] && [ ! -e "$b/.venv-render.new" ] && [ ! -e "$b/.venv-render" ]; then sm_ok "a rebuild that fails offline leaves no staged venv behind"
  else sm_miss "rebuild failing offline (rc=$rr_rc; staged venv left: $([ -e "$b/.venv-render.new" ] && echo yes || echo no))" "$out"; fi
  rm -rf "$b"

  sm_run_rc=0; out="$("$BASH" "$SM_SRC" nonsense 2>&1)" || sm_run_rc=$?
  if [ "$sm_run_rc" -eq 64 ]; then sm_ok "an unknown word exits 64"; else sm_miss "unknown word (rc=$sm_run_rc)"; fi
fi

# tools/private-mode/check-setup.sh — private mode's first-time setup check. Each case runs it with PATH reduced to
# a stub directory (uname and the tools as stubs, grep and awk linked in), so it sees exactly the machine the case
# describes. Test: a Mac with a too-old Python, tesseract without English, no ImageMagick and no Homebrew
# — each named with its install command, Homebrew first, exit 1; an Ollama holding other weights is reported,
# never required, and so is another row's missing language. Control: a Linux machine with every tool needed now
# and none of local masking's — macOS only said, no install command, complete, exit 0, and --summary prints that
# one line. Extra: a placeholder python3 that fails and a missing osd, with --summary's failing line; a Linux
# machine missing tools names them without install commands, exit 1.
PMS_SRC="$ROOT/tools/private-mode/check-setup.sh"
if [ ! -f "$PMS_SRC" ]; then
  echo "BITE  MISS (private-mode setup check: tools/private-mode/check-setup.sh is missing)"; fail=$((fail+1))
else
  pms_stub(){ printf '#!/bin/sh\n%s\n' "$2" > "$1"; chmod +x "$1"; }   # $1 = path · $2 = its body
  pms_dir(){ # $1 = uname answer · $2 = python3 version · $3 = tesseract's languages -> a stub directory
    local b u
    b="$(mktemp -d "${TMPDIR:-/tmp}/tabularium-pms.XXXXXX")"
    for u in grep awk; do ln -s "$(command -v "$u")" "$b/$u"; done
    pms_stub "$b/uname" "echo $1"
    pms_stub "$b/python3" "echo $2"
    pms_stub "$b/pdftoppm" "exit 0"
    pms_stub "$b/tesseract" "printf 'List of available languages (n):\\n$3\\n'"
    printf '%s\n' "$b"; }
  pb="$(pms_dir Darwin 3.8.10 'osd')"
  pms_stub "$pb/ollama" "printf 'NAME ID SIZE MODIFIED\\nqwen3.5:9b 0123456789ab 6.6GB yesterday\\n'"
  out="$(PATH="$pb" "$BASH" "$PMS_SRC" 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] \
     && [ "$(sed -n 2p <<<"$out")" = "  MISSING  Homebrew, which the brew commands below need — install it first: https://brew.sh" ] \
     && grep -qxF "  MISSING  Python 3.9 or newer (this one is 3.8.10) — install: brew install python" <<<"$out" \
     && grep -qxF "  MISSING  tesseract's language data (eng) — install: brew reinstall tesseract" <<<"$out" \
     && grep -qxF "  absent   tesseract's language data (pol), needed for a person whose number row or documents are in that language — install: brew install tesseract-lang" <<<"$out" \
     && grep -qxF "  MISSING  ImageMagick — install: brew install imagemagick" <<<"$out" \
     && grep -qF "qwen3.5:9b model, but not the weights the masking benchmark tested" <<<"$out" \
     && [ "$(tail -n 1 <<<"$out")" = "private mode setup: incomplete — missing Python 3.9 or newer, tesseract's language data (eng), ImageMagick (install commands above)" ]; then
    echo "BITE  OK  (private-mode setup check: a missing or too-old tool is named with its install command, exit 1)"; pass=$((pass+1))
  else
    echo "BITE  MISS (private-mode setup check, missing tools — rc=$rc)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi
  rm -rf "$pb"
  # extra: a fresh Mac's python3 is a placeholder that fails, and a tesseract may lack its orientation data — the
  # check must run Python, not just find it, and the installer's --summary line must say Python is everyone's
  pb="$(pms_dir Darwin 3.9.6 'eng\npol')"
  pms_stub "$pb/python3" "echo 'xcrun: error: invalid active developer path' >&2; exit 1"
  pms_stub "$pb/magick" "exit 0"
  out="$(PATH="$pb" "$BASH" "$PMS_SRC" 2>&1)"; rc=$?
  sum="$(PATH="$pb" "$BASH" "$PMS_SRC" --summary 2>&1)"; src=$?
  if [ "$rc" -eq 1 ] && [ "$src" -eq 1 ] \
     && grep -qxF "  MISSING  Python 3.9 or newer (python3 is on PATH but does not run; on a Mac, Apple's command line tools are missing) — install: xcode-select --install" <<<"$out" \
     && grep -qxF "  MISSING  tesseract's orientation data (osd) — install: brew reinstall tesseract" <<<"$out" \
     && [ "$sum" = "private mode setup: incomplete — missing Python 3.9 or newer, tesseract's orientation data (osd). Every instance needs Python, the rest only a person in private mode; install commands: bash tools/private-mode/check-setup.sh (tools/private-mode/topics/setup.md)" ]; then
    echo "BITE  OK  (private-mode setup check: a python3 that does not run and missing osd are caught, and --summary exits 1 naming Python as every instance's)"; pass=$((pass+1))
  else
    echo "BITE  MISS (private-mode setup check, placeholder Python — rc=$rc, summary rc=$src: $sum)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi
  rm -rf "$pb"
  pb="$(pms_dir Linux 3.9.6 'eng\nosd\npol')"
  pms_stub "$pb/convert" "exit 0"; pms_stub "$pb/identify" "exit 0"
  out="$(PATH="$pb" "$BASH" "$PMS_SRC" 2>&1)"; rc=$?
  sum="$(PATH="$pb" "$BASH" "$PMS_SRC" --summary 2>&1)"; src=$?
  pms_done="private mode setup: complete (local masking's tools are not needed in this release)"
  pms_mac="  NOTE     Tabularium supports macOS only; this system (Linux) gets no install commands"
  if [ "$rc" -eq 0 ] && ! grep -qF 'MISSING' <<<"$out" && [ "$(tail -n 1 <<<"$out")" = "$pms_done" ] \
     && [ "$(sed -n 2p <<<"$out")" = "$pms_mac" ] \
     && grep -qxF "  absent   zbar" <<<"$out" && grep -qxF "  absent   Ollama" <<<"$out" \
     && grep -qxF "  ok       tesseract's language data (pol)" <<<"$out" \
     && ! grep -qiE 'apt-get|brew|install:' <<<"$out" \
     && [ "$src" -eq 0 ] && [ "$sum" = "$pms_done" ]; then
    echo "BITE  OK  (private-mode setup check: on Linux with every tool needed now, it says macOS only, gives no install command, and is complete, exit 0, one summary line)"; pass=$((pass+1))
  else
    echo "BITE  MISS (private-mode setup check, complete Linux machine — rc=$rc, summary rc=$src)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi
  rm -rf "$pb"
  # off macOS a missing tool is still named, without an install command, and still exits 1
  pb="$(pms_dir Linux 3.9.6 'eng\nosd\npol')"; rm -f "$pb/pdftoppm"
  out="$(PATH="$pb" "$BASH" "$PMS_SRC" 2>&1)"; rc=$?
  sum="$(PATH="$pb" "$BASH" "$PMS_SRC" --summary 2>&1)"; src=$?
  if [ "$rc" -eq 1 ] && [ "$src" -eq 1 ] && [ "$(sed -n 2p <<<"$out")" = "$pms_mac" ] \
     && grep -qxF "  MISSING  poppler" <<<"$out" && grep -qxF "  MISSING  ImageMagick" <<<"$out" \
     && ! grep -qiE 'apt-get|brew|install:' <<<"$out" \
     && [ "$(tail -n 1 <<<"$out")" = "private mode setup: incomplete — missing poppler, ImageMagick (Tabularium supports macOS only)" ] \
     && [ "$sum" = "private mode setup: incomplete — missing poppler, ImageMagick. Needed only for a person in private mode; Tabularium supports macOS only" ]; then
    echo "BITE  OK  (private-mode setup check: on Linux a missing tool is named without an install command, exit 1, and both last lines say macOS only)"; pass=$((pass+1))
  else
    echo "BITE  MISS (private-mode setup check, Linux missing tools — rc=$rc, summary rc=$src: $sum)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi
  rm -rf "$pb"
fi

# adopt-release.sh — groups care's adoption steps. Each case runs it in a SYNTHETIC care checkout: a mktemp
# clone of a mktemp source repository. Releases v0.2.0–v0.10.0 are commits of ONE tree (a lexical sort would
# pick v0.9.0); v0.20.0 force-tracks a path under the ignored patients/. The fixture's check.sh answers
# `--instance-mode` with the REAL derivation and runs a synthetic board, its installer logs its arguments and
# pins the release. A `git` shim logs every checkout so a case can count them; the record-safety case runs
# without it, real git. Every git call strips the inherited git environment.
ADOPT="$ROOT/checks/adopt-release.sh"
if [ ! -x "$ADOPT" ]; then
  echo "BITE  MISS (adopt-release: checks/adopt-release.sh is missing or not executable)"; fail=$((fail+1))
elif ! command -v git >/dev/null 2>&1; then
  skip adopt-release "git absent — the adopt-release bites were NOT run"
else
  ar_ok(){   echo "BITE  OK  ($1)"; pass=$((pass+1)); }
  ar_miss(){ echo "BITE  MISS ($1)"; fail=$((fail+1)); }
  ar_git(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
    git -c user.name=fixture -c user.email=fixture@example.invalid -c commit.gpgsign=false -c tag.gpgsign=false \
        -c advice.detachedHead=false "$@"; }
  ar_lines(){ if [ -f "$1" ]; then awk 'END { print NR }' "$1"; else echo 0; fi; }
  ar_head(){ ar_git -C "$1" rev-parse --verify --quiet HEAD 2>/dev/null; }
  ar_tagc(){ ar_git -C "$AR_SRC" rev-parse --verify --quiet "refs/tags/$1^{commit}" 2>/dev/null; }
  AR_BIN="$(mktemp -d)"; AR_SRC="$(mktemp -d)"
  cat > "$AR_BIN/git" <<ARSHIM
#!/bin/sh
for a in "\$@"; do
  case "\$a" in checkout|switch|reset|restore) printf '%s\n' "\$*" >> "\${AR_LOG:?}"; break ;; esac
done
exec "$(command -v git)" "\$@"
ARSHIM
  chmod +x "$AR_BIN/git"
  # the source: v0.2.0 < v0.9.0 < v0.10.0, a NEWER slugged tag and two non-release tags never chosen
  : > "$AR_SRC/CLAUDE.md"; mkdir -p "$AR_SRC/checks" "$AR_SRC/lib"
  printf 'patients/\n' > "$AR_SRC/.gitignore"; printf 'release data\n' > "$AR_SRC/lib/data.txt"
  cp "$ADOPT" "$AR_SRC/checks/adopt-release.sh"; chmod +x "$AR_SRC/checks/adopt-release.sh"
  cat > "$AR_SRC/checks/check.sh" <<ARCHK
#!/usr/bin/env bash
here="\$(cd "\$(dirname "\$0")/.." && pwd)"
if [ "\${1:-}" = "--instance-mode" ]; then
  if [ -f "\$here/.fx-instance" ]; then cat "\$here/.fx-instance"; exit 0; fi
  exec bash "$CHECK" "\$@"
fi
echo "synthetic board ran"
[ ! -e "\$here/.fx-red" ] || { echo "FAIL [LX] synthetic red"; exit 1; }
echo "all guards green"
ARCHK
  cat > "$AR_SRC/checks/install-instance.sh" <<'ARINS'
#!/usr/bin/env bash
here="$(cd "$(dirname "$0")/.." && pwd)"
printf '%s\n' "$*" >> "$here/.fx-install.log"
[ ! -e "$here/.fx-install-fail" ] || { echo "synthetic installer failed"; exit 1; }
[ "${1:-}" != care ] || printf '%s\n' "${2:-}" > "$here/checks/CARE-RELEASE"
echo "synthetic installer ran"
ARINS
  chmod +x "$AR_SRC/checks/check.sh" "$AR_SRC/checks/install-instance.sh"
  ar_git -C "$AR_SRC" init -q >/dev/null 2>&1
  ar_git -C "$AR_SRC" add -A >/dev/null 2>&1
  ar_t="$(ar_git -C "$AR_SRC" write-tree 2>/dev/null)"
  ar_p=""; ar_i=0
  for ar_tags in "v0.2.0" "v0.9.0" "v0.10.0" "v0.11.0-legacy-slug v9 release-note"; do
    ar_i=$((ar_i+1))
    if [ -z "$ar_p" ]; then ar_c="$(ar_git -C "$AR_SRC" commit-tree "$ar_t" -m "release $ar_i" </dev/null 2>/dev/null)"
    else ar_c="$(ar_git -C "$AR_SRC" commit-tree "$ar_t" -p "$ar_p" -m "release $ar_i" </dev/null 2>/dev/null)"; fi
    for ar_tag in $ar_tags; do ar_git -C "$AR_SRC" tag -a -m "synthetic note" "$ar_tag" "$ar_c" >/dev/null 2>&1; done
    ar_p="$ar_c"
  done
  # ar_care <tag at HEAD> <pin> <marker> -> a fresh care checkout (origin = the source)
  ar_care(){ local b; b="$(mktemp -d)"
    ar_git clone -q --no-local --branch "$1" "$AR_SRC" "$b/care" >/dev/null 2>&1
    printf '%s\n' "$3" > "$b/care/.tabularium-instance"
    printf '%s\n' "$2" > "$b/care/checks/CARE-RELEASE"
    printf '%s\n' "$b/care"; }
  # ar_run <care checkout> [args] -> output in ar_out, rc in ar_rc; git env stripped, checkouts logged
  ar_run(){ local d="$1"; shift
    ar_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      AR_LOG="$d/.fx-checkout.log" PATH="$AR_BIN:$PATH" bash "$d/checks/adopt-release.sh" "$@" 2>&1)"; ar_rc=$?; }
  ar_rm(){ case "$1" in */care) chmod -R u+w "$1" 2>/dev/null; rm -rf "$(dirname "$1")" ;; esac; }

  if [ "$(ar_git -C "$AR_SRC" tag | awk 'END { print NR }')" != "6" ]; then
    ar_miss "adopt-release: the synthetic source did not build (tags=$(ar_git -C "$AR_SRC" tag | tr '\n' ' '))"
  else
    # control: no argument adopts the NEWEST strict release — numeric order, slugged and non-release tags
    # ignored — really checks it out, then runs that release's installer with the tag, then the board
    d="$(ar_care v0.9.0 v0.9.0 care)"; ar_run "$d"
    if [ "$ar_rc" -eq 0 ] && [ "$(ar_lines "$d/.fx-checkout.log")" = "1" ] \
       && grep -q 'checkout --no-overwrite-ignore --quiet refs/tags/v0\.10\.0$' "$d/.fx-checkout.log" \
       && [ "$(ar_head "$d")" = "$(ar_tagc v0.10.0)" ] \
       && [ "$(cat "$d/.fx-install.log" 2>/dev/null)" = "care v0.10.0" ] \
       && grep -qF 'v0.10.0 adopted and the board is green' <<<"$ar_out"; then
      ar_ok "adopt-release: no argument adopts the newest vX.Y.Z (v0.10.0 over v0.9.0, the slugged v0.11.0 and non-release tags), HEAD moved, installer then board"
    else
      ar_miss "adopt-release newest (rc=$ar_rc, checkouts=$(tr '\n' ';' < "$d/.fx-checkout.log" 2>/dev/null), installs=$(tr '\n' ';' < "$d/.fx-install.log" 2>/dev/null))"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # v0.20.0 differs from the base tree and is built LAST, so it cannot change which release the control
    # calls the newest. A release that tracks a path where an ignored record sits is refused by real git:
    # HEAD, pin and the record's bytes unchanged, nothing installed.
    ar_bl="$(printf 'the release copy\n' | ar_git -C "$AR_SRC" hash-object -w --stdin 2>/dev/null)"
    ar_tx="$(printf '100644 blob %s\tprofile.md\n' "$ar_bl" | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_tp="$(printf '040000 tree %s\tx\n' "$ar_tx" | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_t20="$({ ar_git -C "$AR_SRC" ls-tree "$ar_t"; printf '040000 tree %s\tpatients\n' "$ar_tp"; } | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_c20="$(ar_git -C "$AR_SRC" commit-tree "$ar_t20" -p "$ar_p" -m "release tracking a record path" </dev/null 2>/dev/null)"
    ar_git -C "$AR_SRC" tag -a -m "synthetic note" v0.20.0 "$ar_c20" >/dev/null 2>&1
    d="$(ar_care v0.9.0 v0.9.0 care)"; mkdir -p "$d/patients/x"; printf 'the care record\n' > "$d/patients/x/profile.md"
    ar_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      bash "$d/checks/adopt-release.sh" v0.20.0 2>&1)"; ar_rc=$?
    if [ -n "$ar_c20" ] && [ "$ar_rc" -eq 1 ] && grep -qF 'would replace an untracked or ignored file' <<<"$ar_out" \
       && [ "$(cat "$d/patients/x/profile.md" 2>/dev/null)" = "the care record" ] \
       && [ "$(ar_head "$d")" = "$(ar_tagc v0.9.0)" ] && [ "$(cat "$d/checks/CARE-RELEASE")" = "v0.9.0" ] \
       && [ ! -e "$d/.fx-install.log" ]; then
      ar_ok "adopt-release: a release tracking an ignored record's path is refused by real git; the record is untouched"
    else
      ar_miss "adopt-release record safety (rc=$ar_rc, record now: $(cat "$d/patients/x/profile.md" 2>/dev/null))"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"

    # ADR-0055 point 4. ar_follow <care checkout>: the operator's hands — the FIRST printed
    # one-line recovery, run as printed in one shell in the care checkout, inherited git variables
    # stripped (rc in ar_frc, output in ar_fout).
    ar_follow(){ local l; l="$(awk '/^  (unset|rm -f) /{ print; exit }' <<<"$ar_out")"
      ar_fout="$(cd "$1" || exit 1; env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
        bash -c "${l#  }" 2>&1)"; ar_frc=$?
      [ -n "$l" ] || ar_frc=99; }
    ar_ended_on(){ # <care checkout> <tag> -> 0 if HEAD, pin, installer and board all say the tag
      [ "$ar_frc" -eq 0 ] && [ "$(ar_head "$1")" = "$(ar_tagc "$2")" ] && [ "$(cat "$1/checks/CARE-RELEASE" 2>/dev/null)" = "$2" ] \
        && [ "$(tail -1 "$1/.fx-install.log" 2>/dev/null)" = "care $2" ] && grep -qF 'synthetic board ran' <<<"$ar_fout" \
        && [ -z "$(ar_git -C "$1" status --porcelain --untracked-files=no 2>/dev/null)" ]; }
    # test (failure 2): a red board, then the same command again before rolling back — the pin now names
    # the release, and the way back is read from HEAD's reflog instead of "nothing to roll back"
    d="$(ar_care v0.9.0 v0.9.0 care)"; : > "$d/.fx-red"
    ar_run "$d" v0.10.0; ar_run "$d" v0.10.0
    if [ "$ar_rc" -eq 2 ] && grep -qF 'came from v0.9.0' <<<"$ar_out" \
       && grep -qxF '  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY && git checkout --no-overwrite-ignore refs/tags/v0.9.0 && bash checks/install-instance.sh care v0.9.0 && bash checks/check.sh' <<<"$ar_out"; then
      ar_ok "adopt-release: a re-run after a red board finds the previous release in HEAD's reflog and prints the way back as one line"
    else
      ar_miss "adopt-release reflog fallback (rc=$ar_rc)"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # control: a checkout cloned at the release itself has no such reflog entry — it says so plainly and
    # names no release to return to
    d="$(ar_care v0.10.0 v0.10.0 care)"; : > "$d/.fx-red"; ar_run "$d" v0.10.0
    if [ "$ar_rc" -eq 2 ] && grep -qF "names no earlier release" <<<"$ar_out" && ! grep -q '^  unset ' <<<"$ar_out"; then
      ar_ok "adopt-release: with no earlier release in HEAD's reflog it says so and invents none"
    else
      ar_miss "adopt-release reflog fallback, none found (rc=$ar_rc)"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # v0.30.0 changes lib/data.txt, adds lib/new.txt and lib/more.txt and tracks _shared/med/note.md (a
    # record-set path, so only the cleanup's record-set belt spares an identical untracked copy of it).
    # Built after the newest-release control, as v0.20.0 is.
    ar_b1="$(printf 'release data, changed in v0.30.0\n' | ar_git -C "$AR_SRC" hash-object -w --stdin 2>/dev/null)"
    ar_b2="$(printf 'a file new in v0.30.0\n' | ar_git -C "$AR_SRC" hash-object -w --stdin 2>/dev/null)"
    ar_b3="$(printf 'synthetic shared note\n' | ar_git -C "$AR_SRC" hash-object -w --stdin 2>/dev/null)"
    ar_b4="$(printf 'another file new in v0.30.0, long enough that a stopped write leaves part of it\n' | ar_git -C "$AR_SRC" hash-object -w --stdin 2>/dev/null)"
    ar_tl="$(printf '100644 blob %s\tdata.txt\n100644 blob %s\tnew.txt\n100644 blob %s\tmore.txt\n' "$ar_b1" "$ar_b2" "$ar_b4" | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_tm="$(printf '100644 blob %s\tnote.md\n' "$ar_b3" | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_ts="$(printf '040000 tree %s\tmed\n' "$ar_tm" | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_t30="$({ ar_git -C "$AR_SRC" ls-tree "$ar_t" | grep -v "$(printf '\t')lib\$"
      printf '040000 tree %s\tlib\n040000 tree %s\t_shared\n' "$ar_tl" "$ar_ts"; } | ar_git -C "$AR_SRC" mktree 2>/dev/null)"
    ar_c30="$(ar_git -C "$AR_SRC" commit-tree "$ar_t30" -p "$ar_p" -m "release changing lib" </dev/null 2>/dev/null)"
    ar_git -C "$AR_SRC" tag -a -m "synthetic note" v0.30.0 "$ar_c30" >/dev/null 2>&1
    ar_new='  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY && git checkout HEAD -- . && git checkout --no-overwrite-ignore refs/tags/v0.30.0 && bash checks/install-instance.sh care v0.30.0 && bash checks/check.sh'
    # a git that stops a checkout of v0.30.0 partway, as a killed one does: two of its files written,
    # HEAD and the index unmoved
    AR_STOP="$(mktemp -d)"
    cat > "$AR_STOP/git" <<ARSTOP
#!/bin/sh
case " \$* " in
  *" checkout "*" refs/tags/v0.30.0 "*)
    [ "\$1" = -C ] && cd "\$2"
    "$(command -v git)" show refs/tags/v0.30.0:lib/data.txt > lib/data.txt
    "$(command -v git)" show refs/tags/v0.30.0:lib/new.txt > lib/new.txt
    exit 1 ;;
esac
exec "$(command -v git)" "\$@"
ARSTOP
    chmod +x "$AR_STOP/git"
    # test (failure 3): a checkout of v0.30.0 that stops with HEAD unmoved leaves lib/data.txt half-new
    # and lib/new.txt an untracked copy, over which the next checkout aborts. Both ways it is met — in
    # the run where git stops, and in a re-run after a kill — remove that copy and print one && line
    # which, followed as printed, ends on v0.30.0: installed, pinned, boarded
    ar_3a=""; ar_3b=""
    d="$(ar_care v0.9.0 v0.9.0 care)"
    ar_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      PATH="$AR_STOP:$PATH" bash "$d/checks/adopt-release.sh" v0.30.0 2>&1)"; ar_rc=$?
    if [ -n "$ar_c30" ] && [ "$ar_rc" -eq 2 ] && grep -qF 'did not complete' <<<"$ar_out" && [ "$(ar_head "$d")" = "$(ar_tagc v0.9.0)" ] \
       && [ ! -e "$d/lib/new.txt" ] && [ ! -e "$d/.fx-install.log" ] && grep -qxF "$ar_new" <<<"$ar_out"; then
      ar_follow "$d"; ar_ended_on "$d" v0.30.0 && ar_3a=ok
    fi
    [ -n "$ar_3a" ] || { echo "      git stopped mid-run (rc=$ar_rc, follow rc=${ar_frc:-})"; echo "$ar_out" | sed 's/^/      /'; }
    ar_rm "$d"
    d="$(ar_care v0.9.0 v0.9.0 care)"
    ar_git -C "$AR_SRC" show v0.30.0:lib/data.txt > "$d/lib/data.txt"
    ar_git -C "$AR_SRC" show v0.30.0:lib/new.txt > "$d/lib/new.txt"
    ar_run "$d" v0.30.0
    if [ -n "$ar_c30" ] && [ "$ar_rc" -eq 1 ] && grep -qF 'stopped partway' <<<"$ar_out" && [ ! -e "$d/lib/new.txt" ] \
       && grep -qF 'removed 1 untracked file(s)' <<<"$ar_out" && grep -qxF "$ar_new" <<<"$ar_out"; then
      ar_follow "$d"; ar_ended_on "$d" v0.30.0 && ar_3b=ok
    fi
    [ -n "$ar_3b" ] || { echo "      re-run after a kill (rc=$ar_rc, follow rc=${ar_frc:-})"; echo "$ar_out" | sed 's/^/      /'; echo "$ar_fout" | sed 's/^/      | /'; }
    ar_rm "$d"
    if [ -n "$ar_3a" ] && [ -n "$ar_3b" ]; then
      ar_ok "adopt-release: a checkout stopped with HEAD unmoved — met when git stops and on a re-run after a kill — loses only the release's own untracked copy and prints one && line that ends on the release"
    else
      ar_miss "adopt-release stopped checkout (git stopped mid-run: ${ar_3a:-MISS}; re-run after a kill: ${ar_3b:-MISS})"
    fi
    # control: the same re-run, but nothing untracked is that release's copy where it may go — lib/new.txt
    # holds other bytes, lib/mine.txt is not in the release, _shared/med/note.md is byte-identical but a
    # record-set path, and the record under patients/ is ignored: every one comes through unchanged. Fifty
    # more of the operator's files make the set large enough for the progress line, and they stay too
    d="$(ar_care v0.9.0 v0.9.0 care)"; mkdir -p "$d/_shared/med" "$d/patients/x" "$d/notes"
    x=0; while [ "$x" -lt 50 ]; do x=$((x+1)); printf 'note %s\n' "$x" > "$d/notes/n$x.txt"; done
    ar_git -C "$AR_SRC" show v0.30.0:lib/data.txt > "$d/lib/data.txt"
    printf 'the operator wrote this\n' > "$d/lib/new.txt"; printf "the operator's own file\n" > "$d/lib/mine.txt"
    ar_git -C "$AR_SRC" show v0.30.0:_shared/med/note.md > "$d/_shared/med/note.md"
    printf 'record  _shared/med/\nrecord  patients/\n' > "$d/checks/RECORD-SET"
    printf 'the care record\n' > "$d/patients/x/profile.md"
    ar_kd="$(dirname "$d")/kept"; mkdir -p "$ar_kd"
    for x in lib/new.txt lib/mine.txt _shared/med/note.md patients/x/profile.md; do cp "$d/$x" "$ar_kd/$(printf '%s' "$x" | tr '/' '_')"; done
    ar_run "$d" v0.30.0; ar_same=1
    for x in lib/new.txt lib/mine.txt _shared/med/note.md patients/x/profile.md; do
      cmp -s "$d/$x" "$ar_kd/$(printf '%s' "$x" | tr '/' '_')" || ar_same=0
    done
    [ "$(ls "$d/notes" | awk 'END { print NR }')" = "50" ] || ar_same=0
    if [ "$ar_rc" -eq 1 ] && [ "$ar_same" -eq 1 ] && ! grep -qF 'removed' <<<"$ar_out" && grep -qxF "$ar_new" <<<"$ar_out" \
       && grep -qF 'removing up to 5' <<<"$ar_out"; then
      ar_ok "adopt-release: a file of other bytes, the operator's own, a record-set path and a record all survive the cleanup; a large set is announced"
    else
      ar_miss "adopt-release cleanup scope (rc=$ar_rc, all byte-identical=$ar_same)"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"; rm -rf "$AR_STOP"
    # test (a write git was killed in): the re-run meets lib/more.txt cut to 0 bytes and lib/new.txt cut
    # to its first 8 — each a strict prefix of v0.30.0's own file, which would still block the checkout.
    # Both are removed as partly written copies, and the printed line, followed, ends on the release
    d="$(ar_care v0.9.0 v0.9.0 care)"
    ar_git -C "$AR_SRC" show v0.30.0:lib/data.txt > "$d/lib/data.txt"
    ar_git -C "$AR_SRC" show v0.30.0:lib/new.txt | head -c 8 > "$d/lib/new.txt"; : > "$d/lib/more.txt"
    ar_run "$d" v0.30.0
    if [ "$ar_rc" -eq 1 ] && [ ! -e "$d/lib/new.txt" ] && [ ! -e "$d/lib/more.txt" ] \
       && grep -qF 'removed 2 untracked file(s)' <<<"$ar_out" && grep -qF 'partly written copy' <<<"$ar_out" \
       && grep -qxF "$ar_new" <<<"$ar_out"; then
      ar_follow "$d"
      if ar_ended_on "$d" v0.30.0; then
        ar_ok "adopt-release: partly written copies (a strict prefix, 0 bytes included) are removed and the printed line ends on the release"
      else
        ar_miss "adopt-release partial copies, followed (follow rc=$ar_frc)"; echo "$ar_fout" | sed 's/^/      | /'
      fi
    else
      ar_miss "adopt-release partial copies (rc=$ar_rc)"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # control: at the same paths, a file LONGER than the release's (its bytes plus the operator's) and a
    # shorter one that is not its start — neither is a partly written copy; both stay byte-identical
    d="$(ar_care v0.9.0 v0.9.0 care)"
    ar_git -C "$AR_SRC" show v0.30.0:lib/data.txt > "$d/lib/data.txt"
    { ar_git -C "$AR_SRC" show v0.30.0:lib/new.txt; printf 'and a line the operator added\n'; } > "$d/lib/new.txt"
    printf 'zzz\n' > "$d/lib/more.txt"
    cp "$d/lib/new.txt" "$(dirname "$d")/new.orig"; cp "$d/lib/more.txt" "$(dirname "$d")/more.orig"
    ar_run "$d" v0.30.0
    if [ "$ar_rc" -eq 1 ] && cmp -s "$d/lib/new.txt" "$(dirname "$d")/new.orig" && cmp -s "$d/lib/more.txt" "$(dirname "$d")/more.orig" \
       && ! grep -qF 'removed' <<<"$ar_out" && grep -qxF "$ar_new" <<<"$ar_out"; then
      ar_ok "adopt-release: a longer file and a shorter one of other bytes at release paths are kept"
    else
      ar_miss "adopt-release partial-copy scope (rc=$ar_rc)"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # ar_killed <care checkout>: what a git killed mid-checkout of v0.30.0 leaves, its index lock included
    ar_killed(){ ar_git -C "$AR_SRC" show v0.30.0:lib/data.txt > "$1/lib/data.txt"
      ar_git -C "$AR_SRC" show v0.30.0:lib/new.txt > "$1/lib/new.txt"; : > "$1/.git/index.lock"; }
    # test (the index lock a killed git leaves): every git command that writes the index stops on it, so
    # the printed line must remove it first — with the reason said — and, followed, end on the release
    d="$(ar_care v0.9.0 v0.9.0 care)"; ar_killed "$d"; ar_run "$d" v0.30.0
    if [ "$ar_rc" -eq 1 ] && grep -qF "index lock (.git/index.lock) was left by a git that stopped" <<<"$ar_out" \
       && grep -qxF "  rm -f .git/index.lock && ${ar_new#  }" <<<"$ar_out" && [ -e "$d/.git/index.lock" ]; then
      ar_follow "$d"
      if ar_ended_on "$d" v0.30.0 && [ ! -e "$d/.git/index.lock" ]; then
        ar_ok "adopt-release: a stale index lock is removed by the printed line's first link, said why, and the line ends on the release"
      else
        ar_miss "adopt-release stale lock, followed (follow rc=$ar_frc)"; echo "$ar_fout" | sed 's/^/      | /'
      fi
    else
      ar_miss "adopt-release stale lock (rc=$ar_rc, lock still there=$([ -e "$d/.git/index.lock" ] && echo yes || echo no))"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # control: the same state without a lock — no rm link, nothing said about a lock
    d="$(ar_care v0.9.0 v0.9.0 care)"; ar_killed "$d"; rm -f "$d/.git/index.lock"; ar_run "$d" v0.30.0
    if [ "$ar_rc" -eq 1 ] && grep -qxF "$ar_new" <<<"$ar_out" && ! grep -qF 'rm -f' <<<"$ar_out" && ! grep -qF 'index lock' <<<"$ar_out"; then
      ar_ok "adopt-release: with no index lock the printed line carries no rm link"
    else
      ar_miss "adopt-release no lock (rc=$ar_rc)"; echo "$ar_out" | sed 's/^/      /'
    fi
    ar_rm "$d"
    # extra: the lock with a git still working in this checkout (a reader on a fifo the suite holds open)
    # — never an rm link then. It backgrounds a process, so it skips under TABULARIUM_NO_HOOK_TEST and
    # reaps the process before going on.
    if [ -n "${TABULARIUM_NO_HOOK_TEST:-}" ] || ! command -v mkfifo >/dev/null 2>&1; then
      skip adopt-release-lock "adopt-release lock with a live git — needs a background process (TABULARIUM_NO_HOOK_TEST set, or no mkfifo), NOT run here"
    else
      d="$(ar_care v0.9.0 v0.9.0 care)"; ar_killed "$d"; ar_fifo="$(dirname "$d")/fifo"; mkfifo "$ar_fifo"
      env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
        git -C "$d" cat-file --batch <"$ar_fifo" >/dev/null 2>&1 &
      ar_live=$!; exec 7>"$ar_fifo"
      ar_run "$d" v0.30.0
      exec 7>&-; kill "$ar_live" 2>/dev/null; wait "$ar_live" 2>/dev/null
      if [ "$ar_rc" -eq 1 ] && grep -qF 'a git process may still be running' <<<"$ar_out" && grep -qxF "$ar_new" <<<"$ar_out" \
         && ! grep -qF 'rm -f' <<<"$ar_out" && [ -e "$d/.git/index.lock" ]; then
        ar_ok "adopt-release: while a git works in the checkout the lock is never offered for removal"
      else
        ar_miss "adopt-release lock with a live git (rc=$ar_rc)"; echo "$ar_out" | sed 's/^/      /'
      fi
      ar_rm "$d"
    fi
  fi
  rm -rf "$AR_BIN" "$AR_SRC"
fi

# release-notice.sh and its Claude Code adapter — the care-side release notice (ADR-0055 companion, accepted
# 2026-10-25). The REAL script runs in a SYNTHETIC care checkout: a mktemp clone of a mktemp source whose
# releases are v0.9.0 < v0.10.0 < v0.10.1 (a lexical sort would pick v0.9.0), beside tags of every other
# shape — slugged, unprefixed, two-part, pre-release, a ten-digit number — that are never chosen. The
# fixture's check.sh answers `--instance-mode` from a file each case writes and passes `--release-name` to
# the real board; HOME is a mktemp folder, so the opt-out file is the case's own. Test: a pin a MINOR or a
# MAJOR behind speaks (exit 1). Control: a patch behind and up to date stay silent (exit 0). Extras: a
# legacy slugged pin compares by its numbers; the network cap returns in seconds and kills what git
# started; a failing remote's address never reaches the output; --daily asks origin at most once a day,
# keeps its stamp out of the working tree and stops at the opt-out file; outside care it is inert. The
# adapter prints its one line only for exit 1 with a MINOR or MAJOR gap and two release-shaped names.
RN="$ROOT/checks/release-notice.sh"
RNA="$ROOT/tools/claude-hooks/release-notice.py"
if [ ! -x "$RN" ] || [ ! -f "$RNA" ]; then
  echo "BITE  MISS (release-notice: checks/release-notice.sh is missing or not executable, or its adapter is missing)"; fail=$((fail+1))
elif ! command -v git >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  skip release-notice "git or python3 absent — the release-notice bites were NOT run"
else
  rn_ok(){   echo "BITE  OK  ($1)"; pass=$((pass+1)); }
  rn_miss(){ echo "BITE  MISS ($1)"; fail=$((fail+1)); }
  rn_git(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
    git -c user.name=fixture -c user.email=fixture@example.invalid -c commit.gpgsign=false -c tag.gpgsign=false "$@"; }
  RN_TMP="$(mktemp -d)"; RN_SRC="$RN_TMP/src"; RN_C="$RN_TMP/care"; RN_HOME="$RN_TMP/home"
  mkdir -p "$RN_SRC/checks" "$RN_HOME"; : > "$RN_SRC/CLAUDE.md"
  cp "$RN" "$RN_SRC/checks/release-notice.sh"; chmod +x "$RN_SRC/checks/release-notice.sh"
  cat > "$RN_SRC/checks/check.sh" <<RNCHK
#!/usr/bin/env bash
if [ "\${1:-}" = "--instance-mode" ]; then cat "\$(cd "\$(dirname "\$0")/.." && pwd)/.fx-instance" 2>/dev/null; exit 0; fi
exec bash "$CHECK" "\$@"
RNCHK
  rn_git -C "$RN_SRC" init -q >/dev/null 2>&1; rn_git -C "$RN_SRC" add -A >/dev/null 2>&1
  rn_git -C "$RN_SRC" commit -q -m release >/dev/null 2>&1
  for rn_t in v0.9.0 v0.10.0 v0.10.1 v0.11.0-slug x1.0.0 v2 v1.2 v0.12.0-rc1 v1234567890.0.0; do
    rn_git -C "$RN_SRC" tag -a -m "synthetic note" "$rn_t" >/dev/null 2>&1
  done
  rn_git clone -q --no-local "$RN_SRC" "$RN_C" >/dev/null 2>&1
  rn_inst(){ printf 'kind=main\nstatus=n/a\nmarker=%s\nmarker_state=ok\nreason=\nfamily=%s\n' "$1" "$RN_C" > "$RN_C/.fx-instance"; }
  rn_pin(){ printf '%s\n' "$1" > "$RN_C/checks/CARE-RELEASE"; }
  rn_run(){ rn_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
    HOME="$RN_HOME" bash "$RN_C/checks/release-notice.sh" "$@" 2>&1)"; rn_rc=$?; }
  rn_v(){ sed -n "s/^$1=//p" <<<"$rn_out"; }
  rn_is(){ [ "$rn_rc" = "$1" ] && [ "$(rn_v pinned)" = "$2" ] && [ "$(rn_v newest)" = "$3" ] && [ "$(rn_v gap)" = "$4" ] \
    && [ "$(rn_v status)" = "$5" ] && [ "$(rn_v reason)" = "$6" ] \
    && [ "$(sed 's/=.*//' <<<"$rn_out" | tr '\n' ' ')" = "pinned newest gap status reason " ]; }
  rn_stamp="$RN_C/.git/tabularium-release-check-$(date +%Y-%m-%d)"   # today's claim
  rn_stamps(){ ls "$RN_C/.git/" 2>/dev/null | grep -c '^tabularium-release-check'; }
  rn_inst care
  if [ "$(rn_git -C "$RN_C" tag | awk 'END { print NR }')" != "9" ]; then
    rn_miss "release-notice: the synthetic source did not build (tags=$(rn_git -C "$RN_C" tag | tr '\n' ' '))"
  else
    # test: a pin a MINOR behind the newest strict release speaks — exit 1, five fixed lines
    rn_pin v0.9.0; rn_run
    if rn_is 1 v0.9.0 v0.10.1 minor ok ""; then
      rn_ok "release-notice: a pin a MINOR behind speaks (v0.10.1 over v0.9.0, every other tag shape ignored), exit 1, five fixed lines"
    else rn_miss "release-notice, minor gap (rc=$rn_rc)"; echo "$rn_out" | sed 's/^/      /'; fi
    # control: a patch behind, and up to date, stay silent — exit 0
    rn_pin v0.10.0; rn_run; rn_a="$rn_rc"; rn_ap="$(rn_v gap)"
    rn_pin v0.10.1; rn_run
    if [ "$rn_a" = "0" ] && [ "$rn_ap" = "patch" ] && rn_is 0 v0.10.1 v0.10.1 none ok ""; then
      rn_ok "release-notice: a patch behind and up to date are silent, exit 0"
    else rn_miss "release-notice, silent cases (patch rc=$rn_a gap=$rn_ap; current rc=$rn_rc)"; echo "$rn_out" | sed 's/^/      /'; fi
    # extra: a legacy slugged pin is that release by its numbers, not a pre-release — one a MINOR behind
    # speaks, one ahead stays silent; no pin is no answer
    rn_pin v0.9.0-legacy-slug; rn_run; rn_b="$rn_rc"; rn_bp="$(rn_v gap)"
    rn_pin v0.52.0-legacy-slug; rn_run; rn_a="$rn_rc"; rn_ap="$(rn_v gap)"
    rn_pin ""; rn_run
    if [ "$rn_b" = "1" ] && [ "$rn_bp" = "minor" ] && [ "$rn_a" = "0" ] && [ "$rn_ap" = "none" ] && rn_is 2 "" "" none no-pin ""; then
      rn_ok "release-notice: a legacy slugged pin compares by its numbers (behind speaks, ahead is silent); no pin is status no-pin, exit 2"
    else rn_miss "release-notice, slugged pin or no pin (behind rc=$rn_b gap=$rn_bp; ahead rc=$rn_a gap=$rn_ap; no pin rc=$rn_rc)"; echo "$rn_out" | sed 's/^/      /'; fi
    # test: a MAJOR behind speaks too
    rn_git -C "$RN_SRC" tag -a -m "synthetic note" v1.0.0 >/dev/null 2>&1
    rn_pin v0.10.1; rn_run
    if rn_is 1 v0.10.1 v1.0.0 major ok ""; then
      rn_ok "release-notice: a pin a MAJOR behind speaks, exit 1"
    else rn_miss "release-notice, major gap (rc=$rn_rc)"; echo "$rn_out" | sed 's/^/      /'; fi
    rn_git -C "$RN_SRC" tag -d v1.0.0 >/dev/null 2>&1
    # extra: a remote that fails — its address, a planted marker, never reaches the output
    rn_git -C "$RN_C" remote set-url origin "$RN_TMP/no-such-repo-PLANTED7Q" >/dev/null 2>&1
    rn_pin v0.9.0; rn_run
    if rn_is 2 v0.9.0 "" none unreachable failed && ! grep -qF PLANTED7Q <<<"$rn_out"; then
      rn_ok "release-notice: a failing remote is status unreachable, and its address never reaches the output"
    else rn_miss "release-notice, failing remote (rc=$rn_rc, address shown=$(grep -c PLANTED7Q <<<"$rn_out"))"; echo "$rn_out" | sed 's/^/      /'; fi
    # extra: the cap — a remote that never answers (an ssh stand-in that sleeps) returns within seconds as a
    # timeout, and the stand-in is killed with git
    printf '#!/bin/sh\necho "$$" > "%s/sleeper.pid"\nexec sleep 30\n' "$RN_TMP" > "$RN_TMP/sleeper"; chmod +x "$RN_TMP/sleeper"
    rn_git -C "$RN_C" remote set-url origin "ssh://fx.invalid/repo" >/dev/null 2>&1
    rn_t0="$(date +%s)"
    rn_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      HOME="$RN_HOME" GIT_SSH_COMMAND="$RN_TMP/sleeper" bash "$RN_C/checks/release-notice.sh" 2>&1)"; rn_rc=$?
    rn_dt=$(( $(date +%s) - rn_t0 )); sleep 1
    rn_alive=no; [ -f "$RN_TMP/sleeper.pid" ] && kill -0 "$(cat "$RN_TMP/sleeper.pid")" 2>/dev/null && rn_alive=yes
    if rn_is 2 v0.9.0 "" none unreachable timeout && [ "$rn_dt" -le 9 ] && [ -f "$RN_TMP/sleeper.pid" ] && [ "$rn_alive" = no ]; then
      rn_ok "release-notice: a remote that never answers is cut off within seconds (${rn_dt}s) and what git started is killed"
    else
      rn_miss "release-notice, network cap (rc=$rn_rc, ${rn_dt}s, stand-in ran=$([ -f "$RN_TMP/sleeper.pid" ] && echo yes || echo no), still alive=$rn_alive)"
      echo "$rn_out" | sed 's/^/      /'; [ "$rn_alive" = no ] || kill "$(cat "$RN_TMP/sleeper.pid")" 2>/dev/null
    fi
    # extra: --daily asks origin at most once a day, a failed attempt included — the first run, against an
    # origin that never answers, times out and has already stamped git's own directory (the working tree's
    # status is unchanged); the second, with origin answering again, says checked-today at once and asks
    # nothing; a stamp from another day does not stop it; the opt-out file stops it and writes no stamp
    rn_git -C "$RN_C" remote set-url origin "ssh://fx.invalid/repo" >/dev/null 2>&1; rm -f "$RN_C"/.git/tabularium-release-check*
    rn_st0="$(rn_git -C "$RN_C" status --porcelain --untracked-files=all 2>/dev/null)"
    rn_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      HOME="$RN_HOME" GIT_SSH_COMMAND="$RN_TMP/sleeper" bash "$RN_C/checks/release-notice.sh" --daily 2>&1)"; rn_rc=$?
    rn_a="$rn_rc"; rn_ar="$(rn_v reason)"
    rn_st1="$(rn_git -C "$RN_C" status --porcelain --untracked-files=all 2>/dev/null)"
    rn_git -C "$RN_C" remote set-url origin "$RN_SRC" >/dev/null 2>&1
    rn_t0="$(date +%s)"; rn_run --daily; rn_dt=$(( $(date +%s) - rn_t0 ))
    if [ "$rn_a" = "2" ] && [ "$rn_ar" = "timeout" ] && [ -f "$rn_stamp" ] && [ "$(rn_stamps)" = "1" ] \
       && [ "$rn_st0" = "$rn_st1" ] && rn_is 2 v0.9.0 "" none off checked-today && [ "$rn_dt" -le 2 ]; then
      rn_ok "release-notice --daily: one attempt a day, a failed one included, stamped in git's own directory with the working tree unchanged"
    else rn_miss "release-notice --daily (first rc=$rn_a reason=$rn_ar, stamps=$(rn_stamps), tree unchanged=$([ "$rn_st0" = "$rn_st1" ] && echo yes || echo no), second rc=$rn_rc ${rn_dt}s)"; echo "$rn_out" | sed 's/^/      /'; fi
    rm -f "$RN_C"/.git/tabularium-release-check*; : > "$RN_C/.git/tabularium-release-check-2000-01-01"
    : > "$RN_C/.git/tabularium-release-check-2999-12-31"   # a later day's claim, as after a midnight rollover
    rn_run --daily; rn_a="$rn_rc"
    rn_ao="$([ -e "$RN_C/.git/tabularium-release-check-2000-01-01" ] && echo kept || echo gone)$([ -e "$RN_C/.git/tabularium-release-check-2999-12-31" ] && echo /later-kept || echo /later-gone)"
    rm -f "$RN_C"/.git/tabularium-release-check*; mkdir -p "$RN_HOME/.config/tabularium"; : > "$RN_HOME/.config/tabularium/release-notice-off"
    rn_run --daily
    if [ "$rn_a" = "1" ] && [ "$rn_ao" = "gone/later-kept" ] && rn_is 2 v0.9.0 "" none off opted-out && [ "$(rn_stamps)" = "0" ]; then
      rn_ok "release-notice --daily: an earlier day's stamp does not stop it and is cleared, a later day's is kept; the opt-out file stops it, with nothing written"
    else rn_miss "release-notice --daily, old stamp and opt-out (old-stamp rc=$rn_a, old stamp $rn_ao, opted-out rc=$rn_rc, stamps=$(rn_stamps))"; echo "$rn_out" | sed 's/^/      /'; fi
    rm -rf "$RN_HOME/.config"
    # extra: four care sessions starting at the same moment, origin never answering — the day is claimed
    # exclusively, so exactly one asks (and times out) and the other three answer checked-today
    rm -f "$RN_C"/.git/tabularium-release-check*
    rn_git -C "$RN_C" remote set-url origin "ssh://fx.invalid/repo" >/dev/null 2>&1
    for rn_k in 1 2 3 4; do
      env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
        HOME="$RN_HOME" GIT_SSH_COMMAND="$RN_TMP/sleeper" bash "$RN_C/checks/release-notice.sh" --daily > "$RN_TMP/par.$rn_k" 2>&1 &
    done
    wait
    rn_git -C "$RN_C" remote set-url origin "$RN_SRC" >/dev/null 2>&1
    rn_pt="$(cat "$RN_TMP"/par.* | grep -c '^reason=timeout$')"; rn_pc="$(cat "$RN_TMP"/par.* | grep -c '^reason=checked-today$')"
    if [ "$rn_pt" = "1" ] && [ "$rn_pc" = "3" ]; then
      rn_ok "release-notice --daily: four sessions starting at once — exactly one asks origin"
    else rn_miss "release-notice --daily, simultaneous starts (asked=$rn_pt, checked-today=$rn_pc)"; cat "$RN_TMP"/par.* | sed 's/^/      /'; fi
    rm -f "$RN_C"/.git/tabularium-release-check*
    # extra: inert outside care — the fixture marked dev, and the live tree, answer not-care without a call
    rn_inst dev; rn_run --daily; rn_a="$rn_rc"; rn_ar="$(rn_v reason)"
    printf 'kind=worktree\nstatus=ok\nmarker=care\nmarker_state=ok\nreason=\nfamily=%s\n' "$RN_C" > "$RN_C/.fx-instance"
    rn_run --daily; rn_w="$rn_rc"; rn_wr="$(rn_v reason)"; rn_inst care
    rn_live="$(HOME="$RN_HOME" bash "$RN" 2>&1)"
    if [ "$rn_a" = "2" ] && [ "$rn_ar" = "not-care" ] && [ "$rn_w" = "2" ] && [ "$rn_wr" = "not-care" ] && [ "$(rn_stamps)" = "0" ] \
       && grep -qx 'reason=not-care' <<<"$rn_live"; then
      rn_ok "release-notice: inert outside a care main checkout — a tree marked dev, a worktree of a care family and the live tree answer not-care, nothing written"
    else rn_miss "release-notice, inert (dev rc=$rn_a reason=$rn_ar; worktree rc=$rn_w reason=$rn_wr; live: $(tr '\n' ' ' <<<"$rn_live"))"; fi

    # the adapter, end to end on the same fixture: the first start of the day prints one JSON object whose
    # line names both releases and /update, and whose context carries that line marked as already shown (the
    # desktop app shows it; unmarked, the session repeated it); a resumed session prints nothing
    rna_run(){ rna_out="$(printf '{"source":"%s"}' "$1" | env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      HOME="$RN_HOME" CLAUDE_PROJECT_DIR="$2" python3 "$RNA" 2>&1)"; rna_rc=$?; }
    rna_line(){ python3 -c 'import json, sys
try:
    d = json.loads(sys.stdin.read())
    c = d["hookSpecificOutput"]
    assert set(d) == {"systemMessage", "hookSpecificOutput"} and c["hookEventName"] == "SessionStart"
    assert d["systemMessage"] in c["additionalContext"] and "already shown" in c["additionalContext"]
    print(d["systemMessage"])
except Exception:
    print("NOT-JSON")' <<<"$rna_out"; }
    rm -f "$RN_C"/.git/tabularium-release-check*; rn_pin v0.9.0
    rna_run resume "$RN_C"; rna_r="$rna_out"
    rna_run startup "$RN_C"; rna_l="$(rna_line)"
    if [ "$rna_rc" -eq 0 ] && [ -z "$rna_r" ] && grep -qF 'v0.10.1' <<<"$rna_l" && grep -qF 'v0.9.0' <<<"$rna_l" \
       && grep -qF '/update' <<<"$rna_l" && [ "$(awk 'END { print NR }' <<<"$rna_out")" = "1" ]; then
      rn_ok "release-notice adapter: the first start prints one line naming both releases and /update; a resumed session nothing"
    else rn_miss "release-notice adapter, minor gap (rc=$rna_rc, resume printed=${#rna_r} chars)"; echo "$rna_out" | sed 's/^/      /'; fi
    # adapter control and extras on a stub check: a patch gap, exit 0 with a minor gap, a name carrying more
    # than a release, and a missing check each print nothing, exit 0
    RNA_D="$RN_TMP/adapter"; mkdir -p "$RNA_D/checks"
    printf '#!/usr/bin/env bash\nhere="$(cd "$(dirname "$0")/.." && pwd)"\n[ "${1:-}" = --daily ] || exit 9\ncat "$here/.fx-out"; exit "$(cat "$here/.fx-rc")"\n' > "$RNA_D/checks/release-notice.sh"
    rna_stub(){ printf '%s\n' "$1" > "$RNA_D/.fx-rc"; printf 'pinned=%s\nnewest=%s\ngap=%s\nstatus=ok\nreason=\n' "$2" "$3" "$4" > "$RNA_D/.fx-out"; rna_run startup "$RNA_D"; }
    rna_q=""
    rna_stub 1 v0.9.0 v0.10.1 minor;  [ -n "$rna_out" ] || rna_q="$rna_q stub-minor-silent"
    rna_stub 0 v0.10.0 v0.10.1 patch; [ -z "$rna_out" ] && [ "$rna_rc" -eq 0 ] || rna_q="$rna_q patch"
    rna_stub 0 v0.9.0 v0.10.1 minor;  [ -z "$rna_out" ] && [ "$rna_rc" -eq 0 ] || rna_q="$rna_q exit-0"
    rna_stub 1 v0.9.0 "v0.10.1 https://example.invalid/x" minor; [ -z "$rna_out" ] && [ "$rna_rc" -eq 0 ] || rna_q="$rna_q long-newest"
    rna_stub 1 "v0.9.0 https://example.invalid/x" v0.10.1 minor; [ -z "$rna_out" ] && [ "$rna_rc" -eq 0 ] || rna_q="$rna_q long-pinned"
    rm -f "$RNA_D/checks/release-notice.sh"; rna_run startup "$RNA_D"; [ -z "$rna_out" ] && [ "$rna_rc" -eq 0 ] || rna_q="$rna_q missing"
    if [ -z "$rna_q" ]; then
      rn_ok "release-notice adapter: a patch, an exit 0, a name carrying more than a release and a missing check print nothing, exit 0"
    else rn_miss "release-notice adapter, quiet cases (wrong:$rna_q)"; fi
  fi
  [ ! -f "$RN_TMP/sleeper.pid" ] || kill "$(cat "$RN_TMP/sleeper.pid")" 2>/dev/null
  rm -rf "$RN_TMP"
fi

# Line endings (break test 2026-10-11): under core.autocrlf=true a checkout wrote changed scripts as CRLF and
# bash died on `set -uo pipefail\r`, so adoption, its installer and the printed rollback all failed. A
# synthetic source with the REAL .gitattributes and check.sh plus an extensionless hook is cloned with
# autocrlf on: no CR in either file, and check.sh runs. The control drops .gitattributes: both carry a CR and
# the same run fails — proof the fixture really converts. Every git call strips the inherited git environment.
if ! command -v git >/dev/null 2>&1; then
  skip line-endings "git absent — the line-ending bites were NOT run"
else
  eol_git(){ inst_git -c core.attributesFile=/dev/null -c user.name=fixture -c user.email=fixture@example.invalid \
    -c commit.gpgsign=false "$@"; }
  for eol_arm in bite control; do
    e="$(mktemp -d)"; mkdir -p "$e/src/checks/git-hooks"
    cp "$CHECK" "$e/src/checks/check.sh"; printf '#!/bin/sh\nexit 0\n' > "$e/src/checks/git-hooks/pre-commit"
    [ "$eol_arm" = control ] || cp "$ROOT/.gitattributes" "$e/src/.gitattributes"
    { eol_git -C "$e/src" init -q && eol_git -C "$e/src" add -A && eol_git -C "$e/src" commit -qm fixture \
      && eol_git -c core.autocrlf=true clone -q --no-local "$e/src" "$e/co"; } >/dev/null 2>&1
    eol_cr="$(grep -l $'\r' "$e/co/checks/check.sh" "$e/co/checks/git-hooks/pre-commit" 2>/dev/null | awk 'END { print NR }')"
    env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE bash "$e/co/checks/check.sh" --release-name v1.2.3 >/dev/null 2>&1; eol_rc=$?
    case "$eol_arm:$eol_cr:$eol_rc" in
      bite:0:0) echo "BITE  OK  (line endings: under core.autocrlf=true the real .gitattributes checks out LF and check.sh runs)"; pass=$((pass+1)) ;;
      control:2:[1-9]*) echo "BITE  OK  (line endings, control: without .gitattributes the same clone writes CRLF and check.sh fails)"; pass=$((pass+1)) ;;
      *) echo "BITE  MISS (line endings, $eol_arm: files with a CR=$eol_cr, check.sh rc=$eol_rc)"; fail=$((fail+1)) ;;
    esac
    rm -rf "${e:?}"
  done
fi

# retire-worktree.sh (ADR-0040) — retirement must refuse to destroy unverified bytes (the 2026-07-19
# near-loss) and move a clean merged worktree into locked, retained quarantine while keeping its branch.
# Synthetic mini-repos; the fixtures install no hooks, so the suite cannot recurse through them. Under the
# pre-commit hook git exports GIT_INDEX_FILE etc., which would point these at the real repository: stripped.
if command -v git >/dev/null 2>&1; then
  RETIRE="$ROOT/checks/retire-worktree.sh"
  retgit(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY git "$@"; }
  mk_retirerepo(){ # -> minimal repo: main + one clean worktree .claude/worktrees/wt1 (branch wip)
    local d; d="$(mktemp -d)"
    retgit -C "$d" init -q
    retgit -C "$d" symbolic-ref HEAD refs/heads/main
    retgit -C "$d" config user.email t@t.test; retgit -C "$d" config user.name tester
    retgit -C "$d" config commit.gpgsign false
    : > "$d/CLAUDE.md"; mkdir -p "$d/checks"
    cp "$RETIRE" "$d/checks/retire-worktree.sh"
    retgit -C "$d" add -A >/dev/null 2>&1; retgit -C "$d" commit -q -m base >/dev/null 2>&1
    retgit -C "$d" worktree add "$d/.claude/worktrees/wt1" -b wip >/dev/null 2>&1
    echo "$d"
  }
  # unique dirty bytes → REFUSED and the worktree SURVIVES (the incident)
  d="$(mk_retirerepo)"; echo unique >> "$d/.claude/worktrees/wt1/CLAUDE.md"
  bash "$d/checks/retire-worktree.sh" wt1 >/dev/null 2>&1; rrc=$?
  if [ "$rrc" -ne 0 ] && [ -d "$d/.claude/worktrees/wt1" ]; then
    echo "RETIRE OK  (unique dirty bytes refused, worktree survives)"; pass=$((pass+1))
  else echo "RETIRE MISS (unique dirty bytes: rc=$rrc, survived=$([ -d "$d/.claude/worktrees/wt1" ] && echo yes || echo no))"; fail=$((fail+1)); fi
  rm -rf "$d"
  # control: clean + merged → locked retained quarantine, branch KEPT
  d="$(mk_retirerepo)"
  bash "$d/checks/retire-worktree.sh" wt1 >/dev/null 2>&1; rrc=$?
  reg="$(retgit -C "$d" worktree list --porcelain)"
  if [ "$rrc" -eq 0 ] && [ ! -d "$d/.claude/worktrees/wt1" ] \
     && [ -d "$d/.git/retired-worktrees/wt1" ] && [ ! -e "$d/_archive" ] \
     && printf '%s\n' "$reg" | grep -q '^locked' \
     && retgit -C "$d" rev-parse --verify -q wip >/dev/null 2>&1; then
    echo "RETIRE OK  (clean merged worktree locked in retained quarantine; branch kept)"; pass=$((pass+1))
  else
    echo "RETIRE MISS (clean retire: rc=$rrc)"; fail=$((fail+1))
  fi
  rm -rf "$d"
else
  skip retire-worktree "git absent — the worktree-retirement bites were NOT run"
fi

# publish-skeleton.sh — the flip-time export gate, the ONLY firewall scan left running: a miss publishes
# patient data. Every case runs against a SYNTHETIC registry the fixture writes for itself (mode 0600, five
# opaque `zqx…` classes) named by the fixture's OWN checks/FIREWALL-REGISTRY — the real registry is never
# read, copied or pointed at. The REAL script is copied into a synthetic mini-repo and run there (its SRC
# resolves to dirname/.. = the temp root), so it firewalls the FIXTURE, never real data.
PUB="$ROOT/checks/publish-skeleton.sh"
FW_ID="zqx1aa"; FW_CASE="zqx2bb"; FW_CLIN="zqx3cc"; FW_BRAND="zqx4dd"; FW_CONSENT="zqx5ee"
# Synthetic accented clinical atom, used only to prove the publisher pins a UTF-8 locale. Under the
# inherited C locale BSD grep misses the uppercase token against the lowercase word-anchored atom.
FW_ACCENT="ŻÓŁĆ"; FW_ACCENT_ATOM="żółć"
# the wrapped-brand adjacency pairs the script's registry must carry (it aborts without them): ordinary
# words, plus a synthetic pair with Polish diacritics (the lane keeps accented letters as word letters)
FW_PAIR_L="alpha"; FW_PAIR_R="beta"; FW_APAIR_L="gęślą"; FW_APAIR_R="jaźń"
# under the pre-commit hook git exports GIT_INDEX_FILE (and an absolute GIT_DIR in a linked worktree), which
# would re-target the publisher's own `git init/add/commit` at the REAL repo: stripped for every run
pubrun(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY bash "$@"; }
fw_regfile(){ printf '%s\n' "$1/checks/registry.sh"; }
# ALLOW-array reader: the array holds multi-entry lines and trailing comments, so read it as the shell does
# (one entry per line); rc=1 when the block cannot be parsed or parses empty. Entries are bare words.
allow_entries(){ # $1 = a publish-skeleton.sh path -> one ALLOW entry per line on stdout
  local _ae
  [ -f "$1" ] || return 1
  _ae="$(awk '/^ALLOW=\(/{f=1;next} f&&/^\)/{exit} f{sub(/#.*/,""); for(i=1;i<=NF;i++) print $i}' "$1")" || return 1
  [ -n "$_ae" ] || return 1
  printf '%s\n' "$_ae"; }
seed_publish_contract(){ # $1 = synthetic repo root; create every required ALLOW entry, patient-free
  local r="$1"
  mkdir -p "$r/.github/workflows" "$r/.github/ISSUE_TEMPLATE" "$r/checks/git-hooks" "$r/checks/topics" "$r/adr" "$r/contributing" "$r/_templates" \
           "$r/tools/private-mode" "$r/tools/person_ownership" "$r/tools/handout_attest" "$r/tools/claude-hooks" \
           "$r/tools/interview_capture" "$r/tools/original_view" \
           "$r/tools/claude-skills/architect" "$r/tools/claude-skills/private" \
           "$r/tools/claude-skills/guard-admission" "$r/tools/claude-skills/update" \
           "$r/reference-library" "$r/_shared"
  printf 'synthetic contract file\n' > "$r/README.md"; printf 'synthetic contract file\n' > "$r/NOTICE.md"; printf 'synthetic contract file\n' > "$r/CONTRIBUTING.md"
  printf 'synthetic contract file\n' > "$r/CLAUDE.md"; printf 'synthetic contract file\n' > "$r/SETUP.md"
  printf 'synthetic contract file\n' > "$r/LICENSE"; printf 'synthetic contract file\n' > "$r/TRADEMARKS.md"; printf 'authors:\n  - given-names: Synthetic\n    family-names: Maintainer\n' > "$r/CITATION.cff"
  printf 'synthetic contract file\n' > "$r/AGENTS.md"; printf 'synthetic contract file\n' > "$r/.gitignore"
  printf '* text=auto eol=lf\n' > "$r/.gitattributes"
  printf 'synthetic contract file\n' > "$r/.github/workflows/skeleton-check.yml"
  printf 'synthetic contract file\n' > "$r/.github/ISSUE_TEMPLATE/report.md"
  printf 'synthetic contract file\n' > "$r/.github/readme-banner.svg"
  printf 'synthetic contract file\n' > "$r/checks/check.sh"; printf 'synthetic contract file\n' > "$r/checks/snapshot.sh"
  printf 'synthetic contract file\n' > "$r/checks/backup-tree.sh"; printf 'synthetic contract file\n' > "$r/checks/selftest.sh"
  printf 'synthetic contract file\n' > "$r/checks/confirms.sh"; printf 'synthetic contract file\n' > "$r/checks/README.md"
  printf 'synthetic contract file\n' > "$r/reference-library/README.md"
  printf 'synthetic contract file\n' > "$r/checks/retire-worktree.sh"
  printf 'synthetic contract file\n' > "$r/checks/backup-offsite.sh"
  printf 'synthetic contract file\n' > "$r/checks/RECORD-SET"
  printf 'synthetic contract file\n' > "$r/checks/PYTHON-SUITES"
  printf 'synthetic contract file\n' > "$r/checks/install-instance.sh"
  printf 'synthetic contract file\n' > "$r/checks/relay-scan.sh"
  printf 'synthetic contract file\n' > "$r/checks/config-paths.sh"
  printf 'synthetic contract file\n' > "$r/checks/reveal-private-id.sh"
  printf 'synthetic contract file\n' > "$r/checks/setup-mac.sh"
  printf 'synthetic contract file\n' > "$r/checks/adopt-release.sh"
  printf 'synthetic contract file\n' > "$r/checks/release-notice.sh"
  printf 'synthetic contract file\n' > "$r/tools/claude-hooks/README.md"
  printf 'synthetic contract file\n' > "$r/tools/claude-hooks/registry-read-guard.py"
  printf 'synthetic contract file\n' > "$r/tools/claude-hooks/test_registry_guard.py"
  printf 'synthetic contract file\n' > "$r/tools/claude-hooks/context-health.py"
  printf 'synthetic contract file\n' > "$r/tools/claude-hooks/test_context_health.py"
  printf 'synthetic contract file\n' > "$r/tools/claude-hooks/release-notice.py"
  printf 'synthetic contract file\n' > "$r/tools/claude-skills/architect/SKILL.md"
  printf 'synthetic contract file\n' > "$r/tools/claude-skills/private/SKILL.md"
  printf 'synthetic contract file\n' > "$r/tools/claude-skills/guard-admission/SKILL.md"
  printf 'synthetic contract file\n' > "$r/tools/claude-skills/update/SKILL.md"
  printf 'synthetic contract file\n' > "$r/tools/claude-skills/README.md"
  printf 'synthetic contract file\n' > "$r/_shared/README.md"
  printf 'synthetic directory sentinel\n' > "$r/checks/git-hooks/pre-commit"
  printf 'synthetic directory sentinel\n' > "$r/checks/topics/relay-and-export.md"
  printf 'synthetic directory sentinel\n' > "$r/adr/README.md"
  printf 'synthetic directory sentinel\n' > "$r/contributing/releases.md"
  printf 'synthetic directory sentinel\n' > "$r/_templates/README.md"
  printf 'synthetic directory sentinel\n' > "$r/tools/private-mode/README.md"
  printf 'synthetic directory sentinel\n' > "$r/tools/person_ownership/README.md"
  printf 'synthetic directory sentinel\n' > "$r/tools/handout_attest/README.md"
  printf 'synthetic directory sentinel\n' > "$r/tools/interview_capture/README.md"
  printf 'synthetic directory sentinel\n' > "$r/tools/original_view/README.md"
  # the behavioural suite is in the export contract too. The evals/cases entries are read back out of the
  # ALLOW array, not restated (a seeder with its own copy would drift the day a case is promoted); with none
  # parsed, the preflight aborts on a missing entry and every case here MISSes carrying that abort line.
  mkdir -p "$r/evals/profiles" "$r/evals/harness" "$r/evals/topics" "$r/evals/cases" "$r/evals/results"
  printf 'synthetic contract file\n' > "$r/evals/README.md"
  printf 'synthetic directory sentinel\n' > "$r/evals/profiles/eval-mode-addendum.md"
  printf 'synthetic directory sentinel\n' > "$r/evals/harness/README.md"
  printf 'synthetic directory sentinel\n' > "$r/evals/topics/how-a-run-works.md"
  local _cse _seeded=0
  for _cse in $(allow_entries "$PUB" | grep '^evals/cases/'); do
    mkdir -p "$r/$(dirname "$_cse")"
    printf 'synthetic case spec\n' > "$r/$_cse"; _seeded=$((_seeded+1))
  done
  if [ "$_seeded" -eq 0 ]; then
    echo "seed_publish_contract: no evals/cases entry parsed out of the ALLOW array" >&2
  fi
  # a local run ledger: deny-listed and not an ALLOW entry, so it must never reach the export
  printf '{"synthetic":"run ledger row"}\n' > "$r/evals/results/ledger.jsonl"
  cp "$PUB" "$r/checks/publish-skeleton.sh"
  # the SYNTHETIC registry + the config naming it. Owner-only (the sourcing block refuses a group/world-
  # readable one); neither file is an ALLOW entry, so neither reaches the export the firewall scans.
  {
    echo '# SYNTHETIC export-gate registry (selftest) — no real token anywhere.'
    echo "PII_IDENTITY='$FW_ID'"
    echo "PII_CASEREF='$FW_CASE'"   # a leftover line of the retired case-reference class: ignored (ADR-0072)
    printf "PII_CLINICAL='%s|%s%s%s'\n" "$FW_CLIN" '\b' "$FW_ACCENT_ATOM" '\b'
    echo "PII_BRAND='$FW_BRAND'"
    echo "PII_CONSENT='$FW_CONSENT'"
    echo "BRAND_ADJ_PAIRS='$FW_PAIR_L $FW_PAIR_R|$FW_APAIR_L $FW_APAIR_R'"
  } > "$r/checks/registry.sh"
  chmod 600 "$r/checks/registry.sh"
  printf '%s\n' "$r/checks/registry.sh" > "$r/checks/FIREWALL-REGISTRY"
  return 0
}
mk_pubrepo(){ # $1 = token to plant in README.md ("" = none); $2 (optional) = token to plant in
  #             NOTICE.md (the identity-class carve-out file) -> synthetic repo
  local d; d="$(mktemp -d)"
  seed_publish_contract "$d"
  if [ -n "$1" ]; then printf 'synthetic skeleton readme — %s\n' "$1" > "$d/README.md"
  else               printf 'synthetic skeleton readme — nothing sensitive\n' > "$d/README.md"; fi
  if [ -n "${2:-}" ]; then printf 'preview note — © 2026 %s. All rights reserved.\n' "$2" > "$d/NOTICE.md"
  else printf 'synthetic preview note\n' > "$d/NOTICE.md"; fi
  echo "$d"; }
# a release build reads a tag, so its fixture is a real source repository: everything planted so far is
# committed, and the tag annotated on it (ADR-0066). No git call inherits the hook environment or a global hook.
# pub_git is the only way in: `git -C ""` means the current directory, and a fixture that failed to build once
# put these commits, tags and config on the real repository (a scratch copy of these bites, 2026-11-07).
pub_git(){ # $1 = fixture, an absolute path that is not this repository · rest = git arguments
  local _f="${1:-}"; shift
  case "$_f" in
    "$ROOT"|"$ROOT"/*) echo "pub_git: refusing git on this repository" >&2; return 97 ;;
    /*) [ -d "$_f" ] || { echo "pub_git: no fixture at $_f" >&2; return 97; } ;;
    *) echo "pub_git: refusing git on '${_f:-<empty>}': not a fixture path" >&2; return 97 ;;
  esac
  inst_git -C "$_f" "$@"; }
# Once pub_tag has given a fixture its origin (a bare repository inside it), commits reach origin's main and
# tags reach origin, as a release is pushed before it is exported.
pub_has_origin(){ pub_git "$1" remote get-url origin >/dev/null 2>&1; }
pub_commit(){ # $1 = fixture · $2 = subject
  pub_git "$1" add -A; pub_git "$1" commit -q -m "$2" || return 1
  ! pub_has_origin "$1" || pub_git "$1" push -q origin HEAD:refs/heads/main; }
pub_annotate(){ # $1 = fixture · $2 = tag · $3 = its note
  pub_git "$1" tag -a "$2" -m "$3" || return 1
  ! pub_has_origin "$1" || pub_git "$1" push -q origin "refs/tags/$2"; }
pub_tag(){ # $1 = fixture · $2 = tag (default v1.0.0) · $3 = its note
  pub_git "$1" init -q || return 97; pub_git "$1" symbolic-ref HEAD refs/heads/main
  pub_git "$1" config user.email t@t.test; pub_git "$1" config user.name tester
  pub_git "$1" config commit.gpgsign false; pub_git "$1" config tag.gpgSign false; pub_git "$1" config tag.forceSignAnnotated false
  pub_git "$1" config core.hooksPath "$1/.git/hooks"
  printf '/export/\n/public.git/\n/.gitshim/\n/.origin.git/\n' >> "$1/.git/info/exclude"
  inst_git init -q --bare "$1/.origin.git" && pub_git "$1" remote add origin "$1/.origin.git" || return 97
  pub_commit "$1" "synthetic source history"; pub_annotate "$1" "${2:-v1.0.0}" "${3:-synthetic note}"; }
# PUBLISH_DEST pins the export INSIDE the fixture so the single `rm -rf "$d"` reaps it (the clean path
# deliberately keeps its build for inspection)
assert_firewall_abort(){ # $1=label $2=token
  local d out rc; d="$(mk_pubrepo "$2")"
  out="$(PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -qi 'PII tokens found' <<<"$out"; then
    echo "FIRE  OK  ($1): firewall aborted on the planted token"; pass=$((pass+1))
  else
    echo "FIRE  MISS ($1): expected an abort, rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; rm -rf "$d"; }
assert_firewall_clean(){ # $1=label; $2 (optional) = token planted in NOTICE.md (carve-out cases)
  local d out; d="$(mk_pubrepo "" "${2:-}")"
  # later git steps may exit on a bare host; assert ONLY on the firewall verdict, printed before any git op
  out="$(PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)" || true
  if grep -qi 'firewall: clean' <<<"$out" && ! grep -qi 'PII tokens found' <<<"$out"; then
    echo "FIRE  OK  ($1): firewall passed a clean tree (no false positive)"; pass=$((pass+1))
  else
    echo "FIRE  MISS ($1): firewall did not report clean"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; rm -rf "$d"; }
if [ -f "$PUB" ]; then
  # the documented entrypoint is executable (the EPX lint cannot see it: its README line is indented)
  if [ -x "$PUB" ]; then
    echo "FIRE  OK  (the documented export entrypoint is executable)"; pass=$((pass+1))
  else
    echo "FIRE  MISS (the documented export entrypoint is not executable)"; fail=$((fail+1))
  fi
  # the A1 read-guard classes an in-tree script as a legacy registry the moment it carries a `PII_*=` line
  # other than the PII_REST composition; a class line re-entering this tracked, shipped file would leak
  _wb_pii="$(grep -cE '^[[:space:]]*PII_[A-Z_]+=' "$PUB" || true)"
  _wb_rest="$(grep -cE '^[[:space:]]*PII_REST=' "$PUB" || true)"
  if [ "$_wb_pii" = "1" ] && [ "$_wb_rest" = "1" ]; then
    echo "FIRE  OK  (export script carries exactly one PII_* line, the PII_REST composition — the read-guard's legacy-registry rule stays off)"; pass=$((pass+1))
  else
    echo "FIRE  MISS (export script PII_* lines=$_wb_pii of which PII_REST=$_wb_rest; expected 1 and 1)"; fail=$((fail+1))
  fi
  # test: an identity-class token in a shipped file aborts the export. Control: the clean twin passes.
  assert_firewall_abort "identity-class token caught" "$FW_ID"
  assert_firewall_clean "clean export passes the firewall"
  # extra: a scan whose grep ERRORS (rc>=2) must abort loudly, never print "firewall: clean" with a class
  # unscanned (the old `|| true` swallow was fail-OPEN at the highest-stakes gate). Trigger: the pattern line
  # is sed-replaced with an unbalanced '(' — an invalid ERE that exits rc=2 on BOTH BSD and GNU grep.
  d="$(mk_pubrepo "")"
  sed 's|^PII_REST=.*|PII_REST="("|' "$d/checks/publish-skeleton.sh" > "$d/checks/.fwtmp" && mv "$d/checks/.fwtmp" "$d/checks/publish-skeleton.sh"
  out="$(PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ] && grep -qi 'firewall scan errored' <<<"$out" && ! grep -qi 'firewall: clean' <<<"$out" && ! grep -qi 'PII tokens found' <<<"$out"; then
    echo "FIRE  OK  (rest-scan grep error fails closed (rc>=2)): scan error aborted the export (fail closed)"; pass=$((pass+1))
  else
    echo "FIRE  MISS (rest-scan grep error fails closed (rc>=2)): expected a loud scan-error abort, rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
  fi; rm -rf "$d"

  # --- THE WIDER MATRIX (opt-in: --export) ----------------------------------------------------------
  # Restored 2026-10-10 from the pre-shrink suite (ROADMAP F12) and ported to the current ALLOW list. It
  # runs before an export and in CI, not on every local run, because it builds about a hundred synthetic
  # exports. It covers everything the synthetic registry can drive: the other content classes, the consent
  # marker, the locale pin, the private-mode split, the deny-list belts, the contract preflight, the NOTICE
  # carve-out, the scan-error and registry fail-closed arms, the filename lane, the binary and symlink
  # guards, inherited git env, the export commit's fixed identity, the hold (dry build and both --push
  # directions, network off), the release path, the wrapped-brand lane (accented letters included) and the eval-case
  # classification. Each class was mutation-checked when restored (the gate broken, its bites MISS).
  if [ "$EXPORT_MATRIX" -eq 1 ]; then
    # PRECISION control for every abort: a near-miss string that is NOT a class member must pass clean,
    # so an abort can only have come from the token itself, never from the fixture's shape.
    assert_firewall_pass_token(){ # $1=label $2=benign look-alike planted in README that MUST pass clean
      local d out; d="$(mk_pubrepo "$2")"
      out="$(PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)" || true
      if grep -qi 'firewall: clean' <<<"$out" && ! grep -qi 'PII tokens found' <<<"$out"; then
        echo "FIRE  OK  ($1): benign look-alike '$2' passed clean (no false positive)"; pass=$((pass+1))
      else
        echo "FIRE  MISS ($1): benign look-alike '$2' tripped the firewall"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
      fi; rm -rf "$d"; }
    # DENY-LIST BELT: a DENY-listed path in the export must ABORT even when it carries no PII. A benign
    # EMPTY denied dir is pre-seeded inside PUBLISH_DEST, so the distinct "denied path present" abort (not
    # "PII tokens found") proves the belt, not the grep, stopped it.
    assert_firewall_deny(){ # $1=label $2=a path from the script's DENY array
      local d out rc; d="$(mk_pubrepo "")"; mkdir -p "$d/export/$2"
      out="$(PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
      if [ "$rc" -ne 0 ] && grep -qi 'denied path present in export' <<<"$out" && ! grep -qi 'PII tokens found' <<<"$out"; then
        echo "FIRE  OK  ($1): deny-list belt aborted on a PII-free denied path"; pass=$((pass+1))
      else
        echo "FIRE  MISS ($1): expected a deny-list abort, rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
      fi; rm -rf "$d"; }
    # one fixture, one expected verdict. abort = nonzero exit with the abort's OWN marker and no firewall
    # verdict printed; belt = the same, for the deny belts, which run after `firewall: clean` and must not be
    # a content hit; clean = the firewall verdict with no hit. Reaps the fixture.
    fw_expect(){ # $1=label $2=fixture dir $3=abort|belt|clean $4=marker ("" for clean)
      local _l="$1" _d="$2" _w="$3" _m="$4" _o _r
      _o="$(PUBLISH_DEST="$_d/export" pubrun "$_d/checks/publish-skeleton.sh" 2>&1)"; _r=$?
      if { [ "$_w" = abort ] && [ "$_r" -ne 0 ] && grep -qi -- "$_m" <<<"$_o" && ! grep -qi 'firewall: clean' <<<"$_o"; } \
         || { [ "$_w" = belt ] && [ "$_r" -ne 0 ] && grep -qi -- "$_m" <<<"$_o" && ! grep -qi 'PII tokens found' <<<"$_o"; } \
         || { [ "$_w" = clean ] && grep -qi 'firewall: clean' <<<"$_o" && ! grep -qi 'PII tokens found' <<<"$_o"; }; then
        echo "FIRE  OK  ($_l)"; pass=$((pass+1))
      else
        echo "FIRE  MISS ($_l): expected $_w, rc=$_r"; printf '%s\n' "$_o" | sed 's/^/      /'; fail=$((fail+1))
      fi; rm -rf "$_d"; }

    # the publisher ignores inherited GIT_* env (2026-08-23 audit): GIT_DIR and GIT_INDEX_FILE aim at DECOY
    # paths inside the fixture (every other git variable stripped) and the real script runs WITHOUT pubrun. A
    # publisher that inherited them would `git init` the decoy and stage the export into the decoy index.
    d="$(mk_pubrepo "")"
    out="$(env -u GIT_WORK_TREE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
      GIT_DIR="$d/decoy-gitdir" GIT_INDEX_FILE="$d/decoy-index" PUBLISH_DEST="$d/export" bash "$d/checks/publish-skeleton.sh" 2>&1)" || true
    if [ ! -e "$d/decoy-gitdir" ] && [ ! -e "$d/decoy-index" ] && [ -d "$d/export/.git" ] && grep -qi 'firewall: clean' <<<"$out"; then
      echo "FIRE  OK  (publisher ignores inherited GIT_* env: decoy gitdir/index untouched, export has its own .git)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (publisher followed inherited GIT_* env — decoy gitdir=$([ -e "$d/decoy-gitdir" ] && echo present || echo absent), export/.git=$([ -d "$d/export/.git" ] && echo present || echo absent))"; echo "$out" | tail -3 | sed 's/^/      /'; fail=$((fail+1))
    fi; rm -rf "$d"

    # the export commit and tag name no person (operator decision 2026-10-10). Three decoys ride in, each above
    # every git config file: an inherited identity, a commit-msg hook that appends a decoy sign-off, and signing
    # on with a missing signer (a publisher that signs makes no commit or tag). Both must exist, carry the fixed
    # identity and hold no decoy anywhere in the object. Negative control: a copied publisher with its identity
    # and hook overrides stripped must show both decoys, proving the reader sees each leak. A MISS prints no
    # identity value, since a regression could surface the host's real one.
    fw_ident_hooks="$(mktemp -d)"
    printf '%s\n' '#!/bin/sh' 'printf "\nSigned-off-by: decoy-person <decoy@example.invalid>\n" >> "$1"' > "$fw_ident_hooks/commit-msg"
    chmod +x "$fw_ident_hooks/commit-msg"
    fw_export_commit(){ # $1 = fixture -> its export commit object, raw ("" if none was made); fw_tag_obj = its tag object
      pub_tag "$1"
      GIT_AUTHOR_NAME=decoy-person GIT_AUTHOR_EMAIL=decoy@example.invalid \
        GIT_COMMITTER_NAME=decoy-person GIT_COMMITTER_EMAIL=decoy@example.invalid \
        GIT_CONFIG_COUNT=4 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$fw_ident_hooks" \
        GIT_CONFIG_KEY_1=commit.gpgsign GIT_CONFIG_VALUE_1=true \
        GIT_CONFIG_KEY_2=gpg.program GIT_CONFIG_VALUE_2=/nonexistent-signer \
        GIT_CONFIG_KEY_3=tag.gpgSign GIT_CONFIG_VALUE_3=true \
        PUBLISH_DEST="$1/export" pubrun "$1/checks/publish-skeleton.sh" v1.0.0 >/dev/null 2>&1 || true
      fw_tag_obj="$(inst_git -C "$1/export" cat-file tag refs/tags/v1.0.0 2>/dev/null)" || fw_tag_obj=""
      inst_git -C "$1/export" cat-file commit HEAD 2>/dev/null || true; }
    fw_ident="Synthetic Maintainer <142178223+mtrzes@users.noreply.github.com> "
    d="$(mk_pubrepo "")"; fw_export_commit "$d" > "$d/.fw-co"; _co="$(cat "$d/.fw-co")"
    if grep -qF "author $fw_ident" <<<"$_co" && grep -qF "committer $fw_ident" <<<"$_co" && ! grep -q decoy <<<"$_co" \
       && grep -qF "tagger $fw_ident" <<<"$fw_tag_obj" && ! grep -q decoy <<<"$fw_tag_obj" && ! grep -q 'BEGIN PGP' <<<"$fw_tag_obj"; then
      echo "FIRE  OK  (export commit and tag carry the fixed export identity; no inherited identity, hook sign-off or signature reached them)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (export commit: $([ -n "$_co" ] && echo made || echo 'not made — a publisher that signs fails here'), fixed author and committer: $(grep -qF "author $fw_ident" <<<"$_co" && grep -qF "committer $fw_ident" <<<"$_co" && echo yes || echo no), decoy lines: $(grep -c decoy <<<"$_co"))"
      grep decoy <<<"$_co" | sed 's/^/      /'; fail=$((fail+1))
    fi; rm -rf "$d"
    d="$(mk_pubrepo "")"
    grep -v -e '^GIT_AUTHOR_NAME="\$EXPORT_IDENT_NAME"' -e '^GIT_COMMITTER_NAME="\$EXPORT_IDENT_NAME"' "$d/checks/publish-skeleton.sh" \
      | sed 's|git -c core\.hooksPath=/dev/null |git |' > "$d/checks/.fw-ident" && mv "$d/checks/.fw-ident" "$d/checks/publish-skeleton.sh"
    fw_export_commit "$d" > "$d/.fw-co"; _co="$(cat "$d/.fw-co")"
    if grep -q '^author decoy-person ' <<<"$_co" && grep -q '^Signed-off-by: decoy-person ' <<<"$_co" && grep -q '^tagger decoy-person ' <<<"$fw_tag_obj"; then
      echo "FIRE  OK  (negative control: with the identity and hook overrides stripped, the decoys reach the export commit and tag)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (negative control: decoy author $(grep -q '^author decoy-person ' <<<"$_co" && echo seen || echo missing), decoy sign-off $(grep -q '^Signed-off-by: decoy-person ' <<<"$_co" && echo seen || echo missing) — the bite cannot see that leak)"; fail=$((fail+1))
    fi; rm -rf "$d" "$fw_ident_hooks"

    # --- the other three content classes, one bite each, and the precision control --------------------
    # real case dates are not kept on the registry (ADR-0072): a leftover case-reference line is sourced
    # and never scanned, and deleting it changes nothing — the gate still bites on the other classes
    assert_firewall_pass_token "a leftover case-reference line is ignored (ADR-0072)" "$FW_CASE"
    d="$(mk_pubrepo "")"; sed -i.bak '/^PII_CASEREF=/d' "$(fw_regfile "$d")"; rm -f "$(fw_regfile "$d").bak"
    fw_expect "a registry without the case-reference line exports clean" "$d" clean ""
    d="$(mk_pubrepo "$FW_CLIN")"; sed -i.bak '/^PII_CASEREF=/d' "$(fw_regfile "$d")"; rm -f "$(fw_regfile "$d").bak"
    fw_expect "a registry without the case-reference line still catches a clinical token" "$d" abort 'PII tokens found'
    assert_firewall_abort      "clinical-class token caught"        "$FW_CLIN"
    assert_firewall_abort      "brand-class token caught"           "$FW_BRAND"
    assert_firewall_abort      "consent-class token caught (no marker; ADR-0027)" "$FW_CONSENT"
    assert_firewall_pass_token "near-miss string is not a class member (precision control)" "zqx1a"
    # the consent class is the ONE class a marker on the line lifts
    d="$(mk_pubrepo "")"
    printf 'synthetic note — %s discussed ⟨consent: example-disclosure — patient, 2026-07⟩\n' "$FW_CONSENT" > "$d/README.md"
    fw_expect "a ⟨consent: …⟩ marker on the line lifts the consent gate" "$d" clean ""

    # --- the locale pin (A59): inherited C must not narrow a diacritic atom, a clean tree under the same
    # inherited locale must still pass, and a host with no usable UTF-8 locale must refuse. A git shim stops
    # the clean-path probes after the firewall verdict, so these directions build no export repository.
    fw_nogit="$(mktemp -d)"
    printf '%s\n' '#!/bin/sh' 'exit 97' > "$fw_nogit/git"; chmod +x "$fw_nogit/git"
    d="$(mk_pubrepo "$FW_ACCENT")"
    out="$(LC_ALL=C PATH="$fw_nogit:$PATH" PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ] && grep -qi 'PII tokens found' <<<"$out" && ! grep -qi 'firewall: clean' <<<"$out"; then
      echo "FIRE  OK  (UTF-8 locale pin catches an uppercase accented token despite inherited C)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (accented token escaped under inherited C): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
    fi
    rm -rf "$d"
    # negative control: remove only the LC_ALL pin from the copied publisher. The same fixture must reach
    # `firewall: clean` under C, proving the bite above depends on the pin.
    d="$(mk_pubrepo "$FW_ACCENT")"
    if [ "$(grep -cF 'export LC_ALL="$FW_LC"' "$d/checks/publish-skeleton.sh")" = "1" ]; then
      grep -vF 'export LC_ALL="$FW_LC"' "$d/checks/publish-skeleton.sh" > "$d/checks/.fw-locale" \
        && mv "$d/checks/.fw-locale" "$d/checks/publish-skeleton.sh"
      out="$(LC_ALL=C PATH="$fw_nogit:$PATH" PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
      if grep -qi 'firewall: clean' <<<"$out" && ! grep -qi 'PII tokens found' <<<"$out"; then
        echo "FIRE  OK  (locale-pin NEGATIVE CONTROL: removing LC_ALL reproduces the accented-token miss under C)"; pass=$((pass+1))
      else
        echo "FIRE  MISS (locale-pin negative control did not reproduce the old miss): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
      fi
    else
      echo "FIRE  MISS (locale-pin negative control could not identify exactly one LC_ALL pin)"; fail=$((fail+1))
    fi
    rm -rf "$d"
    d="$(mk_pubrepo "")"
    out="$(LC_ALL=C PATH="$fw_nogit:$PATH" PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
    if grep -qi 'firewall: clean' <<<"$out" && ! grep -qi 'PII tokens found' <<<"$out"; then
      echo "FIRE  OK  (clean export remains clean when the caller inherits C)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (clean export under inherited C): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
    fi
    rm -rf "$d"
    fw_nolocale="$(mktemp -d)"
    printf '%s\n' '#!/bin/sh' 'printf "%s\n" C POSIX' > "$fw_nolocale/locale"; chmod +x "$fw_nolocale/locale"
    d="$(mk_pubrepo "")"
    out="$(PATH="$fw_nolocale:$fw_nogit:$PATH" PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
    if [ "$rc" -eq 2 ] && grep -qi 'no working UTF-8 locale available' <<<"$out" && ! grep -qi 'firewall: clean' <<<"$out"; then
      echo "FIRE  OK  (no usable UTF-8 locale refuses the export fail closed)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (no-UTF-8-locale refusal): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
    fi
    rm -rf "$d" "$fw_nolocale"
    # a locale name in `locale -a` is only a candidate: if grep cannot do the exact accented, case-insensitive
    # word match the firewall needs, the publisher must reject it as unusable
    fw_badlocale="$(mktemp -d)"; real_grep="$(command -v grep)"
    printf '%s\n' '#!/bin/sh' 'printf "%s\n" en_US.UTF-8' > "$fw_badlocale/locale"
    printf '%s\n' '#!/bin/sh' 'case "$*" in *żółw*) exit 1 ;; esac' "exec \"$real_grep\" \"\$@\"" > "$fw_badlocale/grep"
    chmod +x "$fw_badlocale/locale" "$fw_badlocale/grep"
    d="$(mk_pubrepo "")"
    out="$(PATH="$fw_badlocale:$fw_nogit:$PATH" PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rc=$?
    if [ "$rc" -eq 2 ] && grep -qi 'no working UTF-8 locale available' <<<"$out" && ! grep -qi 'firewall: clean' <<<"$out"; then
      echo "FIRE  OK  (listed locale whose accented grep probe fails refuses the export)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (broken-listed-locale refusal): rc=$rc"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
    fi
    rm -rf "$d" "$fw_nogit" "$fw_badlocale"

    # --- the private-mode identifier split (ADR-0050 point 9). The export gate SOURCES the
    # registry; the registry folds the identifier's own file back into its class with the block the
    # operator pastes. These bites run THAT block, extracted from checks/topics/relay-and-export.md, against a synthetic
    # private file, so the recipe and the bite cannot drift apart. Negative control: the same cut WITHOUT
    # the block lets the planted identifier through.
    pm_block="$(awk '/<!-- private-mode-id-block:begin -->/{f=1; next} /<!-- private-mode-id-block:end -->/{f=0} f' "$ROOT/checks/topics/relay-and-export.md" | sed '/^```/d')"
    if [ -n "$pm_block" ] && grep -qF "tab_pmid_file='/ABSOLUTE/PATH/OF/private-mode-id.sh'" <<<"$pm_block" \
       && [ "$(grep -cE '^[[:space:]]*PII_[A-Z_]+=' <<<"$pm_block")" = "0" ]; then
      echo "FIRE  OK  (the documented private-mode block extracts from checks/topics/relay-and-export.md and adds no class line a reader would count)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (private-mode block: not extractable from checks/topics/relay-and-export.md, placeholder missing, or it adds a PII_* class line)"; fail=$((fail+1))
    fi
    mk_splitrepo(){ # $1 = token planted in README ("" = none) · $2 = with-block | no-block · $3 = mode | missing
      local d; d="$(mk_pubrepo "$1")"
      printf "PII_PRIVATE_MODE_ID='zqx9zz'\n" > "$d/private-mode-id.sh"
      if [ "$3" = "missing" ]; then rm -f "$d/private-mode-id.sh"; else chmod "$3" "$d/private-mode-id.sh"; fi
      if [ "$2" = "with-block" ]; then
        printf '%s\n' "$pm_block" | sed "s#/ABSOLUTE/PATH/OF/private-mode-id.sh#$d/private-mode-id.sh#" >> "$(fw_regfile "$d")"
      fi
      printf '%s\n' "$d"; }
    for pm_case in "split: the folded identifier is caught|zqx9zz|with-block|600|abort" \
                   "split: a clean tree still passes|-|with-block|600|clean" \
                   "split: private file missing aborts (fail closed)|-|with-block|missing|five" \
                   "split: private file not owner-only aborts (fail closed)|-|with-block|644|five" \
                   "split NEGATIVE CONTROL: the same cut without the block misses the identifier|zqx9zz|no-block|600|clean"; do
      IFS='|' read -r pm_lbl pm_tok pm_blk pm_mode pm_want <<<"$pm_case"
      [ "$pm_tok" = "-" ] && pm_tok=""
      d="$(mk_splitrepo "$pm_tok" "$pm_blk" "$pm_mode")"
      case "$pm_want" in
        abort) fw_expect "$pm_lbl" "$d" abort 'PII tokens found' ;;
        clean) fw_expect "$pm_lbl" "$d" clean "" ;;
        five)  fw_expect "$pm_lbl" "$d" abort 'did not define all four' ;;
      esac
    done
    # kept details (ADR-0029 point 13, ADR-0075): a PII_PRIVATE_<CLASS> line in the private file is
    # folded back into its class by the same block, so its token stops the export. Negative control: the
    # same planted token with no kept-details line passes. Malformed or duplicate lines unset identity (fail closed).
    for pm_case in "split kept-details: a folded kept-details token is caught|with-v2|abort" \
                   "split kept-details: a folded kept-details token of another class (clinical) is caught|with-v2-clinical|abort" \
                   "split kept-details: a leftover case-reference line is ignored, its token passes (ADR-0072)|with-v2-caseref|clean" \
                   "split kept-details NEGATIVE CONTROL: without the kept-details line the same token passes|no-v2|clean" \
                   "split kept-details: a second line of one kept-details class aborts (fail closed)|dup-v2|five" \
                   "split kept-details: a near-miss line (export ...) aborts (fail closed)|nearmiss-v2|five" \
                   "split kept-details: a line of two quoted parts joined by a bar aborts (fail closed)|quotepair-v2|five" \
                   "split kept-details: a line with text between two quoted parts aborts (fail closed)|quotetext-v2|five"; do
      IFS='|' read -r pm_lbl pm_v2 pm_want <<<"$pm_case"
      d="$(mk_splitrepo "zqx8yy" with-block 600)"
      case "$pm_v2" in
        with-v2) printf "PII_PRIVATE_IDENTITY='zqx8yy'\n" >> "$d/private-mode-id.sh" ;;
        with-v2-clinical) printf "PII_PRIVATE_CLINICAL='zqx7qq|zqx8yy'\n" >> "$d/private-mode-id.sh" ;;
        with-v2-caseref) printf "PII_PRIVATE_CASEREF='zqx7qq|zqx8yy'\n" >> "$d/private-mode-id.sh" ;;
        dup-v2)  printf "PII_PRIVATE_IDENTITY='zqx8yy'\nPII_PRIVATE_IDENTITY='zqx6ww'\n" >> "$d/private-mode-id.sh" ;;
        nearmiss-v2) printf "export PII_PRIVATE_IDENTITY='zqx8yy'\n" >> "$d/private-mode-id.sh" ;;
        quotepair-v2) printf '%s\n' "PII_PRIVATE_IDENTITY='zqx8yy'|'zqx6ww'" >> "$d/private-mode-id.sh" ;;
        quotetext-v2) printf '%s\n' "PII_PRIVATE_IDENTITY='zqx8yy'x'zqx6ww'" >> "$d/private-mode-id.sh" ;;
      esac
      case "$pm_want" in
        abort) fw_expect "$pm_lbl" "$d" abort 'PII tokens found' ;;
        clean) fw_expect "$pm_lbl" "$d" clean "" ;;
        five)  fw_expect "$pm_lbl" "$d" abort 'did not define all four' ;;
      esac
    done

    # --- the deny-list belts: the literal DENY loop, then the STRUCTURAL belt (a record-shaped directory
    # nested under an allow-listed one, invisible to the loop and to the filename scan). The second nested
    # name proves the export root's own `_shared/` is exempt by EXACT path only.
    assert_firewall_deny "deny-list belt catches a PII-free denied path" "patients"
    # the eval run ledgers and score file are tracked in DEV: the belt stops them, and a clean export of a
    # tree holding them ships none (the harness beside them does ship, so the manifest read is not vacuous)
    assert_firewall_deny "deny-list belt catches the tracked eval run ledgers" "evals/results"
    d="$(mk_pubrepo "")"; printf 'run,date\n' > "$d/evals/results/scores.csv"
    out="$(PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)" || true
    _man="$(sed -n '/^== export manifest ==/,$p' <<<"$out")"
    if grep -q '^  \./evals/harness/' <<<"$_man" && ! grep -q '^  \./evals/results' <<<"$_man"; then
      echo "FIRE  OK  (a clean export leaves the eval ledgers and score file behind)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (eval ledgers in the export manifest, or no manifest)"; echo "$out" | sed 's/^/      /'; fail=$((fail+1))
    fi; rm -rf "$d"
    for _nest in _templates/person/patients adr/_shared; do
      d="$(mk_pubrepo "")"; mkdir -p "$d/$_nest"
      printf 'benign body, nothing sensitive\n' > "$d/$_nest/notes.md"
      fw_expect "deny belt: a record-shaped directory nested at $_nest aborts" "$d" belt 'record-shaped directory in export'
    done

    # --- the export CONTRACT preflight: an incomplete ALLOW surface must abort, never ship short ---------
    d="$(mk_pubrepo "")"; rm -f "$d/CLAUDE.md"
    fw_expect "missing required export contract file aborts fail closed" "$d" abort 'required allow-listed path missing'
    d="$(mk_pubrepo "")"; : > "$d/CLAUDE.md"
    fw_expect "empty/truncated required contract file aborts fail closed" "$d" abort 'allow-listed file is empty'
    d="$(mk_pubrepo "")"; rm -rf "$d/tools/person_ownership"; mkdir -p "$d/tools/person_ownership"
    fw_expect "empty required contract directory aborts fail closed" "$d" abort 'directory has no nonempty regular file'
    d="$(mk_pubrepo "")"; rm -rf "$d/tools/person_ownership"; mkdir -p "$d/tools/person_ownership/nested-empty"
    fw_expect "nested-empty required contract directory aborts fail closed" "$d" abort 'directory has no nonempty regular file'
    d="$(mk_pubrepo "")"; rm -rf "$d/tools/person_ownership"; mkdir -p "$d/tools/person_ownership"
    printf 'pruned cruft\n' > "$d/tools/person_ownership/.DS_Store"
    fw_expect "prune-only required contract directory aborts fail closed" "$d" abort 'directory has no nonempty regular file'

    # --- the identity CARVE-OUT, the most dangerous code in the script: both directions. The operator's
    # self-disclosure in the TOP-LEVEL NOTICE.md and CITATION.cff is exempt, and ONLY there: a nested file
    # merely sharing a name inherits nothing (the exemption is anchored to the exact export-root paths).
    assert_firewall_clean "identity token in the top-level NOTICE.md is exempt (self-disclosure carve-out)" "$FW_ID"
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"
    printf 'preview note — © 2026 %s. All rights reserved.\n' "$FW_ID" > "$d/adr/NOTICE.md"
    fw_expect "nested NOTICE.md is NOT exempt: identity token in adr/NOTICE.md still aborts" "$d" abort 'PII tokens found'
    d="$(mk_pubrepo "")"; printf 'family-names: %s\n' "$FW_ID" > "$d/CITATION.cff"
    fw_expect "identity token in the top-level CITATION.cff is exempt (self-disclosure carve-out)" "$d" clean ""
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"; printf 'family-names: %s\n' "$FW_ID" > "$d/adr/CITATION.cff"
    fw_expect "nested CITATION.cff is NOT exempt: identity token in adr/CITATION.cff still aborts" "$d" abort 'PII tokens found'
    d="$(mk_pubrepo "")"; printf 'abstract: %s\n' "$FW_CLIN" > "$d/CITATION.cff"
    fw_expect "the top-level CITATION.cff is still scanned for every other class: a clinical token aborts" "$d" abort 'PII tokens found'

    # --- SCAN-ERROR and REGISTRY fail-closed arms: a scan grep that ERRORS (rc>=2) or a registry that cannot
    # be sourced must abort before any scan verdict. The class lines live in the fixture's registry, so the
    # sed that breaks one (an unbalanced '(' — rc=2 on BSD and GNU grep) is applied there, owner-only kept.
    assert_firewall_scanerr(){ # $1=label $2=sed program breaking one registry line $3=abort marker
      local d rf; d="$(mk_pubrepo "")"; rf="$(fw_regfile "$d")"
      sed "$2" "$rf" > "$d/checks/.fwtmp" && mv "$d/checks/.fwtmp" "$rf" && chmod 600 "$rf"
      fw_expect "$1" "$d" abort "$3"; }
    assert_firewall_scanerr "identity-scan grep error fails closed (rc>=2)" 's|^PII_IDENTITY=.*|PII_IDENTITY="("|' 'identity scan errored'
    assert_firewall_scanerr "consent-scan grep error fails closed (rc>=2)"  's|^PII_CONSENT=.*|PII_CONSENT="("|'   'consent scan errored'
    d="$(mk_pubrepo "")"; rm -f "$(fw_regfile "$d")"
    fw_expect "config names a registry that is gone: aborts before any scan verdict" "$d" abort 'token registry missing/unreadable/symlinked'
    d="$(mk_pubrepo "")"; chmod 644 "$(fw_regfile "$d")"
    fw_expect "a group/world-readable registry is refused, not sourced" "$d" abort 'group- or world-readable'

    # --- FILENAME LANE: a token in a file NAME aborts through the dedicated scan, asserted by its OWN marker
    # (not 'PII tokens found'); the identity leg of the same OR-ed pattern; a near-miss name passes.
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"; printf 'benign body, nothing sensitive\n' > "$d/adr/note-$FW_BRAND.md"
    fw_expect "filename scan: registry token in a file NAME aborts" "$d" abort 'file/dir name'
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"; printf 'benign body, nothing sensitive\n' > "$d/adr/$FW_ID-note.md"
    fw_expect "filename scan: identity token in a file NAME aborts" "$d" abort 'file/dir name'
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"; printf 'benign body, nothing sensitive\n' > "$d/adr/zqx1a-notes.md"
    fw_expect "filename scan: benign look-alike file name passes clean" "$d" clean ""

    # --- BINARY ALLOWLIST: token-shaped bytes inside a vetted font binary do not abort (ADR-0032) … but any
    # OTHER binary does: the -I scans would skip a container that can carry readable text.
    d="$(mktemp -d)"; seed_publish_contract "$d"; mkdir -p "$d/_templates/handout-assets/fonts"
    printf 'synthetic readme, nothing sensitive\n' > "$d/README.md"
    printf '%s\000\000binary\000data' "$FW_CLIN" > "$d/_templates/handout-assets/fonts/x.woff2"
    fw_expect "-I binary-skip: token bytes in a vetted font do not abort" "$d" clean ""
    d="$(mk_pubrepo "")"; printf 'PK\003\004\000\000not-a-real-doc\000' > "$d/_templates/x.pdf"
    fw_expect "binary allowlist: non-font binary in the export aborts" "$d" abort 'unvetted binary'

    # --- SYMLINK GUARD: every scan layer is blind to a link's TARGET, yet git would commit that string — so
    # ANY symlink aborts. Benign target on purpose: the guard fires on the link TYPE, not on a token.
    d="$(mk_pubrepo "")"; ln -s /nonexistent-benign-target "$d/_templates/asset-link"
    fw_expect "symlink guard: a symlink in the export aborts" "$d" abort 'symlink(s) in export'

    # --- PUBLISH-HOLD gates PUSHING only: a dry build under a live hold still runs, for inspection.
    d="$(mk_pubrepo "")"; printf 'held\n' > "$d/checks/PUBLISH-HOLD"
    fw_expect "the hold gates pushing only: a dry build under a live hold still runs" "$d" clean ""
    # --- and the two --push directions. Each runs the fixture's COPY of the publisher with the hold
    # sentinel present; REMOTE, where set, is a path inside the fixture that does not exist. Every git call
    # runs with network transport off (GIT_ALLOW_PROTOCOL=file, no prompt, no inherited GIT_* env or
    # REMOTE), so even a broken hold can reach no remote but that missing local path. A PATH shim logs each
    # git call before running the real git, so a hold that aborts late (after git init/add) still MISSes.
    # Negative controls: make each check a no-op in the fixture's copy and the bite's verdict flips.
    hold_run(){ # $1 = fixture · $2 = REMOTE ("" = unset) · $3 = tag (optional) -> sets hr_out, hr_rc, hr_gc (git calls logged)
      local _s="$1/.gitshim"
      mkdir -p "$_s"; : > "$_s/calls"
      printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "%s/calls"\nexec "%s" "$@"\n' "$_s" "$(command -v git)" > "$_s/git"
      chmod +x "$_s/git"
      if [ -n "$2" ]; then
        hr_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY \
          GIT_ALLOW_PROTOCOL=file GIT_TERMINAL_PROMPT=0 PATH="$_s:$PATH" REMOTE="$2" PUBLISH_DEST="$1/export" \
          bash "$1/checks/publish-skeleton.sh" ${3:+"$3"} --push 2>&1)"; hr_rc=$?
      else
        hr_out="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY -u REMOTE \
          GIT_ALLOW_PROTOCOL=file GIT_TERMINAL_PROMPT=0 PATH="$_s:$PATH" PUBLISH_DEST="$1/export" \
          bash "$1/checks/publish-skeleton.sh" --push 2>&1)"; hr_rc=$?
      fi
      hr_gc="$(grep -c . "$_s/calls")"; }
    # the held bite's verdict, shared by the bite and its negative control
    hold_bites(){ [ "$hr_rc" -ne 0 ] && grep -q 'publishing is HELD' <<<"$hr_out" && [ "$hr_gc" = "0" ] && [ ! -e "$1/export" ]; }
    noremote_bites(){ [ "$hr_rc" -ne 0 ] && grep -q 'requires an explicit REMOTE' <<<"$hr_out" && [ "$hr_gc" = "0" ] && [ ! -e "$1/export" ]; }
    hold_line='if [ "$PUSH" = "yes" ] && [ -f "$SRC/checks/PUBLISH-HOLD" ]; then'
    remote_line='if [ "$PUSH" = "yes" ] && [ -z "$REMOTE" ]; then'
    hold_noop(){ # $1 = fixture, $2 = the exact check line to make a no-op -> rc 1 unless exactly one replaced
      [ "$(grep -cxF -- "$2" "$1/checks/publish-skeleton.sh")" = "1" ] || return 1
      awk -v t="$2" '$0 == t { print "if false; then"; next } { print }' "$1/checks/publish-skeleton.sh" > "$1/checks/.holdtmp" \
        && mv "$1/checks/.holdtmp" "$1/checks/publish-skeleton.sh"; }
    d="$(mk_pubrepo "")"; printf 'held\n' > "$d/checks/PUBLISH-HOLD"; hold_run "$d" "$d/no-such-remote.git"
    if hold_bites "$d" && [ ! -e "$d/no-such-remote.git" ]; then
      echo "FIRE  OK  (held --push with REMOTE aborts before any git call; nothing built, nothing at the remote path)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (held --push with REMOTE: rc=$hr_rc git-calls=$hr_gc remote-path=$([ -e "$d/no-such-remote.git" ] && echo created || echo absent))"; printf '%s\n' "$hr_out" | sed 's/^/      /'; fail=$((fail+1))
    fi; rm -rf "$d"
    # the ceremony's own shape: a tagged release under the hold. The hold still comes before any git call.
    d="$(mk_pubrepo "")"; pub_tag "$d"; printf 'held\n' > "$d/checks/PUBLISH-HOLD"; hold_run "$d" "$d/no-such-remote.git" v1.0.0
    if hold_bites "$d" && [ ! -e "$d/no-such-remote.git" ]; then
      echo "FIRE  OK  (held --push of a tagged release aborts before any git call; nothing built, nothing at the remote path)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (held tagged --push: rc=$hr_rc git-calls=$hr_gc)"; printf '%s\n' "$hr_out" | sed 's/^/      /'; fail=$((fail+1))
    fi; rm -rf "$d"
    d="$(mk_pubrepo "")"; printf 'held\n' > "$d/checks/PUBLISH-HOLD"; hold_run "$d" ""
    if noremote_bites "$d"; then
      echo "FIRE  OK  (--push without REMOTE refuses before any git call — there is no default remote)"; pass=$((pass+1))
    else
      echo "FIRE  MISS (--push without REMOTE: rc=$hr_rc git-calls=$hr_gc)"; printf '%s\n' "$hr_out" | sed 's/^/      /'; fail=$((fail+1))
    fi; rm -rf "$d"
    # NEGATIVE CONTROL, hold: the check made a no-op, the same run gets past it to a release build. The bite must
    # MISS, the public copy must have been read at the missing local path only and failed, and nothing may exist there.
    d="$(mk_pubrepo "")"; printf 'held\n' > "$d/checks/PUBLISH-HOLD"
    if hold_noop "$d" "$hold_line" && pub_tag "$d"; then
      hold_run "$d" "$d/no-such-remote.git" v1.0.0
      _hr_url="$(env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$d/export" config --get remote.origin.url 2>/dev/null)" || _hr_url=""
      if ! hold_bites "$d" && [ "$hr_rc" -ne 0 ] && grep -q 'ls-remote ' <<<" $(tr '\n' ' ' < "$d/.gitshim/calls")" \
         && [ "$_hr_url" = "$d/no-such-remote.git" ] && [ ! -e "$d/no-such-remote.git" ]; then
        echo "FIRE  OK  (hold NEGATIVE CONTROL: with the check a no-op the bite MISSes; the run read only the missing local path, and failed)"; pass=$((pass+1))
      else
        echo "FIRE  MISS (hold negative control: rc=$hr_rc git-calls=$hr_gc remote-path=$([ -e "$d/no-such-remote.git" ] && echo created || echo absent))"; printf '%s\n' "$hr_out" | sed 's/^/      /'; fail=$((fail+1))
      fi
    else
      echo "FIRE  MISS (hold negative control could not identify exactly one hold check line)"; fail=$((fail+1))
    fi; rm -rf "$d"
    # NEGATIVE CONTROL, no REMOTE: that check made a no-op, the run falls through to the hold instead
    d="$(mk_pubrepo "")"; printf 'held\n' > "$d/checks/PUBLISH-HOLD"
    if hold_noop "$d" "$remote_line"; then
      hold_run "$d" ""
      if ! noremote_bites "$d" && grep -q 'publishing is HELD' <<<"$hr_out" && [ "$hr_gc" = "0" ]; then
        echo "FIRE  OK  (no-REMOTE NEGATIVE CONTROL: with the check a no-op the bite MISSes; the hold still stops the run)"; pass=$((pass+1))
      else
        echo "FIRE  MISS (no-REMOTE negative control: rc=$hr_rc git-calls=$hr_gc)"; printf '%s\n' "$hr_out" | sed 's/^/      /'; fail=$((fail+1))
      fi
    else
      echo "FIRE  MISS (no-REMOTE negative control could not identify exactly one REMOTE check line)"; fail=$((fail+1))
    fi; rm -rf "$d"

    # --- A RELEASE IS BUILT FROM ITS TAG (ADR-0066). These fixtures are real source repositories (pub_tag): the
    # refusals, the tag's own tree and note, the append, and the push path. Each --push runs the fixture's COPY
    # of the publisher with no sentinel in the fixture, against a bare repository inside it, network off.
    rel_run(){ # $1 = fixture · $2 = REMOTE ("" = none) · rest = arguments -> rl_out, rl_rc. A fresh build each time.
      local _f="$1" _r="$2"; shift 2; rm -rf "$_f/export"
      rl_out="$(GIT_ALLOW_PROTOCOL=file GIT_TERMINAL_PROMPT=0 REMOTE="$_r" PUBLISH_DEST="$_f/export" \
        pubrun "$_f/checks/publish-skeleton.sh" "$@" 2>&1)"; rl_rc=$?; }
    rel_bite(){ # $1 = status of the bite's condition · $2 = label · $3 = shown on a miss
      if [ "$1" -eq 0 ]; then echo "FIRE  OK  ($2)"; pass=$((pass+1))
      else echo "FIRE  MISS ($2)"; printf '%s\n' "${3:-}" | sed 's/^/      /'; fail=$((fail+1)); fi; }
    rel_refused(){ # $1 = fixture · $2 = label · $3 = the refusal's marker · $4 = expected rc · rest = arguments, no remote
      local _f="$1" _l="$2" _m="$3" _x="$4"; shift 4
      rel_run "$_f" "" "$@"
      { [ "$rl_rc" -eq "$_x" ] && grep -qF -- "$_m" <<<"$rl_out" && ! grep -q 'firewall: clean' <<<"$rl_out" && [ ! -e "$_f/export" ]; }
      rel_bite $? "$_l" "rc=$rl_rc: $rl_out"; }
    rel_mkbare(){ inst_git init -q --bare "$1" && pub_git "$1" symbolic-ref HEAD refs/heads/main; }
    rel_refs(){ inst_git -C "$1" for-each-ref --format='%(refname) %(objectname)'; }

    # the fixture helpers refuse what is not a fixture: empty, relative, this repository
    pub_git "" status >/dev/null 2>&1; a=$?; pub_git checks status >/dev/null 2>&1; b=$?; pub_git "$ROOT" status >/dev/null 2>&1; c=$?
    { [ "$a" -eq 97 ] && [ "$b" -eq 97 ] && [ "$c" -eq 97 ]; }
    rel_bite $? "the fixture git helper refuses an empty path, a relative one and this repository" "rc: $a $b $c"
    # untagged --push: refused before any git call, whatever the hold says
    d="$(mk_pubrepo "")"; hold_run "$d" "$d/no-such-remote.git"
    { [ "$hr_rc" -ne 0 ] && grep -q 'needs a release tag' <<<"$hr_out" && [ "$hr_gc" = "0" ] && [ ! -e "$d/export" ] && [ ! -e "$d/no-such-remote.git" ]; }
    rel_bite $? "an untagged --push is refused before any git call: nothing built, nothing at the remote path" "rc=$hr_rc git-calls=$hr_gc: $hr_out"
    rm -rf "$d"
    # no tag named: the scan runs, on the working tree, and leaves nothing that could be published
    d="$(mk_pubrepo "")"; pub_tag "$d"; printf 'uncommitted — %s\n' "$FW_CLIN" > "$d/README.md"
    rel_run "$d" ""
    { [ "$rl_rc" -ne 0 ] && grep -q 'PII tokens found' <<<"$rl_out"; }
    rel_bite $? "with no tag named the scan reads the working tree, even at a tagged commit" "rc=$rl_rc: $rl_out"
    printf 'synthetic skeleton readme\n' > "$d/README.md"; rel_run "$d" ""
    { [ "$rl_rc" -eq 0 ] && grep -q 'firewall: clean' <<<"$rl_out" && grep -q 'No commit and no tag' <<<"$rl_out" \
      && ! inst_git -C "$d/export" rev-parse --verify --quiet HEAD >/dev/null && [ -z "$(inst_git -C "$d/export" tag)" ]; }
    rel_bite $? "a scan with no tag named makes no commit and no tag" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # what may be named
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "synthetic note"; pub_git "$d" tag v1.0.1
    rel_refused "$d" "a name without three numbers is refused" 'not a release name' 1 v1.2
    rel_refused "$d" "a legacy slugged name is refused" 'not a release name' 1 v1.0.0-slug
    rel_refused "$d" "a name with a leading zero is refused: one number, two names" 'not a release name' 1 v1.02.0
    rel_refused "$d" "a revision of a tag is refused" 'not a release name' 1 'v1.0.0~1'
    rel_refused "$d" "a tag this checkout lacks is refused" 'no tag v7.7.7' 1 v7.7.7
    rel_refused "$d" "a lightweight tag is refused" 'not an annotated tag' 1 v1.0.1
    rel_refused "$d" "an unknown option is a usage error, not a quiet dry run" 'usage:' 2 --psuh
    printf '# edited after the tag\n' >> "$d/checks/publish-skeleton.sh"
    rel_refused "$d" "an export script that is not the tag's own is refused: its ALLOW list decides what ships" "not v1.0.0's own" 1 v1.0.0
    rm -rf "$d"
    # a release is a tag on main, pushed: a tag cut on a branch, a tag origin lacks, a tag moved here
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "on main"
    pub_git "$d" switch -q -c side; printf 'side\n' >> "$d/README.md"; pub_git "$d" commit -q -am side
    pub_git "$d" tag -a v1.1.0 -m "cut on a branch"; pub_git "$d" push -q origin refs/tags/v1.1.0
    rel_refused "$d" "a tag whose commit is not on origin's main is refused" "not on origin's main" 1 v1.1.0
    pub_git "$d" tag -a v1.2.0 -m "never pushed"
    rel_refused "$d" "a tag origin does not carry is refused" "not on origin as it is here" 1 v1.2.0
    pub_git "$d" update-ref refs/remotes/origin/main side
    rel_refused "$d" "a tag on a branch is refused though a stale remote-tracking main names its commit" "not on origin's main" 1 v1.1.0
    pub_git "$d" switch -q main; pub_git "$d" tag -f -a v1.0.0 -m "moved here" >/dev/null 2>&1
    rel_refused "$d" "a tag moved here, unlike origin's, is refused" "not on origin as it is here" 1 v1.0.0
    rm -rf "$d"
    # a release build goes into an empty folder; the scan alone may reuse one
    d="$(mk_pubrepo "")"; pub_tag "$d"; mkdir -p "$d/keep"; printf 'stale\n' > "$d/keep/stale.md"
    rl_out="$(GIT_ALLOW_PROTOCOL=file REMOTE="" PUBLISH_DEST="$d/keep" pubrun "$d/checks/publish-skeleton.sh" v1.0.0 2>&1)"; rl_rc=$?
    { [ "$rl_rc" -ne 0 ] && grep -q 'PUBLISH_DEST is not empty' <<<"$rl_out" && [ -f "$d/keep/stale.md" ] && [ ! -e "$d/keep/.git" ]; }
    rel_bite $? "a release build into a folder that is not empty is refused, and the folder is left as it was" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # git archive applies attributes; an export-subst set in this checkout's untracked info/attributes must abort
    d="$(mk_pubrepo "")"; printf 'synthetic readme $Format:%%an$\n' > "$d/README.md"; pub_tag "$d"
    printf 'README.md export-subst\n' >> "$d/.git/info/attributes"
    rel_run "$d" "" v1.0.0
    { [ "$rl_rc" -ne 0 ] && grep -q 'did not arrive byte for byte' <<<"$rl_out" && [ ! -e "$d/export/.git" ]; }
    rel_bite $? "an attribute that changes the archived bytes aborts the build" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # a clean filter from this machine's global attributes applies at `git add`, after every scan: it must abort
    d="$(mk_pubrepo "")"; printf 'README.md filter=zqxclean\n' > "$d/.attrs"
    rl_out="$(GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.attributesFile GIT_CONFIG_VALUE_0="$d/.attrs" \
      GIT_CONFIG_KEY_1=filter.zqxclean.clean GIT_CONFIG_VALUE_1="sed 's/readme/readme $FW_ID/'" \
      PUBLISH_DEST="$d/export" pubrun "$d/checks/publish-skeleton.sh" 2>&1)"; rl_rc=$?
    { [ "$rl_rc" -ne 0 ] && grep -q 'staging changed bytes after the scan' <<<"$rl_out" && grep -q 'firewall: clean' <<<"$rl_out"; }
    rel_bite $? "a clean filter that changes bytes at staging, after the scan, aborts" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # the tag's committed tree, both directions: a token only in the working tree cannot abort the build or
    # reach it, and a token committed at the tag aborts it though the working tree has lost it
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "synthetic note"; printf 'uncommitted — %s\n' "$FW_CLIN" > "$d/README.md"; printf 'x\n' > "$d/adr/untracked.md"
    rel_run "$d" "" v1.0.0
    { [ "$rl_rc" -eq 0 ] && grep -q 'firewall: clean' <<<"$rl_out" && ! grep -q "$FW_CLIN" "$d/export/README.md" && [ ! -e "$d/export/adr/untracked.md" ]; }
    rel_bite $? "the build reads the tag's committed tree, never the working tree" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    d="$(mk_pubrepo "$FW_CLIN")"; pub_tag "$d" v1.0.0 "synthetic note"; printf 'cleaned afterwards\n' > "$d/README.md"
    rel_run "$d" "" v1.0.0
    { [ "$rl_rc" -ne 0 ] && grep -q 'PII tokens found' <<<"$rl_out"; }
    rel_bite $? "a token committed at the tag aborts the build though the working tree no longer has it" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # a public copy that cannot be read is not an empty one
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "synthetic note"
    rel_run "$d" "$d/no-such-remote.git" v1.0.0
    { [ "$rl_rc" -ne 0 ] && grep -q 'cannot read the public copy' <<<"$rl_out" && [ ! -e "$d/no-such-remote.git" ]; }
    rel_bite $? "a REMOTE that cannot be read aborts the release build rather than reading as an empty public copy" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # the tag travels: one commit of no source history, the annotated tag on it, the note word for word
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "$(printf 'v1.0.0 — synthetic\n\nAdoption: routine\nRollback: v0.9.0')"
    rel_run "$d" "" v1.0.0; x="$d/export"
    { [ "$rl_rc" -eq 0 ] && [ "$(inst_git -C "$x" rev-list --count HEAD)" = "1" ] && [ "$(inst_git -C "$x" symbolic-ref --short HEAD)" = "main" ] \
      && [ "$(inst_git -C "$x" cat-file -t refs/tags/v1.0.0)" = "tag" ] && [ "$(inst_git -C "$x" rev-parse 'refs/tags/v1.0.0^{commit}')" = "$(inst_git -C "$x" rev-parse HEAD)" ] \
      && [ "$(inst_git -C "$x" for-each-ref --format='%(contents)' refs/tags/v1.0.0)" = "$(pub_git "$d" for-each-ref --format='%(contents)' refs/tags/v1.0.0)" ] \
      && [ "$(inst_git -C "$x" log -1 --format=%s)" = "Tabularium v1.0.0" ]; }
    rel_bite $? "a release build carries the annotated tag and its note on one new commit" "rc=$rl_rc: $rl_out"
    pub_git "$d" cat-file tag refs/tags/v1.0.0 | sed '1,/^$/d' > "$d/.note-src"; inst_git -C "$x" cat-file tag refs/tags/v1.0.0 | sed '1,/^$/d' > "$d/.note-pub"
    cmp -s "$d/.note-src" "$d/.note-pub"; rel_bite $? "the note's bytes arrive unchanged, trailing newline included" "$(od -c "$d/.note-pub" | tail -3)"
    rm -rf "$d"
    d="$(mk_pubrepo "")"; pub_tag "$d" v0.0.1 "first"; printf 'v1.0.0 kept as written\n\n  indented line\n\n\n' > "$d/.note-in"
    pub_git "$d" tag -a --cleanup=verbatim -F "$d/.note-in" v1.0.0; pub_git "$d" push -q origin refs/tags/v1.0.0
    rel_run "$d" "" v1.0.0
    inst_git -C "$d/export" cat-file tag refs/tags/v1.0.0 | sed '1,/^$/d' > "$d/.note-pub"
    { [ "$rl_rc" -eq 0 ] && cmp -s "$d/.note-in" "$d/.note-pub"; }
    rel_bite $? "a note written verbatim, trailing blank lines and all, arrives byte for byte" "rc=$rl_rc: $(od -c "$d/.note-pub" | tail -3)"
    rm -rf "$d"
    # a signed tag's signature stays behind: it carries the signer's key. The fixture's signature is a fake
    # block git recognises by its marker, so no key is needed.
    d="$(mk_pubrepo "")"; pub_tag "$d" v0.0.1 "unsigned"
    rel_sig="$(printf 'object %s\ntype commit\ntag v1.0.0\ntagger tester <t@t.test> 1700000000 +0000\n\nv1.0.0 signed note\n-----BEGIN PGP SIGNATURE-----\n\nzqxsigblock\n-----END PGP SIGNATURE-----\n' \
      "$(pub_git "$d" rev-parse HEAD)" | pub_git "$d" mktag)" && pub_git "$d" tag v1.0.0 "$rel_sig" && pub_git "$d" push -q origin refs/tags/v1.0.0
    rel_run "$d" "" v1.0.0; x="$d/export"
    { [ "$rl_rc" -eq 0 ] && ! inst_git -C "$x" cat-file tag refs/tags/v1.0.0 | grep -q -e 'BEGIN PGP' -e zqxsigblock \
      && [ "$(inst_git -C "$x" for-each-ref --format='%(contents)' refs/tags/v1.0.0)" = "v1.0.0 signed note" ]; }
    rel_bite $? "a signed tag's signature is not carried to the public tag; its note is" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # the note is scanned: it reaches the public copy and sits in no file. A hit prints no content.
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "note naming $FW_ID"
    rel_run "$d" "" v1.0.0
    { [ "$rl_rc" -ne 0 ] && grep -q "PII tokens found in v1.0.0's note" <<<"$rl_out" && ! grep -q "$FW_ID" <<<"$rl_out" && [ ! -e "$d/export" ]; }
    rel_bite $? "a token in the tag's note aborts the build and prints no content" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    d="$(mk_pubrepo "")"; pub_tag "$d" v1.0.0 "$(printf 'a line that ends in %s\n%s opens the next one' "$FW_PAIR_L" "$FW_PAIR_R")"
    rel_run "$d" "" v1.0.0
    { [ "$rl_rc" -ne 0 ] && grep -q 'wrapped brand phrase' <<<"$rl_out" && [ ! -e "$d/export" ]; }
    rel_bite $? "a registry pair split across a hard wrap in the note aborts too" "rc=$rl_rc: $rl_out"
    rm -rf "$d"
    # the append: first a root commit, then one commit on top, with what left the tree gone from it
    d="$(mk_pubrepo "")"; b="$d/public.git"; rel_mkbare "$b"; printf 'leaves later\n' > "$d/adr/gone.md"; pub_tag "$d" v1.0.0 "first"
    rel_run "$d" "$b" v1.0.0 --push; first="$(inst_git -C "$b" rev-parse --verify --quiet refs/heads/main)"
    { [ "$rl_rc" -eq 0 ] && [ "$(inst_git -C "$b" rev-list --count main)" = "1" ] && [ "$(inst_git -C "$b" rev-parse 'refs/tags/v1.0.0^{commit}')" = "$first" ]; }
    rel_bite $? "the first release pushes a root commit and its tag" "rc=$rl_rc: $rl_out"
    # a public main no release names (an old display copy, a hosting site's starter README) is not built on
    d2="$(mk_pubrepo "")"; b2="$d2/public.git"; rel_mkbare "$b2"; pub_tag "$d2" v1.0.0 "first"
    pub_git "$d2" push -q "$b2" HEAD:refs/heads/main; rel_before="$(rel_refs "$b2")"
    rel_run "$d2" "$b2" v1.0.0 --push
    { [ "$rl_rc" -ne 0 ] && grep -q 'public main is not a release' <<<"$rl_out" && [ "$(rel_refs "$b2")" = "$rel_before" ]; }
    rel_bite $? "a public main that no release names is refused, not built on" "rc=$rl_rc: $rl_out"
    rm -rf "$d2"
    # a release tag on top of commits the export did not make (a starter commit, a private history)
    d2="$(mk_pubrepo "")"; b2="$d2/public.git"; rel_mkbare "$b2"; pub_tag "$d2" v1.0.0 "first"
    pub_git "$d2" push -q "$b2" HEAD:refs/heads/main refs/tags/v1.0.0; pub_annotate "$d2" v1.1.0 "second"
    rel_before="$(rel_refs "$b2")"
    rel_run "$d2" "$b2" v1.1.0 --push
    { [ "$rl_rc" -ne 0 ] && grep -q 'holds commits this export did not make' <<<"$rl_out" && [ "$(rel_refs "$b2")" = "$rel_before" ]; }
    rel_bite $? "a public main under a release tag but made by someone else is refused" "rc=$rl_rc: $rl_out"
    rm -rf "$d2"
    # a first push whose destination names another default branch: pushed, then flagged, since a plain
    # clone would check out nothing
    d2="$(mk_pubrepo "")"; b2="$d2/public.git"; inst_git init -q --bare "$b2"; pub_git "$b2" symbolic-ref HEAD refs/heads/master; pub_tag "$d2" v1.0.0 "first"
    rel_run "$d2" "$b2" v1.0.0 --push
    { [ "$rl_rc" -eq 3 ] && grep -q 'default branch is not main' <<<"$rl_out" && inst_git -C "$b2" rev-parse --verify --quiet refs/tags/v1.0.0 >/dev/null; }
    rel_bite $? "a first push to a copy whose default branch is not main says so and exits 3" "rc=$rl_rc: $rl_out"
    rm -rf "$d2"
    # the push lands but the lookup after it fails: still said, never a silent exit
    d2="$(mk_pubrepo "")"; b2="$d2/public.git"; rel_mkbare "$b2"; pub_tag "$d2" v1.0.0 "first"
    mkdir -p "$d2/.lookshim"; printf '#!/bin/sh\ncase "$*" in *--symref*) exit 2 ;; esac\nexec "%s" "$@"\n' "$(command -v git)" > "$d2/.lookshim/git"; chmod +x "$d2/.lookshim/git"
    rl_out="$(PATH="$d2/.lookshim:$PATH" GIT_ALLOW_PROTOCOL=file GIT_TERMINAL_PROMPT=0 REMOTE="$b2" PUBLISH_DEST="$d2/export" \
      pubrun "$d2/checks/publish-skeleton.sh" v1.0.0 --push 2>&1)"; rl_rc=$?
    { [ "$rl_rc" -eq 3 ] && grep -q 'default branch could not be read' <<<"$rl_out" && inst_git -C "$b2" rev-parse --verify --quiet refs/tags/v1.0.0 >/dev/null; }
    rel_bite $? "a push that lands while the default-branch lookup fails says it was pushed and exits 3" "rc=$rl_rc: $rl_out"
    rm -rf "$d2"
    # a public copy with refs but no main is not empty: a starter branch, or release tags whose main is gone
    for rel_shape in starter tags; do
      d2="$(mk_pubrepo "")"; b2="$d2/public.git"; rel_mkbare "$b2"; pub_tag "$d2" v1.0.0 "first"
      case "$rel_shape" in
        starter) pub_git "$d2" push -q "$b2" HEAD:refs/heads/master ;;
        tags)    pub_git "$d2" push -q "$b2" refs/tags/v1.0.0; pub_annotate "$d2" v1.1.0 "second" ;;
      esac
      rel_before="$(rel_refs "$b2")"
      rel_run "$d2" "$b2" "$([ "$rel_shape" = tags ] && echo v1.1.0 || echo v1.0.0)" --push
      { [ "$rl_rc" -ne 0 ] && grep -q 'holds refs but no main' <<<"$rl_out" && [ "$(rel_refs "$b2")" = "$rel_before" ]; }
      rel_bite $? "a public copy with refs but no main ($rel_shape) is refused, not treated as empty" "rc=$rl_rc: $rl_out"
      rm -rf "$d2"
    done
    printf 'second release\n' >> "$d/README.md"; rm -f "$d/adr/gone.md"; pub_commit "$d" "second release"; pub_annotate "$d" v1.1.0 "second"
    rel_run "$d" "$b" v1.1.0 --push
    { [ "$rl_rc" -eq 0 ] && [ "$(inst_git -C "$b" rev-parse main~1)" = "$first" ] && [ "$(inst_git -C "$b" rev-list --count main)" = "2" ] \
      && [ "$(inst_git -C "$b" rev-parse 'refs/tags/v1.1.0^{commit}')" = "$(inst_git -C "$b" rev-parse main)" ] && [ "$(inst_git -C "$b" rev-parse 'refs/tags/v1.0.0^{commit}')" = "$first" ] \
      && ! inst_git -C "$b" cat-file -e 'main:adr/gone.md' 2>/dev/null && inst_git -C "$b" cat-file -e 'v1.0.0:adr/gone.md' 2>/dev/null \
      && ! inst_git -C "$b" log --format=%s main | grep -q 'source history'; }
    rel_bite $? "the next release appends one commit: the first and its tag stay, a removed file leaves, no source history enters" "rc=$rl_rc: $rl_out"
    # what the public copy's tags refuse. Nothing moves at the remote.
    rel_before="$(rel_refs "$b")"
    rel_run "$d" "$b" v1.1.0 --push
    { [ "$rl_rc" -ne 0 ] && grep -q 'already on the public copy' <<<"$rl_out" && [ "$(rel_refs "$b")" = "$rel_before" ]; }
    rel_bite $? "a tag already on the public copy is refused" "rc=$rl_rc: $rl_out"
    pub_annotate "$d" v1.1.1 "nothing exported changed"
    rel_run "$d" "$b" v1.1.1 --push
    { [ "$rl_rc" -ne 0 ] && grep -q 'changes no exported file' <<<"$rl_out" && [ "$(rel_refs "$b")" = "$rel_before" ]; }
    rel_bite $? "a release that changes no exported file is refused, not pushed as an empty commit" "rc=$rl_rc: $rl_out"
    printf 'tenth\n' >> "$d/README.md"; pub_commit "$d" "tenth"; pub_annotate "$d" v1.10.0 "tenth"
    rel_run "$d" "$b" v1.10.0 --push; [ "$rl_rc" -eq 0 ]; rel_bite $? "v1.10.0 follows v1.1.0: release numbers compare as numbers" "rc=$rl_rc: $rl_out"
    rel_before="$(rel_refs "$b")"; pub_annotate "$d" v1.9.0 "older by number"
    rel_run "$d" "$b" v1.9.0 --push
    { [ "$rl_rc" -ne 0 ] && grep -q 'older than the public copy' <<<"$rl_out" && [ "$(rel_refs "$b")" = "$rel_before" ]; }
    rel_bite $? "a release older than the public copy's newest is refused" "rc=$rl_rc: $rl_out"
    # no force, both refs or neither: the public main moves after the script read it. The push must be rejected
    # and the moved main stay. NEGATIVE CONTROL: the same race with -f in the fixture's copy overwrites it.
    rel_race(){ # $1 = fixture · $2 = bare · $3 = tag · $4 = the git call the race comes before (default push)
      # -> rl_out, rl_rc; $rel_moved = the commit the race put on main
      local _s="$1/.raceshim" _real _when="${4:-push}"; _real="$(command -v git)"; mkdir -p "$_s"
      rel_moved="$(GIT_AUTHOR_NAME=race GIT_AUTHOR_EMAIL=r@t.test GIT_COMMITTER_NAME=race GIT_COMMITTER_EMAIL=r@t.test \
        inst_git -c commit.gpgsign=false -C "$2" commit-tree 'main^{tree}' -p main -m 'moved by someone else')"
      printf '#!/bin/sh\ncase "$1" in %s) "%s" -C "%s" update-ref refs/heads/main %s ;; esac\nexec "%s" "$@"\n' "$_when" "$_real" "$2" "$rel_moved" "$_real" > "$_s/git"
      chmod +x "$_s/git"; rm -rf "$1/export"
      rl_out="$(PATH="$_s:$PATH" GIT_ALLOW_PROTOCOL=file GIT_TERMINAL_PROMPT=0 REMOTE="$2" PUBLISH_DEST="$1/export" \
        pubrun "$1/checks/publish-skeleton.sh" "$3" --push 2>&1)"; rl_rc=$?; rm -rf "$_s"; }
    # a main that moves between the read and the fetch is not built on
    printf 'raced early\n' >> "$d/README.md"; pub_commit "$d" "raced early"; pub_annotate "$d" v1.10.1 "raced early"
    rel_race "$d" "$b" v1.10.1 fetch
    { [ "$rl_rc" -ne 0 ] && grep -q 'moved while this build read it' <<<"$rl_out" && [ "$(inst_git -C "$b" rev-parse main)" = "$rel_moved" ]; }
    rel_bite $? "a public main that moves between its read and its fetch is not built on" "rc=$rl_rc: $rl_out"
    pub_git "$b" update-ref refs/heads/main "$(pub_git "$b" rev-parse 'refs/tags/v1.10.0^{commit}')"
    printf 'raced\n' >> "$d/README.md"; pub_commit "$d" "raced"; pub_annotate "$d" v1.11.0 "raced"
    rel_race "$d" "$b" v1.11.0
    { [ "$rl_rc" -ne 0 ] && [ "$(inst_git -C "$b" rev-parse main)" = "$rel_moved" ] && ! inst_git -C "$b" rev-parse --verify --quiet refs/tags/v1.11.0 >/dev/null; }
    rel_bite $? "the push never forces: a public main that moved after the read rejects it, and the tag does not land alone" "rc=$rl_rc: $rl_out"
    if [ "$(grep -c 'git push -q --atomic origin' "$d/checks/publish-skeleton.sh")" = "1" ]; then
      sed 's/git push -q --atomic origin/git push -q -f --atomic origin/' "$d/checks/publish-skeleton.sh" > "$d/checks/.relrace" && cat "$d/checks/.relrace" > "$d/checks/publish-skeleton.sh" && rm -f "$d/checks/.relrace"
      pub_commit "$d" "forcing copy"; pub_annotate "$d" v1.12.0 "forced"
      # the first race left a main no release names, which is refused now: put the newest release back first
      pub_git "$b" update-ref refs/heads/main "$(pub_git "$b" rev-parse 'refs/tags/v1.10.0^{commit}')"
      rel_race "$d" "$b" v1.12.0
      { [ "$rl_rc" -eq 0 ] && [ "$(inst_git -C "$b" rev-parse main)" != "$rel_moved" ]; }
      rel_bite $? "no-force NEGATIVE CONTROL: with -f in the push line the same race overwrites the public main" "rc=$rl_rc: $rl_out"
    else
      rel_bite 1 "no-force negative control could not identify exactly one push line" ""
    fi
    rm -rf "$d"
    unset -f rel_race

    # --- THE WHOLE ROUTE ON THE REAL TREE: this tree's tracked files as the source, a release cut and exported,
    # a stranger's clone of it, a first person set up by the intake procedure, the care installer, the board:
    # green, and only because of the tag (NEGATIVE CONTROL: the tag gone, the release check reds). Then a second
    # release appended: the notice sees it on the public copy's tags, and adopting it stays green. The registry
    # is synthetic, its tokens made up at run time so no tracked file can hold them. The one fixture that copies
    # the tree (ADR-0038's objection was records and gigabytes, per case): tracked files only, once, here only.
    e2e="$(mktemp -d)" || e2e=""; e2e_tok="zqxr$$x$RANDOM"
    e2e_note(){ printf '%s — synthetic\n\nBump: MINOR — synthetic\nAdoption: routine\nWithdrawn protections: none\nGuards changed: none\nRollback: none\n\nsynthetic\n' "$1"; }
    e2e_git(){ pub_git "$e2e/dev" "$@"; }
    if [ -n "$e2e" ] && mkdir -p "$e2e/dev" "$e2e/home" && ( cd "$ROOT" && inst_git ls-files -z | tar -c --null -T - -f - ) | tar -xf - -C "$e2e/dev"; then
      {
        printf "PII_IDENTITY='%sa'\nPII_CASEREF='%sb'\nPII_CLINICAL='%sc'\nPII_BRAND='%sd'\nPII_CONSENT='%se'\n" "$e2e_tok" "$e2e_tok" "$e2e_tok" "$e2e_tok" "$e2e_tok"
        printf "BRAND_ADJ_PAIRS='%sf %sg'\n" "$e2e_tok" "$e2e_tok"
      } > "$e2e/registry.sh"; chmod 600 "$e2e/registry.sh"
      e2e_git init -q; e2e_git symbolic-ref HEAD refs/heads/main
      e2e_git config user.email t@t.test; e2e_git config user.name tester; e2e_git config commit.gpgsign false; e2e_git config core.hooksPath "$e2e/dev/.git/hooks"
      e2e_git config tag.gpgSign false; e2e_git config tag.forceSignAnnotated false
      e2e_git add -A; e2e_git commit -q -m "synthetic source"
      e2e_git tag -a v9.9.9 -m "$(e2e_note v9.9.9)"
      inst_git init -q --bare "$e2e/dev-origin.git"; e2e_git remote add origin "$e2e/dev-origin.git"
      e2e_git push -q origin HEAD:refs/heads/main refs/tags/v9.9.9
      printf '%s\n' "$e2e/registry.sh" > "$e2e/dev/checks/FIREWALL-REGISTRY"
      e2e_out="$(REMOTE="" PUBLISH_DEST="$e2e/x1" pubrun "$e2e/dev/checks/publish-skeleton.sh" v9.9.9 2>&1)"; e2e_rc=$?
      rel_bite "$e2e_rc" "the whole route: this tree exports at a tag" "$(printf '%s\n' "$e2e_out" | tail -5)"
      # --no-local: through git's transport, as a stranger's clone goes, not by copying object files, which
      # races a repository that packs itself in the background
      inst_git clone -q --no-local --bare "$e2e/x1" "$e2e/public.git"; inst_git -C "$e2e/public.git" symbolic-ref HEAD refs/heads/main
      inst_git clone -q --no-local "$e2e/public.git" "$e2e/care" 2>/dev/null
      [ -d "$e2e/care/.git" ]; rel_bite $? "the whole route: a stranger's full clone of the public copy" ""
      e2e_cgit(){ [ -d "$e2e/care/.git" ] && pub_git "$e2e/care" "$@"; }
      e2e_care(){ ( cd "$e2e/care" || exit 97; env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY -u REMOTE HOME="$e2e/home" "$@" ); }
      e2e_cgit config core.hooksPath "$e2e/care/.git/hooks"
      # the intake procedure, _templates/INTAKE.md section 1, for one person who declines private mode
      e2e_p="$e2e/care/patients/szroute"; mkdir -p "$e2e_p/med/handouts" "$e2e_p/med/sources" "$e2e_p/med/_inbox"
      sed -e 's/{{NAME}}/Synthetic Route/g' -e 's/{{DATE}}/2026-01-01/g' "$e2e/care/_templates/profile.md" > "$e2e_p/profile.md"
      sed -e 's/{{NAME}}/Synthetic Route/g' -e 's/{{DATE}}/2026-01-01/g' "$e2e/care/_templates/medications.md" > "$e2e_p/medications.md"
      sed -e 's/{{NAME}}/Synthetic Route/g' -e 's/{{DATE}}/2026-01-01/g' "$e2e/care/_templates/person/med/handouts/INDEX.md" > "$e2e_p/med/handouts/INDEX.md"
      printf '# Roster\n\n- szroute — self\n' > "$e2e/care/patients/README.md"
      e2e_out="$(e2e_care python3 -m tools.person_ownership --root . init szroute 2>&1)"; e2e_rc=$?
      rel_bite "$e2e_rc" "the whole route: the first person's ledger is initialised" "$e2e_out"
      e2e_out="$(e2e_care bash checks/install-instance.sh care v9.9.9 2>&1)"; e2e_rc=$?
      rel_bite "$e2e_rc" "the whole route: the care installer pins the tag" "$(printf '%s\n' "$e2e_out" | tail -5)"
      e2e_out="$(e2e_care bash checks/check.sh 2>&1)"; e2e_rc=$?
      { [ "$e2e_rc" -eq 0 ] && grep -q 'L19 CARE anchor: HEAD = pinned release v9.9.9, reachable from origin' <<<"$e2e_out"; }
      rel_bite $? "the whole route: a first care session on a public clone ends green" "rc=$e2e_rc: $(printf '%s\n' "$e2e_out" | grep -E '^FAIL|^OK')"
      e2e_cgit tag -d v9.9.9 >/dev/null 2>&1
      e2e_out="$(e2e_care bash checks/check.sh 2>&1)"; e2e_rc=$?
      { [ "$e2e_rc" -ne 0 ] && grep -q 'FAIL \[L19\].*does not exist in this checkout' <<<"$e2e_out"; }
      rel_bite $? "the whole route NEGATIVE CONTROL: the same clone without its tag reds on the release check" "rc=$e2e_rc: $(printf '%s\n' "$e2e_out" | grep -E '^FAIL|^OK')"
      e2e_cgit fetch -q --tags origin 2>/dev/null
      # the second release: the same script builds it on the public main; this bite's own push stands in for the
      # ceremony, since a copy of this tree can carry the hold
      printf '\nsynthetic second release\n' >> "$e2e/dev/README.md"; e2e_git add README.md; e2e_git commit -q -m "synthetic second"
      e2e_git tag -a v9.10.0 -m "$(e2e_note v9.10.0)"; e2e_git push -q origin HEAD:refs/heads/main refs/tags/v9.10.0
      e2e_out="$(REMOTE="$e2e/public.git" PUBLISH_DEST="$e2e/x2" pubrun "$e2e/dev/checks/publish-skeleton.sh" v9.10.0 2>&1)"; e2e_rc=$?
      inst_git -C "$e2e/x2" push -q origin refs/heads/main refs/tags/v9.10.0 2>/dev/null
      { [ "$e2e_rc" -eq 0 ] && [ "$(inst_git -C "$e2e/public.git" rev-list --count main)" = "2" ]; }
      rel_bite $? "the whole route: the second release appends on the public main" "rc=$e2e_rc: $(printf '%s\n' "$e2e_out" | tail -5)"
      e2e_out="$(e2e_care bash checks/release-notice.sh 2>&1)"; e2e_rc=$?
      { [ "$e2e_rc" -eq 1 ] && grep -qx 'pinned=v9.9.9' <<<"$e2e_out" && grep -qx 'newest=v9.10.0' <<<"$e2e_out" && grep -qx 'gap=minor' <<<"$e2e_out"; }
      rel_bite $? "the whole route: the release notice sees the public copy's tags" "rc=$e2e_rc: $e2e_out"
      e2e_out="$(e2e_care bash checks/adopt-release.sh 2>&1)"; e2e_rc=$?
      rel_bite "$e2e_rc" "the whole route: adopting the appended release ends green" "$(printf '%s\n' "$e2e_out" | tail -5)"
      e2e_out="$(e2e_care bash checks/release-notice.sh 2>&1)"; e2e_rc=$?
      { [ "$e2e_rc" -eq 0 ] && grep -qx 'pinned=v9.10.0' <<<"$e2e_out" && grep -qx 'gap=none' <<<"$e2e_out"; }
      rel_bite $? "the whole route: after adopting, the notice has nothing to say" "rc=$e2e_rc: $e2e_out"
    else
      rel_bite 1 "the whole route: could not copy this tree's tracked files" ""
    fi
    [ -z "$e2e" ] || rm -rf "$e2e"
    unset -f e2e_note e2e_git e2e_care e2e_cgit 2>/dev/null

    # --- THE WRAPPED-BRAND ADJACENCY LANE: the main ERE is line-oriented, so a guarded two-word phrase broken
    # by a hard wrap, Markdown emphasis, a link or an inline tag would cross it. Pairs come from the registry
    # (BRAND_ADJ_PAIRS); the fixture's brand CLASS is an opaque token, so only this lane can produce these
    # aborts. The lane lowercases and keeps ASCII and accented Latin letters as word letters.
    wb_split(){ # $1=label $2=first word $3=second word $4=shape  -> expect ABORT
      local d; d="$(mk_pubrepo "")"; mkdir -p "$d/adr"
      case "$4" in
        wrap)   printf 'a line that ends in %s\n%s opens the next one\n' "$2" "$3" > "$d/adr/wb.md" ;;
        emph)   printf 'inline *%s*, %s and on we go\n' "$2" "$3" > "$d/adr/wb.md" ;;
        link)   printf 'see [%s](http://example.invalid/x) %s below\n' "$2" "$3" > "$d/adr/wb.md" ;;
        markup) printf '%s<br/>%s\n' "$2" "$3" > "$d/adr/wb.md" ;;
      esac
      fw_expect "wrapped-brand: $1" "$d" abort 'wrapped brand phrase'; }
    wb_clean(){ # $1=label $2=file body  -> expect CLEAN
      local d; d="$(mk_pubrepo "")"; mkdir -p "$d/adr"; printf '%s' "$2" > "$d/adr/wb.md"
      fw_expect "wrapped-brand precision: $1 passes clean" "$d" clean ""; }
    wb_split "a registry pair split across a hard wrap aborts"  "$FW_PAIR_L" "$FW_PAIR_R" wrap
    wb_split "the same pair split by Markdown emphasis aborts"  "$FW_PAIR_L" "$FW_PAIR_R" emph
    wb_split "the same pair split by a Markdown link aborts"    "$FW_PAIR_L" "$FW_PAIR_R" link
    wb_split "the same pair split by an inline HTML tag aborts" "$FW_PAIR_L" "$FW_PAIR_R" markup
    # PRECISION three ways: the pair is ORDERED, each side is a WHOLE word, a blank line resets adjacency
    wb_clean "the same two words in the wrong order"   "$(printf 'a line that ends in %s\n%s opens the next one\n' "$FW_PAIR_R" "$FW_PAIR_L")"
    wb_clean "a longer word merely starting with the left side" "$(printf 'a line that ends in %sbet\n%s opens the next one\n' "$FW_PAIR_L" "$FW_PAIR_R")"
    wb_clean "the pair separated by a blank line (paragraph reset)" "$(printf 'a line that ends in %s\n\n%s opens the next one\n' "$FW_PAIR_L" "$FW_PAIR_R")"
    # NEGATIVE CONTROL: delete the lane's pair-match line from the copied script and the split fixture must
    # sail through. Without this, every abort above could be coming from somewhere else.
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"
    printf 'a line that ends in %s\n%s opens the next one\n' "$FW_PAIR_L" "$FW_PAIR_R" > "$d/adr/wb.md"
    sed '/if (prev ~ L\[k\] && word ~ R\[k\]) exit 42/d' "$d/checks/publish-skeleton.sh" > "$d/checks/.wbtmp" \
      && mv "$d/checks/.wbtmp" "$d/checks/publish-skeleton.sh"
    fw_expect "wrapped-brand NEGATIVE CONTROL: with the pair-match line deleted the split fixture passes" "$d" clean ""
    # ACCENTED LETTERS: the macOS awk and Linux mawk are byte-oriented, so the lane once stripped every
    # accented letter and a pair word with a diacritic could never match. Capitals in the text, lower case in
    # the registry. Precision: the same words spelled without their diacritics are different words.
    # NEGATIVE CONTROL: delete the line that keeps accented letters and the split fixture passes again.
    wb_split "an accented pair in capitals split across a hard wrap aborts" "GĘŚLĄ" "Jaźń" wrap
    wb_clean "the accented pair spelled without its diacritics" "$(printf 'a line that ends in gesla\njazn opens the next one\n')"
    d="$(mk_pubrepo "")"; mkdir -p "$d/adr"
    printf 'a line that ends in GĘŚLĄ\nJaźń opens the next one\n' > "$d/adr/wb.md"
    if [ "$(grep -c 'gsub(AC\[j\], CD\[j\], line)' "$d/checks/publish-skeleton.sh")" = "1" ]; then
      sed '/gsub(AC\[j\], CD\[j\], line)/d' "$d/checks/publish-skeleton.sh" > "$d/checks/.wbtmp" \
        && mv "$d/checks/.wbtmp" "$d/checks/publish-skeleton.sh"
      fw_expect "accented-pair NEGATIVE CONTROL: without the line that keeps accented letters the split passes" "$d" clean ""
    else
      echo "FIRE  MISS (accented-pair negative control could not identify exactly one letter-keeping line)"; fail=$((fail+1)); rm -rf "$d"
    fi
    # FAIL CLOSED on the variable itself: absent and empty are the same answer, before any scan verdict; a
    # pair that is not two sides is an UNSCANNED lane and aborts as a scan error
    d="$(mk_pubrepo "")"; rf="$(fw_regfile "$d")"
    grep -v '^BRAND_ADJ_PAIRS=' "$rf" > "$d/checks/.wbreg" && mv "$d/checks/.wbreg" "$rf" && chmod 600 "$rf"
    fw_expect "a registry with no BRAND_ADJ_PAIRS aborts before any scan verdict" "$d" abort 'BRAND_ADJ_PAIRS missing'
    d="$(mk_pubrepo "")"; rf="$(fw_regfile "$d")"
    sed "s|^BRAND_ADJ_PAIRS=.*|BRAND_ADJ_PAIRS=''|" "$rf" > "$d/checks/.wbreg" && mv "$d/checks/.wbreg" "$rf" && chmod 600 "$rf"
    fw_expect "an EMPTY BRAND_ADJ_PAIRS aborts too" "$d" abort 'BRAND_ADJ_PAIRS missing'
    d="$(mk_pubrepo "")"; rf="$(fw_regfile "$d")"
    sed "s|^BRAND_ADJ_PAIRS=.*|BRAND_ADJ_PAIRS='oneword'|" "$rf" > "$d/checks/.wbreg" && mv "$d/checks/.wbreg" "$rf" && chmod 600 "$rf"
    fw_expect "a malformed pair fails the lane CLOSED as a scan error" "$d" abort 'wrapped-brand scan errored'

    # --- THE EVAL-CASE CLASSIFICATION (ADR-0049 publish posture): `evals/cases` is not a directory ALLOW
    # entry, so a case file that merely appears in the tree is private. That default is safe only while
    # "private" is a decision: every evals/cases/*.md must be an ALLOW entry OR a line in evals/cases/HOLDOUT.
    # Static (no export run) and fail closed — an unreadable ALLOW block is rc=2, no case examined rc=3.
    holdout_unclassified(){ # $1 = tree root -> unclassified paths on stdout; rc=2 = could not classify
      local _r="$1" _pub="$1/checks/publish-skeleton.sh" _hold="$1/evals/cases/HOLDOUT"
      local _allow _list _c _rel _bad="" _grc _n=0
      _allow="$(allow_entries "$_pub")" || return 2
      _list=""
      # a MISSING HOLDOUT means the holdout set is empty, which can only make this stricter
      if [ -f "$_hold" ]; then
        _list="$(sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$_hold" | grep -v '^$')" || _list=""
      fi
      for _c in "$_r"/evals/cases/*.md; do
        [ -f "$_c" ] || continue
        _n=$((_n+1))
        _rel="evals/cases/$(basename "$_c")"
        # here-strings, never a pipe: under pipefail a `printf | grep -q` reports printf's SIGPIPE
        grep -qxF -- "$_rel" <<<"$_allow"; _grc=$?
        [ "$_grc" -eq 0 ] && continue
        [ "$_grc" -ge 2 ] && return 2
        grep -qxF -- "$_rel" <<<"$_list"; _grc=$?
        [ "$_grc" -eq 0 ] && continue
        [ "$_grc" -ge 2 ] && return 2
        _bad="$_bad $_rel"
      done
      [ "$_n" -ge 1 ] || return 3
      printf '%s' "$_bad"; return 0; }
    hu="$(holdout_unclassified "$ROOT")"; rc=$?
    if [ "$rc" -eq 0 ] && [ -z "$hu" ]; then
      echo "BITE  OK  (every evals/cases/*.md is classified — ALLOW-listed or named in evals/cases/HOLDOUT)"; pass=$((pass+1))
    else
      echo "BITE  MISS (eval-case classification: rc=$rc — 2 = ALLOW block unparseable, 3 = no evals/cases/*.md examined, else unclassified:$hu)"; fail=$((fail+1))
    fi
    # the fixture directions; EV-99 is synthetic and matches no real case
    hd="$(mktemp -d)"; mkdir -p "$hd/checks" "$hd/evals/cases"
    cp "$PUB" "$hd/checks/publish-skeleton.sh"
    printf 'synthetic case spec\n' > "$hd/evals/cases/EV-99-holdout-bite.md"
    hu="$(holdout_unclassified "$hd")"; rc=$?
    if [ "$rc" -eq 0 ] && [ "$hu" = " evals/cases/EV-99-holdout-bite.md" ]; then
      echo "BITE  OK  (an eval case in neither list is caught — the classification is fail-closed)"; pass=$((pass+1))
    else
      echo "BITE  MISS (an unclassified eval case went unnoticed, rc=$rc):$hu"; fail=$((fail+1))
    fi
    printf '# synthetic holdout list\nevals/cases/EV-99-holdout-bite.md\n' > "$hd/evals/cases/HOLDOUT"
    hu="$(holdout_unclassified "$hd")"; rc=$?
    if [ "$rc" -eq 0 ] && [ -z "$hu" ]; then
      echo "BITE  OK  (naming the case in HOLDOUT classifies it — held back is an accepted answer)"; pass=$((pass+1))
    else
      echo "BITE  MISS (a HOLDOUT-listed case still read as unclassified, rc=$rc):$hu"; fail=$((fail+1))
    fi
    rm -f "$hd/evals/cases/HOLDOUT"
    awk '/^ALLOW=\(/{print; print "  evals/cases/EV-99-holdout-bite.md"; next} {print}' \
      "$PUB" > "$hd/checks/publish-skeleton.sh"
    hu="$(holdout_unclassified "$hd")"; rc=$?
    if [ "$rc" -eq 0 ] && [ -z "$hu" ]; then
      echo "BITE  OK  (an ALLOW entry classifies it too — promotion is the other accepted answer)"; pass=$((pass+1))
    else
      echo "BITE  MISS (an ALLOW-listed case still read as unclassified, rc=$rc):$hu"; fail=$((fail+1))
    fi
    rm -f "$hd/checks/publish-skeleton.sh"
    hu="$(holdout_unclassified "$hd")"; rc=$?
    if [ "$rc" -eq 2 ]; then
      echo "BITE  OK  (an unreadable ALLOW block fails the classification CLOSED, not clean)"; pass=$((pass+1))
    else
      echo "BITE  MISS (missing ALLOW block should be rc=2, got rc=$rc):$hu"; fail=$((fail+1))
    fi
    rm -rf "$hd"
  fi
elif [ "$EXPORT_MATRIX" -eq 1 ]; then
  echo "FIRE  MISS (--export asked for the export gate matrix, but publish-skeleton.sh is not present)"; fail=$((fail+1))
else
  skip export-gate "publish-skeleton.sh not present — the export gate cannot be bitten here"
fi

# git environment — the strip at this file's entry is what keeps a hook's GIT_DIR out of every fixture.
# Test: that line, read from this file, then the first git calls of a fixture as mk_hookrepo makes them, with
# GIT_DIR and GIT_INDEX_FILE aimed at a DECOY repository: the decoy's config stays byte-identical and the fixture is
# a repository of its own. Control: the same calls without the strip write into the decoy, so the inherited
# variable really redirects `git -C` here and the test is not vacuous. Never a hook case: no commit, no hook runs.
if command -v git >/dev/null 2>&1; then
  ge_line="$(grep -m1 '^unset GIT_DIR ' "$ROOT/checks/selftest.sh")"
  ge_run(){ # $1 = code run first ('' = none) -> "<decoy untouched: yes|no> <fixture has .git: yes|no>"
    local base same own; base="$(mktemp -d)"
    git init -q "$base/decoy" >/dev/null 2>&1; cp "$base/decoy/.git/config" "$base/config.orig"; mkdir "$base/fx"
    ( export GIT_DIR="$base/decoy/.git" GIT_INDEX_FILE="$base/decoy/.git/index"; eval "$1"
      git -C "$base/fx" init -q; git -C "$base/fx" config user.name tester
      git -C "$base/fx" config core.hooksPath "$base/fx/.git/hooks"
      : > "$base/fx/staged"; git -C "$base/fx" add staged ) >/dev/null 2>&1
    # untouched = its config byte-identical AND no index written (the fresh decoy has none; GIT_INDEX_FILE would make one)
    cmp -s "$base/decoy/.git/config" "$base/config.orig" && [ ! -e "$base/decoy/.git/index" ] && same=yes || same=no
    [ -d "$base/fx/.git" ] && own=yes || own=no
    rm -rf "$base"; echo "$same $own"; }
  ge_with="$([ -n "$ge_line" ] && ge_run "$ge_line")"; ge_without="$(ge_run '')"
  if [ -n "$ge_line" ] && [ "$ge_with" = "yes yes" ]; then
    echo "BITE  OK  (git env: after the entry strip, a hook's GIT_DIR aimed at a decoy never reaches a fixture's git -C)"; pass=$((pass+1))
  else
    echo "BITE  MISS (git env: entry strip line ${ge_line:+found}${ge_line:-NOT found}; decoy identical / fixture own repo = ${ge_with:-not run})"; fail=$((fail+1))
  fi
  if [ "$ge_without" = "no no" ]; then
    echo "BITE  OK  (git env control: without the strip the same calls write into the decoy)"; pass=$((pass+1))
  else
    echo "BITE  MISS (git env control: without the strip the decoy was not reached — '$ge_without'; the test proves nothing)"; fail=$((fail+1))
  fi
else
  skip git-env "git absent — the inherited-git-environment bite was NOT run"
fi

# Git hooks (ADR-0022): pre-commit blocks a red tree and allows a green one; commit-msg holds the audit half of
# the two-factor override; pre-merge-commit gates the auto-committed merge git routes past pre-commit; pre-push
# is instance-aware (ADR-0050). Built on MINIMAL SYNTHETIC git repos (no real patient data). Skipped when
# TABULARIUM_NO_HOOK_TEST=1, for a caller that runs this suite from inside a git hook, so a hook can never
# recurse back through these cases.
if [ -z "${TABULARIUM_NO_HOOK_TEST:-}" ] && command -v git >/dev/null 2>&1; then
  PRE="$ROOT/checks/git-hooks/pre-commit"; CMSG="$ROOT/checks/git-hooks/commit-msg"

  mk_hookrepo(){ # -> path to a fresh minimal repo (VALID profile, real check.sh, hooks installed)
    local d; d="$(mktemp -d)"
    git -C "$d" init -q
    git -C "$d" config user.email t@t.test; git -C "$d" config user.name tester
    git -C "$d" config commit.gpgsign false                 # don't trip a globally-enabled signer
    git -C "$d" config core.hooksPath "$d/.git/hooks"        # force per-repo hooks (ignore any global hooksPath)
    mkdir -p "$d/checks"
    : > "$d/CLAUDE.md"
    cp "$ROOT/checks/check.sh" "$d/checks/check.sh"
    printf '#!/bin/sh\nexit 0\n' > "$d/checks/selftest.sh"
    chmod +x "$d/checks/selftest.sh"
    # the copied check.sh loads its L13/L15 verifier packages from ITS OWN root, so the fixture carries them
    mkdir -p "$d/tools/person_ownership" "$d/tools/handout_attest"
    cp "$ROOT/tools/__init__.py" "$d/tools/__init__.py" 2>/dev/null || :
    cp "$ROOT/tools/person_ownership/"*.py "$d/tools/person_ownership/"
    cp "$ROOT/tools/handout_attest/"*.py "$d/tools/handout_attest/"
    mkdir -p "$d/_templates/handout-assets"
    printf 'synthetic renderer baseline\n' > "$d/_templates/handout-assets/render_handout.py"
    cp "$PRE"  "$d/.git/hooks/pre-commit"; chmod +x "$d/.git/hooks/pre-commit"
    cp "$CMSG" "$d/.git/hooks/commit-msg"; chmod +x "$d/.git/hooks/commit-msg"
    valid_profile "$d/patients/szthook/profile.md"
    echo "$d"
  }
  break_profile(){ printf '# Profile — t\n## Active conditions\n| a | b |\n|---|---|\n| x | y |\n' > "$1/patients/szthook/profile.md"; }
  try_commit(){ # dir msg [VAR=val] -> returns git commit rc (0 = committed)
    local d="$1" msg="$2" envassign="${3:-}"
    git -C "$d" add -A >/dev/null 2>&1
    env $envassign git -C "$d" commit -q -m "$msg" >/dev/null 2>&1
  }
  hook_assert(){ # label expected(ok|block) actual_rc
    if   [ "$2" = ok    ] && [ "$3" -eq 0 ]; then echo "HOOK  OK  ($1)"; pass=$((pass+1))
    elif [ "$2" = block ] && [ "$3" -ne 0 ]; then echo "HOOK  OK  ($1)"; pass=$((pass+1))
    else echo "HOOK  MISS ($1): expected $2, commit rc=$3"; fail=$((fail+1)); fi; }

  # pre-commit: a red tree (the truncated profile, the L1 incident) is BLOCKED; a green tree commits
  d="$(mk_hookrepo)"; break_profile "$d"; try_commit "$d" "broken tree"; hook_assert "red tree blocked" block $?; rm -rf "$d"
  d="$(mk_hookrepo)"; try_commit "$d" "valid synthetic tree"; hook_assert "green tree commits" ok $?; rm -rf "$d"
  # commit-msg: the override engaged but NOT named in the message is BLOCKED; named, it is allowed
  d="$(mk_hookrepo)"; break_profile "$d"; try_commit "$d" "quick fix" "TABULARIUM_SKIP_GUARD=1"; hook_assert "override unnamed in msg -> blocked" block $?; rm -rf "$d"
  d="$(mk_hookrepo)"; break_profile "$d"; try_commit "$d" "emergency: TABULARIUM_SKIP_GUARD - reason" "TABULARIUM_SKIP_GUARD=1"; hook_assert "override named in msg -> allowed" ok $?; rm -rf "$d"

  # pre-merge-commit: git runs it, never pre-commit, for an auto-committed merge — a red lane once landed on
  # main through `git merge --no-ff` with check.sh never executed. Green baseline, a side branch committed
  # --no-verify, merged back.
  PMC="$ROOT/checks/git-hooks/pre-merge-commit"
  mk_mergerepo(){ # $1 = side kind (red|green) -> repo on its base branch with branch `side` ready to merge
    local d; d="$(mk_hookrepo)"
    git -C "$d" add -A >/dev/null 2>&1
    git -C "$d" commit -q --no-verify -m "fixture baseline" >/dev/null 2>&1
    git -C "$d" checkout -q -b side >/dev/null 2>&1
    if [ "$1" = red ]; then break_profile "$d"; else printf 'benign lane file\n' > "$d/lane.txt"; fi
    git -C "$d" add -A >/dev/null 2>&1
    git -C "$d" commit -q --no-verify -m "side work" >/dev/null 2>&1
    git -C "$d" checkout -q - >/dev/null 2>&1
    echo "$d"
  }
  try_merge(){ git -C "$1" merge -q --no-ff -m "merge side" side >/dev/null 2>&1; }
  d="$(mk_mergerepo red)"; cp "$PMC" "$d/.git/hooks/pre-merge-commit"; chmod +x "$d/.git/hooks/pre-merge-commit"
  try_merge "$d"; hook_assert "auto-committed red merge blocked by pre-merge-commit" block $?; rm -rf "$d"
  d="$(mk_mergerepo green)"; cp "$PMC" "$d/.git/hooks/pre-merge-commit"; chmod +x "$d/.git/hooks/pre-merge-commit"
  try_merge "$d"; hook_assert "auto-committed green merge allowed through pre-merge-commit" ok $?; rm -rf "$d"

  # pre-push: ADR-0017's unconditional block became "DEV and record-free". The marker alone never authorises —
  # the hook re-derives the observable exactly as L20 does — so a tree marked `dev` with records on disk is the
  # case that fails the moment the observable check is removed. Fixtures push FOR REAL into a local bare
  # origin, so they exercise git's own hook invocation. Every git call strips the inherited git environment.
  PPUSH="$ROOT/checks/git-hooks/pre-push"
  ppgit(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY git "$@"; }
  mk_pushrepo(){ # -> "<tmp>/dev"; the parent temp dir also holds origin.git and is what pp_rm reaps
    local d o w; d="$(mktemp -d)"; o="$d/origin.git"; w="$d/dev"
    ppgit init -q --bare "$o" >/dev/null 2>&1; ppgit -C "$o" symbolic-ref HEAD refs/heads/main
    mkdir -p "$w/checks"; : > "$w/CLAUDE.md"
    cp "$ROOT/checks/RECORD-SET" "$w/checks/RECORD-SET"; cp "$ROOT/.gitignore" "$w/.gitignore"
    # the hook asks `checks/check.sh --instance-mode` for the checkout family: the fixture must carry it
    cp "$ROOT/checks/check.sh" "$w/checks/check.sh"; chmod +x "$w/checks/check.sh"
    ppgit -C "$w" init -q >/dev/null 2>&1; ppgit -C "$w" symbolic-ref HEAD refs/heads/main
    ppgit -C "$w" config user.email t@t.test; ppgit -C "$w" config user.name tester
    ppgit -C "$w" config commit.gpgsign false; ppgit -C "$w" config core.hooksPath "$w/.git/hooks"
    ppgit -C "$w" add -A >/dev/null 2>&1; ppgit -C "$w" commit -q -m "product" >/dev/null 2>&1
    ppgit -C "$w" remote add origin "$o"
    cp "$PPUSH" "$w/.git/hooks/pre-push"; chmod +x "$w/.git/hooks/pre-push"
    printf '%s\n' "$w"; }
  # teardown climbs one level, so it refuses anything that is not the absolute `<mktemp -d>/dev` shape
  pp_rm(){ case "${1:-}" in
      /*/dev) rm -rf "$(dirname "$1")" ;;
      *) echo "HOOK  MISS (pre-push fixtures: refusing to remove '${1:-<empty>}' — not a fixture path)"; fail=$((fail+1)) ;;
    esac; }
  pp_case(){ # label expected(ok|block) want-substring [marker] [record-dir]
    local lbl="$1" exp="$2" want="$3" mark="${4:-}" rec="${5:-}" w out rc want_rc=0
    w="$(mk_pushrepo)"
    [ -n "$mark" ] && printf '%s\n' "$mark" > "$w/.tabularium-instance"
    [ -n "$rec" ] && mkdir -p "$w/$rec"
    out="$(ppgit -C "$w" push origin main 2>&1)"; rc=$?
    if [ "$exp" = ok ]; then [ "$rc" -eq 0 ] && want_rc=1; else [ "$rc" -ne 0 ] && want_rc=1; fi
    if [ "$want_rc" -eq 1 ] && grep -qF "$want" <<<"$out"; then
      echo "HOOK  OK  ($lbl)"; pass=$((pass+1))
    else
      echo "HOOK  MISS ($lbl): expected $exp + '$want', push rc=$rc"; fail=$((fail+1))
    fi
    pp_rm "$w"; }
  pp_case "pre-push: marked dev but records present -> blocked" block "reason: records present" dev patients/evalperson-a
  pp_case "pre-push: dev + no records -> push allowed" ok "pre-push: DEV instance, no records — push allowed" dev
  # An unknown marker (an old `migration:` one included, ADR-0050 point 14). Two consumers read one
  # derivation, so both run on ONE fixture and must agree: guard L20 reds it as an unknown marker naming
  # dev | care, and the push hook blocks it. The clean twin is the same fixture marked `dev`, where both pass.
  pp_agree(){ # label marker expected(ok|block)
    local lbl="$1" mark="$2" exp="$3" w bout brc pout prc
    w="$(mk_pushrepo)"; printf '%s\n' "$mark" > "$w/.tabularium-instance"
    bout="$(bash "$CHECK" "$w" 2>&1)"; brc=$?
    pout="$(ppgit -C "$w" push origin main 2>&1)"; prc=$?
    if [ "$exp" = block ] && [ "$brc" -ne 0 ] && [ "$prc" -ne 0 ] \
       && grep -qF "FAIL [L20] unknown instance marker '$mark' — expected dev | care" <<<"$bout" \
       && grep -qF "marker is $mark" <<<"$pout"; then
      echo "HOOK  OK  ($lbl)"; pass=$((pass+1))
    elif [ "$exp" = ok ] && [ "$brc" -eq 0 ] && [ "$prc" -eq 0 ] \
       && grep -q 'L20 instance: dev — record-free' <<<"$bout" \
       && grep -qF 'pre-push: DEV instance, no records — push allowed' <<<"$pout"; then
      echo "HOOK  OK  ($lbl)"; pass=$((pass+1))
    else
      echo "HOOK  MISS ($lbl): expected both to $exp — board rc=$brc, push rc=$prc"
      { echo "$bout"; echo "$pout"; } | sed 's/^/      /' | tail -8; fail=$((fail+1))
    fi
    pp_rm "$w"; }
  pp_agree "L20 + pre-push agree: an unknown marker -> board red, push blocked" staging block
  pp_agree "L20 + pre-push agree: the same fixture marked dev -> board green, push allowed (clean twin)" dev ok
  # A pushed ref that is NOT the checked-out one (ADR-0022 point 6): what leaves is that ref's own
  # tree, so one that tracks a record path is refused though HEAD and the disk are record-free. The pair above
  # cannot see this — both push `main`, and the disk probe already decides them, so they pass with the per-ref
  # check removed. `side` is built in a scratch clone and fetched in, so no checkout touches the fixture.
  w="$(mk_pushrepo)"; echo dev > "$w/.tabularium-instance"; pps="$(dirname "$w")/side"
  ppgit clone -q --no-local "$w" "$pps" >/dev/null 2>&1
  ppgit -C "$pps" config user.email t@t.test; ppgit -C "$pps" config user.name tester
  ppgit -C "$pps" config commit.gpgsign false
  mkdir -p "$pps/patients/evalperson-a"; printf 'synthetic\n' > "$pps/patients/evalperson-a/profile.md"
  ppgit -C "$pps" add -f patients >/dev/null 2>&1
  ppgit -C "$pps" -c core.hooksPath=/dev/null commit -q -m "side tracks a record path" >/dev/null 2>&1
  ppgit -C "$w" fetch -q "$pps" HEAD:refs/heads/side >/dev/null 2>&1
  pptip="$(ppgit -C "$w" rev-parse --verify --quiet refs/heads/side 2>/dev/null)"
  pphead="$(ppgit -C "$w" rev-parse HEAD 2>/dev/null)"
  out="$(ppgit -C "$w" push origin side 2>&1)"; rc=$?
  if [ -z "$pptip" ] || [ "$pptip" = "$pphead" ] || [ -e "$w/patients" ] \
     || ! ppgit -C "$w" cat-file -e "refs/heads/side:patients/evalperson-a/profile.md" 2>/dev/null; then
    # fixture-setup guard: without a distinct, un-checked-out `side` that tracks the record, nothing is under test
    echo "HOOK  MISS (pre-push: a non-HEAD ref whose tree tracks a record path): fixture setup — side=${pptip:-<none>}"; fail=$((fail+1))
  elif [ "$rc" -ne 0 ] && grep -qF "reason: records in a pushed ref — refs/heads/side tracks" <<<"$out"; then
    echo "HOOK  OK  (pre-push: a non-HEAD ref whose tree tracks a record path -> blocked)"; pass=$((pass+1))
  else
    echo "HOOK  MISS (pre-push: a non-HEAD ref whose tree tracks a record path), push rc=$rc"; echo "$out" | sed 's/^/      /' | tail -4; fail=$((fail+1))
  fi
  pp_rm "$w"
elif [ -n "${TABULARIUM_NO_HOOK_TEST:-}" ]; then
  skip hooks "TABULARIUM_NO_HOOK_TEST is set — the git-hook bites were NOT run"
else
  skip hooks "git absent — the git-hook bites were NOT run"
fi

# Handout renderer (ADR-0039): runs ONLY when the pinned venv exists (weasyprint is a host install, not a repo
# file) and is loudly SKIPPED otherwise — CI has none, so only a local pre-PR run exercises it. Strict sealing
# anchors to the repository that OWNS the renderer, so each fixture gets a local runtime copy.
RVENV="$ROOT/.venv-render/bin/python"
if [ -x "$RVENV" ] && "$RVENV" -c 'import markdown, weasyprint' >/dev/null 2>&1; then
  run_fixture_renderer(){ # fixture-root renderer-args...
    local fx="$1" assets
    shift
    assets="$fx/_templates/handout-assets"
    if [ ! -f "$assets/render_handout.py" ]; then
      mkdir -p "$assets" "$fx/tools/private-mode"
      cp "$ROOT/_templates/handout-assets/render_handout.py" "$assets/render_handout.py"
      cp "$ROOT/_templates/handout-assets/handout.css" "$assets/handout.css"
      cp "$ROOT/_templates/handout-assets/preview.css" "$assets/preview.css"
      cp -R "$ROOT/_templates/handout-assets/fonts" "$assets/fonts"
      cp "$ROOT/tools/private-mode/identity.py" "$fx/tools/private-mode/identity.py"
      mkdir -p "$fx/tools/handout_attest"
      cp "$ROOT/tools/handout_attest/handout_id.py" "$fx/tools/handout_attest/handout_id.py"
    fi
    "$RVENV" "$assets/render_handout.py" "$@"
  }
  d="$(mk)"; valid_profile "$d/patients/sztseal/profile.md"
  RB="$d/patients/sztseal/med/handouts/patient/2026-07-16-render"
  mkdir -p "$RB"
  RMD="$RB/2026-07-16__handout-patient__render-bite.md"
  printf 'id: TAB-ZZZ-999A\ndate: 2026-07-16\nlang: pl\n\n# Karta testowa\n\nTresc syntetyczna do proby renderowania.\n' > "$RMD"
  printf '| %s | current |\n' "2026-07-16-render" >> "$d/patients/sztseal/med/handouts/INDEX.md"
  # test: a seal without a factcheck sidecar → the gate refuses with rc=4 and writes NOTHING
  run_fixture_renderer "$d" "$RMD" >/dev/null 2>&1; rc=$?
  if [ "$rc" -eq 4 ] && [ ! -f "${RMD%.md}.pdf" ] && [ ! -f "${RMD%.md}.attest.json" ]; then
    echo "BITE  OK  (renderer gate refuses an unverified seal, rc=4, no artifacts)"; pass=$((pass+1))
  else
    echo "BITE  MISS (renderer gate: expected rc=4 + no artifacts, got rc=$rc)"; fail=$((fail+1))
  fi
  # test (ADR-0070): a five-line PASS sidecar binds the record; the medications list changed after the
  # verify → the real seal refuses with rc=4, says so and writes NOTHING (the person folder is wired in)
  RP="$d/patients/sztseal"
  printf '# Leki\n- syntetyczny\n' > "$RP/medications.md"
  printf 'handout_sha256: %s\nverdict: PASS\nmust_fix_open: 0\nprofile_sha256: %s\nmedications_sha256: %s\n\n# Fact-check ledger\n- ok\n' \
    "$(sha_file "$RMD")" "$(sha_file "$RP/profile.md")" "$(sha_file "$RP/medications.md")" > "${RMD%.md}.factcheck.md"
  printf -- '- zmiana po weryfikacji\n' >> "$RP/medications.md"
  rb_err="$(run_fixture_renderer "$d" "$RMD" 2>&1 >/dev/null)"; rc=$?
  if [ "$rc" -eq 4 ] && [ ! -f "${RMD%.md}.pdf" ] && [ ! -f "${RMD%.md}.attest.json" ] \
     && printf '%s' "$rb_err" | grep -q 'changed since verification'; then
    echo "BITE  OK  (renderer gate refuses a seal whose medications list changed since the verify, rc=4, no artifacts)"; pass=$((pass+1))
  else
    echo "BITE  MISS (renderer record binding: expected rc=4 + the record message + no artifacts, got rc=$rc)"; fail=$((fail+1))
  fi
  rm -f "$RP/medications.md" "${RMD%.md}.factcheck.md"
  # control: with a fresh PASS sidecar the seal renders + attests, and the WHOLE fixture passes check.sh —
  # the renderer↔L15 schema-drift tripwire (a real attestation must verify)
  mk_pass_sidecar "$RMD"
  run_fixture_renderer "$d" "$RMD" >/dev/null 2>&1; rc=$?
  if [ "$rc" -eq 0 ] && [ -f "${RMD%.md}.pdf" ] && [ -f "${RMD%.md}.attest.json" ]; then
    assert_pass "$d" "renderer round-trip: a real sealed render satisfies L15 (schema sync)"
  else
    echo "BITE  MISS (renderer seal: expected rc=0 + pdf + attest, got rc=$rc)"; fail=$((fail+1)); rm -rf "$d"
  fi
  # Print-font coverage: WeasyPrint ignores unicode-range, so each print font is one merged latin + latin-ext
  # file, and a re-merge that drops the extended half prints Polish letters in a system font with build-QA
  # clean (B4 looks only above U+02BF, at the union of the four fonts). Test: a copy whose regular body font
  # lost ą fails, naming that file. Control: the shipped fonts pass.
  font_cov(){ "$RVENV" - "$1" <<'PY'
import os, re, sys
from fontTools.ttLib import TTFont
assets = sys.argv[1]
css = re.sub(r"(?s)/\*.*?\*/", "", open(os.path.join(assets, "handout.css"), encoding="utf-8").read())
files = [u for b in re.findall(r"@font-face\s*\{([^}]*)\}", css)
         for u in re.findall(r"url\(\s*['\"]?([^'\")]+\.woff2?)(?=['\")\s])", b)]
# printable ASCII, Latin-1 Supplement and Latin Extended-A, less the soft hyphen (never drawn) and the
# deprecated ŉ, which Spectral has never carried
need = (set(range(0x20, 0x7F)) | set(range(0xA0, 0x180))) - {0xAD, 0x149}
bad = [] if files else ["no font file in an @font-face of handout.css"]
for f in files:
    gap = sorted(need - set(TTFont(os.path.join(assets, f)).getBestCmap()))
    if gap:
        bad.append("%s lacks %d, first U+%04X" % (os.path.basename(f), len(gap), gap[0]))
print("; ".join(bad) or "%d font files" % len(files))
sys.exit(1 if bad else 0)
PY
  }
  fc="$(mktemp -d "${TMPDIR:-/tmp}/tabularium-fontcov.XXXXXX")"
  cp "$ROOT/_templates/handout-assets/handout.css" "$fc/"; cp -R "$ROOT/_templates/handout-assets/fonts" "$fc/fonts"
  "$RVENV" - "$fc/fonts/handout-sans-400.woff2" >/dev/null 2>&1 <<'PY'
import sys
from fontTools.ttLib import TTFont
t = TTFont(sys.argv[1])
for sub in t["cmap"].tables:
    sub.cmap.pop(0x105, None)
t.save(sys.argv[1])
PY
  fc_ok="$(font_cov "$ROOT/_templates/handout-assets" 2>&1 | tail -n 1)"; fc_ok_rc=$?
  fc_bad="$(font_cov "$fc" 2>&1 | tail -n 1)"; fc_bad_rc=$?
  if [ "$fc_ok_rc" -eq 0 ] && [ "$fc_bad_rc" -eq 1 ] && [ "$fc_bad" = "handout-sans-400.woff2 lacks 1, first U+0105" ]; then
    echo "BITE  OK  (print fonts each cover ASCII, Latin-1 and Latin Extended-A, $fc_ok; a body font without ą is caught)"; pass=$((pass+1))
  else
    echo "BITE  MISS (print-font coverage: shipped rc=$fc_ok_rc '$fc_ok'; body font without ą rc=$fc_bad_rc '$fc_bad')"; fail=$((fail+1))
  fi
  rm -rf "$fc"
else
  skip renderer "renderer round-trip and print-font coverage bites: .venv-render absent or weasyprint missing (rebuild via _templates/handout-assets/rebuild-render-env.sh) — L15's own bites above still ran"
fi

# Print font names (handout.css + the renderer's footer): a stack whose first family no @font-face declares
# renders in a substituted system font with build-QA clean — a name left stale by a font rename. Test: the
# footer and, separately, the body stack renamed to a stale family each fail, naming it. Control: the shipped
# pair passes. A monospace stack is exempt: no print mono font is bundled, code takes the system one by design.
if command -v python3 >/dev/null 2>&1; then
  font_names(){ python3 - "$1" "$2" <<'PY'
import re, sys
css = re.sub(r"(?s)/\*.*?\*/", "", open(sys.argv[1], encoding="utf-8").read())
src = re.sub(r"(?m)^\s*#.*$", "", open(sys.argv[2], encoding="utf-8").read())  # a comment quoting an old name
fam = lambda v: [f.strip().strip("'\"").lower() for f in v.replace("!important", "").split(",")]
faces = re.findall(r"@font-face\s*\{([^}]*)\}", css)
declared = {fam(v)[0] for b in faces for v in re.findall(r"font-family\s*:\s*([^;}]+)", b)}
rules = re.sub(r"@font-face\s*\{[^}]*\}", "", css) + "\n" + src
stacks = [fam(v) for v in re.findall(r"font-family\s*:\s*([^;}]+)", rules)]
for v in re.findall(r"\bfont\s*:\s*([^;}]+)", rules):  # shorthand: the family list follows the size
    m = re.search(r"[\d.]+(?:pt|px|r?em|%|mm|cm|in|ex|ch)(?:\s*/\s*\S+)?\s+(.+)", v)
    if m:
        stacks.append(fam(m.group(1)))
generic = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
           "ui-monospace", "ui-rounded", "math", "emoji", "fangsong", "inherit", "initial", "unset", "revert"}
bad = sorted({s[0] for s in stacks if s[-1] != "monospace"} - declared - generic)
bad += [] if declared and stacks else ["nothing parsed"]
print(", ".join(bad) or "%d stacks" % len(stacks))
sys.exit(1 if bad else 0)
PY
  }
  HA="$ROOT/_templates/handout-assets"
  fn="$(mktemp -d "${TMPDIR:-/tmp}/tabularium-fontnames.XXXXXX")"
  sed 's/"Handout Sans",sans-serif/"Source Sans 3",sans-serif/' "$HA/render_handout.py" > "$fn/footer.py"
  sed "s/font-family:'Handout Sans',/font-family:'Source Sans 3',/" "$HA/handout.css" > "$fn/body.css"
  fn_ok="$(font_names "$HA/handout.css" "$HA/render_handout.py" 2>&1 | tail -n 1)"; fn_ok_rc=$?
  fn_f="$(font_names "$HA/handout.css" "$fn/footer.py" 2>&1 | tail -n 1)"; fn_f_rc=$?
  fn_b="$(font_names "$fn/body.css" "$HA/render_handout.py" 2>&1 | tail -n 1)"; fn_b_rc=$?
  if [ "$fn_ok_rc" -eq 0 ] && [ "$fn_f_rc" -eq 1 ] && [ "$fn_f" = "source sans 3" ] \
     && [ "$fn_b_rc" -eq 1 ] && [ "$fn_b" = "source sans 3" ]; then
    echo "BITE  OK  (print font names: every stack starts with a family @font-face declares, $fn_ok; a stale footer or body name is caught)"; pass=$((pass+1))
  else
    echo "BITE  MISS (print font names: shipped rc=$fn_ok_rc '$fn_ok'; stale footer rc=$fn_f_rc '$fn_f'; stale body rc=$fn_b_rc '$fn_b')"; fail=$((fail+1))
  fi
  rm -rf "$fn"
else
  skip font-names "python3 absent — print font-name check not run"
fi

# make_verify_bundle.sh (ADR-0034 point 6) — the assembler is REPO-BOUND, so each case runs a COPY of
# the script inside its own synthetic fixture repo. Test: a wrong-person entry is refused with the PERSON-SCOPE
# fault named (the person mix-up). Control: the happy path — the stdout digest matches the file and the handout
# body is omitted. Pure bash + python3.
MVB="$ROOT/_templates/handout-assets/make_verify_bundle.sh"
if [ -f "$MVB" ]; then
  bd="$(mktemp -d "${TMPDIR:-/tmp}/tabularium-mvb.XXXXXX")"
  mkdir -p "$bd/A/_templates/handout-assets" "$bd/A/patients/szbun/med/handouts/patient/2026-07-26-t" \
           "$bd/A/patients/szbun/med/sources" "$bd/A/patients/szob2/med/sources" "$bd/A/reference-library"
  cp "$MVB" "$bd/A/_templates/handout-assets/make_verify_bundle.sh"
  printf '# CLAUDE.md (synthetic fixture)\n' > "$bd/A/CLAUDE.md"
  printf '# Karta\n\nTresc probna.\n' > "$bd/A/patients/szbun/med/handouts/patient/2026-07-26-t/2026-07-26__handout-patient__t.md"
  printf '# Profil\n' > "$bd/A/patients/szbun/profile.md"; printf '# Leki\n' > "$bd/A/patients/szbun/medications.md"
  printf 'wynik badania\n' > "$bd/A/patients/szbun/med/sources/lab.ocr.md"
  printf 'obcy\n' > "$bd/A/patients/szob2/med/sources/x.md"
  SA="$bd/A/_templates/handout-assets/make_verify_bundle.sh"
  bh="$bd/A/patients/szbun/med/handouts/patient/2026-07-26-t/2026-07-26__handout-patient__t.md"
  err="$(bash "$SA" --out "$bd/oa.md" "$bh" "$bd/A/patients/szob2/med/sources/x.md" 2>&1 >/dev/null)"; rc=$?
  if [ "$rc" -eq 2 ] && printf '%s' "$err" | grep -q 'PERSON-SCOPE'; then
    echo "BITE  OK  (verify-bundle: wrong-person entry rc=2, PERSON-SCOPE named)"; pass=$((pass+1))
  else
    echo "BITE  MISS (verify-bundle: wrong-person entry — rc=$rc or wrong refusal)"; fail=$((fail+1))
  fi
  out="$(bash "$SA" --out "$bd/oj.md" "$bh" "$bd/A/patients/szbun/med/sources/lab.ocr.md" 2>/dev/null)"; rc=$?
  bs="$(printf '%s\n' "$out" | sed -n 's/^bundle_sha256=//p')"
  fs="$(sha_file "$bd/oj.md" 2>/dev/null)"
  bodyhits="$(grep -c 'Tresc probna' "$bd/oj.md" 2>/dev/null || true)"
  if [ "$rc" -eq 0 ] && [ -n "$bs" ] && [ "$bs" = "$fs" ] && [ "$bodyhits" -eq 0 ]; then
    echo "BITE  OK  (verify-bundle: happy path — digest matches file, handout body omitted)"; pass=$((pass+1))
  else
    echo "BITE  MISS (verify-bundle: happy path rc=$rc digest-match=$([ "$bs" = "$fs" ] && echo yes || echo no) body-hits=$bodyhits)"; fail=$((fail+1))
  fi
  # extra: a relied-on file whose NAME carries a newline is refused AS a control
  # character. The file exists and is text, so no later refusal can stand in for that one; unrefused, the name
  # split into two manifest entries and the repository's own CLAUDE.md was bundled from outside the evidence lane.
  bnl="$bd/A/patients/szbun/med/sources/lab.ocr.md
CLAUDE.md"
  printf 'synthetic text under a newline-bearing name\n' > "$bnl"
  err="$(bash "$SA" --out "$bd/on.md" "$bh" "$bnl" 2>&1 >/dev/null)"; rc=$?
  if [ "$rc" -eq 2 ] && grep -q 'control character in path' <<<"$err" && [ ! -e "$bd/on.md" ]; then
    echo "BITE  OK  (verify-bundle: a relied-on name carrying a newline is refused as a control character)"; pass=$((pass+1))
  else
    echo "BITE  MISS (verify-bundle: newline-bearing name — rc=$rc, bundle written=$([ -e "$bd/on.md" ] && echo yes || echo no), refusal: ${err:-none})"; fail=$((fail+1))
  fi
  rm -rf "$bd"
else
  echo "BITE  MISS (make_verify_bundle.sh absent — ADR-0034 point 6 artifact missing)"; fail=$((fail+1))
fi

# --- static lints and the suite's own wiring ---------------------------------------------------------

# PORTABILITY LINT (ADR-0020/0021) — the guard scripts must run on the macOS host (bash 3.2 / BSD userland),
# not only the Linux sandbox. A static scan, so Linux CI catches a host-only regression (a bash-4 array
# builtin, GNU `find` format flag, `head -n -N`) that the runtime cases pass on Linux and never reveal.
# Targets are AUTO-DISCOVERED (every checks/*.sh + checks/git-hooks/* + tools/private-mode/*.sh); selftest.sh
# is excluded — it must name these tokens.
# PORT_PATS is the lint's WHOLE list — known traps, not a parser: a construct outside it is not caught. Constructs a
# guard legitimately uses in one arm of a BSD/GNU fallback (`stat -c`, `date -d`) are deliberately absent. Every
# pattern has a sample at the same index of PORT_SAMPLES (one line per alternative) that it must flag; the lint's
# negative control below plants each one, so a pattern added without a sample, or one that stops matching, MISSes.
PORT_PATS=(
  'mapfile|readarray'                                                     # array-reading builtins (bash 4.0)
  '(declare|local|typeset)[[:space:]]+-[[:alpha:]]*[Aglnu]'               # associative, global, nameref, case attributes (4.0-4.3)
  '[$][{][[:alnum:]_]+([[][^]]*[]])?[,^]'                                 # case-changing expansion (4.0)
  '[$][{][[:alnum:]_]+([[][^]]*[]])?@[[:alpha:]][}]'                      # transforming expansion (4.4)
  '[$][{][[:alnum:]_]+[[]-[0-9]'                                          # negative array subscript (4.3)
  '[$][{][[:alnum:]_]+:[0-9]+:-[0-9]'                                     # negative substring length (4.2)
  '(^|[[:space:];&|(])coproc([[:space:]]|$)'                              # coproc (4.0)
  '[|]&'                                                                  # |& pipe (4.0)
  '&>>'                                                                   # &>> append (4.0)
  ';;&|;&([[:space:]]|$)'                                                 # case fall-through (4.0)
  'wait[[:space:]]+-n'                                                    # wait -n (4.3)
  '([[][[]?|test)[[:space:]]+-v[[:space:]]'                               # -v set-variable test (4.2)
  'shopt[[:space:]]+-s[[:space:]]+(globstar|lastpipe|inherit_errexit)'    # bash 4 shell options
  'EPOCHSECONDS|EPOCHREALTIME|BASHPID'                                    # bash 4/5 variables
  '%[(][^)]*[)]T'                                                         # printf %(fmt)T (4.2)
  '[{][[:alnum:]]+[.][.][[:alnum:]]+[.][.]'                               # brace-expansion step (4.0)
  '-printf|-fprint'                                                       # GNU find output actions
  'find([[:space:]].*)?[[:space:]]-(regextype|readable|writable|executable|xtype|files0-from)([[:space:]]|$)'  # GNU find tests
  'head[[:space:]]+(-[[:alpha:]]+[[:space:]]+)*-[nc][[:space:]]*-[0-9]'   # GNU head negative count
  'sed([[:space:]]+-[[:alnum:]]+)*[[:space:]]+-[[:alpha:]]*i([[:space:]]|$)'  # sed -i without an attached suffix (GNU and BSD disagree)
  'grep([[:space:]]+-[[:alnum:]]+)*[[:space:]]+-[[:alpha:]]*P'            # grep -P (BSD grep has no PCRE)
)
PORT_SAMPLES=(
  $'mapfile -t lines < f\nreadarray -t lines < f'
  $'declare -A seen\nlocal -n ref=x\ndeclare -g G=1\ntypeset -l low\ndeclare -u up'
  $'y=${x,,}\ny=${x^^}\ny=${arr[1],}'
  'q=${x@Q}'
  'last=${arr[-1]}'
  't=${x:0:-1}'
  'coproc cat'
  'cmd |& tee log'
  'cmd &>> log'
  $'  a) x ;;&\n  b) y ;&'
  'wait -n'
  $'[[ -v name ]]\n[ -v name ]\ntest -v name'
  $'shopt -s globstar\nshopt -s lastpipe\nshopt -s inherit_errexit'
  $'t=$EPOCHSECONDS\nt=$EPOCHREALTIME\np=$BASHPID'
  "printf '%(%F)T' -1"
  'for i in {1..9..2}; do :; done'
  $'find . -printf \'%p\'\nfind . -fprint out'
  $'find . -regextype posix-extended -regex x\nfind . -readable\nfind . -writable\nfind . -executable\nfind . -xtype l\nfind -files0-from list'
  $'head -n -1 f\nhead -c -2 f\nhead -n-1 f'
  $'sed -i \'s/a/b/\' f\nsed -i \'\' \'s/a/b/\' f\nsed -Ei \'s/a/b/\' f\nsed -n -i \'s/a/b/p\' f'
  $'grep -P \'x\' f\ngrep -oP x f'
)
# the portable twin: the nearest bash-3.2/BSD-safe form of each sample, which must scan clean (precision)
PORT_TWIN=$'declare -a arr; local -r ro=1; typeset -i n=0; declare -x E\ny=${x:-a,b}; z=${#arr[@]}; w=${arr[@]}; u=${x:1:2}
head -n 5 f; head -c 10 f; tail -n +2 f\nsed -i.bak \'s/a/b/\' f; sed -n \'s/i/x/p\' f; sed -E \'s/a/b/\' f
grep -E \'a\' f; grep -vF x f; grep -i y f\nfind . -type f -name \'*.sh\' -print\ncase "$x" in a) : ;; esac
wait "$pid"; [ -n "$x" ] && test -z "$y"; shopt -s nullglob\nfor i in 1 2 3; do :; done; printf \'%s\\n\' "$(date +%s)"
cmd 2>&1 | tee log; cmd >> log 2>&1'
# port_scan file… — prints each hit or scan error; rc 0 clean, 1 a listed construct found, 2 a file NOT scanned
# (grep rc ≥ 2: unreadable, vanished). A grep error was once read as "portable".
port_scan(){ local f grc worst=0 hits pe=()
  [ "${#PORT_PATS[@]}" -gt 0 ] || return 2
  for f in "${PORT_PATS[@]}"; do pe+=(-e "$f"); done
  for f in "$@"; do
    hits="$(grep -nE "${pe[@]}" -- "$f" 2>/dev/null)"; grc=$?
    if [ "$grc" -eq 0 ]; then
      echo "PORT  FAIL ($(basename "$f")): bash-4/GNU-only construct — won't run on the macOS host:"
      printf '%s\n' "$hits" | sed 's/^/      /'; [ "$worst" -ge 1 ] || worst=1
    elif [ "$grc" -ge 2 ]; then
      echo "PORT  FAIL ($(basename "$f")): grep rc=$grc — the file was NOT scanned, so it is not shown portable"; worst=2
    fi
  done
  return "$worst"; }
PORT_TARGETS=()
for f in "$ROOT"/checks/*.sh "$ROOT"/checks/git-hooks/* "$ROOT"/tools/private-mode/*.sh; do
  case "$f" in */selftest.sh) continue;; esac
  [ -f "$f" ] && PORT_TARGETS+=("$f")
done
if [ "${#PORT_TARGETS[@]}" -eq 0 ]; then
  echo "PORT  FAIL (zero guard scripts discovered — the lint examined nothing)"; fail=$((fail+1))
elif port_scan "${PORT_TARGETS[@]}"; then
  echo "PORT  OK  (${#PORT_TARGETS[@]} guard scripts free of the ${#PORT_PATS[@]} listed bash-4/GNU-only constructs)"; pass=$((pass+1))
else fail=$((fail+1)); fi
# the lint's negative control: each sample line, alone in a planted file, is matched by ITS OWN
# pattern and flagged by port_scan; the portable twin scans clean; a target that cannot be read fails closed.
port_fx="$(mktemp -d)"; port_bad=""; port_n=0; port_i=0
if [ "${#PORT_PATS[@]}" -ne "${#PORT_SAMPLES[@]}" ]; then
  port_bad=" ${#PORT_PATS[@]}-patterns-but-${#PORT_SAMPLES[@]}-samples"
else
  while [ "$port_i" -lt "${#PORT_PATS[@]}" ]; do
    while IFS= read -r port_s; do
      [ -n "$port_s" ] || continue; port_n=$((port_n+1))
      printf '%s\n' "$port_s" > "$port_fx/sample.sh"
      grep -qE -e "${PORT_PATS[$port_i]}" -- "$port_fx/sample.sh" || port_bad="$port_bad pattern-$port_i-misses:[$port_s]"
      port_scan "$port_fx/sample.sh" >/dev/null; [ "$?" -eq 1 ] || port_bad="$port_bad not-flagged:[$port_s]"
    done <<EOF
${PORT_SAMPLES[$port_i]}
EOF
    port_i=$((port_i+1))
  done
fi
printf '%s\n' "$PORT_TWIN" > "$port_fx/twin.sh"
port_scan "$port_fx/twin.sh" >/dev/null; [ "$?" -eq 0 ] || port_bad="$port_bad portable-twin-flagged"
port_scan "$port_fx/vanished.sh" >/dev/null; [ "$?" -eq 2 ] || port_bad="$port_bad unreadable-target-not-failed-closed"
rm -rf "$port_fx"
if [ -z "$port_bad" ] && [ "$port_n" -ge "${#PORT_PATS[@]}" ]; then
  echo "BITE  OK  (portability lint: $port_n planted samples each caught by their own pattern, the portable twin clean, an unreadable target failed closed)"; pass=$((pass+1))
else
  echo "BITE  MISS (portability lint:$port_bad)"; fail=$((fail+1))
fi

# ENTRYPOINT-MODE LINT (a script shipped without its executable bit, twice). `checks/README.md`'s routine block documents scripts the
# operator runs DIRECTLY (a line starting at column 0 with `checks/<name>.sh`). One tracked at mode 100644
# fails "permission denied" on every clone, exactly when someone reaches for the documented recovery. The
# INDEX mode is what a clone materialises; the WORKING bit is what this machine executes. Targets are
# AUTO-DISCOVERED from the README. Fail-closed: an unreadable README, a grep error or ZERO discovered
# entrypoints is a FAIL — a lint that enumerated nothing must never print OK.
EPX_README="$ROOT/checks/README.md"
epx_bad=""; epx_n=0; epx_raw=""
if [ ! -f "$EPX_README" ]; then
  epx_bad=" checks/README.md-missing(entrypoints-unenumerable)"
else
  # rc 0 = matched, 1 = none at all, >=2 = grep error. Never `|| true` this: rc>=2 means UNSCANNED.
  epx_raw="$(grep -n '^checks/[A-Za-z0-9_.-]*\.sh' "$EPX_README")"; epx_rc=$?
  if   [ "$epx_rc" -ge 2 ]; then epx_bad=" grep-error-rc$epx_rc(entrypoints-UNSCANNED)"
  elif [ "$epx_rc" -eq 1 ]; then epx_bad=" zero-documented-entrypoints(routine-block-drifted)"
  fi
fi
epx_noidx=0
if [ -z "$epx_bad" ]; then
  # strip grep's `NN:` prefix, keep the path up to its first non-path character, dedupe (check.sh is documented twice)
  epx_paths="$(printf '%s\n' "$epx_raw" | sed -e 's/^[0-9][0-9]*://' -e 's/[^A-Za-z0-9_./-].*$//' | sort -u)"
  while IFS= read -r epx_rel; do
    [ -n "$epx_rel" ] || continue
    epx_n=$((epx_n+1))
    if [ ! -f "$ROOT/$epx_rel" ]; then epx_bad="$epx_bad $epx_rel(documented-but-absent)"; continue; fi
    [ -x "$ROOT/$epx_rel" ] || epx_bad="$epx_bad $epx_rel(working-file-not-executable)"
    if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
      # captured, THEN parsed: piped into awk, a failed `git ls-files` (an unreadable or corrupt index) printed
      # nothing, which read as "untracked" and skipped the check
      epx_ls="$(git -C "$ROOT" ls-files -s -- "$epx_rel" 2>/dev/null)"; epx_lrc=$?
      if [ "$epx_lrc" -ne 0 ]; then epx_bad="$epx_bad $epx_rel(index-unreadable:git-ls-files-rc$epx_lrc)"; continue; fi
      epx_mode="${epx_ls%% *}"
      case "$epx_mode" in
        "")     ;;   # untracked (git answered, and listed nothing)
        100755) ;;
        *)      epx_bad="$epx_bad $epx_rel(index-mode-$epx_mode)";;
      esac
    else
      epx_noidx=1
    fi
  done <<EOF
$epx_paths
EOF
fi
if [ -z "$epx_bad" ] && [ "$epx_n" -gt 0 ]; then
  echo "EPX   OK  ($epx_n documented direct entrypoints executable in $([ "$epx_noidx" -eq 1 ] && echo 'the working tree' || echo 'index + working tree'))"; pass=$((pass+1))
else
  echo "EPX   FAIL (documented entrypoint not executable):$epx_bad"; fail=$((fail+1))
fi
[ "$epx_noidx" -eq 0 ] || skip epx-index "git absent or not a git checkout — the entrypoints' INDEX mode (what a clone gets) was NOT checked"

# No guard may self-skip SILENTLY (L9/L12 once skipped silently in every worktree). Static, so it costs nothing and
# cannot self-skip.
# Every self-skip in check.sh must announce itself `SKIP (LOUD)`; finding ZERO self-skips reds too (the
# extraction stopped extracting). `grep -c` prints 0 AND exits 1 on no match, so the value is sanitised.
wire_bad=""
_skips="$(grep -c 'SKIP (LOUD)' "$ROOT/checks/check.sh" 2>/dev/null | head -1)"
case "$_skips" in ''|*[!0-9]*) _skips=0 ;; esac
# the `|| true` on the second leg is safe only because a scan error zeroes $_skips and the count leg fires
_quiet="$(grep -n 'SKIP' "$ROOT/checks/check.sh" 2>/dev/null | grep -v 'SKIP (LOUD)' \
          | grep -v 'NOT verified — see the SKIP above' || true)"
# the floor tracks the real count: a blinded-extraction detector, not a census
[ "${_skips:-0}" -ge 1 ] || wire_bad="$wire_bad only-${_skips:-0}-loud-skips-found(extraction-blinded)"
[ -z "$_quiet" ]         || wire_bad="$wire_bad silent-skip-line(s):$(printf '%s' "$_quiet" | cut -d: -f1 | tr '\n' ',')"
if [ -z "$wire_bad" ]; then
  echo "BITE  OK  (every self-skip in check.sh announces itself LOUDLY — $_skips of them, none silent)"; pass=$((pass+1))
else
  echo "BITE  MISS (silent-skip wiring:$wire_bad)"; fail=$((fail+1))
fi
# This suite's self-skips: a skip line printed by a bare `echo` would show but never be counted, so
# no line outside `skip` may echo one, and the call sites must be found (a floor, so an extraction that finds
# nothing cannot pass). The comparator: an id outside the expected set is reported, the set itself is not.
st_bad=""
st_sites="$(grep -cE '(^|[;&|{][[:space:]]*|^[[:space:]]+)skip [a-z0-9-]+ "' "$ROOT/checks/selftest.sh" 2>/dev/null)"
case "$st_sites" in ''|*[!0-9]*) st_sites=0 ;; esac
[ "$st_sites" -ge 1 ] || st_bad="$st_bad only-$st_sites-skip-call-sites-found(extraction-blinded)"
st_bare="$(grep -nE 'echo[[:space:]]+"([A-Z]+[[:space:]]+)?SKIP[[:space:]]' "$ROOT/checks/selftest.sh" 2>/dev/null \
           | grep -vF 'skip(){ echo "SKIP  [$1]' | grep -vF 'echo "SKIP  UNEXPECTED' || true)"
[ -z "$st_bare" ] || st_bad="$st_bad skip-echoed-outside-skip()-at-line(s):$(printf '%s' "$st_bare" | cut -d: -f1 | tr '\n' ',')"
[ "$(skip_unexpected " renderer hooks board-L20" "renderer")" = " hooks board-L20" ] || st_bad="$st_bad comparator-missed-an-unexpected-id"
[ -z "$(skip_unexpected " renderer" "renderer")" ] || st_bad="$st_bad comparator-flagged-the-expected-set"
[ -z "$(skip_unexpected "" "")" ] || st_bad="$st_bad comparator-flagged-no-skips"
if [ -z "$st_bad" ]; then
  echo "BITE  OK  (this suite's $st_sites self-skip sites all print through skip; an id outside the expected set is reported, the set itself is not)"; pass=$((pass+1))
else
  echo "BITE  MISS (self-skip accounting:$st_bad)"; fail=$((fail+1))
fi
# The tooling-SHAPED record list is written TWICE — `L20_SHAPED` in check.sh and `SHAPED` in the pre-push hook —
# so a path added to one and not the other leaves a machine instance-green but push-blocked, or the reverse. A
# value that will not parse out of either file is a MISS, so the assert cannot pass by extracting nothing.
_sh_c="$(sed -n 's/^L20_SHAPED="\(.*\)"$/\1/p' "$ROOT/checks/check.sh")"
_sh_h="$(sed -n 's/^SHAPED="\(.*\)"$/\1/p' "$ROOT/checks/git-hooks/pre-push")"
if [ -n "$_sh_c" ] && [ "$_sh_c" = "$_sh_h" ]; then
  echo "BITE  OK  (tooling-SHAPED record list identical in check.sh L20 and the pre-push hook)"; pass=$((pass+1))
else
  echo "BITE  MISS (SHAPED list drift: check.sh='${_sh_c:-UNPARSED}' pre-push='${_sh_h:-UNPARSED}')"; fail=$((fail+1))
fi
# registry_path() / private_id_path() live once, in checks/config-paths.sh (2026-11-01). Each consumer —
# snapshot.sh (banks the registry), relay-scan.sh (CARE's relay gate), install-instance.sh — copied without
# it refuses, naming the file, before writing anything; with it beside them that refusal is gone (the twin).
cp_bad=""
for cp_f in snapshot.sh relay-scan.sh install-instance.sh reveal-private-id.sh; do
  for cp_lib in no yes; do
    cp_d="$(mktemp -d)"; mkdir -p "$cp_d/checks"; : > "$cp_d/CLAUDE.md"; valid_profile "$cp_d/patients/sztcfg/profile.md"
    cp "$ROOT/checks/$cp_f" "$cp_d/checks/$cp_f"
    [ "$cp_lib" = yes ] && cp "$ROOT/checks/config-paths.sh" "$cp_d/checks/config-paths.sh"
    case "$cp_f" in
      snapshot.sh)         cp_out="$(bash "$cp_d/checks/snapshot.sh" "$cp_d" 2>&1)"; cp_rc=$? ;;
      relay-scan.sh)       cp_out="$(bash "$cp_d/checks/relay-scan.sh" "$cp_d/CLAUDE.md" 2>&1)"; cp_rc=$? ;;
      install-instance.sh) cp_out="$(cd "$cp_d" && bash "$cp_d/checks/install-instance.sh" dev 2>&1)"; cp_rc=$? ;;
      reveal-private-id.sh) cp_out="$(bash "$cp_d/checks/reveal-private-id.sh" 2>&1)"; cp_rc=$? ;;
    esac
    if [ "$cp_lib" = no ]; then
      { [ "$cp_rc" -ne 0 ] && grep -qF 'config-paths.sh is missing or unreadable' <<<"$cp_out" && [ ! -e "$cp_d/.snapshots" ]; } \
        || cp_bad="$cp_bad $cp_f(no refusal without it: rc=$cp_rc)"
    else
      grep -qF 'config-paths.sh is missing or unreadable' <<<"$cp_out" && cp_bad="$cp_bad $cp_f(refused with it present)"
    fi
    rm -rf "$cp_d"
  done
done
if [ -z "$cp_bad" ]; then
  echo "BITE  OK  (snapshot, relay-scan, install-instance and reveal-private-id refuse without checks/config-paths.sh, and only then)"; pass=$((pass+1))
else
  echo "BITE  MISS (shared path helpers:$cp_bad)"; fail=$((fail+1))
fi
# reveal-private-id.sh (a number page's setup, tools/private-mode/numbers/) hands the identifier file to `open -R` and prints fixed
# words only: never the path the pointer names, never the file's content. No pointer: Finder is not asked.
rp_d="$(mktemp -d)"; rp_x="$(mktemp -d)"; mkdir -p "$rp_d/checks" "$rp_d/bin"
cp "$ROOT/checks/reveal-private-id.sh" "$ROOT/checks/config-paths.sh" "$rp_d/checks/"
printf '#!/bin/sh\nprintf "%%s\\n" "$@" > "%s/open.args"\n' "$rp_d" > "$rp_d/bin/open"; chmod +x "$rp_d/bin/open"
rp_out0="$(PATH="$rp_d/bin:$PATH" bash "$rp_d/checks/reveal-private-id.sh" 2>&1)"; rp_rc0=$?
rp_called0=no; [ -e "$rp_d/open.args" ] && rp_called0=yes
printf "PII_PRIVATE_MODE_ID='zqx9zz'\n" > "$rp_x/private-mode-id.sh"; chmod 600 "$rp_x/private-mode-id.sh"
printf '%s\n' "$rp_x/private-mode-id.sh" > "$rp_d/checks/PRIVATE-MODE-ID"
rp_out="$(PATH="$rp_d/bin:$PATH" bash "$rp_d/checks/reveal-private-id.sh" 2>&1)"; rp_rc=$?
rp_args="$(cat "$rp_d/open.args" 2>/dev/null)"
if [ "$rp_rc0" -eq 1 ] && [ "$rp_called0" = no ] && [ "$rp_rc" -eq 0 ] \
   && [ "$rp_args" = "$(printf -- '-R\n%s' "$rp_x/private-mode-id.sh")" ] \
   && ! grep -qF "$rp_x" <<<"$rp_out$rp_out0" && ! grep -qF zqx9zz <<<"$rp_out$rp_out0"; then
  echo "BITE  OK  (reveal-private-id: shows the identifier file in Finder, prints neither its path nor its content; no pointer, no Finder)"; pass=$((pass+1))
else
  echo "BITE  MISS (reveal-private-id: rc0=$rp_rc0 called0=$rp_called0 rc=$rp_rc args=$(printf '%s' "$rp_args" | tr '\n' ' '))"; fail=$((fail+1))
fi
rm -rf "$rp_d" "$rp_x"

# Python suites: every tools/*/ and evals/*/ test_*.py, each in its own process so one module's patches never
# reach another. The deep verifier logic for L13 and L15 lives there. A module that runs no test, or skips all of
# them, fails: a runner unittest cannot see once read as green. A passing module's own SKIP lines still print, so
# a check it could not run stays visible; -q keeps unittest's progress dots from gluing onto a notice. Colour stays
# off: coloured unittest output hides the skip count from the pattern. CI runs this suite and keeps no list of its own.
# The modules run at the same time, each its own process writing to its own file, and are then judged one by one
# in glob order, so the report reads as a serial run's would; the wall time is the slowest module's, not the sum.
# A background job starts with Ctrl-C ignored, which a hung module would keep: each module's Python takes Ctrl-C
# back itself (`python3 -m unittest` otherwise, with its import path pinned to the launch folder, as -m pins it),
# so a Ctrl-C still stops every module and runs its cleanup.
py_unittest='import os, signal, sys, unittest; sys.path[0] = os.getcwd(); signal.signal(signal.SIGINT, signal.default_int_handler); sys.argv[0] = "python3 -m unittest"; unittest.main(module=None)'
# py_suites root -> one SUITE line per module, py_ok and py_bad counted.
py_suites(){ local root="$1" s d mod ran skipped out rc n=0 i pids="" pd; py_ok=0; py_bad=0
  pd="$(mktemp -d)"
  for s in "$root"/tools/*/test_*.py "$root"/evals/*/test_*.py; do
    [ -e "$s" ] || continue
    n=$((n+1)); d="$(dirname "$s")"
    mod="$(basename "$(dirname "$d")").$(basename "$d").$(basename "$s" .py)"
    printf '%s\n' "$mod" > "$pd/$n.mod"
    ( cd "$root" && PYTHON_COLORS=0 python3 -c "$py_unittest" -q "$mod" > "$pd/$n.out" 2>&1; echo $? > "$pd/$n.rc" ) &
    pids="$pids $!"
  done
  for i in $pids; do wait "$i"; done
  i=0
  while [ "$i" -lt "$n" ]; do
    i=$((i+1)); mod="$(cat "$pd/$i.mod")"; out="$(cat "$pd/$i.out")"; rc="$(cat "$pd/$i.rc" 2>/dev/null)"; rc="${rc:-1}"
    ran="$(sed -n 's/^Ran \([0-9]*\) tests\{0,1\} in .*/\1/p' <<<"$out" | tail -1)"
    skipped="$(sed -n 's/^OK (.*skipped=\([0-9]*\).*/\1/p' <<<"$out" | tail -1)"
    if [ "$rc" -eq 0 ] && [ "${ran:-0}" -gt "${skipped:-0}" ]; then
      echo "SUITE OK  ($mod: $ran tests${skipped:+, $skipped skipped})"; py_ok=$((py_ok+1))
      sed -n 's/^SKIP[[:space:]]/      &/p' <<<"$out"
    else
      echo "SUITE FAIL ($mod: rc=$rc, ${ran:-0} tests ran, ${skipped:-0} skipped)"; sed 's/^/      /' <<<"$out"; py_bad=$((py_bad+1))
    fi
  done
  rm -rf "$pd"
  if [ "$n" -eq 0 ]; then echo "SUITE FAIL (no tools/*/ or evals/*/ test_*.py under $root)"; py_bad=$((py_bad+1)); fi
}
# The runner finds suites by glob, so a deleted, renamed or moved test file once meant one suite fewer and every
# line green. checks/PYTHON-SUITES names the suites that ship, checks/PYTHON-SUITES-DEV the development tree's own
# (absent from an export, whose folders are absent too): a listed suite not found is red, and so is a found one
# listed in neither, so the lists cannot fall behind. Plain bash, so it runs where python3 does not.
# py_suite_list root -> SUITE lines, psl_bad counted.
py_suite_list(){ local root="$1" listed found m; psl_bad=0
  if [ ! -f "$root/checks/PYTHON-SUITES" ]; then
    echo "SUITE FAIL (checks/PYTHON-SUITES is missing: restore it — it names the Python suites this run must find)"; psl_bad=1; return
  fi
  listed="$(cat "$root/checks/PYTHON-SUITES" "$root/checks/PYTHON-SUITES-DEV" 2>/dev/null \
    | sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e '/^$/d' | LC_ALL=C sort -u)"
  found="$(cd "$root" && for m in tools/*/test_*.py evals/*/test_*.py; do [ -e "$m" ] && printf '%s\n' "$m"; done | LC_ALL=C sort -u)"
  for m in $(LC_ALL=C comm -23 <(printf '%s\n' "$listed") <(printf '%s\n' "$found")); do
    echo "SUITE FAIL (listed but not found: $m — restore it, or drop its line from the suite list in the same change)"; psl_bad=$((psl_bad+1))
  done
  for m in $(LC_ALL=C comm -13 <(printf '%s\n' "$listed") <(printf '%s\n' "$found")); do
    echo "SUITE FAIL (found but not listed: $m — add it to checks/PYTHON-SUITES, or to checks/PYTHON-SUITES-DEV if its folder does not ship)"; psl_bad=$((psl_bad+1))
  done
  [ "$psl_bad" -eq 0 ] && echo "SUITE OK  (every listed Python suite found, none unlisted: $(printf '%s\n' "$found" | sed '/^$/d' | wc -l | tr -d ' ') suites)"
  return 0
}
# … its bite, in a scratch tree with lists of its own (so it bites the same in a public copy, which has no DEV list)
# and an empty stand-in for each listed suite: the tree is green; one expected suite removed from either list's set,
# one unlisted added, or the list itself gone turns it red, naming the file; an export-shaped tree (no DEV list, no
# DEV-only folder) stays green.
psl_d="$(mktemp -d)"; mkdir -p "$psl_d/checks"
printf '# synthetic shipped list\ntools/shipped/test_one.py\n\nevals/harness/test_two.py  # trailing note\n' > "$psl_d/checks/PYTHON-SUITES"
printf '# synthetic dev list\ntools/devonly/test_three.py\n' > "$psl_d/checks/PYTHON-SUITES-DEV"
for psl_f in tools/shipped/test_one.py evals/harness/test_two.py tools/devonly/test_three.py; do
  mkdir -p "$psl_d/$(dirname "$psl_f")"; : > "$psl_d/$psl_f"
done
psl_bad_cases=""
py_suite_list "$psl_d" >/dev/null; [ "$psl_bad" -eq 0 ] || psl_bad_cases="$psl_bad_cases intact-tree-red"
for psl_gone in evals/harness/test_two.py tools/devonly/test_three.py; do
  mv "$psl_d/$psl_gone" "$psl_d/$psl_gone.moved"
  psl_out="$(py_suite_list "$psl_d"; echo "psl_bad=$psl_bad")"
  { grep -qxF "SUITE FAIL (listed but not found: $psl_gone — restore it, or drop its line from the suite list in the same change)" <<<"$psl_out" \
    && grep -qx 'psl_bad=1' <<<"$psl_out"; } || psl_bad_cases="$psl_bad_cases removed:$psl_gone"
  mv "$psl_d/$psl_gone.moved" "$psl_d/$psl_gone"
done
mkdir -p "$psl_d/tools/newtool"; : > "$psl_d/tools/newtool/test_new.py"
psl_out="$(py_suite_list "$psl_d"; echo "psl_bad=$psl_bad")"
{ grep -qF 'SUITE FAIL (found but not listed: tools/newtool/test_new.py' <<<"$psl_out" && grep -qx 'psl_bad=1' <<<"$psl_out"; } \
  || psl_bad_cases="$psl_bad_cases unlisted-not-red"
rm -rf "$psl_d/tools/newtool"
mv "$psl_d/checks/PYTHON-SUITES" "$psl_d/checks/PYTHON-SUITES.gone"
psl_out="$(py_suite_list "$psl_d"; echo "psl_bad=$psl_bad")"
grep -qF 'SUITE FAIL (checks/PYTHON-SUITES is missing' <<<"$psl_out" || psl_bad_cases="$psl_bad_cases no-list-not-red"
mv "$psl_d/checks/PYTHON-SUITES.gone" "$psl_d/checks/PYTHON-SUITES"
rm -rf "$psl_d/checks/PYTHON-SUITES-DEV" "$psl_d/tools/devonly"
py_suite_list "$psl_d" >/dev/null; [ "$psl_bad" -eq 0 ] || psl_bad_cases="$psl_bad_cases export-shape-red"
rm -rf "$psl_d"
if [ -z "$psl_bad_cases" ]; then
  echo "BITE  OK  (expected Python suites: a suite removed from either list's set, an unlisted one or a missing list turns the runner red; an intact or export-shaped tree stays green)"; pass=$((pass+1))
else
  echo "BITE  MISS (expected Python suites:$psl_bad_cases)"; fail=$((fail+1))
fi
py_suite_list "$ROOT"; [ "$psl_bad" -eq 0 ] && pass=$((pass+1)) || fail=$((fail+psl_bad))
if command -v python3 >/dev/null 2>&1; then
  # … its bite, on a synthetic tree: one good module passes, its SKIP notices shown (one flushed right after a passing
  # test's progress dot) and its other output not, while each kind of bad one fails, naming the test that failed
  # however much the test printed; a tree with no suites fails too. The same tree runs again with colours forced on,
  # which can only bite on a Python that colours (3.14).
  py_d="$(mktemp -d)"; mkdir -p "$py_d/tools/good" "$py_d/tools/empty" "$py_d/tools/skips" "$py_d/tools/broken" "$py_d/evals/red"
  printf 'import unittest\nclass T(unittest.TestCase):\n    def test_a_passes(self): pass\n    def test_b_flushes(self): print("SKIP  D1 (LOUD): flushed", flush=True)\n    def test_ok(self): print("chatter"); print("SKIPPED_DUPLICATE is expected"); print("SKIP  D0 (LOUD): notice")\n    def test_skip(self): self.skipTest("x")\n' > "$py_d/tools/good/test_good.py"
  printf 'print("a runner of its own")\n' > "$py_d/tools/empty/test_empty.py"
  printf 'import unittest\nclass T(unittest.TestCase):\n    def test_skip(self): self.skipTest("x")\n' > "$py_d/tools/skips/test_skips.py"
  printf 'import no_such_module_here\n' > "$py_d/tools/broken/test_broken.py"
  printf 'import unittest\nclass T(unittest.TestCase):\n    def test_named_in_the_report(self):\n        for i in range(99): print(i)\n        self.fail("x")\n' > "$py_d/evals/red/test_red.py"
  py_log="$(py_suites "$py_d"; echo "py_ok=$py_ok py_bad=$py_bad")"
  py_colour="$(export PYTHON_COLORS=1; py_suites "$py_d"; echo "py_ok=$py_ok py_bad=$py_bad")"
  py_none="$(py_suites "$py_d/nothing-here"; echo "py_ok=$py_ok py_bad=$py_bad")"
  if grep -qF 'SUITE OK  (tools.good.test_good: 4 tests, 1 skipped)' <<<"$py_log" \
     && grep -qx 'py_ok=1 py_bad=4' <<<"$py_log" && grep -qx 'py_ok=0 py_bad=1' <<<"$py_none" \
     && grep -qx '      SKIP  D0 (LOUD): notice' <<<"$py_log" && grep -qx '      SKIP  D1 (LOUD): flushed' <<<"$py_log" \
     && ! grep -qE 'chatter|SKIPPED_DUPLICATE' <<<"$py_log" \
     && grep -q '^ *FAIL: test_named_in_the_report' <<<"$py_log" \
     && grep -qF 'SUITE OK  (tools.good.test_good: 4 tests, 1 skipped)' <<<"$py_colour" \
     && grep -qx 'py_ok=1 py_bad=4' <<<"$py_colour"; then
    echo "BITE  OK  (Python suite runner: a good module passes and shows its SKIP notice; no tests, all skipped, an import error and a red test fail, the red test named, colours on or off; no suites at all fails)"; pass=$((pass+1))
  else
    echo "BITE  MISS (Python suite runner)"; echo "$py_log" | tail -20 | sed 's/^/      /'; echo "$py_colour" | tail -20 | sed 's/^/      /'; echo "$py_none" | sed 's/^/      /'; fail=$((fail+1))
  fi
  rm -rf "$py_d"
  py_suites "$ROOT"; pass=$((pass+py_ok)); fail=$((fail+py_bad))
else
  skip python-suites "python3 absent — the tools/ and evals/ unit suites were NOT run"
fi

echo "--------"
# self-skips: listed on every run; with --expect-skips, an id outside the named set fails it
if [ "$EXPECT_SET" -eq 1 ]; then
  st_unexp="$(skip_unexpected "$SKIPPED" "$EXPECT_SKIPS")"
  if [ -n "$st_unexp" ]; then
    echo "SKIP  UNEXPECTED (outside --expect-skips \"$EXPECT_SKIPS\"):$st_unexp — make the case run here, or add its id to the set that caller names"
    fail=$((fail+1))
  fi
fi
echo "selftest: self-skipped:${SKIPPED:- none}"
echo "selftest: $pass passed, $fail failed$([ "$EXPORT_MATRIX" -eq 1 ] && echo ' (with the export gate matrix)')"
[ "$fail" -eq 0 ]
