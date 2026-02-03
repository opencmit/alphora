# Alphora Sandbox

**安全代码执行沙箱组件**

Sandbox 是一个为 AI Agent 设计的安全代码执行环境，提供隔离的 Python 代码执行、文件操作、包管理等能力。它支持本地执行和 Docker 容器两种后端，并提供与 OpenAI/Anthropic Function Calling 兼容的工具接口。

## 特性

- 🔒 **安全隔离** - 支持 Docker 容器级别隔离，资源限制与安全策略
- 🐍 **代码执行** - Python 代码、脚本文件、Shell 命令执行
- 📁 **文件操作** - 完整的文件系统操作（读写、删除、列表）
- 📦 **包管理** - pip 包安装、卸载、查询
- 🤖 **Agent 集成** - 开箱即用的 OpenAI/Anthropic 工具定义
- ☁️ **多存储后端** - 本地文件系统、S3、MinIO
- 🔄 **生命周期管理** - 异步上下文管理器，自动清理
- 📊 **资源监控** - CPU、内存、磁盘使用监控

## 安装

```bash
pip install alphora

# Docker 后端支持
pip install docker

# S3/MinIO 存储支持
pip install aioboto3
```

## 快速开始

```python
from alphora.sandbox import Sandbox

# 创建并使用沙箱
async with Sandbox.create_local() as sandbox:
    result = await sandbox.run("print('Hello, World!')")
    print(result.stdout)  # Hello, World!
```

## 目录

