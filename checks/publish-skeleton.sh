#!/usr/bin/env bash
# publish-skeleton.sh — build a PII-free public export of the reusable system skeleton and
# (optionally) push it to a remote the operator names EXPLICITLY. Run from the repo root.
#
# WHAT THIS IS, SINCE ADR-0050 (2026-09-06). This was the export half of a firewall that also ran at
# every session (guards L9/L12/L18) because the product and the family's records shared one tree.
# They no longer do: DEV holds the product and never a record, CARE holds the records and is never
# developed. Those three guards are retired; THIS script survives, slimmed, as the **flip-time gate**
# — the one moment ADR-0013's identity-AND-clinical-fingerprint control still has something to do,
# because a public flip must not carry an authoring accident out of any tree it is run from. It is
# tracked product now (it holds no token — the classes live outside every work tree, ADR-0050 A2),
# so git supplies the history and conflict detection the old tracked digest sidecar stood in for.
#
# SAFETY MODEL:
#  - Exports an ALLOW-LIST only — never a push of the local repo. Publishing is always an export carrying
#    none of DEV's history, never a visibility flip: DEV's own history stays on its private remote, and
#    the records have no remote of any kind (ADR-0050).
#  - Runs a PII firewall grep over the export and ABORTS on any match.
#  - Asserts no denied (PII) path slipped in.
#  - A RELEASE IS BUILT FROM ITS TAG (ADR-0066): the tag's committed tree, never the working tree, and
#    the tag travels with it, so a public clone can pin what it adopted. An untagged source makes no
#    export: without a tag there is no commit, no tag and nothing to push, only the scan.
#  - The public copy's history is its releases: the first is a root commit, each later one APPENDS one
#    commit to the public main. Nothing is force-pushed, and DEV's own history never enters it.
#  - Pushes only with --push, and only to an EXPLICIT $REMOTE — there is deliberately NO default remote
#    (an old default pointed at a torn-down repository; stale-narrative fix 2026-07-04).
#  - NEVER touches the local repo or its .git.
#
# Usage:
#   checks/publish-skeleton.sh                  # scan only: the working tree's allow-listed files
#   checks/publish-skeleton.sh vX.Y.Z           # release build in a temp dir: scan, one commit, the tag
#   REMOTE=<url> checks/publish-skeleton.sh vX.Y.Z           # the same, on top of the public main (read only)
#   REMOTE=<url> checks/publish-skeleton.sh vX.Y.Z --push    # and push it; refused under the hold
set -euo pipefail
# Hooks export GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE (ABSOLUTE in a linked worktree). Inherited, they
# re-target every `git` below at the REAL repo: `git init -q` re-initialises it (core.bare flip),
# `git add -A` replaces the in-flight index, and the export commit + `git branch -M main` land on the
# live branch — the header promise ("NEVER touches the local repo or its .git") holds only with these
# unset. Same hazard + same line as retire-worktree.sh (2026-07-19 pinned cause); re-found in the
# publisher by the 2026-08-23 technical audit (the selftest runs this script under the pre-commit hook).
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY
SRC="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${REMOTE:-}"
PUSH="no"; TAG=""
for _arg in "$@"; do
  case "$_arg" in
    --push) PUSH="yes" ;;
    --*|'') echo "usage: checks/publish-skeleton.sh [vX.Y.Z] [--push]" >&2; exit 2 ;;
    *) [ -z "$TAG" ] || { echo "usage: checks/publish-skeleton.sh [vX.Y.Z] [--push]" >&2; exit 2; }
       TAG="$_arg" ;;
  esac
done
if [ "$PUSH" = "yes" ] && [ -z "$REMOTE" ]; then
  echo "ABORT: --push requires an explicit REMOTE=git@github.com:<owner>/<repo>.git (no default, by design)." >&2
  exit 1
fi

# --- PUBLISH HOLD (enforceable gate) ---
# Each export push needs an explicit, current operator decision (contributing/instances.md). The hold
# is a file the operator must remove DELIBERATELY to lift it — so no agent/script/automation can push
# by inference. Dry build (no --push) is always allowed for inspection.
if [ "$PUSH" = "yes" ] && [ -f "$SRC/checks/PUBLISH-HOLD" ]; then
  echo "ABORT: publishing is HELD — '$SRC/checks/PUBLISH-HOLD' is present." >&2
  echo "Each export needs an explicit operator decision; remove that file deliberately to lift the hold." >&2
  exit 1
fi

# --- THE RELEASE SOURCE (ADR-0066) ---
# A public copy without its tag cannot pass the board's release check, so nothing untagged is ever
# pushed. With a tag, the build reads the tag's committed tree and carries the tag's note: a release
# note is what the shipped /update skill reads for a release's extra steps. The running script must be
# the tag's own: its ALLOW list and scans decide what ships. The hold above stays first, so a held run
# touches no git at all.
if [ "$PUSH" = "yes" ] && [ -z "$TAG" ]; then
  echo "ABORT: --push needs a release tag: checks/publish-skeleton.sh vX.Y.Z --push. An untagged source is never published." >&2
  exit 1
