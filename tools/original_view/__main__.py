#!/usr/bin/env python3
"""Write a light, downscaled JPEG of one page of a person's original into a scratch folder, so a
session can open an original too large for its file reader (ADR-0037 §14).

    python3 -m tools.original_view [--root DIR] <handle> --relpath med/sources/<file> --out <dir>
                                   [--page N] [--max-edge PX]

- **Private mode refuses outright**, before the original is touched: the person's profile carries the
  private-mode marker or cannot be read (the board's test, `fsverify.person_status`), or their folder
  holds an identity file of kept details (the read guard's durable sign; the name comes from
  `tools/private-mode/identity.py`). Such a person's originals reach a session only as the
  operator-approved redacted rasters.
- The original is a regular file under the person's `med/sources/` or `med/_inbox/`, reached through
  no link and with no second hard link. The output folder exists, is not a link, and lies outside
  the repository read and this tool's own (compared by file identity, ancestor by ancestor); the copy
  is `<handle>__<stem>__p<N>.jpg`, owner-only, replacing an earlier view of the same page.
- PDF pages need poppler's `pdftoppm` (a host dependency of the render environment); image originals
  need Pillow — run with `.venv-render/bin/python`.

Exit: 0 written · 2 refused (the reason on stderr; no path) · 64 invalid invocation.
"""
import argparse
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata

from ..person_ownership import fsverify, schema
from ..person_ownership.append import AppendStop, _check_handle

PDF_EXT = ('.pdf',)
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp', '.gif')
LANES = ('med/sources/', 'med/_inbox/')
DEFAULT_EDGE = 1600
EDGE_RANGE = (200, 4000)
QUALITY = 85
PRIVATE = ("a private-mode person's originals reach a session only as the operator-approved redacted "
           "rasters (tools/private-mode/README.md)")


class Refused(Exception):
    """The view is not written; the message carries no path and no content."""


def identity_name():
    """The name of the identity file of kept details, from its one owner."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'private-mode', 'identity.py')
    try:
        spec = importlib.util.spec_from_file_location('tabularium_private_mode_identity', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.IDENTITY_NAME
    except (OSError, ImportError, AttributeError, SyntaxError):
        raise Refused('tools/private-mode/identity.py cannot be read, so private mode cannot be ruled '
                      'out (fail closed)')


def private_reason(root, handle):
    """Why this person's originals are never rasterised for a session, or None."""
    status = fsverify.person_status(root, handle)
    if status == 'private':
        return 'this person is in private mode'
    if status != 'public':
        return "this person's profile cannot be read, so private mode cannot be ruled out"
    if os.path.lexists(os.path.join(root, 'patients', handle, identity_name())):
        return 'this person has an identity file of kept details'
    return None


def _original(root, handle, relpath):
    rel = unicodedata.normalize('NFC', relpath or '')
    problem = schema._safe_relpath(rel)
    if problem:
        raise Refused('unsafe relpath (%s)' % problem)
    if not rel.startswith(LANES):
        raise Refused('the original must lie under the person\'s med/sources/ or med/_inbox/')
    if not rel.lower().endswith(PDF_EXT + IMAGE_EXT):
        raise Refused('not a PDF or an image (JPEG, PNG, TIFF, WebP, BMP, GIF); a text layer opens '
                      'directly')
    path = os.path.join(root, 'patients', handle)
    for part in rel.split('/'):
        path = os.path.join(path, part)
        if os.path.islink(path):
            raise Refused('a link on the way to the original')
    try:
        st = os.stat(path)
    except FileNotFoundError:
        raise Refused('no such original')
    if not stat.S_ISREG(st.st_mode):
        raise Refused('the original is not a regular file')
    if st.st_nlink > 1:
        # a hard link carries no owner in its path: it could be a private-mode person's original
        raise Refused('the original has more than one hard link, so whose it is cannot be told from '
                      'where it is filed')
    return path, rel


TOOL_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _out_dir(root, out):
    """The scratch folder, refused when it is not a plain existing folder or when it lies inside the
    repository being read or this tool's own: every resolved ancestor is compared with both by file
    identity, so neither a case variant (a case-insensitive filesystem) nor a link gets a copy into
    the records."""
    if not out or os.path.islink(out) or not os.path.isdir(out):
        raise Refused('--out must be an existing folder, not a link')
    repos = [os.stat(r) for r in (root, TOOL_REPO) if os.path.isdir(r)]
    real = os.path.realpath(out)
    here = real
    while True:
        st = os.stat(here)
        if any(os.path.samestat(st, r) for r in repos):
            raise Refused('--out must lie outside the repository (a scratch folder)')
        parent = os.path.dirname(here)
        if parent == here:
            return real
        here = parent


