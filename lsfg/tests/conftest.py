import pytest

from lsfg import testing


def census_available() -> bool:
    return testing.raw_capture("finder", "full") is not None


census = pytest.mark.skipif(not census_available(), reason="Ax_analysis census captures not found")
