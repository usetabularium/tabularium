#!/usr/bin/env bash
# The ONE sanctioned worktree-teardown path (ADR-0040). Born 2026-07-19: two sessions issued the
# same teardown target raced — one force-removed a worktree holding 10 uncommitted modified files
# seconds after the other had read them mid-verification. End-state was correct by adjudication
# luck, not mechanism. This script makes the teardown protocol executable and a lost race harmless:
#   LOCK        one retirement at a time (mkdir lock in the COMMON git dir — atomic on POSIX;
#               macOS has no flock(1)). Never auto-broken: a stale lock is reported, not stolen.
#   MERGED      the worktree's HEAD must be an ancestor of main. Squash/rebase merges false-fail
#               this by design — then verify at artifact level and bank/quarantine manually (no
#               override flag; see the task-precondition lesson).
#   CLEAN       any dirty tracked or untracked state refuses retirement. `--bank` can preserve
#               non-ignored loose bytes as a WIP commit, then stops; a later invocation may retire
#               only after that commit is merged/adjudicated and the worktree is clean.
#   QUARANTINE  a clean merged worktree is atomically moved from its active path into the common
#               git dir's `retired-worktrees/` — outside every work tree, so no instance sees a new
#               record path (ADR-0040 A2) — then git-locked and rechecked. Automation
#               NEVER recursively deletes a live directory: Git's ordinary remove still deletes an
#               ignored file created after its own clean scan, because writers do not share our lock.
#   IDEMPOTENT  already-quarantined/retired = green no-op (a pre-A2 quarantine under the main
#               checkout's `_archive/worktrees/` included): a still-registered-but-gone worktree is
#               verified from its registry HEAD and its registration is locked/retained (never
#               removed across a missing→reappeared race); a fully deregistered historical one from the tombstone log this
#               script appends on every successful retire ($GIT_COMMON_DIR/retired-worktrees.log,
#               machine-local). The race loser gets a proof, not a trap.
#   KEEP        the branch ref is never deleted (history/audit stays).
# Exit: 0 quarantined or verified no-op; 1 gate refusal (unmerged/dirty/unknown/locked); 2 precondition.
# Usage: bash checks/retire-worktree.sh <name-or-path> [--bank]
set -uo pipefail

# Hooks and other callers export GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE; inherited, they OVERRIDE
# every `git -C` below and silently re-target a different repository. A teardown tool must never
# allow ambient env to choose what it destroys.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/CLAUDE.md" ] || { echo "FAIL: not at repo root (CLAUDE.md missing under '$ROOT')"; exit 2; }
git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || { echo "FAIL: '$ROOT' is not a git repository"; exit 2; }
git -C "$ROOT" rev-parse --verify -q main >/dev/null 2>&1 || { echo "FAIL: no 'main' branch — this protocol verifies against main"; exit 2; }

ARG="${1:-}"; BANK="${2:-}"
[ -n "$ARG" ] || { echo "usage: bash checks/retire-worktree.sh <worktree-name-or-path> [--bank]"; exit 2; }
case "$BANK" in ""|--bank) ;; *) echo "FAIL: unknown option '$BANK' (only --bank)"; exit 2;; esac
while [ "$ARG" != "/" ] && [ "${ARG%/}" != "$ARG" ]; do ARG="${ARG%/}"; done
NAME="${ARG##*/}"
[ -n "$NAME" ] || { echo "FAIL: '$ARG' does not name a worktree"; exit 2; }

# A missing explicit path must match that path in the registry, never an unrelated worktree with
# the same basename. Resolve the existing parent physically to absorb macOS /var↔/private/var skew.
QUERY_PATH=""
case "$ARG" in
  */*)
    case "$ARG" in /*) QUERY_PATH="$ARG";; *) QUERY_PATH="$PWD/$ARG";; esac
    query_parent="${QUERY_PATH%/*}"; query_leaf="${QUERY_PATH##*/}"
    [ -d "$query_parent" ] && QUERY_PATH="$(cd "$query_parent" && pwd -P)/$query_leaf"
    ;;
