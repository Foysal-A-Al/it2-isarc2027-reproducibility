"""Section 5.3: simulated revisions, 20 seeds, share of recreated elements r in {0,0.1,0.2,0.3,0.5}
-> results/identity_<model>.json (mean and 95% bootstrap CI of P, R, F1; Wilcoxon hybrid vs Tag)"""
import sys, json, collections
import numpy as np
from scipy.stats import wilcoxon
from _common import FEAT, RES, IDENTITY_MODELS, dump
from it2.features import load_features
from it2.matching import perturb, score, bootstrap_ci, METHODS

SEEDS = 20
for m in sys.argv[1:] or IDENTITY_MODELS:
    X = load_features(json.load(open(FEAT / f"{m}.json")))
    # Count repeated placement origins within the same class/container partition.
    key = collections.Counter((x["cls"], x["cont"], tuple(np.round(x["pl"], 4))) for x in X)
    shared = [x["cls"] for x in X if key[(x["cls"], x["cont"], tuple(np.round(x["pl"], 4)))] > 1]
    out = {"n": len(X), "shared_placement_share": len(shared) / len(X),
           "shared_placement_by_class": dict(collections.Counter(shared))}
    for r in [0.0, 0.1, 0.2, 0.3, 0.5]:
        S = collections.defaultdict(list)
        # Reuse each simulated revision across all methods for a paired comparison.
        for seed in range(SEEDS):
            new, truth = perturb(X, np.random.default_rng(seed), r)
            for name, fn in METHODS.items():
                S[name].append(score(fn(X, new), truth))
        # Summarize precision/recall/F1 across 20 seeds, with percentile bootstrap intervals.
        res = {name: {k: bootstrap_ci(np.array(v)[:, i]) for i, k in enumerate("PRF")} for name, v in S.items()}
        # At nonzero recreation, compare paired recall scores rather than independent samples.
        if r > 0:
            res["wilcoxon_p_hybrid_vs_tag"] = float(wilcoxon(np.array(S["hybrid"])[:, 1], np.array(S["tag"])[:, 1]).pvalue)
        out[str(r)] = res
        print(m, r, {k: f"P{res[k]['P'][0]:.3f} R{res[k]['R'][0]:.3f}" for k in METHODS})
    dump(out, RES / f"identity_{m}.json")
