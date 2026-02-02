"""
Alphora Sandbox

This example demonstrates how to integrate the sandbox with AI agents
using OpenAI and Anthropic function calling.
"""
import asyncio
import json
from typing import Dict, Any, List

from alphora.sandbox import Sandbox, SandboxTools


async def simulate_openai_agent():
    """
    Simulates an OpenAI-style function calling agent.
    
    In a real implementation, you would:
    1. Send messages to OpenAI with tool definitions
    2. Receive tool_calls from the response
    3. Execute tools and return results
    """
    print("=" * 60)
    print("OpenAI Function Calling Simulation")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        tools = SandboxTools(sandbox)
        
        # Get tool definitions for OpenAI
        tool_definitions = tools.get_openai_tools()
        print(f"Registered {len(tool_definitions)} tools")
        
        # Simulate tool calls from OpenAI
        simulated_tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "run_python_code",
                    "arguments": json.dumps({"code": "print(sum(range(10)))"})
                }
            },
            {
                "id": "call_2", 
                "type": "function",
                "function": {
                    "name": "save_file",
                    "arguments": json.dumps({
                        "path": "analysis.py",
                        "content": "data = [1, 2, 3, 4, 5]\nprint(f'Sum: {sum(data)}')"
                    })
                }
            },
            {
                "id": "call_3",
                "type": "function",
                "function": {
                    "name": "run_python_file",
                    "arguments": json.dumps({"file_path": "analysis.py"})
                }
            }
        ]
        
        # Process tool calls
        for call in simulated_tool_calls:
            func_name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])
            
            print(f"\n[Tool Call] {func_name}")
            print(f"Arguments: {args}")
            
            # Execute tool
            result = await tools.execute_tool(func_name, args)
            print(f"Result: {result}")


async def simulate_anthropic_agent():
    """
    Simulates an Anthropic-style tool use agent.
    """
    print("\n" + "=" * 60)
    print("Anthropic Tool Use Simulation")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        tools = SandboxTools(sandbox)
        
        # Get tool definitions for Anthropic
        tool_definitions = tools.get_anthropic_tools()
        print(f"Registered {len(tool_definitions)} tools")
        
        # Simulate tool use blocks from Claude
        simulated_tool_uses = [
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "run_python_code",
                "input": {
                    "code": """
import math
radius = 5
area = math.pi * radius ** 2
print(f"Circle area with radius {radius}: {area:.2f}")
"""
                }
            },
            {
                "type": "tool_use",
                "id": "toolu_02",
                "name": "list_files",
                "input": {"path": "", "recursive": False}
            }
        ]
        
        # Process tool uses
        for tool_use in simulated_tool_uses:
            name = tool_use["name"]
            inputs = tool_use["input"]
            
            print(f"\n[Tool Use] {name}")
            
            # Execute tool
            result = await tools.execute_tool(name, inputs)
            
            # Format as tool_result
            tool_result = {
                "type": "tool_result",
                "tool_use_id": tool_use["id"],
                "content": json.dumps(result) if isinstance(result, dict) else str(result)
            }
            print(f"Result: {tool_result}")


async def interactive_code_assistant():
    """
    Example of an interactive code assistant that uses sandbox tools.
    """
    print("\n" + "=" * 60)
    print("Interactive Code Assistant Demo")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        tools = SandboxTools(sandbox)
        
        # Simulate a conversation
        tasks = [
            ("Create a function to calculate fibonacci", """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Test
for i in range(10):
    print(f"fib({i}) = {fibonacci(i)}")
"""),
            ("Now make it iterative for better performance", """
def fibonacci_iter(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

# Test with larger numbers
import time
start = time.time()
result = fibonacci_iter(100)
elapsed = time.time() - start
print(f"fib(100) = {result}")
print(f"Time: {elapsed:.6f}s")
"""),
            ("Save this to a file for later use", None),
        ]
        
        for i, (task, code) in enumerate(tasks, 1):
            print(f"\n[Task {i}] {task}")
            
            if code:
                # Execute code
                result = await tools.run_python_code(code)
                print(f"Output:\n{result['output']}")
                
                # Save to file
                if i == 2:  # Save the iterative version
                    await tools.save_file("fibonacci.py", code)
                    print("(Saved to fibonacci.py)")
            else:
                # List files to show saved code
                files = await tools.list_files()
                print(f"Files in workspace: {[f['name'] for f in files['output']]}")


async def data_pipeline_example():
    """
    Example of using sandbox for data processing pipeline.
    """
    print("\n" + "=" * 60)
    print("Data Pipeline Example")
    print("=" * 60)
    
    async with Sandbox.create_local() as sandbox:
        tools = SandboxTools(sandbox)
        
        # Step 1: Create sample data
        print("\n[Step 1] Creating sample data...")
        data_code = '''
import json

data = {
    "users": [
        {"id": 1, "name": "Alice", "purchases": [100, 200, 150]},
        {"id": 2, "name": "Bob", "purchases": [50, 75]},
        {"id": 3, "name": "Charlie", "purchases": [200, 300, 100, 50]},
    ]
}

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)

print("Data saved to data.json")
print(json.dumps(data, indent=2))
'''
        result = await tools.run_python_code(data_code)
        print(result["output"])
        
        # Step 2: Process data
        print("\n[Step 2] Processing data...")
        process_code = '''
import json

with open("data.json") as f:
    data = json.load(f)

# Calculate statistics
results = []
for user in data["users"]:
    total = sum(user["purchases"])
    avg = total / len(user["purchases"])
    results.append({
        "name": user["name"],
        "total_purchases": total,
        "average_purchase": round(avg, 2),
        "num_purchases": len(user["purchases"])
    })

# Sort by total purchases
results.sort(key=lambda x: x["total_purchases"], reverse=True)

# Save results
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("Analysis Results:")
for r in results:
    print(f"  {r['name']}: ${r['total_purchases']} total, ${r['average_purchase']} avg")
'''
        result = await tools.run_python_code(process_code)
        print(result["output"])
        
        # Step 3: Generate report
        print("\n[Step 3] Generating report...")
        report_code = '''
import json

with open("results.json") as f:
    results = json.load(f)

total_revenue = sum(r["total_purchases"] for r in results)
top_customer = results[0]["name"]

report = f"""
# Sales Report
===============

Total Revenue: ${total_revenue}
Top Customer: {top_customer}

## Customer Breakdown
"""

for r in results:
    report += f"- {r['name']}: ${r['total_purchases']} ({r['num_purchases']} purchases)\\n"

print(report)

with open("report.md", "w") as f:
    f.write(report)

print("\\nReport saved to report.md")
'''
        result = await tools.run_python_code(report_code)
        print(result["output"])
        
        # List all generated files
        print("\n[Final] Generated files:")
        files = await tools.list_files()
        for f in files["output"]:
            print(f"  - {f['name']} ({f['size']} bytes)")


async def main():
    """Run all examples."""
    await simulate_openai_agent()
    await simulate_anthropic_agent()
    await interactive_code_assistant()
    await data_pipeline_example()


if __name__ == "__main__":
    asyncio.run(main())
