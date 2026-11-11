"""Copy on-screen interview answers into a person's record word for word (ADR-0041 point 3) —
stdlib only.

A care session asks questions with the client's on-screen question tool (AskUserQuestion in Claude
Code). The client stores each call and its answers in the session transcript,
`~/.claude/projects/<folder>/<session>.jsonl`: the call on an assistant line (`tool_use`, its
`input.questions`), the answers on the user line that returns it (`toolUseResult.answers`, keyed by
the question text; a several-choice answer may be a list; text typed under "Other" is kept as typed,
commas included, and never split). Transcripts live outside the record and the client prunes them, so
this module copies the calls into a source file in the person's `med/sources/interviews/` — no model
types an answer anywhere on the way.

The file is Markdown (stored evidence stays readable Markdown, ADR-0041 (e)). Every question,
answer and note sits in its own fenced block whose fence is one backtick longer than any backtick
run inside it, so a block's bytes are recovered exactly. Its header prints its own citation,
`(operator, <dated name>, B)`, the form `quotes` reads (format 2; `verify` re-renders a format-1 file
with its own wording). Two hashes bind it:
- `answers_sha256` — over the questions, answers and notes as parsed back from the file itself, so an
  answer altered in the file is caught even after the transcript is gone (`verify`);
- `transcript_sha256` — over the raw transcript lines the calls came from, so `verify` can re-render
  the file from the transcript, while it still exists, and compare every byte.
Once inventoried, the ownership ledger (L13) binds the file's bytes as for any source.

A call is filed once, for one person: ids already filed for anyone (from any session — a resumed
session repeats the old calls under the same ids) are skipped, and once a session's call is filed for
one person the default refuses for another. A capture file an interruption left un-inventoried is
completed on the next run.

`quotes` checks the other end: a quotation in `profile.md` or `medications.md` that cites an
interview file by its dated name must be found word for word in one answer or note of that file,
compared after NFC with whitespace runs as one space (ellipses split a quotation into fragments that
must appear in order); wrapped prose is read as one line, and neither an open item's label nor a
quotation followed by another source's citation is read. It is a workflow step the filing procedure
runs after reconciliation, not a board guard (guard-admission, 2026-10-19). Residuals: ADR-0041
point 6.

Regular package so `python3 -m tools.interview_capture` and
`python3 -m unittest tools.interview_capture.test_interview_capture` both resolve.
"""
import datetime
import glob
import hashlib
import json
import os
import re
import unicodedata

TOOL_NAME = "AskUserQuestion"
STATUS_WHY = {
    "unanswered": "it has no answers (declined, interrupted or failed) — ask again if needed",
    "duplicate-question": "two of its questions have the same text, so their answers cannot be told "
                          "apart — ask the operator again",
    "answer-without-question": "it holds an answer for a question the call does not show — ask the "
                               "operator again",
    "off-branch": "the conversation was rewound or edited past it, so its answers were taken back — "
                  "not evidence",
}
FORMAT = "interview_capture 2"
# The header's closing sentence by format. Format 2 (ADR-0041 point 7) prints the file's
# own citation: sessions told only to cite it "by its name" cited it by date, which `quotes` never
# reads. `verify` re-renders a file in the format its own `format:` line names.
_CITE_SENTENCE = {
    "interview_capture 1": "cite this file by its name.",
    "interview_capture 2": "cite it right after the quotation exactly as `{cite}` — this file's dated "
                           "name, not its heading or a date alone.",
}
CAPTURE_MARK = "capture: on-screen questions"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
INTERVIEW_NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}__interview__[A-Za-z0-9-]+(?:__\d+)?)(?:\.md)?")


class CaptureError(Exception):
    """A refusal: nothing was written. The message names one next step."""


# ---- transcripts --------------------------------------------------------------------------------

def session_key(session_id):
    """A session id as the file stores it: 32 hex digits, no hyphens. A hyphenated UUID's last group
    is 12 characters, all digits about once in 300 sessions — an 11-digit run the private-mode guard
    (L10) reds on — while a 32-hex token with a letter is one it reads as a digest."""
    k = (session_id or "").replace("-", "").lower()
    return k if re.match(r"^[0-9a-f]{32}$", k) else session_id


def _dashed(key):
    if re.match(r"^[0-9a-f]{32}$", key or ""):
        return "%s-%s-%s-%s-%s" % (key[:8], key[8:12], key[12:16], key[16:20], key[20:])
    return key


def find_transcript(session_id, config_dir=None):
    """The one `<session>.jsonl` under the client's projects folder, or a CaptureError."""
    session_id = _dashed(session_id)
    if not session_id or not re.match(r"^[0-9A-Za-z-]{8,64}$", session_id):
        raise CaptureError("no usable session id: pass --session <id> or --transcript <path>")
    base = config_dir or os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    hits = sorted(glob.glob(os.path.join(base, "projects", "*", session_id + ".jsonl")))
    if len(hits) != 1:
        raise CaptureError("%s transcript(s) found for session %s under %s/projects: pass --transcript"
                           % (len(hits) or "no", session_id, base))
    return hits[0]


