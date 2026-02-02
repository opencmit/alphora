<img src="asset/image/banner.png" alt="Alphora 框架 banner" style="max-width: 50%; height: auto;">

# Alphora: 一个轻量的智能体开发框架

<div align="center">
  <br>
  <br>
  
  [![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
  [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
  [![Latest Release](https://img.shields.io/badge/Release-v0.1.0-orange)](https://github.com/your-username/alphora/releases)

  <a href="README.en.md">🌐 English Version</a>
</div>

## 🌟 核心特性

- **灵活的智能体架构**：基于 `BaseAgent` 类构建，支持派生、组合和动态创建
- **多模型支持**：兼容 OpenAI 类 API，支持多模型负载均衡和动态选择
- **智能记忆管理**：内置记忆池，支持短期/长期记忆，自动清理和优先级排序
- **高级提示词系统**：支持 Jinja2 模板、占位符替换和并行处理
- **强大后处理**：提供 JSON 提取、类型转换、模式匹配等多种后处理工具
- **快速 API 部署**：一键发布为 RESTful API，支持 OpenAI 兼容接口
- **流式输出**：支持实时流式响应和自定义流内容类型

## 📦 安装

### 环境要求
- Python >= 3.9
- pip >= 21.0

### 安装方式

#### 使用 pip 安装（推荐）
```bash
pip install alphora
```

#### 从源码安装
```bash
git clone https://github.com/your-username/alphora.git
cd alphora
pip install -e .
```

### 核心依赖
| 依赖包 | 版本要求 | 功能说明 |
|--------|----------|----------|
| dill | 0.3.9 | 对象序列化 |
| fastapi | 0.128.0 | API 服务构建 |
| Jinja2 | 3.1.6 | 提示词模板引擎 |
| json_repair | 0.52.1 | JSON 数据修复 |
| openai | 2.14.0 | LLM 模型调用 |
| pandas | 2.3.3 | 数据处理 |
| pydantic | 2.12.5 | 数据验证 |
| Requests | 2.32.5 | HTTP 请求 |
| uvicorn | 0.40.0 | ASGI 服务器 |



### 安装步骤

```bash
# 从源代码安装
git clone <repository-url>
cd alphora
pip install -e .
```

## 🚀 快速开始

### 1. 创建一个简单的智能体

```python
from alphora.agent.base_agent import BaseAgent
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
from alphora.agent.base_agent import BaseAgent
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

## 🏗️ 项目架构

Alphora采用模块化设计，各组件松耦合，易于扩展和维护。

### 目录结构

```
alphora/
├── agent/           # 智能体核心模块
├── memory/          # 记忆管理系统
├── models/          # 模型接口层
├── postprocess/     # 后处理模块
├── prompter/        # 提示词系统
├── sandbox/         # 沙盒环境
├── server/          # 服务器功能
└── utils/           # 工具函数
```

### 核心模块关系

1. **智能体层**：框架核心，协调各模块工作
2. **模型层**：与各种 LLM 模型交互
3. **提示词层**：管理和渲染提示词模板
4. **记忆层**：存储和管理对话历史
5. **后处理层**：处理模型响应
6. **服务器层**：提供 API 部署能力

## 🧩 核心模块

### 1. Agent（智能体）
智能体是框架的核心组件，负责协调各个模块的工作。`BaseAgent` 提供了模型管理、记忆管理、提示词创建、智能体派生、流式处理和并行处理等功能。

```python
# 智能体派生示例
parent_agent = BaseAgent(llm=parent_llm)
child_agent = parent_agent.derive(CustomAgent, additional_param="value")
```

### 2. Memory（记忆）
记忆模块负责管理智能体的对话历史和上下文信息，支持短期/长期记忆、记忆池管理、自动清理和优先级排序。

```python
# 记忆使用示例
history = agent.memory.build_history(memory_id="default", max_round=5)
agent.memory.add_memory(role="用户", content="你好", score=0.8)
memories = agent.memory.get_top_memories(memory_id="default", top_n=3)
```

### 3. Prompter（提示词）
提示词模块负责管理和渲染提示词模板，支持从文件或字符串加载模板、Jinja2 语法、占位符替换和并行处理。

```python
# 提示词使用示例
prompt = agent.create_prompt("你是一个助手，请回答：{{query}}")
prompt.update_placeholder(name="用户")
parallel_prompt = prompt1 | prompt2 | prompt3
```

### 4. Postprocess（后处理）
后处理模块提供了多种响应处理功能，包括 JSON 处理、类型转换、模式匹配、文本处理和后处理器级联组合。

```python
# 后处理使用示例
json_pp = JsonKeyExtractorPP(target_key="response")
replace_pp = ReplacePP(replace_map={"敏感词": "***"})
complex_pp = json_pp >> replace_pp
response = await prompt.acall(query=query, postprocessor=complex_pp)
```

### 5. Server（服务器）
服务器模块提供了快速部署智能体的功能，支持一键发布为 RESTful API、OpenAI 兼容接口、流式输出和自定义状态。

```python
# API 部署示例
config = APIPublisherConfig(memory_ttl=7200, max_memory_items=2000)
app = publish_agent_api(agent=agent, method="api_logic", config=config)
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 🎯 使用场景

Alphora框架适用于多种AI智能体应用场景：

### 1. 智能客服系统
- 多轮对话支持
- 上下文理解
- 个性化回复
- 快速API部署

### 2. 内容生成与翻译
- 多语言同时翻译
- 内容批量生成
- 格式统一管理
- 实时流式输出

### 3. 虚拟助手
- 工具调用集成
- 记忆能力
- 多任务并行处理
- 可扩展的功能模块

### 4. 教育辅导系统
- 个性化教学
- 知识点记忆与复习
- 多学科支持
- 交互式学习体验

### 5. 企业内部工具
- 知识检索与问答
- 工作流程自动化
- 数据处理与分析
- 团队协作支持

## 🚀 高级功能

### 1. 多模型负载均衡

Alphora支持将多个LLM模型组合使用，实现负载均衡和自动故障转移：

```python
# 创建多个模型实例
llm1 = OpenAILike(api_key="key1", base_url="url1", model_name="model1")
llm2 = OpenAILike(api_key="key2", base_url="url2", model_name="model2")

# 组合模型实现负载均衡
combined_llm = llm1 + llm2

# 使用组合模型创建智能体
agent = BaseAgent(llm=combined_llm)
```

### 2. 自定义流式输出

支持自定义流式输出内容类型和格式：

```python
# 输出状态信息
await agent.stream.astream_message(content="正在处理请求...", content_type="status")

# 输出工具调用结果
await agent.stream.astream_message(content=tool_result, content_type="tool")

# 输出最终结果
await agent.stream.astream_message(content=final_result, content_type="result")

# 停止流
await agent.stream.astop(stop_reason="completed")
```

### 3. 高级后处理组合

支持多个后处理器级联组合，实现复杂的响应处理逻辑：

```python
# 创建多个后处理器
json_pp = JsonKeyExtractorPP(target_key="data")
filter_pp = FilterPP(pattern=r"\d+")
replace_pp = ReplacePP(replace_map={"old": "new"})

# 级联组合后处理器
complex_pp = json_pp >> filter_pp >> replace_pp

# 使用组合后处理器
response = await prompt.acall(query=query, postprocessor=complex_pp)
```

### 4. 智能体并行工作

支持多个智能体并行工作，提高处理效率：

```python
# 并行提示词处理
parallel_prompt = prompt1 | prompt2 | prompt3
response = await parallel_prompt.acall(query=query)

# 多语言同时翻译
target_langs = ["en", "jp", "fr", "de"]
await agent.translate(text="你好", target_langs=target_langs)
```

## 🎯 使用场景

Alphora适用于各种需要AI智能体的场景：

- **虚拟助手**：智能对话、多轮交互、个性化响应
- **教育辅导**：个性化学习、智能答疑、交互式体验
- **企业工具**：知识检索、自动化报告、智能客服、工作流自动化
- **内容创作**：文章生成、翻译、摘要、创意写作
- **数据分析**：数据解读、可视化建议、报告生成

## 🚀 高级功能

### 1. 多模型负载均衡

支持多模型负载均衡，自动选择最优模型：

```python
# 创建多模型负载均衡
llms = [OpenAIModel(api_key="key1"), AnthropicModel(api_key="key2")]
load_balanced_llm = load_balancer(llms, strategy="round_robin")
agent = BaseAgent(llm=load_balanced_llm)
```

### 2. 自定义流式输出

支持自定义流式输出处理：

```python
async def custom_stream_handler(chunk):
    print(f"[自定义流] {chunk}")

response = await agent.stream_chat("你好", stream_handler=custom_stream_handler)
```

### 3. 高级后处理组合

支持多个后处理器级联组合：

```python
# 级联后处理器
complex_pp = JsonKeyExtractorPP(target_key="sql") >> ReplacePP(replace_map={"敏感词": "***"})
response = await prompt.acall(query=query, postprocessor=complex_pp)
```

### 4. 智能体并行工作

支持多智能体并行执行：

```python
# 并行执行
results = await asyncio.gather(
    agent1.chat("中文总结：..."),
    agent2.chat("英文翻译：..."),
    agent3.chat("提取关键词：...")
)
```

## ❓ 常见问题

### 1. 如何添加自定义模型？

实现`BaseLLM`接口：

```python
from alphora.models.llms.base import BaseLLM

class MyCustomLLM(BaseLLM):
    async def generate(self, messages, **kwargs):
        # 实现自定义模型调用逻辑
        pass

# 使用自定义模型
llm = MyCustomLLM(api_key="your-key")
agent = BaseAgent(llm=llm)
```

### 2. 如何自定义记忆存储？

实现`BaseMemory`接口：

```python
from alphora.memory.base import BaseMemory

class MyCustomMemory(BaseMemory):
    async def add_memory(self, content, **kwargs):
        # 实现自定义记忆添加逻辑
        pass

    async def build_history(self, **kwargs):
        # 实现自定义历史构建逻辑
        pass

# 使用自定义记忆
agent = BaseAgent(llm=llm, memory=MyCustomMemory())
```

### 3. 如何扩展后处理器？

继承`BasePostprocess`类：

```python
from alphora.postprocess.base_pp import BasePostprocess


class MyCustomPostprocess(BasePostprocess):
  async def process(self, content, **kwargs):
    # 实现自定义后处理逻辑
    return processed_content


# 使用自定义后处理器
response = await prompt.acall(query=query, postprocessor=MyCustomPostprocess())
```

### 4. 如何优化API性能？

- 使用多模型负载均衡分散请求
- 合理配置记忆池大小和TTL
- 启用流式输出减少等待时间
- 使用并行处理提高并发能力
- 优化提示词模板减少模型计算量

## 📝 详细示例

项目提供了多个详细示例，展示了框架的各种功能：

### 1. 智能体基础功能 (`examples/1-1-智能体基础功能.py`)
展示如何创建和使用一个简单的智能体，包括基本的对话功能。

```python
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# 配置LLM
llm = OpenAILike(api_key="your-api-key", base_url="https://api.example.com/v1", model_name="your-model-name")

# 创建智能体
agent = BaseAgent(llm=llm, verbose=True)


# 调用智能体
async def main():
  response = await agent.chat(query="什么是人工智能？")
  print(response)


if __name__ == "__main__":
  import asyncio

  asyncio.run(main())
```

### 2. 记忆管理功能 (`examples/1-2-记忆管理功能.py`)
展示如何使用记忆模块保存和检索对话历史，支持多轮对话上下文。

```python
class MemoryAgent(BaseAgent):
    async def chat_with_memory(self, query: str) -> str:
        # 构建历史对话
        history = self.memory.build_history(memory_id="default", max_round=5)
        
        # 创建包含历史对话的提示词
        prompt = self.create_prompt(
            prompt="根据历史对话和当前问题回答：\n历史对话：\n{{history}}\n当前问题：{{query}}"
        )
        
        prompt.update_placeholder(history=history)
        response = await prompt.acall(query=query, is_stream=False)
        
        # 保存对话到记忆中
        self.memory.add_memory(role="用户", content=query)
        self.memory.add_memory(role="助手", content=response)
        
        return response
```

### 3. 提示词系统功能 (`examples/1-3-提示词系统功能.py`)
展示如何使用提示词模板系统，支持从文件或字符串加载模板。

```python
class PromptAgent(BaseAgent):
    async def chat_with_template(self, query: str, profession: str) -> str:
        # 从文件加载提示词模板
        prompt = self.create_prompt(
            template_path="prompt_template.tmpl",
            template_desc="通用职业角色回答模板"
        )
        
        # 更新提示词占位符
        prompt.update_placeholder(profession=profession)
        
        # 调用LLM获取回复
        response = await prompt.acall(query=query, is_stream=False)
        
        return response
```

### 4. 后处理功能 (`examples/1-4-后处理功能.py`)
展示如何使用各种后处理器以及它们的组合来处理智能体的输出。

```python
class PostProcessAgent(BaseAgent):
    async def sql_coder(self, query: str, school_name: str):
        prompt = ("请编写SQL脚本，其中学校名称为PLACEHOLDER，问题:{{query}}，用json写，包含sql, explain两个key")
        
        # 多个后处理可进行级联
        replace_pp = ReplacePP(replace_map={"PLACEHOLDER": school_name})
        json_pp = JsonKeyExtractorPP(target_key="explain")
        complex_pp = json_pp >> replace_pp
        
        prompter = self.create_prompt(prompt=prompt)
        resp = await prompter.acall(query=query, is_stream=True, postprocessor=complex_pp)
        return resp
```

### 5. 并行推理 (`examples/1-5-并行推理.py`)
展示如何并行使用多个提示词进行批量处理。

```python
class ParallelAgent(BaseAgent):
    async def translate(self, query: str, target_languages: List[str]):
        prompt = "请将{{query}}翻译为{{target_language}}"
        
        # 创建多个并行的提示词
        prompts = [
            self.create_prompt(prompt=prompt, content_type=lang).
            update_placeholder(target_language=lang)
            for lang in target_languages
        ]
        
        parallel_prompt = ParallelPrompt(prompts=prompts)
        resp = await parallel_prompt.acall(query=query, is_stream=True)
        return resp
```

### 6. 快速API部署示例 (`examples/1-6-快速API部署示例.py`)
展示如何一键将智能体发布为RESTful API，支持流式输出和多模型负载均衡。

```python
class MyAgent(BaseAgent):
    async def guide(self, query: str, city: str) -> None:
        # 派生智能体
        weather_agent = self.derive(WeatherTool)
        
        # 查询天气
        weather = await weather_agent.get_weather(city=city)
        
        # 创建提示词
        prompter = self.create_prompt(prompt=PROMPT_GUIDE)
        prompter.update_placeholder(city=city, weather=weather)
        
        # 调用LLM
        await prompter.acall(query=query, is_stream=True, force_json=True)
        
    async def api_logic(self, request: OpenAIRequest):
        query = request.get_user_query()
        await self.guide(query=query, city='北京')

# 部署API
if __name__ == '__main__':
    import uvicorn
    from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
    
    agent = MyAgent(llm=llm)
    config = APIPublisherConfig(memory_ttl=7200, max_memory_items=2000)
    app = publish_agent_api(agent=agent, method="api_logic", config=config)
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

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



