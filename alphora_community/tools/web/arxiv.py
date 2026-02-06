import json
from pydantic import BaseModel, Field


class ArxivSearchInput(BaseModel):
    """arXiv 搜索参数"""
    query: str = Field(..., description="搜索关键词（支持标题、摘要、作者）")
    max_results: int = Field(5, ge=1, le=20, description="返回结果数量")
    sort_by: str = Field("relevance", description="排序方式: relevance(相关性)/submittedDate(日期)")


class ArxivSearchTool:
    """
    arXiv 学术论文搜索工具

    搜索 arXiv.org 上的学术论文，获取最新研究成果。
    """

    API_ENDPOINT = "https://export.arxiv.org/api/query"

    def __init__(self):
        """初始化 arXiv 搜索工具（无需 API Key）"""
        pass

    async def search(
            self,
            query: str,
            max_results: int = 5,
            sort_by: str = "relevance"
    ) -> str:
        """
        搜索 arXiv 学术论文。

        Args:
            query: 搜索关键词（支持标题、摘要、作者搜索）
            max_results: 返回结果数量 (1-20)
            sort_by: 排序方式
                - "relevance": 相关性排序（默认）
                - "submittedDate": 按提交日期排序

        Returns:
            论文列表 JSON，包含标题、作者、摘要、PDF 链接
        """
        import httpx
        import xml.etree.ElementTree as ET

        sort_map = {
            "relevance": "relevance",
            "submittedDate": "submittedDate",
            "date": "submittedDate"
        }

        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max_results, 20),
            "sortBy": sort_map.get(sort_by, "relevance"),
            "sortOrder": "descending"
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.API_ENDPOINT, params=params)
                response.raise_for_status()
                xml_content = response.text

            # 解析 XML
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            papers = []
            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                published_elem = entry.find("atom:published", ns)
                id_elem = entry.find("atom:id", ns)

                # 提取作者
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_elem = author.find("atom:name", ns)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text)

                # 获取 PDF 链接
                pdf_url = ""
                arxiv_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href", "")
                    elif link.get("type") == "text/html":
                        arxiv_url = link.get("href", "")

                # 从 ID 提取 arXiv ID
                arxiv_id = ""
                if id_elem is not None and id_elem.text:
                    arxiv_id = id_elem.text.split("/abs/")[-1]

                papers.append({
                    "arxiv_id": arxiv_id,
                    "title": title_elem.text.strip().replace('\n', ' ') if title_elem is not None and title_elem.text else "",
                    "authors": authors[:5],  # 限制作者数量
                    "summary": summary_elem.text.strip()[:1500] if summary_elem is not None and summary_elem.text else "",
                    "published": published_elem.text[:10] if published_elem is not None and published_elem.text else "",
                    "pdf_url": pdf_url,
                    "arxiv_url": arxiv_url or f"https://arxiv.org/abs/{arxiv_id}"
                })

            return json.dumps({
                "success": True,
                "query": query,
                "papers": papers,
                "count": len(papers)
            }, ensure_ascii=False, indent=2)

        except httpx.TimeoutException:
            return json.dumps({
                "success": False,
                "query": query,
                "error": "arXiv 请求超时"
            }, ensure_ascii=False)
        except ET.ParseError as e:
            return json.dumps({
                "success": False,
                "query": query,
                "error": f"XML 解析失败: {str(e)}"
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "query": query,
                "error": str(e)
            }, ensure_ascii=False)


if __name__ == "__main__":
    import asyncio

    arxiv_tool = ArxivSearchTool()

    async def main():
        result = await arxiv_tool.search(query='LLM')
        print(result)
        pass

    asyncio.run(main())

