"""Core verification for guard L15 (ADR-0039). Stdlib only, fail-closed. Findings carry a category
and a locator; the CLI prints the locator under the private-mode rule (ADR-0029 point 11)."""
import datetime
import hashlib
import json
import os
import re
import stat

ATTEST_SCHEMA = "tabularium-handout-attest/v1"   # must match render_handout.py
AUDIENCES = ("patient", "clinician")
ENCOUNTER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*$")
# Canonical stem grammar. L8 owns the optional TAB-ID details; L15 independently requires the
# self-describing date/audience prefix plus a non-empty slug before it will count a unit sealed.
# This must be a full-stem match: accepting only a matching prefix let a consistently-attested,
# wholly non-canonical stem pass standalone L15 verification.
LEAF_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})__handout-(patient|clinician)__(.+)$")
# the frozen pre-ADR-0039 legacy queue. The legacy lane is CLOSED to new writes — a flat/archive
# file not in this inventory is red, not queued (red-team 2026-07-17: an open lane was a laundering
# channel for never-fact-checked deliverables).
#
# FORMAT v2 (ADR-0039 A6, 2026-08-09): the inventory binds each path to the SHA-256 of its
# bytes, so an already-inventoried deliverable can no longer be edited while L15 stays green. The
# queue is still explicitly UNSEALED (no fact-check, no attestation — that is what makes it legacy);
# what v2 adds is that its bytes are now FROZEN as well as its names.
#   v1 (superseded): bare relpath per line, names only.
#   v2:              "<64-hex sha256><two spaces><relpath>", plus the version marker below.
# The version is read from the MARKER, never inferred per line: if a bare line could downgrade its
# own entry, an edit could escape the hash by rewriting one line to the v1 shape. A v2 inventory
# therefore rejects any entry line that is not hashed, and a v1 inventory reds until migrated
# (`migrate-legacy`) — an unversioned inventory that silently kept passing is precisely how a
# landed mechanism goes unadopted.
LEGACY_FREEZE = ".legacy-frozen"
LEGACY_FREEZE_MARKER = "# format: tabularium-legacy-freeze/v2"
# path may contain spaces; it may not start with one (that would be an ambiguous separator run)
_FREEZE_V2_LINE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")
# A draft's home is the person's med/analysis/drafts/ (previews: med/analysis/previews/) —
# HANDOUT-SOP step 1. L15 never reads med/analysis/, so nothing parked there can red. A stray draft,
# preview or empty FOLDER left under med/handouts/ does red; the CLI then adds the one-line pointer
# below, for these folder-shaped findings only. A finding on a sealed unit's bytes (stale, tampered,
# orphaned or missing artifacts) gets none: it is repaired in place, never moved out of the lane.
DRAFT_SHAPED = frozenset((
    "phantom-encounter-dir", "malformed-encounter-dir", "unknown-audience-dir", "unexpected-subdir",
))
DRAFT_HINT = ("hint: a draft, preview or empty folder belongs in the person's med/analysis/drafts/ "
              "or previews/ (HANDOUT-SOP step 1), not under med/handouts/ - move or remove the "
              "folder named above. A folder holding an .attest.json is a sealed unit: never move "
              "it, restore its name.")
# operator-facing helpers at the handouts/ root (L8's exclusion set)
ROOT_HELPERS = ("INDEX.md", "README.md", ".gitkeep")
DOT_CRUFT = (".DS_Store", ".gitkeep")
# evidence-lane boilerplate excluded from the products∩evidence intersection (ADR-0037 ALT-C)
SOURCE_BOILERPLATE = ("README.md", "CAPTURE-GUIDE.md", ".gitkeep")
ATTEST_FIELDS = frozenset((
    "schema", "tool", "md_file", "md_sha256", "factcheck_sha256", "output_kind",
    "output_file", "output_sha256", "audience", "lang", "id", "person", "encounter",
    "build_qa", "timestamp",
))


