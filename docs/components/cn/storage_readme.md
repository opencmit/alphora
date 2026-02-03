# Alphora Storage

**统一存储后端组件**

Storage 是 Alphora 框架的统一存储模块，提供类似 Redis 的接口，支持多种后端实现（JSON 文件、SQLite、内存）。它是 Memory 组件的底层存储引擎，用于持久化会话历史、用户数据和应用状态。

## 特性

-  **统一接口** - 类似 Redis 的 API，支持键值、列表、哈希操作
-  **多后端支持** - JSON 文件、SQLite 数据库、内存存储
-  **TTL 支持** - 键值过期时间管理
-  **线程安全** - 支持多线程并发访问
-  **自动持久化** - 可配置的自动保存机制
-  **事务支持** - SQLite 后端支持事务操作
-  **压缩支持** - JSON 存储支持 gzip 压缩

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.storage import JSONStorage, SQLiteStorage, InMemoryStorage

# JSON 存储（适合开发调试）
storage = JSONStorage("./data/storage.json")

# SQLite 存储（适合生产环境）
storage = SQLiteStorage("./data/storage.db")

# 内存存储（适合测试）
storage = InMemoryStorage()

# 统一接口
storage.set("user:1:name", "Alice")
name = storage.get("user:1:name")
print(name)  # Alice
```

## 目录

- [存储后端](#存储后端)
- [基本操作](#基本操作)
- [列表操作](#列表操作)
- [哈希操作](#哈希操作)
- [过期时间](#过期时间)
- [事务支持](#事务支持)
- [与 Memory 集成](#与-memory-集成)
- [配置管理](#配置管理)
- [序列化器](#序列化器)
- [API 参考](#api-参考)

---

## 存储后端

### JSONStorage

JSON 文件存储，适合开发调试和轻量级部署。

```python
from alphora.storage import JSONStorage

# 基础用法
storage = JSONStorage("./data/storage.json")
storage.set("key", "value")
storage.save()  # 手动保存

# 上下文管理器（自动保存）
with JSONStorage("./data/storage.json") as storage:
    storage.set("key", "value")
# 退出时自动保存

# 带压缩
from alphora.storage import StorageConfig

config = StorageConfig(
    path="./data/storage.json",
    compression=True,      # 启用 gzip 压缩
    auto_save=True,        # 自动保存
    save_interval=30       # 30 秒保存一次
)
storage = JSONStorage(config=config)
```

**特点**：
- 单文件存储，人类可读
- 支持 gzip 压缩
- 支持自动保存
- 支持备份和恢复

### SQLiteStorage

SQLite 数据库存储，适合生产环境。

```python
from alphora.storage import SQLiteStorage

# 基础用法
storage = SQLiteStorage("./data/storage.db")
storage.set("key", "value")

# 内存数据库
storage = SQLiteStorage()  # 无 path 参数则使用内存

# 事务支持
with storage.transaction():
    storage.set("key1", "value1")
    storage.set("key2", "value2")
# 自动提交或回滚
```

**特点**：
- 支持并发访问
- 查询高效，支持索引
- 完整事务支持
- WAL 模式优化性能

### InMemoryStorage

内存存储，适合测试或不需要持久化的场景。

```python
from alphora.storage import InMemoryStorage

storage = InMemoryStorage()
storage.set("key", "value")

# 数据在程序结束后丢失
```

### 工厂函数

使用 `create_storage()` 工厂函数创建存储实例：

```python
from alphora.storage import create_storage

# JSON 存储
storage = create_storage("json", path="./data/storage.json")

# SQLite 存储
storage = create_storage("sqlite", path="./data/storage.db")

# 内存存储
storage = create_storage("memory")
```

---

## 基本操作

### 键值操作

```python
# 设置值
storage.set("key", "value")
storage.set("user:1:profile", {"name": "Alice", "age": 30})

# 带过期时间（秒）
storage.set("session:abc123", {"token": "xxx"}, ttl=3600)

# 获取值
value = storage.get("key")
value = storage.get("nonexistent", default="默认值")

# 检查存在
if storage.exists("key"):
    print("键存在")

# 也支持 in 操作符
if "key" in storage:
    print("键存在")

# 删除键
storage.delete("key")

# 也支持 del 操作符
del storage["key"]
```

### 批量操作

```python
# 批量设置
storage.mset({
    "key1": "value1",
    "key2": "value2",
    "key3": "value3"
})

# 批量获取
values = storage.mget(["key1", "key2", "key3"])
# {"key1": "value1", "key2": "value2", "key3": "value3"}

# 批量删除
count = storage.mdelete(["key1", "key2"])
print(f"删除了 {count} 个键")
```

### 键查询

```python
# 获取所有键
all_keys = storage.keys()

