"""All figures of the paper -> figures/*.png. Needs the JSON files in results/."""
import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':9,'axes.linewidth':0.7,'savefig.dpi':220})
from _common import RES, FIG
O=str(FIG)+'/'
BL='#2E75B6'; LB='#DDEBF7'; GO='#BF9000'; RD='#C00000'; GR='#548235'; K='black'
def box(ax,x,y,w,h,t,ec=K,fc='white',ls='-',lw=1.1,fs=8,r=0.08,bold=False,tc=K,va='center'):
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={r}',fc=fc,ec=ec,ls=ls,lw=lw))
  ax.text(x+w/2,y+h/2,t,ha='center',va=va,fontsize=fs,fontweight='bold' if bold else 'normal',color=tc,linespacing=1.25)
def arr(ax,a,b,c=BL,ls='-',rad=0,lw=1.0):
  ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=9,lw=lw,color=c,linestyle=ls,connectionstyle=f'arc3,rad={rad}'))

# ---- Fig 1 loops (coloured by loop)
fig,ax=plt.subplots(figsize=(7.4,3.1)); ax.set_xlim(0,16.4); ax.set_ylim(0,6.2); ax.axis('off')
def loop(cx,title,steps,col):
  ax.text(cx,5.85,title,ha='center',fontsize=9.5,style='italic',color=col)
  pos=[(cx,4.7),(cx+2.45,3.0),(cx,1.2),(cx-2.45,3.0)]
  for (x,y),s in zip(pos,steps): box(ax,x-1.55,y-0.45,3.1,0.9,s,ec=col,fs=6.5,r=0.12)
  for i in range(4):
    a=np.array(pos[i]);b=np.array(pos[(i+1)%4]);d=(b-a)/np.linalg.norm(b-a)
    arr(ax,tuple(a+d*np.array([1.1,0.62])),tuple(b-d*np.array([1.1,0.62])),c=col,rad=-0.25)
  ax.text(cx,3.0,'R',ha='center',va='center',fontsize=12,color=col)
loop(4.1,'(a) identity decay loop',['re-export regenerates\nGlobalIds','sensor bindings\nbreak (BV falls)','analytics keyed on\nBMS point names','model off critical path,\nnobody maintains it'],BL)
loop(12.3,'(b) topology absence loop',['models carry no ports\nor connections','diagnosis cannot\ntraverse the network','rules hard-coded\nper building','no contractual push\nto model connectivity'],GO)
plt.savefig(O+'f1_loops.png',bbox_inches='tight'); plt.close()

# ---- Fig 2 research design (framework style)
fig,ax=plt.subplots(figsize=(7.8,3.9)); ax.set_xlim(0,29); ax.set_ylim(0,13.4); ax.axis('off')
def side(x,y,w,h,title,body,ls='-'):
  box(ax,x,y,w,h,'',ec=BL,ls=ls,lw=1.4,r=0.45)
  ax.text(x+w/2,y+h-0.6,title,ha='center',va='top',fontsize=8,fontweight='bold')
  ax.text(x+w/2,y+h/2-0.4,body,ha='center',va='center',fontsize=7,color='0.2',linespacing=1.35)
side(0.2,4.6,4.6,4.0,'Problem','model-to-data links\nin BIM-based twins\nare assumed,\nnot tested')
side(5.6,4.9,4.4,3.4,'Method','IT2: metrics and\nverification\nprotocol',ls='--')
arr(ax,(4.8,6.6),(5.6,6.6))
ph=[(11.3,10.2,'Phase 1: Data and features','7 open IFC models (5 real Revit exports)\nclass, container, Tag, type, bounding box','Output: fingerprint tables'),
    (11.3,5.6,'Phase 2: Topology integrity (RQ3)','PC, CC, TF, LC, SM per model\nexporter and schema compared','Output: topology profile'),
    (11.3,1.0,'Phase 3: Identity integrity (RQ2)','feature-level simulation, 20 seeds\nfile-level round trip, sensitivity, BV','Output: P, R, F1 with 95% CI')]
