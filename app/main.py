from aiohttp import ClientSession
from dotenv import load_dotenv
from loguru import logger

from app.connector import URLConsumer
from app.log import configure_logging
from app.config import get_settings
from app import sequences
from app.services import TokenService, get_driver, get_db_conn
from app.connector import ReconnectingURLConsumer

import nest_asyncio
nest_asyncio.apply()


async def main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)
    queue_conn_args = {
        "amqp_url": config.queue_dsn,
        "queue": config.queue_name,
        "exchange": config.exchange_name,
    }

    root_consumer = URLConsumer(**queue_conn_args)
    consumer = ReconnectingURLConsumer(
        consumer=root_consumer,
        **queue_conn_args,
    )
    conn = await get_db_conn(config)

    logger.info("Pool has been created")

    token_service = TokenService(conn, config.db_tokens_table)

    await token_service.create_tokens_table()

    logger.info("Created Tokens table")

    tokens = await token_service.fetch_active_tokens()
    if not tokens:
        logger.error("In the database has to be at least one active token!")
        return
    token = tokens[0]

    logger.info("First token is taken")

    browser = get_driver(config)

    sequences.auth(browser, token)
    async with ClientSession() as session:
        root_consumer.add_on_startup(lambda _: logger.info("Bot ready to accept data"))
        root_consumer.add_listener(sequences.UrlHandler(driver=browser, conn=conn, session=session))
        root_consumer.add_on_shutdown(lambda _: logger.info("Bot is shutting down"))

        consumer.run()
