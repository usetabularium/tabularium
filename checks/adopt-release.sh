#!/usr/bin/env bash
# checks/adopt-release.sh — adopt a release in the CARE checkout with one command.
#
# It runs the four steps adoption took by hand, in order, and stops at the first that fails:
#   git fetch --tags origin · git checkout <tag> · checks/install-instance.sh care <tag> · checks/check.sh
# The checkout runs with --no-overwrite-ignore: every care record is an ignored file, and a plain
# checkout silently replaces or deletes one that a release happens to track.
# ADR-0055's adoption command, accepted in part on 2026-10-11 — not the full proposed operation:
# nothing is captured and nothing is rolled back for you.
#
# Usage:  checks/adopt-release.sh [vX.Y.Z]
#         No argument adopts the newest release: the highest tag named exactly vMAJOR.MINOR.PATCH
#         (ADR-0054). An older slugged tag (v0.52.0-<name>) can be named, never chosen.
# Exit:   0 = adopted (or already in use) and the board is green
#         1 = refused or failed before this run moved anything — the checkout is as it was, except that
#             over a checkout that stopped partway it first removes that release's own untracked copies
#         2 = RED after the checkout step: the checkout did not complete, or the installer or the board
#             failed — the recovery and the rollback to the previous pin are printed
#
# CARE only: it refuses unless `checks/check.sh --instance-mode` (the one instance derivation) reports
# a main checkout that asserts `care`, and refuses any tracked-file change, which a care checkout never
# has (guard L19). It prints no remote URL and no git output — fixed words, release names, counts and
# git's index-lock path; everything else on screen is the installer's and the board's own.
#
# An interrupted adoption is finished by running the same command with the same tag again. Every
# recovery it prints is ONE line chained with &&, so a checkout that fails stops before the installer
# re-pins. A checkout that stopped partway with HEAD still on the release in use leaves that release's
# new files untracked, and they would block the next checkout: only an untracked file whose bytes are
# the release's own file at that path, whole or a strict prefix of it (a copy git stopped writing), is
# removed — never another file, never a checks/RECORD-SET path.
# A killed git also leaves its index lock: when one is there and no git of this user is working in this
# checkout, the printed line starts by removing it (rm -f); the script never removes it itself.
#
# A red board is REPORTED with the exact commands that return to the previous pin (checks/CARE-RELEASE
# as it was before this run; when the pin already names the release, the release HEAD came from, read
# from git's own HEAD reflog). It never rolls back by itself, by the operator's decision (ADR-0055,
# accepted in part 2026-10-11).
#
# Portable: bash 3.2 / BSD userland; PORT-linted and bite-tested in checks/selftest.sh.
set -uo pipefail

# Hooks and other callers export GIT_DIR / GIT_INDEX_FILE; inherited, they override `git -C` and
# retarget another repository (the 2026-07-19 incident). This script moves HEAD, so strip them. This
# unset cannot reach the operator's shell, so every printed recovery starts with the same one.
STRIP_GIT_ENV='GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY'
unset $STRIP_GIT_ENV

RELEASE_RE='^v[0-9]+\.[0-9]+\.[0-9]+$'                    # what the newest-release choice considers
NAMED_RE='^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9][A-Za-z0-9.-]*)?$'   # what may be named or printed

say(){    printf 'adopt-release: %s\n' "$1"; }
refuse(){ printf 'adopt-release: REFUSED — %s\n' "$1" >&2; exit 1; }
is_named(){ case "$1" in ''|*[!A-Za-z0-9.-]*) return 1 ;; esac; printf '%s\n' "$1" | grep -Eq "$NAMED_RE"; }

