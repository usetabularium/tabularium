# ADR-0035 — License = Apache-2.0

- **Status:** Accepted 2026-07-07
- **Date:** 2026-07-07
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git). **One-off second pass, 2026-11-07 (operator):** the decisions of 2026-10-10 to 2026-10-31,
  held on an unmerged licence branch and so missed by the migration, are folded in, with the rulings
  of 2026-11-01 and 2026-11-06 that attach them. No other ADR takes this exception.
- **Correction, 2026-11-07 (operator):** the patent sentence under Consequences narrowed to match
  Apache §3.

## Context
The published skeleton has had one open licensing question since the licensing notes were written
(2026-07-04, in the private development notes): **Option A — fully permissive (Apache-2.0)** vs
**Option B — source-available (BUSL-1.1 + an Additional Use Grant gating productization)**. The
notes framed a single deciding question — *is the right to charge a future commercial integrator
worth giving up the open-source label and adding adoption friction?* — and deliberately deferred
the answer ("decide at publish time, not before"), because a permissive license is
**irrevocable**: any snapshot shared under it keeps those rights forever and pre-empts Option B.

Two forcing pressures made the question worth *deciding* now (while leaving the *act* for later):
- RELEASE-ROADMAP's v2 line carries an unresolved `[ ] LICENSE decision: Option A vs Option B`,
  and "publishing the marketplace repo IS the license event." An open A/B question at the head of
  the v2 checklist blocks planning the flip.
- The operator settled that monetization is **not** sought through Tabularium. That
  collapses the deciding question — the thing Option B buys (a lever to charge a commercial
  integrator) is a lever the operator has decided not to pull.

This ADR records the decision and its reasoning; it does not relitigate settled points from the
notes (the rejected-along-the-way list). The notes stay as the audit trail.

## Decision
1. **License = Apache-2.0.** This selects Option A and **rejects Option B**. Rationale: (a) Apache's
   **explicit patent grant** and its "serious infrastructure" signal both matter in a
   medical-adjacent space; (b) zero adopter friction and a genuine "open source" label. The notes'
   deciding question is answered **NO**: the right to charge a future commercial integrator is *not*
   worth the lost label and the adoption friction, because commercial upside is deliberately not
   sought through the product.

2. **Attachment comes through its own pull request, before the public export** (operator,
   2026-11-01). Adding the `LICENSE` file *is* the license event: merging that pull request attaches
   Apache-2.0, and the preview terms leave `NOTICE.md` with it. Because a permissive license is
   irrevocable, the act takes the operator's own decision, apart from the choice of license.

3. **Copyright attribution names the maintainer** (operator, 2026-10-31 and 2026-11-01). The
   copyright line in `NOTICE.md` names the maintainer, and `CITATION.cff` names the same person in
   the same form, with no ORCID; its version and release date are added once a release tag exists.
   The maintainer will be named on the project's website in any case, so a collective notice would
   narrow the link to the project, not remove it; identifying combinations in the shipped text stay
   with the release review. A named attribution also travels with each redistributed copy and
   derivative work (Apache §4(d)). No public AUTHORS file: the private development history is the
   record of authorship. The export commit and tag carry the maintainer's name and GitHub no-reply
   address (operator, 2026-11-11). The export's identity
   scan exempts these two files by exact path at the export root (operator, 2026-11-06), which extends
   ADR-0013 point 3.

4. **The name stays a separate lever** (operator, 2026-10-10). No license grants the name
   "Tabularium". It is not registered, no registration is sought, and it is never marked ®.
   `TRADEMARKS.md` is a naming request, not a further licence: a modified version takes its own name
   and is asked to say "based on Tabularium" only while it keeps the intended-purpose statement and
   the listed care-contract rules. Apache §6 caps the request: any fork may state where it came from
   and keeps the NOTICE attribution.

5. **What NOTICE holds** (operator, 2026-10-10). Apache §4(d) obliges a redistributor to keep only
   the **attribution** notices of a NOTICE file and calls its contents informational, so NOTICE does
   not make the intended-purpose statement travel. NOTICE holds the attribution, the licence pointer
   with the fonts' own licence and the name's, the line that the project is shared free of charge
   and without warranty, and the intended-purpose statement; the README carries the bundled fonts'
   licence too and the statement that records kept with Tabularium are not part of it.

6. **Conduct** (operator, 2026-10-10). The project is supplied free and outside any commercial
   activity — nothing is sold or charged under the name, no paid help is offered under it, and no
   personal data is asked in exchange for access. Any change reopens this decision.

7. **Contributions** (operator, 2026-10-11). Issues and ideas only at first, so every merged word
   stays the authors'. If outside code or text is accepted later, each commit needs a sign-off line
   (Developer Certificate of Origin) and is licensed inbound by Apache §5; AI-assisted work is
   allowed, with the contributor answering for it. No contributor agreement: relicensing a
   contributor's part would need their consent.

