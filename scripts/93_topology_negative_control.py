"""Reproducible topology negative control on a source IFC.
20 independent seeds; preserves element degree and component membership, then
exports/reopens one modified IFC. Outputs kept outside the repository.
This is a new independent control, NOT claimed to recover the historical script.
Usage: python scripts/93_topology_negative_control.py SOURCE.ifc OUTPUT_DIR
"""
import collections
import csv
import hashlib
import json
import pathlib
import random
import sys

import ifcopenshell
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from it2.graph import build_graph
from it2.topology import topology_metrics

source = pathlib.Path(sys.argv[1]).resolve()
outdir = pathlib.Path(sys.argv[2]).resolve()
outdir.mkdir(parents=True, exist_ok=True)
f = ifcopenshell.open(str(source))
original = build_graph(f)
relations = sorted(f.by_type("IfcRelConnectsPorts"), key=lambda r: r.id())
owners = original["owners"]
base = []
for rel in relations:
    a, b = rel.RelatingPort, rel.RelatedPort
    if len(owners[a.id()]) != 1 or len(owners[b.id()]) != 1:
        raise RuntimeError("Ambiguous port host: this experiment requires unique ownership")
    base.append((next(iter(owners[a.id()])), next(iter(owners[b.id()]))))
assert len(set(tuple(sorted(x)) for x in base)) == len(base) == len(original["edges"])
initial_components = {frozenset(x) for x in original["components"]}
main = max(original["components"], key=len)
main = set(main)
candidates = [i for i, (a, b) in enumerate(base) if a in main and b in main]
initial_degree = collections.Counter(z for edge in base for z in edge)
baseline_metrics = topology_metrics(str(source), opened=f, graph=original)


def partition(edges):
    adj = collections.defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    remaining = {e.id() for e in original["elements"]}
    parts = set()
    while remaining:
        start = next(iter(remaining))
        stack, group = [start], set()
        while stack:
            v = stack.pop()
            if v in group:
                continue
            group.add(v)
            stack.extend(adj[v] - group)
        remaining -= group
        parts.add(frozenset(group))
    return parts


def run(seed):
    rng = random.Random(seed)
    edges = list(base)
    existing = {tuple(sorted(e)) for e in edges}
    swaps = []
    attempts = 0
    goal = int(len(base) * 0.10) + 1
    while len(existing - set(original["edges"])) < goal and attempts < 50000:
        attempts += 1
        i, j = rng.sample(candidates, 2)
        a, b = edges[i]
        c, d = edges[j]
        if len({a, b, c, d}) != 4:
            continue
        after1, after2 = (a, d), (c, b)
        old1, old2 = tuple(sorted(edges[i])), tuple(sorted(edges[j]))
        new1, new2 = tuple(sorted(after1)), tuple(sorted(after2))
        if new1 in existing or new2 in existing:
            continue
        proposed = (existing - {old1, old2}) | {new1, new2}
        if partition(proposed) != initial_components:
            continue
        edges[i], edges[j] = after1, after2
        existing = proposed
        swaps.append([i, j])
    if len(existing - set(original["edges"])) < goal:
        raise RuntimeError(f"Seed {seed}: goal not reached after {attempts} candidates")
    deg = collections.Counter(z for edge in edges for z in edge)
    assert deg == initial_degree
    assert partition(existing) == initial_components
    assert len(existing) == len(original["edges"])
    changed = len(set(original["edges"]) - existing)
    return edges, swaps, {"seed": seed, "swaps": len(swaps), "changed_edges": changed,
                           "changed_pct": 100.0 * changed / len(base), "components": len(initial_components),
                           "degrees_preserved": True, "partition_preserved": True,
                           "edges_preserved": True, "port_relation_count_preserved": True}


records, first_edges, first_swaps = [], None, None
for seed in range(20):
    edges, swaps, record = run(seed)
    records.append(record)
    if seed == 0:
        first_edges, first_swaps = edges, swaps
    print("SEED", seed, "changed", record["changed_edges"], "swaps", record["swaps"], flush=True)

# Replay seed 0 at the IFC port-relation level, then export and independently reopen.
for i, j in first_swaps:
    rel1, rel2 = relations[i], relations[j]
    rel1.RelatedPort, rel2.RelatedPort = rel2.RelatedPort, rel1.RelatedPort
revised_path = outdir / "Duplex_Plumbing_rewired_seed0.ifc"
f.write(str(revised_path))
after_file = ifcopenshell.open(str(revised_path))
after_graph = build_graph(after_file)
after_metrics = topology_metrics(str(revised_path), opened=after_file, graph=after_graph)
expected_edges = {tuple(sorted(e)) for e in first_edges}
assert after_graph["edges"] == expected_edges, "Reopened IFC edges do not match planned swap results"
metric_keys = ["D", "PC", "ports", "CC", "components", "TF", "LC", "SM", "systems"]
assert all(baseline_metrics[k] == after_metrics[k] for k in metric_keys), "Aggregate metric changed"
assert {frozenset(x) for x in after_graph["components"]} == initial_components
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
report = {"source_file": source.name, "source_sha256": source_hash,
          "source_edges": len(original["edges"]), "source_elements": len(original["elements"]),
          "source_components": len(initial_components), "seed_count": 20,
          "trial_records": records, "source_metrics": {k: baseline_metrics[k] for k in metric_keys},
          "reopened_metrics": {k: after_metrics[k] for k in metric_keys},
          "ifc_export_reopen_success": True,
          "reopened_changed_edges": len(original["edges"] - after_graph["edges"]),
          "interpretation": "Demonstrates descriptor blindness to controlled adjacency changes; not a claim of incorrect physical wiring.",
          "provenance": "New independent reproduction control; does not authenticate the historical rewiring trial outputs."}
(outdir / "topology_rewiring_20seed_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
with (outdir / "topology_rewiring_20seed_audit.csv").open("w", newline="", encoding="utf-8") as h:
    w = csv.DictWriter(h, fieldnames=records[0].keys())
    w.writeheader()
    w.writerows(records)
print("PASSED: 20 trials, exported IFC reopened, metrics unchanged", flush=True)
