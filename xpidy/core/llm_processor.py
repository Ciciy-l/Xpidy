"""
LLM 数据处理模块
"""

import asyncio
import json
import hashlib
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import aiohttp
from jinja2 import Template
from loguru import logger

from .config import LLMConfig, LLMProvider
from ..utils.cache import CacheManager, CacheConfig


class LLMStats:
    """LLM调用统计"""
    
    def __init__(self):
        self.api_calls = 0
        self.cache_hits = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.response_times = []
        self.daily_cost = 0.0
        self.daily_reset_time = datetime.now().date()
        self.errors = 0
        self.successful_calls = 0
    
    async def record_api_call(self, tokens: int, response_time: float, cost: float, success: bool = True):
        """记录API调用"""
        self.api_calls += 1
        self.total_tokens += tokens
        self.total_cost += cost
        self.response_times.append(response_time)
        
        # 重置每日成本
        current_date = datetime.now().date()
        if current_date != self.daily_reset_time:
            self.daily_cost = 0.0
            self.daily_reset_time = current_date
        
        self.daily_cost += cost
        
        if success:
            self.successful_calls += 1
        else:
            self.errors += 1
    
    def record_cache_hit(self):
        """记录缓存命中"""
        self.cache_hits += 1
    
    def check_daily_limit(self, max_daily_cost: float) -> bool:
        """检查是否超过每日成本限制"""
        return self.daily_cost >= max_daily_cost
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_requests = self.api_calls + self.cache_hits
        return {
            "api_calls": self.api_calls,
            "cache_hits": self.cache_hits,
            "total_requests": total_requests,
            "cache_hit_rate": self.cache_hits / max(total_requests, 1),
            "success_rate": self.successful_calls / max(self.api_calls, 1),
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "daily_cost": self.daily_cost,
            "avg_response_time": sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            "errors": self.errors
        }


