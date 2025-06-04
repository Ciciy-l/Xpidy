"""
图片提取器
"""

import base64
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import Page
from pydantic import Field

from ..utils.url_utils import URLUtils
from .base_extractor import BaseExtractor, BaseExtractorConfig


class ImageExtractorConfig(BaseExtractorConfig):
    """图片提取器配置"""

    # 尺寸过滤
    min_width: int = Field(default=0, description="最小宽度")
    min_height: int = Field(default=0, description="最小高度")
    min_area: int = Field(default=0, description="最小面积")

    # 格式过滤
    allowed_formats: List[str] = Field(
        default_factory=lambda: ["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"],
        description="允许的图片格式",
    )
    exclude_formats: List[str] = Field(
        default_factory=list, description="排除的图片格式"
    )

    # 属性提取
    extract_alt: bool = Field(default=True, description="提取alt属性")
    extract_title: bool = Field(default=True, description="提取title属性")
    extract_dimensions: bool = Field(default=True, description="提取尺寸信息")
    extract_lazy_load: bool = Field(default=True, description="提取懒加载属性")

    # 特殊过滤
    exclude_base64: bool = Field(default=True, description="排除base64图片")
    exclude_small_images: bool = Field(default=True, description="排除小图片（如图标）")
    exclude_tracking_pixels: bool = Field(default=True, description="排除跟踪像素")


