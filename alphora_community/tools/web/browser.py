"""
Web Browser Tool - AI Agent 专用网页内容抓取与解析工具

本工具专为 AI Agent 系统设计，提供统一的字符串输出格式，
使 AI 能够轻松理解和处理任意 URL 的内容。

支持功能:
- HTML 页面智能解析，自动提取正文内容并转换为 Markdown
- PDF 文件文本提取
- JavaScript 动态渲染页面支持 (需要 Playwright)
- 多种文件格式处理 (JSON, XML, Markdown, 纯文本等)
- 自动内容清理，过滤导航、广告等噪音
- 健壮的错误处理和自动重试机制

依赖安装:
    pip install httpx beautifulsoup4 html2text lxml
    pip install pymupdf  # 可选，用于 PDF 解析
    pip install playwright && playwright install chromium  # 可选，用于 JS 渲染

基本用法:
    ```python
    from browser import WebBrowser

    browser = WebBrowser()
    result = await browser.fetch("https://example.com")
    print(result)  # 直接打印格式化的字符串结果
    ```
"""

import re
import json
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field
from enum import Enum
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentType(Enum):
    """内容类型枚举"""
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    XML = "xml"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    BINARY = "binary"
    UNKNOWN = "unknown"


@dataclass
class FetchMetadata:
    """抓取元数据"""
    url: str
    final_url: Optional[str] = None
    title: Optional[str] = None
    content_type: Optional[str] = None
    detected_type: Optional[ContentType] = None
    status_code: Optional[int] = None
    content_length: Optional[int] = None
    truncated: bool = False
    links_count: int = 0
    images_count: int = 0
    pdf_pages: Optional[int] = None
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class HTMLParser:
    """HTML 内容解析器 - 智能提取网页正文"""

    REMOVE_TAGS = [
        'script', 'style', 'nav', 'footer', 'header', 'aside',
        'noscript', 'iframe', 'svg', 'canvas', 'form', 'button',
        'input', 'select', 'textarea', 'advertisement', 'ad',
    ]

    REMOVE_SELECTORS = [
        '[class*="sidebar"]', '[class*="menu"]', '[class*="nav"]',
        '[class*="footer"]', '[class*="header"]', '[class*="ad"]',
        '[class*="comment"]', '[class*="share"]', '[class*="social"]',
        '[class*="cookie"]', '[class*="popup"]', '[class*="modal"]',
        '[id*="sidebar"]', '[id*="menu"]', '[id*="nav"]',
        '[id*="footer"]', '[id*="header"]', '[id*="ad"]',
    ]

    CONTENT_SELECTORS = [
        'article', '[role="main"]', 'main',
        '.post-content', '.article-content', '.entry-content',
        '.content', '#content', '.post', '.article',
        '.blog-post', '.markdown-body', '.prose',
    ]

    def __init__(self):
        try:
            from bs4 import BeautifulSoup
            self.BeautifulSoup = BeautifulSoup
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("BeautifulSoup not available. Install: pip install beautifulsoup4")

    def parse(self, html: str, base_url: str = "") -> Dict[str, Any]:
        """解析 HTML 并提取结构化内容"""
        if not self.available:
            return self._fallback_parse(html)

        soup = self.BeautifulSoup(html, 'html.parser')
        title = self._extract_title(soup)
        self._remove_unwanted_elements(soup)
        main_content = self._extract_main_content(soup)
        links = self._extract_links(soup, base_url)
        images = self._extract_images(soup, base_url)
        markdown_content = self._html_to_markdown(main_content)

        return {
            'title': title,
            'content': markdown_content,
            'links': links,
            'images': images,
        }

    def _extract_title(self, soup) -> Optional[str]:
        """提取页面标题"""
        for source in [
            soup.find('meta', property='og:title'),
            soup.find('meta', attrs={'name': 'title'}),
            soup.find('title'),
            soup.find('h1'),
        ]:
            if source:
                title = source.get('content', '') if source.name == 'meta' else source.get_text(strip=True)
                if title:
                    return title
        return None

    def _remove_unwanted_elements(self, soup):
        """移除不需要的 HTML 元素"""
        for tag in self.REMOVE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()

        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        for element in soup.find_all(style=re.compile(r'display:\s*none', re.I)):
            element.decompose()

        from bs4 import Comment
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    def _extract_main_content(self, soup):
        """提取主要内容区域"""
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > 100:
                return content
        body = soup.find('body')
        return body if body else soup

    def _extract_links(self, soup, base_url: str) -> List[Dict[str, str]]:
        """提取页面链接"""
        links, seen = [], set()
        for a in soup.find_all('a', href=True):
            href, text = a['href'], a.get_text(strip=True)
            if base_url and not href.startswith(('http://', 'https://', 'mailto:', 'tel:', 'javascript:')):
                href = urljoin(base_url, href)
            if href.startswith(('javascript:', 'mailto:', 'tel:', '#')) or href in seen:
                continue
            seen.add(href)
            links.append({'url': href, 'text': text[:100] if text else ''})
        return links[:50]

    def _extract_images(self, soup, base_url: str) -> List[Dict[str, str]]:
        """提取页面图片"""
        images, seen = [], set()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not src:
                continue
            if base_url and not src.startswith(('http://', 'https://', 'data:')):
                src = urljoin(base_url, src)
            if src.startswith('data:') or src in seen:
                continue
            seen.add(src)
            images.append({'url': src, 'alt': img.get('alt', '')[:100]})
        return images[:30]

    def _html_to_markdown(self, element) -> str:
        """将 HTML 转换为 Markdown 格式"""
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.body_width = 0
            h.unicode_snob = True
            h.skip_internal_links = True
            h.ignore_tables = False
            return h.handle(str(element))
        except ImportError:
            return self._simple_text_extract(element)

    def _simple_text_extract(self, element) -> str:
        """简单的文本提取（回退方案）"""
        if not self.available:
            text = re.sub(r'<script[^>]*>.*?</script>', '', str(element), flags=re.DOTALL | re.I)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.I)
            text = re.sub(r'<[^>]+>', ' ', text)
            return re.sub(r'\s+', ' ', text).strip()

        lines = []
        for elem in element.descendants:
            if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"\n{'#' * int(elem.name[1])} {text}\n")
            elif elem.name == 'p':
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"\n{text}\n")
            elif elem.name == 'li':
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")
            elif elem.name in ['code', 'pre']:
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"\n```\n{text}\n```\n")
        return '\n'.join(lines)

    def _fallback_parse(self, html: str) -> Dict[str, Any]:
        """不使用 BeautifulSoup 的回退解析"""
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
        title = title_match.group(1).strip() if title_match else None

        content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.I)
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()

        return {'title': title, 'content': content, 'links': [], 'images': []}


