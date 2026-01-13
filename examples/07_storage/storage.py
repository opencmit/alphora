"""
Alphora Storage Component - 存储系统示例

本文件演示各种存储后端的使用：
1. InMemoryStorage - 内存存储
2. JSONStorage - JSON文件存储
3. SQLiteStorage - SQLite数据库存储
4. 存储接口和通用操作
5. 数据序列化
6. 批量操作
7. 查询和过滤
8. 存储迁移

存储系统为Agent、Memory等组件提供持久化能力
"""

import os
import json
import tempfile
import shutil
from typing import Any, Dict, List, Optional
from datetime import datetime

from alphora.storage import (
    BaseStorage,
    InMemoryStorage,
    JSONStorage,
    SQLiteStorage,
    get_storage
)


# ============================================================
# 示例 1: InMemoryStorage - 内存存储
# ============================================================
def example_1_memory_storage():
    """
    InMemoryStorage: 内存存储

    特点：
    - 速度最快
    - 程序重启后数据丢失
    - 适合临时数据、测试场景
    """
    print("=" * 60)
    print("示例 1: InMemoryStorage - 内存存储")
    print("=" * 60)

    # 创建内存存储
    storage = InMemoryStorage()

    # 基本操作：设置值
    storage.set("name", "张三")
    storage.set("age", 25)
    storage.set("skills", ["Python", "Java", "Go"])
    storage.set("profile", {"city": "北京", "job": "工程师"})

    print("\n设置数据:")
    print(f"  name = {storage.get('name')}")
    print(f"  age = {storage.get('age')}")
    print(f"  skills = {storage.get('skills')}")
    print(f"  profile = {storage.get('profile')}")

    # 检查键是否存在
    print(f"\n'name' 存在: {storage.exists('name')}")
    print(f"'email' 存在: {storage.exists('email')}")

    # 获取所有键
    print(f"\n所有键: {storage.keys()}")

    # 删除键
    storage.delete("age")
    print(f"\n删除 'age' 后: {storage.keys()}")

    # 获取不存在的键（返回默认值）
    email = storage.get("email", default="未设置")
    print(f"email（带默认值）: {email}")

    # 清空存储
    storage.clear()
    print(f"\n清空后键数量: {len(storage.keys())}")

    return storage


# ============================================================
# 示例 2: JSONStorage - JSON文件存储
# ============================================================
def example_2_json_storage():
    """
    JSONStorage: JSON文件存储

    特点：
    - 数据持久化到JSON文件
    - 人类可读
    - 适合配置、小规模数据
    """
    print("\n" + "=" * 60)
    print("示例 2: JSONStorage - JSON文件存储")
    print("=" * 60)

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    json_path = os.path.join(temp_dir, "data.json")

    try:
        # 创建JSON存储
        storage = JSONStorage(path=json_path)

        # 存储数据
        storage.set("config", {
            "theme": "dark",
            "language": "zh-CN",
            "notifications": True
        })
        storage.set("user", {
            "id": "U001",
            "name": "李四",
            "created_at": datetime.now().isoformat()
        })
        storage.set("history", ["会话1", "会话2", "会话3"])

        # 保存到文件
        storage.save()

        print(f"\n数据已保存到: {json_path}")
        print(f"文件是否存在: {os.path.exists(json_path)}")

        # 查看文件内容
        with open(json_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        print(f"\n文件内容预览:")
        print(json.dumps(content, indent=2, ensure_ascii=False)[:300] + "...")

        # 重新加载
        storage2 = JSONStorage(path=json_path)
        storage2.load()

        print(f"\n重新加载后的数据:")
        print(f"  config = {storage2.get('config')}")
        print(f"  user.name = {storage2.get('user')['name']}")

        # 自动保存模式
        storage3 = JSONStorage(path=json_path, auto_save=True)
        storage3.set("auto_key", "自动保存的值")
        # auto_save=True 时，每次 set 都会自动保存

    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir)
        print("\n临时文件已清理")

    return storage


