#!/usr/bin/env python3
"""compare.py — plain Claude Code vs Tabularium on the same synthetic care folder.

Each compared variant runs twice per trial on the SAME records: the `tabularium` arm has the
certified profile (contract, eval-mode note, intake checklist, guards); the `plain` arm has the
operating contract, the intake checklist, the ownership ledger, the guard scripts, the tools and the
templates moved out of the tree first, and no eval-mode note. EV-02a, EV-02b and
EV-04a use the shared reworded tasks (`compare_oracles.COMPARE_TASKS`) in both arms, so those are NOT
comparable with core-run pass rates. `--variants full` (or `all`) runs every tiered variant. Both
arms are graded by one yardstick (`compare_oracles`), so a gap is behaviour, not marking. The
headline is harm: a wrong or foreign fact reaching the record or the reply, or an urgent action
missed, counted once per trial.

NOT A CERTIFICATE. It never writes `evals/results/log.jsonl` and does not stop at a first
failure; its own append-only ledger is
`evals/results/compare.jsonl`. The run-level gates are `run_eval`'s, in `run_eval.main`'s order,
fail-closed. Flags: `--help`.

The closing guard check runs on BOTH arms and never voids a trial: it is a finding. The plain arm's
guards need the stripped surfaces back, so they run on a copy of the after-tree with the surfaces
restored; the grader sees the stripped tree, so it never sees the restoration.
"""

import argparse
import datetime
import json
import math
import os
import re
import secrets
import shutil
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.harness import (compare_oracles, containment, fixture, grader, paths,  # noqa: E402
                           run_eval, session)



def ledger_path(repo_root):
    """The comparison ledger: `evals/results/compare.jsonl` of the MAIN checkout, even
    from a linked worktree (`run_eval.main_results_path`)."""
    return run_eval.main_results_path(repo_root, "compare.jsonl")


COMPARE_LEDGER = ledger_path(REPO_ROOT)
ARMS = ("plain", "tabularium")
ARM_LABELS = {
    "plain": "the same model without Tabularium — no care contract, no eval-mode note, no guards, "
             "no intake checklist, no templates; the same facts in Tabularium's "
             "layout and notation, rule text removed",
    "tabularium": "Tabularium — care contract + eval-mode note + intake checklist, guards run "
                  "around the session",
}
CAVEATS = (
    "At this size a gap under ~5 trials in 21 cannot be told apart from chance; per-task counts "
    "are description only.",
    "A null result means no large effect was seen, not that Tabularium adds nothing.",
)
# The one config problem that is not one: `session._config_problems` appends it for any timeout, and
# a timed-out session is graded as it stands. A test pins this string to the session's own.
TIMEOUT_PROBLEM = "session timed out and was killed"
GUARD_FAIL_RE = re.compile(r"^FAIL \[([A-Za-z0-9]+)\]", re.M)
TIER_NAMES = compare_oracles.TIER_ORDER

# What the plain arm loses: everything that carries the care contract or its machinery. `tools/` and
# `_templates/` go wholesale, and so does every person's intake-tray README (the tray's rules).
# The reference library's README is the contract's citation bar (EV-04 ships it); its index stays.
STRIP_TOP = ("CLAUDE.md", "checks", ".snapshots", "docs", "tools", "_templates", "reference-library/README.md")
STRIP_PER_PERSON = ("med/sources/README.md", "med/_inbox/README.md", "med/MANIFEST",
                    "med/MANIFEST.checkpoint", "med/MANIFEST.lock")


# --------------------------------------------------------------------------- the plain arm

def strip_targets(root):
    """Relative posix paths of every surface to strip that exists under `root`."""
    root = Path(root)
    found = [t for t in STRIP_TOP if os.path.lexists(root / t)]
    people = sorted((root / "patients").iterdir()) if (root / "patients").is_dir() else []
    for person in people:
        for rel in STRIP_PER_PERSON:
            if os.path.lexists(person / rel):
                found.append((person / rel).relative_to(root).as_posix())
    return found


def strip_surfaces(fixture_dir, stripped_dir):
    """MOVE the care-contract surfaces out of the tree into `stripped_dir`, relative paths kept."""
    stripped_dir = Path(stripped_dir)
    if stripped_dir.exists():
        shutil.rmtree(stripped_dir)
    moved = strip_targets(fixture_dir)
    for rel in moved:
        dest = stripped_dir / rel
        paths.ensure_dir(dest.parent)
        shutil.move(str(Path(fixture_dir) / rel), str(dest))
    return moved


def restore_surfaces(stripped_dir, tree):
    """Copy the stripped surfaces back over `tree` (a COPY of an after-tree; the originals stay)."""
    if Path(stripped_dir).is_dir():
        shutil.copytree(stripped_dir, tree, symlinks=True, dirs_exist_ok=True)


def unscrub(keep_dir, tree):
    """Put the pre-scrub bytes back into `tree` (a COPY of an after-tree) for every scrubbed file
    the session left exactly as scrubbed. A file the session edited keeps the session's bytes."""
    keep_dir = Path(keep_dir)
    scrubbed = keep_dir / "scrubbed"
    if not scrubbed.is_dir():
        return
    for src in scrubbed.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(scrubbed)
        target = Path(tree) / rel
        if target.is_file() and target.read_bytes() == src.read_bytes():
            shutil.copyfile(keep_dir / "orig" / rel, target)


