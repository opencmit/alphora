# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


from alphora.server.stream_responser import DataStreamer, StreamCallback
from alphora.cli.renderer import cli_print as _cli_print
from typing import Optional, List, Iterator
import random
import time
from contextlib import asynccontextmanager
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.agent.events import ContentType, StatusState, MetaKey
from alphora.postprocess.base_pp import BasePostProcessor

import logging
import asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Stream:
    def __init__(self, callback: Optional[StreamCallback] = None):
        self.callback = callback

    async def astream_message(self,
                              content: str,
                              content_type: str = "char",
                              interval: float = 0,
                              meta: Optional[dict] = None) -> None:
        """
        给 OpenAI 兼容的接口发送流式消息
        Args:
            content: String 对应的消息内容
            content_type: char(character), think(reasoning), result, sql, chart等
            interval: 流式的发送间隔（秒）
            meta: 可选的开放结构化元数据，原样透传到客户端 ``delta.meta``。
                约定保留键：``id``(block 分组键)、``state``(running/done/error)、
                ``agent_id``(子智能体分组)、``name``(工具名) 等；可塞任意 key/value。
                注意：当 interval>0 模拟逐字流式时，meta 会随每个分片一并下发。
        """
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception as e:
                raise TypeError("Content must be a string")

        if interval < 0:
            raise ValueError("Interval must be non-negative")

        # 创建一个自定义生成器类
        class StringGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, content: str, content_type: str, interval: float, meta: Optional[dict]):
                super().__init__(content_type)
                self.content = content
                self.interval = interval
                self.meta = meta

            async def agenerate(self) -> Iterator[GeneratorOutput]:
                if self.interval > 0:
                    # 模拟流式输出，每次输出1-5个字符
                    index = 0
                    while index < len(self.content):
                        num_chars = random.randint(1, 5)
                        chunk = self.content[index:index + num_chars]
                        index += num_chars

                        # time.sleep(self.interval)  # 260402修复

                        #  确保每次 chunk 产出之间都是真正的异步让出，而不是阻塞事件循环，否则缺少异步让出时机，
                        #  导致 SSE 消费端 data_generator() 拿不到调度机会，就会出现前面都攒着，最后一次性喷给客户端。

                        await asyncio.sleep(self.interval)

                        yield GeneratorOutput(content=chunk, content_type=self.content_type, meta=self.meta)
                else:
                    yield GeneratorOutput(content=self.content, content_type=self.content_type, meta=self.meta)

        # 创建并使用生成器
        generator = StringGenerator(content, content_type, interval, meta)
        await self.astream_to_response(generator)

    async def astream_status(self,
                             content: str,
                             *,
                             id: Optional[str] = None,
                             state: str = StatusState.RUNNING,
                             meta: Optional[dict] = None,
                             interval: float = 0) -> None:
        """发送一条 ``status`` 消息，并把 ``id`` / ``state`` 写进 meta。

        前端按同一个 ``id`` 把多条 status 视作同一个块原地更新，并据 ``state``
        渲染"进行中 / 已完成 / 出错"。

        Args:
            content: 状态文案。
            id: block 分组键；同一活动的多次状态更新传同一个 id。
            state: 生命周期状态，见 :class:`StatusState`（running/done/error 等）。
            meta: 额外的自由元数据，会与 id/state 合并。
            interval: >0 时逐字流式。
        """
        merged: dict = dict(meta) if meta else {}
        if id is not None:
            merged[str(MetaKey.ID)] = id
        merged[str(MetaKey.STATE)] = str(state)
        await self.astream_message(
            content=content,
            content_type=str(ContentType.STATUS),
            interval=interval,
            meta=merged,
        )

    @asynccontextmanager
    async def status(self,
                     content: str,
                     *,
                     id: str,
                     done_content: Optional[str] = None,
                     error_content: Optional[str] = None,
                     meta: Optional[dict] = None):
        """status 生命周期上下文管理器：进入发 ``running``，正常退出发 ``done``，异常发 ``error``。

        调用方无需手动维护状态机::

            async with self.stream.status("启动沙箱", id="sandbox"):
                await sandbox.start()
            # 退出时自动发送 done（done_content 或原文案）

        Args:
            content: 进入时（running）的文案。
            id: block 分组键（必填，用于把 running/done/error 收拢为同一块）。
            done_content: 正常结束时的文案；缺省复用 ``content``。
            error_content: 出错时的文案模板；缺省用 "{content} 失败：{error}"。
            meta: 额外的自由元数据，全程合并下发。
        """
        await self.astream_status(content, id=id, state=StatusState.RUNNING, meta=meta)
        try:
            yield
        except Exception as e:
            err = error_content if error_content is not None else f"{content} 失败：{e}"
            await self.astream_status(err, id=id, state=StatusState.ERROR, meta=meta)
            raise
        else:
            await self.astream_status(
                done_content if done_content is not None else content,
                id=id,
                state=StatusState.DONE,
                meta=meta,
            )

    async def astream_tool_result(self,
                                  content: str,
                                  *,
                                  tool_call_id: Optional[str] = None,
                                  tool_name: Optional[str] = None,
                                  ok: bool = True,
                                  meta: Optional[dict] = None,
                                  interval: float = 0) -> None:
        """发送工具执行结果（stdout/stderr），并用 ``tool_call_id`` 关联回对应的 tool_call。

        前端用 ``meta.id``(=tool_call_id) 把 ``tool_call`` / ``tool_call_args`` /
        本结果收拢为同一个工具块，避免并行或缺结果时错位。

        Args:
            content: 结果文案。
            tool_call_id: 对应 LLM 返回的 tool_call id（即 block 分组键）。
            tool_name: 工具名，写入 meta.name 便于展示。
            ok: True→stdout，False→stderr。
            meta: 额外的自由元数据。
            interval: >0 时逐字流式。
        """
        merged: dict = dict(meta) if meta else {}
        if tool_call_id:
            merged[str(MetaKey.ID)] = tool_call_id
        if tool_name:
            merged[str(MetaKey.NAME)] = tool_name
        await self.astream_message(
            content=content,
            content_type=str(ContentType.STDOUT) if ok else str(ContentType.STDERR),
            interval=interval,
            meta=merged or None,
        )

    def stream_message(self,
                       content: str,
                       content_type: str = "char",
                       interval: float = 0) -> None:
        """
        给 OpenAI 兼容的接口发送流式消息
        Args:
            content: String 对应的消息内容
            content_type: char(character), think(reasoning), result, sql, chart等
            interval: 流式的发送间隔（秒）
        """
        if not isinstance(content, str):
            try:
                content = str(content)
            except Exception as e:
                raise TypeError("Content must be a string")

        if interval < 0:
            raise ValueError("Interval must be non-negative")

        class StringGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, content: str, content_type: str, interval: float):
                super().__init__(content_type)
                self.content = content
                self.interval = interval

            def generate(self) -> Iterator[GeneratorOutput]:
                if self.interval > 0:
                    # 模拟流式输出，每次输出1-5个字符
                    index = 0
                    while index < len(self.content):
                        num_chars = random.randint(1, 5)
                        chunk = self.content[index:index + num_chars]
                        index += num_chars
                        time.sleep(self.interval)
                        yield GeneratorOutput(content=chunk, content_type=self.content_type)
                else:
                    yield GeneratorOutput(content=self.content, content_type=self.content_type)

        # 创建并使用生成器
        generator = StringGenerator(content, content_type, interval)
        self.stream_to_response(generator)

    async def astop(self, stop_reason: str = 'end') -> None:
        """
        终结流式输出
        """
        if self.callback:
            await self.callback.stop(stop_reason=stop_reason)
        else:
            _cli_print(f"\n[Stream stopped: {stop_reason}]\n")

    async def astream_usage(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        """
        流式输出用量
        """
        if self.callback:
            await self.callback.usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens)
        else:
            pass

    def stop(self, stop_reason: str = 'end') -> None:
        """
        终结流式输出
        """
        logger.warning(
            "当前使用同步方法 `stop`，无法向客户端发送流式响应；"
            "请改用异步方法 `astop`。"
            " [Synchronous `stop` does not support client streaming; use `astop` for API streaming.]"
        )

        _cli_print(f"\n[Stream stopped: {stop_reason}]\n")

    async def astream_to_response(self,
                                  generator: BaseGenerator,
                                  post_processors: List[BasePostProcessor] = []) -> str:
        """
        将生成器转为实际的字符串，同时发送流式输出

        :param generator:
        :param post_processors:
        """

        data_streamer: Optional[StreamCallback] = self.callback
        response = ''

        # 应用所有后处理器
        processed_generator = generator
        for processor in post_processors:
            processed_generator = processor(processed_generator)

        # 处理最终的生成器
        async for output_content in processed_generator:
            try:
                content = output_content.content
                content_type = output_content.content_type
                meta = getattr(output_content, "meta", None)

                if content:
                    if data_streamer:
                        await data_streamer.send_data(content_type=content_type, content=content, meta=meta)
                    else:
                        _cli_print(content, ctype=content_type)
                        continue

            except Exception as e:
                print(f"Streaming Parsing Error: {str(e)}")
                content = ''

            response += content

        return response

    @staticmethod
    def stream_to_response(generator: BaseGenerator,
                           post_processors: List[BasePostProcessor] = []) -> str:
        """
        将生成器转为实际的字符串，但是同步方法中调用不会发送到接口！！！

        :param generator:
        :param post_processors:
        """
        logger.warning(
            "当前使用同步方法 `stream_to_response`，无法向客户端发送流式响应；"
            "请改用异步方法 `astream_to_response`。"
            " [Synchronous `stream_to_response` does not support client streaming; use `astream_to_response` for API streaming.]"
        )

        response = ''

        # 应用所有后处理器
        processed_generator = generator
        for processor in post_processors:
            processed_generator = processor(processed_generator)

        # 处理最终的生成器
        for output_content in processed_generator:
            try:
                content = output_content.content
                content_type = output_content.content_type

                if content:
                    _cli_print(content, ctype=content_type)

            except Exception as e:
                print(f"Streaming Parsing Error: {str(e)}")
                content = ''

            response += content

        return response
