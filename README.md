# Novel Summarizer

一个用于存储和总结小说章节的工具。

## 安装

1. 安装依赖：
   ```
   pip install -e .
   ```

2. 配置 `.env` 文件：
   ```
   OPENAI_BASE_URL=https://api.openai.com/v1
   OPENAI_MODEL=gpt-3.5-turbo
   OPENAI_API_KEY=your_api_key_here
   ```

## 使用

### 存储小说

从txt文件读取小说并存储到数据库：

```
python main.py -p path/to/novel.txt -t "小说标题" -a "作者"
```

### 总结小说

总结已存储小说的章节：

```
python main.py -t "小说标题" --summarize
```

从头重新开始总结（清空现有总结）：

```
python main.py -t "小说标题" --summarize --reset
```

## 功能

- 自动拆分章节（支持中文和英文章节标题）
- 使用OpenAI兼容LLM总结章节
- 支持断点继续（从第一个未总结章节开始）
- 总结时包含前50章的总结内容作为上下文