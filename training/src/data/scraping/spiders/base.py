"""
古玉鉴真 — 基础爬虫类

所有博物馆爬虫的基类，提供:
- 统一的请求策略 (随机延时、单线程、固定IP)
- pHash 去重
- 图片质量检测
- EXIF/来源元数据记录
- 断点续传
"""

import time
import random
import json
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from PIL import Image
from io import BytesIO


# ── 爬虫配置 ────────────────────────────────────────────

class ScraperConfig:
    """全局爬虫配置。"""

    # 请求策略
    MIN_DELAY_SEC = 3.0         # 最小请求间隔
    MAX_DELAY_SEC = 8.0         # 最大请求间隔
    MAX_REQUESTS_PER_DAY = 500  # 单站点每日上限
    REQUEST_TIMEOUT = 30         # 请求超时

    # 身份标识
    USER_AGENT = (
        "JadeResearchBot/1.0 "
        "(Academic Research; Ancient Jade Authentication Project; "
        "Contact: jade-research@example.com)"
    )

    # 图片过滤
    MIN_IMAGE_PIXELS = 300       # 最小图片边长
    MAX_IMAGE_FILE_SIZE_MB = 20  # 最大文件大小

    # 输出目录 (绝对路径, 不受启动目录影响: base.py → spiders → scraping → data → src → training → 仓库根)
    OUTPUT_DIR = Path(__file__).resolve().parents[5] / "scraped_data"
    IMAGE_DIR = "images"
    METADATA_FILE = "metadata.jsonl"

    # 断点续传
    CHECKPOINT_FILE = "checkpoint.json"


# ── 基础爬虫 ────────────────────────────────────────────

