'use strict';
(()=>{
const byId=id=>document.getElementById(id),node=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(value!==undefined)e.textContent=value;return e;};
const labels={limited:'限额申购',unlimited:'不限购',paused:'暂停申购'};
let data=null,loading=false,index='all',status='all',query='';
const money=v=>Number(v).toLocaleString('zh-CN',{maximumFractionDigits:2})+'元';
const time=v=>new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
function describe(s){return s.status==='limited'?money(s.limit_yuan):labels[s.status];}
function matches(g){return (index==='all'||g.index===index)&&(status==='all'||g.shares.some(s=>status==='available'?s.status!=='paused':s.status===status))&&(!query||(g.name+' '+g.shares.map(s=>s.code+' '+s.name).join(' ')).toLowerCase().includes(query));}
function render(){
 if(!data)return;
 const groups=data.groups.filter(matches).sort((a,b)=>Number(a.shares.every(s=>s.status==='paused'))-Number(b.shares.every(s=>s.status==='paused'))||a.name.localeCompare(b.name,'zh-CN'));
 const list=byId('qdii-list');list.replaceChildren();byId('qdii-count').textContent=`显示 ${groups.length} / ${data.group_count} 行 · ${data.share_count} 个基金份额`;
 for(const g of groups){
  const card=node('article','qdii-fund'),head=node('div','qdii-fund-head');head.append(node('h3',null,g.name),node('span','qdii-index',g.index==='ndx'?'纳指':'标普'));card.append(head);
  for(const s of g.shares){const row=node('div','qdii-share'),identity=node('div','qdii-identity');identity.append(node('span','qdii-class',s.share_class==='独立份额'?'基金':s.share_class+'类'),node('span','qdii-code',s.code));const state=node('span','qdii-limit '+(s.status==='paused'?'mut':s.status==='unlimited'?'ok':'warn'),describe(s));row.append(identity,state);card.append(row);}
  list.append(card);
 }
 if(!groups.length)list.append(node('p','qdii-empty','没有符合条件的基金。'));
 const history=byId('qdii-changes');history.replaceChildren();
 const groupCodes=new Set(groups.flatMap(g=>g.shares.map(s=>s.code)));
 const changes=data.changes.filter(c=>groupCodes.has(c.code)).slice(0,12);
 for(const c of changes){const row=node('li');row.append(node('span',null,c.code+' · '+describe({status:c.previous_status,limit_yuan:c.previous_limit_yuan})+' → '+describe(c)),node('small',null,'监测到变化：'+time(c.observed_at)));history.append(row);}
 byId('qdii-change-empty').hidden=!!changes.length;
}
async function load(){
 if(loading||data)return;loading=true;byId('qdii-loading').hidden=false;byId('qdii-error').hidden=true;
 try{
  const r=await fetch('/qdii.json',{cache:'no-cache'});if(!r.ok)throw Error('QDII HTTP '+r.status);data=await r.json();if(data.schema_version!==1||!Array.isArray(data.groups)||!data.groups.length)throw Error('QDII schema');
  let check;try{const response=await fetch('/qdii-status.json',{cache:'no-cache'});if(response.ok)check=await response.json();}catch(_){}
  byId('qdii-captured').textContent='采集时间：'+time(data.fetched_at)+'（北京时间）';
  byId('qdii-source-age').textContent='源站更新提示：采集时显示“'+data.source_update_label+'”';
  const warning=check?.success===false?'本次更新失败，正在展示上次成功采集的数据。':Date.now()-Date.parse(data.fetched_at)>86400000?'数据已超过 24 小时未重新采集，请留意采集日期。':'';
  byId('qdii-warning').textContent=warning;byId('qdii-warning').hidden=!warning;
  const available=data.groups.filter(g=>g.shares.some(s=>s.status!=='paused')).length,paused=data.groups.filter(g=>g.shares.every(s=>s.status==='paused')).length;
  byId('qdii-metrics').replaceChildren();
  for(const [title,value] of [['可申购基金',available+'只'],['暂停申购基金',paused+'只'],['份额额度合计',money(data.source_total_yuan)]]){const c=node('div','qdii-metric');c.append(node('span',null,title),node('strong',null,value));byId('qdii-metrics').append(c);}
  byId('qdii-content').hidden=false;render();
 }catch(e){data=null;byId('qdii-error').hidden=false;byId('qdii-content').hidden=true;console.error(e);}
 finally{loading=false;byId('qdii-loading').hidden=true;}
}
function switchView(view){const show=view==='qdii';byId('ndx-view').hidden=show;byId('qdii-view').hidden=!show;byId('nav-ndx').setAttribute('aria-pressed',String(!show));byId('nav-qdii').setAttribute('aria-pressed',String(show));if(show)load();else window.dispatchEvent(new Event('resize'));}
byId('nav-ndx').onclick=()=>{history.replaceState(null,'',location.pathname);switchView('ndx');};
byId('nav-qdii').onclick=()=>{history.replaceState(null,'','#qdii');switchView('qdii');};
byId('qdii-retry').onclick=load;
byId('qdii-search').oninput=e=>{query=e.target.value.trim().toLowerCase();render();};
for(const b of document.querySelectorAll('[data-qdii-index]'))b.onclick=()=>{index=b.dataset.qdiiIndex;document.querySelectorAll('[data-qdii-index]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render();};
for(const b of document.querySelectorAll('[data-qdii-status]'))b.onclick=()=>{status=b.dataset.qdiiStatus;document.querySelectorAll('[data-qdii-status]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render();};
window.addEventListener('hashchange',()=>switchView(location.hash==='#qdii'?'qdii':'ndx'));
switchView(location.hash==='#qdii'?'qdii':'ndx');
})();
