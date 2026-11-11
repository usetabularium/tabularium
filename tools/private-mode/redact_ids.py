#!/usr/bin/env python3
"""
Private mode (experimental, ADR-0029) — LOCAL identifier redaction before any AI/vision pass.

Purpose: when the operator declares that a patient's government identity number must never
transit the AI service's API, this tool locates and masks that identifier on scanned documents
LOCALLY (poppler + tesseract + ImageMagick — no LLM, no network), so the model only ever sees
the redacted rasters. Pipeline order is the point: nothing is shown to a model until this ran
and the operator has eyeballed the result.

Safety contract (load-bearing):
  * This script is the ONLY thing that reads raw OCR text. Its stdout / JSON log contain ONLY
    non-sensitive metadata: page counts, bbox coordinates, match *reasons*, flags, tool-stage
    names, sha256 hashes. It NEVER prints recognised text, digit strings, the label token, the
    DOB, or full command argv, and reason strings carry no identifier digits.
  * Raw tesseract TSVs (which may contain the identifier) live in --work and are the caller's
    duty to delete after the run (they never leave the machine either way). --work also briefly
    holds a full-bytes input snapshot per document (input-snapshots/, the immutable capture the
    pipeline renders from); it is unlinked best-effort at end-of-document, and each page's
    darkened copy as soon as it is read, but treat
    --work as raw-identifier-bearing until deleted regardless.
  * The only output intended for eventual model consumption is an OPERATOR_APPROVED artifact
    (see run-state contract below) — a merely-processed run is NOT approval.

Run-state contract (handover 04 / ADR-0029 point 8):
    NEW -> LOCALLY_PROCESSED -> AWAITING_OPERATOR -> OPERATOR_APPROVED
  This script (redact_ids.py) takes a run from NEW through AWAITING_OPERATOR: every invocation
  gets a fresh run_id, renders/OCRs into run-scoped directories (so a stale or shorter rerun can
  never resurface a prior run's pages), and atomically promotes a hash-manifested redacted set
  into --redacted/<doc>/ (superseding, never merging with, any prior set for that document).
  OPERATOR_APPROVED is a SEPARATE, later step performed by approve_redaction.py, which verifies
  artifact hashes against the manifest before promoting into --approved/<doc>/ — the only
  location a later model/vision pass may treat as eligible input. A clean/HOLD/failed run of
  THIS script never writes into --approved; only approve_redaction.py does, and only after
  verification.

Pipeline per PDF page:
  snapshot the input PDF into the run-owned 0700 work area, hashing the COPIED bytes
  (the mutable inbox path is opened once, no-follow, and never reopened — id, manifest hash and
  rendered bytes all bind that one immutable capture)
  -> render (pdftoppm --dpi, from the snapshot) -> OSD orientation-correct -> OCR (tesseract TSV) -> detect
  -> burn padded black boxes (ImageMagick) -> ITERATE: re-OCR the masked raster, mask any
  surviving strong candidate wider, repeat until clean or --max-iters (then HOLD the page).
  Every external command is checked (return code, expected-output existence/size/freshness);
  every write to a final filename goes through a temp-name + os.replace so a failed step can
  never leave a stale file under the name a later step expects to find.

Detection rules (generous — over-mask beats under-mask; operator gate recovers over-masks):
  prefix    an 11-digit run whose first 6 digits encode the patient's DOB per the scheme
            (strict digits + an OCR-confusables fuzzy pass: O->0, I/l->1, B->8, S->5, ...)
  checksum  any 11-digit run passing the scheme checksum (real false-positive rate ~10% on
            arbitrary digit windows — expect over-masks; the gate resolves them)
  label     any numeric token within ~2 line-heights right/below of the printed ID label
            (--label-token; pass the label exactly as printed on your documents)
  lowconf   a word OCR read below its confidence floor (CONF_MIN) is not dropped when it looks like
            the identifier: it takes part in a prefix window, or it is identifier-length (>= 9
            digits or confusables) with at least 6 real digits. Faint ink OCR does not read at all
            gets a second read on a darkened copy of the page, whose own paper sets the black point:
            what only that read finds counts here too, and so does a hit of it that reaches beyond the
            boxes the plain read made. Masked, and the page HOLDs as LOW_CONFIDENCE_CANDIDATE for the
            operator's explicit acknowledgement.
  The prefix rule also joins a line to the line that continues it — the next one on the same row, or
  the one just below in the same column — so an identifier OCR split over two lines is still masked
  (one box per part). The checksum rule stays per line there (its ~10% false-hit rate would multiply
  over line pairs), and reads OCR confusables only within one identifier-length word, at most
  FUZZY_MAX_SUBS of them per window.
  Date-formatted tokens (e.g. 03.02.1901) are excluded from the digit stream: a printed date
  of birth CONTAINS the prefix digits but is never the identifier itself, and DOB stays
  API-visible on purpose (person-separation recon needs it).
  The rules above are the sliding window of 'pl-id'. The other schemes match WHOLE printed numbers
  instead: a run of neighbouring words on a line or across the join to the line that continues it (split
  by spaces, a hyphen or a slash, which binds towards a number part on its far side; a label or sign
  glued on in front is dropped; a date-shaped word may be part of one), never a window inside a longer
  digit run, since their checksums are weak or absent:
  prefix    the number opens with what the DOB gives (a set: Czech/Slovak offsets; French year and
            month), when a DOB is given — a DOB is optional for them
  shape     the scheme's print form (US separated; Czech/Slovak with a slash; French keyless 13 only
            beside a French label), and the US masked form showing only the last four digits; under
            the prefix rule. Bare nine digits (US; Czech/Slovak) mask as id-shape-bare and hold the
            page when nothing else fired
  checksum  forms resting on a check (French key; Czech/Slovak bare ten divisible by 11, or nine leaving
            10 and a last 0) mask as
            id-shape: their false-hit rate is far below 'pl-id''s, so they do not hold the page
  label     the scheme's shipped label words (accent-folded, whole word; a word written in capitals
            below matches only in capitals, so 'INS' never hits 'insulin') mask a number near them like
            --label-token, a label read below the confidence floor too; only the strong ones hold the
            page when no number is near
  lowconf   such a number with a word below the confidence floor, or a low word of that length
  known     a scheme whose number holds no date ('us-ssn') searches the person's own number instead of its
            shape (ADR-0074): --number-from-identity reads it from their identity file; the sliding window
            takes it whole as its prefix, through confusables and up to KNOWN_MAX_OFF wrong digits, on a
            line and across the join, faint words too; its last-four form and its labels still count; a
            run without it is refused

Fail-closed flags -> route the page to the operator eyeball / HOLD, never to vision:
  LABEL_NO_CANDIDATE                    the ID label was seen but no maskable numeric found near it
  NEAR_EMPTY_OCR                        page OCR near-empty (unreadable scan) — do NOT "just look" with vision
  MASK_VERIFY_FAILED                    the verify loop did not converge — ships over-masked, not clean
  CHECKSUM_ONLY_EXPECT_FALSE_POSITIVE   only a checksum hit fired (real ~10% false-positive rate)
  OSD_UNRELIABLE                        orientation could not be determined (nonzero/unparseable OSD, or
                                         a turn below OSD_CONF_MIN, left unapplied) — fail closed; the
                                         operator confirms orientation, never a silent 0
  LOW_CONFIDENCE_CANDIDATE              an identifier-shaped word OCR read below its confidence floor was
                                         masked — the operator checks it on the original
  DARKENED_READ_UNREADABLE              the darkened copy came out dark (dark paper, a dark photo), so faint
                                         ink went unchecked — the operator checks the original for it
  BARE_NUMBER_ONLY                      only bare nine-digit numbers fired (a phone or record number can
                                         have that shape) — the operator checks what was masked
  SCANNABLE_CODE                        French "INS à scanner": a printed code holds the number, and this
                                         tool masks text only — the operator covers the code and rescans
  PROCESS_ERROR                         a pipeline/tool step failed for this page — NO raster is
                                         left for it (one burned before the failure is removed before
                                         promotion); the page is absent from --redacted/<doc>/
                                         until a rerun succeeds (never publish a possibly-unverified
                                         or unmasked image)

Any flag above, or a document-level error (RENDER_FAILED / PAGE_COUNT_MISMATCH), makes the whole
invocation exit nonzero (see EXIT_* below) — "processed" is never silently "clean," and neither
state implies OPERATOR_APPROVED.

Schemes (--scheme KEY[,KEY], required: the ones the person's profile tag names, ADR-0062; a run leaving
one out is refused, an extra key only masks more; in a care folder with people, --inbox must be in a tray). Each key
is a row of id-schemes.tsv, the number list guard L10 also reads, which gives its OCR language
(--lang's default joins the rows' languages with '+'); SCHEMES below holds the detection facts. A DOB
is required only when a selected scheme needs one ('pl-id'). These are public facts of the schemes,
not personal data. Another scheme: a row in the list and an entry here, together. An entry without its
row waits, its key refused (cz-sk-rc and fr-nir, until a later page round passes them).
--covered-by-hand (ADR-0076): the profile's tag names the key `unlisted` (ADR-0077), and the operator
covered that number, not on the list, by hand on every page before
scanning, with any printed code that may hold it. It stands in place of --scheme, with --lang naming the documents' language, or beside it for
a person who also has a listed number. The run looks for no unlisted number; the operator's look-over
is the check of the covering.
  'pl-id'    the Polish 11-digit national identity number. Prefix = YYMMDD of the DOB with the century
             encoded in the month field (+0 for 1900s, +20 for 2000s, +80 for 1800s); checksum weights
             1,3,7,9,1,3,7,9,1,3, check digit = (10 - sum mod 10) mod 10.
  'us-ssn'   US SSN and ITIN (and other 9NN tax numbers): nine digits; never issued: area 000 or 666,
             group 00, serial 0000. No checksum, no date.
  'cz-sk-rc' Czech and Slovak rodné číslo and the Czech insured numbers built like it: YYMMDD + three
             digits (born before 1954) or four. Month +50 (women), +20/+70 (supplementary batch); day
             +40 (EČP) or +50 (generated insured numbers). Ten digits divisible by 11, a weak sign only.
  'fr-nir'   French NIR / matricule INS: sex digit, YY, MM (20-99 when unknown), five place characters
             (Corsica 2A/2B), three order digits, then an optional key = 97 - (number mod 97), the
             Corsican letter read as 0 and 1,000,000 (A) or 2,000,000 (B) taken off first.
"""
import argparse, csv, datetime, glob, hashlib, json, math, os, re, secrets, shutil, stat, subprocess, sys, tempfile, time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import id_schemes  # noqa: E402  the number list, beside this file

TOOL_NAME = 'redact_ids.py'
TOOL_VERSION = '3.4.0'
SCHEMA_VERSION = 3  # HO-09: strict, versioned manifest/approval schema; v2 (permissive) is rejected closed
MIN_PYTHON = (3, 8)  # os.replace/tempfile behavior relied on below is stable from 3.6+; pin 3.8 as a floor

# ---- documented exit-status contract (handover 04) ----
# 0  = clean local processing, zero flags/errors anywhere -> AWAITING_OPERATOR. NOT approval.
# 10 = HOLD: >=1 page carries a fail-closed flag (label/near-empty/non-converged/checksum-only/
#      orientation/low-confidence/darkened read unreadable/bare number only/scannable code),
#      but no hard tool/process failure -> AWAITING_OPERATOR, but never treat as clean.
# 11 = ERROR: >=1 document/page hit a hard failure (render/page-count/tool/process) -> some or
#      all pages of that document are NOT in --redacted/<doc>/ pending a rerun.
# 12 = empty input: --inbox held zero *.pdf files. An error, not a successful zero-document run.
# 64 = invalid invocation (bad CLI args / missing executables) — nothing was processed.
# 65 = run-state error (e.g. run-scoped directory collision) — extremely unlikely; investigate host.
EXIT_OK_AWAITING_OPERATOR = 0
EXIT_HOLD = 10
EXIT_PROCESS_ERROR = 11
EXIT_EMPTY_INPUT = 12
EXIT_INVALID_INVOCATION = 64
EXIT_STATE_ERROR = 65

HOLD_FLAGS = {'LABEL_NO_CANDIDATE', 'NEAR_EMPTY_OCR', 'MASK_VERIFY_FAILED',
              'CHECKSUM_ONLY_EXPECT_FALSE_POSITIVE', 'OSD_UNRELIABLE', 'LOW_CONFIDENCE_CANDIDATE',
              'DARKENED_READ_UNREADABLE', 'BARE_NUMBER_ONLY', 'SCANNABLE_CODE'}
ERROR_FLAGS = {'PROCESS_ERROR'}
DOC_ERROR_STATES = {'RENDER_FAILED', 'PAGE_COUNT_MISMATCH', 'SYMLINK_REJECTED'}

# --- strict-schema vocabularies (HO-09 item 2) — one canonical set, shared by the manifest
#     validator (used by approve_redaction) and the on-disk shape produced by this tool ---
KNOWN_PAGE_FLAGS = HOLD_FLAGS | ERROR_FLAGS                       # HOLD_* + OSD_UNRELIABLE + PROCESS_ERROR
KNOWN_DOC_ERRORS = DOC_ERROR_STATES | ERROR_FLAGS                 # doc-level error vocabulary (+ PROCESS_ERROR)
KNOWN_REASONS = {'id-prefix', 'id-prefix-fuzzy', 'id-checksum', 'id-checksum-fuzzy',
                 'id-label-proximity', 'id-low-confidence', 'id-shape', 'id-shape-fuzzy', 'id-shape-bare',
                 'id-last-four', 'id-known', 'id-known-fuzzy'}
ALL_RULES = ('prefix', 'checksum', 'label', 'lowconf')
DEFAULT_RULES = ALL_RULES

# opaque per-document identity: doc-<first 16 hex of the input PDF's sha256>. Carries ZERO bytes
# derived from the source filename/path (HO-09 item 3) — a filename can itself contain the never-API
# identifier, and an agent shell's stdout transits the model. Content-derived => a gate-fix rerun of
# the same bytes lands under the same id and supersedes the prior set (ADR-0029 point 8).
DOC_ID_RE = re.compile(r'^doc-[0-9a-f]{16}$')
RUN_ID_RE = re.compile(r'^\d{8}T\d{6}Z-[0-9a-f]{8}$')
_HEX64_RE = re.compile(r'^[0-9a-f]{64}$')
_PAGE_FILE_RE = re.compile(r'^page-\d+\.png$')
NEVER_API_MAP_NAME = '.never-api-source-map.json'  # LOCAL-ONLY opaque-id -> source-filename map

# manifest field sets (strict: unknown fields reject; missing required fields reject)
_MANIFEST_REQUIRED = {'schema_version', 'kind', 'tool', 'tool_version', 'run_id', 'doc',
                      'input_sha256', 'created_utc', 'n_pages', 'expected_pages', 'pages',
                      'error', 'notes', 'state'}
_MANIFEST_OPTIONAL = {'error_stage', 'error_reason', 'error_type'}
_PAGE_REQUIRED = {'page', 'w', 'h', 'n_words', 'label_seen', 'reasons', 'n_masked', 'iters',
                  'converged', 'flags', 'sha256', 'osd_deg', 'osd_conf'}
_PAGE_OPTIONAL = {'osd_unreliable', 'rotated'}

