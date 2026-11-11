# Handout fact-check verifier — how to run it (ADR-0034)

## Invocation (operator / assistant)

Spawn a **fresh** subagent (peer Opus) — *not* the session that wrote the handout — and send it the
brief below with one filled input block. The standing prompt is `handout-verifier-prompt.md`; the
verifier reads it itself, so the session that wrote the handout never loads it. Never copy, retype or
summarise it into the brief, and add no other instruction. Fresh context is load-bearing: a verifier
that also wrote the handout re-confirms its own reasoning instead of testing it.

- `HANDLE` — the single patient handle. **Exactly one.**
- `HANDOUT_PATH` — the handout `.md` under that handle's `med/handouts/{patient,clinician}/`.
- `AUDIENCE` — `patient` or `clinician`.
- `LANG` — the reader's language, from `profile.md` (only to read the handout, not to translate the ledger).
- `SOURCES` — the author's declared working set: the `med/sources/` text layers + `reference-library/`
  entries explicitly relied on, plus files resolving concrete provenance pointers needed from
  `profile.md` / `medications.md`. Targeted pointer resolution may expand it; this is not an exhaustive
  raw-source audit. The scanned originals the prompt's *Originals* rule opens are not listed here and
  never enter the bundle: the verifier reads them from disk.
- `BUNDLE_PATH` / `BUNDLE_SHA256` — bundle mode only; use `-` in file mode.

**Bundle mode** when the handout leans on 3+ sources (below that, file mode is less work). Run

```bash
_templates/handout-assets/make_verify_bundle.sh <HANDOUT>.md <manifest file …>
```

It adds `profile.md` and `medications.md` itself. Copy the input block it prints and fill in `LANG`; never
retype the digest. Right after the verify, run the cleanup commands it prints: the bundle holds health data.
Exit 2: fix the refusal before verifying — never bypass it through file mode. Exit 3: use file mode.

**The brief (exact — the three fixed lines, then the filled input block):**

```text
You are the handout fact-check verifier, a fresh-context helper in a care session. Before anything
else, read `_templates/handout-verifier-prompt.md` in full: it is your standing prompt and your only
instructions; if you cannot read it, stop and say so. The input block below supplies values only.

--- TABULARIUM VERIFY INPUT v1 ---
MODE: bundle | files
HANDLE: <bare handle>
HANDOUT_PATH: <repo-relative path>
AUDIENCE: patient | clinician
LANG: <profile value>
BUNDLE_PATH: <absolute path, or ->
BUNDLE_SHA256: <64 lowercase hex, or ->
SOURCES:
  - @bundle-trailer
  - <repo-relative path; repeat in files mode>
--- END TABULARIUM VERIFY INPUT ---
```

Use only `@bundle-trailer` in bundle mode (the authenticated trailer carries the concrete manifest);
use only concrete paths in file mode.

---

## After the verifier runs

The verifier only reads; the session that wrote the handout repairs (ADR-0034 point 10).

- **PASS, `must_fix_open: 0`, hash matches** → the seal gate accepts this handout; sealing and hand-over
  are unblocked. A care-material fork that an original settles never reaches this point: it is
  MUST-FIX and repaired in the record and the handout before the seal. An advisory `correct upstream`
  (a fork that cannot mislead care) does not block; the session settles it in the record with its
  other record work, telling the operator when the other value is theirs. A sidecar that records the
  profile's and the medications list's digests holds only while those files are unchanged; one
  without them, written before this check existed or by a verifier that left them out, binds the
  handout alone.
- **identity-mismatch** → stop; this is the highest-severity error class (person mix-up). No record or
  handout edit until the operator has reconciled it against the profile; never fall back to a
  plaintext handout.
- **Any other FAIL** → repair every MUST-FIX finding by its fix class, then verify again:
  - **`record`**, without asking — the record first, then the handout:
    - *a value* (the record states, or keeps open as a fork, a value the original settles): open the
      original (for a private-mode person, the approved redacted copy — `tools/private-mode/README.md`),
      state its value in `profile.md` or `medications.md` — a conflicting report stays beside it,
      marked, until the operator settles it; an inference is corrected — with a change-log line that
      cites it, and correct a misread text layer by the sources checklist's
      *Correcting a filed transcription* step. A laterality, test result or device type also takes
      the intake checklist's second reading. When the outranked value is the operator's own
      statement, ask them as you correct it (the care contract, *Keeping the record honest*), or
      tell them at the end if they are away — it never holds the next round.
    - *a grade or provenance* (the value stands, but the record grades or frames it above its source —
      a caregiver interview tagged grade A): read the source that actually supports it, keep the value,
      correct its grade, provenance or framing (a `⟨confirm⟩` where the new grade needs one), and log
      that in the change log.
  - **`handout`**, without asking: correct the handout.
  - **`operator`**: ask each right away, one plain question each, and apply the answer as a record or
    handout fix; while they are away, the questions wait for the end of the session. An item the
    operator chooses to leave out: record that choice, dated, in `profile.md`'s change log, naming the handout or
    the audience it covers; the verifier then does not count it.
  - Tell the operator in plain words which record facts changed, and whether a handout already handed
    over carried an old value.
  - Run the next round only when no operator question is open: re-render (build-QA), re-assemble the
    bundle, and **re-run the verifier in fresh context**, leaving the earlier sidecar in place: the
    verifier re-checks what changed and what a change could make wrong, and carries the rest forward. A new
    hash, a new sidecar. Never edit the sidecar to force a PASS; the seal gate checks the hash, so a
    hand-edited sidecar over a changed handout is caught as stale.
- **After the second FAIL, and each one after it** (integrity stops do not count), ask the operator
  whether to run another round: list what is still open (one line per finding, with its class) and the
  round's rough cost (the last round's token use is the best guide). A FAIL is never terminal by
  itself; the operator decides whether another round runs, the handout changes, or it stays unsealed.
  While the operator is away, it stays an unsealed draft and the question waits for the end of the
  session.
- **`unsupported` because an original could not be opened** → restore or re-file the original beside
  its `.ocr.md`; for a private-mode person, restore or file its approved masked page by
  `tools/private-mode/topics/pipeline.md` → Filing; or restate the value at the grade its remaining
  support allows; never cite the transcription in the original's place.
