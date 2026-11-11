#!/usr/bin/env python3
"""CLI for the sealed-handout attestation package (ADR-0039): `python3 -m tools.handout_attest`.

Subcommands:
  verify         L15's fail-closed check. Exit 0 = GREEN (state-only summary); 1 = RED
                 (category + path, the path withheld for a private-mode person — ADR-0029
                 point 11); 2 = internal error (fail closed).
  freeze-legacy  create patients/<handle>/med/handouts/.legacy-frozen ONCE from the lane's current
                 flat/archive contents. Existing inventory is never replaced: the legacy lane is
                 closed to new writes, so a refresh would be a laundering command.
  migrate-legacy one-way v1 (names only) -> v2 (names + SHA-256) conversion of an existing
                 inventory (ADR-0039 A6). Admits NO path the v1 list did not already
                 carry, and refuses a v2 inventory outright — re-hashing an already-bound
                 inventory would re-bless mutated bytes, i.e. the laundering command this whole
                 lane closure exists to prevent.
  next-id        print a person's next free stable handout ID(s) with correct check characters
                 (ADR-0033; handout_id.py). Read-only; prints IDs and notes, never a path.
"""
import argparse
import datetime
import os
import re
import stat
import sys

from . import verify as _verify
from ..person_ownership import fsverify as _owner   # the one Python home of the locator rule


def _raise_walk_error(error):
    """Turn os.walk's otherwise-silent traversal failure into an ordinary fail-closed exception."""
    raise error


def _cmd_verify(a):
    try:
        findings, agg = _verify.verify_tree(a.root)
    except Exception:
        # fail closed: any unexpected error in the guard is RED, not a green pass. Category only.
        print("L15 RED: attestation verifier hit an internal error (fail closed)")
        return 2
    if findings:
        try:
            in_use = _owner.private_mode_in_use(a.root)
            wheres = [_owner.locator(a.root, f.handle, f.relpath, in_use) for f in findings]
        except Exception:
            wheres = [""] * len(findings)   # cannot apply the locator rule: category only
        print("L15 RED: sealed-handout verification failed:")
        for line in sorted(set(f.render() + ((" " + w) if w else "")
                               for f, w in zip(findings, wheres))):
            print("  " + line)
        if any(f.category in _verify.DRAFT_SHAPED for f in findings):
            print("  " + _verify.DRAFT_HINT)   # a fixed pointer: no handle, no path
        return 1
    queue_state = "non-empty" if agg["legacy_unsealed"] else "empty"
    print("L15 GREEN: sealed-handout byte binding verified; legacy queue %s. "
          "L15 proves byte binding + lane separation only — content judgment stays with the "
          "fact-check gate (ADR-0034)."
          % queue_state)
    return 0


