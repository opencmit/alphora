# Alphora: A Lightweight Agent Development Framework

> 🌐 [中文版本](README.md) 

Alphora is a lightweight toolkit for developing AI agents, providing core functionalities needed to build, deploy, and manage agents. It features a clean, extensible design, supports multiple LLM models, and includes built-in memory management, post-processing, prompt templating, and more, helping developers quickly build complex agent applications.

## 🌟 Core Features

- **Flexible Agent Architecture**: Built on the `BaseAgent` class, supporting derivation, composition, and dynamic creation
- **Multi-Model Support**: Compatible with OpenAI-like APIs, supporting multi-model load balancing and dynamic selection
- **Intelligent Memory Management**: Built-in memory pool supporting short-term/long-term memory with automatic cleanup and priority ranking
- **Prompt System**: Supports Jinja2 templates, placeholder replacement, and parallel processing
- **Powerful Post-Processing**: Provides multiple post-processing tools including JSON extraction, type conversion, and pattern matching
- **Rapid API Deployment**: One-click deployment as a RESTful API with OpenAI-compatible interface support
- **Streaming Output**: Supports real-time streaming responses and custom stream content types

## 📦 Installation

### Requirements

- Python >= 3.9
- Dependencies: fastapi, uvicorn, pydantic, openai, numpy, etc.

### Installation Steps

```bash
# Install from source code
git clone <repository-url>
cd alphora
pip install -e .

# Or install directly
pip install alphora
```

## 🚀 Quick Start

### 1. Create a Simple Agent

```python
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# Configure LLM
llm = OpenAILike(
    api_key="your-api-key",
    base_url="https://api.example.com/v1",
    model_name="your-model-name"
)

# Create agent
agent = BaseAgent(llm=llm, verbose=True)

# Create prompt
prompt = agent.create_prompt(prompt="You are an assistant. Please answer the user's question: {{query}}")


# Call agent
async def main():
    response = await prompt.acall(query="What is artificial intelligence?", is_stream=False)
    print(response)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

### 2. Create a Custom Agent

```python
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.openai_request_body import OpenAIRequest


class TeacherAgent(BaseAgent):
    async def teacher(self, query):
        # Build conversation history
        history = self.memory.build_history()

        # Create prompt
        prompt = self.create_prompt(
            prompt="You are a university mathematics teacher currently answering student questions. Please provide accurate responses.\n\nConversation History:\n{{history}}\n\nStudent says: {{query}}"
        )

        prompt.update_placeholder(history=history)

        # Call LLM
        response = await prompt.acall(query=query, is_stream=False)

        # Save conversation to memory
        self.memory.add_memory(role='student', content=query)
        self.memory.add_memory(role='teacher', content=response)

        return response

    async def api_logic(self, request: OpenAIRequest):
        query = request.get_user_query()
        response = await self.teacher(query)
        return response
```

### 3. Deploy as API Service

```python
import uvicorn
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

# Create agent instance
agent = TeacherAgent(llm=llm)

# Configure API publishing
config = APIPublisherConfig(
    memory_ttl=7200,  # Memory TTL in seconds
    max_memory_items=2000,  # Maximum number of memory entries
    auto_clean_interval=300,  # Auto-cleanup interval in seconds
    api_title="Teacher Agent API Service",
    api_description="University Mathematics Teacher Agent API"
)

# Publish API
app = publish_agent_api(
    agent=agent,
    method="api_logic",
    config=config
)

# Start server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 📁 Project Architecture

Alphora adopts a modular design with loosely coupled components for easy extension and maintenance:

```
alphora/
├── agent/           # Core agent module
│   ├── base.py      # Base agent class defining core interfaces
│   └── stream.py    # Streaming implementation supporting real-time responses
├── memory/          # Memory management system
│   ├── base.py      # Base memory interface
│   ├── memory_pool.py # Memory pool managing memories for multiple agents
│   ├── memory_unit.py # Memory unit storing single memory entries
│   └── memories/    # Various memory implementations (short-term, long-term, etc.)
├── models/          # Model interface layer
│   ├── embedder/    # Embedding model interfaces and implementations
│   ├── llms/        # LLM model interfaces and implementations
│   │   └── openai_like.py # OpenAI-compatible model implementation
│   └── message.py   # Message model definitions
├── postprocess/     # Post-processing module
│   ├── base.py      # Base post-processor interface
│   ├── json_key_extractor.py # JSON key extractor
│   ├── type_mapper.py # Type converter
│   ├── filter.py    # Content filter
│   ├── pattern_match.py # Pattern matcher
│   ├── replace.py   # Text replacer
│   └── split_char.py # Text splitter
├── prompter/        # Prompt system
│   ├── base.py      # Base prompt class
│   └── parallel.py  # Parallel prompt processing
├── sandbox/         # Sandbox environment for secure external code execution
├── server/          # Server functionality
│   ├── openai_request_body.py # OpenAI-compatible request body
│   ├── quick_api/   # Rapid API publishing functionality
│   └── stream_responser.py # Streaming responser
└── utils/           # Utility functions
    ├── base64.py    # Base64 encoding/decoding
    ├── code_executer.py # Code executor
    ├── logger.py    # Logging utilities
    └── parallel.py  # Parallel processing utilities
```

