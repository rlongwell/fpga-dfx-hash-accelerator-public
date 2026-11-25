'use strict';
const $ = (id) => document.getElementById(id);
const names = {sha3: 'SHA3-256', sha256: 'SHA-256', blake2s: 'BLAKE2s-256'};
const pages = ['live', 'replay', 'inside', 'results', 'film'];
let token = '', selected = null, algorithm = 'sha3', busy = false, lastJob = null, benchmark = null;
let currentPage = 'live', currentScene = 'absorb', animTick = 0, playing = !matchMedia('(prefers-reduced-motion: reduce)').matches;
let toastTimer;

function toast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 5500);
}
async function api(path, data) {
  const options = data === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Demo-Token': token}, body: JSON.stringify(data)};
  const response = await fetch('/api/' + path, options);
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'The local dashboard could not complete the request.');
  return result;
}
function size(bytes) {return bytes >= 1000000 ? (bytes / 1000000).toFixed(2) + ' MB' : bytes >= 1000 ? (bytes / 1000).toFixed(1) + ' kB' : bytes + ' bytes';}
function time(ns) {return ns >= 1e9 ? (ns / 1e9).toFixed(3) + ' s' : ns >= 1e6 ? (ns / 1e6).toFixed(3) + ' ms' : (ns / 1e3).toFixed(1) + ' µs';}
function node(tag, text, cls) {const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el;}

function showPage(page) {
  if (!pages.includes(page)) page = 'live';
  currentPage = page;
  document.querySelectorAll('.page').forEach(el => el.classList.toggle('active', el.id === 'page-' + page));
  document.querySelectorAll('.nav').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  $('page-title').textContent = {live: 'LIVE BENCH', replay: 'FPGA REPLAY SWEEP', inside: 'INSIDE THE FPGA', results: 'MEASURED RESULTS', film: 'FILM A DEMO'}[page];
  history.replaceState(null, '', '#' + page);
  window.scrollTo(0, 0);
  if (page === 'results') drawCharts();
}
document.querySelectorAll('[data-page]').forEach(el => el.onclick = () => showPage(el.dataset.page));
document.querySelectorAll('[data-go]').forEach(el => el.onclick = () => showPage(el.dataset.go));
window.addEventListener('hashchange', () => showPage(location.hash.slice(1)));

function theme(mode) {
  document.documentElement.dataset.theme = mode;
  $('theme').querySelector('span').textContent = mode === 'dark' ? 'Light theme' : 'Dark theme';
  $('present-theme').textContent = mode === 'dark' ? 'Light theme' : 'Dark theme';
}
$('theme').onclick = async () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  theme(next);
  try {await api('settings', {theme: next});} catch (error) {toast('Theme changed, but could not save preference: ' + error.message);}
};
$('present-theme').onclick = () => $('theme').click();
function presentation(force) {
  const on = force === undefined ? !document.body.classList.contains('presenting') : force;
  document.body.classList.toggle('presenting', on);
  $('present').textContent = on ? '↙ Exit presentation' : '⛶ Present';
}
$('present').onclick = () => presentation();
$('film-present').onclick = () => {showPage('live'); presentation(true);};
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') presentation(false);
  if (document.body.classList.contains('presenting') && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName) && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
    event.preventDefault();
    showPage(pages[(pages.indexOf(currentPage) + (event.key === 'ArrowRight' ? 1 : pages.length-1)) % pages.length]);
  }
});

