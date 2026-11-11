#!/usr/bin/env python3
"""regrade.py — grade a finished run's captured trials again, under the CURRENT engine and oracles.

WHY. Sessions are the only real cost of the eval. Every trial leaves its before-tree, after-tree,
transcript and final message on disk, so when an oracle turns out to be miscalibrated against real
output (the whole first live run was that), the fix is checked here for free — no session is
rerun. Only a case whose *spec* was wrong needs new sessions.

    python3 -m evals.harness.regrade <run root> [--variants EV-02a,...]

Prints one line per trial with the current verdict and the failed assertion ids, then a summary.
What the run observed is carried, not re-judged: a trial that grades clean but whose closing board
was red at run time, an environment-invalid trial, and a captured trial with no run-time row at all
come back `invalid` — never a pass, so `--record` can never write a pass for them.
Without --record it writes nothing (a what-if). With --record it appends one `kind: "regrade"` row
per trial to the run's log AND the repository ledger — the run-time rows stay as they were, the
regrade rows sit after them, and the current verdict of a trial is its LAST row. The ledger must
never say "fail" for a trial the recorded engine judges "pass" while the ADR says otherwise: the
first run did exactly that until this flag existed.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.harness import grader, paths, run_eval, session  # noqa: E402


def fixture_dates(run_root, run_date):
    """`{trial_id: the date that trial's FIXTURE was built from}`, read out of the run's own log.

    WHY (2026-09-07). In a run from before 2026-09-28 a trial's tree may have been built one
    or more days BACK of the run date, to step off a fixture date that collided with the firewall's
    case-reference class (that retry is retired; newer rows always carry the run date). The
    oracles' offset placeholders describe planted content, so a regrade has to instantiate them
    against the base the tree was built from — regrading a shifted run against the run date would
    miss every planted date by exactly the shift, and `regrade --record` is ledger truth.

    Fail-soft, deliberately: an unparseable row, a missing field (every row before 2026-09-07) or
    an unreadable log leaves that trial on `run_date`, which is what it was built with.
    `identity is (run_root, trial_id)`, so the LAST row for a trial id wins.
    """
    import datetime
    import json

    out = {}
    try:
        lines = (Path(run_root) / "log.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or not row.get("trial_id") or not row.get("fixture_date"):
            continue
        try:
            out[row["trial_id"]] = datetime.date.fromisoformat(str(row["fixture_date"]))
        except ValueError:
            out.pop(row["trial_id"], None)
    return out


def recorded_rows(run_root):
    """`{trial_id: the run's own last row for it}` — run-time rows only; regrade rows never count,
    because what they carry is a past regrade's opinion, not what the run observed."""
    import json

    out = {}
    try:
        lines = (Path(run_root) / "log.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("trial_id") and row.get("kind") != "regrade":
            out[row["trial_id"]] = row
    return out


def recorded_closing(row):
    """`(red, FAIL lines)` for the closing board a run recorded for one trial.

    Rows since 2026-10-02 carry `closing_board` and `closing_fail_lines`. Older rows say it only
    in their note (`closing check.sh rc=N: …`), where the run kept the board's LAST line — often a
    SKIP line, so no FAIL line survives to quote. The board is not re-run here: its verdict is what
    the run observed at the time, and a later board would judge a different engine's question.
    """
    if not row:
        return False, []
    if row.get("closing_board"):
        return row["closing_board"] == "red", list(row.get("closing_fail_lines") or [])
    note = str(row.get("note") or "")
    if note.startswith("closing check.sh rc="):
        lines = [part.strip() for part in note.split(": ", 1)[-1].split(" | ")
                 if part.strip().startswith("FAIL [")]
        return True, lines or ["(FAIL line not recorded: this run's note kept the board's last "
                               "line only)"]
    return False, []


def invalid_at_run_time(row):
    """Why a captured trial cannot be regraded to a verdict, else None.

    A misconfigured or timed-out session still leaves a transcript and a pre-tree, so it can be
    graded again — and a regrade that graded it would hand the ledger a `pass` for a session that
    ran without its pinned policy, or never finished. A trial with no run-time row at all (a lost
    or truncated log) never had its closing board observed, so a pass for it would be unfounded.
    A red closing board is handled after grading (regrade_run): a graded fail still stands.
    """
    if not row:
        return "closing board not observed: no run-time row for this trial"
    if row.get("verdict") != "invalid" or recorded_closing(row)[0]:
        return None
    return str(row.get("note") or "invalid at run time")


def _held_invalid(why):
    held = grader.GradeResult(verdict="invalid")
    held.detail["INVALID"] = why
    return held


def regrade_run(run_root, variants=None, run_date=None):
    """Yield (trial_id, GradeResult) for every captured trial under run_root.

    The result carries forward what the run itself observed, as the runner judged it: a trial
    that grades clean while its closing board was red at run time, a trial the run recorded
    `invalid` for an environment reason, and a captured trial with no run-time row come back with
    verdict `invalid`; a graded fail stands whatever the closing board said.
    """
    run_root = Path(run_root)
    if run_date is None:
        # The run's own ledger knows the date its fixtures were built on; today's date is wrong
        # for any run that crossed midnight UTC (it did, once — every dated assertion misread).
        try:
            import datetime
            import json
            run_date = None
            for line in (run_root / "log.jsonl").read_text(encoding="utf-8").splitlines():
                # Rows differ in shape across harness versions: pre-2026-09-06 trial rows carry no
                # containment dispositions, newer ones do, and a run that aborted before any trial
                # leaves a single kind="run" row. Take the first row that states a run date and
                # ignore the rest — a regrade must read every generation of the ledger.
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("run_date"):
                    run_date = datetime.date.fromisoformat(row["run_date"])
                    break
            if run_date is None:
                raise ValueError("no dated row")
        except Exception:                      # noqa: BLE001 — no ledger yet: fall back to today
            run_date = run_eval.utc_today()
    fixtures = run_root / "fixtures"
    if not fixtures.is_dir():
        # A run that aborted before its first fixture (a pre-transit containment abort does) leaves
        # no fixtures at all. That is nothing to regrade, not a crash — and main() below refuses to
        # call it a green.
        return
    # Per TRIAL, not per variant: in a pre-2026-09-28 run each trial resolved its own fixture-date
    # shift, so two trials of one variant may legitimately have been built from different days.
    built_on = fixture_dates(run_root, run_date)
    observed = recorded_rows(run_root)
    cache = {}
    for vdir in sorted(fixtures.iterdir()):
        if not vdir.is_dir() or (variants and vdir.name not in variants):
            continue
        for tdir in sorted(vdir.iterdir()):
            if not tdir.is_dir():
                continue
            fdate = built_on.get(tdir.name, run_date)
            key = (vdir.name, fdate)
            if key not in cache:
                cache[key] = run_eval.manifest_for(vdir.name, today=run_date, fixture_date=fdate)
            manifest = cache[key]
            transcript = run_root / "transcripts" / (tdir.name + ".jsonl")
            pre = run_root / "pre" / vdir.name / tdir.name
            if not transcript.is_file() or not pre.is_dir():
                yield tdir.name, None
                continue
            rec = observed.get(tdir.name)
            why = invalid_at_run_time(rec)
            if why:
                yield tdir.name, _held_invalid(why)
                continue
            events = session._parse_events(transcript.read_text(encoding="utf-8", errors="replace"))
            # The transcript's paths are absolute under the folder the session ran in; a run folder moved
            # since (copied out of the system temp folder, 2026-10-06) is graded against its new tree,
            # but its paths are made relative to the run-time folder the init event records.
            ran_in = (session._find_init(events) or {}).get("cwd") or str(tdir)
            calls = session.extract_tool_calls(events, ran_in)
            final = session._final_message(events) or ""
            graded = grader.grade(manifest, fixture_root=tdir, pre_root=pre,
                                  tool_calls=calls, final_message=final, run_date=run_date,
                                  first_message=session.first_message(events))
            red, lines = recorded_closing(rec)
            if red and graded.verdict != "fail":
                yield tdir.name, _held_invalid("closing check.sh red at run time: %s"
                                               % " | ".join(lines))
                continue
            yield tdir.name, graded


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m evals.harness.regrade")
    ap.add_argument("run_root")
    ap.add_argument("--variants", default=None, help="comma-separated variant ids (default all)")
    ap.add_argument("--run-date", default=None, help="YYYY-MM-DD the run used (default: today, UTC)")
    ap.add_argument("--record", action="store_true",
                    help="append kind=regrade rows (run log + repository ledger); default is a what-if")
    args = ap.parse_args(argv)
    variants = [v.strip() for v in args.variants.split(",")] if args.variants else None
    run_date = None
    if args.run_date:
        import datetime
        run_date = datetime.date.fromisoformat(args.run_date)
    passed = failed = missing = 0
    engine_rev = _engine_rev()
    for tid, g in regrade_run(args.run_root, variants, run_date):
        if g is None:
            missing += 1
            print("%-12s (no transcript or pre-tree captured)" % tid)
            continue
        if g.verdict == "invalid":
            # Counted with the uncaptured: it blocks a green, and is rerun as a new
            # run, exactly as the runner's summary says of an invalid trial.
            missing += 1
            print("%-12s invalid (%s)" % (tid, g.detail.get("INVALID")))
            if args.record:
                _record(Path(args.run_root), tid, g, engine_rev)
            continue
        if g.verdict == "pass":
            passed += 1
            print("%-12s pass" % tid)
        else:
            failed += 1
            print("%-12s fail  %s [%s]" % (tid, ",".join(g.failed), g.worst_severity))
            for aid, detail in g.detail.items():
                print("    %s -> %s" % (aid, detail[:200]))
        if args.record:
            _record(Path(args.run_root), tid, g, engine_rev)
    where = "recorded to ledger, engine %s" % engine_rev if args.record else "ledger untouched"
    print("\nregraded: %d pass, %d fail, %d uncaptured or invalid (%s)"
          % (passed, failed, missing, where))
    if passed + failed + missing == 0:
        # Fail closed, the guards' rule applied here: a regrade that examined nothing must never
        # read as a clean one (an aborted run, or a wrong run root, lands exactly here).
        print("NOTHING TO REGRADE — no captured trials under %s (an aborted run, or the wrong "
              "run root). This is not a green." % args.run_root)
        return 2
    return 0 if failed == 0 and missing == 0 else 1


def _engine_rev():
    """Short git revision of the grader in use, so a regrade row says which engine judged it —
    the same stamp the runner puts on its trial rows (run_eval.engine_rev)."""
    return run_eval.engine_rev()


def _record(run_root, trial_id, graded, engine_rev):
    """Append one regrade row to the run log and the repository ledger (same shape as a trial row,
    plus kind/engine_rev so the two are never confused)."""
    import datetime
    import json
    row = {
        "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": "regrade",
        "engine_rev": engine_rev,
        "run_root": str(run_root),
        "trial_id": trial_id,
        "variant": trial_id.rsplit("-t", 1)[0],
        "verdict": graded.verdict,
        "failed": list(graded.failed),
        "worst_severity": graded.worst_severity,
    }
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    paths.ensure_dir(run_eval.RESULTS_LOG.parent)
    for path in (run_root / "log.jsonl", run_eval.RESULTS_LOG):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)


if __name__ == "__main__":
    sys.exit(main())
