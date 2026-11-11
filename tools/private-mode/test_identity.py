#!/usr/bin/env python3
"""Synthetic suite for identity.py — private mode's identity file of kept details and age (ADR-0029,
ADR-0075).

Synthetic persons only, in temp dirs. Besides the command itself it carries the marker bite: every
consumer's marker constant is the same bytes, and the ownership locator and the read guard treat a
private-mode person as such (guard L10's own bite lives in checks/selftest.sh).

  python3 tools/private-mode/test_identity.py
  python3 -m unittest tools.private-mode.test_identity
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import identity  # noqa: E402
import id_schemes as S  # noqa: E402
from identity import Refused  # noqa: E402

D = datetime.date
V1_LINE = '- Private mode (experimental, ADR-0029): synthetic identifier class ⟨never-API⟩ — operator decision 2026-01-01'
SINCE = '2026-10-01'                 # when the synthetic details were recorded
GIVEN, FAMILY = 'Synthia Maria', 'Testperson'
SECRETS = [GIVEN, FAMILY, '1901-02-23', 'Example Street 12', '+00 555 010 101', 'synth@example.invalid']


def dated(vals, since=SINCE):
    """Values in the identity file's shape, each with its recording date."""
    return [{'value': v, 'since': since} for v in vals]


def plain(data):
    """{class: [values]} without their dates."""
    return {c: identity.values(data, c) for c in identity.CLASSES}


def scoped(pdir, since=SINCE):
    """[(relpath, kind)] of the files where a value recorded on `since` counts."""
    day = D.fromisoformat(since)
    return [(rel, kind) for rel, kind, when in identity.in_scope(pdir) if when is None or when >= day]


def contextlib_quiet():
    return contextlib.redirect_stderr(io.StringIO())


def profile_text(line):
    return '# Profile — synthetic\n\n## Identity & basics\n- Name / role: synthetic\n%s\n' % line


class Tree:
    def __init__(self, line=V1_LINE, handle='szt-pm'):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.handle = handle
        self.pdir = os.path.join(self.root, 'patients', handle)
        os.makedirs(os.path.join(self.pdir, 'med', '_inbox'))
        with open(os.path.join(self.pdir, 'profile.md'), 'w', encoding='utf-8') as fh:
            fh.write(profile_text(line))

    def close(self):
        self.tmp.cleanup()


class Script:
    """Answers for the no-echo prompts, in order; records what the command printed."""
    def __init__(self, answers, confirms=()):
        self.answers = list(answers)
        self.confirms = list(confirms)
        self.out = []

    def ask(self, prompt):
        if not self.answers:
            raise AssertionError('unexpected prompt: %s' % prompt)
        return self.answers.pop(0)

    def confirm(self, prompt):
        self.out.append(prompt)
        return self.confirms.pop(0)

    def tell(self, msg):
        self.out.append(msg)

    def printed(self):
        return '\n'.join(self.out)

    def fns(self):
        return self.ask, self.confirm, self.tell


def twice(*values):
    """Each value typed, then typed again; '' ends a class (asked once)."""
    seq = []
    for v in values:
        seq += [v] if v == '' else [v, v]
    return seq


FULL = (twice(GIVEN, FAMILY, '') + twice('1901-02-23') + twice('') + twice('')
        + twice('Example Street 12', '') + twice('+00 555 010 101', '') + twice('synth@example.invalid', '')
        + twice(''))


class Marker(unittest.TestCase):
    def test_marked(self):
        self.assertTrue(identity.marked(profile_text(V1_LINE)))
        self.assertFalse(identity.marked(profile_text('- Private mode: none')))

    def test_the_retired_second_level_tag_is_plain_text(self):
        # the tag of before ADR-0075 configures nothing; what the identity file holds is kept
        text = profile_text(V1_LINE + ' · ⟨private-v2 cutover=2026-10-01⟩')
        self.assertTrue(identity.marked(text))
        self.assertFalse(hasattr(identity, 'v2_setting'))


class MarkerBite(unittest.TestCase):
    """Every consumer keys on the same marker bytes."""

    def test_every_consumer_matches_the_same_marker(self):
        from tools.person_ownership import fsverify
        self.assertEqual(fsverify._PRIVATE_MARK, identity.MARK)
        spec = importlib.util.spec_from_file_location(
            'rrg', os.path.join(ROOT, 'tools', 'claude-hooks', 'registry-read-guard.py'))
        rrg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrg)
        self.assertEqual(rrg.PM_MARK.decode('utf-8'), identity.MARK)
        with open(os.path.join(ROOT, 'checks', 'check.sh'), encoding='utf-8') as fh:
            check = fh.read()
        for var in ('LOC_MARK', 'L10_MARK'):
            self.assertEqual(re.findall(r"^%s='([^']*)'" % var, check, re.M), [identity.MARK], var)
        self.assertIn(identity.MARK, V1_LINE)

    def test_locator_withholds_a_private_mode_person(self):
        from tools.person_ownership import fsverify
        t = Tree()
        try:
            self.assertEqual(fsverify.person_status(t.root, t.handle), 'private')
            self.assertTrue(fsverify.private_mode_in_use(t.root))
            self.assertEqual(fsverify.locator(t.root, t.handle, 'med/x.md', True), fsverify.WITHHELD_PRIVATE)
            with open(os.path.join(t.pdir, 'profile.md'), 'w', encoding='utf-8') as fh:
                fh.write(profile_text('- Private mode: none'))      # control: an unmarked person
            self.assertEqual(fsverify.locator(t.root, t.handle, 'med/x.md', True), 'patients/szt-pm/med/x.md')
        finally:
            t.close()

    def test_read_guard_refuses_a_private_mode_persons_original(self):
        t = Tree()
        try:
            orig = os.path.join(t.pdir, 'med', '_inbox', '2026-09-30__lab__panel.jpg')
            with open(orig, 'w') as fh:
                fh.write('synthetic\n')
            hook = os.path.join(ROOT, 'tools', 'claude-hooks', 'registry-read-guard.py')
            env = dict(os.environ, CLAUDE_PROJECT_DIR=t.root, HOME=t.root)
            payload = json.dumps({'tool_name': 'Read', 'tool_input': {'file_path': orig}, 'cwd': t.root})
            p = subprocess.run([sys.executable, hook], input=payload.encode(), capture_output=True, env=env)
            self.assertEqual(p.returncode, 2, p.stderr)
            with open(os.path.join(t.pdir, 'profile.md'), 'w', encoding='utf-8') as fh:
                fh.write(profile_text('- Private mode: none'))      # control: an unmarked person
            p = subprocess.run([sys.executable, hook], input=payload.encode(), capture_output=True, env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
        finally:
            t.close()


class SetCommand(unittest.TestCase):
    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def run_set(self, answers, only=None, confirms=()):
        s = Script(answers, confirms)
        identity.cmd_set(self.t.root, self.t.handle, only, s.ask, s.confirm, s.tell)
        return s

    def test_full_set_writes_owner_only_and_prints_no_value(self):
        s = self.run_set(FULL)
        path = os.path.join(self.t.pdir, identity.IDENTITY_NAME)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        data = identity.load(self.t.pdir)
        c = plain(data)
        self.assertEqual(c['patient_names'], [{'given': GIVEN, 'family': FAMILY}])
        self.assertEqual({e['since'] for c_ in identity.CLASSES for e in data['classes'][c_]},
                         {D.today().isoformat()})
        self.assertEqual((c['dob'], c['phones'], c['other_names']), (['1901-02-23'], ['+00 555 010 101'], []))
        for v in SECRETS:
            self.assertNotIn(v, s.printed())
        self.assertIn('patient_names 1', s.printed())
        self.assertEqual([n for n in os.listdir(self.t.pdir) if n.startswith('.tmp-')], [])

    def test_one_class_replaced_others_kept(self):
        self.run_set(FULL)
        self.run_set(twice('+00 555 020 202', ''), only='phones', confirms=[True])
        c = plain(identity.load(self.t.pdir))
        self.assertEqual((c['phones'], c['dob']), (['+00 555 020 202'], ['1901-02-23']))

    def test_declined_replace_keeps_values(self):
        self.run_set(FULL)
        self.run_set([], only='phones', confirms=[False])
        self.assertEqual(plain(identity.load(self.t.pdir))['phones'], ['+00 555 010 101'])

    def test_identifier_shape_refused_spaced_accepted(self):
        s = self.run_set(twice('00000000000', '000 000 000 00', ''), only='case_numbers')
        self.assertEqual(plain(identity.load(self.t.pdir))['case_numbers'], ['000 000 000 00'])
        self.assertIn('never recorded', s.printed())
        self.assertNotIn('00000000000', s.printed())

    def test_mismatch_asks_again_then_gives_up(self):
        s = self.run_set(['a1', 'a2', 'b1', 'b1', ''], only='case_numbers')
        self.assertEqual(plain(identity.load(self.t.pdir))['case_numbers'], ['b1'])
        self.assertIn('differ', s.printed())
        with self.assertRaises(Refused):
            self.run_set(['x', 'y', 'x', 'y', 'x', 'y'], only='case_numbers', confirms=[True])
        self.assertEqual(plain(identity.load(self.t.pdir))['case_numbers'], ['b1'])

    def test_bad_date_and_email_refused(self):
        self.run_set(twice('1901-02-30', '2999-01-01', '1901-02-23'), only='dob')
        self.run_set(twice('not-an-address', ''), only='emails')
        c = plain(identity.load(self.t.pdir))
        self.assertEqual((c['dob'], c['emails']), (['1901-02-23'], []))

    def test_linked_person_or_file_refused(self):
        link = os.path.join(self.t.root, 'patients', 'szt-link')
        os.symlink(self.t.pdir, link)
        with self.assertRaises(Refused):
            identity.cmd_set(self.t.root, 'szt-link', 'phones', *Script([]).fns())
        target = os.path.join(self.t.root, 'elsewhere.json')     # a VALID identity file behind the link
        body = json.dumps(identity.empty())
        with open(target, 'w') as fh:
            fh.write(body)
        os.symlink(target, os.path.join(self.t.pdir, identity.IDENTITY_NAME))
        with self.assertRaises(Refused):
            identity.load(self.t.pdir)
        with self.assertRaises(Refused):
            identity.write(self.t.pdir, identity.empty())
        with open(target) as fh:
            self.assertEqual(fh.read(), body)

    def test_a_value_set_again_keeps_its_date(self):
        self.run_set(FULL)
        data = identity.load(self.t.pdir)
        data['classes']['phones'] = dated(['+00 555 010 101'], '2026-01-05')
        identity.write(self.t.pdir, data)
        self.run_set(twice('+00 555 010 101', '+00 555 020 202', ''), only='phones', confirms=[True])
        self.assertEqual([e['since'] for e in identity.load(self.t.pdir)['classes']['phones']],
                         ['2026-01-05', D.today().isoformat()])

    def test_needs_the_marker(self):
        for line in ('- Private mode: none', '- Private mode: none ⟨private-v2 cutover=2026-10-01⟩'):
            t = Tree(line=line)
            try:
                with self.subTest(line=line), self.assertRaises(Refused):
                    identity.cmd_set(t.root, t.handle, 'phones', *Script([]).fns())
                self.assertFalse(os.path.lexists(os.path.join(t.pdir, identity.IDENTITY_NAME)))
            finally:
                t.close()

    def test_bad_handles_refused(self):
        for h in ('', '.', '..', 'a/b', 'no-such-person'):
            with self.subTest(h=h), self.assertRaises(Refused):
                identity.person_dir(self.t.root, h)

    def test_oversized_update_refused_previous_file_intact(self):
        # every class and value limit respected, the encoded file still too big (Codex review 2026-10-01)
        self.run_set(FULL)
        path = os.path.join(self.t.pdir, identity.IDENTITY_NAME)
        with open(path, 'rb') as fh:
            before = fh.read()
        data = identity.load(self.t.pdir)
        big = 'ż' * identity.MAX_VALUE
        for cls in ('addresses', 'id_numbers', 'case_numbers', 'phones'):
            data['classes'][cls] = dated([big[:-3] + '%03d' % i
                                          for i in range(identity.MAX_VALUES)])
        identity.validate(data, identity.id_shape(self.t.pdir))
        with self.assertRaises(Refused):
            identity.write(self.t.pdir, data)
        with open(path, 'rb') as fh:
            self.assertEqual(fh.read(), before)
        self.assertEqual(sorted(os.listdir(self.t.pdir)), sorted(['med', 'profile.md', identity.IDENTITY_NAME]))

    def test_failed_write_leaves_no_temporary_file_and_names_it_for_the_guard(self):
        seen = []

        def failing_replace(src, dst):
            seen.append(os.path.basename(src))
            raise OSError('synthetic failure')
        real = identity.os.replace
        identity.os.replace = failing_replace
        try:
            with self.assertRaises(OSError):
                identity.write(self.t.pdir, identity.empty())
        finally:
            identity.os.replace = real
        # the read guard refuses any name ending in the identity file's name: an interrupted write's
        # temporary file must carry it, and a failed one must not stay behind
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].endswith(identity.IDENTITY_NAME) and seen[0] != identity.IDENTITY_NAME)
        self.assertEqual(sorted(os.listdir(self.t.pdir)), ['med', 'profile.md'])