fi
BUILD_SRC="$SRC"
TAG_NOTE=""
if [ -n "$TAG" ]; then
  # no leading zeros: v1.02.0 and v1.2.0 would be one number under two names
  printf '%s\n' "$TAG" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' || {
    echo "ABORT: '$TAG' is not a release name: a release is an annotated tag named exactly vMAJOR.MINOR.PATCH, with no leading zeros." >&2; exit 1; }
  _tag_type="$(git -C "$SRC" cat-file -t "refs/tags/$TAG" 2>/dev/null)" || _tag_type=""
  case "$_tag_type" in
    tag) ;;
    '') echo "ABORT: no tag $TAG in this checkout: cut the release first (contributing/releases.md)." >&2; exit 1 ;;
    *)  echo "ABORT: $TAG is not an annotated tag, so it is not a release (contributing/releases.md)." >&2; exit 1 ;;
  esac
  # A release is a tag on a main commit, pushed (contributing/releases.md): origin, read now, must carry this
  # very tag, and its commit must be on origin's main as it is now. A tag cut on a branch, or moved here, is
  # not one; neither is a commit a stale remote-tracking ref still names.
  _tag_oid="$(git -C "$SRC" rev-parse --verify --quiet "refs/tags/$TAG")" || _tag_oid=""
  _origin_refs="$(git -C "$SRC" ls-remote origin refs/heads/main "refs/tags/$TAG" 2>/dev/null)" || {
    echo "ABORT: cannot read this checkout's origin, so $TAG cannot be shown to be a pushed release; failing closed." >&2; exit 1; }
  if [ -z "$_tag_oid" ] || [ "$(printf '%s\n' "$_origin_refs" | awk -F'\t' -v t="refs/tags/$TAG" '$2 == t { print $1 }')" != "$_tag_oid" ]; then
    echo "ABORT: $TAG is not on origin as it is here: push the release tag first, and never move one." >&2; exit 1
  fi
  _origin_main="$(printf '%s\n' "$_origin_refs" | awk -F'\t' '$2 == "refs/heads/main" { print $1 }')"
  if [ -z "$_origin_main" ] || ! git -C "$SRC" merge-base --is-ancestor "refs/tags/$TAG^{commit}" "$_origin_main" 2>/dev/null; then
    echo "ABORT: $TAG's commit is not on origin's main as it is now: a release is cut on main. (If origin's main is newer than this checkout, fetch first.)" >&2; exit 1
  fi
  if ! git -C "$SRC" cat-file blob "refs/tags/$TAG:checks/publish-skeleton.sh" 2>/dev/null | cmp -s - "$SRC/checks/publish-skeleton.sh"; then
    echo "ABORT: this export script is not $TAG's own: run it from the tag (git switch --detach $TAG)." >&2; exit 1
  fi
  _tag_work="$(mktemp -d)"
  trap 'rm -rf "$_tag_work"' EXIT
  BUILD_SRC="$_tag_work/tree"; TAG_NOTE="$_tag_work/note"
  mkdir -p "$BUILD_SRC"
  if ! git -C "$SRC" archive --format=tar "refs/tags/$TAG^{commit}" | tar -xf - -C "$BUILD_SRC"; then
    echo "ABORT: could not read $TAG's committed tree; failing closed." >&2; exit 1
  fi
  # git archive applies attributes (export-ignore, export-subst, filters), from the tree and from this
  # checkout's untracked info/attributes. What was copied must be the tag's own blobs, byte for byte.
  ( cd "$BUILD_SRC" && find . \( -type f -o -type l \) | sed 's|^\./||' | LC_ALL=C sort ) > "$_tag_work/paths" \
    && sed "s|^|$BUILD_SRC/|" "$_tag_work/paths" | git -C "$SRC" hash-object --no-filters --stdin-paths > "$_tag_work/hashes" \
    && paste -d' ' "$_tag_work/hashes" "$_tag_work/paths" | LC_ALL=C sort > "$_tag_work/got" \
    && git -C "$SRC" ls-tree -r -z "refs/tags/$TAG^{commit}" | tr '\0' '\n' \
       | awk -F'\t' '{ split($1, m, " "); if (m[2] == "blob") print m[3] " " $2 }' | LC_ALL=C sort > "$_tag_work/want" || {
    echo "ABORT: could not compare $TAG's committed tree with its copy; failing closed." >&2; exit 1; }
  if ! cmp -s "$_tag_work/got" "$_tag_work/want"; then
    echo "ABORT: $TAG's tree did not arrive byte for byte (an attribute such as export-subst or export-ignore, in the tree or in this checkout's info/attributes); failing closed." >&2; exit 1
  fi
  # The note, byte for byte, without a signature: a signed tag's signature carries the signer's key, which
  # leads back to its owner and is no token any scan could see. The message is what follows the tag
  # object's header; git names the signature, and the lines cut from the end must be exactly it.
  _tag_sig="$(git -C "$SRC" for-each-ref --format='%(contents:signature)' "refs/tags/$TAG")" \
    && git -C "$SRC" cat-file tag "refs/tags/$TAG" | LC_ALL=C sed '1,/^$/d' > "$TAG_NOTE" || {
    echo "ABORT: could not read $TAG's note; failing closed." >&2; exit 1; }
  if [ -n "$_tag_sig" ]; then
    LC_ALL=C awk -v body="$_tag_work/body" -v sig="$_tag_work/sig" '
      { l[NR] = $0 }
      /^-----BEGIN (PGP SIGNATURE|PGP MESSAGE|SSH SIGNATURE|SIGNED MESSAGE)-----$/ { s = NR }
      END { if (!s) exit 3; for (i = 1; i < s; i++) print l[i] > body; for (i = s; i <= NR; i++) print l[i] > sig }
    ' "$TAG_NOTE" && [ "$(cat "$_tag_work/sig")" = "$_tag_sig" ] && : >> "$_tag_work/body" && mv "$_tag_work/body" "$TAG_NOTE" || {
      echo "ABORT: could not separate $TAG's signature from its note; failing closed." >&2; exit 1; }
  fi
fi

# --- ALLOW-LIST: the reusable skeleton only (no patient data) ---
ALLOW=(
  README.md
  NOTICE.md
  CITATION.cff
  LICENSE
  TRADEMARKS.md
  CONTRIBUTING.md
  contributing
  CLAUDE.md
  SETUP.md
  AGENTS.md
  .gitignore .gitattributes
  .github/workflows/skeleton-check.yml
  .github/ISSUE_TEMPLATE/report.md
  .github/readme-banner.svg
  checks/check.sh checks/snapshot.sh checks/backup-tree.sh checks/selftest.sh checks/confirms.sh checks/README.md
  checks/topics
  checks/retire-worktree.sh
  checks/backup-offsite.sh
  checks/RECORD-SET checks/install-instance.sh checks/relay-scan.sh checks/adopt-release.sh
  # The Python suites the shipped selftest must find; checks/PYTHON-SUITES-DEV, the development
  # tree's own, stays out with the folders it names.
  checks/PYTHON-SUITES
  checks/config-paths.sh
  # Shows the private-mode identifier file in Finder at intake (a number page's setup, tools/private-mode/numbers/).
  checks/reveal-private-id.sh
  checks/setup-mac.sh
  # The care-side release notice (ADR-0055 companion, accepted 2026-10-25): the shipped installer wires
  # its adapter and the /update skill into every care instance.
  checks/release-notice.sh
  checks/publish-skeleton.sh
  checks/git-hooks
  adr
  _templates
  tools/private-mode
  tools/person_ownership
  tools/handout_attest
  # The large-original viewer (ADR-0037 §14): the intake checklist names it.
  tools/original_view
  # The on-screen interview capture (ADR-0041 point 3): the keystone and the filing
  # procedure name it.
  tools/interview_capture
  tools/claude-hooks/README.md
  tools/claude-hooks/registry-read-guard.py
  tools/claude-hooks/test_registry_guard.py
  tools/claude-hooks/context-health.py
  tools/claude-hooks/release-notice.py
  tools/claude-hooks/test_context_health.py
  # The build-session declaration (ADR-0053). Ships so an adopter can OPEN and MODIFY it — the
  # care/build split is part of the methodology, not one instance's private wiring. Named as a
  # FILE, not the directory, on the claude-hooks precedent: a future skill must be promoted
  # deliberately, never swept in by a directory entry.
  tools/claude-skills/architect/SKILL.md
  # The private-mode session declaration (ADR-0029 point 10) — same reasoning, same
  # file-not-directory rule.
  tools/claude-skills/private/SKILL.md
  # The guard-admission skill (ADR-0059 point 4; promoted to ship by the operator on
  # 2026-10-11): CONTRIBUTING.md names it as the first step for any new or tightened control, so an
  # export without it would carry a dangling pointer. The installer puts it in development trees only.
  tools/claude-skills/guard-admission/SKILL.md
  # The update skill (ADR-0055 companion, accepted 2026-10-25): the release notice points to it, and
  # the installer puts it in care trees only. Same file-not-directory rule.
  tools/claude-skills/update/SKILL.md
  # The skills folder's own README: one line per skill and how to install them.
  tools/claude-skills/README.md
  reference-library/README.md
  _shared/README.md
  # --- evals/ (ADR-0049 publish posture, decided 2026-09-06) -----------------------------------
  # The behavioral suite ships: a recipient adapting this skeleton should be able to eval their own
  # adaptation, and the cases are synthetic by construction (`evalperson-*`, `Drug X`, `LAB-KFN`).
  # `evals/results/` (the run ledgers and score file) is tracked in DEV and never ships: no ALLOW entry, and deny-listed below.
  # THE CASES ARE LISTED ONE BY ONE, AND `evals/cases` AS A DIRECTORY IS NOT AN ENTRY. That is the
  # holdout convention, made structural: a new case file appears in the tree private, and becomes
  # public only by a deliberate edit here plus a dry export. Public cases can be trained on, so the
  # suite keeps room for a held-back set; `evals/cases/HOLDOUT` names every case file deliberately
  # left out, and `selftest.sh --export` reds a case in neither list. HOLDOUT is
  # itself NOT an entry — the export ships the public cases, not the map of what was withheld — so in
  # an exported tree that file is simply absent and the holdout set reads as empty, which can only
  # make the assert stricter. (ADR-0049 element 16.)
  evals/README.md
  evals/profiles
  evals/harness
  evals/topics
  evals/cases/EV-01-operator-fact.md
  evals/cases/EV-02-inpatient-promotion.md
  evals/cases/EV-03-person-separation.md
  evals/cases/EV-04-context-discipline.md
  evals/cases/EV-05-doc-gap-framing.md
  evals/cases/EV-06-evidence-grade.md
  evals/cases/EV-07-stale-date-fork.md
)
readonly ALLOW
# `readonly` + exactly one consumer loop below: the array cannot be replaced between its declaration
# and the copy, so what a reader sees above is what ships. Until 2026-09-06 the block's exact bytes
# were also digest-checkpointed in a tracked sidecar, because this script was UNTRACKED and a
# clobber that silently dropped a required path would otherwise have been invisible (ADR-0036 D3).
# ADR-0050 makes the script tracked product: git now carries its history and detects the conflict,
# the sidecar (`checks/firewall-registry.sha`) and its refresh tool are deleted, and this preflight
# is the copy loop's own fail-closed check — every ALLOW entry must exist and be nonempty.
# SELF-SCAN (new since this file joined its own ALLOW list): the export now contains this script, so
# the scans below read its own bytes. Its prose therefore has to stay token-free, exactly as every
# other shipped file does — that is the whole reason the class-maintenance history was moved out
# rather than merely trimmed. Two shapes to be careful of when editing: a registry atom quoted in a
# comment (the old failure), and two brand words landing ADJACENT in the wrapped-brand awk's own
# source, which it would then flag in itself. Both are caught by running a dry export.
# --- DENY-LIST: must never appear in the export (belt to the allow-list's braces) ---
# docs/strategy = private packaging/licensing notes; docs/ as a whole is not exported (the rest
# of it is local to DEV's main checkout, never tracked).
# _archive = transient-helper cold storage (ADR-0030), PII-laden operational history — never ships.
# NB this script itself is no longer denied: it carries no token (ADR-0050 A2) and IS product now, so
# the self-reference trap that kept it out of its own export is over. Nothing may be in both lists.
# evals/results = the eval run ledgers, their sidecars and the score file: tracked in DEV, never an
# ALLOW entry, and denied here as a belt, because `evals/harness` IS allow-listed and a sibling
# `results/` is exactly the kind of directory a future ALLOW edit could sweep in by widening one entry to `evals`.
DENY=( patients _shared/med _shared/nmed reference-library/index.md reference-library/whitelist.txt reference-library/blacklist.txt .snapshots outputs cc-prompts docs _archive evals/results )

