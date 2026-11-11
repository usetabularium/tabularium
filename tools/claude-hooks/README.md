# tools/claude-hooks — session-side guards for the assistant's own tooling

`registry-read-guard.py` is a Claude Code **PreToolUse** hook (ADR-0050 Part A1 and point 9).
It keeps the **private-mode identifier** (ADR-0029) out of every model session: the file that holds
it, and the recognised reads of a private-mode person's unredacted originals, which carry it. The
identifier lives in its own small owner-only file outside every repository, named by the untracked
pointer `checks/PRIVATE-MODE-ID` (setting it up: `checks/topics/relay-and-export.md`). The rest of
the token registry stops being secret from sessions once the split is verified; until then the
registry and its pointer (`checks/FIREWALL-REGISTRY`) are protected exactly like the private file.

## The rule set — deliberately small

The guards stay a **high-confidence minimum**, grown only when a real need shows up, rather than
keep blocking legitimate, safe work. A call is denied (exit 2, reason on stderr) only when it is
near-certainly a read of a protected file:

- **File tools** (`Read`, `Edit`, `Write`, `MultiEdit`, `NotebookEdit`) on a protected file or its
  pointer — compared by resolved path, case-insensitively and by inode, so a symlink, an APFS case
  variant or a hard link is the same file — or on any file **named** like one (`private-mode-id.sh`,
  `PRIVATE-MODE-ID`, and until the split verifies `firewall-registry.sh`, `FIREWALL-REGISTRY`): a
  snapshot's banked copy is still the file.
- **`Grep`** in content mode over a protected file or its directory (a `!` negation or a `**/` path
  glob does not narrow that away).
- **Shell commands** — `Bash`, `Monitor` and the terminal tool — when a part of the line reads a
  protected file or pointer, however the path is spelled (literally, with `~`, `$HOME` or `$USER`,
  relative, after a `cd`, through one variable assignment, a glob that matches one on disk, a file
  name above, or a protected file's own directory) and wherever it sits (an argument, an
  assignment, any redirection operand, inside `$(…)`, `$(<…)` or backticks, or code a shell or
  interpreter runs: `bash -c '…'`, `eval`, `python3 -c '…'`, `perl -e '…'`, a here-document or
  here-string fed to a shell). **Allowed** when that command is metadata only — `ls`, `stat`, `wc`,
  `du`, `test`, `chmod`, …, `find` without `-exec`, `git` without `--no-index`, `-C` or
  `hash-object` — and nothing in the same part turns the names it prints into reads (`xargs`, a
  loop, a shell, `awk`, `sed`, a `$(…)`): `ls <dir> | head` runs, `ls <dir> | xargs cat` does not. A
  digest tool is never metadata (a one-line file's hash is brute-forceable), nor is `file` (its `-f`
  prints what it reads). Parts are split at `;`, `&&`, `||`, `&` and newlines.

**Data is not judged.** Here-document bodies, a here-string's text, write targets, a grep-family
pattern (`grep -rn 'checks/PRIVATE-MODE-ID' .`), a commit message and a shell comment
(`cat checks/README.md # documents checks/PRIVATE-MODE-ID`) read nothing, so prose and fixtures
that mention these names run. The exceptions are text the shell does run: the `$(…)` and backtick
spans of an unquoted here-document body or a redirection operand; standard input a shell runs as its
script (`bash -s <<'EOF'`, `cat <<'EOF' | sh`, `bash <<<'…'`), judged as if typed; and a body read
by `cat` into `$(…)` (the `-m "$(cat <<'EOF' … EOF)"` idiom), which counts as a path where it is one
and word by word where its part of the line runs a shell, an interpreter or `xargs`. An unterminated
here-document is not stripped, so a missing delimiter never hides the lines after it. The full
grammar — comments, quoting, line joins, nested substitutions — is specified by
`registry-read-guard.py` and its matrix `test_registry_guard.py`.

**Fail closed.** A PreToolUse hook blocks only on exit 2 — any other exit lets the call run. So any
exception while deciding denies when the raw input names a protected file, a pointer or the registry,
and a command that cannot be tokenised is denied when it does.

## A private-mode person's originals (ADR-0029 point 12)

The same hook keeps a **private-mode person's unredacted originals** out of every session. A person
is in scope when their `profile.md` carries the private-mode marker (a profile that exists but cannot
be read counts as marked), or when their folder holds an identity file of kept details — a durable sign
that a rewritten or missing profile line does not erase. Their originals are everything in their `med/_inbox/` and `med/sources/`
except Markdown (the checklist, and transcriptions made only from approved redacted rasters, which
guard L10 scans) and except redacted rasters (`_redacted/`, under `med/sources/` or beside `med/`);
the pipeline's id-to-file-name map, `.never-api-source-map.json`, is never read either, nor a
person's identity file of kept details or its fill-in form — any file whose name ends in
`.never-api-identity.json`, anywhere, existing or not yet (a copy and a read of the copy can share one
line), snapshot copies included, and any existing file whose name holds `never-api-identity`, an
editor's backup or copy of either (ADR-0029 control C1). A word that only mentions that marker names no file. A grep-family search pattern is data, never a file, so
naming a protected path there runs. Why it exists: the keystone's profile-first rule alone does not
stop a session reading a new scan in the same step as the profile, before it sees the marker
(ADR-0029 point 12).