class Load(unittest.TestCase):
    def setUp(self):
        self.t = Tree()
        self.path = os.path.join(self.t.pdir, identity.IDENTITY_NAME)

    def tearDown(self):
        self.t.close()

    def put(self, obj):
        with open(self.path, 'w', encoding='utf-8') as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj))

    def test_absent_is_none(self):
        self.assertIsNone(identity.load(self.t.pdir))

    def test_shapes_refused(self):
        good = identity.empty()
        bad = []
        for mutate in (
            lambda d: d.update(extra=1),
            lambda d: d.update(version=3),
            lambda d: d['classes'].update(barcodes=[]),
            lambda d: d['classes'].pop('emails'),
            lambda d: d['classes'].update(dob=dated(['1901-02-23', '1901-02-24'])),
            lambda d: d['classes'].update(patient_names=dated([{'given': 'A'}])),
            lambda d: d['classes'].update(patient_names=dated(['A B'])),
            lambda d: d['classes'].update(phones=dated([5])),
            lambda d: d['classes'].update(id_numbers=dated(['00000000000'])),
            lambda d: d['classes'].update(patient_names=dated([{'given': '   ', 'family': 'Testperson'}])),
            lambda d: d['classes'].update(addresses=dated(['Example  Street 12'])),
            lambda d: d['classes'].update(phones=['+00 555 010 101']),                 # no date
            lambda d: d['classes'].update(phones=dated(['+00 555 010 101'], '2026-02-30')),
            lambda d: d['classes'].update(phones=dated(['+00 555 010 101'], '2999-01-01')),
            lambda d: d['classes'].update(phones=[{'value': '+00 555 010 101', 'since': SINCE, 'x': 1}]),
        ):
            d = json.loads(json.dumps(good))
            mutate(d)
            bad.append(d)
        for d in bad + ['not json', 'x' * (identity.MAX_BYTES + 1)]:
            self.put(d)
            with self.subTest(d=str(d)[:60]), self.assertRaises(Refused):
                identity.load(self.t.pdir)

    def test_the_old_format_names_its_way_out(self):
        d = identity.empty()
        d['version'] = 1
        d['classes']['phones'] = ['+00 555 010 101']
        self.put(d)
        with self.assertRaises(Refused) as cm:
            identity.load(self.t.pdir)
        self.assertIn('old format', str(cm.exception))
        self.assertNotIn('555', str(cm.exception))

    def test_errors_carry_no_value(self):
        d = identity.empty()
        d['classes']['phones'] = dated(['+00 555 010 101 ' + 'x' * 500])      # the invalid value holds the secret
        self.put(d)
        with self.assertRaises(Refused) as cm:
            identity.load(self.t.pdir)
        self.assertNotIn('555', str(cm.exception))


class Age(unittest.TestCase):
    CASES = [
        (D(1901, 2, 23), D(2026, 9, 30), '125 years 7 months'),
        (D(2000, 9, 30), D(2026, 9, 30), '26 years 0 months'),
        (D(2024, 9, 30), D(2026, 9, 29), '23 months 4 weeks'),
        (D(2025, 8, 10), D(2026, 9, 30), '13 months 2 weeks'),
        (D(2026, 8, 30), D(2026, 9, 30), '1 month 0 weeks'),
        (D(2026, 9, 20), D(2026, 9, 30), '10 days'),
        (D(2026, 9, 30), D(2026, 9, 30), '0 days'),
        (D(2024, 2, 29), D(2025, 2, 28), '12 months 0 weeks'),
        (D(2024, 2, 29), D(2025, 3, 1), '12 months 0 weeks'),
        (D(2026, 1, 31), D(2026, 4, 30), '3 months 0 weeks'),     # month-end birthdays (review 2026-10-01)
        (D(2026, 1, 31), D(2026, 3, 1), '1 month 0 weeks'),
        (D(2026, 1, 31), D(2026, 2, 27), '27 days'),
        (D(2024, 1, 31), D(2026, 1, 30), '23 months 4 weeks'),
        (D(2024, 1, 31), D(2026, 1, 31), '2 years 0 months'),
    ]

    def test_precision(self):
        for dob, on, want in self.CASES:
            with self.subTest(dob=dob, on=on):
                self.assertEqual(identity.age_text(dob, on), want)

    def test_whole_months_are_exact(self):
        # property, over every birth date of two years (leap day and month ends included) against
        # reference dates up to about three years on: the last monthly anniversary is not after the
        # reference date and the next one is
        dob = D(2023, 1, 1)
        while dob < D(2025, 1, 1):
            for off in range(0, 1100, 13):
                on = dob + datetime.timedelta(days=off)
                months, days = identity.age_parts(dob, on)
                with self.subTest(dob=dob, on=on):
                    self.assertLessEqual(identity.anniversary(dob, months), on)
                    self.assertGreater(identity.anniversary(dob, months + 1), on)
                    self.assertEqual(days, (on - identity.anniversary(dob, months)).days)
            dob += datetime.timedelta(days=1)

    def test_under_two_never_prints_days(self):
        # a day count with the reference date would give the date of birth away
        for off in range(31, 731):
            on = D(2024, 3, 15) + datetime.timedelta(days=off)
            with self.subTest(on=on):
                self.assertNotIn('day', identity.age_text(D(2024, 3, 15), on))

    def test_reference_before_birth_refused(self):
        with self.assertRaises(Refused):
            identity.age_text(D(2026, 9, 30), D(2026, 9, 29))

    def test_command_prints_age_and_reference_date_only(self):
        t = Tree()
        try:
            s = Script(twice('1901-02-23'))
            identity.cmd_set(t.root, t.handle, 'dob', s.ask, s.confirm, s.tell)
            out = Script([])
            identity.cmd_age(t.root, t.handle, out.tell, on=D(2026, 9, 30))
            self.assertEqual(out.printed(), 'age 125 years 7 months (reference date 2026-09-30)')
            # the command line takes no reference date: chosen dates would bisect the date of birth
            old, sys.stderr = sys.stderr, io.StringIO()
            try:
                rc = identity.main(['--root', t.root, 'age', t.handle, '--on', '2026-09-30'])
            finally:
                sys.stderr = old
            self.assertEqual(rc, identity.EXIT_USAGE)
        finally:
            t.close()

    def test_no_date_of_birth_refused(self):
        t = Tree()
        try:
            with self.assertRaises(Refused):
                identity.cmd_age(t.root, t.handle, Script([]).tell)
        finally:
            t.close()


class Status(unittest.TestCase):
    def test_reports_counts_never_values(self):
        t = Tree()
        try:
            s = Script(FULL)
            identity.cmd_set(t.root, t.handle, None, s.ask, s.confirm, s.tell)
            out = Script([])
            identity.cmd_status(t.root, t.handle, out.tell)
            text = out.printed()
            self.assertIn('kept from the AI besides the number: patient_names, dob, addresses, phones, emails', text)
            self.assertIn('dob 1', text)
            for v in SECRETS:
                self.assertNotIn(v, text)
            os.chmod(os.path.join(t.pdir, identity.IDENTITY_NAME), 0o644)
            out = Script([])
            identity.cmd_status(t.root, t.handle, out.tell)
            self.assertIn('chmod 600', out.printed())
        finally:
            t.close()

    def test_nothing_kept_without_an_identity_file(self):
        t = Tree()
        try:
            out = Script([])
            identity.cmd_status(t.root, t.handle, out.tell)
            self.assertIn('kept from the AI besides the number: nothing (no identity file)', out.printed())
        finally:
            t.close()


def seeded(tree, dob=True, since=SINCE, **extra):
    """Write a synthetic identity file for a Tree directly (no prompts); dob=False keeps the date of
    birth visible (not recorded)."""
    data = identity.empty()
    c = data['classes']
    c['patient_names'] = dated([{'given': GIVEN, 'family': FAMILY}], since)
    c['dob'] = dated(['1901-02-23'] if dob else [], since)
    c['phones'] = dated(['+00 555 010 101'], since)
    c['addresses'] = dated(['Example Street 12'], since)
    c['emails'] = dated(['synth@example.invalid'], since)
    c['other_names'] = dated([{'given': 'Relatia', 'family': 'Kinsperson'}], since)
    c['case_numbers'] = dated(['KX/2026/00417', '123'], since)
    for k, v in extra.items():
        c[k] = dated(v, since)
    identity.write(tree.pdir, data)
    prof = os.path.join(tree.pdir, 'profile.md')
    with open(prof, encoding='utf-8') as fh:
        text = fh.read()
    if identity.MARK in text and identity.kept(data):
        with open(prof, 'w', encoding='utf-8') as fh:
            fh.write(identity._with_sign(text))
    return identity.patterns(data)


