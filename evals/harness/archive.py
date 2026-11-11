#!/usr/bin/env python3
"""archive.py — a paid run's folder becomes one verified archive file, in a folder of the operator's choosing.

WHY. A run that spends keeps every before-tree, after-tree and transcript — the evidence `regrade`
re-judges and ADR-0049 cites by run root name. Kept in `~/tab-eval-scratch` (operator decision
2026-10-06) they filled the disk: 75 run folders of about 15 MB and 1,000 files each, 1.3 GB by
2026-10-25. Since then (operator, 2026-10-25) a paid run, whatever its outcome, ends here: its folder is
packed into `<run root name>.tar.zst` (`.tar.gz` where this Python has no zstd), read back from where
it was written and matched entry by entry — kind, size and SHA-256 of every file — against the folder
as it is right then, and only then is the local folder removed. Anything short of a matched archive
keeps the local folder and says so.

    python3 -m evals.harness.archive restore <run root name> [--into DIR]   # back where it ran
    python3 -m evals.harness.archive existing [--dry-run]   # every finished run root a session ran in
    python3 -m evals.harness.archive one <run root>

WHERE. On this disk by default: `archive/` in the scratch folder. Any other folder is the operator's
choice and names no provider (operator, 2026-10-25 and 2026-10-26): `TAB_EVAL_ARCHIVE_DIR`, or else the
first line of `~/.config/tabularium-eval/archive-dir`, holds
  <a folder>     an absolute path: a cloud sync folder (iCloud Drive, Dropbox, Google Drive, ...), an external drive, a network share. One that does not exist is never
                 created, so an unmounted drive cannot swallow a run.
  off            no archive; the folder stays.
Output never prints a cloud sync folder's own name (under `~/Library/CloudStorage` it carries the
account): it shows `<sync folder>` in its place. Eval archives hold invented patients and the tool's
own text, so no encryption is required of the folder; records follow the offsite backup's stricter
rule (`checks/backup-offsite.sh`).

WHAT NEVER ENTERS AN ARCHIVE. `config/` is the CLI's own folder for the run — the account file,
policy files, backups and, in the fallback auth mode, a copied credential file
(`session.make_clean_config`). Only its one-line `.eval-auth-mode` is archived; nothing else in it is
opened. The rest of a run root holds invented patients only.

ONLINE-ONLY (a set folder that macOS's File Provider keeps; an external drive has nothing to evict).
macOS 26's `fileproviderctl` has no evict command; Foundation's
`evictUbiquitousItemAtURL:error:` does it for any File Provider folder (measured on one provider's), once
the file has uploaded (measured 2026-10-25: refused until then, about 4 s for 3 MB). An eviction is
reported only when the file is seen dataless on disk; otherwise the run says so and points to Finder's
"Remove Download". Reading an evicted archive (a restore) downloads it again; the restore then evicts
it again.
"""

import argparse
import collections
import contextlib
import hashlib
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.harness import paths  # noqa: E402  (needs the path bootstrap above)

DEST_ENV = "TAB_EVAL_ARCHIVE_DIR"
CONFIG_FILE = Path.home() / ".config" / "tabularium-eval" / "archive-dir"
LOCAL_SUBDIR = "archive"
#: Where macOS keeps cloud sync folders; each one's own name carries its account, so output withholds it.
CLOUD_STORAGE = Path.home() / "Library" / "CloudStorage"
#: What `run_eval.make_run_root` makes: a `tab-eval-` folder holding these four. Nothing else is
#: archived or removed by this module, so a wrong path can never cost an unrelated folder.
RUN_SUBDIRS = ("fixtures", "pre", "transcripts", "config")
RUN_NAME = re.compile(r"^tab-eval-[A-Za-z0-9_]+$")
KEPT_CONFIG = frozenset({"config/.eval-auth-mode"})
#: The run root's absolute path, kept in the archive's header: the comparison and stress ledgers
#: find a run's evidence by that path, so a restore goes back there by default.
ORIGIN_HEADER = "tabularium.run_root"
SF_DATALESS = getattr(stat, "SF_DATALESS", 0x40000000)
EVICT_WAIT = 120
#: The backfill leaves a run root alone while any of its files is younger than this: a run may still
#: be going in another session. It outlasts the longest stretch a live run can go without a write (a
#: guard check may take 30 minutes; Codex review, 2026-10-26).
RECENT = 2 * 60 * 60

