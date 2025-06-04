"""
结构化数据提取器
"""

import json
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page
from pydantic import Field

from ..core.config import ExtractionConfig
from ..core.llm_processor import LLMProcessor
from .base_extractor import BaseExtractor, BaseExtractorConfig


class DataExtractorConfig(BaseExtractorConfig):
    """数据提取器配置"""

    # 结构化数据提取
    extract_json_ld: bool = Field(default=True, description="提取JSON-LD数据")
    extract_microdata: bool = Field(default=True, description="提取微数据")
    extract_opengraph: bool = Field(default=True, description="提取OpenGraph数据")
    extract_twitter_cards: bool = Field(default=True, description="提取Twitter卡片数据")
    extract_meta_tags: bool = Field(default=True, description="提取META标签")

    # 表格数据提取
    extract_tables: bool = Field(default=False, description="提取表格数据")
    min_table_rows: int = Field(default=2, description="表格最少行数")
    min_table_cols: int = Field(default=2, description="表格最少列数")
    include_empty_cells: bool = Field(default=False, description="包含空单元格")

    # 列表数据提取
    extract_lists: bool = Field(default=False, description="提取列表数据")
    min_list_items: int = Field(default=2, description="列表最少项目数")
    list_selectors: List[str] = Field(
        default_factory=lambda: ["ul", "ol"], description="列表选择器"
    )

    # 自定义数据提取
    custom_selectors: Dict[str, str] = Field(
        default_factory=dict, description="自定义选择器映射"
    )
    custom_attributes: List[str] = Field(
        default_factory=list, description="提取的自定义属性"
    )