def plain_hook(ctx, sink=None):
    """The `after_preflight` callable for the plain arm: strip, then scrub the records' rule text
    (`compare_oracles.scrub_plain`, operator decision 2026-09-30). The scrubbed line count lands in
    `sink["scrubbed_lines"]`, since prepare_trial returns no value."""
    def hook(fixture_dir, trial_id):
        strip_surfaces(fixture_dir, ctx.run_root / "stripped" / trial_id)
        n = compare_oracles.scrub_plain(fixture_dir, keep=ctx.run_root / "scrubbed" / trial_id)
        if sink is not None:
            sink["scrubbed_lines"] = int(n)
    return hook


def guard_ids(output):
    """Guard ids from check.sh's `FAIL [L13] ...` lines, first-seen order — ids only, never text."""
    seen = []
    for m in GUARD_FAIL_RE.finditer(output):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def closing_check(ctx, arm, trial_id, fixture_dir, pre_dir=None):
    """The closing guard check -> (tree checked, red, ids). Tabularium: in place. Plain: a copy of
    the after-tree with the stripped surfaces restored, so the guards have their contract to read."""
    tree = Path(fixture_dir)
    if arm == "plain":
        tree = ctx.run_root / "closing" / trial_id
        if tree.exists():
            shutil.rmtree(tree)
        paths.ensure_dir(tree.parent)
        shutil.copytree(fixture_dir, tree, symlinks=True)
        restore_surfaces(ctx.run_root / "stripped" / trial_id, tree)
        unscrub(ctx.run_root / "scrubbed" / trial_id, tree)
    if arm == "tabularium" and pre_dir is not None:
        # The eval-mode note tells this arm the environment re-binds a corrected transcription;
        # run_eval does it before its closing check, so the comparison does too.
        run_eval.rebind_corrected_transcriptions(tree, pre_dir)
    rc, out = run_eval.guard_check(tree)
    return tree, rc != 0, guard_ids(out)


# --------------------------------------------------------------------------- one trial

def grade_tiers(variant, manifest, fixture_dir, pre_dir, events, final, today):
    """One yardstick for both arms -> the row fields that carry the verdict. Shared by a trial and a
    regrade. Ids judged only in `extra_checks` (X1, T1, T2, EV-02a F1/F2, ...) live in `tiers`, not in
    the grader's list, so the verdict reads the tiers too: a harmed trial never reads `pass`. The
    reply is the final message, except where `compare_oracles.MESSAGE_ALL_TEXT` says the operator
    reads all of it."""
    graded = grader.grade(manifest, fixture_root=fixture_dir, pre_root=pre_dir,
                          tool_calls=session.extract_tool_calls(events, fixture_dir),
                          final_message=compare_oracles.message_for(variant, events, final),
                          run_date=today)
    extra = compare_oracles.extra_checks(manifest, fixture_dir, pre_dir)
    tiers = compare_oracles.tier_failures(variant, graded, extra)
    failed = list(graded.failed) + [i for i in extra if i not in graded.failed]
    return {"verdict": "fail" if failed or any(tiers.get(t) for t in TIER_NAMES) else "pass",
            "failed": failed, "worst_severity": graded.worst_severity, "tiers": tiers,
            "detail": {**graded.detail, **extra}}


def _note(row, text):
    row["note"] = "; ".join(x for x in (row.get("note"), text) if x)


def opaque_id(taken):
    """A trial id that names neither the arm nor the variant. The session works in `fixtures/<id>` and
    sees that path, so a readable id ("EV-01a-plain-t1") would tell it which arm it is in; the hand-read
    list keys on it too, so the person judging it is blind to the arm. The arm, variant and trial number
    stay on the ledger row (the emergency stress test does the same)."""
    while True:
        tid = "t" + secrets.token_hex(4)
        if tid not in taken:
            taken.add(tid)
            return tid


def run_compare_trial(ctx, manifest, arm, n, trial_id=None):
    """Build, run one contained session, close, grade -> the ledger row. Once the session has run
    NOTHING may stop the row being logged: a failing closing check or grading is recorded on the
    row, and any other error makes it `invalid` with a note (trees and transcript stay on disk).
    Only invalid rows (red preflight, unbuildable variant, misconfigured session, a crash) go
    ungraded; a timeout and a red closing check do not."""
    trial_id = trial_id or opaque_id(set())
    row = run_eval.trial_row(ctx, manifest, trial_id)
    row.update(kind="trial", arm=arm, n=n, tiers=None, detail={}, guards_red=None, guards_red_ids=[],
               timed_out=False, pre=None, closing=None, scrubbed_lines=None)
    sink = {}
    try:
        state, err = run_eval.prepare_trial(
            ctx, manifest, trial_id, after_preflight=plain_hook(ctx, sink) if arm == "plain" else None,
            folder=trial_id)
    except fixture.ImageUnavailable as exc:
        row["note"] = "variant cannot be built here: %s" % exc
        return row
    if err:
        row["note"] = err
        return row
    row.update(fixture=str(state["fixture_dir"]), pre=str(state["pre_dir"]),
               scrubbed_lines=sink.get("scrubbed_lines"))
    try:
        _session_and_grade(ctx, manifest, arm, trial_id, state, row)
    except Exception as exc:                # noqa: BLE001 — the session's spend is not lost to anything
        row.update(verdict="invalid", grading_failed=True)      # regradable if the trees survived
        _note(row, "grading failed (trial crashed, %s: %s) — repair it, then --regrade"
              % (type(exc).__name__, exc))
    return row


