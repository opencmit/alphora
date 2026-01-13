"""
Alphora Advanced Examples - 高级示例

本文件演示高级用法：
1. 自定义Agent类
2. Agent派生（Derivation）
3. 多组件集成
4. 复杂工作流
5. Agent协作
6. 动态Prompt生成
7. 高级记忆策略
8. 生产环境最佳实践

这些示例展示了如何构建复杂的AI应用
"""

import os
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from alphora.agent import BaseAgent
from alphora.prompter import BasePrompt
from alphora.memory import MemoryManager, MemoryType
from alphora.tools import Tool, tool, ToolExecutor
from alphora.storage import SQLiteStorage, InMemoryStorage
from alphora.sandbox import Sandbox, SandboxConfig


# ============================================================
# 示例 1: 自定义Agent类
# ============================================================
def example_1_custom_agent():
    """
    创建自定义Agent类

    通过继承BaseAgent并添加自定义功能
    """
    print("=" * 60)
    print("示例 1: 自定义Agent类")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    from alphora.tools import tool
    from alphora.memory import MemoryManager
    
    class CustomerServiceAgent(BaseAgent):
        '''客服Agent'''
        
        def __init__(self, company_name: str, **kwargs):
            super().__init__(**kwargs)
            self.company_name = company_name
            self.ticket_counter = 0
            
            # 初始化组件
            self._setup_tools()
            self._setup_memory()
            self._setup_prompts()
        
        def _setup_tools(self):
            '''设置工具'''
            @tool
            def create_ticket(issue: str, priority: str = "normal") -> dict:
                '''创建工单'''
                self.ticket_counter += 1
                return {
                    "ticket_id": f"TKT-{self.ticket_counter:04d}",
                    "issue": issue,
                    "priority": priority,
                    "status": "open"
                }
            
            @tool
            def search_faq(query: str) -> list:
                '''搜索FAQ'''
                # 模拟FAQ搜索
                return [
                    {"question": "如何退款？", "answer": "..."},
                    {"question": "配送时间？", "answer": "..."}
                ]
            
            self.register_tool(create_ticket)
            self.register_tool(search_faq)
        
        def _setup_memory(self):
            '''设置记忆'''
            self.memory = MemoryManager(
                storage_type="sqlite",
                storage_path="./customer_service.db"
            )
        
        def _setup_prompts(self):
            '''设置Prompt'''
            self.greeting_prompt = self.create_prompt(
                system_prompt=f'''你是{self.company_name}的客服助手。
                你的职责是：
                1. 解答客户问题
                2. 处理投诉和建议
                3. 创建工单跟踪问题
                
                请保持友好、专业的态度。''',
                enable_memory=True
            )
        
        async def handle_customer(self, customer_id: str, message: str) -> str:
            '''处理客户消息'''
            # 使用客户ID作为会话ID
            response = await self.greeting_prompt.acall(
                query=message,
                memory_id=customer_id,
                is_stream=False
            )
            return response
        
        def get_customer_history(self, customer_id: str) -> str:
            '''获取客户历史'''
            return self.memory.build_history(
                memory_id=customer_id,
                format="text"
            )
    
    # 使用自定义Agent
    agent = CustomerServiceAgent(
        company_name="示例公司",
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        default_llm=os.getenv("DEFAULT_LLM")
    )
    
    # 处理客户请求
    response = await agent.handle_customer("C001", "我想退货")
    """)

    print("\n自定义Agent的关键点:")
    print("  1. 继承 BaseAgent")
    print("  2. 在 __init__ 中初始化组件")
    print("  3. 封装业务逻辑为方法")
    print("  4. 使用组合而非继承添加功能")


# ============================================================
# 示例 2: Agent派生（Derivation）
# ============================================================
def example_2_agent_derivation():
    """
    从现有Agent派生新Agent

    派生允许基于现有Agent创建专门化版本
    """
    print("\n" + "=" * 60)
    print("示例 2: Agent派生（Derivation）")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    
    # 创建基础Agent
    base_agent = BaseAgent(
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        default_llm=os.getenv("DEFAULT_LLM")
    )
    
    # 派生方式1：使用 derive 方法
    python_expert = base_agent.derive(
        name="Python专家",
        system_prompt="你是一位Python编程专家...",
        temperature=0.3,
        additional_tools=[code_runner_tool]
    )
    
    # 派生方式2：使用 from_agent 类方法
    java_expert = BaseAgent.from_agent(
        base_agent,
        name="Java专家",
        system_prompt="你是一位Java编程专家...",
        temperature=0.3
    )
    
    # 派生方式3：链式派生
    senior_python_expert = python_expert.derive(
        name="资深Python专家",
        system_prompt="你是一位拥有10年经验的Python专家...",
        additional_context={"expertise_level": "senior"}
    )
    
    # 使用派生Agent
    response = await python_expert.chat("如何实现单例模式？")
    """)

    print("\n派生的优势:")
    print("  1. 复用基础配置（LLM、存储等）")
    print("  2. 专门化系统提示")
    print("  3. 调整参数（temperature、max_tokens等）")
    print("  4. 添加特定工具")
    print("  5. 链式派生创建层级")


