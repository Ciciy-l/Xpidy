"""
Xpidy 核心爬虫类
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from ..extractors import (
    ImageExtractor,
    ImageExtractorConfig,
    LinkExtractor,
    LinkExtractorConfig,
    TextExtractor,
    TextExtractorConfig,
)
from .config import ExtractionConfig, LLMConfig, SpiderConfig, XpidyConfig


class Spider:
    """核心爬虫类"""

    def __init__(self, config: XpidyConfig):
        self.config = config
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._extractors: Dict[str, Any] = {}
        self._extraction_results: Dict[str, Any] = {}
        self._llm_processor = None

        # 初始化提取器
        self._init_extractors()

        # 初始化LLM处理器
        if self.config.llm_config.enabled:
            self._init_llm_processor()

    def _init_extractors(self):
        """初始化提取器"""
        extraction_config = self.config.extraction_config

        # 文本提取器
        if extraction_config.enable_text:
            text_config = self._merge_extractor_config(
                TextExtractorConfig(), extraction_config.text_config
            )
            self._extractors["text"] = TextExtractor(text_config, self._llm_processor)

        # 链接提取器
        if extraction_config.enable_links:
            links_config = self._merge_extractor_config(
                LinkExtractorConfig(), extraction_config.links_config
            )
            self._extractors["links"] = LinkExtractor(links_config)

        # 图片提取器
        if extraction_config.enable_images:
            images_config = self._merge_extractor_config(
                ImageExtractorConfig(), extraction_config.images_config
            )
            self._extractors["images"] = ImageExtractor(images_config)

        # 数据提取器（新增）
        if extraction_config.enable_data:
            from ..extractors.data_extractor import DataExtractor, DataExtractorConfig

            data_config = self._merge_extractor_config(
                DataExtractorConfig(), extraction_config.data_config
            )
            self._extractors["data"] = DataExtractor(data_config)

        # 表单提取器（新增）
        if extraction_config.enable_form:
            from ..extractors.form_extractor import FormExtractor, FormExtractorConfig

            form_config = self._merge_extractor_config(
                FormExtractorConfig(), extraction_config.form_config
            )
            self._extractors["form"] = FormExtractor(form_config)

    def _merge_extractor_config(self, base_config, user_config: Dict[str, Any]):
        """合并提取器配置"""
        if not user_config:
            return base_config

        # 应用全局选择器
        global_selectors = self.config.extraction_config.global_selectors
        global_xpath_selectors = self.config.extraction_config.global_xpath_selectors
        global_exclude_selectors = (
            self.config.extraction_config.global_exclude_selectors
        )

        if global_selectors:
            user_config.setdefault("selectors", []).extend(global_selectors)
        if global_xpath_selectors:
            user_config.setdefault("xpath_selectors", []).extend(global_xpath_selectors)
        if global_exclude_selectors:
            user_config.setdefault("exclude_selectors", []).extend(
                global_exclude_selectors
            )

        # 更新配置
        config_dict = base_config.model_dump()
        config_dict.update(user_config)
        return base_config.__class__(**config_dict)

    def _init_llm_processor(self):
        """初始化LLM处理器"""
        # 暂时禁用LLM功能
        logger.info("LLM功能暂时禁用")
        self._llm_processor = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._start_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self._close_browser()

    async def _start_browser(self):
        """启动浏览器"""
        try:
            # 启动playwright
            self.playwright = await async_playwright().start()

            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.spider_config.headless
            )

            # 创建上下文
            context_options = {
                "viewport": self.config.spider_config.viewport,
                "user_agent": self.config.spider_config.user_agent,
            }

            # 过滤None值
            context_options = {
                k: v for k, v in context_options.items() if v is not None
            }

            self.context = await self.browser.new_context(**context_options)

            # 配置超时
            self.context.set_default_timeout(self.config.spider_config.timeout)

            logger.info("浏览器启动成功")

        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise

    async def _close_browser(self):
        """关闭浏览器"""
        try:
            # 按正确顺序关闭：页面 -> 上下文 -> 浏览器 -> playwright
            if self.context:
                # 关闭所有页面
                for page in self.context.pages:
                    try:
                        await page.close()
                    except Exception:
                        pass

                # 关闭上下文
                await self.context.close()
                self.context = None
                logger.debug("浏览器上下文已关闭")

            if self.browser:
                await self.browser.close()
                self.browser = None
                logger.debug("浏览器已关闭")

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                logger.debug("Playwright已停止")

            logger.info("浏览器资源已完全清理")

        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")

    async def crawl(self, url: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        爬取单个URL

        Args:
            url: 目标URL
            prompt: 可选的LLM后处理提示

        Returns:
            爬取结果字典
        """
        if not self.context:
            raise RuntimeError(
                "Spider未初始化，请使用 async with Spider(...) as spider:"
            )

        logger.info(f"开始爬取: {url}")
        start_time = time.time()

        # 创建页面
        page = await self.context.new_page()

        try:
            # 访问页面
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            # 并发执行所有提取器
            extraction_tasks = []
            for name, extractor in self._extractors.items():
                task = asyncio.create_task(
                    self._safe_extract(name, extractor, page), name=f"extract_{name}"
                )
                extraction_tasks.append(task)

            # 等待所有提取任务完成
            if extraction_tasks:
                extraction_results = await asyncio.gather(
                    *extraction_tasks, return_exceptions=True
                )

                # 处理提取结果
                for i, (name, result) in enumerate(
                    zip(self._extractors.keys(), extraction_results)
                ):
                    if isinstance(result, Exception):
                        logger.error(f"提取器 {name} 执行失败: {result}")
                        self._extraction_results[name] = {"error": str(result)}
                    else:
                        self._extraction_results[name] = result
                        logger.info(
                            f"提取器 {name} 完成，提取到 {self._get_result_count(result)} 项"
                        )

            # 构建最终结果
            final_result = {
                "url": url,
                "timestamp": time.time(),
                "extraction_time": time.time() - start_time,
                "extractors_used": list(self._extractors.keys()),
                "results": self._extraction_results.copy(),
            }

            # LLM后处理
            if prompt and self._llm_processor:
                try:
                    processed_result = await self._llm_post_process(
                        final_result, prompt
                    )
                    final_result["llm_processed"] = processed_result
                    final_result["llm_prompt"] = prompt
                except Exception as e:
                    logger.error(f"LLM后处理失败: {e}")
                    final_result["llm_error"] = str(e)

            logger.info(
                f"爬取完成: {url}, 耗时: {final_result['extraction_time']:.2f}秒"
            )
            return final_result

        except Exception as e:
            logger.error(f"爬取失败: {url}, 错误: {e}")
            return {
                "url": url,
                "timestamp": time.time(),
                "error": str(e),
                "extraction_time": time.time() - start_time,
            }
        finally:
            await page.close()

    async def crawl_multiple_urls(
        self,
        urls: List[str],
        prompts: Optional[List[str]] = None,
        max_concurrent: int = 3,
        delay_between_batches: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        并发爬取多个URL（基于Playwright上下文分隔）

        Args:
            urls: URL列表
            prompts: 可选的LLM提示列表，与urls对应
            max_concurrent: 最大并发数，默认3
            delay_between_batches: 批次间延迟，默认1秒

        Returns:
            爬取结果列表
        """
        if not self.browser:
            raise RuntimeError(
                "Spider未初始化，请使用 async with Spider(...) as spider:"
            )

        if prompts and len(prompts) != len(urls):
            raise ValueError("prompts数量必须与urls数量相等或为None")

        logger.info(f"开始并发爬取 {len(urls)} 个URL，最大并发数: {max_concurrent}")

        # 分批处理URLs
        results = []
        total_start_time = time.time()

        for batch_start in range(0, len(urls), max_concurrent):
            batch_end = min(batch_start + max_concurrent, len(urls))
            batch_urls = urls[batch_start:batch_end]
            batch_prompts = (
                prompts[batch_start:batch_end] if prompts else [None] * len(batch_urls)
            )

            logger.info(
                f"处理批次 {batch_start//max_concurrent + 1}: URLs {batch_start+1}-{batch_end}"
            )

            # 为当前批次创建并发任务
            batch_tasks = []
            for i, (url, prompt) in enumerate(zip(batch_urls, batch_prompts)):
                task = asyncio.create_task(
                    self._crawl_with_context(url, prompt, batch_start + i + 1),
                    name=f"crawl_batch_{batch_start//max_concurrent + 1}_url_{i+1}",
                )
                batch_tasks.append(task)

            # 并发执行当前批次
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 处理批次结果
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"URL {batch_start + i + 1} 爬取异常: {result}")
                    results.append(
                        {
                            "url": batch_urls[i],
                            "timestamp": time.time(),
                            "error": str(result),
                            "extraction_time": 0,
                            "batch_index": batch_start + i + 1,
                        }
                    )
                else:
                    result["batch_index"] = batch_start + i + 1
                    results.append(result)

            # 批次间延迟（避免过于频繁的请求）
            if batch_end < len(urls):
                logger.debug(f"批次间延迟 {delay_between_batches} 秒")
                await asyncio.sleep(delay_between_batches)

        total_time = time.time() - total_start_time
        success_count = len([r for r in results if "error" not in r])

        logger.info(
            f"并发爬取完成: {success_count}/{len(urls)} 成功, "
            f"总耗时: {total_time:.2f}秒, "
            f"平均耗时: {total_time/len(urls):.2f}秒/URL"
        )

        return results

    async def _crawl_with_context(
        self, url: str, prompt: Optional[str], index: int
    ) -> Dict[str, Any]:
        """
        使用独立上下文爬取单个URL

        Args:
            url: 目标URL
            prompt: LLM提示
            index: URL索引（用于日志）

        Returns:
            爬取结果
        """
        # 创建独立的浏览器上下文
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self.config.spider_config.user_agent,
            ignore_https_errors=True,
            java_script_enabled=True,
        )

        logger.info(f"[{index}] 开始爬取: {url}")
        start_time = time.time()

        try:
            # 创建页面
            page = await context.new_page()

            try:
                # 访问页面
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.config.spider_config.timeout,
                )
                await page.wait_for_load_state("networkidle")

                # 应用延迟
                if self.config.spider_config.delay > 0:
                    await asyncio.sleep(self.config.spider_config.delay)

                # 并发执行所有提取器
                extraction_results = {}
                extraction_tasks = []

                for name, extractor in self._extractors.items():
                    task = asyncio.create_task(
                        self._safe_extract_for_context(name, extractor, page),
                        name=f"extract_{name}_url_{index}",
                    )
                    extraction_tasks.append((name, task))

                # 等待所有提取任务完成
                if extraction_tasks:
                    completed_tasks = await asyncio.gather(
                        *[task for _, task in extraction_tasks], return_exceptions=True
                    )

                    # 处理提取结果
                    for (name, _), result in zip(extraction_tasks, completed_tasks):
                        if isinstance(result, Exception):
                            logger.error(f"[{index}] 提取器 {name} 执行失败: {result}")
                            extraction_results[name] = {"error": str(result)}
                        else:
                            extraction_results[name] = result
                            count = self._get_result_count(result)
                            logger.info(
                                f"[{index}] 提取器 {name} 完成，提取到 {count} 项"
                            )

                # 构建最终结果
                final_result = {
                    "url": url,
                    "timestamp": time.time(),
                    "extraction_time": time.time() - start_time,
                    "extractors_used": list(self._extractors.keys()),
                    "results": extraction_results,
                }

                # LLM后处理
                if prompt and self._llm_processor:
                    try:
                        processed_result = await self._llm_post_process(
                            final_result, prompt
                        )
                        final_result["llm_processed"] = processed_result
                        final_result["llm_prompt"] = prompt
                    except Exception as e:
                        logger.error(f"[{index}] LLM后处理失败: {e}")
                        final_result["llm_error"] = str(e)

                logger.info(
                    f"[{index}] 爬取完成: {url}, 耗时: {final_result['extraction_time']:.2f}秒"
                )
                return final_result

            finally:
                await page.close()

        except Exception as e:
            logger.error(f"[{index}] 爬取失败: {url}, 错误: {e}")
            return {
                "url": url,
                "timestamp": time.time(),
                "error": str(e),
                "extraction_time": time.time() - start_time,
            }
        finally:
            await context.close()

    async def _safe_extract_for_context(
        self, name: str, extractor: Any, page: Page
    ) -> Dict[str, Any]:
        """为上下文爬取安全执行提取器"""
        try:
            return await extractor.extract(page)
        except Exception as e:
            logger.error(f"提取器 {name} 执行异常: {e}")
            raise

    async def _safe_extract(
        self, name: str, extractor: Any, page: Page
    ) -> Dict[str, Any]:
        """安全执行提取器"""
        try:
            return await extractor.extract(page)
        except Exception as e:
            logger.error(f"提取器 {name} 执行异常: {e}")
            raise

    def _get_result_count(self, result: Dict[str, Any]) -> int:
        """获取提取结果数量"""
        if isinstance(result, dict):
            # 尝试常见的计数字段
            for count_field in ["total_links", "total_images", "content_length"]:
                if count_field in result:
                    return result[count_field]

            # 尝试查找列表字段
            for key, value in result.items():
                if isinstance(value, list):
                    return len(value)

        return 1

    async def _llm_post_process(self, result: Dict[str, Any], prompt: str) -> Any:
        """LLM后处理"""
        if not self._llm_processor:
            return None

        # 准备输入数据
        input_data = self._prepare_llm_input(result)

        # 调用LLM处理
        processed = await self._llm_processor.process(
            content=input_data, custom_prompt=prompt
        )

        return processed

    def _prepare_llm_input(self, result: Dict[str, Any]) -> str:
        """准备LLM输入数据"""
        input_parts = []

        # 添加基本信息
        input_parts.append(f"URL: {result.get('url', '')}")

        # 添加各提取器结果
        for extractor_name, extractor_result in result.get("results", {}).items():
            if isinstance(extractor_result, dict) and "error" not in extractor_result:
                input_parts.append(f"\n=== {extractor_name.upper()} 提取结果 ===")

                if extractor_name == "text":
                    content = extractor_result.get("content", "")
                    if content:
                        input_parts.append(f"文本内容: {content[:1000]}...")  # 限制长度

                elif extractor_name == "links":
                    links = extractor_result.get("links", [])
                    if links:
                        input_parts.append(f"链接数量: {len(links)}")
                        for i, link in enumerate(links[:5]):  # 只显示前5个
                            input_parts.append(
                                f"  {i+1}. {link.get('text', '')} -> {link.get('url', '')}"
                            )

                elif extractor_name == "images":
                    images = extractor_result.get("images", [])
                    if images:
                        input_parts.append(f"图片数量: {len(images)}")
                        for i, image in enumerate(images[:5]):  # 只显示前5个
                            input_parts.append(
                                f"  {i+1}. {image.get('alt', '')} -> {image.get('src', '')}"
                            )

        return "\n".join(input_parts)

    def get_extractor_count(self) -> int:
        """获取启用的提取器数量"""
        return len(self._extractors)

    def get_extraction_results(self) -> Dict[str, Any]:
        """获取最后一次提取的结果"""
        return self._extraction_results.copy()

    def clear_extraction_cache(self):
        """清除提取器缓存"""
        for extractor in self._extractors.values():
            if hasattr(extractor, "clear_cache"):
                extractor.clear_cache()
        logger.info("提取器缓存已清除")

    @classmethod
    def from_config_file(cls, config_path: str) -> "Spider":
        """从配置文件创建Spider实例"""
        config = XpidyConfig.load_from_file(config_path)
        return cls(config)

    @classmethod
    def quick_create(
        cls,
        enable_text: bool = True,
        enable_links: bool = False,
        enable_images: bool = False,
        enable_llm: bool = False,
        **kwargs,
    ) -> "Spider":
        """快速创建Spider实例"""
        config = XpidyConfig(
            extraction_config=ExtractionConfig(
                enable_text=enable_text,
                enable_links=enable_links,
                enable_images=enable_images,
            ),
            llm_config=LLMConfig(enabled=enable_llm, **kwargs.get("llm_config", {})),
            spider_config=SpiderConfig(**kwargs.get("spider_config", {})),
        )
        return cls(config)
