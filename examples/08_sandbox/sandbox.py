"""
Alphora Sandbox Component - 沙箱环境示例

本文件演示沙箱系统的使用：
1. Sandbox 基础
2. 代码执行
3. 文件操作
4. FileReaderFactory 文件读取工厂
5. 安全限制
6. 超时控制
7. 环境隔离
8. 与Agent集成

沙箱提供安全的代码执行环境，防止恶意代码对系统造成损害
"""

import os
import tempfile
import shutil
from typing import Optional, Dict, Any

from alphora.sandbox import Sandbox, SandboxConfig, FileReaderFactory
from alphora.sandbox.file_reader import (
    TextFileReader,
    PDFFileReader,
    ImageFileReader,
    AudioFileReader,
    VideoFileReader,
    ExcelFileReader,
    get_file_reader
)


# ============================================================
# 示例 1: Sandbox 基础
# ============================================================
def example_1_sandbox_basics():
    """
    Sandbox: 安全的代码执行环境

    特点：
    - 隔离执行环境
    - 资源限制
    - 超时控制
    - 输出捕获
    """
    print("=" * 60)
    print("示例 1: Sandbox 基础")
    print("=" * 60)

    # 创建默认沙箱
    sandbox = Sandbox()

    print(f"\n沙箱类型: {type(sandbox).__name__}")
    print(f"工作目录: {sandbox.working_dir}")

    # 使用配置创建沙箱
    config = SandboxConfig(
        timeout=30,                    # 超时时间（秒）
        max_memory_mb=512,            # 最大内存（MB）
        max_output_size=10000,        # 最大输出大小
        allowed_imports=["math", "json", "datetime"],  # 允许导入的模块
        working_dir="./sandbox_work"  # 工作目录
    )

    sandbox_with_config = Sandbox(config=config)

    print(f"\n配置化沙箱:")
    print(f"  超时: {config.timeout}s")
    print(f"  最大内存: {config.max_memory_mb}MB")
    print(f"  允许的模块: {config.allowed_imports}")

    return sandbox


# ============================================================
# 示例 2: Python代码执行
# ============================================================
def example_2_code_execution():
    """
    在沙箱中执行Python代码
    """
    print("\n" + "=" * 60)
    print("示例 2: Python代码执行")
    print("=" * 60)

    sandbox = Sandbox()

    # 简单代码执行
    print("\n1. 简单代码执行:")
    code = """
result = 2 + 3 * 4
print(f"计算结果: {result}")
"""
    result = sandbox.execute(code)
    print(f"  输出: {result.stdout}")
    print(f"  成功: {result.success}")

    # 带返回值的执行
    print("\n2. 带返回值的执行:")
    code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = [fibonacci(i) for i in range(10)]
result  # 最后一个表达式作为返回值
"""
    result = sandbox.execute(code)
    print(f"  返回值: {result.return_value}")

    # 使用变量
    print("\n3. 传入变量:")
    code = """
total = sum(numbers)
average = total / len(numbers)
print(f"总和: {total}, 平均值: {average:.2f}")
"""
    result = sandbox.execute(code, variables={"numbers": [1, 2, 3, 4, 5]})
    print(f"  输出: {result.stdout}")

    # 多行复杂代码
    print("\n4. 复杂代码执行:")
    code = """
import json
from datetime import datetime

data = {
    "name": "测试",
    "timestamp": datetime.now().isoformat(),
    "values": [1, 2, 3]
}

output = json.dumps(data, ensure_ascii=False, indent=2)
print(output)
"""
    result = sandbox.execute(code)
    print(f"  输出:\n{result.stdout}")

    return sandbox


# ============================================================
# 示例 3: 错误处理
# ============================================================
def example_3_error_handling():
    """
    沙箱中的错误处理
    """
    print("\n" + "=" * 60)
    print("示例 3: 错误处理")
    print("=" * 60)

    sandbox = Sandbox()

    # 语法错误
    print("\n1. 语法错误:")
    code = "print('hello'"  # 缺少括号
    result = sandbox.execute(code)
    print(f"  成功: {result.success}")
    print(f"  错误类型: {result.error_type}")
    print(f"  错误信息: {result.error_message}")

    # 运行时错误
    print("\n2. 运行时错误:")
    code = """
