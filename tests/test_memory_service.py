import pytest
import os
import shutil
from pathlib import Path
from app.core.memory_service import MemoryService


@pytest.fixture
def memory_service():
    # Set up a test memory file
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)
    memory_file = test_dir / "test_memory.json"

    service = MemoryService(str(memory_file))
    yield service

    # Clean up
    shutil.rmtree(test_dir)


def test_user_preferences(memory_service):
    # Test setting preferences
    user_id = "test_user"
    prefs = {"theme": "dark", "language": "en"}

    # Set preferences
    result = memory_service.set_user_preference(user_id, prefs)
    assert result == prefs

    # Get preferences
    retrieved = memory_service.get_user_preference(user_id)
    assert retrieved == prefs
