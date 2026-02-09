"""
ChatExcel 主入口
Excel数据对话智能体
"""

import os
import base64
from uuid import uuid4
from typing import Any, Iterable

from alphora.tools import ToolExecutor, ToolRegistry
from alphora.models.llms.types import ToolCall
from alphora.agent import BaseAgent
from alphora.sandbox.sandbox import Sandbox
from alphora.server.openai_request_body import OpenAIRequest

from alphora_community.tools import FileViewer

from examples.chat_excel.prompts import control_prompt, thinking_prompt


class ExecuteCodeStep(BaseAgent):

    def __init__(self, sandbox: Sandbox, **kwargs):
        super().__init__(**kwargs)
        self.sandbox = sandbox

    async def execute_code_step(
            self,
            description: str,
            code: str
    ) -> str:
        """
        执行单步 Python 代码片段，用于迭代式数据探索和处理。

        Args:
            description: 本步骤的目的说明（如"查看数据结构"、"按城市分组统计"）
            code: 要执行的 Python 代码，建议：
            - 尽量控制在 30 行以内，只做一件事
            - 必须用 print() 输出你想观察的结果
            - 开头写好 import 语句

        【使用场景】
        - 分步探索数据：先看数据结构，再决定下一步
        - 验证处理思路：测试某个想法是否可行
        - 复杂任务拆解：把大任务分成多个小步骤逐一执行

        【重要特性】
        - 每次执行都是独立环境，变量不会保留到下次
        - 每次都需要重新 import 依赖库和读取文件
        - 不会自动修复错误，你需要根据报错自行调整

        【文件系统】
        代码在沙箱环境中执行，可自由读写当前目录下的文件：
        - 读取用户上传的文件
        - 保存处理后的数据、图表、报告等
        - 创建临时文件供后续步骤使用
        文件会持久保存在沙箱中，后续步骤可直接访问。

        【其他】
        如果涉及matplotlib画图，matplotlib需要这样使用，才能正确展示中文字体：
        plt.rcParams['font.sans-serif'] = ['Source Han Sans CN']
        plt.rcParams['axes.unicode_minus'] = False

        Returns:
            执行结果（stdout 或 stderr）
        """
        await self.stream.astream_message(content=description, interval=0.01)
        await self.stream.astream_message(content_type='m_python', content=code)

        result = await self.sandbox.execute_code(code=code)

        if result.success:
            output = result.stdout or "(执行成功，无输出)"
            if result.output_files:
                output += f"\n\n生成的文件: {result.output_files}"
            return output
        else:
            return f"执行出错:\n{result.stderr}"


