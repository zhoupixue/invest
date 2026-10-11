# Invest · 投资日报

手机优先的公开交互式投资日报。独立 Cloudflare Pages 项目 `invest`，生产网址：
https://invest-56s.pages.dev

## 保留原五大指标

`investment_daily.py` 原文件及全部计算、阈值、数据源顺序保持不变。网站读取原报告 JSON，不在前端重新计算金融指标。EPS 每日快照保存在 `data/ndx_fwd_eps.csv`；初始仅一条，原逻辑使用分析师修正趋势。

`web/` 是外置静态界面；`scripts/build_site.py` 校验真实数据并导出静态站点；`scripts/update_daily.py` 检查 NYSE 交易日和收盘时间、调用原脚本、暂存成功结果后更新日报。

页面支持五模块切换、3M/6M/1Y/3Y 区间、图例曲线开关、触摸/悬停数值、指标规则、无障碍数据表和系统深色主题。EPS 图按原全部趋势节点展示，时间区间按钮禁用，避免改变起点=100 口径。

页面保留数据日期、网站更新时间、各模块原始最新观测日期、覆盖率及数据缺失/滞后提示。旧 HTML 没有生成时间，明确显示「原报告未记录取数完成时间」；新的自动日报会记录真实取数完成时间。页面不显示独立数据来源模块，署名位于页脚。

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

需要设置一个仓库 Actions Secret：`CLOUDFLARE_API_TOKEN`，权限仅为本账户 Cloudflare Pages Edit。账户 ID 已固定，部署命令固定为 `--project-name invest --branch main`。不购买域名，不操作「有序」项目。

```sh
npm ci
npx wrangler pages deploy dist --project-name invest --branch main
```

## 审计

- `docs/IMPLEMENTATION_PLAN.md`：开发前检查与实施方案。
- `docs/DATA_RIGHTS_AUDIT.md`：再分发条款检查，包含尚未得到数据方许可的限制。
- `data/publication_policy.json`：用户明确要求直接使用数据后采用 `operator_directed` 公开模式；不宣称取得第三方许可。
- `web/THIRD_PARTY_NOTICES.txt`：Chart.js MIT 许可。

本项目没有修改「有序」仓库或 Cloudflare 项目。
