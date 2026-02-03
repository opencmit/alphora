# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
统一规范消息，包含多模态：图片、文本、音频等
"""

from typing import Optional, List, Dict, Union, Any
import base64
import time
from dataclasses import dataclass, field


@dataclass
class Text:
    content: str = ""

    def __post_init__(self):
        if not isinstance(self.content, str):
            raise TypeError("文本内容必须是字符串")

    def is_empty(self) -> bool:
        return not self.content

    def is_valid(self) -> bool:
        return isinstance(self.content, str)


@dataclass
class Image:
    data: str = ""       # Base64编码
    format: str = "png"  # 图片格式

    # 支持的图片格式列表
    supported_image_type = ['png', 'jpg', 'jpeg', 'bmp', 'dib', 'icns', 'jpeg2000', 'tiff']

    def __post_init__(self):
        # 验证格式
        if self.format and self.format.lower() not in self.supported_image_type:
            raise ValueError(f"不支持的图片格式: {self.format}。"
                             f" 支持的格式有: {', '.join(self.supported_image_type)}")

        # 验证Base64数据
        if self.data and not self._is_valid_base64(self.data):
            raise ValueError("无效的Base64编码数据")

    @staticmethod
    def _is_valid_base64(s: str) -> bool:
        """检查字符串是否为有效的Base64编码"""
        try:
            if s.startswith('data:image/'):
                s = s.split(',', 1)[1]

            s = s.strip()
            padding_needed = len(s) % 4
            if padding_needed:
                s += '=' * (4 - padding_needed)

            base64.b64decode(s, validate=True)
            return True
        except Exception as e:
            return False

    @property
    def data_url(self) -> str:
        """生成DataURL格式的图片地址"""
        return f"data:image/{self.format};base64,{self.data}"

    def is_valid(self) -> bool:
        """检查图片数据是否有效"""
        return bool(self.data) and self.format.lower() in self.supported_image_type and self._is_valid_base64(self.data)


@dataclass
class Audio:
    data: str = ""  # Base64编码
    format: str = "mp3"
    duration: float = 0.0

    # 支持的音频格式
    supported_audio_types = ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']

    def __post_init__(self):
        # 验证格式
        if self.format and self.format.lower() not in self.supported_audio_types:
            raise ValueError(f"不支持的音频格式: {self.format}。"
                                     f" 支持的格式有: {', '.join(self.supported_audio_types)}")

        # 验证Base64数据
        if self.data and not self._is_valid_base64(self.data):
            raise ValueError("无效的音频Base64编码数据")

        # 验证持续时间
        if self.duration < 0:
            raise ValueError("音频持续时间不能为负数")

    @staticmethod
    def _is_valid_base64(s: str) -> bool:
        """检查字符串是否为有效的Base64编码"""
        try:
            if s.startswith('data:audio/'):
                s = s.split(',', 1)[1]

            s = s.strip()
            padding_needed = len(s) % 4
            if padding_needed:
                s += '=' * (4 - padding_needed)

            base64.b64decode(s, validate=True)
            return True
        except Exception:
            return False

    @property
    def data_url(self) -> str:
        """生成DataURL格式的音频地址"""
        return f"data:audio/{self.format};base64,{self.data}"

    def is_valid(self) -> bool:
        """检查音频数据是否有效"""
        return (bool(self.data) and
                self.format.lower() in self.supported_audio_types and
                self._is_valid_base64(self.data) and
                self.duration >= 0)


@dataclass
class Video:
    data: str = ""
    format: str = "mp4"
    duration: float = 0.0

    # 支持的视频格式
    supported_video_types = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv']

    def __post_init__(self):
        # 验证格式
        if self.format and self.format.lower() not in self.supported_video_types:
            raise ValueError(f"不支持的视频格式: {self.format}。"
                                     f" 支持的格式有: {', '.join(self.supported_video_types)}")

        # 验证Base64数据
        if self.data and not self._is_valid_base64(self.data):
            raise ValueError("无效的视频Base64编码数据")

        # 验证持续时间
        if self.duration < 0:
            raise ValueError("视频持续时间不能为负数")

    @staticmethod
    def _is_valid_base64(s: str) -> bool:
        """检查字符串是否为有效的Base64编码"""
        try:
            if s.startswith('data:video/'):
                s = s.split(',', 1)[1]

            s = s.strip()
            padding_needed = len(s) % 4
            if padding_needed:
                s += '=' * (4 - padding_needed)

            base64.b64decode(s, validate=True)
            return True
        except Exception:
            return False

    @property
    def data_url(self) -> str:
        """生成DataURL格式的视频地址"""
        return f"data:video/{self.format};base64,{self.data}"

    def is_valid(self) -> bool:
        """检查视频数据是否有效"""
        return (bool(self.data) and
                self.format.lower() in self.supported_video_types and
                self._is_valid_base64(self.data) and
                self.duration >= 0)


@dataclass
class FunctionCall:
    name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str):
            raise TypeError("函数名必须是字符串")

        if not isinstance(self.parameters, dict):
            raise TypeError("函数参数必须是字典")

    def is_valid(self) -> bool:
        """检查函数调用是否有效"""
        return (isinstance(self.name, str) and
                isinstance(self.parameters, dict))


@dataclass
class FunctionResult:
    name: str = ""
    result: Any = None
    success: bool = True
    error: str = ""

    def __post_init__(self):
        # 验证函数名
        if not isinstance(self.name, str):
            raise TypeError("函数名必须是字符串")

        # 验证成功标志
        if not isinstance(self.success, bool):
            raise TypeError("成功标志必须是布尔值")

        # 验证错误信息
        if not isinstance(self.error, str):
            raise TypeError("错误信息必须是字符串")

        # 验证错误状态
        if not self.success and not self.error:
            raise ValueError("失败的函数调用必须提供错误信息")

    def is_valid(self) -> bool:
        """检查函数结果是否有效"""
        return (isinstance(self.name, str) and
                isinstance(self.success, bool) and
                isinstance(self.error, str) and
                (self.success or bool(self.error)))


@dataclass
class Message:
    """多模态消息体数据结构"""
    id: str = field(default_factory=lambda: f"{int(time.time() * 1000)}")
    timestamp: float = field(default_factory=time.time)  # 当前时间

    text: Optional[Union[Text, str]] = None
    images: List[Image] = field(default_factory=list)
    audios: List[Audio] = field(default_factory=list)
    videos: List[Video] = field(default_factory=list)
    function_call: Optional[FunctionCall] = None
    function_result: Optional[FunctionResult] = None

    def __post_init__(self):
        if self.text is not None:
            if isinstance(self.text, str):
                self.text = Text(content=self.text)
            elif not isinstance(self.text, Text):
                raise TypeError("text参数必须是Text对象或字符串")

    def add_text(self, content: str) -> 'Message':
        self.text = Text(content=content)
        return self

    def add_image(self, data: str, format: str = "png") -> 'Message':
        self.images.append(Image(data=data, format=format))
        return self

    def add_audio(self, data: str, format: str = "mp3", duration: float = 0.0) -> 'Message':
        self.audios.append(Audio(data=data, format=format, duration=duration))
        return self

    def add_video(self, data: str, format: str = "mp4", duration: float = 0.0) -> 'Message':
        self.videos.append(Video(data=data, format=format, duration=duration))
        return self

    def add_function_call(self, name: str, parameters: Dict[str, Any]) -> 'Message':
        self.function_call = FunctionCall(name=name, parameters=parameters)
        return self

    def add_function_result(self, name: str, result: Any, success: bool = True, error: str = "") -> 'Message':
        self.function_result = FunctionResult(name=name, result=result, success=success, error=error)
        return self

    def has_text(self) -> bool:
        return self.text is not None and self.text.content

    def has_images(self) -> bool:
        return bool(self.images)

    def has_audios(self) -> bool:
        return bool(self.audios)

    def has_videos(self) -> bool:
        return bool(self.videos)

    def has_function_call(self) -> bool:
        return self.function_call is not None

    def has_function_result(self) -> bool:
        return self.function_result is not None

    def to_openai_format(self, role: str = "user") -> Dict[str, Any]:
        """
        生成OpenAI API兼容的消息格式
        """
        content = []

        if self.has_text():
            if not any([self.images, self.audios, self.videos]):
                content = self.text.content
            else:
                content.append({
                    "type": "text",
                    "text": self.text.content
                }) # 仅当多模态使用这种格式，用于兼容磐智的大语言模型

        for image in self.images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": image.data_url
                }
            })

        if not content:
            raise ValueError("消息必须包含文本或图片内容")

        return {
            "role": role,
            "content": content
        }

    def __str__(self) -> str:

        parts = [
            f"Message(id={self.id}, timestamp={self.timestamp})"
        ]

        if self.has_text():
            text_preview = self.text.content[:100] + "..." if len(self.text.content) > 50 else self.text.content
            parts.append(f"Text: {text_preview}")

        if self.has_images():
            parts.append(f"Images: {len(self.images)}")

        if self.has_audios():
            audio_info = []
            for i, audio in enumerate(self.audios, 1):
                duration_str = f"{audio.duration:.1f}s" if audio.duration else "unknown"
                audio_info.append(f"{i}. {audio.format} ({duration_str})")
            parts.append(f"Audios: {', '.join(audio_info)}")

        if self.has_videos():
            video_info = []
            for i, video in enumerate(self.videos, 1):
                duration_str = f"{video.duration:.1f}s" if video.duration else "unknown"
                video_info.append(f"{i}. {video.format} ({duration_str})")
            parts.append(f"Videos: {', '.join(video_info)}")

        # 添加函数调用信息
        if self.has_function_call():
            params_str = ", ".join(f"{k}: {v}" for k, v in self.function_call.parameters.items())
            params_preview = params_str[:50] + "..." if len(params_str) > 50 else params_str
            parts.append(f"Function Call: {self.function_call.name}({params_preview})")

        # 添加函数结果信息
        if self.has_function_result():
            status = "Success" if self.function_result.success else "Error"
            result_str = str(self.function_result.result)
            result_preview = result_str[:50] + "..." if len(result_str) > 50 else result_str
            parts.append(f"Function Result: {self.function_result.name} ({status})")
            if not self.function_result.success and self.function_result.error:
                error_preview = self.function_result.error[:50] + "..." if len(self.function_result.error) > 50 else self.function_result.error
                parts.append(f"Error: {error_preview}")

        return " | ".join(parts)


if __name__ == '__main__':
    msg = Message(images=[])
    print(msg.images, msg.videos, msg.audios)
    msg.add_text("为什么地球是圆的")
    # msg.add_image("base64编码的图片数据", format="jpg")

    print(msg)

