"""
Alphora Tools Component - 工具系统示例

本文件演示工具系统的使用：
1. Tool 类基础
2. @tool 装饰器
3. 工具参数定义
4. ToolExecutor 执行器
5. ToolAgentMixin 混入
6. 工具调用流程
7. 异步工具
8. 工具组合

工具系统让 LLM 能够调用外部函数，实现与真实世界的交互
"""

import asyncio
import os
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from alphora.tools import Tool, tool, ToolExecutor
from alphora.tools import ToolAgentMixin
from alphora.agent import BaseAgent


# ============================================================
# 示例 1: Tool 类基础
# ============================================================
def example_1_tool_basics():
    """
    Tool 类的基本使用

    Tool 是工具系统的核心类，定义了工具的名称、描述、参数和执行函数
    """
    print("=" * 60)
    print("示例 1: Tool 类基础")
    print("=" * 60)

    # 方式1：使用字典定义参数
    def add_numbers(a: int, b: int) -> int:
        """两数相加"""
        return a + b

    add_tool = Tool(
        name="add",
        description="将两个数字相加",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "第一个数字"},
                "b": {"type": "integer", "description": "第二个数字"}
            },
            "required": ["a", "b"]
        },
        func=add_numbers
    )

    print(f"\n工具名称: {add_tool.name}")
    print(f"工具描述: {add_tool.description}")
    print(f"参数定义: {json.dumps(add_tool.parameters, indent=2, ensure_ascii=False)}")

    # 执行工具
    result = add_tool.execute(a=5, b=3)
    print(f"\n执行 add(5, 3) = {result}")

    # 方式2：使用 Pydantic 模型定义参数
    class MultiplyParams(BaseModel):
        """乘法参数"""
        x: int = Field(description="第一个数字")
        y: int = Field(description="第二个数字")

    def multiply(x: int, y: int) -> int:
        return x * y

    multiply_tool = Tool(
        name="multiply",
        description="将两个数字相乘",
        parameters=MultiplyParams,  # 使用 Pydantic 模型
        func=multiply
    )

    result = multiply_tool.execute(x=4, y=7)
    print(f"执行 multiply(4, 7) = {result}")

    return add_tool, multiply_tool


# ============================================================
# 示例 2: @tool 装饰器
# ============================================================
def example_2_tool_decorator():
    """
    @tool 装饰器的使用

    装饰器方式更简洁，自动从函数签名推断参数
    """
    print("\n" + "=" * 60)
    print("示例 2: @tool 装饰器")
    print("=" * 60)

    # 基本使用
    @tool
    def get_weather(city: str, unit: str = "celsius") -> str:
        """
        获取指定城市的天气

        Args:
            city: 城市名称
            unit: 温度单位，celsius 或 fahrenheit
        """
        # 模拟天气数据
        weather_data = {
            "北京": {"temp": 15, "condition": "晴"},
            "上海": {"temp": 18, "condition": "多云"},
            "广州": {"temp": 25, "condition": "阴"},
        }

        data = weather_data.get(city, {"temp": 20, "condition": "未知"})
        temp = data["temp"]
        if unit == "fahrenheit":
            temp = temp * 9/5 + 32

        return f"{city}天气：{data['condition']}，温度 {temp}°{'F' if unit == 'fahrenheit' else 'C'}"

    print(f"\n工具名称: {get_weather.name}")
    print(f"工具描述: {get_weather.description}")

    # 执行
    result = get_weather.execute(city="北京")
    print(f"结果: {result}")

    result = get_weather.execute(city="上海", unit="fahrenheit")
    print(f"结果: {result}")

    # 自定义名称和描述
    @tool(name="search_web", description="在网络上搜索信息")
    def search(query: str, max_results: int = 5) -> List[str]:
        """搜索网络"""
        # 模拟搜索结果
        return [f"搜索结果 {i+1}: {query}" for i in range(max_results)]

    print(f"\n自定义工具名称: {search.name}")
    results = search.execute(query="Python教程", max_results=3)
    print(f"搜索结果: {results}")

    return get_weather, search


