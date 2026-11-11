# ADR-0048 — L4 closed-world citation membership (half (a) of the citation gap)

- **Status:** Accepted 2026-08-16
- **Date:** 2026-08-16
- **Deciders:** operator (+ assistant; red-teamed by an arbiter the same day)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Two gaps in guard **L4** (citation integrity) were recorded as one issue, kept apart on purpose (the operator's
design note of 2026-08-09):

- **(a) fabrication** — a citation identifier that appears in **no** library entry, never Vetted and
  never even a listed Candidate, passed L4 clean. Invented citations are a known failure mode of the
  system that drafts clinician handouts. This is the higher-stakes half, and it can be closed
  offline as a pure closed-world membership check.
- **(b) rot** — a Vetted link dies or a guideline is superseded. Detecting that needs the network,
  and no guard makes an outbound request. The offline route, a per-entry verified date surfaced
  only for what a *new* handout cites, would be a separate build. (b) does not touch (a): an
  invented identifier has no entry, so it has no date to go stale.

Before this decision L4 extracted every citation id (`PMID`/`DOI`/`PMC`) from each clinical doc
and from the `## Candidates — PENDING VERIFICATION` section of `reference-library/index.md`, and
flagged a doc-cited id that matched a Candidate. An id matching nothing in the library passed.

This ADR builds (a) only. Leg (b) was left open on 2026-08-16. Under the simplification decision of
2026-09-20 it is accepted as a gap that owes no per-entry expiry date and no pre-seal
freshness gate, and since the quarterly library review ended on 2026-10-04, freshness rests on the
handout fact-check.

## Decision

What holds now: the L4 section of `checks/check.sh` (code and comments), the L4 row of
`checks/README.md`, `reference-library/README.md` (*The bar*, *Two-tier verification*) and
`_templates/HANDOUT-RULES.md` (*Citations*); the bites are in `checks/selftest.sh`.

1. **Every cited id must resolve to a Vetted entry** (2026-08-16). `l4_ids()` keeps its extraction
   and canonical form and gains a second reference set, `VETTED`: everything in
   `reference-library/index.md` before the `## Candidates` header, the inverse of `CAND`'s
   boundary. Each id in a clinical doc is checked in this order:
   1. in `VETTED` → passes, even if it also appears in `## Candidates`;
   2. else a listed Candidate → an unverified Candidate citation;
   3. else → it resolves to no Vetted entry: a paper not yet added, or an invented one.

2. **`VETTED` is checked first** (same-day red-team, item 1). `CAND` sweeps every id-shaped token in
   the Candidates text, and a pending bullet may legitimately cross-reference an already-Vetted id
   ("cf. the already-Vetted PMID … above"), as the library's house style does. With `CAND` first
   (the first build), a handout's correct citation of that id was flagged: a live-plausible false
   positive. **Accepted consequence:** an id listed in both sections, say promoted but left in
   Candidates, passes too. The guard cannot tell an incidental mention from a stale duplicate, the
   id is Vetted either way, and `CAND` never adds an id that is not in the text, so this is library
   hygiene, not a fabrication path. A lint on `index.md` for an id in both sections would catch it;
   not built.

3. **Three recognised forms: PMID, DOI, PMC** (2026-08-16), enumerated from the bar and the live
   corpus. The bar requires every entry, a recognised guideline body included, to carry "a working
   DOI or PMID", so there is no identifier-less form to parse; a guideline-body source Vetted by DOI
   alone is the DOI form with an empty PMID slot. PMC is parsed, but no Vetted entry is PMC-keyed,
   so a citation by PMC id alone has no path to membership and warns. No PMC ↔ PMID ↔ DOI
   resolution is attempted (*Alternatives considered*).

4. **A citation-shaped label that never resolves is reported, not dropped** (2026-08-16; reversed
   2026-11-01, point 12), for the shapes this mechanism can see: `PMID: (missing)`, a DOI registrant
   outside the conventional 4–9 digits, a bare `PMC`. Each shape is counted by a loose and a strict
   pattern, and a mismatch warns. Boundaries are explicit ASCII classes, never `\b`, which BSD grep
   misreads next to a multibyte byte in the C locale (these handouts are largely non-English); the
   counts matched under `C` and UTF-8 on the live corpus. A grep exit code of 2 or more is a failed
   scan and warns as its own finding (red-team item 2). Coverage is enumerated, not total:
   *Confirmed residuals*.

5. **A library that cannot vouch is reported when a doc cites something** (2026-08-16). A missing,
   symlinked or non-regular `index.md`, or one yielding no Vetted ids, warns while at least one
   scanned doc cites a well-formed id (the L1/L5 precedent: when what must vouch for a doc is
   blinded, say so). Before, the whole L4 block was gated on `[ -n "$CAND" ]`, so a deleted index
   produced no output at all.
   - **Distrust a symlinked or non-regular index; do not merely warn.** It is never read, so it
     behaves like an absent one. That is stricter than needed, chosen for consistency with L18's
     symlinked-path precedent, not because a laundered pass was otherwise possible.
   - **The gate is driven by content, not doc type:** it counts docs that cite (`L4_CITING`), not
     docs that exist. `profile.md` and `medications.md` stay in the scan, so a stray citation there
     is still checked, and if they ever cite literature the gate adapts unchanged. The first gate
     keyed on doc existence and failed about thirty unrelated bites whose fixtures have no library.
     **Lesson:** run the full suite, not only the new bites, before calling a guard change done.

