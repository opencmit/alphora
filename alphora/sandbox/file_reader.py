import json
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Union, Callable, Type
from pathlib import Path
from chatbi.models import LLM
from chatbi.agent import BaseAgent

# Import Prompts
from chatbi.sandbox.prompts.excel_prompt import excel_prompt
from chatbi.sandbox.prompts.image_prompt import image_prompt


class FileReader(BaseAgent):

    desc, content = "", ""

    def read(self, file_path: Union[Path, str]) -> str:
        """读取文件内容"""
        raise NotImplementedError("子类必须实现此方法")

    def description(self, file_path: Union[Path, str]) -> str:
        """生成文件描述"""
        raise NotImplementedError("子类必须实现此方法")

    @staticmethod
    def save_description(file_path: Union[Path, str], description: str):
        """保存描述信息到隐藏文件"""
        file_path = Path(file_path)
        hidden_file_path = file_path.with_name(f"{file_path.name}.description")
        hidden_file_path.write_text(description, encoding='utf-8')

    @staticmethod
    def read_description(file_path: Union[Path, str]) -> str:
        """读取描述信息"""
        file_path = Path(file_path)
        hidden_file_path = file_path.with_name(f"{file_path.name}.description")
        if hidden_file_path.exists():
            return hidden_file_path.read_text(encoding='utf-8')
        return ""


class TextFileReader(FileReader):
    """文本文件读取器"""

    def read(self, file_path: Union[Path, str]) -> str:
        """读取文本文件内容"""
        file_path = Path(file_path)
        return file_path.read_text(encoding='utf-8')

    def description(self, file_path: Union[Path, str]) -> str:
        """生成文本文件描述"""
        if not self.llm:
            return "文本文件描述信息不可用（未提供LLM）"

        content = self.read(file_path)
        if len(content) > 1000:
            content = content[:1000] + "..."  # 截断长文本

        prompt = f"为以下文本生成一个简洁的描述:\n\n{content}"
        return self.llm.invoke(prompt)


class DataBaseReader(FileReader):
    """数据库文件读取器"""

    def read(self, file_path: Union[Path, str]) -> str:
        """读取数据库文件内容"""
        file_path = Path(file_path)
        return file_path.read_text(encoding='utf-8')

    def description(self, file_path: Union[Path, str]) -> str:
        """生成数据库文件描述"""
        if not self.llm:
            return "数据库文件描述信息不可用（未提供LLM）"

        content = self.read(file_path)
        prompt = f"为以下数据库内容生成一个简洁的描述:\n\n{content}"
        return self.llm.invoke(prompt)


class ExcelFileReader(FileReader):
    """Excel文件读取器"""

    def read(self, file_path: Union[Path, str]) -> str:
        """读取Excel文件内容"""
        # file_path = Path(file_path)
        # return pd.read_excel(file_path).head(2).to_markdown()
        return "由于excel数据量过大，不提供明细数据，请参考'概要信息'"

    def description(self, file_path: Union[Path, str]) -> str:
        """生成Excel文件描述"""
        if not self.llm:
            return "Excel文件描述信息不可用（未提供LLM）"

        file_path = Path(file_path)
        file_name = file_path.name
        self.stream.stream_message(content=f'我正在对数据表进行分析。\n',
                                   content_type='m_text',
                                   interval=0.02)

        raw_data = pd.read_excel(file_path)
        data_str: str = raw_data.head(5).to_markdown()
        excel_desc_prompt = self.create_prompt(prompt=excel_prompt)
        excel_desc_prompt.update_placeholder(table_str=data_str)
        excel_desc: str = excel_desc_prompt.call(query=None, is_stream=True,
                                                 content_type='m_text', return_generator=False)

        return excel_desc


class CSVFileReader(FileReader):
    """CSV文件读取器"""

    def read(self, file_path: Union[Path, str]) -> str:
        """读取CSV文件内容"""
        file_path = Path(file_path)
        return pd.read_csv(file_path).to_markdown()

    def description(self, file_path: Union[Path, str]) -> str:
        """生成CSV文件描述"""
        if not self.llm:
            return "CSV文件描述信息不可用（未提供LLM）"

        content = self.read(file_path)
        prompt = f"为以下CSV数据生成一个简洁的描述:\n\n{content}"
        return self.llm.invoke(prompt)


class ImageFileReader(FileReader):

    def read(self, file_path: Union[Path, str]) -> str:
        # 复用描述的内容
        return self.desc

    def description(self, file_path: Union[Path, str]) -> str:
        from chatbi.models import Message
        from chatbi.utils.base64 import file_to_base64

        if not self.vision_llm:
            return "图片文件描述信息不可用（未提供视觉大模型）"

        file_path = Path(file_path)
        file_name = file_path.name
        file_suffix = file_path.suffix.lower().lstrip('.')

        self.stream.stream_message(content=f'我正在对图片进行分析。\n',
                                   content_type='m_text',
                                   interval=0.02)

        message = Message()
        img_b64 = file_to_base64(file_path=file_path)
        message.add_image(data=img_b64, format=file_suffix)

        image_desc_prompt = self.create_prompt(prompt=image_prompt, model=self.vision_llm)

        image_desc = image_desc_prompt.call(query=None, multimodal_message=message,
                                            content_type='m_text', return_generator=False,
                                            is_stream=True)

        self.desc = image_desc

        return image_desc


class FileReaderFactory:

    def __init__(self, **kwargs):
        self.params = kwargs
        pass

    # 映射文件扩展名到对应的读取器类
    READER_CLASSES: Dict[str, Type[FileReader]] = {
        'txt': TextFileReader,
        'md': TextFileReader,
        'json': TextFileReader,
        'xlsx': ExcelFileReader,
        'xls': ExcelFileReader,
        'csv': CSVFileReader,
        'png': ImageFileReader,
        'jpg': ImageFileReader,
        'gif': ImageFileReader,
        'jpeg': ImageFileReader,
        'db': DataBaseReader,
    }

    def get_reader(self, extension: str) -> Callable[[Path], Any]:
        """
        获取指定扩展名的读取函数

        Args:
            extension: 文件扩展名（不带点）

        Returns:
            读取函数
        """
        ext = extension.lower().lstrip('.')
        if ext not in FileReaderFactory.READER_CLASSES:
            raise ValueError(f"不支持的文件类型: {ext}")
        reader_class = FileReaderFactory.READER_CLASSES[ext]
        return reader_class(**self.params).read

    def create_reader(self, file_path: Union[Path, str],) -> FileReader:
        """
        根据文件路径创建适当的FileReader实例
        Args:
            file_path: 文件路径
        Returns:
            FileReader子类实例
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower().lstrip('.')

        if extension in FileReaderFactory.READER_CLASSES:
            reader_class = FileReaderFactory.READER_CLASSES[extension]
            return reader_class(**self.params)
        else:
            return TextFileReader(**self.params)

    def read_file(self, file_path: Union[Path, str]) -> Dict[str, str]:
        """
        读取文件内容并生成描述
        Args:
            file_path: 文件路径
        Returns:
            包含内容和描述的字典
        """
        reader = self.create_reader(file_path=file_path)
        content = reader.read(file_path)
        description = reader.description(file_path)

        FileReader.save_description(file_path, description)

        return {
            "content": content,
            "description": description
        }


if __name__ == '__main__':
    from chatbi.models import LLM

    lm = LLM(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
             api_key="sk-3d3f75c8f74b46ceb8397b69218667fd",
             model_name='qwen-vl-max-latest')

    ifr = ImageFileReader(vision_llm=lm)
    ifr.description(file_path='/Users/tiantiantian/Downloads/绘制卡通画.png')
