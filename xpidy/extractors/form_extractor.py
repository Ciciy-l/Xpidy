"""
表单数据提取器
"""

from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from ..core.config import ExtractionConfig
from ..core.llm_processor import LLMProcessor
from .base_extractor import BaseExtractor


class FormExtractor(BaseExtractor):
    """表单数据提取器"""

    def __init__(
        self, config: ExtractionConfig, llm_processor: Optional[LLMProcessor] = None
    ):
        super().__init__(config)
        self.llm_processor = llm_processor

    async def extract(self, page: Page, **kwargs) -> Dict[str, Any]:
        """提取表单数据"""
        try:
            result = {
                "forms": [],
                "form_count": 0,
                "input_fields": [],
                "buttons": [],
                "selects": [],
                "textareas": [],
            }

            # 获取所有表单
            forms = await self._extract_forms(page)
            result["forms"] = forms
            result["form_count"] = len(forms)

            # 获取所有输入字段
            result["input_fields"] = await self._extract_input_fields(page)
            result["buttons"] = await self._extract_buttons(page)
            result["selects"] = await self._extract_selects(page)
            result["textareas"] = await self._extract_textareas(page)

            # 添加页面信息
            result["url"] = page.url
            result["timestamp"] = __import__("time").time()

            logger.info(f"表单提取完成，URL: {page.url}, 发现 {len(forms)} 个表单")
            return result

        except Exception as e:
            logger.error(f"表单提取失败: {e}")
            raise

    async def _extract_forms(self, page: Page) -> List[Dict[str, Any]]:
        """提取表单信息"""
        try:
            forms_data = await page.evaluate(
                """
                () => {
                    const forms = document.querySelectorAll('form');
                    return Array.from(forms).map((form, index) => {
                        const inputs = form.querySelectorAll('input, select, textarea');
                        const buttons = form.querySelectorAll('button, input[type="submit"], input[type="button"]');
                        
                        return {
                            index: index,
                            id: form.id || '',
                            name: form.name || '',
                            action: form.action || '',
                            method: form.method || 'get',
                            enctype: form.enctype || '',
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
                                value: input.value || '',
                                class_name: input.className || ''
                            })),
                            buttons: Array.from(buttons).map(button => ({
                                type: button.type || '',
                                text: button.textContent?.trim() || '',
                                value: button.value || '',
                                name: button.name || '',
                                id: button.id || '',
                                class_name: button.className || ''
                            }))
                        };
                    });
                }
            """
            )

            return forms_data or []

        except Exception as e:
            logger.warning(f"表单信息提取失败: {e}")
            return []

    async def _extract_input_fields(self, page: Page) -> List[Dict[str, Any]]:
        """提取输入字段"""
        try:
            inputs_data = await page.evaluate(
                """
                () => {
                    const inputs = document.querySelectorAll('input');
                    return Array.from(inputs).map((input, index) => ({
                        index: index,
                        type: input.type || 'text',
                        name: input.name || '',
                        id: input.id || '',
                        placeholder: input.placeholder || '',
                        value: input.value || '',
                        required: input.required || false,
                        disabled: input.disabled || false,
                        readonly: input.readOnly || false,
                        maxlength: input.maxLength || null,
                        minlength: input.minLength || null,
                        pattern: input.pattern || '',
                        class_name: input.className || '',
                        form_id: input.form?.id || '',
                        label: (() => {
                            // 尝试找到关联的label
                            let label = '';
                            if (input.id) {
                                const labelElement = document.querySelector(`label[for="${input.id}"]`);
                                if (labelElement) {
                                    label = labelElement.textContent?.trim() || '';
                                }
                            }
                            // 如果没有找到，尝试找父级label
                            if (!label) {
                                const parentLabel = input.closest('label');
                                if (parentLabel) {
                                    label = parentLabel.textContent?.trim() || '';
                                }
                            }
                            return label;
                        })()
                    }));
                }
            """
            )

            return inputs_data or []

        except Exception as e:
            logger.warning(f"输入字段提取失败: {e}")
            return []

    async def _extract_buttons(self, page: Page) -> List[Dict[str, Any]]:
        """提取按钮"""
        try:
            buttons_data = await page.evaluate(
                """
                () => {
                    const buttons = document.querySelectorAll('button, input[type="submit"], input[type="button"], input[type="reset"]');
                    return Array.from(buttons).map((button, index) => ({
                        index: index,
                        tag: button.tagName.toLowerCase(),
                        type: button.type || '',
                        text: button.textContent?.trim() || button.value || '',
                        value: button.value || '',
                        name: button.name || '',
                        id: button.id || '',
                        disabled: button.disabled || false,
                        class_name: button.className || '',
                        form_id: button.form?.id || ''
                    }));
                }
            """
            )

            return buttons_data or []

        except Exception as e:
            logger.warning(f"按钮提取失败: {e}")
            return []

    async def _extract_selects(self, page: Page) -> List[Dict[str, Any]]:
        """提取下拉选择框"""
        try:
            selects_data = await page.evaluate(
                """
                () => {
                    const selects = document.querySelectorAll('select');
                    return Array.from(selects).map((select, index) => {
                        const options = select.querySelectorAll('option');
                        return {
                            index: index,
                            name: select.name || '',
                            id: select.id || '',
                            multiple: select.multiple || false,
                            required: select.required || false,
                            disabled: select.disabled || false,
                            size: select.size || 1,
                            class_name: select.className || '',
                            form_id: select.form?.id || '',
                            options: Array.from(options).map(option => ({
                                text: option.textContent?.trim() || '',
                                value: option.value || '',
                                selected: option.selected || false,
                                disabled: option.disabled || false
                            })),
                            selected_values: Array.from(options)
                                .filter(option => option.selected)
                                .map(option => option.value),
                            label: (() => {
                                let label = '';
                                if (select.id) {
                                    const labelElement = document.querySelector(`label[for="${select.id}"]`);
                                    if (labelElement) {
                                        label = labelElement.textContent?.trim() || '';
                                    }
                                }
                                if (!label) {
                                    const parentLabel = select.closest('label');
                                    if (parentLabel) {
                                        label = parentLabel.textContent?.trim() || '';
                                    }
                                }
                                return label;
                            })()
                        };
                    });
                }
            """
            )

            return selects_data or []

        except Exception as e:
            logger.warning(f"下拉选择框提取失败: {e}")
            return []

    async def _extract_textareas(self, page: Page) -> List[Dict[str, Any]]:
        """提取文本域"""
        try:
            textareas_data = await page.evaluate(
                """
                () => {
                    const textareas = document.querySelectorAll('textarea');
                    return Array.from(textareas).map((textarea, index) => ({
                        index: index,
                        name: textarea.name || '',
                        id: textarea.id || '',
                        placeholder: textarea.placeholder || '',
                        value: textarea.value || '',
                        required: textarea.required || false,
                        disabled: textarea.disabled || false,
                        readonly: textarea.readOnly || false,
                        rows: textarea.rows || null,
                        cols: textarea.cols || null,
                        maxlength: textarea.maxLength || null,
                        minlength: textarea.minLength || null,
                        class_name: textarea.className || '',
                        form_id: textarea.form?.id || '',
                        label: (() => {
                            let label = '';
                            if (textarea.id) {
                                const labelElement = document.querySelector(`label[for="${textarea.id}"]`);
                                if (labelElement) {
                                    label = labelElement.textContent?.trim() || '';
                                }
                            }
                            if (!label) {
                                const parentLabel = textarea.closest('label');
                                if (parentLabel) {
                                    label = parentLabel.textContent?.trim() || '';
                                }
                            }
                            return label;
                        })()
                    }));
                }
            """
            )

            return textareas_data or []

        except Exception as e:
            logger.warning(f"文本域提取失败: {e}")
            return []

    async def fill_form(
        self,
        page: Page,
        form_data: Dict[str, str],
        form_selector: str = "form",
        submit: bool = False,
    ) -> Dict[str, Any]:
        """填写表单"""
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
            logger.error(f"表单填写失败: {e}")
            return {
                "success": False,
                "filled_fields": [],
                "errors": [str(e)],
                "submitted": False,
            }
