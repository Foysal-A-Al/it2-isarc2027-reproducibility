"""Explicit-port metrics using the shared operational graph policy.

CC retains its published meaning (ports participating in exported relations).
Excluded edges are reported separately: CC is not valid-edge coverage.
Saved paper artifacts and experimental matching remain unchanged.
"""
from pathlib import Path
import ifcopenshell
from .graph import ports_of as _ports_of, build_graph, GRAPH_POLICY


def topology_metrics(path, opened=None, graph=None):
    f = opened if opened is not None else ifcopenshell.open(path)
    graph=graph if graph is not None else build_graph(f);D=graph['elements']
    if not D:raise ValueError(f'{path}: no IfcDistributionElement instances')
    ids={e.id() for e in D};sizes=[len(c) for c in graph['components']]
    ports=f.by_type('IfcPort');in_system=set()
    for g in f.by_type('IfcSystem'):
        for rel in g.IsGroupedBy or []:in_system.update(o.id() for o in rel.RelatedObjects)
    header=f.header.file_name
    return dict(file=Path(path).name,schema=f.schema,
                exporter=' | '.join(x for x in (getattr(header,'preprocessor_version','') or '',getattr(header,'originating_system','') or '') if x),
                D=len(D),PC=sum(bool(graph['port_ids'][e.id()]) for e in D)/len(D),ports=len(ports),
                CC=len(graph['connected_ports'])/len(ports) if ports else 0.,
                components=len(sizes),isolated=sum(s==1 for s in sizes),TF=len(sizes)/len(D),LC=max(sizes)/len(D),
                SM=len(in_system & ids)/len(D),systems=len(f.by_type('IfcSystem')),
                control_elements=len(f.by_type('IfcDistributionControlElement')),
                contained=sum(bool(e.ContainedInStructure) for e in D)/len(D))


def topology_details(path, opened=None, graph=None):
    f=opened if opened is not None else ifcopenshell.open(path)
    graph=graph if graph is not None else build_graph(f);comp={eid:(cid,len(members)) for cid,members in enumerate(graph['components']) for eid in members}
    in_system=set()
    for g in f.by_type('IfcSystem'):
        for rel in g.IsGroupedBy or []:in_system.update(o.id() for o in rel.RelatedObjects)
    return [dict(GlobalId=e.GlobalId,ifc_class=e.is_a(),name=e.Name or '',ports=len(graph['port_ids'][e.id()]),
                 component=comp[e.id()][0],component_size=comp[e.id()][1],in_system=e.id() in in_system,step_id=e.id()) for e in graph['elements']]
