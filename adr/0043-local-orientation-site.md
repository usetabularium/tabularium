# ADR-0043 — Local orientation site: the human surface, v1 = orientation ring only

- **Status:** Superseded by ADR-0051 2026-09-07 (accepted 2026-07-30)
- **Date:** 2026-07-27
- **Deciders:** operator (scope and rulings, 2026-07-26 to 2026-07-31) (+ assistant; red-teamed
  2026-07-30)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Humans onboarded through `README.md`, `OVERVIEW.md` and `NOTICE.md` as raw Markdown, and the old
`README.md` → *Getting started* listed agent steps that `CLAUDE.md` already owns and a human cannot
carry out. The operator asked (2026-07-26/27) for a **navigable human surface**: an entry page with
tiles, the notice always visible and, while no person exists yet, a numbered first-run tutorial. A
sibling session had drafted per-person profile views, static HTML projections of `profile.md`; the
operator scoped v1 to orientation only (2026-07-27), to be built aware of what would follow.

## Decision

**Model the surface as three rings and build only ring 1** (2026-07-27): ring 1, orientation (a tile
index, the rendered `OVERVIEW.md`, a quickstart and the notice) in a tracked, record-free, English
`site/`; ring 2, a roster generated into a local-only `patients/index.html`; ring 3, person views
generated into a local-only `patients/<handle>/med/view/`, a medications section in them deferred
furthest.

1. **`site/` is tracked but outside the export allow-list** (2026-07-27), so it stays local;
   promotion was left to a separate, operator-gated registry ceremony.
   - **Promotion executed** (operator, 2026-07-31): `site/` and its builder joined the allow-list.
   - **The ceremony ended with the 2026-09-06 split** (recorded 2026-09-07; ADR-0050). It was
     main-checkout-only because a worktree lacked the then-untracked export script, so its guards
     read green over nothing. With the script tracked and guard L12 retired, an allow-list entry is
     an ordinary reviewed edit in DEV, proved by a dry export.
2. **Deterministic build, committed output, zero egress** (2026-07-27): self-contained `file://`
   pages with no external resources, and no timestamps, so a rebuild-and-diff catches a stale or
   hand-edited page. **`README.md` is not a site source** (operator, 2026-07-28): it stays the
   repository-level equivalent. A generated page is marked by an HTML comment only, with no visible
   line (operator, 2026-07-28).
3. **A full notice page and a compact footer on every page** (operator, 2026-07-28): the footer
   says not a medical device, verify against sources, links the full notice and takes © from
   `NOTICE.md`.
4. **One theme, no fork** (2026-07-27): the handout stylesheet's tokens and fonts (ADR-0032), so
   later person views would read as one system.
5. **No Patients tile in v1** (operator, 2026-07-28): no tile or placeholder until ring 2 makes the
   destination real.
6. **`README.md` → *Getting started* becomes a short pointer to the quickstart** (2026-07-27); agent
   orientation stays in `CLAUDE.md`.
7. **Guard L17, site freshness, as a warning pilot** (2026-07-27): drift warned, to turn red once
   the routine settled; without the render environment the guard skipped loudly, since a skipped
   check must never read as passed. It was minted as L16 and renumbered on merge (2026-07-30)
   because ADR-0044 had taken L16 on main meanwhile: claim a guard number on main, or expect a sweep
   at merge. The red-team hardening (2026-07-30) made a leak class red while
   staleness still warned, after finding that a symlinked source into `patients/` would have
   rendered clinical content into a tracked page on a green board.

### Backlog (deferred by operator decision, 2026-07-27)

Ring 2, ring 3, and teaching the skeleton CI to build the site. The ring 2 and 3 design questions
(roster next-event dates, care-team and source links, the medications section) stayed open by
operator instruction. ADR-0051 point 4 declined rings 2 and 3 as generated files; the CI item went
with `site/`.

### Supersession (2026-09-07)

On the operator's instruction ADR-0051 deleted `site/`, `tools/site/` and `OVERVIEW.md` and retired
L17, its number not reused. ADR-0051 gave the same jobs to the separately maintained public website,
its URLs placeholders until the public flip; a second human surface, a `file://` page only the
maintainer opens, was upkeep with no reader.

## Alternatives considered

- **Un-gitignoring `docs/` to host the site** (rejected 2026-07-27): `docs/` stays local-only
  strategy and roadmap space.
- **Building the roster and person views in v1** (deferred by the operator, 2026-07-27).
- **Keeping agent setup steps in the README** (rejected 2026-07-27): `CLAUDE.md` owns them.

## Consequences

- Committed generated HTML is a drift liability by construction; L17's rebuild-and-diff and the
  generated marker were the mitigation.
- The site added no new PII surface in v1: every input was already shipped or publish-candidate
  English prose, and the builder still scanned its output as a belt.
- Nothing in ring 1 pre-committed rings 2 and 3; the tile and URL space and the theme held their
  place.
