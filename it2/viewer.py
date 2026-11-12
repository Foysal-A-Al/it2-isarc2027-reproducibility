"""Bounded real-IFC tessellation and a fully local interactive Plotly viewport."""
from collections import defaultdict
from html import escape
import json
from pathlib import Path
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import plotly.graph_objects as go


def _geometry_summary(records, triangles):
    """Partition the inventory without treating a display limit as missing IFC data."""
    from collections import Counter
    counts = Counter(r['status'] for r in records)
    return dict(requested=len(records), rendered=counts['rendered'], triangles=triangles,
                without_mesh=counts['no_representation'] + counts['tessellation_failed'],
                omitted_by_limit=counts['element_limit'] + counts['triangle_limit'],
                not_processed=counts['pending'] + counts['timeout'], reasons=dict(counts))


def extract_meshes(path, context=False, max_triangles=1_000_000, max_elements=10_000, _architecture_only=False, checkpoint=None):
    """Tessellate actual IFC geometry; retain one auditable outcome per element.

    Display budgets do not change topology or correspondence evidence. The
    default covers the study clinic; larger inputs remain explicitly bounded.
    """
    import hashlib
    import time
    if max_triangles < 1 or max_elements < 1:
        raise ValueError('Geometry budgets must be positive.')
    if context and not _architecture_only and max_triangles >= 2 and max_elements >= 2:
        shell = extract_meshes(path, context=True, max_triangles=max(1,max_triangles//4),
                               max_elements=max(1,max_elements//4), _architecture_only=True)
        network = extract_meshes(path, max_triangles=max_triangles-shell['triangles'],
                                 max_elements=max_elements-shell['rendered'], checkpoint=checkpoint)
        network['distribution'] = _geometry_summary(network['geometry_records'], network['triangles'])
        network['architecture'] = _geometry_summary(shell['geometry_records'], shell['triangles'])
        for key in ('requested','rendered','triangles','omitted_by_limit','without_mesh','not_processed'):
            network[key] += shell[key]
        network['geometry_records'] += shell['geometry_records']
        network['meshes'] = shell['meshes'] + network['meshes']
        network['warnings'] += shell['warnings']
        network.update(context_included=True,max_triangles=max_triangles,max_elements=max_elements)
        if not shell['requested']:
            network['warnings'].append('This IFC contains no supported architectural shell (building-element geometry). A full building view requires an architectural IFC; no building is invented.')
        return network
    f = ifcopenshell.open(str(path))
    elements = [] if _architecture_only else sorted(f.by_type('IfcDistributionElement'), key=lambda e:e.id())
    if context:
        family = 'IfcBuiltElement' if f.schema.upper().startswith('IFC4X3') else 'IfcBuildingElement'
        elements.extend(sorted(f.by_type(family),key=lambda e:e.id()))
    elements = list({e.id():e for e in elements}.values())
    records = {e.id():dict(step_id=e.id(), GlobalId=e.GlobalId or '', name=e.Name or '',
                           ifc_class=e.is_a(), context=not e.is_a('IfcDistributionElement'),
                           status='pending' if getattr(e,'Representation',None) else 'no_representation')
               for e in elements}
    # Elements with no representation consume no tessellation admission slots.
    eligible = [e for e in elements if records[e.id()]['status']=='pending']
    candidates = eligible[:max_elements]
    for e in eligible[max_elements:]:
        records[e.id()]['status']='element_limit'
    out = dict(meshes=[], context_included=bool(context), max_triangles=max_triangles,
               max_elements=max_elements, linear_deflection_m=.005, warnings=[],
               source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
    triangles = 0
    def result(partial=False):
        rows=[dict(r) for r in records.values()]
        summary=_geometry_summary(rows,triangles)
        data=dict(out,**summary,geometry_records=rows,partial=partial)
        data['architecture' if _architecture_only else 'distribution']=dict(summary)
        return data
    def save_partial():
        if checkpoint:
            target=Path(checkpoint); temporary=target.with_suffix('.partial')
            temporary.write_text(json.dumps(result(partial=True),allow_nan=False),encoding='utf-8')
            temporary.replace(target)
    if not candidates:
        return result()
    settings=ifcopenshell.geom.settings()
    settings.set('use-world-coords',True)
    settings.set('mesher-linear-deflection',.005)
    by_id={e.id():e for e in candidates}
    returned=set(); last_checkpoint=time.monotonic()
    save_partial()  # Inventory survives a timeout before the first mesh completes.
    try:
        iterator=ifcopenshell.geom.iterator(settings,f,2,include=candidates)
        if iterator.initialize():
            while True:
                shape=iterator.get(); eid=shape.id
                returned.add(eid)
                v=np.asarray(shape.geometry.verts,dtype=float).reshape(-1,3)
                faces=np.asarray(shape.geometry.faces,dtype=int).reshape(-1,3)
                valid=(len(v) and len(faces) and np.isfinite(v).all()
                       and faces.min()>=0 and faces.max()<len(v))
                if not valid:
                    records[eid]['status']='tessellation_failed'
                elif triangles+len(faces)>max_triangles:
                    records[eid]['status']='triangle_limit'
                else:
                    e=by_id[eid]
                    out['meshes'].append(dict(step_id=eid,GlobalId=e.GlobalId or '',
                        name=e.Name or '',ifc_class=e.is_a(),context=not e.is_a('IfcDistributionElement'),
                        vertices=v.tolist(),faces=faces.tolist()))
                    records[eid]['status']='rendered'
                    triangles+=len(faces)
                if len(returned)%256==0 and time.monotonic()-last_checkpoint>=3:
                    save_partial(); last_checkpoint=time.monotonic()
                # Complete the iterator: an early 90% cutoff hid usable geometry
                # and could leave the native iterator destructing an active job.
                if not iterator.next():
                    break
        for eid in set(by_id)-returned:
            records[eid]['status']='tessellation_failed'
    except Exception as exc:
        for eid in by_id:
            if records[eid]['status']=='pending':records[eid]['status']='tessellation_failed'
        out['warnings'].append('IFC tessellation did not complete: '+str(exc)[:300])
    return result()


def build_figure(meshes, highlight_ids=(), visible_ids=None, selected_id=None, source_key='model', context_opacity=.06, view='Perspective'):
    """Merge meshes by category for efficient rendering; filter by stable STEP id."""
    highlight = set(highlight_ids)
    visible = None if visible_ids is None else set(visible_ids)
    included = [m for m in meshes if m.get('context') or visible is None or m['step_id'] in visible]
    groups = defaultdict(list)
    for m in included:
        category = ('Architectural context' if m.get('context') else
                    'Selected element' if m['step_id'] == selected_id else
                    'Review elements' if m['step_id'] in highlight else
                    'Architectural context' if m.get('context') else 'Distribution network')
        groups[category].append(m)
    # Rebase only the display coordinates to protect WebGL precision for georeferenced IFCs.
    origin = np.asarray(included[0]['vertices'][0], dtype=float) if included else np.zeros(3)
    styles = {'Distribution network': ('#0891A6', 1.),
              'Review elements': ('#D97706', 1.),
              'Selected element': ('#7C3AED', 1.),
              'Architectural context': ('#94A3B8', float(np.clip(context_opacity,.02,.6)))}
    figure = go.Figure()
    for category in ('Architectural context', 'Distribution network', 'Review elements', 'Selected element'):
        items = groups.get(category)
        if not items:
            continue
        verts, triangles, labels, offset = [], [], [], 0
        for m in items:
            v = np.asarray(m['vertices'], dtype=float)-origin
            face = np.asarray(m['faces'], dtype=int)
            verts.extend(v.tolist())
            triangles.extend((face+offset).tolist())
            # Compact numeric hover ids avoid repeating long IFC names for every vertex.
            labels.extend([m['step_id']]*len(v))
            offset += len(v)
        v, t = np.asarray(verts), np.asarray(triangles)
        color, opacity = styles[category]
        figure.add_trace(go.Mesh3d(x=v[:,0], y=v[:,1], z=v[:,2],
            i=t[:,0], j=t[:,1], k=t[:,2], customdata=np.asarray(labels,dtype=np.int32), color=color, opacity=opacity,
            name=category, showlegend=True, flatshading=False,
            hovertemplate='IFC STEP #%{customdata}<extra></extra>',
            lighting=dict(ambient=.65, diffuse=.75, specular=.22, roughness=.65),
            lightposition=dict(x=100,y=200,z=300)))
    axis = dict(visible=False, showbackground=False)
    cameras = {'Perspective':dict(eye=dict(x=1.35,y=1.35,z=1.1)),
               'Plan':dict(eye=dict(x=0,y=0,z=2.5),up=dict(x=0,y=1,z=0),projection=dict(type='orthographic')),
               'Front':dict(eye=dict(x=0,y=-2.5,z=.1),up=dict(x=0,y=0,z=1),projection=dict(type='orthographic'))}
    figure.update_layout(height=440, margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF',
        scene=dict(xaxis=axis,yaxis=axis,zaxis=axis,aspectmode='data',
                   camera=cameras.get(view,cameras['Perspective']), bgcolor='#FFFFFF'),
        legend=dict(orientation='h', y=1.02, x=0, font=dict(size=11,color='#52667D')),
        uirevision=source_key+':framing-v2', font=dict(family='Arial, sans-serif'),
        annotations=[dict(text='World geometry · metres · display origin rebased',
                          x=0,y=0,xref='paper',yref='paper',showarrow=False,
                          font=dict(size=10,color='#708198'))])
    return figure


def context_alignment(network_meshes, shell_meshes):
    """Report coordinate bounds only. Never infer or apply an alignment transform."""
    def bounds(meshes):
        points=[np.asarray(m['vertices'],dtype=float) for m in meshes if m['vertices']]
        if not points:
            return None
        return np.min([p.min(0) for p in points],axis=0), np.max([p.max(0) for p in points],axis=0)
    a,b=bounds(network_meshes),bounds(shell_meshes)
    if a is None or b is None:
        return dict(overlaps=False,gap_m=None,available=False)
    gap=np.maximum(0,np.maximum(a[0]-b[1],b[0]-a[1]))
    return dict(overlaps=bool(np.all(gap==0)),gap_m=float(np.linalg.norm(gap)),available=True,
                network_bounds=[a[0].tolist(),a[1].tolist()],context_bounds=[b[0].tolist(),b[1].tolist()])


def extract_meshes_isolated(path, context=False, timeout=90, architecture_only=False):
    """Bound native code, snapshot input bytes and validate geometry provenance."""
    import hashlib
    import subprocess
    import sys
    import tempfile
    from .runtime import LIMITS
    from .worker import _SLOT
    path=Path(path).resolve()
    if not path.is_file() or not 0<path.stat().st_size<=LIMITS.upload_bytes:
        raise ValueError('IFC geometry input is missing, empty or exceeds 100 MiB.')
    if not 0<timeout<=LIMITS.worker_seconds:
        raise ValueError('Geometry timeout must be positive and at most 90 seconds.')
    if not _SLOT.acquire(blocking=False):
        raise ValueError('Another IFC analysis is running on this host. Retry after it finishes.')
    try:
        raw=path.read_bytes()
        if not 0<len(raw)<=LIMITS.upload_bytes:
            raise ValueError('IFC geometry input changed or exceeded its size budget.')
        digest=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(prefix='it2-geometry-') as folder:
            output=Path(folder)/'meshes.json'
            snapshot=Path(folder)/'input.ifc'; snapshot.write_bytes(raw); del raw
            command=[sys.executable,'-m','it2.viewer',str(snapshot),str(output),
                     '2' if architecture_only else '1' if context else '0']
            timed_out=False
            try:
                process=subprocess.run(command,cwd=Path(__file__).resolve().parents[1],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                       timeout=timeout,check=False)
            except subprocess.TimeoutExpired:
                timed_out=True; process=None
            if not output.exists():
                if timed_out:
                    raise TimeoutError(f'3D extraction exceeded {timeout:g} seconds before saving geometry. Full topology evidence remains available.')
                raise ValueError('3D geometry worker failed. Diagnostic tables remain available.')
            if output.stat().st_size>LIMITS.worker_output_bytes:
                raise ValueError('3D geometry payload exceeded the 100 MiB display budget.')
            data=json.loads(output.read_text(encoding='utf-8'))
            if data.get('source_sha256')!=digest:
                raise ValueError('Geometry worker provenance mismatch.')
            if data['requested']!=sum(data[k] for k in ('rendered','without_mesh','omitted_by_limit','not_processed')):
                raise ValueError('Geometry worker inventory is inconsistent.')
            if timed_out:
                for row in data['geometry_records']:
                    if row['status']=='pending':row['status']='timeout'
                data['timed_out']=True; data['partial']=True
                for layer in ('distribution','architecture'):
                    if layer in data:
                        records=[r for r in data['geometry_records'] if r['context']==(layer=='architecture')]
                        data[layer]=_geometry_summary(records,data[layer]['triangles'])
                data['warnings'].append('Geometry time limit reached. Showing saved real meshes; unprocessed elements are identified as timeout outcomes. Topology evidence is separate.')
            elif process.returncode:
                raise ValueError('3D geometry worker failed. No complete display is claimed.')
            return data
    finally:
        _SLOT.release()


if __name__=='__main__':
    import json
    from pathlib import Path
    import sys
    result=extract_meshes(sys.argv[1],context=sys.argv[3] in ('1','2'), _architecture_only=sys.argv[3]=='2',checkpoint=sys.argv[2])
    target=Path(sys.argv[2])
    temporary=target.with_suffix('.final')
    temporary.write_text(json.dumps(result,allow_nan=False),encoding='utf-8')
    temporary.replace(target)