for x,y,t,sb,o in ph:
  box(ax,x,y,11.0,2.5,'',ec=BL,ls='--',lw=1.3,r=0.35)
  ax.text(x+5.5,y+1.9,t,ha='center',fontsize=8,fontweight='bold'); ax.text(x+5.5,y+0.85,sb,ha='center',va='center',fontsize=6.9,color='0.25',linespacing=1.3)
  box(ax,x+1.75,y-0.95,7.5,0.7,o,ec=BL,fc=LB,lw=0.8,fs=7,r=0.12)
  arr(ax,(10.0,6.6),(x,y+1.25),ls='--',c=BL,lw=1.0)
arr(ax,(16.8,9.25),(16.8,8.1)); arr(ax,(16.8,4.65),(16.8,3.5))
side(23.6,4.4,5.2,4.4,'Outcome','acceptance gate for\nmodel revisions,\nevidence on exporters\nand matcher limits')
ax.plot([20.3,26.2],[0.4,0.4],color=BL,lw=1.0); arr(ax,(26.2,0.4),(26.2,4.4))
plt.savefig(O+'f2_design.png',bbox_inches='tight'); plt.close()

# ---- Fig 3 protocol
fig,ax=plt.subplots(figsize=(7.4,3.1)); ax.set_xlim(0,15.2); ax.set_ylim(0,6.4); ax.axis('off')
box(ax,0.1,2.6,1.9,1.3,'model\nrevision\nM$_{t+1}$',ec=K,fc='0.95',fs=7,r=0.15)
xs=[2.5,5.0,7.5,10.0]; labs=['S1  IDS\nreadiness','S2  identity\nreconciliation','S3  topology\nintegrity','S4  lift to\nBOT / Brick']
cols=[GR,BL,GO,BL]
for x,l,c in zip(xs,labs,cols): box(ax,x,2.6,2.0,1.3,l,ec=c,lw=1.4,fs=7,r=0.15)
box(ax,12.6,2.45,2.4,1.6,'S5  gate\nIC, BV, PC, LC\n≥ thresholds?',ec=RD,lw=1.4,fs=7,r=0.3)
arr(ax,(2.0,3.25),(2.5,3.25),c=K)
for x in xs[:-1]: arr(ax,(x+2.0,3.25),(x+2.5,3.25),c=K)
arr(ax,(12.0,3.25),(12.6,3.25),c=K)
box(ax,12.95,5.2,1.7,0.8,'accept into\ntwin',ec=GR,fc='#EAF3E2',fs=7,r=0.12); arr(ax,(13.8,4.05),(13.8,5.2),c=GR); ax.text(13.9,4.55,'pass',fontsize=7.5,color=GR)
box(ax,4.0,0.2,6.5,0.95,'human review queue (BCF issues):\nlow-confidence matches, inferred connections',ec=K,fc='0.97',fs=7,r=0.12)
arr(ax,(13.8,2.45),(10.5,0.68),c=RD,rad=-0.15); ax.text(11.9,1.05,'fail',fontsize=7.5,color=RD)
arr(ax,(6.0,2.6),(6.4,1.15),ls='--',c=K); arr(ax,(8.5,2.6),(8.2,1.15),ls='--',c=K)
arr(ax,(4.0,0.68),(1.05,2.6),rad=-0.2,ls='--',c=K); ax.text(0.15,0.45,'fix and\nre-submit',fontsize=7.5)
ax.text(7.5,6.0,'runs at handover and at every model or BMS point-list change',ha='center',fontsize=8,color='0.3')
ax.legend(handles=[Patch(fc='white',ec=GR,label='standard reused (IDS)'),Patch(fc='white',ec=BL,label='identity and semantics'),Patch(fc='white',ec=GO,label='topology'),Patch(fc='white',ec=RD,label='decision')],loc='upper left',fontsize=6.5,frameon=True,edgecolor='0.6',bbox_to_anchor=(0,1.02))
plt.savefig(O+'f3_protocol.png',bbox_inches='tight'); plt.close()

# ---- Fig 4 quadrant
# Experimental panels read saved JSON outputs; conceptual panels above are authored diagrams.
T=json.load(open(RES/'topology.json'))
NAMES={'Simple-Scene_Building-Hvac_IFC4X3.ifc':'Simple-Scene HVAC','Simple-Scene_Infra-Plumbing_IFC4X3.ifc':'Simple-Scene Plumbing',
 'Duplex_MEP_20110907.ifc':'Duplex MEP','Duplex_Electrical_20121207.ifc':'Duplex Electrical','Duplex_Plumbing_20121113.ifc':'Duplex Plumbing',
 'Clinic_HVAC.ifc':'Clinic HVAC','Clinic_Plumbing.ifc':'Clinic Plumbing'}