def _pdf_pages(src):
    exe = shutil.which('pdfinfo')
    if not exe:
        return None
    run = subprocess.run([exe, src], capture_output=True, text=True, errors='replace')
    for line in run.stdout.splitlines():
        if line.startswith('Pages:'):
            try:
                return int(line.split(':', 1)[1])
            except ValueError:
                return None
    return None


def _render_pdf(src, page, edge, dest):
    exe = shutil.which('pdftoppm')
    if not exe:
        raise Refused("PDF pages need poppler's pdftoppm (brew install poppler / apt-get install "
                      "poppler-utils)")
    pages = _pdf_pages(src)
    if pages is not None and page > pages:
        raise Refused('the original has %d page(s)' % pages)
    work = tempfile.mkdtemp(prefix='.view-', dir=os.path.dirname(dest))
    try:
        prefix = os.path.join(work, 'page')
        run = subprocess.run([exe, '-f', str(page), '-l', str(page), '-singlefile', '-scale-to',
                              str(edge), '-jpeg', '-jpegopt', 'quality=%d' % QUALITY, src, prefix],
                             capture_output=True)
        made = prefix + '.jpg'
        if run.returncode != 0 or not os.path.isfile(made):
            raise Refused('the PDF page could not be rendered')
        os.chmod(made, 0o600)
        os.replace(made, dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return pages


def _render_image(src, page, edge, dest):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise Refused('image originals need Pillow — run this with .venv-render/bin/python')
    fd, tmp = tempfile.mkstemp(prefix='.view-', suffix='.jpg', dir=os.path.dirname(dest))
    os.close(fd)
    try:
        try:
            with Image.open(src) as im:
                frames = getattr(im, 'n_frames', 1)
                if page > frames:
                    raise Refused('the original has %d page(s)' % frames)
                im.seek(page - 1)
                out = ImageOps.exif_transpose(im).convert('RGB')
                out.thumbnail((edge, edge))
                out.save(tmp, 'JPEG', quality=QUALITY)
        except Refused:
            raise
        except Exception:
            raise Refused('the image could not be read')
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return frames


def view(root, handle, relpath, out, page=1, max_edge=DEFAULT_EDGE):
    """Write the view and return (its path, the original's page count or None)."""
    try:
        handle = _check_handle(root, handle)
    except AppendStop as e:
        raise Refused(str(e))
    pdir = os.path.join(root, 'patients', handle)
    if os.path.islink(pdir) or not os.path.isdir(pdir):
        raise Refused('no such person folder (or it is a link)')
    reason = private_reason(root, handle)
    if reason:
        raise Refused(reason + ' — ' + PRIVATE)
    if not (isinstance(page, int) and page >= 1):
        raise Refused('--page counts from 1')
    if not (isinstance(max_edge, int) and EDGE_RANGE[0] <= max_edge <= EDGE_RANGE[1]):
        raise Refused('--max-edge must be between %d and %d pixels' % EDGE_RANGE)
    src, rel = _original(root, handle, relpath)
    folder = _out_dir(root, out)
    stem = os.path.splitext(os.path.basename(rel))[0]
    dest = os.path.join(folder, '%s__%s__p%d.jpg' % (handle, stem, page))   # one scratch folder, many people
    if os.path.islink(dest) or (os.path.lexists(dest) and not os.path.isfile(dest)):
        raise Refused('the output name is taken by a link or a folder')
    render = _render_pdf if rel.lower().endswith(PDF_EXT) else _render_image
    return dest, render(src, page, max_edge, dest)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python3 -m tools.original_view',
                                 description="A light JPEG of one page of a person's original")
    ap.add_argument('--root', default=os.getcwd(), help='repository root (default: cwd)')
    ap.add_argument('handle', help='patient folder handle under patients/')
    ap.add_argument('--relpath', required=True, help='med/sources/<file> or med/_inbox/<file>')
    ap.add_argument('--out', required=True, help='an existing scratch folder outside the repository')
    ap.add_argument('--page', type=int, default=1, help='page (or frame) to show, from 1')
    ap.add_argument('--max-edge', type=int, default=DEFAULT_EDGE,
                    help='longest edge in pixels (%d-%d, default %d)' % (EDGE_RANGE + (DEFAULT_EDGE,)))
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    try:
        dest, pages = view(a.root, a.handle, a.relpath, a.out, a.page, a.max_edge)
    except Refused as e:
        print('original_view: refused — %s' % e, file=sys.stderr)
        return 2
    except OSError:
        print('original_view: refused — a filesystem operation failed (locator withheld)',
              file=sys.stderr)
        return 2
    print('written: %s (page %d%s; longest edge at most %d px) — delete it when you are done'
          % (dest, a.page, ' of %d' % pages if pages else '', a.max_edge))
    return 0


if __name__ == '__main__':
    sys.exit(main())
