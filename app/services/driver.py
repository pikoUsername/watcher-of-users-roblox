from typing import List, Dict, Any, TYPE_CHECKING
from urllib.parse import urlparse

from loguru import logger
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from seleniumwire.webdriver import Chrome
from webdriver_manager.chrome import ChromeDriverManager

if TYPE_CHECKING:
    from app.config import Settings


def csrf_token_to_request(csrf_token: str, roblox_token: str):
    def interceptor(request):
        request.headers['X-CSRF-TOKEN'] = csrf_token
        request.headers['Cookies'] = ".ROBLOSECURITY=" + roblox_token

    return interceptor


def set_token(driver: Chrome, token: str) -> None:
    driver.add_cookie({"name": ".ROBLOSECURITY", "value": token, "domain": "www.roblox.com"})


def get_driver(settings: "Settings") -> webdriver.Chrome:
    logger.info("Setting up driver")

    if settings.browser.lower() == "chrome":
        opts = webdriver.ChromeOptions()
        agent = settings.user_agent
        opts.add_argument(agent)
        opts.add_argument('--ignore-ssl-errors=yes')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--ignore-certificate-errors')
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--headless")
        opts.add_argument("--window-size=%s" % settings.window_size)
        opts.add_argument('--no-sandbox')

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path="./drivers/").install()), options=opts)
    elif settings.browser.lower() == "remote":
        logger.info("Setting up remote chrome browser")

        options = webdriver.ChromeOptions()
        agent = settings.user_agent
        options.add_argument(agent)
        options.add_argument('--ignore-ssl-errors=yes')
        options.add_argument('--disable-gpu')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument("--headless")
        options.add_argument("--window-size=%s" % settings.window_size)
        logger.info(f"Options of browser: {options.arguments}")

        logger.info(f"Connecting to {settings.browser_dsn} Remote browser")

        driver = webdriver.Remote(command_executor=settings.browser_dsn, options=options)
    else:
        raise NotImplementedError(f"{settings.browser} is not yet implemented")

    return driver


def convert_browser_cookies_to_aiohttp(cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {}
    for cookie in cookies:
        name = cookie["name"]
        value = cookie["value"]
        result[name] = value
    return result


def extract_user_id_from_profile_url(url: str) -> int:
    uri = urlparse(url).path[1:]
    parts = uri.split('/')
    return int(parts[1])
