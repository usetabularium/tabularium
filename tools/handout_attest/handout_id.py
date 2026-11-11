#!/usr/bin/env python3
"""Handout stable identifier (ADR-0033): the check character, in Python. STDLIB ONLY, no package
imports — the renderer loads this file by path (render_handout.py), and `next-id` in this package's
CLI uses it to print the next free ID.

`TAB-<PPP>-<NNN><C>[.rREV]`: <PPP> is the person's opaque Crockford tag, <NNN> their sequence, and
    <C> = A[(sum of value(char_i) * w_i) mod 32]  over the six symbols <PPP><NNN>, w = 1 3 5 7 9 11,
with A the Crockford base-32 alphabet (index = value; I L O U removed). Guard L8's `tab_checkchar`
in checks/check.sh is the shell twin; test_attest runs both on the same IDs.
"""
import re

ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
WEIGHTS = (1, 3, 5, 7, 9, 11)
_SYM = '[0-9A-HJKMNP-TV-Z]'
ID_RE = re.compile(r'TAB-(%s{3})-([0-9]{3})(%s)(\.r[0-9]+)?' % (_SYM, _SYM))
# An ID inside running text (an INDEX row, a filename segment): not glued to a longer token.
ID_IN_TEXT_RE = re.compile(r'(?<![0-9A-Za-z])TAB-(%s{3})-([0-9]{3})(%s)(?:\.r[0-9]+)?(?![0-9A-Za-z])'
                           % (_SYM, _SYM))
TAG_RE = re.compile(r'%s{3}' % _SYM)


def check_char(payload):
    """The check character over the six-symbol payload <PPP><NNN> (uppercase)."""
    if not isinstance(payload, str) or len(payload) != 6:
        raise ValueError('the payload is not six symbols')
    total = 0
    for ch, weight in zip(payload, WEIGHTS):
        value = ALPHABET.find(ch)
        if value < 0:
            raise ValueError('the payload holds a symbol outside the Crockford alphabet')
        total += value * weight
    return ALPHABET[total % 32]


def make_id(tag, number):
    """`TAB-<tag>-<NNN><C>` for a three-symbol tag and a number 1..999."""
    if not (isinstance(tag, str) and TAG_RE.fullmatch(tag)):
        raise ValueError('the tag is not three Crockford symbols')
    if not (isinstance(number, int) and 1 <= number <= 999):
        raise ValueError('the sequence number is outside 1..999')
    payload = '%s%03d' % (tag, number)
    return 'TAB-%s-%03d%s' % (tag, number, check_char(payload))


def id_problem(handout_id):
    """None for a well-formed ID whose check character is right. Otherwise (reason, expected): the
    reason in a few value-free words, and the right check character when only that is wrong."""
    m = ID_RE.fullmatch(handout_id or '')
    if not m:
        return ('not the form TAB-<PPP>-<NNN><C>[.rN] (Crockford tag, three digits)', None)
    expected = check_char(m.group(1) + m.group(2))
    if m.group(3) != expected:
        return ('wrong check character', expected)
    return None


def front_matter_id_verdict(value):
    """How a handout's front-matter `id:` is judged — the renderer's B0 halt applies this rule: '' when
    it is not checked (plain ASCII with no `TAB` in any case — a legacy ID), 'ok', 'malformed' (quoted,
    mis-cased, a look-alike or hidden character, a broken shape), or the expected check character."""
    value = value or ''
    if value.isascii() and 'TAB' not in value.upper():
        return ''
    problem = id_problem(value)
    if problem is None:
        return 'ok'
    return problem[1] or 'malformed'
