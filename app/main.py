import asyncpg
from aiohttp import ClientSession
from dotenv import load_dotenv
from selenium.webdriver.chrome.service import Service as ChromeService
# from seleniumwire import webdriver
from selenium import webdriver
from loguru import logger
from webdriver_manager.chrome import ChromeDriverManager
import pika

from .log import configure_logging
from .config import Settings, get_settings
from . import sequences
from .puller import RabbitNotifier
from .services import fetch_active_tokens


def get_driver(settings: Settings) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    agent = settings.user_agent
    opts.add_argument(agent)

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path="./drivers/").install()), options=opts)

    logger.info("Driver has been started")

    return driver


async def second_main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)

    browser = get_driver(config)
    creds = pika.PlainCredentials(username="guest", password="guest")
    params = pika.ConnectionParameters(host="localhost", port='5672', credentials=creds)
    connection = pika.BlockingConnection(params)
    notifier = RabbitNotifier(conn=connection)
    # i dont want to make another abstraction to this
    pool = await asyncpg.create_pool(config.db_dsn)

    tokens = await fetch_active_tokens(pool, config.db_tokens_table)
    if not tokens:
        logger.error("In the database has to be at least one active token!")
        browser.quit()
        return
    token = tokens[0]

    sequences.auth(browser, token)
    async with ClientSession() as session:
        notifier.add_on_startup(lambda _: logger.info("Application has been runned"))
        notifier.add_listener(sequences.UrlHandler(driver=browser, pool=pool, session=session))
        notifier.add_on_shutdown(lambda _: logger.info("Application has been shutdown"))

        notifier.run()

        connection.close()