# ============================================================
# 示例 3: 复杂参数定义
# ============================================================
def example_3_complex_parameters():
    """
    复杂参数类型的工具定义

    支持嵌套对象、数组、枚举等
    """
    print("\n" + "=" * 60)
    print("示例 3: 复杂参数定义")
    print("=" * 60)

    # 使用 Pydantic 定义复杂参数
    from enum import Enum
    from typing import List, Optional

    class Priority(str, Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    class TaskParams(BaseModel):
        """任务参数"""
        title: str = Field(description="任务标题")
        description: Optional[str] = Field(None, description="任务描述")
        priority: Priority = Field(Priority.MEDIUM, description="优先级")
        tags: List[str] = Field(default_factory=list, description="标签列表")
        due_date: Optional[str] = Field(None, description="截止日期，格式 YYYY-MM-DD")

    def create_task(title: str, description: str = None,
                    priority: str = "medium", tags: List[str] = None,
                    due_date: str = None) -> dict:
        """创建任务"""
        return {
            "id": "task_001",
            "title": title,
            "description": description,
            "priority": priority,
            "tags": tags or [],
            "due_date": due_date,
            "status": "created"
        }

    task_tool = Tool(
        name="create_task",
        description="创建一个新任务",
        parameters=TaskParams,
        func=create_task
    )

    # 执行
    result = task_tool.execute(
        title="学习Alphora",
        description="完成所有示例代码",
        priority="high",
        tags=["学习", "编程"],
        due_date="2024-12-31"
    )

    print(f"\n创建任务结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 嵌套对象参数
    class AddressParams(BaseModel):
        """地址"""
        city: str
        street: str
        zipcode: str

    class OrderParams(BaseModel):
        """订单参数"""
        product_id: str = Field(description="产品ID")
        quantity: int = Field(ge=1, description="数量，至少为1")
        shipping_address: AddressParams = Field(description="收货地址")

    def create_order(product_id: str, quantity: int, shipping_address: dict) -> dict:
        return {
            "order_id": "ORD001",
            "product_id": product_id,
            "quantity": quantity,
            "address": shipping_address,
            "status": "pending"
        }

    order_tool = Tool(
        name="create_order",
        description="创建订单",
        parameters=OrderParams,
        func=create_order
    )

    print(f"\n订单工具参数结构:")
    print(json.dumps(order_tool.parameters, indent=2, ensure_ascii=False))

    return task_tool, order_tool


# ============================================================
# 示例 4: ToolExecutor 执行器
# ============================================================
def example_4_tool_executor():
    """
    ToolExecutor: 管理和执行多个工具

    功能：
    - 工具注册和管理
    - 统一执行接口
    - 工具调用记录
    """
    print("\n" + "=" * 60)
    print("示例 4: ToolExecutor 执行器")
    print("=" * 60)

    # 定义工具
    @tool
    def calculator_add(a: float, b: float) -> float:
        """加法"""
        return a + b

    @tool
    def calculator_subtract(a: float, b: float) -> float:
        """减法"""
        return a - b

    @tool
    def calculator_multiply(a: float, b: float) -> float:
        """乘法"""
        return a * b

    @tool
    def calculator_divide(a: float, b: float) -> float:
        """除法"""
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b

    # 创建执行器
    executor = ToolExecutor()

    # 注册工具
    executor.register(calculator_add)
    executor.register(calculator_subtract)
    executor.register(calculator_multiply)
    executor.register(calculator_divide)

    print(f"\n已注册的工具: {executor.list_tools()}")

    # 获取工具描述（用于发送给LLM）
    tools_schema = executor.get_tools_schema()
    print(f"\n工具Schema（发送给LLM）:")
    for schema in tools_schema:
        print(f"  - {schema['function']['name']}: {schema['function']['description']}")

    # 执行工具
    print("\n执行工具:")
    result = executor.execute("calculator_add", {"a": 10, "b": 5})
    print(f"  add(10, 5) = {result}")

    result = executor.execute("calculator_multiply", {"a": 3, "b": 7})
    print(f"  multiply(3, 7) = {result}")

    # 批量注册
    executor2 = ToolExecutor()
    executor2.register_all([
        calculator_add,
        calculator_subtract,
        calculator_multiply,
        calculator_divide
    ])
    print(f"\n批量注册: {executor2.list_tools()}")

    return executor


# ============================================================
# 示例 5: 异步工具
# ============================================================
async def example_5_async_tools():
    """
    异步工具的定义和执行

    适用于：
    - 网络请求
    - 数据库操作
    - 其他IO密集型操作
    """
    print("\n" + "=" * 60)
    print("示例 5: 异步工具")
    print("=" * 60)

    @tool
    async def async_fetch_data(url: str) -> dict:
        """
        异步获取数据

        Args:
            url: 数据URL
        """
        # 模拟网络延迟
        await asyncio.sleep(0.1)
        return {"url": url, "data": "模拟数据", "status": "success"}

    @tool
    async def async_save_data(key: str, value: str) -> bool:
        """
        异步保存数据

        Args:
            key: 键
            value: 值
        """
        await asyncio.sleep(0.05)
        print(f"  [保存] {key} = {value}")
        return True

    # 异步执行
    print("\n异步执行工具:")
    result = await async_fetch_data.aexecute(url="https://api.example.com/data")
    print(f"  获取数据: {result}")

    result = await async_save_data.aexecute(key="user_name", value="张三")
    print(f"  保存结果: {result}")

    # 并行执行多个异步工具
    print("\n并行执行多个异步工具:")
    results = await asyncio.gather(
        async_fetch_data.aexecute(url="https://api1.example.com"),
        async_fetch_data.aexecute(url="https://api2.example.com"),
        async_fetch_data.aexecute(url="https://api3.example.com"),
    )
    for i, r in enumerate(results):
        print(f"  结果{i+1}: {r['url']}")

    return async_fetch_data, async_save_data


# ============================================================
# 示例 6: ToolAgentMixin 混入
# ============================================================
def example_6_tool_agent_mixin():
    """
    ToolAgentMixin: 为Agent添加工具能力

    使Agent能够：
    - 调用工具
    - 处理工具结果
    - 多轮工具调用
    """
    print("\n" + "=" * 60)
    print("示例 6: ToolAgentMixin 混入")
    print("=" * 60)

    # 定义工具
    @tool
    def get_current_time() -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @tool
    def calculate(expression: str) -> float:
        """
        计算数学表达式

        Args:
            expression: 数学表达式，如 "2 + 3 * 4"
        """
        # 安全计算（仅允许数字和基本运算符）
        allowed = set("0123456789+-*/. ()")
        if not all(c in allowed for c in expression):
            raise ValueError("表达式包含非法字符")
        return eval(expression)

    @tool
    def get_user_info(user_id: str) -> dict:
        """
        获取用户信息

        Args:
            user_id: 用户ID
        """
        # 模拟数据库查询
        users = {
            "001": {"name": "张三", "age": 25, "city": "北京"},
            "002": {"name": "李四", "age": 30, "city": "上海"},
        }
        return users.get(user_id, {"error": "用户不存在"})

    # 创建带工具能力的Agent类
    class ToolAgent(ToolAgentMixin, BaseAgent):
        """带工具能力的Agent"""
        pass

    # 初始化Agent
    agent = ToolAgent(
        llm_api_key=os.getenv("LLM_API_KEY", "sk-test"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        default_llm=os.getenv("DEFAULT_LLM", "gpt-3.5-turbo")
    )

    # 注册工具
    agent.register_tool(get_current_time)
    agent.register_tool(calculate)
    agent.register_tool(get_user_info)

    print(f"\nAgent已注册的工具: {agent.list_tools()}")

    # 获取工具Schema（用于Prompt）
    tools_for_llm = agent.get_tools_for_llm()
    print(f"\n工具Schema数量: {len(tools_for_llm)}")

    # 模拟工具调用处理
    print("\n模拟工具调用:")

    # 模拟LLM返回的工具调用
    tool_call = {
        "name": "calculate",
        "arguments": {"expression": "2 + 3 * 4"}
    }

    result = agent.execute_tool(tool_call["name"], tool_call["arguments"])
    print(f"  calculate('2 + 3 * 4') = {result}")

    tool_call = {
        "name": "get_user_info",
        "arguments": {"user_id": "001"}
    }
    result = agent.execute_tool(tool_call["name"], tool_call["arguments"])
    print(f"  get_user_info('001') = {result}")

    return agent


# ============================================================
# 示例 7: 完整工具调用流程
# ============================================================
async def example_7_full_tool_flow():
    """
    完整的工具调用流程演示

    流程：
    1. 用户提问
    2. LLM决定调用工具
    3. 执行工具
    4. 将结果返回给LLM
    5. LLM生成最终回答
    """
    print("\n" + "=" * 60)
    print("示例 7: 完整工具调用流程")
    print("=" * 60)

    # 定义工具
    @tool
    def search_products(keyword: str, max_price: float = None) -> List[dict]:
        """
        搜索产品

        Args:
            keyword: 搜索关键词
            max_price: 最高价格限制
        """
        products = [
            {"id": "P001", "name": "Python编程入门", "price": 59.0, "category": "图书"},
            {"id": "P002", "name": "深度学习实战", "price": 89.0, "category": "图书"},
            {"id": "P003", "name": "机械键盘", "price": 299.0, "category": "电子"},
            {"id": "P004", "name": "显示器", "price": 1299.0, "category": "电子"},
        ]

        results = [p for p in products if keyword.lower() in p["name"].lower()]
        if max_price:
            results = [p for p in results if p["price"] <= max_price]

        return results

    @tool
    def get_product_detail(product_id: str) -> dict:
        """
        获取产品详情

        Args:
            product_id: 产品ID
        """
        details = {
            "P001": {
                "id": "P001",
                "name": "Python编程入门",
                "price": 59.0,
                "description": "适合初学者的Python入门书籍",
                "stock": 100,
                "rating": 4.5
            }
        }
        return details.get(product_id, {"error": "产品不存在"})

    # 创建工具执行器
    executor = ToolExecutor()
    executor.register(search_products)
    executor.register(get_product_detail)

    # 模拟完整流程
    print("\n=== 模拟完整工具调用流程 ===")

    user_query = "帮我找一下100元以内的Python相关书籍"
    print(f"\n用户: {user_query}")

    # Step 1: 准备工具Schema
    tools_schema = executor.get_tools_schema()
    print(f"\n[系统] 可用工具: {[t['function']['name'] for t in tools_schema]}")

    # Step 2: 模拟LLM决定调用工具
    print("\n[LLM] 分析用户需求，决定调用 search_products 工具")
    llm_tool_call = {
        "name": "search_products",
        "arguments": {"keyword": "Python", "max_price": 100.0}
    }

    # Step 3: 执行工具
    print(f"\n[系统] 执行工具: {llm_tool_call['name']}")
    tool_result = executor.execute(
        llm_tool_call["name"],
        llm_tool_call["arguments"]
    )
    print(f"[系统] 工具返回: {json.dumps(tool_result, ensure_ascii=False)}")

    # Step 4: 模拟LLM生成最终回答
    print("\n[LLM] 根据工具结果生成回答:")
    print("助手: 我找到了1本符合条件的Python书籍：")
    print("      - 《Python编程入门》，价格59元")

    return executor


# ============================================================
# 示例 8: 工具错误处理
# ============================================================
def example_8_error_handling():
    """
    工具的错误处理

    包括：
    - 参数验证
    - 执行错误
    - 超时处理
    """
    print("\n" + "=" * 60)
    print("示例 8: 工具错误处理")
    print("=" * 60)

    @tool
    def divide(a: float, b: float) -> float:
        """
        除法运算

        Args:
            a: 被除数
            b: 除数
        """
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b

    @tool
    def fetch_with_timeout(url: str, timeout: int = 5) -> dict:
        """
        带超时的数据获取

        Args:
            url: URL地址
            timeout: 超时时间（秒）
        """
        import time
        # 模拟超时
        if "slow" in url:
            time.sleep(timeout + 1)
        return {"url": url, "data": "success"}

    executor = ToolExecutor()
    executor.register(divide)
    executor.register(fetch_with_timeout)

    # 正常执行
    print("\n正常执行:")
    result = executor.execute("divide", {"a": 10, "b": 2})
    print(f"  divide(10, 2) = {result}")

    # 错误处理
    print("\n错误处理:")
    try:
        result = executor.execute("divide", {"a": 10, "b": 0})
    except ValueError as e:
        print(f"  divide(10, 0) 错误: {e}")

    # 参数验证错误
    print("\n参数验证错误:")
    try:
        result = executor.execute("divide", {"a": "abc", "b": 2})
    except Exception as e:
        print(f"  参数类型错误: {type(e).__name__}")

    # 工具不存在
    print("\n工具不存在:")
    try:
        result = executor.execute("unknown_tool", {})
    except KeyError as e:
        print(f"  工具不存在: {e}")

    return executor


# ============================================================
# 示例 9: 工具组合和复用
# ============================================================
def example_9_tool_composition():
    """
    工具的组合和复用

    构建工具集合，按功能分组
    """
    print("\n" + "=" * 60)
    print("示例 9: 工具组合和复用")
    print("=" * 60)

    # 数学工具集
    @tool
    def math_add(a: float, b: float) -> float:
        """加法"""
        return a + b

    @tool
    def math_sqrt(x: float) -> float:
        """平方根"""
        import math
        return math.sqrt(x)

    @tool
    def math_power(base: float, exp: float) -> float:
        """幂运算"""
        return base ** exp

    math_tools = [math_add, math_sqrt, math_power]

    # 字符串工具集
    @tool
    def str_upper(text: str) -> str:
        """转大写"""
        return text.upper()

    @tool
    def str_reverse(text: str) -> str:
        """反转字符串"""
        return text[::-1]

    @tool
    def str_count(text: str, char: str) -> int:
        """统计字符出现次数"""
        return text.count(char)

    string_tools = [str_upper, str_reverse, str_count]

    # 创建不同用途的执行器
    math_executor = ToolExecutor()
    math_executor.register_all(math_tools)

    string_executor = ToolExecutor()
    string_executor.register_all(string_tools)

    # 全功能执行器
    full_executor = ToolExecutor()
    full_executor.register_all(math_tools + string_tools)

    print(f"\n数学工具集: {math_executor.list_tools()}")
    print(f"字符串工具集: {string_executor.list_tools()}")
    print(f"全功能工具集: {full_executor.list_tools()}")

    # 使用
    print("\n使用示例:")
    print(f"  math_sqrt(16) = {math_executor.execute('math_sqrt', {'x': 16})}")
    print(f"  str_upper('hello') = {string_executor.execute('str_upper', {'text': 'hello'})}")

    return full_executor


# ============================================================
# 示例 10: 与Prompt集成
# ============================================================
def example_10_prompt_integration():
    """
    工具与Prompt的集成

    演示如何在Prompt中使用工具
    """
    print("\n" + "=" * 60)
    print("示例 10: 与Prompt集成")
    print("=" * 60)

    # 定义工具
    @tool
    def get_stock_price(symbol: str) -> dict:
        """
        获取股票价格

        Args:
            symbol: 股票代码
        """
        prices = {
            "AAPL": {"price": 175.50, "change": "+1.2%"},
            "GOOGL": {"price": 140.30, "change": "-0.5%"},
            "MSFT": {"price": 378.90, "change": "+0.8%"},
        }
        return prices.get(symbol, {"error": "未找到该股票"})

    @tool
    def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
        """
        货币转换

        Args:
            amount: 金额
            from_currency: 源货币
            to_currency: 目标货币
        """
        rates = {
            "USD_CNY": 7.2,
            "EUR_CNY": 7.8,
            "USD_EUR": 0.92,
        }
        key = f"{from_currency}_{to_currency}"
        if key in rates:
            converted = amount * rates[key]
            return {"original": amount, "converted": converted, "rate": rates[key]}
        return {"error": "不支持的货币对"}

    # 在Prompt中使用工具的代码示例
    print("\n在Prompt中使用工具的代码示例:")
    print("""
    from alphora.agent import BaseAgent
    from alphora.tools import tool
    
    agent = BaseAgent(...)
    
    # 定义工具
    @tool
    def get_stock_price(symbol: str) -> dict:
        '''获取股票价格'''
        ...
    
    # 创建带工具的Prompt
    prompt = agent.create_prompt(
        template="你是一个金融助手...",
        tools=[get_stock_price, convert_currency],  # 传入工具列表
        tool_choice="auto"  # auto, required, none
    )
    
    # 调用时会自动处理工具调用
    response = await prompt.acall(
        query="AAPL的股价是多少？",
        is_stream=False
    )
    """)

    print("\n工具Schema示例（发送给LLM）:")
    executor = ToolExecutor()
    executor.register(get_stock_price)
    executor.register(convert_currency)

    for schema in executor.get_tools_schema():
        print(f"\n{schema['function']['name']}:")
        print(f"  描述: {schema['function']['description']}")
        print(f"  参数: {list(schema['function']['parameters']['properties'].keys())}")

    return executor


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Tools 工具系统示例")
    print("=" * 60)

    example_1_tool_basics()
    example_2_tool_decorator()
    example_3_complex_parameters()
    example_4_tool_executor()

    # 异步示例
    print("\n" + "=" * 60)
    print("运行异步示例...")
    print("=" * 60)
    asyncio.run(example_5_async_tools())

    example_6_tool_agent_mixin()

    asyncio.run(example_7_full_tool_flow())

    example_8_error_handling()
    example_9_tool_composition()
    example_10_prompt_integration()

    print("\n" + "=" * 60)
    print("所有工具系统示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()