class Finding:
    """Category + locator context. `render()` is the category; the CLI appends the locator through
    tools.person_ownership.fsverify.locator(), which withholds it for a private-mode person."""

    def __init__(self, category, handle, relpath, detail=""):
        self.category = category
        self.handle = handle
        self.relpath = relpath
        self.detail = detail

    def render(self):
        return "[%s]" % self.category


def _unique_object(pairs):
    """JSON object hook that rejects duplicate keys instead of silently choosing first/last."""
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_dotfile(name):
    return name.startswith(".")


def _valid_encounter(name):
    m = ENCOUNTER_RE.match(name)
    if not m:
        return False
    try:  # real calendar parse — the HO-09 DOB lesson: slicing arithmetic is not validation
        datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return False
    return True


def _verify_sealed_dir(handle, hroot, audience, encdir, findings):
    """Verify one encounter dir (sealed, or a draft awaiting its seal). Returns the number of sealed
    (attested) units found."""
    encpath = os.path.join(hroot, audience, encdir)
    rel = lambda n: os.path.join("med/handouts", audience, encdir, n)  # noqa: E731
    entries = []
    for n in sorted(os.listdir(encpath)):
        p = os.path.join(encpath, n)
        if os.path.islink(p):
            findings.append(Finding("symlink", handle, rel(n), "symlinks undermine byte binding"))
            continue
        if os.path.isdir(p):
            findings.append(Finding("unexpected-subdir", handle, rel(n),
                                    "a sealed encounter dir holds files only"))
            continue
        try:
            mode = os.lstat(p).st_mode
        except OSError:
            findings.append(Finding("uninspectable-artifact", handle, rel(n)))
            continue
        if not stat.S_ISREG(mode):
            findings.append(Finding("non-regular-artifact", handle, rel(n),
                                    "sealed artifacts must be regular files"))
            continue
        if _is_dotfile(n):
            if n == ".DS_Store":  # Finder's own file (a regular file, checked above): never bound
                continue
            findings.append(Finding("hidden-artifact", handle, rel(n),
                                    "sealed encounter dirs allow no hidden file but .DS_Store"))
            continue
        entries.append(n)
    if not entries:
        findings.append(Finding("phantom-encounter-dir", handle, rel(""),
                                "empty encounter dir (crashed render / slug typo?)"))
        return 0

    mds, pdfs, txts, attests, sidecars = {}, {}, {}, {}, {}
    for n in entries:
        if n.endswith(".factcheck.md"):
            sidecars[n[: -len(".factcheck.md")]] = n
        elif n.endswith(".attest.json"):
            attests[n[: -len(".attest.json")]] = n
        elif n.endswith(".md"):
            mds[n[: -len(".md")]] = n
        elif n.endswith(".pdf"):
            pdfs[n[: -len(".pdf")]] = n
        elif n.endswith(".txt"):
            txts[n[: -len(".txt")]] = n
        else:
            findings.append(Finding("unknown-artifact", handle, rel(n),
                                    "not md/pdf/txt/attest/factcheck (leftover temp?)"))

    # Leaf ↔ container cross-checks operate on complete stems, not filename prefixes. A complete
    # but non-canonical four-file set must be red and must not inflate the sealed-unit aggregate.
    encdate = encdir[:10]
    stems = set(mds) | set(pdfs) | set(txts) | set(attests) | set(sidecars)
    canonical_stems = set()
    for stem in sorted(stems):
        m = LEAF_RE.fullmatch(stem)
        locator = (mds.get(stem) or pdfs.get(stem) or txts.get(stem)
                   or attests.get(stem) or sidecars[stem])
        if not m:
            findings.append(Finding("noncanonical-leaf", handle, rel(locator),
                                    "sealed artifacts require the canonical full stem grammar"))
            continue
        canonical_stems.add(stem)
        if m.group(1) != encdate:
            findings.append(Finding("leaf-date-mismatch", handle, rel(locator),
                                    "leaf date != encounter dir date %s" % encdate))
        if m.group(2) != audience:
            findings.append(Finding("leaf-audience-mismatch", handle, rel(locator),
                                    "leaf audience token != %s/ directory" % audience))

    # A dir with Markdown (and its sidecar) but no attestation and no output is a DRAFT awaiting its
    # seal — not a finding (A7, 2026-09-27): the renderer's seal gate is the fact-check lock, and an
    # output with no attestation stays red below. Beside a sealed unit, an unattested .md is red.
    for stem in sorted(mds):
        if attests and stem not in attests:
            findings.append(Finding("unsealed-md", handle, rel(mds[stem]),
                                    "canonical .md beside a sealed unit has no .attest.json"))
    for stem in sorted(set(pdfs) | set(txts)):
        if stem in pdfs and stem in txts:
            findings.append(Finding("conflicting-deliverables", handle, rel(pdfs[stem]),
                                    "both .pdf and .txt at one stem"))
        if stem not in attests:
            findings.append(Finding("orphan-output", handle,
                                    rel(pdfs.get(stem) or txts[stem]), "output with no .attest.json"))
    for stem in sorted(sidecars):
        if stem not in mds:
            findings.append(Finding("orphan-factcheck", handle, rel(sidecars[stem]),
                                    "fact-check sidecar with no .md"))
    if len(attests) > 1:
        findings.append(Finding("multiple-sealed-units", handle, rel(""),
                                "one encounter directory must contain exactly one attested stem"))

    sealed = 0
    for stem in sorted(attests):
        if stem not in canonical_stems:
            continue
        apath = os.path.join(encpath, attests[stem])
        arel = rel(attests[stem])
        try:
            with open(apath, encoding="utf-8") as f:
                a = json.load(f, object_pairs_hook=_unique_object)
        except (OSError, ValueError):
            findings.append(Finding("malformed-attestation", handle, arel, "not parseable JSON"))
            continue
        if not isinstance(a, dict) or a.get("schema") != ATTEST_SCHEMA:
            findings.append(Finding("unknown-attestation-schema", handle, arel,
                                    "expected %s" % ATTEST_SCHEMA))
            continue
        if set(a) != ATTEST_FIELDS:
            findings.append(Finding("malformed-attestation", handle, arel,
                                    "attestation fields do not exactly match the v1 schema"))
            continue
        missing = [k for k in ("md_file", "md_sha256", "factcheck_sha256", "output_kind",
                               "output_file", "output_sha256", "audience", "build_qa",
                               "person", "encounter", "lang", "tool", "timestamp")
                   if not isinstance(a.get(k), str) or not a.get(k)]
        if not isinstance(a.get("id"), str):  # id may be empty ("" = no TAB id) but must be present
            missing.append("id")
        if missing:
            findings.append(Finding("malformed-attestation", handle, arel,
                                    "missing field(s): " + ",".join(missing)))
            continue
        ok = True
        if stem not in mds or a["md_file"] != mds[stem]:
            findings.append(Finding("orphan-attestation", handle, arel,
                                    "attested .md absent or name mismatch"))
            ok = False
        if a["output_kind"] not in ("pdf", "txt"):
            findings.append(Finding("malformed-attestation", handle, arel,
                                    "output_kind not pdf|txt")); ok = False
        elif a["build_qa"] != {"pdf": "PASS", "txt": "FALLBACK"}[a["output_kind"]]:
            findings.append(Finding("malformed-attestation", handle, arel,
                                    "build_qa inconsistent with output_kind")); ok = False
        if a["audience"] != audience:
            findings.append(Finding("audience-mismatch", handle, arel,
                                    "attested audience != %s/ directory" % audience)); ok = False
        # person + encounter binding (red-team 2026-07-17): a sealed unit must not be portable —
        # copied into another patient's tree (the #1 error class, L13's product-lane analogue) or
        # renamed into a different-dated encounter dir (stale content presented as current).
        if a["person"] != handle:
            findings.append(Finding("person-mismatch", handle, arel,
                                    "attested person != patients/%s/ tree (wrong-patient filing)"
                                    % handle)); ok = False
        if a["encounter"] != encdir:
            findings.append(Finding("encounter-mismatch", handle, arel,
                                    "attested encounter != containing dir (unit moved/re-dated)"))
            ok = False
        if not ok:
            continue
        if a["md_sha256"] != _sha256(os.path.join(encpath, mds[stem])):
            findings.append(Finding("stale-source", handle, rel(mds[stem]),
                                    ".md changed since sealing — re-verify + re-render"))
            continue
        if stem not in sidecars:
            findings.append(Finding("missing-factcheck", handle, arel,
                                    "attested fact-check sidecar absent"))
            continue
        if a["factcheck_sha256"] != _sha256(os.path.join(encpath, sidecars[stem])):
            findings.append(Finding("stale-factcheck", handle, rel(sidecars[stem]),
                                    "sidecar changed since sealing"))
            continue
        out_map = pdfs if a["output_kind"] == "pdf" else txts
        if stem not in out_map or a["output_file"] != out_map[stem]:
            findings.append(Finding("missing-output", handle, arel,
                                    "attested %s absent or name mismatch" % a["output_kind"]))
            continue
        if a["output_sha256"] != _sha256(os.path.join(encpath, out_map[stem])):
            findings.append(Finding("tampered-output", handle, rel(out_map[stem]),
                                    "deliverable bytes changed after sealing"))
            continue
        sealed += 1
    return sealed


