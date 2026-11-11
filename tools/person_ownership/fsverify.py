#!/usr/bin/env python3
"""Filesystem verification = guard L13 (ADR-0037). Binds the on-disk evidence layer to each
patient's active manifest view. Metadata only: hashes bytes and reads path structure; never parses
or reasons over clinical content. The one text it reads is a transcription's front matter, for the
`filed_as:` name of its original.

A finding's `render()` is its category; the CLI adds the path it is about through `locator()`, which
withholds it inside a private-mode person's folder (a filename can itself contain the protected
identifier, and agent-run shell output crosses that boundary — ADR-0029 point 11). The
`person_record_id` and source hashes never print. The green summary reports only whether the legacy
review queue is present."""
import hashlib
import importlib.util
import os
import re
import stat
import unicodedata

from . import schema

# files under med/sources/** that are NOT primary evidence needing their own source record
_BOILERPLATE = frozenset({'README.md', 'CAPTURE-GUIDE.md'})
_OCR_SUFFIX = '.ocr.md'
_CANONICAL_PERSON_ID_LINE_RE = re.compile(
    r'^\s*-\s+\*\*Person record ID(?: [^*]*)?:\*\*\s+`([0-9a-f]{32})`\s*$')
_H2_RE = re.compile(r'^\s*##\s+(.+?)\s*$')
_PRIVATE_MARK = '⟨never-API⟩'
_L10_WAIVER_RE = re.compile(r'⟨not-an-id: verified [0-9]{4}-[0-9]{2}-[0-9]{2}⟩')
_CRUFT_NAMES = frozenset({'.DS_Store', 'Thumbs.db'})
# Finding categories the append writer's refusal reads back to name files still waiting to be logged.
UNLOGGED_SOURCE = 'source on disk with no active manifest record'
UNBOUND_TRANSCRIPTION = '.ocr.md derivative on disk with no manifest binding'


class Finding:
    __slots__ = ('category', 'handle', 'relpath')

    def __init__(self, category, handle=None, relpath=None):
        self.category = category
        self.handle = handle
        self.relpath = relpath

    def render(self):
        return 'RED ' + self.category


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


# Markdown front matter exactly as python-markdown's `meta` extension reads it — the parser the handout
# renderer uses — ported to the standard library: an optional opening `---` line, then `key: value`
# lines (up to three leading spaces), continuation lines indented four or more, ending at a blank line,
# a `---`/`...` line or the first line of anything else. test_attest compares it with the real parser.
_FM_BEGIN_RE = re.compile(r'^-{3}(\s.*)?')
_FM_END_RE = re.compile(r'^(-{3}|\.{3})(\s.*)?')
_FM_KEY_RE = re.compile(r'^[ ]{0,3}(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)')
_FM_MORE_RE = re.compile(r'^[ ]{4,}(?P<value>.*)')


def _front_matter_scan(text, strip_bom=False):
    """([(key, value, is_key_line)], the line that ended the block or '') of a Markdown text's front
    matter, python-markdown `meta` rules. `strip_bom` drops one leading byte-order mark first: the
    renderer's parser does not, so the handout readers keep it off to stay in step with the renderer."""
    if strip_bom and text.startswith('\ufeff'):
        text = text[1:]
    text = text.replace('\x02', '').replace('\x03', '').replace('\r\n', '\n').replace('\r', '\n')
    lines = text.expandtabs(4).split('\n')
    entries, key = [], None
    start = 1 if lines and _FM_BEGIN_RE.match(lines[0]) else 0
    for line in lines[start:]:
        if line.strip() == '' or _FM_END_RE.match(line):
            return entries, line
        m = _FM_KEY_RE.match(line)
        if m:
            key = m.group('key').lower().strip()
            entries.append((key, m.group('value').strip(), True))
            continue
        more = _FM_MORE_RE.match(line)
        if not (more and key):
            return entries, line
        entries.append((key, more.group('value').strip(), False))
    return entries, ''


def front_matter(text, strip_bom=False):
    """{lower-case key: [values]} of a Markdown text's front matter (python-markdown `meta` rules)."""
    meta = {}
    for key, value, _ in _front_matter_scan(text, strip_bom)[0]:
        meta.setdefault(key, []).append(value)
    return meta


_FRONT_MATTER_READ = 64 * 1024


def _front_matter_text(path):
    with open(path, 'rb') as f:
        data = f.read(_FRONT_MATTER_READ)
    if len(data) == _FRONT_MATTER_READ:
        data = data[:data.rfind(b'\n') + 1]
    return data.decode('utf-8', errors='replace')


def read_front_matter(path, strip_bom=False):
    """The front matter of a regular Markdown file, read from its first 64 KiB (a cut final line is
    dropped). Raises OSError when it cannot be read."""
    return front_matter(_front_matter_text(path), strip_bom)


_LIST_ITEM_RE = re.compile(r'^\s*-\s*\S')


