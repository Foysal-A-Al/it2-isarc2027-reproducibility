"""Compare file-level round trips with matched feature-level simulations -> results/roundtrip_eval.json"""
import json, collections
import numpy as np
from _common import FEAT, RES, dump
from it2.features import load_features
from it2.matching import perturb, score, METHODS

out = {}
for model in ["Duplex_Plumbing_20121113"]:
    O = load_features(json.load(open(FEAT / f"{model}.json")))
    gi = {x["g"]: i for i, x in enumerate(O)}
    per_cfg = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in sorted(RES.glob(f"roundtrip_{model}_*.json")):
        d = json.load(open(p)); c = d["config"]
        N = load_features(d["new"])
        # Convert stored GlobalId truth to the index-based truth expected by score().
        truth = {j: gi[d["truth"][x["g"]]] for j, x in enumerate(N) if d["truth"].get(x["g"]) in gi}
        cfg = f"{c['r']}_{c['move']}_{c['sigma']}"
        for name, fn in METHODS.items():
            per_cfg[cfg][name].append(score(fn(O, N), truth))
        per_cfg[cfg]["centroid_drift_median_m"].append(float(np.median([np.linalg.norm(N[j]["cen"] - O[i]["cen"]) for j, i in truth.items()])))
    for cfg, v in per_cfg.items():
        r, mv, sg = map(float, cfg.split("_"))
        S = collections.defaultdict(list)
        for s in range(20):
            # No decoy additions here: the file-level round trip only deletes/moves/recreates.
            new, truth = perturb(O, np.random.default_rng(300 + s), r, move=mv, sigma=sg, add=0)
            for name, fn in METHODS.items():
                S[name].append(score(fn(O, new), truth))
        out[f"{model}|{cfg}"] = {"file_level": {k: np.mean(a, 0).tolist() for k, a in v.items()}, "n_file_seeds": len(v["tag"]),
                                 "feature_level": {k: np.mean(a, 0).tolist() for k, a in S.items()}}
        print(cfg, json.dumps(out[f"{model}|{cfg}"], default=lambda x: round(x, 3)))
dump(out, RES / "roundtrip_eval.json")
