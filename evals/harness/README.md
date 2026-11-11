# The eval harness — how to run the behavioral eval

This is a **driving test for the assistant**. The guards in `checks/` test the files; this tests
whether the assistant still *behaves* — still preserves a fact you gave it when its own analysis
disagrees, still treats a missing document as a question rather than an alarm, still keeps one
person's session to one person.

Each case builds a small pretend patient tree in a scratch folder **outside this repository**, asks
the assistant to do one ordinary job in it, and then checks what actually happened: which files
changed, which files it opened, and the last thing it said. The people, drugs and labs are invented
(`evalperson-a`, `Drug X`, `LAB-KFN`). No real record is ever read, copied, or sent anywhere.

## Before the first real run

Two things the harness cannot do for you:

1. **Give the eval sessions a login.** A subscription login is enough — sessions count against the
   plan's rate window, not a bill. Do *not* export `ANTHROPIC_API_KEY` unless you want pay-per-token
   billing: the CLI prefers a key when one is present. Without a usable login the CLI reports "Not
   logged in" and the harness stops rather than record empty sessions. The controls, the dry run
   and `regrade` need no login. Eval sessions run on your own Claude account, so they count against
   your plan and fall under its terms.

   Each eval session starts from a fresh config folder, so your memory and settings stay out. If
   that folder cannot see your login (the harness says so), mint a headless token once in a normal
   terminal where `claude` is logged in and export it; the harness passes it through:

   ```
   claude setup-token
   export CLAUDE_CODE_OAUTH_TOKEN=<the token it prints>
   ```

   The token is a credential: never share or commit it.

   **From inside a Claude Code session** the assistant's shell never receives that token
   (deliberate credential hygiene). Put it in a 0600 file outside the repository instead; the
   launcher reads it into the eval sessions only, never printed or logged:

   ```
   mkdir -p ~/.config/tabularium-eval
   (umask 077; printf '%s' "$CLAUDE_CODE_OAUTH_TOKEN" > ~/.config/tabularium-eval/token)
   ```

   Delete the file to revoke. One that is group/world-readable or inside the repository is refused,
   loudly.
2. **Prove containment once, and look at the answer yourself.** The containment probe costs one to
   three short sessions (a declined attempt is retried); the image probe costs one:

   ```
   export TAB_EVAL_SCRATCH=~/tab-eval-scratch      # any folder outside the repository
   python3 evals/harness/session.py containment --model opus   # must print "proven": true
   python3 evals/harness/session.py image          # must print "image_delivered": true
   ```

   The runner repeats both probes at the start of every run and refuses to start trials if
   containment is not proven; the manual run is so a human has read the reasons at least once.

## Running it

From the repository root. A run that spends builds its folder (transcripts, trees, log) in
`~/tab-eval-scratch` (or `TAB_EVAL_SCRATCH`). When it ends — green, red, partial or crashed — the
folder is packed into one compressed file, read back, and the local folder removed only if every file
matches; any mismatch keeps the folder, and the run says so. The CLI's account folder (`config/`)
never enters the archive, but for `.eval-auth-mode`. Where the file goes is yours to choose (*Where
archives go*, below). The free checks (the controls and dry runs) use a system temp folder and delete
it on exit, after a crash, Ctrl-C, or a kill by SIGTERM or SIGHUP too, unless given `--keep`, which
prints the kept folder's path; a folder that could not be removed is named, never reported removed:

