"""
高级记忆管理功能示例

这个示例展示了如何使用记忆管理模块的高级特性，包括记忆池、持久化、自定义记忆策略等。

主要功能：
1. 记忆池的使用（MemoryPool）
2. 记忆的持久化和加载
3. 自定义记忆增强和衰减策略
4. 多记忆实例管理
5. 高级对话历史构建
"""

import asyncio
import os
from alphora.agent.base import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.memory import BaseMemory, MemoryPool


class AdvancedMemoryAgent(BaseAgent):
    """高级记忆管理智能体"""

    def __init__(self, llm, memory_pool=None, verbose=False):
        super().__init__(llm, verbose=verbose)
        self.memory_pool = memory_pool or MemoryPool(max_memories=10)
        
        # 为智能体创建默认记忆
        self.default_memory = BaseMemory()
        self.memory_pool.add_memory("default_agent", self.default_memory)

    async def multi_memory_instance_chat(self, user_id, query):
        """多记忆实例聊天示例"""
        print(f"\n用户 {user_id}: {query}")
        
        # 获取或创建用户特定的记忆实例
        user_memory = self.memory_pool.get_memory(user_id)
        if not user_memory:
            user_memory = BaseMemory()
            self.memory_pool.add_memory(user_id, user_memory)
            print(f"为用户 {user_id} 创建了新的记忆实例")
        
        # 构建历史对话
        history = user_memory.build_history(memory_id="default", max_round=5)
        
        # 创建提示词
        prompt = self.create_prompt(
            prompt="你是一个友好的智能助手，请根据历史对话和当前问题用中文回答。\n\n" +
                   "历史对话：\n{{history}}\n\n" +
                   "当前问题：{{query}}"
        )
        
        # 更新提示词占位符
        prompt.update_placeholder(history=history)
        
        # 调用LLM获取回复
        response = await prompt.acall(query=query, is_stream=False)
        
        # 保存对话到用户特定记忆中
        user_memory.add_memory(role="用户", content=query, decay_factor=0.9, increment=0.2)
        user_memory.add_memory(role="助手", content=response, decay_factor=0.9, increment=0.1)
        
        print(f"助手: {response}")
        return response

    def demonstrate_memory_pool(self):
        """演示记忆池功能"""
        print("\n2. 记忆池功能演示")
        print("=" * 50)
        
        # 查看记忆池中的所有记忆实例
        print(f"记忆池中的记忆实例数量: {len(self.memory_pool.pool)}")
        print("记忆池中的记忆实例ID:", list(self.memory_pool.pool.keys()))
        
        # 获取特定记忆实例
        default_memory = self.memory_pool.get_memory("default_agent")
        if default_memory:
            print(f"默认记忆实例中的记忆数量: {len(default_memory.get_memories('default'))}")

    async def custom_memory_strategy(self, user_id, queries):
        """自定义记忆策略示例"""
        print("\n3. 自定义记忆策略示例")
        print("=" * 50)
        
        # 获取或创建用户记忆
        user_memory = self.memory_pool.get_memory(user_id)
        if not user_memory:
            user_memory = BaseMemory()
            self.memory_pool.add_memory(user_id, user_memory)
        
        for i, query in enumerate(queries):
            print(f"\n查询 {i+1}: {query}")
            
            # 对于重要查询，使用更高的增强值
            if "重要" in query:
                decay_factor = 0.8  # 更低的衰减
                user_increment = 0.3  # 更高的用户记忆增强
                assistant_increment = 0.2  # 更高的助手记忆增强
                print("(检测到重要查询，使用强化记忆策略)")
            else:
                decay_factor = 0.95  # 正常衰减
                user_increment = 0.1  # 正常用户记忆增强
                assistant_increment = 0.05  # 正常助手记忆增强
            
            # 构建历史对话
            history = user_memory.build_history(memory_id="default", max_round=3)
            
            # 创建提示词
            prompt = self.create_prompt(
                prompt="你是一个助手，请根据历史对话和当前问题回答。\n\n" +
                       "历史对话：\n{{history}}\n\n" +
                       "当前问题：{{query}}"
            )
            
            # 更新提示词占位符
            prompt.update_placeholder(history=history)
            
            # 调用LLM获取回复
            response = await prompt.acall(query=query, is_stream=False)
            
            # 保存对话到记忆中，使用自定义的衰减和增强策略
            user_memory.add_memory(
                role="用户", 
                content=query, 
                decay_factor=decay_factor, 
                increment=user_increment
            )
            user_memory.add_memory(
                role="助手", 
                content=response, 
                decay_factor=decay_factor, 
                increment=assistant_increment
            )
            
            print(f"回复 {i+1}: {response}")
        
        # 显示记忆分数，验证自定义策略效果
        print("\n记忆单元分数列表：")
        memories = user_memory.get_memories("default")
        for i, memory in enumerate(memories):
            content = list(memory.content.values())[0]
            role = list(memory.content.keys())[0]
            print(f"{i+1}. [{role}] {content[:20]}... (分数: {memory.score:.3f})")

    def memory_persistence(self, save_path):
        """记忆持久化示例"""
        print("\n4. 记忆持久化示例")
        print("=" * 50)
        
        # 获取默认记忆实例
        default_memory = self.memory_pool.get_memory("default_agent")
        if not default_memory:
            print("没有找到默认记忆实例")
            return
        
        # 保存记忆到文件
        default_memory.dump(save_path)
        print(f"记忆已保存到: {save_path}")
        print(f"保存的记忆数量: {len(default_memory.get_memories('default'))}")
        
        # 这里可以演示加载记忆，但需要重新实例化BaseMemory
        # 由于当前接口限制，我们只展示保存功能
        print("记忆持久化功能演示完成")

    def advanced_history_building(self, user_id):
        """高级对话历史构建示例"""
        print("\n5. 高级对话历史构建示例")
        print("=" * 50)
        
        # 获取用户记忆
        user_memory = self.memory_pool.get_memory(user_id)
        if not user_memory:
            print(f"没有找到用户 {user_id} 的记忆实例")
            return
        
        # 1. 基于长度的历史构建
        length_based_history = user_memory.build_history(
            memory_id="default", 
            max_length=200,  # 限制总字符数
            include_timestamp=False
        )
        print("基于长度的历史对话 (200字符限制):")
        print(length_based_history)
        
        # 2. 基于轮数的历史构建
        round_based_history = user_memory.build_history(
            memory_id="default", 
            max_round=2,  # 只保留最后2轮
            include_timestamp=True
        )
        print("\n基于轮数的历史对话 (2轮限制，包含时间戳):")
        print(round_based_history)
        
        # 3. 完整历史构建
        full_history = user_memory.build_history(
            memory_id="default", 
            max_round=10,  # 足够大的轮数限制
            include_timestamp=True
        )
        print(f"\n完整历史对话 (共 {len(full_history)} 字符):")
        print(full_history[:300] + "..." if len(full_history) > 300 else full_history)