def _cmd_freeze_legacy(a):
    handle = a.handle
    if not handle or handle.startswith(".") or os.path.isabs(handle) \
       or os.path.basename(handle) != handle or os.sep in handle \
       or (os.altsep and os.altsep in handle):
        print("freeze-legacy: invalid patient handle shape (locator withheld)")
        return 2
    patients = os.path.join(a.root, "patients")
    pdir = os.path.join(patients, handle)
    med = os.path.join(pdir, "med")
    hroot = os.path.join(med, "handouts")
    if any(os.path.islink(p) or not os.path.isdir(p)
           for p in (patients, pdir, med, hroot)):
        print("freeze-legacy: requested patient handouts tree is absent (locator withheld)")
        return 2
    fpath = os.path.join(hroot, _verify.LEGACY_FREEZE)
    if os.path.lexists(fpath):
        print("freeze-legacy: inventory already exists; replacement is forbidden (lane remains closed)")
        return 2
    keys = []
    for audience in _verify.AUDIENCES:
        adir = os.path.join(hroot, audience)
        try:
            audience_mode = os.lstat(adir).st_mode
        except FileNotFoundError:
            continue
        except OSError:
            print("freeze-legacy: audience lane could not be inspected (locator withheld)")
            return 2
        if stat.S_ISLNK(audience_mode) or not stat.S_ISDIR(audience_mode):
            print("freeze-legacy: symlinked/wrong-type audience lane refused (locator withheld)")
            return 2
        try:
            names = sorted(os.listdir(adir))
        except OSError:
            print("freeze-legacy: audience lane could not be inspected (locator withheld)")
            return 2
        for n in names:
            p = os.path.join(adir, n)
            try:
                mode = os.lstat(p).st_mode
            except OSError:
                print("freeze-legacy: uninspectable lane entry refused (locator withheld)")
                return 2
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                print("freeze-legacy: non-regular lane entry refused (locator withheld)")
                return 2
            if _verify._is_dotfile(n):
                if n in _verify.DOT_CRUFT and stat.S_ISREG(mode):
                    continue
                print("freeze-legacy: hidden lane entry refused (locator withheld)")
                return 2
            if stat.S_ISREG(mode):
                keys.append(audience + "/" + n)
            elif n == "archive":
                try:
                    for dirpath, dirnames, filenames in os.walk(
                            p, followlinks=False, onerror=_raise_walk_error):
                        for dirname in dirnames:
                            child = os.path.join(dirpath, dirname)
                            if os.path.islink(child) or _verify._is_dotfile(dirname):
                                print("freeze-legacy: hidden/symlinked archive entry refused "
                                      "(locator withheld)")
                                return 2
                        for filename in sorted(filenames):
                            child = os.path.join(dirpath, filename)
                            try:
                                child_mode = os.lstat(child).st_mode
                            except OSError:
                                print("freeze-legacy: uninspectable archive entry refused "
                                      "(locator withheld)")
                                return 2
                            if not stat.S_ISREG(child_mode):
                                print("freeze-legacy: non-regular archive entry refused "
                                      "(locator withheld)")
                                return 2
                            if _verify._is_dotfile(filename):
                                print("freeze-legacy: hidden archive entry refused "
                                      "(locator withheld)")
                                return 2
                            keys.append(os.path.relpath(child, hroot).replace(os.sep, "/"))
                except OSError:
                    print("freeze-legacy: archive traversal failed closed (locator withheld)")
                    return 2
    # A lane path that cannot be written unambiguously into the line-oriented inventory is refused
    # OUTRIGHT — never encoded around, never skipped (red-team 2026-08-09: a crafted directory name
    # containing a line break injected a whole valid entry, pre-blessing bytes for a file that was
    # never in the lane). Rename at the source instead.
    for k in sorted(keys):
        if _verify.unsafe_freeze_key(k):
            print("freeze-legacy: lane entry name carries a line break or control character; "
                  "refusing to write an ambiguous inventory — rename it at the source (locator withheld)")
            return 2
    # v2 (ADR-0039 A6): bind each queued path to its bytes, not just its name. Hash BEFORE
    # creating the file so a read failure leaves no half-inventory behind (fail closed).
    try:
        hashed = [(k, _verify._sha256(os.path.join(hroot, k))) for k in sorted(keys)]
    except OSError:
        print("freeze-legacy: lane entry could not be hashed; nothing written (locator withheld)")
        return 2
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    fd = None
    created = False
    try:
        fd = os.open(fpath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            f.write(_freeze_header(stamp))
            for k, digest in hashed:
                f.write("%s  %s\n" % (digest, k))
            f.flush()
            os.fsync(f.fileno())
    except (FileExistsError, OSError) as exc:
        if fd is not None:
            os.close(fd)
        # A mid-write failure previously left the half-written (or fully written but unsynced)
        # inventory on disk while reporting that nothing was written — and create-once then blocked
        # every supported repair (red-team 2026-08-09). This command owns the file only when its
        # own O_EXCL create succeeded, so remove exactly that and nothing else.
        if created and not isinstance(exc, FileExistsError):
            try:
                os.unlink(fpath)
            except OSError:
                print("freeze-legacy: inventory creation failed AND the partial inventory could not "
                      "be removed — delete it by hand before retrying (locator withheld)")
                return 2
        print("freeze-legacy: inventory creation failed closed (existing state retained)")
        return 2
    print("freeze-legacy: inventory written (patient locator and corpus count withheld)")
    return 0


def _freeze_header(stamp):
    return ("# Tabularium frozen pre-ADR-0039 legacy handout queue (L15). The lane is CLOSED:\n"
            "# files not listed here are RED, and a listed file whose BYTES change is RED too.\n"
            "# One entry per line, relative to med/handouts/:  <sha256><two spaces><relpath>\n"
            "# Create-once; replacement is forbidden (regeneration would re-bless current bytes).\n"
            "%s\n"
            "# generated: %s\n" % (_verify.LEGACY_FREEZE_MARKER, stamp))


def _cmd_migrate_legacy(a):
    """One-way v1 (names) -> v2 (names + SHA-256). ADR-0039 A6.

    Deliberately narrow, because this is the only command allowed to REPLACE an inventory:
      * refuses anything that is not a v1 inventory (a v2 re-hash would re-bless mutated bytes —
        the laundering command the closed lane exists to prevent);
      * admits NO key the v1 list did not already carry — migration is not a re-freeze;
      * a listed path that no longer exists is DROPPED, so the whitelist only ever shrinks. If such
        a file reappears later it reds as a post-adoption write, which is the correct reading of a
        closed lane (restore it from .snapshots/ and migrate deliberately, or seal it properly);
      * honest scope: the baseline is the bytes AT MIGRATION TIME, not at original authoring. A
        deliverable already mutated before today is blessed as-is — the same limit the original
        freeze had, and the reason this lane shrinks toward sealed units rather than growing.
    """
    handle = a.handle
    if not handle or handle.startswith(".") or os.path.isabs(handle) \
       or os.path.basename(handle) != handle or os.sep in handle \
       or (os.altsep and os.altsep in handle):
        print("migrate-legacy: invalid patient handle shape (locator withheld)")
        return 2
    hroot = os.path.join(a.root, "patients", handle, "med", "handouts")
    for p in (os.path.join(a.root, "patients"), os.path.dirname(os.path.dirname(hroot)),
              os.path.dirname(hroot), hroot):
        if os.path.islink(p) or not os.path.isdir(p):
            print("migrate-legacy: requested patient handouts tree is absent (locator withheld)")
            return 2
    fpath = os.path.join(hroot, _verify.LEGACY_FREEZE)
    if os.path.islink(fpath) or not os.path.isfile(fpath):
        print("migrate-legacy: no regular inventory to migrate (locator withheld)")
        return 2
    frozen = _verify.read_freeze(hroot)
    if frozen is None or frozen.errors:
        print("migrate-legacy: inventory is unreadable or structurally untrustworthy; "
              "restore it from .snapshots/ instead (locator withheld)")
        return 2
    if frozen.version != 1:
        print("migrate-legacy: inventory is already byte-bound; re-hashing is forbidden "
              "(it would re-bless current bytes)")
        return 2
    hashed = []
    hroot_abs = os.path.abspath(hroot)
    for key in sorted(frozen.entries):
        # containment: a '..' or absolute key from a hand-edited inventory must not make this
        # command hash — and thereby bless — a file outside the lane. Both sides are absolutized
        # before comparison (a relative-vs-absolute compare would refuse every ordinary key).
        target = os.path.normpath(os.path.join(hroot_abs, key))
        if os.path.isabs(key) or (target != hroot_abs and not target.startswith(hroot_abs + os.sep)):
            print("migrate-legacy: inventory carries a non-contained path; refusing (locator withheld)")
            return 2
        try:
            mode = os.lstat(target).st_mode
        except FileNotFoundError:
            continue          # migrated away / deleted: drop it, the whitelist only shrinks
        except OSError:
            print("migrate-legacy: inventoried entry could not be inspected; nothing written")
            return 2
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            print("migrate-legacy: inventoried entry is a symlink or non-regular file; nothing written")
            return 2
        if _verify.unsafe_freeze_key(key):
            # same injection class as freeze-legacy: an ambiguous key must never be rewritten into
            # the line-oriented v2 form (red-team 2026-08-09)
            print("migrate-legacy: inventoried path carries a line break or control character; "
                  "refusing to rewrite an ambiguous inventory (locator withheld)")
            return 2
        try:
            hashed.append((key, _verify._sha256(target)))
        except OSError:
            print("migrate-legacy: inventoried entry could not be hashed; nothing written")
            return 2
    if not set(k for k, _ in hashed) <= set(frozen.entries):
        # belt: migration must never admit a path the v1 list did not carry
        print("migrate-legacy: refusing to admit a path absent from the existing inventory")
        return 2
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    tmp = os.path.join(hroot, ".legacy-frozen.migrating")
    fd = None
    committed = False
    try:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            f.write(_freeze_header(stamp))
            f.write("# migrated from the v1 names-only inventory (ADR-0039 A6)\n")
            for key, digest in hashed:
                f.write("%s  %s\n" % (digest, key))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, fpath)   # atomic: a crash leaves either the v1 or the v2 inventory, never a torn one
        committed = True
        dirfd = os.open(hroot, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except OSError:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        if committed:
            # The replace already landed, so "existing inventory retained" would be a lie — and it
            # would steer the operator toward restoring the old inventory, the one action that
            # re-opens the re-bless path (red-team 2026-08-09). Report the true state instead.
            print("migrate-legacy: the migration WAS applied (the inventory on disk is the new "
                  "byte-bound one and verifies), but its durability barrier failed — do NOT restore "
                  "the previous inventory; re-run `verify` and treat only a power loss in this "
                  "window as suspect")
            return 2
        print("migrate-legacy: migration failed closed (existing inventory retained)")
        return 2
    print("migrate-legacy: inventory migrated to byte-bound form "
          "(patient locator and corpus count withheld)")
    return 0


class _NextIdStop(Exception):
    """next-id cannot answer; the message says why (no path, no content)."""


def _real_dir(path):
    return os.path.isdir(path) and not os.path.islink(path)


def _ids_in_folder(top, walk_names, notes, label):
    """Every stable ID in a folder of this person's: in a file name (when `walk_names`) and in the
    front matter of each regular Markdown file. Never follows a link, never opens anything else; what
    it skips or cannot read cleanly it says in `notes`, and any ID found inside an unclean value counts."""
    from . import handout_id as _hid
    found = []
    if os.path.islink(top):
        notes.append("%s is a link and was not read: IDs used there are not counted" % label)
        return found
    if not os.path.isdir(top):
        return found
    for dirpath, dirnames, filenames in os.walk(top, onerror=_raise_walk_error):
        linked = [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
        if linked:
            notes.append("a linked folder under %s was not read: IDs used there are not counted" % label)
        dirnames[:] = [d for d in dirnames if d not in linked]
        for name in filenames:
            full = os.path.join(dirpath, name)
            in_name = [m.group(0) for m in _hid.ID_IN_TEXT_RE.finditer(name)]
            if walk_names:
                found.extend(in_name)
            if not name.endswith(".md"):
                continue
            if os.path.islink(full) or not os.path.isfile(full):
                notes.append("a linked or special Markdown file under %s was not read" % label)
                continue
            value = (_owner.read_front_matter(full).get("id") or [""])[0]
            if _hid.ID_IN_TEXT_RE.fullmatch(value):
                found.append(value)
            elif _hid.front_matter_id_verdict(value):
                notes.append("a front-matter id under %s is not a clean stable ID (quoted, mis-cased or "
                             "with a look-alike or hidden character): correct it" % label)
                found.extend(m.group(0) for m in _hid.ID_IN_TEXT_RE.finditer(value.upper()))
            if not walk_names and in_name and not value:
                notes.append("a draft under %s carries its ID only in its file name (counted): put it in "
                             "the front matter" % label)
                found.extend(in_name)
    return found


# An ID-like token in INDEX.md: `TAB-` in any case and what follows it up to a space, a table bar or
# a template placeholder's `<`.
_INDEX_TOKEN_RE = re.compile(r'(?i)(?<![0-9a-z])tab-[^\s|<>`]+')
_TOKEN_EDGES = "\"'.,;:()[]*_"


def next_ids(root, handle, count=1, tag=None):
    """([next IDs], [notes]) for one person, read-only (ADR-0033 point 8). The tag is the
    one `med/handouts/INDEX.md` uses (or `tag`, which must agree with it); the number follows the
    highest one in use — in INDEX.md, a file name or front matter under med/handouts/, or the front
    matter of a draft under med/analysis/."""
    from . import handout_id as _hid
    if not handle or handle.startswith(".") or os.path.isabs(handle) \
       or os.path.basename(handle) != handle or os.sep in handle \
       or (os.altsep and os.altsep in handle):
        raise _NextIdStop("invalid patient handle shape")
    if not (isinstance(count, int) and 1 <= count <= 50):
        raise _NextIdStop("--count must be between 1 and 50")
    pdir = os.path.join(root, "patients", handle)
    med = os.path.join(pdir, "med")
    hroot = os.path.join(med, "handouts")
    index = os.path.join(hroot, "INDEX.md")
    if not all(_real_dir(p) for p in (os.path.join(root, "patients"), pdir, med, hroot)):
        raise _NextIdStop("no handout lane for this person (or a linked folder on the way)")
    if os.path.islink(index) or not os.path.isfile(index):
        raise _NextIdStop("no INDEX.md in the person's handout lane — start it from "
                          "_templates/person/med/handouts/INDEX.md")
    with open(index, encoding="utf-8", errors="replace") as f:
        index_text = f.read()
    index_ids = [m.group(0) for m in _hid.ID_IN_TEXT_RE.finditer(index_text)]
    tags = {i[4:7] for i in index_ids}
    notes = ["INDEX.md lists %s, whose check character is wrong: if that handout is still in use, "
             "supersede it with a new unit" % i for i in sorted(set(index_ids)) if _hid.id_problem(i)]
    for token in sorted({m.group(0).strip(_TOKEN_EDGES) for m in _INDEX_TOKEN_RE.finditer(index_text)}):
        if not _hid.ID_IN_TEXT_RE.fullmatch(token):
            notes.append("INDEX.md holds %s, which is not a clean stable ID: correct it" % token)
    if tag is not None:
        if not _hid.TAG_RE.fullmatch(tag):
            raise _NextIdStop("--tag must be three Crockford symbols (0-9, A-Z without I L O U)")
        if tags and tags != {tag}:
            raise _NextIdStop("--tag differs from the tag INDEX.md uses — check whose register this is")
    elif len(tags) == 1:
        tag = tags.pop()
    elif not tags:
        raise _NextIdStop("INDEX.md holds no stable ID yet: pass --tag <PPP>, the person's tag "
                          "recorded in their profile.md")
    else:
        raise _NextIdStop("INDEX.md uses more than one person tag — resolve that before numbering")
    in_use = (index_ids + _ids_in_folder(hroot, True, notes, "med/handouts")
              + _ids_in_folder(os.path.join(med, "analysis"), False, notes, "med/analysis"))
    if any(i[4:7] != tag for i in in_use):
        notes.append("a stable ID with another person tag sits in this person's folder — check whose "
                     "document it is")
    top = max([int(i[8:11]) for i in in_use if i[4:7] == tag] or [0])
    if top + count > 999:
        raise _NextIdStop("the sequence would pass 999")
    return ([_hid.make_id(tag, n) for n in range(top + 1, top + count + 1)],
            list(dict.fromkeys(notes)))


def _cmd_next_id(a):
    try:
        ids, notes = next_ids(a.root, a.handle, a.count, a.tag)
    except (_NextIdStop, OSError) as e:
        reason = str(e) if isinstance(e, _NextIdStop) else "a file could not be read (locator withheld)"
        print("next-id: " + reason, file=sys.stderr)
        return 2
    for note in notes:
        print("next-id: note: " + note, file=sys.stderr)
    for handout_id in ids:
        print(handout_id)
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="python3 -m tools.handout_attest",
                                 description="Sealed-handout attestation verification (ADR-0039)")
    ap.add_argument("--root", default=os.getcwd(), help="repository root (default: cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify", help="L15 fail-closed sealed-handout check")
    fl = sub.add_parser("freeze-legacy",
                        help="create a patient's legacy inventory once (replacement forbidden)")
    fl.add_argument("handle", help="patient folder handle under patients/")
    ml = sub.add_parser("migrate-legacy",
                        help="one-way v1->v2 (byte-binding) migration of an existing inventory")
    ml.add_argument("handle", help="patient folder handle under patients/")
    ni = sub.add_parser("next-id", help="print the person's next free handout ID(s) with their "
                        "check characters (read-only, ADR-0033)")
    ni.add_argument("handle", help="patient folder handle under patients/")
    ni.add_argument("--count", type=int, default=1, help="how many consecutive IDs (default 1)")
    ni.add_argument("--tag", default=None,
                    help="the person's <PPP> tag; needed only while INDEX.md holds no stable ID")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    return {"verify": _cmd_verify,
            "freeze-legacy": _cmd_freeze_legacy,
            "migrate-legacy": _cmd_migrate_legacy,
            "next-id": _cmd_next_id}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
