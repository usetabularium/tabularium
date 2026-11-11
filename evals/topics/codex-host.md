# Codex host (disabled pending read confinement)

Read when: you work on the Codex host adapter, plan a Codex run, or change what it refuses.

`python3 -m evals.harness.run_eval --host codex --estimate` plans the same core cases (20 trials by
default); `--full`, `--variants` and trial-count overrides select the same cases as the Claude host.
It reports unmeasured Codex time with a ten-minute timeout budget per trial. Usage comes from the
operator's Codex plan and quota; Claude's dollar ledger does not price it.
`… run_eval --host codex --dry-run` builds and preflights fixtures without a session.

Codex's fixture adds `AGENTS.md`, a thin pointer requiring `CLAUDE.md` first and then `EVAL-MODE.md`.
The former keeps the same keystone bytes; the latter holds the existing eval-mode addendum verbatim
(the generated handout-verifier note for that profile). The synthetic records, intake checklist,
ownership steps and guard checks use the existing builder.

**`… run_eval --host codex` refuses before any live session.** `workspace-write` does not prove that
reads stay inside the trial, and a separate HOME only isolates configuration. The local OS sandbox
sanity test was denied; no outside-canary probe or Codex trial ran. There is no containment override.
An enclosing read boundary and an actual denied-read/write probe must be implemented before this
host can run; [ADR-0057 points 4–5](../../adr/0057-portable-core-and-host-adapters.md#decision)
record the evidence and remaining work. API-key environment variables also refuse by default;
`--allow-api-key` bypasses only that credential check, never containment. No login material is read
or copied while the host is disabled.

The offline JSONL adapter records conservative possible reads, file changes and their event order.
Shell commands and implicit reads cannot certify a complete read inventory: declared `READ_REQUIRED`,
`READ_SCOPE` and `read_before_write` assertions are **UNVERIFIABLE**, never a silent pass. Incomplete
or unknown events also make affected message assertions unverifiable; tree assertions are unchanged.
Offline tests: `python3 -m unittest evals.harness.test_codex evals.harness.test_codex_trace`.
They also run in CI and need no Codex installation or login.

Read confinement is only one enablement requirement. The runner still needs Codex configuration,
launch, probes, trace grading and runtime/ledger dispatch. The experiment must also resolve two
host assumptions explicitly: `CLAUDE.md` permits record edits only in Claude Code, and the shared
eval note promises file tools without a shell, while the proposed Codex launch exposes command
execution. The operator has approved a synthetic-only host exception; its hashed host note and
matching launch policy are not implemented. The scaffold changes neither care rule.

After those requirements are met, the core variants using tree/message evidence are EV-01a and
EV-09a (two trials each), and EV-17a and EV-18a (one trial each). The other fourteen core trials
need read evidence this adapter cannot establish. The prospective
selection is `--host codex --variants EV-01a,EV-09a --trials 2` (add `--estimate` or `--dry-run` for
offline preparation). Four targeted trials never count as a passing core run, and live execution
of this selection remains disabled. Pin the model and reasoning effort and agree the quota budget
before spending sessions.
