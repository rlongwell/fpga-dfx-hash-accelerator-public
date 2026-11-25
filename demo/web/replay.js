'use strict';
let lastReplay = null;
function replaySize(bytes) {
  for (const [unit, scale] of [['GiB',1073741824],['MiB',1048576],['KiB',1024]])
    if (bytes>=scale) return (bytes/scale).toLocaleString()+' '+unit;
  return bytes+' B';
}
function replayView(results) {
  $('replay-run-view').classList.toggle('hidden',results);
  $('replay-results-view').classList.toggle('hidden',!results);
  $('guided-replay').classList.toggle('hidden',results);
  $('replay-heading').textContent=results?'Replay sweep results':'FPGA memory replay';
}
function replayChart(container, rows, ratio=false) {
  const ns='http://www.w3.org/2000/svg', svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 640 330');svg.setAttribute('role','img');
  svg.setAttribute('aria-label',ratio?'Compact speedup by message size':'SHA3-256 throughput in megabytes per second by message size');
  const add=(tag, attrs, text)=>{const el=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));if(text!==undefined)el.textContent=text;svg.append(el);return el;};
  const left=62,right=616,top=28,bottom=263;
  const ymax=ratio?Math.max(4,Math.ceil(Math.max(...rows.map(r=>r.speedup)))):Math.ceil(Math.max(...rows.flatMap(r=>[r.oxide_MB_per_second,r.compact_MB_per_second]))/50)*50;
  const x=n=>left+(Math.log2(n)-6)/24*(right-left), y=n=>bottom-n/ymax*(bottom-top);
  const ys=ratio?Array.from({length:ymax+1},(_,i)=>i):Array.from({length:ymax/50+1},(_,i)=>i*50);
  for(const value of ys){add('line',{x1:left,y1:y(value),x2:right,y2:y(value),class:ratio&&value===1?'equal-line':'grid-line'});add('text',{x:left-13,y:y(value)+5,'text-anchor':'end'},value+(ratio?'×':''));}
  for(const [power,label] of [[6,'64 B'],[10,'1 KiB'],[14,'16 KiB'],[18,'256 KiB'],[22,'4 MiB'],[26,'64 MiB'],[30,'1 GiB']])
    add('text',{x:x(2**power),y:bottom+29,'text-anchor':'middle'},label);
  add('text',{x:(left+right)/2,y:324,'text-anchor':'middle',class:'axis-label'},'Message size');
  add('text',{x:left,y:14,class:'axis-label'},ratio?'Compact / Quartz (×)':'Throughput (MB/s)');
  for(const [key,cls] of ratio?[['speedup','ratio']]:[['oxide_MB_per_second','oxide'],['compact_MB_per_second','compact']]){
    add('path',{d:rows.map((r,i)=>(i?'L':'M')+x(r.bytes).toFixed(2)+','+y(r[key]).toFixed(2)).join(' '),class:'replay-curve '+cls});
    for(const r of rows)add('circle',{cx:x(r.bytes),cy:y(r[key]),r:2.5,class:'replay-point '+cls});
  }
  container.replaceChildren(svg);
}
function renderReplay(job) {
  document.dispatchEvent(new CustomEvent('demojobupdated',{detail:job}));
  lastReplay=job;
  if(job.board)boardStatus(job.board);
  const running=job.state==='running', counts=job.core_counts||{oxide:0,compact:0};
  $('replay-cancel').classList.toggle('hidden',!running);
  $('replay-start').classList.toggle('hidden',running);
  $('replay-show-results').classList.toggle('hidden',job.state!=='passed');
  $('replay-start').innerHTML=job.state==='passed'?'Run again <span>→</span>':'Start sweep <span>→</span>';
  for(const core of ['oxide','compact']){
    $('replay-'+core+'-count').textContent=counts[core]+' / 200';
    $('replay-'+core+'-bar').style.width=(counts[core]/2)+'%';
    const active=running&&job.stage==='sweeping'&&job.current_core===core;
    document.querySelector('[data-replay-core="'+core+'"]').classList.toggle('active-core',active);
    $('replay-'+core+'-detail').textContent=counts[core]===200?'All 200 hashes complete':active?
      (job.warmup?'Warmup':'Measured round '+job.current_trial+' / 7')+' · '+replaySize(job.current_size||64):
      counts[core]?'Waiting for the next round':'Ready · 25 sizes × 8 runs';
  }
  const status={connecting:'Connecting to the board',preparing:'Preparing independent reference digests',sweeping:'Sweep in progress',restoring:'Verifying the restored compact core',complete:'Sweep complete',cancelled:'Sweep stopped safely',failed:'Sweep did not complete'};
  $('replay-status').textContent=status[job.stage]||job.stage;
  $('replay-detail').textContent=job.state==='failed'||job.state==='cancelled'?job.error:
    job.state==='passed'?'400 / 400 hashes complete · 350 measured + 50 warmups · compact core restored':
    job.stage==='sweeping'?(job.completed_hashes||0)+' / 400 hardware hashes complete · '+(job.current_core==='oxide'?'Oxide Quartz':'Compact core'):
    'The pattern is generated on the board. No large input file is transferred.';
  if(job.state==='passed'){
    const row=job.sweep_summary.find(r=>r.bytes===1073741824);
    $('replay-quartz-time').textContent=row.oxide_median_seconds.toFixed(3)+' s';
    $('replay-compact-time').textContent=row.compact_median_seconds.toFixed(3)+' s';
    $('replay-quartz-rate').textContent=row.oxide_MB_per_second.toFixed(1)+' MB/s';
    $('replay-compact-rate').textContent=row.compact_MB_per_second.toFixed(1)+' MB/s';
    $('replay-speedup').textContent=row.speedup.toFixed(1)+'×';
    history.replaceState(null,'','?replay='+job.id+'#'+currentPage);
    replayChart($('replay-throughput-chart'),job.sweep_summary);
    replayChart($('replay-speedup-chart'),job.sweep_summary,true);
  }
}
$('replay-check').onclick=async()=>{
  setBusy(true);$('replay-status').textContent='Checking the physical board';
  try {const job=await api('jobs',{kind:'probe',transport:$('transport').value});await follow(job.id);const result=await api('jobs/'+job.id);if(result.state!=='passed')throw Error(result.error);$('replay-status').textContent='Board verified · ready to sweep';}
  catch(error){setBusy(false);$('replay-status').textContent='Board check failed';$('replay-detail').textContent=error.message;toast(error.message);}
};
$('replay-start').onclick=async()=>{
  if(busy)return;
  if($('transport').value==='usb-uart'){toast('Select wired SSH or Wi-Fi SSH for the live sweep.');return;}
  $('replay-cancel').disabled=false;$('replay-cancel').textContent='Stop after batch';
  setBusy(true);replayView(false);
  try {const job=await api('jobs',{kind:'replay',transport:$('transport').value});await follow(job.id);}
  catch(error){setBusy(false);toast(error.message);document.dispatchEvent(new CustomEvent('demojobupdated',{detail:{kind:'replay',state:'failed',error:error.message}}));}
};
$('replay-cancel').onclick=async()=>{
  $('replay-cancel').disabled=true;$('replay-cancel').textContent='Finishing this batch…';
  try{await api('cancel',{});}catch(error){toast(error.message);}
};
$('replay-show-results').onclick=()=>replayView(true);
$('replay-back').onclick=()=>replayView(false);
$('replay-export').onclick=async()=>{
  if(!lastReplay||lastReplay.state==='running')return;
  try{const evidence=await api('replay-evidence/'+lastReplay.id),a=node('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(evidence,null,2)+'\n'],{type:'application/json'}));a.download='zybo-replay-'+lastReplay.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}catch(error){toast(error.message);}
};
