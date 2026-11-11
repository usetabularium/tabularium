#!/usr/bin/env python3
"""
Private mode — does masking still work with the REAL poppler, tesseract and ImageMagick?

Run by hand on the operator's Mac before a release (contributing/releases.md), and after a Homebrew
upgrade of any of the three tools:

    python3 tools/private-mode/real_tools_check.py

It is NOT a test_*.py suite: the selftest and CI run those, and CI installs none of these tools. Every
suite there fakes the three tools, so a change in what the real ones do (or in how redact_ids.py drives
them) passes all of them. This check builds invented pages with ImageMagick, runs the real redact_ids.py
pipeline on them (PDF -> pdftoppm -> OSD -> tesseract -> mask -> ImageMagick burn -> re-OCR), and judges
the output bytes with the real tools again. SYNTHETIC data only: the number is the invented one below, on
pages it draws itself, and nothing here reads a record, a person's folder or the private-mode identifier.
Run it in a development tree (a care folder with people refuses the throwaway inbox).

It asserts, per case (plain page, number only on page 2, a page scanned sideways):
  OCR_NOT_RECOVERABLE   real tesseract reads no run of the number's digits from the output page
  PLAIN_RASTER          the output is a PNG holding pixels only: no text but ImageMagick's own date stamps,
                        no Exif or colour profile
  MASK_BLACK            every pixel where the number was, plus a margin, is black
  PAGE_KEPT             the rest of the page is untouched: white ground, its words still read
  PAGE1_UNMASKED        (page 2 only) page 1 holds no mask: page 2's mask is its own
  UPRIGHT               (sideways page) the output is upright and its mask sits in that frame
and, across the whole run: LANG_REACHES (every OCR read used --lang), DPI_REACHES (the render used
--dpi, so the output has the size that dpi gives).

Then the controls: the same judgement over runs broken on purpose (zero padding, no burn, swapped x/y,
page 1's masks reused, page 2's mask leaking onto page 1, no rotation, --lang ignored, --dpi ignored). Each
must fail its own assertion; a
broken run that passes means this check cannot see that breakage.

Output is exit tokens and counts only: no number, no OCR text, no path.
Exit: 0 REAL_TOOLS_OK · 1 CHECK_FAILED · 2 TOOLS_ABSENT · 3 TOOLS_WRONG_VERSION · 4 CONTROL_NOT_CAUGHT ·
      5 SETUP_ERROR (the invented pages or the pipeline could not be made to run) · 64 usage.
A tool that is missing or too old is a failure, never a skip.
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REDACT = os.path.join(HERE, 'redact_ids.py')

EXIT_OK, EXIT_CHECK_FAILED, EXIT_ABSENT, EXIT_WRONG_VERSION, EXIT_CONTROL, EXIT_SETUP, EXIT_USAGE = 0, 1, 2, 3, 4, 5, 64

# The majors this was written against (tesseract 5.5, ImageMagick 7.1, poppler 26.02). A floor is a judgement:
# raise it when an older release is found to break masking. A newer release is not refused: the pages decide.
FLOORS = {'tesseract': 5, 'ImageMagick': 7, 'pdftoppm': 24}

# An invented number and date of birth, plainly so: 1970-01-01, then 1234 and a check digit (scheme 'pl-id').
DOB = '1970-01-01'
NUMBER = '70010112341'
SCHEME = 'pl-id'
LANG = 'eng'
DPI = 150                      # the pages are drawn at this density: 1275 x 1650 pixels, a letter page
OTHER_DPI = 200
PAGE_W, PAGE_H = 1275, 1650
NUMBER_AT = (600, 400)         # where the number is drawn (pixels from the top left, text baseline)
MARGIN = 4                     # the mask must reach this far past the number's glyphs: redact_ids pads 6 or more
WORDS = ('Patient', 'Clinic', 'Medication', 'orientation', 'invented', 'summary')   # words the pages keep
FONTS = ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Supplemental/Courier New.ttf',
         '/System/Library/Fonts/Monaco.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/dejavu/DejaVuSans.ttf')
BREAKS = ('zero-pad', 'skip-burn', 'swap-xy', 'page1-masks', 'page1-leak', 'no-rotate', 'ignore-lang', 'ignore-dpi')
# the assertion each break must trip (id, case)
CATCHES = {'zero-pad': ('MASK_BLACK', 'plain'), 'skip-burn': ('OCR_NOT_RECOVERABLE', 'plain'),
           'swap-xy': ('MASK_BLACK', 'plain'), 'page1-masks': ('MASK_BLACK', 'page2'),
           'page1-leak': ('PAGE1_UNMASKED', 'page2'),
           'no-rotate': ('UPRIGHT', 'rotated'), 'ignore-lang': ('LANG_REACHES', 'run'),
           'ignore-dpi': ('DPI_REACHES', 'run')}
CASES_FOR = {'zero-pad': ('plain',), 'skip-burn': ('plain',), 'swap-xy': ('plain',),
             'page1-masks': ('page2',), 'page1-leak': ('page2',), 'no-rotate': ('rotated',), 'ignore-lang': ('plain',),
             'ignore-dpi': ('plain',)}
ALL_CASES = ('plain', 'page2', 'rotated')
# What a plain raster PNG may hold: its pixels and how to show them, and ImageMagick's own date stamps (a
# tIME chunk and three tEXt chunks keyed exactly so: when the file was written, nothing of the page or the
# source). Any other text, a compressed or international text chunk, Exif or a colour profile is not plain.
PNG_PIXEL_CHUNKS = {b'IHDR', b'PLTE', b'IDAT', b'IEND', b'tRNS', b'gAMA', b'cHRM', b'sRGB', b'pHYs', b'sBIT', b'bKGD'}
PNG_DATE_STAMPS = {b'date:create', b'date:modify', b'date:timestamp'}


class Setup(Exception):
    """The check itself could not be set up or run (the invented pages, the pipeline): SETUP_ERROR."""


def _im():
    return ['magick'] if shutil.which('magick') else ['convert']


def _run(cmd, env=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise Setup('a tool could not run')


def tool_problems():
    """([absent tool names], [too-old tool names]) among the three tools, tesseract's eng and osd data, and a font."""
    absent, old = [], []
    im_ok = bool(shutil.which('magick') or (shutil.which('convert') and shutil.which('identify')))
    for name, found in (('pdftoppm', shutil.which('pdftoppm')), ('tesseract', shutil.which('tesseract')),
                        ('ImageMagick', im_ok)):
        if not found:
            absent.append(name)
    if absent:
        return absent, old

    def major(cmd, pattern):
        r = _run(cmd)
        m = re.search(pattern, (r.stdout or '') + '\n' + (r.stderr or ''), re.M)
        return int(m.group(1)) if m else 0

    seen = {'pdftoppm': major(['pdftoppm', '-v'], r'^pdftoppm version (\d+)'),
            'tesseract': major(['tesseract', '--version'], r'^tesseract (\d+)'),
            'ImageMagick': major(_im() + ['-version'], r'^Version: ImageMagick (\d+)')}
    old = [n for n, v in seen.items() if v < FLOORS[n]]
    if old:
        return absent, old
    r = _run(['tesseract', '--list-langs'])
    have = set(((r.stdout or '') + '\n' + (r.stderr or '')).split())
    if not {LANG, 'osd'} <= have:
        absent.append('tesseract-data')
    if not _font():
        absent.append('font')
    return absent, old