def put(tree, rel, text, written=None):
    """Write a synthetic file. A dated name is taken as written on its date (the scan uses the later of
    the two), unless `written` gives the day it was last written."""
    path = os.path.join(tree.pdir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    day = written or identity._path_date(rel)
    if day is not None and day <= D.today():
        ts = datetime.datetime(day.year, day.month, day.day, 12).timestamp()
        os.utime(path, (ts, ts))
    return path


class Matcher(unittest.TestCase):
    """Whole values only, in the forms documents print them (control C2)."""

    def setUp(self):
        self.t = Tree()
        self.pats = seeded(self.t)

    def tearDown(self):
        self.t.close()

    def hits(self, text, pats=None):
        return identity.residue(text, pats or self.pats)

    def test_fires(self):
        cases = {
            'Patient: Synthia Maria Testperson': 'patient_names',
            'TESTPERSON SYNTHIA MARIA, ward 3': 'patient_names',
            'Testperson, Synthia': 'patient_names',
            'seen with Synthia Testperson today': 'patient_names',
            'born 23.02.1901 r.': 'dob',
            'DOB 1901-02-23': 'dob',
            'ur. 23/02/1901': 'dob',
            'tel. +00 555-010-101': 'phones',
            'tel 555010101': 'phones',
            'lives at example street 12, flat 3': 'addresses',
            'mail Synth@Example.invalid': 'emails',
            'relative Relatia Kinsperson called': 'other_names',
            'case KX 2026 00417': 'case_numbers',
        }
        for text, cls in cases.items():
            with self.subTest(text=text):
                self.assertIn(cls, self.hits(text))

    def test_fires_on_printed_variants(self):
        # forms PDFs, OCR and Markdown produce (review 2026-10-01)
        cases = {
            '_Synthia Testperson_': 'patient_names',
            '**Synthia** **Testperson**': 'patient_names',
            '| Synthia |  Testperson |': 'patient_names',
            'tel. +00 (555) 010 101': 'phones',
            'tel. 555–010–101': 'phones',
            'born 23-2-1901': 'dob', 'born 1901-2-23': 'dob', 'born 23. 02. 1901': 'dob',
            'born 23 02 1901': 'dob', 'DOB 02/23/1901': 'dob', 'DOB 19010223': 'dob',
            'ur. 23.02.01': 'dob', 'ur. 23–02–1901': 'dob',
            '_synth@example.invalid_': 'emails',
            'Exämpla Fäkename called': 'other_names',
            'Exampla Fakename called': 'other_names',
            'Exämpla Fäkename called': 'other_names',
            'Łorem Ipsąm visits': 'other_names',
            'Lorem Ipsam visits': 'other_names',
            'order 12345': 'case_numbers',
        }
        t = Tree()
        try:
            pats = seeded(t, other_names=[{'given': 'Exämpla', 'family': 'Fäkename'}, {'given': 'Łorem', 'family': 'Ipsąm'}],
                          case_numbers=['12345', '1234'])
            for text, cls in cases.items():
                with self.subTest(text=text):
                    self.assertIn(cls, self.hits(text, pats))
            self.assertEqual(self.hits('order 1234', pats), {})     # under five characters: not looked for
        finally:
            t.close()

    def test_does_not_fire(self):
        for text in ('Synthia came in', 'Dr Testperson (clinic)', 'dose 23.02 mg', '11901-02-235',
                     'order 1234', 'call 555 010 1019', 'Example Street 120', 'case 123 of 456',
                     'ratio 23.02.011', '2150-02-23', 'Synthia\n\nTestperson'.split('\n')[0],
                     '⟨withheld:patient-name⟩, born ⟨withheld:date-of-birth⟩'):
            with self.subTest(text=text):
                self.assertEqual(self.hits(text), {})

    def test_waiver_and_dob_exemption(self):
        self.assertEqual(self.hits('Synthia Testperson (pharmacist) ⟨not-an-id: verified 2026-10-01⟩'), {})
        t = Tree()
        try:
            self.assertEqual(self.hits('born 23.02.1901', seeded(t, dob=False)), {})
        finally:
            t.close()

    def test_substitute_replaces_every_form_and_keeps_waived_lines(self):
        text = ('Name: Synthia Testperson, born 23.02.1901\n'
                'phone +00 555 010 101\n'
                'Synthia Testperson (namesake) ⟨not-an-id: verified 2026-10-01⟩\n')
        new, counts, refs = identity.substitute(text, self.pats)
        self.assertEqual(refs, 0)
        self.assertEqual(new.splitlines()[0], 'Name: ⟨withheld:patient-name⟩, born ⟨withheld:date-of-birth⟩')
        self.assertEqual(new.splitlines()[1], 'phone ⟨withheld:phone⟩')
        self.assertEqual(new.splitlines()[2], text.splitlines()[2])
        self.assertEqual(counts, {'patient_names': 1, 'dob': 1, 'phones': 1})
        self.assertEqual(self.hits(new), {})


def ledger(tree, *records):
    body = ''.join(json.dumps(r) + '\n' for r in records)
    put(tree, 'med/MANIFEST', body)


def rec(rid, src, review, deriv=None, supersedes=''):
    return {'record_id': rid, 'source_relpath': src, 'review_date': review, 'supersedes': supersedes,
            'derivatives': [{'derivative_relpath': deriv, 'derivative_sha256': '0' * 64}] if deriv else []}


class Scope(unittest.TestCase):
    CUT = D(2026, 10, 1)

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def scope(self):
        return dict(scoped(self.t.pdir, self.CUT.isoformat()))

    def written_on(self, path, day):
        ts = datetime.datetime(day.year, day.month, day.day, 12).timestamp()
        os.utime(path, (ts, ts))

    def test_dated_and_working_record(self):
        put(self.t, 'medications.md', 'x')
        put(self.t, 'med/analysis/2026-09-30__old.md', 'x')
        put(self.t, 'med/analysis/2026-10-01__new.md', 'x')
        put(self.t, 'med/handouts/patient/2026-10-05__visit/handout.md', 'x')     # a draft: its path dates it
        put(self.t, 'med/handouts/patient/2026-09-05__visit/handout.md', 'x')
        put(self.t, 'med/analysis/2026-10-05-visit/2026-09-01__prep.md', 'x')     # the latest date in the path
        self.written_on(put(self.t, 'med/sources/README.md', 'x'), D(2026, 9, 1))
        self.written_on(put(self.t, 'med/analysis/tk-notes.md', 'x'), D(2026, 10, 3))  # undated, written later
        put(self.t, 'nmed/2026-10-03__letter.md', 'x')
        s = self.scope()
        self.assertEqual(set(s), {'profile.md', 'medications.md', 'med/analysis/2026-10-01__new.md',
                                  'med/handouts/patient/2026-10-05__visit/handout.md',
                                  'med/analysis/2026-10-05-visit/2026-09-01__prep.md',
                                  'med/analysis/tk-notes.md'})

    def test_sealed_handout_dated_by_its_seal(self):
        # a handout sealed before the cutover for a later appointment is legacy: its sealed bytes can
        # never be edited (review 2026-10-01); one sealed after is in scope
        early = put(self.t, 'med/handouts/patient/2026-10-30__clinic-a/2026-10-30__handout-patient__x.md', 'x')
        put(self.t, early[:-3] + '.attest.json', json.dumps({'timestamp': '2026-09-28T10:00:00+00:00'}))
        late = put(self.t, 'med/handouts/patient/2026-09-10__clinic-b/2026-09-10__handout-patient__y.md', 'x')
        put(self.t, late[:-3] + '.attest.json', json.dumps({'timestamp': '2026-10-02T10:00:00+00:00'}))
        s = self.scope()
        self.assertNotIn('med/handouts/patient/2026-10-30__clinic-a/2026-10-30__handout-patient__x.md', s)
        self.assertEqual(s['med/handouts/patient/2026-09-10__clinic-b/2026-09-10__handout-patient__y.md'],
                         'a handout sealed after that detail was recorded')

    def test_filed_on_the_cutover_day_and_ledger_wins_over_the_name(self):
        on_day = 'med/sources/2019-01-01__letter__a.ocr.md'
        future = 'med/sources/2026-11-30__referral__b.ocr.md'     # a future-dated letter filed earlier
        migrated = 'med/sources/2019-02-01__letter__c.ocr.md'
        for rel in (on_day, future, migrated):
            put(self.t, rel, 'x')
        m = rec('e5e5e5e5', 'med/sources/2019-02-01__letter__c.pdf', '2026-10-05', migrated)
        m['identity_source'] = 'legacy migration 2026-10-05 — folder position only, unverified'
        ledger(self.t, rec('a1a1a1a1', 'med/sources/2019-01-01__letter__a.pdf', '2026-10-01', on_day),
               rec('b2b2b2b2', 'med/sources/2026-11-30__referral__b.pdf', '2026-09-15', future), m)
        s = self.scope()
        self.assertIn(on_day, s)
        self.assertNotIn(future, s)
        self.assertNotIn(migrated, s)

    def test_unlistable_folder_refused(self):
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            self.skipTest('mode bits do not deny root')
        locked = os.path.join(self.t.pdir, 'med', 'locked')
        os.makedirs(locked)
        os.chmod(locked, 0)
        try:
            with self.assertRaises(Refused):
                self.scope()
        finally:
            os.chmod(locked, 0o700)

    def test_filing_date_from_the_ledger(self):
        # an old letter filed after cutover is in scope; one filed before is legacy; a rename after
        # cutover keeps the original filing date (operator, 2026-10-01)
        old_new = 'med/sources/2019-03-01__letter__gp.ocr.md'
        old_old = 'med/sources/2019-04-01__letter__gp.ocr.md'
        renamed = 'med/sources/2019-05-01__letter__gp-renamed.ocr.md'
        for rel in (old_new, old_old, renamed):
            put(self.t, rel, 'x')
        ledger(self.t,
               rec('a1a1a1a1', 'med/sources/2019-03-01__letter__gp.pdf', '2026-10-02', old_new),
               rec('b2b2b2b2', 'med/sources/2019-04-01__letter__gp.pdf', '2026-09-20', old_old),
               rec('c3c3c3c3', 'med/sources/2019-05-01__letter__gp.pdf', '2026-09-21'),
               rec('d4d4d4d4', 'med/sources/2019-05-01__letter__gp-renamed.pdf', '2026-10-09', renamed,
                   supersedes='c3c3c3c3'))
        s = self.scope()
        self.assertIn(old_new, s)
        self.assertNotIn(old_old, s)
        self.assertNotIn(renamed, s)

    def test_a_transcription_bound_late_is_dated_by_its_binding(self):
        # `append … transcribe` (ADR-0037 §14) binds new text to an original filed, or migrated,
        # before the cutover: the text is dated by the binding, so it is scanned; the original keeps
        # its filing date (negative control: the same chain bound before the cutover stays legacy)
        late_mig, late_add, early = ('med/sources/2019-06-01__letter__m.ocr.md',
                                     'med/sources/2019-07-01__letter__n.ocr.md',
                                     'med/sources/2019-08-01__letter__o.ocr.md')
        for rel in (late_mig, late_add, early, 'med/sources/2019-07-01__letter__n.md'):
            put(self.t, rel, 'x')
        m = rec('e5e5e5e5', 'med/sources/2019-06-01__letter__m.pdf', '2026-07-01')
        m['identity_source'] = 'legacy migration 2026-07-01 — folder position only, unverified'
        t1 = rec('f6f6f6f6', 'med/sources/2019-06-01__letter__m.pdf', '2026-07-01', late_mig, 'e5e5e5e5')
        t1.update(supersede_reason='transcribe', supersede_date='2026-10-03')
        n = rec('a7a7a7a7', 'med/sources/2019-07-01__letter__n.md', '2026-09-01')
        t2 = rec('b8b8b8b8', 'med/sources/2019-07-01__letter__n.md', '2026-09-01', late_add, 'a7a7a7a7')
        t2.update(supersede_reason='transcribe', supersede_date='2026-10-04')
        conf = dict(t2, record_id='c9c9c9c9', supersedes='b8b8b8b8', supersede_reason='status-change',
                    supersede_date='2026-10-05')
        o = rec('d0d0d0d0', 'med/sources/2019-08-01__letter__o.pdf', '2026-08-01')
        t3 = rec('e1e1e1e1', 'med/sources/2019-08-01__letter__o.pdf', '2026-08-01', early, 'd0d0d0d0')
        t3.update(supersede_reason='transcribe', supersede_date='2026-09-02')
        ledger(self.t, m, t1, n, t2, conf, o, t3)
        s = self.scope()
        self.assertIn(late_mig, s)
        self.assertIn(late_add, s)
        self.assertNotIn('med/sources/2019-07-01__letter__n.md', s)    # the original: filed 2026-09-01
        self.assertNotIn(early, s)

    def test_a_backdated_binding_is_dated_no_earlier_than_the_filing(self):
        # a hand-written `transcribe` row dated before its original's filing (after the cutover) would
        # otherwise date new text out of scope; the filing date is the floor
        rel = 'med/sources/2019-09-01__letter__p.ocr.md'
        put(self.t, rel, 'x')
        p = rec('f1f1f1f1', 'med/sources/2019-09-01__letter__p.pdf', '2026-10-05')
        t = rec('f2f2f2f2', 'med/sources/2019-09-01__letter__p.pdf', '2026-10-05', rel, 'f1f1f1f1')
        t.update(supersede_reason='transcribe', supersede_date='2026-09-02')
        ledger(self.t, p, t)
        self.assertIn(rel, self.scope())

    def test_a_layer_re_made_by_a_rehash_is_dated_by_it(self):
        # a rehash after the cutover that brings a new transcription is new text (in scope); one that
        # carries the transcription unchanged keeps the filing date (the negative control)
        new_layer, same_layer = ('med/sources/2019-10-01__letter__q.ocr.md',
                                 'med/sources/2019-11-01__letter__r.ocr.md')
        for rel in (new_layer, same_layer):
            put(self.t, rel, 'x')
        q = rec('a3a3a3a3', 'med/sources/2019-10-01__letter__q.pdf', '2026-08-01', new_layer)
        q2 = rec('a4a4a4a4', 'med/sources/2019-10-01__letter__q.pdf', '2026-08-01', new_layer, 'a3a3a3a3')
        q2['derivatives'][0]['derivative_sha256'] = '1' * 64
        q2.update(supersede_reason='rehash', supersede_date='2026-10-06')
        r1 = rec('a5a5a5a5', 'med/sources/2019-11-01__letter__r.pdf', '2026-08-01', same_layer)
        r2 = rec('a6a6a6a6', 'med/sources/2019-11-01__letter__r.pdf', '2026-08-01', same_layer, 'a5a5a5a5')
        r2.update(supersede_reason='rehash', supersede_date='2026-10-06')
        ledger(self.t, q, q2, r1, r2)
        s = self.scope()
        self.assertIn(new_layer, s)
        self.assertNotIn(same_layer, s)

    def test_unreadable_ledger_refused(self):
        put(self.t, 'med/MANIFEST', '{"torn": ')
        with self.assertRaises(Refused):
            self.scope()


class ScanAndSwap(unittest.TestCase):
    def setUp(self):
        self.t = Tree()
        seeded(self.t)

    def tearDown(self):
        self.t.close()

    def findings(self):
        return identity.scan_tree(self.t.root)

    def test_clean_record_scans_green(self):
        self.assertEqual(self.findings(), [])

    def test_findings_are_category_only(self):
        put(self.t, 'medications.md', 'For Synthia Testperson, born 23.02.1901\n')
        put(self.t, 'med/analysis/2026-10-02__note.md', 'mail synth@example.invalid\n')
        put(self.t, 'med/analysis/2026-09-02__legacy.md', 'Synthia Testperson, Example Street 12\n')
        f = self.findings()
        self.assertEqual(len(f), 3, f)
        text = '\n'.join(f)
        for v in SECRETS + [self.t.handle, 'analysis', 'medications.md']:
            self.assertNotIn(v, text)
        self.assertIn('the medication list', text)

    def test_fail_closed(self):
        # placeholders in the working record mean details are kept: a lost identity file reds, it
        # never switches the scan off
        put(self.t, 'medications.md', 'For ⟨withheld:patient-name⟩\n')
        os.unlink(os.path.join(self.t.pdir, identity.IDENTITY_NAME))
        f = '\n'.join(self.findings())
        self.assertIn('identity file is missing', f)
        self.assertIn('restore it from the latest snapshot', f)
        put(self.t, 'medications.md', 'For Synthia Testperson\n')
        self.assertIn('identity file is missing', '\n'.join(self.findings()))   # the sign alone is enough
        put(self.t, 'profile.md', profile_text(V1_LINE))                       # no sign, no placeholder:
        self.assertEqual(self.findings(), [])                                  # nothing kept
        put(self.t, 'profile.md', profile_text(V1_LINE) + '- Born: ⟨withheld:date-of-birth⟩\n')
        self.assertIn('identity file is missing', '\n'.join(self.findings()))

    def test_a_value_counts_from_the_day_it_was_recorded(self):
        # a detail added later never reds text written before it (operator, 2026-11-09)
        data = identity.load(self.t.pdir)
        identity.add(data, 'phones', ['+00 555 030 303'], D(2026, 10, 20))
        identity.write(self.t.pdir, data)
        put(self.t, 'med/analysis/2026-10-10__note.md', 'call +00 555 030 303\n')
        self.assertEqual(self.findings(), [])
        put(self.t, 'med/analysis/2026-10-20__note.md', 'call +00 555 030 303\n')
        self.assertEqual(len(self.findings()), 1)
        put(self.t, 'medications.md', 'call +00 555 030 303\n')     # the working record always
        self.assertEqual(len(self.findings()), 2)

    def test_a_note_named_for_an_old_letter_but_written_today_counts(self):
        # cold review 2026-11-09; operator, same day: the later of the name's date and the last write
        put(self.t, 'med/analysis/2025-03-01__old-letter-summary.md', 'Synthia Testperson\n')
        self.assertEqual(self.findings(), [])
        put(self.t, 'med/analysis/2025-03-01__old-letter-summary.md', 'Synthia Testperson\n', written=D.today())
        self.assertEqual(len(self.findings()), 1)

    def test_placeholders_in_a_folder_without_a_profile_red(self):
        os.unlink(os.path.join(self.t.pdir, 'profile.md'))
        put(self.t, 'medications.md', 'For ⟨withheld:patient-name⟩\n')
        self.assertIn('without a profile', '\n'.join(self.findings()))

    def test_nothing_kept_person_untouched(self):
        t = Tree(line=V1_LINE, handle='szt-number-only')
        try:
            put(t, 'medications.md', 'For Synthia Testperson\n')
            self.assertEqual(identity.scan_tree(t.root), [])
        finally:
            t.close()

    def test_swap_changes_the_working_record_only(self):
        with open(os.path.join(self.t.pdir, 'profile.md'), 'a', encoding='utf-8') as fh:
            fh.write('- Date of birth / age: 1901-02-23\n- Contact: +00 555 010 101\n')
        meds = put(self.t, 'medications.md', 'Prescribed for Testperson Synthia Maria\n')
        os.chmod(meds, 0o640)
        legacy = put(self.t, 'med/analysis/2026-09-02__legacy.md', 'Synthia Testperson\n')
        self.assertEqual(len(self.findings()), 3)
        out = Script([])
        identity.cmd_swap(self.t.root, self.t.handle, out.tell)
        self.assertEqual(self.findings(), [])
        for v in SECRETS:
            self.assertNotIn(v, out.printed())
        self.assertIn('profile.md: dob 1 · phones 1', out.printed().replace('patient_names', 'x'))
        with open(meds, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'Prescribed for ⟨withheld:patient-name⟩\n')
        self.assertEqual(stat.S_IMODE(os.stat(meds).st_mode), 0o640)
        with open(legacy, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'Synthia Testperson\n')          # history stays as it is
        self.assertEqual(sorted(n for n in os.listdir(self.t.pdir) if n.endswith('.tmp')), [])
        again = Script([])
        identity.cmd_swap(self.t.root, self.t.handle, again.tell)
        self.assertIn('nothing to replace', again.printed())

    def test_dropped_marker_reds(self):
        # the identity file stays; a rewrite of the private-mode line lost the marker
        with open(os.path.join(self.t.pdir, 'profile.md'), 'w', encoding='utf-8') as fh:
            fh.write(profile_text('- Private mode: none') + '- Name / role: Synthia Testperson\n')
        f = '\n'.join(self.findings())
        self.assertIn('carries no private-mode marker', f)
        self.assertNotIn('Synthia', f)

    def test_prose_and_the_retired_tag_configure_nothing(self):
        for line in ('- Private mode: none\n- note: we considered private-v2, maybe later',
                     V1_LINE + '\n- Level: private-v1 (the designated identifier only)',
                     V1_LINE + ' · ⟨private-v2 cutover=2026-10-01⟩'):
            t = Tree(line=line, handle='szt-prose')
            try:
                with self.subTest(line=line):
                    self.assertEqual(identity.scan_tree(t.root), [])
            finally:
                t.close()

    def test_swap_keeps_line_endings_and_is_atomic(self):
        meds = os.path.join(self.t.pdir, 'medications.md')
        with open(meds, 'wb') as fh:
            fh.write(b'# Medications\r\nFor Synthia Testperson\r\n')
        real = identity.os.replace
        identity.os.replace = lambda a, b: (_ for _ in ()).throw(OSError('synthetic failure'))
        try:
            with self.assertRaises(Refused) as cm:
                identity.cmd_swap(self.t.root, self.t.handle, Script([]).tell)
        finally:
            identity.os.replace = real
        self.assertIn('run swap again', str(cm.exception))
        with open(meds, 'rb') as fh:
            self.assertEqual(fh.read(), b'# Medications\r\nFor Synthia Testperson\r\n')
        self.assertEqual([n for n in os.listdir(self.t.pdir) if n.endswith('.tmp')], [])
        identity.cmd_swap(self.t.root, self.t.handle, Script([]).tell)
        with open(meds, 'rb') as fh:
            self.assertEqual(fh.read(), b'# Medications\r\nFor \xe2\x9f\xa8withheld:patient-name\xe2\x9f\xa9\r\n')

    def test_scan_crash_is_never_read_as_residue(self):
        real = identity.scan_tree
        identity.scan_tree = lambda root: [][1]
        err, old = io.StringIO(), sys.stderr
        sys.stderr = err
        try:
            rc = identity.main(['--root', self.t.root, 'scan'])
        finally:
            identity.scan_tree, sys.stderr = real, old
        self.assertEqual(rc, identity.EXIT_REFUSED)
        self.assertIn('internal error', err.getvalue())

    def test_swap_refuses_without_marker_or_identity(self):
        t = Tree(line='- Private mode: none', handle='szt-none')
        try:
            with self.assertRaises(Refused):
                identity.cmd_swap(t.root, t.handle, Script([]).tell)
        finally:
            t.close()
        os.unlink(os.path.join(self.t.pdir, identity.IDENTITY_NAME))
        with self.assertRaises(Refused):
            identity.cmd_swap(self.t.root, self.t.handle, Script([]).tell)


class CodexReview(unittest.TestCase):
    """Regressions for the review of 2026-10-01 on the residue guard (each reproduced first)."""

    def setUp(self):
        self.t = Tree()
        self.pats = seeded(self.t)

    def tearDown(self):
        self.t.close()

    def test_new_filing_counts_even_unconfirmed_and_migration_does_not(self):
        # end to end through the ownership tools: a migrated legacy source carries no filing date; a
        # source appended after the details were recorded is in scope, unconfirmed or later confirmed
        from tools.person_ownership import append
        put(self.t, 'med/sources/2019-01-01__letter__old.pdf', '%PDF synthetic\n')
        put(self.t, 'med/sources/2019-01-01__letter__old.ocr.md', 'Synthia Testperson (legacy)\n')
        append.init_ledger(self.t.root, self.t.handle, today='2026-10-05')     # migration after recording
        put(self.t, 'med/sources/2019-03-01__letter__gp.pdf', '%PDF synthetic\n')
        put(self.t, 'med/sources/2019-03-01__letter__gp.ocr.md', 'Patient: Synthia Testperson\n')
        append.add_source(self.t.root, self.t.handle, 'med/sources/2019-03-01__letter__gp.pdf', today='2026-10-02')
        f = identity.scan_tree(self.t.root)
        self.assertEqual(len(f), 1, f)
        self.assertIn('a transcription filed after that detail was recorded', f[0])
        append.confirm(self.t.root, self.t.handle, 'med/sources/2019-03-01__letter__gp.pdf', today='2026-10-03')
        self.assertEqual(len(identity.scan_tree(self.t.root)), 1)

    def test_decomposed_file_name_still_finds_its_filing_date(self):
        nfc = 'med/sources/2019-03-01__letter__zoë.ocr.md'
        nfd = unicodedata.normalize('NFD', nfc)
        put(self.t, nfd, 'Patient: Synthia Testperson\n')
        ledger(self.t, rec('a1a1a1a1', 'med/sources/2019-03-01__letter__zoë.pdf', '2026-10-02', nfc))
        f = identity.scan_tree(self.t.root)
        self.assertTrue(any('a transcription filed after that detail was recorded' in x for x in f), f)

    def test_the_longest_matched_value_wins(self):
        t = Tree(handle='szt-overlap')
        try:
            pats = seeded(t, id_numbers=['19010223AB12345'],
                          other_names=[{'given': 'Synthia Ann', 'family': 'Testperson'}],
                          emails=['synthia.ann.testperson@example.invalid'])
            new, counts, refs = identity.substitute('ID 19010223AB12345; mail synthia.ann.testperson@example.invalid\n', pats)
            self.assertEqual(new, 'ID ⟨withheld:id-number⟩; mail ⟨withheld:email⟩\n')
            self.assertEqual(identity.residue(new, pats), {})
        finally:
            t.close()

    def test_numbers_never_match_inside_alphanumeric_fields(self):
        t = Tree(handle='szt-hex')
        try:
            pats = seeded(t, case_numbers=['12345'])
            pid = 'a12345' + 'bc' * 13
            line = '- **Person record ID (local-only integrity key):** `%s`\n' % pid
            self.assertEqual(identity.residue('ref a12345bc and %s' % line, pats), {})
            self.assertEqual(identity.substitute(line, pats)[0], line)
            self.assertIn('case_numbers', identity.residue('case 12345.', pats))
        finally:
            t.close()

    def test_fact_check_sidecar_shares_its_units_seal(self):
        unit = 'med/handouts/clinician/2026-10-30__clinic-a/'
        stem = unit + '2026-10-30__handout-clinician__x'
        put(self.t, stem + '.md', 'x')
        put(self.t, stem + '.factcheck.md', 'checked for Synthia Testperson')
        put(self.t, stem + '.attest.json', json.dumps({'timestamp': '2026-09-28T10:00:00+00:00'}))
        s = dict(scoped(self.t.pdir))
        self.assertNotIn(stem + '.md', s)
        self.assertNotIn(stem + '.factcheck.md', s)

    def test_slashes_and_bold_are_not_file_references(self):
        # certification review 2026-10-01: a date, a flat number, a case number or Markdown bold is not
        # a file; the swap replaces them, and the scan's next step is the placeholder, not a rename
        t = Tree(handle='szt-slash')
        try:
            seeded(t, addresses=['Example Street 12/3'], case_numbers=['KX/2026/00417'])
            prof = os.path.join(t.pdir, 'profile.md')
            with open(prof, 'a', encoding='utf-8') as fh:
                fh.write('- born 23/02/1901; lives at Example Street 12/3; case KX/2026/00417\n'
                         '- __Synthia Testperson__\n')
            self.assertNotIn('rename', '\n'.join(identity.scan_tree(t.root)))
            identity.cmd_swap(t.root, t.handle, Script([]).tell)
            with open(prof, encoding='utf-8') as fh:
                text = fh.read()
            self.assertIn('- born ⟨withheld:date-of-birth⟩; lives at ⟨withheld:address⟩; case '
                          '⟨withheld:case-number⟩\n- __⟨withheld:patient-name⟩__\n', text)
            self.assertEqual(identity.scan_tree(t.root), [])
        finally:
            t.close()

    def test_link_targets_are_references_and_mid_text_folders_are_not(self):
        # certification nit 2026-10-01: any Markdown link target refuses; prose naming a folder does not
        for target in ('Synthia_Testperson.md#sec', 'Synthia_Testperson.csv', 'letters/Synthia_Testperson'):
            line = '- [letter](%s)\n' % target
            with self.subTest(target=target):
                self.assertEqual(identity.substitute(line, self.pats)[2], 1)
        self.assertEqual(identity.substitute('- see Synthia_Testperson.md#sec\n', self.pats)[2], 1)
        for line in ('- see analysis/ notes on Synthia Testperson\n', '- Synthia Testperson analysis/notes\n'):
            with self.subTest(line=line):
                new, counts, refs = identity.substitute(line, self.pats)
                self.assertEqual((refs, counts), (0, {'patient_names': 1}))

    def test_repeated_names_leave_no_fragment(self):
        # Codex rereview 2026-10-01: the reverse-order pattern matched across the comma and the two
        # whole names were dropped, leaving `Synthia ⟨…⟩ Testperson`
        for line in ('Synthia Testperson, Synthia Testperson\n', '| Synthia Testperson | Synthia Testperson |\n',
                     'Testperson Synthia Testperson\n'):
            with self.subTest(line=line):
                new, counts, refs = identity.substitute(line, self.pats)
                self.assertNotIn('Synthia', new)
                self.assertNotIn('Testperson', new)
                self.assertEqual(identity.residue(new, self.pats), {})

    def test_link_destination_with_parentheses_is_one_reference(self):
        for line in ('- [source](med/sources/2020-02-23__clinic__letter_(Synthia_Testperson).md)\n',
                     '- [source](<med/sources/letter Synthia Testperson.md>)\n',
                     '[src]: med/sources/2020-02-23__clinic__Synthia_Testperson.md\n'):
            with self.subTest(line=line):
                self.assertEqual(identity.substitute(line, self.pats)[2], 1)
        self.assertEqual(identity.substitute('- see med/sources/letter_(Synthia_Testperson).md\n', self.pats)[2], 1)
        new = identity.substitute('- (Synthia Testperson) attended\n', self.pats)[0]
        self.assertEqual(new, '- (⟨withheld:patient-name⟩) attended\n')     # prose in parentheses is not a file

    def test_integrity_keys_are_never_matched(self):
        t = Tree(handle='szt-key')
        try:
            pats = seeded(t, phones=['555 010 101'])
            pid = 'a555010101' + 'bc' * 11
            line = '- **Person record ID (local-only integrity key):** `%s`\n' % pid
            self.assertEqual(identity.residue(line + 'sha256 %s\n' % ('0555010101' + 'f' * 54), pats), {})
            self.assertEqual(identity.substitute(line, pats)[0], line)
            self.assertIn('phones', identity.residue('tel 555 010 101', pats))
        finally:
            t.close()

    def test_values_holding_a_hex_run_are_still_found(self):
        # certification review 2026-10-01: only a match strictly inside an integrity key is dropped
        h = 'c0ffee' + '0123456789abcdef' * 2
        t = Tree(handle='szt-hexval')
        try:
            pats = seeded(t, id_numbers=[h], emails=[h + '@example.invalid'], case_numbers=['ORD-' + h])
            for text, cls in (('doc id %s' % h, 'id_numbers'), ('mail %s@example.invalid' % h, 'emails'),
                              ('order ORD-%s' % h, 'case_numbers')):
                with self.subTest(text=text):
                    self.assertIn(cls, identity.residue(text, pats))
            self.assertEqual(identity.substitute('see Synthia_Testperson_%s.pdf\n' % h, pats)[2], 2)   # name and ID
        finally:
            t.close()

    def test_recall_kept_where_letters_touch_a_date_or_phone(self):
        for text, cls in (('ur. 23.02.1901r.', 'dob'), ('1901-02-23T00:00:00Z', 'dob'),
                          ('DOB23.02.1901', 'dob'), ('tel555010101', 'phones'), ('555-010-101ext', 'phones')):
            with self.subTest(text=text):
                self.assertIn(cls, identity.residue(text, self.pats))
        self.assertEqual(identity.residue('id a19010223bc', self.pats), {})      # compact date stays bounded
        t = Tree(handle='szt-phone')
        try:                                      # a phone without a country code, glued to letters
            self.assertIn('phones', identity.residue('tel601234567ext', seeded(t, phones=['601 234 567'])))
        finally:
            t.close()

    def test_swap_refuses_to_break_a_file_reference(self):
        prof = os.path.join(self.t.pdir, 'profile.md')
        with open(prof, 'a', encoding='utf-8') as fh:
            fh.write('- Name / role: Synthia Testperson\n'
                     '- Evidence: [letter](med/sources/2020-02-23__clinic__Synthia_Testperson.md)\n')
        with open(prof, 'rb') as fh:
            before = fh.read()
        with self.assertRaises(Refused) as cm:
            identity.cmd_swap(self.t.root, self.t.handle, Script([]).tell)
        self.assertIn('rename those files', str(cm.exception))
        with open(prof, 'rb') as fh:
            self.assertEqual(fh.read(), before)                      # nothing changed
        f = '\n'.join(identity.scan_tree(self.t.root))
        self.assertIn('1 inside a file name or link', f)
        self.assertNotIn('Testperson', f)


class Main(unittest.TestCase):
    def test_set_refuses_without_a_terminal(self):
        # answers would be available, so only the terminal check can refuse (review 2026-10-01)
        t = Tree()
        err = io.StringIO()
        saved = sys.stdin, sys.stderr, identity.getpass.getpass
        sys.stdin, sys.stderr = io.StringIO('y\n'), err
        identity.getpass.getpass = lambda prompt='': '+00 555 010 101'
        try:
            rc = identity.main(['--root', t.root, 'set', t.handle, 'phones'])
        finally:
            sys.stdin, sys.stderr, identity.getpass.getpass = saved
            self.assertFalse(os.path.exists(os.path.join(t.pdir, identity.IDENTITY_NAME)))
            t.close()
        self.assertEqual(rc, identity.EXIT_REFUSED)
        self.assertIn('own terminal', err.getvalue())

    def test_usage(self):
        err = io.StringIO()
        old, sys.stderr = sys.stderr, err
        try:
            self.assertEqual(identity.main(['nope']), identity.EXIT_USAGE)
            self.assertEqual(identity.main(['set']), identity.EXIT_USAGE)
        finally:
            sys.stderr = old



class IdSchemes(unittest.TestCase):
    """The private-mode number list and the profile tag that names a person's schemes (ADR-0062)."""

    def table(self, body):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = os.path.join(d.name, 't.tsv')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# comment\n' + body)
        return path

    def test_shipped_list_loads_and_no_tag_searches_every_row(self):
        t = S.load()
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE), t), list(t))
        for row in t.values():
            self.assertTrue(row['lang'] and row['words'])

    def test_malformed_lists_are_refused(self):
        for body in ('', 'a\tb\tc\n', 'k\tl\t[0-9]{3}\tw\nk\tl\t[0-9]{4}\tw\n', 'K\tl\t[0-9]{3}\tw\n',
                     'k\tl\t[0-9\tw\n', 'k\tl\t[0-9]*\tw\n', 'k\tl\t [0-9]{3}\tw\n',
                     'unlisted\tl\t[0-9]{3}\tw\n'):                    # the reserved key is no row
            with self.assertRaises(S.SchemeError, msg=repr(body)):
                S.load(self.table(body))
        with self.assertRaises(S.SchemeError):
            S.load(os.path.join(HERE, 'no-such-list.tsv'))

    def test_tag_names_one_or_several_schemes_and_unions_their_shapes(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb-c\tl\tX[0-9]{3}\tsecond\n'))
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE), t), ['aa', 'bb-c'])      # no tag: every row
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme bb-c⟩'), t), ['bb-c'])
        keys = S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme bb-c,aa,bb-c⟩'), t)
        self.assertEqual(keys, ['bb-c', 'aa'])
        rx = S.residue_re(keys, t)
        self.assertTrue(rx.search('n 12345 n') and rx.search('n X123 n'))
        self.assertIsNone(rx.search('n 1234 Y123 n'))

    def test_unreadable_tags_refuse_never_read_as_absent(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\n'))
        for text in (profile_text(V1_LINE + ' ⟨id-scheme zz⟩'),                    # unknown key
                     profile_text(V1_LINE + ' ⟨id-scheme AA⟩'),                    # malformed
                     profile_text(V1_LINE + ' ⟨id-scheme aa⟩ ⟨id-scheme aa⟩'),     # repeated on the line
                     profile_text(V1_LINE + ' ⟨id-scheme aa⟩') + '- quoted ⟨never-API⟩ ⟨id-scheme aa⟩\n'):
            with self.assertRaises(S.SchemeError, msg=text):
                S.profile_schemes(text, t)

    def test_a_tag_outside_the_identity_section_is_plain_text(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[0-9]{3}\tsecond\n'))
        log = '\n## Change log\n- 2026-01-02 set %s\n'
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE) + log % '⟨id-scheme bb⟩', t), ['aa', 'bb'])
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme bb⟩') + log % '⟨id-scheme zz⟩', t),
                         ['bb'])
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme bb⟩') + log % '⟨ID scheme aa⟩', t),
                         ['bb'])

    def test_a_tag_off_the_marker_line_in_the_identity_section_is_refused(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[0-9]{3}\tsecond\n'))
        for text in (profile_text(V1_LINE) + '  ⟨id-scheme bb⟩\n',                     # wrapped onto the next line
                     profile_text(V1_LINE + ' ⟨id-scheme bb⟩') + '- was ⟨id-scheme aa⟩\n',
                     '# P\n\n## Identity\n- ⟨id-scheme bb⟩\n%s\n' % V1_LINE):
            with self.assertRaises(S.SchemeError, msg=text) as cm:
                S.profile_schemes(text, t)
            self.assertIn('not on the line carrying', str(cm.exception))

    def test_a_mistyped_tag_on_the_marker_line_is_refused_never_read_as_absent(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[0-9]{3}\tsecond\n'))
        for tail in (' [id-scheme bb]', ' ⟨id scheme bb⟩', ' ⟨id_scheme bb⟩', ' ⟨ID-Scheme bb⟩', ' ⟨idscheme bb⟩',
                     ' ⟨id-schemes bb⟩', ' ⟨id‑scheme bb⟩', ' ⟨id-scheme: bb⟩', ' ⟨id-scheme bb⟩ ⟨id scheme aa⟩',
                     ' (id-scheme bb)', ' id-scheme bb', ' ⟨id-schema bb⟩', ' ⟨id – scheme bb⟩',
                     ' ⟨id\u00a0—\u00a0scheme bb⟩', ' ⟨id-sceme bb⟩', ' ⟨id-shceme bb⟩', ' ⟨scheme bb⟩', ' ⟨bb⟩',
                     ' ⟨BB⟩', ' ⟨id-scheme bb⟩ (bb)'):
            with self.assertRaises(S.SchemeError, msg=tail) as cm:
                S.profile_schemes(profile_text(V1_LINE + tail), t)
            self.assertIn(cm.exception.code, ('MALFORMED', 'REPEATED'), tail)
        # the same on the shipped list: a key outside the exact tag never reads as the first row
        for tail in (' ⟨id-sceme pl-id⟩', ' ⟨id-shceme pl-id⟩', ' ⟨scheme pl-id⟩', ' ⟨pl-id⟩'):
            with self.assertRaises(S.SchemeError, msg=tail) as cm:
                S.profile_schemes(profile_text(V1_LINE + tail), S.load())
            self.assertEqual(cm.exception.code, 'MALFORMED', tail)
        # not tag-shaped: the list's file name, words that only contain the letters, a longer word with a key in it
        for tail in (' see tools/private-mode/id-schemes.tsv', ' paid scheme', ' valid schemes', ' bbq at the bb-c'):
            self.assertEqual(S.profile_schemes(profile_text(V1_LINE + tail), t), ['aa', 'bb'], tail)

    def test_the_unlisted_key_names_a_number_with_no_shape(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[0-9]{3}\tsecond\n'))
        keys = S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme unlisted⟩ — issued in a synthetic country'), t)
        self.assertEqual(keys, ['unlisted'])
        self.assertIsNone(S.residue_re(keys, t).search('12345 X123 anything'))
        self.assertEqual(S.board_shape(keys, t), '')
        keys = S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme bb,unlisted⟩'), t)
        self.assertEqual(keys, ['bb', 'unlisted'])
        rx = S.residue_re(keys, t)
        self.assertTrue(rx.search('n X123 n'))
        self.assertIsNone(rx.search('n 12345 n'))
        with self.assertRaises(S.SchemeError) as cm:                 # a misspelt key is unknown, never absent
            S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme unlistd⟩'), t)
        self.assertEqual(cm.exception.code, 'UNKNOWN')

    def test_words_never_narrow_the_search(self):
        # ADR-0077: only the exact tag decides; the phrase alone, or beside a damaged tag, searches every row
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[0-9]{3}\tsecond\n'))
        for text in (profile_text(V1_LINE + ' — number not on the list (a synthetic country)'),
                     profile_text(V1_LINE + ' — number not on the list; ⟨id-') + 'scheme bb⟩\n'):
            self.assertEqual(S.profile_schemes(text, t), ['aa', 'bb'], text)
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme bb⟩ number not on the list'), t), ['bb'])

    def test_a_byte_that_is_not_utf8_does_not_hide_the_tag(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[0-9]{3}\tsecond\n'))
        bad = b'caf\xe9'.decode('utf-8', 'surrogateescape')
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE + ' %s ⟨id-scheme bb⟩' % bad), t), ['bb'])
        replaced = b'caf\xe9'.decode('utf-8', 'replace')
        self.assertEqual(S.profile_schemes(profile_text(V1_LINE + ' %s ⟨id-scheme bb⟩' % replaced), t), ['bb'])
        body = profile_text(V1_LINE)[:-1].encode('utf-8') + b' caf\xe9 \xe2\x9f\xa8id-scheme bb\xe2\x9f\xa9\n'
        self.assertEqual(S.profile_schemes(body, t), ['bb'])            # the file's bytes, as the callers pass them
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with open(os.path.join(d.name, 'profile.md'), 'wb') as fh:
            fh.write(body)
        self.assertEqual(identity.read_profile(d.name, raw=True), body)

    def test_shipped_shapes_avoid_known_incompatible_syntax(self):
        for key, row in S.load().items():
            for banned in ('[[:', '\\', '(?'):
                self.assertNotIn(banned, row['shape'].replace('\\t', ''), key)

    def test_the_us_row_searches_separated_forms_only(self):
        # 987-65-432N is the range kept for advertising: never a person's number
        t = S.load()
        us = S.residue_re(['us-ssn'], t)
        for text in ('n 987-65-4321 n', '987 65 4321', 'x\t987\t65\t4321', '987–65–4321',
                     '987 — 65 — 4321', '987 65 4321', '(987-65-4321).'):
            self.assertTrue(us.search(text), text)
        for text in ('987654321', '1987-65-4321', '987-65-43210', '98-765-4321', 'tel 555-123-4567',
                     '2026-11-11', 'f987-65-4321', 'doc-0987654321abcdef', '987-65-****'):
            self.assertIsNone(us.search(text), text)
        # no exact tag searches both rows; a Polish tag searches the Polish shape alone
        both = S.residue_re(S.profile_schemes(profile_text(V1_LINE), t), t)
        self.assertTrue(both.search('n 987-65-4321 n') and both.search('n 44051401359 n'))
        pl = S.residue_re(S.profile_schemes(profile_text(V1_LINE + ' ⟨id-scheme pl-id⟩'), t), t)
        self.assertIsNone(pl.search('n 987-65-4321 n'))

    def test_the_board_gets_the_persons_shape_with_real_tabs(self):
        t = S.load(self.table('aa\tl\t[0-9]{5}\tfirst\nbb\tl\tX[ \\t]Y\tsecond\n'))
        self.assertEqual(S.board_shape(['aa', 'bb'], t), '([0-9]{5})|(X[ \t]Y)')
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = os.path.join(d.name, 'profile.md')
        for tail, want in ((' ⟨id-scheme pl-id⟩', 'TAG pl-id\nSHAPE ('), (' ⟨id-scheme unlisted⟩', 'NOTLISTED\n'),
                           (' ⟨id-scheme pl-id,unlisted⟩', 'TAG pl-id,unlisted\nSHAPE ('),
                           (' ⟨id-scheme us-ssn⟩', 'TAG us-ssn\nSHAPE ('),
                           (' — number not on the list', 'TAG pl-id,us-ssn\nSHAPE ('), (' ⟨pl-id⟩', 'MALFORMED\n')):
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(profile_text(V1_LINE + tail))
            out = subprocess.run([sys.executable, os.path.join(HERE, 'id_schemes.py'), path], capture_output=True)
            self.assertEqual(out.returncode, 0)
            self.assertTrue(out.stdout.decode('utf-8').startswith(want), tail)
        # a row whose shape has a tab: the reader prints a real tab, never a backslash
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(profile_text(V1_LINE + ' ⟨id-scheme aa,bb⟩'))
        raw = io.BytesIO()
        stdout = io.TextIOWrapper(raw, encoding='utf-8')
        with mock.patch.object(S, 'load', lambda path=None: t), mock.patch('sys.stdout', stdout):
            self.assertEqual(S.main(['id_schemes.py', path]), 0)
            stdout.flush()
        self.assertEqual(raw.getvalue(), 'TAG aa,bb\nSHAPE ([0-9]{5})|(X[ \t]Y)\n'.encode('utf-8'))

    def test_identity_values_in_the_persons_shape_are_refused(self):
        t = Tree()
        self.addCleanup(t.close)
        shape = identity.id_shape(t.pdir)
        self.assertIsNotNone(identity.check_value('phones', '4' * 11, shape))
        self.assertIsNone(identity.check_value('phones', '444 444 444 44', shape))
        with open(os.path.join(t.pdir, 'profile.md'), 'a', encoding='utf-8') as fh:
            fh.write('- quoted ⟨never-API⟩ ⟨id-scheme zz-none⟩\n')
        with self.assertRaises(Refused):
            identity.id_shape(t.pdir)

    def test_a_byte_that_is_not_utf8_does_not_stop_the_shape(self):
        t = Tree()
        self.addCleanup(t.close)
        with open(os.path.join(t.pdir, 'profile.md'), 'ab') as fh:
            fh.write(b'- caf\xe9\n')
        self.assertTrue(identity.id_shape(t.pdir).search('4' * 11))


# ---- the form: Claude writes the structure, the operator the values, in an editor ----------------

TYPED = {                       # what the operator types; nothing here passes through a session
    'name': ['Synthia Maria / Testperson'],
    'date of birth': ['23.02.1901'],
    'relative or contact': ['Exempla / Relative', 'Another / Contactperson'],
    'address': ['Example Street 12'],
    'phone': ['+00 555 010 101'],
    'e-mail': ['synth@example.invalid'],
    'case, visit or order number': ['AB 12 34 56'],
}
TYPED_VALUES = ['Synthia', 'Maria', 'Testperson', '23.02.1901', '1901-02-23', '010223', 'Exempla', 'Relative',
                'Contactperson', 'Example Street', '555 010', 'synth@example.invalid', 'AB 12 34']


def operator_fills(path, typed):
    """The operator's editor: each label's slot lines replaced in order, a further value on a copied line.
    The date of birth goes on its second line too, unless the case says otherwise."""
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().splitlines()
    left = {k: list(v) for k, v in typed.items()}
    if 'date of birth' in left and 'date of birth again' not in left:
        left['date of birth again'] = list(left['date of birth'])
    out = []
    for line in lines:
        label = line.partition(':')[0]
        if not line.startswith('#') and left.get(label):
            out.append('%s: %s' % (label, left[label].pop(0)))
        else:
            out.append(line)
    for label, rest in left.items():
        out += ['%s: %s' % (label, v) for v in rest]
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')


def no_open(path):
    return False


ALL = list(identity.CLASSES)


class Form(unittest.TestCase):
    def tree(self, line=V1_LINE):
        t = Tree(line=line)
        self.addCleanup(t.close)
        return t, identity.form_path(t.pdir)

    def assert_no_value(self, text):
        for v in TYPED_VALUES:
            self.assertNotIn(v, text)

    def identity_data(self, t):
        return plain(identity.load(t.pdir))

    def test_the_blank_form_holds_slots_only_and_is_owner_only(self):
        t, path = self.tree()
        out, opened = Script([]), []
        old = os.umask(0)
        try:
            identity.cmd_form(t.root, t.handle, ALL, lambda p: opened.append(p) or True, out.tell)
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(opened, [path])
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        self.assertEqual(text, identity.form_text(t.handle, ALL))
        self.assert_no_value(text + '\n'.join(out.out))
        self.assertNotIn('"', text)                 # nothing for an editor's smart quotes to change
        self.assertNotIn("'", text)
        self.assertTrue(identity.FORM_NAME.endswith(identity.IDENTITY_NAME), 'the read guard matches by this ending')

    def test_the_command_has_no_way_to_take_a_value(self):
        t, path = self.tree()
        for extra in (['Synthia'], ['--given', 'Synthia'], ['--dob', '1901-02-23']):
            with contextlib_quiet():
                self.assertEqual(identity.main(['--root', t.root, 'form', t.handle, '--keep', 'phones', '--no-open']
                                               + extra), identity.EXIT_USAGE)
        self.assertFalse(os.path.lexists(path))

    def test_the_form_holds_only_the_kept_parts(self):
        text = identity.form_text('szt-pm', ['phones', 'dob'])
        labels = [ln.partition(':')[0] for ln in text.splitlines() if ln and not ln.startswith('#')]
        self.assertEqual(labels, ['date of birth', 'date of birth again', 'phone', 'phone'])
        self.assertEqual(identity.parse_keep('phones, dob'), ['dob', 'phones'])
        for bad in ('', 'barcodes', 'phones,number'):
            with self.subTest(bad=bad), self.assertRaises(Refused):
                identity.parse_keep(bad)
        t, path = self.tree()
        with contextlib_quiet():
            self.assertEqual(identity.main(['--root', t.root, 'form', t.handle, '--no-open']), identity.EXIT_USAGE)
            self.assertEqual(identity.main(['--root', t.root, 'form', t.handle, '--keep', 'barcodes', '--no-open']),
                             identity.EXIT_REFUSED)
        self.assertFalse(os.path.lexists(path))

    def test_taking_the_form_swaps_the_working_record_in_the_same_step(self):
        t, path = self.tree()
        put(t, 'medications.md', 'Prescribed for Synthia Testperson, tel. +00 555 010 101\n')
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, TYPED)
        out = Script([])
        identity.cmd_take_form(t.root, t.handle, out.tell)
        with open(os.path.join(t.pdir, 'medications.md'), encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'Prescribed for ⟨withheld:patient-name⟩, tel. ⟨withheld:phone⟩\n')
        self.assertIn('medications.md: patient_names 1 · phones 1', out.printed())
        self.assertEqual(identity.scan_tree(t.root), [])

    def test_a_kept_detail_inside_a_file_name_records_nothing_and_keeps_the_form(self):
        # all or nothing (cold review 2026-11-09): a swap that would refuse records nothing
        t, path = self.tree()
        meds = put(t, 'medications.md', '- see [letter](med/sources/2026-01-01__letter__Testperson_Synthia.md)\n')
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, TYPED)
        with self.assertRaises(Refused) as cm:
            identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertIn('nothing is recorded and the form is kept', str(cm.exception))
        self.assertTrue(os.path.lexists(path))
        self.assertFalse(os.path.lexists(identity.identity_path(t.pdir)))
        with open(os.path.join(t.pdir, 'profile.md'), encoding='utf-8') as fh:
            self.assertNotIn(identity.KEPT_SIGN, fh.read())
        put(t, 'medications.md', '- see the GP letter\n')         # the operator renamed the file
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertEqual(plain(identity.load(t.pdir))['phones'], ['+00 555 010 101'])
        self.assertEqual(identity.scan_tree(t.root), [])

    def test_the_sign_goes_on_the_private_mode_line_even_when_no_detail_stands_in_the_profile(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ['phones'], no_open, Script([]).tell)
        operator_fills(path, {'phone': ['+00 555 010 101']})
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        prof = os.path.join(t.pdir, 'profile.md')
        with open(prof, encoding='utf-8') as fh:
            text = fh.read()
        line = [ln for ln in text.splitlines() if identity.MARK in ln][0]
        self.assertTrue(line.endswith(' · ' + identity.KEPT_SIGN), line)
        self.assertEqual(text.count(identity.KEPT_SIGN), 1)
        identity.cmd_swap(t.root, t.handle, Script([]).tell)              # a rerun adds no second sign
        with open(prof, encoding='utf-8') as fh:
            self.assertEqual(fh.read().count(identity.KEPT_SIGN), 1)
        self.assertEqual(identity.scan_tree(t.root), [])
        # the sign is what tells a lost file apart from a person keeping nothing
        os.rename(identity.identity_path(t.pdir), os.path.join(t.root, 'elsewhere'))
        self.assertIn('identity file is missing', '\n'.join(identity.scan_tree(t.root)))
        os.rename(os.path.join(t.root, 'elsewhere'), identity.identity_path(t.pdir))
        with open(prof, 'w', encoding='utf-8') as fh:
            fh.write(text.replace(' · ' + identity.KEPT_SIGN, ''))
        self.assertIn('lacks the kept-details sign', '\n'.join(identity.scan_tree(t.root)))

    def test_a_name_the_handle_spells_cannot_be_kept(self):
        t = Tree(handle='synthia-testperson')
        self.addCleanup(t.close)
        path = identity.form_path(t.pdir)
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'name': ['Synthia / Testperson']})
        with self.assertRaises(Refused) as cm:
            identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertIn('handle spells a name', str(cm.exception))
        self.assertNotIn('Synthia', str(cm.exception).replace('synthia', ''))
        self.assertTrue(os.path.lexists(path))
        self.assertFalse(os.path.lexists(identity.identity_path(t.pdir)))

    def test_no_form_before_the_marker(self):
        t, path = self.tree(line='- Private mode: none')
        with self.assertRaises(Refused):
            identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        self.assertFalse(os.path.lexists(path))

    def test_a_waiting_form_is_opened_again_never_overwritten(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'name': ['Synthia Maria / Testperson']})
        with open(path, 'rb') as fh:
            typed = fh.read()
        opened, out = [], Script([])
        identity.cmd_form(t.root, t.handle, ALL, lambda p: opened.append(p) or True, out.tell)
        with open(path, 'rb') as fh:
            self.assertEqual(fh.read(), typed)
        self.assertEqual(opened, [path])
        self.assert_no_value('\n'.join(out.out))

    def test_the_filled_form_becomes_the_identity_file_and_is_deleted(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, TYPED)
        out = Script([])
        identity.cmd_take_form(t.root, t.handle, out.tell)
        self.assertFalse(os.path.lexists(path))
        self.assertEqual(stat.S_IMODE(os.stat(identity.identity_path(t.pdir)).st_mode), 0o600)
        c = self.identity_data(t)
        self.assertEqual(c['patient_names'], [{'given': 'Synthia Maria', 'family': 'Testperson'}])
        self.assertEqual(c['dob'], ['1901-02-23'])
        self.assertEqual(c['other_names'], [{'given': 'Exempla', 'family': 'Relative'},
                                            {'given': 'Another', 'family': 'Contactperson'}])
        self.assertEqual(c['addresses'], ['Example Street 12'])
        self.assertEqual(c['phones'], ['+00 555 010 101'])
        self.assertEqual(c['emails'], ['synth@example.invalid'])
        self.assertEqual(c['case_numbers'], ['AB 12 34 56'])
        self.assertEqual(c['id_numbers'], [])       # an untouched slot records nothing
        self.assert_no_value('\n'.join(out.out))
        self.assertEqual(identity.recorded_dob(t.pdir), '1901-02-23')

    def test_a_copied_line_gives_another_entry_and_the_date_may_be_written_several_ways(self):
        for typed_date in ('23.02.1901', '23-02-1901', '1901-02-23', '23.2.1901'):
            t, path = self.tree()
            identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
            operator_fills(path, {'date of birth': [typed_date], 'phone': ['+00 555 010 101', '+00 555 010 102',
                                                                          '+00 555 010 103']})
            identity.cmd_take_form(t.root, t.handle, Script([]).tell)
            c = self.identity_data(t)
            self.assertEqual(c['dob'], ['1901-02-23'])
            self.assertEqual(len(c['phones']), 3)

    def test_apostrophes_and_an_editors_curly_ones_are_fine_and_still_match(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'name': ['Synthia / O’Testperson'], 'relative or contact': ["Exempla / D'Relative"]})
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        pats = identity.patterns(identity.load(t.pdir))
        self.assertTrue(identity.residue("Seen: Synthia O'Testperson today\n", pats))
        self.assertTrue(identity.residue('Seen: Exempla D’Relative today\n', pats))

    def test_a_refusal_names_the_line_changes_nothing_and_never_quotes_the_value(self):
        cases = [
            ('a date that does not exist', {'date of birth': ['31.02.1901']}, 'form line'),
            ('a future date', {'date of birth': ['23.02.2999']}, 'form line'),
            ('a slash date, which reads differently by country', {'date of birth': ['03/04/1901']}, 'form line'),
            ('a name with no slash', {'name': ['Synthia Testperson']}, 'form line'),
            ('a name half filled', {'name': ['Synthia / Xxxx']}, 'form line'),
            ('the designated number', {'other ID or document number': ['01022312344']}, 'form line'),
            ('an e-mail with no at sign', {'e-mail': ['synth.example.invalid']}, 'form line'),
            ('two dates of birth', {'date of birth': ['23.02.1901', '24.02.1901']}, 'more than one'),
            ('the date on one of its lines only', {'date of birth': ['23.02.1901'], 'date of birth again': []},
             'both of its lines'),
            ('the second date line only', {'date of birth again': ['23.02.1901']}, 'both of its lines'),
            ('a day and month swapped on one line', {'date of birth': ['23.02.1901'],
                                                    'date of birth again': ['02.23.1901']}, 'form line'),
            ('two different real dates', {'date of birth': ['05.06.1901'], 'date of birth again': ['06.05.1901']},
             'lines differ'),
            ('nothing filled', {}, 'discard-form'),
        ]
        for what, typed, words in cases:
            with self.subTest(what):
                t, path = self.tree()
                identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
                operator_fills(path, typed)
                with open(path, 'rb') as fh:
                    before = fh.read()
                with self.assertRaises(Refused) as cm:
                    identity.cmd_take_form(t.root, t.handle, Script([]).tell)
                self.assertIn(words, str(cm.exception))
                for v in TYPED_VALUES + ['01022312344', '31.02', '2999', 'synth.example', '05.06', '06.05', '1901']:
                    self.assertNotIn(v, str(cm.exception))
                with open(path, 'rb') as fh:
                    self.assertEqual(fh.read(), before)
                self.assertFalse(os.path.lexists(identity.identity_path(t.pdir)))

    def test_a_label_the_form_does_not_have_is_refused_by_line_number(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('Synthia Testperson\n')
        with self.assertRaises(Refused) as cm:
            identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertRegex(str(cm.exception), r'^form line [0-9]+ is not')
        self.assertNotIn('Synthia', str(cm.exception))

    def test_rich_text_and_other_encodings_are_named_not_misread(self):
        for raw, words in ((b'{\\rtf1\\ansi name: Synthia / Testperson}', 'rich text'),
                           ('name: Synthia / Testpérson\n'.encode('latin-1'), 'UTF-8')):
            t, path = self.tree()
            with open(path, 'wb') as fh:
                fh.write(raw)
            with self.assertRaises(Refused) as cm:
                identity.cmd_take_form(t.root, t.handle, Script([]).tell)
            self.assertIn(words, str(cm.exception))
            self.assertNotIn('Testp', str(cm.exception))

    def test_a_stray_copy_beside_the_form_stops_it(self):
        for stray in ('fill-in-form.never-api-identity copy.json', 'fill-in-form.never-api-identity.json~',
                      '.tmp-0a1b2c3d.never-api-identity.json'):
            with self.subTest(stray):
                t, path = self.tree()
                identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
                operator_fills(path, TYPED)
                with open(os.path.join(t.pdir, stray), 'w', encoding='utf-8') as fh:
                    fh.write('anything')
                with self.assertRaises(Refused):
                    identity.cmd_take_form(t.root, t.handle, Script([]).tell)
                self.assertTrue(os.path.lexists(path))
                self.assertFalse(os.path.lexists(identity.identity_path(t.pdir)))

    def test_a_later_form_adds_and_never_replaces(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, TYPED)
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'date of birth': ['23.02.1901'], 'phone': ['+00 555 010 101', '+00 555 010 999']})
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        c = self.identity_data(t)
        self.assertEqual(c['phones'], ['+00 555 010 101', '+00 555 010 999'])
        self.assertEqual(c['addresses'], ['Example Street 12'])
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'phone': ['+00 555 010 888']})
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertEqual(self.identity_data(t)['phones'], ['+00 555 010 101', '+00 555 010 999', '+00 555 010 888'])
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'date of birth': ['24.02.1901']})
        with self.assertRaises(Refused) as cm:
            identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertIn('different date of birth', str(cm.exception))
        self.assertIn('set %s dob' % t.handle, str(cm.exception))      # the way out is named
        self.assertNotIn('24.02', str(cm.exception))
        self.assertEqual(self.identity_data(t)['dob'], ['1901-02-23'])

    def test_discard_form_deletes_a_waiting_form_unread_and_changes_nothing_else(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, TYPED)
        identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        with open(identity.identity_path(t.pdir), 'rb') as fh:
            recorded = fh.read()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        operator_fills(path, {'date of birth': ['24.02.1901'], 'phone': ['+00 555 010 777']})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(identity.main(['--root', t.root, 'discard-form', t.handle]), identity.EXIT_OK)
        self.assertFalse(os.path.lexists(path))
        with open(identity.identity_path(t.pdir), 'rb') as fh:
            self.assertEqual(fh.read(), recorded)
        self.assert_no_value(out.getvalue() + err.getvalue())
        self.assertNotIn('555 010 777', out.getvalue() + err.getvalue())
        with self.assertRaises(Refused):
            identity.cmd_discard_form(t.root, t.handle, Script([]).tell)
        status = Script([])
        identity.cmd_status(t.root, t.handle, status.tell)
        self.assertNotIn('form: waiting for the operator', status.out)

    def test_a_stray_copy_refusal_sends_no_session_to_look(self):
        t, path = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        with open(os.path.join(t.pdir, 'fill-in-form.never-api-identity copy.json'), 'w', encoding='utf-8') as fh:
            fh.write('anything')
        with self.assertRaises(Refused) as cm:
            identity.cmd_take_form(t.root, t.handle, Script([]).tell)
        self.assertIn('the operator closes the editor and deletes that file themselves', str(cm.exception))
        self.assertIn('a session leaves it alone', str(cm.exception))

    def test_a_form_with_no_identity_file_yet_shows_in_status(self):
        t, _ = self.tree()
        identity.cmd_form(t.root, t.handle, ALL, no_open, Script([]).tell)
        out = Script([])
        identity.cmd_status(t.root, t.handle, out.tell)
        self.assertIn('form: waiting for the operator', out.out)

    def test_no_recorded_date_is_refused_by_category(self):
        t, _ = self.tree()
        with self.assertRaises(Refused):
            identity.recorded_dob(t.pdir)


