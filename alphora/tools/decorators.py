"""
工具装饰器 - 简化工具定义

使用方式：
```python
@tool(description="搜索互联网")
async def search(query: str, limit: int = 10) -> str:
    '''
    搜索互联网获取信息

    Args:
        query: 搜索关键词
        limit: 返回结果数量
    '''
    return f"搜索结果: {query}"

# 或者使用更详细的参数描述
@tool(
    name="web_search",
    description="搜索互联网获取信息",
    params={
        "query": "搜索关键词",
        "limit": "返回结果数量，默认10"
    }
)
async def search(query: str, limit: int = 10) -> str:
    return f"搜索结果: {query}"
```
"""

import re
from typing import Callable, Dict, Optional, TypeVar, Union
from functools import wraps

from alphora.tools.base import FunctionTool, Tool, ToolRegistry, get_global_registry

F = TypeVar('F', bound=Callable)


def tool(
        func: Optional[Callable] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        params: Optional[Dict[str, str]] = None,
        register: bool = True,
        registry: Optional[ToolRegistry] = None
) -> Union[Tool, Callable[[F], Tool]]:
    """
    工具装饰器

    Args:
        func: 被装饰的函数
        name: 工具名称，默认使用函数名
        description: 工具描述，默认从docstring提取
        params: 参数描述字典，键为参数名，值为描述
        register: 是否自动注册到全局注册表
        registry: 指定注册表，默认使用全局注册表

    Returns:
        Tool实例

    Examples:
        >>> @tool
        ... async def greet(name: str) -> str:
        ...     '''向用户打招呼'''
        ...     return f"Hello, {name}!"

        >>> @tool(description="计算两数之和")
        ... def add(a: int, b: int) -> int:
        ...     return a + b
    """

    def decorator(fn: Callable) -> Tool:
        # 从docstring解析参数描述
        param_descriptions = params or {}
        if not param_descriptions and fn.__doc__:
            param_descriptions = _parse_docstring_params(fn.__doc__)

        # 获取描述
        tool_description = description
        if not tool_description and fn.__doc__:
            tool_description = _get_docstring_summary(fn.__doc__)

        # 创建工具
        tool_instance = FunctionTool(
            func=fn,
            name=name,
            description=tool_description,
            parameter_descriptions=param_descriptions
        )

        # 注册工具
        if register:
            target_registry = registry or get_global_registry()
            target_registry.register(tool_instance)

        return tool_instance

    # 支持 @tool 和 @tool(...) 两种用法
    if func is not None:
        return decorator(func)
    return decorator


def _parse_docstring_params(docstring: str) -> Dict[str, str]:
    """
    从docstring解析参数描述

    支持Google风格和Sphinx风格的docstring
    """
    params = {}

    # Google风格: Args:
    args_match = re.search(r'Args?:\s*\n((?:\s+\w+.*\n?)+)', docstring, re.IGNORECASE)
    if args_match:
        args_section = args_match.group(1)
        # 匹配 "param_name: description" 或 "param_name (type): description"
        for match in re.finditer(r'^\s+(\w+)(?:\s*\([^)]*\))?:\s*(.+?)(?=\n\s+\w+|\n\n|\Z)',
                                 args_section, re.MULTILINE | re.DOTALL):
            param_name = match.group(1)
            param_desc = match.group(2).strip().replace('\n', ' ')
            params[param_name] = param_desc
        return params

    # Sphinx风格: :param name: description
    for match in re.finditer(r':param\s+(\w+):\s*(.+?)(?=:|$)', docstring, re.MULTILINE):
        param_name = match.group(1)
        param_desc = match.group(2).strip()
        params[param_name] = param_desc

    return params


def _get_docstring_summary(docstring: str) -> str:
    """获取docstring的第一行作为摘要"""
    lines = docstring.strip().split('\n')
    if lines:
        return lines[0].strip()
    return ""


class ToolSet:
    """
    工具集合 - 用于组织相关工具

    使用方式：
    ```python
    math_tools = ToolSet("math", "数学计算工具集")

    @math_tools.tool
    def add(a: int, b: int) -> int:
        '''两数相加'''
        return a + b

    @math_tools.tool
    def multiply(a: int, b: int) -> int:
        '''两数相乘'''
        return a * b

    # 获取所有工具
    tools = math_tools.get_tools()
    ```
    """

    def __init__(self, prefix: str = "", description: str = ""):
        self.prefix = prefix
        self.description = description
        self._registry = ToolRegistry()

    def tool(
            self,
            func: Optional[Callable] = None,
            *,
            name: Optional[str] = None,
            description: Optional[str] = None,
            params: Optional[Dict[str, str]] = None
    ) -> Union[Tool, Callable[[F], Tool]]:
        """注册工具到此工具集"""

        def decorator(fn: Callable) -> Tool:
            tool_name = name or fn.__name__
            if self.prefix:
                tool_name = f"{self.prefix}_{tool_name}"

            param_descriptions = params or {}
            if not param_descriptions and fn.__doc__:
                param_descriptions = _parse_docstring_params(fn.__doc__)

            tool_description = description
            if not tool_description and fn.__doc__:
                tool_description = _get_docstring_summary(fn.__doc__)

            tool_instance = FunctionTool(
                func=fn,
                name=tool_name,
                description=tool_description,
                parameter_descriptions=param_descriptions
            )

            self._registry.register(tool_instance)
            return tool_instance

        if func is not None:
            return decorator(func)
        return decorator

    def get_tools(self) -> list[Tool]:
        """获取所有工具"""
        return self._registry.list_tools()

    def get_registry(self) -> ToolRegistry:
        """获取注册表"""
        return self._registry

    def to_openai_tools(self) -> list[dict]:
        """转换为OpenAI tools格式"""
        return self._registry.to_openai_tools()