"""
02_llm/multimodal.py
多模态消息示例

演示如何处理图片、音频等多模态内容
"""

import asyncio
import base64
from pathlib import Path
from alphora.models import OpenAILike
from alphora.models.message import Message, Text, Image, Audio, Video
from alphora.utils.base64 import file_to_base64


def create_multimodal_llm():
    """创建多模态 LLM 实例"""
    return OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-vl-max-latest",  # 多模态模型
        is_multimodal=True  # 标记为多模态
    )


# ============================================================
# 示例 1: Message 基础用法
# ============================================================
def example_message_basics():
    """Message 基础用法"""
    print("=" * 60)
    print("示例 1: Message 基础用法")
    print("=" * 60)

    # 创建空消息
    msg = Message()
    print(f"空消息: {msg}")
    print(f"  has_text: {msg.has_text()}")
    print(f"  has_images: {msg.has_images()}")

    # 添加文本
    msg.add_text("这是一条测试消息")
    print(f"\n添加文本后: {msg}")
    print(f"  has_text: {msg.has_text()}")

    # 链式调用
    msg2 = Message().add_text("Hello").add_text(" World")
    print(f"\n链式调用: {msg2}")


# ============================================================
# 示例 2: Text 组件
# ============================================================
def example_text_component():
    """Text 组件示例"""
    print("\n" + "=" * 60)
    print("示例 2: Text 组件")
    print("=" * 60)

    # 直接创建 Text
    text = Text(content="这是文本内容")
    print(f"Text 内容: {text.content}")
    print(f"是否为空: {text.is_empty()}")
    print(f"是否有效: {text.is_valid()}")

    # 在 Message 中使用
    msg = Message(text="直接通过字符串创建")
    print(f"\n消息中的文本: {msg.text.content}")


# ============================================================
# 示例 3: Image 组件
# ============================================================
def example_image_component():
    """Image 组件示例"""
    print("\n" + "=" * 60)
    print("示例 3: Image 组件")
    print("=" * 60)

    # 创建一个简单的 1x1 红色像素图片的 base64
    # 实际使用时应该从文件读取
    red_pixel_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    # 创建 Image
    img = Image(data=red_pixel_base64, format="png")
    print(f"Image 格式: {img.format}")
    print(f"是否有效: {img.is_valid()}")
    print(f"Data URL: {img.data_url[:50]}...")

    # 支持的图片格式
    print(f"\n支持的图片格式: {Image.supported_image_type}")

    # 在 Message 中添加图片
    msg = Message()
    msg.add_text("这张图片是什么？")
    msg.add_image(data=red_pixel_base64, format="png")

    print(f"\n消息中的图片数量: {len(msg.images)}")
    print(f"has_images: {msg.has_images()}")


# ============================================================
# 示例 4: 从文件加载图片
# ============================================================
def example_load_image_from_file():
    """从文件加载图片"""
    print("\n" + "=" * 60)
    print("示例 4: 从文件加载图片")
    print("=" * 60)

    # 假设有一个图片文件
    image_path = "/path/to/your/image.png"

    if Path(image_path).exists():
        # 使用工具函数转换
        img_base64 = file_to_base64(image_path)

        msg = Message()
        msg.add_text("请描述这张图片")
        msg.add_image(data=img_base64, format="png")

        print(f"图片已加载，base64 长度: {len(img_base64)}")
    else:
        print(f"图片文件不存在: {image_path}")
        print("请替换为实际的图片路径")


# ============================================================
# 示例 5: 多模态对话
# ============================================================
async def example_multimodal_chat():
    """多模态对话示例"""
    print("\n" + "=" * 60)
    print("示例 5: 多模态对话")
    print("=" * 60)

    # 创建一个测试图片的 base64（1x1 白色像素）
    test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

    llm = create_multimodal_llm()

    # 创建多模态消息
    msg = Message()
    msg.add_text("这是什么颜色的图片？")
    msg.add_image(data=test_image_base64, format="png")

    print(f"发送多模态消息...")
    print(f"  文本: {msg.text.content}")
    print(f"  图片数量: {len(msg.images)}")

    # 调用多模态模型
    try:
        response = await llm.ainvoke(msg)
        print(f"\n回答: {response}")
    except Exception as e:
        print(f"调用失败: {e}")
        print("请确保使用了支持多模态的模型")