class DataExtractor(BaseExtractor):
    """结构化数据提取器"""

    def __init__(
        self,
        config: Optional[DataExtractorConfig] = None,
        llm_processor: Optional[LLMProcessor] = None,
    ):
        super().__init__(config)
        self.llm_processor = llm_processor

    @classmethod
    def get_default_config(cls) -> DataExtractorConfig:
        """获取默认配置"""
        return DataExtractorConfig()

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
            if self.config.extract_json_ld:
                result["json_ld"] = await self._extract_json_ld(page)

            # 尝试提取 Schema.org 微数据
            if self.config.extract_microdata:
                result["microdata"] = await self._extract_microdata(page)

            # 提取 OpenGraph 数据
            if self.config.extract_opengraph:
                result["opengraph"] = await self._extract_opengraph(page)

            # 提取 Twitter 卡片数据
            if self.config.extract_twitter_cards:
                result["twitter_cards"] = await self._extract_twitter_cards(page)

            # 提取 META 标签
            if self.config.extract_meta_tags:
                result["meta_tags"] = await self._extract_meta_tags(page)

            # 提取表格数据
            if self.config.extract_tables:
                result["tables"] = await self._extract_tables(page)

            # 提取列表数据
            if self.config.extract_lists:
                result["lists"] = await self._extract_lists(page)

            # 自定义选择器提取
            if self.config.custom_selectors:
                result["custom_data"] = await self._extract_custom_data(page)

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
                            } else if (prop.tagName === 'A') {
                                value = prop.href || prop.textContent || '';
                            } else if (prop.tagName === 'IMG') {
                                value = prop.src || prop.alt || '';
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

    async def _extract_opengraph(self, page: Page) -> Dict[str, Any]:
        """提取 OpenGraph 数据"""
        try:
            og_data = await page.evaluate(
                """
                () => {
                    const ogTags = document.querySelectorAll('meta[property^="og:"]');
                    const data = {};
                    
                    ogTags.forEach(tag => {
                        const property = tag.getAttribute('property');
                        const content = tag.getAttribute('content');
                        if (property && content) {
                            const key = property.replace('og:', '');
                            data[key] = content;
                        }
                    });
                    
                    return data;
                }
            """
            )
            return og_data or {}
        except Exception:
            return {}

    async def _extract_twitter_cards(self, page: Page) -> Dict[str, Any]:
        """提取 Twitter 卡片数据"""
        try:
            twitter_data = await page.evaluate(
                """
                () => {
                    const twitterTags = document.querySelectorAll('meta[name^="twitter:"]');
                    const data = {};
                    
                    twitterTags.forEach(tag => {
                        const name = tag.getAttribute('name');
                        const content = tag.getAttribute('content');
                        if (name && content) {
                            const key = name.replace('twitter:', '');
                            data[key] = content;
                        }
                    });
                    
                    return data;
                }
            """
            )
            return twitter_data or {}
        except Exception:
            return {}

    async def _extract_meta_tags(self, page: Page) -> Dict[str, Any]:
        """提取 META 标签"""
        try:
            meta_data = await page.evaluate(
                """
                () => {
                    const metaTags = document.querySelectorAll('meta');
                    const data = {};
                    
                    metaTags.forEach(tag => {
                        const name = tag.getAttribute('name') || tag.getAttribute('property') || tag.getAttribute('http-equiv');
                        const content = tag.getAttribute('content');
                        if (name && content) {
                            data[name] = content;
                        }
                    });
                    
                    return data;
                }
            """
            )
            return meta_data or {}
        except Exception:
            return {}

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

    async def _extract_tables(self, page: Page) -> List[Dict[str, Any]]:
        """提取表格数据"""
        try:
            tables = await page.evaluate(
                f"""
                () => {{
                    const tables = Array.from(document.querySelectorAll('table'));
                    return tables.map((table, index) => {{
                        const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent?.trim() || '');
                        const rows = Array.from(table.querySelectorAll('tr')).slice(headers.length > 0 ? 1 : 0).map(tr => {{
                            return Array.from(tr.querySelectorAll('td, th')).map(cell => cell.textContent?.trim() || '');
                        }});
                        
                        // 过滤空行和不符合条件的表格
                        const filteredRows = rows.filter(row => 
                            row.length >= {self.config.min_table_cols} && 
                            ({self.config.include_empty_cells.lower()} || row.some(cell => cell.length > 0))
                        );
                        
                        if (filteredRows.length >= {self.config.min_table_rows}) {{
                            return {{
                                index: index,
                                headers: headers,
                                rows: filteredRows,
                                rowCount: filteredRows.length,
                                colCount: headers.length || (filteredRows[0] ? filteredRows[0].length : 0),
                                id: table.id || '',
                                className: table.className || ''
                            }};
                        }}
                        return null;
                    }}).filter(table => table !== null);
                }}
            """
            )
            return tables or []
        except Exception:
            return []

    async def _extract_lists(self, page: Page) -> List[Dict[str, Any]]:
        """提取列表数据"""
        try:
            selectors = ", ".join(self.config.list_selectors)
            lists = await page.evaluate(
                f"""
                () => {{
                    const lists = Array.from(document.querySelectorAll('{selectors}'));
                    return lists.map((list, index) => {{
                        const items = Array.from(list.querySelectorAll('li')).map(li => li.textContent?.trim() || '');
                        const filteredItems = items.filter(item => item.length > 0);
                        
                        if (filteredItems.length >= {self.config.min_list_items}) {{
                            return {{
                                index: index,
                                type: list.tagName.toLowerCase(),
                                items: filteredItems,
                                itemCount: filteredItems.length,
                                id: list.id || '',
                                className: list.className || ''
                            }};
                        }}
                        return null;
                    }}).filter(list => list !== null);
                }}
            """
            )
            return lists or []
        except Exception:
            return []

    async def _extract_custom_data(self, page: Page) -> Dict[str, Any]:
        """提取自定义选择器数据"""
        custom_data = {}

        for name, selector in self.config.custom_selectors.items():
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    if len(elements) == 1:
                        text = await elements[0].text_content()
                        custom_data[name] = await self._clean_text(text or "")
                    else:
                        texts = []
                        for element in elements:
                            text = await element.text_content()
                            if text:
                                texts.append(await self._clean_text(text))
                        custom_data[name] = texts
                else:
                    custom_data[name] = None
            except Exception:
                custom_data[name] = None

        return custom_data

    def _generate_extraction_stats(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """生成提取统计信息"""
        stats = {}

        if "json_ld" in result:
            stats["json_ld_count"] = len(result["json_ld"])

        if "microdata" in result:
            stats["microdata_count"] = len(result["microdata"])

        if "tables" in result:
            stats["table_count"] = len(result["tables"])
            stats["total_table_rows"] = sum(
                table.get("rowCount", 0) for table in result["tables"]
            )

        if "lists" in result:
            stats["list_count"] = len(result["lists"])
            stats["total_list_items"] = sum(
                lst.get("itemCount", 0) for lst in result["lists"]
            )

        if "opengraph" in result:
            stats["opengraph_properties"] = len(result["opengraph"])

        if "twitter_cards" in result:
            stats["twitter_properties"] = len(result["twitter_cards"])

        if "meta_tags" in result:
            stats["meta_tag_count"] = len(result["meta_tags"])

        return stats

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器"""
        # 表格行数过滤
        if filters.get("min_rows") and item.get("rowCount", 0) < filters["min_rows"]:
            return False

        # 列表项目数过滤
        if filters.get("min_items") and item.get("itemCount", 0) < filters["min_items"]:
            return False

        return True
