#!/usr/bin/env python3
"""
Private mode (ADR-0029, ADR-0075) — a person's identity file: the details kept from the AI service
besides the designated number. STDLIB ONLY.

For a private-mode person, the operator chooses at setup which further details to keep from the AI
API: names of the patient, relatives and contacts; the date of birth; ID and document numbers;
addresses, phones, e-mails; case, visit and order numbers. They live in one local-only file in the
person's folder (IDENTITY_NAME), and sessions write placeholders instead. The file is the one truth
about what is kept: a class with values is kept, and no file means nothing besides the number. This
command writes the file from a form the operator fills in an editor, or from their own terminal
without echo, and is the one reader of it besides the other local tools (the residue guard, the
handout renderer, masking). The read guard refuses the file and the form to every session by name.

It never prints a kept value: only counts, reasons and the handle, plus the one transparent
exemption, the age with its reference date (operator, 2026-09-30).

  identity.py [--root DIR] form <handle> --keep CLASS,… [--no-open]   writes the form, slots only
  identity.py [--root DIR] form <handle> --read-number PDF [--page N] [--no-open]
                                                       reads the person's own number beside its label
                                                       on one PDF page into the form, with a picture
  identity.py [--root DIR] take-form <handle>          the filled form -> the identity file, then swap
  identity.py [--root DIR] discard-form <handle>       deletes a waiting form unread
  identity.py [--root DIR] set <handle> [<class>]      the operator, at their own terminal
  identity.py [--root DIR] age <handle>                today's age; no other reference date
  identity.py [--root DIR] status <handle>             what is kept, as counts
  identity.py [--root DIR] swap <handle>               kept values in the working record -> placeholders
  identity.py [--root DIR] scan                        the residue guard (L10, control C2), category only

`form` and `set` need the private-mode marker on the profile first. Each value carries the date it
was recorded: the residue guard looks for it in the working record always, elsewhere only in text
dated on or after that day. The designated identifier is never recorded here: a value holding a run
in its shape — the shape guard L10 reds, from the schemes the profile names (ADR-0062) — is refused,
so a phone or a case number is typed with its spaces. One exception (ADR-0074): a number that holds
no date, which masking cannot work out, is kept under `numbers`, undated, once the tool has read it
beside its label on a page, the operator has checked it in the form against a picture of that spot,
and the tool has found it on that page again.

Exit: 0 done · 1 `scan` found residue · 2 refused or not possible (the reason on stderr, category
only) · 64 invalid invocation.
"""
import argparse
import datetime
import getpass
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import id_schemes  # noqa: E402  the number list, beside this file

MARK = '⟨never-API⟩'
IDENTITY_NAME = '.never-api-identity.json'
FORM_NAME = 'fill-in-form' + IDENTITY_NAME   # plain text; the name's end puts it under the read guard's by-name rule
PICTURE_NAME = 'number-picture.never-api-identity.png'   # the spot a number was read from; the same rule covers it
SCHEMA = 'tabularium.never-api-identity'
VERSION = 2                    # 2: each value carries the date it was recorded (ADR-0075)
MAX_BYTES = 64 * 1024
MAX_VALUE = 200
MAX_VALUES = 50

CONTROL = re.compile(r'[\x00-\x1f\x7f]')

# class -> the prompt's plain words. Order is the order `set` asks in.
CLASSES = {
    'patient_names': "the person's names (a maiden or former name is a second entry)",
    'dob': 'date of birth',
    'other_names': "relatives' and contacts' names",
    'id_numbers': 'ID and document numbers other than the designated identifier',
    'addresses': 'addresses (street with its number, as documents print it)',
    'phones': 'phone numbers',
    'emails': 'e-mail addresses',
    'case_numbers': 'case, visit and order numbers',
}
NAME_CLASSES = ('patient_names', 'other_names')

EXIT_OK, EXIT_FOUND, EXIT_REFUSED, EXIT_USAGE = 0, 1, 2, 64


class Refused(Exception):
    """A refusal whose message is category only — never a value."""


# ---- dates and the marker ------------------------------------------------------------------------

def iso_date(text):
    try:
        return datetime.date.fromisoformat(text) if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', text) else None
    except ValueError:
        return None


def marked(profile_text):
    """Does the profile carry the private-mode marker? Kept details stand only beside it: the marker
    is what makes the read guard protect the person's folder whole."""
    return MARK in profile_text


# ---- paths --------------------------------------------------------------------------------------

def person_dir(root, handle):
    if not handle or handle in ('.', '..') or '/' in handle or '\\' in handle or CONTROL.search(handle):
        raise Refused('not a person handle')
    d = os.path.join(root, 'patients', handle)
    if os.path.islink(d) or not os.path.isdir(d):
        raise Refused('no person folder %s under patients/ (or it is a link)' % handle)
    return d


def read_profile(pdir, errors='strict', raw=False):
    """The profile's text; its bytes with raw=True (how the number tag is read, as L10 reads it)."""
    p = os.path.join(pdir, 'profile.md')
    if os.path.islink(p) or not os.path.isfile(p):
        raise Refused('the profile is missing, a link or not a regular file')
    try:
        if raw:
            with open(p, 'rb') as fh:
                return fh.read()
        with open(p, encoding='utf-8', errors=errors) as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        raise Refused('the profile cannot be read')


# ---- the identity file --------------------------------------------------------------------------

def empty():
    return {'schema': SCHEMA, 'version': VERSION, 'classes': {c: [] for c in CLASSES}}


def clean(value):
    return ' '.join(unicodedata.normalize('NFC', value).split())


def check_value(cls, value, shape):
    """Return the reason a value is refused, or None. Category only. `shape` is the person's designated
    number's residue shape (`id_shape`)."""
    if not value:
        return 'empty'
    if len(value) > MAX_VALUE or CONTROL.search(value):
        return 'too long or holds control characters'
    if shape.search(value):
        return ('it has the shape of the designated identifier, which is never recorded; '
                'type a phone or case number with its spaces')
    if cls == 'dob':
        d = iso_date(value)
        if d is None or d.year < 1880 or d > datetime.date.today():
            return 'not a real past date in the form YYYY-MM-DD'
    if cls == 'emails' and ('@' not in value or ' ' in value):
        return 'not an e-mail address'
    return None


def values(data, cls):
    """The recorded values of one class, without their dates."""
    return [e['value'] for e in data['classes'][cls]]


def kept(data):
    """The classes kept from the AI service: those with at least one value."""
    return [c for c in CLASSES if data['classes'][c]]


def add(data, cls, new, since):
    """Append the values not yet recorded, each dated `since`; a value already there keeps its date."""
    have = values(data, cls)
    for v in new:
        if v not in have:
            data['classes'][cls].append({'value': v, 'since': since.isoformat()})
            have.append(v)


def validate(data, shape):
    """Strict shape check of a loaded identity file. Raises Refused (category only)."""
    if not isinstance(data, dict) or set(data) - {'numbers'} != {'schema', 'version', 'classes'}:
        raise Refused('the identity file has an unexpected shape')
    numbers = data.get('numbers', {})          # the designated number with no date inside (ADR-0074): undated
    if not isinstance(numbers, dict) or len(numbers) > 5 or not all(
            isinstance(k, str) and id_schemes.KEY_RE.fullmatch(k) and isinstance(v, str)
            and re.fullmatch(r'[0-9]{9,15}', v) for k, v in numbers.items()):
        raise Refused('the identity file holds an invalid national number entry')
    if data['schema'] == SCHEMA and data['version'] == 1:
        raise Refused('the identity file is in the old format, from before each detail carried the date '
                      'it was recorded; the operator deletes it and fills in the form again')
    if data['schema'] != SCHEMA or data['version'] != VERSION:
        raise Refused('the identity file has an unknown schema or version')
    classes = data['classes']
    if not isinstance(classes, dict) or set(classes) != set(CLASSES):
        raise Refused('the identity file has missing or unknown classes')
    for cls, entries in classes.items():
        if not isinstance(entries, list) or len(entries) > MAX_VALUES:
            raise Refused('the identity file class %s is not a list of values' % cls)
        if cls == 'dob' and len(entries) > 1:
            raise Refused('the identity file holds more than one date of birth')
        for e in entries:
            if not isinstance(e, dict) or set(e) != {'value', 'since'} or not isinstance(e['since'], str) \
                    or iso_date(e['since']) is None or iso_date(e['since']) > datetime.date.today():
                raise Refused('the identity file class %s holds a value without a real recording date' % cls)
            v = e['value']
            if cls in NAME_CLASSES:
                ok = isinstance(v, dict) and set(v) == {'given', 'family'}
                parts = [v['given'], v['family']] if ok else [None]
            else:
                parts = [v]
            for part in parts:
                if not isinstance(part, str) or part != clean(part) or check_value(cls, part, shape) is not None:
                    raise Refused('the identity file class %s holds an invalid value' % cls)


