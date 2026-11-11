# Session operational note — environment-performed steps

This session has file tools only (no shell). The environment performs, outside the session,
**exactly these steps**: when the filing procedure applies, the ownership-ledger append it
prescribes (done before this session began); the opening board check (`checks/check.sh`); making
sure no other session is writing records (this session is the only one working in this tree); the
copy before editing (`checks/snapshot.sh` — the copy is taken outside this tree, so no `.snapshots/`
folder exists here — do not look for one); the re-bind of a filed transcription you corrected
(`append … retranscribe`, done after this session ends — the corrected text and its erratum line
are yours, and without that line the re-bind is refused); and the closing board check, whose reds
the environment lists itself. (This prose does not define execution order — the profile manifest does.) Treat these
enumerated steps as performed on your behalf; do not attempt them, and do not treat their absence
from your own actions as a failure. **No other step is delegated.**

Nothing else is modified: every other obligation of the care contract — evidence marks, sources and
dates, one person per session, context, the operator's facts, reconciliation — applies in full.
