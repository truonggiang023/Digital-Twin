const $=id=>document.getElementById(id);
let schema=null,report=null,selected=null,pending=false,revision=0,projectContext=null;
const colors={LFP:'#5dd5bf',NMC622:'#c799ff',NMC811:'#f6cd85',NFPP:'#6ba8ff'};
const format=v=>v===null||v===undefined?'—':typeof v==='number'?v.toLocaleString('vi-VN',{maximumFractionDigits:3}):String(v);
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function setExports(){for(const id of ['doe-csv','doe-json'])$(id).disabled=pending||!report?.effects;}
function invalidate(){revision++;report=null;selected=null;$('doe-results').hidden=true;$('doe-table-body').replaceChildren();$('doe-table-head').replaceChildren();$('doe-run-count').textContent='';$('doe-status').textContent='Cấu hình đã đổi · xem trước hoặc chạy lại.';setExports();}
function config(){
 const baseline={},vary={};
 for(const [key,spec] of Object.entries(schema.factors)){
  baseline[key]=spec.options?$('base-'+key).value:Number($('base-'+key).value);
  if($('vary-'+key).checked){
   const tokens=$('levels-'+key).value.split(',').map(x=>x.trim());
   if(tokens.some(x=>!x))throw Error('Mức thử không được rỗng: '+spec.label);
   vary[key]=tokens.map(v=>spec.options?v:Number(v));
  }
 }
 return {method:$('doe-method').value,baseline,vary,cycles:Number($('doe-cycles').value),replicates:Number($('doe-replicates').value),seed:Number($('doe-seed').value),samples:Number($('doe-samples').value),variation_percent:Number($('doe-variation').value)};
}
function factors(){
 for(const [key,spec] of Object.entries(schema.factors)){
  const row=el('tr'),check=document.createElement('input');check.type='checkbox';check.id='vary-'+key;check.checked=schema.default_vary.includes(key);check.disabled=spec.role==='objective'||(spec.options&&spec.options.length<2);check.setAttribute('aria-label','Thay đổi '+spec.label);
  const td=el('td');td.append(check);row.append(td);
  const name=el('td',spec.label);name.append(el('small',spec.unit+(spec.role==='objective'?' · Mục tiêu đánh giá':'')));row.append(name);
  const base=document.createElement(spec.options?'select':'input');base.id='base-'+key;base.setAttribute('aria-label','Giá trị '+spec.label);
  if(spec.options)for(const value of spec.options)base.add(new Option(value,value));
  else{base.type='number';base.min=spec.min;base.max=spec.max;base.step='any';base.required=true;}
  base.value=spec.baseline;const baseTd=el('td');baseTd.append(base);row.append(baseTd);
  const levels=document.createElement('input');levels.type='text';levels.id='levels-'+key;levels.value=spec.levels.join(', ');levels.disabled=!check.checked;levels.setAttribute('aria-label','Các mức '+spec.label);
  if(spec.options)levels.title='Chọn trong: '+spec.options.join(', ');
  const levelsTd=el('td');levelsTd.append(levels);row.append(levelsTd);$('doe-factors').append(row);
  check.addEventListener('change',()=>{levels.disabled=!check.checked;});
 }
}
function table(){
 const keys=Object.keys(report.config.baseline),metrics=report.effects?Object.keys(schema.metrics):[];
 const head=el('tr');
 for(const title of ['Run / Rep','Status','ML split',...keys.map(k=>schema.factors[k].label+' ('+schema.factors[k].unit+')'),...metrics.map(k=>schema.metrics[k]),'Đạt Energy Target?','Lý do'])head.append(el('th',title));
 $('doe-table-head').replaceChildren(head);$('doe-table-body').replaceChildren();
 for(const row of report.runs){
  const tr=el('tr',undefined,row.status||'');tr.dataset.runId=row.run_id;tr.tabIndex=0;
  const values=[`${row.run_order} / R${row.replicate}`,row.status||'planned',row.ml_split,...keys.map(k=>row.inputs[k]),...metrics.map(k=>row.metrics?.[k]),row.metrics?(row.metrics.energy_target_met?'Đạt':'Chưa đạt'):'—',row.reason||''];
  values.forEach((v,i)=>tr.append(el('td',format(v),i===values.length-1?'reason':'')));
  const choose=()=>{selected=row;drawSelected();for(const r of $('doe-table-body').children)r.classList.toggle('selected',r.dataset.runId===row.run_id);};
  tr.addEventListener('click',choose);tr.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});$('doe-table-body').append(tr);
 }
 $('doe-run-count').textContent=`${report.run_count} runs · ${report.unique_designs} thiết kế · ID ${report.experiment_id}`;
}
function canvas(id,height){const c=$(id),w=c.clientWidth,dpr=Math.min(devicePixelRatio,2);c.width=w*dpr;c.height=height*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.font='11px system-ui';return {ctx,w,h:height};}
function drawEffects(){
 const {ctx,w,h}=canvas('doe-effects',300),metric=$('doe-metric').value;
 const effects=report.effects[metric];$('doe-level-means').replaceChildren();
 if(!effects.length){ctx.fillStyle='#91a9c2';ctx.fillText('Chọn yếu tố thay đổi để phân tích ảnh hưởng.',12,30);return;}
 const max=Math.max(1e-12,...effects.map(f=>f.effect_range??0)),left=Math.min(170,w*.42),right=w-35,step=Math.min(48,260/effects.length);
 effects.forEach((f,i)=>{
  const y=22+i*step;ctx.fillStyle='#adbac7';ctx.fillText(schema.factors[f.factor].label.slice(0,23),0,y+12);
  if(f.effect_range!==null){ctx.fillStyle='#5dd5bf';ctx.fillRect(left,y,Math.max(1,(f.effect_range/max)*(right-left)),Math.max(5,step-15));ctx.fillStyle='#dce7f3';ctx.fillText(format(f.effect_range),left,y-3);}
  const line=el('div');line.append(el('b',schema.factors[f.factor].label+': '));line.append(document.createTextNode(f.levels.map(g=>`${g.level} → ${format(g.mean)} (n=${g.n})`).join(' · ')));$('doe-level-means').append(line);
 });
}
function drawScatter(){
 const {ctx,w,h}=canvas('doe-scatter',300),rows=report.runs.filter(r=>r.status==='completed');
 if(!rows.length){ctx.fillStyle='#91a9c2';ctx.fillText('Chưa có run hoàn tất.',20,35);return;}
 const target=report.config.baseline.energy_density_target_wh_kg;
 const minX=Math.min(target,...rows.map(r=>r.metrics.specific_energy_wh_kg))*.9,maxX=Math.max(target,...rows.map(r=>r.metrics.specific_energy_wh_kg))*1.1;
 const minY=Math.max(0,Math.min(...rows.map(r=>r.metrics.soh_final_percent))-5),maxY=100;
 const x=v=>45+(v-minX)/(maxX-minX)*(w-65),y=v=>260-(v-minY)/(maxY-minY)*230;
 ctx.strokeStyle='#365064';ctx.fillStyle='#91a9c2';
 for(let i=0;i<=4;i++){const xv=minX+(maxX-minX)*i/4,yv=minY+(maxY-minY)*i/4;ctx.fillText(xv.toFixed(0),x(xv)-9,278);ctx.fillText(yv.toFixed(0)+'%',0,y(yv)+4);ctx.beginPath();ctx.moveTo(45,y(yv));ctx.lineTo(w-20,y(yv));ctx.stroke();}
 ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(x(target),25);ctx.lineTo(x(target),260);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#ef7777';ctx.fillText('Target '+target,x(target)-30,15);
 for(const row of rows){ctx.fillStyle=colors[row.inputs.cathode];ctx.beginPath();ctx.arc(x(row.metrics.specific_energy_wh_kg),y(row.metrics.soh_final_percent),4,0,Math.PI*2);ctx.fill();}
 ctx.fillStyle='#91a9c2';ctx.fillText('Năng lượng riêng (Wh/kg)',Math.max(45,w-200),297);
}
function drawSelected(){
 if(!selected)return;const row=selected,m=row.metrics;const {ctx,w}=canvas('doe-curve',220);
 $('doe-selected').textContent=`Run ${row.run_order} · ${row.inputs.cathode} / ${row.inputs.anode} / ${row.inputs.electrolyte} · ${row.status} · ${row.reason||'Mô phỏng minh họa'}`;
 $('doe-design-details').replaceChildren();
 if(!m){ctx.fillStyle='#f6b879';ctx.fillText('Thiết kế không phù hợp · không tạo curve giả.',20,35);return;}
 const left=45,right=w-20,top=18,bottom=185,limit=report.config.cycles;
 const x=v=>left+v/limit*(right-left),y=v=>bottom-v/100*(bottom-top);
 ctx.fillStyle='#91a9c2';ctx.strokeStyle='#30465a';
 for(const value of [0,20,40,60,80,100]){ctx.fillText(value+'%',4,y(value)+4);ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(right,y(value));ctx.stroke();}
 for(let i=0;i<=4;i++)ctx.fillText(Math.round(limit*i/4),x(limit*i/4)-8,207);
 ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(80));ctx.lineTo(right,y(80));ctx.stroke();ctx.setLineDash([]);
 ctx.strokeStyle='#5dd5bf';ctx.lineWidth=2;ctx.beginPath();m.curve.forEach((p,i)=>i?ctx.lineTo(x(p.cycle),y(p.soh_percent)):ctx.moveTo(x(p.cycle),y(p.soh_percent)));ctx.stroke();
 const details=el('div',undefined,'doe-grid');
 for(const [label,value] of [['Cathode porosity',format(m.cathode_porosity*100)+' %'],['Cathode thickness',format(m.cathode_thickness_um)+' µm'],['Cell mass',format(m.cell_mass_g)+' g'],['Energy Target margin',format(m.energy_density_margin_wh_kg)+' Wh/kg'],['Completed cycles',m.completed_cycles],['EOL cycle',m.cycles_to_80??'Chưa đạt · censored'],['Cell energy',format(m.energy_wh)+' Wh'],['Electrode area',format(m.electrode_area_cm2)+' cm²']]){const d=el('div',label);d.append(el('b',value));details.append(d);}$('doe-design-details').append(details);
}
function render(){
 table();$('doe-results').hidden=!report.effects;
 if(report.effects){
  $('doe-summary').replaceChildren();
  for(const [label,value] of [['Tổng số run',report.run_count],['Run hoàn tất',report.summary.completed],['STOP / Không phù hợp',report.summary.stopped+report.summary.infeasible],['Đạt Energy Target',report.summary.energy_target_met]]){const d=el('div');d.append(el('small',label),el('strong',String(value)));$('doe-summary').append(d);}
  selected=report.runs.find(r=>r.status==='completed')||report.runs[0];drawEffects();drawScatter();drawSelected();
 }
 setExports();
}
async function execute(kind){
 if(pending||!schema)return;if(!$('doe-form').reportValidity())return;
 let body;try{body=config();}catch(e){$('doe-error').textContent=e.message;return;}
 const seq=++revision;pending=true;setExports();$('doe-run').disabled=true;$('doe-preview').disabled=true;$('doe-error').textContent='';$('doe-status').textContent=kind==='run'?'Đang mô phỏng DOE…':'Đang tạo ma trận…';
 try{
  const endpoint=projectContext&&kind==='run'?'/api/workspace/experiments':'/api/doe/'+kind;
  const payload=projectContext&&kind==='run'?{design_id:projectContext.design.id,config:body,name:$('project-experiment-name').value}:body;
  const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(60000)});let data=await response.json();
  if(!response.ok)throw Error(data.error||response.statusText);
  if(projectContext&&kind==='run'){
   const id=data.id;
   for(;;){
    const stateResponse=await fetch('/api/workspace/experiments/'+id,{signal:AbortSignal.timeout(15000)});const state=await stateResponse.json();
    if(!stateResponse.ok)throw Error(state.error||'Không tải được DOE');
    if(state.status==='completed'){data=state.report;break;}
    if(['failed','interrupted'].includes(state.status))throw Error('DOE '+state.status+' · xem issue trong dashboard dự án');
    if(seq!==revision)return;
    $('doe-status').textContent=`DOE ${state.status} · đang chạy ${state.counts.running||0} · hoàn tất ${state.counts.completed||0} · xem được tại dashboard dự án`;
    await new Promise(resolve=>setTimeout(resolve,300));
   }
  }
  if(seq!==revision)return;if(!response.ok)throw Error(data.error||response.statusText);
  report=data;render();$('doe-status').textContent=`${kind==='run'?'Đã chạy':'Đã lập ma trận'} ${data.run_count} runs · seed ${data.config.seed} · dữ liệu tổng hợp ${data.model_version}`;
 }catch(e){if(seq===revision){$('doe-error').textContent=e.message;$('doe-status').textContent='Chưa hoàn tất · kiểm tra cấu hình hoặc kết nối.';}}
 finally{pending=false;$('doe-run').disabled=false;$('doe-preview').disabled=false;setExports();}
}
function save(name,body,type){const url=URL.createObjectURL(new Blob([body],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function csv(){
 const metricKeys=[...Object.keys(schema.metrics),'energy_target_met','eol_censored','completed_cycles','cell_mass_g','cathode_porosity','cathode_thickness_um','nominal_voltage_v','capacity_033c_ah','capacity_1c_ah','areal_capacity_mah_cm2'];
 const headers=['experiment_id','project_id','worksheet_id','worksheet_revision','workspace_experiment_id','model_version','data_origin','calibrated','seed','cycles','variation_percent','design_id','run_id','run_order','replicate','ml_split','status','reason',...Object.keys(schema.factors),...metricKeys];
 const quote=v=>{let s=String(v??'');if(typeof v==='string'&&/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
 const lines=report.runs.map(r=>{
  const row={experiment_id:report.experiment_id,project_id:report.project_context?.project.id,worksheet_id:report.project_context?.worksheet_id,worksheet_revision:report.project_context?.revision,workspace_experiment_id:report.workspace_experiment_id,model_version:report.model_version,data_origin:report.data_origin,calibrated:false,seed:report.config.seed,cycles:report.config.cycles,variation_percent:report.config.variation_percent,...r,...r.inputs,...(r.metrics||{})};
  return headers.map(k=>quote(row[k])).join(',');
 });save(`doe-${report.experiment_id}.csv`,'\uFEFF'+headers.join(',')+'\r\n'+lines.join('\r\n'),'text/csv;charset=utf-8');
}
$('doe-form').addEventListener('submit',e=>{e.preventDefault();execute('run');});$('doe-preview').addEventListener('click',()=>execute('plan'));
$('doe-form').addEventListener('input',invalidate);$('doe-form').addEventListener('change',invalidate);
$('doe-method').addEventListener('change',()=>{$('doe-samples').disabled=$('doe-method').value!=='balanced';});
$('doe-metric').addEventListener('change',()=>{if(report?.effects)drawEffects();});
$('doe-csv').addEventListener('click',csv);$('doe-json').addEventListener('click',()=>save(`doe-${report.experiment_id}.json`,JSON.stringify(report,null,2),'application/json'));
new ResizeObserver(()=>{if(report?.effects){drawEffects();drawScatter();drawSelected();}}).observe($('doe-results'));
try{
 const response=await fetch('/api/doe/schema');if(!response.ok)throw Error('Không tải được DOE schema');schema=await response.json();
 const query=new URLSearchParams(location.search),designId=query.get('design');
 if(designId){
  const contextResponse=await fetch('/api/workspace/designs/'+encodeURIComponent(designId));projectContext=await contextResponse.json();
  if(!contextResponse.ok)throw Error(projectContext.error);
  if(!projectContext.design.validation.simulation_supported)throw Error('Hồ sơ cell còn issue chặn mô phỏng; sửa trong trang dự án.');
  for(const [key,value] of Object.entries(projectContext.baseline))schema.factors[key].baseline=value;
  for(const [key,list] of [['cathode',projectContext.allowed_cathodes],['anode',projectContext.allowed_anodes],['electrolyte',projectContext.allowed_electrolytes]]){schema.factors[key].options=list;schema.factors[key].levels=list.slice(0,2);}
  schema.default_vary=Object.keys(projectContext.default_vary);
  for(const [key,levels] of Object.entries(projectContext.default_vary))schema.factors[key].levels=levels;
  $('project-return').href='projects.html?project='+projectContext.design.project_id;
  const box=$('doe-project-context');box.hidden=false;box.append(el('h3',projectContext.design.project.name+' · '+projectContext.design.name+' · rev '+projectContext.design.revision));
  const label=el('label','Tên lần chạy DOE '),input=document.createElement('input');input.id='project-experiment-name';input.value=projectContext.design.name+' DOE';input.maxLength=100;label.append(input);box.append(label,el('p','Kết quả và issue được lưu trong workspace SQLite. Các trường BOM ghi nhận riêng không tự tạo ảnh hưởng vật lý nếu chưa có mô hình hiệu chuẩn.'));
 }
 factors();for(const [key,label] of Object.entries(schema.metrics))$('doe-metric').add(new Option(label,key));$('doe-samples').disabled=true;$('doe-status').textContent=projectContext?'Sẵn sàng · DOE theo dự án đã chọn.':'Sẵn sàng · mặc định 16 tổ hợp × 500 chu kỳ.';
}catch(e){$('doe-error').textContent=e.message;$('doe-run').disabled=true;$('doe-preview').disabled=true;}
