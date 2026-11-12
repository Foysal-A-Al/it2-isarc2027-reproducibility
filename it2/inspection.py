"""Actionable IFC diagnostics, distinct from the preserved paper metrics.

All connections come from explicit IFC relations. System fragmentation is a
review prompt, never proof of a physically defective network.
"""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path
import ifcopenshell
import ifcopenshell.util.element
from .graph import ports_of as _ports_of, build_graph, components as _components, connection_evidence


def inspect_model(path, opened=None, graph=None):
    """Return source-scoped findings with IFC STEP ids, including duplicate GUIDs."""
    f = opened if opened is not None else ifcopenshell.open(str(path))
    graph = graph if graph is not None else build_graph(f)
    elements = graph['elements']
    ids = {e.id() for e in elements}
    owners, port_ids, adjacency = graph['owners'], graph['port_ids'], graph['adjacency']
    membership = defaultdict(set)
    system_entities = {}
    for group in f.by_type('IfcSystem'):
        system_entities[group.id()] = group
        for relation in getattr(group, 'IsGroupedBy', None) or []:
            for e in relation.RelatedObjects or []:
                if e.id() in ids:
                    membership[e.id()].add(group.id())

    issues = []
    def issue(kind, title, element_ids, detail, action, port_ids=(), system_id=None, severity='Review'):
        involved, ports = sorted(set(element_ids)), sorted(set(port_ids))
        identity = repr((kind, involved, ports, system_id)).encode()
        issues.append(dict(id=hashlib.sha256(identity).hexdigest()[:20],
                           kind=kind, title=title, severity=severity,
                           element_ids=involved, port_ids=ports, system_id=system_id,
                           detail=detail, action=action))

    all_ports = f.by_type('IfcPort')
    for p in sorted(all_ports, key=lambda e: e.id()):
        owned = owners[p.id()]
        if not owned:
            issue('orphan_port', 'Port without distribution owner', [],
                  f'Port #{p.id()} has no exported owner in the distribution-element scope.',
                  'Check port nesting or port-to-element ownership in the source export.', [p.id()])
        elif len(owned) > 1:
            issue('port_ownership_conflict', 'Conflicting port ownership', owned,
                  f'Port #{p.id()} is attached to {len(owned)} distribution elements. Its graph edges are excluded from this inspection.',
                  'Resolve the port owner in the authoring model and export again.', [p.id()])

    for rel in f.by_type('IfcRelConnectsPorts'):
        a, b = rel.RelatingPort, rel.RelatedPort
        if a is None or b is None:
            issue('incomplete_connection', 'Incomplete port relation', [],
                  f'Relation #{rel.id()} has a missing endpoint.', 'Repair the relation in the source IFC export.', [rel.id()])
            continue
        oa, ob = owners[a.id()], owners[b.id()]
        if len(oa) == len(ob) == 1:
            x, y = next(iter(oa)), next(iter(ob))
            if x == y:
                issue('self_connection', 'Connection within one element', [x],
                      'Both connected ports belong to the same distribution element.',
                      'Verify whether this internal connection is intentional.', [a.id(), b.id()])
            else:
                adjacency[x].add(y)
                adjacency[y].add(x)
        da, db = getattr(a, 'FlowDirection', None), getattr(b, 'FlowDirection', None)
        if da == db and da in ('SOURCE', 'SINK'):
            issue('flow_direction', 'Port flow directions need review', oa | ob,
                  f'The exported connection joins two {da} ports. Undirected reachability does not validate this flow.',
                  'Check source/sink direction and exporter conventions.', [a.id(), b.id()])

    components = _components(ids, adjacency)
    comp = {eid: (i, len(members)) for i, members in enumerate(components) for eid in members}
    rows = []
    gids, tags = defaultdict(list), defaultdict(list)
    for e in elements:
        eid = e.id()
        try:
            container = ifcopenshell.util.element.get_container(e)
        except (AttributeError, RuntimeError):
            container = None
        systems = sorted(membership[eid])
        rows.append(dict(step_id=eid, GlobalId=e.GlobalId or '', name=e.Name or '',
                         ifc_class=e.is_a(), tag=getattr(e, 'Tag', None) or '',
                         storey=(container.Name or '') if container else '',
                         system_ids=systems,
                         system_names=[system_entities[s].Name or f'System #{s}' for s in systems],
                         ports=len(port_ids[eid]), component=comp[eid][0],
                         component_size=comp[eid][1]))
        if not port_ids[eid]:
            issue('missing_ports', 'Distribution element has no ports', [eid],
                  f'{e.is_a()} #{eid} exports no owned ports.',
                  'Check whether ports are expected for this element and enable them in the IFC export.')
        elif not adjacency[eid]:
            issue('isolated_element', 'Element has no external connection', [eid],
                  f'{len(port_ids[eid])} owned ports, but no unambiguous exported link to another distribution element.',
                  'Inspect its ports and determine whether the element is a valid standalone device.')
        if e.GlobalId:
            gids[e.GlobalId].append(eid)
        else:
            issue('missing_globalid', 'Missing GlobalId', [eid], 'No identity key is exported.',
                  'Assign a stable IFC GlobalId before linking external points.')
        if getattr(e, 'Tag', None):
            tags[(e.is_a(), e.Tag)].append(eid)
    for key, members in sorted(gids.items()):
        if len(members) > 1:
            issue('duplicate_globalid', 'Duplicate GlobalId', members,
                  f'{len(members)} elements share GlobalId {key}. STEP ids keep them distinct in this view.',
                  'Repair duplicate identities before accepting bindings or revision matches.')
    for key, members in sorted(tags.items()):
        if len(members) > 1:
            issue('duplicate_tag', 'Ambiguous class / Tag key', members,
                  f'{len(members)} elements share {key[0]} / {key[1]}.',
                  'Review geometry and source identities; do not accept an arbitrary Tag match.')

    systems = []
    for sid, group in sorted(system_entities.items()):
        members = {eid for eid in ids if sid in membership[eid]}
        if not members:
            continue
        parts = _components(members, adjacency)
        systems.append(dict(step_id=sid, name=group.Name or f'System #{sid}',
                            PC=sum(bool(port_ids[eid]) for eid in members)/len(members),
                            elements=len(members), components=len(parts),
                            largest_component_share=max(map(len, parts)) / len(members),
                            element_ids=sorted(members)))
        if len(parts) > 1:
            issue('system_fragmentation', 'Named system contains separate branches', members,
                  f'{group.Name or "Unnamed system"} contains {len(parts)} components in its induced exported graph.',
                  'Verify whether these branches are intentionally independent; inspect missing exported connections.',
                  system_id=sid)
    order = {'port_ownership_conflict': 0, 'duplicate_globalid': 1, 'incomplete_connection': 2,
             'flow_direction': 3, 'system_fragmentation': 4}
    issues.sort(key=lambda x: (order.get(x['kind'], 5), x['kind'], x['id']))
    return dict(source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                schema=f.schema, elements=rows, issues=issues, systems=systems,
                graph_components=len(components), connections=connection_evidence(graph), graph_policy=graph['policy'],
                limits=['All operational views exclude edges with ambiguous ownership; saved paper artifacts are unchanged.',
                        'Findings are review prompts, not engineering certification or automatically repaired connections.'])
