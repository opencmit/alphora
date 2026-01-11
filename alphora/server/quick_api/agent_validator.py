import inspect
from typing import Type, Dict, Any

from alphora.agent.base_agent import BaseAgent
from alphora.server.openai_request_body import OpenAIRequest


class AgentValidationError(ValueError):
    """Agent校验异常"""
    pass


def validate_agent_class(agents: BaseAgent) -> None:
    """
    校验Agent类合法性
    :param agents: Agent类
    :raise AgentValidationError: 校验失败
    """
    if not isinstance(agents, BaseAgent):
        raise AgentValidationError(
            f"agents必须是BaseAgent子类，当前类型: {type(agents)}"
        )


def validate_agent_method(
        agent: BaseAgent,
        method_name: str
) -> None:
    """
    校验Agent方法合法性
    :param agent: Agent类
    :param method_name: 方法名
    :raise AgentValidationError: 校验失败
    """

    if not hasattr(agent, method_name):
        raise AgentValidationError(
            f"Agent类 {agent.__class__.__name__} 不存在方法: {method_name}"
        )

    # 校验方法是异步的
    method = getattr(agent, method_name)
    if not inspect.iscoroutinefunction(method):
        raise AgentValidationError(
            f"方法 {method_name} 必须是async def定义的异步方法"
        )

    # 校验方法参数
    sig = inspect.signature(method)
    params = list(sig.parameters.values())
    if len(params) != 1:
        raise AgentValidationError(
            f"方法 {method_name} 必须且只能有一个参数（OpenAIRequest类型），当前参数数: {len(params)}"
        )

    param = params[0]
    if param.annotation is not OpenAIRequest:
        raise AgentValidationError(
            f"方法 {method_name} 的参数必须注解为OpenAIRequest，当前注解: {param.annotation}"
        )