pts=[]
for t in T:
  src='2011' if 'Revit MEP 2011' in t['exporter'] else ('2013' if 'Revit' in t['exporter'] else 'sample')
  pts.append((NAMES.get(t['file'],t['file']),t['SM'],t['PC'],t['D'],src))
col={'sample':GR,'2011':RD,'2013':BL}
fig,ax=plt.subplots(figsize=(5.4,4.2))
ax.axvline(0.5,color=K,lw=0.6); ax.axhline(0.5,color=K,lw=0.6)
for (x,y,t) in [(0.08,0.97,'Topology without systems'),(0.52,0.97,'Target: both present'),(0.08,0.46,'Neither'),(0.52,0.46,'Systems without topology')]:
  ax.text(x,y,t,fontsize=7.2,fontweight='bold',va='top')
lab={'Simple-Scene HVAC':(0.72,0.28),'Simple-Scene Plumbing':(0.66,0.14),'Duplex MEP':(0.12,0.24),'Duplex Electrical':(0.12,0.1),'Duplex Plumbing':(0.14,0.62),'Clinic HVAC':(0.16,0.85),'Clinic Plumbing':(0.2,0.73)}
for n,x,y,d,s in pts:
  jx=x+(0.012 if 'Plumbing' in n and s=='sample' else 0)
  ax.scatter(x,y,s=16+np.sqrt(d)*1.1,marker='D',fc=col[s],ec=K,lw=0.5,zorder=3)
  tx,ty=lab[n]; ax.annotate(f'{n} ({d:,})',(x,y),(tx,ty),fontsize=6.8,ha='left',va='center',arrowprops=dict(arrowstyle='-',lw=0.6,color=col[s]),bbox=dict(boxstyle='square,pad=0.25',fc='white',ec=col[s],lw=0.9))
ax.set_xlim(-0.07,1.07); ax.set_ylim(-0.07,1.07); ax.set_xlabel('System membership, SM'); ax.set_ylabel('Port coverage, PC')
ax.legend(handles=[Patch(fc='white',ec=GR,label='buildingSMART sample'),Patch(fc='white',ec=RD,label='Revit MEP 2011 export'),Patch(fc='white',ec=BL,label='Revit 2013 exports')],fontsize=6.5,loc='center right',bbox_to_anchor=(1.0,0.62),frameon=True,edgecolor='0.6',title='Source',title_fontsize=7)
plt.savefig(O+'f4_quadrant.png',bbox_inches='tight'); plt.close()

# ---- Fig 5 recall vs recreated, three models
# Plot the mean and bootstrap endpoints saved by the identity experiment.
rs=['0.0','0.1','0.2','0.3','0.5']
fig,ax=plt.subplots(figsize=(5.0,3.3))
for fn,ls,lab in [('Clinic_HVAC','-','Clinic HVAC'),('Duplex_Plumbing_20121113','--','Duplex Plumbing'),('Duplex_MEP_20110907',':','Duplex MEP')]:
  M=json.load(open(RES/f'identity_{fn}.json'))
  for m,c,mk in [('tag',RD,'s'),('placement',GO,'^'),('hybrid',BL,'o')]:
    y=[M[r][m]['R'][0] for r in rs]; lo=[M[r][m]['R'][1] for r in rs]; hi=[M[r][m]['R'][2] for r in rs]
    x=[float(r) for r in rs]; ax.plot(x,y,ls=ls,marker=mk,ms=3.5,color=c,lw=1.0,mfc='white')
    ax.fill_between(x,lo,hi,color=c,alpha=0.15,lw=0)
