// SPDX-License-Identifier: MIT
// Actual drag-and-drop, automatic import and result bundle checks. Node >= 22 and an installed Chromium browser.
const fs = require('fs'), path = require('path'), os = require('os'), crypto = require('crypto');
const { spawn, execFileSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const sourceHash = file => crypto.createHash('sha256').update(fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n')).digest('hex');
const hash = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const candidates = [process.env.ROBUSTBAND_BROWSER_PATH, 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe', '/usr/bin/microsoft-edge', '/usr/bin/google-chrome',
  '/usr/bin/chromium', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'];
const browserPath = candidates.find((candidate) => candidate && fs.existsSync(candidate));
assert(browserPath, 'Set ROBUSTBAND_BROWSER_PATH to an installed Chromium browser.');

let python, browser, ws, launch = '', exceptions = [], id = 0;
const pending = new Map();
const checked = [];
async function until(test, label, timeout = 25000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { if (await test()) return; await sleep(80); }
  throw new Error('Timed out: ' + label);
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const request = ++id; pending.set(request, { resolve, reject });
    ws.send(JSON.stringify({ id: request, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

function pythonCommand() {
  const override = process.env.ROBUSTBAND_PYTHON;
  if (override) return { command: override, args: [] };
  const candidates = process.platform === 'win32'
    ? [{ command: 'python', args: [] }, { command: 'py', args: ['-3'] }]
    : [{ command: 'python3', args: [] }, { command: 'python', args: [] }];
  for (const candidate of candidates) {
    try {
      execFileSync(candidate.command, [...candidate.args, '-c',
        'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'], { stdio: 'ignore' });
      return candidate;
    } catch {}
  }
  throw new Error('No Python 3.9+ interpreter found; set ROBUSTBAND_PYTHON.');
}

async function main() {
  const py=pythonCommand();
  const fixtures=process.env.ROBUSTBAND_IMPORT_FIXTURES||path.join(ROOT,'build','import-fixtures');
  if(!process.env.ROBUSTBAND_IMPORT_FIXTURES)execFileSync(py.command,[...py.args,'-S','experiments/import_fixtures.py',fixtures],{cwd:ROOT,stdio:'ignore'});
  const cases=JSON.parse(fs.readFileSync(path.join(fixtures,'cases.json'),'utf8'));
  const official=process.env.ROBUSTBAND_MMLU_SOURCES;
  if(official)cases.push({name:'official MMLU-Pro complete CS subject',files:['Meta-Llama-3-8B','Meta-Llama-3-8B-Instruct'].map(m=>path.join(official,'model_outputs_'+m+'_5shots.zip')),n:410,band:['-39/410','-39/410']});
  python=spawn(py.command,[...py.args,'-m','robustband','ui','--no-browser'],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});
  python.stdout.on('data',data=>{launch+=data.toString();});
  await until(()=>/http:\/\/127\.0\.0\.1:\d+\/#\S+/.test(launch),'server launch');
  const base=launch.match(/http:\/\/127\.0\.0\.1:\d+\/#\S+/)[0];
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),'robustband-import-browser-'));
  browser=spawn(browserPath,['--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port=0','--user-data-dir='+profile,base],{windowsHide:true,stdio:'ignore'});
  const active=path.join(profile,'DevToolsActivePort');await until(()=>fs.existsSync(active),'debugger');
  const port=fs.readFileSync(active,'utf8').split('\n')[0];
  const targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=event=>{const item=JSON.parse(event.data);if(item.id){const task=pending.get(item.id);pending.delete(item.id);if(item.error)task.reject(new Error(JSON.stringify(item.error)));else task.resolve(item.result);}else if(item.method==='Runtime.exceptionThrown')exceptions.push(item.params.exceptionDetails.exception?.description||item.params.exceptionDetails.text);};
  await send('Runtime.enable');await send('Page.enable');
  await until(()=>evaluate('typeof options==="object" && options!==null'),'page ready');
  await evaluate('(()=>{const e=document.createElement("input");e.type="file";e.multiple=true;e.id="fixturePicker";e.hidden=true;document.body.append(e);})()');
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
  const doc=await send('DOM.getDocument');const input=await send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#fixturePicker'});
  const downloads=fs.mkdtempSync(path.join(ROOT,'build','import-downloads-'));
  await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});
  for(const item of cases){
    if(item.name==='MMLU-Pro ZIP'){
      await send('DOM.setFileInputFiles',{nodeId:input.nodeId,files:[item.files[0]]});
      await evaluate('(()=>{const dt=new DataTransfer();dt.items.add(document.getElementById("fixturePicker").files[0]);const e=new Event("drop",{bubbles:true,cancelable:true});Object.defineProperty(e,"dataTransfer",{value:dt});document.getElementById("dropZone").dispatchEvent(e);})()');
      assert(await evaluate('!busy && importedFiles.length===1 && importedResult===null && document.getElementById("quickImport").hidden'),'First archive did not wait for its partner');checked.push('first archive waits without a stale result');
    }
    await send('DOM.setFileInputFiles',{nodeId:input.nodeId,files:item.name==='MMLU-Pro ZIP'?[item.files[1]]:item.files});
    await evaluate('(()=>{const dt=new DataTransfer();for(const file of document.getElementById("fixturePicker").files)dt.items.add(file);const e=new Event("drop",{bubbles:true,cancelable:true});Object.defineProperty(e,"dataTransfer",{value:dt});document.getElementById("dropZone").dispatchEvent(e);})()');
    await until(async()=>{const state=await evaluate('({ready:!busy&&importedResult!==null&&!document.getElementById("quickImport").hidden,failed:!busy&&!document.getElementById("error").hidden,error:document.getElementById("error").textContent})');if(state.failed)throw new Error(item.name+': '+state.error);return state.ready;},'import '+item.name,60000);
    const got=await evaluate('({n:importedResult.report.result.n_items,band:importedResult.report.result.exact_band??importedResult.report.pairs[0].exact_band,error:document.getElementById("error").textContent,errorVisible:!document.getElementById("error").hidden})');
    assert(got.n===item.n && JSON.stringify(got.band)===JSON.stringify(item.band),item.name+': '+JSON.stringify(got));
    assert(!got.errorVisible,item.name+' displayed an error: '+got.error);
    checked.push('drop → automatic analysis: '+item.name);
    if(item.matrix){await until(()=>evaluate('document.getElementById("importRankingFrame").contentDocument?.body?.textContent.includes("Pairwise comparisons")'),'ranking report renders inside sandbox');assert(await evaluate('document.getElementById("importRankingFrame").sandbox.value==="allow-same-origin"'),'Report must remain script-sandboxed');checked.push('ranking report renders inside script-blocked sandbox');}
    if(item.name==='csv'){
      await evaluate('document.getElementById("importBundle").click()');
      const bundle=path.join(downloads,'robustband-results.zip');await until(()=>fs.existsSync(bundle),'download result bundle');
      execFileSync(py.command,[...py.args,'-S','-c','import sys,zipfile,json,hashlib; from robustband.domains import verify_audit; z=zipfile.ZipFile(sys.argv[1]); assert set(z.namelist())=={"report.json","report.html","paired.jsonl","import_manifest.json"}; assert verify_audit(json.loads(z.read("report.json"))); assert hashlib.sha256(z.read("report.json")).hexdigest()==json.loads(z.read("import_manifest.json"))["report_json_sha256"]',bundle],{cwd:ROOT,stdio:'pipe'});
      checked.push('downloaded bundle preserves inputs, provenance and replay');
      await evaluate('document.getElementById("modelA").value="Changed model";document.getElementById("modelA").dispatchEvent(new Event("input"))');
      assert(await evaluate('document.getElementById("quickImport").hidden && last===null'),'Changed settings retained a stale import bundle');checked.push('changed settings hide the previous imported bundle');
    }
  }
  if(official){
    const image=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
    fs.writeFileSync(path.join(ROOT,'build','import-official-desktop.png'),Buffer.from(image.data,'base64'));
    await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    assert(await evaluate('document.documentElement.scrollWidth<=window.innerWidth'),'Imported official result overflows mobile width');checked.push('official import fits a 390px viewport');
    const mobile=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(ROOT,'build','import-official-mobile.png'),Buffer.from(mobile.data,'base64'));
    await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
    const category=await evaluate('Array.from(document.getElementById("importCategory").options).map(x=>x.value).find(x=>x!==importedResult.selected_category)');
    if(category){await evaluate('document.getElementById("importCategory").value='+JSON.stringify(category)+';document.getElementById("importCategory").dispatchEvent(new Event("change"))');await until(()=>evaluate('!busy && importedResult?.selected_category==='+JSON.stringify(category)),'subject change',60000);checked.push('subject selection reruns a complete paired subject');}
    await send('DOM.setFileInputFiles',{nodeId:input.nodeId,files:['Meta-Llama-3-8B-Instruct','Meta-Llama-3-70B-Instruct'].map(m=>path.join(official,'model_outputs_'+m+'_5shots.zip'))});
    await evaluate('(()=>{const dt=new DataTransfer();for(const f of document.getElementById("fixturePicker").files)dt.items.add(f);const e=new Event("drop",{bubbles:true,cancelable:true});Object.defineProperty(e,"dataTransfer",{value:dt});document.getElementById("dropZone").dispatchEvent(e);})()');
    await until(()=>evaluate('!busy && !document.getElementById("error").hidden'),'reject unpaired archives',60000);
    assert(await evaluate('importedResult===null'),'Rejected import retained a stale result');checked.push('unpaired official archives show an error without stale results');
  }
  assert(exceptions.length===0,'Script exceptions: '+exceptions.join(', '));
  const version=await evaluate('options.version');const result={schema:'robustband.import_browser/v1',version,browser:(await send('Browser.getVersion')).product,checked,script_exceptions:exceptions,official_data_used:Boolean(official),independent_human_user:false,source_sha256_lf:{'robustband/ui.html':sourceHash(path.join(ROOT,'robustband/ui.html')),'experiments/import_browser_smoke.cjs':sourceHash(__filename)}};
  fs.writeFileSync(path.join(ROOT,'results','import_ui_'+version+'.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({browser:result.browser,checks:checked.length,exceptions:exceptions.length,official_data_used:result.official_data_used}));
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1;}).finally(async()=>{
 if(launch.startsWith('http://127.0.0.1:')){try{const [url,token]=launch.split('#');await fetch(url+'api/stop',{method:'POST',headers:{'X-Robustband-Token':token,'Content-Length':'2'},body:'{}'});}catch{}}
 if(ws&&ws.readyState===1){try{await send('Browser.close');}catch{}ws.close();}
 if(python&&!python.killed)python.kill();if(browser&&!browser.killed)browser.kill();await sleep(500);
});
