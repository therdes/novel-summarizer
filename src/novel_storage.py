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