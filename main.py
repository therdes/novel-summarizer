import argparse
import os

from src.novel_storage import store_novel, list_novels, get_novel_stats, get_all_summaries
from src.novel_summarizer import summarize_novel
from src.novel_rewriter import rewrite_novel, DEFAULT_BATCH_COUNT, HARD_WORD_LIMIT
from src.check_openai import check_openai_availability


def parse_args():
    parser = argparse.ArgumentParser(
        description='小说存储与章节总结工具。'
    )
    subparsers = parser.add_subparsers(dest='command')

    store_parser = subparsers.add_parser('store', help='存储小说到数据库')
    store_parser.add_argument('-p', '--path', required=True, help='小说文本文件路径，支持 .txt 文件。')
    store_parser.add_argument('-t', '--title', required=True, help='小说名称。')
    store_parser.add_argument('-a', '--author', required=True, help='小说作者。')

    summarize_parser = subparsers.add_parser('summarize', help='总结小说章节')
    summarize_parser.add_argument('-t', '--title', required=True, help='小说名称。')
    summarize_parser.add_argument('--reset', action='store_true', help='重新开始总结，清空现有总结。')
    summarize_parser.add_argument('--chapters', type=int, help='本次总结的章节数量。')

    list_parser = subparsers.add_parser('list', help='列出所有小说，或查看指定小说的统计信息')
    list_parser.add_argument('-t', '--title', help='小说名称，指定后展示详细统计。')
    list_parser.add_argument('--export', nargs='?', const='', default=None,
                             help='导出总结到txt文件，需同时指定 -t。无值则用 "<书名>-summary.txt" 输出到当前目录。')

    rewrite_parser = subparsers.add_parser('rewrite', help='将已完全总结的小说重写为大纲小说')
    rewrite_parser.add_argument('-t', '--title', required=True, help='小说名称。')
    rewrite_parser.add_argument('--batch', type=int, default=DEFAULT_BATCH_COUNT,
                                help=f'批次数，默认 {DEFAULT_BATCH_COUNT}。')
    rewrite_parser.add_argument('--target-words', type=int,
                                help=f'目标字数，默认按原文5%%与总结字数估算，上限 {HARD_WORD_LIMIT:,}。')
    rewrite_parser.add_argument('--reset', action='store_true', help='清空已有重写并重新开始。')
    rewrite_parser.add_argument('--export', nargs='?', const='', default=None,
                                help='重写完成后导出到txt文件。无值则用 "<书名>-outline.txt" 输出到当前目录。')

    subparsers.add_parser('check', help='检查 OpenAI 兼容接口是否可用')

    return parser.parse_args()


def read_novel_file(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f'文件不存在: {file_path}')

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def cmd_store(args):
    novel_text = read_novel_file(args.path)
    novel_id = store_novel(novel_text, args.title, args.author)
    print(f'小说存储完成，小说ID: {novel_id}')


def cmd_summarize(args):
    if args.chapters is not None and args.chapters <= 0:
        print("章节数量必须是正整数。")
        return
    summarize_novel(args.title, reset=args.reset, chapters_limit=args.chapters)


def _resolve_export_path(export_arg, default_name):
    """Resolve --export argument to a target file path. Returns None if user cancels."""
    if export_arg == '':
        return os.path.abspath(default_name)

    path = export_arg
    if os.path.isdir(path):
        return os.path.join(path, default_name)
    if os.path.isfile(path):
        confirm = input(f"文件已存在: {path}，是否覆盖？(yes/no): ")
        if confirm.strip().lower() != 'yes':
            return None
        return path
    # Path does not exist
    if path.endswith(('/', '\\')) or path.endswith(os.sep):
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, default_name)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    return path


