from alphora.prompter.base import BasePrompt, PrompterOutput
from alphora.utils.parallel import parallel_run, parallel_run_heterogeneous
from typing import List, Iterable
import asyncio


class ParallelPrompt(BasePrompt):

    def __init__(self, prompts: List["BasePrompt"] | Iterable["BasePrompt"]):
        self.prompts = list(prompts)

        if not self.prompts:
            raise ValueError("At least one prompt is required.")

        # 验证所有元素都是BasePrompt实例
        for p in self.prompts:
            if not isinstance(p, BasePrompt):
                raise TypeError("All elements must be instances of BasePrompt")

        super().__init__(template_path=None)

        self.prompt = None
        self.content = ""
        self.placeholders = []

    def render(self) -> str:
        # 不适用
        return "[ParallelPrompt: multiple sub-prompts]"

    def call(self, *args, **kwargs):
        calls = []
        for p in self.prompts:
            calls.append((p, args, kwargs))
        results = parallel_run(calls, method_name='call')
        output_tuple = tuple(results)

        return [result for result in output_tuple]

    async def acall(self, *args, **kwargs):
        calls = [(p, 'acall', args, kwargs) for p in self.prompts]
        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: parallel_run_heterogeneous(calls)
        ) if False else await _async_parallel_run(self.prompts, args, kwargs)
        return [result for result in results]


async def _async_parallel_run(prompts, args, kwargs):
    tasks = [p.acall(*args, **kwargs) for p in prompts]
    return await asyncio.gather(*tasks)

