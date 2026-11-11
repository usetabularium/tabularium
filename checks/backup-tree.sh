#!/usr/bin/env bash
# Whole-tree tarball backup — backup LAYER 2 (see checks/README.md "Version control & backups").
# Includes raw source scans and the rest of the working tree (analysis / handouts / nmed).
# The linked guide owns coverage and the relationship to the snapshot and offsite layers;
# git versions the skeleton only and is NOT a patient-data backup. Run this as an operator habit —
# there is deliberately no daemon (ADR-0031 point 2: no reliance on local scheduled jobs).
#
# Usage: checks/backup-tree.sh [ROOT]
set -uo pipefail
# Recovery artifacts contain the complete private tree. Do not let a permissive caller umask make
# them group/world-readable (the 2026-07-26 backup audit found historical 0644 tarballs).
umask 077
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT" || { echo "FAIL: cannot cd to $ROOT"; exit 2; }
# Fail closed (ADR-0021 stance): refuse to tar the wrong/empty tree. CLAUDE.md marks the repo root —
# without it we would silently archive whatever directory we happen to be in.
[ -f CLAUDE.md ] || { echo "FAIL: not at repo root (CLAUDE.md missing under '$ROOT') — refusing to back up the wrong tree"; exit 2; }
TS="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="outputs/_snapshots"
# Recovery bytes must not be redirected through a symlink into an unintended/shared location.
# Check both path components before and after creation; the repeated check narrows a concurrent
# namespace swap and makes the ordinary pre-existing-symlink case fail closed.
if [ -L outputs ] || [ -L "$DEST" ]; then
  echo "FAIL: backup destination is symlinked — refusing to write private recovery data"
  exit 2
fi
mkdir -p "$DEST" || { echo "FAIL: cannot create backup destination"; exit 2; }
if [ ! -d "$DEST" ] || [ -L outputs ] || [ -L "$DEST" ]; then
  echo "FAIL: backup destination is not a real directory — refusing to write private recovery data"
  exit 2
fi
chmod 700 "$DEST" || { echo "FAIL: cannot restrict backup directory permissions ($DEST)"; exit 1; }
OUT="$DEST/${TS}__worktree.tgz"
PART=""
cleanup_backup(){
  [ -n "${PART:-}" ] && [ -e "$PART" ] && rm -f "$PART"
  return 0
}
trap cleanup_backup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
# Fail closed (ADR-0021): never silently clobber a prior good backup. Two runs in the SAME UTC second
# (back-to-back on a small tree, or a scripted double-invocation) resolve to the same filename; without
# this guard the second `tar -czf` would truncate + overwrite the first — a silent rc=0 loss of a prior
# backup of the irreplaceable raw scans. Refuse instead; rerun >1 s later for a distinct name.
[ -e "$OUT" ] && { echo "FAIL: a layer-2 backup for this second already exists ($OUT) — refusing to overwrite (rerun in >1 s)"; exit 1; }
PART="$(mktemp "$DEST/.${TS}__worktree.tgz.part.XXXXXX")" \
  || { echo "FAIL: cannot atomically create private backup staging file"; exit 1; }
chmod 600 "$PART" || { echo "FAIL: cannot restrict backup staging file permissions"; exit 1; }

# Archive EXPLICIT top-level members — everything except the three regenerable / huge trees:
#   .git       — skeleton-only history; regenerable, its own backup story (ADR-0017).
#   .snapshots — backup layer 1; no point nesting it inside layer 2.
#   outputs    — THIS directory; skipping it stops the tarball swallowing itself (and prior tarballs).
# We SELECT root members rather than `tar . --exclude=./name` because that exclusion is NOT root-anchored:
# BSD (macOS) and GNU tar both match an --exclude name at ANY depth, so a nested dir that merely SHARES a
# name — a `med/sources/outputs/` scan folder, or a vendored / checkout `.git` — would be silently dropped
# from the SOLE backup of the raw evidence (verified on bsdtar 3.5.3; GNU would need --anchored, which BSD
# lacks). Selecting the genuine root entries anchors by construction: tar then recurses into each normally,
# so nothing nested is special-cased. Host-portable: glob + case + positional params (bash 3.2 / BSD).
set --
for e in * .[!.]* ..?*; do
  [ -e "$e" ] || continue                     # unmatched glob stays literal → skip
  case "$e" in .git|.snapshots|outputs) continue ;; esac
  set -- "$@" "$e"