class ImageExtractor(BaseExtractor):
    """图片提取器"""

    def __init__(self, config: Optional[ImageExtractorConfig] = None):
        super().__init__(config)

    @classmethod
    def get_default_config(cls) -> ImageExtractorConfig:
        """获取默认配置"""
        return ImageExtractorConfig()

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取页面中的所有图片"""
        current_url = page.url

        # 获取提取范围
        extraction_scopes = await self._get_extraction_scope(page)

        all_images = []
        for scope in extraction_scopes:
            scope_images = await self._extract_images_from_scope(scope, current_url)
            all_images.extend(scope_images)

        # 过滤和处理图片
        filtered_images = self._filter_and_deduplicate_items(
            all_images, current_url, url_key="src"
        )

        # 统计信息
        stats = self._generate_stats(filtered_images)

        return {
            "url": current_url,
            "images": filtered_images,
            "total_images": len(filtered_images),
            "stats": stats,
            "timestamp": time.time(),
            "extraction_method": "image_extractor",
        }

    async def _extract_images_from_scope(
        self, scope, base_url: str
    ) -> List[Dict[str, Any]]:
        """从指定范围提取图片"""
        try:
            if hasattr(scope, "query_selector_all"):
                # 这是一个页面
                images_data = await scope.evaluate(
                    """
                    () => {
                        const images = [];
                        const imgElements = document.querySelectorAll('img');
                        
                        imgElements.forEach(img => {
                            const data = {
                                src: img.src || img.getAttribute('src') || '',
                                alt: img.alt || '',
                                title: img.title || '',
                                width: img.naturalWidth || img.width || 0,
                                height: img.naturalHeight || img.height || 0,
                                loading: img.loading || '',
                                className: img.className || '',
                                id: img.id || ''
                            };
                            
                            // 懒加载属性
                            const dataSrc = img.getAttribute('data-src') || 
                                          img.getAttribute('data-original') ||
                                          img.getAttribute('data-lazy');
                            if (dataSrc) {
                                data.dataSrc = dataSrc;
                                data.isLazy = true;
                            }
                            
                            // srcset属性
                            if (img.srcset) {
                                data.srcset = img.srcset;
                            }
                            
                            images.push(data);
                        });
                        
                        return images;
                    }
                """
                )
            else:
                # 这是一个元素句柄
                images_data = await scope.evaluate(
                    """
                    (element) => {
                        const images = [];
                        const imgElements = element.querySelectorAll('img');
                        
                        imgElements.forEach(img => {
                            const data = {
                                src: img.src || img.getAttribute('src') || '',
                                alt: img.alt || '',
                                title: img.title || '',
                                width: img.naturalWidth || img.width || 0,
                                height: img.naturalHeight || img.height || 0,
                                loading: img.loading || '',
                                className: img.className || '',
                                id: img.id || ''
                            };
                            
                            const dataSrc = img.getAttribute('data-src') || 
                                          img.getAttribute('data-original') ||
                                          img.getAttribute('data-lazy');
                            if (dataSrc) {
                                data.dataSrc = dataSrc;
                                data.isLazy = true;
                            }
                            
                            if (img.srcset) {
                                data.srcset = img.srcset;
                            }
                            
                            images.push(data);
                        });
                        
                        return images;
                    }
                """
                )

            processed_images = []
            for image_data in images_data or []:
                processed_image = await self._process_image(image_data, base_url)
                if processed_image:
                    processed_images.append(processed_image)

            return processed_images

        except Exception:
            return []

    async def _process_image(
        self, image_data: Dict[str, Any], base_url: str
    ) -> Optional[Dict[str, Any]]:
        """处理单个图片"""
        src = image_data.get("src", "").strip()
        if not src:
            # 检查懒加载src
            src = image_data.get("dataSrc", "").strip()
            if not src:
                return None

        # 排除base64图片
        if self.config.exclude_base64 and src.startswith("data:"):
            return None

        # 转换为绝对URL
        absolute_url = urljoin(base_url, src)
        parsed_url = urlparse(absolute_url)

        # 获取文件扩展名
        file_extension = self._get_file_extension(absolute_url)

        # 格式过滤
        if (
            self.config.allowed_formats
            and file_extension not in self.config.allowed_formats
        ):
            return None
        if file_extension in self.config.exclude_formats:
            return None

        # 尺寸过滤
        width = image_data.get("width", 0)
        height = image_data.get("height", 0)

        if width < self.config.min_width or height < self.config.min_height:
            return None

        if self.config.min_area > 0 and (width * height) < self.config.min_area:
            return None

        # 排除小图片（如图标）
        if self.config.exclude_small_images and width <= 16 and height <= 16:
            return None

        # 排除跟踪像素
        if self.config.exclude_tracking_pixels and width == 1 and height == 1:
            return None

        # 构建结果
        result = {
            "src": absolute_url,
            "original_src": image_data.get("src", ""),
            "file_extension": file_extension,
            "domain": parsed_url.netloc,
        }

        if self.config.extract_dimensions:
            result.update(
                {
                    "width": width,
                    "height": height,
                    "area": width * height,
                    "aspect_ratio": round(width / height, 2) if height > 0 else 0,
                }
            )

        if self.config.extract_alt:
            result["alt"] = image_data.get("alt", "")

        if self.config.extract_title:
            result["title"] = image_data.get("title", "")

        if self.config.extract_lazy_load:
            result["is_lazy"] = image_data.get("isLazy", False)
            if image_data.get("dataSrc"):
                result["data_src"] = image_data["dataSrc"]

        # 其他属性
        for attr in ["loading", "className", "id", "srcset"]:
            if image_data.get(attr):
                result[attr] = image_data[attr]

        return result

    def _get_file_extension(self, url: str) -> str:
        """获取文件扩展名"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        if "." in path:
            extension = path.split(".")[-1]
            # 去除查询参数
            return extension.split("?")[0]
        return ""

    def _generate_stats(self, images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成统计信息"""
        if not images:
            return {}

        stats = {
            "by_format": {},
            "by_domain": {},
            "size_distribution": {
                "small": 0,  # < 100x100
                "medium": 0,  # 100x100 - 500x500
                "large": 0,  # > 500x500
            },
            "lazy_loaded": sum(1 for img in images if img.get("is_lazy", False)),
            "with_alt": sum(1 for img in images if img.get("alt", "")),
            "total_area": sum(img.get("area", 0) for img in images),
        }

        for image in images:
            # 按格式统计
            ext = image.get("file_extension", "unknown")
            stats["by_format"][ext] = stats["by_format"].get(ext, 0) + 1

            # 按域名统计
            domain = image.get("domain", "unknown")
            stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

            # 尺寸分布
            width = image.get("width", 0)
            height = image.get("height", 0)
            if width < 100 or height < 100:
                stats["size_distribution"]["small"] += 1
            elif width <= 500 and height <= 500:
                stats["size_distribution"]["medium"] += 1
            else:
                stats["size_distribution"]["large"] += 1

        return stats

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器"""
        # 文件大小过滤（如果提供）
        if filters.get("max_file_size"):
            # 这里可以添加实际的文件大小检查逻辑
            pass

        # 文件名过滤
        if filters.get("filename_patterns"):
            src = item.get("src", "")
            import re

            patterns = filters["filename_patterns"]
            if not any(re.search(pattern, src, re.IGNORECASE) for pattern in patterns):
                return False

        return True

    async def extract_by_size(
        self, page: Page, min_width: int = 0, min_height: int = 0, **kwargs
    ) -> Dict[str, Any]:
        """根据尺寸过滤图片"""
        kwargs["min_width"] = min_width
        kwargs["min_height"] = min_height
        return await self.extract(page, **kwargs)

    async def extract_by_format(
        self, page: Page, formats: List[str], **kwargs
    ) -> Dict[str, Any]:
        """根据格式过滤图片"""
        kwargs["allowed_formats"] = [fmt.lower() for fmt in formats]
        return await self.extract(page, **kwargs)

    async def extract_with_metadata(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取图片并包含详细元数据"""
        kwargs["include_detailed_metadata"] = True
        return await self.extract(page, **kwargs)

    async def _extract_images(self, page: Page) -> List[Dict[str, str]]:
        """重写基类方法，增强图片提取功能"""
        try:
            images = await page.evaluate(
                """
                () => {
                    const images = [];
                    
                    // 提取img标签
                    document.querySelectorAll('img').forEach(img => {
                        const image = {
                            src: img.src || '',
                            alt: img.alt || '',
                            title: img.title || '',
                            width: img.naturalWidth || img.width || 0,
                            height: img.naturalHeight || img.height || 0,
                            displayWidth: img.width || 0,
                            displayHeight: img.height || 0,
                            className: img.className || '',
                            id: img.id || '',
                            loading: img.loading || '',
                            decoding: img.decoding || '',
                            crossOrigin: img.crossOrigin || '',
                            srcset: img.srcset || '',
                            sizes: img.sizes || '',
                            type: 'img'
                        };
                        
                        // 获取父元素信息
                        const parent = img.parentElement;
                        if (parent) {
                            image.parentTag = parent.tagName.toLowerCase();
                            image.parentClass = parent.className || '';
                        }
                        
                        // 检查是否在链接中
                        const linkParent = img.closest('a[href]');
                        if (linkParent) {
                            image.linkUrl = linkParent.href;
                            image.linkText = linkParent.textContent?.trim() || '';
                        }
                        
                        // 检查是否在图形容器中
                        const figure = img.closest('figure');
                        if (figure) {
                            const caption = figure.querySelector('figcaption');
                            image.caption = caption ? caption.textContent?.trim() : '';
                        }
                        
                        images.push(image);
                    });
                    
                    // 提取CSS背景图片
                    document.querySelectorAll('*').forEach(element => {
                        const styles = window.getComputedStyle(element);
                        const backgroundImage = styles.backgroundImage;
                        
                        if (backgroundImage && backgroundImage !== 'none') {
                            const urlMatch = backgroundImage.match(/url\\(["']?([^"')]+)["']?\\)/);
                            if (urlMatch && urlMatch[1]) {
                                const image = {
                                    src: urlMatch[1],
                                    alt: element.getAttribute('alt') || '',
                                    title: element.getAttribute('title') || '',
                                    width: element.offsetWidth || 0,
                                    height: element.offsetHeight || 0,
                                    displayWidth: element.offsetWidth || 0,
                                    displayHeight: element.offsetHeight || 0,
                                    className: element.className || '',
                                    id: element.id || '',
                                    type: 'background',
                                    parentTag: element.tagName.toLowerCase()
                                };
                                images.push(image);
                            }
                        }
                    });
                    
                    // 提取SVG图像
                    document.querySelectorAll('svg').forEach(svg => {
                        const image = {
                            src: '', // SVG is inline
                            alt: svg.getAttribute('alt') || '',
                            title: svg.getAttribute('title') || svg.querySelector('title')?.textContent || '',
                            width: svg.getAttribute('width') ? parseInt(svg.getAttribute('width')) : svg.getBoundingClientRect().width,
                            height: svg.getAttribute('height') ? parseInt(svg.getAttribute('height')) : svg.getBoundingClientRect().height,
                            displayWidth: svg.getBoundingClientRect().width,
                            displayHeight: svg.getBoundingClientRect().height,
                            className: svg.className.baseVal || '',
                            id: svg.id || '',
                            type: 'svg',
                            svgContent: svg.outerHTML
                        };
                        
                        const parent = svg.parentElement;
                        if (parent) {
                            image.parentTag = parent.tagName.toLowerCase();
                            image.parentClass = parent.className || '';
                        }
                        
                        images.push(image);
                    });
                    
                    return images;
                }
            """
            )
            return images or []
        except Exception as e:
            logger.warning(f"JavaScript图片提取失败，使用备用方法: {e}")
            return await super()._extract_images(page)

    async def _process_svg_image(
        self, svg_image: Dict[str, Any], base_url: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """处理SVG图像"""
        try:
            processed_image = {
                "url": "",  # SVG是内联的
                "original_src": "",
                "alt": svg_image.get("alt", ""),
                "title": svg_image.get("title", ""),
                "width": svg_image.get("width", 0),
                "height": svg_image.get("height", 0),
                "display_width": svg_image.get("displayWidth", 0),
                "display_height": svg_image.get("displayHeight", 0),
                "aspect_ratio": (
                    round(svg_image.get("width", 0) / svg_image.get("height", 1), 2)
                    if svg_image.get("height", 0) > 0
                    else 0
                ),
                "file_extension": "svg",
                "type": "svg",
                "className": svg_image.get("className", ""),
                "id": svg_image.get("id", ""),
                "parentTag": svg_image.get("parentTag", ""),
                "parentClass": svg_image.get("parentClass", ""),
                "svg_content": svg_image.get("svgContent", ""),
                "is_inline": True,
            }

            return processed_image

        except Exception as e:
            logger.warning(f"处理SVG图像失败: {e}")
            return None

    async def _get_detailed_metadata(self, image_url: str) -> Dict[str, Any]:
        """获取图片的详细元数据"""
        try:
            # 这里可以添加获取图片EXIF数据、文件大小等的逻辑
            # 目前返回基本信息
            return {
                "content_type": self._guess_content_type(image_url),
                "estimated_size": self._estimate_file_size(image_url),
            }
        except Exception:
            return {}

    def _guess_content_type(self, image_url: str) -> str:
        """根据文件扩展名猜测内容类型"""
        extension = URLUtils.get_file_extension_from_url(image_url)
        if not extension:
            return "unknown"

        content_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "svg": "image/svg+xml",
            "bmp": "image/bmp",
            "ico": "image/x-icon",
            "tiff": "image/tiff",
            "avif": "image/avif",
        }

        return content_types.get(extension.lower(), "image/unknown")

    def _estimate_file_size(self, image_url: str) -> str:
        """估算文件大小（基于URL特征）"""
        # 这是一个简单的启发式方法
        if "thumb" in image_url.lower() or "small" in image_url.lower():
            return "small"
        elif "large" in image_url.lower() or "big" in image_url.lower():
            return "large"
        else:
            return "medium"

    async def analyze_image_structure(self, page: Page) -> Dict[str, Any]:
        """分析页面图片结构"""
        try:
            result = await self.extract(page, include_detailed_metadata=True)
            images = result["images"]

            # 统计分析
            by_type = {}
            by_format = {}
            by_size = {"small": 0, "medium": 0, "large": 0}
            by_parent = {}

            total_width = 0
            total_height = 0

            for image in images:
                # 按类型分类
                img_type = image.get("type", "unknown")
                by_type[img_type] = by_type.get(img_type, 0) + 1

                # 按格式分类
                file_ext = image.get("file_extension", "unknown")
                by_format[file_ext] = by_format.get(file_ext, 0) + 1

                # 按尺寸分类
                if image.get("is_small"):
                    by_size["small"] += 1
                elif image.get("is_large"):
                    by_size["large"] += 1
                else:
                    by_size["medium"] += 1

                # 按父元素分类
                parent = image.get("parentTag", "unknown")
                by_parent[parent] = by_parent.get(parent, 0) + 1

                # 累计尺寸
                total_width += image.get("width", 0)
                total_height += image.get("height", 0)

            analysis = {
                "url": page.url,
                "total_images": len(images),
                "by_type": by_type,
                "by_format": by_format,
                "by_size": by_size,
                "by_parent_element": by_parent,
                "images_with_alt": len([img for img in images if img.get("alt")]),
                "images_with_title": len([img for img in images if img.get("title")]),
                "images_with_links": len([img for img in images if img.get("linkUrl")]),
                "images_with_captions": len(
                    [img for img in images if img.get("caption")]
                ),
                "avg_width": round(total_width / len(images), 2) if images else 0,
                "avg_height": round(total_height / len(images), 2) if images else 0,
                "inline_svg_count": len(
                    [img for img in images if img.get("type") == "svg"]
                ),
                "background_images": len(
                    [img for img in images if img.get("type") == "background"]
                ),
                "timestamp": time.time(),
                "extraction_method": "image_analysis",
            }

            return analysis

        except Exception as e:
            logger.error(f"图片结构分析失败: {e}")
            raise
