# ADR-0056 — Durable specifications with selective retrieval

- **Status:** Proposed 2026-09-12
- **Date:** 2026-09-12
- **Deciders:** operator; discussion invited with Fable
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

An untracked handover cannot be the only specification a fresh clone or PR reviewer needs.
Conversely, a durable Markdown file is not automatically a good index: on 2026-09-12 the ADR
register combined navigation, current decisions and substantial historical reasoning in long table
cells. Serializing that same prose as JSON would not reduce the context an agent loads.

The operator favors a navigable JSON-LD index and structured system incidents. This proposal keeps
those useful identities and relationships while limiting the machinery and migration cost.

## Proposed decision

1. Keep architectural proposals in numbered ADR files with **Proposed** status. Use their PRs for
   discussion with Fable and dated points in the ADR for durable conclusions. A merged proposal
   document does not by itself accept the proposal. Existing accepted rules remain authoritative;
   since 2026-11-01 they include ADR-0061: a Proposed ADR is edited until it is accepted or
   rejected, and an accepted one is superseded, not amended.
2. Keep specifications and substantial reasoning in short tracked documents. Each entity has one
   authoritative home and a stable ID independent of its file location. A `docs/` runbook holds
   execution steps or a kickoff pointer, never the only durable rationale or acceptance criteria
   (2026-10-24: the first text named `_inbox`, and the development inbox retired that day,
   ADR-0030; `docs/` is DEV-local since 2026-10-28).
3. Generate a compact JSON-LD catalog from authoritative metadata. Query IDs, status or affected
   product paths before loading selected documents. Follow explicit links as needed, not every
   transitive relationship. Do not load the full catalog at every session start.
   **The register is an index; no JSON is stored** (operator, 2026-09-13; recorded 2026-09-29).
   `adr/README.md` holds one line per decision — number, title, status, link — and every decision
   has its own file carrying its reasoning (and, until the ADR-0061 migration, its amendments). The
   register's rows moved into those files verbatim, as did 17 of its 18 amendment blocks; the
   eighteenth, the README's summary of ADR-0023's 2026-06-25 amendment, was dropped as a duplicate
   of the full text that file already holds. A JSON catalogue, with links between decisions, is
   generated from the decision files by a small script only the first time a real question needs
   it; nothing is stored, so nothing has to be kept in sync. This proposal stays Proposed.
4. Separate an **incident occurrence** from the **persistent limitation** it exposes: several
   incidents can point to one KI. Structured occurrences distinguish observation, inferred cause,
   evidence and resolution. Narrative analysis remains possible where useful.

## A first implementation, when a real query needs one

A DEV-only, read-only, stdlib-only query over **git-tracked, file-backed ADRs** would read header
metadata and return JSON-LD on demand. It does not migrate register-only ADRs,
known issues or incidents, replace their canonical sources, or introduce a session gate.
Path queries use only explicit `affects` metadata; no match is not evidence that an older ADR is
unrelated. `related` IDs may refer to register-only decisions, which such a query would not resolve.

The optional header comment supplies only explicit relationships and affected paths:

```text
<!-- catalog: {"related":["ADR-0050"],"affects":["checks/install-instance.sh"]} -->
```

The existing title/status remain their own source of truth. The catalog is generated, not checked
in as a second editable register. It uses an embedded vocabulary context and needs no network or
graph service. Ordinary JSON consumers can use it; a future independent consumer can interpret the
typed links. [JSON-LD design goals](https://www.w3.org/TR/json-ld11/#design-goals-and-rationale).

**The pilot waits for a real query** (operator, 2026-09-13). A pilot (`tools/adr_catalog.py`) was
built and removed before merge: only 3 of 56 decisions carried its metadata, plain search found the
same results, and its IDs would sit under a website address that is not live. Reintroduce it the
first time a session cannot find a decision with plain search. The rest of this proposal stands.

## Alternatives and tradeoffs

Plain JSON provides nearly all the immediate retrieval benefit. A small JSON-LD context additionally
gives identities and relations shared meaning at low initial cost, but it will need versioning if
its meaning changes. Broad ontology work has no current consumer to justify it.

JSONL suits a real stream of appended observations; it is not required merely to preserve history
already in Git. Markdown is still the useful format for rationale. A structural validator can
require an evidence pointer for closure; it cannot establish that the evidence is true.

## Discussion with Fable

Try the pilot on a concrete maintenance question. Does it find the necessary decision with less
context, and is any omitted register-only entry misleading despite the explicit scope? Which
recurring query first justifies adding KI/incident records? Challenge the proposed vocabulary and
identify duplicate authoritative facts before proposing more fields.

Adopt a broader migration only with a narrow batch, preserved IDs and references, and a demonstrated
reduction in loaded context. No bulk rewriting of historical ADR bodies is authorized by this
proposal. Use the PR for discussion and record agreed decisions here, dated.

The frozen register-row copies were trimmed on 2026-10-11 (operator, 2026-10-11) wherever the index
and the body held their facts; a cell holding a fact found nowhere else in its body moved into that
body first. The authority was that operator rule, then in `adr/README.md`, not this proposal, whose
"no bulk rewriting" line is unchanged. The migration of every ADR under ADR-0061 (2026-11-01)
likewise rests on that ADR.
