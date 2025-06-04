"""
Xpidy - 配置驱动的智能网页数据提取框架
"""

from .core.config import ExtractionConfig, LLMConfig, SpiderConfig, XpidyConfig
from .core.spider import Spider

__version__ = "0.2.0"
__author__ = "Xpidy Team"
__description__ = "配置驱动的智能网页数据提取框架"

__all__ = [
    # 核心类
    "Spider",
    # 配置类
    "XpidyConfig",
    "SpiderConfig",
    "ExtractionConfig",
    "LLMConfig",
    # 版本信息
    "__version__",
    "__author__",
    "__description__",
]
