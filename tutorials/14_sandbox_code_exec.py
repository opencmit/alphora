"""
Tutorial 14: Sandbox code execution, security policy, storage, docker.

Run:
  python tutorials/14_sandbox_code_exec.py
"""

import asyncio
import tempfile
from pathlib import Path

from alphora.sandbox import Sandbox
from alphora.sandbox.types import ResourceLimits, SecurityPolicy
from alphora.sandbox.storage.local import LocalStorage
from alphora.sandbox.config import StorageConfig


async def main() -> None:
    limits = ResourceLimits.minimal()
    policy = SecurityPolicy.strict()

    async with Sandbox.create_local(resource_limits=limits, security_policy=policy) as sandbox:
        result = await sandbox.execute_code(
            "print('Hello from sandbox')\n"
            "x = 6 * 7\n"
            "print('x =', x)\n"
        )

        print("=== Execution Result ===")
        print("stdout:", result.stdout.strip())
        print("stderr:", result.stderr.strip())

        await sandbox.write_file("note.txt", "sandbox file content")
        files = await sandbox.list_files(".")

        print("\n=== Files ===")
        for f in files:
            print(f"- {f.path} (dir={f.is_directory}, size={f.size})")

    # Storage-mounted sandbox (persistent workspace)
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalStorage(StorageConfig.local(tmp))
        async with storage:
            sandbox = Sandbox.create_local(storage=storage)
            async with sandbox:
                await sandbox.write_file("persist.txt", "hello storage")
                files = await sandbox.list_files(".")
                print("\n=== Storage-mounted Files ===")
                for f in files:
                    print(f"- {f.path}")

    # Docker sandbox (requires docker & image)
    sandbox = Sandbox.create_docker(docker_image="alphora-sandbox:latest")
    async with sandbox:
        result = await sandbox.execute_code("print('docker sandbox')")
        print(result.stdout.strip())


if __name__ == "__main__":
    asyncio.run(main())
