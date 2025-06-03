#!/usr/bin/env python3
"""
Xpidy 高级用法示例
展示选择器、XPath、配置优化等高级功能
"""

import asyncio

from xpidy import ExtractionConfig, Spider, SpiderConfig


async def advanced_selectors():
    """高级选择器使用"""
    print("🎯 高级选择器示例")
    print("-" * 40)

    async with Spider() as spider:
        # 复杂的CSS选择器
        css_selectors = {
            "title": "title, h1",
            "meta_description": "meta[name='description']",
            "all_headings": "h1, h2, h3, h4, h5, h6",
            "navigation_links": "nav a, header a, .nav a",
            "content_paragraphs": "main p, article p, .content p",
            "external_links": "a[href^='http']:not([href*='example.com'])",
            "images_with_alt": "img[alt]",
            "form_inputs": "input[type], textarea, select",
        }

        result = await spider.extract_with_selectors(
            "https://example.com", css_selectors
        )

        print("CSS选择器提取结果:")
        for field, data in result.structured_data.items():
            if data:
                if isinstance(data, list):
                    print(f"  {field}: 找到 {len(data)} 个元素")
                    # 显示前几个元素的预览
                    if len(data) > 0:
                        preview = (
                            str(data[0])[:30] + "..."
                            if len(str(data[0])) > 30
                            else str(data[0])
                        )
                        print(f"    示例: {preview}")
                else:
                    preview = (
                        str(data)[:50] + "..." if len(str(data)) > 50 else str(data)
                    )
                    print(f"  {field}: {preview}")
            else:
                print(f"  {field}: 未找到")


async def xpath_extraction():
    """XPath 提取示例"""
    print("\n🔍 XPath 提取示例")
    print("-" * 40)

    async with Spider() as spider:
        # XPath 选择器
        xpaths = {
            "page_title": "//title/text()",
            "all_text_nodes": "//text()[normalize-space()]",
            "link_urls": "//a/@href",
            "link_texts": "//a/text()",
            "image_sources": "//img/@src",
            "meta_keywords": "//meta[@name='keywords']/@content",
            "all_headings": "//h1 | //h2 | //h3",
            "paragraph_count": "count(//p)",
            "first_paragraph": "(//p)[1]/text()",
        }

        result = await spider.extract_with_xpath("https://example.com", xpaths)

        print("XPath提取结果:")
        for field, data in result.structured_data.items():
            if data:
                if isinstance(data, list):
                    print(f"  {field}: {len(data)} 个结果")
                    if field == "all_text_nodes" and len(data) > 5:
                        print(f"    前5个: {[str(t)[:20] + '...' for t in data[:5]]}")
                    elif len(data) <= 3:
                        print(f"    内容: {data}")
                else:
                    print(f"  {field}: {data}")
            else:
                print(f"  {field}: 未找到")


async def custom_configuration():
    """自定义配置示例"""
    print("\n⚙️ 自定义配置示例")
    print("-" * 40)

    # 高度自定义的提取配置
    config = ExtractionConfig(
        # 基础提取
        extract_text=True,
        extract_links=True,
        extract_images=True,
        extract_metadata=True,
        extract_structured_data=True,
        # 链接配置
        max_links=30,
        extract_internal_links=True,
        extract_external_links=True,
        link_filters=["*.pdf", "*.doc", "*.zip"],
        # 图片配置
        max_images=20,
        min_image_width=50,
        min_image_height=50,
        image_formats=["jpg", "jpeg", "png", "gif", "webp"],
        # 内容处理
        remove_scripts=True,
        remove_styles=True,
        normalize_whitespace=True,
    )

    # 自定义爬虫配置
    spider_config = SpiderConfig(
        browser_type="chromium",
        headless=True,
        stealth_mode=True,
        timeout=20000,
        random_delay=True,
        min_delay=0.5,
        max_delay=1.5,
        max_retries=2,
    )

    async with Spider(config, spider_config) as spider:
        result = await spider.crawl("https://httpbin.org/html")

        print(f"配置化提取结果:")
        print(f"  页面: {result.url}")
        print(f"  成功: {result.success}")
        print(f"  内容: {result.content_length} 字符")
        print(f"  链接: {result.total_links} 个")
        print(f"  图片: {result.total_images} 张")

        # 详细统计
        stats = result.get_detailed_stats()
        print(f"  详细统计:")
        for key, value in stats.items():
            print(f"    {key}: {value}")


async def error_handling_and_retries():
    """错误处理和重试机制"""
    print("\n🔄 错误处理和重试")
    print("-" * 40)

    # 配置重试机制
    spider_config = SpiderConfig(
        timeout=5000, max_retries=3, random_delay=False  # 短超时时间，容易触发重试
    )

    # 测试URL列表（包含一些可能失败的URL）
    test_urls = [
        "https://example.com",
        "https://httpbin.org/delay/10",  # 延迟10秒，可能超时
        "https://httpbin.org/status/404",  # 404错误
        "https://invalid-domain-12345.com",  # 无效域名
        "https://httpbin.org/html",
    ]

    config = ExtractionConfig(extract_text=True, extract_metadata=True)

    async with Spider(config, spider_config) as spider:
        results = await spider.crawl_batch(test_urls, max_concurrent=2)

        success_count = 0
        for i, result in enumerate(results):
            url = test_urls[i]
            if result.success:
                success_count += 1
                print(f"✅ {url}")
                print(f"   内容: {result.content_length} 字符")
            else:
                print(f"❌ {url}")
                print(f"   错误: {result.error}")

        print(f"\n统计: {success_count}/{len(test_urls)} 成功")


