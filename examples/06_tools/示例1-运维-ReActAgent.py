import asyncio
import os
import json
import logging
from typing import List, Dict

# 1. 导入 Alphora 核心组件
from alphora.agent.react import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool, ToolRegistry, ToolExecutor
from alphora.models.llms.types import ToolCall

# 2. 导入 Pydantic 用于参数定义
from pydantic import Field

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==============================================================================
# 1. 定义真实的运维工具 (Real-world DevOps Tools)
# ==============================================================================

@tool
def check_server_health(ip: str):
    """
    检查指定服务器的健康状态（CPU、内存、磁盘）。
    """
    logger.info(f"正在连接 {ip} 检查健康状态...")
    # 模拟真实数据：假设 192.168.1.100 负载很高
    if ip == "192.168.1.100":
        return {
            "status": "warning",
            "cpu_usage": "92%",
            "memory_usage": "85%",
            "disk_free": "12GB",
            "active_alerts": ["High CPU Load"]
        }
    return {
        "status": "healthy",
        "cpu_usage": "15%",
        "memory_usage": "40%",
        "disk_free": "200GB",
        "active_alerts": []
    }

@tool
async def fetch_error_logs(
        service_name: str,
        lines: int = 5
):
    """
    获取指定服务的最近几条错误日志。
    """
    await asyncio.sleep(1)    # 模拟 IO 耗时
    logger.info(f"正在读取 {service_name} 的日志...")

    if service_name == "payment-service":
        return [
            "ERROR 2023-10-27 10:01:05 - Connection timed out to DB-01",
            "ERROR 2023-10-27 10:01:06 - Retry attempt 1 failed",
            "CRITICAL 2023-10-27 10:01:07 - Transaction aborted"
        ]
    return ["INFO: Service is running smoothly."]


@tool
def restart_service(
        service_name: str,
        confirm_backup: bool
):
    """
    重启服务。注意：这是一个高风险操作，模型必须先确认备份。
    """
    if not confirm_backup:
        raise ValueError("安全拦截：未确认数据备份，无法执行重启操作！")

    logger.warning(f"正在执行重启操作: {service_name}...")
    return {"status": "success", "message": f"Service '{service_name}' restarted successfully."}


# ==============================================================================
# 2. 构建 Agent 循环 (The Agent Loop)
# ==============================================================================

async def run_agent_loop(query: str):

    llm = OpenAILike()

    system_prompt = """你是一个资深的 SRE 运维专家。
你的职责是诊断系统故障并修复问题。
- 在采取危险操作（如重启）前，必须仔细分析日志。
- 只有在确认安全后才能调用执行类工具。
- 请用简洁专业的风格回答。
"""

    agent = ReActAgent(llm=llm,
                       tools=[check_server_health, fetch_error_logs, restart_service],
                       system_prompt=system_prompt)

    print(f"\n🔵 [User]: {query}")

    print("🟡 [Agent]: 正在分析需求并规划工具调用...")

    resp = await agent.run(query=query)
    print(resp)


# ==============================================================================
# 3. 运行入口
# ==============================================================================

if __name__ == "__main__":
    # 场景：服务器报警，Agent 需要自主诊断
    # 预期流程：
    # 1. 检查服务器健康 -> 发现 CPU 高
    # 2. 自动决定去查 'payment-service' 的日志 -> 发现 DB 链接错误
    # 3. 建议用户（或尝试）修复

    user_query = "服务器 192.168.1.100 报警了，帮我排查一下原因，如果是支付服务的问题，请告诉我具体的错误日志。"

    try:
        asyncio.run(run_agent_loop(user_query))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"运行出错: {e}")