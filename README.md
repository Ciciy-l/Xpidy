# Xpidy - 智能网页数据提取框架

一个基于Playwright的现代化智能爬虫库，采用"配置驱动"设计理念。

## ✨ 特性

- 🎯 **配置驱动** - 基于配置文件的自动化数据提取
- 🚀 **现代化工具链** - 基于uv包管理器和异步编程
- 🎭 **Playwright驱动** - 支持JavaScript渲染和SPA
- 🧠 **智能提取** - 支持LLM增强的内容理解
- 📋 **多种数据类型** - 文本、链接、图片、表格、表单等
- 🔍 **灵活选择器** - 支持CSS选择器和XPath
- ⚡ **高性能** - 异步并发处理和智能缓存
- 🛡️ **反爬虫** - 内置隐身模式和随机延迟
- 📊 **监控统计** - 实时性能监控和错误追踪
- 🔧 **CLI工具** - 命令行工具支持配置文件模式

## 🚀 快速开始

### 安装

```bash
# 安装uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <repo-url>
cd Xpidy

# 安装依赖
uv sync

# 安装Playwright浏览器
uv run playwright install
```

### CLI使用（推荐）

使用配置文件方式，符合"配置即文档"设计理念：

```bash
# 1. 生成配置模板
xpidy init basic --output my_config.json

# 2. 验证配置文件
xpidy validate my_config.json

# 3. 执行爬取任务
xpidy run my_config.json --output results.json

# 4. 快速爬取单个URL
xpidy quick https://example.com
```

**配置文件示例：**

```json
{
  "spider_config": {
    "headless": true,
    "timeout": 30000,
    "stealth_mode": true
  },
  "extraction_config": {
    "extract_text": true,
    "extract_links": true,
    "extract_images": true,
    "max_links": 50,
    "max_images": 20
  },
  "tasks": [
    {
      "url": "https://example.com",
      "name": "example_site"
    }
  ]
}
```

### 编程接口

```python
import asyncio
from xpidy import Spider, ExtractionConfig

async def main():
    # 1. 定义提取配置（配置即文档）
    config = ExtractionConfig(
        extract_text=True,      # 提取文本内容
        extract_links=True,     # 提取链接
        extract_images=True,    # 提取图片
        max_links=20,          # 最多20个链接
        max_images=10          # 最多10张图片
    )
    
    # 2. 创建爬虫实例
    async with Spider(extraction_config=config) as spider:
        # 3. 一键提取所有配置的数据
        result = await spider.crawl("https://example.com")
        
        # 4. 使用便捷属性访问结果（有IDE智能提示）
        print(f"📰 标题: {result.metadata.title}")
        print(f"📝 内容: {result.content_length} 字符，{result.word_count} 字")
        print(f"🔗 链接: {result.total_links} 个")
        print(f"🖼️ 图片: {result.total_images} 张")
        
        # 5. 使用便捷方法获取特定数据
        if result.has_links:
            internal_links = result.get_internal_links()
            external_links = result.get_external_links()
            print(f"   内部链接: {len(internal_links)} 个")
            print(f"   外部链接: {len(external_links)} 个")
        
        if result.has_images:
            large_images = result.get_large_images()
            jpg_images = result.get_images_by_format('jpg')
            print(f"   大图片: {len(large_images)} 张")
            print(f"   JPG图片: {len(jpg_images)} 张")

asyncio.run(main())
```

## 📚 CLI使用指南

### 配置模板

Xpidy提供多种预设配置模板：

```bash
# 基础文本提取
xpidy init basic

# 链接分析
xpidy init links

# 图片分析
xpidy init images

# 全面数据提取
xpidy init comprehensive

# LLM增强提取
xpidy init llm
```

### 核心CLI命令

```bash
# 生成配置模板
xpidy init <template> [--output config.json]

# 执行配置任务
xpidy run <config_file> [--output results.json] [--dry-run]

# 验证配置文件
xpidy validate <config_file>

# 快速爬取
xpidy quick <url> [--output result.json]

# URL验证工具
xpidy validate-urls <url1> <url2> ...
```

