#!/usr/bin/env bash
# Tabularium records lint — turns the prose rules in CLAUDE.md into executable guards.
# "A commitment with no failing test is a comment, not a control."
#
# Usage:  checks/check.sh [ROOT]        ROOT defaults to the repo root (parent of checks/)
# Exit:   0 = all guards green; 1 = a guard fired; 2 = setup error (incl. L0 precondition — except L0's
#         hidden-patient-directory arm, which reports as a guard finding and exits 1). A `WARN [Ln]`
#         line is advisory and never changes the exit code (today L4, L6 and L10's read-guard notice warn).
# Guards: L0 fail-closed precondition · L1 anti-truncation/structure ·
#         L4 citation integrity (warns only) ·
#         L5 person separation · L6 source naming (a warning only) · L7 moving-date single-source · L8 handout naming ·
#         L10 private-mode identifier residue ·
#         L13 person-ownership binding (ADR-0037; delegates to tools/person_ownership, fail-closed) ·
#         L15 sealed-handout byte binding (ADR-0039; delegates to tools/handout_attest, fail-closed) ·
#         L19 CARE never edits a tracked file (ADR-0050; runs only in the derived `care` mode) ·
#         L20 instance shape — DEV holds no record; the mode is derived, the marker only asserts it (ADR-0050).
#         Retired numbers, never reused (L3 L9 L11 L12 L16 L17 L18 L21): checks/README.md → Guards.
#         Guards FAIL CLOSED — a guard never reports green having examined nothing (ADR-0021). Each has
#         a bite-test in checks/selftest.sh.
set -uo pipefail
# SELF_ROOT = the repo THIS check.sh belongs to — resolved from $0 BEFORE any cd ($0 may be a
# relative path, which silently re-anchors to the linted tree after `cd "$ROOT"`; found 2026-07-17).
# L13/L15 load their verifier packages from here, whatever tree is being linted.
SELF_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# The release-name shape, defined once: `vMAJOR.MINOR.PATCH`, optionally `-slug` (the historical
# `v0.52.0-evals-ship-lean-route`). L19 applies it to the CARE pin; `checks/install-instance.sh care
# <tag>` asks `check.sh --release-name NAME` (exit 0 = a release name) before writing one. Both resolve
# the pin as `refs/tags/<pin>^{}`, which also accepts a revision such as `v0.54.0~1` — an untagged
# commit — so the shape is what keeps a pin naming a release. Whether the tag exists is each caller's.
is_release_name(){ case "$1" in ''|*[!A-Za-z0-9.-]*) return 1 ;; esac
  printf '%s\n' "$1" | LC_ALL=C grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9][A-Za-z0-9.-]*)?$'; }
if [ "${1:-}" = "--release-name" ]; then is_release_name "${2:-}"; exit $?; fi
# `--instance-mode` answers ONE question — what checkout family is this tree in, and what does that
# family assert — and exits. It is how `checks/git-hooks/pre-push` and `checks/install-instance.sh`
# get the answer instead of each carrying its own copy of the derivation (ADR-0050 point 7,
# 2026-09-10: the same rule written three times is what made the worktree fix cost three fixes, and
# what let the three copies disagree about one tree). No guard runs on this path.
IM_ONLY=0
if [ "${1:-}" = "--instance-mode" ]; then IM_ONLY=1; shift; fi
ROOT="${1:-$SELF_ROOT}"
cd "$ROOT" || { echo "FAIL: cannot cd to $ROOT"; exit 2; }
ROOT="$(pwd)"   # absolutize: L13/L15 pass --root from a different cwd (their package root)
# ---- L0: fail-closed precondition (ADR-0021) ----
# If we are not actually in the repo (CLAUDE.md + checks/ present), every glob below matches nothing
# and ALL guards "pass" over an empty tree — a false green. A guard must never report success having
# examined nothing. Refuse loudly instead. (Skeleton-safe: CLAUDE.md + checks/ ship in the skeleton too;
# patients/ is intentionally NOT required, since the published skeleton has none.)
if [ ! -f CLAUDE.md ] || [ ! -d checks ]; then
  printf 'FAIL [L0] %s\n' "not at repo root (CLAUDE.md/checks/ missing under '$ROOT') — refusing to report green over an empty/wrong tree"
  exit 2
fi
fail=0
err(){ printf 'FAIL [%s] %s\n' "$1" "$2"; fail=1; }
warn(){ printf 'WARN [%s] %s\n' "$1" "$2"; }   # tells the operator; never reds the board

# ---- Locators (ADR-0029 point 11) ----
# A red names the file it is about, relative to the tree. The one reason to withhold it is private
# mode: a filename can carry the identifier that must never reach the AI API. So `loc` withholds a
# path inside a person folder whose profile.md carries the marker (L10's test), and — only while
# some person in the tree is private-mode — a path whose owner cannot be established (a profile that
# is absent, linked, not a regular file or unreadable; `_shared/`). Everything else prints.
# The same rule lives in tools/person_ownership/fsverify.py `locator()` for L13/L15; keep both.
LOC_MARK='⟨never-API⟩'
LOC_ANY_PRIVATE=0
# $1 = a person folder -> public | private | unknown. Never follows a link, opens only a regular file.
loc_status(){
  if [ -L "$1" ] || [ ! -d "$1" ] || [ -L "$1/profile.md" ] || [ ! -f "$1/profile.md" ]; then
    echo unknown; return
  fi
  # Bytes, here and wherever the marker is searched: under a UTF-8 locale grep can miss it after a
  # byte that is not UTF-8, or anywhere after a NUL byte.
  LC_ALL=C grep -qF "$LOC_MARK" "$1/profile.md" 2>/dev/null
  case $? in 0) echo private ;; 1) echo public ;; *) echo unknown ;; esac
}
# $1 = a tree-relative path -> the person folder it lies in: `…patients/<h>` at any depth (L20 looks
# for records misplaced anywhere), the parent of a `med/` otherwise, `_shared` for the joint lane,
# or nothing (product paths have no owner).
loc_owner(){
  local rest="$1" pre="" c
  case "$rest" in _shared|_shared/*) printf '_shared'; return ;; esac
  while [ -n "$rest" ]; do
    c="${rest%%/*}"
    if [ "$c" = "$rest" ]; then rest=""; else rest="${rest#*/}"; fi
    if [ "$c" = patients ] && [ -n "$rest" ]; then printf '%s' "${pre}patients/${rest%%/*}"; return; fi
    if [ "$c" = med ] && [ -n "$pre" ]; then printf '%s' "${pre%/}"; return; fi
    pre="$pre$c/"
  done
}
# $1 = a tree-relative path -> that path (control bytes shown as ?), or the withheld form.
loc(){
  local o s="public"
  o="$(loc_owner "$1")"
  [ -n "$o" ] && s="$(loc_status "$o")"
  if [ "$s" = private ]; then printf '%s' "<locator withheld: private-mode person>"
  elif [ "$s" = unknown ] && [ "$LOC_ANY_PRIVATE" -eq 1 ]; then printf '%s' "<locator withheld: owner unknown while private mode is in use>"
  else printf '%s' "$1" | tr '\001-\037\177' '?'; fi
}
# $1 = path, $2 = value read from that path. A private/unknown owner's *contents* can carry the
# protected identifier too; L10 runs later, so a diagnostic must not echo them on the way to red.
loc_detail(){
  if [ "$(loc "$1")" = "$1" ]; then
    printf '%s' "$2" | tr '\001-\037\177' '?'
  else
    printf '%s' '<detail withheld: private-mode or unknown owner>'
  fi
}
# Sets LOC_ANY_PRIVATE: a person declares private mode, or has a profile.md whose status cannot be
# read, or the roster itself cannot be listed. Run once patients/ is known to be a real directory.
loc_scan(){
  local d
  # A quoted glob, as L10 enumerates people: a folder name holding a line break reads as itself (the
  # find-and-split this replaced misread one; review 2026-10-25). Dot-prefixed folders are included —
  # L0 rejects them right after, but the locator rule must already know about them.
  { [ -r patients ] && [ -x patients ]; } || { LOC_ANY_PRIVATE=1; return; }
  for d in patients/*/ patients/.[!.]*/ patients/..?*/; do
    [ -d "$d" ] || continue
    d="${d%/}"
    case "$(loc_status "$d")" in
      private) LOC_ANY_PRIVATE=1 ;;
      unknown) { [ -e "$d/profile.md" ] || [ -L "$d/profile.md" ]; } && LOC_ANY_PRIVATE=1 ;;
    esac
  done
}
# $1 = newline-separated tree-relative paths -> "<first located>" plus " (+N more)" when N > 0.
loc_first(){
  local first n
  first="$(printf '%s\n' "$1" | sed -n '1p')"
  n="$(printf '%s\n' "$1" | sed '/^$/d' | wc -l | tr -d '[:space:]')"
  printf '%s' "$(loc "$first")"
  [ "${n:-1}" -gt 1 ] && printf ' (+%s more)' "$((n - 1))"
  return 0
}

# ---- the CHECKOUT FAMILY: one derivation, three consumers (ADR-0050 point 7) ---------------------
# Guard L20's two inputs are UNTRACKED — the `.tabularium-instance` marker and the record
# directories — and untracked files are per-tree, so a linked worktree (ADR-0040) has neither. The
# instance is therefore a property of the CHECKOUT FAMILY: one repository, one instance. This is the
# only place that is worked out; L20 below, `checks/git-hooks/pre-push` and
# `checks/install-instance.sh` all consume THIS answer (the hook and the installer via
# `check.sh --instance-mode`). Three copies of one rule is what made the first version of this fix
# cost three fixes and still let the copies disagree about the same tree.
#
# It reports; it never decides. Every red, block and refusal stays with the caller — which is how the
# asymmetry is kept: the CARE side (records to protect) reds hard, and DEV-side ambiguity is loud and
# proceeds, because a wrong answer there costs a rerun, not a record (operator, 2026-09-10).
#
# ONE outcome for every family we cannot verify — bare repository, `--separate-git-dir`, main tree
# gone, unreadable marker: `status=unverifiable`, nothing inherited, said out loud, and the tree's own
# marker governs exactly as it does in a plain clone. That collapse is deliberate. The version this
# replaced asked `core.bare` first and let a `true` end the family read, so ONE config bit — a bit
# this repository has already flipped by accident once (2026-07-06) and which can also arrive from
# the environment with no file written — silently restored the pre-fix state in all three copies
# (Tier-S red-team round 2, N1). No git config is consulted here at all now, and the exotic layouts
# that round found (N2) land in the same harmless branch instead of being detected one by one.
#
# Locator discipline: `family=` IS an absolute path, because the callers need it to read a file. It
# must never reach guard output — a directory name can carry a person handle (the L10/L20 rule).
fam_git(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY git "$@"; }
FAM_KIND=""      # main | worktree | nogit
FAM_STATUS=""    # ok (a verified main work tree) | unverifiable | n/a (not a worktree)
FAM_PATH=""      # the family's main work tree, absolute; empty unless status=ok
FAM_MARKER=""    # what that tree asserts: dev | care | ''
FAM_MSTATE=""    # absent | ok | bad (symlinked, not a regular file, or not exactly one line)
FAM_REASON=""    # one short phrase for the loud line; never a path
# $1 = a tree whose `.tabularium-instance` to read -> FAM_MARKER / FAM_MSTATE / FAM_REASON.
# Exactly the stance L20 takes on a local marker: never followed through a link, a regular readable
# file, exactly one line.
fam_read_marker(){
  local mm="$1/.tabularium-instance" mraw
  [ -e "$mm" ] || [ -L "$mm" ] || { FAM_MSTATE="absent"; return 0; }
  if [ -L "$mm" ] || [ ! -f "$mm" ] || [ ! -r "$mm" ]; then
    FAM_MSTATE="bad"; FAM_REASON="the family's marker is not a readable regular file"; return 0
  fi
  mraw="$(tr -d '\r' < "$mm" | sed '/^[[:space:]]*$/d')"
  FAM_MARKER="$(printf '%s\n' "$mraw" | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  if [ "$(printf '%s\n' "$mraw" | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')" = "1" ]; then
    FAM_MSTATE="ok"
  else
    FAM_MSTATE="bad"; FAM_MARKER=""; FAM_REASON="the family's marker does not hold exactly one line"
  fi
  return 0
}
family_resolve(){
  local fam cand cgd cgc cabs
  FAM_KIND="nogit"; FAM_STATUS="n/a"; FAM_PATH=""; FAM_MARKER=""; FAM_MSTATE="absent"; FAM_REASON=""
  command -v git >/dev/null 2>&1 || { FAM_REASON="git is not installed"; return 0; }
  [ -e .git ] || { FAM_REASON="no .git at this root"; return 0; }
  fam_git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { FAM_REASON="not a git work tree"; return 0; }
  [ -z "$(fam_git rev-parse --show-prefix 2>/dev/null)" ] || { FAM_REASON="not at the top level of the work tree"; return 0; }
  local gd gc
  gd="$(fam_git rev-parse --git-dir 2>/dev/null)" || gd=""
  gc="$(fam_git rev-parse --git-common-dir 2>/dev/null)" || gc=""
  if [ -z "$gd" ] || [ -z "$gc" ]; then FAM_REASON="git cannot name this tree's git directory"; return 0; fi
  if [ "$gd" = "$gc" ]; then                                  # a main checkout IS its own family
    FAM_KIND="main"; FAM_PATH="$(pwd)"; fam_read_marker "$FAM_PATH"; return 0
  fi
  FAM_KIND="worktree"; FAM_STATUS="unverifiable"
  # The family's git directory, absolutized. cwd is the linted root, so a relative answer resolves
  # against it; a subshell's cd cannot move this script's cwd.
  case "$gc" in
    /*) fam="$(cd "$gc" 2>/dev/null && pwd)" || fam="" ;;
    ?*) fam="$(cd "./$gc" 2>/dev/null && pwd)" || fam="" ;;
    *)  fam="" ;;
  esac
  if [ -z "$fam" ]; then FAM_REASON="the family's git directory does not resolve"; return 0; fi
  # Its parent is the main work tree in the ONE layout this system uses. Verified, not assumed: git
  # must read that directory as a checkout root (`--git-dir` = `--git-common-dir`, which is false in
  # any linked worktree) whose common dir is this same family, and the family's git directory must
  # be that tree's own `.git`. Anything else is `unverifiable` — including a bare repository, whose
  # parent is not a work tree at all, and a separate git directory, which git itself cannot map back
  # to its work tree (round 2, N2: the mapping is one-way, so do not pretend to invert it).
  cand="$(dirname "$fam")"
  if [ ! -d "$cand" ]; then FAM_REASON="the family's main work tree is missing"; return 0; fi
  cgd="$(fam_git -C "$cand" rev-parse --git-dir 2>/dev/null)" || cgd=""
  cgc="$(fam_git -C "$cand" rev-parse --git-common-dir 2>/dev/null)" || cgc=""
  if [ -z "$cgd" ] || [ "$cgd" != "$cgc" ]; then FAM_REASON="no main work tree beside the family's git directory"; return 0; fi
  case "$cgc" in
    /*) cabs="$(cd "$cgc" 2>/dev/null && pwd)" || cabs="" ;;
    ?*) cabs="$(cd "$cand" 2>/dev/null && cd "$cgc" 2>/dev/null && pwd)" || cabs="" ;;
    *)  cabs="" ;;
  esac
  if [ -z "$cabs" ] || [ "$cabs" != "$fam" ]; then FAM_REASON="the tree beside the family's git directory belongs to another repository"; return 0; fi
  if [ "$fam" != "$cand/.git" ]; then FAM_REASON="the family's git directory is not that tree's own .git"; return 0; fi
  # Every git-level test above passes for a git directory that merely SITS in a container directory
  # (`--separate-git-dir <box>/.git`): git reads `<box>` as a checkout root of the family while the
  # real work tree is elsewhere, so the marker would be read from a directory that holds none
  # (round 2, N2 / shape S4). A main checkout of THIS repository necessarily satisfies L0's own
  # precondition, so require it — the cheapest test that tells a work tree from a box.
  if [ ! -f "$cand/CLAUDE.md" ] || [ ! -d "$cand/checks" ]; then
    FAM_REASON="the tree beside the family's git directory is not a checkout of this repository"; return 0; fi
  FAM_STATUS="ok"; FAM_PATH="$cand"; fam_read_marker "$FAM_PATH"
  return 0
}
if [ "$IM_ONLY" -eq 1 ]; then
  family_resolve
  printf 'kind=%s\nstatus=%s\nmarker=%s\nmarker_state=%s\nreason=%s\nfamily=%s\n' \
    "$FAM_KIND" "$FAM_STATUS" "$FAM_MARKER" "$FAM_MSTATE" "$FAM_REASON" "$FAM_PATH"
  exit 0
fi

# A dot-prefixed directory under patients/ is not harmless cruft: every patient-discovery glob
# below excludes it. A symlinked patients root or patient directory is worse — ordinary globs follow
# it and can make guards read an unrelated tree. Reject those shapes before any discovery/read; the
# locator follows the private-mode rule above (a symlinked root is never followed to classify it).
if [ -L patients ]; then
  printf 'FAIL [L0] %s\n' "patients/ root is symlinked — refusing to discover records outside the repository"
  exit 2
elif [ -e patients ] && [ ! -d patients ]; then
  printf 'FAIL [L0] %s\n' "patients/ root exists but is not a real directory"
  exit 2
elif [ -d patients ]; then
  loc_scan
  patient_links="$(find patients -mindepth 1 -maxdepth 1 -type l -print 2>/dev/null)"; plrc=$?
  if [ "$plrc" -ne 0 ]; then
    printf 'FAIL [L0] %s\n' "cannot inspect patients/ root for symlinked patient nodes — discovery may be redirected"
    exit 2
  elif [ -n "$patient_links" ]; then
    printf 'FAIL [L0] %s\n' "symlink directly under patients/: $(loc_first "$patient_links") — refusing redirected patient discovery"
    exit 2
  fi
  hidden_patient_nodes="$(find patients -mindepth 1 -maxdepth 1 -name '.*' -type d -print 2>/dev/null)"; hprc=$?
  if [ "$hprc" -ne 0 ]; then
    err L0 "cannot inspect patients/ root for hidden patient nodes — discovery may be blinded"
  elif [ -n "$hidden_patient_nodes" ]; then
    err L0 "hidden directory directly under patients/: $(loc_first "$hidden_patient_nodes") — patient roots must be visible to every guard"
  fi
fi

# auto-discover every patient folder (no hardcoded handles → no roster in a published file)
# HOST-PORTABILITY (ADR-0020): every "${CANON[@]}" loop below uses the ${CANON[@]+"${CANON[@]}"} form,
# because on bash 3.2 (the macOS host) `set -u` treats an EMPTY array's "${arr[@]}" as an *unbound
# variable* and aborts. CANON is empty on a patient-free tree (the published skeleton, or a fresh repo) —
# the plain form crashed check.sh there instead of letting it pass green. Masked locally (real patients
# keep CANON non-empty); only a patient-free tree exposes it. Regression: selftest.sh case "skeleton-safe".
CANON=()
for p in patients/*/; do
  [ -f "${p}profile.md" ] && CANON+=("${p}profile.md")
  [ -f "${p}medications.md" ] && CANON+=("${p}medications.md")
done
# L1 coverage (fail-closed, ADR-0021): patient folders present but ZERO canonical docs discovered ⇒
# discovery is blinded → fail loud rather than skip the L1 loop and pass. (0 patient folders is a
# legitimate empty state — e.g. the skeleton — so only trip when folders exist but docs don't.)
_pd=0; for d in patients/*/; do [ -d "$d" ] && _pd=$((_pd+1)); done
[ "$_pd" -gt 0 ] && [ "${#CANON[@]}" -eq 0 ] && err L1 "$_pd patient folder(s) present but 0 canonical docs discovered — L1 blinded"

# ---- L1: structural completeness / anti-truncation (the 38-line incident) ----
for f in ${CANON[@]+"${CANON[@]}"}; do
  [ -f "$f" ] || { err L1 "$(loc "$f") missing"; continue; }
  case "$f" in
    */profile.md)
      for h in "## Active conditions" "## Current status" "## Next steps" "## Change log"; do
        grep -qF "$h" "$f" || err L1 "$(loc "$f") missing required header: $h (truncation?)"
      done ;;
    */medications.md)
      grep -qF "## Change log" "$f" || err L1 "$(loc "$f") missing required header: ## Change log" ;;
  esac
  # a canonical doc must not END on a table row — that's what a mid-write truncation looks like
  last="$(grep -v '^[[:space:]]*$' "$f" | tail -1)"
  [ "${last:0:1}" = "|" ] && err L1 "$(loc "$f") ends on a table row (suspected truncation): $(loc_detail "$f" "${last:0:48}")"
  # gross-shrink floor
  n="$(wc -l < "$f")"
  [ "$n" -lt 25 ] && err L1 "$(loc "$f") only $n lines (suspiciously short)"
