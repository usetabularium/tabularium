#!/usr/bin/env bash
# checks/setup-mac.sh — what a caregiver's Mac needs for Tabularium, and getting it there.
#
# Run by a session on a person's behalf (SETUP.md, _templates/INTAKE.md), which puts the lines below into plain
# words. Base setup is git and Python; private mode's tools and the handout renderer come when first
# needed. Nothing here touches a record, and nothing installs without the person's yes, which the
# session asks for first.
#
# Usage:  checks/setup-mac.sh                       what this Mac has and what is missing. Changes nothing.
#         checks/setup-mac.sh pre-approve           pre-approve the routine safe steps for this folder
#         checks/setup-mac.sh private-mode <lang>   install private mode's tools, with the text-recognition
#                                                   language of the person's documents (a tesseract code:
#                                                   pol, deu, eng) plus English
#         checks/setup-mac.sh handouts              install what rendering a handout needs
# Exit:   0 = complete · 1 = something is missing or failed · 2 = stopped for the person: an
#         `in Terminal:` line names a step needing a password or Apple's dialog, or a `restart:` line
#         asks for the Claude app to be quit and reopened · 64 = bad usage.
#
# Lines: `ok`, `MISSING … — why: …`, `in Terminal: <command>`, `restart: …`, `note: …`, and a last
# `setup: …` line.
# Apple's git and python3 are placeholders until the command line tools are in: running one only
# opens Apple's install prompt. So `xcode-select -p` is asked first and neither is run without it.
#
# Portable: bash 3.2 / BSD userland; bite-tested in checks/selftest.sh.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)" || { echo "setup: cannot find the Tabularium folder" >&2; exit 1; }
usage(){ echo "usage: checks/setup-mac.sh [pre-approve | private-mode <language code> | handouts]" >&2; exit 64; }

# Where Apple's placeholders sit, and Homebrew's two standard homes; replaced in the bites, whose stub
# machines have neither.
APPLE_BIN="${SETUP_APPLE_BIN:-/usr/bin}"
BREW_DIRS="${SETUP_BREW_DIRS:-/opt/homebrew/bin /usr/local/bin}"
BREW_INSTALL='/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
# The Python the handout renderer's pinned packages install on (_templates/handout-assets/requirements-render.txt
# is a freeze on it). Apple's Python 3.9 cannot install them. A change of pin changes this line.
RENDER_PYTHON="python@3.14"

is_mac(){ [ "$(uname -s 2>/dev/null)" = "Darwin" ]; }
not_mac(){ echo "setup: this is not a Mac — macOS is the only system Tabularium supports"; exit 1; }

# ---- what this Mac has ---------------------------------------------------------------------------
inspect(){
  local missing="" dev=0 g p gr pv here home
  is_mac || not_mac
  xcode-select -p >/dev/null 2>&1 && dev=1
  g="$(command -v git 2>/dev/null)" || g=""
  p="$(command -v python3 2>/dev/null)" || p=""
  # without the tools, Apple's own copies are placeholders and are not run
  if [ "$dev" -eq 0 ] && { [ -z "$g" ] || [ "$g" = "$APPLE_BIN/git" ] || [ -z "$p" ] || [ "$p" = "$APPLE_BIN/python3" ]; }; then
    echo "MISSING Apple's command line tools — why: git and Python come with them. git keeps Tabularium's own files at a known version (your records never go into it); Python runs its checks and filing tools"
    echo "in Terminal: xcode-select --install"
    missing="Apple's command line tools"
  else
    # Apple's installer is the remedy only while Apple's tools are missing; with them in, it fixes neither
    # git nor Python, so the line says what is wrong instead of sending the person round in a circle
    gr=0; [ -n "$g" ] && { git --version >/dev/null 2>&1 || gr=$?; } || gr=127
    if [ "$gr" -eq 0 ]; then echo "ok      git"
    elif [ "$gr" -eq 69 ]; then
      echo "MISSING git — why: it keeps Tabularium's own files at a known version. Apple's licence for Xcode has not been accepted on this Mac, so git will not run; accepting it needs your password"
      echo "in Terminal: sudo xcodebuild -license"; missing="git"
    elif [ "$dev" -eq 1 ]; then
      echo "MISSING git — why: it keeps Tabularium's own files at a known version. Apple's command line tools are in, but the git at ${g:-(none on the path)} does not run"; missing="git"
    else echo "MISSING git — why: it keeps Tabularium's own files at a known version"; echo "in Terminal: xcode-select --install"; missing="git"; fi
    pv="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)" || pv=""
    case "$pv" in
      [0-2].*|3.[0-8].*)
        if [ "$dev" -eq 1 ]; then
          echo "MISSING Python 3.9 or newer (this one is $pv, at $p) — why: it runs Tabularium's checks and filing tools. An older Python comes before Apple's on this Mac's path"
        else
          echo "MISSING Python 3.9 or newer (this one is $pv) — why: it runs Tabularium's checks and filing tools"
          echo "in Terminal: xcode-select --install"
        fi
        missing="${missing:+$missing, }Python" ;;
      [0-9]*.[0-9]*.[0-9]*) echo "ok      Python $pv" ;;
      *) if [ "$dev" -eq 1 ]; then
           echo "MISSING Python 3.9 or newer — why: it runs Tabularium's checks and filing tools. Apple's command line tools are in, but the python3 at ${p:-(none on the path)} does not run"
         else
           echo "MISSING Python 3.9 or newer — why: it runs Tabularium's checks and filing tools"
           echo "in Terminal: xcode-select --install"
         fi
         missing="${missing:+$missing, }Python" ;;
    esac
  fi
  here="$(cd "$ROOT" && pwd -P)/"; home="$(cd "$HOME" 2>/dev/null && pwd -P)"
  case "$here" in
    "$home/Desktop/"*|"$home/Documents/"*|"$home/Library/Mobile Documents/"*|"$home/Library/CloudStorage/"*)
      echo "note: this folder sits where iCloud's Desktop & Documents sync or a cloud drive can copy it off this Mac; records belong in a Tabularium folder directly in the home folder" ;;
  esac
  echo "note: Claude sessions send what they read to the AI service; check your plan's data settings."
  if [ -z "$missing" ]; then echo "setup: base complete (git and Python)"; return 0; fi
  echo "setup: base incomplete — missing $missing"
  return 1
}

