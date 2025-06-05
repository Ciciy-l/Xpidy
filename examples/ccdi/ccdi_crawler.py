#!/usr/bin/env python3
"""
中央纪委监察委网站爬虫示例
使用Xpidy内置并发功能，简洁高效地爬取违纪处分案例
"""

import asyncio
import csv
import re
import time
from typing import Any, Dict, List

from xpidy import ExtractionConfig, Spider, SpiderConfig, XpidyConfig


async def main():
    """主函数：爬取中纪委违纪处分案例"""

    # 🎯 目标页面
    urls = [
        "https://www.ccdi.gov.cn/scdcn/sggb/djcf/",  # 省管干部违纪处分
        "https://www.ccdi.gov.cn/scdcn/zyyj/djcf/",  # 中央一级违纪处分
        "https://www.ccdi.gov.cn/scdcn/zggb/djcf/",  # 中管干部违纪处分
    ]

    # ⚙️ 配置爬虫
    config = XpidyConfig(
        spider_config=SpiderConfig(
            headless=True,
            timeout=30000,
            delay=1.0,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ),
        extraction_config=ExtractionConfig(
            enable_text=True,
            enable_links=True,
            enable_data=False,
            # 专门提取li元素内容
            global_selectors=["li"],
            global_exclude_selectors=["nav", "header", "footer"],
            text_config={
                "content_selectors": ["li", "li a", "li span"],
                "min_text_length": 5,
                "remove_scripts": True,
                "remove_styles": True,
            },
            links_config={
                "extract_internal_links": True,
                "extract_external_links": False,
                "include_link_text": True,
                "deduplicate": True,
                "filter_patterns": [r"\.html$", r"\.shtml$"],
                "base_domain": "ccdi.gov.cn",
            },
        ),
    )

    print("🚀 开始爬取中央纪委监察委网站...")
    print(f"📝 目标页面: {len(urls)} 个")
    print("⚡ 使用Xpidy内置并发功能\n")

    start_time = time.time()

    # 🔥 核心代码：一行实现并发爬取
    async with Spider(config) as spider:
        results = await spider.crawl_multiple_urls(
            urls=urls,
            max_concurrent=3,  # 最大并发数
            delay_between_batches=0.5,  # 批次间延迟
        )

    end_time = time.time()

    # 📊 处理结果
    all_cases = []
    for result in results:
        if "error" not in result:
            page_type = get_page_type(result["url"])
            cases = extract_cases_from_result(result)

            for case in cases:
                case["页面类型"] = page_type
                all_cases.append(case)

    # 💾 保存为CSV
    save_to_csv(all_cases, "ccdi_cases.csv")

    # 📈 显示统计
    print_summary(results, all_cases, end_time - start_time)


def get_page_type(url: str) -> str:
    """根据URL判断页面类型"""
    if "sggb" in url:
        return "省管干部违纪处分"
    elif "zyyj" in url:
        return "中央一级违纪处分"
    elif "zggb" in url:
        return "中管干部违纪处分"
    else:
        return "未知类型"


def extract_cases_from_result(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """从爬取结果中提取案例信息"""
    cases = []

    # 获取文本内容和链接
    text_content = result.get("results", {}).get("text", {}).get("content", "")
    links_data = result.get("results", {}).get("links", {}).get("links", [])

    if not text_content:
        return cases

    # 创建链接映射
    link_map = {}
    for link in links_data:
        if link.get("text") and link.get("url"):
            link_url = link["url"]
            link_text = link["text"].strip()

            # 扩大链接范围：包含更多类型的链接
            if any(
                pattern in link_url
                for pattern in ["yaowenn", "scdcn", "toutiao", "djcf"]
            ):
                full_url = (
                    f"https://www.ccdi.gov.cn{link_url}"
                    if not link_url.startswith("http")
                    else link_url
                )
                link_map[link_text] = full_url

    # 解析文本内容 - 新的解析逻辑
    lines = text_content.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 匹配包含违纪处分关键词的行
        if any(
            keyword in line
            for keyword in ["被开除党籍", '被"双开"', "被取消", "被撤销"]
        ):
            # 尝试从行末提取日期
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})$", line)
            if date_match:
                date = date_match.group(1)
                # 移除日期部分得到标题
                title = line[: date_match.start()].strip()

                if title:  # 确保标题不为空
                    name = extract_name_from_title(title)

                    # 查找匹配的链接 - 改进匹配算法
                    link = ""
                    best_match_score = 0

                    for link_text, link_url in link_map.items():
                        match_score = 0

                        # 1. 完全匹配标题
                        if title == link_text:
                            match_score = 100
                        # 2. 标题包含链接文本
                        elif link_text in title:
                            match_score = 80
                        # 3. 链接文本包含标题
                        elif title in link_text:
                            match_score = 70
                        # 4. 人名匹配
                        elif name != "未知" and name in link_text:
                            match_score = 60
                        # 5. 关键词匹配（违纪、开除等）
                        elif any(
                            keyword in link_text for keyword in ["违纪", "开除", "党籍"]
                        ):
                            # 检查是否有共同的关键词
                            title_words = set(title.split())
                            link_words = set(link_text.split())
                            common_words = title_words & link_words
                            if len(common_words) >= 2:  # 至少2个共同词
                                match_score = 40

                        # 更新最佳匹配
                        if match_score > best_match_score:
                            best_match_score = match_score
                            link = link_url

                    # 如果没有找到好的匹配，尝试模糊匹配
                    if best_match_score < 40:
                        for link_text, link_url in link_map.items():
                            # 检查是否包含相同的中文姓名
                            if name != "未知" and len(name) >= 2:
                                if name in link_text:
                                    link = link_url
                                    break

                    case = {"标题": title, "时间": date, "人名": name, "链接": link}
                    cases.append(case)

    return cases


