import requests
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from seleniumwire import webdriver
from loguru import logger

from .log import configure_logging
from .config import Settings, get_settings


def get_driver(settings: Settings) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    agent = settings.user_agent
    opts.add_argument(agent)

    # driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
    driver = webdriver.Chrome("./drivers/chromedriver.exe", options=opts)

    logger.info("Driver has been started")

    return driver


def csrf_token_to_request(csrf_token: str, roblox_token: str):
    def interceptor(request):
        request.headers['X-CSRF-TOKEN'] = csrf_token
        request.headers['Cookies'] = ".ROBLOSECURITY=" + roblox_token

    return interceptor


def main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)

    browser = get_driver(config)
    req = requests.post(
        "https://auth.roblox.com/v1/authentication-ticket",
        headers={"Cookie": ".ROBLOSECURITY=" + config.roblox_token}
    )
    csrf = req.headers['x-csrf-token']

    browser.request_interceptor = csrf_token_to_request(csrf, config.roblox_token)
    browser.get("https://www.roblox.com/game-pass/19962432/unnamed")
    browser.add_cookie({"name": ".ROBLOSECURITY", "value": config.roblox_token, "domain": "www.roblox.com"})
    elemt = browser.find_element(By.CLASS_NAME, "rbx-navbar-login")
    link = elemt.get_attribute("href")
    browser.get(link)
    browser.get("https://www.roblox.com/game-pass/19962432/unnamed")

    # scenarios has to end with redirect of website itself, or going by yourself.

    while 1:
        pass
