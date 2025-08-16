# 转发消息组件
from __future__ import annotations


from .. import strategy as strategy_model
from ....core import entities as core_entities
from ....platform.types import message as platform_message


ForwardMessageDiaplay = platform_message.ForwardMessageDiaplay
Forward = platform_message.Forward


@strategy_model.strategy_class('forward')
class ForwardComponentStrategy(strategy_model.LongTextStrategy):
    async def process(self, message: str, query: core_entities.Query) -> list[platform_message.MessageComponent]:
        display = ForwardMessageDiaplay(
            title='Group chat history',
            brief='[Chat history]',
            source='Chat history',
            preview=['User: ' + message],
            summary='View 1 forwarded message',
        )

        node_list = [
            platform_message.ForwardMessageNode(
                sender_id=query.adapter.bot_account_id,
                sender_name='User',
                message_chain=platform_message.MessageChain([message]),
            )
        ]

        forward = Forward(display=display, node_list=node_list)

        return [forward]
