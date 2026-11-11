# Backups: the three recovery layers

Read when: you set up or change a backup layer, choose the off-machine folder, or judge what a layer
does and does not protect. The command index is in [checks/README.md](../README.md), and its
*Recovery* section says how to restore.

**Git does not back up patient data.** Every `record` path of `checks/RECORD-SET` (`patients/` and
`_shared/{med,nmed}/` among them) is git-ignored, so git versions the skeleton only. Use these three
layers for the records.

## 1. Snapshots: `.snapshots/` (`snapshot.sh`)

Append-only copies inside this folder, in CARE only.
- A DEV marker, local or inherited from the verified checkout family, refuses before the directory is
  created or either external pointer is resolved; malformed or unverifiable instance metadata refuses
  at the same point. Unmarked legacy and synthetic roots keep the standalone path.
- It captures the **canonical docs** (`profile.md`, `medications.md` and the identity file of a person with kept details,
  `.never-api-identity.json` under the same name; `CLAUDE.md`; `reference-library/*.md` and `*.txt`;
  `_shared/med/*.md`) and **the out-of-tree token registry** as
  `.snapshots/<ts>/external/firewall-registry.sh` (0600, byte-compared like the rest), the only copy
  a suspect class line can be diffed against. `checks/publish-skeleton.sh` is banked too when present.
- Refused: a root with no canonical input, a zero-capture result, a symlinked `.snapshots/` root.
  Each file is byte-compared before the private staging folder is published, and a root
  `.snapshot-complete` marker tells a complete publication from a partial or nested one.
- An out-of-tree file whose **folder** this shell cannot see (a chat's Linux VM that mounts only the
  care folder) is left out with a `note:` line and the records are still copied; a file gone from a
  folder that exists refuses the snapshot. A lock folder the shell may not delete gets a `note:` too.
- It does **not** capture `med/sources/`.

## 2. Tarball: `outputs/_snapshots/<ts>__worktree.tgz` (`backup-tree.sh`)

A whole-tree copy except `.git`, `.snapshots` and `outputs`, so it holds the raw evidence
(`med/sources/` scans: grade A, unregenerable), analysis, handouts and `nmed/`. It is built as a
private partial, validated by reading it back, and published atomically without overwrite; a
symlinked destination is refused. Run it as a habit (there is no daemon, on purpose) and prune old
ones by hand.

## 3. Off-machine mirror (`backup-offsite.sh`)

A one-way, **append-only** copy of `patients/` + `_shared/` into a folder the operator chooses, on an
external drive or synced by a cloud client: the only layer that survives losing the laptop.
- **Set up once:** put the folder's absolute path in `TABULARIUM_OFFSITE_DEST` or the untracked
  `checks/OFFSITE-DEST` (never committed: it names a provider account), then
  `touch .tabularium-offsite-ok` **inside that folder**. Every run refuses without that marker: an
  unmounted or logged-out cloud folder looks like an empty local one, and a copy into it would report
  success while never leaving the machine.
- A folder on the records' own disk is refused unless it sits in macOS's cloud-app area
  (`~/Library/CloudStorage/`, `~/Library/Mobile Documents/`): the marker says "this folder, on
  purpose", not "off this disk".
- **Schedule:** a second line in `checks/OFFSITE-DEST`, `every session` or `every week`, lets
  `snapshot.sh` run the copy when due (by the age of `tabularium/.tabularium-last-backup`, written
  after each verified copy); without it the copy runs only when asked. A copy that cannot run costs the
  snapshot one note, never its own result.
- No `--delete`: a file removed locally stays in the mirror, so a local accident cannot reach the copy
  meant to survive it.
- Each run checks the mirror file by file (every local file at its path with the same size, names
  compared Unicode-normalized, two local names differing only in that form refused, extra mirror files
  ignored, a tree it cannot list a failure), then hash-verifies the evidence layer with the ownership
  verifier (`verify --mirror`: files no current record binds, such as a renamed source's old name, are
  counted, never failed). It refuses to call an incomplete, out-of-date or drifted copy a backup.
  Sizes, not bytes: a same-size change outside `med/sources/` is not caught.
- It writes to a local path only; the provider's client uploads on its own schedule, so "mirror OK"
  means staged and verified, not yet off the machine.
- `--verify-only` writes nothing: a missing mirror is reported, never created. A destination that
  resolves, through any symlinked part, inside the repository or onto a folder holding it is refused.

## Limits shared by the layers

Layers 1 and 2 share the machine's failure domain; only layer 3 leaves it. Re-run the restore drill
([ADR-0045](../../adr/0045-offsite-mirror-backup-layer-3.md#decision)) after any change to the
destination or provider. Only the snapshot flushes its copies to disk; the tarball and the mirror do
not, and all three rely on a prior green L0 to find the tree.

**Layer 3's confidentiality** rests on where the folder is and who can reach it, not on file
permissions, which a provider-mounted filesystem often ignores. A provider that does not encrypt end
to end can read the copy, and a lost unencrypted drive gives it away. With an end-to-end-encrypted
provider it rests on the account: two-factor sign-in and **the recovery phrase stored physically
offline**, without which a password reset makes the archive permanently unreadable.
