// SPDX-License-Identifier: MIT
// Browser checks for the ranking page. Node >= 22 and an installed Chromium browser.
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
  python=spawn(py.command,[...py.args,'-m','robustband','ui','--no-browser'],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});
  python.stdout.on('data', (data) => { launch += data.toString(); });
  await until(() => /http:\/\/127\.0\.0\.1:\d+\/#\S+/.test(launch), 'local server launch');
  const base = launch.match(/http:\/\/127\.0\.0\.1:\d+\/#\S+/)[0];
  const url = base.replace('/#', '/matrix#');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'robustband-browser-'));
  browser = spawn(browserPath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=0', '--user-data-dir=' + profile, url], { windowsHide: true, stdio: 'ignore' });
  const active = path.join(profile, 'DevToolsActivePort');
  await until(() => fs.existsSync(active), 'browser debugger');
  const port = fs.readFileSync(active, 'utf8').split('\n')[0];
  const targets = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
  ws = new WebSocket(targets.find((target) => target.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  ws.onmessage = (event) => {
    const item = JSON.parse(event.data);
    if (item.id) { const task = pending.get(item.id); pending.delete(item.id); if (item.error) task.reject(new Error(JSON.stringify(item.error))); else task.resolve(item.result); }
    else if (item.method === 'Runtime.exceptionThrown') exceptions.push(item.params.exceptionDetails.exception?.description || item.params.exceptionDetails.text);
  };
  await send('Runtime.enable'); await send('Page.enable');
  await until(() => evaluate("document.readyState === 'complete' && typeof options === 'object'"), 'page init');

  assert((await evaluate("document.getElementById('back').href")).endsWith('/#' + base.split('#')[1]), 'Back link lost the session token');
  await evaluate("document.getElementById('example').click()");
  await until(() => evaluate("!document.getElementById('result').hidden"), 'example result');
  const verdict = await evaluate("document.getElementById('verdict').textContent");
  const verdicts = ['名次稳健', '第一名稳定、其余随规则变化', '第一名随规则变化',
                    'Stable order', 'Stable leader, moving rest', 'Rule-sensitive leader'];
  assert(verdicts.includes(verdict), 'Unexpected verdict text: ' + verdict);
  assert((await evaluate("document.querySelectorAll('#rankTable table tr').length")) === 4, 'Rank table should list three models');
  assert((await evaluate("document.querySelectorAll('#pairTable table tr').length")) === 4, 'Pair table should list three models');
  assert((await evaluate("document.querySelectorAll('#protocolTable table tr').length")) >= 2, 'Protocol table missing rows');
  assert((await evaluate("document.getElementById('error').textContent")) === '', 'The page reported an error');
  assert((await evaluate("document.getElementById('finding').textContent")).length > 0, 'Finding sentence missing');
  checked.push('ranking page loads with session token', 'example renders verdict and tables', 'pair labels and protocol rows present');
  const before = await evaluate("document.documentElement.lang");
  const findingBefore = await evaluate("document.getElementById('finding').textContent");
  await evaluate("document.getElementById('language').click()");
  const after = await evaluate("document.documentElement.lang");
  const findingAfter = await evaluate("document.getElementById('finding').textContent");
  assert(before !== after && findingBefore !== findingAfter && findingAfter.length > 0, 'Language toggle did not update the page');
  checked.push('language toggle updates text');
  const zeroEndpointText = 'sample_id,model,gold,output\nq1,A,42,42\nq1,B,42,42 then 7\n';
  await evaluate(`(async()=>{
    const value=await api('/api/matrix/audit',{text:${JSON.stringify(zeroEndpointText)},format:'csv'});
    window.zeroEndpointReport=value;
    render(value.report,value.html,value.json);
  })()`);
  assert(await evaluate("zeroEndpointReport.report.pairs[0].exact_band.join(',')==='0,1'"), 'Hand-checked zero-endpoint band missing');
  assert(await evaluate("!zeroEndpointReport.html.includes('behind [0, 1]') && zeroEndpointReport.html.includes('ahead [0, 1]')"), 'Exported HTML reverses a nonnegative band');
  assert(await evaluate("/ahead|领先/.test(document.getElementById('pairTable').textContent) && !/behind|落后/.test(document.getElementById('pairTable').textContent)"), 'Browser direction disagrees with exported HTML');
  checked.push('nonnegative zero-endpoint band agrees in browser and exported HTML');
  assert(exceptions.length === 0, 'Script exceptions: ' + exceptions.join(', '));

  const version = (await (await fetch(base.split('#')[0] + 'api/options')).json()).version;
  const result = { schema: 'robustband.matrix_browser/v1', software_version: version, browser: (await send('Browser.getVersion')).product,
    checked, script_exceptions: exceptions, independent_human_user: false,
    source_sha256_lf: { 'robustband/matrix.html': sourceHash(path.join(ROOT, 'robustband/matrix.html')),
                     'experiments/matrix_browser_smoke.cjs': sourceHash(__filename) } };
  fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'results', 'matrix_ui_' + version + '.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ browser: result.browser, checks: checked.length, exceptions: exceptions.length }));
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; }).finally(async () => {
  if (launch.startsWith('http://127.0.0.1:')) {
    try { const [url, token] = launch.split('#'); await fetch(url + 'api/stop', { method: 'POST', headers: { 'X-Robustband-Token': token, 'Content-Length': '2' }, body: '{}' }); } catch {}
  }
  if (ws && ws.readyState === 1) { try { await send('Browser.close'); } catch {} ws.close(); }
  if (python && !python.killed) python.kill();
  if (browser && !browser.killed) browser.kill();
  await sleep(500);
});
