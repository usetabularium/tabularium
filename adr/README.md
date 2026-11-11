# Architecture Decision Records (ADRs)

Why a decision was made, when, and what it traded off — so we don't relitigate settled choices or
lose the rationale. Write an ADR when a change **picks one of several plausible approaches, creates
a workflow boundary, defines a convention others rely on, or records a constraint/workaround**, if it
also meets *Essentials only*, below. Not for routine content edits (those live in each doc's change
log).

**Format and lifecycle (ADR-0061).** One decision per ADR, kept short: Context, Decision,
Alternatives considered and Consequences, with the dated operator rulings it rests on. A Proposed
ADR may be edited until Accepted or Rejected. An Accepted ADR may later be Deprecated or Superseded,
wholly or in part, by a named ADR. Accepted substance is fixed: a changed decision gets a new ADR
that names what it supersedes, and this index shows the chain. In place, only the Status line (with
its index line), links, typos and pointers change, plus each existing ADR's one-time migration under
ADR-0061. Operating detail lives in its owning doc, and its history in git and the pull request.
Selftest section numbers and test counts written before 2026-10-04 refer to the suite as it was then.
The bodies as they stood before the first trim are at `4a419ec`.
Commit and blob hashes, tags, run roots (`tab-eval-…`), pull request numbers,
`ROADMAP`, dated amendments and "in git" refer to development history or development-only
artifacts, which a published copy does not carry; they record provenance and cannot be followed
there. Development-only, not shipped: `checks/PUBLISH-HOLD`, `tools/session_counts/`,
`evals/local-masking/`, the held-out eval cases.
Template: `adr/_template.md`.

**Essentials only.** Write an ADR only for a decision that is costly to reverse or surprising without
context. It records the decision as decided (a Proposed ADR: as proposed, with the open questions that
settle it): the rule, why, what it replaces, each rejected option in one line, and its costs in
general terms. Keep a line only if a reader needs it to apply or revisit the decision. Evidence (test
and break-test results, counts, review findings), guard-admission answers, the specifics of accepted
residuals, and facts another doc owns go to the pull request, the owning doc or the local risk
register. Aim for 40 lines or fewer.

> This register is part of the publishable skeleton (no PII). Every decision has its own
> `adr/NNNN-title.md` file holding its reasoning and status; the list below is only an index to
> them. A new decision takes the next free number, starts from the template and adds its line here
> in the same change. The status column records lifecycle states and their dates and shows each
> supersession from both ends (ADR-0061 points 4 and 5).

## Index

