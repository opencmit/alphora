"""
agent = ReActAgent(
    llm=OpenAILike(),
    tools=[get_market_info, place_order, get_account],  # 直接传函数
    system_prompt="你是一个交易机器人...",
    enable_memory=True,
)

# 一行调用，自动处理工具执行循环
response = await agent.run("今天应该买还是卖？")

# 或者手动控制循环
async for step in agent.run_steps("今天应该买还是卖？"):
    print(f"Step: {step.action}")  # 可观察每一步
"""


from .base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.decorators import Tool
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from typing import Callable, List, Union, Dict


class ReActAgent(BaseAgent):

    def __init__(
            self,
            llm: OpenAILike,
            tools: List[Union[Tool, Callable]],
            system_prompt: str = "",
            max_iterations: int = 10,
            **kwargs
    ):
        super().__init__(llm=llm, **kwargs)

        self._registry = ToolRegistry()

        for tool in tools:
            self._registry.register(tool)

        self._executor = ToolExecutor(self._registry)

        if system_prompt == "":
            system_prompt = "你是一个AI专家，负责调用工具来帮助用户实现需求"

        # 创建 prompt
        self._prompt = self.create_prompt(
            system_prompt=system_prompt,
        )

        self._max_iterations = max_iterations

    async def run(self, query: str) -> str:
        """执行完整的工具调用循环"""
        for _ in range(self._max_iterations):
            response = await self._prompt.acall(
                query=query,
                tools=self._registry.get_openai_tools_schema()
            )

            if not response:  # 没有工具调用，返回文本
                return response.content

            # 执行工具
            await self._executor.execute(response)

        return "达到最大迭代次数"

