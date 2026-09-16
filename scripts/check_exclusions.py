"""Publication check: private paths must never be tracked.

Path exclusion only. It does not establish that tracked file *contents* are safe
to publish; that review is separate and recorded in the Quest notes.
"""
from __future__ import annotations

import subprocess
import sys

BLOCKED_DIRS = {"_bmad-output"}
BLOCKED_FILES = {"CLAUDE.md", "GOALS.md", "stress-test-results.md", ".DS_Store"}

paths = [p for p in subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0") if p]
bad = []
for raw in paths:
    parts = raw.decode().split("/")
    if BLOCKED_DIRS.intersection(parts) or parts[-1] in BLOCKED_FILES:
        bad.append(raw.decode())

print(f"Tracked-path exclusion: {'FAIL' if bad else 'PASS'} ({len(paths)} tracked files)")
for path in bad:
    print("  unexpectedly tracked:", path)
sys.exit(1 if bad else 0)
