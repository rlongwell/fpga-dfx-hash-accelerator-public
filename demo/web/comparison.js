'use strict';
// Diagrams illustrate the checked-in RTL. They are not internal signal captures.
// Primary plotted values come from the same sealed physical summary as Hash Lab.
const stage = document.getElementById('stage');
let durations = [], titles = [], sceneOrder = [];

const captions = [
  ['Compact SystemVerilog core compared with Oxide’s pinned Quartz SHA3-256 core.','Higher large-buffer throughput and fewer used cells in this Zybo integration.'],
  ['Both cores use the same board, 100 MHz clock, static shell, Linux driver, and DMA buffer.','The baseline keeps Oxide’s double buffering and a full-rate byte adapter.'],
  ['A shared 64-bit stream feeds the Quartz integration through a local byte adapter.','Double buffering hides permutation backpressure and sustains one byte per clock.'],
  ['An eight-byte input buffer feeds an aligned XOR into the existing sponge state.','Capture and absorption use separate cycles. The permutation still takes 24 rounds.'],
  ['Within the compact core, static padding decode replaces a mux across all 25 state lanes.','Registered framing checks keep AXI validation off the state enable path.'],
  ['Direct absorption avoids two full block registers. The digest reads the held state.','LUT and flip-flop totals include each hash partition’s local interface logic.'],
  ['','The local API includes memory copying, so its speedup is smaller than the DMA speedup.'],
  ['','Fewer used cells leave the reserved DFX region and partial-image size unchanged.'],
  ['Oxide Computer Company and Quartz contributors supplied the unchanged reference.','This is a workload-specific comparison on Zybo, without Oxide endorsement.']
];
let total = 0;
let evidence, token='', elapsed=0, running=false, previousTime=0, toastTimer;
function toast(message){const el=document.getElementById('toast');el.textContent=message;el.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),4500);}
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const text=(x,y,s,size=28,cls='',anchor='start')=>`<text x="${x}" y="${y}" font-size="${size}" class="${cls}" text-anchor="${anchor}">${esc(s)}</text>`;
const box=(x,y,w,h,cls='panel',r=12)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" class="${cls}"/>`;
const line=(x,y,x2,y2,cls='line',width=3)=>`<line x1="${x}" y1="${y}" x2="${x2}" y2="${y2}" class="${cls}" stroke-width="${width}"/>`;
function arrow(x,y,x2,y2){return line(x,y,x2,y2)+`<path d="M ${x2-12} ${y2-9} L ${x2} ${y2} L ${x2-12} ${y2+9}" fill="none" class="line" stroke-width="3"/>`;}
function chapter(){let start=0;for(let i=0;i<durations.length;i++){const end=start+durations[i];if(elapsed<end||i===durations.length-1)return {i,time:elapsed-start};start=end;}}
function startOf(i){return durations.slice(0,i).reduce((a,b)=>a+b,0);}
function flowNode(x,y,w,heading,sub,cls=''){return box(x,y,w,125)+text(x+w/2,y+52,heading,31,cls,'middle')+text(x+w/2,y+90,sub,22,'muted','middle');}
function bars(x,y,w,rows,max,progress){return rows.map((r,i)=>{const yy=y+i*100;return text(x,yy,r.label,27,r.cls)+box(x,yy+20,w,24,'rate',3)+box(x,yy+20,Math.max(1,w*r.value/max*progress),24,r.cls==='ours'?'active':'oxactive',3)+text(x+w,yy,r.display,29,r.cls,'end');}).join('');}
// Narration-led reveals. Each fact enters once and stays in place. Packets move
// only during the narrated transfer; there are no cycling lane/counter displays.
function reveal(t, at, content) {
 const p=running?Math.max(0,Math.min(1,(t-at)/.5)):1;
 const e=1-Math.pow(1-p,3);
 return `<g opacity="${e}" transform="translate(0 ${10*(1-e)})">${content}</g>`;
}
function transfer(x,y,x2,y2,t,at,cls='active') {
 if(!running)return '';
 let out='';
 for(let i=0;i<3;i++){
  const p=(t-at-i*.38)/2.2;
  if(p>=0&&p<=1)out+=box(x+(x2-x)*p-5,y+(y2-y)*p-5,10,10,cls,3);
 }
 return out;
}
function architectureNode(x,y,w,heading,sub,cls='',changed=false){
 return box(x,y,w,125,changed?'changed':'panel')+text(x+w/2,y+51,heading,27,cls,'middle')+text(x+w/2,y+90,sub,22,'muted','middle');
}
function architectureRow(y,compact){
 const data=compact?[['Beat buffer','64 bits'],['Aligned XOR','Direct absorption'],['Keccak state','1,600 bits · 24 rounds'],['Digest view','Reads the held state']]:[['Elastic adapter','1 byte / clock'],['Block A + Block B','136 bytes each'],['Keccak state','1,600 bits · 24 rounds'],['Digest register','256 bits']];
 return architectureNode(100,y,210,'AXI Stream','64-bit words')+[[350,270],[660,330],[1030,330],[1400,410]].map(([x,w],i)=>arrow(x-40,y+62,x,y+62)+architectureNode(x,y,w,...data[i])).join('');
}
function quartzArchitecture(t) {
 const r=(at,x)=>reveal(t,at,x);
 return r(.15,architectureNode(100,400,210,'AXI Stream','64-bit words'))+
  r(3.4,text(100,275,'Oxide Quartz integration',34,'oxide'))+
  r(5,arrow(310,462,350,462)+architectureNode(350,400,270,'Byte adapter','1 byte / clock','oxide'))+
  r(7.3,arrow(620,462,660,462)+architectureNode(660,400,330,'Block A + Block B','136 bytes each','oxide'))+
  r(10.4,arrow(990,462,1030,462)+architectureNode(1030,400,330,'Keccak state','1,600 bits · 24 rounds'))+
  r(15.1,arrow(1360,462,1400,462)+architectureNode(1400,400,410,'Digest register','256 bits'))+
  transfer(315,462,345,462,t,5.5,'oxactive')+transfer(625,462,655,462,t,7.7,'oxactive')+
  transfer(995,462,1025,462,t,10.9,'oxactive')+transfer(1365,462,1395,462,t,15.6,'oxactive')+
  r(9.3,text(100,680,'One block fills while the other feeds the state.',34));
}
function paddingGrid(x,y,compact,t) {
 let out='';
 for(let i=0;i<25;i++){
  const xx=x+(i%5)*52,yy=y+Math.floor(i/5)*52;
  const active=compact&&(i===5||i===16)&&t>13;
  out+=box(xx,yy,44,44,active?'changed':(compact&&i<17?'rate-cell':'gridcell'),5)+text(xx+22,yy+29,i,20,compact&&i>=17?'muted':'','middle');
 }
 return out;
}
function paddingRefinement(t) {
 const r=(at,s)=>reveal(t,at,s);
 return r(.3,text(100,270,'Earlier wide core → compact core',30,'muted'))+
  r(4.5,box(100,330,820,500)+text(135,380,'BEFORE · dynamic selection',29)+
    paddingGrid(140,430,false,t)+text(140,735,'All 25 lanes in the selection network',25,'muted'))+
  r(8,arrow(410,555,470,555)+architectureNode(470,480,405,'Select · XOR · write','Variable lane index'))+
  r(9.5,text(135,795,'Choose the destination through a wide selector.',25,'muted'))+
  r(11.5,box(1000,330,820,500)+text(1035,380,'AFTER · local lane enables',29,'warm'))+
  r(13,text(1035,430,'Example: message ends in lane 5',24,'muted')+architectureNode(1030,480,390,'Decode padding lane','Only the 17 rate lanes','warm',true)+arrow(1420,555,1490,555)+paddingGrid(1510,430,true,t))+
  transfer(1425,555,1485,555,t,14.4)+
  r(15.5,text(1035,705,'0x06 at the message end · 0x80 at the rate end',25,'warm'))+
  r(19,text(1035,765,'8 capacity lanes remain in the state.',26,'muted')+text(1035,805,'Padding does not modify them.',26,'muted'))+
  r(20,text(100,905,'Same 1,600-bit hash state. A smaller padding-selection network.',31));
}
function miniNode(x,y,w,title,sub,changed=false) {
 return box(x,y,w,100,changed?'changed':'panel')+text(x+w/2,y+40,title,25,changed?'warm':'','middle')+text(x+w/2,y+74,sub,20,'muted','middle');
}
function framingRefinement(t) {
 const r=(at,s)=>reveal(t,at,s);
 return r(.3,text(100,265,'Earlier wide core → compact core',30,'muted'))+
  r(1.3,text(100,325,'BEFORE',25,'muted')+miniNode(100,355,350,'Input metadata','Byte mask · last · length'))+
  r(2.8,arrow(450,405,520,405)+miniNode(520,355,400,'Framing checks','Count + compare'))+
  r(5.1,arrow(920,405,1000,405)+miniNode(1000,355,440,'State-update control','Validation in the control path')+arrow(1440,405,1510,405)+miniNode(1510,355,310,'Hash state','25 lanes'))+
  r(7.2,text(100,535,'AFTER',25,'warm')+text(470,535,'Capture cycle',28)+text(1330,535,'Following cycle',28))+
  r(8,miniNode(100,625,300,'Stream input','Data + metadata')+miniNode(470,575,350,'Capture word','Existing beat buffer'))+
  r(8.6,line(400,675,435,675)+line(435,625,435,790)+arrow(435,625,470,625)+arrow(435,790,470,790)+miniNode(470,740,350,'Check framing','Byte mask + message end'))+
  r(9.3,arrow(820,790,880,790)+miniNode(880,740,350,'Fault register',t>=11.5?'Bad word: fault = 1':'Store the check result',true))+
  r(11.2,arrow(820,625,1330,625)+miniNode(1330,575,490,'Absorb buffered word',t>=12.5?'Invalid word: state stays unchanged':'Aligned XOR into the state')+arrow(1230,790,1330,790)+miniNode(1330,740,490,t>=12.5?'Invalid → reject':'Allow or reject','A bad word never reaches the state',true)+line(1575,740,1575,675))+
  transfer(825,625,1110,625,t,11.4)+transfer(1235,790,1325,790,t,11.4)+
  r(12.5,line(1135,607,1171,643,'reject-line',5)+line(1135,643,1171,607,'reject-line',5)+text(1153,590,'STOP',22,'warm','middle'))+
  r(17,text(100,910,'Less control logic · same algorithm · same simulated cycle count',31));
}