done

# ---- L5: person separation (highest-severity error class) ----
# No OTHER patient's folder-name token may appear inside a patient's files (scales to N patients).
# Shared surname is NOT a trigger — we match each folder's basename as a whole word (grep -w).
# Discovery is HOST-PORTABLE: a glob + parameter-expansion basename (no bash-4-only builtins, no
# GNU-only find flags — the operator's host is macOS bash 3.2 / BSD userland). Portability is
# lint-guarded in selftest.sh; see ADR-0020. (Earlier this used a Linux-sandbox-only construct that
# ran red on the host — and a naive half-fix would have left this list empty, silently disabling the
# highest-severity guard. Hence the tripwire below.)
PT=()
for d in patients/*/; do
  [ -d "$d" ] || continue                 # no match → literal glob → skip
  base="${d%/}"; PT+=("${base##*/}")       # strip trailing slash, then path → basename
done
# Tripwire: canonical docs exist but zero handles enumerated ⇒ discovery is blinded → fail loud.
if [ "${#PT[@]}" -eq 0 ] && [ "${#CANON[@]}" -gt 0 ]; then
  err L5 "0 patient folders enumerated but ${#CANON[@]} canonical doc(s) present — L5 discovery blinded (portability?)"
fi
# L5's search. A UTF-8 locale treats a non-ASCII letter as part of the word around it, so grep runs under the
# board's own locale. macOS and Linux grep can lose a hit on a line holding a byte that locale cannot decode, so
# those lines, and only those, are searched again as bytes. There a non-ASCII letter ends a word, so a handle
# inside a longer word also reds; saving the file as UTF-8 clears that. -a on both searches: a NUL byte elsewhere
# in the file must not hide such a line, or turn a hit into a summary the sources exemption cannot read.
l5_search(){ # grep flags, handle, directory - prints each hit once; returns grep's exit code, 0 on any hit
  local hits rc bytes
  hits="$(grep "$1" -e "$2" "$3" --include='*.md' 2>/dev/null)"; rc=$?
  [ "$rc" -ge 2 ] && return "$rc"
  bytes="$(LC_ALL=C grep "$1" -e "$2" "$3" --include='*.md' 2>/dev/null)"
  [ $? -ge 2 ] && return 2
  bytes="$(printf '%s\n' "$bytes" | grep -axv '.*')"
  [ -n "$bytes" ] && { hits="$(printf '%s\n%s\n' "$hits" "$bytes" | LC_ALL=C grep -a . | LC_ALL=C sort -u)"; rc=0; }
  [ -z "$hits" ] || printf '%s\n' "$hits"
  return "$rc"
}
if [ "${#PT[@]}" -gt 0 ]; then
  # Fail closed on a non-matchable handle (ADR-0021): each handle is interpolated below as an ERE.
  # A regex metacharacter would either error grep out (rc=2, indistinguishable from "no hits" in a
  # bare && chain — the pair silently skips) or silently WIDEN matching ('.' matches any char).
  # Handles are free-form (ADR-0003), so nothing else constrains them — validate up front instead.
  for p in "${PT[@]}"; do
    case "$p" in *[!a-zA-Z0-9_-]*)
      err L5 "handle path $(loc "patients/$p") contains non-[A-Za-z0-9_-] characters — L5 cannot safely match it (rename the folder)";;
    esac
  done
  for p in "${PT[@]}"; do
    for q in "${PT[@]}"; do
      [ "$p" = "$q" ] && continue
      # rc captured explicitly: rc=2 (grep error) must fail loud, never read as "no hits" (ADR-0021)
      # `-e`: a handle may start with "-", which grep would otherwise read as an option (blinding L5)
      hits="$(l5_search -rnaiwE "$q" "patients/$p/")"; rc=$?
      if [ "$rc" -ge 2 ]; then
        err L5 "grep failed (rc=$rc) matching handle '$(loc_detail "patients/$q" "$q")' inside $(loc "patients/$p") — L5 blinded for this pair"
      elif [ "$rc" -eq 0 ] && [ -n "$hits" ]; then
        # Evidence-layer exemption (ADR-0028): med/sources/** is an immutable transcript of reality —
        # third parties (clinicians, lab staff) may legitimately share a first name with a patient
        # handle (a first-name handle meets unrelated clinicians sharing that name in other
        # patients' scans). L5's target is ASSISTANT-AUTHORED cross-contamination, so the canonical
        # docs, analysis, handouts and nmed stay fully scanned; a truly misfiled scan would carry the
        # other person's REAL name (≠ handle), which this grep never caught anyway — that risk is
        # owned by the operator's placement of the document and the ownership ledger (ADR-0028 point 2).
        # Path-anchored filter, applied only on rc=0 so rc≥2 above still fails loud.
        hits="$(printf '%s\n' "$hits" | LC_ALL=C grep -av '^patients/[^:]*/med/sources/')"
        if [ -n "$hits" ] && { [ "$(loc "patients/$p")" != "patients/$p" ] || [ "$LOC_ANY_PRIVATE" -eq 1 ]; }; then
          # a hit line carries a file name and text; while any person is in private mode either can
          # carry the identifier, so only the count prints (review 2026-10-25)
          err L5 "'$(loc_detail "patients/$q" "$q")' referenced inside $(loc "patients/$p") — separation breach in $(printf '%s\n' "$hits" | grep -c .) line(s); lines withheld under the locator rule"
        elif [ -n "$hits" ]; then
          err L5 "'$q' referenced inside patients/$p/ — separation breach:"; echo "$hits" | sed 's/^/        /'
        fi
      fi
    done
  done
  # The shared reference library is read in every person's session and every fact-check bundle, so a
  # handle there carries one person into another's context, a Candidates annotation included. Whole-word as above but CASE-SENSITIVE: a lowercase handle that is also an ordinary
  # word in a citation line must not red a bibliography line. Accepted gaps: the handle capitalised
  # (e.g. at a sentence start), symlinked files or subdirectories, `.MD`/`.markdown` files and the
  # `whitelist.txt`/`blacklist.txt` lists are not scanned. `_shared/` and the roster
  # (patients/README.md) may name several people at pointer level and stay unscanned.
  if [ -d reference-library ]; then
    for q in "${PT[@]}"; do
      hits="$(l5_search -rnawE "$q" reference-library/)"; rc=$?
      if [ "$rc" -ge 2 ]; then
        err L5 "grep failed (rc=$rc) matching handle '$(loc_detail "patients/$q" "$q")' inside reference-library/ — L5 blinded for the shared library"
      elif [ "$rc" -eq 0 ] && [ -n "$hits" ] && [ "$LOC_ANY_PRIVATE" -eq 1 ]; then
        # the hit lines name a library file and quote it; while any person is in private mode either
        # can carry the identifier, so only the count prints (review 2026-10-25)
        err L5 "'$(loc_detail "patients/$q" "$q")' referenced inside the shared reference-library/ in $(printf '%s\n' "$hits" | grep -c .) line(s) — file names and lines withheld while private mode is in use; name no person there (a note about one person belongs in their med/analysis/)"
      elif [ "$rc" -eq 0 ] && [ -n "$hits" ]; then
        err L5 "'$q' referenced inside the shared reference-library/ — name no person there (a note about one person belongs in their med/analysis/):"
        echo "$hits" | sed 's/^/        /'
      fi
    done
  fi
fi

# ---- L4: citation integrity ----
# WARNS, NEVER REDS (ADR-0048 point 10, operator decision): every finding below prints
# `WARN [L4] …` and leaves the exit code alone. Where the comments in this section say "reds" or
# "fails closed", read "warns" — the checks themselves are unchanged.
#
# A clinical doc (profile/medications/handout markdown) may NOT cite an identifier that lives
# only under "## Candidates — PENDING VERIFICATION" in the reference library. Catches the
# wrong-paper / unvetted-citation class (a review cited by a wrong id). index.md itself is exempt.
# Comparison is CANONICAL ID vs CANONICAL ID — the same extractor runs on both the Candidates
# section and each scanned doc. The old form (mangled candidate substring searched in de-spaced
# doc text) was FAIL-OPEN: a trailing comma on the index line, a markdown-link DOI, or "PMID N"
# vs "PMID: N" spacing made the candidate unmatchable against a cleanly-cited id (ADR-0021).
#
# ADR-0048 — closed-world Vetted membership (does NOT touch link/guideline
# rot — that half needs a per-entry verified-date mark and stays open, offline-unreachable by design).
# Blocking known-Candidate ids (above) is necessary but not sufficient: a hallucinated identifier that
# appears in NO library entry at all — never listed as a Candidate either — passed before this. Every
# citation id found in a clinical doc must now RESOLVE to a "## Vetted" entry; anything else reds,
# whether or not it happens to also be a named Candidate.
#
# Recognised forms (enumerated from reference-library/README.md's bar + what the live corpus actually
# emits — not invented): PMID, DOI, PMC — l4_ids() below. A "recognised guideline body" citation
# (NICE/USPSTF/ESC/PTK-PTND-and-other-Polish-society-guidelines/Cochrane/WHO, per README.md's bar) is
# never identifier-less: the bar's "Traceable: a working DOI or PMID" clause is unconditional, so
# there is no fourth, id-less parsing form to build. The live corpus proves the boundary case rather
# than needing one invented: a live classification monograph (a defining standard-setting text,
# admitted under the guideline-body clause) is Vetted via DOI ALONE — "book chapter — no PMID; not
# PubMed-indexed" (reference-library/index.md) — which is simply the existing DOI form with an empty
# PMID slot; l4_ids() already extracts a DOI-only or PMID-only entry correctly with no special-casing.
# PMC is recognised/parsed because the original Candidate-side extractor already parsed it; no live
# Vetted entry is PMC-keyed today, so a citation using ONLY a paper's PMC id (when the library recorded
# that same paper's PMID/DOI instead) has no path to Vetted membership and would red — a documented
# residual (no cross-identifier PMID<->PMC<->DOI resolution is attempted; this is an offline closed-
# world check, not a live lookup), not a defect: it hasn't occurred in the live corpus.
l4_ids(){ # stdin (raw text) → canonical citation ids, one per line
  # extraction runs on RAW text (spaces still delimit DOIs); ']'/'}'/')' stop a DOI so a
  # markdown-link candidate yields the clean id; then lowercase, strip trailing punctuation,
  # drop the pmid colon — identical canonical form on both sides. bash-3.2/BSD-safe.
  #
  # ADR-0048 hardening (found running the closed-world check against the LIVE library — the
  # original Candidate-only use of this extractor never exercised these two shapes):
  #  (1) a DOI immediately closed by markdown bold ("**DOI 10.1000/xyz123.**" in shape, the live
  #      reference-library/index.md house style) is not bounded by the stop-class below — "." and
  #      "*" are not markdown-STRUCTURAL delimiters the way "]"/")"/"{"/"}" are, so the old
  #      extraction silently trailed a literal ".**" into the "id", which then could never equal
  #      the same DOI extracted cleanly from a handout's markdown-link form. Stripped in the
  #      trailing-punctuation pass below (added "*" alongside the existing [.,;:]).
  #  (2) a DOI whose own real suffix contains a parenthesised segment (shaped "S0000-
  #      0000(25)00000-X", a shape real DOIs carry) hit the stop-class's ")" at the
  #      FIRST internal close-paren and truncated to "...0000(25" — worse than cosmetic: two
  #      DIFFERENT real DOIs sharing a year ("(25)", "(26)", …) truncate to the SAME wrong prefix,
  #      an actual collision risk for a fabrication check, not merely an ugly id. "(" now joins the
  #      stop-class, with a single-level "\([^()]*\)" escape hatch so exactly one balanced
  #      parenthesised group is consumed as part of the id — enough for the live shape without
  #      accepting nested/unbalanced parens (which would just re-open the same ambiguity).
  # (1) and (2) were verified against a working library: no id lost or changed except the intended
  # repairs (checks/selftest.sh; the validation run is recorded in adr/0048-*.md).
  #  (3) a DOI closed by an autolink's ">" ("<https://doi.org/10.…>"), a code span's
  #      backtick or an ASCII quote kept that character, so a Vetted DOI written that way read as
  #      uncatalogued. They join the trailing pass, not the stop-class: a SICI-style DOI carries "<"
  #      and ">" inside its suffix, and stripping only at the end keeps it whole on both sides. A
  #      quote with more text glued after it (an HTML href="…">) still sticks; no live handout is HTML.
  grep -oiE 'PMC[0-9]+|10\.[0-9]{4,9}/([^] (){}]|\([^()]*\))+|PMID:? *[0-9]+' \
  | tr -d ' ' | tr '[:upper:]' '[:lower:]' \
  | sed -E "s/[*.,;:\"'\`>]+\$//; s/^pmid:/pmid/" | sort -u
}
# Vetted-side extraction strips "*(...)*" italicized parenthetical asides before running l4_ids()
# (ADR-0048 finding, red-team style: don't assume the boundary is clean, test it). The library
# legitimately discusses a WRONG/mis-cited id as a caveat inside an otherwise-Vetted entry's own
# commentary — e.g. an italic aside naming the mis-cited review id an entry replaces sits inside
# that Vetted bullet. Left unstripped, that id earns accidental Vetted membership by mere mention,
# defeating the closed-world check for exactly the wrong-paper class it exists to catch. A Vetted
# citation's OWN id sits in **bold**, never inside an italic aside — verified against a working
# index.md (reference-library/index.md): stripping removed only non-citation mentions. This is a
# boundary-drawing judgment call, not a completeness proof — see the ADR.
l4_strip_asides(){ # stdin (raw text) → same text, asides removed
  # count nested parentheses instead of stopping at the first ")". Keep the
  # existing line-local scope and require a complete outer ")*"; ordinary parentheses,
  # incomplete wrappers and text between separate asides stay available to l4_ids().
  awk '{
    rest=$0; out=""
    while (start=index(rest, "*(")) {
      out=out substr(rest, 1, start-1)
      depth=1
      for (i=start+2; i<=length(rest); i++) {
        ch=substr(rest, i, 1)
        if (ch=="(") depth++
        else if (ch==")") depth--
        if (depth==0) break
      }
      if (depth==0 && substr(rest, i+1, 1)=="*") {
        rest=substr(rest, i+2)
      } else {
        out=out "*("
        rest=substr(rest, start+2)
      }
    }
    print out rest
  }'
}

