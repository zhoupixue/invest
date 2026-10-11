const {JSDOM}=require('jsdom');const fs=require('node:fs');const assert=require('node:assert/strict');
const dom=new JSDOM(fs.readFileSync('web/index.html','utf8'),{runScripts:'outside-only',url:'https://invest.test'});const w=dom.window;
const data=JSON.parse(fs.readFileSync('dist/data.json','utf8'));let instances=[];
w.fetch=async()=>({ok:true,json:async()=>JSON.parse(JSON.stringify(data))});
w.Chart=class{constructor(el,c){this.data=c.data;this.options=c.options;this.hidden={};instances.push(this)}destroy(){this.destroyed=true}isDatasetVisible(i){return !this.hidden[i]}setDatasetVisibility(i,on){this.hidden[i]=!on}update(){}};
w.eval(fs.readFileSync('web/app.js','utf8'));
setTimeout(()=>{try{
 const d=w.document;const cards=[...d.querySelectorAll('.card')];assert.equal(cards.length,5);assert.equal(d.querySelector('#date').textContent,data.date);assert.equal(instances[0].data.labels.length,252);
 d.querySelector('#ranges button').click();assert.equal(instances.at(-2).data.labels.length,63);
 cards[1].click();assert.equal(d.querySelector('#chart-title').textContent,'市场宽度');assert.equal(instances.at(-1).data.datasets.length,5);
 const legend=d.querySelector('#legend button');legend.click();assert.equal(legend.getAttribute('aria-pressed'),'false');legend.click();assert.equal(legend.getAttribute('aria-pressed'),'true');
 cards[2].click();assert.equal(instances.at(-1).data.datasets[0].label,'VIX');cards[3].click();assert.equal(instances.at(-1).data.datasets.length,3);
 cards[4].click();assert.equal(instances.at(-1).data.labels.length,data.eps.dates.length);assert.equal(d.querySelector('#ranges button').disabled,true);assert.equal(d.querySelectorAll('#values tbody tr').length,data.eps.dates.length);
 assert.equal(d.querySelector('#empty').hidden,true);assert.equal(d.querySelector('#drawdown-wrap').hidden,true);assert.ok(!d.body.textContent.includes('授权待核实'));
 console.log('PASS: five modules, range switching, legend toggles, EPS nodes, data table and metadata');
 }catch(e){console.error(e);process.exitCode=1}},30);
