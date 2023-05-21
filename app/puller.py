import asyncio
import abc
from functools import partial
from typing import List, Any, Dict, Union, Type, Callable

from loguru import logger
from pika import BlockingConnection


class IListener(abc.ABC):
    @abc.abstractmethod
    def __call__(self, data: Dict[str, Any]):
        pass


ListenerType = Union[Type[IListener], Callable[[Dict[str, Any]], Any]]


class SkipException(Exception):
    pass


class Notifier(abc.ABC):
    @abc.abstractmethod
    def run(self):
        pass


class RabbitNotifier(Notifier):
    def __init__(self, connection: BlockingConnection, listeners: List[ListenerType] = None, queue_name: str = "url-queue"):
        self._listeners = listeners
        self._on_startup = []
        self._on_shutdown = []
        self.error_handlers = []
        self._conn = connection

        self._queue_name = queue_name

        self.add_on_shutdown(partial(self._close_connection, self=self))

    def add_listener(self, listener: ListenerType):
        self._listeners.append(listener)

    def _close_connection(self, _: dict) -> None:
        self._conn.close()

    def add_on_startup(self, listener: ListenerType):
        self._on_startup.append(listener)

    def add_on_shutdown(self, listener: ListenerType):
        self._on_shutdown.append(listener)

    def _run_listeners(self, data, listeners):
        for listener in listeners:
            try:
                if asyncio.iscoroutine(listener):
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(listener)
                else:
                    listener(data)
            except SkipException:
                pass

    def run(self):
        # notifies all listeners when update comes
        self._run_listeners(data={}, listeners=self._on_startup)

        channel = self._conn.channel()
        channel.queue_declare(queue=self._queue_name)

        def run_listeners(ch, method, properties, body):
            logger.info(f"Recieved a body: {body}")

            self._run_listeners(data={"url": body}, listeners=self._listeners)

        while 1:
            try:
                channel.basic_consume(queue=self._queue_name, on_message_callback=run_listeners, auto_ack=True)

                channel.start_consuming()
            except KeyboardInterrupt:
                self._run_listeners(data={}, listeners=self._on_shutdown)
                raise
            except Exception as exc:
                self._run_listeners(data={"exc": exc}, listeners=self.error_handlers)
                raise