6. **Asides in a Vetted entry earn no membership** (a finding while building `VETTED`, 2026-08-16).
   One Vetted entry names, in an italic aside, the mis-cited review id it replaces; swept into
   `VETTED`, that id would defeat the check for exactly the wrong-paper class it exists for. The
   Vetted extraction strips `*(...)*` asides first. On the live `index.md` this removed exactly two
   tokens, that id and a PMID in another entry's caveat, and nothing else: every Vetted entry's own
   id sits in **bold**. A heuristic, not a proof of completeness: it closes the one shape found, not
   a caveat formatted otherwise.

7. **Two extraction bugs fixed in `l4_ids()` itself** (2026-08-16), found by running it over the
   Vetted sections for the first time, so the fixes apply to `CAND`, `VETTED` and every doc alike:
   a DOI closed by markdown bold swallowed `.**` and could never match the same DOI in a handout;
   and a DOI with a parenthesised year was cut at its own `)`, so two DOIs of the same year
   collided on one wrong prefix, a real hole for a fabrication check. Both shapes exist only in the
   live corpus, so running there is required validation.

8. **`INDEX.md` and `README.md` under `handouts/` are not scanned** (red-team item 3). They are
   excluded by basename, as in L8: pointer and registry docs, never a citation surface.

9. **A Candidate named only to say it was left out is still flagged** (operator, 2026-09-30). In the
   first plain-vs-Tabularium comparison run (EV-04b, Tabularium arm, trial 1) a session cited the
   Vetted entry correctly and wrote in the change log "Candidate entry PMID 90000002 not cited
   (unverified)". L4's Candidate arm flagged it, as did the eval oracle EV-04b F1. Should a clearly
   declined mention pass? **Decided: no.** The guard matches the id, not the intent, and cannot
   tell "not cited (unverified)" from a hedged real citation ("PMID …, not yet verified"), the
   wrong-paper class it exists for. A negation or section exemption would need the prose
   understanding already rejected, and the grader's negation filter looks only before a match. In a
   care session the board names the id and the session deletes the note: one edit, and nothing is
   lost, since the Candidates list already records the entry as unverified. An eval session never
   sees the board, so the rule is now written where a citing session reads it
   (`reference-library/README.md` and the EV-04 fixture library's header, whose history
   `evals/harness/fixture.py` keeps); F1 covers a listed Candidate as well as an id in no entry; and
   eval controls and selftest bites were added: the declined note flagged in a profile, passing in
   `med/analysis/`.