def _legacy_keys(base, hroot, handle=None, findings=None):
    """All non-dot files under base, as freeze-list keys (relpath from handouts/, '/'-separated)."""
    keys = []

    def walk_error(_error):
        # os.walk otherwise suppresses permission/I/O failures and returns a partial inventory. The
        # public CLI renders only the category; the internal locator merely helps a local debugger.
        if findings is not None:
            findings.append(Finding(
                "uninspectable-artifact", handle, os.path.relpath(base, hroot)))

    for dirpath, dirnames, filenames in os.walk(
            base, followlinks=False, onerror=walk_error):
        for dirname in list(dirnames):
            p = os.path.join(dirpath, dirname)
            rel = os.path.relpath(p, hroot)
            if os.path.islink(p):
                if findings is not None:
                    findings.append(Finding("symlink", handle, rel))
                dirnames.remove(dirname)
            elif _is_dotfile(dirname):
                if findings is not None:
                    findings.append(Finding("hidden-artifact", handle, rel))
                dirnames.remove(dirname)
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, hroot)
            if os.path.islink(p):
                if findings is not None:
                    findings.append(Finding("symlink", handle, rel))
                continue
            try:
                mode = os.lstat(p).st_mode
            except OSError:
                if findings is not None:
                    findings.append(Finding("uninspectable-artifact", handle, rel))
                continue
            if not stat.S_ISREG(mode):
                if findings is not None:
                    findings.append(Finding("non-regular-artifact", handle, rel))
                continue
            if _is_dotfile(f):
                if findings is not None:
                    findings.append(Finding("hidden-artifact", handle, rel))
                continue
            keys.append(rel.replace(os.sep, "/"))
    return keys


