#!/usr/bin/env python3
"""registry-read-guard — a Claude Code PreToolUse hook (ADR-0050 A1 and point 9).

WHAT IT PROTECTS. One thing a model session must never see: the private-mode identifier
(ADR-0029). Since the operator's decision of 2026-09-14 it lives in its own small owner-only file
outside every repository, named by the untracked pointer `checks/PRIVATE-MODE-ID`. The rest of the
token registry stops being secret from sessions once that split is verified.

A DELIBERATELY SMALL RULE SET (operator, 2026-09-16: keep the guards to a high-confidence minimum and
grow them only when a real need shows up). A call is denied only when it is near-certainly a read of
a protected file:

  * a file tool (Read, Edit, Write, MultiEdit, NotebookEdit) on a protected file or its pointer —
    compared by resolved path, case-insensitively and by inode, so a symlink, a case variant or a
    hard link is the same file — or on any file NAMED like one (`private-mode-id.sh`,
    `PRIVATE-MODE-ID`, anywhere: a snapshot's banked copy is still the file);
  * a content-mode Grep over a protected file or its directory;
  * a shell command (Bash, Monitor, the terminal tool) in which a command reads a protected file or
    pointer — an operand spelled literally, with `~`/`$HOME`, relative, after `cd`, through one
    variable assignment, inside `$(…)` or backticks (in an argument, an assignment, an unquoted
    here-document body or any redirection operand — a here-string, an input, a write target), a
    `-c` / `eval` code string, or a here-document or here-string a shell runs as its script
    (`bash -s <<'EOF'`, `cat <<'EOF' | sh`, `bash <<<'…'`; not `bash -c … <<'EOF'`, whose stdin is
    data), judged as the command line it is; a glob matching one; a path named like one; or a
    protected file's own directory — unless that command is metadata only (`ls`, `stat`, `wc`, `test`, `find` without
    `-exec`, `git` without `--no-index`, …; never a digest: a hash of a one-line file is
    brute-forceable back to the identifier) and nothing in the same part of the line turns the names
    it prints into reads (`xargs`, a loop, a shell, `awk`, `$(…)`).

DATA IS NOT JUDGED. Here-document bodies and redirection operands — a write target, a here-string's
text — are data, apart from the `$(…)` and backtick spans in them, which the shell runs, and
standard input a shell in the same pipeline runs as its script (judged whole, as if typed): writing prose
or a synthetic fixture that mentions these names reads nothing. A here-document inside `$(…)` — even
within double quotes, where the shell reads commands again — is found too: read by a bare `cat` (the
commit-message idiom, `-m "$(cat <<'EOF' … EOF)"`) it becomes a string, judged as a path where it is
one and word by word where its part of the line runs a shell or an interpreter or reads names; with
any other reader inside double quotes it stays in its word, as before. Neither is a shell comment (a `#`
that begins a word outside quotes, to the end of its line or, inside backticks, to the closing one —
removed, quote-aware, before the words are read), nor a word that only names a protected file
without being a path to it — a grep pattern, a commit message. A backtick substitution is judged as the `$(…)` it is rewritten to.

UNTIL THE SPLIT IS VERIFIED the token registry and its pointer (`checks/FIREWALL-REGISTRY`) are
protected by the same rules as the private file: `checks/install-instance.sh` verifies the split
and only then writes `--split-verified`.

WHERE THE PATHS COME FROM. The installer writes them into this hook's command line:
    --private <absolute path>   --registry <absolute path>   [--split-verified]
With no arguments (settings from an older installer) the hook reads the two pointers in
`$CLAUDE_PROJECT_DIR/checks/` and never treats the split as verified. No checkout-family
derivation runs here.

FAIL CLOSED. A PreToolUse hook blocks only on exit 2, so every denial is exit 2 with the reason on
stderr, and any exception while deciding denies when the raw input names a protected file, a
pointer or the registry. Otherwise the call gets no opinion (exit 0, silent).

A hook is a discipline aid, not an enforcement boundary: it closes the honest-slip class, not an
adversary. The residuals it knowingly leaves are listed in tools/claude-hooks/README.md.
Matrix: test_registry_guard.py.
"""
import fnmatch
import functools
import glob
import itertools
import json
import os
import re
import shlex
import stat
import sys
from urllib.parse import unquote, urlsplit

PRIVATE_POINTER = "PRIVATE-MODE-ID"
REGISTRY_POINTER = "FIREWALL-REGISTRY"
PRIVATE_DEFAULT = "private-mode-id.sh"
REGISTRY_DEFAULT = "firewall-registry.sh"

# Commands that tell you about a file without printing its bytes. Digest tools are deliberately
# absent: a SHA-256 of a one-line file is a brute-force target, and the private file is one line.
# `file` is absent too: `file -f` prints the lines of the file it is given.
META = {"ls", "stat", "wc", "du", "test", "[", "[[", "cd", "pushd", "popd", "realpath", "readlink",
        "basename", "dirname", "echo", "printf", "true", "false", "pwd", "mkdir", "chmod", "touch",
        "xattr", "which", "type", ":", "export", "local", "readonly", "declare"}
# In the same part of a line as a command that names protected paths, these turn names into reads.
NAME_CONSUMERS = {"xargs", "parallel", "while", "until", "for", "read", "do", "source", ".", "eval",
                  "exec", "awk", "gawk", "nawk", "sed", "gsed", "env", "sudo", "nohup", "nice", "time",
                  "timeout", "stdbuf", "script", "watch", "command", "builtin"}
INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "python", "python3", "perl", "ruby", "node",
                "osascript", "eval"}
# Standard input a shell runs as its script (a here-document, a here-string) is judged as a command
# line, not as data. Wrappers put the command they run later on the line; options with a value:
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
WRAPPERS = {"env", "sudo", "nohup", "nice", "time", "timeout", "gtimeout", "stdbuf", "command",
            "builtin", "exec", "busybox", "arch", "caffeinate", "script"}
RESERVED = {"if", "then", "else", "elif", "while", "until", "do", "!", "{", "coproc"}
SHELL_VALUE_OPTS = {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}
STDIN_FILES = ("-", "/dev/stdin", "/dev/fd/0")
SUDO_SHELL = {"-s", "-i", "--shell", "--login"}
BASE_LIMIT = 32     # `cd` targets tried per call beyond those at or above a protected directory
SHELL_TOOLS = {"Bash", "Monitor", "mcp__terminal__run_in_terminal"}
GREPS = {"grep", "egrep", "fgrep", "rg", "ugrep", "ug", "ag"}
# Options whose next word is a value, not the pattern and not a file (rg's differ from grep's: `-E`
# is an encoding there, `-r` a replacement).
GREP_VALUE_OPTS = {"-m", "-A", "-B", "-C", "-d", "-D", "--max-count", "--context", "--after-context",
                   "--before-context", "--include", "--exclude", "--exclude-dir", "--binary-files",
                   "--label", "--devices", "--directories"}
RG_VALUE_OPTS = GREP_VALUE_OPTS | {"-g", "--glob", "--iglob", "-t", "--type", "-T", "--type-not", "-E",
                                  "--encoding", "-j", "--threads", "-M", "--max-columns", "--sort",
                                  "--sortr", "--max-depth", "--maxdepth", "--pre", "--pre-glob",
                                  "--type-add", "-r", "--replace", "--max-filesize", "--path-separator"}
