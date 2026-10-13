const $=id=>document.getElementById(id);
let data=null,index=0,timer=null,requestID=0;
function stop(){clearInterval(timer);timer=null;}
function draw(){
 const canvas=$('ml-chart'),w=canvas.clientWidth,h=220,dpr=Math.min(devicePixelRatio,2);canvas.width=w*dpr;canvas.height=h*dpr;
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);if(!data)return;
 const rows=data.replay.slice(0,index+1),left=42,right=w-15,top=12,bottom=h-30;
 const x=c=>left+(c-1)/(data.replay.at(-1).cycle-1)*(right-left),y=v=>bottom-(v-55)/50*(bottom-top);
 ctx.font='11px system-ui';ctx.fillStyle='#91a9c2';ctx.strokeStyle='#293e52';
 for(const v of [60,70,80,90,100]){ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(right,y(v));ctx.stroke();ctx.fillText(v+'%',2,y(v)+4);}
 for(const c of [1,25,50,75,100,132])ctx.fillText(c,x(c)-7,h-8);
 ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(80));ctx.lineTo(right,y(80));ctx.stroke();ctx.setLineDash([]);
 for(const [key,color] of [['soh_percent','#5dd5bf'],['predicted_soh','#c799ff']]){
  ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();rows.forEach((r,i)=>i?ctx.lineTo(x(r.cycle),y(r[key])):ctx.moveTo(x(r.cycle),y(r[key])));ctx.stroke();
 }
}
async function show(){
 if(!data)return;const row=data.replay[index],seq=++requestID;
 $('ml-cycle').value=index;$('ml-status').textContent=`B0018 · Chu kỳ ${row.cycle}/${data.replay.length} · kiểm tra ngoài tập huấn luyện`;
 $('ml-soh').textContent=`${row.soh_percent.toFixed(2)} / ${row.predicted_soh.toFixed(2)} %`;
 $('ml-rul').textContent=`${row.true_rul.toFixed(0)} / ${row.predicted_rul.toFixed(1)}`;
 draw();
 try{
  const response=await fetch('/api/ml/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({features:row.features}),signal:AbortSignal.timeout(4000)});
  const result=await response.json();if(seq!==requestID)return;if(!response.ok)throw Error(result.error);
  $('ml-soh').textContent=`${row.soh_percent.toFixed(2)} / ${result.soh_percent.toFixed(2)} %`;
  $('ml-rul').textContent=`${row.true_rul.toFixed(0)} / ${result.remaining_cycles.toFixed(1)}`;
 }catch(e){if(seq===requestID){stop();$('ml-status').textContent='Lỗi suy luận ML: '+e.message;}}
}
export function initML(){
 $('ml-load').addEventListener('click',async()=>{stop();$('ml-status').textContent='Đang tải kết quả ML từ raw data…';try{
  const response=await fetch('/api/ml/replay',{signal:AbortSignal.timeout(4000)});const result=await response.json();if(!response.ok)throw Error(result.error);data=result;index=0;
  $('ml-mae-soh').textContent=`${data.metrics.soh.mae.toFixed(2)} điểm %`;$('ml-mae-rul').textContent=`${data.metrics.rul.mae.toFixed(2)} chu kỳ`;
  for(const id of ['ml-play','ml-pause','ml-cycle'])$(id).disabled=false;$('ml-cycle').max=data.replay.length-1;show();
 }catch(e){$('ml-status').textContent=e.message;}});
 $('ml-play').addEventListener('click',()=>{if(!data)return;stop();if(index>=data.replay.length-1)index=0;timer=setInterval(()=>{if(index>=data.replay.length-1){stop();return;}index++;show();},500);});
 $('ml-pause').addEventListener('click',stop);$('ml-cycle').addEventListener('input',e=>{stop();index=Number(e.target.value);show();});
 new ResizeObserver(draw).observe($('ml-chart'));
}
