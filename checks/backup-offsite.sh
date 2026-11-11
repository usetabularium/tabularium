#!/usr/bin/env bash
# Off-machine mirror of the patient tree — backup LAYER 3 (see checks/README.md "Version control &
# backups"). Layers 1 (.snapshots/) and 2 (outputs/_snapshots/*.tgz) both live on THIS machine, so
# they defend against bad writes and local deletion but not against device loss, theft or ransomware
# — the architecture's weakest point for life-and-death records. This script is the
# adopted answer: a one-way copy of the irreplaceable patient tree into an operator-configured
# directory, on an external drive or synced off the machine by a cloud client of the operator's choice.
#
# Usage: checks/backup-offsite.sh [--verify-only] [ROOT]
#
# WHAT IT COPIES: patients/ and _shared/ wholesale — the full patient tree, i.e. exactly the set that
# local git CANNOT back up (.gitignore'd under the ADR-0017 PII firewall). Everything else in this
# repo is skeleton and lives in the private git ring. Copying the two roots wholesale is deliberate:
# an include-list of subpaths is the kind of clever selection that silently drops a lane when the
# layout grows, and this is the sole off-machine copy of unregenerable grade-A evidence.
#
# WHAT IT DOES NOT DO:
#   - No --delete. A mirror that propagates deletions would carry a local accident straight to the
#     off-machine copy, destroying the one property this layer exists to provide. The offsite copy is
#     APPEND-ONLY: it grows, and a file removed locally stays there until the operator removes it by
#     hand. Renamed sources therefore accumulate under both names offsite; that is intended.
#   - No credentials, no network calls, no provider API. It writes to a local path; the provider's own
#     client does the sync. This script never authenticates to anything.
#   - It does not preserve POSIX modes (see the rsync flags below) and does not claim to.
#
# CONFIDENTIALITY MODEL — read before trusting this. Off-machine confidentiality rests on where the
# folder is and who can reach it (the provider's encryption and the account's hygiene, or the drive's
# custody), NOT on file permissions: a provider-mounted filesystem routinely ignores chmod, so a 0600
# scan can land 0644 in the synced folder. That is why this script does not pretend to preserve modes.
# It also means a compromised account or a lost drive is a full breach of the patient tree, and a
# provider that does not encrypt end to end can read it — the operator's choice (ADR-0045, ADR-0067).
set -uo pipefail
umask 077

VERIFY_ONLY=no
ROOT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --verify-only) VERIFY_ONLY=yes; shift ;;
    --) shift; break ;;
    -*) echo "FAIL: unknown option '$1' (usage: checks/backup-offsite.sh [--verify-only] [ROOT])"; exit 2 ;;
    *)  ROOT="$1"; shift ;;
  esac
done
# The repository that OWNS this script — the verifier below must be the one shipped alongside it, not
# whatever happens to sit under a passed-in ROOT (same stance as ADR-0039's repository-bound renderer).
SELF_REPO="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "$ROOT" ] || ROOT="$SELF_REPO"
cd "$ROOT" || { echo "FAIL: cannot cd to $ROOT"; exit 2; }
ROOT="$(pwd)"
# Fail closed (ADR-0021 stance): refuse to mirror the wrong/empty tree. CLAUDE.md marks the repo root.
[ -f CLAUDE.md ] || { echo "FAIL: not at repo root (CLAUDE.md missing under '$ROOT') — refusing to mirror the wrong tree"; exit 2; }
[ -d patients ] || { echo "FAIL: no patients/ under '$ROOT' — refusing to report an empty mirror as a backup"; exit 2; }

# ---------------------------------------------------------------------------------------------
# Destination resolution. The path contains the operator's provider account name, which is PII, so it
# is NEVER hardcoded here — checks/ ships in the published skeleton. It comes from the environment or
# from an untracked, never-published sentinel file, the same convention as checks/PUBLISH-HOLD.
# ---------------------------------------------------------------------------------------------
DEST_CFG="$ROOT/checks/OFFSITE-DEST"
DEST="${TABULARIUM_OFFSITE_DEST:-}"
if [ -z "$DEST" ] && [ -f "$DEST_CFG" ]; then
  # first non-empty, non-comment line; trailing whitespace stripped
  DEST="$(sed -e 's/[[:space:]]*$//' -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "$DEST_CFG" | head -1)"
fi
if [ -z "$DEST" ]; then
  echo "FAIL: no offsite destination configured."
  echo "      Set TABULARIUM_OFFSITE_DEST=/path/to/synced/folder, or write that path into"
  echo "      checks/OFFSITE-DEST (untracked, never published). Then create the marker file"
  echo "      .tabularium-offsite-ok inside it — see checks/README.md, backup layer 3."
  exit 2
fi

