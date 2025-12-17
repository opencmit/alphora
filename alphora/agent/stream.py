from alphora.server.stream_responser import DataStreamer
from typing import Optional, List, Any, Iterator
import random
import time
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.prompter.postprocess.base import BasePostProcessor


class Stream:
    def __init__(self, callback: Optional[DataStreamer] = None):
        self.callback = callback
        self.post_processors: List[BasePostProcessor] = []

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

    def stop(self, stop_reason: str = 'end') -> None:
        """
        终结流式输出
        """
        if self.callback:
            self.callback.stop(stop_reason=stop_reason)
        else:
            print(f"\n[Stream stopped: {stop_reason}]")

    async def astream_to_response(self, generator: BaseGenerator) -> str:
        """
        将生成器转为实际的字符串，同时发送流式输出(如果有DS)
        Args:
            generator: BaseGenerator
        Returns: String
        """

        data_streamer: Optional[DataStreamer] = self.callback
        response = ''

        # 应用所有后处理器
        processed_generator = generator
        for processor in self.post_processors:
            processed_generator = processor(processed_generator)

        # 处理最终的生成器
        async for output_content in processed_generator:
            try:
                content = output_content.content
                content_type = output_content.content_type

                if content:
                    if data_streamer:
                        await data_streamer.send_data(content_type=content_type, content=content)

            except Exception as e:
                print(f"Streaming Parsing Error: {str(e)}")
                content = ''

            response += content

        return response

    def stream_to_response(self, generator: BaseGenerator) -> str:
        """
        将生成器转为实际的字符串，同时发送流式输出(如果有DS)
        Args:
            generator: BaseGenerator
        Returns: String
        """

        data_streamer: Optional[DataStreamer] = self.callback
        response = ''

        # 应用所有后处理器
        processed_generator = generator
        for processor in self.post_processors:
            processed_generator = processor(processed_generator)

        # 处理最终的生成器
        for output_content in processed_generator:
            try:
                content = output_content.content
                content_type = output_content.content_type

                if content:
                    if data_streamer:
                        data_streamer.send_data(content_type=content_type, content=content)

            except Exception as e:
                print(f"Streaming Parsing Error: {str(e)}")
                content = ''

            response += content

        return response