# The functions below read ROOT from main(), which calls them (bash's locals are dynamically scoped).
git_running_here(){ # -> 0 when a git process of this user is, or may be, working in this checkout
  local pl pid comm cwd top
  top="$(cd "$ROOT" && pwd -P)" || return 0
  pl="$(ps -U "$(id -u)" -o pid= -o comm= 2>/dev/null)" || return 0
  while read -r pid comm; do
    case "${comm##*/}" in git|git-*) ;; *) continue ;; esac
    cwd=""
    if [ -d "/proc/$pid" ]; then cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null)"
    elif command -v lsof >/dev/null 2>&1; then cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"; fi
    if [ -z "$cwd" ]; then
      kill -0 "$pid" 2>/dev/null || continue        # it ended in between: not running
      return 0                                      # a git whose folder cannot be read may be ours
    fi
    case "$cwd/" in "$top"/*) return 0 ;; esac
  done <<EOF
$pl
EOF
  return 1
}
lock_check(){ # once per run, in the calling shell: LOCK_RM = "rm -f <git's index lock> && " when a lock
  # is left with no git running here — a killed git leaves it, and every git command that writes the
  # index then stops on it. This script never removes it: the printed line does, at the operator's hand.
  local lp lf
  [ -z "${LOCK_DONE:-}" ] || return 0
  LOCK_DONE=1; LOCK_RM=""
  lp="$(git -C "$ROOT" rev-parse --git-path index.lock 2>/dev/null)" || return 0
  case "$lp" in /*) lf="$lp" ;; *) lf="$ROOT/$lp" ;; esac
  [ -e "$lf" ] || return 0
  if git_running_here; then
    printf "adopt-release: git's index lock (%s) is held and a git process may still be running in this checkout — let it finish before running the line below.\n" "$lp" >&2
  else
    LOCK_RM="rm -f $(printf '%q' "$lp") && "
    printf "adopt-release: git's index lock (%s) was left by a git that stopped, and no git is running in this checkout — the line below removes it first.\n" "$lp" >&2
  fi
}
chain(){ # $1 = a release · $2 = commands to run first -> the one line that puts this checkout on it:
  # checkout, installer, board, chained with && so a checkout that fails stops before the installer
  # re-pins. Every release has these commands, one older than this script included, so a printed
  # recovery never names this script.
  printf '%sunset %s && %sgit checkout --no-overwrite-ignore refs/tags/%s && bash checks/install-instance.sh care %s && bash checks/check.sh' \
    "${LOCK_RM:-}" "$STRIP_GIT_ENV" "${2:-}" "$1" "$1"
}
back_to(){ # $1 = the release to return to · $2 = commands to run first ('' = none)
  lock_check
  printf 'adopt-release: to return to %s, run this one line from the top folder of this checkout:\n' "$1" >&2
  printf '  %s\n' "$(chain "$1" "${2:-}")" >&2
}
newest(){ # -> the highest local tag named exactly vMAJOR.MINOR.PATCH (ADR-0054), or nothing
  local n
  n="$(git -C "$ROOT" tag --list 'v*' 2>/dev/null | grep -E "$RELEASE_RE" \
       | sed 's/^v//' | LC_ALL=C sort -t. -k1,1n -k2,2n -k3,3n | tail -1)"
  [ -z "$n" ] || printf 'v%s\n' "$n"
}
prev_release(){ # $1 = the release being adopted · $2 = the pin read before this run -> the release to return to, or nothing
  local want sha
  if [ -n "$2" ] && [ "$2" != "$1" ]; then printf '%s\n' "$2"; return 0; fi
  [ -n "$2" ] || return 0
  # The pin already names it (a re-run after a red board re-pins before the board runs). git's own HEAD
  # reflog still says where the checkout came from: the newest "moving from <sha> to <tag>", and a
  # release tag at that sha. No state of this script's own is kept.
  want="$(git -C "$ROOT" rev-parse --verify --quiet "refs/tags/$1^{commit}" 2>/dev/null)" || return 0
  sha="$(git -C "$ROOT" reflog show --format='%gs' HEAD 2>/dev/null | awk -v t="$1" -v w="$want" '
    NF == 6 && $1 == "checkout:" && $2 == "moving" && $3 == "from" && $5 == "to" \
      && ($6 == t || $6 == "tags/" t || $6 == "refs/tags/" t) \
      && $4 ~ /^[0-9a-f]+$/ && length($4) >= 40 && $4 != w { print $4; exit }')"
  [ -n "$sha" ] || return 0
  git -C "$ROOT" tag --points-at "$sha" 2>/dev/null | while IFS= read -r t; do
      is_named "$t" && [ "$t" != "$1" ] && printf '%s\n' "${t#v}"
    done | LC_ALL=C sort -t. -k1,1n -k2,2n -k3,3n | tail -1 | sed 's/^/v/'
}
in_record_set(){ # $1 = a path, $RS = RECORD-SET entries one per line -> 0 if the path is one of them
  local e
  while IFS= read -r e; do
    [ -n "$e" ] || continue
    case "$e" in
      */) case "$1" in "$e"*) return 0 ;; esac ;;
      *)  [ "$1" != "$e" ] || return 0 ;;
    esac
  done <<EOF
