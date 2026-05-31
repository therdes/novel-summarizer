# Novel Summarizer

一个用于存储和总结小说章节的命令行工具，支持 OpenAI 兼容的 LLM 接口。

## 功能

- 自动拆分章节（支持 `第X章` / `Chapter N` 格式）
- 使用 OpenAI 兼容接口逐章总结，自动包含前 50 章作为上下文
- 支持断点续传（从首个未总结章节继续）
- 记录每次 LLM 请求的 token 消耗与费用
- 导出整本小说的总结到 txt 文件
- DeepSeek/R1 thinking 标签自动剥离

## 安装

依赖管理使用 [uv](https://github.com/astral-sh/uv)（要求 Python 3.13）：

```
uv sync
```

复制 `.env.example` 为 `.env` 并填入实际配置：

```
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_API_KEY=your_api_key_here
INPUT_TOKEN_PRICE_RMB=0
OUTPUT_TOKEN_PRICE_RMB=0
```

> Windows PowerShell 运行前需设置 UTF-8 编码避免中文乱码：
> ```
> $env:PYTHONIOENCODING = "utf-8"
> ```

## 使用

工具采用子命令模式，所有命令通过 `uv run python main.py <command>` 调用。

### `store` — 存储小说

```
uv run python main.py store -p path/to/novel.txt -t "小说标题" -a "作者"
```

### `summarize` — 总结章节

总结全部未总结章节：
```
uv run python main.py summarize -t "小说标题"
```

仅总结指定数量的章节：
```
uv run python main.py summarize -t "小说标题" --chapters 50
```

清空已有总结后重新开始：
```
uv run python main.py summarize -t "小说标题" --reset
```

### `list` — 查看与导出

列出所有小说：
```
uv run python main.py list
```

查看指定小说的统计（章节数、总结进度、token 消耗、费用）：
```
uv run python main.py list -t "小说标题"
```

导出该小说所有章节总结到 txt 文件（要求所有章节均已总结）：
```
uv run python main.py list -t "小说标题" --export                    # 默认输出 <书名>-summary.txt
uv run python main.py list -t "小说标题" --export output/dir/        # 指定目录
uv run python main.py list -t "小说标题" --export custom.txt         # 指定文件，已存在则提示覆盖
```

### `check` — 接口连通性检查

```
uv run python main.py check
```

## 数据库

SQLite 数据库 `novels.db` 在运行时自动创建，不纳入版本管理。表结构：

- `novels` — 小说元信息
- `chapters` — 章节正文与总结
- `llm_requests` — LLM 调用日志（含 token、费用、模型等）
