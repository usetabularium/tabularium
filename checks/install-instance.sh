#!/usr/bin/env bash
# checks/install-instance.sh — install this tree's per-instance UNTRACKED tooling (ADR-0050 Part B).
#
# ADR-0050 splits the system into two instances: DEV (the product — tooling, templates, guards, ADRs,
# the eval; it never holds a record) and CARE (a pull-only checkout of DEV at a release tag, plus the
# record directories that are never committed anywhere). What differs between them is exactly the
# machinery that is installed rather than committed, and the ADR's inventory of it lived only in
# prose — so it was reproducible only by remembering. This script is that inventory, executable.
#
# Usage:  checks/install-instance.sh dev | care [<release-tag>]
# Exit:   0 = every action written or already in place · 1 = refused, or an action failed.
#
# IDEMPOTENT: a second run prints `unchanged` for everything and changes nothing. Every action prints
# ONE line — `written`, `unchanged` or `warn: …` — so a run is readable at a glance and a diff of two
# runs is the change set.
#
# What it does, per mode:
#   marker      .tabularium-instance = the mode, in every mode. It only ASSERTS the mode: L20 DERIVES
#               it from which checks/RECORD-SET record paths exist and reds when the two disagree.
#   git hooks   dev: the four hooks from checks/git-hooks/; CARE: pre-push only (a belt). CARE never
#               commits, so installing them there would only double the installed-hook drift surface.
#   origin      care only — a CARE instance tracks DEV by fetch; without an `origin` remote L19's
#               provenance anchor cannot pass and the tag at HEAD proves nothing. Warn, never create.
#   release     care only — checks/CARE-RELEASE names the release tag this instance ADOPTED; L19
#               requires HEAD to be exactly it. `care <tag>` refuses, before writing anything, a tag
#               that does not resolve locally or is not checked out at HEAD, and writes the pin LAST,
#               only when every other action succeeded — a failed or interrupted install leaves the
#               previous pin, so L19 stays red. Warned about when absent. Never fetched or chosen for you.
#   leftovers   care only — tooling of this installer's own that care must not run is removed, each
#               removal printed: a skill this release does not ship, or a git hook care does not install
#               (any name), whose bytes are that path's own at a local release tag; a settings hook whose
#               tools/claude-hooks/ script is gone (python3 on a missing script exits 2, which a
#               PreToolUse hook treats as a block) or that is the development-only context-health
#               notice — taken out of a shared entry alone, the operator's hooks and matcher left as they
#               are. Ownership is read from the releases' bytes, not from name lists or headers, so a
#               newer release's additions are recognised on a rollback, and an edited copy is kept with
#               a warning. Any other skill, hook or settings entry is the operator's and is never touched.
#   .venv-render  advised in BOTH (CARE renders handouts with it; DEV needs it so the renderer bites
#                 run instead of printing SKIP).
#               Never created here: it is a pinned environment, not a directory.
#   private mode  reported in BOTH, in one line: tools/private-mode/check-setup.sh --summary says
#               complete or names each missing local tool. Never installed here and never a failure:
#               only a person in private mode needs them (Python aside, which step 6 requires anyway).
#   registry    checks/FIREWALL-REGISTRY must resolve, or the readers are blind. Since ADR-0050 Part B
#               no session guard reads the registry at all: the readers are the flip-time export gate,
#               the CARE relay scan and the eval's pre-transit scan. A care-only install has neither
#               file and needs neither (ADR-0068): those readers stay refused, and nothing else reads them.
#   private id  checks/PRIVATE-MODE-ID names the private-mode identifier's own file (ADR-0050 point 9,
#               2026-09-16). The split is VERIFIED here, content-blind: owner-only, one identifier class line (plus private mode v2 class lines), a
#               usable pattern, absent from every file beside the registry (cut, not copied), and folded
#               back into exactly one class when the registry is sourced (the export gate's view).
#   read-guard  the ADR-0050 A1 PreToolUse hook + the Read/Edit deny rules, MERGED into
#               .claude/settings.local.json (never replaced). The hook's command line carries the
#               absolute paths it protects (--private, --registry) and --split-verified only once the
#               split verifies; until then the registry stays protected. Deny rules follow the same
#               state: the private file and its pointer always, the registry and its pointer only
#               until the split verifies — those two, and the pre-A2 export-script pair once the
#               script is token-free, are the only rules this installer ever removes (and, in care,
#               the hooks named under `leftovers`).
#   context-health  dev only: the PostToolUse size notice for the docs that enter a
#               session's context, merged into the same file the same way; a care run removes one an
#               earlier install left, by the same path as the other leftovers (tools/claude-hooks/README.md).
#   release-notice  care only, when this release ships tools/claude-hooks/release-notice.py: the
#               SessionStart hook (matcher `startup`) that shows one line when a newer MINOR or MAJOR
#               release waits (ADR-0055 companion; checks/release-notice.sh), merged the same way. A
#               rollback to a release without the script removes it by the leftovers path.
#   /update     care only: the skill that runs checks/adopt-release.sh at the operator's word.
#
# In a LINKED WORKTREE (ADR-0040) the marker and the hooks are the FAMILY's, not this tree's — see
# step 0b. The instance is not worked out here: `checks/check.sh --instance-mode` is the single
# derivation, shared with guard L20 and the pre-push hook (ADR-0050 point 7). A
# requested mode that disagrees with the family is REFUSED; a family that cannot be read is a WARN
# with no marker written, because writing one there is the operator's deliberate act, not this
# script's.
#
# What it never does: create the venv, add a remote, write a record, touch a tracked file, or run git
# in a way that changes state. It reads the registry's PATH to write a deny rule and never prints it
# (the checks/OFFSITE-DEST discipline) — no class value is read here at all.
#
# Portable: bash 3.2 / BSD userland; PORT-linted and bite-tested in checks/selftest.sh.
set -uo pipefail

SELF_ROOT="$(cd "$(dirname "$0")/.." && pwd)" || SELF_ROOT=""
[ -n "$SELF_ROOT" ] || { echo "install-instance: REFUSED — cannot resolve the repository root." >&2; exit 1; }

rc_final=0
say(){  printf '%s\n' "$1"; }
warn(){ printf 'warn: %s\n' "$1"; }
die(){  printf 'install-instance: REFUSED — %s\n' "$1" >&2; exit 1; }

# git with the inherited git environment STRIPPED: this script may run from a session whose
# GIT_DIR/GIT_INDEX_FILE point at another repository, and those OVERRIDE discovery (the 2026-07-19
# incident that flipped core.bare). Read-only here — nothing below changes git state.
xgit(){ env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_COMMON_DIR -u GIT_PREFIX -u GIT_OBJECT_DIRECTORY git "$@"; }

# ---- release_copy(): is this file a release's own copy of that path? (care leftovers) -------------
# $1 = a path in a release (tools/claude-skills/<name>/SKILL.md, checks/git-hooks/<name>) · $2 = the file
# -> "same <tag>" when the file's bytes are that path's blob at a local release tag (the name rule is
# check.sh's --release-name), "named <tag>" when no release has those bytes but one has the path, else
# nothing. The proof the care clean-up removes a skill or a git hook on: bytes, never a name or a header.
release_copy(){
  local h t b named=""
  h="$(xgit -C "$SELF_ROOT" hash-object --path="$1" -- "$2" 2>/dev/null)" || return 0
  [ -n "$h" ] || return 0
  while IFS= read -r t; do
    [ -n "$t" ] || continue
    bash "$SELF_ROOT/checks/check.sh" --release-name "$t" 2>/dev/null || continue
    b="$(xgit -C "$SELF_ROOT" rev-parse --verify --quiet "refs/tags/${t}^{commit}:$1" 2>/dev/null)" || continue
    if [ "$b" = "$h" ]; then printf 'same %s\n' "$t"; return 0; fi
    [ -n "$named" ] || named="$t"
  done <<EOF
$(xgit -C "$SELF_ROOT" tag --list 'v*' 2>/dev/null)
EOF
  [ -z "$named" ] || printf 'named %s\n' "$named"
  return 0
}

# ---- WHERE the class lines and the private-mode identifier live: checks/config-paths.sh, shared with
# snapshot.sh and relay-scan.sh, loaded from this script's own tree.
CFG_PATHS="$SELF_ROOT/checks/config-paths.sh"
[ -f "$CFG_PATHS" ] && [ -r "$CFG_PATHS" ] && . "$CFG_PATHS" 2>/dev/null && declare -F registry_path private_id_path >/dev/null \
  || die "checks/config-paths.sh is missing or unreadable — the token registry and the private-mode identifier file cannot be located"