- [基础用法](#基础用法)
- [执行后端](#执行后端)
- [代码执行](#代码执行)
- [文件操作](#文件操作)
- [包管理](#包管理)
- [资源限制与安全策略](#资源限制与安全策略)
- [AI Agent 工具集成](#ai-agent-工具集成)
- [多沙箱管理](#多沙箱管理)
- [存储后端](#存储后端)
- [配置管理](#配置管理)
- [API 参考](#api-参考)

---

## 基础用法

### 创建沙箱

```python
from alphora.sandbox import Sandbox

# 方式 1：上下文管理器（推荐）
async with Sandbox.create_local() as sandbox:
    result = await sandbox.run("print(1 + 1)")
    print(result.stdout)  # 2

# 方式 2：手动管理生命周期
sandbox = Sandbox.create_local()
await sandbox.start()

result = await sandbox.run("print('Hello')")
print(result.stdout)

await sandbox.stop()
```

### 工厂方法

```python
# 本地沙箱
sandbox = Sandbox.create_local(
    base_path="/data/sandboxes",
    resource_limits=ResourceLimits(timeout_seconds=60)
)

# Docker 沙箱
sandbox = Sandbox.create_docker(
    docker_image="python:3.11-slim",
    resource_limits=ResourceLimits(memory_mb=512)
)

# 从配置创建
config = SandboxConfig.docker(image="python:3.11", network_enabled=True)
sandbox = Sandbox.from_config(config)
```

### 执行结果

```python
result = await sandbox.run("print('Hello')")

# 检查结果
if result.success:
    print(result.stdout)       # 标准输出
    print(result.execution_time)  # 执行时间（秒）
else:
    print(result.stderr)       # 标准错误
    print(result.error)        # 错误信息
    print(result.return_code)  # 返回码
```

---

## 执行后端

### Local 后端

直接使用本地 Python 解释器执行代码。

```python
from alphora.sandbox import Sandbox, LocalBackend

# 通过 Sandbox
sandbox = Sandbox.create_local()

# 直接使用后端
backend = LocalBackend(
    sandbox_id="test",
    workspace_path="/tmp/sandbox/test"
)
await backend.initialize()
await backend.start()
result = await backend.execute_code("print('Hello')")
await backend.stop()
```

**特点**：
- 启动快速，无需 Docker
- 适合开发和测试环境
- 隔离性较弱，依赖文件系统隔离

### Docker 后端

在 Docker 容器中执行代码，提供强隔离。

```python
from alphora.sandbox import Sandbox, DockerBackend, is_docker_available

# 检查 Docker 可用性
if is_docker_available():
    sandbox = Sandbox.create_docker(
        docker_image="python:3.11-slim"
    )
    async with sandbox:
        result = await sandbox.run("import sys; print(sys.version)")
```

**特点**：
- 完整的容器隔离
- 资源限制（CPU、内存）
- 网络隔离
- 安全选项（no-new-privileges 等）

**预置镜像**：

```dockerfile
# 基础镜像
python:3.11-slim

# 数据科学镜像（包含 numpy, pandas, scikit-learn）
alphora/sandbox:datascience

# 机器学习镜像（包含 torch, transformers）
alphora/sandbox:ml

# 最小镜像（快速启动）
alphora/sandbox:minimal
```

---

## 代码执行

### 执行 Python 代码

```python
# 简单执行
result = await sandbox.run("print(1 + 1)")

# 带超时
result = await sandbox.execute_code(
    code="import time; time.sleep(5); print('done')",
    timeout=10
)

# 多行代码
code = """
import json
data = {"name": "Alice", "age": 30}
print(json.dumps(data, indent=2))
"""
result = await sandbox.execute_code(code)
```

### 执行 Python 文件

```python
# 保存文件
await sandbox.write_file("script.py", """
import sys
print(f"Args: {sys.argv[1:]}")
print("Hello from file!")
""")

# 执行文件
result = await sandbox.execute_file(
    "script.py",
    args=["arg1", "arg2"],
    timeout=30
)
print(result.stdout)
# Args: ['arg1', 'arg2']
# Hello from file!
```

### 执行 Shell 命令

```python
# 执行 Shell 命令
result = await sandbox.execute_shell("ls -la")
print(result.stdout)

# 管道命令
result = await sandbox.execute_shell("echo 'Hello' | tr '[:lower:]' '[:upper:]'")
print(result.stdout)  # HELLO
```

---

## 文件操作

### 读写文件

```python
# 写入文本文件
await sandbox.write_file("data.txt", "Hello, World!")

# 读取文件
content = await sandbox.read_file("data.txt")
print(content)  # Hello, World!

# 写入二进制文件
await sandbox.write_file_bytes("image.png", image_bytes)

# 读取二进制文件
data = await sandbox.read_file_bytes("image.png")

# 保存文件并获取信息
file_info = await sandbox.save_file("config.json", '{"key": "value"}')
print(file_info.size)  # 文件大小
print(file_info.file_type)  # FileType.JSON
```

### 文件管理

```python
# 检查文件存在
exists = await sandbox.file_exists("data.txt")

# 删除文件
deleted = await sandbox.delete_file("data.txt")

# 复制文件
await sandbox.copy_file("source.txt", "dest.txt")

# 移动文件
await sandbox.move_file("old.txt", "new.txt")

# 下载文件（获取字节）
data = await sandbox.download_file("report.pdf")
```

### 列出文件

```python
# 列出当前目录
files = await sandbox.list_files()
for f in files:
    print(f"{f.name}: {f.size_human}")

# 列出指定目录
files = await sandbox.list_files("src/")

# 递归列出
files = await sandbox.list_files("", recursive=True)

# 按模式过滤
files = await sandbox.list_files("", pattern="*.py")
```

---

## 包管理

### 安装包

```python
# 安装单个包
result = await sandbox.install_package("requests")

# 安装指定版本
result = await sandbox.install_package("pandas", version="2.0.0")

# 升级包
result = await sandbox.install_package("numpy", upgrade=True)

# 批量安装
result = await sandbox.install_packages(["numpy", "pandas", "scikit-learn"])

# 从 requirements.txt 安装
await sandbox.write_file("requirements.txt", "requests>=2.28.0\npandas>=2.0.0")
result = await sandbox.install_requirements("requirements.txt")
```

### 卸载包

```python
result = await sandbox.uninstall_package("requests")
```

### 查询包

```python
# 列出已安装包
packages = await sandbox.list_packages()
for pkg in packages:
    print(f"{pkg.name}=={pkg.version}")

# 检查包是否安装
installed = await sandbox.package_installed("numpy")
```

---

## 资源限制与安全策略

### 资源限制

```python
from alphora.sandbox import ResourceLimits

# 自定义资源限制
limits = ResourceLimits(
    timeout_seconds=60,      # 执行超时
    memory_mb=512,           # 内存限制
    cpu_cores=1.0,           # CPU 核心数
    disk_mb=1024,            # 磁盘限制
    max_processes=10,        # 最大进程数
    max_threads=50,          # 最大线程数
    network_enabled=False,   # 禁用网络
    max_output_size=10*1024*1024,  # 输出大小限制
)

sandbox = Sandbox.create_docker(resource_limits=limits)

# 预设配置
minimal = ResourceLimits.minimal()      # 轻量级任务
standard = ResourceLimits.standard()    # 标准配置
high_perf = ResourceLimits.high_performance()  # 高性能
```

### 安全策略

```python
from alphora.sandbox import SecurityPolicy

# 自定义安全策略
policy = SecurityPolicy(
    allow_shell=True,           # 允许 Shell 命令
    allow_network=False,        # 禁用网络
    allow_file_write=True,      # 允许文件写入
    allow_subprocess=False,     # 禁用子进程
    blocked_imports=[           # 阻止的导入
        "os.system", "subprocess", "ctypes"
    ],
    blocked_paths=[             # 阻止访问的路径
        "/etc", "/usr", "/root"
    ],
    max_file_size_mb=100,       # 最大文件大小
    audit_enabled=True,         # 启用审计
)

sandbox = Sandbox.create_local(security_policy=policy)

# 预设策略
strict = SecurityPolicy.strict()        # 严格模式
permissive = SecurityPolicy.permissive()  # 宽松模式
```

---

## AI Agent 工具集成

### SandboxTools 类

```python
from alphora.sandbox import Sandbox, SandboxTools

async with Sandbox.create_local() as sandbox:
    tools = SandboxTools(sandbox)
    
    # 执行代码
    result = await tools.run_python_code("print(1 + 1)")
    print(result)
    # {'success': True, 'output': '2\n', 'error': '', 'execution_time': 0.05}
    
    # 保存文件
    result = await tools.save_file("test.py", "print('hello')")
    
    # 安装包
    result = await tools.install_pip_package("requests")
```

### OpenAI Function Calling

```python
tools = SandboxTools(sandbox)

# 获取 OpenAI 格式的工具定义
openai_tools = tools.get_openai_tools()

# 传给 OpenAI API
response = await client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=openai_tools
)

# 执行工具调用
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        result = await tools.execute_tool(
            tool_call.function.name,
            json.loads(tool_call.function.arguments)
        )
```

### Anthropic Tool Use

```python
# 获取 Anthropic 格式的工具定义
anthropic_tools = tools.get_anthropic_tools()

# 传给 Anthropic API
response = await client.messages.create(
    model="claude-3-opus",
    messages=messages,
    tools=anthropic_tools
)
```

### 可用工具列表

| 工具名称 | 说明 |
|---------|------|
| `run_python_code` | 执行 Python 代码 |
| `run_python_file` | 执行 Python 文件 |
| `run_shell_command` | 执行 Shell 命令 |
| `save_file` | 保存文件 |
| `read_file` | 读取文件 |
| `delete_file` | 删除文件 |
| `list_files` | 列出文件 |
| `file_exists` | 检查文件存在 |
| `copy_file` | 复制文件 |
| `move_file` | 移动文件 |
| `install_pip_package` | 安装 pip 包 |
| `install_pip_packages` | 批量安装包 |
| `uninstall_pip_package` | 卸载包 |
| `list_installed_packages` | 列出已安装包 |
| `check_package_installed` | 检查包是否安装 |
| `set_environment_variable` | 设置环境变量 |
| `get_environment_variable` | 获取环境变量 |
| `get_sandbox_status` | 获取沙箱状态 |
| `get_resource_usage` | 获取资源使用情况 |
| `reset_sandbox` | 重置沙箱 |

---

## 多沙箱管理

### SandboxManager

```python
from alphora.sandbox import SandboxManager

async with SandboxManager(base_path="/data/sandboxes") as manager:
    # 创建沙箱
    sandbox1 = await manager.create_sandbox("worker-1")
    sandbox2 = await manager.create_sandbox("worker-2")
    
    # 并行执行
    import asyncio
    results = await asyncio.gather(
        sandbox1.run("print('worker 1')"),
        sandbox2.run("print('worker 2')")
    )
    
    # 列出沙箱
    sandboxes = manager.list_sandboxes()
    
    # 获取指定沙箱
    sandbox = manager.get_sandbox("worker-1")
    
    # 销毁沙箱
    await manager.destroy_sandbox("worker-1")
```

### 沙箱池管理

```python
manager = SandboxManager(
    base_path="/data/sandboxes",
    default_backend=BackendType.DOCKER,
    max_sandboxes=100,
    auto_cleanup=True
)

await manager.start()

# 获取或创建
sandbox = await manager.get_or_create("task-123")

# 批量操作
await manager.stop_all()
await manager.destroy_all()
health = await manager.health_check_all()

# 清理空闲沙箱
cleaned = await manager.cleanup_idle(max_idle_seconds=3600)

# 获取资源使用总量
usage = await manager.get_total_resource_usage()

await manager.shutdown()
```

---

## 存储后端

### 本地存储

```python
from alphora.sandbox.storage import LocalStorage, StorageConfig

config = StorageConfig.local("/data/storage")

async with LocalStorage(config) as storage:
    # 存储文件
    await storage.put("myfile.txt", b"Hello World")
    
    # 读取文件
    data = await storage.get("myfile.txt")
    
    # 列出文件
    files = await storage.list(prefix="my")
    
    # 删除文件
    await storage.delete("myfile.txt")
```

### S3/MinIO 存储

```python
from alphora.sandbox.storage import S3Storage, StorageConfig, StorageFactory

# MinIO 配置
config = StorageConfig.minio(
    endpoint="http://localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    bucket="sandboxes"
)

# 或使用工厂
storage = StorageFactory.minio(
    endpoint="http://localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    bucket="sandboxes"
)

async with storage:
    await storage.put("data/file.txt", b"content")
    
    # 生成预签名 URL
    url = await storage.get_presigned_url("data/file.txt", expires_in=3600)
    
    # 获取存储桶信息
    info = await storage.get_bucket_info()
```

### 存储工厂

```python
from alphora.sandbox.storage import StorageFactory

# 本地存储
storage = StorageFactory.local("/data/storage")

# MinIO 存储
storage = StorageFactory.minio(
    endpoint="localhost:9000",
    access_key="admin",
    secret_key="password",
    bucket="sandboxes"
)

# S3 存储
storage = StorageFactory.s3(
    access_key="AKIAXXXXXXXXXX",
    secret_key="xxxxxxxxxxxxx",
    bucket="my-bucket",
    region="us-west-2"
)
```

---

## 配置管理

### SandboxConfig

```python
from alphora.sandbox import SandboxConfig, ResourceLimits, SecurityPolicy

# 本地配置
config = SandboxConfig.local(
    path="/data/sandboxes",
    resource_limits=ResourceLimits(timeout_seconds=60)
)

# Docker 配置
config = SandboxConfig.docker(
    path="/data/sandboxes",
    image="python:3.11-slim",
    network_enabled=True
)

# 带 MinIO 存储
config = SandboxConfig.minio(
    endpoint="http://localhost:9000",
    access_key="admin",
    secret_key="password",
    bucket="sandboxes"
)
```

### 从环境变量加载

```python
from alphora.sandbox import config_from_env

# 环境变量：
# SANDBOX_BASE_PATH=/data/sandboxes
# SANDBOX_BACKEND=docker
# SANDBOX_DOCKER_IMAGE=python:3.11
# SANDBOX_TIMEOUT=60
# SANDBOX_MEMORY_MB=512

config = config_from_env()
sandbox = Sandbox.from_config(config)
```

### 从文件加载

```python
from alphora.sandbox import config_from_file

# JSON 配置文件
config = config_from_file("sandbox.json")

# YAML 配置文件
config = config_from_file("sandbox.yaml")
```

**配置文件示例** (sandbox.json)：

```json
{
  "base_path": "/data/sandboxes",
  "backend_type": "docker",
  "resource_limits": {
    "timeout_seconds": 300,
    "memory_mb": 512,
    "cpu_cores": 1.0,
    "network_enabled": false
  },
  "security_policy": {
    "allow_shell": true,
    "allow_network": false
  },
  "docker": {
    "image": "python:3.11-slim",
    "network_mode": "none"
  }
}
```

---

## API 参考

### Sandbox

#### 工厂方法

| 方法 | 说明 |
|------|------|
| `create_local(base_path, resource_limits, security_policy)` | 创建本地沙箱 |
| `create_docker(base_path, docker_image, resource_limits, security_policy)` | 创建 Docker 沙箱 |
| `from_config(config)` | 从配置创建沙箱 |
| `create(backend_type, **kwargs)` | 上下文管理器工厂 |

#### 生命周期

| 方法 | 说明 |
|------|------|
| `start()` | 启动沙箱 |
| `stop()` | 停止沙箱 |
| `restart()` | 重启沙箱 |
| `destroy()` | 销毁沙箱 |
| `health_check()` | 健康检查 |

#### 代码执行

| 方法 | 说明 |
|------|------|
| `run(code, timeout)` | 执行 Python 代码（简写） |
| `execute_code(code, timeout)` | 执行 Python 代码 |
| `execute_file(file_path, args, timeout)` | 执行 Python 文件 |
| `execute_shell(command, timeout)` | 执行 Shell 命令 |

#### 文件操作

| 方法 | 说明 |
|------|------|
| `read_file(path)` | 读取文本文件 |
| `read_file_bytes(path)` | 读取二进制文件 |
| `write_file(path, content)` | 写入文本文件 |
| `write_file_bytes(path, content)` | 写入二进制文件 |
| `save_file(path, content)` | 保存文件并返回信息 |
| `delete_file(path)` | 删除文件 |
| `file_exists(path)` | 检查文件存在 |
| `list_files(path, recursive, pattern)` | 列出文件 |
| `copy_file(source, dest)` | 复制文件 |
| `move_file(source, dest)` | 移动文件 |
| `download_file(path)` | 下载文件 |

#### 包管理

| 方法 | 说明 |
|------|------|
| `install_package(package, version, upgrade)` | 安装包 |
| `install_packages(packages)` | 批量安装包 |
| `uninstall_package(package)` | 卸载包 |
| `list_packages()` | 列出已安装包 |
| `package_installed(package)` | 检查包是否安装 |
| `install_requirements(path)` | 从 requirements.txt 安装 |

#### 环境变量

| 方法 | 说明 |
|------|------|
| `set_env(key, value)` | 设置环境变量 |
| `get_env(key)` | 获取环境变量 |
| `set_env_vars(env_vars)` | 批量设置环境变量 |

#### 监控

| 方法 | 说明 |
|------|------|
| `get_resource_usage()` | 获取资源使用情况 |
| `get_status()` | 获取状态字典 |
| `get_info()` | 获取完整信息 |

### SandboxManager

| 方法 | 说明 |
|------|------|
| `start()` | 启动管理器 |
| `shutdown(force)` | 关闭管理器 |
| `create_sandbox(name, sandbox_id, backend_type, ...)` | 创建沙箱 |
| `create_local_sandbox(name)` | 创建本地沙箱 |
| `create_docker_sandbox(name, docker_image)` | 创建 Docker 沙箱 |
| `get_or_create(sandbox_id)` | 获取或创建沙箱 |
| `get_sandbox(sandbox_id)` | 获取沙箱 |
| `get_sandbox_by_name(name)` | 按名称获取沙箱 |
| `has_sandbox(sandbox_id)` | 检查沙箱存在 |
| `list_sandboxes(status, backend_type)` | 列出沙箱 |
| `list_running()` | 列出运行中沙箱 |
| `stop_sandbox(sandbox_id)` | 停止沙箱 |
| `destroy_sandbox(sandbox_id)` | 销毁沙箱 |
| `restart_sandbox(sandbox_id)` | 重启沙箱 |
| `stop_all()` | 停止所有沙箱 |
| `destroy_all()` | 销毁所有沙箱 |
| `health_check_all()` | 检查所有沙箱健康状态 |
| `cleanup_stopped()` | 清理已停止沙箱 |
| `cleanup_idle(max_idle_seconds)` | 清理空闲沙箱 |
| `get_total_resource_usage()` | 获取总资源使用 |
| `get_status()` | 获取管理器状态 |

### SandboxTools

| 方法 | 说明 |
|------|------|
| `run_python_code(code, timeout)` | 执行 Python 代码 |
| `run_python_file(file_path, args, timeout)` | 执行 Python 文件 |
| `run_shell_command(command, timeout)` | 执行 Shell 命令 |
| `save_file(path, content)` | 保存文件 |
| `read_file(path)` | 读取文件 |
| `delete_file(path)` | 删除文件 |
| `list_files(path, recursive)` | 列出文件 |
| `file_exists(path)` | 检查文件存在 |
| `copy_file(source, dest)` | 复制文件 |
| `move_file(source, dest)` | 移动文件 |
| `install_pip_package(package, version)` | 安装包 |
| `install_pip_packages(packages)` | 批量安装包 |
| `uninstall_pip_package(package)` | 卸载包 |
| `list_installed_packages()` | 列出已安装包 |
| `check_package_installed(package)` | 检查包是否安装 |
| `set_environment_variable(key, value)` | 设置环境变量 |
| `get_environment_variable(key)` | 获取环境变量 |
| `get_sandbox_status()` | 获取沙箱状态 |
| `get_resource_usage()` | 获取资源使用 |
| `reset_sandbox()` | 重置沙箱 |
| `execute_tool(tool_name, parameters)` | 执行工具 |
| `get_available_tools()` | 获取可用工具列表 |
| `get_tool_definitions()` | 获取工具定义 |
| `get_openai_tools()` | 获取 OpenAI 格式工具 |
| `get_anthropic_tools()` | 获取 Anthropic 格式工具 |

### 类型定义

```python
from alphora.sandbox import (
    # 枚举
    BackendType,        # LOCAL, DOCKER
    StorageType,        # LOCAL, S3, MINIO
    SandboxStatus,      # CREATED, STARTING, RUNNING, STOPPING, STOPPED, ERROR, DESTROYED
    ExecutionStatus,    # PENDING, RUNNING, SUCCESS, FAILED, TIMEOUT, CANCELLED
    FileType,           # TEXT, PYTHON, JSON, IMAGE, ...
    
    # 配置
    ResourceLimits,     # 资源限制
    SecurityPolicy,     # 安全策略
    
    # 结果
    ExecutionResult,    # 执行结果
    FileInfo,           # 文件信息
    PackageInfo,        # 包信息
    SandboxInfo,        # 沙箱信息
    ResourceUsage,      # 资源使用
)
```

### 异常类

```python
from alphora.sandbox import (
    # 基础异常
    SandboxError,
    
    # 状态异常
    SandboxNotFoundError,
    SandboxAlreadyExistsError,
    SandboxNotRunningError,
    SandboxAlreadyRunningError,
    
    # 执行异常
    ExecutionError,
    ExecutionTimeoutError,
    ExecutionFailedError,
    
    # 文件系统异常
    FileSystemError,
    FileNotFoundError,
    PathTraversalError,
    
    # 包管理异常
    PackageError,
    PackageInstallError,
    
    # 安全异常
    SecurityViolationError,
    ShellAccessDeniedError,
    
    # 后端异常
    BackendError,
    DockerError,
    ContainerError,
    
    # 存储异常
    StorageError,
    StorageNotFoundError,
    
    # 配置异常
    ConfigurationError,
)
```