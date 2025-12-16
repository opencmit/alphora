import os
import sys
import subprocess
import tempfile
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, TypedDict


class CodeExecutionResult(TypedDict):
    status: str          # "success" or "error"
    stdout: str          # 标准输出（已截断）
    stderr: str          # 标准错误（已清理路径、已截断）
    exit_code: int       # 子进程退出码（0 表示成功）
    message: str         # 人类可读摘要（可用于日志或 UI）


def run_python_code(
        code_str: str,
        base_dir: str,
        *,
        timeout: int = 10,
        python_executable: str = sys.executable,
        env_vars: Optional[Dict[str, str]] = None,
        max_output_length: int = 100_000,
        log_execution: bool = True,
        hide_temp_filename: bool = True,
) -> CodeExecutionResult:
    """
    安全执行 Python 代码，返回结构化结果，便于程序化判断状态。

    所有异常均被捕获，不会抛出任何异常。
    """
    # 参数校验
    if not isinstance(code_str, str):
        return {
            "status": "error",
            "stdout": "",
            "stderr": "code_str must be a string",
            "exit_code": -1,
            "message": "❌ Invalid input: code_str must be a string"
        }
    if not code_str.strip():
        return {
            "status": "success",
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "message": "✅ Empty code executed successfully"
        }

    try:
        base_path = Path(base_dir).resolve()
        if not base_path.is_absolute():
            err_msg = f"base_dir must be an absolute path, got: {base_dir}"
            return {
                "status": "error",
                "stdout": "",
                "stderr": err_msg,
                "exit_code": -1,
                "message": f"❌ {err_msg}"
            }
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "message": f"❌ Failed to resolve base_dir: {e}"
        }

    try:
        base_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "message": f"❌ Failed to create base_dir: {e}"
        }

    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', dir=str(base_path), delete=False, encoding='utf-8'
        ) as f:
            f.write(code_str)
            temp_file = f.name

        if log_execution:
            print(f"[INFO] Executing code in: {base_path}, timeout={timeout}s")

        start_time = time.time()
        try:
            result = subprocess.run(
                [python_executable, temp_file],
                cwd=str(base_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            elapsed = time.time() - start_time
            if log_execution:
                print(f"[INFO] Execution finished in {elapsed:.2f}s")
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            stderr_msg = f"Code execution timed out after {elapsed:.2f}s (limit: {timeout}s)"
            return {
                "status": "error",
                "stdout": "",
                "stderr": stderr_msg,
                "exit_code": -2,  # 自定义超时码
                "message": f"❌ {stderr_msg}"
            }

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # 清理 traceback 中的路径
        if temp_file and stderr:
            replacement = "code.py" if hide_temp_filename else os.path.basename(temp_file)
            escaped_path = re.escape(temp_file)
            stderr = re.sub(escaped_path, replacement, stderr)

        # 截断
        if len(stdout) > max_output_length:
            stdout = stdout[:max_output_length] + "\n[OUTPUT TRUNCATED]"
        if len(stderr) > max_output_length:
            stderr = stderr[:max_output_length] + "\n[ERROR OUTPUT TRUNCATED]"

        # 构造结果
        if result.returncode == 0:
            return {
                "status": "success",
                "stdout": stdout,
                "stderr": stderr,  # 可能有警告信息
                "exit_code": 0,
                "message": "✅ Code executed successfully"
            }
        else:
            # 错误情况：只在 stdout 非空时才包含它（可选，这里保留原始数据）
            return {
                "status": "error",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
                "message": f"❌ Code failed with exit code {result.returncode}"
            }

    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "exit_code": -3,
            "message": f"❌ Internal executor error: {e}"
        }

    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                if log_execution:
                    print(f"[DEBUG] Cleaned up: {temp_file}")
            except OSError:
                pass


if __name__ == "__main__":

    code = """
import pandasx
with open("text.txt", "w") as f:
    f.write("Hello from safe sandbox!")
print("File created! Check your base_dir for 'test.txt'")
    """

    base_dir = "/Users/tiantiantian/Code/alphadata-ms/svc-chatexcel/example"

    result = run_python_code(code_str=code, base_dir=base_dir)
    print(result)