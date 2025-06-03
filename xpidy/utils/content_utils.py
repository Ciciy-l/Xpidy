"""
内容处理工具类
"""

import html
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from loguru import logger


class ContentUtils:
    """内容处理工具类"""

    @staticmethod
    def clean_html(html_content: str, preserve_formatting: bool = False) -> str:
        """清理HTML内容"""
        if not html_content:
            return ""

        try:
            # 解码HTML实体
            content = html.unescape(html_content)

            # 使用BeautifulSoup解析
            soup = BeautifulSoup(content, "html.parser")

            # 移除脚本和样式标签
            for tag in soup(["script", "style", "noscript", "meta", "link"]):
                tag.decompose()

            if preserve_formatting:
                # 保留基本格式
                for br in soup.find_all("br"):
                    br.replace_with("\n")

                for p in soup.find_all("p"):
                    p.insert_after("\n\n")

                for div in soup.find_all("div"):
                    div.insert_after("\n")

            # 提取文本
            text = soup.get_text()

            # 清理空白字符
            text = ContentUtils.normalize_whitespace(text)

            return text

        except Exception as e:
            logger.warning(f"HTML清理失败: {e}")
            return html_content

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """标准化空白字符"""
        if not text:
            return ""

        # 替换各种空白字符为普通空格
        text = re.sub(r"\s+", " ", text)

        # 移除行首行尾空白
        text = text.strip()

        return text

    @staticmethod
    def extract_sentences(text: str, min_length: int = 10) -> List[str]:
        """提取句子"""
        if not text:
            return []

        # 简单的句子分割
        sentences = re.split(r"[.!?]\s+", text)

        # 过滤太短的句子
        valid_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= min_length:
                valid_sentences.append(sentence)

        return valid_sentences

    @staticmethod
    def extract_keywords(
        text: str, min_word_length: int = 3, max_keywords: int = 20
    ) -> List[str]:
        """提取关键词（简单版本）"""
        if not text:
            return []

        # 移除标点符号并转为小写
        words = re.findall(r"\b[a-zA-Z\u4e00-\u9fff]+\b", text.lower())

        # 过滤短词
        words = [word for word in words if len(word) >= min_word_length]

        # 移除常用停用词
        stop_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
            "a",
            "an",
            "as",
            "it",
            "if",
            "or",
            "but",
            "的",
            "了",
            "在",
            "是",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "一个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没有",
            "看",
            "好",
            "自己",
            "这样",
        }

        # 统计词频
        word_count = {}
        for word in words:
            if word not in stop_words:
                word_count[word] = word_count.get(word, 0) + 1

        # 按频率排序
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)

        # 返回高频词
        return [word for word, count in sorted_words[:max_keywords]]

    @staticmethod
    def extract_email_addresses(text: str) -> List[str]:
        """提取邮箱地址"""
        if not text:
            return []

        email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )

        emails = email_pattern.findall(text)
        return list(set(emails))  # 去重

    @staticmethod
    def extract_phone_numbers(text: str) -> List[str]:
        """提取电话号码（简单版本）"""
        if not text:
            return []

        phone_patterns = [
            r"\b\d{3}-\d{3}-\d{4}\b",  # 123-456-7890
            r"\b\d{3}\.\d{3}\.\d{4}\b",  # 123.456.7890
            r"\b\d{3}\s\d{3}\s\d{4}\b",  # 123 456 7890
            r"\(\d{3}\)\s?\d{3}-\d{4}",  # (123) 456-7890
            r"\b\d{11}\b",  # 中国手机号
            r"\+\d{1,3}\s?\d{3,4}\s?\d{3,4}\s?\d{3,4}",  # 国际格式
        ]

        phones = []
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            phones.extend(matches)

        return list(set(phones))  # 去重

    @staticmethod
    def extract_dates(text: str) -> List[str]:
        """提取日期"""
        if not text:
            return []

        date_patterns = [
            r"\b\d{4}-\d{2}-\d{2}\b",  # 2023-12-25
            r"\b\d{2}/\d{2}/\d{4}\b",  # 12/25/2023
            r"\b\d{2}-\d{2}-\d{4}\b",  # 12-25-2023
            r"\b\d{4}年\d{1,2}月\d{1,2}日\b",  # 2023年12月25日
        ]

        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)

        return list(set(dates))  # 去重

    @staticmethod
    def extract_numbers(text: str) -> List[str]:
        """提取数字"""
        if not text:
            return []

        number_pattern = re.compile(r"\b\d+(?:\.\d+)?\b")
        numbers = number_pattern.findall(text)
        return numbers

    @staticmethod
    def remove_extra_newlines(text: str) -> str:
        """移除多余的换行符"""
        if not text:
            return ""

        # 将多个连续换行符替换为最多两个
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """截断文本"""
        if not text or len(text) <= max_length:
            return text

        truncated = text[: max_length - len(suffix)]

        # 尝试在单词边界截断
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.8:  # 如果最后一个空格位置合理
            truncated = truncated[:last_space]

        return truncated + suffix

    @staticmethod
    def count_words(text: str, language: str = "auto") -> int:
        """统计词数"""
        if not text:
            return 0

        if language == "chinese" or (
            language == "auto" and ContentUtils.contains_chinese(text)
        ):
            # 中文按字符数计算，只计算中文字符
            chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
            return len(chinese_chars)
        else:
            # 英文按单词数计算
            words = re.findall(r"\b\w+\b", text)
            return len(words)

    @staticmethod
    def contains_chinese(text: str) -> bool:
        """检查文本是否包含中文"""
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    @staticmethod
    def detect_language(text: str) -> str:
        """简单的语言检测"""
        if not text:
            return "unknown"

        # 统计不同字符类型
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        english_chars = len(re.findall(r"[a-zA-Z]", text))

        total_chars = chinese_chars + english_chars
        if total_chars == 0:
            return "unknown"

        chinese_ratio = chinese_chars / total_chars

        if chinese_ratio > 0.5:
            return "chinese"
        elif chinese_ratio < 0.1:
            return "english"
        else:
            return "mixed"

    @staticmethod
    def clean_filename(filename: str) -> str:
        """清理文件名中的非法字符"""
        if not filename:
            return "untitled"

        # 移除或替换非法字符
        illegal_chars = r'[<>:"/\\|?*]'
        cleaned = re.sub(illegal_chars, "_", filename)

        # 移除多余的空格和点号
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(". ")

        # 限制长度
        if len(cleaned) > 100:
            cleaned = cleaned[:100]

        return cleaned or "untitled"

    @staticmethod
    def extract_structured_data(
        text: str, patterns: Dict[str, str]
    ) -> Dict[str, List[str]]:
        """根据正则表达式模式提取结构化数据"""
        results = {}

        for name, pattern in patterns.items():
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                results[name] = matches if isinstance(matches, list) else [matches]
            except re.error as e:
                logger.warning(f"正则表达式错误 {name}: {pattern} - {e}")
                results[name] = []

        return results

    @staticmethod
    def summarize_text(text: str, max_sentences: int = 3) -> str:
        """简单的文本摘要（提取前几句）"""
        if not text:
            return ""

        sentences = ContentUtils.extract_sentences(text)
        if len(sentences) <= max_sentences:
            return ". ".join(sentences) + "."

        # 选择前几句作为摘要
        summary_sentences = sentences[:max_sentences]
        return ". ".join(summary_sentences) + "."
