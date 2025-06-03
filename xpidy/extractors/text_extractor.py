"""
文本数据提取器
"""

from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page

from ..core.config import ExtractionConfig
from ..core.llm_processor import LLMProcessor
from .base_extractor import BaseExtractor


class TextExtractor(BaseExtractor):
    """文本数据提取器"""

    def __init__(
        self, config: ExtractionConfig, llm_processor: Optional[LLMProcessor] = None
    ):
        super().__init__(config)
        self.llm_processor = llm_processor

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取文本数据"""
        try:
            result = {}

            # 提取基本内容
            if self.config.extract_text:
                content = await self._get_page_content(page)
                result["content"] = content

                # 如果启用 LLM 处理
                if self.config.enable_llm_processing and self.llm_processor:
                    try:
                        # 获取自定义提示词参数
                        custom_prompt = kwargs.get("custom_prompt")
                        prompt_name = kwargs.get("prompt_name", "extract_text")
                        template_vars = kwargs.get("template_vars", {})

                        # 使用 LLM 处理内容
                        processed_content = await self.llm_processor.process(
                            content=content,
                            prompt_name=prompt_name,
                            custom_prompt=custom_prompt,
                            **template_vars,
                        )
                        result["processed_content"] = processed_content

                        logger.info("LLM 处理完成，已添加处理后的内容")

                    except Exception as e:
                        logger.warning(f"LLM 处理失败，跳过: {e}")
                        result["llm_error"] = str(e)

            # 提取其他数据
            if self.config.extract_links:
                result["links"] = await self._extract_links(page)

            if self.config.extract_images:
                result["images"] = await self._extract_images(page)

            if self.config.extract_metadata:
                result["metadata"] = await self._extract_metadata(page)

            # 添加页面信息
            result["url"] = page.url
            result["timestamp"] = __import__("time").time()

            logger.info(f"文本提取完成，URL: {page.url}")
            return result

        except Exception as e:
            logger.error(f"文本提取失败: {e}")
            raise

    async def extract_with_selectors(
        self, page: Page, selectors: Dict[str, str], **kwargs
    ) -> Dict[str, Any]:
        """使用指定选择器提取文本"""
        try:
            result = {}

            for name, selector in selectors.items():
                try:
                    elements = page.locator(selector)
                    count = await elements.count()

                    if count == 0:
                        result[name] = None
                    elif count == 1:
                        text = await elements.text_content()
                        result[name] = await self._clean_text(text or "")
                    else:
                        texts = []
                        for i in range(count):
                            element = elements.nth(i)
                            text = await element.text_content()
                            if text:
                                texts.append(await self._clean_text(text))
                        result[name] = texts

                except Exception as e:
                    logger.warning(f"选择器 {selector} 提取失败: {e}")
                    result[name] = None

            # 如果启用 LLM 处理
            if self.config.enable_llm_processing and self.llm_processor:
                try:
                    # 合并所有提取的文本
                    all_text = []
                    for key, value in result.items():
                        if isinstance(value, str) and value:
                            all_text.append(f"{key}: {value}")
                        elif isinstance(value, list):
                            all_text.extend([f"{key}: {v}" for v in value if v])

                    content = "\n".join(all_text)

                    if content:
                        # 获取自定义提示词参数
                        custom_prompt = kwargs.get("custom_prompt")
                        prompt_name = kwargs.get("prompt_name", "extract_data")
                        template_vars = kwargs.get("template_vars", {})

                        # 使用 LLM 处理内容
                        processed_content = await self.llm_processor.process(
                            content=content,
                            prompt_name=prompt_name,
                            custom_prompt=custom_prompt,
                            **template_vars,
                        )
                        result["llm_processed"] = processed_content

                except Exception as e:
                    logger.warning(f"LLM 处理失败: {e}")
                    result["llm_error"] = str(e)

            # 添加元信息
            result["url"] = page.url
            result["timestamp"] = __import__("time").time()
            result["extraction_method"] = "selectors"

            logger.info(f"选择器文本提取完成，URL: {page.url}")
            return result

        except Exception as e:
            logger.error(f"选择器文本提取失败: {e}")
            raise

    async def extract_article(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取文章内容（自动检测文章结构）"""
        try:
            # 常见的文章选择器
            article_selectors = [
                "article",
                "[role='main']",
                ".content",
                ".article-content",
                ".post-content",
                ".entry-content",
                "#content",
                "main",
            ]

            content = ""
            for selector in article_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.text_content()
                        if text and len(text) > len(content):
                            content = text
                except Exception:
                    continue

            if not content:
                # 如果没有找到文章容器，使用整个页面内容
                content = await self._get_page_content(page)

            content = await self._clean_text(content)

            result = {
                "content": content,
                "url": page.url,
                "timestamp": __import__("time").time(),
                "extraction_method": "article_detection",
            }

            # 提取标题
            try:
                title_selectors = [
                    "h1",
                    "title",
                    ".title",
                    ".article-title",
                    ".post-title",
                ]
                for selector in title_selectors:
                    title_element = page.locator(selector).first
                    if await title_element.count() > 0:
                        title = await title_element.text_content()
                        if title:
                            result["title"] = await self._clean_text(title)
                            break
            except Exception:
                pass

            # 如果启用 LLM 处理
            if self.config.enable_llm_processing and self.llm_processor and content:
                try:
                    custom_prompt = kwargs.get("custom_prompt")
                    prompt_name = kwargs.get("prompt_name", "extract_text")
                    template_vars = kwargs.get("template_vars", {})

                    processed_content = await self.llm_processor.process(
                        content=content,
                        prompt_name=prompt_name,
                        custom_prompt=custom_prompt,
                        **template_vars,
                    )
                    result["processed_content"] = processed_content

                except Exception as e:
                    logger.warning(f"LLM 处理失败: {e}")
                    result["llm_error"] = str(e)

            logger.info(f"文章提取完成，URL: {page.url}")
            return result

        except Exception as e:
            logger.error(f"文章提取失败: {e}")
            raise