# BOTH depths (ADR-0039): depth-2 = legacy flat handouts (handouts/<audience>/file.md); depth-3 =
# sealed encounter units (handouts/<audience>/<YYYY-MM-DD-slug>/file.md) AND legacy archive/ files.
# The depth-2-only glob would silently match ZERO sealed handouts — L4 fail-open on the exact docs
# a clinician receives (10-agent panel finding, 2026-07-17); regression bite in selftest.sh.
# L4_TARGETS is walked twice below (a coverage count, then the real scan) — computed once, reused,
# rather than trusting two separately-typed globs to stay in sync.
L4_TARGETS=()
for f in ${CANON[@]+"${CANON[@]}"} patients/*/med/handouts/*/*.md patients/*/med/handouts/*/*/*.md; do
  [ -f "$f" ] || continue   # also skips the literal unmatched-glob token when no handouts exist (no nullglob) — keep this guard
  case "$f" in *.factcheck.md) continue ;; esac   # ADR-0034 QA sidecar, not a clinical handout — it legitimately names a Candidate id when flagging an 'unvetted' citation, which would false-trip L4
  case "$(basename "$f")" in INDEX.md|README.md) continue ;; esac   # operator-facing registry/pointer docs, not a citation surface — same exemption L8 already gives them; a live archive/README.md was being scanned before this (arbiter red-team, item 3)
  L4_TARGETS+=("$f")
done

# Fail-closed coverage (ADR-0021; the L1/L5 precedent: docs present but the thing that must vouch
# for them is blinded ⇒ loud, not silent). A missing/symlinked/non-regular/empty reference-library
# index while a clinical doc CITES SOMETHING is not "feature absent" the way an absent
# patients/ is for L10 (nothing there yet, nothing claimed) — it means Vetted membership cannot
# be established for a claim that already exists, which is worse than any single red. Judgment call
# (flagged for the arbiter): this treats "library missing" as categorically different from "library
# present but has nothing new to say" — precedent is L15's stance on its own discovery roots, not a
# byte-identical guard, since reference-library/ has no sibling guard that already set this norm.
#
# Gate is on L4_CITING (a doc containing >=1 well-formed id), NOT on "${#L4_TARGETS[@]}" (every
# scanned doc) — profile.md/medications.md are IN L4_TARGETS (so a stray citation there still gets
# checked below) but never cite PubMed literature in this system's own design (they cite med/
# sources/ evidence instead); gating on mere doc-existence made every OTHER guard's synthetic
# profile-only fixture spuriously trip L4 the instant it lacked a reference-library/ of its own
# (found running the full selftest suite — 30+ unrelated assert_pass bites went red; a real
# regression caught by exercising the whole board, not just the new bites in isolation).
L4_CITING=0
for f in ${L4_TARGETS[@]+"${L4_TARGETS[@]}"}; do
  # a doc L4 cannot open is not "citing nothing" — it is unexamined (2026-08-23 audit).
  # Readability is tested explicitly: l4_ids ends in a pipefail pipeline whose grep returns 1 on a
  # citation-free doc, so its rc cannot distinguish "nothing cited" from "could not read".
  [ -r "$f" ] || { warn L4 "cannot read $(loc "$f") — L4 blinded for this doc (fail closed)"; continue; }
  [ -n "$(l4_ids < "$f")" ] && L4_CITING=$((L4_CITING+1))
done

# The trust gate runs BEFORE any extraction (the L18 precedent: a flagged symlink is never read
# through, not just flagged-and-trusted-anyway — a symlinked index could otherwise vouch for
# whatever an attacker/accident points it at while still nominally "having a Vetted section"; CAND/
# VETTED are only ever populated from a path that passed this gate, so a distrusted index behaves
# exactly like an absent one for every downstream per-citation check, never a laundered pass).
L4_IDX_OK=0
if [ "$L4_CITING" -gt 0 ]; then
  if [ -L reference-library/index.md ]; then
    warn L4 "reference-library/index.md is a symlink — refusing to trust an externally-redirected library while $L4_CITING clinical doc(s) cite an identifier"
  elif [ -e reference-library/index.md ] && [ ! -f reference-library/index.md ]; then
    warn L4 "reference-library/index.md exists but is not a regular file — citation membership cannot be established for $L4_CITING clinical doc(s)"
  elif [ ! -f reference-library/index.md ]; then
    warn L4 "reference-library/index.md missing but $L4_CITING clinical doc(s) cite an identifier — citation membership cannot be established (fail closed)"
  else
    L4_IDX_OK=1
  fi
elif [ -f reference-library/index.md ] && [ ! -L reference-library/index.md ]; then
  L4_IDX_OK=1   # nothing to scan yet, but a trustworthy library present anyway (e.g. seeded ahead of the first handout) — harmless to read
fi

CAND=""; VETTED=""
if [ "$L4_IDX_OK" -eq 1 ]; then
  CAND="$(awk '/^## Candidates/{c=1} c' reference-library/index.md 2>/dev/null | l4_ids)"
  # Everything BEFORE "## Candidates" is Vetted content (## Vetted AND ### Vetted sub-sections, plus
  # prose/dividers that carry no ids) — the exact mirror of CAND's own boundary above, inverted; this
  # avoids hard-coding every "## Vetted — <topic>" heading text, which is unbounded and would
  # silently miss a topic added without updating a guard-side allowlist.
  VETTED="$(awk '/^## Candidates/{exit} {print}' reference-library/index.md 2>/dev/null | l4_strip_asides | l4_ids)"
  [ "$L4_CITING" -gt 0 ] && [ -z "$VETTED" ] && \
    warn L4 "reference-library/index.md present but yields ZERO Vetted identifiers while $L4_CITING clinical doc(s) cite an identifier — L4 Vetted-membership check blinded (empty/malformed library?)"
fi

for f in ${L4_TARGETS[@]+"${L4_TARGETS[@]}"}; do
  [ -r "$f" ] || continue   # the coverage loop above already warned
  DOC_IDS="$(l4_ids < "$f")"
  [ -z "$DOC_IDS" ] && continue
  while IFS= read -r cid; do
    [ -z "$cid" ] && continue
    # VETTED is checked FIRST (arbiter red-team item 1, 2026-08-16): a "## Candidates" bullet may
    # legitimately mention an ALREADY-Vetted id in its own editorial prose (e.g. "cf. the already-
    # Vetted PMID NNNNN finding above") — CAND's extraction sweeps that mention in exactly the same
    # way it sweeps a genuine pending id (by design, mirroring VETTED's own boundary-only extraction).
    # Checking CAND first made a handout's CORRECT citation of that Vetted id red as "unverified
    # candidate" — a live-plausible false positive, not a hypothetical. Vetted membership now wins
    # outright, even when the same id is also textually present in Candidates. Accepted consequence
    # (documented, not silently absorbed): an id truly listed in BOTH sections — e.g. promoted to
    # Vetted but sloppily left in Candidates — now passes too; the guard cannot mechanically tell
    # "incidental mention" from "stale duplicate entry" apart, and passing is the safe direction for
    # that ambiguity (the id IS genuinely vetted either way). This is a library-hygiene state, not
    # handout fabrication; a future "no id in both sections" lint on reference-library/index.md
    # itself would catch the staleness case without touching this guard.
    if [ -n "$VETTED" ] && printf '%s\n' "$VETTED" | grep -qxF "$cid"; then
      :   # Vetted wins
    elif [ -n "$CAND" ] && printf '%s\n' "$CAND" | grep -qxF "$cid"; then
      warn L4 "unverified candidate citation '$(loc_detail "$f" "$cid")' used in clinical doc $(loc "$f")"
    elif [ -n "$VETTED" ]; then
      warn L4 "citation '$(loc_detail "$f" "$cid")' in $(loc "$f") does not resolve to any Vetted reference-library entry — a paper not yet in the library (open and verify it, then add it) or an invented one (remove it)"
    fi
  done <<< "$DOC_IDS"
done

# ---- L6: source-file naming (YYYY-MM-DD__source__desc.ext, plus README/CAPTURE-GUIDE/.ocr.md/.gitkeep) ----
# fail-closed enumeration (L6; 2026-08-23 audit): `< <(find … 2>/dev/null)` discarded find's exit status,
# so a subtree find could not enter (mode bits dropped by a restore/rsync/cloud client, operator chmod)
# contributed zero entries and zero errors — a mis-named file inside it read as green. Enumerate only
# the dirs that exist (an absent sources/ is a legitimate scaffold state, not an error), capture
# rc, and red the guard when the walk failed.
# A mis-named file is a WARN (2026-10-04: housekeeping must never block care); a walk that could not
# enumerate the tree stays a FAIL.
_l6_list=""; _l6_n=0; _l6_dirs=()
for _d in patients/*/med/sources; do [ -d "$_d" ] && { _l6_dirs+=("$_d"); _l6_n=$((_l6_n+1)); }; done
if [ "$_l6_n" -gt 0 ]; then
  _l6_list="$(find ${_l6_dirs[@]+"${_l6_dirs[@]}"} -type f 2>/dev/null)"; _l6_rc=$?
  [ "$_l6_rc" -eq 0 ] || err L6 "cannot fully enumerate patients/*/med/sources (find rc=$_l6_rc) — an unreadable subtree, L6 blinded (fail closed)"
fi
while IFS= read -r f; do
  [ -z "$f" ] && continue
  b="$(basename "$f")"
  case "$b" in
    README.md|CAPTURE-GUIDE.md|.gitkeep) ;;  # operator-facing helper docs, not evidence — the template ships CAPTURE-GUIDE.md in sources/
    .*) ;;                                  # hidden / OS cruft (.DS_Store, ._*, .Spotlight…) — never evidence, Finder regenerates them
    *.ocr.md) ;;
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]__*__*.*) ;;  # full-date form (the convention)
    [0-9][0-9][0-9][0-9]-[0-9][0-9]__*__*.*) ;;             # month-precision when the day is unknown
    *) warn L6 "source file not date-named: $(loc "$f")" ;;   # a naming slip, not a care risk: warn, stay green
  esac
done <<< "$_l6_list"

# ---- L7: moving-date single-source-of-truth (the moving-date misattribution incident; ADR-0025) ----
# OPT-IN per doc: a canonical doc that declares an open-items block (the OPEN-ITEMS markers around the
# profile's `## Open items` table) subjects itself to L7; a doc WITHOUT the block is untouched. On an
# adopting doc L7 asserts: NO bare future date (YYYY-MM-DD, strictly > today, as defined below) in the LIVE body —
# moving dates live only in the table, and elsewhere an item is referred to in words. This is the
# rule the incident violated (a future date copied onto the wrong condition row).
# The block must hold a markdown table (a header row, then a separator row). An intact EMPTY table is
# green — it is what the profile template ships; a BEGIN without its END, or a block with no table,
# is a loud fail, never a silent skip (ADR-0021).
# The "## Change log" section is EXCLUDED: it is append-only history that legitimately records dates as
# they were known; policing it would force editing history.
# Boundary moving-vs-historical = strictly future (date > today): historical dates can't move and are
# left as stated; strict-> dodges a host/sandbox midnight off-by-one. Lexicographic compare is
# chronological for YYYY-MM-DD (no date -d/-v: the BSD/GNU trap). Host-portable (ADR-0020): glob/awk/
# grep/parameter-expansion only — no bash-4 array reads, GNU find flags, or date math.
# "Today" is the LATER of the UTC and the local date: an operator east of UTC writes their own today
# (a "Last reviewed" line) hours before UTC reaches it, and that is not a future date. West of UTC the
# UTC date is already the later one. A date past both is still caught.
L7NOW="$(date -u +%F)"; L7LOC="$(date +%F)"
[ "$L7LOC" \> "$L7NOW" ] && L7NOW="$L7LOC"
for f in ${CANON[@]+"${CANON[@]}"}; do
  [ -f "$f" ] || continue
  LC_ALL=C grep -aqF 'OPEN-ITEMS:BEGIN' "$f" || continue    # opt-in: no block → L7 does not apply
  LC_ALL=C grep -aqF 'OPEN-ITEMS:END' "$f" || { err L7 "$(loc "$f") has OPEN-ITEMS:BEGIN but no :END (unclosed open-items block)"; continue; }
  # coverage tripwire (fail-closed): a header row, then a separator row — nothing else is required
  # Bytes: under a UTF-8 locale, a byte that is not UTF-8 makes awk quit and print the rest of the line on
  # stderr, which would show whatever the line holds. The header test alone keeps the locale, so that a
  # header in another alphabet still counts as words.
  L7_TBL="$(LC_ALL=C awk '/OPEN-ITEMS:BEGIN/{i=1;next} /OPEN-ITEMS:END/{i=0} i' "$f" 2>/dev/null)"; l7_rc=$?
  if [ "$l7_rc" -ne 0 ]; then
    err L7 "$(loc "$f") has an open-items block that could not be parsed — L7 blinded"; continue
  fi
  L7_TBL="$(printf '%s\n' "$L7_TBL" | LC_ALL=C grep -aE '^[[:space:]]*\|')"
  if ! printf '%s\n' "$L7_TBL" | LC_ALL=C sed -n '1p' | grep -aqE '[[:alnum:]]' 2>/dev/null \
     || ! printf '%s\n' "$L7_TBL" | LC_ALL=C sed -n '2p' | LC_ALL=C grep -aqE '^[[:space:]]*\|[[:space:]:|-]*-[[:space:]:|-]*$'; then
    err L7 "$(loc "$f") declares an open-items block without a markdown table (header row + separator row) — L7 blinded"; continue
  fi
  # live body = outside the open-items block AND before "## Change log" (history excluded)
  L7_BODY="$(LC_ALL=C awk '/OPEN-ITEMS:BEGIN/{i=1;next} /OPEN-ITEMS:END/{i=0;next} /^## Change log/{c=1} (i==0 && c==0)' "$f" 2>/dev/null)"; l7_rc=$?
  if [ "$l7_rc" -ne 0 ]; then
    err L7 "$(loc "$f") has a body that could not be parsed — L7 blinded"; continue
  fi
  while IFS= read -r d; do
    [ -z "$d" ] && continue
    [ "$d" \> "$L7NOW" ] || continue                          # strictly-future only
    err L7 "$(loc "$f"): bare future date '$(loc_detail "$f" "$d")' in body — a moving date belongs ONLY in the open-items table; refer to the item in words"
  done < <(printf '%s\n' "$L7_BODY" | LC_ALL=C grep -aoE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort -u)
