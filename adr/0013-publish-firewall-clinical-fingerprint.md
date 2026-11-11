# ADR-0013 — Publish firewall covers the clinical fingerprint

- **Status:** Accepted by 2026-06-07; superseded in part by ADR-0050 2026-09-06, by
  ADR-0051 2026-09-07, by ADR-0035 2026-11-06 and by ADR-0072 (point 6, the relay scan's classes;
  point 5, case dates) 2026-11-08
- **Date:** not recorded (backfilled 2026-09-29 from its register row; the register was backfilled
  2026-06-07)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

An identity-only firewall would have shipped a re-identifying clinical picture in a published
skeleton: a person's several conditions and medicines together can identify them with no name. A
byte-level review caught it. De-identification is not name-stripping.

## Decision

What holds now: `checks/publish-skeleton.sh` (`ALLOW`, `DENY`, the scans and the one carve-out),
`checks/relay-scan.sh`, `checks/topics/relay-and-export.md`, `checks/RECORD-SET` and `.gitignore`.

1. **The firewall covers the clinical fingerprint, not just identity.** Every would-be-published
   file is genericized: no roster handles, real case dates, condition or drug specifics, or
   case-author citations. Since ADR-0050, `ALLOW` is only the export list, and `.gitignore` mirrors
   `checks/RECORD-SET` (guard L20), not `ALLOW` as first decided (drift, 2026-10-11).

2. **Care utility outranks publishing** (operator, 2026-06-08). Publishing is a secondary, later
   goal. Care-relevant files (the reference library's whitelist, blacklist and index) stay
   publish-safe by staying local and deny-listed; only care-neutral governance and process docs,
   which carry no clinical information, were genericized. **If genericization ever degrades care,
   revert it and deny-list instead.**

3. **Private-ring packaging and one identity carve-out** (operator, 2026-07-04). The operator
   decided to share the skeleton with a first ring, the clinicians who gave feedback, through a
   fresh private repository under preview terms: no licence granted yet (all rights reserved;
   review and personal use, no redistribution), the source-available option still open.
   `NOTICE.md` (purpose, terms, copyright) and `OVERVIEW.md` (gone since ADR-0051) joined `ALLOW`.
   The intended-purpose statement (personal record-keeping and care-coordination methodology for
   informal caregivers; not a medical device; not for diagnosis or treatment decisions) went into
   README, NOTICE and the clinician handout. The identity scan exempts `NOTICE.md` only, for the
   copyright line; every other class still scans it. The trade-off: a deliberately disclosed
   identity can also identify people whose records must stay private. **Re-examine the carve-out at
   the PUBLIC flip**, which changes that identity's exposure and its links to private records.

4. **The carve-out is anchored to the exact path** (2026-07-06; Tier-S, ADR-0031). The first build,
   a basename exclude, would also have exempted any nested `NOTICE.md` and let an identity token
   ride out in it, a latent fail-open a red-team found; only the export root's file is exempt. With
   the site carve-out (point 7) and the render helper's month-array carve-out (ADR-0032,
   2026-09-29) retired, it is the only content carve-out left (drift, 2026-10-11).

5. **Token upkeep is continuous** (2026-07-05), **at the moment of transfer** (2026-10-04). A new
   person's tokens had joined the registry only when noticed, and until then an export relied on
   the deny-list alone, so each handle, date of birth and newly distinctive condition or drug name
   joins it, unless private mode withholds it. Since 2026-10-04 that happens before a
   relay or an export, prompted by `checks/relay-scan.sh` when an ownership ledger is newer than the
   registry, and no longer at intake, which records only what private mode needs, in its own file:
   the registry only matters where a scan reads it. The procedure:
   `checks/topics/relay-and-export.md` → *Keep the registry current*.

6. **The session-time identity guard: deferred, built, then retired.**
   - **Deferred** (2026-07-08). An identity token put back on an `ALLOW` surface had been caught
     only at a publish dry run (cc-prompts/031). An Opus panel judged the publish-time scan the
     terminal backstop while publishing is held, and deferred a session-time net to its first live
     exposure path, an operator request for the PUBLIC flip. Folding identity into guard L9 was
     rejected: the two classes' exemptions differ in shape. Guard L12 (ADR-0036 D3) closed the
     registry-drop half.
   - **Built ahead of its trigger** (operator, 2026-08-09) as guard L18 (ADR-0046),
     with the export scan's exemptions replicated and anchored on the path field.
   - **Retired** with L12 (2026-09-06, ADR-0050 Part B; number not reused). L18 existed because
     product and records shared one tree, and it needed a token list inside it; DEV holds no record
     and no token list, so a scan there could only skip itself. Its premise changed; ADR-0046 was
     not reversed. The fingerprint scan now runs only where records could still cross: the
     flip-time export scan, the terminal backstop, and `checks/relay-scan.sh` in CARE over prose
     bound for DEV, all five classes. A reviewer required this narrowing to be recorded as a
     reversal, not a tidy-up. The cost: a token reaching a shipped file another way is caught at the
     flip, not at the commit.

7. **Site © footer carve-out** (2026-07-31; withdrawn by ADR-0051). With `site/` in `ALLOW`, the
   identity scan exempted the operator's copyright line on generated pages line by line
   (`site/*.html`, only where `© ` shares the hit line), to be re-examined at the PUBLIC flip with
   NOTICE's. It retired with `site/` (`658ebc8`, 2026-09-08).

8. **A care-setting and relationship class** (2026-08-01). A drift sweep found care-setting
   details in shipped files; they were genericized, and `PII_BRAND` gained a class for such words.

9. **The registry lives outside every repository; the export gate is tracked** (2026-09-06,
   recorded 2026-09-07; ADR-0050). This ADR was the only shipping record of points 4, 5, 7 and 8,
   because their fixes and the registry lived in the deny-listed export script. The class lines and
   wrapped-brand pairs moved into one file outside every work tree, named by the untracked
   `checks/FIREWALL-REGISTRY`. The operator edits it by hand, outside any session; a session may say
   what to add, never open it. The export script became tracked, token-free product in its own
   `ALLOW`, so git carries its history. The carve-outs and classes stayed live; only that reason for
   recording them here expired.

10. **The self-reference discipline is permanent** (2026-09-07), though its mechanism is not: never
    write a real handle, date, identifier or condition fingerprint into a tracked file, guard
    comments and ADRs included. A collision is fixed by genericizing the example, never by muzzling
    the class. Point 8 names its class and quotes none of its words.

The 2026-10-11 drift sweep is folded in above.

## Alternatives considered

Each is rejected in the point named, with its reason:

- an identity-only firewall (*Context*);
- genericizing care files for publication (operator, 2026-06-08; point 2);
- a basename exclude for `NOTICE.md` (2026-07-06; point 4);
- folding the identity class into guard L9 (2026-07-08; point 6);
- widening the care-setting atom to its bare stem, and muzzling a colliding class (2026-08-01;
  points 8 and 10).

## Consequences

- What the scans cannot see (a picture retold in fresh words, a token never added) is stated in
  `checks/topics/relay-and-export.md`.
- Verified by the export-gate matrix of `checks/selftest.sh --export` and the relay-scan bites.
