import asyncio
import inspect
import threading
from contextvars import Context, copy_context
from platform import uname

from loguru import logger
from selenium.common import StaleElementReferenceException

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


def in_wsl() -> bool:
    return 'microsoft-standard' in uname().release


def presence_of_any_text_in_element(locator):
    """
    It returns the text of the element

    :param locator:
    :return:
    """
    def _predicate(driver):
        try:
            element_text = driver.find_element(*locator).text
            if element_text != "":
                return element_text
            return False
        except StaleElementReferenceException:
            return False

    return _predicate
