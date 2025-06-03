#!/usr/bin/env python3
"""
Xpidy 快速入门示例
展示基本的网页数据提取功能
"""

import asyncio

from xpidy import ExtractionConfig, Spider


async def basic_text_extraction():
    """最简单的文本提取"""
    print("🚀 基本文本提取")
    print("-" * 40)

    config = ExtractionConfig(extract_text=True)

    async with Spider(extraction_config=config) as spider:
        result = await spider.crawl("https://example.com")

        print(f"标题: {result.metadata.title}")
        print(f"内容长度: {result.content_length} 字符")
        print(f"提取成功: {result.text_success}")


async def extract_links_and_images():
    """提取链接和图片"""
    print("\n🔗 链接和图片提取")
    print("-" * 40)

    config = ExtractionConfig(
        extract_text=True,
        extract_links=True,
        extract_images=True,
        max_links=10,
        max_images=5,
    )

    async with Spider(extraction_config=config) as spider:
        result = await spider.crawl("https://httpbin.org/html")

        print(f"页面标题: {result.metadata.title}")
        print(f"文本内容: {result.content_length} 字符")
        print(f"链接总数: {result.total_links}")
        print(f"图片总数: {result.total_images}")

        if result.has_links:
            print(f"内部链接: {len(result.get_internal_links())}")
            print(f"外部链接: {len(result.get_external_links())}")


async def batch_processing():
    """批量处理多个URL"""
    print("\n📦 批量处理")
    print("-" * 40)

    urls = ["https://example.com", "https://httpbin.org/html"]

    config = ExtractionConfig(extract_text=True, extract_links=True)

    async with Spider(extraction_config=config) as spider:
        results = await spider.crawl_batch(urls, max_concurrent=2)

        for i, result in enumerate(results, 1):
            print(f"结果 {i}: {result.url}")
            print(f"  成功: {result.success}")
            print(f"  内容: {result.content_length} 字符")
            print(f"  链接: {result.total_links} 个")


async def using_selectors():
    """使用选择器提取特定数据"""
    print("\n🎯 选择器提取")
    print("-" * 40)

    async with Spider() as spider:
        # CSS选择器
        css_selectors = {"title": "title, h1", "paragraphs": "p", "links": "a[href]"}

        result = await spider.extract_with_selectors(
            "https://example.com", css_selectors
        )

        print(f"提取成功: {result.success}")
        print(f"提取的数据字段: {list(result.structured_data.keys())}")

        # 显示提取的内容
        for key, value in result.structured_data.items():
            if value:
                if isinstance(value, list):
                    print(f"{key}: {len(value)} 个元素")
                else:
                    print(f"{key}: {str(value)[:50]}...")


async def main():
    """主函数，运行所有示例"""
    print("🕷️ Xpidy 快速入门示例")
    print("=" * 50)

    try:
        await basic_text_extraction()
        await extract_links_and_images()
        await batch_processing()
        await using_selectors()

        print("\n✅ 所有示例运行完成！")
        print("\n💡 接下来可以查看更多示例:")
        print("   - 02_practical_examples.py (实用案例)")
        print("   - 03_advanced_usage.py (高级用法)")

    except Exception as e:
        print(f"❌ 示例运行失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
