#!/usr/bin/env bash
# checks/release-notice.sh — is a newer release out than the one this care checkout adopted?
#
# The host-neutral half of the care-side release notice (ADR-0055 point 5, accepted
# 2026-10-25; ROADMAP F7). It asks origin for its release tags and compares the newest with the pin. It
# never fetches objects, moves HEAD, rewrites checks/CARE-RELEASE or adopts anything: adopting is
# checks/adopt-release.sh, run when the operator chooses. The Claude Code adapter that shows the line at
# session start is tools/claude-hooks/release-notice.py.
#
# Usage:  checks/release-notice.sh [--daily]
#         --daily is the automatic check's mode: it does nothing when the opt-out file
#         ~/.config/tabularium/release-notice-off exists, or when a check already ran today (a dated
#         stamp in git's own directory, never in the working tree, where an untracked file would red L19),
#         and it claims the day before it contacts origin, so a killed or failed check still counts.
# Prints five lines, key=value — fixed words and release names only, never the remote address, git's
# own messages or a tag's message:
#   pinned=<the release checks/CARE-RELEASE names; empty when it names none>
#   newest=<the highest tag on origin named exactly vMAJOR.MINOR.PATCH; empty when there is none>
#   gap=none|patch|minor|major      how far newest is ahead of pinned, compared by number
#   status=ok|unreachable|no-pin|off
#   reason=<empty, or a fixed word: not-care opted-out checked-today no-stamp no-origin no-python timeout failed>
# Exit:   0 = nothing to say (no newer release, or a patch only) · 1 = a newer MINOR or MAJOR release
#         waits · 2 = no answer (status is not ok) · 3 = usage
#
# Inert outside a care main checkout — development, CI and every fixture — by the one instance
# derivation (checks/check.sh --instance-mode). A failure says nothing on screen and never reds.
# The one network call is `git ls-remote --tags --refs origin`, capped at a few seconds by python3
# (macOS ships no timeout(1)), with no prompt of any kind: no terminal prompt, no askpass program,
# SSH in batch mode. It sends the configured remote whatever git sends it and receives ref names;
# nothing from the records travels.
#
# Portable: bash 3.2 / BSD userland; PORT-linted and bite-tested in checks/selftest.sh.
set -uo pipefail

# Inherited git variables would override `git -C` and retarget another repository (the 2026-07-19
# incident). Read-only here, but the strip is the same as every other script's.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX GIT_OBJECT_DIRECTORY

CAP=4   # seconds for the one network call; measured at about one second on the operator's host
# python3 -c CAPPED <seconds> <command…>: runs the command in its own process group with no input and
# no stderr, prints its stdout, and kills the whole group at the cap (exit 124)
CAPPED='
import os, signal, subprocess, sys
cap = float(sys.argv[1])
try:
    p = subprocess.Popen(sys.argv[2:], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, start_new_session=True)
except OSError:
    sys.exit(125)
try:
    out, _ = p.communicate(timeout=cap)
except subprocess.TimeoutExpired:
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
    p.wait()
    sys.exit(124)
sys.stdout.buffer.write(out)
sys.exit(p.returncode)
'

DAILY=0
case "${1:-}" in
  '') ;;
  --daily) DAILY=1 ;;
  -h|--help) awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0"; exit 0 ;;
  *) echo 'usage: checks/release-notice.sh [--daily]' >&2; exit 3 ;;
esac
[ "$#" -le 1 ] || { echo 'usage: checks/release-notice.sh [--daily]' >&2; exit 3; }

PINNED=""; NEWEST=""; GAP="none"
answer(){ # $1 = status · $2 = reason ('' = none) · $3 = exit code
  printf 'pinned=%s\nnewest=%s\ngap=%s\nstatus=%s\nreason=%s\n' "$PINNED" "$NEWEST" "$GAP" "$1" "${2:-}"
  exit "$3"
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)" || ROOT=""
[ -n "$ROOT" ] && [ -f "$ROOT/checks/check.sh" ] || answer off not-care 2
command -v git >/dev/null 2>&1 || answer off not-care 2

# 1. A care main checkout only, by the one derivation (as checks/adopt-release.sh asks it).
im="$(bash "$ROOT/checks/check.sh" --instance-mode "$ROOT" 2>/dev/null)" || im=""
kind=""; marker=""; mstate=""
while IFS='=' read -r k v; do
  case "$k" in kind) kind="$v" ;; marker) marker="$v" ;; marker_state) mstate="$v" ;; esac
done <<EOF
$im
EOF
{ [ "$kind" = "main" ] && [ "$marker" = "care" ] && [ "$mstate" = "ok" ]; } || answer off not-care 2

# 2. The pin: a release name by check.sh's one definition, else there is nothing to compare with.
pin=""
if [ -f "$ROOT/checks/CARE-RELEASE" ] && [ ! -L "$ROOT/checks/CARE-RELEASE" ]; then
  pin="$(tr -d '\r' < "$ROOT/checks/CARE-RELEASE" | sed '/^[[:space:]]*$/d' | head -1 | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
