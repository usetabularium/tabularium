# AGENTS.md — Tabularium (Codex entry surface)

This file is the entry point read by Codex and other `AGENTS.md`-aware agents. It is **not** the
operating contract — it is a thin pointer to it, kept deliberately short so the two can never drift.

## Start with `CLAUDE.md`

`CLAUDE.md` (same directory) is the always-read care contract and routes build sessions to
`CONTRIBUTING.md`, the building contract. The care and safety rules bind both kinds of session.

**Before doing anything in this repo, read `CLAUDE.md` in full and follow it.** Put care and shared
safety rules there; put build workflows, repository machinery and the documentation map in
`CONTRIBUTING.md` and its topic docs under `contributing/`. Do not copy either contract into this entry point — one home for each rule.