$RS
EOF
  return 1
}
drop_copies(){ # $1 = a release -> removes each untracked, unignored regular file whose bytes are that
  # release's own file at the same path, or a strict prefix of it (a copy git stopped writing; 0 bytes
  # counts), never a RECORD-SET path; prints how many. A checkout that stopped with HEAD unmoved leaves
  # the release's new files untracked, and git then refuses to check the release out over them. Nothing
  # else is touched: a file of other bytes may be the operator's, and the stopped checkout may already
  # have replaced .gitignore, so a record can be listed as untracked.
  local c p o m h b sz bs hr RS n=0 i=0
  local -a cand
  c="$(git -C "$ROOT" rev-parse --verify --quiet "refs/tags/$1^{commit}" 2>/dev/null)" || return 0
  RS="$( { cat "$ROOT/checks/RECORD-SET" 2>/dev/null
           git -C "$ROOT" show "HEAD:checks/RECORD-SET" 2>/dev/null
           git -C "$ROOT" show "$c:checks/RECORD-SET" 2>/dev/null; } \
         | awk '{ sub(/#.*/, "") } NF >= 2 && ($1 == "record" || $1 == "tooling") { print $2 }')"
  cand=()
  while IFS= read -r -d '' p; do
    in_record_set "$p" && continue
    [ -f "$ROOT/$p" ] && [ ! -L "$ROOT/$p" ] || continue
    cand[${#cand[@]}]="$p"
  done < <(git -C "$ROOT" ls-files -z --others --exclude-standard 2>/dev/null)
  [ "${#cand[@]}" -le 50 ] || printf "adopt-release: removing up to %s untracked file(s)… (only %s's own copies, whole or partly written; each is checked first)\n" "${#cand[@]}" "$1" >&2
  while [ "$i" -lt "${#cand[@]}" ]; do
    p="${cand[$i]}"; i=$((i+1))
    o="$(git -C "$ROOT" --literal-pathspecs ls-tree "$c" -- "$p" 2>/dev/null | cut -f1)"   # "<mode> blob <sha>"
    m="${o%% *}"
    case "$m" in 100644|100755) ;; *) continue ;; esac
    case "$o" in "$m blob "*) ;; *) continue ;; esac
    b="${o##* }"
    h="$(git -C "$ROOT" hash-object -- "$p" 2>/dev/null)" || continue
    [ -n "$h" ] || continue
    if [ "$h" != "$b" ]; then
      # a partly written copy: shorter than the release's file, and its bytes that file's first ones.
      # Hashes are compared from $(…), never piped into a comparison, which pipefail would break; BSD head
      # refuses -c 0, and an empty file is a prefix of any file anyway.
      sz="$(wc -c < "$ROOT/$p" 2>/dev/null | tr -d '[:space:]')"
      bs="$(git -C "$ROOT" cat-file -s "$b" 2>/dev/null)" || continue
      case "$sz" in ''|*[!0-9]*) continue ;; esac
      case "$bs" in ''|*[!0-9]*) continue ;; esac
      [ "$sz" -lt "$bs" ] || continue
      if [ "$sz" -gt 0 ]; then
        hr="$(git -C "$ROOT" hash-object --no-filters -- "$p" 2>/dev/null)" || continue
        [ -n "$hr" ] && [ "$(git -C "$ROOT" cat-file blob "$b" 2>/dev/null | head -c "$sz" | git -C "$ROOT" hash-object --no-filters --stdin 2>/dev/null)" = "$hr" ] || continue
      fi
    fi
    rm -f -- "$ROOT/$p" && n=$((n+1))
  done
  [ "$n" -eq 0 ] || printf "adopt-release: removed %s untracked file(s) the stopped checkout had written — each %s's own file at that path, whole or a partly written copy of it; nothing else was touched.\n" "$n" "$1" >&2
}
rollback(){ # $1 = what went red · $2 = the tag now checked out · $3 = the previous pin ('' = none)
  # The way back is keyed on the PIN, not on whether this run moved HEAD: the installer re-pins even
  # when HEAD was already on the tag (checked out by hand, or finished after a partial checkout).
  local back
  printf 'adopt-release: RED — %s on %s. Nothing was rolled back.\n' "$1" "$2" >&2
  back="$(prev_release "$2" "$3")"
  if [ -n "$back" ]; then
    [ "$3" != "$2" ] || printf "adopt-release: the pin already named %s before this run; HEAD's history shows the checkout came from %s.\n" "$2" "$back" >&2
    back_to "$back"
  elif [ -z "$3" ]; then
    printf 'adopt-release: no earlier release was pinned, so there is no release to return to. Read the red lines above.\n' >&2
  else
    printf "adopt-release: the pin already named %s before this run and HEAD's history names no earlier release, so there is no release to return to. Read the red lines above.\n" "$2" >&2
  fi
  exit 2
}
stopped(){ # $1 = the release whose checkout stopped · $2 = the previous pin ('' = none) · $3 = 1 if HEAD is still the old release
  # A checkout that moved HEAD has written HEAD's index already: `git checkout HEAD -- .` writes HEAD's
  # files and the checkout of the tag is then a no-op. One that did not move HEAD restores the old
  # release's files, and the checkout of the tag then runs over the copies drop_copies removed.
  local back
  [ "$3" != "1" ] || drop_copies "$1"
  lock_check
  printf "adopt-release: fix what stopped git (usually a folder it cannot write; 'git status' lists the files it could not write under \"Changes not staged for commit\"), then run this one line from the top folder of this checkout:\n" >&2
  printf '  %s\n' "$(chain "$1" 'git checkout HEAD -- . && ')" >&2
  printf 'adopt-release: leave every other untracked file alone — a release can change which files git ignores, so records may be listed among them.\n' >&2
  back="$(prev_release "$1" "$2")"
  if [ -n "$back" ]; then
    printf 'adopt-release: or return instead:\n' >&2
    back_to "$back" 'git checkout HEAD -- . && '
  fi
}
incomplete(){ # $1 = the tag · $2 = the previous pin ('' = none) · $3 = 1 if HEAD is still the old release
  printf 'adopt-release: RED — the checkout of %s did not complete; the installer and the board were not run.\n' "$1" >&2
  stopped "$1" "$2" "$3"
  exit 2
}