# ---- pm_alternatives(): the spelling of an ERE's alternatives, at every nesting level --------------
# `a|b(cd|ef)g` -> a · b(cd|ef)g · cd · ef. A `|`, `(` or `)` that is escaped or sits inside a bracket
# expression (`[|]`, `[[:alpha:]]`) is carried verbatim, never split. Fills PM_ALTS[] with each
# alternative that carries a run of three or more letters or digits OUTSIDE bracket expressions and
# escapes; purely structural branches (`[^0-9]`, `^`, `\b`) are dropped, so class syntax shared with
# another class cannot block a correct split. rc 1 = the shape could not be told apart (an unbalanced
# ( ) or [ ], a trailing backslash) and the caller refuses conservatively. CONTENT-BLIND: the pattern
# arrives in a variable and the alternatives leave in an array; nothing is printed. Bash 3.2 has no
# namerefs, so pm_put/pm_emit reach the caller's buf[]/lit[]/d by dynamic scope.
pm_put(){ # $1 = verbatim text · $2 = its literal text, appended at every open level
  local k=0; while [ "$k" -le "$d" ]; do buf[$k]="${buf[$k]}$1"; lit[$k]="${lit[$k]}$2"; k=$((k+1)); done; }
pm_emit(){ case "${lit[$d]}" in *[[:alnum:]][[:alnum:]][[:alnum:]]*) PM_ALTS[${#PM_ALTS[@]}]="${buf[$d]}" ;; esac; }
pm_alternatives(){ # $1 = pattern -> PM_ALTS[]
  local p="$1" n i ch d=0 k j cls
  local -a buf lit
  PM_ALTS=(); buf[0]=""; lit[0]=""; n=${#p}; i=0
  while [ "$i" -lt "$n" ]; do
    ch="${p:$i:1}"
    case "$ch" in
      '\') [ $((i+1)) -lt "$n" ] || return 1
           pm_put "${p:$i:2}" " "; i=$((i+2)) ;;
      '[') k="$i"; i=$((i+1))
           [ "${p:$i:1}" = '^' ] && i=$((i+1))
           [ "${p:$i:1}" = ']' ] && i=$((i+1))
           while [ "$i" -lt "$n" ] && [ "${p:$i:1}" != ']' ]; do
             case "${p:$i:2}" in
               '[:'|'[='|'[.')   # a class inside the bracket: skip to its own `:]`, `=]` or `.]`
                 cls="${p:$((i+1)):1}"; j=$((i+2))
                 while [ $((j+1)) -lt "$n" ] && [ "${p:$j:2}" != "$cls]" ]; do j=$((j+1)); done
                 [ $((j+1)) -lt "$n" ] || return 1
                 i=$((j+2)) ;;
               *) i=$((i+1)) ;;
             esac
           done
           [ "$i" -lt "$n" ] || return 1
           i=$((i+1)); pm_put "${p:$k:$((i-k))}" " " ;;
      '(') pm_put "(" " "; d=$((d+1)); buf[$d]=""; lit[$d]=""; i=$((i+1)) ;;
      '|') pm_emit; buf[$d]=""; lit[$d]=""
           k=0; while [ "$k" -lt "$d" ]; do buf[$k]="${buf[$k]}|"; lit[$k]="${lit[$k]} "; k=$((k+1)); done
           i=$((i+1)) ;;
      ')') [ "$d" -gt 0 ] || return 1
           pm_emit; d=$((d-1)); pm_put ")" " "; i=$((i+1)) ;;
      *)   case "$ch" in [[:alnum:]]) pm_put "$ch" "$ch" ;; *) pm_put "$ch" " " ;; esac
           i=$((i+1)) ;;
    esac
  done
  [ "$d" -eq 0 ] || return 1
  pm_emit
  return 0
}

