# ADR-0057 — A portable core with small agent-host adapters

- **Status:** Proposed 2026-09-12
- **Date:** 2026-09-12
- **Deciders:** operator; discussion invited with Fable
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Care rules, Markdown records, templates and most executable helpers are usable by different agents.
Host assumptions cluster in skill activation, installation paths, hook events and the eval driver,
which launches `claude`; the registry read-guard dispatches Claude tool names. Converting a manifest
would not prove equal behavior or protection. OpenAI's documentation (reviewed 2026-09-11) covers
converting a Claude plugin, reusing its skills and adapting command hooks for ChatGPT Work and
Codex, but says not to depend on hooks in ordinary Chat; local and web projects differ in
local-folder access
([conversion guide](https://developers.openai.com/plugins/guides/submit-claude-plugin),
[hooks](https://learn.chatgpt.com/docs/hooks), [projects](https://learn.chatgpt.com/docs/projects)).

## Decision

What holds now: no second host is enabled. The Codex eval host and what it still needs are in
`evals/topics/codex-host.md` and in `evals/harness/` (`codex.py`, `codex_trace.py`,
`run_eval.py`); its offline tests run in `checks/selftest.sh`, which CI runs.

1. **One product core, small host adapters** (2026-09-12). The core is care and build rules,
   record formats, templates, deterministic operations and eval scenarios. Packaging, activation
   policy, tool-event translation, configuration and eval launch go in small per-host adapters. No
   general plugin framework until a second adapter shows the need.
2. **Cheap choices now** (2026-09-12). New operations take explicit inputs and return a structured
   result and a meaningful exit status, whatever the provider's transcript or tools. `/architect`
   means explicit operator intent plus the independently checked instance, and each host maps its
   own explicit invocation to it; entry files stay thin pointers. Helpers use package-relative
   assets and an explicit working root; host settings and provider and model names belong in
   adapters or tested configuration, not care prose. Eval cases are shared, launch and event parsing
   isolated, and each result keeps its exact model and runtime rather than claiming hosts
   equivalent.
3. **Second host and scope** (2026-09-12). Local ChatGPT Work or local Codex is the initial
   candidate because it can preserve the local care architecture. Ordinary Chat can reuse the
   method, but uploading instructions does not recreate this install. Cloud operation changes
   storage and recovery assumptions and needs its own decision. Never infer hook coverage from a
   successful install: test the real read, edit, search and shell paths on synthetic restricted
   data, and report a missing capability before care relies on it. ADR-0031's single-operator,
   honest-slip scope stands. Release adoption and durable retrieval come first (ADR-0055, ADR-0056),
   then operator-control behavior and the second host on the same scenarios. Nothing here authorizes
   a record transfer or public distribution, or claims ChatGPT compatibility.
4. **A Codex eval adapter, disabled until containment is proven** (2026-10-27). On local Codex CLI
   `0.164.0-alpha.11.1`, `workspace-write` does not establish that a process's reads stay confined,
   and the macOS `sandbox-exec` sanity test was denied; nothing else was tried after that. So
   `run_eval --host codex` refuses before any Codex process, service call or login read, with no
   override. Enabling it needs an outer boundary over startup instruction discovery, tools,
   subprocesses and symlink paths, with only the trial's data readable and no tool network, proven
   by denied outside reads and writes through the real launch, plus image and configuration
   checks. Comparison mode is unchanged.
5. **A valid first Codex experiment** (2026-10-28) also needs Codex dispatch to its own launcher
   and grader, unresolved assertions kept in summaries and the ledger, the actual model, effort and
   runtime recorded, and the event parser calibrated on a captured, safely isolated session. The
   care contract allows record edits only in Claude Code, and the eval note says file tools only, no
   shell, while the proposed Codex launch exposes command execution. **Operator rulings,
   2026-10-28:** the operator approved an explicit, hashed, synthetic-only host note that adapts
   those two assumptions, with a matching launch policy (neither built yet); it changes neither the
   care contract nor its real-record boundary. The operator chose to merge the disabled scaffold
   first. The first selection (`evals/topics/codex-host.md`) is a targeted run, never a core pass.

### Admission test (guard-admission)

The credential and containment refusals (2026-10-27): (1) an unconfined read could send care
records to a service the operator did not choose, and an API key could spend outside the plan; (2)
they enforce the operator's synthetic-only, no-transfer limits and leave offline work (discussion,
estimates, fixtures) open; (3) they come before the first Codex process or service call; (4) live
use waits for proven confinement, not a per-trial confirmation; (5) one adapter owns them, with no
bypass flag.

## Alternatives considered

- **A full rewrite around one provider's API:** swaps one dependency for another and adds a host.
  **Duplicating the instruction stack per provider:** creates drift. Thin adapters keep the
  substance shared and each compatibility claim testable.
- **A separate HOME alone** (2026-10-27): isolates configuration, not reads. Live use waits for
  proven confinement rather than per-trial confirmation; no containment bypass is allowed.
- **A literal-contract Codex experiment** (2026-10-28): a compliant refusal to edit would not show
  a portability failure; such refusals would need to be interpreted against the unchanged contract.

## Consequences

- Each compatibility claim becomes a test, not a manifest. The Codex scaffold stays offline and
  CI-tested without Codex or a login; even enabled, its event stream cannot certify reads, so most
  core trials stay unverifiable there.
- Open for the discussion with Fable: the smallest second-host experiment (one synthetic care
  workflow, its file and image operations, the relevant denied-read cases); which assumptions need
  an adapter; any abstraction without two concrete callers; and what the adapter lets us remove.
