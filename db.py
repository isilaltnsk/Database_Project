"""Database helpers: raw SQL through psycopg2 (no ORM)."""
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a new PostgreSQL connection using the .env settings."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "commoncents"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def fetch_all(sql, params=None):
    """Run a SELECT with parametrized values and return a list of dicts."""
    conn = get_connection()
    try:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(sql, params or {})
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
