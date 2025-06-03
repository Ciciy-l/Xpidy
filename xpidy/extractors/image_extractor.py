"""
图片提取器
"""

import base64
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from loguru import logger
from playwright.async_api import Page

from ..utils.url_utils import URLUtils
from .base_extractor import BaseExtractor


class ImageExtractor(BaseExtractor):
    """图片提取器"""

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取页面中的所有图片"""
        try:
            current_url = page.url
            images = await self._extract_images(page)

            # 处理和过滤图片
            processed_images = await self._process_images(images, current_url, **kwargs)

            # 提取额外信息
            metadata = await self._extract_metadata(page)

            result = {
                "url": current_url,
                "images": processed_images,
                "total_images": len(processed_images),
                "metadata": metadata,
                "timestamp": time.time(),
                "extraction_method": "image_extractor",
            }

            logger.info(f"提取到 {len(processed_images)} 张图片")
            return result

        except Exception as e:
            logger.error(f"图片提取失败: {e}")
            raise

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

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用图片特定的过滤器"""
        # 尺寸过滤
        min_width = filters.get("min_width", 0)
        min_height = filters.get("min_height", 0)
        width = item.get("width", 0)
        height = item.get("height", 0)

        if width < min_width or height < min_height:
            return False

        # 格式过滤
        allowed_formats = filters.get("allowed_formats", [])
        if allowed_formats:
            file_extension = URLUtils.get_file_extension_from_url(item.get("url", ""))
            if file_extension and file_extension.lower() not in allowed_formats:
                return False

        return True

    async def _process_images(
        self, images: List[Dict[str, Any]], base_url: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """处理和过滤图片"""
        # 预处理：添加原始src信息和处理特殊类型
        processed_images = []
        for image in images:
            # 处理SVG图像
            if image.get("type") == "svg":
                processed_image = await self._process_svg_image(
                    image, base_url, **kwargs
                )
                if processed_image:
                    processed_images.append(processed_image)
                continue

            # 跳过没有src的图片
            if not image.get("src"):
                continue

            image["original_src"] = image.get("src", "")
            processed_images.append(image)

        # 使用基类的通用过滤方法
        filtered = self._filter_and_deduplicate_items(
            processed_images,
            base_url,
            url_key="src",
            deduplicate=kwargs.get("deduplicate", True),
            max_items=kwargs.get("max_images"),
            exclude_patterns=kwargs.get("exclude_patterns", []),
            **kwargs,
        )

        # 添加图片特定的元数据
        for image in filtered:
            # 重命名src为url以保持一致性
            image["url"] = image.pop("src")

            # 计算图片特定属性
            width = image.get("width", 0)
            height = image.get("height", 0)

            image.update(
                {
                    "aspect_ratio": round(width / height, 2) if height > 0 else 0,
                    "display_width": image.get("displayWidth", 0),
                    "display_height": image.get("displayHeight", 0),
                    "type": image.get("type", "img"),
                    "className": image.get("className", ""),
                    "id": image.get("id", ""),
                    "loading": image.get("loading", ""),
                    "srcset": image.get("srcset", ""),
                    "sizes": image.get("sizes", ""),
                    "parentTag": image.get("parentTag", ""),
                    "parentClass": image.get("parentClass", ""),
                    "linkUrl": image.get("linkUrl", ""),
                    "linkText": image.get("linkText", ""),
                    "caption": image.get("caption", ""),
                    "is_large": width >= 500 or height >= 500,
                    "is_small": width <= 50 or height <= 50,
                    "is_square": (
                        abs(width - height) <= 10 if width > 0 and height > 0 else False
                    ),
                    "is_landscape": (
                        width > height if width > 0 and height > 0 else False
                    ),
                    "is_portrait": (
                        height > width if width > 0 and height > 0 else False
                    ),
                }
            )

            # 添加详细元数据
            if kwargs.get("include_detailed_metadata", False):
                image.update(await self._get_detailed_metadata(image["url"]))

        # 添加URL元数据
        self._add_url_metadata(filtered, base_url, url_key="url")

        return filtered

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
