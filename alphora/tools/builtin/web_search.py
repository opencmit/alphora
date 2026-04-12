"""
互联网搜索工具

支持多搜索引擎后端（BoChaAI / DuckDuckGo / Exa AI），支持网页搜索、图片搜索和新闻搜索。
自动回退策略：优先 BoChaAI，失败回退 Exa，再回退 DuckDuckGo
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Literal

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class SearchType(str, Enum):
    """搜索类型"""
    TEXT = "text"       # 网页/文本搜索
    IMAGE = "image"     # 图片搜索
    NEWS = "news"       # 新闻搜索


class SearchEngine(str, Enum):
    """搜索引擎后端"""
    BOCHA = "bocha"             # 博查AI
    DUCKDUCKGO = "duckduckgo"   # DuckDuckGo
    EXA = "exa"                 # Exa AI
    AUTO = "auto"


class Freshness(str, Enum):
    """搜索时间范围"""
    NO_LIMIT = "noLimit"
    ONE_DAY = "oneDay"
    ONE_WEEK = "oneWeek"
    ONE_MONTH = "oneMonth"
    ONE_YEAR = "oneYear"


@dataclass
class SearchResultItem:
    """单条搜索结果"""
    title: str                          # 标题
    url: str                            # 链接
    snippet: str = ""                   # 摘要 / 描述
    source: str = ""                    # 来源网站名
    published_date: str = ""            # 发布日期
    image_url: str = ""                 # 图片 URL（图片搜索时）
    thumbnail_url: str = ""             # 缩略图 URL
    extra: dict = field(default_factory=dict)  # 其他扩展字段

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class SearchResponse:
    """统一搜索响应"""
    query: str                                      # 原始查询
    search_type: str                                # 搜索类型
    engine: str                                     # 使用的搜索引擎
    results: list[SearchResultItem] = field(default_factory=list)
    summary: str = ""                               # AI 生成的摘要（BoCha 支持）
    total_results: int = 0                          # 估计总结果数
    elapsed_seconds: float = 0.0                    # 耗时
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "search_type": self.search_type,
            "engine": self.engine,
            "success": self.success,
            "error_message": self.error_message,
            "summary": self.summary,
            "total_results": self.total_results,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)

    def to_text(self) -> str:
        """将搜索结果格式化为纯文本，方便直接喂给 LLM。"""
        lines = [f"搜索查询: {self.query}", f"搜索引擎: {self.engine}", ""]

        if self.summary:
            lines.append(f"摘要: {self.summary}")
            lines.append("")

        if not self.success:
            lines.append(f"搜索失败: {self.error_message}")
            return "\n".join(lines)

        if not self.results:
            lines.append("未找到相关结果。")
            return "\n".join(lines)

        for i, r in enumerate(self.results, 1):
            if self.search_type == SearchType.IMAGE:
                lines.append(f"[{i}] {r.title}")
                lines.append(f"    图片: {r.image_url or r.url}")
                if r.source:
                    lines.append(f"    来源: {r.source}")
            else:
                lines.append(f"[{i}] {r.title}")
                lines.append(f"    链接: {r.url}")
                if r.snippet:
                    lines.append(f"    摘要: {r.snippet}")
                if r.source:
                    lines.append(f"    来源: {r.source}")
                if r.published_date:
                    lines.append(f"    日期: {r.published_date}")
            lines.append("")

        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_text()


# ============================================================================
# 搜索引擎后端实现
# ============================================================================

class BochaSearchBackend:
    """
    博查 AI 搜索后端
    文档: https://open.bochaai.com/
    API: POST https://api.bochaai.com/v1/web-search
    """
    BASE_URL = "https://api.bochaai.com/v1"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search_web(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
            summary: bool = True,
    ) -> SearchResponse:
        """网页/文本搜索"""
        url = f"{self.BASE_URL}/web-search"
        payload = {
            "query": query,
            "count": min(count, 50),  # BoCha 最多支持 50 条
            "freshness": freshness,
            "summary": summary,
        }

        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            return SearchResponse(
                query=query, search_type="text", engine="bocha",
                success=False, error_message=f"HTTP {e.response.status_code}: {e.response.text}",
                elapsed_seconds=time.monotonic() - t0,
            )
        except Exception as e:
            return SearchResponse(
                query=query, search_type="text", engine="bocha",
                success=False, error_message=str(e),
                elapsed_seconds=time.monotonic() - t0,
            )

        elapsed = time.monotonic() - t0

        api_error = self._check_api_error(data)
        if api_error:
            return SearchResponse(
                query=query, search_type="text", engine="bocha",
                success=False, error_message=api_error,
                elapsed_seconds=elapsed,
            )

        return self._parse_web_response(query, data, elapsed)

    def search_image(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
    ) -> SearchResponse:
        """
        图片搜索 —— BoCha web-search 返回结果中包含图片链接字段，
        我们从中提取 image 相关数据。如果 BoCha 未来提供独立图片搜索端点，
        可在此处替换。
        """
        url = f"{self.BASE_URL}/web-search"
        payload = {
            "query": f"{query} 图片",
            "count": min(count * 2, 50),  # 多请求一些，因为并非每条都有图片
            "freshness": freshness,
            "summary": False,
        }

        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return SearchResponse(
                query=query, search_type="image", engine="bocha",
                success=False, error_message=str(e),
                elapsed_seconds=time.monotonic() - t0,
            )

        elapsed = time.monotonic() - t0

        api_error = self._check_api_error(data)
        if api_error:
            return SearchResponse(
                query=query, search_type="image", engine="bocha",
                success=False, error_message=api_error,
                elapsed_seconds=elapsed,
            )

        return self._parse_image_response(query, data, elapsed, count)

    @staticmethod
    def _check_api_error(data: dict) -> str:
        """检查 BoCha API 响应中的业务错误（HTTP 200 但 API 返回失败）"""
        code = data.get("code")
        if code is not None and code != 200:
            msg = data.get("msg") or data.get("message") or f"API 错误码 {code}"
            return f"BoCha API 错误: {msg} (code={code})"
        return ""

    def _parse_web_response(self, query: str, data: dict, elapsed: float) -> SearchResponse:
        """解析 BoCha 网页搜索响应"""
        # BoCha 响应可能有 {"data": {"webPages": ...}} 的外层包装
        inner = data.get("data", data)

        web_pages = inner.get("webPages", {})
        values = web_pages.get("value", [])
        total = web_pages.get("totalEstimatedMatches", 0)

        top_summary = ""
        if isinstance(inner.get("summary"), str):
            top_summary = inner["summary"]

        items = []
        for v in values:
            item = SearchResultItem(
                title=v.get("name", ""),
                url=v.get("url", ""),
                snippet=v.get("summary") or v.get("snippet", ""),
                source=v.get("siteName", ""),
                published_date=v.get("datePublished", ""),
                image_url=v.get("imageUrl", ""),
                thumbnail_url=v.get("thumbnailUrl", ""),
            )
            items.append(item)

        return SearchResponse(
            query=query,
            search_type="text",
            engine="bocha",
            results=items,
            summary=top_summary,
            total_results=total,
            elapsed_seconds=elapsed,
        )

    def _parse_image_response(
            self, query: str, data: dict, elapsed: float, limit: int
    ) -> SearchResponse:
        """从 BoCha 网页搜索结果中提取图片"""
        inner = data.get("data", data)

        web_pages = inner.get("webPages", {})
        values = web_pages.get("value", [])

        images_block = inner.get("images", {})
        image_values = images_block.get("value", []) if images_block else []

        items = []

        # 1) 先从独立 images 块提取
        for v in image_values:
            items.append(SearchResultItem(
                title=v.get("name", ""),
                url=v.get("hostPageUrl", v.get("url", "")),
                image_url=v.get("contentUrl", v.get("url", "")),
                thumbnail_url=v.get("thumbnailUrl", ""),
                source=v.get("hostPageDisplayUrl", ""),
            ))

        # 2) 再从 webPages 中提取含图片链接的结果
        for v in values:
            img_url = v.get("imageUrl", "") or v.get("thumbnailUrl", "")
            if img_url:
                items.append(SearchResultItem(
                    title=v.get("name", ""),
                    url=v.get("url", ""),
                    image_url=img_url,
                    thumbnail_url=v.get("thumbnailUrl", ""),
                    source=v.get("siteName", ""),
                ))

        # 去重
        seen_urls = set()
        unique_items = []
        for item in items:
            key = item.image_url or item.url
            if key and key not in seen_urls:
                seen_urls.add(key)
                unique_items.append(item)

        return SearchResponse(
            query=query,
            search_type="image",
            engine="bocha",
            results=unique_items[:limit],
            elapsed_seconds=elapsed,
        )


class DuckDuckGoSearchBackend:
    """
    DuckDuckGo 搜索后端（免费、无需 API Key）
    使用 duckduckgo_search 库。
    """

    def __init__(self, timeout: float = 30.0, proxy: Optional[str] = None):
        self.timeout = timeout
        self.proxy = proxy

    def _get_ddgs(self):
        """延迟导入 duckduckgo_search 以避免未安装时报错"""
        try:
            from duckduckgo_search import DDGS
            return DDGS(timeout=int(self.timeout), proxy=self.proxy)
        except ImportError:
            raise ImportError(
                "请安装 duckduckgo-search: pip install duckduckgo-search"
            )

    def search_web(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
            **kwargs,
    ) -> SearchResponse:
        """网页搜索"""
        ddgs = self._get_ddgs()

        # 将 freshness 映射为 DuckDuckGo 的 timelimit 参数
        timelimit_map = {
            "oneDay": "d",
            "oneWeek": "w",
            "oneMonth": "m",
            "oneYear": "y",
            "noLimit": None,
        }
        timelimit = timelimit_map.get(freshness)

        t0 = time.monotonic()
        try:
            raw_results = list(ddgs.text(
                keywords=query,
                max_results=count,
                timelimit=timelimit,
            ))
        except Exception as e:
            return SearchResponse(
                query=query, search_type="text", engine="duckduckgo",
                success=False, error_message=str(e),
                elapsed_seconds=time.monotonic() - t0,
            )

        elapsed = time.monotonic() - t0
        items = []
        for r in raw_results:
            items.append(SearchResultItem(
                title=r.get("title", ""),
                url=r.get("href", r.get("link", "")),
                snippet=r.get("body", r.get("snippet", "")),
            ))

        return SearchResponse(
            query=query,
            search_type="text",
            engine="duckduckgo",
            results=items,
            total_results=len(items),
            elapsed_seconds=elapsed,
        )

    def search_image(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
            **kwargs,
    ) -> SearchResponse:
        """图片搜索"""
        ddgs = self._get_ddgs()

        timelimit_map = {
            "oneDay": "Day",
            "oneWeek": "Week",
            "oneMonth": "Month",
            "oneYear": "Year",
            "noLimit": None,
        }
        timelimit = timelimit_map.get(freshness)

        t0 = time.monotonic()
        try:
            raw_results = list(ddgs.images(
                keywords=query,
                max_results=count,
                timelimit=timelimit,
            ))
        except Exception as e:
            return SearchResponse(
                query=query, search_type="image", engine="duckduckgo",
                success=False, error_message=str(e),
                elapsed_seconds=time.monotonic() - t0,
            )

        elapsed = time.monotonic() - t0
        items = []
        for r in raw_results:
            items.append(SearchResultItem(
                title=r.get("title", ""),
                url=r.get("url", ""),
                image_url=r.get("image", r.get("url", "")),
                thumbnail_url=r.get("thumbnail", ""),
                source=r.get("source", ""),
            ))

        return SearchResponse(
            query=query,
            search_type="image",
            engine="duckduckgo",
            results=items,
            total_results=len(items),
            elapsed_seconds=elapsed,
        )

    def search_news(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
            **kwargs,
    ) -> SearchResponse:
        """新闻搜索"""
        ddgs = self._get_ddgs()

        timelimit_map = {
            "oneDay": "d",
            "oneWeek": "w",
            "oneMonth": "m",
            "oneYear": "y",
            "noLimit": None,
        }
        timelimit = timelimit_map.get(freshness)

        t0 = time.monotonic()
        try:
            raw_results = list(ddgs.news(
                keywords=query,
                max_results=count,
                timelimit=timelimit,
            ))
        except Exception as e:
            return SearchResponse(
                query=query, search_type="news", engine="duckduckgo",
                success=False, error_message=str(e),
                elapsed_seconds=time.monotonic() - t0,
            )

        elapsed = time.monotonic() - t0
        items = []
        for r in raw_results:
            items.append(SearchResultItem(
                title=r.get("title", ""),
                url=r.get("url", r.get("link", "")),
                snippet=r.get("body", ""),
                source=r.get("source", ""),
                published_date=r.get("date", ""),
            ))

        return SearchResponse(
            query=query,
            search_type="news",
            engine="duckduckgo",
            results=items,
            total_results=len(items),
            elapsed_seconds=elapsed,
        )


class ExaSearchBackend:
    """
    Exa AI 搜索后端
    文档: https://exa.ai/docs
    使用 exa-py SDK。支持多种搜索类型和内容提取模式。
    """

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    def _get_client(self):
        """延迟导入 exa_py 以避免未安装时报错"""
        try:
            from exa_py import Exa
            client = Exa(api_key=self.api_key)
            client.headers["x-exa-integration"] = "alphora"
            return client
        except ImportError:
            raise ImportError(
                "请安装 exa-py: pip install exa-py>=2.0.0"
            )

    @staticmethod
    def _freshness_to_date(freshness: str) -> Optional[str]:
        """将 freshness 枚举映射为 ISO 8601 日期字符串"""
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        delta_map = {
            "oneDay": datetime.timedelta(days=1),
            "oneWeek": datetime.timedelta(weeks=1),
            "oneMonth": datetime.timedelta(days=30),
            "oneYear": datetime.timedelta(days=365),
        }
        delta = delta_map.get(freshness)
        if delta:
            return (now - delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        return None

    def search_web(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
            content_mode: str = "highlights",
            search_type: str = "auto",
            category: Optional[str] = None,
            include_domains: Optional[list] = None,
            exclude_domains: Optional[list] = None,
            include_text: Optional[str] = None,
            exclude_text: Optional[str] = None,
    ) -> SearchResponse:
        """网页/文本搜索"""
        client = self._get_client()

        kwargs: dict = {
            "query": query,
            "num_results": min(count, 100),
            "type": search_type,
        }

        # 时间范围过滤
        start_date = self._freshness_to_date(freshness)
        if start_date:
            kwargs["start_published_date"] = start_date

        # 可选过滤参数
        if category:
            kwargs["category"] = category
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        if include_text:
            kwargs["include_text"] = include_text
        if exclude_text:
            kwargs["exclude_text"] = exclude_text

        # 内容提取模式
        if content_mode == "text":
            kwargs["text"] = {"max_characters": 10000}
        elif content_mode == "summary":
            kwargs["summary"] = True
        else:
            # 默认使用 highlights
            kwargs["highlights"] = {"max_characters": 4000}

        t0 = time.monotonic()
        try:
            response = client.search_and_contents(**kwargs)
        except Exception as e:
            return SearchResponse(
                query=query, search_type="text", engine="exa",
                success=False, error_message=str(e),
                elapsed_seconds=time.monotonic() - t0,
            )

        elapsed = time.monotonic() - t0
        items = []
        for r in response.results:
            # 根据内容模式提取摘要
            snippet = ""
            if content_mode == "highlights" and getattr(r, "highlights", None):
                snippet = "\n".join(r.highlights)
            elif content_mode == "text" and getattr(r, "text", None):
                snippet = r.text[:500]
            elif content_mode == "summary" and getattr(r, "summary", None):
                snippet = r.summary

            items.append(SearchResultItem(
                title=getattr(r, "title", "") or "",
                url=getattr(r, "url", "") or "",
                snippet=snippet,
                published_date=getattr(r, "published_date", "") or "",
                source=getattr(r, "author", "") or "",
            ))

        return SearchResponse(
            query=query,
            search_type="text",
            engine="exa",
            results=items,
            total_results=len(items),
            elapsed_seconds=elapsed,
        )

    def search_news(
            self,
            query: str,
            count: int = 10,
            freshness: str = "noLimit",
    ) -> SearchResponse:
        """新闻搜索（通过 category='news' 实现）"""
        return self.search_web(
            query=query,
            count=count,
            freshness=freshness,
            category="news",
            content_mode="highlights",
        )


# ============================================================================
# 主搜索类
# ============================================================================

class AISearch:
    """
    AI 搜索工具 —— 统一的搜索接口，支持多后端和自动回退。

    参数:
        bocha_api_key:  BoCha API Key（可选，若不传则从环境变量 BOCHA_API_KEY 读取）
        exa_api_key:    Exa API Key（可选，若不传则从环境变量 EXA_API_KEY 读取）
        engine:         搜索引擎 ("bocha" | "duckduckgo" | "exa" | "auto")
                        默认 "auto" —— 优先 BoCha，失败回退 Exa，再回退 DuckDuckGo
        timeout:        单次请求超时秒数
        proxy:          代理地址（仅 DuckDuckGo 后端使用）

    使用:
        searcher = AISearch(bocha_api_key="sk-xxx")

        # 文本搜索
        result = searcher.search("2024年诺贝尔物理奖得主")

        # 图片搜索
        result = searcher.search("可爱的猫咪", search_type="image", count=5)

        # 新闻搜索（仅 DuckDuckGo 支持独立新闻端点）
        result = searcher.search("AI最新进展", search_type="news", engine="duckduckgo")

        # Exa AI 搜索（支持 category / domain / text 过滤）
        result = searcher.search("latest AI research", engine="exa")

        # 获取纯文本（喂给 LLM）
        print(result.to_text())

        # 获取 JSON
        print(result.to_json())

        # 获取字典
        data = result.to_dict()
    """

    def __init__(
            self,
            bocha_api_key: Optional[str] = None,
            exa_api_key: Optional[str] = None,
            engine: str = "auto",
            timeout: float = 30.0,
            proxy: Optional[str] = None,
    ):
        self.bocha_api_key = bocha_api_key or os.environ.get("BOCHA_API_KEY", "")
        self.exa_api_key = exa_api_key or os.environ.get("EXA_API_KEY", "")
        self.default_engine = engine
        self.timeout = timeout
        self.proxy = proxy

        # 初始化后端
        self._bocha: Optional[BochaSearchBackend] = None
        self._ddg: Optional[DuckDuckGoSearchBackend] = None
        self._exa: Optional[ExaSearchBackend] = None

        if self.bocha_api_key:
            self._bocha = BochaSearchBackend(self.bocha_api_key, timeout=timeout)
        if self.exa_api_key:
            self._exa = ExaSearchBackend(self.exa_api_key, timeout=timeout)
        self._ddg = DuckDuckGoSearchBackend(timeout=timeout, proxy=proxy)

    def search(
            self,
            query: str,
            search_type: str = "text",
            count: int = 10,
            freshness: str = "noLimit",
            engine: Optional[str] = None,
            summary: bool = True,
    ) -> SearchResponse:
        """
        执行搜索。

        参数:
            query:       搜索查询文本（必填）
            search_type: "text"  - 网页搜索（默认）
                         "image" - 图片搜索（返回图片 URL）
                         "news"  - 新闻搜索
            count:       返回结果数量（1-50，默认 10；Exa 支持最多 100）
            freshness:   时间范围过滤
                         "noLimit"  - 不限（默认）
                         "oneDay"   - 最近一天
                         "oneWeek"  - 最近一周
                         "oneMonth" - 最近一月
                         "oneYear"  - 最近一年
            engine:      指定搜索引擎（覆盖实例默认设置）
                         "bocha"      - 仅用博查
                         "duckduckgo" - 仅用 DuckDuckGo
                         "exa"        - 仅用 Exa AI
                         "auto"       - 自动（优先 BoCha，失败回退 Exa，再回退 DDG）
            summary:     是否请求 AI 摘要（仅 BoCha 支持）

        返回:
            SearchResponse 对象，包含 results 列表和可选的 summary。
            可调用 .to_text() / .to_json() / .to_dict() 转换格式。
        """
        engine = engine or self.default_engine
        count = max(1, min(count, 100 if engine == "exa" else 50))

        if engine == "bocha":
            return self._search_bocha(query, search_type, count, freshness, summary)
        elif engine == "duckduckgo":
            return self._search_ddg(query, search_type, count, freshness)
        elif engine == "exa":
            return self._search_exa(query, search_type, count, freshness)
        else:  # auto
            return self._search_auto(query, search_type, count, freshness, summary)

    def _search_bocha(
            self, query, search_type, count, freshness, summary
    ) -> SearchResponse:
        if not self._bocha:
            return SearchResponse(
                query=query, search_type=search_type, engine="bocha",
                success=False,
                error_message="BoCha API Key 未配置。请设置 bocha_api_key 参数或 BOCHA_API_KEY 环境变量。",
            )
        if search_type == "image":
            return self._bocha.search_image(query, count, freshness)
        else:
            return self._bocha.search_web(query, count, freshness, summary)

    def _search_ddg(self, query, search_type, count, freshness) -> SearchResponse:
        if not self._ddg:
            return SearchResponse(
                query=query, search_type=search_type, engine="duckduckgo",
                success=False, error_message="DuckDuckGo 后端未初始化。",
            )
        if search_type == "image":
            return self._ddg.search_image(query, count, freshness)
        elif search_type == "news":
            return self._ddg.search_news(query, count, freshness)
        else:
            return self._ddg.search_web(query, count, freshness)

    def _search_exa(self, query, search_type, count, freshness) -> SearchResponse:
        if not self._exa:
            return SearchResponse(
                query=query, search_type=search_type, engine="exa",
                success=False,
                error_message="Exa API Key 未配置。请设置 exa_api_key 参数或 EXA_API_KEY 环境变量。",
            )
        if search_type == "news":
            return self._exa.search_news(query, count, freshness)
        else:
            return self._exa.search_web(query, count, freshness)

    _AUTH_ERROR_KEYWORDS = ("API 错误", "401", "403", "unauthorized", "forbidden", "quota", "余额", "额度", "Key")

    def _search_auto(
            self, query, search_type, count, freshness, summary
    ) -> SearchResponse:
        """自动策略：优先 BoCha，失败回退 Exa，再回退 DuckDuckGo。API Key 认证/额度错误不回退，直接暴露。"""
        if self._bocha:
            result = self._search_bocha(query, search_type, count, freshness, summary)
            if result.success and result.results:
                return result

            if not result.success and result.error_message and any(
                kw in result.error_message for kw in self._AUTH_ERROR_KEYWORDS
            ):
                logger.error("BoCha API 认证或额度错误，不回退: %s", result.error_message)
                return result

            logger.warning(
                "BoCha 搜索失败或无结果，回退到 Exa: %s", result.error_message
            )

        if self._exa:
            result = self._search_exa(query, search_type, count, freshness)
            if result.success and result.results:
                return result

            if not result.success and result.error_message and any(
                kw in result.error_message for kw in self._AUTH_ERROR_KEYWORDS
            ):
                logger.error("Exa API 认证或额度错误，不回退: %s", result.error_message)
                return result

            logger.warning(
                "Exa 搜索失败或无结果，回退到 DuckDuckGo: %s", result.error_message
            )

        return self._search_ddg(query, search_type, count, freshness)


class WebSearcher:
    """
    bocha_api_key:  BoCha API Key（也可通过环境变量 BOCHA_API_KEY 设置）
    exa_api_key:    Exa API Key（也可通过环境变量 EXA_API_KEY 设置）
    engine:         搜索引擎 ("bocha" | "duckduckgo" | "exa" | "auto"，默认 auto)
    timeout:        请求超时秒数
    proxy:          代理地址（仅 DuckDuckGo 使用）
    """

    def __init__(
            self,
            bocha_api_key: Optional[str] = None,
            exa_api_key: Optional[str] = None,
            engine: str = "bocha",
            timeout: float = 30.0,
            proxy: Optional[str] = None,
    ):
        self._engine = AISearch(
            bocha_api_key=bocha_api_key,
            exa_api_key=exa_api_key,
            engine=engine,
            timeout=timeout,
            proxy=proxy,
        )

    def search(
            self,
            query: str,
            search_type: str = "text",
            count: int = 10,
            freshness: str = "noLimit",
    ) -> str:
        """搜索互联网获取实时信息，支持网页、图片和新闻三种搜索类型。当你需要查询事实、获取最新资讯、寻找图片素材或了解新闻动态时，请使用此工具。

        Args:
            query: 搜索关键词或问题，例如 "2024年诺贝尔物理学奖得主是谁"
            search_type: 搜索类型，可选值：text（网页搜索，默认）、image（图片搜索，返回图片URL）、news（新闻搜索）
            count: 期望返回的结果数量，范围 1-50，默认 10
            freshness: 时间范围过滤，可选值：noLimit（不限，默认）、oneDay（最近一天）、oneWeek（最近一周）、oneMonth（最近一个月）、oneYear（最近一年）
        """
        result = self._engine.search(
            query=query, search_type=search_type, count=count, freshness=freshness,
        ).to_text()

        return result


if __name__ == "__main__":

    searcher = WebSearcher(
        bocha_api_key='bocha api',
    )

    print(searcher.search("中国移动 国际信息港", count=10, freshness="noLimit"))