# ============================================================
# 示例 3: SQLiteStorage - SQLite数据库存储
# ============================================================
def example_3_sqlite_storage():
    """
    SQLiteStorage: SQLite数据库存储

    特点：
    - 数据持久化到SQLite数据库
    - 支持事务
    - 适合大规模数据、生产环境
    """
    print("\n" + "=" * 60)
    print("示例 3: SQLiteStorage - SQLite数据库存储")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "data.db")

    try:
        # 创建SQLite存储
        storage = SQLiteStorage(path=db_path)

        # 存储数据
        storage.set("session:001", {
            "user_id": "U001",
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！有什么可以帮你的？"}
            ],
            "created_at": datetime.now().isoformat()
        })

        storage.set("session:002", {
            "user_id": "U002",
            "messages": [
                {"role": "user", "content": "帮我写代码"}
            ],
            "created_at": datetime.now().isoformat()
        })

        # 存储不同类型的数据
        storage.set("counter", 100)
        storage.set("flag", True)
        storage.set("tags", ["AI", "Python", "机器学习"])

        print(f"\n数据已存储到: {db_path}")
        print(f"数据库大小: {os.path.getsize(db_path)} bytes")

        # 读取数据
        print(f"\n读取数据:")
        session = storage.get("session:001")
        print(f"  session:001 消息数: {len(session['messages'])}")
        print(f"  counter = {storage.get('counter')}")
        print(f"  flag = {storage.get('flag')}")

        # 列出所有键
        all_keys = storage.keys()
        print(f"\n所有键: {all_keys}")

        # 按前缀筛选键
        session_keys = [k for k in all_keys if k.startswith("session:")]
        print(f"session键: {session_keys}")

        # 事务操作（SQLite支持）
        print("\n事务操作示例:")
        print("  storage.begin_transaction()")
        print("  storage.set('key1', 'value1')")
        print("  storage.set('key2', 'value2')")
        print("  storage.commit()  # 或 storage.rollback()")

    finally:
        shutil.rmtree(temp_dir)
        print("\n临时文件已清理")

    return storage


# ============================================================
# 示例 4: 存储工厂函数
# ============================================================
def example_4_storage_factory():
    """
    get_storage: 存储工厂函数

    根据类型或路径自动创建合适的存储实例
    """
    print("\n" + "=" * 60)
    print("示例 4: 存储工厂函数")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        # 根据类型创建
        memory_storage = get_storage(storage_type="memory")
        print(f"memory类型: {type(memory_storage).__name__}")

        # 根据路径后缀自动识别
        json_path = os.path.join(temp_dir, "test.json")
        json_storage = get_storage(path=json_path)
        print(f".json后缀: {type(json_storage).__name__}")

        sqlite_path = os.path.join(temp_dir, "test.db")
        sqlite_storage = get_storage(path=sqlite_path)
        print(f".db后缀: {type(sqlite_storage).__name__}")

        # 显式指定类型
        storage = get_storage(
            storage_type="sqlite",
            path=os.path.join(temp_dir, "explicit.db")
        )
        print(f"显式指定sqlite: {type(storage).__name__}")

    finally:
        shutil.rmtree(temp_dir)

    return memory_storage


# ============================================================
# 示例 5: 数据序列化
# ============================================================
def example_5_serialization():
    """
    存储系统的数据序列化

    支持多种数据类型的自动序列化
    """
    print("\n" + "=" * 60)
    print("示例 5: 数据序列化")
    print("=" * 60)

    storage = InMemoryStorage()

    # 基本类型
    storage.set("string", "Hello World")
    storage.set("integer", 42)
    storage.set("float", 3.14159)
    storage.set("boolean", True)
    storage.set("none", None)

    # 复杂类型
    storage.set("list", [1, 2, 3, "four", 5.0])
    storage.set("dict", {"a": 1, "b": {"nested": True}})
    storage.set("tuple", (1, 2, 3))  # 会被转换为list

    # 日期时间（需要转换为字符串）
    storage.set("datetime", datetime.now().isoformat())

    print("\n存储的数据类型:")
    for key in storage.keys():
        value = storage.get(key)
        print(f"  {key}: {type(value).__name__} = {repr(value)[:50]}")

    # 自定义对象序列化
    print("\n自定义对象需要手动序列化:")
    print("  class User:")
    print("      def to_dict(self): return {...}")
    print("  storage.set('user', user.to_dict())")

    return storage


