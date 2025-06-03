"""
Xpidy - 智能爬虫框架

基于 Playwright 的智能网页数据提取框架，支持多种提取器和 LLM 增强功能。
"""

from .core import (CrawlResult, ExtractionConfig, FormStats, ImageStats,
                   LinkStats, LLMConfig, PageMetadata, Spider, SpiderConfig,
                   TableStats, create_error_result, create_success_result)
from .core.spider import quick_crawl, quick_crawl_batch

__version__ = "0.2.0"
__all__ = [
    # 主要类
    "Spider",
    "SpiderConfig",
    "LLMConfig",
    "ExtractionConfig",
    # 结果类
    "CrawlResult",
    "PageMetadata",
    "LinkStats",
    "ImageStats",
    "TableStats",
    "FormStats",
    # 工厂函数
    "create_error_result",
    "create_success_result",
    # 便捷函数
    "quick_crawl",
    "quick_crawl_batch",
]
