# ADR-0044 — Template-owned blocks: per-patient instruction docs are bound to `_templates/` (guard L16)

- **Status:** Accepted 2026-07-29; guard L16 retired 2026-10-04
- **Date:** 2026-07-29
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Closing a known-issue (KI) row updates the tool and the template. It has not been updating the
**per-patient copies** of the affected doc, and nothing notices.

The demonstrated case: the append-safe ownership writer (ADR-0037 §11) landed 2026-07-19, and
`_templates/person/med/sources/README.md` step 3 was rewritten the same day. All the
`patients/<h>/med/sources/README.md` copies kept the superseded instruction — *"do not file a new
document — park the original in `_inbox/`"*, correct only while no append-safe writer existed. Two
files sat parked for ten days, and the stale step would have re-parked every future source. No
guard was red. Guards check structure, naming, hashes and ownership; **none reads whether a doc
still says the right thing.** The step-3 blocks were re-synced by hand on 2026-07-29.

Auditing the rest of the class the same day found it was the modal state, not a one-off:

- one patient's `med/sources/README.md` had lost **step 0 entirely** — the "is this person
  ⟨never-API⟩ private-mode?" gate (ADR-0029). No live exposure (that person is not private-mode),
  but the question had stopped being asked at intake.
- another patient's `med/sources/CAPTURE-GUIDE.md` **did not exist**, while their
  `sources/README.md` pointed at it.
- All the `med/handouts/INDEX.md` registers still instructed the **delta-by-default** handout
  regime, removed on 2026-07-26 (ADR-0034 point 7) pending an unbuilt baseline-binding
  design. A delta handout can omit material facts; this one is care-material.

Whole-file comparison cannot express the invariant: every copy legitimately diverges.
Person-specific annotations are appended throughout, and one divergence is *required* — the
private-mode patient's step 0 declares private mode ACTIVE per ADR-0029 and must not be flattened
back to the generic text. The dangerous direction is one-way: a copy that **lacks, or holds a stale
version of, text the template owns**. Additions are always fine.

## Decision

Split each template-derived doc into **template-owned blocks** and person-owned prose, and make the
first mechanically enforceable (2026-07-29).

```
template   <!-- t:NAME -->  …block…  <!-- t:/NAME -->        NAME = [a-z0-9][a-z0-9-]*
copy       <!-- t:NAME -->                    body must equal the template's, byte for byte
           <!-- t:NAME override=XXXXXXXX -->  deliberate person-specific divergence, reviewed
                                              against template-body sha256 prefix XXXXXXXX
```

1. **Guard L16 in `check.sh` enforces it:** every anchor the template defines is present in every
   patient copy of that doc; a plain anchor's body is byte-identical; an `override=` anchor's pin
   equals the current template block's digest. **Person-specific prose goes outside the anchors**
   — anything inside them belongs to the template.

2. **An override is a *pinned* divergence, not an exemption:** when the template block changes, the
   pin goes stale and L16 reds, so the person-specific version is re-reviewed against the new text
   rather than frozen.

3. **Presence is demanded per lane** — a template doc is owed by a patient tree wherever its parent
   directory exists, so a person with no `med/handouts/` owes no register, while a person who has
   `med/sources/` owes the capture guide. Scope is opt-in twice over: a template doc with no anchors
   is out of scope (and its copies must then define none), and a tree that ships no
   `_templates/profile.md` owns no person scaffolding at all.

4. **Retired with the copies (2026-10-04); number not reused.** The policy docs under
   `_templates/person/` are now the one shared copy, read from there in every person's session and
   never copied into a person's folder; their anchors and the `override=` pins are removed, and
   guard L16 is retired. The only incident it answered was stale copies, and the copies are gone.
   Care checkouts' existing copies are removed by a separate migration.

## Alternatives considered

- **Whole-file digest stamp** (`<!-- template-sync: <sha256 of the whole template doc> -->` in each
  copy; red when the template file changes). ~25 lines, no anchor plumbing. Rejected as strictly
  weaker on both axes: it reds all copies on a cosmetic template edit, and it can only prove the
  copy was *re-reviewed*, never that the text actually propagated — the operator can re-stamp
  without re-syncing. Anchored blocks prove content for every non-override block.
- **Whole-file diff against the template.** Rejected outright: every copy legitimately diverges, so
  this is red permanently and therefore ignored permanently.
- **Targeted lint for known-superseded phrases** (grep the copies for "park the original in
  `_inbox/`"). Zero false positives, but only ever catches instances already known — it would not
  have found any of the three drifts above. Useful as a complement, not a mechanism.
- **Process only** (extend the KI-closure checklist, no guard). Kept — as the *third* leg, not
  instead of the guard: the checklist is what makes someone re-sync, and L16 is what notices when
  they didn't.

## Consequences

- Editing a template block now reds every patient copy until it is re-synced or re-pinned. That is
  the point, and it is the ongoing maintenance cost: anchor granularity is per section/step
  precisely so a typo fix in step 2 does not force a re-review of an unrelated step-0 override.
- The anchors are visible in a text editor and invisible when rendered. They also document
  ownership at the point of reading: text inside an anchor is not yours to edit in a patient's copy.
- **Limits, stated plainly.** L16 proves the instruction text is **current, not correct** — a wrong
  rule propagated everywhere is uniformly wrong and green. It covers only template-derived docs:
  hand-written analysis notes, `_shared/`, and any lane the template does not own remain
  process-held. Byte comparison ignores trailing blank lines inside a block. And, like
  every guard reading `patients/`, it self-skips in a worktree — the full board must be re-run in
  the main tree.
- Since the retirement (point 4) there are no per-person copies to drift, and no guard checks one.