### 配置文件结构

```json
{
  "spider_config": {
    "browser_type": "chromium",
    "headless": true,
    "timeout": 30000,
    "stealth_mode": true,
    "random_delay": true,
    "min_delay": 0.5,
    "max_delay": 2.0,
    "max_retries": 3,
    "user_agent": "custom-ua"
  },
  "extraction_config": {
    "extract_text": true,
    "extract_links": true,
    "extract_images": true,
    "extract_metadata": true,
    "extract_structured_data": true,
    "extract_tables": true,
    "extract_forms": true,
    "max_links": 100,
    "max_images": 50,
    "min_image_width": 50,
    "min_image_height": 50,
    "image_formats": ["jpg", "png", "gif", "webp"],
    "normalize_whitespace": true,
    "enable_deduplication": true
  },
  "llm_config": {
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "api_key": "your-api-key",
    "temperature": 0.1
  },
  "tasks": [
    {
      "url": "https://example.com",
      "name": "task_name",
      "options": {
        "custom_prompt": "提取关键信息",
        "output_schema": {...}
      }
    }
  ]
}
```

## 📚 编程接口指南

### 配置驱动的数据提取

```python
from xpidy import ExtractionConfig

# 基础文本提取
text_config = ExtractionConfig(
    extract_text=True,
    extract_metadata=True
)

# 链接分析配置
link_config = ExtractionConfig(
    extract_text=True,
    extract_links=True,
    extract_internal_links=True,
    extract_external_links=True,
    max_links=50
)

# 图片分析配置
image_config = ExtractionConfig(
    extract_text=True,
    extract_images=True,
    min_image_width=100,
    min_image_height=100,
    max_images=20,
    image_formats=["jpg", "png", "gif"]
)

# 全面分析配置
comprehensive_config = ExtractionConfig(
    extract_text=True,
    extract_links=True,
    extract_images=True,
    extract_structured_data=True,
    extract_tables=True,
    extract_forms=True,
    max_links=100,
    max_images=30
)
```

### 核心API

#### 1. 基础爬取

```python
async with Spider(extraction_config=config) as spider:
    # 单个URL
    result = await spider.crawl(url)
    
    # 批量URL
    results = await spider.crawl_batch(urls, max_concurrent=5)
```

#### 2. 选择器提取

```python
# CSS选择器
css_selectors = {
    "title": "h1.title",
    "price": ".price",
    "description": ".description"
}
result = await spider.extract_with_selectors(url, css_selectors)

# XPath选择器
xpaths = {
    "title": "//h1[@class='title']/text()",
    "items": "//div[@class='item']",
    "links": "//a[@href]/@href"
}
result = await spider.extract_with_xpath(url, xpaths)
```

#### 3. LLM增强提取

```python
from xpidy import LLMConfig

llm_config = LLMConfig(
    provider="openai",
    model="gpt-3.5-turbo",
    api_key="your-api-key"
)

# JSON模式提取
schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "price": {"type": "number"},
        "in_stock": {"type": "boolean"}
    }
}

async with Spider(extraction_config=config, llm_config=llm_config) as spider:
    result = await spider.extract_with_schema(url, schema)
```

### 便捷函数

```python
from xpidy import quick_crawl, quick_crawl_batch

# 快速单次爬取
result = await quick_crawl(url, extraction_config=config)

# 快速批量爬取
results = await quick_crawl_batch(urls, extraction_config=config)
```

### 结果结构

Xpidy 返回结构化的 `CrawlResult` 对象，提供类型安全和IDE智能提示：

