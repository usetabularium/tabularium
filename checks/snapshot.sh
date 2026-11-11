#!/usr/bin/env bash
# Append-only snapshot of the canonical files: a clean/caught-process recovery floor for
# truncation/corruption, restored by inspecting a `diff` before any `cp`. It flushes its copies to the
# disk before publishing them and the publication before reporting success, best effort (see snap_flush);
# sudden power loss can still lose data. Standalone/no-.git roots need no git; a checkout uses
# git-backed family lookup before capture. Run after a green check.sh preflight with other
# patient-data writers quiesced.
#
# Usage: checks/snapshot.sh [ROOT]
set -euo pipefail
# Canonical snapshots contain private medical summaries. `cp -p` preserves a source file's mode, so
# umask alone is insufficient; every copied recovery file is explicitly restricted below.
umask 077
SNAP_SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$(cd "$SNAP_SELF_DIR/.." && pwd)}"
cd "$ROOT"
ROOT="$(pwd)"

# A snapshot is record recovery data (CARE).
# Refuse before creating `.snapshots/` or resolving either
# external pointer when this is a development tree, or when indicated instance metadata
# is ambiguous. `check.sh --instance-mode` owns the checkout-family lookup (including inheritance
# for linked worktrees); the small local read below covers plain/no-git roots, which that lookup
# deliberately reports as `kind=nogit` without interpreting their marker. A genuinely unmarked
# root remains supported for legacy use and synthetic recovery tests.
MODE_CHECK="$SNAP_SELF_DIR/check.sh"
snapshot_refuse(){
  printf 'FAIL: snapshot refused before recovery data was touched — %s; no snapshot or external recovery copy was written\n' "$1"
  exit 2
}
MODE_KIND=""; MODE_STATUS=""; MODE_FAMILY_MARKER=""; MODE_FAMILY_STATE=""
MODE_FAMILY_REQUIRED=0
if [ -e .git ] || [ -L .git ]; then
  MODE_FAMILY_REQUIRED=1
  [ -f "$MODE_CHECK" ] && [ ! -L "$MODE_CHECK" ] && [ -r "$MODE_CHECK" ] \
    || snapshot_refuse "instance mode lookup is unavailable"
  MODE_OUT="$(bash "$MODE_CHECK" --instance-mode "$ROOT" 2>/dev/null)" \
    || snapshot_refuse "instance mode lookup failed"
else
  # Historical standalone roots and synthetic fixtures predate the instance contract. They have no
  # checkout family to inherit; the strict local-marker read below still refuses an explicit DEV.
  MODE_OUT="kind=nogit
status=n/a
marker=
marker_state=absent"
fi
while IFS='=' read -r mode_k mode_v; do
  case "$mode_k" in
    kind)         MODE_KIND="$mode_v" ;;
    status)       MODE_STATUS="$mode_v" ;;
    marker)       MODE_FAMILY_MARKER="$mode_v" ;;
    marker_state) MODE_FAMILY_STATE="$mode_v" ;;
  esac
done <<< "$MODE_OUT"
[ "$MODE_FAMILY_REQUIRED" -eq 0 ] || [ "$MODE_KIND" != "nogit" ] \
  || snapshot_refuse "checkout metadata is present but its instance family cannot be determined"
case "$MODE_KIND:$MODE_STATUS:$MODE_FAMILY_STATE" in
  main:n/a:absent|main:n/a:ok|nogit:n/a:absent) : ;;
  main:n/a:bad) snapshot_refuse "the instance marker is not a readable single line" ;;
  worktree:ok:absent|worktree:ok:ok) : ;;
  worktree:ok:bad) snapshot_refuse "the checkout family's instance marker is not a readable single line" ;;
  worktree:unverifiable:*) snapshot_refuse "this linked worktree's checkout family cannot be verified" ;;
  *) snapshot_refuse "instance mode lookup returned an unrecognised result" ;;
esac

LOCAL_MARKER=""; LOCAL_STATE="absent"
if [ -e .tabularium-instance ] || [ -L .tabularium-instance ]; then
  if [ -L .tabularium-instance ] || [ ! -f .tabularium-instance ] || [ ! -r .tabularium-instance ]; then
    LOCAL_STATE="bad"
  else
    local_raw="$(tr -d '\r' < .tabularium-instance | sed '/^[[:space:]]*$/d')"
    local_count="$(printf '%s\n' "$local_raw" | sed '/^[[:space:]]*$/d' | wc -l | tr -d '[:space:]')"
    LOCAL_MARKER="$(printf '%s\n' "$local_raw" | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    if [ "$local_count" = "1" ]; then LOCAL_STATE="ok"; else LOCAL_STATE="bad"; fi
  fi
