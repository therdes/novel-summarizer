import argparse
import os

from src.novel_storage import store_novel, list_novels, get_novel_stats
from src.novel_summarizer import summarize_novel
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


def cmd_list(args):
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


def main():
    args = parse_args()

    if args.command == 'store':
        cmd_store(args)
    elif args.command == 'summarize':
        cmd_summarize(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'check':
        cmd_check(args)
    else:
        print("请指定子命令: store | summarize | list | check")
        print("使用 --help 查看帮助。")


if __name__ == '__main__':
    main()