def _font():
    return next((f for f in FONTS if os.path.isfile(f)), None)


# ---- the invented pages ----

def _page_png(path, lines, number, rotate):
    """One invented page: `lines` of plain words, the number drawn at NUMBER_AT when `number`; turned
    `rotate` degrees as a scanner that fed the sheet sideways would."""
    args = _im() + ['-size', f'{PAGE_W}x{PAGE_H}', 'xc:white', '-font', _font(), '-pointsize', '36', '-fill', 'black']
    for i, text in enumerate(lines):
        args += ['-annotate', f'+100+{200 + 100 * i}', text]
    if number:
        args += ['-annotate', f'+{NUMBER_AT[0]}+{NUMBER_AT[1]}', NUMBER]
    if rotate:
        args += ['-rotate', str(rotate)]
    r = _run(args + ['-density', str(DPI), '-units', 'PixelsPerInch', path])
    if r.returncode != 0 or not os.path.isfile(path):
        raise Setup('a page could not be drawn')


def _number_box():
    """(x, y, w, h) of the number's own glyphs, found by ImageMagick on a page holding only the number."""
    probe = _run(_im() + ['-size', f'{PAGE_W}x{PAGE_H}', 'xc:white', '-font', _font(), '-pointsize', '36',
                          '-fill', 'black', '-annotate', f'+{NUMBER_AT[0]}+{NUMBER_AT[1]}', NUMBER,
                          '-format', '%@', 'info:'])
    m = re.fullmatch(r'(\d+)x(\d+)\+(\d+)\+(\d+)', probe.stdout.strip())
    if probe.returncode != 0 or not m:
        raise Setup('the number box could not be measured')
    w, h, x, y = map(int, m.groups())
    return x, y, w, h


