#!/usr/bin/env python3
"""Synthetic suite for tools/interview_capture — invented transcripts and people only.

    python3 tools/interview_capture/test_interview_capture.py
    python3 -m unittest tools.interview_capture.test_interview_capture

The mutation proofs: a retyped or altered answer in the filed file is caught by `verify` with and
without the transcript (every answer, every position class), and a retyped quotation in the profile
is caught by `quotes`.
"""
import datetime
import hashlib
import io
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools import interview_capture as ic  # noqa: E402
from tools.interview_capture.__main__ import main  # noqa: E402
from tools.person_ownership import fsverify  # noqa: E402

PID = "0123456789abcdef0123456789abcdef"
SID = "11111111-2222-3333-4444-555555555555"
HANDLE = "evalperson-a"

# Answers chosen to break naive handling: commas in "Other" text, a backtick run, a fence-like line,
# a heading-like line, CRLF, leading and trailing spaces, a trailing newline, Polish diacritics.
TRICKY = [
    "Rano 5 mg, wieczorem 2,5 mg, czasem pomija",
    "Mówi: „boli mnie w krzyżu”, od wtorku",
    "```\nnot a fence\n````",
    "### 9.9 · not a question\nsecond line",
    "line one\r\nline two",
    "  leading and trailing  ",
    "ends with a newline\n",
    "",
]


def _ask(tid, questions, ts="2026-10-18T10:00:00.000Z", sidechain=False):
    return {"parentUuid": "p", "isSidechain": sidechain, "type": "assistant", "timestamp": ts,
            "sessionId": SID, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": tid, "name": "AskUserQuestion",
                 "input": {"questions": questions}}]}}


def _answer(tid, questions, answers, ts="2026-10-18T10:01:00.000Z", annotations=None, error=False):
    tur = {"questions": questions, "answers": answers}
    if annotations:
        tur["annotations"] = annotations
    return {"parentUuid": "p", "isSidechain": False, "type": "user", "timestamp": ts,
            "sessionId": SID, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tid, "content": "User has answered.",
                 "is_error": error}]},
            "toolUseResult": "Error: the user declined" if error else tur}


def _q(text, header="Hdr", multi=False, labels=("Yes", "No")):
    return {"question": text, "header": header, "multiSelect": multi,
            "options": [{"label": l, "description": "about " + l} for l in labels]}


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write_transcript(path, records):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


