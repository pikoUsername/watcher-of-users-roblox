from typing import List, Dict, Any, TYPE_CHECKING
from urllib.parse import urlparse

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
    # TODO, Implement thread safe mechanism to give each thread its own browser
    if settings.browser.lower() == "chrome":
        opts = webdriver.ChromeOptions()
        agent = settings.user_agent
        opts.add_argument(agent)
        opts.add_argument("--headless")
        opts.add_argument("--window-size=%s" % settings.window_size)
        opts.add_argument('--no-sandbox')

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path="./drivers/").install()), options=opts)
    # elif settings.browser.lower() == "firefox" and False:  # does not work, yet
    #     opts = webdriver.FirefoxOptions()
    #     agent = settings.user_agent
    #     opts.add_argument(agent)
    #     opts.headless = True
    #     service = FirefoxService(GeckoDriverManager(version="v0.33.0", path="./drivers/").install())
    #     if in_wsl():
    #         driver = webdriver.Firefox(
    #             service=service, firefox_binary=r"\mnt\c\Program Files\Mozilla Firefox\firefox.exe")
    #     else:
    #         # bug, with downloading the latest version of firefox
    #         driver = webdriver.Firefox(service=service, options=opts)
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


def extract_user_id_from_profile_url(url: str) -> int:
    uri = urlparse(url).path[1:]
    parts = uri.split('/')
    return int(parts[1])
