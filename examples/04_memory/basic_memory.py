"""
Alphora Memory Component - 基础记忆管理示例

本文件演示 MemoryManager 的核心功能：
1. 创建记忆管理器
2. 添加记忆（对话历史）
3. 构建历史记录
4. 记忆ID隔离
5. 记忆统计信息

运行前请确保已安装 alphora 包并配置好环境变量
"""

import asyncio
from alphora.memory import MemoryManager, MemoryType


# ============================================================
# 示例 1: 创建记忆管理器
# ============================================================
def example_1_create_memory_manager():
    """
    创建 MemoryManager 实例

    MemoryManager 支持多种存储后端：
    - memory: 内存存储（默认，程序重启后丢失）
    - json: JSON 文件存储
    - sqlite: SQLite 数据库存储（推荐生产环境）
    """
    print("=" * 60)
    print("示例 1: 创建记忆管理器")
    print("=" * 60)

    # 方式1：默认内存存储
    memory1 = MemoryManager()
    print(f"内存存储: {memory1}")

    # 方式2：JSON 文件存储
    memory2 = MemoryManager(
        storage_path="./data/memory.json",
        storage_type="json"
    )
    print(f"JSON存储: {memory2}")

    # 方式3：SQLite 数据库存储（推荐）
    memory3 = MemoryManager(
        storage_path="./data/memory.db",
        storage_type="sqlite"
    )
    print(f"SQLite存储: {memory3}")

    # 方式4：带配置参数
    memory4 = MemoryManager(
        storage_type="memory",
        decay_strategy="log",           # 衰减策略：log, linear, exponential
        retrieval_strategy="hybrid",    # 检索策略：keyword, fuzzy, hybrid
        auto_save=True,                 # 自动保存
        auto_extract_tags=True          # 自动提取标签
    )
    print(f"带配置的记忆管理器: {memory4}")

    return memory1


# ============================================================
# 示例 2: 添加记忆（对话历史）
# ============================================================
def example_2_add_memory():
    """
    向 MemoryManager 添加对话记忆

    记忆按 memory_id 分组，相同 memory_id 的记忆属于同一会话
    """
    print("\n" + "=" * 60)
    print("示例 2: 添加记忆")
    print("=" * 60)

    memory = MemoryManager()

    # 添加用户消息
    memory.add_memory(
        role="user",
        content="你好，我想学习Python",
        memory_id="session_001"
    )

    # 添加助手回复
    memory.add_memory(
        role="assistant",
        content="好的！Python是一门非常适合初学者的编程语言。你有什么编程基础吗？",
        memory_id="session_001"
    )

    # 继续对话
    memory.add_memory(
        role="user",
        content="我有一点Java基础",
        memory_id="session_001"
    )

    memory.add_memory(
        role="assistant",
        content="太好了！有Java基础会让学习Python更容易。Python的语法更简洁，你会发现很多概念是相通的。",
        memory_id="session_001"
    )

    # 查看记忆数量
    memories = memory.get_memories("session_001")
    print(f"会话 session_001 共有 {len(memories)} 条记忆")

    # 添加带元数据的记忆
    memory.add_memory(
        role="user",
        content="请推荐一些Python学习资源",
        memory_id="session_001",
        importance=0.8,                          # 重要性（0-1）
        tags=["学习", "资源", "Python"],         # 标签
        metadata={"source": "user_request"},    # 自定义元数据
        memory_type=MemoryType.SHORT_TERM       # 记忆类型
    )

    print("添加了带元数据的记忆")

    return memory


# ============================================================
# 示例 3: 构建历史记录
# ============================================================
def example_3_build_history():
    """
    从记忆中构建对话历史

    支持两种格式：
    - text: 文本格式，适合展示
    - messages: 消息列表格式，适合发送给 LLM
    """
    print("\n" + "=" * 60)
    print("示例 3: 构建历史记录")
    print("=" * 60)

    memory = MemoryManager()

    # 添加一些对话
    conversations = [
        ("user", "什么是机器学习？"),
        ("assistant", "机器学习是人工智能的一个分支，让计算机能够从数据中学习并做出决策。"),
        ("user", "有哪些常见的机器学习算法？"),
        ("assistant", "常见的算法包括：线性回归、决策树、随机森林、支持向量机、神经网络等。"),
        ("user", "神经网络和深度学习有什么关系？"),
        ("assistant", "深度学习是神经网络的一种，特指具有多个隐藏层的神经网络。"),
    ]

    for role, content in conversations:
        memory.add_memory(role=role, content=content, memory_id="ml_chat")

    # 构建文本格式历史（带时间戳）
    text_history = memory.build_history(
        memory_id="ml_chat",
        max_round=5,                 # 最大轮数
        format="text",               # 输出格式
        include_timestamp=True       # 包含时间戳
    )
    print("文本格式（带时间戳）：")
    print(text_history[:500] + "..." if len(text_history) > 500 else text_history)

    # 构建文本格式历史（不带时间戳）
    text_history_no_ts = memory.build_history(
        memory_id="ml_chat",
        max_round=5,
        format="text",
        include_timestamp=False
    )
    print("\n文本格式（无时间戳）：")
    print(text_history_no_ts)

    # 构建消息列表格式（用于 LLM）
    messages_history = memory.build_history(
        memory_id="ml_chat",
        max_round=3,                 # 只取最近3轮
        format="messages"
    )
    print("\n消息列表格式（最近3轮）：")
    for msg in messages_history:
        print(f"  {msg['role']}: {msg['content'][:50]}...")

    return memory


