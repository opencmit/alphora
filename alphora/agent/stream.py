"""
因为改了异步，所有的同步方法都不允许使用了！！！
"""

from alphora.server.stream_responser import DataStreamer
from typing import Optional, List, Iterator
import random
import time
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess.base_pp import BasePostProcessor

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Stream:
    def __init__(self, callback: Optional[DataStreamer] = None):
        self.callback = callback

    async def astream_message(self,
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

        # 创建一个自定义生成器类
        class StringGenerator(BaseGenerator[GeneratorOutput]):
            def __init__(self, content: str, content_type: str, interval: float):
                super().__init__(content_type)
                self.content = content
                self.interval = interval

            async def agenerate(self) -> Iterator[GeneratorOutput]:
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
        await self.astream_to_response(generator)

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

        # 创建一个自定义生成器类
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
            print(f"\n[Stream stopped: {stop_reason}]")

    def stop(self, stop_reason: str = 'end') -> None:
        """
        终结流式输出
        """
        logger.warning(
            "当前使用同步方法 `stop`，无法向客户端发送流式响应；"
            "请改用异步方法 `astop`。"
            " [Synchronous `stop` does not support client streaming; use `astop` for API streaming.]"
        )

        print(f"\n[Stream stopped: {stop_reason}]")

    async def astream_to_response(self,
                                  generator: BaseGenerator,
                                  post_processors: List[BasePostProcessor] = []) -> str:
        """
        将生成器转为实际的字符串，同时发送流式输出

        :param generator:
        :param post_processors:
        """

        data_streamer: Optional[DataStreamer] = self.callback
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

                if content:
                    if data_streamer:
                        await data_streamer.send_data(content_type=content_type, content=content)
                    else:
                        print(content, end='', flush=True)
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
                    print(content, end='', flush=True)

            except Exception as e:
                print(f"Streaming Parsing Error: {str(e)}")
                content = ''

            response += content

        return response
