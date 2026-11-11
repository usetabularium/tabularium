"""The EV-09 probe corpus as grader controls (handover 49; ADR-0049 element 12).

`ev09_probe_corpus.json` keeps the replies three review rounds wrote against EV-09's oracles, each
with the verdict the RULE gives it. This loader turns every ACTIVE entry into a message-only control
in the shape `controls.py` runs: EV-09a replies on the untouched tree (record work waits), EV-09b
replies on the tree with the requested Drug W row (`oracles_b._CORRECT_EV09B`), so only the
final-message assertions can move. No session, no model: `run_eval --controls-only` runs them.

EXCLUDED entries are parked probes whose right verdict the oracles cannot give today (or whose verdict
is a judgement call); each names its category and the decision it awaited. They are not certified
controls: `stress_controls.py` runs every one against the rule's verdict. Ruled 2026-11-01 (operator):
each stays an accepted, recorded gap, the oracles neither tightened nor loosened for it.

Fail closed: an entry with an unknown status, variant or verdict, an empty reply, a failing entry
that names no assertion or severity, or a parked entry with no category or pending decision is a
load error, never a skipped control — and so is a corpus with no active entry.
"""

import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / "ev09_probe_corpus.json"
_VARIANTS = ("EV-09a", "EV-09b")


def _problem(e, seen):
    """Why an entry cannot load, or None."""
    if e.get("id") in seen:
        return "duplicate id"
    if e.get("status") not in ("active", "excluded"):
        return "status must be active or excluded"
    if e.get("variant") not in _VARIANTS:
        return "unknown variant %r" % e.get("variant")
    if not str(e.get("text") or "").strip():
        return "empty reply"
    if e["status"] == "excluded":
        if not e.get("category") or not e.get("awaits"):
            return "a parked entry names no category or pending decision"
        return None
    if e.get("expect") not in ("pass", "fail"):
        return "expect must be pass or fail"
    if e["expect"] == "fail" and not e.get("expect_ids"):
        return "a failing entry names no assertion"
    if e["expect"] == "fail" and e.get("expect_severity") not in ("safety", "care"):
        return "a failing entry names no severity"
    return None


def load(path=CORPUS):
    """(active entries, excluded entries), validated."""
    path = Path(path)
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries") or []
    seen = set()
    for e in entries:
        problem = _problem(e, seen)
        if problem:
            raise ValueError("%s: entry %s: %s" % (path.name, e.get("id"), problem))
        seen.add(e.get("id"))
    active = [e for e in entries if e["status"] == "active"]
    if not active:
        raise ValueError("%s holds no active entries — refusing to report a green over nothing"
                         % path.name)
    return active, [e for e in entries if e["status"] == "excluded"]


def controls(path=CORPUS):
    """Every ACTIVE corpus entry as a control dict (placeholders left for the runner to expand)."""
    from evals.harness import oracles_b

    out = []
    for e in load(path)[0]:
        control = {
            "id": "EV-09.%s" % e["id"], "variant": e["variant"], "expect": e["expect"],
            "expect_ids": list(e.get("expect_ids") or []),
            "mutations": [] if e["variant"] == "EV-09a" else list(oracles_b._CORRECT_EV09B),
            "trace": None, "final_message": e["text"],
            "desc": "probe corpus — %s (%s)" % (e.get("kind", "?"), e.get("round", "?")),
        }
        if e["expect"] == "fail":
            control["expect_severity"] = e["expect_severity"]
        out.append(control)
    return out