# 模式匹配
user_keys = storage.keys("user:*")      # 以 user: 开头
name_keys = storage.keys("*:name")      # 以 :name 结尾
session_keys = storage.keys("session:*:token")
```

### 计数器

```python
# 递增
storage.set("counter", 0)
new_value = storage.incr("counter")      # 1
new_value = storage.incr("counter", 5)   # 6

# 递减
new_value = storage.decr("counter")      # 5
new_value = storage.decr("counter", 3)   # 2
```

### 字典式访问

```python
# 设置
storage["key"] = "value"

# 获取
value = storage["key"]

# 删除
del storage["key"]

# 长度
count = len(storage)

# 迭代
for key in storage:
    print(key, storage[key])
```

---

## 列表操作

支持类似 Redis 的列表操作，适合存储有序数据如消息历史。

### 基本列表操作

```python
# 从右侧添加（追加）
storage.rpush("messages", "msg1", "msg2", "msg3")

# 从左侧添加（前置）
storage.lpush("messages", "msg0")

# 获取列表范围
messages = storage.lrange("messages", 0, -1)  # 获取全部
# ["msg0", "msg1", "msg2", "msg3"]

messages = storage.lrange("messages", 0, 1)   # 前两个
# ["msg0", "msg1"]

messages = storage.lrange("messages", -2, -1)  # 后两个
# ["msg2", "msg3"]

# 获取列表长度
length = storage.llen("messages")  # 4
```

### 弹出操作

```python
# 从左侧弹出
first = storage.lpop("messages")  # "msg0"

# 从右侧弹出
last = storage.rpop("messages")   # "msg3"
```

### 索引操作

```python
# 获取指定位置元素
item = storage.lindex("messages", 0)   # 第一个
item = storage.lindex("messages", -1)  # 最后一个

# 设置指定位置的值
storage.lset("messages", 0, "new_msg")

# 移除元素
# count=0 移除所有匹配项
# count>0 从头开始移除 count 个
# count<0 从尾开始移除 |count| 个
removed = storage.lrem("messages", 0, "msg1")
```

### 消息历史示例

```python
# 存储聊天历史
session_key = "chat:session:abc123"

# 添加消息
storage.rpush(session_key, {
    "role": "user",
    "content": "你好"
})
storage.rpush(session_key, {
    "role": "assistant", 
    "content": "你好！有什么可以帮助你的？"
})

# 获取最近 10 条消息
recent = storage.lrange(session_key, -10, -1)

# 限制历史长度（保留最近 100 条）
while storage.llen(session_key) > 100:
    storage.lpop(session_key)
```

---

## 哈希操作

支持类似 Redis 的哈希操作，适合存储结构化对象。

### 基本哈希操作

```python
# 设置单个字段
storage.hset("user:1", "name", "Alice")
storage.hset("user:1", "age", 30)
storage.hset("user:1", "email", "alice@example.com")

# 获取单个字段
name = storage.hget("user:1", "name")  # "Alice"
name = storage.hget("user:1", "nonexistent", default="Unknown")

# 获取所有字段
user = storage.hgetall("user:1")
# {"name": "Alice", "age": 30, "email": "alice@example.com"}

# 获取所有字段名
fields = storage.hkeys("user:1")
# ["name", "age", "email"]

# 检查字段是否存在
if storage.hexists("user:1", "email"):
    print("邮箱已设置")

# 删除字段
storage.hdel("user:1", "email")
storage.hdel("user:1", "field1", "field2")  # 批量删除
```

### 用户配置示例

```python
# 存储用户配置
config_key = "config:user:123"

storage.hset(config_key, "theme", "dark")
storage.hset(config_key, "language", "zh-CN")
storage.hset(config_key, "notifications", True)

# 获取所有配置
config = storage.hgetall(config_key)

# 更新单个配置
storage.hset(config_key, "theme", "light")
```

---

## 过期时间

支持为键设置过期时间（TTL）。

```python
# 设置时指定 TTL（秒）
storage.set("session:token", "abc123", ttl=3600)  # 1 小时后过期

# 为已存在的键设置过期时间
storage.set("key", "value")
storage.expire("key", 300)  # 5 分钟后过期

# 查询剩余时间
ttl = storage.ttl("key")
# 返回值：
#   > 0: 剩余秒数
#   -1: 永不过期
#   -2: 键不存在

# 移除过期时间（使键永久有效）
storage.persist("key")
```

### 会话管理示例

```python
import uuid
import time

def create_session(user_id: str) -> str:
    """创建会话"""
    session_id = str(uuid.uuid4())
    storage.set(
        f"session:{session_id}",
        {"user_id": user_id, "created_at": time.time()},
        ttl=86400  # 24 小时
    )
    return session_id

def get_session(session_id: str) -> dict:
    """获取会话"""
    return storage.get(f"session:{session_id}")