def _parse_ts(text):
    """An ISO time; naive input is read as local time. Returns an aware UTC datetime."""
    t = text.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    d = datetime.datetime.fromisoformat(t)
    if d.tzinfo is None:
        d = d.astimezone()
    return d.astimezone(datetime.timezone.utc)


def read_calls(path):
    """Every on-screen question call in a transcript, in order, answered or not.

    Each call: dict(n, tool_use_id, asked_at, answered_at, questions, answers, notes, raw, status).
    `raw` is the list of raw transcript lines (bytes, no newline) the call came from; `status` is
    'answered', 'unanswered' (declined, interrupted or failed) or 'duplicate-question' (two
    questions with the same text: their answers cannot be told apart)."""
    uses, order = {}, []
    parent, by_msg, last = {}, {}, None
    with open(path, "rb") as fh:
        lines = fh.read().split(b"\n")
    for raw in lines:
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        uid = rec.get("uuid")
        msg = rec.get("message")
        if isinstance(uid, str):
            # a compaction boundary has no parent but names its logical one
            parent[uid] = rec.get("parentUuid") or rec.get("logicalParentUuid")
            last = uid
            if isinstance(msg, dict) and isinstance(msg.get("id"), str):
                by_msg.setdefault(msg["id"], set()).add(uid)
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == TOOL_NAME:
                qs = (block.get("input") or {}).get("questions")
                if not isinstance(qs, list) or block.get("id") in uses:
                    continue
                call = {"tool_use_id": block["id"], "asked_at": rec.get("timestamp", ""),
                        "answered_at": "", "questions": qs, "answers": {}, "notes": {},
                        "raw": [raw], "status": "unanswered", "_lines": {uid},
                        "_msg": msg.get("id")}
                uses[block["id"]] = call
                order.append(call)
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in uses:
                call = uses[block["tool_use_id"]]
                if call["answered_at"]:
                    continue
                call["_lines"].add(uid)
                result = rec.get("toolUseResult")
                answers = result.get("answers") if isinstance(result, dict) else None
                call["raw"].append(raw)
                call["answered_at"] = rec.get("timestamp", "")
                if block.get("is_error") or not isinstance(answers, dict):
                    continue
                call["answers"] = answers
                ann = result.get("annotations")
                if isinstance(ann, dict):
                    call["notes"] = {k: v.get("notes") for k, v in ann.items()
                                     if isinstance(v, dict) and isinstance(v.get("notes"), str)
                                     and v.get("notes")}
                texts = [q.get("question") for q in call["questions"] if isinstance(q, dict)]
                if len(set(texts)) != len(texts):
                    call["status"] = "duplicate-question"
                elif set(answers) - set(texts) or set(call["notes"]) - set(texts):
                    call["status"] = "answer-without-question"
                else:
                    call["status"] = "answered"
    # The live conversation is the ancestry of the transcript's last line. A rewind, or an edit of an
    # earlier message, leaves the old branch in the file; its answers were taken back. A call is live
    # when its line, its result's line or any line of its assistant message is on that ancestry
    # (parallel tool calls branch within one message). A transcript without line ids is all live.
    live, u = set(), last
    while u and u not in live:
        live.add(u)
        u = parent.get(u)
    for i, call in enumerate(order, 1):
        call["n"] = i
        mine = call.pop("_lines") | by_msg.get(call.pop("_msg"), set())
        if parent and call["status"] == "answered" and not (mine & live):
            call["status"] = "off-branch"
    return order


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in value]
    return [value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)]


def canonical(calls):
    """The questions, answers and notes the hash binds: exactly what the file's blocks hold."""
    out = []
    for c in calls:
        for k, q in enumerate(c["questions"], 1):
            text = q.get("question", "")
            out.append(["%d.%d" % (c["n"], k), text, _as_list(c["answers"].get(text)),
                        c["notes"].get(text)])
    return out


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def answers_hash(items):
    blob = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha(blob.encode("utf-8"))


def transcript_hash(calls):
    return _sha(b"".join(r + b"\n" for c in calls for r in c["raw"]))


# ---- rendering ----------------------------------------------------------------------------------

def _fence(text, info):
    runs = [len(m) for m in re.findall(r"`+", text)]
    f = "`" * max(3, max(runs or [0]) + 1)
    return "%s%s\n%s\n%s\n" % (f, info, text, f)


def _offset_of(ts):
    """The local UTC offset at time `ts`, as `+HH:MM`."""
    z = _parse_ts(ts).astimezone().strftime("%z") or "+0000"
    return z[:3] + ":" + z[3:]


def _tz(offset):
    m = re.match(r"^([+-])(\d{2}):(\d{2})$", offset or "")
    if not m:
        raise CaptureError("the file's offset line is missing or damaged")
    mins = int(m.group(2)) * 60 + int(m.group(3))
    return datetime.timezone(datetime.timedelta(minutes=-mins if m.group(1) == "-" else mins))


def _one_line(text):
    return " ".join(str(text).split())


