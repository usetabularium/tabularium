# Shared — cross-cutting & joint matters

For things that aren't cleanly one person's. Two reasons something lives here:

1. **Joint by nature** — shared property, household finances, decisions involving more than one person.
2. **Cross-cutting** — a non-medical question whose answer *depends on* one person's
   medical facts (e.g. "can a trip fit around one person's treatment dates?"). The decision
   artifact lives here under `nmed/`, it may *read* the relevant person's `profile.md`, but pull only
   the specific facts needed — don't copy medical history in.

## Layout
- `nmed/` — non-medical joint matters; one folder per matter (e.g. a joint contract, shared paperwork).
- `med/` — joint medical-adjacent material (rare; e.g. a decision affecting both, shared
  caregiving logistics). Person-specific medical records do **not** go here.

> Context rule: working a `_shared/nmed/` question does not entitle you to load any
> person's full medical file. Load medical facts only when the question is explicitly
> cross-cutting, and only the facts in play. See CLAUDE.md → *Context*.
