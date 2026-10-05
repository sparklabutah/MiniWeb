"""Tests exercise the annotation tool's editing routes, which data/final_set.yaml locks; run them unlocked.
tests/test_final_set.py clears the override to test the lock itself."""
import os

os.environ.setdefault("MINIWEB_UNLOCK", "1")
