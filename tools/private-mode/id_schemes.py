"""
The national ID numbers private mode knows (ADR-0062) — the Python reader of `id-schemes.tsv`.
STDLIB ONLY. Guard L10 reads a profile with this module (`python3 id_schemes.py PROFILE`, which prints
an outcome code and the person's shape, never a line of the profile) and searches with `grep -E`, so
the residue shapes stay plain POSIX extended regular expressions; a tab is written `\\t`.

A profile names a private-mode person's schemes on the line that carries the v1 marker:
`⟨id-scheme KEY⟩`, or `⟨id-scheme KEY,KEY⟩` for a person with more than one number. The reserved key
`unlisted` names a number not on the list, which the operator covers by hand (ADR-0076): it has no
residue shape. Only exact tokens decide (ADR-0077): with no exact tag read, every row of the list is
searched, so a damaged tag can widen the search but never narrow it; words carry no machine meaning,
and spotting a damaged tag is the session's job. The one-line refusals of ADR-0073 stay, frozen:
- on a marker line, anything shaped like the tag (another bracket, case or joiner), and any key of
  the list outside the one exact tag, is refused; the list's file name is not a tag;
- in the Identity section, the exact opening `⟨id-scheme` on any other line is refused as misplaced;
- elsewhere (a change-log quote, a note) a tag is plain text.
A tag that is repeated, malformed or names an unknown key raises SchemeError. Messages are category only.
"""
import os
import re
import sys

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'id-schemes.tsv')
MARK = '⟨never-API⟩'
TAG_OPEN = '⟨id-scheme'
UNLISTED = 'unlisted'      # reserved: a number not on the list, covered by hand (ADR-0076, ADR-0077)
TAG_RE = re.compile(r'⟨id-scheme ([a-z0-9-]+(?:,[a-z0-9-]+)*)⟩')
EXACT_RE = re.compile(TAG_RE.pattern.encode('utf-8'))
KEY_RE = re.compile(r'[a-z0-9-]+')


class SchemeError(ValueError):
    """The table or a profile's tag cannot be read. The message names the category, never a value; `code`
    names it for guard L10."""
    def __init__(self, message, code='LIST'):
        super().__init__(message)
        self.code = code


def load(path=TABLE):
    """key -> {'lang', 'shape', 'words'}, in the table's order (no exact tag searches every row: ADR-0077)."""
    try:
        with open(path, encoding='utf-8') as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        raise SchemeError('the private-mode number list is missing or unreadable')
    table = {}
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) != 4 or not all(p.strip() == p and p for p in parts):
            raise SchemeError('a row of the private-mode number list does not have four tab-separated fields')
        key, lang, shape, words = parts
        if not KEY_RE.fullmatch(key) or key in table or key == UNLISTED:
            raise SchemeError('the private-mode number list has a malformed or repeated key')
        try:
            compiled = re.compile(shape)
        except re.error:
            raise SchemeError('a residue shape in the private-mode number list does not compile')
        if compiled.search(''):
            raise SchemeError('a residue shape in the private-mode number list matches an empty line')
        table[key] = {'lang': lang, 'shape': shape, 'words': words}
    if not table:
        raise SchemeError('the private-mode number list has no rows')
    return table


# up to 12 joiner bytes: room for a spaced dash, no-break spaces or a zero-width mark (3 bytes each in UTF-8)
LOOSE_RE = re.compile(rb'(?:^|[^A-Za-z0-9])[Ii][Dd][^A-Za-z0-9]{0,12}[Ss][Cc][Hh][Ee][Mm]')
LIST_NAME = b'id-schemes.tsv'
H2_RE = re.compile(rb'^##[ \t]+(.*?)[ \t]*$')


def _identity_heading(title):
    title = title.lower()
    return title == b'identity' or title.startswith(b'identity &')


def profile_schemes(profile_text, table):
    """What to search: the keys the exact tag names (`tag_keys`), or every row of the list when no tag is
    read, never fewer. Pass the file's bytes (str is encoded back)."""
    return tag_keys(profile_text, table) or list(table)