# ---- Homebrew: found, or a step for the person --------------------------------------------------
# A brew only in its standard home is not on a new install's PATH, and neither is anything it adds; the
# masking tools are looked up on PATH in later sessions, so its one line goes where Homebrew says to. The
# Claude app reads that path only when it starts, so the app's sessions see the new tools after it is
# quit and reopened: the step then ends on a `restart:` line (exit 2), not on complete.
BREW_OFF_PATH=0
restart_or_done(){ # $1 = the step's complete line
  if [ "$BREW_OFF_PATH" -eq 1 ]; then
    echo "restart: quit the Claude app completely and open it again: its sessions find these tools only after that"
    echo "$1, once the Claude app has been reopened"
    return 2
  fi
  echo "$1"
}
# The login profile the account's shell reads: zsh, the default since macOS 10.15, reads .zprofile; bash
# reads only the first of .bash_profile, .bash_login and .profile that exists, so the line joins that one
# (a new .bash_profile would hide an existing .profile) and .bash_profile is made only when none exists.
login_profile(){
  local f
  case "${SHELL##*/}" in
    bash) for f in .bash_profile .bash_login .profile; do [ -f "$HOME/$f" ] && { echo "$HOME/$f"; return; }; done
          echo "$HOME/.bash_profile" ;;
    *)    echo "$HOME/.zprofile" ;;
  esac
}
find_brew(){
  local d prof pf
  if command -v brew >/dev/null 2>&1; then return 0; fi
  for d in $BREW_DIRS; do
    [ -x "$d/brew" ] || continue
    PATH="$d:$PATH"; export PATH; BREW_OFF_PATH=1
    # Only a live line for this Homebrew counts: a commented-out one, or one naming another Homebrew home
    # (an Intel Mac's profile on Apple silicon), would leave every later run asking for a restart.
    # Guarded, so the line stays harmless at every login once Homebrew is removed.
    pf="$(login_profile)"
    prof="$(grep -v '^[[:space:]]*#' "$pf" 2>/dev/null)" || prof=""
    if ! grep -qF "$d/brew shellenv" <<<"$prof"; then
      printf '[ -x %s/brew ] && eval "$(%s/brew shellenv)"\n' "$d" "$d" >> "$pf" \
        && echo "ok      added Homebrew to your shell's path (${pf##*/} in the home folder)"
    fi
    return 0
  done
  echo "MISSING Homebrew — why: it installs the free tools this step needs. Its installer asks for your password"
  echo "in Terminal: $BREW_INSTALL"
  echo "setup: stopped — run the line above, then run this step again"
  exit 2
}

brew_install(){ # the formulae to install; brew's own output is left on screen
  [ "$#" -gt 0 ] || return 0
  brew install "$@" || { echo "setup: Homebrew could not install $* — its message is above"; exit 1; }
}

