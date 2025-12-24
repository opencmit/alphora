# Alphora: 一个轻量的智能体开发框架

Alphora 是一个轻量级的 AI 智能体开发工具包，提供了构建、部署和管理智能体所需的核心功能。它设计简洁、易于扩展，支持多种 LLM 模型，内置记忆管理、后处理、提示词模板等功能，帮助开发者快速构建复杂的智能体应用。

## 🌟 核心特性

- **灵活的智能体架构**：基于 `BaseAgent` 类构建，支持智能体的派生和组合
- **多模型支持**：兼容 OpenAI 类 API 的多种 LLM 模型
- **记忆管理**：内置记忆池和记忆单元，支持短期记忆和长期记忆
- **提示词系统**：支持模板化提示词，方便复用和管理
- **后处理功能**：提供多种后处理工具，如 JSON 提取、类型转换、模式匹配等
- **快速 API 部署**：一键将智能体发布为 RESTful API
- **流式输出支持**：支持实时流式响应

## 📦 安装

### 依赖要求

- Python >= 3.9
- 依赖库：fastapi, uvicorn, pydantic, openai, numpy 等

### 安装步骤

```bash
# 从源代码安装
git clone <repository-url>
cd alphora
pip install -e .

# 或直接安装
pip install alphora
```

## 🚀 快速开始

### 1. 创建一个简单的智能体

```python
from alphora.agent.base import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# 配置 LLM
llm = OpenAILike(
    api_key="your-api-key",
    base_url="https://api.example.com/v1",
    model_name="your-model-name"
)

# 创建智能体
agent = BaseAgent(llm=llm, verbose=True)

# 创建提示词
prompt = agent.create_prompt(prompt="你是一个助手，请回答用户的问题：{{query}}")

# 调用智能体
async def main():
    response = await prompt.acall(query="什么是人工智能？", is_stream=False)
    print(response)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 2. 创建自定义智能体

```python
from alphora.agent.base import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.openai_request_body import OpenAIRequest

class TeacherAgent(BaseAgent):
    async def teacher(self, query):
        # 构建历史对话
        history = self.memory.build_history()
        
        # 创建提示词
        prompt = self.create_prompt(
            prompt="你是一个大学数学老师，目前正在回复学生的问题，请你准确的回复学生的问题。\n\n历史对话: \n{{history}} \n\n学生说:{{query}}"
        )
        
        prompt.update_placeholder(history=history)
        
        # 调用 LLM
        response = await prompt.acall(query=query, is_stream=False)
        
        # 保存对话记忆
        self.memory.add_memory(role='学生', content=query)
        self.memory.add_memory(role='老师', content=response)
        
        return response
    
    async def api_logic(self, request: OpenAIRequest):
        query = request.get_user_query()
        response = await self.teacher(query)
        return response
```

### 3. 部署为 API 服务

```python
import uvicorn
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

# 创建智能体实例
agent = TeacherAgent(llm=llm)

# 配置 API 发布
config = APIPublisherConfig(
    memory_ttl=7200,  # 记忆有效期（秒）
    max_memory_items=2000,  # 最大记忆条目数
    auto_clean_interval=300,  # 自动清理间隔（秒）
    api_title="Teacher Agent API Service",
    api_description="大学数学老师智能体 API"
)

# 发布 API
app = publish_agent_api(
    agent=agent,
    method="api_logic",
    config=config
)

# 启动服务器
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 📁 项目架构

```
alphora/
├── agent/           # 智能体核心模块
│   ├── base.py      # 基础智能体类
│   └── stream.py    # 流式处理
├── memory/          # 记忆管理
│   ├── base.py      # 基础记忆类
│   ├── memory_pool.py # 记忆池
│   └── memory_unit.py # 记忆单元
├── models/          # 模型接口
│   ├── embedder/    # 嵌入模型
│   ├── llms/        # LLM 模型
│   └── message.py   # 消息模型
├── postprocess/     # 后处理功能
│   ├── base.py      # 基础后处理器
│   ├── json_key_extractor.py # JSON 键提取
│   └── type_mapper.py # 类型映射
├── prompter/        # 提示词系统
│   ├── base.py      # 基础提示词类
│   └── parallel.py  # 并行提示词
├── sandbox/         # 沙盒环境
├── server/          # 服务器功能
│   ├── quick_api/   # 快速 API 发布
│   └── stream_responser.py # 流式响应器
└── utils/           # 工具函数
```

## 🧩 核心模块

### 1. Agent（智能体）

智能体是框架的核心组件，负责协调各个模块的工作。`BaseAgent` 提供了智能体的基本功能，包括：
- LLM 模型管理
- 记忆管理
- 提示词创建
- 智能体派生

### 2. Memory（记忆）

记忆模块负责管理智能体的对话历史和上下文信息：
- 支持短期记忆和长期记忆
- 提供记忆池管理多个智能体的记忆
- 支持记忆的添加、查询和清理

### 3. Prompter（提示词）

提示词模块负责管理和渲染提示词模板：
- 支持从文件或字符串加载模板
- 支持占位符替换
- 支持并行提示词处理

### 4. Postprocess（后处理）

后处理模块提供了多种响应处理功能：
- JSON 键提取
- 类型转换
- 模式匹配
- 文本替换和拆分

### 5. Server（服务器）

服务器模块提供了快速部署智能体的功能：
- 一键发布为 RESTful API
- 支持 OpenAI 兼容的 API 接口
- 支持流式输出

## 📝 示例

项目提供了多个示例，展示了框架的各种功能：

- `2-3-智能体并行.py`：展示如何并行使用多个智能体
- `2-4-后处理.py`：展示如何使用后处理功能
- `2-5-示例.py`：基础使用示例
- `2-5-调用API.py`：展示如何调用外部 API

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！请遵循以下步骤：

1. Fork 仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📧 联系方式

- 作者：Tian tian
- 邮箱：tiantianit@chinamobile.com

## 📚 文档

更多详细文档，请参考：
- [API 文档](docs/api.md)
- [快速入门指南](docs/quickstart.md)
- [高级功能](docs/advanced.md)



