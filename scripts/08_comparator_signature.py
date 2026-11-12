"""External-method comparison: graph-signature matching vs the IT2 hybrid (paper Table 3b).

A two-round Weisfeiler-Lehman signature is computed over the explicit-port adjacency graph of
each real IFC model (initial label = element class, refined by sorted neighbour labels). Object
GlobalIds and Tags are never used, matching the identifier-masked setting. Two signature variants
run through the *same* perturb()/score() harness and the same 20 seeds as scripts/03_identity.py:

  sig_struct  pure structural: accept only signature groups with a unique 1-old <-> 1-new pair.
  sig_geo     signature-partitioned geometric assignment (Hungarian on centre + sorted dims,
              with the published 0.5 m gate) within each signature class.

Requires data/ifc/<model>.ifc (run data/download.py first) for the connectivity graph, and
data/features/<model>.json for the geometry fingerprints. Output: results/comparator_signature.json
-> scripts/07_figures.py / the manuscript Table 3b. Deterministic (seeds 0-19, bootstrap seed 0).
"""
import collections, hashlib, json
import numpy as np
from scipy.optimize import linear_sum_assignment
from _common import IFC, FEAT, RES, IDENTITY_MODELS, dump
import ifcopenshell
from it2.graph import build_graph
from it2.features import load_features
from it2.matching import perturb, score, match_tag, match_placement, match_hybrid, bootstrap_ci

SEEDS = 20
RATES = [0.0, 0.1, 0.2, 0.3, 0.5]
GATE = 0.5           # same geometry gate as the published hybrid (DEFAULT_TAU)
WL_ROUNDS = 2
MAX_CELLS = 6_000_000  # drop the dimension term for a pathologically large signature partition


def wl_signatures(adjacency, labels, rounds=WL_ROUNDS):
    """Weisfeiler-Lehman refinement: label = hash(own label | sorted neighbour labels)."""
    lab = dict(labels)
    for _ in range(rounds):
        nxt = {}
        for v in lab:
            neigh = ",".join(sorted(lab[u] for u in adjacency.get(v, ())))
            nxt[v] = hashlib.sha1((lab[v] + "|" + neigh).encode()).hexdigest()[:12]
        lab = nxt
    return lab


def signatures_by_globalid(model):
    """Open the IFC, build the explicit-port graph, return {GlobalId: WL signature}."""
    f = ifcopenshell.open(str(IFC / f"{model}.ifc"))
    g = build_graph(f)
    labels = {e.id(): e.is_a() for e in g["elements"]}
    id2g = {e.id(): e.GlobalId for e in g["elements"]}
    sig = wl_signatures(g["adjacency"], labels)
    out = {}
    for sid, gid in id2g.items():
        out.setdefault(gid, sig[sid])   # first occurrence wins on duplicate GlobalId
    return out


def match_sig_struct(old, new):
    go, gn = collections.defaultdict(list), collections.defaultdict(list)
    for i, x in enumerate(old): go[x["sig"]].append(i)
    for j, y in enumerate(new): gn[y["sig"]].append(j)
    return [(A[0], gn[s][0]) for s, A in go.items() if len(A) == 1 and len(gn.get(s, [])) == 1]


def match_sig_geo(old, new, gate=GATE):
    go, gn = collections.defaultdict(list), collections.defaultdict(list)
    for i, x in enumerate(old): go[x["sig"]].append(i)
    for j, y in enumerate(new): gn[y["sig"]].append(j)
    pairs = []
    for s, A in go.items():
        B = gn.get(s, [])
        if not A or not B:
            continue
        Pa = np.array([old[i]["cen"] for i in A]); Pb = np.array([new[j]["cen"] for j in B])
        C = np.linalg.norm(Pa[:, None, :] - Pb[None, :, :], axis=2)
        if len(A) * len(B) <= MAX_CELLS:
            Da = np.array([old[i]["dim"] for i in A]); Db = np.array([new[j]["dim"] for j in B])
            C = C + np.abs(Da[:, None, :] - Db[None, :, :]).sum(2)
        r, c = linear_sum_assignment(C)
        pairs += [(A[a], B[b]) for a, b in zip(r, c) if C[a, b] <= gate]
    return pairs


def main():
    methods = {"tag": match_tag, "placement": match_placement, "hybrid": match_hybrid,
               "sig_struct": match_sig_struct, "sig_geo": match_sig_geo}
    report = {"seeds": SEEDS, "rates": RATES, "wl_rounds": WL_ROUNDS, "gate_m": GATE, "models": {}}
    for m in IDENTITY_MODELS:
        byg = signatures_by_globalid(m)
        X = load_features(json.load(open(FEAT / f"{m}.json")))
        for x in X:
            x["sig"] = byg.get(x["g"], x["cls"])   # fall back to class if no graph node
        counts = collections.Counter(x["sig"] for x in X)
        entry = {"n": len(X), "distinct_signatures": len(counts),
                 "unique_signature_fraction": sum(1 for x in X if counts[x["sig"]] == 1) / len(X),
                 "rates": {}}
        for r in RATES:
            S = collections.defaultdict(list)
            for seed in range(SEEDS):
                new, truth = perturb(X, np.random.default_rng(seed), r)
                for name, fn in methods.items():
                    S[name].append(score(fn(X, new), truth))
            row = {name: dict(zip("PRF", np.array(S[name]).mean(0))) for name in methods}
            diff = np.array(S["hybrid"])[:, 1] - np.array(S["sig_geo"])[:, 1]
            mean, lo, hi = bootstrap_ci(diff)
            row["hybrid_minus_siggeo_recall"] = dict(mean=mean, ci_low=lo, ci_high=hi)
            entry["rates"][str(r)] = row
        report["models"][m] = entry
        print(f'{m}: n={entry["n"]} distinct_sig={entry["distinct_signatures"]} '
              f'unique_frac={entry["unique_signature_fraction"]:.3f}')
    dump(report, RES / "comparator_signature.json")
    print("wrote", RES / "comparator_signature.json")


if __name__ == "__main__":
    main()