fi
[ "$LOCAL_STATE" != "bad" ] || snapshot_refuse "the local instance marker is not a readable single line"

SNAP_MODE=""
if [ "$MODE_KIND" = "worktree" ] && [ "$MODE_FAMILY_STATE" = "ok" ]; then
  if [ "$LOCAL_STATE" = "ok" ] && [ "$LOCAL_MARKER" != "$MODE_FAMILY_MARKER" ]; then
    snapshot_refuse "the local marker contradicts the verified checkout family"
  fi
  SNAP_MODE="$MODE_FAMILY_MARKER"
elif [ "$LOCAL_STATE" = "ok" ]; then
  SNAP_MODE="$LOCAL_MARKER"
fi
case "$SNAP_MODE" in
  care|'') : ;;
  dev) snapshot_refuse "instance mode is dev" ;;
  *) snapshot_refuse "the instance marker has an unsupported value" ;;
esac

# Discover the canonical recovery inputs before touching `.snapshots/`. A typoed, parent or empty
# root otherwise publishes a completion marker containing no recovery data. Keep standalone roots
# broad: any canonical input this tool already supports is enough; neither git nor a patient tree is
# required.
FILES=()
[ -f CLAUDE.md ] && FILES+=(CLAUDE.md)
for f in reference-library/*.md reference-library/*.txt _shared/med/*.md; do [ -f "$f" ] && FILES+=("$f"); done
for p in patients/*/; do
  [ -f "${p}profile.md" ] && FILES+=("${p}profile.md")
  [ -f "${p}medications.md" ] && FILES+=("${p}medications.md")
  # The identity file of a person with kept details (ADR-0029 point 13) is banked beside the
  # profile, under the same name, so the read guard's by-name rule covers the copy too.
  [ -f "${p}.never-api-identity.json" ] && [ ! -L "${p}.never-api-identity.json" ] \
    && FILES+=("${p}.never-api-identity.json")
done
[ "${#FILES[@]}" -gt 0 ] \
  || snapshot_refuse "root has no canonical files to capture"
# The export gate is banked too. It was UNTRACKED while it carried the token registry, and this floor
# was then its ONLY pre-edit recovery path (ADR-0036 D3); since ADR-0050 Part B it is tracked product
# and git carries its history, but a pre-edit copy beside the canonical docs still costs nothing and
# is what a session reaches for first. Path is a checks/ script name, not patient data — safe to name.
[ -f checks/publish-skeleton.sh ] && FILES+=(checks/publish-skeleton.sh)

# ---- WHERE the firewall's PII_* class lines and the private-mode identifier live (ADR-0050 Part A2 and
# point 9): checks/config-paths.sh. Before the A2 move the class lines sit inside
# checks/publish-skeleton.sh, which the FILES loop above already banks; after it they sit in a file
# OUTSIDE the tree, which no repo-relative loop can reach — so it is banked separately below.
SNAP_CFG="$SNAP_SELF_DIR/config-paths.sh"
[ -f "$SNAP_CFG" ] && [ -r "$SNAP_CFG" ] && . "$SNAP_CFG" 2>/dev/null && declare -F registry_path private_id_path >/dev/null \
  || snapshot_refuse "checks/config-paths.sh is missing or unreadable — the token registry and the private-mode identifier file cannot be located"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
DEST=".snapshots/$TS"
PART=".snapshots/.${TS}.part.$$"
LOCK=".snapshots/.${TS}.lock"
# Never follow a recovery-root symlink: it could redirect private canonical records into an
# unintended/shared directory. Check again after mkdir to narrow a concurrent namespace swap.
[ ! -L .snapshots ] \
  || { echo "FAIL: snapshot root is symlinked — refusing to write private recovery data"; exit 2; }
mkdir -p .snapshots
[ -d .snapshots ] && [ ! -L .snapshots ] \
  || { echo "FAIL: snapshot root is not a real directory — refusing to write private recovery data"; exit 2; }
chmod 700 .snapshots
[ ! -e "$DEST" ] && [ ! -L "$DEST" ] \
  || { echo "FAIL: snapshot for this second already exists ($DEST)"; exit 1; }
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "FAIL: another snapshot is already publishing timestamp $TS"
  exit 1
fi
cleanup_snapshot(){
  [ -n "${PART:-}" ] && [ -d "$PART" ] && rm -rf "$PART"
  [ -n "${LOCK:-}" ] && [ -d "$LOCK" ] && rmdir "$LOCK" 2>/dev/null
  return 0
}
trap cleanup_snapshot EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$PART"
chmod 700 "$PART" "$LOCK"
CANONICAL_CAPTURE_COUNT=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  mkdir -p "$PART/$(dirname "$f")"
  cp -p "$f" "$PART/$f"
  chmod 600 "$PART/$f"
  cmp -s "$f" "$PART/$f" || { echo "FAIL: snapshot copy verification failed"; exit 1; }
  [ "$f" = "checks/publish-skeleton.sh" ] || CANONICAL_CAPTURE_COUNT=$((CANONICAL_CAPTURE_COUNT + 1))