# ---- split_unverified(): is the private-mode identifier really split out? (ADR-0050 point 9) ----
# Prints WHY NOT, one line; prints nothing when the split verifies. CONTENT-BLIND: the pattern is read
# into a variable and used only as a grep argument and a sourced comparison, never printed, and every
# grep here is -q. The read-guard stops protecting the registry only when this prints nothing, so it
# checks the one thing a by-hand cut can get wrong without anyone noticing — a COPY left behind.
split_unverified(){ # $1 = the private-mode identifier file · $2 = the token registry ('' = none)
  local f="$1" r="$2" mode n v lc c x k hits dir cls
  local -a pm_e
  [ -n "$r" ] || { echo "the token registry does not resolve"; return 0; }
  mode="$(stat -f '%Lp' "$f" 2>/dev/null)" || mode=""
  case "$mode" in [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;; *) mode="$(stat -c '%a' "$f" 2>/dev/null)" || mode="" ;; esac
  case "$mode" in [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;; *) echo "its file mode cannot be read"; return 0 ;; esac
  case "${mode: -2}" in 00) ;; *) echo "it is not owner-only (mode $mode) — chmod 600 it"; return 0 ;; esac
  case "$f" in "$SELF_ROOT"/*|"${WT_MAIN:-/nonexistent-family}"/*) echo "it sits inside a work tree — it must live outside every repository"; return 0 ;; esac
  # One PII_PRIVATE_MODE_ID line, and for private mode v2 (ADR-0029 point 13) at most one
  # PII_PRIVATE_<CLASS> line per registry class, holding a v2 person's withheld-value tokens moved out
  # of the readable registry. Every value gets the same proof below: compiles, cut not copied, folded.
  # A PII_PRIVATE_CASEREF line (the retired case-reference class, ADR-0072) is accepted and ignored.
  # every line not blank or a `#` comment must be one of those assignments, exactly (a near miss —
  # `export …`, spaces around `=`, another case or name — would be ignored by every reader)
  # (under the C locale, as every reader does; one assignment per line; one quoted pair per value with
  # no ' inside it — read greedily, `'a'|'b'` is one value matching neither token, Codex review of PR #92)
  n="$(LC_ALL=C grep -cvE '^[[:space:]]*(#.*)?$' "$f" 2>/dev/null)"
  { [ "$n" = "$(LC_ALL=C grep -cE "^[[:space:]]*PII_PRIVATE_(MODE_ID|IDENTITY|CASEREF|CLINICAL|BRAND|CONSENT)='[^']*'\$" "$f" 2>/dev/null)" ] \
    && [ "$(LC_ALL=C grep -cE '^[[:space:]]*PII_PRIVATE_MODE_ID=' "$f" 2>/dev/null)" = "1" ] \
    && [ "$(LC_ALL=C grep -cE '^[[:space:]]*PII_PRIVATE_[A-Z_]+=.*PII_PRIVATE_' "$f" 2>/dev/null)" = "0" ]; } \
    || { echo "it must carry exactly one PII_PRIVATE_MODE_ID line and, for kept details, PII_PRIVATE_<CLASS> lines only, one NAME='value' per line with no ' inside the value (write an apostrophe as .), every other line blank or a # comment"; return 0; }
  v="$(sed -n "s/^[[:space:]]*PII_PRIVATE_MODE_ID='\([^']*\)'\$/\1/p" "$f")"
  [ -n "$v" ] || { echo "its PII_PRIVATE_MODE_ID value is empty or not single-quoted"; return 0; }
  local -a v2c v2v
  v2c=(); v2v=()
  for x in IDENTITY CLINICAL BRAND CONSENT; do
    case "$(LC_ALL=C grep -cE "^[[:space:]]*PII_PRIVATE_${x}=" "$f" 2>/dev/null)" in
      0) continue ;;
      1) ;;
      *) echo "it carries more than one PII_PRIVATE_${x} line"; return 0 ;;
    esac
    k="$(sed -n "s/^[[:space:]]*PII_PRIVATE_${x}='\([^']*\)'\$/\1/p" "$f")"
    [ -n "$k" ] || { echo "its PII_PRIVATE_${x} value is empty or not single-quoted"; return 0; }
    v2c[${#v2c[@]}]="$x"; v2v[${#v2v[@]}]="$k"; k=""
  done
  # `|| true`, never `|| lc=""`: under pipefail an early `head` exit can fail the pipeline after the
  # locale was found, and resetting it would read as "no UTF-8 locale" (relay-scan.sh's own note).
  lc="$(locale -a 2>/dev/null | grep -E '^(en_US|en_GB|C)\.(UTF-8|utf8)$' | head -1)" || true
  [ -n "$lc" ] || { echo "there is no UTF-8 locale on this host to test its pattern under"; return 0; }
  # every value — the identifier's and each v2 line's — must compile and must not match an empty line
  for k in "$v" ${v2v[@]+"${v2v[@]}"}; do
    printf 'x' | LC_ALL="$lc" grep -qiE -- "$k" 2>/dev/null; c=$?
    [ "$c" -lt 2 ] || { echo "a pattern in it does not compile"; return 0; }
    if printf '\n' | LC_ALL="$lc" grep -qiE -- "$k" 2>/dev/null; then
      echo "a pattern in it matches an empty line, so every line (a stray | left by the cut?)"; return 0
    fi
  done
  k=""
  [ "$(grep -cE '^[[:space:]]*PII_PRIVATE_[A-Z_]+=' "$r" 2>/dev/null)" = "0" ] \
    || { echo "the registry itself carries a PII_PRIVATE_* line — those lines belong only in the private file"; return 0; }
  # Cut, not copied: nothing in the registry's directory (three levels down) — the registry itself, an
  # editor's backup of it, a stray or staged copy — may still carry the identifier or a v2 value. Each is
  # checked THREE ways: as the pattern (a literal left behind); as the pattern's own TEXT, because a
  # pattern written with regex syntax (`[ -]?`, `\b`) does not match its own spelling (review of PR #14);
  # and as the text of each of its ALTERNATIVES at every nesting level, because a partial cut leaves one
  # alternative of several behind and neither of the first two sees it (Codex review of PR #14).
  pm_e=()
  for k in "$v" ${v2v[@]+"${v2v[@]}"}; do
    pm_alternatives "$k" || { echo "a pattern's alternatives cannot be told apart (an unbalanced ( ) or [ ], or a trailing backslash) — simplify the pattern"; return 0; }
    if [ "${#PM_ALTS[@]}" -gt 0 ]; then
      for x in "${PM_ALTS[@]}"; do pm_e[${#pm_e[@]}]="-e"; pm_e[${#pm_e[@]}]="$x"; done
    fi
  done
  k=""
  dir="$(dirname "$r")"; hits=0; n=0
  while IFS= read -r -d '' x; do
    [ "$x" -ef "$f" ] && continue
    n=$((n+1))
    [ "$n" -le 200 ] || { echo "the registry's directory holds too many files to check"; return 0; }
    cls=0
    for k in "$v" ${v2v[@]+"${v2v[@]}"}; do
      LC_ALL="$lc" grep -qiE -- "$k" "$x" 2>/dev/null; c=$?
      [ "$c" -lt 2 ] || { echo "a file beside the registry could not be checked"; return 0; }
      if [ "$c" -eq 0 ] || LC_ALL="$lc" grep -qiF -- "$k" "$x" 2>/dev/null; then cls=1; fi
    done
    k=""
    if [ "$cls" -eq 1 ] || { [ "${#pm_e[@]}" -gt 0 ] && LC_ALL="$lc" grep -qiF "${pm_e[@]}" -- "$x" 2>/dev/null; }; then hits=$((hits+1)); fi
  done < <(find "$dir" -maxdepth 3 -type f -print0 2>/dev/null)
  PM_ALTS=(); pm_e=()
  [ "$hits" -eq 0 ] || { echo "$hits file(s) beside the registry (the registry itself, or a backup or copy of it) still carry the identifier, a kept-details value, its pattern or one of the pattern's alternatives — it was copied, not cut"; return 0; }
  # The export gate SOURCES the registry: sourced, it must fold the identifier back into exactly one
  # class, and each v2 line back into its own class; every folded class must still compile and not match
  # every line (a class whose only alternative was the identifier folds into `|pattern`). Output and
  # errors discarded — a sourcing error could echo source text. Only three counters come back.
  set -- "$r" "$v"
  if [ "${#v2c[@]}" -gt 0 ]; then
    for n in "${!v2c[@]}"; do set -- "$@" "${v2c[$n]}" "${v2v[$n]}"; done
  fi
  cls="$(env -i PATH="$PATH" HOME="${HOME:-}" LC_ALL="$lc" bash -c 'set -u; . "$1" >/dev/null 2>&1 || exit 3; n=0; bad=0; miss=0
    for c in PII_IDENTITY PII_CLINICAL PII_BRAND PII_CONSENT; do
      eval "cv=\${$c:-}"
      case "$cv" in *"|$2"|*"|$2|"*)
        n=$((n+1))
        printf x | grep -qiE -- "$cv" 2>/dev/null; [ "$?" -lt 2 ] || bad=1
        if printf "\n" | grep -qiE -- "$cv" 2>/dev/null; then bad=1; fi ;;
      esac
    done
    shift 2
    while [ "$#" -ge 2 ]; do
      eval "cv=\${PII_$1:-}"
      case "$cv" in *"|$2"|*"|$2|"*) ;; *) miss=$((miss+1)) ;; esac
      printf x | grep -qiE -- "$cv" 2>/dev/null; [ "$?" -lt 2 ] || bad=1
      if printf "\n" | grep -qiE -- "$cv" 2>/dev/null; then bad=1; fi
      shift 2
    done; printf "%s %s %s" "$n" "$bad" "$miss"' _ "$@" 2>/dev/null)" || cls=""
  set --
  v=""; v2v=()
  [ "${cls%% *}" = "1" ] || { echo "the registry does not fold the private class back into exactly one class when sourced — paste the block from checks/topics/relay-and-export.md at its end"; return 0; }
  [ "$(printf '%s' "$cls" | cut -d' ' -f3)" = "0" ] || { echo "the registry does not fold a kept-details line back into its class when sourced — paste the current block from checks/topics/relay-and-export.md at its end"; return 0; }
  [ "$(printf '%s' "$cls" | cut -d' ' -f2)" = "0" ] || { echo "the class the registry folds it into no longer compiles, or matches every line (was the identifier that class's only alternative, or is a | left over?)"; return 0; }
  return 0
}

# ---- 0. the mode ---------------------------------------------------------------------------------
[ "$#" -ge 1 ] || die "no mode given (usage: checks/install-instance.sh dev | care [<release-tag>])"
MODE="$1"
PIN="${2:-}"
[ "$#" -le 2 ] || die "too many arguments (usage: checks/install-instance.sh dev | care [<release-tag>])"
if [ -n "$PIN" ] && [ "$MODE" != "care" ]; then
  die "a release tag is a CARE property — only 'care <tag>' takes a second argument (ADR-0050: DEV is where releases are made, CARE is where one is adopted)"
fi
case "$MODE" in
  dev|care) ;;
  # `migration:YYYY-MM-DD`, the instance split's bounded third mode, was retired once the split
  # finished (ADR-0050 point 14); guard L20 reds an old marker as unknown.
  *) die "mode must be dev | care (got '$(printf '%s' "$MODE" | cut -c1-32)')" ;;
esac
say "instance: $MODE (in $SELF_ROOT)"

# ---- 0b. is this a LINKED WORKTREE? (ADR-0040 scratch trees; ADR-0050 point 7) -------------------
# A worktree is not its own instance, and this script does not work that out for itself: the single
# derivation is `checks/check.sh --instance-mode`, and check.sh, this script and the pre-push hook all
# consume that one answer. Two things are the FAMILY's, never this tree's:
#   · the marker — untracked, so a worktree has none; L20 reads the main checkout's;
#   · the git hooks — ONE hooks directory serves every worktree, so installing from here would push
#     this worktree's (possibly uncommitted) branch of checks/git-hooks/* onto the main checkout and
#     every sibling. A silent, tree-wide change nobody asked for.
# Both are skipped here and said out loud; the genuinely per-tree tooling (read-guard settings, the
# skills) still installs, which is exactly what a worktree created by hand needs.
# A requested mode that disagrees with the family is REFUSED. A family that cannot be read is NOT a
# refusal — it is a warn, and no marker is written: writing one here is the operator's deliberate act,
# never this script's (round 2, N1: the version that wrote a marker in that branch completed a chain
# that made a records-holding family read as `dev`).
WT_LINKED=0; WT_INHERIT=0; WT_MAIN=""
if [ -f "$SELF_ROOT/checks/check.sh" ] && [ ! -L "$SELF_ROOT/checks/check.sh" ]; then
  im_out="$(bash "$SELF_ROOT/checks/check.sh" --instance-mode "$SELF_ROOT" 2>/dev/null)" || im_out=""
  im_kind=""; im_status=""; im_marker=""; im_mstate=""; im_reason=""; im_family=""
  while IFS='=' read -r im_k im_v; do
    case "$im_k" in
      kind)         im_kind="$im_v" ;;
      status)       im_status="$im_v" ;;
      marker)       im_marker="$im_v" ;;
      marker_state) im_mstate="$im_v" ;;
      reason)       im_reason="$im_v" ;;
      family)       im_family="$im_v" ;;
    esac
  done <<IMEOF
$im_out
IMEOF
  if [ -z "$im_kind" ]; then
    die "the instance derivation (checks/check.sh --instance-mode) returned nothing usable — refusing to install against an unknown checkout family"
  elif [ "$im_kind" = "worktree" ]; then
    WT_LINKED=1
    if [ "$im_status" = "ok" ] && [ "$im_mstate" = "ok" ]; then
      WT_MAIN="$im_family"
      [ "$im_marker" = "$MODE" ] \
        || die "the family asserts '$(printf '%s' "$im_marker" | cut -c1-32)' but this run asks for '$MODE' — the instance is a property of the checkout family, not of one worktree; re-run as: checks/install-instance.sh $im_marker"
      # A CARE family has no worktrees: guard L20 refuses this shape outright, so provisioning it
      # would tell the operator the tree is fine and leave them with a board that can never go green
      # (round 3, finding 5 — the third consumer disagreeing about the same tree).
      [ "$im_marker" != "care" ] \
        || die "this is a linked worktree of a CARE instance — CARE is a pull-only checkout that never edits a tracked file, so it has no worktrees (ADR-0050); guard L20 refuses this tree, and installing tooling into it would not change that. Record work: start a new session in the main care folder with the client's worktree option off; tool work: do it in DEV"
      WT_INHERIT=1
      say "worktree: linked — instance '$MODE' inherited from the main checkout (marker and git hooks are the family's; only per-tree tooling is installed here)"
    else
      warn "linked worktree, but ${im_reason:-the checkout family cannot be read} — nothing is inherited and NO marker is written here. If this tree really is a '$MODE' instance, write .tabularium-instance yourself; guard L20 will say so either way"
    fi
  fi
else
  die "checks/check.sh is missing or symlinked — the instance derivation cannot be run, and this script will not install against an unknown checkout family"
fi

# ---- 0c. the release to pin, verified before anything is written (care only; ADR-0050 / ADR-0055) --
# L19's anchor is "HEAD is the release this instance ACCEPTED", not "HEAD is at some tag" — so the tag
# name has to be recorded somewhere. It is per-instance (which release THIS machine adopted), hence
# untracked, hence installed here. A tag that does not resolve locally, or is not the commit checked
# out, is REFUSED before any action: a pin naming nothing anchors nothing, and a pin naming a release
# this checkout does not run would let a stopped checkout look adopted. The pin itself is written LAST
# (step 8), and only when every action succeeded. `git rev-parse` is read-only; nothing here fetches.
RELPIN="$SELF_ROOT/checks/CARE-RELEASE"
if [ "$MODE" = "care" ]; then
  if [ -L "$RELPIN" ]; then
    die "checks/CARE-RELEASE is a symlink — remove it by hand; the release pin is never followed through a link"
  elif [ -e "$RELPIN" ] && [ ! -f "$RELPIN" ]; then
    die "checks/CARE-RELEASE exists but is not a regular file"
  fi
  if [ -n "$PIN" ]; then
    # The shape is check.sh's, the one definition L19 applies to the same pin.
    bash "$SELF_ROOT/checks/check.sh" --release-name "$PIN" \
      || die "'${PIN:0:64}' is not a release name (vMAJOR.MINOR.PATCH, optionally -slug) — a revision like <tag>~1 or a branch names no release; pass the release tag itself"
    command -v git >/dev/null 2>&1 || die "git is not installed — the release tag '$PIN' cannot be verified, and an unverified pin is not written"
    xgit -C "$SELF_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
      || die "this is not a git work tree — the release tag '$PIN' cannot be verified, and an unverified pin is not written"
    pin_c="$(xgit -C "$SELF_ROOT" rev-parse --verify --quiet "refs/tags/${PIN}^{commit}" 2>/dev/null)" \
      || die "no such release tag in this checkout: '$PIN' — fetch DEV's tags first (git fetch --tags), then re-run; a pin naming nothing anchors nothing"
    head_c="$(xgit -C "$SELF_ROOT" rev-parse --verify --quiet HEAD 2>/dev/null)" || head_c=""
    [ "$head_c" = "$pin_c" ] \
      || die "HEAD is not the release '$PIN' — check it out first (git checkout --no-overwrite-ignore refs/tags/$PIN), then re-run; nothing was installed"
  fi
fi

# ---- 1. the marker -------------------------------------------------------------------------------
MARK="$SELF_ROOT/.tabularium-instance"
if [ -L "$MARK" ]; then
  die ".tabularium-instance is a symlink — remove it by hand; the marker is never followed through a link"
elif [ -e "$MARK" ] && [ ! -f "$MARK" ]; then
  die ".tabularium-instance exists but is not a regular file"
elif [ "$WT_LINKED" -eq 1 ]; then
  # NEVER written in a linked worktree, in either branch. Where the family was read, its marker is
  # the answer and a second copy here could only drift out of agreement with it (which L20 reds).
  # Where it could not be read, writing one would be this script asserting an instance it did not
  # verify — the step that completed the chain in the red-team's N1. It stays the operator's act.
  if [ "$WT_INHERIT" -eq 0 ]; then
    say "marker: not written (a linked worktree never carries one, and the family could not be read — see the warning above)"
  elif [ -f "$MARK" ] && { [ "$(tr -d '\r' < "$MARK" | sed '/^[[:space:]]*$/d' | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')" != "$MODE" ] \
       || [ "$(tr -d '\r' < "$MARK" | sed '/^[[:space:]]*$/d' | awk 'END { print NR }')" != "1" ]; }; then
    # The WHOLE marker must agree, not its first line: `dev` followed by `care` used to be reported as
    # a redundant copy that agrees with the family, while guard L20 rejects the same file as not a
    # readable single line — the installer and the board disagreeing about one tree (PR #1 review).
    # Count logical lines, including an unterminated last line; wc -l counts only newline bytes.
    die "this worktree carries its own .tabularium-instance that is not exactly one line reading '$MODE' — delete it; the instance is inherited from the main checkout (ADR-0050)"
  elif [ -f "$MARK" ]; then
    say "marker: redundant local copy present (reads $MODE, agrees with the family; L20 reads the main checkout's)"
  else
    say "marker: inherited (a linked worktree has none of its own — L20 and pre-push read the main checkout's)"
  fi
elif [ -f "$MARK" ] && [ "$(tr -d '\r' < "$MARK" | sed '/^[[:space:]]*$/d' | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')" = "$MODE" ] \
     && [ "$(tr -d '\r' < "$MARK" | sed '/^[[:space:]]*$/d' | awk 'END { print NR }')" = "1" ]; then
  say "marker: unchanged (.tabularium-instance already reads $MODE)"
else
  printf '%s\n' "$MODE" > "$MARK" || die "cannot write .tabularium-instance"
  say "marker: written (.tabularium-instance = $MODE)"
fi

# ---- 2. the git hooks (dev: all four; CARE: pre-push only, as a belt) -------------------------------
# CARE never commits, so the three commit-path hooks would only double the installed-hook drift surface there —
# but a CARE checkout has an `origin` (DEV), and without pre-push nothing would block a push from it
# (selftest HOOK 15f proves a care-marked tree pushes when the hook is absent). The instance-aware
# pre-push blocks on a `care` marker by itself; installing it in CARE costs nothing and closes that.
case "$MODE" in
  care) HOOKS='pre-push'; H_TOTAL=1 ;;
  *)    HOOKS='pre-commit commit-msg pre-merge-commit pre-push'; H_TOTAL=4 ;;
esac
# ONE hooks directory serves the whole family (`rev-parse --git-path hooks` resolves to the main
# checkout's `.git/hooks` from every worktree), so a hook install from a linked worktree is a change
# to the MAIN checkout and to every sibling — with this worktree's, possibly uncommitted, branch of
# the hook files. Refuse that side effect; the family's hooks already serve this tree.
if [ "$WT_LINKED" -eq 1 ]; then
  say "hooks: shared with the main checkout — not touched from a linked worktree (refresh them by running this installer there)"
else
  command -v git >/dev/null 2>&1 || die "git is not installed, but a $MODE instance installs its git hook(s)"
  xgit -C "$SELF_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "this is not a git work tree, but a $MODE instance installs its git hook(s)"
  hp="$(xgit -C "$SELF_ROOT" rev-parse --git-path hooks 2>/dev/null)" || hp=""
  case "$hp" in
    /*) HOOKS_DIR="$hp" ;;
    ?*) HOOKS_DIR="$SELF_ROOT/$hp" ;;
    *)  HOOKS_DIR="$SELF_ROOT/.git/hooks" ;;
  esac
  mkdir -p "$HOOKS_DIR" || die "cannot create the hooks directory"
  h_written=0; h_same=0
  for h in $HOOKS; do
    src="$SELF_ROOT/checks/git-hooks/$h"
    [ -f "$src" ] && [ ! -L "$src" ] && [ -r "$src" ] || die "checks/git-hooks/$h is missing or unreadable — refusing a partial hook install"
    dst="$HOOKS_DIR/$h"
    if [ -f "$dst" ] && [ ! -L "$dst" ] && [ -x "$dst" ] && cmp -s "$src" "$dst"; then
      h_same=$((h_same+1)); continue
    fi
    [ ! -L "$dst" ] || die "$h in the hooks directory is a symlink — remove it by hand"
    cp "$src" "$dst" || die "cannot install the $h hook"
    chmod +x "$dst" || die "cannot make the $h hook executable"
    h_written=$((h_written+1))
  done
  if [ "$MODE" = "care" ]; then h_what="pre-push only — CARE never commits, the push block is a belt (ADR-0050)"; else h_what="the four commit-path hooks"; fi
  if [ "$h_written" -eq 0 ]; then say "hooks: unchanged ($h_same/$H_TOTAL already current in the repository's hooks directory; $h_what)"
  else say "hooks: written ($h_written of $H_TOTAL installed or refreshed; $h_same already current; $h_what)"; fi
  # Care: a Tabularium hook this mode does not install — left by an earlier mode, or by a release, newer
  # or older, that installed more — is removed, whatever its name, but only on proof: its bytes are
  # checks/git-hooks/<its name> at a local release tag (release_copy). Only from this repository's own
  # hooks directory (a core.hooksPath shared with other repositories is never cleaned), and only a
  # regular, non-sample file. The Tabularium header only picks which files are worth that check (every
  # release's hooks carry it): a headed hook of other bytes — written or edited by the operator — is kept
  # with a warning, and an unheaded one is the operator's, left without a word.
  if [ "$MODE" = "care" ]; then
    own_hd="$(xgit -C "$SELF_ROOT" rev-parse --git-common-dir 2>/dev/null)" || own_hd=""
    case "$own_hd" in /*) ;; ?*) own_hd="$SELF_ROOT/$own_hd" ;; esac
    hd_real="$(cd "$HOOKS_DIR" 2>/dev/null && pwd -P)" || hd_real=""
    own_real=""; [ -z "$own_hd" ] || own_real="$(cd "$own_hd/hooks" 2>/dev/null && pwd -P)" || own_real=""
    if [ -n "$hd_real" ] && [ "$hd_real" = "$own_real" ]; then
      for dst in "$HOOKS_DIR"/*; do
        h="${dst##*/}"
        case "$h" in *.sample) continue ;; esac
        case " $HOOKS " in *" $h "*) continue ;; esac
        [ -f "$dst" ] && [ ! -L "$dst" ] || continue
        h_head="$(head -n 5 "$dst" 2>/dev/null)"   # no pipe into grep -q: under pipefail its SIGPIPE reads as a miss
        grep -q '^# Tabularium ' <<<"$h_head" || continue
        h_rel="$(release_copy "checks/git-hooks/$h" "$dst")"
        case "$h_rel" in
          "same "*)
            if rm -f "$dst"; then say "removed: the $h git hook — ${h_rel#same }'s own, which a care instance does not install (it installs pre-push only)"
            else warn "cannot remove the $h git hook from the hooks directory"; rc_final=1; fi ;;
          *) warn "kept the $h git hook as the operator's: it carries a Tabularium header, but no release here has these bytes as checks/git-hooks/$h (written or edited by hand?) — remove it yourself if it is not yours" ;;
        esac
      done
    fi
  fi
