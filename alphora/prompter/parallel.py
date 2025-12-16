from alphora.prompter.base import BasePrompt, ResponseWithReasoning
from typing import Union, List, Optional, Callable, Any, Tuple
import threading

from chatbi.models.message import Message
from chatbi.models.llm.stream_helper import BaseGenerator


class ParallelPrompts:
    def __init__(self, prompts):
        self.prompts = prompts  # 存放BasePrompt实例List

    def __or__(self, other):
        if isinstance(other, BasePrompt):
            self.prompts.append(other)
            return self
        elif isinstance(other, ParallelPrompts):
            self.prompts.extend(other.prompts)
            return self
        else:
            raise TypeError("The right-hand side of the 'or' must be an instance of BasePrompt or ParallelPrompts.")

    def pcall(
            self,
            query: Union[str, List[str]] = None,
            is_stream: bool = True,
            multimodal_message: Union[Message, List[Message]] = None,
            return_generator: bool = False,
            content_type: str = 'text',
            postprocessor: Union[
                "BasePostProcessor",
                Callable[[BaseGenerator], BaseGenerator],
                List["BasePostProcessor"],
                List[Callable[[BaseGenerator], BaseGenerator]],
                None
            ] = None,
            enable_thinking: bool = False,
    ) -> Tuple[Union[BaseGenerator, str, ResponseWithReasoning], ...]:
        """
        并行调用所有BasePrompt的call方法，支持与BasePrompt.call一致的参数

        Args:
            query: 单个查询字符串（所有prompt共用）或与prompt数量匹配的查询列表（逐个对应）
            is_stream: 是否启用流式输出
            multimodal_message: 单个多模态消息（所有prompt共用）或与prompt数量匹配的消息列表（逐个对应）
            return_generator: 是否返回生成器（而非最终结果）
            content_type: 输出内容类型
            postprocessor: 后处理器（单个处理器所有prompt共用，或列表形式逐个对应）
            enable_thinking: 是否启用思考过程记录

        Returns:
            按prompt顺序排列的结果元组，每个元素为对应prompt的call方法返回值
        """
        # 参数校验：确保列表参数长度与prompt数量一致
        prompt_count = len(self.prompts)
        if isinstance(query, list) and len(query) != prompt_count:
            raise ValueError(f"query列表长度（{len(query)}）与prompt数量（{prompt_count}）不匹配")
        if isinstance(multimodal_message, list) and len(multimodal_message) != prompt_count:
            raise ValueError(f"multimodal_message列表长度（{len(multimodal_message)}）与prompt数量（{prompt_count}）不匹配")
        if isinstance(postprocessor, list) and len(postprocessor) != prompt_count:
            raise ValueError(f"postprocessor列表长度（{len(postprocessor)}）与prompt数量（{prompt_count}）不匹配")

        results = [None] * prompt_count  # 按顺序存储结果
        threads = []
        output_lock = threading.Lock()  # 确保结果写入线程安全

        def thread_run(
                prompt: BasePrompt,
                index: int,
                query_inner: str,
                msg_inner: Optional[Message],
                postprocessor_inner: Any
        ):
            """线程执行函数：调用单个prompt的call方法并存储结果"""
            try:
                # 调用对应prompt的call方法，传入当前线程的参数
                result = prompt.call(
                    query=query_inner,
                    is_stream=is_stream,
                    multimodal_message=msg_inner,
                    return_generator=return_generator,
                    content_type=content_type,
                    postprocessor=postprocessor_inner,
                    enable_thinking=enable_thinking
                )
                with output_lock:
                    results[index] = result
            except Exception as e:
                with output_lock:
                    results[index] = f"调用失败：{str(e)}"
                raise RuntimeError(f"Prompt[{index}]调用出错：{str(e)}") from e

        # 为每个prompt创建线程
        for index, prompt in enumerate(self.prompts):
            # 处理单个参数/列表参数的分配
            query_inner = query[index] if isinstance(query, list) else query
            msg_inner = multimodal_message[index] if isinstance(multimodal_message, list) else multimodal_message
            postprocessor_inner = postprocessor[index] if isinstance(postprocessor, list) else postprocessor

            # 创建并启动线程
            thread = threading.Thread(
                target=thread_run,
                args=(prompt, index, query_inner, msg_inner, postprocessor_inner),
                daemon=True  # 守护线程：主程序退出时自动结束
            )
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        return tuple(results)  # 转换为元组返回（确保不可变，保持顺序）

