from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from loguru import logger
from selenium.webdriver.support.wait import WebDriverWait

from app.consts import ROBLOX_HOME_URL
from app.repos import TokenRepository
from app.services.driver import presence_of_any_text_in_element, set_token


def is_authed(driver: WebDriver) -> bool:
	try:
		# if it's text is ? then it means we cant buy, it means this session can't be used
		WebDriverWait(driver, 3).until(
			presence_of_any_text_in_element((By.ID, "nav-robux-amount"))
		)
	except TimeoutException:
		return False

	return True


def auth(browser: WebDriver, token: str):
	"""
	Just sets a token and refreshes the page

	:param browser:
	:param token:
	:return:
	"""
	browser.get(ROBLOX_HOME_URL)
	set_token(browser, token)
	browser.refresh()


async def auth_browser(driver: WebDriver, token_service: TokenRepository, depth: int = 5) -> None:
	logger.info("First token has been taken")

	token = await token_service.fetch_token()
	if token is None:
		raise ValueError("Tokens are unavailable")

	logger.info("Starting authentication to roblox.com")

	logger.info("Logging in")
	auth(driver, token)
	if not is_authed(driver):
		if depth == 0:
			await token_service.mark_as_inactive(token)

		logger.warning("Login failed, trying another token!")

		return await auth_browser(driver, token_service, depth - 1)

	logger.info("Login complete")