def read_filed_as(path):
    """(the one name a transcription's `filed_as:` gives, or None; 'ambiguous' or None). Ambiguous: the
    key twice, a list (`[…]` or `- …` items), or more than one non-empty value. A leading byte-order
    mark is dropped. Raises OSError when the file cannot be read."""
    entries, stop = _front_matter_scan(_front_matter_text(path), strip_bom=True)
    mine = [(value, is_key) for key, value, is_key in entries if key == 'filed_as']
    if sum(1 for _, is_key in mine if is_key) > 1:
        return None, 'ambiguous'
    names = [value for value, _ in mine if value]
    if len(names) > 1 or any(n.startswith(('-', '[')) for n in names):
        return None, 'ambiguous'
    if names:
        return names[0], None
    if mine and entries[-1][0] == 'filed_as' and _LIST_ITEM_RE.match(stop):
        return None, 'ambiguous'          # `filed_as:` with list items below it, ending the block
    return None, None


def _named_original(value):
    """The basename a `filed_as:` value names: quotes and backticks around it dropped, a path's last
    component kept, NFC."""
    value = value.strip().strip('`"\'').strip()
    return unicodedata.normalize('NFC', value.rsplit('/', 1)[-1])


def _read_person_id_state(profile_path):
    """Return ``(canonical_ids, misplaced_count)`` without exposing either value.

    A canonical field belongs to the Identity/Identity & basics section. The former migration
    writer's only unambiguous legacy shape is also accepted: a profile with no Identity section and
    one exact field as its final nonblank line. Exact-looking fields elsewhere are *misplaced*, not
    silently promoted to identity metadata.
    """
    try:
        with open(profile_path, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except OSError:
        return [], 0

    identity_ids = []
    outside = []
    in_identity = False
    has_identity = False
    for index, line in enumerate(lines):
        heading = _H2_RE.match(line)
        if heading:
            title = heading.group(1).strip().lower()
            in_identity = title == 'identity' or title.startswith('identity &')
            has_identity = has_identity or in_identity
        match = _CANONICAL_PERSON_ID_LINE_RE.match(line)
        if match:
            if in_identity:
                identity_ids.append(match.group(1))
            else:
                outside.append((index, match.group(1)))

    if has_identity:
        return identity_ids, len(outside)
    last_nonblank = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip()), -1)
    if len(outside) == 1 and outside[0][0] == last_nonblank:
        return [outside[0][1]], 0
    return [], len(outside)


def read_person_ids(profile_path):
    """All structurally canonical person IDs. Values stay in memory and never print."""
    return _read_person_id_state(profile_path)[0]


def read_person_id(profile_path):
    """The canonical person_record_id from profile.md -> Identity (a line naming the field with a
    32-hex value). Returns the hex string, or None if absent/placeholder. Never printed."""
    ids = read_person_ids(profile_path)
    return ids[0] if len(ids) == 1 else None


def is_private_mode(profile_path):
    try:
        with open(profile_path, encoding='utf-8', errors='replace') as f:
            return any(_PRIVATE_MARK in line for line in f)
    except OSError:
        return False


_CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')

# The identifier's residue shape is the person's: each scheme their profile's tag names, from the
# private-mode number list (ADR-0062). Its reader lives in tools/private-mode/, a directory whose
# name is not a Python identifier, so it is loaded by path, once.
_SCHEMES = None