def dated_name(path):
    """A file's dated name: its file name without `.md`, the form a citation names."""
    return os.path.splitext(os.path.basename(path))[0]


def citation(name):
    """The citation of an interview file's on-screen answers, in the record's own form."""
    return "(operator, %s, B)" % name


def render(handle, session_id, calls, filed_at, offset, name, fmt=FORMAT):
    """The source file's text. Deterministic in its inputs, so `verify` can re-render it; `offset`
    (`+02:00`) is the local UTC offset at filing, stored so the heading never depends on where it
    is re-rendered; `name` is the file's own dated name, which the header cites; `fmt` is the format
    to render, so a file filed in an earlier one re-renders as it was written."""
    if fmt not in _CITE_SENTENCE:
        raise CaptureError("the file's format line names a format this tool does not know")
    m = INTERVIEW_NAME_RE.fullmatch(name or "")
    if fmt != "interview_capture 1" and not (m and m.group(1) == name):     # format 1 cites no name
        raise CaptureError("the file's name is not an interview file's dated name "
                           "(YYYY-MM-DD__interview__<slug>.md)")
    items = canonical(calls)
    first = _parse_ts(calls[0]["answered_at"]).astimezone(_tz(offset))
    fm = ["---", CAPTURE_MARK, "person: " + handle, "session: " + session_key(session_id),
          "asked: " + calls[0]["asked_at"], "answered: " + calls[-1]["answered_at"],
          "filed: " + filed_at, "offset: " + offset, "evidence: B — the operator's answers as given on screen",
          "calls: " + " ".join(c["tool_use_id"] for c in calls),
          "transcript_sha256: " + transcript_hash(calls),
          "answers_sha256: " + answers_hash(items), "format: " + fmt, "---", ""]
    out = ["\n".join(fm),
           "# On-screen questions, %s\n\n" % first.strftime("%Y-%m-%d %H:%M"),
           "Copied from the session transcript by `tools/interview_capture`; no model typed these "
           "answers. Each question, answer and note sits between two fence lines of backticks, which "
           "are not part of it. Quote an answer by copying it from its block, and %s\n"
           % _CITE_SENTENCE[fmt].format(cite=citation(name))]
    for c in calls:
        out.append("\n## Call %d — answered %s\n\ntool_use: %s\n"
                   % (c["n"], c["answered_at"], c["tool_use_id"]))
        for k, q in enumerate(c["questions"], 1):
            text = q.get("question", "")
            several = bool(q.get("multiSelect"))
            labels = [o.get("label", "") for o in q.get("options") or [] if isinstance(o, dict)]
            out.append("\n### %d.%d · %s\n\nquestion:\n" % (c["n"], k, _one_line(q.get("header", ""))))
            out.append(_fence(text, "question"))
            opt_lines = []
            for o in q.get("options") or []:
                if not isinstance(o, dict):
                    continue
                opt_lines.append("- " + o.get("label", ""))
                for part in ("description", "preview"):
                    if o.get(part):
                        opt_lines += ["    %s: %s" % (part, ln) for ln in str(o[part]).split("\n")]
            out.append("\noptions (%s):\n" % ("several may be chosen" if several else "one choice"))
            out.append(_fence("\n".join(opt_lines), "options"))
            answers = _as_list(c["answers"].get(text))
            if not answers:
                out.append("\nanswer: none recorded\n")
            for a in answers:
                how = "an option" if a in labels else (
                    "as given; may join several choices" if several else "typed by the operator")
                out.append("\nanswer (%s):\n" % how)
                out.append(_fence(a, "answer"))
            note = c["notes"].get(text)
            if note:
                out.append("\nnote (typed by the operator):\n")
                out.append(_fence(note, "note"))
    return "".join(out)


# ---- reading a filed file back ------------------------------------------------------------------

_OPEN_RE = re.compile(r"^(`{3,})([a-z]*)$")
_ITEM_RE = re.compile(r"^### (\d+\.\d+) · ")


def parse_file(text):
    """(frontmatter dict, canonical items) from a filed interview file's own text."""
    lines = text.split("\n")
    fm = {}
    if (lines[0] == "---" and "---" not in lines[1:]
            and (len(lines) < 2 or CAPTURE_MARK.startswith(lines[1]) or lines[1] == CAPTURE_MARK)):
        raise CaptureError("a capture header cut off before its closing line: the file is damaged")
    if lines and lines[0] == "---" and "---" in lines[1:]:
        end = lines.index("---", 1)
        for entry in lines[1:end]:
            key, _, val = entry.partition(": ")
            fm[key] = val
        if CAPTURE_MARK in lines[1:end]:
            fm["capture"] = "on-screen questions"
        lines = lines[end + 1:]
    if not fm.get("capture"):
        return fm, []                     # a sheet-era file: its fences are not this tool's
    items, cur, i = [], None, 0
    while i < len(lines):
        m = _OPEN_RE.match(lines[i])
        if m:
            fence, kind = m.group(1), m.group(2)
            j = i + 1
            while j < len(lines) and lines[j] != fence:
                j += 1
            if j >= len(lines):
                raise CaptureError("an unclosed block: the file is damaged")
            body = "\n".join(lines[i + 1:j])
            if cur is not None:
                if kind == "question":
                    cur[1] = body
                elif kind == "answer":
                    cur[2].append(body)
                elif kind == "note":
                    cur[3] = body
            i = j + 1
            continue
        m = _ITEM_RE.match(lines[i])
        if m:
            cur = [m.group(1), "", [], None]
            items.append(cur)
        i += 1
    return fm, items