class ContentProcessor:
    """内容处理工具类"""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        # 简单估算：中文约1字符=1token，英文约1.3字符=1token
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return chinese_chars + int(other_chars / 1.3)
    
    @staticmethod
    def smart_truncate(content: str, max_tokens: int, extraction_type: str = "text") -> str:
        """智能截断内容"""
        current_tokens = ContentProcessor.estimate_tokens(content)
        if current_tokens <= max_tokens:
            return content
        
        # 计算截断比例
        ratio = max_tokens / current_tokens * 0.9  # 保留10%余量
        target_length = int(len(content) * ratio)
        
        if extraction_type == "structured":
            # 结构化提取：尝试保留HTML结构
            return ContentProcessor._truncate_preserve_structure(content, target_length)
        else:
            # 文本提取：保留开头和结尾
            return ContentProcessor._truncate_head_tail(content, target_length)
    
    @staticmethod
    def _truncate_preserve_structure(content: str, target_length: int) -> str:
        """保留结构的截断"""
        if len(content) <= target_length:
            return content
        
        # 尝试在HTML标签边界截断
        truncated = content[:target_length]
        
        # 查找最后一个完整的标签
        last_tag_end = truncated.rfind('>')
        if last_tag_end > target_length * 0.8:  # 如果截断点不太远
            return truncated[:last_tag_end + 1]
        
        return truncated
    
    @staticmethod
    def _truncate_head_tail(content: str, target_length: int) -> str:
        """头尾截断"""
        if len(content) <= target_length:
            return content
        
        # 80%开头，20%结尾
        head_length = int(target_length * 0.8)
        tail_length = target_length - head_length - 20  # 预留连接符空间
        
        head = content[:head_length]
        tail = content[-tail_length:] if tail_length > 0 else ""
        
        return f"{head}\n\n... [内容已截断] ...\n\n{tail}"
    
    @staticmethod
    def generate_cache_key(content: str, prompt_name: str, template_vars: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 组合所有影响结果的因素
        key_components = [content, prompt_name, str(sorted(template_vars.items()))]
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.rate_limiter = asyncio.Semaphore(config.max_concurrent_requests)

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
    
    async def generate_with_retry(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """带重试的生成"""
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                async with self.rate_limiter:
                    start_time = time.time()
                    result = await self.generate(prompt, system_prompt)
                    response_time = time.time() - start_time
                    
                    # 估算成本
                    tokens = ContentProcessor.estimate_tokens(prompt + (result or ""))
                    cost = tokens * self.config.cost_per_token
                    
                    return result, response_time, tokens, cost
                    
            except Exception as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    # 指数退避
                    wait_time = min(2 ** attempt * self.config.request_interval, 60)
                    logger.warning(f"LLM调用失败，{wait_time:.1f}秒后重试 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                break
        
        # 降级策略
        logger.error(f"LLM调用最终失败，使用降级策略: {last_exception}")
        fallback_result = self._fallback_processing(prompt)
        return fallback_result, 0.0, 0, 0.0
    
    def _fallback_processing(self, prompt: str) -> str:
        """降级处理"""
        if self.config.fallback_strategy == "original":
            # 尝试从prompt中提取原始内容
            content_match = re.search(r'内容[：:](.+?)(?:\n\n|请|JSON|$)', prompt, re.DOTALL)
            if content_match:
                return content_match.group(1).strip()
            return prompt[:1000]  # 返回prompt前1000字符
        elif self.config.fallback_strategy == "simple":
            # 简单的文本清理
            content_match = re.search(r'内容[：:](.+?)(?:\n\n|请|JSON|$)', prompt, re.DOTALL)
            if content_match:
                content = content_match.group(1).strip()
                # 简单清理HTML标签
                clean_content = re.sub(r'<[^>]+>', '', content)
                clean_content = re.sub(r'\s+', ' ', clean_content)
                return clean_content.strip()
            return ""
        else:  # none
            return ""


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
        # 使用重试机制处理每个prompt
        tasks = []
        for prompt in prompts:
            task = self.generate_with_retry(prompt, system_prompt)
            tasks.append(task)
        
        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 提取文本结果
        text_results = []
        for result in results:
            if isinstance(result, Exception):
                text_results.append(self._fallback_processing(str(result)))
            elif isinstance(result, tuple):
                # 从 (result, response_time, tokens, cost) 中提取结果
                text_results.append(result[0])
            else:
                text_results.append(str(result))
        
        return text_results


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
        # 使用重试机制处理每个prompt
        tasks = []
        for prompt in prompts:
            task = self.generate_with_retry(prompt, system_prompt)
            tasks.append(task)
        
        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 提取文本结果
        text_results = []
        for result in results:
            if isinstance(result, Exception):
                text_results.append(self._fallback_processing(str(result)))
            elif isinstance(result, tuple):
                # 从 (result, response_time, tokens, cost) 中提取结果
                text_results.append(result[0])
            else:
                text_results.append(str(result))
        
        return text_results


class LLMProcessor:
    """LLM 数据处理器"""

    # 增强的内置提示词模板
    BUILT_IN_PROMPTS = {
        "extract_text": """
你是一个专业的网页内容提取专家。请从以下网页内容中提取主要文本信息。

要求：
1. 去除HTML标签和无关信息（如导航、广告、版权声明等）
2. 保留重要的段落结构和换行
3. 提取核心内容，保持原始语义
4. 如果内容为空或无意义，返回空字符串

示例：
输入：<div><h1>新闻标题</h1><p>这是新闻内容。</p><nav>导航菜单</nav><footer>版权信息</footer></div>
输出：新闻标题

这是新闻内容。

内容：
{content}

请只返回整理后的纯文本内容：
        """.strip(),
        
        "extract_data": """
你是一个数据结构化专家。请从以下网页内容中提取结构化数据。

要求：
1. 以JSON格式返回数据
2. 包含标题、正文内容、链接等关键信息
3. 如果某项信息不存在，设为null
4. 确保JSON格式正确，不要包含其他文本

内容：
{content}

请以JSON格式返回提取的数据：
        """.strip(),
        
        "summarize": """
你是一个内容总结专家。请对以下内容进行专业总结。

要求：
1. 提取核心观点和关键信息
2. 保持原始内容的主要意思
3. 语言简洁明了，逻辑清晰
4. 总结长度控制在原文的20-30%

内容：
{content}

请提供简洁明了的总结：
        """.strip(),
        
        "classify": """
你是一个内容分类专家。请对以下内容进行分类分析。

要求：
1. 判断内容的主要类别（如：新闻、博客、产品页面、学术文章等）
2. 提供分类的置信度（0-1之间）
3. 简要说明分类依据

内容：
{content}

请返回内容的类别、置信度和分类依据：
        """.strip(),
        
        "extract_structured_data": """
你是一个专业的数据提取专家。请严格按照给定的JSON模式从内容中提取结构化数据。

重要规则：
1. 严格遵循提供的JSON模式
2. 如果某个字段在内容中找不到对应信息，设为null
3. 确保数据类型与模式定义完全一致
4. 不要添加模式中未定义的字段
5. 只返回JSON格式的数据，不要包含任何其他文本

JSON模式：
{schema}

内容：
{content}

JSON结果：
        """.strip()
    }

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = self._create_client()
        
        # 合并内置和自定义提示词
        self.prompts = {**self.BUILT_IN_PROMPTS, **config.custom_prompts}
        
        # 初始化缓存
        self.cache = None
        if config.enable_cache:
            cache_config = CacheConfig(
                cache_dir=".llm_cache",
                default_ttl=config.cache_ttl,
                max_memory_size=200,
                enable_file_cache=True,
                enable_memory_cache=True
            )
            self.cache = CacheManager(cache_config)
        
        # 初始化统计
        self.stats = LLMStats() if config.enable_stats else None

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
            # 检查每日成本限制
            if self.stats and self.stats.check_daily_limit(self.config.max_daily_cost):
                logger.warning("已达到每日成本限制，使用降级策略")
                return self.client._fallback_processing(content)
            
            # 内容预处理
            processed_content = await self._preprocess_content(content)
            
            # 选择提示词
            if custom_prompt:
                prompt_template = custom_prompt
            elif prompt_name in self.prompts:
                prompt_template = self.prompts[prompt_name]
            else:
                raise ValueError(f"未找到提示词: {prompt_name}")

            # 生成缓存键
            cache_key = None
            if self.cache:
                cache_key = ContentProcessor.generate_cache_key(
                    processed_content, prompt_name, template_vars
                )
                
                # 检查缓存
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    if self.stats:
                        self.stats.record_cache_hit()
                    logger.info(f"命中LLM缓存，内容长度: {len(processed_content)}")
                    return cached_result

            # 渲染提示词模板
            template = Template(prompt_template)
            prompt = template.render(content=processed_content, **template_vars)

            # 调用 LLM
            result, response_time, tokens, cost = await self.client.generate_with_retry(prompt)
            
            # 记录统计
            if self.stats:
                await self.stats.record_api_call(tokens, response_time, cost, success=bool(result))
            
            # 缓存结果
            if self.cache and cache_key and result:
                await self.cache.set(cache_key, result)

            logger.info(
                f"LLM 处理完成，输入长度: {len(processed_content)}, 输出长度: {len(result)}, "
                f"耗时: {response_time:.2f}s, 成本: ${cost:.4f}"
            )
            return result

        except Exception as e:
            logger.error(f"LLM 处理失败: {e}")
            if self.stats:
                await self.stats.record_api_call(0, 0, 0, success=False)
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

            # 预编译模板
            template = Template(prompt_template)
            
            # 预处理所有内容
            processed_contents = []
            cache_keys = []
            cached_results = {}
            
            for i, content in enumerate(contents):
                processed_content = await self._preprocess_content(content)
                processed_contents.append(processed_content)
                
                # 检查缓存
                if self.cache:
                    cache_key = ContentProcessor.generate_cache_key(
                        processed_content, prompt_name, template_vars
                    )
                    cache_keys.append(cache_key)
                    
                    cached_result = await self.cache.get(cache_key)
                    if cached_result:
                        cached_results[i] = cached_result
                        if self.stats:
                            self.stats.record_cache_hit()

            # 处理未缓存的内容
            uncached_indices = [i for i in range(len(contents)) if i not in cached_results]
            results = [""] * len(contents)
            
            # 填充缓存结果
            for i, result in cached_results.items():
                results[i] = result
            
            if uncached_indices:
                # 分批处理未缓存的内容
                batch_size = self.config.batch_size
                
                for batch_start in range(0, len(uncached_indices), batch_size):
                    batch_indices = uncached_indices[batch_start:batch_start + batch_size]
                    
                    # 渲染提示词
                    prompts = []
                    for i in batch_indices:
                        prompt = template.render(content=processed_contents[i], **template_vars)
                        prompts.append(prompt)
                    
                    # 批量调用 LLM
                    batch_results = await self.client.generate_batch(prompts)
                    
                    # 处理结果
                    for j, result in enumerate(batch_results):
                        original_index = batch_indices[j]
                        
                        if isinstance(result, Exception):
                            logger.error(f"批处理中第 {original_index} 项失败: {result}")
                            result = self.client._fallback_processing(prompts[j])
                        
                        results[original_index] = result
                        
                        # 缓存结果
                        if self.cache and cache_keys[original_index] and result:
                            await self.cache.set(cache_keys[original_index], result)
                    
                    # 智能延迟
                    if batch_start + batch_size < len(uncached_indices):
                        await asyncio.sleep(self.config.request_interval)

            logger.info(f"批量 LLM 处理完成，处理了 {len(contents)} 个内容，缓存命中 {len(cached_results)} 个")
            return results

        except Exception as e:
            logger.error(f"批量 LLM 处理失败: {e}")
            raise

    async def extract_structured_data(
        self, content: str, schema: Dict[str, Any], custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """提取结构化数据"""
        for attempt in range(self.config.max_json_retries):
            try:
                # 构建结构化提示词
                if custom_prompt:
                    prompt_template = custom_prompt
                else:
                    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
                    prompt_template = self.prompts["extract_structured_data"].format(schema=schema_str)

                # 处理内容
                result = await self.process(
                    content, 
                    custom_prompt=prompt_template,
                    schema=schema_str,
                    extraction_type="structured"
                )

                # 鲁棒JSON解析
                parsed_data = self._robust_json_parse(result, schema)
                return parsed_data

            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"JSON解析失败 (尝试 {attempt + 1}/{self.config.max_json_retries}): {e}")
                
                if attempt < self.config.max_json_retries - 1:
                    # 增强提示词，要求更严格的JSON格式
                    custom_prompt = self._enhance_json_prompt(prompt_template, str(e))
                    continue
                else:
                    # 最后尝试失败，返回基础结构
                    logger.error("JSON解析最终失败，返回基础结构")
                    return self._create_fallback_json(schema)

        # 这里不应该到达，但为了安全
        return self._create_fallback_json(schema)

    async def _preprocess_content(self, content: str) -> str:
        """预处理内容"""
        if not content:
            return ""
        
        # 内容截断
        if self.config.enable_content_truncation:
            max_tokens = self.config.max_input_tokens
            if ContentProcessor.estimate_tokens(content) > max_tokens:
                content = ContentProcessor.smart_truncate(content, max_tokens)
        
        # 基础清理
        content = re.sub(r'\s+', ' ', content.strip())
        
        return content

    def _robust_json_parse(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """鲁棒的JSON解析"""
        # 1. 直接解析
        try:
            parsed = json.loads(text.strip())
            if self._validate_schema_structure(parsed, schema):
                return parsed
        except json.JSONDecodeError:
            pass

        # 2. 提取JSON代码块
        json_blocks = re.findall(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
        for block in json_blocks:
            try:
                parsed = json.loads(block)
                if self._validate_schema_structure(parsed, schema):
                    return parsed
            except json.JSONDecodeError:
                continue

        # 3. 更智能的正则匹配
        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
        for match in json_matches:
            try:
                parsed = json.loads(match)
                if self._validate_schema_structure(parsed, schema):
                    return parsed
            except json.JSONDecodeError:
                continue

        # 4. 尝试修复常见JSON错误
        return self._attempt_json_repair(text, schema)

    def _validate_schema_structure(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """验证数据结构是否符合schema"""
        if not isinstance(data, dict):
            return False
        
        # 检查必需的属性
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        for field in required:
            if field not in data:
                return False
        
        return True

    def _attempt_json_repair(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """尝试修复JSON"""
        try:
            # 尝试修复常见问题：
            # 1. 移除多余的文本
            cleaned = re.sub(r'^[^{]*(\{.*\})[^}]*$', r'\1', text, flags=re.DOTALL)
            
            # 2. 修复未闭合的引号
            cleaned = re.sub(r'(["\'])\s*\n\s*(["\'])', r'\1, \2', cleaned)
            
            # 3. 修复尾随逗号
            cleaned = re.sub(r',\s*}', '}', cleaned)
            cleaned = re.sub(r',\s*]', ']', cleaned)
            
            return json.loads(cleaned)
        except:
            # 修复失败，返回基础结构
            return self._create_fallback_json(schema)

    def _create_fallback_json(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """创建符合schema的基础JSON结构"""
        result = {}
        properties = schema.get("properties", {})
        
        for field, field_schema in properties.items():
            field_type = field_schema.get("type", "string")
            if field_type == "string":
                result[field] = ""
            elif field_type == "number":
                result[field] = 0
            elif field_type == "boolean":
                result[field] = False
            elif field_type == "array":
                result[field] = []
            elif field_type == "object":
                result[field] = {}
            else:
                result[field] = None
        
        return result

    def _enhance_json_prompt(self, original_prompt: str, error_msg: str) -> str:
        """增强JSON提示词"""
        enhancement = f"""

特别注意：上次解析出现错误 "{error_msg}"，请确保：
1. 返回完整的JSON对象，以{{开始，以}}结束
2. 所有字符串值都用双引号包围
3. 不要有尾随逗号
4. 确保JSON格式完全正确
5. 只返回JSON，不要包含任何其他文本或解释

"""
        return original_prompt + enhancement

    def add_custom_prompt(self, name: str, template: str) -> None:
        """添加自定义提示词"""
        self.prompts[name] = template
        logger.info(f"添加自定义提示词: {name}")

    def get_available_prompts(self) -> List[str]:
        """获取可用的提示词列表"""
        return list(self.prompts.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self.stats:
            return self.stats.get_stats()
        return {}
    
    async def cleanup_cache(self) -> None:
        """清理过期缓存"""
        if self.cache:
            await self.cache.cleanup_expired()
            logger.info("LLM缓存清理完成")
