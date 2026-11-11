#!/usr/bin/env bash
# checks/relay-scan.sh — the CARE→DEV relay gate (ADR-0050 Part B).
#
# WHY. Under ADR-0050 incidents flow ONE WAY: a failure observed in CARE becomes a keystone rule, an
# ADR row or an eval case written in DEV — as ABSTRACT prose composed by a person or by the assistant
# in the CARE session, never a file copy and nothing copied word for word from a care folder. That
# prose is the one channel through which a person's details could cross into a tree that must never
# hold one. It gates what DEV STORES, not what a build session READS (ADR-0050 point 8); private-mode
# lines are replaced by number before a build session reads the note.
# WHAT IT MATCHES — PERSONAL DETAILS ONLY: the identity class (names, handles, dates of birth), the
# private-mode identifier and each kept-details line (a person's details kept from the AI). Real case
# dates are not kept on the registry: a leftover PII_CASEREF line, in the registry or as a
# PII_PRIVATE_CASEREF line in the private file, is ignored — never counted, scanned or refused. The
# clinical, brand and consent classes hold condition and drug names, care-setting and relationship
# words and sensitive attributes — words that on their own fit anybody — so they are not matched here. The flip-time export gate still scans every class over what is
# published.
# The scan sits HERE, in CARE (or DEV's main checkout, whose untracked pointers name the same files),
# because the token registry and the private-mode identifier's own owner-only file (ADR-0050 point 9;
# named by the untracked checks/PRIVATE-MODE-ID) live outside every repository. DEV holds no token
# list of any kind.
#
# Usage:  checks/relay-scan.sh <file> [<file> …]     — name the outgoing files explicitly
# Exit:   0 = clean · 1 = a token class matched · 2 = BLINDED (fail closed; nothing was scanned)
#
# OUTPUT DISCIPLINE (the L10/L18 rule, and the whole point of ADR-0050 A2). A hit prints its LOCATOR
# only — `<CLASS> <file>:<line>` — never the matched text, never a class value, never the registry's
# path (that names a location in the operator's home: messages name the config file instead, the
# checks/OFFSITE-DEST discipline). The class values are read into variables and are not printed
# on any path, success or failure. Nothing here writes a file, so a scanned draft never leaves a copy.
# A scan also prints the registry's last-change DATE (its mtime: metadata, never content) — but only
# when some person's ownership ledger is newer than the registry, i.e. documents were filed that the
# registry may not know: the upkeep reminder that used to sit in the intake checklist, silent when
# there is nothing to do. The ledgers are stat'ed, never opened; no ledger path or handle is printed.
#
# FAIL CLOSED. A relay scan that examined nothing must never read as "clean": no registry, a registry
# that is a symlink or group/world-readable, a missing/renamed/duplicated class line, a matched class
# that is empty or whose regex does not compile or matches an empty line (so every line), no private-mode identifier file or
# one that is a symlink, not owner-only or not exactly one identifier line (plus v2 class lines), no UTF-8 locale on the host, a
# directory or symlink named as input, an unreadable input, or zero inputs are each exit 2 — never 0.
#
# HONEST SCOPE. A scan catches TOKENS, not a re-identifying clinical picture told in fresh words, and
# not a line copied from a care file. The abstract-prose relay rule (contributing/instances.md) and the
# CARE author's judgment remain the control there (ADR-0050 point 8). Bite-tested in checks/selftest.sh
# against a SYNTHETIC registry.
set -uo pipefail

SELF_CHECKS="$(cd "$(dirname "$0")" && pwd)" || SELF_CHECKS=""
REG_CFG_NAME="checks/FIREWALL-REGISTRY"

blind(){ printf 'relay-scan: BLINDED (fail closed) — %s\n' "$1" >&2; exit 2; }
[ -n "$SELF_CHECKS" ] || blind "cannot resolve this script's own directory — the token registry is unlocatable"

# ---- WHERE the class lines and the private-mode identifier live: checks/config-paths.sh, shared with
# snapshot.sh and install-instance.sh. Without it nothing is located, so nothing is scanned.
CFG_PATHS="$SELF_CHECKS/config-paths.sh"
[ -f "$CFG_PATHS" ] && [ -r "$CFG_PATHS" ] && . "$CFG_PATHS" 2>/dev/null && declare -F registry_path private_id_path >/dev/null \
  || blind "checks/config-paths.sh is missing or unreadable — the token registry is unlocatable"