def tag_keys(profile_text, table):
    """The scheme keys a marked profile's exact tag names, in tag order, `unlisted` included; [] when no tag
    is read. A step that acts on one named number (reading it from a page) uses this, never the default."""
    mark, opening = MARK.encode('utf-8'), TAG_OPEN.encode('utf-8')
    keys_re = re.compile(rb'(?<![A-Za-z0-9-])(?:%s)(?![A-Za-z0-9-])' % b'|'.join(
        re.escape(k.encode('utf-8')) for k in table), re.I)   # a key, whole, outside the exact tag
    tagged, stray, misplaced, in_identity = [], False, False, False
    data = profile_text if isinstance(profile_text, bytes) else profile_text.encode('utf-8', 'surrogateescape')
    for line in data.split(b'\n'):
        if line.endswith(b'\r'):
            line = line[:-1]
        heading = H2_RE.match(line)
        if heading:
            in_identity = _identity_heading(heading.group(1))
        if mark in line:
            n = len(LOOSE_RE.findall(line.replace(LIST_NAME, b'')))
            if n:
                tagged.append((line, n))
            stray = stray or bool(keys_re.search(EXACT_RE.sub(b' ', line)))
        elif in_identity and opening in line:
            misplaced = True
    if misplaced:
        raise SchemeError('the private-mode number tag is in the Identity section but not on the line carrying '
                          'the private-mode marker; move it onto that line and describe it in words elsewhere', 'MISPLACED')
    malformed = SchemeError('the private-mode number tag is malformed; the form is ⟨id-scheme KEY⟩ or ⟨id-scheme KEY,KEY⟩', 'MALFORMED')
    if stray:
        raise malformed
    if not tagged:
        return []
    if len(tagged) != 1 or tagged[0][1] != 1:
        raise SchemeError('the private-mode number tag appears more than once on the private-mode line; keep one', 'REPEATED')
    m = TAG_RE.search(tagged[0][0].decode('utf-8', 'surrogateescape'))
    if not m:
        raise malformed
    keys = []
    for key in m.group(1).split(','):
        if key not in table and key != UNLISTED:
            raise SchemeError('the private-mode number tag names a scheme the number list does not know; '
                              'choose the intended key from the number list; if the number is not on it, '
                              'use the key unlisted, name its issuing country in words, and cover it by hand '
                              'before scanning', 'UNKNOWN')
        if key not in keys:
            keys.append(key)
    return keys


def residue_re(keys, table):
    """One pattern matching any of these schemes' residue shapes (`unlisted` has none); one that never
    matches for none."""
    keys = [k for k in keys if k != UNLISTED]
    if not keys:
        return re.compile(r'(?!)')
    return re.compile('|'.join('(?:%s)' % table[k]['shape'] for k in keys))


def board_shape(keys, table):
    """The union of these schemes' shapes as grep -E reads it, each `\\t` a real tab."""
    return '|'.join('(%s)' % table[k]['shape'] for k in keys if k != UNLISTED).replace('\\t', '\t')


def main(argv):
    """Guard L10's reader: `id_schemes.py PROFILE` prints `TAG KEY[,KEY]` and `SHAPE <the union shape>`,
    `NOTLISTED` (a tag of `unlisted` alone: no shape), or the code of the refusal — never a line or a value of the profile. An unreadable
    profile exits 1 with nothing printed."""
    try:
        with open(argv[1], 'rb') as fh:
            data = fh.read()
    except (OSError, IndexError):
        return 1
    try:
        table = load()
        keys = profile_schemes(data, table)
    except SchemeError as e:
        print(e.code)
        return 0
    shape = board_shape(keys, table)
    out = 'TAG %s\nSHAPE %s\n' % (','.join(keys), shape) if shape else 'NOTLISTED\n'
    sys.stdout.buffer.write(out.encode('utf-8'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
