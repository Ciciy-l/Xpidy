"""
配置管理模块
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BrowserType(str, Enum):
    """浏览器类型"""

    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class LLMProvider(str, Enum):
    """LLM 提供商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    LOCAL = "local"


class SpiderConfig(BaseModel):
    """爬虫配置"""

    # 浏览器配置
    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    viewport: Optional[Dict[str, int]] = Field(default={"width": 1920, "height": 1080})
    user_agent: Optional[str] = None

    # 网络配置
    timeout: int = Field(default=30000, description="超时时间(毫秒)")
    wait_for_load_state: str = Field(
        default="domcontentloaded", description="等待加载状态"
    )

    # 请求配置
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试延迟(秒)")

    # 反爬虫配置
    stealth_mode: bool = Field(default=True, description="隐身模式")
    random_delay: bool = Field(default=True, description="随机延迟")
    min_delay: float = Field(default=0.5, description="最小延迟(秒)")
    max_delay: float = Field(default=2.0, description="最大延迟(秒)")


class LLMConfig(BaseModel):
    """LLM 配置"""

    provider: LLMProvider = LLMProvider.OPENAI
    model: str = Field(default="gpt-3.5-turbo", description="模型名称")
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    # 生成参数
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2000, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)

    # 提示词配置
    system_prompt: Optional[str] = None
    custom_prompts: Dict[str, str] = Field(default_factory=dict)

    # 处理配置
    batch_size: int = Field(default=5, gt=0, description="批处理大小")
    timeout: int = Field(default=60, description="请求超时(秒)")


class ExtractionConfig(BaseModel):
    """数据提取配置"""

    # 基础提取策略
    extract_text: bool = Field(default=True, description="提取文本")
    extract_links: bool = Field(default=False, description="提取链接")
    extract_images: bool = Field(default=False, description="提取图片")
    extract_metadata: bool = Field(default=True, description="提取元数据")
    extract_structured_data: bool = Field(default=False, description="提取结构化数据")
    extract_tables: bool = Field(default=False, description="提取表格数据")
    extract_forms: bool = Field(default=False, description="提取表单数据")

    # 选择器配置
    content_selectors: List[str] = Field(default_factory=list, description="内容选择器")
    exclude_selectors: List[str] = Field(default_factory=list, description="排除选择器")

    # 链接提取配置
    extract_internal_links: bool = Field(default=True, description="提取内部链接")
    extract_external_links: bool = Field(default=True, description="提取外部链接")
    link_filters: List[str] = Field(default_factory=list, description="链接过滤规则")
    max_links: Optional[int] = Field(default=None, description="最大链接数")

    # 图片提取配置
    min_image_width: int = Field(default=0, description="最小图片宽度")
    min_image_height: int = Field(default=0, description="最小图片高度")
    image_formats: List[str] = Field(
        default_factory=lambda: ["jpg", "jpeg", "png", "gif", "webp", "svg"],
        description="图片格式",
    )
    max_images: Optional[int] = Field(default=None, description="最大图片数")

    # 清理配置
    remove_scripts: bool = Field(default=True, description="移除脚本")
    remove_styles: bool = Field(default=True, description="移除样式")
    normalize_whitespace: bool = Field(default=True, description="标准化空白字符")

    # LLM 处理配置
    enable_llm_processing: bool = Field(default=False, description="启用LLM处理")
    llm_extraction_prompt: Optional[str] = None
    structured_output: bool = Field(default=False, description="结构化输出")
    output_schema: Optional[Dict[str, Any]] = None

    # 高级配置
    enable_deduplication: bool = Field(default=True, description="启用去重")
    preserve_html_structure: bool = Field(default=False, description="保留HTML结构")
    extract_css_info: bool = Field(default=False, description="提取CSS信息")
    extract_js_variables: bool = Field(default=False, description="提取JS变量")