GIT_REACH = {"--no-index", "-C", "--git-dir", "--work-tree", "-c", "--exec-path", "hash-object"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
GROUP_SEPARATORS = {";", "&&", "||", "&", "\n", ";;", ";&", ";;&"}
STATEMENT_BREAKS = {"|", "|&", "(", ")", "<(", ">("}
OPERATORS = sorted(["&&", "||", ";;&", ";;", ";&", "|&", ">>", "<<<", "<<-", "<<", "&>>", "&>", ">&",
                    "<&", "<>", ">|", "<(", ">(", ";", "&", "|", "(", ")", "<", ">", "\n"],
                   key=len, reverse=True)
PUNCT = set(";&|()<>\n")
GLOB_LIMIT = 1000
CODE_ATOM = re.compile(r"[^\s'\"`$()<>;|&]+")
QUOTED = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"")
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\+?=(.*)$", re.S)
VARREF = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
HEREDOC_OP = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|(\\?)([A-Za-z0-9_.+-]+))")
# A here-document body a `$(…)` yields as a string is held out of the text; a marker in its word
# says where the string is used.
HELD_MARK = "\x1fheld%d\x1f"
HELD = re.compile("\x1fheld([0-9]+)\x1f")
FRAME_IDS = itertools.count(1)
# A `#` begins a comment only where it begins a word: after whitespace, a newline or an operator
# (`;#x`, `(ls)#x`, `>#x` are all comments to bash), never inside a word (`a#b`, `${#x}`, `$#`).
COMMENT_AFTER = " \t\n;&|()<>"
# Only for input the hook could not analyse: names that make a crash deny rather than allow.
NAMED = re.compile(r"private[-_]mode[-_]id(?![a-z0-9-])|firewall[-_]registry(?![a-z])", re.I)


def split_cf(path):
    return [c.casefold() for c in path.split(os.sep) if c]


@functools.lru_cache(maxsize=4096)
def real_parts(path):
    try:
        return tuple(split_cf(os.path.realpath(path)))
    except (OSError, ValueError):
        return tuple(split_cf(path))


@functools.lru_cache(maxsize=4096)
def inode(path):
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino) if stat.S_ISREG(st.st_mode) else None


class Protected(object):
    """What this call protects, and every spelling of it the comparisons need."""

    def __init__(self, private, registry, verified, project):
        self.verified = bool(verified and private)
        files = [os.path.normpath(f) for f in list(private) + ([] if self.verified else list(registry))]
        pointers = [PRIVATE_POINTER] + ([] if self.verified else [REGISTRY_POINTER])
        self.files = [(tuple(split_cf(f)), real_parts(f), inode(f)) for f in files]
        # a protected file's own directory is a scope that reads it (`grep -r`, `cat dir/*`)
        self.dirs = [(p[:-1], r[:-1]) for p, r, _ in self.files]
        self.pointer_paths = [tuple(split_cf(os.path.join(project, "checks", n))) for n in pointers]
        self.names = {n.casefold() for n in pointers} | {PRIVATE_DEFAULT} | \
            {os.path.basename(f).casefold() for f in files}
        if not self.verified:
            self.names.add(REGISTRY_DEFAULT)
        self.dir_spellings = {os.path.dirname(f).casefold() for f in files}
        # the directories a relative word must start at or above to reach a protected file or pointer
        self.anchors = {d for p, r in self.dirs for d in (p, r)} | {pp[:-1] for pp in self.pointer_paths}

    def above(self, path):
        """Is this directory a protected file's or pointer's directory, or one of its ancestors?"""
        mine = {tuple(split_cf(path)), real_parts(path)}
        return any(a[:len(m)] == m for m in mine for a in self.anchors)