def extract_name_from_title(title: str) -> str:
    """从标题中提取人名 - 匹配最后一个职务到严重/被之间的内容"""

    # 职务词汇列表（按长度排序，长的优先匹配）
    job_titles = [
        "总法律顾问",
        "(主持工作)",
        "总会计师",
        "党组成员",
        "总工程师",
        "总经济师",
        "总审计师",
        "总规划师",
        "总设计师",
        "总指挥",
        "总编辑",
        "总裁判",
        "秘书长",
        "检察长",
        "总经理",
        "董事长",
        "巡视员",
        "督察员",
        "特派员",
        "研究员",
        "负责人",
        "监事长",
        "专家",
        "队长",
        "督办",
        "专员",
        "司长",
        "书记",
        "州长",
        "干部",
        "组长",
        "主任",
        "委员",
        "常委",
        "厅长",
        "局长",
        "院长",
        "董事",
        "经理",
        "主席",
        "部长",
        "省长",
        "市长",
        "区长",
        "县长",
        "镇长",
        "处长",
        "科长",
        "秘书",
        "视员",
        "关长",
        "行长",
        "署长",
        "参事",
        "助理",
        "顾问",
        "理事",
        "监事",
        "总裁",
        "总监",
    ]

    # 找到所有职务词汇的位置
    job_positions = []
    for job in job_titles:
        start_pos = 0
        while True:
            pos = title.find(job, start_pos)
            if pos == -1:
                break
            # 检查是否被更长的职务词汇包含
            is_part_of_longer = False
            for longer_job in job_titles:
                if len(longer_job) > len(job) and job in longer_job:
                    # 检查是否存在更长的匹配
                    longer_pos = title.find(
                        longer_job, max(0, pos - len(longer_job) + len(job))
                    )
                    if longer_pos != -1 and longer_pos <= pos < longer_pos + len(
                        longer_job
                    ):
                        is_part_of_longer = True
                        break

            if not is_part_of_longer:
                job_positions.append((pos, pos + len(job), job))
            start_pos = pos + 1

    if not job_positions:
        return "未知"

    # 取最后一个职务的结束位置
    last_job_end = max(job_positions, key=lambda x: x[0])[1]

    # 找到第一个"严重"或"被"的位置
    serious_pos = title.find("严重", last_job_end)
    bei_pos = title.find("被", last_job_end)

    # 取最早出现的位置
    end_pos = float("inf")
    if serious_pos != -1:
        end_pos = min(end_pos, serious_pos)
    if bei_pos != -1:
        end_pos = min(end_pos, bei_pos)

    if end_pos == float("inf"):
        return "未知"

    # 提取职务结束到关键词之间的内容并清理
    content = title[last_job_end:end_pos].strip()

    # 简单清理：去掉可能的标点符号
    content = re.sub(r'[，。、；：！？""' "（）【】《》]", "", content)

    return content if content else "未知"


def save_to_csv(cases: List[Dict[str, str]], filename: str):
    """保存案例到CSV文件"""
    if not cases:
        print("⚠️  没有提取到案例数据")
        return

    with open(filename, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["页面类型", "标题", "时间", "人名", "链接"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cases)

    print(f"💾 数据已保存到: {filename}")


def print_summary(results: List[Dict], cases: List[Dict], total_time: float):
    """打印爬取摘要"""
    success_count = len([r for r in results if "error" not in r])
    total_urls = len(results)

    print("\n" + "=" * 60)
    print("📊 爬取结果摘要")
    print("=" * 60)
    print(f"✅ 成功页面: {success_count}/{total_urls}")
    print(f"📋 提取案例: {len(cases)} 个")
    print(f"⏱️  总耗时: {total_time:.2f} 秒")
    print(f"⚡ 平均速度: {len(results)/total_time:.1f} 页面/秒")

    # 按页面类型统计
    type_stats = {}
    for case in cases:
        page_type = case["页面类型"]
        type_stats[page_type] = type_stats.get(page_type, 0) + 1

    print(f"\n📈 分类统计:")
    for page_type, count in type_stats.items():
        print(f"   {page_type}: {count} 个案例")

    print(f"\n🎉 爬取完成！数据已保存为CSV格式")


if __name__ == "__main__":
    asyncio.run(main())