# A release build goes into an empty folder: a folder that already holds a build would merge its files, and
# its .git would keep an unpublished commit under the new one.
# DEST is overridable (PUBLISH_DEST) so the selftest bite-test can pin the export inside its own
# fixture and reap it; unset (every real run) it is identical to before — a fresh mktemp dir.
DEST="${PUBLISH_DEST:-$(mktemp -d)/tabularium}"; DEST="${DEST%/}"; mkdir -p "$DEST"
if [ -n "$TAG" ]; then
  _dest_list="$(ls -A "$DEST")" || { echo "ABORT: cannot list PUBLISH_DEST; failing closed." >&2; exit 1; }
  [ -z "$_dest_list" ] || {
    echo "ABORT: PUBLISH_DEST is not empty: a release is built into an empty folder, or it would carry what is already there. Name a new one." >&2; exit 1; }
fi
# ^ strip a trailing slash so the exact-path anchor below ($_NOTICE) matches grep's single-slash
#   output. Without it a trailing-slash PUBLISH_DEST makes $_NOTICE ".../export//NOTICE.md" (double slash)
#   which no longer matches ".../export/NOTICE.md" — a fail-CLOSED false positive (top-level NOTICE would
#   abort), never a leak. Unreachable on real runs (default DEST has no trailing slash) but cheap to harden.
#   (Firewall red-team nit, 2026-07-06.)
for p in "${ALLOW[@]}"; do
  _srcp="$BUILD_SRC/$p"
  if [ -L "$_srcp" ]; then
    echo "ABORT: required allow-listed source path is a symlink; failing closed." >&2
    rm -rf "$DEST"; exit 1
  elif [ -f "$_srcp" ]; then
    if [ ! -s "$_srcp" ]; then
      echo "ABORT: required allow-listed file is empty/truncated; export contract is incomplete." >&2
      rm -rf "$DEST"; exit 1
    fi
  elif [ -d "$_srcp" ]; then
    _probe=""; _prc=0; _candidates=""
    _candidates="$(find "$_srcp" -type f -print 2>/dev/null)" || _prc=$?
    if [ "$_prc" -eq 0 ]; then
      while IFS= read -r _candidate; do
        [ -n "$_candidate" ] || continue
        _candidate_rel="${_candidate#"$_srcp"/}"
        _candidate_base="$(basename "$_candidate")"
        case "$_candidate_base" in .DS_Store|Thumbs.db|._*|*.pyc) continue ;; esac
        case "/$_candidate_rel/" in */__pycache__/*) continue ;; esac
        [ -s "$_candidate" ] && { _probe="$_candidate"; break; }
      done <<<"$_candidates"
    fi
    if [ "$_prc" -ne 0 ] || [ -z "$_probe" ]; then
      echo "ABORT: required allow-listed directory has no nonempty regular file or is unreadable; export contract is incomplete." >&2
      rm -rf "$DEST"; exit 1
    fi
  else
    echo "ABORT: required allow-listed path missing — export contract is incomplete; failing closed." >&2
    rm -rf "$DEST"; exit 1
  fi
  mkdir -p "$DEST/$(dirname "$p")"; cp -a "$BUILD_SRC/$p" "$DEST/$(dirname "$p")/"
done

# --- prune OS/editor cruft (cp -a bypasses .gitignore, so .DS_Store et al. ride along) ---
# These carry no PII (firewall passes them) but would ship in the published skeleton — strip them.
# Host-portable: BSD find + bash 3.2 (ADR-0020). Mirrors the .gitignore entries (cc-prompt 009).
find "$DEST" \( -name .DS_Store -o -name '._*' -o -name Thumbs.db -o -name '*.pyc' \) -delete
find "$DEST" -type d -name __pycache__ -prune -exec rm -rf {} \; 2>/dev/null || true

# --- PII firewall: identity AND clinical-fingerprint tokens must not appear in the export ---
# Identity alone is insufficient: an aggregate clinical picture re-identifies a person to anyone
# who knows them, so the registry carries four classes — identity, clinical fingerprint, brand/origin
# framing, and the consent-gated attribute class (ADR-0013, ADR-0027). Real case dates are not kept
# there (ADR-0072): a leftover PII_CASEREF line is sourced like any line and never scanned.
#
# THE CLASSES ARE NOT DESCRIBED HERE, AND MUST NOT BE. This file is tracked product and ships in the
# export it builds; the token set lives in ONE file outside every work tree (ADR-0050 A2) and this
# script sources it below. The maintenance history that used to sit here — which atom was widened
# when, which prose look-alike it collided with, which case dates joined — named those atoms in
# plain text and was removed with the ADR-0050 Part B retirement (2026-09-06). It survives where it
# belongs: in the registry file's own comments, in ADR-0013/0027 abstractly, and in the operator's
# CARE instance. If a class needs changing, edit the registry, not this script.
#
# Upkeep rule (ADR-0013 point 5), stated abstractly because it is the
# rule that keeps the enumerated-token model honest: before a relay or an export, the operator adds
# the handles, identifying particulars and newly distinctive clinical tokens of
# everything filed since the registry last changed (private-mode tokens join their own file at
# intake). A token never ADDED is invisible to every scan here; that limit is the reason the flip
# is also an eyeball, not only a script.
# ---- firewall token registry (ADR-0050 Part A2) ----------------------------------------------
# The PII_* class lines used to live here. They now live in ONE file outside every git work
# tree, named by the untracked one-line config checks/FIREWALL-REGISTRY (the checks/OFFSITE-DEST
# pattern) — so a session running in this repository cannot print them. checks/relay-scan.sh,
# checks/install-instance.sh and checks/snapshot.sh resolve it exactly the same way.
# FAIL CLOSED: no config, no registry file, or a registry others can read ⇒ no scan at all.
_tab_reg_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)" || {
  echo "ABORT: cannot resolve this script's own directory — the token registry is unlocatable" >&2; exit 2; }
_tab_reg_cfg="$_tab_reg_dir/FIREWALL-REGISTRY"
[ -f "$_tab_reg_cfg" ] && [ ! -L "$_tab_reg_cfg" ] && [ -r "$_tab_reg_cfg" ] || {
  echo "ABORT: token-registry config missing/unreadable/symlinked: $_tab_reg_cfg (ADR-0050 A2)" >&2; exit 2; }
_tab_registry="$(awk '{ sub(/[[:space:]]*$/, ""); sub(/^[[:space:]]*/, "") } /^#/ { next } /^$/ { next } { print; exit }' "$_tab_reg_cfg")"
case "$_tab_registry" in
  '~')   _tab_registry="$HOME" ;;
  '~/'*) _tab_registry="$HOME/${_tab_registry#\~/}" ;;
