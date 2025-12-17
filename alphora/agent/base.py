from fastapi import Request
import asyncio
from alphora.models.llms.openai_like import OpenAILike
from typing import Optional, List, Any, overload, Union, Dict, Iterator
from alphora.server.stream_responser import DataStreamer

from uuid import uuid4
import functools
import os
import uuid
import logging
from dataclasses import dataclass
import time
import warnings

from alphora.models.llms.stream_helper import GeneratorOutput, BaseGenerator
from alphora.models.embedder.embedder_model import EmbeddingModel

from alphora.prompter import BasePrompt

from alphora.memory.base import BaseMemory
from alphora.memory.memories.short_term_memory import ShortTermMemory
import random
from alphora.prompter.postprocess.base import BasePostProcessor

from alphora.agent.stream import Stream

from typing import Optional, Type, TypeVar, Dict, Any

T = TypeVar('T', bound='BaseAgent')


class BaseAgent(object):
    def __init__(self,
                 callback: Optional[DataStreamer] = None,
                 llm: Optional[OpenAILike] = None,
                 verbose: bool = False,
                 memory: Optional[BaseMemory] = None,
                 **kwargs):

        self.init_params = {
            'callback': callback,
            'llm': llm,
            'verbose': verbose,
            'memory': memory,
            **kwargs
        }

        self.verbose = verbose
        self.memory = memory if memory is not None else ShortTermMemory()
        self.callback = callback
        self.llm = llm
        self.stream = Stream(callback=self.callback)

    def _reinitialize(self, **new_kwargs) -> None:
        merged_params = {**self.init_params, **new_kwargs}
        self.__init__(**merged_params)

    def derive(self, agent_cls_or_instance: Union[Type[T], T], **kwargs) -> T:
        """
        从当前 agent 派生出一个新的 agent 实例。

        - 如果传入类：创建新实例，参数 = self.init_params + kwargs
        - 如果传入实例：用 self.init_params + kwargs 更新该实例
        """
        # 合并参数：kwargs 优先级最高，然后是 self.init_params
        override_params = {**self.init_params, **kwargs}

        # 情况1：传入的是类
        if isinstance(agent_cls_or_instance, type) and issubclass(agent_cls_or_instance, BaseAgent):
            return agent_cls_or_instance(**override_params)

        # 情况2：传入的是实例
        elif isinstance(agent_cls_or_instance, BaseAgent):
            agent_cls_or_instance._reinitialize(**override_params)
            return agent_cls_or_instance

        else:
            raise TypeError(
                f"Unsupported type: {type(agent_cls_or_instance)}. "
                f"Expected a subclass or instance of BaseAgent."
            )

    def create_prompt(
            self,
            prompt: str = None,
            template_path: str = None,
            template_desc: str = "") -> BasePrompt:
        """
        快速创建提示词模板
        Args:
            template_path: 提示词路径（建议为相对路径）
            template_desc: 提示词描述
            prompt: Optional

        Returns: BasePrompt实例
        """

        if not self.llm:
            raise ValueError("LLM model is not configured")

        prompt_instance = BasePrompt(
            template_path=template_path,
            template_desc=template_desc,
            callback=self.callback,
        )

        try:
            prompt_instance.add_llm(model=self.llm)

            if prompt:
                prompt_instance.load_from_string(prompt=prompt)

            prompt_instance.verbose = self.verbose

            return prompt_instance

        except Exception as e:
            error_msg = f'Failed to create prompt: {str(e)}'
            logging.error(error_msg)
            raise ValueError(error_msg)

    def run(self, **kwargs) -> ...:
        """
        基于FDLayer开发的Agent，进行调用这个Agent的入口方法，后续并行调用Agent也需要使用该方法
        必须传入query，如果涉及其他参数要传递，请在agent里写一个辅助函数传入。
        """
        raise NotImplementedError(
            f"'{self.__class__.__name__}.run' must be implemented "
        )

    def to_api(self):
        """
        返回一个可直接用于 @app.post 的视图函数。
        支持 POST JSON 输入，自动注入 streamer 和原始配置。
        """
        agent_class = self.__class__
        init_kwargs = self._init_kwargs

        async def api_view(request: Request):
            input_data = await request.json()

            agent = agent_class(**init_kwargs)
            agent.callback = streamer

            asyncio.create_task(agent.run(input_data))

            return streamer.start_streaming_openai()

        return api_view

    def __or__(self, other):
        from chatbi.agent.foundation.utils.parallel import ParallelFoundationLayer
        """允许在FoundationLayer后面加入 | 实现并行"""
        if isinstance(other, FoundationLayer):
            return ParallelFoundationLayer([self, other])
        elif isinstance(other, ParallelFoundationLayer):
            other.agents.append(self)
            return other
        else:
            raise TypeError("The right-hand side of the 'or' must be an instance of FDLayer or Parallel FDlayer.")

