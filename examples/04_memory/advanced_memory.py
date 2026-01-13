"""
Alphora Memory Component - 高级记忆功能示例

本文件演示 MemoryManager 的高级功能：
1. 记忆搜索和检索
2. 记忆反思（需要LLM）
3. 持久化存储
4. 衰减策略
5. 记忆导出/导入

运行前请确保已安装 alphora 包并配置好环境变量
"""

import asyncio
import os
from alphora.memory import (
    MemoryManager,
    MemoryType,
    # 衰减策略
    LinearDecay,
    ExponentialDecay,
    LogarithmicDecay,
    NoDecay,
    get_decay_strategy,
    # 检索策略
    KeywordRetrieval,
    FuzzyRetrieval,
    HybridRetrieval,
    get_retrieval_strategy,
)
from alphora.models import OpenAILike


# ============================================================
# 示例 1: 记忆搜索
# ============================================================
def example_1_memory_search():
    """
    在记忆中搜索相关内容

    支持多种检索策略：
    - keyword: 关键词匹配
    - fuzzy: 模糊匹配
    - hybrid: 混合策略（推荐）
    """
    print("=" * 60)
    print("示例 1: 记忆搜索")
    print("=" * 60)

    memory = MemoryManager(retrieval_strategy="hybrid")

    # 添加一些对话记忆
    conversations = [
        ("user", "Python和Java哪个更适合初学者？"),
        ("assistant", "Python语法更简洁，对初学者更友好。"),
        ("user", "我想学习机器学习，需要什么基础？"),
        ("assistant", "建议先掌握Python编程和数学基础，包括线性代数和概率论。"),
        ("user", "深度学习框架有哪些推荐？"),
        ("assistant", "推荐PyTorch和TensorFlow，它们都有丰富的社区资源。"),
        ("user", "如何部署机器学习模型？"),
        ("assistant", "可以使用Flask/FastAPI做API，或者使用Docker容器化部署。"),
        ("user", "数据预处理有哪些常用库？"),
        ("assistant", "Pandas用于数据处理，NumPy用于数值计算，Scikit-learn有预处理工具。"),
    ]

    for role, content in conversations:
        memory.add_memory(role, content, memory_id="tech_chat")

    # 搜索与"Python"相关的记忆
    print("\n搜索 'Python'：")
    results = memory.search("Python", memory_id="tech_chat", top_k=3)
    for result in results:
        print(f"  [{result.score:.2f}] {result.memory.get_content_text()[:60]}...")

    # 搜索与"机器学习"相关的记忆
    print("\n搜索 '机器学习'：")
    results = memory.search("机器学习", memory_id="tech_chat", top_k=3)
    for result in results:
        print(f"  [{result.score:.2f}] {result.memory.get_content_text()[:60]}...")

    # 使用不同的检索策略
    print("\n使用关键词策略搜索 '部署'：")
    results = memory.search("部署", memory_id="tech_chat", top_k=2, strategy="keyword")
    for result in results:
        print(f"  [{result.score:.2f}] {result.memory.get_content_text()[:60]}...")

    return memory


# ============================================================
# 示例 2: 基于查询构建历史
# ============================================================
def example_2_query_based_history():
    """
    根据查询内容构建相关的历史记录

    这对于长对话特别有用，可以只选取与当前问题相关的历史
    """
    print("\n" + "=" * 60)
    print("示例 2: 基于查询构建历史")
    print("=" * 60)

    memory = MemoryManager()

    # 添加多主题的对话
    topics = [
        # 编程话题
        ("user", "如何在Python中读取文件？"),
        ("assistant", "可以使用 open() 函数或 pathlib 模块。"),
        # 数学话题
        ("user", "什么是矩阵乘法？"),
        ("assistant", "矩阵乘法是线性代数中的基本运算..."),
        # 编程话题
        ("user", "Python的装饰器是什么？"),
        ("assistant", "装饰器是一种修改函数行为的高级特性。"),
        # 生活话题
        ("user", "推荐一些好吃的餐厅"),
        ("assistant", "这取决于你喜欢什么口味的菜..."),
        # 编程话题
        ("user", "异步编程怎么实现？"),
        ("assistant", "Python使用async/await语法实现异步编程。"),
    ]

    for role, content in topics:
        memory.add_memory(role, content, memory_id="mixed_chat")

    # 基于查询构建历史 - 只获取相关内容
    print("\n查询 'Python编程' 相关的历史：")
    history = memory.build_history(
        memory_id="mixed_chat",
        query="Python编程",           # 根据查询筛选相关记忆
        max_round=3,
        format="text",
        include_timestamp=False
    )
    print(history)

    # 另一个查询
    print("\n查询 '数学' 相关的历史：")
    history = memory.build_history(
        memory_id="mixed_chat",
        query="数学",
        max_round=3,
        format="text",
        include_timestamp=False
    )
    print(history)

    return memory


