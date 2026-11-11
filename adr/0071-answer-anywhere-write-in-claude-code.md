# ADR-0071 — Outside the main care folder: answer in full, send only the write to Claude Code

- **Status:** Accepted 2026-11-08; supersedes in part ADR-0050 point 17
- **Date:** 2026-11-08
- **Deciders:** operator (+ assistant)

## Context

ADR-0050 point 17 made a session outside Claude Code's main care folder open with a notice and a
ready prompt carrying its session id, so Claude Code could file its answers. The filing tool reads
only Claude Code's local transcripts, so a chat-app id leads nowhere, and that handover is not an
endorsed route.

## Decision

1. Such a session answers and asks as usual, with no first-reply notice (operator, 2026-11-08).
2. It changes, files and copies out no record. When a write is needed, it says so in one sentence and
   gives a ready Claude Code prompt for the main care folder, worktree option off, carrying the
   request.
3. No session-id handover: answers given there are asked again.

The rest of point 17 stands.

## Alternatives considered

- **Keep the handover for worktrees,** where the id works: one more branch for a care session.
- **Keep the first-reply notice:** it gates a session that can answer well.

## Consequences

- A fact stated only outside the main care folder is lost unless repeated.
- No guard holds the rule; the board's and the client's refusals still hold every write.
