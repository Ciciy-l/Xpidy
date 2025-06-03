"""
核心模块
"""

from .config import (BrowserType, ExtractionConfig, LLMConfig, LLMProvider,
                     SpiderConfig)
from .llm_processor import LLMProcessor
from .results import (CrawlResult, FormStats, ImageStats, LinkStats,
                      PageMetadata, TableStats, create_error_result,
                      create_success_result)
from .spider import Spider

__all__ = [
    "Spider",
    "LLMProcessor",
    "SpiderConfig",
    "LLMConfig",
    "ExtractionConfig",
    "BrowserType",
    "LLMProvider",
    "CrawlResult",
    "PageMetadata",
    "LinkStats",
    "ImageStats",
    "TableStats",
    "FormStats",
    "create_error_result",
    "create_success_result",
]