## Alternatives considered
- **Option B (BUSL-1.1 + Additional Use Grant).** The steelman: it keeps a monetization lever
  (only *offering the skeleton or a derivative to third parties as a commercial product/service*
  needs a commercial license; all direct use stays free), which is real optionality for an
  author who might later want to sell. It loses here because the lever protects an upside the
  operator has decided not to seek through this artifact, and it costs on every axis that matters to
  a public-good release: it forfeits the "open source" label (must say "source-available") and adds
  adoption friction (hospital counsel balks at non-OSI terms). Given the non-commercial framing,
  Option B buys an unwanted lever at a certain cost.
- **MIT** (the other permissive default). Also OSI-permissive, but
  **Apache is preferred** for two concrete features MIT lacks: an **express patent grant** (worth
  having in a medical-adjacent space where a patent claim is not unthinkable) and a **`NOTICE`
  mechanism** whose attribution notices a redistributor must keep (point 5). MIT would work; Apache
  fits what is already built.
- **MPL-2.0, AGPL-3.0, and Apache for code with CC-BY for documents** (reconsidered 2026-10-10).
  MPL-2.0 is file-level copyleft with no network clause; AGPL-3.0 would oblige a hosted fork to publish
  its changes, at a real adoption cost; in the third, here the prose is the program. Apache stays: an
  express patent grant, common for agent skills, one licence for prose and code. Copyleft would oblige
  disclosure, not safety; the naming request is what ties safety to the name.
- **Attaching the license only at the public flip** (the rule from 2026-07-07; reversed by the
  operator, 2026-11-01). It kept the decision and the act apart, so that no shared snapshot carried an
  irrevocable grant before publishing. The operator decided the preview terms should come out now.
- **A collective notice, "The Tabularium authors"** (the rule from 2026-10-10; reversed by the
  operator, 2026-10-31). Same reason as point 3.
- **A fixed project identity, "The Tabularium authors", on the export commit and tag** (the rule from
  2026-10-10; reversed by the operator, 2026-11-11). With the maintainer already named in `NOTICE.md`
  it hid nothing, and it left the public repository with no linked contributor.
- **A reserved mark** (the rule from 2026-07-07; replaced by the operator, 2026-10-10).
  The naming request carries the safety aim without one.
- **Passing `CITATION.cff` by changing the token list** (not chosen, 2026-11-06). The list guards the
  records in every other file, where the name should stay flagged.

## Consequences
- **Easier:** the v2 LICENSE line resolves to a mechanical attach, not a deliberation;
  adopters get zero-friction, genuinely-open terms.
- **Harder / one-way:** Apache-2.0 is **irrevocable** once attached — the decision is one-way at the
  moment the pull request adding the `LICENSE` file merges, and the grant reaches anyone with access
  to the private remote as well as the public export (point 2). A later pivot to charging is not fully
  foreclosed, but be precise about what survives: the copyright holder can always grant *separate*
  terms, yet Apache already permits commercial productization of the released code for free — so
  **the only residual commercial lever after attachment is the name/trademark + goodwill, not the
  code.** Do not bank a code-monetization option that Apache has actually foreclosed. Relatedly,
  Apache §3 grants a perpetual, royalty-free patent license for the Work, limited to claims each
  contributor can license that are necessarily infringed by their contributions alone or combined
  with the Work to which they were submitted. Patent litigation alleging that the Work or an
  incorporated contribution directly or contributorily infringes a patent terminates the claimant's
  Apache patent licenses for that Work, including when raised by cross-claim or counterclaim. The
  grant does not by itself license independent implementations of the same method. For a
  documentation methodology this is largely theoretical, but attachment irrevocably gives up patent
  leverage within that scope, subject to §3's litigation clause — noted so it isn't discovered
  later.
- **Must be maintained — the load-bearing artifact is unchanged:** the **intended-purpose
  statement** ("personal record-keeping and care-coordination methodology for informal caregivers;
  not a medical device; not for diagnosis or treatment decisions; outputs may contain errors and
  must be verified against source documents") — MDR device status and AI Act risk class key off
  intended purpose, not the license. It stays stamped in README, NOTICE, and the clinician-handout
  Metodyka (kept in sync per HANDOUT-RULES).
- **The export's two identity exemptions** (point 3): each file is exempt whole, so an identity token
  added to either would ship; both stay short, are read at the release review and are scanned for every
  other class, and a same-named nested file still aborts. The relay scan has no such exemption and
  keeps flagging the name, one more hit to account for at the flip. **At the flip,** re-examine these
  carve-outs as already flagged in ADR-0013 (2026-07-04) and RELEASE-ROADMAP v2 — that tension is
  orthogonal to the license choice.
- One reason ADR-0054 point 5 gives for its numbering — the license unattached and preview terms in
  `NOTICE.md` — no longer holds once the license is attached.
- **Verified by:** the decision itself has no executable guard — it is governance, not a repo
  invariant — and lives here and in the resolved LICENSING-NOTES checklist. `LICENSE`, `TRADEMARKS.md`
  and `CITATION.cff` are on the export list, the export scans them, and `selftest.sh --export` bites
  both exemptions in both directions.