class PDFParser:
    """PDF 内容解析器 - 支持智能换行合并"""

    def __init__(self):
        self.available = False
        self.parser_type = None

        try:
            import fitz
            self.fitz = fitz
            self.available = True
            self.parser_type = 'pymupdf'
        except ImportError:
            try:
                import pdfplumber
                self.pdfplumber = pdfplumber
                self.available = True
                self.parser_type = 'pdfplumber'
            except ImportError:
                logger.warning("No PDF parser available. Install: pip install pymupdf")

    def _clean_pdf_text(self, text: str) -> str:
        """
        智能清理 PDF 提取的文本，合并不必要的换行。

        处理：
        1. 连字符断词合并 (如 "deter-\\nministic" → "deterministic")
        2. 段落内换行合并（保持段落分隔）
        3. 清理多余空白
        """
        if not text:
            return text

        # 1. 处理连字符断词：行末连字符 + 换行 + 小写字母开头 → 合并
        text = re.sub(r'-\n([a-z])', r'\1', text)

        # 2. 将文本按行分割处理
        lines = text.split('\n')
        cleaned_lines = []
        current_paragraph = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 空行表示段落结束
            if not stripped:
                if current_paragraph:
                    cleaned_lines.append(' '.join(current_paragraph))
                    current_paragraph = []
                cleaned_lines.append('')  # 保留段落分隔
                continue

            # 判断是否是新段落的开始
            is_new_paragraph = False

            # 新段落的特征：
            # - 以数字+点开头（如 "1. Introduction"）
            # - 以大写字母开头且前一行以句末标点结束
            # - 看起来像标题（全大写或很短的行）
            # - 以 "•", "-", "*" 等列表符号开头
            if re.match(r'^\d+\.?\s+[A-Z]', stripped):  # 编号标题
                is_new_paragraph = True
            elif re.match(r'^[•\-\*]\s+', stripped):  # 列表项
                is_new_paragraph = True
            elif re.match(r'^(Abstract|Introduction|Conclusion|References|Acknowledgment)', stripped, re.I):
                is_new_paragraph = True
            elif stripped.isupper() and len(stripped) < 100:  # 全大写标题
                is_new_paragraph = True
            elif current_paragraph:
                last_line = current_paragraph[-1]
                # 前一行以句末标点结束，当前行以大写开头
                if re.search(r'[.!?:]\s*$', last_line) and re.match(r'^[A-Z]', stripped):
                    # 但要排除一些常见的缩写情况
                    if not re.search(r'\b(Fig|Tab|Eq|et al|i\.e|e\.g|vs|Dr|Mr|Mrs|Prof)\.\s*$', last_line, re.I):
                        is_new_paragraph = True

            if is_new_paragraph and current_paragraph:
                cleaned_lines.append(' '.join(current_paragraph))
                current_paragraph = []

            current_paragraph.append(stripped)

        # 处理最后一个段落
        if current_paragraph:
            cleaned_lines.append(' '.join(current_paragraph))

        # 3. 合并结果，清理多余空行
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)  # 最多保留一个空行

        return result.strip()

    def parse(self, pdf_content: bytes, max_pages: int = 50) -> Dict[str, Any]:
        """解析 PDF 内容"""
        if not self.available:
            return {'content': None, 'error': 'No PDF parser available. Install pymupdf or pdfplumber.', 'metadata': {}}

        if self.parser_type == 'pymupdf':
            return self._parse_with_pymupdf(pdf_content, max_pages)
        return self._parse_with_pdfplumber(pdf_content, max_pages)

    def _parse_with_pymupdf(self, pdf_content: bytes, max_pages: int) -> Dict[str, Any]:
        try:
            doc = self.fitz.open(stream=pdf_content, filetype="pdf")
            metadata = {
                'page_count': doc.page_count,
                'title': doc.metadata.get('title'),
                'author': doc.metadata.get('author'),
            }
            text_parts = []
            pages_parsed = min(doc.page_count, max_pages)
            for page_num in range(pages_parsed):
                text = doc[page_num].get_text("text")
                if text.strip():
                    # 对每页文本进行清理
                    cleaned_text = self._clean_pdf_text(text)
                    text_parts.append(f"--- Page {page_num + 1} ---\n{cleaned_text}")
            doc.close()
            return {'content': '\n\n'.join(text_parts), 'metadata': metadata, 'pages_parsed': pages_parsed}
        except Exception as e:
            return {'content': None, 'error': f'PDF parsing failed: {str(e)}', 'metadata': {}}

    def _parse_with_pdfplumber(self, pdf_content: bytes, max_pages: int) -> Dict[str, Any]:
        import io
        try:
            with self.pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                metadata = {'page_count': len(pdf.pages), 'title': pdf.metadata.get('Title')}
                text_parts = []
                pages_parsed = min(len(pdf.pages), max_pages)
                for i, page in enumerate(pdf.pages[:max_pages]):
                    text = page.extract_text()
                    if text and text.strip():
                        # 对每页文本进行清理
                        cleaned_text = self._clean_pdf_text(text)
                        text_parts.append(f"--- Page {i + 1} ---\n{cleaned_text}")
                return {'content': '\n\n'.join(text_parts), 'metadata': metadata, 'pages_parsed': pages_parsed}
        except Exception as e:
            return {'content': None, 'error': f'PDF parsing failed: {str(e)}', 'metadata': {}}