# ============================================================
# 示例 3: 多组件集成
# ============================================================
def example_3_component_integration():
    """
    集成多个组件构建完整应用
    """
    print("\n" + "=" * 60)
    print("示例 3: 多组件集成")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    from alphora.memory import MemoryManager
    from alphora.tools import tool, ToolExecutor
    from alphora.storage import SQLiteStorage
    from alphora.sandbox import Sandbox
    from alphora.postprocess import FilterPP, JsonKeyExtractorPP
    
    class IntegratedAgent:
        '''集成所有组件的完整Agent'''
        
        def __init__(self, data_dir: str = "./data"):
            # 存储
            self.storage = SQLiteStorage(path=f"{data_dir}/agent.db")
            
            # 记忆
            self.memory = MemoryManager(
                storage_path=f"{data_dir}/memory.db",
                storage_type="sqlite"
            )
            
            # 沙箱
            self.sandbox = Sandbox(config=SandboxConfig(
                timeout=30,
                allowed_imports=["math", "json", "datetime"]
            ))
            
            # 工具执行器
            self.tool_executor = ToolExecutor()
            self._register_tools()
            
            # Agent
            self.agent = BaseAgent(
                llm_api_key=os.getenv("LLM_API_KEY"),
                llm_base_url=os.getenv("LLM_BASE_URL"),
                default_llm=os.getenv("DEFAULT_LLM"),
                storage=self.storage
            )
            
            # Prompts
            self._setup_prompts()
        
        def _register_tools(self):
            @tool
            def run_code(code: str) -> dict:
                '''执行Python代码'''
                result = self.sandbox.execute(code)
                return {
                    "success": result.success,
                    "output": result.stdout,
                    "error": result.error_message
                }
            
            @tool
            def save_note(title: str, content: str) -> dict:
                '''保存笔记'''
                key = f"note:{datetime.now().strftime('%Y%m%d%H%M%S')}"
                self.storage.set(key, {"title": title, "content": content})
                return {"status": "saved", "key": key}
            
            @tool
            def search_notes(query: str) -> list:
                '''搜索笔记'''
                notes = []
                for key in self.storage.keys():
                    if key.startswith("note:"):
                        note = self.storage.get(key)
                        if query.lower() in note["title"].lower():
                            notes.append(note)
                return notes
            
            self.tool_executor.register(run_code)
            self.tool_executor.register(save_note)
            self.tool_executor.register(search_notes)
        
        def _setup_prompts(self):
            # 分析Prompt
            self.analysis_prompt = self.agent.create_prompt(
                system_prompt="你是一个数据分析专家...",
                tools=self.tool_executor.tools,
                output_format="json",
                postprocessor=[JsonKeyExtractorPP(target_key="analysis")]
            )
            
            # 聊天Prompt
            self.chat_prompt = self.agent.create_prompt(
                system_prompt="你是一个友好的助手...",
                enable_memory=True
            )
        
        async def analyze(self, data: str, user_id: str) -> dict:
            '''分析数据'''
            response = await self.analysis_prompt.acall(
                query=f"分析以下数据：{data}",
                memory_id=user_id,
                is_stream=False
            )
            return response
        
        async def chat(self, message: str, user_id: str) -> str:
            '''聊天'''
            return await self.chat_prompt.acall(
                query=message,
                memory_id=user_id,
                is_stream=False
            )
    
    # 使用
    agent = IntegratedAgent()
    result = await agent.analyze("销售数据...", "user_001")
    response = await agent.chat("你好", "user_001")
    """)


# ============================================================
# 示例 4: 复杂工作流
# ============================================================
def example_4_complex_workflow():
    """
    实现复杂的多步骤工作流
    """
    print("\n" + "=" * 60)
    print("示例 4: 复杂工作流")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    from alphora.prompter import ParallelPrompt
    
    class DocumentWorkflow:
        '''文档处理工作流'''
        
        def __init__(self, agent: BaseAgent):
            self.agent = agent
            
            # 步骤1：内容分析
            self.analyzer = agent.create_prompt(
                system_prompt="分析文档内容，提取关键信息..."
            )
            
            # 步骤2：多角度评估（并行）
            self.evaluators = ParallelPrompt([
                agent.create_prompt(system_prompt="从技术角度评估..."),
                agent.create_prompt(system_prompt="从商业角度评估..."),
                agent.create_prompt(system_prompt="从风险角度评估...")
            ])
            
            # 步骤3：综合报告
            self.reporter = agent.create_prompt(
                system_prompt="综合各方意见，生成最终报告..."
            )
        
        async def process(self, document: str) -> dict:
            '''处理文档'''
            results = {}
            
            # 步骤1：分析
            print("步骤1：分析文档...")
            analysis = await self.analyzer.acall(
                query=document,
                is_stream=False
            )
            results["analysis"] = analysis
            
            # 步骤2：并行评估
            print("步骤2：多角度评估...")
            evaluations = await self.evaluators.acall(
                query=f"基于分析结果评估：{analysis}",
                is_stream=False
            )
            results["evaluations"] = {
                "technical": evaluations[0],
                "business": evaluations[1],
                "risk": evaluations[2]
            }
            
            # 步骤3：生成报告
            print("步骤3：生成报告...")
            report = await self.reporter.acall(
                query=f'''
                分析结果：{analysis}
                技术评估：{evaluations[0]}
                商业评估：{evaluations[1]}
                风险评估：{evaluations[2]}
                
                请生成综合报告。
                ''',
                is_stream=False
            )
            results["report"] = report
            
            return results
    
    # 使用工作流
    workflow = DocumentWorkflow(agent)
    results = await workflow.process("这是一份产品需求文档...")
    print(results["report"])
    """)

    print("\n工作流设计模式:")
    print("  1. 顺序执行：一步完成后执行下一步")
    print("  2. 并行执行：多个独立任务同时执行")
    print("  3. 条件分支：根据结果选择不同路径")
    print("  4. 循环迭代：重复执行直到满足条件")
    print("  5. 聚合合并：合并多个结果")


