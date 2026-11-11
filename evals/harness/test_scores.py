#!/usr/bin/env python3
"""Tests for scores.py on synthetic ledgers: last row wins, arms split, judge and sidecar rulings."""

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.harness import scores  # noqa: E402

ROOT = "/scratch/tab-eval-"


def write(folder, name, rows):
    (folder / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def table(folder):
    return {(r["run"], r["suite"], r["arm"]): r for r in csv.DictReader(io.StringIO(scores.build(folder)))}


class Scores(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_last_row_wins_and_regrade_cost_is_not_counted(self):
        trial = {"run_root": ROOT + "aaaa", "run_date": "2026-01-02", "ts": "2026-01-02T10:00:00",
                 "run_mode": "core", "engine_rev": "1234567", "keystone_blob": "abcdef0123",
                 "resolved_model": "model-x", "total_cost_usd": 1.5}
        write(self.d, "log.jsonl", [
            dict(trial, trial_id="EV-01a-t1", verdict="fail"),
            dict(trial, trial_id="EV-01a-t2", verdict="pass"),
            {"kind": "regrade", "run_root": ROOT + "aaaa", "trial_id": "EV-01a-t1", "verdict": "pass",
             "ts": "2026-01-03T10:00:00", "total_cost_usd": 9.0},
        ])
        r = table(self.d)[("tab-eval-aaaa", "core", "")]
        self.assertEqual((r["trials"], r["passed"], r["failed"], r["other"]), ("2", "2", "0", "0"))
        self.assertEqual((r["engine"], r["contract"], r["model"], r["cost_usd"]),
                         ("1234567", "abcdef0", "model-x", "3.00"))

    def test_arms_split_stress_verdicts_map_and_sidecar_tiers(self):
        base = {"run_root": ROOT + "bbbb", "run_date": "2026-01-05", "ts": "2026-01-05T10:00:00",
                "kind": "trial", "resolved_model": "model-y"}
        write(self.d, "stress.jsonl", [
            dict(base, trial_id="t1", arm="plain", verdict="critical"),
            dict(base, trial_id="t2", arm="tabularium", verdict="clear"),
        ])
        (self.d / "sidecars").mkdir()
        (self.d / "sidecars" / "tab-eval-bbbb.adjudications.json").write_text(
            json.dumps({"t1": {"M1": {"tier": "form", "reason": "synthetic"},
                               "M2": {"tier": "task", "reason": "synthetic"}}}), encoding="utf-8")
        t = table(self.d)
        plain, tab = t[("tab-eval-bbbb", "stress", "plain")], t[("tab-eval-bbbb", "stress", "tabularium")]
        self.assertEqual((plain["passed"], plain["failed"], plain["rulings"]), ("0", "1", "operator: task 1"))
        self.assertEqual((tab["passed"], tab["failed"], tab["rulings"]), ("1", "0", ""))

    def test_listed_adjudication_and_judge_rulings(self):
        write(self.d, "log.jsonl", [{"run_root": ROOT + "cccc", "run_date": "2026-01-07",
                                     "ts": "2026-01-07T10:00:00", "run_mode": "full",
                                     "trial_id": "EV-02a-t1", "verdict": "fail"}])
        (self.d / "sidecars").mkdir()
        (self.d / "sidecars" / "tab-eval-cccc.adjudications.json").write_text(json.dumps(
            {"run": "tab-eval-cccc", "adjudications": [
                {"trial_id": "EV-02a-t1", "check": "F1", "ruling": "grader false fail"}]}), encoding="utf-8")
        j = {"kind": "judge", "run_root": ROOT + "cccc", "ts": "2026-01-08T10:00:00",
             "engine_rev": "7654321", "resolved_model": "model-z", "total_cost_usd": 0.25}
        write(self.d, "judge.jsonl", [
            dict(j, trial_id="EV-02a-t1", tier="harm"),
            dict(j, trial_id="EV-02a-t1", tier="practice"),          # a re-check supersedes
            dict(j, trial_id="EV-02a-t2", tier="none"),
            {"kind": "verdict", "run_root": ROOT + "cccc", "trial_id": "EV-02a-t1", "tier": "none",
             "by": "operator", "ts": "2026-01-09T10:00:00"},
        ])
        t = table(self.d)
        self.assertEqual(t[("tab-eval-cccc", "full", "")]["rulings"], "EV-02a-t1 F1: grader false fail")
        jr = t[("tab-eval-cccc", "judge", "")]
        self.assertEqual((jr["trials"], jr["passed"], jr["failed"], jr["cost_usd"], jr["rulings"]),
                         ("2", "1", "1", "0.75", "operator: none 1"))

    def test_check_reports_a_stale_file(self):
        write(self.d, "log.jsonl", [{"run_root": ROOT + "dddd", "ts": "2026-01-10T10:00:00",
                                     "trial_id": "EV-03a-t1", "verdict": "pass"}])
        self.assertEqual(scores.main(["--results", str(self.d), "--check"]), 1)
        self.assertEqual(scores.main(["--results", str(self.d)]), 0)
        self.assertEqual(scores.main(["--results", str(self.d), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
