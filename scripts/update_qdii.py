#!/usr/bin/env python3
"""Read only FEIXIA's public homepage. No login, private endpoints or fund-company sources."""
import argparse
import copy
import math
from collections import Counter
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo
from lxml import html

ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://feixia.org/'
TZ=ZoneInfo('Asia/Shanghai')

def now(): return dt.datetime.now(dt.timezone.utc)
def atomic(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    os.replace(temp,path)
def text(e): return ' '.join(e.itertext()).strip()

def parse_homepage(raw):
    doc=html.fromstring(raw)
    if 'QDII' not in ''.join(doc.xpath('//h1//text()')): raise ValueError('源页面不是 QDII 看板')
    open_tables=doc.xpath('//table[@id="fundTable"]')
    if len(open_tables)!=1: raise ValueError('可申购表结构变化')
    closed_sections=doc.xpath('//section[.//h2[contains(normalize-space(.),"暂停申购")]]')
    if len(closed_sections)!=1: raise ValueError('暂停表结构变化')
    rows=[]
    for parent,paused in [(open_tables[0],False),(closed_sections[0],True)]:
        for tr in parent.xpath('.//tbody/tr'):
            links=tr.xpath('.//a[starts-with(@href,"/f/")]')
            if len(links)!=1: raise ValueError('基金链接缺失或重复')
            a=links[0];m=re.fullmatch(r'/f/(\d{6})\.html',a.get('href',''))
            if not m: raise ValueError('基金代码无效')
            names=a.xpath('./div[1]')
            if not names: raise ValueError('基金名称缺失')
            name=' '.join(names[0].xpath('./text()')).strip()
            if not name or not any(k in name for k in ('纳斯达克','纳指','标普')): raise ValueError('出现未识别基金名称')
            badge=names[0].xpath('.//span/text()');share=badge[0].strip().removesuffix('类') if badge else '独立份额'
            if share not in ('A','C','独立份额'): raise ValueError('份额类别变化')
            amount=None;label='暂停申购';state='paused'
            if not paused:
                cells=tr.xpath('./td');label=text(cells[1]) if len(cells)>1 else ''
                raw_value=cells[1].get('data-value') if len(cells)>1 else None
                if label=='不限购':
                    if raw_value is not None and Decimal(raw_value)!=0: raise ValueError('不限购与数值不一致')
                    state='unlimited'
                else:
                    try: v=Decimal(raw_value)
                    except (InvalidOperation,TypeError): raise ValueError('额度缺失或无效')
                    if not v.is_finite() or v<0: raise ValueError('额度非有限数或负数')
                    # FEIXIA guide defines open rows with zero as unlimited, never paused.
                    if v==0:
                        if label not in ('0元','0.0元','0.00元'): raise ValueError('零额度显示不一致')
                        state='unlimited'
                    else:
                        shown=re.fullmatch(r'([\d,.]+)元',label.replace(' ',''))
                        if not shown or Decimal(shown[1].replace(',',''))!=v: raise ValueError('显示额度与数值不一致')
                        state='limited';amount=float(v)
            rows.append(dict(code=m[1],name=name,share_class=share,status=state,limit_yuan=amount,source_label=label))
    if not rows or len(rows)>1000: raise ValueError('基金数量异常')
    codes=[r['code'] for r in rows]
    if len(codes)!=len(set(codes)): raise ValueError('重复基金代码')
    summary=re.search(r'今日可申购总额度[：:]\s*([\d,.]+)\s*元',text(doc))
    if not summary: raise ValueError('源站合计缺失')
    total=float(Decimal(summary[1].replace(',','')))
    actual=sum(r['limit_yuan'] or 0 for r in rows)
    if abs(actual-total)>.001: raise ValueError('份额额度合计与源站不一致')
    updated=re.search(r'数据更新[：:]\s*([^\s<]+)',text(doc))
    if not updated: raise ValueError('源站更新提示缺失')
    return dict(funds=rows,source_total_yuan=total,source_update_label=updated[1])

def group_funds(funds, mapping):
    by_code={r['code']:r for r in funds};used=set();result=[]
    mapped=[c for g in mapping for c in g['codes']]
    if len(mapped)!=len(set(mapped)): raise ValueError('配对表重复代码')
    for g in mapping:
        members=[by_code[c] for c in g['codes'] if c in by_code]
        if not members: continue
        if len(members)>1 and len({r['share_class'] for r in members})!=len(members): raise ValueError('份额类别重复')
        result.append(dict(id=g['id'],name=g['name'],index=g['index'],shares=members))
        used.update(r['code'] for r in members)
    for r in funds:
        if r['code'] not in used:
            index='spx' if '标普' in r['name'] else 'ndx'
            result.append(dict(id=r['code'],name=r['name'],index=index,shares=[r]))
    if sum(len(g['shares']) for g in result)!=len(funds): raise ValueError('合并后份额不守恒')
    return result

def validate_snapshot(data):
    if data.get('schema_version')!=1 or data.get('source')!='FEIXIA': raise ValueError('QDII 数据版本或来源无效')
    stamp=dt.datetime.fromisoformat(data['fetched_at'])
    if stamp.tzinfo is None or stamp>now()+dt.timedelta(minutes=5): raise ValueError('采集时间无效')
    funds=data['funds'];codes=[r['code'] for r in funds]
    if not funds or len(codes)!=len(set(codes)) or data['share_count']!=len(funds): raise ValueError('QDII 份额数量不一致')
    for r in funds:
        if not re.fullmatch(r'\d{6}',r['code']): raise ValueError('QDII 基金代码无效')
        amount=r['limit_yuan']
        if r['status']=='limited':
            if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not 0<amount<float('inf'): raise ValueError('QDII 有限额度无效')
        elif r['status'] in ('paused','unlimited'):
            if amount is not None: raise ValueError('QDII 暂停或不限购不能具有有限额度')
        else: raise ValueError('QDII 状态无效')
    if dict(Counter(r['status'] for r in funds))!=data['counts']: raise ValueError('QDII 状态统计不一致')
    if not isinstance(data['source_total_yuan'],(int,float)) or not math.isfinite(data['source_total_yuan']) or data['source_total_yuan']<0: raise ValueError('QDII 合计无效')
    if abs(sum(r['limit_yuan'] or 0 for r in funds)-data['source_total_yuan'])>.001: raise ValueError('QDII 合计不一致')
    members=[r for g in data['groups'] for r in g['shares']]
    if data['group_count']!=len(data['groups']) or sorted(members,key=lambda r:r['code'])!=sorted(funds,key=lambda r:r['code']): raise ValueError('QDII 合并丢失或重复份额')
    return data

def make_snapshot(parsed, mapping, previous=None, captured=None, digest=None):
    captured=captured or now().isoformat();funds=copy.deepcopy(parsed['funds'])
    groups=group_funds(funds,mapping);counts=Counter(r['status'] for r in funds)
    previous=previous or {};old={r['code']:r for r in previous.get('funds',[])}
    if old and set(old)-{r['code'] for r in funds}: raise ValueError('源页面漏掉已监控份额，保留上一版')
    history=previous.get('changes',[])[:200]
    for r in funds:
        last=old.get(r['code'])
        if not last: continue  # First collection establishes a baseline, not a change event.
        if (last['status'],last['limit_yuan'])!=(r['status'],r['limit_yuan']):
            history.insert(0,dict(code=r['code'],name=r['name'],observed_at=captured,
                previous_status=last['status'],previous_limit_yuan=last['limit_yuan'],
                status=r['status'],limit_yuan=r['limit_yuan']))
    return dict(schema_version=1,source='FEIXIA',source_url=SOURCE,fetched_at=captured,
        source_update_label=parsed['source_update_label'],source_updated_at=None,
        source_total_yuan=parsed['source_total_yuan'],source_sha256=digest,
        share_count=len(funds),group_count=len(groups),counts=dict(counts),
        funds=funds,groups=groups,changes=history[:200])

def eligible(moment=None):
    local=(moment or now()).astimezone(TZ)
    return dt.time(7,30)<=local.time().replace(tzinfo=None)<dt.time(23,30)

def fetch_snapshot():
    req=urllib.request.Request(SOURCE,headers={'User-Agent':'NDX5S-QDII-monitor/1.0 (+https://ndx5s.pages.dev/)','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=45) as res:
        if res.status!=200 or 'text/html' not in res.headers.get('Content-Type',''): raise ValueError('源站响应异常')
        raw=res.read(2_000_001)
    if len(raw)>2_000_000: raise ValueError('源页面体积异常')
    path=ROOT/'data/qdii.json';previous=json.loads(path.read_text()) if path.exists() else None
    mapping=json.loads((ROOT/'data/qdii_groups.json').read_text())
    return make_snapshot(parse_homepage(raw),mapping,previous,digest=hashlib.sha256(raw).hexdigest())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--gate-only',action='store_true');ap.add_argument('--force',action='store_true');a=ap.parse_args()
    if a.gate_only:
        value='true' if eligible() else 'false';print('eligible='+value)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('eligible='+value+'\n')
        return
    if not a.force and not eligible(): print('静默期间不检查');return
    attempted=now().isoformat()
    try:
        snapshot=validate_snapshot(fetch_snapshot());atomic(ROOT/'data/qdii.json',snapshot)
        atomic(ROOT/'data/qdii_status.json',dict(success=True,attempted_at=attempted))
        print(f"QDII 已核验：{snapshot['share_count']} 个份额，{snapshot['group_count']} 行")
    except Exception as e:
        atomic(ROOT/'data/qdii_status.json',dict(success=False,attempted_at=attempted,message='本次获取或校验失败，保留上次数据'))
        print('QDII 更新失败：'+str(e),file=sys.stderr);raise

if __name__=='__main__':main()
