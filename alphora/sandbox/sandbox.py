import os
import sys
import subprocess
import contextlib
import shutil
import json
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from chatbi.mcp import MCPServer
import logging
from chatbi.sandbox.file_reader import FileReaderFactory, FileReader
from chatbi.utils.log import log_info, log_error
from chatbi.agent import BaseAgent
from chatbi.utils.base64 import base64_to_file
from chatbi.models import LLM


class Sandbox(BaseAgent):
    def __init__(self,
                 sandbox_path: str,
                 format_on_init: bool = False,
                 **kwargs):
        """
        创建一个Python代码执行沙箱

        Args:
            sandbox_path: 沙箱目录路径，如果为None则创建临时目录
        """
        super(Sandbox, self).__init__(**kwargs)
        self.sandbox_path = sandbox_path

        if self.sandbox_path is None:
            raise ValueError("Sandbox path is None")

        # 检查路径是否已存在，存在则不执行初始化
        if os.path.exists(self.sandbox_path):
            logging.info(f"沙箱路径已存在: {self.sandbox_path}，跳过初始化")
        else:
            if format_on_init:
                self.format_sandbox(confirm=True)
            self._sandbox_init()

    def _sandbox_init(self) -> None:
        """初始化沙箱环境"""
        self._ensure_dir_exists(self.sandbox_path)

        self.create_sandbox(session_id=int(time.time()))

        # 注册沙箱目录资源
        self.register_directory_with_files(
            directory_path=self.sandbox_path,
            uri_prefix="files://",
            recursive=False,
            exclude_patterns=[r"/\..*", r"__pycache__", r".*\.description$"]  # 排除隐藏文件和缓存
        )

        # 检查现有文件是否有描述信息，没有则生成
        self._check_existing_files()

    def _check_existing_files(self) -> None:
        """检查沙箱中现有文件是否有描述信息，没有则生成"""
        sandbox_root = Path(self.sandbox_path)

        for root, dirs, files in os.walk(sandbox_root):
            # 过滤隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                # if file.startswith('.'):  # 过滤以 . 开头的文件
                if file.endswith('.description'):  # 过滤描述文件
                    continue

                file_path = Path(root) / file

                # 检查文件是否有描述信息
                description = FileReader.read_description(file_path)
                if not description:
                    print('未发现描述文件')
                    try:
                        # 使用FileReaderFactory生成描述
                        description = self._generate_file_description(file_path)
                        if description:
                            # 保存描述到隐藏文件
                            FileReader.save_description(file_path, description)
                    except Exception as e:
                        logging.warning(f"无法为文件 {file_path} 生成描述: {str(e)}")

    def _generate_file_description(self, file_path: Path) -> str:
        """生成文件描述信息"""
        try:
            # 使用FileReaderFactory读取文件并生成描述
            file_info = FileReaderFactory(**self.init_params).read_file(file_path=file_path)
            return file_info["description"]
        except Exception as e:
            logging.warning(f"生成文件描述失败: {str(e)}")
            return ""

    def _ensure_dir_exists(self, path: str) -> None:
        """确保目录存在，增强安全校验"""
        normalized_path = os.path.normpath(path)
        if not normalized_path.startswith(self.sandbox_path):
            raise ValueError(f"非法路径: {path}")
        Path(normalized_path).mkdir(parents=True, exist_ok=True)

    def create_sandbox(self, session_id: int) -> None:
        """创建沙箱环境，添加初始化文件"""
        sandbox_root = Path(self.sandbox_path)

        logging.info(f"沙箱已创建: {self.sandbox_path}, session_id: {session_id}")

    def read_files(self, with_description: bool = False) -> List[Dict[str, Any]]:
        """
        读取沙箱中所有文件信息.
        Returns:
            文件列表，包含文件名、大小、修改时间、类型等信息
        """
        file_list = []
        sandbox_root = Path(self.sandbox_path)

        for root, dirs, files in os.walk(sandbox_root):
            # 过滤隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                # if file.startswith('.'):  # 过滤以 . 开头的文件
                if file.endswith('.description'):  # 过滤描述文件
                    continue

                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(sandbox_root))

                try:
                    stat = file_path.stat()
                    file_info = {
                        "name": rel_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "created": stat.st_ctime,
                        "type": "directory" if file_path.is_dir() else "file",
                        "extension": file_path.suffix.lower()[1:] if file_path.suffix else ""
                    }

                    if with_description:
                        # 从隐藏文件读取描述信息
                        description = FileReader.read_description(file_path)
                        file_info["description"] = description

                    file_list.append(file_info)

                except OSError as e:
                    logging.warning(f"无法访问文件: {file_path}, 错误: {e}")

        return file_list

    def list_resource(self) -> List[Dict[str, Any]]:
        """
        列出沙盒下所有文件的content和description

        Returns:
            包含文件名、content和description的列表
        """
        resource_list = []
        sandbox_root = Path(self.sandbox_path)

        # 遍历所有文件（排除隐藏文件和描述文件）
        for file_path in sandbox_root.glob('**/*'):
            if file_path.is_dir() or file_path.name.startswith('.') or file_path.name.endswith('.description'):
                continue

            try:
                file_info = self.read_file(str(file_path.relative_to(sandbox_root)))
                resource_list.append({
                    "文件名": str(file_path.relative_to(sandbox_root)),
                    "内容": file_info["内容"],
                    "概要信息": file_info["概要信息"]
                })
            except Exception as e:
                logging.warning(f"获取文件资源失败: {file_path}, 错误: {e}")

        return resource_list

    @MCPServer.tool()
    def execute_python(self, file_name: str) -> str:
        """
        执行Python代码文件
        Args:
            file_name: 要执行的Python文件名
        Returns:
            包含标准输出、标准错误和返回码的元组
        """

        file_path = Path(self.sandbox_path) / file_name

        if not file_path.is_file():
            raise FileNotFoundError(f"文件不存在: {file_name}")
        if file_path.suffix.lower() != '.py':
            raise ValueError(f"不是有效的Python文件: {file_name}")

        # 限制执行环境
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.sandbox_path)
        env["SANDBOX_SECURE"] = "1"  # 标记安全执行环境

        try:
            result = subprocess.run(
                [sys.executable, str(file_path)],
                cwd=self.sandbox_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 1:
                raise RuntimeError(f"执行错误: {result.stderr}")

            else:
                return result.stdout

            # return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired:
            raise "执行超时"
        except Exception as e:
            raise f"执行错误: {str(e)}"

    @MCPServer.tool()
    def save_file(self, content: str, file_name: str) -> None:
        """创建名为file_name的文件(需带文件后缀，例如README.md)，并将content提供的内容写入进去，内容长度不限"""
        target_path = Path(self.sandbox_path) / file_name
        # 防止路径穿越
        if not str(target_path).startswith(self.sandbox_path):
            raise ValueError("非法的文件路径，禁止路径穿越")

        # 确保目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        target_path.write_text(content, encoding='utf-8')
        logging.info(f"文件已保存: {target_path}")

        # 生成并保存文件描述
        try:
            # 使用FileReaderFactory读取文件并生成描述
            file_info = FileReaderFactory(**self.init_params).read_file(file_path=target_path)
            if file_info["description"]:
                FileReader.save_description(target_path, file_info["description"])
        except Exception as e:
            logging.warning(f"无法为文件 {target_path} 生成描述: {str(e)}")

    @MCPServer.tool()
    def read_file(self, file_name: str) -> Dict[str, Any]:
        """读取指定文件内容和描述，返回包含content和description的字典"""

        target_path = Path(self.sandbox_path) / file_name

        if not target_path.is_file():
            raise FileNotFoundError(f"文件不存在: {file_name}")

        try:
            # 检查描述文件是否存在
            description_path = target_path.with_name(f"{target_path.name}.description")
            if description_path.exists():
                # 读取描述文件内容
                description = description_path.read_text(encoding='utf-8')
                # 读取文件内容
                reader = FileReaderFactory(**self.init_params).create_reader(file_path=target_path)
                content = reader.read(file_path=target_path)
            else:
                # 使用FileReaderFactory读取文件内容和描述
                file_info = FileReaderFactory(**self.init_params).read_file(file_path=target_path)
                description = file_info["description"]
                content = file_info["content"]

            return {
                "内容": content,
                "概要信息": description
            }

        except Exception as e:
            raise ValueError(f"文件读取错误: {str(e)}") from e

    def delete_file(self, file_name: str) -> bool:
        """删除沙箱中的文件及其描述文件"""
        target_path = Path(self.sandbox_path) / file_name
        if not target_path.exists():
            return False

        # 删除描述文件
        # description_path = target_path.with_name(f".{target_path.name}.description")
        description_path = target_path.with_name(f"{target_path.name}.description")

        if description_path.exists():
            description_path.unlink()

        # 删除原文件
        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
        return True

    def install_package(self, package_name: str) -> Dict[str, Any]:
        """安装Python包到沙箱环境"""
        requirements_path = Path(self.sandbox_path) / "requirements.txt"
        current_packages = requirements_path.read_text(encoding='utf-8').splitlines()

        # 检查是否已安装
        if any(package_name in line for line in current_packages if not line.startswith('#')):
            return {"status": "already_installed", "package": package_name}

        # 添加到requirements.txt
        with requirements_path.open('a', encoding='utf-8') as f:
            f.write(f"{package_name}\n")

        # 执行安装
        stdout, stderr, code = self.execute_python(
            "src/install_package.py",
            timeout=60
        )

        return {
            "status": "success" if code == 0 else "failed",
            "package": package_name,
            "stdout": stdout,
            "stderr": stderr
        }

    @contextlib.contextmanager
    def redirect_stdio(self, stdout_path: str, stderr_path: str):
        """
        重定向标准输出和标准错误，支持Path对象
        """
        stdout_path = Path(self.sandbox_path) / stdout_path
        stderr_path = Path(self.sandbox_path) / stderr_path

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            with stdout_path.open('w') as f_stdout, stderr_path.open('w') as f_stderr:
                sys.stdout = f_stdout
                sys.stderr = f_stderr
                yield
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    def format_sandbox(self, confirm: bool = False) -> Dict[str, Any]:
        """
        安全格式化沙箱目录（清空所有数据）
        """
        # 安全确认机制（防止误操作）
        if not confirm:
            raise ValueError("格式化操作未确认，请设置confirm=True强制执行")

        start_time = time.time()
        sandbox_path = Path(self.sandbox_path)

        # 路径安全校验（防止越权操作）
        if not str(sandbox_path).startswith(self.sandbox_path):
            raise ValueError(f"非法格式化路径: {sandbox_path}")

        # 统计并删除文件
        file_count = 0
        dir_count = 0

        try:
            # 递归删除沙箱内所有内容
            for root, dirs, files in os.walk(sandbox_path, topdown=False):
                for f in files:
                    file_path = os.path.join(root, f)
                    os.remove(file_path)
                    file_count += 1
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    os.rmdir(dir_path)
                    dir_count += 1

            # 删除空的根目录（重新创建）
            if os.path.exists(sandbox_path):
                os.rmdir(sandbox_path)

            # 重新初始化沙箱环境
            self._sandbox_init()

            return {
                "status": "success",
                "message": "沙箱格式化完成",
                "deleted_files": file_count,
                "deleted_dirs": dir_count,
                "elapsed_seconds": round(time.time() - start_time, 2)
            }

        except Exception as e:
            return {
                "status": "failed",
                "message": f"格式化失败: {str(e)}",
                "deleted_files": file_count,
                "deleted_dirs": dir_count,
                "error": str(e)
            }

    def upload_file(self,
                    base64_content: str,
                    target_file_name: str) -> str:
        """
        将Base64编码的文件内容载入到沙箱环境中
        """

        target_path = Path(self.sandbox_path)

        if target_file_name:
            target_path /= target_file_name
        else:
            raise ValueError("target_file_name不能为空")

        if not str(target_path).startswith(self.sandbox_path):
            raise ValueError("非法的目标路径，禁止路径穿越")

        try:
            base64_to_file(base64_content, target_path)
            logging.info(f"Base64文件已载入: {target_path}")

            file_info = FileReaderFactory(**self.init_params).read_file(
                file_path=target_path
            )

            if file_info["description"]:
                FileReader.save_description(target_path, file_info["description"])
                return file_info["description"]

            return ""

        except Exception as e:
            raise e

    def is_empty(self) -> bool:
        """
        判断沙箱目录是否为空（不包含有效文件，忽略隐藏文件和描述文件）

        Returns:
            bool: 沙箱为空返回True，否则返回False
        """
        sandbox_root = Path(self.sandbox_path)

        if not sandbox_root.exists():
            return True  # 路径不存在视为空

        # 遍历目录检查是否有有效文件
        for root, dirs, files in os.walk(sandbox_root):
            # 过滤隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            # 过滤隐藏文件和描述文件
            valid_files = [
                f for f in files
                if not f.startswith('.') and not f.endswith('.description')
            ]

            if valid_files:
                return False  # 存在有效文件，不为空

        return True  # 无有效文件，视为空

    def destroy(self, confirm: bool = False) -> None:
        """
        销毁沙箱（彻底删除沙箱目录及所有内容）

        Args:
            confirm: 是否确认销毁，必须设置为True才会执行删除操作
        """
        if not confirm:
            logging.error("销毁操作未确认，请设置confirm=True强制执行")
            return

        start_time = time.time()
        sandbox_root = Path(self.sandbox_path)

        # 安全校验：防止删除非沙箱路径
        if not str(sandbox_root).startswith(self.sandbox_path):
            logging.error(f"非法销毁路径: {sandbox_root}")
            return

        try:
            if not sandbox_root.exists():
                logging.info(f"沙箱路径不存在，无需销毁: {sandbox_root}")
                return

            # 统计并删除所有内容
            file_count = 0
            dir_count = 0

            # 先删除文件
            for root, dirs, files in os.walk(sandbox_root, topdown=False):
                for f in files:
                    file_path = os.path.join(root, f)
                    os.remove(file_path)
                    file_count += 1
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    os.rmdir(dir_path)
                    dir_count += 1

            # 最后删除根目录
            os.rmdir(sandbox_root)

            elapsed = round(time.time() - start_time, 2)
            logging.info(
                f"沙箱已成功销毁: {sandbox_root} "
                f"[删除文件: {file_count}, 删除目录: {dir_count}, 耗时: {elapsed}秒]"
            )

        except Exception as e:
            logging.error(
                f"沙箱销毁失败: {sandbox_root}, 错误: {str(e)} ", exc_info=True
            )
            return


if __name__ == '__main__':
    from chatbi.models import LLM
    from chatbi.utils.base64 import file_to_base64

    img_file = "/Users/tiantiantian/工作/梧桐ChatBI/3-测评/交通主题/交通工具数据.xlsx"
    img_b64 = file_to_base64(img_file)

    vllm = LLM(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
               api_key="sk-3d3f75c8f74b46ceb8397b69218667fd",
               model_name='qwen-vl-max-latest')

    llm = LLM()

    sb = Sandbox(sandbox_path='/Users/tiantiantian/临时/chatbi_workspace/sandbox/test',
                 llm=llm,
                 vision_llm=vllm)

    sb.upload_file(base64_content=img_b64, target_file_name='交通数据.xlsx')
    sb.list_resource()