def _schemes():
    global _SCHEMES
    if _SCHEMES is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'private-mode', 'id_schemes.py')
        spec = importlib.util.spec_from_file_location('tabularium_id_schemes', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _SCHEMES = mod
    return _SCHEMES


def person_scheme_keys(profile_path):
    """The scheme keys a private-mode profile names, or raises ValueError (category only) when the
    number list or the tag cannot be read."""
    m = _schemes()
    table = m.load()
    try:
        with open(profile_path, 'rb') as f:
            data = f.read()
    except OSError:
        raise m.SchemeError('the profile is unreadable')
    return m.profile_schemes(data, table)


def residue_re(keys):
    m = _schemes()
    return m.residue_re(keys, m.load())
WITHHELD_PRIVATE = '<locator withheld: private-mode person>'
WITHHELD_UNKNOWN = '<locator withheld: owner unknown while private mode is in use>'


def person_status(root, handle):
    """'public', 'private' or 'unknown' for patients/<handle>/ — L10's marker test, failing closed.
    Never follows a link; opens only a regular profile.md. Mirrors check.sh `loc_status`."""
    pdir = os.path.join(root, 'patients', handle)
    profile = os.path.join(pdir, 'profile.md')
    try:
        if os.path.islink(pdir) or not os.path.isdir(pdir) \
           or os.path.islink(profile) or not os.path.isfile(profile):
            return 'unknown'
        with open(profile, encoding='utf-8', errors='replace') as f:
            return 'private' if any(_PRIVATE_MARK in line for line in f) else 'public'
    except OSError:
        return 'unknown'


def private_mode_in_use(root):
    """True when a person declares private mode, has a profile.md whose status cannot be read, or the
    roster cannot be listed. Mirrors check.sh `loc_scan`."""
    pdir = os.path.join(root, 'patients')
    try:
        if os.path.islink(pdir):
            return True
        names = os.listdir(pdir)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    for name in names:
        full = os.path.join(pdir, name)
        if os.path.islink(full) or not os.path.isdir(full):
            continue
        status = person_status(root, name)
        if status == 'private' or (status == 'unknown'
                                   and os.path.lexists(os.path.join(full, 'profile.md'))):
            return True
    return False


def locator(root, handle, relpath, in_use):
    """The tree-relative path a finding is about, for guard output (ADR-0029 point 11):
    withheld inside a private-mode person's folder, and — while `in_use` — where the owner cannot be
    established (`_shared/`, an unreadable profile). Control bytes print as '?'. Mirrors check.sh
    `loc`; `relpath` is patient-root-relative when `handle` is set, tree-relative otherwise."""
    parts = ['patients', handle] if handle else []
    if isinstance(relpath, str):
        parts.append(relpath)
    path = '/'.join(p.strip('/') for p in parts if p.strip('/'))
    if not path:
        return ''
    if handle:
        status = person_status(root, handle)
    elif path == '_shared' or path.startswith('_shared/'):
        status = 'unknown'
    else:
        status = 'public'
    if status == 'private':
        return WITHHELD_PRIVATE
    if status == 'unknown' and in_use:
        return WITHHELD_UNKNOWN
    return _CONTROL_RE.sub('?', path)


def _is_cruft_name(name):
    return name in _CRUFT_NAMES or name.startswith('._')


def _is_retraction(r):
    """A `wrong-owner` retraction (ADR-0037 §11): an active record that supersedes a
    misfiled record to REMOVE it from the active view. Such a record expects its source_relpath to be
    ABSENT on disk (the operator moved the file to its true owner), declares no derivatives, and is
    neither evidence nor a review-queue item. It is excluded from the on-disk active view so that if
    the retracted file is still present it is caught as an un-inventoried source (RED)."""
    return (isinstance(r, dict) and r.get('supersede_reason') == 'wrong-owner'
            and isinstance(r.get('supersedes'), str) and r.get('supersedes') != '')


# The masking tool's own document id, a hash of the page's bytes: about one in sixty holds a run in the
# default shape. Exempt only as the name of a folder the tool made, live or superseded, which holds its
# manifest or approval; the rest of the name is still searched, and every other name in full.
TOOL_DOC_ID = re.compile(r'^doc-[0-9a-f]{16}(?=\Z|__)')
TOOL_DOC_FILES = ('manifest.json', 'approval.json')


def _searched_name(name, path):
    if TOOL_DOC_ID.match(name) and not os.path.islink(path) and os.path.isdir(path) and any(
            os.path.isfile(os.path.join(path, f)) and not os.path.islink(os.path.join(path, f))
            for f in TOOL_DOC_FILES):
        return TOOL_DOC_ID.sub('', name)
    return name


def _tree_path_has_identifier_residue(root, residue):
    """Path components only; never reads evidence bytes and never returns the sensitive path.
    Returns True (residue found), False (clean), or None when a directory could not be listed — the
    scan is then INCOMPLETE and the caller must fail closed (os.walk's default swallows the error and
    silently yields nothing for that subtree; 2026-08-23 audit)."""
    errors = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=errors.append):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == '.' else rel_dir.split(os.sep)
        if any(residue.search(_searched_name(p, os.path.join(root, *parts[:i + 1]))) for i, p in enumerate(parts)):
            return True
        if any(residue.search(_searched_name(name, os.path.join(dirpath, name))) for name in dirnames):
            return True
        if any(residue.search(name) for name in filenames):
            return True
    if errors:
        return None
    return False


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, '/')


def _scan_sources(sources_dir):
    """Return (primary_sources, ocr_derivatives) as lists of (abspath, rel_to_sources, issue).
    rel_to_sources is patient-root-relative from med/sources onward is added by the caller; here it
    is relative to sources_dir. ``issue`` is None, ``symlink``, ``non-regular``, or ``uninspectable``.
    Unsafe entries are reported without opening them: in particular, a FIFO named as an inventoried
    source must RED immediately rather than block the guard forever while `_sha256_file` reads it."""
    primary, ocr = [], []
    # A directory os.walk cannot list (mode bits dropped by a restore/rsync/cloud client, or an operator
    # chmod) must RED, not vanish: the default onerror=None swallows the error and the subtree's files
    # are simply never enumerated, so an un-inventoried source inside it passed GREEN (2026-08-23 audit).
    walk_errors = []
    for dirpath, dirnames, filenames in os.walk(sources_dir, onerror=walk_errors.append):
        # do not descend into symlinked directories; report them
        for dn in list(dirnames):
            full = os.path.join(dirpath, dn)
            if os.path.islink(full):
                primary.append((full, os.path.relpath(full, sources_dir).replace(os.sep, '/'),
                                'symlink'))
                dirnames.remove(dn)
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, sources_dir).replace(os.sep, '/')
            try:
                mode = os.lstat(full).st_mode
                issue = ('symlink' if stat.S_ISLNK(mode) else
                         None if stat.S_ISREG(mode) else 'non-regular')
            except OSError:
                issue = 'uninspectable'
            if issue:
                (ocr if fn.endswith(_OCR_SUFFIX) else primary).append((full, rel, issue))
                continue
            if _is_cruft_name(fn):
                continue
            if rel in _BOILERPLATE:
                continue  # boilerplate is not evidence (exempt, ADR-0037 §4)
            if fn.endswith(_OCR_SUFFIX):
                ocr.append((full, rel, None))
            else:
                primary.append((full, rel, None))
    for e in walk_errors:
        bad = getattr(e, 'filename', None) or sources_dir
        primary.append((bad, os.path.relpath(bad, sources_dir).replace(os.sep, '/'), 'unreadable-dir'))
    return primary, ocr


