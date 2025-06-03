"""
数据提取器基类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

from playwright.async_api import Page

from ..core.config import ExtractionConfig
from ..utils import ContentUtils, URLUtils


class BaseExtractor(ABC):
    """数据提取器基类"""

    def __init__(self, config: ExtractionConfig):
        self.config = config

    @abstractmethod
    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取数据"""
        pass

    async def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""

        # 使用ContentUtils的标准化方法
        if self.config.normalize_whitespace:
            text = ContentUtils.normalize_whitespace(text)

        return text

    def _filter_and_deduplicate_items(
        self,
        items: List[Dict[str, Any]],
        base_url: str,
        url_key: str = "url",
        deduplicate: bool = True,
        max_items: Optional[int] = None,
        exclude_patterns: Optional[List[str]] = None,
        **filters,
    ) -> List[Dict[str, Any]]:
        """通用的过滤和去重逻辑"""
        processed = []
        seen_urls: Set[str] = set()

        for item in items:
            try:
                # 获取URL
                url = item.get(url_key, "")
                if not url:
                    continue

                # 转换为绝对URL
                absolute_url = urljoin(base_url, url)

                # 去重
                if deduplicate and absolute_url in seen_urls:
                    continue
                seen_urls.add(absolute_url)

                # 验证URL
                if not URLUtils.is_valid_url(absolute_url):
                    continue

                # 排除模式过滤
                if exclude_patterns and self._should_exclude_by_patterns(
                    absolute_url, exclude_patterns
                ):
                    continue

                # 应用自定义过滤器
                if not self._apply_custom_filters(item, **filters):
                    continue

                # 更新URL为绝对URL
                item[url_key] = absolute_url
                processed.append(item)

                # 限制数量
                if max_items and len(processed) >= max_items:
                    break

            except Exception:
                continue

        return processed

    def _should_exclude_by_patterns(
        self, url: str, exclude_patterns: List[str]
    ) -> bool:
        """检查URL是否应该被排除模式过滤"""
        import re

        for pattern in exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器，子类可以重写此方法"""
        return True

    def _process_urls_to_absolute(
        self, items: List[Dict[str, Any]], base_url: str, url_key: str = "url"
    ) -> List[Dict[str, Any]]:
        """将相对URL转换为绝对URL"""
        for item in items:
            if url_key in item:
                item[url_key] = urljoin(base_url, item[url_key])
        return items

    def _add_url_metadata(
        self, items: List[Dict[str, Any]], base_url: str, url_key: str = "url"
    ) -> List[Dict[str, Any]]:
        """为URL添加元数据信息"""
        for item in items:
            url = item.get(url_key, "")
            if url:
                item["domain"] = URLUtils.extract_domain(url)
                item["is_internal"] = URLUtils.is_same_domain(base_url, url)
                item["file_extension"] = URLUtils.get_file_extension_from_url(url)
                item["is_absolute"] = URLUtils.is_absolute_url(
                    item.get("original_" + url_key, url)
                )
        return items

    async def _get_page_content(self, page: Page) -> str:
        """获取页面内容"""
        # 移除脚本和样式
        if self.config.remove_scripts:
            await page.evaluate(
                "() => { document.querySelectorAll('script').forEach(el => el.remove()); }"
            )

        if self.config.remove_styles:
            await page.evaluate(
                "() => { document.querySelectorAll('style').forEach(el => el.remove()); }"
            )

        # 根据选择器获取内容
        if self.config.content_selectors:
            content_parts = []
            for selector in self.config.content_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    for i in range(count):
                        element = elements.nth(i)
                        text = await element.text_content()
                        if text:
                            content_parts.append(text)
                except Exception:
                    continue
            content = "\n".join(content_parts)
        else:
            # 获取整个页面内容
            content = await page.text_content("body") or ""

        # 排除指定的内容
        if self.config.exclude_selectors:
            for selector in self.config.exclude_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    for i in range(count):
                        element = elements.nth(i)
                        text = await element.text_content()
                        if text and text in content:
                            content = content.replace(text, "")
                except Exception:
                    continue

        return await self._clean_text(content)

    async def _extract_links(self, page: Page) -> List[Dict[str, str]]:
        """提取链接"""
        if not self.config.extract_links:
            return []

        try:
            links = await page.evaluate(
                """
                () => {
                    return Array.from(document.querySelectorAll('a[href]')).map(link => ({
                        text: link.textContent?.trim() || '',
                        href: link.href,
                        title: link.title || ''
                    }));
                }
            """
            )
            return links or []
        except Exception:
            return []

    async def _extract_images(self, page: Page) -> List[Dict[str, str]]:
        """提取图片"""
        if not self.config.extract_images:
            return []

        try:
            images = await page.evaluate(
                """
                () => {
                    return Array.from(document.querySelectorAll('img[src]')).map(img => ({
                        src: img.src,
                        alt: img.alt || '',
                        title: img.title || '',
                        width: img.width || 0,
                        height: img.height || 0
                    }));
                }
            """
            )
            return images or []
        except Exception:
            return []

    async def _extract_metadata(self, page: Page) -> Dict[str, Any]:
        """提取元数据"""
        if not self.config.extract_metadata:
            return {}

        try:
            metadata = await page.evaluate(
                """
                () => {
                    const meta = {};
                    
                    // 标题
                    meta.title = document.title || '';
                    
                    // 描述
                    const description = document.querySelector('meta[name="description"]');
                    meta.description = description ? description.content : '';
                    
                    // 关键词
                    const keywords = document.querySelector('meta[name="keywords"]');
                    meta.keywords = keywords ? keywords.content : '';
                    
                    // Open Graph
                    const ogTitle = document.querySelector('meta[property="og:title"]');
                    const ogDescription = document.querySelector('meta[property="og:description"]');
                    const ogImage = document.querySelector('meta[property="og:image"]');
                    
                    if (ogTitle || ogDescription || ogImage) {
                        meta.og = {
                            title: ogTitle ? ogTitle.content : '',
                            description: ogDescription ? ogDescription.content : '',
                            image: ogImage ? ogImage.content : ''
                        };
                    }
                    
                    // 其他元数据
                    const metaTags = document.querySelectorAll('meta[name], meta[property]');
                    meta.other = {};
                    metaTags.forEach(tag => {
                        const name = tag.getAttribute('name') || tag.getAttribute('property');
                        if (name && !['description', 'keywords'].includes(name) && !name.startsWith('og:')) {
                            meta.other[name] = tag.content;
                        }
                    });
                    
                    return meta;
                }
            """
            )
            return metadata or {}
        except Exception:
            return {}
