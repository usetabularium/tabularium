# ADR-0055 — Release adoption as one recoverable operation

- **Status:** Accepted in part 2026-10-11; companion release notice accepted 2026-10-25
- **Date:** 2026-09-12
- **Deciders:** operator; discussion invited with Fable
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Under the two-instance split (ADR-0050) care runs an adopted release. Adoption was a hand-run
sequence: fetch the tags, check out the release, run the installer and the board, and, when this
was proposed, re-sync template blocks in records. Checking out the previous tag restores product
files, but not record changes or installed tooling. The caregiver should not have to design
recovery during an encounter. Complexity is measured in operator decisions, independently
maintained facts and possible intermediate states: moving a checklist behind a button helps only if
the operation owns its state and recovery.

The proposal of 2026-09-12 was one explicitly requested operation with a small local operation
record (care state, never a product file, and no second release pin), in five phases: prepare,
capture (pause other record writers and capture the recovery state with the existing snapshot
tools), apply (including a declared template migration), verify, and recover (resume or restore
code, pin, tooling and changed records without reading the previous agent's transcript). Rollback
during adoption and a later downgrade were separate promises: a downgrade must keep the records
created since adoption. Acceptance was to need synthetic success, interrupted-phase recovery,
failed-verification and downgrade-preservation examples.

**The companion question** (operator, 2026-09-13): do development changes reach care on their own?
They do not. Care moves only when an adoption session adopts a tag (ADR-0050, ADR-0054), and
nothing tells a care checkout that a newer release exists: the releaser's memory is the whole
mechanism. Here the releaser and the adopter are one operator; for a public adopter they never are.
The design: when a care session starts, a bounded, read-only check compares origin's release tags
with the adopted pin and, only when a newer release changes what the checkout runs, shows one plain
line; it never fetches objects, moves `HEAD`, rewrites the pin or adopts anything. Sessions never
start offline (operator, 2026-09-13), so that is not a design case. Captured that day as deferred to
the public flip, it moved here from the roadmap on 2026-09-20 and was triaged as a planned feature,
not required before launch; PUBLIC-FLIP R7 requires an explicit route for telling adopters about
releases.

## Decision

What holds now: the headers of `checks/adopt-release.sh`, `checks/install-instance.sh` (*release*,
*leftovers*, *release-notice*, */update*) and `checks/release-notice.sh`; `contributing/releases.md`
(*Adopting it*); `tools/claude-hooks/README.md` (*release-notice.py*);
`tools/claude-skills/update/SKILL.md`; and `README.md` (*Updates*, and the release check's
disclosure).

1. **Adoption is one explicit command in the care checkout** (accepted in part, operator,
   2026-10-11; built on 2026-09-29 as the smallest first step). It fetches the tags, checks the
   release out without touching an ignored file (every record is one), runs the installer and the
   board, stops at the first failure and prints the recovery. Nothing updates by itself.

2. **It never rolls itself back** (operator, 2026-10-11, deciding the open choice of 2026-09-29).
   On a red installer or board it prints the way back to the previous pin.

3. **The rest of the proposal is not adopted** (operator, 2026-10-11): capture, the operation
   record, resume and the downgrade promise. The template-migration step went with the per-person
   template copies (removed on 2026-10-04; ADR-0044); a release that changes the record format ships
   a one-time migration tool instead. A later downgrade, if ever built, must keep the records
   created since adoption, never restoring an old snapshot wholesale. Revisit when an adoption ends
   red or interrupted and its printed recovery does not finish it.

4. **Hardened, not redesigned, when that trigger fired** (break test, 2026-10-11). On a synthetic
   care checkout some runs ended red or interrupted without the printed recovery finishing or
   undoing them; no record was at risk in any. The fixes kept the one command: an interrupted
   adoption is finished by running the same command with the same tag again; a stopped checkout's
   recovery, which deleted nothing as first built, now removes the release's own untracked copies,
   which would block the next checkout, and never a record-set path; and the installer tells its
   own skills and hooks from the operator's by their bytes at a release tag. The clean-ups run in
   the installer being installed, so a rollback to an older release leaves a newer release's
   additions to remove by hand, as its note names them. The acceptance in part rests on a final
   re-test in which every printed recovery finished its adoption; point 3's trigger stands.

5. **The companion release notice** (accepted by the operator 2026-10-25; built 2026-10-26). The
   operator's three choices: build it now, to ship in the next minor release; on by default for any
   user, disclosed in `README.md` (the check tells the service hosting the repository that this
   machine runs Tabularium, once a day at most), with one opt-out outside the repository; and the
   line points to a `/update` care skill that runs the adoption command and reports in plain words.
   Its shape is a host-neutral operation plus a thin host adapter (ADR-0057). It speaks only when a
   MINOR or MAJOR release waits, since a patch changes nothing an instance runs (ADR-0054), in fixed
   words and release names only; adopting is the answer that silences it (`contributing/gates.md`,
   *A notice that repeats without a decision path trains dismissal*). The choices made in building
   it are stated in its owners: the daily stamp gates the network call itself, the opt-out stops
   only the automatic check, the adapter's place lets a rollback drop it, version numbers are capped
   at nine digits, and the skill is care-only and operator-invoked. Revisit a "skip this release"
   answer the first time the operator reports ignoring the notice.

6. **The hook's own message shows the line; no care rule relays it** (open choice 1, decided by a
   host test on 2026-10-26): the desktop app shows a SessionStart hook's user-facing message on
   screen, and the line reaches the session's context marked as already shown, since unmarked it
   was repeated unprompted. Run such a host test in a plain folder: in a scratch worktree under
   `.claude/worktrees/` a project's local-settings start hook did not run at all (cause not
   isolated). Open choice 2 closed with it: the line names `/update`.