# Everything runs inside main(): bash reads a script as it executes, and the checkout below replaces
# this file with the adopted release's copy (or removes it). The call and the exit share one line.
main(){
  local ROOT TAG PREV im k v kind marker mstate st head want rc crc now cand cc pc

  case "${1:-}" in -h|--help) awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0"; exit 0 ;; esac
  [ "$#" -le 1 ] || refuse "too many arguments (usage: checks/adopt-release.sh [vX.Y.Z])"
  TAG="${1:-}"
  if [ -n "$TAG" ] && ! is_named "$TAG"; then
    refuse "'$(printf '%s' "$TAG" | cut -c1-40)' is not a release name (vMAJOR.MINOR.PATCH)"
  fi

  ROOT="$(cd "$(dirname "$0")/.." && pwd)" || ROOT=""
  [ -n "$ROOT" ] && [ -f "$ROOT/CLAUDE.md" ] && [ -f "$ROOT/checks/check.sh" ] \
    || refuse "cannot find the checkout this script belongs to"
  command -v git >/dev/null 2>&1 || refuse "git is not installed"

  # 1. CARE only, from the one derivation. A linked worktree is never a care instance.
  im="$(bash "$ROOT/checks/check.sh" --instance-mode "$ROOT" 2>/dev/null)" || im=""
  kind=""; marker=""; mstate=""
  while IFS='=' read -r k v; do
    case "$k" in kind) kind="$v" ;; marker) marker="$v" ;; marker_state) mstate="$v" ;; esac
  done <<EOF
