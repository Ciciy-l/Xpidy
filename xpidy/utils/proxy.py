"""
代理管理器
"""

import asyncio
import random
from enum import Enum
from typing import Dict, List, Optional, Union

import aiohttp
from loguru import logger
from pydantic import BaseModel, field_validator


class ProxyType(str, Enum):
    """代理类型"""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyConfig(BaseModel):
    """代理配置"""

    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 10
    max_retries: int = 3

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("端口号必须在1-65535之间")
        return v

    def to_url(self) -> str:
        """转换为代理URL"""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""

        return f"{self.proxy_type.value}://{auth}{self.host}:{self.port}"

    def to_playwright_proxy(self) -> Dict[str, Union[str, int]]:
        """转换为Playwright代理格式"""
        proxy_dict = {"server": f"{self.host}:{self.port}"}

        if self.username and self.password:
            proxy_dict["username"] = self.username
            proxy_dict["password"] = self.password

        return proxy_dict


class ProxyManager:
    """代理管理器"""

    def __init__(self, proxies: Optional[List[ProxyConfig]] = None):
        self.proxies = proxies or []
        self.working_proxies: List[ProxyConfig] = []
        self.failed_proxies: List[ProxyConfig] = []
        self._current_index = 0

    def add_proxy(self, proxy: ProxyConfig) -> None:
        """添加代理"""
        self.proxies.append(proxy)
        logger.info(f"添加代理: {proxy.host}:{proxy.port}")

    def add_proxies(self, proxies: List[ProxyConfig]) -> None:
        """批量添加代理"""
        self.proxies.extend(proxies)
        logger.info(f"批量添加 {len(proxies)} 个代理")

    def remove_proxy(self, proxy: ProxyConfig) -> bool:
        """移除代理"""
        try:
            self.proxies.remove(proxy)
            if proxy in self.working_proxies:
                self.working_proxies.remove(proxy)
            if proxy in self.failed_proxies:
                self.failed_proxies.remove(proxy)
            return True
        except ValueError:
            return False

    async def test_proxy(
        self, proxy: ProxyConfig, test_url: str = "http://httpbin.org/ip"
    ) -> bool:
        """测试代理是否可用"""
        try:
            proxy_url = proxy.to_url()
            timeout = aiohttp.ClientTimeout(total=proxy.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(test_url, proxy=proxy_url) as response:
                    if response.status == 200:
                        logger.debug(f"代理测试成功: {proxy.host}:{proxy.port}")
                        return True
                    else:
                        logger.warning(
                            f"代理测试失败: {proxy.host}:{proxy.port} - 状态码: {response.status}"
                        )
                        return False

        except Exception as e:
            logger.warning(f"代理测试失败: {proxy.host}:{proxy.port} - {e}")
            return False

    async def test_all_proxies(self, test_url: str = "http://httpbin.org/ip") -> None:
        """测试所有代理"""
        logger.info(f"开始测试 {len(self.proxies)} 个代理")

        # 重置状态
        self.working_proxies.clear()
        self.failed_proxies.clear()

        tasks = []
        for proxy in self.proxies:
            task = self._test_and_categorize_proxy(proxy, test_url)
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(
            f"代理测试完成 - 可用: {len(self.working_proxies)}, 失败: {len(self.failed_proxies)}"
        )

    async def _test_and_categorize_proxy(
        self, proxy: ProxyConfig, test_url: str
    ) -> None:
        """测试并分类代理"""
        is_working = await self.test_proxy(proxy, test_url)
        if is_working:
            self.working_proxies.append(proxy)
        else:
            self.failed_proxies.append(proxy)

    def get_random_proxy(self) -> Optional[ProxyConfig]:
        """获取随机代理"""
        if not self.working_proxies:
            logger.warning("没有可用的代理")
            return None

        return random.choice(self.working_proxies)

    def get_next_proxy(self) -> Optional[ProxyConfig]:
        """获取下一个代理(轮询)"""
        if not self.working_proxies:
            logger.warning("没有可用的代理")
            return None

        proxy = self.working_proxies[self._current_index % len(self.working_proxies)]
        self._current_index += 1
        return proxy

    def mark_proxy_failed(self, proxy: ProxyConfig) -> None:
        """标记代理失败"""
        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)
            self.failed_proxies.append(proxy)
            logger.warning(f"代理已标记为失败: {proxy.host}:{proxy.port}")

    def mark_proxy_working(self, proxy: ProxyConfig) -> None:
        """标记代理正常"""
        if proxy in self.failed_proxies:
            self.failed_proxies.remove(proxy)
            self.working_proxies.append(proxy)
            logger.info(f"代理已恢复正常: {proxy.host}:{proxy.port}")

    async def retry_failed_proxies(
        self, test_url: str = "http://httpbin.org/ip"
    ) -> None:
        """重试失败的代理"""
        if not self.failed_proxies:
            return

        logger.info(f"重试 {len(self.failed_proxies)} 个失败的代理")
        failed_copy = self.failed_proxies.copy()

        for proxy in failed_copy:
            if await self.test_proxy(proxy, test_url):
                self.mark_proxy_working(proxy)

    def get_stats(self) -> Dict[str, int]:
        """获取代理统计信息"""
        return {
            "total_proxies": len(self.proxies),
            "working_proxies": len(self.working_proxies),
            "failed_proxies": len(self.failed_proxies),
            "untested_proxies": len(self.proxies)
            - len(self.working_proxies)
            - len(self.failed_proxies),
        }

    def has_working_proxies(self) -> bool:
        """检查是否有可用代理"""
        return len(self.working_proxies) > 0

    @classmethod
    def from_file(
        cls, file_path: str, proxy_type: ProxyType = ProxyType.HTTP
    ) -> "ProxyManager":
        """从文件加载代理列表"""
        proxies = []

        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # 支持格式: host:port 或 host:port:username:password
                    parts = line.split(":")
                    if len(parts) >= 2:
                        host = parts[0]
                        port = int(parts[1])
                        username = parts[2] if len(parts) > 2 else None
                        password = parts[3] if len(parts) > 3 else None

                        proxy = ProxyConfig(
                            host=host,
                            port=port,
                            proxy_type=proxy_type,
                            username=username,
                            password=password,
                        )
                        proxies.append(proxy)

        except Exception as e:
            logger.error(f"从文件加载代理失败: {e}")

        logger.info(f"从文件加载了 {len(proxies)} 个代理")
        return cls(proxies)

    @classmethod
    def from_list(
        cls, proxy_list: List[str], proxy_type: ProxyType = ProxyType.HTTP
    ) -> "ProxyManager":
        """从代理列表创建管理器"""
        proxies = []

        for proxy_str in proxy_list:
            try:
                # 支持格式: host:port 或 host:port:username:password
                parts = proxy_str.split(":")
                if len(parts) >= 2:
                    host = parts[0]
                    port = int(parts[1])
                    username = parts[2] if len(parts) > 2 else None
                    password = parts[3] if len(parts) > 3 else None

                    proxy = ProxyConfig(
                        host=host,
                        port=port,
                        proxy_type=proxy_type,
                        username=username,
                        password=password,
                    )
                    proxies.append(proxy)

            except Exception as e:
                logger.warning(f"解析代理失败 {proxy_str}: {e}")

        return cls(proxies)
