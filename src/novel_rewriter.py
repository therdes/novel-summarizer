import math
import random
import time

from src.novel_storage import (
    get_rewrite_batches,
    save_rewrite_batch,
    clear_rewrites,
)
from src.novel_summarizer import (
    client,
    model,
    sanitize_llm_response,
    log_llm_request,
    INPUT_TOKEN_PRICE_RMB,
    OUTPUT_TOKEN_PRICE_RMB,
    get_novel_id_by_title,
    get_chapters_by_novel_id,
)


DEFAULT_BATCH_COUNT = 20
HARD_WORD_LIMIT = 50000


def compute_target_words(chapters, override=None):
    """chapters: list of (id, title, content, summary)."""
    if override is not None:
        return override
    total_content = sum(len(c[2] or '') for c in chapters)
    total_summary = sum(len(c[3] or '') for c in chapters)
    return min(HARD_WORD_LIMIT, max(total_summary, int(total_content * 0.05)))


def plan_batches(chapters, target_words, batch_count):
    """Split chapters into batch_count contiguous groups balanced by summary length.
    Returns list of dicts: {batch_index, start_idx, end_idx, target_words}.
    start_idx/end_idx are 0-based inclusive chapter indices.
    """
    total_summary = sum(len(c[3] or '') for c in chapters)
    if total_summary == 0:
        raise ValueError("所有章节总结字数为 0，无法划分批次。")

    n = len(chapters)
    batch_count = min(batch_count, n)
    target_per_batch = total_summary / batch_count

    batches = []
    cursor = 0
    accumulated = 0
    for batch_index in range(batch_count):
        start = cursor
        # Last batch takes all remaining chapters
        if batch_index == batch_count - 1:
            end = n - 1
            cursor = n
        else:
            limit = (batch_index + 1) * target_per_batch
            while cursor < n and accumulated < limit:
                accumulated += len(chapters[cursor][3] or '')
                cursor += 1
            # Ensure at least one chapter per batch
            if cursor == start:
                cursor = start + 1
            end = cursor - 1
        batch_summary_chars = sum(len(chapters[i][3] or '') for i in range(start, end + 1))
        batch_target = int(target_words * batch_summary_chars / total_summary) if total_summary else 0
        batches.append({
            'batch_index': batch_index,
            'start_idx': start,
            'end_idx': end,
            'target_words': max(batch_target, 200),
        })
    return batches


def build_prompt(novel_title, total_chapters, batch, chapters, prev_tail):
    start = batch['start_idx']
    end = batch['end_idx']
    target = batch['target_words']

    summary_lines = []
    for i in range(start, end + 1):
        ch_title = chapters[i][1]
        summary = chapters[i][3] or ''
        summary_lines.append(f"[Ch.{i+1}] {ch_title}\n{summary}")
    summary_block = "\n\n".join(summary_lines)

    prev_section = ''
    if prev_tail:
        prev_section = f"前情衔接（上一批结尾片段）：\n{prev_tail}\n\n"

    chapter_range = f"第{start+1}章 - 第{end+1}章" if start != end else f"第{start+1}章"

    return f"""Role: 资深小说编辑，擅长将网文压缩为节奏紧凑的大纲小说。
Background: 你正在重写《{novel_title}》，全书共 {total_chapters} 章。
{prev_section}本批任务: 将以下 {end - start + 1} 章（{chapter_range}）重写为约 {target} 字的连贯正文。
要求:
- 第三人称叙事，可在合适位置插入小节标题
- 突出关键剧情、状态变化与人物决策，删去过渡描写
- 风格连贯，与前情衔接自然
- 不使用 markdown 标记，不输出任何额外说明
- 章节间用空行分隔

本批章节总结:
{summary_block}

请直接输出重写后的正文。"""


def call_llm(novel_id, prompt):
    """Call LLM and return (output_text, error). On success error is None."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        output = response.choices[0].message.content.strip()
        cleaned = sanitize_llm_response(output)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        input_cost = (input_tokens / 1_000_000) * INPUT_TOKEN_PRICE_RMB
        output_cost = (output_tokens / 1_000_000) * OUTPUT_TOKEN_PRICE_RMB
        log_llm_request(novel_id, prompt, output, input_tokens, output_tokens,
                        input_cost, output_cost, str(client.base_url), model)
        return cleaned, None
    except Exception as e:
        return None, str(e)


def rewrite_novel(novel_title, batch_count=DEFAULT_BATCH_COUNT, target_words=None, reset=False):
    """Rewrite a novel into an outline. Returns (success: bool, completed_batches: list).
    Aborts immediately on failure and returns (False, completed_batches_so_far).
    """
    novel_id = get_novel_id_by_title(novel_title)
    if not novel_id:
        print(f"未找到小说: {novel_title}")
        return False, []

    chapters = get_chapters_by_novel_id(novel_id)
    if not chapters:
        print(f"小说 '{novel_title}' 无章节。")
        return False, []

    unsummarized = sum(1 for c in chapters if not c[3])
    if unsummarized > 0:
        print(f"无法重写：还有 {unsummarized} 章未总结，请先完成总结。")
        return False, []

    if reset:
        clear_rewrites(novel_id)

    target_words = compute_target_words(chapters, target_words)
    batches = plan_batches(chapters, target_words, batch_count)

    print(f"目标字数: {target_words:,}，批次数: {len(batches)}")

    existing = get_rewrite_batches(novel_id)
    done_indices = {row[0] for row in existing}
    prev_tail = ''
    if existing:
        last = max(existing, key=lambda r: r[0])
        prev_tail = (last[4] or '')[-500:]

    success_count = len(done_indices)
    for batch in batches:
        if batch['batch_index'] in done_indices:
            continue
        chapter_range = f"Ch.{batch['start_idx']+1}-{batch['end_idx']+1}"
        print(f"[{batch['batch_index']+1}/{len(batches)}] {chapter_range} (~{batch['target_words']} words) ... ",
              end='', flush=True)

        prompt = build_prompt(novel_title, len(chapters), batch, chapters, prev_tail)
        output, error = call_llm(novel_id, prompt)
        if error is not None or not output:
            print("FAIL")
            print(f"错误: {error or '空输出'}")
            return False, get_rewrite_batches(novel_id)

        save_rewrite_batch(
            novel_id, batch['batch_index'],
            batch['start_idx'] + 1, batch['end_idx'] + 1,
            batch['target_words'], output,
        )
        prev_tail = output[-500:]
        success_count += 1
        print(f"OK ({len(output)} chars)")
        time.sleep(random.uniform(0.1, 0.5))

    final = get_rewrite_batches(novel_id)
    total_chars = sum(len(row[4] or '') for row in final)
    print(f"\n重写完成: 成功 {success_count} 批, 总字数 {total_chars:,}")
    return True, final