done

# ---- Handout ID check character (ADR-0033): Crockford base-32, positional-weighted mod-32 ----
# The CANONICAL definition — this guard is the reference implementation, and
# tools/handout_attest/handout_id.py its Python twin, cross-tested in test_attest.py. Over
# the 6-char payload <PPP><NNN> (uppercase; PPP three Crockford symbols, NNN three digits) and the 32-symbol
# Crockford alphabet A (index = value; I L O U removed), the check char is
#     A[ ( Σ value(char_i) * w_i ) mod 32 ],   w = 1 3 5 7 9 11  (left→right).
# All weights are ODD (units mod 32), so EVERY single-symbol substitution changes the checksum — the common
# read-aloud misread. Adjacent transposition of two symbols is caught unless their values differ by exactly
# 16 (an inherent mod-32 linear-code limitation: one check symbol over a composite modulus cannot fully
# cover both error classes — the residual is documented + accepted in ADR-0033 as a read-aloud aid, not
# integrity crypto). HOST-PORTABLE (ADR-0020): parameter-expansion index + integer arithmetic, no externals.
tab_checkchar(){ # $1 = PPP+NNN (6 uppercase Crockford chars) → echo the expected check char ('?' if a char is invalid)
  local A='0123456789ABCDEFGHJKMNPQRSTVWXYZ' s=0 i c v; local -a w=(1 3 5 7 9 11)
  for ((i=0; i<${#1}; i++)); do
    c="${1:i:1}"; v="${A%%"$c"*}"; v="${#v}"     # index of c in A (== 32 when c is not a Crockford symbol)
    [ "$v" -ge 32 ] && { printf '?'; return 1; }
    s=$(( s + v * ${w[i]} ))
  done
  printf '%s' "${A:$(( s % 32 )):1}"
}

# ---- L8: handout-file naming (YYYY-MM-DD__handout-<audience>__<slug>[__TAB-<PPP>-<NNN><C>[.rREV]].<ext>) ----
# The output layer the patient/clinician actually receives — a mis-named file ships a mis-titled document
# (the pre-ADR-0026 drift). Audience is patient|clinician; ANY extension passes (the .md source and its
# rendered .pdf/.docx share the stem). Exempts the operator-facing INDEX.md/README.md and OS/editor cruft,
# exactly like L6. Skeleton-safe: a patient-free tree has no handouts, so the loop runs zero times.
# ADR-0033: the trailing __TAB-<PPP>-<NNN><C>[.rREV] identifier segment is OPTIONAL — a file WITHOUT it stays
# green (grandfathered; the rollout is forward-only, files are never renamed). When __TAB- IS present it must
# be well-formed (Crockford PPP + 3-digit NNN + Crockford check char [+ optional .rN]) AND the check
# character must validate — a typo'd ID on a document handed to a clinician is the exact read-aloud failure
# the check char exists to catch. Fail-closed: a present-but-unparseable segment reds, never passes silently.
# fail-closed enumeration (L8; 2026-08-23 audit): `< <(find … 2>/dev/null)` discarded find's exit status,
# so a subtree find could not enter (mode bits dropped by a restore/rsync/cloud client, operator chmod)
# contributed zero entries and zero errors — a mis-named file inside it read as green. Enumerate only
# the dirs that exist (an absent handouts/ is a legitimate scaffold state, not an error), capture
# rc, and red the guard when the walk failed.
_l8_list=""; _l8_n=0; _l8_dirs=()
for _d in patients/*/med/handouts; do [ -d "$_d" ] && { _l8_dirs+=("$_d"); _l8_n=$((_l8_n+1)); }; done
if [ "$_l8_n" -gt 0 ]; then
  _l8_list="$(find ${_l8_dirs[@]+"${_l8_dirs[@]}"} -type f 2>/dev/null)"; _l8_rc=$?
  [ "$_l8_rc" -eq 0 ] || err L8 "cannot fully enumerate patients/*/med/handouts (find rc=$_l8_rc) — an unreadable subtree, L8 blinded (fail closed)"
fi
while IFS= read -r f; do
  [ -z "$f" ] && continue
  b="$(basename "$f")"
  case "$b" in
    *.factcheck.md) continue ;;               # ADR-0034 QA sidecar, not a handout (L4 skips it too); its
                                              # <stem>.factcheck.md name inherits the handout's __TAB- segment
                                              # and would otherwise false-trip the ID-segment regex below
    *.attest.json) continue ;;                # ADR-0039 build attestation — same two-dot-extension trap as
                                              # .factcheck.md (the single-extension regex tail can't match it);
                                              # verified by L15, not a handout the reader receives
    INDEX.md|README.md|.gitkeep) continue ;;  # operator-facing registry/readme, not a handout
    .*) continue ;;                            # hidden / OS cruft (.DS_Store, ._*) — never a handout
  esac
  case "$b" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]__handout-patient__*) ;;
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]__handout-clinician__*) ;;
    *) err L8 "handout file not canonically named (YYYY-MM-DD__handout-<audience>__<slug>): $(loc "$f")"; continue ;;
  esac
  # optional trailing ID segment: validate shape + check char when present; grandfather when absent
  case "$b" in
    *__TAB-*)
      # regex held in a var (bash-3.2 =~ quoting trap: an inline quoted regex matches literally). The
      # Crockford class [0-9A-HJKMNP-TV-Z] excludes I L O U by construction, so a bad letter fails shape.
      _re='^[0-9]{4}-[0-9]{2}-[0-9]{2}__handout-(patient|clinician)__.+__TAB-([0-9A-HJKMNP-TV-Z]{3})-([0-9]{3})([0-9A-HJKMNP-TV-Z])(\.r[0-9]+)?\.[A-Za-z0-9]+$'
      if [[ "$b" =~ $_re ]]; then
        _exp="$(tab_checkchar "${BASH_REMATCH[2]}${BASH_REMATCH[3]}")"
        [ "${BASH_REMATCH[4]}" = "$_exp" ] || err L8 "handout ID check character invalid (got '${BASH_REMATCH[4]}', expected '$_exp') — misread/typo'd ID: $(loc "$f")"
      else
        err L8 "handout ID segment malformed (expected __TAB-<PPP>-<NNN><C>[.rREV]: Crockford PPP/check-char, 3-digit NNN): $(loc "$f")"
      fi ;;
  esac
  # The front-matter `id:` is not read here: the renderer refuses a malformed or wrong one at draft and
  # at seal, before the fact-check gate (B0; ADR-0033 point 8).
done <<< "$_l8_list"

# ---- L10: private-mode identifier residue (ADR-0029) ----
# ADR-0029's core promise — a private-mode patient's operator-designated identifier is NEVER recorded
# anywhere in the tree — made executable. IN SCOPE = a patient whose profile.md carries the private-mode
# marker (the ⟨never-API⟩ tag, which the profile template spells out only in words, so an unfilled
# scaffold is out of scope). For each such patient, scan every TEXT
# file a model may read (profile, medications, analysis, handouts, .ocr.md, nmed — any extension)
# for an identifier-shaped residue — a run in the shapes of the numbers the person's tag names, every
# listed shape with no exact tag (ADR-0062, ADR-0077) — and, while any patient is private-mode,
# the joint `_shared/nmed/` Markdown too (A85). Binaries are OUT of scope by design, and so are the originals
# the read guard withholds from a model (everything in med/_inbox/ and med/sources/ but Markdown and
# `_redacted/`): the untouched originals legitimately hold the identifier and never leave the machine;
# L10 targets the DERIVED text, where a run would mean the redaction discipline failed. A plain shape,
# NOT checksum-validated (an OCR-mangled identifier still ~the identifier fails a checksum yet must
# red; arithmetic has no place in a safety guard; contiguous 11-runs are rare in clinical prose — labs/
# orders carry separators, local phone numbers are shorter). Over-red beats under-red; a verified non-id
# is waived per line with ⟨not-an-id: verified YYYY-MM-DD⟩ (dated, so the exemption reads as a deliberate,
# audited act). SELF-REFERENCE TRAP (check.sh ships): comments stay abstract — "the designated identifier",
# never the scheme name or any real digit; synthetic fixtures live only in selftest.sh. And the guard NEVER
# echoes a match, patient handle, or path (a filename may itself contain the protected identifier).
# FAIL CLOSED (ADR-0021): scope-grep or scan-grep rc≥2 → loud red; the marker present in a patient tree
# with no profile.md anchor to establish scope → loud red; an in-scope patient yielding zero scannable
# files → loud red (never green having examined nothing). Zero private-mode patients is a legitimate state
# → L10 no-ops green (skeleton-safe). HOST-PORTABLE (ADR-0020): glob/find/grep/parameter-expansion, and
# python3 to read a marked person's number tag (without it, that person reds).
L10_MARK='⟨never-API⟩'
L10_WAIVER='⟨not-an-id: verified [0-9]{4}-[0-9]{2}-[0-9]{2}⟩'
# One file: red on a run of the given shape, category only. A binary file reads as no match (grep -I). Not residue:
# a line with the dated waiver; digits inside an integrity key — a hex digest of 32, 40 or 64 characters
# with at least one letter, such as the handout digest a sealed unit's fact-check sidecar records (about
# one 64-hex digest in nine holds 11 decimal digits in a row, so sealed handouts would red at random); and
# the redaction tool's opaque document id, `doc-` and 16 hex (a hash of the input; about one in sixty holds
# such a run). A pure-digit run, or one of another length, still counts.
# The shape is the person's: the residue shape of each scheme their profile names (ADR-0062), read
# from the private-mode number list beside the masking tool, through its reader — `l10_shape` below.
l10_scan(){ # file shape
  local hits grc
  # Bytes throughout: under a UTF-8 locale, a byte that is not UTF-8 can hide a number from grep, and
  # makes awk quit and print the rest of the line on stderr, which would show the number and lose the hit.
  hits="$(LC_ALL=C grep -IE -- "$2" "$1" 2>/dev/null)"; grc=$?
  if [ "$grc" -ge 2 ]; then
    err L10 "grep failed while scanning one private-mode text file — L10 is blinded"; return 0
  fi
  [ "$grc" -eq 0 ] || return 0                              # rc=1 → no run of the shape (or a binary file)
  hits="$(printf '%s\n' "$hits" | LC_ALL=C grep -avE "$L10_WAIVER")"
  hits="$(printf '%s\n' "$hits" | LC_ALL=C awk '{ out = ""; s = $0
    while (match(s, /[0-9A-Fa-f]+/)) {
      t = substr(s, RSTART, RLENGTH); pre = out substr(s, 1, RSTART - 1)
      if ((RLENGTH == 32 || RLENGTH == 40 || RLENGTH == 64) && t ~ /[A-Fa-f]/) t = " "
      else if (RLENGTH == 16 && substr(pre, length(pre) - 3) == "doc-") t = " "
      out = pre t; s = substr(s, RSTART + RLENGTH) }
    print out s }' 2>/dev/null)"; grc=$?
  if [ "$grc" -ne 0 ]; then
    err L10 "the residue scan could not parse one private-mode text file (locator withheld) — L10 is blinded"; return 0
  fi
  hits="$(printf '%s\n' "$hits" | LC_ALL=C grep -aE -- "$2")"
  if [ -n "$hits" ]; then
    err L10 "identifier-shaped residue in one private-mode text file (locator withheld) — must never be recorded (ADR-0029)"
  fi
}
# A marked profile's schemes (ADR-0062, ADR-0073), read with this check.sh's number list by
# tools/private-mode/id_schemes.py, which prints an outcome code and the person's union shape, never a line.
# Only the exact tag decides (ADR-0077): no tag read means every row of the list is searched. A tag of the
# key `unlisted` alone (a number not on the list, covered by hand) names no shape: L10_SHAPE is empty and the
# person's text is not searched. A mistyped tag on a marker line reds; in the Identity section a tag on
# another line reds as misplaced. An unreadable list reds only here, for a marked person. Sets L10_SHAPE, or
# reds and returns 1. Without python3 the tag cannot be read, so L10 reds.
l10_shape(){ # profile
  local res arc nl='
'
  res="$(python3 "$SELF_ROOT/tools/private-mode/id_schemes.py" "$1" 2>/dev/null)"; arc=$?
  case "$arc:$res" in
    0:NOTLISTED) L10_SHAPE=""; return 0 ;;
    "0:TAG "*"${nl}SHAPE "?*) L10_SHAPE="${res#*${nl}SHAPE }"; return 0 ;;
    0:LIST) err L10 "the private-mode number list is missing, malformed or unreadable — L10 is blinded"; return 1 ;;
    0:MISPLACED)
      err L10 "the private-mode number tag is in one profile's Identity section but not on the line carrying the private-mode marker (locator withheld) — move it onto that line"; return 1 ;;
    0:REPEATED)
      err L10 "the private-mode number tag appears more than once on the private-mode line in one profile (locator withheld) — keep one"; return 1 ;;
    0:MALFORMED)
      err L10 "the private-mode number tag is malformed in one profile (locator withheld) — the form is ⟨id-scheme KEY⟩ or ⟨id-scheme KEY,KEY⟩"; return 1 ;;
    0:UNKNOWN)
      err L10 "the private-mode number tag in one profile names a scheme the number list does not know (locator withheld) — choose the intended key from the number list; if the number is not on it, use the key unlisted, name its issuing country in words, and cover it by hand before scanning"; return 1 ;;
    *) err L10 "the private-mode number tag could not be read in one profile (locator withheld) — L10 is blinded (python3 missing or not running — see tools/private-mode/check-setup.sh)"; return 1 ;;
  esac
}
L10_SHARED_SHAPE=""
# Is this path (relative to a private-mode person's folder) left out of L10? Names are case-folded the
# way the read guard folds them: the originals in med/_inbox/ and med/sources/ (all but Markdown and
# `_redacted/`), the pipeline's id-to-name map and an identity file of kept details, which no model reads; and the
# ownership ledger's own files (MANIFEST, its checkpoint, lock and interrupted-write temporaries).
l10_skip(){ # rel
  case "$1" in
    med/MANIFEST|med/MANIFEST.checkpoint|med/MANIFEST.lock|med/MANIFEST.tmp-*|med/MANIFEST.checkpoint.tmp-*) return 0 ;;
  esac
  case "${1##*/}" in
    .[nN][eE][vV][eE][rR]-[aA][pP][iI]-[sS][oO][uU][rR][cC][eE]-[mM][aA][pP].[jJ][sS][oO][nN]) return 0 ;;
    *.[nN][eE][vV][eE][rR]-[aA][pP][iI]-[iI][dD][eE][nN][tT][iI][tT][yY].[jJ][sS][oO][nN]) return 0 ;;
  esac
  case "$1" in
    [mM][eE][dD]/_[iI][nN][bB][oO][xX]/*|[mM][eE][dD]/[sS][oO][uU][rR][cC][eE][sS]/*)
      case "$1" in *.[mM][dD]|*/_[rR][eE][dD][aA][cC][tT][eE][dD]/*) return 1 ;; esac
      return 0 ;;
  esac
  return 1
}
L10_ANY_PRIVATE=no
for d in patients/*/; do
  [ -d "$d" ] || continue                                  # unmatched glob → literal token → skip
  prof="${d}profile.md"
  if [ -L "$prof" ]; then
    err L10 "profile.md anchor is symlinked (locator withheld) — cannot establish private-mode scope"
    continue
  elif [ -f "$prof" ]; then
    LC_ALL=C grep -qF "$L10_MARK" "$prof" 2>/dev/null; mrc=$?
    if [ "$mrc" -ge 2 ]; then
      err L10 "scope detection blinded: grep failed for one profile — cannot establish private-mode status"; continue
    fi
    [ "$mrc" -eq 0 ] || continue                            # no marker → not private-mode → out of L10 scope
    L10_ANY_PRIVATE=yes
    l10_shape "$prof" || continue
    [ -z "$L10_SHAPE" ] || case "|$L10_SHARED_SHAPE|" in *"|$L10_SHAPE|"*) ;; *) L10_SHARED_SHAPE="${L10_SHARED_SHAPE:+$L10_SHARED_SHAPE|}$L10_SHAPE" ;; esac
  else
    # Never recursively grep an unclassified tree: grep can block on a FIFO and silently normalize a
    # traversal error into "no match". First reject a wrong-type profile and any linked/special node;
    # then prove regular-Markdown discovery succeeds and inspect only those regular files.
    if [ -e "$prof" ] || [ -L "$prof" ]; then
      err L10 "profile.md anchor exists but is not a real regular file (locator withheld) — cannot establish private-mode scope"
      continue
    fi
    l10_bad_nodes="$(find "$d" \
      \( -type l -o -type b -o -type c -o -type p -o -type s \) -print 2>/dev/null)"; l10_brc=$?
    if [ "$l10_brc" -ne 0 ]; then
      err L10 "cannot inspect one profile-less patient tree for linked/special nodes — scope discovery is blinded"
      continue
    elif [ -n "$l10_bad_nodes" ]; then
      err L10 "linked or special node exists in one profile-less patient tree (locator withheld) — scope discovery is unsafe"
      continue
    fi
    l10_missing_files="$(find "$d" -type f -name '*.md' -print 2>/dev/null)"; l10_frc=$?
    if [ "$l10_frc" -ne 0 ]; then
      err L10 "cannot enumerate one profile-less patient tree's Markdown — scope discovery is blinded"
      continue
    fi
    l10_marker_found=no
    l10_marker_error=no
    while IFS= read -r l10_mf; do
      [ -n "$l10_mf" ] || continue
      LC_ALL=C grep -qF "$L10_MARK" "$l10_mf" 2>/dev/null; l10_mrc=$?
      [ "$l10_mrc" -eq 0 ] && l10_marker_found=yes
      [ "$l10_mrc" -ge 2 ] && l10_marker_error=yes
    done <<EOF
