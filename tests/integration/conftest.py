from pathlib import Path
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if Path(__file__).parent in item.path.parents:
            item.add_marker(pytest.mark.integration)
