"""
Alphora Sandbox - Basic Usage Examples

This file demonstrates the basic usage patterns for the sandbox component.
"""
import asyncio
from alphora.sandbox import (
    Sandbox,
    SandboxTools,
    SandboxManager,
    ResourceLimits,
    SecurityPolicy,
)


async def example_basic_usage():
    """Basic sandbox usage with context manager."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)

    sandbox = Sandbox.create_docker()
    await sandbox.start()
    result = await sandbox.execute_shell(command='pwd')
    print(result)
    result = await sandbox.run("print('Hello, Sandbox!')")
    print(f"Output: {result.stdout}")
    print(f"Success: {result.success}")
    print(f"Execution time: {result.execution_time:.3f}s")
    await sandbox.stop()

    #  ------------ 使用上下文来创建管理 ------------------
    async with Sandbox.create_local() as sandbox:
        result = await sandbox.run("print('Hello, Sandbox docker!')")
        print(f"Output: {result.stdout}")
        print(f"Success: {result.success}")
        print(f"Execution time: {result.execution_time:.3f}s")


async def example_file_operations():
    """File operations in sandbox."""
    print("\n" + "=" * 60)
    print("Example 2: File Operations")
    print("=" * 60)
    
    async with Sandbox.create_docker() as sandbox:
        # Save a Python file
        code = '''
def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
'''
        await sandbox.write_file("greet.py", code)
        print("Created greet.py")
        
        # List files
        files = await sandbox.list_files()
        print(f"Files in workspace: {[f.name for f in files]}")
        
        # Execute the file
        result = await sandbox.execute_file("greet.py")
        print(f"Output: {result.stdout}")
        
        # Read file back
        content = await sandbox.read_file("greet.py")
        print(f"File content ({len(content)} chars)")


async def example_data_analysis():
    """Data analysis with pandas."""
    print("\n" + "=" * 60)
    print("Example 3: Data Analysis")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        # Install pandas (may already be installed)
        await sandbox.execute_shell("pip install pandas -q")
        
        # Run data analysis
        code = '''
import pandas as pd
import json

# Create sample data
data = {
    'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'age': [25, 30, 35, 28],
    'city': ['NYC', 'LA', 'Chicago', 'NYC']
}
df = pd.DataFrame(data)

# Analysis
print("=== Data Summary ===")
print(f"Total records: {len(df)}")
print(f"Average age: {df['age'].mean():.1f}")
print(f"Cities: {df['city'].unique().tolist()}")

# Group by city
print("\\n=== By City ===")
print(df.groupby('city')['age'].mean().to_string())
'''
        result = await sandbox.run(code)
        print(result.stdout)


async def example_with_tools():
    """Using SandboxTools for AI agent integration."""
    print("\n" + "=" * 60)
    print("Example 4: AI Agent Tools")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        tools = SandboxTools(sandbox)
        
        # List available tools
        print(f"Available tools: {tools.get_available_tools()[:5]}...")
        
        # Execute using tools interface
        result = await tools.run_python_code("print(2 ** 10)")
        print(f"Tool result: {result}")
        
        # Save and read file
        await tools.save_file("data.txt", "Hello from tools!")
        content = await tools.read_file("data.txt")
        print(f"File content: {content['output']}")
        
        # Get tool definitions (for LLM function calling)
        openai_tools = tools.get_openai_tools()
        print(f"OpenAI tool count: {len(openai_tools)}")


async def example_resource_limits():
    """Sandbox with resource limits."""
    print("\n" + "=" * 60)
    print("Example 5: Resource Limits")
    print("=" * 60)
    
    # Configure limits
    limits = ResourceLimits(
        timeout_seconds=10,
        memory_mb=256,
        cpu_cores=1.0,
    )
    
    async with Sandbox.create_local(resource_limits=limits) as sandbox:
        # Normal execution
        result = await sandbox.run("print('Quick task')")
        print(f"Output: {result.stdout}")
        
        # Timeout demonstration
        code = '''
import time
for i in range(100):
    print(f"Step {i}")
    time.sleep(0.2)
'''
        result = await sandbox.run(code, timeout=2)
        if not result.success:
            print(f"Timed out as expected: {result.error}")


async def example_multi_sandbox():
    """Managing multiple sandboxes."""
    print("\n" + "=" * 60)
    print("Example 6: Multi-Sandbox Management")
    print("=" * 60)
    
    async with SandboxManager() as manager:
        # Create multiple sandboxes
        sandbox1 = await manager.create_sandbox(name="worker-1")
        sandbox2 = await manager.create_sandbox(name="worker-2")
        
        print(f"Created {manager.sandbox_count} sandboxes")
        
        # Run tasks in parallel
        results = await asyncio.gather(
            sandbox1.run("print('Result from worker 1')"),
            sandbox2.run("print('Result from worker 2')")
        )
        
        for i, result in enumerate(results, 1):
            print(f"Worker {i}: {result.stdout.strip()}")
        
        # Get manager status
        status = await manager.get_status()
        print(f"Manager status: {status['sandbox_count']} sandboxes")


async def example_error_handling():
    """Error handling in sandbox."""
    print("\n" + "=" * 60)
    print("Example 7: Error Handling")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        # Syntax error
        result = await sandbox.run("print('missing quote)")
        print(f"Syntax error caught: {result.success=}, error={result.stderr[:50]}...")
        
        # Runtime error
        result = await sandbox.run("x = 1/0")
        print(f"Runtime error caught: {result.success=}, error={result.stderr[:50]}...")
        
        # Import error
        result = await sandbox.run("import nonexistent_module")
        print(f"Import error caught: {result.success=}")


async def main():
    """Run all examples."""
    print("Alphora Sandbox - Examples")
    print("=" * 60)
    
    await example_basic_usage()
    await example_file_operations()
    await example_data_analysis()
    await example_with_tools()
    await example_resource_limits()
    await example_multi_sandbox()
    await example_error_handling()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
