import asyncio
import json
import abc
from functools import partial
from typing import List

from loguru import logger
from pika import BlockingConnection

from app.consts import DEFAULT_QUEUE_NAME, EXHANGE_DEFAULT_NAME
from app.abc import Notifier, ListenerType, SkipException



class BaseNotifier(Notifier):
    def __init__(self, listeners: List[ListenerType] = None):
        self._listeners = listeners or []
        self._on_startup = []
        self._on_shutdown = []
        self.error_handlers = []

        self.add_on_shutdown(self.close)

    def add_listener(self, listener: ListenerType):
        self._listeners.append(listener)

    def add_on_startup(self, listener: ListenerType):
        self._on_startup.append(listener)

    def add_on_shutdown(self, listener: ListenerType):
        self._on_shutdown.append(listener)

    def run_listeners(self, data, listeners):
        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    loop = asyncio.get_running_loop()
                    loop.run_until_complete(listener)
                if hasattr(listener, "__call__"):
                    if asyncio.iscoroutinefunction(listener.__call__):
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(listener.__call__(data))
                        loop.run_until_complete(task)
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
    def __init__(self,
                 conn: BlockingConnection,
                 queue_name: str = DEFAULT_QUEUE_NAME,
                 exchange_name: str = EXHANGE_DEFAULT_NAME
                 ) -> None:
        self._conn = conn
        self._queue_name = queue_name
        self._exchange_name = exchange_name

        super().__init__()

    def inner_run(self):
        channel = self._conn.channel()
        channel.exchange_declare(
            exchange=self._exchange_name,
            exchange_type="direct",
            passive=False,
            durable=True,
            auto_delete=False,
        )
        channel.queue_declare(queue=self._queue_name)
        channel.queue_bind(queue=self._queue_name, exchange=self._exchange_name)
        channel.basic_qos(prefetch_count=2)

        def run_listeners(ch, method, properties, body: bytes):
            logger.info(f"Recieved a body: {body}")

            # it has to contain this data: URL
            self.run_listeners(data=json.loads(body), listeners=self._listeners)

        channel.basic_consume(queue=self._queue_name, on_message_callback=run_listeners, auto_ack=True)

        try:
            # runs an infinite loop.
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
            self.close(data={})

    def close(self, data: dict):
        self._conn.close()


class RabbitMultiThreadNotifier(BaseNotifier):
    pass