esac
[ -n "$_tab_registry" ] || { echo "ABORT: $_tab_reg_cfg names no registry path" >&2; exit 2; }
[ -f "$_tab_registry" ] && [ ! -L "$_tab_registry" ] && [ -r "$_tab_registry" ] || {
  echo "ABORT: token registry missing/unreadable/symlinked (path named by $_tab_reg_cfg)" >&2; exit 2; }
_tab_reg_mode="$(stat -f '%Lp' "$_tab_registry" 2>/dev/null)" || _tab_reg_mode=""
case "$_tab_reg_mode" in
  [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
  *) _tab_reg_mode="$(stat -c '%a' "$_tab_registry" 2>/dev/null)" || _tab_reg_mode="" ;;
esac
case "$_tab_reg_mode" in
  [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
  *) echo "ABORT: cannot read the token registry's mode — refusing to source it" >&2; exit 2 ;;
esac
case "${_tab_reg_mode: -2}" in
  *[4567]*) echo "ABORT: token registry is group- or world-readable (mode $_tab_reg_mode) — chmod 600 it" >&2; exit 2 ;;
esac
. "$_tab_registry"
[ -n "${PII_IDENTITY:-}" ] && [ -n "${PII_CLINICAL:-}" ] && \
  [ -n "${PII_BRAND:-}" ] && [ -n "${PII_CONSENT:-}" ] || {
  echo "ABORT: the token registry did not define all four PII_* classes" >&2; exit 2; }
# The wrapped-brand adjacency pairs live in the same registry (ADR-0050 A2, second move):
# they are the component words of the guarded brand phrases and are token material like
# any class. FAIL CLOSED — an old registry or a banked copy that predates the move must
# not silently disable the lane, so a missing or empty variable is an ABORT, never a skip.
[ -n "${BRAND_ADJ_PAIRS:-}" ] || {
  echo "ABORT: registry: BRAND_ADJ_PAIRS missing — the wrapped-brand adjacency lane has no pairs to scan for; add it to the token registry (checks/topics/relay-and-export.md)" >&2; exit 2; }
# ---- end firewall token registry --------------------------------------------------------------

# Locale pin (the L3/relay-scan lesson): an inherited C/POSIX locale can make BSD grep silently
# narrow a case-insensitive, word-anchored alternative containing diacritics. Pick and PROVE one
# useful UTF-8 locale, then force every scan below to use it. The invented probe token is not a
# registry atom and its output is discarded; a listed-but-broken locale is not enough.
FW_LC=""
while IFS= read -r _fw_lc; do
  if printf 'ŻÓŁW\n' | LC_ALL="$_fw_lc" grep -qiE '\bżółw\b' >/dev/null 2>&1; then
    FW_LC="$_fw_lc"; break
  fi
done < <(locale -a 2>/dev/null | grep -E '^(en_US|en_GB|C)\.(UTF-8|utf8)$')
if [ -z "$FW_LC" ]; then
  echo "ABORT: no working UTF-8 locale available — diacritic firewall atoms could silently narrow under C/POSIX; export NOT verified." >&2
  rm -rf "$DEST"; exit 2
fi
export LC_ALL="$FW_LC"

PII_REST="$PII_CLINICAL|$PII_BRAND"
echo "== PII firewall scan =="
# --- symlink guard (Tier-S red-team 2026-07-08, MUST-FIX): cp -a preserves symlinks WITHOUT
# dereferencing, and a symlink is invisible to every scan layer — the content greps do not follow
# links, the binary loop below walks -type f only, and the filename scan sees the link's own name
# but never its TARGET path; yet `git add -A` commits the link as a blob whose content IS that
# literal target-path string (a host path, a username, a ../..-escape toward patient data — all
# unscanned). No symlink legitimately ships today, so ANY symlink in the export aborts, fail closed.
_SL="$(find "$DEST" -type l)" || {
  echo "ABORT: symlink enumeration failed — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1; }
if [ -n "$_SL" ]; then
  printf '%s\n' "$_SL"
  echo "ABORT: symlink(s) in export (above) — link targets are unscannable by the firewall; failing closed. Ship real files instead." >&2
  rm -rf "$DEST"; exit 1
fi
# --- binary allowlist (firewall audit 2026-07-08): every content scan below runs with -I, which
# SKIPS binary files wholesale — safe only while the ONLY binaries shipped are the OFL woff/woff2
# fonts (no readable text; ADR-0032). That caveat was prose ("revisit if…"); this makes it
# executable: any OTHER binary in the export (a PDF, an image, a .docx — containers that can carry
# text the -I scans would never read) ABORTS. The arbiter is grep's own classifier — exactly the
# files the -I scans will skip are the files asserted here, so the two cannot drift apart. A file
# grep cannot READ (rc≥2) also lands in the abort branch unless it is a vetted font — fail closed.
# Zero-byte files are exempt explicitly (grep classes them non-text, but no bytes = nothing to skip).
while IFS= read -r _bf; do
  [ -s "$_bf" ] || continue
  if ! grep -qI '' "$_bf" 2>/dev/null; then
    case "$_bf" in
      *.woff|*.woff2) ;;   # the vetted font binaries (ADR-0032)
      *) echo "ABORT: unvetted binary file in export: ${_bf#"$DEST"/} — the -I scans below cannot read it; failing closed. Vet the type here deliberately, or drop the file." >&2
         rm -rf "$DEST"; exit 1 ;;
    esac
  fi