$l10_missing_files
EOF
    if [ "$l10_marker_error" = yes ]; then
      err L10 "cannot scan one profile-less patient tree's Markdown — scope discovery is blinded"
    elif [ "$l10_marker_found" = yes ]; then
      err L10 "private-mode marker present in a patient tree without a profile.md anchor — cannot establish scope (fail-closed)"
    fi
    continue
  fi
  # `find -type f` neither follows nor reports a symlinked directory. In private mode that creates a
  # silent hole where model-bound text remains reachable from the patient tree but is never scanned.
  # Reject every symlink in the in-scope tree. ONE walk lists symlinks and files, so its status covers
  # the very list that is scanned (a failed listing never reads as clean); paths are never printed.
  l10_list="$(find "$d" \( -type l -o -type f \) -print 2>/dev/null)"; l10_lrc=$?
  if [ "$l10_lrc" -ne 0 ]; then
    err L10 "cannot list one private-mode patient tree — L10 is blinded"; continue
  fi
  l10_link=no
  while IFS= read -r f; do [ -n "$f" ] && [ -L "$f" ] && { l10_link=yes; break; }; done <<EOF
$l10_list
EOF
  if [ "$l10_link" = yes ]; then
    err L10 "symlink exists in one private-mode patient tree (locator withheld) — L10 cannot prove complete text coverage"; continue
  fi
  # in-scope: every text file a model may read (portable; ADR-0020); `l10_skip` names what is left out.
  # The extension-less MANIFEST is not scanned by this shell layer: a plain \d{11} scan over it collides
  # with its sha256/person-id/record-id HEX fields (a 64-hex digest routinely contains an 11-digit run) →
  # an unwaivable false RED. The correct
  # scan is over the source_relpath / identity_source fields ONLY (excluding hashes); L13's field-aware
  # parser performs it, including `_shared/med` prose, whenever any private-mode patient exists.
  L10F=()
  while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    l10_rel="${f#"$d"}"; l10_rel="${l10_rel#/}"             # BSD find doubles the slash after "$d"
    l10_skip "$l10_rel" || L10F+=("$f")
  done <<EOF
$l10_list
EOF
  if [ "${#L10F[@]}" -eq 0 ]; then
    err L10 "one private-mode patient has 0 scannable text files — L10 examined nothing (fail-closed)"; continue
  fi
  [ -z "$L10_SHAPE" ] || for f in ${L10F[@]+"${L10F[@]}"}; do l10_scan "$f" "$L10_SHAPE"; done   # unlisted alone: no shape
done
# Shared notes are scanned for the shapes successfully read from private-mode profiles.
# If none could be read, skip this residue scan: the board is already red.
# _shared/nmed/: while any patient is private-mode, the joint non-medical lane's Markdown is
# scanned the same way — whose it is cannot be established, so findings stay category-only. Other files
# there are originals of joint matters, not prose; `_shared/med/` is L13's (its shape rule and prose scan).
if [ "$L10_ANY_PRIVATE" = yes ]; then
  if [ -z "$L10_SHARED_SHAPE" ]; then
    :                                                      # no person shape read: red above, or no number on the list
  elif [ -L _shared/nmed ]; then
    err L10 "_shared/nmed is a symlink while private mode is in use — L10 cannot prove its prose is clean"
  elif [ -d _shared/nmed ]; then
    l10_list="$(find _shared/nmed \( -type l -o -type f -iname '*.md' \) -print 2>/dev/null)"; l10_lrc=$?
    l10_link=no
    while IFS= read -r f; do [ -n "$f" ] && [ -L "$f" ] && { l10_link=yes; break; }; done <<EOF
$l10_list
EOF
    if [ "$l10_lrc" -ne 0 ]; then
      err L10 "cannot list _shared/nmed while private mode is in use — L10 is blinded"
    elif [ "$l10_link" = yes ]; then
      err L10 "symlink inside _shared/nmed while private mode is in use (locator withheld) — L10 cannot prove its prose is clean"
    else
      while IFS= read -r f; do [ -n "$f" ] && [ -f "$f" ] && l10_scan "$f" "$L10_SHARED_SHAPE"; done <<EOF
$l10_list
EOF
    fi
  fi
fi
# L10, the session read-guard (ADR-0029 point 12): a person marked private mode, or holding masked output
# (a `_redacted` folder), in a tree whose `.claude/settings.local.json` does not name the read-guard hook. That
# hook is what stops a session reading an unmasked original, and the untracked settings file is what a fresh
# checkout, a restore or a hand edit loses. WARN, never red: a machine that wires its hooks another way is not
# blocked, and the answer is one idempotent command. Category only: no handle, no path of a person. Exact
# token only: the hook script's own name in the settings file. Which tools its matcher covers is selftest's.
L10_RG_NEED="$L10_ANY_PRIVATE"
for d in patients/*/; do
  [ -d "${d}_redacted" ] && L10_RG_NEED=yes
done
if [ "$L10_RG_NEED" = yes ] && ! { [ -f .claude/settings.local.json ] && LC_ALL=C grep -qF 'tools/claude-hooks/registry-read-guard.py' .claude/settings.local.json 2>/dev/null; }; then
  warn L10 "a person here is in private mode or holds masked output, but the session read-guard is not wired in .claude/settings.local.json — nothing stops a session reading an unmasked original; run: bash checks/install-instance.sh care (idempotent)"
fi
# python3 runs the L10 kept-details scan and the L13/L15 verifiers; TABULARIUM_TEST_NO_PYTHON=1 is how the bite suite
# takes it away. py_people: any person entry under patients/ — without python3, L13 and L15 red on one.
HAVE_PY3=no
[ "${TABULARIUM_TEST_NO_PYTHON:-0}" != "1" ] && command -v python3 >/dev/null 2>&1 && HAVE_PY3=yes
py_people(){ local p; for p in patients/*; do { [ -d "$p" ] || [ -L "$p" ]; } && return 0; done; return 1; }

# L10, kept details (ADR-0029 control C2, ADR-0075): for a private-mode person with an identity file,
# the kept values in it — whole names in either order, the date of birth in its printed forms, phone
# and document digit runs, the street with its number — must not stand in the profile or medications,
# nor in any other *.md named, or (a transcription) filed, on or after the day that value was
# recorded; nmed/ never. The identity file is read by the local tool only; output is category-only,
# locators withheld; L10's dated waiver applies. FAIL CLOSED: an identity file without the marker, an
# unreadable ledger, or a placeholder in the profile or medications with the identity file missing
# reds; without python3, either sign reds. An identity file or a placeholder wakes the scan, so a lost
# file reds instead of switching the scan off.
L10V2_ANY=no
for d in patients/*/; do
  if [ -e "${d}.never-api-identity.json" ] || [ -L "${d}.never-api-identity.json" ]; then L10V2_ANY=yes; break; fi
  for l10v2_f in "${d}profile.md" "${d}medications.md"; do
    [ -f "$l10v2_f" ] || continue
    LC_ALL=C grep -qF '⟨withheld:' "$l10v2_f" 2>/dev/null; l10v2_grc=$?
    [ "$l10v2_grc" -eq 1 ] || { L10V2_ANY=yes; break 2; }     # a match, or grep could not tell
  done
done
if [ "$L10V2_ANY" = yes ]; then
  if [ "$HAVE_PY3" = yes ]; then
    L10V2_OUT="$(cd "$SELF_ROOT" && python3 tools/private-mode/identity.py --root "$ROOT" scan 2>&1)"; L10V2_RC=$?
    if [ "$L10V2_RC" -eq 1 ]; then
      while IFS= read -r l10v2_line; do
        [ -n "$l10v2_line" ] && err L10 "$l10v2_line"
      done <<EOF
$L10V2_OUT
EOF
    elif [ "$L10V2_RC" -ne 0 ]; then
      err L10 "the kept-details residue scan could not run (exit $L10V2_RC) — L10 is blinded for persons with kept details (fail closed)"
    fi
  else
    err L10 "python3 not on PATH but a person has kept details (an identity file or a placeholder) — the residue scan cannot run (fail closed)"
  fi
fi

# ---- L13: person-ownership binding (ADR-0037) ----
# Makes mechanically-detectable wrong-person filing LOUD: every source under a patient's med/sources/**
# must have an active MANIFEST record, its bytes must match the recorded sha256, its person_record_id
# must match profile.md, its 1:1 .ocr.md derivative must bind, paths must be safe (no symlink/escape/
# non-NFC), the append-only ledger must match its untracked MANIFEST.checkpoint, and _shared/med/ may
# hold only .md prose. L13 proves METADATA/HASH consistency ONLY — the identity judgment stays
# operator/intake provenance (no vision, no real-name registry; ADR-0028). The schema/graph logic lives
# in ONE place — the stdlib tools/person_ownership package (JSONL nesting is past awk's reach) — invoked
# here fail-closed, never duplicated in shell. LEAN MVP (operator choice): bundle-chains and cross-root
# evidence-duplicate detection are a deferred v2 (ADR-0037 §9). Findings name the file under
# the locator rule above; person_record_id and source hashes never print. FAIL CLOSED (ADR-0021): a RED verdict,
# an internal verifier error, or —
# when python3 is absent — any person entry, or anything in _shared/med → loud red. Zero-patient skeleton
# → green. Skeleton-safe: the package ships (publish ALLOW-list) and
# resolves via PEP-420 there, exactly like tools/private-mode (ADR-0029).
if [ "$HAVE_PY3" = yes ]; then
  # Load the verifier package from where THIS check.sh lives (its own repo/skeleton), not from the
  # tree being verified — so check.sh can lint any --root (e.g. a selftest fixture that ships no
  # tools/) with its own guard logic. $0's dir is checks/; its parent holds tools/person_ownership.
  # RUN FROM the package root (subshell cd to $SELF_ROOT — resolved pre-cd at the top), don't just
  # PYTHONPATH it: `python3 -m` prepends the CURRENT dir to sys.path, and `tools/__init__.py` makes
  # `tools` a REGULAR package — so when check.sh lints a DIFFERENT tree (worktree↔main), the linted
  # tree's own tools/ silently shadows this check.sh's copy and a package present only here is
  # "No module named …" (found 2026-07-17 building L15; the same latent shadowing sat in L13,
  # masked while both copies were identical).
  L13_OUT="$(cd "$SELF_ROOT" && python3 -m tools.person_ownership --root "$ROOT" verify 2>&1)"; L13_RC=$?
  if [ "$L13_RC" -ne 0 ]; then
    printf '%s\n' "$L13_OUT"
    err L13 "person-ownership verification RED (ADR-0037) — resolve the finding(s) above"
  fi
else
  # No python3: fail closed on any person entry, or on anything in _shared/med — a shared-lane original
  # (or a symlinked or wrong-type _shared root) still reds before any person folder is back.
  l13_sh=""; l13_src=0
  if [ -L _shared ] || [ -L _shared/med ] || { [ -e _shared ] && [ ! -d _shared ]; } || { [ -e _shared/med ] && [ ! -d _shared/med ]; }; then
    l13_sh=yes
  elif [ -d _shared/med ]; then
    l13_sh="$(find _shared/med -mindepth 1 -print 2>/dev/null)"; l13_src=$?
  fi
  if py_people || [ -n "$l13_sh" ] || [ "$l13_src" -ne 0 ]; then
    err L13 "python3 not on PATH but person records are present — L13 cannot verify them (fail closed); install Python 3.9 or newer"
  fi
fi

# ---- L15: sealed-handout byte binding (ADR-0039) ----
# Binds the bytes a patient/clinician actually receives to the fact-checked Markdown: every sealed
# encounter unit (handouts/<audience>/<YYYY-MM-DD-slug>/) must carry a <stem>.attest.json whose
# md/factcheck/output SHA-256s match current bytes; orphans/conflicts/phantom dirs/root strays red;
# products never share bytes with the evidence lane (med/sources/**); flat + archive/ legacy files
# are QUEUED (deferred per-patient migration) while the person's .legacy-frozen inventory lists them
# with unchanged bytes — a missing or malformed inventory, a new file in that lane or changed bytes
# red (ADR-0039 A6). An encounter dir holding Markdown (and its
# sidecar) with no attestation and no output is a draft awaiting its seal, never red (ADR-0039 A7).
# L15 proves byte binding + lane separation ONLY — the content verdict is the fact-check the
# renderer's seal gate demands (ADR-0034). Logic lives in ONE
# place — the stdlib tools/handout_attest package (JSON is past awk's reach — the L13 pattern) —
# invoked fail-closed, never duplicated in shell. Findings name the file under the locator rule
# above (never a hash). Zero-patient skeleton / scaffolded person → no-op green. FAIL CLOSED (ADR-0021): a RED
# verdict, an internal verifier error, or — python3 absent — any person entry → loud red.
if [ "$HAVE_PY3" = yes ]; then
  # Same loading rule as L13: the verifier comes from where THIS check.sh lives ($SELF_ROOT), the
  # tree being verified is $ROOT — subshell-cd, not PYTHONPATH (see L13's shadowing note).
  L15_OUT="$(cd "$SELF_ROOT" && python3 -m tools.handout_attest --root "$ROOT" verify 2>&1)"; L15_RC=$?
  if [ "$L15_RC" -ne 0 ]; then
    printf '%s\n' "$L15_OUT"
    err L15 "sealed-handout verification RED (ADR-0039) — resolve the finding(s) above"
  else
    # green: SURFACE a non-empty legacy queue (ADR-0039 §6 — the queue is visible until it shrinks
    # to zero; red-team 2026-07-17: discarding the green summary made queue growth silent)
    case "$L15_OUT" in
      *"legacy queue empty."*) : ;;
      *) printf '%s\n' "$L15_OUT" ;;
    esac
  fi
else
  py_people && err L15 "python3 not on PATH but person records are present — L15 cannot verify them (fail closed); install Python 3.9 or newer"
fi

