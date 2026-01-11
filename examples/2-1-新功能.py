"""
Alphora 新功能示例

展示新增的功能模块：
1. 工具调用系统
2. 结构化输出
3. 重试与容错
4. 调用链追踪
5. 上下文管理
"""

import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field

# ============================================================
# 1. 工具调用系统示例
# ============================================================

from alphora.tools import Tool, ToolResult, ToolRegistry, tool, ToolParameter
from alphora.tools.decorators import ToolSet


# 方式1：使用装饰器定义工具
@tool(description="搜索互联网获取信息")
async def search(query: str, limit: int = 10) -> str:
    """
    搜索互联网

    Args:
        query: 搜索关键词
        limit: 返回结果数量
    """
    # 模拟搜索
    return f"搜索'{query}'的前{limit}条结果: [结果1, 结果2, ...]"


@tool(description="计算数学表达式")
def calculate(expression: str) -> float:
    """
    计算数学表达式

    Args:
        expression: 数学表达式，如 "2 + 3 * 4"
    """
    try:
        result = eval(expression)
        return float(result)
    except Exception as e:
        raise ValueError(f"计算错误: {e}")


# 方式2：使用类定义工具
class WeatherTool(Tool):
    name = "get_weather"
    description = "获取指定城市的天气信息"

    def define_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="city",
                type=str,
                description="城市名称"
            ),
            ToolParameter(
                name="unit",
                type=str,
                description="温度单位",
                required=False,
                default="celsius",
                enum=["celsius", "fahrenheit"]
            )
        ]

    async def execute(self, city: str, unit: str = "celsius") -> ToolResult:
        # 模拟天气查询
        weather_data = {
            "city": city,
            "temperature": 25 if unit == "celsius" else 77,
            "unit": unit,
            "condition": "晴天"
        }
        return ToolResult.ok(weather_data)


# 方式3：使用工具集
math_tools = ToolSet("math", "数学计算工具集")

@math_tools.tool
def add(a: int, b: int) -> int:
    """两数相加"""
    return a + b

@math_tools.tool
def multiply(a: int, b: int) -> int:
    """两数相乘"""
    return a * b


async def demo_tools():
    """工具系统演示"""
    print("=" * 60)
    print("1. 工具调用系统演示")
    print("=" * 60)

    # 使用装饰器定义的工具
    result = await search(query="Python教程", limit=5)
    print(f"搜索结果: {result}")

    # 使用类定义的工具
    weather_tool = WeatherTool()
    result = await weather_tool(city="北京")
    print(f"天气信息: {result}")

    # 获取OpenAI格式的工具定义
    print("\n工具定义（OpenAI格式）:")
    print(weather_tool.to_openai_function())

    # 使用工具集
    print(f"\n数学工具集: {math_tools.get_tools()}")
    print()


# ============================================================
# 4. 调用链追踪示例
# ============================================================

from alphora.tracing import Tracer, trace, get_current_span

# 创建追踪器
tracer = Tracer(service_name="demo_service")


@tracer.trace("process_order")
async def process_order(order_id: str):
    """处理订单"""
    span = get_current_span()
    if span:
        span.set_tag("order_id", order_id)

    # 调用子操作
    await validate_order(order_id)
    await calculate_total(order_id)
    await send_notification(order_id)

    return f"订单 {order_id} 处理完成"


@tracer.trace("validate_order")
async def validate_order(order_id: str):
    """验证订单"""
    await asyncio.sleep(0.1)  # 模拟验证
    return True


@tracer.trace("calculate_total")
async def calculate_total(order_id: str):
    """计算总价"""
    await asyncio.sleep(0.05)  # 模拟计算
    return 299.99


@tracer.trace("send_notification")
async def send_notification(order_id: str):
    """发送通知"""
    await asyncio.sleep(0.02)  # 模拟发送
    return True


async def demo_tracing():
    """调用链追踪演示"""
    print("=" * 60)
    print("4. 调用链追踪演示")
    print("=" * 60)

    # 使用追踪上下文
    async with tracer.start_trace("demo_trace") as trace_ctx:
        result = await process_order("ORD-12345")
        print(f"处理结果: {result}")

        # 打印追踪树
        print("\n追踪树:")
        print(trace_ctx.print_tree())

    print()


# ============================================================
# 综合示例：使用新功能构建Agent
# ============================================================

from alphora.agent.base_agent import BaseAgent
from alphora.tools.executor import ToolAgentMixin


class EnhancedAgent(BaseAgent, ToolAgentMixin):
    """
    增强型Agent示例
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup_tools()
        self._setup_custom_tools()

    def _setup_custom_tools(self):
        """设置自定义工具"""

        @self.tool(description="获取当前时间")
        async def get_time() -> str:
            """获取当前时间"""
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        @self.tool(description="计算两个数的和")
        async def add_numbers(a: float, b: float) -> float:
            """
            计算两数之和

            Args:
                a: 第一个数
                b: 第二个数
            """
            return a + b

    @tracer.trace("enhanced_chat")
    async def chat(self, query: str) -> str:
        """增强的对话方法"""
        span = get_current_span()
        if span:
            span.set_tag("query_length", len(query))

        # 这里可以集成工具调用
        tools_schema = self.get_tools_schema()
        print(tools_schema)
        span.set_tag("available_tools", len(tools_schema)) if span else None

        # 模拟响应
        return f"收到您的问题: {query}"


async def demo_enhanced_agent():
    """增强型Agent演示"""
    print("=" * 60)
    print("6. 增强型Agent演示")
    print("=" * 60)

    agent = EnhancedAgent()

    # 显示可用工具
    print("可用工具:")
    for tool_def in agent.get_tools_schema():
        print(f"  - {tool_def['function']['name']}: {tool_def['function']['description']}")

    # 使用追踪的对话
    async with tracer.start_trace("agent_demo") as trace_ctx:
        response = await agent.chat("你好，请问现在几点了？")
        print(f"\nAgent响应: {response}")
        print("\n追踪信息:")
        print(trace_ctx.print_tree())

    print()


# ============================================================
# 主函数
# ============================================================

async def main():
    """运行所有演示"""
    print("\n" + "=" * 60)
    print("    Alphora 新功能演示")
    print("=" * 60 + "\n")

    # 1. 工具系统
    await demo_tools()

    # 4. 调用链追踪
    await demo_tracing()

    # 6. 增强型Agent
    await demo_enhanced_agent()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())