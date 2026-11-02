# 爬虫值班交接 (Scraping Handoff)

> JadeScrapeDaily 定时任务已删除 (2026-10-30, 用户决定: 电脑需手动开机、
> 代理需手动设置, 定时自动跑无意义)。现为**手动值班模式**: 用户说
> 「继续自动任务」时, 人工会话读取本文件按「下一步」推进, 结束时更新本文件。
> daily_scrape.ps1 / daily_scrape_prompt.txt 留存仓库仅作参考, 不再被调度。

**状态: ACTIVE**
最后更新: 2026-11-02

## 总体进度

| 站点 | 状态 | 图片 | 导入 |
|---|---|---|---|
| cleveland | ✅ 完成 | 578 | ✅ |
| vam | ✅ 完成 | 742 | ✅ |
| met | ✅ 完成 (仅5件可商用图) | 5 | ✅ |
| tnm | ✅ 扩轴完成 (2026-10-28) | 2 | ✅ |
| emuseum | ❌ 已扫描无中国玉器 (2026-10-28) | 0 | - |
| knmdb (京都国立) | ✅ 负结果坐实 (2026-10-31 逐件复核 408 件全非玉, 证据见 skip_log.jsonl) | 0 | - |
| senoku (泉屋博古館) | ✅ 负结果坐实 (2026-11-02 43件逐件留档全非玉, 证据见 scraped_data/senoku/skip_log.jsonl) | 0 | - |
| colbase | ✅ 完成 (2026-11-02, 606件候选 → 309下载导入 / 297拒件留档, 见 skip_log) | 309 | ✅ |
| 出土玉器全集 | 🔶 图书导入 (见 book_importer.py) | - | - |
| 其他 | ⬜ 见下一步 | - | - |

## 下一步 (按优先级推进)

1. **untested 海外站探测** (sites.json): korea, taipei_npm, brooklyn, mfa,
   guimet, asian_art_sf — 探测 → 可行则写蜘蛛
2. **capital_museum** (static_verified) → 静态爬虫
3. **reachable 国内站** (多数 JS 渲染, 需找 API): guobo, henan, hunan, shandong,
   shaanxi, nanjing, shanxi, liaoning, sichuan, guangdong, gansu, guangxi,
   fujian, jiangxi, chongqing, yin_ruins, sanxingdui
4. **gugong** Playwright 骨架落地 (`spiders/domestic/central/gugong.py`)
5. key_required 站点 (freer_sackler, rijksmuseum, harvard) 无 key, 暂缓

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
  前 720 件重建 + 备份 checkpoint.json.bak)。开工前先确认没有并发会话
  (值班代理可用 ListAgents); 同一 spider 绝不并发双开, 并发会造成当日
  请求合计超 500 配额。
- **详情页结构陷阱 (knmdb 0 玉器根因)** (2026-10-30): knmdb 详情页主体是
  `<th>/<td>` 表结构, 列表页才是 `<dt>/<dd>`; 早期 parse_detail 只解析
  dt/dd → 详情字段全空 → 700+ 件全被误判 not Chinese jade (0 下载假象)。
  已修 (th/td 优先 + dt/dd 兜底)。教训: 新站点落地时先抓一个真实详情页
  验证解析字段非空, 再批量跑; 大比例 skip 单一原因时先怀疑解析器。
  另: 列表级可加分类预筛 (排除不可能含玉的大类), 省 ~81% 详情请求。
- **负结果复核手法** (2026-10-31): 从 checkpoint.processed_items 移除目标 ID
  (先备份 .bak) → 重跑同 spider → skip_log.jsonl 逐件留档。skip_log 写入带
  f.flush() 可实时查进度; 而 stdout 重定向到文件时块缓冲, 运行中看日志文件
  不可靠 (进程退出后才落盘)。复核收尾: 全文 grep skip_log 的材质+标题,
  玉系关键词 (玉/翡翠/瑪瑙/玉髄/青金/琥珀/水晶/璧/琮/圭/璜/玦, 中日双形) 零命中
  才算坐实。
- **青铜嵌石非玉器** (2026-10-31): knmdb 408 件复核中发现 2 件青铜器带嵌饰 —
  透彫虺龍文鏡 (13904, 「緑色の石」嵌) 与 銅戈 (20831, 「トルコ石」绿松石象嵌,
  西周)。主材质为青铜, 属青铜器非玉器, 不加材质表 (加 トルコ石 会误标青铜器
  为绿松石, 污染标注库)。
- **WordPress 站枚举手法** (2026-11-02, senoku): WP 站直接拉 /wp-sitemap.xml
  拿全站页面清单 (senoku 61 页), 比翻导航快且不漏; 另注意「coming soon」页的
  真实内容可能藏在 HTML 注释里 (senoku 青铜器馆 4 展厅 19 件条目即如此),
  负结果复核也要扫注释块, 否则会漏件。
- **Nuxt SPA 挖接口手法** (2026-11-02, colbase): 壳页列出的 bundle 里 grep
  `baseURL` 拿 API 基址 + `axios.get` 调参代码; 路由到 API 参数的映射函数
  (getXxxQueryOrThrowFromRoute) 直接给出全部参数名与类型 (required 参数缺失
  返回 400 Bad Request 而非 401/404, 易误判)。API 返回结果含 resultset.count/
  page/limit, limit 上限 100。colbase 偶发 SSL 断连 (约 40 请求后), 加
  try/retry + 8s 退避即可, 非硬限流。
- **colbase media 端点抖动** (2026-11-02): 图片 URL (media/…/image/…) 间歇性
  200/404/ReadTimeout (同 URL 三连测 200/200/404), 且部分藏品只有缩略图变体
  存活; 下载必须带 4-5 次重试 (HTTPError 404 + ConnectionError/ReadTimeout
  都重试), 一轮不重试的 88 件全部假失败。
- **TNM「東洋」分类陷阱** (2026-11-02, colbase): TNM bunrui=東洋陶磁/東洋考古
  不只含中国, 还含印度 (ムガル朝玉器)、中东 (シュメル装身具)、中亚 (前期青銅器
  時代 BMAC ラピスラズリ) — 玉器大国印度莫卧儿玉尤其易混入清玉堆; 过滤必须加
  非中国文明词表 (NCN_ERA_RE)。楽浪 (汉四郡) 属中国汉文化, 不排除。
- **导入流水号防冲突** (2026-11-02): import_museum 的每日流水 base_seq 原用
  count(今日行)+1 起算, 手工删除中间行后 count 空洞会让新行重生成尾部已存在的
  登录号 → 冲突跳过; 已改为 max(今日登录号后缀) 起算, 对删除免疫。
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