esac

COMMON="$(git -C "$ROOT" rev-parse --git-common-dir)"
case "$COMMON" in /*) ;; *) COMMON="$ROOT/$COMMON";; esac
COMMON="$(cd "$COMMON" && pwd -P)" || { echo "FAIL: cannot resolve git common dir"; exit 2; }
TOMB="$COMMON/retired-worktrees.log"

# Resolve the target: an existing dir (path or bare name under .claude/worktrees/), else fall
# through to the registered-but-gone / tombstone paths below with the raw name.
WT=""
if [ -d "$ARG" ]; then WT="$(cd "$ARG" && pwd -P)"
elif [ -d "$ROOT/.claude/worktrees/$ARG" ]; then WT="$(cd "$ROOT/.claude/worktrees/$ARG" && pwd -P)"
fi

# ---- lock (acquire before reading registry state, so read→act is one critical section) ----------
LOCK="$COMMON/retire-worktree.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "FAIL: another retirement holds the lock ($LOCK)"
  [ -f "$LOCK/info" ] && sed 's/^/  holder: /' "$LOCK/info"
  echo "  If that process is dead, inspect and remove the lock dir by hand — never auto-broken."
  exit 1
fi
LOCK_MARK="$LOCK/owner.$$"
if ! : > "$LOCK_MARK"; then rmdir "$LOCK" 2>/dev/null || true; echo "FAIL: cannot mark retirement lock ownership"; exit 2; fi
cleanup_retire(){
  if [ -f "$LOCK_MARK" ]; then
    rm -f "$LOCK/info" "$LOCK_MARK"
    rmdir "$LOCK" 2>/dev/null || echo "WARN: retirement lock contains unexpected files; inspect $LOCK" >&2
  fi
  return 0
}
trap cleanup_retire EXIT
# A caught signal must terminate. Releasing the lock and then continuing would run the teardown
# outside its critical section; EXIT owns cleanup so a replaced lock is not removed by this process.
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
printf 'pid=%s ts=%s target=%s\n' "$$" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$NAME" > "$LOCK/info" \
  || { echo "FAIL: cannot write retirement lock holder info"; exit 2; }

# ---- registry scan: main worktree (protected) + the target's registered HEAD/branch -------------
MAIN_WT=""; REG_HEAD=""; REG_BR=""; REG_PATH=""; REG_LOCKED=0; REG_MATCHES=0; cur=""; in_target=0
while IFS= read -r line; do
  case "$line" in
    "worktree "*)
      cur="${line#worktree }"
      [ -z "$MAIN_WT" ] && MAIN_WT="$cur"
      curphys="$cur"; [ -d "$cur" ] && curphys="$(cd "$cur" && pwd -P)"
      curmatch="$cur"
      if [ ! -d "$cur" ] && [ -d "${cur%/*}" ]; then curmatch="$(cd "${cur%/*}" && pwd -P)/${cur##*/}"; fi
      in_target=0
      if [ -n "$WT" ] && [ "$curphys" = "$WT" ]; then in_target=1
      elif [ -z "$WT" ] && [ -n "$QUERY_PATH" ] && [ "$curmatch" = "$QUERY_PATH" ]; then in_target=1
      elif [ -z "$WT" ] && [ -z "$QUERY_PATH" ] && [ "${cur##*/}" = "$NAME" ]; then in_target=1; fi
      if [ "$in_target" -eq 1 ]; then
        REG_MATCHES=$((REG_MATCHES+1)); REG_PATH="$cur"; REG_HEAD=""; REG_BR=""; REG_LOCKED=0
      fi ;;
    "HEAD "*)   [ "$in_target" -eq 1 ] && REG_HEAD="${line#HEAD }" ;;
    "branch "*) [ "$in_target" -eq 1 ] && REG_BR="${line#branch }" ;;
    "locked"*)  [ "$in_target" -eq 1 ] && REG_LOCKED=1 ;;
  esac