fi

# ---- 3. the DEV remote, from CARE's side ----------------------------------------------------------
if [ "$MODE" = "care" ]; then
  if ! command -v git >/dev/null 2>&1; then
    warn "git is not installed — a CARE instance tracks DEV by fetch and L19's provenance anchor cannot pass without it"; rc_final=0
  elif ! xgit -C "$SELF_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    warn "this is not a git work tree — a CARE instance is a CLONE of DEV at a release tag (L19 will red)"
  elif [ -n "$(xgit -C "$SELF_ROOT" remote 2>/dev/null | grep -x origin || true)" ]; then
    say "origin: present (CARE fast-forwards to a fetched release tag)"
  else
    warn "no git remote 'origin' — CARE tracks DEV by fetch; without it the tag at HEAD proves nothing and L19 reds. Add the DEV remote, then: git fetch --tags"
  fi
fi

# ---- 3b. the adopted release pin (care only; ADR-0050 point 6) --------------------------
# With a tag it was verified in step 0c and is written in step 8, after everything else.
if [ "$MODE" = "care" ] && [ -z "$PIN" ]; then
  if [ -f "$RELPIN" ]; then
    say "release: present (checks/CARE-RELEASE pins an adopted release; L19 checks it against HEAD)"
  else
    warn "no checks/CARE-RELEASE — L19 has no adopted release to anchor HEAD against and will red. Re-run as: checks/install-instance.sh care <release-tag>"
  fi