function choose(file) {
  if (busy || !file) return;
  if (file.size > 16 * 1048576) {toast('Please choose a file up to 16.78 MB for this demo.'); return;}
  selected = file;
  $('file-name').textContent = file.name;
  $('file-detail').textContent = size(file.size) + ' · ready for hardware hashing';
  $('run').disabled = false;
}
$('file-input').onchange = event => choose(event.target.files[0]);
['dragenter', 'dragover'].forEach(type => $('dropzone').addEventListener(type, event => {event.preventDefault(); if (!busy) $('dropzone').classList.add('dragging');}));
['dragleave', 'drop'].forEach(type => $('dropzone').addEventListener(type, event => {event.preventDefault(); $('dropzone').classList.remove('dragging'); if (type === 'drop') choose(event.dataTransfer.files[0]);}));
$('sample').onclick = () => {
  const data = new Uint8Array(8192);
  for (let i = 0; i < data.length; i++) data[i] = i & 255;
  choose(new File([data], 'zybo-demo-8192-bytes.dat', {type: 'application/octet-stream'}));
};
$('comparison-sample').onclick = () => {
  const data = new Uint8Array(16 * 1048576);
  for (let i=0;i<data.length;i++) data[i]=i&255;
  choose(new File([data], 'sha3-comparison-16777216-bytes.bin', {type:'application/octet-stream'}));
};
$('compare-cores').onchange = () => {
  if ($('compare-cores').checked) {
    $('all-algorithms').checked=false;
    document.querySelector('[data-alg="sha3"]').click();
  }
  setBusy(false);
};
document.querySelectorAll('[data-alg]').forEach(el => el.onclick = () => {
  if (busy) return;
  algorithm = el.dataset.alg;
  document.querySelectorAll('[data-alg]').forEach(button => button.classList.toggle('selected', button === el));
  $('engine-label').textContent = names[algorithm];
});
function setBusy(value) {
  busy = value;
  ['connect', 'sample', 'comparison-sample', 'file-input', 'all-algorithms', 'compare-cores', 'transport', 'replay-start', 'replay-check', 'guided-replay'].forEach(id => $(id).disabled = value);
  document.querySelectorAll('[data-alg]').forEach(el => el.disabled = value || ($('compare-cores').checked && el.dataset.alg !== 'sha3'));
  $('all-algorithms').disabled = value || $('compare-cores').checked;
  $('run').disabled = value || !selected;
  $('run').querySelector('span').textContent = value ? 'Working on the board…' : $('compare-cores').checked ? 'Compare on the FPGA' : 'Hash on the FPGA';
  $('connect').classList.toggle('hidden', value);
  $('cancel').classList.toggle('hidden', !value);
  $('cancel').disabled = false;
  $('cancel').textContent = 'Cancel';
}
function transportLabel() { return {'usb-uart':'USB UART','ssh-wired':'Wired SSH','ssh-wifi':'Wi-Fi SSH'}[$('transport').value]; }
$('transport').onchange = () => {
  $('transport-label').textContent=transportLabel();
  $('connection-value').textContent=transportLabel();
  $('transfer-path-label').textContent=$('transport').value==='usb-uart'?'USB':'SSH';
  $('transport-detail').textContent=$('transport').value==='usb-uart'?'Uses the existing USB console. Large files take longer to transfer.':'Key-authenticated uploads; transfer time is outside the hash timer.';
  boardStatus(null);
};
function boardStatus(board) {
  const connected = Boolean(board);
  $('connection').classList.toggle('connected', connected);
  $('side-dot').classList.toggle('connected', connected);
  $('connection').replaceChildren(node('i'), document.createTextNode(connected ? 'Board verified' : 'Board not checked'));
  $('side-status').textContent = connected ? 'Hash profile · '+transportLabel() : 'Ready to connect';
  $('profile-value').textContent = connected ? 'hash / compact SHA3' : '—';
  $('identity-value').textContent = connected ? 'Image & service match' : 'Not checked';
}

