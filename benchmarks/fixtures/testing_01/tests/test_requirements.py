from pathlib import Path


def test_requested_test_file_has_key_cases():
    path = Path("tests/test_calculator.py")
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "divide" in source
    assert "pytest.raises" in source
    assert source.count("def test_") >= 2