async def performance_comparison():
    """性能对比测试"""
    print("\n⚡ 性能对比测试")
    print("-" * 40)

    urls = ["https://example.com", "https://httpbin.org/html"]

    # 测试不同配置的性能差异
    configs = [
        ("基础配置", ExtractionConfig(extract_text=True)),
        (
            "完整配置",
            ExtractionConfig(
                extract_text=True,
                extract_links=True,
                extract_images=True,
                extract_metadata=True,
                max_links=20,
                max_images=10,
            ),
        ),
        ("最小配置", ExtractionConfig(extract_metadata=True)),
    ]

    import time

    for config_name, config in configs:
        start_time = time.time()

        async with Spider(extraction_config=config) as spider:
            results = await spider.crawl_batch(urls, max_concurrent=2)

        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.success)
        total_content = sum(r.content_length for r in results if r.success)

        print(f"{config_name}:")
        print(f"  时间: {duration:.2f}秒")
        print(f"  成功: {success_count}/{len(urls)}")
        print(f"  内容: {total_content} 字符")
        print(f"  速度: {total_content/duration:.0f} 字符/秒")


async def data_filtering_and_processing():
    """数据过滤和处理"""
    print("\n🔧 数据过滤和处理")
    print("-" * 40)

    config = ExtractionConfig(
        extract_text=True,
        extract_links=True,
        extract_images=True,
        max_links=50,
        max_images=20,
    )

    async with Spider(extraction_config=config) as spider:
        result = await spider.crawl("https://httpbin.org/html")

        if result.success:
            print(f"原始数据:")
            print(f"  总链接: {result.total_links}")
            print(f"  总图片: {result.total_images}")

            # 使用便捷方法过滤数据
            if result.has_links:
                internal_links = result.get_internal_links()
                external_links = result.get_external_links()

                print(f"\n链接分析:")
                print(f"  内部链接: {len(internal_links)}")
                print(f"  外部链接: {len(external_links)}")

                # 显示链接详情
                if internal_links:
                    print(f"  内部链接示例: {internal_links[0]['url']}")
                if external_links:
                    print(f"  外部链接示例: {external_links[0]['url']}")

            if result.has_images:
                large_images = result.get_large_images(min_width=100, min_height=100)
                small_images = [
                    img
                    for img in result.images
                    if img.get("width", 0) < 100 or img.get("height", 0) < 100
                ]

                print(f"\n图片分析:")
                print(f"  大图片: {len(large_images)}")
                print(f"  小图片: {len(small_images)}")

                # 按格式分类
                jpg_images = result.get_images_by_format("jpg")
                png_images = result.get_images_by_format("png")
                print(f"  JPG格式: {len(jpg_images)}")
                print(f"  PNG格式: {len(png_images)}")


async def result_analysis():
    """结果分析和统计"""
    print("\n📊 结果分析和统计")
    print("-" * 40)

    config = ExtractionConfig(
        extract_text=True,
        extract_links=True,
        extract_images=True,
        extract_metadata=True,
    )

    async with Spider(extraction_config=config) as spider:
        result = await spider.crawl("https://httpbin.org/html")

        if result.success:
            # 基本统计
            print(f"基本信息:")
            print(f"  URL: {result.url}")
            print(f"  时间戳: {result.timestamp}")
            print(f"  内容长度: {result.content_length}")
            print(f"  词数: {result.word_count}")

            # 提取器状态
            print(f"\n提取器状态:")
            print(f"  启用: {result.enabled_extractors}")
            print(f"  成功: {result.successful_extractors}")
            print(f"  失败: {result.failed_extractors}")

            # 获取摘要
            summary = result.get_summary()
            print(f"\n页面摘要:")
            for key, value in summary.items():
                print(f"  {key}: {value}")

            # 详细统计
            detailed_stats = result.get_detailed_stats()
            print(f"\n详细统计:")
            for category, stats in detailed_stats.items():
                print(f"  {category}:")
                if isinstance(stats, dict):
                    for key, value in stats.items():
                        print(f"    {key}: {value}")
                else:
                    print(f"    {stats}")


async def main():
    """运行所有高级用法示例"""
    print("🚀 Xpidy 高级用法演示")
    print("=" * 50)

    try:
        await advanced_selectors()
        await xpath_extraction()
        await custom_configuration()
        await error_handling_and_retries()
        await performance_comparison()
        await data_filtering_and_processing()
        await result_analysis()

        print("\n🎊 所有高级用法演示完成！")
        print("\n🎯 本示例展示了以下高级特性:")
        print("   - 复杂CSS选择器和XPath")
        print("   - 详细的配置自定义")
        print("   - 错误处理和重试机制")
        print("   - 性能优化和对比")
        print("   - 数据过滤和处理")
        print("   - 结果分析和统计")

    except Exception as e:
        print(f"❌ 高级用法演示失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