def unsafe_freeze_key(key):
    """True when `key` cannot be written into the line-oriented inventory without ambiguity.

    Red-team 2026-08-09 (MEDIUM, injection): the writer interpolated a lane path straight into
    "<sha>  <path>\\n", so a DIRECTORY named `d\\n<64-hex>  patient` produced a second, syntactically
    valid entry — pre-blessing bytes for a file that was never in the lane, in a lane whose whole
    contract is that it only ever shrinks. The reject set is defined by what the READER splits on
    (str.splitlines: \\n \\r \\v \\f \\x1c-\\x1e \\x85 \\u2028 \\u2029), not by an ASCII guess, so writer
    and parser cannot disagree; other control characters are refused too, since a lane file whose
    name needs them is a rename-at-source problem, never something to encode around.
    """
    if not key or key != "".join(key.splitlines()):
        return True
    return any(ord(c) < 32 or ord(c) == 127 for c in key)


class Freeze:
    """A parsed legacy inventory.

    `entries` maps freeze-key -> sha256 hex (v2) or None (v1, names only). `version` is 1 or 2.
    `errors` holds category strings for structural faults that make the inventory untrustworthy;
    a caller that sees errors must RED rather than fall back to name-only behaviour (fail closed).
    """

    def __init__(self, version, entries, errors):
        self.version = version
        self.entries = entries
        self.errors = errors

    def __contains__(self, key):
        return key in self.entries