fi

# ---- 4. the render environment (advised, never created) -------------------------------------------
if [ -d "$SELF_ROOT/.venv-render" ] && [ ! -L "$SELF_ROOT/.venv-render" ]; then
  say "venv: .venv-render/ present"
else
  warn ".venv-render/ absent — handout rendering and sealing are unavailable and the bite suite's renderer bites print SKIP until it exists. Create it by hand (a pinned environment is not something an installer should guess); this script never creates it"
fi

# ---- 4b. private mode's local tools (reported, never installed) ------------------------------------
# One line either way, never a failure: only a person in private mode needs them (Python aside: step 6
# refuses without it). The check itself names each missing tool with its install command
# (tools/private-mode/topics/setup.md).
PMS="$SELF_ROOT/tools/private-mode/check-setup.sh"
if [ -f "$PMS" ] && [ ! -L "$PMS" ]; then
  pms_line="$(bash "$PMS" --summary 2>/dev/null | tail -n 1)"
  if [ -n "$pms_line" ]; then say "$pms_line"
  else warn "tools/private-mode/check-setup.sh printed nothing — run it by hand to see private mode's setup"; fi
else
  warn "tools/private-mode/check-setup.sh is missing — private mode's setup was not checked"
fi

# ---- 5. the token registry -------------------------------------------------------------------------
# Only the PATH is resolved here, and it is never printed: it names a location in the operator's home.
# The pointers are untracked, so a linked worktree has none of its own: when the family was read (step
# 0b), they are read from the main checkout, and the paths written below are the family's.
FAM_CHECKS="$SELF_ROOT/checks"
[ "$WT_INHERIT" -eq 1 ] && [ -n "$WT_MAIN" ] && FAM_CHECKS="$WT_MAIN/checks"
REG_EXT=0; { [ -e "$FAM_CHECKS/FIREWALL-REGISTRY" ] || [ -L "$FAM_CHECKS/FIREWALL-REGISTRY" ]; } && REG_EXT=1
REG_ABS=""
# THE CLASS-LINE TEST, RUN ONCE WITH ITS EXIT CODE CAPTURED (§5 and §6 both key on it).
#   0 = the pre-A2 in-tree layout (the export gate still carries class lines)
#   1 = post-A2 (present, and it carries none)
#   2+ = grep could not read it, or it is a symlink / not a regular file — which is NOT "no class
#        lines". Until 2026-09-07 an unreadable gate fell through to the reassuring "already
#        token-free" branch: the installer told the operator the file holds no token when nobody had
#        looked. A scan rc>=2 is an error, never a clean result (the COMMON guard idiom).
PUBSH="$SELF_ROOT/checks/publish-skeleton.sh"
PUB_PRESENT=0; CLS_RC=1
if [ -e "$PUBSH" ] || [ -L "$PUBSH" ]; then
  PUB_PRESENT=1
  if [ -f "$PUBSH" ] && [ ! -L "$PUBSH" ]; then
    grep -qE '^[[:space:]]*PII_(IDENTITY|CASEREF|CLINICAL|BRAND|CONSENT)=' "$PUBSH" 2>/dev/null; CLS_RC=$?
  else
    CLS_RC=2   # a symlinked or non-regular export gate is never read through (the L15/L20 stance)
  fi
