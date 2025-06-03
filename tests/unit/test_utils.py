"""
工具类单元测试
"""

import asyncio

import pytest

from xpidy.utils import CacheManager, ContentUtils, StatsCollector, URLUtils
from xpidy.utils.cache import CacheConfig


class TestURLUtils:
    """URL工具测试"""

    def test_is_valid_url(self):
        """测试URL有效性检查"""
        assert URLUtils.is_valid_url("https://example.com")
        assert URLUtils.is_valid_url("http://example.com")
        assert not URLUtils.is_valid_url("not-a-url")
        assert not URLUtils.is_valid_url("")

    def test_normalize_url(self):
        """测试URL标准化"""
        assert URLUtils.normalize_url("example.com") == "https://example.com/"
        assert (
            URLUtils.normalize_url("https://example.com:443/") == "https://example.com/"
        )
        assert URLUtils.normalize_url("http://example.com:80/") == "http://example.com/"

    def test_extract_domain(self):
        """测试域名提取"""
        assert (
            URLUtils.extract_domain("https://www.example.com/path") == "www.example.com"
        )
        assert URLUtils.extract_domain("http://example.com") == "example.com"
        assert URLUtils.extract_domain("invalid") is None

    def test_extract_base_domain(self):
        """测试基础域名提取"""
        assert URLUtils.extract_base_domain("https://www.example.com") == "example.com"
        assert (
            URLUtils.extract_base_domain("https://sub.domain.example.com")
            == "example.com"
        )

    def test_is_same_domain(self):
        """测试同域检查"""
        assert URLUtils.is_same_domain(
            "https://example.com/page1", "https://example.com/page2"
        )
        assert not URLUtils.is_same_domain("https://example.com", "https://other.com")

    def test_join_url(self):
        """测试URL连接"""
        assert (
            URLUtils.join_url("https://example.com", "/path")
            == "https://example.com/path"
        )
        assert (
            URLUtils.join_url("https://example.com/", "path")
            == "https://example.com/path"
        )

    def test_clean_url_params(self):
        """测试URL参数清理"""
        url = "https://example.com/path?param1=value1&param2=value2"
        cleaned = URLUtils.clean_url_params(url)
        assert cleaned == "https://example.com/path"

        kept = URLUtils.clean_url_params(url, keep_params=["param1"])
        assert "param1=value1" in kept
        assert "param2" not in kept

    def test_get_file_extension_from_url(self):
        """测试文件扩展名提取"""
        assert (
            URLUtils.get_file_extension_from_url("https://example.com/file.pdf")
            == "pdf"
        )
        assert (
            URLUtils.get_file_extension_from_url("https://example.com/image.jpg")
            == "jpg"
        )
        assert URLUtils.get_file_extension_from_url("https://example.com/page") is None

    def test_is_media_url(self):
        """测试媒体URL检查"""
        assert URLUtils.is_media_url("https://example.com/image.jpg")
        assert URLUtils.is_media_url("https://example.com/video.mp4")
        assert not URLUtils.is_media_url("https://example.com/page.html")


