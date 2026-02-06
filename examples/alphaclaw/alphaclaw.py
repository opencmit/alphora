#!/usr/bin/env python3
"""
AlphaClaw - AI Agent 终端交互工具
"""

import logging
import asyncio
import os
import sys
from typing import Callable, List, Union, Optional

# --- 引入必要的库 ---
from alphora.models import OpenAILike
from alphora_community.tools.web.arxiv import ArxivSearchTool
from alphora_community.tools.web.browser import WebBrowser
from alphora_community.tools.files.file_viewer import FileViewerAgent
from alphora_community.tools.files.read_image import ImageReaderTool

from alphora.sandbox.storage.local import LocalStorage, StorageConfig

from alphora.agent.base_agent import BaseAgent
from alphora.tools.decorators import Tool
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.memory import MemoryManager
from alphora.sandbox import Sandbox, SandboxTools


vllm = OpenAILike(model_name='qwen-vl-plus', is_multimodal=True)

# ============================================================
#                        配置区域
# ============================================================

# 日志配置 - 只显示错误
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


# ============================================================
#                      终端美化工具
# ============================================================

class Colors:
    """终端颜色常量"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

    # Readline 转义符 - 用于包裹不可见字符，解决中文输入问题
    RL_START = '\001'  # 告诉 readline: 后面的字符不占显示宽度
    RL_END = '\002'    # 告诉 readline: 不可见字符结束

    @classmethod
    def rl_wrap(cls, code: str) -> str:
        """包裹颜色代码，使其在 input() 中不影响光标计算"""
        return f"{cls.RL_START}{code}{cls.RL_END}"


class Terminal:
    """终端输出工具类"""

    # ASCII Art Logo - 带龙虾形象
    LOGO = f"""
{Colors.CYAN}{Colors.BOLD}
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║      █████╗ ██╗     ██████╗ ██╗  ██╗ █████╗               ║
    ║     ██╔══██╗██║     ██╔══██╗██║  ██║██╔══██╗              ║
    ║     ███████║██║     ██████╔╝███████║███████║              ║
    ║     ██╔══██║██║     ██╔═══╝ ██╔══██║██╔══██║              ║
    ║     ██║  ██║███████╗██║     ██║  ██║██║  ██║              ║
    ║     ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝              ║
    ║                                                           ║
    ║              ██████╗██╗      █████╗ ██╗    ██╗            ║
    ║             ██╔════╝██║     ██╔══██╗██║    ██║            ║
    ║             ██║     ██║     ███████║██║ █╗ ██║            ║
    ║             ██║     ██║     ██╔══██║██║███╗██║            ║
    ║             ╚██████╗███████╗██║  ██║╚███╔███╔╝            ║
    ║              ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝             ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
{Colors.RESET}"""

    DIVIDER = f"{Colors.DIM}{'─' * 60}{Colors.RESET}"

    @staticmethod
    def clear():
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_logo():
        """打印 Logo"""
        print(Terminal.LOGO)

    @staticmethod
    def info(msg: str):
        """信息提示"""
        print(f"{Colors.BLUE}ℹ {Colors.RESET}{msg}")

    @staticmethod
    def success(msg: str):
        """成功提示"""
        print(f"{Colors.GREEN}✓ {Colors.RESET}{msg}")

    @staticmethod
    def warning(msg: str):
        """警告提示"""
        print(f"{Colors.YELLOW}⚠ {Colors.RESET}{msg}")

    @staticmethod
    def error(msg: str):
        """错误提示"""
        print(f"{Colors.RED}✗ {Colors.RESET}{msg}")

    @staticmethod
    def step(msg: str):
        """步骤提示"""
        print(f"{Colors.CYAN}→ {Colors.RESET}{msg}")

    @staticmethod
    def divider():
        """分隔线"""
        print(Terminal.DIVIDER)

    @staticmethod
    def prompt(msg: str) -> str:
        """带样式的输入提示（已修复中文输入问题）"""
        # 使用 rl_wrap 包裹颜色代码，防止 readline 计算错误
        green = Colors.rl_wrap(Colors.GREEN)
        bold = Colors.rl_wrap(Colors.BOLD)
        reset = Colors.rl_wrap(Colors.RESET)
        return input(f"\n{green}{bold}❯ {reset}{msg}")

    @staticmethod
    def ai_response_header():
        """AI 响应头"""
        print(f"\n{Colors.RED}{Colors.BOLD}🤖 AlphaClaw:{Colors.RESET}")

    @staticmethod
    def print_help():
        """打印帮助信息"""
        print(f"""
{Colors.BOLD}可用命令:{Colors.RESET}
  {Colors.CYAN}help{Colors.RESET}      显示此帮助信息
  {Colors.CYAN}clear{Colors.RESET}     清空屏幕
  {Colors.CYAN}exit{Colors.RESET}      退出程序
  {Colors.CYAN}quit{Colors.RESET}      退出程序

