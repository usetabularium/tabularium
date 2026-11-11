"""Person-ownership binding (ADR-0037) — deterministic, stdlib-only.

The single source of truth for the ownership manifest schema, hashing, active-view/supersession
evaluation, migration, checkpoint refresh, and verification. `check.sh` L13 calls the `verify`
path fail-closed. NO LLM inference anywhere in the hashing/binding path; metadata only — this
package never renders or reasons over clinical content. The texts it parses are a corrected
transcription's erratum block (`append … retranscribe`, ADR-0037 §13), for shape and date only, and
a transcription's front matter, for the `filed_as:` name of its original (§14).

Regular package (not PEP-420) so `python3 -m unittest tools.person_ownership.test_ownership` and
`python3 -m tools.person_ownership` both resolve, exactly as tools/private-mode does. The published
skeleton ships this directory but not `tools/__init__.py`, so the dotted forms resolve there via
PEP-420 namespace packages — verified for the sibling package (ADR-0029 note)."""
