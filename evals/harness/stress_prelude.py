"""stress_prelude.py — the stress test's mid-interview rows: earlier turns played before the critical one.

WHY. A single-turn opener cannot show what a session does when a warning sign first appears in an answer
to its own questions, several turns into routine work: by then the session is busy with the record, the
contract sits turns back, and the answer is not framed as a worry. A mid-interview row carries a scripted
conversation (`preludes` in the held-back data, the same bytes for every arm) and its `opener` is the
critical turn: the operator's answer that holds the warning sign.

HOW — the smallest honest way found. The scripted turns are PLAYED through the real CLI, in the trial's
own tree and with the session's own flags, against a local stand-in for the model (`StandIn`) that only
replays the scripted assistant turns; a scripted read is run for real by the CLI's Read tool. The CLI
writes its own conversation record, which the critical turn then resumes (`--resume`, read-only under
`--no-session-persistence`). Only the critical turn reaches the model; the stand-in never does.

PROBE RECORD, 2026-10-19, macOS, `claude` 2.1.289, the stand-in on 127.0.0.1 (no API call):
  * A hand-written record resumes, but the CLI then attaches CLAUDE.md to the RESUMED turn, beside the
    warning sign — where a live session never has it. Played turns put it at turn 1, as live. Hence play.
  * `--resume` with `--no-session-persistence` sends the record's turns, in order, before the new one,
    and leaves the record unchanged; a record copied into another config dir resumes the same way.
  * The resumed turn's stream-json carries that turn's events only (no history replayed), and its init
    names the resumed session id — the receipt `run_trial` checks.
  * A scripted Read runs for real: its tool result is the tree's file, in the CLI's own format.
Every trial re-checks the shape (`check_request`) by rehearsing the critical turn against the stand-in
first: the history in order, the contract at turn 1 and not at the critical turn, the critical text
last. A CLI that changes any of it voids the trial before anything is spent.

WHAT IT CANNOT SHOW. The earlier turns are scripted, not the arm's own: Tabularium might have asked in
another order or with the structured-question tool, plain Claude might not have asked at all. Every arm
gets the same prefix, so the arms differ in the contract only; the measurement is the reply to the
critical turn given that prefix. A live structured answer arrives as a tool result; here it is typed.

Stdlib only. No side effects at import.
"""

import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import threading
import uuid
from pathlib import Path

from evals.harness import grader, session

#: What every played or rehearsed CLI is told about the API: a local address and a key that is not one.
STAND_IN_KEY = "stand-in-not-a-key"
#: Marks a contract arm's CLAUDE.md in a request: every contract arm's text carries this heading.
CONTRACT_MARK = "## An emergency comes first"
#: The stand-in's reply to the rehearsed critical turn (never graded, never seen by the model).
REHEARSAL_REPLY = "(stand-in rehearsal reply)"
_PERSON_PATH = re.compile(r"patients/[a-z0-9-]+/(?:[A-Za-z0-9_. -]+/)*[A-Za-z0-9_. -]+")


class PreludeError(Exception):
    """The history could not be played, or a rehearsal showed the CLI would not send it as played."""


# --------------------------------------------------------------------------- the data

def turns_of(data, s):
    """The row's scripted history: [{"user": text} | {"assistant": text, "reads": [path]}], alternating,
    user first, assistant last. [] for a single-turn row."""
    name = s.get("prelude")
    if not name:
        return []
    return list(((data or {}).get("preludes") or {}).get(name) or [])


def validate(data, s, target_pattern):
    """Why a row's history cannot be used, or []. `target_pattern` is the emergency-number pattern: the
    history must not name it, or the earlier turns would prime the call the critical turn measures."""
    name, out = s.get("prelude"), []
    if not name:
        return out
    turns = ((data or {}).get("preludes") or {}).get(name)
    if not turns:
        return ["%s: prelude %r is not in the data's preludes" % (s.get("id"), name)]
    for i, t in enumerate(turns):
        role = "user" if i % 2 == 0 else "assistant"
        if set(t) - {"user", "assistant", "reads"} or not str(t.get(role) or "").strip() or (
                role == "user" and "reads" in t):
            out.append("prelude %s turn %d: expected a %s turn" % (name, i + 1, role))
            continue
        for p in t.get("reads") or []:
            if not _PERSON_PATH.fullmatch(str(p)) or ".." in str(p):
                out.append("prelude %s turn %d: read %r is not a file under a person's folder" % (name, i + 1, p))
        if re.search(target_pattern, t[role], re.I):
            out.append("prelude %s turn %d names the emergency number" % (name, i + 1))
    if len(turns) % 2:
        out.append("prelude %s must end on an assistant turn (the critical turn is the row's opener)" % name)
    if len(turns) < 4:
        out.append("prelude %s: at least two assistant turns before the critical one" % name)
    return out


def scripted_text(turns):
    """Every scripted word, for the pre-transit scan (it reaches the API inside the critical turn)."""
    return "\n\n".join(t.get("user") or t.get("assistant") or "" for t in turns)


