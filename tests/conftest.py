import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import app as application


@pytest.fixture
def app_module():
    return application


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()
