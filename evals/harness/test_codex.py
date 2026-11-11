"""Codex host's offline refusals and shared fixture integration; no CLI sessions."""

import contextlib
import datetime
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evals.harness import codex, run_eval


class RefusalTests(unittest.TestCase):
    def test_api_credentials_refused_by_name_without_value(self):
        for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "AZURE_OPENAI_API_KEY",
                     "OPENAI_ACCESS_TOKEN", "ANTHROPIC_API_KEY"):
            with self.subTest(name=name), patch.object(codex, "containment_selftest") as probe:
                with self.assertRaises(codex.CodexUnavailable) as caught:
                    codex.require_enabled(environ={name: "synthetic-secret"})
                self.assertIn(name, str(caught.exception))
                self.assertNotIn("synthetic-secret", str(caught.exception))
                probe.assert_not_called()

    def test_empty_api_key_is_not_a_credential(self):
        codex.check_credentials({"OPENAI_API_KEY": "", "PATH": "/synthetic/bin"})

    def test_override_does_not_bypass_failed_containment(self):
        with patch.object(codex, "containment_selftest", return_value={"proven": False}) as probe:
            with self.assertRaisesRegex(codex.CodexUnavailable, "read confinement"):
                codex.require_enabled(environ={"OPENAI_API_KEY": "synthetic"}, allow_api_key=True)
            probe.assert_called_once_with()

    def test_default_probe_is_explicitly_unproven_and_untried(self):
        result = codex.containment_selftest()
        self.assertIs(result["proven"], False)
        self.assertEqual(result["attempts"], 0)
        self.assertFalse(result["attempted_read"])
        self.assertFalse(result["attempted_write"])
        self.assertEqual(result["read_canary"], "not-run")

    def test_claimed_probe_success_cannot_enable_missing_launcher(self):
        with patch.object(codex, "containment_selftest", return_value={"proven": True}):
            with self.assertRaises(codex.CodexUnavailable):
                codex.require_enabled(environ={})

    def test_run_refuses_before_side_effects(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(run_eval, "paid_run_root") as paid, \
                patch.object(run_eval.session, "make_clean_config") as config, \
                patch.object(run_eval, "log_trial") as ledger, \
                patch.object(run_eval.archive, "archive_run") as archive, \
                patch.object(run_eval.subprocess, "run") as process, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(run_eval.main(["--host", "codex"]), 2)
            for mocked in (paid, config, ledger, archive, process):
                mocked.assert_not_called()
            self.assertIn("DISABLED", err.getvalue())

    def test_failed_probe_refuses_before_paid_root(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(codex, "containment_selftest", return_value={"proven": False}), \
                patch.object(run_eval, "paid_run_root") as paid, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run_eval.main(["--host", "codex"]), 2)
            paid.assert_not_called()

    def test_direct_session_and_trial_cannot_bypass_refusal(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(run_eval, "prepare_trial") as prepare:
            with self.assertRaises(codex.CodexUnavailable):
                codex.run_session("/synthetic", "task", None, "/synthetic/log")
            with self.assertRaises(codex.CodexUnavailable):
                run_eval.run_trial(SimpleNamespace(host="codex"), {}, "synthetic")
            with self.assertRaises(codex.CodexUnavailable):
                run_eval.run_suite(run_eval.parse_args(["--host", "codex"]), "core", [])
            prepare.assert_not_called()


class OfflineTests(unittest.TestCase):
    def test_estimate_uses_same_trial_plan_without_auth_ledger_or_scratch(self):
        with patch.object(run_eval, "priced_rows") as ledger, \
                patch.object(run_eval, "make_run_root") as scratch, \
                patch.object(codex, "require_enabled") as auth, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(run_eval.main(["--host", "codex", "--estimate"]), 0)
            for mocked in (ledger, scratch, auth):
                mocked.assert_not_called()
        self.assertIn("20 trial(s)", out.getvalue())
        self.assertIn("200 minutes", out.getvalue())
        self.assertIn("Codex plan/quota", out.getvalue())
        self.assertIn("unmeasured", out.getvalue())
        self.assertNotIn("$", out.getvalue())

    def test_estimate_targeted_counts_and_invalid_arguments(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(run_eval.main(["--host", "codex", "--estimate", "--variants",
                                            "EV-01a,EV-03a", "--trials", "7"]), 0)
        self.assertIn("14 trial(s)", out.getvalue())
        for args in (["--trials", "0"], ["--full", "--variants", "EV-01a"],
                     ["--variants", "UNKNOWN"]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                run_eval.main(["--host", "codex", "--estimate"] + args)

    def test_exec_argv_is_noninteractive_task_is_single_literal_argument(self):
        task = "Synthetic task with $(literal) and `literal`"
        argv = codex.exec_argv("/synthetic/trial root", task, "/synthetic/last.txt", "synthetic-model")
        self.assertEqual(argv[:9], ["codex", "exec", "--json", "-s", "workspace-write", "-C",
                                    "/synthetic/trial root", "--ephemeral", "-o"])
        self.assertEqual(argv[-2:], ["--", task])
        self.assertIn("sandbox_workspace_write.network_access=false", argv)
        self.assertIn('web_search="disabled"', argv)
        self.assertIn('forced_login_method="chatgpt"', argv)

    def test_shared_fixture_bytes_plus_two_codex_surfaces_before_scan_and_snapshot(self):
        today = datetime.date(2031, 3, 14)
        manifest = run_eval.manifest_for("EV-01a", today)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scanned = []
            def scan(_label, tree, _task):
                scanned.append((tree / "AGENTS.md").read_bytes())
                self.assertEqual((tree / "EVAL-MODE.md").read_bytes(), b"synthetic note\n")
            ctx = SimpleNamespace(run_root=root, today=today, host="codex",
                                  keystone=b"synthetic contract\n", addendum=b"synthetic note\n",
                                  containment=SimpleNamespace(scan_trial=scan))
            with patch.object(run_eval, "guard_check", return_value=(0, "green")), \
                    patch.object(run_eval.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
                state, error = run_eval.prepare_trial(ctx, manifest, "synthetic")
            self.assertIsNone(error)
            self.assertEqual(scanned, [codex.ENTRY_BYTES])
            tree, pre = state["fixture_dir"], state["pre_dir"]
            self.assertEqual((tree / "CLAUDE.md").read_bytes(), ctx.keystone)
            for name in ("AGENTS.md", "EVAL-MODE.md", "CLAUDE.md",
                         "_templates/person/med/sources/README.md"):
                self.assertEqual((tree / name).read_bytes(), (pre / name).read_bytes())
            shared = root / "shared"
            run_eval.build_fixture_tree(shared, manifest, ctx.keystone, ctx.addendum, today, "shared")
            def files(folder):
                return {p.relative_to(folder).as_posix(): p.read_bytes()
                        for p in folder.rglob("*") if p.is_file()}
            codex_files = files(tree)
            self.assertEqual(codex_files.pop("AGENTS.md"), codex.ENTRY_BYTES)
            self.assertEqual(codex_files.pop("EVAL-MODE.md"), ctx.addendum)
            self.assertEqual(codex_files, files(shared))

    def test_handout_note_replaces_default_note_without_changing_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_bytes(b"synthetic contract\n")
            codex.prepare_fixture(root, "synthetic verifier note\n")
            self.assertEqual((root / "CLAUDE.md").read_bytes(), b"synthetic contract\n")
            self.assertEqual((root / "EVAL-MODE.md").read_bytes(), b"synthetic verifier note\n")


if __name__ == "__main__":
    unittest.main()