def refresh_session(session_id: str):
    """刷新会话过期时间"""
    if storage.exists(f"session:{session_id}"):
        storage.expire(f"session:{session_id}", 86400)
```

---

## 事务支持

SQLite 后端支持完整的事务操作。

```python
from alphora.storage import SQLiteStorage

storage = SQLiteStorage("./data/storage.db")

# 使用上下文管理器
with storage.transaction():
    storage.set("account:1:balance", 1000)
    storage.set("account:2:balance", 500)
    # 如果发生异常，自动回滚
    # 正常完成则自动提交

# 模拟转账
def transfer(from_id: str, to_id: str, amount: float):
    with storage.transaction():
        from_key = f"account:{from_id}:balance"
        to_key = f"account:{to_id}:balance"
        
        from_balance = storage.get(from_key, 0)
        to_balance = storage.get(to_key, 0)
        
        if from_balance < amount:
            raise ValueError("余额不足")
        
        storage.set(from_key, from_balance - amount)
        storage.set(to_key, to_balance + amount)
```

---

## 与 Memory 集成

Storage 是 Memory 组件的底层存储引擎，用于持久化会话历史。

### 基础集成

```python
from alphora.memory import MemoryManager
from alphora.storage import SQLiteStorage

# 创建存储后端
storage = SQLiteStorage("./data/memory.db")

# 创建 Memory Manager（带存储）
memory = MemoryManager(storage=storage)

# 添加消息
memory.add_user("你好", session_id="session_123")
memory.add_assistant("你好！有什么可以帮助你的？", session_id="session_123")

# 消息自动持久化到 SQLite
```

### 多会话管理

```python
from alphora.memory import MemoryManager
from alphora.storage import SQLiteStorage

storage = SQLiteStorage("./data/conversations.db")
memory = MemoryManager(storage=storage)

# 不同用户的会话
memory.add_user("你好", session_id="user:alice:chat")
memory.add_user("Hi", session_id="user:bob:chat")

# 获取特定会话历史
alice_history = memory.build_history(session_id="user:alice:chat")
bob_history = memory.build_history(session_id="user:bob:chat")

# 列出所有会话
sessions = storage.keys("memory:session:*")
```

### 自定义存储键

```python
import time

# 使用 Storage 直接存储 Memory 相关数据

# 存储用户偏好
storage.hset("user:123:prefs", "system_prompt", "你是一个友好的助手")
storage.hset("user:123:prefs", "max_history", 50)

# 存储会话元数据
storage.hset("session:abc:meta", "created_at", time.time())
storage.hset("session:abc:meta", "message_count", 0)
storage.hset("session:abc:meta", "total_tokens", 0)

# 存储消息历史（列表）
storage.rpush("session:abc:messages", {
    "role": "user",
    "content": "你好"
})
```

---

## 配置管理

### StorageConfig

```python
from alphora.storage import StorageConfig, JSONStorage, SQLiteStorage

# 配置对象
config = StorageConfig(
    path="./data/storage.json",  # 存储路径
    auto_save=True,              # 自动保存
    save_interval=60,            # 自动保存间隔（秒）
    compression=False,           # 是否压缩（仅 JSON）
    encryption_key=None          # 加密密钥（预留）
)

# 使用配置创建存储
storage = JSONStorage(config=config)

# 或直接传递 path
storage = JSONStorage("./data/storage.json")
```

### 存储信息

```python
# 获取存储信息
info = storage.info()
print(info)
# {
#     "type": "JSONStorage",
#     "size": 42,
#     "config": {"path": "./data/storage.json", "auto_save": True},
#     "file_size": 1024,
#     "data_count": 30,
#     "list_count": 5,
#     "hash_count": 7,
#     ...
# }

# 获取键数量
count = storage.size()
# 或
count = len(storage)
```

### 维护操作

```python
# JSON 存储
json_storage = JSONStorage("./data/storage.json")

# 创建备份
json_storage.backup("./data/storage.bak")

# 压缩（清理过期数据并重新保存）
json_storage.compact()

# SQLite 存储
sqlite_storage = SQLiteStorage("./data/storage.db")

# 压缩数据库文件
sqlite_storage.vacuum()

# 清空所有数据
storage.clear()
```

---

## 序列化器

Storage 使用序列化器处理复杂数据类型的存储。

### 内置序列化器

```python
from alphora.storage import JSONSerializer, PickleSerializer, get_serializer

# JSON 序列化器（默认）
json_serializer = JSONSerializer(indent=2, ensure_ascii=False)
data = {"name": "Alice", "age": 30}
serialized = json_serializer.serialize(data)
restored = json_serializer.deserialize(serialized)

# Pickle 序列化器（支持任意 Python 对象）
pickle_serializer = PickleSerializer()
serialized = pickle_serializer.serialize(data)
restored = pickle_serializer.deserialize(serialized)