# REG_EXT=1 means the external layout is in force (the config file exists), which is what gates the
# registry-FILE permission/symlink checks below — as the export gate gates them: they must not fire on the
# in-tree script, whose mode is 0700-ish by design.
REG_EXT=0; { [ -e "$SELF_CHECKS/FIREWALL-REGISTRY" ] || [ -L "$SELF_CHECKS/FIREWALL-REGISTRY" ]; } && REG_EXT=1
REG="$(registry_path "$SELF_CHECKS")"; REG_RC=$?
[ "$REG_RC" -eq 0 ] && [ -n "$REG" ] || blind "$REG_CFG_NAME exists but is unusable — not a readable regular file, or it names no path, or the path it names is RELATIVE (it must be absolute: this scan runs from any working directory)"
if [ "$REG_EXT" -eq 1 ]; then
  [ ! -L "$REG" ] || blind "the registry named by $REG_CFG_NAME is a SYMLINK — never followed (it could redirect the entire token set); path withheld"
  [ -f "$REG" ]   || blind "the registry named by $REG_CFG_NAME is MISSING — the config points at nothing (path withheld)"
  [ -r "$REG" ]   || blind "the registry named by $REG_CFG_NAME is unreadable (path withheld)"
  REG_MODE="$(stat -f '%Lp' "$REG" 2>/dev/null)" || REG_MODE=""
  case "$REG_MODE" in
    [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
    *) REG_MODE="$(stat -c '%a' "$REG" 2>/dev/null)" || REG_MODE="" ;;
  esac
  case "$REG_MODE" in
    [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
    *) blind "cannot read the file mode of the registry named by $REG_CFG_NAME — its exposure is unverifiable" ;;
  esac
  case "${REG_MODE: -2}" in
    *[4567]*) blind "the registry named by $REG_CFG_NAME is group- or world-readable (mode $REG_MODE) — moving it out of the tree only helps while it is owner-only; chmod 600 it" ;;
  esac
else
  [ -f "$REG" ] && [ ! -L "$REG" ] && [ -r "$REG" ] \
    || blind "no $REG_CFG_NAME config and no readable in-tree registry — there is nothing to scan against"
fi

# ---- the scanned class values (read, never printed) --------------------------------------------
# The registry carries four classes; this scan matches the one that holds personal details. The class
# SET must still be exactly these four, each on EXACTLY ONE assignment line — a fifth or renamed class
# is unruled here, so it blinds the scan until it is ruled in or out, and a later duplicate shadows the
# live value under bash last-assignment-wins while the original still extracts clean. A leftover
# PII_CASEREF line (the retired case-reference class) is skipped, so the operator may delete it any time.
RS_ALL_CLASSES='PII_IDENTITY PII_CLINICAL PII_BRAND PII_CONSENT'
RS_CLASSES='PII_IDENTITY'
rs_total="$(grep -E '^[[:space:]]*PII_[A-Za-z0-9_]*=' "$REG" 2>/dev/null | grep -vcE '^[[:space:]]*PII_(REST|CASEREF)=' || true)"
[ "$rs_total" = "4" ] || blind "the firewall token registry carries ${rs_total:-unreadable} PII_* class line(s); this scan expects 4 — rule a new class in or out of the relay (checks/relay-scan.sh) before it relays"
for rs_c in $RS_ALL_CLASSES; do
  rs_n="$(grep -cE "^[[:space:]]*${rs_c}=" "$REG" 2>/dev/null || true)"
  [ "$rs_n" = "1" ] || blind "$rs_c: expected exactly 1 assignment line in the firewall token registry, found ${rs_n:-unreadable} (missing, renamed or duplicated — rule a new class in or out of the relay first; a later duplicate shadows the live value)"
done

RS_NAMES=(); RS_VALS=()
for rs_c in $RS_CLASSES; do
  rs_v="$(sed -n "s/^[[:space:]]*${rs_c}='\(.*\)'\$/\1/p" "$REG")"
  [ -n "$rs_v" ] || blind "$rs_c class line missing, renamed or empty in the firewall token registry — a blind class is not a clean one"
  RS_NAMES+=("$rs_c"); RS_VALS+=("$rs_v")
done