NEAR_EMPTY_WORDS = 20
CONF_MIN = 30
# the darkened read: the page's own paper goes white, and everything darker than FAINT_BLACK_RATIO of it
# black, faint ink included. A fixed black point turned grey paper below it solid black (cold review
# 2026-11-07: 78% grey paper came out CLEAN with nothing read)
FAINT_BLACK_RATIO = 0.8
GREY_CELLS = 64            # the page scaled to 64 x 64 grey cells: enough to tell paper from ink, never text
PAPER_SHARE = 0.9          # the paper: the cell 90% of the way up; the middle one fell into a dark half-page
PAPER_FLOOR = 0.25         # a page whose middle cell is darker than this (a dark photo, a failed scan) cannot be darkened usefully
DARK_SHARE_MAX = 0.25      # a darkened copy with more of its cells dark than this went partly unread
# (invented pages, 2026-11-07: text, blur, noise and tinted paper 0.00 to 0.04, bold headings 0.06, a black
# header band over a fifth of the page 0.22; a grey band with a faint number on white 0.36)
KNOWN_MAX_OFF = 2   # digits a known number's window may read wrong besides confusables: 7 of 9 pinned
FUZZY_MAX_SUBS = 3  # confusables one checksum window may read through (A89): at least 8 of 11 read as digits
OSD_CONF_MIN = 1.5
TOOL_TIMEOUT_S = 120
FRESHNESS_SLOP_S = 2.0  # coarse-mtime-filesystem tolerance; still catches genuinely stale files

# ---- workload bounds — enforced before/while buffering, fail closed ----
# Generous for real scanned documents (a 300-dpi multi-page scan is tens of MB). Scope, honestly:
# these bound what THIS tooling buffers or copies — the input snapshot, state JSON, and page rasters
# at the consumption gate; a file that outgrows its fstat'ed size may transiently buffer up to
# bound + one 1 MiB chunk before rejecting. MAX_PAGES_PER_DOC binds manifest/approval validation,
# NOT pdftoppm's render volume — a crafted small PDF declaring a huge page count can still fill
# --render before any page bound runs (the inbox is operator-curated by SOP; revisit if that ever
# stops being true). Every rejection is category-only (never echoes a size/path that could
# correlate to a source).
MAX_INPUT_PDF_BYTES = 256 * 1024 * 1024        # one inbox PDF (input-snapshot bound)
MAX_STATE_JSON_BYTES = 8 * 1024 * 1024         # manifest.json / approval.json read bound
MAX_PAGES_PER_DOC = 500                        # page records per document manifest/approval
MAX_PAGE_BYTES = 64 * 1024 * 1024              # one rendered page raster
MAX_TOTAL_PAGE_BYTES = 2 * 1024 * 1024 * 1024  # all rasters of one document (buffered consumption)
DIGITS_CONFUSE = str.maketrans({'O': '0', 'o': '0', 'Q': '0', 'D': '0',
                                'I': '1', 'l': '1', '|': '1', '!': '1',
                                'B': '8', 'S': '5', 'Z': '2', 'G': '6', 'T': '7', 'A': '4'})

def _pl_id_prefix(dob):
    """DOB 'YYYY-MM-DD' -> the 6-digit prefix the scheme derives from it."""
    y, m, d = int(dob[0:4]), int(dob[5:7]), int(dob[8:10])
    off = {18: 80, 19: 0, 20: 20, 21: 40, 22: 60}.get(y // 100)
    if off is None:
        raise ValueError('DOB century outside the scheme')
    return f'{y % 100:02d}{m + off:02d}{d:02d}'

def _pl_id_checksum_ok(s):
    if len(s) != 11 or not s.isdigit():
        return False
    w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    return (10 - sum(int(s[i]) * w[i] for i in range(10)) % 10) % 10 == int(s[10])

def _confused(ch):
    """A character as a digit: itself, or the digit OCR misreads as it; None for anything else."""
    d = ch.translate(DIGITS_CONFUSE)
    return d if d in '0123456789' and len(d) == 1 else None

def _read_number(text, fuzzy):
    """A printed number's text as digits, spaces and separators, through at most FUZZY_MAX_SUBS OCR
    confusables when fuzzy; None when anything else is left."""
    out, subs = [], 0
    for ch in text:
        if ch in '0123456789 /-':
            out.append(ch)
        elif fuzzy and _confused(ch):
            out.append(_confused(ch)); subs += 1
        else:
            return None
    return ''.join(out) if subs <= FUZZY_MAX_SUBS else None

_US_SEPARATED = re.compile(r'[0-9]{3}[- ][0-9]{2}[- ][0-9]{4}')

def _us_ssn_issued(d):
    """Nine digits that could have been issued: never area 000 or 666, group 00 or serial 0000 (any 9NN)."""
    return len(d) == 9 and d.isdigit() and d[:3] not in ('000', '666') and d[3:5] != '00' and d[5:] != '0000'

def _us_ssn_match(text, fuzzy, starts, rules, labelled):
    """'shape' for the separated print form (its hyphens hold it where OCR split a group), 'bare' for
    nine digits that could have been issued, OCR's split of them included (but not 3-3-3, another
    country's grouping)."""
    t = _read_number(text, fuzzy)
    if t is None or 'prefix' not in rules:
        return None
    c = t.replace(' ', '')
    if _US_SEPARATED.fullmatch(t) or _US_SEPARATED.fullmatch(c):
        return 'shape'
    if _us_ssn_issued(c) and not re.fullmatch(r'[0-9]{3} [0-9]{3} [0-9]{3}', t):
        return 'bare'            # any 9NN too: the ITIN list has grown, and IRSN and ATIN share the form
    return None

def _cz_sk_prefixes(dob):
    """DOB -> every YYMMDD the number may open with: month +0, +50 (women), +20/+70 (supplementary
    batch) x day +0, +40 (EČP), +50 (generated insured numbers). No calendar gate: day above 31 is real."""
    y, m, d = int(dob[0:4]), int(dob[5:7]), int(dob[8:10])
    return {f'{y % 100:02d}{m + mo:02d}{d + do:02d}' for mo in (0, 50, 20, 70) for do in (0, 40, 50)}

def _cz_sk_divisible(s):
    """Ten digits divisible by 11, or nine leaving 10 and a last digit 0 (how such numbers were issued)."""
    return len(s) == 10 and s.isdigit() and (int(s) % 11 == 0 or int(s[:9]) % 11 == 10 and s[9] == '0')

_CZ_SK_MONTHS = set(range(1, 13)) | set(range(51, 63)) | set(range(21, 33)) | set(range(71, 83))

def _cz_sk_match(text, fuzzy, starts, rules, labelled):
    """'prefix' when the DOB's YYMMDD opens it; else a possible month and day: 'shape' with a slash,
    'bare' for nine digits; bare ten only when divisible by 11 (pre-1954 nine-digit numbers never are)."""
    t = _read_number(text, fuzzy)
    m = t is not None and re.fullmatch(r'([0-9]{6})(/| |)([0-9]{3,4})', t)
    if not m:
        return None
    head, sep, tail = m.groups()
    if 'prefix' in rules and head in starts:
        return 'prefix'
    month, day = int(head[2:4]), int(head[4:6])
    if len(tail) == 4 and sep != '/':
        return 'shape' if ('checksum' in rules and month in _CZ_SK_MONTHS
                           and _cz_sk_divisible(head + tail)) else None
    if 'prefix' not in rules or month not in _CZ_SK_MONTHS or not (1 <= day <= 31 or 41 <= day <= 81) \
            or (tail == '000' and sep != '/'):      # ČSSZ: a nine-digit ending 000 is never issued
        return None
    return 'shape' if sep == '/' else 'bare'

def _fr_nir_prefixes(dob):
    """DOB -> the year and month the number carries after its sex digit."""
    return {dob[2:4] + dob[5:7]}

def _fr_nir_key_ok(s):
    """15 characters: the key is 97 - (the first 13 mod 97), Corsica's letter read as 0 and 1,000,000
    (A) or 2,000,000 (B) taken off (INSEE)."""
    body = s[:13]
    n = int(body.replace('A', '0').replace('B', '0')) - {'A': 1000000, 'B': 2000000}.get(body[6], 0)
    return 97 - n % 97 == int(s[13:])

def _fr_nir_read(text, fuzzy):
    """The number's 13 or 15 characters with Corsica's letter kept, or None. Spaces anywhere (no
    official grouping); one slash or hyphen, only before the key."""
    s = text.replace(' ', '')
    m = re.fullmatch(r'([^/-]{13})[/-]([^/-]{2})|([^/-]{13}|[^/-]{15})', s)
    if not m:
        return None
    s = (m.group(1) + m.group(2)) if m.group(1) else m.group(3)
    corsica = s[6] in 'AB' and (_confused(s[5]) if fuzzy else s[5]) == '2'
    t = _read_number(s[:6] + '0' + s[7:] if corsica else s, fuzzy)
    return t[:6] + s[6] + t[7:] if t and corsica else t

def _fr_nir_match(text, fuzzy, starts, rules, labelled):
    """'prefix' when the DOB's year and month follow the sex digit; 'shape' for 15 with a valid key,
    or 13 (keyless) beside a French label. First digit 1-4, 7 or 8; no gate on month or place."""
    s = _fr_nir_read(text, fuzzy)
    if s is None or s[0] not in '123478':
        return None
    readings = {s}
    if s[5] == '2':                       # OCR reads Corsica's 2A as 24 and 2B as 28, and back: try each
        for pair in ('A4', 'B8'):
            if s[6] in pair:
                readings |= {s[:6] + c + s[7:] for c in pair}
    if 'prefix' in rules and s[1:5] in starts:
        return 'prefix'
    if len(s) == 15 and 'checksum' in rules and any(_fr_nir_key_ok(r) for r in readings):
        return 'shape'
    if len(s) == 13 and 'prefix' in rules and labelled:
        return 'shape'
    return None

# window 'sliding': digit windows over a line's stream (a strong checksum and a date in every number, so it
# needs the DOB); 'token': whole printed numbers only. dob_prefix: what the DOB says the number opens with (the
# sliding scheme's one prefix, a token scheme's set). labels: (label, strong) — a strong one holds a page where
# no number is near it; the operator's own --label-token is separate and stays local. needs_known: the
# number holds no date, so a run searches the person's own number from their identity file instead of its
# shape (ADR-0074), and refuses without one.
SCHEMES = {
    'pl-id': dict(window='sliding', lengths=(11,), dob_prefix=_pl_id_prefix, checksum_ok=_pl_id_checksum_ok,
                  labels=()),
    'us-ssn': dict(window='token', lengths=(9,), dob_prefix=None, match=_us_ssn_match, needs_known=True,
                   valid=_us_ssn_issued,
                   shown=lambda d: '%s-%s-%s' % (d[:3], d[3:5], d[5:]),
                   labels=(('SSN', True), ('Social Security', False), ('ITIN', False), ('TIN', False),
                           ('TTIN', False), ('ATIN', False))),
    'cz-sk-rc': dict(window='token', lengths=(9, 10), dob_prefix=_cz_sk_prefixes, match=_cz_sk_match,
                     labels=(('rodné číslo', True), ('RČ', False), ('číslo pojištěnce', False),
                             ('EČP', False), ('identifikačné číslo poistenca', False), ('IČP', False))),
    'fr-nir': dict(window='token', lengths=(13, 15), dob_prefix=_fr_nir_prefixes, match=_fr_nir_match,
                   labels=(('NIR', True), ('numéro de sécurité sociale', True), ('N° de sécurité sociale', True),
                           ('Nº de sécurité sociale', True), ('numéro INSEE', False),
                           ('matricule INS', False), ('Mat INS', False), ('INS', False), ('NIA', False),
                           ('ouvrant droit', False))),
}

# --- ImageMagick front-end: IM7 'magick' or legacy 'convert'/'identify' ---
def _im():
    if shutil.which('magick'):
        return dict(convert=['magick'], identify=['magick', 'identify'])
    if shutil.which('convert') and shutil.which('identify'):
        return dict(convert=['convert'], identify=['identify'])
    raise RuntimeError('ImageMagick not found (need `magick`, or `convert`+`identify`).')
IM = None  # resolved in main(); tests may inject

class ToolError(RuntimeError):
    """Sanitized external-tool failure: carries only a stage name and a short, non-sensitive
    reason category. NEVER carries stdout/stderr/argv (may contain OCR text, digits, or the
    label token) — that is the whole point of the safety contract above."""
    def __init__(self, stage, reason):
        self.stage = stage
        self.reason = reason
        super().__init__(f'{stage}: {reason}')

def run_checked(cmd, stage, outputs=(), min_size=1, allow_rc=(0,)):
    """Run an external command and validate it before trusting its effects. Checks: the
    executable actually ran, its return code is in allow_rc, and every path in `outputs`
    exists, is at least `min_size` bytes, and was written/touched no earlier than this call
    started (freshness — a stale pre-existing file at the expected path must never be mistaken
    for this call's output). Raises ToolError on any violation; never returns a path that was
    merely requested rather than verified."""
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)
    except FileNotFoundError:
        raise ToolError(stage, 'executable not found')
    except subprocess.TimeoutExpired:
        raise ToolError(stage, 'timed out')
    if r.returncode not in allow_rc:
        raise ToolError(stage, f'nonzero exit ({r.returncode})')
    for p in outputs:
        if not os.path.exists(p):
            raise ToolError(stage, 'expected output missing')
        try:
            st = os.stat(p)
        except OSError:
            raise ToolError(stage, 'expected output unreadable')
        if st.st_size < min_size:
            raise ToolError(stage, 'expected output empty')
        if st.st_mtime < t0 - FRESHNESS_SLOP_S:
            raise ToolError(stage, 'expected output stale (predates this command)')
    return r

def digits_only(s):
    return re.sub(r'\D', '', s)

def fuzzy_digits(s):
    return re.sub(r'\D', '', s.translate(DIGITS_CONFUSE))

DATE_RE = re.compile(r'^\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}$|^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}$')

def is_date_word(txt):
    """A date-formatted token is never the identifier — without this, a printed DOB would fire
    the prefix rule via line concatenation and eat the whole row (first-run lesson)."""
    return bool(DATE_RE.match(txt.strip().strip('.,;r')))

def union(boxes):
    x1 = min(b[0] for b in boxes); y1 = min(b[1] for b in boxes)
    x2 = max(b[0] + b[2] for b in boxes); y2 = max(b[1] + b[3] for b in boxes)
    return [x1, y1, x2 - x1, y2 - y1]

def median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n else 0

def parse_tsv(path):
    words = []
    if not path or not os.path.exists(path):
        return words
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            try:
                if int(row['level']) != 5:
                    continue
                txt = (row['text'] or '').strip()
                if not txt:
                    continue
                words.append(dict(text=txt, conf=float(row['conf']),
                                  left=int(row['left']), top=int(row['top']),
                                  width=int(row['width']), height=int(row['height']),
                                  line_key=(row['block_num'], row['par_num'], row['line_num'])))
            except (ValueError, KeyError, TypeError):
                continue
    return words

_DIGIT_RE = re.compile(r'\d')

def _digit_stream(lw, fuzzy):
    """A line's digit stream as (digit, owner word index, read through a confusable?) in reading
    order; date words are skipped (a printed DOB is never the identifier). No text leaves here."""
    out = []
    for wi, w in enumerate(lw):
        if is_date_word(w['text']):
            continue
        for ch in w['text']:
            d = ch.translate(DIGITS_CONFUSE) if fuzzy else ch
            if _DIGIT_RE.match(d):
                out.append((d, wi, not _DIGIT_RE.match(ch)))
    return out

