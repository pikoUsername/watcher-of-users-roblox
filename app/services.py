import asyncio
from typing import Sequence, Dict, Any, List
from urllib.parse import urlparse

from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from app.abc import SkipException
from app.config import Settings
from app.connector import BasicDBConnector, SQLiteDBConnector, AsyncpgDBConnector
from app.mixins import ContextInstanceMixin


def csrf_token_to_request(csrf_token: str, roblox_token: str):
    def interceptor(request):
        request.headers['X-CSRF-TOKEN'] = csrf_token
        request.headers['Cookies'] = ".ROBLOSECURITY=" + roblox_token

    return interceptor


def set_token(driver, token: str) -> None:
    driver.add_cookie({"name": ".ROBLOSECURITY", "value": token, "domain": "www.roblox.com"})


def get_driver(settings: Settings) -> webdriver.Chrome:
    if settings.browser.lower() == "chrome":
        opts = webdriver.ChromeOptions()
        agent = settings.user_agent
        opts.add_argument(agent)
        opts.add_argument("--headless")
        opts.add_argument("--window-size=%s" % settings.window_size)
        opts.add_argument('--no-sandbox')

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path="./drivers/").install()), options=opts)
    else:
        raise ValueError("Browser is not supported")

    return driver


def convert_browser_cookies_to_aiohttp(cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {}
    for cookie in cookies:
        name = cookie["name"]
        value = cookie["value"]
        result[name] = value
    return result


@staticmethod
def run_listeners(data, listeners):
    for listener in listeners:
        try:
            if asyncio.iscoroutinefunction(listener):
                loop = asyncio.get_running_loop()
                loop.run_until_complete(listener)
            if hasattr(listener, "__call__"):
                if asyncio.iscoroutinefunction(listener.__call__):
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(listener.__call__(data))
                    loop.run_until_complete(task)
            else:
                listener(data)
        except SkipException:
            pass


def extract_user_id_from_profile_url(url: str) -> int:
    uri = urlparse(url).path[1:]
    parts = uri.split('/')
    return int(parts[1])


async def get_db_conn(config: Settings) -> BasicDBConnector:
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


class TokenService(ContextInstanceMixin):
    def __init__(self, conn: BasicDBConnector, model_name: str) -> None:
        self.conn = conn

        self._model_name = model_name

        # singleton
        self.set_current(self)

    async def fetch_active_tokens(self) -> Sequence[str]:
        conn = self.conn
        model_name = self._model_name

        results: Sequence[dict] = await conn.fetchmany(f"SELECT token FROM {model_name} WHERE is_active = true")
        tokens = []
        for record in results:
            tokens.append(record.get("token"))
        return tokens

    async def mark_as_spent(self, token: str) -> None:
        conn = self.conn
        model_name = self._model_name

        await conn.execute(f"UPDATE {model_name} SET is_active = false WHERE token = $1", token)

    async def create_tokens_table(self) -> None:
        conn = self.conn
        model_name = self._model_name

        await conn.execute(f"CREATE TABLE IF NOT EXISTS {model_name} ("
                           f"id SERIAL PRIMARY KEY, token TEXT, is_active BOOLEAN DEFAULT true);")