x = 1 / 0  # 除零错误
"""
    result = sandbox.execute(code)
    print(f"  成功: {result.success}")
    print(f"  错误类型: {result.error_type}")
    print(f"  错误信息: {result.error_message}")

    # 名称错误
    print("\n3. 名称错误:")
    code = """
print(undefined_variable)
"""
    result = sandbox.execute(code)
    print(f"  成功: {result.success}")
    print(f"  错误类型: {result.error_type}")

    # 超时错误
    print("\n4. 超时处理（配置5秒超时）:")
    config = SandboxConfig(timeout=5)
    sandbox_with_timeout = Sandbox(config=config)

    code = """
import time
time.sleep(10)  # 睡眠10秒，会超时
"""
    # 实际执行会阻塞，这里只是演示
    print("  代码: time.sleep(10)")
    print("  预期: 超时错误（TimeoutError）")

    return sandbox


# ============================================================
# 示例 4: 文件操作
# ============================================================
def example_4_file_operations():
    """
    沙箱中的文件操作
    """
    print("\n" + "=" * 60)
    print("示例 4: 文件操作")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        config = SandboxConfig(working_dir=temp_dir)
        sandbox = Sandbox(config=config)

        # 创建文件
        print("\n1. 创建文件:")
        code = """
with open('test.txt', 'w', encoding='utf-8') as f:
    f.write('Hello, Sandbox!\\n')
    f.write('这是测试文件\\n')
print('文件创建成功')
"""
        result = sandbox.execute(code)
        print(f"  输出: {result.stdout}")

        # 读取文件
        print("\n2. 读取文件:")
        code = """
with open('test.txt', 'r', encoding='utf-8') as f:
    content = f.read()
print(content)
"""
        result = sandbox.execute(code)
        print(f"  文件内容:\n{result.stdout}")

        # 列出目录
        print("\n3. 列出目录:")
        code = """
import os
files = os.listdir('.')
print(f"目录内容: {files}")
"""
        result = sandbox.execute(code)
        print(f"  输出: {result.stdout}")

        # 处理数据文件
        print("\n4. 处理CSV数据:")
        code = """
import csv

