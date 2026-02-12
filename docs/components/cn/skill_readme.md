# Alphora Skills

**Agent Skills 标准兼容组件**

Skills 是 Alphora 框架的 Skill 管理组件，完全兼容 [agentskills.io](https://agentskills.io) 开放标准。实现了渐进式披露（Progressive Disclosure）模式，支持 Skill 发现、激活、资源访问和 prompt 注入，可直接使用 Anthropic、OpenAI、GitHub Copilot 等平台发布的社区 Skill。

## 特性

-  **标准兼容** - 完全遵循 agentskills.io 规范，社区 Skill 开箱即用
-  **渐进式披露** - 三阶段加载（元数据 → 指令 → 资源），高效管理 Token 预算
-  **开发者友好** - 简洁 API，链式调用，丰富类型提示，详细错误提示
- ️ **安全防护** - 路径遍历检测、文件大小限制、输入校验
-  **灵活集成** - 独立使用或与 SkillAgent / ReActAgent 无缝配合
-  **双模式** - 支持 Tool 模式和 Filesystem 模式两种集成方式
-  **Sandbox 支持** - 可在沙箱中安全执行 Skill 脚本

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.skills import SkillManager

# 创建管理器，自动发现 Skill
manager = SkillManager(["./skills"])

# 查看已发现的 Skill
for skill in manager:
    print(f"{skill.name}: {skill.description}")

# 生成 system prompt 注入内容
prompt = manager.to_prompt()

# 激活并加载完整指令
content = manager.activate("pdf-processing")
print(content.instructions)
```

## 目录

- [Skill 格式规范](#skill-格式规范)
- [基础用法](#基础用法)
- [与 Agent 集成](#与-agent-集成)
- [渐进式披露](#渐进式披露)
- [资源访问](#资源访问)
- [Prompt 生成](#prompt-生成)
- [Skill 校验](#skill-校验)
- [高级用法](#高级用法)
- [API 参考](#api-参考)

---

## Skill 格式规范

遵循 [agentskills.io/specification](https://agentskills.io/specification)。

### 目录结构

```
my-skill/
├── SKILL.md          # 必需：元数据 + 指令
├── scripts/          # 可选：可执行脚本
│   ├── extract.py
│   └── validate.sh
├── references/       # 可选：参考文档（按需加载）
│   ├── REFERENCE.md
│   └── FORMS.md
└── assets/           # 可选：模板、图片等静态资源
    └── template.docx
```

### SKILL.md 格式

```markdown
---
name: pdf-processing
description: Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF documents.
license: Apache-2.0
metadata:
  author: my-team
  version: "1.0"
---

# PDF Processing

## 使用步骤

1. 读取用户提供的 PDF 文件
2. 根据任务类型选择处理方式
3. 使用 scripts/extract.py 提取内容

## 脚本说明

- `scripts/extract.py`: 提取 PDF 文本和表格
- `scripts/merge.py`: 合并多个 PDF

## 注意事项

- 扫描件需要 OCR 处理
- 表格提取可能需要调整参数
```

### 命名规则

- 1-64 字符
- 仅小写字母、数字、连字符（`a-z`, `0-9`, `-`）
- 不以连字符开头或结尾
- 不包含连续连字符
- 目录名须与 `name` 字段一致

---

## 基础用法

### 创建 SkillManager

```python
from alphora.skills import SkillManager

# 方式 1：传入搜索路径（自动发现）
manager = SkillManager(["./skills", "~/.alphora/skills"])

# 方式 2：手动添加路径
manager = SkillManager()
manager.add_path("./skills")
manager.add_path("/shared/team-skills")

# 方式 3：直接注册单个 Skill
manager = SkillManager()
manager.add_skill_dir("./my-custom-skill")
```

### 发现 Skill

```python
# 自动发现（默认行为）
skills = manager.discover()
print(f"发现 {len(skills)} 个 Skill")

# 查看所有 Skill 名称
print(manager.skill_names)  # ['pdf-processing', 'data-analysis', ...]

# 查看具体 Skill 信息
skill = manager.get_skill("pdf-processing")
print(skill.name)         # "pdf-processing"
print(skill.description)  # "Extract text and tables from PDF files..."
print(skill.path)         # PosixPath('/path/to/skills/pdf-processing')

# 遍历
for skill in manager:
    print(f"  {skill.name}: {skill.description}")

# 检查是否存在
if "pdf-processing" in manager:
    print("PDF skill is available!")
```

### 激活 Skill

```python
# 激活（加载完整指令内容）
content = manager.activate("pdf-processing")

print(content.name)          # "pdf-processing"
print(content.instructions)  # Markdown 正文内容
print(content.properties)    # 完整元数据

# 查看已激活的 Skill
print(manager.activated_skills)  # ['pdf-processing']

# 反激活（释放内容缓存）
manager.deactivate("pdf-processing")
```

### 刷新与清理

```python
# 刷新：清除缓存并重新发现
manager.refresh()

# 完全清理
manager.clear()
```

---

## 与 Agent 集成

### 方式 1：使用 SkillAgent（推荐）

最简单的方式，SkillAgent 自动处理 Skill 发现、注入和工具注册：

```python
from alphora.agent import SkillAgent
from alphora.models import OpenAILike

agent = SkillAgent(
    llm=OpenAILike(model_name="gpt-4"),
    skill_paths=["./skills"],
    system_prompt="你是一个智能助手",
)

response = await agent.run("帮我处理这个 PDF 文件")
```

#### 带额外工具

```python
from alphora.tools.decorators import tool

@tool
def get_weather(city: str) -> str:
    """获取天气信息"""
    return f"{city}: 晴, 25°C"

agent = SkillAgent(
    llm=llm,
    skill_paths=["./skills"],
    tools=[get_weather],  # Skills 内置工具 + 自定义工具混合使用
)
```

#### 带 Sandbox

```python
from alphora.sandbox import Sandbox

async with Sandbox(runtime="local") as sandbox:
    agent = SkillAgent(
        llm=llm,
        skill_paths=["./skills"],
        sandbox=sandbox,  # 可执行 Skill 脚本
        system_prompt="你是一个数据分析助手",
    )
    response = await agent.run("用 Python 分析数据")
```

#### 动态管理 Skill

```python
agent = SkillAgent(llm=llm, skill_paths=["./skills"])

# 动态添加 Skill 路径
agent.add_skill_path("/new/skills/directory")

# 动态注册单个 Skill
agent.add_skill("./my-custom-skill")

# 查看当前 Skill
print(agent.skills)
```

### 方式 2：与 ReActAgent 配合

如果已有 ReActAgent，可以通过 SkillManager 提供 Skill 能力：

```python
from alphora.agent import ReActAgent
from alphora.skills import SkillManager, create_skill_tools

# 创建 SkillManager
manager = SkillManager(["./skills"])

# 生成 Skill 交互工具
skill_tools = create_skill_tools(manager)

# 传给 ReActAgent
agent = ReActAgent(
    llm=llm,
    tools=[*my_tools, *skill_tools],  # 混合使用
    system_prompt=f"你是一个助手。\n\n{manager.to_system_instruction()}",
)

response = await agent.run("处理 PDF 文件")
```

### 方式 3：独立使用（自定义 Agent）

完全手动控制 Skill 的使用方式：

```python
from alphora.agent import BaseAgent
from alphora.skills import SkillManager

class MyAgent(BaseAgent):
    def __init__(self, skill_paths, **kwargs):
        super().__init__(**kwargs)
        self.skill_manager = SkillManager(skill_paths)

    async def run(self, query: str):
        # 1. 将 Skill 清单注入 prompt
        prompt = self.create_prompt(
            system_prompt=f"你是助手。\n{self.skill_manager.to_prompt()}",
            user_prompt="{{query}}"
        )

        # 2. 让 LLM 决定使用哪个 Skill
        response = await prompt.acall(query=query)

        # 3. 根据 LLM 输出手动激活 Skill
        if "pdf-processing" in response:
            content = self.skill_manager.activate("pdf-processing")
            # 将 Skill 指令作为 runtime_system_prompt 注入后续对话
            final = await prompt.acall(
                query="请按照指令处理",
                runtime_system_prompt=content.instructions,
            )
            return final

        return response
```

### 方式 4：通过 derive 共享 SkillManager

```python
# 主智能体
main = SkillAgent(llm=llm, skill_paths=["./skills"])

# 派生子智能体，共享 LLM 和 Memory
from alphora.agent import ReActAgent
from alphora.skills import create_skill_tools

sub = main.derive(ReActAgent, tools=create_skill_tools(main.skill_manager))
```

---

## 渐进式披露

Skills 组件严格遵循三阶段渐进式披露模式，最大化 Token 效率：

### Phase 1: Discovery（~100 tokens/skill）

启动时仅加载 YAML frontmatter 中的 name 和 description。

```python
manager = SkillManager(["./skills"])  # 自动执行 Phase 1
# 此时每个 Skill 仅占用约 50-100 tokens 的 system prompt 空间
```

### Phase 2: Activation（< 5000 tokens 建议）

当 LLM 决定使用某个 Skill 时，加载完整 SKILL.md 内容。

```python
content = manager.activate("pdf-processing")
# 完整指令内容现在可用
print(f"~{len(content.instructions) // 4} tokens")
```

### Phase 3: Resources（按需加载）

仅在 Skill 指令引用了特定资源文件时才加载。

```python
# 按需读取参考文档
ref = manager.read_resource("pdf-processing", "references/FORMS.md")

# 按需读取脚本
script = manager.read_resource("pdf-processing", "scripts/extract.py")
```

### Token 预算示意

```
100 个 Skill：Phase 1 ≈ 5,000 - 10,000 tokens（始终加载）
激活 1 个 Skill：Phase 2 ≈ 2,000 - 5,000 tokens（按需加载）
读取 1 个资源：Phase 3 ≈ 视文件大小而定（按需加载）
```

---

## 资源访问

### 读取资源文件

```python
# 读取参考文档
ref = manager.read_resource("pdf-processing", "references/FORMS.md")
print(ref.content)          # 文件内容
print(ref.resource_type)    # "reference"
print(ref.relative_path)    # "references/FORMS.md"

# 读取脚本源码
script = manager.read_resource("pdf-processing", "scripts/extract.py")
print(script.resource_type) # "script"

# 读取资源
asset = manager.read_resource("pdf-processing", "assets/template.docx")
```

### 列出资源目录

```python
info = manager.list_resources("pdf-processing")
print(info.scripts)     # ['extract.py', 'merge.py']
print(info.references)  # ['FORMS.md', 'REFERENCE.md']
print(info.assets)      # ['template.docx']

# 格式化展示
print(info.to_display())
# 📁 pdf-processing/
#   └── SKILL.md
#   └── scripts/
#       └── extract.py
#       └── merge.py
#   └── references/
#       └── FORMS.md
```

### 获取脚本路径

```python
# 获取脚本绝对路径（用于沙箱执行）
path = manager.get_script_path("pdf-processing", "extract.py")
# 自动补全 scripts/ 前缀
print(path)  # PosixPath('/path/to/skills/pdf-processing/scripts/extract.py')
```

### 安全特性

```python
# 路径遍历攻击会被拦截
manager.read_resource("my-skill", "../../etc/passwd")
# SkillResourceError: Path traversal detected

# 超大文件会被拦截（默认 5MB 限制）
manager.read_resource("my-skill", "assets/huge_file.bin")
# SkillResourceError: Resource is too large
```

---

## Prompt 生成

### XML 格式（默认，推荐）

```python
prompt = manager.to_prompt()  # 或 to_prompt(format="xml")
```

输出：

```xml
<available_skills>
<skill>
<n>pdf-processing</n>
<description>Extract text and tables from PDF files...</description>
<location>/path/to/skills/pdf-processing/SKILL.md</location>
</skill>
<skill>
<n>data-analysis</n>
<description>Analyze datasets and generate reports...</description>
<location>/path/to/skills/data-analysis/SKILL.md</location>
</skill>
</available_skills>
```

### Markdown 格式

```python
prompt = manager.to_prompt(format="markdown")
```

### 完整系统指令

```python
# 包含使用说明 + Skill 清单
instruction = manager.to_system_instruction()
# "You have access to a set of specialized skills..."
```

---

## Skill 校验

### 校验单个 Skill

```python
issues = manager.validate("my-skill")
if issues:
    for issue in issues:
        print(f"  ⚠ {issue}")
else:
    print("✓ Skill is valid")
```

### 校验所有 Skill

```python
results = manager.validate_all()
for name, issues in results.items():
    print(f"\n{name}:")
    for issue in issues:
        print(f"  ⚠ {issue}")
```

### 独立校验（无需 SkillManager）

```python
from alphora.skills import validate_skill

issues = validate_skill("./my-skill")
```

### 校验规则

| 规则 | 说明 |
|------|------|
| SKILL.md 存在 | 必需文件 |
| name 格式 | kebab-case，1-64字符 |
| name 匹配目录名 | name 须与父目录名一致 |
| description 非空 | 1-1024字符 |
| compatibility 长度 | ≤ 500字符 |
| 指令行数 | 建议 < 500 行 |

---

## 高级用法

### 自定义 Skill 搜索路径策略

```python
import os

# 从环境变量读取
paths = os.environ.get("ALPHORA_SKILL_PATHS", "").split(":")
manager = SkillManager(paths)

# 多层级搜索
manager = SkillManager([
    "./skills",              # 项目级
    "~/.alphora/skills",     # 用户级
    "/etc/alphora/skills",   # 系统级
])
```

### Filesystem 模式

适用于 Agent 有 bash 能力的场景（如 Claude Code）：

```python
from alphora.skills import SkillManager, create_filesystem_skill_tools

manager = SkillManager(["./skills"])
tools = create_filesystem_skill_tools(manager)

# 工具提供路径，LLM 通过 cat/bash 自行读取文件
# 而不是通过工具返回文件内容
```

### 动态 Skill 注册

```python
# 运行时添加 Skill
manager.add_skill_dir("/dynamic/new-skill")

# 重新发现（如磁盘上的 Skill 有变化）
manager.refresh()
```

### 解析器直接使用

```python
from alphora.skills import parse_frontmatter, parse_properties, parse_content

# 解析字符串
frontmatter, body = parse_frontmatter("""---
name: my-skill
description: A test skill
---
# Instructions here
""")

# 解析目录
props = parse_properties(Path("./my-skill"))
content = parse_content(Path("./my-skill"))
```

---

## API 参考

### SkillManager

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skill_paths` | `List[str\|Path]` | `None` | Skill 目录搜索路径 |
| `auto_discover` | `bool` | `True` | 初始化时自动执行 discover() |

#### 方法

| 方法 | 说明 |
|------|------|
| `add_path(path)` | 添加搜索路径（链式调用） |
| `add_skill_dir(skill_dir)` | 直接注册单个 Skill 目录 |
| `discover()` | 扫描搜索路径，发现所有 Skill |
| `activate(name)` | 激活 Skill，加载完整内容 |
| `deactivate(name)` | 反激活 Skill，释放缓存 |
| `read_resource(name, path)` | 读取资源文件 |
| `list_resources(name)` | 列出资源目录 |
| `get_script_path(name, script)` | 获取脚本绝对路径 |
| `to_prompt(format)` | 生成 Skill 清单 prompt |
| `to_system_instruction(format)` | 生成完整系统指令 |
| `get_skill(name)` | 获取 Skill 元数据 |
| `validate(name)` | 校验指定 Skill |
| `validate_all()` | 校验所有 Skill |
| `refresh()` | 清缓存并重新发现 |
| `clear()` | 清除所有状态 |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `skills` | `Dict[str, SkillProperties]` | 所有已发现的 Skill |
| `skill_names` | `List[str]` | Skill 名称列表 |
| `activated_skills` | `List[str]` | 已激活的 Skill 列表 |
| `search_paths` | `List[Path]` | 搜索路径列表 |
| `discovery_errors` | `List[str]` | 发现过程中的错误 |

### SkillAgent

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm` | `OpenAILike` | 必填 | LLM 实例 |
| `skill_paths` | `List[str\|Path]` | `None` | Skill 搜索路径 |
| `skill_manager` | `SkillManager` | `None` | 已有的 SkillManager |
| `tools` | `List[Tool\|Callable]` | `None` | 额外的工具列表 |
| `system_prompt` | `str` | `""` | 系统提示词 |
| `max_iterations` | `int` | `100` | 最大迭代次数 |
| `sandbox` | `Sandbox` | `None` | 沙箱实例 |
| `filesystem_mode` | `bool` | `False` | 文件系统模式 |

#### 方法

| 方法 | 说明 |
|------|------|
| `run(query)` | 执行完整循环 |
| `run_steps(query)` | 逐步执行，yield 每步结果 |
| `add_skill_path(path)` | 动态添加 Skill 路径 |
| `add_skill(skill_dir)` | 动态注册 Skill |

### SkillProperties

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | Skill 名称 |
| `description` | `str` | Skill 描述 |
| `license` | `str?` | 许可证 |
| `compatibility` | `str?` | 环境要求 |
| `metadata` | `Dict?` | 自定义元数据 |
| `allowed_tools` | `List[str]?` | 预授权工具 |
| `path` | `Path` | 目录绝对路径 |
| `skill_md_path` | `Path` | SKILL.md 路径 |

### SkillContent

| 属性 | 类型 | 说明 |
|------|------|------|
| `properties` | `SkillProperties` | 元数据 |
| `instructions` | `str` | Markdown 正文指令 |
| `raw_content` | `str` | 原始完整内容 |

### 工具创建函数

| 函数 | 说明 |
|------|------|
| `create_skill_tools(manager, sandbox?)` | 创建 Tool 模式的工具集 |
| `create_filesystem_skill_tools(manager)` | 创建 Filesystem 模式的工具集 |

### 异常

| 异常 | 说明 |
|------|------|
| `SkillError` | 基础异常 |
| `SkillParseError` | 解析失败 |
| `SkillValidationError` | 校验不通过 |
| `SkillNotFoundError` | Skill 不存在（含相似名建议） |
| `SkillActivationError` | 激活失败 |
| `SkillResourceError` | 资源访问失败 |