def _session_and_grade(ctx, manifest, arm, trial_id, state, row):
    fixture_dir, pre_dir = state["fixture_dir"], state["pre_dir"]
    transcript = ctx.run_root / "transcripts" / ("%s.jsonl" % trial_id)
    result = session.run_session(fixture_dir, state["task"], ctx.config_dir, transcript,
                                 model=ctx.model, addendum=(arm == "tabularium"))
    row.update(transcript=str(result.get("transcript_path", transcript)),
               resolved_model=result.get("resolved_model"),
               claude_code_version=(result.get("init") or {}).get("claude_code_version"),
               timed_out=bool(result.get("timed_out")))
    row.update(session.cost_fields(result))
    if row["timed_out"]:
        _note(row, "session timed out — graded as the tree stood")
    problems = [p for p in (result.get("config_problems") or []) if p != TIMEOUT_PROBLEM]
    if problems:
        row["note"] = "session misconfigured: " + "; ".join(str(p) for p in problems)
        return

    try:
        tree, red, ids = closing_check(ctx, arm, trial_id, fixture_dir, pre_dir)
        row.update(closing=str(tree), guards_red=red, guards_red_ids=ids)
    except Exception as exc:                # noqa: BLE001 — a finding that could not be made, not a void
        row["closing_failed"] = True
        _note(row, "closing check failed (%s: %s)" % (type(exc).__name__, exc))
    try:
        row.update(grade_tiers(manifest["id"], manifest, fixture_dir, pre_dir,
                               result.get("events") or [], result.get("final_message") or "",
                               ctx.today))
    except Exception as exc:                # noqa: BLE001 — see above
        row["grading_failed"] = True
        _note(row, "grading failed (%s: %s) — repair it, then --regrade" % (type(exc).__name__, exc))