ax.text(0.5,1.012,'IT2 hybrid',ha='right',fontsize=7.5,color=BL); ax.text(0.34,0.72,'ElementId (Tag) key',fontsize=7.5,color=RD)
ax.text(0.2,0.95,'placement only, 2011 export',fontsize=7,color=GO); ax.text(0.2,0.61,'placement only, 2013 exports',fontsize=7,color=GO)
ax.set_xlabel('share of elements recreated (new GlobalId and new Tag)'); ax.set_ylabel('recall (mean, 95% CI)'); ax.set_ylim(0.42,1.04); ax.set_xticks([0,0.1,0.2,0.3,0.5])
for s in ['top','right']: ax.spines[s].set_visible(False)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([],[],color=K,ls='-',label='Clinic HVAC (3,704)'),Line2D([],[],color=K,ls='--',label='Duplex Plumbing (498)'),Line2D([],[],color=K,ls=':',label='Duplex MEP (926)')],fontsize=6.8,frameon=False,loc='lower left')
plt.savefig(O+'f5_recall.png',bbox_inches='tight'); plt.close()

# ---- Fig 6 sensitivity heatmaps
# Each heatmap cell is mean F1, not an individual run or a confidence interval.
fig,axs=plt.subplots(1,2,figsize=(6.8,2.7))
lams=['0','0.15','0.3','0.6','1.0']; taus=['0.25','0.5','1.0','2.0']
for ax,(fn,tt) in zip(axs,[('Clinic_HVAC','(a) Clinic HVAC'),('Duplex_Plumbing_20121113','(b) Duplex Plumbing')]):
  G=json.load(open(RES/f'extra_{fn}.json'))['grid']
  Z=np.array([[G[f'{float(l) if l!="0" else 0}|{float(t)}'][2] if f'{float(l) if l!="0" else 0}|{float(t)}' in G else G[f'{l}|{t}'][2] for t in taus] for l in lams])
  im=ax.imshow(Z,cmap='Blues',vmin=0.85,vmax=1.0,aspect='auto')
  for i in range(len(lams)):
    for j in range(len(taus)): ax.text(j,i,f'{Z[i,j]:.3f}',ha='center',va='center',fontsize=6.8,color='white' if Z[i,j]>0.95 else K)
  ax.set_xticks(range(len(taus))); ax.set_xticklabels(taus); ax.set_yticks(range(len(lams))); ax.set_yticklabels(lams)
  ax.set_xlabel('gate τ (m)'); ax.set_title(tt,fontsize=8.5)
  ax.add_patch(plt.Rectangle((0.5,1.5),1,1,fill=False,ec=RD,lw=1.5))
axs[0].set_ylabel('name weight λ')
cb=fig.colorbar(im,ax=axs,shrink=0.85); cb.set_label('F1',fontsize=8)
plt.savefig(O+'f6_sensitivity.png',bbox_inches='tight'); plt.close()

# ---- Fig 7 roadmap
tasks=[('W1  metrics, protocol, controlled study',0,3,'done'),('W2  exporter study: consecutive exports, several tools',2,7,''),('W3  learned fingerprint weights, calibrated confidence',5,10,''),('W4  instrumented building: measure BV on a live BMS',6,13,''),('W5  FDD portability test with and without IT2 gate',11,16,''),('W6  open benchmark: IDS file, scripts, labelled pairs',14,18,'')]
cs=[BL,BL,BL,GO,RD,GR]
fig,ax=plt.subplots(figsize=(7.2,2.9))
for k,((t,a,b,note),c) in enumerate(zip(tasks[::-1],cs[::-1])):
  ax.barh(k,b-a,left=a,height=0.45,color=c if note else 'white',edgecolor=c,lw=1.2,hatch='' if note else '////',alpha=1)
  ax.text(-0.3,k,t,ha='right',va='center',fontsize=7.8)
  if note: ax.text(b+0.2,k,'done (this paper)',va='center',fontsize=7,style='italic')
for g,l in [(7,'G1: IC on real\nrevision pairs'),(13,'G2: BV on a\nlive building'),(18,'G3: public\nrelease')]:
  ax.axvline(g,color=K,lw=0.6,ls=':'); ax.text(g,len(tasks)-0.35,l,ha='center',va='bottom',fontsize=6.8)
ax.set_xlim(0,18.5); ax.set_ylim(-0.6,len(tasks)+0.6); ax.set_yticks([]); ax.set_xticks(range(0,19,3)); ax.set_xlabel('month')
for s in ['top','right','left']: ax.spines[s].set_visible(False)
plt.savefig(O+'f7_roadmap.png',bbox_inches='tight'); plt.close()
print('ok')
