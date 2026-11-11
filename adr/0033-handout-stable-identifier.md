# ADR-0033 — Handout stable identifier (`TAB-<PPP>-<NNN><C>`)

- **Status:** Accepted 2026-07-05
- **Date:** 2026-07-05
- **Deciders:** operator (+ assistant; design red-teamed by an independent Opus subagent)
- **Migrated under ADR-0061: 2026-11-01** (source revision `ba2851d`; the amendment history is in
  git).

## Context

The operator wanted stable, sortable, human-usable IDs for families managing many handouts, without
a database. The ID is read aloud (a family member to a receptionist, the operator on a call), and it
prints on documents handed to third-party clinicians, inside the disclosure threat model (identity
and clinical fingerprint, ADR-0013).

## Decision

What holds now: the L8 row of `checks/README.md`, `tools/handout_attest/`, the renderer in
`_templates/handout-assets/`, `_templates/HANDOUT-RULES.md` (*Header, identity and footer*;
*Filing, sealing and the register*) and `_templates/HANDOUT-SOP.md` (*IDs*).

1. **Grammar: `TAB-<PPP>-<NNN><C>[.rREV]`** (2026-07-05), printed in the footer and usable in the
   filename and `INDEX.md`. `<PPP>` is an opaque per-person tag of three Crockford base-32 symbols,
   assigned once and recorded in the person's `profile.md`, never the handle, initials or date of
   birth. `<NNN>` is a per-person, zero-padded sequence owned by the person's `INDEX.md` (next =
   highest + 1), race-free with no central database because `INDEX.md` is the sole writer inside a
   single-person session. `<C>` is a check character (point 2). `.rREV` marks only a re-issue of the
   same handout (a typo or content correction); a new handout, a delta included, gets a new `<NNN>`,
   and a pure re-render changes nothing.

2. **Check-character algorithm** (fixed 2026-07-06, undefined before; guard L8's `tab_checkchar`
   is the reference implementation). Alphabet A = `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (index =
   value); over the six symbols `<PPP><NNN>`, weights w = 1 3 5 7 9 11 left to right:
   **C = A[ ( Σ value(char_i) · w_i ) mod 32 ]**. Worked values: `AAA001` → `5` (sum 101),
   `AAA014` → `F`, `BBB007` → `G`. Every weight is odd, a unit mod 32, so every single-symbol
   substitution changes the character. An adjacent transposition is missed when the two values
   differ by exactly 16 (`0`↔`G`), a limit of one check symbol over a composite modulus. The gap is
   accepted: the character is a read-aloud aid, not integrity crypto, and with an opaque `<PPP>`
   most real errors are single-symbol.

3. **Privacy (load-bearing)** (2026-07-05). The ID encodes only tag, sequence and check character:
   no handle, name, initials, date of birth, audience, specialty or condition. The `<PPP>`↔person
   map lives only in the local `profile.md`, so the printed ID is inert in the wild and needs no
   firewall entry.

4. **A forward-only rollout** (2026-07-06). The filename segment is optional in L8 (grandfathered,
   as ADR-0026 did) and checked when present; `INDEX.md` leads with an `ID` column and gains a
   `Supersedes` column. Historical files are never renamed: they are listed in `INDEX.md` only, a
   grade-C bookkeeping act noted in its header so a gap is not read as a lost document. A person's
   `<PPP>` was assigned only when the operator took that person live; the trigger fired 2026-07-26.

5. **One identity line; bold grades, plain references** (operator, 2026-07-05). The header's
   identity and occasion lines merge into one `.identity` line, whose occasion date is distinct from
   the footer's preparation date; grades render bold (`**[A]**`), references plain (`[1]`). Since
   2026-09-20 handouts use upright faces only.

6. **No INDEX/ID coherence guard: the unbuilt L14 proposal is retired** (2026-09-20, in a
   simplification pass the operator delegated). L14 (INDEX/ID coherence; renumbered from L12 on
   2026-07-11) was gated on real ID use and declared ready
   when IDs went live on 2026-07-26. Another cross-file guard is not justified merely because IDs
   are in use: manual INDEX discipline, L8 and L15 remain, and no L14 code ever ran, so nothing
   implemented is withdrawn.

7. **The footer ID and the filename ID agree** (2026-09-20). Before output, the renderer refuses a
   Markdown whose recognized trailing stable ID disagrees with its front-matter `id`; L8 owns ID
   validity, and unmarked legacy filenames remain accepted.

8. **The check character is checked where the ID is written** (2026-10-02). A care session drafting
   outside the handout lane could neither learn nor check a character, since L8 read only filenames
   and the draft renderer ignored the front-matter `id:` (handover 50, finding 1): it renamed staged
   copies to learn three, reddening the board, and a deliberately wrong one stayed green. From
   2026-10-02 a Python twin of point 2 served a read-only `next-id` command, and the renderer (B0,
   at draft and seal) and L8 (in unsealed units, until 2026-11-01, below) applied one rule: a
   front-matter `id:` holding `TAB` in any case or a non-ASCII character must be a clean, valid ID.
   **Sealed units and the frozen legacy lane are not checked:** their bytes are immutable, so a red
   would have no fix and leave the board red for good, a notice with no answer that trains dismissal
   (as would a loud note on every run). The point of harm is the seal, which refuses a bad ID first.
   Admission (`guard-admission`): a wrong character on a handed-over document is the failure the
   character exists to catch, and cannot be corrected once sealed; the check blocks no reading, acts
   before the fact-check binds the bytes, and asks one thing, "correct it, or take one from
   next-id"; no new guard, only L8 and B0 extended.
   - **L8 stops reading the front matter** (operator, 2026-11-01, a simplification scan). L8's bash
     port of the renderer's front-matter parser and its check of unsealed encounter units are
     removed: the renderer's B0 halt is the one check of a front-matter `id:`, refusing a malformed
     or wrong one at draft and at seal, before the fact-check gate, and the handout procedure
     requires a clean draft render before a draft moves into its encounter dir, the only place L8
     looked. Lost: an earlier board red for an ID edited after the draft render; the seal then
     halts, and the fact-check reruns once. L8 keeps the filename checks and `tab_checkchar`, still
     cross-tested with `handout_id.py`.

## Alternatives considered

- **A global sequence:** with no coordinator it races, and it leaks family-wide volume and tenure
  onto a third-party document.
- **A random-only code:** not sortable, with no "next one" and no evidence of a gap.
- **Encoding the handle or initials:** re-identifying (cf. ADR-0028, where a handle was a common
  first name).
- **mod-37, the true Crockford check symbols** (rejected 2026-07-06): it emits `* ~ $ = %`, which
  cannot be spoken and lie outside the ID's 32-symbol set.
- **Guard L14** (retired, point 6); **checking sealed units or the legacy lane** (rejected,
  point 8).

## Consequences

- IDs are collision-free with no coordinator and short enough to speak (12 characters before a
  revision suffix).
- Exact INDEX registration and per-person uniqueness rest on manual discipline.