$im
EOF
  if [ "$kind" != "main" ] || [ "$marker" != "care" ] || [ "$mstate" != "ok" ]; then
    refuse "this is not the care checkout (it reads as '$(printf '%s' "${marker:-no instance}" | cut -c1-32)'${kind:+, $kind}) — releases are adopted in care; in development they are cut (contributing/releases.md)"
  fi

  # The previous pin, read before anything moves: it is the rollback target.
  PREV=""
  if [ -f "$ROOT/checks/CARE-RELEASE" ] && [ ! -L "$ROOT/checks/CARE-RELEASE" ]; then
    PREV="$(tr -d '\r' < "$ROOT/checks/CARE-RELEASE" | sed '/^[[:space:]]*$/d' | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    is_named "$PREV" || PREV=""
  fi

  # 2. No tracked-file change: care never edits one, and a checkout must not carry one along. A checkout
  #    that stopped partway (killed, or a file it could not write) leaves exactly that, with HEAD on the
  #    pinned release or on the new one: when the release named here (else the newest already fetched)
  #    explains it, the way to finish or undo it is printed; anything else is refused as it stands.
  st="$(git -C "$ROOT" status --porcelain --untracked-files=no 2>/dev/null)"; rc=$?
  [ "$rc" -eq 0 ] || refuse "git cannot read this checkout's status"
  if [ -n "$st" ]; then
    cand="$TAG"; [ -n "$cand" ] || cand="$(newest)"
    head="$(git -C "$ROOT" rev-parse --verify --quiet HEAD 2>/dev/null)" || head=""
    cc=""; pc=""
    [ -z "$cand" ] || cc="$(git -C "$ROOT" rev-parse --verify --quiet "refs/tags/${cand}^{commit}" 2>/dev/null)" || cc=""
    [ -z "$PREV" ] || pc="$(git -C "$ROOT" rev-parse --verify --quiet "refs/tags/${PREV}^{commit}" 2>/dev/null)" || pc=""
    if [ -n "$cc" ] && [ -n "$pc" ] && [ -n "$head" ] && [ "$cc" != "$pc" ] && { [ "$head" = "$pc" ] || [ "$head" = "$cc" ]; }; then
      printf 'adopt-release: REFUSED — tracked files differ from the release checked out, which is what a checkout of %s that stopped partway leaves.\n' "$cand" >&2
      if [ "$head" = "$pc" ]; then stopped "$cand" "$PREV" 1; else stopped "$cand" "$PREV" 0; fi
      exit 1
    fi
    refuse "tracked files differ from the release in use — run 'bash checks/check.sh' to see them; nothing was changed"
  fi

  # 3. Fetch the release tags. git's own output can carry the remote URL, so none of it is shown.
  git -C "$ROOT" remote 2>/dev/null | grep -qx origin \
    || refuse "this checkout has no 'origin' remote to fetch releases from; nothing was changed"
  git -C "$ROOT" fetch --quiet --tags origin >/dev/null 2>&1 \
    || refuse "fetching release tags from origin failed; nothing was changed. Run 'git fetch --tags origin' yourself to see why (a connection or sign-in problem, or a release tag that moved upstream)"

  # 4. Which release.
  if [ -z "$TAG" ]; then
    TAG="$(newest)"
    [ -n "$TAG" ] || refuse "no release tag (vMAJOR.MINOR.PATCH) found after fetching; nothing was changed"
  fi
  want="$(git -C "$ROOT" rev-parse --verify --quiet "refs/tags/${TAG}^{commit}" 2>/dev/null)" \
    || refuse "no such release tag: $TAG; nothing was changed"
  head="$(git -C "$ROOT" rev-parse --verify --quiet HEAD 2>/dev/null)" || head=""

  # 5. Check it out — unless this checkout is on it already. --no-overwrite-ignore: a release that
  #    tracks a path where an ignored record sits is refused, never allowed to replace or delete it.
  #    A checkout can also stop partway (a file it cannot write) and still exit 0, so the result is
  #    verified: HEAD on the release and no tracked-file difference, or it is RED. A refusal with HEAD
  #    unmoved may still have written some of the release's new files (or an earlier stopped checkout
  #    left them): those exact copies are removed, so the checkout is as it was and a re-run can proceed.
  if [ "$head" = "$want" ]; then
    say "already on $TAG (pinned before: ${PREV:-none}) — running the installer and the board again"
  else
    say "adopting $TAG (pinned before: ${PREV:-none})"
    git -C "$ROOT" -c advice.detachedHead=false checkout --no-overwrite-ignore --quiet "refs/tags/$TAG" >/dev/null 2>&1; crc=$?
    now="$(git -C "$ROOT" rev-parse --verify --quiet HEAD 2>/dev/null)" || now=""
    st="$(git -C "$ROOT" status --porcelain --untracked-files=no 2>/dev/null)"; rc=$?
    if [ "$crc" -ne 0 ] && [ "$now" = "$head" ] && [ "$rc" -eq 0 ] && [ -z "$st" ]; then
      drop_copies "$TAG"
      lock_check
      [ -z "${LOCK_RM:-}" ] || printf '  %s\n' "${LOCK_RM% && }" >&2
      refuse "git would not check out $TAG (most often: a file in the release would replace an untracked or ignored file here); the checkout is as it was — fix what stopped git, then run the same command again"
    fi
    if ! { [ "$crc" -eq 0 ] && [ "$now" = "$want" ] && [ "$rc" -eq 0 ] && [ -z "$st" ]; }; then
      if [ "$now" = "$head" ]; then incomplete "$TAG" "$PREV" 1; else incomplete "$TAG" "$PREV" 0; fi
    fi
  fi

  # 6. The adopted release's own installer, then its own board.
  bash "$ROOT/checks/install-instance.sh" care "$TAG" || rollback "the installer failed" "$TAG" "$PREV"
  bash "$ROOT/checks/check.sh" || rollback "the board" "$TAG" "$PREV"
  say "$TAG adopted and the board is green"
  exit 0
}
main "$@"; exit $?
