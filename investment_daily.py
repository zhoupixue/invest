#!/usr/bin/env python3
"""
投资日报：免费数据源取数 + 指标计算 + 生成交互式 HTML 报告

安装：pip install yfinance pandas numpy requests lxml
运行：python investment_daily.py                 # 正常运行
      python investment_daily.py --proxy http://127.0.0.1:7890
      python investment_daily.py --demo          # 不联网，用模拟数据检查版式
输出：reports/investment_daily_YYYY-MM-DD.html、reports/latest.html
      data/ndx_fwd_eps.csv（Forward EPS 每日快照，趋势靠它积累）
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import webbrowser

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
NOTES = []      # 异常、备源、覆盖率说明
SOURCES = {}    # 模块 -> [实际来源, 最新观测日期]
N_VIEW = 756    # 图表保留的交易日数（约 3 年）


def note(msg):
    print("[!]", msg, file=sys.stderr)
    NOTES.append(msg)


def get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def first_ok(label, fns):
    """依次尝试各来源，成功即返回；全部失败返回 None（标记数据缺失）。"""
    for name, fn in fns:
        try:
            s = fn()
            if s is None or len(s) == 0:
                raise ValueError("空数据")
            SOURCES[label] = [name, str(s.index.max().date())]
            return s
        except Exception as e:  # noqa: BLE001
            note(f"{label}：{name} 失败（{type(e).__name__}: {str(e)[:80]}）")
    note(f"{label}：所有来源失败，标记为数据缺失")
    return None


# ---------------------------------------------------------------- 数据源
def yf_hist(sym, period="max"):
    import yfinance as yf
    last = None
    for wait in (0, 20, 40):          # 被 Yahoo 限流时自动等待后重试
        time.sleep(wait)
        try:
            h = yf.Ticker(sym).history(period=period, auto_adjust=False)
            s = h["Close"].dropna()
            if len(s) == 0:
                raise ValueError("空数据")
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
            return s[~s.index.duplicated()]
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def stooq(sym):
    txt = get(f"https://stooq.com/q/d/l/?s={sym}&i=d").text
    if not txt.lstrip().startswith("Date"):
        raise ValueError("Stooq 未返回行情（可能被限流或需要验证）")
    df = pd.read_csv(io.StringIO(txt), parse_dates=["Date"], index_col="Date")
    return df["Close"].dropna()


def cboe_vix():
    txt = get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv").text
    df = pd.read_csv(io.StringIO(txt))
    df["DATE"] = pd.to_datetime(df["DATE"])
    return df.set_index("DATE")["CLOSE"].astype(float).dropna()


def fred(series):
    txt = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}").text
    df = pd.read_csv(io.StringIO(txt))
    d, v = df.columns[:2]
    s = pd.Series(pd.to_numeric(df[v], errors="coerce").values, index=pd.to_datetime(df[d]))
    return s.dropna()


def treasury_real():
    y0 = dt.date.today().year
    parts = []
    for y in range(y0 - 3, y0 + 1):
        u = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
             f"daily-treasury-rates.csv/{y}/all?type=daily_treasury_real_yield_curve"
             f"&field_tdr_date_value={y}&page&_format=csv")
        df = pd.read_csv(io.StringIO(get(u).text))
        df["Date"] = pd.to_datetime(df["Date"])
        parts.append(df.set_index("Date")["10 YR"])
    return pd.concat(parts).sort_index().dropna()


def wiki_tables(url):
    return pd.read_html(io.StringIO(get(url).text))


def clean_syms(series):
    import re
    out = [str(x).strip().replace(".", "-") for x in series.dropna()]
    return [x for x in out if re.fullmatch(r"[A-Z0-9\-]{1,6}", x)]


def find_col(t, keys):
    for c in t.columns:
        name = " ".join(map(str, c)) if isinstance(c, tuple) else str(c)
        if any(k in name.lower() for k in keys):
            return c
    return None


def wiki_pick(url, lo, hi, what):
    tabs = wiki_tables(url)
    for t in tabs:
        c = find_col(t, ("ticker", "symbol"))
        if c is not None and lo <= len(t) <= hi:
            r = clean_syms(t[c])
            if len(r) >= lo:
                return r
    info = "; ".join(f"{len(t)}行/{[str(x)[:10] for x in list(t.columns)[:3]]}" for t in tabs[:10])
    raise ValueError(f"未找到{what}成分表；页面表格：{info}")


def sp500_wiki():
    return wiki_pick("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 400, 600, "SPX")


def ndx_wiki():
    return wiki_pick("https://en.wikipedia.org/wiki/Nasdaq-100", 85, 130, "NDX")


def sp500_github():
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    return clean_syms(pd.read_csv(io.StringIO(get(url).text))["Symbol"])


def slick_symbols(page):
    return clean_syms(wiki_tables(f"https://www.slickcharts.com/{page}")[0]["Symbol"])


def first_list(label, fns):
    for name, fn in fns:
        try:
            r = fn()
            if len(r) < 50:
                raise ValueError(f"只得到 {len(r)} 只")
            return r
        except Exception as e:  # noqa: BLE001
            note(f"{label}：{name} 失败（{type(e).__name__}: {str(e)[:150]}）")
    note(f"{label}：所有来源失败")
    return None


def slick_weights():
    t = wiki_tables("https://www.slickcharts.com/nasdaq100")[0]
    w = pd.Series(t["Weight"].astype(str).str.rstrip("%").astype(float).values,
                  index=t["Symbol"].astype(str).str.replace(".", "-", regex=False))
    return w / w.sum()


def download_closes(tickers, period="4y", chunk=80):
    import yfinance as yf
    out = []
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        for attempt in range(3):
            try:
                df = yf.download(part, period=period, interval="1d", auto_adjust=True,
                                 progress=False, threads=True)["Close"]
                if isinstance(df, pd.Series):
                    df = df.to_frame(part[0])
                out.append(df)
                break
            except Exception:  # noqa: BLE001
                time.sleep(3 * (attempt + 1))
        else:
            note(f"成分股行情：第 {i // chunk + 1} 批下载失败")
        time.sleep(1)
    df = pd.concat(out, axis=1)
    df = df.loc[:, ~df.columns.duplicated()]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def breadth(closes):
    res = {}
    for n in (50, 200):
        m = closes.rolling(n).mean()
        valid = m.notna() & closes.notna()
        cnt = valid.sum(axis=1)
        pct = ((closes > m) & valid).sum(axis=1) / cnt.replace(0, np.nan) * 100
        res[n] = pct.where(cnt >= 0.6 * closes.shape[1])
    return res


def ndx_eps(tickers, weights, ndx_last):
    """逐只取 forwardEps/价格/eps_trend，按权重做调和加权。"""
    import yfinance as yf
    rows = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info
            try:
                tr = tk.eps_trend
            except Exception:  # noqa: BLE001
                tr = None
            rows.append(dict(t=t, px=info.get("currentPrice") or info.get("regularMarketPrice"),
                             fe=info.get("forwardEps"), mc=info.get("marketCap"), tr=tr))
        except Exception as e:  # noqa: BLE001
            note(f"Forward EPS：{t} 获取失败（{type(e).__name__}）")
        time.sleep(0.3)
    df = pd.DataFrame(rows).set_index("t")
    for c in ("px", "fe", "mc"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    wsrc = "Slickcharts 权重"
    w = weights.reindex(df.index) if weights is not None else None
    if w is None or w.isna().mean() > 0.3:
        w = df["mc"] / df["mc"].sum()
        wsrc = "市值近似权重"
    w = (w / w.sum()).fillna(0)
    ok = (df["fe"] > 0) & (df["px"] > 0) & (w > 0)
    if ok.sum() < 20:
        raise ValueError(f"有效 EPS 成分股仅 {ok.sum()} 只")
    ey = ((w[ok] / w[ok].sum()) * (df["fe"][ok] / df["px"][ok])).sum()
    res = dict(eps=ndx_last * ey, pe=1 / ey, cov=float(w[ok].sum() / w.sum()),
               wsrc=wsrc, n=int(ok.sum()))
    return res, df, w


def eps_trend_levels(df, w):
    """用 yfinance eps_trend（90/60/30/7 天前→当前）聚合“明年 EPS”修正，起点=100。"""
    cols = ["90daysAgo", "60daysAgo", "30daysAgo", "7daysAgo", "current"]
    offs = [90, 60, 30, 7, 0]
    rows = {}
    for t, tr in df["tr"].items():
        if isinstance(tr, pd.DataFrame) and "+1y" in tr.index and set(cols) <= set(tr.columns):
            v = pd.to_numeric(tr.loc["+1y", cols], errors="coerce")
            if (v > 0).all():
                rows[t] = v.values
    if len(rows) < 20:
        return None
    a = pd.DataFrame(rows, index=offs).T
    ww = w.reindex(a.index).fillna(0)
    ww = ww / ww.sum()
    lvl = {o: float(100 * (ww * (a[o] / a[90])).sum()) for o in offs}
    return lvl, float((a[0] > a[30]).mean()), len(rows)


def update_snapshots(path, date, ndx, res):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cols = ["date", "ndx", "fwd_eps", "fwd_pe", "coverage", "weight_src"]
    old = pd.read_csv(path, parse_dates=["date"]) if os.path.exists(path) else pd.DataFrame(columns=cols)
    old = old[old["date"] != pd.Timestamp(date)]
    new = pd.DataFrame([[pd.Timestamp(date), ndx, res["eps"], res["pe"], res["cov"], res["wsrc"]]], columns=cols)
    df = pd.concat([old, new], ignore_index=True).sort_values("date")
    df.to_csv(path, index=False)
    return df


# ---------------------------------------------------------------- 演示数据
def demo_data():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1100)
    ret = rng.normal(0.0006, 0.0105, len(idx))
    ret[0] = 0
    px = pd.Series(10000 * np.exp(np.cumsum(ret)), index=idx)
    px *= 21350 / px.iloc[-1]
    vx = np.zeros(len(idx))
    for i in range(1, len(idx)):
        vx[i] = 0.94 * vx[i - 1] - 9 * ret[i] + 0.025 * rng.normal()
    vix = pd.Series(np.clip(15.5 * np.exp(vx), 10, 80), index=idx)
    ry = pd.Series(1.6 + np.cumsum(rng.normal(0.0003, 0.018, len(idx))), index=idx)

    def mk(base, k, n, sm, sd):
        ch = (px / px.shift(n) - 1).fillna(0).values * 100
        x, out = 0.0, []
        for i in range(len(idx)):
            x = sm * x + sd * rng.normal()
            out.append(float(np.clip(base + k * ch[i] + x, 4, 96)))
        return pd.Series(out, index=idx)

    br = dict(s50=mk(52, 1.6, 20, .9, 1.6), s200=mk(58, .9, 60, .95, .9),
              n50=mk(50, 1.8, 20, .9, 1.8), n200=mk(56, 1.0, 60, .95, 1.0))
    res = dict(eps=905.0, pe=px.iloc[-1] / 905, cov=0.97, wsrc="演示权重", n=96)
    trend = ({90: 100.0, 60: 101.2, 30: 102.5, 7: 103.1, 0: 103.4}, 0.64, 92)
    return px, vix, ry, br, res, trend


# ---------------------------------------------------------------- 指标与状态卡
def missing(title, why="数据缺失"):
    return dict(t=title, v="数据缺失", s=[why, ""], st=["数据缺失", "mut"])


def card_price(ndx):
    ma200 = ndx.rolling(200).mean()
    dd = (ndx / ndx.cummax() - 1) * 100
    last, d = ndx.iloc[-1], dd.iloc[-1]
    hi52 = ndx.iloc[-252:].max()
    vs = (last / ma200.iloc[-1] - 1) * 100
    sl = (ma200.iloc[-1] / ma200.iloc[-21] - 1) * 100
    dr = "上行" if sl > 0.3 else "下行" if sl < -0.3 else "走平"
    st = ["正常", "ok"] if d > -5 else ["轻度回撤", "warn"] if d > -10 else \
        ["回调", "bad"] if d > -20 else ["熊市区", "bad"]
    c = dict(t="01 价格", v=f"{d:+.1f}%",
             s=["距历史高点", f"距52周高 {(last / hi52 - 1) * 100:+.1f}% · MA200 {vs:+.1f}% {dr}"], st=st)
    return c, ma200, dd


def card_breadth(br, dd):
    r = lambda k: br[k].dropna().iloc[-1]  # noqa: E731
    avg = (br["s50"] + br["s200"] + br["n50"] + br["n200"]) / 4
    a = avg.dropna()
    st = ["强", "ok"] if a.iloc[-1] > 70 else ["中性偏强", "ok"] if a.iloc[-1] > 50 else \
        ["偏弱", "warn"] if a.iloc[-1] > 30 else ["弱", "bad"]
    line2 = f"MA50：{r('s50'):.0f}% · {r('n50'):.0f}%"
    if dd.iloc[-1] > -3 and a.iloc[-1] - a.iloc[-21] < -5:
        line2 += " · 价格近高点但宽度走弱"
        if st[1] == "ok":
            st = [st[0], "warn"]
    return dict(t="02 宽度", v=f"{r('s200'):.0f}% · {r('n200'):.0f}%",
                s=["站上 MA200（SPX · NDX）", line2], st=st)


def card_vix(vix):
    v = vix.iloc[-1]
    v5, v20 = (v / vix.iloc[-6] - 1) * 100, (v / vix.iloc[-21] - 1) * 100
    pk = vix.iloc[-10:].max()
    spike = pk >= vix.iloc[-11] * 1.25 and v <= pk * 0.85
    st = ["低波动", "ok"] if v < 15 else ["正常", "ok"] if v < 20 else \
        ["紧张", "warn"] if v < 30 else ["恐慌", "bad"]
    return dict(t="03 风险", v=f"{v:.1f}",
                s=["VIX", f"5日 {v5:+.1f}% · 20日 {v20:+.1f}% · 冲高回落：{'是' if spike else '否'}"], st=st)


def card_ry(ry):
    ma20, ma60 = ry.rolling(20).mean(), ry.rolling(60).mean()
    y = ry.iloc[-1]
    r5, r20 = (y - ry.iloc[-6]) * 100, (y - ry.iloc[-21]) * 100
    if ma20.iloc[-1] > ma60.iloc[-1] and y > ma20.iloc[-1]:
        st = ["上行通道", "warn"]
    elif ma20.iloc[-1] < ma60.iloc[-1] and y < ma20.iloc[-1]:
        st = ["下行通道", "ok"]
    else:
        st = ["震荡", "mut"]
    return dict(t="04 资金价格", v=f"{y:.2f}%",
                s=["10Y 实际利率", f"5日 {r5:+.0f}bp · 20日 {r20:+.0f}bp"], st=st), ma20, ma60


def card_eps(res, snap, trend, ndx):
    last_d = ndx.index[-1]
    up = None
    if snap is not None and len(snap) >= 20:
        sub = snap[snap["date"] <= last_d - pd.Timedelta(days=90)]
        b = sub.iloc[-1] if len(sub) else snap.iloc[0]
        cur = snap.iloc[-1]
        e = (cur["fwd_eps"] / b["fwd_eps"] - 1) * 100
        p = (cur["ndx"] / b["ndx"] - 1) * 100
        win = f"{(cur['date'] - b['date']).days}天"
        chart = dict(mode="快照", dates=[d.strftime("%Y-%m-%d") for d in snap["date"]],
                     ndx=[round(float(x / snap["ndx"].iloc[0] * 100), 2) for x in snap["ndx"]],
                     eps=[round(float(x / snap["fwd_eps"].iloc[0] * 100), 2) for x in snap["fwd_eps"]])
    elif trend:
        lvl, up, _ = trend
        offs = (90, 60, 30, 7, 0)
        dates = [last_d - pd.Timedelta(days=o) for o in offs]
        nd = [float(ndx.asof(d)) for d in dates]
        e, p, win = lvl[0] - 100, (nd[-1] / nd[0] - 1) * 100, "90天"
        chart = dict(mode="分析师修正", dates=[d.strftime("%Y-%m-%d") for d in dates],
                     ndx=[round(x / nd[0] * 100, 2) for x in nd],
                     eps=[round(lvl[o], 2) for o in offs])
    else:
        return missing("05 基本面", "趋势数据不足"), None
    if e < 0 < p:
        st = ["盈利不支撑", "bad"]
    elif e < 0:
        st = ["盈利走弱", "warn"]
    elif p > e + 3:
        st = ["估值扩张", "warn"]
    else:
        st = ["盈利支撑", "ok"]
    l2 = f"{win}EPS {e:+.1f}% · 同期 NDX {p:+.1f}%"
    if up is not None:
        l2 += f" · 上调占比 {up * 100:.0f}%"
    return dict(t="05 基本面", v=f"{res['eps']:,.0f}",
                s=[f"NDX Forward EPS（点）· Fwd PE {res['pe']:.1f}", l2], st=st), chart


# ---------------------------------------------------------------- 报告生成
def lst(s, nd=4):
    return [None if pd.isna(x) else round(float(x), nd) for x in s]


def align(s, base, label, max_lag=5):
    if s is None:
        return None
    s = s[~s.index.duplicated()].sort_index()
    if (base[-1] - s.index.max()).days > max_lag:
        note(f"{label}：最新数据 {s.index.max().date()} 落后于 NDX {base[-1].date()} 超过 {max_lag} 天")
    return s.reindex(base.union(s.index)).ffill().reindex(base)


def build_overview(cards):
    ok = [c for c in cards if c["v"] != "数据缺失"]
    if not ok:
        return "今日数据均缺失，请查看页脚说明。"
    parts = "；".join(f"{c['t'][3:]}：{c['st'][0]}" for c in ok)
    bad = [c["t"][3:] for c in ok if c["st"][1] == "bad"]
    warn = [c["t"][3:] for c in ok if c["st"][1] == "warn"]
    tail = ""
    if bad:
        tail = f" 风险项：{'、'.join(bad)}。"
    elif warn:
        tail = f" 需关注：{'、'.join(warn)}。"
    if len(ok) < len(cards):
        tail += f" {len(cards) - len(ok)} 个模块数据缺失。"
    head = f"NDX 距历史高点 {cards[0]['v']}。" if cards[0]["v"] != "数据缺失" else ""
    return f"{head}{parts}。{tail}".strip()


def main():
    ap = argparse.ArgumentParser(description="投资日报")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--data", default="data")
    ap.add_argument("--proxy", help="如 http://127.0.0.1:7890（Clash 混合端口）")
    ap.add_argument("--demo", action="store_true", help="用模拟数据生成版式，不联网")
    ap.add_argument("--skip-breadth", action="store_true")
    ap.add_argument("--skip-eps", action="store_true")
    ap.add_argument("--open", action="store_true", help="生成后用浏览器打开")
    a = ap.parse_args()

    if a.proxy:
        os.environ["HTTP_PROXY"] = os.environ["HTTPS_PROXY"] = a.proxy
        try:
            import yfinance as yf
            try:
                yf.config.network.proxy = a.proxy
            except Exception:  # noqa: BLE001
                yf.set_config(proxy=a.proxy)
        except Exception:  # noqa: BLE001
            pass

    br = res = trend = None
    snap = None
    if a.demo:
        ndx, vix, ry, br, res, trend = demo_data()
        for k in ("价格", "VIX", "实际利率", "宽度", "Forward EPS"):
            SOURCES[k] = ["演示数据", str(ndx.index[-1].date())]
    else:
        ndx = first_ok("价格", [("Yahoo ^NDX", lambda: yf_hist("^NDX")), ("Stooq ^ndx", lambda: stooq("^ndx")),
                              ("FRED NASDAQ100（备用）", lambda: fred("NASDAQ100"))])
        if ndx is None:
            sys.exit("NDX 价格获取失败，无法生成报告。请打开 Clash 并加 --proxy，或过 15 分钟再试。")
        if SOURCES["价格"][0].startswith("FRED"):
            NOTES.append("价格使用 FRED 备用源：历史高点按近 10 年计算，数据约晚一个交易日")
        vix = first_ok("VIX", [("CBOE 官方 CSV", cboe_vix), ("FRED VIXCLS", lambda: fred("VIXCLS")),
                               ("Yahoo ^VIX", lambda: yf_hist("^VIX"))])
        ry = first_ok("实际利率", [("FRED DFII10", lambda: fred("DFII10")),
                                 ("Treasury 实际收益率曲线", treasury_real)])
        sp = nd = None
        if not (a.skip_breadth and a.skip_eps):
            nd = first_list("NDX 成分股", [("Wikipedia", ndx_wiki),
                                          ("Slickcharts", lambda: slick_symbols("nasdaq100"))])
            if not a.skip_breadth:
                sp = first_list("SPX 成分股", [("Wikipedia", sp500_wiki), ("GitHub datasets", sp500_github),
                                              ("Slickcharts", lambda: slick_symbols("sp500"))])
        if not a.skip_breadth and sp and nd:
            try:
                cl = download_closes(sorted(set(sp) | set(nd)))
                cs = [c for c in cl.columns if c in set(sp)]
                cn = [c for c in cl.columns if c in set(nd)]
                bs, bn = breadth(cl[cs]), breadth(cl[cn])
                br = dict(s50=bs[50], s200=bs[200], n50=bn[50], n200=bn[200])
                SOURCES["宽度"] = ["Yahoo 成分股日线自行计算", str(cl.index.max().date())]
                NOTES.append(f"宽度覆盖：SPX {len(cs)}/{len(sp)} 只，NDX {len(cn)}/{len(nd)} 只有行情")
            except Exception as e:  # noqa: BLE001
                note(f"宽度计算失败（{type(e).__name__}: {str(e)[:80]}）")
        if not a.skip_eps and nd:
            try:
                try:
                    wts = slick_weights()
                except Exception as e:  # noqa: BLE001
                    note(f"Forward EPS：Slickcharts 权重失败，改用市值近似（{type(e).__name__}）")
                    wts = None
                res, edf, w = ndx_eps(nd, wts, float(ndx.iloc[-1]))
                trend = eps_trend_levels(edf, w)
                SOURCES["Forward EPS"] = [f"Yahoo 成分股 forwardEps 调和加权（{res['wsrc']}）",
                                          str(ndx.index[-1].date())]
                NOTES.append(f"Forward EPS 覆盖率 {res['cov'] * 100:.0f}%（{res['n']} 只有效）")
            except Exception as e:  # noqa: BLE001
                note(f"Forward EPS 计算失败（{type(e).__name__}: {str(e)[:80]}）")

    date = ndx.index[-1]
    if res is not None and not a.demo:
        snap = update_snapshots(os.path.join(a.data, "ndx_fwd_eps.csv"), date, float(ndx.iloc[-1]), res)
    elif res is not None:
        snap = None

    # 各模块计算（任一模块失败只影响该模块）
    cards, D = [], {}
    base = ndx.index
    try:
        c, ma200, dd = card_price(ndx)
        cards.append(c)
        D.update(ndx=lst(ndx.iloc[-N_VIEW:], 2), ma200=lst(ma200.iloc[-N_VIEW:], 2), dd=lst(dd.iloc[-N_VIEW:], 2))
    except Exception as e:  # noqa: BLE001
        note(f"价格模块失败（{e}）")
        cards.append(missing("01 价格"))
        dd = None
    try:
        if br is None:
            raise ValueError("无宽度数据")
        brs = {k: align(v, base, f"宽度 {k}") for k, v in br.items()}
        cards.append(card_breadth(brs, dd if dd is not None else pd.Series([-99.0], index=[base[-1]])))
        D["br"] = {k: lst(v.iloc[-N_VIEW:], 1) for k, v in brs.items()}
    except Exception as e:  # noqa: BLE001
        cards.append(missing("02 宽度"))
        if br is not None:
            note(f"宽度模块失败（{e}）")
    try:
        if vix is None:
            raise ValueError("无 VIX 数据")
        v = align(vix, base, "VIX")
        cards.append(card_vix(v))
        D["vix"] = lst(v.iloc[-N_VIEW:], 2)
    except Exception as e:  # noqa: BLE001
        cards.append(missing("03 风险"))
        if vix is not None:
            note(f"VIX 模块失败（{e}）")
    try:
        if ry is None:
            raise ValueError("无实际利率数据")
        c, m20, m60 = card_ry(ry)
        cards.append(c)
        r_, a20, a60 = (align(x, base, "实际利率") for x in (ry, m20, m60))
        D.update(ry=lst(r_.iloc[-N_VIEW:], 3), ma20=lst(a20.iloc[-N_VIEW:], 3), ma60=lst(a60.iloc[-N_VIEW:], 3))
    except Exception as e:  # noqa: BLE001
        cards.append(missing("04 资金价格"))
        if ry is not None:
            note(f"实际利率模块失败（{e}）")
    try:
        if res is None:
            raise ValueError("无 Forward EPS 数据")
        c, chart = card_eps(res, snap, trend, ndx)
        cards.append(c)
        D["eps"] = chart
    except Exception as e:  # noqa: BLE001
        cards.append(missing("05 基本面"))
        if res is not None:
            note(f"基本面模块失败（{e}）")

    D.update(dates=[d.strftime("%Y-%m-%d") for d in base[-N_VIEW:]], date=str(date.date()), demo=a.demo,
             cards=cards, overview=build_overview(cards),
             sources=[[k] + v for k, v in SOURCES.items()], notes=NOTES)

    data_json = json.dumps(D, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", data_json).replace("__CHARTJS__", chartjs())
    os.makedirs(a.out, exist_ok=True)
    p1 = os.path.join(a.out, f"investment_daily_{date.date()}.html")
    for p in (p1, os.path.join(a.out, "latest.html")):
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)
    print("已生成：", os.path.abspath(p1))
    if a.open:
        webbrowser.open("file://" + os.path.abspath(p1))


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>投资日报</title>
<style>
:root{--bg:#fff;--sf:#f6f5f1;--cd:#faf9f6;--bd:#e1e0d9;--tx:#1f1f1d;--tx2:#5f5e5a;--mut:#898781;--ac:#2a78d6;--acbg:#e8f1fc;--ok:#1baf7a;--warn:#e0a02e;--bad:#e34948}
@media(prefers-color-scheme:dark){:root{--bg:#161615;--sf:#1f1f1d;--cd:#1f1f1d;--bd:#33332f;--tx:#ecebe6;--tx2:#a8a69f;--mut:#898781;--ac:#3987e5;--acbg:#1b2a3d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
main{max-width:760px;margin:0 auto;padding:16px 14px 32px}
.row{display:flex;justify-content:space-between;font-size:12px;color:var(--tx2);margin-bottom:8px}
#ov{background:var(--sf);border-radius:8px;padding:10px 12px;margin-bottom:12px}
#cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:14px}
.card{background:var(--cd);border:.5px solid var(--bd);border-radius:12px;padding:12px;cursor:pointer;min-width:0}
.card.on{border:1.5px solid var(--ac);padding:11.5px}
.card:focus-visible,.chip:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
.hd{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--tx2)}
.hd i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.big{font-size:22px;font-weight:500;margin:4px 0 2px}
.sub{font-size:12px;color:var(--tx2);line-height:1.5;min-height:18px}
#chips{display:flex;gap:6px;margin-bottom:8px}
.chip{height:30px;padding:0 12px;font-size:13px;border:.5px solid var(--bd);border-radius:8px;background:var(--cd);color:var(--tx);cursor:pointer}
.chip.on{background:var(--acbg);color:var(--ac);border-color:var(--ac)}
#lg{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:var(--tx2);margin-bottom:6px}
#lg span{display:flex;align-items:center;gap:5px}
#nt,#msg{font-size:12px;color:var(--mut);margin-bottom:6px}
#msg{font-size:14px;padding:40px 0;text-align:center}
.w{position:relative;width:100%}
#foot{margin-top:16px;font-size:12px;color:var(--mut);line-height:1.6}
#foot h3{font-size:12px;font-weight:500;color:var(--tx2);margin:10px 0 2px}
#foot ul{margin:0;padding-left:16px}
</style></head><body><main>
<div class="row"><span id="dt"></span><span id="mode"></span></div>
<div id="ov"></div>
<div id="cards"></div>
<div id="chips"></div>
<div id="lg"></div><div id="nt"></div>
<div class="w" id="w1" style="height:230px"><canvas id="c1" role="img" aria-label="图表"></canvas></div>
<div id="msg" style="display:none"></div>
<div class="w" id="w2" style="height:0;margin-top:6px"><canvas id="c2" role="img" aria-label="回撤图"></canvas></div>
<div id="foot"></div>
</main>
<script>__CHARTJS__</script>
<script>
const D=__DATA__;
const $=id=>document.getElementById(id);
const dark=matchMedia('(prefers-color-scheme: dark)').matches;
const C={b:dark?'#3987e5':'#2a78d6',o:dark?'#d95926':'#eb6834',a:dark?'#199e70':'#1baf7a',r:dark?'#e66767':'#e34948',v:dark?'#9085e9':'#6250d6',g:dark?'#383835':'#c3c2b7',grid:dark?'#2c2c2a':'#e1e0d9',tx:'#898781'};
const DOT={ok:'var(--ok)',warn:'var(--warn)',bad:'var(--bad)',mut:'var(--mut)'};
let N=252,cur=0,c1=null,c2=null;
$('dt').textContent='数据日期 '+D.date;$('mode').textContent=D.demo?'演示数据':'';
$('ov').textContent=D.overview;
const cw=$('cards');
D.cards.forEach((c,i)=>{
  const el=document.createElement('div');el.className='card'+(i===0?' on':'');el.setAttribute('role','button');el.tabIndex=0;
  if(i===4)el.style.gridColumn='1/-1';
  el.innerHTML='<div class="hd"><span>'+c.t+'</span><span><i style="background:'+DOT[c.st[1]]+'"></i>'+c.st[0]+'</span></div><div class="big">'+c.v+'</div><div class="sub">'+c.s.join('<br>')+'</div>';
  const go=()=>{cur=i;[...cw.children].forEach((x,j)=>x.classList.toggle('on',j===i));render()};
  el.onclick=go;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}};cw.appendChild(el);
});
const cp=$('chips');
[['3M',63],['6M',126],['1Y',252],['3Y',756]].forEach(([n,v])=>{
  const b=document.createElement('button');b.className='chip'+(v===N?' on':'');b.textContent=n;
  b.onclick=()=>{N=v;[...cp.children].forEach(x=>x.classList.toggle('on',x===b));render()};cp.appendChild(b);
});
const sl=a=>a?a.slice(-N):null;
function ln(label,data,color,o){return Object.assign({label,data,borderColor:color,backgroundColor:color,borderWidth:2,pointRadius:0,pointHoverRadius:4,tension:.15},o||{})}
function opts(fmt,yo,tk){return{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
 plugins:{legend:{display:false},tooltip:{filter:i=>!i.dataset.ref,callbacks:{label:c=>' '+c.dataset.label+' '+(c.parsed.y==null?'—':fmt(c.parsed.y))}}},
 scales:{x:{grid:{display:false},border:{color:C.g},ticks:{color:C.tx,maxTicksLimit:5,maxRotation:0,font:{size:11},callback(v){return this.getLabelForValue(v).slice(tk[0],tk[1])}}},
 y:Object.assign({grid:{color:C.grid},border:{display:false},ticks:{color:C.tx,font:{size:11},maxTicksLimit:5,callback:v=>fmt(v)}},yo||{})}}}
function mod(){
  const n=sl(D.dates)?sl(D.dates).length:0;
  const ref=(l,v)=>ln(l,Array(n).fill(v),C.tx,{borderDash:[2,4],borderWidth:1,ref:true,pointHoverRadius:0});
  if(cur===0){if(!D.ndx)return null;
    return{ds:[ln('NDX',sl(D.ndx),C.b),ln('MA200',sl(D.ma200),C.o,{borderDash:[5,3]})],fmt:v=>Math.round(v).toLocaleString(),lg:[['NDX',C.b],['MA200',C.o,1]],
      sub:{ds:[ln('回撤',sl(D.dd),C.r,{fill:true,backgroundColor:C.r+'22',borderWidth:1.5})],fmt:v=>v.toFixed(1)+'%',yo:{max:0}},aria:'NDX 与 MA200 折线，下方为回撤面积图'}}
  if(cur===1){if(!D.br)return null;const q=D.br;
    return{ds:[ln('SPX·MA50',sl(q.s50),C.b),ln('SPX·MA200',sl(q.s200),C.b,{borderDash:[5,3]}),ln('NDX·MA50',sl(q.n50),C.o),ln('NDX·MA200',sl(q.n200),C.o,{borderDash:[5,3]}),ref('50%',50)],
      fmt:v=>Math.round(v)+'%',yo:{min:0,max:100},lg:[['SPX·MA50',C.b],['SPX·MA200',C.b,1],['NDX·MA50',C.o],['NDX·MA200',C.o,1]],aria:'成分股站上 MA50、MA200 的比例'}}
  if(cur===2){if(!D.vix)return null;
    return{ds:[ln('VIX',sl(D.vix),C.v),ref('20',20),ref('30',30)],fmt:v=>v.toFixed(1),lg:[['VIX',C.v],['20 / 30 阈值',C.tx,1]],aria:'VIX 折线与阈值线'}}
  if(cur===3){if(!D.ry)return null;
    return{ds:[ln('10Y 实际利率',sl(D.ry),C.b),ln('MA20',sl(D.ma20),C.o,{borderDash:[5,3],borderWidth:1.5}),ln('MA60',sl(D.ma60),C.a,{borderDash:[2,3],borderWidth:1.5})],
      fmt:v=>v.toFixed(2)+'%',lg:[['10Y 实际利率',C.b],['MA20',C.o,1],['MA60',C.a,1]],aria:'10 年期实际利率与均线'}}
  if(!D.eps)return null;const e=D.eps,pr=e.mode!=='快照'?3:0;
  return{labels:e.dates,tk:[5,10],ds:[ln('NDX',e.ndx,C.b,{pointRadius:pr}),ln('Forward EPS',e.eps,C.a,{borderDash:[5,3],pointRadius:pr})],fmt:v=>v.toFixed(1),
    lg:[['NDX（起点=100）',C.b],['Forward EPS（起点=100）',C.a,1]],note:e.mode==='快照'?'EPS 来自每日快照':'快照不足 20 天，EPS 趋势取自分析师修正（约 90 天）',aria:'NDX 与 Forward EPS 指数化走势'}}
function render(){
  const m=mod(),w1=$('w1'),w2=$('w2');
  if(c1){c1.destroy();c1=null}if(c2){c2.destroy();c2=null}
  if(!m){w1.style.display='none';w2.style.height='0';$('lg').innerHTML='';$('nt').textContent='';$('msg').style.display='block';$('msg').textContent='数据缺失：该模块的所有来源均不可用，详见页脚说明';return}
  $('msg').style.display='none';w1.style.display='block';
  $('lg').innerHTML=m.lg.map(x=>'<span><span style="width:16px;height:0;border-top:2px '+(x[2]?'dashed':'solid')+' '+x[1]+'"></span>'+x[0]+'</span>').join('');
  $('nt').textContent=m.note||'';$('c1').setAttribute('aria-label',m.aria);
  const lb=m.labels||sl(D.dates),tk=m.tk||[2,7];
  c1=new Chart($('c1'),{type:'line',data:{labels:lb,datasets:m.ds},options:opts(m.fmt,m.yo,tk)});
  if(m.sub){w2.style.height='90px';c2=new Chart($('c2'),{type:'line',data:{labels:lb,datasets:m.sub.ds},options:opts(m.sub.fmt,m.sub.yo,tk)})}else w2.style.height='0';
}
render();
let h='<h3>数据来源</h3><ul>'+D.sources.map(s=>'<li>'+s[0]+'：'+s[1]+'（最新 '+s[2]+'）</li>').join('')+'</ul>';
if(D.notes.length)h+='<h3>备源与异常</h3><ul>'+D.notes.map(s=>'<li>'+s+'</li>').join('')+'</ul>';
$('foot').innerHTML=h;
</script></body></html>
"""

def chartjs():
    """返回内嵌的 Chart.js 源码（报告因此不依赖网络，可离线打开）。"""
    import base64
    import zlib
    js = zlib.decompress(base64.b64decode(CHARTJS_B64)).decode("utf-8")
    return js.replace("</script", "<\\/script")


# Chart.js v4.4.1（MIT 许可，https://www.chartjs.org），压缩后内嵌
CHARTJS_B64 = """
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
"""

if __name__ == "__main__":
    main()
