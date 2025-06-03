"""
核心爬虫类
"""

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, Union

from loguru import logger
from playwright.async_api import (Browser, BrowserContext, Page, Playwright,
                                  async_playwright)

from ..extractors.data_extractor import DataExtractor
from ..extractors.image_extractor import ImageExtractor
from ..extractors.link_extractor import LinkExtractor
from ..extractors.text_extractor import TextExtractor
from .config import ExtractionConfig, LLMConfig, SpiderConfig
from .llm_processor import LLMProcessor
from .results import (CrawlResult, FormStats, ImageStats, LinkStats,
                      PageMetadata, TableStats, create_error_result)


class Spider:
    """智能爬虫 - 配置驱动的数据提取"""

    def __init__(
        self,
        extraction_config: Optional[ExtractionConfig] = None,
        spider_config: Optional[SpiderConfig] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        # 配置管理（提取配置放在第一位，体现其重要性）
        self.extraction_config = extraction_config or ExtractionConfig()
        self.spider_config = spider_config or SpiderConfig()
        self.llm_config = llm_config

        # 初始化组件
        self.llm_processor = None
        if self.llm_config:
            self.llm_processor = LLMProcessor(self.llm_config)

        self.text_extractor = TextExtractor(self.extraction_config, self.llm_processor)
        self.data_extractor = DataExtractor(self.extraction_config, self.llm_processor)
        self.link_extractor = LinkExtractor(self.extraction_config)
        self.image_extractor = ImageExtractor(self.extraction_config)

        # 内部状态
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._session_active = False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def start(self) -> None:
        """启动爬虫"""
        if self._session_active:
            return

        try:
            self._playwright = await async_playwright().start()

            # 选择浏览器
            if self.spider_config.browser_type == "chromium":
                browser_launcher = self._playwright.chromium
            elif self.spider_config.browser_type == "firefox":
                browser_launcher = self._playwright.firefox
            else:
                browser_launcher = self._playwright.webkit

            # 启动浏览器
            launch_options = {
                "headless": self.spider_config.headless,
            }

            self._browser = await browser_launcher.launch(**launch_options)

            # 创建上下文
            context_options = {}

            if self.spider_config.viewport:
                context_options["viewport"] = self.spider_config.viewport

            if self.spider_config.user_agent:
                context_options["user_agent"] = self.spider_config.user_agent

            self._context = await self._browser.new_context(**context_options)

            # 设置默认超时
            self._context.set_default_timeout(self.spider_config.timeout)

            self._session_active = True
            logger.info("爬虫启动成功")

        except Exception as e:
            logger.error(f"爬虫启动失败: {e}")
            await self.close()
            raise

    async def close(self) -> None:
        """关闭爬虫"""
        if not self._session_active:
            return

        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()

            self._context = None
            self._browser = None
            self._playwright = None
            self._session_active = False

            logger.info("爬虫关闭成功")

        except Exception as e:
            logger.error(f"爬虫关闭失败: {e}")

    async def crawl(self, url: str, **kwargs) -> CrawlResult:
        """
        核心爬取方法 - 根据配置自动提取数据

        Args:
            url: 目标URL
            **kwargs: 额外参数，会传递给提取器

        Returns:
            CrawlResult: 爬取结果
        """
        if not self._session_active:
            await self.start()

        if not self._context:
            raise RuntimeError("爬虫未正确初始化")

        page = None
        try:
            # 创建新页面
            page = await self._context.new_page()

            # 应用反爬虫策略
            if self.spider_config.stealth_mode:
                await self._apply_stealth_mode(page)

            # 随机延迟
            if self.spider_config.random_delay:
                delay = random.uniform(
                    self.spider_config.min_delay, self.spider_config.max_delay
                )
                await asyncio.sleep(delay)

            # 访问页面
            await self._navigate_with_retry(page, url)

            # 等待页面加载
            await page.wait_for_load_state(self.spider_config.wait_for_load_state)

            # 根据配置自动提取数据
            result = await self._extract_data(page, url, **kwargs)

            logger.info(f"爬取完成: {url} (提取器: {self._get_enabled_extractors()})")
            return result

        except Exception as e:
            logger.error(f"爬取失败 {url}: {e}")
            raise
        finally:
            if page:
                await page.close()

    async def crawl_batch(
        self, urls: List[str], max_concurrent: int = 3, **kwargs
    ) -> List[CrawlResult]:
        """
        批量爬取URLs

        Args:
            urls: URL列表
            max_concurrent: 最大并发数
            **kwargs: 传递给crawl方法的参数

        Returns:
            List[CrawlResult]: 所有URL的爬取结果
        """
        if not self._session_active:
            await self.start()

        semaphore = asyncio.Semaphore(max_concurrent)

        async def crawl_single(url: str) -> CrawlResult:
            async with semaphore:
                try:
                    return await self.crawl(url, **kwargs)
                except Exception as e:
                    logger.error(f"批量爬取失败 {url}: {e}")
                    return create_error_result(url, str(e))

        logger.info(f"开始批量爬取 {len(urls)} 个URL")
        results = await asyncio.gather(*[crawl_single(url) for url in urls])

        success_count = len([r for r in results if not r.error])
        logger.info(f"批量爬取完成: {success_count}/{len(urls)} 成功")

        return results

    async def extract_with_selectors(
        self, url: str, selectors: Dict[str, str], **kwargs
    ) -> CrawlResult:
        """
        使用CSS选择器提取数据

        Args:
            url: 目标URL
            selectors: CSS选择器字典 {"name": "selector"}
            **kwargs: 额外参数

        Returns:
            CrawlResult: 提取结果
        """
        if not self._session_active:
            await self.start()

        if not self._context:
            raise RuntimeError("爬虫未正确初始化")

        page = None
        try:
            page = await self._context.new_page()

            if self.spider_config.stealth_mode:
                await self._apply_stealth_mode(page)

            await self._navigate_with_retry(page, url)
            await page.wait_for_load_state(self.spider_config.wait_for_load_state)

            # 调用text_extractor获取字典结果
            selector_result = await self.text_extractor.extract_with_selectors(
                page, selectors, **kwargs
            )

            # 转换为CrawlResult对象
            result = CrawlResult(
                url=url,
                timestamp=selector_result.get("timestamp", __import__("time").time()),
                success=True,
            )

            # 设置提取的数据（选择器结果作为结构化数据）
            result.structured_data = {
                k: v
                for k, v in selector_result.items()
                if k
                not in [
                    "url",
                    "timestamp",
                    "extraction_method",
                    "llm_processed",
                    "llm_error",
                ]
            }
            result.structured_success = True

            # 如果有LLM处理结果
            if "llm_processed" in selector_result:
                result.content = selector_result["llm_processed"]
                result.text_success = True

            return result

        except Exception as e:
            logger.error(f"选择器提取失败 {url}: {e}")
            raise
        finally:
            if page:
                await page.close()

    async def extract_with_xpath(
        self, url: str, xpaths: Dict[str, str], **kwargs
    ) -> CrawlResult:
        """
        使用XPath选择器提取数据

        Args:
            url: 目标URL
            xpaths: XPath选择器字典 {"name": "xpath"}
            **kwargs: 额外参数

        Returns:
            CrawlResult: 提取结果
        """
        if not self._session_active:
            await self.start()

        if not self._context:
            raise RuntimeError("爬虫未正确初始化")

        page = None
        try:
            page = await self._context.new_page()

            if self.spider_config.stealth_mode:
                await self._apply_stealth_mode(page)

            await self._navigate_with_retry(page, url)
            await page.wait_for_load_state(self.spider_config.wait_for_load_state)

            result = await self._extract_with_xpath_impl(page, xpaths, **kwargs)

            return result

        except Exception as e:
            logger.error(f"XPath提取失败 {url}: {e}")
            raise
        finally:
            if page:
                await page.close()

    async def extract_with_schema(
        self, url: str, schema: Dict[str, Any], custom_prompt: Optional[str] = None
    ) -> CrawlResult:
        """
        使用JSON模式提取结构化数据（需要LLM支持）

        Args:
            url: 目标URL
            schema: JSON模式定义
            custom_prompt: 自定义提示词

        Returns:
            CrawlResult: 结构化提取结果
        """
        if not self.llm_processor:
            raise ValueError("需要配置LLM处理器才能使用模式提取")

        if not self._session_active:
            await self.start()

        if not self._context:
            raise RuntimeError("爬虫未正确初始化")

        page = None
        try:
            page = await self._context.new_page()

            if self.spider_config.stealth_mode:
                await self._apply_stealth_mode(page)

            await self._navigate_with_retry(page, url)
            await page.wait_for_load_state(self.spider_config.wait_for_load_state)

            # 调用data_extractor获取字典结果
            schema_result = await self.data_extractor.extract_with_schema(
                page, schema, custom_prompt
            )

            # 转换为CrawlResult对象
            result = CrawlResult(
                url=url,
                timestamp=schema_result.get("timestamp", __import__("time").time()),
                success=True,
            )

            # 设置结构化数据
            result.structured_data = schema_result.get("structured_data", {})
            result.structured_success = True

            # 设置原始内容
            if "raw_content" in schema_result:
                result.content = schema_result["raw_content"]
                result.text_success = True

            return result

        except Exception as e:
            logger.error(f"模式提取失败 {url}: {e}")
            raise
        finally:
            if page:
                await page.close()

    # ==================== 内部方法 ====================

    async def _extract_data(self, page: Page, url: str, **kwargs) -> CrawlResult:
        """根据配置提取数据的核心方法"""
        result = CrawlResult(
            url=url,
            timestamp=__import__("time").time(),
            success=True,
            config_summary=self._get_config_summary(),
        )

        # 文本提取（通常是基础需求）
        if self.extraction_config.extract_text:
            try:
                text_result = await self.text_extractor.extract(page, **kwargs)
                # 正确设置文本内容和元数据
                result.content = text_result.get("content", "")

                # 设置元数据
                metadata_dict = text_result.get("metadata", {})
                if metadata_dict:
                    result.metadata = PageMetadata(
                        title=metadata_dict.get("title"),
                        description=metadata_dict.get("description"),
                        language=metadata_dict.get("language"),
                        keywords=metadata_dict.get("keywords", []),
                        author=metadata_dict.get("author"),
                        charset=metadata_dict.get("charset"),
                        viewport=metadata_dict.get("viewport"),
                    )

                result.text_success = True
            except Exception as e:
                logger.warning(f"文本提取失败: {e}")
                result.text_error = str(e)
                result.text_success = False

        # 链接提取
        if self.extraction_config.extract_links:
            try:
                link_kwargs = self._build_link_kwargs(kwargs)
                links_result = await self.link_extractor.extract(page, **link_kwargs)
                result.links = links_result.get("links", [])
                result.link_stats = LinkStats(
                    total_links=links_result.get("total_links", 0),
                    internal_links=links_result.get("internal_links", 0),
                    external_links=links_result.get("external_links", 0),
                )
                result.links_success = True
            except Exception as e:
                logger.warning(f"链接提取失败: {e}")
                result.links_error = str(e)
                result.links_success = False

        # 图片提取
        if self.extraction_config.extract_images:
            try:
                image_kwargs = self._build_image_kwargs(kwargs)
                images_result = await self.image_extractor.extract(page, **image_kwargs)
                result.images = images_result.get("images", [])
                result.image_stats = ImageStats(
                    total_images=images_result.get("total_images", 0),
                    by_format=images_result.get("by_format", {}),
                    avg_dimensions=images_result.get("avg_dimensions", {}),
                )
                result.images_success = True
            except Exception as e:
                logger.warning(f"图片提取失败: {e}")
                result.images_error = str(e)
                result.images_success = False

        # 结构化数据提取
        if self.extraction_config.extract_structured_data:
            try:
                structured_result = await self.data_extractor.extract(page, **kwargs)
                result.structured_data = structured_result.get("data", {})
                result.structured_success = True
            except Exception as e:
                logger.warning(f"结构化数据提取失败: {e}")
                result.structured_error = str(e)
                result.structured_success = False

        # 表格数据提取
        if self.extraction_config.extract_tables:
            try:
                tables_result = await self.data_extractor.extract_table_data(
                    page, **kwargs
                )
                result.tables = tables_result.get("tables", [])
                result.table_stats = TableStats(
                    total_tables=len(tables_result.get("tables", [])),
                )
                result.tables_success = True
            except Exception as e:
                logger.warning(f"表格提取失败: {e}")
                result.tables_error = str(e)
                result.tables_success = False

        # 表单数据提取
        if self.extraction_config.extract_forms:
            try:
                from ..extractors.form_extractor import FormExtractor

                form_extractor = FormExtractor(self.extraction_config)
                forms_result = await form_extractor.extract(page, **kwargs)
                result.forms = forms_result.get("forms", [])
                result.form_stats = FormStats(
                    total_forms=len(forms_result.get("forms", [])),
                    input_fields=len(forms_result.get("input_fields", [])),
                    buttons=len(forms_result.get("buttons", [])),
                )
                result.forms_success = True
            except Exception as e:
                logger.warning(f"表单提取失败: {e}")
                result.forms_error = str(e)
                result.forms_success = False

        return result

    def _build_link_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """构建链接提取参数"""
        return {
            "include_internal": self.extraction_config.extract_internal_links,
            "include_external": self.extraction_config.extract_external_links,
            "limit": self.extraction_config.max_links,
            "filters": self.extraction_config.link_filters,
            **kwargs,
        }

    def _build_image_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """构建图片提取参数"""
        return {
            "min_width": self.extraction_config.min_image_width,
            "min_height": self.extraction_config.min_image_height,
            "formats": self.extraction_config.image_formats,
            "limit": self.extraction_config.max_images,
            **kwargs,
        }

    async def _extract_with_xpath_impl(
        self, page: Page, xpaths: Dict[str, str], **kwargs
    ) -> CrawlResult:
        """XPath提取的内部实现"""
        try:
            current_url = page.url
            extracted_data = {}

            for name, xpath in xpaths.items():
                try:
                    elements = await page.query_selector_all(f"xpath={xpath}")

                    if not elements:
                        extracted_data[name] = None
                        continue

                    if len(elements) == 1:
                        element = elements[0]
                        text_content = await element.text_content()
                        inner_html = await element.inner_html()
                        attributes = await element.evaluate(
                            "el => Object.fromEntries(Array.from(el.attributes).map(attr => [attr.name, attr.value]))"
                        )

                        extracted_data[name] = {
                            "text": (text_content or "").strip(),
                            "html": inner_html or "",
                            "attributes": attributes or {},
                            "tag_name": await element.evaluate(
                                "el => el.tagName.toLowerCase()"
                            ),
                        }
                    else:
                        elements_data = []
                        for element in elements:
                            text_content = await element.text_content()
                            inner_html = await element.inner_html()
                            attributes = await element.evaluate(
                                "el => Object.fromEntries(Array.from(el.attributes).map(attr => [attr.name, attr.value]))"
                            )

                            elements_data.append(
                                {
                                    "text": (text_content or "").strip(),
                                    "html": inner_html or "",
                                    "attributes": attributes or {},
                                    "tag_name": await element.evaluate(
                                        "el => el.tagName.toLowerCase()"
                                    ),
                                }
                            )

                        extracted_data[name] = elements_data

                except Exception as e:
                    logger.warning(f"XPath提取失败 {name}: {xpath} - {e}")
                    extracted_data[name] = None

            metadata = await self.text_extractor._extract_metadata(page)

            # 创建CrawlResult对象
            xpath_result = CrawlResult(
                url=current_url, timestamp=__import__("time").time(), success=True
            )

            # 设置提取的数据（这是选择器特定的数据）
            xpath_result.structured_data = extracted_data
            xpath_result.structured_success = True

            # 设置元数据
            if metadata:
                xpath_result.metadata = PageMetadata(
                    title=metadata.get("title"),
                    description=metadata.get("description"),
                    language=metadata.get("language"),
                    keywords=metadata.get("keywords", []),
                    author=metadata.get("author"),
                    charset=metadata.get("charset"),
                    viewport=metadata.get("viewport"),
                )

            return xpath_result

        except Exception as e:
            logger.error(f"XPath数据提取失败: {e}")
            raise

    async def _navigate_with_retry(self, page: Page, url: str) -> None:
        """带重试的页面导航"""
        for attempt in range(self.spider_config.max_retries):
            try:
                await page.goto(url, timeout=self.spider_config.timeout)
                return
            except Exception as e:
                if attempt == self.spider_config.max_retries - 1:
                    raise

                logger.warning(
                    f"导航重试 {attempt + 1}/{self.spider_config.max_retries}: {e}"
                )
                await asyncio.sleep(self.spider_config.retry_delay * (attempt + 1))

    async def _apply_stealth_mode(self, page: Page) -> None:
        """应用隐身模式"""
        try:
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' }),
                    }),
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """
            )

        except Exception as e:
            logger.warning(f"隐身模式设置失败: {e}")

    def _get_config_summary(self) -> Dict[str, bool]:
        """获取配置摘要"""
        return {
            "extract_text": self.extraction_config.extract_text,
            "extract_links": self.extraction_config.extract_links,
            "extract_images": self.extraction_config.extract_images,
            "extract_metadata": self.extraction_config.extract_metadata,
            "extract_structured_data": self.extraction_config.extract_structured_data,
            "extract_tables": self.extraction_config.extract_tables,
            "extract_forms": self.extraction_config.extract_forms,
            "llm_processing": self.extraction_config.enable_llm_processing,
        }

    def _get_enabled_extractors(self) -> List[str]:
        """获取启用的提取器列表"""
        enabled = []
        config = self.extraction_config

        if config.extract_text:
            enabled.append("text")
        if config.extract_links:
            enabled.append("links")
        if config.extract_images:
            enabled.append("images")
        if config.extract_structured_data:
            enabled.append("structured")
        if config.extract_tables:
            enabled.append("tables")
        if config.extract_forms:
            enabled.append("forms")

        return enabled

    # ==================== 便捷属性 ====================

    @property
    def is_active(self) -> bool:
        """检查爬虫是否处于活动状态"""
        return self._session_active

    def add_custom_prompt(self, name: str, template: str) -> None:
        """添加自定义提示词"""
        if self.llm_processor:
            self.llm_processor.add_custom_prompt(name, template)
        else:
            logger.warning("未配置LLM处理器，无法添加自定义提示词")

    def get_available_prompts(self) -> List[str]:
        """获取可用的提示词列表"""
        if self.llm_processor:
            return self.llm_processor.get_available_prompts()
        else:
            return []


# ==================== 便捷函数 ====================


async def quick_crawl(
    url: str,
    extraction_config: Optional[ExtractionConfig] = None,
    spider_config: Optional[SpiderConfig] = None,
    llm_config: Optional[LLMConfig] = None,
    **kwargs,
) -> CrawlResult:
    """
    快速爬取单个URL

    Args:
        url: 目标URL
        extraction_config: 提取配置
        spider_config: 爬虫配置
        llm_config: LLM配置
        **kwargs: 额外参数

    Returns:
        CrawlResult: 爬取结果
    """
    async with Spider(
        extraction_config=extraction_config,
        spider_config=spider_config,
        llm_config=llm_config,
    ) as spider:
        return await spider.crawl(url, **kwargs)


async def quick_crawl_batch(
    urls: List[str],
    extraction_config: Optional[ExtractionConfig] = None,
    spider_config: Optional[SpiderConfig] = None,
    llm_config: Optional[LLMConfig] = None,
    max_concurrent: int = 3,
    **kwargs,
) -> List[CrawlResult]:
    """
    快速批量爬取URLs

    Args:
        urls: URL列表
        extraction_config: 提取配置
        spider_config: 爬虫配置
        llm_config: LLM配置
        max_concurrent: 最大并发数
        **kwargs: 额外参数

    Returns:
        List[CrawlResult]: 爬取结果列表
    """
    async with Spider(
        extraction_config=extraction_config,
        spider_config=spider_config,
        llm_config=llm_config,
    ) as spider:
        return await spider.crawl_batch(urls, max_concurrent, **kwargs)