### Core Module Relationships

1. **Agent Layer**: The framework's core that coordinates other modules
2. **Model Layer**: Interfaces for interacting with various LLM models
3. **Prompt Layer**: Manages and renders prompt templates
4. **Memory Layer**: Stores and manages conversation history
5. **Post-Processing Layer**: Processes model responses
6. **Server Layer**: Provides API deployment capabilities

## 🧩 Core Module Details

### 1. Agent

The agent is the framework's core component responsible for coordinating module operations. `BaseAgent` provides essential agent functionalities:

- **Model Management**: Encapsulates LLM models with a unified calling interface
- **Memory Management**: Integrates memory system for automatic conversation context management
- **Prompt Creation**: Offers convenient prompt creation and management
- **Agent Derivation**: Supports deriving new agents from existing ones to share resources and configurations
- **Streaming Processing**: Built-in streaming output support for real-time results
- **Parallel Processing**: Supports multi-agent parallel operation

#### Agent Derivation Example
```python
# Derive new agent from existing one
parent_agent = BaseAgent(llm=parent_llm)
child_agent = parent_agent.derive(CustomAgent, additional_param="value")
```

### 2. Memory

The memory module manages agent conversation history and context information:

- **Memory Types**: Supports short-term and long-term memory
- **Memory Pool**: Manages memories for multiple agents with memory isolation
- **Memory Unit**: Stores individual memory entries with content, role, score, and other attributes
- **Automatic Cleanup**: Supports TTL- and size-based automatic cleanup
- **Priority Ranking**: Automatically ranks memories by importance
- **History Construction**: Automatically builds formatted conversation history

#### Memory Usage Example
```python
# Build conversation history
history = agent.memory.build_history(memory_id="default", max_round=5)

# Add memory
agent.memory.add_memory(role="user", content="Hello", score=0.8)

# Retrieve memories
memories = agent.memory.get_top_memories(memory_id="default", top_n=3)
```

### 3. Prompter

The prompt module manages and renders prompt templates:

- **Template Loading**: Supports loading templates from files or strings
- **Jinja2 Support**: Supports dynamic templates with Jinja2 syntax
- **Placeholder Replacement**: Dynamically updates placeholders in prompts
- **Parallel Processing**: Processes multiple prompts in parallel
- **Content Types**: Supports different content types for various prompts

#### Prompt Usage Example
```python
# Create prompt from string
prompt = agent.create_prompt("You are an assistant. Please answer: {{query}}")

# Create prompt from file
prompt = agent.create_prompt(template_path="prompt_template.tmpl")

# Update placeholders
prompt.update_placeholder(name="User")

# Parallel prompts
parallel_prompt = prompt1 | prompt2 | prompt3
```

### 4. Postprocess

The post-processing module provides various response processing functions:

- **JSON Processing**: Extracts specific key-value pairs from JSON
- **Type Conversion**: Converts strings to specific data types
- **Pattern Matching**: Uses regular expressions to match and extract content
- **Text Processing**: Replaces, splits, and filters text
- **Cascading Combination**: Supports cascading multiple post-processors

#### Post-Processing Usage Example
```python
# Create post-processors
json_pp = JsonKeyExtractorPP(target_key="response")
replace_pp = ReplacePP(replace_map={"sensitive_word": "***"})

# Cascade post-processors
complex_pp = json_pp >> replace_pp

# Use post-processor
response = await prompt.acall(query=query, postprocessor=complex_pp)
```

### 5. Server

The server module enables rapid agent deployment:

- **Quick Deployment**: One-click publication of agents as RESTful APIs
- **OpenAI Compatibility**: Supports OpenAI-compatible API interfaces
- **Streaming Output**: Supports real-time streaming responses
- **Custom Output**: Supports outputting custom status and tool results
- **Memory Management**: Built-in API-level memory management
- **Security Mechanisms**: Supports API key authentication and request limiting

#### API Deployment Example
```python
# Configure API publishing
config = APIPublisherConfig(
    memory_ttl=7200,  # Memory TTL in seconds
    max_memory_items=2000,  # Maximum number of memory entries
    auto_clean_interval=300  # Auto-cleanup interval in seconds
)

# Publish API
app = publish_agent_api(agent=agent, method="api_logic", config=config)

# Start server
uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 🚀 Advanced Features

### 1. Multi-Model Load Balancing

Alphora supports combining multiple LLM models for load balancing and automatic failover:

```python
# Create multiple model instances
llm1 = OpenAILike(api_key="key1", base_url="url1", model_name="model1")
llm2 = OpenAILike(api_key="key2", base_url="url2", model_name="model2")

# Combine models for load balancing
combined_llm = llm1 + llm2

# Create agent with combined model
agent = BaseAgent(llm=combined_llm)
```

### 2. Custom Streaming Output

Supports custom streaming output content types and formats:

```python
# Output status information
await agent.stream.astream_message(content="Processing request...", content_type="status")

# Output tool call results
await agent.stream.astream_message(content=tool_result, content_type="tool")

# Output final result
await agent.stream.astream_message(content=final_result, content_type="result")

# Stop stream
await agent.stream.astop(stop_reason="completed")
```

### 3. Advanced Post-Processing Combinations

Supports cascading multiple post-processors for complex response processing logic:

```python
# Create multiple post-processors
json_pp = JsonKeyExtractorPP(target_key="data")
filter_pp = FilterPP(pattern=r"\d+")
replace_pp = ReplacePP(replace_map={"old": "new"})

# Cascade post-processors
complex_pp = json_pp >> filter_pp >> replace_pp

# Use combined post-processor
response = await prompt.acall(query=query, postprocessor=complex_pp)
```

### 4. Parallel Agent Operation

Supports parallel operation of multiple agents to improve processing efficiency:

```python
# Parallel prompt processing
parallel_prompt = prompt1 | prompt2 | prompt3
response = await parallel_prompt.acall(query=query)

# Simultaneous translation to multiple languages
target_langs = ["en", "jp", "fr", "de"]
await agent.translate(text="Hello", target_langs=target_langs)
```

## ❓ Frequently Asked Questions

### 1. How to Add a Custom Model?

Implement the `BaseLLM` interface and register it with the framework:

```python
from alphora.models.llms.base import BaseLLM

class MyCustomLLM(BaseLLM):
    async def generate(self, messages, **kwargs):
        # Implement custom model calling logic
        pass

# Use custom model
llm = MyCustomLLM(api_key="your-key", base_url="your-url")
agent = BaseAgent(llm=llm)
```

### 2. How to Customize Memory Storage?

Implement the `BaseMemory` interface and replace the default memory:

```python
from alphora.memory.base import BaseMemory

class MyCustomMemory(BaseMemory):
    async def add_memory(self, content, **kwargs):
        # Implement custom memory addition logic
        pass

    async def build_history(self, **kwargs):
        # Implement custom history construction logic
        pass

# Use custom memory
agent = BaseAgent(llm=llm, memory=MyCustomMemory())
```

### 3. How to Extend Post-Processors?

Inherit from the `BasePostprocess` class and implement the `process` method:

```python
from alphora.postprocess.base import BasePostprocess

class MyCustomPostprocess(BasePostprocess):
    async def process(self, content, **kwargs):
        # Implement custom post-processing logic
        return processed_content

# Use custom post-processor
custom_pp = MyCustomPostprocess()
response = await prompt.acall(query=query, postprocessor=custom_pp)
```

### 4. How to Optimize API Performance?

- Use multi-model load balancing to distribute requests
- Configure appropriate memory pool size and TTL
- Enable streaming output to reduce waiting time
- Use parallel processing to improve concurrency
- Optimize prompt templates to reduce model computation

## 📝 Detailed Examples

The project includes several detailed examples demonstrating various framework capabilities:

### 1. Basic Agent Functionality (`examples/1-1-agent-basics.py`)
Demonstrates creating and using a simple agent with basic conversation capabilities.

```python
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# Configure LLM
llm = OpenAILike(api_key="your-api-key", base_url="https://api.example.com/v1", model_name="your-model-name")