# ============================================================
# 示例 5: Agent协作
# ============================================================
def example_5_agent_collaboration():
    """
    多Agent协作完成复杂任务
    """
    print("\n" + "=" * 60)
    print("示例 5: Agent协作")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    
    class AgentTeam:
        '''Agent团队'''
        
        def __init__(self, base_agent: BaseAgent):
            # 产品经理Agent
            self.pm = base_agent.derive(
                name="产品经理",
                system_prompt='''你是产品经理，负责：
                1. 分析需求
                2. 定义功能
                3. 制定优先级'''
            )
            
            # 开发者Agent
            self.developer = base_agent.derive(
                name="开发者",
                system_prompt='''你是开发者，负责：
                1. 技术方案设计
                2. 代码实现
                3. 技术评审'''
            )
            
            # 测试Agent
            self.tester = base_agent.derive(
                name="测试工程师",
                system_prompt='''你是测试工程师，负责：
                1. 设计测试用例
                2. 执行测试
                3. 报告问题'''
            )
            
            # 协调者
            self.coordinator = base_agent.derive(
                name="协调者",
                system_prompt="你负责协调团队工作，整合各方意见..."
            )
        
        async def develop_feature(self, requirement: str) -> dict:
            '''开发新功能'''
            results = {}
            
            # PM分析需求
            print("\\n[产品经理] 分析需求...")
            pm_analysis = await self.pm.chat(
                f"分析这个需求：{requirement}"
            )
            results["pm_analysis"] = pm_analysis
            
            # 开发者设计方案
            print("\\n[开发者] 设计技术方案...")
            tech_design = await self.developer.chat(
                f"基于需求分析设计技术方案：{pm_analysis}"
            )
            results["tech_design"] = tech_design
            
            # 测试者设计测试用例
            print("\\n[测试] 设计测试用例...")
            test_cases = await self.tester.chat(
                f"为以下功能设计测试用例：{pm_analysis}"
            )
            results["test_cases"] = test_cases
            
            # 协调者整合
            print("\\n[协调者] 整合意见...")
            final_plan = await self.coordinator.chat(
                f'''整合以下信息生成最终计划：
                需求分析：{pm_analysis}
                技术方案：{tech_design}
                测试用例：{test_cases}'''
            )
            results["final_plan"] = final_plan
            
            return results
    
    # 使用团队
    team = AgentTeam(base_agent)
    results = await team.develop_feature("用户登录功能")
    """)

    print("\n协作模式:")
    print("  1. 流水线模式：A -> B -> C")
    print("  2. 讨论模式：A <-> B <-> C")
    print("  3. 评审模式：A提议，B/C评审")
    print("  4. 投票模式：多Agent投票决策")
    print("  5. 层级模式：管理者协调工作者")


# ============================================================
# 示例 6: 动态Prompt生成
# ============================================================
def example_6_dynamic_prompts():
    """
    根据上下文动态生成Prompt
    """
    print("\n" + "=" * 60)
    print("示例 6: 动态Prompt生成")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    from alphora.prompter import BasePrompt
    
    class DynamicPromptBuilder:
        '''动态Prompt构建器'''
        
        def __init__(self, agent: BaseAgent):
            self.agent = agent
            
            # 基础模板
            self.base_templates = {
                "greeting": "欢迎用户，介绍自己",
                "analysis": "分析用户提供的内容",
                "summary": "总结对话内容",
                "suggestion": "提供建议"
            }
            
            # 角色模板
            self.role_templates = {
                "assistant": "你是一个友好的助手",
                "expert": "你是领域专家",
                "teacher": "你是耐心的老师",
                "advisor": "你是专业顾问"
            }
        
        def build_prompt(
            self,
            task: str,
            role: str = "assistant",
            context: dict = None,
            constraints: list = None
        ) -> BasePrompt:
            '''构建动态Prompt'''
            
            # 组合系统提示
            system_parts = []
            
            # 角色定义
            if role in self.role_templates:
                system_parts.append(self.role_templates[role])
            
            # 任务描述
            if task in self.base_templates:
                system_parts.append(f"你的任务是：{self.base_templates[task]}")
            
            # 上下文信息
            if context:
                context_str = "\\n".join([
                    f"- {k}: {v}" for k, v in context.items()
                ])
                system_parts.append(f"上下文信息：\\n{context_str}")
            
            # 约束条件
            if constraints:
                constraints_str = "\\n".join([f"- {c}" for c in constraints])
                system_parts.append(f"请遵守以下约束：\\n{constraints_str}")
            
            system_prompt = "\\n\\n".join(system_parts)
            
            return self.agent.create_prompt(
                system_prompt=system_prompt
            )
        
        async def execute_dynamic(
            self,
            query: str,
            task: str,
            role: str = "assistant",
            **kwargs
        ) -> str:
            '''执行动态Prompt'''
            prompt = self.build_prompt(task, role, **kwargs)
            return await prompt.acall(query=query, is_stream=False)
    
    # 使用
    builder = DynamicPromptBuilder(agent)
    
    # 动态生成分析Prompt
    response = await builder.execute_dynamic(
        query="分析这段代码",
        task="analysis",
        role="expert",
        context={"language": "Python", "purpose": "代码审查"},
        constraints=["关注安全问题", "检查性能"]
    )
    """)