# ---- private mode's tools -------------------------------------------------------------------------
# tools/private-mode/check-setup.sh stays the one list of what private mode needs, the number list's
# language data included, so the chosen language adds to that list and never replaces it. A care-only
# install needs no token registry or identifier file, and this creates neither, nor their pointers.
has_lang(){ local l; l="$(tesseract --list-langs 2>&1)" || l=""; grep -qx "$1" <<<"$l"; }   # no pipe into grep -q: under pipefail its SIGPIPE reads as a miss
# a tesseract code: three lower-case letters, perhaps a suffix (chi_sim). Matched in the C locale, where a-z
# is the 26 letters: under UTF-8, bash 3.2's range takes capitals too, and `POL` would reach the download.
lang_ok(){
  local LC_ALL=C
  case "$1" in
    osd|'') return 1 ;;
    *[!a-z_]*) return 1 ;;
    [a-z][a-z][a-z]|[a-z][a-z][a-z]_[a-z]*) return 0 ;;
  esac
  return 1
}
private_mode(){
  local lang="$1" want="" check="$ROOT/tools/private-mode/check-setup.sh" missing=""
  lang_ok "$lang" || usage
  is_mac || not_mac
  find_brew
  command -v pdftoppm >/dev/null 2>&1 || want="$want poppler"
  command -v tesseract >/dev/null 2>&1 || want="$want tesseract"
  { command -v magick >/dev/null 2>&1 || { command -v convert >/dev/null 2>&1 && command -v identify >/dev/null 2>&1; }; } || want="$want imagemagick"
  # shellcheck disable=SC2086
  brew_install $want
  # Homebrew's tesseract brings English and the orientation data; every other language is in one pack
  if ! has_lang "$lang" || ! bash "$check" --summary >/dev/null 2>&1; then
    brew_install tesseract-lang
  fi
  for want in eng "$lang"; do
    if has_lang "$want"; then echo "ok      text recognition ($want)"
    else missing="${missing:+$missing, }text recognition ($want)"; fi
  done
  if ! bash "$check" --summary; then missing="${missing:+$missing, }what the line above names"; fi
  if [ -z "$missing" ]; then restart_or_done "setup: private mode's tools complete"; return; fi
  echo "setup: private mode's tools incomplete — missing $missing"
  return 1
}

# ---- the handout renderer -------------------------------------------------------------------------
handouts(){
  local f want="" py
  is_mac || not_mac
  find_brew
  for f in "$RENDER_PYTHON" pango cairo glib poppler; do
    brew list --versions "$f" >/dev/null 2>&1 || want="$want $f"
  done
  # shellcheck disable=SC2086
  brew_install $want
  py="$(brew --prefix "$RENDER_PYTHON" 2>/dev/null)/bin/${RENDER_PYTHON/@/}"
  if ! PYTHON="$py" bash "$ROOT/_templates/handout-assets/rebuild-render-env.sh"; then
    echo "setup: the handout renderer did not build — its message is above"
    return 1
  fi
  restart_or_done "setup: handout tools complete"
}

# ---- the narrow pre-approval: checks, snapshots, filing tools; anything else still asks ------------
pre_approve(){
  command -v python3 >/dev/null 2>&1 || { echo "setup: Python is missing — run this script with no argument first"; exit 1; }
  mkdir -p "$ROOT/.claude" || { echo "setup: cannot create .claude/"; exit 1; }
  python3 - "$ROOT/.claude/settings.local.json" <<'PY'
import json, os, sys, tempfile

path = sys.argv[1]
RULES = []
for script in ("check", "snapshot", "confirms"):
    for run in ("bash checks/%s.sh", "checks/%s.sh"):
        RULES.append("Bash(%s)" % (run % script))
        RULES.append("Bash(%s *)" % (run % script))
# the filing tools as the procedures call them: the ledger's first record, its appends and its read-only check
# (not migrate or refresh-checkpoint), the word-for-word capture, and the large-original viewer in its venv
for sub in ("init", "append", "verify"):
    RULES.append("Bash(python3 -m tools.person_ownership --root . %s *)" % sub)
RULES.append("Bash(python3 -m tools.interview_capture *)")
RULES.append("Bash(.venv-render/bin/python -m tools.original_view *)")

def refuse(msg):
    print("setup: %s" % msg)
    sys.exit(1)

data = {}
if os.path.islink(path):
    refuse(".claude/settings.local.json is a symlink; nothing written")
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        refuse(".claude/settings.local.json cannot be read as settings; nothing written")
    if not isinstance(data, dict):
        refuse(".claude/settings.local.json does not hold settings; nothing written")
perms = data.setdefault("permissions", {})
allow = perms.setdefault("allow", []) if isinstance(perms, dict) else None
if not isinstance(allow, list):
    refuse("the permissions in .claude/settings.local.json are not in the usual form; nothing written")
added = [r for r in RULES if r not in allow]
if not added:
    print("ok      routine steps already pre-approved")
    sys.exit(0)
allow.extend(added)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".settings.", suffix=".tmp")
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
os.replace(tmp, path)
print("ok      routine steps pre-approved (the checks, snapshots and filing tools); anything else still asks")
PY
}

case "${1:-}" in
  '')           [ "$#" -le 1 ] || usage; inspect ;;
  pre-approve)  [ "$#" -eq 1 ] || usage; pre_approve ;;
  private-mode) [ "$#" -eq 2 ] || usage; private_mode "$2" ;;
  handouts)     [ "$#" -eq 1 ] || usage; handouts ;;
  *) usage ;;
esac
