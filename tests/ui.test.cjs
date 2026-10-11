const {JSDOM}=require('jsdom');const fs=require('node:fs');const assert=require('node:assert/strict');
const dom=new JSDOM(fs.readFileSync('web/index.html','utf8'),{runScripts:'outside-only',url:'https://invest.test'});const w=dom.window;
const data=JSON.parse(fs.readFileSync('dist/data.json','utf8'));let instances=[];
w.matchMedia=()=>({matches:false});
w.fetch=async()=>({ok:true,json:async()=>JSON.parse(JSON.stringify(data))});
w.Chart=class{constructor(el,c){this.data=c.data;this.options=c.options;this.hidden={};instances.push(this)}destroy(){this.destroyed=true}isDatasetVisible(i){return !this.hidden[i]}setDatasetVisibility(i,on){this.hidden[i]=!on}update(){}};
w.eval(fs.readFileSync('web/app.js','utf8'));
setTimeout(()=>{try{
 const d=w.document;const cards=[...d.querySelectorAll('.card')];assert.equal(cards.length,5);assert.equal(d.querySelector('#date').textContent,data.date);if(data.modules[0].available)assert.equal(instances[0].data.labels.length,252);
 d.querySelector('#ranges button').click();if(data.modules[0].available)assert.equal(instances.at(-2).data.labels.length,63);
 cards[1].click();assert.equal(d.querySelector('#chart-title').textContent,'市场宽度');if(data.modules[1].available)assert.equal(instances.at(-1).data.datasets.length,5);
 const legend=d.querySelector('#legend button');if(legend){legend.click();assert.equal(legend.getAttribute('aria-pressed'),'false');legend.click();assert.equal(legend.getAttribute('aria-pressed'),'true');}
 cards[2].click();if(data.modules[2].available)assert.equal(instances.at(-1).data.datasets[0].label,'VIX');cards[3].click();if(data.modules[3].available)assert.equal(instances.at(-1).data.datasets.length,3);
 cards[4].click();if(data.modules[4].available)assert.equal(instances.at(-1).data.labels.length,data.eps.dates.length);assert.equal(d.querySelector('#ranges button').disabled,true);assert.equal(d.querySelector('#values'),null);assert.equal(d.querySelector('#notes-wrap'),null);assert.equal(d.querySelector('#attributions'),null);assert.ok(d.querySelector('#report-title').textContent.includes(data.date+' 日报'));assert.equal(d.querySelector('.brand-sub').textContent,'NDX投资日报');assert.equal(d.querySelector('.daily'),null);assert.equal(d.querySelector('details summary').textContent,'如何理解这个指标');
 assert.equal(d.querySelector('#empty').hidden,data.modules[4].available);assert.equal(d.querySelector('#drawdown-wrap').hidden,true);assert.ok(!d.body.textContent.includes('授权待核实'));
 console.log('PASS: five modules, range switching, legend toggles, EPS nodes, requested layout and metadata');
 }catch(e){console.error(e);process.exitCode=1}},30);
