"""
03_prompter/template_file.py - 从模板文件加载提示词

演示如何从 .tmpl 文件加载提示词模板，支持复杂的多行模板和占位符。
"""

import asyncio
import os
from pathlib import Path

# ============================================================
# 环境配置
# ============================================================
os.environ.setdefault("LLM_API_KEY", "your-api-key")
os.environ.setdefault("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")


# ============================================================
# 示例 1: 创建模板文件
# ============================================================
def example_1_create_template_file():
    """
    创建一个 .tmpl 模板文件

    模板文件支持 Jinja2 语法，包括：
    - 变量: {{variable}}
    - 条件: {% if condition %}...{% endif %}
    - 循环: {% for item in items %}...{% endfor %}
    """
    print("=" * 60)
    print("示例 1: 创建模板文件")
    print("=" * 60)

    # 创建模板目录
    template_dir = Path("./templates")
    template_dir.mkdir(exist_ok=True)

    # 创建翻译模板
    translator_template = """你是一个专业的{{source_lang}}到{{target_lang}}翻译专家。

翻译要求：
- 保持原文的语气和风格
- 专业术语需要准确翻译
- 输出只包含翻译结果，不要解释

请翻译以下内容：
{{query}}
"""

    with open(template_dir / "translator.tmpl", "w", encoding="utf-8") as f:
        f.write(translator_template)

    print(f"✓ 创建模板文件: {template_dir / 'translator.tmpl'}")

    # 创建代码审查模板
    code_review_template = """你是一个资深的{{language}}开发工程师，请对以下代码进行审查。

审查维度：
{% for dimension in review_dimensions %}
- {{dimension}}
{% endfor %}

代码：
```{{language}}
{{code}}
```

请按照上述维度逐一分析，并给出改进建议。
"""

    with open(template_dir / "code_review.tmpl", "w", encoding="utf-8") as f:
        f.write(code_review_template)

    print(f"✓ 创建模板文件: {template_dir / 'code_review.tmpl'}")

    # 创建报告生成模板
    report_template = """# {{report_title}}

## 概述
{{summary}}

## 详细分析
{% if sections %}
{% for section in sections %}
### {{section.title}}
{{section.content}}

{% endfor %}
{% endif %}

## 结论与建议
请基于以上内容，给出你的分析结论和建议。

用户问题：{{query}}
"""

    with open(template_dir / "report.tmpl", "w", encoding="utf-8") as f:
        f.write(report_template)

    print(f"✓ 创建模板文件: {template_dir / 'report.tmpl'}")
    print()


# ============================================================
# 示例 2: 从模板文件加载
# ============================================================
def example_2_load_from_template():
    """
    使用 template_path 参数从文件加载模板
    """
    print("=" * 60)
    print("示例 2: 从模板文件加载")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm, verbose=True)

    # 从模板文件创建 Prompt
    prompt = agent.create_prompt(
        template_path="./templates/translator.tmpl",
        template_desc="翻译模板"
    )

    # 查看占位符
    print(f"模板占位符: {prompt.placeholders}")
    # 输出: ['source_lang', 'target_lang']

    # 更新占位符
    prompt.update_placeholder(
        source_lang="中文",
        target_lang="英文"
    )

    # 渲染后预览
    print("\n渲染后的模板:")
    print("-" * 40)
    print(prompt.render())
    print()


# ============================================================
# 示例 3: 使用代码审查模板
# ============================================================
async def example_3_code_review_template():
    """
    使用带循环的代码审查模板
    """
    print("=" * 60)
    print("示例 3: 使用代码审查模板")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        template_path="./templates/code_review.tmpl"
    )

    # 设置审查维度（列表会在模板中循环展开）
    review_dimensions = [
        "代码可读性",
        "性能优化",
        "安全性检查",
        "错误处理"
    ]

    code_to_review = """
def get_user(user_id):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()
"""

    prompt.update_placeholder(
        language="Python",
        review_dimensions=review_dimensions,
        code=code_to_review
    )

    print("渲染后的模板:")
    print("-" * 40)
    print(prompt.render())

    # 调用模型（实际运行时取消注释）
    # response = await prompt.acall(query="请开始审查", is_stream=True)
    # print(f"\n审查结果:\n{response}")
    print()


