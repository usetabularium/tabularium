#!/usr/bin/env python3
"""Render a Tabularium handout markdown file to a styled PDF — with a footer, an automated
build-QA pass, and a plaintext fallback.

Canonical toolchain (HANDOUT-RULES.md → Rendering): python-markdown with `sane_lists`, `tables`,
`attr_list` and `meta` → weasyprint, with the shared house stylesheet (handout.css). This is the
single render path so every handout gets the same typography, the same footer, and the same
verification. Do not hand-roll a markdown→PDF conversion.

Front-matter (optional, at the very TOP of the .md, `key: value` lines then a blank line):
    id:    TAB-<PPP>-<NNN><C>       handout identifier, printed in the footer (ADR-0033)
    date:  YYYY-MM-DD               preparation date, printed in the footer as DD.MM.YYYY
    lang:  en | pl                  footer language (default en); body language is the author's
The title, occasion subheader and patient identity live in the BODY, not here.

Build-QA (non-LLM, fast — ADR-0034): after rendering, the output is checked for the mechanical
breakages that have bitten us before (broken tables, collapsed references <ol>, literal attr_list
markers, tofu/uncovered glyphs, missing page numbers, leaked unfinished-text markers, a list that ran
into the paragraph above it for lack of a blank line, a draft page without its draft line). If it cannot be verified clean, the helper writes a
plain-but-correct `.txt` fallback instead of handing over a suspect PDF (accuracy over aesthetics)
and exits non-zero — except for authoring faults (B0/B7/B8), which halt so the source gets fixed.

Sealing (ADR-0039): by default a render is a SEAL — it refuses unless a fresh PASS/0 fact-check
sidecar (ADR-0034) matches the Markdown's current SHA-256 — and, when the sidecar records them, the
person's current profile.md and medications.md (ADR-0070) — (canonical order: author → fact-check →
render+attest), renders CRASH-SAFE (sibling temp → build-QA on the temp → atomic os.replace promote;
a prior good deliverable is never clobbered before the new one verifies), and then writes a sibling
`<stem>.attest.json` (schema v1: md/factcheck/output SHA-256s, kind pdf|txt, build_qa PASS|FALLBACK,
person+encounter binding) atomically, LAST — so any crash window leaves an output newer than its
attestation, which guard L15 reads as red, never silent-green.

Refusals (red-team 2026-07-17 — all exit 5): a seal happens IN PLACE at
patients/<handle>/med/handouts/<audience>/<YYYY-MM-DD-slug>/<leaf>.md, with the leaf date equal to
the encounter-dir date, the resolved audience equal to the containing audience dir, and no --out
other than the canonical sibling <stem>.pdf; an explicit --audience contradicting the filename's
__handout-<audience>__ token refuses (the flag never silently wins); a stem whose .attest.json
already exists refuses in every mode — sealed units are IMMUTABLE, supersede with a new dated unit.
The attestation binds person (handle) + encounter (dir name), so a sealed unit copied into another
patient's tree or re-dated is red (L15 person-mismatch / encounter-mismatch).

`--draft` renders an eyeball copy with no gate and no attestation, to `<stem>.draft.pdf` by
default, and NEVER touches live deliverables (no promote onto the canonical name, no fallback
deletion, no stale-txt sweep). Drafts belong OUTSIDE sealed encounter dirs — L15 reds a draft
artifact inside one (loud), and the live bytes stay intact. Every page of a draft PDF prints a "draft —
not fact-checked" line in the top margin, and a draft's text fallback opens with it, so a printed or
forwarded draft cannot pass for a sealed handout; the margin keeps the page layout identical to the seal's.

`--preview-html NEW.html` additionally saves a standalone local reading copy styled with the Tabularium
design system (preview.css — the PDF keeps handout.css) and the exact generated PDF embedded as its download. It has no editor or browser-print path;
Markdown remains the source. The preview is new, private, outside med/handouts, and stays in the same
person's record directory when the source is there. Without this option the render path is unchanged.

Usage:
    python3 render_handout.py INPUT.md [--audience patient|clinician] [--out OUT.pdf]
                              [--no-fallback] [--draft] [--preview-html NEW.html]
Exit: 0 sealed/drafted clean · 3 build-QA failed · 4 fact-check gate refused ·
      5 refused (location / immutability / audience contradiction / non-canonical --out).

Requires: python-markdown, weasyprint (+ poppler `pdftotext` for the QA text scan; falls back to
pypdf if absent). Fonts are bundled under ./fonts (OFL) — no network. Reproducible env: the pinned
sibling requirements-render.txt → repo-local .venv-render/ (ADR-0039).
"""
import argparse, base64, datetime, hashlib, html, importlib.util, io, json, logging, os, re, stat, subprocess, sys, tempfile, unicodedata
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import url2pathname

TOOL_VERSION = "render_handout.py/2.10.0"      # bump on any change to render/QA/attest behaviour
ATTEST_SCHEMA = "tabularium-handout-attest/v1"  # ADR-0039 §4 — L15 verifies against this exact value
LEAF_MD_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})__handout-(patient|clinician)__(.+)\.md$")
# An extractor, not a validator: the renderer refuses a footer that disagrees with a stable ID already
# in the source filename (unmarked legacy filenames keep their behaviour). The front-matter ID itself is
# validated against tools/handout_attest/handout_id.py, the one Python check character (B0 halt).
FILENAME_STABLE_ID_RE = re.compile(
    r"__(?P<id>TAB-[0-9A-HJKMNP-TV-Z]{3}-[0-9]{3}[0-9A-HJKMNP-TV-Z](?:\.r[0-9]+)?)\.md$")

HERE = os.path.dirname(os.path.realpath(__file__))
# A seal is a repository state transition, not merely a path-shaped render. Anchor it to the
# repository that owns this renderer; unit tests may monkeypatch this module constant, but there is
# deliberately no CLI/environment override that could mint an unguarded external "seal".
REPO_ROOT = os.path.realpath(os.path.join(HERE, "..", ".."))
CSS_PATH = os.path.join(HERE, "handout.css")
PREVIEW_CSS_PATH = os.path.join(HERE, "preview.css")   # screen-only design-system stylesheet (ADR-0058)
FONTS = os.path.join(HERE, "fonts")

FOOTER = {  # per-language footer strings; page counter is CSS (reliable — weasyprint computes it)
    # "attr" ends with the site root; the clinician closing note links the clinicians page. "draft" is the top-margin line
    # every page of a --draft render prints (a seal never does): a draft skipped the fact-check gate.
    "pl": {"prep": "Przygotowano {d}",
           "attr": "z pomocą asystenta AI · Tabularium · usetabularium.com",
           "page": '"str. " counter(page) " / " counter(pages)',
           "draft": "WERSJA ROBOCZA — treść niezweryfikowana"},
    "en": {"prep": "Prepared {d}",
           "attr": "with an AI assistant · Tabularium · usetabularium.com",
           "page": '"p. " counter(page) " / " counter(pages)',
           "draft": "DRAFT — not fact-checked"},
}

