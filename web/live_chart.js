const $=id=>document.getElementById(id);

function plot(id,rows,series,threshold=null){
 const canvas=$(id),width=canvas.clientWidth,height=180,dpr=Math.min(devicePixelRatio,2);
 canvas.width=Math.round(width*dpr);canvas.height=height*dpr;
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 ctx.font='11px system-ui';ctx.fillStyle='#adbac7';
 if(!rows.length){ctx.textAlign='center';ctx.fillText('Chờ đủ 600 giây dữ liệu xả',width/2,height/2);canvas.dataset.points='0';return;}
 canvas.dataset.points=String(rows.length);
 const values=rows.flatMap(r=>series.map(s=>r[s.key]));
 const lo=threshold===null?0:Math.max(0,Math.floor((Math.min(threshold,...values)-5)/10)*10);
 const hi=threshold===null?Math.max(10,Math.ceil(Math.max(...values)*1.15/10)*10):Math.max(105,Math.ceil(Math.max(...values)/5)*5);
 const left=42,right=width-14,top=20,bottom=height-30;
 const minCycle=rows[0].cycle,maxCycle=Math.max(minCycle+1,rows.at(-1).cycle);
 const x=cycle=>left+(cycle-minCycle)/(maxCycle-minCycle)*(right-left);
 const y=v=>bottom-(v-lo)/(hi-lo)*(bottom-top);
 ctx.strokeStyle='#3e453c';ctx.lineWidth=1;
 for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4;ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(right,y(value));ctx.stroke();ctx.fillText(value.toFixed(0),3,y(value)+4);}
 ctx.fillText(threshold===null?'Chu kỳ còn lại':'SOH (%)',left,12);
 for(const cycle of [...new Set([minCycle,Math.round((minCycle+maxCycle)/2),maxCycle])])ctx.fillText(String(cycle),x(cycle)-4,height-16);
 ctx.textAlign='right';ctx.fillText('Chu kỳ xả',right,height-2);ctx.textAlign='left';
 if(threshold!==null){ctx.strokeStyle='#ef7777';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(threshold));ctx.lineTo(right,y(threshold));ctx.stroke();ctx.setLineDash([]);}
 for(const {key,color} of series){
  ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.beginPath();
  rows.forEach((r,i)=>i?ctx.lineTo(x(r.cycle),y(r[key])):ctx.moveTo(x(r.cycle),y(r[key])));ctx.stroke();
  for(const r of rows){ctx.beginPath();ctx.arc(x(r.cycle),y(r[key]),3,0,Math.PI*2);ctx.fill();}
  const last=rows.at(-1);ctx.textAlign='right';ctx.fillText(last[key].toFixed(2),right,Math.max(top+12,Math.min(bottom-4,y(last[key])-7)));ctx.textAlign='left';
 }
}

export function drawLivePrediction(cell){
 const rows=cell.live_ml_history||[];
 plot('live-soh-chart',rows,[{key:'simulated_soh_percent',color:'#5dd5bf'},{key:'soh_percent',color:'#c799ff'}],80);
 plot('live-rul-chart',rows,[{key:'remaining_cycles',color:'#f6cd85'}]);
 $('live-soh-chart').setAttribute('aria-label',`CH ${cell.id}: ${rows.length} dự báo SOH theo chu kỳ`);
 $('live-rul-chart').setAttribute('aria-label',`CH ${cell.id}: ${rows.length} dự báo số chu kỳ còn lại`);
}
