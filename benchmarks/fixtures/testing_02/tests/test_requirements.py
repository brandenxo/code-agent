from pathlib import Path


def test_requested_test_file_has_key_cases():
    path = Path("tests/test_slug.py")
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "slugify" in source
    assert "punct" in source.lower()
    assert '""' in source
    assert source.count("def test_") >= 3
