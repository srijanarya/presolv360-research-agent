# One entrypoint a reviewer can run: tests, before/after measurement, publication checks.
.PHONY: check test measure exclusions

check: test measure exclusions
	@echo "\nmake check: OK"

test:
	uv run --locked pytest -q

measure:
	uv run --locked python scripts/measure.py --check

exclusions:
	@uv run --locked python scripts/check_exclusions.py
