import asyncio
import json
from typing import Optional

import pydantic
from aiohttp import ClientSession
from loguru import logger
from selenium.common import NoSuchElementException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from app.browser import is_authed
from app.settings import Settings
from app.services.interfaces import IListener
from app.services.driver import set_token
from app.repos import TokenRepository
from app.consts import ROBLOX_TOKEN_KEY, TOKEN_RECURSIVE_CHECK
from app.services.exceptions import CancelException
from app.services.queue.publisher import BasicMessageSender
from app.schemas import ReturnSignal, StatusCodes, SendError, SearchResponse
from app.schemas import SearchData


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
        self.token_service: Optional[TokenRepository] = None

    async def setup(self, token_service: TokenRepository):
        self.token_service = token_service

    def close(self):
        pass

    async def mark_as_spent(self, driver: WebDriver) -> None:
        token = driver.get_cookie(ROBLOX_TOKEN_KEY)
        await self.token_service.mark_as_inactive(str(token))

    async def change_token(self, driver: WebDriver) -> None:
        # marks the current token as spent
        await self.mark_as_spent(driver)
        driver.delete_cookie(name=ROBLOX_TOKEN_KEY)
        token = await self.token_service.fetch_token()
        logger.info("Changing tokens")
        if not token:
            logger.info("OUT OF TOKENS")
            return
        set_token(driver, token)
        driver.refresh()

    async def change_token_recursive(self, driver: Chrome, depth: int = TOKEN_RECURSIVE_CHECK):
        if depth == 0:
            raise RuntimeError("TOKENS CORRUPTED, WAITING FOR ACTIONS")
        await self.change_token(driver)
        if not is_authed(driver):
            await self.change_token(driver)
        await self.change_token_recursive(driver, depth - 1)

    def form_url(self, name: str):
        return f"https://www.roblox.com/search/users?keyword={name}"

    async def __call__(
            self,
            driver: Chrome,
            search_data: SearchData,
            settings: Settings,
            publisher: BasicMessageSender,
            data: dict,
            session: ClientSession
    ) -> None:
        url = self.form_url(search_data.name)
        driver.get(url)

        logins = driver.find_elements(by=By.CSS_SELECTOR, value=".text-overflow.avatar-card-label.ng-binding")
        nicknames = driver.find_elements(by=By.CSS_SELECTOR, value=".avatar-name")

        response = []
        logger.info(logins + nicknames)

        for login, nickname in zip(logins, nicknames):
            response.append(
                SearchResponse(
                    login=login.text,
                    nickname=nickname.text,
                )
            )

        logger.info(f"collected response up: {response}")

        if settings.debug:
            driver.save_screenshot("screenshot.png")

        # if True:
        #     try:
        #         await self.change_token_recursive(driver)
        #     except RuntimeError:
        #         data.update(
        #             return_signal=ReturnSignal(
        #                 status_code=StatusCodes.no_tokens_available,
        #             )
        #         )
        #         return

        result = ReturnSignal(
            status_code=StatusCodes.success,
            data=response,
        )

        publisher.send_message(result.dict())


class DataHandler(IListener):
    def setup(self, *args, **kwargs):
        pass

    def close(self, *args, **kwargs):
        pass

    def __call__(self, data: dict, body: bytes, publisher: BasicMessageSender):
        try:
            _temp = json.loads(body)
            pur_data = SearchData(**_temp)
        except json.JSONDecodeError:
            logger.error("NOT HELLO")

            raise CancelException
        except pydantic.ValidationError as e:
            logger.info(f"Invalid data: {body}")

            errors = [SendError(name="validation error", info=str(e.errors()))]

            data = ReturnSignal(status_code=StatusCodes.invalid_data, errors=errors)

            publisher.send_message(data.dict())
            raise CancelException

        data.update(search_data=pur_data)
