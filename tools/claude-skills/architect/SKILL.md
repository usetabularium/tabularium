---
name: architect
description: Open a build session — work on the tool, not on a person's records.
disable-model-invocation: true
---

# Build session

The operator has opened the **build session**: this session is about the tool, not a person.

1. Read `CONTRIBUTING.md` — the building contract — and work under it from here, starting at
   *Opening a build session*.
2. Its workflow begins with the board. If guard L20 does not report a development tree, this
   session cannot open — say so; `CLAUDE.md` → *Sessions and people* says
   what to do instead.

Pointer only — every rule it names lives in `CONTRIBUTING.md`, `CLAUDE.md` and ADR-0053. The copy
under `.claude/skills/` is refreshed byte-identical from `tools/claude-skills/architect/SKILL.md`
by `checks/install-instance.sh`; edit the source, never the copy.