def _group_lines(words):
    lines = {}
    for w in words:
        lines.setdefault(w['line_key'], []).append(w)
    for k in lines:
        lines[k].sort(key=lambda w: w['left'])
    return lines

def _extent(lw):
    return (min(w['left'] for w in lw), min(w['top'] for w in lw),
            max(w['left'] + w['width'] for w in lw), max(w['top'] + w['height'] for w in lw))

def _continues(a, b, lh):
    """Line extent b continues a: the next line on the same row, or the line just below in the same
    column — where an identifier split by OCR, or wrapped by the layout, carries on."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    same_row = (abs((ay1 + ay2) - (by1 + by2)) / 2 <= 0.8 * lh and bx1 >= ax1
                and bx1 - ax2 <= 18 * lh)
    below = ay1 < by1 and by1 - ay2 <= 1.5 * lh and bx1 <= ax2 + 2 * lh and bx2 >= ax1 - 2 * lh
    return same_row or below

def _rule_windows(lines, L, prefix, rules, checksum_ok, lh, match=None, reason_of='id-prefix'):
    """(owner words, reason) for every identifier-shaped window. Each line's own digit stream takes
    the prefix rule (strict and fuzzy) and the checksum rule (strict). A pair of neighbouring lines
    (A83) takes the prefix rule only, for windows that cross the join: the true identifier always
    carries the DOB prefix, while a checksum over every pair of lines would multiply its ~10% false
    hits. `match` replaces the prefix test (a person's known number, read whole), under `reason_of`."""
    hit = match or (lambda win: win.startswith(prefix))
    out = []
    streams = {(k, fz): _digit_stream(lw, fz) for k, lw in lines.items() for fz in (False, True)}
    for k, lw in lines.items():
        for fz in (False, True):
            st = streams[(k, fz)]
            s = ''.join(d for d, _, _ in st)
            for i in range(0, len(s) - (L - 1)):
                win = s[i:i + L]
                reason = None
                if 'prefix' in rules and hit(win):
                    reason = reason_of + ('-fuzzy' if fz else '')
                elif 'checksum' in rules and not fz and checksum_ok(win):
                    reason = 'id-checksum'
                if reason:
                    out.append(([lw[j] for j in sorted({st[x][1] for x in range(i, i + L)})], reason))
    if 'prefix' not in rules:
        return out
    ext = {k: _extent(lw) for k, lw in lines.items()}
    for ka in lines:
        for kb in lines:
            if ka == kb or not _continues(ext[ka], ext[kb], lh):
                continue
            for fz in (False, True):
                sa, sb = streams[(ka, fz)], streams[(kb, fz)]
                s = ''.join(d for d, _, _ in sa + sb)
                for i in range(max(0, len(sa) - L + 1), len(sa)):
                    if i + L > len(s):
                        break
                    if hit(s[i:i + L]):
                        owners = ([lines[ka][j] for j in sorted({sa[x][1] for x in range(i, len(sa))})]
                                  + [lines[kb][j] for j in sorted({sb[x][1] for x in range(0, i + L - len(sa))})])
                        out.append((owners, reason_of + ('-fuzzy' if fz else '')))
    return out

def _boxes_by_line(owners):
    """One mask box per OCR line among a hit's owner words (a split identifier gets one per part)."""
    per = {}
    for w in owners:
        per.setdefault(w['line_key'], []).append([w['left'], w['top'], w['width'], w['height']])
    return [union(bs) for bs in per.values()]

def _near_label(lab, w, lh):
    """Is word w where a label's number is printed: on its line to the right, or just below it?"""
    lcx, lcy = lab['left'] + lab['width'] / 2, lab['top'] + lab['height'] / 2
    wcx, wcy = w['left'] + w['width'] / 2, w['top'] + w['height'] / 2
    same_line_right = (abs(wcy - lcy) <= 0.8 * lh and w['left'] >= lab['left']
                       and (w['left'] - lab['left']) <= 18 * lh)
    below = ((lab['top'] + lab['height'] - 0.3 * lh) <= w['top']
             <= (lab['top'] + lab['height'] + 2.5 * lh) and abs(wcx - lcx) <= 14 * lh)
    return same_line_right or below

TOKEN_MAX_WORDS = 17   # a French number printed one digit per box, with its slash and key
TOKEN_GAP = 2          # line heights between two words of one printed number

_DASHES = str.maketrans(dict.fromkeys('–—\u2010\u2011\u2012\u2212', '-'))   # dashes, hyphens, minus
_US_DOTTED = re.compile(r'(.*?(?<![0-9]))([0-9]{3})[-._]([0-9]{2})[-._]([0-9]{4})')

def _clean(text):
    """A word as part of a number: the punctuation after it dropped, and whatever is glued on before it (a
    label, a sign, a quote) up to the last character that is not a digit, a confusable or a separator —
    when a digit follows ('Tel' is not a 1). Any dash reads as a hyphen, and so do dots or underscores
    between US groups. A | at an end stays: the reader tries it as a table rule and as OCR's 1."""
    t = text.strip().rstrip('.,;:)]"\'”’*').translate(_DASHES)
    m = _US_DOTTED.fullmatch(t)
    t = m.group(1) + '-'.join(m.group(2, 3, 4)) if m else t
    cut = max((i for i, c in enumerate(t) if not (c in '0123456789/-' or _confused(c))), default=-1)
    return t if cut < 0 else t[cut + 1:] if _DIGIT_RE.search(t[cut + 1:]) else ''

def _number_part(text):
    """The word's text when it can be part of a printed number (digits, OCR confusables, separators),
    else None: it ends the number."""
    return _clean(text) or None

def _parts(lw, lh, part=_number_part):
    """Each word of a line as a number part (`part` reads one), or None. A separator binds only towards a
    number part on its far side: one with none there is dropped (the dash after a name, the slash after a
    number)."""
    parts = [part(w['text']) for w in lw]
    for i, p in enumerate(parts):
        if p and p[0] in '/-' and not (i and parts[i - 1] and _joined(lw, i, lh)):
            p = p.lstrip('/-')
        if p and p[-1] in '/-' and not (i + 1 < len(lw) and parts[i + 1] and _joined(lw, i + 1, lh)):
            p = p.rstrip('/-')
        parts[i] = p or None
    return parts

def _norm(texts):
    return re.sub(r'\s*([/-])\s*', r'\1', ' '.join(texts))

def _joined(lw, i, lh):
    """Words i-1 and i of a line sit close enough to be one printed number."""
    return lw[i]['left'] - (lw[i - 1]['left'] + lw[i - 1]['width']) <= TOKEN_GAP * lh

def _token_spans(lw, parts, lh):
    """(i, j) of every run of neighbouring number parts that could be one whole printed number. A
    separator binds its neighbours, so a run never starts or ends at one, nor beside one."""
    out = []
    for i in range(len(lw)):
        if parts[i] is None or parts[i][0] in '/-' or (
                i and parts[i - 1] and parts[i - 1][-1] in '/-' and _joined(lw, i, lh)):
            continue
        for j in range(i, min(len(lw), i + TOKEN_MAX_WORDS)):
            if parts[j] is None or (j > i and not _joined(lw, j, lh)):
                break
            if parts[j][-1] in '/-' or (j + 1 < len(lw) and parts[j + 1] and parts[j + 1][0] in '/-'
                                        and _joined(lw, j + 1, lh)):
                continue
            out.append((i, j))
    return out

def _runs(lw, parts, lh):
    """Each line's maximal runs of neighbouring number parts (a spaced-out number near a label)."""
    out, cur = [], []
    for i, p in enumerate(parts):
        if p is not None and cur and _joined(lw, i, lh):
            cur.append(lw[i])
        else:
            if cur:
                out.append(cur)
            cur = [lw[i]] if p is not None else []
    return out + ([cur] if cur else [])

_MASK_CH = r'[Xx×✕*∗⁎#•·●∙◦+]'
# Each mask group at one to four characters: OCR misreads its width (XXX-XxX-1234 was seen on a page).
_LAST_FOUR = re.compile(_MASK_CH + '{1,4}[- ]?' + _MASK_CH + r'{1,4}[- ]?(\S{4})')

def _masked_part(text):
    """A word as part of a number masked to its last four (mask characters kept), else None."""
    t = text.rpartition(':')[2].strip('([.,;)]').translate(_DASHES)
    return t if t and all(c == '-' or re.fullmatch(_MASK_CH, c) or _confused(c) for c in t) else None

def _last_four(text):
    """A US number masked to its last four (XXX-XX-1234; Xs and asterisks are the official masks,
    the rest OCR tolerance): the four read as digits, at most one through a confusable. A | at an end is
    read as OCR's 1, then as a table rule."""
    m = _LAST_FOUR.fullmatch(text) or _LAST_FOUR.fullmatch(text.strip('|'))
    if not m:
        return False
    four = m.group(1)
    return all(_confused(c) for c in four) and sum(c in '0123456789' for c in four) >= 3

def _token_hits(lines, lh, keys, rules, starts, fr_labels, known=()):
    """(owner words, reason) for every whole printed number of a token scheme, and the US forms masked
    to the last four. Strict reading first; through OCR confusables only when it fails. A line and the
    line that continues it (A83) are read as one too, for a number that crosses the join."""
    out = []
    ext = {k: _extent(lw) for k, lw in lines.items()}
    pairs = [(lines[a] + lines[b], len(lines[a])) for a in lines for b in lines
             if a != b and _continues(ext[a], ext[b], lh)]
    for lw, cut in [(lw, 0) for lw in lines.values()] + pairs:
        if 'us-ssn' in keys and 'prefix' in rules:
            masked = _parts(lw, lh, _masked_part)
            out += [(lw[i:j + 1], 'id-last-four') for i, j in _token_spans(lw, masked, lh)
                    if (not cut or i < cut <= j) and _last_four(_norm(masked[i:j + 1]))]
        parts = _parts(lw, lh)
        for i, j in _token_spans(lw, parts, lh):
            if cut and not i < cut <= j:
                continue
            labelled = any(_near_label(lab, w, lh) for lab in fr_labels for w in lw[i:j + 1])
            found = len(out)
            whole = _norm(parts[i:j + 1])
            for text in dict.fromkeys((whole, whole.strip('|'))):   # a | at an end: OCR's 1, then a table rule
                n = len(re.sub(r'[ /-]', '', text))
                for k in keys:
                    sch = SCHEMES[k]
                    if k in known or n not in sch['lengths']:     # a known number replaces the shape guess
                        continue
                    for fz in (False, True):
                        kind = sch['match'](text, fz, starts[k], rules, labelled)
                        if kind:
                            out.append((lw[i:j + 1], 'id-shape-bare' if kind == 'bare' else
                                        'id-' + kind + ('-fuzzy' if fz else '')))
                            break
                if len(out) > found:
                    break
    return out

def _fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def _label_words(s):
    return re.findall(r'[A-Za-z0-9]+', _fold(s))

def _same_label_word(seen, want):
    # a word written in capitals matches only in capitals: 'INS' never hits 'insulin', 'TIN' not 'Tin'
    return seen == want if want.isupper() else seen.lower() == want.lower()

def _shipped_labels(lines, keys):
    """(label words, scheme, strong) for each shipped label of the selected schemes printed on a line:
    accent-folded, whole words, across OCR words of one line."""
    specs = [(k, _label_words(lab), strong) for k in keys for lab, strong in SCHEMES[k]['labels']]
    found = []
    for lw in lines.values():
        subs = [(wi, t) for wi, w in enumerate(lw) for t in _label_words(w['text'])]
        for k, want, strong in specs:
            for i in range(len(subs) - len(want) + 1):
                if all(_same_label_word(subs[i + x][1], want[x]) for x in range(len(want))):
                    found.append(([lw[j] for j in sorted({subs[i + x][0] for x in range(len(want))})], k, strong))
    return found

def _box_word(owners):
    x, y, w, h = union([[o['left'], o['top'], o['width'], o['height']] for o in owners])
    return dict(left=x, top=y, width=w, height=h)

def _label_number(text):
    """Enough digits to be the number beside a label: four or more, at least half of them real digits
    (a capitalised word read through confusables, e.g. STATISTICS, is not a number)."""
    fz = fuzzy_digits(text)
    return len(fz) >= 4 and 2 * len(digits_only(text)) >= len(fz)

_SCAN_CODE = re.compile(r'(?<![a-z0-9])ins\s*a\s*scanner(?![a-z0-9])')

def _token_detect(words, good, lines, lh, keys, rules, dob, label_boxes, signals, known=()):
    """The token schemes' rules (see the module docstring): (hits, label_seen, label_no_candidate)."""
    hits = []
    starts = {k: SCHEMES[k]['dob_prefix'](dob) if dob and SCHEMES[k]['dob_prefix'] else set() for k in keys}
    all_lines = _group_lines(words)
    labels = _shipped_labels(all_lines, keys)          # a faint label still says what the number beside it is
    fr_labels = [_box_word(o) for o, k, _ in labels if k == 'fr-nir']
    for owners, reason in _token_hits(lines, lh, keys, rules, starts, fr_labels, known):
        hits.extend({'box': b, 'reason': reason} for b in _boxes_by_line(owners))
    if 'lowconf' in rules:
        hits += _low_confidence(words, min(n for k in keys for n in SCHEMES[k]['lengths']),
                                lambda: _token_hits(all_lines, lh, keys, rules, starts, fr_labels, known))

    label_seen = label_no_candidate = False
    if 'label' in rules and labels:
        # a printed date stays visible beside a label too (the French INS block prints the DOB)
        units = [[w] for w in good if not is_date_word(w['text']) and _label_number(w['text'])]
        for lw in lines.values():
            parts = [None if is_date_word(w['text']) else _number_part(w['text']) for w in lw]
            units += [r for r in _runs(lw, parts, lh) if len(r) > 1 and _label_number(' '.join(w['text'] for w in r))]
        for owners, k, strong in labels:
            label_seen = True
            lab = _box_word(owners)
            found_near = False
            for unit in units:
                if not any(w in owners for w in unit) and any(_near_label(lab, w, lh) for w in unit):
                    hits.extend({'box': b, 'reason': 'id-label-proximity'} for b in _boxes_by_line(unit))
                    found_near = True
            if strong:
                label_no_candidate = label_no_candidate or not found_near
                if label_boxes is not None:
                    label_boxes.append(([lab['left'], lab['top'], lab['width'], lab['height']], found_near))

    # the French datamatrix holding the number: text masking cannot reach it, so the page holds. The page's
    # text is searched as one, so a caption wrapped over two lines still counts.
    if 'fr-nir' in keys and signals is not None and _SCAN_CODE.search(
            _fold(' '.join(w['text'] for lw in all_lines.values() for w in lw)).lower()):
        signals.add('scan-code')
    return hits, label_seen, label_no_candidate

def _low_confidence(words, L, owner_hits):
    """Below the confidence floor (A80): a word OCR read too faintly to trust is not dropped silently when
    it looks like the identifier — a hit of `owner_hits()` (run over every word) it takes part in, or a word
    of identifier length L read mostly as digits. Masked, and the caller HOLDs the page."""
    low = [w for w in words if w['conf'] < CONF_MIN]
    if not low:
        return []
    low_ids = {id(w) for w in low}
    hits = [{'box': b, 'reason': 'id-low-confidence'} for owners, _ in owner_hits()
            if any(id(w) in low_ids for w in owners) for b in _boxes_by_line(owners)]
    for w in low:
        st = _digit_stream([w], True)
        if len(st) >= L - 2 and sum(1 for _, _, sub in st if not sub) >= (L + 1) // 2:
            hits.append({'box': [w['left'], w['top'], w['width'], w['height']], 'reason': 'id-low-confidence'})
    return hits

def known_match(digits):
    """The test a window of a person's known number passes: every digit but at most KNOWN_MAX_OFF read
    as itself (a confusable already read as its digit in the fuzzy stream)."""
    return lambda win: len(win) == len(digits) and sum(a != b for a, b in zip(win, digits)) <= KNOWN_MAX_OFF

def _known_hits(words, lines, lh, digits, rules):
    """A person's own number, recorded in their identity file (ADR-0074): the sliding window with the
    whole number as its prefix, on each line and across a line that continues it, strict and through
    confusables, and a faint word taking part in one. It runs whatever --rules narrows: a rerun may drop
    noisy rules, never the person's own number."""
    L, match = len(digits), known_match(digits)
    rules = tuple(rules) + ('prefix',)
    never = lambda s: False                                   # noqa: E731  no checksum for a known number
    hits = [{'box': b, 'reason': reason} for owners, reason in
            _rule_windows(lines, L, None, rules, never, lh, match, 'id-known') for b in _boxes_by_line(owners)]
    if 'lowconf' in rules:
        hits += _low_confidence(words, L, lambda: _rule_windows(_group_lines(words), L, None, ('prefix',), never,
                                                                 lh, match, 'id-known'))
    return hits

def _sliding_hits(words, good, lines, lh, sch, prefix, rules):
    """The sliding-window rules of a scheme like 'pl-id' (see the module docstring)."""
    L = sch['lengths'][0]
    hits = []

    # prefix / checksum: each line's concatenated digit stream, and neighbouring lines joined (A83)
    for owners, reason in _rule_windows(lines, L, prefix, rules, sch['checksum_ok'], lh):
        hits.extend({'box': b, 'reason': reason} for b in _boxes_by_line(owners))

    # checksum through OCR confusables (A89), within one identifier-length word read mostly as digits
    # (1..FUZZY_MAX_SUBS confusables per window). One word, not the line: letters of a neighbouring
    # word would otherwise turn most lines that hold a number into a ~10% false hit.
    if 'checksum' in rules:
        for w in good:
            st = _digit_stream([w], True)
            for i in range(0, len(st) - (L - 1)):
                win = st[i:i + L]
                if (1 <= sum(1 for _, _, sub in win if sub) <= FUZZY_MAX_SUBS
                        and sch['checksum_ok'](''.join(d for d, _, _ in win))):
                    hits.append({'box': [w['left'], w['top'], w['width'], w['height']],
                                 'reason': 'id-checksum-fuzzy'})
                    break

    # below the confidence floor: a prefix window a faint word takes part in (its line or a neighbour)
    if 'lowconf' in rules:
        hits += _low_confidence(words, L, lambda: _rule_windows(_group_lines(words), L, prefix, ('prefix',),
                                                                 sch['checksum_ok'], lh))
    return hits

def detect(words, W, H, prefix, rules=DEFAULT_RULES, label_token=None, scheme='pl-id', label_boxes=None,
           dob=None, signals=None, known=None):
    """Return (hits, label_seen, label_no_candidate); hits=[{box,reason}]. No text leaves here.
    Reasons: id-prefix / id-prefix-fuzzy / id-checksum / id-checksum-fuzzy / id-label-proximity /
    id-low-confidence / id-shape / id-shape-fuzzy / id-shape-bare / id-last-four (no digits). `scheme`
    is one key or several joined by commas; `prefix` is the sliding scheme's, `dob` (optional) gives the
    token schemes theirs. A `label_boxes` list gets each printed label that can hold the page as (box,
    number found near it); a `signals` set gets 'scan-code' when a French page prints its code. `known`
    maps a scheme to the person's own number (digits): searched whole, it replaces that scheme's shape
    rules (ADR-0074)."""
    keys = [k for k in (scheme or '').split(',') if k]   # none: covered by hand (ADR-0076)
    known = {k: v for k, v in (known or {}).items() if k in keys}
    good = [w for w in words if w['conf'] >= CONF_MIN]
    lh = median([w['height'] for w in good]) or max(1, H // 80)
    hits = []
    lines = _group_lines(good)

    for sch in [SCHEMES[k] for k in keys if SCHEMES[k]['window'] == 'sliding']:
        hits.extend(_sliding_hits(words, good, lines, lh, sch, prefix, rules))
    for digits in dict.fromkeys(known.values()):
        hits.extend(_known_hits(words, lines, lh, digits, rules))

    # label proximity (also catches a spaced-out label)
    label_seen = False; label_no_candidate = False
    if 'label' in rules and label_token:
        tok = re.sub(r'[^a-z0-9]', '', label_token.lower())
        labels = [w for w in good if tok in re.sub(r'[^a-z0-9]', '', w['text'].lower())]
        for k, lw in lines.items():
            joined = re.sub(r'[^a-z0-9]', '', ''.join(w['text'].lower() for w in lw))
            if tok in joined and not any(w in labels for w in lw):
                labels.append(lw[0])
        for lab in labels:
            label_seen = True
            found_near = False
            for w in good:
                if w is lab:
                    continue
                if len(fuzzy_digits(w['text'])) < 4:
                    continue
                if _near_label(lab, w, lh):
                    hits.append({'box': [w['left'], w['top'], w['width'], w['height']],
                                 'reason': 'id-label-proximity'})
                    found_near = True
            if not found_near:
                label_no_candidate = True
            if label_boxes is not None:
                label_boxes.append(([lab['left'], lab['top'], lab['width'], lab['height']], found_near))

    token_keys = [k for k in keys if SCHEMES[k]['window'] == 'token']
    if token_keys:
        th, seen, no_cand = _token_detect(words, good, lines, lh, token_keys, rules, dob, label_boxes, signals,
                                          tuple(known))
        hits.extend(th)
        label_seen = label_seen or seen
        label_no_candidate = label_no_candidate or no_cand
    return hits, label_seen, label_no_candidate

# ---- one page read for the identity tool (ADR-0074): the number beside its label, and the self-check ----

def page_words(pdf, page, lang, wdir, dpi=300):
    """(words, W, H, png) of one PDF page, rendered, turned upright and read in `wdir` (the caller's
    private folder, deleted after). Prints nothing; a failure raises ToolError."""
    base = os.path.join(wdir, 'page')
    run_checked(['pdftoppm', '-r', str(dpi), '-f', str(page), '-l', str(page), '-singlefile', '-png', pdf, base],
                stage='render', outputs=[base + '.png'])
    png = base + '.png'
    deg, conf, unreliable = osd(png)
    if deg in (90, 180, 270) and conf >= OSD_CONF_MIN and not unreliable:
        png = rotate_to(png, base + '_rot.png', deg)
    W, H = dims(png)
    return parse_tsv(ocr_tsv(png, base + '.tsv', lang)), W, H, png

def labelled_numbers(words, key):
    """{digits: box} for each number printed beside one of the scheme's shipped labels, read whole (strict,
    else through confusables) and of the scheme's length; the box covers the label and the number. No
    text leaves here but to the local caller."""
    good = [w for w in words if w['conf'] >= CONF_MIN]
    lh = median([w['height'] for w in good]) or 10
    lines = _group_lines(good)
    out = {}
    for owners, _, _ in _shipped_labels(lines, [key]):
        lab = _box_word(owners)
        for lw in lines.values():
            parts = _parts(lw, lh)
            for i, j in _token_spans(lw, parts, lh):
                unit = lw[i:j + 1]                 # a label word may hold the number too ('SSN:987-…')
                if not any(_near_label(lab, w, lh) for w in unit):
                    continue
                for fz in (False, True):
                    t = _read_number(_norm(parts[i:j + 1]), fz)
                    digits = re.sub(r'[ /-]', '', t or '')
                    if len(digits) in SCHEMES[key]['lengths']:
                        boxes = [[w['left'], w['top'], w['width'], w['height']] for w in owners + unit]
                        out.setdefault(digits, union(boxes))
                        break
    return out

def strong_hits(hits):
    """Hits that drive the verify loop: every rule but label proximity, which masks but is weak."""
    return [h for h in hits if h['reason'] != 'id-label-proximity']

def pad_clamp(box, W, H, pad):
    x, y, w, h = box
    return [max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)]

def dims(png):
    """Validated (w, h) — raises ToolError rather than returning (0, 0) on an unreadable image,
    so a caller can never mistake 'identify failed' for 'a zero-sized image' and proceed."""
    r = run_checked(IM['identify'] + ['-format', '%w %h', png], stage='identify')
    try:
        w, h = r.stdout.split()[:2]
        w, h = int(w), int(h)
    except Exception:
        raise ToolError('identify', 'unparseable dimensions')
    if w <= 0 or h <= 0:
        raise ToolError('identify', 'non-positive dimensions')
    return w, h

def ocr_tsv(png, out_tsv, lang):
    """Run tesseract TSV OCR through a temp basename, validate, then os.replace into place."""
    base = out_tsv[:-4] if out_tsv.endswith('.tsv') else out_tsv
    tmp_base = base + '.part'
    tmp_tsv = tmp_base + '.tsv'
    run_checked(['tesseract', png, tmp_base, '-l', lang, '--psm', '3', 'tsv'],
                stage='ocr', outputs=[tmp_tsv])
    os.replace(tmp_tsv, out_tsv)
    os.chmod(out_tsv, 0o600)
    return out_tsv

def grey_cells(png, wdir, stem):
    """The image as GREY_CELLS x GREY_CELLS grey levels (0-255, sorted), each the mean of its patch.
    The scaled file is read once and deleted."""
    tmp = os.path.join(wdir, stem + '_cells.part.pgm')     # the extension picks the format
    try:
        run_checked(IM['convert'] + [png, '-colorspace', 'Gray', '-scale', f'{GREY_CELLS}x{GREY_CELLS}!',
                                     '-depth', '8', tmp], stage='paper', outputs=[tmp])
        with open(tmp, 'rb') as fh:
            data = fh.read(1 << 20)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    m = re.match(rb'P5\s+(?:#[^\n]*\s+)*(\d+)\s+(\d+)\s+255\s', data)
    n = int(m.group(1)) * int(m.group(2)) if m else 0
    px = data[m.end():m.end() + n] if m else b''
    if not n or len(px) != n:
        raise ToolError('paper', 'unparseable grey cells')
    return sorted(px)

def overlaps(p, q):
    return p[0] < q[0] + q[2] and q[0] < p[0] + p[2] and p[1] < q[1] + q[3] and q[1] < p[1] + p[3]

def covered(box, known, tol):
    """Is the box, less up to `tol` on each side, wholly inside the union of the known boxes? The
    tolerance never shrinks a box to nothing: a small box is judged by its middle."""
    tx, ty = min(tol, (box[2] - 1) / 2), min(tol, (box[3] - 1) / 2)
    x0, y0, x1, y1 = box[0] + tx, box[1] + ty, box[0] + box[2] - tx, box[1] + box[3] - ty
    ks = [k for k in known if k[0] < x1 and x0 < k[0] + k[2] and k[1] < y1 and y0 < k[1] + k[3]]
    xs = sorted({x0, x1} | {min(max(v, x0), x1) for k in ks for v in (k[0], k[0] + k[2])})
    ys = sorted({y0, y1} | {min(max(v, y0), y1) for k in ks for v in (k[1], k[1] + k[3])})
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            if not any(k[0] <= cx <= k[0] + k[2] and k[1] <= cy <= k[1] + k[3] for k in ks):
                return False
    return True

def faint_hits(png, wdir, stem, a, W, H, known, label_token=None, signals=None):
    """(hits, labels, unreadable) that only a darkened copy of the page shows: OCR reads no word at all
    in faint ink, so the confidence floor never sees it. The page's own paper sets the black point. A
    hit the known boxes already cover is masked; one reaching beyond them is kept whole. `labels` are
    the darkened read's printed labels as (box, number found near it). `unreadable`: the copy came
    out dark, so nothing faint could be checked. Off with the lowconf rule. A failure raises and fails
    the page, never read as 'nothing faint'. The darkened copy is deleted once read."""
    if 'lowconf' not in a.rules:
        return [], [], False
    cells = grey_cells(png, wdir, stem)
    paper = cells[min(len(cells) - 1, int(PAPER_SHARE * len(cells)))] / 255
    if cells[len(cells) // 2] / 255 < PAPER_FLOOR:      # mostly dark: judged apart from the brighter estimate
        return [], [], True
    dark = os.path.join(wdir, stem + '_dark.png')
    tmp = dark + '.part'
    level = f'{100 * FAINT_BLACK_RATIO * paper:.1f}%,{100 * paper:.1f}%'
    try:
        run_checked(IM['convert'] + [png, '-level', level, tmp], stage='darken', outputs=[tmp])
        os.replace(tmp, dark)
        os.chmod(dark, 0o600)
        dcells = grey_cells(dark, wdir, stem + '_dark')
        if sum(1 for v in dcells if v < 128) > DARK_SHARE_MAX * len(dcells):
            return [], [], True
        labels = []
        hits, _, _ = detect(parse_tsv(ocr_tsv(dark, os.path.join(wdir, stem + '_dark.tsv'), a.lang)),
                            W, H, a.prefix, rules=a.rules, label_token=label_token, scheme=a.scheme,
                            label_boxes=labels, dob=a.dob, signals=signals, known=getattr(a, 'known', None))
    finally:
        for p in (tmp, dark):
            try:
                os.unlink(p)
            except OSError:
                pass
    boxes = [k['box'] for k in known]
    return ([{'box': h['box'], 'reason': 'id-low-confidence'} for h in hits
             if not covered(h['box'], boxes, max(6, h['box'][3] // 4))], labels, False)

def osd(png):
    """(rotate_deg, confidence, unreliable) from tesseract OSD. Orientation is HONESTLY UNCERTAIN
    unless every part parses cleanly (HO-09 item 4): a nonzero return, a missing/unparseable Rotate
    line, a rotation outside {0,90,180,270}, or a missing/unparseable confidence -> unreliable=True.
    A parsed non-zero turn below OSD_CONF_MIN is unreliable too (A82): the page may be sideways.
    Unreliable never rotates (apply-no-rotation is safe) but is recorded and raised to an
    OSD_UNRELIABLE page HOLD by the caller — 'no parse' is NEVER silently treated as orientation 0
    with confidence, and orientation uncertainty is not swallowed as reliable."""
    try:
        r = run_checked(['tesseract', png, 'stdout', '--psm', '0'], stage='osd', allow_rc=(0, 1, 2))
    except ToolError:
        return 0, 0.0, True
    if r.returncode != 0:                       # a nonzero OSD return is unreliable, output or not
        return 0, 0.0, True
    deg = conf = None
    for line in (r.stdout + '\n' + r.stderr).splitlines():
        if line.startswith('Rotate:'):
            try: deg = int(line.split(':')[1])
            except (ValueError, IndexError): deg = None
        elif line.startswith('Orientation confidence:'):
            try: conf = float(line.split(':')[1])
            except (ValueError, IndexError): conf = None
    if deg is None or conf is None or deg not in (0, 90, 180, 270):
        return 0, 0.0, True                     # missing/unparseable/invalid -> fail closed, not silent 0
    if deg != 0 and conf < OSD_CONF_MIN:
        return deg, conf, True                  # a turn OSD is unsure of: neither applied nor trusted (A82)
    return deg, conf, False

def rotate_to(src, dst, deg):
    tmp = dst + '.part'
    run_checked(IM['convert'] + [src, '-rotate', str(deg), tmp], stage='rotate', outputs=[tmp])
    dims(tmp)  # readability/dims check before this becomes trusted
    os.replace(tmp, dst)
    os.chmod(dst, 0o600)
    return dst

def burn(src_png, boxes, out_png):
    tmp = out_png + '.part'
    if boxes:
        prim = ' '.join(f'rectangle {b[0]},{b[1]} {b[2]},{b[3]}' for b in boxes)
        run_checked(IM['convert'] + [src_png, '-fill', 'black', '-draw', prim, tmp],
                    stage='mask-burn', outputs=[tmp])
    else:
        run_checked(IM['convert'] + [src_png, tmp], stage='mask-burn', outputs=[tmp])
    dims(tmp)  # readability/dims check before this becomes the page's redacted raster
    os.replace(tmp, out_png)
    os.chmod(out_png, 0o600)
    return out_png

def _discard_page_raster(out_png):
    """Remove a failed page's raster and burn temp from the staged set before it is promoted. A page
    can fail after its first burn (verify re-OCR, a re-mask, hashing); that burn's image is unverified
    and must not reach --redacted/<doc>/ (PROCESS_ERROR contract). A removal that fails raises, so the
    document-level firewall reports the document and promotes nothing for it."""
    for p in (out_png, out_png + '.part'):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass

# ---- hashing / atomic-write / promotion primitives (handover 04, points 1-3, 7, 11) ----
def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()

# open flags for descriptor-based reads: never follow a symlink at the final component,
# and never block on a FIFO smuggled in at a regular file's path — open, then let fstat decide.
_NOFOLLOW_RD = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)

def _read_fd_bounded(fd, bound):
    """Read a descriptor to EOF, refusing (ValueError) past `bound` bytes — the bound is enforced
    while reading, not inferred from a pre-read stat the file could outgrow."""
    chunks, total = [], 0
    while True:
        chunk = os.read(fd, 1 << 20)
        if not chunk:
            return b''.join(chunks)
        total += len(chunk)
        if total > bound:
            raise ValueError('exceeds the workload bound')
        chunks.append(chunk)

def _read_regular_bounded(path, bound):
    """Open `path` no-follow/no-block, require a REGULAR file by fstat (post-open — this is the
    race-closing check, not the caller's advisory islink/isfile pre-filter), and return its bytes,
    bounded. OSError = unreadable/vanished/symlink; ValueError = non-regular or over-bound.
    The returned buffer IS the read bytes — any hash a caller computes over it binds exactly what
    was consumed, with no path reopen."""
    fd = os.open(path, _NOFOLLOW_RD)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError('non-regular file')
        if st.st_size > bound:
            raise ValueError('exceeds the workload bound')
        return _read_fd_bounded(fd, bound)
    finally:
        os.close(fd)

def _read_state_json_bytes(path):
    """Bounded read of a trusted-state JSON file (manifest.json / approval.json)."""
    return _read_regular_bounded(path, MAX_STATE_JSON_BYTES)

def _read_page_bytes(path):
    """Bounded read of one page raster at the consumption gate."""
    return _read_regular_bounded(path, MAX_PAGE_BYTES)

def _snapshot_input(src_path, snap_dir):
    """Copy one inbox PDF into the run-owned 0700 snapshot area while hashing the COPIED bytes.
    The caller's lstat pre-filter is advisory only: the open here is
    no-follow/no-block and the fstat on the OPEN descriptor is what actually excludes a
    symlink/FIFO/device raced in after that pre-filter. Every later pipeline step (render,
    pdfinfo) consumes the snapshot — the mutable inbox path is never reopened, so the manifest's
    input hash, the opaque doc id, and the rendered bytes all bind one immutable capture of the
    input, not whatever sits at the inbox path later. Returns (snapshot_path, sha256).
    OSError = unreadable/vanished/symlink; ValueError = non-regular or over-bound. The snapshot
    filename is opaque (never derived from the source name — HO-09 item 3)."""
    fd = os.open(src_path, _NOFOLLOW_RD)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError('non-regular input')
        if st.st_size > MAX_INPUT_PDF_BYTES:
            raise ValueError('input exceeds the workload bound')
        snap_path = os.path.join(snap_dir, 'in-%s.pdf' % secrets.token_hex(8))
        out_fd = os.open(snap_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            h = hashlib.sha256()
            total = 0
            while True:
                chunk = os.read(fd, 1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_INPUT_PDF_BYTES:
                    raise ValueError('input exceeds the workload bound')
                h.update(chunk)
                view = memoryview(chunk)
                while view:
                    view = view[os.write(out_fd, view):]
        except Exception:
            os.close(out_fd)
            try:
                os.unlink(snap_path)
            except OSError:
                pass
            raise
        os.close(out_fd)
        return snap_path, h.hexdigest()
    finally:
        os.close(fd)

def _json_load_bytes_strict(data):
    """Decode one trusted-state JSON object while rejecting duplicate keys.

    The default JSON decoder silently keeps the last duplicate key, which makes a displayed or
    reviewed manifest ambiguous even when the post-parse schema is strict.
    """
    def no_duplicates(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('duplicate JSON object key')
            out[key] = value
        return out
    return json.loads(data.decode('utf-8'), object_pairs_hook=no_duplicates)

def _utcnow():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def _atomic_write_json(path, obj):
    """Write JSON through a temp file + os.replace, so a crash mid-write can never leave a
    truncated/partial manifest or run-log under the expected final name."""
    d = os.path.dirname(os.path.abspath(path)) or '.'
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.tmp-', suffix='.json', dir=d)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try: os.remove(tmp)
        except OSError: pass
        raise

def _promote_dir(tmp_dir, final_dir):
    """Atomically make tmp_dir the live contents of final_dir. If final_dir already exists, it
    is renamed aside to a `.superseded/` sibling FIRST (never deleted — a rerun's stale prior
    output stays on disk as forensic history, just unreachable from the live path), then tmp_dir
    is renamed into place. Returns the superseded path, or None if there was nothing to supersede.

    Rollback-safe (HO-09 item 7): if the prior live set was moved aside and the staging rename then
    fails, the prior live set is RESTORED to final_dir before the error propagates — the last
    known-good set is never left stranded in `.superseded/` with an empty live path. Refuses an
    unsafe same-path/nested/symlink alias between tmp_dir and final_dir before any mutation."""
    final_abs = os.path.abspath(final_dir)
    tmp_abs = os.path.abspath(tmp_dir)
    final_parent = os.path.dirname(final_abs)
    # never let staging and destination alias, nest, or route through a symlinked destination —
    # that could make the rename land inside the very set it supersedes (raised, not returned:
    # the caller's exception firewall maps it to a documented failure, nothing is published).
    if final_abs == tmp_abs or os.path.islink(final_dir) or os.path.islink(tmp_dir):
        raise RuntimeError('promotion path alias/symlink refused')
    common = os.path.commonpath([final_abs, tmp_abs])
    if common in (final_abs, tmp_abs):
        raise RuntimeError('promotion path nesting refused')
    os.makedirs(final_parent, exist_ok=True)
    os.chmod(final_parent, 0o700)
    superseded = None
    if os.path.exists(final_dir):
        superseded_root = os.path.join(final_parent, '.superseded')
        os.makedirs(superseded_root, exist_ok=True)
        os.chmod(superseded_root, 0o700)
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        superseded = os.path.join(superseded_root,
                                  f'{os.path.basename(final_dir)}__{stamp}-{os.getpid()}-{secrets.token_hex(3)}')
        os.rename(final_dir, superseded)
    try:
        os.rename(tmp_dir, final_dir)
    except OSError:
        if superseded is not None and not os.path.exists(final_dir):
            os.rename(superseded, final_dir)    # restore the last known-good live set
        raise
    return superseded

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)

def _validate_dir_artifacts(directory, page_numbers, extra_allowed):
    """Reject symlinked directory, symlinked/non-regular page files, and any on-disk page-file set
    that is not EXACTLY the manifest/attestation page set (missing, extra, or stray files).
    `extra_allowed` is the set of non-page filenames permitted alongside (e.g. {'manifest.json'}).
    Category-only messages; never echoes a path. Shared by the manifest and approval validators."""
    e = []
    if os.path.islink(directory):
        return ['document directory is a symlink']
    try:
        entries = os.listdir(directory)
    except OSError:
        return ['document directory unreadable']
    expected = {f'page-{n:02d}.png' for n in page_numbers}
    allowed = set(extra_allowed) | expected
    present_pages = {x for x in entries if _PAGE_FILE_RE.match(x)}
    if present_pages != expected:
        e.append('page files on disk do not exactly match the recorded page set')
    if set(entries) - allowed:
        e.append('unexpected file(s) present in the document directory')
    for name in sorted(present_pages | (set(entries) & expected)):
        fp = os.path.join(directory, name)
        if os.path.islink(fp):
            e.append('a page artifact is a symlink')
        elif not os.path.isfile(fp):
            e.append('a page artifact is not a regular file')
    return e

def validate_document_manifest(man, doc_dir, require_awaiting=True):
    """THE canonical document-manifest validator (HO-09 item 2), used by approval and any
    pre-consumption check. Returns a list of sanitized (category-only) error strings; empty == the
    manifest is a well-formed, strictly-versioned document-manifest for the supported schema. With
    require_awaiting, additionally requires an approvable AWAITING_OPERATOR state (no doc/page error,
    non-empty pages). Rejects unknown schema versions CLOSED rather than guessing an upgrade; does
    not preserve accidental compatibility with the permissive v2 shape."""
    e = []
    if not isinstance(man, dict):
        return ['manifest is not a JSON object']
    if man.get('schema_version') != SCHEMA_VERSION:
        e.append('unknown or unsupported manifest schema_version')
    if man.get('kind') != 'document-manifest':
        e.append('manifest kind is not document-manifest')
    if man.get('tool') != TOOL_NAME:
        e.append('manifest tool identity mismatch')
    if not isinstance(man.get('tool_version'), str):
        e.append('malformed tool_version')

    keys = set(man)
    if _MANIFEST_REQUIRED - keys:
        e.append('manifest is missing required field(s)')
    if keys - _MANIFEST_REQUIRED - _MANIFEST_OPTIONAL:
        e.append('manifest carries unknown top-level field(s)')

    if not (isinstance(man.get('run_id'), str) and RUN_ID_RE.match(man.get('run_id', ''))):
        e.append('malformed run_id')
    doc = man.get('doc')
    if not (isinstance(doc, str) and DOC_ID_RE.match(doc or '')):
        e.append('malformed or non-opaque document id')
    elif doc != os.path.basename(os.path.normpath(doc_dir)):
        e.append('manifest document id does not match its directory')
    input_sha = man.get('input_sha256')
    if not (isinstance(input_sha, str) and _HEX64_RE.match(input_sha or '')):
        e.append('malformed input hash')
    elif isinstance(doc, str) and DOC_ID_RE.match(doc) and doc != 'doc-' + input_sha[:16]:
        e.append('document id is not bound to the input hash')
    if not isinstance(man.get('created_utc'), str):
        e.append('malformed created_utc')
    if not (isinstance(man.get('notes'), list) and all(isinstance(x, str) for x in man.get('notes', []))):
        e.append('malformed notes')
    ep = man.get('expected_pages')
    if not (ep is None or (_is_int(ep) and ep >= 0)):
        e.append('malformed expected_pages')

    state = man.get('state')
    if state not in ('AWAITING_OPERATOR', 'FAILED'):
        e.append('unknown manifest state')
    err = man.get('error')
    if err is not None and (not isinstance(err, str) or err not in KNOWN_DOC_ERRORS):
        e.append('unknown document error code')
    if (err is not None) != (state == 'FAILED'):
        e.append('inconsistent document error/state')
    if require_awaiting:
        if state != 'AWAITING_OPERATOR':
            e.append('manifest state is not AWAITING_OPERATOR')
        if err is not None:
            e.append('document carries an unresolved error; not approvable')

    pages = man.get('pages')
    if not isinstance(pages, list):
        e.append('pages is not a list')
        return e
    if not _is_int(man.get('n_pages')):
        e.append('malformed n_pages')
    elif man['n_pages'] != len(pages):
        e.append('n_pages does not equal the number of page records')
    elif ep is not None and ep != man['n_pages']:
        e.append('expected_pages does not equal n_pages')
    if len(pages) > MAX_PAGES_PER_DOC:
        e.append('page count exceeds the workload bound')
        return e  # refuse to iterate an unbounded page list (the bound exists to precede the work)
    if require_awaiting and not pages:
        e.append('no pages to approve')

    seen = []
    for p in pages:
        if not isinstance(p, dict):
            e.append('a page record is not an object'); continue
        pn = p.get('page')
        if not (_is_int(pn) and pn >= 1):
            e.append('malformed page number'); continue
        seen.append(pn)
        flags = p.get('flags')
        if not (isinstance(flags, list)
                and all(isinstance(f, str) and f in KNOWN_PAGE_FLAGS for f in flags)):
            e.append('unknown or malformed page flag(s)')
            flags = flags if isinstance(flags, list) else []
        is_error = 'PROCESS_ERROR' in flags
        if is_error:
            if require_awaiting:
                e.append('a page carries a processing error; not approvable')
            continue
        pk = set(p)
        if _PAGE_REQUIRED - pk:
            e.append('a page record is missing required field(s)')
        if pk - _PAGE_REQUIRED - _PAGE_OPTIONAL:
            e.append('a page record carries unknown field(s)')
        if not (isinstance(p.get('sha256'), str) and _HEX64_RE.match(p.get('sha256', ''))):
            e.append('malformed page hash')
        if not (isinstance(p.get('reasons'), list)
                and all(isinstance(r, str) and r in KNOWN_REASONS
                        for r in p.get('reasons', []))):
            e.append('unknown or malformed page reason(s)')
        conv = p.get('converged')
        if not isinstance(conv, bool):
            e.append('malformed converged flag')
        elif ('MASK_VERIFY_FAILED' in flags) == conv:
            e.append('inconsistent convergence/flag state')
        if not isinstance(p.get('label_seen'), bool):
            e.append('malformed label_seen')
        if p.get('osd_deg') not in (0, 90, 180, 270):
            e.append('malformed osd_deg')
        osd_conf = p.get('osd_conf')
        if (isinstance(osd_conf, bool) or not isinstance(osd_conf, (int, float)) or
                not math.isfinite(osd_conf) or osd_conf < 0):
            e.append('malformed osd_conf')
        osd_unreliable = p.get('osd_unreliable', False)
        if 'osd_unreliable' in p and not isinstance(osd_unreliable, bool):
            e.append('malformed osd_unreliable')
        elif bool(osd_unreliable) != ('OSD_UNRELIABLE' in flags):
            e.append('inconsistent osd_unreliable/flag state')
        if 'rotated' in p and p.get('rotated') not in (90, 180, 270):
            e.append('malformed rotated value')
        for nf in ('w', 'h'):
            if not (_is_int(p.get(nf)) and p.get(nf) > 0):
                e.append('malformed page dimension')
        for nf in ('n_words', 'n_masked', 'iters'):
            if not (_is_int(p.get(nf)) and p.get(nf) >= 0):
                e.append('malformed page counter')

    if seen:
        if len(set(seen)) != len(seen):
            e.append('duplicate page numbers')
        if seen != sorted(seen):
            e.append('page numbers are out of order')
        if sorted(seen) != list(range(1, len(seen) + 1)):
            e.append('page numbers are not a contiguous 1..N set')
        e.extend(_validate_dir_artifacts(doc_dir, seen, {'manifest.json'}))
    return e

# approval-attestation (approval.json) schema — self-verifying approved bytes (HO-09 item 6)
_APPROVAL_REQUIRED = {'schema_version', 'kind', 'tool', 'tool_version', 'doc', 'source_run_id',
                      'source_manifest_sha256', 'approved_utc', 'pages',
                      'flags_present_at_approval', 'accepted_flagged'}

def validate_approval_attestation(app, approved_dir):
    """Canonical approval.json validator (HO-09 item 6), shared by the writer (approve_redaction)
    and the pre-consumption integrity reader (verify_approved). Category-only errors. Empty == a
    well-formed, strictly-versioned approval attestation whose page set is non-empty, contiguous,
    and unique."""
    e = []
    if not isinstance(app, dict):
        return ['approval is not a JSON object']
    if app.get('schema_version') != SCHEMA_VERSION:
        e.append('unknown or unsupported approval schema_version')
    if app.get('kind') != 'approval-attestation':
        e.append('approval kind mismatch')
    if app.get('tool') != 'approve_redaction.py':
        e.append('approval tool identity mismatch')
    if not isinstance(app.get('tool_version'), str):
        e.append('malformed tool_version')
    keys = set(app)
    if _APPROVAL_REQUIRED - keys:
        e.append('approval is missing required field(s)')
    if keys - _APPROVAL_REQUIRED:
        e.append('approval carries unknown field(s)')
    doc = app.get('doc')
    if not (isinstance(doc, str) and DOC_ID_RE.match(doc or '')):
        e.append('malformed or non-opaque approval document id')
    elif doc != os.path.basename(os.path.normpath(approved_dir)):
        e.append('approval document id does not match its directory')
    if not (isinstance(app.get('source_run_id'), str) and RUN_ID_RE.match(app.get('source_run_id', ''))):
        e.append('malformed source run id')
    if not (isinstance(app.get('source_manifest_sha256'), str) and _HEX64_RE.match(app.get('source_manifest_sha256', ''))):
        e.append('malformed source manifest hash')
    if not isinstance(app.get('approved_utc'), str):
        e.append('malformed approved_utc')
    approval_flags = app.get('flags_present_at_approval')
    if not (isinstance(approval_flags, list)
            and all(isinstance(f, str) and f in HOLD_FLAGS for f in approval_flags)
            and approval_flags == sorted(set(approval_flags))):
        e.append('malformed or unknown approval flag set')
    accepted_flagged = app.get('accepted_flagged')
    if not isinstance(accepted_flagged, bool):
        e.append('malformed accepted_flagged')
    elif isinstance(approval_flags, list) and accepted_flagged != bool(approval_flags):
        e.append('accepted_flagged does not match the approval flag set')
    pages = app.get('pages')
    if not isinstance(pages, list) or not pages:
        e.append('approval has no pages')
        return e
    if len(pages) > MAX_PAGES_PER_DOC:
        e.append('approval page count exceeds the workload bound')
        return e  # refuse to iterate an unbounded page list
    seen = []
    for p in pages:
        if not (isinstance(p, dict) and set(p) == {'page', 'sha256'}):
            e.append('an approval page record has the wrong fields'); continue
        pn = p.get('page')
        if not (_is_int(pn) and pn >= 1):
            e.append('malformed approval page number'); continue
        if not (isinstance(p.get('sha256'), str) and _HEX64_RE.match(p.get('sha256', ''))):
            e.append('malformed approval page hash')
        seen.append(pn)
    if seen:
        if len(set(seen)) != len(seen):
            e.append('duplicate approval page numbers')
        if seen != sorted(seen):
            e.append('approval page numbers are out of order')
        if sorted(seen) != list(range(1, len(seen) + 1)):
            e.append('approval page numbers are not a contiguous 1..N set')
    return e

def _doc_has_error(rec):
    return bool(rec.get('error')) or any(
        f in ERROR_FLAGS for p in rec.get('pages', []) for f in p.get('flags', []))

def _finalize_doc(rec, sdir, a, run_id, doc):
    """Write the per-document manifest inside its (still-staged) directory, then atomically
    promote that staged directory to be the live --redacted/<doc>/. A pre-existing (stale, or
    from a longer prior version of this document) --redacted/<doc>/ is superseded, never merged
    with — a shorter rerun can never leave a prior run's extra trailing pages behind. An errored
    document's manifest is stamped FAILED, never AWAITING_OPERATOR — a failed run must not claim
    operator-readiness (approval refuses it either way; the state must not overstate)."""
    rec['state'] = 'FAILED' if _doc_has_error(rec) else 'AWAITING_OPERATOR'
    _atomic_write_json(os.path.join(sdir, 'manifest.json'), rec)
    final_dir = os.path.join(a.redacted, doc)
    superseded = _promote_dir(sdir, final_dir)
    # NB: absolute paths are NOT written back into rec — rec is embedded in the run log, and a
    # path component can itself carry the never-API identifier (HO-09 item 3). Only the opaque
    # supersession basename (doc-id + timestamp + pid + hex — no filename) is recorded, for audit.
    rec['superseded_previous_name'] = os.path.basename(superseded) if superseded else None

def process_pdf(pdf, input_sha, a, run_id, render_run, work_run):
    doc = 'doc-' + input_sha[:16]              # opaque, content-derived identity (DOC_ID_RE); no filename
    rdir = os.path.join(render_run, doc)
    wdir = os.path.join(work_run, doc)
    sdir = os.path.join(a.redacted, '.staging', run_id, doc)  # fresh; promoted at the end
    os.makedirs(rdir, exist_ok=False)
    os.makedirs(wdir, exist_ok=False)
    os.makedirs(sdir, exist_ok=False)
    for private_dir in (rdir, wdir, os.path.join(a.redacted, '.staging'),
                        os.path.dirname(sdir), sdir):
        os.chmod(private_dir, 0o700)
    rec = dict(schema_version=SCHEMA_VERSION, kind='document-manifest', tool=TOOL_NAME,
               tool_version=TOOL_VERSION, run_id=run_id, doc=doc,
               input_sha256=input_sha, created_utc=_utcnow(),
               n_pages=0, expected_pages=None, pages=[], error=None, notes=[])

    try:
        run_checked(['pdftoppm', '-r', str(a.dpi), '-png', pdf, os.path.join(rdir, 'page')],
                    stage='render')
    except ToolError as e:
        rec['error'] = 'RENDER_FAILED'; rec['error_stage'] = e.stage; rec['error_reason'] = e.reason
        _finalize_doc(rec, sdir, a, run_id, doc)
        return rec

    pages = sorted(glob.glob(os.path.join(rdir, 'page-*.png')),
                   key=lambda p: int(re.search(r'page-(\d+)\.png', p).group(1)))
    for rendered_page in pages:
        os.chmod(rendered_page, 0o600)
    rec['n_pages'] = len(pages)
    if not pages:
        rec['error'] = 'RENDER_FAILED'
        _finalize_doc(rec, sdir, a, run_id, doc)
        return rec

    nums = [int(re.search(r'page-(\d+)\.png', p).group(1)) for p in pages]
    if nums != list(range(1, len(nums) + 1)):
        rec['error'] = 'PAGE_COUNT_MISMATCH'
        rec['notes'].append('rendered page numbering has a gap or duplicate')
        _finalize_doc(rec, sdir, a, run_id, doc)
        return rec

    # independently-determined page count, where available (point 5)
    if shutil.which('pdfinfo'):
        try:
            r = run_checked(['pdfinfo', pdf], stage='pdfinfo')
            m = re.search(r'^Pages:\s*(\d+)', r.stdout, re.M)
            if m:
                rec['expected_pages'] = int(m.group(1))
                if rec['expected_pages'] != len(pages):
                    rec['error'] = 'PAGE_COUNT_MISMATCH'
                    rec['notes'].append(
                        f"pdfinfo reports {rec['expected_pages']} page(s), rendered {len(pages)}")
                    _finalize_doc(rec, sdir, a, run_id, doc)
                    return rec
        except ToolError:
            rec['notes'].append('PDFINFO_UNAVAILABLE')
    else:
        rec['notes'].append('PDFINFO_UNAVAILABLE')

    for png in pages:
        pno = int(re.search(r'page-(\d+)\.png', png).group(1))
        pg = dict(page=pno)
        out = os.path.join(sdir, f'page-{pno:02d}.png')
        try:
            odeg, oconf, osd_unreliable = osd(png)
            pg['osd_deg'], pg['osd_conf'] = odeg, round(oconf, 2)
            if osd_unreliable:
                pg['osd_unreliable'] = True
            work_png = png
            if odeg in (90, 180, 270) and oconf >= OSD_CONF_MIN:
                work_png = rotate_to(png, png.replace('.png', '_rot.png'), odeg)
                pg['rotated'] = odeg
            W, H = dims(work_png)
            words = parse_tsv(ocr_tsv(work_png, os.path.join(wdir, f'p{pno}.tsv'), a.lang))
            good = [w for w in words if w['conf'] >= CONF_MIN]
            lh = median([w['height'] for w in good]) or max(1, H // 80)
            pad = int(0.06 * lh) + 6
            plain_labels = []
            signals = set()
            hits, label_seen, label_no_cand = detect(
                words, W, H, a.prefix, rules=a.rules, label_token=a.label_token, scheme=a.scheme,
                label_boxes=plain_labels, dob=a.dob, signals=signals, known=getattr(a, 'known', None))
            faint, dark_labels, dark_unread = faint_hits(work_png, wdir, f'p{pno}', a, W, H, hits, a.label_token,
                                                         signals)
            hits += faint
            # a label only the darkened read sees, with no number near it: wherever the plain read saw others
            label_no_cand = label_no_cand or any(
                not found and not any(overlaps(box, p) for p, _ in plain_labels) for box, found in dark_labels)
            first_reasons = sorted({h['reason'] for h in hits})
            checksum_only = bool(first_reasons) and set(first_reasons) <= {'id-checksum', 'id-checksum-fuzzy'}
            low_conf = 'id-low-confidence' in first_reasons
            # bare nine digits are a phone's or a record number's shape too: alone, the operator looks
            bare_only = ('id-shape-bare' in first_reasons
                         and set(first_reasons) <= {'id-shape-bare', 'id-checksum', 'id-checksum-fuzzy'})

            masks = [pad_clamp(h['box'], W, H, pad) for h in hits]
            burn(work_png, masks, out)

            # iterative verify-and-remask (OCR non-determinism / multiple instances). A failure
            # inside the loop (e.g. re-OCR of the masked raster) is NOT treated as "converged" —
            # it is raised and the page becomes PROCESS_ERROR (see except below), because
            # silently reading "OCR couldn't run" as "no hits survived" would ship an unverified
            # page as if it had passed the verify loop.
            converged = (len(strong_hits(hits)) == 0)
            iters = 0
            for iters in range(1, a.max_iters + 1):
                bhits, _, _ = detect(
                    parse_tsv(ocr_tsv(out, os.path.join(wdir, f'p{pno}_v{iters}.tsv'), a.lang)),
                    W, H, a.prefix, rules=a.rules, label_token=None, scheme=a.scheme, dob=a.dob,
                    known=getattr(a, 'known', None))
                vfaint, _, vunread = faint_hits(out, wdir, f'p{pno}_v{iters}', a, W, H, bhits)
                bhits += vfaint
                dark_unread = dark_unread or vunread
                surv = strong_hits(bhits)
                low_conf = low_conf or any(h['reason'] == 'id-low-confidence' for h in surv)
                if not surv:
                    converged = True; break
                converged = False
                wide = pad + int(0.6 * lh) + 24  # survived one pass -> mask wider
                for h in surv:
                    masks.append(pad_clamp(h['box'], W, H, wide))
                burn(work_png, masks, out)

            flags = []
            if osd_unreliable:
                flags.append('OSD_UNRELIABLE')     # orientation uncertain -> operator confirms (HOLD)
            if len(good) < NEAR_EMPTY_WORDS:
                flags.append('NEAR_EMPTY_OCR')
            if label_no_cand:
                flags.append('LABEL_NO_CANDIDATE')
            if not converged:
                flags.append('MASK_VERIFY_FAILED')
            if checksum_only:
                flags.append('CHECKSUM_ONLY_EXPECT_FALSE_POSITIVE')
            if low_conf:
                flags.append('LOW_CONFIDENCE_CANDIDATE')  # masked, but OCR could not read it: the operator looks
            if dark_unread:
                flags.append('DARKENED_READ_UNREADABLE')  # faint ink went unchecked: the operator looks
            if bare_only:
                flags.append('BARE_NUMBER_ONLY')
            if 'scan-code' in signals:
                flags.append('SCANNABLE_CODE')            # the operator covers the printed code and rescans
            pg.update(w=W, h=H, n_words=len(good), label_seen=label_seen,
                      reasons=first_reasons, n_masked=len(masks), iters=iters,
                      converged=converged, flags=flags, sha256=_sha256_file(out))
        except ToolError as e:
            pg['flags'] = ['PROCESS_ERROR']
            pg['error_stage'] = e.stage
            pg['error_reason'] = e.reason
        except Exception as e:
            pg['flags'] = ['PROCESS_ERROR']
            pg['error_type'] = type(e).__name__
        if 'PROCESS_ERROR' in pg['flags']:
            _discard_page_raster(out)
        rec['pages'].append(pg)

    _finalize_doc(rec, sdir, a, run_id, doc)
    return rec

# ---- CLI: parsing, validation, pipeline driver, exit-code contract ----
def _shipped_schemes():
    """The schemes a run can name, as advertised: the number list's rows (none when it cannot be read)."""
    try:
        return ', '.join(k for k in id_schemes.load() if k in SCHEMES)
    except id_schemes.SchemeError:
        return ''

def _scheme_keys(text):
    """--scheme KEY[,KEY]: the keys in order, once each, joined by commas."""
    keys = []
    for k in text.split(','):
        k = k.strip()
        if k not in SCHEMES:
            raise argparse.ArgumentTypeError('names a scheme this tool does not know; known: ' + _shipped_schemes())
        if k not in keys:
            keys.append(k)
    return ','.join(keys)

def build_arg_parser():
    ap = argparse.ArgumentParser(description='Private mode: local ID redaction (ADR-0029)')
    ap.add_argument('--inbox', required=True, help='dir with input *.pdf scans')
    ap.add_argument('--render', required=True, help='work dir root: raw page rasters (run-scoped; DELETE after run)')
    ap.add_argument('--redacted', required=True,
                    help='AWAITING_OPERATOR output dir: masked rasters + manifest.json, one subdir per document')
    ap.add_argument('--work', required=True,
                    help='work dir root: OCR TSVs, and each darkened copy while it is read (run-scoped; DELETE after run)')
    ap.add_argument('--log', required=True, help='JSON run log (metadata only, no text/digits); must not pre-exist')
    dob = ap.add_mutually_exclusive_group()    # required when a selected scheme needs it (main)
    dob.add_argument('--dob', help="patient's DOB YYYY-MM-DD -> identifier prefix")
    dob.add_argument('--dob-from-identity', metavar='PERSON_FOLDER',
                     help="the folder of a person who keeps their DOB from the AI: it comes from their identity file, so no "
                          "session writes it")
    ap.add_argument('--number-from-identity', metavar='PERSON_FOLDER',
                    help="a private-mode person's folder: their own number comes from their identity file "
                         "(required for a scheme whose number holds no date: ADR-0074)")
    ap.add_argument('--scheme', default=None, type=_scheme_keys, metavar='KEY[,KEY]',
                    help="the identifier schemes the person's profile tag names (no default: ADR-0062); "
                         "known: " + _shipped_schemes())
    ap.add_argument('--covered-by-hand', action='store_true',
                    help="the person's private-mode tag names the key unlisted, and the operator "
                         "covered it by hand on every page before scanning (ADR-0076); in place of --scheme "
                         "it needs --lang")
    ap.add_argument('--label-token', default=None,
                    help='the ID label exactly as printed on documents (enables the label rule)')
    ap.add_argument('--rules', default=','.join(DEFAULT_RULES),
                    help='comma-set of: ' + ','.join(ALL_RULES) + ' (e.g. gate-fix reruns: prefix,label,lowconf)')
    ap.add_argument('--dpi', type=int, default=300, help='render DPI (~2x the scan density; more is blur)')
    ap.add_argument('--lang', default=None,
                    help="tesseract language pack (default: the schemes' joined with +, from the number list)")
    ap.add_argument('--max-iters', type=int, default=5)
    return ap

_DOB_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_LANG_RE = re.compile(r'[A-Za-z0-9_]+')

def run_langs(keys, lang, table):
    """The tesseract languages a run reads with: --lang's, or the selected rows' joined in order."""
    if lang:
        return lang.split('+')
    langs = []
    for k in keys:
        langs += [x for x in table[k]['lang'].split('+') if x not in langs]
    return langs

def _installed_langs():
    """The language data tesseract lists, or None when it cannot list them. Its output is never shown."""
    try:
        r = run_checked(['tesseract', '--list-langs'], stage='list-langs')
    except ToolError:
        return None
    lines = ((r.stdout or '') + '\n' + (r.stderr or '')).splitlines()   # older versions list on stderr
    return {l.strip() for l in lines if _LANG_RE.fullmatch(l.strip())}

def distinct_nonnested_errors(dirs):
    """Given {label: path}, return sanitized error strings if any two resolve to the same
    real path or one is nested inside another — aliasing/nesting lets one stage's output land
    under another stage's tree. Shared by redact_ids.validate_args and approve_redaction so
    both tools apply the identical rule. Messages carry the labels only, never the paths."""
    errs = []
    reals = {k: os.path.realpath(v) for k, v in dirs.items()}
    seen = {}
    for k, v in reals.items():
        if v in seen:
            errs.append(f'--{k} and --{seen[v]} resolve to the same path; directories must be distinct')
        else:
            seen[v] = k
    keys = list(reals)
    for i, ki in enumerate(keys):
        for kj in keys[i + 1:]:
            vi, vj = reals[ki], reals[kj]
            if vi == vj:
                continue
            common = os.path.commonpath([vi, vj])
            if common == vi:
                errs.append(f'--{ki} is a parent directory of --{kj}; directories must not be nested')
            elif common == vj:
                errs.append(f'--{kj} is a parent directory of --{ki}; directories must not be nested')
    return errs

def doc_labels(docs):
    """Model-visible labels for discovered document folder names, in order: the name itself only
    when it has the generated opaque form (DOC_ID_RE), otherwise a numbered category. A renamed or
    misfiled folder's name can carry the never-API identifier, so no part of it is ever echoed —
    the folder is still rejected by the validators; only its printed name is withheld. Shared by
    approve_redaction and verify_approved so both CLIs print the identical form."""
    out, odd = [], 0
    for d in docs:
        if DOC_ID_RE.fullmatch(d):
            out.append(d)
        else:
            odd += 1
            out.append('non-standard folder name #%d (withheld)' % odd)
    return out

def validate_args(a):
    """Return a list of sanitized, human-readable error strings (never echoes --dob or
    --label-token values). Empty list == invocation is well-formed enough to attempt."""
    errs = []
    if not os.path.isdir(a.inbox):
        errs.append('--inbox does not exist or is not a directory')
    elif not os.access(a.inbox, os.R_OK):
        errs.append('--inbox is not readable')

    keys = [k for k in a.scheme.split(',') if k]   # known keys only: _scheme_keys parsed them
    if a.dob is None and not any(SCHEMES[k]['window'] == 'sliding' for k in keys):
        pass                                      # no selected scheme needs a DOB; none was given
    elif not _DOB_RE.match(a.dob or ''):
        errs.append('--dob must be in the form YYYY-MM-DD')
    else:
        try:
            datetime.date.fromisoformat(a.dob)   # REAL calendar validation (HO-09 item 1): rejects
        except ValueError:                        # 1901-99-99 / 02-30; accepts a valid leap day 02-29.
            errs.append('--dob is not a real calendar date')  # value never echoed (fixed string)
        else:
            try:
                for k in keys:
                    if SCHEMES[k]['dob_prefix']:
                        SCHEMES[k]['dob_prefix'](a.dob)
            except (ValueError, KeyError, IndexError):
                errs.append('--dob is a real date but outside the century range the selected --scheme covers')

    table = None
    try:
        table = id_schemes.load()
        if any(k not in table for k in keys):     # a scheme comes with its row (ADR-0062)
            errs.append('--scheme is not in the private-mode number list (id-schemes.tsv)')
            table = None
    except id_schemes.SchemeError as e:
        errs.append(str(e))

    if not a.rules:
        errs.append('--rules must name at least one of: ' + ', '.join(ALL_RULES))
    else:
        unknown = set(a.rules) - set(ALL_RULES)
        if unknown:
            errs.append('--rules contains unknown token(s); allowed: ' + ', '.join(ALL_RULES))

    if a.dpi <= 0:
        errs.append('--dpi must be a positive integer')
    if a.max_iters <= 0:
        errs.append('--max-iters must be a positive integer')

    errs.extend(distinct_nonnested_errors(
        dict(inbox=a.inbox, render=a.render, work=a.work, redacted=a.redacted)))

    # Reject symlinked roots (HO-09 items 1/14): a symlinked working/output root can alias a path
    # outside the declared tree, undermining path ownership and the atomic-promotion guarantees.
    for label, path in (('inbox', a.inbox), ('render', a.render), ('work', a.work),
                        ('redacted', a.redacted)):
        if os.path.islink(path):
            errs.append(f'--{label} is a symlink; symlinked roots are refused (path-ownership boundary)')

    if os.path.exists(a.log):
        errs.append('--log path already exists; refusing to reuse/overwrite a prior run log (choose a fresh path)')

    for exe in ('pdftoppm', 'tesseract'):
        if shutil.which(exe) is None:
            errs.append(f'required executable not found on PATH: {exe}')
    # The selected schemes' language data, named before any page is read (check-setup.sh reports them
    # without requiring them). The language code only, never a person or a path.
    if table is not None and (keys or a.lang) and shutil.which('tesseract') is not None:
        have = _installed_langs()
        if have is None:
            errs.append("tesseract could not list its language data")
        else:
            for lang in run_langs(keys, a.lang, table):
                if lang not in have:
                    errs.append("tesseract's language data (%s) is not installed; "
                                "bash tools/private-mode/check-setup.sh names the command that installs it"
                                % (lang if _LANG_RE.fullmatch(lang) else 'one named by --lang'))
    return errs

# The care folder's people, from this file's place in it (tools/private-mode/): their intake trays are found here.
PATIENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))), 'patients')
NOT_A_TRAY = object()                         # _tray_profile: this folder has people, and --inbox is none of their trays
UNREADABLE = object()                         # _tray_profile: the roster, a tray or the profile cannot be read

def _tray_profile(inbox):
    """The bytes of the profile of the person whose intake tray (patients/<handle>/med/_inbox) --inbox is,
    or is under. None when this folder has no people (no patients/: a development tree); NOT_A_TRAY when
    it has people and --inbox is in none of their trays; UNREADABLE on any other error, or when it is in
    more than one person's tray. A tray is known by
    the directory itself (device and inode) among the resolved --inbox and the folders above it, never by the names
    in the path given; a path not known as a tray refuses (ADR-0077: fail toward refusing, never skip)."""
    try:
        handles = sorted(os.listdir(PATIENTS))
    except FileNotFoundError:
        return None
    except OSError:
        return UNREADABLE
    try:
        seen, here = set(), os.path.realpath(inbox)
        while True:
            st = os.stat(here)
            seen.add((st.st_dev, st.st_ino))
            if os.path.dirname(here) == here:
                break
            here = os.path.dirname(here)
        owners = []
        for handle in handles:
            try:
                st = os.stat(os.path.join(PATIENTS, handle, 'med', '_inbox'))
            except (FileNotFoundError, NotADirectoryError):
                continue                     # no tray for this person
            if (st.st_dev, st.st_ino) in seen:
                owners.append(handle)
        if len(owners) > 1:
            return UNREADABLE                # two people's trays meet here: whose pages these are is unknown
        if owners:
            with open(os.path.join(PATIENTS, owners[0], 'profile.md'), 'rb') as fh:
                return fh.read()
    except OSError:
        return UNREADABLE
    return NOT_A_TRAY

def _schemes_cover_tag(data, keys, covered_by_hand):
    """ADR-0077: a run on a private-mode person's intake tray leaves out no key the profile's tag names
    (every row of the list when no exact tag is read): a key left out would leave that number unmasked.
    The key `unlisted` is named by --covered-by-hand. An extra key only masks more. Exact tokens only: the
    marker and id_schemes.profile_schemes. `data` is _tray_profile's answer (NOT_A_TRAY is refused before).
    No people in this folder, or a profile without the marker: True. Unreadable, or a refused tag: False."""
    if data is None:
        return True
    if data is UNREADABLE:
        return False
    if id_schemes.MARK.encode('utf-8') not in data:
        return True
    run = set(keys) | ({id_schemes.UNLISTED} if covered_by_hand else set())
    try:
        return set(id_schemes.profile_schemes(data, id_schemes.load())) <= run
    except id_schemes.SchemeError:
        return False

def _left_out(data, keys):
    """The listed keys the profile's tag names (every row when no exact tag is read) that a run of these keys
    leaves out, in tag or list order; [] when there is no marked profile or its tag cannot be read. Row names
    only, never a value, so a refusal may print them."""
    if not isinstance(data, bytes) or id_schemes.MARK.encode('utf-8') not in data:
        return []
    try:
        named = id_schemes.profile_schemes(data, id_schemes.load())
    except id_schemes.SchemeError:
        return []
    return [k for k in named if k != id_schemes.UNLISTED and k not in keys]

def _covered_by_hand_allowed(data, keys):
    """ADR-0076, ADR-0077: --covered-by-hand only for a person whose exact tag names the key `unlisted`, and
    never in place of a number the tag names: every other tagged key must be among the run's --scheme keys.
    `data` is _tray_profile's answer for --inbox. No profile found or read, or an unreadable tag: False."""
    if not isinstance(data, bytes):
        return False
    try:
        tagged = id_schemes.profile_schemes(data, id_schemes.load())
    except id_schemes.SchemeError:
        return False
    return id_schemes.UNLISTED in tagged and set(tagged) - {id_schemes.UNLISTED} <= set(keys)

def _sanitized_args(a):
    """Args safe to write into the run log. DOB and label-token VALUES are never included (only
    whether a label token was supplied), and — HO-09 item 3 — the inbox/render/work/redacted PATHS
    are omitted too: a path component can itself carry the never-API identifier, and the run log is
    described as non-sensitive/model-eligible. Only non-path knobs remain."""
    return dict(scheme=a.scheme, rules=list(a.rules), dpi=a.dpi, lang=a.lang,
                max_iters=a.max_iters, label_token_given=bool(a.label_token),
                known_number_given=bool(getattr(a, 'known', None)),
                covered_by_hand=bool(getattr(a, 'covered_by_hand', False)))

def _assert_no_name_residue(results, docmap):
    """Fail CLOSED if any source FILENAME appears in the JSON-serialized document records that back
    stdout and the run log. Opaque doc ids should make this impossible; this is the executable proof
    for HO-09 item 3. Two correctness points (both were red-team defects, now fixed):
      * The needle is escaped the SAME way the surfaces are serialized (`json.dumps(basename)[1:-1]`,
        ensure_ascii=True) — a non-ASCII name (e.g. a Polish filename) is written as \\uXXXX in the
        run log, so a raw-string search would silently miss exactly the target population.
      * The needle is the full basename (it always ends in `.pdf` — glob matched `*.pdf`), which never
        appears in the manifest's structural scaffolding — so common scan names like `document.pdf`
        or `notes.pdf` do NOT false-trip the check (their bare stems are substrings of structural
        keys/values like `document-manifest` / `n_pages`; the full name is not).
    Raises RuntimeError (category only — never the leaked name) -> mapped to the documented exit 65."""
    blob = json.dumps(results)  # ensure_ascii=True — identical to how _atomic_write_json persists
    for basename in docmap.values():
        if not basename:
            continue
        needle = json.dumps(basename)[1:-1]  # escape identically before comparing
        if needle and needle in blob:
            raise RuntimeError('internal residue check failed')
        # Also catch the canonical never-API threat — a scan named after the identifier — even if it
        # leaked WITHOUT its extension (a bare '44051401359'). Gate to an all-digit stem of length
        # >= the scheme's shortest prefix so it can NEVER be a substring of the structural scaffolding
        # (whose numeric tokens are short, e.g. the '256' in 'input_sha256'): this closes the
        # extension-less evasion without reopening the 'document.pdf'-style false positive.
        stem = os.path.splitext(basename)[0]
        if re.fullmatch(r'\d{6,}', stem) and stem in blob:
            raise RuntimeError('internal residue check failed')

def _write_never_api_map(redacted_root, docmap):
    """Merge {opaque-id: source-basename} into a LOCAL-ONLY never-API map beside the redacted tree.
    Best-effort and non-load-bearing: identity/supersession do not depend on it (the id is content-
    derived), so a corrupt/absent map is never fatal. Its dotfile name keeps it out of the
    `*/manifest.json` glob; it holds filenames (possibly identifier-shaped) and must NEVER be read
    by any model-facing step, printed, or copied into a tracked file (the redacted tree is
    gitignored + publish-DENY)."""
    if not docmap:
        return
    path = os.path.join(redacted_root, NEVER_API_MAP_NAME)
    try:
        merged = {}
        if os.path.isfile(path) and not os.path.islink(path):
            try:
                with open(path) as f:
                    prior = json.load(f)
                if isinstance(prior, dict) and isinstance(prior.get('map'), dict):
                    merged = dict(prior['map'])
            except (OSError, json.JSONDecodeError, ValueError):
                merged = {}   # tolerate a corrupt prior map (informational only)
        merged.update(docmap)
        _atomic_write_json(path, {
            'kind': 'never-api-source-map',
            'note': 'LOCAL ONLY — opaque doc id -> source filename. Must NEVER reach the API, a '
                    'model-facing step, or a tracked file. Not read by verify/approve.',
            'map': merged})
    except OSError:
        pass  # best-effort; never fail a run over the informational map

def run_pipeline(a):
    """Process every *.pdf under a.inbox. Returns (results, run_id, exit_code, run_result).
    run_id is None iff the input was empty (EXIT_EMPTY_INPUT) — nothing else was created."""
    pdfs = sorted(glob.glob(os.path.join(a.inbox, '*.pdf')))
    if not pdfs:
        return [], None, EXIT_EMPTY_INPUT, 'EMPTY_INPUT'

    run_id = f'{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}-{secrets.token_hex(4)}'
    render_run = os.path.join(a.render, run_id)
    work_run = os.path.join(a.work, run_id)
    snap_run = os.path.join(work_run, 'input-snapshots')
    try:
        os.makedirs(render_run, exist_ok=False)
        os.makedirs(work_run, exist_ok=False)
        os.makedirs(snap_run, exist_ok=False)
        os.chmod(render_run, 0o700)
        os.chmod(work_run, 0o700)
        os.chmod(snap_run, 0o700)
    except FileExistsError:
        # sanitized: no path/filename in the exception object (it is caught in main() and mapped
        # to exit 65 — the message must not carry a path even in-process)
        raise RuntimeError('run-scoped directory collision')

    def _failed_rec(error, error_type=None, state='FAILED', notes=None):
        return dict(schema_version=SCHEMA_VERSION, kind='document-manifest', tool=TOOL_NAME,
                    tool_version=TOOL_VERSION, run_id=run_id, doc='doc-' + secrets.token_hex(8),
                    input_sha256='0' * 64, created_utc=_utcnow(), n_pages=0, expected_pages=None,
                    pages=[], error=error, state=state, notes=notes or [],
                    **({'error_type': error_type} if error_type else {}))

    results = []
    docmap = {}        # opaque doc id -> source basename, for the LOCAL never-API map ONLY (never printed)
    seen_shas = set()  # FULL input hashes already processed THIS run (byte-identical dedup)
    for pdf in pdfs:
        basename = os.path.basename(pdf)
        try:
            input_mode = os.lstat(pdf).st_mode
        except OSError as e:
            rec = _failed_rec('PROCESS_ERROR', error_type=type(e).__name__,
                              notes=['could not inspect input; nothing promoted for this document'])
            results.append(rec); docmap[rec['doc']] = basename
            continue
        if stat.S_ISLNK(input_mode):
            # a symlinked input PDF can point outside the inbox (path ownership) — refuse it as a
            # documented, opaque-id FAILED record; never hash/render a file the inbox does not own.
            rec = _failed_rec('SYMLINK_REJECTED', notes=['symlinked input rejected (path ownership)'])
            results.append(rec); docmap[rec['doc']] = basename
            continue
        if not stat.S_ISREG(input_mode):
            # In particular, never open a FIFO named *.pdf: hashing it would block indefinitely.
            rec = _failed_rec('PROCESS_ERROR', notes=['non-regular input rejected; nothing promoted'])
            results.append(rec); docmap[rec['doc']] = basename
            continue
        try:
            # snapshot FIRST: the copied bytes are hashed as they are copied, so
            # id + dedup + every later render/pdfinfo step bind ONE immutable capture of the input
            # — the mutable inbox path is never reopened after this point. An OSError (unreadable /
            # vanished / symlink raced in) or ValueError (non-regular / over-bound) is contained.
            snap_pdf, input_sha = _snapshot_input(pdf, snap_run)
        except (OSError, ValueError) as e:
            rec = _failed_rec('PROCESS_ERROR', error_type=type(e).__name__,
                              notes=['could not snapshot input; nothing promoted for this document'])
            results.append(rec); docmap[rec['doc']] = basename
            continue
        doc_id = 'doc-' + input_sha[:16]
        if input_sha in seen_shas:
            # byte-identical (FULL sha, not the truncated id) to an earlier input this run: the same
            # document by content. Process it ONCE and record the duplicate as a benign, non-error
            # note. Keying on the full hash is deliberate: two DIFFERENT documents that merely share
            # the 64-bit id prefix must NOT be silently dropped here — they fall through to
            # process_pdf, collide on the run-scoped makedirs(exist_ok=False), and fail CLOSED as a
            # documented PROCESS_ERROR / run ERROR (operator alerted), never a silent "duplicate".
            results.append(dict(schema_version=SCHEMA_VERSION, kind='document-manifest', tool=TOOL_NAME,
                                tool_version=TOOL_VERSION, run_id=run_id, doc=doc_id,
                                input_sha256=input_sha, created_utc=_utcnow(), n_pages=0,
                                expected_pages=None, pages=[], error=None, state='SKIPPED_DUPLICATE',
                                notes=['byte-identical to an earlier input this run; processed once']))
            docmap.setdefault(doc_id, basename)
            try:
                os.unlink(snap_pdf)   # duplicate's snapshot is unneeded; best-effort, run-owned
            except OSError:
                pass
            continue
        seen_shas.add(input_sha)
        try:
            rec = process_pdf(snap_pdf, input_sha, a, run_id, render_run, work_run)
            results.append(rec)
            docmap[rec['doc']] = basename
        except Exception as e:
            # Exception firewall at the document boundary: an unexpected failure outside the per-page
            # handling (e.g. a staging makedirs error) must surface as a documented ERROR result for
            # THIS document — never an unhandled traceback with an undocumented exit code, and never
            # abandonment of the remaining documents. Sanitized: exception TYPE only, no message.
            rec = _failed_rec('PROCESS_ERROR', error_type=type(e).__name__,
                              notes=['document-level exception; nothing promoted for this document'])
            results.append(rec); docmap[rec['doc']] = basename
        finally:
            # the snapshot is dead weight once render/pdfinfo consumed it — one fewer raw-identifier
            # copy on disk (best-effort; --work deletion after the run remains the caller's duty)
            try:
                os.unlink(snap_pdf)
            except OSError:
                pass

    # DEFENSE IN DEPTH (HO-09 item 3): prove the model-visible surfaces (the recs, which back both
    # stdout and the run log) carry NO source basename/stem residue — the opaque-id design should
    # already guarantee it. If a raw name leaked, fail CLOSED rather than emit it.
    _assert_no_name_residue(results, docmap)
    # LOCAL-ONLY never-API map: opaque id -> source filename, for the operator to correlate an
    # eyeballed doc dir back to its physical file. Written through a separate interface; NEVER read
    # or printed by this tool, approve_redaction, or verify_approved; best-effort (non-load-bearing).
    _write_never_api_map(a.redacted, docmap)

    # best-effort cleanup of the (now-empty, if every doc promoted cleanly) staging root; never
    # a recursive delete — os.removedirs only removes directories it finds empty.
    try:
        os.removedirs(os.path.join(a.redacted, '.staging', run_id))
    except OSError:
        pass

    any_error = any(
        r.get('error') in DOC_ERROR_STATES or r.get('error') == 'PROCESS_ERROR' or
        any(f in ERROR_FLAGS for p in r.get('pages', []) for f in p.get('flags', []))
        for r in results)
    any_hold = any(f in HOLD_FLAGS for r in results for p in r.get('pages', []) for f in p.get('flags', []))
    if any_error:
        run_result, exit_code = 'ERROR', EXIT_PROCESS_ERROR
    elif any_hold:
        run_result, exit_code = 'HOLD', EXIT_HOLD
    else:
        run_result, exit_code = 'CLEAN', EXIT_OK_AWAITING_OPERATOR
    return results, run_id, exit_code, run_result

def main(argv=None):
    global IM
    if sys.version_info < MIN_PYTHON:
        print(f'ABORT: requires Python >= {".".join(map(str, MIN_PYTHON))}', file=sys.stderr)
        return EXIT_INVALID_INVOCATION

    ap = build_arg_parser()
    a = ap.parse_args(argv)
    a.rules = tuple(sorted({r.strip() for r in a.rules.split(',') if r.strip()}))
    a.scheme = a.scheme or ''                     # none named: --covered-by-hand alone (ADR-0076)
    keys = [k for k in a.scheme.split(',') if k]
    if not keys and not a.covered_by_hand:
        ap.error('one of the arguments --scheme --covered-by-hand is required')
    if not keys and not a.lang:
        ap.error('--covered-by-hand without --scheme needs --lang, the language of the documents')
    if a.dob is None and a.dob_from_identity is None and any(SCHEMES[k]['window'] == 'sliding' for k in keys):
        ap.error('one of the arguments --dob --dob-from-identity is required')

    try:
        IM = _im()
    except RuntimeError as e:
        print(f'ABORT (invalid invocation): {e}')
        return EXIT_INVALID_INVOCATION

    if a.dob_from_identity:
        import identity                        # beside this file; stdlib only, like id_schemes
        try:
            a.dob = identity.recorded_dob(a.dob_from_identity)
        except identity.Refused as e:          # category only, never a value
            print(f'ABORT (invalid invocation): {e}')
            return EXIT_INVALID_INVOCATION

    a.known = {}
    if a.number_from_identity:
        import identity
        try:
            a.known = {k: v for k, v in identity.recorded_numbers(a.number_from_identity).items() if k in keys}
        except identity.Refused as e:          # category only, never a value
            print(f'ABORT (invalid invocation): {e}')
            return EXIT_INVALID_INVOCATION
    errs = validate_args(a)
    if errs:
        for e in errs:
            print(f'ABORT (invalid invocation): {e}')
        return EXIT_INVALID_INVOCATION
    profile = _tray_profile(a.inbox)
    if profile is NOT_A_TRAY:
        print('ABORT (invalid invocation): --inbox is not a person\'s intake tray in this care folder; put the '
              'pages in patients/<handle>/med/_inbox (a folder inside it is fine) and run on that; no page was read')
        return EXIT_INVALID_INVOCATION
    if a.covered_by_hand and not _covered_by_hand_allowed(profile, keys):
        print('ABORT (invalid invocation): --covered-by-hand is only for a person whose private-mode tag names '
              'the key unlisted, beside --scheme for every other number the tag names; this person\'s '
              'profile does not allow it (or cannot be read); no page was read')
        return EXIT_INVALID_INVOCATION
    if not _schemes_cover_tag(profile, keys, a.covered_by_hand):
        left = _left_out(profile, keys)
        print('ABORT (invalid invocation): the run leaves out a number this person\'s profile tag names (or the '
              'profile or its tag cannot be read)%s; pass in --scheme every listed key the tag names, and for '
              'the key unlisted --covered-by-hand once the operator has covered that number on every page; a '
              'line with no exact tag names every listed number, so first offer the operator the line with the '
              'tag naming the person\'s number; for each listed key, read tools/private-mode/numbers/<key>.md; '
              'no page was read' % (': ' + ', '.join(left) if left else ''))
        return EXIT_INVALID_INVOCATION
    missing = [k for k in keys if SCHEMES[k].get('needs_known') and k not in a.known]
    if missing:
        print('ABORT (invalid invocation): this number holds no date, so masking searches the person\'s own '
              'number, and none is recorded for %s; read tools/private-mode/numbers/<key>.md (*When a run is '
              'refused for this number*) and follow it; the pages wait'
              % ', '.join(missing))
        return EXIT_INVALID_INVOCATION

    sliding = [k for k in keys if SCHEMES[k]['window'] == 'sliding']
    a.prefix = SCHEMES[sliding[0]]['dob_prefix'](a.dob) if sliding else None  # validated safe above
    if a.lang is None:
        a.lang = '+'.join(run_langs(keys, None, id_schemes.load()))   # validated present above
    if 'label' in a.rules and not a.label_token and not any(SCHEMES[k]['labels'] for k in keys):
        print('note: label rule enabled but no --label-token given -> label rule inert')

    # A run-state error (run-scoped directory collision, or an unexpected makedirs OSError) must
    # exit with the DOCUMENTED code 65 and a sanitized line — never escape as an uncaught
    # traceback (Python exit 1) that both contradicts the contract and could print a path. The
    # exception message is deliberately NOT interpolated: category only, no filename/argv.
    try:
        results, run_id, exit_code, run_result = run_pipeline(a)
    except (RuntimeError, OSError):
        print('ABORT (run-state error): could not establish a fresh run-scoped working area '
              '(directory collision or filesystem error) — nothing was processed')
        return EXIT_STATE_ERROR

    # run-level state mirrors the result honestly: an ERROR run is FAILED, never presented as
    # awaiting the operator (HOLD runs DO await the operator — that is what a hold is for).
    if run_id is None:
        run_state = 'FAILED_EMPTY_INPUT'
    elif run_result == 'ERROR':
        run_state = 'FAILED'
    else:
        run_state = 'AWAITING_OPERATOR'
    run_log = dict(schema_version=SCHEMA_VERSION, kind='run-log', tool=TOOL_NAME,
                   tool_version=TOOL_VERSION, run_id=run_id, created_utc=_utcnow(),
                   args=_sanitized_args(a), documents=results, run_result=run_result,
                   exit_code=exit_code, state=run_state)
    # The run-log write (fsync/replace, disk-full, etc.) is INSIDE the sanitized exit boundary
    # (HO-09 item 7): a failure here — after documents may already have been promoted — must map to
    # the documented exit 65 with a category-only line, never a traceback/path leak or exit 1.
    try:
        _atomic_write_json(a.log, run_log)
    except OSError:
        print('ABORT (run-state error): could not durably write the run log '
              '(filesystem error) — any promoted documents remain at --redacted, unlogged')
        return EXIT_STATE_ERROR

    if run_id is None:
        print('ABORT: --inbox contains 0 PDF(s) — empty input is an error, not a successful run')
        return exit_code

    print(f'run_id={run_id}  PDFs processed: {len(results)}  result={run_result}')
    for r in results:
        pages = r.get('pages', [])
        tot = sum(p.get('n_masked', 0) for p in pages)
        allflags = sorted({fl for p in pages for fl in p.get('flags', [])})
        rot = ','.join(str(p['rotated']) for p in pages if p.get('rotated')) or '-'
        print(f"  {r['doc'][:32]:32s}  pages={r.get('n_pages', 0):2d}  masked={tot:2d}"
              f"  rot={rot}  flags={allflags if allflags else '-'}  {r.get('error') or ''}")
    if a.covered_by_hand:
        print('note: covered by hand (ADR-0076): this run looked for no number that is not on the list; '
              'the operator checks on every page that their covering hides it')
    if run_result == 'CLEAN':
        print('STATE: AWAITING_OPERATOR (clean local processing). NEXT: operator eyeballs every '
              'masked raster, then runs approve_redaction.py before ANY model/vision pass.')
    elif run_result == 'HOLD':
        print('STATE: AWAITING_OPERATOR / HOLD — one or more pages carry a fail-closed flag. '
              'Resolve or explicitly accept each flag at the operator gate before approving.')
    else:
        print('STATE: FAILED — one or more documents/pages hit a processing error; the affected '
              'page(s) are NOT in --redacted (nothing unverified was published). Investigate and rerun.')
    return exit_code

if __name__ == '__main__':
    sys.exit(main())
