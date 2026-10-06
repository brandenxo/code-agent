"""Import verified public benchmark data into SQLite.

Add only values copied from a named public source, with its URL and publication
date. No sample scores are included because fabricated data would make routing
look more informed than it is.
"""

from app.database import initialize_database, seed_external_benchmarks


EXTERNAL_BENCHMARKS = []


def main():
    initialize_database()
    inserted = seed_external_benchmarks(EXTERNAL_BENCHMARKS)
    print(f"Inserted {inserted} external benchmark record(s).")


if __name__ == "__main__":
    main()
