#!/usr/bin/env bash
# checks/reveal-private-id.sh — show the private-mode identifier file in Finder, for the operator to
# edit by hand (the setup of a number whose page asks for it: tools/private-mode/numbers/).
#
# A session runs it; the operator opens the file. It resolves the file through checks/PRIVATE-MODE-ID
# (checks/config-paths.sh) and hands the path to `open -R`, which opens the folder with the file
# selected. It never opens or reads the file, and prints fixed words only: never the path, the pointer
# or anything in either.
#
# Exit: 0 = shown · 1 = nothing to show (no pointer, an unusable pointer, a missing file, no Finder) ·
#       2 = checks/config-paths.sh missing
#
# Portable: bash 3.2 / BSD userland.
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)" || exit 2
# shellcheck source=checks/config-paths.sh
{ [ -f "$here/config-paths.sh" ] && [ -r "$here/config-paths.sh" ] && . "$here/config-paths.sh"; } \
  || { echo 'reveal-private-id: checks/config-paths.sh is missing or unreadable'; exit 2; }

p="$(private_id_path "$here")"; rc=$?
case "$rc" in
  0) ;;
  2) echo 'private-mode identifier: this install has no pointer file, so there is nothing to add'; exit 1 ;;
  *) echo 'private-mode identifier: the pointer file is unusable; checks/install-instance.sh care names the fix'; exit 1 ;;
esac
{ [ -f "$p" ] && [ ! -L "$p" ]; } \
  || { echo 'private-mode identifier: the file the pointer names is missing or a link; checks/install-instance.sh care names the fix'; exit 1; }
command -v open >/dev/null 2>&1 || { echo 'private-mode identifier: no Finder on this machine'; exit 1; }
open -R "$p" >/dev/null 2>&1 || { echo 'private-mode identifier: Finder did not open the folder'; exit 1; }
echo 'private-mode identifier: its folder is open in Finder, with the file selected'
