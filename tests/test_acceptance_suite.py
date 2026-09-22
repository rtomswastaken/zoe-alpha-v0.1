"""Unit tests for the 21-point acceptance test suite."""

from zoe.cli import run_acceptance_suite


def test_acceptance_suite_execution():
    res = run_acceptance_suite()
    assert res["total"] == 21
    # All 21 tests should pass
    assert res["failed"] == 0, f"Failed tests: {[r for r in res['results'] if not r['passed']]}"
    assert res["passed"] == 21
