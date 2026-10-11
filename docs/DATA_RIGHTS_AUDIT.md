# 数据再分发检查

检查日期 2026-10-11。此文档记录检查结果，不是许可证书。

| 来源 | 检查结果 | 官方材料 |
| --- | --- | --- |
| Yahoo / yfinance | yfinance 明确提示 Yahoo API 仅供个人使用，开源代码许可不授予数据许可；未找到项目许可证据 | https://ranaroussi.github.io/yfinance/ |
| Cboe VIX CSV | Cboe 网站条款第 2 节限制个人非商业使用以外的公开展示和再分发；未找到项目书面授权 | https://www.cboe.com/terms/ |
| Nasdaq / FRED NASDAQ100 | 序列标注 Nasdaq 第三方版权；FRED 作为备用源不自动消除限制 | https://fred.stlouisfed.org/series/NASDAQ100/ |
| Slickcharts 成分和权重 | 条款未明确授予公开数据再分发权；未找到项目许可证据 | https://www.slickcharts.com/terms |
| Stooq | 未找到项目再分发许可，备用源未获核准 | https://stooq.com/db/h/ |
| Treasury / FRED DFII10 | 政府原始数据；DFII10 标注 Public Domain: Citation Requested；展示时保留署名，不把第三方版权序列一起当作公有数据 | https://fred.stlouisfed.org/series/DFII10 |
| Wikipedia / GitHub 成分表 | 原代码只用于取成分列表；列表、权重、价格、派生指标分别核对，不能用列表的开放许可覆盖 Yahoo 行情 | https://github.com/datasets/s-and-p-500-companies |
| Chart.js 4.4.1 | MIT；随网站提供完整 MIT 文本 | https://github.com/chartjs/Chart.js/blob/v4.4.1/LICENSE.md |

用户在检查结果告知后要求“不要保留授权待核实，直接使用即可”。公开构建因此采用 operator_directed 模式，展示原始报告真实数据；没有把此指令标记为数据方授予许可，也没有宣称授权检查已通过。

原报告仅包含非 demo 数据。原计算脚本不修改，原数据源、备用源和计算规则不变。页面无独立数据来源模块，必要署名在页脚保留。
