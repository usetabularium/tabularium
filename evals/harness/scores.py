#!/usr/bin/env python3
"""scores.py — one compact row per eval run, generated from the run ledgers so it never drifts.

    python3 -m evals.harness.scores            # rewrite evals/results/scores.csv
    python3 -m evals.harness.scores --check    # exit 1 if scores.csv is not what the ledgers give

Reads `log.jsonl` (core, full and targeted runs), `compare.jsonl` (comparison and pilot runs, one row
per arm), `stress.jsonl` (emergency stress runs, one row per arm), `judge.jsonl` (the inference
judge, one row per judged run) and the operator's adjudication files in `sidecars/`. A trial's
current verdict is its last row under (run root, trial id), as the ledger defines it.

Columns: run (the run root's folder name), date, suite, arm, engine (commit), contract (the
`CLAUDE.md` blob), model, trials, passed, failed, other (invalid, aborted, or graded without a
pass/fail verdict; a judge row's unanswered trials; a stress trial counts clear as passed and
critical as failed), cost_usd (the sum of the sessions' reported
cost, the API-equivalent price whatever the billing; blank where none was logged), rulings (the
operator's rulings from a sidecar or the judge ledger). A judge row counts a trial with no flag as
passed and a flagged one as failed.
"""

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
OUT_NAME = "scores.csv"
COLUMNS = ["run", "date", "suite", "arm", "engine", "contract", "model", "trials", "passed",
           "failed", "other", "cost_usd", "rulings"]
# Worst first: the comparison's tiers (compare_oracles.TIER_ORDER), the judge's being a subset of them.
TIER_ORDER = ["harm", "practice", "task", "caution", "form", "none"]
RUN_TIME_KINDS = {None, "trial", "pilot_trial", "pilot_bridge_trial"}
PASS_FAIL = {"clear": "pass", "critical": "fail"}  # the stress test's two verdicts


def rows_of(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_name(row):
    """The run root's folder name; the oldest rows carry only the fixture path."""
    root = row.get("run_root") or (row.get("fixture") or "").split("/fixtures/")[0]
    return root.rstrip("/").rsplit("/", 1)[-1]


def short(rev):
    if not rev or rev == "worktree":
        return ""
    rev = rev.split("@", 1)[0]
    return rev[:7] if all(c in "0123456789abcdef" for c in rev) else rev


def joined(values):
    return "/".join(sorted({v for v in values if v}))


def cost(rows):
    logged = [r["total_cost_usd"] for r in rows if isinstance(r.get("total_cost_usd"), (int, float))]
    return "%.2f" % sum(logged) if logged else ""


def tally(verdicts):
    c = Counter(PASS_FAIL.get(v, v) for v in verdicts)
    return c["pass"], c["fail"], sum(n for v, n in c.items() if v not in ("pass", "fail"))


def tiers_text(counter, lead):
    parts = ["%s %d" % (t, counter[t]) for t in TIER_ORDER if counter.get(t)]
    return "%s: %s" % (lead, ", ".join(parts)) if parts else ""


def load_sidecars(folder):
    """`{run: {trial id: text}}` from both sidecar shapes: a list of grader-fail adjudications,
    and the comparison's `{trial: {check: {tier, reason}}}` map."""
    out = defaultdict(dict)
    for path in sorted(folder.glob("*.adjudications.json")) if folder.is_dir() else []:
        run = path.name[:-len(".adjudications.json")]
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data.get("adjudications"), list):
            for a in data["adjudications"]:
                out[run][a["trial_id"]] = "%s %s: %s" % (a["trial_id"], a.get("check", ""), a["ruling"])
        else:
            for trial, checks in data.items():
                tiers = {c.get("tier") for c in checks.values()}
                out[run][trial] = next((t for t in TIER_ORDER if t in tiers), "none")
    return out


def ruling_text(rulings, trials):
    """The sidecar rulings that fall on these trials, worded or counted by tier."""
    mine = [rulings[t] for t in sorted(trials) if t in rulings]
    tiers = Counter(r for r in mine if r in TIER_ORDER)
    words = [r for r in mine if r not in TIER_ORDER]
    return "; ".join(x for x in words + [tiers_text(tiers, "operator")] if x)