# ============================================================
# 示例 3: 衰减策略
# ============================================================
def example_3_decay_strategies():
    """
    不同的记忆衰减策略

    衰减策略决定了旧记忆如何逐渐"遗忘"：
    - NoDecay: 不衰减
    - LinearDecay: 线性衰减
    - ExponentialDecay: 指数衰减
    - LogarithmicDecay: 对数衰减（默认）
    """
    print("\n" + "=" * 60)
    print("示例 3: 衰减策略")
    print("=" * 60)

    # 使用对数衰减（默认，推荐）
    memory_log = MemoryManager(decay_strategy="log")

    # 使用线性衰减
    memory_linear = MemoryManager(decay_strategy="linear")

    # 使用指数衰减
    memory_exp = MemoryManager(decay_strategy="exponential")

    # 不衰减
    memory_no = MemoryManager(decay_strategy=NoDecay())

    # 自定义衰减策略
    custom_decay = ExponentialDecay(base_factor=0.95, min_score=0.1)
    memory_custom = MemoryManager(decay_strategy=custom_decay)

    print("可用的衰减策略：")
    print("  - log (LogarithmicDecay): 对数衰减，推荐使用")
    print("  - linear (LinearDecay): 线性衰减")
    print("  - exponential (ExponentialDecay): 指数衰减")
    print("  - NoDecay: 不衰减")

    # 演示衰减效果
    print("\n演示衰减效果（添加10条消息后查看分数）：")
    for i in range(10):
        memory_log.add_memory("user", f"消息{i}", memory_id="test")

    memories = memory_log.get_memories("test")
    print("各记忆的分数：")
    for i, m in enumerate(memories):
        print(f"  消息{i}: score={m.score:.3f}")

    return memory_log


# ============================================================
# 示例 4: 检索策略
# ============================================================
def example_4_retrieval_strategies():
    """
    不同的记忆检索策略

    - keyword: 关键词精确匹配
    - fuzzy: 模糊匹配（容错性好）
    - hybrid: 混合策略（推荐）
    - regex: 正则表达式匹配
    - tag: 标签匹配
    """
    print("\n" + "=" * 60)
    print("示例 4: 检索策略")
    print("=" * 60)

    memory = MemoryManager()

    # 添加带标签的记忆
    memory.add_memory(
        "user",
        "Python是一门解释型编程语言",
        memory_id="test",
        tags=["编程", "Python", "基础"]
    )
    memory.add_memory(
        "user",
        "机器学习需要大量数据",
        memory_id="test",
        tags=["AI", "机器学习", "数据"]
    )
    memory.add_memory(
        "user",
        "深度学习是机器学习的子集",
        memory_id="test",
        tags=["AI", "深度学习", "神经网络"]
    )

    # 关键词检索
    print("\n关键词检索 'Python'：")
    results = memory.search("Python", memory_id="test", strategy="keyword")
    for r in results:
        print(f"  {r.memory.get_content_text()}")

    # 模糊检索（可以容忍拼写错误）
    print("\n模糊检索 'machne lerning'（拼写错误）：")
    results = memory.search("machne lerning", memory_id="test", strategy="fuzzy")
    for r in results:
        print(f"  [{r.score:.2f}] {r.memory.get_content_text()}")

    # 混合检索
    print("\n混合检索 '学习'：")
    results = memory.search("学习", memory_id="test", strategy="hybrid")
    for r in results:
        print(f"  [{r.score:.2f}] {r.memory.get_content_text()}")

    return memory


