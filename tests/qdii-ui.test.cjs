const {JSDOM}=require('jsdom'),fs=require('node:fs'),assert=require('node:assert/strict');
const data=JSON.parse(fs.readFileSync('dist/qdii.json','utf8'));
async function boot(fail=false){const dom=new JSDOM(fs.readFileSync('dist/index.html','utf8'),{url:'https://ndx5s.test/#qdii',runScripts:'outside-only'}),w=dom.window;
 w.fetch=async url=>({ok:!fail,json:async()=>url==='/qdii.json'?JSON.parse(JSON.stringify(data)):{success:true}});w.console.error=()=>{};w.eval(fs.readFileSync('web/qdii.js','utf8'));await new Promise(r=>setTimeout(r,30));return w;}
(async()=>{
 const w=await boot(),d=w.document;assert.equal(d.querySelector('#ndx-view').hidden,true);assert.equal(d.querySelector('#qdii-view').hidden,false);
 assert.equal(d.querySelectorAll('.qdii-fund').length,data.group_count);assert.equal(d.querySelectorAll('.qdii-share').length,data.share_count);
 for(const s of data.funds){const row=[...d.querySelectorAll('.qdii-share')].find(e=>e.querySelector('.qdii-code').textContent===s.code);assert.ok(row,s.code);assert.ok(row.textContent.includes(s.status==='paused'?'暂停申购':s.status==='unlimited'?'不限购':s.limit_yuan.toLocaleString('zh-CN')+'元'));}
 d.querySelector('[data-qdii-status="paused"]').click();assert.equal(d.querySelectorAll('.qdii-fund').length,data.groups.filter(g=>g.shares.some(s=>s.status==='paused')).length);
 d.querySelector('[data-qdii-status="all"]').click();d.querySelector('[data-qdii-index="spx"]').click();assert.equal(d.querySelectorAll('.qdii-fund').length,data.groups.filter(g=>g.index==='spx').length);
 d.querySelector('[data-qdii-index="all"]').click();let input=d.querySelector('#qdii-search');input.value=data.funds[0].code;input.dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('.qdii-fund').length,1);
 input.value='not-a-fund';input.dispatchEvent(new w.Event('input'));assert.equal(d.querySelectorAll('.qdii-fund').length,0);assert.ok(d.querySelector('.qdii-empty'));
 d.querySelector('#nav-ndx').click();assert.equal(d.querySelector('#ndx-view').hidden,false);assert.equal(d.querySelector('#qdii-view').hidden,true);
 const bad=await boot(true);assert.equal(bad.document.querySelector('#qdii-error').hidden,false);assert.equal(bad.document.querySelector('#qdii-content').hidden,true);
 console.log('PASS: QDII source equality, A/C grouping, filters, code search, view switching and fetch failure');
})().catch(e=>{console.error(e);process.exitCode=1});