| What you want | Command |
|---|---|
| Check the marking scheme itself | `python3 -m evals.harness.controls` |
| Check the containment machinery | `python3 -m evals.harness.test_containment` |
| Check the comparison's machinery and its marking scheme | `python3 -m evals.harness.test_compare` · `python3 -m evals.harness.compare_controls` |
| What is this machine, as the eval sees it | `python3 -m evals.harness.containment` |
| Rehearse without spending a session | `python3 -m evals.harness.run_eval --dry-run` |
| One case, one go | `python3 -m evals.harness.run_eval --variants EV-01a --trials 1` |
| What a run will cost, from the last one | `python3 -m evals.harness.run_eval --estimate` |
| **The core run — the default, and the one that counts** (20 trials + 3 short probes) | `python3 -m evals.harness.run_eval` |
| A new model (the core run counts for it too) | `python3 -m evals.harness.run_eval --model <new model>` |
| The full suite, on request (78 trials + 3 short probes) | `python3 -m evals.harness.run_eval --full` |
| Only the cases a change touched (never a passing run) | `python3 -m evals.harness.run_eval --variants EV-04a,EV-06b --trials 10` |
| The handout fact-checker's care twin, in neither suite (never a passing run; EV-12a is in the full suite) | `python3 -m evals.harness.run_eval --variants EV-12b` |
| Was it the model or was it us? | `python3 -m evals.harness.run_eval --stack <old git revision>` |
| Re-judge a finished run for free | `python3 -m evals.harness.regrade <run root>` |
| Bring an archived run back where it ran, first, for `regrade`, `--regrade` or `--report` (a few seconds) | `python3 -m evals.harness.archive restore <run root name>` |
| Archive the run folders a session ran in that are still in the scratch folder, one at a time (each local folder removed once its archive matches; the rest listed, not touched) | `python3 -m evals.harness.archive existing` · `… existing --dry-run` lists them |
| The same model without Tabularium (never a passing run; `evals/topics/with-and-without.md`) | `python3 -m evals.harness.compare --model <model>` |
| … its price, its rehearsal, its re-judging | `… compare --estimate` · `… compare --dry-run` · `… compare --regrade <run root>` |
| The emergency stress test, up to four arms (never a passing run; needs the held-back data) | `python3 -m evals.harness.stress --arms tabularium,floor2 --model <model>` |
| … its price (no model call), rehearsal, arms' exact rule texts, re-judging | `… stress --estimate` · `… stress --dry-run` · `… stress --show-arms` · `… stress --regrade <run root>` |
| … its marking scheme: controls, the EV-09 replay, the predictions | `python3 -m evals.harness.stress_controls` · `python3 -m evals.harness.test_stress` |
| Read a finished run's wording with the inference judge (non-gating; [`judge.md`](judge.md)) | `python3 -m evals.harness.judge run <run root>` · `--estimate` · `--dry-run` |
| … record the operator's ruling on a listed trial; re-check a revised judge on a fresh run; its tests | `… judge verdict <run root> <trial id> <tier> "<reason>"` · `… judge recheck <run root>` · `python3 -m unittest evals.harness.test_judge` |
| One row per run, from the ledgers (`evals/README.md` → *Ledger*); is it current? | `python3 -m evals.harness.scores` · `… scores --check` |
| Run the judge as part of a core or full run, before it is archived (otherwise its price is printed at the end) | `python3 -m evals.harness.run_eval [--full] --judge` |

Without `--model` (or `TAB_EVAL_MODEL`) sessions run on the headless CLI's own default, which need
not be your client's model and has changed before; name the model you mean to test. The log records the model the session actually resolved to, not the one requested.

**Start with the controls.** They plant deliberately wrong answers and confirm the marking scheme
catches each one — a marker that never fails anything would print a comforting green over nothing.
They also compile every manifest pattern first: the grader fails an assertion whose pattern does not compile, so every bad tree aimed at it would fail for nothing. If the controls misbehave, fix that before believing any run. They include the EV-09 probe corpus
(`ev09_probe_corpus.json`); its `excluded` entries are parked, not certified controls.

**After a contract rewrite, before paying for a run:** search the oracles for the old contract's
wording and examples; ship every file the new contract names as a rule; then have a reviewer write
answers that follow the new contract in its own words and grade them through `grader.grade`,
pinning each fix with a green control (ADR-0049 element 12).

**Two checks run before anything is sent:** the scan for the private-mode identifier and the roster
check (`evals/README.md` → *Containment requirements*, 6 and 7). A find stops the run before the
first session and says *where* (file, line, class), never what. The token list is found through
`TABULARIUM_REGISTRY_PATH`, else `checks/FIREWALL-REGISTRY`; `python3 -m evals.harness.containment`
shows what this machine looks like.

