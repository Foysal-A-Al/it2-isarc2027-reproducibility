"""Cross-check it2.topology against IfcOpenShell's own system utilities for one IFC file.

it2.topology walks IfcRelConnectsPorts itself. This script rebuilds the element graph
independently with ifcopenshell.util.system (get_ports, get_connected_port,
get_port_element) and compares port counts, edges and connected components.

Usage: python scripts/topology_crosscheck.py <file.ifc> [out.json]
"""
import collections, hashlib, json, pathlib, sys
import ifcopenshell
import ifcopenshell.util.system as system

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from it2.topology import topology_details, topology_metrics


def _partition(labels):
    """Connected components as a set of frozensets, independent of label numbering."""
    groups = collections.defaultdict(set)
    for node, label in labels.items():
        groups[label].add(node)
    return {frozenset(g) for g in groups.values()}


def crosscheck(path):
    f = ifcopenshell.open(path)
    D = f.by_type("IfcDistributionElement")
    ids = {e.GlobalId for e in D}
    # Independent graph: ports and their partners come from IfcOpenShell, not it2.
    ports, adj = {}, collections.defaultdict(set)
    for e in D:
        own = system.get_ports(e)
        ports[e.GlobalId] = len(own)
        for p in own:
            other = system.get_connected_port(p)
            owner = system.get_port_element(other) if other is not None else None
            if owner is not None and owner.GlobalId in ids and owner.GlobalId != e.GlobalId:
                adj[e.GlobalId].add(owner.GlobalId)
                adj[owner.GlobalId].add(e.GlobalId)
    label, n = {}, 0
    for g in ids:
        if g in label:
            continue
        stack = [g]
        while stack:
            x = stack.pop()
            if x not in label:
                label[x] = n
                stack += list(adj[x])
        n += 1
    rows = topology_details(path, opened=f)
    metrics = topology_metrics(path, opened=f)
    it2_ports = {r["GlobalId"]: r["ports"] for r in rows}
    it2_parts = _partition({r["GlobalId"]: r["component"] for r in rows})
    ifc_parts = _partition(label)
    port_mismatch = sorted(g for g in ids if it2_ports.get(g) != ports[g])
    return dict(
        file=pathlib.Path(path).name,
        sha256=hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest(),
        schema=f.schema_identifier,
        ifcopenshell=ifcopenshell.version,
        distribution_elements=len(D),
        it2=dict(components=metrics["components"], isolated=metrics["isolated"], PC=metrics["PC"],
                 CC=metrics["CC"], ports=metrics["ports"], LC=metrics["LC"]),
        ifcopenshell_util=dict(components=len(ifc_parts), edges=sum(map(len, adj.values())) // 2,
                               elements_with_ports=sum(1 for v in ports.values() if v)),
        port_count_mismatches=port_mismatch,
        components_identical=it2_parts == ifc_parts,
        agree=not port_mismatch and it2_parts == ifc_parts,
    )


if __name__ == "__main__":
    result = crosscheck(sys.argv[1])
    text = json.dumps(result, indent=2) + "\n"
    if len(sys.argv) > 2:
        pathlib.Path(sys.argv[2]).write_text(text, newline="\n")
    print(text, end="")
    sys.exit(0 if result["agree"] else 1)
