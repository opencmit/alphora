from typing import List, Optional, Dict, Any
from alphora.memory.memory_unit import MemoryUnit
import json
from typing import Dict
import pickle
import dill
from datetime import datetime


class BaseMemory:
    def __init__(self):
        """
        存放多个Prompt的记忆，key为Prompt id
        """
        self._memories: Dict[str, List[MemoryUnit]] = {}    # 每个 Prompt 的记忆
        self.current_turn: Dict[str, int] = {}              # 当前对话轮数

    def add_memory(self,
                   content: Dict[str, Any],
                   memory_id: str = 'default',
                   decay_factor: float = 0.9,
                   increment: float = 0.1):
        """
        添加记忆，并对该 Prompt 的记忆进行增强或衰减

        Args:
            memory_id (str): Prompt 的唯一标识符。
            content (Dict[str, Any]): 新的记忆内容。
            decay_factor (float): 对现有记忆的衰减系数。
            increment (float): 新记忆的增强值。
        """

        if memory_id not in self._memories:
            self._memories[memory_id] = []
            self.current_turn[memory_id] = 0

        self.current_turn[memory_id] += 1

        for memory in self._memories[memory_id]:
            memory.decay(decay_factor)

        new_memory = MemoryUnit(content=content)
        new_memory.reinforce(increment)
        self._memories[memory_id].append(new_memory)

    def get_memories(self, memory_id: str) -> List[MemoryUnit]:
        """
        获取指定 Prompt 的所有记忆

        Args:
            memory_id (str):

        Returns:
            List[MemoryUnit]: 该 Prompt 的记忆列表
        """
        return self._memories.get(memory_id, [])

    def get_top_memories(self, memory_id: str, top_n: int = 5) -> List[MemoryUnit]:
        """
        获取指定 Prompt 分数最高的记忆

        Args:
            memory_id (str):
            top_n (int): 返回的记忆单元数量

        Returns:
            List[MemoryUnit]: 排名前 N 的记忆单元
        """
        memories = self.get_memories(memory_id)
        return sorted(memories, key=lambda m: m.score, reverse=True)[:top_n]

    def clear_memory(self, memory_id: str):

        if memory_id in self._memories:
            self._memories.pop(memory_id)
            self.current_turn.pop(memory_id, None)

    def build_history(self,
                      memory_id: str = "default",
                      max_length: Optional[int] = None,
                      max_round: int = 5,
                      include_timestamp: bool = True) -> str:
        """
        根据传入的记忆单元列表生成适合大模型使用的历史对话信息，使用MemoryUnit自带的时间戳

        Args:
            memory_id(str)
            max_length (int): 限制生成的对话上下文总字符数
            max_round (int): 轮数
            include_timestamp (bool): 是否在历史中包含时间戳信息
        Returns:
            str: 格式化的历史对话信息
        """
        if max_length:
            memories: List[MemoryUnit] = self.get_top_memories(memory_id=memory_id, top_n=max_length // 20)
        else:
            memories = self.get_top_memories(memory_id=memory_id, top_n=max_round)

        # 按MemoryUnit自带的时间戳排序，确保对话时序正确
        sorted_memories = sorted(memories, key=lambda m: m.timestamp)

        context = []
        total_length = 0

        max_length = max_length if max_length else 999999999

        for memory in sorted_memories:
            formatted_lines = []
            for key, value in memory.content.items():
                # 如果需要包含时间戳，使用MemoryUnit的格式化时间
                if include_timestamp:
                    line = f"[{memory.formatted_timestamp(include_second=False)}] % {key}: {value}"
                else:
                    line = f"{key}: {value}"
                formatted_lines.append(line)

            formatted_message = "\n".join(formatted_lines) + "\n"

            if total_length + len(formatted_message) > max_length:
                break

            context.append(formatted_message)
            total_length += len(formatted_message)

        return "".join(context)

    def is_empty(self, memory_id: str) -> bool:
        """
        判断该prompt的历史是否为空
        Args:
            memory_id:
        Returns:
        """
        if len(self.get_memories(memory_id=memory_id)) == 0:
            return True
        else:
            return False

    def dump(self, dump_path: str):
        """
        使用 dill 将内存数据序列化保存到指定路径的二进制文件中

        Args:
            dump_path (str): 保存文件的路径
        """
        try:
            with open(dump_path, 'wb') as f:
                dill.dump(self, f)
        except Exception as e:
            raise Exception(f"Failed to dump memory to {dump_path}: {str(e)}")


if __name__ == "__main__":
    memory_manager = BaseMemory()

    memory_manager.add_memory(memory_id="prompt1", content={"input": "Hello"})
    # memory_manager.add_memory(memory_id="prompt1", content={"input": "How are you?", "output": "I'm fine"})

    x = memory_manager.build_history(memory_id="prompt1", include_timestamp=True)
    print(x)



