import asyncio
from typing import Optional

from aiohttp import ClientSession
from asyncpg import Pool
from loguru import logger
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By

from .config import Settings, get_settings
from .abc import IListener
from .services import set_token, fetch_active_tokens, mark_as_spent
from .consts import ROBLOX_TOKEN_KEY


def auth(browser: Chrome, token: str):
    """
    Redirects to home page

    :param browser:
    :param token:
    :return:
    """
    browser.get("https://www.roblox.com/game-pass/19962432/unnamed")
    browser.add_cookie({"name": ".ROBLOSECURITY", "value": token, "domain": "www.roblox.com"})
    elemt = browser.find_element(By.CLASS_NAME, "rbx-navbar-login")
    link = elemt.get_attribute("href")
    # redirected to home page
    browser.get(link)


class UrlHandler(IListener):
    """
    Основной хендлер всех запросов,

    Не слишком элегантно но сойдет
    """
    def __init__(self, driver: Chrome, pool: Pool, session: ClientSession, config: Optional[Settings] = None, loop=None):
        self.config = config or get_settings()
        self.driver = driver
        self.current_token = ""
        self.loop = loop or asyncio.get_event_loop()
        self._session = session
        self._pool = pool

    async def get_robux_count(self, driver: Chrome):
        # use it to get user_id
        url = "https://thumbnails.roblox.com/v1/batch"
        cookies = driver.get_cookies()

        async with self._session.post(url, cookies=cookies) as resp:
            assert resp.status == 200

            data = await resp.json()

            try:
                user_id = data["data"]["targetId"]
            except KeyError:
                logger.info("Invalid payload", extra={"cookies": cookies})
                return

        robux_url = "https://economy.roblox.com/v1/users/{user_id}/currency"

        async with self._session.post(robux_url.format(user_id), cookies=cookies) as resp:
            assert resp.status == 200

            return (await resp.json()).get("robux")

    async def get_new_token(self) -> Optional[str]:
        """
        Выбирает рандомный свободный токен

        :return:
        """
        tokens = await fetch_active_tokens(self._pool, self.config.db_tokens_table)
        if not tokens:
            return ""
        return tokens[0]

    async def mark_as_spent(self, driver) -> None:
        token = driver.get_cookie(ROBLOX_TOKEN_KEY)
        await mark_as_spent(self._pool, token, self.config.db_tokens_table)

    def __call__(self, data: dict):
        url = data.pop("url")
        driver = self.driver
        loop = self.loop

        # предпологается что бразуер уже авторизорван
        driver.get(url)
        robux = self.loop.run_until_complete(self.get_robux_count(driver))
        cost = driver.find_element(By.CLASS_NAME, "text-robux-lg")
        if cost > robux:
            # it can't buy this battlepass
            return
        if robux < 5:
            # marks the current token as spent
            loop.run_until_complete(self.mark_as_spent(driver))
            driver.delete_cookie(name=ROBLOX_TOKEN_KEY)
            token = loop.run_until_complete(self.get_new_token())
            if not token:
                logger.info("OUT OF TOKENS")
                return
            set_token(driver, token)
        # finds a buy button element
        btn = driver.find_element(By.CLASS_NAME, "PurchaseButton")
        # HERE IT'S IT BUYS GAMEPASS
        btn.click()
        logger.info(f"Purchased gamepass for {cost} robuxes")