# ============================================================
# 示例 7: 高级记忆策略
# ============================================================
def example_7_advanced_memory():
    """
    高级记忆管理策略
    """
    print("\n" + "=" * 60)
    print("示例 7: 高级记忆策略")
    print("=" * 60)

    print("""
    from alphora.memory import MemoryManager, MemoryType
    from alphora.agent import BaseAgent
    
    class SmartMemoryAgent:
        '''具有智能记忆管理的Agent'''
        
        def __init__(self, agent: BaseAgent):
            self.agent = agent
            
            # 短期记忆（当前会话）
            self.short_term = MemoryManager(
                decay_strategy="exponential",
                storage_type="memory"
            )
            
            # 长期记忆（重要信息）
            self.long_term = MemoryManager(
                decay_strategy="log",
                storage_type="sqlite",
                storage_path="./long_term.db"
            )
            
            # 工作记忆（任务相关）
            self.working = MemoryManager(
                storage_type="memory"
            )
            
            # 重要性评估Prompt
            self.importance_evaluator = agent.create_prompt(
                system_prompt='''评估消息的重要性（0-1）。
                考虑因素：
                - 是否包含用户个人信息
                - 是否是重要决策
                - 是否需要长期记住
                
                只返回数字。'''
            )
        
        async def process_message(
            self,
            user_id: str,
            message: str,
            response: str
        ):
            '''处理消息并管理记忆'''
            
            # 添加到短期记忆
            self.short_term.add_memory(
                "user", message,
                memory_id=user_id,
                memory_type=MemoryType.SHORT_TERM
            )
            self.short_term.add_memory(
                "assistant", response,
                memory_id=user_id,
                memory_type=MemoryType.SHORT_TERM
            )
            
            # 评估重要性
            importance = await self._evaluate_importance(message)
            
            # 如果重要，添加到长期记忆
            if importance > 0.7:
                self.long_term.add_memory(
                    "user", message,
                    memory_id=user_id,
                    importance=importance,
                    memory_type=MemoryType.LONG_TERM
                )
            
            # 定期压缩短期记忆
            if len(self.short_term.get_memories(user_id)) > 20:
                await self._compress_memories(user_id)
        
        async def _evaluate_importance(self, message: str) -> float:
            '''评估消息重要性'''
            result = await self.importance_evaluator.acall(
                query=message,
                is_stream=False
            )
            try:
                return float(result.strip())
            except:
                return 0.5
        
        async def _compress_memories(self, user_id: str):
            '''压缩记忆'''
            # 获取短期记忆
            memories = self.short_term.get_memories(user_id)
            
            # 使用LLM生成摘要
            summary = await self.agent.create_prompt(
                system_prompt="总结以下对话的关键信息"
            ).acall(
                query=str(memories),
                is_stream=False
            )
            
            # 清除旧记忆，保存摘要
            self.short_term.clear_memory(user_id)
            self.short_term.add_memory(
                "system",
                f"[历史摘要] {summary}",
                memory_id=user_id,
                memory_type=MemoryType.EPISODIC
            )
        
        def get_relevant_context(self, user_id: str, query: str) -> str:
            '''获取相关上下文'''
            # 从长期记忆搜索相关内容
            long_term_relevant = self.long_term.search(
                query, memory_id=user_id, top_k=3
            )
            
            # 获取短期记忆
            short_term_history = self.short_term.build_history(
                memory_id=user_id,
                max_round=5,
                format="text"
            )
            
            return f'''
            [长期记忆]
            {[m.memory.get_content_text() for m in long_term_relevant]}
            
            [近期对话]
            {short_term_history}
            '''
    """)


