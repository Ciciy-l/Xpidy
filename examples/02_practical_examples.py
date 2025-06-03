#!/usr/bin/env python3
"""
Xpidy 实用案例示例
展示真实场景中的数据提取应用
"""

import asyncio

from xpidy import ExtractionConfig, Spider, SpiderConfig


async def news_article_extraction():
    """新闻文章提取案例"""
    print("📰 新闻文章提取")
    print("-" * 40)

    config = ExtractionConfig(
        extract_text=True,
        extract_links=True,
        extract_images=True,
        max_links=20,
        max_images=10,
    )

    # 使用自定义爬虫配置
    spider_config = SpiderConfig(headless=True, stealth_mode=True, timeout=15000)

    async with Spider(config, spider_config) as spider:
        # 示例使用 httpbin.org 的 HTML 页面
        result = await spider.crawl("https://httpbin.org/html")

        print(f"文章标题: {result.metadata.title}")
        print(f"文章长度: {result.content_length} 字符")
        print(f"相关链接: {result.total_links} 个")
        print(f"配图数量: {result.total_images} 张")

        # 分析链接类型
        if result.has_links:
            internal = result.get_internal_links()
            external = result.get_external_links()
            print(f"站内链接: {len(internal)} | 站外链接: {len(external)}")


async def e_commerce_product_analysis():
    """电商产品页面分析"""
    print("\n🛒 电商产品分析")
    print("-" * 40)

    config = ExtractionConfig(
        extract_text=True,
        extract_images=True,
        extract_tables=True,
        extract_forms=True,
        min_image_width=100,
        min_image_height=100,
        max_images=15,
    )

    async with Spider(extraction_config=config) as spider:
        result = await spider.crawl("https://example.com")

        print(f"产品页面: {result.url}")
        print(f"页面内容: {result.content_length} 字符")

        # 产品图片分析
        if result.has_images:
            large_images = result.get_large_images(min_width=200, min_height=200)
            jpg_images = result.get_images_by_format("jpg")
            png_images = result.get_images_by_format("png")

            print(f"产品图片: {result.total_images} 张")
            print(f"  高清图片: {len(large_images)} 张")
            print(f"  JPG格式: {len(jpg_images)} 张")
            print(f"  PNG格式: {len(png_images)} 张")

        # 表格和表单分析
        if result.has_tables:
            print(f"规格表格: {len(result.tables)} 个")

        if result.has_forms:
            print(f"购买表单: {len(result.forms)} 个")


async def website_structure_analysis():
    """网站结构分析"""
    print("\n🏗️ 网站结构分析")
    print("-" * 40)

    config = ExtractionConfig(
        extract_text=True,
        extract_links=True,
        extract_structured_data=True,
        max_links=50,
    )

    async with Spider(extraction_config=config) as spider:
        result = await spider.crawl("https://httpbin.org/html")

        print(f"分析网站: {result.url}")
        print(f"页面结构:")
        print(f"  文本内容: {result.content_length} 字符")
        print(f"  总链接数: {result.total_links}")

        # 链接结构分析
        if result.has_links:
            nav_links = result.get_navigation_links()
            content_links = result.get_content_links()

            print(f"  导航链接: {len(nav_links)}")
            print(f"  内容链接: {len(content_links)}")

        # 页面元数据
        print(f"页面元数据:")
        print(f"  标题: {result.metadata.title}")
        print(f"  描述: {result.metadata.description}")
        print(f"  语言: {result.metadata.language}")


async def content_monitoring():
    """内容监控示例"""
    print("\n👁️ 内容监控")
    print("-" * 40)

    # 监控多个页面的变化
    urls = ["https://example.com", "https://httpbin.org/html"]

    config = ExtractionConfig(extract_text=True, extract_metadata=True)

    async with Spider(extraction_config=config) as spider:
        results = await spider.crawl_batch(urls, max_concurrent=3)

        print("监控结果:")
        for result in results:
            if result.success:
                print(f"✅ {result.url}")
                print(f"   内容: {result.content_length} 字符")
                print(f"   更新时间: {result.timestamp}")
            else:
                print(f"❌ {result.url} - 访问失败")


async def data_extraction_with_selectors():
    """使用选择器进行精确数据提取"""
    print("\n🎯 精确数据提取")
    print("-" * 40)

    async with Spider() as spider:
        # 提取特定的页面元素
        selectors = {
            "main_title": "h1, title",
            "navigation": "nav a, .nav a",
            "content_paragraphs": "p",
            "external_links": "a[href^='http']:not([href*='example.com'])",
        }

        result = await spider.extract_with_selectors("https://example.com", selectors)

        print(f"选择器提取结果:")
        for field, data in result.structured_data.items():
            if data:
                if isinstance(data, list):
                    print(f"  {field}: {len(data)} 个元素")
                else:
                    preview = (
                        str(data)[:50] + "..." if len(str(data)) > 50 else str(data)
                    )
                    print(f"  {field}: {preview}")
            else:
                print(f"  {field}: 未找到")


async def performance_optimized_crawling():
    """性能优化的爬取示例"""
    print("\n⚡ 性能优化爬取")
    print("-" * 40)

    # 优化配置：只提取必要的数据
    config = ExtractionConfig(
        extract_text=True,
        extract_links=True,
        max_links=10,  # 限制链接数量
        extract_metadata=True,
    )

    # 优化爬虫配置
    spider_config = SpiderConfig(
        headless=True,
        stealth_mode=False,  # 关闭隐身模式以提高速度
        timeout=10000,  # 较短的超时时间
        random_delay=False,  # 关闭随机延迟
    )

    urls = ["https://example.com", "https://httpbin.org/html"]

    import time

    start_time = time.time()

    async with Spider(config, spider_config) as spider:
        results = await spider.crawl_batch(urls, max_concurrent=5)

    duration = time.time() - start_time

    success_count = sum(1 for r in results if r.success)
    total_content = sum(r.content_length for r in results if r.success)

    print(f"性能统计:")
    print(f"  处理时间: {duration:.2f} 秒")
    print(f"  成功率: {success_count}/{len(urls)}")
    print(f"  总内容: {total_content} 字符")
    print(f"  平均速度: {total_content/duration:.0f} 字符/秒")


async def main():
    """运行所有实用案例"""
    print("🔧 Xpidy 实用案例演示")
    print("=" * 50)

    try:
        await news_article_extraction()
        await e_commerce_product_analysis()
        await website_structure_analysis()
        await content_monitoring()
        await data_extraction_with_selectors()
        await performance_optimized_crawling()

        print("\n🎉 所有实用案例演示完成！")
        print("\n💡 这些案例展示了 Xpidy 在以下场景的应用:")
        print("   - 新闻文章内容提取")
        print("   - 电商产品信息分析")
        print("   - 网站结构分析")
        print("   - 内容变化监控")
        print("   - 精确数据提取")
        print("   - 性能优化策略")

    except Exception as e:
        print(f"❌ 案例运行失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
