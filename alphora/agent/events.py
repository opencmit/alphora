# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""流式事件协议常量。

向客户端输出的每个 chunk 由三部分组成：``content``(文本) + ``content_type``(渲染类型)
+ ``meta``(开放结构化元数据)。

``meta`` 是一个**开放的自由 dict**，开发者可以塞任意 key/value，框架原样透传到
客户端 ``delta.meta``。下面只是**约定（而非强制）的保留键和取值**，用常量收口、
方便前后端对齐，避免拼写漂移。
"""

from __future__ import annotations

from enum import Enum


class ContentType(str, Enum):
    """常用 ``content_type`` 取值。

    ``content_type`` 本身仍是自由字符串，这里只收口最常用的一批，开发者可继续传
    任意字符串。
    """

    CHAR = "char"            # 普通正文（默认）
    THINK = "think"          # 模型 reasoning / 思考过程
    STATUS = "status"        # 活动日志 / 进度（配合 meta.state 表达生命周期）
    STDOUT = "stdout"        # 工具执行成功输出
    STDERR = "stderr"        # 工具执行失败 / 错误输出
    TOOL_CALL = "tool_call"  # 工具调用开始
    TOOL_CALL_ARGS = "tool_call_args"  # 工具参数增量
    RESULT = "result"        # 最终结果
    STOP = "stop"            # 流结束信号

    # —— 多智能体协作块（collab）生命周期 —— #
    # 一段「多智能体协作」（一次并行批次 / 一次议会讨论等）的开始/结束标记。
    # content 为 JSON 字符串，详见 alphora.agent.agent_collab.AgentCollabScope。
    # collab 仅是通用的「多 agent 协作」容器；具体业务语义（如议会）由上层定义。
    AGENT_COLLAB_START = "agent_collab_start"
    AGENT_COLLAB_END = "agent_collab_end"

    # —— 议会类协作（kind=council）专用 —— #
    # 主席/主控对一轮讨论的结论或最终决议。content 为 JSON 字符串（结构由上层定义），
    # meta 一般带 collab_id + chair=True (+ round)。仅是通用承载，框架不解释其语义。
    COUNCIL_DECISION = "council_decision"

    def __str__(self) -> str:  # 让其可直接当字符串用
        return self.value


class StatusState(str, Enum):
    """``status`` 类消息的生命周期状态，放在 ``meta.state``。

    前端按同一个 ``meta.id`` 把多条 status 视作同一个块，并据 ``state`` 渲染
    "进行中 / 已完成 / 出错"。
    """

    START = "start"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


# meta 中约定的保留键名（仅为对齐用，开发者可加任意键）
class MetaKey(str, Enum):
    ID = "id"               # block 分组键
    STATE = "state"         # 生命周期状态（见 StatusState）
    AGENT_ID = "agent_id"   # 子智能体分组 / 分泳道
    AGENT_NAME = "agent_name"  # 子智能体人类可读展示名
    NAME = "name"           # 工具名等
    GROUP = "group"         # 协作分组标识（如 "swarm"）
    TASK_ID = "task_id"     # 派活实例 id（同一角色多次派活区分）

    # —— 多智能体协作块（collab）相关键 —— #
    COLLAB_ID = "collab_id"      # 一段协作块的唯一 id（与对话 session 无关）
    COLLAB_KIND = "collab_kind"  # 协作种类（如 "batch" 并行 / 上层可扩展 "council" 等）
    ROUND = "round"          # 协作内的轮次（议会类讨论用）
    TURN = "turn"            # 本轮内的发言序（议会类讨论用）
    CHAIR = "chair"          # 是否主持人/主控发言（议会类讨论用）

    def __str__(self) -> str:
        return self.value
