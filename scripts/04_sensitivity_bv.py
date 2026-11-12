"""Sections 5.5 and 5.6: sensitivity grid over lambda x tau, and simulated binding validity
-> results/extra_<model>.json"""
import sys, json, collections
import numpy as np
from _common import FEAT, RES, dump
from it2.features import load_features
from it2.matching import perturb, score, bootstrap_ci, match_tag, match_placement, match_hybrid

EQUIPMENT = ("IfcFlowTerminal", "IfcFlowController", "IfcEnergyConversionDevice",
             "IfcFlowMovingDevice", "IfcFlowStorageDevice", "IfcFlowTreatmentDevice")
for m in sys.argv[1:] or ["Clinic_HVAC", "Duplex_Plumbing_20121113"]:
    X = load_features(json.load(open(FEAT / f"{m}.json")))
    out = {"grid": {}}
    # hardest condition: every element recreated (Tag stage never helps), 30% moved by N(0, 0.3 m)
    for lam in [0, 0.15, 0.3, 0.6, 1.0]:
        for tau in [0.25, 0.5, 1.0, 2.0]:
            F = [score(match_hybrid(X, new, lam, tau, use_tag=False), truth)
                 for new, truth in (perturb(X, np.random.default_rng(100 + s), 1.0, move=0.3, sigma=0.3) for s in range(5))]
            out["grid"][f"{lam}|{tau}"] = np.mean(F, 0).tolist()
            print(m, lam, tau, np.round(np.mean(F, 0), 3))
    # Treat equipment classes as hypothetical bound assets; there is no live BMS point list.
    bound = [i for i, x in enumerate(X) if x["cls"] in EQUIPMENT]
    B = collections.defaultdict(list)
    for s in range(20):
        new, truth = perturb(X, np.random.default_rng(200 + s), 0.3)
        # Invert ground truth to find the surviving counterpart of each old bound element.
        inv = {i: j for j, i in truth.items()}
        alive = [i for i in bound if i in inv]
        # The GUID baseline encodes the assumption that every GlobalId is regenerated.
        # It intentionally predicts no recovered bindings; it is not an actual GUID lookup.
        for name, fn in [("guid", lambda a, b: []), ("tag", match_tag), ("placement", match_placement), ("hybrid", match_hybrid)]:
            mp = dict(fn(X, new))
            # Evaluate correct and wrong links only among bindings whose assets survive.
            B[name].append((sum(mp.get(i) == inv[i] for i in alive) / len(alive),
                            sum(i in mp and mp[i] != inv[i] for i in alive) / len(alive)))
    out["bound_elements"] = len(bound)
    out["bv"] = {k: {"correct": bootstrap_ci(np.array(v)[:, 0]), "wrong": bootstrap_ci(np.array(v)[:, 1])} for k, v in B.items()}
    print(m, "bound", len(bound), {k: round(v["correct"][0], 3) for k, v in out["bv"].items()})
    dump(out, RES / f"extra_{m}.json")
