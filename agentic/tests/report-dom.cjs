// DOM unit checks, not a replacement for visual browser inspection.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {createRequire} = require('node:module');
const path = require('node:path');
const resolver = createRequire(path.resolve(process.argv[2] || 'package.json'));
const {JSDOM,VirtualConsole} = resolver('jsdom');
const html = fs.readFileSync(process.argv[3] || 'agentic/report.html','utf8');
const errors=[]; let printed=false, downloaded=false;
const vc = new VirtualConsole(); vc.on('jsdomError',error=>errors.push(error.message));
const dom = new JSDOM(html,{runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
  // JSDOM has no native dialog layout or print UI. Test the application's handlers only.
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.print=()=>{printed=true;};
  w.URL.createObjectURL=()=> 'blob:test'; w.URL.revokeObjectURL=()=>{};
  const original=w.HTMLAnchorElement.prototype.click;
  w.HTMLAnchorElement.prototype.click=function(){if(this.download==='report-data.json') downloaded=true; else original.call(this);};
}});
const d=dom.window.document;
const report=JSON.parse(d.getElementById('report-data').textContent).report;
assert.equal(report.stages.length,5);
assert.equal(d.querySelectorAll('[data-panel]:not([hidden])').length,1);
d.querySelector('[data-tab="ledger"]').click();
assert.equal(d.getElementById('ledger').hidden,false);
const search=d.getElementById('source-search');search.value='投资';search.dispatchEvent(new dom.window.Event('input'));
assert.equal(d.querySelectorAll('[data-fact]:not([hidden])').length,1);
assert.match(d.getElementById('search-count').textContent,/1/);
d.querySelector('[data-fact]:not([hidden]) [data-source]').click();
assert.equal(d.getElementById('source-dialog').open,true);
assert.equal(d.getElementById('source-quote').textContent,report.case.sources.find(s=>s.source_id==='M004').text);
d.getElementById('source-close').click();assert.equal(d.getElementById('source-dialog').open,false);
d.querySelector('[data-tab="gaps"]').click();
d.querySelector('[data-filter="needs_evidence"]').click();
assert.equal(d.querySelectorAll('[data-gap]:not([hidden])').length,report.gaps.items.filter(g=>g.status==='needs_evidence').length);
d.querySelector('[data-tab="gaps"]').dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
assert.equal(d.getElementById('execution').hidden,false);
assert.equal(d.querySelectorAll('.step').length,5);
d.getElementById('print-report').click();d.getElementById('download-data').click();assert.ok(printed&&downloaded);
const csp=d.querySelector('meta[http-equiv="Content-Security-Policy"]').content;
for(const selector of ['style','script:not([type])']){
 const content=d.querySelector(selector).textContent;
 const hash=crypto.createHash('sha256').update(content).digest('base64');
 assert.ok(csp.includes(hash));
}
assert.equal(d.querySelectorAll('script[src],link[href],iframe,img[src^="http"]').length,0);
assert.deepEqual(errors,[]);
dom.window.close();
console.log(JSON.stringify({status:'PASS',checks:['tabs','keyboard tabs','source dialog','search','gap filter','print/download handlers','CSP hashes','offline assets','JS errors'],scope:'DOM handlers, keyboard tabs, source dialog, search, gap filters, export, CSP hashes; no visual layout validation'}));
