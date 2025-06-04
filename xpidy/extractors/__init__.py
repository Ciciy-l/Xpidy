"""
数据提取器模块
"""

from .base_extractor import BaseExtractor, BaseExtractorConfig
from .data_extractor import DataExtractor, DataExtractorConfig
from .form_extractor import FormExtractor, FormExtractorConfig
from .image_extractor import ImageExtractor, ImageExtractorConfig
from .link_extractor import LinkExtractor, LinkExtractorConfig
from .text_extractor import TextExtractor, TextExtractorConfig

__all__ = [
    # 基础类
    "BaseExtractor",
    "BaseExtractorConfig",
    # 文本提取器
    "TextExtractor",
    "TextExtractorConfig",
    # 链接提取器
    "LinkExtractor",
    "LinkExtractorConfig",
    # 图片提取器
    "ImageExtractor",
    "ImageExtractorConfig",
    # 数据提取器
    "DataExtractor",
    "DataExtractorConfig",
    # 表单提取器
    "FormExtractor",
    "FormExtractorConfig",
]
