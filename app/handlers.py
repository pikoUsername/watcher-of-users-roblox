import asyncio
import time
from typing import Optional

from aiohttp import ClientSession
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By

from app.config import Settings
from app.errors import GamePassAlreadyBought
from app.services.abc import IListener, BasicDBConnector
from app.services.db import get_db_conn
from app.services.driver import set_token, convert_browser_cookies_to_aiohttp, \
    extract_user_id_from_profile_url, get_driver
from app.repos import TokenService
from app.consts import ROBLOX_TOKEN_KEY, TOKEN_RECURSIVE_CHECK, ROBLOX_HOME_URL
from app.services.publisher import BasicMessageSender
from app.schemas import ReturnSignal, StatusCodes


def auth(browser: Chrome, token: str):
    """
    Just sets a token and refreshes the page

    :param browser:
    :param token:
    :return:
    """
    browser.get(ROBLOX_HOME_URL)
    set_token(browser, token)  # noqa
    browser.refresh()


class UrlHandler(IListener):
    """
    Основной хендлер всех запросов,

    Он должен иметь в __init__ только самое необходимое!

    Очень грязный код
    """
    def __init__(self) -> None:
        # предпологается что мы будем работать в треде,
        # так что все переменные будут установлены ТОЛЬКО в setup
        # потому как в __init__ не принято делать инициализацию вешей
        # которые требуют сложных действии, да URLHandler для каждого треда будет свой
        # но лучше перестрахаватся
        self.config: Optional[Settings] = None
        self.driver: Optional[Chrome] = None
        self.current_token = ""
        self._session: Optional[ClientSession] = None

        self.token_service: Optional[TokenService] = None
        self.setupped = False

    async def setup(self, data: dict, conn: BasicDBConnector, settings: Settings, token_service: TokenService):
        if self.setupped:
            return
        driver = get_driver(settings)

        logger.info("Driver has been set")

        data.update(driver=driver)

        loop = asyncio.get_event_loop()

        _task = loop.create_task(token_service.fetch_token())
        token = loop.run_until_complete(_task)

        logger.info("First token has been taken")

        cookies = convert_browser_cookies_to_aiohttp(driver.get_cookies())

        self._session = ClientSession(cookies=cookies)
        self.driver = driver

        self.current_token = token
        self.token_service = token_service

        logger.info("Going to login")
        auth(driver, token)

        self.setupped = True

    def close(self, driver: Chrome):
        driver.quit()

        loop = asyncio.get_event_loop()

        loop.run_until_complete(self._session.close())

        logger.info("Closing up...")

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

    async def mark_as_spent(self, driver) -> None:
        token = driver.get_cookie(ROBLOX_TOKEN_KEY)
        await self.token_service.mark_as_spent(token)

    async def change_token(self, driver) -> None:
        # marks the current token as spent
        await self.mark_as_spent(driver)
        driver.delete_cookie(name=ROBLOX_TOKEN_KEY)
        token = await self.token_service.fetch_token()
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

    async def __call__(self, driver: Chrome, url: str, settings: Settings, publisher: BasicMessageSender):
        # предпологается что бразуер уже авторизорван
        t = time.monotonic()
        logger.info(f"Redirecting to {url}")
        driver.get(url)
        if settings.debug:
            driver.save_screenshot("screenshot.png")
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
            logger.debug("Getting purchase button")
            btn = driver.find_element(By.CLASS_NAME, "PurchaseButton")
            # HERE IT'S BUYS GAMEPASS
            btn.click()

            confirm_btn = driver.find_element(By.ID, "confirm-btn")
        except NoSuchElementException:
            logger.info("Gamepass has been already bought")

            data = ReturnSignal(
                status_code=StatusCodes.already_bought,
            )

            logger.debug("Sending back information about.")
        else:
            confirm_btn.click()

            logger.info(f"Purchased gamepass for {cost} robuxes")
            data = ReturnSignal(status_code=StatusCodes.success)
        if data:
            publisher.send_message(data.dict())

        logger.info(f"Execution Time: {(time.monotonic() - t)}")


class DBHandler(IListener):
    async def setup(self, data: dict, settings: Settings):
        conn = await get_db_conn(settings)

        token_service = TokenService.get_current(
            no_error=True
        ) or TokenService(conn, settings.db_tokens_table)

        data.update(token_service=token_service, conn=conn)

    async def close(self, conn: BasicDBConnector):
        await conn.close()

    def __call__(self, *args, **kwargs):
        pass


class PublisherHandler(IListener):
    async def setup(self, data: dict, settings: Settings) -> None:
        logger.info("Setting up basicMessageSender")

        publisher = BasicMessageSender(
            settings.queue_dsn,
            queue=settings.send_queue_name,
            exchange=settings.send_queue_exchange_name,
            routing=settings.send_queue_name,
        )
        publisher.connect()

        data.update(publisher=publisher)

    def close(self, publisher: BasicMessageSender):
        publisher.close()

    def __call__(self, *args, **kwargs):
        pass
