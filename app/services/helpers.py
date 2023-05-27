import asyncio
import inspect
from platform import uname

from loguru import logger

from .exceptions import SkipException


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

                logger.debug(f"{func} workflow: {workflow}")

                loop.run_until_complete(func(**workflow))
            else:
                func(**workflow)

        except SkipException:
            pass


def in_wsl() -> bool:
    return 'microsoft-standard' in uname().release