7. **`CLAUDE.md` stays unchanged** (2026-10-26). The worry was that its rule against editing a
   tracked file in a care checkout would make an assistant refuse an adoption. Headless probes on a
   synthetic care folder under the real care contract found no refusal: `/update` ran the command
   and reported plainly, and, asked with no skill invoked, the assistant took the same command as
   the folder's update route.

8. **The check keeps git's credential helper** (2026-10-27, from a code review): clearing it would
   silence the notice for every private remote.

9. **An adopter's remote stays open** (open choice 3, with PUBLIC-FLIP R6): a public adopter's
   origin is the public repository, which today carries no tags to compare against.

### Guard admission (a notice is a control)

(1) Harm: a care checkout keeps running a release whose fixes it lacks, and for an adopter who is
not the releaser nothing says so. (2) Never against the operator: it blocks nothing and reads
nothing of theirs. (3) At the point of harm: the session start, where the choice to adopt belongs.
(4) Net positive: about a second once a day, one line only while a MINOR or MAJOR waits, an
opt-out. (5) Smallest form: no existing control compares with origin, and the line names one
decision, `/update`, whose answer silences it.

### Limits

- A lapsed sign-in looks the same as "up to date".
- The line gives a version, not whether CI passed on its tag; adoption still checks.
- A notice, not a guard: nothing reds while a release waits, and L19's pin rule is unchanged.
- With an https remote whose credential helper needs the keychain, a keychain dialog could appear
  at session start, at most once a day, cut off after four seconds.
- An operator's own skill that shares a name with a later release's skill is overwritten when that
  release is adopted.
- On case-insensitive macOS a local tag differing from a release only in letter case can shadow it;
  that needs a tag made in care.

## Alternatives considered

- **The full recoverable operation as proposed** (2026-09-12): not adopted on 2026-10-11 (point 3).
- **More prose around the hand-run procedure:** cheap at first, but it depends on agent memory and
  leaves interrupted state ambiguous.
- **A general workflow engine:** excessive for one local operation.
- **Automatic updates during care:** defeats operator control; adoption stays deliberate.
- **Rolling back by itself on a red installer or board:** declined 2026-10-11 (point 2).
- **Name lists or a header to tell the installer's own skills and hooks from the operator's**
  (2026-10-11): re-tests found name lists missed a newer release's additions on a rollback, and a
  header alone could not tell the operator's hook from ours (point 4).
- **Relaying the line through a care rule** (open choice 1's fallback): one keystone sentence
  telling the assistant to relay the hook's context output once; not needed (point 6).
- **Pointing the line at the manual sequence** (open choice 2's fallback, had the one command not
  been built first).
- **Deriving "routine" or "has extra steps" from the release note's `Adoption:` line:** a possible
  refinement, as a fixed word from an exact match; not built.
- **Clearing git's credential helper for the check:** declined 2026-10-27 (point 8).

## Consequences

- Adoption is one operator-visible step, `/update` or one command, and the care safety rules are
  unchanged. A red or interrupted adoption is recovered from a printed line, not by interpreting an
  earlier session; nothing rolls back by itself, so a red board waits for the operator.
- At session start, a care checkout can learn of a newer MINOR or MAJOR release, at the disclosed
  cost of at most one automatic tag listing a day sent to the hosting service. Adding installer
  and session-start behaviour, the notice is a MINOR change (ADR-0054).
- The notice cannot help a public adopter until releases reach the public copy (point 9).