- **Denied** — a read that could hand an original to the model:
  - `Read` of an original; a content-mode `Grep` over one, over a lane, over the person's folder or
    `med/`, or over a `patients/` folder holding a marked person — unless a **positive** glob or the
    `md` type keeps it to Markdown (`!*.md` selects everything else and grants nothing);
  - any tool that is given one and sends it somewhere: a connector (`mcp__…`), `Artifact`,
    `SendUserFile` — `file:` URLs parsed and percent-decoded, whatever their authority;
  - a shell command that could print one: `cat`, `tesseract … stdout`, `pdftotext`, `strings`,
    `base64`, `md5 -p` (it echoes its input), a checksum check (`shasum -c`), a bare input
    redirection (`$(<file)`; zsh pages a lone `<file` to the screen), an interpreter (a `-c`
    string, or a script fed as a here-document), `xargs` or a `while read` loop into a reader, a
    `$(…)` whose result a reader consumes (a backtick substitution is judged exactly as one), a
    conversion that writes to the screen or outside the person's lanes. Paths are followed
    through globs (`**` recursive, as zsh does), `cd`, a variable assigned on the line, a `for` loop's
    variable, symlinks, names with spaces or brackets, and snapshot copies that keep the
    `patients/<handle>/` layout. A case variant is the file only where the filesystem ignores case.
    A line that cannot be parsed is denied when any word in it reaches an original.
- **Allowed** — work that never prints an original's content: listing (`ls`, `find` without `-exec`),
  filing (`cp`, `mv`, `mkdir`, a `for` loop or `find -exec`/`xargs` that runs one of these, a date
  from `$(…)` in a new name), hashing (`shasum`, `md5`, … in hashing mode, through `find -exec` or
  `xargs` too), a local conversion that writes a file into the person's lanes (`magick`/`convert`,
  `img2pdf -o`, `sips --out` — how an image original becomes the PDF the pipeline reads), `open` and
  the host's open-in-editor and reveal tools (the operator's own screen), name-only `Grep`, and the
  redaction pipeline
  (`python3 tools/private-mode/*.py`, wrapped in `nohup`, `time` or `caffeinate` too) and the
  ownership ledger (`python3 -m tools.person_ownership`), which read originals by design and print
  none. A person without the marker is unaffected.
- **Interpreter code** — a `python3 - <<'EOF'` script, a `python3 -c` string, perl, ruby, node,
  osascript — is judged by what names a path there: each string literal whole, and each word that
  holds a `/` (or is the identity file's or the map's name). The words of prose inside a literal are
  no paths, so an edit script whose replacement text says *patients* or carries Markdown bold
  (`**patient**`) runs; a literal without a `/` is a name in the working directory, never a glob
  (`'*' * 40`). `open('<lane>/<file>')`, `os.listdir('patients')`, `os.walk('patients/<person>')`,
  `os.system('cat <path>')` and any name after a `cd` into a lane are still refused. Shell code
  (`bash -c`, `eval`, a script a shell runs) keeps the shell's word-by-word reading (ADR-0029
  point 12).
- **The denial names the rule class that matched**, never the word, the path or the person: a path
  that resolves to an original (or a kept-details final, or a file refused by its name), to a lane, or to a
  folder above one (the person's folder or `med/`, or a `patients/` folder holding a marked person); a
  glob pattern that matches one on disk; or a variable assigned on the line that holds one. A session
  can check its own command against that class without reading anything protected.
- **The handouts of a person with kept details** (ADR-0029 control C1; an identity file in their folder): in their
  `med/handouts/`, a final render — the sealed PDF, or any output other than Markdown, the attestation
  and `*.draft.pdf`/`*.draft.txt` — carries their details, filled in at the seal, and is refused like
  an original (a folder search too, unless a positive glob keeps it to Markdown). The draft shows the
  handle and stays readable; the operator opens the final in their own viewer (`open` runs).

**Refused though harmless:** `ls … | awk …`, `while read … mv` loops, `rg -g '*.md'` over a lane
(use the `Grep` tool with a `*.md` glob), `cmp -s`, an unquoted `$(…)` or backtick substitution
followed by more of its command (`mv <original> labs/$(date +%F)-x.jpg`, `touch -t $(date …)
<original>`: quote it), and an original's path in a `$(…)` or backtick span inside single quotes,
where the shell runs nothing, a search pattern included (write the text to a file; search with
the `Grep` tool);
the identity file's name inside interpreter code, a `sed` script or a `gh … --body` (write a
pull request body to a file and pass `--body-file`).

## Where the protected paths come from