fi
if [ "$REG_EXT" -eq 1 ]; then
  reg="$(registry_path "$FAM_CHECKS")"; reg_rc=$?
  if [ "$reg_rc" -ne 0 ] || [ -z "$reg" ]; then
    warn "checks/FIREWALL-REGISTRY exists but is unusable — not a readable regular file, or it names no path, or the path it names is RELATIVE (it must be absolute; every reader runs from a different working directory) — the flip-time export gate and the CARE relay scan are blind until it resolves"
  elif [ -L "$reg" ]; then
    warn "the registry named by checks/FIREWALL-REGISTRY is a SYMLINK (path withheld) — it is never followed; replace it with the real file"
  elif [ ! -f "$reg" ] || [ ! -r "$reg" ]; then
    warn "the registry named by checks/FIREWALL-REGISTRY is missing or unreadable (path withheld) — restore it from .snapshots/<ts>/external/ before trusting any green"
  else
    # registry_path() already refuses a relative path (review round 4, F5), so this is a belt: if that
    # ever regresses, the deny rules are skipped rather than written against a path that means
    # something different in every working directory.
    case "$reg" in /*) REG_ABS="$reg" ;; *) REG_ABS="" ;; esac
    say "registry: checks/FIREWALL-REGISTRY resolves to a readable registry outside the tree (path withheld)"
    [ -n "$REG_ABS" ] || warn "checks/FIREWALL-REGISTRY names a RELATIVE path — the absolute deny rules cannot be written; make it absolute"
  fi
elif [ "$PUB_PRESENT" -eq 1 ] && [ "$CLS_RC" -ge 2 ]; then
  warn "cannot tell whether checks/publish-skeleton.sh still carries class lines (grep rc=$CLS_RC — unreadable, a symlink, or not a regular file), and there is no checks/FIREWALL-REGISTRY. INSPECT IT BY HAND before trusting either answer: this is not a clean bill of health, it is 'nobody looked'. The export-script deny belt was NOT written for the same reason"
elif [ "$PUB_PRESENT" -eq 1 ] && [ "$CLS_RC" -eq 0 ]; then
  # PRE-A2 ONLY. The same test §6 uses below, and it has to be here: without it this branch fires on
  # every fresh clone of the post-A2 tree — where the export script is tracked, token-free product —
  # and tells the installer to externalize class lines that are not there (drift sweep 2026-09-06).
  say "registry: in-tree layout (the class lines are still in checks/publish-skeleton.sh and there is no checks/FIREWALL-REGISTRY yet) — take them out of the tree into a 0600 file named by checks/FIREWALL-REGISTRY (ADR-0050 A2)"
elif [ "$PUB_PRESENT" -eq 1 ] && [ "$MODE" = "care" ]; then
  # nothing here tells an install used only for care from one that lost its pointer, so both are named
  say "registry: none. An install used only for care needs no token registry and no private-mode identifier file (ADR-0068). An install that relays to a development tree or exports has lost checks/FIREWALL-REGISTRY: restore it from .snapshots/<ts>/external/; until then its relay scan and export stay refused"
elif [ "$PUB_PRESENT" -eq 1 ]; then
  warn "no checks/FIREWALL-REGISTRY — the export gate is present and already token-free (post-A2), so nothing here resolves a registry. Expected in a fresh clone or an exported skeleton, where the pointer is untracked and there may be no registry at all; needed before this tree can run the flip-time export or a CARE relay scan, both of which abort rather than pass without it. Write it by hand — one line, the registry's ABSOLUTE path — or restore it from a snapshot. There are no class lines here to move"
else
  warn "neither checks/FIREWALL-REGISTRY nor checks/publish-skeleton.sh is present — nothing here could scan for a token. In an EXPORT the pointer is untracked and absent by design (the export gate itself does ship); in a CARE instance the relay scan is blind until the pointer is restored"
fi

# ---- 5b. the private-mode identifier's own file (ADR-0050 point 9) --------------------
# The one secret left: the operator cuts it out of its registry class line into a file of its own, by
# hand (ADR-0050 point 9). The read-guard shrinks to that file only when split_unverified() is silent.
PM_ABS=""; SPLIT_VERIFIED=0
pm="$(private_id_path "$FAM_CHECKS")"; pm_rc=$?
if [ "$pm_rc" -eq 2 ]; then
  if [ -n "$REG_ABS" ]; then
    warn "private-mode identifier: not split out of the token registry yet (no checks/PRIVATE-MODE-ID) — the read-guard keeps protecting the whole registry, and the relay scan and the eval's pre-transit scan refuse to run until the split is done (order: ADR-0050 point 9; setup: checks/topics/relay-and-export.md)"
  fi
elif [ "$pm_rc" -ne 0 ]; then
  warn "checks/PRIVATE-MODE-ID exists but is unusable — not a readable regular file, or it names no path, or the path it names is RELATIVE (it must be absolute)"
elif [ -L "$pm" ] || [ ! -f "$pm" ] || [ ! -r "$pm" ]; then
  warn "the private-mode identifier file named by checks/PRIVATE-MODE-ID is missing, unreadable or a symlink (path withheld)"
else
  PM_ABS="$pm"
  pm_why="$(split_unverified "$pm" "$REG_ABS")"
  if [ -z "$pm_why" ]; then
    SPLIT_VERIFIED=1
    say "private-mode identifier: split verified — its own owner-only file, every value in it cut (not copied) from the registry and folded back for the export gate (paths withheld)"
  else
    warn "private-mode identifier: split NOT verified — $pm_why. The read-guard keeps protecting the whole token registry until it verifies"
  fi
fi

# ---- 6. the session read-guard (ADR-0050 A1) ------------------------------------------------------
command -v python3 >/dev/null 2>&1 \
  || die "python3 is not available — .claude/settings.local.json cannot be merged safely; wire the read-guard by hand (tools/claude-hooks/README.md)"
mkdir -p "$SELF_ROOT/.claude" || die "cannot create .claude/"
SETTINGS="$SELF_ROOT/.claude/settings.local.json"
# The export script's own deny rules are wanted only while it still CARRIES class lines (the pre-A2
# layout); after A2 it holds no token and a later round must be able to read it to slim it. Keyed on
# the ONE captured class-line test in §5 — a "cannot tell" (rc>=2) neither writes nor removes a rule.
SCRIPT_GUARD=0; SCRIPT_FREE=0
[ "$CLS_RC" -eq 0 ] && SCRIPT_GUARD=1
[ "$CLS_RC" -eq 1 ] && SCRIPT_FREE=1
python3 - "$SETTINGS" "$REG_ABS" "$SCRIPT_GUARD" "$PM_ABS" "$SPLIT_VERIFIED" "$SCRIPT_FREE" "$MODE" "$SELF_ROOT" <<'PY'
import json, os, re, shlex, sys, tempfile

path = sys.argv[1]
reg, script_guard, pm, verified, script_free, mode, root = (sys.argv[2:9] + [""] * 7)[:7]
verified = verified == "1" and bool(pm)

HOOK_BASE = 'python3 "$CLAUDE_PROJECT_DIR/tools/claude-hooks/registry-read-guard.py"'
# The protected paths travel on the hook's own command line, never in the session's environment.
HOOK_CMD = HOOK_BASE + "".join(
    [" --private " + shlex.quote(pm)] if pm else []) + "".join(
    [" --registry " + shlex.quote(reg)] if reg else []) + (" --split-verified" if verified else "")
# Every tool that runs a shell command is judged like Bash (Monitor, the terminal tool); connector
# tools (mcp__…) and the tools that send a file off this machine are judged for a private-mode
# person's originals (ADR-0029 point 12).
MATCHER  = "Bash|Monitor|mcp__terminal__run_in_terminal|Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Artifact|SendUserFile|mcp__.*"

def refuse(msg):
    print("settings: ERROR — %s" % msg)
    sys.exit(1)

created = not os.path.exists(path)
if created:
    data = {}
else:
    if os.path.islink(path):
        refuse(".claude/settings.local.json is a symlink; refusing to write through it")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError:
        refuse(".claude/settings.local.json is not valid JSON; refusing to rewrite it (fix it by hand)")
    except OSError as exc:
        refuse("cannot read .claude/settings.local.json (%s)" % exc.__class__.__name__)
    if not isinstance(data, dict):
        refuse(".claude/settings.local.json does not hold a JSON object")

# The Tabularium hooks this installer wires: the read-guard everywhere, the context-health notice in
# development trees only — the docs it watches change only there (tools/claude-hooks/README.md).
CH_CMD = 'python3 "$CLAUDE_PROJECT_DIR/tools/claude-hooks/context-health.py"'
CH_MATCHER = "Write|Edit"
def is_rg(h):
    cmd = h.get("command") if isinstance(h, dict) else None
    return isinstance(cmd, str) and (cmd == HOOK_BASE or cmd.startswith(HOOK_BASE + " "))
def is_ch(h):
    cmd = h.get("command") if isinstance(h, dict) else None
    return isinstance(cmd, str) and (cmd == CH_CMD or cmd.startswith(CH_CMD + " "))
want_ch = mode != "care"
# The release notice: care only, and only when this release ships its adapter (a hook naming a missing
# script would be removed again by the leftovers path below at the next run).
RN_CMD = 'python3 "$CLAUDE_PROJECT_DIR/tools/claude-hooks/release-notice.py"'
def is_rn(h):
    cmd = h.get("command") if isinstance(h, dict) else None
    return isinstance(cmd, str) and (cmd == RN_CMD or cmd.startswith(RN_CMD + " "))
want_rn = mode == "care" and bool(root) and os.path.isfile(
    os.path.join(root, "tools", "claude-hooks", "release-notice.py"))

# ---- care: hooks of this installer's own that this tree must not run, by ONE path ----
# A command naming "$CLAUDE_PROJECT_DIR/tools/claude-hooks/<file>" is this project's. It goes when <file>
# is not in this release (python3 exits 2 on it, and Claude Code reads exit 2 from a PreToolUse hook as
# a block), or when it is the context-health notice, which a care tree never runs. Only that hook leaves
# its entry, each removal printed: an entry it shared keeps the operator's hooks and matcher, and only an
# entry left empty goes. The read-guard is set below; nothing else is touched.
OWN = re.compile(r'(?:\$CLAUDE_PROJECT_DIR|\$\{CLAUDE_PROJECT_DIR\})/tools/claude-hooks/([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)')
def stale(h):
    if not isinstance(h, dict) or is_rg(h) or not isinstance(h.get("command"), str):
        return None
    for rel in OWN.findall(h["command"]):
        if ".." not in rel.split("/") and not os.path.isfile(os.path.join(root, "tools", "claude-hooks", rel)):
            return "runs tools/claude-hooks/%s, which this release does not ship" % rel
    if is_ch(h) and not want_ch:
        return "runs tools/claude-hooks/context-health.py, which a care instance does not run"
    return None
pruned = ch_removed = 0
if mode == "care" and root and isinstance(data.get("hooks"), dict):
    for event in list(data["hooks"]):
        entries = data["hooks"][event]
        if not isinstance(entries, list):
            continue
        kept_entries, here = [], 0
        for entry in entries:
            hl = entry.get("hooks") if isinstance(entry, dict) else None
            if not isinstance(hl, list) or not hl:
                kept_entries.append(entry)
                continue
            kept = []
            for h in hl:
                why = stale(h)
                if why is None:
                    kept.append(h)
                    continue
                here += 1
                ch_removed += 1 if is_ch(h) else 0
                print("removed: the settings hook (%s) that %s" % (str(event)[:40], why))
            if len(kept) != len(hl):
                entry["hooks"] = kept
            if kept:
                kept_entries.append(entry)
        if here:
            pruned += here
            if kept_entries:
                data["hooks"][event] = kept_entries
            else:
                del data["hooks"][event]

# ---- the PreToolUse hook: one entry of its own, its command line carrying the current protected paths ----
hooks = data.setdefault("hooks", {})
if not isinstance(hooks, dict):
    refuse("'hooks' is present but is not an object")
pre = hooks.setdefault("PreToolUse", [])
if not isinstance(pre, list):
    refuse("'hooks.PreToolUse' is present but is not a list")

def own_entry(entries, is_ours, matcher, new_hook, command=None):
    """Keep one hook of ours, alone in an entry under `matcher`. One found in an entry it shares with
    other hooks moves out, so those hooks keep their own matcher. Returns (present, changes)."""
    present, changes, home, first, kept = False, 0, None, None, []
    for entry in entries:
        hs = entry.get("hooks") if isinstance(entry, dict) else None
        mine = [h for h in hs if is_ours(h)] if isinstance(hs, list) else []
        if not mine:
            kept.append(entry)
            continue
        present = True
        if first is None:
            first = mine[0]
        rest = [h for h in hs if not is_ours(h)]
        if home is None and not rest:
            home = entry
            if len(mine) > 1:
                entry["hooks"] = mine[:1]
                changes += 1
            kept.append(entry)
            continue
        changes += 1
        if rest:
            entry["hooks"] = rest
            kept.append(entry)
    if home is None:
        home = {"matcher": matcher, "hooks": [first if first is not None else new_hook]}
        kept.append(home)
    if home.get("matcher") != matcher:
        home["matcher"] = matcher
        changes += 1
    if command is not None and home["hooks"][0].get("command") != command:
        home["hooks"][0]["command"] = command
        changes += 1
    entries[:] = kept
    return present, changes

have_hook, updated = own_entry(pre, is_rg, MATCHER, {
    "type": "command",
    "command": HOOK_CMD,
    "timeout": 10,
    "statusMessage": "registry read-guard",
}, HOOK_CMD)

# ---- the PostToolUse context-health notice: one entry of its own, no arguments, development trees only
# (a care run removed any it found, by the leftovers path above) ----
have_ch = False
ch_updated = 0
if want_ch:
    post = hooks.setdefault("PostToolUse", [])
    if not isinstance(post, list):
        refuse("'hooks.PostToolUse' is present but is not a list")
    have_ch, ch_updated = own_entry(post, is_ch, CH_MATCHER,
                                    {"type": "command", "command": CH_CMD, "timeout": 10})

# ---- the SessionStart release notice: one entry of its own, matcher `startup` (a resumed or compacted
# session is not notified again), care only ----
have_rn = False
rn_updated = 0
if want_rn:
    start = hooks.setdefault("SessionStart", [])
    if not isinstance(start, list):
        refuse("'hooks.SessionStart' is present but is not a list")
    have_rn, rn_updated = own_entry(start, is_rn, "startup",
                                    {"type": "command", "command": RN_CMD, "timeout": 15})

# ---- the deny rules: a second, hook-independent belt for the file tools ----
perms = data.setdefault("permissions", {})
if not isinstance(perms, dict):
    refuse("'permissions' is present but is not an object")
deny = perms.setdefault("deny", [])
if not isinstance(deny, list):
    refuse("'permissions.deny' is present but is not a list")

def pair(target):
    return ["Read(%s)" % target, "Edit(%s)" % target]

want, drop = [], []
script_rules = pair("./checks/publish-skeleton.sh")
if script_guard == "1":            # the in-tree script still carries class lines
    want += script_rules
elif script_free == "1":           # token-free tracked product: the pre-A2 belt only blocks real work
    drop += script_rules
# The absolute path spelling (Read(/<abs>) renders as `Read(//Users/…)`), so the belt follows each
# file out of the tree. No path is ever printed by this script.
want += pair("./checks/PRIVATE-MODE-ID")
if pm:
    want += pair("/" + pm)
registry_rules = pair("./checks/FIREWALL-REGISTRY") + (pair("/" + reg) if reg else [])
if verified:                       # the split verified: the registry is no longer secret from sessions
    drop += registry_rules
else:
    want += registry_rules
added = removed = 0
for rule in want:
    if rule not in deny:
        deny.append(rule)
        added += 1
for rule in drop:
    while rule in deny:
        deny.remove(rule)
        removed += 1

changed = (created or (not have_hook) or (want_ch and not have_ch) or (want_rn and not have_rn)
           or updated > 0 or ch_updated > 0 or rn_updated > 0 or pruned > 0 or added > 0 or removed > 0)
if changed:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        refuse("cannot write .claude/settings.local.json (%s)" % exc.__class__.__name__)
    print("settings: written (%s; read-guard hook %s; context-health hook %s; %s%d deny rule(s) added, %d removed)"
          % ("created" if created else "merged",
             "added" if not have_hook else ("updated" if updated else "present"),
             ("removed (care)" if ch_removed else "not installed (care)") if not want_ch else (
                 "added" if not have_ch else ("updated" if ch_updated else "present")),
             ("release-notice hook %s; " % ("added" if not have_rn else ("updated" if rn_updated else "present")))
             if want_rn else "",
             added, removed))
else:
    print("settings: unchanged (read-guard hook%s%s and all %d deny rule(s) already in place)"
          % (", context-health hook" if want_ch else "", ", release-notice hook" if want_rn else "", len(want)))
PY
prc=$?
[ "$prc" -eq 0 ] || rc_final=1

# ---- 6b. skills of a release that this release does not ship (care only) -------------------------
# What a red release or a rollback, to an older release or a newer one, leaves behind. A skill folder
# is removed only when it is exactly what an installer writes — a folder holding SKILL.md alone — this
# release carries no source for it (the source test install_skill applies), and its bytes are that
# skill's own in some release here: `tools/claude-skills/<name>/SKILL.md` at a local release tag (the
# name rule is check.sh's --release-name; release_copy). Ownership comes from the releases, not from a
# list of names, so a skill a later release added is recognised too. A skill of other bytes is the
# operator's and stays; when a release once shipped a skill of that name, a warning says so (an edited
# copy of a released skill).
if [ "$MODE" = "care" ] && [ -d "$SELF_ROOT/.claude/skills" ] && [ ! -L "$SELF_ROOT/.claude/skills" ]; then
  for s_dir in "$SELF_ROOT"/.claude/skills/*; do
    s="${s_dir##*/}"
    { [ -f "$SELF_ROOT/tools/claude-skills/$s/SKILL.md" ] && [ ! -L "$SELF_ROOT/tools/claude-skills/$s/SKILL.md" ]; } && continue
    { [ -d "$s_dir" ] && [ ! -L "$s_dir" ] && [ -f "$s_dir/SKILL.md" ] && [ ! -L "$s_dir/SKILL.md" ] \
      && [ "$(ls -A "$s_dir" 2>/dev/null)" = "SKILL.md" ]; } || continue
    s_rel="$(release_copy "tools/claude-skills/$s/SKILL.md" "$s_dir/SKILL.md")"
    case "$s_rel" in
      "same "*)
        if rm -f "$s_dir/SKILL.md" && rmdir "$s_dir"; then say "removed: the $s skill — ${s_rel#same }'s own copy, which this release does not ship"
        else warn "cannot remove .claude/skills/$s"; rc_final=1; fi ;;
      "named "*)
        warn "kept .claude/skills/$s as the operator's: ${s_rel#named } shipped a skill of that name, but no release here has these bytes (an edited copy of a released skill?) — remove it yourself if it is not yours" ;;
    esac
  done
