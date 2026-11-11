# Session operational note — environment-performed steps

This session has file tools only (no shell). The environment performs, outside the session,
**exactly these steps**: the guard preflight (`checks/check.sh`); the pre-edit snapshot (the copy
is taken outside this tree, so no `.snapshots/` folder exists here — do not look for one); the hash rule's SHA-256 command, run on the handout file at `HANDOUT_PATH`
and on that handle's `profile.md` and `medications.md` before this session began; and the closing
guard check. (This prose does not define execution order — the profile manifest does.) The hash
command's digest fields, extracted and validated as 64 lowercase hexadecimal characters, are:

- handout: {{HANDOUT_SHA256}}
- profile.md: {{PROFILE_SHA256}}
- medications.md: {{MEDICATIONS_SHA256}}

Treat these enumerated steps as performed on your behalf: use each digest wherever the hash rule
asks for that file's SHA-256, do not attempt the steps, and do not treat their absence from your
own actions as a failure. The profile digest also serves the re-hash the standing prompt asks for
before the first original or page image: nothing changes the profile during this session. **No
other step is delegated.**

Nothing else is modified: every other obligation of the standing prompt and of the operating
contract applies in full.