```python
# CrawlResult 对象的便捷属性
result = await spider.crawl(url)

# 基础信息
print(f"URL: {result.url}")
print(f"成功状态: {result.success}")
print(f"时间戳: {result.timestamp}")

# 便捷属性（有IDE智能提示）
print(f"有内容: {result.has_content}")
print(f"有链接: {result.has_links}")
print(f"有图片: {result.has_images}")
print(f"内容长度: {result.content_length}")
print(f"字数: {result.word_count}")
print(f"总链接数: {result.total_links}")
print(f"总图片数: {result.total_images}")

# 提取器状态
print(f"启用的提取器: {result.enabled_extractors}")
print(f"成功的提取器: {result.successful_extractors}")
print(f"失败的提取器: {result.failed_extractors}")

# 便捷数据访问方法
internal_links = result.get_internal_links()
external_links = result.get_external_links()
large_images = result.get_large_images()
jpg_images = result.get_images_by_format('jpg')

# 统计信息
summary = result.get_summary()
detailed_stats = result.get_detailed_stats()

# 兼容性：转换为字典（如果需要）
result_dict = result.to_dict()
```

#### 原始数据结构

如果需要访问原始数据结构，可以直接访问对象属性：

```python
# 文本数据
content = result.content
metadata = result.metadata
text_success = result.text_success

# 链接数据
links = result.links
link_stats = result.link_stats
links_success = result.links_success

# 图片数据
images = result.images
image_stats = result.image_stats
images_success = result.images_success

# 结构化数据
structured_data = result.structured_data
structured_success = result.structured_success

# 表格和表单数据
tables = result.tables
forms = result.forms
```

## 🔧 高级配置

### 爬虫配置

```python
from xpidy import SpiderConfig

spider_config = SpiderConfig(
    browser_type="chromium",      # 浏览器类型
    headless=True,                # 无头模式
    timeout=30000,                # 超时时间(毫秒)
    stealth_mode=True,            # 隐身模式
    random_delay=True,            # 随机延迟
    min_delay=0.5,                # 最小延迟(秒)
    max_delay=2.0,                # 最大延迟(秒)
    max_retries=3,                # 最大重试次数
    user_agent="custom-ua"        # 自定义UA
)
```

### 提取配置详解

```python
extraction_config = ExtractionConfig(
    # 基础提取
    extract_text=True,
    extract_links=True,
    extract_images=True,
    extract_metadata=True,
    extract_structured_data=True,
    extract_tables=True,
    extract_forms=True,
    
    # 链接配置
    extract_internal_links=True,
    extract_external_links=True,
    max_links=100,
    link_filters=["*.pdf", "*.zip"],
    
    # 图片配置
    min_image_width=50,
    min_image_height=50,
    max_images=50,
    image_formats=["jpg", "jpeg", "png", "gif", "webp"],
    
    # 内容处理
    remove_scripts=True,
    remove_styles=True,
    normalize_whitespace=True,
    
    # LLM处理
    enable_llm_processing=False,
    structured_output=False
)
```

## 🛠️ 开发环境

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 运行测试
uv run pytest

# 运行示例
uv run python examples/01_quick_start.py
uv run python examples/02_practical_examples.py
uv run python examples/03_advanced_usage.py

# 测试CLI工具
uv run xpidy init basic --output test_config.json
uv run xpidy validate test_config.json
uv run xpidy run test_config.json

