import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { initPrediction } from './prediction.js';
import { initBatteryLake } from './batterylake.js';
import { initML } from './ml.js';
import { drawLivePrediction } from './live_chart.js';

const $ = id => document.getElementById(id);
const palette = ['#2563eb','#06b6d4','#22c55e','#facc15','#ef4444'].map(x=>new THREE.Color(x));
function thermalColor(t) {
  const x = Math.max(0, Math.min(1, (t-20)/25))*4;
  const i = Math.min(3, Math.floor(x));
  return palette[i].clone().lerp(palette[i+1], x-i);
}
const stages = {ready:'Sẵn sàng',charge:'Sạc',rest_after_charge:'Nghỉ sau sạc',discharge:'Xả',rest_after_discharge:'Nghỉ sau xả'};
const statuses = {ready:'Sẵn sàng',running:'Đang chạy',complete:'Hoàn tất',fault:'Dừng lỗi',stopped:'Dừng bảo vệ'};
let selected=0, state=null, history=Array.from({length:12},()=>[]), lastTime=Array(12).fill(-1);
const meshes=[], outlines=[];
for(let i=0;i<12;i++) $('cell-select').add(new Option(`CH ${String(i+1).padStart(2,'0')}`,i));
for(let i=0;i<12;i++) $('fault-cell').add(new Option(`CH ${String(i+1).padStart(2,'0')}`,i+1));
function selectCell(i){selected=i;$('cell-select').value=i;if(state)updateUI(state);window.dispatchEvent(new CustomEvent('cycler-cell',{detail:i}));}
$('cell-select').addEventListener('change',e=>selectCell(Number(e.target.value)));
const definitions=[['temperature_c','Nhiệt độ · °C','#facc15'],['voltage_v','Điện áp · V','#5dd5bf'],['current_a','Dòng điện · A','#6ba8ff'],['soc','SOC · %','#c799ff']];
for(const [key,label] of definitions){
 const box=document.createElement('div');box.className='chart';
 const text=document.createElement('div');text.className='chart-label';text.innerHTML=`<span>${label}</span><span id="range-${key}"></span>`;
 const canvas=document.createElement('canvas');canvas.id=`chart-${key}`;
 box.append(text,canvas);$('charts').append(box);
}

try {
 const host=$('scene'),scene=new THREE.Scene();scene.background=new THREE.Color('#0c1623');
 const camera=new THREE.PerspectiveCamera(40,1,.1,100);camera.position.set(8,6,12);
 const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.append(renderer.domElement);
 const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,2.4,0);controls.enableDamping=true;controls.minDistance=5;controls.maxDistance=22;
 scene.add(new THREE.HemisphereLight(0xe1f4ff,0x24384c,2.4));
 const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(5,8,6);scene.add(light);
 function box(w,h,d,x,y,z,color){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color,roughness:.55,metalness:.4}));m.position.set(x,y,z);scene.add(m);return m;}
 // Open rack leaves every channel visible and selectable.
 for(const x of [-3.25,3.25])for(const z of [-1.1,1.1])box(.15,5.9,.15,x,2.9,z,'#61788f');
 for(const y of [0,1.85,3.7,5.6])box(6.7,.13,2.5,0,y,0,'#334b61');
 box(6.6,5.6,.12,0,2.8,-1.15,'#1a2b3d');
 for(let i=0;i<12;i++){
   const x=(i%4-1.5)*1.55,y=4.55-Math.floor(i/4)*1.85;
   const cell=new THREE.Mesh(new THREE.CylinderGeometry(.42,.42,1.3,40),new THREE.MeshStandardMaterial({color:thermalColor(25),roughness:.4,metalness:.22}));
   cell.position.set(x,y,.1);cell.userData.id=i;scene.add(cell);meshes.push(cell);
   box(.32,.1,.32,x,y+.7,.1,'#b5c5d3');
   const edges=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1.65,1)),new THREE.LineBasicMaterial({color:'#e7fffa'}));
   edges.position.copy(cell.position);scene.add(edges);outlines.push(edges);
   const labelCanvas=document.createElement('canvas');labelCanvas.width=256;labelCanvas.height=64;
   const ctx=labelCanvas.getContext('2d');ctx.fillStyle='#c4dae9';ctx.font='bold 28px sans-serif';ctx.textAlign='center';ctx.fillText(`CH ${String(i+1).padStart(2,'0')}`,128,42);
   const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(labelCanvas)}));sprite.position.set(x,y-.68,1.35);sprite.scale.set(1.15,.29,1);scene.add(sprite);
 }
 const grid=new THREE.GridHelper(20,20,0x345168,0x192d40);grid.position.y=-.1;scene.add(grid);
 const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();let down;
 renderer.domElement.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY]});
 renderer.domElement.addEventListener('pointerup',e=>{
   if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;
   const r=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);
   ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(meshes)[0];if(hit)selectCell(hit.object.userData.id);
 });
 new ResizeObserver(()=>{const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}).observe(host);
 renderer.setAnimationLoop(()=>{controls.update();outlines.forEach((o,i)=>o.visible=i===selected);renderer.render(scene,camera);});
 window.cycler3D={renderer,scene,meshes};
} catch(error){$('scene').textContent='Không khởi tạo được WebGL 3D. Bảng dữ liệu vẫn hoạt động. '+error.message;}

