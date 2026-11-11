# tools/claude-skills — the session skills

Four small skills for Claude Code. Each lives here as one `SKILL.md`.

- **`/architect`** opens a build session, where you work on the tool itself rather than on a person's
  records. Only the operator types it; a session never starts one on its own.
- **`/private`** declares a private-mode care session early, for one person whose identifier must
  never reach the AI; a session also takes that posture by itself from the profile marker.
  Experimental; read `tools/private-mode/README.md` first.
- **`/update`** moves a care folder to a newer release with `checks/adopt-release.sh` and reports the
  outcome in plain words; the release notice at session start points to it. Only the operator types it;
  care checkouts only.
- **`guard-admission`** is the admission test before adding or tightening any check, hook or gate.
  Development trees only.

**Install:** run `bash checks/install-instance.sh dev` in a development tree (all but `/update`) or
`bash checks/install-instance.sh care <release-tag>` in a care checkout (`/private` and `/update`;
a care checkout carries no build tools). The installer keeps a copy of each skill in
`.claude/skills/`, refreshed to match this folder byte for byte. Edit the source here, never the
installed copy; the next install overwrites it.
