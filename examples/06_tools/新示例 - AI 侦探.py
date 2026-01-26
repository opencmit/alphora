import asyncio
import logging
import json
from typing import List, Dict, Any

from alphora.agent import BaseAgent
from alphora.models import OpenAILike
from alphora.tools import tool, ToolRegistry, ToolExecutor
from alphora.models.llms.types import ToolCall

from alphora.memory import MemoryManager

from pydantic import Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("Detective_Agent")

# --- 1. 探案工具集 (Forensics & Interrogation Tools) ---

@tool
def read_case_file(case_id: str):
    """
    [第一步] 读取案件卷宗，获取案情背景、嫌疑人名单和初始物证。
    """
    logger.info(f"正在调取案件卷宗: {case_id}...")
    return {
        "case_title": "豪宅密室蓝宝石失窃案",
        "description": "昨晚 22:00-23:00 期间，书房保险柜内的'蔚蓝之心'被盗。现场无强行闯入痕迹。",
        "suspects": ["管家(Butler)", "园丁(Gardener)", "私人医生(Doctor)"],
        "initial_evidence": [
            {"id": "EV-01", "desc": "地毯上的一块奇怪泥土污渍"},
            {"id": "EV-02", "desc": "破碎的红酒杯，残留微量液体"}
        ]
    }

@tool
def analyze_forensic_evidence(evidence_id: str):
    """
    [鉴识科] 对物证进行化验。可以分析泥土成分、指纹或化学物质。
    """
    logger.info(f"正在化验物证: {evidence_id}")

    if evidence_id == "EV-01":
        return {
            "result": "成分分析：富含稀有白磷矿物质的红壤。",
            "implication": "这种土壤只存在于庄园的后花园温室中，普通草坪没有。"
        }
    elif evidence_id == "EV-02":
        return {
            "result": "指纹提取失败（被擦拭），但检测到微量'乙醚'成分。",
            "implication": "受害者可能在失窃前被迷晕。"
        }
    return {"error": "Evidence not found"}

@tool
def check_surveillance_log(location: str, time_range: str):
    """
    [安保中心] 调取特定区域的监控出入记录。
    """
    logger.info(f"正在查阅监控日志: {location} ({time_range})")

    if "garden" in location.lower() or "greenhouse" in location.lower() or "温室" in location:
        return [
            "22:15 - 园丁离开温室",
            "22:30 - 管家进入温室 (携带清洁工具)",    # 疑点：管家大晚上去温室干嘛？
            "22:45 - 管家离开温室"
        ]
    return ["无异常记录"]

@tool
def interrogate_suspect(name: str, question_topic: str):
    """
    [审讯] 询问嫌疑人特定问题。用来验证时间线或寻找口供矛盾。
    """
    logger.info(f"正在审讯嫌疑人 {name}: 关于 '{question_topic}'")

    if name == "管家(Butler)":
        if "温室" in question_topic or "泥土" in question_topic:
            # 这是一个谎言，Agent 需要通过监控记录拆穿它
            return "我？我昨晚一直在厨房擦银器，根本没去过后花园那种脏地方！"
        return "我对老爷忠心耿耿。"

    if name == "园丁(Gardener)":
        return "我22:15就回宿舍睡觉了，医生可以给我作证，他当时给了我安眠药。"

    return "无可奉告。"

@tool
def submit_arrest_warrant(suspect_name: str, motive: str, evidence_chain: str):
    """
    [结案] 当确认凶手并拥有完整证据链时，提交逮捕令。
    """
    logger.info(f"正在申请逮捕令 -> 嫌疑人: {suspect_name}")
    return {
        "status": "APPROVED",
        "verdict": "CASE CLOSED",
        "message": f"逮捕令已签发。依据是：{evidence_chain}。干得好，侦探。"
    }


# --- 2. 核心推理流程 ---

async def run_detective_session(user_objective: str):
    # --- 初始化 ---
    registry = ToolRegistry()
    registry.register(read_case_file)
    registry.register(analyze_forensic_evidence)
    registry.register(check_surveillance_log)
    registry.register(interrogate_suspect)
    registry.register(submit_arrest_warrant)

    executor = ToolExecutor(registry)
    llm = OpenAILike()

    # --- System Prompt (赋予灵魂) ---
    # 这里的关键是让 Agent 学会 "质疑" 和 "验证"
    system_prompt = """你是一位世界顶级的 AI 侦探。
你的目标是找出真相。不要随意猜测，必须基于证据链（Chain of Evidence）行动。

推理法则：
1. **全面了解**：先看卷宗。
2. **循迹追踪**：如果有物理物证（如泥土），先查验它的来源。
3. **交叉验证**：如果物证指向某个地点，去查该地点的监控。
4. **寻找矛盾**：如果监控显示某人去过该地，而审讯时他却否认，那就是铁证。
5. **结案**：只有当有了完整的逻辑链（动机+物证+谎言）时，才申请逮捕。

请开始你的调查。
"""

    agent = BaseAgent(llm=llm)
    prompt = agent.create_prompt(
        system_prompt=system_prompt,
    )

    print(f"\n🕵️‍♂️ [委托人]: {user_objective}")

    # --- 循环逻辑 ---
    max_turns = 30
    current_turn = 0

    memory = MemoryManager()

    # 添加用户的输入
    memory.add_user(content=user_objective)

    while current_turn < max_turns:
        current_turn += 1

        print(f"\n--- Round {current_turn} of Investigation ---")

        response = await prompt.acall(
            tools=registry.get_openai_tools_schema(),
            is_stream=True,
            runtime_system_prompt='如果证据不足，继续调用工具搜查；如果证据确凿，请调用 submit_arrest_warrant。',
            history=memory.build_history()
        )

        memory.add_assistant(content=response)   # 添加大模型的返回（无需判断是否是工具调用）

        if response.has_tool_calls:   # 假如有调用工具
            tool_calls = response

            print(f"🟡 [侦探决定行动]:\n")
            execution_results = await executor.execute(tool_calls)
            memory.add_tool_result(result=execution_results)    # 直接把 Executor 的输出传入记忆即可

            print(response.format_details())   # 展示工具调用详情

            print(f"🟢 [现场反馈]: {execution_results}")

        else:
            # 3. 结案陈词
            final_report = response
            print(f"🔵 [侦探结案报告]:\n{final_report}")
            break

if __name__ == "__main__":
    # 场景：这是一个开放式谜题，Agent 必须自己去探索
    case_query = "警长，这起蓝宝石失窃案非常蹊跷，请找出真凶。"

    try:
        asyncio.run(run_detective_session(case_query))
    except Exception as e:
        logger.error(f"Investigation aborted: {e}", exc_info=True)