done
# ADR-0050 Part A2: once the token registry lives OUTSIDE this tree, the repo-relative FILES loop
# above cannot reach it — yet it is the file retired guard L12 once checkpointed, and whose clobber
# this floor exists to recover from. Bank it under external/, same 0600 discipline. Never printed: only
# the destination's in-snapshot name (the path names a location in the operator's home).
# Its folder not existing at all means this shell cannot see the operator's home (a chat's Linux VM with
# only the care folder mounted): copy the records and say so. A missing file in a folder that exists is a
# loss, and still refuses.
SNAP_NOTES=""; SNAP_REG=""; SNAP_PM=""
if [ -e checks/FIREWALL-REGISTRY ] || [ -L checks/FIREWALL-REGISTRY ]; then
  SNAP_REG="$(registry_path checks)" \
    || { echo "FAIL: checks/FIREWALL-REGISTRY exists but is unusable — not a readable regular file, or it names no path, or the path it names is RELATIVE (it must be absolute) — refusing a snapshot that would silently omit the token registry"; exit 2; }
fi
if [ -n "${SNAP_REG:-}" ] && [ ! -d "$(dirname "$SNAP_REG")" ]; then
  SNAP_NOTES="${SNAP_NOTES}note: the token registry's folder is not visible from this shell (path withheld) — the records were copied; that file is not in this snapshot, and the next snapshot taken on the Mac copies it
"
elif [ -n "${SNAP_REG:-}" ]; then
  [ -f "$SNAP_REG" ] && [ ! -L "$SNAP_REG" ] && [ -r "$SNAP_REG" ] \
    || { echo "FAIL: the token registry named by checks/FIREWALL-REGISTRY is missing, unreadable or a symlink (path withheld) — refusing an incomplete recovery point"; exit 2; }
  mkdir -p "$PART/external"
  chmod 700 "$PART/external"
  cp -p "$SNAP_REG" "$PART/external/firewall-registry.sh"
  chmod 600 "$PART/external/firewall-registry.sh"
  cmp -s "$SNAP_REG" "$PART/external/firewall-registry.sh" \
    || { echo "FAIL: snapshot copy verification failed (token registry)"; exit 1; }
fi
# ADR-0050 point 9 (2026-09-16): the private-mode identifier was cut out of the registry into its own
# file beside it. Banked the same way, or a restore of the registry alone would lose the identifier
# the scans look for. Same 0600 discipline; never printed.
if [ -e checks/PRIVATE-MODE-ID ] || [ -L checks/PRIVATE-MODE-ID ]; then
  SNAP_PM="$(private_id_path checks)" \
    || { echo "FAIL: checks/PRIVATE-MODE-ID exists but is unusable — not a readable regular file, or it names no path, or the path it names is RELATIVE (it must be absolute) — refusing a snapshot that would silently omit the private-mode identifier file"; exit 2; }
fi
if [ -n "${SNAP_PM:-}" ] && [ ! -d "$(dirname "$SNAP_PM")" ]; then
  SNAP_NOTES="${SNAP_NOTES}note: the private-mode identifier file's folder is not visible from this shell (path withheld) — the records were copied; that file is not in this snapshot, and the next snapshot taken on the Mac copies it
"
elif [ -n "${SNAP_PM:-}" ]; then
  [ -f "$SNAP_PM" ] && [ ! -L "$SNAP_PM" ] && [ -r "$SNAP_PM" ] \
    || { echo "FAIL: the private-mode identifier file named by checks/PRIVATE-MODE-ID is missing, unreadable or a symlink (path withheld) — refusing an incomplete recovery point"; exit 2; }
  mkdir -p "$PART/external"
  chmod 700 "$PART/external"
  cp -p "$SNAP_PM" "$PART/external/private-mode-id.sh"
  chmod 600 "$PART/external/private-mode-id.sh"
  cmp -s "$SNAP_PM" "$PART/external/private-mode-id.sh" \
    || { echo "FAIL: snapshot copy verification failed (private-mode identifier file)"; exit 1; }
fi
[ "$CANONICAL_CAPTURE_COUNT" -gt 0 ] \
  || { echo "FAIL: snapshot captured zero canonical files — no recovery point was published"; exit 1; }
