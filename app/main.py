from dotenv import load_dotenv

from app.services.consumers import MultiThreadedConsumer, URLConsumer
from app.log import configure_logging
from app.config import get_settings
from app import handlers
from app.services.consumers import ReconnectingURLConsumer

import nest_asyncio

nest_asyncio.apply()


async def main():
    load_dotenv()

    config = get_settings()

    configure_logging(config.loggers)
    # to make it use only one db
    # db = await get_db_conn(config)

    kw = {
        "amqp_url": config.queue_dsn,
        "queue": config.queue_name,
        "exchange": config.exchange_name,
        "routing": config.queue_name,
        "workflow_data": {"settings": config}
    }
    root_consumer = URLConsumer(**kw)
    # root_consumer = MultiThreadedConsumer(**kw)
    consumer = ReconnectingURLConsumer(
        consumer=root_consumer,
        **kw,
    )

    root_consumer.add_listener(handlers.PublisherHandler())
    root_consumer.add_listener(handlers.DBHandler())
    root_consumer.add_listener(handlers.UrlHandler())

    consumer.run()
