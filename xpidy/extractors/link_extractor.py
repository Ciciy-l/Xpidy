"""
链接提取器
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import Page
from pydantic import Field

from ..utils import URLUtils
from .base_extractor import BaseExtractor, BaseExtractorConfig


class LinkExtractorConfig(BaseExtractorConfig):
    """链接提取器配置"""

    # 链接类型
    include_internal: bool = Field(default=True, description="包含内部链接")
    include_external: bool = Field(default=True, description="包含外部链接")

    # 过滤规则
    include_patterns: List[str] = Field(
        default_factory=list, description="包含的URL模式"
    )
    exclude_patterns: List[str] = Field(
        default_factory=list, description="排除的URL模式"
    )
    allowed_schemes: List[str] = Field(
        default_factory=lambda: ["http", "https"], description="允许的协议"
    )

    # 链接属性
    extract_text: bool = Field(default=True, description="提取链接文本")
    extract_title: bool = Field(default=True, description="提取链接标题")
    extract_anchor: bool = Field(default=True, description="提取锚点")

    # 文件类型过滤
    include_file_types: List[str] = Field(
        default_factory=list, description="包含的文件类型"
    )
    exclude_file_types: List[str] = Field(
        default_factory=lambda: ["pdf", "doc", "docx", "xls", "xlsx"],
        description="排除的文件类型",
    )


class LinkExtractor(BaseExtractor):
    """链接提取器"""

    def __init__(self, config: Optional[LinkExtractorConfig] = None):
        super().__init__(config)

    @classmethod
    def get_default_config(cls) -> LinkExtractorConfig:
        """获取默认配置"""
        return LinkExtractorConfig()

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取页面中的所有链接"""
        current_url = page.url
        base_domain = urlparse(current_url).netloc

        # 获取提取范围
        extraction_scopes = await self._get_extraction_scope(page)

        all_links = []
        for scope in extraction_scopes:
            scope_links = await self._extract_links_from_scope(scope, current_url)
            all_links.extend(scope_links)

        # 过滤和处理链接
        filtered_links = self._filter_and_deduplicate_items(
            all_links, current_url, url_key="url"
        )

        # 分类统计
        internal_count = sum(
            1 for link in filtered_links if link.get("is_internal", False)
        )
        external_count = len(filtered_links) - internal_count

        return {
            "url": current_url,
            "links": filtered_links,
            "total_links": len(filtered_links),
            "internal_links": internal_count,
            "external_links": external_count,
            "timestamp": time.time(),
            "extraction_method": "link_extractor",
        }

    async def _extract_links_from_scope(
        self, scope, base_url: str
    ) -> List[Dict[str, Any]]:
        """从指定范围提取链接"""
        try:
            if hasattr(scope, "query_selector_all"):
                # 这是一个页面或元素
                links_data = await scope.evaluate(
                    """
                    () => {
                        return Array.from(document.querySelectorAll('a[href]')).map(link => ({
                            url: link.href,
                            text: link.textContent?.trim() || '',
                            title: link.title || '',
                            rel: link.rel || '',
                            target: link.target || '',
                            download: link.download || ''
                        }));
                    }
                """
                )
            else:
                # 这是一个元素句柄
                links_data = await scope.evaluate(
                    """
                    (element) => {
                        return Array.from(element.querySelectorAll('a[href]')).map(link => ({
                            url: link.href,
                            text: link.textContent?.trim() || '',
                            title: link.title || '',
                            rel: link.rel || '',
                            target: link.target || '',
                            download: link.download || ''
                        }));
                    }
                """
                )

            processed_links = []
            for link_data in links_data or []:
                processed_link = await self._process_link(link_data, base_url)
                if processed_link:
                    processed_links.append(processed_link)

            return processed_links

        except Exception:
            return []

    async def _process_link(
        self, link_data: Dict[str, Any], base_url: str
    ) -> Optional[Dict[str, Any]]:
        """处理单个链接"""
        url = link_data.get("url", "").strip()
        if not url:
            return None

        # 转换为绝对URL
        absolute_url = urljoin(base_url, url)
        parsed_url = urlparse(absolute_url)
        base_domain = urlparse(base_url).netloc

        # 验证协议
        if parsed_url.scheme not in self.config.allowed_schemes:
            return None

        # 判断内外部链接
        is_internal = parsed_url.netloc == base_domain

        # 过滤内外部链接
        if not self.config.include_internal and is_internal:
            return None
        if not self.config.include_external and not is_internal:
            return None

        # 文件类型过滤
        file_extension = self._get_file_extension(absolute_url)
        if (
            self.config.include_file_types
            and file_extension not in self.config.include_file_types
        ):
            return None
        if file_extension in self.config.exclude_file_types:
            return None

        # URL模式过滤
        if not self._matches_patterns(absolute_url):
            return None

        # 构建结果
        result = {
            "url": absolute_url,
            "original_url": url,
            "is_internal": is_internal,
            "domain": parsed_url.netloc,
            "path": parsed_url.path,
            "file_extension": file_extension,
            "scheme": parsed_url.scheme,
        }

        if self.config.extract_text:
            result["text"] = link_data.get("text", "")

        if self.config.extract_title:
            result["title"] = link_data.get("title", "")

        if self.config.extract_anchor:
            result["anchor"] = parsed_url.fragment

        # 其他属性
        for attr in ["rel", "target", "download"]:
            if link_data.get(attr):
                result[attr] = link_data[attr]

        return result

    def _get_file_extension(self, url: str) -> str:
        """获取文件扩展名"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        if "." in path:
            return path.split(".")[-1]
        return ""

    def _matches_patterns(self, url: str) -> bool:
        """检查URL是否匹配模式"""
        # 检查包含模式
        if self.config.include_patterns:
            if not any(
                re.search(pattern, url, re.IGNORECASE)
                for pattern in self.config.include_patterns
            ):
                return False

        # 检查排除模式
        if self.config.exclude_patterns:
            if any(
                re.search(pattern, url, re.IGNORECASE)
                for pattern in self.config.exclude_patterns
            ):
                return False

        return True

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器"""
        # 文本长度过滤
        if filters.get("min_text_length"):
            text = item.get("text", "")
            if len(text.strip()) < filters["min_text_length"]:
                return False

        # 域名过滤
        if filters.get("allowed_domains"):
            domain = item.get("domain", "")
            if domain not in filters["allowed_domains"]:
                return False

        return True

    async def extract_internal_links(self, page: Page, **kwargs) -> Dict[str, Any]:
        """只提取内部链接"""
        kwargs["only_internal"] = True
        return await self.extract(page, **kwargs)

    async def extract_external_links(self, page: Page, **kwargs) -> Dict[str, Any]:
        """只提取外部链接"""
        kwargs["only_external"] = True
        return await self.extract(page, **kwargs)

    async def extract_by_pattern(
        self, page: Page, pattern: str, **kwargs
    ) -> Dict[str, Any]:
        """根据URL模式提取链接"""
        kwargs["url_pattern"] = pattern
        return await self.extract(page, **kwargs)

    async def extract_sitemap_links(self, page: Page) -> Dict[str, Any]:
        """尝试从sitemap.xml提取链接"""
        try:
            current_url = page.url
            base_domain = URLUtils.extract_domain(current_url)

            # 常见的sitemap路径
            sitemap_paths = [
                "/sitemap.xml",
                "/sitemap_index.xml",
                "/sitemap.txt",
                "/robots.txt",
            ]

            sitemap_links = []

            for path in sitemap_paths:
                try:
                    sitemap_url = urljoin(current_url, path)
                    await page.goto(sitemap_url)
                    content = await page.text_content("body") or ""

                    if path.endswith(".xml"):
                        # 解析XML sitemap
                        urls = URLUtils.extract_sitemap_urls(content)
                        sitemap_links.extend(urls)
                    elif path.endswith("robots.txt"):
                        # 从robots.txt查找sitemap
                        import re

                        sitemap_matches = re.findall(
                            r"Sitemap:\s*(.+)", content, re.IGNORECASE
                        )
                        for sitemap_match in sitemap_matches:
                            try:
                                await page.goto(sitemap_match.strip())
                                sitemap_content = await page.text_content("body") or ""
                                urls = URLUtils.extract_sitemap_urls(sitemap_content)
                                sitemap_links.extend(urls)
                            except Exception:
                                continue

                except Exception:
                    continue

            # 去重和过滤
            unique_links = list(set(sitemap_links))
            valid_links = [url for url in unique_links if URLUtils.is_valid_url(url)]

            return {
                "url": current_url,
                "sitemap_links": valid_links,
                "total_sitemap_links": len(valid_links),
                "extraction_method": "sitemap",
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Sitemap链接提取失败: {e}")
            return {
                "url": page.url,
                "sitemap_links": [],
                "total_sitemap_links": 0,
                "error": str(e),
                "extraction_method": "sitemap",
                "timestamp": time.time(),
            }

    async def analyze_link_structure(self, page: Page) -> Dict[str, Any]:
        """分析页面链接结构"""
        try:
            result = await self.extract(page)
            links = result["links"]

            # 分析链接分布
            navigation_links = [link for link in links if link["inNavigation"]]
            content_links = [link for link in links if link["inMainContent"]]

            # 按父元素分类
            by_parent = {}
            for link in links:
                parent = link["parentTag"]
                if parent not in by_parent:
                    by_parent[parent] = []
                by_parent[parent].append(link)

            # 按域名分类
            by_domain = {}
            for link in links:
                domain = link["domain"]
                if domain not in by_domain:
                    by_domain[domain] = []
                by_domain[domain].append(link)

            return {
                "url": page.url,
                "total_links": len(links),
                "navigation_links": len(navigation_links),
                "content_links": len(content_links),
                "by_parent_tag": {tag: len(links) for tag, links in by_parent.items()},
                "by_domain": {
                    domain: len(links) for domain, links in by_domain.items()
                },
                "unique_domains": len(by_domain),
                "analysis_timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"链接结构分析失败: {e}")
            return {"url": page.url, "error": str(e), "analysis_timestamp": time.time()}