def read_pointer(path, project):
    """The first non-comment line of a pointer file, `~` expanded; never raises."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    p = os.path.expanduser(line)
                    return p if os.path.isabs(p) else os.path.join(project, p)
    except (OSError, ValueError):
        return None
    return None


def load(argv, project):
    private, registry, verified, had_args = [], [], False, False
    it = iter(argv)
    for a in it:
        if a in ("--private", "--registry"):
            had_args = True
            v = next(it, "")
            if os.path.isabs(v):
                (private if a == "--private" else registry).append(v)
        elif a == "--split-verified":
            had_args = True
            verified = True
    if not had_args:
        for name, bucket in ((PRIVATE_POINTER, private), (REGISTRY_POINTER, registry)):
            p = read_pointer(os.path.join(project, "checks", name), project)
            if p:
                bucket.append(p)
        verified = False
    return Protected(private, registry, verified, project)


def deny(prot, why):
    try:
        what = ("the private-mode identifier" if prot is not None and prot.verified
                else "the private-mode identifier (and the token registry, until its split is verified)")
        sys.stderr.write("registry read-guard: %s — %s never enters a model session (ADR-0029; "
                         "ADR-0050 point 9). Ask the operator to look at the file "
                         "themselves.\n" % (why, what))
    except BaseException:  # noqa: BLE001 — a reason that cannot be written still denies
        pass
    sys.exit(2)


# ---------- a private-mode person's originals (ADR-0029 point 12) ----------
# A person whose profile.md carries the private-mode marker has originals no model may see until the
# local redaction pipeline and the operator's gate have run: everything in their med/_inbox/ and
# med/sources/ except Markdown — the checklist, and transcriptions made only from approved redacted
# rasters, which guard L10 scans — and except redacted rasters (`_redacted/`, filed under
# med/sources/ or beside it). The pipeline's id-to-file-name map is never read either, nor a private
# mode v2 person's identity file (ADR-0029 control C1): both by name, anywhere,
# snapshot copies included; the identity file's name as a suffix, so the temporary file of an
# interrupted write is covered too, and whether or not it exists yet (a copy and a read of the copy
# can share one line). A grep-family pattern is data, never a path, so mentioning a name there runs.
# Measured
# before this existed (contained sessions, 2026-09-29): a session asked to file a new scan read it
# in the same batch as the profile, before the marker was seen — Sonnet 5 in 4 of 6 runs, Opus 5.5
# in 1 of 4. Judged separately from the registry: its own safe commands, and folders ABOVE the
# lanes (the person's folder and med/, a patients/ folder holding a marked person) count too.
# A non-shell interpreter's code (python, perl, …; a here-document script or a `-c` string) is judged
# by its string literals and its words with a `/`, never by the words of prose inside a literal
# (ADR-0029 point 12). A denial names the rule class that matched, never the path.
PM_MARK = "⟨never-API⟩".encode("utf-8")
PM_LANES = ("_inbox", "sources")
PM_MAP = ".never-api-source-map.json"
PM_IDENTITY = ".never-api-identity.json"
PM_IDENTITY_MARK = "never-api-identity"   # in the identity file's name, its form's, and an editor's copy of either
# private mode v2 (ADR-0029 control C1, second part): in a v2 person's
# med/handouts/, a final render (its PDF, or any other output) carries the person's details, filled in
# at the seal; the Markdown with its placeholders, the attestation's metadata and drafts (which show the
# handle) stay readable
PM_V2_SHAPED = re.compile(rb"(?i)private.{0,4}v[0-9]")
PM_HANDOUT_READABLE = (".md", ".attest.json", ".draft.pdf", ".draft.txt", ".legacy-frozen")
# commands that move, copy, list or show a file to the operator, never print its content
PM_SAFE = {"cp", "mv", "ln", "rm", "mkdir", "rmdir", "touch", "open"}
# digests are safe in hashing mode only: macOS `md5 -p` echoes its input, and a checksum check (`-c`)
# reads the file it is given as lines
PM_DIGESTS = {"shasum", "sha256sum", "sha1sum", "sha512sum", "sha224sum", "sha384sum", "md5", "md5sum"}
# a local conversion (an image original into the PDF the redaction pipeline reads) is safe when it
# writes only a file, and that file inside a private-mode lane, where it stays protected
PM_CONVERTERS = {"magick", "convert", "img2pdf", "sips"}
PM_CONVERT_PRINTS = {"-print", "-identify", "-verbose", "-format", "-debug", "-list", "-version",
                     "-g", "--getProperty", "-1", "--oneLine"}
PM_MAGICK_NOT_CONVERT = {"identify", "compare", "stream", "display", "montage", "animate", "import",
                         "conjure", "mogrify"}
# a stream of file NAMES (after `ls` or `find`) may pass through these without becoming a read
PM_NAME_FILTERS = {"head", "tail", "sort", "uniq", "cut", "tr", "wc", "column", "nl"}
# in the same part of a line these turn names into reads; a `for` loop is judged by its body, and a
# wrapper by the command it runs
PM_CONSUMERS = (NAME_CONSUMERS - {"for", "do"} - WRAPPERS) | {"xargs", "parallel"}
XARGS_VALUE_OPTS = {"-I", "-i", "-n", "-P", "-L", "-l", "-d", "-s", "-E", "-e", "-a", "-J", "-R", "-S"}
PM_UPLOAD_TOOLS = {"Artifact", "SendUserFile"}      # they send a file off this machine
PM_VIEWERS = {"mcp__ccd_host__open_in_editor", "mcp__ccd_host__reveal_path"}   # the operator's own screen
PM_TAINTED = set()     # variables holding an original's path (one hop, like the registry's `tainted`)
PM_VARS = {}           # the line's own assignments, for paths built from a variable
PM_BODIES = []         # (operator line, body) of here-documents handed to a program as data


def pm_named(name, path):
    """Is this file refused by its name (casefolded)? The file-name map; a name ending like the
    identity file, existing or not (`cp … && cat <new copy>` is one line); and any existing file whose
    name holds the identity marker: an editor's backup or a copy of the filled form or of the identity
    file (`…json~`, `#…json#`, `… copy.json`; cold review 2026-11-07, an exception to the guard's
    freeze for this rule alone). A word that only mentions the marker (a commit message, a search, a
    line of code) names no file."""
    return name == PM_MAP or name.endswith(PM_IDENTITY) or (
        PM_IDENTITY_MARK in name and os.path.lexists(path))


@functools.lru_cache(maxsize=512)
def pm_identity_beside(profile):
    """A private mode v2 identity file in the person's folder: a durable sign of private mode that a
    lost or edited profile line does not erase."""
    try:
        return os.path.lexists(os.path.join(os.path.dirname(profile), PM_IDENTITY))
    except (OSError, ValueError):
        return True


@functools.lru_cache(maxsize=512)
def pm_marked(profile):
    """Does this profile.md carry the private-mode marker? One that exists but cannot be read counts
    as marked (fail closed), and so does any person whose folder holds a v2 identity file; a missing
    profile otherwise, or a path through a file, as unmarked."""
    if pm_identity_beside(profile):
        return True
    try:
        with open(profile, "rb") as fh:
            return PM_MARK in fh.read()
    except (FileNotFoundError, NotADirectoryError):
        return False
    except (OSError, ValueError):
        return True


@functools.lru_cache(maxsize=512)
def pm_v2(profile):
    """Is this person on private mode v2 (the marker and something shaped like the v2 tag, or a v2
    identity file in their folder)? A profile that exists but cannot be read counts as v2 (fail closed)."""
    if pm_identity_beside(profile):
        return True
    try:
        with open(profile, "rb") as fh:
            data = fh.read()
    except (FileNotFoundError, NotADirectoryError):
        return False
    except (OSError, ValueError):
        return True
    return PM_MARK in data and PM_V2_SHAPED.search(data) is not None


@functools.lru_cache(maxsize=128)
def pm_any_marked(patients_dir):
    try:
        names = sorted(os.listdir(patients_dir))[:512]
    except (OSError, ValueError):
        return False
    return any(pm_marked(os.path.join(patients_dir, n, "profile.md")) for n in names)


@functools.lru_cache(maxsize=8192)
def pm_original(path):
    """'file' when this absolute path is a private-mode person's original (or the pipeline's
    id-to-name map, or a v2 identity file); 'dir' when it is a folder holding originals — a lane or a folder inside one,
    the person's med/ or folder, a patients/ folder with a marked person in it; else None. Judged on
    the path as written and as resolved, so a symlink into a lane is the lane; a snapshot or backup
    copy that keeps the patients/<handle>/ layout counts too."""
    try:
        cands = {os.path.normpath(path), os.path.realpath(path)}
    except (OSError, ValueError):
        cands = {os.path.normpath(path)}
    for cand in cands:
        parts = cand.split(os.sep)
        low = [x.casefold() for x in parts]
        if low and pm_named(low[-1], cand):
            return "file"
        for k in range(len(parts) - 4, -1, -1):
            if low[k] != "patients" or low[k + 2] != "med":
                continue
            if low[k + 3] == "handouts":              # a v2 person's final output carries their details
                if not pm_v2(os.sep.join(parts[:k + 2] + ["profile.md"])):
                    continue
                rest = low[k + 4:]
                if not rest or os.path.isdir(cand):
                    return "dir"
                if rest[-1].endswith(PM_HANDOUT_READABLE):
                    break
                return "file"
            if low[k + 3] not in PM_LANES:
                continue
            rest = low[k + 4:]
            if "_redacted" in rest:
                break
            if not pm_marked(os.sep.join(parts[:k + 2] + ["profile.md"])):
                continue            # an unmarked tree nested in a marked lane is still inside it
            if not rest or os.path.isdir(cand):
                return "dir"
            if rest[-1].endswith(".md"):
                break
            return "file"
        n = len(low)
        if n >= 3 and low[-3] == "patients" and low[-1] == "med" and os.path.isdir(cand) and \
                pm_marked(os.sep.join(parts[:-1] + ["profile.md"])):
            return "dir"
        if n >= 2 and low[-2] == "patients" and os.path.isdir(cand) and \
                pm_marked(os.sep.join(parts + ["profile.md"])):
            return "dir"
        if n >= 1 and low[-1] == "patients" and os.path.isdir(cand) and pm_any_marked(cand):
            return "dir"
    return None


def pm_class(path):
    """What kind of protected thing this path is, for the denial message (never the path itself):
    'name' (a file refused by its name: the identity file, the file-name map), 'file' (an original,
    or a v2 person's final handout), 'lane' (a lane, a folder inside one, a v2 person's handouts) or
    'above' (a folder holding a lane: the person's folder or med/, a patients/ folder); else None."""
    kind = pm_original(path)
    if kind is None:
        return None
    try:
        cands = {os.path.normpath(path), os.path.realpath(path)}
    except (OSError, ValueError):
        cands = {os.path.normpath(path)}
    if kind == "file":
        return "name" if any(pm_named(os.path.basename(c).casefold(), c) for c in cands) else "file"
    for cand in cands:
        low = [x.casefold() for x in cand.split(os.sep)]
        if any(low[k] == "patients" and low[k + 2] == "med" and low[k + 3] in PM_LANES + ("handouts",)
               for k in range(len(low) - 3)):
            return "lane"
    return "above"


def pm_hits(path, pattern=True):
    """The class (pm_class) of what this absolute path reaches, or None. With `pattern`, glob
    characters are expanded against the disk, as the shell would; a match reports 'glob:<class>'."""
    cls = pm_class(path)                         # a literal name may hold glob characters: `lab [1].txt`
    if cls:
        return cls
    if pattern and any(ch in path for ch in "*?["):  # `**` recurses, as zsh does
        for m in itertools.islice(glob.iglob(path, recursive=True), GLOB_LIMIT):
            cls = pm_class(m)
            if cls:
                return "glob:" + cls
    return None


def pm_reaches(word, bases, pattern=True):
    """Like `reaches`, but a word may hold spaces (incoming files keep the names they arrived with;
    a quoted operand is one word) and a variable the line assigned is substituted once. Returns the
    class of the first thing reached (pm_hits; 'variable' for a variable holding one), or None."""
    if any(v in PM_TAINTED for v in VARREF.findall(word)):
        return "variable"
    word = VARREF.sub(lambda m: PM_VARS.get(m.group(1), m.group(0)), word)
    if not word or "\n" in word or len(word) > 4096:
        return None
    return next(filter(None, (pm_hits(p, pattern) for p in expand(word, bases))), None)


def pm_first(words, bases):
    """The class reached by the first of these words that reaches anything, or None."""
    return next(filter(None, (pm_reaches(w, bases) for w in words)), None)


def pm_words(text):
    """Candidate paths inside shell code or a substitution: its words, and its quoted strings whole."""
    return CODE_ATOM.findall(text) + [x or y for x, y in QUOTED.findall(text)]


def pm_code_reaches(text, bases):
    """The class reached by a non-shell interpreter's code (python, perl, ruby, node, osascript), or
    None. A path there is a string literal, so a word counts only when it holds a `/` (or is a name
    refused anywhere, the identity file's or the map's), and a literal counts whole: prose inside one
    (`"most patients agree"`, Markdown bold `**patient**`) names nothing, while
    `open('<lane>/<file>')`, `os.walk('patients/<person>')`, `os.listdir('patients')` and
    `os.system('cat <path>')` still do. A literal without a `/` is a name in the working directory,
    never a pattern (`'*' * 40`, `.replace('**', '')`); inside a lane every name is an original."""
    for w in CODE_ATOM.findall(text):
        if "/" in w or w.casefold() == PM_MAP or PM_IDENTITY_MARK in w.casefold():
            cls = pm_reaches(w, bases)
            if cls:
                return cls
    for x, y in QUOTED.findall(text):
        w = x or y
        cls = pm_reaches(w, bases, pattern="/" in w)
        if cls:
            return cls
    return None


PM_CLASS_TEXT = {
    "file": "an original of a private-mode person, or the final handout of a person with kept details",
    "name": "a file refused by its name: an identity file of kept details, its fill-in form or a copy of "
            "either, or the pipeline's file-name map",
    "lane": "a folder of a private-mode person's originals, their med/_inbox or med/sources, or the "
            "med/handouts of a person with kept details",
    "above": "a folder above a private-mode person's originals, their folder or med/ or a patients/ "
             "folder holding one",
}


def pm_matched(cls):
    """The rule class that matched, in words — never the word, the path or the file, so a session can
    tell a real hit from a false one without reading anything protected."""
    if cls == "variable":
        return "a variable assigned on the line holds the path of one"
    if cls.startswith("glob:"):
        return "a glob pattern in it matches, on disk, %s" % PM_CLASS_TEXT.get(cls[5:], "a protected path")
    return "a path in it resolves to %s" % PM_CLASS_TEXT.get(cls, "a protected path")


def pm_effective(words):
    """The command a statement runs, past reserved words and wrappers: (head, word, arguments)."""
    i, n = 0, len(words)
    while i < n and words[i] in RESERVED:
        i += 1
    while i < n and os.path.basename(words[i]) in WRAPPERS:
        i += 1
        while i < n and (words[i].startswith("-") or ASSIGNMENT.match(words[i])
                         or re.match(r"^[0-9][0-9.]*[smhd]?$", words[i])):
            i += 1
    if i >= n:
        return None, None, []
    return os.path.basename(words[i]), words[i], words[i + 1:]


def pm_exempt(head, args, bases):
    """The redaction pipeline and the ownership ledger read originals by design and print none."""
    if not head or not interpreter(head):
        return False
    for k, a in enumerate(args):
        if a == "-m":
            return k + 1 < len(args) and args[k + 1] == "tools.person_ownership"
        if not a.startswith("-"):
            for p in expand(a, bases):
                parts = split_cf(os.path.realpath(p))
                if len(parts) >= 3 and parts[-3:-1] == ["tools", "private-mode"] and \
                        parts[-1].endswith(".py"):
                    return True
            return False
    return False


def pm_digest_safe(head, args):
    for a in args:
        if a.startswith("--"):
            if a == "--check" or a.startswith("--check="):
                return False
        elif a.startswith("-") and len(a) > 1:
            if (head == "md5" and "p" in a[1:]) or (head != "md5" and "c" in a[1:]):
                return False
    return True


def pm_convert_safe(head, args, bases):
    """A conversion that writes only a file, inside a private-mode lane (where it stays protected)."""
    out = None
    if head in ("magick", "convert"):
        a = args[1:] if (head == "magick" and args[:1] == ["convert"]) else args
        if not a or a[0] in PM_MAGICK_NOT_CONVERT or any(x in PM_CONVERT_PRINTS for x in a):
            return False
        out = a[-1]
    elif head == "img2pdf":
        for k, x in enumerate(args):
            if x in ("-o", "--output") and k + 1 < len(args):
                out = args[k + 1]
            elif x.startswith("--output="):
                out = x.split("=", 1)[1]
    else:                                        # sips
        if any(x in PM_CONVERT_PRINTS for x in args):
            return False
        for k, x in enumerate(args):
            if x in ("-o", "--out") and k + 1 < len(args):
                out = args[k + 1]
    if not out or out == "-" or out.endswith(":-") or out.casefold().startswith(("fd:", "info:")):
        return False
    if re.match(r"^[A-Za-z0-9]{2,8}:", out):     # a format prefix: `pdf:<path>`
        out = out.split(":", 1)[1]
    return bool(out) and any(pm_original(p) == "file" for p in expand(out, bases))


def pm_safe(head, args, bases=()):
    """Does this command print nothing of a file's content (listing, filing, hashing, showing, a
    conversion into a lane)?"""
    if head is None or head in META or head in PM_SAFE:
        return True
    if head in PM_DIGESTS:
        return pm_digest_safe(head, args)
    if head in PM_CONVERTERS:
        return pm_convert_safe(head, args, list(bases))
    if head == "find":                           # safe without -exec, or when what it runs is safe
        for k, a in enumerate(args):
            if a in FIND_EXEC:
                if k + 1 >= len(args):
                    return False
                end = next((j for j in range(k + 2, len(args)) if args[j] in ("+", ";")), len(args))
                if not pm_safe(os.path.basename(args[k + 1]), args[k + 2:end], bases):
                    return False
        return True
    if head == "git":
        return not any(a in GIT_REACH or a.startswith(("--git-dir=", "--work-tree=")) for a in args)
    if head in ("xargs", "parallel"):
        k = 0
        while k < len(args):
            if args[k] in XARGS_VALUE_OPTS:
                k += 2
            elif args[k].startswith("-"):
                k += 1
            else:
                return pm_safe(os.path.basename(args[k]), args[k + 1:], bases)
    return False


def pm_inner_safe(span, bases):
    """A `$(…)`, backtick or `<(…)` body yields file NAMES at most — never a file's content?"""
    body = span
    for a, b in (("$(", ")"), ("<(", ")"), (">(", ")"), ("`", "`")):
        if body.startswith(a):
            body = body[len(a):-len(b)] if body.endswith(b) else body[len(a):]
            break
    try:
        toks = tokens(body)
    except ValueError:
        return False
    stmts, cur = [], []
    for t in toks:
        if t in GROUP_SEPARATORS or t in STATEMENT_BREAKS:
            if cur:
                stmts.append(cur)
            cur = []
        elif not redirection(t):
            cur.append(t)
    if cur:
        stmts.append(cur)
    for w in stmts:
        head, _, args = pm_effective(w)
        for inner in (x for a in w for x in runs_in(a)):     # `"$(echo \"$(cat <original>)\")"`
            if inner != span and any(pm_reaches(x, bases) for x in pm_words(inner)) and \
                    not pm_inner_safe(inner, bases):
                return False
        if pm_safe(head, args, bases):
            continue
        if head in PM_NAME_FILTERS and not any(pm_reaches(a, bases) for a in args):
            continue
        return False
    return True


def pm_group(stmts, bases, code, unquoted_sub):
    """One part of a line, judged for a private-mode person's originals. `code` is 'shell' when the
    part runs a shell or `eval` (its arguments' words are judged as shell words), 'script' when it runs
    only another interpreter (its arguments are judged as that code: pm_code_reaches), else None."""
    reached = unsafe = None          # the class reached first; first by a statement that could print
    consumed = any_unsafe = hint = False
    for s in stmts:
        head, word, args = pm_effective(([s["word"]] if s["word"] else []) + s["args"])
        if head == "for" and len(args) >= 2 and args[1] == "in":
            if any(pm_reaches(a, bases) for a in args[2:]):
                PM_TAINTED.add(args[0])          # judged where its body uses it
            continue
        exempt = pm_exempt(head, args, bases)
        safe = exempt or pm_safe(head, args, bases)
        if head is None and s["inputs"]:
            safe = False       # `$(<file)` yields the file; zsh pages a bare `<file` to the screen
        if not safe and head in PM_CONVERTERS:
            hint = True
        any_unsafe = any_unsafe or not safe
        if (head in PM_CONSUMERS and not safe) or (head and interpreter(head) and not exempt):
            consumed = True                      # an xargs that runs a safe command consumes nothing
        assigns = list(s["assign"])
        if head in ("export", "local", "readonly", "declare"):
            assigns += [a for a in args if ASSIGNMENT.match(a)]
        words = list(s["inputs"]) + [ASSIGNMENT.match(a).group(2) for a in assigns]
        scripts = []                             # code a non-shell interpreter runs
        if not exempt:
            skip = pattern_args(head, args)      # a search pattern is data, never read as a file
            words += [a for k, a in enumerate(args) if k not in skip and "$(" not in a and "`" not in a]
            if word and "/" in word:
                words.append(word)
            if code == "shell":
                for a in args:
                    words += pm_words(a)
            elif code:
                scripts += args
        for body in s["held"]:
            words.append(body.rstrip("\n"))
            if code == "shell":
                words += pm_words(body)
            elif code:
                scripts.append(body)
        hit = pm_first(words, bases) or next(filter(None, (pm_code_reaches(t, bases) for t in scripts)), None)
        if hit:
            reached = reached or hit
            if not safe:
                unsafe = unsafe or hit
        for span in [x for a in args + assigns for x in runs_in(a)] + list(s["runs"]):
            hit = pm_first(pm_words(span), bases)
            if hit:
                reached = reached or hit
                if not (safe and pm_inner_safe(span, bases)):
                    unsafe = unsafe or hit
        for a in assigns:
            m = ASSIGNMENT.match(a)
            if m:
                PM_VARS[m.group(1)] = m.group(2)
                if pm_reaches(m.group(2), bases):
                    PM_TAINTED.add(m.group(1))
    # an unquoted `$(…)`/`<(…)` hands what it yields to the command around it
    if reached and (unsafe or consumed or (unquoted_sub and any_unsafe)):
        deny_pm("a conversion of an original must write a file into the person's med/_inbox/, where it "
                "stays protected — never to the screen or elsewhere" if hint else
                "the command could print a private-mode person's original", unsafe or reached)


def pm_bodies(bodies, bases):
    """A here-document handed to an interpreter as its script (`python3 - <<'EOF'`) is code, judged
    by its literals and its paths (pm_code_reaches)."""
    for line, body in bodies:
        if any(interpreter(w) and os.path.basename(w) not in SHELLS for w in line.split()):
            cls = pm_code_reaches(body, bases)
            if cls:
                deny_pm("an interpreter's script names a private-mode person's original", cls)


def pm_raw(text, bases):
    """Fallback for a line that cannot be parsed: any word in it that reaches an original."""
    cls = pm_first(pm_words(text)[:4096], bases)
    if cls:
        deny_pm("a command naming a private-mode person's original could not be parsed", cls)


def deny_pm(why, cls=None):
    """Deny, naming the rule class that matched (pm_matched) when a shell judgement found one."""
    try:
        if cls:
            why = "%s [matched rule: %s]" % (why, pm_matched(cls))
        sys.stderr.write("private-mode guard: %s — a private-mode person's original never reaches a "
                         "model session until the redaction pipeline and the operator's gate have run "
                         "(ADR-0029; tools/private-mode/README.md). Read the approved redacted rasters "
                         "under the person's _redacted/ instead; search their Markdown with a *.md "
                         "glob.\n" % why)
    except BaseException:  # noqa: BLE001
        pass
    sys.exit(2)


# ---------- is this path a protected one? ----------

def hits(path, prot, scopes, by_name=True, expanded=False):
    """An absolute path: a protected file or pointer, or — with `scopes` — a protected file's own
    directory, or — with `by_name` — any file NAMED like a protected one. A bare word on a command
    line (no `/`) is judged without `by_name`: it is a path only where it resolves. A glob is
    expanded against the disk, as the shell would, and each real match is judged."""
    if not expanded and any(ch in path for ch in "*?["):
        return any(hits(m, prot, scopes, True, True) for m in itertools.islice(glob.iglob(path), GLOB_LIMIT))
    parts = tuple(split_cf(path))
    if not parts:
        return False
    if (by_name and parts[-1] in prot.names) or parts in prot.pointer_paths:
        return True
    mine = {parts, real_parts(path)}
    ino = inode(path)
    for p, r, i in prot.files:
        if p in mine or r in mine or (ino is not None and ino == i):
            return True
    return bool(scopes and any(p in mine or r in mine for p, r in prot.dirs))


# ---------- the shell command line ----------

def redirection(t):
    return set(t) <= set("<>&") and ("<" in t or ">" in t)


def simple_commands(toks):
    """The words of each simple command in a token list, redirections (with an fd number before one)
    left out."""
    out, cur, skip = [], [], False
    for k, t in enumerate(toks):
        if skip:
            skip = False
        elif t in STATEMENT_BREAKS or t in GROUP_SEPARATORS:
            if cur:
                out.append(cur)
            cur = []
        elif redirection(t):
            skip = True
        elif not (t.isdigit() and k + 1 < len(toks) and redirection(toks[k + 1])):
            cur.append(t)
    return out + ([cur] if cur else [])


def stdin_script(args):
    """Given a shell's arguments: does it read its script from standard input (no `-c`, and `-s`, no
    script file, or the file `-` / `/dev/stdin`)?"""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a in SHELL_VALUE_OPTS:
            i += 2
            continue
        if len(a) > 1 and a[0] in "-+":
            short = not a.startswith("--")
            if a[0] == "-" and short and "c" in a:
                return False
            if a[0] == "-" and short and "s" in a:
                return True
            i += 2 if short and ("o" in a or "O" in a) else 1     # `-euo pipefail`: `o` takes a value
            continue
        break
    return i >= len(args) or args[i] in STDIN_FILES


def runs_stdin(words):
    """Does this simple command run its standard input as shell code — `bash -s`, `timeout 9 zsh`,
    `$SHELL`, `source /dev/stdin`, `sudo -s` — rather than read it as data (`bash -c …`,
    `bash script.sh`)?"""
    k = 0
    while k < len(words) and (words[k] in RESERVED or ASSIGNMENT.match(words[k])):
        k += 1
    if k < len(words) and os.path.basename(words[k]) in WRAPPERS:
        wrapper, rest = os.path.basename(words[k]), words[k + 1:]
        k = next((j for j in range(k + 1, len(words)) if is_shell(words[j])), len(words))
        if k == len(words):         # `sudo -s` / `sudo -i` with no command runs a shell on stdin
            return wrapper == "sudo" and bool(SUDO_SHELL & set(rest))
    if k >= len(words):
        return False
    if words[k] in ("source", "."):
        return len(words) > k + 1 and words[k + 1] in STDIN_FILES[1:]
    return is_shell(words[k]) and stdin_script(words[k + 1:])


def is_shell(word):
    return os.path.basename(word) in SHELLS or word in ("$SHELL", "${SHELL}")


def feeds_shell(segment):
    """Does a shell run this pipeline's standard input — `bash -s <<'EOF'`, `cat <<'EOF' | sh`?"""
    try:
        toks = tokens(segment)
    except ValueError:
        toks = segment.split()
    return any(runs_stdin(w) for w in simple_commands(toks))


def bare_cat(segment):
    """Is this pipeline a lone `cat`, which prints its standard input (any file it names is an
    operand, judged in its word)?"""
    try:
        cmds = simple_commands(tokens(segment))
    except ValueError:
        return False
    return len(cmds) == 1 and os.path.basename(cmds[0][0]) == "cat"


def heredoc_ops(line, stack):
    """(delimiter, dash, quoted, fate, end) for each here-document operator on one command line,
    outside quotes, comments, `${…}`, `$[…]` and arithmetic `((…))` / `$((…))` — but inside a
    command substitution, even one within double quotes, where the shell reads commands again.
    `stack` carries open quotes and substitutions to the next line; a body is never scanned. Fate:
      script  a command of its own pipeline runs standard input as a script (runs_stdin);
      hold    a bare `cat` inside `$(…)`: the substitution yields the body as a string (the
              commit-message idiom) — data, judged where the string is used (check_group);
      keep    any other reader inside a double-quoted `$(…)`: the body stays in its word;
      skip    its substitution closes on this line, so the body is empty and the lines after it
              are commands;
      data    otherwise."""
    found, bounds, closed, spans, k = [], [], set(), [], 0
    while k < len(line):
        ch = line[k]
        top = stack[-1] if stack else None
        kind, fid = (top[0], top[1]) if top else ("c", 0)
        if kind in ("'", "$'"):
            if ch == "\\" and kind == "$'":
                k += 2
                continue
            if ch == "'":
                stack.pop()
        elif kind == '"':
            if ch == "\\":
                k += 2
                continue
            if ch == '"':
                stack.pop()
            elif line.startswith("$((", k):
                stack += [[")", 0, 0], [")", 0, 0]]
                k += 3
                continue
            elif line.startswith("$(", k) or ch == "`":
                stack.append(["c" if ch == "$" else "`", next(FRAME_IDS), 0])
                bounds.append((stack[-1][1], k + 1))
                k += 1 if ch == "`" else 2
                continue
        elif ch == "\\":
            k += 2
            continue
        elif line.startswith("$'", k):
            stack.append(["$'", 0, 0])
            k += 2
            continue
        elif ch in "'\"":
            stack.append([ch, 0, 0])
        elif line.startswith("$((", k) or line.startswith("((", k):
            stack += [[")", 0, 0], [")", 0, 0]]
            k += 3 if ch == "$" else 2
            continue
        elif line.startswith("${", k) or line.startswith("$[", k):
            stack.append(["}" if line[k + 1] == "{" else "]", 0, 0])
            k += 2
            continue
        elif kind not in ("c", "`"):            # inside `${…}`, `$[…]`, `((…))`: no commands
            if ch == "(":
                stack.append([")", 0, 0])
            elif ch == kind:
                stack.pop()
        elif ch == "`" and kind == "`":         # a backtick span closes like a `$(…)`
            stack.pop()
            bounds.append((fid, k))
            closed.add(fid)
        elif ch == "`":
            stack.append(["`", next(FRAME_IDS), 0])
            bounds.append((stack[-1][1], k + 1))
        elif ch == "#" and (k == 0 or line[k - 1] in COMMENT_AFTER):
            bounds.append((fid, k))
            break
        elif line.startswith(("$(", "<(", ">("), k):
            stack.append(["c", next(FRAME_IDS), 0])
            bounds.append((stack[-1][1], k + 1))
            k += 2
            continue
        elif ch == "(" and top:
            top[2] += 1                         # a subshell inside a substitution
        elif ch == ")" and top:
            if top[2]:
                top[2] -= 1
            elif kind != "`":
                stack.pop()
                bounds.append((fid, k))
                closed.add(fid)
        elif ch == ";" or line.startswith("||", k) or (
                ch == "&" and line[k + 1:k + 2] != ">" and (k == 0 or line[k - 1] not in "<>|&")):
            bounds.append((fid, k))             # `;`, `&&`, `||`, `&` end a pipeline; `|` does not
        elif line.startswith("<<", k) and not line.startswith("<<<", k) and (k == 0 or line[k - 1] != "<"):
            m = HEREDOC_OP.match(line, k)
            if m:
                delim = next(g for g in m.group(2, 3, 5) if g is not None)
                quoted = m.group(2) is not None or m.group(3) is not None or m.group(4) == "\\"
                fd = re.search(r"(?:^|[\s;&|()<>])(\d*)$", line[:k])
                stdin = fd is None or fd.group(1) in ("", "0")
                inside = [f[0] for f in stack]
                found.append((delim, m.group(1) == "-", quoted, k, stdin, fid,
                              "c" in inside or "`" in inside,
                              '"' in inside, m.end()))
                spans.append((k - (len(fd.group(1)) if fd else 0), m.end()))
                k = m.end()
                continue
        k += 1
    blank = line                                # operators and delimiters are no command words
    for a, b in spans:
        blank = blank[:a] + " " * (b - a) + blank[b:]
    out = []
    for delim, dash, quoted, at, stdin, fid, sub, in_dq, end in found:
        mine = [b for f, b in bounds if f == fid]     # the pipeline bounds of the op's own level
        start = max([b for b in mine if b < at], default=-1) + 1
        segment = blank[start:min([b for b in mine if b > at], default=len(line))]
        if fid in closed:
            fate = "skip"
        elif sub and stdin and bare_cat(segment):
            fate = "hold"
        elif sub and in_dq:
            fate = "keep"
        elif stdin and feeds_shell(segment):
            fate = "script"
        else:
            fate = "data"
        out.append((delim, dash, quoted, fate, end))
    return out


def continued(line):
    """Does this command line end in a line-continuing backslash? Not in a comment, which ends at the
    newline whatever it holds, so a read on the next line is never pulled into it."""
    code = strip_comments(line)
    return (len(code) - len(code.rstrip("\\"))) % 2 == 1


def strip_heredocs(cmd):
    """The command with here-document BODIES removed (they are data), except the `$(…)` and
    backtick spans of an unquoted body, which the shell runs; those are kept as lines of their own.
    A body a shell runs is no data: it is returned as a script, to be judged as a command line.
    A body a `$(…)` yields as a string is held, and a marker left in its word (heredoc_ops: hold).
    An unterminated body is not stripped, so a missing delimiter can never hide the lines after it."""
    lines, out, runs, scripts, held, stack, i = cmd.split("\n"), [], [], [], {}, [], 0
    while i < len(lines):
        line = lines[i]
        i += 1
        while i < len(lines) and continued(line):   # a command line's `\`-newline joins it to the next
            line = line[:-1] + lines[i]
            i += 1
        ops = heredoc_ops(line, stack)
        keys = {n: len(held) + r for r, n in enumerate(n for n, op in enumerate(ops) if op[3] == "hold")}
        for n in sorted(keys, reverse=True):
            line = line[:ops[n][4]] + " " + HELD_MARK % keys[n] + line[ops[n][4]:]
        out.append(line)
        for n, (delim, dash, quoted, fate, _) in enumerate(ops):
            if fate == "skip":
                continue
            j = i
            while j < len(lines) and (lines[j].lstrip("\t") if dash else lines[j]) != delim:
                j += 1
            if j == len(lines):
                return "\n".join(out + lines[i:] + runs), scripts, held
            body = [b.lstrip("\t") for b in lines[i:j]] if dash else lines[i:j]
            if fate == "script":
                scripts.append("\n".join(body))
            elif fate == "keep":
                out += lines[i:j + 1]
            else:
                if fate == "hold":
                    held[keys[n]] = "\n".join(body)
                else:
                    PM_BODIES.append((line, "\n".join(body)))
                if not quoted:
                    runs += runs_in("\n".join(body))
            i = j + 1
    return "\n".join(out + runs), scripts, held


def backtick_end(text, k):
    """The index of the backtick closing the span opened at `k` (len(text) when none does)."""
    j = k + 1
    while j < len(text) and text[j] != "`":
        j += 2 if text[j] == "\\" else 1
    return min(j, len(text))


def strip_comments(text):
    """The text with shell comments removed: a `#` that begins a word outside quotes, to the end of
    its line (the same rule as heredoc_ops). Quotes may span lines, and a quote inside a comment
    opens nothing; `${#x}`, `$#`, `a#b` and `\\#` are not comments. A backtick span is a command of
    its own, so a comment inside one ends at its closing backtick, as in the shell."""
    out, quote, k, n = [], None, 0, len(text)
    while k < n:
        ch = text[k]
        if ch == "`" and quote not in ("'", "$'"):
            j = backtick_end(text, k)
            out.append("`" + strip_comments(text[k + 1:j]) + text[j:j + 1])
            k = j + 1
            continue
        if quote:
            if ch == "\\" and quote in ('"', "$'"):
                out.append(text[k:k + 2])
                k += 2
                continue
            if ch == quote[-1]:
                quote = None
            out.append(ch)
        elif ch == "\\":
            out.append(text[k:k + 2])
            k += 2
            continue
        elif text.startswith("$'", k):          # an ANSI-C string: `\'` does not close it
            quote = "$'"
            out.append("$'")
            k += 2
            continue
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch == "#" and (k == 0 or text[k - 1] in COMMENT_AFTER):
            j = text.find("\n", k)
            k = n if j < 0 else j
            continue
        else:
            out.append(ch)
        k += 1
    return "".join(out)


def backticks(text):
    """The text with each backtick substitution spelled `$(…)`, so it is judged exactly as one: outside
    single quotes and unescaped. Inside a span `\\``, `\\\\` and `\\$` lose their backslash, as in the
    shell, and a nested span is rewritten too; a span that never closes runs to the end."""
    out, quote, k, n = [], None, 0, len(text)
    while k < n:
        ch = text[k]
        if quote in ("'", "$'"):
            if ch == "\\" and quote == "$'":
                out.append(text[k:k + 2])
                k += 2
                continue
            if ch == "'":
                quote = None
        elif ch == "\\":
            out.append(text[k:k + 2])
            k += 2
            continue
        elif ch == "`":
            j = backtick_end(text, k)
            inner = re.sub(r"\\([`\\$])", r"\1", text[k + 1:j])
            out.append("$(" + backticks(inner) + ")")
            k = j + 1
            continue
        elif ch == '"':
            quote = None if quote else '"'
        elif not quote and text.startswith("$'", k):
            quote = "$'"
            out.append("$'")
            k += 2
            continue
        elif ch == "'" and not quote:
            quote = "'"
        out.append(ch)
        k += 1
    return "".join(out)


def runs_in(text):
    """The `$(…)` and backtick spans of some text — what the shell runs before the text is used
    (a here-document body, a redirection operand). A span that never closes runs to the end."""
    out, k, n = [], 0, len(text)
    while k < n:
        if text.startswith("$(", k):
            depth, j = 0, k + 1
            while j < n:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(text[k:j + 1])
            k = j + 1
        elif text[k] == "`":
            j = text.find("`", k + 1)
            j = n - 1 if j < 0 else j
            out.append(text[k:j + 1])
            k = j + 1
        else:
            k += 1
    return out


def tokens(text):
    """Shell words; runs of operators the tokeniser glues together (`(<`, `);`, `)&&`) are split."""
    lex = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = ""
    out = []
    for t in lex:
        if t and set(t) <= PUNCT:
            k = 0
            while k < len(t):
                op = next((o for o in OPERATORS if t.startswith(o, k)), t[k])
                out.append(op)
                k += len(op)
        else:
            out.append(t)
    return out


def braces(word, limit=64):
    m = re.search(r"\{([^{}]*,[^{}]*)\}", word)
    if not m:
        return [word]
    out = []
    for alt in m.group(1).split(","):
        out.extend(braces(word[:m.start()] + alt + word[m.end():], limit))
        if len(out) >= limit:
            break
    return out[:limit]


def expand(word, bases):
    """Absolute paths a word can denote: braces, `~`, `$HOME`, `$USER`, relative to each base."""
    out = []
    for w in braces(word):
        c = w
        for home in ("${HOME}", "$HOME"):
            if c.startswith(home):
                c = "~" + c[len(home):]
        user = os.environ.get("USER") or ""
        if user:
            c = c.replace("${USER}", user).replace("$USER", user)
        if c.startswith("~"):
            c = os.path.expanduser(c)
        if "$" in c or "`" in c or not c:
            continue
        for b in bases:
            out.append(os.path.normpath(c if os.path.isabs(c) else os.path.join(b, c)))
    return out


def pathlike(word):
    return bool(word) and "\n" not in word and (
        not any(ch.isspace() for ch in word) or word.startswith(("/", "~/", "$HOME/", "${HOME}/")))


def reaches(word, bases, prot, tainted):
    """Does this word denote a protected file, pointer or directory (or a variable holding one)?"""
    if any(v in tainted for v in VARREF.findall(word)):
        return True
    if not pathlike(word):
        return False
    by_name = "/" in word
    paths = expand(word, bases)
    if not paths:
        name = word.rstrip("/").rsplit("/", 1)[-1]
        return by_name and "$" not in name and "`" not in name and name.casefold() in prot.names
    return any(hits(p, prot, True, by_name) for p in paths)


def interpreter(word):
    base = os.path.basename(word)
    return base in INTERPRETERS or base.startswith("python")


def pattern_args(head, args):
    """Indices of a grep-family command's arguments that are its PATTERN — data, never a file."""
    if head not in GREPS:
        return set()
    value_opts = RG_VALUE_OPTS if head == "rg" else GREP_VALUE_OPTS
    out, explicit, first, i = set(), False, None, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            if first is None and i + 1 < len(args):
                first = i + 1
            break
        if a in ("-e", "--regexp"):
            explicit = True
            out.add(i + 1)
            i += 2
            continue
        if a.startswith("--regexp=") or (a.startswith("-e") and len(a) > 2):
            explicit = True
            out.add(i)
        elif a in ("-f", "--file"):
            explicit = True       # the patterns come from a FILE, which stays a path
            i += 2
            continue
        elif a.startswith("--file="):
            explicit = True
        elif a in value_opts:
            i += 2
            continue
        elif not a.startswith("-") or a == "-":
            if first is None:
                first = i
        i += 1
    if not explicit and first is not None:
        out.add(first)
    return out


def metadata_only(stmt):
    head, args = stmt["head"], stmt["args"]
    if head is None or head in META:
        return True
    if head == "find":
        return not any(a in FIND_EXEC for a in args)
    if head == "git":
        return not any(a in GIT_REACH or a.startswith(("--git-dir=", "--work-tree=")) for a in args)
    return False


def check_group(group, cwd, bases, tainted, prot, held=None):
    """One part of a line (between ; && || & and newlines): its statements, split at pipes and
    parentheses, each with its head, arguments, input redirections and leading assignments. A held
    here-document body (strip_heredocs) is judged where its marker sits: as the string it becomes,
    and word by word when this part of the line runs a shell or an interpreter or reads names."""
    held = held or {}
    stmts, st, redirect, substituted, prev, strings = [], None, None, False, "", []
    unquoted_sub = False
    code = any(interpreter(t) for t in group)
    for t in group:
        if t in STATEMENT_BREAKS:
            if t in ("<(", ">(") or (t == "(" and prev.endswith("$")):
                substituted = True
                unquoted_sub = True
            st, redirect, prev = None, None, t
            continue
        if set(t) <= set("<>&") and ("<" in t or ">" in t):
            redirect, prev = t, t
            continue
        if "$(" in t or "`" in t:
            substituted = True
        if st is None:
            st = {"head": None, "word": None, "args": [], "inputs": [], "assign": [], "runs": [],
                  "held": []}
            stmts.append(st)
        st["held"] += [held[int(n)] for n in HELD.findall(t) if int(n) in held]
        if redirect is not None:
            if redirect in ("<", "<>"):
                st["inputs"].append(t)   # an input redirection reads; the rest are written or data
            elif redirect == "<<<":
                strings.append(t)
            st["runs"] += runs_in(t)     # …but a `$(…)` or backtick in ANY operand is run by the shell
            redirect, prev = None, t
            continue
        if st["head"] is None and ASSIGNMENT.match(t):
            st["assign"].append(t)
        elif st["head"] is None:
            st["head"], st["word"] = os.path.basename(t), t
        else:
            st["args"].append(t)
        prev = t
    consumed = any(s["head"] in NAME_CONSUMERS or (s["head"] and interpreter(s["head"])) for s in stmts)
    fed = code or consumed or any(runs_stdin(w) for w in simple_commands(group))
    reached, unsafe = False, False
    for s in stmts:
        skip = pattern_args(s["head"], s["args"])
        atoms = s["inputs"] + [a for k, a in enumerate(s["args"]) if k not in skip]
        atoms += [ASSIGNMENT.match(a).group(2) for a in s["assign"]]
        if s["word"] and "/" in s["word"]:
            atoms.append(s["word"])                     # running a protected file by its path
        for a in s["args"] + s["assign"]:
            if code or "$(" in a or "`" in a:
                atoms += CODE_ATOM.findall(a)           # the words of a code string or substitution
                atoms += [x or y for x, y in QUOTED.findall(a)]   # …and its quoted strings, spaces kept
        for a in s["runs"]:
            atoms += CODE_ATOM.findall(a)               # the words a redirection operand's $(…) runs
        for body in s["held"]:
            atoms.append(body.rstrip("\n"))            # the string a held body becomes…
            if fed:
                atoms += CODE_ATOM.findall(body)        # …run as code, or read as names
        if any(reaches(a, bases, prot, tainted) for a in atoms):
            reached = True
            unsafe = unsafe or not metadata_only(s)
        for a in s["assign"] + (s["args"] if s["head"] in ("export", "local", "readonly", "declare") else []):
            m = ASSIGNMENT.match(a)
            if m and reaches(m.group(2), bases, prot, tainted):
                tainted.add(m.group(1))                 # one hop: `P=<protected>; cat "$P"`
        if s["head"] in ("cd", "pushd"):
            target = next((a for a in s["args"] if not a.startswith("-")), None)
            if target:
                # each `cd` doubles the bases; past the cap keep the first, the newest (the last has
                # every `cd` applied) and any at or above a protected directory
                grown = bases + [p for b in bases for p in expand(target, [b])]
                grown = list(reversed(list(dict.fromkeys(reversed(grown)))))
                if len(grown) > BASE_LIMIT:
                    keep = set(grown[:1] + grown[1 - BASE_LIMIT:])
                    grown = [b for b in grown if b in keep or prot.above(b)]
                bases[:] = grown
    if reached and (unsafe or substituted or consumed):
        deny(prot, "the command reads a protected file, its pointer or its directory")
    shell = any(interpreter(t) and os.path.basename(t) in SHELLS | {"eval"} for t in group)
    pm_group(stmts, bases, "shell" if shell else "script" if code else None, unquoted_sub)
    if strings and any(runs_stdin(w) for w in simple_commands(group)):
        for s in strings:                               # `bash <<<'…'` runs the here-string's text
            check_shell(s, cwd, prot, bases, tainted)


def check_shell(cmd, cwd, prot, bases=None, tainted=None):
    first_body = len(PM_BODIES)
    text, scripts, held = strip_heredocs(cmd)    # bodies first: a body's stray quote must not span
    text = backticks(strip_comments(text))
    bases = [cwd] if bases is None else bases
    tainted = set() if tainted is None else tainted
    try:
        toks = tokens(text)
    except ValueError:
        if NAMED.search(text) or any(d and d != "/" and d in text.casefold() for d in prot.dir_spellings):
            deny(prot, "a command that names a protected file could not be parsed")
        pm_raw(text, bases)
        toks = []
    groups, cur = [], []
    for t in toks:
        if t in GROUP_SEPARATORS:
            groups.append(cur)
            cur = []
        else:
            cur.append(t)
    groups.append(cur)
    for g in groups:
        if g:
            check_group(g, cwd, bases, tainted, prot, held)
    pm_bodies(PM_BODIES[first_body:], bases)
    for s in scripts:                            # after the line: its `cd` and assignments carry in
        check_shell(s, cwd, prot, bases, tainted)


# ---------- the file tools ----------

def resolve(path, cwd):
    p = os.path.expanduser(path)
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd, p))