class StrangerWalk(unittest.TestCase):
    """A fresh person keeping every detail, on an install with no token registry and no identifier file. Every command a
    session runs, and all it prints, is what the model sees; the operator's step runs beside them.
    Masking's half of this walk: DobFromIdentity in test_redact_ids.py. The board's: checks/selftest.sh."""

    def test_no_typed_value_reaches_anything_a_session_writes_or_reads(self):
        t = Tree()
        self.addCleanup(t.close)
        seen = []

        def run(cmd):
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
            seen.extend([' '.join(cmd), r.stdout, r.stderr])
            return r.returncode

        def session(*args):
            return run([sys.executable, os.path.join(HERE, 'identity.py'), '--root', t.root] + list(args))

        self.assertEqual(session('form', t.handle, '--keep', ','.join(ALL), '--no-open'), 0)
        self.assertEqual(session('status', t.handle), 0)
        operator_fills(identity.form_path(t.pdir), TYPED)
        self.assertEqual(session('take-form', t.handle), 0)
        self.assertEqual(session('swap', t.handle), 0)
        self.assertEqual(session('status', t.handle), 0)
        self.assertEqual(session('age', t.handle), 0)
        self.assertEqual(session('scan'), 0)
        everything = '\n'.join(seen)
        self.assertIn('age ', everything)              # the walk really reached the file
        for v in TYPED_VALUES:
            self.assertNotIn(v, everything)
        self.assertFalse(os.path.lexists(identity.form_path(t.pdir)))
        # the positive control: a local caller that does print a recorded value, captured the same way,
        # is caught by the same check (so the file really holds the date, and the capture sees output)
        self.assertEqual(run([sys.executable, '-c', 'import identity, sys; print(identity.recorded_dob(sys.argv[1]))',
                              t.pdir]), 0)
        self.assertIn('1901-02-23', '\n'.join(seen))


