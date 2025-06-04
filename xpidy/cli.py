"""
Xpidy 配置驱动的命令行工具
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click

from . import Spider, XpidyConfig
from .utils import URLUtils


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """Xpidy - 配置驱动的智能爬虫工具

    基于"配置即文档"的设计理念，通过配置文件定义爬取任务。
    """
    pass


@cli.command()
@click.argument("config_file")
@click.option("--output", "-o", help="输出文件路径")
@click.option("--dry-run", is_flag=True, help="预览配置而不执行")
def run(config_file: str, output: Optional[str], dry_run: bool):
    """使用配置文件执行爬取任务

    示例配置文件：

    {
      "spider_config": {
        "headless": true,
        "timeout": 30000
      },
      "extraction_config": {
        "enable_text": true,
        "enable_links": true,
        "enable_images": true,
        "text_config": {"min_text_length": 10},
        "links_config": {"max_items": 20}
      },
      "tasks": [
        {
          "url": "https://example.com",
          "name": "example_site"
        }
      ]
    }
    """

    async def run_task():
        try:
            # 读取配置文件
            config_path = Path(config_file)
            if not config_path.exists():
                click.echo(f"❌ 配置文件不存在: {config_file}", err=True)
                sys.exit(1)

            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # 解析配置 - 使用新的统一配置
            try:
                config = XpidyConfig.from_dict(config_data)
            except Exception as e:
                click.echo(f"❌ 配置解析失败: {e}", err=True)
                sys.exit(1)

            tasks = config_data.get("tasks", [])

            if dry_run:
                click.echo("🔍 配置预览:")
                click.echo(f"  爬虫配置: {config.spider_config}")
                click.echo(f"  提取配置: {config.extraction_config}")
                if config.llm_config.enabled:
                    click.echo(f"  LLM配置: {config.llm_config}")
                click.echo(f"  任务数量: {len(tasks)}")
                return

            if not tasks:
                click.echo("❌ 配置文件中没有任务", err=True)
                sys.exit(1)

            # 执行任务
            click.echo(f"🚀 开始执行 {len(tasks)} 个任务")

            async with Spider(config) as spider:
                results = {}

                for i, task in enumerate(tasks, 1):
                    url = task["url"]
                    name = task.get("name", f"task_{i}")

                    try:
                        click.echo(f"📥 ({i}/{len(tasks)}) 处理: {name} - {url}")

                        # 任务级别的配置覆盖
                        task_options = task.get("options", {})
                        prompt = task_options.get("prompt")

                        result = await spider.crawl(url, prompt=prompt)

                        # 判断成功状态
                        success = "error" not in result

                        results[name] = {
                            "url": url,
                            "success": success,
                            "data": result,
                        }

                        if success:
                            click.echo(f"✅ 完成: {name}")
                        else:
                            click.echo(f"⚠️ 部分完成: {name}")

                    except Exception as e:
                        click.echo(f"❌ 失败: {name} - {e}")
                        results[name] = {"url": url, "success": False, "error": str(e)}

                # 保存结果
                if output:
                    with open(output, "w", encoding="utf-8") as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    click.echo(f"✅ 结果已保存到: {output}")
                else:
                    click.echo(json.dumps(results, ensure_ascii=False, indent=2))

                # 显示总结
                successful = sum(1 for r in results.values() if r.get("success", False))
                click.echo(f"\n📊 执行总结: 成功 {successful}/{len(tasks)} 个任务")

        except Exception as e:
            click.echo(f"❌ 执行失败: {e}", err=True)
            sys.exit(1)

    asyncio.run(run_task())


@cli.command()
@click.argument(
    "template_name",
    type=click.Choice(["basic", "links", "images", "comprehensive", "data", "form"]),
)
@click.option("--output", "-o", default="xpidy_config.json", help="配置文件输出路径")
def init(template_name: str, output: str):
    """生成配置文件模板

    可用模板:
    - basic: 基础文本提取
    - links: 链接提取
    - images: 图片提取
    - comprehensive: 全面提取
    - data: 结构化数据提取
    - form: 表单数据提取
    """
    templates = {
        "basic": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "enable_text": True,
                "text_config": {"extract_metadata": True, "min_text_length": 10},
            },
            "tasks": [{"url": "https://example.com", "name": "example_basic"}],
        },
        "links": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "enable_text": True,
                "enable_links": True,
                "links_config": {
                    "include_internal": True,
                    "include_external": True,
                    "max_items": 50,
                },
            },
            "tasks": [{"url": "https://example.com", "name": "example_links"}],
        },
        "images": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "enable_text": True,
                "enable_images": True,
                "images_config": {
                    "min_width": 100,
                    "min_height": 100,
                    "max_items": 20,
                    "allowed_formats": ["jpg", "png", "gif"],
                },
            },
            "tasks": [{"url": "https://example.com", "name": "example_images"}],
        },
        "comprehensive": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "enable_text": True,
                "enable_links": True,
                "enable_images": True,
                "enable_data": True,
                "enable_form": True,
                "text_config": {"extract_metadata": True},
                "links_config": {"max_items": 100},
                "images_config": {"max_items": 30},
                "data_config": {"extract_json_ld": True, "extract_tables": True},
                "form_config": {"extract_input_fields": True},
            },
            "tasks": [
                {"url": "https://example.com", "name": "comprehensive_extraction"}
            ],
        },
        "data": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "enable_text": True,
                "enable_data": True,
                "data_config": {
                    "extract_json_ld": True,
                    "extract_microdata": True,
                    "extract_opengraph": True,
                    "extract_tables": True,
                    "extract_lists": True,
                },
            },
            "tasks": [{"url": "https://example.com", "name": "data_extraction"}],
        },
        "form": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "enable_text": True,
                "enable_form": True,
                "form_config": {
                    "extract_input_fields": True,
                    "extract_buttons": True,
                    "extract_selects": True,
                    "include_hidden_fields": False,
                },
            },
            "tasks": [{"url": "https://example.com", "name": "form_extraction"}],
        },
    }

    template = templates.get(template_name)
    if not template:
        click.echo(f"❌ 未知模板: {template_name}", err=True)
        sys.exit(1)

    # 保存模板
    with open(output, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    click.echo(f"✅ 已生成 {template_name} 配置模板: {output}")
    click.echo(f"🔧 请编辑配置文件后使用: xpidy run {output}")


@cli.command()
@click.argument("config_file")
def validate(config_file: str):
    """验证配置文件"""
    try:
        config_path = Path(config_file)
        if not config_path.exists():
            click.echo(f"❌ 配置文件不存在: {config_file}", err=True)
            sys.exit(1)

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        # 验证配置结构
        errors = []

        try:
            config = XpidyConfig.from_dict(config_data)
        except Exception as e:
            errors.append(f"配置格式错误: {e}")

        # 验证tasks
        tasks = config_data.get("tasks", [])
        if not tasks:
            errors.append("tasks 不能为空")

        for i, task in enumerate(tasks):
            if "url" not in task:
                errors.append(f"任务 {i+1} 缺少 url 字段")
            elif not URLUtils.is_valid_url(task["url"]):
                errors.append(f"任务 {i+1} 的 URL 无效: {task['url']}")

        if errors:
            click.echo("❌ 配置验证失败:")
            for error in errors:
                click.echo(f"  - {error}")
            sys.exit(1)
        else:
            click.echo("✅ 配置文件验证通过")
            click.echo(f"📊 包含 {len(tasks)} 个任务")

            # 显示启用的提取器
            enabled_extractors = []
            if config.extraction_config.enable_text:
                enabled_extractors.append("text")
            if config.extraction_config.enable_links:
                enabled_extractors.append("links")
            if config.extraction_config.enable_images:
                enabled_extractors.append("images")
            if config.extraction_config.enable_data:
                enabled_extractors.append("data")
            if config.extraction_config.enable_form:
                enabled_extractors.append("form")

            click.echo(f"🔧 启用的提取器: {', '.join(enabled_extractors)}")

    except json.JSONDecodeError as e:
        click.echo(f"❌ JSON格式错误: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 验证失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("url")
@click.option("--output", "-o", help="输出文件路径")
@click.option("--enable-links", is_flag=True, help="启用链接提取")
@click.option("--enable-images", is_flag=True, help="启用图片提取")
@click.option("--enable-data", is_flag=True, help="启用数据提取")
def quick(
    url: str,
    output: Optional[str],
    enable_links: bool,
    enable_images: bool,
    enable_data: bool,
):
    """快速爬取单个URL（使用默认配置）"""

    async def run_quick():
        try:
            click.echo(f"🚀 快速爬取: {url}")

            # 创建快速配置
            spider = Spider.quick_create(
                enable_text=True,
                enable_links=enable_links,
                enable_images=enable_images,
                enable_data=enable_data,
            )

            async with spider:
                result = await spider.crawl(url)

            # 判断成功状态
            success = "error" not in result

            output_data = json.dumps(result, ensure_ascii=False, indent=2)

            if output:
                with open(output, "w", encoding="utf-8") as f:
                    f.write(output_data)
                click.echo(f"✅ 结果已保存到: {output}")
            else:
                click.echo(output_data)

            # 显示摘要
            click.echo(f"\n📊 爬取摘要:")
            click.echo(f"  成功: {success}")
            click.echo(f"  提取器: {result.get('extractors_used', [])}")
            click.echo(f"  耗时: {result.get('extraction_time', 0):.2f}秒")

            # 显示各提取器结果统计
            results = result.get("results", {})
            for extractor_name, extractor_result in results.items():
                if (
                    isinstance(extractor_result, dict)
                    and "error" not in extractor_result
                ):
                    if extractor_name == "text":
                        content_length = len(extractor_result.get("content", ""))
                        click.echo(f"  文本长度: {content_length}字符")
                    elif extractor_name == "links":
                        link_count = extractor_result.get("total_links", 0)
                        click.echo(f"  链接数量: {link_count}")
                    elif extractor_name == "images":
                        image_count = extractor_result.get("total_images", 0)
                        click.echo(f"  图片数量: {image_count}")
                    elif extractor_name == "data":
                        stats = extractor_result.get("stats", {})
                        click.echo(f"  结构化数据: {stats}")

        except Exception as e:
            click.echo(f"❌ 快速爬取失败: {e}", err=True)
            sys.exit(1)

    asyncio.run(run_quick())


@cli.command()
@click.argument("urls", nargs=-1)
def validate_urls(urls):
    """验证URL的有效性"""
    if not urls:
        click.echo("请提供至少一个URL")
        return

    click.echo("🔍 URL验证结果:")
    for url in urls:
        is_valid = URLUtils.is_valid_url(url)
        normalized = URLUtils.normalize_url(url) if is_valid else "无效URL"
        domain = URLUtils.extract_domain(url) if is_valid else "N/A"

        status = "✅" if is_valid else "❌"
        click.echo(f"{status} {url}")
        click.echo(f"   标准化: {normalized}")
        click.echo(f"   域名: {domain}")
        click.echo()


if __name__ == "__main__":
    cli()