FILLER = ('Patient summary report for review', 'Clinic visit notes and ordinary words',
          'Reference number pending', 'Further lines for orientation of the page',
          'Another line of invented sample content', 'Medication list follows below this line')
WITH_NUMBER = ('Patient summary report for review', 'Clinic visit notes and ordinary words',
               'Identity number', 'Further lines for orientation of the page',
               'Another line of invented sample content', 'Medication list follows below this line')

# case -> pages: (lines, number drawn, turned degrees)
CASES = {'plain': [(WITH_NUMBER, True, 0)],
         'page2': [(FILLER, False, 0), (WITH_NUMBER, True, 0)],
         'rotated': [(WITH_NUMBER, True, 90)]}


def _build_pdf(root, case):
    """The case's PDF in root/inbox, one letter-sized page per page of the case; its path."""
    pngs = []
    for i, (lines, number, rotate) in enumerate(CASES[case]):
        p = os.path.join(root, f'{case}-{i + 1}.png')
        _page_png(p, lines, number, rotate)
        pngs.append(p)
    pdf = os.path.join(root, 'inbox', f'{case}.pdf')
    r = _run(_im() + pngs + ['-density', str(DPI), '-units', 'PixelsPerInch', pdf])
    if r.returncode != 0 or not os.path.isfile(pdf):
        raise Setup('a pdf could not be built')
    return pdf


# ---- one real pipeline run ----

def _spy_dir(root, log):
    """A folder of two wrappers, tesseract and pdftoppm, that note their arguments and run the real tool, so
    the check sees what redact_ids.py really passed (--lang, --dpi)."""
    d = os.path.join(root, 'spy')
    os.makedirs(d)
    for tool in ('tesseract', 'pdftoppm'):
        real = shutil.which(tool)
        with open(os.path.join(d, tool), 'w') as f:
            f.write('#!/bin/sh\n{ echo @@call; for a in "$@"; do printf "%%s\\n" "$a"; done; } >> %s\n'
                    'exec %s "$@"\n' % (shlex.quote(log), shlex.quote(real)))
        os.chmod(os.path.join(d, tool), 0o755)
    return d


def _calls(log):
    calls = []
    if os.path.isfile(log):
        for line in open(log, encoding='utf-8').read().split('\n'):
            if line == '@@call':
                calls.append([])
            elif calls and line != '':
                calls[-1].append(line)
    return calls


def _after(args, flag):
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