def _interview_files(root, damaged=None):
    """(handle, path, frontmatter) for every on-screen capture file under patients/. A file in an
    interviews/ folder that is empty or cannot be read back is appended to `damaged` when given."""
    for p in sorted(glob.glob(os.path.join(root, "patients", "*", "med", "sources", "interviews",
                                           "*.md"))):
        try:
            with open(p, encoding="utf-8", newline="") as fh:
                text = fh.read()
            fm, _ = parse_file(text)
        except (OSError, UnicodeDecodeError, CaptureError):
            if damaged is not None:
                damaged.append(p)
            continue
        if not text.strip() and damaged is not None:
            damaged.append(p)
        if fm.get("capture"):
            yield p.split(os.sep)[-5], p, fm


def filed_calls(root):
    """{tool_use id: handle} for every call already filed for anyone, from any session. A tool_use
    id is the call's own: a resumed session copies the old calls under the same ids. Refuses while
    any interviews/ file cannot be read back: its calls could not be counted."""
    done, damaged = {}, []
    files = list(_interview_files(root, damaged))
    if damaged:
        raise CaptureError("%s is empty or cannot be read back (an interrupted or damaged filing): "
                           "ask the operator before filing anything"
                           % os.path.relpath(damaged[0], root))
    for handle, _, fm in files:
        for tid in fm.get("calls", "").split():
            done.setdefault(tid, handle)
    return done


def _ledger_relpaths(med):
    from tools.person_ownership import schema
    try:
        with open(os.path.join(med, "MANIFEST"), "rb") as fh:
            records = schema.parse_manifest_bytes(fh.read())
    except (OSError, schema.ManifestError):
        return None
    return {r.get("source_relpath") for r in records if isinstance(r, dict)}


# ---- selecting and filing -----------------------------------------------------------------------

def _bound(text, end=False):
    """--since/--until: a bare date means the whole day, so --until's runs to that day's end."""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text.strip()):
        d = _parse_ts(text.strip() + "T00:00")
        return d + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1) if end else d
    return _parse_ts(text)


def select(calls, since=None, until=None, numbers=None, filed=None, handle=None,
           several_people=False, take_all=False, recovering=()):
    """(calls to file, calls skipped as unfilable). `filed` maps tool_use ids already filed to
    their person. Explicit numbers must each be answered and not filed for anyone; the default
    refuses outright once any call of this transcript is filed for another person — the session
    held more than one person, so the operator names this person's calls."""
    filed = filed or {}
    lo = _bound(since) if since else None
    hi = _bound(until, end=True) if until else None
    if numbers:
        if since or until:
            raise CaptureError("--call names the calls itself: drop --since/--until")
        by_n = {c["n"]: c for c in calls}
        picked = []
        for n in sorted(set(numbers)):
            c = by_n.get(n)
            if c is None:
                raise CaptureError("there is no call %d in this transcript (see `list`)" % n)
            if c["status"] != "answered":
                raise CaptureError("call %d cannot be filed: %s" % (n, STATUS_WHY[c["status"]]))
            if c["tool_use_id"] in recovering:
                continue                          # held by this person's interrupted filing
            if c["tool_use_id"] in filed:
                raise CaptureError("call %d is already filed%s" % (
                    n, "" if filed[c["tool_use_id"]] == handle else " for another person"))
            picked.append(c)
        return sorted(picked, key=lambda c: c["n"]), []
    if several_people and not take_all:
        raise CaptureError("this record holds more than one person: name this person's own calls "
                           "with --call N (see `list`), or pass --all when every question in this "
                           "session was about them")
    others = sorted({filed[c["tool_use_id"]] for c in calls if c["tool_use_id"] in filed} - {handle})
    if others:
        raise CaptureError("some of this session's calls are already filed for another person, so it "
                           "held more than one: name this person's own calls with --call N (see `list`)")
    picked, skipped = [], []
    for c in calls:
        if c["tool_use_id"] in filed:
            continue
        at = _parse_ts(c["answered_at"]) if c["answered_at"] else None
        if (lo and (at is None or at < lo)) or (hi and (at is None or at > hi)):
            continue
        if c["status"] == "answered":
            picked.append(c)
        elif c["status"] != "unanswered":
            skipped.append(c)
    return picked, skipped


def target_path(sources_dir, calls, slug, offset):
    if not SLUG_RE.match(slug):
        raise CaptureError("slug must be lower-case letters, digits and hyphens")
    day = _parse_ts(calls[0]["answered_at"]).astimezone(_tz(offset)).strftime("%Y-%m-%d")
    folder = os.path.join(sources_dir, "interviews")
    base = "%s__interview__%s" % (day, slug)
    name, k = base + ".md", 2
    while os.path.lexists(os.path.join(folder, name)):
        name, k = "%s__%d.md" % (base, k), k + 1
    return os.path.join(folder, name)


