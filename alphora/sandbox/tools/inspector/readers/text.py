"""纯文本 / 代码文件 Reader"""

from alphora.sandbox.tools.inspector.readers import FileContent, get_file_type


def read(content: str, path: str, size: int, **_kwargs) -> FileContent:
    lines = content.splitlines()
    return FileContent(
        text=content,
        total_lines=len(lines),
        file_type=get_file_type(path),
        size=size,
    )
