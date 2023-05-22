import asyncio
import json
import abc
from functools import partial
from typing import List

from loguru import logger
from pika import BlockingConnection

from app.consts import DEFAULT_QUEUE_NAME
from app.abc import Notifier, ListenerType, SkipException



class BaseNotifier(Notifier):
    def __init__(self, listeners: List[ListenerType] = None):
        self._listeners = listeners or []
        self._on_startup = []
        self._on_shutdown = []
        self.error_handlers = []

        self.add_on_shutdown(partial(self.close, self=self))

    def add_listener(self, listener: ListenerType):
        self._listeners.append(listener)

    def add_on_startup(self, listener: ListenerType):
        self._on_startup.append(listener)

    def add_on_shutdown(self, listener: ListenerType):
        self._on_shutdown.append(listener)

    def run_listeners(self, data, listeners):
        for listener in listeners:
            try:
                if asyncio.iscoroutine(listener):
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(listener)
                else:
                    listener(data)
            except SkipException:
                pass

    @abc.abstractmethod
    def inner_run(self):
        pass

    @abc.abstractmethod
    def close(self, data: dict):
        pass

    def run(self):
        # notifies all listeners when update comes
        self.run_listeners(data={}, listeners=self._on_startup)

        try:
            self.inner_run()
        except KeyboardInterrupt:
            self.run_listeners(data={}, listeners=self._on_shutdown)
            raise
        except Exception as exc:
            self.run_listeners(data={"exc": exc}, listeners=self.error_handlers)
            raise


class RabbitNotifier(BaseNotifier):
    """
    TODO: multithreading support!
    """
    def __init__(self, conn: BlockingConnection, queue_name: str = DEFAULT_QUEUE_NAME) -> None:
        self._conn = conn
        self._queue_name = queue_name

        super().__init__()

    def inner_run(self):
        channel = self._conn.channel()
        channel.queue_declare(queue=self._queue_name)

        def run_listeners(ch, method, properties, body):
            logger.info(f"Recieved a body: {body}")

            # it has to contain this data: URL
            self.run_listeners(data=json.loads(body), listeners=self._listeners)

            ch.basic_ack(delivery_tag=method.delivery_tag)
        channel.basic_consume(queue=self._queue_name, on_message_callback=run_listeners, auto_ack=True)

        # runs an infinite loop.
        channel.start_consuming()

    def close(self, _: dict):
        self._conn.close()
