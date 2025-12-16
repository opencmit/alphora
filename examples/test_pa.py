from alphora.utils.parallel import parallel_run, parallel_run_heterogeneous
import asyncio


class Demo:
    def __init__(self, name):
        self.name = name

    def sync_task(self, x=0):
        import time
        time.sleep(5)
        return f"{self.name}_sync({x})"

    async def async_task(self, y=0):
        await asyncio.sleep(0.2)
        return f"{self.name}_async({y})"

    def health(self):
        return f"{self.name}_healthy"


if __name__ == "__main__":
    a = Demo("A")
    b = Demo("B")
    c = Demo("C")

    # 同构调用
    print("=== parallel_run (同构) ===")
    res1 = parallel_run([
        (a, (1,)),
        b,
        (c, (3,), {})
    ], method_name="sync_task")
    print(res1)

    # 异构调用
    print("\n=== parallel_run_heterogeneous (异构) ===")
    res2 = parallel_run_heterogeneous([
        (a, "sync_task", (10,)),
        (b, "async_task", (20,)),
        (c, "health"),
        (a, "async_task", (99,))
    ])
    print(res2)