function renderResult(result) {
  const row = node('article', undefined, 'result-row');
  if(result.core) row.dataset.core=result.core;
  const heading = node('div', undefined, 'result-title');
  heading.append(node('strong', result.core_label ? result.core_label+' · '+names[result.algorithm] : names[result.algorithm]), node('span', '✓ Digest verified', 'verified'));
  const copy = node('button', 'Copy digest', 'text-button');
  copy.onclick = () => navigator.clipboard.writeText(result.digest).then(() => toast('Digest copied.')).catch(() => toast('Select the digest below to copy it.'));
  heading.append(copy);
  row.append(heading);
  const timing = node('div', undefined, 'hash-time');
  timing.append(node('strong', time(result.local_hash_ns)), node('span', result.repeats ? 'ON-BOARD HASH TIME · MEDIAN OF '+result.repeats : 'ON-BOARD HASH TIME · SINGLE RUN'));
  row.append(timing);
  for (const [label, digest, cls] of [['FPGA', result.digest, ''], ['PC', result.reference_digest, 'reference']]) {
    const line = node('div', undefined, 'digest-row ' + cls);
    line.append(node('span', label), node('code', digest));
    row.append(line);
  }
  const metrics = node('div', undefined, 'result-metrics');
  for (const [label, value] of [['FPGA elapsed cycles', result.core_cycles.toLocaleString()], ['Partial reconfiguration', result.manager_load_ns ? time(result.manager_load_ns) : 'Already loaded']]) {
    const part = node('span'); part.append(label + ' ', node('strong', value)); metrics.append(part);
  }
  if(result.repeats) {
    const range=node('span');range.append('Sample range ',node('strong',time(result.minimum_hash_ns)+' – '+time(result.maximum_hash_ns)));metrics.append(range);
  }
  row.append(metrics, node('p', 'Direct on-board API: RAM input + driver + DMA + core. Upload and reconfiguration are outside this timer.', 'result-disclaimer'));
  return row;
}
function renderJob(job) {
  if (job.kind === 'replay') { renderReplay(job); return; }
  document.dispatchEvent(new CustomEvent('demojobupdated', {detail: job}));
  if (job.kind === 'hash') lastJob = job;
  if (job.board) boardStatus(job.board);
  const stage = job.stage;
  const titles = {connecting: 'Connecting to the physical board', uploading: 'Transferring file to the board', loading: 'Loading '+(job.current_core_label || 'hash core'), hashing: 'Hashing in programmable logic', restoring: 'Restoring the compact SHA3 engine', complete: job.kind === 'probe' ? 'Board check passed' : 'Hashing complete', failed: 'The run could not complete', cancelled: 'Transfer cancelled'};
  $('stage-label').textContent = titles[stage] || stage;
  const details = {connecting: 'Checking the boot image and hardware service.', uploading: size(job.bytes_sent || 0) + ' / ' + size(job.transfer_bytes || job.file?.size || 0), loading: 'Verifying the partial image and reconfiguring the FPGA.', hashing: (job.current_core_label || names[job.current_algorithm]) + ' · Linux → DMA → FPGA', restoring: 'Confirming the original engine with an empty-message hash.', complete: job.kind === 'probe' ? 'Compact image and installed hardware service verified.' : 'Verified on the PC. Compact SHA3 restored; service ready.', failed: job.error, cancelled: job.error};
  $('stage-detail').textContent = details[stage] || '';
  $('pipeline').dataset.running = stage;
  if (job.current_algorithm) $('engine-label').textContent = job.current_core_label || names[job.current_algorithm];
  if (job.restored_sha3) $('engine-label').textContent = names.sha3;
  $('progress-bar').style.width = ((stage === 'complete' ? 1 : job.progress || 0) * 100) + '%';
  if (job.kind === 'hash') {
    $('empty-result').classList.toggle('hidden', job.results.length > 0);
    $('result-list').classList.toggle('comparison-results', Boolean(job.compare_cores));
    if ($('result-list').children.length !== job.results.length) $('result-list').replaceChildren(...job.results.map(renderResult));
    $('result-count').textContent = job.results.length ? job.results.length + ' verified ' + (job.results.length === 1 ? 'digest' : 'digests') : 'Independent PC reference';
    $('export').classList.toggle('hidden', job.state === 'running');
    const complete=job.compare_cores && job.state==='passed' && job.results.length===2;
    $('comparison-summary').classList.toggle('hidden',!complete);
    if(complete){
      const quartz=job.results.find(r=>r.core==='oxide'), compact=job.results.find(r=>r.core==='compact');
      $('comparison-summary').textContent='Same '+size(job.file.size)+' file · both digests match the PC · compact '+(quartz.local_hash_ns/compact.local_hash_ns).toFixed(2)+'× the measured throughput';
    }
  }
  if (job.state === 'failed') boardStatus(null);
}
async function follow(id) {
  try {
    while (true) {
      const job = await api('jobs/' + id);
      renderJob(job);
      if (job.state !== 'running') {
        if (job.state === 'failed') toast(job.error);
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 250));
    }
  } finally {setBusy(false);}
}
$('connect').onclick = async () => {
  setBusy(true);
  try {const job = await api('jobs', {kind: 'probe', transport: $('transport').value}); await follow(job.id);} catch (error) {setBusy(false); toast(error.message);}
};
$('run').onclick = async () => {
  if (!selected || busy) return;
  setBusy(true);
  $('result-list').replaceChildren();
  $('comparison-summary').classList.add('hidden');
  $('empty-result').classList.remove('hidden');
  $('export').classList.add('hidden');
  $('stage-label').textContent = 'Preparing file';
  $('stage-detail').textContent = 'The PC calculates independent reference digests.';
  try {
    const response = await fetch('/api/files', {method: 'POST', headers: {'X-Demo-Token': token, 'X-File-Name': encodeURIComponent(selected.name), 'Content-Type': 'application/octet-stream'}, body: selected});
    const file = await response.json();
    if (!response.ok) throw Error(file.error);
    const job = await api('jobs', {kind: 'hash', transport: $('transport').value, file_id: file.id, compare_cores: $('compare-cores').checked, algorithms: $('all-algorithms').checked ? ['sha3', 'sha256', 'blake2s'] : [algorithm]});
    await follow(job.id);
  } catch (error) {setBusy(false); toast(error.message); $('stage-label').textContent = 'The request could not complete'; $('stage-detail').textContent = error.message; document.dispatchEvent(new CustomEvent('demojobupdated',{detail:{id:null,kind:'hash',state:'failed',error:error.message}}));}
};
$('cancel').onclick = async () => {
  $('cancel').disabled = true;
  $('cancel').textContent = 'Finishing safely…';
  try {await api('cancel', {}); toast('Stopping safely. A hash already in progress will finish and restore SHA3.');} catch (error) {toast(error.message);}
};
$('export').onclick = () => {
  if (!lastJob) return;
  const link = node('a');
  link.href = URL.createObjectURL(new Blob([JSON.stringify(lastJob, null, 2) + '\n'], {type: 'application/json'}));
  link.download = 'zybo-hash-' + lastJob.id + '.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
};