# Build-QA B7 reads the rendered PDF text for two kinds of word (split 2026-10-04, so a style word never
# blocks a handout that is otherwise right):
#   LEAK  — an unfinished draft or a private-data leak. HALTS with NO fallback: the source is wrong.
#   STYLE — system-internal vocabulary a reader should not see. WARNS (one stderr line per class) and
#           the render continues.
# NOTE (2026-07-06 red-team): bare "baseline"/"delta" are in neither list. Both are real clinical terms
# in reader-facing prose ("fala delta" / EEG delta wave, "wariant Delta", a baseline lab value, an
# English clinician handout's "baseline renal function"). The internal baseline-vs-delta *handout-type*
# framing lives only in INDEX.md (never rendered); HANDOUT-RULES still lists both as author guidance
# (the check is a backstop, not an exhaustive filter).
LEAK = re.compile(
    r"⟨confirm|\{\{|\bTODO\b|\bFIXME\b|\.factcheck|MUST-FIX|⟨withheld|\bwithheld:[a-z]", re.IGNORECASE)
STYLE = (
    ("an evidence grade (grade A-D)", re.compile(r"\bgrade[\s\-]?[A-D]\b", re.IGNORECASE)),
    ("the word \"Vetted\"", re.compile(r"\bVetted\b", re.IGNORECASE)),
    ("\"reference library\"", re.compile(r"reference[\s\-]?library", re.IGNORECASE)),
    ("the word \"handout\"", re.compile(r"\bhandouts?\b", re.IGNORECASE)),
    ("a calendar id (cal-...)", re.compile(r"\bcal-[a-z0-9]", re.IGNORECASE)),
    ("attr-list syntax ({: .)", re.compile(r"\{:\s*\.")),
)


def style_words(text):
    """Names of the style-word classes found in `text` (each once, in table order)."""
    return [name for name, rx in STYLE if rx.search(text)]


ALLOW_FALLBACK = set("⟨⟩")  # glyphs we knowingly let a system font supply


def fmt_date(iso):
    """Footer prep-date: the front-matter `YYYY-MM-DD`, printed as DD.MM.YYYY in every language. An
    empty value returns "" (B0 reports the missing field); any other value that is not a real
    YYYY-MM-DD calendar date raises ValueError, which render() halts on as a B0 authoring fault."""
    iso = (iso or "").strip()
    if not iso:
        return ""
    m = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", iso)
    if not m:
        raise ValueError("front-matter date is not YYYY-MM-DD")
    d = datetime.date(*map(int, m.groups()))
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def infer_audience(name):
    if "__handout-patient__" in name:
        return "patient"
    if "__handout-clinician__" in name:
        return "clinician"
    return None


def assert_filename_id_matches_metadata(in_path, handout_id):
    """Reject a footer ID that contradicts a recognized stable filename ID.

    Filename validity remains L8's one authority. This narrow check gives drafts and seals the same
    pre-output protection while preserving the forward-only, no-ID legacy lane.
    """
    match = FILENAME_STABLE_ID_RE.search(os.path.basename(in_path))
    if match and handout_id != match.group("id"):
        _refuse("front-matter ID contradicts the stable ID in the filename (values withheld)")


