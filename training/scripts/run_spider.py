#!/usr/bin/env python3
"""
古玉鉴真 — 博物馆爬虫 CLI

用法:
    cd training
    python scripts/run_spider.py --spider list
    python scripts/run_spider.py --spider met --limit 5          # 调试: 只处理 5 件
    python scripts/run_spider.py --spider met --limit 5 --dry-run  # 只映射不下载
    python scripts/run_spider.py --spider met --import-after     # 爬完自动导入标注库
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'training' / 'src'))
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

from data.scraping.spiders.registry import SPIDERS  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='古玉鉴真博物馆爬虫')
    ap.add_argument('--spider', type=str, default='list',
                    help='爬虫 ID (met/cleveland/gugong/list)')
    ap.add_argument('--limit', type=int, default=None,
                    help='最多处理 N 件藏品 (默认全部)')
    ap.add_argument('--dry-run', action='store_true',
                    help='只走发现+详情映射, 不下载图片')
    ap.add_argument('--import-after', action='store_true',
                    help='爬取完成后自动导入标注库 (genuine.jsonl + jade.db)')
    args = ap.parse_args()

    if args.spider == 'list':
        print('可用爬虫:')
        for key, cls in SPIDERS.items():
            print(f"  {key:12s} {cls.__doc__ and cls.__doc__.strip().splitlines()[0]}")
        return

    if args.spider not in SPIDERS:
        print(f"未知爬虫: {args.spider} (可用: {', '.join(SPIDERS)})")
        sys.exit(1)

    spider = SPIDERS[args.spider]()
    spider.run(max_items=args.limit, dry_run=args.dry_run)

    if args.import_after and not args.dry_run:
        print(f"\n── 导入标注库: {args.spider} ──")
        from data.scraping.import_museum_data import import_museum
        import_museum(args.spider, db_path=str(REPO_ROOT / 'jade.db'))


if __name__ == '__main__':
    main()
