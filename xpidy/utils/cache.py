"""
缓存管理器
"""

import asyncio
import hashlib
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union

from loguru import logger
from pydantic import BaseModel


class CacheConfig(BaseModel):
    """缓存配置"""

    cache_dir: str = ".xpidy_cache"
    max_memory_size: int = 100  # 内存缓存最大条目数
    default_ttl: int = 3600  # 默认TTL(秒)
    enable_file_cache: bool = True
    enable_memory_cache: bool = True
    compression: bool = False


class CacheEntry:
    """缓存条目"""

    def __init__(self, data: Any, ttl: Optional[int] = None):
        self.data = data
        self.created_at = datetime.now()
        self.ttl = ttl
        self.access_count = 0
        self.last_access = self.created_at

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl)

    def access(self) -> Any:
        """访问数据"""
        self.access_count += 1
        self.last_access = datetime.now()
        return self.data


class CacheManager:
    """缓存管理器"""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_dir = Path(self.config.cache_dir)

        # 创建缓存目录
        if self.config.enable_file_cache:
            self.cache_dir.mkdir(exist_ok=True)

    def _generate_key(self, key: str) -> str:
        """生成缓存键的哈希值"""
        return hashlib.md5(key.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        cache_key = self._generate_key(key)

        # 优先检查内存缓存
        if self.config.enable_memory_cache and cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if not entry.is_expired():
                logger.debug(f"命中内存缓存: {key}")
                return entry.access()
            else:
                # 过期则删除
                del self.memory_cache[cache_key]

        # 检查文件缓存
        if self.config.enable_file_cache:
            file_path = self.cache_dir / f"{cache_key}.cache"
            if file_path.exists():
                try:
                    with open(file_path, "rb") as f:
                        cache_data = pickle.load(f)

                    # 检查是否过期
                    created_at = cache_data.get("created_at")
                    ttl = cache_data.get("ttl")

                    if ttl is None or datetime.now() <= created_at + timedelta(
                        seconds=ttl
                    ):
                        data = cache_data["data"]

                        # 同时加载到内存缓存
                        if self.config.enable_memory_cache:
                            self._add_to_memory_cache(cache_key, data, ttl)

                        logger.debug(f"命中文件缓存: {key}")
                        return data
                    else:
                        # 过期则删除文件
                        file_path.unlink()

                except Exception as e:
                    logger.warning(f"读取文件缓存失败: {e}")

        return None

    async def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """设置缓存数据"""
        cache_key = self._generate_key(key)
        cache_ttl = ttl or self.config.default_ttl

        # 存储到内存缓存
        if self.config.enable_memory_cache:
            self._add_to_memory_cache(cache_key, data, cache_ttl)

        # 存储到文件缓存
        if self.config.enable_file_cache:
            try:
                cache_data = {
                    "data": data,
                    "created_at": datetime.now(),
                    "ttl": cache_ttl,
                }

                file_path = self.cache_dir / f"{cache_key}.cache"
                with open(file_path, "wb") as f:
                    pickle.dump(cache_data, f)

                logger.debug(f"缓存已保存: {key}")

            except Exception as e:
                logger.warning(f"保存文件缓存失败: {e}")

    def _add_to_memory_cache(self, cache_key: str, data: Any, ttl: Optional[int]):
        """添加到内存缓存"""
        # 检查内存缓存大小限制
        if len(self.memory_cache) >= self.config.max_memory_size:
            self._evict_lru()

        entry = CacheEntry(data, ttl)
        self.memory_cache[cache_key] = entry

    def _evict_lru(self):
        """清理最少使用的缓存条目"""
        if not self.memory_cache:
            return

        # 找出最少使用的条目
        lru_key = min(
            self.memory_cache.keys(),
            key=lambda k: (
                self.memory_cache[k].access_count,
                self.memory_cache[k].last_access,
            ),
        )

        del self.memory_cache[lru_key]
        logger.debug(f"清理LRU缓存条目: {lru_key}")

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        cache_key = self._generate_key(key)
        deleted = False

        # 删除内存缓存
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]
            deleted = True

        # 删除文件缓存
        if self.config.enable_file_cache:
            file_path = self.cache_dir / f"{cache_key}.cache"
            if file_path.exists():
                file_path.unlink()
                deleted = True

        return deleted

    async def clear(self) -> None:
        """清空所有缓存"""
        # 清空内存缓存
        self.memory_cache.clear()

        # 清空文件缓存
        if self.config.enable_file_cache and self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.warning(f"删除缓存文件失败 {cache_file}: {e}")

        logger.info("缓存已清空")

    async def cleanup_expired(self) -> None:
        """清理过期缓存"""
        # 清理内存缓存
        expired_keys = [
            key for key, entry in self.memory_cache.items() if entry.is_expired()
        ]

        for key in expired_keys:
            del self.memory_cache[key]

        # 清理文件缓存
        if self.config.enable_file_cache and self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        cache_data = pickle.load(f)

                    created_at = cache_data.get("created_at")
                    ttl = cache_data.get("ttl")

                    if ttl and datetime.now() > created_at + timedelta(seconds=ttl):
                        cache_file.unlink()

                except Exception as e:
                    logger.warning(f"清理缓存文件失败 {cache_file}: {e}")

        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存条目")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        file_count = 0
        if self.config.enable_file_cache and self.cache_dir.exists():
            file_count = len(list(self.cache_dir.glob("*.cache")))

        return {
            "memory_cache_size": len(self.memory_cache),
            "file_cache_size": file_count,
            "memory_cache_limit": self.config.max_memory_size,
            "cache_dir": str(self.cache_dir),
            "total_access_count": sum(
                entry.access_count for entry in self.memory_cache.values()
            ),
        }
