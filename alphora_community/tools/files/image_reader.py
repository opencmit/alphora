"""
ImageReaderTool - 图片读取与分析工具

通过多模态大模型读取和分析指定路径的图片文件。

主要特性：
1. 支持多种图片格式 - PNG, JPG, JPEG, BMP, GIF, WEBP 等
2. 灵活的分析模式 - 描述、OCR、问答、结构化提取等
3. 支持批量处理 - 可同时分析多张图片
4. 异步支持 - 提供同步和异步调用接口
"""

import os
import base64
import json
from typing import Optional, List, Union
from pathlib import Path
from pydantic import BaseModel, Field

from alphora.models import OpenAILike
from alphora.models.message import Message
from alphora.sandbox import Sandbox


class ImageAnalysisInput(BaseModel):
    """图片分析参数"""
    image_path: str = Field(..., description="图片文件路径(沙箱)")
    prompt: str = Field("请描述这张图片的内容", description="分析提示词")
    mode: str = Field("describe", description="分析模式: describe(描述)/ocr(文字识别)/qa(问答)/extract(结构化提取)")


class ImageReaderTool:
    """
    图片读取与分析工具，读取沙箱内的图片文件

    使用多模态大模型分析图片内容，支持描述、OCR、问答等多种模式。

    使用示例：
        tool = ImageReaderTool(llm=your_multimodal_llm)

        # 描述图片
        result = await tool.analyze("path/to/image.png")

        # OCR 文字识别
        result = await tool.analyze("path/to/image.png", mode="ocr")

        # 自定义问答
        result = await tool.analyze("path/to/image.png", prompt="图片中有几个人？")
    """
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.ico'}
    PROMPT_TEMPLATES = {
        "describe": "请简洁地描述这张图片的内容，包括主要对象、场景、颜色、布局等信息。",
        "ocr": "请识别并提取图片中的所有文字内容，保持原有的格式和布局。如果没有文字，请说明。",
        "qa": "{question}",
        "extract": "请从图片中提取结构化信息，以 JSON 格式返回。提取内容：{fields}",
        "summary": "请用一句话简洁地概括这张图片的主要内容。",
        "table": "请识别图片中的表格内容，并以 Markdown 表格格式输出。",
        "code": "请识别图片中的代码内容，保持代码格式和缩进。",
        "chart": "请分析这张图表，描述其类型、数据趋势和关键信息。",
    }

    def __init__(
            self,
            llm: OpenAILike,
            sandbox: Sandbox = None
    ):
        """
        Args:
            llm: 已配置的多模态 LLM 实例
            sandbox: sandbox
        """
        if llm is not None:
            self._llm = llm

        self._sandbox = sandbox

    def _read_image_as_base64(self, image_path: str) -> tuple[str, str]:
        """
        读取图片文件并转换为 base64 编码

        Args:
            image_path: 图片文件路径

        Returns:
            (base64_data, format): base64 编码数据和图片格式

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的图片格式
        """
        if self._sandbox:
            path = self._sandbox.to_host_path(image_path)
        else:
            path = image_path

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        ext = path.suffix.lower()
        if ext not in ImageReaderTool.SUPPORTED_FORMATS:
            raise ValueError(
                f"不支持的图片格式: {ext}\n"
                f"支持的格式: {', '.join(sorted(ImageReaderTool.SUPPORTED_FORMATS))}"
            )

        with open(path, "rb") as f:
            image_data = f.read()

        base64_data = base64.b64encode(image_data).decode("utf-8")

        format_map = {
            ".jpg": "jpeg",
            ".jpeg": "jpeg",
            ".png": "png",
            ".gif": "gif",
            ".bmp": "bmp",
            ".webp": "webp",
            ".tiff": "tiff",
            ".ico": "ico",
        }
        image_format = format_map.get(ext, ext[1:])

        return base64_data, image_format

    def _build_prompt(
            self,
            mode: str,
            custom_prompt: Optional[str] = None,
            question: Optional[str] = None,
            extract_fields: Optional[List[str]] = None
    ) -> str:
        """
        构建分析提示词

        Args:
            mode: 分析模式
            custom_prompt: 自定义提示词
            question: 问答模式的问题
            extract_fields: 结构化提取的字段列表

        Returns:
            构建好的提示词
        """
        if custom_prompt:
            return custom_prompt

        template = self.PROMPT_TEMPLATES.get(mode, self.PROMPT_TEMPLATES["describe"])

        if mode == "qa" and question:
            return template.format(question=question)
        elif mode == "extract" and extract_fields:
            fields_str = ", ".join(extract_fields)
            return template.format(fields=fields_str)

        return template

    async def analyze(
            self,
            image_path: str,
            prompt: Optional[str] = None,
            mode: str = "describe",
            question: Optional[str] = None,
            extract_fields: Optional[List[str]] = None,
            max_tokens: int = 2048,
            temperature: float = 0.3,
    ) -> str:
        """
        分析单张图片

        Args:
            image_path: 图片文件路径
            prompt: 自定义提示词（覆盖 mode 预设）
            mode: 分析模式
                - "describe": 详细描述图片内容（默认）
                - "ocr": 识别图片中的文字
                - "qa": 问答模式（需配合 question 参数）
                - "extract": 结构化信息提取（需配合 extract_fields 参数）
                - "summary": 一句话概括
                - "table": 表格识别
                - "code": 代码识别
                - "chart": 图表分析
            question: 问答模式下的问题
            extract_fields: 结构化提取的字段列表
            max_tokens: 最大输出 token 数
            temperature: 采样温度

        Returns:
            分析结果文本

        Examples:
            # 描述图片
            >>> result = await tool.analyze("photo.jpg")

            # OCR 文字识别
            >>> result = await tool.analyze("document.png", mode="ocr")

            # 问答
            >>> result = await tool.analyze("scene.jpg", mode="qa", question="图中有几辆车？")

            # 结构化提取
            >>> result = await tool.analyze(
            ...     "receipt.jpg",
            ...     mode="extract",
            ...     extract_fields=["商家名称", "日期", "总金额", "商品列表"]
            ... )
        """
        try:
            # 读取图片
            base64_data, image_format = self._read_image_as_base64(image_path)

            # 构建提示词
            final_prompt = self._build_prompt(
                mode=mode,
                custom_prompt=prompt,
                question=question,
                extract_fields=extract_fields
            )

            # 构建多模态消息
            message = Message()
            message.add_text(final_prompt)
            message.add_image(data=base64_data, format=image_format)

            # 临时调整参数
            original_max_tokens = self._llm.max_tokens
            original_temperature = self._llm.temperature

            self._llm.set_max_tokens(max_tokens)
            self._llm.set_temperature(temperature)

            try:
                # 调用模型
                response = await self._llm.ainvoke(message)
                return response
            finally:
                # 恢复原参数
                self._llm.set_max_tokens(original_max_tokens)
                self._llm.set_temperature(original_temperature)

        except FileNotFoundError as e:
            return f"错误: {str(e)}"
        except ValueError as e:
            return f"错误: {str(e)}"
        except Exception as e:
            return f"分析图片时出错: {str(e)}"

    async def analyze_batch(
            self,
            image_paths: List[str],
            prompt: Optional[str] = None,
            mode: str = "describe",
            compare: bool = False,
    ) -> Union[List[str], str]:
        """
        批量分析多张图片

        Args:
            image_paths: 图片文件路径列表
            prompt: 自定义提示词
            mode: 分析模式
            compare: 是否进行对比分析（将所有图片放在一个请求中）

        Returns:
            如果 compare=False，返回每张图片的分析结果列表
            如果 compare=True，返回对比分析结果字符串
        """
        if compare:
            # 对比模式：所有图片放在一个请求中
            return await self._analyze_comparison(image_paths, prompt)
        else:
            # 独立模式：分别分析每张图片
            results = []
            for path in image_paths:
                result = await self.analyze(path, prompt=prompt, mode=mode)
                results.append(result)
            return results

    async def _analyze_comparison(
            self,
            image_paths: List[str],
            prompt: Optional[str] = None
    ) -> str:
        """
        对比分析多张图片

        Args:
            image_paths: 图片文件路径列表
            prompt: 自定义提示词

        Returns:
            对比分析结果
        """
        try:
            message = Message()

            # 默认对比提示词
            if prompt is None:
                prompt = f"请对比分析以下 {len(image_paths)} 张图片，指出它们的相同点和不同点。"

            message.add_text(prompt)

            for i, path in enumerate(image_paths, 1):
                base64_data, image_format = self._read_image_as_base64(path)
                message.add_image(data=base64_data, format=image_format)

            response = await self._llm.ainvoke(message)
            return response

        except Exception as e:
            return f"对比分析时出错: {str(e)}"

    async def extract_text(self, image_path: str) -> str:
        """
        OCR 文字识别快捷方法
        Args:
            image_path: 图片文件路径
        Returns:
            识别出的文字内容
        """
        return await self.analyze(image_path, mode="ocr")

    async def describe(self, image_path: str) -> str:
        """
        图片描述快捷方法
        Args:
            image_path: 图片文件路径
        Returns:
            图片描述
        """
        return await self.analyze(image_path, mode="describe")

    async def ask(self, image_path: str, question: str) -> str:
        """
        图片问答快捷方法
        Args:
            image_path: 图片文件路径
            question: 问题
        Returns:
            回答
        """
        return await self.analyze(image_path, mode="qa", question=question)

    async def extract_table(self, image_path: str) -> str:
        """
        表格提取快捷方法
        Args:
            image_path: 图片文件路径
        Returns:
            Markdown 格式的表格
        """
        return await self.analyze(image_path, mode="table")

    async def extract_structured(
            self,
            image_path: str,
            fields: List[str],
            output_format: str = "json"
    ) -> Union[str, dict]:
        """
        结构化信息提取
        Args:
            image_path: 图片文件路径
            fields: 要提取的字段列表
            output_format: 输出格式 ("json" 或 "text")
        Returns:
            提取的结构化信息
        """
        result = await self.analyze(
            image_path,
            mode="extract",
            extract_fields=fields
        )

        if output_format == "json":
            try:
                clean_result = result.strip()
                if clean_result.startswith("```json"):
                    clean_result = clean_result[7:]
                if clean_result.startswith("```"):
                    clean_result = clean_result[3:]
                if clean_result.endswith("```"):
                    clean_result = clean_result[:-3]
                return json.loads(clean_result.strip())
            except json.JSONDecodeError:
                return result

        return result

    def get_image_info(self, image_path: str) -> dict:
        """
        获取图片基本信息 no llm
        Args:
            image_path: 图片文件路径
        Returns:
            包含图片信息的字典
        """
        path = Path(image_path)

        if not path.exists():
            return {"error": f"文件不存在: {image_path}"}

        stat = path.stat()

        info = {
            "name": path.name,
            "path": str(path.absolute()),
            "format": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "size_human": self._format_size(stat.st_size),
        }

        try:
            from PIL import Image
            with Image.open(path) as img:
                info["width"] = img.width
                info["height"] = img.height
                info["mode"] = img.mode
        except ImportError:
            info["note"] = "安装 Pillow 可获取图片尺寸信息"
        except Exception:
            pass

        return info

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def list_supported_formats(self) -> str:
        """列出支持的图片格式"""
        return f"支持的图片格式: {', '.join(sorted(self.SUPPORTED_FORMATS))}"


if __name__ == "__main__":
    from alphora.models import OpenAILike
    from alphora.sandbox import Sandbox, StorageConfig, LocalStorage
    import asyncio

    async def main():
        llm = OpenAILike(model_name='qwen-vl-plus', is_multimodal=True)
        sb_storage_config = StorageConfig(local_path='/Users/tiantiantian/临时/sandbox/my_sandbox')
        sb_storage = LocalStorage(config=sb_storage_config)
        sb = Sandbox.create_docker(base_path='/Users/tiantiantian/临时/sandbox', storage=sb_storage, sandbox_id='123456')

        await sb.start()

        tool = ImageReaderTool(
            llm=llm,
            sandbox=sb
        )

        print(await sb.list_files())

        result = await tool.describe("WechatIMG3494.jpg")
        print(f"图片描述: {result}")

        await sb.destroy()

    asyncio.run(main())
