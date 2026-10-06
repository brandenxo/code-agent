from app import database
from app.seed_benchmarks import EXTERNAL_BENCHMARKS


def test_verified_external_benchmarks_seed_idempotently(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "external.db")
    database.initialize_database()

    assert EXTERNAL_BENCHMARKS
    assert database.seed_external_benchmarks(EXTERNAL_BENCHMARKS) == len(
        EXTERNAL_BENCHMARKS
    )
    assert database.seed_external_benchmarks(EXTERNAL_BENCHMARKS) == 0

    rows = database.get_external_benchmarks()
    assert len(rows) == len(EXTERNAL_BENCHMARKS)
    assert {row["model_id"] for row in rows} == {
        model_id for _, _, model_id in database.SEEDED_MODELS
    }
    assert all(row["source_url"] and row["published_date"] for row in rows)
