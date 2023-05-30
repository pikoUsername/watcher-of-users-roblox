import asyncio
import inspect
import threading
from platform import uname
from urllib.parse import urlparse

from loguru import logger

from .exceptions import SkipException, CancelException


def _get_spec(func: callable):
    while hasattr(func, '__wrapped__'):  # Try to resolve decorated callbacks
        func = func.__wrapped__
    return inspect.getfullargspec(func)


def _check_spec(spec: inspect.FullArgSpec, kwargs: dict):
    if spec.varkw:
        return kwargs

    return {k: v for k, v in kwargs.items() if k in set(spec.args + spec.kwonlyargs)}


def run_listeners(data, listeners, key: str = '__call__'):
    for listener in listeners:
        try:
            func = getattr(listener, key)
            spec = _get_spec(func)
            workflow = _check_spec(spec, data)
            if asyncio.iscoroutinefunction(func):
                loop = asyncio.get_event_loop()
                if threading.current_thread().name != "MainThread":
                    logger.debug("Executing in thread")
                    logger.debug(f"Workflow of task: {workflow}, Function: {func}")

                    task = func(**workflow)
                    loop.run_until_complete(task)

                    logger.debug("Task in thread has been completed")
                else:
                    loop.run_until_complete(func(**workflow))
            else:
                func(**workflow)

        except SkipException:
            pass
        except CancelException:
            break


def in_wsl() -> bool:
    return 'microsoft-standard' in uname().release


def validate_url(url: str):
    parsed_url = urlparse(url)
    return bool(parsed_url.scheme and parsed_url.netloc)