`checks/install-instance.sh` writes them into the hook's own command line — never into the session's
environment, where every Bash command would see them:

```
python3 "$CLAUDE_PROJECT_DIR/tools/claude-hooks/registry-read-guard.py" --private '<abs>' --registry '<abs>' [--split-verified]
```

`--split-verified` is written only when the installer verified the split, content-blind; what it
checks is in the installer's header (*private id*), and the operator's setup steps are in
`checks/topics/relay-and-export.md`. In a linked worktree the installer reads the main checkout's
pointers, so the worktree's settings name the family's files. A worktree session needs no copy of
its own: Claude Code reads its settings from the main checkout, and the desktop app copies the main
checkout's `.claude/` into each worktree it hands a session and removes it when the session ends — so
an idle worktree's bare `.claude/` says nothing about the session that ran there. With **no
arguments** — settings written by an older installer — the hook reads the two pointers in
`$CLAUDE_PROJECT_DIR/checks/` itself and never treats the split as verified. It runs no
checkout-family derivation of its own.

The installer also keeps the hook-independent **deny rules** in `.claude/settings.local.json` in step:
`Read`/`Edit` of the private file and of `./checks/PRIVATE-MODE-ID` always; of the registry and
`./checks/FIREWALL-REGISTRY` only until the split verifies. It merges, never replaces, and the only
rules it ever removes are those two registry pairs (once the split verifies) and the pre-A2
`./checks/publish-skeleton.sh` pair (once that script is token-free).

## Proving it

1. The matrix: `python3 tools/claude-hooks/test_registry_guard.py` → `cases=… mismatches=0`. It builds
   a synthetic layout in a temp dir and checks both directions — the allow direction (ordinary work,
   prose and fixtures that mention the names) as carefully as the deny direction — in five
   configurations: verified, unverified, registry-only (no split yet), pointers-only and bare.
   Its own negative control runs a stub that allows everything, which the matrix must report;
   `checks/selftest.sh` runs both.
2. Live, in a new session after the installer ran: `head -c 0 "$(cat checks/PRIVATE-MODE-ID)"` must be
   **denied** (safe even if the hook is not live: it prints nothing), and `ls -l checks/PRIVATE-MODE-ID`
   must run.

## Residuals — known, stated, and left until a need shows up

A hook is a discipline aid, not an enforcement boundary: it closes the honest-slip class, not an
adversary. The private-mode limits a caregiver should know are in `tools/private-mode/README.md` →
*What it does not protect*. Four need care:

- **Other clients** (Cowork, the Claude app) have no hook: the keystone's profile-first rule and the
  `/private` posture are all there is.
- **File names are shown by listing**, and an incoming file keeps the name it arrived with: name files
  in a private-mode inbox without the identifier.
- On an older client that reads only a worktree's own settings, **worktrees that already existed**
  when the installer ran keep the older settings, whose hook recognises the files by name only —
  re-run the installer there or retire them.
- In the care checkout, **snapshots banked before the split** still carry the identifier, unprotected
  once the split verifies — removing them is the operator's call (`checks/topics/relay-and-export.md`).

## context-health.py — a size notice for the docs that enter a session's context

A **PostToolUse** hook on `Write` and `Edit`, wired by the installer in development trees only — the docs it watches change nowhere else; a care run removes a leftover entry. It watches
`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, every Markdown file one of them points to (a backticked
repository path or a Markdown link; one hop, so the topic docs under `contributing/` are in) and every
skill (`SKILL.md`). When an edit carries one of them past **400 lines or 16 KB** (about 4k tokens — a
line count alone misses a doc of few, long lines), and again each time it grows a further 50 lines or
2 KB, the hook asks the session to agree a workaround with the operator through AskUserQuestion:
split by role, move a rule to the doc that owns it, or cut history to ADRs and commits — or keep the
size for now. A subagent reports it to its caller. It is advisory and keeps no state: it cannot undo
an edit, the sizes before and after the edit decide, it opens no file outside the watched set
and it is silent on any error.

A different line limit is `--limit N` on its command line. Proof: `python3
tools/claude-hooks/test_context_health.py` → `mismatches=0`; its own negative control runs a silent
stub, and `checks/selftest.sh` runs both.

## release-notice.py — the care-side release notice at session start

A **SessionStart** hook, matcher `startup`, wired by the installer in care trees only and only while
the release ships this file — a rollback to one without it removes the hook by the leftovers path. It
runs `checks/release-notice.sh --daily`, the host-neutral check (ADR-0055 companion; mechanics in its
header), and speaks only when a release raising MINOR or MAJOR waits: one fixed line naming the newer
release, the release in use and `/update`, as the hook's user-facing message — the desktop app shows it
on screen (host test, ADR-0055 point 6) — and in the session's context, marked as already
shown so the session does not repeat it. A patch-only gap, an up-to-date pin, an opted-out machine
(`~/.config/tabularium/release-notice-off`), a check already made today and any failure print nothing;
it always exits 0. Proof: the release-notice cases in `checks/selftest.sh`.