# ============================================================
# 示例 6: 批量操作
# ============================================================
def example_6_batch_operations():
    """
    批量读写操作

    提高大量数据操作的效率
    """
    print("\n" + "=" * 60)
    print("示例 6: 批量操作")
    print("=" * 60)

    storage = InMemoryStorage()

    # 批量设置
    batch_data = {
        f"item:{i}": {"id": i, "value": f"数据{i}"}
        for i in range(10)
    }

    storage.set_many(batch_data)
    print(f"批量设置 {len(batch_data)} 条数据")

    # 批量获取
    keys_to_get = ["item:0", "item:5", "item:9"]
    results = storage.get_many(keys_to_get)
    print(f"\n批量获取 {keys_to_get}:")
    for key, value in results.items():
        print(f"  {key} = {value}")

    # 批量删除
    keys_to_delete = ["item:1", "item:2", "item:3"]
    storage.delete_many(keys_to_delete)
    print(f"\n批量删除后剩余键数: {len(storage.keys())}")

    # 批量检查存在
    keys_to_check = ["item:0", "item:1", "item:5"]
    exists_results = storage.exists_many(keys_to_check)
    print(f"\n批量检查存在:")
    for key, exists in exists_results.items():
        print(f"  {key}: {exists}")

    return storage


# ============================================================
# 示例 7: 键的命名空间
# ============================================================
def example_7_key_namespaces():
    """
    使用命名空间组织键

    推荐使用冒号分隔的命名规范
    """
    print("\n" + "=" * 60)
    print("示例 7: 键的命名空间")
    print("=" * 60)

    storage = InMemoryStorage()

    # 用户数据
    storage.set("user:001:profile", {"name": "张三", "age": 25})
    storage.set("user:001:settings", {"theme": "dark"})
    storage.set("user:002:profile", {"name": "李四", "age": 30})
    storage.set("user:002:settings", {"theme": "light"})

    # 会话数据
    storage.set("session:abc123:messages", [])
    storage.set("session:abc123:metadata", {"created": "2024-01-01"})
    storage.set("session:def456:messages", [])

    # 配置数据
    storage.set("config:app:name", "MyApp")
    storage.set("config:app:version", "1.0.0")

    print("\n所有键:")
    for key in sorted(storage.keys()):
        print(f"  {key}")

    # 按命名空间筛选
    def get_by_prefix(storage, prefix):
        return {k: storage.get(k) for k in storage.keys() if k.startswith(prefix)}

    print("\n用户001的数据:")
    user_001_data = get_by_prefix(storage, "user:001:")
    for key, value in user_001_data.items():
        print(f"  {key}: {value}")

    print("\n所有会话:")
    sessions = get_by_prefix(storage, "session:")
    print(f"  共 {len(sessions)} 个键")

    # 删除命名空间下所有键
    def delete_by_prefix(storage, prefix):
        keys_to_delete = [k for k in storage.keys() if k.startswith(prefix)]
        storage.delete_many(keys_to_delete)
        return len(keys_to_delete)

    deleted = delete_by_prefix(storage, "session:")
    print(f"\n删除session命名空间: {deleted} 个键")
    print(f"剩余键: {storage.keys()}")

    return storage


# ============================================================
# 示例 8: 存储统计和元数据
# ============================================================
def example_8_storage_stats():
    """
    存储统计信息和元数据
    """
    print("\n" + "=" * 60)
    print("示例 8: 存储统计和元数据")
    print("=" * 60)

    storage = InMemoryStorage()

    # 添加一些数据
    for i in range(100):
        storage.set(f"item:{i}", {"index": i, "data": "x" * (i * 10)})

    # 基本统计
    print("\n存储统计:")
    print(f"  键数量: {len(storage.keys())}")
    print(f"  存储类型: {type(storage).__name__}")

    # 估算存储大小
    total_size = 0
    for key in storage.keys():
        value = storage.get(key)
        total_size += len(json.dumps(value))
    print(f"  估算数据大小: {total_size / 1024:.2f} KB")

    # 获取存储信息
    info = storage.info()
    print(f"\n存储信息:")
    for k, v in info.items():
        print(f"  {k}: {v}")

    return storage


