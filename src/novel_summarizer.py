import os
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

DB_PATH = 'novels.db'

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

def summarize_chapter(chapter_id, prompt):
    """Summarize a chapter using LLM."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        summary = response.choices[0].message.content.strip()
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

def summarize_novel(novel_title, reset=False):
    """Summarize chapters of a novel using LLM, with resume capability."""
    novel_id = get_novel_id_by_title(novel_title)
    if not novel_id:
        print(f"Novel '{novel_title}' not found.")
        return

    if reset:
        clear_summaries(novel_id)
        start_index = 0
    else:
        chapters = get_chapters_by_novel_id(novel_id)
        start_index = next((i for i, (_, _, _, summary) in enumerate(chapters) if summary is None), len(chapters))

    chapters = get_chapters_by_novel_id(novel_id)
    for i in range(start_index, len(chapters)):
        chapter_id, chapter_title, content, _ = chapters[i]

        # Get previous summaries (up to 50)
        prev_summaries = []
        for j in range(max(0, i - 50), i):
            if chapters[j][3]:  # summary exists
                prev_summaries.append(f"Chapter {j+1} Summary: {chapters[j][3]}")
        prev_summaries_join = "\n".join(prev_summaries)

        # Build prompt
        prompt = f"""
Role: 资深网文剧情分析师。
Context: 前面若干章节的剧情简述为：
{prev_summaries_join}
Task: 结合上述背景，总结本章节的新进展。
Constraints:

字数严格控制在 100-200 字。

重点记录剧情的“状态变化”（例如：修为提升、获得宝物、结识新队友、地图切换）。

如果本章是过渡章，请精炼为一句话，不要为了凑字数而罗列细节。

只需输出总结内容，不要任何额外说明。

本章标题：
{chapter_title}
本章正文：
{content}
        """

        print(f"Summarizing chapter {i+1}: {chapter_title}")
        summary = summarize_chapter(chapter_id, prompt)
        if summary:
            print(f"Summary: {summary[:100]}...")
        else:
            print("Failed to summarize.")

    print("Summarization complete.")
    