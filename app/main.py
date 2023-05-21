import requests
from dotenv import load_dotenv
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from seleniumwire import webdriver
from loguru import logger
from webdriver_manager.chrome import ChromeDriverManager
import pika

from .log import configure_logging
from .config import Settings, get_settings
from . import sequences
from .puller import RabbitNotifier


def get_driver(settings: Settings) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    agent = settings.user_agent
    opts.add_argument(agent)

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)

    logger.info("Driver has been started")

    return driver


def csrf_token_to_request(csrf_token: str, roblox_token: str):
    def interceptor(request):
        request.headers['X-CSRF-TOKEN'] = csrf_token
        request.headers['Cookies'] = ".ROBLOSECURITY=" + roblox_token

    return interceptor


def main():
    """
    Программа имеет только один вход, и не имеет выхода.
    Она получат список пользвателей со токенами на вход от постгрес
    (что является антипаттерном, но ладно), и использует их до исчерпания робоксов.
    потом марикрует их как использванные.
    """
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

    # самая важная часть
    browser.add_cookie({"name": ".ROBLOSECURITY", "value": config.roblox_token, "domain": "www.roblox.com"})
    elemt = browser.find_element(By.CLASS_NAME, "rbx-navbar-login")
    link = elemt.get_attribute("href")
    browser.get(link)
    browser.get("https://www.roblox.com/game-pass/19962432/unnamed")

    # scenarios has to end with redirect of website itself, or going by yourself.

    while 1:
        pass


def second_main():
    config = get_settings()

    configure_logging(config.loggers)

    browser = get_driver(config)
    req = requests.post(
        "https://auth.roblox.com/v1/authentication-ticket",
        headers={"Cookie": ".ROBLOSECURITY=" + config.roblox_token}
    )
    csrf = req.headers['x-csrf-token']

    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

    notifier = RabbitNotifier(connection=connection)

    browser.request_interceptor = csrf_token_to_request(csrf, config.roblox_token)
    sequences.auth(browser, config)

    notifier.add_on_startup(lambda _: logger.info("Application has been runned"))

    notifier.add_listener(sequences.UrlHandler(driver=browser))

    notifier.add_on_shutdown(lambda _: logger.info("Application has been shutdown"))

    notifier.run()