# ---- the private-mode identifier's own file (ADR-0050 point 9) ----------------------
# The identifier was cut out of its class line into one owner-only file outside every repository, so
# the registry no longer carries it. A scan without that file would pass the one token that must never
# leave this machine — so every way of not having it is BLINDED, never a "clean" that skipped it. Its
# value is parsed exactly like a registry class (one single-quoted line), read into a variable, never
# printed.
PM_CFG_NAME="checks/PRIVATE-MODE-ID"
PM="$(private_id_path "$SELF_CHECKS")"; PM_RC=$?
case "$PM_RC" in
  0) ;;
  2) blind "no $PM_CFG_NAME — the private-mode identifier lives in its own file, and a scan without it would let the identifier cross the relay unscanned (split it out of the registry first: checks/topics/relay-and-export.md)" ;;
  *) blind "$PM_CFG_NAME exists but is unusable — not a readable regular file, or it names no path, or the path it names is RELATIVE (it must be absolute)" ;;
esac
[ ! -L "$PM" ] || blind "the private-mode identifier file named by $PM_CFG_NAME is a SYMLINK — never followed (path withheld)"
[ -f "$PM" ]   || blind "the private-mode identifier file named by $PM_CFG_NAME is MISSING (path withheld)"
[ -r "$PM" ]   || blind "the private-mode identifier file named by $PM_CFG_NAME is unreadable (path withheld)"
PM_MODE="$(stat -f '%Lp' "$PM" 2>/dev/null)" || PM_MODE=""
case "$PM_MODE" in
  [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
  *) PM_MODE="$(stat -c '%a' "$PM" 2>/dev/null)" || PM_MODE="" ;;
esac
case "$PM_MODE" in
  [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
  *) blind "cannot read the file mode of the private-mode identifier file — its exposure is unverifiable" ;;
esac
case "${PM_MODE: -2}" in
  00) ;;
  *) blind "the private-mode identifier file is not owner-only (mode $PM_MODE) — chmod 600 it" ;;
esac
# Private mode v2 (ADR-0029 point 13): the file may also carry one line per registry class,
# PII_PRIVATE_<CLASS>, holding the tokens of a v2 person's withheld details moved out of the readable
# registry; each is scanned as a class of its own. A PII_PRIVATE_CASEREF line (the retired
# case-reference class) is accepted and ignored. Any other class line blinds the scan.
# Every line that is not blank or a `#` comment must be one of those assignments, exactly so — a near
# miss (`export …`, spaces around `=`, another case or name) would otherwise be ignored and its value
# go unscanned. The installer, the registry's fold block and the eval scan read the file the same way.
# Under the C locale, as every reader of this file does: a UTF-8 locale would count a non-breaking space
# as indentation here and not in the eval scan. One assignment per line: a second on the same line
# would hide inside the first one's value. One quoted pair per value, no `'` inside it (Codex review of
# PR #92): read greedily, `'a'|'b'` or `'a'x'b'` is one value that matches neither token.
pm_total="$(LC_ALL=C grep -cvE '^[[:space:]]*(#.*)?$' "$PM" 2>/dev/null || true)"
pm_known="$(LC_ALL=C grep -cE "^[[:space:]]*PII_PRIVATE_(MODE_ID|IDENTITY|CASEREF|CLINICAL|BRAND|CONSENT)='[^']*'\$" "$PM" 2>/dev/null || true)"
pm_n="$(LC_ALL=C grep -cE '^[[:space:]]*PII_PRIVATE_MODE_ID=' "$PM" 2>/dev/null || true)"
pm_two="$(LC_ALL=C grep -cE '^[[:space:]]*PII_PRIVATE_[A-Z_]+=.*PII_PRIVATE_' "$PM" 2>/dev/null || true)"
{ [ "$pm_n" = "1" ] && [ "$pm_total" = "$pm_known" ] && [ "$pm_two" = "0" ]; } \
  || blind "the private-mode identifier file must carry exactly one PII_PRIVATE_MODE_ID line and, for kept details, PII_PRIVATE_<CLASS> lines only, one NAME='value' per line with no ' inside the value (write an apostrophe as .) and every other line blank or a # comment (found ${pm_total:-unreadable} other-than-blank line(s), ${pm_n:-unreadable} PII_PRIVATE_MODE_ID)"