def read_freeze(hroot):
    """The frozen legacy inventory, or None when absent/non-regular.

    Version comes from the marker line, never from per-line shape: see LEGACY_FREEZE above for why
    a per-line fallback would be a downgrade channel. Structural faults are reported through
    `errors` rather than raised, so one malformed inventory reds its own patient without blinding
    the rest of the sweep.
    """
    fpath = os.path.join(hroot, LEGACY_FREEZE)
    try:
        mode = os.lstat(fpath).st_mode
    except OSError:
        return None
    if not stat.S_ISREG(mode):
        return None
    entries = {}
    errors = []
    version = 1
    try:
        with open(fpath, encoding="utf-8") as f:
            raw = f.read()
    except (OSError, UnicodeError):
        return Freeze(0, {}, ["legacy-freeze-unreadable"])
    for line in raw.splitlines():
        if line.strip() == LEGACY_FREEZE_MARKER:
            version = 2
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if version == 2:
            m = _FREEZE_V2_LINE.match(line)
            if not m:
                # A bare line is the downgrade shape; a garbled one (short/none-hex digest, wrong
                # separator) never reaches `entries` at all, so this branch — not the trailing
                # all-hashed sweep below — is the only thing that catches it. Both are kept: the
                # sweep is the belt for a bare line, this is the braces for a malformed one.
                errors.append("legacy-freeze-malformed")
                continue
            key, digest = m.group(2), m.group(1)
        else:
            key, digest = line.strip(), None
        if unsafe_freeze_key(key):
            # unreachable for keys this tool wrote (the writers refuse them) — a hand-edited
            # inventory is the reachable path, and an ambiguous key must never bind bytes
            errors.append("legacy-freeze-malformed")
            continue
        if key in entries and entries[key] != digest:
            errors.append("legacy-freeze-conflicting-entry")
            continue
        entries[key] = digest
    if version == 2 and any(v is None for v in entries.values()):
        errors.append("legacy-freeze-malformed")
    return Freeze(version, entries, errors)


