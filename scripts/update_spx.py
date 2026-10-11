#!/usr/bin/env python3
"""Fetch a real SPX comparison series, separate from the five indicator engine."""
import datetime as dt
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def fetch_spx(report_date, output):
    import investment_daily as engine
    errors=[]
    def cboe_spx():
        import io,pandas as pd
        df=pd.read_csv(io.StringIO(engine.get('https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv').text))
        return pd.Series(pd.to_numeric(df[next(c for c in ('CLOSE','SPX') if c in df.columns)],errors='raise').values,index=pd.to_datetime(df['DATE'])).dropna()
    for name, fetch in [('Cboe official SPX CSV',cboe_spx),('Yahoo ^GSPC',lambda:engine.yf_hist('^GSPC',period='5y')),('Stooq ^spx',lambda:engine.stooq('^spx'))]:
        try:
            series=fetch().sort_index()
            series=series[series.index.date <= dt.date.fromisoformat(report_date)].tail(850)
            if series.empty or str(series.index[-1].date()) != report_date:
                raise ValueError('SPX 最新日期未覆盖日报日期')
            rows=[{'date':str(date.date()),'close':float(value)} for date,value in series.items()]
            if any(not math.isfinite(r['close']) or r['close']<=0 for r in rows):
                raise ValueError('SPX 收盘点位无效')
            payload={'source':name,'observed_at':report_date,'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat(),'values':rows}
            Path(output).write_text(json.dumps(payload,allow_nan=False))
            print('SPX real closes:',len(rows),'latest',report_date,'source',name)
            return
        except Exception as exc:
            errors.append(type(exc).__name__)
    Path(output).write_text(json.dumps({'values':[],'observed_at':None}))
    print('SPX 数据缺失；不生成替代曲线。失败类型：'+','.join(errors))

if __name__=='__main__':
    from build_site import load_report
    fetch_spx(load_report(ROOT/'reports/latest.html')['date'],ROOT/'data/spx_close.json')