# ============================================================
# 示例 8: 生产环境最佳实践
# ============================================================
def example_8_production_practices():
    """
    生产环境部署的最佳实践
    """
    print("\n" + "=" * 60)
    print("示例 8: 生产环境最佳实践")
    print("=" * 60)

    print("""
    # ===== 配置管理 =====
    
    from pydantic import BaseSettings
    
    class Settings(BaseSettings):
        '''应用配置'''
        # LLM配置
        llm_api_key: str
        llm_base_url: str
        default_llm: str = "gpt-4"
        
        # 数据库配置
        db_path: str = "./data/production.db"
        
        # 服务配置
        host: str = "0.0.0.0"
        port: int = 8000
        workers: int = 4
        
        # 安全配置
        api_keys: list = []
        rate_limit: int = 100
        
        class Config:
            env_file = ".env"
    
    settings = Settings()
    
    # ===== 日志配置 =====
    
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # ===== 错误处理 =====
    
    class AgentError(Exception):
        '''Agent错误基类'''
        pass
    
    class LLMError(AgentError):
        '''LLM调用错误'''
        pass
    
    class ToolError(AgentError):
        '''工具执行错误'''
        pass
    
    async def safe_execute(func, *args, **kwargs):
        '''安全执行'''
        try:
            return await func(*args, **kwargs)
        except LLMError as e:
            logger.error(f"LLM错误: {e}")
            # 重试逻辑
            return await retry_with_backoff(func, *args, **kwargs)
        except ToolError as e:
            logger.error(f"工具错误: {e}")
            raise
        except Exception as e:
            logger.exception(f"未知错误: {e}")
            raise
    
    # ===== 监控和指标 =====
    
    from prometheus_client import Counter, Histogram
    
    REQUEST_COUNT = Counter(
        'agent_requests_total',
        'Total requests',
        ['endpoint', 'status']
    )
    
    RESPONSE_TIME = Histogram(
        'agent_response_seconds',
        'Response time',
        ['endpoint']
    )
    
    # ===== 缓存 =====
    
    from functools import lru_cache
    import hashlib
    
    class ResponseCache:
        def __init__(self, max_size: int = 1000):
            self.cache = {}
            self.max_size = max_size
        
        def get_key(self, query: str, context: dict) -> str:
            content = f"{query}:{json.dumps(context, sort_keys=True)}"
            return hashlib.md5(content.encode()).hexdigest()
        
        def get(self, key: str):
            return self.cache.get(key)
        
        def set(self, key: str, value: str):
            if len(self.cache) >= self.max_size:
                # 简单LRU
                oldest = next(iter(self.cache))
                del self.cache[oldest]
            self.cache[key] = value
    
    # ===== 健康检查 =====
    
    async def health_check():
        '''健康检查'''
        checks = {
            "llm": await check_llm_connection(),
            "database": await check_database_connection(),
            "memory": check_memory_usage(),
        }
        
        healthy = all(checks.values())
        return {"status": "healthy" if healthy else "unhealthy", "checks": checks}
    """)

    print("\n生产环境检查清单:")
    print("  ✓ 配置外部化（环境变量/.env）")
    print("  ✓ 完善的日志记录")
    print("  ✓ 错误处理和重试机制")
    print("  ✓ 监控指标（Prometheus）")
    print("  ✓ 健康检查端点")
    print("  ✓ 响应缓存")
    print("  ✓ 速率限制")
    print("  ✓ 认证授权")
    print("  ✓ 数据持久化")
    print("  ✓ 优雅关闭")


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Advanced Examples - 高级示例")
    print("=" * 60)

    example_1_custom_agent()
    example_2_agent_derivation()
    example_3_component_integration()
    example_4_complex_workflow()
    example_5_agent_collaboration()
    example_6_dynamic_prompts()
    example_7_advanced_memory()
    example_8_production_practices()

    print("\n" + "=" * 60)
    print("所有高级示例完成！")
    print("=" * 60)
    print("\n这些示例展示了Alphora的高级用法，")
    print("可以根据实际需求组合使用。")


if __name__ == "__main__":
    main()