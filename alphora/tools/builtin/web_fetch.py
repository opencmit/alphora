"""
网页内容读取工具
输入 URL，返回干净的网页正文内容（自动去除导航栏、广告、脚本等噪音）
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from urllib.parse import urlparse

import httpx

try:
    import ssl as _ssl_module
except ImportError:
    _ssl_module = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class FetchResponse:
    """网页抓取结果"""
    url: str  # 请求的 URL
    final_url: str = ""  # 最终 URL（跟随重定向后）
    title: str = ""  # 页面标题
    text: str = ""  # 提取的正文纯文本
    html: str = ""  # 原始 HTML（可选保留）
    content_type: str = ""  # 响应 Content-Type
    status_code: int = 0  # HTTP 状态码
    elapsed_seconds: float = 0.0  # 请求耗时
    success: bool = True
    error_message: str = ""
    links: list[dict] = field(default_factory=list)  # 页面中的链接
    images: list[dict] = field(default_factory=list)  # 页面中的图片
    metadata: dict = field(default_factory=dict)  # meta 标签信息

    def to_dict(self) -> dict:
        d = asdict(self)
        # 不在 dict 输出中包含原始 HTML（太大）
        d.pop("html", None)
        # 清除空值
        return {k: v for k, v in d.items() if v or isinstance(v, (bool, int, float))}

    def to_json(self, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)

    def to_text(self, max_length: int = 0) -> str:
        """
        格式化为纯文本输出，适合直接喂给 LLM。

        参数:
            max_length: 正文最大字符数，0 表示不限制
        """
        lines = []
        if self.title:
            lines.append(f"标题: {self.title}")
        lines.append(f"URL: {self.final_url or self.url}")

        if self.metadata.get("description"):
            lines.append(f"描述: {self.metadata['description']}")

        lines.append("")

        if not self.success:
            lines.append(f"错误: {self.error_message}")
            return "\n".join(lines)

        content = self.text
        if max_length > 0 and len(content) > max_length:
            content = content[:max_length] + f"\n\n... [内容已截断，共 {len(self.text)} 字符]"

        lines.append(content)
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_text(max_length=2000)


class _LiteHTMLParser:
    """
    轻量级 HTML 文本提取器，不依赖 BeautifulSoup。
    用正则做基本清洗，适合 bs4 未安装时的降级方案。
    """

    # 需要完全移除的标签（含内容）
    REMOVE_TAGS = re.compile(
        r"<\s*(script|style|noscript|iframe|svg|canvas|template|head)"
        r"[^>]*>.*?</\s*\1\s*>",
        re.DOTALL | re.IGNORECASE,
    )
    TAG_RE = re.compile(r"<[^>]+>")
    WHITESPACE_RE = re.compile(r"[ \t]+")
    BLANK_LINES_RE = re.compile(r"\n{3,}")

    @classmethod
    def extract_title(cls, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return cls._decode_entities(m.group(1).strip()) if m else ""

    @classmethod
    def extract_text(cls, html: str) -> str:
        text = cls.REMOVE_TAGS.sub("", html)
        text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = re.sub(r"</(p|div|h[1-6]|li|tr|blockquote|article|section)>", "\n", text, flags=re.IGNORECASE)
        text = cls.TAG_RE.sub("", text)
        text = cls._decode_entities(text)
        text = cls.WHITESPACE_RE.sub(" ", text)
        text = cls.BLANK_LINES_RE.sub("\n\n", text)
        return text.strip()

    @classmethod
    def extract_meta(cls, html: str) -> dict:
        meta = {}
        for m in re.finditer(
                r'<meta\s[^>]*(?:name|property)\s*=\s*["\']([^"\']+)["\'][^>]*'
                r'content\s*=\s*["\']([^"\']*)["\']',
                html, re.IGNORECASE,
        ):
            meta[m.group(1).lower()] = m.group(2)
        # 反向匹配 content 在前的情况
        for m in re.finditer(
                r'<meta\s[^>]*content\s*=\s*["\']([^"\']*)["\'][^>]*'
                r'(?:name|property)\s*=\s*["\']([^"\']+)["\']',
                html, re.IGNORECASE,
        ):
            meta[m.group(2).lower()] = m.group(1)
        return meta

    @staticmethod
    def _decode_entities(text: str) -> str:
        import html as html_mod
        return html_mod.unescape(text)


class _BSHTMLParser:
    """
    基于 BeautifulSoup 的高质量 HTML 解析器。
    能更精准地提取正文、链接和图片。
    """

    def __init__(self, html: str, url: str = ""):
        from bs4 import BeautifulSoup
        self.soup = BeautifulSoup(html, "html.parser")
        self.url = url

    def extract_title(self) -> str:
        tag = self.soup.find("title")
        if tag:
            return tag.get_text(strip=True)
        # 尝试 og:title
        og = self.soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            return og["content"]
        # 尝试 h1
        h1 = self.soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return ""

    def extract_text(self) -> str:
        # 移除噪音标签
        for tag_name in ["script", "style", "noscript", "iframe", "svg",
                         "nav", "footer", "header", "aside", "form"]:
            for tag in self.soup.find_all(tag_name):
                tag.decompose()

        # 尝试找 <article> 或 <main> 优先提取正文
        main_content = (
                self.soup.find("article")
                or self.soup.find("main")
                or self.soup.find(attrs={"role": "main"})
                or self.soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
        )

        target = main_content or self.soup.body or self.soup
        text = target.get_text(separator="\n", strip=True)

        # 清理多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def extract_links(self, limit: int = 50) -> list[dict]:
        links = []
        seen = set()
        for a in self.soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            # 简单的相对路径处理
            if href.startswith("/") and self.url:
                parsed = urlparse(self.url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            if href in seen:
                continue
            seen.add(href)
            links.append({
                "text": a.get_text(strip=True)[:100],
                "url": href,
            })
            if len(links) >= limit:
                break
        return links

    def extract_images(self, limit: int = 20) -> list[dict]:
        images = []
        seen = set()
        for img in self.soup.find_all("img", src=True):
            src = img["src"].strip()
            if not src or src.startswith("data:"):
                continue
            if src.startswith("/") and self.url:
                parsed = urlparse(self.url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            if src in seen:
                continue
            seen.add(src)
            images.append({
                "src": src,
                "alt": img.get("alt", "")[:100],
            })
            if len(images) >= limit:
                break
        return images

    def extract_meta(self) -> dict:
        meta = {}
        for tag in self.soup.find_all("meta"):
            key = tag.get("name") or tag.get("property")
            content = tag.get("content")
            if key and content:
                meta[key.lower()] = content
        return meta


class WebFetcher:
    """
    网页内容读取工具。

    参数:
        timeout:        请求超时秒数（默认 30）
        max_content_length: 最大下载字节数（默认 5MB，防止下载巨型文件）
        user_agent:     自定义 User-Agent
        proxy:          代理地址
        extract_links:  是否提取页面链接（默认 True）
        extract_images: 是否提取页面图片（默认 True）
    """

    # 使用真实浏览器 UA，避免被反爬机制拦截
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # 模拟真实浏览器的请求头
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def __init__(
            self,
            timeout: float = 30.0,
            max_content_length: int = 5 * 1024 * 1024,
            user_agent: str = "",
            proxy: Optional[str] = None,
            extract_links: bool = True,
            extract_images: bool = True,
            max_retries: int = 2,
    ):
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.user_agent = user_agent or self.DEFAULT_UA
        self.proxy = proxy
        self.extract_links = extract_links
        self.extract_images = extract_images
        self.max_retries = max_retries

    def fetch(
            self,
            url: str,
            extract_links: Optional[bool] = None,
            extract_images: Optional[bool] = None,
            raw_html: bool = False,
    ) -> FetchResponse:
        """
        抓取并解析网页内容。

        参数:
            url:             目标 URL（必填）
            extract_links:   是否提取链接（覆盖实例设置）
            extract_images:  是否提取图片（覆盖实例设置）
            raw_html:        是否在结果中保留原始 HTML

        返回:
            FetchResponse 对象
        """
        if extract_links is None:
            extract_links = self.extract_links
        if extract_images is None:
            extract_images = self.extract_images

        # 规范化 URL
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        t0 = time.monotonic()

        # ---------- HTTP 请求（带重试和 SSL 降级） ----------
        resp = None
        last_error = ""

        for attempt in range(self.max_retries + 1):
            try:
                import ssl
                # 第一次用默认设置，重试时放宽 SSL 验证
                if attempt == 0:
                    verify = True
                else:
                    # 创建宽松的 SSL 上下文，应对国内部分网站的 SSL 问题
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    verify = ssl_ctx

                headers = {**self.DEFAULT_HEADERS, "User-Agent": self.user_agent}

                with httpx.Client(
                        timeout=self.timeout,
                        follow_redirects=True,
                        proxy=self.proxy,
                        verify=verify,
                        headers=headers,
                        http2=False,  # 避免部分站点 h2 兼容问题
                ) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    break  # 成功，跳出重试

            except httpx.HTTPStatusError as e:
                # HTTP 状态码错误不需要重试（如 403、404）
                return FetchResponse(
                    url=url, status_code=e.response.status_code,
                    success=False,
                    error_message=f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                    elapsed_seconds=time.monotonic() - t0,
                )
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning("请求失败 (第%d次): %s", attempt + 1, last_error)
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))  # 递增等待
                    continue
                return FetchResponse(
                    url=url, success=False,
                    error_message=f"重试 {self.max_retries + 1} 次后仍失败: {last_error}",
                    elapsed_seconds=time.monotonic() - t0,
                )

        elapsed = time.monotonic() - t0
        content_type = resp.headers.get("content-type", "")

        # ---------- 非 HTML 内容处理 ----------
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            # PDF、JSON、纯文本等
            if "application/json" in content_type:
                try:
                    text = json.dumps(resp.json(), ensure_ascii=False, indent=2)
                except Exception:
                    text = resp.text[:self.max_content_length]
            elif "text/" in content_type:
                text = resp.text[:self.max_content_length]
            else:
                text = f"[二进制内容: {content_type}, 大小: {len(resp.content)} bytes]"

            return FetchResponse(
                url=url,
                final_url=str(resp.url),
                text=text,
                content_type=content_type,
                status_code=resp.status_code,
                elapsed_seconds=elapsed,
            )

        # ---------- HTML 解析 ----------
        html = resp.text[:self.max_content_length]

        # 优先使用 BeautifulSoup，降级使用轻量解析器
        try:
            parser = _BSHTMLParser(html, url=str(resp.url))
            title = parser.extract_title()
            text = parser.extract_text()
            links = parser.extract_links() if extract_links else []
            images = parser.extract_images() if extract_images else []
            metadata = parser.extract_meta()
        except ImportError:
            logger.info("bs4 未安装，使用轻量解析器（建议 pip install beautifulsoup4）")
            title = _LiteHTMLParser.extract_title(html)
            text = _LiteHTMLParser.extract_text(html)
            metadata = _LiteHTMLParser.extract_meta(html)
            links = []
            images = []

        # 从 meta 中补充描述
        description = (
                metadata.get("description")
                or metadata.get("og:description")
                or metadata.get("twitter:description")
                or ""
        )
        if description:
            metadata["description"] = description

        return FetchResponse(
            url=url,
            final_url=str(resp.url),
            title=title,
            text=text,
            html=html if raw_html else "",
            content_type=content_type,
            status_code=resp.status_code,
            elapsed_seconds=elapsed,
            links=links,
            images=images,
            metadata=metadata,
        )


_default_fetcher: Optional[WebFetcher] = None


def _get_default_fetcher() -> WebFetcher:
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = WebFetcher()
    return _default_fetcher


from alphora.tools.decorators import tool


@tool
def web_fetch(
        url: str,
        extract_links: bool = True,
        extract_images: bool = True,
        raw_html: bool = False,
        timeout: Optional[float] = None,
) -> str:
    """读取指定 URL 的网页内容，自动提取正文纯文本、标题、链接和图片，去除导航栏、广告、脚本等噪音。适用于需要阅读网页文章、获取页面详情、查看链接内容等场景。

    Args:
        url: 目标网页的完整 URL，例如 "https://example.com/article"
        extract_links: 是否提取页面中的超链接列表，默认 True
        extract_images: 是否提取页面中的图片列表，默认 True
        raw_html: 是否在结果中保留原始 HTML 源码，默认 False
        timeout: 请求超时秒数，默认使用全局设置（30秒）
    """
    if timeout:
        fetcher = WebFetcher(timeout=timeout)
    else:
        fetcher = _get_default_fetcher()

    return fetcher.fetch(
        url=url,
        extract_links=extract_links,
        extract_images=extract_images,
        raw_html=raw_html,
    ).to_text()


if __name__ == "__main__":
    result = web_fetch("https://baijiahao.baidu.com/s?id=1607431792512173135&wfr=spider&for=pc")
    print(result)
