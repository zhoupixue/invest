# 上线验证

2026-10-11 首次上线到 https://invest-56s.pages.dev 。Cloudflare 部署 4cec17f8-c3c8-402a-ad84-f16c93a2a05e 状态 success。

- 9 项 Python 检查通过：原始脚本 SHA256 未变、报告与公开全部数值/卡片/概览一致、演示数据禁止发布、非有限数值/序列长度校验、EPS 快照 EPS×PE=NDX、交易日/节假日/夏冬时间/提前收盘。
- DOM 集成检查通过：五模块、区间切换、图例开关、EPS 原始节点、数据表、元数据。此检查不包含真实浏览器像素渲染；浏览器控制工具超时，未完成手机/桌面截图检查。
- 生产网页 HTTP 200，Content-Security-Policy 存在；data.json 与本地输出完全一致（数据日期 2026-10-09、五张卡）；app.js/style.css/chart.umd.js/THIRD_PARTY_NOTICES.txt 与本地文件字节完全一致。
- 生产公开文件没有独立数据来源模块、原始请求错误、凭据或演示数据。
- 仅新增并部署 Cloudflare `invest` 项目。「有序」项目没有任何写入。

自动化文件已存入独立私有 GitHub 仓库 zhoupixue/invest，待 CLOUDFLARE_API_TOKEN Secret 配置后，需手动运行一次 Actions 验证完整部署链路。