fi

# ---- 7. the build-session skill (ADR-0053)--------------------------------------------------------
# `/architect` is the operator's declaration that a session is working on the TOOL, not on a person.
# Installed ONLY into a development instance: in CARE its absence is the refusal, and an absent
# command is a louder, less forgeable "no" than a body that talks itself out of running. The body is
# a pointer — every rule it names lives in a tracked, gated file — because `.claude/` is untracked
# (RECORD-SET `tooling`), so this copy can drift from its source exactly as an installed hook can.
# Skill format, not the legacy `.claude/commands/` one.
SKILL_SRC="$SELF_ROOT/tools/claude-skills/architect/SKILL.md"
SKILL_DST_DIR="$SELF_ROOT/.claude/skills/architect"
SKILL_DST="$SKILL_DST_DIR/SKILL.md"
case "$MODE" in
  care)
    if [ -e "$SKILL_DST" ] || [ -L "$SKILL_DST" ]; then
      warn "the build-session skill is present in a CARE instance — remove $SKILL_DST by hand; a care checkout never edits a tracked file (L19)"
      rc_final=1
    else
      say "build-session skill: not installed (CARE — by design; its absence is the refusal, ADR-0053)"
    fi ;;
  *)
    if [ -f "$SKILL_SRC" ] && [ ! -L "$SKILL_SRC" ] && [ -r "$SKILL_SRC" ]; then
      if [ -L "$SKILL_DST" ]; then
        warn "$SKILL_DST is a symlink — remove it by hand; refusing to write through it"; rc_final=1
      elif [ -f "$SKILL_DST" ] && cmp -s "$SKILL_SRC" "$SKILL_DST"; then
        say "build-session skill: unchanged (already byte-identical to its tracked source)"
      else
        mkdir -p "$SKILL_DST_DIR" || die "cannot create the build-session skill directory"
        cp "$SKILL_SRC" "$SKILL_DST" || die "cannot install the build-session skill"
        cmp -s "$SKILL_SRC" "$SKILL_DST" || die "the build-session skill did not land byte-identical"
        say "build-session skill: written (invoke it with /architect to open a build session)"
      fi
    else
      warn "tools/claude-skills/architect/SKILL.md is missing or unreadable — /architect will not exist in this tree"
      rc_final=1
    fi ;;