# ============================================================
# 示例 5: 持久化存储
# ============================================================
def example_5_persistence():
    """
    记忆的持久化存储

    支持：
    - JSON文件存储
    - SQLite数据库存储（推荐生产环境）
    - 导出/导入
    """
    print("\n" + "=" * 60)
    print("示例 5: 持久化存储")
    print("=" * 60)

    import tempfile
    import os

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()

    # JSON存储示例
    json_path = os.path.join(temp_dir, "memory.json")
    memory_json = MemoryManager(
        storage_path=json_path,
        storage_type="json"
    )

    # 添加数据
    memory_json.add_memory("user", "这是持久化测试", memory_id="persist_test")
    memory_json.add_memory("assistant", "收到，已保存到JSON", memory_id="persist_test")

    # 手动保存
    memory_json.save()
    print(f"JSON存储路径: {json_path}")
    print(f"文件是否存在: {os.path.exists(json_path)}")

    # SQLite存储示例
    sqlite_path = os.path.join(temp_dir, "memory.db")
    memory_sqlite = MemoryManager(
        storage_path=sqlite_path,
        storage_type="sqlite"
    )

    memory_sqlite.add_memory("user", "这是SQLite测试", memory_id="sqlite_test")
    memory_sqlite.save()
    print(f"\nSQLite存储路径: {sqlite_path}")
    print(f"文件是否存在: {os.path.exists(sqlite_path)}")

    # 导出到文件
    dump_path = os.path.join(temp_dir, "memory_dump.pkl")
    memory_json.dump(dump_path)
    print(f"\n导出文件路径: {dump_path}")

    # 从导出文件加载
    loaded_memory = MemoryManager.load_from_dump(dump_path)
    print(f"加载后的记忆数: {len(loaded_memory.get_memories('persist_test'))}")

    # 清理临时文件
    import shutil
    shutil.rmtree(temp_dir)
    print("\n临时文件已清理")

    return memory_json


# ============================================================
# 示例 6: LLM反思功能（需要配置LLM）
# ============================================================
async def example_6_reflection():
    """
    使用LLM对记忆进行反思和总结

    需要配置LLM才能使用此功能
    """
    print("\n" + "=" * 60)
    print("示例 6: LLM反思功能")
    print("=" * 60)

    # 检查是否配置了LLM
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("未配置 LLM_API_KEY，跳过反思示例")
        print("要使用反思功能，请设置以下环境变量：")
        print("  - LLM_API_KEY")
        print("  - LLM_BASE_URL")
        print("  - DEFAULT_LLM")
        return None

    # 创建LLM实例
    llm = OpenAILike(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM", "gpt-3.5-turbo")
    )

    # 创建带LLM的记忆管理器
    memory = MemoryManager(
        llm=llm,
        auto_reflect=False  # 关闭自动反思，手动触发
    )

    # 添加一些对话
    conversations = [
        ("user", "我叫张三，今年25岁"),
        ("assistant", "你好张三！很高兴认识你。"),
        ("user", "我在北京工作，是一名软件工程师"),
        ("assistant", "软件工程师是个很好的职业！北京的科技公司很多。"),
        ("user", "我想转型做AI方向"),
        ("assistant", "这是个不错的选择！你可以从机器学习基础开始学习。"),
        ("user", "我有Python和数据分析的经验"),
        ("assistant", "那太好了！这些都是学习AI的良好基础。"),
    ]

    for role, content in conversations:
        memory.add_memory(role, content, memory_id="reflect_test")

    # 触发反思
    print("正在进行记忆反思...")
    reflection = await memory.reflect(memory_id="reflect_test")

    if reflection:
        print(f"\n反思结果：")
        print(f"  摘要: {reflection.summary}")
        print(f"  关键信息: {reflection.key_insights}")
        print(f"  情感倾向: {reflection.sentiment}")

    # 生成摘要
    print("\n生成简短摘要...")
    summary = await memory.summarize(memory_id="reflect_test", style="brief")
    print(f"摘要: {summary}")

    # 提取关键信息
    print("\n提取关键信息...")
    key_info = await memory.extract_key_info(memory_id="reflect_test")
    print(f"关键信息: {key_info}")

    return memory