fi
[ -n "$pin" ] && bash "$ROOT/checks/check.sh" --release-name "$pin" 2>/dev/null || answer no-pin "" 2
PINNED="$pin"
# compared by its numeric triple alone: a legacy slugged pin (v0.52.0-<slug>) is that release, not the
# pre-release SemVer would read
ptriple="$(printf '%s\n' "$pin" | sed -n 's/^v\([0-9][0-9]*\)\.\([0-9][0-9]*\)\.\([0-9][0-9]*\).*$/\1.\2.\3/p')"
[ -n "$ptriple" ] || answer no-pin "" 2

# 3. The automatic check: the operator's opt-out, then at most once a day.
if [ "$DAILY" -eq 1 ]; then
  [ -z "${HOME:-}" ] || [ ! -e "$HOME/.config/tabularium/release-notice-off" ] || answer off opted-out 2
  sd="$(git -C "$ROOT" rev-parse --git-path tabularium-release-check 2>/dev/null)" || sd=""
  [ -n "$sd" ] || answer off no-stamp 2
  case "$sd" in /*) ;; *) sd="$ROOT/$sd" ;; esac
  today="$(date +%Y-%m-%d)"; sp="$sd-$today"
  # The day is claimed before origin is asked, by creating today's stamp exclusively (noclobber opens
  # it O_EXCL): of two sessions starting at once, only one asks. A stamp that cannot be created stops
  # the check too — an unwritable one would otherwise ask origin at every session start.
  if ! ( set -C; : > "$sp" ) 2>/dev/null; then
    { [ -e "$sp" ] || [ -L "$sp" ]; } && answer off checked-today 2
    answer off no-stamp 2
  fi
  # clear older days only: a session that claimed yesterday and resumes after midnight must not remove
  # today's claim
  for old in "$sd"-*; do
    [ "${old#"$sd"-}" \< "$today" ] && rm -f "$old"
  done 2>/dev/null
fi

# 4. Ask origin for its tags, capped, with every prompt off. Only stdout is kept: ref lines.
git -C "$ROOT" remote 2>/dev/null | grep -qx origin || answer unreachable no-origin 2
command -v python3 >/dev/null 2>&1 || answer unreachable no-python 2
ssh_env=""
if [ -z "${GIT_SSH:-}" ]; then
  ssh_base="${GIT_SSH_COMMAND:-}"
  [ -n "$ssh_base" ] || ssh_base="$(git -C "$ROOT" config --get core.sshCommand 2>/dev/null)" || ssh_base=""
  [ -n "$ssh_base" ] || ssh_base="ssh"
  ssh_env="$ssh_base -o BatchMode=yes"
fi
refs="$(env GIT_TERMINAL_PROMPT=0 GIT_ASKPASS= SSH_ASKPASS= GCM_INTERACTIVE=never \
  ${ssh_env:+"GIT_SSH_COMMAND=$ssh_env"} \
  python3 -c "$CAPPED" "$CAP" git -C "$ROOT" ls-remote --tags --refs origin 2>/dev/null)"; rrc=$?
[ "$rrc" -ne 124 ] || answer unreachable timeout 2
[ "$rrc" -eq 0 ] || answer unreachable failed 2

# 5. The newest strict release on origin, by numeric triple; a tag of any other shape is ignored, and
#    so is a number of more than nine digits, which could not be compared exactly.
NEWEST="$(printf '%s\n' "$refs" | awk -F'\t' '
  NF == 2 && $2 ~ /^refs\/tags\/v[0-9]+\.[0-9]+\.[0-9]+$/ {
    t = substr($2, 11); split(substr(t, 2), n, ".")
    if (length(n[1]) > 9 || length(n[2]) > 9 || length(n[3]) > 9) next
    if (!have || n[1] + 0 > a || (n[1] + 0 == a && (n[2] + 0 > b || (n[2] + 0 == b && n[3] + 0 > c)))) {
      have = 1; a = n[1] + 0; b = n[2] + 0; c = n[3] + 0; best = t
    }
  }
  END { if (have) print best }')"
[ -n "$NEWEST" ] || answer ok "" 0
GAP="$(awk -v p="$ptriple" -v n="${NEWEST#v}" 'BEGIN {
  split(p, a, "."); split(n, b, ".")
  if (b[1] + 0 != a[1] + 0)      print (b[1] + 0 > a[1] + 0 ? "major" : "none")
  else if (b[2] + 0 != a[2] + 0) print (b[2] + 0 > a[2] + 0 ? "minor" : "none")
  else                           print (b[3] + 0 > a[3] + 0 ? "patch" : "none")
}')"
case "$GAP" in
  minor|major) answer ok "" 1 ;;
  patch)       answer ok "" 0 ;;
  *)           GAP="none"; answer ok "" 0 ;;
esac
