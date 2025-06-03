"""
结构化数据提取器
"""

import json
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from ..core.config import ExtractionConfig
from ..core.llm_processor import LLMProcessor
from .base_extractor import BaseExtractor


class DataExtractor(BaseExtractor):
    """结构化数据提取器"""

    def __init__(
        self, config: ExtractionConfig, llm_processor: Optional[LLMProcessor] = None
    ):
        super().__init__(config)
        self.llm_processor = llm_processor

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取结构化数据"""
        try:
            result = {}

            # 提取基本内容
            content = await self._get_page_content(page)
            result["raw_content"] = content

            # 如果启用结构化输出且配置了输出模式
            if self.config.structured_output and self.config.output_schema:
                if self.llm_processor:
                    try:
                        custom_prompt = kwargs.get("custom_prompt")
                        structured_data = (
                            await self.llm_processor.extract_structured_data(
                                content=content,
                                schema=self.config.output_schema,
                                custom_prompt=custom_prompt,
                            )
                        )
                        result["structured_data"] = structured_data

                    except Exception as e:
                        logger.warning(f"结构化数据提取失败: {e}")
                        result["extraction_error"] = str(e)
                else:
                    logger.warning("启用了结构化输出但未配置 LLM 处理器")

            # 提取其他数据
            if self.config.extract_links:
                result["links"] = await self._extract_links(page)

            if self.config.extract_images:
                result["images"] = await self._extract_images(page)

            if self.config.extract_metadata:
                result["metadata"] = await self._extract_metadata(page)

            # 尝试提取 JSON-LD 结构化数据
            result["json_ld"] = await self._extract_json_ld(page)

            # 尝试提取 Schema.org 微数据
            result["microdata"] = await self._extract_microdata(page)

            # 添加页面信息
            result["url"] = page.url
            result["timestamp"] = __import__("time").time()

            logger.info(f"结构化数据提取完成，URL: {page.url}")
            return result

        except Exception as e:
            logger.error(f"结构化数据提取失败: {e}")
            raise

    async def extract_with_schema(
        self, page: Page, schema: Dict[str, Any], custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """使用指定模式提取结构化数据"""
        if not self.llm_processor:
            raise ValueError("需要配置 LLM 处理器才能使用模式提取")

        try:
            # 获取页面内容
            content = await self._get_page_content(page)

            # 使用 LLM 提取结构化数据
            structured_data = await self.llm_processor.extract_structured_data(
                content=content, schema=schema, custom_prompt=custom_prompt
            )

            result = {
                "structured_data": structured_data,
                "raw_content": content,
                "url": page.url,
                "timestamp": __import__("time").time(),
                "extraction_method": "schema_based",
                "schema": schema,
            }

            logger.info(f"模式化数据提取完成，URL: {page.url}")
            return result

        except Exception as e:
            logger.error(f"模式化数据提取失败: {e}")
            raise

    async def extract_table_data(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取表格数据"""
        try:
            tables = await page.evaluate(
                """
                () => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    return tables.map((table, index) => {
                        const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent?.trim() || '');
                        const rows = Array.from(table.querySelectorAll('tr')).slice(headers.length > 0 ? 1 : 0).map(tr => {
                            return Array.from(tr.querySelectorAll('td, th')).map(cell => cell.textContent?.trim() || '');
                        });
                        
                        return {
                            index: index,
                            headers: headers,
                            rows: rows,
                            rowCount: rows.length,
                            colCount: headers.length || (rows[0] ? rows[0].length : 0)
                        };
                    });
                }
            """
            )

            result = {
                "tables": tables or [],
                "table_count": len(tables or []),
                "url": page.url,
                "timestamp": __import__("time").time(),
                "extraction_method": "table_extraction",
            }

            # 如果启用 LLM 处理
            if self.config.enable_llm_processing and self.llm_processor and tables:
                try:
                    # 将表格数据转换为文本
                    table_text = self._tables_to_text(tables)

                    custom_prompt = kwargs.get("custom_prompt")
                    prompt_name = kwargs.get("prompt_name", "extract_data")
                    template_vars = kwargs.get("template_vars", {})

                    processed_content = await self.llm_processor.process(
                        content=table_text,
                        prompt_name=prompt_name,
                        custom_prompt=custom_prompt,
                        **template_vars,
                    )
                    result["llm_processed"] = processed_content

                except Exception as e:
                    logger.warning(f"表格 LLM 处理失败: {e}")
                    result["llm_error"] = str(e)

            logger.info(f"表格数据提取完成，找到 {len(tables or [])} 个表格")
            return result

        except Exception as e:
            logger.error(f"表格数据提取失败: {e}")
            raise

    async def extract_form_data(self, page: Page) -> Dict[str, Any]:
        """提取表单数据"""
        try:
            forms = await page.evaluate(
                """
                () => {
                    const forms = Array.from(document.querySelectorAll('form'));
                    return forms.map((form, index) => {
                        const fields = Array.from(form.querySelectorAll('input, select, textarea')).map(field => ({
                            name: field.name || '',
                            type: field.type || field.tagName.toLowerCase(),
                            id: field.id || '',
                            className: field.className || '',
                            placeholder: field.placeholder || '',
                            required: field.required || false,
                            value: field.value || ''
                        }));
                        
                        return {
                            index: index,
                            action: form.action || '',
                            method: form.method || 'get',
                            id: form.id || '',
                            className: form.className || '',
                            fields: fields,
                            fieldCount: fields.length
                        };
                    });
                }
            """
            )

            result = {
                "forms": forms or [],
                "form_count": len(forms or []),
                "url": page.url,
                "timestamp": __import__("time").time(),
                "extraction_method": "form_extraction",
            }

            logger.info(f"表单数据提取完成，找到 {len(forms or [])} 个表单")
            return result

        except Exception as e:
            logger.error(f"表单数据提取失败: {e}")
            raise

    async def _extract_json_ld(self, page: Page) -> List[Dict[str, Any]]:
        """提取 JSON-LD 结构化数据"""
        try:
            json_ld_data = await page.evaluate(
                """
                () => {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    const data = [];
                    scripts.forEach(script => {
                        try {
                            const content = JSON.parse(script.textContent);
                            data.push(content);
                        } catch (e) {
                            // 忽略解析错误
                        }
                    });
                    return data;
                }
            """
            )
            return json_ld_data or []
        except Exception:
            return []

    async def _extract_microdata(self, page: Page) -> List[Dict[str, Any]]:
        """提取 Schema.org 微数据"""
        try:
            microdata = await page.evaluate(
                """
                () => {
                    const items = document.querySelectorAll('[itemscope]');
                    const data = [];
                    
                    items.forEach(item => {
                        const itemType = item.getAttribute('itemtype') || '';
                        const props = {};
                        
                        const propElements = item.querySelectorAll('[itemprop]');
                        propElements.forEach(prop => {
                            const name = prop.getAttribute('itemprop');
                            let value = '';
                            
                            if (prop.tagName === 'META') {
                                value = prop.getAttribute('content') || '';
                            } else if (prop.tagName === 'TIME') {
                                value = prop.getAttribute('datetime') || prop.textContent || '';
                            } else {
                                value = prop.textContent?.trim() || '';
                            }
                            
                            if (name && value) {
                                if (props[name]) {
                                    if (Array.isArray(props[name])) {
                                        props[name].push(value);
                                    } else {
                                        props[name] = [props[name], value];
                                    }
                                } else {
                                    props[name] = value;
                                }
                            }
                        });
                        
                        if (Object.keys(props).length > 0) {
                            data.push({
                                type: itemType,
                                properties: props
                            });
                        }
                    });
                    
                    return data;
                }
            """
            )
            return microdata or []
        except Exception:
            return []

    def _tables_to_text(self, tables: List[Dict[str, Any]]) -> str:
        """将表格数据转换为文本格式"""
        text_parts = []

        for i, table in enumerate(tables):
            text_parts.append(f"表格 {i + 1}:")

            if table.get("headers"):
                text_parts.append(" | ".join(table["headers"]))
                text_parts.append("-" * 50)

            for row in table.get("rows", []):
                text_parts.append(" | ".join(str(cell) for cell in row))

            text_parts.append("")  # 空行分隔

        return "\n".join(text_parts)