def id_shape(pdir):
    """The residue shape of the designated number(s) the person's profile names."""
    try:
        table = id_schemes.load()
        return id_schemes.residue_re(id_schemes.profile_schemes(read_profile(pdir, raw=True), table), table)
    except id_schemes.SchemeError as e:
        raise Refused(str(e))


def identity_path(pdir):
    return os.path.join(pdir, IDENTITY_NAME)


def _read_bounded(path, what):
    """The bytes of a regular file under the size bound, or None when there is none. Never follows a link."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    except FileNotFoundError:
        return None
    except OSError:
        raise Refused('the %s is a link or cannot be opened' % what)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_BYTES:
            raise Refused('the %s is not a regular file of a sane size' % what)
        raw = b''
        while len(raw) <= MAX_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            raw += chunk
    finally:
        os.close(fd)
    if len(raw) > MAX_BYTES:
        raise Refused('the %s is not a regular file of a sane size' % what)
    return raw


def load(pdir):
    """The validated identity data, or None when there is no file."""
    raw = _read_bounded(identity_path(pdir), 'identity file')
    if raw is None:
        return None
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise Refused('the identity file is not valid JSON')
    validate(data, id_shape(pdir))
    return data


def write(pdir, data):
    """Owner-only, atomic. The temporary file's name ends in the identity file's name, so the read
    guard's by-name rule covers a leftover from an interrupted write too."""
    validate(data, id_shape(pdir))
    body = (json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + '\n').encode('utf-8')
    if len(body) > MAX_BYTES:                    # never replace a usable file with one load() refuses
        raise Refused('the identity file would exceed its size limit; nothing changed')
    tmp = os.path.join(pdir, '.tmp-%s%s' % (secrets.token_hex(4), IDENTITY_NAME))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        final = identity_path(pdir)
        if os.path.islink(final) or (os.path.lexists(final) and not os.path.isfile(final)):
            raise Refused('the identity file is a link or not a regular file; not replaced')
        os.replace(tmp, final)
        dfd = os.open(pdir, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


# ---- age -----------------------------------------------------------------------------------------

def _plural(n, word):
    return '%d %s%s' % (n, word, '' if n == 1 else 's')


def anniversary(dob, months):
    """The date `months` whole months after `dob`, its day clamped to the month's end."""
    ay, am = divmod(dob.month - 1 + months, 12)
    year, month = dob.year + ay, am + 1
    last = (datetime.date(year + (month == 12), month % 12 + 1, 1) - datetime.timedelta(days=1)).day
    return datetime.date(year, month, min(dob.day, last))


def age_parts(dob, on):
    """(whole months, days since the last monthly anniversary)."""
    if on < dob:
        raise Refused('the reference date is before the date of birth')
    months = (on.year - dob.year) * 12 + (on.month - dob.month)
    while months > 0 and anniversary(dob, months) > on:
        months -= 1
    return months, (on - anniversary(dob, months)).days


def age_text(dob, on):
    """Age at the precision care needs: years and months from two years; months and whole weeks
    under two; days in the first month, where care needs them. No finer than that: a reference date
    with days would give the date of birth away, and with it the identifier's date-derived prefix."""
    months, days = age_parts(dob, on)
    if months >= 24:
        return '%s %s' % (_plural(months // 12, 'year'), _plural(months % 12, 'month'))
    if months == 0:
        return _plural(days, 'day')
    return '%s %s' % (_plural(months, 'month'), _plural(days // 7, 'week'))


# ---- kept values in text: the residue guard's matcher and the swap (control C2) ------------------

PLACEHOLDER_OPEN = '⟨withheld:'
# the sign the swap writes on the private-mode line while any detail is kept (ADR-0075): every session
# reads the profile, so it learns details are kept even when none of them stands in the profile
KEPT_SIGN = '⟨withheld:details-kept⟩'
PLACEHOLDER = {
    'patient_names': '⟨withheld:patient-name⟩',
    'dob': '⟨withheld:date-of-birth⟩',
    'other_names': '⟨withheld:other-name⟩',
    'id_numbers': '⟨withheld:id-number⟩',
    'addresses': '⟨withheld:address⟩',
    'phones': '⟨withheld:phone⟩',
    'emails': '⟨withheld:email⟩',
    'case_numbers': '⟨withheld:case-number⟩',
    'national_number': '⟨withheld:national-number⟩',
}
LABEL = {
    'patient_names': "the person's name", 'dob': 'the date of birth',
    'other_names': "a relative's or contact's name", 'id_numbers': 'an ID or document number',
    'addresses': 'an address', 'phones': 'a phone number', 'emails': 'an e-mail address',
    'case_numbers': 'a case, visit or order number',
    'national_number': 'the national ID number',
}
SCAN_CLASSES = tuple(CLASSES) + ('national_number',)   # what the residue guard looks for
WAIVER = re.compile(r'⟨not-an-id: verified [0-9]{4}-[0-9]{2}-[0-9]{2}⟩')   # guard L10's dated waiver
MIN_SIGNIFICANT = 5          # a shorter number or string is too common to be looked for alone
DASHES = '‐‑‒–—―−'                      # as PDFs and OCR print them
DIGIT_SEP = r'[\s\-%s./()]{0,2}' % DASHES
DATE_SEP = r'[\s\-%s./]{1,2}' % DASHES
CHUNK_SEP = r'[\W_]{0,6}'                     # spaces, punctuation, Markdown emphasis, a table bar
BEFORE, AFTER = r'(?<![^\W_])', r'(?![^\W_])'  # letters and digits bound a value; `_x_` is Markdown
FOLD = {'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'ø': 'o', 'Ø': 'O', 'ı': 'i', 'ß': 's'}
# never a kept value: the private-mode marker and the placeholders themselves
PROTECTED = re.compile(r'⟨never-API⟩|⟨withheld:[a-z-]+⟩')
# an integrity key — a run of 32 or more hex digits, such as the ledger's person record ID or a digest:
# a match lying strictly inside one (a phone's digits) is dropped; a value that is or contains a run
# is still found
HEXRUN = re.compile(r'(?<![0-9A-Fa-f])[0-9A-Fa-f]{32,}(?![0-9A-Fa-f])')


def fold(text):
    """Accents off, one character for one, so a span found in the folded text is the same span in
    the original: 'Exämpla', 'Exampla' and a decomposed spelling read alike (after NFC)."""
    out = []
    for ch in text:
        if ch in FOLD:
            out.append(FOLD[ch])
            continue
        base = unicodedata.normalize('NFKD', ch)
        out.append(base[0] if len(base) > 1 and all(unicodedata.combining(c) for c in base[1:]) else ch)
    return ''.join(out)


def _chunks(value):
    parts = re.findall(r'[^\W_]+', fold(value))
    return BEFORE + CHUNK_SEP.join(re.escape(p) for p in parts) + AFTER


def _digits(digits, plus=False, letters=True):
    # an ID or case number is bounded by letters too, so `12345` never matches inside an ID such as
    # `a12345bc…`; a phone only by digits, so `tel555010101` is still found
    before, after = (BEFORE, AFTER) if letters else (r'(?<![0-9])', r'(?![0-9])')
    return before + (r'\+?' if plus else '') + DIGIT_SEP.join(digits) + after


def _dob(d):
    """The date of birth in its numeric printed forms: day-month-year (four- or two-digit year),
    year-month-day, month-day-year, leading zeros optional, any date separator; compact too."""
    day = ('0?%d' % d.day) if d.day < 10 else '%d' % d.day
    mon = ('0?%d' % d.month) if d.month < 10 else '%d' % d.month
    y4, y2, s = '%04d' % d.year, '%02d' % (d.year % 100), DATE_SEP
    separated = [day + s + mon + s + y4, y4 + s + mon + s + day, mon + s + day + s + y4, day + s + mon + s + y2]
    compact = ['%s%02d%02d' % (y4, d.month, d.day), '%02d%02d%s' % (d.day, d.month, y4)]
    # a separated date is bounded by digits only (`23.02.1901r.`, `1901-02-23T00:00`); a compact one,
    # all digits, by letters too, so it never matches inside an ID
    return (r'(?<![0-9])(?:' + '|'.join(separated) + r')(?![0-9])|'
            + BEFORE + '(?:' + '|'.join(compact) + ')' + AFTER)


def patterns(data, upto=None):
    """(class, compiled pattern) pairs, longest first, for every kept value recorded on or before
    `upto` (every value when None) — whole values only, so a shared first name or a common street
    never fires. Values too short to look for are left out."""
    out = []
    for cls in CLASSES:
        for e in data['classes'][cls]:
            if upto is not None and iso_date(e['since']) > upto:
                continue
            v = e['value']
            if cls in NAME_CLASSES:
                given, family = v['given'].split(), v['family']
                for g in {' '.join(given), given[0]}:
                    out += [(cls, _chunks(g + ' ' + family)), (cls, _chunks(family + ' ' + g))]
            elif cls == 'dob':
                out.append((cls, _dob(iso_date(v))))
            elif cls == 'emails':
                out.append((cls, BEFORE + r'(?<!\.)' + re.escape(fold(v)) + AFTER))
            elif re.fullmatch(r'[0-9\s\-./()+]+', v):          # phone, or an all-digit number
                digits = re.sub(r'[^0-9]', '', v)
                if len(digits) >= MIN_SIGNIFICANT:
                    phone = cls == 'phones'
                    out.append((cls, _digits(digits, plus=v.lstrip().startswith('+'), letters=not phone)))
                    if phone and len(digits) > 9:
                        out.append((cls, _digits(digits[-9:], letters=False)))   # without its country code
            elif len(re.sub(r'[\W_]', '', v)) >= MIN_SIGNIFICANT:
                out.append((cls, _chunks(v)))
    for digits in data.get('numbers', {}).values():    # the designated number: kept always, so no date filter
        out.append(('national_number', _digits(digits)))
    uniq = {(c, p) for c, p in out}
    return [(c, re.compile(p, re.I)) for c, p in sorted(uniq, key=lambda cp: (-len(cp[1]), cp))]


def _prepared(line):
    """(the line in NFC, its folded twin with the protected tags blanked) — same length, same spans."""
    nfc = unicodedata.normalize('NFC', line)
    return nfc, fold(PROTECTED.sub(lambda m: ' ' * len(m.group(0)), nfc))


REFERENCE_EXT = re.compile(r'\.(?:md|pdf|jpe?g|png|heic|tiff?|txt|json|docx?|odt|rtf|xlsx?|csv|eml|zip|gif|webp)'
                           r'(?:[#?]\S*)?$', re.I)
# a path into the record (from the token's start), or the date-named file convention; a slash alone is
# not one (23/02/1901, 12/3)
PATHISH = re.compile(r'^(?:\.\.?/)*(?:med|nmed|patients|_shared|sources|analysis|handouts)/|^\.\.?/'
                     r'|[0-9]{4}-[0-9]{2}-[0-9]{2}__')
TOKEN_STOP = set(' \t\r\n[]<>|"\'`')


def _spans(folded, pats):
    """Non-overlapping (start, end, class) spans: overlapping matches are merged into one span, named
    by the class of the longest of them, so no fragment of any value is left beside a placeholder (a
    date inside an ID, a name inside an e-mail, two names read across their comma in reverse order)."""
    runs = [m.span() for m in HEXRUN.finditer(folded)]
    found = sorted((m.start(), m.end(), cls) for cls, pat in pats for m in pat.finditer(folded)
                   if m.end() > m.start()
                   and not any(a <= m.start() and m.end() <= b and (a, b) != m.span() for a, b in runs))
    merged = []
    for s, e, cls in found:
        if merged and s < merged[-1][1]:
            ms, me, mcls, mlen = merged[-1]
            merged[-1] = (ms, max(me, e), cls if e - s > mlen else mcls, max(mlen, e - s))
        else:
            merged.append((s, e, cls, e - s))
    return [(s, e, cls) for s, e, cls, _ in merged]


def _link_ranges(line):
    """(start, end) of every inline Markdown link destination on the line, nested parentheses and
    `<…>` included (a reference definition's target is a path the token test below recognises)."""
    out, i = [], 0
    while True:
        i = line.find('](', i)
        if i < 0:
            return out
        start = j = i + 2
        if j < len(line) and line[j] == '<':
            k = line.find('>', j)
            j = len(line) if k < 0 else k
        else:
            depth = 1
            while j < len(line):
                c = line[j]
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if not depth:
                        break
                elif c in ' \t' and depth == 1:          # a title follows the destination
                    break
                j += 1
        out.append((start, j))
        i = j


def _in_reference(line, s, e, links=None):
    """Does the match sit inside a file name or a link target? Then replacing it would break the
    reference: the file must be renamed (an ownership-ledger rename) first."""
    if any(s < le and ls < e for ls, le in (_link_ranges(line) if links is None else links)):
        return True
    a, b = s, e
    while a > 0 and line[a - 1] not in TOKEN_STOP:
        a -= 1
    while b < len(line) and line[b] not in TOKEN_STOP:
        b += 1
    token = line[a:b].lstrip('(').rstrip(').,;:')
    return '@' not in token and bool(REFERENCE_EXT.search(token) or PATHISH.search(token))


def residue(text, pats):
    """{class: [lines holding one of its values, of which inside a file reference]}; lines carrying
    the dated waiver skipped."""
    hits = {}
    for line in text.splitlines():
        if WAIVER.search(line):
            continue
        folded = _prepared(line)[1]
        links, seen = _link_ranges(folded), {}
        for s, e, cls in _spans(folded, pats):
            seen[cls] = seen.get(cls, False) or _in_reference(folded, s, e, links)
        for cls, ref in seen.items():
            h = hits.setdefault(cls, [0, 0])
            h[0] += 1
            h[1] += ref
    return hits


def substitute(text, pats):
    """(the text with every withheld value replaced by its class's placeholder, counts per class,
    matches inside file references). Waived and untouched lines are kept byte for byte; a match
    inside a file reference is left as it is and counted, so the caller can refuse."""
    counts, refs, out = {}, 0, []
    for line in text.splitlines(keepends=True):
        if WAIVER.search(line):
            out.append(line)
            continue
        nfc, folded = _prepared(line)
        spans = _spans(folded, pats)
        if not spans:
            out.append(line)
            continue
        links = _link_ranges(folded)
        for s, e, cls in reversed(spans):
            if _in_reference(folded, s, e, links):
                refs += 1
                continue
            nfc = nfc[:s] + PLACEHOLDER[cls] + nfc[e:]
            counts[cls] = counts.get(cls, 0) + 1
        out.append(nfc)
    return ''.join(out), counts, refs


# ---- which files the residue guard reads for a person with kept details --------------------------

DATE_PREFIX = re.compile(r'^([0-9]{4}-[0-9]{2}-[0-9]{2})')
MIGRATION_SOURCE = 'legacy migration '       # how tools/person_ownership/migrate.py stamps its records
WORKING_RECORD = ('profile.md', 'medications.md')


def _path_date(rel):
    """The latest date the path is named with — the file's, or an enclosing folder's (an encounter unit)."""
    dates = [iso_date(m.group(1)) for m in (DATE_PREFIX.match(p) for p in rel.split('/')) if m]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else None


def _seal_date(full):
    """A sealed encounter unit's date — the timestamp of the one attestation in the file's folder,
    which the canonical Markdown and its fact-check sidecar share — or None when it is not sealed."""
    folder = os.path.dirname(full)
    try:
        atts = [n for n in os.listdir(folder) if n.endswith('.attest.json')]
    except OSError:
        return None
    att = os.path.join(folder, atts[0]) if len(atts) == 1 else None
    if att is None or os.path.islink(att) or not os.path.isfile(att):
        return None
    try:
        with open(att, encoding='utf-8') as fh:
            ts = json.load(fh)['timestamp']
        return iso_date(ts[:10]) if isinstance(ts, str) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _ledger_dates(pdir):
    """{person-folder-relative path: filing date, or None when undatable} for the Markdown the
    ownership ledger binds (a transcription, a Markdown source), by the review date of its chain's
    first record, so a rename keeps the original filing date — except a transcription written whole
    later (bound by `transcribe`, or re-made with a `rehash`), dated by that row. A record the one-time ledger
    migration wrote carries its migration day, not a filing date, and is left out; a new filing is
    unconfirmed by default too, so the ownership status does not tell them apart. Keys are NFC, as the
    ledger stores paths."""
    path = os.path.join(pdir, 'med', 'MANIFEST')
    if not os.path.lexists(path):
        return {}
    if os.path.islink(path) or not os.path.isfile(path):
        raise Refused('the ownership ledger is not a regular file; transcriptions cannot be dated')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools.person_ownership import schema
    try:
        with open(path, 'rb') as fh:
            records = [r for r in schema.parse_manifest_bytes(fh.read()) if isinstance(r, dict)]
    except (OSError, schema.ManifestError):
        raise Refused('the ownership ledger cannot be read; transcriptions cannot be dated')
    by_id = {r.get('record_id'): r for r in records}

    def layer(row):
        return sorted((d.get('derivative_relpath'), d.get('derivative_sha256'))
                      for d in (row.get('derivatives') or []) if isinstance(d, dict))

    out = {}
    for r in records:
        chain, seen = [r], set()
        while isinstance(chain[-1].get('supersedes'), str) and chain[-1]['supersedes'] in by_id \
                and chain[-1]['supersedes'] not in seen:
            seen.add(chain[-1]['supersedes'])
            chain.append(by_id[chain[-1]['supersedes']])
        root = chain[-1]
        migrated = str(root.get('identity_source', '')).startswith(MIGRATION_SOURCE)
        filed = iso_date(root['review_date']) if isinstance(root.get('review_date'), str) else None
        rels = [d.get('derivative_relpath') for d in (r.get('derivatives') or []) if isinstance(d, dict)]
        # a transcription written whole after its original was filed — bound late by `transcribe` or
        # re-made with a `rehash` (ADR-0037 §14) — is new text, dated by the latest such row and never
        # before the original's filing; an unreadable date leaves it in scope
        written = next((row for row, prev in zip(chain, chain[1:])
                        if row.get('supersede_reason') in ('transcribe', 'rehash')
                        and layer(row) != layer(prev)), None)
        if written is not None:
            day = iso_date(written['supersede_date']) if isinstance(written.get('supersede_date'), str) else None
            if not migrated:
                day = max(day, filed) if day is not None and filed is not None else None
            out.update((unicodedata.normalize('NFC', x), day) for x in rels
                       if isinstance(x, str) and x.endswith('.md'))
            rels = []
        if migrated:
            continue
        rels.append(r.get('source_relpath'))
        out.update((unicodedata.normalize('NFC', x), filed) for x in rels if isinstance(x, str) and x.endswith('.md'))
    return out


def _walk_error(err):
    raise Refused('a folder of a person with kept details cannot be listed — the residue scan is blinded')


def in_scope(pdir):
    """[(relpath, kind, date)] of the Markdown the residue guard reads for a person with kept details:
    the working record and an undatable transcription with date None (every value counts there); any
    other file with its date — a transcription by its filing date, a sealed handout by its seal,
    anything else by the latest date in its path, an undated file by when it was last written. A value
    counts in a dated file only if it was recorded on or before that date. `nmed/` never."""
    ledger = _ledger_dates(pdir)
    out = []
    for dirpath, dirnames, filenames in os.walk(pdir, onerror=_walk_error):
        rel_dir = os.path.relpath(dirpath, pdir)
        dirnames[:] = sorted(n for n in dirnames if not os.path.islink(os.path.join(dirpath, n))
                             and not (rel_dir == '.' and n == 'nmed'))
        for n in sorted(filenames):
            full = os.path.join(dirpath, n)
            if not n.endswith('.md') or os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = n if rel_dir == '.' else '/'.join(rel_dir.split(os.sep) + [n])
            if rel in WORKING_RECORD:
                out.append((rel, 'the %s' % rel[:-3].replace('medications', 'medication list'), None))
                continue
            key = unicodedata.normalize('NFC', rel)       # macOS may hand back a decomposed name
            if key in ledger:
                when, kind = ledger[key], 'a transcription filed after that detail was recorded'
            elif rel.startswith('med/handouts/') and _seal_date(full) is not None:
                when, kind = _seal_date(full), 'a handout sealed after that detail was recorded'
            elif _path_date(rel) is not None:
                # the later of its name's date and its last write: a note named for an old letter but
                # written today is today's text (operator, 2026-11-09)
                when = max(_path_date(rel), datetime.date.fromtimestamp(os.stat(full).st_mtime))
                kind = 'a text file dated or written after that detail was recorded'
            else:
                when = datetime.date.fromtimestamp(os.stat(full).st_mtime)
                kind = 'an undated text file written after that detail was recorded'
            out.append((rel, kind, when))
    return out


def scan_person(pdir, data, who):
    """Category-only findings for one person with kept details; never a value, a path or a line."""
    cache, findings = {}, []
    for rel, kind, when in in_scope(pdir):
        if when not in cache:
            cache[when] = patterns(data, when)
        pats = cache[when]
        if not pats:
            continue
        try:
            with open(os.path.join(pdir, rel), encoding='utf-8', errors='replace') as fh:
                hits = residue(fh.read(), pats)
        except OSError:
            findings.append('%s: a text file cannot be read — the residue scan is blinded' % who)
            continue
        for cls in SCAN_CLASSES:
            if cls in hits:
                n, refs = hits[cls]
                findings.append('%s: kept detail (%s) in %s, %d line%s — replace it with %s%s%s'
                                % (who, LABEL[cls], kind, n, '' if n == 1 else 's', PLACEHOLDER[cls],
                                   '; a verified namesake line takes the dated not-an-id waiver'
                                   if cls in NAME_CLASSES else '',
                                   '; %d inside a file name or link: rename that file through the '
                                   'ownership ledger first, then update the reference and run swap' % refs
                                   if refs else ''))
    return findings


def _holds_placeholder(pdir):
    """Does the profile or the medication list carry a kept-detail placeholder (the sign included)?"""
    for name in WORKING_RECORD:
        path = os.path.join(pdir, name)
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8', errors='replace') as fh:
            if PLACEHOLDER_OPEN in fh.read():
                return True
    return False


LOST_FILE = ('a profile or medication list holds kept-detail placeholders but the person\'s identity file '
             'is missing (locator withheld) — restore it from the latest snapshot; for a new person whose '
             'form is not taken in yet, run take-form. The residue scan cannot run without it')


def scan_tree(root):
    """Category-only findings over every person folder under root/patients. A person is named by
    their position among the persons with kept details, never by handle (locators are withheld)."""
    pdir_root = os.path.join(root, 'patients')
    findings = []
    try:
        names = sorted(os.listdir(pdir_root))
    except FileNotFoundError:
        return findings
    n = 0
    for name in names:
        pdir = os.path.join(pdir_root, name)
        prof = os.path.join(pdir, 'profile.md')
        if os.path.islink(pdir) or not os.path.isdir(pdir):
            continue
        try:
            if os.path.islink(prof) or not os.path.isfile(prof):
                if _holds_placeholder(pdir):          # guard L10 reds a marked tree with no profile
                    findings.append('a person folder without a profile holds kept-detail placeholders '
                                    '(locator withheld) — restore the profile from the latest snapshot')
                continue
            if not os.path.lexists(identity_path(pdir)):
                if _holds_placeholder(pdir):
                    findings.append(LOST_FILE)
                continue
            with open(prof, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
            if not marked(text):
                findings.append('an identity file exists but its profile carries no private-mode marker '
                                '(locator withheld) — restore the marker, or, if the operator ended '
                                'private mode for this person, they remove the file')
                continue
            data = load(pdir)
            n += 1
            who = 'person with kept details %d (locator withheld)' % n
            if kept(data) and KEPT_SIGN not in text:
                findings.append('%s: the private-mode line lacks the kept-details sign %s — run swap, '
                                'which writes it' % (who, KEPT_SIGN))
            elif not kept(data) and KEPT_SIGN in text:
                findings.append('%s: the kept-details sign is on the profile but the identity file keeps '
                                'nothing — remove the sign from the private-mode line' % who)
            findings += scan_person(pdir, data, who)
        except Refused as e:
            findings.append('private mode (locator withheld): %s' % e)
        except OSError:
            findings.append('a profile cannot be read — the kept-details scan is blinded')
    return findings


def _replace_text(path, text):
    """Atomic, same mode, line endings kept."""
    st = os.stat(path)
    tmp = os.path.join(os.path.dirname(path), '.%s.%s.tmp' % (os.path.basename(path), secrets.token_hex(4)))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def _with_sign(text):
    """The profile with the kept-details sign appended to the private-mode marker's line, once."""
    if KEPT_SIGN in text:
        return text
    out, done = [], False
    for line in text.splitlines(keepends=True):
        if not done and MARK in line:
            body = line.rstrip('\r\n')
            line, done = body + ' · ' + KEPT_SIGN + line[len(body):], True
        out.append(line)
    if not done:
        raise Refused('the profile carries no private-mode marker line for the kept-details sign; nothing changed')
    return ''.join(out)


def plan_swap(pdir, data):
    """[(name, path, old text, new text, counts)] for the working record, and the number of file
    references that name a kept value. Pure: nothing is written."""
    pats = patterns(data)
    plans, refs = [], 0
    for name in WORKING_RECORD:
        path = os.path.join(pdir, name)
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8', newline='') as fh:
                text = fh.read()
        except UnicodeDecodeError:
            raise Refused('%s is not UTF-8 text; nothing changed' % name)
        new, counts, r = substitute(text, pats)
        if name == 'profile.md' and kept(data):
            new = _with_sign(new)
        refs += r
        plans.append((name, path, text, new, counts))
    return plans, refs


REFS_REFUSAL = ('%d file reference%s in the working record name a kept detail; rename those files '
                'through the ownership ledger and update the references, then run this again')


def apply_swap(plans, tell):
    for name, path, text, new, counts in plans:
        if new != text:
            try:
                _replace_text(path, new)
            except OSError as e:
                raise Refused('%s could not be written (%s); any file named before it here was swapped — '
                              'run swap again' % (name, type(e).__name__))
        tell('%s: %s' % (name, ' · '.join('%s %d' % (c, counts[c]) for c in SCAN_CLASSES if c in counts)
                         or 'nothing to replace'))


def swap(pdir, data, tell):
    """Replace the kept values in the working record (profile and medications) with their
    placeholders, and put the kept-details sign on the private-mode line. Runs inside a care edit
    session, after its snapshot; history stays as it is. A file reference that names a kept value
    refuses the whole swap, changing nothing, since replacing it would break the reference; a rerun
    completes an interrupted swap."""
    plans, refs = plan_swap(pdir, data)
    if refs:
        raise Refused((REFS_REFUSAL % (refs, '' if refs == 1 else 's')) + ' (nothing changed)')
    apply_swap(plans, tell)


def cmd_swap(root, handle, tell):
    pdir = person_dir(root, handle)
    if not marked(read_profile(pdir)):
        raise Refused('%s is not in private mode' % handle)
    data = load(pdir)
    if data is None:
        raise Refused('nothing besides the number is kept for %s; there is nothing to swap' % handle)
    swap(pdir, data, tell)


# ---- commands ------------------------------------------------------------------------------------

def _ask_one(label, ask, tell):
    """One value typed twice without echo; empty ends the class. None = finished."""
    for _ in range(3):
        value = clean(ask('  %s (Enter when done): ' % label))
        if not value:
            return None
        if clean(ask('  again: ')) == value:
            return value
        tell('  the two entries differ; once more')
    raise Refused('three mismatched entries; nothing changed for this class')


def collect(cls, ask, tell, shape):
    values = []
    limit = 1 if cls == 'dob' else MAX_VALUES
    while len(values) < limit:
        if cls in NAME_CLASSES:
            given = _ask_one('given name(s)', ask, tell)
            if given is None:
                break
            family = _ask_one('family name', ask, tell)
            if family is None:
                tell('  a name needs its family name; entry dropped')
                continue
            value, parts = {'given': given, 'family': family}, [given, family]
        else:
            value = _ask_one('YYYY-MM-DD' if cls == 'dob' else 'value', ask, tell)
            if value is None:
                break
            parts = [value]
        reasons = [r for r in (check_value(cls, p, shape) for p in parts) if r]
        if reasons:
            tell('  refused: %s' % reasons[0])
            continue
        values.append(value)
    return values


def counts(data):
    return ' · '.join(['%s %d' % (c, len(data['classes'][c])) for c in CLASSES]
                      + (['national numbers %d' % len(data['numbers'])] if data.get('numbers') else []))


def check_handle(data, handle):
    """Refuse a kept name the handle itself spells: every path and handout carries the handle, so the
    name could never be kept, and every mention of the folder would read as a leftover."""
    folded = fold(handle)
    if any(pat.search(folded) for cls, pat in patterns(data) if cls in NAME_CLASSES):
        raise Refused('the person\'s handle spells a name the form would keep, so that name cannot be kept '
                      'from the AI for them (every path names it); leave it out and run this again; '
                      'nothing changed')


def need_marker(pdir, handle):
    # the marker makes the read guard protect the person's folder whole; without it a folder search
    # would reach the file
    if not marked(read_profile(pdir)):
        raise Refused('%s is not in private mode; the private-mode marker goes on the profile first' % handle)


def cmd_set(root, handle, only, ask, confirm, tell):
    pdir = person_dir(root, handle)
    need_marker(pdir, handle)
    data = load(pdir) or empty()
    today = datetime.date.today()
    for cls in ([only] if only else list(CLASSES)):
        have = len(data['classes'][cls])
        tell('%s — %s' % (cls, CLASSES[cls]))
        if have and not confirm('  %d recorded; replace them? [y/N] ' % have):
            continue
        old = {json.dumps(e['value'], sort_keys=True): e['since'] for e in data['classes'][cls]}
        data['classes'][cls] = [{'value': v, 'since': old.get(json.dumps(v, sort_keys=True), today.isoformat())}
                                for v in collect(cls, ask, tell, id_shape(pdir))]
    check_handle(data, handle)
    write(pdir, data)
    tell('written for %s: %s' % (handle, counts(data)))
    tell('in a care edit session, swap %s replaces them in the profile and medication list' % handle)


# ---- the form: a session writes the structure, the operator the values, in an editor ------------
# Line-based and free of quotes, so an editor's smart quotes and an apostrophe in a name change nothing.

NAME_SLOT, TEXT_SLOT, DATE_SLOT = 'Xxxx / Xxxx', 'Xxxx', '00.00.0000'
NUMBER_SLOT, PHONE_SLOT, EMAIL_SLOT = '000000', '000 000 000', 'xxxx@xxxx'
DOB_AGAIN = 'dob again'
FORM_LINES = (                 # label, class, slot, how many lines the blank form offers
    ('name', 'patient_names', NAME_SLOT, 1),
    ('former name', 'patient_names', NAME_SLOT, 1),
    ('date of birth', 'dob', DATE_SLOT, 1),
    ('date of birth again', DOB_AGAIN, DATE_SLOT, 1),   # typed twice, as `set` asks: masking keys on it
    ('relative or contact', 'other_names', NAME_SLOT, 3),
    ('other ID or document number', 'id_numbers', NUMBER_SLOT, 1),
    ('address', 'addresses', TEXT_SLOT, 2),
    ('phone', 'phones', PHONE_SLOT, 2),
    ('e-mail', 'emails', EMAIL_SLOT, 1),
    ('case, visit or order number', 'case_numbers', NUMBER_SLOT, 2),
)
FORM_HEAD = """\
# Private details for %s. This form stays on this computer. No session can read it.
#
# After each colon, replace the slot with the real detail, as documents print it.
# A line that does not apply: leave it as it is. Need another of a kind: copy the whole line.
# A name: given name or names, a slash, then the family name.
# The date of birth: day.month.year, the same on both of its lines.
# Numbers: keep their spaces as printed. Never the national ID number: it is never typed here.
# Keep this as plain text and make no copy of it. Use this editor, not one with AI features.
# Then save, close the window and tell the session you are done. It deletes this form.

"""


def form_path(pdir):
    return os.path.join(pdir, FORM_NAME)


def form_text(handle, keep):
    """The blank form, holding only the lines of the classes the operator chose to keep."""
    keep = set(keep) | ({DOB_AGAIN} if 'dob' in keep else set())
    lines = ['%s: %s\n' % (label, slot) for label, cls, slot, n in FORM_LINES if cls in keep for _ in range(n)]
    return FORM_HEAD % handle + ''.join(lines)


def parse_keep(text):
    """The classes named in a comma-separated --keep list, in the form's order."""
    names = [n.strip() for n in text.split(',') if n.strip()]
    unknown = [n for n in names if n not in CLASSES]
    if unknown or not names:
        raise Refused('--keep takes a comma-separated list of: %s' % ', '.join(CLASSES))
    return [c for c in CLASSES if c in names]


def _form_value(cls, value, n, shape):
    """One filled-in value in the identity file's shape. Refusals name the line, never its content."""
    if cls in NAME_CLASSES:
        parts = [clean(p) for p in value.split('/')]
        if len(parts) != 2 or not all(parts) or TEXT_SLOT in parts:
            raise Refused('form line %d: a name is given name or names, a slash, then the family name' % n)
        value, checked = {'given': parts[0], 'family': parts[1]}, parts
    elif cls in ('dob', DOB_AGAIN):
        # no slash: 03/04/1901 reads as two different dates in different countries
        m = re.fullmatch(r'([0-9]{1,2})[.\-]([0-9]{1,2})[.\-]([0-9]{4})', value)
        checked = [value if not m else '%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1)))]
        value = checked[0]
    else:
        checked = [value]
    for part in checked:
        reason = check_value('dob' if cls == DOB_AGAIN else cls, part, shape)
        if reason:
            raise Refused('form line %d: %s' % (n, reason if cls in CLASSES and cls != 'dob'
                                                  else 'not a real past date, day.month.year'))
    return value


NUMBER_LINE, SOURCE_LINE = 'national number', 'read from'   # only a form the tool read a number into


def _number_line(value, n):
    digits = re.sub(r'[\s\-%s.]' % DASHES, '', value)
    if not re.fullmatch(r'[0-9]{9,15}', digits):
        raise Refused('form line %d: the national number holds something other than its digits and '
                      'separators; correct it to what the page prints' % n)
    return digits


def _source_line(value, n):
    m = re.fullmatch(r'(.+) page ([0-9]{1,4})', value)
    if not m or int(m.group(2)) < 1:
        raise Refused('form line %d: the line naming the page was changed; discard this form and read the '
                      'number again' % n)
    return m.group(1), int(m.group(2))


def parse_form(text, shape):
    """{class: [values]} from a filled-in form; a line still holding its slot is left out. The date of
    birth counts only when its two lines agree: masking finds the national number by it. A form the tool
    read a number into adds NUMBER_LINE (its digits) and SOURCE_LINE (the page it came from)."""
    known = {label.lower(): (cls, slot) for label, cls, slot, _ in FORM_LINES}
    known[NUMBER_LINE], known[SOURCE_LINE] = (NUMBER_LINE, None), (SOURCE_LINE, None)
    found = {c: [] for c in CLASSES}
    found[DOB_AGAIN] = []
    lines = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        label, colon, value = line.partition(':')
        key = ' '.join(label.split()).lower()
        if not colon or key not in known:
            raise Refused('form line %d is not one of the form\'s lines; put its label back' % n)
        cls, slot = known[key]
        value = clean(value)
        if cls in (NUMBER_LINE, SOURCE_LINE):
            if cls in found:
                raise Refused('form line %d: the form holds that line twice; keep one' % n)
            found[cls] = _number_line(value, n) if cls == NUMBER_LINE else _source_line(value, n)
            lines[cls] = n
        elif value and value != slot:
            found[cls].append(_form_value(cls, value, n, shape))
            lines.setdefault(cls, n)
    dob, again = found['dob'], found.pop(DOB_AGAIN)
    if len(dob) > 1 or len(again) > 1:
        raise Refused('the form holds more than one date of birth; nothing changed')
    if len(dob) != len(again):
        raise Refused('form line %d: the date of birth goes on both of its lines, the same both times; '
                      'nothing changed' % lines['dob' if dob else DOB_AGAIN])
    if dob != again:
        raise Refused('form line %d: the two date-of-birth lines differ; nothing changed' % lines[DOB_AGAIN])
    if (NUMBER_LINE in found) != (SOURCE_LINE in found):
        raise Refused('form line %d: a national number goes with the line naming the page it was read '
                      'from; discard this form and read the number again' % lines.get(NUMBER_LINE, lines.get(SOURCE_LINE)))
    return found




NUMBER_FORM_HEAD = """\
# The national ID number for %s, as this computer read it from a page. This form stays on this
# computer. No session can read it, nor the picture of the page beside it.
#
# Compare the number below with the picture, digit by digit. If a digit differs, correct it here as
# the page prints it. Change nothing else.
# Not this person's number, or no number in the picture: tell the session; it deletes this unread.
# Keep this as plain text and make no copy of it or of the picture.
# Then save, close both windows and tell the session you are done. It looks for the number on the
# page once more, records it only if it finds it there, and deletes this form and the picture.

"""


def _redact():
    """The masking tool, for its local render and OCR (no model, no network)."""
    import redact_ids
    if redact_ids.IM is None:
        try:
            redact_ids.IM = redact_ids._im()
        except RuntimeError:
            raise Refused('ImageMagick is not installed; bash tools/private-mode/check-setup.sh names the command')
    return redact_ids


def number_scheme(pdir):
    """The one scheme of the person's profile whose number holds no date (ADR-0074), and its row."""
    try:
        table = id_schemes.load()
        keys = id_schemes.tag_keys(read_profile(pdir, raw=True), table)     # named in the tag, never the default
    except id_schemes.SchemeError as e:
        raise Refused(str(e))
    r = _redact()
    need = [k for k in keys if r.SCHEMES.get(k, {}).get('needs_known')]
    if not need:
        raise Refused('this person\'s number is worked out from the date of birth (or none is listed); '
                      'there is no number to read and record')
    if len(need) > 1:
        raise Refused('the profile names more than one number that holds no date; this reads one: '
                      'the operator decides which, and the tag names that one alone while it is read')
    return need[0], table[need[0]]['lang']


def _source(pdir, path, root=None):
    """(the PDF's full path, its path inside the person's folder): a regular file in that folder. A
    relative path is read from the care folder's root (patients/<handle>/...), else from the person's."""
    given = path if os.path.isabs(path) else os.path.join(root, path) if root and os.path.lexists(
        os.path.join(root, path)) else os.path.join(pdir, path)
    full, real = os.path.realpath(given), os.path.realpath(pdir)
    if os.path.commonpath([full, real]) != real or os.path.islink(given) or not os.path.isfile(full) \
            or not full.lower().endswith('.pdf'):
        raise Refused('the page to read is a PDF file in this person\'s folder; nothing written')
    return full, os.path.relpath(full, real)


def _page(pdf, page, lang, wdir):
    for exe in ('pdftoppm', 'tesseract'):
        if shutil.which(exe) is None:
            raise Refused('%s is not installed; bash tools/private-mode/check-setup.sh names the command; '
                          'nothing written' % exe)
    r = _redact()
    try:
        return r.page_words(pdf, page, lang, wdir)
    except r.ToolError:
        raise Refused('that page could not be rendered and read (no such page, or a damaged file); '
                      'nothing written')


class _Scratch:
    """A private (0700) folder for one page's render and OCR, which hold the number: deleted on leaving,
    left behind only by a forced quit or a power cut."""
    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix='tab-read-')
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


def found_on_page(pdf, page, key, lang, digits):
    """Does masking find this number on that page? Local; prints nothing."""
    with _Scratch() as wdir:
        words, W, H, _ = _page(pdf, page, lang, wdir)
        hits, _, _ = _redact().detect(words, W, H, None, scheme=key, known={key: digits})
        return any(h['reason'].startswith('id-known') for h in hits)


def read_number(pdir, pdf, page, key, lang):
    """(digits, picture written): the one number beside the scheme's label on that page, and a picture
    of that spot, owner-only, under the read guard's by-name rule. Refused when none or several."""
    r = _redact()
    with _Scratch() as wdir:
        return _read_number(r, pdir, pdf, page, key, lang, wdir)


def _read_number(r, pdir, pdf, page, key, lang, wdir):
    try:
        words, W, H, png = _page(pdf, page, lang, wdir)
        found = {d: b for d, b in r.labelled_numbers(words, key).items() if r.SCHEMES[key]['valid'](d)}
        if not found:
            raise Refused('no number beside its printed label could be read on that page; try another page '
                          'that prints it clearly; nothing written')
        if len(found) > 1:
            raise Refused('%d different numbers sit beside the label on that page; try a page that prints '
                          'only the person\'s own; nothing written' % len(found))
        (digits, (x, y, w, h)), = found.items()
        pad = max(20, h)
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
        tmp = os.path.join(wdir, 'picture.png')
        r.run_checked(r.IM['convert'] + [png, '-crop', '%dx%d+%d+%d' % (x1 - x0, y1 - y0, x0, y0), '+repage',
                                         '-resize', '200%', tmp], stage='crop', outputs=[tmp])
        os.chmod(tmp, 0o600)
        shutil.move(tmp, os.path.join(pdir, PICTURE_NAME))
        return digits
    except r.ToolError:
        raise Refused('the picture of the number could not be made; nothing written')


def open_picture(path):
    """Preview on a Mac; elsewhere the operator opens it."""
    if sys.platform != 'darwin':
        return False
    return subprocess.run(['open', '-a', 'Preview', path], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def open_form(path):
    """TextEdit on a Mac, a plain editor with no AI extension; elsewhere the operator opens it."""
    if sys.platform != 'darwin':
        return False
    return subprocess.run(['open', '-e', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def cmd_form(root, handle, keep, opener, tell, read=None, page=1, viewer=None):
    """Write the blank form for the chosen classes, owner-only, and open it. A form already waiting is
    opened again, never overwritten: it may hold what the operator typed. Takes no value and prints none.
    With `read` (a PDF in the person's folder), the form holds the number read beside its label on
    `page` instead, and a picture of that spot opens beside it (ADR-0074); `keep` is not needed."""
    pdir = person_dir(root, handle)
    need_marker(pdir, handle)
    path = form_path(pdir)
    if read is not None:
        return _form_read(root, pdir, handle, path, read, page, opener, viewer or (lambda p: False), tell)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except FileExistsError:
        if os.path.islink(path) or not os.path.isfile(path):
            raise Refused('the form is a link or not a regular file; not opened')
        tell('a form for %s was already waiting; it is unchanged' % handle)
    else:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(form_text(handle, keep))
        tell('form written for %s, slots only' % handle)
    if opener(path):
        tell('it is open in TextEdit; when they say they are done, run take-form')
    else:
        tell('they open it in a plain text editor (%s); when they say they are done, run take-form'
             % os.path.relpath(path, root))


def _form_read(root, pdir, handle, path, read, page, opener, viewer, tell):
    if os.path.lexists(path) or os.path.lexists(os.path.join(pdir, PICTURE_NAME)):
        raise Refused('a form or a picture for %s is already waiting; take-form or discard-form first' % handle)
    if page < 1:
        raise Refused('pages are numbered from 1; nothing written')
    key, lang = number_scheme(pdir)
    pdf, rel = _source(pdir, read, root)
    digits = read_number(pdir, pdf, page, key, lang)
    shown = _redact().SCHEMES[key]['shown'](digits)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except OSError:
        os.unlink(os.path.join(pdir, PICTURE_NAME))
        raise Refused('the form could not be written; nothing is waiting')
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        fh.write(NUMBER_FORM_HEAD % handle + '%s: %s\n%s: %s page %d\n' % (NUMBER_LINE, shown, SOURCE_LINE, rel, page))
    tell('the number beside its label was read and written into the form for %s, with a picture of that spot'
         % handle)
    picture = os.path.join(pdir, PICTURE_NAME)
    if opener(path) and viewer(picture):
        tell('both are open (TextEdit, Preview); when they say they are done, run take-form')
    else:
        tell('they open the form in a plain text editor and the picture beside it (%s, %s); when they say '
             'they are done, run take-form' % (os.path.relpath(path, pdir), PICTURE_NAME))


def _take_number(pdir, found):
    """(scheme, digits) of a form's national number, checked: valid for the scheme and found again by
    masking on the page it was read from. Refused otherwise; nothing is recorded."""
    if NUMBER_LINE not in found:
        return None
    key, lang = number_scheme(pdir)
    digits = found.pop(NUMBER_LINE)
    rel, page = found.pop(SOURCE_LINE)
    if not _redact().SCHEMES[key]['valid'](digits):
        raise Refused('the national number cannot be one that was ever issued (its length or one of its '
                      'groups); correct it in the form; nothing changed')
    try:
        pdf, _ = _source(pdir, rel)
    except Refused:
        raise Refused('the page the number was read from is no longer where it was (moved or renamed); '
                      'discard-form, then read the number again; nothing changed')
    if not found_on_page(pdf, page, key, lang, digits):
        raise Refused('masking does not find that number on the page it was read from; check it against the '
                      'picture again and correct it, or discard the form and read another page; nothing changed')
    return key, digits


def cmd_take_form(root, handle, tell):
    """The filled form -> the identity file, the form deleted, then the swap in the working record.
    New values join those recorded, dated today; all or nothing: a refusal changes nothing and leaves
    the form for the operator to correct. A swap that cannot run (a kept detail inside a file name)
    leaves the details recorded and says what to do next."""
    pdir = person_dir(root, handle)
    need_marker(pdir, handle)
    raw = _read_bounded(form_path(pdir), 'form')
    if raw is None:
        raise Refused('no form is waiting for %s' % handle)
    if any('never-api-identity' in n and n not in (IDENTITY_NAME, FORM_NAME, PICTURE_NAME) for n in os.listdir(pdir)):
        raise Refused('another file named like the form is in the person\'s folder, an editor\'s copy or one '
                      'still being saved; run this again in a moment. If it stays, the operator closes the '
                      'editor and deletes that file themselves; a session leaves it alone. Nothing changed')
    if raw.startswith(b'{\\rtf'):
        raise Refused('the form was saved as rich text; in TextEdit choose Format, Make Plain Text, save, '
                      'then run this again; nothing changed')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise Refused('the form is not plain UTF-8 text; save it as UTF-8, then run this again; nothing changed')
    found = parse_form(text, id_shape(pdir))
    number = _take_number(pdir, found)
    if not number and not any(found.values()):
        raise Refused('no slot in the form was replaced, or it is not saved yet; nothing changed. A form '
                      'the operator does not want: discard-form deletes it unread')
    data = load(pdir) or empty()
    if found['dob'] and data['classes']['dob'] and found['dob'] != values(data, 'dob'):
        raise Refused('a different date of birth is already recorded; nothing changed. The operator corrects '
                      'the form, or, if the recorded one is wrong, enters it again at their own terminal '
                      '(set %s dob); then this runs again' % handle)
    today = datetime.date.today()
    for cls, new in found.items():
        add(data, cls, new, today)
    if number:
        data.setdefault('numbers', {})[number[0]] = number[1]     # a new reading replaces the earlier one
    validate(data, id_shape(pdir))
    check_handle(data, handle)
    plans, refs = plan_swap(pdir, data)       # all or nothing: a swap that would refuse records nothing
    if refs:
        raise Refused((REFS_REFUSAL % (refs, '' if refs == 1 else 's'))
                      + '; nothing is recorded and the form is kept')
    write(pdir, data)
    try:
        os.unlink(form_path(pdir))
        if os.path.lexists(os.path.join(pdir, PICTURE_NAME)):
            os.unlink(os.path.join(pdir, PICTURE_NAME))
    except OSError:
        raise Refused('the details are recorded but the form or the picture could not be deleted; the '
                      'operator deletes it, then swap %s replaces them in the profile and medication list' % handle)
    tell('recorded for %s: %s · the form is deleted%s' % (handle, counts(data),
                                                         ', and the picture' if number else ''))
    apply_swap(plans, tell)


def cmd_discard_form(root, handle, tell):
    """Delete a waiting form unread, at the operator's word: one never filled, or one they gave up on.
    Nothing it held is recorded; the identity file is unchanged."""
    pdir = person_dir(root, handle)
    paths = [p for p in (form_path(pdir), os.path.join(pdir, PICTURE_NAME)) if os.path.lexists(p)]
    if not paths:
        raise Refused('no form is waiting for %s' % handle)
    if any(os.path.isdir(p) and not os.path.islink(p) for p in paths):
        raise Refused('the form or the picture is a folder, not a file; not deleted')
    for p in paths:
        os.unlink(p)
    tell('the form for %s is deleted unread%s; the identity file is unchanged'
         % (handle, ', and the picture' if paths[-1].endswith(PICTURE_NAME) else ''))


def recorded_numbers(pdir):
    """{scheme: digits} for a local tool that must not print them (masking)."""
    if os.path.islink(pdir) or not os.path.isdir(pdir):
        raise Refused('not a person folder')
    data = load(pdir)
    if data is None or not data.get('numbers'):
        raise Refused('no national number is recorded in this person\'s identity file')
    return dict(data['numbers'])


def recorded_dob(pdir):
    """The date of birth for a local tool that must not print it (masking)."""
    if os.path.islink(pdir) or not os.path.isdir(pdir):
        raise Refused('not a person folder')
    data = load(pdir)
    if data is None or not data['classes']['dob']:
        raise Refused('no date of birth is recorded in this person\'s identity file')
    return values(data, 'dob')[0]


def cmd_age(root, handle, tell, on=None):
    """Today's age. The command line takes no other reference date: repeated calls with chosen dates
    would find the date of birth by bisection. `on` is for local callers (the handout renderer)."""
    pdir = person_dir(root, handle)
    data = load(pdir)
    if data is None or not data['classes']['dob']:
        raise Refused('the date of birth is not kept from the AI for %s; the profile shows it' % handle)
    ref = on or datetime.date.today()
    tell('age %s (reference date %s)' % (age_text(iso_date(values(data, 'dob')[0]), ref), ref))


def cmd_status(root, handle, tell):
    """What is kept from the AI for this person, as counts; the first thing a session runs after the
    profile of a private-mode person."""
    pdir = person_dir(root, handle)
    text = read_profile(pdir)
    tell('private-mode marker: %s' % ('present' if marked(text) else 'absent'))
    if os.path.lexists(form_path(pdir)):
        tell('form: waiting for the operator')
    if os.path.lexists(os.path.join(pdir, PICTURE_NAME)):
        tell('picture of a page: waiting beside the form; take-form or discard-form deletes it')
    path = identity_path(pdir)
    data = load(pdir)
    if data is None:
        tell('kept from the AI besides the number: nothing (no identity file)')
        return
    mode = stat.S_IMODE(os.lstat(path).st_mode)
    tell('identity file: present%s' % ('' if mode & 0o077 == 0 else ' — readable by others; chmod 600 it'))
    if data.get('numbers'):
        tell('the number itself: recorded, read from a page (masking searches it)')
    tell('kept from the AI besides the number: %s' % (', '.join(kept(data)) or 'nothing'))
    tell('recorded: %s' % counts(data))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Private mode identity file (never prints a value).')
    ap.add_argument('--root', default='.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('set')
    s.add_argument('handle')
    s.add_argument('cls', nargs='?', choices=list(CLASSES))
    f = sub.add_parser('form')
    f.add_argument('handle')
    what = f.add_mutually_exclusive_group(required=True)
    what.add_argument('--keep', help='comma-separated: ' + ','.join(CLASSES))
    f.add_argument('--no-open', action='store_true')
    what.add_argument('--read-number', metavar='PDF', help="a PDF in the person's folder printing their number "
                                                        "beside its label (ADR-0074); --keep is then not needed")
    f.add_argument('--page', type=int, default=1)
    k = sub.add_parser('take-form')
    k.add_argument('handle')
    d = sub.add_parser('discard-form')
    d.add_argument('handle')
    a = sub.add_parser('age')
    a.add_argument('handle')
    t = sub.add_parser('status')
    t.add_argument('handle')
    sub.add_parser('scan')
    c = sub.add_parser('swap')
    c.add_argument('handle')
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_OK if e.code == 0 else EXIT_USAGE
    tell = lambda msg: print(msg, flush=True)  # noqa: E731
    try:
        if args.cmd == 'set':
            if not sys.stdin.isatty():
                raise Refused('set reads from your own terminal; run it there, not through a session')
            cmd_set(args.root, args.handle, args.cls, getpass.getpass,
                    lambda q: input(q).strip().lower() in ('y', 'yes'), tell)
        elif args.cmd == 'form':
            cmd_form(args.root, args.handle, parse_keep(args.keep) if args.keep else None,
                     (lambda path: False) if args.no_open else open_form, tell,
                     read=args.read_number, page=args.page,
                     viewer=(lambda path: False) if args.no_open else open_picture)
        elif args.cmd == 'take-form':
            cmd_take_form(args.root, args.handle, tell)
        elif args.cmd == 'discard-form':
            cmd_discard_form(args.root, args.handle, tell)
        elif args.cmd == 'age':
            cmd_age(args.root, args.handle, tell)
        elif args.cmd == 'scan':
            findings = scan_tree(args.root)
            for f in findings:
                tell(f)
            return EXIT_FOUND if findings else EXIT_OK
        elif args.cmd == 'swap':
            cmd_swap(args.root, args.handle, tell)
        else:
            cmd_status(args.root, args.handle, tell)
    except Refused as e:
        print('refused: %s' % e, file=sys.stderr)
        return EXIT_REFUSED
    except OSError as e:
        print('refused: a filesystem error (%s); nothing written' % type(e).__name__, file=sys.stderr)
        return EXIT_REFUSED
    except (KeyboardInterrupt, EOFError):
        print('\nstopped; nothing written', file=sys.stderr)
        return EXIT_REFUSED
    except Exception as e:                        # never exit 1, which `scan` means as residue found
        print('refused: an internal error (%s); nothing written' % type(e).__name__, file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
