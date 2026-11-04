import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("APP_ENV", "development")
# the original tests are written against the demonstration curriculum;
# tests on the real KUSOM data build their engine explicitly (test_kusom_data.py)
os.environ.setdefault("CURRICULUM_SOURCE", "placeholder")

import pytest

from app.mimar.service import MimarService
from app.mimar.store import Store


@pytest.fixture
def svc():
    return MimarService(Store(":memory:"))


@pytest.fixture
def admin(svc):
    return svc.ensure_admin("test-admin-token")