done <<EOF
$(git -C "$ROOT" worktree list --porcelain)
EOF
[ -n "$MAIN_WT" ] || { echo "FAIL: could not read the worktree registry"; exit 2; }
[ "$REG_MATCHES" -le 1 ] || { echo "FAIL: worktree name '$NAME' is ambiguous in the registry — pass an explicit path"; exit 1; }

# cwd-independence: a bare NAME is resolved against ROOT above, but ROOT is wherever THIS script lives
# (any worktree), so a sibling worktree's `.claude/worktrees/<name>` won't be under it. The registry
# knows the true path — adopt it when the direct lookup missed but a live registry entry exists. Without
# this, an in-a-sibling invocation slips past the self/main guards into the "gone from disk" branch.
if [ -z "$WT" ] && [ -n "$REG_PATH" ] && [ -d "$REG_PATH" ]; then
  WT="$(cd "$REG_PATH" && pwd -P)"
fi
[ -z "$WT" ] || [ -n "$REG_PATH" ] || { echo "FAIL: '$ARG' is a directory but is not a worktree registered in this repository"; exit 2; }

MAIN_PHYS="$MAIN_WT"; [ -d "$MAIN_WT" ] && MAIN_PHYS="$(cd "$MAIN_WT" && pwd -P)"
if [ -n "$WT" ] && [ "$WT" = "$MAIN_PHYS" ]; then echo "FAIL: refusing to retire the MAIN worktree"; exit 1; fi
SELF="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$SELF" ] && SELF="$(cd "$SELF" && pwd -P)"
if [ -n "$WT" ] && [ "$WT" = "$SELF" ]; then echo "FAIL: refusing to retire the worktree you are standing in"; exit 1; fi

# ---- no-op paths: verify, don't trap ------------------------------------------------------------
if [ -z "$WT" ]; then
  if [ -n "$REG_PATH" ]; then
    # Registered but gone from disk: verify from the registry's recorded HEAD, then LOCK AND RETAIN
    # the registration. Even a target-scoped `git worktree remove` is unsafe here: the path can
    # reappear with unique ignored bytes after this observation and Git will recursively delete it.
    if [ -n "$REG_HEAD" ] && git -C "$ROOT" merge-base --is-ancestor "$REG_HEAD" main; then
      : >> "$TOMB" || { echo "FAIL: retirement audit log is not writable ($TOMB) — refusing"; exit 1; }
      if [ "$REG_LOCKED" -ne 1 ]; then
        git -C "$ROOT" worktree lock --reason "retirement: registered path missing; registration retained" "$REG_PATH" \
          || { echo "FAIL: missing worktree registration could not be locked — nothing removed"; exit 1; }
        printf '%s name=%s head=%s branch=%s verified=ancestor-of-main event=missing-registration-locked-retained\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REG_PATH##*/}" "$REG_HEAD" "${REG_BR:-detached}" >> "$TOMB" \
          || { echo "FAIL: registration locked but audit-log append failed — nothing removed"; exit 1; }
      fi
      if [ -e "$REG_PATH" ] || [ -L "$REG_PATH" ]; then
        echo "FAIL: registered path reappeared during retirement check — bytes retained and registration locked; re-inspect"
        exit 1
      fi
      echo "OK: already inactive (registered path absent; HEAD ancestor of main; registration locked and retained)"
      exit 0
    fi
    echo "FAIL: '$NAME' is gone from disk but its recorded HEAD (${REG_HEAD:-unknown}) is NOT a verified ancestor of main — investigate (reflog/branches) before registry removal"
    exit 1
  fi
  if [ -f "$TOMB" ]; then
    prior="$(grep -F " name=$NAME " "$TOMB" 2>/dev/null | tail -1)" || true
    if [ -n "${prior:-}" ]; then echo "OK: already retired per tombstone — $prior"; exit 0; fi
  fi
  echo "FAIL: no worktree '$NAME' on disk, in the registry, or in the tombstone log ($TOMB) — nothing verifiable to retire (typo?)"
  exit 1
