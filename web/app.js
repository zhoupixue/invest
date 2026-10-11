'use strict';
const $=id=>document.getElementById(id);
const titles=['价格走势','市场宽度','市场风险','资金价格','盈利与估值'];
const rules=[
'价格沿用 NDX 收盘点位。回撤 =（价格 / 累计历史高点 − 1）× 100；同时观察 252 日高点和 MA200。回撤高于 −5% 为正常，−5% 至 −10% 为轻度回撤，−10% 至 −20% 为回调，其余为熊市区。MA200 相对 20 个交易日前的变化高于 0.3% 为上行，低于 −0.3% 为下行。',
'图中仅展示 NDX 成分股站上 MA50、MA200 的比例；状态沿用原四项比例的综合平均口径。大于 70% 为强，大于 50% 为中性偏强，大于 30% 为偏弱，其余为弱。有效样本不足成分股的 60% 时标为缺失；价格距高点不足 3% 且宽度平均较 20 个交易日前下降超过 5 个百分点时提示背离。当前成分股回溯，不是历史成分股复原。',
'VIX 小于 15 为低波动，小于 20 为正常，小于 30 为紧张，其余为恐慌。5 日、20 日变化按交易日比较；最近 10 日峰值较 10 个交易日前上升至少 25%，且现值较峰值回落至少 15%，标记冲高回落。',
'10 年期实际利率采用原始观测序列计算均线和状态。MA20 高于 MA60 且现值高于 MA20 为上行通道；MA20 低于 MA60 且现值低于 MA20 为下行通道；其余为震荡。5 日、20 日变化换算为 bp（1 个百分点 = 100 bp）。图表按原逻辑对齐到 NDX 交易日并前向填充。',
'成分股 Forward EPS / 价格按有效权重加权得到盈利收益率；NDX Forward EPS = NDX × 盈利收益率，Forward PE = 1 / 盈利收益率。至少 20 条快照后使用原快照趋势，否则采用分析师明年 EPS 的 90/60/30/7/0 天修正。EPS 下跌而价格上涨为盈利不支撑；EPS 下跌为盈利走弱；价格涨幅超过 EPS 增幅 3 个百分点为估值扩张；其余为盈利支撑。'];
let D,cur=0,N=252,chart=null,drawdown=null;
const dark=matchMedia('(prefers-color-scheme: dark)').matches;
const colors=dark?['#3987e5','#d95926','#199e70','#9085e9']:['#2a78d6','#eb6834','#1baf7a','#6250d6'];
function elem(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
function line(label,data,color,extra={}){return {label,data,borderColor:color,backgroundColor:color,borderWidth:2,pointRadius:0,pointHoverRadius:4,tension:.15,...extra}}
function model(){const sl=a=>a?.slice(-N),dates=sl(D.dates);if(!D.modules[cur].available)return null;
 if(cur===0)return {dates,series:[line('NDX',sl(D.ndx),colors[0]),line('MA200',sl(D.ma200),colors[1],{borderDash:[5,3]})],unit:'点',sub:sl(D.dd)};
 if(cur===1)return {dates,series:[line('NDX · MA50',sl(D.br.n50),colors[1]),line('NDX · MA200',sl(D.br.n200),colors[1],{borderDash:[5,3]})],unit:'%',bounds:{min:0,max:100},refs:[50]};
 if(cur===2){const spx=sl(D.spx),has=spx?.some(v=>v!=null);return {dates,series:[line('VIX',sl(D.vix),colors[3]),...(has?[line('SPX',spx,colors[0],{yAxisID:'y1',unit:'点'})]:[])],unit:'',refs:[20,30],right:has,note:has?'':'SPX 数据缺失，暂不展示对照曲线。'};}
 if(cur===3)return {dates,series:[line('10Y 实际利率',sl(D.ry),colors[0]),line('MA20',sl(D.ma20),colors[1],{borderDash:[5,3]}),line('MA60',sl(D.ma60),colors[2],{borderDash:[2,3]})],unit:'%'};
 if(!D.eps)return null;
 const e=D.eps;return {dates:e.dates,series:[line('NDX（起点=100）',e.ndx,colors[0]),line('Forward EPS（起点=100）',e.eps,colors[1],{borderDash:[5,3],pointRadius:e.mode==='快照'?0:3})],unit:'',note:e.mode==='快照'?'EPS 来自每日快照；采用全部快照日期。':'快照不足 20 条，采用分析师约 90 天修正趋势，保留五个原始节点。'};
}
const fmt=(v,u)=>v==null?'—':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:u==='点'?0:2})+u;
function options(unit,bounds={}){return {responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{filter:item=>!item.dataset.reference,callbacks:{label:c=>c.dataset.label+' '+fmt(c.parsed.y,c.dataset.unit??unit)}}},scales:{x:{grid:{display:false},ticks:{maxTicksLimit:6,maxRotation:0,color:'#89958b'}},y:{...bounds,border:{display:false},grid:{color:'#89958b22'},ticks:{color:'#89958b',callback:v=>fmt(v,unit)}}}}}
function render(){chart?.destroy();drawdown?.destroy();chart=drawdown=null;$('legend').replaceChildren();$('chart-title').textContent=titles[cur];$('rule').textContent=rules[cur];const meta=D.modules[cur];const m=model();$('chart-wrap').hidden=!m;$('drawdown-wrap').hidden=!m?.sub;$('empty').hidden=!!m;$('chart-note').textContent=m?.note||'';$('empty-reason').textContent=meta.reason||'数据缺失：趋势数据不足';[...$('ranges').children].forEach(b=>b.disabled=cur===4);if(!m)return;
 const ds=[...m.series,...(m.refs||[]).map(v=>line('阈值 '+v,Array(m.dates.length).fill(v),'#89958b',{reference:true,borderDash:[2,4],borderWidth:1}))];
 const opts=options(m.unit,m.bounds);if(m.right){opts.scales.y.title={display:true,text:'VIX'};opts.scales.y1={position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'SPX（点）'},ticks:{color:'#89958b',callback:v=>fmt(v,'点')}};}chart=new Chart($('chart'),{type:'line',data:{labels:m.dates,datasets:ds},options:opts});$('chart').setAttribute('aria-label',titles[cur]+'，轻触或悬停查看数值');m.series.forEach((s,i)=>{const b=elem('button');b.type='button';b.setAttribute('aria-pressed','true');const sw=elem('span','swatch');sw.style.borderColor=s.borderColor;if(s.borderDash)sw.style.borderTopStyle='dashed';b.append(sw,elem('span',null,s.label));b.onclick=()=>{const on=!chart.isDatasetVisible(i);chart.setDatasetVisibility(i,on);chart.update();b.setAttribute('aria-pressed',String(on))};$('legend').append(b)});
 if(m.sub)drawdown=new Chart($('drawdown'),{type:'line',data:{labels:m.dates,datasets:[line('距历史高点回撤',m.sub,'#b74e4c',{fill:true,backgroundColor:'#b74e4c15'})]},options:options('%',{max:0})});
}
async function start(){try{const res=await fetch('/data.json',{cache:'no-cache'});if(!res.ok)throw Error('HTTP '+res.status);D=await res.json();$('date').textContent=D.date;const overview=D.overview.replace(/：/g,'').replace(/；/g,'，'),attention=overview.match(/需关注[^。]*。?/);if(attention){$('overview').replaceChildren(document.createTextNode(overview.slice(0,attention.index)),elem('span','overview-alert',attention[0]),document.createTextNode(overview.slice(attention.index+attention[0].length)));}else{$('overview').textContent=overview;}
 D.cards.forEach((c,i)=>{if(i===1&&D.modules[1].available){const latest=a=>a.findLast(v=>v!=null);const extra=c.s[1]?.includes(' · 价格')?c.s[1].slice(c.s[1].indexOf(' · 价格')):'';c={...c,v:Math.round(latest(D.br.n200))+'%',s:['NDX 站上 MA200','MA50：'+Math.round(latest(D.br.n50))+'%'+extra]};}const b=elem('button','card');b.type='button';b.setAttribute('aria-pressed',String(i===cur));const h=elem('span','card-head'),name=elem('span','card-name');name.append(elem('span','card-index','0'+(i+1)),document.createTextNode(c.t.slice(3)));const state=elem('span','state '+c.st[1]);const dot=elem('span','state-dot','●');dot.setAttribute('aria-hidden','true');state.append(dot,document.createTextNode(' '+c.st[0]));h.append(name,state);b.append(h,elem('span','card-value',c.v),...c.s.filter(Boolean).map(t=>elem('span','card-desc',t)));b.onclick=()=>{cur=i;[...$('cards').children].forEach((x,j)=>x.setAttribute('aria-pressed',String(i===j)));render()};$('cards').append(b)});
 [['3M',63],['6M',126],['1Y',252],['3Y',756]].forEach(([name,n])=>{const b=elem('button',null,name);b.type='button';b.setAttribute('aria-pressed',String(n===N));b.onclick=()=>{N=n;[...$('ranges').children].forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render()};$('ranges').append(b)});
 render();
 }catch(e){$('overview').textContent='日报暂时无法加载，请稍后刷新。';$('empty').hidden=false;$('empty-reason').textContent='数据缺失：日报文件未能加载';$('chart-wrap').hidden=true;$('drawdown-wrap').hidden=true;console.error(e)}}
start();
