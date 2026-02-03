# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""阿里云百炼平台 API获取文本向量
https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-synchronous-api?spm=a2c4g.11186623.0.i36

text_type：取值：query 或者 document，默认值为 document
说明：文本转换为向量后可以应用于检索、聚类、分类等下游任务，
对检索这类非对称任务为了达到更好的检索效果建议区分查询文本（query）和底库文本（document）类型,
聚类、分类等对称任务可以不用特殊指定，采用系统默认值"document"即可
"""

from typing import List, Union, Any, Optional
from openai import OpenAI, AsyncOpenAI
import os


class EmbeddingModel:
    def __init__(
            self,
            api_key: str = None,
            base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
            model: str = 'text-embedding-v3',
            dimension: int = None,
            header: dict = None
    ):
        self.model_name: str = model or os.getenv("EMBEDDING_MODEL", None)
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY", None)
        self.base_url = base_url or os.getenv("EMBEDDING_URL", None)
        self.dimension: int = dimension
        self.headers = header

        # 同步客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self.headers
        )

        # 异步客户端
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self.headers
        )

    def get_text_embeddings(self, texts: List[str], max_batch: int = 10) -> Union[list[None], list[list]]:
        """同步：获取文本的embedding，支持分批处理"""
        if not texts or not isinstance(texts, list):
            raise ValueError("texts 参数必须为非空的列表")

        all_embeddings = []
        errors_occurred = False
        try:
            for i in range(0, len(texts), max_batch):
                batch_texts = texts[i:i + max_batch]
                completion = self.client.embeddings.create(
                    model=self.model_name,
                    input=batch_texts,
                )
                batch_embeddings = [data.embedding for data in completion.data]
                all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"获取embedding时发生错误: {e}")
            errors_occurred = True

        if errors_occurred or len(all_embeddings) != len(texts):
            return [None] * len(texts)
        return all_embeddings

    def get_text_embedding(self, text: str) -> Optional[List[float]]:
        embeddings = self.get_text_embeddings([text])
        return embeddings[0] if embeddings else None

    async def aget_text_embeddings(self, texts: List[str], max_batch: int = 10) -> Union[list[None], list[list]]:
        """异步：获取文本的embedding，支持分批处理"""
        if not texts or not isinstance(texts, list):
            raise ValueError("texts 参数必须为非空的列表")

        all_embeddings = []
        errors_occurred = False
        try:
            for i in range(0, len(texts), max_batch):
                batch_texts = texts[i:i + max_batch]
                completion = await self.async_client.embeddings.create(
                    model=self.model_name,
                    input=batch_texts,
                )
                batch_embeddings = [data.embedding for data in completion.data]
                all_embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"异步获取embedding时发生错误: {e}")
            errors_occurred = True

        if errors_occurred or len(all_embeddings) != len(texts):
            return [None] * len(texts)
        return all_embeddings

    async def aget_text_embedding(self, text: str) -> Optional[List[float]]:
        embeddings = await self.aget_text_embeddings([text])
        return embeddings[0] if embeddings else None

    def get_embedding_dimension(self):
        """获取向量维度"""
        return self.dimension

    def __getstate__(self):
        state = self.__dict__.copy()
        # 移除不可序列化的客户端
        del state['client']
        del state['async_client']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # 重新创建客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self.headers
        )
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self.headers
        )

    def ping(self) -> bool:
        try:
            self.get_text_embedding(text='你好')
            return True
        except Exception as e:
            return False

    async def aping(self) -> bool:
        try:
            await self.aget_text_embedding(text='你好')
            return True
        except Exception as e:
            return False

