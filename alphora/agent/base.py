from fastapi import Request
import asyncio
from uuid import uuid4
from alphora.models.llms.openai_like import OpenAILike
from typing import Optional, List, Any, overload, Union, Dict, Iterator, TypeVar, Type
from alphora.server.stream_responser import DataStreamer
import logging
from alphora.prompter import BasePrompt

from alphora.memory.base import BaseMemory
from alphora.memory.memories.short_term_memory import ShortTermMemory
from alphora.agent.stream import Stream
from alphora.server.openai_request_body import OpenAIRequest

from alphora.agent.agent_contract import *


T = TypeVar('T', bound='BaseAgent')


class BaseAgent(object):

    agent_type: str = "BaseAgent"

    def __init__(self,
                 llm: Optional[OpenAILike] = None,
                 verbose: bool = False,
                 memory: Optional[BaseMemory] = None,
                 agent_id: Optional[str] = None,
                 callback: Optional[DataStreamer] = None,
                 **kwargs):

        if not callback:
            self.callback = DataStreamer(timeout=300)
        else:
            self.callback = callback

        self.agent_id = agent_id or str(uuid4())

        self.verbose = verbose
        self.memory = memory if memory is not None else ShortTermMemory()

        self.llm = llm

        # Agent配置字典，会继承给派生智能体
        self.config: Dict[str, Any]= {}

        self.stream = Stream(callback=self.callback)

        self.init_params = {
            "llm": self.llm,
            **kwargs}

        # self.metadata = AgentMetadata(name=self.agent_type)

        self.input_ports: List[AgentInputPort] = []
        self.output_ports: List[AgentOutputPort] = []

        self._status: AgentStatus = AgentStatus.PENDING
        # self._outputs: Dict[str, AgentOutput] = {}

        self._log = []

    def update_config(self,
                      key: str,
                      value: Any = None,
                      merge: bool = True) -> None:
        """
        更新单个配置项。
        :param key: 配置项的键名（必须为字符串）
        :param value: 配置项的值。若为 None，可将该 key 设为 None（允许）。
        :param merge:
            - 若为 True（默认）：将该 key-value 合并到现有 config 中。
            - 若为 False：先清空 config，再仅设置此 key-value。
        :return: None
        """
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")

        if not merge:
            # 清空现有配置，仅保留当前这一项
            self.config = {key: value}
        else:
            self.config[key] = value
        pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取指定配置项的值。

        :param key: 配置项的键名（必须为字符串）
        :param default: 如果 key 不存在时返回的默认值（默认为 None）
        :return: 配置项的值，若不存在则返回 default
        """
        if not isinstance(key, str):
            raise TypeError("Parameter 'key' must be a string.")

        return self.config.get(key, default)

    def _reinitialize(self, **new_kwargs) -> None:
        merged_params = {**self.init_params, **new_kwargs}
        self.__init__(**merged_params)

    def set_input_ports(self) -> None:
        """设置Agent的输入"""
        self.input_ports = self.input_ports
        if not self.input_ports:
            logging.warning("No input ports defined")
        pass

    def set_output_ports(self) -> None:
        """设置Agent的输出"""
        self.output_ports = self.output_ports
        if not self.output_ports:
            logging.warning("No output ports defined")
        pass

    def list_input_ports(self) -> dict:
        """列出该智能体的输入端口要求"""

        pass

    def derive(self, agent_cls_or_instance: Union[Type[T], T], **kwargs) -> T:
        """
        从当前 agent 派生出一个新的 agent 实例。

        - 如果传入类：创建新实例，参数 = self.init_params + kwargs
        - 如果传入实例：用 self.init_params + kwargs 更新该实例
        """
        # 合并参数：kwargs 优先级最高，然后是 self.init_params
        override_params = {**self.init_params, **kwargs}

        # 情况1：传入的是类
        if isinstance(agent_cls_or_instance, type) and issubclass(agent_cls_or_instance, BaseAgent):
            derived_agent = agent_cls_or_instance(**override_params)
            derived_agent.callback = self.callback
            return derived_agent

        # 情况2：传入的是实例
        elif isinstance(agent_cls_or_instance, BaseAgent):
            agent_cls_or_instance._reinitialize(**override_params)
            agent_cls_or_instance.callback = self.callback
            return agent_cls_or_instance

        else:
            raise TypeError(
                f"Unsupported type: {type(agent_cls_or_instance)}. "
                f"Expected a subclass or instance of BaseAgent."
            )

    def create_prompt(
            self,
            prompt: str = None,
            template_path: str = None,
            template_desc: str = "",
            content_type: Optional[str] = None) -> BasePrompt:
        """
        快速创建提示词模板
        Args:
            template_path: 提示词路径（建议为相对路径）
            template_desc: 提示词描述
            content_type: 当调用 acall 方法时，输出的流的 content_type
            prompt: Optional

        Returns: BasePrompt实例
        """

        if not self.llm:
            raise ValueError("LLM model is not configured")

        prompt_instance = BasePrompt(
            template_path=template_path,
            template_desc=template_desc,
            callback=self.callback,
            content_type=content_type
        )

        try:
            prompt_instance.add_llm(model=self.llm)

            if prompt:
                prompt_instance.load_from_string(prompt=prompt)

            prompt_instance.verbose = self.verbose

            return prompt_instance

        except Exception as e:
            error_msg = f'Failed to create prompt: {str(e)}'
            logging.error(error_msg)
            raise ValueError(error_msg)

    # async def arun(self, inputs: Dict[str, AgentInput]) -> Dict[str, AgentOutput]:
    #     """运行Agent（包含验证和异常处理）
    #
    #     Args:
    #         inputs: 输入端口名称到输入数据的映射
    #             例如: {"data": NodeInput(...)}
    #             对于简单节点，通常只有一个输入端口
    #
    #     Returns:
    #         输出端口名称到输出数据的映射
    #         例如: {"output": NodeOutput(...)} 或
    #               {"result": NodeOutput(...), "logs": NodeOutput(...)}
    #     """
    #     # 准备基础日志
    #     execution_logs = []
    #     base_metadata = {"node_id": self.node_id, "node_type": self.node_type}
    #
    #     try:
    #         # 更新状态
    #         self._status = AgentStatus.RUNNING
    #
    #         # 验证配置（延迟验证，允许运行时配置）
    #         self._validate_config()
    #         execution_logs.append(f"配置验证通过")
    #
    #         # 验证输入
    #         self.validate_inputs(inputs)
    #         execution_logs.append(f"输入验证通过")
    #
    #         # 执行节点逻辑
    #         execution_logs.append(f"开始执行节点: {self.node_type}")
    #         results = await self.aexecute(inputs)
    #
    #         # 验证输出
    #         self.validate_outputs(results)
    #         execution_logs.append(f"输出验证通过")
    #
    #         # 为每个输出端口添加日志和元数据
    #         for port_name, output in results.items():
    #             # 添加日志（根据输出状态决定）
    #             if output.status == AgentStatus.FAILED:
    #                 output.add_log(f"节点执行失败")
    #             else:
    #                 output.add_log(f"节点执行成功")
    #                 # 只有当输出没有显式设置状态时，才设置为 SUCCESS
    #                 if output.status not in [AgentStatus.SUCCESS, AgentStatus.FAILED]:
    #                     output.status = AgentStatus.SUCCESS
    #
    #             # 合并执行日志
    #             output.logs = execution_logs + output.logs
    #
    #             # 设置元数据
    #             output.metadata.update(base_metadata)
    #             output.metadata["port"] = port_name
    #
    #         # 更新节点状态（如果有任何输出失败，则节点失败）
    #         has_failed = any(output.status == NodeStatus.FAILED for output in results.values())
    #         self._status = NodeStatus.FAILED if has_failed else NodeStatus.SUCCESS
    #         self._outputs = results
    #
    #         return results
    #
    #     except (NodeValidationError, Exception) as e:
    #         # 创建错误输出
    #         error_msg = (
    #             f"输入验证失败: {str(e)}" if isinstance(e, NodeValidationError)
    #             else f"节点执行失败: {type(e).__name__}: {str(e)}"
    #         )
    #
    #         # 确定输出端口名称（用于错误情况）
    #         if len(self.output_ports) == 1:
    #             error_port_name = self.output_ports[0].name
    #         elif len(self.output_ports) == 0:
    #             error_port_name = "output"
    #         else:
    #             # 多个输出端口时，为每个端口创建错误输出
    #             error_outputs = {}
    #             for port in self.output_ports:
    #                 error_output = NodeOutput(
    #                     status=NodeStatus.FAILED,
    #                     error=error_msg,
    #                     metadata=base_metadata.copy()
    #                 )
    #                 error_output.logs = execution_logs.copy()
    #                 error_output.metadata["port"] = port.name
    #                 error_outputs[port.name] = error_output
    #
    #             self._status = NodeStatus.FAILED
    #             self._outputs = error_outputs
    #             return error_outputs
    #
    #         # 单个输出端口的错误处理
    #         error_output = NodeOutput(
    #             status=NodeStatus.FAILED,
    #             error=error_msg,
    #             metadata=base_metadata
    #         )
    #         error_output.logs = execution_logs
    #         error_output.metadata["port"] = error_port_name
    #
    #         self._status = NodeStatus.FAILED
    #         error_outputs = {error_port_name: error_output}
    #         self._outputs = error_outputs
    #         return error_outputs

    # async def aexecute(self, inputs: AgentInput) -> AgentOutput:
    #     """
    #     由子类实现此方法
    #     返回值必须是 {port_name: NodeOutput(...)} 的字典。
    #     """
    #     raise NotImplementedError(f"'{self.__class__.__name__}._execute' must be implemented")
    #
    # def execute(self, inputs: AgentInput) -> AgentOutput:
    #     """
    #     由子类实现此方法。
    #     返回值必须是 {port_name: NodeOutput(...)} 的字典。
    #     """
    #     raise NotImplementedError(f"'{self.__class__.__name__}._execute' must be implemented")
    #
    # def get_output(self, port_name: Optional[str] = None) -> Optional[AgentOutput]:
    #     if not self._outputs:
    #         return None
    #     if port_name is None:
    #         if len(self._outputs) == 1:
    #             return next(iter(self._outputs.values()))
    #         else:
    #             raise ValueError(f"多个输出端口，请指定名称。可用: {list(self._outputs.keys())}")
    #     return self._outputs.get(port_name)

    def __or__(self, other):
        # TODO
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "metadata": self.metadata.model_dump(),
            "status": self._status.value,
            "input_ports": [p.model_dump() for p in self.input_ports],
            "output_ports": [p.model_dump() for p in self.output_ports],
        }

    def to_api(
            self,
            method: str,
            path: str = "/alphadata"
    ) -> "FastAPI":
        """
        将当前 agent 的指定方法暴露为可直接运行的 FastAPI 应用。

        要求目标方法：
          - 是 async def 定义的异步方法
          - 有且仅有一个参数，类型注解为 OpenAIRequest

        示例：
            app = MyAgent(llm=...).to_api(method="chat", path="/v1/chat")
            # 然后运行：uvicorn.run(app)

        Args:
            method: 要暴露的方法名（如 "chat"）
            path: API 路径（默认 "/invoke"）
            title: FastAPI 文档标题
            description: FastAPI 文档描述

        Returns:
            FastAPI 实例，可直接传给 uvicorn.run()
        """
        import inspect
        from fastapi import FastAPI
        from alphora.server.openai_request_body import OpenAIRequest
        import asyncio

        if not hasattr(self, method):
            raise ValueError(f"Method '{method}' not found in {self.__class__.__name__}")

        bound_method = getattr(self, method)
        if not inspect.iscoroutinefunction(bound_method):
            raise ValueError(f"Method '{method}' must be defined with 'async def'.")

        sig = inspect.signature(bound_method)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise ValueError(f"Method '{method}' must have exactly one parameter, got {len(params)}.")

        param = params[0]
        if param.annotation is not OpenAIRequest:
            raise ValueError(
                f"Parameter of method '{method}' must be annotated as 'OpenAIRequest', "
                f"but got: {param.annotation}"
            )

        app = FastAPI()

        # 获取原始函数
        original_func = getattr(self, method)

        path = f'{path}/chat/completions'

        @app.post(path)
        async def dynamic_endpoint(request: OpenAIRequest):

            is_stream = request.stream

            # 换一个新的DataStreamer
            new_callback = DataStreamer(timeout=300)
            self.callback = new_callback
            self.stream = Stream(callback=self.callback)

            _ = asyncio.create_task(original_func(request))

            if is_stream:
                return self.callback.start_streaming_openai()
            else:
                return await self.callback.start_non_streaming_openai()

        return app