def trial_runs(rows, suite_of, arm_of, sidecars):
    """Rows of the trial ledgers, grouped by (run, arm); the current verdict is the last row."""
    groups = defaultdict(list)
    for r in rows:
        groups[run_name(r)].append(r)
    out = []
    for run, rs in groups.items():
        runtime = [r for r in rs if r.get("kind") in RUN_TIME_KINDS and r.get("trial_id")]
        meta = [r for r in rs if r.get("kind") in ("run", "pilot_run")]
        arm = {r["trial_id"]: arm_of(r) for r in runtime}
        last = {}
        for r in rs:
            if r.get("trial_id") and r.get("verdict"):
                last[r["trial_id"]] = r["verdict"]
        by_arm = defaultdict(list)
        for t in last:
            by_arm[arm.get(t, "")].append(t)
        if not last:  # a run that stopped before any session
            for m in meta:
                out.append({"run": run, "date": m.get("run_date") or m["ts"][:10],
                            "suite": suite_of(m) or "unrecorded", "arm": "", "engine": short(m.get("engine_rev")),
                            "contract": "", "model": m.get("model") or "", "trials": 0, "passed": 0,
                            "failed": 0, "other": 0, "cost_usd": "",
                            "rulings": m.get("verdict") or ""})
            continue
        for a, trials in by_arm.items():
            mine = [r for r in runtime if arm.get(r["trial_id"]) == a]
            passed, failed, other = tally(last[t] for t in trials)
            out.append({
                "run": run,
                "date": min(r.get("run_date") or r["ts"][:10] for r in mine or rs),
                "suite": joined(suite_of(r) for r in mine) or joined(suite_of(m) for m in meta) or "unrecorded",
                "arm": a,
                "engine": joined(short(r.get("engine_rev")) or short(r.get("stack_rev")) for r in mine)
                          or joined(short(m.get("engine_rev")) for m in meta),
                "contract": joined((r.get("arm_claude_md_blob") or r.get("keystone_blob") or "")[:7] for r in mine),
                "model": joined(r.get("resolved_model") for r in mine) or joined(m.get("model") for m in meta),
                "trials": len(trials), "passed": passed, "failed": failed, "other": other,
                "cost_usd": cost(mine),
                "rulings": ruling_text(sidecars.get(run, {}), trials),
            })
    return out


def judge_runs(rows):
    """One row per judged run; a later judge pass or ruling on the same trial supersedes."""
    tier, verdict, meta = defaultdict(dict), defaultdict(dict), defaultdict(list)
    for r in rows:
        run = run_name(r)
        if r.get("kind") == "judge":
            tier[run][r["trial_id"]] = r.get("tier")
            meta[run].append(r)
        elif r.get("kind") == "verdict":
            verdict[run][r["trial_id"]] = r.get("tier")
    out = []
    for run, tiers in tier.items():
        ms = meta[run]
        c = Counter(tiers.values())
        out.append({
            "run": run, "date": max(m["ts"][:10] for m in ms), "suite": "judge", "arm": "",
            "engine": short(ms[-1].get("engine_rev")), "contract": "",
            "model": joined(m.get("resolved_model") for m in ms),
            "trials": len(tiers), "passed": c["none"],
            "failed": sum(n for t, n in c.items() if t in TIER_ORDER and t != "none"),
            "other": sum(n for t, n in c.items() if t not in TIER_ORDER),
            "cost_usd": cost(ms),
            "rulings": tiers_text(Counter(verdict[run].values()), "operator"),
        })
    return out


def build(results=RESULTS):
    sidecars = load_sidecars(results / "sidecars")
    out = []
    out += trial_runs(rows_of(results / "log.jsonl"), lambda r: r.get("run_mode"), lambda r: "", sidecars)
    out += trial_runs(rows_of(results / "compare.jsonl"),
                      lambda r: r.get("run_mode") or r.get("suite") or "compare",
                      lambda r: r.get("arm") or "", sidecars)
    out += trial_runs(rows_of(results / "stress.jsonl"), lambda r: "stress",
                      lambda r: r.get("arm") or "", sidecars)
    out += judge_runs(rows_of(results / "judge.jsonl"))
    out.sort(key=lambda r: (r["date"], r["run"], r["suite"] == "judge", r["suite"], r["arm"]))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(out)
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if scores.csv is stale")
    ap.add_argument("--results", type=Path, default=RESULTS, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    text = build(args.results)
    target = args.results / OUT_NAME
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current != text:
            print("scores.csv is stale: run `python3 -m evals.harness.scores`", file=sys.stderr)
            return 1
        print("scores.csv is current")
        return 0
    target.write_text(text, encoding="utf-8")
    print("wrote %s (%d runs)" % (target.name, text.count("\n") - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