class TestContentUtils:
    """内容工具测试"""

    def test_clean_html(self):
        """测试HTML清理"""
        html = '<div><script>alert("test")</script><p>Hello World</p></div>'
        cleaned = ContentUtils.clean_html(html)
        assert "Hello World" in cleaned
        assert "script" not in cleaned
        assert "alert" not in cleaned

    def test_normalize_whitespace(self):
        """测试空白字符标准化"""
        text = "  Hello   \n\n  World  \t "
        normalized = ContentUtils.normalize_whitespace(text)
        assert normalized == "Hello World"

    def test_extract_email_addresses(self):
        """测试邮箱地址提取"""
        text = "Contact us at test@example.com or admin@domain.org"
        emails = ContentUtils.extract_email_addresses(text)
        assert "test@example.com" in emails
        assert "admin@domain.org" in emails
        assert len(emails) == 2

    def test_extract_phone_numbers(self):
        """测试电话号码提取"""
        text = "Call us at 123-456-7890 or (555) 123-4567"
        phones = ContentUtils.extract_phone_numbers(text)
        assert len(phones) >= 1  # 至少能识别一个格式

    def test_count_words(self):
        """测试词数统计"""
        english_text = "Hello world this is a test"
        assert ContentUtils.count_words(english_text) == 6

        chinese_text = "这是中文测试"
        assert ContentUtils.count_words(chinese_text, "chinese") == 6

    def test_contains_chinese(self):
        """测试中文检测"""
        assert ContentUtils.contains_chinese("这是中文")
        assert not ContentUtils.contains_chinese("This is English")
        assert ContentUtils.contains_chinese("Mixed 中文 text")

    def test_detect_language(self):
        """测试语言检测"""
        assert ContentUtils.detect_language("This is English text") == "english"
        assert ContentUtils.detect_language("这是中文文本") == "chinese"
        assert ContentUtils.detect_language("Mixed 中文 text") == "mixed"

    def test_clean_filename(self):
        """测试文件名清理"""
        dirty_name = 'test<>:"/\\|?*file.txt'
        clean_name = ContentUtils.clean_filename(dirty_name)
        assert "<" not in clean_name
        assert ">" not in clean_name
        assert ":" not in clean_name

    def test_truncate_text(self):
        """测试文本截断"""
        long_text = "This is a very long text that should be truncated"
        truncated = ContentUtils.truncate_text(long_text, 20)
        assert len(truncated) <= 20
        assert truncated.endswith("...")


class TestCacheManager:
    """缓存管理器测试"""

    @pytest.fixture
    def cache_manager(self):
        """缓存管理器fixture"""
        config = CacheConfig(
            cache_dir=".test_cache",
            enable_file_cache=False,  # 只测试内存缓存
            enable_memory_cache=True,
        )
        return CacheManager(config)

    @pytest.mark.asyncio
    async def test_cache_operations(self, cache_manager):
        """测试缓存基本操作"""
        # 设置缓存
        await cache_manager.set("test_key", {"data": "test_value"})

        # 获取缓存
        result = await cache_manager.get("test_key")
        assert result == {"data": "test_value"}

        # 删除缓存
        deleted = await cache_manager.delete("test_key")
        assert deleted

        # 再次获取应该为空
        result = await cache_manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl(self, cache_manager):
        """测试缓存TTL"""
        # 设置短TTL的缓存
        await cache_manager.set("ttl_key", "test_data", ttl=1)

        # 立即获取应该有数据
        result = await cache_manager.get("ttl_key")
        assert result == "test_data"

        # 等待过期后应该为空
        await asyncio.sleep(1.1)
        result = await cache_manager.get("ttl_key")
        assert result is None


class TestStatsCollector:
    """统计收集器测试"""

    @pytest.fixture
    def stats_collector(self):
        """统计收集器fixture"""
        return StatsCollector(max_history=10)

    def test_request_recording(self, stats_collector):
        """测试请求记录"""
        # 记录请求开始
        context = stats_collector.record_request_start("https://example.com", "text")
        assert context["url"] == "https://example.com"
        assert context["extractor_type"] == "text"

        # 记录请求结束
        stats_collector.record_request_end(context, success=True, response_size=1024)

        # 检查统计
        summary = stats_collector.get_summary()
        assert summary["session"]["total_requests"] == 1
        assert summary["session"]["successful_requests"] == 1
        assert summary["session"]["failed_requests"] == 0

    def test_error_recording(self, stats_collector):
        """测试错误记录"""
        context = stats_collector.record_request_start("https://example.com", "text")

        stats_collector.record_request_end(
            context, success=False, error="Connection timeout"
        )

        summary = stats_collector.get_summary()
        assert summary["session"]["failed_requests"] == 1
        assert "Connection timeout" in summary["errors"]

    def test_performance_stats(self, stats_collector):
        """测试性能统计"""
        import time

        context = stats_collector.record_request_start("https://example.com", "text")
        time.sleep(0.1)  # 模拟处理时间

        stats_collector.record_request_end(context, success=True, response_size=1024)

        summary = stats_collector.get_summary()
        assert summary["performance"]["avg_duration"] > 0
        assert summary["performance"]["min_duration"] > 0
