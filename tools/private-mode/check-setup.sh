#!/usr/bin/env bash
# tools/private-mode/check-setup.sh — is this machine ready for private mode? Read-only.
#
# Private mode masks the designated identifier on each page on this machine, before any AI pass
# (tools/private-mode/README.md), so it needs a few local tools. This names each one that is missing
# with the Homebrew command that installs it. It installs nothing, changes nothing and reads no record.
# Tabularium supports macOS only: on any other system it says so and still names what is missing,
# without install commands, with the same exit codes (CI runs it on Linux through the installer).
#
# Usage:  bash tools/private-mode/check-setup.sh [--summary]
#         --summary prints the last line only; checks/install-instance.sh runs it that way.
# Exit:   0 = everything private mode needs in this release is here · 1 = something is missing ·
#         64 = bad usage.
#
# Needed now: Python 3.9 or newer that runs (macOS ships a placeholder that only offers to install
# Apple's command line tools); poppler's pdftoppm; tesseract with its orientation data (osd) and
# English (eng); ImageMagick (magick, or convert + identify).
# Reported, not needed: the language data of each other scheme in the private-mode number list
# (id-schemes.tsv beside this script). Only the person whose number needs one needs it, and
# redact_ids.py names a missing one when it starts, so a machine is never told to install them all.
# Later, reported and never required: local masking's tools — Ollama with qwen3.5:9b, and zbar
# (ADR-0029 points 13.4-13.5: gated, not in this release). The change that ships
# masking moves them up to needed now. --summary skips them, so the installer never calls Ollama.
#
# Portable: bash 3.2 / BSD userland; bite-tested in checks/selftest.sh.
set -uo pipefail

usage(){ echo "usage: bash tools/private-mode/check-setup.sh [--summary]" >&2; exit 64; }
SUMMARY=0
[ "$#" -le 1 ] || usage
case "${1:-}" in
  '') ;;
  --summary) SUMMARY=1 ;;
  *) usage ;;
esac

OS="$(uname -s 2>/dev/null)"
TESTED_QWEN="6488c96fa5fa"   # the qwen3.5:9b weights the masking benchmark ran on (evals/local-masking)

# Tabularium supports macOS only: there, a command prints as given; on any other system it prints
# nothing, so a missing tool is still named, without an install command.
mac(){ [ "$OS" != Darwin ] || printf '%s' "$1"; }
how(){ mac "brew install $1"; }   # $1 = Homebrew formula(s)

report=""; missing=""; uses_brew=0
row(){ report="$report$(printf '  %-8s %s' "$1" "$2")
"; }
need(){ # $1 = what is missing, as the last line names it · $2 = install command (none off macOS) · $3 = detail (optional)
  row MISSING "$1${3:+ ($3)}${2:+ — install: $2}"
  missing="${missing:+$missing, }$1"
  case "$2" in "brew "*) uses_brew=1 ;; esac
}
[ "$OS" = Darwin ] || row NOTE "Tabularium supports macOS only; this system (${OS:-unknown}) gets no install commands"

# Python: run it, never just find it — on a Mac without Apple's command line tools, /usr/bin/python3
# is a placeholder that only opens Apple's install prompt and fails. Every instance needs Python (the
# installer and the guards run it), so the last line says so when it is missing.
PY="Python 3.9 or newer"; py_missing=0
py_fix="$(mac "xcode-select --install")"; py_old="$(how python)"
if ! command -v python3 >/dev/null 2>&1; then
  need "$PY" "$py_fix"; py_missing=1
else
  pv="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)" || pv=""
  case "$pv" in
    [0-2].*|3.[0-8].*) need "$PY" "$py_old" "this one is $pv"; py_missing=1 ;;
    [0-9]*.[0-9]*.[0-9]*) row ok "Python $pv" ;;
    *) need "$PY" "$py_fix" "python3 is on PATH but does not run; on a Mac, Apple's command line tools are missing"
       py_missing=1 ;;
  esac
fi

if command -v pdftoppm >/dev/null 2>&1; then row ok "poppler (pdftoppm)"
else need "poppler" "$(how poppler)"; fi

