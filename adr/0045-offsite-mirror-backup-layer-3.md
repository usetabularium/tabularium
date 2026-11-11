# ADR-0045 — Off-machine mirror of the patient tree (backup layer 3)

- **Status:** Accepted 2026-08-01; superseded in part by ADR-0067 2026-11-07
- **Date:** 2026-08-01
- **Deciders:** operator (+ assistant)
- **Migrated under ADR-0061: 2026-11-01** (source revision `12572a0`; the amendment history is in
  git).

## Context

Every backup lived on one laptop. Layers 1 (`.snapshots/`) and 2 (whole-tree tarballs) defend
against a bad write or a local deletion, not against losing the machine, and local git is no third
layer: the ADR-0017 PII firewall keeps `patients/` and `_shared/{med,nmed}/` out of it. That gap
was the architecture's weakest point: the scans under
`med/sources/` are grade A and unregenerable, so a dead disk, a theft or ransomware takes the
records and every backup. A disk review on 2026-08-01 found eight near-identical tarballs: eight
copies, one failure domain.

## Decision

What holds now: `checks/backup-offsite.sh` (header and comments), `checks/README.md` → *Version
control & backups*, layer 3, `tools/person_ownership` (`verify --mirror`) and the off-machine
mirror bites listed in the `checks/selftest.sh` header.

Add **backup layer 3** (operator, 2026-08-01): `checks/backup-offsite.sh` copies `patients/` and
`_shared/` one way into an operator-configured local folder that an end-to-end-encrypted cloud drive
syncs off the machine. This is the roadmap's option 2 (local primary plus encrypted cloud backup) without
the Cryptomator or rclone-crypt layer it assumed, which an end-to-end-encrypted drive makes redundant.

1. **Copy target, not repository relocation** (2026-08-01). The working tree and its guards stay
   put. The roadmap's hard invariant, *the safety layer must be demonstrated on the selected
   backend, not inferred from a local-looking path*, holds because no safety machinery runs on the
   provider's filesystem.
2. **The two roots wholesale, no include-list** (2026-08-01): exactly the set git cannot back up. A
   curated subpath list silently drops a lane when the layout grows, and this is the only
   off-machine copy of unregenerable evidence.
3. **Append-only: no `rsync --delete`** (2026-08-01), which would forward a local accident to the
   copy meant to survive it. A file removed or renamed locally stays in the mirror until the
   operator removes it there by hand; pruning the mirror is never urgent.
4. **The destination is configuration, never code** (2026-08-01). Its path names the operator's
   provider account (PII) and `checks/` ships, so it comes from `TABULARIUM_OFFSITE_DEST` or the
   untracked `checks/OFFSITE-DEST`, the `checks/PUBLISH-HOLD` sentinel convention.
5. **An operator-placed marker gates every run** (2026-08-01): `.tabularium-offsite-ok`, put inside
   the destination once by hand ("this folder, on purpose"). A provider folder disappears or
   reappears empty when the client is logged out or offline; without the marker the script would
   recreate it on the local disk, mirror into the failure domain it exists to escape, and print
   success.
6. **Verification by the repository's own verifier, with presence checked separately.**
   - **Bytes** (2026-08-01): `tools.person_ownership verify` against the ownership ledger's
     SHA-256s (ADR-0037, L13), run from the repository that owns the script, never from a
     passed-in root (ADR-0039's stance).
   - **Presence, file by file** (2026-10-25), since hashes prove the bytes that are
     there, not that nothing is missing: every local file under the two roots at its path in the
     mirror with the same size, names compared after Unicode NFC normalization. It replaced a file
     count, which the old names an append-only mirror keeps could make up while a new file was
     missing. Sizes, not bytes, so no provider placeholder is downloaded.
   - **Current records only** (operator, 2026-10-31). The live-tree verifier reds every file
     without an active ledger record, so the first backup after a recorded rename failed although
     everything had copied correctly. `verify --mirror` requires every active record's file,
     source and transcription, with its recorded bytes, and only counts a file no active record
     binds; a stray file is caught where it arises, by L13 on the live tree.
7. **Confidentiality rests on the provider and the account, not on file permissions**, which a
   provider-mounted filesystem routinely ignores (operator, 2026-08-01): end-to-end encryption
   plus a strong unique password, 2FA and the recovery phrase stored physically offline. Accepted:
   a compromised provider account is a full breach of the patient tree, and a password reset
   without the recovery phrase leaves the archive permanently unreadable.
8. **The one sanctioned egress** (2026-08-01; re-affirmed 2026-09-06). `CLAUDE.md`'s PII boundary
   ("never leaves this machine") was amended to name it; the publish firewall is a separate
   boundary, untouched. When ADR-0050 moved every backup layer to CARE, design unchanged, the rule
   was re-affirmed: **this remains the single sanctioned egress for record-bearing bytes, and the
   two roots are the only things that may travel it.** No repository archive, bundle, tarball or
   export goes into the mirror folder, whose safety argument is that it holds the mirror and nothing
   else; ADR-0050's review struck its draft's `git archive` there. The pre-split tree is destroyed
   after a verified restore or kept on offline encrypted media, never in a synced folder.
9. **The device-loss gap closed on a restore drill and the recovery phrase** (2026-08-09), since an untested
   backup is not a backup. The full mirror was pulled back through the provider's mount
   into a scratch directory (`rsync -rlt`), passed `tools.person_ownership verify` and a file-count
   match against the local tree, and was deleted. It proves the mirror restorable and byte-correct,
   but cannot tell locally hydrated bytes from provider-side retention. The same day the operator
   confirmed that the recovery phrase is stored offline, the second closure leg.

## Alternatives considered

- **A cloud-synced working tree** (roadmap option 1; rejected for now, 2026-08-01): plaintext to a
  provider that is not end-to-end-encrypted, and a File Provider mount's dehydration, rename and
  permission semantics to re-prove the guards, the pre-commit hook and the worktrees against. More
  risk, for multi-device access nobody asked for.
- **Connector-native storage** (option 3; still rejected, 2026-08-01): it trades the
  filesystem-based safety machinery for convenience.
- **An encrypted archive or Cryptomator vault pushed to the provider** (rejected 2026-08-01): the
  ciphertext of an append-only corpus changes wholesale, so each run re-uploads it all, and a
  second passphrase over an end-to-end-encrypted provider adds a second key-loss single point of failure
  for one operator, against no meaningful added adversary.
- **`rsync --delete`** (rejected, point 3): storage is cheap; the deletion it would propagate is
  not.
- **A raw name-level local-versus-mirror diff** (rejected 2026-08-01, on precedent):
  `backup-tree.sh`'s red-team note records such a diff false-failing on non-ASCII scan names, and a
  "fix" that deleted a good backup; provider filesystems normalize Unicode. The 2026-10-25 check
  compares names only after NFC normalization (point 6).
- **Matching each old copy against the ledger's history** (built, then dropped by the operator,
  2026-10-31): it grew with every review round, for files that no restore depends on.

## Consequences

- **An operator habit, not a guarded invariant:** deliberately no daemon (ADR-0031 point 2), so
  the mirror is only as fresh as the last run.
- **A same-size corruption already in the mirror is not re-copied** (`rsync -rlt` skips a file
  whose size and mtime are unchanged); the ledger's hashes catch it in the evidence layer. Delete
  that file in the mirror and rerun.
- **Not covered:** the checks prove each local file's presence and size and the ledger-bound
  evidence bytes, not that the provider uploaded, kept or durably stores them. An empty mirror and
  an unhydrated provider mount look alike locally, so that case is indeterminate, never green
  (since 2026-09-20).