def run_pipeline(root, cases, dpi, brk=None):
    """Draw the cases' pages, run redact_ids.py over them (broken on purpose when `brk` names a break) and
    return what the assertions need. The three tools are the real ones."""
    for sub in ('inbox', 'render', 'work', 'redacted'):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    pdfs = {c: _build_pdf(root, c) for c in cases}
    shas = {c: hashlib.sha256(open(p, 'rb').read()).hexdigest() for c, p in pdfs.items()}
    log = os.path.join(root, 'spy.log')
    spy = _spy_dir(root, log)
    run_log = os.path.join(root, 'run.json')
    args = ['--inbox', os.path.join(root, 'inbox'), '--render', os.path.join(root, 'render'),
            '--work', os.path.join(root, 'work'), '--redacted', os.path.join(root, 'redacted'),
            '--log', run_log, '--scheme', SCHEME, '--dob', DOB, '--lang', LANG, '--dpi', str(dpi)]
    cmd = [sys.executable, '-I', os.path.abspath(__file__), '--run-broken', brk or 'none', '--'] + args
    env = dict(os.environ, PATH=spy + os.pathsep + os.environ.get('PATH', ''))
    r = _run(cmd, env=env)
    if not os.path.isfile(run_log):
        raise Setup('the pipeline wrote no run log (exit %d)' % r.returncode)
    docs = {d['input_sha256']: d for d in json.load(open(run_log))['documents']}
    out = {}
    for c in cases:
        doc = docs.get(shas[c])
        pages = []
        for p in (doc or {}).get('pages', []):
            png = os.path.join(root, 'redacted', doc['doc'], 'page-%02d.png' % p['page'])
            pages.append(dict(png=png if os.path.isfile(png) else None, masked=p.get('n_masked', 0)))
        out[c] = pages
    return dict(exit=r.returncode, cases=out, calls=_calls(log), dpi=dpi)


# ---- judging output bytes ----

