"""
古玉鉴真 — 东京国立博物馆爬虫 (静态 HTML)

- 搜索: /modules/r_collection/index.php?controller=list
        &search[{key}]={value}&lang=zh_cn&start={n}
  注意: search_kw / mode=search 参数会被站点忽略 (返回默认展厅列表),
        必须用表单真实参数 search[keyword] / search[seisakuchi] 等。
- 搜索轴 (SEARCH_AXES):
  - seisakuchi=中国 106 件已于 2026-10-27 全量处理 (命中玉器 1 件), 停用
  - keyword 轴 (2026-10-28 探测): 石・玉 4 件 / 玉 8 件 / 玛瑙 1 件;
    软玉、翡翠无结果 (站点为全文检索, 藏品描述无此词)
  - 列表页搜索框为 Google CSE 站内搜索, 表单无 bunrui 等结构化下拉
- 图片: 搜索页 M_{n}.jpg 缩略图 → 详情页 .desc-img 内 L_{n}.jpg 主图
        + LL_{n}.jpg 放大图 (同号, 放大图非每件都有)
- 过滤: 材质形状命中中文材质表 (玉/翡翠/玛瑙等) 且 制作地含"中国"
- 详情: controller=dtl&colid={id} — 年代/材质形状/制作地/尺寸/机构管理序号
- 网络: 国内直连 tnm.jp 不通, 需走系统代理 (启动时设 HTTPS_PROXY);
        站点 WAF 对持续请求敏感 (约300请求后 SSL 断连), 建议每日小批量续跑
        (每日 ≤30 请求, 见 docs/scraping_handoff.md)
- 更全的日本馆藏来源: ColBase (colbase.nich.go.jp), 待评估
"""

import re
from typing import Dict, List

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

TNM_BASE = 'https://www.tnm.jp'
SEARCH_TPL = (TNM_BASE + '/modules/r_collection/index.php?controller=list'
              '&search[{key}]={value}&lang=zh_cn&start={start}')
DETAIL_TPL = (TNM_BASE + '/modules/r_collection/index.php'
              '?controller=dtl&colid={colid}&lang=zh_cn')
IMG_TPL = TNM_BASE + '/uploads/r_collection/{size}_{n}.jpg'
PAGE_SIZE = 100


def _strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '').replace('&nbsp;', ' ').strip()


class TnmSpider(BaseJadeSpider):
    """东京国立博物馆玉器藏品爬虫 (静态 HTML, 首个非 API 蜘蛛)。"""

    # 搜索轴: (表单字段, 取值), 2026-10-28 探测结果见模块 docstring
    # 关键词轴结果与制作地轴有重叠, 按 item_id 去重; 软玉/翡翠轴无结果不列
    SEARCH_AXES = [
        ('keyword', '石・玉'),
        ('keyword', '玉'),
        ('keyword', '玛瑙'),
    ]

    def __init__(self, config=None):
        super().__init__(
            name='tnm',
            museum_name='Tokyo National Museum',
            museum_name_cn='东京国立博物馆',
            base_url=TNM_BASE,
            config=config,
        )
        # 国内直连不可达, 走系统代理 (启动时设 HTTPS_PROXY=http://127.0.0.1:7890);
        # 不再 trust_env=False —— VPN TUN 模式下直连可通, 两种模式自适应
        # 站点 WAF 对持续请求敏感 (曾 300+ 请求后 SSL 断连), 放宽延时
        self.config.MIN_DELAY_SEC = 8.0
        self.config.MAX_DELAY_SEC = 15.0

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        items = []
        for key, value in self.SEARCH_AXES:
            start = 0
            while True:
                url = SEARCH_TPL.format(key=key, value=value, start=start)
                html = self.get(url).text
                # 搜索结果: colid → 缩略图 成对出现 (每 <li> 一个藏品)
                pairs = re.findall(
                    r'controller=dtl&colid=([A-Z0-9]+)[^>]*>.*?'
                    r'src=["\']([^"\']*r_collection/M_(\d+)\.jpg)["\']',
                    html, re.S)
                print(f"[tnm] q={key}={value!r} start={start}: {len(pairs)} 件")
                for colid, thumb, n in pairs:
                    items.append({
                        'item_id': colid,
                        'detail_url': DETAIL_TPL.format(colid=colid),
                        # 兜底候选 (详情页未解析出 L/LL 时), M 缩略图会被质量过滤
                        'image_urls': [IMG_TPL.format(size=s, n=n)
                                       for s in ('L', 'LL')],
                    })
                # 分页: 分页器链接均用 pager-next 样式 (含 first/prev),
                # 仅当存在 start 更大的页码链接时继续
                next_starts = [int(x) for x in
                               re.findall(r'start=(\d+)', html) if int(x) > start]
                if not next_starts:
                    break
                start = min(next_starts)
        # 去重 (保持顺序)
        seen = set()
        uniq = []
        for it in items:
            if it['item_id'] not in seen:
                seen.add(it['item_id'])
                uniq.append(it)
        return uniq

    # ── 详情解析 ──

    def parse_detail(self, detail_url: str) -> Dict:
        colid = re.search(r'colid=([A-Z0-9]+)', detail_url or '')
        item_id = colid.group(1) if colid else ''
        try:
            html = self.get(detail_url).text
        except Exception:
            return {'item_id': item_id, 'title': '', 'era': '',
                    'image_urls': [], 'skip_reason': '网络错误'}

        # dt/dd 字段表
        fields: Dict[str, str] = {}
        for k, v in re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>',
                               html, re.S):
            key = _strip_tags(k)
            val = _strip_tags(v)
            if key:
                fields[key] = val
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            title = _strip_tags(m.group(1))

        material = fields.get('材质形状', '')
        place = fields.get('制作地', '')
        era_raw = ' '.join(x for x in [fields.get('年代', ''),
                                       fields.get('时代', ''), title] if x)

        # 过滤: 材质形状字段常为空, 改用 材质形状+标题 联合匹配中文材质表;
        # 制作地须含"中国" (空则放行)
        material_hit = map_material_zh(' '.join(x for x in [material, title] if x))
        if not material_hit or ('中国' not in place and place):
            return {'item_id': item_id, 'title': title, 'era': '',
                    'image_urls': [], 'skip_reason': 'not Chinese jade'}

        # 主图: .desc-img 内 L_{n} 为主图, LL_{n} 为放大图 (同号, 优先 LL)
        groups: List[List[str]] = []
        ll = re.search(r'LL_(\d+)\.jpg', html)
        l = re.search(r'L_(\d+)\.jpg', html)
        candidates = []
        if ll:
            candidates.append(IMG_TPL.format(size='LL', n=ll.group(1)))
        if l:
            candidates.append(IMG_TPL.format(size='L', n=l.group(1)))
        if candidates:
            groups = [candidates]

        # 中文年代映射
        era_result = map_era_zh(era_raw)
        extra = {
            'title': title or '',
            'material_raw': material,
            'dimensions_raw': fields.get('尺寸', ''),
            'page_url': detail_url,
            'accession_number': fields.get('机构管理序号', ''),
            'culture': place,
            'era_raw': era_raw,
            'license': 'TNM 藏品检索页面公开图 (研究用途)',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if is_approx_era_zh(era_raw):
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw,
            'description': '',
            'material': material,
            'dimensions': fields.get('尺寸', ''),
            'source': '东京国立博物馆',
            'image_groups': groups,  # [[LL, L]] 回退链; 空列表回退 discover 候选
            'extra_metadata': extra,
        }
