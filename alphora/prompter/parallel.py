from alphora.prompter.base_prompter import BasePrompt, PrompterOutput
from alphora.utils.parallel import parallel_run, parallel_run_heterogeneous
from typing import List, Iterable
import asyncio


class _PromptPrefixedCallback:
    """Lightweight prefix wrapper (same idea as ``_PrefixedCallback`` in base_agent)."""

    def __init__(self, callback, prefix: str):
        self._callback = callback
        self._prefix = prefix

    async def send_data(self, content_type: str, content: str = None):
        if self._callback:
            await self._callback.send_data(
                content_type=f"{self._prefix}:{content_type}",
                content=content,
            )

    async def stop(self, stop_reason="stop"):
        pass


class ParallelPrompt(BasePrompt):

    def __init__(self, prompts: List["BasePrompt"] | Iterable["BasePrompt"]):
        self.prompts = list(prompts)

        if not self.prompts:
            raise ValueError("At least one prompt is required.")

        for p in self.prompts:
            if not isinstance(p, BasePrompt):
                raise TypeError("All elements must be instances of BasePrompt")

        super().__init__(template_path=None)

        self.prompt = None
        self.content = ""
        self.placeholders = []

    def render(self) -> str:
        return "[ParallelPrompt: multiple sub-prompts]"

    def call(self, *args, **kwargs):
        calls = []
        for p in self.prompts:
            calls.append((p, args, kwargs))
        results = parallel_run(calls, method_name='call')
        output_tuple = tuple(results)

        return [result for result in output_tuple]

    async def acall(self, *args, **kwargs):
        any_has_callback = any(p.callback for p in self.prompts)

        cli_streamer = None
        if not any_has_callback:
            from alphora.cli import create_cli_streamer
            labels = [
                f"{type(p).__name__}_{i}" for i, p in enumerate(self.prompts)
            ]
            cli_streamer = create_cli_streamer(agent_labels=labels)

            saved_callbacks = [p.callback for p in self.prompts]
            for i, p in enumerate(self.prompts):
                p.callback = _PromptPrefixedCallback(cli_streamer, f"parallel_{i}")

        if cli_streamer is not None:
            cli_streamer.start()

        try:
            results = await _async_parallel_run(self.prompts, args, kwargs)
        finally:
            if cli_streamer is not None:
                cli_streamer.stop_display()
                for i, p in enumerate(self.prompts):
                    p.callback = saved_callbacks[i]

        return [result for result in results]


async def _async_parallel_run(prompts, args, kwargs):
    tasks = [p.acall(*args, **kwargs) for p in prompts]
    return await asyncio.gather(*tasks)