# 写入CSV
with open('data.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['姓名', '年龄', '城市'])
    writer.writerow(['张三', 25, '北京'])
    writer.writerow(['李四', 30, '上海'])

# 读取CSV
with open('data.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row)
"""
        result = sandbox.execute(code)
        print(f"  输出:\n{result.stdout}")

    finally:
        shutil.rmtree(temp_dir)
        print("\n临时目录已清理")

    return sandbox


# ============================================================
# 示例 5: FileReaderFactory 文件读取工厂
# ============================================================
def example_5_file_reader_factory():
    """
    FileReaderFactory: 多格式文件读取

    支持的文件类型：
    - 文本文件 (.txt, .md, .json, .yaml, .py, etc.)
    - PDF文件 (.pdf)
    - 图片文件 (.jpg, .png, .gif, etc.)
    - 音频文件 (.mp3, .wav, etc.)
    - 视频文件 (.mp4, .avi, etc.)
    - Excel文件 (.xlsx, .xls, .csv)
    """
    print("\n" + "=" * 60)
    print("示例 5: FileReaderFactory 文件读取工厂")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        # 创建测试文件
        txt_path = os.path.join(temp_dir, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("这是测试文本文件\n第二行内容")

        json_path = os.path.join(temp_dir, "test.json")
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"name": "测试", "value": 123}, f, ensure_ascii=False)

        # 使用工厂获取读取器
        print("\n1. 自动识别文件类型:")

        reader = get_file_reader(txt_path)
        print(f"  .txt 文件使用: {type(reader).__name__}")
        content = reader.read()
        print(f"  内容: {content[:50]}...")

        reader = get_file_reader(json_path)
        print(f"\n  .json 文件使用: {type(reader).__name__}")
        content = reader.read()
        print(f"  内容: {content}")

        # 直接使用特定读取器
        print("\n2. 直接使用特定读取器:")

        text_reader = TextFileReader(txt_path)
        print(f"  TextFileReader: {text_reader.read()[:30]}...")

        # FileReaderFactory 使用
        print("\n3. FileReaderFactory 批量处理:")
        factory = FileReaderFactory()

        # 注册自定义读取器
        # factory.register(".custom", CustomFileReader)

        # 获取支持的文件类型
        print(f"  支持的文件扩展名: {factory.supported_extensions()}")

        # 读取多个文件
        files = [txt_path, json_path]
        for file_path in files:
            reader = factory.get_reader(file_path)
            content = reader.read()
            print(f"\n  {os.path.basename(file_path)}:")
            print(f"    读取器: {type(reader).__name__}")
            print(f"    内容预览: {str(content)[:50]}...")

    finally:
        shutil.rmtree(temp_dir)

    return factory


# ============================================================
# 示例 6: 特定文件读取器
# ============================================================
def example_6_specific_readers():
    """
    各种文件读取器的详细使用
    """
    print("\n" + "=" * 60)
    print("示例 6: 特定文件读取器")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()

    try:
        # 文本文件读取器
        print("\n1. TextFileReader - 文本文件:")
        txt_path = os.path.join(temp_dir, "sample.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("第一行\n第二行\n第三行")

        reader = TextFileReader(txt_path)
        print(f"  完整内容: {reader.read()}")
        print(f"  编码: {reader.encoding}")
        print(f"  行数: {reader.line_count()}")
        print(f"  读取第2行: {reader.read_line(2)}")

        # Markdown文件
        print("\n2. Markdown文件读取:")
        md_path = os.path.join(temp_dir, "sample.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 标题\n\n## 子标题\n\n- 列表项1\n- 列表项2")

        reader = TextFileReader(md_path)
        content = reader.read()
        print(f"  内容:\n{content}")

        # CSV文件（使用Excel读取器或文本读取器）
        print("\n3. CSV文件读取:")
        csv_path = os.path.join(temp_dir, "data.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("name,age,city\n")
            f.write("张三,25,北京\n")
            f.write("李四,30,上海\n")

        reader = TextFileReader(csv_path)
        print(f"  原始内容:\n{reader.read()}")

        # 解析CSV
        import csv
        with open(csv_path, encoding="utf-8") as f:
            csv_reader = csv.DictReader(f)
            print("  解析后:")
            for row in csv_reader:
                print(f"    {row}")

        # PDF读取器（需要pypdf库）
        print("\n4. PDFFileReader - PDF文件:")
        print("  需要安装: pip install pypdf")
        print("  使用方式:")
        print("    reader = PDFFileReader('document.pdf')")
        print("    text = reader.read()  # 提取文本")
        print("    pages = reader.page_count()  # 页数")
        print("    page_text = reader.read_page(1)  # 读取第1页")

        # 图片读取器
        print("\n5. ImageFileReader - 图片文件:")
        print("  支持: .jpg, .jpeg, .png, .gif, .bmp, .webp")
        print("  使用方式:")
        print("    reader = ImageFileReader('image.png')")
        print("    base64_data = reader.read()  # Base64编码")
        print("    size = reader.get_size()  # (width, height)")
        print("    format = reader.get_format()  # 'PNG'")

        # 音频读取器
        print("\n6. AudioFileReader - 音频文件:")
        print("  支持: .mp3, .wav, .ogg, .flac")
        print("  使用方式:")
        print("    reader = AudioFileReader('audio.mp3')")
        print("    base64_data = reader.read()  # Base64编码")
        print("    duration = reader.get_duration()  # 时长（秒）")
        print("    sample_rate = reader.get_sample_rate()  # 采样率")

        # Excel读取器
        print("\n7. ExcelFileReader - Excel文件:")
        print("  支持: .xlsx, .xls")
        print("  需要安装: pip install openpyxl")
        print("  使用方式:")
        print("    reader = ExcelFileReader('data.xlsx')")
        print("    df = reader.read()  # 返回DataFrame或字典")
        print("    sheets = reader.get_sheet_names()  # 工作表列表")
        print("    sheet_data = reader.read_sheet('Sheet1')  # 读取特定工作表")

    finally:
        shutil.rmtree(temp_dir)


# ============================================================
# 示例 7: 安全限制
# ============================================================
def example_7_security():
    """
    沙箱的安全限制
    """
    print("\n" + "=" * 60)
    print("示例 7: 安全限制")
    print("=" * 60)

    # 创建严格限制的沙箱
    config = SandboxConfig(
        allowed_imports=["math", "json"],  # 只允许这些模块
        blocked_imports=["os", "subprocess", "sys"],  # 明确禁止的模块
        allow_file_write=False,  # 禁止写文件
        allow_network=False,     # 禁止网络访问
        max_memory_mb=256,       # 内存限制
        timeout=10               # 超时限制
    )

    sandbox = Sandbox(config=config)

    print("\n安全配置:")
    print(f"  允许的模块: {config.allowed_imports}")
    print(f"  禁止的模块: {config.blocked_imports}")
    print(f"  允许写文件: {config.allow_file_write}")
    print(f"  允许网络: {config.allow_network}")

    # 尝试导入禁止的模块
    print("\n尝试导入禁止的模块:")
    code = "import os; print(os.getcwd())"
    result = sandbox.execute(code)
    print(f"  import os: 成功={result.success}")
    if not result.success:
        print(f"  错误: {result.error_message[:100]}...")

    # 尝试使用允许的模块
    print("\n使用允许的模块:")
    code = """
import math
import json
result = {"pi": math.pi, "e": math.e}
print(json.dumps(result, indent=2))
"""
    result = sandbox.execute(code)
    print(f"  成功: {result.success}")
    if result.success:
        print(f"  输出:\n{result.stdout}")

    # 内置函数限制
    print("\n内置函数限制:")
    print("  可能被禁止的函数:")
    print("    - eval(), exec(): 动态代码执行")
    print("    - open(): 文件操作（如果禁用）")
    print("    - __import__(): 动态导入")
    print("    - compile(): 代码编译")

    return sandbox


# ============================================================
# 示例 8: 与Agent集成
# ============================================================
def example_8_agent_integration():
    """
    沙箱与Agent的集成
    """
    print("\n" + "=" * 60)
    print("示例 8: 与Agent集成")
    print("=" * 60)

    print("\n沙箱在Agent中的典型应用:")

    print("""
    from alphora.agent import BaseAgent
    from alphora.sandbox import Sandbox, SandboxConfig
    
    # 创建带沙箱的Agent
    agent = BaseAgent(
        sandbox=Sandbox(config=SandboxConfig(
            timeout=30,
            allowed_imports=["math", "json", "datetime", "re"]
        ))
    )
    
    # Agent可以安全执行用户提供的代码
    user_code = '''
    import math
    result = math.sqrt(16) + math.pi
    print(f"结果: {result}")
    '''
    
    result = agent.execute_code(user_code)
    print(result.stdout)
    """)

    print("\n代码执行工具示例:")
    print("""
    from alphora.tools import tool
    
    @tool
    def run_python(code: str) -> dict:
        '''
        执行Python代码
        
        Args:
            code: Python代码
        '''
        sandbox = Sandbox()
        result = sandbox.execute(code)
        return {
            "success": result.success,
            "output": result.stdout,
            "error": result.error_message if not result.success else None,
            "return_value": result.return_value
        }
    
    # LLM可以调用这个工具来执行代码
    # agent.register_tool(run_python)
    """)

    print("\n文件处理集成:")
    print("""
    from alphora.sandbox import FileReaderFactory
    
    # Agent处理用户上传的文件
    factory = FileReaderFactory()
    
    def process_uploaded_file(file_path: str) -> str:
        reader = factory.get_reader(file_path)
        content = reader.read()
        
        # 根据文件类型进行处理
        if file_path.endswith('.pdf'):
            return f"PDF文档，共 {reader.page_count()} 页"
        elif file_path.endswith('.csv'):
            return f"CSV数据文件"
        else:
            return f"文本文件，{len(content)} 字符"
    """)


# ============================================================
# 示例 9: 高级用法
# ============================================================
def example_9_advanced_usage():
    """
    沙箱的高级用法
    """
    print("\n" + "=" * 60)
    print("示例 9: 高级用法")
    print("=" * 60)

    sandbox = Sandbox()

    # 持久化上下文
    print("\n1. 持久化上下文（多次执行共享状态）:")

    # 第一次执行：定义变量
    sandbox.execute("x = 10", persist_context=True)

    # 第二次执行：使用之前定义的变量
    result = sandbox.execute("y = x * 2; print(y)", persist_context=True)
    print(f"  第二次执行输出: {result.stdout}")

    # 第三次执行：继续使用
    result = sandbox.execute("z = x + y; print(z)", persist_context=True)
    print(f"  第三次执行输出: {result.stdout}")

    # 清除上下文
    sandbox.clear_context()
    print("  上下文已清除")

    # 异步执行
    print("\n2. 异步执行:")
    print("""
    import asyncio
    
    async def async_execute():
        sandbox = Sandbox()
        result = await sandbox.aexecute('''
            import asyncio
            await asyncio.sleep(1)
            print("异步执行完成")
        ''')
        return result
    
    result = asyncio.run(async_execute())
    """)

    # 流式输出
    print("\n3. 流式输出:")
    print("""
    sandbox = Sandbox()
    
    code = '''
    for i in range(5):
        print(f"进度: {i+1}/5")
        time.sleep(0.5)
    '''
    
    # 流式获取输出
    for line in sandbox.execute_stream(code):
        print(line, end='')
    """)

    # 资源监控
    print("\n4. 资源监控:")
    print("""
    result = sandbox.execute(code)
    
    print(f"执行时间: {result.execution_time}s")
    print(f"内存使用: {result.memory_usage}MB")
    print(f"CPU时间: {result.cpu_time}s")
    """)

    return sandbox


# ============================================================
# 示例 10: 自定义文件读取器
# ============================================================
def example_10_custom_reader():
    """
    创建自定义文件读取器
    """
    print("\n" + "=" * 60)
    print("示例 10: 自定义文件读取器")
    print("=" * 60)

    print("""
    from alphora.sandbox.file_reader import BaseFileReader
    
    class XMLFileReader(BaseFileReader):
        '''XML文件读取器'''
        
        supported_extensions = ['.xml']
        
        def __init__(self, file_path: str):
            super().__init__(file_path)
            
        def read(self) -> dict:
            '''读取XML并转换为字典'''
            import xml.etree.ElementTree as ET
            
            tree = ET.parse(self.file_path)
            root = tree.getroot()
            
            return self._element_to_dict(root)
        
        def _element_to_dict(self, element):
            result = {}
            for child in element:
                if len(child) == 0:
                    result[child.tag] = child.text
                else:
                    result[child.tag] = self._element_to_dict(child)
            return result
        
        def get_root_tag(self) -> str:
            '''获取根元素标签'''
            import xml.etree.ElementTree as ET
            tree = ET.parse(self.file_path)
            return tree.getroot().tag
    
    # 注册到工厂
    factory = FileReaderFactory()
    factory.register('.xml', XMLFileReader)
    
    # 使用
    reader = factory.get_reader('config.xml')
    data = reader.read()
    """)

    print("\n自定义读取器要点:")
    print("  1. 继承 BaseFileReader")
    print("  2. 定义 supported_extensions")
    print("  3. 实现 read() 方法")
    print("  4. 可选：添加额外的辅助方法")
    print("  5. 注册到 FileReaderFactory")


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Sandbox 沙箱环境示例")
    print("=" * 60)

    example_1_sandbox_basics()
    example_2_code_execution()
    example_3_error_handling()
    example_4_file_operations()
    example_5_file_reader_factory()
    example_6_specific_readers()
    example_7_security()
    example_8_agent_integration()
    example_9_advanced_usage()
    example_10_custom_reader()

    print("\n" + "=" * 60)
    print("所有沙箱示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()