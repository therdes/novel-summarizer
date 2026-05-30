import sqlite3
import re

DB_PATH = 'novels.db'

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            chapter_title TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            FOREIGN KEY (novel_id) REFERENCES novels (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            novel_id INTEGER,
            input TEXT NOT NULL,
            output TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            input_cost REAL,
            output_cost REAL,
            api_base_url TEXT,
            model_name TEXT,
            FOREIGN KEY (novel_id) REFERENCES novels (id)
        )
    ''')
    # Add new columns if they don't exist (for migration)
    try:
        cursor.execute('ALTER TABLE llm_requests ADD COLUMN api_base_url TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        cursor.execute('ALTER TABLE llm_requests ADD COLUMN model_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        cursor.execute('ALTER TABLE llm_requests ADD COLUMN novel_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()

def split_chapters(text):
    """Split the novel text into chapters based on regex patterns."""
    # Regex to match various chapter start patterns
    pattern = r'(第[一二三四五六七八九十百千万\d]+章|Chapter \d+|CHAPTER \d+)'
    matches = list(re.finditer(pattern, text))
    if not matches:
        # If no chapters found, treat the whole text as one chapter
        return [('Chapter 1', text.strip())]
    chapters = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        newline_index = text.find('\n', start)
        if newline_index == -1 or newline_index >= end:
            # No newline before end, title is the match, content from match end to end
            chapter_title = match.group(0)
            content = text[match.end():end].strip()
        else:
            chapter_title = text[start:newline_index].strip()
            content = text[newline_index+1:end].strip()
        chapters.append((chapter_title, content))
    return chapters

def store_novel(novel_text, title, author):
    """Store a novel and its chapters in the database."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO novels (title, author) VALUES (?, ?)', (title, author))
    novel_id = cursor.lastrowid
    chapters = split_chapters(novel_text)
    for chapter_title, content in chapters:
        cursor.execute('INSERT INTO chapters (novel_id, chapter_title, content) VALUES (?, ?, ?)', (novel_id, chapter_title, content))
    conn.commit()
    conn.close()
    return novel_id


def list_novels():
    """List all novels with title, author, and chapter count."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT n.id, n.title, n.author, COUNT(c.id) AS chapter_count
        FROM novels n
        LEFT JOIN chapters c ON c.novel_id = n.id
        GROUP BY n.id
        ORDER BY n.id
    ''')
    novels = cursor.fetchall()
    conn.close()
    return novels


def get_novel_stats(title):
    """Get detailed statistics for a specific novel."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM novels WHERE title = ?', (title,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    novel_id = row[0]

    cursor.execute('''
        SELECT
            COUNT(*) AS total_chapters,
            SUM(CASE WHEN summary IS NOT NULL AND summary != '' THEN 1 ELSE 0 END) AS summarized,
            AVG(CASE WHEN summary IS NOT NULL AND summary != '' THEN LENGTH(summary) ELSE NULL END) AS avg_summary_length
        FROM chapters
        WHERE novel_id = ?
    ''', (novel_id,))
    chapter_stats = cursor.fetchone()

    cursor.execute('''
        SELECT
            COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
            COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
            COALESCE(SUM(input_cost), 0) AS total_input_cost,
            COALESCE(SUM(output_cost), 0) AS total_output_cost
        FROM llm_requests
        WHERE novel_id = ?
    ''', (novel_id,))
    token_stats = cursor.fetchone()

    conn.close()

    return {
        'title': title,
        'total_chapters': chapter_stats[0],
        'summarized': chapter_stats[1],
        'avg_summary_length': chapter_stats[2],
        'total_input_tokens': token_stats[0],
        'total_output_tokens': token_stats[1],
        'total_input_cost': token_stats[2],
        'total_output_cost': token_stats[3],
    }