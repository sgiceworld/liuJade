# 爬虫值班交接 (Scraping Handoff)

> 每日自动爬虫代理 (JadeScrapeDaily 计划任务, 08:50) 读取本文件推进工作。
> 人工修改「状态」为 DONE 即可停掉每日任务; 改回 ACTIVE 重新激活。

**状态: ACTIVE**
最后更新: 2026-10-29

## 总体进度

| 站点 | 状态 | 图片 | 导入 |
|---|---|---|---|
| cleveland | ✅ 完成 | 578 | ✅ |
| vam | ✅ 完成 | 742 | ✅ |
| met | ✅ 完成 (仅5件可商用图) | 5 | ✅ |
| tnm | ✅ 扩轴完成 (2026-10-28) | 2 | ✅ |
| emuseum | ❌ 已扫描无中国玉器 (2026-10-28) | 0 | - |
| knmdb (京都国立) | 🔄 发现完成, 搜索模式直达玉器中 (2026-10-29) | 0 | - |
| 出土玉器全集 | 🔶 图书导入 (见 book_importer.py) | - | - |
| 其他 | ⬜ 见下一步 | - | - |

## 下一步 (按优先级推进)

1. **knmdb 搜索轴直达玉器** (2026-10-29 起): 全库 150 页已扫完, 2194 件
   中国候选已缓存 (_discovered.json, 7 天有效); 前 700 件详情全为书画/陶瓷
   (非玉, 顺序磨要 3+ 天)。改用全文搜索直达:
   `python scripts/run_spider.py --spider knmdb --search-kw 玉`
   (每日首个; 之后依次 翡翠/瑪瑙/玛瑙/水晶/琥珀/青金石/碧玉/玉髄 —
   日站材质用日文汉字, 瑪瑙=玛瑙, 玉髄=玉髓)。搜索命中即进详情+下载,
   与全库扫描共享 checkpoint (processed_items) 自动去重。
   搜索轴全部跑完后, 兜底无关键词全库续跑磨剩余 ~1494 件 (预计 3-4 天)。
2. **senoku (泉屋博古館)** 探测: sen-oku.or.jp/kyoto/collection/database/ —
   页面 18KB 无静态链接 (疑 JS 渲染), 需挖接口; 住友收藏中国青铜器/玉器
3. **ColBase 评估**: colbase.nich.go.jp — 注意: JS SPA (首页仅 3KB 壳),
   需先挖 JS bundle 找 API; 覆盖全日本馆藏 (未指定级别也收), 值得投入
4. **untested 海外站探测** (sites.json): korea, taipei_npm, brooklyn, mfa,
   guimet, asian_art_sf — 探测 → 可行则写蜘蛛
5. **capital_museum** (static_verified) → 静态爬虫
6. **reachable 国内站** (多数 JS 渲染, 需找 API): guobo, henan, hunan, shandong,
   shaanxi, nanjing, shanxi, liaoning, sichuan, guangdong, gansu, guangxi,
   fujian, jiangxi, chongqing, yin_ruins, sanxingdui
7. **gugong** Playwright 骨架落地 (`spiders/domestic/central/gugong.py`)
8. key_required 站点 (freer_sackler, rijksmuseum, harvard) 无 key, 暂缓

## 完成定义

- 所有 reachable/verified 站点已有可用爬虫且至少跑过一批数据
- 数据全部导入标注库 (genuine.jsonl + jade.db) 并提交推送
- 将本文件「状态」改为 DONE

## 已知坑 (勿重蹈)

- **海外站点必须走代理** 127.0.0.1:7890 (包装脚本已注入 HTTPS_PROXY; 手动运行也要设)
- **TNM**: search_kw/mode=search 参数被忽略, 必须用 controller=list + search[...] 表单参数
- **TNM**: 分页器链接全部带 pager-next 样式, 判断翻页要比较 start 数值
- **TNM**: 列表页搜索框是 Google CSE 站内搜索, 无 bunrui 等结构化下拉;
  关键词轴全文命中「种别: 考古>材质>石・玉」类目文本, 会混入石雕/画像石等非玉
  (详情级 材质形状+标题 联合过滤已兜住); 软玉/翡翠关键词 0 结果
- **TNM**: 材质形状字段常为空, 过滤必须联合标题匹配 (否则漏 玛瑙珠 类藏品)
- **WAF**: tnm.jp 约300请求后 SSL 断连; 遵守爬虫限速 (MIN/MAX_DELAY), 每日小批量
  (每日 ≤30 请求, 27 请求/日 实测安全)
- **GBK 控制台**: run_spider.py 已统一 UTF-8 输出
- **断点续传**: processed_items 存在 checkpoint.json, 续跑自动跳过
- **配额 vs 熔断** (2026-10-29 教训): 每日 500 配额用尽时 `_respect_rate_limit`
  抛 RuntimeError, 曾被 parse_detail 的 `except Exception` 吞掉伪装成网络错误,
  触发 20 次/180s 熔断循环空转 3.7h。已修: base.py 主循环每件前
  `_check_daily_quota()` 前置检查 + knmdb.py except 收窄为
  `requests.exceptions.RequestException` (RuntimeError 正常传播收尾)
- **日站材质日文汉字**: 瑪瑙=玛瑙, 玉髄=玉髓 (era_map MATERIAL_MAP_ZH 已加);
  搜索关键词也要中日双形都试
- **列表页末件**: rows 正则依赖「下一条 item 或 pager」做边界, 已加 `\Z`
  兜底防末件漏匹配
- **每日任务代理竞态** (2026-10-29): 开机后 Clash 未就绪时定时任务
  ECONNREFUSED; daily_scrape.ps1 已加 pre-flight (等 7890 端口, 20s×30,
  超时干净退出)
- 爬虫伦理: 单线程、随机延时、500请求/天/域名、尊重 robots.txt (CLAUDE.md)
