# conftest.py (project root)
import pytest

def pytest_collection_modifyitems(items):
    """Run test_rate_limit last to avoid Windows anyio cancel scope issues."""
    rate_limit_tests = [i for i in items if "test_rate_limit" in i.nodeid]
    other_tests = [i for i in items if "test_rate_limit" not in i.nodeid]
    items[:] = other_tests + rate_limit_tests