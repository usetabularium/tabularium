#!/usr/bin/env bash
# confirms.sh — the ⟨confirm⟩ queue monitor (NOT a check.sh guard).
#
# Lists two kinds of dated reminder in each person's docs and prints each as file:line with a status:
#   1. needs-confirmation tags of the exact form CLAUDE.md specifies, in profile.md, medications.md and
#      every med/analysis/**/*.md (working notes and handout drafts — a C/D fact carries its tag where
#      it is stated, and this is the one place that lists it):
#          ⟨confirm by YYYY-MM: what to obtain⟩
#      NOT scanned: med/handouts/ (a sealed handout is immutable, so an overdue tag there has no fix;
#      build-QA halts on any "⟨confirm" in a handout anyway), med/sources/ (a transcription flags its
#      uncertainty with the undated ⟨confirm⟩; the dated tag goes where the value enters the profile),
#      nmed/ and _shared/.
#   2. rows of the open-items table in patients/*/profile.md (the rows between the OPEN-ITEMS markers)
#      whose "by when" cell — the third — holds YYYY-MM-DD or YYYY-MM; a row with no date is skipped.
# Status, on the month (YYYY-MM prefix; the day is never compared):
#       future     — deadline month is ahead of now
#       due        — deadline month IS this month (chase it)
#       overdue    — deadline month already passed
#       MALFORMED  — a deadline the queue cannot read: "confirm", "by" and a four-digit year not in the
#                    exact `confirm by YYYY-MM` form (a non-breaking space or tab, a short month such as
#                    2026-1, a month outside 01-12), or a by-when date whose month is not 01-12. Prose
#                    with "confirm" alone, or "confirm by" before anything but a year, is never a tag.
# Exits 1 iff at least one tag or row is OVERDUE or MALFORMED (a deadline it cannot read may be past).
# Month granularity (lexicographic YYYY-MM compare).
#
# This is a QUEUE MONITOR, deliberately SEPARATE from check.sh: a nonzero result means "an item in
# the queue is overdue or unreadable and needs chasing", NOT "this edit session is broken". Keeping it out
# of check.sh preserves the never-end-a-session-red rule (check.sh stays about record integrity).
# The tag match keys on the ASCII substring "confirm by YYYY-MM" so it is locale-independent (the ⟨⟩
# brackets are cosmetic). PII-free: no names or conditions live in this script.
# FAILS CLOSED: a file it cannot read, or a `find` that cannot list every file, is exit 2 with the
# partial queue printed — never "no tags".
#
# Usage: checks/confirms.sh [ROOT]      ROOT defaults to the repo root (parent of checks/)
# Exit:  0 = nothing overdue or malformed; 1 = at least one overdue or malformed tag or row (a finding
#        in the record — fix the tag or chase the item); 2 = setup error: not a repo root, or the scan
#        was incomplete (the queue printed above it is partial).
set -uo pipefail
# byte semantics on every host, so the spacing alternation and [0-9] below read the same under any
# inherited locale; the file scan also passes -a, so a stray NUL or non-UTF-8 byte cannot turn a file
# "binary" and hide its lines
export LC_ALL=C
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT" || { echo "FAIL: cannot cd to $ROOT"; exit 2; }
# check.sh's L0 precondition: outside the repo `patients/` is simply absent and the queue would read
# empty. A repo root with no patients/ (the skeleton, a care install before intake) is an empty queue.
if [ ! -f CLAUDE.md ] || [ ! -d checks ]; then
  echo "FAIL: not at repo root (CLAUDE.md/checks/ missing under '$ROOT') — refusing to report an empty queue"; exit 2
fi

NOW="$(date -u +%Y-%m)"
overdue=0; due=0; future=0; malformed=0; scanned=0; incomplete=0

# a candidate tag: "confirm", any run of spacing (a plain or non-breaking space, a tab), "by", and a
# date token starting with a four-digit year. The exact form is checked per hit (tag_month).
SPACING="( |"$'\t'"|"$'\xc2\xa0'"|"$'\xe2\x80\xaf'")"
CAND="confirm${SPACING}+by${SPACING}*[0-9]{4}[0-9-]*"

# $1 = YYYY-MM, $2 = locator, $3 = line -> print one queue line and count it
report(){
  local st
  if [[ "$1" < "$NOW" ]];      then st="OVERDUE"; overdue=$((overdue+1))
  elif [[ "$1" == "$NOW" ]];   then st="due";     due=$((due+1))
  else                              st="future";  future=$((future+1)); fi
  printf '%-8s %s  %s:%s\n' "$st" "$1" "$2" "$3"
}
# $1 = locator, $2 = line, $3 = why the deadline cannot be read
malformed(){ printf 'MALFORMED %s:%s  (%s)\n' "$1" "$2" "$3"; malformed=$((malformed+1)); }

# $1 = a date token (digits and hyphens, four digits first) -> echo YYYY-MM, or echo why and return 1.
# The day, if any, is never compared, so only the year and the month are read.
date_month(){
  local y="${1%%-*}" m
  [ "$y" != "$1" ] || { echo "no -MM after the year"; return 1; }
  m="${1#*-}"; m="${m%%-*}"
  [ "${#y}" -eq 4 ] || { echo "the year is not four digits"; return 1; }
  case "$m" in 0[1-9]|1[0-2]) printf '%s-%s\n' "$y" "$m" ;; *) echo "month '$m' is not 01-12"; return 1 ;; esac
}
# $1 = a candidate tag -> echo YYYY-MM when it is the exact form, or echo why and return 1
tag_month(){
  case "$1" in
    [Cc][Oo][Nn][Ff][Ii][Rr][Mm]' '[Bb][Yy]' '[0-9]*) date_month "${1:11}" ;;
    *) echo "not 'confirm by YYYY-MM' with one plain space each"; return 1 ;;
  esac
}

