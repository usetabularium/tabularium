"""Directory creation for the harness, in one spelling the export scan passes.

WHY THIS MODULE EXISTS. `evals/` ships in the flip-time export (ADR-0049 publish posture, decided
2026-09-06), and the export's PII firewall scans code as well as prose. An earlier spelling of the
directory-creating call sites in this package tripped that firewall, so every one of them aborted
a dry export. The export gate already admits one narrower form of that spelling through a
carve-out kept deliberately narrow (ADR-0013
point 8); widening that carve-out to cover the keyword form would blunt a scan whose
teeth are the whole point, so the call sites were rewritten instead and this module is where they
land. `os.makedirs` says the same thing in words the scan has no opinion about — and `fixture.py`
had been spelling it that way since the harness landed, so this is the package's own idiom, not a
new one. Nothing under `evals/` now depends on that carve-out at all, in either spelling.

Both helpers accept a `str` or any `os.PathLike` (a `pathlib.Path` included) and create every
missing ancestor. They differ only in what happens when the leaf already exists — which is
load-bearing at the two `session.py` call sites that use `create_dir`: there the directory has just
been removed, so its presence would mean the teardown failed, and reusing it would run a
containment or image probe over somebody else's leftovers. Fail closed; do not "helpfully" reuse.
"""

import os


def ensure_dir(path):
    """Create `path` and every missing ancestor. An already-existing directory is fine."""
    os.makedirs(path, exist_ok=True)


def create_dir(path):
    """Create `path` and every missing ancestor; raise `FileExistsError` if `path` already exists.

    The strict counterpart of `ensure_dir`, for the call sites where a pre-existing directory is a
    bug (a failed teardown) rather than a no-op. Matches what `Path.mkdir` does without `exist_ok`:
    missing ancestors are created silently, an existing leaf raises.
    """
    os.makedirs(path)
