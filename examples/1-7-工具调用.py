import asyncio
from typing import List, Optional
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


async def main():

    await demo_tools()


if __name__ == "__main__":
    asyncio.run(main())