{Colors.BOLD}提示:{Colors.RESET}
  • 直接输入任务描述，AI 将自动执行
  • 按 Ctrl+C 可以中断当前操作
""")


# ============================================================
#                      ReAct Agent
# ============================================================

class ReActAgent(BaseAgent):
    """ReAct 模式的 AI Agent"""

    agent_type: str = "ReActAgent"

    def __init__(
            self,
            llm: OpenAILike,
            tools: List[Union[Tool, Callable]],
            system_prompt: str = "",
            max_iterations: int = 100,
            sandbox: Optional[Sandbox] = None,
            memory: Optional[MemoryManager] = None,
            **kwargs
    ):
        super().__init__(llm=llm, memory=memory, **kwargs)

        self._registry = ToolRegistry()
        self._sandbox = sandbox
        self._sandbox_tools: Optional["SandboxTools"] = None

        # 注册用户提供的工具
        for t in tools:
            self._registry.register(t)

        if sandbox is not None:
            self._setup_sandbox_tools(sandbox)

        self._executor = ToolExecutor(self._registry)
        system_prompt = self._get_default_system_prompt()

        self._system_prompt = system_prompt
        self._prompt = self.create_prompt(system_prompt=system_prompt)
        self._max_iterations = max_iterations

    def _get_default_system_prompt(self) -> str:
        return (
                "## Core Identity\n"
                "你是一个拥有 **Root 权限** 的高智商 Shell 原生智能体 (Shell-Native Agent)。\n"
                "你的核心能力不在于空想，而在于**通过执行 Shell 指令来感知环境、解决问题和验证结果**。\n\n"

                "## Operational Protocols (行动准则)\n"
                "1. **Shell First 策略**：\n"
                "   - 遇到未知，先用 `ls`, `grep`, `find` 探测。\n"
                "   - 遇到文本处理，优先使用 `sed`, `awk` 或编写临时 Python 脚本处理，而非手动逐字修改。\n"
                "   - 遇到依赖缺失，你有权判断并执行 `pip install` 或 `apt-get`（需保持环境清洁）。\n"
                "2. **智能闭环 (The Intelligent Loop)**：\n"
                "   - **执行 -> 报错 -> 分析 -> 修正**。如果指令失败，不要仅是道歉，要利用 Shell 的报错信息进行自我修复。\n"
                "3. **文件系统审计 (CHANGELOG)**：\n"
                "   - 你对文件系统的每一次 **Write/Modify/Delete** 操作，都必须在 `CHANGELOG.md` 中留下审计记录。\n"
                "   - 格式：`echo ' ACTION: <简述> | FILE: <路径>' >> CHANGELOG.md`\n\n"
        "## Goal\n"
        "像一个顶级黑客或系统架构师一样思考。利用 Shell 的强大能力，自动化、精准地完成用户任务。"
        )

    def _setup_sandbox_tools(self, sandbox: Sandbox) -> None:
        from alphora.sandbox import SandboxTools
        self._sandbox_tools = SandboxTools(sandbox)
        # self._registry.register(self._sandbox_tools.save_file)
        # self._registry.register(self._sandbox_tools.list_files)
        self._registry.register(self._sandbox_tools.run_shell_command)

    async def run(self, query: str) -> str:
        self.memory.add_user(content=query)
        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            logger.debug(f"ReAct iteration {iteration + 1}/{self._max_iterations}")

            history = self.memory.build_history()
            Terminal.ai_response_header()

            response = await self._prompt.acall(
                query=query if iteration == 0 else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
                runtime_system_prompt='如果你认为用户的任务已经完成，请直接输出 TASK_FINISHED'
            )

            Terminal.divider()
            self.memory.add_assistant(content=response)

            if not response.has_tool_calls:
                if "TASK_FINISHED" in response.content:
                    Terminal.success("任务已完成")
                    return ""
                else:
                    await self.stream.astream_message(content=response.content)
                    self.memory.add_assistant(content=response.content)

            tool_results = await self._executor.execute(response.tool_calls)
            self.memory.add_tool_result(result=tool_results)

            if self.verbose:
                for result in tool_results:
                    if result.status == "success":
                        Terminal.success(f"{result.tool_name}: {result.content[:100]}...")
                    else:
                        Terminal.error(f"{result.tool_name}: {result.content[:100]}...")

        Terminal.warning(f"已达到最大迭代次数 ({self._max_iterations})")
        return "抱歉，我无法在限定步骤内完成这个任务。"

    @property
    def tools(self) -> List[Tool]:
        return self._registry.get_all_tools()

    @property
    def sandbox(self) -> Optional["Sandbox"]:
        return self._sandbox


# ============================================================
#                        主程序
# ============================================================

def get_script_directory() -> str:
    """获取脚本所在目录"""
    return os.path.dirname(os.path.abspath(__file__))


def get_workspace_path() -> str:
    """获取并验证工作目录路径，支持默认值"""

    # 默认工作目录：脚本所在目录下的 workspace 文件夹
    default_workspace = os.path.join(get_script_directory(), "workspace")

    Terminal.divider()
    Terminal.info(f"默认工作目录: {Colors.DIM}{default_workspace}{Colors.RESET}")

    while True:
        path = Terminal.prompt("请输入工作目录路径 (直接回车使用默认): ").strip()

        # 如果用户直接回车，使用默认路径
        if not path:
            path = default_workspace
            Terminal.info(f"使用默认工作目录")

        # 展开用户目录符号 ~
        path = os.path.expanduser(path)

        # 如果是相对路径，转换为绝对路径（相对于脚本目录）
        if not os.path.isabs(path):
            path = os.path.join(get_script_directory(), path)

        # 如果路径不存在，询问是否创建
        if not os.path.exists(path):
            Terminal.warning(f"路径不存在: {path}")
            create = Terminal.prompt("是否创建该目录? [Y/n]: ").strip().lower()
            if create != 'n':
                try:
                    os.makedirs(path, exist_ok=True)
                    Terminal.success(f"已创建目录: {path}")
                except Exception as e:
                    Terminal.error(f"创建失败: {e}")
                    continue
            else:
                continue

        if not os.path.isdir(path):
            Terminal.error("指定的路径不是一个目录")
            continue

        return path


async def main():
    """主函数"""
    Terminal.clear()
    Terminal.print_logo()

    print(f"{Colors.DIM}  输入 'help' 查看帮助 | 'exit' 退出程序{Colors.RESET}\n")

    # 1. 获取工作目录
    workspace_path = get_workspace_path()
    Terminal.success(f"工作目录: {workspace_path}")

    # 2. 初始化系统
    Terminal.divider()
    Terminal.step("正在初始化系统组件...")

    try:
        # 初始化 LLM
        Terminal.info("加载语言模型...")
        llm = OpenAILike(max_tokens=8000)

        # 配置存储 - 使用父目录作为存储根目录
        # 这样 sandbox_id 就可以是目标文件夹的名称
        parent_dir = os.path.dirname(workspace_path)
        folder_name = os.path.basename(workspace_path)

        Terminal.info(f"配置沙箱环境...")
        config = StorageConfig.local(parent_dir)
        storage = LocalStorage(config=config)

        # 使用文件夹名称作为 sandbox_id
        # 这样沙箱的实际路径就是 parent_dir/folder_name = workspace_path
        sandbox = Sandbox.create_docker(sandbox_id=folder_name, storage=storage)

        # 初始化工具
        Terminal.info("加载工具集...")
        arxiv = ArxivSearchTool()
        browser = WebBrowser()
        file_agent = FileViewerAgent(sandbox=sandbox)

        image_reader = ImageReaderTool(llm=vllm)

        # 初始化 Agent
        Terminal.info("初始化 AI Agent...")
        react = ReActAgent(
            llm=llm,
            sandbox=sandbox,
            tools=[browser.fetch, file_agent.view_file, image_reader.analyze],
            system_prompt='每次调用工具之前，都输出一小段文字说明你的思考过程。并且牢记你对文件系统的每一次 **Write/Modify/Delete** 操作，都必须在 `CHANGELOG.md` 中留下审计记录。'
        )

        # 启动沙箱
        Terminal.info("启动沙箱容器...")
        await sandbox.start()

        Terminal.success("系统初始化完成！")
        Terminal.divider()

    except Exception as e:
        Terminal.error(f"初始化失败: {e}")
        Terminal.info("请检查配置后重试")
        return

    # 3. 打印帮助信息
    Terminal.print_help()

    # 4. 主交互循环
    while True:
        try:
            user_input = Terminal.prompt("").strip()

            if not user_input:
                continue

            # 处理内置命令
            cmd = user_input.lower()

            if cmd in ['exit', 'quit', 'q']:
                Terminal.info("正在关闭系统...")
                break

            if cmd == 'help':
                Terminal.print_help()
                continue

            if cmd == 'clear':
                Terminal.clear()
                Terminal.print_logo()
                continue

            # 执行 AI 任务
            await react.run(query=user_input)

        except KeyboardInterrupt:
            print()  # 换行
            Terminal.warning("操作已中断")
            continue
        except Exception as e:
            Terminal.error(f"执行出错: {e}")
            logger.exception("运行时错误")

    # 5. 清理资源
    Terminal.step("正在清理资源...")
    try:
        await sandbox.destroy()
        Terminal.success("沙箱已关闭")
    except Exception as e:
        Terminal.warning(f"清理时出错: {e}")

    print(f"\n{Colors.CYAN}感谢使用 AlphaClaw，再见！{Colors.RESET}\n")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}程序已退出{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}程序异常退出: {e}{Colors.RESET}")
        sys.exit(1)