def check_grep_tool(ti, cwd, prot):
    if (ti.get("output_mode") or "files_with_matches") != "content":
        return
    path = ti.get("path") or cwd
    if not isinstance(path, str):
        raise TypeError("Grep path is not a string")
    if not hits(resolve(path, cwd), prot, True):
        return
    pattern = ti.get("glob")
    if pattern:
        # a negation restricts nothing; a path glob (`**/*.sh`) is judged by its file-name part
        pats = set()
        for g in braces(pattern):
            if g.startswith("!"):
                continue
            pats.update((g.casefold(), g.casefold().rsplit("/", 1)[-1]))
        if pats and not any(fnmatch.fnmatchcase(n, g) for g in pats for n in prot.names):
            return
    if ti.get("type") and ti.get("type") not in ("sh", "shell", "bash", "all"):
        return
    deny(prot, "a content search over a protected file")


def pm_paths(value, cwd, depth=0):
    """Every path-like string in a tool's input, resolved — for connector tools, whose field names
    vary (a PDF reader's `path`, a viewer's `file_path`, a `file://` URL)."""
    if depth > 6:
        return
    if isinstance(value, str):
        v = value
        if v[:5].casefold() == "file:":
            # `file:///a%20b/c`, `file://localhost/…`, `file:/…`: the path, decoded; the authority is
            # not trusted to mean another machine — a tool may simply ignore it
            try:
                v = unquote(urlsplit(v).path)
            except ValueError:                   # e.g. `file://[…`: take everything from the first /
                rest = v[5:].lstrip("/")
                v = unquote("/" + rest[rest.find("/") + 1:] if "/" in rest else "/" + rest)
        if v and "\n" not in v and ("/" in v or "." in v) and len(v) < 4096:
            yield resolve(v, cwd)
    elif isinstance(value, dict):
        for x in value.values():
            yield from pm_paths(x, cwd, depth + 1)
    elif isinstance(value, list):
        for x in value[:256]:
            yield from pm_paths(x, cwd, depth + 1)


