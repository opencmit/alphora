import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Type, Union, Coroutine
from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo
from .exceptions import ToolValidationError, ToolExecutionError


class Tool(BaseModel):
    """
    工具包装器

    Attributes:
        name: 工具名称（大模型调用的唯一标识）。
        description: 工具描述（Prompt的一部分）。
        func: 实际执行的函数（同步或异步）。
        args_schema: Pydantic模型，用于验证输入参数。
        is_async: 标记是否为异步函数。
    """
    name: str
    description: str
    func: Callable[..., Any]
    args_schema: Type[BaseModel]
    is_async: bool = False

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_function(
            cls,
            func: Callable,
            name: Optional[str] = None,
            description: Optional[str] = None,
            args_schema: Optional[Type[BaseModel]] = None
    ) -> "Tool":
        """
        将普通函数或方法转换为 Tool 实例。
        自动处理 docstring 解析和 Pydantic 模型动态生成。
        """
        # 1. 确定名称
        tool_name = name or func.__name__

        # 2. 确定描述 (优先使用传入的，否则提取 docstring)
        tool_description = description or inspect.getdoc(func) or "No description provided."
        # 清理多余空格
        tool_description = tool_description.strip()

        # 3. 检测是否为异步函数
        is_async = inspect.iscoroutinefunction(func)

        # 4. 动态生成参数 Schema (核心逻辑)
        if args_schema is None:
            args_schema = cls._create_schema_from_signature(func, tool_name)

        return cls(
            name=tool_name,
            description=tool_description,
            func=func,
            args_schema=args_schema,
            is_async=is_async
        )

    @staticmethod
    def _create_schema_from_signature(func: Callable, tool_name: str) -> Type[BaseModel]:
        """
        利用 inspect 和 Pydantic 动态生成参数模型。
        """
        signature = inspect.signature(func)
        fields = {}

        for param_name, param in signature.parameters.items():
            # 跳过 self, cls 等绑定参数（如果是 bound method，inspect通常已经自动处理了，但为了保险）
            if param_name in ('self', 'cls'):
                continue

            # 获取类型注解，默认为 Any
            annotation = param.annotation
            if annotation == inspect.Parameter.empty:
                annotation = Any

            # 获取默认值
            if param.default == inspect.Parameter.empty:
                # 无默认值 -> 必填 (Pydantic 使用 ... 表示必填)
                field_info = Field(...)
            else:
                # 有默认值 -> 选填
                field_info = Field(default=param.default)

            fields[param_name] = (annotation, field_info)

        # 动态创建 Pydantic 模型
        # 模型名称建议由工具名+Schema后缀组成，避免冲突
        model_name = f"{tool_name.title().replace('_', '')}Schema"
        return create_model(model_name, **fields)

    @property
    def openai_schema(self) -> Dict[str, Any]:
        """
        生成符合 OpenAI Function Calling 标准的 Schema。
        """
        schema = self.args_schema.model_json_schema()

        # 清理 Pydantic 生成的额外字段 (如 title, definitions) 以符合 OpenAI 规范
        parameters = {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters
            }
        }

    def validate_args(self, tool_input: Union[str, Dict]) -> Dict[str, Any]:
        """验证并清洗输入参数"""
        if isinstance(tool_input, str):
            # 如果大模型传回的是 JSON 字符串，先解析
            # 注意：实际场景中通常由 ToolExecutor 统一解析 JSON，这里不处理 JSON 字符串解析，交给上层
            raise ToolValidationError("Tool input should be a dictionary, not string.")

        try:
            validated_model = self.args_schema(**tool_input)
            return validated_model.model_dump()
        except Exception as e:
            raise ToolValidationError(f"Arguments validation failed for tool '{self.name}': {str(e)}")

    def __call__(self, *args, **kwargs) -> Any:
        """允许 Tool 像普通函数一样被调用，自动映射位置参数到参数名。"""
        if args:
            import inspect
            sig = inspect.signature(self.func)
            params = [
                p.name for p in sig.parameters.values()
                if p.name not in ('self', 'cls')
            ]
            for i, val in enumerate(args):
                if i < len(params):
                    kwargs[params[i]] = val
        if self.is_async:
            return self.arun(**kwargs)
        return self.run(**kwargs)

    def run(self, **kwargs) -> Any:
        """同步执行入口"""
        if self.is_async:
            raise ToolExecutionError(f"Tool '{self.name}' is async. Please use 'arun' instead.")

        try:
            validated_args = self.validate_args(kwargs)
            return self.func(**validated_args)
        except ToolValidationError:
            raise
        except Exception as e:
            # 捕获业务逻辑的 Crash，包装抛出
            raise ToolExecutionError(f"Error executing tool '{self.name}': {str(e)}")

    async def arun(self, **kwargs) -> Any:
        """异步执行入口"""
        if not self.is_async:
            # 使用 run_in_executor 防止阻塞 EventLoop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self.run(**kwargs))

        try:
            validated_args = self.validate_args(kwargs)
            return await self.func(**validated_args)
        except ToolValidationError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Error executing async tool '{self.name}': {str(e)}")
