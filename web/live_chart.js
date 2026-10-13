const $=id=>document.getElementById(id);

function plot(id,rows,series,threshold=null,timeAxis=false){
 const canvas=$(id),width=canvas.clientWidth,height=180,dpr=Math.min(devicePixelRatio,2);
 canvas.width=Math.round(width*dpr);canvas.height=height*dpr;
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 ctx.font='11px system-ui';ctx.fillStyle='#adbac7';
 if(!rows.length){ctx.textAlign='center';ctx.fillText('Chờ đủ 600 giây dữ liệu xả',width/2,height/2);canvas.dataset.points='0';return;}
 canvas.dataset.points=String(rows.length);
 const values=rows.flatMap(r=>series.map(s=>r[s.key])).filter(Number.isFinite);
 const lo=threshold===null?0:Math.max(0,Math.floor((Math.min(threshold,...values)-5)/10)*10);
 const hi=threshold===null?Math.max(10,Math.ceil(Math.max(...values)*1.15/10)*10):Math.max(105,Math.ceil(Math.max(...values)/5)*5);
 const left=42,right=width-14,top=20,bottom=height-30;
 const coordinate=r=>timeAxis?r.time_s/60:r.cycle;
 const minCycle=coordinate(rows[0]),maxCycle=Math.max(minCycle+1,coordinate(rows.at(-1)));
 const x=cycle=>left+(cycle-minCycle)/(maxCycle-minCycle)*(right-left);
 const y=v=>bottom-(v-lo)/(hi-lo)*(bottom-top);
 ctx.strokeStyle='#3e453c';ctx.lineWidth=1;
 for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4;ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(right,y(value));ctx.stroke();ctx.fillText(value.toFixed(0),3,y(value)+4);}
 ctx.fillText(threshold===null?'Chu kỳ còn lại':'SOH (%)',left,12);
 for(const cycle of [...new Set([minCycle,(minCycle+maxCycle)/2,maxCycle])])ctx.fillText(cycle.toFixed(timeAxis?1:0),x(cycle)-4,height-16);
 ctx.textAlign='right';ctx.fillText(timeAxis?'Thời gian giả lập (phút)':'Chu kỳ xả',right,height-2);ctx.textAlign='left';
 if(threshold!==null){ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(threshold));ctx.lineTo(right,y(threshold));ctx.stroke();ctx.setLineDash([]);}
 const labelYs=[];
 for(const {key,color} of series){
  const points=rows.filter(r=>Number.isFinite(r[key]));if(!points.length)continue;
  ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.beginPath();
  points.forEach((r,i)=>i?ctx.lineTo(x(coordinate(r)),y(r[key])):ctx.moveTo(x(coordinate(r)),y(r[key])));ctx.stroke();
  for(const r of points){ctx.beginPath();ctx.arc(x(coordinate(r)),y(r[key]),points.length>20?1:3,0,Math.PI*2);ctx.fill();}
  const last=points.at(-1),desired=Math.max(top+12,Math.min(bottom-4,y(last[key])-7));
  const labelY=[desired,desired+14,desired-14].find(v=>v>=top+12&&v<=bottom-4&&labelYs.every(other=>Math.abs(v-other)>=12))??desired;
  labelYs.push(labelY);ctx.textAlign='right';ctx.fillText(last[key].toFixed(2),right,labelY);ctx.textAlign='left';
 }
}

export function drawLivePrediction(cell){
 const rows=cell.live_ml_history||[];
 const timeline=[...(cell.live_soh_history||[{time_s:cell.time_s,simulated_soh_percent:cell.soh_percent}]),...rows.map(r=>({time_s:r.time_s,soh_percent:r.soh_percent}))].sort((a,b)=>a.time_s-b.time_s);
 plot('live-soh-chart',timeline,[{key:'simulated_soh_percent',color:'#5dd5bf'},{key:'soh_percent',color:'#c799ff'}],80,true);
 plot('live-rul-chart',rows,[{key:'remaining_cycles',color:'#f6cd85'}]);
 $('live-soh-chart').setAttribute('aria-label',`CH ${cell.id}: SOH theo thời gian, ${rows.length} dự báo ML`);
 $('live-rul-chart').setAttribute('aria-label',`CH ${cell.id}: ${rows.length} dự báo số chu kỳ còn lại`);
}