def _verify_patient(root, handle, findings, manifest_override=None, extras=None):
    """Verify one patient. Appends Findings. Returns (legacy_count, evidence_count) — the active
    legacy-folder-only and verified-evidence source-record counts, for the aggregate green summary.

    extras (a list) checks an append-only backup mirror (`checks/backup-offsite.sh`): every active
    record's file must still be there with its recorded bytes, but a file under med/sources that no
    active record binds (an old name the no-delete copy keeps, or anything else) is appended to
    `extras` instead of failing. The live tree's own check catches a stray file where it arises.

    manifest_override maps handle -> (manifest_bytes, records). When it carries THIS handle, the
    PROJECTED manifest is verified in place of the on-disk one (a pre-publish check for an append that
    has not been written); its checkpoint is consistent by construction so the on-disk checkpoint
    match is skipped. Every other check (source binding, person id, derivatives, private residue,
    structural symlink safety) runs unchanged against the real filesystem."""
    pdir = os.path.join(root, 'patients', handle)
    profile = os.path.join(pdir, 'profile.md')
    sources_dir = os.path.join(pdir, 'med', 'sources')
    manifest_path = os.path.join(pdir, 'med', 'MANIFEST')
    checkpoint_path = os.path.join(pdir, 'med', 'MANIFEST.checkpoint')

    # Fail closed on symlinked path components (a symlinked patient dir or med/sources could point at
    # un-inventoried evidence outside the tree; treating it as "empty" was a silent false-GREEN).
    if os.path.islink(pdir):
        findings.append(Finding('patient directory is a symlink', handle))
        return 0, 0
    if os.path.islink(profile):
        findings.append(Finding('profile.md is a symlink', handle))
        return 0, 0
    if os.path.lexists(profile) and not os.path.isfile(profile):
        findings.append(Finding('profile.md exists but is not a regular file', handle))
        return 0, 0
    med_dir = os.path.join(pdir, 'med')
    if os.path.islink(med_dir):
        findings.append(Finding('med/ is a symlink', handle))
        return 0, 0
    if os.path.lexists(med_dir) and not os.path.isdir(med_dir):
        findings.append(Finding('med/ exists but is not a directory', handle))
        return 0, 0
    if os.path.islink(sources_dir):
        findings.append(Finding('med/sources is a symlink', handle))
        return 0, 0
    if os.path.lexists(sources_dir) and not os.path.isdir(sources_dir):
        findings.append(Finding('med/sources exists but is not a directory', handle))
        return 0, 0
    if os.path.islink(manifest_path):
        findings.append(Finding('manifest is a symlink', handle))
        return 0, 0
    if os.path.lexists(manifest_path) and not os.path.isfile(manifest_path):
        findings.append(Finding('manifest exists but is not a regular file', handle))
        return 0, 0
    if os.path.islink(checkpoint_path):
        findings.append(Finding('checkpoint is a symlink', handle))
        return 0, 0
    if os.path.lexists(checkpoint_path) and not os.path.isfile(checkpoint_path):
        findings.append(Finding('checkpoint exists but is not a regular file', handle))
        return 0, 0
    if os.path.isfile(checkpoint_path) and not os.path.isfile(manifest_path):
        findings.append(Finding('checkpoint exists without a manifest', handle))
        return 0, 0

    person_ids, misplaced_ids = _read_person_id_state(profile)
    person_id = person_ids[0] if len(person_ids) == 1 else None
    if misplaced_ids:
        findings.append(Finding('profile.md contains a person record id outside the Identity section', handle))
    if len(person_ids) > 1:
        findings.append(Finding('profile.md contains more than one person record id', handle))
    private_mode = is_private_mode(profile)
    residue_shape = None
    if private_mode:
        try:
            residue_shape = residue_re(person_scheme_keys(profile))
        except ValueError as e:
            findings.append(Finding('private-mode number unreadable: ' + str(e) + ' (locator withheld)', handle))
    if residue_shape is not None:
        residue = _tree_path_has_identifier_residue(pdir, residue_shape)
        if residue is None:
            findings.append(Finding('private-mode path-residue scan could not list the patient tree '
                                    '(unreadable directory; fail closed; locator withheld)', handle))
        elif residue:
            findings.append(Finding('private-mode identifier-shaped residue in a path (locator withheld)', handle))

    override = None
    if manifest_override:
        # The override is keyed by the operator's NFC handle, but this loop variable is the raw on-disk
        # dirent — NFD on a normalization-preserving filesystem (macOS/APFS). Look up under both forms
        # so the PROJECTED manifest is actually applied; a byte-exact lookup would miss and silently
        # verify the stale on-disk manifest, defeating the append writer's pre-publish gate.
        override = (manifest_override.get(handle)
                    or manifest_override.get(unicodedata.normalize('NFC', handle)))
    has_sources_dir = os.path.isdir(sources_dir)
    primary, ocr = ([], [])
    if has_sources_dir:
        primary, ocr = _scan_sources(sources_dir)
        if any(issue == 'unreadable-dir' for _full, _rel, issue in primary):
            primary = [e for e in primary if e[2] != 'unreadable-dir']
            findings.append(Finding('med/sources has an unreadable directory — evidence inventory '
                                    'incomplete (fail closed; locator withheld)', handle))
    manifest_exists = True if override is not None else os.path.isfile(manifest_path)

    # A source-empty scaffold needs no ID yet, but structural/profile/private-path checks above still
    # apply. The old early return bypassed all three and could report false GREEN.
    if not primary and not ocr and not manifest_exists:
        return 0, 0
    if (primary or ocr) and not manifest_exists:
        findings.append(Finding('sources present without a manifest', handle))
        return 0, 0
    if (primary or ocr or manifest_exists) and len(person_ids) == 0:
        findings.append(Finding('sources present without a canonical person record id in profile.md', handle))

    # parse + schema-validate the manifest (or the caller-supplied PROJECTED bytes, for a pre-publish
    # verify of an append that has not yet been written — the manifest_override path).
    if override is not None:
        manifest_bytes, records = override
    else:
        try:
            with open(manifest_path, 'rb') as f:
                manifest_bytes = f.read()
            records = schema.parse_manifest_bytes(manifest_bytes)
        except schema.ManifestError as e:
            findings.append(Finding('manifest unparseable (' + str(e) + ')', handle))
            return 0, 0
        except OSError:
            findings.append(Finding('manifest unreadable', handle))
            return 0, 0

    row_errs = []
    for r in records:
        row_errs.extend(schema.validate_record(r))
        if residue_shape is not None:
            scan_values = [r.get('source_relpath'), r.get('identity_source')]
            raw_derivatives = r.get('derivatives')
            derivatives = raw_derivatives if isinstance(raw_derivatives, list) else []
            scan_values.extend(d.get('derivative_relpath') for d in derivatives
                               if isinstance(d, dict))
            if any(isinstance(v, str) and residue_shape.search(v) for v in scan_values):
                findings.append(Finding('private-mode identifier-shaped residue in manifest metadata '
                                        '(locator withheld)', handle))
    active, sup_errs = schema.supersession_errors(records)
    for e in set(row_errs) | set(sup_errs):
        findings.append(Finding('manifest schema/graph: ' + e, handle))

    # Every manifest, including a zero-record manifest, is checkpointed. Otherwise truncating the
    # ledger to zero and removing its sources/checkpoint turns an append-only violation into GREEN.
    # A PROJECTED (pre-publish) verify has no on-disk checkpoint for the not-yet-written manifest; its
    # consistency is guaranteed by construction (the forward write emits manifest+checkpoint together),
    # so the checkpoint match is asserted only against the real on-disk state.
    if override is None:
        if not (os.path.isfile(checkpoint_path) and not os.path.islink(checkpoint_path)):
            findings.append(Finding('manifest without a valid MANIFEST.checkpoint', handle))
        else:
            try:
                with open(checkpoint_path, 'rb') as f:
                    cp = schema.parse_checkpoint_bytes(f.read())
                cerrs = schema.validate_checkpoint_shape(cp)
                if cerrs:
                    for e in cerrs:
                        findings.append(Finding('checkpoint: ' + e, handle))
                else:
                    want = schema.compute_checkpoint(manifest_bytes, records)
                    if cp['manifest_sha256'] != want['manifest_sha256']:
                        findings.append(Finding('checkpoint manifest hash mismatch (mutation/truncation)', handle))
                    if cp['record_count'] != want['record_count']:
                        findings.append(Finding('checkpoint record_count mismatch (stale/truncated)', handle))
                    if cp['tail_record_id'] != want['tail_record_id']:
                        findings.append(Finding('checkpoint tail_record_id mismatch (reordered/appended)', handle))
            except (OSError, ValueError, UnicodeDecodeError, RecursionError):
                findings.append(Finding('checkpoint unreadable/unparseable', handle))

    # build active views keyed by relpath (source_relpath is patient-root-relative). A wrong-owner
    # retraction is excluded: it must have NO file on disk, so it never binds an on-disk source, and a
    # retracted file left behind falls through to the un-inventoried-source check below (RED).
    active_by_relpath = {}
    for r in active:
        if _is_retraction(r):
            continue
        rp = r.get('source_relpath')
        if isinstance(rp, str):
            active_by_relpath.setdefault(rp, []).append(r)

    # person-id binding for every active record; collect declared derivatives
    declared_derivs = {}  # derivative_relpath -> (parent_record, derivative_sha256)
    legacy_count = 0
    evidence_count = 0
    for r in active:
        if person_id is not None and r.get('person_record_id') != person_id:
            findings.append(Finding('record person id does not match profile', handle, r.get('source_relpath')))
        if _is_retraction(r):
            continue  # not evidence, not queue, declares no derivatives; on-disk absence enforced below
        if r.get('identity_status') == 'legacy-folder-only':
            legacy_count += 1
        raw_derivatives = r.get('derivatives')
        derivatives = raw_derivatives if isinstance(raw_derivatives, list) else []
        for d in derivatives:
            if isinstance(d, dict) and isinstance(d.get('derivative_relpath'), str):
                if d['derivative_relpath'] in declared_derivs:
                    findings.append(Finding('derivative declared by more than one record', handle, d['derivative_relpath']))
                declared_derivs[d['derivative_relpath']] = (r, d.get('derivative_sha256'))

    # every active source record must have exactly one primary source on disk with matching bytes.
    # Keys are NFC-normalized so an on-disk NFD name (macOS returns what was written) matches its
    # NFC manifest relpath — the lean design normalizes in this Python verifier rather than renaming
    # on a normalization-insensitive filesystem (ADR-0037 chose NFC-at-rest for a SHELL verifier).
    # Detect an NFC-key COLLISION (two distinct on-disk files that normalize to the same NFC path —
    # possible on a normalization-preserving filesystem like ext4). A silent dict-overwrite would drop
    # one file from BOTH the byte-check and the un-inventoried-source check, letting an un-inventoried
    # (possibly wrong-person) file pass GREEN. Fail closed: RED on any collision, never overwrite.
    primary_by_rel = {}
    for full, rel_src, issue in primary:
        key = unicodedata.normalize('NFC', 'med/sources/' + rel_src)
        if key in primary_by_rel:
            findings.append(Finding('two source files normalize to the same path (NFC collision)', handle, key))
        else:
            primary_by_rel[key] = (full, issue)
    ocr_by_rel = {}
    for full, rel_src, issue in ocr:
        key = unicodedata.normalize('NFC', 'med/sources/' + rel_src)
        if key in ocr_by_rel:
            findings.append(Finding('two .ocr.md files normalize to the same path (NFC collision)', handle, key))
        else:
            ocr_by_rel[key] = (full, issue)

    for rp, recs in active_by_relpath.items():
        if len(recs) > 1:
            findings.append(Finding('multiple active records for one source path', handle, rp))
        if rp not in primary_by_rel:
            findings.append(Finding('active record for a source not on disk', handle, rp))
            continue
        full, issue = primary_by_rel[rp]
        if issue == 'symlink':
            findings.append(Finding('source is a symlink', handle, rp))
            continue
        if issue:
            findings.append(Finding('source is not a readable regular file', handle, rp))
            continue
        try:
            digest = _sha256_file(full)
        except OSError:
            findings.append(Finding('source unreadable', handle, rp))
            continue
        want = recs[0].get('sha256')
        if digest != want:
            findings.append(Finding('source bytes do not match recorded sha256 (drift)', handle, rp))
        else:
            evidence_count += 1

    # every on-disk primary source must have an active record (un-inventoried source -> RED)
    for rel, (full, issue) in primary_by_rel.items():
        if rel not in active_by_relpath:
            if extras is not None:
                extras.append(rel)
                continue
            findings.append(Finding(UNLOGGED_SOURCE, handle, rel))
            if issue == 'symlink':
                findings.append(Finding('source is a symlink', handle, rel))
            elif issue:
                findings.append(Finding('source is not a readable regular file', handle, rel))

    # derivative binding is 1:1: every declared derivative exists with matching hash + real parent;
    # every on-disk .ocr.md is declared by exactly one record
    for drel, (parent, dsha) in declared_derivs.items():
        if drel not in ocr_by_rel:
            findings.append(Finding('declared derivative not on disk', handle, drel))
            continue
        full, issue = ocr_by_rel[drel]
        if issue == 'symlink':
            findings.append(Finding('derivative is a symlink', handle, drel))
            continue
        if issue:
            findings.append(Finding('derivative is not a readable regular file', handle, drel))
            continue
        try:
            if _sha256_file(full) != dsha:
                findings.append(Finding('derivative bytes do not match recorded sha256', handle, drel))
        except OSError:
            findings.append(Finding('derivative unreadable', handle, drel))
    for drel in ocr_by_rel:
        if drel not in declared_derivs:
            if extras is not None:
                extras.append(drel)
                continue
            findings.append(Finding(UNBOUND_TRANSCRIPTION, handle, drel))
            issue = ocr_by_rel[drel][1]
            if issue == 'symlink':
                findings.append(Finding('derivative is a symlink', handle, drel))
            elif issue:
                findings.append(Finding('derivative is not a readable regular file', handle, drel))

    if extras is not None:   # in a mirror, pair only the transcriptions an active record binds
        ocr_by_rel = {drel: v for drel, v in ocr_by_rel.items() if drel in declared_derivs}
    _verify_transcription_pairs(handle, records, active_by_relpath, primary_by_rel, ocr_by_rel,
                                declared_derivs, findings)
    return legacy_count, evidence_count


