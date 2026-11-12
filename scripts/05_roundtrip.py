"""Section 5.4: file-level round trip. Writes a perturbed IFC, re-opens it, re-extracts features.
Usage: python 05_roundtrip.py <model> <seed> <r> <move> <sigma>      (about 1 to 2 min per run)"""
import sys, pathlib
import numpy as np
import ifcopenshell, ifcopenshell.guid, ifcopenshell.api, ifcopenshell.util.unit as uu
from _common import IFC, FEAT, RES, dump
from it2.features import extract_features

model, seed, r, mv, sig = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
src = IFC / f"{model}.ifc"
orig_path = FEAT / f"{model}.json"
if not orig_path.exists():
    dump(extract_features(ifcopenshell.open(str(src))), orig_path)
# Read a real IFC, then perturb its entities rather than only its fingerprint vectors.
f = ifcopenshell.open(str(src))
unit = 1.0 / uu.calculate_unit_scale(f)        # metres -> file units
rng = np.random.default_rng(seed)
truth, dele = {}, []
for e in f.by_type("IfcDistributionElement"):
    if rng.random() < 0.05:
        dele.append(e); continue
    # Keep the old ID as truth before assigning a fresh, valid IFC GlobalId.
    old = e.GlobalId
    e.GlobalId = ifcopenshell.guid.new()
    truth[e.GlobalId] = old
    if rng.random() < r:                                   # recreated: new Tag and instance name
        e.Tag = "R%d" % rng.integers(10**12)
        e.Name = (e.Name or "").rsplit(":", 1)[0] + ":%d" % rng.integers(10**9)
    if rng.random() < mv:                                  # moved in plan, own placement only
        d = rng.normal(0, sig, 2) * unit
        ax = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((float(d[0]), float(d[1]), 0.0)), None, None)
        # Add a child placement, preserving the existing placement as its parent.
        e.ObjectPlacement = f.createIfcLocalPlacement(e.ObjectPlacement, ax)
# Remove deleted products through the IFC API so related entities are handled consistently.
for e in dele:
    ifcopenshell.api.run("root.remove_product", f, product=e)
tmp = pathlib.Path("/tmp") / f"rt_{model}_{seed}.ifc"
f.write(str(tmp))
# Re-open the written IFC and independently extract geometry for the file-level check.
new = extract_features(ifcopenshell.open(str(tmp)))
dump({"new": new, "truth": truth, "config": dict(seed=seed, r=r, move=mv, sigma=sig)},
     RES / f"roundtrip_{model}_{seed}_{r}_{mv}_{sig}.json")
print("done", len(new), "elements")
