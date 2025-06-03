"""
重试管理器
"""

import asyncio
import random
from enum import Enum
from typing import Any, Callable, List, Optional, Union

from loguru import logger
from pydantic import BaseModel


class RetryStrategy(str, Enum):
    """重试策略"""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    RANDOM = "random"


class RetryConfig(BaseModel):
    """重试配置"""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_on_exceptions: List[type] = []


class RetryManager:
    """重试管理器"""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    async def retry_async(
        self,
        func: Callable,
        *args,
        retry_config: Optional[RetryConfig] = None,
        **kwargs,
    ) -> Any:
        """异步重试装饰器"""
        config = retry_config or self.config
        last_exception = None

        for attempt in range(config.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                # 检查是否应该重试此异常
                if config.retry_on_exceptions:
                    if not any(
                        isinstance(e, exc_type)
                        for exc_type in config.retry_on_exceptions
                    ):
                        logger.warning(
                            f"异常类型不在重试列表中，直接抛出: {type(e).__name__}"
                        )
                        raise

                if attempt == config.max_attempts - 1:
                    logger.error(f"重试失败，已达到最大重试次数 {config.max_attempts}")
                    break

                delay = self._calculate_delay(attempt, config)
                logger.warning(f"第 {attempt + 1} 次尝试失败: {e}，{delay:.2f}秒后重试")
                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算延迟时间"""
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_factor**attempt)
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(config.base_delay, config.max_delay)
        else:
            delay = config.base_delay

        # 限制最大延迟
        delay = min(delay, config.max_delay)

        # 添加抖动
        if config.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    def create_retry_decorator(self, config: Optional[RetryConfig] = None):
        """创建重试装饰器"""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                return await self.retry_async(
                    func, *args, retry_config=config, **kwargs
                )

            return wrapper

        return decorator


# 便捷函数
async def retry_on_failure(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    *args,
    **kwargs,
) -> Any:
    """便捷的重试函数"""
    config = RetryConfig(
        max_attempts=max_attempts, base_delay=base_delay, strategy=strategy
    )
    manager = RetryManager(config)
    return await manager.retry_async(func, *args, **kwargs)
