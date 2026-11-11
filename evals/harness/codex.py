"""Codex host scaffolding. Live execution is deliberately disabled (ADR-0057).

workspace-write alone does not confine reads. There is NO subprocess launch here,
no containment override, and no credential copying. Offline fixture/argv construction
and JSONL normalization can be reviewed before a real enclosing boundary is built.
"""

import os
import re
from pathlib import Path

TIMEOUT_S = 600
ENTRY_BYTES = (
    "# Tabularium evaluation entry\n\n"
    "Before doing any work, read `CLAUDE.md` in full, then `EVAL-MODE.md` in full.\n"
    "CLAUDE.md is the care contract; EVAL-MODE.md is this trial's operational note.\n"
).encode("utf-8")
DISABLED_REASON = (
    "Codex host DISABLED: trial-root read confinement is not proven. "
    "workspace-write confines writes but is not a trial-root read boundary; a separate HOME "
    "does not restrict reads. No enclosing sandbox/container or outside-read/write canary "
    "probe is implemented. Implement and validate that boundary before enabling this host "
    "(ADR-0057). No Codex session has run."
)


class CodexUnavailable(RuntimeError):
    """A refusal before any Codex service call or authentication access."""


def api_key_names(environ=None):
    """Credential *names* only; never echo values. Empty variables are harmless.

    Catch vendor aliases as well as the usual OPENAI_API_KEY and CODEX_API_KEY.
    A future clean login configuration must still force the OpenAI/ChatGPT provider.
    """
    env = os.environ if environ is None else environ
    return sorted(k for k, v in env.items() if v and (
        re.search(r"(?:API_KEY|API_TOKEN|ACCESS_TOKEN|AUTH_TOKEN)$", k, re.I)
        or k.upper() in {"OPENAI_TOKEN", "CODEX_TOKEN", "AZURE_OPENAI_KEY"}))


def check_credentials(environ=None, allow_api_key=False):
    names = api_key_names(environ)
    if names and not allow_api_key:
        raise CodexUnavailable(
            "Codex host refused: API credentials are set (%s). Use the operator's Codex "
            "login; unset them or explicitly pass --allow-api-key. That flag does not "
            "bypass containment." % ", ".join(names))


def containment_selftest():
    """Fail closed without starting a model in an unconfined environment.

    This is a precondition report, NOT a successful canary probe. A future confiner
    must enclose startup instruction discovery, tools and subprocesses, deny reads
    outside the trial, and prove attempted outside reads/writes fail on that exact
    launch route. Also deny tool network access; only the chosen inference service
    may receive the synthetic trial. Never probe against a real care path.
    """
    return {"proven": False, "attempts": 0, "attempted_read": False,
            "attempted_write": False, "read_canary": "not-run",
            "write_canary": "not-run", "reasons": [DISABLED_REASON]}


def require_enabled(*, environ=None, allow_api_key=False):
    """No flag can turn missing confinement into permission to run."""
    check_credentials(environ, allow_api_key)
    result = containment_selftest()
    if not isinstance(result, dict) or result.get("proven") is not True:
        raise CodexUnavailable(DISABLED_REASON)
    # Deliberate second stop: a mocked/stale probe or future change to its return
    # value cannot enable an adapter that still has no enclosing launcher.
    raise CodexUnavailable(DISABLED_REASON)


def prepare_fixture(fixture_root, note):
    """Add only the Codex entry pointer and the exact note supplied to Claude.

    The shared builder owns every record, checklist and CLAUDE.md byte. These two
    extra files enter the before-tree and pre-transit scan, never a grader edit.
    """
    root = Path(fixture_root)
    (root / "AGENTS.md").write_bytes(ENTRY_BYTES)
    (root / "EVAL-MODE.md").write_bytes(note if isinstance(note, bytes) else note.encode("utf-8"))


def exec_argv(fixture_root, task, last_message, model=None):
    """Reviewable proposed argv; NOT an executable containment mechanism.

    A future launcher must supply stdin=subprocess.DEVNULL (equivalent to
    </dev/null), a clean login-only HOME/CODEX_HOME under run-root config/ and an
    enclosing, proven read/network boundary. This function launches nothing.
    """
    argv = ["codex", "exec", "--json", "-s", "workspace-write", "-C", str(fixture_root),
            "--ephemeral", "-o", str(last_message), "--skip-git-repo-check",
            "--ignore-user-config", "-c", "sandbox_workspace_write.network_access=false",
            "-c", 'web_search="disabled"', "-c", 'forced_login_method="chatgpt"',
            "-c", 'model_provider="openai"']
    if model:
        argv += ["--model", model]
    return argv + ["--", task]


def run_session(fixture_root, task_text, config_dir, transcript_path, model=None,
                *, allow_api_key=False, **kwargs):
    """Same host entry shape as session.py; refuses before touching any path."""
    require_enabled(allow_api_key=allow_api_key)


def estimate_lines(mode, n_trials, n_variants):
    return [
        "plan: codex %s run — %d trial(s) over %d variant(s), plus containment and image "
        "probes before any trial" % (mode, n_trials, n_variants),
        "time: unmeasured on Codex; %d-minute timeout per trial (%d minutes total serial "
        "trial timeout budget), plus fixture/probe time" % (TIMEOUT_S // 60,
                                                          n_trials * TIMEOUT_S // 60),
        "cost: operator's Codex plan/quota; no dollar estimate from the Claude ledger "
        "(an API-key override, if eventually enabled, requires separate pricing)",
        DISABLED_REASON,
    ]