# ============================================================
# 示例 4: 记忆ID隔离（多会话管理）
# ============================================================
def example_4_memory_isolation():
    """
    不同 memory_id 的记忆相互隔离

    适用于：
    - 多用户系统：每个用户一个 memory_id
    - 多会话场景：每个对话一个 memory_id
    """
    print("\n" + "=" * 60)
    print("示例 4: 记忆ID隔离")
    print("=" * 60)

    memory = MemoryManager()

    # 用户A的对话
    memory.add_memory("user", "我想学习数据分析", memory_id="user_A")
    memory.add_memory("assistant", "数据分析是个很好的方向！", memory_id="user_A")

    # 用户B的对话
    memory.add_memory("user", "如何做Web开发？", memory_id="user_B")
    memory.add_memory("assistant", "Web开发需要学习前端和后端技术。", memory_id="user_B")

    # 用户C的对话
    memory.add_memory("user", "推荐一些AI课程", memory_id="user_C")
    memory.add_memory("assistant", "推荐Coursera的Machine Learning课程。", memory_id="user_C")

    # 列出所有会话
    all_sessions = memory.list_memory_ids()
    print(f"所有会话: {all_sessions}")

    # 检查各会话记忆数量
    for session_id in all_sessions:
        memories = memory.get_memories(session_id)
        print(f"  {session_id}: {len(memories)} 条记忆")

    # 获取特定会话的历史（互不影响）
    print("\n用户A的历史：")
    print(memory.build_history("user_A", format="text", include_timestamp=False))

    print("\n用户B的历史：")
    print(memory.build_history("user_B", format="text", include_timestamp=False))

    # 检查会话是否存在
    print(f"\nuser_A 存在: {memory.has_memory('user_A')}")
    print(f"user_X 存在: {memory.has_memory('user_X')}")

    return memory


# ============================================================
# 示例 5: 记忆统计信息
# ============================================================
def example_5_memory_stats():
    """
    获取记忆系统的统计信息

    包括：记忆数量、类型分布、时间范围等
    """
    print("\n" + "=" * 60)
    print("示例 5: 记忆统计信息")
    print("=" * 60)

    memory = MemoryManager()

    # 添加一些测试数据
    for i in range(10):
        memory.add_memory("user", f"用户消息 {i}", memory_id="stats_test")
        memory.add_memory("assistant", f"助手回复 {i}", memory_id="stats_test")

    # 获取特定会话统计
    session_stats = memory.stats("stats_test")
    print("会话统计信息:")
    print(f"  记忆数量: {session_stats['count']}")
    print(f"  对话轮数: {session_stats['turns']}")
    print(f"  平均分数: {session_stats['avg_score']:.2f}")
    print(f"  平均重要性: {session_stats['avg_importance']:.2f}")
    print(f"  类型分布: {session_stats['types']}")

    # 获取会话摘要
    summary = memory.get_session_summary("stats_test")
    print("\n会话摘要:")
    print(f"  存在: {summary['exists']}")
    print(f"  轮数: {summary['rounds']}")
    print(f"  总消息数: {summary['total_messages']}")
    print(f"  用户消息数: {summary['user_messages']}")
    print(f"  助手消息数: {summary['assistant_messages']}")

    # 获取全局统计
    global_stats = memory.stats()
    print("\n全局统计:")
    print(f"  总记忆数: {global_stats['total_memories']}")
    print(f"  会话数: {len(global_stats['memory_ids'])}")
    print(f"  衰减策略: {global_stats['decay_strategy']}")
    print(f"  检索策略: {global_stats['retrieval_strategy']}")

    return memory


