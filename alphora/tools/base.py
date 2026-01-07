"""
工具调用系统 - 统一的Tool定义和调用机制

支持功能：
1. 工具定义和注册
2. 参数验证（基于Pydantic）
3. 同步/异步执行
4. 工具结果标准化
5. 自动生成OpenAI兼容的函数描述
"""

import json
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Type, Union,
    get_type_hints, TypeVar, Generic
)
from enum import Enum
from pydantic import BaseModel, Field, create_model, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ToolStatus(str, Enum):
    """工具执行状态"""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolResult:
    """工具执行结果"""
    status: ToolStatus
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }

    def __str__(self) -> str:
        if self.success:
            return str(self.data)
        return f"Error: {self.error}"

    @classmethod
    def ok(cls, data: Any, **metadata) -> "ToolResult":
        """创建成功结果"""
        return cls(status=ToolStatus.SUCCESS, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "ToolResult":
        """创建失败结果"""
        return cls(status=ToolStatus.ERROR, error=error, metadata=metadata)


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: Type
    description: str = ""
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        """转换为JSON Schema格式"""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            List: "array",
            Dict: "object",
        }

        # 处理泛型类型
        origin = getattr(self.type, '__origin__', None)
        if origin is not None:
            json_type = type_mapping.get(origin, "string")
        else:
            json_type = type_mapping.get(self.type, "string")

        schema = {
            "type": json_type,
            "description": self.description
        }

        if self.enum:
            schema["enum"] = self.enum

        return schema


class Tool(ABC):
    """
    工具基类

    使用方式：
    ```python
    class SearchTool(Tool):
        name = "search"
        description = "搜索互联网获取信息"

        def define_parameters(self) -> List[ToolParameter]:
            return [
                ToolParameter(name="query", type=str, description="搜索关键词"),
                ToolParameter(name="limit", type=int, description="结果数量", default=10)
            ]

        async def execute(self, query: str, limit: int = 10) -> ToolResult:
            # 实现搜索逻辑
            results = await do_search(query, limit)
            return ToolResult.ok(results)
    ```
    """

    name: str = ""
    description: str = ""

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__.lower().replace("tool", "")
        self._parameters: Optional[List[ToolParameter]] = None
        self._pydantic_model: Optional[Type[BaseModel]] = None

    @abstractmethod
    def define_parameters(self) -> List[ToolParameter]:
        """定义工具参数"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """异步执行工具"""
        pass

    def execute_sync(self, **kwargs) -> ToolResult:
        """同步执行（默认抛出异常，子类可重写）"""
        raise NotImplementedError(
            f"Tool '{self.name}' does not support synchronous execution. "
            "Please use 'execute' method with await."
        )

    @property
    def parameters(self) -> List[ToolParameter]:
        """获取参数列表（带缓存）"""
        if self._parameters is None:
            self._parameters = self.define_parameters()
        return self._parameters

    def get_pydantic_model(self) -> Type[BaseModel]:
        """动态生成Pydantic模型用于参数验证"""
        if self._pydantic_model is not None:
            return self._pydantic_model

        fields = {}
        for param in self.parameters:
            if param.required:
                fields[param.name] = (param.type, Field(description=param.description))
            else:
                fields[param.name] = (
                    Optional[param.type],
                    Field(default=param.default, description=param.description)
                )

        self._pydantic_model = create_model(
            f"{self.name.title()}Params",
            **fields
        )
        return self._pydantic_model

    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """验证并规范化参数"""
        model = self.get_pydantic_model()
        try:
            validated = model(**params)
            return validated.model_dump()
        except ValidationError as e:
            raise ValueError(f"Tool '{self.name}' parameter validation failed: {e}")

    def to_openai_function(self) -> Dict[str, Any]:
        """转换为OpenAI Function Calling格式"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

    async def __call__(self, **kwargs) -> ToolResult:
        """使工具可调用"""
        try:
            validated_params = self.validate_params(kwargs)
            return await self.execute(**validated_params)
        except ValueError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            logger.exception(f"Tool '{self.name}' execution failed")
            return ToolResult.fail(f"Execution error: {str(e)}")

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"


class FunctionTool(Tool):
    """
    从函数创建的工具

    用于将普通函数包装为Tool
    """

    def __init__(
            self,
            func: Callable,
            name: Optional[str] = None,
            description: Optional[str] = None,
            parameter_descriptions: Optional[Dict[str, str]] = None
    ):
        self._func = func
        self._is_async = inspect.iscoroutinefunction(func)
        self._parameter_descriptions = parameter_descriptions or {}

        # 设置名称和描述
        self.name = name or func.__name__
        self.description = description or (func.__doc__ or "").strip().split('\n')[0]

        super().__init__()

    def define_parameters(self) -> List[ToolParameter]:
        """从函数签名推断参数"""
        sig = inspect.signature(self._func)
        type_hints = get_type_hints(self._func) if hasattr(self._func, '__annotations__') else {}

        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue

            param_type = type_hints.get(param_name, str)
            has_default = param.default is not inspect.Parameter.empty

            parameters.append(ToolParameter(
                name=param_name,
                type=param_type if param_type != inspect.Parameter.empty else str,
                description=self._parameter_descriptions.get(param_name, ""),
                required=not has_default,
                default=param.default if has_default else None
            ))

        return parameters

    async def execute(self, **kwargs) -> ToolResult:
        """执行函数"""
        try:
            if self._is_async:
                result = await self._func(**kwargs)
            else:
                result = self._func(**kwargs)

            # 如果函数已经返回ToolResult，直接使用
            if isinstance(result, ToolResult):
                return result

            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(str(e))

    def execute_sync(self, **kwargs) -> ToolResult:
        """同步执行"""
        if self._is_async:
            raise NotImplementedError("Async function cannot be executed synchronously")

        try:
            result = self._func(**kwargs)
            if isinstance(result, ToolResult):
                return result
            return ToolResult.ok(result)
        except Exception as e:
            return ToolResult.fail(str(e))


class ToolRegistry:
    """
    工具注册表

    用于管理和查找已注册的工具
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, will be overwritten")
        self._tools[tool.name] = tool
        return self

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """转换为OpenAI tools格式"""
        return [tool.to_openai_function() for tool in self._tools.values()]

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """执行指定工具"""
        tool = self.get(tool_name)
        if tool is None:
            return ToolResult.fail(f"Tool '{tool_name}' not found")
        return await tool(**kwargs)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())


# 全局工具注册表
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    return _global_registry

