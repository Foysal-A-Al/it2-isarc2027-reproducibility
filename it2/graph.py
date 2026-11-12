"""One explicit-port graph policy for operational audits, inspection and revisions.

No inferred geometric edge, hydraulic correctness or physical ground truth is implied.
"""
from collections import defaultdict, Counter

GRAPH_POLICY = 'explicit-unambiguous-undirected-v2'


def ports_of(element):
    ports = {}
    for rel in getattr(element, 'HasPorts', None) or []:
        p = rel.RelatingPort
        if p is not None:
            ports[p.id()] = p
    for rel in getattr(element, 'IsNestedBy', None) or []:
        for p in rel.RelatedObjects or []:
            if p.is_a('IfcPort'):
                ports[p.id()] = p
    return list(ports.values())


def components(ids, adjacency):
    remaining, out = set(ids), []
    while remaining:
        stack, members = [min(remaining)], []
        while stack:
            current = stack.pop()
            if current not in remaining:
                continue
            remaining.remove(current)
            members.append(current)
            stack.extend(adjacency.get(current, set()) & remaining)
        out.append(sorted(members))
    return out


def build_graph(f):
    elements = sorted(f.by_type('IfcDistributionElement'), key=lambda e: e.id())
    owners, port_ids, adj = defaultdict(set), {}, defaultdict(set)
    for e in elements:
        port_ids[e.id()] = {p.id() for p in ports_of(e)}
        for p in port_ids[e.id()]:
            owners[p].add(e.id())
    edges, excluded, connected = set(), [], set()
    for rel in f.by_type('IfcRelConnectsPorts'):
        a, b = rel.RelatingPort, rel.RelatedPort
        reason = None
        if a is None or b is None:
            reason = 'missing_endpoint'
        else:
            connected.update((a.id(), b.id()))
            oa, ob = owners[a.id()], owners[b.id()]
            if len(oa) != 1 or len(ob) != 1:
                reason = 'missing_or_ambiguous_owner'
            else:
                x, y = next(iter(oa)), next(iter(ob))
                if x == y:
                    reason = 'same_element'
                else:
                    edges.add(tuple(sorted((x, y))))
                    adj[x].add(y); adj[y].add(x)
        if reason:
            excluded.append(dict(relation_step_id=rel.id(), reason=reason,
                                 ports=[p.id() for p in (a, b) if p is not None]))
    return dict(elements=elements, owners=owners, port_ids=port_ids, adjacency=adj,
                components=components([e.id() for e in elements], adj), edges=edges,
                connected_ports=connected, excluded=excluded, policy=GRAPH_POLICY)


def connection_evidence(graph):
    elements = {e.id(): e for e in graph['elements']}
    counts = Counter(e.GlobalId for e in elements.values() if e.GlobalId)
    edges, unresolved = [], []
    for a, b in sorted(graph['edges']):
        ga, gb = elements[a].GlobalId, elements[b].GlobalId
        if ga and gb and counts[ga] == counts[gb] == 1:
            edges.append(sorted((ga, gb)))
        else:
            unresolved.append(dict(element_step_ids=[a, b], reason='missing_or_duplicate_GlobalId'))
    return dict(policy=GRAPH_POLICY, edges=sorted(edges), unkeyed_edges=unresolved,
                excluded_connections=graph['excluded'])


def compare_connections(earlier, later, mapping):
    """Compare element adjacency only where an approved one-to-one map exists.

    Endpoints outside the map remain unresolved, never presumed deleted/added.
    """
    allowed = [r for r in mapping if (r.get('stage')=='globalid' and not r.get('requires_review')) or r.get('review_approved')]
    ca = Counter(r['old_GlobalId'] for r in allowed)
    cb = Counter(r['new_GlobalId'] for r in allowed)
    forward = {r['old_GlobalId']:r['new_GlobalId'] for r in allowed
               if r['old_GlobalId'] and r['new_GlobalId'] and ca[r['old_GlobalId']] == cb[r['new_GlobalId']] == 1}
    new_ids = set(forward.values())
    old_edges = {tuple(sorted(e)) for e in earlier.get('edges', [])}
    new_edges = {tuple(sorted(e)) for e in later.get('edges', [])}
    translated = {tuple(sorted((forward[a], forward[b]))) for a,b in old_edges if a in forward and b in forward}
    comparable = {e for e in new_edges if set(e) <= new_ids}
    return dict(policy=GRAPH_POLICY, coordinate_system='later-version GlobalIds',
                retained=[list(e) for e in sorted(translated & comparable)],
                removed=[list(e) for e in sorted(translated - comparable)],
                added=[list(e) for e in sorted(comparable - translated)],
                unresolved_earlier=[list(e) for e in sorted(e for e in old_edges if not set(e) <= set(forward))],
                unresolved_later=[list(e) for e in sorted(e for e in new_edges if not set(e) <= new_ids)],
                excluded_earlier=earlier.get('excluded_connections', []),
                excluded_later=later.get('excluded_connections', []),
                unkeyed_earlier=earlier.get('unkeyed_edges', []), unkeyed_later=later.get('unkeyed_edges', []),
                interpretation='Changes in exported undirected element adjacency on mapped endpoints; not physical or flow validation.')