done < <(find "$DEST" -type f)
# Identity class: the TOP-LEVEL NOTICE.md and CITATION.cff ONLY are exempt — the operator's own name
# there is a deliberate, operator-chosen SELF-disclosure (LICENSING-NOTES 2026-07-04; ADR-0013 point 3;
# ADR-0035 point 3). Every OTHER file still aborts on an identity token; and
# both files are still scanned for every other class (clinical/brand/consent). The exemption is
# anchored to the EXACT paths $DEST/NOTICE.md and $DEST/CITATION.cff (see $_NOTICE and $_CITATION below),
# NOT a basename --exclude: a basename match would also exempt any NESTED file that merely shares a name
# (e.g. adr/NOTICE.md) and let an identity token ride out inside it. Full-path anchored, so only the two
# export-root files are exempt and every same-named nested file still aborts (firewall red-team 2026-07-06).
# -I on every scan grep: skip BINARY files (the bundled woff/woff2 fonts, ADR-0032). A coincidental byte
# match inside a font would otherwise print "Binary file … matches" and ABORT a legitimate export; the fonts
# carry no readable PII, and every TEXT file is still fully scanned (Part A step 4 / cc-prompts/029). CAVEAT:
# today the ALLOW-list ships only OFL font binaries (no readable PII); if it ever adds a binary that could
# carry TEXT PII — a PDF, an image, a .docx — revisit this, since -I would skip that file's PII too.
# rc CAPTURED, never swallowed (cc-prompts/031 finding 5; the check.sh L9 per-path-rc lesson applied
# at publish time): rc=1 = scanned clean; rc≥2 = the scan itself ERRORED (invalid ERE from a clobbered
# registry, unreadable file) — NOTHING was verified, so fail CLOSED and abort. Never echo the pattern.
_fwrc=0
FW_HITS="$(grep -rIniE "$PII_REST" "$DEST")" || _fwrc=$?
if [ "$_fwrc" -ge 2 ]; then
  echo "ABORT: firewall scan errored (grep rc=$_fwrc) — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1
