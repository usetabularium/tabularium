# How a run works

Read when: you change the runner's steps or gates, change the surfaces the grader checks, or need
to understand a run before its first session.

**When a run happens, and what it leaves behind:**

```mermaid
flowchart TD
  K["CLAUDE.md or the eval-mode note is edited"] --> C["Decide how much the change moved"]
  M["A new model, same instructions"] --> CORE
  C --> ED["editorial: no run"]
  C --> TG["targeted: optional lean run of the touched cases"]
  C --> CORE["load-bearing: core run recommended"]
  TG --> RUN["Run the harness"]
  CORE --> RUN
  RUN --> G["green"]
  RUN --> F["read these failures (safety: do not adopt)"]
  RUN --> P["partial (never green)"]
  G --> B["core or full green: the run says it is a passing run"]
```

**Once per run: the gates.** Each fails closed:

```mermaid
flowchart TD
  S1["Pick the suite: core by default, --full, or --variants"] --> S2["Load and hash the instructions (working tree, or --stack for an older revision)"]
  S2 --> S3["Containment preflight: registry, private-mode file, roster, instruction scan"]
  S3 -- "any hit or a blind scan" --> X1["Abort: one aborted row, nothing sent"]
  S3 --> S4["Print the plan and its price"]
  S4 -- "--dry-run" --> D["Build and preflight each variant once, no sessions"]
  S4 --> S5["Clean config folder and login check"]
  S5 -- "not logged in" --> X2["Stop before any session"]
  S5 --> S6["Containment self-test: read and write canaries"]
  S6 -- "not proven" --> X3["Abort before any trial"]
  S6 --> S7["Image probe: read a token out of a PNG"]
  S7 -- "no pixels" --> X4["Image cases skipped: the run can only be partial"]
  S7 --> L["The trial loop"]
```

**Once per trial, in this order:**

```mermaid
flowchart TD
  T1["Build the synthetic fixture outside the repository, dated from the run date"] --> T2["Ownership-ledger append"]
  T2 -- "fails" --> I["Trial invalid: rerun as a new run"]
  T2 --> T3["Guard preflight: check.sh on the fixture"]
  T3 -- "red" --> I
  T3 --> T4["Copy the before-tree"]
  T4 --> T5["Pre-transit scan of the tree and the task for the private-mode identifier"]
  T5 -- "hit" --> A["Abort the whole run"]
  T5 --> T6["Headless session: claude -p, file tools only, 10-minute cap"]
  T6 -- "misconfigured or timed out" --> I
  T6 --> T6b["Re-bind any transcription the session corrected"] --> T7["Closing guard check, always last: red voids a pass, a fail stands"]
  T7 --> T8["Grade the three surfaces"]
  T8 --> V["pass, fail or invalid: one ledger row"]
```

**Grading.** Grading is offline and deterministic, and the grader is checked without sessions:

```mermaid
flowchart TD
  S["Captured per trial: before and after trees, tool-call log, final message"] --> G["Grader, after the session ends"]
  G --> C1["Scoped writes"] & C2["Collateral guard"] & C3["Content rules"] & C4["Confirm-by dates"] & C5["Read scope"] & C6["Final-message phrases"]
  C1 & C2 & C3 & C4 & C5 & C6 --> V["Verdict carries the worst failed severity: safety or care"]
  K["Controls: planted wrong answers must fail"] -.-> G
  R["Regrade: re-judge a captured run for free"] -.-> G
```

Reading the outcome (**green**, **read these failures**, **partial**) and where the transcripts
land: [`harness/README.md`](../harness/README.md) → *Reading the result*.
