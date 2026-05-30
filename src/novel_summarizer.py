import os
import re
import random
import time
import sqlite3
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client with config from .env
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    base_url=os.getenv('OPENAI_BASE_URL')
)
model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')

# Pricing configuration (per million tokens in RMB)
INPUT_TOKEN_PRICE_RMB = float(os.getenv('INPUT_TOKEN_PRICE_RMB', 0.0))
OUTPUT_TOKEN_PRICE_RMB = float(os.getenv('OUTPUT_TOKEN_PRICE_RMB', 0.0))

DB_PATH = 'novels.db'

def sanitize_llm_response(text):
    """Remove <think>...</think> tags and their content from LLM responses."""
    if not text:
        return text
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()

def log_llm_request(novel_id, input_text, output_text, input_tokens, output_tokens, input_cost, output_cost, api_base_url, model_name):
    """Log an LLM request to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO llm_requests (novel_id, input, output, input_tokens, output_tokens, input_cost, output_cost, api_base_url, model_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (novel_id, input_text, output_text, input_tokens, output_tokens, input_cost, output_cost, api_base_url, model_name))
    conn.commit()
    conn.close()

def get_novel_id_by_title(title):
    """Get novel ID by title."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM novels WHERE title = ?', (title,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_chapters_by_novel_id(novel_id):
    """Get all chapters for a novel, ordered by id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, chapter_title, content, summary FROM chapters WHERE novel_id = ? ORDER BY id', (novel_id,))
    chapters = cursor.fetchall()
    conn.close()
    return chapters

def clear_summaries(novel_id):
    """Clear all summaries for a novel."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE chapters SET summary = NULL WHERE novel_id = ?', (novel_id,))
    conn.commit()
    conn.close()

def summarize_chapter(chapter_id, novel_id, prompt):
    """Summarize a chapter using LLM."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        output = response.choices[0].message.content.strip()
        summary = sanitize_llm_response(output)
        # Calculate costs
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        input_cost = (input_tokens / 1_000_000) * INPUT_TOKEN_PRICE_RMB
        output_cost = (output_tokens / 1_000_000) * OUTPUT_TOKEN_PRICE_RMB
        # Log the request
        log_llm_request(novel_id, prompt, output, input_tokens, output_tokens, input_cost, output_cost, str(client.base_url), model)
        # Store summary in database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE chapters SET summary = ? WHERE id = ?', (summary, chapter_id))
        conn.commit()
        conn.close()
        return summary
    except Exception as e:
        print(f"Error summarizing chapter {chapter_id}: {e}")
        return None

def summarize_novel(novel_title, reset=False, chapters_limit=None):
    """Summarize chapters of a novel using LLM, with resume capability."""
    novel_id = get_novel_id_by_title(novel_title)
    if not novel_id:
        print(f"Novel '{novel_title}' not found.")
        return

    if reset:
        clear_summaries(novel_id)

    chapters = get_chapters_by_novel_id(novel_id)

    if not reset:
        start_index = next((i for i, (_, _, _, summary) in enumerate(chapters) if summary is None), len(chapters))
    else:
        start_index = 0
    if chapters_limit is not None:
        end_index = min(start_index + chapters_limit, len(chapters))
    else:
        end_index = len(chapters)
    total_input_tokens = 0
    total_output_tokens = 0
    success_count = 0
    fail_count = 0
    for i in range(start_index, end_index):
        chapter_id, chapter_title, content, _ = chapters[i]

        # Get previous summaries (up to 50)
        prev_summaries = []
        for j in range(max(0, i - 50), i):
            if chapters[j][3]:  # summary exists
                prev_summaries.append(f"[Ch.{j+1}] {chapters[j][3]}")
        prev_summaries_join = "\n".join(prev_summaries)

        # Build prompt
        prompt = f"""Role: 资深网文剧情分析师。
Context: 前面章节剧情简述：
{prev_summaries_join}
Task: 结合上述背景，用100-200字总结本章新进展。
Constraints:
- 纯文本，不加markdown标记
- 只记状态变化（修为、宝物、队友、地图切换）
- 过渡章精炼为一句话
- 只输出总结，无额外说明
本章标题：{chapter_title}
本章正文：
{content}"""

        print(f"[{i+1}/{end_index}] {chapter_title} ... ", end='', flush=True)
        summary = summarize_chapter(chapter_id, novel_id, prompt)
        if summary:
            chapters[i] = (chapter_id, chapter_title, content, summary)
            success_count += 1
            print("OK")
            time.sleep(random.uniform(0.1, 0.5))
        else:
            fail_count += 1
            print("FAIL")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0)
        FROM llm_requests WHERE novel_id = ?
    ''', (novel_id,))
    total_input_tokens, total_output_tokens = cursor.fetchone()
    conn.close()

    print(f"\n总结完成: 成功 {success_count} 章, 失败 {fail_count} 章, 输入 {total_input_tokens:,} tokens, 输出 {total_output_tokens:,} tokens")
    