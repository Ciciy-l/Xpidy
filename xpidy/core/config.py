"""
Xpidy 核心配置类
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class SpiderConfig(BaseModel):
    """爬虫基础配置"""

    # 浏览器配置
    headless: bool = Field(default=True, description="是否无头模式")
    timeout: int = Field(default=30000, description="页面超时时间（毫秒）")
    user_agent: Optional[str] = Field(default=None, description="用户代理")
    viewport: Dict[str, int] = Field(
        default_factory=lambda: {"width": 1920, "height": 1080}, description="视口大小"
    )

    # 请求配置
    delay: float = Field(default=1.0, description="请求间隔（秒）")
    retry_times: int = Field(default=3, description="重试次数")
    retry_delay: float = Field(default=2.0, description="重试间隔（秒）")

    # 缓存配置
    enable_cache: bool = Field(default=True, description="启用缓存")
    cache_ttl: int = Field(default=3600, description="缓存TTL（秒）")

    # 安全配置
    enable_stealth: bool = Field(default=True, description="启用隐身模式")
    javascript_enabled: bool = Field(default=True, description="启用JavaScript")
    images_enabled: bool = Field(default=True, description="启用图片加载")


class ExtractionConfig(BaseModel):
    """提取配置"""

    # 提取器启用开关
    enable_text: bool = Field(default=False, description="启用文本提取器")
    enable_links: bool = Field(default=False, description="启用链接提取器")
    enable_images: bool = Field(default=False, description="启用图片提取器")
    enable_data: bool = Field(default=False, description="启用数据提取器")
    enable_form: bool = Field(default=False, description="启用表单提取器")

    # 通用选择器配置（适用于所有提取器）
    global_selectors: Optional[List[str]] = Field(
        default=None, description="全局CSS选择器"
    )
    global_xpath_selectors: Optional[List[str]] = Field(
        default=None, description="全局XPath选择器"
    )
    global_exclude_selectors: Optional[List[str]] = Field(
        default_factory=list, description="全局排除选择器"
    )

    # 提取器专用配置
    text_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="文本提取器配置"
    )
    links_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="链接提取器配置"
    )
    images_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="图片提取器配置"
    )
    data_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="数据提取器配置"
    )
    form_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="表单提取器配置"
    )


class LLMConfig(BaseModel):
    """LLM配置"""

    # 基础配置
    enabled: bool = Field(default=False, description="是否启用LLM")
    provider: str = Field(default="openai", description="LLM提供商")
    model: str = Field(default="gpt-3.5-turbo", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="API基础URL")

    # 生成参数
    temperature: float = Field(default=0.7, description="温度参数")
    max_tokens: Optional[int] = Field(default=None, description="最大token数")
    top_p: float = Field(default=1.0, description="top_p参数")

    # 缓存配置
    enable_cache: bool = Field(default=True, description="启用LLM缓存")
    cache_ttl: int = Field(default=86400, description="缓存TTL（秒）")

    # 批处理配置
    batch_size: int = Field(default=10, description="批处理大小")
    batch_delay: float = Field(default=1.0, description="批处理延迟（秒）")

    # 成本控制
    max_cost_per_request: float = Field(
        default=1.0, description="单次请求最大成本（美元）"
    )
    daily_cost_limit: float = Field(default=100.0, description="每日成本限制（美元）")

    # 重试配置
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试延迟（秒）")


class XpidyConfig(BaseModel):
    """Xpidy 主配置类"""

    spider_config: SpiderConfig = Field(
        default_factory=SpiderConfig, description="爬虫配置"
    )
    extraction_config: ExtractionConfig = Field(
        default_factory=ExtractionConfig, description="提取配置"
    )
    llm_config: LLMConfig = Field(default_factory=LLMConfig, description="LLM配置")

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "XpidyConfig":
        """从字典创建配置"""
        return cls(**config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()

    @classmethod
    def load_from_file(cls, file_path: str) -> "XpidyConfig":
        """从文件加载配置"""
        import json

        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)

    def save_to_file(self, file_path: str):
        """保存配置到文件"""
        import json

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
