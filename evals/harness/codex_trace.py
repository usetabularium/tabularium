"""Offline normalization of Codex ``exec --json`` events, with explicit evidence gaps.

This is an event adapter, not a filesystem audit. In particular, a shell command is
not proof that a named file reached the model, and automatic instruction reads are
not enumerated by this stream. Never feed ``tool_calls`` to the grader on its own:
``grade_trace`` preserves the existing tree/message checks and marks assertions
that this host cannot establish UNVERIFIABLE. No case or assertion is changed.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path


READ_GAP = ("Codex exec JSONL is not a complete read audit; shell and automatic "
            "instruction reads cannot prove inspection or absence of reads")
ORDER_GAP = "Codex exec JSONL does not establish file-read/write order inside tool executions"
_ITEM_EVENTS = {"item.started", "item.updated", "item.completed"}
_PASSIVE_ITEMS = {"reasoning", "todo_list"}
_LIFECYCLE = {"thread.started", "turn.started", "turn.completed"}
_TOOLS = {"command_execution", "file_change", "mcp_tool_call", "web_search"}


@dataclass
class ParsedTrace:
    tool_calls: dict = field(default_factory=lambda: {"reads": [], "writes": [], "sequence": []})
    first_message: str = None
    final_message: str = None
    issues: list = field(default_factory=list)
    messages_complete: bool = False

    def unverifiable_assertions(self, manifest):
        """Assertion ids whose outcome cannot be established by this event stream."""
        result = {}
        if manifest.get("transcript_required_reads"):
            result["READ_REQUIRED"] = READ_GAP
        if manifest.get("transcript_forbidden_reads"):
            result["READ_SCOPE"] = READ_GAP
        for rule in manifest.get("read_before_write") or []:
            result[rule.get("id", "ORDER")] = ORDER_GAP
        if not self.messages_complete:
            for key in ("final_message_required", "final_message_forbidden"):
                for rule in manifest.get(key) or []:
                    result[rule.get("id", "M?")] = "complete first/final assistant messages are unavailable"
        return result


def _path(raw, root):
    """Normalize textually; preserve escapes as absolute paths, without opening files."""
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        return None
    candidate = raw if os.path.isabs(raw) else os.path.join(root, raw)
    candidate = os.path.normpath(candidate)
    try:
        return Path(candidate).relative_to(root).as_posix()
    except ValueError:
        return Path(candidate).as_posix()


def parse_jsonl(text, fixture_root):
    """Parse a captured string, never executing tools or inspecting referenced paths.

    Items are ordered by first appearance (invocation), not completion. Repeated
    lifecycle snapshots do not duplicate accesses. Every shell execution conservatively
    has potential whole-tree reads and writes, even when its exit status is nonzero:
    a failed compound command may already have accessed files. ``file_change`` paths
    identify write attempts, while update/delete may also read the previous contents.
    These potential accesses are deliberately insufficient to pass read assertions.
    """
    result = ParsedTrace()
    root = os.path.abspath(os.fspath(fixture_root))
    items, active, messages = {}, set(), []
    completed_messages = []
    message_active = set()
    seen_thread = seen_turn = False
    complete = False
    opaque = False

    def issue(message, *, opaque_message=False):
        nonlocal opaque
        if message not in result.issues:
            result.issues.append(message)
        opaque = opaque or opaque_message

    if not isinstance(text, str):
        raise TypeError("parse_jsonl needs captured JSONL text")
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            issue("line %d: invalid JSON event" % number, opaque_message=True)
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            issue("line %d: invalid event shape" % number, opaque_message=True)
            continue
        event_type = event["type"]
        if event_type in _LIFECYCLE:
            if event_type == "turn.completed":
                if complete:
                    issue("multiple completed turns", opaque_message=True)
                if event.get("status", "completed") != "completed":
                    issue("completed turn has an unknown terminal status", opaque_message=True)
                complete = True
            elif event_type == "thread.started":
                if complete or seen_thread or seen_turn or items:
                    issue("thread starts after earlier stream activity", opaque_message=True)
                seen_thread = True
            else:
                if complete or seen_turn or items:
                    issue("turn starts after earlier stream activity", opaque_message=True)
                seen_turn = True
            continue
        if event_type in {"error", "turn.failed"}:
            issue("stream reports an error or failed turn", opaque_message=True)
            continue
        if event_type not in _ITEM_EVENTS:
            issue("line %d: unknown event type" % number, opaque_message=True)
            continue
        if complete:
            issue("item event after completed turn", opaque_message=True)
        item = event.get("item")
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            issue("line %d: invalid item shape" % number, opaque_message=True)
            continue
        identity = item.get("id")
        if not isinstance(identity, str) or not identity:
            issue("line %d: item without identity" % number, opaque_message=True)
            continue
        kind = item["type"]
        if identity in items:
            previous = items[identity]
            if previous["item"]["type"] != kind:
                issue("item changes type", opaque_message=True)
            if previous["completed"]:
                if event_type != "item.completed" or previous["item"] != item:
                    issue("conflicting event after completed item", opaque_message=True)
                continue
        else:
            items[identity] = {"item": item, "completed": False}
            if event_type == "item.updated":
                issue("item update without start", opaque_message=True)
        record = items[identity]
        record["item"] = item
        if kind in _TOOLS and event_type == "item.started":
            if active - {identity}:
                issue("overlapping tool executions: internal access order is unavailable")
            active.add(identity)
        if kind == "agent_message" and event_type == "item.started":
            if message_active - {identity}:
                issue("overlapping assistant messages", opaque_message=True)
            message_active.add(identity)
        if event_type == "item.completed":
            record["completed"] = True
            active.discard(identity)
            if kind == "agent_message":
                message_active.discard(identity)
                body = item.get("text")
                if not isinstance(body, str) or not body.strip():
                    issue("assistant message has no text", opaque_message=True)
                else:
                    completed_messages.append(identity)

    def access(kind, path):
        key = "reads" if kind == "read" else "writes"
        if path not in result.tool_calls[key]:
            result.tool_calls[key].append(path)
        result.tool_calls["sequence"].append([kind, path])

    for record in items.values():
        item, finished = record["item"], record["completed"]
        kind = item["type"]
        if not finished:
            issue("incomplete item at end of stream", opaque_message=True)
        if kind == "command_execution":
            # Parsing shell syntax as though it were a file-tool call would give false
            # confidence for pipelines, aliases, scripts, redirections and failed commands.
            access("read", "**")
            access("write", "**")
            issue("shell execution has only conservative whole-tree access scopes")
            if not isinstance(item.get("command"), str):
                issue("command execution has no command", opaque_message=True)
            if finished and (not isinstance(item.get("exit_code"), int)
                             or isinstance(item.get("exit_code"), bool)):
                issue("completed command has no exit status", opaque_message=True)
        elif kind == "file_change":
            changes = item.get("changes")
            if not isinstance(changes, list) or not changes:
                issue("file change has no path inventory", opaque_message=True)
                access("read", "**")
                access("write", "**")
                continue
            for change in changes:
                path = _path(change.get("path"), root) if isinstance(change, dict) else None
                operation = change.get("kind") if isinstance(change, dict) else None
                if path is None or not isinstance(operation, str) \
                        or operation not in {"add", "update", "delete"}:
                    issue("file change contains an unknown path or operation", opaque_message=True)
                    access("read", "**")
                    access("write", "**")
                    continue
                if operation != "add":
                    access("read", path)
                access("write", path)
            if item.get("status") != "completed":
                issue("file change success is not established")
        elif kind in {"mcp_tool_call", "web_search"}:
            access("read", "**")
            access("write", "**")
            issue("unsupported tool execution has unknown access scopes", opaque_message=True)
        elif kind not in _PASSIVE_ITEMS and kind != "agent_message":
            access("read", "**")
            access("write", "**")
            issue("unknown item type has unknown access scopes", opaque_message=True)

    # Message identity follows first appearance just like tool invocation identity.
    # Out-of-order completions cannot establish which message actually opened the reply.
    message_ids = [identity for identity, record in items.items()
                   if record["item"]["type"] == "agent_message" and record["completed"]
                   and isinstance(record["item"].get("text"), str) and record["item"]["text"].strip()]
    if message_ids != completed_messages:
        issue("assistant messages complete out of invocation order", opaque_message=True)
    messages = [items[identity]["item"]["text"] for identity in message_ids]

    if not complete:
        issue("stream has no completed turn", opaque_message=True)
    if messages:
        result.first_message, result.final_message = messages[0], messages[-1]
    else:
        issue("stream contains no assistant message", opaque_message=True)
    result.messages_complete = complete and not opaque and bool(messages)
    return result


def grade_trace(manifest, parsed, **kwargs):
    """Grade established surfaces, retaining per-assertion UNVERIFIABLE outcomes.

    Existing grader assertions are unchanged. Their speculative transcript outcomes
    are removed from failures and recorded separately; known tree/message failures
    still outrank uncertainty. A clean result with any uncertainty never passes.
    """
    from evals.harness import grader

    graded = grader.grade(manifest, tool_calls=parsed.tool_calls,
                          first_message=parsed.first_message,
                          final_message=parsed.final_message or "", **kwargs).as_dict()
    unknown = parsed.unverifiable_assertions(manifest)
    graded["failed"] = [aid for aid in graded["failed"] if aid not in unknown]
    graded["detail"] = {aid: message for aid, message in graded["detail"].items() if aid not in unknown}
    graded["unverifiable"] = unknown
    graded["trace_issues"] = list(parsed.issues)
    severity = {}
    defaults = {"required_effects": "R?", "forbidden_effects": "F?", "file_checks": "C?",
                "date_assertions": "D?", "write_scope_forbidden": "W?", "read_before_write": "ORDER",
                "final_message_required": "M?", "final_message_forbidden": "M?"}
    for key, default in defaults.items():
        for assertion in manifest.get(key) or []:
            aid = assertion.get("id", default)
            sev = assertion.get("severity") or manifest.get("cls", "care")
            # Several declarations may intentionally share a category id. Keep the
            # strongest declared severity, including the grader's default message id.
            if severity.get(aid) != "safety":
                severity[aid] = sev
            if key in {"required_effects", "forbidden_effects"} and severity.get("?") != "safety":
                severity["?"] = sev  # missing-file/section failures use _scope_for's default id
    grades = {severity.get(aid, manifest.get("cls", "care")) for aid in graded["failed"]}
    graded["worst_severity"] = "safety" if "safety" in grades else ("care" if grades else None)
    graded["verdict"] = "fail" if graded["failed"] else ("unverifiable" if unknown else "pass")
    return graded