Result = collections.namedtuple("Result", "status archive evicted why")
#: Where archives go: `folder` (None: nowhere, `why`), and whether it was set (a set folder may be one
#: a File Provider keeps, so eviction is asked for; the local default never is).
Dest = collections.namedtuple("Dest", "folder why cloud")


class Mismatch(Exception):
    """The archive read back is not the run root minus the exclusions."""


def scrub(msg):
    """`msg` with every cloud sync folder's own name (its account) withheld, as `shown` does: each
    name actually under CloudStorage replaced exactly, spaces and quotes and all, then any other path
    there cut at its next slash. Every line this module prints, and every refusal, goes through it."""
    base = str(CLOUD_STORAGE)
    try:
        names = sorted(os.listdir(base), key=len, reverse=True)
    except OSError:
        names = []
    for name in names:
        msg = msg.replace(os.path.join(base, name), shown(CLOUD_STORAGE / name))
    return re.sub(re.escape(base) + r"/[^/\n]+", lambda m: shown(m.group(0)), msg)


def say(msg):
    print(scrub(msg), flush=True)


def loud(msg):
    """One marked line to stderr, withheld like every other line (`scrub`)."""
    print("!! " + scrub(msg), file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- where

def setting():
    """`(value, where it came from)`: `TAB_EVAL_ARCHIVE_DIR`, else the config file's first line, else
    `(None, None)`."""
    value = os.environ.get(DEST_ENV, "").strip()
    if value:
        return value, DEST_ENV
    try:
        lines = CONFIG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, None
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            return line, shown(CONFIG_FILE)
    return None, None


def destination():
    """Where archives go, as a `Dest`."""
    value, source = setting()
    if value is None:
        folder = scratch_base() / LOCAL_SUBDIR
        paths.ensure_dir(folder)
        return Dest(folder, None, False)
    if value.lower() == "off":
        return Dest(None, "archiving is off (%s)" % source, False)
    folder = Path(value).expanduser()
    if not folder.is_absolute():
        return Dest(None, "%s holds %r, which is neither `off` nor an absolute folder path" % (source, value), False)
    if not folder.is_dir():
        return Dest(None, "%s names no existing folder (create it, or fix the setting)" % source, False)
    return Dest(folder, None, True)


def shown(path):
    """`path` for output: home-relative, with a cloud sync folder's own name (its account) withheld."""
    path = Path(path)

    def home_relative(p):
        try:
            return "~/" + p.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(p)
    try:
        parts = path.relative_to(CLOUD_STORAGE).parts
    except ValueError:
        return home_relative(path)
    return "/".join([home_relative(CLOUD_STORAGE)] + (["<sync folder>"] + list(parts[1:]) if parts else []))


def scratch_base():
    from evals.harness import run_eval
    return Path(os.environ.get("TAB_EVAL_SCRATCH") or run_eval.DURABLE_SCRATCH)


def archive_format():
    """`zst` where this Python can write it (3.14+), else `gz`."""
    try:
        import compression.zstd  # noqa: F401
        return "zst"
    except ImportError:
        return "gz"


def archive_in(folder, name):
    """The archive of run root `name` already in `folder`, or None."""
    for fmt in ("zst", "gz"):
        path = Path(folder) / ("%s.tar.%s" % (name, fmt))
        if path.is_file():
            return path
    return None


def is_run_root(root):
    root = Path(root)
    return (RUN_NAME.match(root.name) is not None and root.is_dir() and not root.is_symlink()
            and all((root / sub).is_dir() for sub in RUN_SUBDIRS))


# --------------------------------------------------------------------------- what

def archived(rel):
    """Whether a run-root-relative path goes into the archive: all but `config/`'s contents, of
    which only `.eval-auth-mode` is kept."""
    parts = rel.split("/")
    return parts[0] != "config" or len(parts) == 1 or rel in KEPT_CONFIG


def walk(root):
    """`(relative path, lstat)` of every entry the archive must hold, each folder before its contents, sorted.
    Excluded folders are never entered."""
    def entries(folder, prefix):
        for entry in sorted(os.scandir(folder), key=lambda e: e.name):
            rel = prefix + entry.name
            if not archived(rel):
                continue
            st = os.lstat(entry.path)
            yield rel, st
            if stat.S_ISDIR(st.st_mode):
                yield from entries(entry.path, rel + "/")
    return entries(str(root), "")


def _digest(fh):
    h = hashlib.sha256()
    for block in iter(lambda: fh.read(1 << 20), b""):
        h.update(block)
    return h.hexdigest()


def tree_entries(root):
    """`{relative path: (kind, size, digest or link target)}` of the run root minus the exclusions."""
    out = {}
    for rel, st in walk(root):
        if stat.S_ISDIR(st.st_mode):
            out[rel] = ("dir", 0, "")
        elif stat.S_ISREG(st.st_mode):
            with open(os.path.join(str(root), rel), "rb") as fh:
                out[rel] = ("file", st.st_size, _digest(fh))
        elif stat.S_ISLNK(st.st_mode):
            out[rel] = ("link", 0, os.readlink(os.path.join(str(root), rel)))
        else:
            out[rel] = ("other", 0, "")     # a tar cannot carry it, so the match fails: kept
    return out


def archive_entries(path, name):
    """The same map, read back out of the archive at `path`. Every member must sit in `name/`."""
    out = {}
    with tarfile.open(str(path), "r:*") as tf:
        for m in tf:
            if m.name == name and m.isdir():
                continue
            if not m.name.startswith(name + "/"):
                raise Mismatch("a member outside %s/: %s" % (name, m.name))
            rel = m.name[len(name) + 1:]
            if rel in out:
                raise Mismatch("a member twice: %s" % rel)
            if m.isdir():
                out[rel] = ("dir", 0, "")
            elif m.isfile():
                out[rel] = ("file", m.size, _digest(tf.extractfile(m)))
            elif m.issym():
                out[rel] = ("link", 0, m.linkname)
            else:
                out[rel] = ("other", 0, "")
    return out


def origin_of(path):
    """The run root's path when it was archived, from the archive's header, or None."""
    with tarfile.open(str(path), "r:*") as tf:
        tf.next()
        value = tf.pax_headers.get(ORIGIN_HEADER)
    return Path(value) if value else None


def newest_write(root):
    """The newest modification time of any file under `root` (0 when it holds none)."""
    return max((st.st_mtime for _name, st in walk_all(root)), default=0)


def ran_sessions(root):
    """Whether any session ran in this run root: the CLI wrote its config, or a transcript exists.
    A rehearsal (a dry run kept with --keep under TAB_EVAL_SCRATCH) or a run stopped before its
    first session has neither."""
    return any(any(os.scandir(str(Path(root) / sub))) for sub in ("config", "transcripts"))


def compare(want, got):
    """None when the two maps match, else a short account of the first differences."""
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    changed = sorted(r for r in set(want) & set(got) if want[r] != got[r])
    if not (missing or extra or changed):
        return None
    parts = []
    for label, items in (("missing", missing), ("unexpected", extra), ("different", changed)):
        if items:
            parts.append("%d %s (%s%s)" % (len(items), label, ", ".join(items[:3]),
                                           ", ..." if len(items) > 3 else ""))
    return "; ".join(parts)


def write_archive(root, target, fmt):
    root = Path(root)

    def scrub(info):
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info

    with tarfile.open(str(target), "w:" + fmt, format=tarfile.PAX_FORMAT,
                      pax_headers={ORIGIN_HEADER: str(root)}) as tf:
        tf.add(str(root), arcname=root.name, recursive=False, filter=scrub)
        for rel, _st in walk(root):
            tf.add(str(root / rel), arcname="%s/%s" % (root.name, rel), recursive=False, filter=scrub)


# --------------------------------------------------------------------------- online-only

def is_dataless(path):
    """True when the File Provider holds `path`'s bytes online only (APFS's dataless flag)."""
    try:
        return bool(getattr(os.stat(str(path)), "st_flags", 0) & SF_DATALESS)
    except OSError:
        return False


def _evict_request(path):
    """Ask macOS's File Provider to drop the local copy of `path`. Returns `(state, why)`, state
    one of `requested`, `pending` (not uploaded yet, or refused for now) or `unsupported`."""
    if sys.platform != "darwin":
        return "unsupported", "eviction needs macOS's File Provider"
    import ctypes
    import ctypes.util
    objc = ctypes.CDLL(ctypes.util.find_library("objc"))
    foundation = ctypes.CDLL(ctypes.util.find_library("Foundation"))
    objc.objc_getClass.restype = objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = objc.sel_registerName.argtypes = [ctypes.c_char_p]

    def send(restype, *argtypes):
        return ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(("objc_msgSend", objc))

    def cls(name):
        return objc.objc_getClass(name.encode())

    def sel(name):
        return objc.sel_registerName(name.encode())

    def text(nsstring):
        return (send(ctypes.c_char_p)(nsstring, sel("UTF8String")) or b"").decode("utf-8", "replace")

    def flag(url, key):
        value, err = ctypes.c_void_p(0), ctypes.c_void_p(0)
        key_obj = ctypes.c_void_p.in_dll(foundation, key)
        ok = send(ctypes.c_bool, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            url, sel("getResourceValue:forKey:error:"), ctypes.byref(value), key_obj, ctypes.byref(err))
        return bool(ok and value.value and send(ctypes.c_bool)(value.value, sel("boolValue")))

    pool = send(ctypes.c_void_p)(send(ctypes.c_void_p)(cls("NSAutoreleasePool"), sel("alloc")), sel("init"))
    try:
        string = send(ctypes.c_void_p, ctypes.c_char_p)(cls("NSString"), sel("stringWithUTF8String:"),
                                                       os.fsencode(str(path)))
        url = send(ctypes.c_void_p, ctypes.c_void_p)(cls("NSURL"), sel("fileURLWithPath:"), string)
        if not flag(url, "NSURLIsUbiquitousItemKey"):
            return "unsupported", "the folder is not kept by a File Provider"
        if not flag(url, "NSURLUbiquitousItemIsUploadedKey"):
            return "pending", "not uploaded yet"
        err = ctypes.c_void_p(0)
        manager = send(ctypes.c_void_p)(cls("NSFileManager"), sel("defaultManager"))
        ok = send(ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            manager, sel("evictUbiquitousItemAtURL:error:"), url, ctypes.byref(err))
        if ok:
            return "requested", None
        return "pending", text(send(ctypes.c_void_p)(err.value, sel("localizedDescription"))) if err.value else "refused"
    finally:
        send(None)(pool, sel("drain"))


def evict_and_confirm(path, request=_evict_request, dataless=is_dataless, wait=EVICT_WAIT, poll=2.0):
    """Ask for `path` to go online-only until it is seen dataless or `wait` seconds pass. Returns
    `(confirmed, why not)`: True only when the flag on disk says so, never on the request's answer;
    None when no File Provider keeps the folder (nothing to evict); False otherwise."""
    deadline = time.monotonic() + wait
    why = None
    while True:
        if dataless(path):
            return True, None
        try:
            state, why = request(path)
        except Exception as exc:                  # noqa: BLE001 — a failed request is "not confirmed",
            return False, "%s: %s" % (type(exc).__name__, exc)   # never "nothing to evict"
        if state == "unsupported":
            return None, why
        if state == "requested" and dataless(path):
            return True, None
        if time.monotonic() >= deadline:
            return False, why or "the File Provider has not dropped the local copy"
        time.sleep(poll)


def report_eviction(path, confirmed, why):
    if confirmed:
        say("archive: online-only — the local copy was evicted, confirmed on disk")
    elif confirmed is None:
        say("archive: nothing to evict (%s)" % why)
    else:
        loud("archive: NOT confirmed online-only (%s). The archive matched and sits in its folder, "
             "still downloaded; if its upload has not finished, it is not yet off this machine. To free "
             "the space later, in Finder right-click it and choose Remove Download: %s" % (why, shown(path)))


# --------------------------------------------------------------------------- one run

def walk_all(root):
    """Every file under `root`, config/ included — only to tell an empty run root from one that ran."""
    for dirpath, _dirs, files in os.walk(str(root)):
        for name in files:
            yield name, os.lstat(os.path.join(dirpath, name))


def archive_run(root, dest=None, evict=None, label="run"):
    """Archive one run root, match it, then remove the local folder. Returns a `Result` whose status
    is `archived`, `empty` (no file at all: nothing ran, the folder is removed) or `kept`. Never raises
    for an archiving failure: the local folder is the fallback, and the run's own result stands."""
    root = Path(root)
    if not is_run_root(root):
        loud("archive: %s is not a run root; left alone" % root)
        return Result("kept", None, False, "not a run root")
    try:
        if not any(stat.S_ISREG(st.st_mode) for _name, st in walk_all(root)):
            shutil.rmtree(str(root))
            say("archive: the %s's folder held no file (nothing ran); removed: %s" % (label, root))
            return Result("empty", None, False, None)
    except OSError as exc:
        loud("archive: could not read %s (%s); kept" % (root, exc))
        return Result("kept", None, False, str(exc))
    try:
        dest = dest or destination()
    except Exception as exc:                      # noqa: BLE001 — e.g. a file where archive/ goes
        dest = Dest(None, "cannot make the archive folder (%s: %s)" % (type(exc).__name__, exc), False)
    if dest.folder is None:
        loud("archive: the %s was NOT archived — %s. Its folder stays at %s" % (label, dest.why, root))
        return Result("kept", None, False, dest.why)
    folder = dest.folder
    name = root.name
    real_root = os.path.realpath(str(root))
    if os.path.commonpath([os.path.realpath(str(folder)), real_root]) == real_root:
        # Its `config/` is left out of the archive, so a destination there would match and then go
        # with the folder it archives (Codex review, 2026-10-26).
        why = "the destination %s is inside the run's own folder" % shown(folder)
        loud("archive: the %s was NOT archived — %s. Its folder stays at %s" % (label, why, root))
        return Result("kept", None, False, why)
    part = None
    try:
        # The folder is hashed AFTER the archive is read back, right before anything is removed, so
        # a file that changed after it was packed is a mismatch, never a silent loss.
        final = archive_in(folder, name)
        if final is not None:
            # Archived before: a restored run, or a backfill that stopped part-way.
            got = archive_entries(final, name)
            problem = compare(tree_entries(root), got)
            if problem:
                loud("archive: %s already exists and differs from the folder (%s); nothing replaced, "
                     "the folder stays at %s" % (shown(final), problem, root))
                return Result("kept", final, False, problem)
            how = "already in"
        else:
            fmt = archive_format()
            final = Path(folder) / ("%s.tar.%s" % (name, fmt))
            # Created exclusively, so a second archiver of the same run never writes into this
            # one's file between its check and its rename (Codex review, 2026-10-26).
            fd, tmp_name = tempfile.mkstemp(prefix=".%s." % final.name, suffix=".part", dir=str(folder))
            os.close(fd)
            part = Path(tmp_name)
            write_archive(root, part, fmt)
            got = archive_entries(part, name)
            problem = compare(tree_entries(root), got)
            if problem:
                raise Mismatch(problem)
            os.replace(str(part), str(final))
            part = None
            how = "written to"
    except Exception as exc:                      # noqa: BLE001 — every failure keeps the folder
        loud("archive: the %s was NOT archived — %s: %s. Its folder stays at %s"
             % (label, "the archive read back does not match" if isinstance(exc, Mismatch)
                else type(exc).__name__, exc, root))
        return Result("kept", None, False, str(exc))
    finally:
        if part is not None:                      # a failed or interrupted write leaves no partial file
            with contextlib.suppress(OSError):
                part.unlink()
    files = sum(1 for kind, _s, _d in got.values() if kind == "file")
    say("archive: %s %s %s, read back and matched (%d files; of config/ only .eval-auth-mode)"
          % (name, how, shown(final), files))
    try:
        shutil.rmtree(str(root))
        say("archive: local folder removed: %s" % root)
    except OSError as exc:
        loud("archive: the archive matched, but removing the local folder failed part-way (%s): %s"
             % (exc, root))
    if dest.cloud:
        confirmed, why = (evict or evict_and_confirm)(final)
        report_eviction(final, confirmed, why)
    else:
        confirmed, why = None, "local archive"
        say("archive: kept in %s, the default; to keep archives elsewhere (a cloud sync folder, an external "
              "drive), put that folder's path in %s (harness README, Where archives go)"
              % (shown(folder), shown(CONFIG_FILE)))
    say("archive: restore with: python3 -m evals.harness.archive restore %s" % name)
    return Result("archived", final, confirmed is True, why)


# --------------------------------------------------------------------------- restore

def restore(name, into=None, evict=None):
    """Unpack one archived run into the scratch folder (or `into`), matched before it appears."""
    if not RUN_NAME.match(name or ""):
        raise SystemExit(scrub("not a run root name: %r (expected tab-eval-...)" % name))
    if not hasattr(tarfile, "data_filter"):
        raise SystemExit(scrub("restore needs a Python whose tarfile has the data filter (3.12 or later)"))
    dest = destination()
    if dest.folder is None:
        raise SystemExit(scrub("cannot restore: %s" % dest.why))
    source = archive_in(dest.folder, name)
    if source is None:
        raise SystemExit(scrub("no archive of %s in %s" % (name, shown(dest.folder))))
    origin = origin_of(source)
    if into:
        base = Path(into)
    elif origin is not None and origin.name == name:
        base = origin.parent
    else:
        base = scratch_base()
    if origin is not None and base / name != origin:
        loud("restoring %s to %s, not where it ran (%s): the comparison and stress ledgers find its "
             "evidence by that path, so their --regrade and --report will not" % (name, base / name, origin))
    paths.ensure_dir(base)
    target = base / name
    if os.path.lexists(str(target)):
        raise SystemExit(scrub("refusing to restore over %s: it already exists (use it as it is, or restore "
                               "elsewhere with --into DIR)" % target))
    staging = Path(tempfile.mkdtemp(prefix=".restore-", dir=str(base)))
    try:
        want = archive_entries(source, name)
        with tarfile.open(str(source), "r:*") as tf:
            tf.extractall(str(staging), filter="data")
        problem = compare(want, tree_entries(staging / name))
        if problem:
            raise SystemExit(scrub("restore of %s does not match its archive (%s); nothing restored"
                                   % (name, problem)))
        os.rename(str(staging / name), str(target))
    finally:
        shutil.rmtree(str(staging), ignore_errors=True)
    say("restored %s to %s (config/ held only .eval-auth-mode); regrade and --report work on it again"
          % (name, target))
    if dest.cloud:
        confirmed, why = (evict or evict_and_confirm)(source)
        report_eviction(source, confirmed, why)
    return 0


# --------------------------------------------------------------------------- existing runs

def archive_existing(base=None, dry_run=False, evict=None):
    """Archive every run root in the scratch folder, one at a time, each matched before it goes."""
    base = Path(base) if base else scratch_base()
    if not base.is_dir():
        say("no scratch folder at %s; nothing to archive" % base)
        return 0
    candidates = [p for p in sorted(base.iterdir()) if is_run_root(p)]
    recent = [p for p in candidates if time.time() - newest_write(p) < RECENT]
    roots = [p for p in candidates if p not in recent and ran_sessions(p)]
    idle = [p.name for p in candidates if p not in roots and p not in recent]
    others = sum(1 for p in base.iterdir() if p not in candidates)
    if recent:
        say("left alone, written in the last %d minutes (a run may still be going): %s"
              % (RECENT // 60, ", ".join(p.name for p in recent)))
    if idle:
        say("left alone, no session ran in them (a kept rehearsal, or a run stopped before its first "
              "session): %s. To archive one anyway: python3 -m evals.harness.archive one <path>" % ", ".join(idle))
    if dry_run:
        for root in roots:
            n = sum(1 for _ in walk_all(root))
            say("would archive %s (%d files)" % (root.name, n))
        say("%d run roots would be archived; %d recent, %d without a session and %d other entries in %s "
              "left alone" % (len(roots), len(recent), len(idle), others, base))
        return 0
    dest = destination()
    if dest.folder is None:
        loud("nothing archived: %s" % dest.why)
        return 2
    tally = collections.Counter()
    kept = []
    for i, root in enumerate(roots, 1):
        say("[%d/%d] %s" % (i, len(roots), root.name))
        result = archive_run(root, dest, evict=evict, label="run")
        tally[result.status] += 1
        tally["evicted"] += int(result.evicted)
        if result.status == "kept":
            kept.append(root.name)
    say("%d archived (%d confirmed online-only), %d empty removed, %d kept; %d recent, %d without a "
          "session and %d other entries left alone" % (tally["archived"], tally["evicted"], tally["empty"],
                                                        tally["kept"], len(recent), len(idle), others))
    if kept:
        loud("kept, not archived: %s" % ", ".join(kept))
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m evals.harness.archive",
                                 description="Archive paid eval runs to a folder of your choosing; restore one")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("restore", help="download and unpack one archived run into the scratch folder")
    r.add_argument("name", help="the run root's name, e.g. tab-eval-why9jaka")
    r.add_argument("--into", help="unpack here instead (default: where the run ran; comparison and stress "
                                  "--regrade/--report need that place)")
    e = sub.add_parser("existing", help="archive every run root in the scratch folder, removing each "
                                        "local folder only once its archive matched")
    e.add_argument("--dry-run", action="store_true", help="list what would be archived; change nothing")
    o = sub.add_parser("one", help="archive one run root, as a paid run does at its end")
    o.add_argument("root")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "restore":
            return restore(args.name, args.into)
        if args.cmd == "existing":
            return archive_existing(dry_run=args.dry_run)
        return 0 if archive_run(Path(os.path.abspath(args.root))).status in ("archived", "empty") else 1
    except Exception as exc:                      # noqa: BLE001 — printed withheld, not as a raw traceback
        loud("%s: %s" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
