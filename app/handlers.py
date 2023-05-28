import asyncio
import time
from typing import Optional

from aiohttp import ClientSession
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By

from app.config import Settings
from app.services.abc import IListener, BasicDBConnector
from app.services.db import get_db_conn
from app.services.driver import set_token, convert_browser_cookies_to_aiohttp, get_driver
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


def press_agreement_button(browser: Chrome):
    try:
        logger.info("Pressing user agreement button")
        btn = browser.find_element(By.CSS_SELECTOR, ".modal-window .modal-footer .modal-button")
        btn.click()
    except NoSuchElementException:
        return


class UrlHandler(IListener):
    """
    Основной хендлер всех запросов,

    Он должен иметь в __init__ только самое необходимое!

    Очень грязный код
    """
    def __init__(self) -> None:
        self.config: Optional[Settings] = None

        self.token_service: Optional[TokenService] = None
        self.setupped = False

    async def setup(self, data: dict, conn: BasicDBConnector, settings: Settings, token_service: TokenService):
        driver = get_driver(settings)

        logger.info("Driver has been set")

        loop = asyncio.get_event_loop()

        _task = loop.create_task(token_service.fetch_token())
        token = loop.run_until_complete(_task)
        if not token:
            raise ValueError("No tokens available")

        logger.info("First token has been taken")

        cookies = convert_browser_cookies_to_aiohttp(driver.get_cookies())

        session = ClientSession(cookies=cookies)

        logger.info("Going to login")
        auth(driver, token)

        self.setupped = True

        data.update(driver=driver, session=session)

    def close(self, driver: Chrome, session):
        driver.quit()

        loop = asyncio.get_event_loop()

        loop.run_until_complete(session.close())

        logger.info("Closing up...")

    def get_robuxes(self, driver: Chrome) -> int:
        return int(driver.find_element(By.ID, "nav-robux-amount").text)

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
        robux = self.get_robuxes(driver)
        cost = driver.find_element(By.CLASS_NAME, "text-robux-lg")
        if int(cost.text) > robux:
            # it can't buy this battlepass
            return
        if robux < 5:
            try:
                await self.change_token_recursive(driver)
            except RuntimeError:
                data = ReturnSignal(
                    status_code=StatusCodes.no_tokens_available,
                )
                publisher.send_message(data.dict())
                return

        press_agreement_button(driver)

        try:
            btn = driver.find_element(By.CLASS_NAME, "PurchaseButton")

            btn.click()
        except NoSuchElementException:
            logger.info("Gamepass has been already bought")

            data = ReturnSignal(
                status_code=StatusCodes.already_bought,
            )

            logger.debug("Sending back information about.")
        else:
            confirm_btn = driver.find_element(By.CSS_SELECTOR, "a#confirm-btn.btn-primary-md")

            logger.info("Clicking buy now")

            # HERE IT'S BUYS GAMEPASS
            confirm_btn.click()

            logger.info(f"Purchased gamepass for {cost.text} robuxes")
            data = ReturnSignal(status_code=StatusCodes.success)

        if settings.debug:
            driver.save_screenshot("screenshot.png")

        if data:
            publisher.send_message(data.dict())

        logger.info(f"Execution Time: {(time.monotonic() - t)}")


class DBHandler(IListener):
    async def setup(self, data: dict, settings: Settings):
        logger.info("Creating database connection...")
        conn = await get_db_conn(settings)
        logger.info("Database conn complete")

        token_service = TokenService.get_current(
            no_error=True
        ) or TokenService(conn, settings.db_tokens_table)

        await token_service.create_tokens_table()

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
        logger.info("Connection to publisher has been established")

        data.update(publisher=publisher)

    def close(self, publisher: BasicMessageSender):
        publisher.close()

    def __call__(self, *args, **kwargs):
        pass


class ErrorHandler(IListener):
    def setup(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def __call__(self, err: Exception):
        logger.exception(err)