def _product_evidence_intersection(handle, pdir, findings):
    """Products (handouts/**) and evidence (sources/**) must never share bytes (ADR-0039 §1)."""
    def tree_hashes(base, skip_names, optional=False):
        out = {}
        try:
            base_mode = os.lstat(base).st_mode
        except FileNotFoundError:
            if not optional:
                findings.append(Finding(
                    "uninspectable-artifact", handle, os.path.relpath(base, pdir)))
            return out
        except OSError:
            findings.append(Finding(
                "uninspectable-artifact", handle, os.path.relpath(base, pdir)))
            return out
        if stat.S_ISLNK(base_mode):
            findings.append(Finding("symlink", handle, os.path.relpath(base, pdir),
                                    "product/evidence lane root must not be a symlink"))
            return out
        if not stat.S_ISDIR(base_mode):
            findings.append(Finding("lane-root-wrong-type", handle, os.path.relpath(base, pdir),
                                    "product/evidence lane root must be a directory"))
            return out

        def walk_error(_error):
            # A partial walk must never prove the products/evidence intersection empty.
            findings.append(Finding(
                "uninspectable-artifact", handle, os.path.relpath(base, pdir)))

        for dirpath, dirnames, filenames in os.walk(
                base, followlinks=False, onerror=walk_error):
            for dirname in list(dirnames):
                p = os.path.join(dirpath, dirname)
                rel = os.path.relpath(p, pdir)
                try:
                    mode = os.lstat(p).st_mode
                except OSError:
                    findings.append(Finding("uninspectable-artifact", handle, rel))
                    dirnames.remove(dirname)
                    continue
                if stat.S_ISLNK(mode):
                    findings.append(Finding("symlink", handle, rel,
                                            "product/evidence traversal does not follow symlinks"))
                    dirnames.remove(dirname)
                elif not stat.S_ISDIR(mode):
                    findings.append(Finding("non-regular-artifact", handle, rel))
                    dirnames.remove(dirname)
            for f in filenames:
                p = os.path.join(dirpath, f)
                rel = os.path.relpath(p, pdir)
                try:
                    mode = os.lstat(p).st_mode
                except OSError:
                    findings.append(Finding("uninspectable-artifact", handle, rel))
                    continue
                if stat.S_ISLNK(mode):
                    findings.append(Finding("symlink", handle, rel,
                                            "product/evidence traversal does not hash symlinks"))
                    continue
                if not stat.S_ISREG(mode):
                    findings.append(Finding("non-regular-artifact", handle, rel,
                                            "only regular files may enter byte comparison"))
                    continue
                if _is_dotfile(f) or f in skip_names:
                    continue
                try:
                    digest = _sha256(p)
                except OSError:
                    findings.append(Finding("uninspectable-artifact", handle, rel))
                    continue
                out.setdefault(digest, rel)
        return out

    prod = tree_hashes(os.path.join(pdir, "med", "handouts"), set(ROOT_HELPERS))
    evid = tree_hashes(
        os.path.join(pdir, "med", "sources"), set(SOURCE_BOILERPLATE), optional=True)
    for h in sorted(set(prod) & set(evid)):
        findings.append(Finding("product-in-evidence", handle, prod[h],
                                "same bytes as evidence file %s — products are never sources" % evid[h]))