# ============================================================
# 示例 7: 记忆类型
# ============================================================
def example_7_memory_types():
    """
    不同类型的记忆

    - SHORT_TERM: 短期记忆（默认）
    - LONG_TERM: 长期记忆
    - WORKING: 工作记忆
    - EPISODIC: 情景记忆
    - REFLECTION: 反思记忆
    """
    print("\n" + "=" * 60)
    print("示例 7: 记忆类型")
    print("=" * 60)

    memory = MemoryManager()

    # 添加不同类型的记忆
    memory.add_memory(
        "user",
        "今天的会议很重要",
        memory_id="type_test",
        memory_type=MemoryType.SHORT_TERM
    )

    memory.add_memory(
        "user",
        "我的长期目标是成为技术专家",
        memory_id="type_test",
        memory_type=MemoryType.LONG_TERM
    )

    memory.add_memory(
        "assistant",
        "正在处理用户请求...",
        memory_id="type_test",
        memory_type=MemoryType.WORKING
    )

    memory.add_memory(
        "user",
        "上次我们讨论了Python基础",
        memory_id="type_test",
        memory_type=MemoryType.EPISODIC
    )

    # 查看类型分布
    stats = memory.stats("type_test")
    print("记忆类型分布：")
    for type_name, count in stats['types'].items():
        print(f"  {type_name}: {count}")

    # 构建历史时排除反思记忆
    history = memory.build_history(
        memory_id="type_test",
        format="text",
        include_reflections=False,  # 不包含反思记忆
        include_timestamp=False
    )
    print(f"\n历史记录（排除反思）：")
    print(history)

    return memory


# ============================================================
# 示例 8: 综合应用 - 智能对话助手
# ============================================================
def example_8_smart_assistant():
    """
    综合应用：构建具有记忆能力的智能对话系统
    """
    print("\n" + "=" * 60)
    print("示例 8: 综合应用 - 智能对话助手")
    print("=" * 60)

    class SmartAssistant:
        """具有记忆能力的智能助手"""

        def __init__(self, user_id: str):
            self.user_id = user_id
            self.memory = MemoryManager(
                decay_strategy="log",
                retrieval_strategy="hybrid"
            )

        def chat(self, user_input: str) -> str:
            """处理用户输入（模拟）"""
            # 保存用户输入
            self.memory.add_memory(
                "user",
                user_input,
                memory_id=self.user_id,
                importance=0.5
            )

            # 搜索相关历史
            relevant = self.memory.search(
                user_input,
                memory_id=self.user_id,
                top_k=3
            )

            # 模拟回复（实际应用中会调用LLM）
            response = f"[模拟回复] 收到您的消息：{user_input}"
            if relevant:
                response += f"\n（找到 {len(relevant)} 条相关历史记忆）"

            # 保存助手回复
            self.memory.add_memory(
                "assistant",
                response,
                memory_id=self.user_id
            )

            return response

        def get_context(self, query: str = None) -> str:
            """获取对话上下文"""
            return self.memory.build_history(
                memory_id=self.user_id,
                query=query,
                max_round=5,
                format="text",
                include_timestamp=False
            )

        def get_stats(self) -> dict:
            """获取会话统计"""
            return self.memory.get_session_summary(self.user_id)

    # 使用示例
    assistant = SmartAssistant(user_id="user_123")

    # 模拟对话
    messages = [
        "你好，我想学习Python",
        "我有一点C++基础",
        "推荐一些学习资源",
        "Python和C++的主要区别是什么？"
    ]

    for msg in messages:
        print(f"\n用户: {msg}")
        response = assistant.chat(msg)
        print(f"助手: {response}")

    # 查看上下文
    print("\n\n当前对话上下文：")
    print(assistant.get_context())

    # 查看统计
    print("\n会话统计：")
    stats = assistant.get_stats()
    print(f"  对话轮数: {stats['rounds']}")
    print(f"  总消息数: {stats['total_messages']}")

    return assistant


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Memory 高级功能示例")
    print("=" * 60)

    example_1_memory_search()
    example_2_query_based_history()
    example_3_decay_strategies()
    example_4_retrieval_strategies()
    example_5_persistence()

    # 反思功能需要异步运行
    # asyncio.run(example_6_reflection())
    print("\n" + "=" * 60)
    print("示例 6 (LLM反思) 需要配置LLM，请单独运行")
    print("=" * 60)

    example_7_memory_types()
    example_8_smart_assistant()

    print("\n" + "=" * 60)
    print("所有高级记忆示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()