fi

# ---- live worktree: the gates -------------------------------------------------------------------
WTHEAD="$(git -C "$WT" rev-parse HEAD)" || { echo "FAIL: cannot read HEAD of $WT"; exit 2; }
BR="$(git -C "$WT" symbolic-ref -q --short HEAD || true)"
dirty="$(git -C "$WT" status --porcelain --untracked-files=no --ignore-submodules=none)" || { echo "FAIL: cannot read status of $WT"; exit 2; }
# Deliberately omit --exclude-standard: ignored files are still untracked bytes, and both normal
# and forced `git worktree remove` can delete them. The prior exclusion caused silent data loss.
untracked="$(git -C "$WT" ls-files --others)" || { echo "FAIL: cannot list all untracked files of $WT"; exit 2; }
ignored="$(git -C "$WT" ls-files --others --ignored --exclude-standard)" || { echo "FAIL: cannot list ignored files of $WT"; exit 2; }
submodule_count="$(git -C "$WT" ls-files --stage | awk '$1 == "160000" { n++ } END { print n+0 }')" \
  || { echo "FAIL: cannot inspect gitlink entries in $WT"; exit 2; }

# Bank before the merged gate: preserving loose bytes is useful even when the branch already has
# unmerged commits. Ignore-rule-protected and nested-submodule bytes need an explicit manual plan;
# `git add -A` would silently omit them while claiming the whole worktree was preserved.
if [ "$BANK" = "--bank" ] && [ -n "$ignored" ]; then
  echo "FAIL: --bank cannot safely preserve ignored files (git add -A omits them); copy/adjudicate them manually first:"
  printf '%s\n' "$ignored" | sed -n '1,5p' | sed 's/^/  /'
  exit 1
fi
if [ "$BANK" = "--bank" ] && [ "$submodule_count" -gt 0 ]; then
  echo "FAIL: --bank cannot prove or preserve nested submodule work — bank/deinit submodules explicitly first"
  exit 1
fi
if [ "$BANK" = "--bank" ] && { [ -n "$dirty" ] || [ -n "$untracked" ]; }; then
  [ -n "$BR" ] || { echo "FAIL: --bank on a detached HEAD would dangle the bank commit — attach a branch first"; exit 1; }
  git -C "$WT" add -A || { echo "FAIL: bank staging failed"; exit 1; }
  git -C "$WT" commit -m "WIP preservation: bank uncommitted worktree changes before retirement (retire-worktree.sh, ADR-0040)" \
    || { echo "FAIL: bank commit refused (a hook may have blocked it) — resolve, then rerun"; exit 1; }
  echo "BANKED: $(git -C "$WT" rev-parse HEAD) on $BR. NOT retiring — the bank commit is unmerged by construction; merge or adjudicate it, then rerun."
  exit 1
fi

git -C "$ROOT" merge-base --is-ancestor "$WTHEAD" main; anc=$?
if [ "$anc" -ne 0 ]; then
  echo "FAIL: HEAD $WTHEAD (${BR:-detached}) is NOT an ancestor of main — unmerged work."
  echo "  If it was squash/rebase-merged, verify at ARTIFACT level, bank anything loose, and remove manually."
  exit 1
fi

if [ -n "$untracked" ]; then
  n="$(printf '%s\n' "$untracked" | grep -c .)"
  echo "FAIL: $n untracked file(s), including ignored files, are present and cannot be byte-verified against main:"
  printf '%s\n' "$untracked" | sed -n '1,5p' | sed 's/^/  /'
  echo "  Rerun with --bank for non-ignored files; ignored files require explicit manual preservation or cleanup."
  exit 1
fi

if [ -n "$dirty" ]; then
  echo "FAIL: tracked worktree state is dirty — refusing retirement without a writer-exclusion proof."
  echo "  Rerun with --bank to preserve non-ignored loose bytes, or reconcile/clean it explicitly first."
  exit 1
fi