def verify_tree(root):
    """Returns (findings, aggregate). Raises on internal error (caller fails closed)."""
    findings = []
    agg = {"patients": 0, "sealed_units": 0, "legacy_unsealed": 0}
    patients_dir = os.path.join(root, "patients")
    try:
        patients_mode = os.lstat(patients_dir).st_mode
    except FileNotFoundError:
        return findings, agg  # patient-free tree (skeleton) — legitimate no-op green
    except OSError:
        findings.append(Finding(
            "uninspectable-root", "", "patients", "cannot inspect patient root"))
        return findings, agg
    if stat.S_ISLNK(patients_mode):
        findings.append(Finding(
            "symlink", "", "patients", "patients root must be a real directory"))
        return findings, agg
    if not stat.S_ISDIR(patients_mode):
        findings.append(Finding(
            "patients-root-wrong-type", "", "patients",
            "patients root must be a directory"))
        return findings, agg

    try:
        handles = sorted(os.listdir(patients_dir))
    except OSError:
        findings.append(Finding(
            "uninspectable-root", "", "patients", "cannot enumerate patient roots"))
        return findings, agg

    for handle in handles:
        pdir = os.path.join(patients_dir, handle)
        try:
            patient_mode = os.lstat(pdir).st_mode
        except OSError:
            findings.append(Finding(
                "uninspectable-root", handle, "", "patient root cannot be inspected"))
            continue
        if stat.S_ISLNK(patient_mode):
            findings.append(Finding(
                "symlink", handle, "", "patient root must not be a symlink"))
            continue
        if _is_dotfile(handle):
            if stat.S_ISDIR(patient_mode):
                findings.append(Finding(
                    "hidden-patient-root", handle, "",
                    "hidden patient roots evade ordinary discovery"))
            continue
        if not stat.S_ISDIR(patient_mode):
            continue
        try:
            patient_entries = set(os.listdir(pdir))
        except OSError:
            findings.append(Finding(
                "uninspectable-root", handle, "", "patient root cannot be enumerated"))
            continue
        if "med" not in patient_entries:
            continue

        med = os.path.join(pdir, "med")
        try:
            med_mode = os.lstat(med).st_mode
        except OSError:
            findings.append(Finding(
                "uninspectable-root", handle, "med", "med root cannot be inspected"))
            continue
        if stat.S_ISLNK(med_mode):
            findings.append(Finding(
                "symlink", handle, "med", "med root must not be a symlink"))
            continue
        if not stat.S_ISDIR(med_mode):
            findings.append(Finding(
                "handouts-wrong-type", handle, "med",
                "med root must be a directory"))
            continue
        try:
            med_entries = set(os.listdir(med))
        except OSError:
            findings.append(Finding(
                "uninspectable-root", handle, "med", "med root cannot be enumerated"))
            continue
        if "handouts" not in med_entries:
            continue

        hroot = os.path.join(med, "handouts")
        try:
            handouts_mode = os.lstat(hroot).st_mode
        except OSError:
            findings.append(Finding(
                "uninspectable-root", handle, "med/handouts",
                "handouts root cannot be inspected"))
            continue
        if stat.S_ISLNK(handouts_mode):
            findings.append(Finding("symlink", handle, "med/handouts",
                                    "handouts root must be a real directory in this patient tree"))
            continue
        if not stat.S_ISDIR(handouts_mode):
            findings.append(Finding("handouts-wrong-type", handle, "med/handouts",
                                    "handouts root must be a directory"))
            continue
        try:
            handout_entries = sorted(os.listdir(hroot))
        except OSError:
            findings.append(Finding(
                "uninspectable-root", handle, "med/handouts",
                "handouts root cannot be enumerated"))
            continue
        agg["patients"] += 1

        for n in handout_entries:
            p = os.path.join(hroot, n)
            relp = os.path.join("med/handouts", n)
            if os.path.islink(p):
                findings.append(Finding("symlink", handle, relp, "symlinks undermine byte binding"))
                continue
            try:
                mode = os.lstat(p).st_mode
            except OSError:
                findings.append(Finding("uninspectable-artifact", handle, relp))
                continue
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                findings.append(Finding("non-regular-artifact", handle, relp))
                continue
            if _is_dotfile(n):
                if (n == LEGACY_FREEZE and stat.S_ISREG(mode)) \
                   or (n in DOT_CRUFT and stat.S_ISREG(mode)):
                    continue
                findings.append(Finding("hidden-artifact", handle, relp))
                continue
            if os.path.isdir(p):
                if n not in AUDIENCES:
                    findings.append(Finding("unknown-audience-dir", handle, relp,
                                            "only patient/ and clinician/ exist in the sealed lane"))
                continue
            if n not in ROOT_HELPERS:
                findings.append(Finding("root-stray", handle, relp,
                                        "files at handouts/ root are INDEX/README only"))

        index_path = os.path.join(hroot, "INDEX.md")
        index_text = ""
        if os.path.isfile(index_path) and not os.path.islink(index_path):
            with open(index_path, encoding="utf-8", errors="replace") as f:
                index_text = f.read()

        # the legacy lane is CLOSED (red-team 2026-07-17): flat/archive files are queued ONLY if
        # inventoried in .legacy-frozen at adoption. Anything else in the lane is a post-adoption
        # write — the un-fact-checked / un-bound deliverable classes L15 exists to stop.
        frozen = read_freeze(hroot)
        lane_files = []  # (freeze-key, display-relpath)

        for audience in AUDIENCES:
            adir = os.path.join(hroot, audience)
            if os.path.islink(adir) or not os.path.isdir(adir):
                continue
            for n in sorted(os.listdir(adir)):
                p = os.path.join(adir, n)
                relp = os.path.join("med/handouts", audience, n)
                if os.path.islink(p):
                    findings.append(Finding("symlink", handle, relp,
                                            "symlinks undermine byte binding"))
                    continue
                try:
                    mode = os.lstat(p).st_mode
                except OSError:
                    findings.append(Finding("uninspectable-artifact", handle, relp))
                    continue
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    findings.append(Finding("non-regular-artifact", handle, relp))
                    continue
                if _is_dotfile(n):
                    if n in DOT_CRUFT and stat.S_ISREG(mode):
                        continue
                    findings.append(Finding("hidden-artifact", handle, relp))
                    continue
                if os.path.isfile(p):
                    lane_files.append((audience + "/" + n, relp))
                    continue
                if n == "archive":
                    for key in _legacy_keys(p, hroot, handle, findings):
                        lane_files.append((key, os.path.join("med/handouts", key)))
                    continue
                if not _valid_encounter(n):
                    findings.append(Finding("malformed-encounter-dir", handle, relp,
                                            "expected YYYY-MM-DD-<slug> (real calendar date)"))
                    continue
                sealed = _verify_sealed_dir(handle, hroot, audience, n, findings)
                agg["sealed_units"] += sealed
                # boundary-anchored BOTH sides, not bare substring: '…-alpha' must not ride
                # green on an INDEX row naming '…-alpha-followup', nor '…-visit' on
                # '…-prep-2026-01-01-visit' (red-team 2026-07-17: left edge too)
                if sealed and not re.search(r"(?<![a-z0-9-])" + re.escape(n) + r"(?![a-z0-9-])",
                                            index_text):
                    findings.append(Finding("index-missing", handle, relp,
                                            "sealed unit not referenced in INDEX.md"))

        if lane_files and frozen is None:
            findings.append(Finding(
                "legacy-freeze-missing", handle, "med/handouts/" + LEGACY_FREEZE,
                "%d legacy-lane file(s) but no frozen inventory — generate it once via "
                "`python3 -m tools.handout_attest --root . freeze-legacy <handle>`" % len(lane_files)))
        elif frozen is not None:
            # structural faults first: an inventory we cannot trust must never fall back to
            # name-only acceptance (that is the exact downgrade the v2 marker exists to prevent).
            for category in sorted(set(frozen.errors)):
                findings.append(Finding(
                    category, handle, "med/handouts/" + LEGACY_FREEZE,
                    "legacy inventory is structurally untrustworthy — restore it from .snapshots/ "
                    "rather than regenerating (regeneration would re-bless current bytes)"))
            if frozen.version == 1 and lane_files:
                # v1 binds names only: an inventoried deliverable could be edited with the
                # board green. Red until migrated — a silently-tolerated old format is how a landed
                # mechanism goes unadopted.
                findings.append(Finding(
                    "legacy-freeze-unversioned", handle, "med/handouts/" + LEGACY_FREEZE,
                    "names-only (v1) inventory — migrate once via `python3 -m tools.handout_attest "
                    "--root . migrate-legacy <handle>` to bind each queued file's bytes"))
            for key, disp in lane_files:
                if key not in frozen:
                    findings.append(Finding(
                        "legacy-lane-new-file", handle, disp,
                        "not in the frozen pre-ADR-0039 queue — new handouts are sealed encounter "
                        "units, never flat/archive files"))
                    continue
                digest = frozen.entries.get(key)
                if digest is not None:
                    try:
                        current = _sha256(os.path.join(hroot, key))
                    except OSError:
                        findings.append(Finding("uninspectable-artifact", handle, disp))
                        continue
                    if current != digest:
                        # the edited-legacy class: an already-inventoried legacy deliverable whose bytes
                        # changed. The queue is unsealed by design, but mutation is never silent.
                        findings.append(Finding(
                            "legacy-bytes-changed", handle, disp,
                            "inventoried legacy deliverable's bytes changed since the freeze — "
                            "restore it, or retire it and issue a sealed encounter unit instead"))
                        continue
                agg["legacy_unsealed"] += 1  # inventoried pre-ADR-0039 legacy, queued not red

        _product_evidence_intersection(handle, pdir, findings)

    return findings, agg
