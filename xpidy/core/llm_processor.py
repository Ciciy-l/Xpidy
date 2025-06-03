"""
LLM 数据处理模块
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

import aiohttp
from jinja2 import Template
from loguru import logger

from .config import LLMConfig, LLMProvider


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成文本"""
        pass

    @abstractmethod
    async def generate_batch(
        self, prompts: List[str], system_prompt: Optional[str] = None
    ) -> List[str]:
        """批量生成"""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI 客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import openai

            self.client = openai.AsyncOpenAI(
                api_key=config.api_key, base_url=config.base_url
            )
        except ImportError:
            raise ImportError("需要安装 openai 包: uv add openai")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成文本"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        elif self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                timeout=self.config.timeout,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise

    async def generate_batch(
        self, prompts: List[str], system_prompt: Optional[str] = None
    ) -> List[str]:
        """批量生成"""
        tasks = [self.generate(prompt, system_prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)


class AnthropicClient(BaseLLMClient):
    """Anthropic 客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import anthropic

            self.client = anthropic.AsyncAnthropic(
                api_key=config.api_key, base_url=config.base_url
            )
        except ImportError:
            raise ImportError("需要安装 anthropic 包: pip install anthropic")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成文本"""
        try:
            system = system_prompt or self.config.system_prompt or ""

            response = await self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens or 1000,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.config.timeout,
            )

            return response.content[0].text if response.content else ""

        except Exception as e:
            logger.error(f"Anthropic API 调用失败: {e}")
            raise

    async def generate_batch(
        self, prompts: List[str], system_prompt: Optional[str] = None
    ) -> List[str]:
        """批量生成"""
        tasks = [self.generate(prompt, system_prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)


class LLMProcessor:
    """LLM 数据处理器"""

    # 内置提示词模板
    BUILT_IN_PROMPTS = {
        "extract_text": """
请从以下网页内容中提取主要文本信息：

{content}

请只返回整理后的纯文本内容，去除HTML标签和无关信息。
        """.strip(),
        "extract_data": """
请从以下网页内容中提取结构化数据：

{content}

请以JSON格式返回提取的数据，包含标题、内容、链接等信息。
        """.strip(),
        "summarize": """
请对以下内容进行总结：

{content}

请提供简洁明了的总结，突出重点信息。
        """.strip(),
        "classify": """
请对以下内容进行分类：

{content}

请返回内容的类别和置信度。
        """.strip(),
    }

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = self._create_client()

        # 合并内置和自定义提示词
        self.prompts = {**self.BUILT_IN_PROMPTS, **config.custom_prompts}

    def _create_client(self) -> BaseLLMClient:
        """创建 LLM 客户端"""
        if self.config.provider == LLMProvider.OPENAI:
            return OpenAIClient(self.config)
        elif self.config.provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(self.config)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {self.config.provider}")

    async def process(
        self,
        content: str,
        prompt_name: str = "extract_text",
        custom_prompt: Optional[str] = None,
        **template_vars,
    ) -> str:
        """处理单个内容"""
        try:
            # 选择提示词
            if custom_prompt:
                prompt_template = custom_prompt
            elif prompt_name in self.prompts:
                prompt_template = self.prompts[prompt_name]
            else:
                raise ValueError(f"未找到提示词: {prompt_name}")

            # 渲染提示词模板
            template = Template(prompt_template)
            prompt = template.render(content=content, **template_vars)

            # 调用 LLM
            result = await self.client.generate(prompt)

            logger.info(
                f"LLM 处理完成，输入长度: {len(content)}, 输出长度: {len(result)}"
            )
            return result

        except Exception as e:
            logger.error(f"LLM 处理失败: {e}")
            raise

    async def process_batch(
        self,
        contents: List[str],
        prompt_name: str = "extract_text",
        custom_prompt: Optional[str] = None,
        **template_vars,
    ) -> List[str]:
        """批量处理内容"""
        if not contents:
            return []

        try:
            # 选择提示词
            if custom_prompt:
                prompt_template = custom_prompt
            elif prompt_name in self.prompts:
                prompt_template = self.prompts[prompt_name]
            else:
                raise ValueError(f"未找到提示词: {prompt_name}")

            # 分批处理
            results = []
            batch_size = self.config.batch_size

            for i in range(0, len(contents), batch_size):
                batch = contents[i : i + batch_size]

                # 渲染提示词
                template = Template(prompt_template)
                prompts = [
                    template.render(content=content, **template_vars)
                    for content in batch
                ]

                # 批量调用 LLM
                batch_results = await self.client.generate_batch(prompts)
                results.extend(batch_results)

                # 避免请求过快
                if i + batch_size < len(contents):
                    await asyncio.sleep(0.5)

            logger.info(f"批量 LLM 处理完成，处理了 {len(contents)} 个内容")
            return results

        except Exception as e:
            logger.error(f"批量 LLM 处理失败: {e}")
            raise

    async def extract_structured_data(
        self, content: str, schema: Dict[str, Any], custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """提取结构化数据"""
        try:
            # 构建结构化提示词
            if custom_prompt:
                prompt_template = custom_prompt
            else:
                schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
                prompt_template = f"""
请从以下内容中按照给定的 JSON 模式提取结构化数据：

内容：
{{content}}

JSON 模式：
{schema_str}

请严格按照模式返回 JSON 格式的数据，不要包含其他文本。
                """.strip()

            # 处理内容
            result = await self.process(content, custom_prompt=prompt_template)

            # 尝试解析 JSON
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # 如果解析失败，尝试提取 JSON 部分
                import re

                json_match = re.search(r"\{.*\}", result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise ValueError("无法从 LLM 响应中提取有效的 JSON 数据")

        except Exception as e:
            logger.error(f"结构化数据提取失败: {e}")
            raise

    def add_custom_prompt(self, name: str, template: str) -> None:
        """添加自定义提示词"""
        self.prompts[name] = template
        logger.info(f"添加自定义提示词: {name}")

    def get_available_prompts(self) -> List[str]:
        """获取可用的提示词列表"""
        return list(self.prompts.keys())