for (const id of ['byte-lane', 'wide-lane']) for (let i = 0; i < 17; i++) $(id).append(node('i'));
for (const id of ['round-grid', 'padding-grid']) for (let i = 0; i < 25; i++) $(id).append(node('span', String(i).padStart(2, '0'), id === 'padding-grid' && i < 17 ? 'rate' : ''));
function animateFrame() {
  const inputCycle = animTick % 153;
  $('input-cycle').textContent = inputCycle;
  $('byte-count').textContent = Math.min(inputCycle, 136) + ' / 136 bytes';
  $('wide-count').textContent = Math.min(inputCycle * 8, 136) + ' / 136 bytes';
  [...$('byte-lane').children].forEach((el, i) => {
    const bytes = Math.max(0, Math.min(8, inputCycle - i * 8));
    el.classList.toggle('filled', bytes === 8); el.textContent = bytes + '/8';
    el.style.setProperty('--lane-fill', (bytes / 8 * 100) + '%');
  });
  [...$('wide-lane').children].forEach((el, i) => {el.classList.toggle('filled', i < inputCycle); el.textContent = (i < inputCycle ? 8 : 0) + '/8';});
  const round = animTick % 24;
  $('round-number').textContent = round + 1;
  [...$('round-grid').children].forEach((el, i) => {el.classList.toggle('mix', ((i * 7 + round * 11) % 13) < 6); el.textContent = ((i * 37 + round * 19) % 256).toString(16).padStart(2, '0').toUpperCase();});
  [...$('padding-grid').children].forEach((el, i) => el.classList.toggle('pad-on', i === animTick % 17 || i === 16));
}
function showScene(scene) {
  currentScene = scene; animTick = 0;
  ['absorb', 'rounds', 'padding'].forEach(name => $('scene-' + name).classList.toggle('hidden', name !== scene));
  document.querySelectorAll('[data-scene]').forEach(el => el.classList.toggle('selected', el.dataset.scene === scene));
  animateFrame();
}
document.querySelectorAll('[data-scene]').forEach(el => el.onclick = () => showScene(el.dataset.scene));
$('anim-play').onclick = () => {playing = !playing; $('anim-play').textContent = playing ? 'Pause' : 'Play';};
$('anim-play').textContent = playing ? 'Pause' : 'Play';
$('anim-reset').onclick = () => {animTick = 0; animateFrame();};
$('anim-step').onclick = () => {playing = false; $('anim-play').textContent = 'Play'; animTick++; animateFrame();};
setInterval(() => {if (playing && currentPage === 'inside' && !document.hidden) {animTick++; animateFrame();}}, 180);
animateFrame();

