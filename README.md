# NDX5S · 纳指投资看板

手机优先的公开交互式投资日报。独立 Cloudflare Pages 项目 `ndx5s`，生产网址：
https://ndx5s.pages.dev

## 保留原五大指标

`ndx5s_daily.py` 原文件及全部计算、阈值、数据源顺序保持不变。网站读取原报告 JSON，不在前端重新计算金融指标。EPS 每日快照保存在 `data/ndx_fwd_eps.csv`；初始仅一条，原逻辑使用分析师修正趋势。

`web/` 是外置静态界面；`scripts/build_site.py` 校验真实数据并导出静态站点；`scripts/update_daily.py` 检查 NYSE 交易日和收盘时间、调用原脚本、暂存成功结果后更新日报。

页面支持五模块切换、3M/6M/1Y/3Y 区间、图例曲线开关、触摸/悬停数值、指标规则和系统深色主题。EPS 图按原全部趋势节点展示，时间区间按钮禁用，避免改变起点=100 口径。

页面保留数据日期、网站更新时间、各模块原始最新观测日期、覆盖率及数据缺失/滞后提示。旧 HTML 没有生成时间，明确显示「原报告未记录取数完成时间」；新的自动日报会记录真实取数完成时间。页面不显示独立数据来源模块，许可与署名文件由页脚链接提供。

## 本地构建

```sh
python -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/build_site.py
venv/bin/python -m unittest discover -s tests -v
python3 -m http.server 8765 --directory dist
```

仓库已按用户要求改为公开，代码、`reports/latest.html` 与 EPS 快照均可公开访问；Cloudflare 部署目录为 `dist/`。部署凭据只保存在 GitHub Actions Secret。禁止发布 `--demo` 结果；禁止非有限数值、不一致日期/长度与未来数据。取数得到旧日期时自动更新失败，不覆盖上一版网站。

## 自动更新

GitHub Actions `.github/workflows/daily.yml` 每个星期一至五 UTC 22:17（北京时间次日 06:17）启动，在 NYSE 交易日且收盘至少一小时后才取数；夏令时、冬令时、交易所节假日和提前收盘由交易日历判断。GitHub 调度可能延迟。

手动 Run workflow：交易日窗口内取新数据，否则部署仓库中的最新真实报告。每次运行保存 EPS 快照及最新报告，使用原报告生成方式；取数/计算/验证/部署失败会显示为 Actions 失败。

需要设置一个仓库 Actions Secret：`CLOUDFLARE_API_TOKEN`，权限仅为本账户 Cloudflare Pages Edit。账户 ID 已固定，部署命令固定为 `--project-name ndx5s --branch main`。不购买域名，不操作「有序」项目。

```sh
npm ci
npx wrangler pages deploy dist --project-name ndx5s --branch main
```

## 审计

- `docs/IMPLEMENTATION_PLAN.md`：开发前检查与实施方案。
- `docs/DATA_RIGHTS_AUDIT.md`：再分发条款检查，包含尚未得到数据方许可的限制。
- `data/publication_policy.json`：用户明确要求直接使用数据后采用 `operator_directed` 公开模式；不宣称取得第三方许可。
- `web/THIRD_PARTY_NOTICES.txt`：Chart.js MIT 许可。

本项目没有修改「有序」仓库或 Cloudflare 项目。

## SPX 对照曲线

宽度页面仅展示 NDX 的 MA50/MA200 比例，状态保持原四项综合计算口径。VIX 图新增 SPX 实际收盘点位，左轴为 VIX、右轴为 SPX 点位，不做归一化或缩放。SPX 由独立补充脚本读取 Cboe 官方 CSV，失败时尝试原引擎 Yahoo/Stooq 获取函数；缺失或日期未覆盖日报时不绘制替代曲线。真实收盘序列保存于 `data/spx_close.json`，每日工作流同步更新。

## QDII 额度栏目

同一网站顶部切换「纳指日报 / QDII额度」，直达网址 https://ndx5s.pages.dev/#qdii 。数据仅读取用户指定的 FEIXIA 公开首页，A/C 合并但保留各自代码、状态和额度。独立 Actions 每日北京时间 09:00、11:00 检查；自动静默窗口为 23:30 至次日 07:30，首次人工初始化和手动运行除外。源站更新时间为相对提示，采集时间另行记录；失败保留上一版。完整口径、范围及限制见 docs/QDII_INTEGRATION.md。

2026-10-13 页面精简：删除 QDII 标题、采集/源站时间、超时提示、搜索和筛选、份额数量说明及变化记录，仅保留汇总和全部基金卡片；后台仍保留状态和历史。静默时间经用户确认修正为 23:30–次日07:30，白天延迟任务允许更新。
