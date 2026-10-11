# 上线验证

2026-10-11 首次上线到 https://invest-56s.pages.dev 。Cloudflare 部署 4cec17f8-c3c8-402a-ad84-f16c93a2a05e 状态 success。

- 9 项 Python 检查通过：原始脚本 SHA256 未变、报告与公开全部数值/卡片/概览一致、演示数据禁止发布、非有限数值/序列长度校验、EPS 快照 EPS×PE=NDX、交易日/节假日/夏冬时间/提前收盘。
- DOM 集成检查通过：五模块、区间切换、图例开关、EPS 原始节点、数据表、元数据。此检查不包含真实浏览器像素渲染；浏览器控制工具超时，未完成手机/桌面截图检查。
- 生产网页 HTTP 200，Content-Security-Policy 存在；data.json 与本地输出完全一致（数据日期 2026-10-09、五张卡）；app.js/style.css/chart.umd.js/THIRD_PARTY_NOTICES.txt 与本地文件字节完全一致。
- 生产公开文件没有独立数据来源模块、原始请求错误、凭据或演示数据。
- 仅新增并部署 Cloudflare `invest` 项目。「有序」项目没有任何写入。

自动化文件已存入独立私有 GitHub 仓库 zhoupixue/invest。用户已确认配置 CLOUDFLARE_API_TOKEN Secret，并手动运行 Invest daily close。

2026-10-11，运行 https://github.com/zhoupixue/invest/actions/runs/38133677943 在执行任何步骤前失败。用户提供的 Annotation 为 “The job was not started because recent account payments have failed or your spendi”（原文截断）。阻塞位于 GitHub 账户付款或支出限制，尚不能区分具体原因；没有执行 Python 更新或 Cloudflare 部署步骤，因此 Secret 的实际可用性及完整自动更新链路仍待账户限制解除后验证。网站当前保留已验证的 2026-10-09 数据。

随后用户提供的 Billing 截图确认账户 2,000 分钟免费额度已用完。用户明确授权公开 invest 仓库并完成操作，API 已确认 private=false、visibility=public；当前提交的 25 个文本文件中未检出常见凭据格式或硬编码长凭据。

重新运行同一工作流（job 114455857728）后，依赖安装、交易日判断、构建、9 项 Python 检查与 DOM 交互检查全部通过。当前为周日，按设计部署已有真实报告，没有取新数据。最后部署步骤访问 Invest Pages 项目返回 Authentication error [code: 10000]；Wrangler 识别到 Account API Token 及正确账户 ID，但没有成功访问项目。尚需核实该 Token 的 Cloudflare Pages Edit 权限、资源范围及限制，完整自动部署仍未通过。

用户修改 Token 权限后，最终重试 job 114457422174 全部步骤 success；9 项 Python 检查与 DOM 交互检查通过，Wrangler 成功上传并完成生产部署 43080695-1df8-4d93-8050-c861dd684e6e。Cloudflare API 确认该部署为 invest 的 canonical production deployment、branch=main、stage=success。

生产首页再次核验 HTTP 200 且带 CSP；线上 data.json 的五大指标卡片、概览及全部金融序列与原始报告完全一致，demo=false，数据日期 2026-10-09，网站构建更新时间 2026-10-11T11:20:15.238896+00:00。周日手动运行验证了交易日判断、已有数据构建、检查与自动部署链路；实际交易日的取新数据和快照提交仍需首次定时运行检验。工作流调度仍为周一至五 UTC 22:17，未增加生产 push 触发。

2026-10-11 页面调整与网址迁移：新建独立 Pages 项目 ndx5s，精确获得 https://ndx5s.pages.dev 。生产部署 2b542590-04cb-454f-af87-0ac133765768 stage=success、branch=main，代码提交 2408f9c9599d42f69606dc06d02729c2c26e463e。恢复原 HTML 的白底、灰卡片、蓝色选中状态、双列布局和 760px 最大宽度，日期日报与指标标题放大，品牌改为 Invest · NDX投资日报；移除介绍区、右上角小字、图表数据表、数据提示区和页面来源区，保留理解指标说明、更新时间、观测日期、缺失状态与许可署名文件。

本地 9 项 Python 检查与更新后的 DOM 检查通过；GitHub Validate Invest run 38136857329 success。生产首页 HTTP 200，HTML、CSS、JS、Chart.js 和许可文件与本地字节一致，线上五大指标全部数值及原概览与原报告一致，demo=false、date=2026-10-09。每日 Actions 仅将部署目标由 invest 改为 ndx5s，调度和指标逻辑未变。旧 invest 项目保留，「有序」未改动。真实浏览器像素检查仍受浏览器控制工具超时限制。