async def main():
    """
    主函数，演示高级记忆管理功能
    """
    print("===== 高级记忆管理功能示例 =====")
    
    # 配置LLM（使用阿里云通义千问作为示例）
    llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'  # 替换为您的API密钥
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    
    # 初始化LLM模型
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name
    )
    
    # 创建记忆池
    memory_pool = MemoryPool(max_memories=10)
    
    # 初始化高级记忆智能体
    agent = AdvancedMemoryAgent(llm=llm, memory_pool=memory_pool, verbose=True)
    
    # 1. 多用户多记忆实例示例
    print("\n1. 多用户多记忆实例示例")
    print("=" * 50)
    
    # 用户1的对话
    await agent.multi_memory_instance_chat("user1", "你好，我叫张三。")
    await agent.multi_memory_instance_chat("user1", "我叫什么名字？")
    await agent.multi_memory_instance_chat("user1", "请告诉我人工智能的定义。")
    
    # 用户2的对话
    await agent.multi_memory_instance_chat("user2", "你好，我是李四。")
    await agent.multi_memory_instance_chat("user2", "我对机器学习很感兴趣。")
    await agent.multi_memory_instance_chat("user2", "你能推荐一些学习资源吗？")
    
    # 再次与用户1对话，验证记忆隔离
    await agent.multi_memory_instance_chat("user1", "我之前问过什么问题？")
    
    # 2. 演示记忆池功能
    agent.demonstrate_memory_pool()
    
    # 3. 自定义记忆策略示例
    user_queries = [
        "请解释什么是深度学习？",
        "这个问题很重要：深度学习在医疗领域有哪些应用？",
        "谢谢，那在金融领域呢？",
        "重要：请总结一下深度学习的主要挑战。"
    ]
    await agent.custom_memory_strategy("user3", user_queries)
    
    # 4. 记忆持久化示例
    save_path = "./agent_memory.dump"
    agent.memory_persistence(save_path)
    
    # 5. 高级对话历史构建示例
    agent.advanced_history_building("user1")
    
    # 清理临时文件
    if os.path.exists(save_path):
        os.remove(save_path)
        print(f"\n临时文件已清理: {save_path}")
    
    print("\n===== 高级记忆管理功能示例完成 =====")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())