pm_v="$(sed -n "s/^[[:space:]]*PII_PRIVATE_MODE_ID='\([^']*\)'\$/\1/p" "$PM")"
[ -n "$pm_v" ] || blind "PII_PRIVATE_MODE_ID is empty or not single-quoted in the private-mode identifier file — a blind class is not a clean one"
RS_NAMES+=("PII_PRIVATE_MODE_ID"); RS_VALS+=("$pm_v"); pm_v=""
for pm_c in IDENTITY CLINICAL BRAND CONSENT; do
  pm_k="$(LC_ALL=C grep -cE "^[[:space:]]*PII_PRIVATE_${pm_c}=" "$PM" 2>/dev/null || true)"
  case "$pm_k" in
    0) continue ;;
    1) ;;
    *) blind "the private-mode identifier file carries more than one PII_PRIVATE_${pm_c} line" ;;
  esac
  pm_v="$(sed -n "s/^[[:space:]]*PII_PRIVATE_${pm_c}='\([^']*\)'\$/\1/p" "$PM")"
  [ -n "$pm_v" ] || blind "PII_PRIVATE_${pm_c} is empty or not single-quoted in the private-mode identifier file — a blind class is not a clean one"
  RS_NAMES+=("PII_PRIVATE_${pm_c}"); RS_VALS+=("$pm_v"); pm_v=""
done
RS_COUNT="${#RS_NAMES[@]}"

# Locale pin (the L18 lesson): several registry atoms carry multibyte diacritics, and under a C/POSIX
# locale BSD grep silently NARROWS them — -i case-folding and adjacency fail with rc=1, not rc=2, so
# no tripwire fires and the scan reads clean. No `grep -q` in this pipeline: -q's early exit SIGPIPEs
# `locale -a` and the whole probe reads as failed. The trailing `|| true` quiets only that harmless
# head/grep rc; an empty result — genuine absence OR a probe error — lands in the blinded arm.
RS_LC="$(locale -a 2>/dev/null | grep -E '^(en_US|en_GB|C)\.(UTF-8|utf8)$' | head -1)" || true
[ -n "$RS_LC" ] || blind "no UTF-8 locale available on this host — diacritic registry atoms would silently narrow under a C locale"

# regex sanity per class, BEFORE any input is read: a malformed class would error every scan grep out
# silently (the L5 lesson) and a relay leak would ride through behind rc=2 read as "no hits".
rs_i=0
while [ "$rs_i" -lt "${#RS_NAMES[@]}" ]; do
  printf 'x' | LC_ALL="$RS_LC" grep -qE -- "${RS_VALS[$rs_i]}" 2>/dev/null; rs_rc=$?
  [ "$rs_rc" -ge 2 ] && blind "the ${RS_NAMES[$rs_i]} class regex does not compile (grep rc=$rs_rc)"
  # A class that matches an EMPTY line matches every line: the shape a hand edit leaves behind when it
  # cuts an alternative and keeps its `|` (the private-mode split is exactly such an edit). It would
  # red every relay forever, which trains the author to stop scanning — refuse it as unusable instead.
  printf '\n' | LC_ALL="$RS_LC" grep -qiE -- "${RS_VALS[$rs_i]}" 2>/dev/null \
    && blind "the ${RS_NAMES[$rs_i]} class regex matches an EMPTY line, so it would match every line — a stray | or an empty group left by an edit?"
  rs_i=$((rs_i+1))
done

# ---- the inputs --------------------------------------------------------------------------------
# Directories and symlinks are refused rather than walked: the relay is a named set of outgoing
# files, and a linked or recursive input is how a scan quietly covers something other than what the
# author is about to paste.
# Every grep over an input carries `--` before its operands (review round 4, F8): an outgoing draft
# named `-dash.md` would otherwise be read as an option bundle and the scan would error out — a rc≥2
# blind rather than a leak, but a scan the author cannot run at all is a scan that gets skipped.
# `test`'s single-operand forms below (-L/-d/-e/-f/-r) already take the next word literally, so a
# leading dash cannot confuse them; there is no `stat` on an input here.
[ "$#" -gt 0 ] || blind "no input file named — refusing to report clean having scanned nothing (usage: checks/relay-scan.sh <file> …)"
for rs_f in "$@"; do
  [ ! -L "$rs_f" ] || blind "input '$rs_f' is a symlink — name the file itself (a link could redirect the scan away from the outgoing bytes)"
  [ ! -d "$rs_f" ] || blind "input '$rs_f' is a directory — name the outgoing files explicitly"
  [ -e "$rs_f" ]   || blind "input '$rs_f' does not exist"
  [ -f "$rs_f" ]   || blind "input '$rs_f' is not a regular file"
  [ -r "$rs_f" ]   || blind "input '$rs_f' is unreadable"
