# Person template

Scaffold for adding a new person to the system. The pipeline holds the people currently in
care and stays open for more — add a person any time.

## Add a person
Follow `_templates/INTAKE.md` — onboarding one or more people and filing their first documents.

## What each new person gets
Only `profile.md`, `medications.md` and `med/handouts/INDEX.md` are created at scaffold, from the
templates, with empty `med/sources/` and `med/_inbox/` beside them; every other folder is created at
first use. The policy docs in this folder
(`med/sources/README.md` and its `med/sources/topics/` pages, `med/sources/CAPTURE-GUIDE.md`,
`med/_inbox/README.md`) are read from here
in any person's session and are never copied into a person's folder.

- `profile.md` — canonical facts, current status, next steps (+ the opaque Person record ID).
- `medications.md` — prescribed vs. actually taken.
- `med/sources/…` — raw evidence buckets (the filing checklist is `med/sources/README.md` here; bucket
  dirs are created at first filing).
- `med/_inbox/` — the intake tray (created empty at scaffold; its procedure note is `med/_inbox/README.md`
  here).
- `med/MANIFEST` — the ownership ledger (ADR-0037): per-source hash + person-ID + status; append-only;
  local-only (+ untracked `MANIFEST.checkpoint`). Written/refreshed by `tools/person_ownership`.
- `med/analysis/` — reasoning / working notes (created at first use).
- `med/handouts/{patient,clinician}/` — the **products lane** (never evidence; ADR-0039): each
  handout seals into its own `<YYYY-MM-DD>-<slug>/` encounter dir (md + PDF/TXT + factcheck +
  `.attest.json`, immutable — supersede, don't edit; guard L15), registered in `med/handouts/INDEX.md`.
- `nmed/` — their non-medical matters.
