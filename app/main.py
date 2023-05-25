from dotenv import load_dotenv
from loguru import logger

from app.connector import URLConsumer
from app.log import configure_logging
from app.config import get_settings
from app import sequences
from app.connector import ReconnectingURLConsumer

import nest_asyncio
nest_asyncio.apply()


async def main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)
    kw = {
        "amqp_url": config.queue_dsn,
        "queue": config.queue_name,
        "exchange": config.exchange_name,
        "routing": config.queue_name,
        "workflow_data": {"settings": config}
    }

    root_consumer = URLConsumer(**kw)
    consumer = ReconnectingURLConsumer(
        consumer=root_consumer,
        **kw,
    )

    logger.info("Created Tokens table")

    root_consumer.add_listener(sequences.DBHandler())
    root_consumer.add_listener(sequences.UrlHandler())

    consumer.run()
