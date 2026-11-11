#!/usr/bin/env bash
# checks/config-paths.sh — where the two out-of-tree files live. Sourced, never run: snapshot.sh,
# relay-scan.sh and install-instance.sh load it from their own directory and refuse to run without it.
#   registry_path   — the file holding the firewall's PII_* class lines (ADR-0050 Part A2): the absolute
#                     path named by <checks>/FIREWALL-REGISTRY, else the in-tree publish-skeleton.sh.
#   private_id_path — the private-mode identifier file named by <checks>/PRIVATE-MODE-ID (ADR-0050
#                     point 9).
# Both take the checks/ directory whose pointer is read, which need not be the one this file sits in
# (snapshot.sh passes the snapshotted root's). They read the pointer and print a path; they never open
# the file it names. One copy since 2026-11-01; the consumers held three, equal by a selftest lint.
registry_path(){ # $1 = the checks/ directory -> path holding the PII_* class lines (rc 1 = unusable)
  local k="$1" c p
  c="$k/FIREWALL-REGISTRY"
  if [ -e "$c" ] || [ -L "$c" ]; then
    [ -f "$c" ] && [ ! -L "$c" ] && [ -r "$c" ] || return 1
    p="$(awk '{ sub(/[[:space:]]*$/, ""); sub(/^[[:space:]]*/, "") } /^#/ { next } /^$/ { next } { print; exit }' "$c" 2>/dev/null)" || return 1
    case "$p" in '~') p="$HOME" ;; '~/'*) p="$HOME/${p#\~/}" ;; esac
    [ -n "$p" ] || return 1
    case "$p" in /*) ;; *) return 1 ;; esac   # ABSOLUTE only: this config is resolved from any cwd
    printf '%s\n' "$p"
    return 0
  fi
  printf '%s\n' "$k/publish-skeleton.sh"
}

private_id_path(){ # $1 = the checks/ directory -> the private-mode identifier file (rc 1 = unusable, 2 = no pointer)
  local k="$1" c p
  c="$k/PRIVATE-MODE-ID"
  { [ -e "$c" ] || [ -L "$c" ]; } || return 2
  [ -f "$c" ] && [ ! -L "$c" ] && [ -r "$c" ] || return 1
  p="$(awk '{ sub(/[[:space:]]*$/, ""); sub(/^[[:space:]]*/, "") } /^#/ { next } /^$/ { next } { print; exit }' "$c" 2>/dev/null)" || return 1
  case "$p" in '~') p="$HOME" ;; '~/'*) p="$HOME/${p#\~/}" ;; esac
  [ -n "$p" ] || return 1
  case "$p" in /*) ;; *) return 1 ;; esac   # ABSOLUTE only: this pointer is resolved from any cwd
  printf '%s\n' "$p"
  return 0
}
