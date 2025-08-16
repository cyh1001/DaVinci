# 内容过滤器的抽象类
from __future__ import annotations
import abc
import typing

from ...core import app, entities as core_entities
from . import entities


preregistered_filters: list[typing.Type[ContentFilter]] = []


def filter_class(
    name: str,
) -> typing.Callable[[typing.Type[ContentFilter]], typing.Type[ContentFilter]]:
    """Content filter class decorator

    Args:
        name (str): Filter name

    Returns:
        typing.Callable[[typing.Type[ContentFilter]], typing.Type[ContentFilter]]: Decorator
    """

    def decorator(cls: typing.Type[ContentFilter]) -> typing.Type[ContentFilter]:
        assert issubclass(cls, ContentFilter)

        cls.name = name

        preregistered_filters.append(cls)

        return cls

    return decorator


class ContentFilter(metaclass=abc.ABCMeta):
    """Content filter abstract class"""

    name: str

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    @property
    def enable_stages(self):
        """Enabled stages

        Default is the two stages before and after the message request to AI.

        entity.EnableStage.PRE: Before message request to AI, the content to check is the user's input message.
        entity.EnableStage.POST: After message request to AI, the content to check is the AI's reply message.
        """
        return [entities.EnableStage.PRE, entities.EnableStage.POST]

    async def initialize(self):
        """Initialize filter"""
        pass

    @abc.abstractmethod
    async def process(self, query: core_entities.Query, message: str = None, image_url=None) -> entities.FilterResult:
        """Process message

        It is divided into two stages, depending on the value of enable_stages.
        For content filters, you do not need to consider the stage of the message, you only need to check the message content.

        Args:
            message (str): Content to check
            image_url (str): URL of the image to check

        Returns:
            entities.FilterResult: Filter result, please refer to the documentation of entities.FilterResult class
        """
        raise NotImplementedError
