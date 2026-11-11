# Marker for explicitness. This directory's name ("private-mode") contains a hyphen, which is
# not a valid Python identifier — so `import tools.private-mode.test_redact_ids` (the statement
# form) can never work. But `python3 -m unittest tools.private-mode.test_redact_ids` does not
# use that statement: unittest's loader resolves the dotted name via importlib.import_module(),
# whose underlying path-based finder matches each component against filesystem entries by
# literal string, not by parsing it as an identifier. Verified empirically (not merely assumed):
# the resolution succeeds BOTH with this file present (regular package) and without any
# __init__.py at all (PEP-420 namespace package) — the published skeleton, which ships this
# directory but not tools/__init__.py, therefore also passes. The marker is kept because a
# regular package behaves more predictably across discovery tooling than a namespace package,
# and to carry this note. See topics/pipeline.md → Self-test and ADR-0029 point 8.
