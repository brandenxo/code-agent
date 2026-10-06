import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "code-agent.db"

SEEDED_MODELS = [
    (
        "Nemotron 3 Ultra",
        "NVIDIA",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    ),
    (
        "Laguna S 2.1",
        "Poolside",
        "poolside/laguna-s-2.1:free",
    ),
    (
        "North Mini Code",
        "Cohere",
        "cohere/north-mini-code:free",
    ),
]


def current_time():
    """Return a UTC timestamp suitable for storing as text."""
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    connection = get_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_id TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS internal_benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                task_id TEXT,
                category TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency REAL,
                tokens INTEGER,
                tool_calls INTEGER,
                run_date TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES models(model_id)
            );

            CREATE TABLE IF NOT EXISTS external_benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                benchmark_name TEXT NOT NULL,
                score REAL NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT,
                published_date TEXT,
                fetched_at TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES models(model_id)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    seed_models()


def seed_models():
    connection = get_connection()
    try:
        connection.executemany(
            """
            INSERT OR IGNORE INTO models (name, provider, model_id)
            VALUES (?, ?, ?)
            """,
            SEEDED_MODELS,
        )
        connection.commit()
    finally:
        connection.close()


def get_models(active_only=False):
    connection = get_connection()
    try:
        sql = "SELECT * FROM models"
        parameters = []
        if active_only:
            sql += " WHERE active = ?"
            parameters.append(1)
        sql += " ORDER BY id"
        return connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()


def add_internal_benchmark(
    model_id,
    task_id,
    category,
    success,
    latency=None,
    tokens=None,
    tool_calls=None,
    run_date=None,
):
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO internal_benchmarks (
                model_id, task_id, category, success, latency,
                tokens, tool_calls, run_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                task_id,
                category,
                int(success),
                latency,
                tokens,
                tool_calls,
                run_date or current_time(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def get_internal_benchmarks(model_id=None, category=None):
    connection = get_connection()
    try:
        sql = "SELECT * FROM internal_benchmarks WHERE 1 = 1"
        parameters = []
        if model_id is not None:
            sql += " AND model_id = ?"
            parameters.append(model_id)
        if category is not None:
            sql += " AND category = ?"
            parameters.append(category)
        sql += " ORDER BY run_date DESC, id DESC"
        return connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()


def add_external_benchmark(
    model_id,
    benchmark_name,
    score,
    source,
    source_url=None,
    published_date=None,
    fetched_at=None,
):
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO external_benchmarks (
                model_id, benchmark_name, score, source, source_url,
                published_date, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                benchmark_name,
                score,
                source,
                source_url,
                published_date,
                fetched_at or current_time(),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def seed_external_benchmarks(records):
    """Insert published benchmark records without duplicating existing rows.

    Each record must contain a real, sourced value. This helper deliberately
    ships without benchmark numbers; callers provide records they have verified.
    """
    inserted = 0
    connection = get_connection()
    try:
        for record in records:
            required = {"model_id", "benchmark_name", "score", "source"}
            missing = required.difference(record)
            if missing:
                raise ValueError(
                    f"External benchmark record is missing: {', '.join(sorted(missing))}"
                )

            published_date = record.get("published_date")
            existing = connection.execute(
                """
                SELECT 1 FROM external_benchmarks
                WHERE model_id = ? AND benchmark_name = ? AND source = ?
                  AND published_date IS ?
                """,
                (
                    record["model_id"],
                    record["benchmark_name"],
                    record["source"],
                    published_date,
                ),
            ).fetchone()
            if existing:
                continue

            connection.execute(
                """
                INSERT INTO external_benchmarks (
                    model_id, benchmark_name, score, source, source_url,
                    published_date, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["model_id"],
                    record["benchmark_name"],
                    record["score"],
                    record["source"],
                    record.get("source_url"),
                    published_date,
                    record.get("fetched_at") or current_time(),
                ),
            )
            inserted += 1
        connection.commit()
        return inserted
    finally:
        connection.close()


def get_external_benchmarks(model_id=None, benchmark_name=None):
    connection = get_connection()
    try:
        sql = "SELECT * FROM external_benchmarks WHERE 1 = 1"
        parameters = []
        if model_id is not None:
            sql += " AND model_id = ?"
            parameters.append(model_id)
        if benchmark_name is not None:
            sql += " AND benchmark_name = ?"
            parameters.append(benchmark_name)
        sql += " ORDER BY fetched_at DESC, id DESC"
        return connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()


def create_conversation(conversation_id, title=None):
    timestamp = current_time()
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, title, timestamp, timestamp),
        )
        connection.commit()
    finally:
        connection.close()


def get_conversation(conversation_id):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    finally:
        connection.close()


def get_conversations():
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        connection.close()


def update_conversation_title(conversation_id, title):
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, current_time(), conversation_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def add_message(conversation_id, role, content, model_id=None):
    timestamp = current_time()
    connection = get_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO messages (
                conversation_id, role, content, model_id, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, role, content, model_id, timestamp),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (timestamp, conversation_id),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def get_messages(conversation_id):
    connection = get_connection()
    try:
        return connection.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (conversation_id,),
        ).fetchall()
    finally:
        connection.close()