# ---- a number with no date inside, read from a page (ADR-0074). Synthetic only: 987-65-4321 is in the
# range the US keeps for advertising; the "page" is OCR words handed to the tool, never a real scan.

def _word(text, left, top, line=('1', '1', '1'), conf=95):
    return dict(text=text, conf=conf, left=left, top=top, width=20 * len(text), height=30, line_key=line)


def _page_row(*texts, top=500, line=('1', '1', '1')):
    out, left = [], 100
    for t in texts:
        out.append(_word(t, left, top, line=line))
        left += 20 * len(t) + 15
    return out


US_LINE = V1_LINE + ' · ⟨id-scheme us-ssn⟩'
US_NUMBER, US_SHOWN = '987654321', '987-65-4321'
FILLER_WORDS = [_word('w%d' % i, 100, 900 + 40 * i, line=(str(i + 10), '1', '1')) for i in range(5)]


real_page = identity._page


class ReadNumber(unittest.TestCase):
    def setUp(self):
        import redact_ids
        self.R = redact_ids
        self.t = Tree(line=US_LINE)
        self.addCleanup(self.t.close)
        table = os.path.join(self.t.root, 'id-schemes.tsv')
        with open(table, 'w', encoding='utf-8') as fh:
            fh.write('pl-id\tpol\t[0-9]{11}\tsynthetic row\nus-ssn\teng\t[0-9]{3}-[0-9]{2}-[0-9]{4}\tsynthetic row\n')
        real = S.load
        self.pdf = os.path.join(self.t.pdir, 'med', '_inbox', 'scan.pdf')
        with open(self.pdf, 'wb') as fh:
            fh.write(b'%PDF-FAKE')
        self.png = os.path.join(self.t.root, 'page.png')
        with open(self.png, 'wb') as fh:
            fh.write(b'png')
        self.words = _page_row('SSN:', US_SHOWN) + FILLER_WORDS
        self.pages_read = []

        def page(pdf, n, lang, wdir):
            self.pages_read.append((pdf, n, lang))
            return list(self.words), 2000, 2000, self.png

        def run_checked(cmd, stage, outputs=(), **kw):
            for o in outputs:
                with open(o, 'wb') as fh:
                    fh.write(b'picture')
            return subprocess.CompletedProcess(cmd, 0, '', '')
        for p in (mock.patch.object(S, 'load', lambda path=None: real(table)),
                  mock.patch.object(redact_ids, 'IM', {'convert': ['convert'], 'identify': ['identify']}),
                  mock.patch.object(identity, '_page', page),
                  mock.patch.object(redact_ids, 'run_checked', run_checked)):
            p.start()
            self.addCleanup(p.stop)
        self.form = identity.form_path(self.t.pdir)
        self.picture = os.path.join(self.t.pdir, identity.PICTURE_NAME)

    def read(self, opened=None, page=1):
        out = Script([])
        opened = [] if opened is None else opened
        identity.cmd_form(self.t.root, self.t.handle, None, lambda p: opened.append(p) or True, out.tell,
                          read='med/_inbox/scan.pdf', page=page, viewer=lambda p: opened.append(p) or True)
        return out

    def take(self):
        out = Script([])
        identity.cmd_take_form(self.t.root, self.t.handle, out.tell)
        return out

    def edit_form(self, old, new):
        with open(self.form, encoding='utf-8') as fh:
            text = fh.read()
        with open(self.form, 'w', encoding='utf-8') as fh:
            fh.write(text.replace(old, new))

    def assert_no_number(self, text):
        for v in (US_NUMBER, US_SHOWN, '4321'):
            self.assertNotIn(v, text)

    def test_the_reading_goes_into_the_form_beside_a_picture_both_owner_only(self):
        opened = []
        out = self.read(opened)
        self.assertEqual(opened, [self.form, self.picture])
        for p in (self.form, self.picture):
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        self.assertIn('never-api-identity', identity.PICTURE_NAME, 'the read guard matches this mark')
        with open(self.form, encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('national number: %s\n' % US_SHOWN, text)
        self.assertIn('read from: med/_inbox/scan.pdf page 1\n', text)
        self.assertEqual(self.pages_read[0][1:], (1, 'eng'))
        self.assert_no_number(out.printed())

    def test_take_form_records_it_after_finding_it_on_the_page_again(self):
        self.read()
        out = self.take()
        self.assertEqual(identity.recorded_numbers(self.t.pdir), {'us-ssn': US_NUMBER})
        self.assertFalse(os.path.lexists(self.form) or os.path.lexists(self.picture))
        self.assertEqual(len(self.pages_read), 2, 'the page is read once more for the self-check')
        self.assert_no_number(out.printed())
        self.assertIn('national numbers 1', out.printed())

    def test_a_corrected_digit_is_kept_when_masking_still_finds_it(self):
        self.words = _page_row('SSN:', '987-65-4821') + FILLER_WORDS      # OCR read one digit wrong
        self.read()
        self.edit_form('987-65-4821', US_SHOWN)
        self.take()
        self.assertEqual(identity.recorded_numbers(self.t.pdir), {'us-ssn': US_NUMBER})

    def test_a_number_masking_cannot_find_on_its_page_is_not_recorded(self):
        self.read()
        self.edit_form(US_SHOWN, '912-34-5678')
        with self.assertRaises(Refused) as cm:
            self.take()
        self.assertIn('does not find that number', str(cm.exception))
        self.assertIsNone(identity.load(self.t.pdir))
        self.assertTrue(os.path.exists(self.form), 'the form stays for the operator to correct')

    def test_a_number_never_issued_is_refused(self):
        self.read()
        for bad in ('000-65-4321', '987-00-4321', '987-65-0000', '666-65-4321', '987-65-432'):
            self.edit_form(US_SHOWN, bad)
            with self.assertRaises(Refused):
                self.take()
            self.edit_form(bad, US_SHOWN)
        self.assertIsNone(identity.load(self.t.pdir))

    def test_no_single_reading_beside_the_label_writes_nothing(self):
        for words in (_page_row('Patient', US_SHOWN) + FILLER_WORDS,                       # no label
                      _page_row('SSN:', US_SHOWN, 'SSN:', '987-65-4320') + FILLER_WORDS,   # two numbers
                      _page_row('SSN:', '000-12-3456') + FILLER_WORDS):                    # never issued
            self.words = words
            with self.assertRaises(Refused):
                self.read()
            self.assertFalse(os.path.lexists(self.form) or os.path.lexists(self.picture))

    def test_only_a_marked_person_whose_number_holds_no_date(self):
        for line in ('- Private mode: none · ⟨id-scheme us-ssn⟩', V1_LINE, V1_LINE + ' ⟨id-scheme pl-id⟩'):
            with open(os.path.join(self.t.pdir, 'profile.md'), 'w', encoding='utf-8') as fh:
                fh.write(profile_text(line))
            with self.assertRaises(Refused):
                self.read()
            self.assertFalse(os.path.lexists(self.form) or os.path.lexists(self.picture))

    def test_the_page_must_be_a_pdf_in_the_persons_folder(self):
        outside = os.path.join(self.t.root, 'other.pdf')
        with open(outside, 'wb') as fh:
            fh.write(b'%PDF-FAKE')
        for path in (outside, '../../other.pdf', 'profile.md', 'med/_inbox/missing.pdf'):
            with self.assertRaises(Refused):
                identity.cmd_form(self.t.root, self.t.handle, None, no_open, Script([]).tell, read=path,
                                  viewer=no_open)
        with self.assertRaises(Refused):
            self.read(page=0)
        self.assertEqual(self.pages_read, [])

    def test_a_changed_page_line_is_refused(self):
        self.read()
        self.edit_form('page 1', 'page one')
        with self.assertRaises(Refused):
            self.take()
        self.assertIsNone(identity.load(self.t.pdir))

    def test_a_second_reading_replaces_the_first(self):
        self.read()
        self.take()
        self.words = _page_row('SSN:', '987-65-4320') + FILLER_WORDS
        self.read()
        self.take()
        self.assertEqual(identity.recorded_numbers(self.t.pdir), {'us-ssn': '987654320'})

    def test_discard_deletes_the_form_and_the_picture_unread(self):
        self.read()
        out = Script([])
        identity.cmd_discard_form(self.t.root, self.t.handle, out.tell)
        self.assertFalse(os.path.lexists(self.form) or os.path.lexists(self.picture))
        self.assertIn('and the picture', out.printed())

    def test_a_waiting_form_blocks_a_new_reading(self):
        self.read()
        with self.assertRaises(Refused):
            self.read()

    def test_the_blank_form_still_has_no_line_for_the_number(self):
        self.assertNotIn(identity.NUMBER_LINE, identity.form_text(self.t.handle, list(identity.CLASSES)))

    def test_the_residue_guard_finds_the_number_in_the_record_in_any_spacing(self):
        self.read()
        self.take()
        for written in ('987 65 4321', '987-65-4321', '987654321'):
            with open(os.path.join(self.t.pdir, 'profile.md'), 'a', encoding='utf-8') as fh:
                fh.write('- note %s\n' % written)
            findings = identity.scan_tree(self.t.root)
            self.assertTrue(any('the national ID number' in f for f in findings), written)
            self.assert_no_number('\n'.join(findings))
            with open(os.path.join(self.t.pdir, 'profile.md'), 'w', encoding='utf-8') as fh:
                fh.write(profile_text(US_LINE))
        self.assertEqual(identity.scan_tree(self.t.root), [])

    def test_the_file_refuses_a_malformed_number_entry(self):
        base = identity.empty()
        for numbers in ({'us-ssn': '98765'}, {'US SSN': US_NUMBER}, {'us-ssn': 987654321}, ['us-ssn']):
            data = dict(base, numbers=numbers)
            with self.assertRaises(Refused):
                identity.validate(data, re.compile('(?!)'))
        identity.validate(dict(base, numbers={'us-ssn': US_NUMBER}), re.compile('(?!)'))

    def test_a_path_from_the_care_folder_root_is_read_too(self):
        out = Script([])
        identity.cmd_form(self.t.root, self.t.handle, None, no_open, out.tell,
                          read='patients/%s/med/_inbox/scan.pdf' % self.t.handle, viewer=no_open)
        with open(self.form, encoding='utf-8') as fh:
            self.assertIn('read from: med/_inbox/scan.pdf page 1\n', fh.read())

    def test_a_moved_page_says_how_to_start_again(self):
        self.read()
        os.rename(self.pdf, self.pdf + '.moved.pdf')
        with self.assertRaises(Refused) as cm:
            self.take()
        self.assertIn('discard-form', str(cm.exception))
        self.assertIsNone(identity.load(self.t.pdir))

    def test_missing_ocr_tools_are_named(self):
        with mock.patch.object(identity.shutil, 'which', return_value=None):
            with self.assertRaises(Refused) as cm:
                real_page(self.pdf, 1, 'eng', self.t.root)
        self.assertIn('pdftoppm is not installed', str(cm.exception))

    def test_a_number_only_file_swaps_the_number_out_and_writes_no_sign(self):
        prof = os.path.join(self.t.pdir, 'profile.md')
        with open(prof, 'a', encoding='utf-8') as fh:
            fh.write('- written by mistake: 987 65 4321\n')
        self.read()
        out = self.take()
        with open(prof, encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('⟨withheld:national-number⟩', text)
        self.assertNotIn(identity.KEPT_SIGN, text, 'the number alone needs no kept-details sign')
        self.assertIn('national_number 1', out.printed())
        self.assertEqual(identity.scan_tree(self.t.root), [])
        status = Script([])
        identity.cmd_status(self.t.root, self.t.handle, status.tell)
        self.assertIn('the number itself: recorded', status.printed())
        self.assertIn('besides the number: nothing', status.printed())

    def test_the_cli_prints_no_digit(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(identity.main(['--root', self.t.root, 'form', self.t.handle, '--no-open',
                                            '--read-number', 'med/_inbox/scan.pdf']), identity.EXIT_OK)
            self.assertEqual(identity.main(['--root', self.t.root, 'status', self.t.handle]), identity.EXIT_OK)
            self.assertEqual(identity.main(['--root', self.t.root, 'take-form', self.t.handle]), identity.EXIT_OK)
        self.assert_no_number(stdout.getvalue() + stderr.getvalue())
        self.assertIn('picture of a page: waiting', stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
