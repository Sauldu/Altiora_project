import sys
import pytest
from pathlib import Path

# Ajoute le dossier src directement au sys.path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

@pytest.fixture
def test_data_dir():
    return Path(__file__).parent / "test_data"