const $=id=>document.getElementById(id),labels={cell:'Cell',cathode:'Cathode',anode:'Anode',assembly:'Assembly',formation:'Formation'};
const roles={modeled:'Mô hình dùng',recorded:'Ghi nhận · chưa mô phỏng',target:'Target đánh giá',validation:'Kiểm tra nhất quán'};
let schema=null,projectId=null,snapshot=null,design=null,selection=null,selectedSample=null,epoch=0,refreshing=false,curveRevision=0;
const reports=new Map(),drafts=new Map();
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
const fmt=v=>v===undefined||v===null?'—':typeof v==='number'?v.toLocaleString('vi-VN',{maximumFractionDigits:3}):String(v);
async function request(path,body){const r=await fetch(path,{...(body!==undefined?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(15000)});const d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d;}
function error(e){$('ws-error').textContent=e.message||String(e);}
function tab(which){$('design-panel').hidden=which!=='design';$('performance-panel').hidden=which==='design';}
function cards(){
 for(const p of schema.projects){const b=node('button',undefined,'project-card');b.dataset.project=p.id;const icon=node('span',undefined,'cell-icon'+(p.form_factor==='CYLINDRICAL'?' cylinder':''));b.append(icon,node('small',p.form_factor),node('b',p.code),node('small',p.chemistry==='sodium-ion'?'Sodium-ion · NFPP / HardCarbon':'Lithium-ion · LFP'));b.addEventListener('click',()=>selectProject(p.id).catch(error));$('project-cards').append(b);}
}
async function selectProject(id){
 const seq=++epoch;projectId=id;selection=null;design=null;selectedSample=null;$('ws-error').textContent='';$('ws-body').hidden=true;
 const state=await request('/api/workspace/dashboard?project='+encodeURIComponent(id));if(seq!==epoch)return;snapshot=state;
 $('ws-body').hidden=false;$('ws-project-name').textContent=state.project.name;
 for(const card of $('project-cards').children)card.classList.toggle('selected',card.dataset.project===id);
 history.replaceState(null,'','?project='+encodeURIComponent(id));renderDesigns();newDesign();renderPerformance();tab(state.designs.length?'performance':'design');
 $('ws-status').textContent='Dự án '+state.project.name+' · dữ liệu cục bộ / mô phỏng';
}
function renderDesigns(){const select=$('design-list');select.replaceChildren(new Option('Tạo hồ sơ mới',''));for(const d of snapshot.designs)select.add(new Option(d.name+' · rev '+d.revision,d.id));if(design)select.value=design.id;}
function fillSheet(bom){
 $('sheet-groups').replaceChildren();
 for(const [group,fields] of Object.entries(schema.fields)){
  const details=node('details');details.open=group==='cell';details.append(node('summary',labels[group]));const grid=node('div',undefined,'sheet-fields');
  for(const [key,spec] of Object.entries(fields)){
   const label=node('label',spec.label+(spec.unit?' ('+spec.unit+')':''));const input=document.createElement(group==='formation'?'textarea':'input');input.id='sheet-'+group+'-'+key;input.dataset.group=group;input.dataset.key=key;
   if(spec.type==='number'){input.type='number';input.min=spec.min;input.max=spec.max;input.step=spec.integer?'1':'any';}else{if(input.tagName==='INPUT')input.type='text';input.maxLength=250;}
   input.value=bom[group][key]??'';input.addEventListener('input',totals);label.append(input,node('small',roles[spec.role]));grid.append(label);
  }
  details.append(grid);if(['cathode','anode'].includes(group)){const total=node('p',undefined,'sheet-total');total.id='total-'+group;details.append(total);}$('sheet-groups').append(details);
 }
 totals();
}
function gather(){const bom={};for(const [group,fields] of Object.entries(schema.fields)){bom[group]={};for(const [key,spec] of Object.entries(fields)){const v=$('sheet-'+group+'-'+key).value;bom[group][key]=spec.type==='number'?(v.trim()===''?null:Number(v)):v;}}return bom;}
function totals(){for(const group of ['cathode','anode']){let total=0;for(const key of Object.keys(schema.fields[group]))if(key.endsWith('_pct'))total+=Number($('sheet-'+group+'-'+key).value)||0;$('total-'+group).textContent='Total · dry composition: '+total.toFixed(2)+'%';$('total-'+group).classList.toggle('bad',Math.abs(total-100)>.1);}}
function newDesign(){if(!schema||!projectId)return;design=null;$('design-list').value='';$('sheet-name').value='DOE-'+String((snapshot?.designs.length||0)+1).padStart(2,'0');$('sheet-revision').textContent='Template minh họa · cần xác nhận bằng spec thực';fillSheet(schema.templates[projectId]);$('sheet-validation').replaceChildren();}
function loadDesign(id){design=snapshot.designs.find(d=>d.id===id);if(!design){newDesign();return;}$('sheet-name').value=design.name;$('sheet-revision').textContent='Revision '+design.revision;fillSheet(design.bom);validation(design.validation);}
function validation(value){const box=$('sheet-validation');box.replaceChildren(node('p',value.simulation_supported?'Có thể chạy mô phỏng với các trường được hỗ trợ.':'Còn issue chặn mô phỏng; hồ sơ vẫn được lưu.'));for(const issue of value.issues)box.append(node('p',(issue.blocking?'⛔ ':'⚠ ')+issue.title));}
async function save(openDOE){
 if(!$('sheet-form').reportValidity())return;$('ws-error').textContent='';$('save-design').disabled=true;$('save-open-doe').disabled=true;
 const savedEpoch=epoch,savedProject=projectId;
 try{
  const saved=await request('/api/workspace/designs',{...(design?{id:design.id,revision:design.revision}:{}),project_id:projectId,name:$('sheet-name').value,bom:gather()});
  if(savedEpoch!==epoch)return;design=saved;snapshot=await request('/api/workspace/dashboard?project='+savedProject);if(savedEpoch!==epoch)return;renderPerformance();renderDesigns();$('design-list').value=saved.id;$('sheet-revision').textContent='Đã lưu revision '+saved.revision;validation(saved.validation);
  if(openDOE&&saved.validation.simulation_supported)location.href='doe.html?design='+encodeURIComponent(saved.id);
 }catch(e){error(e);}finally{$('save-design').disabled=false;$('save-open-doe').disabled=false;}
}
async function refresh(){
 if(!projectId||refreshing)return;refreshing=true;const seq=epoch;
 try{const path='/api/workspace/dashboard?project='+encodeURIComponent(projectId)+(selection?'&experiments='+[...selection].join(','):'');const data=await request(path);if(seq!==epoch)return;snapshot=data;renderPerformance();}
 catch(e){error(e);}finally{refreshing=false;}
}
function renderPerformance(){
 const c=snapshot.counts;$('ws-kpis').replaceChildren();
 for(const [label,value] of [['Tổng cell trong DOE chọn',c.total],['Cell đang chạy · mô phỏng',c.running],['Đang chờ',c.queued],['Đã hoàn tất',c.completed],['Đạt tất cả target',c.target_pass],['Chưa đạt target',c.target_miss],['Cell lỗi / STOP',c.faults],['Issue dự án chưa xử lý',c.open_issues]]){const div=node('div');div.append(node('small',label),node('strong',String(value)));$('ws-kpis').append(div);}
 renderExperiments();renderCells();renderIssues();
}
function renderExperiments(){
 $('experiment-list').replaceChildren();
 const selected=selection||new Set(snapshot.selected_experiments);
 for(const e of snapshot.experiments){
  const row=node('tr'),check=document.createElement('input');check.type='checkbox';check.checked=selected.has(e.id);check.setAttribute('aria-label','So sánh '+e.name);
  check.addEventListener('change',async()=>{const next=new Set(selection||snapshot.selected_experiments);check.checked?next.add(e.id):next.delete(e.id);if(next.size>4||next.size===0){check.checked=!check.checked;error('Chọn từ 1 đến 4 DOE');return;}selection=next;selectedSample=null;await refresh();});
  const td=node('td');td.append(check);row.append(td);
  for(const value of [e.name+' / rev '+e.revision,e.status,e.cycles,e.cells,e.passed,e.faults,fmt(e.mean_energy),fmt(e.mean_soh)])row.append(node('td',String(value)));
  const link=node('a','Cấu hình DOE');link.href='doe.html?design='+e.design_id;const action=node('td');action.append(link);const download=node('button','JSON');download.addEventListener('click',()=>request('/api/workspace/experiments/'+e.id).then(data=>saveFile('DOE-'+e.id+'.json',JSON.stringify(data,null,2),'application/json')).catch(error));action.append(download);row.append(action);$('experiment-list').append(row);
 }
 const horizons=snapshot.experiments.filter(e=>selected.has(e.id)).map(e=>e.cycles);$('compare-warning').textContent=new Set(horizons).size>1?'Các DOE có số chu kỳ thử khác nhau: không diễn giải SOH cuối như so sánh cùng điều kiện.':'';
}
function outcome(cell){return ['stopped','infeasible','interrupted'].includes(cell.status)?'fault':cell.assessment?.state||cell.status;}
function renderCells(){
 const filter=$('cell-filter').value,rows=snapshot.cells.filter(c=>filter==='all'||(filter==='running'?c.status==='running':outcome(c)===filter));$('workspace-cells').replaceChildren();
 if(!rows.some(c=>c.sample_id===selectedSample))selectedSample=rows.find(c=>c.metrics)?.sample_id||rows[0]?.sample_id||null;
 for(const cell of rows){
  const m=cell.metrics||{},state=outcome(cell),tr=node('tr',undefined,'status-'+state);tr.dataset.sample=cell.sample_id;tr.tabIndex=0;tr.classList.toggle('selected',cell.sample_id===selectedSample);
  const experiment=snapshot.experiments.find(e=>e.id===cell.experiment_id);
  const missing=Object.entries(cell.assessment?.checks||{}).filter(([,v])=>!v).map(([k])=>k).join(', ');
  for(const v of [`Cell ${cell.run_order} / ${experiment?.name||'DOE'}`,cell.status,state,m.capacity_033c_ah,m.capacity_1c_ah,m.nominal_voltage_v,m.cell_mass_g,m.specific_energy_wh_kg,m.soh_final_percent,m.peak_temperature_c,cell.reason||missing])tr.append(node('td',fmt(v)));
  const choose=()=>{selectedSample=cell.sample_id;renderCells();};tr.addEventListener('click',choose);tr.addEventListener('keydown',e=>{if(e.key==='Enter'){choose();}});$('workspace-cells').append(tr);
 }
 drawSelected().catch(error);
}
async function drawSelected(){
 const seq=epoch,drawVersion=++curveRevision,cell=snapshot.cells.find(c=>c.sample_id===selectedSample),canvas=$('workspace-curve'),w=canvas.clientWidth,dpr=Math.min(devicePixelRatio,2);canvas.width=w*dpr;canvas.height=230*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.fillStyle='#9eb3c9';ctx.font='12px system-ui';
 if(!cell){$('ws-selected-cell').textContent='Chọn một cell để xem performance.';return;}
 $('ws-selected-cell').textContent=`Cell ${cell.run_order} · ${cell.status} · ${outcome(cell)} · ${cell.reason||'Mô phỏng minh họa'}`;
 let info=reports.get(cell.experiment_id);if(!info){info=await request('/api/workspace/experiments/'+cell.experiment_id);if(info.status==='completed')reports.set(cell.experiment_id,info);}
 if(seq!==epoch||drawVersion!==curveRevision||cell.sample_id!==selectedSample)return;
 const row=info.report?.runs.find(r=>r.run_id===cell.run_id);
 if(!row?.metrics){ctx.fillText(cell.status==='infeasible'?'Thiết kế không hợp lệ · không tạo curve giả.':'Chưa có curve hoàn tất.',20,35);return;}
 const horizon=info.report.config.cycles,x=v=>42+v/horizon*(w-60),y=v=>190-v/100*170;
 ctx.strokeStyle='#2d4258';for(const v of [0,20,40,60,80,100]){ctx.fillText(v+'%',2,y(v)+4);ctx.beginPath();ctx.moveTo(42,y(v));ctx.lineTo(w-18,y(v));ctx.stroke();}
 for(let i=0;i<=4;i++)ctx.fillText(Math.round(horizon*i/4),x(horizon*i/4)-8,216);
 ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(42,y(80));ctx.lineTo(w-18,y(80));ctx.stroke();ctx.setLineDash([]);ctx.strokeStyle='#5dd5bf';ctx.lineWidth=2;ctx.beginPath();row.metrics.curve.forEach((p,i)=>i?ctx.lineTo(x(p.cycle),y(p.soh_percent)):ctx.moveTo(x(p.cycle),y(p.soh_percent)));ctx.stroke();
}
function renderIssues(){
 if(document.activeElement?.closest('#issue-list'))return;
 const filter=$('issue-filter').value,issues=snapshot.issues.filter(i=>filter==='all'||i.status===filter);$('issue-list').replaceChildren();
 if(!issues.length){$('issue-list').append(node('p','Không có issue ở bộ lọc này.'));return;}
 for(const issue of issues){
  const item=node('article',undefined,issue.status);item.dataset.issue=issue.id;item.append(node('b',issue.title),node('p',`${issue.severity} · ${issue.origin} · ${issue.status} · ${issue.experiment_name||issue.design_name||'Hồ sơ thiết kế'}${issue.cell_number?' · Cell '+issue.cell_number:''}`));
  if(issue.status==='open'){const actions=node('div',undefined,'issue-actions'),input=document.createElement('input');input.placeholder='Ghi rõ cách đã xử lý';input.maxLength=500;input.value=drafts.get(issue.id)||'';input.setAttribute('aria-label','Ghi chú xử lý '+issue.title);input.addEventListener('input',()=>drafts.set(issue.id,input.value));const button=node('button','Đánh dấu đã xử lý');button.addEventListener('click',async()=>{try{await request('/api/workspace/issues/'+issue.id+'/resolve',{resolution:input.value});drafts.delete(issue.id);button.blur();await refresh();}catch(e){error(e);}});actions.append(input,button);item.append(actions);}else item.append(node('p','Xử lý: '+issue.resolution));$('issue-list').append(item);
 }
}
function saveFile(name,text,type){const url=URL.createObjectURL(new Blob([text],{type})),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function exportCells(){
 if(!snapshot)return;const state=snapshot,lookup=new Map();
 for(const id of state.selected_experiments){const result=reports.get(id)||await request('/api/workspace/experiments/'+id);lookup.set(id,result);}
 const bomFields=Object.entries(schema.fields).flatMap(([g,fields])=>Object.keys(fields).map(k=>'bom.'+g+'.'+k));
 const headers=['project_id','form_factor','chemistry','experiment_id','worksheet_id','revision','sample_id','run_id','design_id','ml_split','status','target_state','reason','data_origin','bom_basis',...bomFields,'capacity_033c_ah','capacity_1c_ah','nominal_voltage_v','cell_mass_g','specific_energy_wh_kg','soh_final_percent','peak_temperature_c'];
 const quote=value=>{let s=String(value??'');if(typeof value==='string'&&/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
 const lines=state.cells.map(c=>{const exp=lookup.get(c.experiment_id),run=exp.report?.runs.find(r=>r.run_id===c.run_id),bom=run?.effective_bom||exp.sheet;const row={project_id:state.project.id,form_factor:state.project.form_factor,chemistry:state.project.chemistry,experiment_id:c.experiment_id,worksheet_id:exp.design_id,revision:exp.revision,sample_id:c.sample_id,run_id:c.run_id,design_id:c.design_id,ml_split:c.ml_split,status:c.status,target_state:outcome(c),reason:c.reason,data_origin:'synthetic_doe',bom_basis:run?'effective_trial':'reference_sheet_pending',...(c.metrics||{})};for(const field of bomFields){const [,g,k]=field.split('.');row[field]=bom[g][k];}return headers.map(k=>quote(row[k])).join(',');});
 saveFile(state.project.id+'-cells.csv','\uFEFF'+headers.join(',')+'\r\n'+lines.join('\r\n'),'text/csv;charset=utf-8');
}
$('sheet-form').addEventListener('submit',e=>{e.preventDefault();save(false);});$('save-open-doe').addEventListener('click',()=>save(true));$('new-design').addEventListener('click',()=>{newDesign();tab('design');});$('design-list').addEventListener('change',e=>loadDesign(e.target.value));$('tab-design').addEventListener('click',()=>tab('design'));$('tab-performance').addEventListener('click',()=>{tab('performance');drawSelected().catch(error);});$('cell-filter').addEventListener('change',renderCells);$('issue-filter').addEventListener('change',renderIssues);$('export-cells').addEventListener('click',()=>exportCells().catch(error));
new ResizeObserver(()=>{if(snapshot)drawSelected().catch(error);}).observe($('workspace-curve'));
try{schema=await request('/api/workspace/schema');cards();$('ws-status').textContent='Chọn PRISMATIC / CYLINDRICAL và dự án LFP01 / SIB để bắt đầu.';const requested=new URLSearchParams(location.search).get('project');if(requested&&schema.projects.some(p=>p.id===requested))await selectProject(requested);}catch(e){error(e);}
setInterval(()=>{if(projectId&&!document.hidden)refresh();},2000);
