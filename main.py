import argparse
import os

from src.novel_storage import store_novel
from src.novel_summarizer import summarize_novel


def parse_args():
    parser = argparse.ArgumentParser(
        description='从指定 txt 文件读取小说内容，并拆分章节存储到 sqlite 数据库中，或总结已存储的小说。'
    )
    parser.add_argument(
        '-p', '--path',
        help='小说文本文件路径，支持 .txt 文件。'
    )
    parser.add_argument(
        '-t', '--title',
        required=True,
        help='小说名称。'
    )
    parser.add_argument(
        '-a', '--author',
        help='小说作者。'
    )
    parser.add_argument(
        '--summarize',
        action='store_true',
        help='总结小说章节。'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='重新开始总结，清空现有总结。'
    )
    return parser.parse_args()


def read_novel_file(file_path):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f'文件不存在: {file_path}')

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()



def main():
    args = parse_args()

    if args.summarize:
        summarize_novel(args.title, reset=args.reset)
    else:
        if not args.path or not args.author:
            print("存储小说需要 --path 和 --author 参数。")
            return
        novel_text = read_novel_file(args.path)
        novel_id = store_novel(novel_text, args.title, args.author)
        print(f'小说存储完成，小说ID: {novel_id}')


if __name__ == '__main__':
    main()
