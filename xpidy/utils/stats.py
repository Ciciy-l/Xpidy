"""
统计收集器
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class RequestStats:
    """请求统计"""

    url: str
    start_time: float
    end_time: float
    success: bool
    error: Optional[str] = None
    response_size: int = 0
    extractor_type: str = "unknown"

    @property
    def duration(self) -> float:
        """请求持续时间"""
        return self.end_time - self.start_time

    @property
    def timestamp(self) -> datetime:
        """时间戳"""
        return datetime.fromtimestamp(self.start_time)


@dataclass
class SessionStats:
    """会话统计"""

    start_time: float = field(default_factory=time.time)
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_bytes: int = 0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def duration(self) -> float:
        """会话持续时间"""
        return time.time() - self.start_time


class StatsCollector:
    """统计收集器"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.request_history: deque = deque(maxlen=max_history)
        self.session_stats = SessionStats()

        # 按类型统计
        self.stats_by_extractor: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0, "failed": 0}
        )

        # 错误统计
        self.error_counts: Dict[str, int] = defaultdict(int)

        # 性能统计
        self.performance_stats = {
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "min_duration": float("inf"),
            "max_duration": 0.0,
            "requests_per_minute": 0.0,
        }

        # 实时统计
        self._current_requests = 0
        self._last_minute_requests = deque(maxlen=60)

    def record_request_start(
        self, url: str, extractor_type: str = "unknown"
    ) -> Dict[str, Any]:
        """记录请求开始"""
        start_time = time.time()
        context = {
            "url": url,
            "start_time": start_time,
            "extractor_type": extractor_type,
        }

        self.session_stats.total_requests += 1
        self.stats_by_extractor[extractor_type]["total"] += 1

        logger.debug(f"开始请求: {url}")
        return context

    def record_request_end(
        self,
        context: Dict[str, Any],
        success: bool,
        error: Optional[str] = None,
        response_size: int = 0,
    ) -> None:
        """记录请求结束"""
        end_time = time.time()

        stats = RequestStats(
            url=context["url"],
            start_time=context["start_time"],
            end_time=end_time,
            success=success,
            error=error,
            response_size=response_size,
            extractor_type=context["extractor_type"],
        )

        # 添加到历史记录
        self.request_history.append(stats)

        # 更新会话统计
        if success:
            self.session_stats.successful_requests += 1
            self.stats_by_extractor[stats.extractor_type]["success"] += 1
        else:
            self.session_stats.failed_requests += 1
            self.stats_by_extractor[stats.extractor_type]["failed"] += 1
            if error:
                self.error_counts[error] += 1

        self.session_stats.total_bytes += response_size

        # 更新性能统计
        self._update_performance_stats(stats.duration)

        # 更新实时统计
        self._current_requests += 1
        self._last_minute_requests.append(time.time())

        logger.debug(f"请求完成: {stats.url} - 耗时: {stats.duration:.2f}s")

    def _update_performance_stats(self, duration: float) -> None:
        """更新性能统计"""
        self.performance_stats["total_duration"] += duration
        self.performance_stats["min_duration"] = min(
            self.performance_stats["min_duration"], duration
        )
        self.performance_stats["max_duration"] = max(
            self.performance_stats["max_duration"], duration
        )

        # 计算平均持续时间
        if self.session_stats.total_requests > 0:
            self.performance_stats["avg_duration"] = (
                self.performance_stats["total_duration"]
                / self.session_stats.total_requests
            )

        # 计算每分钟请求数
        now = time.time()
        minute_ago = now - 60
        recent_requests = [t for t in self._last_minute_requests if t > minute_ago]
        self.performance_stats["requests_per_minute"] = len(recent_requests)

    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        return {
            "session": {
                "duration": self.session_stats.duration,
                "total_requests": self.session_stats.total_requests,
                "successful_requests": self.session_stats.successful_requests,
                "failed_requests": self.session_stats.failed_requests,
                "success_rate": self.session_stats.success_rate,
                "total_bytes": self.session_stats.total_bytes,
                "avg_bytes_per_request": (
                    self.session_stats.total_bytes
                    / max(1, self.session_stats.total_requests)
                ),
            },
            "performance": self.performance_stats.copy(),
            "by_extractor": dict(self.stats_by_extractor),
            "errors": dict(self.error_counts),
        }

    def get_recent_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的请求记录"""
        recent = list(self.request_history)[-limit:]
        return [
            {
                "url": req.url,
                "timestamp": req.timestamp.isoformat(),
                "duration": req.duration,
                "success": req.success,
                "error": req.error,
                "response_size": req.response_size,
                "extractor_type": req.extractor_type,
            }
            for req in recent
        ]

    def get_error_analysis(self) -> Dict[str, Any]:
        """获取错误分析"""
        if not self.error_counts:
            return {"total_errors": 0, "error_types": {}}

        total_errors = sum(self.error_counts.values())
        error_percentages = {
            error: (count / total_errors) * 100
            for error, count in self.error_counts.items()
        }

        return {
            "total_errors": total_errors,
            "error_types": dict(self.error_counts),
            "error_percentages": error_percentages,
            "most_common_error": max(self.error_counts.items(), key=lambda x: x[1])[0],
        }

    def get_performance_analysis(self) -> Dict[str, Any]:
        """获取性能分析"""
        if not self.request_history:
            return {}

        durations = [req.duration for req in self.request_history]
        durations.sort()

        n = len(durations)
        p50 = durations[n // 2] if n > 0 else 0
        p90 = durations[int(n * 0.9)] if n > 0 else 0
        p95 = durations[int(n * 0.95)] if n > 0 else 0
        p99 = durations[int(n * 0.99)] if n > 0 else 0

        return {
            "percentiles": {"p50": p50, "p90": p90, "p95": p95, "p99": p99},
            "distribution": {
                "fast_requests": len([d for d in durations if d < 1.0]),
                "medium_requests": len([d for d in durations if 1.0 <= d < 5.0]),
                "slow_requests": len([d for d in durations if d >= 5.0]),
            },
        }

    def get_throughput_stats(self) -> Dict[str, Any]:
        """获取吞吐量统计"""
        if self.session_stats.duration == 0:
            return {"requests_per_second": 0, "bytes_per_second": 0}

        return {
            "requests_per_second": self.session_stats.total_requests
            / self.session_stats.duration,
            "bytes_per_second": self.session_stats.total_bytes
            / self.session_stats.duration,
            "requests_per_minute": self.performance_stats["requests_per_minute"],
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.request_history.clear()
        self.session_stats = SessionStats()
        self.stats_by_extractor.clear()
        self.error_counts.clear()

        self.performance_stats = {
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "min_duration": float("inf"),
            "max_duration": 0.0,
            "requests_per_minute": 0.0,
        }

        self._current_requests = 0
        self._last_minute_requests.clear()

        logger.info("统计信息已重置")

    def export_stats(self) -> Dict[str, Any]:
        """导出完整统计信息"""
        return {
            "summary": self.get_summary(),
            "recent_requests": self.get_recent_requests(50),
            "error_analysis": self.get_error_analysis(),
            "performance_analysis": self.get_performance_analysis(),
            "throughput_stats": self.get_throughput_stats(),
            "export_time": datetime.now().isoformat(),
        }

    def print_summary(self) -> None:
        """打印统计摘要"""
        summary = self.get_summary()

        print("\n" + "=" * 50)
        print("📊 Xpidy 爬虫统计报告")
        print("=" * 50)

        session = summary["session"]
        print(f"🕐 会话时长: {session['duration']:.2f}秒")
        print(f"📄 总请求数: {session['total_requests']}")
        print(f"✅ 成功请求: {session['successful_requests']}")
        print(f"❌ 失败请求: {session['failed_requests']}")
        print(f"📈 成功率: {session['success_rate']:.1f}%")
        print(f"📦 总数据量: {session['total_bytes']} 字节")

        perf = summary["performance"]
        print(f"\n⚡ 性能指标:")
        print(f"   平均响应时间: {perf['avg_duration']:.2f}秒")
        print(f"   最快响应: {perf['min_duration']:.2f}秒")
        print(f"   最慢响应: {perf['max_duration']:.2f}秒")
        print(f"   每分钟请求数: {perf['requests_per_minute']:.1f}")

        if summary["errors"]:
            print(f"\n🚨 错误统计:")
            for error, count in summary["errors"].items():
                print(f"   {error}: {count}次")

        print("=" * 50)