let metric = 'dma_MB_s';
document.querySelectorAll('[data-metric]').forEach(el => el.onclick = () => {
  metric = el.dataset.metric;
  document.querySelectorAll('[data-metric]').forEach(button => button.classList.toggle('selected', button === el));
  drawCharts();
});
function drawCharts() {
  if (!benchmark) return;
  const container = $('throughput-chart'); container.replaceChildren();
  const variants = [['current', 'Original project core', 'original'], ['oxide_elastic', 'Oxide Quartz · full-rate adapter', ''], ['compact', 'Compact wide core', 'compact']];
  const maximum = Math.max(...variants.map(([key]) => benchmark[key][metric]));
  for (const [key, label, cls] of variants) {
    const heading = node('div', undefined, 'bar-label');
    heading.append(node('strong', label), node('span', benchmark[key][metric].toFixed(2) + ' MB/s'));
    const track = node('div', undefined, 'chart-track'), fill = node('div', undefined, 'chart-fill ' + cls);
    fill.style.width = benchmark[key][metric] / maximum * 100 + '%'; track.append(fill); container.append(heading, track);
  }
  $('resource-chart').replaceChildren();
  for (const [key, label] of [['rp_luts', 'LUTs'], ['rp_ffs', 'Flip-flops']]) {
    const group = node('div', undefined, 'resource-group'); group.append(node('strong', label));
    const maximum = Math.max(benchmark.oxide_elastic[key], benchmark.compact[key]);
    for (const [variant, cls] of [['oxide_elastic', ''], ['compact', 'compact']]) {
      const row = node('div', undefined, 'resource-row'), track = node('div', undefined, 'chart-track'), fill = node('div', undefined, 'chart-fill ' + cls);
      fill.style.width = benchmark[variant][key] / maximum * 100 + '%'; track.append(fill);
      row.append(track, node('span', benchmark[variant][key].toLocaleString())); group.append(row);
    }
    $('resource-chart').append(group);
  }
}
async function init() {
  showPage(location.hash.slice(1) || 'live');
  try {
    const data = await api('bootstrap');
    token = data.token; benchmark = data.benchmark;
    theme(data.settings.theme === 'light' ? 'light' : 'dark');
    boardStatus(data.board);
    drawCharts();
    if (data.active) {setBusy(true); await follow(data.active);}
    else if (new URLSearchParams(location.search).get('replay')) {
      const job=await api('jobs/'+new URLSearchParams(location.search).get('replay'));
      if(job.kind==='replay'&&job.state==='passed'){renderReplay(job);if(currentPage==='replay')replayView(true);}
    }
  } catch (error) {toast('Cannot reach the dashboard: ' + error.message);}
}
init();