def check_pm_grep(ti, cwd):
    if (ti.get("output_mode") or "files_with_matches") != "content":
        return
    path = ti.get("path") or cwd
    if not isinstance(path, str):
        raise TypeError("Grep path is not a string")
    kind = pm_original(resolve(path, cwd))
    if kind is None:
        return
    # exempt only a search that a positive glob keeps to Markdown: a negation (`!*.md`) selects
    # everything else, and a mixed brace (`{*.md,*.txt}`) still reaches an original
    pattern = ti.get("glob")
    positive = [g for g in braces(pattern) if not g.startswith("!")] if pattern else []
    md_only = (positive and all(g.casefold().endswith(".md") for g in positive)) or \
        str(ti.get("type") or "").casefold() in ("md", "markdown")
    if kind == "dir" and md_only:
        return
    deny_pm("a content search over a private-mode person's originals")


def main(argv):
    text, prot = "", None
    try:
        text = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(text) if text.strip() else {}
        if not isinstance(data, dict):
            raise TypeError("the hook payload is not an object")
        cwd = data.get("cwd") or os.getcwd()
        if not isinstance(cwd, str):
            raise TypeError("cwd is not a string")
        prot = load(argv, os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
        tool, ti = data.get("tool_name") or "", data.get("tool_input") or {}
        if not isinstance(ti, dict):
            raise TypeError("tool_input is not an object")
        if tool in SHELL_TOOLS:
            cmd = ti.get("command") or ""
            if not isinstance(cmd, str):
                raise TypeError("command is not a string")
            check_shell(cmd, cwd, prot)
        elif tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
            path = ti.get("file_path") or ti.get("notebook_path") or ""
            if not isinstance(path, str):
                raise TypeError("file path is not a string")
            if path and hits(resolve(path, cwd), prot, False):
                deny(prot, "a file tool on a protected file or its pointer")
            if tool == "Read" and path and pm_original(resolve(path, cwd)):
                deny_pm("Read of a private-mode person's original")
        elif tool == "Grep":
            check_grep_tool(ti, cwd, prot)
            check_pm_grep(ti, cwd)
        elif tool in PM_UPLOAD_TOOLS or (tool.startswith("mcp__") and tool not in PM_VIEWERS):
            if any(pm_original(p) for p in pm_paths(ti, cwd)):
                deny_pm("a tool given a private-mode person's original")
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 — a call the guard could not analyse is judged on its raw text
        dirs = prot.dir_spellings if prot is not None else set()
        if NAMED.search(text) or any(d and d != "/" and d in text.casefold() for d in dirs):
            deny(prot, "the guard could not analyse a call that names a protected file (fail closed)")
        try:
            pm_raw(text, [os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()])
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