class Base(unittest.TestCase):
    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "Etc/GMT-3"
        time.tzset()
        self.root = tempfile.mkdtemp(prefix="icap-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.cfg = os.path.join(self.root, "_client")
        self.tdir = os.path.join(self.cfg, "projects", "-care")
        os.makedirs(self.tdir)
        self.transcript = os.path.join(self.tdir, SID + ".jsonl")
        pdir = os.path.join(self.root, "patients", HANDLE)
        os.makedirs(os.path.join(pdir, "med", "sources"))
        with open(os.path.join(pdir, "profile.md"), "w", encoding="utf-8") as fh:
            fh.write("# profile\n## Identity\n- **Person record ID (local-only):** `%s`\n" % PID)
        self.pdir = pdir

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def standard(self, extra=()):
        q1 = [_q("Which doses now?", "Doses"),
              _q("Which symptoms?", "Symptoms", multi=True, labels=("Pain", "Fever", "None"))]
        q2 = [_q("Tricky %d?" % i, "T%d" % i) for i in range(len(TRICKY))]
        recs = [_ask("toolu_A", q1, "2026-10-18T09:59:00.000Z"),
                _answer("toolu_A", q1, {"Which doses now?": TRICKY[0],
                                        "Which symptoms?": ["Pain", "Fever, mostly at night"]},
                        "2026-10-18T10:00:00.000Z",
                        annotations={"Which doses now?": {"notes": "they checked the box"}}),
                _ask("toolu_B", q2, "2026-10-18T10:05:00.000Z"),
                _answer("toolu_B", q2, {"Tricky %d?" % i: a for i, a in enumerate(TRICKY)},
                        "2026-10-18T10:06:00.000Z")]
        _write_transcript(self.transcript, recs + list(extra))
        return recs

    def file(self, handle=HANDLE, transcript=None, **kw):
        r = ic.file_interview(self.root, handle, transcript or self.transcript, **kw)
        return r["path"], r["calls"]

    def person(self, handle, pid):
        pdir = os.path.join(self.root, "patients", handle)
        os.makedirs(os.path.join(pdir, "med", "sources"))
        with open(os.path.join(pdir, "profile.md"), "w", encoding="utf-8") as fh:
            fh.write("# profile\n## Identity\n- **Person record ID (local-only):** `%s`\n" % pid)
        return pdir

    def manifest(self, pdir=None):
        with open(os.path.join(pdir or self.pdir, "med", "MANIFEST"), encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def l13(self):
        findings, _ = fsverify.verify_tree(self.root)
        return findings


class ReadCalls(Base):
    def test_answers_lists_notes_and_other_text_with_commas(self):
        self.standard()
        calls = ic.read_calls(self.transcript)
        self.assertEqual([c["status"] for c in calls], ["answered", "answered"])
        items = ic.canonical(calls)
        self.assertEqual(items[0], ["1.1", "Which doses now?", [TRICKY[0]], "they checked the box"])
        # a several-choice answer stays a list; typed text with a comma is never split
        self.assertEqual(items[1][2], ["Pain", "Fever, mostly at night"])
        self.assertEqual([it[2] for it in items[2:]], [[a] for a in TRICKY])

    def test_declined_duplicate_unmatched_and_sidechain_calls(self):
        q = [_q("Same?"), _q("Same?")]
        _write_transcript(self.transcript, [
            _ask("toolu_X", [_q("Declined?")]), _answer("toolu_X", [], {}, error=True),
            _ask("toolu_D", q), _answer("toolu_D", q, {"Same?": "Yes"}),
            _ask("toolu_U", [_q("Asked?")]), _answer("toolu_U", [], {"Something else?": "Yes"}),
            _ask("toolu_S", [_q("Side?")], sidechain=True), _answer("toolu_S", [], {"Side?": "Yes"}),
            _ask("toolu_N", [_q("Never answered?")])])
        calls = ic.read_calls(self.transcript)
        self.assertEqual([(c["tool_use_id"], c["status"]) for c in calls],
                         [("toolu_X", "unanswered"), ("toolu_D", "duplicate-question"),
                          ("toolu_U", "answer-without-question"), ("toolu_N", "unanswered")])
        with self.assertRaises(ic.CaptureError):
            self.file()
        with self.assertRaises(ic.CaptureError):
            self.file(numbers=[2])

    def test_a_single_string_answer_to_a_several_choice_question_is_kept_whole(self):
        q = [_q("Which?", multi=True, labels=("Pain", "Fever"))]
        _write_transcript(self.transcript, [_ask("toolu_A", q),
                                            _answer("toolu_A", q, {"Which?": "Pain, Fever"})])
        path, _ = self.file()
        _, items = ic.parse_file(_read(path))
        self.assertEqual(items[0][2], ["Pain, Fever"])
        self.assertIn("as given; may join several choices", _read(path))


class FileAndRegister(Base):
    def test_files_word_for_word_names_by_local_date_and_inits_the_ledger(self):
        self.standard()
        path, calls = self.file()
        self.assertEqual(os.path.basename(path), "2026-10-18__interview__on-screen.md")
        self.assertEqual(os.path.dirname(path),
                         os.path.join(self.pdir, "med", "sources", "interviews"))
        text = _read(path)
        fm, items = ic.parse_file(text)
        self.assertEqual(items, ic.canonical(calls))          # every block reads back exactly
        self.assertEqual(fm["session"], SID.replace("-", ""))
        self.assertEqual(fm["calls"], "toolu_A toolu_B")
        self.assertTrue(os.path.isfile(os.path.join(self.pdir, "med", "MANIFEST")))
        self.assertEqual(self.l13(), [])

    def test_local_date_not_utc_date_names_the_file(self):
        q = [_q("Late?")]
        _write_transcript(self.transcript, [
            _ask("toolu_L", q, "2026-10-18T22:30:00.000Z"),
            _answer("toolu_L", q, {"Late?": "Yes"}, "2026-10-18T22:31:00.000Z")])
        path, _ = self.file()
        self.assertTrue(os.path.basename(path).startswith("2026-10-19__"))   # Etc/GMT-3 is UTC+3

    def test_appends_when_a_ledger_exists_and_never_files_a_call_twice(self):
        self.standard()
        self.file(numbers=[1])
        p2, calls = self.file()                     # only call 2 is left
        self.assertEqual([c["n"] for c in calls], [2])
        self.assertTrue(p2.endswith("2026-10-18__interview__on-screen__2.md"))
        self.assertEqual(self.l13(), [])
        with self.assertRaises(ic.CaptureError):
            self.file()
        with self.assertRaises(ic.CaptureError):
            self.file(numbers=[1])

    def test_window_selects_by_answer_time(self):
        self.standard()
        _, calls = self.file(since="2026-10-18T12:03+02:00")
        self.assertEqual([c["n"] for c in calls], [2])

    def test_a_ledger_refusal_leaves_no_file(self):
        self.standard()
        self.file(numbers=[1])
        stray = os.path.join(self.pdir, "med", "sources", "other", "2026-10-01__x__stray.pdf")
        os.makedirs(os.path.dirname(stray))
        with open(stray, "wb") as fh:
            fh.write(b"not inventoried")
        before = sorted(os.listdir(os.path.join(self.pdir, "med", "sources", "interviews")))
        with self.assertRaises(Exception) as cm:
            self.file()
        self.assertIsInstance(cm.exception, ic.LedgerRefused)
        self.assertEqual(sorted(os.listdir(os.path.join(self.pdir, "med", "sources", "interviews"))),
                         before)

    def test_refuses_an_unknown_person_and_a_bad_slug(self):
        self.standard()
        with self.assertRaises(ic.CaptureError):
            ic.file_interview(self.root, "nobody", self.transcript)
        with self.assertRaises(ic.CaptureError):
            self.file(slug="../x")
        self.assertFalse(os.path.exists(os.path.join(self.pdir, "med", "sources", "interviews")))


class VerifyMutations(Base):
    def setUp(self):
        super().setUp()
        self.standard()
        self.path, _ = self.file(do_register=False)
        self.text = _read(self.path)

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def test_clean_file_verifies_against_the_transcript(self):
        problems, notes = ic.verify(self.path, config_dir=self.cfg)
        self.assertEqual(problems, [])
        self.assertIn("byte-identical to a fresh copy of the transcript", notes)

    def test_every_answer_altered_or_retyped_is_caught_with_and_without_the_transcript(self):
        _, items = ic.parse_file(self.text)
        answers = [a for it in items for a in it[2] if a]
        self.assertGreaterEqual(len(answers), 8)
        gone = os.path.join(self.root, "_nowhere")
        for a in answers:
            for mutated in (a[:-1] + chr(ord(a[-1]) ^ 1), a + " ", " " + a,
                            a.replace(",", "", 1) if "," in a else a + "."):
                fence_body = "answer\n" + a + "\n"
                self.assertIn(fence_body, self.text)
                self.write(self.text.replace(fence_body, "answer\n" + mutated + "\n", 1))
                with_t, _ = ic.verify(self.path, config_dir=self.cfg)
                without_t, notes = ic.verify(self.path, config_dir=gone)
                self.assertTrue(with_t, (a, mutated))
                self.assertTrue(without_t, (a, mutated))
                self.assertTrue(any("no longer on disk" in n for n in notes))
        self.write(self.text)
        self.assertEqual(ic.verify(self.path, config_dir=self.cfg)[0], [])

    def test_a_spell_corrected_answer_is_caught(self):
        self.write(self.text.replace("czasem pomija", "czasami pomija"))
        self.assertTrue(ic.verify(self.path, config_dir=self.cfg)[0])

    def test_an_edit_outside_the_answers_is_caught_only_against_the_transcript(self):
        self.write(self.text.replace("about Yes", "about yes", 1))
        self.assertTrue(ic.verify(self.path, config_dir=self.cfg)[0])
        # ... and only there: without the transcript the file's own hash covers the answers alone.
        self.assertEqual(ic.verify(self.path, config_dir=os.path.join(self.root, "_nowhere"))[0], [])

    def test_an_altered_transcript_line_is_caught(self):
        with open(self.transcript, encoding="utf-8") as fh:
            body = fh.read()
        with open(self.transcript, "w", encoding="utf-8") as fh:
            fh.write(body.replace("czasem pomija", "czasami pomija"))
        problems, _ = ic.verify(self.path, config_dir=self.cfg)
        self.assertTrue(any("transcript lines differ" in p for p in problems))


class Quotes(Base):
    def setUp(self):
        super().setUp()
        self.standard()
        self.path, _ = self.file(do_register=False)
        self.stem = os.path.basename(self.path)[:-3]

    def profile(self, *lines):
        with open(os.path.join(self.pdir, "profile.md"), "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def test_exact_and_excerpted_quotations_pass(self):
        self.profile('- Doses: "Rano 5 mg, wieczorem 2,5 mg, czasem pomija" (operator, %s, B)' % self.stem,
                     "- Pain: „boli mnie w krzyżu” (operator, %s.md, B)" % self.stem,
                     '- Excerpt: "Rano 5 mg … czasem pomija" (%s, B)' % self.stem)
        failures, checked, _, _ = ic.check_quotes(self.root, HANDLE)
        self.assertEqual((failures, checked), ([], 3))

    def test_a_retyped_quotation_is_caught(self):
        for bad in ('"Rano 5 mg, wieczorem 2,5 mg, czasami pomija"',     # spell-corrected
                    '"Rano 5 mg, wieczorem 2.5 mg, czasem pomija"',      # normalised number
                    '"rano 5 mg, wieczorem 2,5 mg, czasem pomija"',      # capitalisation
                    '"in the morning 5 mg"',                              # paraphrase / translation
                    '"Which doses now?"',                                 # a question, not an answer
                    '"czasem pomija … Rano 5 mg"'):                       # fragments out of order
            with open(os.path.join(self.pdir, "profile.md"), "w", encoding="utf-8") as fh:
                fh.write("- Doses: %s (operator, %s, B)\n" % (bad, self.stem))
            failures, checked, _, _ = ic.check_quotes(self.root, HANDLE)
            self.assertEqual((len(failures), checked), (1, 1), bad)

    def test_a_missing_file_fails_and_a_sheet_era_file_is_skipped(self):
        sheet = os.path.join(self.pdir, "med", "sources", "interviews",
                             "2026-09-01__interview__clinic-review.md")
        with open(sheet, "w", encoding="utf-8") as fh:
            fh.write("---\nperson: x\n---\n# sheet\n→ Answer: tak\n")
        self.profile('- A: "tak" (2026-09-01__interview__clinic-review, B)',
                     '- B: "tak" (2026-09-02__interview__missing, B)',
                     '- C: "uncited quotation" (operator 2026-10-18, B)')
        failures, checked, skipped, unquoted = ic.check_quotes(self.root, HANDLE)
        self.assertEqual((len(failures), checked, skipped, unquoted), (1, 1, 1, 0))
        self.assertIn("not in med/sources/interviews/", failures[0])


class RedTeamFindings(Base):
    """One test per finding of the 2026-10-19 red-team round."""

    def test_another_persons_calls_never_land_in_a_file(self):
        self.standard()
        other = self.person("evalperson-b", "fedcba9876543210fedcba9876543210")
        self.file(numbers=[1])
        with self.assertRaises(ic.CaptureError) as cm:            # the default, once a session held two
            self.file(handle="evalperson-b")
        self.assertIn("--call", str(cm.exception))
        with self.assertRaises(ic.CaptureError) as cm:
            self.file(handle="evalperson-b", numbers=[1])
        self.assertIn("for another person", str(cm.exception))
        path, calls = self.file(handle="evalperson-b", numbers=[2])
        self.assertEqual([c["n"] for c in calls], [2])
        self.assertTrue(path.startswith(other))
        self.assertEqual(self.l13(), [])

    def test_a_resumed_session_never_files_the_same_call_twice(self):
        self.standard()
        self.file()
        resumed = os.path.join(self.tdir, "66666666-7777-8888-9999-000000000000.jsonl")
        shutil.copy(self.transcript, resumed)
        with self.assertRaises(ic.CaptureError):
            self.file(transcript=resumed)
        with self.assertRaises(ic.CaptureError):
            self.file(transcript=resumed, numbers=[1])

    def test_an_interrupted_filing_is_completed_on_the_next_run(self):
        self.standard()
        self.file(numbers=[1])
        orphan, _ = self.file(numbers=[2], do_register=False)    # written, never inventoried
        self.assertTrue(self.l13())                               # L13 red, as after a crash
        r = ic.file_interview(self.root, HANDLE, self.transcript)
        self.assertEqual(r["path"], None)
        self.assertEqual(r["recovered"], [os.path.relpath(orphan, self.pdir)])
        self.assertEqual(self.l13(), [])

    def test_an_interrupted_filing_altered_since_is_not_inventoried(self):
        self.standard()
        self.file(numbers=[1])
        orphan, _ = self.file(numbers=[2], do_register=False)
        text = _read(orphan)
        with open(orphan, "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace("czasem", "czasami"))
        with self.assertRaises(ic.CaptureError) as cm:
            ic.file_interview(self.root, HANDLE, self.transcript)
        self.assertIn("ask the operator", str(cm.exception))

    def test_a_ledger_refusal_never_names_the_removed_file(self):
        self.standard()
        self.file(numbers=[1])
        stray = os.path.join(self.pdir, "med", "sources", "other", "2026-10-01__x__stray.pdf")
        os.makedirs(os.path.dirname(stray))
        with open(stray, "wb") as fh:
            fh.write(b"not inventoried")
        with self.assertRaises(ic.LedgerRefused) as cm:
            self.file()
        self.assertNotIn("interviews/", str(cm.exception))

    def test_a_first_ledger_keeps_confirmed_and_counts_what_it_took_in(self):
        self.standard()
        lab = os.path.join(self.pdir, "med", "sources", "labs", "2026-09-01__lab__x.pdf")
        os.makedirs(os.path.dirname(lab))
        with open(lab, "wb") as fh:
            fh.write(b"lab")
        r = ic.file_interview(self.root, HANDLE, self.transcript, confirmed=True)
        self.assertEqual(r["swept_in"], 1)
        rel = os.path.relpath(r["path"], self.pdir)
        mine = [rec for rec in self.manifest() if rec.get("source_relpath") == rel]
        self.assertIn("operator-confirmed", json.dumps(mine[-1]))
        self.assertEqual(self.l13(), [])

    def test_verify_does_not_depend_on_the_machine_timezone(self):
        self.standard()
        path, _ = self.file(do_register=False)
        os.environ["TZ"] = "UTC"
        time.tzset()
        self.assertEqual(ic.verify(path, config_dir=self.cfg)[0], [])
        os.environ["TZ"] = "America/Los_Angeles"
        time.tzset()
        self.assertEqual(ic.verify(path, config_dir=self.cfg)[0], [])

    def test_until_a_bare_date_runs_to_the_end_of_that_day(self):
        self.standard()
        _, calls = self.file(until="2026-10-18")
        self.assertEqual([c["n"] for c in calls], [1, 2])

    def test_an_unfilable_call_is_reported_not_silently_dropped(self):
        q = [_q("Same?"), _q("Same?")]
        _write_transcript(self.transcript, [
            _ask("toolu_D", q), _answer("toolu_D", q, {"Same?": "Yes"}),
            _ask("toolu_G", [_q("Good?")]), _answer("toolu_G", [], {"Good?": "Yes"})])
        r = ic.file_interview(self.root, HANDLE, self.transcript)
        self.assertEqual([c["n"] for c in r["calls"]], [2])
        self.assertEqual([c["n"] for c in r["skipped"]], [1])
        _write_transcript(self.transcript, [_ask("toolu_E", q), _answer("toolu_E", q, {"Same?": "No"})])
        with self.assertRaises(ic.CaptureError) as cm:
            ic.file_interview(self.root, HANDLE, self.transcript)
        self.assertIn("cannot be told apart", str(cm.exception))

    def test_compliant_quotations_in_other_forms_pass(self):
        q = [_q("Since when?"), _q("How?")]
        nfd = unicodedata.normalize("NFD", "żółć w nocy")
        _write_transcript(self.transcript, [
            _ask("toolu_Q", q), _answer("toolu_Q", q, {"Since when?": "od 2001 roku,\nrano gorzej",
                                                       "How?": nfd + "\u00a0bardzo"})])
        path, _ = self.file(do_register=False)
        stem = os.path.basename(path)[:-3]
        with open(os.path.join(self.pdir, "profile.md"), "a", encoding="utf-8") as fh:
            fh.write('- (operator, %s, B): "od 2001 roku"\n' % stem)               # after the citation
            fh.write('- „od 2001 roku" (%s, B)\n' % stem)                            # straight close
            fh.write("- ‘rano gorzej’ (%s, B)\n" % stem)
            fh.write('- "od 2001 roku, rano gorzej" (%s, B)\n' % stem)              # two lines as one
            fh.write('- "żółć w nocy bardzo" (%s, B)\n' % stem)                     # NFC + plain space
            fh.write('- "od 2001 roku." (%s, B)\n' % stem)                          # full stop inside
            fh.write('- "…" (%s, B)\n' % stem)                                      # not a quotation
            fh.write("- paraphrase: since 2001 (%s, B)\n" % stem)
        failures, checked, _, unquoted = ic.check_quotes(self.root, HANDLE)
        self.assertEqual((failures, checked, unquoted), ([], 6, 1))


class RedTeamRound2(Base):
    """One test per finding of the second red-team round, 2026-10-19."""

    def test_a_default_run_first_in_a_record_of_several_people_refuses(self):
        self.standard()
        self.person("evalperson-b", "fedcba9876543210fedcba9876543210")
        with self.assertRaises(ic.CaptureError) as cm:
            self.file(handle="evalperson-b")
        self.assertIn("--all", str(cm.exception))
        r = ic.file_interview(self.root, HANDLE, self.transcript, take_all=True)
        self.assertEqual([c["n"] for c in r["calls"]], [1, 2])

    def test_all_refuses_once_a_call_of_the_session_is_filed_for_another_person(self):
        self.standard()
        self.person("evalperson-b", "fedcba9876543210fedcba9876543210")
        self.file(numbers=[1])
        with self.assertRaises(ic.CaptureError) as cm:
            self.file(handle="evalperson-b", take_all=True)
        self.assertIn("already filed for another person", str(cm.exception))

    def test_an_orphan_naming_another_person_or_holding_a_call_filed_elsewhere_refuses(self):
        self.standard()
        other = self.person("evalperson-b", "fedcba9876543210fedcba9876543210")
        mine, _ = self.file(numbers=[1], take_all=True)
        os.makedirs(os.path.join(other, "med", "sources", "interviews"))
        stray = os.path.join(other, "med", "sources", "interviews", "2026-10-18__interview__x.md")
        shutil.copy(mine, stray)                       # a's file copied into b's folder by mistake
        with self.assertRaises(ic.CaptureError) as cm:
            self.file(handle="evalperson-b", numbers=[2])
        self.assertIn("names another person", str(cm.exception))
        with open(stray, encoding="utf-8") as fh:
            text = fh.read()
        with open(stray, "w", encoding="utf-8") as fh:
            fh.write(text.replace("person: " + HANDLE, "person: evalperson-b"))
        with self.assertRaises(ic.CaptureError) as cm:
            self.file(handle="evalperson-b", numbers=[2])
        self.assertIn("ask the operator", str(cm.exception))

    def _damaged_refuses(self, ledger):
        self.standard()
        if ledger:
            self.file(numbers=[1])
        folder = os.path.join(self.pdir, "med", "sources", "interviews")
        os.makedirs(folder, exist_ok=True)
        bad = os.path.join(folder, "2026-10-17__interview__cut.md")
        for body in ("", "---\ncapture: on-screen questions\n---\n```answer\ncut off"):
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write(body)
            with self.assertRaises(ic.CaptureError) as cm:
                self.file(numbers=[2])
            self.assertIn("ask the operator", str(cm.exception))
            self.assertEqual(os.path.exists(os.path.join(self.pdir, "med", "MANIFEST")), ledger)

    def test_an_empty_or_truncated_interview_file_refuses_without_a_ledger(self):
        self._damaged_refuses(ledger=False)

    def test_an_empty_or_truncated_interview_file_refuses_with_a_ledger(self):
        self._damaged_refuses(ledger=True)

    def test_a_refusal_with_confirmed_names_no_confirm_for_the_removed_file(self):
        self.standard()
        self.file(numbers=[1])
        stray = os.path.join(self.pdir, "med", "sources", "other", "2026-10-01__x__stray.pdf")
        os.makedirs(os.path.dirname(stray))
        with open(stray, "wb") as fh:
            fh.write(b"not inventoried")
        with self.assertRaises(ic.LedgerRefused) as cm:
            self.file(confirmed=True)
        msg = str(cm.exception)
        self.assertNotIn("interviews/", msg)
        self.assertFalse([l for l in msg.split("\n") if l.rstrip().endswith(" confirm")], msg)

    def test_an_attestation_refused_after_init_keeps_the_inventoried_file(self):
        from unittest import mock
        from tools.person_ownership import append as _append
        self.standard()
        with mock.patch.object(_append, "confirm", side_effect=_append.AppendStop("simulated")):
            with self.assertRaises(ic.LedgerKept):
                self.file(confirmed=True)
        self.assertEqual(len(os.listdir(os.path.join(self.pdir, "med", "sources", "interviews"))), 1)
        self.assertEqual(self.l13(), [])

    def test_an_orphan_is_inventoried_unverified_and_only_the_new_file_attested(self):
        self.standard()
        self.file(numbers=[1])
        orphan, _ = self.file(numbers=[2], do_register=False)
        extra = [_ask("toolu_C", [_q("Later?")], "2026-10-18T11:00:00.000Z"),
                 _answer("toolu_C", [], {"Later?": "Yes"}, "2026-10-18T11:01:00.000Z")]
        with open(self.transcript, "a", encoding="utf-8") as fh:
            for r in extra:
                fh.write(json.dumps(r) + "\n")
        r = ic.file_interview(self.root, HANDLE, self.transcript, confirmed=True)
        last = {}
        for rec in self.manifest():
            last[rec.get("source_relpath")] = json.dumps(rec)
        self.assertIn("operator-confirmed", last[os.path.relpath(r["path"], self.pdir)])
        self.assertNotIn("operator-confirmed", last[os.path.relpath(orphan, self.pdir)])
        self.assertEqual(self.l13(), [])

    def test_quotation_edge_cases(self):
        q = [_q("Dose?"), _q("Evening?"), _q("Know?")]
        _write_transcript(self.transcript, [
            _ask("toolu_Q", q), _answer("toolu_Q", q, {"Dose?": "12 mg rano",
                                                       "Evening?": "wieczorem 2,5 mg",
                                                       "Know?": "Nie wiem"})])
        path, _ = self.file(do_register=False)
        stem = os.path.basename(path)[:-3]
        prof = os.path.join(self.pdir, "profile.md")

        def run(line):
            with open(prof, "w", encoding="utf-8") as fh:
                fh.write(line + "\n")
            failures, checked, _, _ = ic.check_quotes(self.root, HANDLE)
            return len(failures), checked

        self.assertEqual(run('- "2 mg rano" (%s, B)' % stem), (1, 1))           # inside a number
        self.assertEqual(run('- "wieczorem 2." (%s, B)' % stem), (1, 1))        # inside 2,5
        self.assertEqual(run('- "Nie wiem?" (%s, B)' % stem), (1, 1))           # a ? added
        self.assertEqual(run('- "." (%s, B)' % stem), (0, 0))                   # not a quotation
        self.assertEqual(run('- „12 mg rano" i „Nie wiem" (%s, B)' % stem), (0, 2))
        self.assertEqual(run(',,12 mg rano" i ,,Nie wiem" (%s, B)' % stem), (0, 2))
        with open(self.transcript, "a", encoding="utf-8") as fh:
            for r in (_ask("toolu_R", [_q("Again?")]), _answer("toolu_R", [], {"Again?": "Tak"})):
                fh.write(json.dumps(r) + "\n")
        stem2 = os.path.basename(self.file(do_register=False, slug="second")[0])[:-3]
        self.assertEqual(run('- (%s, B): "12 mg rano"; (%s, B): "Tak"' % (stem, stem2)), (0, 2))
        self.assertEqual(run('- "12 mg rano" (%s, B); "Tak" (%s, B)' % (stem, stem2)), (0, 2))
        self.assertEqual(run('- (%s, B): "Tak"; (%s, B): "12 mg rano"' % (stem, stem2)), (2, 2))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("```answer\ncut off")                      # the cited file damaged
        n, _ = run('- "12 mg rano" (%s, B)' % stem)
        self.assertEqual(n, 1)

    def test_a_bare_number_answer_is_quoted(self):
        """First-run walk: an answer that starts with a number of two or more digits failed when
        quoted from its first character, because the start-of-answer check read the answer's end."""
        q = [_q("Age?"), _q("Since?"), _q("Dose?"), _q("Spoon?")]
        _write_transcript(self.transcript, [
            _ask("toolu_N", q), _answer("toolu_N", q, {"Age?": "65", "Since?": "40 years, 12 of them",
                                                       "Dose?": "2,5", "Spoon?": "2.50"})])
        stem = os.path.basename(self.file(do_register=False)[0])[:-3]

        def run(quote):
            with open(os.path.join(self.pdir, "profile.md"), "w", encoding="utf-8") as fh:
                fh.write('- %s (%s, B)\n' % (quote, stem))
            failures, checked, _, _ = ic.check_quotes(self.root, HANDLE)
            return len(failures), checked

        for good in ('"65"', '„65”', '"65."', '"40"', '"40 years"', '"2,5"', '"2.50"'):
            self.assertEqual(run(good), (0, 1), good)
        for bad in ('"66"', '"6"', '"5"', '"2.5"', '"2"', '"4"', '"2,"', '",5"', '"2."', '".50"'):
            self.assertEqual(run(bad), (1, 1), bad)


class CodexFindings(Base):
    """The three findings of the Codex review of 2026-10-19, reproduced as it described them."""

    def test_a_partial_ledger_write_keeps_the_capture_and_refresh_recovers(self):
        from unittest import mock
        from tools.person_ownership import append as _append
        self.standard()
        self.file(numbers=[1])
        real = _append._atomic_write

        def checkpoint_fails(path, data):
            if path.endswith("MANIFEST.checkpoint"):
                raise OSError("simulated")
            return real(path, data)

        with mock.patch.object(_append, "_atomic_write", side_effect=checkpoint_fails):
            with self.assertRaises(ic.LedgerInterrupted) as cm:
                self.file(numbers=[2])
        self.assertIn("refresh-checkpoint", str(cm.exception))
        names = os.listdir(os.path.join(self.pdir, "med", "sources", "interviews"))
        self.assertEqual(len(names), 2)                              # the capture is kept
        _append.prefix_finalize(self.root, HANDLE)
        self.assertEqual(self.l13(), [])

    def test_retrying_the_original_call_completes_an_interrupted_filing(self):
        self.standard()
        self.person("evalperson-b", "fedcba9876543210fedcba9876543210")
        self.file(numbers=[1])
        orphan, _ = self.file(handle="evalperson-b", numbers=[2], do_register=False)
        r = ic.file_interview(self.root, "evalperson-b", self.transcript, numbers=[2])
        self.assertEqual(r["path"], None)
        self.assertEqual(r["recovered"],
                         [os.path.relpath(orphan, os.path.join(self.root, "patients", "evalperson-b"))])
        self.assertEqual(self.l13(), [])

    def test_a_capture_header_cut_before_its_closing_line_refuses(self):
        self.standard()
        folder = os.path.join(self.pdir, "med", "sources", "interviews")
        os.makedirs(folder)
        for body in ("---\ncapture: on-screen questions\nperson: %s\n" % HANDLE, "---\n",
                     "---\ncapture: on-scr"):
            with open(os.path.join(folder, "2026-10-17__interview__cut.md"), "w",
                      encoding="utf-8") as fh:
                fh.write(body)
            with self.assertRaises(ic.CaptureError) as cm:
                self.file()
            self.assertIn("ask the operator", str(cm.exception))
            self.assertFalse(os.path.exists(os.path.join(self.pdir, "med", "MANIFEST")))
        # a sheet-era file with an unclosed header of its own shape does not block filing
        with open(os.path.join(folder, "2026-10-17__interview__cut.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nperson: x\n")
        r = ic.file_interview(self.root, HANDLE, self.transcript)
        self.assertTrue(r["path"])


class ReviewFindings(Base):
    """The independent review of 2026-10-19."""

    def _chain(self, recs):
        """Give records line ids and previous-record links in order, as the client writes them."""
        prev = None
        for i, r in enumerate(recs):
            r["uuid"] = "u%03d" % i
            r["parentUuid"] = r.pop("_parent", prev)
            prev = r["uuid"]
        return recs

    def test_a_call_on_a_rewound_branch_is_not_filed(self):
        q = [_q("Dose?")]
        recs = self._chain([
            {"type": "user", "message": {"role": "user", "content": "start"}},       # u000
            _ask("toolu_OLD", q), _answer("toolu_OLD", q, {"Dose?": "10 mg"}),        # u001, u002
            dict(_ask("toolu_NEW", q), _parent="u000"),                               # rewound to u000
            _answer("toolu_NEW", q, {"Dose?": "5 mg"})])
        _write_transcript(self.transcript, recs)
        calls = ic.read_calls(self.transcript)
        self.assertEqual([c["status"] for c in calls], ["off-branch", "answered"])
        r = ic.file_interview(self.root, HANDLE, self.transcript)
        self.assertEqual([c["n"] for c in r["calls"]], [2])
        self.assertEqual([c["n"] for c in r["skipped"]], [1])
        self.assertNotIn("10 mg", _read(r["path"]))
        with self.assertRaises(ic.CaptureError) as cm:
            ic.file_interview(self.root, HANDLE, self.transcript, numbers=[1])
        self.assertIn("rewound or edited", str(cm.exception))

    def test_parallel_calls_and_a_compaction_stay_live(self):
        q = [_q("Dose?")]
        a1 = _ask("toolu_P", q)
        a1["message"]["id"] = "msg_1"
        other = {"type": "assistant", "message": {"id": "msg_1", "role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_R", "name": "Read", "input": {}}]}}
        recs = self._chain([
            {"type": "user", "message": {"role": "user", "content": "start"}},       # u000
            other, a1,                                   # u001, u002: one message, two tool calls
            dict(_answer("toolu_P", q, {"Dose?": "5 mg"}), _parent="u002"),           # u003
            {"type": "user", "_parent": "u001", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_R", "content": "x"}]}}, # u004: chain goes on here
            {"type": "system", "subtype": "compact_boundary", "_parent": None,
             "logicalParentUuid": "u004"},                                           # u005
            {"type": "user", "message": {"role": "user", "content": "after compaction"}}])
        _write_transcript(self.transcript, recs)
        self.assertEqual([c["status"] for c in ic.read_calls(self.transcript)], ["answered"])

    def test_the_session_id_never_leaves_an_eleven_digit_run(self):
        sid = "aaaaaaaa-bbbb-cccc-dddd-012345678901"
        q = [_q("Dose?")]
        path = os.path.join(self.tdir, sid + ".jsonl")
        _write_transcript(path, [_ask("toolu_A", q), _answer("toolu_A", q, {"Dose?": "5 mg"})])
        p, _ = ic.file_interview(self.root, HANDLE, path, do_register=False)["path"], None
        text = _read(p)
        # the private-mode guard's rule: a 32/40/64-hex token with a letter is a digest, not digits
        stripped = re.sub(r"[0-9A-Fa-f]+", lambda m: " " if len(m.group()) in (32, 40, 64)
                          and re.search("[A-Fa-f]", m.group()) else m.group(), text)
        self.assertIsNone(re.search(r"[0-9]{11}", stripped))
        self.assertEqual(ic.verify(p, config_dir=self.cfg)[0], [])      # still finds its transcript

    def test_a_sheet_era_file_with_a_lone_fence_never_blocks_filing(self):
        self.standard()
        other = self.person("evalperson-b", "fedcba9876543210fedcba9876543210")
        folder = os.path.join(other, "med", "sources", "interviews")
        os.makedirs(folder)
        with open(os.path.join(folder, "2026-09-01__interview__sheet.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nperson: b\n---\n# sheet\n```\nan answer with a fence\n")
        r = ic.file_interview(self.root, HANDLE, self.transcript, take_all=True)
        self.assertTrue(r["path"])

    def test_the_write_is_whole_and_a_stale_temp_is_removed(self):
        self.standard()
        med = os.path.join(self.pdir, "med")
        with open(os.path.join(med, ".interview-capture-1.tmp"), "w") as fh:
            fh.write("left by a crash")
        self.file()
        self.assertEqual([n for n in os.listdir(med) if n.endswith(".tmp")], [])
        self.assertEqual(self.l13(), [])

    def test_call_with_a_window_refuses_and_a_repeated_call_is_filed_once(self):
        self.standard()
        with self.assertRaises(ic.CaptureError):
            self.file(numbers=[1], since="2026-10-18")
        _, calls = self.file(numbers=[1, 1])
        self.assertEqual([c["n"] for c in calls], [1])

    def test_quotes_refuses_an_unknown_handle(self):
        with self.assertRaises(ic.CaptureError):
            ic.check_quotes(self.root, "nobody")

    def test_cli_reports_partly_done(self):
        from unittest import mock
        from tools.person_ownership import append as _append
        self.standard()
        buf = io.StringIO()
        with mock.patch.object(_append, "confirm", side_effect=_append.AppendStop("simulated")):
            with redirect_stdout(buf):
                rc = main(["--root", self.root, "file", HANDLE, "--transcript", self.transcript,
                           "--confirmed"])
        self.assertEqual(rc, 3)
        self.assertIn("PARTLY DONE", buf.getvalue())


class WrappedAndLabels(Base):
    """ADR-0041 point 6: wrapped prose is read as one line, the record's
    own `open item “<label>”` naming is not a quotation, and another source's quotation is that
    source's (behavioural eval EV-14 calibration, 2026-10-19, and the red-team round on this change)."""

    def setUp(self):
        super().setUp()
        self.standard()
        self.stem = os.path.basename(self.file(do_register=False)[0])[:-3]

    def second(self):
        """A second interview file whose only answer is "Tak"; its dated name."""
        with open(self.transcript, "a", encoding="utf-8") as fh:
            for r in (_ask("toolu_S", [_q("Again?")]), _answer("toolu_S", [], {"Again?": "Tak"})):
                fh.write(json.dumps(r) + "\n")
        return os.path.basename(self.file(do_register=False, slug="second")[0])[:-3]

    def run_on(self, text, stem2=None):
        if stem2:
            text = text.replace("STEM2", stem2)
        with open(os.path.join(self.pdir, "profile.md"), "w", encoding="utf-8") as fh:
            fh.write("# profile\n\n" + text.replace("STEM", self.stem) + "\n")
        failures, checked, _, unquoted = ic.check_quotes(self.root, HANDLE)
        return failures, checked, unquoted

    def test_a_quotation_wrapped_across_lines_is_read(self):
        good = ('- Doses: the operator says "Rano 5 mg, wieczorem\n'
                '  2,5 mg, czasem pomija" (operator, STEM, B)')
        self.assertEqual(self.run_on(good), ([], 1, 0))
        failures, checked, _ = self.run_on(good.replace("czasem", "czasami"))
        self.assertEqual(checked, 1)
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0].startswith("profile.md:3:"), failures)   # the line it starts on
        self.assertIn("copy it from the file, or, if it quotes no answer, take the quote marks off",
                      failures[0])                                  # both ways out are named
        failures, checked, _ = self.run_on('- Doses, as the operator\n  put it: "Rano 5 mg, wieczorem 2,5 mg,'
                                           ' czasami pomija" (operator, STEM, B)')
        self.assertEqual((len(failures), checked), (1, 1))
        self.assertTrue(failures[0].startswith("profile.md:4:"), failures)
        failures, checked, _ = self.run_on('- "Rano 5 mg, wieczorem\n  2,5 mg, czasami pomija", so the'
                                           ' operator (STEM, B)')
        self.assertEqual((len(failures), checked), (1, 1))          # a citation on its last line
        failures, checked, _ = self.run_on('- "Rano 5 mg, wieczorem\n  2,5 mg, czasami pomija" and "Pain"'
                                           ' (operator, STEM, B)')
        self.assertEqual((len(failures), checked), (1, 2))          # past another quotation, on its line

    def test_a_citation_on_the_next_line_or_wrapped_in_its_parentheses_is_seen(self):
        for text in ('Reported: "Rano 5 mg, wieczorem 2,5 mg, czasami pomija"\n(operator, STEM, B).',
                     'Reported: "Rano 5 mg, wieczorem 2,5 mg, czasami pomija" (operator,\nSTEM, B).',
                     '- (operator,\n  STEM, B): "Rano 5 mg, wieczorem 2,5 mg, czasami pomija"',
                     '- „Rano 5 mg, wieczorem 2,5 mg, czasami pomija”, the operator wrote on screen\n'
                     '  (operator, STEM, B).'):
            failures, checked, _ = self.run_on(text)
            self.assertEqual((len(failures), checked), (1, 1), text)

    def test_a_quotation_no_citation_claims_is_counted_not_read(self):
        # another source's quotation on the line above, in the same paragraph, is not this file's
        text = ('The discharge letter says "bez zmian w leczeniu", and the operator\n'
                'reports "Rano 5 mg, wieczorem 2,5 mg, czasem pomija" (operator, STEM, B).')
        self.assertEqual(self.run_on(text), ([], 1, 1))
        # a citation on an earlier line, with words between, claims nothing on a later line
        text = ('(operator, STEM, B) says they stopped it. The letter says\n'
                '“bez zmian w leczeniu” and nothing else.')
        self.assertEqual(self.run_on(text), ([], 0, 1))
        self.run_on('- (operator, STEM, B) says they skip it;\n  „Rano 5 mg, czasami pomija” at times')
        self.assertEqual(list(ic.quotations(self.root, HANDLE)),
                         [("profile.md:4", None, "Rano 5 mg, czasami pomija", "unread")])

    def test_a_quotation_followed_by_another_sources_citation_is_that_sources(self):
        self.assertEqual(self.run_on('The discharge letter says “bez zmian w\nleczeniu” (letter 2026-09-01,'
                                     ' A), and the operator reports “Pain” (operator, STEM, B).'), ([], 1, 0))
        self.assertEqual(self.run_on('The letter: “bez zmian” (letter, A); the operator: “Pain” (STEM, B)'),
                         ([], 1, 0))
        self.assertEqual(self.run_on('This waits on open item “clinic review” (operator,\n  STEM, B). The'
                                     ' discharge letter says „bez\n  zmian w leczeniu” (letter 2026-09-01,'
                                     ' A).'), ([], 0, 1))
        failures, checked, _ = self.run_on('- "Pian" (sic) (operator, STEM, B)')
        self.assertEqual((len(failures), checked), (1, 1))          # a gloss is not a source

    def test_two_files_in_one_wrapped_paragraph_keep_their_quotations(self):
        stem2 = self.second()
        self.assertEqual(self.run_on('Per the first call (operator, STEM, B): "Rano 5 mg, wieczorem 2,5 mg,'
                                     ' czasem pomija"\n(operator, STEM2, B): "Tak"', stem2), ([], 2, 0))
        self.assertEqual(self.run_on('- "Pain" (operator, STEM, B)\n  "Tak" — confirmed in the second'
                                     ' call (STEM2, B)', stem2), ([], 2, 0))
        self.assertEqual(self.run_on('- "Pain" (operator, STEM, B) — "Tak"\n  (operator, STEM2, B)', stem2),
                         ([], 2, 0))                                # a citation serves one quotation
        self.assertEqual(self.run_on('- In the second call they confirmed „Tak” (operator,\n  STEM2, B). They'
                                     ' wrote "Rano 5 mg, wieczorem 2,5 mg, czasem pomija" and later\n'
                                     '  “Pain”, both on screen (operator, STEM, B).', stem2), ([], 3, 0))

    def test_another_quotation_between_does_not_hide_the_next_citation(self):
        failures, checked, _ = self.run_on('- They wrote „Rano 5 mg, wieczorem 2,5 mg, czasami pomija” and'
                                           ' later „Pain”, both\n  on screen (operator, STEM, B).')
        self.assertEqual((len(failures), checked), (1, 2))
        failures, checked, _ = self.run_on('- They wrote „Rano 5 mg, wieczorem 2,5 mg, czasami pomija”, and the'
                                           ' letter\n  says “bez zmian w leczeniu” (letter 2026-09-01, A); both'
                                           ' noted (operator, STEM, B)')
        self.assertEqual((len(failures), checked), (1, 1))

    def test_an_answer_tagged_with_the_records_own_grade_b_mark_is_still_read(self):
        for text in ('- "Rano 5 mg, wieczorem 2,5 mg, czasami pomija" (operator 2026-10-18, B) (STEM)',
                     '| Drug Y | partial | "Rano 5 mg, wieczorem 2,5 mg, czasami pomija" (operator, B) | STEM |',
                     '- The operator: "Pain" (operator, STEM, B); on doses "Rano 5 mg, wieczorem 2,5 mg,'
                     ' czasami pomija" (operator 2026-10-18, B).'):
            failures, checked, _ = self.run_on(text)
            self.assertEqual(len(failures), 1, text)
        failures, checked, _ = self.run_on('- The analysis: "czasami pomija" (analysis 2026-10-01, C);'
                                           ' the operator: "Pain" (STEM, B)')
        self.assertEqual((failures, checked), ([], 1))             # grades A, C and D are other sources

    def test_the_cli_names_each_quotation_it_could_not_read(self):
        self.run_on('- (operator, STEM, B) says they skip it;\n  „Rano 5 mg, czasami pomija” at times\n'
                    '- a paraphrase (STEM, B)')
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--root", self.root, "quotes", HANDLE])
        self.assertEqual(rc, 0)
        self.assertIn("NOT READ  profile.md:4: a quotation with no citation beside it", buf.getvalue())
        self.assertIn("1 citing paragraph(s) with no quotation of the file", buf.getvalue())

    def test_list_items_headings_and_blank_lines_are_never_joined(self):
        # a stray straight quote (inch marks) in one block never pairs with the next block's quotes
        for before in ('- Frame 5\'7"\n- ', '* Frame 5\'7"\n* ', '+ Frame 5\'7"\n+ ', '1. Frame 5\'7"\n2. ',
                       '## Frame 5\'7"\n', '| Frame | 5\'7" |\n', '> Frame 5\'7"\n', 'Frame 5\'7"\n> ',
                       'Frame 5\'7"\n\n'):
            text = before + '"Rano 5 mg, wieczorem 2,5 mg, czasem pomija" (operator, STEM, B)'
            self.assertEqual(self.run_on(text), ([], 1, 0), before)

    def test_a_bare_citation_takes_the_quotation_beside_it(self):
        text = ('- (letter 2026-01-01, A) "Pain" STEM, and "Tak" — STEM2\n'
                '- STEM: "Pain"; "Tak" (STEM2, B)')
        self.assertEqual(self.run_on(text, self.second()), ([], 4, 0))

    def test_an_open_item_label_is_not_a_quotation(self):
        self.assertEqual(self.run_on('- Ask at open item “clinic review”: "Pain" (operator, STEM, B)'),
                         ([], 1, 0))
        for label in ('- See open item "clinic review" (operator, STEM, B)',
                      '- See open\n  item “clinic review” (operator, STEM, B)',
                      '- Open item “clinic review” (operator, STEM, B)',
                      '- see open items “gp review” (STEM, B)'):
            self.assertEqual(self.run_on(label), ([], 0, 1), label)
        failures, checked, _ = self.run_on('- open item “gp”: "Rano 5 mg wieczorem" (STEM, B)')
        self.assertEqual((len(failures), checked), (1, 1))          # a misquote beside one still fails
        failures, checked, _ = self.run_on('- the item “clinic review” (operator, STEM, B)')
        self.assertEqual((len(failures), checked), (1, 1))          # any other wording is a quotation

    def test_quotations_yields_each_verdict_with_its_text(self):
        self.run_on('- "Pain" (operator, STEM, B), then\n  "Pian" (STEM, B)\n'
                    '- "Pain" (2026-09-02__interview__missing, B)\n- a paraphrase\n  of it (STEM, B)')
        self.assertEqual(list(ic.quotations(self.root, HANDLE)), [
            ("profile.md:3", self.stem, "Pain", "ok"),
            ("profile.md:4", self.stem, "Pian", "altered"),
            ("profile.md:5", "2026-09-02__interview__missing", "Pain", "missing"),
            ("profile.md:6", None, None, "unquoted")])


class CitationHeader(Base):
    """ADR-0041 point 7: the header prints the file's own citation (format 2), since
    sessions told to cite the file "by its name" cited it by date, which `quotes` never reads (EV-14's
    first live run); a file filed in format 1 still verifies byte for byte."""

    NEW = re.compile(r"cite it right after the quotation exactly as `([^`]+)` — this file's dated "
                     r"name, not its heading or a date alone\.\n")

    def header_cite(self, path):
        m = self.NEW.search(_read(path))
        return m and m.group(1)

    def as_format_1(self, text):
        """The text the format-1 tool wrote for the same calls: its format line and its sentence."""
        return self.NEW.sub("cite this file by its name.\n", text.replace(
            "format: interview_capture 2\n", "format: interview_capture 1\n", 1), 1)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def test_the_header_cites_its_own_file_a_taken_name_and_a_slug_included(self):
        self.standard([_ask("toolu_C", [_q("Later?")], "2026-10-18T11:00:00.000Z"),
                       _answer("toolu_C", [], {"Later?": "Yes"}, "2026-10-18T11:01:00.000Z")])
        p1, _ = self.file(numbers=[1])
        p2, _ = self.file(numbers=[2])
        p3, _ = self.file(slug="doses")
        self.assertEqual(self.header_cite(p1), "(operator, 2026-10-18__interview__on-screen, B)")
        self.assertEqual(self.header_cite(p2), "(operator, 2026-10-18__interview__on-screen__2, B)")
        self.assertEqual(self.header_cite(p3), "(operator, 2026-10-18__interview__doses, B)")
        for p in (p1, p2, p3):
            self.assertIn("\nformat: interview_capture 2\n", _read(p))
            self.assertNotIn("cite this file by its name", _read(p))
            self.assertEqual(ic.verify(p, config_dir=self.cfg)[0], [])
        self.assertEqual(self.l13(), [])

    def test_the_header_citation_copied_into_the_profile_is_read_by_quotes(self):
        self.standard()
        p, _ = self.file()
        with open(os.path.join(self.pdir, "profile.md"), "a", encoding="utf-8") as fh:
            fh.write('- Symptoms: "Pain" %s\n- Doses: "Rano 6 mg" %s\n'
                     % (self.header_cite(p), self.header_cite(p)))
        self.assertEqual([v for _, _, _, v in ic.quotations(self.root, HANDLE)], ["ok", "altered"])

    # SHA-256 of the file the format-1 tool (commit 9abbb13) wrote for `standard()`, filed at FILED_AT:
    # the converted text must be those bytes, so a change to text both formats share goes red here
    # rather than failing every format-1 file in a record (red-team, 2026-10-22).
    FORMAT_1_SHA256 = "eef5b0d59481f35e860fcad932171f8f816d4ef8f690041eec1c1d91c6a6786b"
    FILED_AT = datetime.datetime(2026, 10, 18, 10, 10, tzinfo=datetime.timezone.utc)

    def test_a_format_1_file_verifies_byte_for_byte_in_its_own_wording(self):
        self.standard()
        p, _ = self.file(do_register=False, now=self.FILED_AT)
        text = _read(p)
        old = self.as_format_1(text)
        self.assertEqual(hashlib.sha256(old.encode("utf-8")).hexdigest(), self.FORMAT_1_SHA256)
        self.assertNotIn("(operator, ", old)
        self.write(p, old)
        problems, notes = ic.verify(p, config_dir=self.cfg)
        self.assertEqual(problems, [])
        self.assertIn("byte-identical to a fresh copy of the transcript", notes)
        moved = os.path.join(os.path.dirname(p), "renamed.md")
        os.rename(p, moved)                                  # format 1 cites no name: not read
        self.assertEqual(ic.verify(moved, config_dir=self.cfg)[0], [])
        self.write(moved, text.replace("format: interview_capture 2\n",
                                       "format: interview_capture 1\n", 1))
        self.assertEqual(ic.verify(moved, config_dir=self.cfg)[0],
                         ["the file differs from a fresh copy of the transcript"])

    def test_a_renamed_file_or_an_unknown_format_fails_verify(self):
        self.standard()
        p, _ = self.file(do_register=False)
        text = _read(p)
        moved = p[:-3] + "__2.md"
        os.rename(p, moved)                                  # its header cites another name
        self.assertEqual(ic.verify(moved, config_dir=self.cfg)[0],
                         ["the file differs from a fresh copy of the transcript"])
        odd = os.path.join(os.path.dirname(p), "notes.md")
        os.rename(moved, odd)
        problems, _ = ic.verify(odd, config_dir=self.cfg)
        self.assertTrue(any("not an interview file's dated name" in x for x in problems), problems)
        self.write(p, text.replace("format: interview_capture 2\n", "format: interview_capture 3\n"))
        problems, _ = ic.verify(p, config_dir=self.cfg)
        self.assertTrue(any("format this tool does not know" in x for x in problems), problems)
        self.assertEqual(ic.verify(p, transcript=False)[0], [])   # the answers themselves are intact


class Cli(Base):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--root", self.root] + list(args))
        return rc, buf.getvalue()

    def test_list_file_verify_quotes(self):
        self.standard()
        rc, out = self.run_cli("list", "--transcript", self.transcript)
        self.assertEqual(rc, 0)
        self.assertIn("call 2", out)
        self.assertNotIn("czasem", out)                       # list never prints an answer
        rc, out = self.run_cli("file", HANDLE, "--transcript", self.transcript)
        self.assertEqual(rc, 0, out)
        path = os.path.join(self.root, out.split("filed word for word: ", 1)[1].split("\n")[0])
        self.assertIn("quotes %s" % HANDLE, out)                # the next step is named
        self.assertIn("cite it right after the quotation exactly as "
                      "`(operator, 2026-10-18__interview__on-screen, B)`;", out)   # and its citation
        rc, out = self.run_cli("verify", path, "--transcript", self.transcript)
        self.assertEqual(rc, 0, out)
        rc, out = self.run_cli("quotes", HANDLE)
        self.assertEqual(rc, 0, out)
        rc, out = self.run_cli("file", HANDLE, "--transcript", self.transcript)
        self.assertEqual(rc, 3)
        self.assertIn("REFUSED (nothing written)", out)

    def test_file_prints_each_files_citation_when_it_completes_an_interrupted_filing(self):
        self.standard()
        self.file(numbers=[1])
        self.file(numbers=[2], do_register=False)           # on disk, not inventoried
        with open(self.transcript, "a", encoding="utf-8") as fh:
            for r in (_ask("toolu_C", [_q("Later?")], "2026-10-18T11:00:00.000Z"),
                      _answer("toolu_C", [], {"Later?": "Yes"}, "2026-10-18T11:01:00.000Z")):
                fh.write(json.dumps(r) + "\n")
        rc, out = self.run_cli("file", HANDLE, "--transcript", self.transcript)
        self.assertEqual(rc, 0, out)
        self.assertIn("exactly as `(operator, 2026-10-18__interview__on-screen__2, B)` or "
                      "`(operator, 2026-10-18__interview__on-screen__3, B)` (the file it comes from);",
                      out)

    def test_session_from_the_environment(self):
        self.standard()
        env = dict(os.environ, CLAUDE_CODE_SESSION_ID=SID, CLAUDE_CONFIG_DIR=self.cfg)
        r = subprocess.run([sys.executable, "-m", "tools.interview_capture", "--root", self.root,
                            "list"], cwd=REPO, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("call 1", r.stdout)
        env["CLAUDE_CODE_SESSION_ID"] = "99999999-0000-0000-0000-000000000000"
        r = subprocess.run([sys.executable, "-m", "tools.interview_capture", "list"], cwd=REPO,
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
