"""
博查 Web Search API: 通用互联网搜索
"""

import os
import json
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(..., description="搜索关键词或问题，支持自然语言")
    count: int = Field(8, ge=1, le=20, description="返回结果数量")
    freshness: str = Field(
        "noLimit",
        description="时间范围: noLimit(不限)/oneDay(一天)/oneWeek(一周)/oneMonth(一月)/oneYear(一年)"
    )


class WebSearchTool:
    """
    互联网搜索工具

    使用博查 Web Search API 搜索互联网信息。
    文档：https://open.bochaai.com/
    """

    API_ENDPOINT = "https://api.bochaai.com/v1/web-search"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化搜索工具

        Args:
            api_key: 博查 API Key，不传则从环境变量 BOCHA_API_KEY 获取
        """
        self._api_key = api_key or os.getenv("BOCHA_API_KEY")

    def set_api_key(self, api_key: str):
        """设置 API Key"""
        self._api_key = api_key

    async def search(
            self,
            query: str,
            count: int = 8,
            freshness: Literal["noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear"] = "noLimit"
    ) -> str:
        """
        执行互联网实时搜索，获取最新资讯、事实验证或特定领域的知识补充。

        【核心原则：聚焦与拆解】
        1. **搜索范围控制**：Query 必须具体且聚焦。严禁使用宽泛的通用词汇。
        2. **分步检索策略**：复杂问题拆解为多次搜索。
           - 忌："特斯拉2024销量及比亚迪同期对比和两者的电池技术差异"
           - 宜：拆解为多次搜索：
             1. "特斯拉 2024年 全球销量 数据"
             2. "比亚迪 2024年 销量 财报"
             3. "Blade battery vs 4680 battery comparison"

        【使用场景】
        - 查询实时信息：新闻、股价、天气、赛事比分等
        - 查找最新资讯：政策法规、产品发布、行业动态
        - 验证事实：核实某个说法或数据是否准确
        - 补充知识：获取训练数据之外的新知识

        Args:
            query: 搜索关键词或问题，支持自然语言
            count: 返回结果数量，默认 8 条，最多 20 条
            freshness: 时间范围过滤
                - "noLimit": 不限时间（默认）
                - "oneDay": 最近一天
                - "oneWeek": 最近一周
                - "oneMonth": 最近一个月
                - "oneYear": 最近一年

        Returns:
            格式化的搜索结果 JSON
        """
        import httpx

        if not self._api_key:
            return json.dumps({
                "success": False,
                "error": "未配置博查 API Key，请设置环境变量 BOCHA_API_KEY 或调用 set_api_key()"
            }, ensure_ascii=False)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "count": min(count, 20),
            "freshness": freshness,
            "summary": True,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.API_ENDPOINT,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            return self._format_results(query, data)

        except httpx.TimeoutException:
            return json.dumps({
                "success": False,
                "query": query,
                "error": "搜索超时，请稍后重试"
            }, ensure_ascii=False)
        except httpx.HTTPStatusError as e:
            return json.dumps({
                "success": False,
                "query": query,
                "error": f"请求失败：HTTP {e.response.status_code}"
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "query": query,
                "error": str(e)
            }, ensure_ascii=False)

    def _format_results(self, query: str, data: dict) -> str:
        """格式化搜索结果"""
        response_data = data.get("data", {})
        web_pages = response_data.get("webPages", {}).get("value", [])

        if not web_pages:
            return json.dumps({
                "success": True,
                "query": query,
                "results": [],
                "count": 0,
                "message": "未找到相关结果"
            }, ensure_ascii=False)

        results = []
        for page in web_pages:
            result = {
                "title": page.get("name", ""),
                "url": page.get("url", ""),
                "site_name": page.get("siteName", ""),
                "snippet": page.get("snippet", ""),
                "summary": page.get("summary", ""),
            }

            date = page.get("datePublished", "")
            if date:
                result["date"] = date[:10]

            results.append(result)

        return json.dumps({
            "success": True,
            "query": query,
            "results": results,
            "count": len(results)
        }, ensure_ascii=False, indent=2)

