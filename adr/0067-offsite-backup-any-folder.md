# ADR-0067 — The off-machine backup takes any folder off this Mac's disk, refreshed at the operator's pace

- **Status:** Accepted 2026-11-07 (operator)
- **Date:** 2026-11-07
- **Deciders:** operator (+ assistant)

## Context

ADR-0045 sent the records' off-machine copy only to an end-to-end-encrypted cloud drive, and
`contributing/instances.md` and ADR-0049 point 20 stated the same as a rule: an end-to-end-encrypted
provider only. A likely public user is a non-technical caregiver, offered a backup once at the end of
the first intake. Most such users cannot judge a provider's encryption, and a condition they cannot
check can leave them with every copy on one disk, where a dead Mac loses scans nothing can regenerate.

## Decision

The off-machine backup accepts any folder the operator chooses: an external drive or a cloud folder of
any provider (operator, 2026-11-07). No Tabularium text tells an operator that a provider must encrypt
end to end. The offer reads: "Would you like a backup off this Mac, on an external drive or in a cloud
folder of your choice? No is fine; the recovery copies on this Mac keep running."

Two more rules came out of the pull request's review the same day (operator, 2026-11-07):

1. **Off this Mac's disk.** The backup refuses a folder on the records' own disk unless it sits in the
   area where macOS's cloud apps keep the folders they sync (`~/Library/CloudStorage/`,
   `~/Library/Mobile Documents/`). The intake's session places the marker at setup, so the marker now
   means "this folder, on purpose" and the disk test means "off this disk".
2. **Refreshed at the operator's pace.** After the first verified copy, the intake asks once how often
   it should refresh: each time they work here, once a week, or only when they ask. The answer is the
   second line of `checks/OFFSITE-DEST`, and `checks/snapshot.sh`, run at the start of every editing
   session, refreshes the copy when it is due. A copy that cannot run leaves the snapshot standing and
   costs it one note.

This supersedes the end-to-end-encryption condition in ADR-0045's Decision and its point 7, the
end-to-end-encryption clause of ADR-0049 point 20, and, in part, ADR-0045 point 5: the marker is no
longer put there by hand. The rest of ADR-0045 stands: a copy target, both roots wholesale,
append-only, the destination as configuration, the marker as a gate on every run, verification, the
one sanctioned egress.

## Alternatives considered

- **Keep the rule, say it only when someone picks a cloud folder.** The session's recommendation: the
  offer stays one line and records stay end-to-end encrypted. The operator chose otherwise on
  2026-11-07.
- **Keep the rule, inside the one line.** Longer and technical for someone who will say no anyway.
- **For the refresh: the snapshot always running it, or a closing step in every session.** The first
  copies each session whether wanted or not; the second needs a care-contract line. The operator chose
  a pace asked once.
- **For the disk: the person making the marker by hand, or the session judging the folder in words.**
  Neither stops a folder beside the records from passing.

## Consequences

- A provider that does not encrypt end to end can read the copy, and a breach of that provider or
  account exposes it. A lost unencrypted drive gives it away. Nothing warns about either; `checks/topics/backups.md`
  and `checks/backup-offsite.sh` state them as facts for anyone who reads them.
- Fewer caregivers should be left with one copy on one machine. That is the aim, not a measurement.
- The marker, the disk test and the verification stop a backup that never left the disk from reporting
  success. A cloud app that still syncs from a folder outside its macOS area is refused, and the person
  picks that app's folder in the area, or a drive. A cloud folder whose app is paused still passes, and
  so does a second volume or a disk image kept on the Mac's own drive: the test compares file systems,
  not physical disks, and a caregiver rarely makes either.
- A weekly or per-session refresh makes the snapshot slower while the copy runs, and a drive left
  unplugged costs a note at each due snapshot. A per-session refresh copies at the start of a session,
  so that session's new scans leave the Mac at the next one.
- The refresh runs without a prompt, because snapshots are pre-approved; the person agreed to it once,
  when asked how often.