# ============================================================
# 示例 9: 存储后端切换
# ============================================================
def example_9_backend_switching():
    """
    在不同存储后端之间切换和迁移
    """
    print("\n" + "=" * 60)
    print("示例 9: 存储后端切换")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        # 从内存存储开始
        memory_storage = InMemoryStorage()
        memory_storage.set("key1", "value1")
        memory_storage.set("key2", {"nested": "data"})
        memory_storage.set("key3", [1, 2, 3])

        print("内存存储中的数据:")
        for key in memory_storage.keys():
            print(f"  {key}: {memory_storage.get(key)}")

        # 迁移到JSON存储
        json_path = os.path.join(temp_dir, "migrated.json")
        json_storage = JSONStorage(path=json_path)

        # 复制所有数据
        for key in memory_storage.keys():
            json_storage.set(key, memory_storage.get(key))
        json_storage.save()

        print(f"\n已迁移到JSON存储: {json_path}")

        # 迁移到SQLite存储
        sqlite_path = os.path.join(temp_dir, "migrated.db")
        sqlite_storage = SQLiteStorage(path=sqlite_path)

        for key in json_storage.keys():
            sqlite_storage.set(key, json_storage.get(key))

        print(f"已迁移到SQLite存储: {sqlite_path}")

        # 验证数据一致性
        print("\n验证数据一致性:")
        for key in memory_storage.keys():
            mem_val = memory_storage.get(key)
            json_val = json_storage.get(key)
            sql_val = sqlite_storage.get(key)
            consistent = mem_val == json_val == sql_val
            print(f"  {key}: {'✓' if consistent else '✗'}")

    finally:
        shutil.rmtree(temp_dir)

    return memory_storage


# ============================================================
# 示例 10: 与Agent集成
# ============================================================
def example_10_agent_integration():
    """
    存储与Agent的集成使用
    """
    print("\n" + "=" * 60)
    print("示例 10: 与Agent集成")
    print("=" * 60)

    print("\n存储在Agent中的使用方式:")
    print("""
    from alphora.agent import BaseAgent
    from alphora.storage import SQLiteStorage
    
    # 方式1：Agent自动管理存储
    agent = BaseAgent(
        storage_path="./data/agent.db",
        storage_type="sqlite"
    )
    
    # 方式2：使用自定义存储
    custom_storage = SQLiteStorage(path="./custom.db")
    agent = BaseAgent(storage=custom_storage)
    
    # Agent内部会使用存储来：
    # - 保存会话历史
    # - 存储用户数据
    # - 缓存中间结果
    # - 持久化配置
    
    # 访问Agent的存储
    agent.storage.set("custom_key", "custom_value")
    value = agent.storage.get("custom_key")
    """)

    # 模拟Agent使用存储
    storage = InMemoryStorage()

    # 模拟保存会话
    session_id = "sess_001"
    storage.set(f"session:{session_id}:messages", [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"}
    ])
    storage.set(f"session:{session_id}:metadata", {
        "created_at": datetime.now().isoformat(),
        "user_id": "user_001"
    })

    # 模拟保存用户偏好
    storage.set("user:user_001:preferences", {
        "language": "zh-CN",
        "response_style": "concise"
    })

    print("\n模拟的存储数据:")
    for key in sorted(storage.keys()):
        print(f"  {key}")

    return storage


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Storage 存储系统示例")
    print("=" * 60)

    example_1_memory_storage()
    example_2_json_storage()
    example_3_sqlite_storage()
    example_4_storage_factory()
    example_5_serialization()
    example_6_batch_operations()
    example_7_key_namespaces()
    example_8_storage_stats()
    example_9_backend_switching()
    example_10_agent_integration()

    print("\n" + "=" * 60)
    print("所有存储系统示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()