# 工厂函数
serializer = get_serializer("json", indent=2)
serializer = get_serializer("pickle")
```

### 扩展类型支持

JSON 序列化器自动支持以下扩展类型：

```python
from datetime import datetime
from dataclasses import dataclass

# datetime
storage.set("timestamp", datetime.now())
dt = storage.get("timestamp")  # 自动还原为 datetime

# bytes
storage.set("binary", b"hello world")
data = storage.get("binary")  # 自动还原为 bytes

# set
storage.set("tags", {"python", "ai", "llm"})
tags = storage.get("tags")  # 自动还原为 set

# dataclass
@dataclass
class User:
    name: str
    age: int

storage.set("user", User("Alice", 30))
user = storage.get("user")  # 返回字典形式
```

### 自定义序列化

```python
class MyObject:
    def __init__(self, value):
        self.value = value
    
    def __json__(self):
        """自定义 JSON 序列化"""
        return {"value": self.value}

obj = MyObject(42)
storage.set("obj", obj)
```

---

## API 参考

### StorageBackend（基类）

#### 基本操作

| 方法 | 说明 |
|------|------|
| `get(key, default=None)` | 获取值 |
| `set(key, value, ttl=None)` | 设置值 |
| `delete(key)` | 删除键 |
| `exists(key)` | 检查键是否存在 |
| `keys(pattern="*")` | 获取匹配的键 |

#### 批量操作

| 方法 | 说明 |
|------|------|
| `mget(keys)` | 批量获取 |
| `mset(data, ttl=None)` | 批量设置 |
| `mdelete(keys)` | 批量删除 |

#### 列表操作

| 方法 | 说明 |
|------|------|
| `lpush(key, *values)` | 从左侧插入 |
| `rpush(key, *values)` | 从右侧插入 |
| `lpop(key)` | 从左侧弹出 |
| `rpop(key)` | 从右侧弹出 |
| `lrange(key, start, end)` | 获取范围 |
| `llen(key)` | 获取长度 |
| `lindex(key, index)` | 获取指定位置 |
| `lset(key, index, value)` | 设置指定位置 |
| `lrem(key, count, value)` | 移除元素 |

#### 哈希操作

| 方法 | 说明 |
|------|------|
| `hget(key, field, default=None)` | 获取字段值 |
| `hset(key, field, value)` | 设置字段值 |
| `hdel(key, *fields)` | 删除字段 |
| `hgetall(key)` | 获取所有字段 |
| `hkeys(key)` | 获取所有字段名 |
| `hexists(key, field)` | 检查字段是否存在 |

#### 计数器

| 方法 | 说明 |
|------|------|
| `incr(key, amount=1)` | 递增 |
| `decr(key, amount=1)` | 递减 |

#### 过期管理

| 方法 | 说明 |
|------|------|
| `expire(key, seconds)` | 设置过期时间 |
| `ttl(key)` | 获取剩余过期时间 |
| `persist(key)` | 移除过期时间 |

#### 持久化

| 方法 | 说明 |
|------|------|
| `save()` | 保存到存储 |
| `load()` | 从存储加载 |
| `clear()` | 清空所有数据 |
| `close()` | 关闭连接 |

#### 工具方法

| 方法 | 说明 |
|------|------|
| `size()` | 获取键数量 |
| `info()` | 获取存储信息 |
| `transaction()` | 事务上下文管理器 |

### JSONStorage

继承 `StorageBackend`，额外方法：

| 方法 | 说明 |
|------|------|
| `backup(backup_path=None)` | 创建备份 |
| `compact()` | 压缩存储文件 |

### SQLiteStorage

继承 `StorageBackend`，额外方法：

| 方法 | 说明 |
|------|------|
| `vacuum()` | 压缩数据库文件 |

### StorageConfig

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | `None` | 存储路径 |
| `auto_save` | `bool` | `True` | 自动保存 |
| `save_interval` | `int` | `60` | 保存间隔（秒） |
| `compression` | `bool` | `False` | 启用压缩 |
| `encryption_key` | `str` | `None` | 加密密钥 |

### Serializer

| 方法 | 说明 |
|------|------|
| `serialize(data)` | 序列化为字节 |
| `deserialize(data)` | 从字节反序列化 |
| `serialize_to_string(data)` | 序列化为字符串 |
| `deserialize_from_string(data)` | 从字符串反序列化 |

### 工厂函数

```python
# 创建存储实例
storage = create_storage(storage_type, path=None, **kwargs)
# storage_type: "json", "sqlite", "memory"

# 获取序列化器
serializer = get_serializer(name, **kwargs)
# name: "json", "pickle"
```

### 异常类

| 异常 | 说明 |
|------|------|
| `SerializationError` | 序列化失败 |
| `DeserializationError` | 反序列化失败 |
