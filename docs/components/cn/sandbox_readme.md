# Alphora Sandbox

**安全代码执行沙箱组件**

Sandbox 是为 AI Agent 设计的安全执行环境，支持本地与 Docker 两种运行时，提供代码执行、文件管理、包管理和工具集成能力。

## 特性

-  **双运行时** - 支持 `local` 与 `docker`，按场景选择执行隔离级别
-  **远程 Docker** - 通过 `docker_host` 连接远程 TCP Docker daemon，支持镜像校验、Skills 自动同步、容器内文件操作
-  **挂载模式** - 支持 `direct` 直接挂载已有目录，或 `isolated` 子目录隔离
-  **代码执行** - 提供 Python 代码、脚本文件、Shell 命令执行能力
-  **文件管理** - 提供读写、复制、移动、删除、列表等完整文件操作
-  **包管理** - 支持 pip 包安装、卸载、查询与 requirements 安装
-  **工具集成** - 内置 `SandboxTools`，可直接对接工具调用流程
-  **异步生命周期** - 支持 `async with` 自动启动和停止

## 安装

```bash
pip install alphora

# 使用 Docker 运行时时需要
pip install docker
```

## 快速开始

```python
from alphora.sandbox import Sandbox

async with Sandbox(
    workspace_root="/data/my-project",
    mount_mode="direct",
    runtime="docker",
    allow_network=True,
) as sandbox:
    result = await sandbox.run("print('Hello, Sandbox')")
    print(result.stdout)
```

## 目录

