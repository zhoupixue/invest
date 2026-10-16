#!/usr/bin/env python3
"""Build a public artifact without changing the original calculation engine."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ORIGINAL_SHA = 'fdfc5ddf0e17b4340a6d09bdcb51911b15c08376dc52074b59bf342a18a73f15'
MODULES = [('价格', ['ndx','ma200','dd']), ('宽度', ['br']), ('VIX', ['vix']), ('实际利率', ['ry','ma20','ma60']), ('Forward EPS', ['eps'])]

def load_report(path):
    match = re.search(r'const D=(.*?);\s*const \$', Path(path).read_text(), re.S)
    if not match:
        raise ValueError('报告中没有原始 JSON')
    data = json.loads(match.group(1))
    validate(data)
    return data

def validate(d):
    if d.get('demo') is not False:
        raise ValueError('禁止发布演示数据')
    if len(d.get('cards', [])) != 5:
        raise ValueError('必须保留五大指标')
    dates = d['dates']
    if not dates or dates != sorted(set(dates)) or dates[-1] != d['date']:
        raise ValueError('数据日期无效')
    if dt.date.fromisoformat(d['date']) > dt.datetime.now(dt.timezone.utc).date():
        raise ValueError('禁止未来数据')
    def walk(v):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError('非有限数值')
        if isinstance(v, dict):
            for x in v.values(): walk(x)
        if isinstance(v, list):
            for x in v: walk(x)
    walk(d)
    for key in ('ndx','ma200','dd','vix','ry','ma20','ma60'):
        if key in d and len(d[key]) != len(dates):
            raise ValueError(f'{key} 序列长度不一致')
    for values in d.get('br', {}).values():
        if len(values) != len(dates) or any(x is not None and not 0 <= x <= 100 for x in values):
            raise ValueError('宽度数据无效')
    e = d.get('eps')
    if e and not len(e['dates']) == len(e['ndx']) == len(e['eps']):
        raise ValueError('EPS 序列长度不一致')

def public_data(d, policy):
    # Build from an explicit allowlist: raw source metadata and errors never go public.
    out = {k:d[k] for k in ('date','dates','demo')}
    out.update(cards=[], modules=[], attributions=[], updated_at=dt.datetime.now(dt.timezone.utc).isoformat(), report_generated_at=d.get('generated_at'))
    sources = {s[0]:s for s in d.get('sources', [])}
    for i, (name, keys) in enumerate(MODULES):
        src = sources.get(name)
        rules = policy.get('modules', {}).get(name, [])
        rule = next((r for r in rules if src and r.get('source') == src[1] and r.get('status') == 'approved' and r.get('evidence') and r.get('public_display') and r.get('historical') and r.get('derived')), None)
        # Breadth and EPS conclusions depend on NDX as well as their own inputs.
        if i in (1,4):
            p = sources.get('价格')
            price_ok = any(r.get('source') == (p[1] if p else None) and r.get('status') == 'approved' and r.get('evidence') and all(r.get(k) for k in ('public_display','historical','derived')) for r in policy.get('modules',{}).get('价格',[]))
            if not price_ok: rule = None
        directed = policy.get('mode') == 'operator_directed'
        available = (rule is not None or directed) and d['cards'][i]['v'] != '数据缺失'
        reason = '数据缺失：取数或计算失败，未使用替代或演示数据' if directed or rule else '数据缺失：公开再分发授权待核实'
        card = d['cards'][i] if available else dict(t=d['cards'][i]['t'],v='数据缺失',s=[reason,''],st=['待核实' if rule is None and not directed else '数据缺失','mut'])
        out['cards'].append(card)
        out['modules'].append(dict(available=available,reason=None if available else reason,observed_at=src[2] if src else None))
        if available:
            for key in keys:
                if key in d: out[key]=d[key]
            if rule and rule.get('attribution'): out['attributions'].append(rule['attribution'])
    permitted = [c for i,c in enumerate(out['cards']) if out['modules'][i]['available']]
    out['overview'] = '；'.join(c['t'][3:]+'：'+c['st'][0] for c in permitted) if permitted else '五大指标已保留。数据公开授权尚待核实，暂不展示数值与衍生结论。'
    out['notes'] = [n for n in d.get('notes',[]) if ('落后于 NDX' in n) or ('覆盖' in n and ((n.startswith('宽度') and out['modules'][1]['available']) or (n.startswith('Forward EPS') and out['modules'][4]['available'])))]
    if policy.get('mode') == 'operator_directed':
        out['overview'] = d['overview']
        out['attributions'] = policy.get('attributions', [])
    return out

def spx_data(path, dates):
    if not Path(path).exists(): return [None]*len(dates)
    rows=json.loads(Path(path).read_text()).get('values',[])
    observed=[r['date'] for r in rows]
    if observed != sorted(set(observed)): raise ValueError('SPX 日期顺序无效')
    for row in rows:
        dt.date.fromisoformat(row['date'])
        if not isinstance(row['close'],(int,float)) or not math.isfinite(row['close']) or row['close']<=0:
            raise ValueError('SPX 收盘数据无效')
    if not rows or observed[-1]!=dates[-1]: return [None]*len(dates)
    by_date={r['date']:r['close'] for r in rows}
    return [by_date.get(date) for date in dates]

def build(report, output, policy_path):
    if hashlib.sha256((ROOT/'ndx5s_daily.py').read_bytes()).hexdigest() != ORIGINAL_SHA:
        raise ValueError('原计算脚本发生变化，需要重新审核')
    d=load_report(report)
    policy=json.loads(Path(policy_path).read_text())
    out=public_data(d,policy)
    if out["modules"][2]["available"] and policy.get("mode")=="operator_directed":
        out["spx"]=spx_data(ROOT/"data/spx_close.json",d["dates"])
    import ndx5s_daily as engine
    output=Path(output)
    if output.resolve() in (ROOT.resolve(),(ROOT/'reports').resolve(),(ROOT/'data').resolve()): raise ValueError('不可覆盖原始目录')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ndx5s-publish-',dir=output.parent) as folder:
        staging=Path(folder)
        for p in (ROOT/'web').iterdir():
            if p.is_file(): shutil.copy2(p,staging/p.name)
        # Version presentation assets so an already-open browser gets the current design.
        index=staging/'index.html'
        html=index.read_text()
        for name in ('style.css','app.js','qdii.js'):
            version=hashlib.sha256((staging/name).read_bytes()).hexdigest()[:12]
            html=html.replace('/'+name+'"','/'+name+'?v='+version+'"')
        index.write_text(html)
        for filename,target in [('qdii.json','qdii.json'),('qdii_status.json','qdii-status.json')]:
            source=ROOT/'data'/filename
            if source.exists():
                if filename=='qdii.json':
                    from update_qdii import validate_snapshot
                    validate_snapshot(json.loads(source.read_text()))
                shutil.copy2(source,staging/target)
        (staging/'data.json').write_text(json.dumps(out,ensure_ascii=False,allow_nan=False))
        (staging/'chart.umd.js').write_text(engine.chartjs())
        generated=json.loads((staging/'data.json').read_text())
        if generated != out or generated['date'] != d['date']:
            raise ValueError('部署数据与本次报告不一致，禁止发布')
        # Never inherit old JSON from dist; replace complete files atomically.
        output.mkdir(parents=True,exist_ok=True)
        for name in ('data.json','qdii.json','qdii-status.json'):
            stale=output/name
            if not (staging/name).exists() and stale.exists():stale.unlink()
        for asset in staging.iterdir():
            os.replace(asset,output/asset.name)
    print('网站已构建：',output,'；公开模块',sum(m['available'] for m in out['modules']),'/5')

if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--report',default=str(ROOT/'reports/latest.html'));ap.add_argument('--out',default=str(ROOT/'dist'));ap.add_argument('--policy',default=str(ROOT/'data/publication_policy.json'));a=ap.parse_args()
    build(a.report,a.out,a.policy)