fi
# The main ERE is intentionally line-oriented. Carry only the immediately preceding word across
# nonblank hard wraps so a guarded brand phrase cannot evade it through Markdown emphasis,
# punctuation, or a line break. A blank paragraph resets adjacency. The scan prints no matched
# content or path; any awk/read failure aborts rather than becoming a clean-by-silence pass.
# A word is ASCII letters plus the accented Latin letters (U+00C0-U+017F). The awk on macOS and the
# mawk on Linux are byte-oriented — mawk lowercases ASCII only, and a letter class there cannot see a
# two-byte letter — so the accented letters are spelled out as literal strings: capitals fold to
# lower case, each letter is swapped for an ASCII code while punctuation and digits are stripped,
# and swapped back per word. Literal strings behave alike in byte- and character-oriented awks.
_BRAND_FILES="$(find "$DEST" -type f)" || {
  echo "ABORT: wrapped-brand file enumeration failed — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1; }
# the tag's note ships too, and is no file of the tree: the lane reads it with them
[ -z "$TAG_NOTE" ] || _BRAND_FILES="$_BRAND_FILES"$'\n'"$TAG_NOTE"
_brand_wrapped_hit=0
while IFS= read -r _tf; do
  [ -n "$_tf" ] || continue
  case "$_tf" in *.woff|*.woff2) continue ;; esac
  if awk -v pairs="$BRAND_ADJ_PAIRS" '
    BEGIN {
      np = split(pairs, _pr, "[|]")
      for (k = 1; k <= np; k++) {
        if (split(_pr[k], _w, " ") != 2 || _w[1] == "" || _w[2] == "") bad = 1
        else { L[k] = "^(" _w[1] ")$"; R[k] = "^(" _w[2] ")$" }
      }
      if (np < 1 || bad) exit 3   # unusable pairs = an UNSCANNED lane: fail closed
      # capitals UP[j] fold to LO[j] (U+0130 folds to ASCII i); AC = every accented lower-case letter
      nu = split("À Á Â Ã Ä Å Æ Ç È É Ê Ë Ì Í Î Ï Ð Ñ Ò Ó Ô Õ Ö Ø Ù Ú Û Ü Ý Þ " \
        "Ā Ă Ą Ć Ĉ Ċ Č Ď Đ Ē Ĕ Ė Ę Ě Ĝ Ğ Ġ Ģ Ĥ Ħ Ĩ Ī Ĭ Į İ Ĳ Ĵ Ķ Ĺ Ļ Ľ Ŀ Ł Ń Ņ Ň Ŋ Ō Ŏ Ő Œ Ŕ Ŗ Ř Ś Ŝ Ş Š Ţ Ť Ŧ Ũ Ū Ŭ Ů Ű Ų Ŵ Ŷ Ÿ Ź Ż Ž", UP, " ")
      nl = split("à á â ã ä å æ ç è é ê ë ì í î ï ð ñ ò ó ô õ ö ø ù ú û ü ý þ " \
        "ā ă ą ć ĉ ċ č ď đ ē ĕ ė ę ě ĝ ğ ġ ģ ĥ ħ ĩ ī ĭ į i ĳ ĵ ķ ĺ ļ ľ ŀ ł ń ņ ň ŋ ō ŏ ő œ ŕ ŗ ř ś ŝ ş š ţ ť ŧ ũ ū ŭ ů ű ų ŵ ŷ ÿ ź ż ž", LO, " ")
      if (nu != 93 || nl != nu) exit 4   # a damaged letter table = an UNSCANNED lane: fail closed
      na = 0
      for (j = 1; j <= nu; j++) if (LO[j] !~ /^[a-z]$/) AC[++na] = LO[j]
      nx = split("ß ı ĸ ŉ ſ", _x, " "); for (j = 1; j <= nx; j++) AC[++na] = _x[j]
      for (j = 1; j <= na; j++) {
        CD[j] = "Q" substr("ABCDEFGHIJKLMNOP", int((j - 1) / 16) + 1, 1) substr("ABCDEFGHIJKLMNOP", (j - 1) % 16 + 1, 1)
        DC[CD[j]] = AC[j]
      }
    }
    /^[[:space:]]*$/ { prev=""; next }
    {
      line=tolower($0)
      gsub(/\]\([^)]*\)/, "]", line)
      gsub(/\]\[[^]]*\]/, "]", line)
      gsub(/<[^>]*>/, " ", line)
      gsub(/&[a-z0-9#]+;/, " ", line)
      if (line ~ /[^\t -~]/) {   # non-ASCII on the line: fold accented capitals, then encode the letters
        for (j = 1; j <= nu; j++) if (index(line, UP[j])) gsub(UP[j], LO[j], line)
        for (j = 1; j <= na; j++) if (index(line, AC[j])) gsub(AC[j], CD[j], line)
      }
      gsub(/[^a-zA-Z]+/, " ", line)   # after tolower, A-Z occur only inside the letter codes
      n=split(line, words, / +/)
      saw=0
      for (i=1; i<=n; i++) {
        word=words[i]; if (word == "") continue
        while (match(word, /Q[A-P][A-P]/)) word = substr(word, 1, RSTART - 1) DC[substr(word, RSTART, 3)] substr(word, RSTART + 3)
        saw=1
        if (prev != "")
          for (k = 1; k <= np; k++)
            if (prev ~ L[k] && word ~ R[k]) exit 42
        prev=word
      }
      if (!saw) prev=""
    }
  ' "$_tf" >/dev/null 2>&1; then _awrc=0; else _awrc=$?; fi
  if [ "$_awrc" -eq 42 ]; then
    _brand_wrapped_hit=1; break
  elif [ "$_awrc" -ne 0 ]; then
    echo "ABORT: wrapped-brand scan errored — export NOT verified; failing closed." >&2
    rm -rf "$DEST"; exit 1
  fi
done <<<"$_BRAND_FILES"
if [ "$_brand_wrapped_hit" -ne 0 ]; then
  echo "ABORT: PII tokens found in the export (wrapped brand phrase; locator withheld). Genericize the source, then retry." >&2
  rm -rf "$DEST"; exit 1
fi
# Identity scan. The render helper's month-array CARVE-OUT (2026-07-06) was retired 2026-09-29: the
# helper prints a numeric footer date and carries no month names (ADR-0032 points 8 and 10), so it
# is scanned like every other file. The top-level NOTICE.md and CITATION.cff below are the ONLY content
# carve-outs left; keep it that way.
# TOP-LEVEL carve-outs, full-path anchored (NOT `--exclude=NOTICE.md`, a BASENAME match that
# would also exempt any nested file named NOTICE.md — e.g. adr/NOTICE.md — and let an identity token
# escape the scan; firewall red-team 2026-07-06). Exact-path anchored: only the export-root files
# match, so a same-named nested file is scanned normally and still aborts.
_NOTICE="$DEST/NOTICE.md"
_CITATION="$DEST/CITATION.cff"
# Helper (a `case` with its ')' patterns cannot live directly inside $(...) — bash misreads the ')' as
# closing the substitution; a function sidesteps that). Prints each identity hit EXCEPT the exempted files'.
_id_scan(){
  grep -rIniE "$PII_IDENTITY" "$DEST" | while IFS= read -r _l; do
    [ -z "$_l" ] && continue
    # Exemptions anchor on the PATH FIELD (text before the first ':'), never the whole hit line — a
    # case glob `*` crosses ':' too, so the old whole-line shapes were CONTENT-FORGEABLE (red-team
    # 2026-08-09: `index.html: © <token>` inside ANY site source satisfied the © carve-out and the
    # token would have shipped). That site arm retired with `site/` on 2026-09-07 (ADR-0051); the
    # anchoring rule it taught still governs the arm below. The second field must be a pure
    # line number, or nothing is exempt —
    # a filename containing ':' (legal in POSIX names) can no longer smuggle a fake path field.
    _lp="${_l%%:*}"
    _ln="${_l#*:}"; _ln="${_ln%%:*}"
    case "$_ln" in ''|*[!0-9]*) _lp="" ;; esac
    case "$_lp" in
      "$_NOTICE"|"$_CITATION") ;;                                                           # top-level NOTICE.md and CITATION.cff ONLY: operator self-disclosure carve-out → drop (exempt)
      *) printf '%s\n' "$_l" ;;                                                              # any other file/line → keep (still aborts)
    esac
  done
  # Surface the SCAN grep's rc explicitly: pipefail alone is MASKABLE here — worse, a broken ERE
  # emits ZERO lines, the while runs zero iterations and exits 0, so the pipeline reports SUCCESS on
  # a scan error (red-team 2026-07-08). Return 0 = scan completed (hits, if any, already printed);
  # ≥2 = the scan itself errored. PIPESTATUS must be read as the VERY NEXT statement after `done` —
  # inserting anything (even an echo) between them silently resets it to that new command's status.
  _idgrc="${PIPESTATUS[0]}"
  [ "$_idgrc" -ge 2 ] && return "$_idgrc"
  return 0
}
_idrc=0
ID_HITS="$(_id_scan)" || _idrc=$?
if [ "$_idrc" -ge 2 ]; then
  echo "ABORT: identity scan errored (rc=$_idrc) — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1
fi
if [ -n "$FW_HITS$ID_HITS" ]; then
  [ -n "$FW_HITS" ] && printf '%s\n' "$FW_HITS"
  [ -n "$ID_HITS" ] && printf '%s\n' "$ID_HITS"
  echo "ABORT: PII tokens found in the export (above). Genericize the source, then retry." >&2
  rm -rf "$DEST"; exit 1
fi
# Two stages SPLIT so the scan grep's rc is not masked by the filter's (pipefail = rightmost nonzero;
# the filter legitimately exits 1 whenever every hit carries a consent marker). Filter keeps || true:
# its pattern is a fixed literal (cannot fail to compile) and rc=1 there is the benign all-marked case.
_cgrc=0
CG_RAW="$(grep -rIniE "$PII_CONSENT" "$DEST")" || _cgrc=$?
if [ "$_cgrc" -ge 2 ]; then
  echo "ABORT: consent scan errored (grep rc=$_cgrc) — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1
fi
CG="$(printf '%s\n' "$CG_RAW" | grep -v '⟨consent:' || true)"
if [ -n "$CG" ]; then
  printf '%s\n' "$CG"
  echo "ABORT: PII tokens found in the export — consent-gated attribute without a consent marker (above)." >&2
  rm -rf "$DEST"; exit 1
