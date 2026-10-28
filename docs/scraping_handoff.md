# 爬虫值班交接 (Scraping Handoff)

> 每日自动爬虫代理 (JadeScrapeDaily 计划任务, 08:50) 读取本文件推进工作。
> 人工修改「状态」为 DONE 即可停掉每日任务; 改回 ACTIVE 重新激活。

**状态: ACTIVE**
最后更新: 2026-10-28

## 总体进度

| 站点 | 状态 | 图片 | 导入 |
|---|---|---|---|
| cleveland | ✅ 完成 | 578 | ✅ |
| vam | ✅ 完成 | 742 | ✅ |
| met | ✅ 完成 (仅5件可商用图) | 5 | ✅ |
| tnm | ✅ 扩轴完成 (2026-10-28) | 2 | ✅ |
| 出土玉器全集 | 🔶 图书导入 (见 book_importer.py) | - | - |
| 其他 | ⬜ 见下一步 | - | - |

## 下一步 (按优先级推进)

1. **ColBase 评估**: colbase.nich.go.jp 国立文化財機構統合検索 — 若 API/静态友好,
   新建 colbase 蜘蛛 (TNM 在线模块仅约500件展品, ColBase 覆盖更全)
3. **untested 海外站探测** (sites.json): korea, taipei_npm, brooklyn, mfa,
   guimet, asian_art_sf — 探测 → 可行则写蜘蛛
4. **capital_museum** (static_verified) → 静态爬虫
5. **reachable 国内站** (多数 JS 渲染, 需找 API): guobo, henan, hunan, shandong,
   shaanxi, nanjing, shanxi, liaoning, sichuan, guangdong, gansu, guangxi,
   fujian, jiangxi, chongqing, yin_ruins, sanxingdui
6. **gugong** Playwright 骨架落地 (`spiders/domestic/central/gugong.py`)
7. key_required 站点 (freer_sackler, rijksmuseum, harvard) 无 key, 暂缓

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
- 爬虫伦理: 单线程、随机延时、500请求/天/域名、尊重 robots.txt (CLAUDE.md)