function drawCharts(){
 const rows=history[selected];
 for(const [key,,color] of definitions){
   const canvas=$(`chart-${key}`),w=canvas.clientWidth,h=62,dpr=Math.min(devicePixelRatio,2);canvas.width=w*dpr;canvas.height=h*dpr;
   const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
   const values=rows.map(r=>r[key]*(key==='soc'?100:1));if(!values.length)continue;
   let lo=Math.min(...values),hi=Math.max(...values);$(`range-${key}`).textContent=`${lo.toFixed(2)} – ${hi.toFixed(2)}`;
   if(hi-lo<.01){lo-=.5;hi+=.5;}
   ctx.strokeStyle='#283c50';ctx.beginPath();ctx.moveTo(0,h-5);ctx.lineTo(w,h-5);ctx.stroke();
   ctx.strokeStyle=color;ctx.lineWidth=1.8;ctx.beginPath();
   const start=rows[0].time_s,span=Math.max(1,rows.at(-1).time_s-start);
   values.forEach((v,i)=>{const x=(rows[i].time_s-start)/span*(w-4)+2,y=h-5-(v-lo)/(hi-lo)*(h-10);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
 }
}
function updateUI(s){
 state=s;const cell=s.cells[selected];
 $('start').disabled=s.safety_stop;
 $('inject-fault').disabled=s.safety_stop;
 $('safety-alarm').hidden=!s.safety_stop;
 $('safety-alarm').textContent=s.safety_stop?'STOP — '+s.alarms.map(a=>`CH ${a.cell}: ${a.reason} tại ${a.time_s.toFixed(0)} s`).join(' · ')+' · Reset để bỏ khóa.':'';
 $('fault-pending').textContent=s.pending_fault?`Đã lên lịch lỗi ${s.pending_fault.kind} cho CH ${s.pending_fault.cell}. Bắt đầu để áp dụng.`:'';
 $('run-status').textContent=s.safety_stop?'STOP · Dừng bảo vệ':s.running?'Đang mô phỏng':s.cells.every(c=>['complete','fault'].includes(c.status))?'Đã kết thúc':'Tạm dừng / Sẵn sàng';
 $('run-status').classList.toggle('error',s.safety_stop);
 $('speed').value=String(s.speed);$('cell-title').textContent=`CH ${String(cell.id).padStart(2,'0')}`;
 $('stage').textContent=`${stages[cell.stage]||cell.stage} · ${cell.mode} · Chu kỳ ${cell.cycle}/3`;
 $('temperature').textContent=`${cell.temperature_c.toFixed(2)} °C`;$('temperature').style.color='#'+thermalColor(cell.temperature_c).getHexString();
 $('voltage').textContent=`${cell.voltage_v.toFixed(3)} V`;$('current').textContent=`${cell.current_a.toFixed(3)} A`;
 $('soc').textContent=`${(cell.soc*100).toFixed(1)} %`;$('soc-fill').style.width=`${cell.soc*100}%`;
 $('time').textContent=`Thời gian mô phỏng: ${cell.time_s.toFixed(0)} s · ${statuses[cell.status]}`;$('fault').textContent=cell.error;
 $('health-soh').textContent=`${cell.soh_percent.toFixed(3)} %`;
 $('health-capacity').textContent=`${cell.capacity_ah.toFixed(3)} Ah`;
 $('health-resistance').textContent=`${cell.resistance_mohm.toFixed(2)} mΩ`;
 $('health-efc').textContent=cell.efc.toFixed(3);
 const live=cell.live_ml;
 drawLivePrediction(cell);
 const liveLabels={waiting:'Chờ xả',collecting:'Đang gom dữ liệu xả',ready:'Đã cập nhật',insufficient:'Thiếu dữ liệu',error:'Lỗi mô hình',safety_stop:'STOP · Dự báo ngừng cập nhật'};
 $('live-ml-state').textContent=`${liveLabels[live.status]||live.status} · ${live.sample_count} mẫu / 600 s${live.feature_cycle===null?'':` · chu kỳ ${live.feature_cycle} · cập nhật tại ${live.updated_time_s.toFixed(0)} s`}${['error','insufficient'].includes(live.status)?' · '+live.reason:''}`;
 $('channels').replaceChildren();
 for(const [i,c] of s.cells.entries()){
   if(c.time_s!==lastTime[i]){history[i].push({...c});if(history[i].length>240)history[i].shift();lastTime[i]=c.time_s;}
   if(meshes[i])meshes[i].material.color.copy(thermalColor(c.temperature_c));
   const tr=document.createElement('tr');tr.classList.toggle('selected',i===selected);tr.tabIndex=0;
   const texts=[`CH ${String(c.id).padStart(2,'0')}`,statuses[c.status],`${c.cycle}/3`,c.mode,`${c.voltage_v.toFixed(3)} V`,`${c.current_a.toFixed(3)} A`,`${(c.soc*100).toFixed(1)} %`,`${c.temperature_c.toFixed(2)} °C`,`${c.soh_percent.toFixed(3)} %`,c.efc.toFixed(3),c.live_ml.remaining_cycles===null?'Chờ xả':`≈ ${Math.round(c.live_ml.remaining_cycles)}`,c.live_ml.feature_cycle??'—'];
   texts.forEach((text,j)=>{const td=document.createElement('td');td.textContent=text;if(j===7){const dot=document.createElement('span');dot.className='dot';dot.style.background='#'+thermalColor(c.temperature_c).getHexString();td.prepend(dot);}tr.append(td);});
   tr.addEventListener('click',()=>selectCell(i));tr.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectCell(i);}});$('channels').append(tr);
 }
 drawCharts();
}
async function request(path,options){
 const response=await fetch(path,{...options,signal:AbortSignal.timeout(4000)});
 const data=await response.json();if(!response.ok)throw Error(data.error||response.statusText);return data;
}
function connection(ok,error=''){$('connection').textContent=ok?'● Dữ liệu trực tuyến · 4 Hz':`Mất kết nối: ${error}`;$('connection').classList.toggle('error',!ok);}
let busy=false;
async function control(action,speed,extra={}){
 if(busy)return;busy=true;
 try{
   const data=await request('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,speed,...extra})});
   if(action==='reset'){history=Array.from({length:12},()=>[]);lastTime.fill(-1);window.dispatchEvent(new CustomEvent('cycler-cell',{detail:selected}));}
   updateUI(data);connection(true);
 }catch(e){connection(false,e.message);}finally{busy=false;}
}
for(const id of ['start','pause','reset'])$(id).addEventListener('click',()=>control(id));
$('speed').addEventListener('change',e=>control('speed',Number(e.target.value)));
$('inject-fault').addEventListener('click',()=>control('fault',undefined,{cell:Number($('fault-cell').value),kind:$('fault-kind').value}));
async function poll(){try{if(!busy){updateUI(await request('/api/state'));connection(true);}}catch(e){connection(false,e.message);}finally{setTimeout(poll,250);}}
poll();
initPrediction();
initBatteryLake();
initML();
new ResizeObserver(()=>{if(state)drawLivePrediction(state.cells[selected]);}).observe($('live-soh-chart').parentElement);
