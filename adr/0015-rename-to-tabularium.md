# ADR-0015 — Project renamed to `tabularium`

- **Status:** Accepted by 2026-06-09
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Deciders:** not recorded
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

The old name carried a setting-specific hint, and a half-rename (repository renamed, content still
using the old name) would leak it again.

## Decision

What holds now: the export scan's brand class (`checks/topics/relay-and-export.md`, ADR-0013).

The project and repository are renamed `tabularium`: neutral, and it signals records integrity.
Internal brand strings and the repository URL follow, and the publish firewall catches the old name
as a brand-leak token. The local folder may keep the old name until renamed on the host. This record
never prints the old name (the self-reference trap).
