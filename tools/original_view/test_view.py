#!/usr/bin/env python3
"""Synthetic tests for tools.original_view (ADR-0037 §14). SYNTHETIC data only. Run:
    python3 -m unittest tools.original_view.test_view
Rendering cases need Pillow (and poppler's pdftoppm for PDFs) and skip loudly without them; every
refusal case runs anywhere.
"""
import contextlib
import io
import os
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from . import __main__ as V

try:
    from PIL import Image
except ImportError:      # pragma: no cover - depends on the host
    Image = None


class ViewTests(unittest.TestCase):
    def setUp(self):
        base = tempfile.mkdtemp(prefix='oview-')
        self.addCleanup(shutil.rmtree, base, True)
        self.root = os.path.join(base, 'repo')
        self.out = os.path.join(base, 'scratch')
        os.makedirs(self.out)
        self.pdir = os.path.join(self.root, 'patients', 'szview')
        os.makedirs(os.path.join(self.pdir, 'med', 'sources'))
        self.profile('# profile\n## Identity\n- Private mode: — none\n')

    def profile(self, text):
        with open(os.path.join(self.pdir, 'profile.md'), 'w', encoding='utf-8') as f:
            f.write(text)

    def src(self, name, data=b'x'):
        p = os.path.join(self.pdir, 'med', 'sources', name)
        with open(p, 'wb') as f:
            f.write(data)
        return 'med/sources/' + name

    def refused(self, rel='med/sources/2026-01-01__lab__x.png', out=None, want=None, **kw):
        with self.assertRaises(V.Refused) as cm:
            V.view(self.root, 'szview', rel, out or self.out, **kw)
        if want:
            self.assertIn(want, str(cm.exception))
        self.assertEqual(os.listdir(self.out), [])          # nothing written
        return str(cm.exception)

    def image(self, name='2026-01-01__lab__x.png', size=(3000, 2000), frames=1):
        if Image is None:
            self.skipTest('Pillow absent — run under .venv-render/bin/python for the render cases')
        p = os.path.join(self.pdir, 'med', 'sources', name)
        pages = [Image.new('RGB', size, (200, 30 * i, 40)) for i in range(frames)]
        pages[0].save(p, save_all=frames > 1, append_images=pages[1:])
        return 'med/sources/' + name

    # ---- private mode refuses before the original is touched ----------------------------------
    def assert_private_refusal(self):
        rel = self.src('2026-01-01__lab__x.png', b'never read')
        with mock.patch.object(V, '_original', side_effect=AssertionError('original touched')), \
                mock.patch.object(V, '_render_image', side_effect=AssertionError('rendered')):
            message = self.refused(rel, want='redacted rasters')
        self.assertNotIn('szview', message)
        self.assertNotIn('lab__x', message)

    def test_private_mode_marker_refuses(self):
        self.profile('# profile\n## Identity\n- Private mode: national ID ⟨never-API⟩\n')
        self.assert_private_refusal()

    def test_v2_identity_file_refuses_even_without_the_marker(self):
        with open(os.path.join(self.pdir, '.never-api-identity.json'), 'w') as f:
            f.write('{}')
        self.assert_private_refusal()

    def test_unreadable_or_missing_profile_refuses(self):
        os.remove(os.path.join(self.pdir, 'profile.md'))
        self.assert_private_refusal()

    def test_negative_control_a_public_person_reaches_the_renderer(self):
        rel = self.src('2026-01-01__lab__x.png')
        with mock.patch.object(V, '_render_image', return_value=1) as render:
            V.view(self.root, 'szview', rel, self.out)
        render.assert_called_once()

    # ---- where the original and the copy may be -----------------------------------------------
    def test_out_folder_inside_the_repository_refuses(self):
        rel = self.src('2026-01-01__lab__x.png')
        inside = os.path.join(self.root, 'scratch')
        os.makedirs(inside)
        with self.assertRaises(V.Refused) as cm:
            V.view(self.root, 'szview', rel, inside)
        self.assertIn('outside the repository', str(cm.exception))
        self.assertEqual(os.listdir(inside), [])

    def test_a_case_variant_or_linked_ancestor_of_the_repository_refuses(self):
        # compared by file identity: on a case-insensitive filesystem /…/Repo is /…/repo, and a link
        # to a folder inside the records resolves to it — either would put the copy into the records
        rel = self.src('2026-01-01__lab__x.png')
        lane = os.path.join(self.pdir, 'med', 'sources')
        variant = os.path.join(os.path.dirname(self.root), 'REPO', 'patients', 'szview', 'med', 'sources')
        if os.path.isdir(variant):
            with self.assertRaises(V.Refused) as cm:
                V.view(self.root, 'szview', rel, variant)
            self.assertIn('outside the repository', str(cm.exception))
        link = os.path.join(os.path.dirname(self.root), 'via')
        os.symlink(os.path.join(self.root, 'patients'), link)
        with self.assertRaises(V.Refused) as cm:
            V.view(self.root, 'szview', rel, os.path.join(link, 'szview', 'med', 'sources'))
        self.assertIn('outside the repository', str(cm.exception))
        self.assertEqual(sorted(os.listdir(lane)), ['2026-01-01__lab__x.png'])

    def test_the_tools_own_repository_refuses_whatever_the_root(self):
        rel = self.src('2026-01-01__lab__x.png')
        inside_tool_repo = tempfile.mkdtemp(prefix='.oview-', dir=V.TOOL_REPO)
        self.addCleanup(shutil.rmtree, inside_tool_repo, True)
        with self.assertRaises(V.Refused) as cm:
            V.view(self.root, 'szview', rel, inside_tool_repo)
        self.assertIn('outside the repository', str(cm.exception))
        self.assertEqual(os.listdir(inside_tool_repo), [])

    def test_a_hard_linked_original_refuses(self):
        rel = self.src('2026-01-01__lab__x.png')
        other = os.path.join(os.path.dirname(self.root), 'elsewhere.png')
        os.link(os.path.join(self.pdir, rel), other)
        self.refused(rel, want='hard link')

    def test_out_folder_link_or_missing_refuses(self):
        rel = self.src('2026-01-01__lab__x.png')
        link = os.path.join(os.path.dirname(self.out), 'link')
        os.symlink(self.out, link)
        self.refused(rel, out=link, want='not a link')
        self.refused(rel, out=os.path.join(self.out, 'absent'), want='existing folder')

    def test_original_outside_the_lanes_or_through_a_link_refuses(self):
        self.refused('profile.md', want='med/sources/')
        self.refused('med/sources/../../profile.md', want='unsafe relpath')
        real = os.path.join(os.path.dirname(self.root), 'elsewhere')
        os.makedirs(real)
        with open(os.path.join(real, 'x.png'), 'wb') as f:
            f.write(b'x')
        os.symlink(real, os.path.join(self.pdir, 'med', 'sources', 'linked'))
        self.refused('med/sources/linked/x.png', want='link on the way')
        self.refused('med/sources/2026-01-01__lab__absent.png', want='no such original')

    def test_text_layers_and_unknown_formats_refuse(self):
        self.refused(self.src('2026-01-01__lab__x.ocr.md'), want='not a PDF or an image')
        self.refused(self.src('2026-01-01__lab__x.heic'), want='not a PDF or an image')

    def test_bounds(self):
        rel = self.src('2026-01-01__lab__x.png')
        self.refused(rel, page=0, want='--page')
        self.refused(rel, max_edge=50, want='--max-edge')

    def test_cli_refusal_prints_no_path_and_exits_2(self):
        self.profile('# profile\n- Private mode: ⟨never-API⟩\n')
        rel = self.src('2026-01-01__lab__x.png')
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = V.main(['--root', self.root, 'szview', '--relpath', rel, '--out', self.out])
        self.assertEqual(code, 2)
        self.assertNotIn('lab__x', err.getvalue())
        self.assertNotIn(self.root, err.getvalue())

    # ---- rendering (needs Pillow; PDFs also pdftoppm) -----------------------------------------
    def test_large_image_becomes_a_light_owner_only_jpeg(self):
        rel = self.image()
        dest, pages = V.view(self.root, 'szview', rel, self.out)
        self.assertEqual(os.path.basename(dest), 'szview__2026-01-01__lab__x__p1.jpg')
        self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)
        with Image.open(dest) as im:
            self.assertEqual(im.format, 'JPEG')
            self.assertEqual(max(im.size), V.DEFAULT_EDGE)
        self.assertEqual(sorted(os.listdir(self.out)), ['szview__2026-01-01__lab__x__p1.jpg'])  # no temp left

    def test_multi_page_image_and_page_out_of_range(self):
        rel = self.image('2026-01-01__lab__y.tiff', size=(800, 600), frames=2)
        dest, pages = V.view(self.root, 'szview', rel, self.out, page=2, max_edge=400)
        self.assertEqual(pages, 2)
        with Image.open(dest) as im:
            self.assertEqual(max(im.size), 400)
        with self.assertRaises(V.Refused):
            V.view(self.root, 'szview', rel, self.out, page=3)

    def test_pdf_page(self):
        if shutil.which('pdftoppm') is None:
            self.skipTest("poppler's pdftoppm absent — the PDF render case needs it")
        if Image is None:
            self.skipTest('Pillow absent — needed to build the synthetic PDF')
        p = os.path.join(self.pdir, 'med', 'sources', '2026-01-01__lab__z.pdf')
        pages = [Image.new('RGB', (1240, 1754), (255, 255, 255)) for _ in range(2)]
        pages[0].save(p, save_all=True, append_images=pages[1:], resolution=150)
        dest, count = V.view(self.root, 'szview', 'med/sources/2026-01-01__lab__z.pdf', self.out, page=2)
        self.assertEqual(os.path.basename(dest), 'szview__2026-01-01__lab__z__p2.jpg')
        with Image.open(dest) as im:
            self.assertEqual(max(im.size), V.DEFAULT_EDGE)
        if shutil.which('pdfinfo'):
            self.assertEqual(count, 2)
            with self.assertRaises(V.Refused):
                V.view(self.root, 'szview', 'med/sources/2026-01-01__lab__z.pdf', self.out, page=3)
        self.assertEqual(sorted(os.listdir(self.out)), ['szview__2026-01-01__lab__z__p2.jpg'])


if __name__ == '__main__':
    unittest.main()