# --------------------------------------------------------------------------- the stand-in

def _sse(msg_id, model, blocks):
    """One assistant message as the API's event stream."""
    msg = {"id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [],
           "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}
    ev, stop = [("message_start", {"type": "message_start", "message": msg})], "end_turn"
    for i, b in enumerate(blocks):
        if b["type"] == "text":
            ev += [("content_block_start", {"type": "content_block_start", "index": i,
                                            "content_block": {"type": "text", "text": ""}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i,
                                            "delta": {"type": "text_delta", "text": b["text"]}})]
        else:
            stop = "tool_use"
            ev += [("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                       "type": "tool_use", "id": b["id"], "name": b["name"], "input": {}}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {
                       "type": "input_json_delta", "partial_json": json.dumps(b["input"])}})]
        ev.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    ev += [("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                              "usage": {"output_tokens": 0}}),
           ("message_stop", {"type": "message_stop"})]
    return "".join("event: %s\ndata: %s\n\n" % (k, json.dumps(v)) for k, v in ev).encode("utf-8")


class StandIn:
    """A local stand-in for the model on 127.0.0.1: each request to /v1/messages gets the next scripted
    assistant message; every request body is kept. It answers nothing it was not scripted to (an empty
    queue is a 500, which fails the CLI and so the play)."""

    def __init__(self):
        self.queue, self.requests, self._n = [], [], 0
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send(200, b"{}", "application/json")

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("content-length") or 0))
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    body = {}
                if "count_tokens" in self.path:
                    return self._send(200, b'{"input_tokens": 0}', "application/json")
                outer.requests.append(body)
                if not outer.queue:
                    return self._send(500, b'{"type":"error","error":{"type":"api_error","message":"stand-in: '
                                           b'no scripted turn left"}}', "application/json")
                outer._n += 1
                self._send(200, _sse("msg_standin_%d" % outer._n, str(body.get("model") or "stand-in"),
                                     outer.queue.pop(0)), "text/event-stream")

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        self._server = Server(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self._server.server_address[1]

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    def script_turn(self, turn, fixture_dir):
        """Queue one scripted assistant turn: its reads as one tool-use message, then its text."""
        reads = turn.get("reads") or []
        if reads:
            self.queue.append([{"type": "tool_use", "id": "toolu_standin_%s" % uuid.uuid4().hex[:12], "name": "Read",
                                "input": {"file_path": str(Path(fixture_dir) / r)}} for r in reads])
        self.queue.append([{"type": "text", "text": turn["assistant"]}])
        return 1 + bool(reads)


# --------------------------------------------------------------------------- the CLI

def stand_in_env(config_dir, url):
    """The session's environment (`session._session_env`) with every credential removed and the API
    pointed at the stand-in: nothing played can reach the real API, and no token reaches the stand-in."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "CLAUDE", "ANTHROPIC")) and k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY",
                                                                                   "ALL_PROXY")}
    env.update(CLAUDE_CONFIG_DIR=str(Path(config_dir).resolve()), ANTHROPIC_BASE_URL=url,
               ANTHROPIC_API_KEY=STAND_IN_KEY, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
               NO_PROXY="127.0.0.1,localhost", TZ="UTC")
    return env


def cli_argv(addendum, extra, prompt):
    """`session.run_session`'s flags, so the played turns run as the session will: the same settings, tool
    allowlist and eval-mode note. Persistence is left on (the record is the point); the system prompt is
    rendered fresh at every request, as at a single-turn row's first one."""
    argv = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--settings", str(session.SETTINGS_PATH),
            "--tools", ",".join(session.EVAL_TOOLS), "--strict-mcp-config", "--system-prompt-snapshot", "off"]
    if addendum:
        argv += ["--append-system-prompt-file", str(session.ADDENDUM_PATH)]
    return argv + list(extra) + [prompt]


def resume_args(session_id):
    """What the critical turn adds to `run_session`'s flags (it already passes --no-session-persistence)."""
    return ["--resume", session_id, "--system-prompt-snapshot", "off"]


def _run_cli(argv, fixture_dir, env, timeout_s, what):
    try:
        proc = subprocess.run(argv, cwd=str(fixture_dir), env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=timeout_s)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise PreludeError("%s: %s" % (what, exc))
    events = session._parse_events(proc.stdout or "")
    result = session._find_result(events)
    if proc.returncode != 0 or result is None or result.get("is_error"):
        raise PreludeError("%s: rc %s, %s" % (what, proc.returncode, " ".join(
            str((result or {}).get("result") or proc.stderr or "no result event").split())[:200]))
    return events


# --------------------------------------------------------------------------- checks