# ============================================================
# 示例 6: Audio 组件
# ============================================================
def example_audio_component():
    """Audio 组件示例"""
    print("\n" + "=" * 60)
    print("示例 6: Audio 组件")
    print("=" * 60)

    # 创建 Audio（需要实际的音频 base64 数据）
    # 这里用占位符演示
    audio_base64 = "placeholder_audio_data"

    try:
        audio = Audio(data=audio_base64, format="mp3", duration=10.5)
        print(f"Audio 格式: {audio.format}")
        print(f"时长: {audio.duration}秒")
    except ValueError as e:
        print(f"创建失败（预期）: {e}")

    # 支持的音频格式
    print(f"\n支持的音频格式: {Audio.supported_audio_types}")

    # 在 Message 中添加音频
    msg = Message()
    # msg.add_audio(data=audio_base64, format="mp3", duration=10.5)
    print(f"消息中的音频数量: {len(msg.audios)}")


# ============================================================
# 示例 7: Video 组件
# ============================================================
def example_video_component():
    """Video 组件示例"""
    print("\n" + "=" * 60)
    print("示例 7: Video 组件")
    print("=" * 60)

    # 支持的视频格式
    print(f"支持的视频格式: {Video.supported_video_types}")

    # 创建 Video（需要实际的视频 base64 数据）
    # video = Video(data="...", format="mp4", duration=30.0)

    # 在 Message 中添加视频
    msg = Message()
    # msg.add_video(data="...", format="mp4", duration=30.0)
    print(f"消息中的视频数量: {len(msg.videos)}")


# ============================================================
# 示例 8: 转换为 OpenAI 格式
# ============================================================
def example_openai_format():
    """转换为 OpenAI 格式"""
    print("\n" + "=" * 60)
    print("示例 8: 转换为 OpenAI 格式")
    print("=" * 60)

    # 纯文本消息
    msg1 = Message()
    msg1.add_text("Hello, world!")

    openai_format1 = msg1.to_openai_format(role="user")
    print(f"纯文本格式:\n{openai_format1}")

    # 带图片的消息
    test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    msg2 = Message()
    msg2.add_text("描述这张图片")
    msg2.add_image(data=test_image, format="png")

    openai_format2 = msg2.to_openai_format(role="user")
    print(f"\n多模态格式:")
    print(f"  role: {openai_format2['role']}")
    print(f"  content 类型: {type(openai_format2['content'])}")
    print(f"  content 长度: {len(openai_format2['content'])}")


# ============================================================
# 示例 9: FunctionCall 和 FunctionResult
# ============================================================
def example_function_components():
    """FunctionCall 和 FunctionResult 示例"""
    print("\n" + "=" * 60)
    print("示例 9: FunctionCall 和 FunctionResult")
    print("=" * 60)

    from alphora.models.message import FunctionCall, FunctionResult

    # 创建函数调用
    func_call = FunctionCall(
        name="search",
        parameters={"query": "Python tutorial", "limit": 10}
    )
    print(f"函数调用: {func_call.name}({func_call.parameters})")

    # 创建函数结果
    func_result = FunctionResult(
        name="search",
        result=["result1", "result2"],
        success=True
    )
    print(f"函数结果: {func_result.name} -> {func_result.result}")

    # 在 Message 中使用
    msg = Message()
    msg.add_function_call("get_weather", {"city": "北京"})
    msg.add_function_result("get_weather", {"temp": 25, "weather": "晴"})

    print(f"\nhas_function_call: {msg.has_function_call()}")
    print(f"has_function_result: {msg.has_function_result()}")


# ============================================================
# 示例 10: 完整的多模态工作流
# ============================================================
async def example_full_workflow():
    """完整的多模态工作流"""
    print("\n" + "=" * 60)
    print("示例 10: 完整的多模态工作流")
    print("=" * 60)

    # 1. 准备图片数据
    # 实际应用中从文件读取
    image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    # 2. 创建消息
    msg = Message(id="msg_001")
    msg.add_text("请分析这张图片的内容，并用JSON格式回复。")
    msg.add_image(data=image_base64, format="png")

    print(f"消息 ID: {msg.id}")
    print(f"时间戳: {msg.timestamp}")
    print(f"内容摘要: {msg}")

    # 3. 发送请求
    try:
        llm = create_multimodal_llm()
        response = await llm.ainvoke(msg)
        print(f"\n模型回复:\n{response}")
    except Exception as e:
        print(f"\n请求失败: {e}")
        print("提示: 请确保配置了支持多模态的模型")


# ============================================================
# 主函数
# ============================================================
async def main():
    """运行所有示例"""
    # 同步示例
    example_message_basics()
    example_text_component()
    example_image_component()
    example_load_image_from_file()
    example_audio_component()
    example_video_component()
    example_openai_format()
    example_function_components()

    # 异步示例
    await example_multimodal_chat()
    await example_full_workflow()


if __name__ == "__main__":
    asyncio.run(main())