class ChatExcel(BaseAgent):
    """Excel数据对话智能体主类"""

    @staticmethod
    def _safe_sandbox_path(file_name: str) -> str:
        """规范化并防止路径穿越"""
        if not file_name:
            return "unnamed"
        normalized = os.path.normpath(str(file_name)).replace("\\", "/").lstrip("/")
        if normalized.startswith(".."):
            return os.path.basename(normalized)
        return normalized

    @staticmethod
    def _extract_text_content(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        texts.append(str(text))
            return "".join(texts)
        if isinstance(content, dict):
            text = content.get("text")
            return str(text) if text is not None else ""
        return str(content)

    @staticmethod
    def _normalize_file_items(payload: Any) -> Iterable[dict]:
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    @staticmethod
    def _decode_file_content(content: Any) -> bytes:
        if content is None:
            return b""
        if isinstance(content, bytes):
            return content
        if not isinstance(content, str):
            content = str(content)
        if content.startswith("data:") and "," in content:
            content = content.split(",", 1)[1]
        try:
            return base64.b64decode(content, validate=True)
        except Exception:
            return content.encode("utf-8")

    async def excel_answering(self, request: OpenAIRequest) -> ...:
        """处理Excel数据分析查询"""
        # 解析请求
        query, files, session_id = self._parse_request(request)

        # 空查询处理
        if not query:
            await self.stream.astream_message(
                content='您好，我是梧桐数据分析智能体，请问您想分析什么数据？'
            )
            await self.stream.astop(stop_reason='end')
            return None

        # 初始化沙箱
        sandbox = await self._init_sandbox(session_id, files)

        view_files_agent = FileViewer(sandbox=sandbox)

        python_coder_agent = ExecuteCodeStep(sandbox=sandbox)
        python_coder_agent = self.derive(python_coder_agent)

        # 注册工具
        register = ToolRegistry()

        register.register(view_files_agent.view_file)    # 查看数据工具
        register.register(python_coder_agent.execute_code_step)

        # 工具执行器
        tool_executor = ToolExecutor(registry=register)

        # 列出所有的文件名
        file_names = list(files.keys())

        mm = self.memory

        if file_names:
            mm.add_user(session_id=session_id,
                        content=f'我上传了以下文件: {file_names}, 我提出的任务是{query}')
        else:
            mm.add_user(session_id=session_id,
                        content=f'我提出的任务是{query}')

        # 主控prompt
        control_prompter = self.create_prompt(system_prompt=control_prompt)

        # 思考prompt
        thinking_prompter = self.create_prompt(system_prompt=thinking_prompt)

        thinking_prompter.update_placeholder(
            files=file_names,
            today=self.today(),
            tools=register.get_openai_tools_schema()
        )

        history = mm.build_history(session_id=session_id)

        for step in range(20):

            files = await sandbox.list_files(recursive=True)

            files = [file.path for file in files]

            control_prompter.update_placeholder(files=files,
                                                today=self.today(),
                                                session_id=session_id)

            history = mm.build_history(session_id=session_id)

            await self.stream.astream_message(content='\n')

            runtime_sys_prompt = f"""
# 执行时规则

## 规则一：先说话，再行动

每次调用工具之前，必须先输出一段文字告诉用户你在做什么。

用户看不到工具调用过程，如果你沉默着调用工具，用户会看到长时间空白，以为系统卡死了。

**示例：**
- "让我先看一下数据文件的结构..."
- "数据结构确认了，现在计算月度汇总..."
- "计算完成，正在生成图表..."

简洁自然即可，一两句话即可。

---

## 规则二：任务结束时的输出格式

### 情况A：完成了数据分析/处理任务

1. **总结结果**：说明完成了什么、关键发现是什么，可用表格辅助展示

2. **展示文件**（如有生成）：
   - 图片：`![图片说明](http://43.143.212.30:8378/{session_id}/文件路径.png)`
   - 其他：`[📎 点击下载 文件名.xlsx](http://43.143.212.30:8378/{session_id}/文件路径.xlsx)`
   - 注意，因为文件是保存在沙箱服务器上的静态资源，输出必须是链接并且保留文件的完整相对路径，如 output/report.xlsx、charts/trend.png

3. **结束标记**：最后单独一行输出 `TASK_FINISHED`
"""

            tc_resp: ToolCall = await control_prompter.acall(query=None,
                                                             runtime_system_prompt=runtime_sys_prompt,
                                                             is_stream=True,
                                                             history=history,
                                                             tools=register.get_openai_tools_schema()
                                                             )

            # 这里是新增大模型工具调用的情况
            mm.add_assistant(content=tc_resp,
                             session_id=session_id,)

            if 'TASK_FINISHED' in tc_resp.content:
                return

            await self.stream.astream_message(content='\n\n')

            if tc_resp.has_tool_calls:
                tool_return = await tool_executor.execute(tool_calls=tc_resp)
                mm.add_tool_result(result=tool_return,
                                   session_id=session_id)

            else:
                mm.add_assistant(content=tc_resp,
                                 session_id=session_id)

        return "None"

    async def _init_sandbox(self, session_id: str, files: dict) -> Sandbox:
        """初始化沙箱环境"""

        if not session_id:
            session_id = str(uuid4())[:8]

        workspace_dir = "./chatexcel_workspace"
        sandbox_base_path = os.path.join(workspace_dir, "sandbox")

        sandbox = Sandbox.create_docker(
            base_path=sandbox_base_path,
            sandbox_id=session_id
        )
        await sandbox.start()
        print(f'沙箱已初始化{sandbox.workspace_path}')

        # 上传文件到沙箱
        for file_name, file_content in files.items():
            if isinstance(file_content, bytes):
                await sandbox.write_file_bytes(path=file_name, content=file_content)
            else:
                await sandbox.upload_file_base64(path=file_name, base64_data=file_content)
        return sandbox

    def _parse_request(self, request: OpenAIRequest) -> tuple:
        """
        解析请求

        Returns:
            (query, files_dict, session_id)
        """
        messages = request.messages
        session_id = request.session_id

        query = ""
        files = {}

        for message in messages:
            role = message.get('role', '')
            content = message.get('content', '')

            if role == 'user':
                query = content
            elif role != 'user' and content:
                files[role] = content

        return query, files, session_id

    @staticmethod
    def today():
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return now_str

    async def run_logic(self, request: OpenAIRequest):
        """运行主逻辑（框架入口）"""
        try:
            await self.excel_answering(request=request)
        except Exception as e:
            await self.stream.astop(stop_reason=str(e))

        await self.stream.astop(stop_reason='end')


if __name__ == "__main__":

    import uvicorn
    from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
    from alphora.models.llms import OpenAILike

    llm = OpenAILike(
        max_tokens=8000
    )

    # 初始化一个Agent
    agent = ChatExcel(llm=llm)

    # API发布配置信息
    config = APIPublisherConfig(
        path='/chatexcel'
    )

    # 4. 发布 API
    app = publish_agent_api(
        agent=agent,
        method="run_logic",
        config=config
    )

    uvicorn.run(
        app,
        host='127.0.0.1',
        port=8001
    )