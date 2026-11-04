import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const lines=(await fs.readFile('results/ledger.csv','utf8')).trim().split(/\r?\n/);
const keys=lines.shift().split(',');
const data=lines.map(l=>Object.fromEntries(l.split(',').map((v,i)=>[keys[i],i===0?v:Number(v)])));
const wb=Workbook.create(), pub=wb.worksheets.add('Public markets'), s=wb.worksheets.add('Overview'), d=wb.worksheets.add('Daily');
const r=(sh,a)=>sh.getRange(a);
const val=(sh,a,v)=>r(sh,a).values=[[v]];
const fx=(sh,a,v)=>r(sh,a).formulas=[[v]];
function band(sh,addr,title,color='#18384B'){
 const range=r(sh,addr);range.merge();range.values=[[title]];
 range.format.fill=color;range.format.font.color='#FFFFFF';range.format.font.bold=true;range.format.rowHeight=26;
}
for(const sh of [s,d]) sh.showGridLines=false;
r(s,'A1:F25').format.columnWidth=16;r(s,'A:A').format.columnWidth=32;
band(s,'A1:F1','Energy research   /   Henry Hub × ERCOT North');
band(s,'A2:F2','Daily spark-spread model     •     Synthetic sample, January–December 2025','#296B70');
r(s,'A4:C7').values=[['Performance  /  USD','Signal strategy','Always long'],['Net P&L',null,null],['Max drawdown',null,null],['Trading fees',null,null]];
r(s,'B5:C7').formulas=[['=Daily!Q369','=Daily!V369'],['=MIN(Daily!R5:R369)','=MIN(Daily!W5:W369)'],['=SUM(Daily!O5:O369)','=SUM(Daily!T5:T369)*B12*B13']];
band(s,'A9:F9','Model assumptions     /     Edit the blue values');
r(s,'A10:B13').values=[['Heat rate  ·  MMBtu/MWh',7],['Variable O&M  ·  $/MWh',3],['Position size  ·  MWh',100],['Fee per spread turn  ·  $/MWh',.15]];
band(s,'A15:F15','Generation margin sensitivity     /     Final observation, $ per MWh');
band(s,'A16:F16','Rows shift power ($/MWh). Columns shift gas ($/MMBtu).','#296B70');
r(s,'A17:F17').values=[['Power shift  /  gas shift',-1,-.5,0,.5,1]];
r(s,'A18:A22').values=[[-10],[-5],[0],[5],[10]];
r(s,'B18:F22').formulas=Array.from({length:5},(_,i)=>Array.from('BCDEF',c=>'=Daily!$C$369+$A'+(18+i)+'-(Daily!$B$369+'+c+'$17)*$B$10-$B$11'));
band(s,'A24:F24','Daily contains the inputs, signals and P&L. Both strategies close on the last day.','#296B70');
for(const a of ['A4:C4','A17:F17']){r(s,a).format.fill='#D9E9EB';r(s,a).format.font.bold=true;}
for(const a of ['B10:B13','B17:F17','A18:A22'])r(s,a).format.font.color='#2158A0';
for(const a of ['B5:C7','B10:B13','B18:F22'])r(s,a).setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
band(d,'A1:W1','Daily market observations and trading ledger');
band(d,'A2:W2','Synthetic sample from model.py, seed 913   •   Blue cells are inputs   •   Held position earns the change from the preceding mark','#296B70');
const headers=['Date','Gas $/MMBtu','Power $/MWh','Temp °F','Load MW','Fuel $/MWh','Spread $/MWh','Implied MMBtu/MWh','Margin $/MWh','Degrees from 65°F','Signal','Held position','Δ spread $/MWh','Turns','Fees $','Net P&L $','Cum. P&L $','Drawdown $','Long position','Long turns','Long P&L $','Long cum. $','Long drawdown $'];
r(d,'A4:W4').values=[headers];r(d,'A4:W4').format.fill='#D9E9EB';r(d,'A4:W4').format.font.bold=true;
r(d,'A:W').format.columnWidth=20;r(d,'A5:E369').format.font.color='#2158A0';
r(d,'A5:E369').values=data.map(x=>[Date.parse(x.day)/86400000+25569,x.gas,x.power,x.temp,x.load]);
r(d,'A5:A369').setNumberFormat('mmm d, yyyy');r(d,'B5:W369').setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
r(d,'F5:W369').formulas=data.map((x,i)=>{
 const n=i+5,p=n-1,avg=c=>'AVERAGE('+c+(n-20)+':'+c+p+')';
 const signal=i<20?'0':'IF(AND(E'+n+'>'+avg('E')+',J'+n+'>'+avg('J')+',G'+n+'<'+avg('G')+'),1,IF(AND(E'+n+'<'+avg('E')+',J'+n+'<'+avg('J')+',G'+n+'>'+avg('G')+'),-1,0))';
 const turns=c=>'ABS('+c+n+'-'+(i?c+p:'0')+')'+(i===364?'+ABS('+c+n+')':'');
 return ['B'+n+'*Overview!$B$10','C'+n+'-F'+n,'C'+n+'/B'+n,'G'+n+'-Overview!$B$11','ABS(D'+n+'-65)',signal,i>=2?'K'+(n-2):'0',i?'G'+n+'-G'+p:'0',turns('L'),'N'+n+'*Overview!$B$12*Overview!$B$13','L'+n+'*M'+n+'*Overview!$B$12-O'+n,'P'+n+(i?'+Q'+p:''),'Q'+n+'-MAX(0,Q$5:Q'+n+')',i>=22?'1':'0',turns('S'),'Overview!$B$12*(S'+n+'*M'+n+'-T'+n+'*Overview!$B$13)','U'+n+(i?'+V'+p:''),'V'+n+'-MAX(0,V$5:V'+n+')'].map(v=>'='+v);
});
d.freezePanes.freezeRows(4);
const publicRows=(await fs.readFile('public_results/daily.csv','utf8')).trim().split(/\r?\n/);
const publicKeys=publicRows.shift().split(',');
const marks=publicRows.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[publicKeys[i],i===0?v:Number(v)])));
const status=JSON.parse(await fs.readFile('public_results/status.json','utf8'));
pub.showGridLines=false;
const endRow=marks.length+11;
r(pub,'A:L').format.columnWidth=19;
band(pub,'A1:L1','ERCOT North   /   Day-ahead and real-time settlement strategy');
band(pub,'A2:L2','Historical paper book   •   '+status.first+' through '+status.last+'   •   ERCOT settlements, Henry Hub gas and DFW weather','#296B70');
r(pub,'A4:F4').values=[['Net P&L $','Max drawdown $','Without weather $','Always long $','Double costs $','Scored days']];
r(pub,'A5:F5').formulas=[['=SUM(F12:F'+endRow+')','=MIN(H12:H'+endRow+')','=SUM(I12:I'+endRow+')','=SUM(J12:J'+endRow+')','=SUM(F12:F'+endRow+')-SUM(K12:K'+endRow+')','=COUNT(F12:F'+endRow+')']];
band(pub,'A7:L7','Paper signal for '+status.target+'     /     '+(status.signal ? status.signal.target_mwh.toFixed(1)+' signed MWh   •   Expected RT minus DA '+status.signal.forecast.toFixed(2)+' USD/MWh' : 'Unavailable due to missing inputs'));
band(pub,'A8:L8','Snapshot from refresh.py. The local dashboard updates while refresh.py --watch is running. Other worksheets contain the synthetic reference model.','#296B70');
r(pub,'A11:L11').values=[['Delivery date','DA $/MWh','RT $/MWh','Edge $/MWh','Held MWh','Net P&L $','Cum. P&L $','Drawdown $','No weather $','Always long $','Assumed cost $','Spark input $/MWh']];
r(pub,'A12:L'+endRow).values=marks.map(m=>[Date.parse(m.day)/86400000+25569,m.da,m.rt,m.forecast,m.mwh,null,null,null,m.no_weather,m.always_long,m.cost,m.spark]);
r(pub,'F12:H'+endRow).formulas=marks.map((_,i)=>{const n=12+i;return ['=E'+n+'*(C'+n+'-B'+n+')-K'+n,'=F'+n+(i?'+G'+(n-1):''),'=G'+n+'-MAX(0,G$12:G'+n+')'];});
r(pub,'A12:A'+endRow).setNumberFormat('mmm d, yyyy');
for (const a of ['B12:L'+endRow,'A5:E5']) r(pub,a).setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
for (const a of ['A4:F4','A11:L11']){r(pub,a).format.fill='#D9E9EB';r(pub,a).format.font.bold=true;}
pub.freezePanes.freezeRows(11);
val(pub,'G4','Always short $');
fx(pub,'G5','=SUM(M12:M'+endRow+')');
val(pub,'M11','Always short $');
r(pub,'M:M').format.columnWidth=19;
r(pub,'M12:M'+endRow).values=marks.map(m=>[m.always_short]);
for(const a of ['G5','M12:M'+endRow])r(pub,a).setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
const review=wb.worksheets.add('Walk-forward');
review.showGridLines=false;
const readRows=async name=>{
 const csv=(await fs.readFile('results/'+name+'.csv','utf8')).trim().split(/\r?\n/);
 const columns=csv.shift().split(',');
 return csv.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[columns[i],v])));
};
const runs=await readRows('walkforward'), forecasts=new Map((await readRows('forecasts')).map(row=>[row.day,row]));
const serial=v=>Date.parse(v)/86400000+25569;
const last=7+runs.length;
r(review,'A:M').format.columnWidth=20;
band(review,'A1:M1','Walk-forward evaluation   /   Ridge forecast');
band(review,'A2:M2','Fixed Python run   •   Synthetic 2025 marks   •   90 training observations per fit   •   Refit every 20 signals   •   $350 daily risk budget','#296B70');
r(review,'A4:F4').values=[['Net P&L $','Always long $','Max drawdown $','Worst 5% mean $','Fees $','Test days']];
r(review,'A5:F5').formulas=[['=SUM(J8:J'+last+')','=SUM(K8:K'+last+')','=MIN(M8:M'+last+')','=AVERAGE(SMALL(J8:J'+last+',{'+Array.from({length:Math.ceil(runs.length*.05)},(_,i)=>i+1).join(',')+'}))','=SUM(I8:I'+last+')','=COUNT(J8:J'+last+')']];
// Average the bottom k observations (including ties only to fill k slots).
const cutoff='SMALL(J8:J'+last+',ROUNDUP(F5*5%,0))', net='J8:J'+last;
fx(review,'D5','=(SUMIF('+net+',"<"&'+cutoff+','+net+')+(ROUNDUP(F5*5%,0)-COUNTIF('+net+',"<"&'+cutoff+'))*'+cutoff+')/ROUNDUP(F5*5%,0)');
r(review,'A7:M7').values=[['Mark date','Signal date','Fit through','Forecast $/MWh','Volatility $/MWh','Held MWh','Gas leg MMBtu','Turnover MWh','Fees $','Net P&L $','Always long $','Cum. P&L $','Drawdown $']];
r(review,'A8:M'+last).values=runs.map(row=>{
 const f=forecasts.get(row.decision_day);
 return [serial(row.day),serial(row.decision_day),serial(f.train_last_label),+f.forecast,+f.volatility,+row.held_mwh,-7*row.held_mwh,+row.traded_mwh,+row.fees,+row.net_pnl,+row.benchmark_pnl,+row.equity,+row.drawdown];
});
r(review,'A8:C'+last).setNumberFormat('mmm d, yyyy');
for(const a of ['A5:E5','D8:M'+last])r(review,a).setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
for(const a of ['A4:F4','A7:M7']){r(review,a).format.fill='#D9E9EB';r(review,a).format.font.bold=true;}
review.freezePanes.freezeRows(7);
band(s,'A26:F26','Walk-forward test    /    Fixed Python run, independent of inputs above','#296B70');
r(s,'A27:D27').values=[['Net P&L $','Always long $','Max drawdown $','Worst 5% mean $']];
r(s,'A28:D28').formulas=[['=\'Walk-forward\'!A5','=\'Walk-forward\'!B5','=\'Walk-forward\'!C5','=\'Walk-forward\'!D5']];
r(s,'A28:D28').setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
val(s,'B10',8);wb.recalculate();
if(Math.abs(r(d,'F5').values[0][0]-8*data[0].gas)>1e-8)throw Error('Heat-rate change failed');
val(s,'B10',7);wb.recalculate();
for(const [col,key] of [['G','spread'],['K','signal'],['L','position'],['P','net_pnl'],['Q','equity'],['R','drawdown'],['V','bench_equity'],['W','bench_drawdown']]){
 const v=r(d,col+'5:'+col+'369').values;
 if(data.some((x,i)=>!Number.isFinite(v[i][0])||Math.abs(x[key]-v[i][0])>1e-6))throw Error('Mismatch '+key);
}
console.log((await wb.inspect({kind:'table',range:'Overview!A4:C7',include:'values,formulas',tableMaxRows:4,tableMaxCols:3})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!',options:{useRegex:true,maxResults:3}})).ndjson);
if(Math.abs(r(review,'D5').values[0][0]-Number((await readRows('risk'))[0].worst_tail_mean_pnl))>1e-7)throw Error('Tail mismatch');
if(Math.abs(r(pub,'A5').values[0][0]-status.net)>1e-6)throw Error('Public ledger mismatch');
for(const [sheetName,range] of [['Public markets','A1:L15'],['Overview','A1:F28'],['Daily','A1:J10'],['Walk-forward','A1:M12']]){
 const blob=await wb.render({sheetName,range,scale:1});
 await fs.writeFile('artifacts/'+sheetName+'.png',new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save('artifacts/Spark Spread.xlsx');

