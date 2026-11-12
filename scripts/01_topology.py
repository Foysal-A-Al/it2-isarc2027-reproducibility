"""Section 5.2: topology audit of all seven models -> results/topology.json"""
from _common import IFC, RES, dump
from it2.topology import topology_metrics

rows = []
# Audit the available IFC files in deterministic filename order.
for p in sorted(IFC.glob("*.ifc")):
    m = topology_metrics(str(p))
    rows.append(m)
    print(f"{m['file']:45s} D={m['D']:6d} PC={m['PC']:.2f} comps={m['components']:4d} "
          f"LC={m['LC']:.2f} SM={m['SM']:.2f} CC={m['CC']:.2f} ctrl={m['control_elements']}")
dump(rows, RES / "topology.json")
