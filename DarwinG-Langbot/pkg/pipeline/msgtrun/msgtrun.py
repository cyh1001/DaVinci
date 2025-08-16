from __future__ import annotations

from .. import stage, entities
from ...core import entities as core_entities
from . import truncator
from ...utils import importutil

from . import truncators

importutil.import_modules_in_pkg(truncators)


@stage.stage_class('ConversationMessageTruncator')
class ConversationMessageTruncator(stage.PipelineStage):
    """Conversation message truncator

    Used to truncate the conversation message chain to adapt to the LLM message length limit.
    """

    trun: truncator.Truncator

    async def initialize(self, pipeline_config: dict):
        use_method = 'round'

        for trun in truncator.preregistered_truncators:
            if trun.name == use_method:
                self.trun = trun(self.ap)
                break
        else:
            raise ValueError(f'Unknown truncator: {use_method}')

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """Process"""
        query = await self.trun.truncate(query)

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
