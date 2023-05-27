from typing import Optional, Dict, Any, List, TYPE_CHECKING

import sqlite3
from asyncpg import Pool, Connection, Record

from app.services.abc import BasicDBConnector

if TYPE_CHECKING:
    from app.config import Settings


class AsyncpgDBConnector(BasicDBConnector):
    __slots__ = ("pool",)

    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    # noinspection PyTypeChecker
    async def execute(self, sql, *args, **kwargs) -> Optional[str]:
        pool = self.pool

        async with pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                await conn.execute(sql, *args, **kwargs)

    async def fetch(self, sql, *args, **kwargs) -> Dict[str, Any]:
        pool = self.pool

        async with pool.acquire() as conn:
            conn: Connection
            record: Record = await conn.fetchrow(sql, *args, **kwargs)
            return record.items()

    async def fetchmany(self, sql, *args, **kwargs) -> List[Dict[str, Any]]:
        pool = self.pool

        async with pool.acquire() as conn:
            conn: Connection
            records: List[dict] = await conn.fetch(sql, *args, **kwargs)

        return records

    async def close(self):
        await self.pool.close()


# noinspection PyArgumentList
class SQLiteDBConnector(BasicDBConnector):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = self.dict_factory
        self._cursor = None

    @staticmethod
    def dict_factory(cursor, row):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}

    @property
    def cursor(self) -> sqlite3.Cursor:
        if self._cursor:
            self._cursor = self.conn.cursor()
        return self._cursor

    async def execute(self, sql, *args, **kwargs) -> Optional[str]:
        self.cursor.execute(sql, *args)
        self.conn.commit()

    async def fetch(self, sql, *args, **kwargs) -> Dict[str, Any]:
        result: dict = self.cursor.fetchone(sql, *args)
        return result

    async def fetchmany(self, sql, *args, **kwargs) -> List[Dict[str, Any]]:
        return self.cursor.fetchmany(sql, *args)

    async def close(self):
        self.conn.close()


async def get_db_conn(config: "Settings") -> BasicDBConnector:
    if config.db_dsn.startswith("sqlite3"):
        import sqlite3

        conn = sqlite3.connect(config.db_dsn)
        conn = SQLiteDBConnector(conn)
    elif config.db_dsn.startswith("postgresql") or config.db_dsn.startswith("postgres"):
        import asyncpg

        pool = await asyncpg.create_pool(config.db_dsn)
        conn = AsyncpgDBConnector(pool)
    else:
        raise ValueError("Db does not support, or DSN empty, dsn: %s" % config.db_dsn)
    return conn

