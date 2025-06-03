"""
Xpidy 配置驱动的命令行工具
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from loguru import logger

from . import (ExtractionConfig, LLMConfig, Spider, SpiderConfig, quick_crawl,
               quick_crawl_batch)
from .utils import ContentUtils, URLUtils


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
        "extract_text": true,
        "extract_links": true,
        "extract_images": true,
        "max_links": 20
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
                config = json.load(f)

            # 解析配置
            spider_config = SpiderConfig(**config.get("spider_config", {}))
            extraction_config = ExtractionConfig(**config.get("extraction_config", {}))
            llm_config = None
            if "llm_config" in config:
                llm_config = LLMConfig(**config["llm_config"])

            tasks = config.get("tasks", [])

            if dry_run:
                click.echo("🔍 配置预览:")
                click.echo(f"  爬虫配置: {spider_config}")
                click.echo(f"  提取配置: {extraction_config}")
                if llm_config:
                    click.echo(f"  LLM配置: {llm_config}")
                click.echo(f"  任务数量: {len(tasks)}")
                return

            if not tasks:
                click.echo("❌ 配置文件中没有任务", err=True)
                sys.exit(1)

            # 执行任务
            click.echo(f"🚀 开始执行 {len(tasks)} 个任务")

            async with Spider(
                spider_config=spider_config,
                extraction_config=extraction_config,
                llm_config=llm_config,
            ) as spider:
                results = {}

                for i, task in enumerate(tasks, 1):
                    url = task["url"]
                    name = task.get("name", f"task_{i}")

                    try:
                        click.echo(f"📥 ({i}/{len(tasks)}) 处理: {name} - {url}")

                        # 任务级别的配置覆盖
                        task_kwargs = task.get("options", {})

                        result = await spider.crawl(url, **task_kwargs)
                        results[name] = {
                            "url": url,
                            "success": result.success,
                            "data": result.to_dict(),
                        }

                        click.echo(f"✅ 完成: {name}")

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
    type=click.Choice(["basic", "links", "images", "comprehensive", "llm"]),
)
@click.option("--output", "-o", default="xpidy_config.json", help="配置文件输出路径")
def init(template_name: str, output: str):
    """生成配置文件模板

    可用模板:
    - basic: 基础文本提取
    - links: 链接提取
    - images: 图片提取
    - comprehensive: 全面提取
    - llm: LLM增强提取
    """
    templates = {
        "basic": {
            "spider_config": {"headless": True, "timeout": 30000, "stealth_mode": True},
            "extraction_config": {"extract_text": True, "extract_metadata": True},
            "tasks": [{"url": "https://example.com", "name": "example_basic"}],
        },
        "links": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "extract_text": True,
                "extract_links": True,
                "extract_internal_links": True,
                "extract_external_links": True,
                "max_links": 50,
            },
            "tasks": [
                {
                    "url": "https://example.com",
                    "name": "example_links",
                    "options": {"deduplicate": True, "include_media": False},
                }
            ],
        },
        "images": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "extract_text": True,
                "extract_images": True,
                "min_image_width": 100,
                "min_image_height": 100,
                "max_images": 20,
                "image_formats": ["jpg", "png", "gif"],
            },
            "tasks": [{"url": "https://example.com", "name": "example_images"}],
        },
        "comprehensive": {
            "spider_config": {"headless": True, "timeout": 30000, "stealth_mode": True},
            "extraction_config": {
                "extract_text": True,
                "extract_links": True,
                "extract_images": True,
                "extract_structured_data": True,
                "extract_tables": True,
                "extract_forms": True,
                "max_links": 100,
                "max_images": 30,
            },
            "tasks": [
                {"url": "https://example.com", "name": "comprehensive_extraction"}
            ],
        },
        "llm": {
            "spider_config": {"headless": True, "timeout": 30000},
            "extraction_config": {
                "extract_text": True,
                "enable_llm_processing": True,
                "structured_output": True,
            },
            "llm_config": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "api_key": "your-api-key-here",
                "temperature": 0.1,
            },
            "tasks": [
                {
                    "url": "https://example.com",
                    "name": "llm_extraction",
                    "options": {
                        "custom_prompt": "提取这个页面的主要信息",
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                                "key_points": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                }
            ],
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
            config = json.load(f)

        # 验证配置结构
        errors = []

        # 验证spider_config
        if "spider_config" in config:
            try:
                SpiderConfig(**config["spider_config"])
            except Exception as e:
                errors.append(f"spider_config 错误: {e}")

        # 验证extraction_config
        if "extraction_config" in config:
            try:
                ExtractionConfig(**config["extraction_config"])
            except Exception as e:
                errors.append(f"extraction_config 错误: {e}")

        # 验证llm_config
        if "llm_config" in config:
            try:
                LLMConfig(**config["llm_config"])
            except Exception as e:
                errors.append(f"llm_config 错误: {e}")

        # 验证tasks
        tasks = config.get("tasks", [])
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

    except json.JSONDecodeError as e:
        click.echo(f"❌ JSON格式错误: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 验证失败: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("url")
@click.option("--output", "-o", help="输出文件路径")
def quick(url: str, output: Optional[str]):
    """快速爬取单个URL（使用默认配置）"""

    async def run_quick():
        try:
            click.echo(f"🚀 快速爬取: {url}")

            result = await quick_crawl(url)

            output_data = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

            if output:
                with open(output, "w", encoding="utf-8") as f:
                    f.write(output_data)
                click.echo(f"✅ 结果已保存到: {output}")
            else:
                click.echo(output_data)

            # 显示摘要
            click.echo(f"\n📊 爬取摘要:")
            click.echo(f"  成功: {result.success}")
            click.echo(f"  内容长度: {result.content_length}")
            if result.has_links:
                click.echo(f"  链接数: {result.total_links}")
            if result.has_images:
                click.echo(f"  图片数: {result.total_images}")

        except Exception as e:
            click.echo(f"❌ 快速爬取失败: {e}", err=True)
            sys.exit(1)

    asyncio.run(run_quick())


# 保留一些实用的工具命令
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
