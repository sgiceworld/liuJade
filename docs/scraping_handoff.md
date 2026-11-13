# 爬虫值班交接 (Scraping Handoff)

> JadeScrapeDaily 定时任务已删除 (2026-10-30, 用户决定: 电脑需手动开机、
> 代理需手动设置, 定时自动跑无意义)。现为**手动值班模式**: 用户说
> 「继续自动任务」时, 人工会话读取本文件按「下一步」推进, 结束时更新本文件。
> daily_scrape.ps1 / daily_scrape_prompt.txt 留存仓库仅作参考, 不再被调度。

**状态: ACTIVE**
最后更新: 2026-11-14

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
| untested 海外站探测 | ✅ 完成 (2026-11-03: brooklyn WAF / mfa robots禁搜 / korea 登录 / guimet 无库 / asian_art_sf 无库; **taipei_npm 命中**), 证据 scraped_data/_untested_probe/ | - | - |
| npm (台北故宫) | 🔄 第5天 0 件 (累计2090; 文化期✅商✅西周春秋✅战国✅秦汉✅三国晋南北✅隋唐✅ 五代宋轴续跑中; iiifod 图源 11-12 14:15 起持续宕机 ~35h, 第4/5两天配额基本未用); 剩余 ~1695 | 2090 | ✅ |
| 出土玉器全集 | 🔶 图书导入 (见 book_importer.py) | - | - |
| 其他 | ⬜ 见下一步 | - | - |

## 下一步 (按优先级推进)

1. **npm (台北故宫) 分层抽样续跑**: iiifod 图源 11-12 14:15 起长宕机 (11-14 01:00 仍未恢复, ~35h, 整站 TCP 层不可达 — 根路径/HTTP/HTTPS 全超时, digitalarchive 同馆健康), **先探活再跑批** (python truststore 探活器测 iiifod 图 URL 返 200, 否则跑批白烧 digitalarchive 配额); 恢复后 `HTTPS_PROXY=http://127.0.0.1:7890 /c/Users/LiuCN/AppData/Local/Python/pythoncore-3.14-64/python.exe /d/liuJade/training/scripts/run_spider.py --spider npm --limit N` (单件 3 请求, 1500 配额约 700 件/日 [第3天实测]; 命令须以放行的 python 绝对路径或 HTTPS_PROXY 前缀开头, 勿带 cd 前缀, 否则 Auto 模式 allow 规则不匹配); 跑完 `--import-after` 或单独 import; 12 个时代轴配额见 npm.py SEARCH_AXES, 轴序 A→L; 当前轴: H_五代宋; 剩余 ~1695 ≈ 3 天
2. **capital_museum** — 2026-11-04 复核: Nuxt SPA 藏品列表走客户端 API
   (needs_browser), 与 reachable 国内站同批走 Playwright/挖接口
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
- **配额 vs 熔断** (2026-10-29 教训): 每日配额用尽时 `_respect_rate_limit`
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
  请求合计超配额。
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
- **npm iiifod 连接重置可中断整批** (2026-11-11): iiifod 偶发
  ConnectionResetError(10054) 逃逸逐件异常处理, 使 run() 提前收尾
  (已处理件进度不丢 — finally 里保存 checkpoint; 未轮到件下轮继续)。
  对策: 批次控制在 ~220 件以内 (2h 后台上限内), 中断后直接补跑小批。
  第3天 699 件 = 4 批 (300+220+215+60), 其中 215 批被中断只完成 140,
  补 60 小批后 digitalarchive 恰满 1500 配额正常收尾。
- **iiifod 长宕机 + 逃逸已根治** (2026-11-12): 图源可宕机 23 小时以上
  (11-12 14:15 起, 11-13 13:22 仍未恢复, 仅 14:30 短暂 15 分钟窗口)。
  宕机期间跑批会白烧 digitalarchive 配额 (详情+manifest 拿了、图下不动、
  件不标记已处理, 恢复后全要重拉), 第4天仅成 1 批 +210 件。对策:
  **先探活再跑批** (curl 图 URL 返 200 才开跑)。base.py 已修根治:
  图片连接级错误 (ReadTimeout/ConnectionError/ChunkedEncodingError
  重试后仍失败) 不再逃逸杀批, 改件级失败 — 不标记已处理 (恢复后重试
  不丢图), 连续 10 件图片失败提前收尾防白烧配额 (此逃逸 11-12 曾
  连续杀死 3 个批次: 0 下载早退)。
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
- **npm 搜索 WAF** (2026-11-03): /Collection/Search 的 POST (AJAX JSON) 被 WAF
  拦 555 Unauthorized, 同端点 GET + query 参数直接可用 (MVC model binding
  接受 PageInfo.PageIndex/PageSize 等全部参数, PageSize=300 实测有效);
  每页 list-item + card 双模式渲染同 cid 两份, 必须按 cid 去重;
  list 模式 title 属性带无障碍壳「移至 … 另開新視窗」需剥壳, card-title 更干净。
- **繁体站点文化名双形** (2026-11-03): NPM 时代字段为繁体 (齊家/崧澤/馬家浜/興隆洼/北陰陽營…), era_map 已收录简繁双形; 新接台湾/香港站点时先抽样详情页检查文化名是否全命中, 大比例待OCR先怀疑繁体缺口。
- **npm「西元」纪年误配** (2026-11-03): 详情时代字段带「西元1368-1644年」注记
  (带或不带括号), 其中「元」会被 era_map 金元模式 (辽|遼|金|元) 误配 →
  明器标金元。npm.py 已剥离西元纪年再映射; 跨时代跨度 (明至清/宋或元) 不映射
  落待OCR确认。凡中文站带公元纪年注记者皆须注意此坑。
- **npm IIIF 图源** (2026-11-03): manifest GetJson?cid=&dept=U → canvas 资源
  @id 尺寸段 /full/,300/ 替换为 /full/1600,/ 取大图; iiifod 是 Cantaloupe,
  2048px+ 403 (尺寸上限), 标识符内 / 必须保留 %2F 编码。
- **iiifod 证书 SKI 缺失** (2026-11-03): iiifod.npm.gov.tw 证书缺 Subject
  Key Identifier 扩展, Python 3.14/OpenSSL 严格校验拒绝 (curl/Schannel
  容忍)。解决: pip install truststore + truststore.inject_into_ssl()
  (证书校验保持开启, 仅换 Windows 系统证书库为信任源), 勿用 verify=False。
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
- 爬虫伦理: 单线程、随机延时、1500请求/天/域名 (2026-11-03 上调)、尊重 robots.txt (CLAUDE.md)