# ============================================================
# 示例 4: 动态加载字符串模板
# ============================================================
def example_4_load_from_string():
    """
    使用 load_from_string 动态加载模板字符串
    适用于运行时动态生成的模板
    """
    print("=" * 60)
    print("示例 4: 动态加载字符串模板")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建空 Prompt
    prompt = agent.create_prompt()

    # 动态构建模板字符串
    task_type = "数据分析"
    template_string = f"""你是一个专业的{task_type}助手。

用户背景：{{{{background}}}}
数据来源：{{{{data_source}}}}

请分析以下问题：
{{{{query}}}}
"""

    # 从字符串加载
    prompt.load_from_string(template_string)

    print(f"动态模板占位符: {prompt.placeholders}")

    prompt.update_placeholder(
        background="金融行业",
        data_source="公司年报"
    )

    print("\n渲染后的模板:")
    print("-" * 40)
    print(prompt.render())
    print()


# ============================================================
# 示例 5: 模板继承与复用
# ============================================================
def example_5_template_inheritance():
    """
    通过组合多个模板片段实现模板复用
    """
    print("=" * 60)
    print("示例 5: 模板继承与复用")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    # 定义基础角色模板
    base_role = "你是一个专业的{{role}}，拥有{{years}}年经验。"

    # 定义任务模板
    task_template = """
任务类型：{{task_type}}
要求：{{requirements}}
"""

    # 定义输出格式模板
    output_template = """
请按照以下格式输出：
{{output_format}}
"""

    # 组合成完整模板
    full_template = f"{base_role}\n{task_template}\n{output_template}\n用户输入：{{{{query}}}}"

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)
    prompt = agent.create_prompt()
    prompt.load_from_string(full_template)

    prompt.update_placeholder(
        role="数据工程师",
        years="10",
        task_type="ETL流程设计",
        requirements="高效、可维护、可扩展",
        output_format="1. 架构图描述\n2. 关键步骤\n3. 注意事项"
    )

    print("组合模板占位符:", prompt.placeholders)
    print("\n渲染后的模板:")
    print("-" * 40)
    print(prompt.render())
    print()


# ============================================================
# 示例 6: 条件模板
# ============================================================
def example_6_conditional_template():
    """
    使用 Jinja2 条件语法的模板
    """
    print("=" * 60)
    print("示例 6: 条件模板")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    conditional_template = """你是一个智能助手。

{% if expert_mode %}
你现在处于专家模式，请提供详细的技术分析和专业建议。
包括：理论基础、实现细节、最佳实践、潜在风险。
{% else %}
你现在处于普通模式，请用简单易懂的语言回答。
避免使用过多专业术语，必要时举例说明。
{% endif %}

{% if context %}
参考上下文：
{{context}}
{% endif %}

用户问题：{{query}}
"""

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)
    prompt = agent.create_prompt()
    prompt.load_from_string(conditional_template)

    # 专家模式
    prompt.update_placeholder(
        expert_mode=True,
        context="用户是一名软件工程师，有5年开发经验"
    )

    print("专家模式渲染:")
    print("-" * 40)
    print(prompt.render())

    # 普通模式
    prompt.update_placeholder(
        expert_mode=False,
        context=""
    )

    print("\n普通模式渲染:")
    print("-" * 40)
    print(prompt.render())
    print()


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Alphora 模板文件示例")
    print("=" * 60 + "\n")

    # 示例 1: 创建模板文件
    example_1_create_template_file()

    # 示例 2: 从模板文件加载
    example_2_load_from_template()

    # 示例 3: 代码审查模板
    asyncio.run(example_3_code_review_template())

    # 示例 4: 动态加载字符串模板
    example_4_load_from_string()

    # 示例 5: 模板继承与复用
    example_5_template_inheritance()

    # 示例 6: 条件模板
    example_6_conditional_template()

    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()