# Locators — narrower than check.sh's `loc` on purpose (checks/README.md → the confirm queue): a
# profile.md / medications.md path is fixed-shape and prints for everyone, so the queue says whose item
# is due. An analysis note's name is free text and can carry the private-mode identifier, so below
# med/analysis/ it is withheld unless the person's profile.md is a regular file that plainly lacks the
# marker. Control bytes show as ?.
PM_MARK='⟨never-API⟩'
where(){ # $1 = a scanned path -> its printable locator
  local p r rc=2
  case "$1" in
    patients/*/med/analysis/*)
      r="${1#patients/}"; p="patients/${r%%/*}"
      if [ -f "$p/profile.md" ] && [ ! -L "$p/profile.md" ]; then grep -qF -- "$PM_MARK" "$p/profile.md" 2>/dev/null; rc=$?; fi
      [ "$rc" -eq 1 ] || { printf '%s/med/analysis/<name withheld: private-mode or unknown owner>' "$p" | tr '\001-\037\177' '?'; return; } ;;
  esac
  printf '%s' "$1" | tr '\001-\037\177' '?'
}

# $1 = a file -> list its tags and (for profile.md) its dated open-items rows. A read error is never
# "no tags": it marks the run incomplete.
scan(){
  local f="$1" loc hits rc ln rest toks hit m cells cell tok
  loc="$(where "$f")"
  hits="$(grep -naiE "$CAND" "$f" 2>/dev/null)"; rc=$?
  if [ "$rc" -ge 2 ]; then echo "UNREADABLE $loc — its tags and rows are not in this queue"; incomplete=1; return; fi
  scanned=$((scanned+1))
  # grep -n gives "lineno:linetext"; split on the FIRST colon only (line text keeps its own colons).
  while IFS=: read -r ln rest; do
    [ -n "${ln:-}" ] || continue
    # a single line may carry more than one tag — classify every hit
    toks="$(grep -oiE "$CAND" <<<"$rest")"; rc=$?
    [ "$rc" -ge 2 ] && { echo "UNREADABLE $loc:$ln — the tag scan failed"; incomplete=1; continue; }
    while IFS= read -r hit; do
      [ -n "$hit" ] || continue
      if m="$(tag_month "$hit")"; then report "$m" "$loc" "$ln"; else malformed "$loc" "$ln" "$m"; fi
    done <<EOF
$toks
EOF
  done <<EOF
$hits
EOF
  case "$f" in */profile.md) ;; *) return ;; esac
  # open-items rows: awk prints "lineno<TAB>third cell" for every table row inside the block (the header
  # and separator rows carry no date, so the date match skips them)
  cells="$(awk -F'|' '/OPEN-ITEMS:BEGIN/{i=1;next} /OPEN-ITEMS:END/{i=0} i && /^[[:space:]]*\|/ {print NR "\t" $4}' "$f" 2>/dev/null)" \
    || { echo "UNREADABLE $loc — its open-items rows are not in this queue"; incomplete=1; return; }
  while IFS=$'\t' read -r ln cell; do
    [ -n "${ln:-}" ] || continue
    toks="$(grep -oE '[0-9]{4}-[0-9][0-9-]*' <<<"$cell")"; rc=$?
    [ "$rc" -ge 2 ] && { echo "UNREADABLE $loc:$ln — the row scan failed"; incomplete=1; continue; }
    tok="${toks%%$'\n'*}"
    [ -n "$tok" ] || continue
    if m="$(date_month "$tok")"; then report "$m" "$loc" "$ln"; else malformed "$loc" "$ln" "by-when $m"; fi
  done <<EOF
$cells
EOF
}

list=""
if [ -L patients ] || { [ -e patients ] && [ ! -d patients ]; }; then
  echo "FAIL: patients/ is not a real directory — refusing to list a queue through it"; incomplete=1
elif [ -d patients ]; then
  # rc != 0 = some directory could not be listed: the files under it are missing from the queue
  list="$(find patients -type f \( -name 'profile.md' -o -name 'medications.md' -o \( -path '*/med/analysis/*' -name '*.md' \) \) 2>/dev/null)" \
    || { echo "FAIL: find could not list every file under patients/ — the queue below is partial"; incomplete=1; }
  list="$(printf '%s\n' "$list" | sort)" || { echo "FAIL: could not sort the file list"; incomplete=1; }
fi
while IFS= read -r f; do
  [ -n "$f" ] || continue
  scan "$f"
done <<EOF
$list
EOF

echo "--------"
echo "confirm queue @ $NOW : $overdue overdue, $due due-this-month, $future future, $malformed malformed — $scanned file(s) scanned"
if [ "$incomplete" -ne 0 ]; then echo "FAIL: the scan is incomplete (see above) — the queue is partial, not empty"; exit 2; fi
[ "$overdue" -eq 0 ] && [ "$malformed" -eq 0 ]