class BaseJadeSpider(ABC):
    """博物馆玉器图片爬虫基类。

    Usage:
        spider = GugongSpider()
        spider.run()
    """

    def __init__(
        self,
        name: str,
        museum_name: str,
        museum_name_cn: str,
        base_url: str,
        config: ScraperConfig = None,
    ):
        self.name = name
        self.museum_name = museum_name
        self.museum_name_cn = museum_name_cn
        self.base_url = base_url
        self.config = config or ScraperConfig()

        # 输出目录
        self.output_dir = self.config.OUTPUT_DIR / name
        self.image_dir = self.output_dir / self.config.IMAGE_DIR
        self.image_dir.mkdir(parents=True, exist_ok=True)

        # 请求计数: 总数 + 按域名 (500 请求/天/域名)
        self.request_count = 0
        self.request_counts: Dict[str, int] = {}
        self.robots_cache: Dict[str, bool] = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,*/*',
            'Accept-Language': 'zh-CN,en;q=0.9',
        })

        # 去重 + 图片序号 (断点续传后不重复)
        self.seen_hashes: Set[str] = set()
        self.image_seq = 0
        self.processed_items: Set[str] = set()  # 已处理过的藏品 ID (续跑跳过)
        self._load_checkpoint()

    # ── 请求方法 ──

    def get(self, url: str, **kwargs) -> requests.Response:
        """发送 GET 请求 (自动延时 + 按域名限速 + robots 检查 + 连接错误重试 1 次)。"""
        host = urlparse(url).netloc
        if host not in self.robots_cache and not self.check_robots(host):
            raise RuntimeError(f"{self.name}: robots.txt 禁止访问 {host}")
        self._respect_rate_limit(host)
        kwargs.setdefault('timeout', self.config.REQUEST_TIMEOUT)
        for attempt in (1, 2):
            try:
                response = self.session.get(url, **kwargs)
                self.request_count += 1
                self.request_counts[host] = self.request_counts.get(host, 0) + 1
                response.raise_for_status()
                return response
            except (requests.ConnectionError, requests.ChunkedEncodingError) as e:
                if attempt == 2:
                    raise
                print(f"    ⚠ 连接错误重试 ({host}): {type(e).__name__}")
                self._respect_rate_limit(host)

    def _respect_rate_limit(self, host: str):
        """遵守限速规则: 随机延时 + 每日上限 (按域名)。"""
        if self.request_counts.get(host, 0) >= self.config.MAX_REQUESTS_PER_DAY:
            raise RuntimeError(
                f"{self.name}: 域名 {host} 已达每日请求上限 "
                f"({self.config.MAX_REQUESTS_PER_DAY})"
            )
        delay = random.uniform(self.config.MIN_DELAY_SEC, self.config.MAX_DELAY_SEC)
        time.sleep(delay)

    def check_robots(self, host: str) -> bool:
        """检查 robots.txt (每域名只查一次)。

        404/无文件 → 允许; 200 → 按 UA 与 * 判定; 403/401 → 保守禁爬。
        """
        robots_url = f"https://{host}/robots.txt"
        try:
            resp = self.session.get(robots_url, timeout=15)
            if resp.status_code in (401, 403):
                self.robots_cache[host] = False
                print(f"    ⚠ {host} robots.txt {resp.status_code} → 保守禁爬")
                return False
            if resp.status_code != 200:
                self.robots_cache[host] = True
                return True
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
            allowed = parser.can_fetch(self.config.USER_AGENT, robots_url) and \
                parser.can_fetch('*', robots_url)
            self.robots_cache[host] = allowed
            if not allowed:
                print(f"    ⚠ {host} robots.txt 禁止抓取")
            return allowed
        except requests.RequestException:
            # 网络问题不阻断, 由后续请求失败暴露
            return True

    # ── 图片下载 ──

    def download_image(self, url: str, item_id: str = None,
                       extra: Dict = None) -> Optional[Dict]:
        """
        下载单张图片，进行质量检测和去重。

        Args:
            url: 图片 URL
            item_id: 藏品 ID/编号
            extra: 并入 metadata 的详情字段 (title/era_mapped/accession_number 等)

        Returns:
            dict with metadata, or None if rejected
        """
        response = self.get(url, stream=True)
        content = response.content

        # 文件大小检查
        if len(content) > self.config.MAX_IMAGE_FILE_SIZE_MB * 1024 * 1024:
            return None

        # pHash 去重
        img_hash = self._compute_phash(content)
        if img_hash in self.seen_hashes:
            return None

        # 质量检测
        try:
            img = Image.open(BytesIO(content))
            w, h = img.size
            if w < self.config.MIN_IMAGE_PIXELS or h < self.config.MIN_IMAGE_PIXELS:
                return None
        except Exception:
            return None

        # 保存文件 (序号自增, 断点续传后不重复)
        while True:
            file_name = f"{self.name}_{self.image_seq:06d}.jpg"
            file_path = self.image_dir / file_name
            self.image_seq += 1
            if not file_path.exists():
                break
        with open(file_path, 'wb') as f:
            f.write(content)

        # 记录元数据
        self.seen_hashes.add(img_hash)
        metadata = {
            'museum': self.museum_name,
            'museum_cn': self.museum_name_cn,
            'source_url': url,
            'item_id': item_id,
            'file_path': str(file_path),
            'file_name': file_name,
            'file_size_bytes': len(content),
            'width': w,
            'height': h,
            'phash': img_hash,
            'downloaded_at': datetime.now().isoformat(),
        }
        if extra:
            metadata.update(extra)

        # 追加到 metadata.jsonl
        self._append_metadata(metadata)
        self._save_checkpoint()

        return metadata

    # ── pHash ──

    @staticmethod
    def _compute_phash(image_bytes: bytes, hash_size: int = 16) -> str:
        """计算图片的感知哈希 (用于去重)。"""
        from PIL import Image
        import numpy as np

        img = Image.open(BytesIO(image_bytes)).convert('L')
        img = img.resize((hash_size + 1, hash_size), Image.LANCZOS)
        pixels = np.array(img, dtype=np.float32)

        diff = pixels[:, 1:] - pixels[:, :-1]
        hash_bits = (diff > 0).flatten()
        hash_str = ''.join('1' if b else '0' for b in hash_bits)

        # 转 hex
        return hex(int(hash_str, 2))[2:].zfill(hash_size * 2)

    # ── 元数据持久化 ──

    def _append_metadata(self, metadata: Dict):
        """追加一条元数据到 JSONL 文件。"""
        meta_file = self.output_dir / self.config.METADATA_FILE
        with open(meta_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
            f.flush()

    # ── 断点续传 ──

    def _load_checkpoint(self):
        """加载断点续传状态。"""
        ckpt_file = self.output_dir / self.config.CHECKPOINT_FILE
        if ckpt_file.exists():
            with open(ckpt_file, encoding='utf-8') as f:
                data = json.load(f)
                self.seen_hashes = set(data.get('seen_hashes', []))
                self.request_count = data.get('request_count', 0)
                self.request_counts = data.get('request_counts', {})
                self.image_seq = data.get('image_seq', 0)
                self.processed_items = set(data.get('processed_items', []))
                # 恢复已下载图片的 hash
                meta_file = self.output_dir / self.config.METADATA_FILE
                if meta_file.exists():
                    with open(meta_file, encoding='utf-8') as mf:
                        for line in mf:
                            try:
                                rec = json.loads(line)
                                if 'phash' in rec:
                                    self.seen_hashes.add(rec['phash'])
                            except json.JSONDecodeError:
                                continue
        # checkpoint 缺失时从 images 目录恢复最大序号
        if self.image_seq == 0 and self.image_dir.exists():
            max_seq = 0
            for p in self.image_dir.glob(f"{self.name}_*.jpg"):
                m = re.search(r'_(\d+)\.jpg$', p.name)
                if m:
                    max_seq = max(max_seq, int(m.group(1)))
            self.image_seq = max_seq + 1

    def _save_checkpoint(self):
        """保存断点续传状态。"""
        ckpt_file = self.output_dir / self.config.CHECKPOINT_FILE
        with open(ckpt_file, 'w', encoding='utf-8') as f:
            json.dump({
                'seen_count': len(self.seen_hashes),
                'request_count': self.request_count,
                'request_counts': self.request_counts,
                'image_seq': self.image_seq,
                'processed_items': sorted(self.processed_items),
                'last_updated': datetime.now().isoformat(),
                # 不保存完整 hash (太大)，从 metadata.jsonl 恢复
            }, f, ensure_ascii=False, indent=2)

    # ── 抽象方法 ──

    @abstractmethod
    def discover_items(self) -> List[Dict]:
        """
        发现藏品列表页的条目。

        Returns:
            List of dicts with keys:
                - item_id: 藏品ID/编号
                - title: 藏品名称
                - era: 年代 (如有)
                - detail_url: 详情页 URL
                - image_urls: 图片 URL 列表
        """
        pass

    @abstractmethod
    def parse_detail(self, detail_url: str) -> Dict:
        """
        解析藏品详情页，获取完整元数据。

        Returns:
            dict with:
                - item_id, title, era, description,
                - material, dimensions, source,
                - image_urls (高清图)
        """
        pass

    # ── 主循环 ──

    def run(self, max_items: int = None, dry_run: bool = False) -> int:
        """
        执行爬虫主循环。

        Args:
            max_items: 最多处理 N 件藏品 (调试/日常限流)
            dry_run: 只走发现+详情映射, 不下载图片

        Returns:
            下载的图片数量
        """
        print(f"[{self.name}] Starting crawl: {self.museum_name_cn}")
        print(f"  Output: {self.output_dir}")
        print(f"  Rate limit: {self.config.MIN_DELAY_SEC}-{self.config.MAX_DELAY_SEC}s delay, "
              f"max {self.config.MAX_REQUESTS_PER_DAY} req/day/domain")

        downloaded = 0
        skipped = 0

        try:
            items = self.discover_items()
            if max_items:
                items = items[:max_items]
            print(f"[{self.name}] Processing {len(items)} items")

            for item in items:
                # 获取详情页数据
                detail = self.parse_detail(item.get('detail_url', ''))
                if detail.get('skip_reason'):
                    skipped += 1
                    continue
                image_urls = detail.get('image_urls', item.get('image_urls', []))

                for url in image_urls:
                    if dry_run:
                        print(f"  [dry-run] {item.get('item_id')}: "
                              f"{detail.get('title', '')[:40]} → {url[:80]}")
                        continue
                    metadata = self.download_image(
                        url, item_id=item.get('item_id'),
                        extra=detail.get('extra_metadata'),
                    )
                    if metadata:
                        downloaded += 1
                        if downloaded % 10 == 0:
                            print(f"[{self.name}] Downloaded {downloaded} images...")

        except KeyboardInterrupt:
            print(f"\n[{self.name}] Interrupted. Progress saved.")
        except Exception as e:
            print(f"[{self.name}] Error: {e}")
        finally:
            self._save_checkpoint()

        print(f"[{self.name}] Done. Downloaded {downloaded} images "
              f"({skipped} skipped). Total requests: {self.request_count}")
        return downloaded