esac

# ---- 7b. the care-side skill: /private ---------------------------------------------------------------
# Unlike `/architect` it serves CARE sessions, so it installs into EVERY instance — CARE most of all.
# `/private` (ADR-0029 point 10) is the operator's declaration of a private-mode session.
# Same drift class as the build-session skill (an untracked copy of a tracked source), same
# byte-identity rule. (The `interview` skill was retired on 2026-10-19, ADR-0041 point 9; a care run
# removes an installed copy by the leftovers path above.)
install_skill(){ # $1 = skill dir · $2 = label · $3 = the "written" hint · $4 = what goes missing
  _cs_src="$SELF_ROOT/tools/claude-skills/$1/SKILL.md"
  _cs_dir="$SELF_ROOT/.claude/skills/$1"
  _cs_dst="$_cs_dir/SKILL.md"
  if [ -f "$_cs_src" ] && [ ! -L "$_cs_src" ] && [ -r "$_cs_src" ]; then
    if [ -L "$_cs_dst" ]; then
      warn "$_cs_dst is a symlink — remove it by hand; refusing to write through it"; rc_final=1
    elif [ -f "$_cs_dst" ] && cmp -s "$_cs_src" "$_cs_dst"; then
      say "$2: unchanged (already byte-identical to its tracked source)"
    else
      mkdir -p "$_cs_dir" || die "cannot create the $2 directory"
      cp "$_cs_src" "$_cs_dst" || die "cannot install the $2"
      cmp -s "$_cs_src" "$_cs_dst" || die "the $2 did not land byte-identical"
      say "$2: written ($3)"
    fi
  else
    warn "tools/claude-skills/$1/SKILL.md is missing or unreadable — $4 will not exist in this tree"
    rc_final=1
  fi
}
install_skill private "private-session skill" "invoke it with /private to open a private-mode care session" "/private"

# ---- 7c. the guard-admission skill (ADR-0059 point 4) — development trees only ---------------------
# Build sessions propose controls; a care checkout never does, so it gets nothing — and care
# sessions carry no build machinery in their skill list.
case "$MODE" in
  care) : ;;
  *) install_skill guard-admission "guard-admission skill" "it fires before a new guard or control is proposed" "the guard-admission skill" ;;
esac

# ---- 7d. the update skill (ADR-0055 companion, accepted 2026-10-25) — care only ---------------------
# `/update` runs checks/adopt-release.sh at the operator's word; the release notice points to it. A
# development tree cuts releases and never adopts one, so it gets nothing.
case "$MODE" in
  care) install_skill update "update skill" "invoke it with /update to adopt a newer release" "/update" ;;
  *) : ;;
esac

# ---- 8. the release pin, LAST (care <tag> only; verified in step 0c) --------------------------------
# Written only when every action above succeeded: an install that failed, or was interrupted before
# this line, leaves the previous pin, so L19 stays red against a moved HEAD and a re-run of the same
# adoption still knows the way back.
if [ "$MODE" = "care" ] && [ -n "$PIN" ]; then
  if [ "$rc_final" -ne 0 ]; then
    warn "release: NOT written — an action above failed, so checks/CARE-RELEASE still names the release pinned before. Fix the failure, then re-run: checks/install-instance.sh care $PIN"
  elif [ -f "$RELPIN" ] \
       && [ "$(tr -d '\r' < "$RELPIN" | sed '/^[[:space:]]*$/d' | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')" = "$PIN" ] \
       && [ "$(tr -d '\r' < "$RELPIN" | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')" = "1" ]; then
    say "release: unchanged (checks/CARE-RELEASE already pins $PIN)"
  else
    printf '%s\n' "$PIN" > "$RELPIN" || die "cannot write checks/CARE-RELEASE"
    say "release: written (checks/CARE-RELEASE = $PIN)"
  fi
fi

if [ "$rc_final" -eq 0 ]; then
  say "install-instance: done — now run checks/check.sh (L20 must agree with what this tree actually holds)"
else
  printf 'install-instance: one or more actions FAILED — see the lines above.\n' >&2
fi
exit "$rc_final"