class LedgerRefused(CaptureError):
    """The ownership ledger refused the new file; it was removed again."""


class LedgerInterrupted(CaptureError):
    """Registration stopped for another reason than the ledger's refusal; the file is kept."""


class LedgerKept(CaptureError):
    """The file is inventoried, but attesting it (`confirm`) was refused; the file stays."""


def _ledger_reason(e, relpaths):
    """The ledger's refusal without the removed file: no `--relpath` for it, no `confirm` line."""
    import shlex
    lines = []
    for line in str(e).split("\n"):
        if any(" confirm --relpath " + shlex.quote(rp) in line for rp in relpaths):
            continue
        for rp in relpaths:
            line = line.replace(" --relpath " + shlex.quote(rp), "")
        lines.append(line)
    return "\n".join(lines).strip()


def register(root, handle, relpaths, confirmed=False, attest=()):
    """Inventory capture files as the filing procedure's step 3 does: `init` when the person has no
    ledger yet, else `append add`; files in `attest` are recorded as operator-confirmed when
    `confirmed` (by `confirm` afterwards when the op could not carry it). Returns how many other
    sources a first ledger took in. Raises LedgerRefused with the ledger's own reason, or LedgerKept
    when only the attestation after the files were inventoried failed."""
    from tools.person_ownership import append as _append
    med = os.path.join(root, "patients", handle, "med")
    # every file in one op (the ledger refuses an op while another file is pending); attestation of
    # the new file only, by `confirm` afterwards whenever the op could not carry it
    first = not os.path.lexists(os.path.join(med, "MANIFEST"))
    one_op = not first and confirmed and list(attest) == list(relpaths)
    try:
        if first:
            _append.init_ledger(root, handle)
        else:
            _append.add_source(root, handle, list(relpaths), confirmed=one_op)
    except _append.AppendStop as e:
        raise LedgerRefused("the ownership ledger refused it —\n" + _ledger_reason(e, relpaths))
    try:
        for rp in attest if confirmed and not one_op else ():
            _append.confirm(root, handle, rp)
    except _append.AppendStop as e:
        raise LedgerKept("the file is filed and inventoried, unverified; confirming it was refused — "
                         + str(e))
    if not first:
        return 0
    known = _ledger_relpaths(med) or set()
    return len(known - set(relpaths))


def _orphans(root, handle):
    """This person's capture files on disk that the ledger does not hold (an interrupted filing).
    Each must name this person and hold no call filed in another file, or it refuses."""
    pdir = os.path.join(root, "patients", handle)
    known = _ledger_relpaths(os.path.join(pdir, "med"))
    files = list(_interview_files(root))
    out = []
    for h, p, fm in files:
        rp = os.path.relpath(p, pdir).replace(os.sep, "/")
        if h != handle or (known is not None and rp in known):
            continue
        mine = set(fm.get("calls", "").split())
        elsewhere = any(q != p and mine & set(f.get("calls", "").split()) for _, q, f in files)
        problems, _ = verify(p, transcript=False)
        if problems or fm.get("person") != handle or elsewhere:
            raise CaptureError("%s is on disk but not inventoried, and %s: ask the operator before "
                               "anything else" % (rp, "names another person" if fm.get("person") != handle
                                                  else "holds a call filed elsewhere" if elsewhere
                                                  else "no longer matches its own hash"))
        out.append(rp)
    return out


def _calls_in(pdir, relpaths):
    out = set()
    for rp in relpaths:
        with open(os.path.join(pdir, rp), encoding="utf-8", newline="") as fh:
            out.update(parse_file(fh.read())[0].get("calls", "").split())
    return out


