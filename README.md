# 市场周报

一套每周更新的中文市场简报流水线，参考用户提供的 `market-brief-main` 静态站点：数据与展示分离、按期归档、来源可追溯、窄栏响应式阅读。

## 每周流程

1. GitHub Actions 每周一北京时间 07:00（UTC 周日 23:00）运行，也可手动触发。
2. 从公开 RSS 源抓取新闻候选，去重并保留原始链接；从 Yahoo Finance chart 接口取主要市场指数/ETF 一周行情。
3. Python 生成带事实数据、来源链接、编辑核查清单的中文周报草稿，存入 `data/YYYY-Www.json`。
4. Actions 上传草稿 artifact。人工核查新闻、行情、解释和免责声明后，再提交 JSON 到仓库；静态站点自动部署。

当前版本不自动生成或发布 AI 投资观点。这样避免把未经核实的机器摘要直接推送给读者。新闻目前作为“候选线索”展示，编辑需阅读原文后补写摘要。

## 本地运行

需要 Python 3.11+，无第三方依赖：

```powershell
python scripts/build_weekly.py --week latest --output data/draft.json
python -m http.server 8000
```

浏览 `http://localhost:8000`。离线/行情接口不可用时会在周报的 `data_warnings` 中记录，不会静默假装取数成功。

## 信源和边界

- 行情：Yahoo Finance chart 接口（非官方、无 SLA；仅作方便的公开行情来源，生产使用可替换为有授权的数据商）。
- 美国宏观：可选 FRED API。配置仓库 Actions secret `FRED_API_KEY` 后拉取利率、通胀、就业的近端观测；不配置时标记为未接入。FRED 注册 key 免费。
- 新闻：`config/sources.json` 中的 RSS。当前包含美联储、BLS、BEA、SEC、CFTC、ECB、中国人民银行、国家统计局、证监会、新华社等官方/一手源，以及少量媒体 RSS；条目只是线索，需打开原文核实。
- 事件日历：官方日历入口在 `config/sources.json` 中，暂不从非稳定网页自动抽取；编辑每周核对后录入。

RSS 可用性、转载/访问限制和数据商条款会变化。请遵守各源条款，不抓取付费墙内容，不将转载摘要当作原始事实。市场数据有延迟和修订的可能。

## 周报内容

- 一句话周势、主要指数/利率/美元/黄金/原油/比特币周变动
- 本周核心事件（编辑填充）与行情反应
- 宏观数据和政策观察（FRED 数值仅展示原始序列变化）
- 下周重要事件日历（编辑核对）
- 新闻候选池（标题、来源、时间、链接）
- 数据时间戳、缺失警告、来源及人工核查清单

不提供个性化投资建议。仅供信息整理与研究参考。

## 部署

1. 将此目录内容推送到 GitHub 仓库。
2. 在仓库 Settings → Pages 选择 GitHub Actions；工作流将 `index.html`、`styles.css`、`app.js`、`data/` 上传并发布。
3. 允许 Actions 写入 Pages artifact。每周草稿独立作为 artifact 保存，不会自动覆盖正式周报。
4. 若接入 FRED，在 Settings → Secrets and variables → Actions 新增 `FRED_API_KEY`。

## 自定义

- 新闻源：编辑 `config/sources.json`。
- 指数/ETF：编辑 `config/markets.json`。
- 周报栏目：编辑 `templates/weekly.json` 与前端渲染器。

