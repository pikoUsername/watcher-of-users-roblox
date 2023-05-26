from dotenv import load_dotenv
from loguru import logger

from app.services.consumers import MultiThreadedConsumer
from app.log import configure_logging
from app.config import get_settings
from app import sequences
from app.services.consumers import ReconnectingURLConsumer

import nest_asyncio

from app.services.db import get_db_conn

nest_asyncio.apply()


async def main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)
    db = await get_db_conn(config)

    kw = {
        "amqp_url": config.queue_dsn,
        "queue": config.queue_name,
        "exchange": config.exchange_name,
        "routing": config.queue_name,
        "workflow_data": {"settings": config, "conn": db}
    }

    root_consumer = MultiThreadedConsumer(**kw)
    consumer = ReconnectingURLConsumer(
        consumer=root_consumer,
        **kw,
    )

    root_consumer.add_listener(sequences.DBHandler())
    root_consumer.add_listener(sequences.UrlHandler())

    consumer.run()
