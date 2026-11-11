#!/usr/bin/env bash
# Rebuild the pinned render virtualenv (.venv-render) for render_handout.py from the tracked,
# shipped requirements-render.txt — one command, on macOS OR Linux (ADR-0039 §7 / A2).
#
# The pin (requirements-render.txt) is a full transitive freeze captured on Darwin / Python 3.14.6;
# it reproduces the SAME package versions on Linux (only the compiled wheels differ). weasyprint also
# needs native libraries that pip does NOT install — this script prints the platform's install line
# and fails closed with a clear message if the import check can't pass.
#
# Usage:   _templates/handout-assets/rebuild-render-env.sh [--force]
#   --force   rebuild even if the existing venv already imports cleanly (default: skip = idempotent)
# Env:     VENV_DIR   override the venv path (default <repo>/.venv-render)
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"                       # _templates/handout-assets → repo root
REQ="$HERE/requirements-render.txt"
VENV="${VENV_DIR:-$ROOT/.venv-render}"
PY="${PYTHON:-python3}"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

native_hint() {
  case "$(uname -s)" in
    Linux)  echo "  Debian/Ubuntu:  sudo apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 \\";
            echo "                    libcairo2 libgdk-pixbuf-2.0-0 libffi-dev libglib2.0-0 poppler-utils" ;;
    Darwin) echo "  macOS (brew):   brew install pango cairo gdk-pixbuf glib poppler" ;;
    *)      echo "  (unknown platform — install pango, cairo, gdk-pixbuf, glib, and poppler for your OS)" ;;
  esac
}

verify() { "$1" -c 'import markdown, weasyprint, fontTools, pypdf' >/dev/null 2>&1; }

if [ ! -f "$REQ" ]; then
  echo "FATAL: pin not found: $REQ" >&2; exit 2
fi

# Defense-in-depth for the rm -rf below: refuse to manage a path that doesn't look like a venv, so a
# fat-fingered VENV_DIR (e.g. "/", "$HOME") can never become an rm -rf target.
case "$(basename "$VENV")" in
  *venv*) : ;;
  *) echo "FATAL: refusing to manage '$VENV' — its basename must contain 'venv' (rm -rf safety guard)." >&2
     exit 2 ;;
esac

# Idempotent: a venv that already imports cleanly is left alone unless --force.
if [ "$FORCE" -eq 0 ] && [ -x "$VENV/bin/python" ] && verify "$VENV/bin/python"; then
  echo "render env already good: $VENV  (--force to rebuild)"; exit 0
fi

# Stage-then-swap (the same temp → verify → promote discipline render_handout.py uses for a PDF):
# build into a sibling .new, verify it imports, and replace the live venv ONLY once the new one is
# known good. A failed or offline rebuild then leaves the previously-working venv untouched instead
# of stranding the render pipeline — exactly the constrained moment (ADR-0039 A2) this script is for.
NEW="$VENV.new"
# Any exit before the promote below (set -e included: a venv or pip step that fails offline) removes the
# staged venv, so a failed rebuild leaves nothing untracked behind. After the promote it no longer exists.
trap 'rm -rf "$NEW"' EXIT
echo "rebuilding render env: $VENV"
echo "  pin:    $REQ"
echo "  python: $("$PY" --version 2>&1)"
rm -rf "$NEW"
"$PY" -m venv "$NEW"
"$NEW/bin/pip" install --quiet --upgrade pip
if ! "$NEW/bin/pip" install --quiet -r "$REQ"; then
  echo "FATAL: pip install failed (offline? or the pin's wheels don't match this interpreter)." >&2
  echo "The freeze targets Python 3.14 — a very different interpreter may need a deliberate re-pin." >&2
  echo "The previous $VENV (if any) is untouched." >&2
  rm -rf "$NEW"; exit 3
fi
if ! verify "$NEW/bin/python"; then
  echo "FATAL: packages installed but weasyprint won't import — a native library is missing." >&2
  echo "Install the platform prerequisites, then re-run:" >&2
  native_hint >&2
  echo "The previous $VENV (if any) is untouched." >&2
  rm -rf "$NEW"; exit 4
fi
# Promote: the staged venv is verified good — swap it in for the old one.
rm -rf "$VENV"
mv "$NEW" "$VENV"
echo "OK: $VENV — markdown / weasyprint / fontTools / pypdf import cleanly."
echo "Note: build-QA also needs poppler (pdftotext/pdftoppm) on PATH. If a real render errors on a"
echo "missing native lib (pango/cairo/glib/gdk-pixbuf), install it for your platform:"
native_hint
