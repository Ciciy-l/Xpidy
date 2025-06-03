"""
Xpidy 核心模块
"""

from .config import SpiderConfig, ExtractionConfig, LLMConfig
from .spider import Spider
from .results import (
    CrawlResult, 
    FormStats, 
    ImageStats, 
    LinkStats, 
    TableStats, 
    PageMetadata,
    create_error_result,
    create_success_result
)
from .llm_processor import LLMProcessor, LLMStats, ContentProcessor

__all__ = [
    "SpiderConfig",
    "ExtractionConfig", 
    "LLMConfig",
    "Spider",
    "CrawlResult",
    "FormStats",
    "ImageStats", 
    "LinkStats",
    "TableStats",
    "PageMetadata",
    "create_error_result",
    "create_success_result",
    "LLMProcessor",
    "LLMStats", 
    "ContentProcessor",
]
