# 爬虫值班交接 (Scraping Handoff)

> 每日自动爬虫代理 (JadeScrapeDaily 计划任务, 08:50) 读取本文件推进工作。
> 人工修改「状态」为 DONE 即可停掉每日任务; 改回 ACTIVE 重新激活。

**状态: ACTIVE**
最后更新: 2026-10-30

## 总体进度

| 站点 | 状态 | 图片 | 导入 |
|---|---|---|---|
| cleveland | ✅ 完成 | 578 | ✅ |
| vam | ✅ 完成 | 742 | ✅ |
| met | ✅ 完成 (仅5件可商用图) | 5 | ✅ |
| tnm | ✅ 扩轴完成 (2026-10-28) | 2 | ✅ |
| emuseum | ❌ 已扫描无中国玉器 (2026-10-28) | 0 | - |
| knmdb (京都国立) | 🔄 全库续跑中 (已处理 1105 件全非玉, 剩 ~1089 件, 2026-10-30) | 0 | - |
| 出土玉器全集 | 🔶 图书导入 (见 book_importer.py) | - | - |
| 其他 | ⬜ 见下一步 | - | - |

## 下一步 (按优先级推进)

1. **knmdb 全库续跑 (兜底)** (2026-10-30 起): 搜索轴 9 关键词全部 0 中国玉器
   (结论: sf= 搜索不索引 材質・技法, 只命中作品名/作者文本; 玉 的 25 件中国候选
   全是作者名/画题含玉的书画)。玉器只能靠全库续跑磨详情:
   `python scripts/run_spider.py --spider knmdb --import-after`
   (无 search-kw, 自动用 _discovered.json 缓存, 7 天有效至 ~2026-11-05)。
   进度 (2026-10-30): processed 1105 件全部非玉 (前 1105 件无玉器),
   剩余 ~1089 件, 每日 ~420 件详情节奏, 预计 2-3 天磨完。发现缓存过期前
   (2026-11-05) 需重扫或提前续命。注意 checkpoint.json.bak 为 720 件进度备份
   (10-30 被并发会话清空后重建), 缓存/checkpoint 任何异常可对照恢复。
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
- **checkpoint 竞态 / 会话并发** (2026-10-30 教训): 本机两个 Claude 会话同时跑
  knmdb 会互相覆盖 checkpoint.json (processed_items 曾被清空, 已用发现缓存
  前 720 件重建 + 备份 checkpoint.json.bak)。另一会话还会临时替换
  _discovered.json (切成已处理区之后的片段) 事后 cp -p 还原 —— 值班代理
  读到 385 件「缓存」时勿惊, 先看文件 mtime/条目数是否被并发会话动过。
  开工前先确认没有并发会话 (值班代理可用 ListAgents); 同一 spider 绝不并发
  双开, 并发会造成当日请求合计超 500 配额。
- **Bash 后台命令 10 分钟时限** (2026-10-30 教训): run_in_background 默认
  600s 超时被杀, 长任务 (全库续跑 ~40 分钟) 必须显式 timeout (上限 7200000);
  被硬杀会丢内存中的 processed 进度 (checkpoint 不会保存)。另外 WindowsApps
  python 别名 (shim) 有诡异延迟/respawn, 跑长任务用
  `/c/Users/LiuCN/AppData/Local/Python/pythoncore-3.14-64/python.exe` 直连。
- **0 下载轴退出码** (2026-10-30 已修): 关键词轴 0 下载时 metadata.jsonl
  不存在, import_museum 抛 SystemExit 使每日任务非零码收尾; run_spider.py
  已改为跳过导入并正常退出
- **jade.db 主键**: 导入用馆方 item_id 作 JadePiece.id; knmdb 纯数字 ID
  (4-33128) 与库内已有数字 ID (cleveland/met 42188+) 无交集, 但新站点接入
  前要先查 ID 区间避免冲突
- 爬虫伦理: 单线程、随机延时、500请求/天/域名、尊重 robots.txt (CLAUDE.md)