done

# ---- the scan ----------------------------------------------------------------------------------
rs_hits=0; rs_files=0
for rs_f in "$@"; do
  rs_files=$((rs_files+1))
  rs_i=0
  while [ "$rs_i" -lt "${#RS_NAMES[@]}" ]; do
    # rc captured explicitly: rc>=2 is an ERROR, never "no hits" (the L5/ADR-0021 lesson). The
    # captured hits carry matched CONTENT and are never printed — only the line-number field is.
    rs_g="$(LC_ALL="$RS_LC" grep -inE -- "${RS_VALS[$rs_i]}" "$rs_f" 2>/dev/null)"; rs_rc=$?
    if [ "$rs_rc" -ge 2 ]; then
      blind "scan failed (grep rc=$rs_rc) on '$rs_f' for class ${RS_NAMES[$rs_i]} — a scan error is never a clean result"
    elif [ "$rs_rc" -eq 0 ]; then
      while IFS= read -r rs_l; do
        [ -n "$rs_l" ] || continue
        rs_ln="${rs_l%%:*}"
        # a non-numeric first field is grep's "Binary file … matches" (or a locator we cannot trust):
        # report the hit without inventing a line number rather than dropping it.
        case "$rs_ln" in ''|*[!0-9]*) rs_ln='?' ;; esac
        printf '%s %s:%s\n' "${RS_NAMES[$rs_i]}" "$rs_f" "$rs_ln"
        rs_hits=$((rs_hits+1))
      done <<<"$rs_g"
    fi
    rs_i=$((rs_i+1))
  done
done

# Registry upkeep happens HERE, at the transfer moment, not at intake (ADR-0013 point 5):
# a scan is only as current as the registry, and the registry only goes stale when something is filed.
# Every filing appends to the person's ownership ledger and adding a person creates it, so a ledger
# (patients/*/med/MANIFEST) NEWER than the registry file means documents were filed since the registry
# last changed — then, and only then, the scan says so and names the registry's last-change date.
# Metadata only: a ledger is stat'ed, never opened; a symlink or non-regular file never counts; no ledger
# path, handle or content is printed, nor the registry's path or content. Otherwise it stays silent, since
# a notice that repeats on every relay is learned away. A notice, never a refusal: the exit code and every
# other line are unchanged. The operator answers it once — add the missing tokens, or touch the registry
# when there are none — and either moves the registry's mtime past the ledgers.
rs_filed=0
for rs_m in "$SELF_CHECKS"/../patients/*/med/MANIFEST; do
  if [ -f "$rs_m" ] && [ ! -L "$rs_m" ] && [ "$rs_m" -nt "$REG" ]; then rs_filed=1; break; fi
done
if [ "$rs_filed" -eq 1 ]; then
  rs_day="$(date -r "$REG" +%F 2>/dev/null)" || rs_day=""
  case "$rs_day" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;; *) rs_day="unknown" ;; esac
  printf 'relay-scan: documents were filed after the token registry last changed (%s) — this scan cannot see tokens added since; have the operator add new handles, dates of birth and distinctive names first, or touch the registry file if there is nothing to add (checks/topics/relay-and-export.md → Keep the registry current), then re-scan.\n' "$rs_day"
fi

if [ "$rs_hits" -gt 0 ]; then
  printf 'relay-scan: %d hit(s) in %d file(s), %d classes — locators above, content withheld.\n' "$rs_hits" "$rs_files" "$RS_COUNT"
  printf 'Never copy a flagged line into a DEV tracked file: write it there as abstract prose, then re-scan.\n'
  printf 'A build session may read it; if a PII_PRIVATE_* line is listed above, only from a copy with those lines replaced by line number (ADR-0050 point 8).\n'
  exit 1
fi
printf 'relay-scan: clean (%d files, %d classes)\n' "$rs_files" "$RS_COUNT"
exit 0
