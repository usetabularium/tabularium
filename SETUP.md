# Setup — first run on a new Mac

Read when: the setup prompt sent you here, in a fresh clone at `~/Tabularium` with no records. The
session usually stands in the home folder, not here: run every command below from `~/Tabularium`.
The person may not be technical: plain words, one step at a time, nothing about how the tools are
built. They did not read this file and need not.

1. **The release.** The folder may have waited since it was copied. `git fetch --tags origin` asks
   the public copy for newer releases; if it fails: go on with what is here, and say so at step 5. Then
   check out the newest: `git checkout "$(git tag --list 'v*' --sort=-v:refname | head -n 1)"`;
   `git describe --tags --exact-match` names it.
2. **The Mac.** `bash checks/setup-mac.sh` changes nothing and reports the Mac. Its `note:` lines go
   into the reply at step 5, without pausing for an answer. Something `MISSING`: say what and why,
   and ask once before installing it. An `in Terminal:` line needs a password or Apple's dialog: run
   it in the app's Terminal panel, say what they will see, wait, then run the check again.
   - A `restart:` line: ask them to quit the Claude app completely, open it again and reply, then run
     the step again. Back again: hand over to a new session in the folder, as in step 5. Back in that
     one too: stop, and say the tools are installed but the app cannot find them yet, so this step
     waits for someone who knows the Mac.
3. **Routine steps.** `bash checks/setup-mac.sh pre-approve`. The checks, snapshots and filing tools
   then run without asking; everything else still asks.
4. Open the folder in Finder.
5. **Move into the folder, before asking about anyone.** Records change only in a session in that
   folder with the worktree option off, and a session opened elsewhere has not loaded the care
   contract. Moving takes a tool that changes this session's folder. With one: call it on that
   folder, then end the turn with one plain line asking them to reply to go on, since the move takes
   effect when the turn ends; read `CLAUDE.md` first thing in the next turn. Without one, this
   session cannot move: give a ready prompt for a new session there, say to open it with the
   worktree option off, and stop. Either way, that reply also gives step 2's `note:` lines in plain
   words, and how later visits go: each time, a new session in the Code tab opened on the Tabularium
   folder in their home folder, worktree option off, then say what they need.
6. **The first person.** Follow `_templates/INTAKE.md` from section 1. Right after their folder
   exists: `bash checks/install-instance.sh care <the release from step 1>`, then
   `bash checks/check.sh`. A care declaration over a tree with no records reds the board, which is
   why it waits until now. Its warnings about things this person does not need are not problems; say
   what matters in plain words.
