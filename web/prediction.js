const $=id=>document.getElementById(id);
let selected=Number($('cell-select').value||0)+1,result=null,version=0;

function graph(id,key,threshold=null){
 const canvas=$(id),w=canvas.clientWidth,h=220,dpr=Math.min(devicePixelRatio,2);
 canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 if(!result||w<1)return;
 const points=result.points,isSOH=key==='soh_percent',maxX=result.scenario.horizon;
 const lo=isSOH?Math.max(0,Math.floor(Math.min(...points.map(p=>p.pessimistic_soh_percent),threshold)/10)*10):0;
 const hi=isSOH?100:points[0].capacity_ah*1.05;
 const left=48,right=w-16,top=12,bottom=h-30;
 const x=n=>left+n/maxX*(right-left),y=n=>bottom-(n-lo)/(hi-lo)*(bottom-top);
 ctx.font='11px system-ui';ctx.fillStyle='#91a9c2';ctx.strokeStyle='#293e52';
 for(let i=0;i<=4;i++){
  const v=lo+(hi-lo)*i/4;ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(right,y(v));ctx.stroke();ctx.fillText(v.toFixed(isSOH?0:2),2,y(v)+4);
  const cycle=maxX*i/4;ctx.fillText(Math.round(cycle),x(cycle)-12,h-8);
 }
 if(isSOH){
  ctx.fillStyle='rgba(93,213,191,.15)';ctx.beginPath();
  points.forEach((p,i)=>i?ctx.lineTo(x(p.cycle),y(p.optimistic_soh_percent)):ctx.moveTo(x(p.cycle),y(p.optimistic_soh_percent)));
  [...points].reverse().forEach(p=>ctx.lineTo(x(p.cycle),y(p.pessimistic_soh_percent)));ctx.closePath();ctx.fill();
 }
 if(threshold!==null){ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(threshold));ctx.lineTo(right,y(threshold));ctx.stroke();ctx.setLineDash([]);}
 ctx.strokeStyle='#5dd5bf';ctx.lineWidth=2;ctx.beginPath();
 points.forEach((p,i)=>i?ctx.lineTo(x(p.cycle),y(p[key])):ctx.moveTo(x(p.cycle),y(p[key])));ctx.stroke();
}
function render(){
 if(!result)return;
 $('prediction-cell').textContent=`CH ${String(result.cell).padStart(2,'0')}`;
 $('p-soh').textContent=`${result.initial_soh_percent.toFixed(3)} %`;
 $('p-rul').textContent=`≈ ${Math.ceil(result.remaining_cycles).toLocaleString('vi-VN')}`;
 const end=result.points.at(-1);$('p-capacity').textContent=`${end.capacity_ah.toFixed(3)} Ah`;$('p-resistance').textContent=`${end.resistance_mohm.toFixed(2)} mΩ`;
 $('prediction-context').textContent=`Chụp trạng thái tại ${result.time_s.toFixed(0)} s. Khoảng kịch bản EOL: ${Math.ceil(result.remaining_cycles_low)}–${Math.ceil(result.remaining_cycles_high)} chu kỳ bổ sung. ${result.eol_within_horizon?'Ngưỡng EOL nằm trong khoảng dự báo.':'Ngưỡng EOL nằm ngoài khoảng dự báo.'} Một chu kỳ bổ sung tương ứng ${result.scenario.dod.toFixed(2)} EFC.`;
 graph('forecast-soh','soh_percent',result.scenario.eol_soh*100);graph('forecast-capacity','capacity_ah');
}
async function calculate(){
 const seq=++version;
 if(!$('prediction-form').checkValidity()){$('export-prediction').disabled=true;return;}
 const query=new URLSearchParams({cell:selected,temperature_c:$('p-temperature').value,c_rate:$('p-rate').value,dod:Number($('p-dod').value)/100,horizon:$('p-horizon').value,eol_soh:Number($('p-eol').value)/100});
 try{
  const response=await fetch('/api/prediction?'+query,{signal:AbortSignal.timeout(4000)});const data=await response.json();
  if(seq!==version)return;
  if(!response.ok)throw Error(data.error||'Không lấy được dự báo');
  result=data;$('prediction-error').textContent='';$('export-prediction').disabled=false;render();
 }catch(e){if(seq===version){$('prediction-error').textContent=e.message;$('export-prediction').disabled=true;}}
}
export function initPrediction(){
 $('prediction-form').addEventListener('submit',e=>{e.preventDefault();calculate();});
 $('prediction-form').addEventListener('input',()=>{$('export-prediction').disabled=true;});
 window.addEventListener('cycler-cell',e=>{selected=e.detail+1;result=null;version++;$('export-prediction').disabled=true;calculate();});
 $('export-prediction').addEventListener('click',()=>{
  if(!result)return;
  const fields=['cycle','efc','soh_percent','capacity_ah','resistance_mohm','optimistic_soh_percent','pessimistic_soh_percent'];
  const metadata=['source,local-model','model,'+result.model,'cell,'+result.cell,'snapshot_time_s,'+result.time_s,...Object.entries(result.scenario).map(([k,v])=>k+','+v),''];
  const text=metadata.join('\n')+'\n'+fields.join(',')+'\n'+result.points.map(p=>fields.map(k=>p[k]).join(',')).join('\n');
  const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`prediction-cell-${result.cell}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 new ResizeObserver(render).observe($('forecast-soh').parentElement);
 calculate();setInterval(calculate,5000);
}