# ============================================================
# 示例 6: 清空和遗忘记忆
# ============================================================
def example_6_clear_and_forget():
    """
    清空记忆和智能遗忘

    - clear_memory: 完全清空指定会话
    - forget: 智能遗忘低分记忆
    """
    print("\n" + "=" * 60)
    print("示例 6: 清空和遗忘记忆")
    print("=" * 60)

    memory = MemoryManager()

    # 添加测试数据
    for i in range(20):
        importance = 0.9 if i % 5 == 0 else 0.3  # 每5条有一条重要
        memory.add_memory(
            "user",
            f"消息 {i}",
            memory_id="forget_test",
            importance=importance
        )

    print(f"初始记忆数: {len(memory.get_memories('forget_test'))}")

    # 智能遗忘：保留高分和重要记忆
    forgotten_count = memory.forget(
        memory_id="forget_test",
        threshold=0.3,              # 分数低于此值的记忆将被遗忘
        keep_important=True,        # 保留重要记忆
        importance_threshold=0.7    # 重要性高于此值的记忆保留
    )
    print(f"遗忘了 {forgotten_count} 条低分记忆")
    print(f"剩余记忆数: {len(memory.get_memories('forget_test'))}")

    # 清空特定会话
    memory.add_memory("user", "测试", memory_id="to_clear")
    print(f"\nto_clear 会话存在: {memory.has_memory('to_clear')}")

    memory.clear_memory("to_clear")
    print(f"清空后 to_clear 存在: {memory.has_memory('to_clear')}")

    return memory


# ============================================================
# 示例 7: 获取高分记忆
# ============================================================
def example_7_top_memories():
    """
    获取评分最高的记忆

    支持多种排序方式：
    - score: 按分数排序
    - importance: 按重要性排序
    - composite: 综合评分
    - time: 按时间排序
    """
    print("\n" + "=" * 60)
    print("示例 7: 获取高分记忆")
    print("=" * 60)

    memory = MemoryManager()

    # 添加不同重要性的记忆
    topics = [
        ("我的目标是成为AI工程师", 0.9),
        ("今天天气不错", 0.2),
        ("我对深度学习特别感兴趣", 0.8),
        ("刚才吃了午饭", 0.1),
        ("我有5年Python开发经验", 0.85),
        ("明天有个会议", 0.4),
    ]

    for content, importance in topics:
        memory.add_memory(
            "user",
            content,
            memory_id="top_test",
            importance=importance
        )

    # 按重要性获取前3条
    top_by_importance = memory.get_top_memories(
        "top_test",
        top_n=3,
        sort_by="importance"
    )
    print("按重要性排序（前3条）：")
    for m in top_by_importance:
        print(f"  [{m.importance:.1f}] {m.get_content_text()}")

    # 按综合评分获取
    top_by_composite = memory.get_top_memories(
        "top_test",
        top_n=3,
        sort_by="composite"
    )
    print("\n按综合评分排序（前3条）：")
    for m in top_by_composite:
        print(f"  [{m.get_composite_score():.2f}] {m.get_content_text()}")

    return memory


# ============================================================
# 示例 8: 记忆判空和列表
# ============================================================
def example_8_memory_utils():
    """
    记忆系统的实用工具方法
    """
    print("\n" + "=" * 60)
    print("示例 8: 实用工具方法")
    print("=" * 60)

    memory = MemoryManager()

    # 检查空状态
    print(f"新会话是否为空: {memory.is_empty('new_session')}")

    memory.add_memory("user", "测试消息", memory_id="new_session")
    print(f"添加消息后是否为空: {memory.is_empty('new_session')}")

    # 添加多个会话
    memory.add_memory("user", "消息1", memory_id="session_1")
    memory.add_memory("user", "消息2", memory_id="session_2")
    memory.add_memory("user", "消息3", memory_id="session_3")

    # 列出所有会话
    all_ids = memory.list_memory_ids()
    print(f"\n所有会话ID: {all_ids}")

    # 检查特定会话是否存在
    print(f"\nsession_1 存在: {memory.has_memory('session_1')}")
    print(f"session_x 存在: {memory.has_memory('session_x')}")

    # 获取所有记忆
    all_memories = memory.get_memories("session_1")
    print(f"\nsession_1 的记忆: {len(all_memories)} 条")

    return memory


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Memory 基础示例")
    print("=" * 60)

    example_1_create_memory_manager()
    example_2_add_memory()
    example_3_build_history()
    example_4_memory_isolation()
    example_5_memory_stats()
    example_6_clear_and_forget()
    example_7_top_memories()
    example_8_memory_utils()

    print("\n" + "=" * 60)
    print("所有基础记忆示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()