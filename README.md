[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Ciciy-l/Xpidy)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/xpidy.svg)](https://badge.fury.io/py/xpidy)
[![PyPI Downloads](https://static.pepy.tech/badge/xpidy)](https://pepy.tech/projects/xpidy)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Playwright](https://img.shields.io/badge/playwright-enabled-brightgreen.svg)](https://playwright.dev/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

# Xpidy - 智能网页数据提取框架

一个基于Playwright的现代化智能爬虫库，采用"配置驱动"设计理念，让网页数据提取变得极其简单。

## ✨ 特性

- 🎯 **配置驱动** - 基于配置的自动化数据提取，配置即文档
- 🚀 **极简API** - 配置完成后只需 `await spider.crawl(url)` 
- 🎭 **Playwright驱动** - 支持JavaScript渲染和SPA应用
- ⚡ **高性能** - 多提取器并发执行，内置智能缓存
- 🧠 **LLM增强** - 可选的大语言模型后处理优化
- 📋 **全面提取** - 文本、链接、图片、表格、表单等多种数据
- 🔍 **灵活选择器** - 支持CSS选择器和XPath范围限制
- 🛡️ **反爬虫** - 内置隐身模式和随机延迟
- 🔧 **CLI工具** - 完整的命令行工具支持

## 🚀 快速开始

### 安装

```bash
# 方式1：使用uv安装（推荐）
uv add xpidy

# 方式2：使用pip安装
pip install xpidy

# 安装Playwright浏览器
uv run playwright install
# 或者如果使用pip安装的
playwright install
```

### 验证安装

```bash
# 验证xpidy CLI工具
xpidy --version

# 验证Python导入
python -c "from xpidy import Spider; print('Xpidy安装成功！')"
```

### 开发安装（仅限贡献者）

如果你想参与开发或需要最新的开发版本：

```bash
# 安装uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone https://github.com/Ciciy-l/Xpidy.git
cd Xpidy

# 安装依赖
uv sync

# 安装Playwright浏览器
uv run playwright install
```

### 最简使用方式

```python
import asyncio
from xpidy import Spider, XpidyConfig, ExtractionConfig

async def main():
    # 快速创建爬虫实例
    spider = Spider.quick_create(
        enable_text=True,      # 提取文本
        enable_links=True,     # 提取链接
        enable_images=True     # 提取图片
    )
    
    # 一行代码完成所有提取
    async with spider:
        result = await spider.crawl("https://example.com")
        print(f"提取完成！文本: {len(result['results']['text']['content'])}字符")

asyncio.run(main())
```

### 配置驱动方式

```python
import asyncio
from xpidy import Spider, XpidyConfig, ExtractionConfig, SpiderConfig

async def main():
    # 1. 定义配置（配置即文档）
    config = XpidyConfig(
        spider_config=SpiderConfig(
            headless=True,
            timeout=30000,
            enable_stealth=True
        ),
        extraction_config=ExtractionConfig(
            enable_text=True,
            enable_links=True, 
            enable_images=True,
            text_config={"min_text_length": 10},
            links_config={"max_items": 50},
            images_config={"max_items": 20}
        )
    )
    
    # 2. 创建爬虫实例
    async with Spider(config) as spider:
        # 3. 一键提取所有配置的数据
        result = await spider.crawl("https://example.com")
        
        # 4. 使用结构化结果
        print(f"URL: {result['url']}")
        print(f"提取器: {result['extractors_used']}")
        print(f"耗时: {result['extraction_time']:.2f}秒")
        
        # 5. 访问各提取器结果
        if 'text' in result['results']:
            text_data = result['results']['text']
            print(f"文本长度: {len(text_data['content'])}字符")
            print(f"标题: {text_data['metadata']['title']}")
        
        if 'links' in result['results']:
            links_data = result['results']['links']
            print(f"链接数量: {links_data['total_links']}")
            print(f"内部链接: {len(links_data['internal_links'])}")
        
        if 'images' in result['results']:
            images_data = result['results']['images']
            print(f"图片数量: {images_data['total_images']}")

asyncio.run(main())
```

## 📋 CLI使用指南

### 基础命令

```bash
# 1. 生成配置模板
xpidy init basic --output my_config.json

# 2. 验证配置文件
xpidy validate my_config.json

# 3. 执行爬取任务
xpidy run my_config.json --output results.json

# 4. 快速爬取单个URL
xpidy quick https://example.com --enable-links --enable-images --enable-data
```

### 配置文件示例

```json
{
  "spider_config": {
    "headless": true,
    "timeout": 30000,
    "enable_stealth": true,
    "delay": 1.0,
    "retry_times": 3
  },
  "extraction_config": {
    "enable_text": true,
    "enable_links": true,
    "enable_images": true,
    "enable_data": true,
    "text_config": {
      "min_text_length": 10,
      "extract_metadata": true
    },
    "links_config": {
      "include_internal": true,
      "include_external": true,
      "max_items": 50
    },
    "images_config": {
      "min_width": 100,
      "min_height": 100,
      "max_items": 20,
      "allowed_formats": ["jpg", "png", "gif"]
    }
  },
  "tasks": [
    {
      "url": "https://example.com",
      "name": "example_site"
    }
  ]
}
```

### 可用模板

```bash
# 基础文本提取
xpidy init basic

# 链接分析  
xpidy init links

# 图片分析
xpidy init images

# 全面数据提取
xpidy init comprehensive

# 结构化数据提取
xpidy init data

# 表单数据提取
xpidy init form
```

## 🔧 高级功能

### 1. 选择器范围限制

```python
from xpidy import XpidyConfig, ExtractionConfig, SpiderConfig

config = XpidyConfig(
    extraction_config=ExtractionConfig(
        enable_text=True,
        enable_links=True,
        # 全局选择器限制
        global_selectors=["main .content"],  # 只在主内容区域提取
        global_exclude_selectors=[".ads"],  # 排除广告和侧边栏
        text_config={
            "selectors": ["article p"]  # 文本提取器专用选择器
        },
        links_config={
            "selectors": ["nav a", ".content a"]  # 链接提取器专用选择器
        }
    )
)
```

### 2. 配置文件保存与加载

```python
# 保存配置
config = XpidyConfig(...)
config.save_to_file("my_config.json")

# 从文件加载配置
config = XpidyConfig.load_from_file("my_config.json")
```

### 3. LLM后处理（可选）

```python
from xpidy import LLMConfig

config = XpidyConfig(
    extraction_config=ExtractionConfig(enable_text=True),
    llm_config=LLMConfig(
        provider="openai",
        model="gpt-3.5-turbo", 
        api_key="your-api-key",
        enabled=True,
        temperature=0.7,
        max_tokens=2000
    )
)

async with Spider(config) as spider:
    # 使用LLM优化结果
    result = await spider.crawl(
        "https://example.com",
        prompt="请提取关键信息并整理为结构化格式"
    )
```

### 4. 并发批量处理

```python
urls = [
    "https://example1.com",
    "https://example2.com", 
    "https://example3.com"
]

async with Spider(config) as spider:
    # 并发处理多个URL
    results = await spider.crawl_multiple_urls(
        urls, 
        max_concurrent=3,
        delay_between_batches=1.0
    )
```

## 🏗️ 架构设计

### 核心设计理念

1. **配置驱动**：所有提取逻辑通过配置声明，运行时自动执行
2. **并发架构**：多提取器自动并发执行，提高效率  
3. **智能缓存**：提取器内部结果暂存，避免重复计算
4. **优雅错误处理**：单点失败不影响整体，详细错误日志

### 架构层次

```
用户层: 极简API (Spider.crawl)
配置层: 声明式配置 (XpidyConfig, ExtractionConfig, SpiderConfig)
控制层: 智能调度 (Spider内部并发管理)
执行层: 专用提取器 (TextExtractor, LinkExtractor, ImageExtractor等)
基础层: 统一抽象 (BaseExtractor, Playwright)
```

## 📁 项目结构

```
Xpidy/
├── xpidy/                      # 主包
│   ├── core/                   # 核心模块
│   │   ├── spider.py           # 主爬虫类
│   │   ├── config.py           # 配置类定义  
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
│   │   ├── stats.py            # 统计工具
│   │   ├── proxy.py            # 代理工具
│   │   ├── retry.py            # 重试工具
│   │   └── __init__.py         # 工具模块导出
│   ├── cli.py                  # 配置驱动的命令行工具
│   └── __init__.py             # 包主入口
├── examples/                   # 示例代码
├── tests/                      # 测试文件
├── .venv/                      # 虚拟环境 (uv管理)
├── pyproject.toml              # 项目配置文件
├── uv.lock                     # 依赖锁定文件
└── README.md                   # 项目说明文档
```

## 🔧 配置详解

### SpiderConfig（爬虫配置）

```python
from xpidy import SpiderConfig

spider_config = SpiderConfig(
    headless=True,                # 无头模式
    timeout=30000,                # 超时时间(毫秒)
    user_agent="custom-ua",       # 自定义UA
    viewport={"width": 1920, "height": 1080},  # 视口大小
    delay=1.0,                    # 请求间隔(秒)
    retry_times=3,                # 最大重试次数
    retry_delay=2.0,              # 重试间隔(秒)
    enable_cache=True,            # 启用缓存
    cache_ttl=3600,               # 缓存TTL(秒)
    enable_stealth=True,          # 启用隐身模式
    javascript_enabled=True,      # 启用JavaScript
    images_enabled=True           # 启用图片加载
)
```

### ExtractionConfig（提取配置）

```python
from xpidy import ExtractionConfig

extraction_config = ExtractionConfig(
    # 启用的提取器
    enable_text=True,
    enable_links=True,
    enable_images=True,
    enable_data=True,
    enable_form=True,
    
    # 全局选择器（影响所有提取器）
    global_selectors=["main"],    # CSS选择器范围限制
    global_xpath_selectors=["//main"],  # XPath选择器范围限制
    global_exclude_selectors=[".ads"],  # 排除选择器
    
    # 各提取器专用配置
    text_config={
        "min_text_length": 10,
        "extract_metadata": True,
        "clean_content": True
    },
    links_config={
        "include_internal": True,
        "include_external": True,
        "max_items": 100,
        "filter_patterns": ["*.pdf", "*.zip"]
    },
    images_config={
        "min_width": 50,
        "min_height": 50,
        "max_items": 50,
        "allowed_formats": ["jpg", "png", "gif", "webp"]
    },
    data_config={
        "extract_json_ld": True,
        "extract_microdata": True,
        "extract_tables": True
    },
    form_config={
        "extract_input_fields": True,
        "extract_buttons": True,
        "include_hidden_fields": False
    }
)
```

### LLMConfig（LLM配置）

```python
from xpidy import LLMConfig

llm_config = LLMConfig(
    enabled=True,                 # 启用LLM处理
    provider="openai",            # 提供商: openai/anthropic
    model="gpt-3.5-turbo",        # 模型名称
    api_key="your-api-key",       # API密钥
    base_url=None,                # API基础URL
    temperature=0.7,              # 温度参数
    max_tokens=2000,              # 最大令牌数
    top_p=1.0,                    # top_p参数
    enable_cache=True,            # 启用LLM缓存
    cache_ttl=86400,              # 缓存TTL(秒)
    batch_size=10,                # 批处理大小
    max_retries=3                 # 最大重试次数
)
```

## 🧪 开发环境

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 运行测试
uv run pytest tests/ -v

# 测试CLI工具
uv run xpidy init basic --output test_config.json
uv run xpidy validate test_config.json
uv run xpidy run test_config.json

# 代码格式化
uvx isort .
uvx black .
```

## 📊 性能特性

### 并发提取

所有提取器在爬取过程中并发执行：

```python
# 内部实现伪代码
async def crawl(self, url):
    # 创建并发任务
    tasks = []
    if self.config.extraction_config.enable_text:
        tasks.append(self._extractors['text'].extract(page))
    if self.config.extraction_config.enable_links:
        tasks.append(self._extractors['links'].extract(page))
    if self.config.extraction_config.enable_images:
        tasks.append(self._extractors['images'].extract(page))
    
    # 并发执行所有提取器
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 智能缓存

每个提取器内部维护结果缓存，避免重复计算：

```python
# 自动缓存机制
class TextExtractor(BaseExtractor):
    async def extract(self, page):
        if self._cached_result:
            return self._cached_result
        
        result = await self._do_extract(page)
        self._cached_result = result  # 自动缓存
        return result
```

### 错误隔离

单个提取器失败不影响其他提取器：

```python
# 优雅错误处理
results = await asyncio.gather(*tasks, return_exceptions=True)
for extractor_name, result in zip(enabled_extractors, results):
    if isinstance(result, Exception):
        logger.warning(f"提取器 {extractor_name} 失败: {result}")
        # 继续处理其他提取器结果
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**Xpidy - 让网页数据提取变得简单而强大！** 🕷️✨
