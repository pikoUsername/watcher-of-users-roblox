import asyncio
from typing import Optional

from aiohttp import ClientSession
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By

from app.config import Settings, get_settings
from app.abc import IListener
from app.connector import BasicDBConnector
from app.services import set_token, convert_browser_cookies_to_aiohttp, \
    extract_user_id_from_profile_url, TokenService
from app.consts import ROBLOX_TOKEN_KEY, TOKEN_RECURSIVE_CHECK


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
    logger.info("Passed Roblox registration")


class UrlHandler(IListener):
    """
    Основной хендлер всех запросов,

    Очень грязный код
    """
    def __init__(
            self,
            driver: Chrome,
            conn: BasicDBConnector,
            session: ClientSession,
            config: Optional[Settings] = None,
            loop=None
    ) -> None:
        self.config = config or get_settings()
        self.driver = driver
        self.current_token = ""
        self.loop = loop or asyncio.get_event_loop()
        self._session = session
        self._conn = conn

        self.token_service = TokenService.get_current()

    async def get_robux_count(self, driver: Chrome):
        # use it to get user_id
        url = "https://thumbnails.roblox.com/v1/batch"
        cookies = driver.get_cookies()
        cookies = convert_browser_cookies_to_aiohttp(cookies)

        async with self._session.post(url, cookies=cookies) as resp:
            assert resp.status == 200

            data = await resp.json()

            try:
                user_id = data["data"]["targetId"]
            except KeyError:
                logger.info("Invalid payload", extra={"cookies": cookies})
                return
        return self.get_robux_by_uid(driver, user_id)

    async def get_robux_by_uid(self, driver: Chrome, user_id: int) -> int:
        cookies = driver.get_cookies()
        cookies = convert_browser_cookies_to_aiohttp(cookies)

        robux_url = "https://economy.roblox.com/v1/users/{user_id}/currency"

        async with self._session.get(robux_url.format(user_id=user_id), cookies=cookies) as resp:
            logger.info(f"Headers, {resp.headers}")
            logger.info(f"Status, {resp.status}")
            logger.info(f"Body, {await resp.text()}")

            assert resp.status == 200

            return int((await resp.json()).get("robux"))

    async def get_new_token(self) -> Optional[str]:
        """
        Выбирает рандомный свободный токен

        :return:
        """
        tokens = await self.token_service.fetch_active_tokens()
        if not tokens:
            return ""
        return tokens[0]

    async def mark_as_spent(self, driver) -> None:
        token = driver.get_cookie(ROBLOX_TOKEN_KEY)
        await self.token_service.mark_as_spent(token)

    async def change_token(self, driver) -> None:
        loop = self.loop

        # marks the current token as spent
        loop.run_until_complete(self.mark_as_spent(driver))
        driver.delete_cookie(name=ROBLOX_TOKEN_KEY)
        token = loop.run_until_complete(self.get_new_token())
        if not token:
            logger.info("OUT OF TOKENS")
            return
        set_token(driver, token)
        driver.refresh()

    async def change_token_recursive(self, driver: Chrome, depth: int = TOKEN_RECURSIVE_CHECK):
        if depth == 0:
            raise RuntimeError("TOKENS CORRUPTED, WAITING FOR ACTIONS")
        await self.change_token(driver)
        if not self.check_page_for_valid_login(driver):
            await self.change_token(driver)
        await self.change_token_recursive(driver, depth - 1)

    def check_page_for_valid_login(self, driver: Chrome) -> bool:
        # finds a signup button, if yes, then it returns False
        try:
            driver.find_element(By.CLASS_NAME, "rbx-navbar-signup")
        except NoSuchElementException:
            return True
        return False

    async def __call__(self, data: dict):
        url = data.pop("url")
        driver = self.driver

        # предпологается что бразуер уже авторизорван
        driver.get(url)
        driver.save_screenshot("screenshot.png")
        # robux = await self.get_robux_count(driver)
        link = driver.find_element(By.CSS_SELECTOR, ".age-bracket-label > a.text-link")
        profile_url = link.get_attribute("href")
        user_id = extract_user_id_from_profile_url(profile_url)
        robux = await self.get_robux_by_uid(driver, user_id)
        cost = driver.find_element(By.CLASS_NAME, "text-robux-lg")
        if int(cost.text) > robux:
            # it can't buy this battlepass
            return
        if robux < 5:
            await self.change_token_recursive(driver)

        # finds a buy button element
        try:

            btn = driver.find_element(By.CLASS_NAME, "PurchaseButton")
            # HERE IT'S IT BUYS GAMEPASS
            btn.click()

            confirm_btn = driver.find_element(By.ID, "confirm-btn")
        except NoSuchElementException:
            logger.info("Gamepass has been already bought")
        else:
            confirm_btn.click()

            logger.info(f"Purchased gamepass for {cost} robuxes")