def _handout_id_module():
    path = os.path.join(REPO_ROOT, "tools", "handout_attest", "handout_id.py")
    try:
        spec = importlib.util.spec_from_file_location("tabularium_handout_id", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except (OSError, ImportError, AttributeError, SyntaxError):
        _refuse("the stable-ID check needs tools/handout_attest/handout_id.py beside this renderer "
                "(fail closed)")


def assert_front_matter_id_valid(handout_id):
    """B0-class halt (exit 3, nothing written) for a front-matter ID that is malformed or carries the
    wrong check character (ADR-0033 point 8) — any value holding `TAB` in any case or a
    non-ASCII character; a plain-ASCII legacy value is left to B0's presence test, as before. This is the
    only check of it. A draft halts too, so the ID is right before the fact-check binds the bytes."""
    verdict = _handout_id_module().front_matter_id_verdict(handout_id)
    if verdict in ("", "ok"):
        return
    if verdict == "malformed":
        reason = ("not the form TAB-<PPP>-<NNN><C>[.rN] — unquoted, upper-case, no look-alike or hidden "
                  "characters")
    else:
        reason = "wrong check character; it should be '%s'" % verdict
    print("BUILD-QA FAILED:", file=sys.stderr)
    print("  - B0: front-matter id: %s (id withheld) — correct it, or take a valid one from "
          "`python3 -m tools.handout_attest next-id <handle>`." % reason, file=sys.stderr)
    print("→ CONTENT problem — halting; fix the source. No fallback written.", file=sys.stderr)
    sys.exit(3)


def _refuse(msg):
    print(f"SEAL REFUSED: {msg}", file=sys.stderr)
    sys.exit(5)


def seal_location(in_path, audience):
    """A SEAL happens only in place — patients/<handle>/med/handouts/<audience>/<YYYY-MM-DD-slug>/ —
    and returns (handle, encounter) for the attestation's person/encounter binding, else exits 5.
    Red-team 2026-07-17: a seal outside the unit shape produced a cosmetic attestation L15 never
    opens, and an unbound attestation made sealed units portable across patients and dates."""
    candidate = os.path.abspath(in_path)
    # Recover the lexical repository prefix from the exact unit depth, then bind its inode to the
    # renderer's real owning repository. `samefile` absorbs macOS /var↔/private/var spelling without
    # realpathing the patient path (which would erase the very symlink evidence checked below).
    candidate_root = candidate
    for _ in range(7):  # patients/handle/med/handouts/audience/encounter/leaf
        candidate_root = os.path.dirname(candidate_root)
    try:
        anchored = os.path.samefile(candidate_root, REPO_ROOT)
    except OSError:
        anchored = False
    if not anchored:
        _refuse("a seal renders in place under patients/<handle>/med/handouts/<audience>/"
                "<YYYY-MM-DD-slug>/ — file the unit there first, or use --draft for an eyeball copy")
    root_parts = os.path.relpath(candidate, candidate_root).split(os.sep)
    if len(root_parts) != 7 or root_parts[0] != "patients":
        _refuse("a seal renders in place under patients/<handle>/med/handouts/<audience>/"
                "<YYYY-MM-DD-slug>/ — file the unit there first, or use --draft for an eyeball copy")
    rel_parts = root_parts[1:]
    if rel_parts[1:3] != ["med", "handouts"] or not rel_parts[0] \
       or rel_parts[0].startswith("."):
        _refuse("a seal renders in place under patients/<handle>/med/handouts/<audience>/"
                "<YYYY-MM-DD-slug>/ — file the unit there first, or use --draft for an eyeball copy")
    handle, _med, _handouts, aud, enc, leaf = rel_parts

    # lstat every repository-relative component before reading. A symlinked patient/audience/
    # encounter/leaf could otherwise redirect a correctly shaped lexical path outside the guarded
    # tree; special files can block or violate byte binding.
    components = [candidate_root]
    cur = candidate_root
    for part in root_parts:
        cur = os.path.join(cur, part)
        components.append(cur)
    try:
        modes = [os.lstat(path).st_mode for path in components]
    except OSError:
        _refuse("seal location cannot be inspected completely (locator withheld; fail closed)")
    if any(stat.S_ISLNK(mode) for mode in modes):
        _refuse("seal location contains a symlink (locator withheld; fail closed)")
    if any(not stat.S_ISDIR(mode) for mode in modes[:-1]) or not stat.S_ISREG(modes[-1]):
        _refuse("seal location contains a non-directory/non-regular component "
                "(locator withheld; fail closed)")
    if aud != audience:
        _refuse("resolved audience does not match the containing audience directory "
                "(locator/value withheld)")
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*$", enc)
    valid = False
    if m:
        try:
            datetime.date.fromisoformat(m.group(1))
            valid = True
        except ValueError:
            pass
    if not valid:
        _refuse("encounter directory is not a valid YYYY-MM-DD-<slug> value (locator withheld)")
    leaf_match = LEAF_MD_RE.fullmatch(leaf)
    if not leaf_match:
        _refuse("handout leaf does not use the canonical Markdown filename grammar "
                "(locator/value withheld)")
    if leaf_match.group(2) != audience:
        _refuse("handout leaf audience does not match the resolved audience "
                "(locator/value withheld)")
    if leaf_match.group(1) != enc[:10]:
        _refuse("handout leaf date does not match its encounter directory date "
                "(locator/value withheld; one unit, one date)")
    return handle, enc


# ---- kept details (ADR-0029 point 13, ADR-0075): the source carries placeholders for the
# details a private-mode person keeps from the AI; a draft shows the handle (and neutral labels) in their place, so the
# assistant's visual check never sees them; the seal fills in the recorded values from the person's
# identity file, here, on the Mac, and L15 binds the delivered bytes. A render fault halts: no
# plaintext fallback, no HTML preview of the final, since either would carry the values outside
# every check. The operator looks at the sealed PDF before handing it over.
PLACEHOLDER_RE = re.compile(r"⟨withheld:([a-z-]+)⟩")
PLACEHOLDER_CLASS = {"patient-name": "patient_names", "date-of-birth": "dob", "other-name": "other_names",
                     "id-number": "id_numbers", "address": "addresses", "phone": "phones",
                     "email": "emails", "case-number": "case_numbers"}
MD_SPECIAL = re.compile(r"([\\`*_{}\[\]|#])")


def bundled_only_fetcher():
    """A URL fetcher that serves only `data:` URLs and files under this directory (the stylesheet and
    its fonts). Anything else — a remote image, a local file outside the assets — stops the render:
    a handout source must never make the renderer reach the network (a kept-details seal would carry the filled
    values in the URL) or embed another file in a delivered PDF."""
    from weasyprint.urls import URLFetcher, FatalURLFetchingError

    class BundledOnly(URLFetcher):
        def fetch(self, url, headers=None):
            parts = urlsplit(url)
            if parts.scheme == "data":
                return super().fetch(url, headers)
            if parts.scheme == "file" and parts.netloc in ("", "localhost"):
                target = os.path.realpath(url2pathname(parts.path))
                if target.startswith(HERE + os.sep):
                    return super().fetch(url, headers)
            raise FatalURLFetchingError("a resource outside the bundled assets")
    return BundledOnly()


def _identity_module():
    path = os.path.join(REPO_ROOT, "tools", "private-mode", "identity.py")
    try:
        spec = importlib.util.spec_from_file_location("tabularium_private_mode_identity", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except (OSError, ImportError, AttributeError, SyntaxError):
        _refuse("kept details need tools/private-mode/identity.py beside this renderer (fail closed)")


def kept_details_substitutions(in_path, text, draft):
    """None for an ordinary handout. For a person with kept details (an identity file in their folder):
    {placeholder name: text} — the handle and neutral labels in a draft, the recorded values in a seal.
    Refuses (exit 5) a source whose placeholders cannot be resolved; never prints a value."""
    rel = os.path.relpath(os.path.realpath(in_path), REPO_ROOT).split(os.sep)
    handle = rel[1] if len(rel) >= 3 and rel[0] == "patients" else None
    pdir = os.path.join(REPO_ROOT, "patients", handle) if handle else None
    # the front matter as the renderer itself reads it (indented keys, no space after the colon and
    # `---` blocks included): a placeholder there would reach the footer and the readable attestation
    import markdown
    probe = markdown.Markdown(extensions=["meta"])
    probe.convert(text)
    front = " ".join(" ".join(v) for v in getattr(probe, "Meta", {}).values())
    if PLACEHOLDER_RE.search(front):
        _refuse("a withheld-value placeholder belongs in the body, never in the front matter (its values "
                "reach the footer and the readable attestation)")
    # nor inside markup: a link target, an image source, any other attribute or a style sheet (CSS can
    # make a link) would carry the filled value into the PDF's link annotations (a click sends it to
    # that host), where B9 cannot see it. The unfilled body is parsed by the engine's own HTML parser,
    # so a quote or a `>` inside an attribute reads here exactly as it will in the render.
    from weasyprint import HTML
    probe_html = markdown.Markdown(extensions=["tables", "sane_lists", "attr_list", "meta"]).convert(text)
    tree = HTML(string="<!DOCTYPE html><html><head></head><body>\n%s\n</body></html>" % probe_html).etree_element
    for el in tree.iter():
        markup = " ".join(k + "=" + v for k, v in el.attrib.items())
        if el.tag == "style":
            markup += " " + (el.text or "")
        if "⟨withheld:" in markup:
            _refuse("a withheld-value placeholder belongs in plain text, never in a link target, an image, "
                    "another attribute or a style sheet (its value would travel with the link)")
    keys = set(PLACEHOLDER_RE.findall(text))
    if not keys:                       # nothing to fill: the source carries no kept detail
        return None
    if handle is None:
        _refuse("withheld-value placeholders render only from a source inside its person's folder")
    ident = _identity_module()
    if not os.path.lexists(os.path.join(pdir, ident.IDENTITY_NAME)):
        if keys:
            _refuse("the source holds withheld-value placeholders, but its person keeps no details in an "
                    "identity file; restore it from the latest snapshot, or write the details by role")
        return None
    unknown = keys - set(PLACEHOLDER_CLASS)
    if unknown:
        _refuse("the source holds an unknown withheld-value placeholder (value withheld)")
    if draft:
        return {k: (handle if k == "patient-name" else "[%s]" % k) for k in keys}
    try:
        data = ident.load(pdir)
    except ident.Refused as e:
        _refuse("kept details: %s" % e)
    if data is None:
        _refuse("kept details: the person's identity file cannot be read; the operator restores it")
    subs = {}
    for k in sorted(keys):
        vals = ident.values(data, PLACEHOLDER_CLASS[k])
        if not vals or (k != "patient-name" and len(vals) != 1):
            _refuse("placeholder %s needs exactly one recorded value (the person's first name entry "
                    "for patient-name); write the detail by role instead" % k)
        v = vals[0]
        if isinstance(v, dict):
            v = v["given"] + " " + v["family"]
        if k == "date-of-birth":
            v = fmt_date(v)
        subs[k] = v
    return subs


def fill_placeholders(text, subs):
    """The source with every placeholder replaced, Markdown-escaped so a value cannot alter structure."""
    return PLACEHOLDER_RE.sub(
        lambda m: MD_SPECIAL.sub(r"\\\1", html.escape(subs[m.group(1)], quote=False)), text)


def footer_css(hid, date_str, lang, draft=False):
    def safe(s):  # footer text is interpolated into a CSS content:"…" inside @page{…}; neutralise the
        return s.replace('"', "'").replace("{", "").replace("}", "")  # 3 chars that could break out
    f = FOOTER.get(lang, FOOTER["en"])
    left = (f["prep"].format(d=date_str) + " · " + f["attr"]) if date_str else f["attr"]
    left = safe(left)
    right_id = (safe(hid) + " · ") if hid else ""
    # a margin box sits outside the content flow, so a draft paginates exactly like its seal
    top = (f'@top-center{{ content:"{safe(draft_mark(lang))}"; font:600 8pt "Handout Sans",sans-serif; '
           'color:#555555; }' if draft else "")
    return ("@page{"
            f'@bottom-left{{ content:"{left}"; font:7pt "Handout Sans",sans-serif; color:#555555; }}'
            f'@bottom-right{{ content:"{right_id}" {f["page"]}; font:7pt "Handout Sans",sans-serif; color:#555555; }}'
            f"{top}}}")


def draft_mark(lang):
    return FOOTER.get(lang, FOOTER["en"])["draft"]


def covered_codepoints():
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    cps = set()
    for fn in ("handout-sans-400.woff2", "handout-sans-600.woff2",
               "spectral-500.woff2", "spectral-600.woff2"):  # every weight the CSS actually renders
        p = os.path.join(FONTS, fn)
        if os.path.isfile(p):
            t = TTFont(p); cps |= set(t.getBestCmap().keys()); t.close()
    return cps or None


def pdf_text(path):
    """The PDF's text, pages separated by a form feed (pdftotext's own separator)."""
    try:
        return subprocess.run(["pdftotext", "-layout", path, "-"],
                              capture_output=True, text=True, timeout=30).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        try:
            from pypdf import PdfReader
            return "\f".join(p.extract_text() or "" for p in PdfReader(path).pages)
        except Exception:
            return ""


def page_is_white(path):
    """Rasterise page 1 (low-DPI grayscale via pdftoppm) and check the top margin is white — a
    regression guard on the paper-first white page (ADR-0032). Returns True/False, or None to skip
    when the rasteriser is unavailable (don't false-fail)."""
    try:
        out = subprocess.run(["pdftoppm", "-gray", "-r", "36", "-f", "1", "-l", "1", path],
                             capture_output=True, timeout=30).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if not out.startswith(b"P5"):
        return None
    try:
        parts = out.split(None, 4)
        w = int(parts[1]); px = parts[4]
    except (ValueError, IndexError):
        return None
    vals = [px[r * w + c] for r in range(3, 9) for c in range(0, w, max(1, w // 40))
            if r * w + c < len(px)]
    return (sum(vals) / len(vals) >= 250) if vals else None


def _squeezed(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def build_qa(source_text, html, pdf_path, values=(), mark=None):
    """Return a list of human-readable QA failures (empty = clean). `values` are a kept-details
    seal's filled-in values: B7 ignores them (a surname may read like a marker), B4 names them as the
    likely cause, and B9 requires each to reach the PDF intact. `mark` is a draft's draft line, which
    B10 requires on every page."""
    fails = []
    body = re.sub(r"(?s)^.*?\n\n", "", source_text, count=0)  # keep full text for scans
    # B1 — a markdown pipe-table must become a real <table>
    if re.search(r"(?m)^\s*\|.*\|\s*$", source_text) and "<table" not in html:
        fails.append("B1: a table did not render as <table>")
    # B2 — the REFERENCES section itself must render as a real <ol>. Scope it: the clinician template
    # also has a numbered Rekomendacje list, so a plain "<ol> anywhere?" test would miss a collapsed
    # Piśmiennictwo — the exact ADR-0026 incident.
    if re.search(r"(?im)^#+\s*(piśmiennictwo|bibliografia|references)\b", source_text):
        hm = re.search(r"<h[1-3][^>]*>\s*(?:piśmiennictwo|bibliografia|references)\b.*?</h[1-3]>",
                       html, re.I | re.S)
        sect = html[hm.end():] if hm else ""
        nxt = re.search(r"<h[1-3][^>]*>", sect)
        sect = sect[:nxt.start()] if nxt else sect
        if "<ol" not in sect:
            fails.append("B2: the references section did not render as a numbered <ol>")
    # B3 — attr_list markers must be consumed, never printed
    if re.search(r"\{:\s*\.", html):
        fails.append("B3: a literal attr_list marker ({: .…}) leaked into the document")
    # B8 — a list written with NO blank line above it does not start a list in the pinned
    # python-markdown (3.10.2) whenever another block precedes it (a title/heading always does in a
    # real handout): the marker lines render as literal text INSIDE the preceding <p> — a run-in
    # "list", the re-seal failure this check exists for. It is MARKER-AGNOSTIC: "-", "*", "+" and ordered
    # "1." all run in equally (confirmed end-to-end 2026-07-20 — the trigger is the missing blank line
    # after a preceding block, NOT the bullet character; a first-block list is the only case that
    # self-recognises, and real handouts never open with a bare list). em-/en-dashes ("—"/"–",
    # U+2014/2013) are not ASCII "- ", and a range like "5 - 10" has no marker+space at a line start,
    # so both are excluded. Signature: a list marker on a non-first line inside a rendered <p>.
    # Authoring fault (halt, no fallback — the fix is one blank line): joins B0/B7 in content_bug.
    for _pm in re.finditer(r"(?s)<p\b[^>]*>(.*?)</p>", html):
        if re.search(r"\n[ \t]*(?:[-*+]|\d+\.)[ \t]", _pm.group(1)):
            fails.append("B8: a list ran into the paragraph above it (no blank line) — add a blank "
                         "line before the list so it renders as a list, not a run-in paragraph")
            break
    txt = pdf_text(pdf_path)
    if "{:" in txt:
        fails.append("B3: a literal attr_list marker leaked into the PDF text")
    # B6 — page number present in the rendered footer
    if not re.search(r"(?:str\.|\bp\.)\s*\d+\s*/\s*\d+", txt):
        fails.append("B6: page number ('str. X / Y') not found in the rendered PDF")
    # B10 — every page of a draft carries the draft line: the draft skipped the fact-check, and a page-style
    # override in the source (a raw <style> with @page) can blank the margin box that prints it
    if mark:
        pages = txt.split("\f")
        if pages and not pages[-1].strip():
            pages.pop()                 # pdftotext ends the last page with a form feed too
        if not pages or any(_squeezed(mark) not in _squeezed(pg) for pg in pages):
            fails.append("B10: a draft page is missing its draft line — remove any page-style override "
                         "(a <style> block with @page) from the source")
    # B7 — no draft or private-data marker in the reader-facing PDF (halts); style words only warn (a
    # filled-in value is not authored text)
    jt = txt
    for v in values:
        jt = jt.replace(v, " ")
    if LEAK.search(jt):
        fails.append("B7: draft or private-data marker leaked into the PDF (matched text withheld)")
    for name in style_words(jt):
        print("WARN: style word in the PDF text: %s — reword it if the reader would not know it; "
              "rendering continues" % name, file=sys.stderr)
    # B4 — every glyph used is covered by a bundled font (else it may tofu on another host).
    # CAVEAT (2026-07-06 red-team): this scans the markdown SOURCE (`body`), not the rendered text — safe
    # while the enabled extensions (tables/sane_lists/attr_list/meta) synthesise no new characters. If a
    # typography extension (e.g. `smarty` for curly quotes) is ever added, switch this to scan pdf_text()
    # so a render-introduced glyph cannot slip past uncovered. Below U+02C0 it trusts the fonts: the bite
    # suite checks that each print font covers printable ASCII, Latin-1 and Latin Extended-A (less the soft
    # hyphen and ŉ); U+0180–U+02BF goes unchecked.
    cps = covered_codepoints()
    if cps is not None:
        used = {ch for ch in body if ord(ch) > 0x2BF and ch not in ALLOW_FALLBACK and not ch.isspace()}
        missing = sorted(ch for ch in used if ord(ch) not in cps)
        if missing:
            fails.append("B4: glyph(s) not in the bundled fonts (values withheld; may tofu)"
                         + ("; a filled-in value uses them — tell the operator, the source cannot fix it"
                            if any(ch in v for v in values for ch in missing) else ""))
    # B9 — a seal with kept details: every filled-in value reaches the PDF intact (a placeholder inside a
    # link, an autolink, code or at a list marker's place can mangle or drop it)
    if values and any(_squeezed(v) not in _squeezed(txt) for v in values):
        fails.append("B9: a filled-in value did not reach the PDF intact (value withheld) — write the "
                     "placeholder in plain text, not in a link, code or list marker")
    # B5 — the printed page background must be white (paper-first; no @media-screen fill reached print)
    if page_is_white(pdf_path) is False:
        fails.append("B5: the page background is not white (a fill reached the print layer)")
    return fails


def plaintext_fallback(source_text, out_txt, mark=None):
    t = re.sub(r"\A(?:[^\n:]+:[^\n]*\n)+\n", "", source_text)   # strip the leading front-matter block
    t = re.sub(r"(?m)^\{:.*$", "", t)          # drop attr_list marker lines
    t = re.sub(r"\{:\s*[^}]*\}", "", t)         # inline markers
    t = re.sub(r"(?m)^>\s?", "", t)             # blockquote markers
    if mark:                                    # a draft's fallback opens with the draft line
        t = mark + "\n\n" + t.strip()
    tmp = out_txt + ".tmp"                      # atomic like every other promoted artifact (ADR-0039)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(t.strip() + "\n")
    os.replace(tmp, out_txt)


# ---- sealing helpers (ADR-0039) -------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def factcheck_gate(md_path, md_sha, person_dir=None):
    """Enforce the canonical order author → fact-check → render (ADR-0039 §3): the ADR-0034
    sidecar must exist, parse, match the Markdown's CURRENT bytes, read PASS with zero open
    MUST-FIX. Returns the sidecar bytes' SHA-256 (for attestation binding) or exits 4 — the render
    never seals unverified content. Since guard L11 retired (ADR-0034 point 3) this gate is
    the only reader of the field contract, and the one fact-check lock. The sidecar
    is read ONCE: the hash attested is the hash of the exact bytes parsed (red-team 2026-07-17).

    A five-line control block also records the profile.md and medications.md digests the verifier
    checked (ADR-0070): both files in `person_dir` are re-hashed here and must match, so the record
    matched when the gate ran. A three-line block (verified before ADR-0070, or by a verifier that
    left the lines out) binds the handout alone."""
    side = os.path.splitext(md_path)[0] + ".factcheck.md"
    try:
        side_mode = os.lstat(side).st_mode
    except OSError:
        _gate_fail("no fact-check sidecar beside this handout — run the independent verifier first "
                   "(locator withheld; ADR-0034), or use --draft for an unsealed eyeball copy")
    if not stat.S_ISREG(side_mode):
        _gate_fail("fact-check sidecar is symlinked or non-regular "
                   "(locator withheld; fail closed)")
    try:
        with open(side, "rb") as f:
            raw = f.read()
    except OSError:
        _gate_fail("fact-check sidecar could not be read (locator withheld; fail closed)")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        _gate_fail("fact-check sidecar is not valid UTF-8 (locator withheld)")
    if len(lines) >= 4 and lines[3] == "":
        n_controls = 3
    elif len(lines) >= 6 and lines[5] == "":
        n_controls = 5
    else:
        _gate_fail("fact-check sidecar must begin with the exact three- or five-line control block "
                   "followed by a blank line (locator withheld)")
    patterns = (
        ("handout_sha256", r"handout_sha256: ([0-9a-f]{64})"),
        ("verdict", r"verdict: (PASS|FAIL)"),
        ("must_fix_open", r"must_fix_open: ([0-9]+)"),
        ("profile_sha256", r"profile_sha256: ([0-9a-f]{64})"),
        ("medications_sha256", r"medications_sha256: ([0-9a-f]{64})"),
    )
    fields = {}
    for index, (key, pattern) in enumerate(patterns[:n_controls]):
        m = re.fullmatch(pattern, lines[index])
        if not m:
            _gate_fail(f"fact-check sidecar has malformed {key} control syntax (locator withheld)")
        fields[key] = m.group(1)
    counts = {
        key: sum(1 for line in lines if re.match(r"^" + re.escape(key) + r":", line))
        for key, _pattern in patterns
    }
    # Every reserved key is counted across the whole sidecar: once each in the block it belongs to,
    # and a record key absent from a three-line one — a misplaced record line is never ignored.
    if any(counts[key] != (1 if index < n_controls else 0)
           for index, (key, _pattern) in enumerate(patterns)):
        _gate_fail("fact-check sidecar repeats or misplaces a control field — conflicting/ambiguous "
                   "verification record (locator withheld)")
    if fields["handout_sha256"] != md_sha:
        _gate_fail("sidecar is STALE (the Markdown changed since verification) — re-run the verifier")
    if fields["verdict"] != "PASS":
        _gate_fail("fact-check verdict is not PASS (value withheld)")
    if fields["must_fix_open"] != "0":
        _gate_fail("fact-check has open MUST-FIX findings (count withheld)")
    if n_controls == 5:
        if person_dir is None:
            _gate_fail("the person's record cannot be located to check the sidecar's record digests "
                       "(fail closed)")
        for key, name in (("profile_sha256", "profile.md"), ("medications_sha256", "medications.md")):
            path = os.path.join(person_dir, name)
            try:
                if not stat.S_ISREG(os.lstat(path).st_mode):
                    raise OSError
                current = sha256_file(path)
            except OSError:
                _gate_fail(f"the person's {name} is missing, not a regular file or unreadable "
                           "(locator withheld; fail closed)")
            if fields[key] != current:
                _gate_fail("profile.md or medications.md changed since verification — run a later "
                           "verify round, then seal")
    return hashlib.sha256(raw).hexdigest()


def _gate_fail(msg):
    print(f"FACT-CHECK GATE REFUSED: {msg}", file=sys.stderr)
    sys.exit(4)


def write_attest(out_path, md_path, md_sha, factcheck_sha, output_kind, output_sha,
                 audience, lang, hid, build_qa, person, encounter):
    """Write <stem>.attest.json atomically (temp + os.replace), LAST in the promote sequence —
    attestation present ⇒ deliverable valid (ADR-0039 §4/§5). Basenames only, no paths; person +
    encounter bind the unit to its patient tree and dated dir (portable units are red-team RED)."""
    attest_path = os.path.splitext(md_path)[0] + ".attest.json"
    doc = {
        "schema": ATTEST_SCHEMA,
        "tool": TOOL_VERSION,
        "md_file": os.path.basename(md_path),
        "md_sha256": md_sha,
        "factcheck_sha256": factcheck_sha,
        "output_kind": output_kind,
        "output_file": os.path.basename(out_path),
        "output_sha256": output_sha,
        "audience": audience,
        "lang": lang,
        "id": hid,
        "person": person,
        "encounter": encounter,
        "build_qa": build_qa,
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
                             .isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    tmp = attest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, attest_path)
    return attest_path


def preflight_artifact_paths(in_path, out_path, draft):
    """Refuse static redirections/clobber traps before any renderer write.

    Existing live PDF/TXT files may be superseded only when they are ordinary regular files.
    Reserved sibling staging names must be absent: opening a planted `.tmp` symlink would otherwise
    write outside the encounter before the later atomic replace. This closes accidental/static
    namespace hazards; a hostile same-user swap after preflight remains outside this minimal control.
    """
    fallback = os.path.splitext(out_path)[0] + ".txt"
    if draft and (os.path.lexists(out_path) or os.path.lexists(fallback)):
        _refuse("draft output already exists; drafts never replace any deliverable "
                "(locator withheld)")
    for live in (out_path, fallback):
        if not os.path.lexists(live):
            continue
        try:
            mode = os.lstat(live).st_mode
        except OSError:
            _refuse("an output sibling cannot be inspected (locator withheld; fail closed)")
        if not stat.S_ISREG(mode):
            _refuse("an output sibling is symlinked or non-regular "
                    "(locator withheld; fail closed)")
    reserved = [out_path + ".tmp", fallback + ".tmp"]
    if not draft:
        reserved.append(os.path.splitext(in_path)[0] + ".attest.json.tmp")
    if any(os.path.lexists(path) for path in reserved):
        _refuse("a reserved renderer staging path already exists "
                "(locator withheld; remove/adjudicate it first)")


def preflight_preview_path(in_path, preview_path):
    """A preview is a new local copy, outside the sealed handout lane (ADR-0058)."""
    target = os.path.realpath(preview_path)
    if not preview_path.lower().endswith(".html") or os.path.lexists(preview_path):
        _refuse("HTML preview needs a new .html path; existing copies are never overwritten")
    if not os.path.isdir(os.path.dirname(target)):
        _refuse("HTML preview parent directory does not exist (locator withheld)")
    if "/med/handouts/" in target.replace(os.sep, "/"):
        _refuse("HTML previews belong outside med/handouts; sealed units accept no HTML artifact")
    # A preview of an actual patient source remains in that person's record area, even when the
    # requested destination traverses a link. Synthetic draft fixtures outside patients are portable.
    source = os.path.realpath(in_path)
    patient_root = os.path.realpath(os.path.join(REPO_ROOT, "patients"))
    if os.path.commonpath((source, patient_root)) == patient_root:
        handle = os.path.relpath(source, patient_root).split(os.sep)[0]
        owner = os.path.join(patient_root, handle)
        if os.path.commonpath((target, owner)) != owner:
            _refuse("HTML preview must stay inside the source person's record directory "
                    "(locator withheld)")
    elif re.search(r"/patients/[^/]+/", source.replace(os.sep, "/")):
        _refuse("HTML preview of an external patient source must use that checkout's renderer "
                "(locator withheld)")


class PreviewMarkup(HTMLParser):
    """Handout prose only: a browser must not activate markup the PDF treats as inert text."""
    TAGS = set("a abbr b blockquote br caption code col colgroup dd del div dl dt em h1 h2 h3 h4 "
               "h5 h6 hr i li ol p pre s small span strong sub sup table tbody td th thead tfoot "
               "tr u ul".split())
    ATTRS = set("class id title lang dir colspan rowspan scope headers span start reversed value href".split())

    def feed(self, data):
        # This is one complete Markdown-converted fragment, not a streaming parser. A buffered
        # unfinished declaration/tag can otherwise become active when browser chrome follows it.
        super().feed(data)
        if self.rawdata:
            _refuse("HTML preview requires complete markup; unfinished declarations/tags are unsupported")

    def unknown_decl(self, data):
        # CDATA is not inert in an HTML browser: its closing '>' can expose markup that this
        # stdlib parser treated as declaration data. Reject rather than interpret it a second way.
        _refuse("HTML preview does not support declarations or CDATA in the document body")

    handle_decl = unknown_decl
    handle_pi = unknown_decl

    def handle_comment(self, data):
        if data.startswith((">", "->")):
            _refuse("HTML preview does not support malformed HTML comments")

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            _refuse("HTML preview supports text, lists and tables; embedded media or active "
                    "HTML is not supported (source unchanged)")
        for name, value in attrs:
            # python-markdown's tables extension emits this one style for aligned columns.
            if name == "style" and tag in ("th", "td") and re.fullmatch(
                    r"text-align: (left|center|right);", value or ""):
                continue
            if name not in self.ATTRS:
                _refuse("HTML preview supports only prose, table and citation-link attributes")
            if name == "href" and value and not value.startswith("#"):
                if urlsplit(value).scheme.lower() not in ("https", "http", "mailto"):
                    _refuse("HTML preview links must be explicit web/email links or page anchors")


def embedded_preview_css():
    """The preview's design-system stylesheet with its bundled fonts inlined, for the HTML only.

    The PDF never uses this: it is rendered from handout.css exactly as without --preview-html, so the
    optional reading copy cannot change the document it previews (asserted by the parity test).
    """
    with open(PREVIEW_CSS_PATH, encoding="utf-8") as f:
        css = f.read()

    def embed(match):
        rel = match.group(2)
        if not re.fullmatch(r"fonts/[a-z0-9-]+\.woff2?", rel):
            _refuse("HTML preview stylesheet contains an unsupported resource reference")
        with open(os.path.join(HERE, rel), "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        kind = "woff2" if rel.endswith("woff2") else "woff"
        return "url('data:font/%s;base64,%s')" % (kind, encoded)

    if re.search(r"@import\b", css, re.I):
        _refuse("HTML preview stylesheet must use bundled assets only")
    return re.sub(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)", embed, css)


def preview_document(body, title, audience, lang, css, pdf_bytes, pdf_name, draft):
    """The download is the exact QA'd PDF, embedded so this saved copy stays self-contained."""
    pl = lang == "pl"
    # a draft's status line is the PDF's draft line, and it stays on paper when the preview is printed
    status = draft_mark("pl" if pl else "en") if draft else ("Zapisana kopia" if pl else "Saved copy")
    status_class = "preview-status preview-draft" if draft else "preview-status"
    label = "Pobierz PDF" if pl else "Download PDF"   # the status line above already says "draft"
    note = ("Podgląd i PDF zawierają tę samą wersję dokumentu. Późniejsze zmiany wymagają nowej kopii."
            if pl else "This preview and PDF contain the same version. Later edits need a new copy.")
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    policy = "default-src 'none'; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'"
    return (f'<!DOCTYPE html><html lang="{"pl" if pl else "en"}"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{policy}">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{css}</style></head>'
            f'<body class="audience-{audience or "patient"}"><p class="{status_class}">{status}</p>'
            f'{body}<aside class="preview-actions"><a class="preview-download" '
            f'href="data:application/pdf;base64,{encoded}" download="{html.escape(pdf_name, quote=True)}">'
            f'{label}</a><p>{note}</p></aside></body></html>')


def write_preview(path, document):
    """Publish a private, complete new copy; never replace an older preview or a sealed artifact."""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                         dir=os.path.dirname(os.path.abspath(path)),
                                         prefix=".handout-preview-") as f:
            tmp = f.name
            f.write(document)
        os.link(tmp, path)  # atomic publication; unlike replace(), refuses an existing destination
    except OSError:
        print("PREVIEW FAILED: the PDF was created, but its HTML preview could not be saved. "
              "The PDF remains intact; do not re-seal an existing unit.", file=sys.stderr)
        sys.exit(5)
    finally:
        if tmp is not None:
            os.unlink(tmp)
    print("HTML preview saved (local copy; includes the matching PDF; locator withheld)")


def render(in_path, out_path, audience, allow_fallback=True, draft=False,
           person=None, encounter=None, preview_html=None):
    if preview_html:
        preflight_preview_path(in_path, preview_html)
    try:
        import markdown
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError as e:
        sys.exit(f"missing dependency: {e.name}. Install: pip install -r requirements-render.txt "
                 "(pinned sibling file, ADR-0039)")

    # read the source ONCE and derive everything — render, gate comparison, attested md_sha256 —
    # from the same bytes. A second read opened a TOCTOU window where the seal bound hash(new bytes)
    # to render(old bytes): an internally consistent wrong seal L15 could never catch (red-team
    # 2026-07-17).
    try:
        with open(in_path, "rb") as f:
            data = f.read()
    except OSError:
        _refuse("input handout could not be read (locator withheld; fail closed)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("input handout is not valid UTF-8 (locator withheld)")

    subs = kept_details_substitutions(in_path, text, draft)
    if subs is not None:
        if preview_html and not draft:
            _refuse("a seal for a person with kept details takes no HTML preview: it would carry their details "
                    "outside the read guard; preview the draft instead")
        allow_fallback = False            # a plaintext copy would carry them outside every check
        text = fill_placeholders(text, subs)

    md = markdown.Markdown(extensions=["tables", "sane_lists", "attr_list", "meta"])
    body = md.convert(text)
    meta = {k: (v[0] if v else "") for k, v in getattr(md, "Meta", {}).items()}
    hid = meta.get("id", "").strip()
    assert_filename_id_matches_metadata(in_path, hid)
    assert_front_matter_id_valid(hid)

    # ---- fact-check gate (ADR-0039 §3): sealing renders only verified content ----
    # The two ID checks above are deliberately first: they are source-shape errors, so neither draft
    # nor seal should spend a fact-check gate or start rendering before they red.
    md_sha = factcheck_sha = None
    if not draft:
        md_sha = hashlib.sha256(data).hexdigest()
        factcheck_sha = factcheck_gate(
            in_path, md_sha, os.path.join(REPO_ROOT, "patients", person) if person else None)

    lang = (meta.get("lang", "") or "en").strip().lower()
    if lang not in FOOTER:
        print("WARNING: unsupported language metadata; footer chrome uses English "
              "(value withheld).", file=sys.stderr)
    try:
        date_str = fmt_date(meta.get("date", ""))
    except ValueError:  # an authoring fault like B0: halt before anything is written, no fallback
        print("BUILD-QA FAILED:", file=sys.stderr)
        print("  - B0: front-matter date is not a real YYYY-MM-DD date (value withheld) — fix the "
              "source.", file=sys.stderr)
        print("→ CONTENT problem — halting; fix the source. No fallback written.", file=sys.stderr)
        sys.exit(3)

    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else "Handout"
    if draft:
        title = draft_mark(lang) + " · " + title   # the PDF's title metadata says draft too
    cls = f' class="audience-{audience}"' if audience else ""
    doc = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>'
           f"<style>{footer_css(hid, date_str, lang, draft)}</style></head><body{cls}>\n{body}\n</body></html>")
    preview_css = None
    if preview_html:
        PreviewMarkup().feed(body)
        preview_css = embedded_preview_css()

    # ---- crash-safe render (ADR-0039 §5): sibling temp in the SAME directory (same filesystem,
    # so the promoting os.replace is an atomic rename), QA against the temp, promote only on PASS.
    # A prior good deliverable at out_path is never touched until the new render verifies clean.
    tmp_path = out_path + ".tmp"
    font_config = FontConfiguration()
    wlog = logging.getLogger("weasyprint")
    buf = io.StringIO(); handler = logging.StreamHandler(buf)
    wlog.addHandler(handler); prev = wlog.level; wlog.setLevel(logging.WARNING)
    try:
        fetcher = bundled_only_fetcher()
        HTML(string=doc, base_url=os.path.dirname(os.path.abspath(in_path)), url_fetcher=fetcher).write_pdf(
            tmp_path, stylesheets=[CSS(filename=CSS_PATH, font_config=font_config, url_fetcher=fetcher)],
            font_config=font_config)
    except BaseException as e:            # the engine's fatal fetch error is a BaseException
        if type(e).__name__ != "FatalURLFetchingError":
            raise
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        _refuse("the source refers to a resource outside the bundled assets (a remote or local file); "
                "a handout embeds nothing and fetches nothing — remove the reference (locator withheld)")
    finally:
        wlog.removeHandler(handler); wlog.setLevel(prev)
    warns = buf.getvalue().strip()
    if warns:
        print("WARNING: rendering engine emitted warning(s); raw details withheld because they "
              "may contain private locators.", file=sys.stderr)
    if "ignored" in warns.lower() and "src" in warns.lower():
        print("WARNING: an @font-face failed to load — check handout.css / fonts.", file=sys.stderr)

    fails = build_qa(text, body, tmp_path, values=tuple(subs.values()) if subs is not None and not draft else (),
                     mark=draft_mark(lang) if draft else None)
    if not (meta and meta.get("id") and meta.get("date")):
        fails.insert(0, "B0: front-matter id/date missing or not parsed — put it at the very TOP of the "
                        "file (above any comment block).")
    if fails:
        print("BUILD-QA FAILED:", file=sys.stderr)
        for f in fails:
            print("  - " + f, file=sys.stderr)
        # The suspect render only ever existed at tmp_path — remove it; the previously-promoted
        # deliverable (if any) is untouched, which is exactly the crash-safe promise: a failed
        # re-render can no longer destroy the last good artifact. (If the Markdown changed, that
        # prior artifact is already loud-red via L15's stale md_sha256 — never silently green.)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        # B0 (front-matter), B7 (leaked marker) and B8 (run-in list) are CONTENT/authoring
        # faults — the source is what's wrong, so halt and fix it (a plaintext copy would carry B0/B7
        # verbatim, and B8's one-blank-line fix yields the intended styled PDF, not a degraded .txt).
        # Everything else is a RENDER fault where a plain-but-correct fallback is the safe remedy (ADR-0034).
        content_bug = any(f[:2] in ("B0", "B7", "B8", "B9") for f in fails)
        if content_bug:
            print("→ CONTENT problem — halting; fix the source. No fallback written.", file=sys.stderr)
        elif allow_fallback:
            txt = os.path.splitext(out_path)[0] + ".txt"
            plaintext_fallback(text, txt, draft_mark(lang) if draft else None)
            if draft:
                # a draft NEVER touches live deliverables: out_path is <stem>.draft.pdf (which the
                # failed render only ever wrote as a now-removed temp) and the canonical PDF stays.
                print("→ RENDER problem — wrote sibling plain-but-correct fallback "
                      "(draft, unsealed; locator withheld).",
                      file=sys.stderr)
            else:
                # The fallback DELIBERATELY supersedes any stale PDF at the live name (ADR-0034:
                # never hand over a suspect/stale PDF; the .txt is now THE deliverable at this stem)
                # and is attested as such (ADR-0039 §4): kind=txt, build_qa=FALLBACK — bound to the
                # same fact-checked source, so L15 can verify the fallback exactly like a PDF.
                try:
                    os.remove(out_path)
                except OSError:
                    pass
                write_attest(txt, in_path, md_sha, factcheck_sha, "txt", sha256_file(txt),
                             audience, lang, hid, "FALLBACK", person, encounter)
                print("→ RENDER problem — wrote sibling plain-but-correct fallback "
                      "(sealed, attested; locator withheld); "
                      "do NOT hand over any PDF.", file=sys.stderr)
        sys.exit(3)

    # ---- QA PASS: promote atomically, retire a stale fallback, attest LAST (ADR-0039 §4/§5) ----
    preview = None
    if preview_html:
        with open(tmp_path, "rb") as f:
            preview = preview_document(body, title, audience, lang, preview_css, f.read(),
                                       os.path.basename(out_path), draft)
    output_sha = sha256_file(tmp_path)
    os.replace(tmp_path, out_path)
    if draft:
        print("render complete (build-QA clean; DRAFT — not sealed, no attestation; "
              "locator/id withheld)")
        if preview_html:
            write_preview(preview_html, preview)
        return
    stale_txt = os.path.splitext(out_path)[0] + ".txt"
    if os.path.isfile(stale_txt):
        # a PDF and a TXT at one stem is a conflicting-deliverable state (L15 red) — the fresh,
        # QA-clean PDF supersedes the old fallback. Seal path only: a draft sweeps nothing.
        try:
            os.remove(stale_txt)
        except OSError:
            pass
    write_attest(out_path, in_path, md_sha, factcheck_sha, "pdf", output_sha,
                 audience, lang, hid, "PASS", person, encounter)
    print("render complete (build-QA clean; sealed + attested; locator/id withheld)")
    if subs is not None:
        print("kept details: the sealed PDF carries the person's details, which no session may read; "
              "look at it yourself before handing it over")
    if preview_html:
        write_preview(preview_html, preview)


def main():
    ap = argparse.ArgumentParser(description="Render a handout .md to a styled, QA'd, sealed PDF.")
    ap.add_argument("input")
    ap.add_argument("--audience", choices=["patient", "clinician"], default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--preview-html", metavar="NEW.html", default=None,
                    help="also save a local styled preview with the exact generated PDF download; "
                         "new path outside med/handouts, inside the person's directory for patient sources")
    ap.add_argument("--no-fallback", action="store_true", help="fail hard instead of writing a .txt fallback")
    ap.add_argument("--draft", action="store_true",
                    help="unsealed eyeball copy to <stem>.draft.pdf: skip the fact-check gate, write "
                         "no attestation, never touch live deliverables (keep drafts OUT of sealed "
                         "encounter dirs — L15 reds a draft artifact inside one)")
    a = ap.parse_args()
    if not os.path.isfile(a.input):
        _refuse("input is absent or not a regular file (locator withheld)")
    token = infer_audience(os.path.basename(a.input))
    if a.audience and token and a.audience != token:
        _refuse("--audience contradicts the filename's audience token (values withheld) — "
                "the flag never silently wins")
    audience = a.audience or token
    if not a.draft and audience not in ("patient", "clinician"):
        sys.exit("sealing requires an audience — canonical __handout-<audience>__ filename or "
                 "--audience (or use --draft). [ADR-0039]")
    stem = os.path.splitext(a.input)[0]
    if os.path.lexists(stem + ".attest.json"):
        _refuse("an attestation already exists at this stem (locator withheld) — sealed units are IMMUTABLE "
                "(ADR-0039 §2); supersede with a NEW dated unit (or consciously unseal by removing "
                "the unit's attest + output first)")
    person = encounter = None
    if a.draft:
        out = a.out or (stem + ".draft.pdf")
        expected_leaf = os.path.basename(stem) + ".draft.pdf"
        if os.path.basename(out) != expected_leaf:
            _refuse("draft output must retain the input leaf and use the dedicated "
                    "<stem>.draft.pdf name (locator/value withheld)")
        if a.out and os.path.lexists(os.path.splitext(a.out)[0] + ".attest.json"):
            _refuse("--out targets a SEALED stem — drafts never overwrite sealed deliverables")
    else:
        out = stem + ".pdf"
        if a.out and os.path.abspath(a.out) != os.path.abspath(out):
            _refuse("a seal writes only the canonical sibling <stem>.pdf — for a copy elsewhere "
                    "use --draft")
        person, encounter = seal_location(a.input, audience)
    preflight_artifact_paths(a.input, out, a.draft)
    render(a.input, out, audience, allow_fallback=not a.no_fallback, draft=a.draft,
           person=person, encounter=encounter, preview_html=a.preview_html)


def entrypoint():
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print("RENDER REFUSED: unexpected renderer/filesystem error "
              "(locator and exception detail withheld; fail closed)", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    entrypoint()