def _write_whole(path, text, tmpdir):
    """The file appears whole or not at all: written beside the ledger (outside sources/, which L13
    scans), then hard-linked into place, which refuses an existing name. A temp file a crash left
    behind is removed on the next run."""
    for stale in glob.glob(os.path.join(tmpdir, ".interview-capture-*.tmp")):
        os.unlink(stale)
    tmp = os.path.join(tmpdir, ".interview-capture-%d.tmp" % os.getpid())
    try:
        with open(tmp, "x", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.link(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def _people(root):
    return [d for d in sorted(os.listdir(os.path.join(root, "patients")))
            if not d.startswith((".", "_")) and os.path.isfile(os.path.join(root, "patients", d,
                                                                             "profile.md"))]


def file_interview(root, handle, transcript, session_id=None, since=None, until=None,
                   numbers=None, slug="on-screen", confirmed=False, now=None, do_register=True,
                   take_all=False):
    """Write the source file and inventory it, or write nothing. Returns a dict: path (None when
    only an interrupted earlier filing was completed), calls, skipped, recovered, swept_in."""
    pdir = os.path.join(root, "patients", handle)
    sources = os.path.join(pdir, "med", "sources")
    if handle.startswith(".") or os.sep in handle or not os.path.isfile(os.path.join(pdir, "profile.md")):
        raise CaptureError("no patients/<handle>/profile.md for that handle: check the spelling")
    session_id = session_id or os.path.splitext(os.path.basename(transcript))[0]
    filed = filed_calls(root)
    recovered = _orphans(root, handle) if do_register else []
    recovering = {t for t, h in filed.items() if h == handle} & _calls_in(pdir, recovered)
    calls, skipped = select(read_calls(transcript), since, until, numbers, filed, handle,
                            several_people=len(_people(root)) > 1, take_all=take_all,
                            recovering=recovering)
    result = {"path": None, "calls": calls, "skipped": skipped, "recovered": recovered,
              "swept_in": 0}
    if not calls and not recovered:
        why = ("no answered call left to file in this window (see `list`)" if not skipped else
               "no call left that can be filed: %s"
               % "; ".join("call %d: %s" % (c["n"], STATUS_WHY[c["status"]]) for c in skipped))
        raise CaptureError(why)
    new = []
    if calls:
        filed_at = (now or datetime.datetime.now(datetime.timezone.utc)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        offset = _offset_of(calls[0]["answered_at"])
        path = target_path(sources, calls, slug, offset)          # first: the header cites it
        text = render(handle, session_id, calls, filed_at, offset, dated_name(path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _write_whole(path, text, os.path.join(pdir, "med"))
        result["path"] = path
        new = [os.path.relpath(path, pdir).replace(os.sep, "/")]
    if do_register:
        try:
            result["swept_in"] = register(root, handle, recovered + new, confirmed, attest=new)
        except LedgerRefused:
            # the ledger's refusal writes nothing (append.AppendStop), so nothing refers to the file
            if result["path"]:
                os.unlink(result["path"])
            raise
        except LedgerKept:
            raise
        except BaseException as e:
            # anything else may have stopped between the ledger and its checkpoint: keep the file
            raise LedgerInterrupted(
                "the ledger write was interrupted (%s: %s); the interview file is kept. Run "
                "`python3 -m tools.person_ownership --root . verify`: on a checkpoint mismatch run "
                "`python3 -m tools.person_ownership --root . refresh-checkpoint %s`, then run `file` "
                "again, which completes the filing if it is still not inventoried"
                % (type(e).__name__, e, handle))
    return result


# ---- verify -------------------------------------------------------------------------------------

def verify(path, transcript=None, config_dir=None):
    """(problems, notes) for a filed interview file. Empty problems = it holds what was captured.
    `transcript=False` checks the file against its own hash only."""
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    fm, items = parse_file(text)
    if not fm.get("capture"):
        return ["not an on-screen interview file (no capture line)"], []
    problems, notes = [], []
    if answers_hash(items) != fm.get("answers_sha256"):
        problems.append("a question, answer or note differs from what was captured "
                        "(answers_sha256 does not match the file's blocks)")
    if transcript is False:
        return problems, notes
    if transcript is None:
        try:
            transcript = find_transcript(fm.get("session", ""), config_dir)
        except CaptureError:
            notes.append("the transcript is no longer on disk: checked against the file's own hash "
                         "only (the ownership ledger binds its bytes)")
            return problems, notes
    wanted = fm.get("calls", "").split()
    by_id = {c["tool_use_id"]: c for c in read_calls(transcript)}
    if any(w not in by_id for w in wanted):
        problems.append("a call this file names is not in the transcript")
        return problems, notes
    calls = [by_id[w] for w in wanted]
    if transcript_hash(calls) != fm.get("transcript_sha256"):
        problems.append("the transcript lines differ from the ones this file was made from")
    try:
        again = render(fm.get("person", ""), fm.get("session", ""), calls, fm.get("filed", ""),
                       fm.get("offset", ""), dated_name(path), fm.get("format", ""))
    except CaptureError as e:
        again = None
        problems.append(str(e))
    if again is not None and again != text:
        problems.append("the file differs from a fresh copy of the transcript")
    elif again is not None:
        notes.append("byte-identical to a fresh copy of the transcript")
    return problems, notes


# ---- quotes -------------------------------------------------------------------------------------

# Typographic forms first: a straight-quote match overlapping one already taken is dropped.
_QUOTE_RES = [re.compile(p) for p in (
    r"„([^”“\"\n]+)[”“\"]", r",,([^”“\"\n]+)[”“\"]", r"“([^”\n]+)”", r"«([^»\n]+)»",
    r"‘([^’\n]+)’", r'"([^"\n]+)"')]
_ELLIPSIS_RE = re.compile(r"\s*(?:\[…\]|\[\.\.\.\]|…|\.\.\.)\s*")
_TRAIL_PUNCT = ".,"


def _norm(text):
    """Unicode NFC, every run of whitespace (no-break spaces and line breaks included) one space."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def _splits_decimal(block, i):
    """Offset `i` falls inside a digit, comma or full stop, digit run ("2,5", "2.50")."""
    return any(j >= 0 and block[j:j + 1].isdigit() and block[j + 1:j + 2] in (",", ".")
               and block[j + 2:j + 3].isdigit() for j in (i - 2, i - 1))


def _at_bounds(block, k, f):
    """A fragment starts and ends where a word or number does: never inside "12 mg" or "2,5"."""
    before = block[k - 1] if k else ""
    after = block[k + len(f)] if k + len(f) < len(block) else ""
    if f[0].isalnum() and before.isalnum():
        return False
    if f[-1].isalnum() and after.isalnum():
        return False
    return not (_splits_decimal(block, k) or _splits_decimal(block, k + len(f)))


def _fragments_in(fragments, block):
    pos = 0
    for f in fragments:
        k = block.find(f, pos)
        while k >= 0 and not _at_bounds(block, k, f):
            k = block.find(f, k + 1)
        if k < 0:
            return False
        pos = k + len(f)
    return True


def _quotes_on(line):
    """(start, end, text) of each quotation on a line, typographic forms winning overlaps."""
    taken = []
    for r in _QUOTE_RES:
        for m in r.finditer(line):
            if all(m.end() <= a or m.start() >= b for a, b, _ in taken):
                taken.append((m.start(), m.end(), m.group(1)))
    return sorted(taken)


# A line that starts a block of its own (a list item, heading, table row, blockquote, HTML comment or
# code fence) never continues the line above; one of the last five is never continued either.
_BLOCK_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|\||>|<!--|```|~~~)")
_ALONE_RE = re.compile(r"^\s*(?:#{1,6}\s|\||>|<!--|```|~~~)")
# The record's own way of naming an open-items row in words, `open item “<label>”`: a label, not a
# quotation of anyone.
_LABEL_RE = re.compile(r"\bopen items?\s*$", re.I)


def _paragraphs(lines):
    """Wrapped prose read as one line: (text, starts) per paragraph or list item, `starts` holding the
    (offset in `text`, line number) of each physical line joined into it with one space. A non-blank
    line continues the one above unless it starts a block or the line above is blank or stands alone."""
    out = []
    for n, line in enumerate(lines, 1):
        if (n > 1 and line.strip() and not _BLOCK_RE.match(line)
                and lines[n - 2].strip() and not _ALONE_RE.match(lines[n - 2])):
            text, starts = out[-1]
            text = text.rstrip() + " "
            starts.append((len(text), n))
            out[-1] = (text + line.strip(), starts)
        else:
            out.append((line, [(0, n)]))
    return out


def _line_index(starts, pos):
    """Which of a paragraph's physical lines (an index into its `starts`) holds offset `pos`."""
    return [k for k, (off, _) in enumerate(starts) if off <= pos][-1]


def _quoted(fragments, blocks):
    if any(_fragments_in(fragments, b) for b in blocks):
        return True
    last = fragments[-1].rstrip(_TRAIL_PUNCT)      # a full stop placed inside the quote marks
    return bool(last) and last != fragments[-1] and any(
        _fragments_in(fragments[:-1] + [last], b) for b in blocks)


def _owner(line, cites, at, end, span=None, quotes=()):
    """The citation a quotation at line[at:end] belongs to, by layout. `span` is the (start, end)
    of the physical lines the quotation touches in a joined paragraph (the whole line when not
    given); `quotes` are the paragraph's quotations. In order:
    - one that follows it with only spaces between (`"…" (operator, <file>, B)`), when it opens on
      the quotation's own lines;
    - one whose parentheses close just before it with at most a colon or dash between
      (`(operator, <file>, B): "…"`) — across a line break only with the colon or dash, and not
      when it already follows a quotation of its own while one follows this one across the break;
    - one that follows it with only spaces between, across a line break;
    - the next one, if it starts on the quotation's own lines or does not follow, with only spaces
      between, another quotation in between;
    - the last one on the quotation's own lines; else None.
    A citation's parentheses are the ones that hold it."""
    lo, hi = span or (0, len(line))

    def opens(c):
        k = line.rfind("(", 0, c.start())
        return k if k >= 0 and ")" not in line[k:c.start()] else c.start()

    def closes(c):
        k = line.find(")", c.end())
        return k + 1 if k >= 0 and "(" not in line[c.end():k] else c.end()

    after = [c for c in cites if opens(c) >= end]
    before = [c for c in cites if closes(c) <= at]
    beside = after[0] if after and not line[end:opens(after[0])].strip() else None
    if beside is not None and opens(beside) < hi:
        return beside
    def follows_a_quotation(c, start=0):
        return any(start <= e <= opens(c) and not line[e:opens(c)].strip() for _, e, _ in quotes)

    if before:
        gap = line[closes(before[-1]):at]
        if (re.match(r"^\s*[:—–-]?\s*$", gap) and (closes(before[-1]) > lo or gap.strip())
                and (beside is None or not follows_a_quotation(before[-1]))):
            return before[-1]
    if beside is not None:
        return beside
    if after and (after[0].start() < hi or not follows_a_quotation(after[0], end)):
        return after[0]
    near = [c for c in cites if lo <= c.start() < hi]
    return near[-1] if near else None


# A parenthesis right after a quotation that ends in an evidence mark other than B and names no
# interview file: `"…" (discharge letter 2026-09-01, A)`. On-screen answers are grade B, so the
# quotation is that other source's.
_SOURCE_RE = re.compile(r"\s*\(([^()]*)\)")
_SOURCE_MARK_RE = re.compile(r",\s*[ACD]\s*$")


def _other_source(line, end):
    m = _SOURCE_RE.match(line, end)
    return bool(m and _SOURCE_MARK_RE.search(m.group(1)) and not INTERVIEW_NAME_RE.search(m.group(1)))


def quotations(root, handle, files=("profile.md", "medications.md")):
    """Every quotation in the person's `files` that cites an interview file by its dated name, as
    (where, stem, text, verdict): `where` is `<file>:<line the quotation starts on>`, `stem` the cited
    file's dated name, and `verdict` "ok", "altered" (not word for word in any of its answers or
    notes), "missing" (no such file in med/sources/interviews/), "damaged" (it cannot be read back)
    or "sheet" (a sheet-era file, not checked). A quotation in a citing paragraph that no citation
    claims yields (where, None, text, "unread"); a citing paragraph with no quotation yields (where,
    None, None, "unquoted"). Wrapped prose is read as one line (`_paragraphs`); a quotation belongs
    to its citation by layout (`_owner`); one naming an open item (`open item “<label>”`) is a label,
    and one followed by another source's citation (`_other_source`) is that source's — neither is
    read. Comparison is after `_norm` on both sides, fragments matching only at word and number
    boundaries."""
    pdir = os.path.join(root, "patients", handle)
    if handle.startswith(".") or os.sep in handle or not os.path.isfile(os.path.join(pdir, "profile.md")):
        raise CaptureError("no patients/<handle>/profile.md for that handle: check the spelling")
    folder = os.path.join(pdir, "med", "sources", "interviews")
    cache = {}
    for name in files:
        p = os.path.join(pdir, name)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", newline="") as fh:
            lines = fh.read().split("\n")
        for line, starts in _paragraphs(lines):
            cites = list(INTERVIEW_NAME_RE.finditer(line))
            if not cites:
                continue
            quotes = [x for x in _quotes_on(line) if not _LABEL_RE.search(line[:x[0]])]
            if not [x for x in quotes if not _other_source(line, x[1])]:
                yield "%s:%d" % (name, starts[0][1]), None, None, "unquoted"
                continue
            for at, end, q in quotes:
                if _other_source(line, end):
                    continue                      # another source's quotation
                first, last = _line_index(starts, at), _line_index(starts, end - 1)
                lo = starts[first][0]
                hi = starts[last + 1][0] if last + 1 < len(starts) else len(line)
                where = "%s:%d" % (name, starts[first][1])
                cite = _owner(line, cites, at, end, (lo, hi), quotes)
                if cite is None:
                    yield where, None, q, "unread"
                    continue
                stem = cite.group(1)
                if stem not in cache:
                    fp = os.path.join(folder, stem + ".md")
                    if not os.path.isfile(fp):
                        cache[stem] = None
                    else:
                        try:
                            with open(fp, encoding="utf-8", newline="") as fh:
                                fm, items = parse_file(fh.read())
                            cache[stem] = ([_norm(b) for it in items for b in it[2] + [it[3] or ""]
                                            if b] if fm.get("capture") else "sheet")
                        except (UnicodeDecodeError, CaptureError):
                            cache[stem] = "damaged"
                blocks = cache[stem]
                frags = [f for f in (_norm(x) for x in _ELLIPSIS_RE.split(q)) if f]
                if not any(ch.isalnum() for f in frags for ch in f):
                    continue                      # an ellipsis or a stop alone is not a quotation
                if blocks in ("sheet", "damaged"):
                    yield where, stem, q, blocks
                elif blocks is None:
                    yield where, stem, q, "missing"
                else:
                    yield where, stem, q, "ok" if _quoted(frags, blocks) else "altered"


def check_quotes(root, handle, files=("profile.md", "medications.md")):
    """(failures, checked, skipped, unquoted) over `quotations`: a failure names the line the
    quotation starts on; `unquoted` counts what was not read — citing paragraphs with no quotation
    (a paraphrase, or a quote form this check does not read) and quotations no citation claims."""
    failures, checked, skipped, unquoted = [], 0, 0, 0
    for where, stem, _, verdict in quotations(root, handle, files):
        if verdict in ("unquoted", "unread"):
            unquoted += 1
        elif verdict == "sheet":
            skipped += 1
        else:
            checked += 1
            if verdict == "missing":
                failures.append("%s cites %s, which is not in med/sources/interviews/" % (where, stem))
            elif verdict == "damaged":
                failures.append("%s cites %s, which cannot be read back: ask the operator"
                                % (where, stem))
            elif verdict == "altered":
                failures.append("%s: a quotation citing %s is not word for word in any of its "
                                "answers — copy it from the file, or, if it quotes no answer, take "
                                "the quote marks off" % (where, stem))
    return failures, checked, skipped, unquoted