| # | Decision | Status |
|---|---|---|
| 0001 | [Three-layer model](0001-three-layer-model.md) | Accepted by 2026-06-07; superseded in part by ADR-0039 2026-07-17 |
| 0002 | [Person separation is the #1 rule](0002-person-separation.md) | Accepted by 2026-06-07 |
| 0003 | [`patients/<handle>/` layout](0003-patients-handle-layout.md) | Accepted by 2026-06-07 |
| 0004 | [Executable safeguards](0004-executable-safeguards.md) | Accepted by 2026-06-07; superseded in part by ADR-0042 2026-07-26 |
| 0005 | [Evidence grades A–D, ⟨confirm⟩ and operator facts](0005-evidence-grades.md) | Accepted by 2026-06-07 |
| 0006 | [Two-tier citation verification](0006-two-tier-citation-verification.md) | Accepted by 2026-06-07 |
| 0007 | [Abstract `CLAUDE.md`, local roster and PII firewall](0007-abstract-keystone-roster-firewall.md) | Accepted by 2026-06-07 |
| 0008 | [Per-person handout language](0008-per-person-handout-language.md) | Accepted by 2026-06-07 |
| 0009 | [Medical peer persona](0009-medical-peer-persona.md) | Accepted by 2026-06-07; superseded in part by ADR-0050 2026-10-27 |
| 0010 | [Ingested third-party analyses are grade C](0010-third-party-analyses-grade-c.md) | Accepted by 2026-06-07 |
| 0011 | [Central handout spec](0011-central-handout-spec.md) | Accepted by 2026-06-07 |
| 0012 | [Scripted, firewalled GitHub publish](0012-scripted-firewalled-publish.md) | Accepted by 2026-06-07; superseded in part by ADR-0050 2026-09-06 and by ADR-0066 2026-11-07 |
| 0013 | [Publish firewall covers the clinical fingerprint](0013-publish-firewall-clinical-fingerprint.md) | Accepted by 2026-06-07; superseded in part by ADR-0050 2026-09-06, by ADR-0051 2026-09-07, by ADR-0035 2026-11-06 and by ADR-0072 2026-11-08 |
| 0014 | [Per-condition whitelist that grows with casework](0014-per-condition-whitelist.md) | Accepted by 2026-06-09 |
| 0015 | [Project renamed to `tabularium`](0015-rename-to-tabularium.md) | Accepted by 2026-06-09 |
| 0016 | [Top-level README, `docs/` unpublished, public flip held](0016-readme-docs-unpublished-flip-held.md) | Accepted by 2026-06-09; point 3 deprecated 2026-11-08 |
| 0017 | [Go local-only](0017-local-only.md) | Accepted by 2026-06-09; superseded in part by ADR-0050 2026-09-06 and by ADR-0066 2026-11-07 |
| 0018 | [An explicit revisit trigger for guard L3](0018-l3-revisit-trigger.md) | Superseded by ADR-0047 2026-08-16 (accepted 2026-06-13) |
| 0019 | [Numbered, append-only handover prompts](0019-numbered-handover-prompts.md) | Accepted 2026-06-13; retired 2026-10-04; superseded in part by ADR-0030 2026-10-24 |
| 0020 | [Host-portable guard scripts](0020-host-portable-guards.md) | Accepted 2026-06-13 |
| 0021 | [Guards fail closed and carry provenance](0021-guards-fail-closed-with-provenance.md) | Accepted 2026-06-13 |
| 0022 | [Executable pre-commit enforcement of the guards](0022-pre-commit-enforcement.md) | Accepted 2026-06-13; supersedes ADR-0054 point 7 2026-09-27 |
| 0023 | [Source-scan ingestion: vision-primary OCR](0023-ocr-ingestion-pipeline.md) | Accepted 2026-06-21 |
| 0024 | [CC handover routine for sandbox-limited tasks](0024-cc-handover-routine.md) | Deprecated 2026-10-11 (accepted 2026-06-21) |
| 0025 | [Single-source calendar for moving dates (guard L7)](0025-moving-date-calendar-and-guard.md) | Accepted 2026-06-23; calendar block replaced by the open-items table 2026-10-04 |
| 0026 | [Patient-handout voice and canonical handout format](0026-handout-voice-and-format.md) | Accepted 2026-06-23 |
| 0027 | [Consent-gated sensitive attributes](0027-consent-gated-sensitive-attributes.md) | Accepted 2026-07-04; guard L9 retired 2026-09-06; point 3 superseded in part by ADR-0072 2026-11-08 |
| 0028 | [L5 evidence-layer exemption](0028-L5-evidence-layer-exemption.md) | Accepted 2026-07-04 |
| 0029 | [Private mode: an identifier never transits the API](0029-private-mode-local-redaction.md) | Accepted (experimental) 2026-07-04; v2 record half accepted 2026-09-30, frozen 2026-10-04, unfrozen for real persons 2026-10-28; v2 masking half proposed 2026-09-30, gated and frozen 2026-10-04; superseded in part by ADR-0062 2026-11-05 (point 7's fixed residue shape); point 13.2 superseded in part by ADR-0068 2026-11-07 and by ADR-0072 2026-11-08; points 13.1–13.3 superseded in part by ADR-0075 2026-11-09 |
| 0030 | [Transient-helper lifecycle; substrate retired](0030-inbox-archive-lifecycle-and-substrate-retirement.md) | Accepted 2026-07-05; DEV helper lifecycle retired 2026-10-04; DEV `_inbox/` lane retired 2026-10-24; CARE's top-level `_inbox/` removed 2026-10-25; supersedes ADR-0019 in part 2026-10-24; point 3's roadmap clause deprecated 2026-11-08 |
| 0031 | [Change-control tiers](0031-change-control-tiers.md) | Accepted 2026-07-05; PR/CI rejection reversed for DEV 2026-09-06 (CI) and 2026-09-07 (pull requests); `Red-team:` trailer retired 2026-10-24 |
| 0032 | [Handout visual style](0032-handout-visual-style.md) | Accepted 2026-07-05 |
| 0033 | [Handout stable identifier](0033-handout-stable-identifier.md) | Accepted 2026-07-05 |
| 0034 | [Handout fact-check gate, non-LLM build-QA and plaintext fallback](0034-fact-check-gate-and-build-qa.md) | Accepted 2026-07-05; superseded in part by ADR-0064 2026-11-07 (points 1 and 6), ADR-0069 2026-11-07 (point 9's private-mode exception) and ADR-0070 2026-11-07 (point 2's control block) |
| 0035 | [License: Apache-2.0](0035-license-apache-2.0.md) | Accepted 2026-07-07; supersedes ADR-0013 in part 2026-11-06 |
| 0036 | [Concurrent-threads working-tree safety](0036-concurrent-threads-working-tree-safety.md) | Accepted 2026-07-08; D3 (guard L12) retired 2026-09-06 |
| 0037 | [Person-ownership binding](0037-person-ownership-binding.md) | Accepted 2026-07-11 |
| 0038 | [Synthetic selftest fixtures](0038-selftest-synthetic-fixtures.md) | Accepted 2026-07-11; superseded in part by ADR-0050 (2026-09-06) |
| 0039 | [Sealed handout units and attestation (guard L15)](0039-sealed-handout-units-attestation-l15.md) | Accepted 2026-07-17; supersedes ADR-0001 in part 2026-07-17; superseded in part by ADR-0070 2026-11-07 (point 3, the control block) |
| 0040 | [Worktree retirement protocol](0040-worktree-retirement-protocol.md) | Accepted 2026-07-19; recursive removal reversed 2026-07-26 |
| 0041 | [Interview capture: on-screen answers filed word for word](0041-interview-capture-mechanism.md) | Accepted 2026-07-23; revised decision accepted 2026-10-19 |
| 0042 | [Private recovery and patient-root discovery](0042-private-recovery-and-discovery-boundaries.md) | Accepted 2026-07-26; independent validation of pre-edit snapshots dropped 2026-10-27; supersedes ADR-0004 in part 2026-07-26 |
| 0043 | [Local orientation site](0043-local-orientation-site.md) | Superseded by ADR-0051 2026-09-07 (accepted 2026-07-30) |
| 0044 | [Template-owned blocks (guard L16)](0044-template-owned-blocks-l16.md) | Accepted 2026-07-29; guard L16 retired 2026-10-04 |
| 0045 | [Off-machine mirror (backup layer 3)](0045-offsite-mirror-backup-layer-3.md) | Accepted 2026-08-01; superseded in part by ADR-0067 2026-11-07 |
| 0046 | [Firewall token classes at session and commit time (guard L18)](0046-precommit-firewall-surface-guard.md) | Accepted 2026-08-09; superseded by ADR-0050 2026-09-06 |
| 0047 | [Guard L3: literature-value qualifier](0047-guard-l3-literature-value-qualifier.md) | Accepted 2026-08-16; supersedes ADR-0018; guard L3 retired 2026-10-04 |
| 0048 | [L4 closed-world citation membership](0048-l4-closed-world-citation-membership.md) | Accepted 2026-08-16 |
| 0049 | [Behavioral compatibility eval](0049-behavioral-compatibility-eval.md) | Accepted 2026-08-30; supersedes ADR-0050 point 11 2026-09-07; a clause of point 20 superseded by ADR-0067 2026-11-07; a clause of point 5 superseded by ADR-0072 2026-11-08 |
| 0050 | [Two instances: development and care](0050-two-instance-split.md) | Accepted 2026-09-06; point 11 superseded by ADR-0049 2026-09-07; supersedes ADR-0046, and ADR-0012, ADR-0013, ADR-0017 and ADR-0038 in part, 2026-09-06, and ADR-0009 in part 2026-10-27; point 4 superseded in part by ADR-0066 2026-11-07; point 9 superseded in part by ADR-0068 2026-11-07; point 4's flip hold deprecated 2026-11-08; point 17 superseded in part by ADR-0071 2026-11-08; point 8 superseded in part by ADR-0072 2026-11-08 |
| 0051 | [Human orientation moves to the website](0051-orientation-moves-to-the-website.md) | Accepted 2026-09-07; supersedes ADR-0043, and ADR-0013 in part |
| 0052 | [Export-list freshness (guard L21)](0052-export-list-freshness-l21.md) | Accepted 2026-09-08; guard L21 retired 2026-09-27 |
| 0053 | [Session kinds and the `/architect` declaration](0053-session-kinds-and-the-architect-command.md) | Accepted 2026-09-08 |
| 0054 | [Versioning and releases](0054-versioning-and-releases.md) | Accepted 2026-09-13; point 7 superseded by ADR-0022 2026-09-27; point 6 superseded in part by ADR-0066 2026-11-07; point 5 superseded in part by ADR-0065 2026-11-08 |
| 0055 | [Release adoption as one recoverable operation](0055-release-adoption-as-one-operation.md) | Accepted in part 2026-10-11; companion release notice accepted 2026-10-25 |
| 0056 | [Durable specifications with selective retrieval](0056-durable-specifications-and-selective-retrieval.md) | Proposed 2026-09-12 |
| 0057 | [A portable core with small agent-host adapters](0057-portable-core-and-host-adapters.md) | Proposed 2026-09-12 |
| 0058 | [Local handout HTML preview](0058-local-handout-html-preview.md) | Accepted 2026-09-12 |
| 0059 | [Maintained quality-control register](0059-maintained-quality-control-register.md) | Accepted 2026-09-19; register retired 2026-10-04 |
| 0060 | [Longitudinal eval: does a maintained record beat one session over the raw history?](0060-longitudinal-history-eval.md) | Proposed 2026-10-01 |
| 0061 | [ADR format and lifecycle](0061-adr-format-and-lifecycle.md) | Accepted 2026-11-01 |
| 0062 | [Private mode names each person's number from a shared list of schemes](0062-private-mode-number-schemes.md) | Accepted 2026-11-05; supersedes in part ADR-0029 point 7 (fixed residue shape); superseded in part by ADR-0073 2026-11-08 and by ADR-0074 2026-11-09 |
| 0064 | [The handout verifier opens cited product information](0064-verifier-opens-product-information.md) | Accepted 2026-11-07; supersedes ADR-0034 in part 2026-11-07 |
| 0065 | [1.0.0 waits for a settled contract, not the public flip](0065-one-zero-waits-for-a-settled-contract.md) | Accepted 2026-11-08; supersedes in part ADR-0054 point 5 |
| 0066 | [A public release is built from its tag and appended to the public copy](0066-public-releases-from-tags.md) | Accepted 2026-11-07; supersedes in part ADR-0012, ADR-0017, ADR-0050 and ADR-0054 2026-11-07 |
| 0067 | [The off-machine backup takes any folder off this Mac's disk, refreshed at the operator's pace](0067-offsite-backup-any-folder.md) | Accepted 2026-11-07; supersedes in part ADR-0045 (its end-to-end-encryption condition, points 5 and 7) and ADR-0049 |
| 0068 | [Private mode on a care-only install: no token files, no typed number, a form for v2](0068-private-mode-on-a-care-only-install.md) | Accepted 2026-11-07; supersedes in part ADR-0050 point 9 and ADR-0029 point 13.2; point 2 superseded in part by ADR-0074 2026-11-09; point 3 superseded in part by ADR-0075 2026-11-09 |
| 0069 | [The handout verifier opens a private-mode person's filed masked pages](0069-verifier-opens-masked-pages.md) | Accepted 2026-11-07; supersedes ADR-0034 in part (point 9); point 2 superseded in part by ADR-0075 2026-11-09 |
| 0070 | [A fact-check pass expires when the record changes](0070-verifier-pass-binds-the-record.md) | Accepted 2026-11-07; supersedes ADR-0034 and ADR-0039 in part |
| 0071 | [Outside the main care folder: answer in full, send only the write to Claude Code](0071-answer-anywhere-write-in-claude-code.md) | Accepted 2026-11-08; supersedes in part ADR-0050 point 17 |
| 0072 | [The relay scan matches personal details; nothing crosses word for word](0072-relay-scan-matches-personal-details.md) | Accepted 2026-11-08; supersedes in part ADR-0050 point 8, ADR-0013 points 5 and 6, ADR-0027 point 3, ADR-0029 point 9 and ADR-0049 point 5 |
| 0073 | [Private mode reads its number tag strictly, before a second number ships](0073-private-mode-new-numbers.md) | Accepted 2026-11-08; supersedes in part ADR-0062 points 2 and 4; point 2 superseded in part by ADR-0076 2026-11-10; points 1 and 2 superseded in part by ADR-0077 2026-11-10 |
| 0074 | [Private mode learns a number with no date inside from a page](0074-private-mode-known-number.md) | Accepted 2026-11-09; supersedes in part ADR-0068 point 2 and ADR-0062 point 5 |
| 0075 | [One private mode: the identity file says what else is kept](0075-one-private-mode.md) | Accepted 2026-11-09; supersedes in part ADR-0029 points 13.1–13.3, ADR-0068 point 3 and ADR-0069 point 2 |
| 0076 | [A number private mode cannot mask yet is covered by hand, not waited for](0076-unlisted-number-covered-by-hand.md) | Accepted 2026-11-10; supersedes in part ADR-0073 point 2; point 2 superseded in part by ADR-0077 2026-11-10 |
| 0077 | [Private mode decides by the exact tag alone: an unlisted number is a key, no tag searches every row](0077-private-mode-exact-tokens-only.md) | Accepted 2026-11-10; supersedes in part ADR-0073 points 1 and 2 and ADR-0076 point 2 |
