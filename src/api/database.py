"""
Database connection and utilities
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "../../db/uloom_quran.db")


def get_db_path() -> str:
    """Get absolute path to database"""
    return os.path.abspath(DATABASE_PATH)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Get database connection as context manager"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def dict_from_row(row: sqlite3.Row) -> dict:
    """Convert sqlite3.Row to dictionary"""
    return dict(zip(row.keys(), row))