def _names_of(rec, by_id):
    """The basenames a source carried along its record chain: today's and every earlier one a
    `rename` left behind (NFC)."""
    names, seen = set(), set()
    while isinstance(rec, dict) and rec.get('record_id') not in seen:
        seen.add(rec.get('record_id'))
        if isinstance(rec.get('source_relpath'), str):
            names.add(unicodedata.normalize('NFC', rec['source_relpath'].rsplit('/', 1)[-1]))
        rec = by_id.get(rec.get('supersedes')) if rec.get('supersedes') else None
    return names


def _verify_transcription_pairs(handle, records, active_by_relpath, primary_by_rel, ocr_by_rel,
                                declared_derivs, findings):
    """A transcription sits beside its own original (KI A66): every on-disk `.ocr.md` has exactly one
    original with the same name stem in the same folder, is bound (when bound) to that original, and
    its front matter's `filed_as:`, when present, names that original — by today's name or one its
    record carried before a `rename`. Reads front matter only; never prints a value."""
    by_stem = {}
    for rel in primary_by_rel:
        by_stem.setdefault(os.path.splitext(rel)[0], []).append(rel)
    by_id = {r.get('record_id'): r for r in records
             if isinstance(r, dict) and isinstance(r.get('record_id'), str)}
    for drel, (full, issue) in ocr_by_rel.items():
        originals = by_stem.get(drel[:-len(_OCR_SUFFIX)], [])
        bound = declared_derivs.get(drel)
        bound_to = bound[0].get('source_relpath') if bound is not None else None
        if len(originals) == 1:
            original = originals[0]
        elif bound_to in originals:
            original = bound_to       # two originals share the stem (x.pdf, x.jpg): the bound one is its own
        else:
            findings.append(Finding('transcription has no single original with its name stem beside it',
                                    handle, drel))
            continue
        if bound is not None and bound_to != original:
            findings.append(Finding('transcription is bound to an original with another name stem',
                                    handle, drel))
        if issue:
            continue
        try:
            filed_as, problem = read_filed_as(full)
        except OSError:
            findings.append(Finding('transcription front matter unreadable (filed_as not checked)',
                                    handle, drel))
            continue
        if problem:
            findings.append(Finding('transcription filed_as is repeated or a list — it names one original',
                                    handle, drel))
            continue
        if filed_as is None:
            continue
        names = {unicodedata.normalize('NFC', original.rsplit('/', 1)[-1])}
        recs = active_by_relpath.get(original) or []
        if len(recs) == 1:
            names |= _names_of(recs[0], by_id)
        if _named_original(filed_as) not in names:
            findings.append(Finding('transcription filed_as names another original (swapped pair?)',
                                    handle, drel))


