import asyncpg
from aiohttp import ClientSession
from dotenv import load_dotenv
from selenium.webdriver.chrome.service import Service as ChromeService
from seleniumwire import webdriver
# from selenium import webdriver
from loguru import logger
from webdriver_manager.chrome import ChromeDriverManager
import pika

from .log import configure_logging
from .config import Settings, get_settings
from . import sequences
from .puller import RabbitNotifier
from .services import fetch_active_tokens, create_tokens_table

import nest_asyncio
nest_asyncio.apply()


def get_driver(settings: Settings) -> webdriver.Chrome:
    if settings.browser.lower() == "chrome":
        opts = webdriver.ChromeOptions()
        agent = settings.user_agent
        opts.add_argument(agent)
        opts.add_argument("--headless")
        opts.add_argument("--window-size=%s" % settings.window_size)
        opts.add_argument('--no-sandbox')

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path="./drivers/").install()), options=opts)
    elif settings.browser.lower() == "safari":
        # нужно установить тест браузер самостоятельно
        driver = webdriver.Safari(executable_path="./drivers/")
    else:
        raise ValueError("Browser is not supported")

    logger.info("Driver has been started")

    return driver


async def second_main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)
    url = pika.URLParameters(config.queue_dsn)
    connection = pika.BlockingConnection(url)
    notifier = RabbitNotifier(conn=connection, queue_name=config.queue_name, exchange_name=config.exchange_name)
    # i dont want to make another abstraction to this
    pool = await asyncpg.create_pool(config.db_dsn)

    logger.info("Pool has been created")

    await create_tokens_table(pool, config.db_tokens_table)

    logger.info("Created Tokens table")

    tokens = await fetch_active_tokens(pool, config.db_tokens_table)
    if not tokens:
        logger.error("In the database has to be at least one active token!")
        return
    token = tokens[0]

    logger.info("First token is taken")

    browser = get_driver(config)

    sequences.auth(browser, token)
    async with ClientSession() as session:
        notifier.add_on_startup(lambda _: logger.info("Application has been runned"))
        notifier.add_listener(sequences.UrlHandler(driver=browser, pool=pool, session=session))
        notifier.add_on_shutdown(lambda _: logger.info("Application has been shutdown"))

        notifier.run()