def _flat(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            out.append(str(b.get("text") or ""))
        elif b.get("type") == "tool_result":
            out.append(_flat(b.get("content")))
        elif b.get("type") == "tool_use":
            out.append(json.dumps(b.get("input") or {}))
    return "\n".join(out)


def check_request(req, turns, critical, contract, fixture_dir):
    """[] when the rehearsed critical turn's request carries the history as played; else what is wrong.
    `contract`: True for an arm whose tree carries CLAUDE.md (the plain arm's does not)."""
    msgs = [m for m in (req or {}).get("messages") or [] if m.get("role") in ("user", "assistant")]
    users = [_flat(m.get("content")) for m in msgs if m["role"] == "user"]
    out, pos = [], 0
    if not users:
        return ["the rehearsal sent no user message"]
    for t in turns:
        role, text = ("user", t["user"]) if "user" in t else ("assistant", t["assistant"])
        hit = next((i for i in range(pos, len(msgs)) if msgs[i]["role"] == role and text in _flat(msgs[i]["content"])),
                   None)
        if hit is None:
            out.append("a scripted %s turn is missing or out of order: %r" % (role, text[:60]))
        else:
            pos = hit + 1
    if critical not in users[-1]:
        out.append("the critical turn is not the last user message")
    if any(t["user"] in users[-1] for t in turns if "user" in t):
        out.append("a scripted turn shares the critical turn's message")
    marks = [i for i, u in enumerate(users) if CONTRACT_MARK in u]
    if contract and marks != [0]:
        out.append("the contract is not attached at turn 1 only (user messages carrying it: %s)" % marks)
    if not contract and marks:
        out.append("a tree without a contract sent one")
    used = {}
    for m in msgs:
        for b in m.get("content") if isinstance(m.get("content"), list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Read":
                used[b.get("id")] = str((b.get("input") or {}).get("file_path") or "")
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in used:
                if b.get("is_error") or not _flat(b.get("content")).strip():
                    out.append("a scripted read failed: %s" % used[b["tool_use_id"]])
    for r in [r for t in turns for r in t.get("reads") or []]:
        if str(Path(fixture_dir) / r) not in used.values():
            out.append("a scripted read is not in the history: %s" % r)
    return out


def _tree(root):
    return grader._collect(str(root))


# --------------------------------------------------------------------------- the whole step

def prepare(work_dir, fixture_dir, turns, critical, addendum, contract, config_dir=None, timeout_s=120):
    """Play `turns` in `fixture_dir`, rehearse `critical` against the stand-in, and (with `config_dir`)
    install the record there for the real critical turn. -> the row's `prelude` record. Raises
    PreludeError on anything short of a history the CLI recorded and will send as played; the tree must be
    byte-identical afterwards (a played turn may read, never write)."""
    if addendum and session._addendum_route() != "append-system-prompt-file":
        raise PreludeError("the eval-mode note reaches a resumed session only by the system-prompt file, "
                           "which this CLI lacks")
    work_dir, fixture_dir = Path(work_dir), Path(fixture_dir).resolve()
    play_cfg = work_dir / "config"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    os.makedirs(play_cfg)
    os.chmod(play_cfg, 0o700)
    before, sid = _tree(fixture_dir), str(uuid.uuid4())
    with StandIn() as stand:
        env = stand_in_env(play_cfg, stand.url)
        for k in range(0, len(turns), 2):
            expected = len(stand.requests) + stand.script_turn(turns[k + 1], fixture_dir)
            extra = ["--session-id", sid] if k == 0 else ["--resume", sid]
            _run_cli(cli_argv(addendum, extra, turns[k]["user"]), fixture_dir, env, timeout_s,
                     "played turn %d" % (k // 2 + 1))
            if stand.queue or len(stand.requests) != expected:
                raise PreludeError("played turn %d: the CLI made %d request(s) to the stand-in, %d scripted"
                                   % (k // 2 + 1, len(stand.requests), expected))
        records = sorted(play_cfg.glob("projects/*/%s.jsonl" % sid))
        if len(records) != 1:
            raise PreludeError("the CLI recorded the played conversation %d time(s), not once" % len(records))
        recorded = records[0].read_bytes()
        stand.queue.append([{"type": "text", "text": REHEARSAL_REPLY}])
        events = _run_cli(cli_argv(addendum, ["--resume", sid, "--no-session-persistence"], critical), fixture_dir,
                          env, timeout_s, "rehearsed critical turn")
        problems = check_request(stand.requests[-1] if stand.requests else None, turns, critical, contract,
                                 fixture_dir)
        init = session._find_init(events) or {}
        if init.get("session_id") != sid:
            problems.append("the rehearsed turn did not resume the played session")
    if records[0].read_bytes() != recorded:
        problems.append("the rehearsal changed the recorded conversation")
    if _tree(fixture_dir) != before:
        problems.append("playing the history changed the trial's tree")
    if problems:
        raise PreludeError("; ".join(problems))
    installed = None
    if config_dir is not None:
        installed = Path(config_dir) / records[0].relative_to(play_cfg)
        os.makedirs(installed.parent, exist_ok=True)
        shutil.copy2(records[0], installed)
    return {"session_id": sid, "turns": len(turns), "record": str(records[0]),
            "installed": str(installed) if installed else None,
            "rehearsal": "history in order, contract %s, critical turn last" % (
                "at turn 1 only" if contract else "absent (no contract in this tree)")}