class WebBrowser:
    """
    AI Agent 专用智能网页浏览器工具

    专为 AI Agent 系统设计，fetch 方法直接返回格式化的字符串结果，
    便于 AI 理解和处理。支持多种内容类型的抓取和解析。

    Attributes:
        user_agent: HTTP 请求使用的 User-Agent
        timeout: 请求超时时间（秒）
        max_retries: 请求失败时的最大重试次数
        use_playwright: 是否默认使用 Playwright 渲染 JavaScript

    Example:
        ```python
        browser = WebBrowser()

        # 抓取网页
        result = await browser.fetch("https://example.com")
        print(result)

        # 抓取 PDF
        result = await browser.fetch("https://example.com/doc.pdf")
        print(result)

        # 抓取需要 JS 渲染的页面
        result = await browser.fetch("https://spa-app.com", render_js=True)
        print(result)
        ```
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    CONTENT_TYPE_MAP = {
        'text/html': ContentType.HTML,
        'application/xhtml+xml': ContentType.HTML,
        'application/pdf': ContentType.PDF,
        'application/json': ContentType.JSON,
        'text/json': ContentType.JSON,
        'application/xml': ContentType.XML,
        'text/xml': ContentType.XML,
        'text/markdown': ContentType.MARKDOWN,
        'text/x-markdown': ContentType.MARKDOWN,
        'text/plain': ContentType.PLAIN_TEXT,
        'image/': ContentType.IMAGE,
        'video/': ContentType.VIDEO,
        'audio/': ContentType.AUDIO,
    }

    def __init__(
            self,
            user_agent: Optional[str] = None,
            timeout: int = 30,
            max_retries: int = 3,
            use_playwright: bool = False,
    ):
        """
        初始化 WebBrowser 实例。

        Args:
            user_agent: 自定义 User-Agent 字符串。如果为 None，使用默认的 Chrome User-Agent。
            timeout: HTTP 请求超时时间，单位为秒，默认 30 秒。
            max_retries: 请求失败时的最大重试次数，默认 3 次。
            use_playwright: 是否默认使用 Playwright 进行 JavaScript 渲染，默认 False。
                           设为 True 可以抓取 SPA 单页应用等需要 JS 渲染的页面。
        """
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_playwright = use_playwright
        self.html_parser = HTMLParser()
        self.pdf_parser = PDFParser()
        self._playwright_available = None

    async def fetch(
            self,
            url: str,
            max_length: int = 100000,
            extract_links: bool = False,
            extract_images: bool = False,
            render_js: bool = False,
            wait_for_selector: Optional[str] = None,
            max_pdf_pages: int = 50,
            output_format: str = "markdown",
    ) -> str:
        """
        抓取并解析指定 URL 的内容，返回格式化的字符串结果。

        这是 WebBrowser 的核心方法，专为 AI Agent 设计。它会自动检测内容类型
        （HTML、PDF、JSON 等），进行智能解析，并返回易于 AI 理解的格式化文本。

        Args:
            url: 要抓取的目标 URL。支持 http:// 和 https:// 协议。
                 如果 URL 不包含协议前缀，会自动添加 https://。

            max_length: 返回内容的最大字符数，默认 100000（约 100KB）。
                       超出此长度的内容会被截断，并在末尾添加截断提示。
                       对于大型文档，建议适当增加此值。

            extract_links: 是否提取页面中的链接，默认 False。
                          设为 True 时，返回结果会包含页面中所有链接的列表。
                          适用于需要进一步爬取或分析页面结构的场景。

            extract_images: 是否提取页面中的图片，默认 False。
                           设为 True 时，返回结果会包含页面中所有图片的 URL 列表。

            render_js: 是否使用 Playwright 渲染 JavaScript，默认 False。
                      对于 SPA 单页应用、动态加载内容的页面，需要设为 True。
                      注意：需要预先安装 Playwright (pip install playwright && playwright install chromium)

            wait_for_selector: 当 render_js=True 时，等待指定的 CSS 选择器出现后再提取内容。
                              例如: wait_for_selector=".main-content" 会等待 class="main-content" 的元素出现。
                              适用于内容异步加载的页面。

            max_pdf_pages: PDF 文件最大解析页数，默认 50 页。
                          对于大型 PDF 文档，可以通过此参数限制解析范围以提高性能。

            output_format: 输出格式，可选 "markdown"（默认）或 "plain"。
                          - "markdown": 返回 Markdown 格式，保留标题、列表、链接等结构
                          - "plain": 返回纯文本格式，适合简单的文本分析

        Returns:
            str: 格式化的字符串结果，包含以下信息：

            成功时的返回格式：
            ```
            ================================================================================
            URL: https://example.com
            Final URL: https://example.com/  (如果发生重定向)
            Title: Example Domain
            Content-Type: text/html; charset=UTF-8
            Detected Type: html
            Content Length: 1234 characters
            ================================================================================

            [页面正文内容，Markdown 或纯文本格式]

            ================================================================================
            Links (10 found):    (如果 extract_links=True)
            - Example Link: https://example.com/link1
            - Another Link: https://example.com/link2
            ...

            Images (5 found):    (如果 extract_images=True)
            - https://example.com/image1.jpg (alt: Description)
            ...
            ================================================================================
            ```

            失败时的返回格式：
            ```
            ================================================================================
            FETCH ERROR
            URL: https://example.com
            Error: HTTP 404: Not Found
            ================================================================================
            ```

        Raises:
            不会抛出异常，所有错误都会被捕获并以字符串形式返回。

        Examples:
            基本用法 - 抓取网页:
            >>> browser = WebBrowser()
            >>> result = await browser.fetch("https://example.com")
            >>> print(result)

            抓取 PDF 文档:
            >>> result = await browser.fetch("https://example.com/document.pdf", max_pdf_pages=10)
            >>> print(result)

            抓取需要 JS 渲染的 SPA 应用:
            >>> result = await browser.fetch(
            ...     "https://spa-app.com",
            ...     render_js=True,
            ...     wait_for_selector=".content-loaded"
            ... )
            >>> print(result)

            提取页面链接用于进一步爬取:
            >>> result = await browser.fetch("https://example.com", extract_links=True)
            >>> print(result)

            抓取 JSON API:
            >>> result = await browser.fetch("https://api.example.com/data.json")
            >>> print(result)  # JSON 会被格式化输出

        Notes:
            - 对于 HTML 页面，会自动过滤导航栏、侧边栏、广告等噪音内容，只提取正文
            - 对于 PDF 文件，需要安装 pymupdf 或 pdfplumber
            - 对于需要 JS 渲染的页面，需要安装 playwright
            - 支持自动处理重定向，final_url 会显示最终的实际 URL
            - 支持自动重试，遇到网络错误会自动重试 max_retries 次
        """
        # 验证并规范化 URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme:
            url = 'https://' + url
            parsed_url = urlparse(url)

        if parsed_url.scheme not in ('http', 'https'):
            return self._format_error(url, f"Unsupported URL scheme: {parsed_url.scheme}")

        # 选择抓取方式
        try:
            if render_js or self.use_playwright:
                if await self._check_playwright():
                    result = await self._fetch_with_playwright(
                        url, max_length, extract_links, extract_images,
                        wait_for_selector, max_pdf_pages
                    )
                else:
                    logger.warning("Playwright not available, falling back to httpx")
                    result = await self._fetch_with_httpx(
                        url, max_length, extract_links, extract_images, max_pdf_pages
                    )
            else:
                result = await self._fetch_with_httpx(
                    url, max_length, extract_links, extract_images, max_pdf_pages
                )

            # 格式化输出
            return self._format_result(result, output_format)

        except Exception as e:
            logger.exception(f"Unexpected error fetching {url}")
            return self._format_error(url, f"Unexpected error: {str(e)}")

    def _format_result(self, result: Dict[str, Any], output_format: str) -> str:
        """将抓取结果格式化为字符串"""
        lines = []
        sep = "=" * 80

        # 头部信息
        lines.append(sep)
        lines.append(f"URL: {result['url']}")

        if result.get('final_url') and result['final_url'] != result['url']:
            lines.append(f"Final URL: {result['final_url']}")

        if result.get('title'):
            lines.append(f"Title: {result['title']}")

        if result.get('content_type'):
            lines.append(f"Content-Type: {result['content_type']}")

        if result.get('detected_type'):
            lines.append(f"Detected Type: {result['detected_type']}")

        content = result.get('content', '')
        lines.append(f"Content Length: {len(content)} characters")

        if result.get('truncated'):
            lines.append("Note: Content was truncated due to length limit")

        if result.get('pdf_pages'):
            lines.append(f"PDF Pages: {result.get('pages_parsed', 'N/A')}/{result['pdf_pages']}")

        lines.append(sep)
        lines.append("")

        # 主要内容
        if content:
            lines.append(content)
        else:
            lines.append("[No content extracted]")

        # 链接和图片
        links = result.get('links', [])
        images = result.get('images', [])

        if links or images:
            lines.append("")
            lines.append(sep)

        if links:
            lines.append(f"Links ({len(links)} found):")
            for link in links[:20]:  # 最多显示 20 个
                text = link.get('text', '').strip()
                url = link.get('url', '')
                if text:
                    lines.append(f"  - {text}: {url}")
                else:
                    lines.append(f"  - {url}")
            if len(links) > 20:
                lines.append(f"  ... and {len(links) - 20} more links")
            lines.append("")

        if images:
            lines.append(f"Images ({len(images)} found):")
            for img in images[:10]:  # 最多显示 10 个
                url = img.get('url', '')
                alt = img.get('alt', '')
                if alt:
                    lines.append(f"  - {url} (alt: {alt})")
                else:
                    lines.append(f"  - {url}")
            if len(images) > 10:
                lines.append(f"  ... and {len(images) - 10} more images")

        if links or images:
            lines.append(sep)

        return '\n'.join(lines)

    def _format_error(self, url: str, error: str) -> str:
        """格式化错误信息"""
        sep = "=" * 80
        return f"""
{sep}
FETCH ERROR
URL: {url}
Error: {error}
{sep}
""".strip()

    async def _check_playwright(self) -> bool:
        """检查 Playwright 是否可用"""
        if self._playwright_available is not None:
            return self._playwright_available
        try:
            from playwright.async_api import async_playwright
            self._playwright_available = True
        except ImportError:
            self._playwright_available = False
        return self._playwright_available

    async def _fetch_with_httpx(
            self,
            url: str,
            max_length: int,
            extract_links: bool,
            extract_images: bool,
            max_pdf_pages: int,
    ) -> Dict[str, Any]:
        """使用 httpx 抓取内容"""
        import httpx

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                        timeout=self.timeout,
                        follow_redirects=True,
                        headers=headers,
                ) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return await self._process_response(
                        response, url, max_length, extract_links,
                        extract_images, max_pdf_pages
                    )
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
                if e.response.status_code in (429, 503):
                    await asyncio.sleep(2 ** attempt)
                else:
                    break
            except httpx.TimeoutException:
                last_error = "Request timeout"
                await asyncio.sleep(1)
            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
                await asyncio.sleep(1)
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                break

        return {'url': url, 'error': last_error or "Unknown error"}

    async def _fetch_with_playwright(
            self,
            url: str,
            max_length: int,
            extract_links: bool,
            extract_images: bool,
            wait_for_selector: Optional[str],
            max_pdf_pages: int,
    ) -> Dict[str, Any]:
        """使用 Playwright 抓取和渲染内容"""
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={'width': 1920, 'height': 1080},
                )
                page = await context.new_page()
                page.set_default_timeout(self.timeout * 1000)

                response = await page.goto(url, wait_until='networkidle')
                if not response:
                    await browser.close()
                    return {'url': url, 'error': "No response received"}

                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=10000)
                    except:
                        pass

                content_type = response.headers.get('content-type', '')
                detected_type = self._detect_content_type(content_type, url)
                final_url = page.url
                html_content = await page.content()
                await browser.close()

                parsed = self.html_parser.parse(html_content, final_url)
                content = parsed.get('content', '')
                truncated = False
                if len(content) > max_length:
                    content = content[:max_length] + "\n\n[Content truncated...]"
                    truncated = True

                return {
                    'url': url,
                    'final_url': final_url if final_url != url else None,
                    'title': parsed.get('title'),
                    'content': content,
                    'content_type': content_type,
                    'detected_type': detected_type.value,
                    'truncated': truncated,
                    'links': parsed.get('links') if extract_links else None,
                    'images': parsed.get('images') if extract_images else None,
                }

        except Exception as e:
            return {'url': url, 'error': f"Playwright error: {str(e)}"}

    async def _process_response(
            self,
            response,
            url: str,
            max_length: int,
            extract_links: bool,
            extract_images: bool,
            max_pdf_pages: int,
    ) -> Dict[str, Any]:
        """处理 HTTP 响应"""
        content_type = response.headers.get('content-type', '')
        detected_type = self._detect_content_type(content_type, url)
        final_url = str(response.url)

        base_result = {
            'url': url,
            'final_url': final_url if final_url != url else None,
            'content_type': content_type,
            'detected_type': detected_type.value,
            'status_code': response.status_code,
        }

        if detected_type == ContentType.PDF:
            return await self._process_pdf(response.content, base_result, max_pdf_pages)
        elif detected_type == ContentType.HTML:
            return await self._process_html(
                response.text, base_result, max_length, extract_links, extract_images, final_url
            )
        elif detected_type == ContentType.JSON:
            return await self._process_json(response.text, base_result, max_length)
        elif detected_type in (ContentType.MARKDOWN, ContentType.PLAIN_TEXT, ContentType.XML):
            return await self._process_text(response.text, base_result, max_length)
        elif detected_type in (ContentType.IMAGE, ContentType.VIDEO, ContentType.AUDIO):
            return await self._process_media(response, base_result)
        else:
            try:
                return await self._process_text(response.text, base_result, max_length)
            except:
                base_result['content'] = f"[Binary content: {len(response.content)} bytes]"
                base_result['detected_type'] = ContentType.BINARY.value
                return base_result

    async def _process_pdf(
            self, content: bytes, base_result: Dict, max_pdf_pages: int
    ) -> Dict[str, Any]:
        """处理 PDF 内容"""
        result = self.pdf_parser.parse(content, max_pdf_pages)

        if result.get('error'):
            base_result['error'] = result['error']
            return base_result

        metadata = result.get('metadata', {})
        base_result.update({
            'title': metadata.get('title'),
            'content': result.get('content', ''),
            'pdf_pages': metadata.get('page_count'),
            'pages_parsed': result.get('pages_parsed'),
        })
        return base_result

    async def _process_html(
            self,
            html: str,
            base_result: Dict,
            max_length: int,
            extract_links: bool,
            extract_images: bool,
            final_url: str,
    ) -> Dict[str, Any]:
        """处理 HTML 内容"""
        parsed = self.html_parser.parse(html, final_url)

        content = parsed.get('content', '')
        truncated = False
        if len(content) > max_length:
            content = content[:max_length] + "\n\n[Content truncated...]"
            truncated = True

        base_result.update({
            'title': parsed.get('title'),
            'content': content,
            'truncated': truncated,
            'links': parsed.get('links') if extract_links else None,
            'images': parsed.get('images') if extract_images else None,
        })
        return base_result

    async def _process_json(
            self, text: str, base_result: Dict, max_length: int
    ) -> Dict[str, Any]:
        """处理 JSON 内容"""
        try:
            data = json.loads(text)
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            truncated = False
            if len(formatted) > max_length:
                formatted = formatted[:max_length] + "\n\n[Content truncated...]"
                truncated = True
            base_result.update({
                'content': f"```json\n{formatted}\n```",
                'truncated': truncated,
            })
        except json.JSONDecodeError:
            base_result['content'] = text[:max_length]
            base_result['truncated'] = len(text) > max_length
        return base_result

    async def _process_text(
            self, text: str, base_result: Dict, max_length: int
    ) -> Dict[str, Any]:
        """处理纯文本内容"""
        truncated = len(text) > max_length
        base_result.update({
            'content': text[:max_length] + ("\n\n[Content truncated...]" if truncated else ""),
            'truncated': truncated,
        })
        return base_result

    async def _process_media(self, response, base_result: Dict) -> Dict[str, Any]:
        """处理媒体文件"""
        file_size = len(response.content)
        type_name = base_result.get('detected_type', 'unknown').capitalize()
        base_result['content'] = f"[{type_name} file: {file_size} bytes]\nContent-Type: {base_result.get('content_type', 'unknown')}"
        return base_result

    def _detect_content_type(self, content_type: str, url: str) -> ContentType:
        """检测内容类型"""
        content_type_lower = content_type.lower()

        for mime, ctype in self.CONTENT_TYPE_MAP.items():
            if mime in content_type_lower:
                return ctype

        path = urlparse(url).path.lower()
        ext_map = {
            '.html': ContentType.HTML, '.htm': ContentType.HTML,
            '.pdf': ContentType.PDF, '.json': ContentType.JSON,
            '.xml': ContentType.XML, '.md': ContentType.MARKDOWN,
            '.markdown': ContentType.MARKDOWN, '.txt': ContentType.PLAIN_TEXT,
            '.jpg': ContentType.IMAGE, '.jpeg': ContentType.IMAGE,
            '.png': ContentType.IMAGE, '.gif': ContentType.IMAGE,
            '.webp': ContentType.IMAGE, '.svg': ContentType.IMAGE,
            '.mp4': ContentType.VIDEO, '.webm': ContentType.VIDEO,
            '.mp3': ContentType.AUDIO, '.wav': ContentType.AUDIO,
        }

        for ext, ctype in ext_map.items():
            if path.endswith(ext):
                return ctype

        if not content_type or 'text' in content_type_lower:
            return ContentType.HTML
        return ContentType.UNKNOWN


if __name__ == '__main__':
    wb = WebBrowser()

    async def main():
        r = await wb.fetch(url='https://arxiv.org/pdf/2601.17768v2')
        print(r)
        pass

    asyncio.run(main())