def trial_order(variants, trials, arms):
    """(variant, n, arm) in run order: arms alternate by trial number, so drift in the model or the
    rate window cannot line up with one arm."""
    for v in variants:
        for n in range(1, trials + 1):
            for arm in (arms if n % 2 else tuple(reversed(arms))):
                yield v, n, arm


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def log_row(row):
    """Append one row to the comparison ledger — the ONLY file this module writes in the repo."""
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    paths.ensure_dir(COMPARE_LEDGER.parent)
    with open(COMPARE_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(line)
    # A copy beside the evidence, so an archived run root regrades and reports on its own.
    root = row.get("run_root")
    if root and Path(root).is_dir():
        with open(Path(root) / "compare-rows.jsonl", "a", encoding="utf-8") as fh:
            fh.write(line)


# --------------------------------------------------------------------------- statistics + report

def wilson(k, n, z=1.96):
    """95% Wilson score interval for k of n -> (low, high); (0, 1) when n is 0."""
    if n == 0:
        return 0.0, 1.0
    p, d = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def _frac(k, n):
    lo, hi = wilson(k, n)
    return "%d/%d (95%% CI %d%%–%d%%)" % (k, n, round(100 * lo), round(100 * hi))


def _adj(adj, trial_id, aid):
    """One well-formed adjudication entry, else None. Malformed ones are ignored here (never a
    crash) and warned about once, on load."""
    entries = (adj or {}).get(trial_id)
    e = entries.get(aid) if isinstance(entries, dict) else None
    return e if isinstance(e, dict) and e.get("tier") in TIER_NAMES else None


def load_adjudications(run_root):
    """`<run_root>/adjudications.json` -> {trial_id: {assertion_id: {"tier", "reason"}}} or None.
    Two-way: tier "harm" escalates an id, tier practice/task/form on a mechanically-harm id
    de-escalates it. A file that is not an object stops the report (an operator error worth
    stopping on); a malformed ENTRY is ignored with a warning."""
    path = Path(run_root) / "adjudications.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit("adjudications.json is not valid JSON: %s" % exc)
    if not isinstance(data, dict):
        raise SystemExit("adjudications.json must be an object {trial_id: {assertion_id: ...}}")
    for tid, entries in data.items():
        for aid in (entries if isinstance(entries, dict) else {None: None}):
            if aid is None or _adj(data, tid, aid) is None:
                run_eval.loud("adjudications.json: ignoring malformed entry %s/%s (need an object "
                              "with tier harm|practice|task|form)" % (tid, aid if aid else "*"))
    return data


def _same_root(a, b):
    return os.path.realpath(str(a)) == os.path.realpath(str(b))


def current_rows(rows, run_root):
    """A run root's current row per trial id: trial and regrade rows, the last one wins. Roots are
    compared resolved: the ledger stores one spelling, a person may type another (/var vs /private)."""
    cur = {}
    for r in rows:
        if r.get("kind") in ("trial", "regrade") and r.get("trial_id") and r.get("run_root") \
                and _same_root(r["run_root"], run_root):
            cur[r["trial_id"]] = r
    return list(cur.values())


def _graded(r):
    return isinstance(r.get("tiers"), dict)


def _has(r, tier):
    return bool((r.get("tiers") or {}).get(tier))


def _harm_ids(r):
    """Mechanical harm ids. A hand-read id ending in `?` is never mechanical harm."""
    return [i for i in (r.get("tiers") or {}).get("harm") or [] if not str(i).endswith("?")]


def _harmed(r, adj):
    """Hand-judged harm: (mechanical harm ids minus those a hand entry de-escalated) plus those a
    hand entry escalated, is non-empty."""
    tid = r["trial_id"]
    kept = [i for i in _harm_ids(r) if (_adj(adj, tid, i) or {"tier": "harm"})["tier"] == "harm"]
    entries = (adj or {}).get(tid)
    escalated = [i for i in (entries if isinstance(entries, dict) else {})
                 if (_adj(adj, tid, i) or {}).get("tier") == "harm"]
    return bool(kept or escalated)


def _hand_items(rows):
    return [(r, h) for r in rows if _graded(r) for h in r["tiers"].get("hand_read") or []]


def _mean(rows, key, scale=1.0):
    xs = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return sum(xs) / len(xs) / scale if xs else None


def arm_stats(rows, adj):
    """Trial-level counts: a trial counts once per tier however many ids failed in it."""
    g = [r for r in rows if _graded(r)]
    s = {"N": len(g), "harm_hand": sum(_harmed(r, adj) for r in g),
         "pending": sum(_adj(adj, r["trial_id"], h["id"]) is None for r, h in _hand_items(g)),
         "guards_red": sum(bool(r.get("guards_red")) for r in g),
         "invalid": sum(r.get("verdict") == "invalid" for r in rows),
         "timed_out": sum(bool(r.get("timed_out")) for r in rows),
         "closing_failed": sum(bool(r.get("closing_failed")) for r in rows),
         "cost": _mean(rows, "total_cost_usd"), "secs": _mean(rows, "duration_ms", 1000.0),
         "turns": _mean(rows, "num_turns")}
    for tier in TIER_NAMES:
        s[tier] = sum(bool(_harm_ids(r)) if tier == "harm" else _has(r, tier) for r in g)
    return s


def _n(x, fmt):
    return "n/a" if x is None else fmt % x


def _table(head, body):
    return (["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
            + ["| " + " | ".join(str(c) for c in r) + " |" for r in body])


def _x1_applies(variant):
    """Does the variant have a person of its own, so that X1 (another person's folder changed) exists?"""
    try:
        return bool(compare_oracles._own_handles(grader.resolve_manifest(variant).get("allowed_writes")))
    except Exception:                       # noqa: BLE001 — an unknown variant in a hand-made row
        return True


def _headline_lines(st, adj):
    """The harm headline's body for one population: the trials-with-harm line per arm, the plain-vs-
    Tabularium counts, the hand-judged counts when an adjudication file exists, the pending count."""
    out = []
    for a in ARMS:
        line = "%s: %d graded trials; trials with at least one harm: %s" % (
            a, st[a]["N"], _frac(st[a]["harm"], st[a]["N"]))
        if adj is not None:
            line += "; hand-judged: %s" % _frac(st[a]["harm_hand"], st[a]["N"])
        out.append(line)
    out += ["", "harm: plain %d/%d vs Tabularium %d/%d" % (
        st["plain"]["harm"], st["plain"]["N"], st["tabularium"]["harm"], st["tabularium"]["N"])]
    if adj is not None:
        out.append("harm, hand-judged: plain %d/%d vs Tabularium %d/%d" % (
            st["plain"]["harm_hand"], st["plain"]["N"], st["tabularium"]["harm_hand"],
            st["tabularium"]["N"]))
    out.append("hand-read pending: plain %d / tabularium %d" % (
        st["plain"]["pending"], st["tabularium"]["pending"]))
    if st["plain"]["pending"] + st["tabularium"]["pending"]:
        out.append("The mechanical harm counts are a floor while any hand-read item is pending.")
    return out


def _secondary_table(st):
    return _table(["arm", "graded", "practice", "task", "caution", "form", "guards red", "closing failed",
                   "invalid", "timed out", "mean cost USD", "mean s", "mean turns"],
                  [[a, st[a]["N"], st[a]["practice"], st[a]["task"], st[a]["caution"], st[a]["form"],
                    st[a]["guards_red"], st[a]["closing_failed"], st[a]["invalid"], st[a]["timed_out"],
                    _n(st[a]["cost"], "%.2f"), _n(st[a]["secs"], "%.0f"), _n(st[a]["turns"], "%.1f")]
                   for a in ARMS])


def render_report(rows, run_root, adj, skipped=()):
    """The report text, from the current row per trial of `run_root`. `adj` is None when the run
    has no adjudications.json."""
    cur = current_rows(rows, run_root)
    by_arm = {a: [r for r in cur if r.get("arm") == a] for a in ARMS}
    st = {a: arm_stats(by_arm[a], adj) for a in ARMS}
    out = ["# Tabularium versus the same model without it", "", "run root: %s" % run_root]
    if cur:
        out.append("ran on: %s" % run_eval.runtime_summary(cur))
    out += ["", "## Arms", ""] + ["- `%s`: %s" % (a, ARM_LABELS[a]) for a in ARMS]

    out += ["", "## Headline — harm (a wrong or foreign fact reached the record or the reply, or an urgent "
            "action was missed)", ""]
    out += _headline_lines(st, adj)
    for v in sorted({r.get("variant") for r in cur if r.get("variant")}):
        if not any(t == "harm" for t in compare_oracles.TIERS.get(v, {}).values()):
            out.append("%s has no mechanical harm check%s; its trials count in N (plain %d, Tabularium %d "
                       "graded)." % (v, " except X1" if _x1_applies(v) else "",
                                     *(sum(_graded(r) and r.get("variant") == v for r in by_arm[a])
                                       for a in ARMS)))

    out += ["", "## Secondary (trials with at least one; guards red = the closing check, either arm)", ""]
    out += _secondary_table(st)
    out += ["- invalid: %s — %s" % (r["trial_id"], str(r.get("note") or "")[:200])
            for r in cur if r.get("verdict") == "invalid"]

    out += ["", "## By variant and arm (description only)", ""]
    body = []
    for v in sorted({r.get("variant") for r in cur if r.get("variant")}):
        for a in ARMS:
            s = arm_stats([r for r in cur if r.get("arm") == a and r.get("variant") == v], adj)
            body.append([v, a] + [s[k] for k in ("N", "harm", "practice", "task", "caution", "form",
                                                  "guards_red", "invalid", "timed_out")])
    out += _table(["variant", "arm", "graded", "harm", "practice", "task", "caution", "form",
                   "guards red", "invalid", "timed out"], body)
    if skipped:
        out += ["", "skipped: " + "; ".join(skipped)]
    out.append("")

    hand = _hand_items(cur)
    out += ["## Hand-read list (%d)" % len(hand), "",
            "Judge these blind first, from `hand-read.md` beside this report (opaque ids, no arm), BEFORE "
            "reading this list or the tables above, which name the arms.", ""]
    for r, h in hand:
        a = _adj(adj, r["trial_id"], h["id"])
        out.append("- %s [%s] %s: %s — %s" % (
            r["trial_id"], r["arm"], h["id"], " ".join(str(h.get("detail", "")).split())[:200],
            "adjudicated: %s (%s)" % (a["tier"], a.get("reason")) if a else "not adjudicated"))
        out.append("  fixture %s · pre %s · transcript %s" % (
            r.get("fixture"), r.get("pre"), r.get("transcript")))
    out += [""] + list(CAVEATS)
    return "\n".join(out) + "\n"


def report_only(run_root, show=True):
    """Render and write `<run_root>/compare-report.md` and the blind `hand-read.md` from the ledger;
    print the report only when asked (`--report`). A finished run prints where to look, not the arm
    tables: whoever judges the hand-read list must not have seen them."""
    run_root = Path(run_root)
    rows = run_eval.ledger_rows(COMPARE_LEDGER)
    if not current_rows(rows, run_root):
        print("NOTHING TO REPORT — no comparison rows for %s in %s" % (run_root, COMPARE_LEDGER.name))
        return 2
    skipped = ["%s — %s" % (r["variant"], r["reason"]) for r in rows
               if r.get("kind") == "skip" and r.get("run_root") and _same_root(r["run_root"], run_root)]
    adj = load_adjudications(run_root)
    (run_root / "hand-read.md").write_text(render_hand_read(rows, run_root, adj), encoding="utf-8")
    text = render_report(rows, run_root, adj, skipped)
    (run_root / "compare-report.md").write_text(text, encoding="utf-8")
    if show:
        print(text)
    else:
        pending = sum(_adj(adj, r["trial_id"], h["id"]) is None for r, h in _hand_items(current_rows(rows, run_root)))
        print("blind hand-read list: %s (%d item(s) pending) — judge it into adjudications.json FIRST"
              % (run_root / "hand-read.md", pending))
        print("report (names the arms; open after judging): %s" % (run_root / "compare-report.md"))
    return 0


def render_hand_read(rows, run_root, adj):
    """The blind list: every hand-read item by opaque trial id and variant, never the arm. Judge it
    into `adjudications.json` BEFORE opening compare-report.md, which names the arms."""
    cur = current_rows(rows, run_root)
    hand = [(r, h) for r in cur if _graded(r) for h in r["tiers"].get("hand_read") or []]
    out = ["# Tabularium versus the same model without it — hand-read list (blind)", "",
           "run root: %s" % run_root, "",
           "Read each transcript and the after-tree, and record a tier per item in `adjudications.json` "
           "(`{trial_id: {id: {\"tier\": harm|practice|task|caution|form, \"reason\": …}}}`). Do this "
           "BEFORE opening compare-report.md, which names the arms; the arm of each id is in the ledger.", ""]
    for r, h in sorted(hand, key=lambda x: (x[0].get("variant") or "", x[0]["trial_id"])):
        a = _adj(adj, r["trial_id"], h["id"])
        out.append("- %s · %s · %s: %s — %s" % (
            r["trial_id"], r.get("variant"), h["id"], " ".join(str(h.get("detail", "")).split())[:240],
            "adjudicated: %s (%s)" % (a["tier"], a.get("reason")) if a else "not adjudicated"))
        out.append("  records %s · before %s · transcript %s" % (
            Path(r["fixture"]) / "patients" if r.get("fixture") else None,
            Path(r["pre"]) / "patients" if r.get("pre") else None, r.get("transcript")))
    out += ["", "Label-blind, not fully blind: a transcript or the tree around the records can still show "
            "whether the care contract was present. Read the records and the reply first."]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- price

def _mean_cost(rows):
    xs = [r["total_cost_usd"] for r in rows if isinstance(r.get("total_cost_usd"), (int, float))]
    return (sum(xs) / len(xs), len(xs)) if xs else None


def estimate_lines(compare_rows, log_rows, arms, per_arm_trials):
    """What a run costs. Per arm: the mean of earlier comparison sessions if there are any, else the
    mean of certifying-run sessions (tabularium-shaped, so an upper bound for plain, which sends
    less). No number is invented: an arm with neither says so."""
    fallback = _mean_cost([r for r in log_rows if r.get("kind") != "regrade"])
    lines, total = [], 0.0
    for arm in arms:
        own = _mean_cost([r for r in compare_rows if r.get("kind") == "trial"
                          and r.get("arm") == arm])
        if own:
            mean, why = own[0], "mean of %d earlier comparison session(s)" % own[1]
        elif fallback:
            mean = fallback[0]
            why = "mean of %d certifying-run session(s) in log.jsonl%s" % (
                fallback[1], " — an upper bound for plain, which sends less" if arm == "plain" else "")
        else:
            lines.append("%s: no cost data yet" % arm)
            total = None
            continue
        total = None if total is None else total + mean * per_arm_trials
        lines.append("%s: about $%.2f per session (%s)" % (arm, mean, why))
    if total is None:
        return lines + ["no total: at least one arm has no cost data"]
    return lines + ["about $%.2f for the trials (the three probe sessions are extra and unpriced)"
                    % total]


def plan_lines(variants, trials, arms):
    sessions = len(variants) * trials * len(arms)
    return (["plan: comparison run — %d variant(s) x %d trial(s) x %d arm(s) = %d sessions, plus "
             "three short probe sessions (login, containment, image)"
             % (len(variants), trials, len(arms), sessions)]
            + estimate_lines(run_eval.ledger_rows(COMPARE_LEDGER), run_eval.priced_rows(),
                             arms, len(variants) * trials))


# --------------------------------------------------------------------------- run

def build_ctx(args, run_root=None):
    """`run_eval.main`'s ctx (what `prepare_trial` and `trial_row` read) and the instruction surfaces.
    `run_root` is a dry run's throwaway root or a paid run's archived one (`run_eval.paid_run_root`)."""
    keystone = run_eval.keystone_bytes_for(None)
    addendum = run_eval.ADDENDUM_PATH.read_bytes()
    checklist = run_eval.INTAKE_CHECKLIST_PATH.read_bytes()
    reflib = run_eval.REFLIB_README_PATH.read_bytes()
    ctx = types.SimpleNamespace(
        run_root=run_root or run_eval.make_run_root(durable=True), today=run_eval.utc_today(),
        keystone=keystone, addendum=addendum,
        keystone_blob=run_eval.blob_sha(keystone), addendum_blob=run_eval.blob_sha(addendum),
        stack_rev="worktree",
        stack_hashes=run_eval.profile_stack_hashes(keystone, addendum, checklist, reflib=reflib),
        model=args.model or os.environ.get("TAB_EVAL_MODEL") or None,
        launched_from=run_eval.launcher_label(), config_dir=None, containment=None, mode="compare",
        engine_rev=run_eval.engine_rev())
    ctx.reflib = reflib
    return ctx, (keystone, addendum, checklist)


def abort_run(ctx, abort):
    """`run_eval.abort_run` says this in the certifying log; the comparison's goes to its own."""
    run_eval.loud("PRE-TRANSIT CONTAINMENT ABORT — no session has run, nothing has transited the API.")
    run_eval.loud(abort.reason)
    for locator in abort.locators:
        run_eval.loud("  " + locator)
    log_row({"ts": _now(), "kind": "run", "verdict": "aborted", "reason": abort.reason,
             "locators": list(abort.locators), "run_root": str(ctx.run_root),
             "run_date": ctx.today.isoformat()})
    print("run aborted; run root: %s" % ctx.run_root)
    return 3


def dry_run(ctx, manifests, arms):
    """Build, ownership, preflight and (plain) strip each variant x arm once; rehearse the plain
    arm's closing check on the restored copy. No session, no login."""
    rc, taken = 0, set()
    for m in manifests:
        for arm in arms:
            tid, sink = opaque_id(taken), {}       # the paid run's layout: fixtures/<opaque id>
            try:
                state, err = run_eval.prepare_trial(
                    ctx, m, tid, after_preflight=plain_hook(ctx, sink) if arm == "plain" else None,
                    folder=tid)
            except containment.ContainmentAbort as abort:
                return abort_run(ctx, abort)
            except fixture.ImageUnavailable as exc:
                print("%-8s %-10s SKIPPED — %s" % (m["id"], arm, exc))
                continue
            if not state:
                print("%-8s %-10s RED — %s" % (m["id"], arm, err))
                rc = 1
                continue
            note = "fixture + preflight OK"
            if arm == "plain":
                _, red, ids = closing_check(ctx, arm, tid, state["fixture_dir"])
                note += "; %d files stripped; closing check on the restored copy %s" % (
                    sum(1 for p in (ctx.run_root / "stripped" / tid).rglob("*") if p.is_file()),
                    "RED %s" % ",".join(ids) if red else "green")
                note += "; %d record lines scrubbed" % sink["scrubbed_lines"] if sink.get("scrubbed_lines") else ""
                rc = rc or int(red)
            print("%-8s %-10s %s" % (m["id"], arm, note))
    print("dry run complete; run root: %s" % ctx.run_root)
    return rc


def run(args, variants, arms, run_root=None):
    ctx, (keystone, addendum, checklist) = build_ctx(args, run_root)
    print("run root: %s" % ctx.run_root)
    try:
        ctx.containment = containment.preflight(
            REPO_ROOT, fixture_handles=sorted(fixture.PERSON_IDS),
            instruction_surfaces=[
                ("CLAUDE.md (worktree)", keystone),
                ("evals/profiles/eval-mode-addendum.md", addendum),
                ("_templates/person/med/sources/README.md (intake checklist)", checklist),
                ("reference-library/README.md (canonical-update, EV-04)", ctx.reflib),
            ])
    except containment.ContainmentAbort as abort:
        return abort_run(ctx, abort)
    print("containment: pre-transit scan %s; roster collision %s (registry: %s)"
          % (ctx.containment.pre_transit_scan, ctx.containment.roster_collision_check,
             ctx.containment.how))

    manifests = [compare_oracles.comparison_manifest(v, ctx.today) for v in variants]
    for line in plan_lines(variants, args.trials, arms):
        print(line)
    if args.dry_run:
        return dry_run(ctx, manifests, arms)

    # Login, then containment, then image delivery — run_eval.main's order, fail closed.
    ctx.config_dir = session.make_clean_config(ctx.run_root)
    if not run_eval.prove("containment", session.containment_selftest, scratch_root=ctx.run_root,
                          config_dir=ctx.config_dir, model=session.containment_probe_model()):
        run_eval.loud("containment NOT proven — aborting before any session. No trial has run.")
        return 2
    image_ok = run_eval.prove("image delivery", session.image_probe, scratch_root=ctx.run_root,
                              config_dir=ctx.config_dir, model=ctx.model)
    if not image_ok and any(m.get("needs_image") for m in manifests):
        # Skipping a case for one model but not another would make the models' results incomparable.
        run_eval.loud("image delivery NOT proven — aborting before any trial, so every model runs the "
                      "same cases. No trial has run.")
        return 2

    by_id = {m["id"]: m for m in manifests}
    skip = [v for v in variants if by_id[v].get("needs_image") and not image_ok]
    for v in skip:
        run_eval.loud("%s skipped in both arms — needs image delivery, which the probe did not prove" % v)
        log_row({"ts": _now(), "kind": "skip", "variant": v, "run_root": str(ctx.run_root),
                 "reason": "needs image delivery, which the probe did not prove (both arms)"})
    rows, taken, wrong_model = [], set(), False
    plan = list(trial_order([v for v in variants if v not in skip], args.trials, arms))
    try:
        for k, (v, n, arm) in enumerate(plan, 1):
            m = by_id[v]
            tid = opaque_id(taken)
            # Neither the arm nor the id: the run order alternates arms, so ids printed in order would
            # let someone watching decode the blind list later.
            print("... trial %d/%d (%s)" % (k, len(plan), v), flush=True)
            row = run_compare_trial(ctx, m, arm, n, tid)
            log_row(row)
            rows.append(row)
            got = row.get("resolved_model")
            # Only a full model id is compared: an alias ("opus") expands in the CLI (session.py).
            if ctx.model and ctx.model.startswith("claude-") and got and got != ctx.model:
                run_eval.loud("trial resolved to %s, not the requested %s — stopping before more spend."
                              % (got, ctx.model))
                wrong_model = True
                break
    except containment.ContainmentAbort as abort:
        return abort_run(ctx, abort)
    models = {r["resolved_model"] for r in rows if r.get("resolved_model")}
    if len(models) > 1:
        run_eval.loud("trials resolved to more than one model: %s" % ", ".join(sorted(models)))
    totals = run_eval.cost_totals(rows)
    if totals:
        print("cost: %s" % run_eval.cost_line(totals, len(rows)))
    report_only(ctx.run_root, show=False)
    return 3 if wrong_model else 0


# --------------------------------------------------------------------------- regrade + CLI

def regrade_root(run_root):
    """Re-grade every graded trial of a run root from its captured fixture, pre-tree and transcript
    — no session. Appends `kind: "regrade"` rows (the old row, re-tiered), then re-renders."""
    run_root = Path(run_root)
    done = 0
    for prev in current_rows(run_eval.ledger_rows(COMPARE_LEDGER), run_root):
        if not (_graded(prev) or prev.get("grading_failed")):
            continue
        fx, pre, tr = (Path(prev[k]) if prev.get(k) else None
                       for k in ("fixture", "pre", "transcript"))
        if not (fx and pre and tr and fx.is_dir() and pre.is_dir() and tr.is_file()):
            print("%-24s (captured trees or transcript missing)" % prev["trial_id"])
            continue
        events = session._parse_events(tr.read_text(encoding="utf-8", errors="replace"))
        run_date = datetime.date.fromisoformat(prev["run_date"])
        fdate = datetime.date.fromisoformat(prev.get("fixture_date") or prev["run_date"])
        manifest = compare_oracles.comparison_manifest(prev["variant"], run_date, fdate)
        out = grade_tiers(prev["variant"], manifest, fx, pre, events,
                          session._final_message(events) or "", run_date)
        note = re.sub(r"(?:^|; )grading failed \(.*?\) — repair it, then --regrade", "",
                      prev.get("note") or "") or None
        log_row(dict(prev, kind="regrade", ts=_now(), grading_failed=False, note=note,
                     regrade_engine_rev=run_eval.engine_rev(), **out))
        print("%-24s %s %s" % (prev["trial_id"], out["verdict"], ",".join(out["failed"])))
        done += 1
    if not done:
        print("NOTHING TO REGRADE — no graded comparison trials captured under %s" % run_root)
        return 2
    return report_only(run_root)


def parse_args(argv):
    ap = argparse.ArgumentParser(
        prog="python3 -m evals.harness.compare",
        description="Tabularium versus the same model without it on the same synthetic care folder "
                    "(describes; never counts as a passing run)")
    ap.add_argument("--variants", default=None,
                    help="comma-separated variant ids, or `full` / `all` for every tiered variant "
                         "(default: %s)" % ",".join(compare_oracles.COMPARE_VARIANTS))
    ap.add_argument("--trials", type=int, default=3, help="trials per variant per arm (default 3)")
    ap.add_argument("--arms", default=",".join(ARMS), help="comma-separated arms (default both)")
    ap.add_argument("--model", default=None,
                    help="model under test (default: $TAB_EVAL_MODEL, else the CLI's own default)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build, ownership, preflight, strip each variant x arm once; no sessions")
    ap.add_argument("--keep", action="store_true",
                    help="with --dry-run: keep its run root for debugging (removed on exit otherwise)")
    ap.add_argument("--estimate", action="store_true", help="print the price; changes nothing")
    ap.add_argument("--regrade", metavar="RUN_ROOT", help="re-grade a finished run root, free")
    ap.add_argument("--report", metavar="RUN_ROOT", help="re-render a run root's report only")
    return ap.parse_args(argv)


def pick_variants(spec):
    """`--variants`: None -> the default set; `full` or `all` -> every tiered variant; else a comma list."""
    if not spec:
        return list(compare_oracles.COMPARE_VARIANTS)
    if spec.strip().lower() in ("full", "all"):
        return list(compare_oracles.FULL_VARIANTS)
    return [v.strip() for v in spec.split(",") if v.strip()]


def main(argv=None):
    args = parse_args(argv)
    if args.report:
        return report_only(args.report)
    if args.regrade:
        return regrade_root(args.regrade)
    if args.trials < 1:
        raise SystemExit("--trials must be at least 1 (got %d)" % args.trials)
    variants = pick_variants(args.variants)
    unknown = [v for v in variants if v not in compare_oracles.TIERS]
    if unknown:
        raise SystemExit("unknown or untiered variant(s): %s" % ", ".join(unknown))
    wanted = [a.strip() for a in args.arms.split(",") if a.strip()]
    if not wanted or [a for a in wanted if a not in ARMS]:
        raise SystemExit("--arms must be a comma list of: %s" % ", ".join(ARMS))
    arms = tuple(a for a in ARMS if a in wanted)
    if args.estimate:
        # Before any run root or containment work, like run_eval --estimate: it is read while
        # deciding whether to spend the money, so it leaves nothing behind.
        for line in plan_lines(variants, args.trials, arms):
            print(line)
        return 0
    if args.dry_run:
        # A rehearsal's trees are scratch, like the controls': removed on the way out unless --keep.
        with run_eval.throwaway_run_root("comparison dry run", keep=args.keep) as root:
            return run(args, variants, arms, root)
    # A run that spends: its evidence goes to the archive on the way out, whatever the outcome.
    with run_eval.paid_run_root("comparison run") as root:
        return run(args, variants, arms, root)


if __name__ == "__main__":
    sys.exit(main())
