"""pytest entry point: the golden-model invariants (same checks run_all.py gates the build on)."""
import pytest
from . import checks

RESULTS = checks.run_all()


@pytest.mark.parametrize("check", RESULTS, ids=[c["name"] for c in RESULTS])
def test_invariant(check):
    assert check["ok"], check["name"]