def _png_chunks(path):
    """The chunks of a PNG as (type, tEXt keyword or None), or None when the file is not one (bad signature,
    cut or bad CRC)."""
    data = open(path, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    i, types = 8, []
    while i + 12 <= len(data):
        n, typ = struct.unpack('>I4s', data[i:i + 8])
        body = data[i + 8:i + 8 + n]
        if len(body) != n or zlib.crc32(typ + body) & 0xffffffff != struct.unpack('>I', data[i + 8 + n:i + 12 + n])[0]:
            return None
        types.append((typ, body.split(b'\0')[0] if typ == b'tEXt' else None))
        i += 12 + n
        if typ == b'IEND':
            return types if i == len(data) else None
    return None


def _size(png):
    r = _run(_im() + [png, '-format', '%w %h', 'info:'])
    try:
        w, h = r.stdout.split()[:2]
        return int(w), int(h)
    except ValueError:
        return None


def _level(png, geom, stat):
    """The `stat` (maxima or mean, 0 black to 1 white) of the grey pixels in geom (WxH+X+Y) of the image."""
    r = _run(_im() + [png, '-alpha', 'off', '-colorspace', 'Gray', '-crop', geom, '+repage',
                      '-format', '%[fx:' + stat + ']', 'info:'])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def _dark(png, geom):
    """Every pixel in geom is black (an unreadable image is not)."""
    v = _level(png, geom, 'maxima')
    return v is not None and v <= 0.02


def _white(png, geom):
    """The pixels in geom are white on average (an unreadable image is not)."""
    v = _level(png, geom, 'mean')
    return v is not None and v >= 0.98


def _ocr_texts(png):
    """What real tesseract reads from the page in two layouts (whole-page and sparse), each as text in reading order."""
    return [_run(['tesseract', png, 'stdout', '-l', LANG, '--psm', psm]).stdout or '' for psm in ('3', '11')]


def _words(texts):
    """The words of those texts, letters and digits only (compared with this file's own fixture words)."""
    return {re.sub(r'[^A-Za-z0-9]', '', w) for t in texts for w in t.split()}


def _leaks(texts):
    """Does any layout's digits, in reading order, hold six digits in a row of the number? (the number is this
    file's own invented one; six, so an OCR slip or a split across words still shows)"""
    runs = {NUMBER[i:i + 6] for i in range(len(NUMBER) - 5)}
    streams = [re.sub(r'\D', '', t) for t in texts]
    return any(r in st for st in streams for r in runs)


def _in_box(box, pad):
    x, y, w, h = box
    x0, y0 = max(0, x - pad), max(0, y - pad)
    return f'{w + 2 * pad}x{h + 2 * pad}+{x0}+{y0}'


def evaluate(res, box, cases):
    """{(assertion, case): True/False}. A page that is missing makes each of its assertions False."""
    out = {}

    def put(a, c, ok):
        out[(a, c)] = bool(ok)

    for c in cases:
        pages = res['cases'].get(c) or []
        want = len(CASES[c])
        pages_ok = len(pages) == want and all(p['png'] for p in pages)
        numbered = [i for i, (_, n, _) in enumerate(CASES[c]) if n]
        put('PAGES_WRITTEN', c, pages_ok)
        if not pages_ok:
            for a in ('OCR_NOT_RECOVERABLE', 'PLAIN_RASTER', 'MASK_BLACK', 'PAGE_KEPT'):
                put(a, c, False)
            if c == 'page2':
                put('PAGE1_UNMASKED', c, False)
            if c == 'rotated':
                put('UPRIGHT', c, False)
            continue
        pngs = [p['png'] for p in pages]
        texts = [_ocr_texts(p) for p in pngs]
        words = [_words(t) for t in texts]
        put('OCR_NOT_RECOVERABLE', c, not any(_leaks(t) for t in texts))
        chunks = [_png_chunks(p) for p in pngs]
        put('PLAIN_RASTER', c, all(k is not None and all(
            t in PNG_PIXEL_CHUNKS or t == b'tIME' or (t == b'tEXt' and key in PNG_DATE_STAMPS) for t, key in k)
            for k in chunks))
        put('MASK_BLACK', c, all(_dark(pngs[i], _in_box(box, MARGIN)) for i in numbered))
        # the ground well away from the number's line is white, and the page's own words still read
        keep = all(_white(p, f'400x150+{PAGE_W - 450}+{PAGE_H - 250}') and sum(1 for w in WORDS if w in ws) >= 3
                   for p, ws in zip(pngs, words))
        put('PAGE_KEPT', c, keep)
        if c == 'page2':
            put('PAGE1_UNMASKED', c, pages[0]['masked'] == 0 and _white(pngs[0], _in_box(box, MARGIN)))
        if c == 'rotated':
            put('UPRIGHT', c, all(_size(p) == (PAGE_W, PAGE_H) for p in pngs) and out[('PAGE_KEPT', c)]
                and out[('MASK_BLACK', c)])
    put('LANG_REACHES', 'run', _lang_ok(res))
    put('DPI_REACHES', 'run', _dpi_ok(res, cases))
    return out


def _lang_ok(res):
    reads = [c for c in res['calls'] if c and c[0] != '--list-langs' and 'tsv' in c]
    return bool(reads) and all(_after(c, '-l') == LANG for c in reads)


def _dpi_ok(res, cases):
    renders = [c for c in res['calls'] if '-png' in c and '-r' in c]
    scale = res['dpi'] / DPI
    sizes = [_size(p['png']) for c in cases for p in res['cases'].get(c, []) if p['png']]
    want = {(PAGE_W, PAGE_H), (PAGE_H, PAGE_W)}
    ok_sizes = all(s is not None and (round(s[0] / scale), round(s[1] / scale)) in want for s in sizes)
    return bool(renders) and all(_after(c, '-r') == str(res['dpi']) for c in renders) and bool(sizes) and ok_sizes


# ---- the controls: runs broken on purpose ----

def run_broken(mode, argv):
    """Child mode: redact_ids.main with one fault put in, to prove this check sees it."""
    sys.path.insert(0, HERE)
    import redact_ids as R
    if mode == 'zero-pad':
        orig = R.pad_clamp
        R.pad_clamp = lambda box, W, H, pad: orig(box, W, H, 0)
    elif mode == 'skip-burn':
        orig = R.burn
        R.burn = lambda src, boxes, out: orig(src, [], out)
    elif mode == 'swap-xy':
        orig = R.burn
        R.burn = lambda src, boxes, out: orig(src, [[b[1], b[0], b[3], b[2]] for b in boxes], out)
    elif mode == 'page1-masks':
        orig, first = R.burn, {}
        R.burn = lambda src, boxes, out: orig(src, first.setdefault(os.path.dirname(out), list(boxes)), out)
    elif mode == 'page1-leak':       # page 2's mask also lands on page 1 (a box [x1, y1, x2, y2] round the number)
        orig = R.burn
        leak = [NUMBER_AT[0] - 10, NUMBER_AT[1] - 35, NUMBER_AT[0] + 240, NUMBER_AT[1] + 10]
        R.burn = lambda src, boxes, out: orig(src, list(boxes) + ([leak] if out.endswith('page-01.png') else []), out)
    elif mode == 'no-rotate':
        R.rotate_to = lambda src, dst, deg: (shutil.copyfile(src, dst), dst)[1]
    elif mode in ('ignore-lang', 'ignore-dpi'):
        orig = R.run_checked

        def run_checked(cmd, *a, **k):
            cmd = list(cmd)
            if mode == 'ignore-lang' and cmd and cmd[0] == 'tesseract' and '-l' in cmd:
                cmd[cmd.index('-l') + 1] = 'eng+osd'
            if mode == 'ignore-dpi' and cmd and cmd[0] == 'pdftoppm' and '-r' in cmd:
                cmd[cmd.index('-r') + 1] = '300'
            return orig(cmd, *a, **k)
        R.run_checked = run_checked
    elif mode != 'none':
        return EXIT_USAGE
    return R.main(argv)


def main(argv):
    if len(argv) >= 3 and argv[0] == '--run-broken' and argv[2] == '--':
        return run_broken(argv[1], argv[3:])
    if argv:
        print('usage: python3 tools/private-mode/real_tools_check.py   (no arguments)')
        return EXIT_USAGE
    try:
        absent, old = tool_problems()
    except Setup as e:
        print('SETUP_ERROR ' + str(e))
        return EXIT_SETUP
    if absent:
        print('TOOLS_ABSENT ' + ' '.join(absent))
        return EXIT_ABSENT
    if old:
        print('TOOLS_WRONG_VERSION ' + ' '.join(old))
        return EXIT_WRONG_VERSION
    root = os.path.realpath(tempfile.mkdtemp(prefix='tabularium-real-tools-'))
    try:
        box = _number_box()
        main_res = run_pipeline(os.path.join(root, 'main'), ALL_CASES, DPI)
        other = run_pipeline(os.path.join(root, 'other'), ('plain',), OTHER_DPI)
        results = evaluate(main_res, box, ALL_CASES)
        scaled = tuple(round(v * OTHER_DPI / DPI) for v in box)     # the same number, on a bigger render
        results.update({(a + '@' + str(OTHER_DPI), c): v for (a, c), v in evaluate(other, scaled, ('plain',)).items()
                        if a in ('DPI_REACHES', 'MASK_BLACK', 'OCR_NOT_RECOVERABLE')})
        results[('EXIT_CLEAN', 'run')] = main_res['exit'] == 0 and other['exit'] == 0
        failed = sorted(k for k, v in results.items() if not v)
        for (a, c), v in sorted(results.items()):
            print(('pass ' if v else 'FAIL ') + a + ' ' + c)
        if failed:
            print('CHECK_FAILED failed=%d of %d' % (len(failed), len(results)))
            return EXIT_CHECK_FAILED
        missed = []
        for brk in BREAKS:
            res = run_pipeline(os.path.join(root, 'broken-' + brk), CASES_FOR[brk], DPI, brk)
            got = evaluate(res, box, CASES_FOR[brk])
            # caught = the run still wrote its pages, and the one assertion this break aims at failed: a break
            # that only made the pipeline fail would show nothing of what the check judges
            usable = all(got.get(('PAGES_WRITTEN', c), False) for c in CASES_FOR[brk])
            tripped = usable and not got.get(CATCHES[brk], True)
            print(('caught ' if tripped else 'MISSED ') + brk)
            if not tripped:
                missed.append(brk)
        if missed:
            print('CONTROL_NOT_CAUGHT missed=%d of %d' % (len(missed), len(BREAKS)))
            return EXIT_CONTROL
        print('REAL_TOOLS_OK checks=%d controls=%d' % (len(results), len(BREAKS)))
        return EXIT_OK
    except Setup as e:
        print('SETUP_ERROR ' + str(e))
        return EXIT_SETUP
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    try:
        code = main(sys.argv[1:])
    except Exception:       # a traceback would print paths: say the category and stop
        print('SETUP_ERROR unexpected')
        code = EXIT_SETUP
    sys.exit(code)
