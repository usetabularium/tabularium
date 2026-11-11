---
name: guard-admission
description: Admission test for a new guard, check, hook, gate, refusal, confirmation step or other quality control in this repository. Use BEFORE proposing, recommending or adding one — including when a review or red-team finding recommends one, and before tightening an existing control. Also use when an existing control blocks work the operator asked for.
---

# Guard admission

A control is admitted only if it passes all five questions. Put the answers in the pull request
description, one line each, not in an ADR. A "no" on 1 or 2 ends the proposal. A "no" on 3, 4 or 5 means reshape it and ask again.

1. **A concrete harm on a concrete path.** Name the failure and where it happens: data going where it
   must never go (a private-mode identifier to the AI API; record content into a tracked
   development-tree file, and from there to the Git remote and the export; one person's facts into
   another person's record) or a record being damaged (immutable sources, sealed handouts, the
   ownership ledger). Cite an observed incident or a credible path, not a theoretical one.
2. **Never the operator against themselves.** It must never stop the operator, or an agent working at
   the operator's request, from reading or using the operator's own data on the operator's own
   machine. Reading is not leaking. A control that fails this is a usability defect, not a guard.
   The one exception is data the operator has declared must never reach the AI API (a private-mode
   identifier): for an agent, reading it is sending it, so that read is the harm in question 1.
3. **At the point of harm.** It acts where the harm happens — the write, the commit, the push, the
   API call, the export — not upstream on reading, discussing or planning.
4. **Clearly net positive.** The patient-safety or record-integrity gain clearly outweighs the
   usability cost: friction per use times how often it is met, extra round trips, notices that
   repeat. If the balance is not clearly positive, prefer a prose rule, a declared posture, or an
   accepted risk with a revisit trigger.
5. **Smallest form, one home.** It is the smallest control that does the job and duplicates no
   existing one (search the repository). Every message it prints names one decision the operator can
   take, or fires once and goes quiet. A legitimate case that trips it has one obvious next step
   that is not a workaround.

**Meeting an existing control that fails 1 or 2:** say so to the operator in one plain sentence and
propose the tear-down. Do not route around it on your own.
