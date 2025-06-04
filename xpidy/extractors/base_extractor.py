"""
数据提取器基类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urljoin

from playwright.async_api import Page
from pydantic import BaseModel, Field

from ..core.config import ExtractionConfig
from ..utils import ContentUtils, URLUtils


class BaseExtractorConfig(BaseModel):
    """提取器基础配置"""

    enabled: bool = Field(default=True, description="是否启用此提取器")
    selectors: Optional[List[str]] = Field(
        default=None, description="CSS选择器列表，限制提取范围"
    )
    xpath_selectors: Optional[List[str]] = Field(
        default=None, description="XPath选择器列表，限制提取范围"
    )
    exclude_selectors: Optional[List[str]] = Field(
        default_factory=list, description="排除的选择器"
    )

    # 通用处理配置
    clean_text: bool = Field(default=True, description="清理文本")
    normalize_whitespace: bool = Field(default=True, description="标准化空白字符")
    deduplicate: bool = Field(default=True, description="去重")
    max_items: Optional[int] = Field(default=None, description="最大提取数量")


class BaseExtractor(ABC):
    """数据提取器基类"""

    def __init__(self, config: Optional[BaseExtractorConfig] = None):
        self.config = config or self.get_default_config()
        self._cached_results: Optional[Dict[str, Any]] = None

    @classmethod
    @abstractmethod
    def get_default_config(cls) -> BaseExtractorConfig:
        """获取默认配置"""
        pass

    @abstractmethod
    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取数据的核心方法"""
        pass

    async def extract_with_cache(self, page: Page, **kwargs) -> Dict[str, Any]:
        """带缓存的提取方法"""
        if self._cached_results is None:
            self._cached_results = await self.extract(page, **kwargs)
        return self._cached_results

    def clear_cache(self):
        """清除缓存"""
        self._cached_results = None

    async def _get_extraction_scope(self, page: Page) -> List:
        """获取提取范围内的元素"""
        elements = []

        # CSS选择器
        if self.config.selectors:
            for selector in self.config.selectors:
                try:
                    scope_elements = await page.query_selector_all(selector)
                    elements.extend(scope_elements)
                except Exception:
                    continue

        # XPath选择器
        if self.config.xpath_selectors:
            for xpath in self.config.xpath_selectors:
                try:
                    scope_elements = await page.query_selector_all(f"xpath={xpath}")
                    elements.extend(scope_elements)
                except Exception:
                    continue

        # 如果没有指定选择器，返回整个页面
        if not elements:
            return [page]

        return elements

    async def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text or not self.config.clean_text:
            return text

        if self.config.normalize_whitespace:
            text = ContentUtils.normalize_whitespace(text)

        return text

    def _filter_and_deduplicate_items(
        self,
        items: List[Dict[str, Any]],
        base_url: str,
        url_key: str = "url",
        **filters,
    ) -> List[Dict[str, Any]]:
        """通用的过滤和去重逻辑"""
        processed = []
        seen_items: Set[str] = set()

        for item in items:
            try:
                # 获取唯一标识（URL或其他关键字段）
                unique_key = item.get(url_key, str(item))

                # 转换为绝对URL（如果是URL）
                if url_key in item and item[url_key]:
                    absolute_url = urljoin(base_url, item[url_key])
                    if URLUtils.is_valid_url(absolute_url):
                        item[url_key] = absolute_url
                        unique_key = absolute_url

                # 去重
                if self.config.deduplicate and unique_key in seen_items:
                    continue
                seen_items.add(unique_key)

                # 应用自定义过滤器
                if not self._apply_custom_filters(item, **filters):
                    continue

                processed.append(item)

                # 限制数量
                if self.config.max_items and len(processed) >= self.config.max_items:
                    break

            except Exception:
                continue

        return processed

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器，子类可以重写此方法"""
        return True

    async def _extract_metadata(self, page: Page) -> Dict[str, Any]:
        """提取页面元数据"""
        try:
            metadata = await page.evaluate(
                """
                () => {
                    const meta = {};
                    
                    meta.title = document.title || '';
                    
                    const description = document.querySelector('meta[name="description"]');
                    meta.description = description ? description.content : '';
                    
                    const keywords = document.querySelector('meta[name="keywords"]');
                    meta.keywords = keywords ? keywords.content.split(',').map(k => k.trim()) : [];
                    
                    const author = document.querySelector('meta[name="author"]');
                    meta.author = author ? author.content : '';
                    
                    const charset = document.charset || document.characterSet;
                    meta.charset = charset || '';
                    
                    const viewport = document.querySelector('meta[name="viewport"]');
                    meta.viewport = viewport ? viewport.content : '';
                    
                    meta.language = document.documentElement.lang || '';
                    
                    return meta;
                }
            """
            )
            return metadata or {}
        except Exception:
            return {}

    def is_enabled(self) -> bool:
        """检查提取器是否启用"""
        return self.config.enabled

    @property
    def extractor_type(self) -> str:
        """提取器类型标识"""
        return self.__class__.__name__.replace("Extractor", "").lower()

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