# The language data each scheme's pages are read with: the second field of every row of the number
# list, one or more codes joined with +. A list that cannot be read is named like a missing tool.
case "$0" in */*) SCHEME_LIST="${0%/*}/id-schemes.tsv" ;; *) SCHEME_LIST="id-schemes.tsv" ;; esac   # no dirname: the bites run on a bare PATH
SCHEME_LANGS=""
if [ -f "$SCHEME_LIST" ] && [ -r "$SCHEME_LIST" ]; then
  for l in $(awk -F'\t' '!/^#/ && NF == 4 { gsub(/\+/, " ", $2); print $2 }' "$SCHEME_LIST"); do
    case " $SCHEME_LANGS " in *" $l "*) ;; *) SCHEME_LANGS="${SCHEME_LANGS:+$SCHEME_LANGS }$l" ;; esac
  done
fi
[ -n "$SCHEME_LANGS" ] || need "private mode's number list (tools/private-mode/id-schemes.tsv)" "a fresh copy of this folder from the release"

if command -v tesseract >/dev/null 2>&1; then
  row ok "tesseract"
  langs="$(tesseract --list-langs 2>&1)"   # older versions print the list on stderr
  if grep -qx 'osd' <<<"$langs"; then row ok "tesseract's orientation data (osd)"
  else need "tesseract's orientation data (osd)" "$(mac "brew reinstall tesseract")"; fi
  if grep -qx 'eng' <<<"$langs"; then row ok "tesseract's language data (eng)"
  else need "tesseract's language data (eng)" "$(mac "brew reinstall tesseract")"; fi
  for l in $SCHEME_LANGS; do
    case "$l" in eng|osd) continue ;; esac
    if grep -qx "$l" <<<"$langs"; then row ok "tesseract's language data ($l)"
    else row absent "tesseract's language data ($l), needed for a person whose number row or documents are in that language$(mac " — install: brew install tesseract-lang")"; fi
  done
else
  need "tesseract" "$(how tesseract)"
fi

if command -v magick >/dev/null 2>&1; then row ok "ImageMagick (magick)"
elif command -v convert >/dev/null 2>&1 && command -v identify >/dev/null 2>&1; then row ok "ImageMagick (convert, identify)"
else need "ImageMagick" "$(how imagemagick)"; fi

if [ "$uses_brew" -eq 1 ] && ! command -v brew >/dev/null 2>&1; then   # first, since the rest need it
  report="$(printf '  %-8s %s' MISSING "Homebrew, which the brew commands below need — install it first: https://brew.sh")
$report"
fi

if [ "$OS" = Darwin ]; then
  sum_how="install commands: bash tools/private-mode/check-setup.sh (tools/private-mode/topics/setup.md)"
  full_how="install commands above"
else
  sum_how="Tabularium supports macOS only"; full_how="$sum_how"
fi
if [ -z "$missing" ]; then
  last="private mode setup: complete (local masking's tools are not needed in this release)"
elif [ "$SUMMARY" -eq 1 ]; then
  if [ "$py_missing" -eq 0 ]; then who="Needed only for a person in private mode"
  elif [ "$missing" = "$PY" ]; then who="Every instance needs Python"
  else who="Every instance needs Python, the rest only a person in private mode"; fi
  last="private mode setup: incomplete — missing $missing. $who; $sum_how"
else
  last="private mode setup: incomplete — missing $missing ($full_how)"
fi

if [ "$SUMMARY" -eq 1 ]; then
  printf '%s\n' "$last"
  [ -z "$missing" ]; exit $?
fi

later=""
lrow(){ later="$later$(printf '  %-8s %s' "$1" "$2")
"; }
if command -v ollama >/dev/null 2>&1; then
  lrow present "Ollama"
  if ol="$(ollama list 2>/dev/null)"; then
    qid="$(printf '%s\n' "$ol" | awk '$1 == "qwen3.5:9b" { print $2; exit }')"
    case "$qid" in
      '') lrow absent "the qwen3.5:9b model — get it with: ollama pull qwen3.5:9b" ;;
      "$TESTED_QWEN") lrow present "the qwen3.5:9b model, the weights the masking benchmark tested" ;;
      *) lrow present "the qwen3.5:9b model, but not the weights the masking benchmark tested ($TESTED_QWEN)" ;;
    esac
  else
    lrow '?' "the qwen3.5:9b model — not checked: Ollama is not running (open the Ollama app, or run: ollama serve)"
  fi
else
  lrow absent "Ollama$(mac " — install: brew install ollama; then: ollama pull qwen3.5:9b")"
fi
if command -v zbarimg >/dev/null 2>&1; then lrow present "zbar (zbarimg)"
else lrow absent "zbar$(mac " — install: brew install zbar")"; fi

printf 'Private mode setup on this machine (read-only: nothing is installed or changed)\n%s' "$report"
printf 'Later: local masking is not in this release, so nothing to install yet\n%s' "$later"
printf '%s\n' "$last"
[ -z "$missing" ]
