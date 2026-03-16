# Alphora Skills

**Agent Skills 标准兼容组件**

Skills 是 Alphora 框架的 Skill 管理组件，兼容 [agentskills.io](https://agentskills.io) 开放标准。支持 Skill 发现、加载、资源访问和 prompt 注入，可直接使用社区发布的 Skill。

## 特性

-  **标准兼容** — 遵循 agentskills.io 规范，社区 Skill 开箱即用
-  **路径自动检测** — 搜索目录和 skill 目录混传，自动识别
-  **一站式集成** — `setup_skills()` 一次调用完成工具 + prompt + sandbox 配置
- ️ **安全防护** — 路径遍历检测、文件大小限制（5MB）、输入校验
-  **灵活集成** — 独立使用 / SkillAgent / 自定义 Agent 三种模式
-  **Sandbox 支持** — 双向绑定自动路径映射，在沙箱中安全执行 Skill 脚本
-  **懒加载** — 发现阶段仅读取 YAML 元数据，指令内容按需加载，节省内存

## 目录

- [Skill 格式规范](#skill-格式规范)
- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [SkillManager 详解](#skillmanager-详解)
- [工具创建](#工具创建)
- [setup_skills 一站式集成](#setup_skills-一站式集成)
- [与 Agent 集成](#与-agent-集成)
- [Sandbox 集成](#sandbox-集成)
- [资源访问](#资源访问)
- [Prompt 生成](#prompt-生成)
- [校验与错误处理](#校验与错误处理)
- [高级用法](#高级用法)
- [架构总览](#架构总览)
- [API 参考](#api-参考)
- [常见问题](#常见问题)

---

## Skill 格式规范

遵循 [agentskills.io/specification](https://agentskills.io/specification)。

### 目录结构

```
my-skill/
├── SKILL.md          # 必需：YAML frontmatter + Markdown 指令
├── scripts/          # 可选：可执行脚本（Python / Shell 等）
│   ├── extract.py
│   └── validate.sh
├── references/       # 可选：参考文档（按需加载，LLM 可请求阅读）
│   ├── REFERENCE.md
│   └── FORMS.md
├── assets/           # 可选：模板、图片等静态资源
│   └── template.docx
└── LICENSE.txt       # 可选：许可证文件
```

### SKILL.md 格式

每个 Skill 目录必须包含一个 `SKILL.md` 文件，由 YAML frontmatter 和 Markdown 正文组成：

```markdown
---
name: pdf
description: >
  Use this skill whenever the user wants to do anything with PDF files.
  This includes reading, extracting, merging, splitting, and creating PDFs.
license: Apache-2.0
compatibility: Requires Python 3.9+, pypdf, pdfplumber
---

# PDF Processing Guide

## Overview

This guide covers essential PDF processing operations...

## Quick Start

(Markdown 正文：提供给 LLM 的详细操作指令)
```

#### Frontmatter 字段

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | ✅ | Skill 名称，kebab-case，须与目录名一致 |
| `description` | ✅ | 功能描述与触发条件（LLM 据此判断是否使用该 Skill） |
| `license` | ❌ | 许可证标识或文件引用 |
| `compatibility` | ❌ | 环境要求说明 |
| `metadata` | ❌ | 自定义键值对 |
| `allowed-tools` | ❌ | 预授权工具列表（实验性） |

#### 命名规则

- 1–64 个字符
- 仅小写字母、数字、连字符（`a-z`, `0-9`, `-`）
- 不以连字符开头或结尾
- 不包含连续连字符（`--`）
- 目录名须与 `name` 字段一致

#### 正文内容建议

- **面向 LLM 撰写**：用清晰的步骤和代码示例告诉 LLM 怎么做
- **建议不超过 500 行**：过长内容应拆分到 `references/` 目录
- **引用脚本和资源**：指明可用的脚本和参考文档位置

### 实际示例

以 `tutorials/skill_example/pdf/` 为例：

```
pdf/
├── SKILL.md                          # 元数据 + PDF 处理指南
├── LICENSE.txt
├── forms.md                          # 表单填写专项文档
├── reference.md                      # 高级参考文档
└── scripts/
    ├── check_fillable_fields.py      # 检查 PDF 可填字段
    ├── extract_form_structure.py     # 提取表单结构
    ├── fill_fillable_fields.py       # 填充表单字段
    ├── convert_pdf_to_images.py      # PDF 转图片
    └── ...
```

---

## 快速开始

### 加载单个 Skill（最简方式）

```python
from alphora.skills import load_skill

skill = load_skill("./skills/pdf")
print(skill.name)           # "pdf"
print(skill.description)    # "Use this skill whenever..."
print(skill.instructions)   # 完整 Markdown 正文
```

### 管理多个 Skill

```python
from alphora.skills import SkillManager

manager = SkillManager(["./skills"])
print(manager.skill_names)  # ["pdf", "data-analysis", ...]

skill = manager.load("pdf")
print(skill.instructions)
```

### 一站式 Agent 集成

```python
from alphora.skills import setup_skills

setup = setup_skills(paths=["./skills"], sandbox=sandbox)

# setup.tools             → 工具列表（含 sandbox 工具）
# setup.system_instruction → 可拼接到 system prompt 的指令
# setup.manager           → 底层 SkillManager 实例
```

---

## 核心概念

### Skill 对象

`Skill` 是 Skills 组件的核心数据模型，代表一个完整的 Skill：

```python
from alphora.skills import Skill

# Skill 对象在 discover 阶段被创建，此时仅包含元数据
skill = manager.get_skill("pdf")
print(skill.name)         # "pdf"
print(skill.description)  # 功能描述
print(skill.path)         # 目录绝对路径
print(skill.status)       # SkillStatus.DISCOVERED

# instructions 支持懒加载，首次访问时自动读取 SKILL.md
print(skill.is_loaded)    # False
print(skill.instructions) # 触发懒加载，返回 Markdown 正文
print(skill.is_loaded)    # True
```

#### 懒加载 vs 显式 load

- **懒加载**：通过 `skill.instructions` 属性访问时自动加载，不加入 manager 的追踪列表
- **显式 load**：通过 `manager.load("pdf")` 加载，加入追踪列表，可通过 `manager.loaded_skills` 查看

```python
# 懒加载方式
skill = manager.get_skill("pdf")
content = skill.instructions  # 自动加载
print(manager.loaded_skills)  # [] — 不追踪

# 显式 load 方式
skill = manager.load("pdf")
print(manager.loaded_skills)  # ["pdf"] — 追踪中
```

### Skill 生命周期

```
                  discover()        load()          unload()
  [搜索路径] ──────────→ DISCOVERED ──────→ LOADED ──────→ DISCOVERED
                              │                              ↑
                              │  skill.instructions          │
                              └── (懒加载，不改状态) ─────────┘
```

1. **Discovered**：仅加载 YAML 元数据（name, description 等），内存占用极小
2. **Loaded**：完整指令已加载到内存，可供 LLM 使用
3. **Unload**：释放指令缓存，回到 Discovered 状态

### SkillSetup 返回值

`setup_skills()` 返回 `SkillSetup` 对象：

```python
@dataclass
class SkillSetup:
    tools: List[Tool]           # 可直接注册到 ToolRegistry 的工具列表
    system_instruction: str     # 可拼接到 system prompt 的指令
    manager: SkillManager       # 底层 SkillManager 实例
```

---

## SkillManager 详解

`SkillManager` 是 Skills 组件的核心管理器，负责 Skill 的发现、加载、资源访问和 prompt 生成。

### 创建方式

```python
from alphora.skills import SkillManager

# 方式 1：传入路径列表（自动检测类型）
manager = SkillManager([
    "./skills",              # 搜索目录 → 扫描子目录
    "./my-custom-skill",     # skill 目录 → 直接注册（有 SKILL.md）
])

# 方式 2：分步创建
manager = SkillManager(auto_discover=False)
manager.add_path("./skills")          # 添加搜索路径
manager.add_skill_dir("./my-skill")   # 直接注册单个 skill
manager.discover()                     # 扫描搜索路径
```

#### 路径自动检测

构造函数的 `paths` 参数支持搜索目录和 skill 目录混传：

```python
# 传入的路径会自动检测：
# - 如果路径下直接有 SKILL.md → 视为 skill 目录，直接注册
# - 否则视为搜索目录，扫描其子目录（寻找含 SKILL.md 的子目录）
manager = SkillManager([
    "./skills",          # 搜索目录：扫描 skills/pdf/, skills/ocr/ 等
    "./extra/my-skill",  # skill 目录：直接注册 my-skill
])
```

### 发现与扫描

```python
# 扫描所有搜索路径
discovered = manager.discover()  # 返回 List[Skill]
print(f"发现 {len(discovered)} 个 skill")

# 查看发现错误
if manager.discovery_errors:
    for err in manager.discovery_errors:
        print(f"  解析失败: {err}")
```

扫描规则：
- 跳过以 `.`、`_`、`__` 开头的目录
- 跳过没有 `SKILL.md` 的目录
- 如果 `name` 与目录名不一致，发出警告
- 重复名称的 Skill 后者覆盖前者

### 加载与卸载

```python
# 加载（读取完整指令）
skill = manager.load("pdf")
print(skill.instructions)   # 完整 Markdown 正文
print(manager.loaded_skills) # ["pdf"]

# 卸载（释放内存）
manager.unload("pdf")
print(manager.loaded_skills) # []
```

### 缓存管理

```python
# 清缓存并重新发现（保留搜索路径）
manager.refresh()

# 清除所有状态（含搜索路径）
manager.clear()
```

### 基础查询

```python
# 获取单个 Skill（不存在返回 None）
skill = manager.get_skill("pdf")

# 所有已发现 Skill
print(manager.skill_names)       # ["pdf", "ocr"]
print(manager.skills)            # {"pdf": Skill(...), ...}

# 支持 Pythonic 用法
print(len(manager))              # 2
print("pdf" in manager)          # True
for skill in manager:
    print(skill.name)
```

---

## 工具创建

Skills 组件提供两种工具创建方式，生成的工具可直接注册到 `ToolRegistry`，通过 OpenAI Function Calling 协议暴露给 LLM。

### 标准模式

生成 3 个工具，LLM 通过工具调用来读取 Skill 内容和资源：

```python
from alphora.skills import create_skill_tools

tools = create_skill_tools(manager)
```

| 工具名 | 参数 | 说明 |
|--------|------|------|
| `read_skill` | `skill_name` | 加载 Skill 完整指令并返回 |
| `read_skill_resource` | `skill_name`, `resource_path` | 读取资源文件内容 |
| `list_skill_resources` | `skill_name` | 列出 Skill 目录结构 |

**典型的 LLM 交互流程**：

```
用户: "帮我提取 PDF 中的表格"

LLM → read_skill("pdf")                        ← 读取指令
LLM → read_skill_resource("pdf", "forms.md")   ← 按需读参考文档
LLM → run_shell_command("python /mnt/skills/pdf/scripts/extract.py ...")  ← 执行脚本
LLM → "提取完成，结果保存在 outputs/tables.xlsx"
```

### 文件系统模式

生成 2 个工具，返回路径让 LLM 通过 bash/shell 自行读取，适合有 shell 能力的 Agent：

```python
from alphora.skills import create_filesystem_skill_tools

tools = create_filesystem_skill_tools(manager)
```

| 工具名 | 参数 | 说明 |
|--------|------|------|
| `get_skill_path` | `skill_name` | 返回 SKILL.md 的绝对路径 |
| `get_skill_directory` | `skill_name` | 返回 Skill 目录的绝对路径 |

> 两种模式均支持**沙箱路径自动适配**：绑定 Sandbox 后，路径输出自动切换为 `/mnt/skills/...`。

### 注册到 ToolRegistry

```python
from alphora.tools import ToolRegistry

registry = ToolRegistry()
registry.register_many(tools)

# 获取 OpenAI Function Calling 格式的 schema
schema = registry.get_openai_tools_schema()
```

---

## setup_skills 一站式集成

`setup_skills()` 将 SkillManager 创建、工具生成、system prompt 生成、Sandbox 配置封装为一次调用：

```python
from alphora.skills import setup_skills

setup = setup_skills(
    paths=["./skills"],     # skill 搜索路径
    sandbox=sandbox,        # 可选：传入后自动配置路径映射 + 注册 SandboxTools
)

setup.tools                # List[Tool] — skill 工具 + sandbox 工具
setup.system_instruction   # str — 完整的系统指令
setup.manager              # SkillManager — 底层实例
```

### 完整参数

```python
setup = setup_skills(
    paths=["./skills"],             # 搜索路径列表
    skill_manager=None,             # 已有的 SkillManager（与 paths 二选一）
    sandbox=None,                   # Sandbox 实例
    filesystem_mode=False,          # True 时使用文件系统模式工具
    prompt_format="xml",            # 系统指令格式："xml" 或 "markdown"
    include_sandbox_tools=True,     # 是否自动注册 SandboxTools
)
```

### 使用已有 SkillManager

```python
manager = SkillManager(["./skills"])
# ... 自定义配置 ...

setup = setup_skills(skill_manager=manager, sandbox=sandbox)
print(setup.manager is manager)  # True — 使用同一个实例
```

### 不需要 Sandbox 工具

```python
# 只要 skill 工具，不注册 run_shell_command / save_file / list_files
setup = setup_skills(paths=["./skills"], sandbox=sandbox, include_sandbox_tools=False)
```

### 自动注册的 SandboxTools

当传入 `sandbox` 且 `include_sandbox_tools=True`（默认）时，以下工具自动加入 `setup.tools`：

| 工具名 | 说明 |
|--------|------|
| `run_shell_command` | 在沙箱中执行 shell 命令 |
| `save_file` | 向沙箱写入文件 |
| `list_files` | 列出沙箱目录文件 |

---

## 与 Agent 集成

Skills 组件提供三种集成层级，从快速上手到完全自定义。

### 方式 1：SkillAgent（开箱即用）

内置 ReAct 循环、SkillManager、工具注册的完整 Agent：

```python
from alphora.agent import SkillAgent
from alphora.models import OpenAILike
from alphora.sandbox import Sandbox

async with Sandbox(runtime="docker") as sandbox:
    agent = SkillAgent(
        llm=OpenAILike(),
        skill_paths=["./skills"],
        sandbox=sandbox,
        system_prompt="你是一个智能助手",
        max_iterations=30,
    )

    print(agent.skills)     # ["pdf", ...]
    print(agent.tools)      # [read_skill, ..., run_shell_command, ...]

    result = await agent.run("帮我提取这个 PDF 中的表格")
    print(result)
```

SkillAgent 特性：
- 自动调用 `setup_skills()` 完成所有配置
- 支持混合使用 `tools`（自定义工具）和 `skills`（Skill 目录）
- 动态添加 Skill：`agent.add_skill_path("./more-skills")`
- 逐步执行：`async for step in agent.run_steps(query):`
- Sandbox 自动启动：如果传入了 Sandbox 但未启动，会自动启动

### 方式 2：setup_skills + 自定义 Agent（推荐进阶）

基于 `BaseAgent` 开发自己的 Agent 时，用 `setup_skills()` 一站式接入：

```python
from alphora.agent import BaseAgent
from alphora.skills import setup_skills
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor

class MyAgent(BaseAgent):
    def __init__(self, llm, skill_paths, sandbox=None, tools=None, **kwargs):
        super().__init__(llm=llm, **kwargs)

        # 步骤 1: 一站式配置
        setup = setup_skills(paths=skill_paths, sandbox=sandbox)
        self._skill_manager = setup.manager

        # 步骤 2: 注册工具（自定义工具 + skill 工具 + sandbox 工具）
        self._registry = ToolRegistry()
        if tools:
            self._registry.register_many(tools)
        self._registry.register_many(setup.tools)
        self._executor = ToolExecutor(self._registry)

        # 步骤 3: 拼接 system prompt
        parts = ["你是一个 AI 助手。"]
        if setup.system_instruction:
            parts.append(setup.system_instruction)
        self._prompt = self.create_prompt(system_prompt="\n\n".join(parts))

    async def run(self, task: str) -> str:
        self.memory.add_user(content=task)
        tools_schema = self._registry.get_openai_tools_schema()

        for i in range(20):
            history = self.memory.build_history()
            response = await self._prompt.acall(
                query=task if i == 0 else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
            )
            self.memory.add_assistant(content=response)

            if not response.has_tool_calls:
                return response.content

            results = await self._executor.execute(response.tool_calls)
            self.memory.add_tool_result(result=results)

        return "达到最大迭代次数"
```

### 方式 3：手动组装（完全控制）

不使用 `setup_skills()`，手动管理各组件：

```python
from alphora.agent import ReActAgent
from alphora.skills import SkillManager, create_skill_tools

manager = SkillManager(["./skills"])
skill_tools = create_skill_tools(manager)

agent = ReActAgent(
    llm=llm,
    tools=[*my_tools, *skill_tools],
    system_prompt=f"你是一个助手。\n\n{manager.to_system_prompt()}",
)
```

---

## Sandbox 集成

Skills 与 Sandbox 通过**双向绑定**自动协作：
- **Sandbox → Skills**：Skills 文件被挂载到沙箱的 `/mnt/skills` 路径
- **Skills → Sandbox**：SkillManager 自动将所有路径输出切换为沙箱内路径

### 自动集成（推荐）

通过 `setup_skills()` 传入 `sandbox` 参数，一切自动完成：

```python
from alphora.sandbox import Sandbox
from alphora.skills import setup_skills

async with Sandbox(runtime="docker") as sandbox:
    setup = setup_skills(paths=["./skills"], sandbox=sandbox)
    # 内部自动完成：
    #   1. sandbox.mount_skill(manager) — 技能目录挂载到沙箱
    #   2. manager.sandbox_skill_root = "/mnt/skills" — 路径自动适配
    #   3. SandboxTools（run_shell_command 等）注册到 setup.tools

    print(setup.manager.resolve_skill_path("pdf"))  # /mnt/skills/pdf
    print(sandbox.skill_host_path)                    # /host/.../skills
```

### 手动绑定

`sandbox.mount_skill()` 是多态方法，接受路径或 SkillManager：

```python
from alphora.sandbox import Sandbox
from alphora.skills import SkillManager

manager = SkillManager(["./skills"])
sandbox = Sandbox(runtime="docker")

# 传入 SkillManager — 双向绑定
sandbox.mount_skill(manager)
print(sandbox.skill_host_path)        # /host/.../skills（自动推断）
print(manager.sandbox_skill_root)     # /mnt/skills（自动设置）

# 也能传路径 — 仅挂载，不绑定 manager
sandbox.mount_skill("./skills")
```

### 路径自动适配

绑定后，SkillManager 的**所有**路径输出自动使用沙箱路径：

```python
# 无沙箱时
manager.resolve_skill_path("pdf")       # /host/.../skills/pdf
manager.resolve_skill_md_path("pdf")    # /host/.../skills/pdf/SKILL.md
manager.get_script_path("pdf", "x.py")  # /host/.../skills/pdf/scripts/x.py

# 绑定沙箱后
manager.resolve_skill_path("pdf")       # /mnt/skills/pdf
manager.resolve_skill_md_path("pdf")    # /mnt/skills/pdf/SKILL.md
manager.get_script_path("pdf", "x.py")  # /mnt/skills/pdf/scripts/x.py
```

同样，`create_filesystem_skill_tools` 生成的工具也会返回沙箱路径，以及 `to_prompt()` 生成的清单中 `<location>` 也会使用沙箱路径。

### 时序无关

`mount_skill()` 在 Sandbox 启动前后均可调用：

```python
# 先启动再挂载 — 动态挂载到运行中的容器
async with Sandbox(runtime="docker") as sandbox:
    sandbox.mount_skill(manager)

# 先挂载再启动 — start() 时自动带上 Docker volume
sandbox = Sandbox(runtime="docker")
sandbox.mount_skill(manager)
await sandbox.start()   # 容器创建时已包含 skills volume
```

### 沙箱内目录结构

```
/mnt/workspace/          ← 工作目录（cwd）
├── uploads/             ← 用户上传的文件
├── outputs/             ← 最终输出文件
└── skills/              ← 符号链接 → /mnt/skills
/mnt/skills/             ← skill 文件（只读）
├── pdf/
│   ├── SKILL.md
│   ├── scripts/
│   └── ...
└── ocr/
    └── ...
```

---

## 资源访问

### 读取资源文件

```python
ref = manager.read_resource("pdf", "references/FORMS.md")
print(ref.content)         # 文件内容
print(ref.resource_type)   # "reference"
print(ref.filename)        # "FORMS.md"
```

`resource_type` 根据路径前缀自动判定：
- `scripts/` → `"script"`
- `references/` → `"reference"`
- `assets/` → `"asset"`
- 其他 → `"other"`

### 列出资源目录

```python
info = manager.list_resources("pdf")
print(info.scripts)        # ["check_fillable_fields.py", "extract.py", ...]
print(info.references)     # ["FORMS.md", "REFERENCE.md"]
print(info.assets)         # []

# 格式化展示
print(info.to_display())
# pdf/
#   └── SKILL.md
#   └── scripts/
#       └── check_fillable_fields.py
#       └── extract.py
#   └── references/
#       └── FORMS.md
```

### 获取脚本路径

```python
path = manager.get_script_path("pdf", "extract.py")
print(path)  # /mnt/skills/pdf/scripts/extract.py（沙箱环境下）
             # /host/.../pdf/scripts/extract.py  （无沙箱时）

# 自动补全 scripts/ 前缀
path = manager.get_script_path("pdf", "extract.py")
# 等效于
path = manager.get_script_path("pdf", "scripts/extract.py")
```

### 安全特性

```python
# 路径遍历攻击会被拦截
manager.read_resource("pdf", "../../etc/passwd")
# SkillResourceError: Path traversal detected

# 超大文件会被拦截（默认 5MB 限制）
manager.read_resource("pdf", "assets/huge_file.bin")
# SkillResourceError: Resource is too large (12.3 MB, max 5 MB)

# 非 UTF-8 文件会被拦截
manager.read_resource("pdf", "assets/image.png")
# SkillResourceError: Resource is not valid UTF-8 text
```

---

## Prompt 生成

SkillManager 提供两级 prompt 生成。

### Skill 清单（to_prompt）

仅生成 Skill 列表，供拼接到自定义 prompt 中：

```python
# XML 格式（默认，推荐）
prompt = manager.to_prompt(format="xml")
```

输出：

```xml
<available_skills>
<skill>
<name>pdf</name>
<description>Use this skill whenever the user wants to...</description>
<location>/mnt/skills/pdf/SKILL.md</location>
</skill>
</available_skills>
```

```python
# Markdown 格式
prompt = manager.to_prompt(format="markdown")
```

输出：

```markdown
## Available Skills

- **pdf**: Use this skill whenever the user wants to...
  Location: `/mnt/skills/pdf/SKILL.md`
```

### 完整系统指令（to_system_prompt）

包含使用说明 + Skill 清单，可直接拼接到 system prompt 末尾：

```python
instruction = manager.to_system_prompt(format="xml")
```

输出包含：
1. 使用说明（告诉 LLM 如何使用 `read_skill` 等工具）
2. 完整的 Skill 清单

```python
# 典型用法：拼接到自定义 prompt
system_prompt = f"""你是一个智能助手。

{manager.to_system_prompt()}"""
```

---

## 校验与错误处理

### Skill 校验

```python
# 校验单个 Skill（返回违规列表，空 = 通过）
issues = manager.validate("pdf")
if not issues:
    print("PASS")

# 校验所有 Skill（返回 {name: [violations]}）
results = manager.validate_all()
for name, violations in results.items():
    print(f"{name}: {violations}")
```

校验规则：
- `name` 格式符合 kebab-case
- `name` 与目录名一致
- `description` 不为空且不超过 1024 字符
- 指令正文不超过 500 行（建议）

### 异常体系

所有异常继承自 `SkillError`，可统一捕获：

```python
from alphora.skills import SkillError, SkillNotFoundError, SkillLoadError

try:
    manager.load("nonexistent")
except SkillNotFoundError as e:
    print(e)
    # Skill 'nonexistent' not found. Did you mean: pdf?
except SkillError as e:
    print(f"其他 Skill 错误: {e}")
```

| 异常 | 触发场景 |
|------|----------|
| `SkillError` | 基础异常，所有 Skill 异常的父类 |
| `SkillParseError` | SKILL.md 解析失败（YAML 格式错误、缺少必需字段等） |
| `SkillValidationError` | Skill 格式校验不通过 |
| `SkillNotFoundError` | 指定名称的 Skill 不存在（含相似名称建议） |
| `SkillLoadError` | Skill 内容加载失败（文件损坏、权限不足等） |
| `SkillResourceError` | 资源文件访问失败（路径遍历检测、文件过大等） |

---

## 高级用法

### 动态 Skill 注册

运行时动态添加 Skill：

```python
# 添加搜索路径并重新扫描
manager.add_path("./more-skills")
manager.discover()

# 直接注册单个 Skill 目录
skill = manager.add_skill_dir("/path/to/my-skill")

# 对于 SkillAgent，可以链式调用
agent.add_skill_path("./more-skills")
agent.add_skill("./standalone-skill")
```

### Filesystem 模式

适用于有 bash/shell 能力的 Agent，提供路径而不是内容：

```python
setup = setup_skills(paths=["./skills"], sandbox=sandbox, filesystem_mode=True)
# tools: [get_skill_path, get_skill_directory, run_shell_command, save_file, list_files]

# LLM 拿到路径后自行读取：
#   get_skill_path("pdf") → "/mnt/skills/pdf/SKILL.md"
#   run_shell_command("cat /mnt/skills/pdf/SKILL.md")
```

### 多搜索路径

```python
manager = SkillManager([
    "./project-skills",      # 项目内 Skill
    "~/.alphora/skills",     # 全局 Skill
    "./community-skills",    # 社区 Skill
])
```

> 当使用 Sandbox 且有多个搜索路径时，仅第一个路径会被挂载（Sandbox 仅支持一个 skill mount point）。系统会发出警告。

### 直接使用解析器

```python
from alphora.skills.parser import parse_frontmatter, parse_properties, validate_skill

# 解析 SKILL.md 的 frontmatter 和正文
fm, body = parse_frontmatter(open("SKILL.md").read())

# 解析为 Skill 对象
skill = parse_properties(Path("./pdf"))

# 校验 Skill 目录
violations = validate_skill(Path("./pdf"))
```

---

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                     开发者接口                            │
├─────────────┬─────────────────┬─────────────────────────┤
│ load_skill()│  setup_skills() │     SkillManager        │
│  极简入口    │  一站式集成       │      核心管理器          │
├─────────────┴────────┬────────┴─────────────────────────┤
│                      │                                   │
│         ┌────────────┴────────────┐                      │
│         │     Tool Creation       │                      │
│         ├─────────────────────────┤                      │
│         │ create_skill_tools()    │ → read_skill         │
│         │                         │   read_skill_resource│
│         │                         │   list_skill_resources│
│         ├─────────────────────────┤                      │
│         │ create_filesystem_      │ → get_skill_path     │
│         │  skill_tools()          │   get_skill_directory │
│         └─────────────────────────┘                      │
│                                                          │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────────┐ │
│  │   Skill   │  │  parser   │  │     Sandbox 集成      │ │
│  │  数据模型  │  │ SKILL.md  │  │ mount_skill()        │ │
│  │ 懒加载指令 │  │ 解析/校验  │  │ 双向路径绑定          │ │
│  └───────────┘  └───────────┘  └──────────────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │              exceptions（异常体系）                    ││
│  │ SkillError → Parse / NotFound / Load / Resource      ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 模块结构

```
alphora/skills/
├── __init__.py       # 公共 API 导出
├── models.py         # Skill, SkillResource, SkillDirectoryInfo, SkillStatus
├── manager.py        # SkillManager 核心管理器
├── parser.py         # SKILL.md 解析器（frontmatter + 正文）
├── tools.py          # 工具创建（标准模式 + 文件系统模式）
├── setup.py          # setup_skills(), load_skill(), SkillSetup
└── exceptions.py     # 异常层级
```

---

## API 参考

### 便捷函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `load_skill` | `(path) → Skill` | 加载单个 Skill 的极简入口 |
| `setup_skills` | `(paths, skill_manager, sandbox, ...) → SkillSetup` | 一站式配置 |
| `create_skill_tools` | `(manager) → List[Tool]` | 创建标准模式工具集 |
| `create_filesystem_skill_tools` | `(manager) → List[Tool]` | 创建文件系统模式工具集 |

### SkillManager 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `paths` | `List[str\|Path]` | `None` | 路径列表（搜索目录或 skill 目录，自动检测） |
| `auto_discover` | `bool` | `True` | 初始化时是否自动执行 `discover()` |
| `sandbox_skill_root` | `str` | `None` | 沙箱内 skill 根路径（通常由 `mount_skill` 自动设置） |

### SkillManager 方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `add_path` | `(path) → self` | 添加搜索路径（支持链式调用） |
| `add_skill_dir` | `(dir) → Skill` | 直接注册 Skill 目录 |
| `discover` | `() → List[Skill]` | 扫描所有搜索路径 |
| `load` | `(name) → Skill` | 加载 Skill 完整内容，加入追踪列表 |
| `unload` | `(name) → None` | 卸载 Skill，释放缓存 |
| `get_skill` | `(name) → Skill\|None` | 获取 Skill 对象 |
| `read_resource` | `(name, path) → SkillResource` | 读取资源文件 |
| `list_resources` | `(name) → SkillDirectoryInfo` | 列出资源目录 |
| `get_script_path` | `(name, script) → Path` | 获取脚本路径（沙箱感知） |
| `resolve_skill_path` | `(name) → Path` | 获取 Skill 目录路径（沙箱感知） |
| `resolve_skill_md_path` | `(name) → Path` | 获取 SKILL.md 路径（沙箱感知） |
| `to_prompt` | `(format) → str` | 生成 Skill 清单 prompt |
| `to_system_prompt` | `(format) → str` | 生成完整系统指令 |
| `validate` | `(name) → List[str]` | 校验指定 Skill |
| `validate_all` | `() → Dict[str, List[str]]` | 校验所有 Skill |
| `refresh` | `() → List[Skill]` | 清缓存并重新发现 |
| `clear` | `() → None` | 清除所有状态 |

### SkillManager 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `skills` | `Dict[str, Skill]` | 所有已发现的 Skill |
| `skill_names` | `List[str]` | Skill 名称列表 |
| `loaded_skills` | `List[str]` | 已加载（追踪中）的 Skill 列表 |
| `search_paths` | `List[Path]` | 搜索路径列表 |
| `discovery_errors` | `List[str]` | 最近一次发现的错误 |
| `sandbox_skill_root` | `Optional[str]` | 沙箱内 skill 根路径（绑定后自动设置） |

### Skill 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | Skill 名称 |
| `description` | `str` | 功能描述 |
| `license` | `Optional[str]` | 许可证 |
| `compatibility` | `Optional[str]` | 环境要求 |
| `metadata` | `Optional[Dict]` | 自定义元数据 |
| `allowed_tools` | `Optional[List[str]]` | 预授权工具（实验性） |
| `path` | `Path` | 目录绝对路径 |
| `status` | `SkillStatus` | 生命周期状态 |
| `instructions` | `str` | Markdown 正文指令（懒加载） |
| `raw_content` | `str` | SKILL.md 完整原始内容（懒加载） |
| `is_loaded` | `bool` | 指令是否已加载 |
| `skill_md_path` | `Path` | SKILL.md 文件路径 |
| `scripts_dir` | `Path` | scripts/ 目录路径 |
| `references_dir` | `Path` | references/ 目录路径 |
| `assets_dir` | `Path` | assets/ 目录路径 |

### SkillResource 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `skill_name` | `str` | 所属 Skill 名称 |
| `relative_path` | `str` | 相对路径 |
| `content` | `str` | 文件文本内容 |
| `resource_type` | `str` | 类型（script / reference / asset / other） |
| `filename` | `str` | 文件名 |

### SkillDirectoryInfo 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `skill_name` | `str` | Skill 名称 |
| `files` | `List[str]` | 顶层文件 |
| `scripts` | `List[str]` | 脚本文件 |
| `references` | `List[str]` | 参考文档 |
| `assets` | `List[str]` | 静态资源 |

### 异常

| 异常 | 父类 | 说明 |
|------|------|------|
| `SkillError` | `Exception` | 基础异常 |
| `SkillParseError` | `SkillError` | SKILL.md 解析失败 |
| `SkillValidationError` | `SkillError` | 格式校验不通过 |
| `SkillNotFoundError` | `SkillError` | Skill 不存在（含相似名建议） |
| `SkillLoadError` | `SkillError` | 加载失败 |
| `SkillResourceError` | `SkillError` | 资源访问失败 |

---

## 常见问题

### Skill 目录下没有 SKILL.md 怎么办？

```
SKILL.md 是 agentskills.io 标准规范的必需文件。
没有 SKILL.md 的目录会在扫描时被跳过。
```

### name 和目录名不一致会怎样？

```
系统会发出警告，但仍能正常使用。
推荐始终保持 name 字段与目录名一致，以符合 agentskills.io 规范。
```

### 多个搜索路径有同名 Skill 怎么办？

```
后发现的会覆盖先发现的，并发出警告日志。
建议避免同名 Skill，或改用 add_skill_dir() 精确注册。
```

### Sandbox 模式下 Skill 脚本如何执行？

```python
# LLM 通过 run_shell_command 执行脚本
# 路径已自动适配为沙箱内路径
result = await sbt.run_shell_command(
    "python /mnt/skills/pdf/scripts/extract.py input.pdf"
)
```

### 如何编写高质量的 SKILL.md？

1. **description 要精准**：这是 LLM 决定是否使用该 Skill 的依据
2. **正文提供清晰步骤**：用编号步骤和代码示例
3. **引用外部资源**：大量内容放 `references/`，正文指明位置
4. **提供可用脚本清单**：列出 `scripts/` 下的工具及用法
5. **保持合理长度**：建议 500 行以内

### setup_skills 和手动配置有什么区别？

```python
# setup_skills 等效于以下手动操作：
manager = SkillManager(paths=["./skills"], auto_discover=True)
sandbox.mount_skill(manager)                   # Sandbox 双向绑定
tools = create_skill_tools(manager)            # 创建 skill 工具
sbt = SandboxTools(sandbox)
tools += [Tool.from_function(m) for m in       # 追加 sandbox 工具
          [sbt.run_shell_command, sbt.save_file, sbt.list_files]]
instruction = manager.to_system_prompt()       # 生成系统指令
```
