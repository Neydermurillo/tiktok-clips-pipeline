from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from clips.config import DB_DSN


@contextmanager
def get_conn():
    conn = psycopg2.connect(DB_DSN)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql: str, params=None) -> list[dict]:
    with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall()) if cur.description else []


def execute(sql: str, params=None) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
