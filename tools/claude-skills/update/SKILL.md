---
name: update
description: Update this care folder to a newer Tabularium release, with the one adoption command.
disable-model-invocation: true
allowed-tools: Bash(bash checks/adopt-release.sh:*), Bash(git tag -l:*)
---

# Update to a newer release

The operator typed `/update`: they want this care folder moved to a newer Tabularium release. This
is how a care folder changes version — the command checks a release out whole, installs its tooling
and runs the board. It is not a hand edit of a tracked file, which the care contract forbids.

1. **Mid-care?** If this session has edited a record and the board has not been green since, say so
   in one sentence and ask whether to update now or after the work is finished.
2. **Run it**, from the top folder of this checkout, exactly as written and on its own (nothing
   chained to it; its exit status comes back with its output), and nothing else first:
   `bash checks/adopt-release.sh` — or, when the operator named a release, `bash checks/adopt-release.sh vX.Y.Z`.
   It refuses by itself outside the main care folder and over any changed tracked file. Never work
   around a refusal, never edit a file to turn a red green, and run no other git command than the
   release-note reads below and, on the operator's word, a line this command printed.
3. **Report the outcome in plain words**, by its exit status:
   - **0** — the folder runs the release it names, and the checks are green. If it said it was already
     on that release, say so: it was in use already, or an earlier update is now complete — the command
     cannot tell which. Then read that release's note, `git tag -l --format='%(contents)' vX.Y.Z`, the
     line beginning `Adoption:`: if it lists steps after `routine`, give them to the operator, in order,
     to do by hand if not already done for this release. Close with: start a fresh session to work
     under this release — this one may still hold the previous release's rules.
   - **1** — nothing changed. Say why in one plain sentence from its `REFUSED` line; if it printed a
     line to run, give that line as a ready command.
   - **2** — the update stopped partway, or a check went red after it. Say so plainly, give the one
     line it printed (to finish, or to return to the previous release) as a ready command, recommend
     one, and run it only on the operator's word. After a return to the previous release, read the
     note of the release you were adopting, the line beginning `Rollback:`, and give the operator any
     items it lists to remove by hand.

The copy under `.claude/skills/` is refreshed byte-identical from `tools/claude-skills/update/SKILL.md`
by `checks/install-instance.sh` (care only); edit the source, never the copy.