def _verify_shared_shape(root, findings, scan_private_residue=None):
    """ALT-C / R-3'(a): `_shared/med/` may contain only `.md` prose. A non-`.md` or evidence-shaped
    file there -> RED. Symlinks -> RED (unscannable)."""
    shared_root = os.path.join(root, '_shared')
    shared = os.path.join(shared_root, 'med')
    if os.path.islink(shared_root) or os.path.islink(shared):
        findings.append(Finding('_shared/med is a symlink'))
        return
    if os.path.lexists(shared_root) and not os.path.isdir(shared_root):
        findings.append(Finding('_shared exists but is not a directory'))
        return
    if os.path.lexists(shared) and not os.path.isdir(shared):
        findings.append(Finding('_shared/med exists but is not a directory'))
        return
    if not os.path.isdir(shared):
        return
    shared_errors = []
    for dirpath, dirnames, filenames in os.walk(shared, onerror=shared_errors.append):
        for dn in list(dirnames):
            if os.path.islink(os.path.join(dirpath, dn)):
                findings.append(Finding('_shared/med symlinked directory', None, _rel(root, os.path.join(dirpath, dn))))
                dirnames.remove(dn)
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = _rel(root, full)
            if scan_private_residue and scan_private_residue.search(rel):
                findings.append(Finding('private-mode identifier-shaped residue in an _shared/med path '
                                        '(locator withheld)'))
            try:
                mode = os.lstat(full).st_mode
            except OSError:
                findings.append(Finding('_shared/med file type is uninspectable', None, rel))
                continue
            if stat.S_ISLNK(mode):
                findings.append(Finding('_shared/med symlinked file', None, rel))
            elif not stat.S_ISREG(mode):
                findings.append(Finding('_shared/med non-regular file', None, rel))
            elif not fn.endswith('.md'):
                findings.append(Finding('_shared/med non-.md / evidence-shaped file', None, rel))
            elif scan_private_residue:
                try:
                    with open(full, encoding='utf-8', errors='replace') as f:
                        if any(scan_private_residue.search(line) and not _L10_WAIVER_RE.search(line)
                               for line in f):
                            findings.append(Finding('private-mode identifier-shaped residue in '
                                                    '_shared/med prose (locator withheld)'))
                except OSError:
                    findings.append(Finding('_shared/med prose unreadable for private-mode residue scan'))
    if shared_errors:
        findings.append(Finding('_shared/med has an unreadable directory — shape check incomplete (fail closed)'))