# ---- L20: instance shape — the mode is DERIVED from the records, the marker only ASSERTS it (ADR-0050) ----
# ADR-0050 Part B splits this system into two instances: DEV (the product — tooling, templates,
# guards, ADRs, the eval; it never holds a record) and CARE (a pull-only checkout of DEV at a release
# tag, plus the record directories that are never committed anywhere). L20 is what keeps them apart,
# and it deliberately does NOT let the marker file decide: an earlier draft had `.tabularium-instance`
# SELECT the mode, which fails open in the dangerous direction — a DEV tree mis-marked `care` would
# have silenced the one check keeping records out (ADR-0050 Part B, L20). So the OBSERVABLE decides.
# `checks/RECORD-SET` names every non-product path once; their presence on disk derives the mode; the
# marker is only an assertion that must agree with it. That same list is checked against `.gitignore`
# (the ALLOW/.gitignore mirror discipline, kept for the one list that survives the split).
# FAIL CLOSED: a marker with no record set, an unparseable set, an entry git does not ignore, or a
# scan that errors is a red — never a silent pass. There is exactly ONE green-without-checking branch:
# a tree carrying NEITHER a marker NOR a record set (the published skeleton, the skeleton CI, and every
# synthetic selftest fixture), and it says so out loud.
# A LINKED WORKTREE has neither input of its own (both are untracked, and untracked files are
# per-tree), so the instance is a property of the CHECKOUT FAMILY: step (2b) reads the marker and
# step (5b) the observable from the MAIN checkout, and this tree is still required to be record-free
# in its own right (ADR-0050 point 7).
# Output: record CATEGORIES, RECORD-SET entry paths, and shape-scan hits named under the locator
# rule (`loc`, top of file). The main checkout's own absolute path is never printed.
L20_SET="checks/RECORD-SET"
L20_MARK=".tabularium-instance"
L20_PROBE=".record-set-drift-probe"     # synthetic child; only ever a `git check-ignore` argument
# Tooling-SHAPED records: listed `record` so L19 tolerates them, but a tree holding only these is not
# a records tree (untracked machinery that a DEV instance legitimately has none of). The publish
# script left this list on 2026-09-06 — it holds no token any more and is tracked product, so it is
# not a `record` entry at all. Kept as a LIST, not folded away: the next per-instance untracked file
# that is machinery rather than a record belongs here, and the pre-push hook mirrors it (SHAPED).
L20_SHAPED="checks/OFFSITE-DEST"
L20_MODE=""                             # derived mode; '' means L19 below does not run
_l20fired=0
l20_err(){ err L20 "$1"; _l20fired=1; }
# git, with the inherited git environment STRIPPED. check.sh runs from the ADR-0022 pre-commit hook,
# which exports GIT_DIR/GIT_INDEX_FILE; those OVERRIDE discovery, so an unstripped `git` in a linted
# FIXTURE tree would answer about the REAL repository (the 2026-07-19 incident that flipped core.bare).
l20_git(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY git "$@"; }
# YYYY-MM-DD -> days since the epoch (Hinnant's days_from_civil), in pure arithmetic; L19's break-glass
# window below calls it. `date -d` is GNU-only and `date -v` is BSD-only, so neither can compare two
# dates on both substrates (ADR-0020).
l20_days(){
  local s="$1" y m d yy era yoe doy doe rt
  case "$s" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;; *) return 1 ;; esac
  y=$((10#${s:0:4})); m=$((10#${s:5:2})); d=$((10#${s:8:2}))
  [ "$m" -ge 1 ] && [ "$m" -le 12 ] && [ "$d" -ge 1 ] && [ "$d" -le 31 ] || return 1
  # CIVIL validity, not merely well-formedness. days_from_civil below NORMALIZES an impossible day
  # rather than rejecting it — 2026-02-30 becomes 2026-03-02 — so an impossible date used to be
  # accepted and then compared as a date two days later than the one written (review round 4, F7).
  # Round-trip the input through date(1) and demand the same bytes back: BSD `-j -f` first, GNU `-d`
  # second (neither exists on both substrates — ADR-0020), both pinned to TZ=UTC so a zone whose DST
  # transition skips local midnight cannot shift a legitimate date. FAIL CLOSED: on a host with
  # neither arm nothing round-trips, so no date parses at all and every caller reds.
  rt="$(TZ=UTC date -j -f '%Y-%m-%d' "$s" '+%Y-%m-%d' 2>/dev/null)" || rt=""
  if [ -z "$rt" ]; then rt="$(TZ=UTC date -d "$s" '+%Y-%m-%d' 2>/dev/null)" || rt=""; fi
  [ "$rt" = "$s" ] || return 1
  yy=$(( m <= 2 ? y - 1 : y ))
  era=$(( (yy >= 0 ? yy : yy - 399) / 400 ))
  yoe=$(( yy - era * 400 ))
  doy=$(( (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1 ))
  doe=$(( yoe * 365 + yoe / 4 - yoe / 100 + doy ))
  printf '%s\n' $(( era * 146097 + doe - 719468 ))
}

# (1) the marker: present? exactly one line? which of the two shapes?
l20_marker=""; l20_marker_present=0; l20_marker_bad=0
if [ -e "$L20_MARK" ] || [ -L "$L20_MARK" ]; then
  l20_marker_present=1
  if [ -L "$L20_MARK" ] || [ ! -f "$L20_MARK" ] || [ ! -r "$L20_MARK" ]; then
    l20_marker_bad=1
  else
    l20_mraw="$(tr -d '\r' < "$L20_MARK" | sed '/^[[:space:]]*$/d')"
    l20_mcnt="$(printf '%s\n' "$l20_mraw" | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')"
    l20_marker="$(printf '%s\n' "$l20_mraw" | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [ "$l20_mcnt" = "1" ] || l20_marker_bad=1
  fi
fi

# (2) can we ask git anything about THIS tree? (used by the ignore-mirror check and by L19)
# `.gitignore` presence is deliberately NOT folded in here: it is what the ignore-mirror check reads,
# not what makes git usable, and conflating them made a CARE tree with a deleted .gitignore report
# "not a usable git checkout" — the wrong diagnosis for the more dangerous fault.
l20_git_ok=0; l20_git_why=""
if ! command -v git >/dev/null 2>&1; then l20_git_why="git not installed"
elif [ ! -e .git ]; then l20_git_why="no .git at the linted root"
elif ! l20_git rev-parse --is-inside-work-tree >/dev/null 2>&1; then l20_git_why="not a git work tree"
elif [ "$(l20_git rev-parse --is-inside-work-tree 2>/dev/null)" = false ]; then
  # rc 0 but "false": `core.bare` is true, the state a fixture once wrote into the shared git config
  # (2026-07-06). Nothing git says about this tree then holds — `ls-files` lists nothing — so red
  # once, with the fix, rather than reading it as a work tree (review 2026-10-25).
  l20_git_why="git reports a bare repository"
  l20_err "git reports this checkout as bare (core.bare is true, in this tree's git config or the shared one) — nothing git says about it can be checked; set it back with: git config core.bare false (fail closed)"
elif [ -n "$(l20_git rev-parse --show-prefix 2>/dev/null)" ]; then l20_git_why="not at the top level of the work tree"
else l20_git_ok=1
fi

# (2b) a LINKED WORKTREE inherits its FAMILY's instance — the derivation is family_resolve() above,
# this is only what L20 DOES with the answer (ADR-0050 point 7; ADR-0040).
# The asymmetry is the point. Where the family is verified, a CARE family is refused and a
# records-holding family reds: those protect records, and the layout they fire in is the only one
# this system uses. Where it is NOT verified — bare repository, separate git directory, main tree
# gone, unreadable marker — nothing is inherited, it is said out loud, and this tree's own marker
# governs exactly as in a plain clone. That is deliberately not a red: a wrong answer in DEV costs a
# rerun, a wrong answer about records costs a record (operator, 2026-09-10). Nothing claims `dev`
# off an unchecked observable either way, because with no marker no mode is derived at all.
family_resolve
l20_wt=0; l20_wt_main=""; l20_wt_inherited=0; l20_wt_recs=0; l20_wt_present=""; l20_wt_loud=""
l20_wt_why=""; l20_msrc=""   # l20_msrc: appended to findings about the marker's VALUE, so an
                             # inherited one is not reported as a file to fix in this tree
if [ "$FAM_KIND" = "worktree" ]; then
  l20_wt=1
  # A VERIFIED family is the observable whatever its marker says: keeping the path is what makes the
  # family record probe (5b) run. The first version discarded it whenever the marker was unreadable,
  # so an ABSENT family marker over records reds while a CORRUPT one greened — the more broken state
  # was the quieter one, and `pre-push` (which probes as soon as the family is verified) disagreed
  # with this file about the same tree (round 3, finding 1). Two-line fix; the disagreement is the
  # defect centralising this rule exists to prevent.
  [ "$FAM_STATUS" = "ok" ] && l20_wt_main="$FAM_PATH"
  if [ "$FAM_STATUS" != "ok" ] || [ "$FAM_MSTATE" = "bad" ]; then
    # Loud, not red, and printed once below — a red here would block every commit in a tree whose
    # only fault is an unusual git layout or a broken file in another tree.
    l20_wt_loud="${FAM_REASON:-the checkout family cannot be read}"
  else
    if [ "$FAM_MSTATE" = "ok" ]; then
      if [ "$l20_marker_present" -eq 1 ] && [ "$l20_marker_bad" -eq 1 ]; then
        # A junk LOCAL marker used to end the reading at "unknown instance marker" — fail-closed, but
        # it swallowed the fact that mattered: whether the FAMILY is a records tree (round 1, F6).
        l20_err "this worktree carries a $L20_MARK that is not a readable single line — delete it; the instance is inherited from the main checkout (ADR-0050)"
        l20_marker="$FAM_MARKER"; l20_marker_bad=0; l20_wt_inherited=1
      elif [ "$l20_marker_present" -eq 1 ] && [ "$l20_marker" != "$FAM_MARKER" ]; then
        l20_err "this worktree asserts '${l20_marker:0:32}' but its main checkout asserts '${FAM_MARKER:0:32}' — the instance is a property of the checkout family, not of one tree (ADR-0050); delete $L20_MARK here and let it be inherited"
        # The family's marker wins for everything below, or the checks after this would report the
        # LOCAL claim as if it were the family's — a false second finding on top of a true first one.
        l20_marker="$FAM_MARKER"; l20_wt_inherited=1
      elif [ "$l20_marker_present" -eq 0 ]; then
        l20_marker="$FAM_MARKER"; l20_marker_present=1; l20_wt_inherited=1
      fi
      [ "$l20_wt_inherited" -eq 1 ] && l20_msrc=" — that value is the MAIN CHECKOUT's marker (inherited); fix it there, not in this worktree"
    fi
  fi
fi
[ -n "$l20_wt_loud" ] && echo "L20 note (LOUD): linked worktree, but $l20_wt_loud — nothing was inherited, so this tree's own marker (if any) is all that governs here"


# (3) the record set itself
l20_set_ok=0; l20_recs=""; l20_tools=""; l20_all=""
# A RECORD-SET that exists but is a symlink, a directory, or unreadable is NOT the "absent" shape:
# absent is legitimate (fixture/skeleton), substituted is an attempt to blind the observable. Say so.
if { [ -e "$L20_SET" ] || [ -L "$L20_SET" ]; } && { [ -L "$L20_SET" ] || [ ! -f "$L20_SET" ] || [ ! -r "$L20_SET" ]; }; then
  l20_err "$L20_SET exists but is not a readable regular file (symlink/dir/unreadable) — the record set is the instance mode's only observable and is never followed through a link (fail closed)"
elif [ -f "$L20_SET" ] && [ ! -L "$L20_SET" ] && [ -r "$L20_SET" ]; then
  # One pass, in awk (portable, no bash-4 anything). A line is `record <path>` or `tooling <path>`;
  # `#` starts a comment; a path may not be absolute, may not contain `..`, and may not contain
  # whitespace (every consumer below word-splits the list, so a spaced path would silently split).
  l20_parsed="$(awk '
    { sub(/#.*/, ""); gsub(/^[ \t]+|[ \t]+$/, "") }
    $0 == "" { next }
    NF != 2                                  { print "BAD\t" NR; next }
    $1 != "record" && $1 != "tooling"        { print "BAD\t" NR; next }
    $2 ~ /^\//                               { print "BAD\t" NR; next }
    $2 ~ /(^|\/)\.\.(\/|$)/                  { print "BAD\t" NR; next }
    { print $1 "\t" $2 }
  ' "$L20_SET" 2>/dev/null)"; l20_prc=$?
  if [ "$l20_prc" -ne 0 ]; then
    l20_err "cannot parse $L20_SET (awk rc=$l20_prc) — the record set is the instance mode's only observable (fail closed)"
  else
    l20_pbad="$(printf '%s\n' "$l20_parsed" | awk -F'\t' '$1=="BAD"{n++} END{print n+0}')"
    l20_recs="$(printf '%s\n'  "$l20_parsed" | awk -F'\t' '$1=="record"{print $2}')"
    l20_tools="$(printf '%s\n' "$l20_parsed" | awk -F'\t' '$1=="tooling"{print $2}')"
    l20_all="$l20_recs $l20_tools"
    if [ "$l20_pbad" != "0" ]; then
      l20_err "$L20_SET has $l20_pbad malformed line(s) — each must read 'record <path>' or 'tooling <path>', root-relative, no '..', no whitespace in the path (fail closed)"
    elif [ -z "$l20_recs" ]; then
      l20_err "$L20_SET names no record paths — the instance mode has no observable to derive from (fail closed)"
    else
      l20_set_ok=1
    fi
  fi
fi

if [ "$l20_set_ok" -eq 0 ] && [ "$_l20fired" -eq 0 ]; then
  # The set is absent rather than broken. A tree that ASSERTS an instance mode owes the list the
  # assertion is checked against; a tree that asserts nothing and defines nothing is the record-free
  # shape (skeleton / CI / fixture) — the only place L20 legitimately checks nothing.
  if [ "$l20_marker_present" -eq 1 ]; then
    l20_err "$L20_MARK asserts an instance mode but $L20_SET is missing or empty — the record set is that mode's only observable (fail closed)"
  elif [ "$l20_git_ok" -eq 1 ] && l20_git cat-file -e HEAD:"$L20_SET" >/dev/null 2>&1; then
    l20_err "$L20_SET is tracked in HEAD but absent from the working tree — deleted or renamed; restore it before trusting any green (fail closed)"
  else
    echo "L20 note: no instance marker — record-free tree (skeleton or fixture); no $L20_SET either, so nothing is asserted and nothing is derived"
  fi
fi

if [ "$l20_set_ok" -eq 1 ]; then
  # (4) ignore-mirror drift: every path the record set names must be ignored by git, or a record can
  # reach a commit. Directory entries are tested twice — the directory itself and a synthetic child —
  # because a pattern can cover one and not the other.
  # It stays a RED in every mode: nothing excuses a hole through which a record could be committed.
  l20_mirror_ok=0
  if [ "$l20_git_ok" -eq 1 ] && [ ! -f .gitignore ]; then
    l20_err "no .gitignore in this tree but $L20_SET names $(printf '%s\n' $l20_all | wc -l | tr -d '[:space:]') non-product path(s) — nothing is ignored, so every one of them could be committed (fail closed)"
  elif [ "$l20_git_ok" -eq 1 ]; then
    l20_mirror_ok=1
    for _e in $l20_all; do
      l20_git check-ignore -q -- "$_e"; _l20rc=$?
      if [ "$_l20rc" -eq 1 ]; then
        l20_err "RECORD-SET entry '$_e' is NOT ignored by git — $L20_SET and .gitignore have drifted; a non-product path could be committed"
      elif [ "$_l20rc" -ne 0 ]; then
        l20_err "git check-ignore errored (rc=$_l20rc) on RECORD-SET entry '$_e' — ignore-mirror unverifiable (fail closed)"
      fi
      case "$_e" in */)
        l20_git check-ignore -q -- "${_e}${L20_PROBE}"; _l20rc=$?
        if [ "$_l20rc" -eq 1 ]; then
          l20_err "RECORD-SET entry '$_e' ignores the directory but NOT its contents — .gitignore drift; a file under it could be committed"
        elif [ "$_l20rc" -ne 0 ]; then
          l20_err "git check-ignore errored (rc=$_l20rc) under RECORD-SET entry '$_e' — ignore-mirror unverifiable (fail closed)"
        fi ;;
      esac
    done
  else
    echo "L20 SKIP (LOUD): $l20_git_why — the RECORD-SET ↔ .gitignore ignore-mirror was NOT verified, and neither was the checkout family (git cannot be asked about this tree), so a marker here is taken at face value"
  fi

  # (5) the observable: which record categories actually exist? (a tooling-SHAPED record does not
  #     count — a machine holding only the offsite-destination file is not a records tree)
  l20_has_records=0; l20_present=""
  for _e in $l20_recs; do
    _l20skip=0
    for _s in $L20_SHAPED; do [ "$_e" = "$_s" ] && _l20skip=1; done
    [ "$_l20skip" -eq 1 ] && continue
    _l20p="${_e%/}"
    if [ -e "$_l20p" ] || [ -L "$_l20p" ]; then l20_has_records=1; l20_present="$l20_present $_e"; fi
  done
  # (5b) in a linked worktree the DERIVATION observable is the MAIN checkout's records: the records
  # are untracked, so this tree can only ever answer "record-free" about itself and an inherited
  # `dev` would be a claim about the family that nothing checked (2b).
  if [ "$l20_wt" -eq 1 ] && [ -n "$l20_wt_main" ]; then
    for _e in $l20_recs; do
      _l20skip=0
      for _s in $L20_SHAPED; do [ "$_e" = "$_s" ] && _l20skip=1; done
      [ "$_l20skip" -eq 1 ] && continue
      _l20p="$l20_wt_main/${_e%/}"
      if [ -e "$_l20p" ] || [ -L "$_l20p" ]; then l20_wt_recs=1; l20_wt_present="$l20_wt_present $_e"; fi
    done
  fi

  # (6) marker vs observable
  if [ "$l20_marker_present" -eq 0 ]; then
    if [ "$l20_has_records" -eq 1 ]; then
      l20_err "instance marker missing on a tree that holds records (${l20_present# }) — write $L20_MARK with one line: dev | care (ADR-0050)"
    elif [ "$l20_wt" -eq 1 ] && [ "$l20_wt_recs" -eq 1 ]; then
      l20_err "linked worktree whose main checkout holds records (${l20_wt_present# }) and asserts no instance mode — write $L20_MARK in the MAIN checkout (ADR-0050); a worktree inherits the family's instance, it does not have one of its own"
    elif [ "$_l20fired" -eq 1 ]; then
      # A finding above already characterised this tree. The reassuring note would contradict it —
      # "record-free tree (skeleton or fixture)" printed under a red is exactly the misleading
      # line round 1 asked us to stop printing, and it came back through this branch (round 2, N4).
      :
    elif [ "$l20_wt" -eq 1 ]; then
      if [ "$FAM_STATUS" = "ok" ] && [ "$FAM_MSTATE" = "absent" ]; then l20_wt_why="linked worktree: its main checkout asserts no mode either"
      elif [ "$FAM_STATUS" = "ok" ]; then                                l20_wt_why="linked worktree: its main checkout's marker is unreadable, so nothing was inherited"
      else                                                               l20_wt_why="linked worktree: the checkout family could not be verified — see the LOUD note above"; fi
      echo "L20 note: no instance marker — record-free tree (skeleton or fixture); $L20_SET verified, no record category present ($l20_wt_why)"
    else
      echo "L20 note: no instance marker — record-free tree (skeleton or fixture); $L20_SET verified, no record category present"
    fi
  elif [ "$l20_marker_bad" -eq 1 ]; then
    l20_err "unknown instance marker — $L20_MARK must be a readable regular file holding exactly one line: dev | care$l20_msrc"
  else
    case "$l20_marker" in
      dev)
        L20_MODE="dev"
        if [ "$l20_wt" -eq 1 ] && [ "$l20_wt_recs" -eq 1 ]; then
          # The family is a records tree whatever its marker says — the same inversion (5b) exists
          # for: the main checkout's own board reds on this too, and a worktree must not green over it.
          l20_err "instance dev, but the main checkout of this worktree holds record categories: ${l20_wt_present# } — DEV never contains a record (ADR-0050); fix the marker in the main checkout, not here"
        fi
        if [ -n "$l20_present" ]; then
          l20_err "marked dev but this tree holds record categories: ${l20_present# } — DEV never contains a record (ADR-0050); the records belong to the CARE instance"
        else
          # A record can also arrive somewhere the set does not name. Scan for the three shapes a
          # record has: a profile.md exactly two levels under a directory named `patients`, a file
          # named MANIFEST (the ownership ledger), a directory `med/sources`. Hits are named under the
          # locator rule (`loc`, top of file), the first ten of them.
          # `_templates/` is exempt by design: the shipped person scaffold legitimately contains
          # `person/med/sources/` and a `profile.md` skeleton, and it holds no record.
          l20_shape_out="$(find . \( -name .git -o -name __pycache__ -o -name node_modules -o -name .venv-render -o -name .claude \) -prune -o \
                           \( -type f \( -name MANIFEST -o -name profile.md \) -o -type d -name sources \) -print 2>/dev/null)"; l20_frc=$?
          # The disk is not what a commit carries; the index is. A record-shaped path staged and then
          # deleted from disk, or staged under a NESTED `.claude/` or `node_modules/` the prune above
          # skips (`.gitignore` ignores only the root one), used to green while the commit carried it
          # (break rounds on the migration-mode retirement, 2026-10-25). So the index's paths join the
          # scan: a file under `med/sources/` stands for that directory, a hit on both counts once.
          # Which index: the one being committed. A hook gets it in GIT_INDEX_FILE (`git commit -a`, a
          # partial commit, or a caller's own index); l20_git strips that variable for fixture safety,
          # so it is passed back only when the inherited git environment names THIS tree's own git
          # directory — never for a fixture or another root, and only to read (review 2026-10-25).
          l20_ienv=""
          if [ -n "${GIT_INDEX_FILE:-}" ]; then
            _gd_in="$(git rev-parse --absolute-git-dir 2>/dev/null)"; _gd_own="$(l20_git rev-parse --absolute-git-dir 2>/dev/null)"
            if [ -n "$_gd_in" ] && [ -n "$_gd_own" ] && [ "$(cd "$_gd_in" 2>/dev/null && pwd -P)" = "$(cd "$_gd_own" 2>/dev/null && pwd -P)" ]; then
              case "$GIT_INDEX_FILE" in /*) l20_ienv="$GIT_INDEX_FILE" ;; *) l20_ienv="$PWD/$GIT_INDEX_FILE" ;; esac
            fi
          fi
          l20_ls(){
            if [ -n "$l20_ienv" ]; then
              env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY GIT_INDEX_FILE="$l20_ienv" git ls-files -z
            else l20_git ls-files -z; fi; }
          l20_irc=0
          if [ "$l20_frc" -eq 0 ] && [ "$l20_git_ok" -eq 1 ]; then
            # NUL-separated fields, one per line: without -z git C-quotes a path holding `"`, `\` or a
            # tab even under core.quotePath=false, so a quoted line no longer ends in `profile.md`; a line
            # break inside a name becomes `?`, so the name still matches and stays one entry.
            l20_idx="$(l20_ls 2>/dev/null | tr '\n\000' '?\n'; exit "${PIPESTATUS[0]}")"; l20_irc=$?
            [ "$l20_irc" -eq 0 ] && l20_shape_out="$( { printf '%s\n' "$l20_shape_out"
              printf '%s\n' "$l20_idx" | grep -E '(^|/)(MANIFEST|profile\.md)$|(^|/)med/sources/' \
                | sed -E 's#^((.*/)?med/sources)/.*#\1#; s#^#./#'; } | LC_ALL=C sort -u)"
          fi
          if [ "$l20_frc" -ne 0 ]; then
            l20_err "record-shape scan failed (find rc=$l20_frc) — DEV record-freeness NOT verified (fail closed)"
          elif [ "$l20_irc" -ne 0 ]; then
            l20_err "record-shape scan of the index failed (git ls-files rc=$l20_irc) — what the next commit carries is NOT verified (fail closed)"
          else
            l20_shapes=""; l20_shape_n=0; l20_shape_hits=""
            while IFS= read -r _h; do
              [ -n "$_h" ] || continue
              _r="${_h#./}"
              case "$_r" in _templates/*|_templates) continue ;; esac
              _l20out=0
              for _e in $l20_all; do
                case "$_e" in
                  */)  case "$_r/" in "$_e"*) _l20out=1 ;; esac ;;
                  *)   [ "$_r" = "$_e" ] && _l20out=1 ;;
                esac
                [ "$_l20out" -eq 1 ] && break
              done
              [ "$_l20out" -eq 1 ] && continue
              case "$_r" in
                MANIFEST|*/MANIFEST)
                  l20_shape_n=$((l20_shape_n+1)); l20_shape_hits="$l20_shape_hits$_r"$'\n'; case "$l20_shapes" in *"a file named MANIFEST"*) ;; *) l20_shapes="$l20_shapes; a file named MANIFEST" ;; esac ;;
                *profile.md)
                  _d1="${_r%/profile.md}"
                  [ "$_d1" = "$_r" ] && continue
                  _d2="${_d1%/*}"
                  [ "$_d2" = "$_d1" ] && continue
                  case "$_d2" in patients|*/patients)
                    l20_shape_n=$((l20_shape_n+1)); l20_shape_hits="$l20_shape_hits$_r"$'\n'; case "$l20_shapes" in *"a profile.md under patients/"*) ;; *) l20_shapes="$l20_shapes; a profile.md under patients/<handle>/" ;; esac ;;
                  esac ;;
                *sources)
                  _d1="${_r%/sources}"
                  [ "$_d1" = "$_r" ] && continue
                  case "$_d1" in med|*/med)
                    l20_shape_n=$((l20_shape_n+1)); l20_shape_hits="$l20_shape_hits$_r"$'\n'; case "$l20_shapes" in *"a med/sources directory"*) ;; *) l20_shapes="$l20_shapes; a med/sources directory" ;; esac ;;
                  esac ;;
              esac
            done <<< "$l20_shape_out"
            # A symlinked DIRECTORY defeats the scan above entirely: find never descends one, so a
            # whole records tree parked outside the repository and linked in at the root reads as
            # record-free (review round 4, F6). We cannot follow it — `find -L` would walk the
            # operator's home and could loop — so an unnamed symlinked directory IS the finding:
            # the guard cannot see behind it, and DEV is the instance that must be provably empty.
            # Depth 2 covers the shapes that matter (a link at the root or one level under it);
            # anything RECORD-SET names is excluded, exactly as above, so `.venv-render/` and the
            # other listed tooling paths may legitimately be links. Named; the link is never followed.
            l20_symout="$(find . -maxdepth 2 \( -name .git -o -name __pycache__ -o -name node_modules -o -name .claude \) -prune -o \
                          -type l -print 2>/dev/null)"; l20_slrc=$?
            if [ "$l20_slrc" -ne 0 ]; then
              l20_err "symlinked-directory scan failed (find rc=$l20_slrc) — DEV record-freeness NOT verified (fail closed)"
            else
              while IFS= read -r _h; do
                [ -n "$_h" ] || continue
                [ -d "$_h" ] || continue            # only links that resolve to a DIRECTORY hide a subtree
                _r="${_h#./}"
                case "$_r" in _templates/*|_templates) continue ;; esac
                _l20out=0
                for _e in $l20_all; do
                  case "$_e" in
                    */)  case "$_r/" in "$_e"*) _l20out=1 ;; esac ;;
                    *)   [ "$_r" = "$_e" ] && _l20out=1 ;;
                  esac
                  [ "$_l20out" -eq 1 ] && break
                done
                [ "$_l20out" -eq 1 ] && continue
                l20_shape_n=$((l20_shape_n+1)); l20_shape_hits="$l20_shape_hits$_r"$'\n'
                case "$l20_shapes" in *"a symlinked directory"*) ;; *) l20_shapes="$l20_shapes; a symlinked directory the scan cannot see behind" ;; esac
              done <<< "$l20_symout"
            fi
            if [ "$l20_shape_n" -gt 0 ]; then
              # A hit only the index has is counted, never named: whether its owner is in private mode
              # is read from a profile on disk, and that profile may be the one that is gone (the
              # withholding rule L19 and L5 follow; review 2026-10-25).
              l20_locs=""; l20_named=0; l20_hidden=0
              while IFS= read -r _h; do
                [ -n "$_h" ] || continue
                if [ ! -e "$_h" ] && [ ! -L "$_h" ]; then l20_hidden=$((l20_hidden+1)); continue; fi
                l20_named=$((l20_named+1))
                [ "$l20_named" -le 10 ] && l20_locs="$l20_locs, $(loc "$_h")"
              done <<L20LEOF