- [基础用法](#基础用法)
- [挂载模式](#挂载模式)
- [执行后端](#执行后端)
- [容器内路径结构](#容器内路径结构)
- [远程 Docker (TCP)](#远程-docker-tcp)
- [代码执行](#代码执行)
- [文件操作](#文件操作)
- [包管理](#包管理)
- [AI Agent 工具集成](#ai-agent-工具集成)
- [多沙箱管理](#多沙箱管理)
- [API 参考](#api-参考)

---

## 基础用法

### 创建 Sandbox

```python
from alphora.sandbox import Sandbox
from alphora.sandbox.types import ResourceLimits, SecurityPolicy

limits = ResourceLimits(timeout_seconds=60, memory_mb=512)
policy = SecurityPolicy.strict()

sandbox = Sandbox(
    workspace_root="/tmp/sandboxes",
    mount_mode="isolated",      # direct | isolated
    runtime="local",            # local | docker
    image="alphora-sandbox:latest",
    allow_network=False,
    sandbox_id="task-001",
    name="analysis-worker",
    resource_limits=limits,
    security_policy=policy,
    auto_cleanup=True,
)

await sandbox.start()
result = await sandbox.run("print(1 + 1)")
await sandbox.stop()
```

### 上下文管理器

```python
async with Sandbox(runtime="local") as sandbox:
    result = await sandbox.run("print('done')")
    print(result.stdout)
```

### 执行结果

```python
result = await sandbox.run("print('Hello')")

if result.success:
    print(result.stdout)         # 标准输出
    print(result.execution_time) # 执行耗时（秒）
else:
    print(result.stderr)         # 标准错误
    print(result.error)          # 错误信息
    print(result.return_code)    # 返回码
```

---

## 挂载模式

### direct 模式（默认）

`workspace_path == workspace_root`

```python
sandbox = Sandbox(
    workspace_root="/data/my-existing-project",
    mount_mode="direct",
    runtime="docker",
)
```

适用场景：
- 直接在已有项目目录中执行代码
- 需要读取和修改现有文件树

### isolated 模式

`workspace_path == workspace_root/<sandbox_id>`

```python
sandbox = Sandbox(
    workspace_root="/tmp/sandboxes",
    mount_mode="isolated",
    sandbox_id="exp-001",
    runtime="local",
)
```

适用场景：
- 任务隔离、并行任务调度
- 按 `sandbox_id` 管理工作目录

---

## 执行后端

### Local 运行时

```python
sandbox = Sandbox(
    workspace_root="/tmp/local-sb",
    runtime="local",
)
```

特点：
- 启动快，依赖少
- 适合开发与调试

### Docker 运行时

```python
from alphora.sandbox import is_docker_available

if is_docker_available():
    async with Sandbox(
        workspace_root="/tmp/docker-sb",
        runtime="docker",
        image="alphora-sandbox:latest",
        allow_network=True,
    ) as sandbox:
        result = await sandbox.run("import sys; print(sys.version)")
```

特点：
- 隔离强，安全性更高
- 适合不受信代码执行场景

---

## 容器内路径结构

沙箱创建时自动在容器内建立以下目录结构（对齐 OpenAI Code Interpreter 等主流平台）：

```
/mnt/workspace/           # 工作目录 (cwd)，Agent 代码在此执行
├── uploads/              # 用户上传的文件
├── outputs/              # 输出文件（返回给用户的结果）
└── ...                   # Agent 自由创建的其他文件
/mnt/skills/              # 技能定义（只读挂载）
```

Agent 使用相对路径即可访问：
```python
result = await sandbox.execute_code("""
import pandas as pd
df = pd.read_csv('uploads/data.csv')
df.describe().to_csv('outputs/summary.csv')
print('Done')
""")
```

---

## 远程 Docker (TCP + TLS)

通过 `docker_host` 参数连接远程 Docker daemon，实现远程代码执行。

> **安全警告：** 切勿使用未加密的 2375 端口暴露 Docker daemon，否则任何人都可远程控制你的服务器。请始终使用 TLS（端口 2376）并配置客户端证书认证。

```python
from alphora.sandbox import Sandbox, DockerHost

async with Sandbox(
    runtime="docker",
    docker_host=DockerHost(
        url="tcp://your-server:2376",
        tls_verify=True,
        tls_ca_cert="/path/to/ca.pem",
        tls_client_cert="/path/to/cert.pem",
        tls_client_key="/path/to/key.pem",
    ),
    workspace_root="/data/sandboxes",         # 远程服务器上的绝对路径
    skill_host_path="/local/path/to/skills",  # 本地路径，自动同步到远程容器
    image="alphora-sandbox:latest",
) as sb:
    result = await sb.execute_code("print('Hello from remote!')")
```

### 远程模式行为

| 行为 | 本地 Docker | 远程 Docker (TCP) |
|------|------------|------------------|
| 镜像不存在 | 自动 build 或 pull | 报错并列出远程可用镜像 |
| workspace 目录 | 本地自动创建 | 要求远程绝对路径，跳过本地 mkdir |
| uploads/outputs | 本地 mkdir | 容器内以 root 创建后 chown |
| skills | 本地 bind mount (只读) | 本地文件打包后复制到容器内 |
| 文件操作 (read/write/delete) | 直接读写本地文件系统 | 通过 Docker API 在容器内操作 |

### 远程镜像校验

远程模式下，镜像不存在时会列出远程可用镜像并给出友好提示：

```
DockerError: Image 'alphora-sandbox:latest' not found on remote Docker daemon tcp://...

Available images:
  - python:3.11-slim
  - ubuntu:22.04
```

---

## 代码执行

```python
# 执行 Python 代码
result = await sandbox.execute_code("print(6 * 7)", timeout=30)

# 执行文件
await sandbox.write_file("script.py", "print('from file')")
result = await sandbox.execute_file("script.py")

# 执行 Shell 命令
result = await sandbox.execute_shell("ls -la")
```

---

## 文件操作

### 读写与管理

```python
await sandbox.write_file("a.txt", "hello")
text = await sandbox.read_file("a.txt")

await sandbox.write_file_bytes("b.bin", b"123")
data = await sandbox.read_file_bytes("b.bin")

exists = await sandbox.file_exists("a.txt")
await sandbox.copy_file("a.txt", "a_copy.txt")
await sandbox.move_file("a_copy.txt", "moved.txt")
await sandbox.delete_file("moved.txt")
```

### list_files

```python
# 列出当前目录（非递归）
files = await sandbox.list_files()

# 列出指定目录
files = await sandbox.list_files("src/")

# 指定目录 + 递归
files = await sandbox.list_files("src/", recursive=True)

# 列出全部文件（包含子目录）
files = await sandbox.list_files(path=None)

# 按模式过滤
py_files = await sandbox.list_files(path=None, pattern="*.py")
```

说明：
- `path=None` 会自动按“工作目录根路径 + 递归”处理

---

## 包管理

```python
await sandbox.install_package("requests")
await sandbox.install_package("pandas", version="2.2.0")
await sandbox.install_packages(["numpy", "scipy"])
await sandbox.uninstall_package("requests")

packages = await sandbox.list_packages()
installed = await sandbox.package_installed("numpy")
```

---

## AI Agent 工具集成

```python
from alphora.sandbox import Sandbox, SandboxTools

async with Sandbox(runtime="local") as sandbox:
    tools = SandboxTools(sandbox)

    result = await tools.run_python_code("print(1 + 1)")
    print(result)
```

---

## 多沙箱管理

```python
from alphora.sandbox import SandboxManager

async with SandboxManager(base_path="/tmp/sandboxes") as manager:
    sb = await manager.create_sandbox(
        name="worker-1",
        runtime="docker",
        mount_mode="isolated",
        image="alphora-sandbox:latest",
        allow_network=False,
    )
    await sb.run("print('ok')")
```

---

## API 参考

### Sandbox 构造参数

| 参数 | 说明 |
|------|------|
| `workspace_root` | Docker daemon 所在机器的工作目录路径。本地 Docker 为本地路径，远程 Docker 为远程服务器绝对路径 |
| `mount_mode` | 挂载模式：`direct` 或 `isolated` |
| `runtime` | 运行时：`local` 或 `docker` |
| `image` | Docker 镜像（`runtime="docker"` 时生效） |
| `allow_network` | 是否允许网络访问 |
| `sandbox_id` | 沙箱 ID |
| `name` | 沙箱名称 |
| `resource_limits` | 资源限制配置 |
| `security_policy` | 安全策略配置 |
| `auto_cleanup` | 停止后是否清理工作目录 |
| `skill_host_path` | 技能目录路径，Docker 中挂载为 `/mnt/skills`（只读）。远程模式下自动将本地目录同步到容器 |
| `docker_host` | Docker daemon 连接配置。接受 `DockerHost` 对象（含 TLS）、纯 URL 字符串或 `None`（自动读取环境变量） |

### Sandbox 属性

| 属性 | 说明 |
|------|------|
| `sandbox_id` | 沙箱唯一标识 |
| `name` | 沙箱名称 |
| `status` | 当前状态 |
| `is_running` | 是否运行中 |
| `backend_type` | 运行时类型 |
| `mount_mode` | 挂载模式 |
| `workspace_path` | 实际工作目录路径 |

### Sandbox 常用方法

| 方法 | 说明 |
|------|------|
| `start()` / `stop()` / `restart()` / `destroy()` | 生命周期管理 |
| `run()` / `execute_code()` / `execute_file()` / `execute_shell()` | 代码执行 |
| `read_file()` / `write_file()` / `list_files()` / `delete_file()` | 文件操作 |
| `install_package()` / `list_packages()` / `uninstall_package()` | 包管理 |
| `get_status()` / `get_info()` / `get_resource_usage()` | 状态与监控 |

### SandboxManager

| 方法 | 说明 |
|------|------|
| `start()` / `shutdown(force)` | 管理器生命周期 |
| `create_sandbox(name, sandbox_id, mount_mode, runtime, image, allow_network, ...)` | 创建沙箱 |
| `get_or_create(sandbox_id)` | 获取或创建沙箱 |
| `get_sandbox(sandbox_id)` / `get_sandbox_by_name(name)` | 查询沙箱 |
| `list_sandboxes(status, backend_type)` / `list_running()` | 列表查询 |
| `stop_sandbox(sandbox_id)` / `restart_sandbox(sandbox_id)` / `destroy_sandbox(sandbox_id)` | 单沙箱控制 |
| `stop_all()` / `destroy_all()` / `health_check_all()` | 批量管理 |
