"""
表单数据提取器
"""

import time
from typing import Any, Dict, List, Optional

from playwright.async_api import Page
from pydantic import Field

from .base_extractor import BaseExtractor, BaseExtractorConfig


class FormExtractorConfig(BaseExtractorConfig):
    """表单提取器配置"""

    # 提取内容配置
    extract_input_fields: bool = Field(default=True, description="提取输入字段")
    extract_buttons: bool = Field(default=True, description="提取按钮")
    extract_selects: bool = Field(default=True, description="提取下拉选择框")
    extract_textareas: bool = Field(default=True, description="提取文本域")
    extract_labels: bool = Field(default=True, description="提取标签信息")

    # 过滤配置
    include_hidden_fields: bool = Field(default=False, description="包含隐藏字段")
    include_disabled_fields: bool = Field(default=False, description="包含禁用字段")
    min_fields_count: int = Field(default=1, description="表单最少字段数")

    # 表单识别配置
    form_selectors: List[str] = Field(
        default_factory=lambda: ["form"], description="表单选择器"
    )
    ignore_empty_forms: bool = Field(default=True, description="忽略空表单")


class FormExtractor(BaseExtractor):
    """表单数据提取器"""

    def __init__(self, config: Optional[FormExtractorConfig] = None):
        super().__init__(config)

    @classmethod
    def get_default_config(cls) -> FormExtractorConfig:
        """获取默认配置"""
        return FormExtractorConfig()

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取表单数据"""
        current_url = page.url

        # 获取提取范围
        extraction_scopes = await self._get_extraction_scope(page)

        all_forms = []
        for scope in extraction_scopes:
            scope_forms = await self._extract_forms_from_scope(scope, current_url)
            all_forms.extend(scope_forms)

        # 过滤和处理表单
        filtered_forms = self._filter_and_deduplicate_items(
            all_forms, current_url, url_key="action"
        )

        # 提取其他表单元素
        result = {
            "url": current_url,
            "forms": filtered_forms,
            "form_count": len(filtered_forms),
            "timestamp": time.time(),
            "extraction_method": "form_extractor",
        }

        # 如果配置了提取独立字段，也提取页面中所有表单元素
        if any(
            [
                self.config.extract_input_fields,
                self.config.extract_buttons,
                self.config.extract_selects,
                self.config.extract_textareas,
            ]
        ):
            standalone_elements = await self._extract_standalone_elements(page)
            result.update(standalone_elements)

        return result

    async def _extract_forms_from_scope(
        self, scope, base_url: str
    ) -> List[Dict[str, Any]]:
        """从指定范围提取表单"""
        try:
            if hasattr(scope, "query_selector_all"):
                # 页面或元素
                forms_data = await scope.evaluate(
                    """
                    () => {
                        const forms = document.querySelectorAll('form');
                        return Array.from(forms).map((form, index) => {
                            const inputs = form.querySelectorAll('input, select, textarea');
                            const buttons = form.querySelectorAll('button, input[type="submit"], input[type="button"], input[type="reset"]');
                            
                            return {
                                index: index,
                                id: form.id || '',
                                name: form.name || '',
                                action: form.action || '',
                                method: form.method || 'get',
                                enctype: form.enctype || 'application/x-www-form-urlencoded',
                                target: form.target || '',
                                class_name: form.className || '',
                                input_count: inputs.length,
                                button_count: buttons.length,
                                inputs: Array.from(inputs).map(input => ({
                                    type: input.type || input.tagName.toLowerCase(),
                                    name: input.name || '',
                                    id: input.id || '',
                                    placeholder: input.placeholder || '',
                                    required: input.required || false,
                                    disabled: input.disabled || false,
                                    readonly: input.readOnly || false,
                                    value: input.value || '',
                                    class_name: input.className || '',
                                    maxlength: input.maxLength || null,
                                    minlength: input.minLength || null,
                                    pattern: input.pattern || '',
                                    label: (() => {
                                        let label = '';
                                        if (input.id) {
                                            const labelElement = document.querySelector(`label[for="${input.id}"]`);
                                            if (labelElement) {
                                                label = labelElement.textContent?.trim() || '';
                                            }
                                        }
                                        if (!label) {
                                            const parentLabel = input.closest('label');
                                            if (parentLabel) {
                                                label = parentLabel.textContent?.trim() || '';
                                            }
                                        }
                                        return label;
                                    })()
                                })),
                                buttons: Array.from(buttons).map(button => ({
                                    type: button.type || '',
                                    text: button.textContent?.trim() || button.value || '',
                                    value: button.value || '',
                                    name: button.name || '',
                                    id: button.id || '',
                                    disabled: button.disabled || false,
                                    class_name: button.className || ''
                                }))
                            };
                        });
                    }
                """
                )
            else:
                # 元素句柄
                forms_data = await scope.evaluate(
                    """
                    (element) => {
                        const forms = element.querySelectorAll('form');
                        return Array.from(forms).map((form, index) => {
                            // 同样的逻辑...
                            return {
                                index: index,
                                id: form.id || '',
                                name: form.name || '',
                                action: form.action || '',
                                method: form.method || 'get',
                                // 简化版本，可以扩展
                            };
                        });
                    }
                """
                )

            processed_forms = []
            for form_data in forms_data or []:
                processed_form = await self._process_form(form_data, base_url)
                if processed_form:
                    processed_forms.append(processed_form)

            return processed_forms

        except Exception:
            return []

    async def _process_form(
        self, form_data: Dict[str, Any], base_url: str
    ) -> Optional[Dict[str, Any]]:
        """处理单个表单"""
        # 过滤空表单
        if self.config.ignore_empty_forms and form_data.get("input_count", 0) == 0:
            return None

        # 最少字段数过滤
        if form_data.get("input_count", 0) < self.config.min_fields_count:
            return None

        # 处理action URL
        action = form_data.get("action", "")
        if action:
            from urllib.parse import urljoin

            form_data["action"] = urljoin(base_url, action)
            form_data["is_external_action"] = not action.startswith(base_url)

        # 过滤字段
        if not self.config.include_hidden_fields:
            form_data["inputs"] = [
                inp
                for inp in form_data.get("inputs", [])
                if inp.get("type", "") != "hidden"
            ]

        if not self.config.include_disabled_fields:
            form_data["inputs"] = [
                inp
                for inp in form_data.get("inputs", [])
                if not inp.get("disabled", False)
            ]

        # 分类字段
        form_data["field_types"] = self._categorize_fields(form_data.get("inputs", []))

        return form_data

    def _categorize_fields(self, inputs: List[Dict[str, Any]]) -> Dict[str, int]:
        """分类字段类型"""
        categories = {}
        for inp in inputs:
            field_type = inp.get("type", "text")
            categories[field_type] = categories.get(field_type, 0) + 1
        return categories

    async def _extract_standalone_elements(self, page: Page) -> Dict[str, Any]:
        """提取独立的表单元素（不在form标签内的）"""
        result = {}

        if self.config.extract_input_fields:
            result["standalone_inputs"] = await self._extract_standalone_inputs(page)

        if self.config.extract_buttons:
            result["standalone_buttons"] = await self._extract_standalone_buttons(page)

        if self.config.extract_selects:
            result["standalone_selects"] = await self._extract_standalone_selects(page)

        if self.config.extract_textareas:
            result["standalone_textareas"] = await self._extract_standalone_textareas(
                page
            )

        return result

    async def _extract_standalone_inputs(self, page: Page) -> List[Dict[str, Any]]:
        """提取独立的输入字段"""
        try:
            inputs_data = await page.evaluate(
                """
                () => {
                    const inputs = document.querySelectorAll('input:not(form input)');
                    return Array.from(inputs).map(input => ({
                        type: input.type || 'text',
                        name: input.name || '',
                        id: input.id || '',
                        placeholder: input.placeholder || '',
                        value: input.value || '',
                        required: input.required || false,
                        disabled: input.disabled || false,
                        readonly: input.readOnly || false,
                        class_name: input.className || ''
                    }));
                }
            """
            )
            return inputs_data or []
        except Exception:
            return []

    async def _extract_standalone_buttons(self, page: Page) -> List[Dict[str, Any]]:
        """提取独立的按钮"""
        try:
            buttons_data = await page.evaluate(
                """
                () => {
                    const buttons = document.querySelectorAll('button:not(form button), input[type="button"]:not(form input)');
                    return Array.from(buttons).map(button => ({
                        type: button.type || '',
                        text: button.textContent?.trim() || button.value || '',
                        value: button.value || '',
                        name: button.name || '',
                        id: button.id || '',
                        disabled: button.disabled || false,
                        class_name: button.className || ''
                    }));
                }
            """
            )
            return buttons_data or []
        except Exception:
            return []

    async def _extract_standalone_selects(self, page: Page) -> List[Dict[str, Any]]:
        """提取独立的下拉选择框"""
        try:
            selects_data = await page.evaluate(
                """
                () => {
                    const selects = document.querySelectorAll('select:not(form select)');
                    return Array.from(selects).map(select => {
                        const options = select.querySelectorAll('option');
                        return {
                            name: select.name || '',
                            id: select.id || '',
                            multiple: select.multiple || false,
                            required: select.required || false,
                            disabled: select.disabled || false,
                            class_name: select.className || '',
                            options: Array.from(options).map(option => ({
                                text: option.textContent?.trim() || '',
                                value: option.value || '',
                                selected: option.selected || false,
                                disabled: option.disabled || false
                            }))
                        };
                    });
                }
            """
            )
            return selects_data or []
        except Exception:
            return []

    async def _extract_standalone_textareas(self, page: Page) -> List[Dict[str, Any]]:
        """提取独立的文本域"""
        try:
            textareas_data = await page.evaluate(
                """
                () => {
                    const textareas = document.querySelectorAll('textarea:not(form textarea)');
                    return Array.from(textareas).map(textarea => ({
                        name: textarea.name || '',
                        id: textarea.id || '',
                        placeholder: textarea.placeholder || '',
                        value: textarea.value || '',
                        required: textarea.required || false,
                        disabled: textarea.disabled || false,
                        readonly: textarea.readOnly || false,
                        rows: textarea.rows || null,
                        cols: textarea.cols || null,
                        class_name: textarea.className || ''
                    }));
                }
            """
            )
            return textareas_data or []
        except Exception:
            return []

    def _apply_custom_filters(self, item: Dict[str, Any], **filters) -> bool:
        """应用自定义过滤器"""
        # 表单字段数过滤
        if filters.get("min_field_count"):
            if item.get("input_count", 0) < filters["min_field_count"]:
                return False

        # 表单方法过滤
        if filters.get("allowed_methods"):
            method = item.get("method", "get").lower()
            if method not in [m.lower() for m in filters["allowed_methods"]]:
                return False

        return True

    async def fill_form(
        self,
        page: Page,
        form_data: Dict[str, str],
        form_selector: str = "form",
        submit: bool = False,
    ) -> Dict[str, Any]:
        """填写表单（保持向后兼容）"""
        try:
            result = {
                "success": False,
                "filled_fields": [],
                "errors": [],
                "submitted": False,
            }

            # 查找表单
            form_element = await page.query_selector(form_selector)
            if not form_element:
                result["errors"].append(f"未找到表单: {form_selector}")
                return result

            # 填写字段
            for field_name, value in form_data.items():
                try:
                    # 尝试多种选择器
                    selectors = [
                        f'input[name="{field_name}"]',
                        f'select[name="{field_name}"]',
                        f'textarea[name="{field_name}"]',
                        f"#{field_name}",
                        f'input[id="{field_name}"]',
                    ]

                    field_filled = False
                    for selector in selectors:
                        field_element = await page.query_selector(selector)
                        if field_element:
                            # 检查字段类型
                            field_type = await field_element.get_attribute("type")
                            tag_name = await field_element.evaluate(
                                "el => el.tagName.toLowerCase()"
                            )

                            if tag_name == "select":
                                await field_element.select_option(value)
                            elif field_type in ["checkbox", "radio"]:
                                if str(value).lower() in ["true", "1", "yes", "on"]:
                                    await field_element.check()
                                else:
                                    await field_element.uncheck()
                            else:
                                await field_element.fill(str(value))

                            result["filled_fields"].append(
                                {
                                    "name": field_name,
                                    "value": value,
                                    "selector": selector,
                                    "type": field_type or tag_name,
                                }
                            )
                            field_filled = True
                            break

                    if not field_filled:
                        result["errors"].append(f"未找到字段: {field_name}")

                except Exception as e:
                    result["errors"].append(f"填写字段 {field_name} 失败: {e}")

            # 提交表单
            if submit and len(result["errors"]) == 0:
                try:
                    # 查找提交按钮
                    submit_selectors = [
                        'input[type="submit"]',
                        'button[type="submit"]',
                        "button:not([type])",  # 默认type是submit
                    ]

                    submit_button = None
                    for selector in submit_selectors:
                        submit_button = await form_element.query_selector(selector)
                        if submit_button:
                            break

                    if submit_button:
                        await submit_button.click()
                        result["submitted"] = True
                    else:
                        # 如果没有找到提交按钮，尝试提交表单
                        await form_element.evaluate("form => form.submit()")
                        result["submitted"] = True

                except Exception as e:
                    result["errors"].append(f"表单提交失败: {e}")

            result["success"] = len(result["errors"]) == 0
            return result

        except Exception as e:
            return {
                "success": False,
                "filled_fields": [],
                "errors": [str(e)],
                "submitted": False,
            }