# A root marker distinguishes a fully copied snapshot from a directory planted concurrently or a
# partial/nested publication. Keep it in the final recovery point; consumers must require it for
# snapshots created after ADR-0042.
printf '%s\n' "$TS.$$" > "$PART/.snapshot-complete"
chmod 600 "$PART/.snapshot-complete"
[ ! -e "$DEST" ] && [ ! -L "$DEST" ] \
  || { echo "FAIL: final snapshot path appeared during capture ($DEST)"; exit 1; }
# Flush the copied bytes before the rename publishes them, so a power cut cannot leave a recovery point
# whose completion marker stands over empty or torn files; the second flush below makes the rename itself
# durable before success is reported. Best effort, and it never refuses a snapshot: Linux's `sync` waits for
# the writes; macOS's may return before they finish (sync(2), BUGS), so on a Mac each staged file and folder,
# and the snapshot folder, first gets the full-flush call (F_FULLFSYNC, 51, which also empties the drive's
# own cache; fsync where a filesystem refuses it) through the system's perl. A write error the disk reports
# only then is not detected here, as before.
SNAP_FLUSH_PL='for my $p (@ARGV) { open(my $fh, "<", $p) or next; fcntl($fh, 51, 0) or $fh->sync; close $fh } exit 0'
snap_flush(){ # path… — on a Mac with perl, each path itself; then the system-wide sync
  if [ "$(uname -s)" = Darwin ] && command -v perl >/dev/null 2>&1; then
    case "$1" in
      --tree) find "$2" -exec perl -MIO::Handle -e "$SNAP_FLUSH_PL" {} + || : ; shift 2 ;;
    esac
    [ "$#" -eq 0 ] || perl -MIO::Handle -e "$SNAP_FLUSH_PL" "$@" || :
  fi
  sync || :
}
snap_flush --tree "$PART" .snapshots
mv "$PART" "$DEST"
if [ "$(sed -n '1p' "$DEST/.snapshot-complete" 2>/dev/null)" != "$TS.$$" ]; then
  PART=""
  echo "FAIL: snapshot publication did not land at the exact final path — captured bytes retained but recovery point is not valid"
  exit 1
fi
PART=""
# A shell that may not delete in this folder (a chat's VM) cannot remove the lock: the snapshot stands.
rmdir "$LOCK" 2>/dev/null \
  || SNAP_NOTES="${SNAP_NOTES}note: this shell could not remove the lock folder $LOCK — the snapshot is complete; the folder is safe to delete later
"
LOCK=""
snap_flush .snapshots
# keep the last 30 snapshots; never auto-delete (manual prune only) — safety over tidiness.
# Host-portable "all but the last 30" via awk (BSD head has no negative -n); see ADR-0020.
ls -1d .snapshots/*/ 2>/dev/null | awk '{a[NR]=$0} END{for(i=1;i<=NR-30;i++) print "keep-or-prune-manually: " a[i]}' || true
# ---- the off-Mac copy, refreshed when due (ADR-0067). checks/OFFSITE-DEST's second line is how often the
# operator chose: `every session` or `every week`; without one, the copy runs only when asked. The local
# snapshot above stands whatever happens here: a drive left unplugged costs one line, never this run.
if [ -f checks/OFFSITE-DEST ] && [ ! -L checks/OFFSITE-DEST ]; then
  off_lines="$(sed -e 's/[[:space:]]*$//' -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' checks/OFFSITE-DEST 2>/dev/null)" || off_lines=""
  off_every="$(printf '%s\n' "$off_lines" | sed -n '2p')"
  off_dest="${TABULARIUM_OFFSITE_DEST:-$(printf '%s\n' "$off_lines" | sed -n '1p')}"
  off_due=no
  case "$off_every" in
    "every session") off_due=yes ;;
    "every week")
      off_recent="$(find "$off_dest/tabularium/.tabularium-last-backup" -mtime -7 2>/dev/null)" || true
      [ -n "${off_recent:-}" ] || off_due=yes ;;
  esac
  if [ "$off_due" = yes ]; then
    off_rc=0; off_out="$(bash "$SNAP_SELF_DIR/backup-offsite.sh" "$ROOT" 2>&1)" || off_rc=$?
    if [ "$off_rc" -eq 0 ]; then
      SNAP_NOTES="${SNAP_NOTES}off-Mac backup refreshed ($off_every)
"
    else
      off_why="$(printf '%s\n' "$off_out" | awk '/^FAIL: /{sub(/^FAIL: /, ""); print; exit}')" || true
      SNAP_NOTES="${SNAP_NOTES}note: the off-Mac backup did not refresh ($off_every): ${off_why:-it stopped with code $off_rc} — this snapshot is complete
"
    fi
  fi
fi
printf '%s' "$SNAP_NOTES"
# The result line prints last, so a tail of the output shows it however long the list above runs.
echo "snapshot -> $DEST ($(find "$DEST" -type f | wc -l | tr -d ' ') files)"