$(printf '%s' "$l20_shape_hits")
L20LEOF
              [ "$l20_named" -gt 10 ] && l20_locs="$l20_locs (+$((l20_named - 10)) more)"
              [ "$l20_hidden" -gt 0 ] && l20_locs="$l20_locs, $l20_hidden staged but gone from disk (names withheld; git ls-files --deleted lists them)"
              l20_err "marked dev but $l20_shape_n path(s) match a record shape outside $L20_SET (shapes:${l20_shapes#;}): ${l20_locs#, } — DEV never contains a record; remove each one, from the index too if it is staged (git rm -r --cached <path>)"
            fi
          fi
        fi
        [ "$_l20fired" -eq 0 ] && echo "L20 instance: dev — record-free (record-shape scan clean, disk$([ "$l20_git_ok" -eq 1 ] && echo " and index"); ignore-mirror $([ "$l20_mirror_ok" -eq 1 ] && echo verified || echo 'NOT verified — see the SKIP above'))$([ "$l20_wt_inherited" -eq 1 ] && echo ' — inherited: linked worktree of a dev main checkout, whose RECORD-SET paths are clean too (its own board scans its shapes)' || true)"
        ;;
      care)
        if [ "$l20_wt" -eq 1 ]; then
          # A CARE instance is a pull-only checkout that never edits a tracked file, so it has no
          # reason to carry a worktree — and a worktree of one would escape L19 entirely: the records
          # and checks/CARE-RELEASE are untracked, so L19's own anchors are absent here while tracked
          # files are perfectly editable. Refuse, rather than derive `care` and red five ways.
          # The reader is usually a care session the client opened here by default, so the remedy
          # leads with record work (read-only answering may go on, CLAUDE.md): a worktree session can
          # neither move its folder nor edit the main checkout, and a session started from it
          # inherits the worktree.
          l20_err "linked worktree of a CARE instance — CARE is a pull-only checkout that never edits a tracked file, so it has no worktrees (ADR-0050). Record work: stop, and ask the operator to start a new session in the main care folder with the client's worktree option off — a session started from this one inherits the worktree. Tool work: do it in DEV and relay what was learned as prose (checks/relay-scan.sh)"
        elif [ "$l20_has_records" -eq 0 ]; then
          # NOT handed to L19: a tree that only CLAIMS to be CARE has no CARE contract to check, and
          # letting L19 run here buries the one real finding under five derived ones (every tracked
          # file of a records-less clone reads as "outside the record set").
          l20_err "marked care, holds no records — mis-marked or empty (ADR-0050); a CARE instance is the records plus a pull-only checkout"
        else
          L20_MODE="care"
        fi
        # Containment requirement 7 (evals/README.md), re-dispositioned by ADR-0050 point 6: the
        # behavioral eval's synthetic roster must never sit beside the real one.
        if [ -d patients ]; then
          l20_ev=0
          for _d in patients/evalperson-*/; do [ -d "$_d" ] && l20_ev=$((l20_ev+1)); done
          [ "$l20_ev" -gt 0 ] && l20_err "$l20_ev behavioral-eval fixture roster director(ies) (patients/evalperson-*) in a CARE tree — eval fixtures live in DEV, never beside the real roster (ADR-0050 point 6)"
        fi
        [ "$_l20fired" -eq 0 ] && echo "L20 instance: care — records present (${l20_present# }); tracked-file discipline is L19's"
        ;;
      *)
        # `migration:YYYY-MM-DD`, the bounded third mode of the instance split, was retired once
        # the split finished (ADR-0050 point 14): an old marker lands here, red.
        l20_err "unknown instance marker '${l20_marker:0:32}' — expected dev | care (ADR-0050)$l20_msrc"
        ;;
    esac
  fi
fi