def _list_patients(root):
    pdir = os.path.join(root, 'patients')
    out = []
    if not os.path.isdir(pdir):
        return out
    for name in sorted(os.listdir(pdir)):
        if name.startswith('.'):
            continue
        full = os.path.join(pdir, name)
        # include a symlinked patient dir too, so _verify_patient can RED it (a silent skip would let
        # a whole patient's un-inventoried sources escape L13 while the summary still printed GREEN).
        if os.path.islink(full) or os.path.isdir(full):
            out.append(name)
    return out


def verify_tree(root, manifest_override=None, mirror=False):
    """Run L13 over a repository tree. Returns (findings, aggregate) where aggregate has
    evidence_records and legacy_folder_only for the green summary. findings empty == GREEN.

    mirror=True checks a backup mirror (`_verify_patient`'s extras); aggregate then also has
    mirror_extra_files, the count of files there that no active record binds.

    manifest_override (optional) maps handle -> (manifest_bytes, records): that patient is verified
    against the PROJECTED manifest instead of its on-disk one, without writing anything — the append
    writer's pre-publish gate (verify a proposed append, commit only if green, so no destructive
    rollback is ever needed). Omitted/None == verify the real on-disk tree (the guard L13 path).

    LEAN MVP scope: proves every source is inventoried, bytes match, the person id matches the
    profile, the 1:1 `.ocr.md` derivative binds, path/symlink safety, append-only checkpoint
    integrity, and the `_shared/med/` shape rule. Cross-root evidence-duplicate detection and
    bundle-chain provenance are deferred to a v2 (ADR-0037 §9)."""
    findings = []
    patients_root = os.path.join(root, 'patients')
    if os.path.islink(patients_root):
        findings.append(Finding('patients/ root is a symlink'))
        return findings, {'evidence_records': 0, 'legacy_folder_only': 0}
    if os.path.lexists(patients_root) and not os.path.isdir(patients_root):
        findings.append(Finding('patients/ root exists but is not a directory'))
        return findings, {'evidence_records': 0, 'legacy_folder_only': 0}
    legacy_total = 0
    evidence_total = 0
    extras = [] if mirror else None
    ids_to_handles = {}
    shared_keys = []
    for handle in _list_patients(root):
        lc, ec = _verify_patient(root, handle, findings, manifest_override, extras)
        legacy_total += lc
        evidence_total += ec
        profile = os.path.join(root, 'patients', handle, 'profile.md')
        # Regular-file gate, not just symlink: this cross-patient re-read would block forever on a
        # FIFO/device node (guard-hang DoS) — _verify_patient has already RED-flagged the wrong-type
        # node without opening it, so skipping the re-read here loses nothing (merge red-team 2026-07-19).
        if not os.path.islink(profile) and os.path.isfile(profile):
            ids = read_person_ids(profile)
            if len(ids) == 1:
                ids_to_handles.setdefault(ids[0], []).append(handle)
            if is_private_mode(profile):
                try:
                    keys = person_scheme_keys(profile)
                except ValueError:
                    keys = []                    # already a finding for this person
                shared_keys.extend(k for k in keys if k not in shared_keys)
    for handles in ids_to_handles.values():
        if len(handles) > 1:
            findings.append(Finding('one person record id is reused across patient roots'))
    # Whose a shared note is cannot be established: every private-mode person's shapes. If none could
    # be read, each such person is already a finding.
    shared_residue = residue_re(shared_keys) if shared_keys else None
    _verify_shared_shape(root, findings, scan_private_residue=shared_residue)
    agg = {'evidence_records': evidence_total, 'legacy_folder_only': legacy_total}
    if mirror:
        agg['mirror_extra_files'] = len(extras)
    return findings, agg
