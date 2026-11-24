# Presence of this conftest at the repository root puts the root on sys.path, so
# ``sect_academy`` imports under a bare ``pytest``.
import os

# The app always persists to a JSON file; keep the test suite off disk.
os.environ.setdefault("SECT_ACADEMY_FILE", ":memory:")
