'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const read = p => JSON.parse(fs.readFileSync(path.join(root,p), 'utf8'));
const target = path.join(root,'charts');
fs.mkdirSync(target,{recursive:true});
const esc = s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const palette=['#1c5d87','#438aaf','#b58a55','#8aa7b7'];
function svgStart(title,subtitle,height=420){
return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 '+height+'" role="img" aria-label="'+esc(title)+'"><rect width="1000" height="'+height+'" fill="#fff"/><rect x="1" y="1" width="998" height="'+(height-2)+'" rx="12" fill="none" stroke="#dae3eb"/><text x="52" y="59" font-family="Arial,sans-serif" font-size="26" font-weight="700" fill="#18364d">'+esc(title)+'</text><text x="52" y="86" font-family="Arial,sans-serif" font-size="15" fill="#63798a">'+esc(subtitle)+'</text>';
}
const text=(x,y,t,size=16,color='#244158',weight='400',anchor='start')=>'<text x="'+x+'" y="'+y+'" text-anchor="'+anchor+'" font-family="Arial,sans-serif" font-size="'+size+'" fill="'+color+'" font-weight="'+weight+'">'+esc(t)+'</text>';
const rect=(x,y,w,h,color,r=4)=>'<rect x="'+x+'" y="'+y+'" width="'+Math.max(0,w)+'" height="'+h+'" rx="'+r+'" fill="'+color+'"/>';
function save(name,body){fs.writeFileSync(path.join(target,name),body+'</svg>','utf8');console.log(name);}
function bars({title,subtitle,rows,max=100,unit='%',footer='',height}){
 const h=height||Math.max(345,170+rows.length*47);
 let out=svgStart(title,subtitle,h);
 const x=325,w=575;
 for(let k=0;k<=4;k++){const gx=x+w*k/4;out+='<line x1="'+gx+'" y1="115" x2="'+gx+'" y2="'+(h-57)+'" stroke="#e5ebf0"/>'+text(gx,109,(max*k/4).toFixed(max===100?0:1)+unit,12,'#7e8b96','400','middle');}
 rows.forEach((r,i)=>{const y=133+i*47;out+=text(52,y+20,r.label,15,'#203b52','600');out+=rect(x,y,w*r.value/max,27,r.color||palette[i%4]);out+=text(Math.min(960,x+w*r.value/max+12),y+19,(r.value).toFixed(r.decimals??1)+unit,15,'#203b52','600')});
 out+=text(52,h-28,footer,12,'#6d7d8b');return out;
}
const external=read('research/validation-2026-10-28/external_summary.json');
const methods=['review_margin_003','original_hybrid','placement'].map(k=>external.methods.find(m=>m.method===k));
save('edited-target-recovery.svg',bars({title:'Edited-target recovery is not overall recall',subtitle:'Authored BIM-Edit evaluation, 36 revision pairs, 12 labelled update targets',rows:methods.map((m,i)=>({label:['Review-aware','Original hybrid','Placement baseline'][i],value:m.update_targets_correct/12*100,color:palette[i],decimals:1})),footer:'Edited-target recovery: 6/12, 4/12 and 8/12. Placement also falsely links 5 creations and 5 deletions.'}));
save('overall-vs-edited.svg',bars({title:'The aggregate-metric blind spot',subtitle:'Review-aware matcher on authored BIM-Edit pairs',rows:[{label:'Overall recall',value:100*methods[0].recall,color:palette[0],decimals:2},{label:'Edited-target recall',value:100*methods[0].update_targets_correct/12,color:palette[2],decimals:1}],footer:'Different denominators: overall survivor correspondences vs 12 labelled edited targets.'}));
const amb=read('results/ambiguity_comparison.json');
const ambRows=[];
for(const [k,label] of [['Duplex_Plumbing','Plumbing'],['Duplex_MEP','MEP']])for(const [mk,ml] of [['it2_review','IT2'],['bimdelta','BIMDelta']])ambRows.push({label:label+' · '+ml,value:100*amb[k][mk].recall,color:mk==='it2_review'?palette[0]:palette[1]});
save('ambiguity-recall.svg',bars({title:'Recall under injected matching ambiguity',subtitle:'Regenerated IDs plus coincident same-Tag decoys, 3 seeds per model',rows:ambRows,footer:'Higher recall is not equivalent to fewer wrong matches; see the accompanying wrong-pair chart.'}));
const wrongRows=[];
for(const [k,label] of [['Duplex_Plumbing','Plumbing'],['Duplex_MEP','MEP']])for(const [mk,ml] of [['it2_review','IT2'],['bimdelta','BIMDelta']])wrongRows.push({label:label+' · '+ml,value:100*amb[k][mk].wrong_per_survivor,color:mk==='it2_review'?palette[0]:palette[2],decimals:2});
save('ambiguity-wrong-pairs.svg',bars({title:'Wrong correspondences under ambiguity',subtitle:'Wrong pairs per surviving element (%)',rows:wrongRows,max:2,footer:'IT2 is not uniformly superior: BIMDelta performs better on both recall and wrong-pair rate for MEP.'}));
const stress=read('results/comparator_full.json');
const sr=[];
for(const [k,name] of [['combined','Combined · '],['coincident_decoys','Decoys · ']])for(const [m,label] of [['review','Review-aware'],['hybrid','Hybrid'],['sig_geo','Graph-signature']])sr.push({label:name+label,value:100*stress.scenarios[k][m].wrong_per_survivor,color:{review:palette[0],hybrid:palette[1],sig_geo:palette[2]}[m],decimals:2});
save('stress-wrong-pairs.svg',bars({title:'Wrong-pair rates across stress scenarios',subtitle:'Macro-averaged over 3 fixed models × 20 perturbation seeds',rows:sr,max:10,footer:'Controlled perturbations; the seeds do not represent independent building histories.',height:495}));
const topology=read('results/topology.json');
const names=[['Duplex_Plumbing','Duplex_Plumbing_20121113.ifc'],['Duplex_MEP','Duplex_MEP_20110907.ifc'],['Clinic_HVAC','Clinic_HVAC.ifc']];
save('port-coverage.svg',bars({title:'Port coverage across the three principal exports',subtitle:'Percentage of in-scope distribution elements with a host-associated port',rows:names.map(([label,f],i)=>{let t=topology.find(x=>x.file===f);if(!t)throw new Error('Missing topology '+f);return {label:label.replaceAll('_',' '),value:100*t.PC,color:palette[i],decimals:1}}),footer:'Port coverage is descriptive and does not certify correct engineering connectivity.'}));
console.log('Charts generated from saved experiment JSON. No random or estimated data.');
