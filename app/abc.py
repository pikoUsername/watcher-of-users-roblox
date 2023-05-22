import abc
from typing import Union, Type, Callable, Dict, Any


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
