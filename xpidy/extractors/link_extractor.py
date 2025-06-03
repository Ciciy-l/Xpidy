"""
链接提取器
"""

import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import Page

from ..utils import URLUtils
from .base_extractor import BaseExtractor


class LinkExtractor(BaseExtractor):
    """链接提取器"""

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取链接数据"""
        try:
            # 获取页面URL
            current_url = page.url

            # 提取链接
            links = await self._extract_links(page)

            # 处理链接
            processed_links = await self._process_links(links, current_url, **kwargs)

            # 统计信息
            internal_links = [link for link in processed_links if link["is_internal"]]
            external_links = [
                link for link in processed_links if not link["is_internal"]
            ]

            return {
                "url": current_url,
                "links": processed_links,
                "internal_links": internal_links,
                "external_links": external_links,
                "total_links": len(processed_links),
                "total_internal_links": len(internal_links),
                "total_external_links": len(external_links),
                "extraction_method": "enhanced",
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"链接提取失败: {e}")
            raise

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

    async def _extract_links(self, page: Page) -> List[Dict[str, str]]:
        """重写基类方法，增强链接提取功能"""
        try:
            links = await page.evaluate(
                """
                () => {
                    const links = [];
                    const linkElements = document.querySelectorAll('a[href]');
                    
                    linkElements.forEach(link => {
                        // 基本信息
                        const linkData = {
                            text: link.textContent?.trim() || '',
                            href: link.href,
                            title: link.title || '',
                            target: link.target || '',
                            rel: link.rel || '',
                            download: link.download || '',
                            className: link.className || '',
                            id: link.id || ''
                        };
                        
                        // 父元素信息
                        const parent = link.parentElement;
                        if (parent) {
                            linkData.parentTag = parent.tagName.toLowerCase();
                            linkData.parentClass = parent.className || '';
                        }
                        
                        // 检查是否在导航区域
                        linkData.inNavigation = !!link.closest('nav, .nav, .navigation, .menu, header, .header');
                        
                        // 检查是否在主要内容区域
                        linkData.inMainContent = !!link.closest('main, .main, .content, article, .article');
                        
                        links.push(linkData);
                    });
                    
                    return links;
                }
            """
            )
            return links or []
        except Exception as e:
            logger.warning(f"JavaScript链接提取失败，使用备用方法: {e}")
            return await super()._extract_links(page)

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用链接特定的过滤器"""
        # 内部/外部链接过滤
        only_internal = filters.get("only_internal", False)
        only_external = filters.get("only_external", False)

        if only_internal and not item.get("is_internal", False):
            return False
        if only_external and item.get("is_internal", False):
            return False

        # URL模式过滤
        url_pattern = filters.get("url_pattern")
        if url_pattern:
            import re

            if not re.search(url_pattern, item.get("url", ""), re.IGNORECASE):
                return False

        # 媒体文件过滤
        include_media = filters.get("include_media", True)
        if not include_media and URLUtils.is_media_url(item.get("url", "")):
            return False

        return True

    async def _process_links(
        self, links: List[Dict[str, str]], base_url: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """处理和过滤链接"""
        # 预处理：添加原始href信息
        for link in links:
            link["original_href"] = link.get("href", "")

        # 使用基类的通用过滤方法
        processed = self._filter_and_deduplicate_items(
            links,
            base_url,
            url_key="href",
            deduplicate=kwargs.get("deduplicate", True),
            max_items=kwargs.get("max_links"),
            exclude_patterns=kwargs.get("exclude_patterns", []),
            **kwargs,
        )

        # 添加链接特定的元数据
        for link in processed:
            # 重命名href为url以保持一致性
            link["url"] = link.pop("href")

            # 清理文本
            link["text"] = await self._clean_text(link.get("text", ""))

            # 添加链接特定的属性
            link["is_media"] = URLUtils.is_media_url(link["url"])

        # 添加URL元数据
        self._add_url_metadata(processed, base_url, url_key="url")

        return processed

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
