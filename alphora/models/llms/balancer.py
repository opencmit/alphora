from typing import Any, Dict, List, Tuple
from itertools import cycle
import random
from openai import OpenAI, AsyncOpenAI


class _LLMLoadBalancer:
    """llm负载均衡器"""

    def __init__(self, strategy: str = "round_robin"):
        if strategy not in ("round_robin", "random"):
            raise ValueError("strategy must be 'round_robin' or 'random'")
        self.strategy = strategy

        self._sync_backends: List[Tuple[OpenAI, Dict[str, Any], bool]] = []
        self._async_backends: List[Tuple[AsyncOpenAI, Dict[str, Any], bool]] = []

        self._sync_cycle = None
        self._async_cycle = None

    def add_client(
            self,
            sync_client: OpenAI,
            async_client: AsyncOpenAI,
            completion_params: Dict[str, Any],
            is_multimodal: bool = False,
    ):
        """
        新增client，同时注册一对同步/异步客户端，共享相同的 completion_params
        """
        if not isinstance(sync_client, OpenAI):
            raise TypeError("sync_client must be an instance of OpenAI")
        if not isinstance(async_client, AsyncOpenAI):
            raise TypeError("async_client must be an instance of AsyncOpenAI")
        if not isinstance(completion_params, dict):
            raise TypeError("completion_params must be a dict")

        # 深拷贝 params
        params_copy = completion_params.copy()

        self._sync_backends.append((sync_client, params_copy, is_multimodal))
        self._async_backends.append((async_client, params_copy, is_multimodal))

        # 重建 cycle
        if self.strategy == "round_robin":
            self._sync_cycle = cycle(range(len(self._sync_backends)))
            self._async_cycle = cycle(range(len(self._async_backends)))

    def _filter_backends(
            self,
            backends: List[Tuple[Any, Dict[str, Any], bool]],
            need_multimodal: bool,
    ) -> List[int]:
        """返回满足 need_multimodal 条件的 backend 索引列表"""
        if not need_multimodal:
            return [
                i for i, (_, _, is_mm) in enumerate(backends)
            ]

        return [
            i for i, (_, _, is_mm) in enumerate(backends)
            if is_mm == need_multimodal
        ]

    def get_next_sync_backend(self, need_multimodal: bool = False) -> Tuple[OpenAI, Dict[str, Any]]:
        if not self._sync_backends:
            raise RuntimeError("No synchronous backends registered.")

        available_indices = self._filter_backends(self._sync_backends, need_multimodal)
        if not available_indices:
            raise RuntimeError(
                f"没有可用的多模态模型, "
                f"No synchronous backends available with need_multimodal={need_multimodal}."
            )

        if self.strategy == "round_robin":
            # 在全量 cycle 中跳过不满足条件的，直到找到一个可用的
            while True:
                idx = next(self._sync_cycle)
                if idx in available_indices:
                    break
        else:  # random
            idx = random.choice(available_indices)

        client, params, _ = self._sync_backends[idx]
        return client, params

    def get_next_async_backend(self, need_multimodal: bool = False) -> Tuple[AsyncOpenAI, Dict[str, Any]]:
        if not self._async_backends:
            raise RuntimeError("No asynchronous backends registered.")

        available_indices = self._filter_backends(self._async_backends, need_multimodal)
        if not available_indices:
            raise RuntimeError(
                f"没有可用的多模态模型, "
                f"No asynchronous backends available with need_multimodal={need_multimodal}."
            )

        if self.strategy == "round_robin":
            while True:
                idx = next(self._async_cycle)
                if idx in available_indices:
                    break
        else:  # random
            idx = random.choice(available_indices)

        client, params, _ = self._async_backends[idx]
        return client, params

    def update_primary_param(self, key: str, value: Any):
        """更新主后端（index 0）的 completion_params 中的指定参数。
        sync 和 async 后端共享同一个 params dict，只需更新一侧即可。
        """
        if self._sync_backends:
            self._sync_backends[0][1][key] = value

    def size(self) -> int:
        """返回后端对的数量"""
        return len(self._sync_backends)

