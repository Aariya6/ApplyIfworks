from pathlib import Path

def test_version_layout():
    root=Path(__file__).resolve().parents[1]/'data/applications'
    assert root.exists()
