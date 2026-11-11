# 市场周报

一套每周更新的中文市场简报工作流，沿用参考项目的数据与展示分离、来源可追溯和窄栏响应式阅读方式。

## 每周更新流程

1. GitHub Actions 每周一北京时间 07:00（UTC 周日 23:00）生成草稿；也可以从 **Actions → Build weekly market brief draft → Run workflow** 手动运行。
2. 从本次运行的 **Artifacts** 下载 `weekly-market-brief-draft`，解压得到 `draft.json`。生成器拉取新闻 RSS 候选、公开行情和可选的 FRED 数据；失败的信源会写入警告。
3. 阅读原文，补充本周结论、三条市场驱动、宏观解释和下周日历。区分已核实事实与分析，并保留来源链接。确认后将 JSON 中 `status` 改为 `published`。
4. 把审核后的文件放进仓库 `data/draft.json`，在项目根目录运行：

   ```powershell
   python scripts/publish_weekly.py data/draft.json
   ```

   脚本会检查状态、结论、周一至周五日期和 ISO 周期号，再生成 `data/YYYY-Www.json` 并更新 `data/manifest.json`。
5. 将这三个文件提交到 `main`。Pages 工作流部署网站，首页就会展示新一期并保留历史期数。

草稿 artifact 保留 30 天。未审核草稿不会进入正式目录，也不会被网站展示。

## 本地运行

需要 Python 3.11+，生成脚本使用标准库：

```powershell
python scripts/build_weekly.py --week latest --output data/draft.json
python -m http.server 8000
```

打开 `http://localhost:8000` 查看网站。手动指定周时使用 ISO 格式，例如 `--week 2026-W45`。周度市场表现以周一之前最近一个交易日的收盘价为基准，比较到本周最后一个可用收盘价。

## 自动化和部署设置

- 在仓库 **Settings → Pages** 选择 **GitHub Actions**，网站部署由 `.github/workflows/pages.yml` 完成。
- 每周草稿工作流在 `.github/workflows/weekly.yml`。GitHub Actions 在 UTC 周日 23:00 调度（北京时间周一 07:00）；定时任务可能延迟几分钟。
- 可选：在 **Settings → Secrets and variables → Actions** 添加 `FRED_API_KEY`，接入美国利率、就业与价格指数。未配置时流程仍可运行，并在页面/草稿中标注。

## 信源

- **行情**：Yahoo Finance chart 接口，非官方、无服务保证；适用于个人研究原型。生产用途建议换成有授权、口径稳定的数据供应商。
- **美国宏观**：FRED API，返回原始序列观测。数据发布滞后，部分数值可能修订；应同时核对发布机构原文及同比/环比口径。
- **新闻候选**：配置见 `config/sources.json`。自动采集的只是标题、时间和链接，不能代替阅读原文。当前列为 HTML 的信源只提供人工入口，不会被脚本抓取。
- **日历**：官方入口在 `config/sources.json`；请手动核对发布时间、时区和临时变更。

RSS 可用性、数据覆盖、服务条款和新闻访问限制可能变化。遵守各源条款，不抓付费墙内容，不把二手转载当成原始事实。

## 目录

```text
config/       新闻来源与市场代码
data/         已发布周报与历史索引
scripts/      周报生成、发布校验脚本
templates/    栏目定义
.github/      每周草稿与 Pages 部署工作流
index.html    简报阅读页
app.js        周报渲染与历史导航
styles.css    响应式视觉样式
```

简报仅供信息整理与研究参考，不构成投资建议。

