"""Source-backed presentation helpers; no analytical results are invented."""
import base64,io
from functools import lru_cache
from pathlib import Path
import numpy as np

ASSETS=Path(__file__).resolve().parents[1]/'app/assets'
LABELS={'Overview':'Overview','Topology check':'Topology','Identity check':'Identity & revisions',
        'Model comparison':'Identity & revisions','Point bindings':'Point bindings','Review queue':'Review queue',
        'Experiment lab':'Experiment lab','Study results':'Study evidence','Settings':'Settings','Help & support':'Help & support'}

def navigation_options(current='Overview'):
    identity='Model comparison' if current=='Model comparison' else 'Identity check'
    return ['Overview','Topology check',identity,'Point bindings','Review queue','Experiment lab','Study results','Settings','Help & support']

def navigation_label(route):return LABELS[route]

@lru_cache(maxsize=32)
def icon_uri(name):
    return 'data:image/svg+xml;base64,'+base64.b64encode((ASSETS/'icons'/f'{name}.svg').read_bytes().replace(b'currentColor',b'#DA7C13' if name=='alert-triangle' else b'#008664' if name=='check' else b'#14375B')).decode()

@lru_cache(maxsize=64)
def coverage_ring(value):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    value=float(np.clip(value,0,1))
    fig=Figure(figsize=(.64,.64),facecolor='none');ax=fig.add_axes([0,0,1,1])
    ax.pie([value,1-value],colors=['#00896A','#E4F1ED'],startangle=90,counterclock=False,wedgeprops=dict(width=.24,edgecolor='none'))
    ax.set_aspect('equal');out=io.StringIO();FigureCanvasSVG(fig).print_svg(out)
    return 'data:image/svg+xml;base64,'+base64.b64encode(out.getvalue().encode()).decode()

def mesh_layer(m):
    if m.get('context'):return 'Architecture'
    c=m.get('ifc_class','').lower();n=m.get('name','').lower();text=c+' '+n
    if any(x in text for x in ('cable','electric','light','conductor')):return 'Electrical'
    if 'pipe' in c or any(x in n for x in ('pipe','plumb','valve','waterheater','water heater')):return 'Plumbing'
    if any(x in text for x in ('duct','fan','airterminal','air terminal','hvac','ventilation')):return 'Mechanical'
    if any(x in text for x in ('sanitary','waste','bath','toilet','lavatory','sink','fixture')):return 'Fixtures'
    return 'Distribution'

def binding_summary(report):
    rows=report['rows'];retained=sum(bool(r['later_resolves_without_rebinding']) for r in rows)
    resolved=sum(bool(r['later_resolves_after_mapping']) for r in rows)
    approved=sum(bool(r['later_resolves_after_mapping']) and not r['later_resolves_without_rebinding'] for r in rows)
    return dict(total=len(rows),retained=retained,approved_rebindings=approved,unresolved=len(rows)-resolved,resolved=resolved)

def mesh_thumbnail(mesh):
    if not mesh or not mesh.get('vertices') or not mesh.get('faces'):return None
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    v=np.asarray(mesh['vertices'],dtype=float);faces=np.asarray(mesh['faces'],dtype=int)
    if not np.isfinite(v).all() or faces.min()<0 or faces.max()>=len(v):return None
    origin=(v.min(0)+v.max(0))/2;v=v-origin
    fig=Figure(figsize=(1.6,1.1),dpi=100,facecolor='#F3F7F9');ax=fig.add_axes([0,0,1,1],projection='3d')
    step=max(1,int(np.ceil(len(faces)/2000)))
    ax.add_collection3d(Poly3DCollection(v[faces[::step]],facecolor='#E88A12',edgecolor='#A96412',linewidths=.12,alpha=.95))
    radius=max(float(np.ptp(v,axis=0).max())*.6,.01)
    ax.set(xlim=(-radius,radius),ylim=(-radius,radius),zlim=(-radius,radius));ax.set_box_aspect((1,1,1))
    ax.view_init(elev=22,azim=-55);ax.set_axis_off();out=io.BytesIO();FigureCanvasAgg(fig).print_png(out)
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