done
[ "$#" -gt 0 ] || { echo "FAIL: no top-level members to back up under '$ROOT'"; exit 1; }
# `--` ends option parsing so a member that happens to start with '-' is treated as a path, not a flag.
# Build under an unmistakable staging name. A caught process interruption can leave `.part.*`, but
# cannot publish that partial under the final name. This script does not yet fsync staged bytes and
# destination-directory metadata, so sudden host power loss is NOT claimed safe.
tar -czf "$PART" -- "$@" ; rc=$?
if [ "$rc" -ne 0 ] || [ ! -s "$PART" ]; then
  echo "FAIL: tarball not created cleanly (tar rc=$rc) — layer-2 backup NOT written"
  exit 1
fi
chmod 600 "$PART" || {
  echo "FAIL: cannot restrict staged backup archive permissions — layer-2 backup NOT written"
  exit 1
}
# Verify the archive is READABLE (not merely non-empty) and capture its member list.
members="$(tar tzf "$PART" 2>/dev/null)"; vrc=$?
n="$(printf '%s\n' "$members" | grep -c .)"
if [ "$vrc" -ne 0 ] || [ "${n:-0}" -eq 0 ]; then
  echo "FAIL: staged tarball unreadable/empty (tar-list rc=$vrc, members=${n:-0}) — layer-2 backup NOT written"
  exit 1
fi
# Atomic, no-clobber publication: a hard-link in the same directory either creates the complete final
# name or fails if a concurrent same-second run won. Unlike `mv`, it never overwrites an existing backup.
if ! ln "$PART" "$OUT" 2>/dev/null; then
  echo "FAIL: final backup name appeared concurrently ($OUT) — refusing to overwrite"
  exit 1
fi
rm -f "$PART" || { echo "WARN: complete backup published but staging link remains ($PART)" >&2; }
PART=""
# NOTE — deliberately NO filename-level "every med/sources file is in the tarball" assert here. An
# earlier version diffed `find` output against `tar tzf` members; that FALSE-FAILED on any non-ASCII scan
# name (find emits raw UTF-8; bsdtar list-mode octal-escapes + NFD-normalizes when the locale is unset)
# and then DELETED the good tarball — worse than the bug it chased, and a live hazard for accented scan
# filenames. Coverage is instead guaranteed STRUCTURALLY: the member-selection above cannot
# drop a nested dir (there is no name-matching exclude to over-match), `tar`'s own nonzero rc catches an
# unreadable/omitted file, and the readability + member-count check above catches an empty/corrupt archive.
# Do not re-add a name-diff coverage check without solving find-vs-tar encoding normalization. (Red-team 2026-07-07.)
echo "backup -> $OUT ($(du -h "$OUT" 2>/dev/null | cut -f1), $n entries)"
# Advisory rotation ONLY — never auto-delete (safety over tidiness, same stance as snapshot.sh). These
# tarballs can be large, so DO prune old ones by hand once you've confirmed a newer one is good.
# Host-portable "all but the last 5" via awk (BSD head has no negative -n; see ADR-0020). Timestamped
# names sort chronologically under a plain ls, so the oldest are printed first.
ls -1 "$DEST"/*.tgz 2>/dev/null | awk '{a[NR]=$0} END{for(i=1;i<=NR-5;i++) print "prune-candidate (manual; keep last 5): " a[i]}' || true