**The pretend dates are built from the day you run.** Every planted date sits at least three days
back, so no guard turns red over a date in the future. The log records the day each tree was built from, so
older runs regrade correctly.

**Calibration is free; sessions are not.** A run keeps every before-tree, after-tree and
transcript in its archive. When the marking scheme misreads a compliant answer, fix the
scheme and `regrade` the captured run (restored first); nothing is re-run. Only a case whose *spec* was wrong costs
new sessions.

**`--stack` is the migration tool.** When a new model arrives, both the model and this repository's
instructions may have moved since the last clean run, so a failure is ambiguous. Running the new
model against an older revision's `CLAUDE.md` separates the two.

The run, comparison, stress and judge ledgers (`evals/results/*.jsonl`) are the main checkout's even when
the harness runs from a linked worktree.

## Where archives go

By default, `archive/` in the scratch folder, on this disk; a paid run with nothing set says so in one
line. To keep archives elsewhere, put an absolute folder path in `~/.config/tabularium-eval/archive-dir`
(first line that is not a `#` comment), or in `TAB_EVAL_ARCHIVE_DIR` for one shell. Any folder works,
and no provider is required:

| Where | First line of `archive-dir` |
|---|---|
| A cloud sync folder (iCloud Drive, Dropbox, Google Drive, …) | `~/Library/CloudStorage/<your sync folder>/tabularium/eval-runs` |
| An external drive | `/Volumes/<drive name>/tabularium-eval-runs` |
| Nowhere: keep each run's folder as it is | `off` |

The folder must exist: a missing one is never created, so an unplugged drive or a stopped sync client
keeps the run's folder instead of swallowing it. In a folder macOS's File Provider keeps (the cloud
sync folders under `~/Library/CloudStorage`), each archive is then made online-only, and the run
says so only once it is; otherwise it names Finder's Remove Download. An external drive has nothing
to evict. The output never prints a sync folder's own name, which carries the account.

A run you stop with Ctrl-C is not archived: its folder stays, and the session it was running stops
with it. `python3 -m evals.harness.archive one <path>` archives it later.

Eval archives hold invented patients and the tool's own text, so no encryption is required of the
folder.

## Reading the result

- **GREEN** — every trial ran and passed. It means no failure showed up *in this many samples*;
  `evals/topics/how-sure-a-green-is.md` says plainly what that can and cannot rule out. A green
  core or full run says it is a passing run; a targeted run never is.
- **READ-THESE-FAILURES** — something failed or could not be judged. The summary lists each one with
  its transcript path, safety-labelled ones first. **A safety failure means do not adopt this setup
  for real care work until it is resolved.** A care failure is yours to weigh — read the transcript,
  decide, and note the decision. Trials marked *invalid* (a guard went red, the session died) are
  not failures of behaviour; rerun them, and never count them toward a green. A red board's note
  names its `FAIL [Lnn]` line(s). `regrade` carries a red closing board, an environment-invalid
  trial and a trial with no run-time row as `invalid`, never as a pass. A safety failure no longer
  stops a run, the core included. A real one is followed up with `--variants <id> --trials 10`, not
  the whole core.
- **PARTIAL** — everything that ran passed, but something was skipped: usually the assistant could
  not be shown an image, so the cases that turn on inspecting an original did not run. A partial run
  is never a full green.

Every run prints its scratch folder, and at the end where its archive went: the transcripts, the
before-tree and the after-tree are in it, which is where to look when a line in the summary needs
explaining. The summary's transcript paths are gone once the run is archived; `archive restore` puts
them back at the same paths.

## Elsewhere

The run record and how its rows land: `evals/README.md` → *Ledger*. Rationale, scope and limits:
`adr/0049-behavioral-compatibility-eval.md`. What it covers, how sure a green is and the technical
contract: `evals/README.md` and the topic docs it lists. One page per case: `evals/cases/`.