# 代码格式化
uvx run black .
uvx run isort .
```

## 📁 项目结构

```
Xpidy/
├── xpidy/                      # 主包
│   ├── core/                   # 核心模块
│   │   ├── spider.py           # 主爬虫类
│   │   ├── config.py           # 配置类定义  
│   │   ├── results.py          # 结果类定义
│   │   ├── llm_processor.py    # LLM处理器
│   │   └── __init__.py         # 核心模块导出
│   ├── extractors/             # 数据提取器模块
│   │   ├── base_extractor.py   # 提取器基类
│   │   ├── text_extractor.py   # 文本提取器
│   │   ├── link_extractor.py   # 链接提取器
│   │   ├── image_extractor.py  # 图片提取器
│   │   ├── data_extractor.py   # 结构化数据提取器
│   │   ├── form_extractor.py   # 表单提取器
│   │   └── __init__.py         # 提取器模块导出
│   ├── utils/                  # 工具模块
│   │   ├── cache.py            # 缓存管理
│   │   ├── content_utils.py    # 内容处理工具
│   │   ├── url_utils.py        # URL处理工具
│   │   ├── stats.py            # 统计收集器
│   │   ├── proxy.py            # 代理管理
│   │   ├── retry.py            # 重试管理器
│   │   └── __init__.py         # 工具模块导出
│   ├── cli.py                  # 配置驱动的命令行工具
│   └── __init__.py             # 包主入口
├── examples/                   # 示例代码
│   ├── cli_config_examples/    # CLI配置文件示例集合
│   ├── 01_quick_start.py       # 快速入门示例，展示基础数据提取功能
│   ├── 02_practical_examples.py # 实用案例示例，展示真实场景应用
│   └── 03_advanced_usage.py    # 高级用法示例，展示选择器、XPath等高级功能
├── tests/                      # 测试文件
│   └── unit/                   # 单元测试
│       └── test_utils.py       # 工具类测试
├── .venv/                      # 虚拟环境 (uv管理)
├── pyproject.toml              # 项目配置文件
├── uv.lock                     # 依赖锁定文件
├── .gitignore                  # Git忽略文件
└── README.md                   # 项目说明文档
```

### 🎯 核心架构

#### 1. 核心模块 (`xpidy/core/`)
- **spider.py**: 主爬虫类，提供统一的爬取接口
- **config.py**: 配置类定义，包括爬虫配置、提取配置和LLM配置
- **results.py**: 结果类定义，提供类型安全的返回结果
- **llm_processor.py**: LLM处理器，支持OpenAI、Claude等模型

#### 2. 提取器模块 (`xpidy/extractors/`)
- **base_extractor.py**: 所有提取器的基类，包含通用处理逻辑
- **text_extractor.py**: 文本内容提取，支持智能清理和LLM处理
- **link_extractor.py**: 链接提取和分析，支持内外部链接分类
- **image_extractor.py**: 图片提取和元数据分析
- **data_extractor.py**: 结构化数据提取，支持JSON-LD和微数据
- **form_extractor.py**: 表单字段提取和分析

#### 3. 工具模块 (`xpidy/utils/`)
- **cache.py**: 智能缓存管理，支持内存和磁盘缓存
- **content_utils.py**: 内容处理工具，文本清理和格式化
- **url_utils.py**: URL处理工具，域名提取和链接规范化
- **stats.py**: 性能统计收集器，监控爬取效率
- **proxy.py**: 代理管理器，支持轮换和故障转移
- **retry.py**: 重试管理器，智能重试机制

#### 4. 命令行工具 (`xpidy/cli.py`)
- 基于配置文件的CLI工具，支持模板生成、配置验证、任务执行
- 符合"配置即文档"设计理念，无需记忆复杂命令参数

#### 5. 示例代码 (`examples/`)
- **cli_config_examples/**: CLI配置文件示例集合
- **01_quick_start.py**: 快速入门示例，展示基础数据提取功能
- **02_practical_examples.py**: 实用案例示例，展示真实场景应用
- **03_advanced_usage.py**: 高级用法示例，展示选择器、XPath等高级功能

## 🎯 设计理念

### 配置即文档
通过配置类和配置文件明确表达提取意图，代码即文档，易于理解和维护。CLI工具完全基于配置文件，避免复杂的命令行参数。

### 简化API
只需关注配置和核心crawl方法，避免复杂的API学习成本。统一的通用处理逻辑，减少代码重复。

### 性能优化
共享页面会话，减少重复加载，支持并发处理。统一的过滤和去重机制，提高处理效率。

### 容错性强
单个提取器失败不影响其他提取器，提供详细的错误信息。

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**Xpidy - 让网页数据提取变得简单而强大！** 🕷️✨
