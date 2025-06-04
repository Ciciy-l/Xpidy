"""
文本内容提取器
"""

import time
from typing import Any, Dict, List, Optional, Union

from playwright.async_api import Page
from pydantic import Field

from .base_extractor import BaseExtractor, BaseExtractorConfig


class TextExtractorConfig(BaseExtractorConfig):
    """文本提取器配置"""

    # 内容选择器
    content_selectors: List[str] = Field(
        default_factory=list, description="内容选择器列表"
    )
    exclude_selectors: List[str] = Field(
        default_factory=list, description="排除的选择器列表"
    )

    # 清理配置
    remove_scripts: bool = Field(default=True, description="移除脚本标签")
    remove_styles: bool = Field(default=True, description="移除样式标签")
    remove_comments: bool = Field(default=True, description="移除HTML注释")
    preserve_html_structure: bool = Field(default=False, description="保留HTML结构")

    # 提取配置
    extract_metadata: bool = Field(default=True, description="提取页面元数据")
    min_text_length: int = Field(default=10, description="最小文本长度")
    include_hidden_text: bool = Field(default=False, description="包含隐藏文本")


class TextExtractor(BaseExtractor):
    """文本内容提取器"""

    def __init__(
        self, config: Optional[TextExtractorConfig] = None, llm_processor=None
    ):
        super().__init__(config)
        self.llm_processor = llm_processor

    @classmethod
    def get_default_config(cls) -> TextExtractorConfig:
        """获取默认配置"""
        return TextExtractorConfig()

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取文本内容"""
        current_url = page.url

        # 应用页面清理
        await self._clean_page(page)

        # 提取文本内容
        content = await self._extract_text_content(page)

        # 提取元数据
        metadata = {}
        if self.config.extract_metadata:
            metadata = await self._extract_metadata(page)

        result = {
            "url": current_url,
            "content": content,
            "metadata": metadata,
            "timestamp": time.time(),
            "extraction_method": "text_extractor",
            "content_length": len(content),
            "llm_processed": False,
        }

        # LLM处理（如果配置了）
        if self.llm_processor and content:
            try:
                processed_content = await self.llm_processor.process_content(content)
                if processed_content:
                    result["content"] = processed_content
                    result["llm_processed"] = True
            except Exception as e:
                result["llm_error"] = str(e)

        return result

    async def extract_with_selectors(
        self, page: Page, selectors: Dict[str, str], **kwargs
    ) -> Dict[str, Any]:
        """使用选择器提取特定文本"""
        current_url = page.url
        extracted_data = {}

        for name, selector in selectors.items():
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    if len(elements) == 1:
                        text = await elements[0].text_content()
                        extracted_data[name] = await self._clean_text(text or "")
                    else:
                        texts = []
                        for element in elements:
                            text = await element.text_content()
                            if text:
                                texts.append(await self._clean_text(text))
                        extracted_data[name] = texts
                else:
                    extracted_data[name] = ""
            except Exception as e:
                extracted_data[name] = ""

        # 基础结果
        result = {
            "url": current_url,
            "timestamp": time.time(),
            "extraction_method": "selector_based",
            "llm_processed": False,
            **extracted_data,
        }

        # LLM处理（如果需要）
        if self.llm_processor and kwargs.get("llm_prompt"):
            try:
                # 准备LLM输入
                content_for_llm = " ".join(str(v) for v in extracted_data.values() if v)

                if content_for_llm:
                    processed = await self.llm_processor.process(
                        content=content_for_llm, custom_prompt=kwargs.get("llm_prompt")
                    )
                    result["llm_processed"] = processed
                    result["llm_error"] = None
            except Exception as e:
                result["llm_error"] = str(e)

        return result

    async def _clean_page(self, page: Page):
        """清理页面内容"""
        if self.config.remove_scripts:
            await page.evaluate(
                "() => document.querySelectorAll('script').forEach(el => el.remove())"
            )

        if self.config.remove_styles:
            await page.evaluate(
                "() => document.querySelectorAll('style').forEach(el => el.remove())"
            )

        if self.config.remove_comments:
            await page.evaluate(
                """
                () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_COMMENT,
                        null,
                        false
                    );
                    const comments = [];
                    let node;
                    while (node = walker.nextNode()) {
                        comments.push(node);
                    }
                    comments.forEach(comment => comment.remove());
                }
            """
            )

        # 移除排除的元素
        for selector in self.config.exclude_selectors:
            try:
                await page.evaluate(
                    f"""
                    () => document.querySelectorAll('{selector}').forEach(el => el.remove())
                """
                )
            except Exception:
                continue

    async def _extract_text_content(self, page: Page) -> str:
        """提取文本内容"""
        content_parts = []

        # 使用指定的内容选择器
        if self.config.content_selectors:
            for selector in self.config.content_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        if text and len(text.strip()) >= self.config.min_text_length:
                            content_parts.append(await self._clean_text(text))
                except Exception:
                    continue
        else:
            # 提取整个body的文本
            try:
                if self.config.preserve_html_structure:
                    content = await page.inner_html("body")
                else:
                    content = await page.text_content("body")

                if content and len(content.strip()) >= self.config.min_text_length:
                    content_parts.append(await self._clean_text(content))
            except Exception:
                pass

        return "\n\n".join(content_parts)

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器"""
        # 文本长度过滤
        content = item.get("content", "")
        if len(content.strip()) < self.config.min_text_length:
            return False

        return True
