"""
URL工具类
"""

import re
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse, urlunparse

from loguru import logger


class URLUtils:
    """URL工具类"""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """检查URL是否有效"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def normalize_url(url: str) -> str:
        """标准化URL"""
        if not url:
            return ""

        # 添加协议前缀
        if not url.startswith(("http://", "https://")):
            if url.startswith("//"):
                url = "https:" + url
            else:
                url = "https://" + url

        try:
            parsed = urlparse(url)

            # 移除默认端口
            netloc = parsed.netloc
            if ":80" in netloc and parsed.scheme == "http":
                netloc = netloc.replace(":80", "")
            elif ":443" in netloc and parsed.scheme == "https":
                netloc = netloc.replace(":443", "")

            # 标准化路径
            path = parsed.path
            if not path:
                path = "/"

            # 重建URL
            normalized = urlunparse(
                (
                    parsed.scheme,
                    netloc,
                    path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )

            return normalized

        except Exception as e:
            logger.warning(f"URL标准化失败: {url} - {e}")
            return url

    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """提取域名"""
        try:
            parsed = urlparse(url)
            # 检查是否有有效的netloc
            if parsed.netloc:
                return parsed.netloc.lower()
            else:
                return None
        except Exception:
            return None

    @staticmethod
    def extract_base_domain(url: str) -> Optional[str]:
        """提取基础域名（去除子域名）"""
        domain = URLUtils.extract_domain(url)
        if not domain:
            return None

        # 简单的基础域名提取逻辑
        parts = domain.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return domain

    @staticmethod
    def is_same_domain(url1: str, url2: str) -> bool:
        """检查两个URL是否同域"""
        domain1 = URLUtils.extract_domain(url1)
        domain2 = URLUtils.extract_domain(url2)
        return domain1 == domain2 if domain1 and domain2 else False

    @staticmethod
    def join_url(base_url: str, relative_url: str) -> str:
        """连接URL"""
        try:
            return urljoin(base_url, relative_url)
        except Exception as e:
            logger.warning(f"URL连接失败: {base_url} + {relative_url} - {e}")
            return relative_url

    @staticmethod
    def extract_links_from_text(text: str, base_url: Optional[str] = None) -> List[str]:
        """从文本中提取链接"""
        links = []

        # URL正则表达式
        url_pattern = re.compile(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )

        # 查找所有URL
        urls = url_pattern.findall(text)
        for url in urls:
            if URLUtils.is_valid_url(url):
                links.append(url)

        # 如果提供了base_url，也查找相对链接
        if base_url:
            relative_pattern = re.compile(r'href=["\']([^"\']+)["\']')
            relative_urls = relative_pattern.findall(text)

            for rel_url in relative_urls:
                if not rel_url.startswith(("http://", "https://", "mailto:", "tel:")):
                    full_url = URLUtils.join_url(base_url, rel_url)
                    if URLUtils.is_valid_url(full_url):
                        links.append(full_url)

        return list(set(links))  # 去重

    @staticmethod
    def clean_url_params(url: str, keep_params: Optional[List[str]] = None) -> str:
        """清理URL参数"""
        try:
            parsed = urlparse(url)

            if not parsed.query:
                return url

            if keep_params:
                # 只保留指定的参数
                query_dict = parse_qs(parsed.query)
                filtered_dict = {
                    k: v for k, v in query_dict.items() if k in keep_params
                }

                # 重建查询字符串
                query_parts = []
                for k, v_list in filtered_dict.items():
                    for v in v_list:
                        query_parts.append(f"{k}={quote(str(v))}")

                new_query = "&".join(query_parts)
            else:
                # 移除所有参数
                new_query = ""

            # 重建URL
            cleaned = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )

            return cleaned

        except Exception as e:
            logger.warning(f"URL参数清理失败: {url} - {e}")
            return url

    @staticmethod
    def add_url_params(url: str, params: dict) -> str:
        """添加URL参数"""
        try:
            parsed = urlparse(url)
            query_dict = parse_qs(parsed.query)

            # 添加新参数
            for k, v in params.items():
                query_dict[k] = [str(v)]

            # 重建查询字符串
            query_parts = []
            for k, v_list in query_dict.items():
                for v in v_list:
                    query_parts.append(f"{k}={quote(str(v))}")

            new_query = "&".join(query_parts)

            # 重建URL
            new_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )

            return new_url

        except Exception as e:
            logger.warning(f"URL参数添加失败: {url} - {e}")
            return url

    @staticmethod
    def get_url_params(url: str) -> dict:
        """获取URL参数"""
        try:
            parsed = urlparse(url)
            return parse_qs(parsed.query)
        except Exception:
            return {}

    @staticmethod
    def is_absolute_url(url: str) -> bool:
        """检查是否为绝对URL"""
        return url.startswith(("http://", "https://"))

    @staticmethod
    def to_absolute_url(relative_url: str, base_url: str) -> str:
        """转换为绝对URL"""
        if URLUtils.is_absolute_url(relative_url):
            return relative_url
        return URLUtils.join_url(base_url, relative_url)

    @staticmethod
    def filter_urls_by_pattern(
        urls: List[str], pattern: str, exclude: bool = False
    ) -> List[str]:
        """根据模式过滤URL"""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            if exclude:
                return [url for url in urls if not regex.search(url)]
            else:
                return [url for url in urls if regex.search(url)]
        except re.error as e:
            logger.error(f"正则表达式错误: {pattern} - {e}")
            return urls

    @staticmethod
    def get_file_extension_from_url(url: str) -> Optional[str]:
        """从URL获取文件扩展名"""
        try:
            parsed = urlparse(url)
            path = parsed.path
            if "." in path:
                return path.split(".")[-1].lower()
            return None
        except Exception:
            return None

    @staticmethod
    def is_media_url(url: str) -> bool:
        """检查是否为媒体文件URL"""
        media_extensions = {
            "jpg",
            "jpeg",
            "png",
            "gif",
            "bmp",
            "webp",
            "svg",  # 图片
            "mp4",
            "avi",
            "mov",
            "wmv",
            "flv",
            "webm",  # 视频
            "mp3",
            "wav",
            "flac",
            "aac",
            "ogg",  # 音频
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",  # 文档
        }

        ext = URLUtils.get_file_extension_from_url(url)
        return ext in media_extensions if ext else False

    @staticmethod
    def extract_sitemap_urls(sitemap_content: str) -> List[str]:
        """从sitemap内容提取URL"""
        urls = []

        # XML sitemap
        xml_pattern = re.compile(r"<loc>(.*?)</loc>", re.IGNORECASE)
        xml_urls = xml_pattern.findall(sitemap_content)
        urls.extend(xml_urls)

        # 文本sitemap
        lines = sitemap_content.split("\n")
        for line in lines:
            line = line.strip()
            if URLUtils.is_valid_url(line):
                urls.append(line)

        return list(set(urls))  # 去重

    @staticmethod
    def batch_normalize_urls(urls: List[str]) -> List[str]:
        """批量标准化URL"""
        normalized_urls = []
        for url in urls:
            normalized = URLUtils.normalize_url(url)
            if normalized:
                normalized_urls.append(normalized)
        return list(set(normalized_urls))  # 去重