# ---------------------------------------------------------------------------------------------
# Destination safety. Every one of these is fail-closed: a backup that quietly writes somewhere
# unintended is worse than no backup, because it reports success and buys false confidence.
# ---------------------------------------------------------------------------------------------
case "$DEST" in
  /*) ;;
  *)  echo "FAIL: offsite destination must be an absolute path (got '$DEST')"; exit 2 ;;
esac
# A symlinked destination could redirect the complete private tree into an unintended or shared
# location. Same stance as snapshot.sh / backup-tree.sh: refuse, never follow.
[ -L "$DEST" ] && { echo "FAIL: offsite destination is a symlink — refusing to write private records through it"; exit 2; }
[ -d "$DEST" ] || {
  echo "FAIL: offsite destination does not exist or is not a directory: $DEST"
  echo "      If this is a cloud-synced folder, the client is probably not running or not logged in."
  exit 2
}
# THE MOUNT CHECK, and the reason this layer can be trusted at all. A provider-mounted folder
# disappears (or reappears empty) when the client is logged out or the machine is offline. Without
# this marker the script would happily recreate the directory on the local disk and rsync the records into
# the SAME failure domain it exists to escape — reporting success the whole way. The operator places
# the marker inside the real synced folder once, by hand; its absence means "this is not the folder
# you configured, or the provider is not mounted right now".
MARKER="$DEST/.tabularium-offsite-ok"
[ -f "$MARKER" ] || {
  echo "FAIL: destination is not a confirmed offsite target — marker missing: $MARKER"
  echo "      Either the sync client is not mounted, or this folder was never confirmed."
  echo "      If the path is right and the client IS running:  touch '$MARKER'"
  exit 2
}
# Containment: mirroring into the repo (or the repo into the mirror) recurses and corrupts both. The
# spelled paths are compared with trailing slashes, so a sibling that merely shares a prefix does not
# trip. That alone is not enough: a symlinked component (or macOS's /var -> /private/var) lets a path
# that reads as outside resolve inside. So each directory's PHYSICAL ancestors are also compared by
# identity (device and inode, `-ef`), which no symlink, case variant or Unicode form of a name can
# disguise. within A B: 0 = A is B or beneath it, 1 = it is not, 2 = A cannot be resolved.
within(){
  local p
  p="$(cd -P "$1" 2>/dev/null && pwd -P)" || return 2
  case "$p" in /*) ;; *) return 2 ;; esac   # only an absolute path climbs to / and ends the walk
  while :; do
    [ "$p" -ef "$2" ] && return 0
    [ "$p" = / ] && return 1
    p="$(dirname "$p")"
  done
}
within "$DEST" "$ROOT"; dest_in_root=$?
within "$ROOT" "$DEST"; root_in_dest=$?
if [ "$dest_in_root" -eq 2 ] || [ "$root_in_dest" -eq 2 ]; then
  echo "FAIL: cannot resolve where the offsite destination or the repository physically is — refusing to guess"; exit 2
fi
case "$DEST/" in "$ROOT"/*) dest_in_root=0 ;; esac
case "$ROOT/" in "$DEST"/*) root_in_dest=0 ;; esac
[ "$dest_in_root" -eq 0 ] && { echo "FAIL: offsite destination is inside the repository ($DEST) — that is not off-machine"; exit 2; }
[ "$root_in_dest" -eq 0 ] && { echo "FAIL: repository is inside the offsite destination ($DEST) — refusing to recurse"; exit 2; }
# OFF THIS MAC'S DISK (ADR-0067). The marker says "this folder, on purpose", not "off this disk": a session
# places it at setup, so an ordinary folder beside the records would pass and die with the Mac. A folder on
# the records' own disk is accepted only inside the area where macOS's cloud apps keep the folders they sync
# (iCloud Drive, and the File Provider folders of Google Drive, OneDrive, Dropbox and others), which sits
# on the startup disk by design. An external drive or a network share is another device and passes.
disk_of(){ stat -c %d "$1" 2>/dev/null || stat -f %d "$1" 2>/dev/null; }   # GNU first: BSD stat refuses -c
in_cloud_area(){
  local p h
  p="$(cd -P "$DEST" 2>/dev/null && pwd -P)/" || return 1
  h="$(cd -P "$HOME" 2>/dev/null && pwd -P)" || return 1
  case "$p" in "$h/Library/CloudStorage/"?*|"$h/Library/Mobile Documents/"?*) return 0 ;; esac
  return 1
}
dest_disk="$(disk_of "$DEST")"; root_disk="$(disk_of "$ROOT")"
if [ -z "$dest_disk" ] || [ -z "$root_disk" ]; then
  echo "FAIL: cannot tell which disk the offsite destination is on — refusing to guess"; exit 2
fi
if [ "$dest_disk" = "$root_disk" ] && ! in_cloud_area; then
  echo "FAIL: the offsite destination is on this Mac's own disk, outside the folders a cloud app syncs — a copy there is lost with the Mac"
  echo "      Choose an external drive, or a folder your cloud app syncs (it shows under that app's name in Finder's sidebar)."
  exit 2
fi

MIRROR="$DEST/tabularium"
if [ "$VERIFY_ONLY" = yes ]; then
  # --verify-only only reads: it never creates the mirror, because creating it on a provider folder that is
  # not hydrated locally is a write into the copy it was asked to check. Report the absence instead.
  [ -d "$MIRROR" ] || {
    echo "FAIL: no mirror to verify at $MIRROR — --verify-only creates nothing, so nothing was written"
    echo "      Run checks/backup-offsite.sh without --verify-only to make it. If a mirror should already be"
    echo "      there, check that the provider client is running and has the folder available locally."
    exit 1
  }
else
  mkdir -p "$MIRROR" || { echo "FAIL: cannot create mirror directory ($MIRROR)"; exit 1; }
fi
[ -L "$MIRROR" ] && { echo "FAIL: mirror directory is a symlink — refusing to write private records through it"; exit 2; }

# ---------------------------------------------------------------------------------------------
# Copy.
# ---------------------------------------------------------------------------------------------
if [ "$VERIFY_ONLY" = no ]; then
  command -v rsync >/dev/null 2>&1 || { echo "FAIL: rsync not found — cannot mirror"; exit 2; }
  # Flags, deliberately minimal (macOS ships openrsync, which advertises 2.6.9 compatibility — exotic
  # flags are not portable across it and GNU rsync):
  #   -r recurse   -l keep symlinks AS symlinks (never follow: following one would pull data from
  #                outside the patient tree into the offsite copy)   -t times, so unchanged files are
  #                skipped on the next run and the incremental stays cheap.
  # NOT -a: -a implies -p/-g/-o/-D. Mode/owner preservation fails on provider-mounted filesystems,
  # which would make every run report an error for something this layer explicitly does not rely on
  # (see CONFIDENTIALITY MODEL above), and -D would try to recreate device/special nodes.
  rc=0
  for src in patients _shared; do
    [ -d "$ROOT/$src" ] || continue
    rsync -rlt -- "$ROOT/$src" "$MIRROR/" || { rc=$?; echo "FAIL: rsync of '$src' failed (rc=$rc)"; }
  done
  [ "$rc" -eq 0 ] || { echo "FAIL: offsite mirror incomplete — do NOT treat this run as a backup"; exit 1; }
fi

# python3 is a hard requirement, not a nice-to-have: both checks below run on it, and without them the
# run would produce an UNVERIFIED pile of bytes and print something reassuring. Fail closed instead —
# the mirror may well be on disk, but this script will not call it a backup it has not checked.
command -v python3 >/dev/null 2>&1 || {
  echo "FAIL: python3 not found — cannot check the mirror file by file or hash-verify it against the ownership ledger."
  echo "      Bytes may have been copied, but this run is NOT a verified backup."
  exit 2
}

# ---------------------------------------------------------------------------------------------
# Completeness, file by file. Every regular local file under patients/ and _shared/ must be in the
# mirror at the same path with the same size. A count cannot prove that: the mirror is append-only, so
# the old names of renamed files make up the number while a new file is missing. Extra mirror files
# are expected and never fail a run. Sizes come from file metadata, so no content is read (a provider
# placeholder is not downloaded) and a same-size content change is NOT caught here — the evidence
# layer's bytes are proven below, by the ownership ledger.
# Names are compared Unicode-normalized (NFC), never as raw bytes. A byte-level name comparison is the
# trap this repo has already been bitten by (see the red-team note at the end of backup-tree.sh): a
# provider filesystem may hand an accented scan name back decomposed (NFD), the same file under other
# bytes, and the check then fails a perfectly good backup — or, worse, provokes a fix that deletes it.
# The output gives counts, never names: a file name can carry a private-mode identifier, and a model
# session may read this output.
# ---------------------------------------------------------------------------------------------
coverage(){
  python3 -I - "$1" "$2" <<'PY'
import os, stat, sys, unicodedata
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def files(base):
    """(NFC tree-relative name, size) of every regular file under patients/ and _shared/. Symlinks are
    never followed (rsync -l copies them as links). Anything unlistable raises OSError."""
    out = []
    def stop(err):
        raise err
    for top in (b'patients', b'_shared'):
        d = os.path.join(base, top)
        try:
            st = os.lstat(d)          # never isdir()/islink(): they read an error as "absent"
        except FileNotFoundError:
            continue                  # a tree that is not there has nothing to mirror
        if not stat.S_ISDIR(st.st_mode):
            continue                  # a link is copied as a link (rsync -l) and never walked
        for dirpath, _dirs, names in os.walk(d, onerror=stop):
            for name in names:
                p = os.path.join(dirpath, name)
                st = os.lstat(p)
                if stat.S_ISREG(st.st_mode):
                    rel = os.path.relpath(p, base).decode('utf-8', 'surrogateescape')
                    out.append((unicodedata.normalize('NFC', rel), st.st_size))
    return out

root, mirror = (os.fsencode(a) for a in sys.argv[1:3])
try:
    local, held = files(root), files(mirror)
except OSError as e:
    print('FAIL: could not list every file (%s) — verification is INDETERMINATE' % (e.strerror or 'error'))
    sys.exit(1)
if not local:
    print('FAIL: enumerated zero local patient files — refusing to report a green mirror over nothing')
    sys.exit(1)
# two local names that differ only in Unicode form (a Linux file system can hold both) are one name to this
# check, so a mirror holding either would count for both: refuse rather than vouch for one of them
dupes = len(local) - len({name for name, _ in local})
if dupes:
    print('FAIL: %d local file name(s) differ from another only in Unicode form — the mirror check cannot tell'
          ' them apart; rename one, then rerun' % dupes)
    sys.exit(1)
sizes = {}
for name, size in held:
    sizes.setdefault(name, set()).add(size)
missing = sum(1 for name, _ in local if name not in sizes)
resized = sum(1 for name, size in local if name in sizes and size not in sizes[name])
if missing:
    print('FAIL: the mirror lacks %d of %d local files — verification is INDETERMINATE' % (missing, len(local)))
    print('      Provider data may be healthy but not hydrated locally, or remote data may be missing.')
    print('      Check the provider state and perform a restore check before relying on this mirror.')
if resized:
    print('FAIL: %d of %d local files have a different size in the mirror — it is out of date or damaged;'
          ' do NOT rely on it' % (resized, len(local)))
    print('      A run without --verify-only brings it up to date; if the difference stays, check the provider.')
if missing or resized:
    sys.exit(1)
print(len(local), len(held))
PY
}
is_count(){ case "$1" in ''|*[!0-9]*) return 1 ;; esac; return 0; }
cov="$(coverage "$ROOT" "$MIRROR")"; cov_rc=$?
src_n="${cov% *}"; dst_n="${cov#* }"
if [ "$cov_rc" -ne 0 ] || ! is_count "$src_n" || ! is_count "$dst_n"; then
  [ -n "$cov" ] && printf '%s\n' "$cov"
  case "$cov" in
    *FAIL:*) ;;
    *) echo "FAIL: the file-by-file mirror check did not complete (rc=$cov_rc) — do NOT treat this run as a backup" ;;
  esac
  exit 1
fi
bytes_of(){ find "$1" -type f -exec ls -l {} + 2>/dev/null | awk '{s+=$5} END{printf "%.0f", s+0}' ; }

# ---------------------------------------------------------------------------------------------
# Byte proof for the layer that matters. The ownership ledger (ADR-0037 / guard L13) already records a
# SHA-256 for every source under med/sources/, bound to its owning person. So verification of the
# offsite copy is not new code — it is the repository's OWN verifier, pointed at the mirror. A
# truncated sync, a dehydrated placeholder left behind by the provider's client, or a silently
# corrupted transfer all fail this. An untested backup is not a backup. `--mirror`: every current
# record's file must be there with its recorded bytes; a file no current record binds (an old name the
# append-only copy keeps, above, or anything else) is counted, never failed — the live tree's own
# check (L13) is where a stray file is caught.
# ---------------------------------------------------------------------------------------------
verify_rc=0
( cd "$SELF_REPO" && python3 -m tools.person_ownership --root "$MIRROR" verify --mirror ) || verify_rc=$?
if [ "$verify_rc" -ne 0 ]; then
  echo "FAIL: offsite copy failed ownership/hash verification (rc=$verify_rc) — do NOT rely on it"
  exit 1
fi

if [ "$VERIFY_ONLY" = yes ]; then
  echo "offsite VERIFY OK: $dst_n files under $MIRROR (local $src_n, each present with its size); evidence bytes match the ownership ledger"
else
  # when the last verified copy was taken: the snapshot's weekly refresh reads its age (ADR-0067)
  : > "$MIRROR/.tabularium-last-backup" 2>/dev/null || echo "note: could not record the time of this backup; a weekly refresh will run again at the next snapshot"
  echo "offsite mirror OK: $dst_n files, $(bytes_of "$MIRROR" | awk '{printf "%.1f GB", $1/1073741824}') under $MIRROR (local $src_n files, each present with its size)"
  echo "  append-only (no --delete): files removed locally remain in the mirror until you delete them there."
  echo "  Sync is the provider client's job — confirm it has finished uploading before treating this as off-machine."
fi
exit 0
