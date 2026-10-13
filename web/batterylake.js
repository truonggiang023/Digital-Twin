const $=id=>document.getElementById(id);
let record=null,source=null,version=0;
async function get(path){const r=await fetch(path,{signal:AbortSignal.timeout(20000)});const d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d;}
function detail(){
 const host=$('lake-details');host.replaceChildren();if(!record)return;
 const heading=document.createElement('h3');heading.textContent=record.identity.dataset_name;host.append(heading);
 const grid=document.createElement('div');grid.className='lake-grid';
 const c=record.cell,cond=record.conditions;
 const values=[['Hóa học',(c.cathode_chemistries||[]).join(', ')||'Chưa biết'],['Dung lượng định mức',c.nominal_capacity_Ah==null?'Chưa biết':c.nominal_capacity_Ah+' Ah'],['Nhiệt độ thử nghiệm',(cond.temperature_setpoints_C||[]).join(', ')+' °C'],['C-rate xả tối đa',cond.discharge_c_rate_max??'Chưa biết']];
 for(const [label,value] of values){const box=document.createElement('div');box.textContent=label;const b=document.createElement('b');b.textContent=value;box.append(b);grid.append(box);}host.append(grid);
 const note=document.createElement('p');note.textContent=record.identity.notes||'';host.append(note);
 const link=document.createElement('a');link.textContent='Metadata gốc · xem nguồn và giới hạn dữ liệu';link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';host.append(link);
 const temperatures=(cond.temperature_setpoints_C||[]).filter(x=>Number.isFinite(x)&&x>=-10&&x<=60);
 $('lake-apply').disabled=!temperatures.length||!Number.isFinite(cond.discharge_c_rate_max)||cond.discharge_c_rate_max<.1||cond.discharge_c_rate_max>5;
}
async function loadRecord(){const seq=++version;record=null;$('lake-apply').disabled=true;try{const data=await get('/api/batterylake/datasets/'+$('lake-dataset').value);if(seq!==version)return;record=data.record;source=data;detail();$('lake-status').textContent='Metadata đã tải từ BatteryLake · commit '+data.upstream_commit.slice(0,7);}catch(e){if(seq===version){$('lake-status').textContent=e.message;$('lake-details').replaceChildren();}}}
async function catalog(){version++;record=null;$('lake-apply').disabled=true;try{
 $('lake-status').textContent='Đang tải metadata thật…';const q=new URLSearchParams({chemistry:$('lake-chemistry').value,task:$('lake-task').value,search:$('lake-search').value});
 const data=await get('/api/batterylake/datasets?'+q);$('lake-status').textContent=`${data.matched}/${data.total} bộ dữ liệu · nguồn BatteryLake`;
 if($('lake-chemistry').options.length===1)for(const x of data.facets.cathode_chemistries||[])$('lake-chemistry').add(new Option(x,x));
 $('lake-dataset').replaceChildren();for(const row of data.items)$('lake-dataset').add(new Option(row.dataset_name,row.dataset_id));
 $('lake-dataset').disabled=!data.items.length;$('lake-details').replaceChildren();if(data.items.length)await loadRecord();
 }catch(e){$('lake-status').textContent=e.message;$('lake-dataset').disabled=true;$('lake-details').replaceChildren();}}
export function initBatteryLake(){
 $('lake-form').addEventListener('submit',e=>{e.preventDefault();catalog();});$('lake-dataset').addEventListener('change',loadRecord);
 $('lake-apply').addEventListener('click',()=>{
  if(!record)return;const cond=record.conditions;const temperature=cond.temperature_setpoints_C.find(x=>Number.isFinite(x)&&x>=-10&&x<=60);
  $('p-temperature').value=temperature;$('p-rate').value=cond.discharge_c_rate_max;
  $('lake-reference').textContent=`Tham khảo ${record.dataset_id}: chọn ${temperature} °C trong các setpoint, C-rate xả tối đa ${cond.discharge_c_rate_max}. DoD và dung lượng của cell mô phỏng giữ nguyên. Đây không phải hiệu chuẩn bằng dữ liệu đo.`;
  $('prediction-form').requestSubmit();
 });
}