# Create agent
agent = BaseAgent(llm=llm, verbose=True)


# Call agent
async def main():
    response = await agent.chat(query="What is artificial intelligence?")
    print(response)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

### 2. Memory Management (`examples/1-2-memory-management.py`)
Demonstrates using the memory module to save and retrieve conversation history for multi-turn context support.

```python
class MemoryAgent(BaseAgent):
    async def chat_with_memory(self, query: str) -> str:
        # Build conversation history
        history = self.memory.build_history(memory_id="default", max_round=5)
        
        # Create prompt with conversation history
        prompt = self.create_prompt(
            prompt="Answer based on conversation history and current question:\nHistory:\n{{history}}\nCurrent question: {{query}}"
        )
        
        prompt.update_placeholder(history=history)
        response = await prompt.acall(query=query, is_stream=False)
        
        # Save conversation to memory
        self.memory.add_memory(role="user", content=query)
        self.memory.add_memory(role="assistant", content=response)
        
        return response
```

### 3. Prompt System (`examples/1-3-prompt-system.py`)
Demonstrates using the prompt template system with templates loaded from files or strings.

```python
class PromptAgent(BaseAgent):
    async def chat_with_template(self, query: str, profession: str) -> str:
        # Load prompt template from file
        prompt = self.create_prompt(
            template_path="prompt_template.tmpl",
            template_desc="General professional role response template"
        )
        
        # Update prompt placeholders
        prompt.update_placeholder(profession=profession)
        
        # Call LLM for response
        response = await prompt.acall(query=query, is_stream=False)
        
        return response
```

### 4. Post-Processing (`examples/1-4-post-processing.py`)
Demonstrates using various post-processors and their combinations to process agent outputs.

```python
class PostProcessAgent(BaseAgent):
    async def sql_coder(self, query: str, school_name: str):
        prompt = ("Please write SQL script where school name is PLACEHOLDER for question:{{query}}. "
                 "Respond in JSON format with 'sql' and 'explain' keys.")
        
        # Multiple post-processors can be cascaded
        replace_pp = ReplacePP(replace_map={"PLACEHOLDER": school_name})
        json_pp = JsonKeyExtractorPP(target_key="explain")
        complex_pp = json_pp >> replace_pp
        
        prompter = self.create_prompt(prompt=prompt)
        resp = await prompter.acall(query=query, is_stream=True, postprocessor=complex_pp)
        return resp
```

### 5. Parallel Inference (`examples/1-5-parallel-inference.py`)
Demonstrates parallel processing with multiple prompts for batch operations.

```python
class ParallelAgent(BaseAgent):
    async def translate(self, query: str, target_languages: List[str]):
        prompt = "Translate {{query}} to {{target_language}}"
        
        # Create multiple parallel prompts
        prompts = [
            self.create_prompt(prompt=prompt, content_type=lang).
            update_placeholder(target_language=lang)
            for lang in target_languages
        ]
        
        parallel_prompt = ParallelPrompt(prompts=prompts)
        resp = await parallel_prompt.acall(query=query, is_stream=True)
        return resp
```

### 6. Rapid API Deployment (`examples/1-6-api-deployment.py`)
Demonstrates one-click deployment of an agent as a RESTful API with streaming output and multi-model load balancing.

```python
class MyAgent(BaseAgent):
    async def guide(self, query: str, city: str) -> None:
        # Derive agent
        weather_agent = self.derive(WeatherTool)
        
        # Query weather
        weather = await weather_agent.get_weather(city=city)
        
        # Create prompt
        prompter = self.create_prompt(prompt=PROMPT_GUIDE)
        prompter.update_placeholder(city=city, weather=weather)
        
        # Call LLM
        await prompter.acall(query=query, is_stream=True, force_json=True)
        
    async def api_logic(self, request: OpenAIRequest):
        query = request.get_user_query()
        await self.guide(query=query, city='Beijing')

# Deploy API
if __name__ == '__main__':
    import uvicorn
    from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
    
    agent = MyAgent(llm=llm)
    config = APIPublisherConfig(memory_ttl=7200, max_memory_items=2000)
    app = publish_agent_api(agent=agent, method="api_logic", config=config)
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

- Author: Tian Tian
- Email: tiantianit@chinamobile.com