# ---- non-destructive retirement quarantine -------------------------------------------------------
# `git worktree remove` is intentionally absent. Even without --force, Git deletes ignored files;
# a writer can create one after our inventory (and after Git's own clean check) but before recursive
# deletion. Moving the directory instead is the only available atomic boundary for path-based writers:
# pre-move bytes move with it; post-move writes at the old path survive outside it. We retain and lock
# the moved tree because a process holding an already-open fd/cwd could still write to the moved inode.
RM="${REG_PATH:-$WT}"
QROOT="$COMMON/retired-worktrees"
# The second pattern is the pre-A2 quarantine (the main checkout's `_archive/worktrees/`): such a
# tree is registered AND locked, so without this arm the run would fall through to `git worktree
# move`, which refuses a locked tree — a loud failure where the contract promises a verified no-op.
case "$WT" in
  "$QROOT"/*|"$MAIN_PHYS"/_archive/worktrees/*)
    if [ "$REG_LOCKED" -ne 1 ]; then
      git -C "$ROOT" worktree lock --reason "retired by checks/retire-worktree.sh; bytes retained" "$RM" \
        || { echo "FAIL: quarantined worktree could not be locked — bytes retained; inspect manually"; exit 1; }
    fi
    echo "OK: worktree already quarantined and retained (HEAD $WTHEAD ancestor of main; branch kept)"
    exit 0
    ;;
esac
[ "$submodule_count" -eq 0 ] || {
  echo "FAIL: automatic quarantine does not move a worktree containing submodules — retain and adjudicate it manually"
  exit 1
}
[ ! -L "$QROOT" ] \
  || { echo "FAIL: retirement quarantine path is symlinked — refusing"; exit 2; }
mkdir -p "$QROOT" || { echo "FAIL: cannot create retirement quarantine"; exit 2; }
chmod 700 "$QROOT" 2>/dev/null \
  || { echo "FAIL: cannot restrict retirement quarantine permissions"; exit 2; }
QDEST="$QROOT/$NAME"
[ ! -e "$QDEST" ] && [ ! -L "$QDEST" ] \
  || { echo "FAIL: retirement quarantine destination already exists — refusing to merge/overwrite"; exit 1; }
: >> "$TOMB" || { echo "FAIL: retirement audit log is not writable ($TOMB) — refusing quarantine"; exit 1; }
git -C "$ROOT" worktree move "$RM" "$QDEST"; rrc=$?
[ "$rrc" -eq 0 ] || { echo "FAIL: git worktree move to quarantine refused (rc=$rrc) — original retained; re-inspect"; exit 1; }
git -C "$ROOT" worktree lock --reason "retired by checks/retire-worktree.sh; bytes retained" "$QDEST" \
  || { echo "FAIL: worktree moved to quarantine but could not be locked — bytes retained; inspect manually"; exit 1; }
post_dirty="$(git -C "$QDEST" status --porcelain --untracked-files=no --ignore-submodules=none)" \
  || { echo "FAIL: worktree quarantined but post-move status failed — bytes retained; inspect manually"; exit 1; }
post_untracked="$(git -C "$QDEST" ls-files --others)" \
  || { echo "FAIL: worktree quarantined but post-move inventory failed — bytes retained; inspect manually"; exit 1; }
if [ -n "$post_dirty" ] || [ -n "$post_untracked" ] || [ -e "$RM" ] || [ -L "$RM" ]; then
  echo "FAIL: state changed during quarantine — all observed paths were retained; inspect both active and quarantine locations"
  exit 1
fi
printf '%s name=%s head=%s branch=%s verified=ancestor-of-main event=quarantined-retained\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$NAME" "$WTHEAD" "${BR:-detached}" >> "$TOMB" \
  || { echo "FAIL: worktree quarantined but audit-log append failed — bytes retained; inspect $TOMB"; exit 1; }
echo "OK: worktree retired into locked quarantine — name=$NAME head=$WTHEAD branch=${BR:-detached} (bytes retained; never recursively deleted)"
