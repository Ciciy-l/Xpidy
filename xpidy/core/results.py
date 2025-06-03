"""
爬取结果类定义
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class LinkStats:
    """链接统计信息"""

    total_links: int = 0
    internal_links: int = 0
    external_links: int = 0


@dataclass
class ImageStats:
    """图片统计信息"""

    total_images: int = 0
    by_format: Dict[str, int] = field(default_factory=dict)
    avg_dimensions: Dict[str, float] = field(default_factory=dict)


@dataclass
class TableStats:
    """表格统计信息"""

    total_tables: int = 0


@dataclass
class FormStats:
    """表单统计信息"""

    total_forms: int = 0
    input_fields: int = 0
    buttons: int = 0


@dataclass
class PageMetadata:
    """页面元数据"""

    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    author: Optional[str] = None
    charset: Optional[str] = None
    viewport: Optional[str] = None


class CrawlResult:
    """
    爬取结果类 - 提供类型安全和IDE智能提示

    替代原来的字典返回值，提供更好的开发体验
    """

    def __init__(
        self,
        url: str,
        success: bool = True,
        timestamp: Optional[float] = None,
        config_summary: Optional[Dict[str, bool]] = None,
    ):
        # 基础信息
        self.url = url
        self.success = success
        self.timestamp = timestamp or time.time()
        self.config_summary = config_summary or {}

        # 文本提取结果
        self.content: Optional[str] = None
        self.metadata: PageMetadata = PageMetadata()
        self.text_success: bool = False
        self.text_error: Optional[str] = None

        # 链接提取结果
        self.links: List[Dict[str, Any]] = []
        self.link_stats: LinkStats = LinkStats()
        self.links_success: bool = False
        self.links_error: Optional[str] = None

        # 图片提取结果
        self.images: List[Dict[str, Any]] = []
        self.image_stats: ImageStats = ImageStats()
        self.images_success: bool = False
        self.images_error: Optional[str] = None

        # 结构化数据提取结果
        self.structured_data: Dict[str, Any] = {}
        self.structured_success: bool = False
        self.structured_error: Optional[str] = None

        # 表格提取结果
        self.tables: List[Dict[str, Any]] = []
        self.table_stats: TableStats = TableStats()
        self.tables_success: bool = False
        self.tables_error: Optional[str] = None

        # 表单提取结果
        self.forms: List[Dict[str, Any]] = []
        self.form_stats: FormStats = FormStats()
        self.forms_success: bool = False
        self.forms_error: Optional[str] = None

        # 通用错误信息
        self.error: Optional[str] = None

    # ==================== 便捷属性 ====================

    @property
    def has_content(self) -> bool:
        """是否有文本内容"""
        return self.text_success and bool(self.content)

    @property
    def has_links(self) -> bool:
        """是否有链接数据"""
        return self.links_success and len(self.links) > 0

    @property
    def has_images(self) -> bool:
        """是否有图片数据"""
        return self.images_success and len(self.images) > 0

    @property
    def has_tables(self) -> bool:
        """是否有表格数据"""
        return self.tables_success and len(self.tables) > 0

    @property
    def has_forms(self) -> bool:
        """是否有表单数据"""
        return self.forms_success and len(self.forms) > 0

    @property
    def has_structured_data(self) -> bool:
        """是否有结构化数据"""
        return self.structured_success and bool(self.structured_data)

    @property
    def word_count(self) -> int:
        """获取文字数量"""
        if not self.has_content:
            return 0
        # 简单的字数统计
        return len(self.content.split())

    @property
    def content_length(self) -> int:
        """获取内容长度"""
        return len(self.content) if self.content else 0

    @property
    def total_links(self) -> int:
        """获取总链接数"""
        return self.link_stats.total_links

    @property
    def total_images(self) -> int:
        """获取总图片数"""
        return self.image_stats.total_images

    @property
    def enabled_extractors(self) -> List[str]:
        """获取启用的提取器列表"""
        return [name for name, enabled in self.config_summary.items() if enabled]

    @property
    def successful_extractors(self) -> List[str]:
        """获取成功的提取器列表"""
        successful = []
        if self.text_success:
            successful.append("text")
        if self.links_success:
            successful.append("links")
        if self.images_success:
            successful.append("images")
        if self.structured_success:
            successful.append("structured")
        if self.tables_success:
            successful.append("tables")
        if self.forms_success:
            successful.append("forms")
        return successful

    @property
    def failed_extractors(self) -> List[str]:
        """获取失败的提取器列表"""
        failed = []
        if self.config_summary.get("extract_text") and not self.text_success:
            failed.append("text")
        if self.config_summary.get("extract_links") and not self.links_success:
            failed.append("links")
        if self.config_summary.get("extract_images") and not self.images_success:
            failed.append("images")
        if (
            self.config_summary.get("extract_structured_data")
            and not self.structured_success
        ):
            failed.append("structured")
        if self.config_summary.get("extract_tables") and not self.tables_success:
            failed.append("tables")
        if self.config_summary.get("extract_forms") and not self.forms_success:
            failed.append("forms")
        return failed

    # ==================== 数据访问方法 ====================

    def get_links_by_type(self, link_type: str) -> List[Dict[str, Any]]:
        """
        按类型获取链接

        Args:
            link_type: "internal" 或 "external"
        """
        if not self.has_links:
            return []

        return [link for link in self.links if link.get("type") == link_type]

    def get_internal_links(self) -> List[Dict[str, Any]]:
        """获取内部链接"""
        return self.get_links_by_type("internal")

    def get_external_links(self) -> List[Dict[str, Any]]:
        """获取外部链接"""
        return self.get_links_by_type("external")

    def get_images_by_format(self, format_name: str) -> List[Dict[str, Any]]:
        """
        按格式获取图片

        Args:
            format_name: 图片格式，如 "jpg", "png" 等
        """
        if not self.has_images:
            return []

        return [
            img
            for img in self.images
            if img.get("file_extension", "").lower() == format_name.lower()
        ]

    def get_large_images(
        self, min_width: int = 500, min_height: int = 300
    ) -> List[Dict[str, Any]]:
        """获取大尺寸图片"""
        if not self.has_images:
            return []

        return [
            img
            for img in self.images
            if img.get("width", 0) >= min_width and img.get("height", 0) >= min_height
        ]

    def get_navigation_links(self) -> List[Dict[str, Any]]:
        """获取导航链接"""
        if not self.has_links:
            return []

        return [link for link in self.links if link.get("inNavigation", False)]

    def get_content_links(self) -> List[Dict[str, Any]]:
        """获取内容区域的链接"""
        if not self.has_links:
            return []

        return [link for link in self.links if link.get("inMainContent", False)]

    # ==================== 统计方法 ====================

    def get_summary(self) -> Dict[str, Any]:
        """获取结果摘要"""
        return {
            "url": self.url,
            "success": self.success,
            "timestamp": self.timestamp,
            "enabled_extractors": self.enabled_extractors,
            "successful_extractors": self.successful_extractors,
            "failed_extractors": self.failed_extractors,
            "content_length": self.content_length,
            "word_count": self.word_count,
            "total_links": self.total_links,
            "total_images": self.total_images,
            "total_tables": len(self.tables),
            "total_forms": len(self.forms),
            "has_structured_data": self.has_structured_data,
        }

    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        stats = {
            "basic_info": {
                "url": self.url,
                "success": self.success,
                "timestamp": self.timestamp,
                "content_length": self.content_length,
                "word_count": self.word_count,
            },
            "extractors": {
                "enabled": self.enabled_extractors,
                "successful": self.successful_extractors,
                "failed": self.failed_extractors,
            },
        }

        if self.has_links:
            stats["links"] = {
                "total": self.total_links,
                "internal": self.link_stats.internal_links,
                "external": self.link_stats.external_links,
                "navigation": len(self.get_navigation_links()),
                "content": len(self.get_content_links()),
            }

        if self.has_images:
            stats["images"] = {
                "total": self.total_images,
                "by_format": dict(self.image_stats.by_format),
                "large_images": len(self.get_large_images()),
            }

        if self.has_tables:
            stats["tables"] = {"total": len(self.tables)}

        if self.has_forms:
            stats["forms"] = {
                "total": len(self.forms),
                "input_fields": self.form_stats.input_fields,
                "buttons": self.form_stats.buttons,
            }

        return stats

    # ==================== 转换方法 ====================

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（兼容性方法）"""
        result = {
            "url": self.url,
            "success": self.success,
            "timestamp": self.timestamp,
            "config_summary": self.config_summary,
            # 文本数据
            "text_success": self.text_success,
            "text_error": self.text_error,
            # 链接数据
            "links": self.links,
            "link_stats": {
                "total_links": self.link_stats.total_links,
                "internal_links": self.link_stats.internal_links,
                "external_links": self.link_stats.external_links,
            },
            "links_success": self.links_success,
            "links_error": self.links_error,
            # 图片数据
            "images": self.images,
            "image_stats": {
                "total_images": self.image_stats.total_images,
                "by_format": dict(self.image_stats.by_format),
                "avg_dimensions": dict(self.image_stats.avg_dimensions),
            },
            "images_success": self.images_success,
            "images_error": self.images_error,
            # 结构化数据
            "structured_data": self.structured_data,
            "structured_success": self.structured_success,
            "structured_error": self.structured_error,
            # 表格数据
            "tables": self.tables,
            "table_stats": {"total_tables": self.table_stats.total_tables},
            "tables_success": self.tables_success,
            "tables_error": self.tables_error,
            # 表单数据
            "forms": self.forms,
            "form_stats": {
                "total_forms": self.form_stats.total_forms,
                "input_fields": self.form_stats.input_fields,
                "buttons": self.form_stats.buttons,
            },
            "forms_success": self.forms_success,
            "forms_error": self.forms_error,
            # 通用错误
            "error": self.error,
        }

        # 添加文本内容和元数据
        if self.content is not None:
            result["content"] = self.content

        if self.metadata:
            result["metadata"] = {
                "title": self.metadata.title,
                "description": self.metadata.description,
                "language": self.metadata.language,
                "keywords": self.metadata.keywords,
                "author": self.metadata.author,
                "charset": self.metadata.charset,
                "viewport": self.metadata.viewport,
            }

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlResult":
        """从字典创建CrawlResult对象"""
        result = cls(
            url=data.get("url", ""),
            success=data.get("success", False),
            timestamp=data.get("timestamp"),
            config_summary=data.get("config_summary", {}),
        )

        # 文本数据
        result.content = data.get("content")
        result.text_success = data.get("text_success", False)
        result.text_error = data.get("text_error")

        # 元数据
        if "metadata" in data:
            metadata = data["metadata"]
            result.metadata = PageMetadata(
                title=metadata.get("title"),
                description=metadata.get("description"),
                language=metadata.get("language"),
                keywords=metadata.get("keywords", []),
                author=metadata.get("author"),
                charset=metadata.get("charset"),
                viewport=metadata.get("viewport"),
            )

        # 链接数据
        result.links = data.get("links", [])
        result.links_success = data.get("links_success", False)
        result.links_error = data.get("links_error")

        if "link_stats" in data:
            stats = data["link_stats"]
            result.link_stats = LinkStats(
                total_links=stats.get("total_links", 0),
                internal_links=stats.get("internal_links", 0),
                external_links=stats.get("external_links", 0),
            )

        # 图片数据
        result.images = data.get("images", [])
        result.images_success = data.get("images_success", False)
        result.images_error = data.get("images_error")

        if "image_stats" in data:
            stats = data["image_stats"]
            result.image_stats = ImageStats(
                total_images=stats.get("total_images", 0),
                by_format=stats.get("by_format", {}),
                avg_dimensions=stats.get("avg_dimensions", {}),
            )

        # 结构化数据
        result.structured_data = data.get("structured_data", {})
        result.structured_success = data.get("structured_success", False)
        result.structured_error = data.get("structured_error")

        # 表格数据
        result.tables = data.get("tables", [])
        result.tables_success = data.get("tables_success", False)
        result.tables_error = data.get("tables_error")

        if "table_stats" in data:
            stats = data["table_stats"]
            result.table_stats = TableStats(total_tables=stats.get("total_tables", 0))

        # 表单数据
        result.forms = data.get("forms", [])
        result.forms_success = data.get("forms_success", False)
        result.forms_error = data.get("forms_error")

        if "form_stats" in data:
            stats = data["form_stats"]
            result.form_stats = FormStats(
                total_forms=stats.get("total_forms", 0),
                input_fields=stats.get("input_fields", 0),
                buttons=stats.get("buttons", 0),
            )

        # 通用错误
        result.error = data.get("error")

        return result

    # ==================== 特殊方法 ====================

    def __repr__(self) -> str:
        """字符串表示"""
        status = "✅" if self.success else "❌"
        return f"CrawlResult({status} {self.url}, {len(self.successful_extractors)} extractors)"

    def __bool__(self) -> bool:
        """布尔值判断"""
        return self.success

    def __len__(self) -> int:
        """返回成功的提取器数量"""
        return len(self.successful_extractors)

    def __contains__(self, extractor_name: str) -> bool:
        """检查是否包含某个成功的提取器"""
        return extractor_name in self.successful_extractors


# ==================== 工厂函数 ====================


def create_error_result(
    url: str, error: str, timestamp: Optional[float] = None
) -> CrawlResult:
    """创建错误结果对象"""
    result = CrawlResult(url=url, success=False, timestamp=timestamp)
    result.error = error
    return result


def create_success_result(url: str, timestamp: Optional[float] = None) -> CrawlResult:
    """创建成功结果对象的基础版本"""
    return CrawlResult(url=url, success=True, timestamp=timestamp)