10. **L4 warns, never reds** (the operator's reduction decision, 2026-10-04). Every finding above —
    a Candidate-only id, an uncatalogued id, a missing, symlinked or empty library, an unreadable
    doc, a parse failure — prints `WARN [L4] …` and leaves the exit code alone; from 2026-08-16 to
    that day each turned the board red. The checks are unchanged, acting on a warning is the
    author's job, and a selftest case pins the warning on a green board.

11. **Two false warnings fixed** (2026-10-25). A DOI closed by an autolink's
    `>`, a backtick or an ASCII quote kept that character and read as uncatalogued; the trailing
    pass now strips them, and the stop-class is unchanged, so a SICI-style DOI stays whole. Decimal
    prose such as `10.5/day` tripped the DOI count; a 1–3-digit registrant now counts only after a
    `DOI` label or the `doi.org` host, which adds residual (e), and a malformed labelled or hosted
    one still warns. Neither change makes quiet text warn. (The count went on 2026-11-01, point 12.)

12. **The parse-failure count removed** (operator decision, 2026-11-01; simplification scan item
    6). The loose-vs-strict count per label (`l4_safe_count`, `l4_shape_check`, the `PMID/DOI`
    legend strip) is gone, and with it the 2026-10-25 residual (e). L4 now reads well-formed ids
    only: each must resolve to a Vetted entry, a Candidate-only id warns, and the index trust gate
    stays. A citation-shaped label with no clean id is the handout fact-check's to catch: it opens
    every citation before a seal. Re-reviewed (operator). The count's one recorded finding was a
    false warning.

### Confirmed residuals

Parse-failure shapes point 4 cannot see, found by measurement and named under red-team item 4, so
that "reported, not dropped" means "for the enumerated shapes". None had occurred at landing.

- **(a) A bare `DOI: pending`**, with no numeral to count against: a residual by measurement, since
  both label-mirror designs false-positived on the live corpus (*Alternatives considered*).
- **(b) A bare PubMed URL** with no label: an authoring slip, since the bibliography template
  mandates the `PMID … · DOI 10.…` form; no URL recogniser was built.
- **(c) A DOI followed directly by a non-ASCII closing character** (`⟩`, `»`, a smart quote)
  includes that character in the extracted id and warns as uncatalogued.
- **(d) A DOI registrant beyond 20 digits**, outside both counts: pathological corruption only.
- **(e) A bare 1–3-digit registrant** with neither label nor host (point 11): retired with the count
  on 2026-11-01 (point 12).

### Admission test (guard-admission)

- **Keeping L4 unchanged for a declined Candidate, 2026-09-30:** (1) harm — an unvetted id in a
  profile or handout, the observed wrong-paper class; (2) not against the operator — it acts only on
  the write into a canonical doc, and the person's `med/analysis/` stays open for the note; (3) at
  the point of harm — the write, through the board and the commit; (4) net positive — one
  self-corrected edit, against a prose exemption that would fail open in clinician handouts;
  (5) smallest form — the existing control.

### Reviews and verification behind the decisions

- **Same-day arbiter red-team, 2026-08-16: ship with fixes, all four items applied.** Item 1:
  `VETTED` first (point 2). Item 2, a rule: capture grep output and save its exit code at once,
  never discarding it through a counting pipeline such as `… 2>/dev/null | wc -l`; call
  `l4_safe_count` as a plain statement, since command substitution would lose its global results;
  an exit code of 2 or more produces a scan-failure finding (`l4_safe_count`, `l4_shape_check`;
  both removed on 2026-11-01, point 12).
  Item 3: the
  `INDEX.md`/`README.md` exclusion (point 8). Item 4: honest wording that names the parse-failure
  residuals and the two rejected label designs.
- **The live-corpus validation run, at landing.** Each new bite was mutation-proven: run against
  the pre-ADR `check.sh` (for the precedence fix, a copy with only the old order restored) and seen
  to fail there. Every live citation (161: 83 PMID-form, 78 DOI-form, none PMC-form) resolved to
  `VETTED` with no false positive and no parse failure, unchanged by the same-day fixes, and the two
  extraction repairs (point 7) lost or changed no other id.

### Other records

- **The 2026-10-11 drift sweep** is folded in: leg (b)'s standing (*Context*), and the "Not yet
  built" note in `checks/README.md` has become its *Deferred controls* pointer to that gap.

## Alternatives considered

- **A bare-label mirror check for residual (a)** (tried twice, rejected on live-corpus measurement,
  red-team item 4; recorded so that a later pass does not retry them). (i) Counting whole-word
  `\bDOI\b`: `doi.org` inside every markdown-link target is itself a bounded `DOI` token, so the
  whole live corpus false-positives. (ii) Stripping `doi.org` first: the bibliography's format
  legend ("Format: … PMID/DOI."), which every live handout then carried, and prose using "DOI"
  descriptively collide the same way. No third design avoided both without prose understanding or
  new false positives.
- **Building (b) alongside (a)** (rejected 2026-08-16, on the operator's design note of
  2026-08-09): the halves differ in mechanism (offline membership against network-dependent
  staleness) and in stakes, and rot detection needs a per-entry dated mark plus a rule to surface
  staleness only for what a new handout cites.
- **Hard-coding each `## Vetted — <topic>` heading as the boundary** (rejected 2026-08-16): a topic
  added without updating a guard-side list would fall outside `VETTED` silently, a fail-open shape.
  The `## Candidates` header alone needs no list and cannot drift.
- **Resolving PMC ↔ PMID ↔ DOI for the same paper** (rejected 2026-08-16): the library records the
  identifiers Tier 1 confirmed on PubMed, today always PMID and/or DOI, and this is a closed-world
  check against that record, not a live resolution service, which would need the network.
- **Generic "citation-shaped prose" detection**, such as bare guideline-body names or "(Smith
  2020)" (rejected 2026-08-16): identifiers appear only in the numbered bibliography, so a prose
  scanner would false-positive on clinical narrative (dates, asides, doses) for a form not in use.
- **Unanchored `10.<digits>` loose DOI scanning** (tried, rejected 2026-08-16): `DD.MM`-style dates
  in lab-tracking prose read as DOI attempts. Requiring the trailing slash, the strict form's own
  shape, removes the collision and still catches a malformed DOI.
- **Whole-board-green bites for "citation resolves" cases** (tried, reverted 2026-08-16): the
  minimal synthetic handout trips unrelated guards, so those bites assert only that L4 stays silent.
- **A negation or section exemption for a declined Candidate** (rejected by the operator,
  2026-09-30; point 9): it would need prose understanding and would fail open in clinician handouts.

## Consequences

- An invented citation in a clinician handout is named before it reaches a reader looking
  legitimate. An id unknown to the library, a listed Candidate and (until 2026-11-01) an unparseable
  citation shape all warn (point 10), where before only the Candidate case was caught.
- `reference-library/index.md`'s prose conventions now carry weight for a safety check: each Vetted
  entry keeps its own id in **bold** and uses italic parentheses only for commentary. An editor who
  puts a real citation inside a `*(...)*` aside drops that id from `VETTED`; it then warns until
  re-added outside the aside, an authoring surprise rather than a safety regression. Worth a mention
  if `HANDOUT-RULES.md` or `reference-library/README.md` is revised.
- L4 does not establish freshness: a dead link or superseded guideline is leg (b).