function scene(i,t){
 const q=evidence.oxide_elastic,c=evidence.compact;
 const r=(at,s)=>reveal(t,at,s);
 if(i===0)return r(.6,text(100,285,'One hash function. Two input architectures.',44))+
  r(2.9,flowNode(100,420,680,'Compact SHA3-256','64-bit stream → direct state absorption','ours'))+
  r(5.4,flowNode(1120,420,680,'Oxide Quartz SHA3-256','Byte-stream input → two block buffers','oxide'))+
  r(8.1,text(100,690,'Architecture',38)+arrow(430,680,600,680)+text(680,690,'Resources',38)+arrow(980,680,1150,680)+text(1230,690,'Board measurements',38))+
  r(9.6,text(100,840,'Same Zybo Z7-20 · 100 MHz · matching digests',30,'muted'));
 if(i===2)return quartzArchitecture(t);
 if(i===3)return r(.5,text(100,270,'Oxide Quartz',30,'oxide')+`<g opacity=".65">`+architectureRow(315,false)+'</g>')+
  r(1.1,text(100,565,'Compact SHA3-256',33,'ours')+text(1810,565,'Outlined blocks change',25,'warm','end'))+
  r(1.5,architectureNode(100,610,210,'AXI Stream','Same 64-bit words'))+
  r(3.3,arrow(310,672,350,672)+architectureNode(350,610,270,'Beat buffer','64 bits','warm',true))+
  r(6.2,arrow(620,672,660,672)+architectureNode(660,610,330,'Aligned XOR','Direct absorption','warm',true))+
  r(8.0,arrow(990,672,1030,672)+architectureNode(1030,610,330,'Keccak state','1,600 bits · 24 rounds'))+
  r(12.3,arrow(1360,672,1400,672)+architectureNode(1400,610,410,'Digest view','Reads the held state','warm',true))+
  transfer(315,672,345,672,t,3.6)+transfer(625,672,655,672,t,6.5)+transfer(995,672,1025,672,t,8.3)+
  r(9.9,text(660,785,'Two full block buffers removed',26,'warm'))+
  r(15.8,text(1400,785,'No separate digest register',26,'warm'))+
  r(17.2,text(100,860,'Capture + absorption: separate cycles',28,'muted'))+
  r(19.6,text(1050,860,'Same 24-round permutation',28,'muted'));
 if(i===4)return paddingRefinement(t);
 if(i===9)return framingRefinement(t);
 if(i===5)return r(.6,text(100,265,'Routed SHA3-256 partitions on the same device',31,'muted'))+
  r(4.1,text(100,345,'LUTs',39)+bars(100,410,760,[{label:'Oxide Quartz + adapter',value:q.rp_luts,display:q.rp_luts.toLocaleString(),cls:'oxide'},{label:'Compact SHA3-256',value:c.rp_luts,display:c.rp_luts.toLocaleString(),cls:'ours'}],q.rp_luts,1)+text(100,710,'22.6% fewer LUTs',45,'ours'))+
  r(7.2,text(1050,345,'Flip-flops',39)+bars(1050,410,760,[{label:'Oxide Quartz + adapter',value:q.rp_ffs,display:q.rp_ffs.toLocaleString(),cls:'oxide'},{label:'Compact SHA3-256',value:c.rp_ffs,display:c.rp_ffs.toLocaleString(),cls:'ours'}],q.rp_ffs,1)+text(1050,710,'58.0% fewer flip-flops',45,'ours'))+
  r(9.4,text(100,800,'Includes each partition’s local interface logic.',29,'muted'))+
  r(15.3,text(100,860,'Both: 0 BRAM · 0 DSP',32));
 if(i===1)return r(.6,text(100,280,'Same board · same shell · same driver · 100 MHz',35))+
  r(4.9,text(100,390,'Median of 7 samples after warmup',38,'ours'))+
  r(8.7,text(100,480,'Every digest checked against software',33))+
  r(11.4,line(100,580,1800,580)+text(100,660,'Outside both timers',35,'muted')+text(100,735,'USB upload and FPGA reconfiguration',38)+text(100,820,'DMA timer: prefilled memory → driver → DMA → digest',28,'muted'));
 if(i===6){const ms=(v,key)=>16777216/(v[key]*1000);return r(.5,text(100,265,'PHYSICAL SHA3-256 DATA · 16.78 MB · median of 7',31,'muted'))+
  r(6.2,text(100,345,'DMA request',39)+bars(100,415,760,[{label:'Oxide Quartz',value:ms(q,'dma_MB_s'),display:ms(q,'dma_MB_s').toFixed(2)+' ms',cls:'oxide'}],ms(q,'dma_MB_s'),1))+
  r(9.9,bars(100,515,760,[{label:'Compact SHA3-256',value:ms(c,'dma_MB_s'),display:ms(c,'dma_MB_s').toFixed(2)+' ms',cls:'ours'}],ms(q,'dma_MB_s'),1))+
  r(12.2,text(100,720,'2.36× DMA throughput',40,'ours')+text(100,785,'99.14 → 233.66 MB/s',31,'muted'))+
  r(15.5,text(1050,345,'Local PS API request',39)+bars(1050,415,760,[{label:'Oxide Quartz',value:ms(q,'local_api_MB_s'),display:ms(q,'local_api_MB_s').toFixed(2)+' ms',cls:'oxide'},{label:'Compact SHA3-256',value:ms(c,'local_api_MB_s'),display:ms(c,'local_api_MB_s').toFixed(2)+' ms',cls:'ours'}],ms(q,'local_api_MB_s'),1)+text(1050,720,'1.91× API throughput',40,'ours'))+
  r(19.9,text(1050,785,'Includes memory copies and request overhead',26,'muted'));
 }
 if(i===7){
  if(t>=21.2)return r(21.2,text(100,310,'The scope of the result',39))+
   r(21.4,text(100,445,'Reserved region and partial-image size are unchanged.',33,'muted'))+
   r(24.5,text(100,610,'Power and Oxide production-system performance',33,'muted')+text(100,665,'were not measured.',33,'muted'));
  return r(.6,text(100,275,'64-byte SHA3-256 request',34,'muted'))+
   r(2.1,flowNode(100,330,750,'Software + DMA setup','Per-request costs dominate tiny requests'))+
   r(5.3,arrow(850,392,1020,392)+flowNode(1050,330,750,'Wider hash input','Very little data to accelerate','ours'))+
   r(8.9,text(100,555,'Oxide Quartz: 168.4 µs',40,'oxide')+text(1050,555,'Compact: 187.3 µs',40,'ours')+text(100,600,'64-byte DMA median · 7 samples after warmup',27,'muted'))+
   r(10.8,text(100,665,'Range: 158.7–213.2 µs',30,'oxide')+text(1050,665,'Range: 183.7–219.4 µs',30,'ours')+text(100,720,'The sample ranges overlap.',29,'muted'))+
   r(12.8,text(100,800,'Request overhead + run-to-run variation can outweigh the streaming gain.',31))+
   r(17.1,text(100,870,'Higher bulk throughput ≠ lower tiny-request latency',35,'ours'));
 }
 return r(.5,text(100,290,'Oxide Computer Company / Quartz contributors',42,'oxide'))+
  r(3,text(100,385,'SHA3 contribution: nathanaelhuffman · Quartz PR #516',30))+
  r(4.4,text(100,475,'Unchanged MPL-2.0 reference · double buffering enabled',30)+text(100,535,'Pinned revision: c0ccf08525f30c43f4c773c2295dabe80f97cd0e',27,'muted'))+
  r(8.5,text(100,665,'Developed with AI assistance',36,'ours'))+
  r(10,text(100,750,'Source, attribution and reproduction: docs/review-guide.md',28,'muted'))+
  r(11.3,text(100,840,'Next: the same file through both physical cores',32))+
  r(10,text(100,895,'Music: Cyber Runner · 2050 / Artlist',23,'muted'));
}
function draw(){if(!evidence)return;const {i,time}=chapter();const caption=(captions[sceneOrder[i]]||['Registered framing checks before absorption.'])[0];const entrance=running?Math.min(1,time/0.7):1, opacity=1-Math.pow(1-entrance,3), shift=18*(1-opacity);stage.setAttribute('aria-label',titles[i]+'. '+caption);stage.innerHTML=box(0,0,1920,1080,'bg',0)+text(100,75,'SHA3-256 · COMPACT vs OXIDE QUARTZ · ZYBO Z7-20',23,'muted')+text(1815,75,String(i+1).padStart(2,'0')+' / '+String(durations.length).padStart(2,'0'),24,'muted','end')+text(100,165,titles[i],52)+line(100,205,1820,205)+`<g opacity="${opacity}" transform="translate(0 ${shift})">`+scene(sceneOrder[i],time)+'</g>'+line(100,930,1820,930)+text(960,984,caption,27,'','middle')+box(100,1057,1720,3,'rate',0)+box(100,1057,Math.max(1,1720*elapsed/total),3,'active',0);document.getElementById('position').textContent=(i+1)+' / '+durations.length+' · '+Math.floor(elapsed)+' / '+total+' s';}
function play(){if(elapsed>=total)elapsed=0;running=!running;previousTime=performance.now();document.getElementById('play').textContent=running?'Pause':'Play presentation';draw();}
document.getElementById('play').onclick=play;
function jump(delta){if(!durations.length)return;const {i}=chapter();elapsed=startOf(Math.max(0,Math.min(durations.length-1,i+delta)));draw();}
document.getElementById('previous').onclick=()=>jump(-1);document.getElementById('next').onclick=()=>jump(1);
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight')jump(1);if(e.key==='ArrowLeft')jump(-1);if(e.key===' '){e.preventDefault();play();}if(e.key==='Escape')document.dispatchEvent(new Event('recordingstoprequested'));});
document.addEventListener('recordingstarted',()=>{elapsed=0;running=false;play();});
document.addEventListener('recordingfinished',()=>{running=false;document.getElementById('play').textContent='Play presentation';});
function setTheme(value){document.documentElement.dataset.theme=value;document.getElementById('theme').textContent=value==='dark'?'Light theme':'Dark theme';}
document.getElementById('theme').onclick=async()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(value);try{await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Token':token},body:JSON.stringify({theme:value})});}catch{toast('Theme could not be saved.');}};
function frame(now){if(running){elapsed=Math.min(total,elapsed+(now-previousTime)/1000);draw();if(elapsed>=total){running=false;document.getElementById('play').textContent='Replay';document.dispatchEvent(new Event('recordingstoprequested'));}}previousTime=now;requestAnimationFrame(frame);}
fetch('/api/bootstrap').then(r=>{if(!r.ok)throw Error('Could not load benchmark evidence.');return r.json();}).then(async data=>{evidence=data.benchmark;token=data.token;const story=await fetch('/story-axi.json').then(r=>r.json());const parts=story.chapters.filter(c=>c.scene!==null);durations=parts.map(c=>c.duration);titles=parts.map(c=>c.title);sceneOrder=parts.map(c=>c.scene);total=durations.reduce((a,b)=>a+b,0);setTheme(data.settings.theme==='light'?'light':'dark');draw();requestAnimationFrame(frame);}).catch(error=>toast(error.message));