def _export_summaries(title, export_arg):
    summaries = get_all_summaries(title)
    if summaries is None:
        print(f"未找到小说: {title}")
        return
    unsummarized = sum(1 for _, s in summaries if not s)
    if unsummarized > 0:
        print(f"无法导出：还有 {unsummarized} 章未总结，请先完成总结。")
        return
    target = _resolve_export_path(export_arg, f"{title}-summary.txt")
    if target is None:
        print("已取消导出。")
        return
    with open(target, 'w', encoding='utf-8') as f:
        for i, (chapter_title, summary) in enumerate(summaries, 1):
            f.write(f"{chapter_title}\n\n{summary}\n\n")
    print(f"已导出 {len(summaries)} 章总结到: {target}")


def cmd_list(args):
    if args.export is not None:
        if not args.title:
            print("--export 需要同时指定 -t/--title。")
            return
        _export_summaries(args.title, args.export)
        return

    if args.title:
        stats = get_novel_stats(args.title)
        if stats is None:
            print(f"未找到小说: {args.title}")
            return
        avg_len = f"{stats['avg_summary_length']:.0f}" if stats['avg_summary_length'] else "-"
        total_cost = stats['total_input_cost'] + stats['total_output_cost']
        print(f"书名: {stats['title']}")
        print(f"总章节数: {stats['total_chapters']}")
        print(f"已总结: {stats['summarized']}  /  未总结: {stats['total_chapters'] - stats['summarized']}")
        print(f"平均总结字数: {avg_len}")
        print(f"总输入 Token: {stats['total_input_tokens']:,}")
        print(f"总输出 Token: {stats['total_output_tokens']:,}")
        print(f"总费用 (RMB): {total_cost:.4f}")
    else:
        novels = list_novels()
        if not novels:
            print("暂无小说记录。")
            return
        print(f"{'ID':<4} {'书名':<20} {'作者':<15} {'章节数':<6}")
        print("-" * 48)
        for novel_id, title, author, chapter_count in novels:
            print(f"{novel_id:<4} {title:<20} {author:<15} {chapter_count:<6}")


def cmd_check(args):
    available, message = check_openai_availability()
    if available:
        print("[OK] OpenAI兼容接口可用。")
    else:
        print(f"[FAIL] OpenAI兼容接口不可用: {message}")


def _export_rewrite(title, export_arg):
    from src.novel_storage import get_rewrite_batches
    novel_id = None
    for nid, nt, _, _ in list_novels():
        if nt == title:
            novel_id = nid
            break
    if novel_id is None:
        print(f"未找到小说: {title}")
        return
    batches = get_rewrite_batches(novel_id)
    if not batches:
        print("尚无重写内容，无法导出。")
        return
    target = _resolve_export_path(export_arg, f"{title}-outline.txt")
    if target is None:
        print("已取消导出。")
        return
    with open(target, 'w', encoding='utf-8') as f:
        for batch_index, start, end, _, content in batches:
            f.write(content.strip())
            f.write("\n\n")
    total_chars = sum(len(c or '') for _, _, _, _, c in batches)
    print(f"已导出 {len(batches)} 个批次（共 {total_chars:,} 字）到: {target}")


def cmd_rewrite(args):
    if args.batch <= 0:
        print("批次数必须为正整数。")
        return
    if args.target_words is not None and args.target_words <= 0:
        print("目标字数必须为正整数。")
        return
    success, _ = rewrite_novel(
        args.title,
        batch_count=args.batch,
        target_words=args.target_words,
        reset=args.reset,
    )
    if args.export is not None:
        if not success:
            print("重写未完成，跳过导出。")
            return
        _export_rewrite(args.title, args.export)


def main():
    args = parse_args()

    if args.command == 'store':
        cmd_store(args)
    elif args.command == 'summarize':
        cmd_summarize(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'rewrite':
        cmd_rewrite(args)
    elif args.command == 'check':
        cmd_check(args)
    else:
        print("请指定子命令: store | summarize | list | rewrite | check")
        print("使用 --help 查看帮助。")


if __name__ == '__main__':
    main()