# ---- L19: CARE never edits a tracked file (ADR-0050 Part B) ----
# Runs ONLY when L20 derived the mode `care` — the derivation is the whole point: L19 must not be
# switchable on or off by the marker it is protecting. A CARE instance is a pull-only checkout of DEV
# at a published tag plus the record directories; anything else in the working tree means the product
# was edited where it can never be committed, reviewed, eval'd or released, and the next fast-forward
# will either clobber it or refuse. Three anchors: the working tree carries nothing outside the record
# set; HEAD is exactly the release this instance ADOPTED, named in the untracked one-line
# checks/CARE-RELEASE; and that commit DEMONSTRABLY came from DEV (a local commit that was then
# re-tagged fails the ancestor test — that is the point).
# Break-glass (`checks/CARE-EXCEPTION`): a renderer fault mid-encounter-prep would otherwise leave
# CARE red for days and train blindness, so a dated, reasoned ticket turns every L19 finding into a
# LOUD yellow. Its window is bounded twice — ≤7 days from the ticket's own date AND ≤7 days from
# today, because a self-consistent ticket dated 2099 would otherwise be a permanent hatch. A
# malformed, over-wide, future-dated or expired ticket is itself a red: the escape hatch fails closed.
# Output discipline: locators under the locator rule (`loc`, top of file), never content. NB the
# ticket's `reason:` is operator-authored prose and IS echoed into guard output
# (truncated to 80 chars): write it about the fault, never about the person.
if [ "$L20_MODE" = "care" ]; then
  L19_EXC="checks/CARE-EXCEPTION"
  l19_exc=0; l19_exc_reason=""; l19_exc_expires=""; _l19fired=0
  if [ -e "$L19_EXC" ] || [ -L "$L19_EXC" ]; then
    if [ -L "$L19_EXC" ] || [ ! -f "$L19_EXC" ] || [ ! -r "$L19_EXC" ]; then
      err L19 "$L19_EXC exists but is not a readable regular file — break-glass ticket unparseable (fail closed)"; _l19fired=1
    else
      l19_r="$(sed -n 's/^[[:space:]]*reason:[[:space:]]*\(.*\)$/\1/p'  "$L19_EXC" | head -1 | sed 's/[[:space:]]*$//')"
      l19_d="$(sed -n 's/^[[:space:]]*date:[[:space:]]*\([0-9-]*\).*$/\1/p'    "$L19_EXC" | head -1)"
      l19_x="$(sed -n 's/^[[:space:]]*expires:[[:space:]]*\([0-9-]*\).*$/\1/p' "$L19_EXC" | head -1)"
      l19_dd="$(l20_days "${l19_d:-}")" || l19_dd=""
      l19_xd="$(l20_days "${l19_x:-}")" || l19_xd=""
      l19_now="$(l20_days "$(date -u +%F 2>/dev/null)")" || l19_now=""
      if [ -z "$l19_r" ] || [ -z "$l19_dd" ] || [ -z "$l19_xd" ]; then
        err L19 "$L19_EXC is malformed — it needs 'reason: <text>', 'date: YYYY-MM-DD' and 'expires: YYYY-MM-DD' (fail closed)"; _l19fired=1
      elif [ -z "$l19_now" ]; then
        err L19 "cannot read today's UTC date — the $L19_EXC window is unverifiable (fail closed)"; _l19fired=1
      elif [ "$l19_xd" -lt "$l19_dd" ] || [ "$((l19_xd - l19_dd))" -gt 7 ]; then
        err L19 "$L19_EXC window is not within 7 days of its own date ($l19_d → $l19_x) — a break-glass ticket is bounded by construction (fail closed)"; _l19fired=1
      elif [ "$((l19_xd - l19_now))" -gt 7 ]; then
        # The self-consistent window above is bounded relative to the ticket's OWN date, which the
        # author writes: `date: 2099-01-01 / expires: 2099-01-07` is internally valid and would be a
        # permanent hatch. Bound it against the wall clock too — never more than 7 days from now.
        err L19 "$L19_EXC expires $l19_x, more than 7 days from today — a break-glass window is bounded from NOW, not from a date the ticket chose (fail closed)"; _l19fired=1
      elif [ "$l19_now" -gt "$l19_xd" ]; then
        err L19 "$L19_EXC EXPIRED on $l19_x — the fix was due in DEV inside the window; land it or write a fresh, reasoned ticket"; _l19fired=1
      else
        l19_exc=1; l19_exc_reason="$(printf '%s' "${l19_r:0:80}" | tr -d '\n\r')"; l19_exc_expires="$l19_x"
      fi
    fi
  fi
  # An OPEN break-glass ticket is announced whether or not it is currently downgrading anything
  # (review round 4, F9). A valid ticket with no findings was previously INVISIBLE — the board read
  # exactly like a board with no hatch open at all, so a ticket left in place after its fault was
  # fixed would sit unnoticed until it expired, which is the blindness the bounded window exists to
  # prevent. It is a LOUD note, never a red: the window itself is what fails closed.
  [ "$l19_exc" -eq 1 ] && \
    printf 'L19 EXCEPTION OPEN (LOUD): reason: %s, expires %s — remove %s once the fix has landed in DEV\n' \
      "$l19_exc_reason" "$l19_exc_expires" "$L19_EXC"
  # one finding sink: red normally, LOUD yellow under a valid ticket
  l19_find(){
    _l19fired=1
    if [ "$l19_exc" -eq 1 ]; then
      printf 'L19 EXCEPTION (LOUD): %s — reason: %s, expires %s\n' "$1" "$l19_exc_reason" "$l19_exc_expires"
    else
      err L19 "$1"
    fi
  }
  # is a status path covered by the record set? (dir entry = prefix; bare-name entry = any basename)
  l19_in_set(){
    local q="$1" e
    for e in $l20_all; do
      case "$e" in
        */)   case "$q/" in "$e"*) return 0 ;; esac ;;
        */*)  [ "$q" = "$e" ] && return 0 ;;
        *)    [ "$q" = "$e" ] && return 0
              case "$q" in */"$e") return 0 ;; esac ;;
      esac
    done
    return 1
  }
  if [ "$l20_git_ok" -ne 1 ]; then
    err L19 "CARE instance is not a usable git checkout ($l20_git_why) — tracked-file integrity and the release-tag anchor are unverifiable (fail closed)"; _l19fired=1
  else
    # (a) working tree: nothing but record-set paths. -uall so an untracked-but-not-ignored stray is
    #     caught too (an edited product file and a NEW product file are the same divergence).
    #     -z, read field by field with `read -d ''`: every name arrives exactly as it is — never quoted,
    #     never split on " -> " (the old line parser could lose a stray that way; break round
    #     2026-10-25), line breaks and control bytes included. A rename's two names arrive as two fields,
    #     the new one first. git's exit status rides along as a last field no status line can be
    #     (status fields start with two status letters); a missing one reads as a failure.
    l19_n=0; l19_orig=0; l19_src=""
    while IFS= read -r -d '' _l; do
      case "$_l" in $'\001'rc=*) l19_src="${_l#$'\001'rc=}"; continue ;; esac
      if [ "$l19_orig" -ne 0 ]; then
        # the source side of a rename (a tracked path that went away: revert) or of a copy (unchanged)
        [ "$l19_orig" -eq 1 ] && { l19_x[l19_n]="R "; l19_q[l19_n]="$_l"; l19_n=$((l19_n+1)); }
        l19_orig=0; continue
      fi
      _xy="${_l:0:2}"
      case "$_xy" in R?|?R) l19_orig=1 ;; C?|?C) l19_orig=2 ;; esac
      l19_x[l19_n]="$_xy"; l19_q[l19_n]="${_l:3}"; l19_n=$((l19_n+1))
    done < <(l20_git status --porcelain -z -uall 2>/dev/null; printf '\001rc=%s\0' "$?")
    case "$l19_src" in ''|*[!0-9]*) l19_src=2 ;; esac
    if [ "$l19_src" -ne 0 ]; then
      err L19 "git status failed (rc=$l19_src) — CARE working-tree integrity NOT verified (fail closed)"; _l19fired=1
    else
      # Two kinds of finding, two remedies. An EDITED TRACKED file is the product changed here: revert
      # it and land the change in DEV. A path NOT IN THE ADOPTED RELEASE — not in HEAD, whatever status
      # code git gives it (untracked, staged new, intent-to-add, the new side of a rename or copy, an
      # intent-to-add moved away as ` D`, an unmerged `UA`) — may be a misfiled record, and "revert"
      # would read as delete it, "land it in DEV" as move a record into DEV. It gets a never-delete
      # remedy instead, and wins when one path shows up both ways (`git rm --cached`: an untracked line
      # is always new). A new path that git still lists but that is gone from disk — staged, then moved
      # as the remedy says — is told how to unstage it, which removes nothing. Membership is asked of
      # git per path (`cat-file -e HEAD:<path>`), exact for any name; an error there reads as new, the
      # never-delete side.
      # A new path's NAME is withheld while any person is in private mode: a product path has no owner,
      # so `loc` prints it, yet a stray file name can carry the identifier (break round 2026-10-25). This
      # is L19's own rule, not the shared locator rule `loc` and fsverify.py `locator()` keep in step.
      # `patients/` is normally covered by the record set, so its arm is reached only when the set and
      # the tree have drifted apart — and then EVERY unlisted record file would print a line. Say it
      # once: the finding is "records are outside the set", not "here are 500 files", and a repeated
      # line is where an operator stops reading. It names the first path (locator rule), unless private
      # mode is in use.
      _i=0
      while [ "$_i" -lt "$l19_n" ]; do
        if [ "${l19_x[$_i]}" = "??" ] || ! l20_git cat-file -e "HEAD:${l19_q[$_i]}" 2>/dev/null; then
          l19_k[_i]=n
        else
          l19_k[_i]=t
        fi
        _i=$((_i+1))
      done
      l19_patn=0; l19_pfirst=""; l19_hidden=0; l19_hgone=0; _i=0
      while [ "$_i" -lt "$l19_n" ]; do
        _k="${l19_k[$_i]}"; _q="${l19_q[$_i]}"; _i=$((_i+1))
        l19_in_set "$_q" && continue
        case "$_q" in
          patients|patients/*)
            l19_patn=$((l19_patn+1))
            [ "$l19_patn" -eq 1 ] && l19_pfirst="$_q"
            continue ;;
        esac
        if [ "$_k" = t ]; then
          _j=0; _dup=0
          while [ "$_j" -lt "$l19_n" ]; do
            [ "${l19_k[$_j]}" = n ] && [ "${l19_q[$_j]}" = "$_q" ] && { _dup=1; break; }
            _j=$((_j+1))
          done
          [ "$_dup" -eq 1 ] && continue
          l19_find "working-tree change outside the record set: $(loc "$_q") — CARE never edits a tracked file (ADR-0050); revert it here and land the change in DEV"
        elif [ ! -e "$_q" ] && [ ! -L "$_q" ]; then
          if [ "$LOC_ANY_PRIVATE" -eq 1 ]; then l19_hgone=$((l19_hgone+1))
          else l19_find "new path still listed by git but gone from disk: $(loc "$_q") — unstage it with git rm --cached -- <that path>, which removes no file (ADR-0050)"; fi
        elif [ "$LOC_ANY_PRIVATE" -eq 1 ]; then
          l19_hidden=$((l19_hidden+1))
        else
          l19_find "new path outside the record set, not in the adopted release: $(loc "$_q") — never delete it: ask the operator whose it is; a record goes into that person's med/_inbox/ to be filed, or into _archive/ (ADR-0050)"
        fi
      done
      [ "$l19_hidden" -gt 0 ] && l19_find "$l19_hidden new path(s) outside the record set, not in the adopted release — names withheld while private mode is in use (the operator lists them with \`git status --short -uall\` in their own terminal); never delete them: ask the operator whose they are; a record goes into that person's med/_inbox/ to be filed, or into _archive/ (ADR-0050)"
      [ "$l19_hgone" -gt 0 ] && l19_find "$l19_hgone new path(s) still listed by git but gone from disk — names withheld while private mode is in use (the operator lists them with \`git status --short -uall\`); unstage each with git rm --cached -- <that path>, which removes no file (ADR-0050)"
      if [ "$l19_patn" -gt 0 ]; then
        if [ "$LOC_ANY_PRIVATE" -eq 1 ]; then
          l19_find "$l19_patn path(s) under patients/ appear in the working-tree status outside the record set (first name withheld while private mode is in use) — reconcile $L20_SET with what is on disk"
        else
          l19_find "$l19_patn path(s) under patients/ appear in the working-tree status outside the record set, first: $(loc "$l19_pfirst") — reconcile $L20_SET with what is on disk"
        fi
      fi
    fi
    # (b) HEAD is the ADOPTED release — the tag this instance was deliberately moved to, named in the
    # untracked one-line checks/CARE-RELEASE that the release-acceptance session writes.
    # The old test asked only "HEAD is at SOME tag", which the green line then reported as a fetched
    # release: a clone detached at any mid-history commit plus a local `git tag` satisfied it, and a
    # CARE instance that had drifted BACKWARD to an older adopted tag was indistinguishable from one
    # at the current release (review round 4, F2). Pinning the tag name makes the claim checkable, so
    # the green line below no longer claims a fetch it never performed — the ancestor test in (c) is
    # the only provenance evidence there is, and it says exactly that much.
    L19_PIN="checks/CARE-RELEASE"
    l19_tag=""
    if [ ! -e "$L19_PIN" ] && [ ! -L "$L19_PIN" ]; then
      l19_find "no adopted release pinned — $L19_PIN is missing; a CARE instance records the release tag it accepted (write it with: checks/install-instance.sh care <tag>)"
    elif [ -L "$L19_PIN" ] || [ ! -f "$L19_PIN" ] || [ ! -r "$L19_PIN" ]; then
      l19_find "no adopted release pinned — $L19_PIN exists but is not a readable regular file (symlink/dir/unreadable); the pin is never followed through a link (fail closed)"
    else
      l19_praw="$(tr -d '\r' < "$L19_PIN" | sed '/^[[:space:]]*$/d')"
      l19_pcnt="$(printf '%s\n' "$l19_praw" | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')"
      l19_pin="$(printf '%s\n' "$l19_praw" | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
      if [ "$l19_pcnt" != "1" ] || [ -z "$l19_pin" ]; then
        l19_find "no adopted release pinned — $L19_PIN must hold exactly one line, the adopted release tag (found ${l19_pcnt:-0} non-empty line(s))"
      elif ! is_release_name "$l19_pin"; then
        l19_find "the pin '${l19_pin:0:64}' is not a release name (vMAJOR.MINOR.PATCH, optionally -slug) — a revision like <tag>~1 names an untagged commit; re-pin the adopted release with: checks/install-instance.sh care <tag>"
      else
        # ^{} peels an annotated tag to the commit it points at; --verify --quiet keeps a missing tag
        # silent so the message below is the guard's, not git's.
        l19_pc="$(l20_git rev-parse --verify --quiet "refs/tags/${l19_pin}^{}" 2>/dev/null)"
        l19_hc="$(l20_git rev-parse --verify --quiet HEAD 2>/dev/null)"
        if [ -z "$l19_hc" ]; then
          l19_find "cannot resolve HEAD in this checkout — the adopted-release anchor is unverifiable (fail closed)"
        elif [ -z "$l19_pc" ]; then
          l19_find "the pinned release tag '${l19_pin:0:64}' does not exist in this checkout — fetch DEV's tags, or correct $L19_PIN; a pin naming nothing anchors nothing (fail closed)"
        elif [ "$l19_pc" != "$l19_hc" ]; then
          l19_find "HEAD is not the pinned release '${l19_pin:0:64}' — CARE moves only by fast-forward to an adopted tag (ADR-0050); check out that tag, or run a release-acceptance session and re-pin"
        else
          l19_tag="$l19_pin"
        fi
      fi
    fi
    # (c) … and that release came from DEV: HEAD must be reachable from a remote-tracking ref of origin.
    # A locally-created tag on a locally-created commit satisfies (b) and fails here — by design.
    l19_refs="$(l20_git for-each-ref --format='%(refname)' refs/remotes/origin 2>/dev/null)"; l19_rrc=$?
    if [ "$l19_rrc" -ne 0 ]; then
      l19_find "cannot enumerate refs/remotes/origin (git rc=$l19_rrc) — release provenance unverifiable (fail closed)"
    elif [ -z "$l19_refs" ]; then
      l19_find "no refs/remotes/origin/* in this checkout — nothing here was fetched from DEV, so the tag at HEAD proves nothing; add the DEV remote and fetch"
    else
      l19_anc=0
      while IFS= read -r _r; do
        [ -n "$_r" ] || continue
        if l20_git merge-base --is-ancestor HEAD "$_r" >/dev/null 2>&1; then l19_anc=1; break; fi
      done <<< "$l19_refs"
      [ "$l19_anc" -eq 0 ] && l19_find "HEAD is not an ancestor of any origin remote-tracking ref — this commit was made locally (a local commit that was then re-tagged fails exactly here); fetch DEV and fast-forward to a published tag"
    fi
  fi
  [ "$_l19fired" -eq 0 ] && echo "L19 CARE anchor: HEAD = pinned release ${l19_tag:-?}, reachable from origin; working tree carries only record-set paths"
fi

# Stamp the green line with its ENVIRONMENT (ADR-0021): a "green" is only meaningful for the platform
# it ran on — this incident began with "green in the Linux sandbox" read as "green everywhere".
if [ "$fail" -eq 0 ]; then
  echo "OK: all guards green ($(date -u +%FT%TZ); $(uname -s) / bash ${BASH_VERSINFO[0]}.${BASH_VERSINFO[1]})"
fi
exit "$fail"
