# AGENTS.md

## Build & Run

- Use `uv` (not pip) — `uv.lock` and `.python-version` (3.13) are present.
- `uv sync` to install dependencies. `uv run python main.py ...` to run.
- Windows PowerShell 默认 GBK 编码会导致中文输出乱码，运行前临时设置：
  ```
  $env:PYTHONIOENCODING = "utf-8"
  ```
- No test suite, linting, or typecheck config exists.

## Environment

- `.env` required with: `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`.
- Optional pricing: `INPUT_TOKEN_PRICE_RMB`, `OUTPUT_TOKEN_PRICE_RMB` (per million tokens).
- `.env` is gitignored; use `.env.example` as template.

## Architecture

- Single package `src/` with two modules:
  - `novel_storage.py` — SQLite schema, chapter splitting, DB writes
  - `novel_summarizer.py` — LLM summarization via OpenAI-compatible API
- `main.py` is the CLI entrypoint (argparse). `src/check_openai.py` is a standalone API health-check script.
- SQLite DB (`novels.db`) is auto-created at runtime; not version-controlled.

## Chapter Splitting

Regex: `(第[一二三四五六七八九十百千万\d]+章|Chapter \d+|CHAPTER \d+)`
Fallback: entire text as one chapter if no matches.

## Summarization Quirks

- `sanitize_llm_response()` strips ` </think>` blocks (DeepSeek/R1 thinking tags). Applies after every LLM call.
- Previous 50 chapter summaries are included as context in the prompt.
- `novel_summarizer.py` calls `load_dotenv()` and creates the OpenAI `client` at module level — importing it triggers env loading and connection setup.
- `--reset` flag clears all summaries before starting. `--chapters N` limits how many chapters to summarize in one run.

## Database Tables

- `novels` (id, title, author)
- `chapters` (id, novel_id, chapter_title, content, summary)
- `llm_requests` (id, timestamp, input, output, input_tokens, output_tokens, input_cost, output_cost, api_base_url, model_name)