fi
# --- filename scan (firewall audit 2026-07-08): the content scans above read file BODIES only —
# a token embedded in a file or directory NAME (the source-file naming convention embeds dates +
# descriptions) would otherwise ship unscanned; the manifest eyeball was the only gate. Paths are
# scanned RELATIVE to $DEST: the absolute prefix is not part of the export and may legitimately
# carry a registry token (a local folder's own name; a selftest PUBLISH_DEST pinned
# inside a fixture tree) — scanning absolute paths would false-abort every real run. Two steps
# (enumerate, then grep the captured list) so each rc surfaces separately (cc-prompts/031
# finding-5 lesson): a failed enumeration or a grep rc≥2 aborts — never "clean by silence".
# NO carve-outs here: the two exempt FILES (top-level NOTICE.md, CITATION.cff) carry no token in their NAMES,
# and a consent marker cannot live in a filename — a token-bearing path fails
# closed and is renamed at the source. This block deliberately runs AFTER the content scans: the
# scan-error bites (selftest) sed-break one PII_* line and assert the CONTENT scan's own abort
# marker — running the (all-classes) filename grep first would shadow those markers with this
# block's; safety is order-independent (every path aborts before "firewall: clean").
FN_LIST="$(cd "$DEST" && find .)" || {
  echo "ABORT: filename enumeration failed — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1; }
_fnrc=0
FN_HITS="$(printf '%s\n' "$FN_LIST" | grep -iE "$PII_IDENTITY|$PII_REST|$PII_CONSENT")" || _fnrc=$?
if [ "$_fnrc" -ge 2 ]; then
  echo "ABORT: filename scan errored (grep rc=$_fnrc) — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1
fi
if [ -n "$FN_HITS" ]; then
  printf '%s\n' "$FN_HITS"
  echo "ABORT: PII token in an export file/dir name (above). Rename at the source, then retry." >&2
  rm -rf "$DEST"; exit 1
fi
# --- the tag's note: it reaches the public copy with the tag and sits in no file above. Every class,
# no carve-out, no consent marker; a hit prints no content. A tag never moves, so the way out is a new
# release with a clean note.
if [ -n "$TAG_NOTE" ]; then
  _ntrc=0
  grep -qiE "$PII_IDENTITY|$PII_REST|$PII_CONSENT" "$TAG_NOTE" || _ntrc=$?
  if [ "$_ntrc" -ge 2 ]; then
    echo "ABORT: note scan errored (grep rc=$_ntrc) — export NOT verified; failing closed." >&2
    rm -rf "$DEST"; exit 1
  elif [ "$_ntrc" -eq 0 ]; then
    echo "ABORT: PII tokens found in $TAG's note (content withheld). A tag never moves: cut a new release with a clean note." >&2
    rm -rf "$DEST"; exit 1
  fi
fi
echo "firewall: clean"
for d in "${DENY[@]}"; do
  [ -e "$DEST/$d" ] && { echo "ABORT: denied path present in export: $d" >&2; rm -rf "$DEST"; exit 1; }
done
# STRUCTURAL belt to that literal one (WP8, 2026-09-06): every DENY entry names a path at the export
# ROOT, so a record directory NESTED under an allow-listed one — a `patients/` inside `_templates/`,
# a `_shared/` inside `adr/` — is invisible to the loop above and to the filename scan (which greps
# names for TOKENS, not for record shapes). `find` catches it by name wherever it sits. The export
# root's own `_shared/` is the single legitimate match (`_shared/README.md` is an ALLOW entry) and is
# exempt by EXACT path, never by basename — a nested same-named directory inherits nothing. Fail
# closed: an enumeration error aborts rather than reading as "none found".
_NEST="$(find "$DEST" -type d \( -name patients -o -name _shared \))" || {
  echo "ABORT: record-directory enumeration failed — export NOT verified; failing closed." >&2
  rm -rf "$DEST"; exit 1; }
while IFS= read -r _nd; do
  [ -n "$_nd" ] || continue
  if [ "$_nd" != "$DEST/_shared" ]; then
    echo "ABORT: record-shaped directory in export: ${_nd#"$DEST"/} — a record directory nested under an allow-listed path; remove it at the source, then retry." >&2
    rm -rf "$DEST"; exit 1
  fi
done <<<"$_NEST"
echo "deny-list: clean"

echo "== export manifest =="; ( cd "$DEST" && find . -type f | sort | sed 's/^/  /' )

# --- the export's own repository (the local repo's .git is never used or touched) ---
# AUTHOR METADATA: the export commit and tag carry one fixed identity: the author named in the exported
# CITATION.cff (its first given-names and family-names keys, so no shipped script holds the name) and the
# GitHub no-reply address below, so GitHub links them to the maintainer's account without exposing an
# inbox; the private development history is never exported. Both are created
# AFTER the firewall pass, so their author/committer/tagger fields are never scanned — the fixed identity below is the whole guarantee. It is passed through
# the GIT_AUTHOR_*/GIT_COMMITTER_* environment, which outranks every git config layer (user.*,
# author.*, committer.*) and any inherited value. Hooks are off, because a global or template hook
# (a sign-off, say) can write an identity into the message, and signing is off, because a signature
# carries the signer's key identity — so no local or global identity can reach them.
_cff_key(){ sed -n "s/^[[:space:]-]*$1:[[:space:]]*//p" "$DEST/CITATION.cff" 2>/dev/null | head -n 1 \
  | tr -d '\r' | sed -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"; }
_cff_family="$(_cff_key family-names)"; _cff_given="$(_cff_key given-names)"
EXPORT_IDENT_NAME="${_cff_given:+$_cff_given }$_cff_family"   # empty: git itself refuses the commit
EXPORT_IDENT_EMAIL="142178223+mtrzes@users.noreply.github.com"
cd "$DEST"
git init -q
git symbolic-ref HEAD refs/heads/main
# no background maintenance in this repository: past about a hundred loose objects git packs them in a
# detached process after a commit, which outlives this script and races anything copying the folder
git config gc.auto 0
git config maintenance.auto false
# --- the public copy, read only: the new commit goes on top of its main, and its tags say whether this
# release may follow them. A pushed tag never moves, and release numbers only rise. A remote that cannot
# be read aborts: an unknown public history must not read as an empty one. Its main must be its newest
# release, so nothing that is not a release (an old display copy, a hosting site's starter README naming
# its account) becomes public history under this one.
if [ -n "$TAG" ] && [ -n "$REMOTE" ]; then
  git remote add origin "$REMOTE" 2>/dev/null || git remote set-url origin "$REMOTE"
  _pub_refs="$(git ls-remote origin 2>/dev/null)" || {
    echo "ABORT: cannot read the public copy at REMOTE; failing closed." >&2; exit 1; }
  _pub_main="$(printf '%s\n' "$_pub_refs" | awk -F'\t' '$2 == "refs/heads/main" { print $1 }')"
  _pub_newest="$(printf '%s\n' "$_pub_refs" | awk -F'\t' '$2 ~ /^refs\/tags\/v[0-9]+\.[0-9]+\.[0-9]+$/ { print substr($2, 12) }' \
    | LC_ALL=C sort -t. -k1,1n -k2,2n -k3,3n | tail -1)"
  if [ -n "$_pub_newest" ]; then
    _higher="$(printf '%s\n%s\n' "$_pub_newest" "${TAG#v}" | LC_ALL=C sort -t. -k1,1n -k2,2n -k3,3n | tail -1)"
    if [ "$_pub_newest" = "${TAG#v}" ]; then
      echo "ABORT: $TAG is already on the public copy, and a pushed tag never moves." >&2; exit 1
    elif [ "$_higher" = "$_pub_newest" ]; then
      echo "ABORT: $TAG is older than the public copy's newest release, v$_pub_newest." >&2; exit 1
    fi
  fi
  if [ -z "$_pub_main" ] && [ -n "$_pub_refs" ]; then
    echo "ABORT: the public copy holds refs but no main (a starter branch, or release tags whose main is gone), so nothing is built on it. Look at what is there; the first release goes into an empty repository." >&2; exit 1
  fi
  if [ -n "$_pub_main" ]; then
    _pub_rel="$(printf '%s\n' "$_pub_refs" | awk -F'\t' -v t="refs/tags/v$_pub_newest" \
      '$2 == t "^{}" { p = $1 } $2 == t { d = $1 } END { print (p != "" ? p : d) }')"
    if [ -z "$_pub_newest" ] || [ "$_pub_rel" != "$_pub_main" ]; then
      echo "ABORT: the public main is not a release this export made (no release tag names it), so nothing is built on it. Look at what is there; the first release goes into an empty repository." >&2; exit 1
    fi
    git fetch -q --no-tags origin refs/heads/main:refs/remotes/origin/main || {
      echo "ABORT: cannot fetch the public main; failing closed." >&2; exit 1; }
    [ "$(git rev-parse refs/remotes/origin/main)" = "$_pub_main" ] || {
      echo "ABORT: the public main moved while this build read it; nothing was built on it. Run again." >&2; exit 1; }
    # every commit already there must be one this export made: a release tag on top of anything else (a
    # starter commit, a private history) would carry that history along as the release's own
    _pub_who="$(git log --format='%an <%ae>|%cn <%ce>' refs/remotes/origin/main | LC_ALL=C sort -u)"
    [ "$_pub_who" = "$EXPORT_IDENT_NAME <$EXPORT_IDENT_EMAIL>|$EXPORT_IDENT_NAME <$EXPORT_IDENT_EMAIL>" ] || {
      echo "ABORT: the public main holds commits this export did not make, so nothing is built on it. Look at what is there; the first release goes into an empty repository." >&2; exit 1; }
    git update-ref refs/heads/main "$_pub_main"
  fi
fi
git add -A
# --- COMMIT-vs-MANIFEST parity (drift sweep 2026-08-01) ---------------------------------------
# Everything above this line reasons about the FILESYSTEM the allow-copy built; `git add -A` then
# applies the SHIPPED .gitignore, which can silently refuse a file the manifest just printed. That
# is not hypothetical: on 2026-07-31 an unanchored `_inbox/` pattern matched the nested
# `_templates/person/med/_inbox/` and dropped its README from the export COMMIT while leaving it in
# the staging TREE — invisible locally (tracked-overrides-ignore) and invisible to the manifest,
# caught only by the published clone's CI. The instance was fixed by anchoring; THIS is the detector,
# and it covers every present and future ignore pattern rather than the one that bit us.
# Fails CLOSED: any divergence in either direction aborts before the commit exists.
_m_fs="$(find . -type f -not -path './.git/*' | sed 's|^\./||' | sort)"
_m_git="$(git ls-files | sort)"
if [ "$_m_fs" != "$_m_git" ]; then
  echo "ABORT: export commit does not match the built manifest — the shipped .gitignore refused a file." >&2
  echo "  in the tree but NOT committed (silently dropped):" >&2
  comm -23 <(printf '%s\n' "$_m_fs") <(printf '%s\n' "$_m_git") | sed 's/^/    /' >&2
  echo "  committed but NOT in the tree (unexpected):" >&2
  comm -13 <(printf '%s\n' "$_m_fs") <(printf '%s\n' "$_m_git") | sed 's/^/    /' >&2
  exit 1
fi
echo "commit parity: clean ($(printf '%s\n' "$_m_git" | grep -c . ) files staged = manifest)"
# ...and staged as the bytes that were scanned: a clean filter or other attribute (from the shipped
# .gitattributes, or this machine's global attributes file) applies at `git add`, after every scan
_st_want="$(git ls-files -s -z | tr '\0' '\n' | awk -F'\t' '{ split($1, m, " "); print m[2] " " $2 }' | LC_ALL=C sort)" \
  && _st_got="$(git ls-files -z | tr '\0' '\n' > .git/tab-paths && git hash-object --no-filters --stdin-paths < .git/tab-paths \
       | paste -d' ' - .git/tab-paths | LC_ALL=C sort)" || {
  echo "ABORT: could not compare the staged files with the scanned ones; failing closed." >&2; exit 1; }
if [ "$_st_want" != "$_st_got" ]; then
  echo "ABORT: staging changed bytes after the scan (a clean filter or attribute); nothing was committed." >&2; exit 1
fi
if [ -z "$TAG" ]; then
  echo ""; echo "Scan complete. No commit and no tag: an untagged source makes no export, so nothing here can be published."
  echo "A release is built from its tag: checks/publish-skeleton.sh vX.Y.Z"
  exit 0
fi
# a release whose exported files match the public main would add an empty commit: stop instead
if git rev-parse --verify --quiet HEAD >/dev/null && git diff --cached --quiet HEAD; then
  echo "ABORT: $TAG changes no exported file since the public copy's newest release, so there is nothing to publish." >&2; exit 1
fi
GIT_AUTHOR_NAME="$EXPORT_IDENT_NAME" GIT_AUTHOR_EMAIL="$EXPORT_IDENT_EMAIL" \
GIT_COMMITTER_NAME="$EXPORT_IDENT_NAME" GIT_COMMITTER_EMAIL="$EXPORT_IDENT_EMAIL" \
  git -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -q -m "Tabularium $TAG"
GIT_COMMITTER_NAME="$EXPORT_IDENT_NAME" GIT_COMMITTER_EMAIL="$EXPORT_IDENT_EMAIL" \
  git -c core.hooksPath=/dev/null -c tag.gpgSign=false -c tag.forceSignAnnotated=false tag -a --cleanup=verbatim -F "$TAG_NOTE" "$TAG"
if [ -n "$REMOTE" ]; then
  echo ""; echo "Release built at: $DEST  (main and $TAG, on top of $REMOTE)"
else
  echo ""; echo "Release built at: $DEST  (main and $TAG; no remote configured — pass REMOTE= to build on the public copy)"
fi

if [ "$PUSH" = "yes" ]; then
  # No force, and both refs or neither: if the public main moved since it was read, the push is
  # rejected and nothing changes. Each push is individually operator-authorized and recorded in
  # checks/PUBLISH-HOLD, which gates this path above.
  git push -q --atomic origin refs/heads/main "refs/tags/$TAG"
  # A push cannot set the public copy's default branch. If it is not main, a plain clone checks out nothing.
  if ! _pub_head="$(git ls-remote --symref origin HEAD 2>/dev/null | awk '$1 == "ref:" { print $2 }')"; then
    echo "PUSHED $TAG to $REMOTE, but its default branch could not be read: check it is main (on GitHub: Settings → Default branch) before anyone clones it." >&2
    exit 3
  fi
  if [ "$_pub_head" != "refs/heads/main" ]; then
    echo "PUSHED $TAG to $REMOTE, but its default branch is not main, so a plain clone would check out nothing." >&2
    echo "Set the public copy's default branch to main (on GitHub: Settings → Default branch) before anyone clones it." >&2
    exit 3
  fi
  echo ""
  echo "✅ PUSHED $TAG to $REMOTE."
  echo "── Next: eyeball the pushed repo file-by-file and confirm it is PII-free."
  echo "   The DEV repository is untouched: this export is an allow-listed copy of the tag's tree, never a"
  echo "   visibility flip of DEV's own history (ADR-0017, ADR-0050, ADR-0066). DEV keeps"
  echo "   pushing to its PRIVATE remote as before — that is not publishing; the records never have"
  echo "   a remote of any kind, and a CARE instance never pushes at all."
else
  echo ""; echo "Dry build complete (no push). When ready:  REMOTE=git@github.com:<owner>/<repo>.git checks/publish-skeleton.sh $TAG --push"
fi
